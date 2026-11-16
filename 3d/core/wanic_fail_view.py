# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
"""ไม่ผ่าน — เลือกวิธีแก้: after a calculation with members that fail, the
user is told at once which marks fail and why (the load that acts against the
load they can take), sees the change the advice makes to each, ticks the ones
to apply — and the program applies them and rebuilds the model.

``proposals(data)`` works on a copy (the fixes of every mark are found
together, as their loads change with each other's sizes); the dialog only
chooses which of them go back into the document."""
from __future__ import annotations

import copy

from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QCheckBox, QDialog, QHBoxLayout, QHeaderView, QLabel, QPushButton, QTableWidget,
                               QTableWidgetItem, QVBoxLayout)

from core import wanic_advice as AD
from core import wanic_building as B
from core import wanic_calc as C

#: the QSettings key of «แสดงอัตโนมัติ»
AUTO_KEY = "wanic/fail_dialog_auto"
KIND_TH = {"footing": "ฐานราก", "stump": "ตอม่อ", "column": "เสา", "beam": "คาน", "slab": "พื้น"}
STAIRS = "__stairs__"


def auto_enabled() -> bool:
    try:
        return str(QSettings().value(AUTO_KEY, "true")).lower() in ("true", "1", "yes")
    except Exception:                                 # noqa: BLE001 - no settings: on
        return True


def failing(res_all) -> list:
    """The members that fail, worst first."""
    return sorted((m for m in res_all.get("members") or [] if not m.ok), key=lambda m: -m.ratio)


def signature(res_all) -> tuple:
    """What fails now — the dialog opens by itself again only when it changes."""
    return tuple(sorted(m.name for m in failing(res_all)))


def proposals(data) -> tuple:
    """(trial document, [row]) — each row a dict: key (mark or STAIRS), kind,
    the change in words, why it failed in plain words, worst ratio."""
    trial = copy.deepcopy(data)
    lines = AD.apply_fixes(trial)
    if not lines:
        return trial, []
    res = C.analyse(data)
    worst = {}
    for m in failing(res):
        mark = m.name.split()[0]
        if mark not in worst or m.ratio > worst[mark].ratio:
            worst[mark] = m
    before, after = B.library_of(data), B.library_of(trial)
    rows = []
    for line in lines:
        mark = line.split(" ", 1)[0]
        if mark in after:
            m = worst.get(mark)
            rows.append({"key": mark, "kind": KIND_TH.get(after[mark].get("kind"), after[mark].get("kind", "")),
                         "change": line.split(": ", 1)[-1],
                         "why": m.plain_text() if m else "ข้อกำหนดเหล็กเสริม/สัดส่วน (ปรับให้ครบตามมาตรฐาน)",
                         "ratio": m.ratio if m else 1.0, "failing": m is not None})
        else:                                         # a stair line
            if not any(r["key"] == STAIRS for r in rows):
                rows.append({"key": STAIRS, "kind": "บันได", "change": line, "why": "ขนาดขั้น/ท้องบันได/เหล็ก",
                             "ratio": 1.0, "failing": True})
            else:
                next(r for r in rows if r["key"] == STAIRS)["change"] += " · " + line
    rows.sort(key=lambda r: (not r["failing"], -r["ratio"]))
    assert before is not None
    return trial, rows


def apply_chosen(data, trial, keys) -> int:
    """Copy the chosen marks (and the stairs) from the trial into ``data``."""
    keys = set(keys)
    lib = dict(data.get("library") or {})
    tlib = trial.get("library") or {}
    n = 0
    for k in keys:
        if k == STAIRS:
            for f, tf in zip(data.get("floors") or [], trial.get("floors") or []):
                if "stairs" in tf:
                    f["stairs"] = copy.deepcopy(tf["stairs"])
            n += 1
        elif k in tlib:
            lib[k] = copy.deepcopy(tlib[k])
            n += 1
    data["library"] = lib
    return n


