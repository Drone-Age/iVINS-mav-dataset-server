[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$PreviousBundle,
    [string]$EnvFile = (Join-Path $PSScriptRoot ".env"),
    [int]$HealthTimeoutSeconds = 60
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$previousRoot = (Resolve-Path -LiteralPath $PreviousBundle).Path
$installer = Join-Path $previousRoot "install.ps1"
$verifier = Join-Path $previousRoot "verify.ps1"
if (-not (Test-Path -LiteralPath $installer -PathType Leaf) -or
    -not (Test-Path -LiteralPath $verifier -PathType Leaf)) {
    throw "PreviousBundle is not an extracted iVINS Distribution bundle."
}
if (-not (Test-Path -LiteralPath $EnvFile -PathType Leaf)) {
    throw "Current environment file is missing: $EnvFile"
}

& $verifier -BundleRoot $previousRoot
Write-Warning "Rollback changes application files only. Runtime data is preserved and is not automatically restored."
& $installer -EnvFile $EnvFile -HealthTimeoutSeconds $HealthTimeoutSeconds -SkipIntegrityCheck
Write-Host "Rollback to the previous bundle completed."
