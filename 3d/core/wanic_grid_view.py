# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
"""โหมดกริด — the window: the spacings along the numbered and the lettered
axes, the storeys, and the bays left open (click a bay to take it out);
drawn with its axis bubbles and dimensions as it is typed."""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (QDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QSpinBox,
                               QVBoxLayout, QWidget)

from core import wanic_rc as R

AXIS = QColor("#1D4ED8")
BAY = QColor("#DCFCE7")
OUT = QColor("#F3F4F6")
INK = QColor("#111827")


def _font(px, bold=False):
    f = QFont()
    f.setFamilies(["TH Sarabun New", "TH SarabunPSK", "Laksaman", "Tahoma"])
    f.setPixelSize(max(1, int(px)))
    f.setBold(bold)
    return f


class GridWidget(QWidget):
    toggled = Signal()

    def __init__(self):
        super().__init__()
        self.sx, self.sy, self.omit = [4.0], [4.0], set()
        self.setMinimumSize(520, 420)
        self._geo = None

    def set_grid(self, sx, sy):
        self.sx, self.sy = sx, sy
        self.omit = {o for o in self.omit if o[0] < len(sx) and o[1] < len(sy)}
        self.update()

    def _layout(self):
        W, H = self.width(), self.height()
        tx, ty = sum(self.sx), sum(self.sy)
        pad = 70
        sc = min((W - 2 * pad) / tx, (H - 2 * pad) / ty)
        ox = (W - tx * sc) / 2
        oy = (H + ty * sc) / 2
        xs = [0.0]
        for v in self.sx:
            xs.append(xs[-1] + v)
        ys = [0.0]
        for v in self.sy:
            ys.append(ys[-1] + v)
        return sc, ox, oy, xs, ys

    def mousePressEvent(self, e):
        sc, ox, oy, xs, ys = self._layout()
        x = (e.position().x() - ox) / sc
        y = (oy - e.position().y()) / sc
        for i in range(len(self.sx)):
            for j in range(len(self.sy)):
                if xs[i] <= x <= xs[i + 1] and ys[j] <= y <= ys[j + 1]:
                    self.omit ^= {(i, j)}
                    self.update()
                    self.toggled.emit()
                    return

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor("#FFFFFF"))
        sc, ox, oy, xs, ys = self._layout()
        nx, ny = R.axis_names(len(xs), False), R.axis_names(len(ys), True)
        for i in range(len(self.sx)):
            for j in range(len(self.sy)):
                r = QRectF(ox + xs[i] * sc, oy - ys[j + 1] * sc, self.sx[i] * sc, self.sy[j] * sc)
                p.fillRect(r, OUT if (i, j) in self.omit else BAY)
                if (i, j) in self.omit:
                    p.setPen(QPen(QColor("#9CA3AF"), 1, Qt.DashLine))
                    p.drawLine(r.topLeft(), r.bottomRight())
                    p.drawLine(r.topRight(), r.bottomLeft())
        top, bot = oy - ys[-1] * sc, oy
        p.setFont(_font(13, True))
        for i, x in enumerate(xs):
            X = ox + x * sc
            p.setPen(QPen(AXIS, 1, Qt.DashDotLine))
            p.drawLine(QPointF(X, top - 30), QPointF(X, bot + 8))
            p.setPen(QPen(AXIS, 1.5))
            p.drawEllipse(QPointF(X, top - 42), 12, 12)
            p.drawText(QRectF(X - 12, top - 54, 24, 24), Qt.AlignCenter, nx[i])
        for j, y in enumerate(ys):
            Y = oy - y * sc
            p.setPen(QPen(AXIS, 1, Qt.DashDotLine))
            p.drawLine(QPointF(ox - 30, Y), QPointF(ox + xs[-1] * sc + 8, Y))
            p.setPen(QPen(AXIS, 1.5))
            p.drawEllipse(QPointF(ox - 42, Y), 12, 12)
            p.drawText(QRectF(ox - 54, Y - 12, 24, 24), Qt.AlignCenter, ny[j])
        # columns at the intersections that touch a kept bay
        p.setPen(Qt.NoPen)
        p.setBrush(INK)
        for i, x in enumerate(xs):
            for j, y in enumerate(ys):
                near = [(a, b) for a in (i - 1, i) for b in (j - 1, j)
                        if 0 <= a < len(self.sx) and 0 <= b < len(self.sy)]
                if any(n not in self.omit for n in near):
                    p.drawRect(QRectF(ox + x * sc - 5, oy - y * sc - 5, 10, 10))
        # dimensions
        p.setFont(_font(12))
        p.setPen(INK)
        for i, v in enumerate(self.sx):
            X = ox + (xs[i] + v / 2) * sc
            p.drawText(QRectF(X - 40, bot + 10, 80, 18), Qt.AlignCenter, f"{v:.2f}")
        for j, v in enumerate(self.sy):
            Y = oy - (ys[j] + v / 2) * sc
            p.drawText(QRectF(ox + xs[-1] * sc + 10, Y - 9, 60, 18), Qt.AlignLeft | Qt.AlignVCenter, f"{v:.2f}")
        p.end()


