; QuickNote Installer — Inno Setup Script
; ติดตั้งไปที่ %LOCALAPPDATA%\Programs\QuickNote\ (ไม่ต้องขอ Admin)

[Setup]
AppName=QuickNote
AppVersion=1.0.1
AppVerName=QuickNote v1.0.1
AppPublisher=Passagain P.
AppPublisherURL=https://github.com/
DefaultDirName={localappdata}\Programs\QuickNote
DefaultGroupName=QuickNote
AllowNoIcons=yes
OutputDir=installer_output
OutputBaseFilename=QuickNote-Setup-v1.0.1
; SetupIconFile=assets/quicknote.ico  (icon not available, use default)
UninstallDisplayIcon={app}\QuickNote.exe
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64

; ไม่ต้องขอ Admin (เพราะติดตั้งไปที่ user folder)
PrivilegesRequiredOverridesAllowed=commandline

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "startupshortcut"; Description: "Create Startup shortcut (auto-launch on Windows start)"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
; Copy main executable
Source: "dist\QuickNote.exe"; DestDir: "{app}"; Flags: ignoreversion
; Copy requirements.txt (optional, for reference)
Source: "requirements.txt"; DestDir: "{app}"; Flags: ignoreversion
; Copy README
Source: "README.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
; Start Menu shortcut
Name: "{group}\QuickNote"; Filename: "{app}\QuickNote.exe"; Comment: "Notes Always on Top"
Name: "{group}\{cm:UninstallProgram,QuickNote}"; Filename: "{uninstallexe}"

; Desktop shortcut (optional, ถ้าผู้ใช้เลือก)
Name: "{userdesktop}\QuickNote"; Filename: "{app}\QuickNote.exe"; Comment: "Notes Always on Top"; Tasks: desktopicon

; Startup folder shortcut (ถ้าผู้ใช้เลือก)
Name: "{userstartup}\QuickNote"; Filename: "{app}\QuickNote.exe"; Comment: "QuickNote — Auto-launch"; Tasks: startupshortcut

[Run]
; เรียก QuickNote หลังติดตั้งเสร็จ (ไม่บังคับ)
Filename: "{app}\QuickNote.exe"; Description: "Launch QuickNote"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; ลบ shortcut ใน Startup folder เวลา uninstall
Type: files; Name: "{userstartup}\QuickNote.lnk"
