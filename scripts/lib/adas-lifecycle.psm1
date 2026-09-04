Set-StrictMode -Version Latest

function ConvertTo-AdasPowerShellLiteral([string]$Value) {
    return "'$(($Value -replace "'", "''"))'"
}

function Write-AdasAtomicText {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Value
    )
    $parent = Split-Path -Parent $Path
    New-Item -ItemType Directory -Force -Path $parent | Out-Null
    $tmp = "$Path.$([Guid]::NewGuid().ToString('N')).tmp"
    try {
        [System.IO.File]::WriteAllText(
            $tmp,
            $Value,
            (New-Object -TypeName System.Text.UTF8Encoding -ArgumentList $false)
        )
        Move-Item -LiteralPath $tmp -Destination $Path -Force
    }
    finally {
        Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue
    }
}

function Write-AdasAtomicJson {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)]$Value
    )
    Write-AdasAtomicText -Path $Path -Value ($Value | ConvertTo-Json -Depth 8)
}

function Get-AdasShellExecutable {
    if (Get-Command pwsh -ErrorAction SilentlyContinue) {
        return "pwsh"
    }
    return "powershell"
}

function Get-AdasRunDirectory([string]$RepoRoot) {
    $path = Join-Path $RepoRoot "var\run"
    New-Item -ItemType Directory -Force -Path $path | Out-Null
    return $path
}

function Get-AdasEnvValue {
    param(
        [Parameter(Mandatory = $true)][string]$RepoRoot,
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$DefaultValue
    )
    # Match pydantic-settings precedence used by the Python process: an
    # explicitly inherited environment variable wins over the repo-root
    # .env.  The scheduled task normally has no such override, so it reads
    # the same .env value as the backend.
    $processValue = [Environment]::GetEnvironmentVariable($Name)
    if ($processValue) {
        return $processValue
    }
    $envPath = Join-Path $RepoRoot ".env"
    if (-not (Test-Path -LiteralPath $envPath)) {
        return $DefaultValue
    }
    $line = Get-Content -LiteralPath $envPath -ErrorAction SilentlyContinue |
        Where-Object { $_ -match "^\s*$Name\s*=" } |
        Select-Object -Last 1
    if (-not $line) {
        return $DefaultValue
    }
    $value = ($line -split "=", 2)[1].Trim()
    if (-not $value) {
        return $DefaultValue
    }
    return $value
}

function Resolve-AdasConfiguredPath {
    param(
        [Parameter(Mandatory = $true)][string]$RepoRoot,
        [Parameter(Mandatory = $true)][string]$PathValue
    )
    if ([System.IO.Path]::IsPathRooted($PathValue)) {
        return $PathValue
    }
    return Join-Path $RepoRoot $PathValue
}

function Get-AdasBackupDirectory([string]$RepoRoot) {
    $value = Get-AdasEnvValue -RepoRoot $RepoRoot -Name "BACKUP_DIR" -DefaultValue "var\backups"
    return Resolve-AdasConfiguredPath -RepoRoot $RepoRoot -PathValue $value
}

function Get-AdasArchiveDirectory([string]$RepoRoot) {
    $value = Get-AdasEnvValue -RepoRoot $RepoRoot -Name "ARCHIVE_DIR" -DefaultValue "var\archive"
    return Resolve-AdasConfiguredPath -RepoRoot $RepoRoot -PathValue $value
}

function Get-AdasLogDirectory([string]$RepoRoot) {
    $value = Get-AdasEnvValue -RepoRoot $RepoRoot -Name "LOG_DIR" -DefaultValue "var\log"
    return Resolve-AdasConfiguredPath -RepoRoot $RepoRoot -PathValue $value
}

function Get-AdasProtectedBackupDirectory([string]$RepoRoot) {
    $value = Get-AdasEnvValue -RepoRoot $RepoRoot -Name "PROTECTED_BACKUP_DIR" -DefaultValue ""
    if (-not $value) {
        return $null
    }
    # P30 requires explicit absolute external targets.  Do not make a
    # relative value look valid by silently anchoring it to the repo.
    return $value
}

function Get-AdasProtectedArchiveDirectory([string]$RepoRoot) {
    $value = Get-AdasEnvValue -RepoRoot $RepoRoot -Name "PROTECTED_ARCHIVE_DIR" -DefaultValue ""
    if (-not $value) {
        return $null
    }
    return $value
}

