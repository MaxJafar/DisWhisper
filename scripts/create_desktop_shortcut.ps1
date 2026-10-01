# Create a direct shortcut to the compiled companion without a console window.
[CmdletBinding()]
param(
    [ValidateSet("x64", "ARM64")][string]$Platform = "x64",
    [string]$DesktopDirectory = [Environment]::GetFolderPath("Desktop")
)

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$runtimeId = "win-$($Platform.ToLowerInvariant())"
$executablePath = Join-Path $projectRoot "companion\windows\DisWhisper.Companion\bin\$Platform\Release\net8.0-windows10.0.19041.0\$runtimeId\DisWhisper.Companion.exe"
if (-not (Test-Path -LiteralPath $executablePath -PathType Leaf)) {
    throw "Build the companion first with scripts\setup_companion.ps1 -Platform $Platform."
}
if (-not (Test-Path -LiteralPath $DesktopDirectory -PathType Container)) {
    throw "Desktop directory does not exist: $DesktopDirectory"
}

$shortcutPath = Join-Path $DesktopDirectory "DisWhisper.lnk"
$shell = New-Object -ComObject WScript.Shell
$shortcut = $null
try {
    $shortcut = $shell.CreateShortcut($shortcutPath)
    if ((Test-Path -LiteralPath $shortcutPath) -and $shortcut.TargetPath -ne $executablePath) {
        throw "The desktop already contains a DisWhisper shortcut to a different application: $shortcutPath"
    }
    $shortcut.TargetPath = $executablePath
    $shortcut.WorkingDirectory = $projectRoot
    $shortcut.Description = "Open DisWhisper Companion — models, Discord settings, and transcripts"
    $shortcut.IconLocation = "$executablePath,0"
    $shortcut.Save()
    Write-Host "Desktop shortcut created: $shortcutPath" -ForegroundColor Green
}
finally {
    if ($null -ne $shortcut) { [void][System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($shortcut) }
    [void][System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($shell)
}
