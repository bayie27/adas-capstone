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

    Every invocation is captured under -LogDir (default var\log\):
    Start-Transcript/Stop-Transcript records the whole run, and the
    backend/AI-engine child processes are launched with
    -RedirectStandardOutput/-RedirectStandardError instead of the old
    -WindowStyle Minimized console that vanished with nothing recoverable
    once closed (be_audit/00_FINDINGS.md F22 — this is what blocked the
    2026-08-11 restart drill's model-load-time measurement). A -Action
    Restart run also appends one JSON line to
    var\log\maintenance-runs.jsonl, which GET /api/system/maintenance/status
    reads for its last_restart field.

.PARAMETER Action
    Start | Stop | Backup | Restart | Restore | Archive

.PARAMETER BackupId
    Required for -Action Restore — the backup id to restore (see
    `uv run python -m app.maintenance list`).

.PARAMETER LogDir
    Where transcripts, component stdout/stderr logs, and
    maintenance-runs.jsonl are written. Relative paths resolve against the
    repo root. Created if absent.

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

    [int]$ReadyTimeoutSeconds = 60,

    [string]$LogDir = "var\log"
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

# Live-drilled finding (P18 Step 8): ai_engine/main.py's startup output is
# plain print() with no flush=True, and Python block-buffers stdout/stderr
# whenever they're not a real console (exactly what -RedirectStandardOutput/
# -RedirectStandardError makes them) -- the model-load line sat in an
# in-process buffer and never reached the log file while the process kept
# running, defeating the point of Step 5's persistent logs for the one
# component F22 was actually about. ai_engine/ itself is off-limits to
# edit, so this is fixed here instead: PYTHONUNBUFFERED forces Python to
# flush every line regardless of what the target script does. Child
# processes started via Start-Process below inherit this from the current
# process environment.
$env:PYTHONUNBUFFERED = "1"

# Live-drilled finding (P18 Step 8, unattended-trigger drill): the very
# first real 3 AM-equivalent unattended restart crashed the backend before
# it ever became ready. -RedirectStandardOutput/-RedirectStandardError
# detach stdout/stderr from a real console, so Python falls back to the
# process's inherited console codepage for encoding -- cp1252 under the
# Windows Scheduled Task's launch context (which differs from whatever an
# already-open interactive terminal may have customized), not UTF-8. FastAPI
# CLI's startup banner ("Starting production server \U0001f680") then raises
# UnicodeEncodeError trying to print that emoji, and the process dies before
# reaching /healthz/ready -- silent in a manual interactive run, which is
# exactly why this only surfaced on the real Task Scheduler firing and not
# in any of this pack's earlier manual drills. PYTHONUTF8 forces UTF-8 mode
# regardless of the inherited codepage.
$env:PYTHONUTF8 = "1"

$RunDir = Join-Path $RepoRoot "var\run"
New-Item -ItemType Directory -Force -Path $RunDir | Out-Null
$BackendPidFile = Join-Path $RunDir "backend.pid"
$AiPidFile = Join-Path $RunDir "ai_engine.pid"

$LogDirFull = if ([System.IO.Path]::IsPathRooted($LogDir)) { $LogDir } else { Join-Path $RepoRoot $LogDir }
New-Item -ItemType Directory -Force -Path $LogDirFull | Out-Null

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
        $exitCode = $LASTEXITCODE

        # The CLI's success/failure paths both print one JSON object to
        # stdout (see app/maintenance/cli.py) — parsed here so callers can
        # pull structured fields (backup_id, timings, heartbeat_confirmed,
        # ...) for the maintenance-runs.jsonl record, on top of the plain
        # exit-code check every caller already did. A parse failure just
        # means no structured data was available (e.g. an ERROR: line went
        # to stderr, which this capture never sees) — not a script error.
        $data = $null
        $jsonText = ($output -join "`n").Trim()
        if ($jsonText) {
            try {
                $data = $jsonText | ConvertFrom-Json
            }
            catch {
                $data = $null
            }
        }

        return [PSCustomObject]@{
            ExitCode = $exitCode
            Data     = $data
        }
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
    $timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $stdout = Join-Path $LogDirFull "backend-$timestamp.log"
    $stderr = Join-Path $LogDirFull "backend-$timestamp.err.log"
    # -WindowStyle Hidden, not Minimized: Start-Process's
    # -RedirectStandardOutput/-RedirectStandardError only reliably applies
    # with a hidden window — the two redirect targets must also be distinct
    # files (backend's own .log vs .err.log here), or Start-Process throws.
    $proc = Start-Process -FilePath "uv" `
        -ArgumentList "run", "fastapi", "run", "backend/app/main.py" `
        -WorkingDirectory $RepoRoot -PassThru -WindowStyle Hidden `
        -RedirectStandardOutput $stdout -RedirectStandardError $stderr
    Set-Content -Path $BackendPidFile -Value $proc.Id
    Write-Step "Backend started (PID $($proc.Id)). Logs: $stdout / $stderr"
}

function Start-AiEngine {
    Write-Step "Starting AI engine..."
    $timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $stdout = Join-Path $LogDirFull "ai_engine-$timestamp.log"
    $stderr = Join-Path $LogDirFull "ai_engine-$timestamp.err.log"
    $proc = Start-Process -FilePath "uv" `
        -ArgumentList "run", "python", "ai_engine/main.py" `
        -WorkingDirectory $RepoRoot -PassThru -WindowStyle Hidden `
        -RedirectStandardOutput $stdout -RedirectStandardError $stderr
    Set-Content -Path $AiPidFile -Value $proc.Id
    Write-Step "AI engine started (PID $($proc.Id)). Logs: $stdout / $stderr"
}

