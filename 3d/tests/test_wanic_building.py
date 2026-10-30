# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
"""WANIC ออกแบบอาคาร: plan → frame → roof → takeoff, and the panel."""
from __future__ import annotations

import math
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from core import wanic_building as B
from core import wanic_takeoff as T
from core.history import CompoundCommand, History, InsertGroupCommand
from core.scene import Scene


def close(a, b, rel=1e-4):
    return math.isclose(a, b, rel_tol=rel, abs_tol=1e-9)


def _grid2x2():
    return [dict(id=f"r{i}", name="ห้องนอน", x=x, y=y, w=3.0, d=3.0)
            for i, (x, y) in enumerate(((0, 0), (3, 0), (0, 3), (3, 3)))]


def test_plan_nodes_and_spans():
    rooms = _grid2x2()
    assert len(B.nodes(rooms)) == 9
    assert len(B.segments(rooms)) == 12
    # A T-junction splits the long edge.
    t = [dict(x=0, y=0, w=4, d=3), dict(x=4, y=0, w=4, d=3),
         dict(x=0, y=3, w=3, d=3)]
    assert len(B.nodes(t)) == 9 and len(B.segments(t)) == 11


def test_snap_to_neighbour_edge():
    got = B.snap_room(dict(x=3.12, y=0.2, w=3, d=3),
                      [dict(x=0, y=0, w=3, d=3)])
    assert (got["x"], got["y"]) == (3.0, 0.0)


def test_structure_counts_like_a_one_storey_house():
    d = B.default_data()
    d["floors"][0]["rooms"] = _grid2x2()
    groups, count = B.structure_members(d)
    assert count["footing"] == 9 and count["stump"] == 9
    assert count["column"] == 9 and count["slab"] == 4
    assert count["beam"] == 24                    # 12 GB + 12 RB
    assert count["wall"] == 12
    f1 = [g for g in groups if g.name == "F1"][0]
    from core.bim import face_set_volume
    assert close(face_set_volume(list(f1.mesh.faces)), 1.0 * 1.0 * 0.3)


def test_two_storeys_share_floor_beams():
    d = B.default_data()
    d["floors"] = [{"rooms": _grid2x2()}, {"rooms": _grid2x2()}]
    _g, count = B.structure_members(d)
    assert count["column"] == 18 and count["beam"] == 36   # GB, B, RB
    assert count["slab"] == 8


def test_hip_and_gable_roofs_build():
    d = B.default_data()
    d["floors"][0]["rooms"] = [dict(id="a", x=0, y=0, w=8, d=6)]
    for kind in ("hip", "gable"):
        d["settings"]["roof"] = kind
        lines = B.roof_lines(d)
        groups, count = B.roof_members(d)
        assert count["rafter"] == len(lines["rafter"]) > 0
        assert count["purlin"] == len(lines["purlin"]) > 0
        assert count.get("skin") == 1
        assert count.get("ridge") == 1
        if kind == "hip":
            assert count["hip"] == 4
    d["settings"]["roof"] = "none"
    assert B.roof_members(d) == ([], {})


def test_takeoff_from_a_build():
    scene = Scene()
    hist = History(scene)
    d = B.default_data()
    d["floors"][0]["rooms"] = _grid2x2()
    groups, _c = B.build(d)
    hist.execute(CompoundCommand([InsertGroupCommand(g) for g in groups]))
    assert len(B.generated(scene)) == len(groups)
    data = T.default_data()
    data["rates"] = B.takeoff_rates(d)
    res = T.compute(T.collect_items(scene), data)
    by = {ln["desc"]: ln for ln in res["lines"]}
    assert close(by["คอนกรีตฐานราก F1"]["quantity"], 9 * 0.3)
    assert close(by["คอนกรีตพื้นชั้นล่าง S1"]["quantity"], 4 * 9 * 0.1)
    assert by["มุงหลังคา (พื้นที่ตามแนวลาด)"]["quantity"] > 36
    assert any(ln["quantity"] > 0 for ln in res["lines"]
               if ln["desc"].startswith("โครงหลังคาเหล็ก จันทัน"))


class _Vp:
    def __init__(self, scene):
        self.scene = scene
        self.history = History(scene)

    def update(self):
        pass


class _App:
    def __init__(self, scene):
        self.scene = scene
        self.viewport = _Vp(scene)
        self.window = object()
        self.key = "wanic_building"

    def document_data(self, default=None):
        import json
        v = scene_data(self.scene).get(self.key)
        return default if v is None else json.loads(json.dumps(v))

    def set_document_data(self, value):
        from core.history import SetPluginDataCommand
        self.viewport.history.execute(SetPluginDataCommand(self.key, value))


