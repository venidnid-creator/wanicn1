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
#: the window lives to the end of the run, as the other tests' windows do
#: (conftest leaves with os._exit instead of tearing them down)
_KEEP: list = []


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
    _KEEP.append(win)
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
        win.set_tray_shown(tkd, True)                    # it starts hidden (Window ▸ Panels)
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


def test_move_axis_paste_same_place_and_free_beam():
    """ค8: เลื่อนแนวคาน (all floors, rooms and openings on it), วางห้องที่
    ตำแหน่งเดิม, คานอิสระ from two clicks."""
    from core import wanic_building as B
    from core import wanic_rc as R
    from views.main_window import MainWindow
    win = MainWindow(defer_extensions=True)
    _KEEP.append(win)
    win.show()
    _settle()
    win.load_extensions()
    _settle()
    bp = win._wanic_building
    d = bp.data()
    R.apply_grid(d, [4.0, 4.0], [4.0], 2, [])
    bp._write(d)
    assert bp.move_axis("x", 4.0, 4.5)
    for f in bp.data()["floors"]:
        xs = sorted({r["x"] for r in f["rooms"]} | {r["x"] + r["w"] for r in f["rooms"]})
        assert 4.5 in [round(v, 3) for v in xs] and 4.0 not in [round(v, 3) for v in xs]
    assert not bp.move_axis("x", 4.5, 8.0)                      # a room would be under 0.50 m
    bp.floor = 0
    n0 = len(bp.data()["floors"][1]["rooms"])
    bp.copy_rooms({r["id"] for r in bp.data()["floors"][0]["rooms"][:1]})
    bp.floor = 1
    got = bp.paste_rooms("same")
    f1 = bp.data()["floors"][1]["rooms"]
    assert len(got) == 1 and len(f1) == n0 + 1
    src = bp.data()["floors"][0]["rooms"][0]
    new = next(r for r in f1 if r["id"] == got[0])
    assert (new["x"], new["y"]) == (src["x"], src["y"])
    assert bp.add_free_beam((0.0, 2.0), (4.5, 2.0))
    fb = B.elements(bp.data())["free"]["beams"]
    assert len(fb) == 1 and abs(fb[0]["pts"][0][2] - 2 * float(B.settings_of(bp.data())["floor_h"])) < 1e-6
