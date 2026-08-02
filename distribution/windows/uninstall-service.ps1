[CmdletBinding()]
param([switch]$RemoveData)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$exe = Join-Path $PSScriptRoot "datasetsmanager-server.exe"
if (Test-Path -LiteralPath $exe) {
    & $exe stop 2>$null
    & $exe remove
}
if ($RemoveData) {
    $dataRoot=[Environment]::GetEnvironmentVariable("DSM_DATA_ROOT", "Machine")
    if (-not $dataRoot) { throw "DSM_DATA_ROOT is not configured; refusing broad deletion." }
    $resolved=[System.IO.Path]::GetFullPath($dataRoot)
    $programData=[System.IO.Path]::GetFullPath($env:ProgramData)
    if (-not $resolved.StartsWith($programData,[System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to delete data outside ProgramData: $resolved"
    }
    Remove-Item -LiteralPath $resolved -Recurse -Force
}