function Wait-Ready {
    Write-Step "Waiting for /healthz/ready and a fresh AI heartbeat (timeout ${ReadyTimeoutSeconds}s)..."
    $result = Invoke-Maintenance @("restart", "--phase", "wait", "--timeout", $ReadyTimeoutSeconds)
    $heartbeatConfirmed = $false
    if ($result.Data -and $null -ne $result.Data.heartbeat_confirmed) {
        $heartbeatConfirmed = [bool]$result.Data.heartbeat_confirmed
    }
    return [PSCustomObject]@{
        Ready              = ($result.ExitCode -eq 0)
        HeartbeatConfirmed = $heartbeatConfirmed
    }
}

function Write-MaintenanceRunRecord([hashtable]$Record) {
    $path = Join-Path $LogDirFull "maintenance-runs.jsonl"
    $json = [PSCustomObject]$Record | ConvertTo-Json -Compress
    Add-Content -Path $path -Value $json
    Limit-MaintenanceRunLog -Path $path
}

function Limit-MaintenanceRunLog([string]$Path) {
    # Prune to the last 30 runs / 30 days so this cannot grow unbounded on
    # a 24/7 box.
    if (-not (Test-Path $Path)) {
        return
    }
    $cutoff = (Get-Date).ToUniversalTime().AddDays(-30)
    $kept = @()
    foreach ($line in (Get-Content $Path)) {
        if (-not $line.Trim()) {
            continue
        }
        try {
            $entry = $line | ConvertFrom-Json
            # ConvertFrom-Json auto-converts an ISO 8601 string like
            # started_at into a [datetime] on PowerShell 7+, but leaves it
            # a plain string on Windows PowerShell 5.1 — handle both rather
            # than assuming one.
            $entryTime = if ($entry.started_at -is [datetime]) {
                $entry.started_at
            }
            else {
                [datetime]::Parse(
                    [string]$entry.started_at, $null,
                    [System.Globalization.DateTimeStyles]::RoundtripKind
                )
            }
            if ($entryTime -ge $cutoff) {
                $kept += $line
            }
        }
        catch {
            # Corrupt/unparseable line — drop it rather than let it wedge
            # pruning forever.
        }
    }
    if ($kept.Count -gt 30) {
        $kept = $kept[($kept.Count - 30)..($kept.Count - 1)]
    }
    Set-Content -Path $Path -Value $kept
}