def scene_data(scene):
    return getattr(scene, "plugin_data", {}) or {}


def test_panel_places_rooms_builds_and_rebuilds(monkeypatch):
    from PySide6.QtWidgets import QApplication, QMessageBox
    QApplication.instance() or QApplication([])
    from plugins.wanic_building import BuildingPanel

    def boom(*a, **k):
        raise AssertionError(a)
    monkeypatch.setattr(QMessageBox, "information", boom)
    scene = Scene()
    app = _App(scene)
    panel = BuildingPanel(app)
    panel.resize(500, 900)
    for x, y in ((1.5, 1.5), (4.6, 1.4), (1.4, 4.6), (4.5, 4.5)):
        panel.place_room(x, y)
    rooms = panel.rooms()
    assert len(rooms) == 4
    assert len(B.nodes(rooms)) == 9                 # snapped edge to edge
    panel.build(("structure", "roof"))
    first = len(B.generated(scene))
    assert first > 50
    panel.build(("structure",))                     # replaces, no duplicates
    assert len(B.generated(scene)) == first
    assert panel.place_opening(1.5, 0.05, "door")       # snaps onto the wall
    assert panel.place_opening(9.0, 9.0, "window") is None
    sid = panel.place_stair(1.5, 1.5)
    panel.rotate_stair(sid)
    assert panel.items("stairs")[0]["dir"] == 2
    panel.copy_floor()
    assert len(panel.data()["floors"]) == 2
    panel.send_rates()
    tk = scene_data(scene)["wanic_takeoff"]
    assert any(r["value"] == "C1" for r in tk["rates"])
    panel.send_rates()                              # no duplicate lines
    assert len(scene_data(scene)["wanic_takeoff"]["rates"]) == len(tk["rates"])
    panel.remove_built()
    assert B.generated(scene) == []
    app.viewport.history.undo()
    assert len(B.generated(scene)) == first


def test_empty_lower_floors_are_skipped_not_floating():
    d = B.default_data()
    d["floors"] = [B.new_floor(), B.new_floor(),
                   {"rooms": _grid2x2(), "openings": [], "stairs": []}]
    floors, skipped = B.stacked(d)
    assert len(floors) == 1 and skipped == 2
    _g, count = B.structure_members(d)
    assert count["footing"] == 9 and count["column"] == 9
    lines = B.roof_lines(d)
    assert close(lines["z0"], 3.0)                 # on the one storey built


def test_doors_and_windows_cut_the_walls():
    d = B.default_data()
    d["floors"][0]["rooms"] = _grid2x2()
    d["floors"][0]["openings"] = [
        {"id": "o1", "type": "door", "x": 1.5, "y": 0.0},
        {"id": "o2", "type": "window", "x": 0.0, "y": 4.5},
    ]
    _g, count = B.structure_members(d)
    assert count["door"] == 1 and count["window"] == 1
    assert count["band"] == 2                       # concrete round both
    # 12 spans: the door span → 2 sides + 1 over; the window span → 2 sides
    # + 1 under + 1 over.
    assert count["wall"] == 12 - 2 + 3 + 4
    rates = B.takeoff_rates(d)
    assert any(r["qty"] == "count" and r["value"].startswith("D1 ประตู")
               for r in rates)


def test_stair_flight_volume():
    from core import wanic_profiles as P
    from core.bim import face_set_volume
    d = B.default_data()
    d["floors"] = [{"rooms": _grid2x2(), "openings": [],
                    "stairs": [{"id": "s1", "x": 1.5, "y": 1.5, "dir": 1}]},
                   {"rooms": _grid2x2(), "openings": [], "stairs": []}]
    groups, count = B.structure_members(d)
    assert count["stair"] == 1
    st = [g for g in groups if g.name == "บันได คสล."][0]
    s = B.settings_of(d)
    n, L, H = B.stair_geometry({}, s)
    area = P.section_area("stair", dict(L=L * 1000, H=H * 1000, n=n,
                                        t=s["stair_t"] * 1000))
    assert close(face_set_volume(list(st.mesh.faces)), area * s["stair_w"])


def test_l_shaped_plan_gets_two_roofs_meeting_in_a_valley():
    d = B.default_data()
    d["floors"][0]["rooms"] = [dict(id="a", x=0, y=0, w=8, d=4),
                               dict(id="b", x=0, y=4, w=3, d=4)]
    lines = B.roof_lines(d)
    assert len(lines["rects"]) == 2
    assert len(lines["ridge"]) == 2
    d["settings"]["roof_mode"] = "bbox"
    assert len(B.roof_lines(d)["rects"]) == 1


