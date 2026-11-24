# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
"""บันไดอัตโนมัติ — the dialog: where the stair goes (six places), its
width and form, a plan of the ground floor with the stair drawn, and the
design in words (risers, goings, landing, the law)."""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import (QButtonGroup, QComboBox, QDialog, QGridLayout, QHBoxLayout, QLabel, QPushButton,
                               QRadioButton, QVBoxLayout, QWidget)

from core import wanic_building as B
from core import wanic_stair_auto as SA


class _Preview(QWidget):
    """The ground floor's rooms and the stair, front at the bottom — drag
    the stair to move it (snapped to 5 cm); ``moved(x, y)`` is called."""

    def __init__(self):
        super().__init__()
        self.setMinimumSize(360, 300)
        self.data, self.stair, self.s = None, None, None
        self.moved = None
        self._drag = None
        self.setCursor(Qt.OpenHandCursor)
        self.setToolTip("ลากบันไดเพื่อเลื่อนตำแหน่ง")

    def _cols(self):
        return B.stair_cols(B.elements(self.data), 0) if self.data else []

    def _frame(self):
        x0, y0, x1, y1 = SA.footprint(self.data)
        m = 28.0
        k = min((self.width() - 2 * m) / max(x1 - x0, 0.1), (self.height() - 2 * m) / max(y1 - y0, 0.1))
        return x0, y0, m, k

    def _model(self, pt):
        x0, y0, m, k = self._frame()
        return x0 + (pt.x() - m) / k, y0 + (self.height() - m - pt.y()) / k

    def mousePressEvent(self, e):                     # noqa: N802 - Qt override
        if self.stair and self.data:
            x, y = self._model(e.position())
            self._drag = (x - float(self.stair["x"]), y - float(self.stair["y"]))
            self.setCursor(Qt.ClosedHandCursor)

    def mouseMoveEvent(self, e):                      # noqa: N802 - Qt override
        if self._drag is None or not self.moved:
            return
        x, y = self._model(e.position())
        nx = round((x - self._drag[0]) / 0.05) * 0.05
        ny = round((y - self._drag[1]) / 0.05) * 0.05
        self.moved(nx, ny)

    def mouseReleaseEvent(self, _e):                  # noqa: N802 - Qt override
        self._drag = None
        self.setCursor(Qt.OpenHandCursor)

    def show_it(self, data, stair, s):
        self.data, self.stair, self.s = data, stair, s
        self.update()

    def paintEvent(self, _e):                         # noqa: N802 - Qt override
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor("#FAFAF7"))
        if not self.data:
            return
        x0, y0, x1, y1 = SA.footprint(self.data)
        if x1 <= x0:
            return
        x0, y0, m, k = self._frame()

        def T(x, y):
            return QPointF(m + (x - x0) * k, self.height() - m - (y - y0) * k)
        p.setPen(QPen(QColor("#2E7D4F"), 1.2))
        p.setBrush(QColor(200, 230, 210))
        for rm in (self.data.get("floors") or [{}])[0].get("rooms") or []:
            a, b = T(rm["x"], rm["y"] + rm["d"]), T(rm["x"] + rm["w"], rm["y"])
            p.drawRect(QRectF(a, b))
        p.setPen(QColor("#374151"))
        p.drawText(QRectF(0, self.height() - m + 4, self.width(), 20), Qt.AlignCenter, "ด้านหน้าอาคาร")
        p.drawText(QRectF(0, 4, self.width(), 20), Qt.AlignCenter, "ด้านหลัง")
        if not self.stair:
            return
        pl = B.stair_plan(self.stair, self.s)
        p.setPen(QPen(QColor("#1F2937"), 1.4))
        p.setBrush(QColor(255, 255, 255, 235))
        for poly in pl["polys"]:
            p.drawPolygon(QPolygonF([T(*q) for q in poly]))
        p.setPen(QPen(QColor("#6B7280"), 0.8))
        for a, b in pl["treads"]:
            p.drawLine(T(*a), T(*b))
        p.setPen(QPen(QColor("#DC2626"), 1.6))
        w = [T(*q) for q in pl["walk"]]
        p.drawPolyline(QPolygonF(w))
        p.drawText(w[0] + QPointF(-14, 14), "ขึ้น")
        for b in B.stair_beams(self.stair, self.s, 0.0, self._cols()):  # the stair beams, dashed
            p.setPen(QPen(QColor("#2563EB"), 2.0, Qt.DashLine))
            p.drawLine(T(*b["p0"][:2]), T(*b["p1"][:2]))
        p.setPen(QPen(QColor("#2563EB"), 1))
        p.setBrush(QColor("#2563EB"))
        for c in B.stair_posts(self.stair, self.s, 0.0, self._cols()):
            q = T(*c["p0"][:2])
            p.drawRect(QRectF(q.x() - 3, q.y() - 3, 6, 6))


