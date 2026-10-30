# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
"""Click every button of every WANIC panel and dialog: none may fail.

File dialogs answer with files in a temporary folder, message boxes are
recorded, dialogs accept at once; an error inside any button is caught by
:func:`core.wanic_ui.safe` and fails the test with its traceback.
"""
from __future__ import annotations

import io
import json
import os
import zipfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from core import wanic_ui
from core.history import History, SetPluginDataCommand
from core.scene import Scene


class _Vp:
    def __init__(self, scene):
        self.scene = scene
        self.history = History(scene)
        self.flashed = []

    def update(self):
        pass

    def flash_status(self, *a, **k):
        self.flashed.append(a)


class _App:
    """The extension API the panels use, for one document key."""

    def __init__(self, scene, key, vp=None):
        self.scene = scene
        self.viewport = vp or _Vp(scene)
        self.window = object()
        self.key = key

    def document_data(self, default=None):
        v = (getattr(self.scene, "plugin_data", {}) or {}).get(self.key)
        return default if v is None else json.loads(json.dumps(v))

    def set_document_data(self, value):
        self.viewport.history.execute(SetPluginDataCommand(self.key, value))


@pytest.fixture
def ui(monkeypatch, tmp_path):
    from PySide6.QtWidgets import QApplication, QDialog, QFileDialog, \
        QMessageBox
    QApplication.instance() or QApplication([])
    saved, msgs = [], []
    monkeypatch.setenv("WANIC_PRICE_DIR", str(tmp_path / "books"))
    prices = tmp_path / "prices.csv"
    prices.write_text("วัสดุ,หน่วย,ราคา\nทรายหยาบ,ลบ.ม.,480\n",
                      encoding="utf-8-sig")
    state = {"open": str(prices), "answers": []}

    def save(parent=None, caption="", name="", flt="", *a, **k):
        base = os.path.basename(name or "out.dat")
        path = str(tmp_path / base)
        saved.append(path)
        return path, (flt.split(";;")[0] if flt else "")

    def opened(*a, **k):
        return state["open"], ""

    def note(*a, **k):
        msgs.append(a[2] if len(a) > 2 else a)
        return QMessageBox.Ok

    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(save))
    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(opened))
    for name in ("information", "warning"):
        monkeypatch.setattr(QMessageBox, name, staticmethod(note))

    def critical(*a, **k):
        raise AssertionError(a[2] if len(a) > 2 else a)
    monkeypatch.setattr(QMessageBox, "critical", staticmethod(critical))
    monkeypatch.setattr(
        QMessageBox, "question",
        staticmethod(lambda *a, **k: state["answers"].pop(0)
                     if state["answers"] else QMessageBox.No))
    monkeypatch.setattr(QDialog, "exec", lambda self: QDialog.Accepted)
    wanic_ui.LAST_ERROR.clear()
    return {"saved": saved, "msgs": msgs, "state": state, "tmp": tmp_path}


def _click_all(widget, skip=()):
    from PySide6.QtWidgets import QPushButton
    done = []
    for b in widget.findChildren(QPushButton):
        text = b.text()
        if any(s in text for s in skip) or not b.isEnabled():
            continue
        b.click()
        done.append(text)
        assert not wanic_ui.LAST_ERROR, (text, wanic_ui.LAST_ERROR[-1])
    return done


def _house(panel):
    panel.room_name.setCurrentText("ห้องนอน")
    panel.place_room(1.5, 1.5)
    panel.place_room(4.5, 1.5)
    panel.room_name.setCurrentText("ห้องน้ำ")
    panel.room_w.setValue(2.0)
    panel.room_d.setValue(3.0)
    panel.place_room(7.0, 1.5)
    panel.place_opening(1.5, 0.0, "door")
    panel.set_tool("window")
    panel.place_opening(4.5, 0.0, "window")


def test_every_button_of_the_building_panel_and_boq(ui):
    from plugins.wanic_building import BoqDialog, BuildingPanel
    scene = Scene()
    app = _App(scene, "wanic_building")
    panel = BuildingPanel(app)
    panel.resize(500, 900)
    _house(panel)
    panel.fill_standard_sets()
    # Build first (the delete/clear buttons come later in the list).
    panel.build(("structure", "roof"))
    done = _click_all(panel, skip=("ลบชั้น", "ล้างห้อง"))
    assert len(done) >= 12, done
    dlg = BoqDialog(panel)
    dlg.province.setCurrentIndex(dlg.province.findData("ขอนแก่น"))
    done = _click_all(dlg, skip=("เว็บ",))
    assert any("พาณิชย์จังหวัด" in t for t in done)
    assert any("Excel" in t for t in done)
    xlsx = [p for p in ui["saved"] if p.endswith(".xlsx")]
    assert xlsx and zipfile.is_zipfile(xlsx[-1])
    csvs = [p for p in ui["saved"] if p.endswith(".csv")]
    assert csvs
    tk = (scene.plugin_data or {}).get("wanic_takeoff")
    assert tk and any(str(r["id"]).startswith("std") for r in tk["rates"])
    assert tk["settings"]["location"] == "จังหวัดขอนแก่น"
    # The destructive ones last.
    _click_all(panel, skip=("สร้าง", "BOQ", "รายการราคา"))


def test_every_button_of_the_takeoff_panel_and_pr_export(ui):
    from PySide6.QtWidgets import QMessageBox

    from plugins.wanic_building import BuildingPanel
    from plugins.wanic_takeoff import TakeoffPanel
    scene = Scene()
    vp = _Vp(scene)
    bapp = _App(scene, "wanic_building", vp)
    building = BuildingPanel(bapp)
    _house(building)
    building.build(("structure", "roof"))
    app = _App(scene, "wanic_takeoff", vp)
    panel = TakeoffPanel(app)
    panel.refresh()
    # An empty price list: export offers the building's BOQ first.
    ui["state"]["answers"] = [QMessageBox.Yes, QMessageBox.No]
    panel.export_boq()
    assert not wanic_ui.LAST_ERROR
    saved = [p for p in ui["saved"] if p.endswith(".xlsx")]
    assert saved, ui["msgs"]
    data = zipfile.ZipFile(io.BytesIO(open(saved[-1], "rb").read()))
    sheets = [n for n in data.namelist() if n.startswith("xl/worksheets/")]
    assert len(sheets) >= 7                              # ปร.4 … BOQ
    assert panel.pull_building_boq() > 10
    done = _click_all(panel)
    assert any("ปร.1" in t for t in done)
    assert len(done) >= 8, done


def test_every_button_of_the_profiles_panel(ui):
    from plugins.wanic_profiles import ProfilePanel
    scene = Scene()
    app = _App(scene, "wanic_profiles")
    panel = ProfilePanel(app)
    done = _click_all(panel)
    assert len(done) >= 3, done
