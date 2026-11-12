# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
"""พื้นไร้คาน (Flat Slab + Drop Panel, DDM) — the window and the booklet
pages: the plan with its column / middle strips and drop panels, the
moments and bars per strip, the punching shear."""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDoubleSpinBox, QFormLayout, QHBoxLayout,
                               QHeaderView, QLabel, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
                               QTabWidget, QVBoxLayout, QWidget)

from core import wanic_flatslab as F
from core import wanic_rc as R

INK = QColor("#111827")
CS = QColor(29, 78, 216, 40)
DROP = QColor("#F59E0B")
OK = QColor("#15803D")
BAD = QColor("#B91C1C")


def _font(px, bold=False):
    f = QFont()
    f.setFamilies(["TH Sarabun New", "TH SarabunPSK", "Laksaman", "Tahoma"])
    f.setPixelSize(max(1, int(px)))
    f.setBold(bold)
    return f


def draw_plan(p: QPainter, rect: QRectF, prm: dict, res: dict, px: float = 11.0):
    sx, sy = prm["x"], prm["y"]
    xs = [0.0]
    for v in sx:
        xs.append(xs[-1] + v)
    ys = [0.0]
    for v in sy:
        ys.append(ys[-1] + v)
    pad = px * 4
    sc = min((rect.width() - 2 * pad) / xs[-1], (rect.height() - 2 * pad) / ys[-1])
    ox = rect.left() + (rect.width() - xs[-1] * sc) / 2
    oy = rect.top() + (rect.height() + ys[-1] * sc) / 2

    def P_(x, y):
        return QPointF(ox + x * sc, oy - y * sc)

    p.fillRect(QRectF(P_(0, ys[-1]), P_(xs[-1], 0)), QColor("#F9FAFB"))
    # column strips along both directions (half the shorter span wide)
    cw = res["dirs"][0]["cs"]
    p.setPen(Qt.NoPen)
    for y in ys:
        p.fillRect(QRectF(P_(0, min(y + cw / 2, ys[-1])), P_(xs[-1], max(y - cw / 2, 0))), CS)
    cw = res["dirs"][1]["cs"]
    for x in xs:
        p.fillRect(QRectF(P_(max(x - cw / 2, 0), ys[-1]), P_(min(x + cw / 2, xs[-1]), 0)), CS)
    if res.get("drop_w"):
        dx, dy = res["drop_w"]
        p.setPen(QPen(DROP, max(1.0, px / 6), Qt.DashLine))
        p.setBrush(Qt.NoBrush)
        for x in xs:
            for y in ys:
                p.drawRect(QRectF(P_(max(x - dx / 2, 0), min(y + dy / 2, ys[-1])),
                                  P_(min(x + dx / 2, xs[-1]), max(y - dy / 2, 0))))
    p.setPen(QPen(INK, max(1.0, px / 7)))
    p.setBrush(Qt.NoBrush)
    p.drawRect(QRectF(P_(0, ys[-1]), P_(xs[-1], 0)))
    c = prm["col"]
    p.setBrush(INK)
    for x in xs:
        for y in ys:
            p.drawRect(QRectF(P_(x - c / 2, y + c / 2), P_(x + c / 2, y - c / 2)))
    nx, ny = R.axis_names(len(xs), False), R.axis_names(len(ys), True)
    p.setFont(_font(px, True))
    p.setBrush(Qt.NoBrush)
    for i, x in enumerate(xs):
        q = P_(x, ys[-1])
        p.drawEllipse(QPointF(q.x(), q.y() - px * 2.2), px * 0.9, px * 0.9)
        p.drawText(QRectF(q.x() - px, q.y() - px * 3.1, px * 2, px * 1.8), Qt.AlignCenter, nx[i])
    for j, y in enumerate(ys):
        q = P_(0, y)
        p.drawEllipse(QPointF(q.x() - px * 2.2, q.y()), px * 0.9, px * 0.9)
        p.drawText(QRectF(q.x() - px * 3.2, q.y() - px * 0.9, px * 2, px * 1.8), Qt.AlignCenter, ny[j])
    p.setFont(_font(px * 0.9))
    for i, v in enumerate(sx):
        q = P_(xs[i] + v / 2, 0)
        p.drawText(QRectF(q.x() - px * 3, q.y() + px * 0.4, px * 6, px * 1.4), Qt.AlignCenter, f"{v:.2f}")
    for j, v in enumerate(sy):
        q = P_(xs[-1], ys[j] + v / 2)
        p.drawText(QRectF(q.x() + px * 0.5, q.y() - px * 0.7, px * 5, px * 1.4), Qt.AlignLeft, f"{v:.2f}")
    p.setFont(_font(px * 0.9))
    p.setPen(QColor(29, 78, 216))
    p.drawText(QRectF(rect.left() + 4, rect.bottom() - px * 1.5, rect.width(), px * 1.4), Qt.AlignLeft,
               "แถบสีฟ้า = แถบเสา (Column Strip)" + ("    เส้นประส้ม = แผ่นหนา (Drop Panel)"
                                                    if res.get("drop_w") else ""))


class PlanWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.prm = self.res = None
        self.setMinimumHeight(300)

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


STRIP_HEAD = ["ช่วง", "ยาว l1", "ตำแหน่ง", "แถบ", "สัดส่วน×Mo", "M (กก.-ม.)", "กว้าง (ม.)", "As ต้องการ",
              "เหล็กเสริม", "As ใช้", "ผล"]
PUNCH_HEAD = ["เสา", "หน้าตัดวิกฤต", "b0 (ม.)", "d (ม.)", "Vu (กก.)", "Vc (กก.)", "อัตราส่วน"]


def strip_rows(d):
    out = []
    for r in d["rows"]:
        out.append((str(r["span"]), f"{r['l1']:.2f}", r["loc"], r["strip"], f"{r['k']:.3f}", f"{r['M']:,.0f}",
                    f"{r['b']:.2f}", "—" if r["As"] == float("inf") else f"{r['As']:.2f}", r["bars"],
                    f"{r['As_used']:.2f}", "ผ่าน" if r["ok"] else "ไม่ผ่าน"))
    return out


def punch_rows(res):
    return [(q["col"], q["where"], f"{q['b0']:.2f}", f"{q['d']:.3f}", f"{q['Vu']:,.0f}", f"{q['Vc']:,.0f}",
             f"{q['ratio']:.2f}") for q in res["punch"]]


def summary(prm, res) -> str:
    t = res["thick"]
    meth = "กำลัง (SDM) U = 1.4D + 1.7L" if res["method"] == "SDM" else "หน่วยแรงใช้งาน (WSD)"
    bad = sum(1 for d in res["dirs"] for r in d["rows"] if not r["ok"]) + \
        sum(1 for q in res["punch"] if q["ratio"] > 1)
    return (f"{meth} · พื้นหนา {prm['t'] * 100:.0f} ซม. (ขั้นต่ำ {t['need'] * 100:.0f} ซม.: ln {t['ln']:.2f} ม. / "
            f"{'36·33' if prm['drop'] else '33·30'})"
            + (f" · แผ่นหนาเพิ่ม {prm['drop_t'] * 100:.0f} ซม. กว้าง l/3" if prm["drop"] else " · ไม่มีแผ่นหนา (Flat Plate)")
            + f" · เสา {prm['col'] * 100:.0f} ซม. · wu = {res['wu']:,.0f} กก./ตร.ม. · d = {res['d'] * 100:.1f} ซม.\n"
            + ("✓ ผ่านทุกรายการ" if not bad and prm["t"] >= t["need"] - 1e-9 else
               f"✗ ไม่ผ่าน {bad} รายการ" + (" · พื้นบางกว่าขั้นต่ำ" if prm["t"] < t["need"] - 1e-9 else "")))


