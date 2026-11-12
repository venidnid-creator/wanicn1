# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
"""ออกแบบ Truss — the window and the booklet pages: the truss drawn to
scale with its member numbers and forces (tension blue, compression red),
the member table, the chosen sizes, the base plate."""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (QComboBox, QDialog, QDoubleSpinBox, QFormLayout, QHBoxLayout, QHeaderView,
                               QLabel, QPushButton, QSpinBox, QTableWidget, QTableWidgetItem, QVBoxLayout,
                               QWidget)

from core import wanic_truss as T

TENSION = QColor("#1D4ED8")
COMPRESSION = QColor("#DC2626")
INK = QColor("#111827")
GROUP_TH = {"top": "จันทัน (คอร์ดบน)", "bottom": "ขื่อ (คอร์ดล่าง)", "web": "ค้ำยัน/ดั้ง (เว็บ)"}


def _font(px, bold=False):
    f = QFont()
    f.setFamilies(["TH Sarabun New", "TH SarabunPSK", "Laksaman", "Tahoma"])
    f.setPixelSize(max(1, int(px)))
    f.setBold(bold)
    return f


def draw_truss(p: QPainter, rect: QRectF, d: T.Design, px: float = 11.0, forces: bool = True):
    """The truss to scale in ``rect``; members coloured by the sign of the force."""
    t = d.truss
    xs = [n[0] for n in t.nodes]
    ys = [n[1] for n in t.nodes]
    w = max(xs) - min(xs) or 1.0
    h = max(ys) - min(ys) or 1.0
    pad = px * 3
    sc = min((rect.width() - 2 * pad) / w, (rect.height() - 2 * pad) / h)
    ox = rect.left() + (rect.width() - w * sc) / 2 - min(xs) * sc
    oy = rect.bottom() - pad - (rect.height() - 2 * pad - h * sc) / 2 + min(ys) * sc

    def P(i):
        x, y = t.nodes[i]
        return QPointF(ox + x * sc, oy - y * sc)

    lw = max(1.0, px / 5)
    F = d.result["force"]
    p.setFont(_font(px * 0.85))
    for k, (a, b, g) in enumerate(t.members):
        N = F[k]
        col = INK if abs(N) < 1e-6 else (TENSION if N > 0 else COMPRESSION)
        p.setPen(QPen(col, lw * (1.6 if g != "web" else 1.0)))
        p.drawLine(P(a), P(b))
    p.setPen(QPen(INK, lw))
    p.setBrush(QColor("#FFFFFF"))
    for i in range(len(t.nodes)):
        p.drawEllipse(P(i), lw * 1.6, lw * 1.6)
    # supports: triangles (pin) / triangle on a line (roller)
    for nd, kind in t.supports.items():
        c = P(nd)
        s = px * 0.9
        p.setBrush(Qt.NoBrush)
        p.drawLine(c, QPointF(c.x() - s, c.y() + s * 1.3))
        p.drawLine(c, QPointF(c.x() + s, c.y() + s * 1.3))
        p.drawLine(QPointF(c.x() - s, c.y() + s * 1.3), QPointF(c.x() + s, c.y() + s * 1.3))
        if kind == "roller":
            p.drawLine(QPointF(c.x() - s * 1.3, c.y() + s * 1.7), QPointF(c.x() + s * 1.3, c.y() + s * 1.7))
    if not forces:
        return
    # crowded trusses (short members on the drawing) show the member numbers only
    short = min(((P(a) - P(b)).manhattanLength() for a, b, _g in t.members), default=0)
    both = short > px * 3.5
    for k, (a, b, g) in enumerate(t.members):
        m = (P(a) + P(b)) / 2
        N = F[k]
        p.setPen(TENSION if N > 0 else COMPRESSION)
        r = QRectF(m.x() - px * 4, m.y() - px * (1.3 if both else 0.6), px * 8, px * 1.2)
        p.drawText(r, Qt.AlignCenter, f"{k + 1}")
        if both:
            p.drawText(r.translated(0, px * 1.15), Qt.AlignCenter, f"{N:+,.0f}")
    # the reactions
    p.setPen(INK)
    for nd, (rx, ry) in d.result["reactions"].items():
        c = P(nd)
        p.drawText(QRectF(c.x() - px * 6, c.y() + px * 2.2, px * 12, px * 1.3), Qt.AlignCenter,
                   f"R = {ry:,.0f} กก.")


class TrussWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.design = None
        self.setMinimumHeight(260)

    def set_design(self, d):
        self.design = d
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor("#FFFFFF"))
        if self.design is not None:
            draw_truss(p, QRectF(self.rect()), self.design, 12.0)
            p.setFont(_font(12))
            p.setPen(TENSION)
            p.drawText(QRectF(8, 4, 300, 18), Qt.AlignLeft, "+ แรงดึง (Tension)")
            p.setPen(COMPRESSION)
            p.drawText(QRectF(8, 22, 300, 18), Qt.AlignLeft, "− แรงอัด (Compression)")
        p.end()


def summary_lines(p: dict, d: T.Design) -> list:
    plate = d.plate
    lines = [f"แบบ {T.TYPES.get(p['kind'], p['kind'])} · ช่วง {p['span']:.2f} ม. · สูง {p['rise']:.2f} ม. · "
             f"ระยะห่างโครง {p['spacing']:.2f} ม.",
             f"น้ำหนักบรรทุกคงที่ {p['dead']:g} + จร {p['live']:g} กก./ตร.ม. (แนวราบ) → แรงที่จุดแป "
             f"รวม {-sum(f[1] for f in d.loads.values()):,.0f} กก./โครง (รวมน้ำหนักตัวเอง)"]
    for g in ("top", "bottom", "web"):
        if g in d.pick:
            rows = [r for r in d.rows if r[1] == g]
            if rows:
                worst = max(rows, key=lambda r: r[6])
                lines.append(f"{GROUP_TH[g]}: {T.FAMILY_TH[p['family']]} {d.pick[g].label} มม. — "
                             f"แรงสูงสุด {worst[3]:+,.0f} กก. / รับได้ {worst[4]:,.0f} กก. "
                             f"(อัตราส่วน {worst[6]:.2f}, KL/r {worst[5]:.0f})")
    if plate.get("weld"):
        lines.append("รอยเชื่อมส้นโครง (เชื่อมพอก E70 6 มม., {:,.0f} กก./ซม.): ".format(plate["weld_cap"])
                     + " · ".join(f"ชิ้น {no} ยาวรวม ≥ {L:.0f} ซม." for no, _g, _N, L in plate["weld"]))
    lines.append(f"น้ำหนักเหล็กต่อโครง {d.weight:,.1f} กก. (≈ {d.weight / (p['span'] * p['spacing']):.1f} "
                 f"กก./ตร.ม. หลังคา)")
    lines.append(f"แผ่นเหล็กรองฐาน (Base Plate): แรงปฏิกิริยา {plate['R']:,.0f} กก. → PL {plate['side']:.0f}×"
                 f"{plate['side']:.0f} ซม. หนา {plate['t']:.0f} มม. · หน่วยแรงแบกทาน {plate['f']:.1f} กก./ตร.ซม. "
                 f"· {plate['bolts']}")
    return lines


