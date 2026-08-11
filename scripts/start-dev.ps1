<#
.SYNOPSIS
    Starts the ADAS dev stack: backend, frontend, camera simulation, AI engine.

.DESCRIPTION
    Replaces the four-terminal-plus-a-seed-script manual bring-up documented
    in README.md with one command. No switches at all starts the everyday
    case, -Backend -Frontend. Preflights the things that fail unhelpfully
    (.env, uv, pnpm/node_modules) before spawning anything, then follows the
    real demo-day bring-up order from be_audit/DEMO_TOPOLOGY.md §5: MediaMTX
    -> backend -> frontend -> AI engine. The engine discovers cameras from
    the backend's heartbeat response, so if it starts before the backend is
    up it just logs failures until the backend appears.

    Each requested process gets its own pwsh window (distinct title) via
    Start-Process, not `concurrently` — MediaMTX spawns a child ffmpeg per
    channel and needs its own Ctrl+C, and four processes interleaved in one
    terminal is unreadable. -NoNewWindow runs a single requested process in
    the current terminal instead.

.PARAMETER Backend
    Start the FastAPI backend (`uv run fastapi dev backend/app/main.py`).

.PARAMETER Frontend
    Start the Vite dev server (`cd frontend && pnpm dev`).

.PARAMETER Sim
    Start MediaMTX + its ffmpeg feeds by delegating to scripts/start-sim.ps1
    (reuses that script's ffmpeg/mediamtx/clips preflight rather than
    duplicating it here).

.PARAMETER Ai
    Start the AI engine (`uv run python ai_engine/main.py`). Needs
    `uv sync --extra ai` and an NVIDIA GPU for a usable frame rate; without
    one it still connects, which is fine for integration work but is not a
    detection platform.

.PARAMETER All
    Shorthand for -Backend -Frontend -Sim -Ai.

.PARAMETER Reseed
    Seed profile name, passed straight through to
    `backend/scripts/reseed_dev.py --profile <value>` — this script does not
    validate the profile itself, Python does. Runs BEFORE any process
    starts: reseed_dev.py deletes the SQLite file, which only works while
    nothing holds it open. If the reseed fails, nothing is started.

.PARAMETER NoNewWindow
    Run a single requested process in the current terminal instead of a new
    window. Errors out if more than one process is requested alongside it.

.EXAMPLE
    scripts\start-dev.ps1
    # Backend + frontend, the everyday case.

.EXAMPLE
    scripts\start-dev.ps1 -Sim -Ai
    # Adds MediaMTX and the AI engine on top of nothing else requested
    # explicitly -- only Sim and Ai start.

.EXAMPLE
    scripts\start-dev.ps1 -All

.EXAMPLE
    scripts\start-dev.ps1 -Reseed demo
    # Reseeds with the "demo" profile, then starts backend + frontend.

.EXAMPLE
    scripts\start-dev.ps1 -Backend -NoNewWindow
#>

param(
    [switch]$Backend,
    [switch]$Frontend,
    [switch]$Sim,
    [switch]$Ai,
    [switch]$All,
    [string]$Reseed,
    [switch]$NoNewWindow
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

function Write-Step($message) {
    Write-Host "[start-dev] $message" -ForegroundColor Cyan
}

# ---------------------------------------------------------------------------
# Resolve which components are requested
# ---------------------------------------------------------------------------

if ($All) {
    $Backend = $true
    $Frontend = $true
    $Sim = $true
    $Ai = $true
}

if (-not ($Backend -or $Frontend -or $Sim -or $Ai)) {
    # The everyday case: no switches at all.
    $Backend = $true
    $Frontend = $true
}

$requested = @()
if ($Sim) { $requested += "Sim" }
if ($Backend) { $requested += "Backend" }
if ($Frontend) { $requested += "Frontend" }
if ($Ai) { $requested += "Ai" }

if ($NoNewWindow -and $requested.Count -gt 1) {
    Write-Error "-NoNewWindow runs one process in the current terminal, but $($requested.Count) were requested ($($requested -join ', ')). Drop -NoNewWindow, or request a single component."
    exit 1
}

# ---------------------------------------------------------------------------
# Preflight
# ---------------------------------------------------------------------------

function Test-EnvFile {
    $envPath = Join-Path $RepoRoot ".env"
    if (Test-Path $envPath) {
        return
    }

    $examplePath = Join-Path $RepoRoot ".env.example"
    if (-not (Test-Path $examplePath)) {
        Write-Error ".env is missing and .env.example is not present to copy from. Create .env manually before continuing."
        exit 1
    }

    Write-Warning ".env not found at repo root."
    $answer = Read-Host "Copy .env.example to .env now? [Y/n]"
    if ($answer -eq "" -or $answer -match '^[Yy]') {
        Copy-Item -Path $examplePath -Destination $envPath
        Write-Step "Copied .env.example to .env."
        Write-Warning "SECRET_KEY, INTERNAL_API_KEY and DEFAULT_ADMIN_PASSWORD in the new .env are placeholders -- fine for local dev, but replace them before anything resembling a real deployment."
    }
    else {
        Write-Error "Cannot continue without .env. Copy .env.example to .env and fill in real values, then retry."
        exit 1
    }
}

function Test-Uv {
    if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
        Write-Error "uv not found on PATH. Install it: https://docs.astral.sh/uv/getting-started/installation/"
        exit 1
    }
}

