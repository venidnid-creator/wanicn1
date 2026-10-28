# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for the WANICNSURVEY start screen.
# Build from the repository root:  pyinstaller launcher/launcher.spec --noconfirm
from pathlib import Path

ROOT = Path(SPECPATH).resolve().parent
BR = ROOT / "branding"

datas = [(str(BR / "wanicnsurvey.ico"), "branding")]
for name in ("wanicnsurvey", "wanicnsurvey-cad", "wanicnsurvey-3d"):
    datas.append((str(BR / "png" / f"{name}-128.png"), "branding"))

a = Analysis(
    [str(ROOT / "launcher" / "launcher.py")],
    pathex=[],
    datas=datas,
    hiddenimports=[],
    excludes=["tkinter", "numpy", "PySide6.QtWebEngineCore", "PySide6.QtQml",
              "PySide6.QtQuick", "PySide6.QtMultimedia", "PySide6.Qt3DCore"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="wanicnsurvey",
    debug=False,
    strip=False,
    upx=False,
    console=False,
    icon=str(BR / "wanicnsurvey.ico"),
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="launcher")
