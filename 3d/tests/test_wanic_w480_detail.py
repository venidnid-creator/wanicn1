# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
"""ว480 in full, wall types (exterior flush with the columns, plaster as
its own skin), the roof frame by the standard (purlins at the tile's
gauge in one piece, a tie beam under every king post, the wall plate,
mitred fascia), part prices in the Properties rows, automatic layers and
the 15 หมวดงาน."""
from __future__ import annotations

import math
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from core import wanic_building as B
from core import wanic_catalog as CAT
from core import wanic_categories as CG
from core import wanic_quantities as Q
from core import wanic_std2569 as S
from core import wanic_w480 as W


def _u_plan():
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


def test_the_whole_w480_list():
    assert len(W.ROWS) > 1400 and len(W.codes()) > 250
    assert set(W.SECTIONS) == {"1", "2", "3", "4", "5"}
    # rows as printed in the letter
    assert W.rate("2.3.1.2", "ฉาบปูนผนัง", "ภายนอก") == 109
    assert W.rate("2.3.1.2", "ฉาบปูนผนัง", "ภายใน") == 96
    assert W.rate("2.3.1.2", "ฉาบปูนโครงสร้าง (ภายนอก)") == 132
    assert W.rate("2.1.10", "รางน้ำตะเข้") == 26
    assert W.rate("1.11.1") == 12 and W.rate("4.58") == 118
    assert W.rate("2.2.1", "ฝ้าเพดานตีเว้นร่อง", "ไม้เทียม") == 113
    assert any("น้ำ" in r[1] for r in W.rows_of("3"))
    assert W.search("ก่ออิฐมวลเบา 0.10")
    # the BOQ's own table agrees with the letter, row by row
    for code, (_d, _u, rate, _c) in S.LABOUR.items():
        base = S.w480_code(code)
        if base in W.codes():
            assert float(rate) in {float(r[4]) for r in W.ROWS if r[0] == base}, code
    # plaster and wall-tile rows carry their ว480 numbers; old saved
    # overrides still apply
    assert S.labour("2.3.1.2b") == 109 and S.labour("2.3.2b") == 109
    d = _data()
    d["labour"] = {"2.3.2a": 99}
    assert Q.labour_of(d)["2.3.1.2a"] == 99
    assert S.wall_labour_code("6.11") == "2.3.1b10" and S.labour("2.3.1b10") == 76


def test_exterior_walls_flush_outside_interior_on_the_line():
    d = _data()
    groups, count = B.structure_members(d)
    assert count["wall"] and count["plaster"] == 2 * count["wall"]
    walls = [g for g in groups if _kind(g) == "wall"]
    col = float(B.library_of(d)["C1"]["b"])
    for g in walls:
        x0, y0, _z0, x1, y1, _z1 = _box(g)
        ext = "ภายนอก" in g.name
        thin = min(x1 - x0, y1 - y0)
        assert math.isclose(thin, 0.07, abs_tol=1e-6)
        mid = (x0 + x1) / 2 if x1 - x0 < y1 - y0 else (y0 + y1) / 2
        if ext:
            # its outside plaster is flush with the column face (grid ± b/2):
            # the masonry's outer face sits the plaster's thickness inside
            faces = (x0, x1) if x1 - x0 < y1 - y0 else (y0, y1)
            po = B.wall_spec(B.settings_of(d), True)["po"]
            assert any(abs(abs(f - round(f / 2.4) * 2.4) - (col / 2 - po)) < 1e-6
                       for f in faces), (g.name, faces)
        else:
            assert abs(mid - round(mid / 0.1) * 0.1) < 1e-6
    # the outside plaster face is flush with the column and beam faces
    skin = [g for g in groups if _kind(g) == "plaster" and "ภายนอก" in g.name]
    assert math.isclose(min(_box(g)[0] for g in skin), -col / 2, abs_tol=1e-6)
    assert math.isclose(min(_box(g)[1] for g in skin), -col / 2, abs_tol=1e-6)
    # nothing overlaps
    solids = [(g.name, _box(g)) for g in groups
              if _kind(g) in ("column", "beam", "slab", "wall", "plaster")]
    for i in range(len(solids)):
        for j in range(i + 1, len(solids)):
            a, b = solids[i][1], solids[j][1]
            ov = [min(a[k + 3], b[k + 3]) - max(a[k], b[k]) for k in range(3)]
            assert not all(o > 1e-4 for o in ov), (solids[i][0], solids[j][0])


def test_wall_types_and_plaster_in_the_bill():
    d = _data()
    d["settings"].update(ext_wall="6.11", int_wall="6.1", ext_plaster_t=0.02)
    r = Q.compute(d)
    outer = [ln for ln in r["lines"] if ln["desc"].startswith("ผนังภายนอก —")]
    inner = [ln for ln in r["lines"] if ln["desc"].startswith("ผนังภายใน —")]
    assert outer and inner
    assert "มวลเบา" in outer[0]["desc"] and outer[0]["lab"] == 76
    assert "มอญ" in inner[0]["desc"] and inner[0]["lab"] == 104
    assert any("ฉาบปูนเรียบ ผนังภายนอก (หนา 2 ซม.)" in ln["desc"] for ln in r["lines"])
    groups, _c = B.structure_members(d)
    ext = next(g for g in groups if _kind(g) == "wall" and "ภายนอก" in g.name)
    assert "มวลเบา 10 ซม." in ext.name
    rates = B.takeoff_rates(d)
    keys = {rt["value"] for rt in rates}
    assert {"ฉาบปูนผนังภายนอก", "ฉาบปูนผนังภายใน"} <= keys


