# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2569 (2026) นายเวนิช ธัมมะวงษ์ วิศวกรสำรวจ — ReadWanicn2027
"""ReadWanicn2027: welcome, sign in, then the main window."""
from __future__ import annotations

import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QDialog

from readwanicn import APP_NAME, themes
from readwanicn.ui import LoginDialog, MainWindow, WelcomeScreen, asset, check_license


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setWindowIcon(QIcon(asset("logo.ico")))
    app.setStyleSheet(themes.stylesheet(themes.DEFAULT))
    WelcomeScreen().show_for(2200)
    login = LoginDialog()
    if login.exec() != QDialog.Accepted:
        return 0
    if not check_license():                 # a year of use is up and not renewed
        return 0
    window = MainWindow(login.user)
    window.show()
    files = [a for a in sys.argv[1:] if a.lower().endswith((".pdf", ".json"))]
    if files:
        window.open_files(files)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
