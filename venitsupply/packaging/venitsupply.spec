# -*- mode: python ; coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
# พัสดุเวนิช (VENIT SUPPLY) — PyInstaller bundle (one folder).
# Build from venitsupply/:  pyinstaller --noconfirm packaging/venitsupply.spec
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

ROOT = Path(SPECPATH).parent

a = Analysis(
    [str(ROOT / "main.py")],
    pathex=[str(ROOT)],
    datas=[
        (str(ROOT / "venitsupply" / "data" / "*.csv"), "venitsupply/data"),
        (str(ROOT / "venitsupply" / "data" / "README.md"), "venitsupply/data"),
        (str(ROOT / "assets" / "*"), "assets"),
    ],
    hiddenimports=collect_submodules("pdfminer") + collect_submodules("venitsupply"),
    excludes=["PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtQuick",
              "PySide6.QtQml", "PySide6.Qt3DCore", "PySide6.QtMultimedia", "PySide6.QtCharts",
              "PySide6.QtDataVisualization", "PySide6.QtBluetooth", "PySide6.QtNetworkAuth",
              "tkinter", "numpy", "matplotlib"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="venitsupply",
    console=False,
    icon=str(ROOT / "assets" / "venitsupply.ico"),
    version=None,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="venitsupply")