def test_purlins_at_the_tile_gauge_in_one_piece():
    d = _data([dict(name="ห้อง", x=0, y=0, w=8, d=6)])
    rsp, psp = B.roof_spacing(B.settings_of(d))
    assert psp == CAT.ROOF_TILES["R1"]["eff"][1] == 0.32 and rsp == 1.0
    lines = B.roof_lines(d)
    segs = [pl["path"] for pl in lines["purlin"]]
    assert B.merge_segments(segs) and len(B.merge_segments(segs)) == len(segs)
    # one straight piece per course and slope: two pieces never share a line
    for i, (a, b) in enumerate(segs):
        for c, e in segs[i + 1:]:
            same = abs(a[2] - c[2]) < 1e-6 and (
                (abs(a[1] - b[1]) < 1e-6 and abs(c[1] - e[1]) < 1e-6 and abs(a[1] - c[1]) < 1e-6)
                or (abs(a[0] - b[0]) < 1e-6 and abs(c[0] - e[0]) < 1e-6 and abs(a[0] - c[0]) < 1e-6))
            assert not same
    # collinear bits merge into one
    m = B.merge_segments([[(0, 0, 0), (1, 0, 0)], [(1, 0, 0), (2.5, 0, 0)],
                          [(3, 1, 0), (4, 1, 0)]])
    assert sorted(round(math.dist(a, b), 3) for a, b in m) == [1.0, 2.5]
    # the top course sits close under the ridge
    ov = B.settings_of(d)["overhang"]
    half = (6 + 2 * ov) / 2
    tan = math.tan(math.radians(B.settings_of(d)["pitch"]))
    ridge_z = lines["ridge"][0][0][2]
    top = max(p[2] for s_ in segs for p in s_)
    assert ridge_z - top < 0.04 * tan + 1e-6 and half > 0


def test_tie_beam_under_every_king_post_and_wall_plates():
    d = _data()
    lines = B.roof_lines(d)
    assert lines["plate_h"] == 0.15 and lines["plate"] and lines["tie"]

    def on(a, t, axis, dz=0.0):
        t0, t1 = t
        if abs(t0[2] + dz - a[2]) > 1e-6 or abs(t0[1 - axis] - t1[1 - axis]) > 1e-9:
            return False
        lo, hi = sorted((t0[axis], t1[axis]))
        return abs(t0[1 - axis] - a[1 - axis]) < 1e-6 and lo - 1e-6 <= a[axis] <= hi + 1e-6
    assert lines["rbeam"]
    db = 0.15
    for a, _b in lines["post"]:
        # every post stands on the ridge beam (คานรับดั้ง), which sits on a
        # tie (ขื่อ) running across under the post: held both ways, and the
        # tie and the beam never cut through each other
        beam = [t for t in lines["rbeam"] if on(a, t, 0) or on(a, t, 1)]
        tie = [t for t in lines["tie"] if on(a, t, 0, db) or on(a, t, 1, db)]
        assert beam and tie, a
        bdir = 0 if abs(beam[0][0][1] - beam[0][1][1]) < 1e-9 else 1
        tdir = 0 if abs(tie[0][0][1] - tie[0][1][1]) < 1e-9 else 1
        assert bdir != tdir
    z0 = lines["z0"]
    assert all(abs(p[2] - (z0 + 0.15)) < 1e-9 for seg in lines["plate"] for p in seg)
    groups, count = B.roof_members(d)
    assert count["wallplate"] == len(lines["plate"]) and count["tiebeam"] == len(lines["tie"])
    plate = next(g for g in groups if _kind(g) == "wallplate")
    assert plate.name.startswith("อะเส C 150") and abs(_box(plate)[2] - z0) < 1e-6
    r = Q.compute(d)
    steel = " ".join(ln["basis"] for ln in r["lines"] if ln["desc"].startswith("โครงหลังคาเหล็ก"))
    assert steel


def test_fascia_corners_are_mitred():
    d = _data([dict(name="ห้อง", x=0, y=0, w=8, d=6)])
    groups, _c = B.roof_members(d)
    boards = [g for g in groups if _kind(g) == "fascia"]
    assert len(boards) == 4
    ov = B.settings_of(d)["overhang"]
    t = B.settings_of(d)["fascia_t"]
    for g in boards:
        x0, y0, _z0, x1, y1, _z1 = _box(g)
        # each board reaches the outer corner and stops there: no crossing
        assert math.isclose(min(x0, y0), -ov - t / 2, abs_tol=1e-6)
    for i in range(4):
        for j in range(i + 1, 4):
            a, b = _box(boards[i]), _box(boards[j])
            ov_ = [min(a[k + 3], b[k + 3]) - max(a[k], b[k]) for k in range(2)]
            # boxes only share the mitre's corner square
            assert min(ov_) <= t + 1e-6


