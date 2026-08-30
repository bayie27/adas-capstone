<#
.SYNOPSIS
    Publishes one positive UAT clip, then returns the RTSP path to the
    non-alerting airbase feed.

.DESCRIPTION
    UAT positive clips must trigger once per profile activation. Publishing a
    positive clip with `-stream_loop -1` creates another accident after the
    operator resolves the first one, while letting FFmpeg exit leaves the
    simulated camera disconnected. This helper performs the positive pass once,
    makes a brief publisher handover, and then retries only the silent feed for
    the rest of the MediaMTX run.

    MediaMTX owns this process through runOnInit. Stopping MediaMTX tree-stops
    the helper and its current FFmpeg child.
#>

param(
    [Parameter(Mandatory = $true)][string]$PositiveClip,
    [Parameter(Mandatory = $true)][string]$SilentClip,
    [Parameter(Mandatory = $true)][string]$RtspUrl,
    [switch]$ValidateOnly
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot

function Resolve-UatClip([string]$ClipPath) {
    $candidate = if ([System.IO.Path]::IsPathRooted($ClipPath)) {
        $ClipPath
    }
    else {
        Join-Path $RepoRoot $ClipPath
    }

    $resolved = Resolve-Path -LiteralPath $candidate -ErrorAction Stop
    if (-not (Test-Path -LiteralPath $resolved.Path -PathType Leaf)) {
        throw "UAT clip is not a file: $($resolved.Path)"
    }
    return $resolved.Path
}

$ffmpeg = Get-Command ffmpeg -ErrorAction Stop
$positivePath = Resolve-UatClip $PositiveClip
$silentPath = Resolve-UatClip $SilentClip

if ($RtspUrl -notmatch '^rtsp://') {
    throw "RtspUrl must start with rtsp://"
}

if ($ValidateOnly) {
    Write-Host "[uat-publisher] ffmpeg: $($ffmpeg.Source)"
    Write-Host "[uat-publisher] positive: $positivePath"
    Write-Host "[uat-publisher] silent: $silentPath"
    Write-Host "[uat-publisher] destination: $RtspUrl"
    exit 0
}

Write-Host "[uat-publisher] Publishing positive clip once: $positivePath"
& $ffmpeg.Source `
    -hide_banner -loglevel warning `
    -re -i $positivePath `
    -c copy -rtsp_transport tcp -f rtsp $RtspUrl

if ($LASTEXITCODE -ne 0) {
    throw "Positive UAT publisher exited with code $LASTEXITCODE"
}

Write-Host "[uat-publisher] Positive clip completed; switching permanently to silent feed."
while ($true) {
    & $ffmpeg.Source `
        -hide_banner -loglevel warning `
        -re -stream_loop -1 -i $silentPath `
        -c copy -rtsp_transport tcp -f rtsp $RtspUrl

    $silentExitCode = $LASTEXITCODE
    Write-Warning "Silent UAT publisher exited with code $silentExitCode; retrying silent feed only."
    Start-Sleep -Seconds 1
}
