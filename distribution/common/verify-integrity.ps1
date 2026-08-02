[CmdletBinding()]
param([string]$BundleRoot = $PSScriptRoot)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$root = [System.IO.Path]::GetFullPath((Resolve-Path -LiteralPath $BundleRoot).Path)
$checksumFile = Join-Path $root "SHA256SUMS"
if (-not (Test-Path -LiteralPath $checksumFile -PathType Leaf)) {
    throw "SHA256SUMS is missing from the package."
}

$separator = [System.IO.Path]::DirectorySeparatorChar
$rootPrefix = $root.TrimEnd([char[]]@('\', '/')) + $separator
$checked = 0
foreach ($line in Get-Content -LiteralPath $checksumFile -Encoding UTF8) {
    if ([string]::IsNullOrWhiteSpace($line)) { continue }
    $match = [regex]::Match($line, '^(?<hash>[A-Fa-f0-9]{64})\s+\*(?<path>.+)$')
    if (-not $match.Success) { throw "Invalid SHA256SUMS entry: $line" }
    $relative = $match.Groups["path"].Value.Replace('/', $separator)
    $target = [System.IO.Path]::GetFullPath((Join-Path $root $relative))
    if (-not $target.StartsWith($rootPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Checksum path escapes the package: $relative"
    }
    if (-not (Test-Path -LiteralPath $target -PathType Leaf)) { throw "Packaged file is missing: $relative" }
    $actual = (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash
    if (-not $actual.Equals($match.Groups["hash"].Value, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "SHA-256 mismatch: $relative"
    }
    $checked++
}
if ($checked -eq 0) { throw "SHA256SUMS contains no files." }
Write-Host "Integrity check passed ($checked files)."