def test_part_prices_layers_and_categories():
    d = _data()
    d["prices"] = dict(S.SAMPLE_PRICES)
    groups, _c = B.build(d)
    col = next(g for g in groups if _kind(g) == "column")
    info = dict(col.ext[B.EXT_KEY]["info"])
    assert "ราคาวัสดุ/หน่วย" in info and "ค่าแรง/หน่วย" in info and "รวม" in info
    assert info["ปริมาณ"].endswith("ลบ.ม.") and "ว480" in info["ค่าแรง/หน่วย"]
    wall = next(g for g in groups if _kind(g) == "wall")
    assert dict(wall.ext[B.EXT_KEY]["info"])["ปริมาณ"].endswith("ตร.ม.")
    raf = next(g for g in groups if _kind(g) == "rafter")
    assert dict(raf.ext[B.EXT_KEY]["info"])["ปริมาณ"].endswith("กก.")
    # layers named after the part
    assert B.layer_name(col, "name") == col.name
    assert B.layer_name(col, "type") == "เสา C1 20×20 ซม."
    assert B.layer_name(col, "floor") == "เสา C1 20×20 ซม. · ชั้น 1"
    assert B.layer_name(col, "category") == "04 งานโครงสร้างคอนกรีต"
    assert B.layer_name(raf, "name").startswith("จันทัน C") and "ยาว" not in B.layer_name(raf)
    by = B.assign_layers(groups, "name")
    assert col.layer == col.name and col in by[col.name]
    assert B.assign_layers(groups, "") == {} and col.layer is None
    # the 15 หมวดงาน
    assert [c[0] for c in CG.CATEGORIES] == list(range(1, 16))
    assert CG.NAME[1] == "งานเตรียมพื้นที่" and CG.NAME[15] == "งานอื่นๆ"
    r = Q.compute(d)
    titles = [th for _k, th, _rows in r["groups"]]
    assert titles[0] == "1. งานเตรียมพื้นที่"
    for t in ("11. งานสุขาภิบาล", "12. งานไฟฟ้า", "13. งานปรับอากาศ",
              "14. งานภายนอก", "15. งานอื่นๆ", "10. งานพื้น/ฝ้า"):
        assert t in titles, t
    assert "5. งานโครงสร้างเหล็ก" in titles and "6. งานผนัง/ฉาบ" in titles
    assert "7. งานหลังคา" in titles and "4. งานโครงสร้างคอนกรีต" in titles
    assert all(ln["cat"] in CG.NAME for ln in r["lines"])
    paint = [ln for ln in r["lines"] if ln["desc"].startswith("ทาสี") and "กันสนิม" not in ln["desc"]]
    assert all(ln["cat"] == 9 for ln in paint)
    d["boq_options"] = {"boq_by": "rule"}
    assert Q.compute(d)["groups"][0][1] == Q.GROUP_TH["prep"]


def test_more_door_and_window_styles():
    doors = dict(CAT.types_of("door"))
    wins = dict(CAT.types_of("window"))
    assert {"D8", "D9", "D10", "D11", "D13"} <= set(doors)
    assert doors["D9"]["leaves"] == 4 and doors["D9"]["w"] == 2.80
    assert doors["D11"]["transom"] == 0.40 and doors["D11"]["h"] == 2.45
    assert {"W6", "W7", "W9", "W10"} <= set(wins)
    sk = CAT.opening_sketch(doors["D10"])
    assert any(w == "fixed" for *_r, w in sk) and any(w == "arrow" for *_r, w in sk)
    d = _data([dict(name="ห้อง", x=0, y=0, w=4, d=4)])
    d["floors"][0]["openings"] = [{"id": "o1", "type": "door", "style": "D11",
                                   "x": 2.0, "y": 0.0}]
    groups, count = B.structure_members(d)
    door = next(g for g in groups if _kind(g) == "door")
    assert "D11" in door.name and count["door"] == 1
    assert math.isclose(_box(door)[5] - _box(door)[2], 2.45, abs_tol=1e-6)