function New-AdasLaunchProfile {
    param(
        [Parameter(Mandatory = $true)][bool]$Lan,
        [Parameter(Mandatory = $true)][string]$CertDir,
        [bool]$BackendManaged = $true,
        [bool]$AiManaged = $true
    )
    return [PSCustomObject]@{
        schema_version   = 1
        created_at       = (Get-Date).ToUniversalTime().ToString("o")
        lan              = $Lan
        cert_dir         = $CertDir
        backend_managed  = $BackendManaged
        ai_managed       = $AiManaged
    }
}

function Write-AdasLaunchProfile {
    param(
        [Parameter(Mandatory = $true)][string]$RepoRoot,
        [Parameter(Mandatory = $true)]$Profile
    )
    $path = Join-Path (Get-AdasRunDirectory $RepoRoot) "maintenance-launch-profile.json"
    Write-AdasAtomicJson -Path $path -Value $Profile
}

function Read-AdasLaunchProfile([string]$RepoRoot) {
    $path = Join-Path (Get-AdasRunDirectory $RepoRoot) "maintenance-launch-profile.json"
    if (-not (Test-Path -LiteralPath $path)) {
        return $null
    }
    try {
        $profile = Get-Content -LiteralPath $path -Raw | ConvertFrom-Json
        if (
            $profile.schema_version -ne 1 -or
            $null -eq $profile.lan -or
            $null -eq $profile.cert_dir -or
            $profile.backend_managed -ne $true -or
            $profile.ai_managed -ne $true
        ) {
            return $null
        }
        return $profile
    }
    catch {
        return $null
    }
}

function Get-AdasComponentCommand {
    param(
        [Parameter(Mandatory = $true)][ValidateSet("backend", "ai_engine")][string]$Component,
        [Parameter(Mandatory = $true)][string]$RepoRoot,
        [Parameter(Mandatory = $true)]$Profile
    )
    if ($Component -eq "backend") {
        if ([bool]$Profile.lan) {
            $certDir = [string]$Profile.cert_dir
            $key = Join-Path $certDir "adas-key.pem"
            $cert = Join-Path $certDir "adas-cert.pem"
            return "`$env:PYTHONUTF8 = '1'; uv run uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000 --ssl-keyfile $(ConvertTo-AdasPowerShellLiteral $key) --ssl-certfile $(ConvertTo-AdasPowerShellLiteral $cert) --ws-ping-interval 20 --ws-ping-timeout 20"
        }
        return "`$env:PYTHONUTF8 = '1'; uv run fastapi dev backend/app/main.py"
    }
    if ([bool]$Profile.lan) {
        $cert = Join-Path ([string]$Profile.cert_dir) "adas-cert.pem"
        return "`$env:AI_BACKEND_BASE_URL = 'https://127.0.0.1:8000'; `$env:REQUESTS_CA_BUNDLE = $(ConvertTo-AdasPowerShellLiteral $cert); uv run python ai_engine/main.py"
    }
    return "uv run python ai_engine/main.py"
}

function Write-AdasPidFile {
    param(
        [Parameter(Mandatory = $true)][string]$RepoRoot,
        [Parameter(Mandatory = $true)][ValidateSet("backend", "ai_engine")][string]$Component,
        [Parameter(Mandatory = $true)][int]$ProcessId
    )
    $path = Join-Path (Get-AdasRunDirectory $RepoRoot) "$Component.pid"
    Write-AdasAtomicText -Path $path -Value ([string]$ProcessId)
}

function Get-AdasProcessIdentityPath {
    param(
        [Parameter(Mandatory = $true)][string]$RepoRoot,
        [Parameter(Mandatory = $true)][ValidateSet("backend", "ai_engine")][string]$Component
    )
    return (Join-Path (Get-AdasRunDirectory $RepoRoot) "$Component.pid.identity.json")
}

