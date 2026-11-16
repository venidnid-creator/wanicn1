# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
"""ไม่ผ่าน — เลือกวิธีแก้: the failing marks with why and the change, the
ticked ones applied, everything passing once all are applied."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

_app = QApplication.instance() or QApplication([])
_KEEP: list = []


def _house():
    from core import wanic_rc as R
    d = {"floors": [{"rooms": []}], "settings": {}}
    R.apply_grid(d, [4, 4, 4], [4, 4], 2, [])
    return d


def test_proposals_say_why_and_what_and_fix_everything():
    from core import wanic_calc as C
    from core import wanic_fail_view as FV
    d = _house()
    res = C.analyse(d)
    assert FV.failing(res) and FV.signature(res)
    trial, rows = FV.proposals(d)
    keys = [r["key"] for r in rows]
    assert "F1" in keys and "C1" in keys
    f1 = next(r for r in rows if r["key"] == "F1")
    assert "น้ำหนักที่กระทำ" in f1["why"] and "รับได้" in f1["why"] and "กว้าง" in f1["change"]
    # only the footing: the rest still fails
    part = _house()
    FV.apply_chosen(part, trial, ["F1"])
    assert (part["library"]["F1"]["w"] > 1.0) and "C1" not in (part.get("library") or {})
    FV.apply_chosen(d, trial, keys)
    assert not FV.failing(C.analyse(d))


def test_the_dialog_ticks_all_and_returns_the_choice():
    from core import wanic_calc as C
    from core import wanic_fail_view as FV
    d = _house()
    _trial, rows = FV.proposals(d)
    dlg = FV.FailDialog(None, C.analyse(d), rows)
    _KEEP.append(dlg)
    assert dlg.chosen() == [r["key"] for r in rows]
    dlg.table.item(0, 0).setCheckState(Qt.Unchecked)
    assert rows[0]["key"] not in dlg.chosen()
    dlg._tick_all(Qt.Unchecked)
    assert dlg.chosen() == []
