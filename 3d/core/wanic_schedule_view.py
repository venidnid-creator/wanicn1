# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
"""แผนงานก่อสร้าง (CPM) window: the project's values, the bar chart with the
critical path in red, the S-curve, the monthly installments, and the .xlsx."""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (QDialog, QDoubleSpinBox, QFileDialog, QFormLayout, QHBoxLayout, QHeaderView,
                               QLabel, QPushButton, QSpinBox, QTableWidget, QTableWidgetItem, QTabWidget,
                               QVBoxLayout, QWidget)

from core import wanic_schedule as SC

RED, BLUE, INK, GRID = QColor("#E06666"), QColor("#6FA8DC"), QColor("#1F2937"), QColor("#CBD5E1")


class GanttWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.plan = None
        self.setMinimumHeight(360)

    def set(self, p):
        self.plan = p
        self.update()

    def paintEvent(self, _e):
        p = self.plan
        qp = QPainter(self)
        qp.setRenderHint(QPainter.Antialiasing)
        qp.fillRect(self.rect(), QColor("white"))
        if not p or not p.days:
            qp.drawText(self.rect(), Qt.AlignCenter, "ยังไม่มีค่าแรงในใบ BOQ")
            return
        tasks = [t for t in p.tasks if t.days]
        left, top, right, bottom = 270.0, 28.0, 16.0, 30.0
        W = self.width() - left - right
        H = self.height() - top - bottom
        row = H / max(len(tasks), 1)
        sx = W / p.days
        f = QFont(self.font())
        f.setPointSizeF(8.5)
        qp.setFont(f)
        qp.setPen(QPen(GRID, 1))
        for w in range(p.weeks + 1):                       # the weeks
            x = left + min(w * p.week, p.days) * sx
            qp.drawLine(QPointF(x, top), QPointF(x, top + H))
            if w < p.weeks and (p.weeks <= 30 or w % 2 == 0):
                qp.setPen(INK)
                qp.drawText(QRectF(x, 4, p.week * sx, 20), Qt.AlignCenter, str(w + 1))
                qp.setPen(QPen(GRID, 1))
        for i, t in enumerate(tasks):
            y = top + i * row
            qp.setPen(INK)
            qp.drawText(QRectF(4, y, left - 10, row), Qt.AlignVCenter | Qt.AlignRight, t.name)
            qp.fillRect(QRectF(left + t.es * sx, y + row * 0.22, max(t.days * sx, 2), row * 0.56),
                        RED if t.critical else BLUE)
            if t.slack and not t.critical:
                qp.setPen(QPen(QColor("#94A3B8"), 1, Qt.DashLine))
                qp.drawLine(QPointF(left + t.ef * sx, y + row / 2), QPointF(left + (t.ef + t.slack) * sx, y + row / 2))
        # the S-curve over it (0–100 % on the chart's height)
        pts = [QPointF(left, top + H)] + [QPointF(left + min(wk * p.week, p.days) * sx, top + H - H * cum / 100)
                                          for wk, _part, cum in p.curve]
        qp.setPen(QPen(QColor("#2E7D4F"), 2.2))
        for a, b in zip(pts, pts[1:]):
            qp.drawLine(a, b)
        qp.setPen(INK)
        qp.drawText(QRectF(left, top + H + 4, W, 20), Qt.AlignCenter,
                    "สัปดาห์ที่ · แถบแดง = งานวิกฤต · แถบฟ้า = งานมีเวลาเผื่อ · เส้นเขียว = ผลงานสะสม S-Curve (0–100 %)")


