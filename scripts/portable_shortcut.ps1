# Run from the extracted release folder. The application opens without a console.
$ErrorActionPreference = "Stop"
$executable = Join-Path $PSScriptRoot "DisWhisper.Companion.exe"
if (-not (Test-Path -LiteralPath $executable)) { throw "Extract the entire release before creating its shortcut." }
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut((Join-Path ([Environment]::GetFolderPath("Desktop")) "DisWhisper.lnk"))
try {
    $shortcut.TargetPath = $executable
    $shortcut.WorkingDirectory = $PSScriptRoot
    $shortcut.Description = "DisWhisper - Free local Discord transcription"
    $shortcut.IconLocation = "$executable,0"
    $shortcut.Save()
    Write-Host "DisWhisper desktop shortcut created."
}
finally {
    [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($shortcut)
    [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($shell)
}
