# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
"""รูปเล่มรายการคำนวณโครงสร้าง: the calculation booklet on A4 landscape
sheets, the way Thai engineers hand it in with a permit:

1. a cover (project, owner, place),
2. the design basis (materials, allowable stresses, live loads by use,
   wind by height and terrain, the strength-reduction factors),
3. a page per beam line: its load, shear and moment diagrams and a table
   per span (moments at the ends and mid-span, the capacity, the steel
   needed and used, where the moment changes sign, the shear at d from
   the support, Vc, the stirrups and Vs),
4. the columns as cards floor by floor (load, bars, ties, Pg, capacity),
5. the footings, the roof members and the summary,

each page framed, titled, numbered and signed by the person who made it."""
from __future__ import annotations

import math

from PySide6.QtCore import QMarginsF, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPageLayout, QPageSize, QPainter, QPdfWriter, QPen, QPolygonF

from core import wanic_calc as C
from core import wanic_rc as R

BLUE = QColor("#1D4ED8")
RED = QColor("#DC2626")
GREEN = QColor("#16A34A")
ORANGE = QColor("#B45309")
INK = QColor("#111827")

#: Steel's allowable tensile stress in WSD (ksc), by bar.
FS = {"RB": 1200.0, "DB": 1700.0}


def _font(px, bold=False):
    f = QFont()
    f.setFamilies(["TH Sarabun New", "TH SarabunPSK", "Laksaman", "Tahoma"])
    f.setPixelSize(int(px))
    f.setBold(bold)
    return f


class Book:
    """Pages on an A4 landscape PDF. The layout is drawn in the units of a
    404 mm wide sheet and scales to the paper (``mm`` = page width / 404)."""

    def __init__(self, path, info: dict):
        self.w = QPdfWriter(str(path))
        self.w.setResolution(200)
        self.w.setPageLayout(QPageLayout(QPageSize(QPageSize.A4), QPageLayout.Landscape,
                                         QMarginsF(6, 6, 6, 6), QPageLayout.Millimeter))
        self.p = QPainter(self.w)
        self.W, self.H = self.w.width(), self.w.height()
        self.mm = self.W / 404.0
        self.info = info
        self.first = True
        self.n = 0

    def page(self, title: str, tag: str):
        if not self.first:
            self.w.newPage()
        self.first = False
        self.n += 1
        p, mm = self.p, self.mm
        p.setPen(QPen(INK, 2))
        p.setBrush(Qt.NoBrush)
        p.drawRect(QRectF(0, 0, self.W, self.H))
        p.setFont(_font(9 * mm))
        p.drawText(QRectF(14 * mm, 6 * mm, 260 * mm, 12 * mm), Qt.AlignLeft | Qt.AlignVCenter,
                   f"Project : {self.info.get('project', '')}")
        p.drawText(QRectF(8 * mm, 17 * mm, 300 * mm, 12 * mm), Qt.AlignLeft | Qt.AlignVCenter,
                   f"รายการคำนวณ : {title}")
        p.drawText(QRectF(self.W - 130 * mm, 6 * mm, 122 * mm, 12 * mm), Qt.AlignRight | Qt.AlignVCenter,
                   f"Page : {tag}  ({self.n})")
        self.sign()

    def sign(self):
        p, mm = self.p, self.mm
        p.setFont(_font(8 * mm))
        p.setPen(INK)
        who = self.info.get("engineer", "")
        qual = self.info.get("qualification", "")
        p.drawText(QRectF(self.W - 120 * mm, self.H - 34 * mm, 110 * mm, 12 * mm), Qt.AlignLeft, who)
        p.drawText(QRectF(self.W - 120 * mm, self.H - 22 * mm, 110 * mm, 12 * mm), Qt.AlignLeft, qual)

    def text(self, x, y, w, h, t, px=6.0, color=INK, align=Qt.AlignLeft | Qt.AlignVCenter, bold=False):
        mm = self.mm
        self.p.setFont(_font(px * mm, bold))
        self.p.setPen(color)
        self.p.drawText(QRectF(x * mm, y * mm, w * mm, h * mm), int(align), t)

    def table(self, x, y, widths, rows, h=7.0, left=False):
        """Rows of cells (mm); a cell may be (text, QColor)."""
        mm, p = self.mm, self.p
        for r, row in enumerate(rows):
            cx = x
            for c, (wd, cell) in enumerate(zip(widths, row)):
                col = INK
                if isinstance(cell, tuple):
                    cell, col = cell
                p.setPen(QPen(INK, 1))
                p.drawRect(QRectF(cx * mm, (y + r * h) * mm, wd * mm, h * mm))
                self.text(cx + 1, y + r * h, wd - 2, h, str(cell), 5.2, col,
                          Qt.AlignRight | Qt.AlignVCenter if (c and not left) else Qt.AlignLeft | Qt.AlignVCenter)
                cx += wd
        return y + len(rows) * h

    def close(self):
        self.p.end()


