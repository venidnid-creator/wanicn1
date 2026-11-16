# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
"""บันไดอัตโนมัติ: balanced risers within the law, the stair inside the
ground floor at the chosen place, on every floor below the top, and its
detail sheets in the drawing set."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

_app = QApplication.instance() or QApplication([])
_KEEP: list = []


def _house(n=2):
    from core import wanic_rc as R
    d = {"floors": [{"rooms": []}], "settings": {}}
    R.apply_grid(d, [4, 4, 4], [4, 4], n, [])
    return d


@pytest.mark.parametrize("H,n", [(2.6, 14), (3.0, 16), (3.2, 18), (3.5, 20)])
def test_risers_are_even_and_within_the_law(H, n):
    from core import wanic_stair_auto as SA
    k = SA.risers_for(H)
    assert k == n and k % 2 == 0
    R_ = H / k
    assert R_ <= 0.19 + 1e-9 and 0.59 <= 2 * R_ + SA.GOING <= 0.65


def test_every_place_fits_inside_and_keeps_the_law():
    from core import wanic_building as B
    from core import wanic_stair_auto as SA
    d = _house()
    x0, y0, x1, y1 = SA.footprint(d)
    for where in SA.PLACES:
        st, rep = SA.design(d, where)
        assert rep["ok"], (where, rep["lines"])
        rect = B.stair_layout(st, rep["settings"])["rect"]
        assert all(x0 - 1e-6 <= p[0] <= x1 + 1e-6 and y0 - 1e-6 <= p[1] <= y1 + 1e-6 for p in rect), where
        assert rep["flights"] == [8, 8]                    # 3.00 m: two equal flights of 8
    left, _r = SA.design(d, ("left", "front"))
    right, _r = SA.design(d, ("right", "back"))
    assert left["x"] < (x0 + x1) / 2 < right["x"] and left["y"] < right["y"]


def test_apply_puts_it_on_every_floor_but_the_top_and_replaces_its_own():
    from core import wanic_stair_auto as SA
    d = _house(3)
    assert SA.needs_stairs(d)
    st, _rep = SA.design(d, ("center", "back"))
    assert SA.apply(d, st) == 2
    assert [len(f.get("stairs") or []) for f in d["floors"]] == [1, 1, 0]
    assert not SA.needs_stairs(d)
    st2, _rep = SA.design(d, ("left", "front"))
    SA.apply(d, st2)
    assert [len(f.get("stairs") or []) for f in d["floors"]] == [1, 1, 0]
    assert abs(d["floors"][0]["stairs"][0]["x"] - st2["x"]) < 1e-9


def test_a_small_house_is_told_it_does_not_fit():
    from core import wanic_rc as R
    from core import wanic_stair_auto as SA
    d = {"floors": [{"rooms": []}], "settings": {}}
    R.apply_grid(d, [1.5], [2.0], 2, [])
    _st, rep = SA.design(d, ("center", "front"))
    assert not rep["fits"] and any("เล็กเกินไป" in t for t in rep["lines"])


def test_the_dialog_and_the_detail_sheets():
    from core import wanic_drawings as D
    from core import wanic_stair_auto as SA
    from core.wanic_stair_auto_view import StairAutoDialog
    d = _house()
    dlg = StairAutoDialog(None, d)
    _KEEP.append(dlg)
    dlg.group.button(0).setChecked(True)
    dlg.update_view()
    assert dlg.where() == ("left", "back") and dlg.rep["ok"] and dlg.ok.isEnabled()
    SA.apply(d, dlg.stair)
    titles = [s.title for s in D.build_set(d, {"project": "x"}, ("A", "S"))]
    assert "แบบขยายบันได" in titles and "รายละเอียดบันได คสล." in titles


def test_the_floor_above_is_opened_and_railed():
    """ช่องบันได: the slab of the floor above has the stair's opening (in the
    model and the BOQ), a guard rail runs round it except where one steps
    off, and the stair keeps a clear floor in front of its first step."""
    from core import wanic_building as B
    from core import wanic_quantities as Q
    from core import wanic_stair_auto as SA
    d = _house()
    before = Q.compute(d)
    st, rep = SA.design(d, ("left", "front"))
    assert rep["ok"] and st["y"] - rep["D"] / 2 >= 1.0 - 1e-6        # 1.00 m clear at the foot
    SA.apply(d, st)
    E = B.elements(d)
    holes = B.holes_by_floor(E)
    assert list(holes) == [1] and len(holes[1]) == 1
    hx0, hy0, hx1, hy1 = holes[1][0]
    groups, count = B.structure_members(d)
    slabs_up = [g for g in groups if (g.ext or {}).get(B.EXT_KEY, {}).get("kind") == "slab"
                and min(v.position.z() for v in g.mesh.vertices) > 1.0]
    for g in slabs_up:                                # no slab piece over the opening's middle
        xs = [v.position.x() for v in g.mesh.vertices]
        ys = [v.position.y() for v in g.mesh.vertices]
        cx, cy = (hx0 + hx1) / 2, (hy0 + hy1) / 2
        assert not (min(xs) + 1e-6 < cx < max(xs) - 1e-6 and min(ys) + 1e-6 < cy < max(ys) - 1e-6)
    rail = B.well_railing(st, B.settings_of(d), B.building_outline(E))
    assert rail and count["stair_rail"] > 20
    after = Q.compute(d)
    conc = lambda r: sum(ln["qty"] for ln in r["lines"] if ln["desc"].startswith("คอนกรีตโครงสร้าง") and "พื้นชั้นบน" in ln["desc"])  # noqa: E731
    assert conc(after) < conc(before)
