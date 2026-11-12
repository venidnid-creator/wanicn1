# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
"""แรงด้านข้าง — the window (standards, site, wind zone), the elevation with
the level forces, the tables, and the booklet page."""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDoubleSpinBox, QFormLayout, QHBoxLayout,
                               QHeaderView, QLabel, QPushButton, QTableWidget, QTableWidgetItem, QTabWidget,
                               QVBoxLayout, QWidget)

from core import wanic_lateral as L

INK = QColor("#111827")
EQ = QColor("#DC2626")
WIND = QColor("#1D4ED8")
OK = QColor("#15803D")
BAD = QColor("#B91C1C")


def _font(px, bold=False):
    f = QFont()
    f.setFamilies(["TH Sarabun New", "TH SarabunPSK", "Laksaman", "Tahoma"])
    f.setPixelSize(max(1, int(px)))
    f.setBold(bold)
    return f


def _arrow(p, a: QPointF, b: QPointF, px):
    p.drawLine(a, b)
    d = b - a
    ln = (d.x() ** 2 + d.y() ** 2) ** 0.5 or 1
    ux, uy = d.x() / ln, d.y() / ln
    s = px * 0.6
    p.drawPolygon(QPolygonF([b, QPointF(b.x() - ux * s * 1.6 - uy * s, b.y() - uy * s * 1.6 + ux * s),
                             QPointF(b.x() - ux * s * 1.6 + uy * s, b.y() - uy * s * 1.6 - ux * s)]))


def draw_elevation(p: QPainter, rect: QRectF, res: dict, d_: str = "X", px: float = 11.0):
    """The frame in elevation along d_, the earthquake forces (left, red)
    and the wind (right, blue) at each level, the storey shears."""
    lv = res["levels"]
    if not lv:
        return
    Lx, Ly = res["size"]
    span = Lx if d_ == "X" else Ly
    Htot = lv[-1][1]
    pad = px * 9
    sc = min((rect.width() - 2 * pad) / span, (rect.height() - px * 6) / Htot)
    ox = rect.left() + (rect.width() - span * sc) / 2
    oy = rect.bottom() - px * 3

    def P_(x, y):
        return QPointF(ox + x * sc, oy - y * sc)

    p.setPen(QPen(INK, max(1.0, px / 6)))
    p.drawLine(P_(-span * 0.1, 0), P_(span * 1.1, 0))
    for x in (0.0, span):
        p.drawLine(P_(x, 0), P_(x, Htot))
    for _j, h, _w in lv:
        p.drawLine(P_(0, h), P_(span, h))
    eq, wd = res["eq"][d_], res["wind"][d_]
    fmax = max(max(eq["F"] or [0]), max(wd["F"] or [0]), 1.0)
    p.setFont(_font(px * 0.9))
    for k, (_j, h, w) in enumerate(lv):
        if eq["V"] > 0:
            ln = px * 6 * eq["F"][k] / fmax + px
            p.setPen(QPen(EQ, max(1.0, px / 6)))
            p.setBrush(EQ)
            _arrow(p, QPointF(P_(0, h).x() - ln - px, P_(0, h).y()), QPointF(P_(0, h).x() - px * 0.4, P_(0, h).y()), px)
            p.drawText(QRectF(P_(0, h).x() - px * 9, P_(0, h).y() - px * 1.5, px * 8, px * 1.3), Qt.AlignRight,
                       f"{eq['F'][k] / 1000:,.2f} ตัน")
        ln = px * 6 * wd["F"][k] / fmax + px
        p.setPen(QPen(WIND, max(1.0, px / 6)))
        p.setBrush(WIND)
        a = P_(span, h)
        _arrow(p, QPointF(a.x() + ln + px, a.y()), QPointF(a.x() + px * 0.4, a.y()), px)
        p.drawText(QRectF(a.x() + px * 2, a.y() - px * 1.6, px * 8, px * 1.3), Qt.AlignLeft, f"{wd['F'][k] / 1000:,.2f} ตัน")
        p.setPen(INK)
        p.drawText(QRectF(P_(0, h).x(), P_(0, h).y() + px * 0.1, span * sc, px * 1.3), Qt.AlignCenter,
                   f"ระดับ {_j} · h {h:.2f} ม. · W {w / 1000:,.1f} ตัน")
    p.setBrush(Qt.NoBrush)
    p.setPen(INK)
    p.drawText(QRectF(rect.left(), oy + px * 0.6, rect.width(), px * 1.3), Qt.AlignCenter,
               f"แนว {d_} กว้าง {span:.2f} ม. — แผ่นดินไหว V = {eq['V'] / 1000:,.2f} ตัน (แดง) · ลม V = "
               f"{wd['V'] / 1000:,.2f} ตัน (น้ำเงิน)")


class ElevWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.res = None
        self.d_ = "X"
        self.setMinimumHeight(300)

    def set(self, res, d_):
        self.res, self.d_ = res, d_
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor("#FFFFFF"))
        if self.res:
            draw_elevation(p, QRectF(self.rect()), self.res, self.d_, 12)
        p.end()


LEVEL_HEAD = ["ระดับ", "สูง (ม.)", "W (ตัน)", "แผ่นดินไหว X (ตัน)", "แผ่นดินไหว Y (ตัน)", "ลม X (ตัน)", "ลม Y (ตัน)",
              "แรงลม (กก./ตร.ม.)"]
CHECK_HEAD = ["ชั้น", "แรง", "แนว", "แรงเฉือนชั้น (ตัน)", "เสา (ต้น)", "เสาวิกฤต", "Pu (ตัน)", "Mu (ตัน-ม.)",
              "อัตราส่วน P-M"]


def level_rows(res):
    out = []
    for k, (j, h, w) in enumerate(res["levels"]):
        out.append((str(j), f"{h:.2f}", f"{w / 1000:,.2f}", f"{res['eq']['X']['F'][k] / 1000:,.3f}",
                    f"{res['eq']['Y']['F'][k] / 1000:,.3f}", f"{res['wind']['X']['F'][k] / 1000:,.3f}",
                    f"{res['wind']['Y']['F'][k] / 1000:,.3f}", f"{res['wind']['X']['p'][k]:.1f}"))
    return out


def check_rows(res):
    return [(str(c["floor"] + 1), c["action"], c["dir"], f"{c['V'] / 1000:,.2f}", str(c["n"]), c["col"],
             f"{c['Pu'] / 1000:,.2f}", f"{c['Mu'] / 1000:,.3f}", f"{c['ratio']:.2f}") for c in res["checks"]]


def summary(res) -> list:
    W = sum(w for _j, _h, w in res["levels"])
    bad = sum(1 for c in res["checks"] if c["ratio"] > 1)
    return [f"น้ำหนักอาคาร (น้ำหนักบรรทุกคงที่) W = {W / 1000:,.1f} ตัน · ขนาด {res['size'][0]:.2f} × "
            f"{res['size'][1]:.2f} ม. · {len(res['levels'])} ระดับ",
            "แผ่นดินไหว: " + res["eq"]["X"]["text"] + (f" · V = {res['eq']['X']['V'] / 1000:,.2f} ตัน"
                                                       if res["eq"]["X"]["V"] else ""),
            "ลม: " + res["wind"]["X"]["text"] + f" · V(X) = {res['wind']['X']['V'] / 1000:,.2f} ตัน · "
            f"V(Y) = {res['wind']['Y']['V'] / 1000:,.2f} ตัน",
            "ตรวจเสา: แรงเฉือนชั้นแบ่งให้เสาเท่ากัน M = V·h/2 · U = 0.75(1.4D + 1.7L + 1.87E) / 0.75(1.4D + 1.7L + 1.6W) "
            "บนเส้นโค้ง P-M — " + ("✓ ผ่านทุกชั้น" if not bad else f"✗ ไม่ผ่าน {bad} รายการ (เพิ่มขนาด/เหล็กเสาในขั้น 6)")]


