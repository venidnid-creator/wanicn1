# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
"""แป · Sag Rod · Tie Rod · ผนังเมทัลชีท — the window and the booklet page,
with a roof-plan sketch of one bay: purlins, the sag rods and the X-bracing."""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (QCheckBox, QDialog, QDoubleSpinBox, QFormLayout, QHBoxLayout, QHeaderView,
                               QLabel, QPushButton, QSpinBox, QTableWidget, QTableWidgetItem, QVBoxLayout,
                               QWidget)

from core import wanic_purlin as P

INK = QColor("#111827")
PURL = QColor("#1D4ED8")
ROD = QColor("#DC2626")
TIE = QColor("#16A34A")


def _font(px, bold=False):
    f = QFont()
    f.setFamilies(["TH Sarabun New", "TH SarabunPSK", "Laksaman", "Tahoma"])
    f.setPixelSize(max(1, int(px)))
    f.setBold(bold)
    return f


def draw_plan(p: QPainter, rect: QRectF, prm: dict, res: dict, px: float = 11.0):
    """One slope over four bays (plan): trusses, purlins, sag rods; the
    X-bracing in the end bays."""
    bays = 4
    L, S = prm["span"], prm["slope_len"]
    tot = L * bays
    pad = px * 3
    sc = min((rect.width() - 2 * pad) / tot, (rect.height() - 2 * pad - px * 2.4) / S)
    ox = rect.left() + (rect.width() - tot * sc) / 2
    oy = rect.top() + (rect.height() - S * sc) / 2 + px * 1.2

    def P_(x, y):
        return QPointF(ox + x * sc, oy + y * sc)

    p.setPen(QPen(INK, px / 4))
    for i in range(bays + 1):
        p.drawLine(P_(i * L, 0), P_(i * L, S))                       # trusses
    p.setPen(QPen(PURL, px / 6))
    n = res["n_purlins"]
    for k in range(n):
        y = S * k / max(1, n - 1)
        p.drawLine(P_(0, y), P_(tot, y))
    sag = int(prm["sag_rods"])
    if sag:
        p.setPen(QPen(ROD, px / 6, Qt.DashLine))
        for i in range(bays):
            for k in range(1, sag + 1):
                x = i * L + L * k / (sag + 1)
                p.drawLine(P_(x, 0), P_(x, S))
    p.setPen(QPen(TIE, px / 5))
    for i in (0, bays - 1):
        p.drawLine(P_(i * L, 0), P_((i + 1) * L, S / 2))
        p.drawLine(P_(i * L, S / 2), P_((i + 1) * L, 0))
        p.drawLine(P_(i * L, S / 2), P_((i + 1) * L, S))
        p.drawLine(P_(i * L, S), P_((i + 1) * L, S / 2))
    p.setFont(_font(px))
    p.setPen(INK)
    p.drawText(QRectF(ox, oy - px * 2.2, tot * sc, px * 1.6), Qt.AlignCenter, "อกไก่ (Ridge)")
    p.drawText(QRectF(ox, oy + S * sc + px * 0.4, tot * sc, px * 1.6), Qt.AlignCenter,
               f"ชายคา (Eave) — ช่วงโครง {L:.2f} ม. · ลาดยาว {S:.2f} ม.")
    y = rect.top() + px * 0.2
    x0 = rect.left() + 4
    for col, t in ((PURL, f"แป {res['purlin'][0].label} @ {prm['spacing']:.2f} ม."),
                   (ROD, f"Sag Rod {res['rod'] or '—'}"), (TIE, f"Tie Rod {res['tie']}")):
        p.setPen(col)
        p.drawText(QRectF(x0, y, rect.width(), px * 1.4), Qt.AlignLeft, t)
        x0 += p.fontMetrics().horizontalAdvance(t) + px * 2


class PlanWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.prm = self.res = None
        self.setMinimumHeight(260)

    def set(self, prm, res):
        self.prm, self.res = prm, res
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor("#FFFFFF"))
        if self.res:
            draw_plan(p, QRectF(self.rect()), self.prm, self.res, 12)
        p.end()


FIELDS = (("span", "ช่วงแป = ระยะโครง Truss/จันทัน (ม.)", 0.5, 12, 2),
          ("spacing", "ระยะแป (ม.)", 0.2, 2.5, 2),
          ("pitch", "ความชันหลังคา (องศา)", 1, 60, 1),
          ("slope_len", "ความยาวลาดหลังคา อกไก่–ชายคา (ม.)", 1, 40, 2),
          ("dead", "น้ำหนักวัสดุมุง (กก./ตร.ม.)", 0, 150, 1),
          ("live", "น้ำหนักจรหลังคา (กก./ตร.ม.)", 0, 200, 1),
          ("wind", "แรงลม (กก./ตร.ม.)", 0, 300, 1),
          ("width", "ความกว้างหน้าจั่ว (ม.)", 1, 80, 2),
          ("eave_h", "ความสูงชายคา (ม.)", 1, 30, 2),
          ("girt_span", "ช่วงแปผนัง (ม.)", 0.5, 12, 2),
          ("girt_sp", "ระยะแปผนัง (ม.)", 0.3, 3, 2),
          ("sheet_kg", "น้ำหนักแผ่นผนัง (กก./ตร.ม.)", 1, 30, 1))


class PurlinDialog(QDialog):
    def __init__(self, parent, data: dict):
        super().__init__(parent)
        self.setWindowTitle("แป · Sag Rod · Tie Rod · ผนังเมทัลชีท")
        self.resize(1200, 760)
        self.data = data
        prm = P.params_of(data)
        lay = QHBoxLayout(self)
        form = QFormLayout()
        self.sp = {}
        for key, th, lo, hi, dec in FIELDS:
            w = QDoubleSpinBox()
            w.setRange(lo, hi)
            w.setDecimals(dec)
            w.setValue(float(prm[key]))
            w.valueChanged.connect(self.recalc)
            self.sp[key] = w
            form.addRow(th, w)
        self.sag = QSpinBox()
        self.sag.setRange(0, 3)
        self.sag.setValue(int(prm["sag_rods"]))
        self.sag.valueChanged.connect(self.recalc)
        form.addRow("Sag Rod ต่อช่วง (แนว)", self.sag)
        self.bays = QSpinBox()
        self.bays.setRange(1, 6)
        self.bays.setValue(int(prm["braced_bays"]))
        self.bays.valueChanged.connect(self.recalc)
        form.addRow("ช่วงที่มี X-Bracing", self.bays)
        self.auto = QCheckBox("เลือกขนาดเหล็กตัวซีที่เบาที่สุดที่ผ่านให้อัตโนมัติ")
        self.auto.setChecked(bool(prm["auto"]))
        self.wall = QCheckBox("ผนังเมทัลชีท (ออกแบบแปผนัง)")
        self.wall.setChecked(bool(prm["wall_sheet"]))
        for w in (self.auto, self.wall):
            w.toggled.connect(self.recalc)
            form.addRow(w)
        self.prm0 = prm
        left = QVBoxLayout()
        left.addLayout(form)
        left.addStretch(1)
        b = QHBoxLayout()
        pdf = QPushButton("รายการคำนวณ (.pdf)")
        pdf.clicked.connect(self.export_pdf)
        ok = QPushButton("บันทึก")
        ok.setStyleSheet("font-weight: 700;")
        ok.clicked.connect(self.accept)
        cancel = QPushButton("ยกเลิก")
        cancel.clicked.connect(self.reject)
        for w in (pdf, ok, cancel):
            b.addWidget(w)
        left.addLayout(b)
        lay.addLayout(left)
        right = QVBoxLayout()
        self.view = PlanWidget()
        right.addWidget(self.view, 3)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["รายการ", "แรงที่เกิด", "กำลังที่รับได้", "อัตราส่วน"])
        self.table.verticalHeader().hide()
        hh = self.table.horizontalHeader()
        for c, mode in enumerate((QHeaderView.Stretch, QHeaderView.Stretch, QHeaderView.ResizeToContents,
                                  QHeaderView.ResizeToContents)):
            hh.setSectionResizeMode(c, mode)
        self.table.setWordWrap(True)
        right.addWidget(self.table, 2)
        self.info = QLabel()
        self.info.setWordWrap(True)
        right.addWidget(self.info)
        lay.addLayout(right, 1)
        self.res = None
        self.recalc()

    def params(self) -> dict:
        p = dict(self.prm0)
        p.update({k: w.value() for k, w in self.sp.items()})
        p.update(sag_rods=self.sag.value(), braced_bays=self.bays.value(), auto=self.auto.isChecked(),
                 wall_sheet=self.wall.isChecked())
        return p

    def recalc(self, *_):
        prm = self.params()
        self.res = P.design(prm)
        self.view.set(prm, self.res)
        rows = self.res["rows"]
        self.table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            for c, v in enumerate((row.name, row.demand, row.capacity, f"{row.ratio:.2f}")):
                it = QTableWidgetItem(v)
                if c == 3:
                    it.setForeground(QColor("#15803D") if row.ok else QColor("#B91C1C"))
                self.table.setItem(r, c, it)
        self.table.resizeRowsToContents()
        bad = [r for r in rows if not r.ok]
        self.info.setText("✓ ผ่านทุกรายการ (ASD, Fy 2,450 กก./ตร.ซม.)" if not bad else
                          f"✗ ไม่ผ่าน {len(bad)} รายการ — ลดช่วง/ระยะแป เพิ่ม Sag Rod หรือให้เลือกขนาดอัตโนมัติ")

    def export_pdf(self):
        from PySide6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getSaveFileName(self, "รายการคำนวณแป", "รายการคำนวณแป.pdf", "PDF (*.pdf)")
        if not path:
            return
        from core import wanic_calc as C
        from core.wanic_calc_book import Book
        b_ = C.basis(self.data)
        bk = Book(path, {k: b_.get(k, "") for k in ("project", "owner", "place", "engineer", "qualification")})
        purlin_pages(bk, self.params(), self.res)
        bk.close()
        self.info.setText(self.info.text() + f"\nบันทึกแล้ว: {path}")