class TrussDialog(QDialog):
    """The building's truss: the form, the loads, the family — drawn and
    designed as it is typed; ``OK`` keeps it in data["truss"]."""

    def __init__(self, parent, data: dict):
        super().__init__(parent)
        self.setWindowTitle("ออกแบบ Truss (โครงถักหลังคาเหล็ก)")
        self.resize(1180, 760)
        self.data = data
        p = T.params_of(data)
        lay = QHBoxLayout(self)
        form = QFormLayout()
        self.kind = QComboBox()
        for k, v in T.TYPES.items():
            self.kind.addItem(v, k)
        self.custom = {k: p[k] for k in ("nodes", "members", "supports") if p.get(k)}
        self.kind.setCurrentIndex(max(0, self.kind.findData(p["kind"])))
        form.addRow("รูปแบบ Truss", self.kind)
        self.sp = {}
        for key, th, lo, hi, dec in (("span", "ช่วงคาน (ม.)", 2, 60, 2), ("rise", "ความสูงกลางช่วง (ม.)", 0.2, 15, 2),
                                     ("depth", "ความลึกโครง (โค้ง/ขนาน) (ม.)", 0.2, 3, 2),
                                     ("radius", "รัศมีโค้ง R (ม.) 0 = จากความสูง", 0, 200, 2),
                                     ("spacing", "ระยะห่างโครง Truss (ม.)", 1, 12, 2),
                                     ("dead", "น้ำหนักคงที่ (กก./ตร.ม.)", 0, 300, 1),
                                     ("live", "น้ำหนักจร (กก./ตร.ม.)", 0, 300, 1)):
            s = QDoubleSpinBox()
            s.setRange(lo, hi)
            s.setDecimals(dec)
            s.setValue(float(p[key]))
            s.valueChanged.connect(self.recalc)
            self.sp[key] = s
            form.addRow(th, s)
        self.panels = QSpinBox()
        self.panels.setRange(2, 40)
        self.panels.setSingleStep(2)
        self.panels.setValue(int(p["panels"]))
        self.panels.valueChanged.connect(self.recalc)
        form.addRow("จำนวนช่อง (แป)", self.panels)
        self.family = QComboBox()
        for k, v in T.FAMILY_TH.items():
            self.family.addItem(v, k)
        self.family.setCurrentIndex(max(0, self.family.findData(p["family"])))
        form.addRow("หน้าตัดเหล็ก", self.family)
        self.kind.currentIndexChanged.connect(self.recalc)
        self.family.currentIndexChanged.connect(self.recalc)
        left = QVBoxLayout()
        left.addLayout(form)
        from PySide6.QtWidgets import QTextEdit
        self.info = QTextEdit()
        self.info.setReadOnly(True)
        self.info.setMinimumWidth(340)
        left.addWidget(self.info, 1)
        btns = QHBoxLayout()
        self.pdf_btn = QPushButton("รายการคำนวณ Truss (.pdf)")
        self.pdf_btn.clicked.connect(self.export_pdf)
        btns.addWidget(self.pdf_btn)
        self.edit_btn = QPushButton("แก้จุดต่อ/ชิ้นส่วน…")
        self.edit_btn.setToolTip("เขียน Truss เอง: เริ่มจากรูปที่เห็นอยู่ แล้วเพิ่ม/ลบ/ย้ายจุดต่อและชิ้นส่วน")
        self.edit_btn.clicked.connect(self.edit_custom)
        btns.addWidget(self.edit_btn)
        ok = QPushButton("บันทึก")
        ok.setStyleSheet("font-weight: 700;")
        ok.clicked.connect(self.accept)
        btns.addWidget(ok)
        cancel = QPushButton("ยกเลิก")
        cancel.clicked.connect(self.reject)
        btns.addWidget(cancel)
        left.addLayout(btns)
        lay.addLayout(left)
        right = QVBoxLayout()
        self.view = TrussWidget()
        right.addWidget(self.view, 3)
        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(["ชิ้น", "กลุ่ม", "ขนาด", "ยาว (ม.)", "แรง (กก.)", "รับได้ (กก.)",
                                              "KL/r", "อัตราส่วน"])
        self.table.verticalHeader().hide()
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        right.addWidget(self.table, 2)
        lay.addLayout(right, 1)
        self.d = None
        self.recalc()

    def params(self) -> dict:
        p = {k: s.value() for k, s in self.sp.items()}
        p.update(kind=self.kind.currentData(), panels=self.panels.value(), family=self.family.currentData())
        if p["kind"] == "custom":
            p.update(self.custom)
        return p

    def edit_custom(self):
        cur = self.d.truss if self.d is not None else T.make("howe", 12, 2, 6)
        base = self.custom if self.custom.get("nodes") else {
            "nodes": [list(n) for n in cur.nodes], "members": [list(m) for m in cur.members],
            "supports": {str(k): v for k, v in cur.supports.items()}}
        dlg = CustomTrussDialog(self, base)
        if dlg.exec() != QDialog.Accepted:
            return
        self.custom = dlg.result_data()
        self.kind.blockSignals(True)
        self.kind.setCurrentIndex(self.kind.findData("custom"))
        self.kind.blockSignals(False)
        self.recalc()

    def recalc(self, *_):
        p = self.params()
        own = p["kind"] == "custom"
        for k in ("span", "rise", "depth", "radius"):            # the user's own nodes set the form
            self.sp[k].setEnabled(not own)
        self.panels.setEnabled(not own)
        try:
            if p["kind"] == "custom" and not p.get("nodes"):
                raise ValueError("Truss เขียนเอง: กด «แก้จุดต่อ/ชิ้นส่วน…» เพื่อกำหนดจุดต่อและชิ้นส่วน")
            t = T.build(p)
            if p["kind"] == "custom":
                xs = [n[0] for n in t.nodes]
                p["span"] = max(xs) - min(xs)
                p["rise"] = max(n[1] for n in t.nodes) - min(n[1] for n in t.nodes)
                for k in ("span", "rise"):
                    self.sp[k].blockSignals(True)
                    self.sp[k].setValue(p[k])
                    self.sp[k].blockSignals(False)
            self.d = T.design(t, p["span"], p["spacing"], p["dead"], p["live"], p["family"])
        except ValueError as e:
            self.d = None
            self.info.setPlainText(str(e))
            self.view.set_design(None)
            return
        self.view.set_design(self.d)
        lines = summary_lines(p, self.d)
        bad = [r for r in self.d.rows if r[6] > 1.0]
        lines.append(f"✗ มี {len(bad)} ชิ้นเกินกำลัง — เพิ่มจำนวนช่องหรือเลือกหน้าตัดอื่น" if bad
                     else "✓ ทุกชิ้นผ่าน (ASD: ดึง 0.60Fy · อัด Fa จาก KL/r, Cc)")
        self.info.setPlainText("\n\n".join(lines))
        self.table.setRowCount(len(self.d.rows))
        for r, (no, g, L, N, cap, klr, ratio) in enumerate(self.d.rows):
            vals = (str(no), GROUP_TH[g], self.d.pick[g].label, f"{L:.2f}", f"{N:+,.0f}", f"{cap:,.0f}",
                    f"{klr:.0f}", f"{ratio:.2f}")
            for c, v in enumerate(vals):
                it = QTableWidgetItem(v)
                if c == 4:
                    it.setForeground(TENSION if N > 0 else COMPRESSION)
                if c == 7:
                    it.setForeground(QColor("#15803D") if ratio <= 1 else QColor("#B91C1C"))
                self.table.setItem(r, c, it)

    def export_pdf(self):
        from PySide6.QtWidgets import QFileDialog
        if self.d is None:
            return
        path, _ = QFileDialog.getSaveFileName(self, "รายการคำนวณ Truss", "รายการคำนวณ Truss.pdf", "PDF (*.pdf)")
        if not path:
            return
        from core import wanic_calc as C
        from core.wanic_calc_book import Book
        b_ = C.basis(self.data)
        bk = Book(path, {k: b_.get(k, "") for k in ("project", "owner", "place", "engineer", "qualification")})
        truss_pages(bk, self.params(), self.d)
        bk.close()
        self.info.append(f"\nบันทึกแล้ว: {path}")