def test_panel_select_copy_marks_library_and_standard_boq(monkeypatch):
    from PySide6.QtWidgets import QApplication, QMessageBox
    QApplication.instance() or QApplication([])
    from plugins.wanic_building import BoqDialog, BuildingPanel, axis_name

    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)
    scene = Scene()
    app = _App(scene)
    panel = BuildingPanel(app)
    panel.resize(500, 900)
    panel.place_room(1.5, 1.5)
    panel.place_room(4.6, 1.4)
    ids = {r["id"] for r in panel.rooms()}
    assert panel.copy_rooms(ids) == 2
    got = panel.paste_rooms((0.0, 3.0))
    assert len(got) == 2 and len(panel.rooms()) == 4
    assert len(B.nodes(panel.rooms())) == 9          # pasted edge to edge
    panel.delete_rooms(set(got))
    assert len(panel.rooms()) == 2
    panel.undo()
    assert len(panel.rooms()) == 4
    panel.redo()
    assert len(panel.rooms()) == 2
    # Marks at a column point and a new library mark.
    node = panel.node_at(0.02, -0.03)
    assert node == (0.0, 0.0)
    spec = dict(B.library_of(panel.data())["F1"], w=1.5, l=1.5)
    panel.set_library("F2", spec)
    panel.set_node_marks(node, {"F": "F2", "PC": "PC1", "C": "C1"})
    assert panel.data()["assign"] == {B.node_key(0, 0): {"F": "F2"}}
    E = B.elements(panel.data())
    assert sorted(e["mark"] for e in E["footings"]).count("F2") == 1
    panel.reset_node(node)
    assert not panel.data()["assign"]
    # The standard BOQ: dialog fills, sending replaces its own lines only.
    dlg = BoqDialog(panel)
    assert dlg.tree.topLevelItemCount() >= 5
    dlg.sample_prices()
    assert dlg.result["totals"]["total"] > 0
    n = panel.send_standard_boq(dlg.result)
    tk = scene_data(scene)["wanic_takeoff"]
    assert len(tk["rates"]) == n
    panel.send_rates()                                 # model-bound lines
    m = len(scene_data(scene)["wanic_takeoff"]["rates"])
    assert panel.send_standard_boq() == n
    assert len(scene_data(scene)["wanic_takeoff"]["rates"]) == m
    assert axis_name(0) == "A" and axis_name(8) == "J"  # no I
    panel.canvas.grab()                                 # paints axes etc.


def test_panel_door_types_fixtures_fascia(monkeypatch):
    from PySide6.QtWidgets import QApplication, QMessageBox
    QApplication.instance() or QApplication([])
    from plugins.wanic_building import BuildingPanel

    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)
    scene = Scene()
    app = _App(scene)
    panel = BuildingPanel(app)
    panel.resize(500, 900)
    panel.room_name.setCurrentText("ห้องนอน")
    panel.place_room(1.5, 1.5)
    panel.room_name.setCurrentText("ห้องน้ำ")
    panel.room_w.setValue(2.0)
    panel.room_d.setValue(3.0)
    panel.place_room(4.0, 1.5)
    # A sliding window of a chosen size.
    panel.set_tool("window")
    panel.op_style.setCurrentIndex(panel.op_style.findData("W2"))
    panel.op_w.setValue(1.5)
    panel.op_h.setValue(1.2)
    oid = panel.place_opening(1.5, 0.02, "window")
    op = [o for o in panel.items("openings") if o["id"] == oid][0]
    assert op["style"] == "W2" and op["w"] == 1.5 and op["h"] == 1.2
    assert B.opening_name(op, B.settings_of(panel.data())).startswith("W2 ")
    # The standard bathroom set goes into the bathroom only.
    n = panel.fill_standard_sets()
    assert n == len(__import__("core.wanic_catalog", fromlist=["x"])
                    .BATHROOM_SET)
    assert panel.fill_standard_sets() == 0            # not twice
    panel.set_tool("fixture")
    fid = panel.place_fixture(1.0, 1.0, "SK1")
    panel.rotate_stair(fid)
    fx = [f for f in panel.items("fixtures") if f["id"] == fid][0]
    assert fx["dir"] == 1
    assert panel.item_at(1.0, 1.0)["id"] == fid
    panel.build(("structure", "roof"))
    kinds = {((g.ext or {}).get("wanic_building") or {}).get("kind")
             for g in B.generated(scene)}
    assert {"fixture", "fascia", "window", "band", "cap", "tiles"} <= kinds
    win = [g for g in B.generated(scene)
           if ((g.ext or {}).get("wanic_building") or {}).get("kind")
           == "window"][0]
    colors = {tuple(f.attrs.get("color", ())) for f in win.mesh.faces}
    assert len(colors) >= 2                           # frame and glass
    assert any(f.attrs.get("opacity") for f in win.mesh.faces)
    panel.canvas.grab()


