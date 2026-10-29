# SPDX-License-Identifier: GPL-3.0-or-later
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
    # 12 spans: the door span → 2 sides + 1 over; the window span → 2 sides
    # + 1 under + 1 over.
    assert count["wall"] == 12 - 2 + 3 + 4
    rates = B.takeoff_rates(d)
    assert any(r["qty"] == "count" and r["value"].startswith("ประตู")
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
