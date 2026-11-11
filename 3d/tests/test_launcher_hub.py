# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
"""The 2027 start screen: five themes, Thai and English, four program cards,
and the language / tool handed to the program it starts."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _launcher():
    if not (ROOT / "launcher" / "launcher.py").exists():
        pytest.skip("the launcher is not beside this checkout")
    sys.path.insert(0, str(ROOT / "launcher"))
    try:
        import launcher as L
    finally:
        sys.path.pop(0)
    return L


def _texts(win):
    from PySide6.QtWidgets import QLabel, QPushButton
    return {w.text() for w in win.findChildren(QLabel)} | \
        {w.text().strip() for w in win.findChildren(QPushButton)}


def test_themes_and_languages_switch_and_are_remembered(monkeypatch, tmp_path):
    L = _launcher()
    from PySide6.QtCore import QSettings
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, str(tmp_path))
    monkeypatch.setattr(L.StartWindow, "_fetch_stats", lambda self, count: None)
    win = L.StartWindow()
    win.set_lang("th")                        # whatever an earlier run left
    assert len(L.THEMES) == 5
    assert "ออกแบบโครงสร้าง คสล." in _texts(win) and "เริ่มงานใหม่  →" in _texts(win)
    for key in L.THEMES:
        win.set_theme(key)
        assert L.THEMES[key]["bg"] in win.styleSheet()
    win.set_lang("en")
    t = _texts(win)
    assert "RC structure design" in t and "New project  →" in t and "Copy account number" in t
    assert str(win.settings.value("ui/lang")) == "en"
    win.set_lang("th")
    win.set_theme(L.DEFAULT_THEME)
    win.close()


def test_a_card_starts_its_program_with_the_language_and_the_tool(monkeypatch):
    L = _launcher()
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    monkeypatch.setattr(L.StartWindow, "_fetch_stats", lambda self, count: None)
    seen = []
    monkeypatch.setattr(L, "start", lambda which, files=(): seen.append(
        (which, os.environ.get("WANIC_LANG"), os.environ.get("WANIC_START_PANEL"))) or True)
    win = L.StartWindow()
    win.lang = "en"
    win.launch("3d", panel="rc")
    win.launch("cad")
    assert seen == [("3d", "en", "rc"), ("cad", "en", None)]
