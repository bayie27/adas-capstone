Describe "managed component shutdown" {
    BeforeAll {
        Import-Module (Join-Path $PSScriptRoot "..\lib\adas-lifecycle.psm1") -Force
    }

    It "handles a stale tracked PID without reporting a missing-process error" {
        $repoRoot = Join-Path $TestDrive "repo"
        $runDir = Get-AdasRunDirectory -RepoRoot $repoRoot
        $stalePid = 2147483647
        $pidPath = Join-Path $runDir "ai_engine.pid"
        $identityPath = Get-AdasProcessIdentityPath -RepoRoot $repoRoot -Component ai_engine

        Set-Content -LiteralPath $pidPath -Value $stalePid
        [ordered]@{
            pid = $stalePid
            process_name = "python"
            started_at = "2026-09-15T00:00:00Z"
        } | ConvertTo-Json | Set-Content -LiteralPath $identityPath

        $Error.Clear()
        $stopped = Stop-AdasManagedComponent -RepoRoot $repoRoot -Component ai_engine -AllowMissing
        $missingProcessErrors = @(
            $Error | Where-Object {
                $_.Exception.Message -match "Cannot find a process with the process identifier"
            }
        )

        $stopped | Should Be $true
        ($missingProcessErrors | Measure-Object).Count | Should Be 0
        (Test-Path -LiteralPath $pidPath) | Should Be $false
        (Test-Path -LiteralPath $identityPath) | Should Be $false
    }
}
