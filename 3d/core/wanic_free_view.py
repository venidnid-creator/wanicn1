# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
"""เขียนแบบอิสระ — the two windows: «แปลงเส้นที่เลือก» (what the selected
lines become: beam / column / wall, the mark, the wall's thickness and
height, an extra load) and «ชิ้นส่วนเขียนอิสระ» (every free member, edit
its mark or load, delete)."""
from __future__ import annotations

from PySide6.QtWidgets import (QComboBox, QDialog, QDoubleSpinBox, QFormLayout, QHBoxLayout, QHeaderView, QLabel,
                               QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout)

from core import wanic_building as B
from core import wanic_free as FR

KINDS = [("auto", "อัตโนมัติ (เส้นดิ่ง = เสา · นอกนั้น = คาน)"), ("beam", "คาน (ตรง / เอียง / โค้ง)"),
         ("column", "เสา (เส้นดิ่ง)"), ("wall", "ผนัง (ตรง / โค้ง)")]


class FreeConvertDialog(QDialog):
    def __init__(self, parent, data, chains):
        super().__init__(parent)
        self.setWindowTitle("แปลงเส้นที่เลือกเป็นชิ้นส่วนโครงสร้าง")
        self.setMinimumWidth(560)
        lay = QVBoxLayout(self)
        nv = sum(1 for c in chains for p, q in zip(c["pts"], c["pts"][1:]) if FR.is_vertical(p, q))
        ncur = sum(1 for c in chains if c["curved"])
        nslope = sum(1 for c in chains if abs(c["pts"][-1][2] - c["pts"][0][2]) > 0.02 and not
                     all(FR.is_vertical(p, q) for p, q in zip(c["pts"], c["pts"][1:])))
        info = QLabel(f"เลือกไว้ {len(chains)} สายเส้น · เส้นดิ่ง {nv} · เส้นโค้ง {ncur} · เส้นเอียง {nslope}<br>"
                      "คานวางให้หลังคานอยู่ที่ระดับเส้น · ผนังตั้งบนระดับเส้น · เสาจากปลายล่างถึงปลายบนของเส้นดิ่ง")
        info.setWordWrap(True)
        info.setStyleSheet("background:#EEF6FF;padding:8px;border-radius:6px")
        lay.addWidget(info)
        form = QFormLayout()
        self.kind = QComboBox()
        for k, t in KINDS:
            self.kind.addItem(t, k)
        if nv and nv == sum(len(c["pts"]) - 1 for c in chains):
            self.kind.setCurrentIndex(2)
        form.addRow("แปลงเป็น", self.kind)
        lib = B.library_of(data)
        self.mark = QComboBox()
        self.marks_beam = B.marks_of(lib, "beam")
        self.marks_col = B.marks_of(lib, "column")
        form.addRow("เบอร์ (จากคลังชิ้นส่วน)", self.mark)
        self.t = QDoubleSpinBox()
        self.t.setRange(0.05, 0.40)
        self.t.setDecimals(3)
        self.t.setValue(0.10)
        self.t.setSuffix(" ม.")
        form.addRow("ผนังหนา (เนื้อผนัง)", self.t)
        self.h = QDoubleSpinBox()
        self.h.setRange(0.0, 10.0)
        self.h.setSpecialValueText("อัตโนมัติ (ความสูงชั้น − ลึกคาน)")
        self.h.setSuffix(" ม.")
        form.addRow("ผนังสูง", self.h)
        self.w = QDoubleSpinBox()
        self.w.setRange(0, 20000)
        self.w.setSuffix(" กก./ม.")
        form.addRow("น้ำหนักเพิ่มบนคาน (คงที่)", self.w)
        lay.addLayout(form)
        self.kind.currentIndexChanged.connect(self._kind)
        self._kind()
        b = QHBoxLayout()
        b.addStretch(1)
        ok = QPushButton("แปลง อัปเดตโมเดล")
        ok.setStyleSheet("font-weight:700")
        ok.clicked.connect(self.accept)
        cancel = QPushButton("ยกเลิก")
        cancel.clicked.connect(self.reject)
        b.addWidget(ok)
        b.addWidget(cancel)
        lay.addLayout(b)

    def _kind(self, *_a):
        k = self.kind.currentData()
        self.mark.clear()
        for m in (self.marks_col if k == "column" else self.marks_beam):
            self.mark.addItem(m)
        if k == "beam" or k == "auto":
            i = self.mark.findText("B1")
            self.mark.setCurrentIndex(max(i, 0))
        self.mark.setEnabled(k != "wall")
        self.t.setEnabled(k == "wall")
        self.h.setEnabled(k == "wall")
        self.w.setEnabled(k in ("beam", "auto"))

    def apply(self, data, chains) -> dict:
        k = self.kind.currentData()
        n = FR.add_from_chains(data, chains, k, self.mark.currentText() or None, self.t.value(), self.h.value(),
                               self.w.value())
        if k == "auto" and n["columns"]:
            # the column mark for vertical lines when the beam mark was chosen
            for c in data["free"]["columns"][-n["columns"]:]:
                if c.get("mark") not in self.marks_col:
                    c["mark"] = "C1"
        return n