def test_panel_layers_picker_walls_and_the_boq_sidebar(monkeypatch):
    from PySide6.QtWidgets import QApplication, QMessageBox
    QApplication.instance() or QApplication([])
    from core.scene import Scene
    from plugins import wanic_building as WB
    from tests.test_wanic_building import _App

    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)
    scene = Scene()
    panel = WB.BuildingPanel(_App(scene))
    panel.resize(500, 900)
    panel.room_name.setCurrentText("ห้องนอน")
    panel.place_room(1.5, 1.5)
    # wall settings on the panel
    panel.combos["ext_wall"].setCurrentIndex(panel.combos["ext_wall"].findData("6.11"))
    panel.combos["ext_plaster_t"].setCurrentIndex(
        panel.combos["ext_plaster_t"].findData(0.02))
    s = panel.data()["settings"]
    assert s["ext_wall"] == "6.11" and s["ext_plaster_t"] == 0.02
    assert math.isclose(s["wall_t"], 0.10 + 0.015 + 0.02)
    # a door picked from the thumbnails
    panel.set_tool("door")
    dlg = WB.OpeningPicker(panel, "door", "D1")
    dlg._pick("D9")
    assert dlg.code == "D9"
    i = panel.op_style.findData("D9")
    assert i >= 0 and not panel.op_style.itemIcon(i).isNull()
    # build: every part on a layer named after it
    panel.build(("structure", "roof"))
    built = B.generated(scene)
    names = {ly.name for ly in scene.layers}
    col = next(g for g in built if _kind(g) == "column")
    assert col.layer == col.name and col.name in names
    assert any(n.startswith("ฉาบปูนผนังภายนอก") for n in names)
    # by type: fewer layers, the old ones dropped
    panel.combos["layer_mode"].setCurrentIndex(panel.combos["layer_mode"].findData("type"))
    panel.build(("structure", "roof"))
    names2 = {ly.name for ly in scene.layers}
    assert "เสา C1 20×20 ซม." in names2 and col.name not in names2
    # the BOQ: 15 หมวดงาน in the sidebar, picking one shows only it
    boq = WB.BoqDialog(panel)
    assert boq.cats.count() == 16
    row = next(r for r in range(boq.cats.count())
               if "4. งานโครงสร้างคอนกรีต" in boq.cats.item(r).text())
    boq.cats.setCurrentRow(row)
    shown = [boq.tree.topLevelItem(i).text(1) for i in range(boq.tree.topLevelItemCount())
             if not boq.tree.topLevelItem(i).isHidden()]
    assert shown == ["4. งานโครงสร้างคอนกรีต"]
    boq.boq_by.setCurrentIndex(boq.boq_by.findData("rule"))
    assert panel.data()["boq_options"]["boq_by"] == "rule"
    assert boq.tree.topLevelItem(0).text(1) == Q.GROUP_TH["prep"]
    # the whole ว480 list, searchable
    assert boq.w480.rowCount() == len(W.ROWS)
    boq.w480_q.setText("ฉาบปูนผนัง ภายนอก")
    assert 0 < boq.w480.rowCount() < 20
    assert any(boq.w480.item(r, 4).text() == "109.00" for r in range(boq.w480.rowCount()))
    # the skirting / cornice buttons and the services switch
    panel.skirt_btn.setChecked(True)
    panel.cornice_btn.setChecked(True)
    s = panel.data()["settings"]
    assert s["skirting"] and s["cornice"]
    panel.build(("structure", "roof"))
    kinds = {_kind(g) for g in B.generated(scene)}
    assert {"skirting", "cornice", "ceiling", "ac", "light", "headplate"} <= kinds
    # a window clicked near a column lands 25 cm off it, head level with the doors
    panel.set_tool("window")
    panel.op_style.setCurrentIndex(panel.op_style.findData("W3"))
    room = panel.rooms()[0]
    oid = panel.place_opening(float(room["x"]) + 0.3, float(room["y"]) + 0.02, "window")
    op = next(o for o in panel.items("openings") if o["id"] == oid)
    col = float(B.library_of(panel.data())["C1"]["b"])
    assert math.isclose(op["x"] - float(room["x"]), col / 2 + 0.25 + op["w"] / 2,
                        abs_tol=1e-6), (op, room)
    assert math.isclose(op["sill"] + op["h"], 2.0, abs_tol=1e-6)


def test_openings_snap_to_three_places_and_heads_line_up():
    p0, p1 = (0.0, 0.0), (4.8, 0.0)
    slots = B.opening_slots(p0, p1, 1.2, 0.2)
    assert [round(v, 3) for v in slots] == [0.95, 2.4, 3.85]   # 0.10 + 0.25 + 0.60
    segs = [(p0, p1)]
    assert B.snap_opening(0.3, 0.05, 1.2, segs, 0.2)[:2] == (0.95, 0.0)
    assert B.snap_opening(2.0, 0.05, 1.2, segs, 0.2)[:2] == (2.4, 0.0)
    assert B.snap_opening(4.7, -0.1, 1.2, segs, 0.2)[:2] == (3.85, 0.0)
    assert B.opening_slots((0, 0), (1.6, 0), 0.9, 0.2) == [0.8]  # short span: middle
    s = B.settings_of(_data())
    assert B.window_sill(s, 1.10) == 0.9 and B.window_sill(s, 1.50) == 0.5
    op = {"type": "window", "style": "W9"}
    w, h, sill = B.opening_size(op, s)
    assert math.isclose(sill + h, 2.0)


