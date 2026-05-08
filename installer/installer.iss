; ============================================================
;  installer/installer.iss — Inno Setup Installer Script
;  SQLite Manager Professional Database Manager
;  Requires: Inno Setup 6.x (https://jrsoftware.org/isinfo.php)
;
;  Run:  ISCC installer\installer.iss
; ============================================================

#define MyAppName      "SQLite Manager"
#define MyAppVersion   "1.0.0"
#define MyAppPublisher "SQLite Manager Team"
#define MyAppURL       "https://github.com/your-username/sqlite-manager"
#define MyAppExeName   "SQLiteManager.exe"
#define MyAppId        "{{8F3A1C2D-4E5B-4F6A-9B8C-1D2E3F4A5B6C}"
#define BuildDir       "..\dist\SQLiteManager"
#define OutputDir      "..\releases"

[Setup]
; App identification
AppId={#MyAppId}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}/issues
AppUpdatesURL={#MyAppURL}/releases

; Install location
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

; Output
OutputDir={#OutputDir}
OutputBaseFilename=SQLiteManagerSetup_{#MyAppVersion}
SetupIconFile=icons\app.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName}

; UI
WizardStyle=modern
WizardResizable=yes
ShowLanguageDialog=auto

; Compression
Compression=lzma2/ultra64
SolidCompression=yes
InternalCompressLevel=ultra64
LZMANumBlockThreads=4

; Windows version requirement
MinVersion=10.0.17763

; Versioning
VersionInfoVersion={#MyAppVersion}
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription={#MyAppName} Setup
VersionInfoCopyright=Copyright (C) 2025 {#MyAppPublisher}
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion={#MyAppVersion}

; Misc
ChangesAssociations=yes
RestartIfNeededByRun=no
DisableWelcomePage=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon";    Description: "{cm:CreateDesktopIcon}";    GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "startmenuicon";  Description: "Create Start Menu shortcut"; GroupDescription: "{cm:AdditionalIcons}"; Flags: checked
Name: "fileassoc_db";   Description: "Associate .db files with {#MyAppName}";   GroupDescription: "File Associations"; Flags: unchecked
Name: "fileassoc_sqlite"; Description: "Associate .sqlite files with {#MyAppName}"; GroupDescription: "File Associations"; Flags: unchecked
Name: "fileassoc_sqlite3"; Description: "Associate .sqlite3 files with {#MyAppName}"; GroupDescription: "File Associations"; Flags: unchecked

[Files]
; Main application (one-dir build)
Source: "{#BuildDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

; Ensure exe is marked as non-read-only
Source: "{#BuildDir}\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion

[Dirs]
; Create user data directories on first install
Name: "{localappdata}\SQLiteManager"
Name: "{localappdata}\SQLiteManager\backups"
Name: "{localappdata}\SQLiteManager\exports"
Name: "{localappdata}\SQLiteManager\crashes"
Name: "{localappdata}\SQLiteManager\logs"

[Icons]
; Start menu
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"

; Desktop (optional task)
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Registry]
; File associations — .db
Root: HKA; Subkey: "Software\Classes\.db";                                    ValueType: string; ValueName: ""; ValueData: "SQLiteManagerDB";    Flags: uninsdeletevalue; Tasks: fileassoc_db
Root: HKA; Subkey: "Software\Classes\SQLiteManagerDB";                        ValueType: string; ValueName: ""; ValueData: "SQLite Database";    Flags: uninsdeletekey; Tasks: fileassoc_db
Root: HKA; Subkey: "Software\Classes\SQLiteManagerDB\DefaultIcon";            ValueType: string; ValueName: ""; ValueData: "{app}\{#MyAppExeName},0"; Tasks: fileassoc_db
Root: HKA; Subkey: "Software\Classes\SQLiteManagerDB\shell\open\command";     ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""; Tasks: fileassoc_db

; File associations — .sqlite
Root: HKA; Subkey: "Software\Classes\.sqlite";                                ValueType: string; ValueName: ""; ValueData: "SQLiteManagerDB";    Flags: uninsdeletevalue; Tasks: fileassoc_sqlite
Root: HKA; Subkey: "Software\Classes\.sqlite3";                               ValueType: string; ValueName: ""; ValueData: "SQLiteManagerDB";    Flags: uninsdeletevalue; Tasks: fileassoc_sqlite3

; App registration for "Open With"
Root: HKA; Subkey: "Software\Classes\Applications\{#MyAppExeName}";           ValueType: string; ValueName: "FriendlyAppName"; ValueData: "{#MyAppName}"
Root: HKA; Subkey: "Software\Classes\Applications\{#MyAppExeName}\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""

; Add to Programs list
Root: HKA; Subkey: "Software\{#MyAppPublisher}\{#MyAppName}"; ValueType: string; ValueName: "InstallPath"; ValueData: "{app}"; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\{#MyAppPublisher}\{#MyAppName}"; ValueType: string; ValueName: "Version";     ValueData: "{#MyAppVersion}"

[Run]
; Launch app after install (optional)
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{localappdata}\SQLiteManager\crashes"
Type: filesandordirs; Name: "{localappdata}\SQLiteManager\logs"

[Code]
// ── Upgrade detection: remove old version first ──────────────────────────────
function GetUninstallString(): String;
var
  sUnInstPath: String;
  sUnInstallString: String;
begin
  sUnInstPath := ExpandConstant('Software\Microsoft\Windows\CurrentVersion\Uninstall\{#MyAppId}_is1');
  sUnInstallString := '';
  if not RegQueryStringValue(HKLM, sUnInstPath, 'UninstallString', sUnInstallString) then
    RegQueryStringValue(HKCU, sUnInstPath, 'UninstallString', sUnInstallString);
  Result := sUnInstallString;
end;

function IsUpgrade(): Boolean;
begin
  Result := (GetUninstallString() <> '');
end;

function UnInstallOldVersion(): Integer;
var
  sUnInstallString: String;
  iResultCode: Integer;
begin
  Result := 0;
  sUnInstallString := GetUninstallString();
  if sUnInstallString <> '' then begin
    sUnInstallString := RemoveQuotes(sUnInstallString);
    if Exec(sUnInstallString, '/SILENT /NORESTART /SUPPRESSMSGBOXES','',SW_HIDE, ewWaitUntilTerminated, iResultCode) then
      Result := 3
    else
      Result := 2;
  end else
    Result := 1;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if (CurStep = ssInstall) then begin
    if (IsUpgrade()) then begin
      UnInstallOldVersion();
    end;
  end;
end;

// ── Minimum Windows 10 check ─────────────────────────────────────────────────
function InitializeSetup: Boolean;
begin
  Result := True;
  if not IsWin64 then begin
    MsgBox('SQLite Manager requires a 64-bit version of Windows 10 or later.', mbError, MB_OK);
    Result := False;
  end;
end;