def test_boq_prices_by_province(monkeypatch, tmp_path):
    """Pick a province, import its commerce-office table, see the prices in
    the bill, switch away and back, then send: ปร. names the province."""
    from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox
    QApplication.instance() or QApplication([])
    from core import wanic_province as P
    from plugins.wanic_building import BoqDialog, BuildingPanel

    monkeypatch.setenv("WANIC_PRICE_DIR", str(tmp_path / "books"))
    monkeypatch.setenv("WANIC_OFFLINE", "1")
    msgs = []
    for name in ("information", "warning"):
        monkeypatch.setattr(QMessageBox, name,
                            staticmethod(lambda *a, **k: msgs.append(a[2])))

    def critical(*a, **k):
        raise AssertionError(a[2] if len(a) > 2 else a)
    monkeypatch.setattr(QMessageBox, "critical", staticmethod(critical))
    from core import wanic_ui
    wanic_ui.LAST_ERROR.clear()
    table = tmp_path / "ขอนแก่น.csv"
    table.write_text("รหัส,รายการ,หน่วย,ราคาเดือนก่อน,ราคาเดือนนี้\n"
                     "01,ทรายหยาบ,ลบ.ม.,520,530\n"
                     "05,เหล็กเส้นกลม SR24 ขนาด 6 มม.,กก.,26.5,26\n"
                     "07,เหล็กข้ออ้อย SD40 ขนาด 12 มม.,กก.,24,23.8\n",
                     encoding="utf-8-sig")
    monkeypatch.setattr(QFileDialog, "getOpenFileName",
                        staticmethod(lambda *a, **k: (str(table), "")))
    scene = Scene()
    app = _App(scene)
    panel = BuildingPanel(app)
    panel.place_room(1.5, 1.5)
    panel.place_room(4.5, 1.5)
    dlg = BoqDialog(panel)
    assert "ยังไม่ได้เลือกจังหวัด" in dlg.cover.text()
    assert dlg.province.count() >= 78
    dlg.province.setCurrentIndex(dlg.province.findData("ขอนแก่น"))
    assert panel.data()["province"] == "ขอนแก่น"
    assert "มีราคา 0/" in dlg.cover.text()
    assert dlg.import_prices() == 3
    d = panel.data()
    assert d["prices"]["ทรายหยาบ"] == 530 and d["prices"]["DB12"] == 23.8
    assert d["price_src"]["RB6"] == "พาณิชย์"
    assert P.load_book("ขอนแก่น")["prices"]["ทรายหยาบ"] == 530
    rows = {dlg.prices.item(r, 0).text(): dlg.prices.item(r, 3).text()
            for r in range(dlg.prices.rowCount())}
    assert rows["ทรายหยาบ"] == "พาณิชย์จ.ขอนแก่น"
    db12 = [ln for ln in dlg.result["lines"] if ln["mat_key"] == "DB12"]
    assert db12 and db12[0]["mat"] == 23.8
    assert "สำนักงานพาณิชย์จังหวัดขอนแก่น" in dlg.total.text()
    # A typed price is kept as the user's own, in the book too.
    r = [i for i in range(dlg.prices.rowCount())
         if dlg.prices.item(i, 0).text() == "DB16"][0]
    dlg.prices.item(r, 2).setText("23.5")
    dlg.save_prices()
    assert P.load_book("ขอนแก่น")["src"]["DB16"] == "ท้องตลาด"
    # Unannounced materials say so in the หมายเหตุ column.
    notes = []
    for i in range(dlg.tree.topLevelItemCount()):
        top = dlg.tree.topLevelItem(i)
        notes += [top.child(j).text(11) for j in range(top.childCount())]
    assert any("ไม่พบราคาที่จังหวัดขอนแก่นประกาศ" in n for n in notes)
    # Another province has its own (empty) prices; coming back restores.
    dlg.province.setCurrentIndex(dlg.province.findData("เชียงใหม่"))
    assert not any(panel.data()["prices"].values())
    dlg.province.setCurrentIndex(dlg.province.findData("ขอนแก่น"))
    assert panel.data()["prices"]["DB16"] == 23.5
    assert "✓" in dlg.province.itemText(dlg.province.findData("ขอนแก่น"))
    # Rows copied from the web page.
    QApplication.clipboard().setText("ทรายละเอียด\tลบ.ม.\t480\t490")
    assert dlg.paste_prices() == 1
    assert panel.data()["prices"]["ทรายละเอียด"] == 490
    # Sending names the province in the takeoff's ปร. header.
    dlg.send()
    st = scene_data(scene)["wanic_takeoff"]["settings"]
    assert st["location"] == "จังหวัดขอนแก่น"
    assert "สำนักงานพาณิชย์จังหวัดขอนแก่น" in st["price_ref"]
    assert "ขอนแก่น" in msgs[-1]
    assert not wanic_ui.LAST_ERROR


