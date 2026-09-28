; Inno Setup script for the Windows installer.
; Built by tools/build.py:  iscc /DAppVersion=x.y.z packaging\installer.iss

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{7F3C2B8E-5D14-4E6A-9B0C-3A1F6E2D8C55}
AppName=SPFL Manager
AppVersion={#AppVersion}
AppPublisher=Mike Hellyer
AppPublisherURL=https://github.com/mikehellyer/spfl-manager
DefaultDirName={autopf}\SPFL Manager
DefaultGroupName=SPFL Manager
DisableProgramGroupPage=yes
OutputDir=..\dist
OutputBaseFilename=SPFL-Manager-{#AppVersion}-Windows-Setup
SetupIconFile=icon.ico
UninstallDisplayIcon={app}\SPFL Manager.exe
LicenseFile=..\LICENSE
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequiredOverridesAllowed=dialog

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "..\dist\SPFL Manager\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\SPFL Manager"; Filename: "{app}\SPFL Manager.exe"
Name: "{group}\Uninstall SPFL Manager"; Filename: "{uninstallexe}"
Name: "{autodesktop}\SPFL Manager"; Filename: "{app}\SPFL Manager.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\SPFL Manager.exe"; Description: "{cm:LaunchProgram,SPFL Manager}"; Flags: nowait postinstall skipifsilent
