[CmdletBinding()]
param(
    [string]$DataRoot = "$env:ProgramData\DataSetsManager\Server\var",
    [string]$BindAddress = "127.0.0.1",
    [ValidateRange(1,65535)][int]$Port = 8080
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$exe = Join-Path $PSScriptRoot "datasetsmanager-server.exe"
if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) { throw "Missing $exe" }
New-Item -ItemType Directory -Path (Join-Path $DataRoot "bags") -Force | Out-Null
[Environment]::SetEnvironmentVariable("DSM_DATA_ROOT", $DataRoot, "Machine")
[Environment]::SetEnvironmentVariable("DSM_BAG_ROOT", (Join-Path $DataRoot "bags"), "Machine")
[Environment]::SetEnvironmentVariable("DSM_BIND_ADDRESS", $BindAddress, "Machine")
[Environment]::SetEnvironmentVariable("DSM_PORT", $Port.ToString(), "Machine")
& $exe --startup auto install
if ($LASTEXITCODE -ne 0) { throw "Service installation failed." }
& $exe start
if ($LASTEXITCODE -ne 0) { throw "Service start failed." }
Write-Host "DataSetsManager Server installed at http://$BindAddress`:$Port/."
