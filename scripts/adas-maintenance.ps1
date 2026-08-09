<#
.SYNOPSIS
    Windows demo orchestrator for backup, restore, and the daily restart
    (be_plan/08_PKG_backup_ops.md, D-011).

.DESCRIPTION
    Explicit and manual, as the deployment note requires — there is no
    systemd on Windows, so this script is a thin wrapper that stops/starts
    the two OS processes (the FastAPI backend and the AI engine) around
    calls into the shared Python maintenance core
    (`uv run python -m app.maintenance <command>`). It never re-implements
    backup/restore/verify logic itself; every actual file operation is one
    of those Python subcommands.

    Process lifecycle is tracked via PID files under var\run\, written by
    this script whenever it starts a process. Use -Action Start once to
    adopt processes you started manually (or just start them with this
    script from the beginning) before running Restart/Restore, which need
    to know what to stop.

.PARAMETER Action
    Start | Stop | Backup | Restart | Restore | Archive

.PARAMETER BackupId
    Required for -Action Restore — the backup id to restore (see
    `uv run python -m app.maintenance list`).

.EXAMPLE
    scripts\adas-maintenance.ps1 -Action Start
    scripts\adas-maintenance.ps1 -Action Backup
    scripts\adas-maintenance.ps1 -Action Restart
    scripts\adas-maintenance.ps1 -Action Restore -BackupId 69c760b1a0d24f6e8c16e675564a5ecd
    scripts\adas-maintenance.ps1 -Action Archive
#>

param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("Start", "Stop", "Backup", "Restart", "Restore", "Archive")]
    [string]$Action,

    [string]$BackupId,

    [int]$ReadyTimeoutSeconds = 60
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$RunDir = Join-Path $RepoRoot "var\run"
New-Item -ItemType Directory -Force -Path $RunDir | Out-Null
$BackendPidFile = Join-Path $RunDir "backend.pid"
$AiPidFile = Join-Path $RunDir "ai_engine.pid"

function Write-Step($message) {
    Write-Host "[adas-maintenance] $message" -ForegroundColor Cyan
}

function Invoke-Maintenance([string[]]$MaintenanceArgs) {
    # $output = & ... (an assignment, not a bare pipeline statement) captures
    # the native command's stdout instead of letting it flow straight into
    # this function's own output stream. Without this, every JSON line the
    # CLI prints becomes part of Invoke-Maintenance's *return value* too, so
    # `$exit = Invoke-Maintenance @(...)` ends up an array (JSON lines plus
    # the exit code) rather than a bare int — and `$exit -ne 0` against an
    # array is a PowerShell *filter* (returns non-matching elements), which
    # is non-empty (truthy) any time the command printed anything at all.
    # That silently inverted every success/failure check in this script:
    # `-Action Restart` reported "backup failed" on a run that produced a
    # fully valid backup file on disk. Write-Host below writes straight to
    # the console host, bypassing the success stream, so the printed JSON
    # stays visible without re-polluting the return value.
    Write-Step "python -m app.maintenance $($MaintenanceArgs -join ' ')"
    Push-Location (Join-Path $RepoRoot "backend")
    try {
        $output = & uv run --no-sync python -m app.maintenance @MaintenanceArgs
        $output | ForEach-Object { Write-Host $_ }
        return $LASTEXITCODE
    }
    finally {
        Pop-Location
    }
}

function Stop-TrackedProcess([string]$PidFile, [string]$Label) {
    if (-not (Test-Path $PidFile)) {
        Write-Step "$Label`: no PID file, nothing to stop."
        return
    }
    $processId = Get-Content $PidFile -ErrorAction SilentlyContinue
    if (-not $processId) {
        Remove-Item $PidFile -ErrorAction SilentlyContinue
        return
    }
    $proc = Get-Process -Id $processId -ErrorAction SilentlyContinue
    if ($null -eq $proc) {
        Write-Step "$Label`: PID $processId is not running."
        Remove-Item $PidFile -ErrorAction SilentlyContinue
        return
    }
    Write-Step "Stopping $Label (PID $processId)..."
    # taskkill /T, not Stop-Process: the PID recorded here is `uv.exe`
    # (Start-Backend/Start-AiEngine launch via `uv run ...`), and on Windows
    # `uv run` does not exec-replace itself — it stays alive as a parent
    # spawning the real fastapi/python worker as a child. Stop-Process only
    # kills the recorded PID, so the worker (and the open port) survived
    # every -Action Stop even though the script reported success and
    # deleted the PID file. taskkill /T walks the whole process tree.
    & taskkill /PID $processId /T /F 2>&1 | Out-Null
    Start-Sleep -Milliseconds 300
    if (Get-Process -Id $processId -ErrorAction SilentlyContinue) {
        Write-Step "$Label`: PID $processId still alive after taskkill /T /F — leaving PID file for investigation."
        return
    }
    Remove-Item $PidFile -ErrorAction SilentlyContinue
}

