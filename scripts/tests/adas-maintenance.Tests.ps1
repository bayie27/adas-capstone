Describe "LAN maintenance readiness probe" {
    It "passes HTTPS readiness URL and certificate arguments for LAN profiles" {
        $scriptPath = Join-Path $PSScriptRoot "..\adas-maintenance.ps1"
        $source = Get-Content -LiteralPath $scriptPath -Raw

        $source | Should Match '\$script:LaunchProfile\.lan'
        $source | Should Match '"--health-url", "https://127\.0\.0\.1:8000/healthz/ready"'
        $source | Should Match '"--health-ca-cert", \$healthCaCert'
    }
}
