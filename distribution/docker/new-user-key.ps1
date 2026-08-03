[CmdletBinding()]
param(
    [ValidatePattern('^[A-Za-z0-9][A-Za-z0-9._ -]{0,63}$')]
    [string]$Name = "dataset-e2e",
    [string]$EnvFile = (Join-Path $PSScriptRoot ".env"),
    [switch]$SkipIntegrityCheck
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if (-not $SkipIntegrityCheck) {
    & (Join-Path $PSScriptRoot "verify.ps1") -BundleRoot $PSScriptRoot
}
if (-not (Test-Path -LiteralPath $EnvFile -PathType Leaf)) {
    throw "Environment file is missing: $EnvFile. Run install.ps1 first."
}

$composeFile = Join-Path $PSScriptRoot "compose.release.yaml"
& docker compose --env-file $EnvFile -f $composeFile run --rm --no-deps server python api_keys.py create --name $Name --role user
if ($LASTEXITCODE -ne 0) {
    throw "The server did not create the user API key."
}

Write-Warning "The plaintext API key above is shown once. Store it in the approved secret store and expose it to clients only as DSM_SERVER_TOKEN."
