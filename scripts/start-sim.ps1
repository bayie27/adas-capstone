<#
.SYNOPSIS
    Starts the MediaMTX camera simulation (mediamtx.yml) from the repo root.

.DESCRIPTION
    Preflights the two external binaries this depends on (ffmpeg, mediamtx)
    and the sample_vids/ directory, then execs `mediamtx mediamtx.yml`. Ctrl+C
    stops MediaMTX and its child ffmpeg processes together.
#>

$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

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

$sampleVidsDir = Join-Path $RepoRoot "ai_engine\sample_vids"
if (-not (Test-Path $sampleVidsDir) -or -not (Get-ChildItem $sampleVidsDir -Filter "*.mp4" -ErrorAction SilentlyContinue)) {
    Write-Warning "ai_engine\sample_vids\ is missing or empty. See the README for how to obtain the clips."
}

Write-Host "Starting MediaMTX (mediamtx.yml) from $RepoRoot ..."
& $mediamtx.Source (Join-Path $RepoRoot "mediamtx.yml")
