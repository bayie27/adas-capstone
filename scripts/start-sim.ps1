<#
.SYNOPSIS
    Starts the MediaMTX camera simulation (mediamtx.yml) from the repo root.

.DESCRIPTION
    Preflights the two external binaries this depends on (ffmpeg, mediamtx)
    and the eval/clips/ directory, then execs `mediamtx mediamtx.yml`. Ctrl+C
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

# mediamtx.yml sources the five channels from here. The clips are gitignored,
# so a fresh clone has none and MediaMTX would start with every path failing to
# publish — a confusing symptom for a missing-files cause. Name the five it
# actually needs rather than just checking the directory is non-empty.
$clipsDir = Join-Path $RepoRoot "ai_engine\eval\clips"
$required = @("dekwatro", "tric-motor-car", "red-car-motor", "motor-motor-night", "airbase")
$missing = $required | Where-Object { -not (Test-Path (Join-Path $clipsDir "$_.mp4")) }
if ($missing) {
    Write-Warning @"
ai_engine\eval\clips\ is missing $($missing.Count) of the 5 clips mediamtx.yml needs:
  $($missing -join ', ')

Populate it from the frozen research package:
  cp ai_engine/adas_transfer/clips/*.mp4 ai_engine/eval/clips/

See ai_engine/eval/README.md.
"@
}

Write-Host "Starting MediaMTX (mediamtx.yml) from $RepoRoot ..."
& $mediamtx.Source (Join-Path $RepoRoot "mediamtx.yml")
