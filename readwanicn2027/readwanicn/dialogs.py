# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2569 (2026) นายเวนิช ธัมมะวงษ์ วิศวกรสำรวจ — ReadWanicn2027
"""Dialogs of the newer tools: editing a line of PDF text, and the usage statistics."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (QCheckBox, QColorDialog, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox,
                               QFileDialog, QFormLayout, QHBoxLayout, QHeaderView, QLabel, QMessageBox,
                               QPlainTextEdit, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout,
                               QWidget)

from . import usage


class TextDialog(QDialog):
    """Write or change a piece of text: the words, size, colour, bold."""

    def __init__(self, parent, title, text="", size=16.0, color=0, bold=False, family="Laksaman", can_delete=False):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(520, 300)
        self.deleted = False
        lay = QVBoxLayout(self)
        self.edit = QPlainTextEdit(text)
        f = QFont(family)
        f.setPointSizeF(16)
        self.edit.setFont(f)
        lay.addWidget(self.edit, 1)
        form = QFormLayout()
        self.size = QDoubleSpinBox()
        self.size.setRange(4, 200)
        self.size.setDecimals(1)
        self.size.setValue(size)
        self.size.setSuffix(" พอยต์")
        form.addRow("ขนาดตัวอักษร", self.size)
        row = QHBoxLayout()
        self.color = QColor(f"#{color:06X}")
        self.swatch = QPushButton()
        self.swatch.setFixedWidth(60)
        self.swatch.clicked.connect(self.pick)
        self._paint()
        row.addWidget(self.swatch)
        self.bold = QCheckBox("ตัวหนา")
        self.bold.setChecked(bold)
        row.addWidget(self.bold)
        row.addStretch(1)
        w = QWidget()
        w.setLayout(row)
        form.addRow("สีตัวอักษร", w)
        lay.addLayout(form)
        note = QLabel("ข้อความใหม่เขียนด้วยแบบอักษรไทย (TH Sarabun) ในตำแหน่งเดิม")
        note.setStyleSheet("font-size:8.5pt;")
        lay.addWidget(note)
        box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        box.button(QDialogButtonBox.Ok).setText("ตกลง")
        box.button(QDialogButtonBox.Cancel).setText("ยกเลิก")
        if can_delete:
            d = box.addButton("ลบข้อความนี้", QDialogButtonBox.DestructiveRole)
            d.clicked.connect(self._delete)
        box.accepted.connect(self.accept)
        box.rejected.connect(self.reject)
        lay.addWidget(box)

    def _paint(self):
        self.swatch.setStyleSheet(f"background:{self.color.name()}; border:1px solid #888;")

    def pick(self):
        c = QColorDialog.getColor(self.color, self, "สีตัวอักษร")
        if c.isValid():
            self.color = c
            self._paint()

    def _delete(self):
        self.deleted = True
        self.accept()

    @property
    def rgb(self) -> int:
        return (self.color.red() << 16) | (self.color.green() << 8) | self.color.blue()

    def text(self) -> str:
        return self.edit.toPlainText()


class UsageDialog(QDialog):
    """Counts of every feature by day, week, month or year, and the report out."""

    def __init__(self, parent, store: "usage.Usage"):
        super().__init__(parent)
        self.store = store
        self.setWindowTitle("สถิติการใช้งาน")
        self.resize(760, 560)
        lay = QVBoxLayout(self)
        top = QHBoxLayout()
        top.addWidget(QLabel("ช่วงเวลา"))
        self.period = QComboBox()
        for k, v in usage.PERIODS.items():
            self.period.addItem(v, k)
        self.period.currentIndexChanged.connect(self.fill)
        top.addWidget(self.period)
        top.addWidget(QLabel("ผู้ใช้"))
        self.who = QComboBox()
        self.who.addItem("ทุกคน", "")
        for u in sorted({u for _, u, _ in store.events() if u}):
            self.who.addItem(u, u)
        self.who.currentIndexChanged.connect(self.fill)
        top.addWidget(self.who)
        top.addStretch(1)
        rep = QPushButton("📈 ออกรายงาน (.xlsx)")
        rep.setObjectName("Primary")
        rep.clicked.connect(self.report)
        top.addWidget(rep)
        lay.addLayout(top)
        self.total = QLabel()
        self.total.setStyleSheet("font-size:11pt;")
        lay.addWidget(self.total)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["ช่วงเวลา", "รายการ", "จำนวนครั้ง", ""])
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(1, QHeaderView.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(3, QHeaderView.Stretch)
        self.table.verticalHeader().hide()
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        lay.addWidget(self.table, 1)
        note = QLabel("สถิติเก็บไว้ในเครื่องนี้เท่านั้น ไม่ได้ส่งออกไปที่ใด")
        note.setStyleSheet("font-size:8.5pt;")
        lay.addWidget(note)
        box = QDialogButtonBox(QDialogButtonBox.Close)
        box.button(QDialogButtonBox.Close).setText("ปิด")
        box.rejected.connect(self.reject)
        lay.addWidget(box)
        self.fill()

    def fill(self):
        events = self.store.events()
        rows, total = usage.summary(events, self.period.currentData(), self.who.currentData() or None)
        self.total.setText(f"ใช้งานทั้งหมด <b>{sum(total.values()):,}</b> ครั้ง · "
                           f"{len(total)} รายการ · {len(rows)} "
                           f"{dict(day='วัน', week='สัปดาห์', month='เดือน', year='ปี')[self.period.currentData()]}")
        flat = []
        for label, counts in rows:
            first = True
            for f, n in counts.most_common():
                flat.append((label if first else "", f, n))
                first = False
        top = max((n for *_, n in flat), default=1)
        self.table.setRowCount(len(flat))
        for r, (label, f, n) in enumerate(flat):
            self.table.setItem(r, 0, QTableWidgetItem(label))
            self.table.setItem(r, 1, QTableWidgetItem(f))
            it = QTableWidgetItem(f"{n:,}")
            it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table.setItem(r, 2, it)
            self.table.setItem(r, 3, QTableWidgetItem("█" * max(1, round(20 * n / top))))
            self.table.item(r, 3).setForeground(QColor("#1F6FEB"))

    def report(self):
        path, _ = QFileDialog.getSaveFileName(self, "รายงานสถิติการใช้งาน", "สถิติการใช้งาน.xlsx",
                                              "ตารางคำนวณ (*.xlsx)")
        if not path:
            return
        usage.report_xlsx(self.store.events(), path)
        self.store.record("ออกรายงานสถิติการใช้งาน")
        QMessageBox.information(self, "สถิติการใช้งาน", f"บันทึกรายงานแล้ว\n{path}")
