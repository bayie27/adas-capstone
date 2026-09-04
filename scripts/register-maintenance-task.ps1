<#
.SYNOPSIS
    Registers, verifies, or removes the Windows Scheduled Task that fires
    the daily restart (NFR-16, be_plan/18_PKG_scheduled_maintenance.md
    Step 4).

.DESCRIPTION
    This is the piece 08_PKG_backup_ops.md Step 7's orchestrator table
    always claimed existed ("Windows (demo) | adas-maintenance.ps1 + a
    Windows Scheduled Task") but never actually shipped — nothing on this
    laptop fired on a schedule until this script registered one.

    Registers task path \ADAS\DailyRestart, idempotent via
    Register-ScheduledTask -Force. The trigger hour is read from the
    repo-root .env's MAINTENANCE_HOUR_LOCAL (default 3 when absent or
    unparseable) — this is what makes that setting live on the restart
    half; the in-app cron job (app/main.py) reads the same setting
    directly for the backup half.

    Catch-up is deliberately OFF here (-StartWhenAvailable:$false) — see
    18_PKG_scheduled_maintenance.md's decision table. A restart is
    process-lifecycle: firing it at whatever arbitrary hour the laptop
    next boots (which could be minutes before a defense) is worse than
    skipping a night. This is the opposite of the in-app backup job's
    catch-up policy (ON) by design; do not make the two symmetric.

    Principal: the current interactive user, -RunLevel Limited,
    -LogonType Interactive. Trade-off: Interactive only fires while that
    user is logged on -- correct for a demo laptop left on with the lid
    closed, and needs no special rights. The alternative, S4U, would fire
    without a login but requires the "log on as batch job" right and is
    unreliable on Windows Home. This script always prints which principal
    it used so the choice is never invisible.

    Never reimplements backup/restore/restart logic -- the task's only
    job is to invoke scripts\adas-maintenance.ps1 -Action Restart, which
    in turn invokes `uv run python -m app.maintenance`.

.PARAMETER Verify
    Prints the resolved trigger time, NextRunTime, LastRunTime and
    LastTaskResult for the registered task. This is the demo artifact --
    how you show a panel the restart is scheduled and when it last ran.

.PARAMETER Unregister
    Removes the task. Safe to call even if it was never registered.

.EXAMPLE
    scripts\register-maintenance-task.ps1
    # Register (or re-register) the task using .env's MAINTENANCE_HOUR_LOCAL.

.EXAMPLE
    scripts\register-maintenance-task.ps1 -Verify

.EXAMPLE
    scripts\register-maintenance-task.ps1 -Unregister
#>

