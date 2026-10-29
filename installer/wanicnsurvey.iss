; SPDX-License-Identifier: GPL-3.0-or-later
; WANICNSURVEY — one Thai installer for the start screen, CAD (2D) and 3D.
;
; Expects the three PyInstaller bundles next to the repository root:
;   dist\launcher\   (wanicnsurvey.exe)
;   dist\ingecad\    (ingecad.exe)
;   dist\ingetrazo\  (ingetrazo.exe)
; Build:  ISCC.exe /DMyAppVersion=2026.10.28 installer\wanicnsurvey.iss
; Needs Inno Setup 6.5 or newer (for Thai.isl).

#define MyAppName "WANICNSURVEY"
#define MyAppPublisher "นายเวนิช ธัมมะวงษ์"
#define LauncherExe "launcher\wanicnsurvey.exe"
#define CadExe "cad\ingecad.exe"
#define ModelExe "3d\ingetrazo.exe"

#ifndef MyAppVersion
  #define MyAppVersion "0.0.0-dev"
#endif

[Setup]
AppId={{3F6A2C1E-8B7D-4E59-9A0C-5D2B71E4A6F3}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} เวอร์ชัน {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppCopyright=Copyright (C) 2569 (2026) นายเวนิช ธัมมะวงษ์ วิศวกรสำรวจ
VersionInfoVersion=1.0.0.0
VersionInfoProductName={#MyAppName}
VersionInfoDescription=WANICNSURVEY Setup

DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

LicenseFile=license-th.txt
OutputDir=..\dist
OutputBaseFilename=wanicnsurvey-setup-{#MyAppVersion}

WizardStyle=modern
WizardImageFile=wizard-large.bmp,wizard-large-2x.bmp
WizardSmallImageFile=wizard-small.bmp,wizard-small-2x.bmp
SetupIconFile=..\branding\wanicnsurvey.ico
UninstallDisplayIcon={app}\{#LauncherExe}
ShowLanguageDialog=no
ChangesAssociations=yes
Compression=lzma2/max
SolidCompression=yes

[Languages]
Name: "thai"; MessagesFile: "Thai.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
thai.HowTo=วิธีใช้งาน
thai.FileAssoc=เปิดไฟล์ด้วยการดับเบิลคลิก
thai.IgzAssoc=ให้ดับเบิลคลิกไฟล์ .igz แล้วเปิดด้วย WANICNSURVEY 3D
thai.DwgAssoc=ให้ดับเบิลคลิกไฟล์ .dwg แล้วเปิดด้วย WANICNSURVEY CAD
thai.DxfAssoc=ให้ดับเบิลคลิกไฟล์ .dxf แล้วเปิดด้วย WANICNSURVEY CAD
thai.DesktopIcon=สร้างไอคอนบนหน้าจอเดสก์ท็อป
thai.IgzDoc=โมเดล 3 มิติ (WANICNSURVEY 3D)
thai.DwgDoc=แบบ AutoCAD (WANICNSURVEY CAD)
thai.DxfDoc=แบบ DXF (WANICNSURVEY CAD)
thai.Launch=เปิด WANICNSURVEY ทันที
english.HowTo=Options
english.FileAssoc=Open on double-click
english.IgzAssoc=Open .igz files with WANICNSURVEY 3D
english.DwgAssoc=Open .dwg files with WANICNSURVEY CAD
english.DxfAssoc=Open .dxf files with WANICNSURVEY CAD
english.DesktopIcon=Create a desktop icon
english.IgzDoc=3D model (WANICNSURVEY 3D)
english.DwgDoc=AutoCAD drawing (WANICNSURVEY CAD)
english.DxfDoc=DXF drawing (WANICNSURVEY CAD)
english.Launch=Start WANICNSURVEY now

[Tasks]
Name: "desktopicon"; Description: "{cm:DesktopIcon}"; GroupDescription: "{cm:HowTo}"
Name: "igzassoc"; Description: "{cm:IgzAssoc}"; GroupDescription: "{cm:FileAssoc}"
Name: "dwgassoc"; Description: "{cm:DwgAssoc}"; GroupDescription: "{cm:FileAssoc}"; Flags: unchecked
Name: "dxfassoc"; Description: "{cm:DxfAssoc}"; GroupDescription: "{cm:FileAssoc}"; Flags: unchecked

[Files]
Source: "..\dist\launcher\*"; DestDir: "{app}\launcher"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\dist\ingecad\*"; DestDir: "{app}\cad"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\dist\ingetrazo\*"; DestDir: "{app}\3d"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\branding\wanicnsurvey.ico"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\branding\wanicnsurvey-cad.ico"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\branding\wanicnsurvey-3d.ico"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\LICENSE"; DestDir: "{app}"; DestName: "LICENSE.txt"; Flags: ignoreversion
Source: "license-th.txt"; DestDir: "{app}"; DestName: "อ่านก่อน-ข้อตกลง.txt"; Flags: ignoreversion
Source: "..\NOTICE.md"; DestDir: "{app}"; DestName: "ลิขสิทธิ์-NOTICE.txt"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#MyAppName}\WANICNSURVEY"; Filename: "{app}\{#LauncherExe}"; IconFilename: "{app}\wanicnsurvey.ico"
Name: "{autoprograms}\{#MyAppName}\WANICNSURVEY CAD (2 มิติ)"; Filename: "{app}\{#CadExe}"; IconFilename: "{app}\wanicnsurvey-cad.ico"
Name: "{autoprograms}\{#MyAppName}\WANICNSURVEY 3D"; Filename: "{app}\{#ModelExe}"; IconFilename: "{app}\wanicnsurvey-3d.ico"
Name: "{autodesktop}\WANICNSURVEY"; Filename: "{app}\{#LauncherExe}"; IconFilename: "{app}\wanicnsurvey.ico"; Tasks: desktopicon

[Registry]
; .igz -> WANICNSURVEY 3D
Root: HKA; Subkey: "Software\Classes\WANICNSURVEY.igz"; ValueType: string; ValueData: "{cm:IgzDoc}"; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\WANICNSURVEY.igz\DefaultIcon"; ValueType: string; ValueData: "{app}\wanicnsurvey-3d.ico,0"
Root: HKA; Subkey: "Software\Classes\WANICNSURVEY.igz\shell\open\command"; ValueType: string; ValueData: """{app}\{#ModelExe}"" ""%1"""
Root: HKA; Subkey: "Software\Classes\.igz\OpenWithProgids"; ValueType: string; ValueName: "WANICNSURVEY.igz"; ValueData: ""; Flags: uninsdeletevalue
Root: HKA; Subkey: "Software\Classes\.igz"; ValueType: string; ValueData: "WANICNSURVEY.igz"; Tasks: igzassoc; Flags: uninsdeletevalue
; .dwg / .dxf -> WANICNSURVEY CAD (always offered in "Open with", default only when ticked)
Root: HKA; Subkey: "Software\Classes\WANICNSURVEY.dwg"; ValueType: string; ValueData: "{cm:DwgDoc}"; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\WANICNSURVEY.dwg\DefaultIcon"; ValueType: string; ValueData: "{app}\wanicnsurvey-cad.ico,0"
Root: HKA; Subkey: "Software\Classes\WANICNSURVEY.dwg\shell\open\command"; ValueType: string; ValueData: """{app}\{#CadExe}"" ""%1"""
Root: HKA; Subkey: "Software\Classes\.dwg\OpenWithProgids"; ValueType: string; ValueName: "WANICNSURVEY.dwg"; ValueData: ""; Flags: uninsdeletevalue
Root: HKA; Subkey: "Software\Classes\.dwg"; ValueType: string; ValueData: "WANICNSURVEY.dwg"; Tasks: dwgassoc; Flags: uninsdeletevalue
Root: HKA; Subkey: "Software\Classes\WANICNSURVEY.dxf"; ValueType: string; ValueData: "{cm:DxfDoc}"; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\WANICNSURVEY.dxf\DefaultIcon"; ValueType: string; ValueData: "{app}\wanicnsurvey-cad.ico,0"
Root: HKA; Subkey: "Software\Classes\WANICNSURVEY.dxf\shell\open\command"; ValueType: string; ValueData: """{app}\{#CadExe}"" ""%1"""
Root: HKA; Subkey: "Software\Classes\.dxf\OpenWithProgids"; ValueType: string; ValueName: "WANICNSURVEY.dxf"; ValueData: ""; Flags: uninsdeletevalue
Root: HKA; Subkey: "Software\Classes\.dxf"; ValueType: string; ValueData: "WANICNSURVEY.dxf"; Tasks: dxfassoc; Flags: uninsdeletevalue

[Run]
Filename: "{app}\{#LauncherExe}"; Description: "{cm:Launch}"; Flags: nowait postinstall skipifsilent