function Write-AdasProcessIdentity {
    param(
        [Parameter(Mandatory = $true)][string]$RepoRoot,
        [Parameter(Mandatory = $true)][ValidateSet("backend", "ai_engine")][string]$Component,
        [Parameter(Mandatory = $true)][int]$ProcessId
    )
    try {
        $process = Get-Process -Id $ProcessId -ErrorAction Stop
        $record = [PSCustomObject]@{
            schema_version  = 1
            pid             = $ProcessId
            process_name    = $process.ProcessName
            executable_path = $process.Path
            started_at      = $process.StartTime.ToUniversalTime().ToString("o")
        }
        Write-AdasAtomicJson -Path (Get-AdasProcessIdentityPath -RepoRoot $RepoRoot -Component $Component) -Value $record
        return $true
    }
    catch {
        return $false
    }
}

function Test-AdasTrackedProcessIdentity {
    param(
        [Parameter(Mandatory = $true)][string]$RepoRoot,
        [Parameter(Mandatory = $true)][ValidateSet("backend", "ai_engine")][string]$Component,
        [Parameter(Mandatory = $true)][int]$ProcessId
    )
    $identityPath = Get-AdasProcessIdentityPath -RepoRoot $RepoRoot -Component $Component
    if (-not (Test-Path -LiteralPath $identityPath)) {
        return $false
    }
    try {
        $identity = Get-Content -LiteralPath $identityPath -Raw | ConvertFrom-Json
        if ([int]$identity.pid -ne $ProcessId) {
            return $false
        }
        $process = Get-Process -Id $ProcessId -ErrorAction Stop
        # ConvertFrom-Json materializes ISO UTC timestamps as DateTime values
        # on PowerShell 7. Parsing their locale-formatted string representation
        # breaks on machines whose culture is not month-first. Preserve the
        # typed UTC value when available and use invariant round-trip parsing
        # only for runtimes that leave the JSON value as a string.
        if ($identity.started_at -is [DateTime]) {
            $expectedStart = ([DateTimeOffset]$identity.started_at).UtcDateTime
        }
        elseif ($identity.started_at -is [DateTimeOffset]) {
            $expectedStart = $identity.started_at.UtcDateTime
        }
        else {
            $expectedStart = [DateTimeOffset]::Parse(
                [string]$identity.started_at,
                [Globalization.CultureInfo]::InvariantCulture,
                [Globalization.DateTimeStyles]::RoundtripKind
            ).UtcDateTime
        }
        $actualStart = $process.StartTime.ToUniversalTime()
        if (($actualStart - $expectedStart).Duration().TotalSeconds -gt 1) {
            return $false
        }
        if ($identity.process_name -and $process.ProcessName -ne [string]$identity.process_name) {
            return $false
        }
        if ($identity.executable_path -and $process.Path -and
            $process.Path -ine [string]$identity.executable_path) {
            return $false
        }
        return $true
    }
    catch {
        return $false
    }
}