function Test-PnpmAndFrontendDeps {
    if (-not (Get-Command pnpm -ErrorAction SilentlyContinue)) {
        Write-Error "pnpm not found on PATH. Install Node.js 22+ and pnpm, then run 'pnpm install' at the repo root."
        exit 1
    }
    $nodeModules = Join-Path $RepoRoot "frontend\node_modules"
    if (-not (Test-Path $nodeModules)) {
        Write-Error "frontend\node_modules not found. Run 'pnpm install' at the repo root (not inside frontend/) -- this is a pnpm workspace, and the root install is what activates the git hooks."
        exit 1
    }
}

if ($Backend -or $Ai -or $Reseed) {
    Test-EnvFile
    Test-Uv
}

if ($Frontend) {
    Test-PnpmAndFrontendDeps
}

if ($Ai) {
    Write-Warning "-Ai needs 'uv sync --extra ai' (heavy CUDA deps) and an NVIDIA GPU for a usable frame rate. It will still connect without a GPU -- fine for integration work -- but is not a detection platform in that mode."
}

# ---------------------------------------------------------------------------
# Reseed -- BEFORE anything starts. reseed_dev.py deletes the SQLite file,
# which only works while nothing holds it open.
# ---------------------------------------------------------------------------

if ($Reseed) {
    Write-Step "Reseeding dev DB with profile '$Reseed' before starting anything..."
    & uv run python backend/scripts/reseed_dev.py --profile $Reseed
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Reseed failed (exit $LASTEXITCODE). Not starting any process against a possibly half-reset DB."
        exit 1
    }
    Write-Step "Reseed complete."
}

# ---------------------------------------------------------------------------
# Spawn, in be_audit/DEMO_TOPOLOGY.md §5's bring-up order: MediaMTX -> backend
# -> frontend -> AI engine.
# ---------------------------------------------------------------------------

# Prefer PowerShell 7 (pwsh) for the spawned windows, but a stock Windows box
# only ships Windows PowerShell 5.1 with no pwsh on PATH. Nothing in these
# scripts needs PS7-only syntax, so fall back to powershell.exe rather than
# hard-failing every spawn with "the system cannot find the file specified."
$script:ShellExe = if (Get-Command pwsh -ErrorAction SilentlyContinue) { "pwsh" } else { "powershell" }

function Start-Component([string]$Title, [string]$Command, [bool]$Foreground) {
    if ($Foreground) {
        Write-Step "Running $Title in this terminal (Ctrl+C to stop)..."
        Invoke-Expression $Command
        return
    }
    Write-Step "Starting $Title in a new window ($script:ShellExe)..."
    $wrapped = "`$Host.UI.RawUI.WindowTitle = '$Title'; $Command"
    # -EncodedCommand (Base64 UTF-16LE), not -Command with a raw string: this
    # repo can live under a path with spaces, and $Command already contains
    # its own embedded double quotes (e.g. the frontend's `Set-Location
    # "<repo>\frontend"`). Start-Process's -ArgumentList quoting does not
    # nest reliably through that combination -- it silently truncates the
    # path at the first space, e.g. `Set-Location` erroring on a stray path
    # fragment. Encoding sidesteps quoting entirely.
    $encoded = [Convert]::ToBase64String([System.Text.Encoding]::Unicode.GetBytes($wrapped))
    Start-Process -FilePath $script:ShellExe -ArgumentList @('-NoExit', '-EncodedCommand', $encoded) -WorkingDirectory $RepoRoot | Out-Null
}

$foreground = $NoNewWindow.IsPresent

if ($Sim) {
    $cmd = "& `"$RepoRoot\scripts\start-sim.ps1`""
    Start-Component -Title "ADAS - Sim (MediaMTX)" -Command $cmd -Foreground $foreground
}

if ($Backend) {
    $cmd = "uv run fastapi dev backend/app/main.py"
    Start-Component -Title "ADAS - Backend" -Command $cmd -Foreground $foreground
}

if ($Frontend) {
    $cmd = "Set-Location `"$RepoRoot\frontend`"; pnpm dev"
    Start-Component -Title "ADAS - Frontend" -Command $cmd -Foreground $foreground
}

if ($Ai) {
    $cmd = "uv run python ai_engine/main.py"
    Start-Component -Title "ADAS - AI Engine" -Command $cmd -Foreground $foreground
}

Write-Step "Requested: $($requested -join ', '). Use scripts\stop-dev.ps1 to tear down."
