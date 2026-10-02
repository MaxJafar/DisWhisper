[CmdletBinding()]
param([Parameter(Mandatory)][string]$Version)
$ErrorActionPreference = "Stop"
if ($Version -notmatch '^\d+\.\d+\.\d+$') { throw "Invalid project release version." }
$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$releaseFolder = Join-Path $projectRoot "dist\DisWhisper-$Version-windows-x64"
$releaseOutput = Join-Path $projectRoot "dist"
if (-not (Test-Path -LiteralPath (Join-Path $releaseFolder "DisWhisper.Companion.exe"))) { throw "Build the portable Windows app first." }
$compiler = Get-Command ISCC.exe -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source
if (-not $compiler) {
    $compiler = Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe"
}
if (-not (Test-Path -LiteralPath $compiler)) { throw "Install Inno Setup 6.3 or newer to create the Windows installer." }
& $compiler "/DAppVersion=$Version" "/DReleaseFolder=$releaseFolder" "/DReleaseOutput=$releaseOutput" (Join-Path $projectRoot "packaging\windows-installer.iss")
if ($LASTEXITCODE -ne 0) { throw "Windows installer compilation failed." }
$installer = Join-Path $releaseOutput "DisWhisper-$Version-windows-x64-setup.exe"
$checksum = (Get-FileHash -LiteralPath $installer -Algorithm SHA256).Hash.ToLowerInvariant()
"$checksum  $([IO.Path]::GetFileName($installer))" | Set-Content -LiteralPath "$installer.sha256" -Encoding ascii
Write-Host "Windows installer ready: $installer" -ForegroundColor Green
