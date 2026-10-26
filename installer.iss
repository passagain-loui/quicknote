; Inno Setup Script for QuickNote v3.0.1
; This script creates a Windows installer for QuickNote
; Updated: 2026-08-26

[Setup]
AppName=QuickNote
AppVersion=3.0.1
AppPublisher=Passagain P.
DefaultDirName={autopf}\QuickNote
DefaultGroupName=QuickNote
AllowNoIcons=yes
OutputDir=installer_output
OutputBaseFilename=QuickNote_v3.0.1_Setup
Compression=lzma
SolidCompression=yes
SetupIconFile=assets\icon.ico
UninstallDisplayIcon={app}\QuickNote.exe
VersionInfoVersion=3.0.1.0
VersionInfoCompany=Passagain P.
VersionInfoProductName=QuickNote
VersionInfoProductVersion=3.0.1.0

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "dist\QuickNote_v3.0.1.exe"; DestDir: "{app}"; DestName: "QuickNote.exe"; Flags: ignoreversion
Source: "README.md"; DestDir: "{app}"; Flags: ignoreversion isreadme
Source: "CLAUDE.md"; DestDir: "{app}\docs"; Flags: ignoreversion

[Icons]
Name: "{group}\QuickNote"; Filename: "{app}\QuickNote.exe"; WorkingDir: "{app}"; AppUserModelID: "PassagainP.QuickNote"
Name: "{group}\{cm:UninstallProgram,QuickNote}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\QuickNote"; Filename: "{app}\QuickNote.exe"; WorkingDir: "{app}"; AppUserModelID: "PassagainP.QuickNote"; Tasks: desktopicon

[Run]
Filename: "{app}\QuickNote.exe"; Description: "{cm:LaunchProgram,QuickNote}"; Flags: nowait postinstall skipifsilent