class GridDialog(QDialog):
    def __init__(self, parent, data: dict):
        super().__init__(parent)
        self.setWindowTitle("โหมดกริด — สร้างผังจากเส้นแกน")
        self.resize(1000, 640)
        g = (data or {}).get("grid") or {}
        lay = QHBoxLayout(self)
        left = QVBoxLayout()
        form = QFormLayout()
        self.ex = QLineEdit(", ".join(f"{v:g}" for v in g.get("x", [4, 4, 4])))
        self.ey = QLineEdit(", ".join(f"{v:g}" for v in g.get("y", [4, 4])))
        for e in (self.ex, self.ey):
            e.textChanged.connect(self.recalc)
        form.addRow("ระยะแกนตัวเลข 1, 2, 3… (ม.)", self.ex)
        form.addRow("ระยะแกนตัวอักษร A, B, C… (ม.)", self.ey)
        self.floors = QSpinBox()
        self.floors.setRange(1, 10)
        self.floors.setValue(int(g.get("floors", max(1, len((data or {}).get("floors") or [1])))))
        self.floors.valueChanged.connect(self.recalc)
        form.addRow("จำนวนชั้น", self.floors)
        left.addLayout(form)
        tip = QLabel("พิมพ์ระยะคั่นด้วยจุลภาค เช่น 4, 4, 3.5 หรือ 3@4 (= 4, 4, 4)\n"
                     "คลิกช่องในรูปเพื่อเว้นช่องนั้น (ไม่มีพื้น/ห้อง) — คลิกอีกครั้งเพื่อคืน\n"
                     "แต่ละช่องเป็นห้องหนึ่งห้อง เสาวางทุกจุดตัดกริด คานวางตามแนวกริด\n"
                     "⚠ การสร้างจากกริดจะแทนที่ห้องเดิมทุกชั้น (ประตู/หน้าต่าง/บันไดเดิมจะถูกลบ)")
        tip.setWordWrap(True)
        left.addWidget(tip)
        self.info = QLabel()
        self.info.setWordWrap(True)
        left.addWidget(self.info)
        left.addStretch(1)
        b = QHBoxLayout()
        self.ok = QPushButton("สร้างผังจากกริด")
        self.ok.setStyleSheet("font-weight: 700;")
        self.ok.clicked.connect(self.accept)
        cancel = QPushButton("ยกเลิก")
        cancel.clicked.connect(self.reject)
        b.addWidget(self.ok)
        b.addWidget(cancel)
        left.addLayout(b)
        lay.addLayout(left)
        self.view = GridWidget()
        self.view.omit = {tuple(o) for o in g.get("omit", [])}
        self.view.toggled.connect(self.recalc)
        lay.addWidget(self.view, 1)
        self.recalc()

    def values(self):
        return (R.parse_spacings(self.ex.text()), R.parse_spacings(self.ey.text()), self.floors.value(),
                sorted(self.view.omit))

    def recalc(self, *_):
        try:
            sx, sy, n, _om = self.values()
        except ValueError as e:
            self.info.setText(f"✗ {e}")
            self.ok.setEnabled(False)
            return
        self.ok.setEnabled(True)
        self.view.set_grid(sx, sy)
        bays = len(sx) * len(sy) - len(self.view.omit)
        self.info.setText(f"กริด {len(sx) + 1} × {len(sy) + 1} แกน · ขนาด {sum(sx):.2f} × {sum(sy):.2f} ม. · "
                          f"{bays} ช่อง × {n} ชั้น · พื้นที่ {sum(a * b for i, a in enumerate(sx) for j, b in enumerate(sy) if (i, j) not in self.view.omit) * n:,.2f} ตร.ม."
                          + ("\n⚠ มีช่วงเสาเกิน 6.00 ม. — ตรวจขนาดคาน" if max(sx + sy) > 6 else ""))
