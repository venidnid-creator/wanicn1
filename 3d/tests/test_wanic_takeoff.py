# SPDX-License-Identifier: GPL-3.0-or-later
"""WANIC ถอดปริมาณ: measuring, matching, pricing, Thai baht text, exports."""
from __future__ import annotations

import io
import math
import os
import zipfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QVector3D

from core import wanic_takeoff as T
from core.bim import next_object_id, tag_faces
from core.edits import build_add_edges
from core.history import AddFaceCommand, History
from core.scene import Scene
from tools.base import ToolContext
from tools.pushpull import PushPullTool


class _Vp:
    def __init__(self, scene):
        self.scene = scene
        self.history = History(scene)

    def update(self):
        pass

    def set_hover(self, *_):
        pass

    def set_suppressed_faces(self, *_):
        pass

    def flash_status(self, *a, **k):
        pass


def V(x, y, z=0.0):
    return QVector3D(x, y, z)


def _wall(scene, vp, x0=0.0, length=4.0, thick=0.25, height=2.6):
    pts = [V(x0, 0), V(x0 + length, 0), V(x0 + length, thick), V(x0, thick)]
    vp.history.execute(build_add_edges(
        scene, [(pts[i], pts[(i + 1) % 4]) for i in range(4)],
        detect_faces=False, extra=[AddFaceCommand(list(pts))]))
    pp = PushPullTool()
    pp.hovered_face = scene.mesh.faces[-1]
    pp._hover_group = None
    pp.on_click(ToolContext(viewport=vp, world=V(0, 0), screen=QPointF(0, 0),
                            modifiers=Qt.NoModifier, snap=None))
    pp.extrusion = height
    pp._commit(vp)


def _tagged_wall_scene():
    scene = Scene()
    vp = _Vp(scene)
    _wall(scene, vp)                         # 4.0 × 0.25 × 2.6
    tag_faces(list(scene.mesh.faces), "IfcWall", "ผนังแกน A",
              next_object_id(scene))
    return scene


def test_tagged_wall_is_measured():
    items = T.collect_items(_tagged_wall_scene())
    wall = [i for i in items if i["ifc"] == "IfcWall"]
    assert len(wall) == 1
    w = wall[0]
    assert abs(w["volume"] - 4.0 * 0.25 * 2.6) < 1e-6
    assert abs(w["top_area"] - 4.0 * 0.25) < 1e-6
    assert math.isclose(w["side_area"], 2 * (4.0 + 0.25) * 2.6, rel_tol=1e-6)
    assert abs(w["length"] - 4.0) < 1e-6


def test_pricing_with_factor_and_vat():
    items = T.collect_items(_tagged_wall_scene())
    data = T.default_data()
    data["settings"].update(factor_f=1.1, vat=7)
    data["rates"] = [
        T.new_rate(id="a", by="ifc", value="IfcWall", qty="volume",
                   mat=2000, lab=500),
        T.new_rate(id="b", by="ifc", value="ifcwall", qty="side_area",
                   factor=2, mat=50),
    ]
    r = T.compute(items, data)
    vol = 4.0 * 0.25 * 2.6
    side = 2 * (4.0 + 0.25) * 2.6
    close = lambda a, b: math.isclose(a, b, rel_tol=1e-6)  # noqa: E731
    assert close(r["lines"][0]["total"], vol * 2500)
    assert close(r["lines"][1]["quantity"], side * 2)
    sub = vol * 2500 + side * 2 * 50
    assert close(r["grand"], sub * 1.1 * 1.07)
    assert set(r["status"].values()) == {"ok"}


def test_open_shell_reports_no_volume():
    scene = Scene()
    scene.mesh.add_face([V(0, 0), V(3, 0), V(3, 2), V(0, 2)])
    items = T.collect_items(scene)
    assert len(items) == 1 and items[0]["kind"] == "loose"
    data = T.default_data()
    data["rates"] = [T.new_rate(by="all", qty="volume", mat=1)]
    r = T.compute(items, data)
    assert r["lines"][0]["problems"] and r["lines"][0]["quantity"] == 0
    assert list(r["status"].values()) == ["problem"]
    data["rates"] = [T.new_rate(by="layer", value="Layer 0", qty="area",
                                mat=10)]
    r = T.compute(items, data)
    assert math.isclose(r["grand"], 6.0 * 10 * 1.07, rel_tol=1e-6)


def test_baht_text():
    assert T.baht_text(0) == "ศูนย์บาทถ้วน"
    assert T.baht_text(21) == "ยี่สิบเอ็ดบาทถ้วน"
    assert T.baht_text(1234.5) == "หนึ่งพันสองร้อยสามสิบสี่บาทห้าสิบสตางค์"
    assert T.baht_text(1000001) == "หนึ่งล้านเอ็ดบาทถ้วน"


def test_rates_csv_round_trip_and_xlsx():
    rates = T.sample_rates()
    rates[0]["mat"] = 123.5
    back = T.rates_from_csv(T.rates_to_csv(rates))
    assert [r["desc"] for r in back] == [r["desc"] for r in rates]
    assert back[0]["mat"] == 123.5 and back[7]["factor"] == 2.0
    items = T.collect_items(_tagged_wall_scene())
    data = T.default_data()
    data["rates"] = back
    r = T.compute(items, data)
    blob = T.boq_xlsx_bytes(r, data["settings"], items)
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        assert "xl/worksheets/sheet2.xml" in z.namelist()
        assert "ผนังก่ออิฐ" in z.read("xl/worksheets/sheet1.xml").decode()
    assert T.boq_csv(r, data["settings"]).startswith("﻿")
