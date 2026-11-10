; SPDX-License-Identifier: GPL-3.0-or-later
; ReadWanicn2027 — Thai installer for the in-house PDF tool.
; Expects the PyInstaller folder dist\ReadWanicn2027\ next to the repository root.
; Build:  ISCC.exe /DMyAppVersion=2027.1.0 installer\readwanicn2027.iss   (Inno Setup 6.5+)

#define MyAppName "ReadWanicn2027"
#define MyAppPublisher "นายเวนิช ธัมมะวงษ์"
#define MyAppExe "ReadWanicn2027.exe"
#ifndef MyAppVersion
  #define MyAppVersion "0.0.0-dev"
#endif

[Setup]
AppId={{9C41D7A2-5E3B-4F86-A0C7-2B8E61F4D913}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} เวอร์ชัน {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppCopyright=Copyright (C) 2569 (2026) นายเวนิช ธัมมะวงษ์ วิศวกรสำรวจ
VersionInfoVersion=1.0.0.0
VersionInfoProductName={#MyAppName}
VersionInfoDescription=ReadWanicn2027 Setup
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
LicenseFile=license-th.txt
OutputDir=..\dist
OutputBaseFilename=readwanicn2027-setup-{#MyAppVersion}
WizardStyle=modern
WizardImageFile=wizard-large.bmp,wizard-large-2x.bmp
WizardSmallImageFile=wizard-small.bmp,wizard-small-2x.bmp
SetupIconFile=..\readwanicn2027\assets\logo.ico
UninstallDisplayIcon={app}\{#MyAppExe}
ShowLanguageDialog=no
ChangesAssociations=yes
Compression=lzma2/max
SolidCompression=yes

[Languages]
Name: "thai"; MessagesFile: "Thai.isl"

[CustomMessages]
thai.DesktopIcon=สร้างไอคอนบนหน้าจอเดสก์ท็อป
thai.PdfAssoc=แสดง ReadWanicn2027 ในเมนู «เปิดด้วย» ของไฟล์ PDF
thai.Launch=เปิด ReadWanicn2027 ทันที

[Tasks]
Name: "desktopicon"; Description: "{cm:DesktopIcon}"
Name: "pdfassoc"; Description: "{cm:PdfAssoc}"

[Files]
Source: "..\dist\ReadWanicn2027\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\LICENSE"; DestDir: "{app}"; DestName: "LICENSE.txt"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExe}"; Tasks: desktopicon

[Registry]
Root: HKA; Subkey: "Software\Classes\ReadWanicn2027.pdf"; ValueType: string; ValueData: "เอกสาร PDF (ReadWanicn2027)"; Flags: uninsdeletekey; Tasks: pdfassoc
Root: HKA; Subkey: "Software\Classes\ReadWanicn2027.pdf\shell\open\command"; ValueType: string; ValueData: """{app}\{#MyAppExe}"" ""%1"""; Tasks: pdfassoc
Root: HKA; Subkey: "Software\Classes\.pdf\OpenWithProgids"; ValueType: string; ValueName: "ReadWanicn2027.pdf"; ValueData: ""; Flags: uninsdeletevalue; Tasks: pdfassoc

[Run]
Filename: "{app}\{#MyAppExe}"; Description: "{cm:Launch}"; Flags: nowait postinstall skipifsilent
