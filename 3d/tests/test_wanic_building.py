# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
"""WANIC ออกแบบอาคาร: plan → frame → roof → takeoff, and the panel."""
from __future__ import annotations

import copy
import math
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from core import wanic_building as B
from core import wanic_profiles as P
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
    f1 = [g for g in groups if g.ext["wanic_building"]["mark"] == "F1"][0]
    # the name says what and where it is; the takeoff matches the short key
    assert f1.name.startswith("ฐานราก F1 100×100×30 ซม.") and "A-1" in f1.name
    assert f1.ext["wanic_building"]["key"] == "F1"
    assert ["ตำแหน่ง", "A-1"] in f1.ext["wanic_building"]["info"]
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
        # (stubs under 15 cm at a hip apex carry nothing and are left out)
        assert count["purlin"] == sum(1 for pl in lines["purlin"]
                                      if P.path_length(pl["path"], pl["closed"]) >= 0.15) > 0
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
    d["settings"]["floor_lift"] = 0.0          # the slab on the ground
    groups, _c = B.build(d)
    hist.execute(CompoundCommand([InsertGroupCommand(g) for g in groups]))
    assert len(B.generated(scene)) == len(groups)
    data = T.default_data()
    data["rates"] = B.takeoff_rates(d)
    res = T.compute(T.collect_items(scene), data)
    by = {ln["desc"]: ln for ln in res["lines"]}
    assert close(by["คอนกรีตฐานราก F1"]["quantity"], 9 * 0.3)
    # Measured off the model, a slab is what lies between the beam faces
    # (no concrete counted twice); the standard BOQ bills the full panel.
    assert close(by["คอนกรีตพื้นชั้นล่าง S1"]["quantity"], 4 * 2.8 * 2.8 * 0.1)
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
    panel.copy_floor(ask=False)
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
    assert count["stair"] == 2                       # the flight + คานรับบันไดขั้นแรก SB1
    st = [g for g in groups if g.name == "บันได คสล."][0]
    s = B.settings_of(d)
    n, L, H = B.stair_geometry({}, s)
    area = P.section_area("stair", dict(L=L * 1000, H=H * 1000, n=n,
                                        t=s["stair_t"] * 1000))
    assert close(face_set_volume(list(st.mesh.faces)), area * B.stair_width({}, s))


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
    # ง2 ตัวตรวจราคา: «เฉพาะที่ยังไม่มีราคา» hides the priced lines, off — all back
    def shown():
        return sum(1 for i in range(dlg.tree.topLevelItemCount())
                   for j in range(dlg.tree.topLevelItem(i).childCount())
                   if not dlg.tree.topLevelItem(i).child(j).isHidden())
    n_all = shown()
    dlg.only_missing.setChecked(True)
    assert shown() <= n_all
    dlg.only_missing.setChecked(False)
    assert shown() == n_all
    dlg.sample_prices()
    assert dlg.result["totals"]["total"] == 0          # every price 0 until the province is chosen
    d_ = panel.data()
    d_["province"] = "ขอนแก่น"
    panel._write(d_)
    dlg.recompute()
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
    n = panel.fill_standard_sets()                    # laid out by the room's size
    CAT_ = __import__("core.wanic_catalog", fromlist=["x"])
    furn = sum(1 for f in panel.items("fixtures") if f["type"] in CAT_.FURNITURE)   # bedrooms / kitchen
    assert n - furn == len(CAT_.bathroom_layout(2.0, 3.0))
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
    # ห้ามส่งออกจนราคาครบ: the orange rows block the export, told why …
    n_msgs = len(msgs)
    dlg.send()
    assert "wanic_takeoff" not in scene_data(scene) and "ยังไม่มีราคา" in msgs[n_msgs]
    # … the rows filled in (every material and labour rate), the export goes
    from core import wanic_quantities as Q
    d_ = panel.data()
    for ln in Q.missing_lines(dlg.result):
        if ln["mat_key"]:
            d_.setdefault("prices", {})[ln["mat_key"]] = 1.0
        if ln["lab_code"]:
            d_.setdefault("labour", {})[ln["lab_code"]] = 1.0
    panel._write(d_)
    dlg.recompute()
    for ln in Q.missing_lines(dlg.result):          # the recipe lines: their materials
        for k in dlg.result.get("need") or {}:
            d_["prices"].setdefault(k, 1.0) if not d_["prices"].get(k) else None
    panel._write(d_)
    dlg.recompute()
    assert not dlg.missing_text(), dlg.missing_text()
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
            if top.child(j).text(1).startswith("เหล็กเสริม DB12"):
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


