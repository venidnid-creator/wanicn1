# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
"""WANIC โปรไฟล์: section outlines, sweeping along paths, schedule, panel."""
from __future__ import annotations

import math
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtGui import QVector3D

from core import wanic_profiles as P
from core.bim import face_set_volume
from core.edits import build_add_edges
from core.history import History, InsertGroupCommand
from core.scene import Scene


def close(a, b, rel=1e-4):
    return math.isclose(a, b, rel_tol=rel, abs_tol=1e-9)


@pytest.mark.parametrize("family", list(P.FAMILIES))
def test_every_preset_is_valid_and_has_area(family):
    for _label, params in P.FAMILIES[family]["presets"]:
        assert P.validate(family, params) is None
        assert P.section_area(family, params) > 0


def test_h_section_area_and_weight():
    p = dict(H=200, B=200, tw=8, tf=12)
    area = (2 * 200 * 12 + (200 - 24) * 8) / 1e6
    assert close(P.section_area("h", p), area)
    assert close(P.weight_per_m("h", p), area * 7850)
    assert P.describe("h", p) == "H 200×200×8×12"
    assert P.validate("h", dict(H=100, B=100, tw=6, tf=60))


def _volume(g):
    return face_set_volume(list(g.mesh.faces))


def test_straight_member_is_a_solid_of_the_right_volume():
    p = dict(H=200, B=100, tw=5.5, tf=8)
    g = P.build_member({"family": "h", "params": p,
                        "path": [(0, 0, 0), (6, 0, 0)], "closed": False})
    assert not isinstance(g, str), g
    vol = _volume(g)
    assert vol is not None and close(vol, P.section_area("h", p) * 6)
    rec = P.member_record(g)
    assert close(rec["length"], 6.0) and rec["family"] == "h"
    zs = [v.position.z() for v in g.mesh.vertices]
    assert close(max(zs), 0.1) and close(min(zs), -0.1)     # centred


def test_vertical_column_and_anchor():
    g = P.build_member({"family": "rect", "params": dict(b=300, h=300),
                        "anchor": "bc", "path": [(0, 0, 0), (0, 0, 3)]})
    assert not isinstance(g, str), g
    assert close(_volume(g), 0.09 * 3)


def test_bent_and_closed_paths():
    p = dict(b=200, h=400)
    g = P.build_member({"family": "rect", "params": p,
                        "path": [(0, 0, 0), (4, 0, 0), (4, 3, 0)]})
    assert not isinstance(g, str), g
    assert close(_volume(g), 0.08 * 7)       # mitred: centre-line length
    ring = P.build_member({"family": "rect", "params": p, "closed": True,
                           "path": [(0, 0, 0), (4, 0, 0), (4, 3, 0),
                                    (0, 3, 0)]})
    assert not isinstance(ring, str), ring
    assert close(_volume(ring), 0.08 * 14)
    assert close(P.member_record(ring)["length"], 14.0)


def test_bad_input_gives_thai_reason():
    assert isinstance(P.build_member({"family": "h", "params": dict(
        H=200, B=100, tw=5.5, tf=8), "path": [(0, 0, 0)]}), str)
    assert isinstance(P.build_member({"family": "box", "params": dict(
        H=50, B=50, t=30), "path": [(0, 0, 0), (1, 0, 0)]}), str)


def test_schedule_and_takeoff_length():
    scene = Scene()
    hist = History(scene)
    for y in (0.0, 2.0):
        g = P.build_member({"family": "lc", "params": dict(H=100, B=50, C=20,
                                                            t=2.3),
                            "path": [(0, y, 0), (5, y, 0), (5, y + 1, 0)]})
        hist.execute(InsertGroupCommand(g))
    rows = P.schedule(scene)
    assert len(rows) == 1 and rows[0]["count"] == 2
    assert close(rows[0]["length"], 12.0)
    assert rows[0]["weight"] > 0
    assert P.schedule_csv(rows).startswith("﻿")
    from core import wanic_takeoff as T
    items = [i for i in T.collect_items(scene) if i["kind"] == "group"]
    assert len(items) == 2 and all(close(i["length"], 6.0) for i in items)


class _Vp:
    def __init__(self, scene):
        self.scene = scene
        self.history = History(scene)

    def update(self):
        pass

    def flash_status(self, *a, **k):
        self.last = a


class _App:
    def __init__(self, scene):
        self.scene = scene
        self.viewport = _Vp(scene)


def test_panel_builds_from_selected_edges(monkeypatch):
    from PySide6.QtWidgets import QApplication, QMessageBox
    QApplication.instance() or QApplication([])
    from plugins.wanic_profiles import ProfilePanel, path_from_selection

    def boom(*a, **k):
        raise AssertionError(a[2] if len(a) > 2 else a)
    monkeypatch.setattr(QMessageBox, "information", boom)
    monkeypatch.setattr(QMessageBox, "warning", boom)
    scene = Scene()
    app = _App(scene)
    a, b, c = QVector3D(0, 0, 0), QVector3D(3, 0, 0), QVector3D(3, 2, 0)
    app.viewport.history.execute(build_add_edges(
        scene, [(a, b), (b, c)], detect_faces=False))
    scene.selection.update(scene.mesh.edges)
    pts, closed = path_from_selection(scene)
    assert len(pts) == 3 and not closed
    panel = ProfilePanel(app)
    i = panel.family.findData("u_ditch")
    panel.family.setCurrentIndex(i)
    panel.make_from_selection()
    groups = [g for g in scene.groups if P.member_record(g)]
    assert len(groups) == 1
    assert close(P.member_record(groups[0])["length"], 5.0)
    # Resize the selected member in place: one undoable step.
    scene.selection.clear()
    scene.selection.add(groups[0])
    panel.load_selected()
    panel.preset.setCurrentIndex(1)                 # ราง U 400×500
    panel.apply_to_selected()
    groups = [g for g in scene.groups if P.member_record(g)]
    assert len(groups) == 1
    assert P.member_record(groups[0])["params"]["b"] == 400
    app.viewport.history.undo()
    groups = [g for g in scene.groups if P.member_record(g)]
    assert P.member_record(groups[0])["params"]["b"] == 300
