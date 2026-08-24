; Inno Setup Script for QuickNote v2.9.43
; This script creates a Windows installer for QuickNote
; Updated: 2026-08-24

[Setup]
AppName=QuickNote
AppVersion=2.9.43
AppPublisher=Passagain P.
DefaultDirName={autopf}\QuickNote
DefaultGroupName=QuickNote
AllowNoIcons=yes
OutputDir=installer_output
OutputBaseFilename=QuickNote_v2.9.43_Setup
Compression=lzma
SolidCompression=yes
UninstallDisplayIcon={app}\QuickNote.exe
VersionInfoVersion=2.9.43.0
VersionInfoCompany=Passagain P.
VersionInfoProductName=QuickNote
VersionInfoProductVersion=2.9.43.0

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "dist\QuickNote_v2.9.43.exe"; DestDir: "{app}"; DestName: "QuickNote.exe"; Flags: ignoreversion
Source: "README.md"; DestDir: "{app}"; Flags: ignoreversion isreadme
Source: "CLAUDE.md"; DestDir: "{app}\docs"; Flags: ignoreversion

[Icons]
Name: "{group}\QuickNote"; Filename: "{app}\QuickNote.exe"; WorkingDir: "{app}"
Name: "{group}\{cm:UninstallProgram,QuickNote}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\QuickNote"; Filename: "{app}\QuickNote.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\QuickNote.exe"; Description: "{cm:LaunchProgram,QuickNote}"; Flags: nowait postinstall skipifsilent
