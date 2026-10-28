# SPDX-License-Identifier: GPL-3.0-or-later
# Build the WANICNSURVEY installer on your own Windows PC.
#
# Needs (install once):
#   - Python 3.12 (64-bit)  https://www.python.org/downloads/  (tick "Add to PATH")
#   - Git                   https://git-scm.com/download/win
#   - Inno Setup 6.5+       https://jrsoftware.org/isdl.php
# Then double-click build-windows.bat. The installer lands in dist\.
# (The GitHub Actions build also compiles the faster Rust engine for 3D;
#  this local build uses the Python engine, which gives the same results.)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$Version = if ($args.Count -gt 0) { $args[0] } else { Get-Date -Format "yyyy.MM.dd" }
$Cache = Join-Path $PSScriptRoot "build\downloads"
New-Item -ItemType Directory -Force $Cache | Out-Null

function Step($t) { Write-Host "`n==> $t" -ForegroundColor Cyan }

Step "Python environment (.venv)"
if (-not (Test-Path ".venv")) { py -3.12 -m venv .venv }
$py = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
& $py -m pip install --upgrade pip
& $py -m pip install PySide6==6.11.2 numpy "ezdxf>=1.4.4" "manifold3d>=3.5.3" Pillow pyproj pyinstaller
& $py -m pip install "openskp @ git+https://github.com/iamahsanmehmood/openskp@291700bc213655a00461838de71e5f206311e619#subdirectory=packages/python"

Step "DWG converters for CAD (IngeCAD's patched LibreDWG)"
$cadBin = "cad\vendor\libredwg\bin"
# Fastest: copy them from an IngeCAD already installed on this PC.
$installed = Get-ChildItem "$env:ProgramFiles\IngeCAD" -Recurse -Filter dwg2dxf.exe -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not (Test-Path "$cadBin\dwg2dxf.exe") -and $installed) {
    New-Item -ItemType Directory -Force $cadBin | Out-Null
    Copy-Item (Join-Path $installed.DirectoryName "*.exe") $cadBin
}
if (-not (Test-Path "$cadBin\dwg2dxf.exe")) {
    $zip = Join-Path $Cache "ingecad-win.zip"
    Invoke-WebRequest "https://github.com/ingelibre/ingecad/releases/download/v0.6.7/IngeCAD-0.6.7-windows-x64.zip" -OutFile $zip
    $tmp = Join-Path $Cache "ingecad-win"
    Expand-Archive $zip $tmp -Force
    New-Item -ItemType Directory -Force $cadBin | Out-Null
    foreach ($f in "dwg2dxf.exe", "dxf2dwg.exe") {
        Get-ChildItem $tmp -Recurse -Filter $f | Select-Object -First 1 | Copy-Item -Destination $cadBin
    }
}

Step "DWG reader for 3D (LibreDWG 0.14.8597 win64)"
$tdBin = "3d\vendor\libredwg\bin"
if (-not (Test-Path "$tdBin\dwg2dxf.exe")) {
    $zip = Join-Path $Cache "libredwg.zip"
    Invoke-WebRequest "https://github.com/LibreDWG/libredwg/releases/download/0.14.8597/libredwg-0.14.8597-win64.zip" -OutFile $zip
    $hash = (Get-FileHash $zip -Algorithm SHA256).Hash.ToLower()
    if ($hash -ne "7fee5c67c4f451f0542c0d6a3b12e91e99b15faf363fbf8b98ad84bac17ddfa2") { throw "LibreDWG download checksum mismatch" }
    $tmp = Join-Path $Cache "libredwg"
    Expand-Archive $zip $tmp -Force
    New-Item -ItemType Directory -Force $tdBin | Out-Null
    foreach ($f in "dwg2dxf.exe", "libredwg-0.dll", "libiconv-2.dll") {
        Get-ChildItem $tmp -Recurse -Filter $f | Select-Object -First 1 | Copy-Item -Destination $tdBin
    }
}

Step "Freeze WANICNSURVEY CAD"
Push-Location cad;  & $py -m PyInstaller --noconfirm --distpath ..\dist --workpath ..\build\cad packaging\ingecad.spec; Pop-Location
Step "Freeze WANICNSURVEY 3D"
Push-Location 3d;   & $py -m PyInstaller --noconfirm --distpath ..\dist --workpath ..\build\3d ingetrazo.spec; Pop-Location
Step "Freeze the start screen"
& $py -m PyInstaller --noconfirm --distpath dist --workpath build\launcher launcher\launcher.spec

Step "Installer (Inno Setup)"
$iscc = @("${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe", "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
          "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) { throw "Inno Setup 6.5+ not found - install it from https://jrsoftware.org/isdl.php" }
& $iscc "/DMyAppVersion=$Version" installer\wanicnsurvey.iss
if ($LASTEXITCODE -ne 0) { throw "Inno Setup failed" }
Write-Host "`nDone: dist\wanicnsurvey-setup-$Version.exe" -ForegroundColor Green
