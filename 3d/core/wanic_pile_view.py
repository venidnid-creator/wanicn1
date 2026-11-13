# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
"""เสาเข็ม 2 ขนาด · กำลังเข็มจากผลทดสอบ — the window: P1 and P2 side by
side (section, length, how the safe load is known and its numbers, the
result live) and which footing mark stands on which."""
from __future__ import annotations

from PySide6.QtWidgets import (QComboBox, QDialog, QDoubleSpinBox, QFormLayout, QGroupBox, QHBoxLayout,
                               QHeaderView, QLabel, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
                               QVBoxLayout)

from core import wanic_building as B
from core import wanic_calc as C
from core import wanic_pile as PL

#: method → [(key, label, lo, hi, step, decimals)]
FIELDS = {
    "given": [("Qa", "รับน้ำหนักปลอดภัย (ตัน/ต้น)", 0, 500, 0.5, 2)],
    "static": [("Qult", "น้ำหนักประลัยจากการทดสอบ Qult (ตัน)", 0, 2000, 1, 2), ("FS", "อัตราส่วนปลอดภัย FS", 1, 5, 0.1, 2)],
    "dynamic": [("Qult", "น้ำหนักประลัยจากการทดสอบ Qult (ตัน)", 0, 2000, 1, 2), ("FS", "อัตราส่วนปลอดภัย FS", 1, 5, 0.1, 2)],
    "hiley": [("W", "น้ำหนักตุ้ม W (ตัน)", 0.1, 20, 0.1, 2), ("H", "ระยะยกตุ้ม H (ม.)", 0.1, 3, 0.05, 2),
              ("S", "ทรุดเฉลี่ย 10 ครั้งสุดท้าย S (มม./ครั้ง)", 0.1, 100, 0.5, 1),
              ("C", "ยุบตัวชั่วคราว C (มม.)", 0, 60, 1, 1), ("eff", "ประสิทธิภาพตุ้ม e", 0.3, 1, 0.05, 2),
              ("FS", "อัตราส่วนปลอดภัย FS", 1, 5, 0.1, 2)],
    "soil": [("qb", "แรงแบกทานปลายเข็ม qb (ตัน/ตร.ม.)", 0, 2000, 5, 1), ("FS", "อัตราส่วนปลอดภัย FS", 1, 5, 0.1, 2)],
}
DEFAULT_VAL = {"Qa": 8.0, "Qult": 40.0, "W": 1.5, "H": 0.5, "S": 10.0, "C": 25.0, "eff": 0.8, "qb": 200.0}


def parse_layers(text: str, L: float) -> list:
    """«4:1.0, 6:2.5» → [[4, 1.0], [6, 2.5]] (thickness m : fs t/m²)."""
    out = []
    for part in (text or "").replace(";", ",").split(","):
        if ":" in part:
            a, b = part.split(":", 1)
            try:
                out.append([float(a), float(b)])
            except ValueError:
                continue
    return out or [[L, 2.0]]


class PileBox(QGroupBox):
    def __init__(self, key, t: dict, on_change):
        super().__init__(f"เสาเข็ม {key}")
        self.key = key
        self.t = dict(t)
        self.on_change = on_change
        lay = QVBoxLayout(self)
        top = QFormLayout()
        self.sec = QComboBox()
        for k, v in PL.SECTIONS.items():
            self.sec.addItem(v[0], k)
        self.sec.setCurrentIndex(list(PL.SECTIONS).index(t.get("section", "I18")) if t.get("section") in PL.SECTIONS
                                 else 0)
        self.len = QDoubleSpinBox()
        self.len.setRange(1, 60)
        self.len.setDecimals(2)
        self.len.setSuffix(" ม.")
        self.len.setValue(float(t.get("len") or 6.0))
        self.meth = QComboBox()
        for k, v in PL.METHODS.items():
            self.meth.addItem(v, k)
        self.meth.setCurrentIndex(list(PL.METHODS).index(t.get("method", "given")))
        top.addRow("หน้าตัดเข็ม", self.sec)
        top.addRow("ความยาว", self.len)
        top.addRow("กำลังเข็มจาก", self.meth)
        lay.addLayout(top)
        self.form = QFormLayout()
        lay.addLayout(self.form)
        self.res = QLabel()
        self.res.setWordWrap(True)
        self.res.setStyleSheet("background:#F1F5F9;padding:6px;border-radius:6px")
        lay.addWidget(self.res)
        self.edits = {}
        self.cur = t.get("method", "given")         # the method the FS in self.t belongs to
        self.sec.currentIndexChanged.connect(self.changed)
        self.len.valueChanged.connect(self.changed)
        self.meth.currentIndexChanged.connect(self.rebuild)
        self.rebuild()

    def rebuild(self, *_a):
        self.t.update(self.values())
        while self.form.rowCount():
            self.form.removeRow(0)
        self.edits = {}
        m = self.meth.currentData()
        for key, lab, lo, hi, step, dec in FIELDS[m]:
            sp = QDoubleSpinBox()
            sp.setRange(lo, hi)
            sp.setSingleStep(step)
            sp.setDecimals(dec)
            v = self.t.get(key)
            if key == "FS" and (v is None or self.cur != m):
                v = PL.FS_DEFAULT[m]
            sp.setValue(float(v if v is not None else DEFAULT_VAL.get(key, 0)))
            sp.valueChanged.connect(self.changed)
            self.edits[key] = sp
            self.form.addRow(lab, sp)
        if m == "soil":
            ed = QLineEdit(", ".join(f"{a:g}:{b:g}" for a, b in (self.t.get("layers") or [[4, 1.0], [4, 2.5]])))
            ed.setToolTip("ชั้นดินจากผิวดินลงไป — ความหนา (ม.) : แรงเสียดทาน fs (ตัน/ตร.ม.) คั่นด้วยจุลภาค")
            ed.textChanged.connect(self.changed)
            self.edits["layers"] = ed
            self.form.addRow("ชั้นดิน หนา:fs (ม.:ตัน/ตร.ม.)", ed)
        self.cur = m
        self.changed()

    def values(self) -> dict:
        out = {"section": self.sec.currentData(), "len": self.len.value(), "method": self.meth.currentData()}
        for k, w in self.edits.items():
            out[k] = parse_layers(w.text(), self.len.value()) if k == "layers" else w.value()
        return out

    def changed(self, *_a):
        c = PL.capacity(self.values())
        self.res.setText("<br>".join(c["lines"]).replace(f"ใช้ Qa = {c['Qa']:,.2f}",
                                                           f"<b>ใช้ Qa = {c['Qa']:,.2f}</b>"))
        self.on_change()


