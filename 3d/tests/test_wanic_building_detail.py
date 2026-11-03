# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
"""The 3D build in detail: wet rooms set down, members that meet cut to one
another, valleys on the right side, caps of every kind, mitred purlins, the
eave soffit with its frame, names and part data, the frame view."""
from __future__ import annotations

import math
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from core import wanic_building as B
from core import wanic_profiles as P
from core import wanic_quantities as Q
from core import wanic_roofclip as RC
from core.scene import Scene


def _u_plan():
    """The plan of the user's house: a U of seven rooms (grid 1–4, A–E)."""
    return [dict(name="ห้องนอน", x=0, y=0, w=4.8, d=4.8),
            dict(name="ห้องทำงาน", x=4.8, y=0, w=4.8, d=4.8),
            dict(name="ห้องน้ำ", x=0, y=4.8, w=2.5, d=2.4),
            dict(name="ห้องน้ำ", x=0, y=7.2, w=2.5, d=2.4),
            dict(name="ทางเดิน", x=2.5, y=4.8, w=2.3, d=4.8),
            dict(name="ห้องนอน", x=0, y=9.6, w=4.8, d=4.8),
            dict(name="ห้องครัว", x=4.8, y=9.6, w=4.8, d=4.8)]


def _data(rooms=None):
    d = B.default_data()
    d["floors"][0]["rooms"] = rooms or _u_plan()
    return d


def _box(g):
    ps = [v.position for v in g.mesh.vertices]
    return (min(p.x() for p in ps), min(p.y() for p in ps), min(p.z() for p in ps),
            max(p.x() for p in ps), max(p.y() for p in ps), max(p.z() for p in ps))


def _kind(g):
    return g.ext[B.EXT_KEY]["kind"]


def test_wet_rooms_sit_five_centimetres_down():
    d = _data()
    d["floors"][0]["fixtures"] = [{"id": "f1", "type": "WC", "x": 1.0, "y": 6.0},
                                  {"id": "f2", "type": "WC", "x": 1.0, "y": 1.0}]
    E = B.elements(d)
    drops = {e["room"]["name"]: e["drop"] for e in E["slabs"]}
    assert drops["ห้องน้ำ"] == 0.05 and drops["ห้องนอน"] == 0.0
    groups, _c = B.structure_members(d)
    tops = sorted({round(_box(g)[5], 3) for g in groups if _kind(g) == "slab"})
    assert tops == [-0.05, 0.0]
    bath = [g for g in groups if _kind(g) == "slab" and "ห้องน้ำ" in g.name]
    assert len(bath) == 2 and all(abs(_box(g)[5] + 0.05) < 1e-6 for g in bath)
    assert ["พื้นห้องเปียก", "ต่ำกว่าพื้นข้างเคียง 5 ซม."] in \
        bath[0].ext[B.EXT_KEY]["info"]


def test_members_that_meet_do_not_overlap():
    groups, _c = B.structure_members(_data())
    solids = [(g.name, _box(g)) for g in groups
              if _kind(g) in ("beam", "column", "stump", "slab")]
    for i in range(len(solids)):
        for j in range(i + 1, len(solids)):
            a, b = solids[i][1], solids[j][1]
            ov = [min(a[k + 3], b[k + 3]) - max(a[k], b[k]) for k in range(3)]
            assert not all(o > 1e-4 for o in ov), (solids[i][0], solids[j][0])
    # a beam stops at the column faces: 4.80 m between centres, 4.60 net
    beam = next(g for g in groups if _kind(g) == "beam" and "แนว A (1–3)" in g.name)
    x0, _y0, _z0, x1, _y1, _z1 = _box(beam)
    assert math.isclose(x1 - x0, 4.6, abs_tol=1e-6)


def test_valleys_on_the_right_side_and_no_false_hips():
    lines = B.roof_lines(_data())
    hips = [(tuple(round(v, 2) for v in a[:2]), tuple(round(v, 2) for v in b[:2]))
            for a, b in lines["hip"]]
    # the hip that lay flat in the wing's slope is gone …
    assert ((5.4, -0.6), (2.4, 2.4)) not in hips
    assert ((5.4, 15.0), (2.4, 12.0)) not in hips
    # … and the valleys run from the ridge junction to the inside corners
    ends = sorted(sorted((round(a[0], 1), round(a[1], 1), round(b[0], 1),
                          round(b[1], 1))) for a, b in lines["valleys"])
    assert len(lines["valleys"]) == 2
    for a, b in lines["valleys"]:
        lo, hi = (a, b) if a[2] < b[2] else (b, a)
        assert (round(lo[0], 1), round(lo[1], 1)) in ((5.4, 5.4), (5.4, 9.0))
        assert (round(hi[0], 1), round(hi[1], 1)) in ((2.4, 2.4), (2.4, 12.0))
    assert ends
    assert math.isclose(lines["valley"], 2 * math.dist(lines["valleys"][0][0],
                                                        lines["valleys"][0][1]),
                        rel_tol=1e-3)