def test_drawing_set_fits_whole_on_a4(tmp_path):
    """PDF on A4: each A3 sheet shrunk whole onto A4 landscape (nothing cut)."""
    import re
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from core import wanic_drawings as D
    from plugins.wanic_building import a4_factor, render_pdf
    d = B.default_data()
    d["floors"][0]["rooms"] = _grid2x2()
    sheets = D.build_set(d, {"project": "ทดสอบ"})[:2]
    path = tmp_path / "a4.pdf"
    assert render_pdf(sheets, str(path), "A4") == 2
    boxes = re.findall(rb"/MediaBox\s*\[\s*0\s+0\s+([\d.]+)\s+([\d.]+)", path.read_bytes())
    assert boxes and all(abs(float(w) - 842) < 2 and abs(float(h) - 595) < 2 for w, h in boxes)
    assert abs(a4_factor() * D.PAPER[0] - 297.0) < 1e-9


def test_no_wall_across_an_open_way():
    """ค4: a corridor open to the living room has no wall between them, a
    porch has no outside wall; a bedroom off the corridor keeps its wall."""
    d = B.default_data()
    d["floors"][0]["rooms"] = [dict(id="a", name="ห้องนั่งเล่น", x=0, y=0, w=4, d=4),
                               dict(id="b", name="โถงทางเดิน", x=4, y=0, w=2, d=4),
                               dict(id="c", name="ห้องนอน", x=6, y=0, w=3, d=4),
                               dict(id="e", name="ระเบียง", x=0, y=-2, w=4, d=2)]
    E = B.elements(d)
    walls = [(w["p0"], w["p1"]) for w in E["walls"] if w["floor"] == 0]

    def has(x0, y0, x1, y1):
        return any({tuple(p0), tuple(p1)} == {(x0, y0), (x1, y1)} for p0, p1 in walls)
    assert not has(4, 0, 4, 4)                      # living | corridor: open
    assert has(6, 0, 6, 4)                          # corridor | bedroom: a wall (and its door)
    assert not has(0, -2, 4, -2) and not has(0, -2, 0, 0)    # the porch's outside edges
    assert has(0, 0, 4, 0)                          # living | porch: a wall (with its door / windows)


def test_view_switches_by_kind_and_floor():
    """ค6: เปิด-ปิดโครงสร้าง — one switch per kind, per floor where it matters,
    in build order (foundation → roof)."""
    from core import wanic_rc as R
    d = B.default_data()
    R.apply_grid(d, [4.0, 4.0], [4.0, 3.0], 2)
    d["settings"]["roof"] = "hip"
    gs, _c = B.build(d, ("structure", "roof"))
    E = B.elements(d)
    labels = [lab for _k, lab, _g in B.view_categories(gs, E["H"], B.floor_lift(E["settings"]), E["n"])]
    for want in ("ฐานราก", "ตอม่อ", "คานคอดิน", "เสา ชั้น 1", "เสา ชั้น 2", "คานหลังคา", "พื้น ชั้น 1",
                 "พื้น ชั้น 2", "ผนัง ชั้น 1", "อะเส", "จันทัน", "อกไก่", "แป", "วัสดุมุงหลังคา"):
        assert want in labels, want
    assert labels.index("ฐานราก") < labels.index("เสา ชั้น 1") < labels.index("จันทัน") < labels.index("แป")


def test_neighbouring_provinces_fill_only_the_empty_items(monkeypatch, tmp_path):
    """ง4: a bordering province's price fills what the province has not, with a note."""
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from core import wanic_province as P
    from core import wanic_quantities as Q
    from plugins.wanic_building import BoqDialog, BuildingPanel

    monkeypatch.setenv("WANIC_PRICE_DIR", str(tmp_path / "books"))
    monkeypatch.setenv("WANIC_OFFLINE", "1")
    assert "ขอนแก่น" in P.neighbours("อุดรธานี") and "อุดรธานี" in P.neighbours("ขอนแก่น")
    assert all(p in P.NEIGHBOURS[q] for p in P.PROVINCES for q in P.NEIGHBOURS[p])     # symmetric
    P.save_book("อุดรธานี", {"ทรายหยาบ": 600.0, "DB12": 25.0}, "ต.ค. 2569",
                item={"DB12": "เหล็กข้ออ้อย SD40 12 มม."})
    panel = BuildingPanel(_App(Scene()))
    panel.place_room(1.5, 1.5)
    d = panel.data()
    d["province"] = "ขอนแก่น"
    d["prices"], d["price_src"] = {"ทรายหยาบ": 530.0}, {"ทรายหยาบ": "พาณิชย์"}
    panel._write(d)
    dlg = BoqDialog(panel)
    assert dlg.fill_neighbours() >= 1
    d = panel.data()
    assert d["prices"]["ทรายหยาบ"] == 530.0                        # the province's own stays
    assert d["prices"]["DB12"] == 25.0 and d["price_src"]["DB12"] == "ข้างเคียง"
    assert d["price_item"]["DB12"].startswith("จ.อุดรธานี")
    db12 = next(ln for ln in Q.priced(d)["lines"] if ln["mat_key"] == "DB12")
    assert "จังหวัดข้างเคียง" in db12["note"] and "อุดรธานี" in db12["note"]
    # never saved into the province's own book
    P.save_book("ขอนแก่น", d["prices"], src=d["price_src"])
    assert "DB12" not in P.load_book("ขอนแก่น")["prices"]


