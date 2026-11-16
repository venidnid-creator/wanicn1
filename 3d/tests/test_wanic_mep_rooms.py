# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
"""งานระบบรายห้อง: the program's lights, sockets, AC and heater per room,
the user's own numbers kept on the room, the circuits' wire by load — in
the BOQ and the load schedule alike."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

_app = QApplication.instance() or QApplication([])
_KEEP: list = []


def _house():
    from core import wanic_rc as R
    d = {"floors": [{"rooms": []}], "settings": {}}
    R.apply_grid(d, [4, 4], [4], 1, [])
    d["floors"][0]["rooms"][0]["name"] = "ห้องนอน 1"
    d["floors"][0]["rooms"][1]["name"] = "ห้องน้ำ"
    return d


def test_wire_sizes_follow_the_load():
    from core import wanic_mep as M
    assert M.ac_wire(12000) == 4 and M.ac_wire(30000) == 6
    assert M.heater_wire(4500) == 6 and M.heater_wire(8000) == 10
    assert set(M.WIRES) >= {2.5, 4, 6}


def test_own_numbers_go_to_the_plan_and_the_boq():
    from core import wanic_mep as M
    from core import wanic_quantities as Q
    from core.wanic_mep_view import MepRoomsDialog
    d = _house()
    auto = M.plan(d)
    bed = next(r for r in auto if r["kind"] == "bed")
    assert bed["ac"] and bed["ac_wire"] == 4 and not bed["own"]
    dlg = MepRoomsDialog(None, d)
    _KEEP.append(dlg)
    i = next(k for k, r in enumerate(dlg.recs) if r["kind"] == "bed")
    dlg.cells[i]["lights"].setValue(bed["lights"] + 3)
    dlg.cells[i]["ac"].setCurrentIndex(dlg.cells[i]["ac"].findData(30000))
    assert dlg.apply(d) == 1
    own = d["floors"][0]["rooms"][0]["mep"]
    assert own == {"lights": bed["lights"] + 3, "ac": 30000}          # only what differs
    bed2 = next(r for r in M.plan(d) if r["kind"] == "bed")
    assert bed2["lights"] == bed["lights"] + 3 and bed2["ac"] == 30000 and bed2["ac_wire"] == 6
    lines = {ln["desc"]: ln for ln in Q.compute(d)["lines"]}
    assert any("THW 6" in k for k in lines) and any("30,000 BTU" in k for k in lines)
    dlg2 = MepRoomsDialog(None, d)
    _KEEP.append(dlg2)
    dlg2.reset_all()
    dlg2.apply(d)
    assert "mep" not in d["floors"][0]["rooms"][0]


def test_the_load_schedule_uses_the_same_wire():
    from core import wanic_building as B
    from core import wanic_drawings as D
    d = _house()
    d["floors"][0]["rooms"][0]["mep"] = {"ac": 36000}
    E = B.elements(d)
    sh = D.Sheet("EE", "x")
    D.ee_single_line(sh, E)
    texts = " ".join(str(it[2]) for it in sh.items if it[0] == "text")
    assert "THW 2×6 + G 6" in texts and "36,000 BTU" in texts
