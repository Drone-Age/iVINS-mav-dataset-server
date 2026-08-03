[CmdletBinding()]
param(
    [string]$EnvFile = (Join-Path $PSScriptRoot ".env"),
    [int]$TimeoutSeconds = 30
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Net.Http

function Get-EnvValue {
    param([string]$Name)
    $escaped = [regex]::Escape($Name)
    foreach ($line in Get-Content -LiteralPath $EnvFile -Encoding UTF8) {
        $match = [regex]::Match($line, "^\s*$escaped\s*=(.*)$")
        if ($match.Success) {
            return $match.Groups[1].Value.Trim()
        }
    }
    throw "$Name is missing from $EnvFile."
}

if (-not (Test-Path -LiteralPath $EnvFile -PathType Leaf)) {
    throw "Environment file is missing: $EnvFile."
}
$hostName = Get-EnvValue -Name "DSM_PUBLIC_HOST"
if ($hostName -notmatch '^[A-Za-z0-9](?:[A-Za-z0-9.-]{0,251}[A-Za-z0-9])?$') {
    throw "DSM_PUBLIC_HOST is invalid."
}

$handler = [System.Net.Http.HttpClientHandler]::new()
$handler.AllowAutoRedirect = $false
$client = [System.Net.Http.HttpClient]::new($handler)
$client.Timeout = [TimeSpan]::FromSeconds($TimeoutSeconds)
try {
    $http = $client.GetAsync("http://$hostName/health").GetAwaiter().GetResult()
    if ([int]$http.StatusCode -notin @(301, 302, 307, 308)) {
        throw "Plain HTTP did not redirect to HTTPS; status=$([int]$http.StatusCode)."
    }
    $location = $http.Headers.Location
    if ($null -eq $location -or $location.Scheme -ne "https") {
        throw "Plain HTTP redirect does not target HTTPS."
    }

    $https = $client.GetAsync("https://$hostName/health").GetAwaiter().GetResult()
    if (-not $https.IsSuccessStatusCode) {
        throw "HTTPS health request failed; status=$([int]$https.StatusCode)."
    }
    $hsts = $https.Headers.GetValues("Strict-Transport-Security") -join ","
    if ($hsts -notmatch 'max-age=31536000') {
        throw "HTTPS response lacks the required HSTS policy."
    }
    $payload = $https.Content.ReadAsStringAsync().GetAwaiter().GetResult() | ConvertFrom-Json
    if ($payload.status -ne "ok") {
        throw "HTTPS health response is not healthy."
    }
    Write-Host "TLS verification passed for https://$hostName (Backend $($payload.backend_version), Distribution $($payload.distribution_version))."
} finally {
    $client.Dispose()
    $handler.Dispose()
}
