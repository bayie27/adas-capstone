<#
.SYNOPSIS
    Starts the MediaMTX camera simulation (mediamtx.yml) from the repo root.

.DESCRIPTION
    Preflights the two external binaries this depends on (ffmpeg, mediamtx)
    and every local media input referenced by mediamtx.yml, then execs
    `mediamtx mediamtx.yml`. Ctrl+C stops MediaMTX and its child ffmpeg
    processes together. The YAML is the source of truth: change its runOnInit
    commands to swap clips or change the number of channels without editing
    this script.

.PARAMETER MediaMtxDir
    Optional directory containing mediamtx.exe. If omitted, an existing PATH
    entry is used; otherwise the repository and its parent are searched for a
    repo-local or extracted MediaMTX release.
#>

param(
    [string]$MediaMtxDir = $env:ADAS_MEDIAMTX_DIR
)

$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot
Import-Module (Join-Path $RepoRoot "scripts\lib\adas-lifecycle.psm1") -Force

if ($MediaMtxDir) {
    $env:PATH = "$MediaMtxDir;$env:PATH"
}
if (-not (Get-Command mediamtx -ErrorAction SilentlyContinue)) {
    $discoveredMediaMtxDir = Find-AdasMediaMtxDirectory -RepoRoot $RepoRoot
    if ($discoveredMediaMtxDir) {
        $env:PATH = "$discoveredMediaMtxDir;$env:PATH"
        Write-Host "Found MediaMTX at '$discoveredMediaMtxDir'."
    }
}

$ffmpeg = Get-Command ffmpeg -ErrorAction SilentlyContinue
if (-not $ffmpeg) {
    Write-Error "ffmpeg not found on PATH. Install it and add its bin/ directory to PATH, then retry."
    exit 1
}

$mediamtx = Get-Command mediamtx -ErrorAction SilentlyContinue
if (-not $mediamtx) {
    Write-Error @"
mediamtx not found on PATH.

Download it from https://github.com/bluenviron/mediamtx/releases
(grab the Windows amd64 zip), extract mediamtx.exe somewhere permanent, and
add that directory to PATH. Then retry this script.
"@
    exit 1
}

# The YAML is intentionally user-editable: discover every local `-i` input
# from its active runOnInit commands instead of assuming clip names or a fixed
# channel count. Remote and shell-variable inputs are ignored by the helper.
$configPath = Join-Path $RepoRoot "mediamtx.yml"
if (-not (Test-Path -LiteralPath $configPath)) {
    Write-Error "MediaMTX config not found at $configPath."
    exit 1
}
$configuredInputs = @(Get-AdasMediaMtxInputPaths -ConfigPath $configPath -RepoRoot $RepoRoot)
$missing = @($configuredInputs | Where-Object { -not (Test-Path -LiteralPath $_) })
if ($missing.Count -gt 0) {
    $missingDisplay = $missing | ForEach-Object { $_ }
    Write-Warning @"
mediamtx.yml references $($missing.Count) local media input(s) that are missing:
  $($missingDisplay -join "`n  ")

Add the configured files or edit mediamtx.yml to point at different local media.

See docs/operations/README.md.
"@
}
elseif ($configuredInputs.Count -eq 0) {
    Write-Warning "No local -i media inputs were found in mediamtx.yml; verify any remote or variable-based inputs manually."
}
else {
    Write-Host "Validated $($configuredInputs.Count) unique local media input(s) from mediamtx.yml."
}

Write-Host "Starting MediaMTX (mediamtx.yml) from $RepoRoot ..."
& $mediamtx.Source (Join-Path $RepoRoot "mediamtx.yml")