def truss_pages(bk, p: dict, d: T.Design):
    """The booklet pages of the truss: the drawing with the forces and the
    data, then the member table."""
    from core.wanic_calc_book import GREEN, RED
    mm = bk.mm
    bk.page("โครงหลังคา Truss", "Truss")
    bk.p.setRenderHint(QPainter.Antialiasing)
    draw_truss(bk.p, QRectF(10 * mm, 32 * mm, 384 * mm, 140 * mm), d, 5.5 * mm)
    y = 176
    for ln in summary_lines(p, d):
        bk.text(12, y, 380, 7, ln, 6.0)
        y += 7.5
    bk.text(12, y + 1, 380, 7, "+ แรงดึง (สีน้ำเงิน)   − แรงอัด (สีแดง)   วิเคราะห์ด้วยวิธี Matrix Stiffness "
            "(โครงข้อหมุน 2 มิติ) · ออกแบบหน่วยแรงที่ยอมให้ (ASD) Fy = 2,450 กก./ตร.ซม.", 5.2)
    head = ("ชิ้น", "กลุ่ม", "ขนาด (มม.)", "ยาว (ม.)", "แรง (กก.)", "Fa·A / 0.6Fy·A (กก.)", "KL/r", "อัตราส่วน", "ผล")
    rows = [(str(no), GROUP_TH[g], d.pick[g].label, f"{L:.2f}", f"{N:+,.0f}", f"{cap:,.0f}", f"{klr:.0f}",
             f"{ratio:.2f}", ("ผ่าน", GREEN) if ratio <= 1 else ("ไม่ผ่าน", RED))
            for no, g, L, N, cap, klr, ratio in d.rows]
    widths = [16, 70, 60, 30, 40, 70, 25, 30, 25]
    per = 30
    for k in range(0, len(rows), per):
        bk.page("โครงหลังคา Truss — แรงในชิ้นส่วน", "Truss")
        bk.table(10, 34, widths, [head] + rows[k:k + per], 7.0)


GROUP_KEYS = ("top", "bottom", "web")