# ---- the pages ---------------------------------------------------------------------------

def cover(bk: Book):
    bk.page("", "cover")
    mm, p = bk.mm, bk.p
    p.setPen(QPen(BLUE, 2))
    for x0, x1, xc in ((30, 150, 32), (260, 380, 378)):
        p.drawLine(QPointF(x0 * mm, 45 * mm), QPointF(x1 * mm, 45 * mm))
        p.drawLine(QPointF(xc * mm, 35 * mm), QPointF(xc * mm, 75 * mm))
        p.drawEllipse(QPointF(xc * mm, 45 * mm), 2.5 * mm, 2.5 * mm)
    bk.text(0, 60, 404, 30, "รายการคำนวณโครงสร้าง", 22, align=Qt.AlignCenter)
    i = bk.info
    for k, (lab, val) in enumerate((("โครงการ", i.get("project", "")), ("เจ้าของ", i.get("owner", "")),
                                    ("สถานที่", i.get("place", "")))):
        bk.text(70, 100 + k * 24, 330, 20, f"{lab} :  {val}", 16)
    bk.text(200, 255, 196, 12, "คำนวณโครงสร้างโดย WANICNSURVEY", 9, align=Qt.AlignRight | Qt.AlignVCenter)


def basis_page(bk: Book, b_: dict):
    bk.page("ข้อกำหนดในการออกแบบ", "Design")
    sdm = b_["method"] == "SDM"
    fc = b_["fc"]
    n = 2.04e6 / (15100 * math.sqrt(fc))
    rows = [("ข้อกำหนดในการออกแบบ", ""),
            ("วิธีออกแบบ", "กำลัง (SDM) วสท. 011008" if sdm else "หน่วยแรงใช้งาน (WSD) ข้อบัญญัติ กทม. 2522"),
            ("fc′ คอนกรีต", f"{fc:,.2f} ksc"), ("fc = 0.375 fc′ (WSD)", f"{0.375 * fc:,.2f} ksc"),
            ("ตัวคูณน้ำหนักคงที่ / น้ำหนักจร", "1.40 / 1.70" if sdm else "1.00 / 1.00")]
    for name, fy in (("SR24", 2400.0), ("SD30", 3000.0), ("SD40", 4000.0)):
        fs = 1200.0 if name == "SR24" else (1500.0 if name == "SD30" else 1700.0)
        k = 1 / (1 + fs / (n * 0.375 * fc))
        j = 1 - k / 3
        Rr = 0.5 * 0.375 * fc * k * j
        used = (name == "SR24") or abs(fy - float(b_.get("fy_db", 4000.0))) < 1
        rows.append((f"เหล็กเสริม {name}" + (" ✓ ใช้" if used else ""),
                     f"fy {fy:,.0f} · fs {fs:,.0f} ksc · n {n:.0f} · k {k:.2f} · j {j:.2f} · R {Rr:.2f} ksc"))
    rows += [("หน่วยแรงเฉือนคอนกรีต (ไม่มีเหล็กลูกตั้ง)", f"{0.29 * math.sqrt(fc):.2f} ksc"),
             ("หน่วยแรงเฉือนคอนกรีต (มีเหล็กลูกตั้ง)", f"{1.32 * math.sqrt(fc):.2f} ksc"),
             ("แผ่นพื้น ฐานราก (เฉือนทะลุ)", f"{0.53 * math.sqrt(fc):.2f} ksc"),
             ("น้ำหนักบรรทุกจรที่ใช้", f"{b_['ll_floor']:g} กก./ตร.ม."),
             ("วัสดุปูพื้น + ฝ้า", f"{b_['finish']:g} กก./ตร.ม."),
             ("น้ำหนักบรรทุกจรหลังคา", f"{b_['ll_roof']:g} กก./ตร.ม."),
             ("ดินรับน้ำหนักปลอดภัย / เสาเข็ม", f"{b_['soil']:g} ตัน/ตร.ม. · {b_['pile_cap']:g} ตัน/ต้น")]
    y = bk.table(14, 34, [110, 150], rows, 8.2)
    right = [("น้ำหนักบรรทุกจรสำหรับการออกแบบ (กฎกระทรวง)", ""),
             ("ที่พักอาศัย ห้องน้ำ", "200 กก./ตร.ม."), ("อาคารชุด หอพัก โรงแรม", "200 กก./ตร.ม."),
             ("สำนักงาน ธนาคาร", "250 กก./ตร.ม."), ("อาคารพาณิชย์ โรงเรียน", "400 กก./ตร.ม."),
             ("คลังสินค้า โรงงาน", "500 กก./ตร.ม."), ("หลังคา", "50 กก./ตร.ม."),
             ("น้ำหนักคอนกรีต", f"{b_['concrete']:,.0f} กก./ลบ.ม."),
             ("ผนังก่ออิฐมอญ อิฐบล็อก", "180 กก./ตร.ม."), ("ผนังอิฐมวลเบา", "90 กก./ตร.ม."),
             ("ผนังยิปซัม โครงไม้", "25 กก./ตร.ม."),
             ("แรงลม เมือง/ชานเมือง สูงไม่เกิน 10 / 10–20 / 20–40 ม.", "60 / 80 / 120 กก./ตร.ม."),
             ("แรงลม โล่งหรือชายฝั่งทะเล สูงไม่เกิน 10 / 10–20 / 20–40 ม.", "100 / 120 / 160 กก./ตร.ม."),
             ("ค่าสัมประสิทธิ์ลดกำลัง φ (SDM)", "ดัด 0.90 · เฉือน 0.85 · เสาปลอกเกลียว 0.75 · เสาปลอกเดี่ยว 0.70")]
    bk.table(285, 34, [70, 45], right, 8.2)
    bk.text(14, y + 6, 380, 10, "เอกสารนี้ต้องให้วิศวกรโยธาผู้มีใบอนุญาตตรวจสอบและลงนามรับรองก่อนก่อสร้าง", 7, RED)


