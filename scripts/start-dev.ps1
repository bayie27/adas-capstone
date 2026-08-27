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

    -Lan swaps every launch command for its TLS equivalent so a second
    machine can reach the dashboard over HTTPS/WSS (LAN_SETUP.md step 6).
    It covers only the process side; the OS-level work around it — static
    IPs, the Private connection profile, firewall rules, the client's hosts
    entry and certificate trust — is manual and stays in LAN_SETUP.md,
    because none of it is safe to do implicitly on someone's machine.

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

.PARAMETER Lan
    LAN demo profile: start every component over real TLS, bound to all
    interfaces, so a second machine on the network can reach the dashboard
    at https://<host>:5173. This is the profile LAN_SETUP.md step 6
    documents; the manual four-window equivalent is still written out there
    for reference.

    Changes each component's launch command rather than which components
    run -- but because the LAN profile exists for the full demo, -Lan with
    NO component switches starts all four rather than the everyday
    backend+frontend pair. Explicit switches are still honoured
    (`-Lan -Backend` starts only the backend, over TLS).

    Requires the certificate pair in -CertDir and a .env carrying the LAN
    keys; both are preflighted, and both fail SILENTLY at runtime if wrong,
    which is why they are checked here rather than left to discover.

.PARAMETER CertDir
    Directory holding adas-cert.pem / adas-key.pem for -Lan. Defaults to
    `certs` at the repo root. Ignored without -Lan.

.PARAMETER MediaMtxDir
    Prepended to PATH for the -Sim window only. MediaMTX ships as a bare
    binary that most people never add to PATH permanently, and
    start-sim.ps1 hard-fails without it. Defaults to the ADAS_MEDIAMTX_DIR
    environment variable, so you can set that once instead of passing it.

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

.EXAMPLE
    scripts\start-dev.ps1 -Lan
    # The whole stack over HTTPS/WSS for a two-machine demo. See LAN_SETUP.md
    # -- the OS-level steps (static IP, Private profile, firewall rules,
    # client hosts entry, certificate trust) are NOT done by this script.
#>