class FlatSlabDialog(QDialog):
    def __init__(self, parent, data: dict):
        super().__init__(parent)
        self.setWindowTitle("พื้นไร้คาน Flat Slab + Drop Panel (DDM)")
        self.resize(1280, 800)
        self.data = data
        prm = F.params_of(data)
        lay = QHBoxLayout(self)
        form = QFormLayout()
        self.ex = QLineEdit(", ".join(f"{v:g}" for v in prm["x"]))
        self.ey = QLineEdit(", ".join(f"{v:g}" for v in prm["y"]))
        form.addRow("ช่วงแกนตัวเลข (ม.)", self.ex)
        form.addRow("ช่วงแกนตัวอักษร (ม.)", self.ey)
        self.sp = {}
        for key, th, lo, hi, dec, mul in (("t", "ความหนาพื้น (ซม.)", 8, 60, 0, 100),
                                          ("drop_t", "แผ่นหนาเพิ่ม (ซม.)", 0, 60, 0, 100),
                                          ("col", "ขนาดเสา (ซม.)", 15, 150, 0, 100),
                                          ("finish", "วัสดุปูพื้น + ฝ้า (กก./ตร.ม.)", 0, 500, 0, 1),
                                          ("ll", "น้ำหนักบรรทุกจร (กก./ตร.ม.)", 0, 2000, 0, 1)):
            w = QDoubleSpinBox()
            w.setRange(lo, hi)
            w.setDecimals(dec)
            w.setValue(float(prm[key]) * mul)
            w.setProperty("mul", mul)
            w.valueChanged.connect(self.recalc)
            self.sp[key] = w
            form.addRow(th, w)
        self.drop = QCheckBox("มีแผ่นหนาหัวเสา (Drop Panel)")
        self.drop.setChecked(bool(prm["drop"]))
        self.drop.toggled.connect(self.recalc)
        form.addRow(self.drop)
        self.bar = QComboBox()
        for b in (10, 12, 16, 20):
            self.bar.addItem(f"DB{b}", b)
        self.bar.setCurrentIndex(max(0, self.bar.findData(int(prm["bar"]))))
        self.bar.currentIndexChanged.connect(self.recalc)
        form.addRow("ขนาดเหล็กเสริม", self.bar)
        for e in (self.ex, self.ey):
            e.textChanged.connect(self.recalc)
        auto = QPushButton("ใช้ความหนาขั้นต่ำ")
        auto.clicked.connect(self.use_min)
        form.addRow(auto)
        left = QVBoxLayout()
        left.addLayout(form)
        self.info = QLabel()
        self.info.setWordWrap(True)
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
        self.view = PlanWidget()
        right.addWidget(self.view, 2)
        self.tabs = QTabWidget()
        self.t_x = self._table(STRIP_HEAD)
        self.t_y = self._table(STRIP_HEAD)
        self.t_p = self._table(PUNCH_HEAD)
        self.tabs.addTab(self.t_x, "โมเมนต์/เหล็ก แนว X")
        self.tabs.addTab(self.t_y, "โมเมนต์/เหล็ก แนว Y")
        self.tabs.addTab(self.t_p, "แรงเฉือนทะลุ (Punching)")
        right.addWidget(self.tabs, 3)
        lay.addLayout(right, 1)
        self.prm = prm
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
        p = dict(self.prm)
        p.update({k: w.value() / w.property("mul") for k, w in self.sp.items()})
        p.update(drop=self.drop.isChecked(), bar=self.bar.currentData(),
                 x=R.parse_spacings(self.ex.text()), y=R.parse_spacings(self.ey.text()))
        return p

    def use_min(self):
        try:
            p = self.params()
        except ValueError:
            return
        self.sp["t"].setValue(F.min_thickness(p)["need"] * 100)

    def recalc(self, *_):
        from core import wanic_calc as C
        try:
            prm = self.params()
        except ValueError as e:
            self.info.setText(f"✗ {e}")
            return
        self.sp["drop_t"].setEnabled(prm["drop"])
        self.res = F.design(prm, C.basis(self.data))
        self.view.set(prm, self.res)
        for t, rows, okcol in ((self.t_x, strip_rows(self.res["dirs"][0]), 10),
                               (self.t_y, strip_rows(self.res["dirs"][1]), 10),
                               (self.t_p, punch_rows(self.res), None)):
            t.setRowCount(len(rows))
            for r, row in enumerate(rows):
                for c, v in enumerate(row):
                    it = QTableWidgetItem(v)
                    if c == okcol:
                        it.setForeground(OK if v == "ผ่าน" else BAD)
                    if okcol is None and c == 6:
                        it.setForeground(OK if float(v) <= 1 else BAD)
                    t.setItem(r, c, it)
        self.info.setText(summary(prm, self.res))

    def export_pdf(self):
        from PySide6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getSaveFileName(self, "รายการคำนวณพื้นไร้คาน", "รายการคำนวณพื้นไร้คาน.pdf", "PDF (*.pdf)")
        if not path:
            return
        from core import wanic_calc as C
        from core.wanic_calc_book import Book
        b_ = C.basis(self.data)
        bk = Book(path, {k: b_.get(k, "") for k in ("project", "owner", "place", "engineer", "qualification")})
        flatslab_pages(bk, self.params(), self.res)
        bk.close()
        self.info.setText(self.info.text() + f"\nบันทึกแล้ว: {path}")