def test_column_heads_ceilings_trims_and_services():
    d = _data()
    d["settings"].update(skirting=True, cornice=True)
    groups, count = B.build(d)
    # a plate with four J-bolts on every top column, in the bill
    assert count["headplate"] == len(B.nodes(d["floors"][0]["rooms"]))
    hp = next(g for g in groups if _kind(g) == "headplate")
    z = [v.position.z() for v in hp.mesh.vertices]
    assert math.isclose(min(z), 3.0 - 0.60, abs_tol=1e-6) and max(z) > 3.0
    r = Q.compute(d)
    assert any(ln["desc"].startswith("เพลทหัวเสา") for ln in r["lines"])
    assert any(ln["desc"].startswith("J-bolt 4-DB12") for ln in r["lines"])
    # a ceiling in every room, under the beams, with its frame
    n_rooms = len(d["floors"][0]["rooms"])
    assert count["ceiling"] == n_rooms and count["ceiling_frame"] == n_rooms
    ceil = next(g for g in groups if _kind(g) == "ceiling" and "ห้องนอน" in g.name)
    assert math.isclose(_box(ceil)[5], 3.0 - 0.4, abs_tol=1e-6)
    wet = next(g for g in groups if _kind(g) == "ceiling" and "ห้องน้ำ" in g.name)
    assert "ไฟเบอร์ซีเมนต์" in dict(wet.ext[B.EXT_KEY]["info"])["ชนิด"]
    descs = " | ".join(ln["desc"] for ln in r["lines"])
    assert "ฝ้ายิปซัมบอร์ด 9 มม. ฉาบรอยต่อเรียบ" in descs and "ฝ้าไฟเบอร์ซีเมนต์" in descs
    # skirting where the walls are not tiled high, cornice under every ceiling
    assert count["skirting"] == n_rooms - 2 and count["cornice"] == n_rooms
    sk = next(ln for ln in r["lines"] if ln["desc"].startswith("บัวเชิงผนังกระเบื้องเซรามิค"))
    assert sk["lab"] == 51 and sk["cat"] == 10
    # services: AC in the bedrooms only, lights everywhere
    assert count["ac"] == 2 and count["ac_out"] == 2 and count["light"] == n_rooms
    ac = next(ln for ln in r["lines"] if ln["desc"].startswith("เครื่องปรับอากาศแยกส่วน"))
    assert "24,000" in ac["desc"] and ac["qty"] == 2 and ac["lab"] == 1538 and ac["cat"] == 13
    cats = {ln["cat"] for ln in r["lines"]}
    assert {1, 11, 12, 13, 14, 15} <= cats
    fd = next(ln for ln in r["lines"] if "ฟลอร์เดรน" in ln["desc"])
    assert fd["qty"] == 2 and fd["cat"] == 11
    unit = next(g for g in groups if _kind(g) == "ac")
    top = _box(unit)[5]
    assert math.isclose(top, 3.0 - 0.4 - 0.009 - 0.15, abs_tol=1e-6)
    d["settings"]["mep"] = False
    assert not any(ln["cat"] in (12, 13) for ln in Q.compute(d)["lines"])


def test_purlins_even_long_and_facing_the_ridge():
    d = _data()
    d["settings"].update(pitch=35, overhang=1.0, purlin_sp=0.32, rafter_sp=1.0)
    lines = B.roof_lines(d)
    # every purlin a single straight piece; none share a line with another
    segs = [pl["path"] for pl in lines["purlin"]]
    assert len(B.merge_segments(segs)) == len(segs)
    # evenly spaced, never wider than the set 0.32 m along the slope
    zs = sorted({round(p[0][2], 4) for p in segs})
    steps = [b - a for a, b in zip(zs, zs[1:])]
    sin = math.sin(math.radians(35))
    assert max(steps) / sin <= 0.32 + 1e-6
    assert max(steps) - min(steps) < 0.02
    # rafters evenly spaced within 1.00 m (a span that does not divide
    # is shared out closer)
    s = B.settings_of(d)
    assert B.roof_spacing(s) == (1.0, 0.32)
    # the C of every purlin opens up the slope, towards the ridge
    for pl in lines["purlin"]:
        a, b = B.purlin_facing(pl["path"], lines["skin"])
        up = B.uphill(tuple((a[i] + b[i]) / 2 for i in range(3)), lines["skin"])
        assert up is not None
        assert (-(b[1] - a[1])) * up[0] + (b[0] - a[0]) * up[1] > 0
    s["purlin_face"] = "eave"
    a, b = B.purlin_facing(segs[0], lines["skin"], "eave")
    up = B.uphill(tuple((a[i] + b[i]) / 2 for i in range(3)), lines["skin"])
    assert (-(b[1] - a[1])) * up[0] + (b[0] - a[0]) * up[1] < 0