param(
    [switch]$Backend,
    [switch]$Frontend,
    [switch]$Sim,
    [switch]$Ai,
    [switch]$All,
    [switch]$Lan,
    [string]$CertDir = "certs",
    [string]$MediaMtxDir = $env:ADAS_MEDIAMTX_DIR,
    [string]$Reseed,
    [switch]$NoNewWindow
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot
Import-Module (Join-Path $RepoRoot "scripts\lib\adas-lifecycle.psm1") -Force

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
    if ($Lan) {
        # The LAN profile exists for the full two-machine demo, so a bare
        # -Lan means all four. Everyday dev never wants TLS, so this
        # doesn't change the no-switches default below.
        $Backend = $true
        $Frontend = $true
        $Sim = $true
        $Ai = $true
    }
    else {
        # The everyday case: no switches at all.
        $Backend = $true
        $Frontend = $true
    }
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

# -Lan's two hard requirements, both of which fail SILENTLY at runtime if
# wrong: no certificate means uvicorn won't start at all, and a .env without
# the LAN keys means the client gets a 403 ORIGIN_REJECTED on every write and
# a WebSocket that closes the instant it opens -- with nothing in either log
# naming the cause. Checked here so the failure is a sentence, not an evening.
function Test-LanProfile {
    $script:CertDirFull = if ([System.IO.Path]::IsPathRooted($CertDir)) { $CertDir } else { Join-Path $RepoRoot $CertDir }
    $script:CertPath = Join-Path $script:CertDirFull "adas-cert.pem"
    $script:KeyPath = Join-Path $script:CertDirFull "adas-key.pem"

    foreach ($f in @($script:CertPath, $script:KeyPath)) {
        if (-not (Test-Path $f)) {
            # Write-Host, not Write-Error, for the body: PowerShell's error
            # formatter reflows a multi-line message into one wrapped
            # paragraph, which would destroy a command meant to be copied.
            Write-Host ""
            Write-Host "Generate one from Git Bash at the repo root (LAN_SETUP.md step 3b):" -ForegroundColor Yellow
            Write-Host ""
            Write-Host '  mkdir -p certs && MSYS_NO_PATHCONV=1 openssl req -x509 -newkey rsa:2048 -sha256 -days 825 -nodes \' -ForegroundColor Yellow
            Write-Host '    -keyout certs/adas-key.pem -out certs/adas-cert.pem -subj "/CN=adas.local" \' -ForegroundColor Yellow
            Write-Host '    -addext "subjectAltName=DNS:adas.local,DNS:localhost,IP:192.168.50.1,IP:127.0.0.1"' -ForegroundColor Yellow
            Write-Host ""
            Write-Error "-Lan needs a certificate pair and $f is missing. See the command above."
            exit 1
        }
    }

    # Expiry and SANs are advisory: an expired or wrongly-named certificate
    # still starts the server, it just fails in the client's browser. Report
    # rather than block -- and degrade quietly on Windows PowerShell 5.1,
    # whose .NET lacks CreateFromPemFile.
    try {
        # CreateFromPem, not CreateFromPemFile: the latter expects the private
        # key in the same file and throws on a certificate-only PEM.
        $cert = [System.Security.Cryptography.X509Certificates.X509Certificate2]::CreateFromPem((Get-Content $script:CertPath -Raw))
        $daysLeft = [int]($cert.NotAfter - (Get-Date)).TotalDays
        if ($daysLeft -lt 0) {
            Write-Warning "Certificate EXPIRED $([Math]::Abs($daysLeft)) days ago ($($cert.NotAfter.ToString('yyyy-MM-dd'))). Every client will refuse it. Regenerate -- see LAN_SETUP.md step 3b."
        }
        elseif ($daysLeft -lt 30) {
            Write-Warning "Certificate expires in $daysLeft days ($($cert.NotAfter.ToString('yyyy-MM-dd')))."
        }
        $san = $cert.Extensions | Where-Object { $_.Oid.Value -eq "2.5.29.17" }
        if ($san) {
            $names = ($san.Format($false) -replace 'DNS Name=', 'DNS:' -replace 'IP Address=', 'IP:')
            Write-Step "Certificate: expires $($cert.NotAfter.ToString('yyyy-MM-dd')), SANs $names"
            if ($names -notmatch 'DNS:') {
                Write-Warning "This certificate has no DNS name in its SAN list, only IPs. It will work, but an IP-pinned certificate breaks the moment the address changes -- see LAN_SETUP.md section 2."
            }
        }
        else {
            Write-Warning "Certificate has no Subject Alternative Name extension. Every current browser rejects CN-only certificates outright. Regenerate -- see LAN_SETUP.md step 3b."
        }
    }
    catch {
        Write-Step "Certificate found (not parsed -- $($_.Exception.GetType().Name)). Verify manually: openssl x509 -in $($script:CertPath) -noout -text"
    }

    # .env: only the two LAN keys are read, and neither is a secret.
    $envPath = Join-Path $RepoRoot ".env"
    $envLines = Get-Content $envPath -ErrorAction SilentlyContinue
    $secure = $envLines | Where-Object { $_ -match '^\s*SESSION_COOKIE_SECURE\s*=' } | Select-Object -Last 1
    $origins = $envLines | Where-Object { $_ -match '^\s*CORS_ORIGINS\s*=' } | Select-Object -Last 1

    $problems = @()
    if ($secure -and $secure -notmatch '=\s*(true|1)\s*$') {
        $problems += "SESSION_COOKIE_SECURE is set to something other than true. Browsers grant the Secure-cookie exemption to localhost ONLY -- over the LAN the cookie is dropped, login returns 200, and every later request is a 401 that looks exactly like an auth bug."
    }
    if (-not $origins) {
        $problems += "CORS_ORIGINS is absent, so the built-in default (http://localhost:5173) applies and no https:// origin is allowed."
    }
    elseif ($origins -notmatch 'https://') {
        $problems += "CORS_ORIGINS contains no https:// origin."
    }

    if ($problems.Count -gt 0) {
        Write-Host ""
        Write-Host ".env is not ready for the LAN profile:" -ForegroundColor Yellow
        foreach ($p in $problems) { Write-Host "  - $p" -ForegroundColor Yellow }
        Write-Host ""
        Write-Host "CORS_ORIGINS gates three independent things -- CORSMiddleware, the origin-validation" -ForegroundColor DarkGray
        Write-Host "middleware (403 ORIGIN_REJECTED on every write), and the WebSocket handshake -- so a" -ForegroundColor DarkGray
        Write-Host "mismatch breaks all three at once. Origins are matched exactly: scheme, host and port." -ForegroundColor DarkGray
        Write-Host ""
        Write-Host "Add to .env at the repo root (LAN_SETUP.md step 5), adjusting the address to yours:" -ForegroundColor Yellow
        Write-Host ""
        Write-Host "  SESSION_COOKIE_SECURE=true" -ForegroundColor Yellow
        Write-Host "  CORS_ORIGINS=https://adas.local:5173,https://192.168.50.1:5173,https://localhost:5173" -ForegroundColor Yellow
        Write-Host ""
        Write-Error ".env is missing the LAN profile keys. See above."
        exit 1
    }
}

# Advisory only -- never blocks. These are OS-level steps LAN_SETUP.md step 2
# owns, but they are the single most common cause of a demo that looks broken
# for no reason, and they are invisible from inside the application.
function Show-LanReachability {
    $rules = @(Get-NetFirewallRule -DisplayName "ADAS*" -ErrorAction SilentlyContinue | Where-Object { $_.Enabled -eq $true -and $_.Direction -eq "Inbound" })
    if ($rules.Count -eq 0) {
        Write-Warning "No enabled inbound 'ADAS*' firewall rules found. Unless something else opens 8000 and 5173, a client will hang with no error at either end. See LAN_SETUP.md step 2."
    }

    $profiles = @(Get-NetConnectionProfile -ErrorAction SilentlyContinue)
    foreach ($p in $profiles) {
        $ips = @(Get-NetIPAddress -InterfaceIndex $p.InterfaceIndex -AddressFamily IPv4 -ErrorAction SilentlyContinue |
                Where-Object { $_.IPAddress -notlike "169.254.*" } | Select-Object -ExpandProperty IPAddress)
        foreach ($ip in $ips) {
            $note = if ($p.NetworkCategory -eq "Public") { "  <-- Public profile: inbound is BLOCKED on this interface" } else { "" }
            Write-Host "    https://${ip}:5173  ($($p.InterfaceAlias), $($p.NetworkCategory))$note" -ForegroundColor DarkGray
        }
    }
}

if ($Lan) {
    Test-EnvFile
    Test-Uv
    Test-LanProfile
}

if ($Backend -or $Ai -or $Reseed) {
    Test-EnvFile
    Test-Uv
}

if ($Frontend) {
    Test-PnpmAndFrontendDeps
}

if ($Ai) {
    Write-Warning "-Ai needs 'uv sync --extra ai' (heavy CUDA deps) and an NVIDIA GPU for a usable frame rate. It will still connect without a GPU -- fine for integration work -- but is not a detection platform in that mode. The weights (ai_engine\epoch50.pt) are committed and loaded directly with no fallback -- a missing epoch50.pt is a hard startup failure, not a degradation. ai_engine\machine_profile.json is machine-specific and gitignored; its absence is NOT an error -- the engine falls back to one camera and says so on startup. Run 'uv run python ai_engine/capacity.py' to generate it."
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

# The restore coordinator is available only when both services are launched
# through the tracked, command-tree-safe helper.  Partial/foreground starts
# deliberately remain uncontrolled so the dashboard fails closed.
$managedBackendAi = $Backend -and $Ai -and -not $NoNewWindow
$launchProfile = $null
if ($managedBackendAi) {
    $profileCertDir = if ($Lan) { $script:CertDirFull } else { Join-Path $RepoRoot $CertDir }
    $launchProfile = New-AdasLaunchProfile -Lan ([bool]$Lan) -CertDir $profileCertDir
}

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
    if ($MediaMtxDir) {
        # start-sim.ps1 hard-fails unless mediamtx is on PATH, and MediaMTX
        # ships as a bare binary most people never install permanently.
        $cmd = "`$env:PATH = `"$MediaMtxDir;`$env:PATH`"; $cmd"
    }
    Start-Component -Title "ADAS - Sim (MediaMTX)" -Command $cmd -Foreground $foreground
}

if ($Backend) {
    # `uv run fastapi dev` has been seen to crash on Windows with a cp1252
    # codec error when launched from a Bash-flavoured shell -- set
    # unconditionally rather than reactively, since there's no reliable way
    # to detect the parent shell's encoding before the crash happens.
    if ($managedBackendAi) {
        Start-AdasManagedComponent -RepoRoot $RepoRoot -Component backend -Profile $launchProfile -LogDirectory (Join-Path $RepoRoot "var\log") -ShellExecutable $script:ShellExe | Out-Null
    }
    elseif ($Lan) {
        # The FastAPI CLI exposes no SSL flags at all, so TLS means driving
        # uvicorn directly. --app-dir backend replaces what the CLI normally
        # does for sys.path. The two --ws-ping-* flags pin a keepalive that
        # is otherwise an unstated library default; this is the only launch
        # path in the repo that can pin it (be_audit/00_FINDINGS.md F6).
        $cmd = "`$env:PYTHONUTF8 = '1'; uv run uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000 --ssl-keyfile `"$script:KeyPath`" --ssl-certfile `"$script:CertPath`" --ws-ping-interval 20 --ws-ping-timeout 20"
    }
    else {
        $cmd = "`$env:PYTHONUTF8 = '1'; uv run fastapi dev backend/app/main.py"
    }
    Start-Component -Title "ADAS - Backend" -Command $cmd -Foreground $foreground
}

if ($Frontend) {
    if ($Lan) {
        # vite.config.ts's server block is gated on this variable being set,
        # so plain `pnpm dev`, `pnpm build` and Playwright stay untouched.
        $cmd = "Set-Location `"$RepoRoot\frontend`"; `$env:ADAS_TLS_CERT_DIR = `"$script:CertDirFull`"; pnpm dev"
    }
    else {
        $cmd = "Set-Location `"$RepoRoot\frontend`"; pnpm dev"
    }
    Start-Component -Title "ADAS - Frontend" -Command $cmd -Foreground $foreground
}

if ($Ai) {
    if ($managedBackendAi) {
        Start-AdasManagedComponent -RepoRoot $RepoRoot -Component ai_engine -Profile $launchProfile -LogDirectory (Join-Path $RepoRoot "var\log") -ShellExecutable $script:ShellExe | Out-Null
    }
    elseif ($Lan) {
        # ai_engine/backend_client.py uses `requests`, which validates against
        # the certifi bundle and ignores the Windows certificate store -- so
        # trusting the cert in Trusted Root on this machine does nothing for
        # it. Without REQUESTS_CA_BUNDLE every heartbeat and every alert fails
        # TLS verification against our own backend.
        $cmd = "`$env:AI_BACKEND_BASE_URL = 'https://127.0.0.1:8000'; `$env:REQUESTS_CA_BUNDLE = `"$script:CertPath`"; uv run python ai_engine/main.py"
    }
    else {
        $cmd = "uv run python ai_engine/main.py"
    }
    Start-Component -Title "ADAS - AI Engine" -Command $cmd -Foreground $foreground
}

if ($managedBackendAi) {
    Write-AdasLaunchProfile -RepoRoot $RepoRoot -Profile $launchProfile
    $backupDirectory = Get-AdasBackupDirectory -RepoRoot $RepoRoot
    Start-AdasRestoreCoordinator -RepoRoot $RepoRoot -BackupDirectory $backupDirectory -LogDirectory (Join-Path $RepoRoot "var\log") | Out-Null
    Write-Step "Restore coordinator started for the full managed backend + AI profile."
}

Write-Step "Requested: $($requested -join ', '). Use scripts\stop-dev.ps1 to tear down."

if ($Lan) {
    Write-Step "LAN profile: TLS on, bound to all interfaces. Reachable dashboard origins --"
    Show-LanReachability
    Write-Step "Whichever origin a client browses MUST also be in CORS_ORIGINS, and the client must trust certs\adas-cert.pem (Trusted Root). See LAN_SETUP.md steps 3c-5 and 7."
}
