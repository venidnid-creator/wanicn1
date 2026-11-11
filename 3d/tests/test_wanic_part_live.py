# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
"""A stretched part reads its new size, concrete and price; a click that
only selects does not make the panels re-read the model."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QMatrix4x4, QVector3D

from core import wanic_building as B
from core import wanic_partprice as P
from core.history import ScaleGroupCommand


def _column():
    d = B.default_data()
    d["floors"][0]["rooms"] = [dict(name="ห้องนอน", x=0, y=0, w=4, d=4)]
    groups, _c = B.build(d, ("structure",))
    return next(g for g in groups if g.ext[B.EXT_KEY]["kind"] == "column")


def _row(g, key):
    return dict(map(tuple, g.ext[B.EXT_KEY]["info"]))[key]


class _Scene:
    version = 0


def test_a_stretched_copy_reads_its_own_height_volume_and_price():
    col = _column()
    assert _row(col, "ขนาด") == "0.20 × 0.20 ม. สูง 3.00 ม."
    before = P._money(_row(col, "รวม"))
    col.xform = QMatrix4x4()                       # a copy sharing its definition
    m = QMatrix4x4()
    m.scale(1.0, 1.0, 1.5)                         # pulled up to 4.50 m
    col.xform = m
    rows = dict(map(tuple, P.live_rows(col)))
    assert rows["ขนาด"] == "0.20 × 0.20 ม. สูง 4.50 ม."
    assert rows["คอนกรีต"] == "0.180 ลบ.ม."
    assert abs(P._money(rows["รวม"]) - before * 1.5) < 0.02


def test_scaling_writes_the_new_rows_and_undo_puts_them_back():
    col = _column()
    col.xform = QMatrix4x4()
    cmd = ScaleGroupCommand(col, QVector3D(0, 0, 0), 2.0)
    cmd.do(_Scene)
    assert _row(col, "คอนกรีต") == "0.960 ลบ.ม."           # 0.12 × 2³
    cmd.undo(_Scene)
    assert _row(col, "คอนกรีต") == "0.120 ลบ.ม."


def test_a_selection_click_is_not_a_document_change():
    from views.extension_api import ExtensionApp
    from PySide6.QtCore import QObject, Signal

    class VP(QObject):
        sceneVersionChanged = Signal(int)

    from core.scene import Scene
    vp = VP()
    vp.scene = Scene()
    api = ExtensionApp.__new__(ExtensionApp)

    class W:
        viewport = vp
    api._window = W
    calls = []
    api.on_document_changed(lambda: calls.append(1))
    vp.sceneVersionChanged.emit(1)
    vp.scene.bump_view()                          # a click selecting something
    vp.sceneVersionChanged.emit(2)
    assert len(calls) == 1
    vp.scene.version += 1                         # an edit
    vp.sceneVersionChanged.emit(3)
    assert len(calls) == 2