def test_services_where_they_are_installed():
    d = _data()
    d["floors"][0]["openings"] = [{"id": "o1", "type": "door", "style": "D1", "x": 2.4, "y": 0.0}]
    d["floors"][0]["fixtures"] = [{"id": "f1", "type": "WC1", "x": 1.0, "y": 6.0}]
    groups, count = B.structure_members(d)
    for k in ("outlet", "panel", "ground_rod", "fan", "pipe_supply", "pipe_drain",
              "septic", "grease", "meter", "walkway", "drain_pipe", "manhole", "sign"):
        assert count.get(k), k
    panel = next(g for g in groups if _kind(g) == "panel")
    assert math.isclose(_box(panel)[2], 1.50, abs_tol=1e-6)        # ขอบล่าง 1.50 ม.
    sw = next(g for g in groups if _kind(g) == "outlet" and "ห้องนอน" in g.name)
    zs = sorted({round(v.position.z(), 2) for v in sw.mesh.vertices})
    assert 1.14 in zs or 1.26 in zs                                   # สวิตช์ 1.20 ม.
    tank = next(g for g in groups if _kind(g) == "septic")
    assert _box(tank)[2] < -1.0                                       # ฝังใต้ดิน
    cats = {CG.kind_category(_kind(g)) for g in groups}
    assert {11, 12, 13, 14, 15} <= cats


def test_building_sections_and_the_front_matter():
    from core import wanic_drawings as D
    d = _data()
    E = B.elements(d)
    cuts = D.section_cuts(E, 0)
    assert len(cuts) == 2 and {c[0] for c in cuts} == {"x", "y"}
    assert cuts[0][3] == "ห้องน้ำ" and cuts[0][2] == "ก-ก" and cuts[1][2] == "ข-ข"
    S = D.build_sections(d, {"project": "บ้านทดสอบ"})
    assert len(S) == E["n"] and S[0].title == "รูปตัด ก-ก รูปตัด ข-ข"
    t = " ".join(S[0].texts())
    for want in ("รูปตัด ก-ก (ตัดผ่านห้องน้ำ)", "รูปตัด ข-ข", "ระดับพื้นชั้น 1",
                 "ระดับฝ้าชั้น 1", "ระดับสันหลังคา", "ห้องน้ำ", "ฝ้า +2.60", "ระดับดินเดิม"):
        assert want in t, want
    full = D.build_set(d, {"project": "บ้านทดสอบ"})
    assert [s.code for s in full[:2]] == ["ปก", "สารบัญ"]
    toc = " ".join(full[1].texts())
    assert "สารบัญ" in toc and "แผ่นที่ A-01 ถึงแผ่นที่" in toc and "บัญชีแสดงปริมาณวัสดุ" in toc
    plan = next(s for s in full if s.title == "แปลนพื้นชั้น 1")
    assert "ก" in plan.texts() and "ข" in plan.texts()                # section marks


def test_truss_struts_apex_cut_and_hip_caps_on_the_fascia():
    d = _data([dict(name="ห้อง", x=0, y=0, w=9.6, d=7.2)])
    d["settings"].update(pitch=35, overhang=1.0)
    lines = B.roof_lines(d)
    # every post has its pair of struts and braces
    assert len(lines["strut"]) == 2 * len(lines["post"]) == len(lines["brace"])
    for a, b in lines["strut"]:
        assert abs(a[0] - b[0]) < 1e-9 and abs(a[1] - b[1]) < 1e-9 and b[2] > a[2]
    groups, count = B.roof_members(d)
    assert count["strut"] == len(lines["strut"]) and count["brace"] == len(lines["brace"])
    r = Q.compute(d)
    assert any("C 100×50×20×2.3" in ln["desc"] for ln in r["lines"])
    # the middle rafter of each hip end runs to the ridge end and is cut
    # square there (no wedge along one hip)
    (ra, rb), = lines["ridge"]
    mids = [g for g in groups if _kind(g) == "rafter"
            and any(math.dist(p[:2], q[:2]) < 1e-6 for p in g.ext["wanic_profiles"]["path"]
                    for q in (ra, rb))]
    assert len(mids) >= 2
    for g in mids:
        path = g.ext["wanic_profiles"]["path"]
        top = max(path, key=lambda p: p[2])
        axis = 0 if abs(path[0][1] - path[1][1]) < 1e-9 else 1
        near = [v.position for v in g.mesh.vertices
                if math.dist((v.position.x(), v.position.y()), top[:2]) < 0.2]
        vals = {round((p.x(), p.y())[axis], 4) for p in near}
        assert len(vals) == 1, vals                      # one plumb square end
    # hip caps run on past the eave corner, about 10 cm (hip_cap_out)
    ov = 1.0
    caps = [g for g in groups if _kind(g) == "cap"]
    xs = [v.position.x() for g in caps for v in g.mesh.vertices]
    ys = [v.position.y() for g in caps for v in g.mesh.vertices]
    assert -ov - 0.30 <= min(xs) < -ov - 0.05 and -ov - 0.30 <= min(ys) < -ov - 0.05