def _span_rows(res, i, b_, fc):
    """The table of one span: moments, steel, shear, stirrups."""
    spec = res.spec
    sp = res.spans[i]
    n = 24
    xs = res.xs[i * (n + 1):(i + 1) * (n + 1)]
    V = res.V[i * (n + 1):(i + 1) * (n + 1)]
    M = res.M[i * (n + 1):(i + 1) * (n + 1)]
    bw, h = float(spec.get("b", 0.2)), float(spec.get("h", 0.4))
    d = h - R.COVER["beam"] - 0.012
    x0 = xs[0]
    ML, MR = max(0.0, -M[0]), max(0.0, -M[-1])
    Mm = max(M)
    sdm = b_["method"] == "SDM"
    top, bot, st = R.parse_bar(spec.get("top")), R.parse_bar(spec.get("bot")), R.parse_bar(spec.get("stir"))

    def need(Mx, bar):
        if Mx <= 0:
            return 0.0
        fy = C.fy_of(bar, b_)
        if sdm:
            Rn = Mx * 100 / (0.9 * bw * 100 * (d * 100) ** 2)
            disc = 1 - 2 * Rn / (0.85 * fc)
            rho = 0.85 * fc / fy * (1 - math.sqrt(max(disc, 0.0)))
            return rho * bw * 100 * d * 100
        fs = C.fs_of(bar, b_)
        return Mx * 100 / (fs * 0.88 * d * 100)
    if sdm:
        rho_b = 0.85 * 0.85 * fc / 4000 * 6120 / (6120 + 4000)
        Mc = 0.9 * 0.75 * rho_b * 4000 * (1 - 0.59 * 0.75 * rho_b * 4000 / fc) * bw * 100 * (d * 100) ** 2 / 100
    else:
        n_ = 2.04e6 / (15100 * math.sqrt(fc))
        k = 1 / (1 + 1700 / (n_ * 0.375 * fc))
        Mc = 0.5 * 0.375 * fc * k * (1 - k / 3) * bw * 100 * (d * 100) ** 2 / 100
    # where the moment changes sign, measured from each end
    zl = next((xs[j] - x0 for j in range(1, len(M)) if M[j - 1] < -1.0 <= M[j] + 1.0 and M[j] >= 0), 0.0)
    zr = next((xs[-1] - xs[j] for j in range(len(M) - 1, 0, -1) if M[j] < -1.0 and M[j - 1] >= 0), 0.0)
    RL, RR = V[0], -V[-1]
    Rd_l = max(RL - sp.w * d, 0.0)
    Rd_r = max(RR - sp.w * d, 0.0)
    Rd_m = abs(V[len(V) // 2])
    vc = (0.53 * 0.85 if sdm else 0.29) * math.sqrt(fc) * bw * 100 * d * 100
    vs = 0.0
    if st and st.s:
        vs = 2 * st.area * (C.fy_of(st, b_) * 0.85 if sdm else C.fs_of(st, b_)) * d * 100 / (st.s * 100)
    nt = top.n if top else 0
    nb = bot.n if bot else 0
    ast_used = nt * (top.area if top else 0)
    asb_used = nb * (bot.area if bot else 0)
    f2 = lambda v: f"{v:,.2f}"                       # noqa: E731
    head = [("NO.", "กว้าง(ซม.)", "ลึก(ซม.)", "ยาว(ม.)", "span(ม.)", "ระดับ"),
            ((res.mark, BLUE), (f"{bw * 100:.0f}", BLUE), (f"{h * 100:.0f}", BLUE), f2(sp.L),
             f2(max(sp.L - 0.2, 0.0)), f"{res.z:+.2f}")]
    me = float(getattr(res, "me", 0.0) or 0.0)
    body = [("Moment", "", "L", "M", "R"),
            ("Moment", "kg-m", f"{ML:,.1f}", f"{Mm:,.1f}", f"{MR:,.1f}"),
            ("Me (EQ/ลม)", "kg-m", f"{me:,.1f}", "0", f"{me:,.1f}"),
            ("Mc", "kg-m", f2(Mc), f2(Mc), f2(Mc)),
            ("Ast", "cm²", f2(need(ML, top)), "0.00", f2(need(MR, top))),
            ("Asb", "cm²", "0.00", f2(need(Mm, bot)), "0.00"),
            ("เหล็กบน", (f"{top.kind}{top.d}" if top else "-", BLUE), (str(nt), BLUE), (str(nt), BLUE),
             (str(nt), BLUE)),
            ("เหล็กล่าง", (f"{bot.kind}{bot.d}" if bot else "-", BLUE), (str(nb), BLUE), (str(nb), BLUE),
             (str(nb), BLUE)),
            ("Ast (used)", "cm²", f2(ast_used), f2(ast_used), f2(ast_used)),
            ("Asb (used)", "cm²", f2(asb_used), f2(asb_used), f2(asb_used)),
            ("ระยะ M0", "m.", f2(zl), "", f2(zr)),
            ("Shear", "", "L", "M", "R"),
            ("R", "kg", f2(RL), "", f2(RR)),
            ("Rd", "kg", f2(Rd_l), f2(Rd_m), f2(Rd_r)),
            ("Vc", "kg", f2(vc), f2(vc), f2(vc)),
            ("Rd−Vc", "kg", f2(max(Rd_l - vc, 0)), f2(max(Rd_m - vc, 0)), f2(max(Rd_r - vc, 0))),
            ("เหล็กปลอก@", (f"{st.kind}{st.d}" if st else "-", BLUE), (f"{st.s:.2f}" if st else "-", BLUE),
             (f"{st.s:.2f}" if st else "-", BLUE), (f"{st.s:.2f}" if st else "-", BLUE)),
            ("Vs", "kg", f2(vs), f2(vs), f2(vs))]
    ok = max(ML, MR) <= Mc and Mm <= Mc and need(max(ML, MR), top) <= ast_used + 1e-6 and \
        need(Mm, bot) <= asb_used + 1e-6 and max(Rd_l, Rd_r) <= vc + vs
    return head, body, ok


def _diagram_strip(bk: Book, y, res, kind):
    """One strip (load / shear / moment) across the page, values labelled."""
    mm, p = bk.mm, bk.p
    left, right = 120 * mm, 330 * mm
    L = res.xs[-1] or 1.0

    def X(x):
        return left + (right - left) * x / L
    base = y * mm
    p.setPen(QPen(INK, 1))
    if kind == "load":
        x = 0.0
        for sp in res.spans:
            p.fillRect(QRectF(X(x), base - 1.5 * mm, X(x + sp.L) - X(x), 3 * mm), GREEN)
            bk.text((X(x) / mm), y - 9, (X(x + sp.L) - X(x)) / mm, 6, f"W={sp.w:,.1f} kg/m", 5,
                    align=Qt.AlignCenter)
            bk.text((X(x) / mm), y + 2, (X(x + sp.L) - X(x)) / mm, 6, f"L= {sp.L:.2f} m.", 5,
                    align=Qt.AlignCenter)
            x += sp.L
        x = 0.0
        for k in range(len(res.spans) + 1):
            cx = X(x)
            p.setBrush(Qt.NoBrush)
            p.drawPolygon(QPolygonF([QPointF(cx, base + 1.5 * mm), QPointF(cx - 1.5 * mm, base + 4 * mm),
                                     QPointF(cx + 1.5 * mm, base + 4 * mm)]))
            if k < len(res.spans):
                x += res.spans[k].L
        return
    vals = res.V if kind == "shear" else res.M
    caps = getattr(res, "caps", None) or {}
    lines = []
    if kind == "shear" and "V" in caps:
        lines = [(caps["V"], GREEN, Qt.DashLine, caps.get("lab_V", "φVn")), (-caps["V"], GREEN, Qt.DashLine, ""),
                 (caps.get("Vc", 0), ORANGE, Qt.DotLine, caps.get("lab_Vc", "φVc")),
                 (-caps.get("Vc", 0), ORANGE, Qt.DotLine, "")]
    elif kind == "moment" and "M+" in caps:
        lines = [(caps["M+"], GREEN, Qt.DashLine, f"{caps.get('lab_M', 'φMn')} ล่าง"),
                 (-caps["M-"], GREEN, Qt.DashLine, f"{caps.get('lab_M', 'φMn')} บน")]
    big = max([abs(v) for v in vals] + [abs(c) for c, *_r in lines if c] + [1.0])
    sc = 9 * mm / big
    sgn = -1 if kind == "shear" else 1
    p.drawLine(QPointF(left, base), QPointF(right, base))
    pts = [QPointF(X(x), base + sgn * v * sc) for x, v in zip(res.xs, vals)]
    fillc = QColor(BLUE if kind == "shear" else RED)
    fillc.setAlpha(40)
    p.setPen(Qt.NoPen)
    p.setBrush(fillc)
    p.drawPolygon(QPolygonF([QPointF(X(res.xs[0]), base)] + pts + [QPointF(X(res.xs[-1]), base)]))
    p.setBrush(Qt.NoBrush)
    for c, col, style, lab in lines:
        if not c:
            continue
        yy = base + sgn * c * sc
        p.setPen(QPen(col, 1.0, style))
        p.drawLine(QPointF(left, yy), QPointF(right, yy))
        if lab:
            below = col is ORANGE or "ล่าง" in lab
            bk.text(right / mm + 1, yy / mm + (0.3 if below else -5.6), 62, 5.4, f"{lab} = {abs(c):,.0f}", 4.4, col)
    p.setPen(QPen(INK, 1.4))
    p.drawPolyline(QPolygonF(pts))
    n = 24
    for i in range(len(res.spans)):
        seg = list(range(i * (n + 1), (i + 1) * (n + 1)))
        if kind == "shear":
            for j, lab in ((seg[0], "R"), (seg[-1], "R")):
                bk.text(pts[j].x() / mm - 12, pts[j].y() / mm - 7 * (1 if vals[j] > 0 else -0.2), 24, 6,
                        f"R={abs(vals[j]):,.2f}", 4.6, align=Qt.AlignCenter)
        else:
            jm = max(seg, key=lambda j: vals[j])
            if vals[jm] > 1e-6:
                bk.text(pts[jm].x() / mm - 15, pts[jm].y() / mm + 1, 30, 6, f"M+={vals[jm]:,.1f}", 4.6,
                        align=Qt.AlignCenter)
            for j in (seg[0], seg[-1]):
                if vals[j] < -1e-6:
                    bk.text(pts[j].x() / mm - 15, pts[j].y() / mm - 7, 30, 6, f"M−={vals[j]:,.1f}", 4.6,
                            align=Qt.AlignCenter)


def beam_pages(bk: Book, res_all, b_, fc):
    k = 0
    for m in res_all["members"]:
        res = m.diagram
        if m.group != "beam" or res is None or not hasattr(res, "spec"):
            continue
        k += 1
        lvl = "ดิน (คานคอดิน)" if res.ground else f"{res.level}"
        bk.page(f"คาน   ชั้น {lvl}", f"Beam{k}")
        bk.text(40, 40, 70, 7, "Load Diagram", 6.5)
        bk.text(40, 47, 70, 7, f"GridLine {'y' if res.axis == 'x' else 'x'} = {res.line:.2f}", 6.5)
        _diagram_strip(bk, 46, res, "load")
        bk.text(40, 75, 70, 7, "Shear Diagram", 6.5)
        _diagram_strip(bk, 80, res, "shear")
        bk.text(40, 108, 70, 7, "Moment Diagram", 6.5)
        bk.text(40, 120, 80, 6, "(โมเมนต์บวกเขียนด้านล่าง = ด้านรับแรงดึง)", 4.4)
        bk.text(120, 128, 210, 6, "เส้นประเขียว = กำลังที่หน้าตัดรับได้ (φMn / φVn) · เส้นจุดส้ม = φVc คอนกรีต · "
                "แผนภาพต้องอยู่ภายในเส้นกำลัง", 4.6, GREEN)
        _diagram_strip(bk, 112, res, "moment")
        x = 12
        for i in range(len(res.spans)):
            head, body, ok = _span_rows(res, i, b_, fc)
            if x + 125 > 290:
                break
            y = bk.table(x, 135, [20, 20, 20, 18, 20, 22], head, 7.5)
            bk.table(x, y + 3, [29, 19, 25, 25, 25], body, 6.6)
            bk.text(x, y + 3 + len(body) * 6.6 + 1, 120, 6, "OK" if ok else "ตรวจสอบ — เพิ่มเหล็ก/ขนาดคาน", 5.5,
                    GREEN if ok else RED)
            x += 128
        if len(res.spans) > 2:
            bk.text(12, 262, 270, 6, f"(แสดง 2 ช่วงแรกจาก {len(res.spans)} ช่วง — ช่วงที่เหลือดูในรายการคำนวณแบบสรุป)",
                    5, RED)


def column_pages(bk: Book, res_all, b_, fc):
    cards = sorted(res_all.get("cards") or [], key=lambda c: (c["x"], c["y"], c["floor"]))
    per_page = 6
    for start in range(0, len(cards), per_page):
        bk.page("เสา", f"Column-{start // per_page + 1}")
        for i, c in enumerate(cards[start:start + per_page]):
            col, row = i % 3, i // 3
            x, y = 12 + col * 92, 40 + row * 112
            spec = c["spec"]
            b, h = float(spec.get("b", 0.2)), float(spec.get("h", 0.2))
            main, tie = R.parse_bar(spec.get("main")), R.parse_bar(spec.get("tie"))
            Ag = b * h * 1e4
            As = (main.n * main.area) if main and main.n else 0.0
            Pg = As / Ag if Ag else 0.0
            fs = C.fs_of(main, b_)
            if b_["method"] == "SDM":
                cap = 0.80 * 0.70 * (0.85 * fc * (Ag - As) + C.fy_of(main, b_) * As)
                cap_lab = "φPn (กก.)"
            else:
                cap = 0.85 * Ag * (0.25 * fc + fs * Pg)
                cap_lab = "0.85Ag(0.25fc′+fsPg)"
            ok = c["P"] <= cap
            yy = bk.table(x, y, [18, 22, 22, 20], [("NO.", "กว้าง(ซม.)", "ยาว(ซม.)", "สูง(ม.)"),
                                                   ((c["mark"], BLUE), (f"{b * 100:.0f}", BLUE),
                                                    (f"{h * 100:.0f}", BLUE), f"{c['H']:.2f}")], 7.5)
            bk.table(x, yy + 2, [34, 24, 24], [
                ("Column", "", ("OK" if ok else "NG", GREEN if ok else RED)),
                ("P", "kg.", f"{c['P']:,.0f}"),
                ("เหล็กยืน", (f"{main.kind}{main.d}" if main else "-", BLUE), (str(main.n if main else 0), BLUE)),
                ("เหล็กปลอก", (f"1-{tie.kind}{tie.d}" if tie else "-", BLUE), (f"@{tie.s:.2f}" if tie else "-", BLUE)),
                ("As", "cm²", f"{As:.2f}"), ("Ag", "cm²", f"{Ag:.2f}"), ("Pg", "", f"{Pg:.3f}"),
                ("Fc′", "ksc", f"{fc:.2f}"), (cap_lab, "", (f"{cap:,.0f}", RED))], 7.0)
            fl = "ตอม่อ" if c["floor"] < 0 else f"ชั้น {c['floor'] + 1}"
            bk.text(x, yy + 2 + 9 * 7.0, 82, 6, f"{fl}      Grid ({c['x']:.2f}, {c['y']:.2f})", 5.2)


def list_page(bk: Book, title: str, tag: str, members):
    bk.page(title, tag)
    rows = [("ชิ้นส่วน", "แรงที่เกิด", "กำลังที่รับได้", "อัตราส่วน", "ผล")]
    for m in members:
        rows.append((m.name, m.demand, m.capacity, f"{m.ratio:.2f}",
                     ("ผ่าน", GREEN) if m.ok else ("ไม่ผ่าน", RED)))
    y = 34
    for chunk in range(0, len(rows), 30):
        y = bk.table(10, y, [95, 135, 110, 22, 18], rows[chunk:chunk + 30], 7.0, left=True)
        if chunk + 30 < len(rows):
            bk.page(title, tag)
            y = 34


def advice_page(bk: Book, res_all, data):
    """รายการที่ไม่ผ่าน และคำแนะนำ — what to add, where, for each failing
    member; then the change of each library mark that makes all pass."""
    from core import wanic_advice as AD
    tips = AD.advise(res_all, data)
    if not tips:
        return
    bk.page("รายการที่ไม่ผ่าน และคำแนะนำการแก้ไข", "Advice")
    y = 34
    for name, lines in tips:
        if y > 228:
            bk.page("รายการที่ไม่ผ่าน และคำแนะนำการแก้ไข", "Advice")
            y = 34
        bk.text(12, y, 380, 6.5, f"✗ {name}", 5.8, RED, bold=True)
        y += 6.5
        for ln in lines:
            bk.text(20, y, 372, 6, f"→ {ln}", 5.4)
            y += 6
        y += 1.5
    try:
        import copy
        trial = copy.deepcopy(data)
        done = AD.apply_fixes(trial)
    except Exception:                                    # noqa: BLE001
        done = []
    if done:
        if y > 200:
            bk.page("รายการที่ไม่ผ่าน และคำแนะนำการแก้ไข", "Advice")
            y = 34
        y += 4
        bk.text(12, y, 380, 7, "สรุปการแก้ตามเบอร์ (คำนวณซ้ำแล้วผ่านทุกรายการ):", 6.2, GREEN, bold=True)
        y += 8
        for t in done:
            bk.text(20, y, 372, 6, f"• {t}", 5.4)
            y += 6
    bk.text(12, 244, 290, 6, "คำแนะนำคิดตามเกณฑ์เดียวกับรายการคำนวณ (วสท. 011008 / ACI 318 · AISC ASD) — "
            "ผู้ออกแบบต้องตรวจและยืนยันก่อนใช้", 5.0)


def make_book(res_all, data, path, info: dict, critical: bool = False) -> int:
    """Write the booklet; returns the number of pages. ``critical``: only the
    most stressed beam / column / slab / footing of each mark (a shorter book
    for the permit)."""
    from core import wanic_calc_cards as CC
    b_ = res_all["basis"]
    fc = b_["fc"]
    CC.attach_lateral_moments(res_all, data)
    if critical:
        res_all = CC.critical_members(res_all)
    bk = Book(path, info)
    cover(bk)
    basis_page(bk, b_)
    CC.roof_page(bk, res_all)
    CC.slab_pages(bk, res_all, data, critical)
    beam_pages(bk, res_all, b_, fc)
    column_pages(bk, res_all, b_, fc)
    CC.footing_pages(bk, res_all, data, critical)
    if (data or {}).get("truss"):
        from core import wanic_truss as T
        from core.wanic_truss_view import truss_pages
        try:
            tp, td = T.design_of(data)
            truss_pages(bk, tp, td)
        except ValueError:
            pass
    if (data or {}).get("lateral"):
        from core import wanic_lateral as LT
        from core.wanic_lateral_view import lateral_pages
        lateral_pages(bk, LT.analyse(data))
    if (data or {}).get("flatslab"):
        from core import wanic_flatslab as FS
        from core.wanic_flatslab_view import flatslab_pages
        fp, fr = FS.design_of(data)
        flatslab_pages(bk, fp, fr)
    if (data or {}).get("purlin"):
        from core import wanic_purlin as PU
        from core.wanic_purlin_view import purlin_pages
        pp, pr = PU.design_of(data)
        purlin_pages(bk, pp, pr)
    if (data or {}).get("steel"):
        from core import wanic_steel as S
        from core.wanic_steel_view import steel_pages
        steel_pages(bk, S.design_building(data))
    ms = res_all["members"]
    groups = ()
    for title, tag, g in groups:
        sel = [m for m in ms if m.group == g]
        if sel:
            list_page(bk, title, tag, sel)
    list_page(bk, "สรุปผลการตรวจสอบทุกชิ้นส่วน", "Summary", ms)
    advice_page(bk, res_all, data)
    n = bk.n
    bk.close()
    return n