function Invoke-RestartAction {
    # A dedicated function (rather than inline in the switch statement)
    # purely so a single try/finally can guarantee the run record is
    # written on every exit path, including an unhandled exception —
    # "a nightly run that crashed is the case this file exists for." No
    # early `return` inside the try: PowerShell can't recover a
    # short-circuited return value inside its own finally block, so every
    # branch below assigns $exitCode and falls through instead.
    $startedAt = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
    $backupId = $null
    $backupDurationS = $null
    $downtimeS = $null
    $ready = $false
    $heartbeatConfirmed = $false
    $exitCode = 1

    try {
        # D-011 / Step 7: backup first (online, services still up), timed
        # separately from restart downtime.
        Write-Step "Phase 1/2: online backup."
        $backupResult = Invoke-Maintenance @("backup", "--origin", "scheduled")
        if ($backupResult.Data) {
            $backupId = $backupResult.Data.backup_id
            $backupDurationS = $backupResult.Data.duration_seconds
        }

        if ($backupResult.ExitCode -eq 0) {
            Write-Step "Phase 2/2: restart downtime."
            $restartStart = Get-Date
            Stop-TrackedProcess -PidFile $AiPidFile -Label "AI engine"
            Stop-TrackedProcess -PidFile $BackendPidFile -Label "backend"
            Start-Backend
            Start-AiEngine
            $waitResult = Wait-Ready
            $downtimeS = ((Get-Date) - $restartStart).TotalSeconds
            Write-Step "Restart downtime: $downtimeS seconds."
            $ready = $waitResult.Ready
            $heartbeatConfirmed = $waitResult.HeartbeatConfirmed

            if ($ready) {
                $exitCode = 0
            }
            else {
                Write-Error "Restart did not reach ready+heartbeat within ${ReadyTimeoutSeconds}s. Investigate before relying on this instance." -ErrorAction Continue
                $exitCode = 1
            }
        }
        else {
            Write-Error "Scheduled backup failed; aborting restart without touching running services." -ErrorAction Continue
            $exitCode = 1
        }
    }
    finally {
        Write-MaintenanceRunRecord -Record @{
            started_at          = $startedAt
            action              = "Restart"
            backup_id           = $backupId
            backup_duration_s   = $backupDurationS
            downtime_s          = $downtimeS
            ready               = $ready
            heartbeat_confirmed = $heartbeatConfirmed
            exit_code           = $exitCode
        }
    }

    return $exitCode
}

$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$transcriptPath = Join-Path $LogDirFull "maintenance-$Action-$timestamp.transcript.log"
Start-Transcript -Path $transcriptPath | Out-Null

try {
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
            $result = Invoke-Maintenance @("backup", "--origin", "manual")
            exit $result.ExitCode
        }

        "Restart" {
            exit (Invoke-RestartAction)
        }

        "Restore" {
            if (-not $BackupId) {
                Write-Error "-BackupId is required for -Action Restore." -ErrorAction Continue
                exit 1
            }

            Write-Step "Stopping services for offline restore..."
            Stop-TrackedProcess -PidFile $AiPidFile -Label "AI engine"
            Stop-TrackedProcess -PidFile $BackendPidFile -Label "backend"

            Write-Step "Running offline restore for backup $BackupId..."
            $restoreResult = Invoke-Maintenance @("restore", $BackupId)

            if ($restoreResult.ExitCode -ne 0) {
                Write-Error "Offline restore reported failure before touching the primary database. Restarting original services unchanged." -ErrorAction Continue
                Start-Backend
                Start-AiEngine
                Wait-Ready | Out-Null
                exit 1
            }

            Write-Step "Restore swapped the database. Starting services..."
            Start-Backend
            Start-AiEngine
            $waitResult = Wait-Ready

            if ($waitResult.Ready) {
                Write-Step "Restore verified healthy. Finalizing."
                Invoke-Maintenance @("restore", "--finalize", "completed") | Out-Null
                exit 0
            }

            Write-Error "Restored system failed to become healthy. Rolling back to the emergency pre-restore backup." -ErrorAction Continue
            Stop-TrackedProcess -PidFile $AiPidFile -Label "AI engine"
            Stop-TrackedProcess -PidFile $BackendPidFile -Label "backend"
            $rollbackResult = Invoke-Maintenance @("rollback")
            Start-Backend
            Start-AiEngine
            $rollbackWaitResult = Wait-Ready
            if ($rollbackResult.ExitCode -ne 0 -or -not $rollbackWaitResult.Ready) {
                Write-Error "ROLLBACK FAILED or the rolled-back system did not become healthy. Manual intervention required." -ErrorAction Continue
                exit 2
            }
            Write-Step "Rollback complete; original system restored."
            exit 1
        }

        "Archive" {
            $result = Invoke-Maintenance @("archive")
            exit $result.ExitCode
        }
    }
}
finally {
    Stop-Transcript | Out-Null
}