def test_walkway_and_drain_follow_the_outline_with_settable_offsets():
    from core import wanic_mep as M
    d = _data()
    s = B.settings_of(d)
    assert s["walk_w"] == 1.0 and s["drain_off"] == 1.5
    E = B.elements(d)
    ring, pits = M.ring_length(E, s)
    assert pits >= 8 and ring > 0
    box = _data([dict(name="ห้อง", x=0, y=0, w=8, d=6)])
    r1, _p = M.ring_length(B.elements(box), B.settings_of(box))
    assert math.isclose(r1, 2 * (8.2 + 3 + 6.2 + 3))         # 1.5 m out each side
    box["settings"]["drain_off"] = 2.5
    r2, _p = M.ring_length(B.elements(box), B.settings_of(box))
    assert math.isclose(r2 - r1, 8.0)
    groups, count = B.structure_members(_data())
    pipes = [g for g in groups if _kind(g) == "drain_pipe"]
    walk = next(g for g in groups if _kind(g) == "walkway")
    wb = _box(walk)
    # the drain is 1.5 m out from the column faces, the walkway 1.0 m
    assert math.isclose(min(_box(p)[0] for p in pipes), -0.1 - 1.5 - 0.15, abs_tol=1e-3)
    assert math.isclose(wb[0], -0.1 - 1.0, abs_tol=1e-6) and wb[5] <= 0.0
    cells = M._rect_union_cells([(0, 0, 4, 4), (3, 3, 7, 7)], [(1, 1, 3, 3)])
    for i, a in enumerate(cells):
        for b in cells[i + 1:]:
            assert not (min(a[2], b[2]) - max(a[0], b[0]) > 1e-9 and
                        min(a[3], b[3]) - max(a[1], b[1]) > 1e-9)
    r = Q.compute(_data())
    walk_line = next(ln for ln in r["lines"] if ln["desc"].startswith("ทางเท้ารอบอาคาร"))
    assert "1.00 ม." in walk_line["desc"]


def _collinear_gaps(segs, most=0.3):
    """Pairs of pieces on one line with a small gap between them (pieces
    that should have been one member)."""
    out = []
    for i, (a, b) in enumerate(segs):
        L = math.dist(a, b)
        u = [(b[k] - a[k]) / L for k in range(3)]
        for c, d in segs[i + 1:]:
            Lv = math.dist(c, d)
            v = [(d[k] - c[k]) / Lv for k in range(3)]
            if abs(sum(u[k] * v[k] for k in range(3))) < 0.9999:
                continue
            tc = sum((c[k] - a[k]) * u[k] for k in range(3))
            if math.dist(c, [a[k] + u[k] * tc for k in range(3)]) > 0.01:
                continue
            td = sum((d[k] - a[k]) * u[k] for k in range(3))
            lo, hi = sorted((tc, td))
            gap = max(lo - L, -hi)
            if gap < most:
                out.append(gap)
    return out


def test_one_plane_of_two_roofs_has_one_set_of_rafters_and_purlins():
    # an L: the wing's hipped end and the main roof's side make one face
    d = _data([dict(name="a", x=0, y=0, w=9, d=4), dict(name="b", x=0, y=4, w=4, d=5)])
    d["settings"]["roof"] = "hip"
    L = B.roof_lines(d)
    assert not _collinear_gaps([p["path"] for p in L["purlin"]])
    assert not _collinear_gaps(L["rafter"])
    # the beam under the posts ends on a tie at both ends
    ties = L["tie"]
    for a, b in L["rbeam"]:
        for e in (a, b):
            assert any(abs((e[0] - t0[0]) * (t1[1] - t0[1]) - (e[1] - t0[1]) * (t1[0] - t0[0]))
                       / math.dist(t0[:2], t1[:2]) < 1e-6 for t0, t1 in ties)


def test_truss_members_butt_and_the_hip_stays_in_the_fascia_corner():
    d = _data([dict(name="ห้อง", x=0, y=0, w=6, d=9)])
    d["settings"]["roof"] = "hip"
    s = B.settings_of(d)
    L = B.roof_lines(d)
    pw = B._dim(s["wallplate"], "B") / 2
    # a tie stops on the wall plate's face, not inside it
    for a, b in L["tie"]:
        assert math.isclose(min(a[0], b[0]), 0.0 + pw, abs_tol=1e-6) or \
            math.isclose(min(a[1], b[1]), 0.0 + pw, abs_tol=1e-6)
    hp = B._dim(s["post"])
    hs = B._dim(s["strut"])
    posts = [(p[0][0], p[0][1]) for p in L["post"]]
    struts = [(p[0][0], p[0][1]) for p in L["strut"]]
    for a, b in L["brace"]:
        # from the post's face to the strut's face, both plumb cuts
        pa = min(posts, key=lambda q: math.dist(q, a[:2]))
        pb = min(struts, key=lambda q: math.dist(q, b[:2]))
        assert math.isclose(math.dist(pa, a[:2]), hp / 2, abs_tol=1e-6)
        assert math.isclose(math.dist(pb, b[:2]), hs / 2, abs_tol=1e-6)
    groups, _c = B.roof_members(d)
    ft = float(s["fascia_t"])
    ov = float(s["overhang"])
    for g in (g for g in groups if _kind(g) == "hip"):
        x0, y0, _z0, x1, y1, _z1 = _box(g)
        assert x0 >= -ov + ft / 2 - 1e-3 and y0 >= -ov + ft / 2 - 1e-3
        assert x1 <= 6 + ov - ft / 2 + 1e-3 and y1 <= 9 + ov - ft / 2 + 1e-3


