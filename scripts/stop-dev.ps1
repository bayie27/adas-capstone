<#
.SYNOPSIS
    Stops the ADAS dev stack started by scripts\start-dev.ps1.

.DESCRIPTION
    Resolves each process by the port it listens on, NOT by the wrapper
    process name or a stored PID. `uv run fastapi dev ...` and
    `uv run python ai_engine/main.py` do not exec-replace themselves on
    Windows -- uv stays alive as a parent and spawns the real interpreter as
    a child. Killing the `uv` PID leaves the real server bound to its port.

    Backend  -> whatever is LISTENing on 8000
    Frontend -> whatever is LISTENing on 5173 (Vite)
    Sim      -> whatever is LISTENing on 8554 (MediaMTX RTSP), tree-killed so
                its child ffmpeg processes (one per channel, spawned by
                runOnInit, which don't exit on their own) go down with it.
    Ai       -> the AI engine binds no port at all (it's an RTSP client, not
                a server), so it's resolved by matching python.exe command
                lines for ai_engine/main.py instead.

    Takes the same switches as start-dev.ps1. No switches at all stops
    everything -- attempting to stop a process that isn't running is not an
    error, so "stop everything" is the safe default when you don't remember
    exactly what you started.

.PARAMETER Backend
.PARAMETER Frontend
.PARAMETER Sim
.PARAMETER Ai
.PARAMETER All
    Explicit synonym for "no switches" -- stop everything.

.EXAMPLE
    scripts\stop-dev.ps1
    # Stops backend, frontend, sim and AI engine -- whichever are running.

.EXAMPLE
    scripts\stop-dev.ps1 -Backend
    # Stops only the backend.
#>

param(
    [switch]$Backend,
    [switch]$Frontend,
    [switch]$Sim,
    [switch]$Ai,
    [switch]$All
)

$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

function Write-Step($message) {
    Write-Host "[stop-dev] $message" -ForegroundColor Cyan
}

if ($All -or -not ($Backend -or $Frontend -or $Sim -or $Ai)) {
    $Backend = $true
    $Frontend = $true
    $Sim = $true
    $Ai = $true
}

$script:UsedNetstatFallback = $false

function Get-ListeningProcessId([int]$Port) {
    if (Get-Command Get-NetTCPConnection -ErrorAction SilentlyContinue) {
        $conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
        if ($conn) {
            return ($conn | Select-Object -First 1 -ExpandProperty OwningProcess)
        }
        return $null
    }

    # Fallback for a machine without the NetTCPIP module.
    $script:UsedNetstatFallback = $true
    $lines = netstat -ano | Select-String -Pattern "\s+\S*:$Port\s+.*LISTENING"
    if ($lines) {
        $fields = ($lines[0].ToString().Trim() -split '\s+')
        return [int]$fields[-1]
    }
    return $null
}

function Stop-ByPort([int]$Port, [string]$Label) {
    $procId = Get-ListeningProcessId -Port $Port
    if (-not $procId) {
        Write-Step "$Label`: nothing listening on port $Port. Not running."
        return
    }
    Write-Step "Stopping $Label (PID $procId, port $Port)..."
    # taskkill /T (tree-kill), not Stop-Process: the PID bound to the port
    # may itself have spawned children (MediaMTX's per-channel ffmpeg), and
    # even where it hasn't, /T is harmless.
    & taskkill /PID $procId /T /F 2>&1 | Out-Null

    # A single check shortly after taskkill isn't enough to rule out a
    # reload supervisor (uvicorn's WatchFiles loop under `fastapi dev`)
    # respawning a worker after an unexpected child death -- that would
    # look clean at 300ms and rebind moments later. Re-check once more
    # after a longer pause before declaring the port free.
    Start-Sleep -Milliseconds 300
    $stillBound = [bool](Get-ListeningProcessId -Port $Port)
    if (-not $stillBound) {
        Start-Sleep -Milliseconds 700
        $stillBound = [bool](Get-ListeningProcessId -Port $Port)
    }

    if ($stillBound) {
        Write-Warning "$Label`: port $Port is still bound after stopping PID $procId. Investigate manually."
    }
    else {
        Write-Step "$Label stopped."
    }
}

function Stop-AiEngine {
    $procs = Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -match 'ai_engine[\\/]main\.py' }
    if (-not $procs) {
        Write-Step "AI engine: no matching python.exe process found. Not running."
        return
    }
    foreach ($p in $procs) {
        Write-Step "Stopping AI engine (PID $($p.ProcessId))..."
        & taskkill /PID $p.ProcessId /T /F 2>&1 | Out-Null
    }
    Write-Step "AI engine stopped."
}

# Reverse of the start-up order: AI engine -> frontend -> backend -> sim.
if ($Ai) { Stop-AiEngine }
if ($Frontend) { Stop-ByPort -Port 5173 -Label "Frontend" }
if ($Backend) { Stop-ByPort -Port 8000 -Label "Backend" }
if ($Sim) { Stop-ByPort -Port 8554 -Label "Sim (MediaMTX)" }

if ($script:UsedNetstatFallback) {
    Write-Step "Get-NetTCPConnection was not available on this machine; fell back to parsing netstat -ano."
}
