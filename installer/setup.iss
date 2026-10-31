; setup.iss - Inno Setup script for the Dialogue Boost Player installer.
; Build it with "python build.py" (which passes the version), or open this file in Inno Setup.
;
; What the installer does:
;   * lets the user install for everyone (Program Files) or just for themselves
;   * copies the app, creates a Start menu shortcut and a desktop shortcut
;   * adds the player to the "Open with" menu of video files (doesn't steal the default player)
;   * registers a normal uninstaller in Settings > Apps

#define AppName "Dialogue Boost Player"
#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif
#define AppPublisher "Tamim Ahmed Rijan"
#define AppURL "https://github.com/tamimrijan"
#define AppInstagram "https://www.instagram.com/tamim_ahmed_rijan/"
#ifndef AppExeName
  #define AppExeName "DialogueBoostPlayer.exe"
#endif
#ifndef SourceDir
  #define SourceDir "..\dist\DialogueBoostPlayer"
#endif
#define ProgId "DialogueBoostPlayer.Media"
; Must match MUTEX_NAME in app_info.py: the running app holds it, so (un)install can detect it.
#define AppMutexName "TamimRijan.DialogueBoostPlayer.Running"
; AppId identifies this app for updates/uninstall. Never change it after the first release.
; (It can be overridden only to build a separate test installer.)
#ifndef AppIdValue
  #define AppIdValue "{{8F3C2A1E-6B4D-4E2A-9C1F-3D5B7A9E0C21}"
#endif
#ifndef OutputName
  #define OutputName "DialogueBoostPlayer_Setup_" + AppVersion
#endif

[Setup]
AppId={#AppIdValue}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
AppUpdatesURL={#AppURL}
AppCopyright=Copyright (C) 2026 {#AppPublisher}
VersionInfoVersion={#AppVersion}
VersionInfoCompany={#AppPublisher}
VersionInfoDescription={#AppName} Setup
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
; Show the Welcome page (it has the author's name and links). Inno Setup hides it by default.
DisableWelcomePage=no
; Ask "install for all users or only for me?" (all users needs admin rights)
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
WizardStyle=modern dark
WizardImageFile=..\assets\wizard_large_100.png,..\assets\wizard_large_150.png,..\assets\wizard_large_200.png,..\assets\wizard_large_250.png
WizardSmallImageFile=..\assets\wizard_small_100.png,..\assets\wizard_small_150.png,..\assets\wizard_small_200.png,..\assets\wizard_small_250.png
SetupIconFile=..\assets\app.ico
UninstallDisplayIcon={app}\{#AppExeName}
UninstallDisplayName={#AppName}
OutputDir=..\release
OutputBaseFilename={#OutputName}
Compression=lzma2/ultra64
SolidCompression=yes
ChangesAssociations=yes
CloseApplications=yes

[Messages]
WelcomeLabel1=Welcome to the [name] Setup
WelcomeLabel2=This will install [name/ver] on your computer.%n%nA video player that makes movie dialogue clear without blowing up the music and explosions.%n%nBuilt by {#AppPublisher}%nGitHub: github.com/tamimrijan%nInstagram: @tamim_ahmed_rijan%n%nIt is recommended that you close all other applications before continuing.
FinishedLabel=Setup has finished installing [name] on your computer. Open it from the desktop or the Start menu.%n%nThanks for using it!%n- {#AppPublisher}

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "openwith"; Description: "Add to the ""Open with"" menu for video files"; GroupDescription: "File types:"

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Comment: "Play videos with Dialogue Boost"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Comment: "Play videos with Dialogue Boost"; Tasks: desktopicon

[Registry]
; The app itself, so Windows knows its name and which files it can open.
Root: HKA; Subkey: "Software\Classes\Applications\{#AppExeName}"; ValueType: string; ValueName: "FriendlyAppName"; ValueData: "{#AppName}"; Flags: uninsdeletekey; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\Applications\{#AppExeName}\DefaultIcon"; ValueType: string; ValueData: "{app}\{#AppExeName},0"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\Applications\{#AppExeName}\shell\open\command"; ValueType: string; ValueData: """{app}\{#AppExeName}"" ""%1"""; Tasks: openwith
; A "ProgID" = a named file type our app can open.
Root: HKA; Subkey: "Software\Classes\{#ProgId}"; ValueType: string; ValueData: "Video file"; Flags: uninsdeletekey; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\{#ProgId}\DefaultIcon"; ValueType: string; ValueData: "{app}\{#AppExeName},0"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\{#ProgId}\shell\open\command"; ValueType: string; ValueData: """{app}\{#AppExeName}"" ""%1"""; Tasks: openwith
; Add the ProgID to each extension's "Open with" list. This does NOT change the default player.
Root: HKA; Subkey: "Software\Classes\.mp4\OpenWithProgids"; ValueType: string; ValueName: "{#ProgId}"; ValueData: ""; Flags: uninsdeletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.mkv\OpenWithProgids"; ValueType: string; ValueName: "{#ProgId}"; ValueData: ""; Flags: uninsdeletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.avi\OpenWithProgids"; ValueType: string; ValueName: "{#ProgId}"; ValueData: ""; Flags: uninsdeletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.mov\OpenWithProgids"; ValueType: string; ValueName: "{#ProgId}"; ValueData: ""; Flags: uninsdeletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.webm\OpenWithProgids"; ValueType: string; ValueName: "{#ProgId}"; ValueData: ""; Flags: uninsdeletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.wmv\OpenWithProgids"; ValueType: string; ValueName: "{#ProgId}"; ValueData: ""; Flags: uninsdeletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.flv\OpenWithProgids"; ValueType: string; ValueName: "{#ProgId}"; ValueData: ""; Flags: uninsdeletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.m4v\OpenWithProgids"; ValueType: string; ValueName: "{#ProgId}"; ValueData: ""; Flags: uninsdeletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.mpg\OpenWithProgids"; ValueType: string; ValueName: "{#ProgId}"; ValueData: ""; Flags: uninsdeletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.mpeg\OpenWithProgids"; ValueType: string; ValueName: "{#ProgId}"; ValueData: ""; Flags: uninsdeletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.ts\OpenWithProgids"; ValueType: string; ValueName: "{#ProgId}"; ValueData: ""; Flags: uninsdeletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.m2ts\OpenWithProgids"; ValueType: string; ValueName: "{#ProgId}"; ValueData: ""; Flags: uninsdeletevalue; Tasks: openwith

[Run]
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent
Filename: "{#AppURL}"; Description: "Visit {#AppPublisher} on GitHub"; Flags: postinstall shellexec skipifsilent unchecked nowait

[UninstallDelete]
; Remove the whole install folder, including anything created after installing.
Type: filesandordirs; Name: "{app}"

[Code]
{ Uninstall step 1: if the player is running, its files can't be deleted.
  Offer to close it (silent uninstalls close it automatically). }
function InitializeUninstall(): Boolean;
var
  ResultCode: Integer;
begin
  Result := True;
  if CheckForMutexes('{#AppMutexName}') then
  begin
    if UninstallSilent or (MsgBox('{#AppName} is still running.' + #13#10 + #13#10 +
        'Close it and continue uninstalling?', mbConfirmation, MB_YESNO) = IDYES) then
    begin
      Exec(ExpandConstant('{sys}\taskkill.exe'), '/F /IM {#AppExeName}', '', SW_HIDE,
           ewWaitUntilTerminated, ResultCode);
      Sleep(1000);   { give Windows a moment to release the files }
    end
    else
      Result := False;   { the user said no: cancel, nothing is removed }
  end;
end;

{ Uninstall step 2: after the program files are gone, offer to delete the user's
  settings and resume positions too (%APPDATA%\DialogueBoostPlayer). }
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  SettingsDir: String;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    SettingsDir := ExpandConstant('{userappdata}\DialogueBoostPlayer');
    if DirExists(SettingsDir) then
      { (no line may start with "#" here: Inno's preprocessor would read it as a directive) }
      if UninstallSilent or (MsgBox('Do you also want to delete your settings and saved resume positions?' + #13#10#13#10 + SettingsDir + #13#10#13#10 + 'Choose No to keep them for a future reinstall.', mbConfirmation, MB_YESNO) = IDYES) then
        DelTree(SettingsDir, True, True, True);
  end;
end;
