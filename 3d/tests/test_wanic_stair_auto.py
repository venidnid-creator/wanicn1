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
    assert "แบบขยายบันได ST.1 (แปลน)" in titles and "แบบขยายบันได ST.1 (รูปตัด)" in titles   # the standard's ST.n
    assert any(t.startswith("รายละเอียดบันได คสล. ST.1") for t in titles)       # one flight a sheet


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
    x0, y0, x1, y1 = SA.footprint(d)
    assert rep["ok"] and st["y"] - rep["D"] / 2 - y0 < 0.2          # the landing against the front wall
    assert st["y"] + rep["D"] / 2 + 1.0 <= y1 + 1e-6                  # 1.00 m clear at the foot, inside
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


def test_four_storeys_ask_for_a_fire_escape_stair_and_the_rules_say_so():
    from core import wanic_building as B
    from core import wanic_drawings as D
    from core import wanic_stair_auto as SA
    d = _house(4)
    st, _r = SA.design(d, ("left", "front"))
    SA.apply(d, st)
    assert SA.needs_fire_stair(d)
    fire, rep = SA.design(d, ("right", "back"))
    assert rep["ok"] and SA.apply_fire(d, fire) == 3
    assert not SA.needs_fire_stair(d)
    assert [len(f["stairs"]) for f in d["floors"]] == [2, 2, 2, 0]
    E = B.elements(d)
    assert len(B.holes_by_floor(E)[1]) == 2
    rules = " ".join(D.storey_rules(E))
    assert "บันไดหนีไฟ" in rules and "ฉบับที่ 39" in rules
    assert "บันไดหนีไฟ" not in " ".join(D.storey_rules(B.elements(_house(2))))


def test_one_floor_and_hand_placement_advice():
    """ค1: «สร้างเฉพาะชั้นนี้» puts the stair on one floor only; a stair
    moved by hand is checked (inside, clear floor at the foot, the landing
    on an outside wall, no column inside)."""
    from core import wanic_stair_auto as SA
    d = _house(3)                                                # three storeys
    st, rep = SA.design(d, ("center", "front"))
    assert SA.apply_one(d, st, 1) == 1
    assert [bool(f.get("stairs")) for f in d["floors"]] == [False, True, False]
    good = SA.check_place(d, st, rep["settings"])
    assert all(ok for ok, _t in good), good
    far = dict(st, x=st["x"] + 100.0)
    assert not SA.check_place(d, far, rep["settings"])[0][0]       # outside the building
    flipped = dict(st, dir=(st["dir"] + 2) % 4)
    assert not all(ok for ok, _t in SA.check_place(d, flipped, rep["settings"]))


def test_auto_stair_beside_a_column_never_across_it():
    """The owner: the stair goes beside the column (the landing's corner on
    it) — no column line through the stair, the landing beam only as long
    as the landing, its end at the column without a post."""
    from core import wanic_building as B
    from core import wanic_rc as R
    from core import wanic_stair_auto as SA
    d = B.default_data()
    R.apply_grid(d, [4.9, 4.9], [4.9, 4.9], 2)
    st, rep = SA.design(d, ("center", "front"))
    s = rep["settings"]
    xs = [p[0] for p in B.stair_layout(st, s)["rect"]]
    assert not any(min(xs) < g < max(xs) for g in (0.0, 4.9, 9.8))
    assert all(ok for ok, _t in SA.check_place(d, st, s))
    cols = B.stair_cols(B.elements(d), 0)
    sb2 = B.stair_beams(st, s, 0.0, cols)[1]
    assert abs(abs(sb2["p1"][0] - sb2["p0"][0]) - (max(xs) - min(xs))) < 0.2     # not past the landing
    assert any(sb2["end_cols"]) and len(B.stair_posts(st, s, 0.0, cols)) == 1