class ScheduleDialog(QDialog):
    def __init__(self, parent, result, data):
        super().__init__(parent)
        self.setWindowTitle("แผนงานก่อสร้าง (CPM) · S-Curve · งวดงาน")
        self.resize(1250, 780)
        self.result, self.data = result, data
        saved = dict((data or {}).get("schedule") or {})
        lay = QVBoxLayout(self)
        top = QHBoxLayout()
        form = QFormLayout()
        self.wage = QDoubleSpinBox()
        self.wage.setRange(100, 3000)
        self.wage.setDecimals(0)
        self.wage.setValue(float(saved.get("wage", 400)))
        self.week = QSpinBox()
        self.week.setRange(5, 7)
        self.week.setValue(int(saved.get("week", 6)))
        self.adv = QDoubleSpinBox()
        self.adv.setRange(0, 30)
        self.adv.setValue(float(saved.get("advance", 0)))
        self.ret = QDoubleSpinBox()
        self.ret.setRange(0, 10)
        self.ret.setValue(float(saved.get("retention", 0)))
        form.addRow("ค่าแรงคนงาน (บาท/คน/วัน)", self.wage)
        form.addRow("ทำงาน (วัน/สัปดาห์)", self.week)
        form.addRow("เงินล่วงหน้า (% ของสัญญา)", self.adv)
        form.addRow("เงินประกันผลงาน (%)", self.ret)
        top.addLayout(form)
        crew = QFormLayout()
        self.crews = {}
        for key, name, _c, _a, _o, n in SC.LOGIC:
            sp = QSpinBox()
            sp.setRange(1, 60)
            sp.setValue(int((saved.get("crews") or {}).get(key, n)))
            sp.valueChanged.connect(self.recalc)
            self.crews[key] = sp
            crew.addRow(f"คนงาน {name}", sp)
        cw = QWidget()
        cw.setLayout(crew)
        top.addWidget(cw)
        self.info = QLabel()
        self.info.setWordWrap(True)
        top.addWidget(self.info, 1)
        lay.addLayout(top)
        for w in (self.wage, self.adv, self.ret):
            w.valueChanged.connect(self.recalc)
        self.week.valueChanged.connect(self.recalc)
        self.tabs = QTabWidget()
        self.gantt = GanttWidget()
        self.tabs.addTab(self.gantt, "แผนภูมิแท่ง + S-Curve")
        self.t_tasks = self._table(["งาน", "ค่าแรง (บาท)", "คนงาน", "วัน", "เริ่ม", "เสร็จ", "เผื่อ (วัน)",
                                    "มูลค่างาน (บาท)", "วิกฤต"])
        self.tabs.addTab(self.t_tasks, "รายการงาน")
        self.t_pay = self._table(["งวดที่", "ถึงวันทำงานที่", "ผลงานงวดนี้ (%)", "ผลงานสะสม (%)", "ค่างานงวดนี้",
                                  "หักคืนเงินล่วงหน้า", "หักเงินประกันผลงาน", "จ่ายสุทธิ"])
        self.tabs.addTab(self.t_pay, "งวดงานรายเดือน")
        lay.addWidget(self.tabs, 1)
        row = QHBoxLayout()
        save = QPushButton("📊 บันทึกแผนงาน (.xlsx)")
        save.clicked.connect(self.save)
        close = QPushButton("ปิด")
        close.clicked.connect(self.accept)
        row.addStretch(1)
        row.addWidget(save)
        row.addWidget(close)
        lay.addLayout(row)
        self.recalc()

    @staticmethod
    def _table(head):
        t = QTableWidget(0, len(head))
        t.setHorizontalHeaderLabels(head)
        t.verticalHeader().hide()
        t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        t.horizontalHeader().setStretchLastSection(True)
        return t

    def values(self) -> dict:
        return {"wage": self.wage.value(), "week": self.week.value(), "advance": self.adv.value(),
                "retention": self.ret.value(), "crews": {k: s.value() for k, s in self.crews.items()}}

    def recalc(self, *_):
        v = self.values()
        self.plan = SC.plan(self.result, self.data, v["wage"], v["week"], v["crews"])
        p = self.plan
        self.gantt.set(p)
        tasks = [t for t in p.tasks if t.days]
        self.t_tasks.setRowCount(len(tasks))
        for r, t in enumerate(tasks):
            for c, val in enumerate((t.name, f"{t.labour:,.2f}", str(t.crew), str(t.days), str(t.es + 1), str(t.ef),
                                     str(t.slack), f"{t.value:,.2f}", "✓" if t.critical else "")):
                it = QTableWidgetItem(val)
                if t.critical:
                    it.setForeground(RED.darker(130))
                self.t_tasks.setItem(r, c, it)
        self.value = float((self.result.get("totals") or {}).get("with_f") or 0)
        pays = p.installments(self.value, v["advance"], v["retention"])
        self.t_pay.setRowCount(len(pays))
        for r, it in enumerate(pays):
            for c, k in enumerate(("no", "day", "percent", "cumulative", "amount", "advance_back", "retention", "pay")):
                self.t_pay.setItem(r, c, QTableWidgetItem(f"{it[k]:,.2f}" if c >= 2 else str(it[k])))
        crit = " → ".join(t.name for t in tasks if t.critical)
        self.info.setText(f"<b>ระยะเวลา {p.days} วันทำงาน</b> ({p.weeks} สัปดาห์ ≈ {p.months:g} เดือน)<br>"
                          f"มูลค่าสัญญา (รวม Factor F) {self.value:,.2f} บาท · {len(pays)} งวด<br>"
                          f"<span style='color:#B91C1C'>งานวิกฤต: {crit}</span><br>"
                          "ระยะเวลาแต่ละงาน = ค่าแรงตาม ว480 ในใบ BOQ ÷ (คนงาน × ค่าแรงต่อวัน) — คนงานและค่าแรงเป็นค่า"
                          "ของโครงการ ปรับได้ (หลักเกณฑ์ 2569 ไม่ได้กำหนด)")

    def save(self):
        path, _ = QFileDialog.getSaveFileName(self, "แผนงานก่อสร้าง", "แผนงานก่อสร้าง.xlsx", "ตารางคำนวณ (*.xlsx)")
        if not path:
            return
        v = self.values()
        SC.write_xlsx(self.plan, path, value=self.value, advance=v["advance"], retention=v["retention"])
        self.info.setText(self.info.text() + f"<br>บันทึกแล้ว: {path}")