def purlin_pages(bk, prm: dict, res: dict):
    from core.wanic_calc_book import GREEN, RED
    mm = bk.mm
    bk.page("แป · Sag Rod · Tie Rod · ผนังเมทัลชีท", "Purlin")
    bk.p.setRenderHint(QPainter.Antialiasing)
    draw_plan(bk.p, QRectF(10 * mm, 32 * mm, 384 * mm, 100 * mm), prm, res, 5.5 * mm)
    y = 138
    bk.text(12, y, 380, 7, f"วัสดุมุง {prm['dead']:g} กก./ตร.ม. (ตามลาด) · น้ำหนักจร {prm['live']:g} กก./ตร.ม. · "
            f"แรงลม {prm['wind']:g} กก./ตร.ม. (แรงดูด Cp 0.7, หน่วยแรงเพิ่ม ⅓) · ความชัน {prm['pitch']:g}° · "
            f"แอ่นตัว L/180", 5.6)
    y += 10
    for r in res["rows"]:
        bk.text(12, y, 300, 7, r.name, 6.2, bold=True)
        bk.text(330, y, 60, 7, f"{r.ratio:.2f}  {'ผ่าน' if r.ok else 'ไม่ผ่าน'}", 6.2, GREEN if r.ok else RED,
                bold=True)
        y += 7
        for part in (r.demand, f"กำลังที่รับได้: {r.capacity}" + (f"   ·   {r.note}" if r.note else "")):
            bk.text(20, y, 370, 6.5, part, 5.6)
            y += 6.6
        y += 3