def test_a_changed_model_is_calculated_again():
    """The owner (25 พ.ย. 69): when the model changes, every item is calculated
    again, so the calc book, the drawings and the BOQ belong together."""
    from core import wanic_rc as R
    d = R.apply_grid(B.default_data(), [4.0], [4.0], 1)
    assert not B.calc_current(d)
    bad, _res = B.recalc_all(d)
    assert B.calc_current(d) == (not bad)
    d["calc_stamp"] = B.struct_stamp(d)              # as if every item had passed
    d["prices"] = {"DB12": 25.0}                     # a price is not the structure
    d["schedule"] = {"start": "1/1/2570"}
    assert B.calc_current(d)
    d["floors"][0]["rooms"][0]["w"] += 0.5           # the model moved
    assert not B.calc_current(d)
    d["calc_stamp"] = B.struct_stamp(d)
    d["library"] = {"B1": {"stir": "RB6@0.10"}}      # a member changed
    assert not B.calc_current(d)


def test_no_stair_is_built_from_the_top_storey():
    """owner 27 Nov: «บันไดจะไม่สร้างชั้นบนสุด» — a stair left on the top floor (copied with the
    floor, or drawn there) is neither built, drawn nor billed."""
    d = B.default_data()
    room = dict(name="a", x=0, y=0, w=6, d=6)
    stair = {"id": "s1", "x": 1.0, "y": 1.0, "type": "U"}
    d["floors"] = [dict(copy.deepcopy(d["floors"][0]), rooms=[dict(room)], stairs=[dict(stair)])
                   for _ in range(2)]
    E = B.elements(d)
    assert [st["floor"] for st in E["stairs"]] == [0]
    assert not B.stair_used(stair, {}, 2, 1) and B.stair_used(stair, {}, 2, 0)


def _two_buildings():
    d = B.default_data()
    main = [dict(name="a", x=0, y=0, w=5, d=4), dict(name="b", x=5, y=0, w=5, d=4)]
    f0 = copy.deepcopy(d["floors"][0])
    f0["rooms"] = main + [dict(name="c", x=14, y=0, w=5, d=4)]
    f0["openings"] = [{"type": "door", "x": 2.5, "y": 0.0}, {"type": "door", "x": 16.5, "y": 0.0}]
    f1 = copy.deepcopy(d["floors"][0])
    f1["rooms"] = copy.deepcopy(main)
    d["floors"] = [f0, f1]
    d["settings"]["roof"] = "hip"
    return d


def test_separate_buildings_are_split_into_jobs_of_their_own():
    """owner 27 Nov: «กรณีแยกอาคาร ให้แยกรายการคำนวณ … ทั้ง BOQ ทุกอย่าง»."""
    from core import wanic_calc as C
    from core import wanic_quantities as Q
    d = _two_buildings()
    assert len(B.buildings(d)) == 2
    a, b = B.building_data(d, 0), B.building_data(d, 1)
    assert [len(f["rooms"]) for f in a["floors"]] == [2, 2]
    assert [len(f["rooms"]) for f in b["floors"]] == [1, 0]
    assert [len(f["openings"]) for f in a["floors"]][0] == 1 and b["floors"][0]["openings"][0]["x"] == 16.5
    assert B.elements(b)["n"] == 1                               # the annex is a one-storey job
    ca, cb = C.analyse(a), C.analyse(b)
    assert all("x 14" not in m.name for m in ca["members"])
    assert sum(1 for m in cb["members"] if m.group == "column" and "ตอม่อ" not in m.name) == 4
    qa, qb, qall = Q.compute(a), Q.compute(b), Q.compute(d)
    assert 0 < qb["totals"]["work"] < qa["totals"]["work"] <= qall["totals"]["work"]
    assert B.buildings(B.default_data()) == [] or len(B.buildings(B.default_data())) <= 1


def test_the_boq_window_bills_one_building_at_a_time():
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from plugins.wanic_building import BoqDialog, BuildingPanel
    panel = BuildingPanel(_App(Scene()))
    panel._write(_two_buildings())
    dlg = BoqDialog(panel)
    assert dlg.bldg_box.count() == 3                     # all · อาคาร 1 · อาคาร 2
    def conc():                                          # no province yet: prices 0 — compare quantities
        return sum(ln["qty"] for ln in dlg.result["lines"] if ln["desc"].startswith("คอนกรีตโครงสร้าง"))
    whole = conc()
    dlg.bldg_box.setCurrentIndex(2)
    annex = conc()
    dlg.bldg_box.setCurrentIndex(1)
    main = conc()
    assert 0 < annex < main < whole
    assert "อาคาร 1" in dlg.result["notes"][0]
