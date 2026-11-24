#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{DBDF4D33-318F-43EC-B146-D2ABBAFAD301}
AppName=IdleDown
AppVersion={#AppVersion}
AppPublisher=JUSSI-G
AppPublisherURL=https://github.com/JUSSI-G/IdleDown
AppSupportURL=https://github.com/JUSSI-G/IdleDown/issues
DefaultDirName={autopf}\IdleDown
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=installer-output
OutputBaseFilename=IdleDown-Setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
SetupIconFile=assets\IdleDown.ico
UninstallDisplayIcon={app}\IdleDown.exe
CloseApplications=yes

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "dist\IdleDown.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\IdleDown"; Filename: "{app}\IdleDown.exe"
Name: "{autodesktop}\IdleDown"; Filename: "{app}\IdleDown.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\IdleDown.exe"; Description: "{cm:LaunchProgram,IdleDown}"; Flags: nowait postinstall skipifsilent