function Start-AdasManagedComponent {
    param(
        [Parameter(Mandatory = $true)][string]$RepoRoot,
        [Parameter(Mandatory = $true)][ValidateSet("backend", "ai_engine")][string]$Component,
        [Parameter(Mandatory = $true)]$Profile,
        [Parameter(Mandatory = $true)][string]$LogDirectory,
        [string]$ShellExecutable = $(Get-AdasShellExecutable)
    )
    if (Test-AdasManagedProcess -RepoRoot $RepoRoot -Component $Component) {
        throw "$Component is already running under the controlled launch profile."
    }
    New-Item -ItemType Directory -Force -Path $LogDirectory | Out-Null
    $timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $stdout = Join-Path $LogDirectory "$Component-$timestamp.log"
    $stderr = Join-Path $LogDirectory "$Component-$timestamp.err.log"
    $command = Get-AdasComponentCommand -Component $Component -RepoRoot $RepoRoot -Profile $Profile
    # `-NoExit` is not sufficient when PowerShell is launched without an
    # interactive console: after the encoded command returns, the wrapper can
    # exit while uv (and the actual service) remains orphaned.  Keep the
    # tracked root alive until its child command exits so the coordinator and
    # the stop guard always have a stable, tree-killable process root.  If the
    # service itself dies, uv returns and this loop leaves an inert wrapper;
    # Test-AdasManagedProcess then fails closed because no matching component
    # remains in its tree.
    $wrapped = "$command; while (`$true) { Start-Sleep -Seconds 3600 }"
    $encoded = [Convert]::ToBase64String(
        [System.Text.Encoding]::Unicode.GetBytes($wrapped)
    )
    $process = Start-Process -FilePath $ShellExecutable `
        -ArgumentList @("-NoExit", "-NoProfile", "-EncodedCommand", $encoded) `
        -WorkingDirectory $RepoRoot -PassThru -WindowStyle Hidden `
        -RedirectStandardOutput $stdout -RedirectStandardError $stderr
    Write-AdasPidFile -RepoRoot $RepoRoot -Component $Component -ProcessId $process.Id
    if (-not (Write-AdasProcessIdentity -RepoRoot $RepoRoot -Component $Component -ProcessId $process.Id)) {
        & taskkill /PID $process.Id /T /F 2>&1 | Out-Null
        Remove-Item -LiteralPath (Join-Path (Get-AdasRunDirectory $RepoRoot) "$Component.pid") -Force -ErrorAction SilentlyContinue
        throw "$Component process identity could not be recorded safely."
    }
    return $process
}

function Get-AdasProcessTreeIds([int]$RootPid) {
    $processes = @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue)
    $children = @{}
    foreach ($process in $processes) {
        $parent = [int]$process.ParentProcessId
        if (-not $children.ContainsKey($parent)) {
            $children[$parent] = @()
        }
        $children[$parent] += [int]$process.ProcessId
    }
    $ids = New-Object System.Collections.Generic.List[int]
    $pending = New-Object System.Collections.Generic.Queue[int]
    $pending.Enqueue($RootPid)
    while ($pending.Count -gt 0) {
        $current = $pending.Dequeue()
        if ($ids.Contains($current)) {
            continue
        }
        $ids.Add($current)
        if ($children.ContainsKey($current)) {
            foreach ($child in $children[$current]) {
                $pending.Enqueue([int]$child)
            }
        }
    }
    return @($ids)
}

function Get-AdasProcessTreeCommandLines([int]$RootPid) {
    $ids = @(Get-AdasProcessTreeIds -RootPid $RootPid)
    $lines = @()
    foreach ($processId in $ids) {
        $process = Get-CimInstance Win32_Process -Filter "ProcessId = $processId" -ErrorAction SilentlyContinue
        if ($process -and $process.CommandLine) {
            $lines += [string]$process.CommandLine
        }
    }
    return @($lines)
}

function Get-AdasMatchingComponentProcesses {
    param(
        [Parameter(Mandatory = $true)][ValidateSet("backend", "ai_engine")][string]$Component
    )
    $pattern = if ($Component -eq "backend") {
        "fastapi|uvicorn|app\.main:app"
    }
    else {
        "ai_engine[\\/]main\.py"
    }
    return @(
        Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
            Where-Object { $_.CommandLine -and $_.CommandLine -match $pattern }
    )
}

function Get-AdasMatchingCoordinatorProcesses {
    return @(
        Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
            Where-Object {
                $_.CommandLine -and
                $_.CommandLine -match "watch-restores" -and
                $_.CommandLine -match "platform" -and
                $_.CommandLine -match "windows"
            }
    )
}

function Test-AdasManagedProcess {
    param(
        [Parameter(Mandatory = $true)][string]$RepoRoot,
        [Parameter(Mandatory = $true)][ValidateSet("backend", "ai_engine")][string]$Component
    )
    $pidPath = Join-Path (Get-AdasRunDirectory $RepoRoot) "$Component.pid"
    if (-not (Test-Path -LiteralPath $pidPath)) {
        return $false
    }
    try {
        $processId = [int](Get-Content -LiteralPath $pidPath -Raw).Trim()
    }
    catch {
        return $false
    }
    if ($processId -le 0) {
        return $false
    }
    $lines = @(Get-AdasProcessTreeCommandLines -RootPid $processId)
    if ($Component -eq "backend") {
        return [bool]($lines | Where-Object { $_ -match "fastapi|uvicorn|app\.main:app" })
    }
    return [bool]($lines | Where-Object { $_ -match "ai_engine[\\/]main\.py" })
}

function Stop-AdasManagedComponent {
    param(
        [Parameter(Mandatory = $true)][string]$RepoRoot,
        [Parameter(Mandatory = $true)][ValidateSet("backend", "ai_engine")][string]$Component,
        [switch]$AllowMissing
    )
    $pidPath = Join-Path (Get-AdasRunDirectory $RepoRoot) "$Component.pid"
    if (-not (Test-Path -LiteralPath $pidPath)) {
        if (@(Get-AdasMatchingComponentProcesses -Component $Component).Count -gt 0) {
            Write-Warning "$Component has a matching process but no controlled PID record; refusing to claim it stopped."
            return $false
        }
        if (-not $AllowMissing) {
            Write-Warning "$Component has no controlled PID record."
            return $false
        }
        return $true
    }
    try {
        $processId = [int](Get-Content -LiteralPath $pidPath -Raw).Trim()
    }
    catch {
        Write-Warning "$Component PID record is invalid; refusing to stop an uncontrolled process."
        return $false
    }
    $managedComponent = Test-AdasManagedProcess -RepoRoot $RepoRoot -Component $Component
    $trackedIdentity = Test-AdasTrackedProcessIdentity -RepoRoot $RepoRoot -Component $Component -ProcessId $processId
    if (-not $managedComponent -and -not $trackedIdentity) {
        if (Get-Process -Id $processId -ErrorAction SilentlyContinue) {
            Write-Warning "$Component PID $processId is not the recorded ADAS process; refusing to kill a reused PID."
            return $false
        }
        $orphaned = @(Get-AdasMatchingComponentProcesses -Component $Component)
        if ($orphaned.Count -gt 0) {
            Write-Warning "$Component's tracked wrapper is gone but a matching process remains; refusing to start database work against an uncontrolled process."
            return $false
        }
        Remove-Item -LiteralPath $pidPath -Force -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath (Get-AdasProcessIdentityPath -RepoRoot $RepoRoot -Component $Component) -Force -ErrorAction SilentlyContinue
        return $true
    }
    & taskkill /PID $processId /T /F 2>&1 | Out-Null
    # taskkill returns before every descendant has finished tearing down.  In
    # particular, uv can briefly leave its interpreter visible while Windows
    # closes the wrapper's process tree.  Give that bounded teardown a chance
    # to finish before classifying a still-matching process as an uncontrolled
    # orphan; the guard remains fail-closed after the deadline.
    for ($attempt = 0; $attempt -lt 20; $attempt++) {
        $rootAlive = $null -ne (Get-Process -Id $processId -ErrorAction SilentlyContinue)
        $matching = @(Get-AdasMatchingComponentProcesses -Component $Component)
        if (-not $rootAlive -and $matching.Count -eq 0) {
            break
        }
        Start-Sleep -Milliseconds 250
    }
    if (Get-Process -Id $processId -ErrorAction SilentlyContinue) {
        Write-Warning "$Component PID $processId remains alive after tree termination."
        return $false
    }
    if (@(Get-AdasMatchingComponentProcesses -Component $Component).Count -gt 0) {
        Write-Warning "$Component has a matching process outside the terminated tree; refusing to claim it stopped."
        return $false
    }
    Remove-Item -LiteralPath $pidPath -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath (Get-AdasProcessIdentityPath -RepoRoot $RepoRoot -Component $Component) -Force -ErrorAction SilentlyContinue
    return $true
}

function Test-AdasPortFree([int]$Port) {
    if (Get-Command Get-NetTCPConnection -ErrorAction SilentlyContinue) {
        return -not [bool](Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
    }
    $lines = netstat -ano | Select-String -Pattern ":$Port\s+.*LISTENING"
    return -not [bool]$lines
}

function Test-AdasCoordinatorProcess {
    param(
        [Parameter(Mandatory = $true)][string]$RepoRoot,
        [Parameter(Mandatory = $true)][string]$BackupDirectory
    )
    $statePath = Join-Path $BackupDirectory "restore_coordinator_state.json"
    if (-not (Test-Path -LiteralPath $statePath)) {
        return @(Get-AdasMatchingCoordinatorProcesses).Count -gt 0
    }
    try {
        $state = Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json
        $processId = [int]$state.pid
        if ($state.platform -ne "windows" -or $state.state -notin @("idle", "executing", "error")) {
            return $false
        }
        $lines = @(Get-AdasProcessTreeCommandLines -RootPid $processId)
        return [bool]($lines | Where-Object { $_ -match "watch-restores" -and $_ -match "platform" -and $_ -match "windows" })
    }
    catch {
        return $false
    }
}

function Start-AdasRestoreCoordinator {
    param(
        [Parameter(Mandatory = $true)][string]$RepoRoot,
        [Parameter(Mandatory = $true)][string]$BackupDirectory,
        [Parameter(Mandatory = $true)][string]$LogDirectory
    )
    if (Test-AdasCoordinatorProcess -RepoRoot $RepoRoot -BackupDirectory $BackupDirectory) {
        return $null
    }
    New-Item -ItemType Directory -Force -Path $LogDirectory | Out-Null
    $timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $stdout = Join-Path $LogDirectory "restore-coordinator-$timestamp.log"
    $stderr = Join-Path $LogDirectory "restore-coordinator-$timestamp.err.log"
    $process = Start-Process -FilePath "uv" `
        -ArgumentList @("run", "--no-sync", "python", "-m", "app.maintenance", "watch-restores", "--platform", "windows") `
        -WorkingDirectory (Join-Path $RepoRoot "backend") -PassThru -WindowStyle Hidden `
        -RedirectStandardOutput $stdout -RedirectStandardError $stderr
    $pidPath = Join-Path (Get-AdasRunDirectory $RepoRoot) "restore-coordinator.pid"
    Write-AdasAtomicText -Path $pidPath -Value ([string]$process.Id)
    return $process
}

