Describe "MediaMTX simulation configuration discovery" {
    BeforeAll {
        Import-Module (Join-Path $PSScriptRoot "..\lib\adas-lifecycle.psm1") -Force
    }

    It "discovers arbitrary local input files from runOnInit commands" {
        $configPath = Join-Path $TestDrive "mediamtx.yml"
        $clipDir = Join-Path $TestDrive "clips"
        New-Item -ItemType Directory -Path $clipDir | Out-Null
        $first = Join-Path $clipDir "first.mp4"
        $second = Join-Path $clipDir "second.mp4"
        New-Item -ItemType File -Path $first, $second | Out-Null

        @"
paths:
  channel-a:
    runOnInit: ffmpeg -re -i ./clips/first.mp4 -f rtsp rtsp://localhost:8554/channel-a
  channel-b:
    runOnInit: ffmpeg -re -i './clips/second.mp4' -f rtsp rtsp://localhost:8554/channel-b
  channel-c:
    runOnInit: ffmpeg -re -i ./clips/first.mp4 -f rtsp rtsp://localhost:8554/channel-c
"@ | Set-Content -LiteralPath $configPath

        $found = @(Get-AdasMediaMtxInputPaths -ConfigPath $configPath -RepoRoot $TestDrive)

        ($found | Measure-Object).Count | Should Be 2
        ($found -contains [System.IO.Path]::GetFullPath($first)) | Should Be $true
        ($found -contains [System.IO.Path]::GetFullPath($second)) | Should Be $true
    }

    It "finds an extracted MediaMTX release beside the repository" {
        $repoRoot = Join-Path $TestDrive "repo"
        $installDir = Join-Path $TestDrive "mediamtx_v1.18.0_windows_amd64"
        New-Item -ItemType Directory -Path $repoRoot, $installDir | Out-Null
        New-Item -ItemType File -Path (Join-Path $installDir "mediamtx.exe") | Out-Null

        $found = Find-AdasMediaMtxDirectory -RepoRoot $repoRoot

        $found | Should Be ([System.IO.Path]::GetFullPath($installDir))
    }
}