class LateralDialog(QDialog):
    def __init__(self, parent, data: dict):
        super().__init__(parent)
        self.setWindowTitle("แรงด้านข้าง — แผ่นดินไหวและลม")
        self.resize(1280, 820)
        self.data = data
        p = L.params_of(data)
        lay = QHBoxLayout(self)
        form = QFormLayout()
        self.eq_on = QCheckBox("คิดแรงแผ่นดินไหว (อาคารอยู่ในพื้นที่บังคับใช้)")
        self.eq_on.setChecked(bool(p["eq_on"]))
        form.addRow(self.eq_on)
        self.std = QComboBox()
        self.std.addItem("มยผ. 1301/1302-61 (ปัจจุบัน)", "new")
        self.std.addItem("กฎกระทรวง 2550 V = ZIKCSW (สูตรเดิม)", "old")
        self.std.setCurrentIndex(0 if p["standard"] == "new" else 1)
        form.addRow("มาตรฐานแผ่นดินไหว", self.std)
        self.sp = {}
        for key, th, lo, hi, dec in (("Ss", "Ss (ตามอำเภอ, ตาราง มยผ.)", 0, 3, 3), ("S1", "S1 (ตามอำเภอ)", 0, 2, 3),
                                     ("I", "ตัวประกอบความสำคัญ I", 1, 1.5, 2),
                                     ("S_old", "S ชั้นดิน (สูตรเดิม 1.0–1.5)", 1, 1.5, 2),
                                     ("Iw", "ตัวประกอบความสำคัญลม Iw", 0.8, 1.15, 2)):
            w = QDoubleSpinBox()
            w.setRange(lo, hi)
            w.setDecimals(dec)
            w.setSingleStep(0.01 if dec == 3 else 0.05)
            w.setValue(float(p[key]))
            self.sp[key] = w
        self.site = QComboBox()
        for k, v in L.SITE_TH.items():
            self.site.addItem(v, k)
        self.site.setCurrentIndex(max(0, self.site.findData(p["site"])))
        self.system = QComboBox()
        for k, (v, R) in L.SYSTEMS.items():
            self.system.addItem(f"{v} (R = {R:g})", k)
        self.system.setCurrentIndex(max(0, self.system.findData(p["system"])))
        self.zone = QComboBox()
        for k in L.ZONE_Z:
            self.zone.addItem(f"เขต {k} (Z = {L.ZONE_Z[k]:g})", k)
        self.zone.setCurrentIndex(max(0, self.zone.findData(p["zone"])))
        self.wstd = QComboBox()
        self.wstd.addItem("มยผ. 1311-50 (ปัจจุบัน)", "new")
        self.wstd.addItem("กฎกระทรวง ฉบับที่ 6 (สูตรเดิม)", "old")
        self.wstd.setCurrentIndex(0 if p["wind_std"] == "new" else 1)
        self.wzone = QComboBox()
        for k, (v, tf) in L.WIND_ZONES.items():
            self.wzone.addItem(f"เขต {k} · V50 {v:g} ม./วินาที" + (f" · TF {tf:g}" if tf != 1 else ""), k)
        self.wzone.setCurrentIndex(max(0, self.wzone.findData(p["wind_zone"])))
        self.terrain = QComboBox()
        self.terrain.addItem("A ที่โล่ง / ชายทะเล", "A")
        self.terrain.addItem("B ชานเมือง / ในเมือง", "B")
        self.terrain.setCurrentIndex(0 if p["terrain"] == "A" else 1)
        form.addRow("Ss (ตามอำเภอ, ตาราง มยผ.)", self.sp["Ss"])
        form.addRow("S1 (ตามอำเภอ)", self.sp["S1"])
        form.addRow("ประเภทชั้นดิน", self.site)
        form.addRow("ระบบโครงสร้าง", self.system)
        form.addRow("ตัวประกอบความสำคัญ I", self.sp["I"])
        form.addRow("เขตแผ่นดินไหว (สูตรเดิม)", self.zone)
        form.addRow("S ชั้นดิน (สูตรเดิม)", self.sp["S_old"])
        form.addRow(QLabel("— ลม —"))
        form.addRow("มาตรฐานลม", self.wstd)
        form.addRow("เขตความเร็วลม", self.wzone)
        form.addRow("สภาพภูมิประเทศ", self.terrain)
        form.addRow("ตัวประกอบความสำคัญ Iw", self.sp["Iw"])
        for w in list(self.sp.values()):
            w.valueChanged.connect(self.recalc)
        for w in (self.std, self.site, self.system, self.zone, self.wstd, self.wzone, self.terrain):
            w.currentIndexChanged.connect(self.recalc)
        self.eq_on.toggled.connect(self.recalc)
        left = QVBoxLayout()
        left.addLayout(form)
        self.info = QLabel()
        self.info.setWordWrap(True)
        self.info.setMaximumWidth(460)
        left.addWidget(self.info)
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
        dirs = QHBoxLayout()
        self.dir = QComboBox()
        self.dir.addItem("รูปด้านแนว X", "X")
        self.dir.addItem("รูปด้านแนว Y", "Y")
        self.dir.currentIndexChanged.connect(self.recalc)
        dirs.addWidget(self.dir)
        dirs.addStretch(1)
        right.addLayout(dirs)
        self.view = ElevWidget()
        right.addWidget(self.view, 3)
        self.tabs = QTabWidget()
        self.t_lv = self._table(LEVEL_HEAD)
        self.t_ck = self._table(CHECK_HEAD)
        self.tabs.addTab(self.t_lv, "แรงแต่ละระดับ")
        self.tabs.addTab(self.t_ck, "ตรวจเสา (P-M)")
        right.addWidget(self.tabs, 2)
        lay.addLayout(right, 1)
        self.res = None
        self.recalc()

    @staticmethod
    def _table(head):
        t = QTableWidget(0, len(head))
        t.setHorizontalHeaderLabels(head)
        t.verticalHeader().hide()
        t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        t.horizontalHeader().setStretchLastSection(True)
        return t

    def params(self) -> dict:
        p = {k: w.value() for k, w in self.sp.items()}
        p.update(eq_on=self.eq_on.isChecked(), standard=self.std.currentData(), site=self.site.currentData(),
                 system=self.system.currentData(), zone=self.zone.currentData(), wind_std=self.wstd.currentData(),
                 wind_zone=self.wzone.currentData(), terrain=self.terrain.currentData())
        return p

    def recalc(self, *_):
        p = self.params()
        new = p["standard"] == "new"
        for w in (self.sp["Ss"], self.sp["S1"], self.site):
            w.setEnabled(p["eq_on"] and new)
        for w in (self.zone, self.sp["S_old"]):
            w.setEnabled(p["eq_on"] and not new)
        for w in (self.system, self.sp["I"], self.std):
            w.setEnabled(p["eq_on"])
        for w in (self.wzone, self.terrain, self.sp["Iw"]):
            w.setEnabled(p["wind_std"] == "new")
        self.res = L.analyse({**self.data, "lateral": p})
        self.view.set(self.res, self.dir.currentData())
        for t, rows, rc in ((self.t_lv, level_rows(self.res), None), (self.t_ck, check_rows(self.res), 8)):
            t.setRowCount(len(rows))
            for r, row in enumerate(rows):
                for c, v in enumerate(row):
                    it = QTableWidgetItem(v)
                    if c == rc:
                        it.setForeground(OK if float(v) <= 1 else BAD)
                    t.setItem(r, c, it)
        self.info.setText("\n\n".join(summary(self.res)))

    def export_pdf(self):
        from PySide6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getSaveFileName(self, "รายการคำนวณแรงด้านข้าง", "รายการคำนวณแรงด้านข้าง.pdf",
                                              "PDF (*.pdf)")
        if not path:
            return
        from core import wanic_calc as C
        from core.wanic_calc_book import Book
        b_ = C.basis(self.data)
        bk = Book(path, {k: b_.get(k, "") for k in ("project", "owner", "place", "engineer", "qualification")})
        lateral_pages(bk, self.res)
        bk.close()
        self.info.setText(self.info.text() + f"\nบันทึกแล้ว: {path}")


