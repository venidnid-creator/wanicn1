# -*- mode: python ; coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
# ReadWanicn2027 for Windows: one folder, no console.  pyinstaller readwanicn.spec
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

a = Analysis(
    ['main.py'],
    pathex=['.'],
    datas=[('assets/*', 'assets')] + collect_data_files('docx') + collect_data_files('ezdxf'),
    hiddenimports=['readwanicn._license_key', 'pymupdf', 'openpyxl', 'docx', 'PySide6.QtPrintSupport']
                  + collect_submodules('ezdxf.addons.drawing') + collect_submodules('ezdxf.fonts')
                  + ['ezdxf.addons.odafc'],
    excludes=['tkinter', 'matplotlib', 'numpy.tests', 'PySide6.QtWebEngineCore',
              'PySide6.Qt3DCore', 'PySide6.QtMultimedia', 'PySide6.QtQuick', 'PySide6.QtQml'],
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='ReadWanicn2027',
          icon='assets/logo.ico', console=False, upx=False)
coll = COLLECT(exe, a.binaries, a.datas, name='ReadWanicn2027', upx=False)
