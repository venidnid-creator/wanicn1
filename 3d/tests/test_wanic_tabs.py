# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
"""The WANIC panels' tabs: an icon of their own and their short Thai name
beside it (the side tray shows only icons since IngeTrazo 0.6)."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QStyleOptionTab, QTabBar

_app = QApplication.instance() or QApplication([])


def test_every_panel_has_an_icon_and_a_short_name():
    from core import wanic_tabs as W
    from views.icons import tool_icon
    for title in ("ออกแบบอาคาร", "ออกแบบโครงสร้าง คสล.", "ออกแบบถนน", "ถอดปริมาณ", "โปรไฟล์"):
        key = W.icon_key(title)
        assert key and not tool_icon(key).isNull(), title
        assert W.short_name(title)
    assert W.short_name("Properties") is None


def test_a_wanic_tab_is_wider_by_its_name():
    from views.main_window import _IconTabStyle, _wanic_short
    style = _IconTabStyle("Fusion")
    bar = QTabBar()
    bar.setStyle(style)
    plain, ours = QStyleOptionTab(), QStyleOptionTab()
    plain.text, ours.text = "Properties", "ออกแบบอาคาร"
    for o in (plain, ours):
        o.iconSize = bar.iconSize()
        o.fontMetrics = bar.fontMetrics()
        o.shape = QTabBar.RoundedNorth
    assert _wanic_short(ours) == "อาคาร" and _wanic_short(plain) is None
    from PySide6.QtCore import QSize
    from PySide6.QtWidgets import QStyle
    w0 = style.sizeFromContents(QStyle.CT_TabBarTab, plain, QSize(10, 20), bar).width()
    w1 = style.sizeFromContents(QStyle.CT_TabBarTab, ours, QSize(10, 20), bar).width()
    assert w1 > w0 + bar.fontMetrics().horizontalAdvance("อาคาร")