def lateral_pages(bk, res):
    from core.wanic_calc_book import GREEN, RED
    mm = bk.mm
    bk.page("แรงด้านข้าง — แผ่นดินไหวและลม", "Lateral")
    bk.p.setRenderHint(QPainter.Antialiasing)
    draw_elevation(bk.p, QRectF(10 * mm, 32 * mm, 190 * mm, 110 * mm), res, "X", 4.6 * mm)
    draw_elevation(bk.p, QRectF(205 * mm, 32 * mm, 190 * mm, 110 * mm), res, "Y", 4.6 * mm)
    y = 146
    for ln in summary(res):
        parts, cur = [], ""
        for word in ln.split(" "):
            if len(cur) + len(word) > 150 and cur:
                parts.append(cur)
                cur = "   "
            cur += word + " "
        parts.append(cur)
        for part in parts:
            bk.text(10, y, 384, 6.2, part, 5.4)
            y += 6.2
    y += 2
    bk.table(10, y, [16, 18, 22, 40, 40, 28, 28, 40], [tuple(LEVEL_HEAD)] + level_rows(res), 6.4)
    rows = [r[:8] + ((r[8], GREEN if float(r[8]) <= 1 else RED),) for r in check_rows(res)]
    for k in range(0, len(rows), 30):
        bk.page("แรงด้านข้าง — ตรวจเสารับแรงด้านข้าง (P-M)", "Lateral")
        bk.table(10, 34, [16, 30, 16, 40, 22, 70, 30, 34, 34], [tuple(CHECK_HEAD)] + rows[k:k + 30], 7.0)
