# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
"""สัญลักษณ์ประตู-หน้าต่าง: the leaf and its arc on the side it opens to
(เปิดเข้า / เปิดออก), sliding arrows, awning, louvres, fixed lights — one
geometry for the plan on screen and the sheets."""
from __future__ import annotations

from core import wanic_opening_sym as OS

ROOM = [{"x": 0.0, "y": 0.0, "w": 4.0, "d": 3.0}]      # the bottom wall y = 0 is exterior


def _arc_side(sym):
    """+1 when the leaves swing to y > 0 (into the room), −1 outside."""
    (_cx, cy), r, a0, a1 = sym["arcs"][0]
    import math
    mid = math.radians((a0 + a1) / 2)
    return 1 if math.sin(mid) > 0 else -1


def test_a_door_opens_in_or_out_as_set():
    wall = ((0.0, 0.0), (4.0, 0.0))
    inn = OS.symbol({"type": "door", "style": "D1", "x": 2.0, "y": 0.0, "w": 0.9, "swing": "in"}, *wall, ROOM)
    out = OS.symbol({"type": "door", "style": "D1", "x": 2.0, "y": 0.0, "w": 0.9, "swing": "out"}, *wall, ROOM)
    assert inn["kind"] == "swing" and inn["inward"] and not out["inward"]
    assert _arc_side(inn) == 1 and _arc_side(out) == -1
    assert inn["label"][1] == "เปิดเข้า" and out["label"][1] == "เปิดออก"
    double = OS.symbol({"type": "door", "style": "D2", "x": 2.0, "y": 0.0, "w": 1.6}, *wall, ROOM)
    assert len(double["arcs"]) == 2


def test_windows_open_out_slide_and_push():
    wall = ((0.0, 0.0), (4.0, 0.0))
    case = OS.symbol({"type": "window", "style": "W1", "x": 2.0, "y": 0.0, "w": 1.2}, *wall, ROOM)
    assert case["kind"] == "swing" and _arc_side(case) == -1           # outward by default
    slide = OS.symbol({"type": "window", "style": "W2", "x": 2.0, "y": 0.0, "w": 1.4}, *wall, ROOM)
    assert slide["kind"] == "slide" and len(slide["arrows"]) == 2 and not slide["arcs"]
    aw = OS.symbol({"type": "window", "style": "W3", "x": 2.0, "y": 0.0, "w": 1.0}, *wall, ROOM)
    assert aw["kind"] == "awning" and aw["dashed"] and aw["label"][1] == "กระทุ้ง"
    assert all(p[1] <= 0.08 for d in aw["dashed"] for p in d)            # pushed out, below the wall
    assert OS.symbol({"type": "window", "style": "W5", "x": 2, "y": 0, "w": 1.0}, *wall, ROOM)["kind"] == "louvre"
    assert OS.symbol({"type": "window", "style": "W4", "x": 2, "y": 0, "w": 1.0}, *wall, ROOM)["kind"] == "fixed"


def test_the_legend_has_every_kind_and_fits_cp874():
    kinds = set()
    for code, swing, text in OS.LEGEND:
        from core import wanic_catalog as CAT
        spec = CAT.OPENING_TYPES[code]
        kinds.add(OS.kind_of(spec, code))
        text.encode("cp874")
    assert kinds == {"swing", "slide", "awning", "louvre", "fixed"}