class CustomTrussDialog(QDialog):
    """Truss เขียนเอง: two tables — the nodes (x, y, support) and the
    members (from, to, group); nodes are numbered from 1 on screen."""

    def __init__(self, parent, base: dict):
        super().__init__(parent)
        self.setWindowTitle("Truss เขียนเอง — จุดต่อและชิ้นส่วน")
        self.resize(900, 620)
        lay = QVBoxLayout(self)
        row = QHBoxLayout()
        sup = {int(k): v for k, v in (base.get("supports") or {}).items()}
        self.nodes = QTableWidget(len(base["nodes"]), 3)
        self.nodes.setHorizontalHeaderLabels(["x (ม.)", "y (ม.)", "จุดรองรับ (pin/roller)"])
        for i, (x, y) in enumerate(base["nodes"]):
            for c, v in enumerate((f"{x:.3f}", f"{y:.3f}", sup.get(i, ""))):
                self.nodes.setItem(i, c, QTableWidgetItem(v))
        self.members = QTableWidget(len(base["members"]), 3)
        self.members.setHorizontalHeaderLabels(["จากจุด", "ถึงจุด", "กลุ่ม (top/bottom/web)"])
        for i, (a, b, g) in enumerate(base["members"]):
            for c, v in enumerate((str(a + 1), str(b + 1), g)):
                self.members.setItem(i, c, QTableWidgetItem(v))
        for tb, th in ((self.nodes, "จุดต่อ"), (self.members, "ชิ้นส่วน")):
            box = QVBoxLayout()
            box.addWidget(QLabel(th))
            tb.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
            box.addWidget(tb)
            b = QHBoxLayout()
            add = QPushButton("+ เพิ่มแถว")
            add.clicked.connect(lambda _=False, t=tb: t.insertRow(t.rowCount()))
            rem = QPushButton("− ลบแถวที่เลือก")
            rem.clicked.connect(lambda _=False, t=tb: t.removeRow(t.currentRow()) if t.currentRow() >= 0 else None)
            b.addWidget(add)
            b.addWidget(rem)
            box.addLayout(b)
            row.addLayout(box)
        lay.addLayout(row)
        self.msg = QLabel("ลำดับจุดต่อเริ่มที่ 1 · กลุ่ม top = จันทัน (รับแป), bottom = ขื่อ, web = ค้ำยัน/ดั้ง · "
                          "ต้องมี pin อย่างน้อย 1 จุดและ roller/pin อีก 1 จุด")
        self.msg.setWordWrap(True)
        lay.addWidget(self.msg)
        b = QHBoxLayout()
        b.addStretch(1)
        ok = QPushButton("ตกลง")
        ok.clicked.connect(self._ok)
        cancel = QPushButton("ยกเลิก")
        cancel.clicked.connect(self.reject)
        b.addWidget(ok)
        b.addWidget(cancel)
        lay.addLayout(b)
        self._data = None

    @staticmethod
    def _cell(tb, r, c):
        it = tb.item(r, c)
        return (it.text() if it else "").strip()

    def _ok(self):
        try:
            nodes, sup = [], {}
            for r in range(self.nodes.rowCount()):
                x, y = self._cell(self.nodes, r, 0), self._cell(self.nodes, r, 1)
                if not x and not y:
                    continue
                nodes.append([float(x), float(y)])
                s = self._cell(self.nodes, r, 2).lower()
                if s in ("pin", "roller"):
                    sup[str(len(nodes) - 1)] = s
            mem = []
            for r in range(self.members.rowCount()):
                a, b = self._cell(self.members, r, 0), self._cell(self.members, r, 1)
                if not a or not b:
                    continue
                g = self._cell(self.members, r, 2).lower() or "web"
                a, b = int(a) - 1, int(b) - 1
                if g not in GROUP_KEYS or not (0 <= a < len(nodes) and 0 <= b < len(nodes)) or a == b:
                    raise ValueError(f"ชิ้นส่วนแถว {r + 1} ไม่ถูกต้อง")
                mem.append([a, b, g])
            t = T.custom([tuple(n) for n in nodes], [tuple(m) for m in mem], {int(k): v for k, v in sup.items()})
            T.solve(t, {i: (0.0, -1.0) for i in t.top} or {0: (0.0, -1.0)})
        except ValueError as e:
            self.msg.setText(f"✗ {e}")
            return
        self._data = {"nodes": nodes, "members": mem, "supports": sup}
        self.accept()

    def result_data(self) -> dict:
        return self._data
