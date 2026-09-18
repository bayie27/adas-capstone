param(
    [Parameter(Mandatory)][string]$Workbook,
    [Parameter(Mandatory)][string]$StagedWorkbook,
    [string]$Edits = 'var/test-evidence/tracker-edits.json'
)
$ErrorActionPreference = 'Stop'
function Invoke-ExcelCall([scriptblock]$Action) {
    for ($attempt = 0; $attempt -lt 10; $attempt++) {
        try { return (& $Action) }
        catch [Runtime.InteropServices.COMException] {
            if ($attempt -eq 9) { throw }
            Start-Sleep -Milliseconds 500
        }
    }
}
$resolvedWorkbook = (Resolve-Path -LiteralPath $Workbook).Path
$resolvedStage = (Resolve-Path -LiteralPath $StagedWorkbook).Path
$backup = $resolvedWorkbook.Replace('.xlsx', '.backup-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.xlsx')
Copy-Item -LiteralPath $resolvedWorkbook -Destination $backup -ErrorAction Stop
$excel = New-Object -ComObject Excel.Application
Invoke-ExcelCall { $excel.Visible = $false }
Invoke-ExcelCall { $excel.DisplayAlerts = $false }
$original = $null
$staged = $null
try {
    $original = Invoke-ExcelCall { $excel.Workbooks.Open($resolvedWorkbook) }
    if ($original.ReadOnly) { throw 'Workbook is locked or read-only. No update saved.' }
    $staged = Invoke-ExcelCall { $excel.Workbooks.Open($resolvedStage, 0, $true) }
    $changes = Get-Content -Raw -LiteralPath $Edits | ConvertFrom-Json
    foreach ($change in $changes) {
        Invoke-ExcelCall {
            $sourceRange = $staged.Worksheets.Item($change.sheet).Range($change.range)
            $destinationRange = $original.Worksheets.Item($change.sheet).Range($change.range)
            $destinationRange.Value2 = $sourceRange.Value2
        }
    }
    $original.Worksheets.Item('Security Testing').Range('F2').NumberFormat = 'yyyy-mm-dd'
    Invoke-ExcelCall { $original.Save() }
    Invoke-ExcelCall { $excel.CalculateFullRebuild() }
    Invoke-ExcelCall { $original.Save() }
    Write-Output ('Backup: ' + $backup)
    Write-Output ('Excel Summary A16:J16: ' + (($original.Worksheets.Item('Summary').Range('A16:J16').Value2 | ConvertTo-Json -Compress)))
} finally {
    if ($staged) { try { Invoke-ExcelCall { $staged.Close($false) } } catch { Write-Warning $_ } }
    if ($original) { try { Invoke-ExcelCall { $original.Close($false) } } catch { Write-Warning $_ } }
    try { Invoke-ExcelCall { $excel.Quit() } } catch { Write-Warning $_ }
    [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($excel)
}
