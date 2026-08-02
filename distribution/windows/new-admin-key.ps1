[CmdletBinding()]
param([Parameter(Mandatory)][ValidatePattern('^[A-Za-z0-9][A-Za-z0-9._ -]{0,63}$')][string]$Name)

$ErrorActionPreference = "Stop"
& (Join-Path $PSScriptRoot "datasetsmanager-server.exe") key create --name $Name --role admin
if ($LASTEXITCODE -ne 0) { throw "API-key creation failed." }
