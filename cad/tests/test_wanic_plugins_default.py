# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
"""Upstream's Roads plugin (Peruvian DG-2018) starts switched off — our own
road design (สำรวจ: แนวทาง สถานี ปริมาณดิน) covers the work — and the
extension manager can still turn it on."""
from __future__ import annotations

from core import plugins as P


def test_roads_start_off_and_can_be_turned_on(clean_settings):
    pm = P.PluginManager(None)
    pm.discover()
    assert "carreteras" in pm.loaded
    assert not pm.enabled("carreteras")
    assert pm.enabled("topografia")
    from PySide6.QtCore import QSettings
    QSettings().setValue(P.PluginManager.SETTING.format(id="carreteras"), True)
    assert pm.enabled("carreteras")
