; SPDX-License-Identifier: GPL-3.0-or-later
; พัสดุเวนิช (VENIT SUPPLY) — Thai installer.
; Expects the PyInstaller bundle at venitsupply\dist\venitsupply\ (venitsupply.exe).
; Build (from venitsupply\):  ISCC.exe /DMyAppVersion=2026.11.13.3 installer\venitsupply.iss
; Needs Inno Setup 6.5 or newer (Thai.isl is shared with the WANICNSURVEY installer).

#define MyAppName "VENIT SUPPLY"
#define MyAppNameTh "พัสดุเวนิช"
#define MyAppPublisher "นายเวนิช ธัมมะวงษ์"
#define MyExe "venitsupply.exe"

#ifndef MyAppVersion
  #define MyAppVersion "0.0.0-dev"
#endif

[Setup]
AppId={{8C1D5E7A-2F43-4B96-A1E0-7D3C59B2E461}
AppName={#MyAppNameTh} ({#MyAppName})
AppVersion={#MyAppVersion}
AppVerName={#MyAppNameTh} ({#MyAppName}) เวอร์ชัน {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppCopyright=Copyright (C) 2569 (2026) นายเวนิช ธัมมะวงษ์ วิศวกรสำรวจ
VersionInfoVersion=1.0.0.0
VersionInfoProductName={#MyAppName}
VersionInfoDescription=VENIT SUPPLY Setup

DefaultDirName={autopf}\VenitSupply
DefaultGroupName={#MyAppNameTh}
DisableProgramGroupPage=yes
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

LicenseFile=license-th.txt
OutputDir=..\dist
OutputBaseFilename=venitsupply-setup-{#MyAppVersion}

WizardStyle=modern
SetupIconFile=..\assets\venitsupply.ico
UninstallDisplayIcon={app}\{#MyExe}
ShowLanguageDialog=no
ChangesAssociations=yes
Compression=lzma2/max
SolidCompression=yes

[Languages]
Name: "thai"; MessagesFile: "..\..\installer\Thai.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
thai.HowTo=ตัวเลือก
thai.DesktopIcon=สร้างไอคอนบนหน้าจอเดสก์ท็อป
thai.VsdbAssoc=ให้ดับเบิลคลิกไฟล์ข้อมูลพัสดุ .vsdb แล้วเปิดด้วยพัสดุเวนิช
thai.VsdbDoc=ข้อมูลพัสดุ (พัสดุเวนิช)
thai.Launch=เปิดพัสดุเวนิชทันที
english.HowTo=Options
english.DesktopIcon=Create a desktop icon
english.VsdbAssoc=Open .vsdb supply files with VENIT SUPPLY
english.VsdbDoc=Supply data (VENIT SUPPLY)
english.Launch=Start VENIT SUPPLY now

[Tasks]
Name: "desktopicon"; Description: "{cm:DesktopIcon}"; GroupDescription: "{cm:HowTo}"
Name: "vsdbassoc"; Description: "{cm:VsdbAssoc}"; GroupDescription: "{cm:HowTo}"

[Files]
Source: "..\dist\venitsupply\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\assets\venitsupply.ico"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\LICENSE"; DestDir: "{app}"; DestName: "LICENSE.txt"; Flags: ignoreversion
Source: "license-th.txt"; DestDir: "{app}"; DestName: "อ่านก่อน-ข้อตกลง.txt"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#MyAppNameTh}"; Filename: "{app}\{#MyExe}"; IconFilename: "{app}\venitsupply.ico"
Name: "{autodesktop}\{#MyAppNameTh}"; Filename: "{app}\{#MyExe}"; IconFilename: "{app}\venitsupply.ico"; Tasks: desktopicon

[Registry]
Root: HKA; Subkey: "Software\Classes\VenitSupply.vsdb"; ValueType: string; ValueData: "{cm:VsdbDoc}"; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\VenitSupply.vsdb\DefaultIcon"; ValueType: string; ValueData: "{app}\venitsupply.ico,0"
Root: HKA; Subkey: "Software\Classes\VenitSupply.vsdb\shell\open\command"; ValueType: string; ValueData: """{app}\{#MyExe}"" ""%1"""
Root: HKA; Subkey: "Software\Classes\.vsdb\OpenWithProgids"; ValueType: string; ValueName: "VenitSupply.vsdb"; ValueData: ""; Flags: uninsdeletevalue
Root: HKA; Subkey: "Software\Classes\.vsdb"; ValueType: string; ValueData: "VenitSupply.vsdb"; Tasks: vsdbassoc; Flags: uninsdeletevalue

[Run]
Filename: "{app}\{#MyExe}"; Description: "{cm:Launch}"; Flags: nowait postinstall skipifsilent