param(
    [switch]$Verify,
    [switch]$Unregister
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$TaskPath = "\ADAS\"
$TaskName = "DailyRestart"
$FullTaskName = "$TaskPath$TaskName"

function Write-Step($message) {
    Write-Host "[register-maintenance-task] $message" -ForegroundColor Cyan
}

# ---------------------------------------------------------------------------
# .env parsing -- MAINTENANCE_HOUR_LOCAL, default 3 when absent/unparseable.
# Deliberately a plain line scan, not a dependency on the Python settings
# loader: this script must work even before `uv sync` has ever run.
# ---------------------------------------------------------------------------

function Get-MaintenanceHourLocal {
    $envPath = Join-Path $RepoRoot ".env"
    $default = 3

    # Match Python's pydantic-settings precedence.  A process-level value is
    # inherited by the task registration shell and by the eventual
    # adas-maintenance.ps1 child; otherwise both resolve the repo-root .env.
    $processValue = [Environment]::GetEnvironmentVariable("MAINTENANCE_HOUR_LOCAL")
    if ($processValue -match '^\d+$') {
        $processHour = [int]$processValue
        if ($processHour -ge 0 -and $processHour -le 23) {
            return $processHour
        }
    }

    if (-not (Test-Path -LiteralPath $envPath)) {
        Write-Warning ".env not found at repo root -- defaulting MAINTENANCE_HOUR_LOCAL to $default."
        return $default
    }

    $rawValue = $null
    foreach ($line in Get-Content $envPath) {
        if ($line -match '^\s*MAINTENANCE_HOUR_LOCAL\s*=\s*(\d+)\s*$') {
            $rawValue = $Matches[1]
        }
    }
    if ($null -eq $rawValue) {
        Write-Warning "MAINTENANCE_HOUR_LOCAL not set in .env -- defaulting to $default."
        return $default
    }

    $hour = [int]$rawValue
    if ($hour -lt 0 -or $hour -gt 23) {
        Write-Warning "MAINTENANCE_HOUR_LOCAL=$hour in .env is out of range 0-23 -- defaulting to $default."
        return $default
    }
    return $hour
}

# Same pwsh -> powershell fallback as scripts/start-dev.ps1 -- a stock
# Windows box has no pwsh on PATH, and a Scheduled Task's Action must name
# a concrete executable (there is no live $script:ShellExe from another
# script's process to reuse across the process boundary).
$script:ShellExe = if (Get-Command pwsh -ErrorAction SilentlyContinue) { (Get-Command pwsh).Source } else { (Get-Command powershell).Source }

# ---------------------------------------------------------------------------
# -Verify / -Unregister
# ---------------------------------------------------------------------------

if ($Verify) {
    $task = Get-ScheduledTask -TaskPath $TaskPath -TaskName $TaskName -ErrorAction SilentlyContinue
    if (-not $task) {
        Write-Host "Task $FullTaskName is not registered."
        exit 1
    }
    $info = $task | Get-ScheduledTaskInfo
    $trigger = $task.Triggers | Select-Object -First 1
    Write-Host "Task:              $FullTaskName"
    Write-Host "State:             $($task.State)"
    Write-Host "Trigger time:      $($trigger.StartBoundary)"
    Write-Host "Principal:         $($task.Principal.UserId) (LogonType=$($task.Principal.LogonType), RunLevel=$($task.Principal.RunLevel))"
    Write-Host "StartWhenAvailable: $($task.Settings.StartWhenAvailable)"
    Write-Host "NextRunTime:       $($info.NextRunTime)"
    Write-Host "LastRunTime:       $($info.LastRunTime)"
    Write-Host "LastTaskResult:    $($info.LastTaskResult)"
    exit 0
}

if ($Unregister) {
    $task = Get-ScheduledTask -TaskPath $TaskPath -TaskName $TaskName -ErrorAction SilentlyContinue
    if (-not $task) {
        Write-Step "Task $FullTaskName was not registered. Nothing to do."
        exit 0
    }
    Unregister-ScheduledTask -TaskPath $TaskPath -TaskName $TaskName -Confirm:$false
    Write-Step "Unregistered $FullTaskName."
    exit 0
}

# ---------------------------------------------------------------------------
# Register (default action), idempotent.
# ---------------------------------------------------------------------------

$hour = Get-MaintenanceHourLocal
$triggerTime = Get-Date -Hour $hour -Minute 0 -Second 0
Write-Step "MAINTENANCE_HOUR_LOCAL resolved to $hour (trigger at $($triggerTime.ToString('HH:mm')) local)."

$maintScript = Join-Path $RepoRoot "scripts\adas-maintenance.ps1"
if (-not (Test-Path $maintScript)) {
    Write-Error "adas-maintenance.ps1 not found at $maintScript."
    exit 1
}

$action = New-ScheduledTaskAction -Execute $script:ShellExe `
    -Argument "-NoProfile -File `"$maintScript`" -Action Restart" `
    -WorkingDirectory $RepoRoot

$trigger = New-ScheduledTaskTrigger -Daily -At $triggerTime

# -StartWhenAvailable:$false is the deliberate decision (see .DESCRIPTION)
# -- do not "helpfully" turn this on to match the backup job's catch-up.
$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable:$false `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 15) `
    -MultipleInstances IgnoreNew

$userId = "$env:USERDOMAIN\$env:USERNAME"
$principal = New-ScheduledTaskPrincipal -UserId $userId -LogonType Interactive -RunLevel Limited
Write-Step "Principal: $userId, LogonType=Interactive, RunLevel=Limited -- fires only while this user is logged on (correct for a demo laptop left on with the lid closed; needs no 'log on as batch job' right, unlike S4U)."

Register-ScheduledTask -TaskPath $TaskPath -TaskName $TaskName `
    -Action $action -Trigger $trigger -Settings $settings -Principal $principal `
    -Description "ADAS daily restart (NFR-16) -- invokes adas-maintenance.ps1 -Action Restart, which calls into app.maintenance for the actual backup/restart work." `
    -Force | Out-Null

Write-Step "Registered $FullTaskName, daily at $($triggerTime.ToString('HH:mm')) local."
Write-Step "Run with -Verify to confirm the trigger and see the last/next run."
