# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
"""ข2: ผ่าน/ไม่ผ่าน on every step of «ออกแบบโครงสร้าง คสล.» — ✓/✗ beside
each step, the failing rows in red, «แสดงเฉพาะชิ้นที่ไม่ผ่าน» hides the rows
that pass, «แก้ไขให้ผ่าน» on every step."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QDockWidget

_app = QApplication.instance() or QApplication([])
_KEEP: list = []


def _settle():
    for _ in range(6):
        _app.processEvents()


def test_every_step_says_pass_or_fail_and_filters_the_failing():
    import core.wanic_fail_view as FV
    from core import wanic_rc as R
    from views.main_window import MainWindow
    FV_auto, FV.auto_enabled = FV.auto_enabled, (lambda: False)
    win = MainWindow(defer_extensions=True)
    _KEEP.append(win)
    win.resize(1400, 900)
    win.show()
    _settle()
    win.load_extensions()
    _settle()
    try:
        bp, rc = win._wanic_building, win._wanic_rc
        d = bp.data()
        R.apply_grid(d, [4.9, 4.9], [4.9], 2, [])
        bp._write(d)
        dk = rc
        while dk is not None and not isinstance(dk, QDockWidget):
            dk = dk.parentWidget()
        dk.show()
        _settle()
        rc.steps.setCurrentRow(5)                                     # เสา + คาน
        _settle()
        heads = [rc.table.horizontalHeaderItem(c).text() for c in range(rc.table.columnCount())]
        assert any("ผ่าน/ไม่ผ่าน" in h for h in heads)
        texts = [rc.steps.item(i).text() for i in range(rc.steps.count())]
        assert any(t.endswith("✗") or t.endswith("✓") for t in texts[1:])
        assert rc.advice_btn.isVisible() and "แก้ไขให้ผ่าน" in rc.advice_btn.text()
        rc.steps.setCurrentRow(8)                                     # คำนวณโครงสร้าง
        _settle()
        fails = rc._row_fail
        assert any(fails) and not all(fails)
        rc.only_bad.setChecked(True)
        _settle()
        hidden = [rc.table.isRowHidden(r) for r in range(rc.table.rowCount())]
        assert hidden == [not f for f in fails]
        bad = next(r for r, f in enumerate(fails) if f)
        assert rc.table.item(bad, 1).foreground().color().name() == "#b91c1c"
        rc.only_bad.setChecked(False)
        _settle()
        assert not any(rc.table.isRowHidden(r) for r in range(rc.table.rowCount()))
    finally:
        FV.auto_enabled = FV_auto


def test_an_empty_model_lists_no_materials():
    """ข6: ค่าเริ่มต้นไม่มีรายการวัสดุ — before anything is built every step
    is empty (no default marks F1, C1 … with a count of 0), nothing is
    calculated."""
    from views.main_window import MainWindow
    win = MainWindow(defer_extensions=True)
    _KEEP.append(win)
    win.show()
    _settle()
    win.load_extensions()
    _settle()
    rc = win._wanic_rc
    dk = rc
    while dk is not None and not isinstance(dk, QDockWidget):
        dk = dk.parentWidget()
    dk.show()
    _settle()
    for row in range(1, 9):
        rc.steps.setCurrentRow(row)
        _settle()
        assert rc.table.rowCount() == 0, rc.steps.item(row).text()
        assert "ยังไม่มี" in rc.note.text()