class FailDialog(QDialog):
    """The failing marks, why, and the change for each — ticked by default."""

    def __init__(self, parent, res_all, rows):
        super().__init__(parent)
        self.setWindowTitle("ไม่ผ่าน — เลือกวิธีแก้ แล้วปรับโมเดลให้อัตโนมัติ")
        self.setMinimumSize(1100, 560)
        self.rows = rows
        lay = QVBoxLayout(self)
        bad = failing(res_all)
        head = QLabel(f"<b>ผลคำนวณ: ไม่ผ่าน {len(bad)} รายการ</b> — โปรแกรมหาวิธีแก้ให้แล้ว {len(rows)} เบอร์ "
                      "(เบอร์เดียวกันใช้ทั้งอาคาร จึงแก้ครั้งเดียวได้ทุกต้น/ทุกตัว) · ติ๊กเลือกที่ต้องการ แล้วกด "
                      "«ปรับที่เลือก» — ขนาดและเหล็กจะถูกแก้ โมเดลสร้างใหม่ และคำนวณซ้ำให้เอง (Undo ได้)")
        head.setWordWrap(True)
        head.setStyleSheet("background:#FEF2F2;color:#991B1B;padding:8px;border-radius:6px")
        lay.addWidget(head)
        self.table = QTableWidget(len(rows), 5)
        self.table.setHorizontalHeaderLabels(["แก้", "เบอร์", "ชนิด", "ทำไมไม่ผ่าน (อธิบายง่าย)",
                                              "แนะนำให้ปรับเป็น"])
        self.table.verticalHeader().hide()
        hh = self.table.horizontalHeader()
        for c in (0, 1, 2):
            hh.setSectionResizeMode(c, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(3, QHeaderView.Stretch)
        hh.setSectionResizeMode(4, QHeaderView.Stretch)
        self.table.setWordWrap(True)
        for r, row in enumerate(rows):
            it = QTableWidgetItem()
            it.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            it.setCheckState(Qt.Checked)
            self.table.setItem(r, 0, it)
            for c, text in ((1, "บันได" if row["key"] == STAIRS else row["key"]), (2, row["kind"]),
                            (3, row["why"]), (4, row["change"])):
                cell = QTableWidgetItem(text)
                cell.setFlags(Qt.ItemIsEnabled)
                if c == 3 and row["failing"]:
                    dark = self.palette().base().color().lightness() < 128
                    cell.setForeground(QColor("#FCA5A5") if dark else QColor("#B91C1C"))
                self.table.setItem(r, c, cell)
        self.table.resizeRowsToContents()
        lay.addWidget(self.table, 1)
        tips = QLabel("คำแนะนำเรียงจากที่เกินกำลังมากที่สุด · แถวที่ไม่ติ๊กจะไม่ถูกแก้ (แก้เองได้ภายหลังที่ขั้น 2–6 หรือ "
                      "ดับเบิลคลิกแถวในขั้น 9) · ทุกค่าคิดตาม วสท. 011008 / ACI 318 และเหล็กสมมาตร ระยะเรียงตามข้อกำหนด")
        tips.setWordWrap(True)
        lay.addWidget(tips)
        row = QHBoxLayout()
        for text, state in (("เลือกทั้งหมด", Qt.Checked), ("ไม่เลือกเลย", Qt.Unchecked)):
            b = QPushButton(text)
            b.clicked.connect(lambda _=False, s=state: self._tick_all(s))
            row.addWidget(b)
        self.auto = QCheckBox("แสดงหน้าต่างนี้อัตโนมัติทุกครั้งที่คำนวณแล้วไม่ผ่าน")
        self.auto.setChecked(auto_enabled())
        row.addWidget(self.auto)
        row.addStretch(1)
        ok = QPushButton("✅ ปรับที่เลือก และอัปเดตโมเดล")
        ok.setStyleSheet("font-weight:700")
        ok.setDefault(True)
        ok.clicked.connect(self.accept)
        later = QPushButton("ไว้ทีหลัง (แก้เอง)")
        later.clicked.connect(self.reject)
        row.addWidget(ok)
        row.addWidget(later)
        lay.addLayout(row)
        self.finished.connect(self._remember)

    def _tick_all(self, state):
        for r in range(self.table.rowCount()):
            self.table.item(r, 0).setCheckState(state)

    def _remember(self, *_a):
        try:
            QSettings().setValue(AUTO_KEY, self.auto.isChecked())
        except Exception:                             # noqa: BLE001
            pass

    def chosen(self) -> list:
        return [self.rows[r]["key"] for r in range(self.table.rowCount())
                if self.table.item(r, 0).checkState() == Qt.Checked]
