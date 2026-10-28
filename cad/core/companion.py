# SPDX-License-Identifier: GPL-3.0-or-later
"""Start the other program of the WANICNSURVEY suite (the 2D <-> 3D menu).

Installed layout (Windows)::

    <install dir>\\cad\\ingecad.exe        WANICNSURVEY CAD (2D)
    <install dir>\\3d\\ingetrazo.exe       WANICNSURVEY 3D
    <install dir>\\launcher\\...           the start screen

From a source checkout the sibling folder's ``main.py`` runs with this
interpreter instead.
"""
from __future__ import annotations

import sys
from pathlib import Path

from core import branding


def companion_command() -> list[str] | None:
    """The command line that starts the companion program, or None."""
    if getattr(sys, "frozen", False):
        exe = (Path(sys.executable).resolve().parent.parent
               / branding.COMPANION_DIR / branding.COMPANION_EXE)
        return [str(exe)] if exe.exists() else None
    here = Path(__file__).resolve().parent.parent
    script = here.parent / branding.COMPANION_DIR / "main.py"
    return [sys.executable, str(script)] if script.exists() else None


def launcher_command() -> list[str] | None:
    """The command line that shows the suite's start screen, or None."""
    if getattr(sys, "frozen", False):
        exe = (Path(sys.executable).resolve().parent.parent
               / "launcher" / "wanicnsurvey.exe")
        return [str(exe)] if exe.exists() else None
    here = Path(__file__).resolve().parent.parent
    script = here.parent / "launcher" / "launcher.py"
    return [sys.executable, str(script)] if script.exists() else None


def _start(cmd: list[str] | None, args=()) -> bool:
    if not cmd:
        return False
    from PySide6.QtCore import QProcess
    ok = QProcess.startDetached(cmd[0], cmd[1:] + [str(a) for a in args])
    # PySide6 returns (ok, pid) on some versions, a bool on others.
    return bool(ok[0] if isinstance(ok, tuple) else ok)


def open_companion(paths=()) -> bool:
    """Start the companion program, optionally opening ``paths`` in it."""
    return _start(companion_command(), paths)


def open_launcher() -> bool:
    return _start(launcher_command())


def install_menu(window, menu_bar, tr) -> None:
    """Add the «2D ⇄ 3D» menu to ``menu_bar`` (before Help)."""
    from PySide6.QtGui import QAction
    from PySide6.QtWidgets import QMessageBox

    menu = menu_bar.addMenu("2D ⇄ 3D")
    go = QAction(f"เปิด {branding.COMPANION_NAME}", window)
    go.setStatusTip(f"สลับไปทำงานใน {branding.COMPANION_NAME}")

    def _go() -> None:
        if not open_companion():
            QMessageBox.warning(
                window, branding.APP_NAME,
                f"ไม่พบ {branding.COMPANION_NAME} ในโฟลเดอร์ติดตั้ง")

    go.triggered.connect(_go)
    menu.addAction(go)
    home = QAction("หน้าเริ่มต้น WANICNSURVEY", window)
    home.triggered.connect(open_launcher)
    menu.addAction(home)
