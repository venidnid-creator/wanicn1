# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for WanicnDesign (ออกแบบอาคาร ประมาณราคา), part of the WANICNSURVEY suite.
# Build from this folder:  pyinstaller --noconfirm --distpath ../../dist --workpath ../../build/design wanicndesign.spec
# The data tables (ว480, recipes, Factor F, provinces, sections) go to _internal/data, where
# wanicndesign.rates.DATA_DIR finds them; the user's own files live in %APPDATA%\WANICNSURVEY.
from pathlib import Path

HERE = Path(SPECPATH).resolve()
BR = HERE.parent.parent / "branding"

datas = [(str(p), "data") for p in sorted((HERE / "data").glob("*.json"))
         if p.name != "labour_override.json"]
datas += [(str(p), "examples") for p in sorted((HERE / "examples").glob("*.json"))]

a = Analysis(
    [str(HERE / "main.py")],
    pathex=[str(HERE)],
    datas=datas,
    hiddenimports=["openpyxl", "ezdxf", "numpy", "PySide6.QtSvg", "PySide6.QtPrintSupport"],
    excludes=["tkinter", "pytest", "PySide6.QtWebEngineCore", "PySide6.QtQml", "PySide6.QtQuick",
              "PySide6.QtMultimedia", "PySide6.Qt3DCore"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="wanicndesign",
    debug=False,
    strip=False,
    upx=False,
    console=False,
    icon=str(BR / "wanicnsurvey-design.ico"),
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="wanicndesign")