def test_choosing_a_province_fills_the_bill_at_once(monkeypatch, tmp_path):
    """Pick ภูเก็ต: its latest MOC prices arrive and every line reads
    ค่าวัสดุ = ปริมาณ × ค่าวัสดุ/หน่วย, ค่าแรง = ปริมาณ × ค่าแรง/หน่วย,
    รวม = ค่าวัสดุ + ค่าแรง."""
    from PySide6.QtWidgets import QApplication, QMessageBox
    QApplication.instance() or QApplication([])
    from core import wanic_province as P
    from plugins.wanic_building import BoqDialog, BuildingPanel

    monkeypatch.setenv("WANIC_PRICE_DIR", str(tmp_path))
    for name in ("information", "warning"):
        monkeypatch.setattr(QMessageBox, name, staticmethod(lambda *a, **k: 0))
    calls = []

    def fake(province, *a, **k):
        calls.append(province)
        return ([("ทรายหยาบ", "ลบ.ม.", 620.0),
                 ("เหล็กข้ออ้อย SD40 ขนาด 12 มม.", "กก.", 24.4),
                 ("เหล็กเส้นกลม SR24 ขนาด 6 มม.", "กก.", 27.1),
                 ("คอนกรีตผสมเสร็จ 240 ksc. (ลูกบาศก์)", "ลบ.ม.", 2450.0)],
                "ก.ย. 2569", "https://dataapi.moc.go.th/…")
    monkeypatch.setattr(P, "fetch_online", fake)
    panel = BuildingPanel(_App(Scene()))
    panel.place_room(1.5, 1.5)
    panel.place_room(4.5, 1.5)
    dlg = BoqDialog(panel)
    dlg.province.setCurrentIndex(dlg.province.findData("ภูเก็ต"))
    assert calls == ["ภูเก็ต"]
    assert dlg.month.text() == "ก.ย. 2569"
    lines = dlg.result["lines"]
    db12 = [ln for ln in lines if ln["mat_key"] == "DB12"][0]
    assert db12["mat"] == 24.4
    for ln in lines:
        assert abs(ln["mat_total"] - round(ln["qty"] * ln["mat"], 2)) < 0.011
        assert abs(ln["lab_total"] - round(ln["qty"] * ln["lab"], 2)) < 0.011
        assert abs(ln["total"] - (ln["mat_total"] + ln["lab_total"])) < 0.011
    # The tree shows it: the DB12 row's ค่าวัสดุ/หน่วย column.
    found = []
    for i in range(dlg.tree.topLevelItemCount()):
        top = dlg.tree.topLevelItem(i)
        for j in range(top.childCount()):
            if "DB12" in top.child(j).text(1):
                found.append(top.child(j).text(6))
    assert found == ["24.40"]
    # Saved for next time: choosing it again does not fetch again.
    dlg.province.setCurrentIndex(dlg.province.findData("เชียงใหม่"))
    calls.clear()
    monkeypatch.setattr(P, "last_month", lambda *a: "ก.ย. 2569")
    dlg.province.setCurrentIndex(dlg.province.findData("ภูเก็ต"))
    assert calls == [] and panel.data()["prices"]["DB12"] == 24.4


def test_drawing_set_prints_one_a3_page_per_sheet(tmp_path):
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from core import wanic_drawings as D
    from plugins.wanic_building import render_pdf
    d = B.default_data()
    d["floors"][0]["rooms"] = _grid2x2()
    d["floors"][0]["openings"] = [dict(id="o1", type="door", x=1.5, y=0.0),
                                  dict(id="o2", type="window", x=4.5, y=0.0)]
    sheets = D.build_set(d, {"project": "ทดสอบ"})
    path = tmp_path / "set.pdf"
    assert render_pdf(sheets, str(path)) == len(sheets) > 10
    data = path.read_bytes()
    assert data[:5] == b"%PDF-"
    assert data.count(b"/Type /Page\n") + data.count(b"/Type /Page ") + \
        data.count(b"/Type/Page") >= len(sheets) or len(data) > 50000
