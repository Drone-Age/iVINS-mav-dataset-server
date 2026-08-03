[CmdletBinding()]
param(
    [string]$EnvFile = (Join-Path $PSScriptRoot ".env"),
    [int]$HealthTimeoutSeconds = 60,
    [switch]$SkipIntegrityCheck
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$bundleRoot = $PSScriptRoot

function Invoke-Docker {
    param([string[]]$Arguments)
    & docker @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Docker command failed: docker $($Arguments -join ' ')"
    }
}

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

if (-not $SkipIntegrityCheck) {
    & (Join-Path $bundleRoot "verify.ps1") -BundleRoot $bundleRoot
}

$manifestPath = Join-Path $bundleRoot "package-manifest.json"
$manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
if ($manifest.package_format -ne "docker-bundle") {
    throw "This installer supports only a docker-bundle package."
}

if (-not (Test-Path -LiteralPath $EnvFile -PathType Leaf)) {
    Copy-Item -LiteralPath (Join-Path $bundleRoot ".env.example") -Destination $EnvFile
    Write-Host "Created $EnvFile from .env.example."
}

$dataValue = Get-EnvValue -Name "DSM_DATA_HOST_ROOT" -Default "./var"
$dataRoot = if ([System.IO.Path]::IsPathRooted($dataValue)) {
    [System.IO.Path]::GetFullPath($dataValue)
} else {
    [System.IO.Path]::GetFullPath((Join-Path $bundleRoot $dataValue))
}
New-Item -ItemType Directory -Path $dataRoot -Force | Out-Null

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker CLI is not installed or is not on PATH."
}
Invoke-Docker -Arguments @("info", "--format", "{{.ServerVersion}}")

$archive = Join-Path $bundleRoot ($manifest.image.archive.Replace('/', [System.IO.Path]::DirectorySeparatorChar))
Invoke-Docker -Arguments @("load", "--input", $archive)
if ($manifest.PSObject.Properties.Name -contains "proxy") {
    $proxyArchive = Join-Path $bundleRoot ($manifest.proxy.archive.Replace('/', [System.IO.Path]::DirectorySeparatorChar))
    Invoke-Docker -Arguments @("load", "--input", $proxyArchive)
}

$composeFile = Join-Path $bundleRoot "compose.release.yaml"
$base = @("compose", "--env-file", $EnvFile, "-f", $composeFile)
Invoke-Docker -Arguments ($base + @("config", "--quiet"))
Invoke-Docker -Arguments ($base + @("up", "-d"))

$deadline = [DateTime]::UtcNow.AddSeconds($HealthTimeoutSeconds)
$health = $null
while ([DateTime]::UtcNow -lt $deadline) {
    try {
        [string]$healthJson = & docker @base exec -T server python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8080/health', timeout=3).read().decode())"
        if ($LASTEXITCODE -ne 0) {
            throw "Internal health request failed."
        }
        $health = $healthJson | ConvertFrom-Json
        if ($health.status -eq "ok") {
            break
        }
    } catch {
        Start-Sleep -Milliseconds 750
    }
}
if ($null -eq $health -or $health.status -ne "ok") {
    throw "Service did not become healthy within $HealthTimeoutSeconds seconds."
}

[string]$versionsJson = & docker @base exec -T server python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8080/versions', timeout=5).read().decode())"
if ($LASTEXITCODE -ne 0) {
    throw "Internal versions request failed."
}
$deployed = $versionsJson | ConvertFrom-Json
foreach ($component in @("backend", "frontend", "process", "distribution")) {
    $expected = $manifest.components.$component
    $actual = $deployed.$component
    if ($actual -ne $expected) {
        throw "Version mismatch for ${component}: expected $expected, got $actual."
    }
}

Write-Host "DataSetsManager Server is healthy on the private Compose network."
Write-Host "Run .\verify-tls.ps1 after DNS and ACME certificate issuance to qualify the public endpoint."
Write-Host "Backend $($deployed.backend), Frontend $($deployed.frontend), Process $($deployed.process), Distribution $($deployed.distribution)."
if (-not $health.key_store_ready) {
    Write-Warning "No active API key exists. Run .\new-admin-key.ps1 locally."
}
