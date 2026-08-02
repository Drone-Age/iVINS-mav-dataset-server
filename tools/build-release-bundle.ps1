[CmdletBinding()]
param(
    [ValidatePattern('^linux/(amd64|arm64)$')]
    [string]$Platform = "linux/amd64",
    [string]$OutputDirectory = (Join-Path $PSScriptRoot "..\dist"),
    [switch]$SkipBuild
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Invoke-Docker {
    param([string[]]$Arguments)
    & docker @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Docker command failed: docker $($Arguments -join ' ')"
    }
}

$repoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$versionsPath = Join-Path $repoRoot "versions.json"
$versions = Get-Content -LiteralPath $versionsPath -Raw -Encoding UTF8 | ConvertFrom-Json
$semver = '^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$'
foreach ($component in @("backend", "frontend", "process", "distribution")) {
    if ($versions.$component -notmatch $semver) {
        throw "Invalid $component version in versions.json."
    }
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker CLI is not installed or is not on PATH."
}
Invoke-Docker -Arguments @("info", "--format", "{{.ServerVersion}}")

$imageReference = "ivins-mav-dataset-server:$($versions.backend)"
if (-not $SkipBuild) {
    Invoke-Docker -Arguments @(
        "buildx", "build",
        "--platform", $Platform,
        "--load",
        "--tag", $imageReference,
        $repoRoot
    )
}

[string]$imageId = & docker image inspect --format "{{.Id}}" $imageReference
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($imageId)) {
    throw "Docker image is unavailable: $imageReference"
}
$imageId = $imageId.Trim()
[string]$imageOs = & docker image inspect --format "{{.Os}}" $imageReference
if ($LASTEXITCODE -ne 0) {
    throw "Cannot inspect image operating system."
}
[string]$imageArchitecture = & docker image inspect --format "{{.Architecture}}" $imageReference
if ($LASTEXITCODE -ne 0) {
    throw "Cannot inspect image architecture."
}
$actualPlatform = "$($imageOs.Trim())/$($imageArchitecture.Trim())"
if ($actualPlatform -ne $Platform) {
    throw "Image platform mismatch: expected $Platform, got $actualPlatform."
}

$outputRoot = [System.IO.Path]::GetFullPath($OutputDirectory)
New-Item -ItemType Directory -Path $outputRoot -Force | Out-Null
$platformName = $Platform.Replace("/", "-")
$bundleName = "ivins-server_d$($versions.distribution)-b$($versions.backend)-f$($versions.frontend)-p$($versions.process)_docker-$platformName"
$stage = [System.IO.Path]::GetFullPath((Join-Path $outputRoot $bundleName))
$outputPrefix = $outputRoot.TrimEnd([char[]]@('\', '/')) + [System.IO.Path]::DirectorySeparatorChar
if (-not $stage.StartsWith($outputPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Refusing to stage outside OutputDirectory."
}
if (Test-Path -LiteralPath $stage) {
    Remove-Item -LiteralPath $stage -Recurse -Force
}
New-Item -ItemType Directory -Path (Join-Path $stage "images") -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $stage "docs") -Force | Out-Null

$imageArchiveName = "ivins-mav-dataset-server_$($versions.backend)_$platformName.tar"
$imageArchiveRelative = "images/$imageArchiveName"
$imageArchive = Join-Path $stage ($imageArchiveRelative.Replace('/', [System.IO.Path]::DirectorySeparatorChar))
Invoke-Docker -Arguments @("save", "--output", $imageArchive, $imageReference)

$rootFiles = @(
    "compose.release.yaml",
    ".env.example",
    "versions.json"
)
foreach ($file in $rootFiles) {
    Copy-Item -LiteralPath (Join-Path $repoRoot $file) -Destination (Join-Path $stage $file)
}
foreach ($script in Get-ChildItem -LiteralPath (Join-Path $repoRoot "distribution\docker") -Filter "*.ps1" -File) {
    Copy-Item -LiteralPath $script.FullName -Destination (Join-Path $stage $script.Name)
}

Copy-Item -LiteralPath (Join-Path $repoRoot "distribution\DISTRIBUTION.md") -Destination (Join-Path $stage "README.md")
Copy-Item -LiteralPath (Join-Path $repoRoot "distribution\package-manifest.schema.json") -Destination (Join-Path $stage "package-manifest.schema.json")
Copy-Item -LiteralPath (Join-Path $repoRoot "VERSIONING.md") -Destination (Join-Path $stage "docs\VERSIONING.md")
Copy-Item -LiteralPath (Join-Path $repoRoot "process") -Destination (Join-Path $stage "docs\process") -Recurse
foreach ($changelog in Get-ChildItem -LiteralPath $repoRoot -Filter "CHANGELOG.*.md" -File) {
    Copy-Item -LiteralPath $changelog.FullName -Destination (Join-Path $stage "docs\$($changelog.Name)")
}

$manifest = [ordered]@{
    schema_version = "1.0"
    distribution = [ordered]@{
        name = "iVINS Dataset Server"
        version = $versions.distribution
    }
    package_format = "docker-bundle"
    platform = [ordered]@{
        os = $imageOs.Trim()
        architecture = $imageArchitecture.Trim()
    }
    components = [ordered]@{
        backend = $versions.backend
        frontend = $versions.frontend
        process = $versions.process
        distribution = $versions.distribution
    }
    compatibility = $versions.compatibility
    image = [ordered]@{
        reference = $imageReference
        archive = $imageArchiveRelative
        image_id = $imageId
    }
    entrypoints = [ordered]@{
        install = "install.ps1"
        update = "update.ps1"
        rollback = "rollback.ps1"
        verify = "verify.ps1"
        create_admin_key = "new-admin-key.ps1"
    }
    data = [ordered]@{
        included = $false
        persistent = $true
        default_root = "./var"
    }
}
$utf8 = New-Object System.Text.UTF8Encoding($false)
$manifestJson = $manifest | ConvertTo-Json -Depth 12
[System.IO.File]::WriteAllText((Join-Path $stage "package-manifest.json"), $manifestJson, $utf8)

$checksumLines = New-Object System.Collections.Generic.List[string]
$stagePrefix = $stage.TrimEnd([char[]]@('\', '/')) + [System.IO.Path]::DirectorySeparatorChar
foreach ($file in Get-ChildItem -LiteralPath $stage -Recurse -File | Sort-Object FullName) {
    $relative = $file.FullName.Substring($stagePrefix.Length).Replace('\', '/')
    $hash = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
    $checksumLines.Add("$hash *$relative")
}
[System.IO.File]::WriteAllLines((Join-Path $stage "SHA256SUMS"), $checksumLines, $utf8)

$zipPath = Join-Path $outputRoot "$bundleName.zip"
if (Test-Path -LiteralPath $zipPath) {
    Remove-Item -LiteralPath $zipPath -Force
}
Add-Type -AssemblyName System.IO.Compression.FileSystem
[System.IO.Compression.ZipFile]::CreateFromDirectory(
    $stage,
    $zipPath,
    [System.IO.Compression.CompressionLevel]::Optimal,
    $false
)
$zipHash = (Get-FileHash -LiteralPath $zipPath -Algorithm SHA256).Hash.ToLowerInvariant()
$sidecar = "$zipHash *$([System.IO.Path]::GetFileName($zipPath))"
[System.IO.File]::WriteAllText("$zipPath.sha256", $sidecar + [Environment]::NewLine, $utf8)

[pscustomobject]@{
    bundle = $bundleName
    zip = $zipPath
    sha256 = $zipHash
    image = $imageReference
    image_id = $imageId
    platform = $Platform
} | Format-List
