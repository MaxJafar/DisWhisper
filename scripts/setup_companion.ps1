# DisWhisper Companion App Windows Build & Setup Script
# Checks .NET 8 SDK, restores NuGet packages, and compiles the WinUI 3 App

$ErrorActionPreference = "Stop"

Write-Host "==============================================" -ForegroundColor Cyan
Write-Host "  DisWhisper WinUI 3 Companion App Setup      " -ForegroundColor Cyan
Write-Host "==============================================" -ForegroundColor Cyan

# 1. Check for .NET SDK
$dotnetSdk = Get-Command dotnet -ErrorAction SilentlyContinue
$hasSdk = $false

if ($dotnetSdk) {
    $sdks = & dotnet --list-sdks 2>$null
    if ($sdks -match "(8\.|9\.)") {
        $hasSdk = $true
        Write-Host "[OK] Detected compatible .NET SDK: $sdks" -ForegroundColor Green
    }
}

if (-not $hasSdk) {
    Write-Host "[!] No .NET 8 or 9 SDK detected." -ForegroundColor Yellow
    Write-Host "Attempting automated installation via winget..." -ForegroundColor Yellow
    
    try {
        winget install Microsoft.DotNet.SDK.8 --accept-source-agreements --accept-package-agreements
        Write-Host "[OK] .NET 8 SDK installed successfully! Please restart your terminal if build fails." -ForegroundColor Green
    } catch {
        Write-Host "[FAIL] Automated winget install failed: $_" -ForegroundColor Red
        Write-Host "Please download .NET 8 SDK manually from: https://dotnet.microsoft.com/download/dotnet/8.0" -ForegroundColor Red
        exit 1
    }
}

# 2. Restore and Build WinUI 3 Solution
$solutionPath = "companion\windows\DisWhisper.Companion.sln"

Write-Host "`n==> Restoring NuGet packages..." -ForegroundColor Cyan
& dotnet restore $solutionPath

Write-Host "`n==> Compiling WinUI 3 Companion App..." -ForegroundColor Cyan
& dotnet build $solutionPath -c Release

if ($LASTEXITCODE -eq 0) {
    Write-Host "`n[SUCCESS] DisWhisper WinUI 3 Companion App built successfully!" -ForegroundColor Green
    Write-Host "To launch, run: scripts\run_companion.bat" -ForegroundColor Cyan
} else {
    Write-Host "`n[FAIL] Build failed with exit code $LASTEXITCODE." -ForegroundColor Red
}
