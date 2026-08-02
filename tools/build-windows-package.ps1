[CmdletBinding()]
param([string]$OutputDirectory = (Join-Path $PSScriptRoot "..\dist"))

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$root=[System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$versions=Get-Content -LiteralPath (Join-Path $root "versions.json") -Raw | ConvertFrom-Json
if ($env:OS -ne "Windows_NT") { throw "windows-portable must be built on Windows." }
python -m pip install --disable-pip-version-check --requirement (Join-Path $root "requirements-windows.txt")
if ($LASTEXITCODE -ne 0) { throw "Windows build dependencies failed." }
$separator=[System.IO.Path]::PathSeparator
$dataArgs=@(
    "--add-data", "$(Join-Path $root 'templates')${separator}templates",
    "--add-data", "$(Join-Path $root 'static')${separator}static",
    "--add-data", "$(Join-Path $root 'seed')${separator}seed",
    "--add-data", "$(Join-Path $root 'versions.json')${separator}."
)
python -m PyInstaller --noconfirm --clean --onefile --name datasetsmanager-server --hidden-import win32timezone @dataArgs (Join-Path $root "windows_service.py")
if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed." }
$name="datasetsmanager-server_d$($versions.distribution)-b$($versions.backend)-f$($versions.frontend)-p$($versions.process)_windows-x64"
$stage=Join-Path ([System.IO.Path]::GetFullPath($OutputDirectory)) $name
New-Item -ItemType Directory -Path $stage -Force | Out-Null
Copy-Item -LiteralPath (Join-Path $root "dist\datasetsmanager-server.exe") -Destination $stage
Copy-Item -Path (Join-Path $root "distribution\windows\*.ps1") -Destination $stage
Copy-Item -LiteralPath (Join-Path $root "versions.json") -Destination $stage
Copy-Item -LiteralPath (Join-Path $root "distribution\package-manifest.schema.json") -Destination $stage
$manifest=[ordered]@{
    schema_version="1.0"; distribution=@{name="DataSetsManager Server";version=$versions.distribution};
    package_format="windows-portable"; platform=@{os="windows";architecture="x64"};
    components=@{backend=$versions.backend;frontend=$versions.frontend;process=$versions.process;distribution=$versions.distribution};
    compatibility=$versions.compatibility; runtime=@{executable="datasetsmanager-server.exe";service="DataSetsManagerServer"};
    entrypoints=@{install="install-service.ps1";update="install-service.ps1";rollback="install-service.ps1";verify="verify.ps1";create_admin_key="new-admin-key.ps1"};
    data=@{included=$false;persistent=$true;default_root="%ProgramData%\DataSetsManager\Server\var"}
}
$manifest | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath (Join-Path $stage "package-manifest.json") -Encoding utf8
Get-ChildItem -LiteralPath $stage -File | Sort-Object Name | ForEach-Object {"$((Get-FileHash $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()) *$($_.Name)"} | Set-Content -LiteralPath (Join-Path $stage "SHA256SUMS") -Encoding ascii
$zip="$stage.zip"
Compress-Archive -Path (Join-Path $stage "*") -DestinationPath $zip -Force
"$((Get-FileHash $zip -Algorithm SHA256).Hash.ToLowerInvariant()) *$([IO.Path]::GetFileName($zip))" | Set-Content -LiteralPath "$zip.sha256" -Encoding ascii
Get-Item -LiteralPath $zip
