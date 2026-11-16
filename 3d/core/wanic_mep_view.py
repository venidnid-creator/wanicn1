# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
"""งานระบบรายห้อง: every room's lights, sockets, switches, TV, extract fan,
air conditioner (BTU), water heater and the wire of their own circuits —
filled in by the program from the room's kind and size, any of them changed
by the user. What is changed is kept on the room (``room["mep"]``) and goes
into the 3D model, the EE / M sheets and the BOQ."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QHBoxLayout, QHeaderView, QLabel, QPushButton,
                               QSpinBox, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from core import wanic_mep as M

COLS = ["ชั้น", "ห้อง", "ตร.ม.", "ดวงไฟ", "เต้ารับ", "สวิตช์", "ทีวี", "พัดลมดูด", "แอร์ (BTU)", "สายแอร์",
        "น้ำอุ่น", "วัตต์", "สายน้ำอุ่น"]
KIND_TH = {"bed": "ห้องนอน", "living": "นั่งเล่น", "kitchen": "ครัว", "wet": "ห้องน้ำ", "work": "ทำงาน",
           "pass": "ทางเดิน", "other": "อื่น ๆ"}
OWN = QColor("#FEF3C7")               # a value the user set (not the program's)


def _wire_box(value, auto):
    cb = QComboBox()
    cb.addItem(f"อัตโนมัติ ({auto:g})" if auto else "—", 0.0)
    for w in M.WIRES:
        cb.addItem(f"THW {w:g} ตร.มม. ({M.WIRES[w]})", float(w))
    i = cb.findData(float(value or 0))
    cb.setCurrentIndex(max(i, 0))
    return cb


class MepRoomsDialog(QDialog):
    def __init__(self, parent, data):
        super().__init__(parent)
        self.setWindowTitle("งานระบบรายห้อง — ไฟฟ้า แอร์ น้ำอุ่น ขนาดสาย")
        self.setMinimumSize(1180, 560)
        self.data = data
        self.recs = M.plan(data)
        lay = QVBoxLayout(self)
        head = QLabel("โปรแกรมกำหนดให้ตามชนิดและขนาดห้อง (ดวงไฟ 1 ดวงต่อ ≤ 9 ตร.ม. · แอร์ห้องนอน 800 / นั่งเล่น "
                      "900 BTU ต่อ ตร.ม. · วงจรเฉพาะแอร์/น้ำอุ่นตาม วสท. 2001) — แก้ตัวเลขได้ทุกช่อง ช่องสีเหลือง = "
                      "ค่าที่ผู้ใช้กำหนดเอง · บันทึกแล้วเข้าโมเดล 3 มิติ แบบไฟฟ้า/ปรับอากาศ และ BOQ")
        head.setWordWrap(True)
        head.setStyleSheet("background:#EEF6FF;color:#1F2937;padding:8px;border-radius:6px")
        lay.addWidget(head)
        self.table = QTableWidget(len(self.recs), len(COLS))
        self.table.setHorizontalHeaderLabels(COLS)
        self.table.verticalHeader().hide()
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.cells = []
        for r, rec in enumerate(self.recs):
            own = rec.get("own") or {}
            for c, text in enumerate((str(rec["floor"] + 1), f"{rec['room'].get('name') or 'ห้อง'} "
                                      f"({KIND_TH.get(rec['kind'], '')})", f"{rec['area']:.1f}")):
                it = QTableWidgetItem(text)
                it.setFlags(Qt.ItemIsEnabled)
                self.table.setItem(r, c, it)
            row = {}
            for c, key, hi in ((3, "lights", 40), (4, "outlets", 40), (5, "switches", 20), (6, "tv", 6),
                               (7, "fan", 6)):
                sp = QSpinBox()
                sp.setRange(0, hi)
                sp.setValue(int(rec[key]))
                self._mark(sp, key in own)
                sp.valueChanged.connect(lambda _v, w=sp: self._mark(w, True))
                self.table.setCellWidget(r, c, sp)
                row[key] = sp
            ac = QComboBox()
            ac.addItem("ไม่มี", 0)
            for b in M.AC_SIZES:
                ac.addItem(f"{b:,}", b)
            ac.setCurrentIndex(max(ac.findData(int(rec["ac"])), 0))
            self._mark(ac, "ac" in own)
            ac.currentIndexChanged.connect(lambda _i, w=ac: self._mark(w, True))
            self.table.setCellWidget(r, 8, ac)
            row["ac"] = ac
            aw = _wire_box(own.get("ac_wire"), M.ac_wire(rec["ac"]) if rec["ac"] else 0)
            self._mark(aw, "ac_wire" in own)
            self.table.setCellWidget(r, 9, aw)
            row["ac_wire"] = aw
            hb = QCheckBox()
            hb.setChecked(bool(rec["heater"]))
            holder = QWidget()
            hl = QHBoxLayout(holder)
            hl.setContentsMargins(6, 0, 6, 0)
            hl.addWidget(hb)
            self.table.setCellWidget(r, 10, holder)
            row["heater"] = hb
            hw = QSpinBox()
            hw.setRange(0, 12000)
            hw.setSingleStep(500)
            hw.setValue(int(rec.get("heater_w") or M.HEATER_W))
            self._mark(hw, "heater_w" in own)
            self.table.setCellWidget(r, 11, hw)
            row["heater_w"] = hw
            hwire = _wire_box(own.get("heater_wire"), M.heater_wire(rec.get("heater_w") or M.HEATER_W))
            self._mark(hwire, "heater_wire" in own)
            self.table.setCellWidget(r, 12, hwire)
            row["heater_wire"] = hwire
            self.cells.append(row)
        lay.addWidget(self.table, 1)
        self.total = QLabel()
        lay.addWidget(self.total)
        btns = QHBoxLayout()
        reset = QPushButton("กลับเป็นค่าอัตโนมัติทั้งหมด")
        reset.clicked.connect(self.reset_all)
        btns.addWidget(reset)
        btns.addStretch(1)
        ok = QPushButton("💾 บันทึก (โมเดล แบบ และ BOQ)")
        ok.setStyleSheet("font-weight:700")
        ok.clicked.connect(self.accept)
        cancel = QPushButton("ยกเลิก")
        cancel.clicked.connect(self.reject)
        btns.addWidget(ok)
        btns.addWidget(cancel)
        lay.addLayout(btns)
        self._reset = False
        for row in self.cells:                        # the totals follow every change
            for key in ("lights", "outlets", "switches", "tv", "fan"):
                row[key].valueChanged.connect(lambda _v: self._totals())
            row["ac"].currentIndexChanged.connect(lambda _i: self._totals())
            row["heater"].toggled.connect(lambda _b: self._totals())
        self._totals()

    @staticmethod
    def _mark(w, own):
        w.setStyleSheet("background:#FEF3C7;color:#1F2937" if own else "")

    def _totals(self):
        t = {k: sum(int(r[k].value()) for r in self.cells) for k in ("lights", "outlets", "switches", "tv", "fan")}
        acs = [int(r["ac"].currentData() or 0) for r in self.cells]
        heaters = sum(1 for r in self.cells if r["heater"].isChecked())
        self.total.setText(f"รวม: ดวงไฟ {t['lights']} · เต้ารับ {t['outlets']} · สวิตช์ {t['switches']} · "
                           f"ทีวี {t['tv']} · พัดลมดูดอากาศ {t['fan']} · แอร์ {sum(1 for a in acs if a)} เครื่อง "
                           f"({sum(acs):,} BTU) · เครื่องทำน้ำอุ่น {heaters}")

    def reset_all(self):
        self._reset = True
        self.accept()

    def apply(self, data) -> int:
        """Keep on each room only what differs from the program's own values."""
        recs = M.plan(data) if data is not self.data else self.recs
        n = 0
        for rec, row in zip(recs, self.cells):
            rm = rec["room"]
            if self._reset:
                rm.pop("mep", None)
                continue
            auto = rec["auto"]
            own = {}
            for key in ("lights", "outlets", "switches", "tv", "fan"):
                v = int(row[key].value())
                if v != int(auto[key]):
                    own[key] = v
            ac = int(row["ac"].currentData() or 0)
            if ac != int(auto["ac"]):
                own["ac"] = ac
            if bool(row["heater"].isChecked()) != bool(auto["heater"]):
                own["heater"] = bool(row["heater"].isChecked())
            if int(row["heater_w"].value()) != M.HEATER_W:
                own["heater_w"] = int(row["heater_w"].value())
            for key in ("ac_wire", "heater_wire"):
                v = float(row[key].currentData() or 0)
                if v:
                    own[key] = v
            if own:
                rm["mep"] = own
                n += 1
            else:
                rm.pop("mep", None)
        return n
