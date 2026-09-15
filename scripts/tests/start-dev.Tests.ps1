Describe "start-dev managed component launches" {
    It "does not spawn a second visible backend window after managed startup" {
        $scriptPath = Join-Path $PSScriptRoot "..\start-dev.ps1"
        $source = Get-Content -LiteralPath $scriptPath -Raw
        $backendBlock = [regex]::Match(
            $source,
            '(?s)if \(\$Backend\) \{\s*# `uv run fastapi dev`.*?\n\}\s*\n\s*if \(\$Frontend\)'
        ).Value

        $backendBlock | Should Match '(?s)if \(\$managedBackendAi\).*?Start-AdasManagedComponent.*?if \(-not \$managedBackendAi\)\s*\{\s*Start-Component -Title "ADAS - Backend"'
    }

    It "does not reuse the frontend command for a second visible AI window" {
        $scriptPath = Join-Path $PSScriptRoot "..\start-dev.ps1"
        $source = Get-Content -LiteralPath $scriptPath -Raw
        $aiBlock = [regex]::Match(
            $source,
            '(?s)if \(\$Ai\) \{\s*if \(\$managedBackendAi\).*?\n\}\s*\n\s*if \(\$managedBackendAi\)'
        ).Value

        $aiBlock | Should Match '(?s)if \(\$managedBackendAi\).*?Start-AdasManagedComponent.*?if \(-not \$managedBackendAi\)\s*\{\s*Start-Component -Title "ADAS - AI Engine"'
    }
}