def test_caps_every_kind_and_the_valley_gutters():
    d = _data()
    lines = B.roof_lines(d)
    specials = [k for k, _p, _n in B.cap_specials(lines)]
    assert specials.count("hip_end") == len(lines["hip"]) == 6
    assert specials.count("three_way") == 4
    assert RC.accessories(lines)["three_way"] == 4          # the BOQ agrees
    groups, count = B.roof_members(d)
    assert count["valley"] == 2 and count["gutter"] == 2
    caps = [g for g in groups if _kind(g) == "cap"]
    names = {g.ext[B.EXT_KEY]["mark"] for g in caps}
    assert {"ครอบสัน", "ครอบตะเข้สัน", "ครอบโค้งหางมน", "ครอบโค้งสามทาง"} <= names
    ridge = next(g for g in caps if g.name.startswith("ครอบสัน · 32 แผ่น"))
    assert ["จำนวน", "32 แผ่น (ยาวใช้งาน 0.303 ม./แผ่น)"] in \
        ridge.ext[B.EXT_KEY]["info"]


def test_purlins_are_mitred_on_the_hips_and_rafters_stop_at_the_hip():
    d = _data()
    lines = B.roof_lines(d)
    assert all(not pl["closed"] and len(pl["path"]) == 2 for pl in lines["purlin"])
    groups, _c = B.roof_members(d)

    def off_line(p, a, b):
        dx, dy = b[0] - a[0], b[1] - a[1]
        return abs((p[0] - a[0]) * dy - (p[1] - a[1]) * dx) / math.hypot(dx, dy)
    checked = 0
    for g in groups:
        if _kind(g) != "purlin":
            continue
        path = g.ext[P.EXT_KEY]["path"]
        for end in (path[0], path[-1]):
            for a, b in lines["hip"]:
                if off_line(end, a, b) < 0.01 and \
                        min(a[0], b[0]) - 0.01 <= end[0] <= max(a[0], b[0]) + 0.01:
                    reach = min(0.3, 0.45 * math.dist(path[0], path[-1]))
                    near = [v.position for v in g.mesh.vertices
                            if math.dist((v.position.x(), v.position.y(),
                                          v.position.z()), end) < reach]
                    assert max(off_line((p.x(), p.y()), a, b) for p in near) < 1e-4
                    checked += 1
    assert checked > 20


def test_soffit_with_its_frame_and_in_the_bill():
    d = _data([dict(name="ห้องนอน", x=0, y=0, w=8, d=6)])
    cells, z = B.soffit_cells(d)
    s = B.settings_of(d)
    ov, rb = s["overhang"], 0.1
    want = (8 + 2 * ov) * (6 + 2 * ov) - (8 + 2 * rb) * (6 + 2 * rb)
    assert math.isclose(B.soffit_area(d), want, rel_tol=1e-9)
    assert z < 3.0
    groups, count = B.roof_members(d)
    assert count["soffit"] == 1 and count["soffit_frame"] == 1
    r = Q.compute(d)
    line = next(ln for ln in r["lines"] if ln["desc"].startswith("ฝ้าชายคา"))
    assert math.isclose(line["qty"], round(want, 2), abs_tol=0.01)
    assert "5.41" in line["ref"]
    d["settings"]["soffit"] = False
    assert not any(ln["desc"].startswith("ฝ้าชายคา") for ln in Q.compute(d)["lines"])


def test_every_part_says_what_and_where_it_is():
    groups, _c = B.build(_data())
    for g in groups:
        wb = g.ext[B.EXT_KEY]
        if wb["kind"] in ("door", "window", "band", "fixture", "stair", "skin",
                          "tiles", "post"):
            continue
        assert wb.get("info"), (wb["kind"], g.name)
    col = next(g for g in groups if _kind(g) == "column")
    assert col.name.startswith("เสา C1 20×20 ซม. · ชั้น 1 · ")
    wall = next(g for g in groups if _kind(g) == "wall")
    assert "แนว" in wall.name and "ชั้น 1" in wall.name
    valley = next(g for g in groups if _kind(g) == "valley")
    assert valley.ext[B.EXT_KEY]["key"] == "ตะเฆ่ราง C 150×65×20×3.2"


def test_the_frame_view_and_the_standard_looks():
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from plugins.wanic_building import BuildingPanel
    from tests.test_wanic_building import _App
    scene = Scene()
    app = _App(scene)
    d = _data()
    app.set_document_data(d)
    panel = BuildingPanel(app)
    panel.build(("structure", "roof"))
    groups = B.generated(scene)
    panel.frame_btn.setChecked(True)
    shown = [g for g in groups if not g.hidden]
    assert shown and all(g.ext[B.EXT_KEY]["part"] == "structure" for g in shown)
    gb = next(g for g in shown if str(g.ext[B.EXT_KEY]["mark"]).startswith("GB"))
    assert gb.material["color"] == panel.FRAME_COLORS["ground_beam"]
    panel.frame_btn.setChecked(False)
    assert not any(g.hidden for g in groups)
    assert gb.material != {"color": panel.FRAME_COLORS["ground_beam"]}
    for key in ("iso", "top", "front", "back", "left", "right"):
        panel.look(key)                     # the test viewport has no camera