function Start-Backend {
    Write-Step "Starting backend..."
    $proc = Start-Process -FilePath "uv" `
        -ArgumentList "run", "fastapi", "run", "backend/app/main.py" `
        -WorkingDirectory $RepoRoot -PassThru -WindowStyle Minimized
    Set-Content -Path $BackendPidFile -Value $proc.Id
    Write-Step "Backend started (PID $($proc.Id))."
}

function Start-AiEngine {
    Write-Step "Starting AI engine..."
    $proc = Start-Process -FilePath "uv" `
        -ArgumentList "run", "python", "ai_engine/main.py" `
        -WorkingDirectory $RepoRoot -PassThru -WindowStyle Minimized
    Set-Content -Path $AiPidFile -Value $proc.Id
    Write-Step "AI engine started (PID $($proc.Id))."
}

function Wait-Ready {
    Write-Step "Waiting for /healthz/ready and a fresh AI heartbeat (timeout ${ReadyTimeoutSeconds}s)..."
    $exitCode = Invoke-Maintenance @("restart", "--phase", "wait", "--timeout", $ReadyTimeoutSeconds)
    return $exitCode -eq 0
}

switch ($Action) {
    "Start" {
        Start-Backend
        Start-AiEngine
        Wait-Ready | Out-Null
    }

    "Stop" {
        Stop-TrackedProcess -PidFile $AiPidFile -Label "AI engine"
        Stop-TrackedProcess -PidFile $BackendPidFile -Label "backend"
    }

    "Backup" {
        $exitCode = Invoke-Maintenance @("backup", "--origin", "manual")
        exit $exitCode
    }

    "Restart" {
        # D-011 / Step 7: backup first (online, services still up), timed
        # separately from restart downtime.
        Write-Step "Phase 1/2: online backup."
        $backupExit = Invoke-Maintenance @("backup", "--origin", "scheduled")
        if ($backupExit -ne 0) {
            Write-Error "Scheduled backup failed; aborting restart without touching running services."
            exit 1
        }

        Write-Step "Phase 2/2: restart downtime."
        $restartStart = Get-Date
        Stop-TrackedProcess -PidFile $AiPidFile -Label "AI engine"
        Stop-TrackedProcess -PidFile $BackendPidFile -Label "backend"
        Start-Backend
        Start-AiEngine
        $ready = Wait-Ready
        $downtime = (Get-Date) - $restartStart
        Write-Step "Restart downtime: $($downtime.TotalSeconds) seconds."
        if (-not $ready) {
            Write-Error "Restart did not reach ready+heartbeat within ${ReadyTimeoutSeconds}s. Investigate before relying on this instance."
            exit 1
        }
    }

    "Restore" {
        if (-not $BackupId) {
            Write-Error "-BackupId is required for -Action Restore."
            exit 1
        }

        Write-Step "Stopping services for offline restore..."
        Stop-TrackedProcess -PidFile $AiPidFile -Label "AI engine"
        Stop-TrackedProcess -PidFile $BackendPidFile -Label "backend"

        Write-Step "Running offline restore for backup $BackupId..."
        $restoreExit = Invoke-Maintenance @("restore", $BackupId)

        if ($restoreExit -ne 0) {
            Write-Error "Offline restore reported failure before touching the primary database. Restarting original services unchanged."
            Start-Backend
            Start-AiEngine
            Wait-Ready | Out-Null
            exit 1
        }

        Write-Step "Restore swapped the database. Starting services..."
        Start-Backend
        Start-AiEngine
        $ready = Wait-Ready

        if ($ready) {
            Write-Step "Restore verified healthy. Finalizing."
            Invoke-Maintenance @("restore", "--finalize", "completed") | Out-Null
            exit 0
        }

        Write-Error "Restored system failed to become healthy. Rolling back to the emergency pre-restore backup."
        Stop-TrackedProcess -PidFile $AiPidFile -Label "AI engine"
        Stop-TrackedProcess -PidFile $BackendPidFile -Label "backend"
        $rollbackExit = Invoke-Maintenance @("rollback")
        Start-Backend
        Start-AiEngine
        $rollbackReady = Wait-Ready
        if ($rollbackExit -ne 0 -or -not $rollbackReady) {
            Write-Error "ROLLBACK FAILED or the rolled-back system did not become healthy. Manual intervention required."
            exit 2
        }
        Write-Step "Rollback complete; original system restored."
        exit 1
    }

    "Archive" {
        $exitCode = Invoke-Maintenance @("archive")
        exit $exitCode
    }
}