function Stop-AdasRestoreCoordinator {
    param(
        [Parameter(Mandatory = $true)][string]$RepoRoot,
        [Parameter(Mandatory = $true)][string]$BackupDirectory
    )
    $pidPath = Join-Path (Get-AdasRunDirectory $RepoRoot) "restore-coordinator.pid"
    if (-not (Test-Path -LiteralPath $pidPath)) {
        if (Test-AdasCoordinatorProcess -RepoRoot $RepoRoot -BackupDirectory $BackupDirectory) {
            Write-Warning "A matching restore coordinator is running without a controlled PID record; refusing to clean up its state."
            return $false
        }
        Remove-Item -LiteralPath (Join-Path $BackupDirectory "restore_coordinator_state.json") -Force -ErrorAction SilentlyContinue
        return $true
    }
    $statePath = Join-Path $BackupDirectory "restore_coordinator_state.json"
    if (Test-Path -LiteralPath $statePath) {
        try {
            $state = Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json
            if ($state.state -eq "executing") {
                Write-Warning "A restore is executing; leaving the coordinator and its runner alive."
                return $false
            }
        }
        catch {
            Write-Warning "Coordinator state is unreadable; refusing to stop an uncontrolled process."
            return $false
        }
    }
    try {
        $processId = [int](Get-Content -LiteralPath $pidPath -Raw).Trim()
    }
    catch {
        Write-Warning "Coordinator PID record is invalid; refusing to stop an uncontrolled process."
        return $false
    }
    if (-not (Test-AdasCoordinatorProcess -RepoRoot $RepoRoot -BackupDirectory $BackupDirectory)) {
        if (Get-Process -Id $processId -ErrorAction SilentlyContinue) {
            Write-Warning "Coordinator PID $processId is not the controlled restore coordinator."
            return $false
        }
        Remove-Item -LiteralPath $pidPath -Force -ErrorAction SilentlyContinue
        return $true
    }
    & taskkill /PID $processId /T /F 2>&1 | Out-Null
    Start-Sleep -Milliseconds 300
    if (Get-Process -Id $processId -ErrorAction SilentlyContinue) {
        Write-Warning "Restore coordinator PID $processId remains alive."
        return $false
    }
    if (@(Get-AdasMatchingCoordinatorProcesses).Count -gt 0) {
        Write-Warning "A matching restore coordinator remains outside the terminated process tree."
        return $false
    }
    Remove-Item -LiteralPath $pidPath -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $statePath -Force -ErrorAction SilentlyContinue
    return $true
}

function Clear-AdasRuntimeMetadata([string]$RepoRoot) {
    $runDir = Get-AdasRunDirectory $RepoRoot
    foreach ($name in @("maintenance-launch-profile.json", "backend.pid", "backend.pid.identity.json", "ai_engine.pid", "ai_engine.pid.identity.json", "restore-coordinator.pid")) {
        Remove-Item -LiteralPath (Join-Path $runDir $name) -Force -ErrorAction SilentlyContinue
    }
}

Export-ModuleMember -Function *-Adas*
