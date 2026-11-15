# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
"""ทำงานเร็วขึ้น: the panels that measure the whole model (ถอดปริมาณ,
โปรไฟล์) do not measure it again while their tab is behind another tab —
Qt still calls such a tab «visible» — and catch up the moment their tab is
brought to the front."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDockWidget

_app = QApplication.instance() or QApplication([])


def _dock_of(w):
    while w is not None and not isinstance(w, QDockWidget):
        w = w.parentWidget()
    return w


def _settle():
    for _ in range(6):
        _app.processEvents()


def test_a_tab_behind_another_waits_and_catches_up():
    from core import wanic_rc as R
    from views.main_window import MainWindow
    win = MainWindow(defer_extensions=True)
    win.resize(1400, 900)
    win.show()
    _settle()
    win.load_extensions()
    _settle()
    try:
        bp, rc, tk, pf = (win._wanic_building, win._wanic_rc,
                          win._wanic_takeoff, win._wanic_profiles)
        d = bp.data()
        R.apply_grid(d, [4, 4], [4], 1, [])
        bp._write(d)
        rcd = _dock_of(rc)
        rcd.show()
        rcd.raise_()
        _settle()
        calls = {"tk": 0, "pf": 0}
        tk_refresh, pf_refresh = tk.refresh, pf.refresh

        def count_tk():
            calls["tk"] += 1
            tk_refresh()

        def count_pf():
            calls["pf"] += 1
            pf_refresh()
        tk.refresh, pf.refresh = count_tk, count_pf
        # the RC tab is in front: building the model does not measure it in the hidden tabs
        rc.build_model()
        _settle()
        tk._refresh_if_shown()
        pf._refresh_if_shown()
        assert calls == {"tk": 0, "pf": 0}
        assert tk._stale and pf._stale
        # the take-off tab is brought to the front: it measures once
        tkd = _dock_of(tk)
        tkd.raise_()
        _settle()
        QTest.qWait(600)                                 # its 0.3 s timer
        _settle()
        assert calls["tk"] == 1 and not tk._stale
        assert tk._items                                 # the members it found in the model
        rcd.raise_()
        _settle()
    finally:
        win._saved_version = win.viewport.scene.version
        win.close()