def test_bath_elevations_and_rebar_details_in_the_set():
    from core import wanic_drawings as D
    d = _data()
    d["floors"][0]["fixtures"] = [{"type": "WC1", "x": 0.5, "y": 5.3, "dir": 0},
                                  {"type": "LV", "x": 1.8, "y": 5.1, "dir": 0}]
    sheets = D.build_set(d, {"project": "ทดสอบ"}, groups=("A", "S"))
    titles = {s.title: s for s in sheets}
    el = titles["รูปด้านภายในห้องน้ำ"]
    txt = " ".join(el.texts())
    assert "รูปด้านภายใน ก" in txt and "รูปด้านภายใน ง" in txt
    assert "WC1 โถส้วม" in txt and "กระจกเงา" in txt
    rb = titles["แบบขยายเหล็กเสริมฐานรากและคาน"]
    txt = " ".join(rb.texts())
    assert "รูปตัดฐานราก F1" in txt and "รูปตัด A-A (ที่หัวเสา)" in txt
    assert "L/4 @0.075" in txt and rb.count("circle", "rebar") > 8
    assert D._bars("2-DB12")[:3] == (2, "DB12", 12)
    assert D._bars("DB12@0.15")[3] == 0.15


def test_download_count_reads_the_public_release_list():
    from core import wanic_downloads as WD
    data = [{"tag_name": "v2", "assets": [{"name": "s-2.exe", "download_count": 5},
                                          {"name": "usage-install.txt", "download_count": 3},
                                          {"name": "usage-open.txt", "download_count": 9}]},
            {"tag_name": "v1", "assets": [{"name": "s-1.exe", "download_count": 60},
                                          {"name": "x.exe", "download_count": 8}]}]
    info = WD.fetch(lambda url: data)
    assert (info["total"], info["latest"], info["tag"], info["releases"]) == (73, 5, "v2", 2)
    assert info["users"] == 3 and info["opens"] == 9
    assert "<b>73</b>" in WD.text(info) and "ผู้ใช้งานสะสม <b>3</b>" in WD.text(info)
    assert "ออฟไลน์" in WD.text(None)

    class St(dict):
        def value(self, k, d=None):
            return self.get(k, d)

        def setValue(self, k, v):
            self[k] = v
    hits = []
    st = St()
    assert WD.ping(st, "2", hits.append, opening=False) == ["usage-install.txt"]
    assert WD.ping(st, "2", hits.append, opening=False) == []      # once per computer
    assert hits == [WD.ASSET.format(version="2", name="usage-install.txt")]
    assert WD.ping(st, "dev", hits.append) == []


def test_model_opacity_slider_and_show_everything():
    import pytest
    pytest.importorskip("PySide6.QtWidgets")
    from PySide6.QtWidgets import QApplication

    from core.history import History
    from core.scene import Scene
    from plugins.wanic_building import BuildingPanel
    from views.viewport import model_opacity
    QApplication.instance() or QApplication([])

    class Vp:
        def __init__(self, scene):
            self.scene, self.history = scene, History(scene)

        def update(self):
            pass

    class App:
        def __init__(self, scene):
            self.scene, self.viewport, self.window = scene, Vp(scene), object()
            self.data = None

        def document_data(self, default=None):
            return default if self.data is None else self.data

        def set_document_data(self, value):
            self.data = value

    scene = Scene()
    app = App(scene)
    panel = BuildingPanel(app)
    assert model_opacity(app.viewport) is None
    panel.opacity_slider.setValue(60)
    assert math.isclose(app.viewport.model_opacity, 0.4)
    assert math.isclose(model_opacity(app.viewport), 0.4)
    assert panel.opacity_label.text() == "60 %"
    for ly in scene.layers:
        ly.visible = False
    panel.show_everything()
    assert all(ly.visible for ly in scene.layers)
    assert panel.opacity_slider.value() == 0 and model_opacity(app.viewport) is None


def test_per_tonne_prices_and_plaster_cement_are_read_right():
    d = _data()
    d["prices"] = {"RB6": 21400, "RB9": 21000, "ปูนซีเมนต์ผสม (มอก. 80/2566)": 2.8,
                   "ทรายหยาบ": 480, "หินเบอร์ 1-2": 560, "ทรายละเอียด": 450,
                   "น้ำยาผสมปูนก่อ": 40, "ลวดผูกเหล็ก": 45, "ตะปูตอกไม้ 3\"": 38}
    p = Q.prices_of(d)
    assert p["RB6"] == 21.4 and p["ทรายหยาบ"] == 480        # per tonne → per kg only
    band, _n = Q.recipe_price("4.1", p)
    plaster, _n = Q.recipe_price("7.2", p)
    assert 20 < band < 200 and 20 < plaster < 200
    r = Q.compute(d)
    t = r["totals"]
    assert t["F"] > 1.0 and math.isclose(t["with_f"], round(t["total"] * t["F"], 2))
    for ln in r["lines"]:
        if ln["desc"].startswith(("เสาเอ็นและคานทับหลัง", "ฉาบปูนเรียบ")):
            assert 1 < ln["mat"] < 200, ln["desc"]
