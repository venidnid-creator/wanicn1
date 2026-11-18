# -*- coding: utf-8 -*-
"""Main window: steps on the left, plan and 3D in the middle, the step
page on the right. Build the model first, then calculate."""
from __future__ import annotations

import copy
import os

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (QComboBox, QFileDialog, QHBoxLayout, QLabel, QListWidget,
                               QMainWindow, QMessageBox, QSplitter, QStackedWidget, QVBoxLayout,
                               QWidget)

from ..structure.building import Building, Foundation, Level, Roof
from .pages import FoundationPage, GridPage, LevelsPage, ProjectPage, ResultsPage, RoofPage, SeismicPage, WindPage
from .plan_view import PlanView
from .view3d import View3D

APP = "WanicnDesign"


def default_building() -> Building:
    """A two-storey house to start from (grid 4, 4, 3.5 × 4, 4.5 m)."""
    return Building(
        name="โครงการใหม่", grid_x=[4.0, 4.0, 3.5], grid_y=[4.0, 4.5],
        levels=[Level("GB", 0.0, "on_ground", 0.10, 150, 50, 0.20, 0.40, "GB", "perimeter"),
                Level("FL2", 3.2, "suspended", 0.10, 150, 50, 0.20, 0.40, "B", "perimeter"),
                Level("ROOF", 6.2, "roof", 0.0, 0, 0, 0.15, 0.30, "RB", "none")],
        roof=Roof(), foundation=Foundation())


