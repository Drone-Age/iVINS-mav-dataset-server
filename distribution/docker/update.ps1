[CmdletBinding()]
param(
    [string]$EnvFile = (Join-Path $PSScriptRoot ".env"),
    [string]$BackupRoot = (Join-Path $PSScriptRoot "backups"),
    [int]$HealthTimeoutSeconds = 60,
    [switch]$SkipBackup
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$bundleRoot = $PSScriptRoot

function Get-EnvValue {
    param([string]$Name, [string]$Default)
    if (Test-Path -LiteralPath $EnvFile) {
        $escaped = [regex]::Escape($Name)
        foreach ($line in Get-Content -LiteralPath $EnvFile -Encoding UTF8) {
            $match = [regex]::Match($line, "^\s*$escaped\s*=(.*)$")
            if ($match.Success) {
                return $match.Groups[1].Value.Trim()
            }
        }
    }
    return $Default
}

& (Join-Path $bundleRoot "verify.ps1") -BundleRoot $bundleRoot
if (-not (Test-Path -LiteralPath $EnvFile -PathType Leaf)) {
    throw "Environment file is missing: $EnvFile. Use install.ps1 for a first installation."
}

$dataValue = Get-EnvValue -Name "IVINS_DATA_HOST_ROOT" -Default "./var"
$dataRoot = if ([System.IO.Path]::IsPathRooted($dataValue)) {
    [System.IO.Path]::GetFullPath($dataValue)
} else {
    [System.IO.Path]::GetFullPath((Join-Path $bundleRoot $dataValue))
}

if (-not $SkipBackup -and (Test-Path -LiteralPath $dataRoot -PathType Container)) {
    $resolvedBackupRoot = if ([System.IO.Path]::IsPathRooted($BackupRoot)) {
        [System.IO.Path]::GetFullPath($BackupRoot)
    } else {
        [System.IO.Path]::GetFullPath((Join-Path $bundleRoot $BackupRoot))
    }
    $dataPrefix = $dataRoot.TrimEnd([char[]]@('\', '/')) + [System.IO.Path]::DirectorySeparatorChar
    if ($resolvedBackupRoot.StartsWith($dataPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "BackupRoot must not be inside the data directory."
    }

    New-Item -ItemType Directory -Path $resolvedBackupRoot -Force | Out-Null
    $stamp = [DateTime]::UtcNow.ToString("yyyyMMdd-HHmmss")
    $destination = Join-Path $resolvedBackupRoot "pre-distribution-update-$stamp"
    Write-Host "Backing up $dataRoot to $destination ..."
    Copy-Item -LiteralPath $dataRoot -Destination $destination -Recurse -Force
    Write-Host "Backup complete: $destination"
} elseif ($SkipBackup) {
    Write-Warning "Update is running without a data backup because -SkipBackup was supplied."
}

& (Join-Path $bundleRoot "install.ps1") -EnvFile $EnvFile -HealthTimeoutSeconds $HealthTimeoutSeconds -SkipIntegrityCheck