def flatslab_pages(bk, prm, res):
    from core.wanic_calc_book import GREEN, RED
    mm = bk.mm
    bk.page("พื้นไร้คาน Flat Slab (DDM)", "Flat Slab")
    bk.p.setRenderHint(QPainter.Antialiasing)
    draw_plan(bk.p, QRectF(10 * mm, 32 * mm, 200 * mm, 150 * mm), prm, res, 5.0 * mm)
    y = 36
    for ln in summary(prm, res).split("\n") + [
            "Mo = wu·l2·ln²/8 · ช่วงใน −0.65/+0.35 · ช่วงริม −0.26/+0.52/−0.70 (ไม่มีคานขอบ)",
            "แถบเสา: ลบใน 75% · บวก 60% · ลบนอก 100% — แถบกลางรับส่วนที่เหลือ",
            "เหล็กเสริม ≥ 0.0018bh · ระยะเรียง ≤ 2h และ ≤ 45 ซม."]:
        parts, cur = [], ""
        for word in ln.split(" "):
            if len(cur) + len(word) > 64 and cur:
                parts.append(cur)
                cur = "   "
            cur += word + " "
        parts.append(cur)
        for part in parts:
            bk.text(215, y, 180, 6.5, part, 5.4)
            y += 6.5
    y += 3
    rows = [tuple(PUNCH_HEAD)] + [r[:6] + ((r[6], GREEN if float(r[6]) <= 1 else RED),) for r in punch_rows(res)]
    bk.table(215, y, [20, 48, 16, 18, 26, 28, 22], rows, 6.5, left=True)
    widths = [14, 20, 24, 24, 28, 34, 24, 30, 46, 26, 20]
    for d in res["dirs"]:
        rows = strip_rows(d)
        for k in range(0, len(rows), 30):
            bk.page(f"พื้นไร้คาน — {d['name']}", "Flat Slab")
            bk.text(10, 32, 380, 7, f"กว้างแถบเสา {d['cs']:.2f} ม. · แถบกลาง {d['ms']:.2f} ม. · "
                    f"ความกว้างโครง l2 = {d['l2']:.2f} ม. · Mo = wu·l2·ln²/8", 5.6)
            body = [r[:10] + ((r[10], GREEN if r[10] == "ผ่าน" else RED),) for r in rows[k:k + 30]]
            bk.table(10, 41, widths, [tuple(STRIP_HEAD)] + body, 6.8, left=True)