class MainWindow(QMainWindow):
    def __init__(self, building: Building | None = None, path: str | None = None):
        super().__init__()
        self.setWindowTitle(APP)
        self.resize(1400, 860)
        self.building = building or default_building()
        self.path = path
        self.result = None
        self.dirty = False

        self.steps = QListWidget()
        self.steps.setMinimumWidth(215)
        self.steps.setMaximumWidth(240)
        self.pages = QStackedWidget()
        self.page_list = [ProjectPage(), GridPage(), LevelsPage(), FoundationPage(), RoofPage(),
                          WindPage(), SeismicPage(), ResultsPage()]
        for p in self.page_list:
            self.steps.addItem(p.title)
            self.pages.addWidget(p)
            p.changed.connect(self.on_model_changed)
        self.results_page = self.page_list[-1]
        self.results_page.run_requested.connect(self.calculate)
        self.results_page.export_requested.connect(self.export)
        self.steps.currentRowChanged.connect(self.pages.setCurrentIndex)

        self.plan = PlanView()
        self.plan.changed.connect(self.on_model_changed)
        self.view3d = View3D()
        self.level_box = QComboBox()
        self.level_box.currentTextChanged.connect(lambda t: t and self.plan.set_level(t))

        centre = QWidget()
        cl = QVBoxLayout(centre)
        top = QHBoxLayout()
        top.addWidget(QLabel("แปลนชั้น"))
        top.addWidget(self.level_box)
        hint = QLabel("คลิกเสา คาน หรือพื้น เพื่อลบ · คลิกเส้นประเพื่อคืน · ล้อเมาส์ซูม")
        hint.setStyleSheet("color:#666")
        top.addWidget(hint, 1)
        cl.addLayout(top)
        views = QSplitter(Qt.Vertical)
        views.addWidget(self.plan)
        views.addWidget(self.view3d)
        views.setSizes([480, 360])
        cl.addWidget(views)

        split = QSplitter()
        split.addWidget(self.steps)
        split.addWidget(centre)
        split.addWidget(self.pages)
        split.setSizes([220, 740, 460])
        self.setCentralWidget(split)
        self._actions()
        self.load_model(self.building, path)
        self.steps.setCurrentRow(1)

    # -- toolbar ------------------------------------------------------------------
    def _actions(self):
        tb = self.addToolBar("หลัก")
        for text, slot, key in (("ใหม่", self.new, QKeySequence.New), ("เปิด", self.open, QKeySequence.Open),
                                ("บันทึก", self.save, QKeySequence.Save), ("บันทึกเป็น", self.save_as, None),
                                ("ย้อนกลับ", self.undo, QKeySequence.Undo),
                                ("คำนวณโครงสร้าง", self.calculate, "F5")):
            a = QAction(text, self)
            if key:
                a.setShortcut(QKeySequence(key))
            a.triggered.connect(slot)
            tb.addAction(a)

    # -- model ----------------------------------------------------------------------
    def load_model(self, building: Building, path: str | None = None):
        self.building, self.path, self.result = building, path, None
        for p in self.page_list:
            p.set_model(building)
        self.refresh_levels()
        self.plan.set_model(building, self.level_box.currentText())
        self.view3d.set_model(building)
        self.results_page.show_result(None)
        self.history = [building.to_dict()]
        self.dirty = False
        self._title()

    def undo(self):
        if len(self.history) < 2:
            self.statusBar().showMessage("ไม่มีขั้นให้ย้อนกลับ")
            return
        self.history.pop()
        state = self.history[-1]
        history, path = self.history, self.path
        self.load_model(Building.from_dict(copy.deepcopy(state)), path)
        self.history = history
        self.dirty = True
        self._title()

    def refresh_levels(self):
        cur = self.level_box.currentText()
        self.level_box.blockSignals(True)
        self.level_box.clear()
        names = [lv.name for lv in self.building.levels]
        self.level_box.addItems(names)
        if cur in names:
            self.level_box.setCurrentText(cur)
        self.level_box.blockSignals(False)

    def on_model_changed(self):
        self.history.append(copy.deepcopy(self.building.to_dict()))
        self.result = None
        self.dirty = True
        self.refresh_levels()
        self.plan.result = None
        self.plan.set_model(self.building, self.level_box.currentText())
        self.view3d.set_model(self.building)
        self.results_page.show_result(None)
        for p in self.page_list[:2]:
            p.load()
        self._title()

    def _title(self):
        name = os.path.basename(self.path) if self.path else "ไม่มีชื่อ"
        self.setWindowTitle(f"{APP} — {self.building.name} [{name}]{' *' if self.dirty else ''}")

    # -- commands ---------------------------------------------------------------------
    def calculate(self):
        from ..structure.design import design
        try:
            self.result = design(copy.deepcopy(self.building))
            self.result.building = self.building
        except Exception as e:  # show why, keep the model
            QMessageBox.critical(self, APP, f"คำนวณไม่สำเร็จ\n{e}")
            return None
        self.plan.set_result(self.result)
        self.view3d.set_model(self.building, self.result)
        self.results_page.show_result(self.result)
        self.steps.setCurrentRow(len(self.page_list) - 1)
        self.statusBar().showMessage("คำนวณเสร็จ — " + ("ผ่านทุกรายการ" if self.result.ok else
                                                         "มีรายการไม่ผ่าน (สีแดง)"))
        return self.result

    def new(self):
        self.load_model(default_building())

    def open(self):
        path, _ = QFileDialog.getOpenFileName(self, "เปิดโมเดล", "", "WanicnDesign (*.json)")
        if path:
            try:
                self.load_model(Building.load(path), path)
            except Exception as e:
                QMessageBox.critical(self, APP, f"เปิดไฟล์ไม่ได้\n{e}")

    def save(self):
        if not self.path:
            return self.save_as()
        self.building.save(self.path)
        self.dirty = False
        self._title()
        return True

    def save_as(self):
        path, _ = QFileDialog.getSaveFileName(self, "บันทึกโมเดล", "", "WanicnDesign (*.json)")
        if not path:
            return False
        if not path.endswith(".json"):
            path += ".json"
        self.path = path
        return self.save()

    def export(self, kind: str):
        if self.result is None and self.calculate() is None:
            return
        res = self.result
        ext = {"report": "xlsx", "dxf": "dxf", "boq": "xlsx", "sheets": "pdf", "cutting": "xlsx"}[kind]
        flt = "แบบก่อสร้าง PDF (*.pdf);;แบบก่อสร้าง DXF (*.dxf)" if kind == "sheets" else f"*.{ext}"
        path, _ = QFileDialog.getSaveFileName(self, "ส่งออก", "", flt)
        if not path:
            return
        self.export_to(kind, path, res)
        self.statusBar().showMessage(f"บันทึก {path}")

    @staticmethod
    def export_to(kind: str, path: str, res):
        if kind == "report":
            from ..structure.report import write_report
            write_report(res, path)
        elif kind == "dxf":
            from ..structure.drawing import write_dxf
            write_dxf(res, path)
        elif kind == "cutting":
            from ..structure.cutting import write_cutting_xlsx
            write_cutting_xlsx(res, path)
        elif kind == "sheets":
            from ..structure.sheets import write_sheets_dxf, write_sheets_pdf
            if path.lower().endswith(".dxf"):
                write_sheets_dxf(res, path)
            else:
                write_sheets_pdf(res, path if path.lower().endswith(".pdf") else path + ".pdf")
        else:
            from ..estimate import Estimate
            from ..quantities import takeoff
            from ..rates import DATA_DIR, Rates
            from ..structure.to_project import to_project
            project = to_project(res)
            rates = Rates(override_file=os.path.join(DATA_DIR, "labour_override.json"))
            Estimate(project.name, takeoff(project, rates), rates).to_xlsx(path)
