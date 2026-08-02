[CmdletBinding()]
param([string]$BaseUri = "http://127.0.0.1:8080")

$ErrorActionPreference = "Stop"
$health=Invoke-RestMethod "$($BaseUri.TrimEnd('/'))/health" -TimeoutSec 10
$versions=Invoke-RestMethod "$($BaseUri.TrimEnd('/'))/versions" -TimeoutSec 10
if ($health.status -ne "ok" -or $versions.backend -ne "4.0.0") { throw "Unexpected service response." }
$versions | ConvertTo-Json -Depth 8
