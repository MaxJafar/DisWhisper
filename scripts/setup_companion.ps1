# Build the unpackaged WinUI companion from any current directory.
[CmdletBinding()]
param(
    [string]$DotnetPath = "dotnet",
    [ValidateSet("x64", "ARM64")][string]$Platform = "x64",
    [switch]$InstallSdk,
    [switch]$CreateDesktopShortcut
)

$ErrorActionPreference = "Stop"
$env:DOTNET_CLI_TELEMETRY_OPTOUT = "1"
$env:DOTNET_NOLOGO = "1"

function Test-CompatibleSdk {
    if (-not (Get-Command $DotnetPath -ErrorAction SilentlyContinue)) { return $false }
    $sdks = & $DotnetPath --list-sdks
    return [bool]($sdks | Where-Object { $_ -match '^(8|9|[1-9]\d+)\.' })
}

if (-not (Test-CompatibleSdk)) {
    if (-not $InstallSdk) {
        throw "A .NET 8+ SDK is required. Install it from https://dotnet.microsoft.com/download/dotnet/8.0 or rerun with -InstallSdk."
    }
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) { throw "winget is unavailable; install the .NET 8 SDK manually." }
    & winget install --id Microsoft.DotNet.SDK.8 --exact --accept-source-agreements --accept-package-agreements
    if ($LASTEXITCODE -ne 0) { throw "SDK installation failed with exit code $LASTEXITCODE." }
    if (-not (Test-CompatibleSdk)) { throw "Restart your terminal so the installed SDK is available, then run this script again." }
}

$projectPath = Join-Path $PSScriptRoot "..\companion\windows\DisWhisper.Companion\DisWhisper.Companion.csproj"
$runtimeId = "win-$($Platform.ToLowerInvariant())"
& $DotnetPath build $projectPath -c Release "-p:Platform=$Platform" "-p:RuntimeIdentifier=$runtimeId" --nologo -v:minimal
if ($LASTEXITCODE -ne 0) { throw "Companion build failed with exit code $LASTEXITCODE." }
if ($CreateDesktopShortcut) {
    & (Join-Path $PSScriptRoot "create_desktop_shortcut.ps1") -Platform $Platform
}
Write-Host "Companion built. Launch it with scripts\run_companion.bat on x64 Windows." -ForegroundColor Green
