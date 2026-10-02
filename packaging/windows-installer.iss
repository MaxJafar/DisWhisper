; Compile with scripts/build_windows_installer.ps1 after the portable build.
#ifndef AppVersion
  #error AppVersion is required
#endif
#ifndef ReleaseFolder
  #error ReleaseFolder is required
#endif
#ifndef ReleaseOutput
  #error ReleaseOutput is required
#endif

[Setup]
AppId=DisWhisper.Companion
AppName=DisWhisper
AppVersion={#AppVersion}
AppPublisher=MaxJafar
AppPublisherURL=https://github.com/MaxJafar/DisWhisper
AppSupportURL=https://github.com/MaxJafar/DisWhisper/issues
DefaultDirName={localappdata}\Programs\DisWhisper
DefaultGroupName=DisWhisper
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.19041
UninstallDisplayIcon={app}\DisWhisper.Companion.exe
SetupIconFile=..\companion\windows\DisWhisper.Companion\Assets\DisWhisper.ico
OutputDir={#ReleaseOutput}
OutputBaseFilename=DisWhisper-{#AppVersion}-windows-x64-setup
Compression=lzma2/fast
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Shortcuts:"; Flags: unchecked

[Files]
Source: "{#ReleaseFolder}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\DisWhisper"; Filename: "{app}\DisWhisper.Companion.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\DisWhisper"; Filename: "{app}\DisWhisper.Companion.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\DisWhisper.Companion.exe"; Description: "Open DisWhisper"; Flags: nowait postinstall skipifsilent