class StairAutoDialog(QDialog):
    def __init__(self, parent, data):
        super().__init__(parent)
        self.setWindowTitle("บันไดอัตโนมัติ — เลือกตำแหน่ง โปรแกรมออกแบบขนาดให้")
        self.data = data
        lay = QVBoxLayout(self)
        head = QLabel("อาคารมี 2 ชั้นขึ้นไป ต้องมีบันได — เลือกตำแหน่งที่ต้องการ โปรแกรมคำนวณจำนวนขั้น ลูกตั้ง ลูกนอน "
                      "และชานพักให้สมดุลกับความสูงชั้น ไม่ต่ำกว่ากฎกระทรวง ฉบับที่ 55 (แก้ภายหลังได้ที่ «บันได คสล.…»)")
        head.setWordWrap(True)
        head.setStyleSheet("background:#EEF6FF;color:#1F2937;padding:8px;border-radius:6px")
        lay.addWidget(head)
        row = QHBoxLayout()
        left = QVBoxLayout()
        left.addWidget(QLabel("<b>ตำแหน่งบันได</b>"))
        grid = QGridLayout()
        self.group = QButtonGroup(self)
        self.places = []
        for r, along in enumerate(("back", "front")):
            for c, across in enumerate(("left", "center", "right")):
                b = QRadioButton(SA.PLACES[(across, along)])
                self.group.addButton(b, len(self.places))
                self.places.append((across, along))
                grid.addWidget(b, r, c)
        self.group.button(self.places.index(("center", "front"))).setChecked(True)
        left.addLayout(grid)
        form = QGridLayout()
        self.width_box = QComboBox()
        for w in (0.90, 1.00, 1.10, 1.20):
            self.width_box.addItem(f"{w:.2f} ม." + ("  (แนะนำ)" if w == 1.00 else ""), w)
        self.width_box.setCurrentIndex(1)
        self.type_box = QComboBox()
        for key, th in (("U", "สองช่วง มีชานพักกลับทาง (แนะนำ)"), ("L", "ตัว L ชานพักเลี้ยว 90°"),
                        ("straight", "ช่วงตรง")):
            self.type_box.addItem(th, key)
        form.addWidget(QLabel("ความกว้าง"), 0, 0)
        form.addWidget(self.width_box, 0, 1)
        form.addWidget(QLabel("แบบบันได"), 1, 0)
        form.addWidget(self.type_box, 1, 1)
        left.addLayout(form)
        from PySide6.QtWidgets import QCheckBox
        self.fire = QCheckBox("บันไดหนีไฟ (แห่งที่ 2 — อาคาร 4 ชั้นขึ้นไป ตามกฎกระทรวง 55 ข้อ 27)")
        storeys = sum(1 for f in (data.get("floors") or []) if f.get("rooms"))
        self.fire.setVisible(storeys >= 4)
        has_main = bool(((data.get("floors") or [{}])[0].get("stairs")))
        self.fire.setChecked(storeys >= 4 and has_main and SA.needs_fire_stair(data))
        left.addWidget(self.fire)
        if storeys >= 4:
            warn = QLabel("⚠ อาคาร 4 ชั้นขึ้นไป: ต้องมีบันไดหนีไฟอีกอย่างน้อย 1 แห่ง — สร้างบันไดหลักก่อน "
                          "แล้วเปิดหน้าต่างนี้อีกครั้ง ติ๊ก «บันไดหนีไฟ» และเลือกตำแหน่งอีกด้านของอาคาร")
            warn.setWordWrap(True)
            warn.setStyleSheet("color:#B45309")
            left.addWidget(warn)
        self.report = QLabel()
        self.report.setWordWrap(True)
        self.report.setMinimumWidth(380)
        left.addWidget(self.report, 1)
        row.addLayout(left, 1)
        right = QVBoxLayout()
        self.preview = _Preview()
        self.preview.moved = self.move_to
        right.addWidget(self.preview, 1)
        tools = QHBoxLayout()
        for text, tip, fn in (("⟲ หมุน 90°", "หมุนบันไดรอบจุดกลาง", self.rotate),
                              ("↕ กลับหัว-ท้าย", "สลับขั้นแรกกับชานพัก", self.flip),
                              ("⇄ เลี้ยวซ้าย/ขวา", "ช่วงที่ 2 ไปอีกฟาก", self.swap_turn),
                              ("↺ ตำแหน่งแนะนำ", "กลับไปตำแหน่งที่โปรแกรมออกแบบ", self.reset_place)):
            b = QPushButton(text)
            b.setToolTip(tip)
            b.clicked.connect(fn)
            tools.addWidget(b)
        right.addLayout(tools)
        self.advice = QLabel()
        self.advice.setWordWrap(True)
        right.addWidget(self.advice)
        row.addLayout(right, 1)
        lay.addLayout(row, 1)
        btns = QHBoxLayout()
        btns.addStretch(1)
        self.only_floor = False
        floor = int(getattr(parent, "floor", 0) or 0)
        self.floor = min(floor, max(len(data.get("floors") or []) - 2, 0))
        self.one = QPushButton(f"🪜 สร้างเฉพาะชั้นนี้ (ชั้น {self.floor + 1}→{self.floor + 2})")
        self.one.setToolTip("สร้างบันไดเฉพาะจากชั้นที่เปิดอยู่ขึ้นไปชั้นถัดไป")
        self.one.clicked.connect(self._accept_one)
        self.ok = QPushButton("🪜 สร้างทุกชั้น (ตำแหน่งเดียวกัน)")
        self.ok.setStyleSheet("font-weight:700")
        self.ok.setDefault(True)
        self.ok.clicked.connect(self.accept)
        no = QPushButton("ไม่ต้องการตอนนี้")
        no.clicked.connect(self.reject)
        btns.addWidget(self.one)
        btns.addWidget(self.ok)
        btns.addWidget(no)
        lay.addLayout(btns)
        self.group.idClicked.connect(lambda _i: self.update_view())
        self.width_box.currentIndexChanged.connect(lambda _i: self.update_view())
        self.type_box.currentIndexChanged.connect(lambda _i: self.update_view())
        self.update_view()

    def where(self):
        return self.places[max(self.group.checkedId(), 0)]

    def _accept_one(self):
        self.only_floor = True
        self.accept()

    # -- moved / turned by hand: the design stays, the place changes
    def move_to(self, x, y):
        self.stair["x"], self.stair["y"] = x, y
        self._redraw()

    def rotate(self):
        self.stair["dir"] = (int(self.stair.get("dir", 1)) + 1) % 4
        self._redraw()

    def flip(self):
        self.stair["dir"] = (int(self.stair.get("dir", 1)) + 2) % 4
        self._redraw()

    def swap_turn(self):
        self.stair["turn"] = "right" if self.stair.get("turn", "left") == "left" else "left"
        self._redraw()

    def reset_place(self):
        self.update_view()

    def _redraw(self):
        s = self.rep["settings"]
        checks = SA.check_place(self.data, self.stair, s)
        good = all(ok for ok, _t in checks)
        self.advice.setText("<br>".join(("✓ " if ok else "✗ ") + t for ok, t in checks))
        self.advice.setStyleSheet(f"color:{'#065F46' if good else '#991B1B'};padding:6px;"
                                  f"background:{'#ECFDF5' if good else '#FEF2F2'};border-radius:6px")
        inside = checks[0][0]
        self.ok.setEnabled(self.rep["fits"] and inside)
        self.one.setEnabled(self.rep["fits"] and inside)
        self.preview.show_it(self.data, self.stair, s)

    def update_view(self):
        self.stair, rep = SA.design(self.data, self.where(), self.width_box.currentData(), self.type_box.currentData())
        self.rep = rep
        color = "#065F46" if rep["ok"] else "#991B1B"
        self.report.setText("<br>".join(rep["lines"]))
        self.report.setStyleSheet(f"color:{color};padding:6px;background:{'#ECFDF5' if rep['ok'] else '#FEF2F2'};"
                                  "border-radius:6px")
        self._redraw()
