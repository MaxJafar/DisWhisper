[CmdletBinding()]
param(
    [string]$PythonPath = "python",
    [string]$DotnetPath = "dotnet",
    [switch]$SkipInstall
)
$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$buildEnvironment = Join-Path $projectRoot ".cache\package-venv"
$packagePython = Join-Path $buildEnvironment "Scripts\python.exe"
$releaseVersion = [regex]::Match((Get-Content -LiteralPath (Join-Path $projectRoot "pyproject.toml") -Raw), '(?m)^version\s*=\s*"(\d+\.\d+\.\d+)"\s*$').Groups[1].Value
if (-not $releaseVersion) { throw "Invalid project release version." }
$releaseDirectory = Join-Path $projectRoot "dist\DisWhisper-$releaseVersion-windows-x64"
$backendDirectory = Join-Path $projectRoot ".cache\frozen-backend"
$env:DOTNET_CLI_TELEMETRY_OPTOUT = "1"
$env:PYTHONUTF8 = "1"
Push-Location $projectRoot
try {
    if (-not (Test-Path -LiteralPath $packagePython)) {
        & $PythonPath -m venv $buildEnvironment
        if ($LASTEXITCODE -ne 0) { throw "Could not create the build environment. Use Python 3.12 x64." }
    }
    if (-not $SkipInstall) {
        & $packagePython -m pip install --disable-pip-version-check -r requirements-windows.lock
        if ($LASTEXITCODE -ne 0) { throw "Release dependency installation failed." }
        & $packagePython -m pip install --no-deps .
        if ($LASTEXITCODE -ne 0) { throw "Project installation failed." }
    }
    & $packagePython -m pytest tests/ -v
    if ($LASTEXITCODE -ne 0) { throw "Tests failed. Release stopped." }
    # Only remove the verified generated release folder, never app data or source.
    $expectedRelease = [IO.Path]::GetFullPath((Join-Path $projectRoot "dist\DisWhisper-$releaseVersion-windows-x64"))
    if ([IO.Path]::GetFullPath($releaseDirectory) -ne $expectedRelease -or -not $expectedRelease.StartsWith($projectRoot + [IO.Path]::DirectorySeparatorChar)) { throw "Unexpected release output path." }
    if (Test-Path -LiteralPath $releaseDirectory) { Remove-Item -LiteralPath $releaseDirectory -Recurse -Force }
    $appBuildDirectory = Join-Path $projectRoot ".cache\release-app-build\"
    & $DotnetPath publish companion/windows/DisWhisper.Companion/DisWhisper.Companion.csproj -c Release -r win-x64 -p:Platform=x64 --self-contained true -p:WindowsAppSDKSelfContained=true "-p:OutputPath=$appBuildDirectory" -o $releaseDirectory --nologo
    if ($LASTEXITCODE -ne 0) { throw "Windows app publish failed." }
    & $packagePython -m PyInstaller --noconfirm --clean --distpath $backendDirectory --workpath .cache/pyinstaller packaging/backend.spec
    if ($LASTEXITCODE -ne 0) { throw "Backend packaging failed." }
    $targetBackend = Join-Path $releaseDirectory "backend"
    New-Item -ItemType Directory -Path $targetBackend -Force | Out-Null
    Copy-Item -LiteralPath (Join-Path $backendDirectory "diswhisper-backend\diswhisper-backend.exe") -Destination $targetBackend -Force
    Copy-Item -LiteralPath (Join-Path $backendDirectory "diswhisper-backend\_internal") -Destination $targetBackend -Recurse -Force
    Copy-Item -LiteralPath LICENSE, THIRD_PARTY_NOTICES.md -Destination $releaseDirectory -Force
    Copy-Item -LiteralPath docs/windows-quickstart.md -Destination (Join-Path $releaseDirectory "START HERE.md") -Force
    Copy-Item -LiteralPath scripts/portable_shortcut.ps1 -Destination (Join-Path $releaseDirectory "Create desktop shortcut.ps1") -Force
    & $packagePython scripts/collect_licenses.py (Join-Path $releaseDirectory "licenses\python")
    if ($LASTEXITCODE -ne 0) { throw "Dependency license collection failed." }
    $pythonLicense = & $packagePython -c "import sys; from pathlib import Path; print(Path(sys.base_prefix) / 'LICENSE.txt')"
    if (-not (Test-Path -LiteralPath $pythonLicense)) { throw "Python license file is missing." }
    Copy-Item -LiteralPath $pythonLicense -Destination (Join-Path $releaseDirectory "licenses\python\PYTHON_LICENSE.txt") -Force
    & $packagePython scripts/collect_native_sources.py (Join-Path $releaseDirectory "licenses\native") (Join-Path $projectRoot "dist\DisWhisper-$releaseVersion-windows-third-party-source.zip")
    if ($LASTEXITCODE -ne 0) { throw "Native-library source or notice collection failed." }
    Copy-Item -LiteralPath (Join-Path $projectRoot ".cache\vendor-sources\GPL-3.0.txt") -Destination (Join-Path $releaseDirectory "COPYING.GPL3.txt") -Force
    $nugetPackages = Join-Path $env:USERPROFILE ".nuget\packages"
    foreach ($package in @("microsoft.windowsappsdk", "microsoft.windows.sdk.buildtools", "microsoft.windows.sdk.net.ref", "microsoft.graphics.win2d", "communitytoolkit.mvvm", "communitytoolkit.winui.ui.controls", "microsoft.netcore.app.runtime.win-x64", "microsoft.windowsdesktop.app.runtime.win-x64")) {
        $folder = Join-Path $nugetPackages $package
        if (-not (Test-Path -LiteralPath $folder)) { continue }
        $target = Join-Path $releaseDirectory "licenses\dotnet\$package"
        New-Item -ItemType Directory -Path $target -Force | Out-Null
        Get-ChildItem -LiteralPath $folder -Recurse -File | Where-Object { $_.Name -match '^(LICENSE|NOTICE|ThirdPartyNotices|.*\.nuspec)' } | ForEach-Object {
            $relative = $_.FullName.Substring($folder.Length).TrimStart('\').Replace('\', '_')
            Copy-Item -LiteralPath $_.FullName -Destination (Join-Path $target $relative) -Force
        }
    }
    $archive = "$releaseDirectory.zip"
    & $packagePython scripts/archive_release.py $releaseDirectory $archive
    if ($LASTEXITCODE -ne 0) { throw "Archive creation failed." }
    $checksum = (Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant()
    "$checksum  $([IO.Path]::GetFileName($archive))" | Set-Content -LiteralPath "$archive.sha256" -Encoding ascii
    & (Join-Path $PSScriptRoot "build_windows_installer.ps1") -Version $releaseVersion
    Write-Host "Release ready: $archive" -ForegroundColor Green
}
finally { Pop-Location }