class PileDialog(QDialog):
    def __init__(self, parent, data):
        super().__init__(parent)
        self.setWindowTitle("เสาเข็ม 2 ขนาด · กำลังเข็มจากผลทดสอบ")
        self.setMinimumSize(1080, 700)
        self.data = data
        b_ = C.basis(data)
        types = PL.types_of(data, b_)
        lay = QVBoxLayout(self)
        info = QLabel("กำหนดเสาเข็ม 2 ขนาด (P1, P2) แล้วเลือกให้ฐานรากแต่ละเบอร์ · กำลังเข็มคิดจากผลทดสอบ "
                      "(สถิต/พลวัต) บันทึกการตอก (Hiley) หรือข้อมูลเจาะสำรวจดิน หารด้วยอัตราส่วนปลอดภัย และไม่เกิน"
                      "กำลังตัวเข็ม 0.25 fc′ Ac · คุณสมบัติหน้าตัดเป็นค่าโดยประมาณ ตรวจกับผู้ผลิต")
        info.setWordWrap(True)
        info.setStyleSheet("background:#EEF6FF;padding:8px;border-radius:6px")
        lay.addWidget(info)
        row = QHBoxLayout()
        self.boxes = {k: PileBox(k, types[k], self.refresh) for k in ("P1", "P2")}
        for b in self.boxes.values():
            row.addWidget(b, 1)
        lay.addLayout(row, 3)
        self.lib = B.library_of(data)
        self.marks = [m for m, sp in self.lib.items() if sp.get("kind") == "footing"]
        self.table = QTableWidget(len(self.marks), 5)
        self.table.setHorizontalHeaderLabels(["ฐานราก", "จำนวนเข็ม/ฐาน", "ใช้เสาเข็ม", "รับได้ต่อฐาน (ตัน)", "หมายเหตุ"])
        self.table.verticalHeader().hide()
        self.combos = {}
        for r, m in enumerate(self.marks):
            sp = self.lib[m]
            self.table.setItem(r, 0, QTableWidgetItem(m))
            self.table.setItem(r, 1, QTableWidgetItem(str(int(sp.get("piles") or 0))))
            cb = QComboBox()
            cb.addItem("P1", "P1")
            cb.addItem("P2", "P2")
            cb.setCurrentIndex(0 if PL.type_of_spec(sp) == "P1" else 1)
            cb.currentIndexChanged.connect(self.refresh)
            self.table.setCellWidget(r, 2, cb)
            self.combos[m] = cb
        self.table.itemChanged.connect(self.refresh)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)
        lay.addWidget(self.table, 1)
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
        self.refresh()

    def _piles(self, r) -> int:
        it = self.table.item(r, 1)
        try:
            return max(0, int(float(it.text()))) if it else 0
        except ValueError:
            return 0

    def refresh(self, *_a):
        if not hasattr(self, "table"):
            return
        caps = {k: PL.capacity(b.values())["Qa"] for k, b in self.boxes.items()}
        self.table.blockSignals(True)
        for r, m in enumerate(self.marks):
            n = self._piles(r)
            t = self.combos[m].currentData()
            self.table.setItem(r, 3, QTableWidgetItem(f"{n * caps[t]:,.2f}" if n else "-"))
            self.table.setItem(r, 4, QTableWidgetItem("" if n else "ฐานแผ่ (ไม่มีเข็ม) — ใส่จำนวนเข็มเพื่อใช้เข็ม"))
        self.table.blockSignals(False)

    def piles(self) -> dict:
        out = {}
        for k, b in self.boxes.items():
            out[k] = b.values()
        return out

    def apply(self, data: dict) -> None:
        data["piles"] = self.piles()
        lib = dict(data.get("library") or {})
        for r, m in enumerate(self.marks):
            spec = dict(lib.get(m) or {})
            spec.update(kind="footing", piles=self._piles(r), pile=self.combos[m].currentData())
            lib[m] = spec
        data["library"] = lib
