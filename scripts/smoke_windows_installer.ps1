[CmdletBinding()]
param([Parameter(Mandatory)][string]$Version)
$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$installer = Join-Path $projectRoot "dist\DisWhisper-$Version-windows-x64-setup.exe"
$installFolder = Join-Path $projectRoot ".cache\installer-check"
$uninstaller = Join-Path $installFolder "unins000.exe"
if (Test-Path -LiteralPath $installFolder) { throw "Installer check folder already exists; inspect it before retrying." }
$process = Start-Process -FilePath $installer -ArgumentList @("/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/NOICONS", "/DIR=`"$installFolder`"") -Wait -PassThru
if ($process.ExitCode -ne 0) { throw "Installer check failed with exit code $($process.ExitCode)." }
try {
    if (-not (Test-Path -LiteralPath (Join-Path $installFolder "DisWhisper.Companion.exe"))) { throw "Installed app is missing." }
    & python (Join-Path $projectRoot "scripts\smoke_release.py") (Join-Path $installFolder "backend\diswhisper-backend.exe")
    if ($LASTEXITCODE -ne 0) { throw "Installed backend failed its smoke test." }
}
finally {
    if (Test-Path -LiteralPath $uninstaller) {
        $process = Start-Process -FilePath $uninstaller -ArgumentList @("/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART") -Wait -PassThru
        if ($process.ExitCode -ne 0) { throw "Uninstaller check failed with exit code $($process.ExitCode)." }
    }
}
if (Test-Path -LiteralPath (Join-Path $installFolder "DisWhisper.Companion.exe")) { throw "Uninstaller left the app executable behind." }
Write-Host "Windows installer passed: silent install, independent backend startup/shutdown, and uninstall." -ForegroundColor Green