class FreeListDialog(QDialog):
    HEADS = ["ชนิด", "เบอร์", "ตำแหน่ง / ความยาว", "น้ำหนักเพิ่ม กก./ม.", "ลบ"]

    def __init__(self, parent, data):
        super().__init__(parent)
        self.setWindowTitle("ชิ้นส่วนเขียนอิสระ")
        self.setMinimumSize(860, 460)
        self.free = {k: [dict(x) for x in v] for k, v in FR.free_of(data).items()}
        lay = QVBoxLayout(self)
        info = QLabel("วาดเส้นในโมเดล (เส้นตรง เส้นโค้ง เส้นเอียง หรือเส้นดิ่ง) → เลือกเส้น → คลิกขวา "
                      "«แปลงเส้นที่เลือกเป็น คาน/เสา/ผนัง…» · ที่นี่แก้เบอร์ น้ำหนักเพิ่ม หรือลบได้")
        info.setWordWrap(True)
        info.setStyleSheet("background:#EEF6FF;padding:8px;border-radius:6px")
        lay.addWidget(info)
        self.rows = [("beams", i) for i in range(len(self.free["beams"]))] + \
            [("columns", i) for i in range(len(self.free["columns"]))] + \
            [("walls", i) for i in range(len(self.free["walls"]))]
        self.table = QTableWidget(len(self.rows), len(self.HEADS))
        self.table.setHorizontalHeaderLabels(self.HEADS)
        self.table.verticalHeader().hide()
        self.dels = []
        for r, (key, i) in enumerate(self.rows):
            el = self.free[key][i]
            if key == "beams":
                kind = FR.describe_beam(el)
                where = f"ยาว {FR.length3(el['pts']):.2f} ม. · ระดับ {el['pts'][0][2]:+.2f}"
                if abs(el["pts"][-1][2] - el["pts"][0][2]) > 0.02:
                    where += f" → {el['pts'][-1][2]:+.2f}"
            elif key == "columns":
                kind = "เสา"
                where = f"({float(el['x']):.2f}, {float(el['y']):.2f}) สูง {float(el['z1']) - float(el['z0']):.2f} ม."
            else:
                kind = "ผนังโค้ง" if el.get("curved") else "ผนัง"
                where = f"ยาว {FR.length2(el['pts']):.2f} ม. หนา {float(el.get('t') or 0.1) * 100:g} ซม."
            self.table.setItem(r, 0, QTableWidgetItem(kind))
            self.table.setItem(r, 1, QTableWidgetItem(el.get("mark", "") if key != "walls" else "-"))
            self.table.setItem(r, 2, QTableWidgetItem(where))
            self.table.setItem(r, 3, QTableWidgetItem(f"{float(el.get('w') or 0):g}" if key == "beams" else "-"))
            cb = QComboBox()
            cb.addItems(["เก็บไว้", "ลบ"])
            self.table.setCellWidget(r, 4, cb)
            self.dels.append(cb)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)
        lay.addWidget(self.table, 1)
        if not self.rows:
            lay.addWidget(QLabel("<b>ยังไม่มีชิ้นส่วนเขียนอิสระ</b>"))
        b = QHBoxLayout()
        b.addStretch(1)
        ok = QPushButton("บันทึก อัปเดตโมเดล และคำนวณใหม่")
        ok.setStyleSheet("font-weight:700")
        ok.clicked.connect(self.accept)
        cancel = QPushButton("ยกเลิก")
        cancel.clicked.connect(self.reject)
        b.addWidget(ok)
        b.addWidget(cancel)
        lay.addLayout(b)

    def apply(self, data) -> int:
        lib = B.library_of(data)
        keep = {"beams": [], "columns": [], "walls": []}
        for r, (key, i) in enumerate(self.rows):
            if self.dels[r].currentIndex() == 1:
                continue
            el = dict(self.free[key][i])
            if key != "walls":
                m = (self.table.item(r, 1).text() or "").strip()
                if m in lib and lib[m].get("kind") == ("beam" if key == "beams" else "column"):
                    el["mark"] = m
            if key == "beams":
                try:
                    el["w"] = float(self.table.item(r, 3).text())
                except ValueError:
                    pass
            keep[key].append(el)
        data["free"] = keep
        return sum(len(v) for v in keep.values())
