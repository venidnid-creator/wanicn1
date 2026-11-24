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

    def page(self, title: str, tag: str, sign: bool = True):
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
        if sign:
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

    def plain(self, x, y, w, lines, ok=True, px=5.3) -> float:
        """«อธิบายง่าย»: a tinted box with the load that acts and the load
        it can take, in plain words — green when it passes, red when not.
        ``lines`` is a string or a list of them; returns the y below it."""
        if isinstance(lines, str):
            lines = [lines]
        lines = [t for t in lines if t]
        if not lines:
            return y
        mm, p = self.mm, self.p
        # wrap at « · » where a line is wider than the box
        from PySide6.QtGui import QFontMetricsF
        fm = QFontMetricsF(_font(px * mm))
        room = (w - 3) * mm
        wrapped = []
        for t in lines:
            lead = t[:len(t) - len(t.lstrip())]
            parts = t.strip().split(" · ")
            cur = ""
            for part in parts:
                cand = part if not cur else cur + " · " + part
                if cur and fm.horizontalAdvance(lead + cand) > room:
                    wrapped.append(lead + cur)
                    cur, lead = part, lead or "   "
                else:
                    cur = cand
            wrapped.append(lead + cur)
        lines = wrapped
        lh = px * 1.25
        h = lh * len(lines) + 2.4
        p.setPen(QPen(GREEN if ok else RED, 1))
        p.setBrush(QColor("#ECFDF5") if ok else QColor("#FEF2F2"))
        p.drawRoundedRect(QRectF(x * mm, y * mm, w * mm, h * mm), 1.6 * mm, 1.6 * mm)
        p.setBrush(Qt.NoBrush)
        for k, t in enumerate(lines):
            self.text(x + 1.5, y + 1.2 + k * lh, w - 3, lh, t, px, QColor("#065F46") if ok else RED)
        return y + h

    def close(self):
        self.p.end()


# ---- the pages ---------------------------------------------------------------------------

#: the chapters of the book, roof to piles (the order of the pages)
CHAPTERS = (("roof", "1", "โครงหลังคา", "Roof"), ("slab", "2", "พื้น คสล. / บันได", "Slab"),
            ("beam", "3", "คาน (หลังคา → ชั้นบน → คานคอดิน)", "Beam"),
            ("column", "4", "เสา (ชั้นบน → ชั้นล่าง → ตอม่อ)", "Column"),
            ("footing", "5", "ฐานราก", "Footing"), ("pile", "6", "เสาเข็ม", "Pile"),
            ("lateral", "7", "แรงด้านข้าง (แผ่นดินไหว / ลม)", "Lateral"),
            ("summary", "8", "สรุปผลการตรวจสอบ", "Summary"))


def _house_sketch(bk: Book, x, y, w, h):
    """A section through a house, roof to piles, its parts numbered as the
    chapters of the book."""
    mm, p = bk.mm, bk.p
    X = lambda u: (x + u * w) * mm                           # noqa: E731 - local scale
    Y = lambda v: (y + v * h) * mm                           # noqa: E731
    ink = QPen(INK, 1.6)
    p.setPen(ink)
    p.setBrush(Qt.NoBrush)
    p.drawPolyline(QPolygonF([QPointF(X(0.02), Y(0.26)), QPointF(X(0.5), Y(0.02)), QPointF(X(0.98), Y(0.26))]))
    p.setBrush(QColor("#E5E7EB"))
    for v in (0.28, 0.52):                                   # roof beam / floor slab with beams
        p.drawRect(QRectF(X(0.10), Y(v), X(0.90) - X(0.10), (0.035 * h) * mm))
    p.drawRect(QRectF(X(0.06), Y(0.76), X(0.94) - X(0.06), (0.03 * h) * mm))      # ground beams
    for u in (0.12, 0.5, 0.86):
        p.drawRect(QRectF(X(u), Y(0.315), (0.02 * w) * mm, Y(0.76) - Y(0.315)))  # columns and stumps
        p.drawRect(QRectF(X(u - 0.05), Y(0.83), (0.12 * w) * mm, (0.05 * h) * mm))  # footings
        p.setBrush(QColor("#F3F4F6"))
        p.drawRect(QRectF(X(u + 0.003), Y(0.88), (0.014 * w) * mm, Y(0.99) - Y(0.88)))  # piles
        p.setBrush(QColor("#E5E7EB"))
    p.setBrush(Qt.NoBrush)
    p.setPen(QPen(QColor("#92400E"), 1, Qt.DashLine))
    p.drawLine(QPointF(X(0.0), Y(0.80)), QPointF(X(1.0), Y(0.80)))
    tags = (("1", 0.5, 0.10), ("2", 0.30, 0.50), ("3", 0.70, 0.27), ("4", 0.535, 0.42), ("5", 0.62, 0.86),
            ("6", 0.89, 0.95))
    for t, u, v in tags:
        cx, cy = X(u), Y(v)
        p.setPen(QPen(BLUE, 1.2))
        p.setBrush(QColor("white"))
        p.drawEllipse(QPointF(cx, cy), 3.2 * mm, 3.2 * mm)
        p.setBrush(Qt.NoBrush)
        bk.text(u * w + x - 4, v * h + y - 4, 8, 8, t, 5.5, BLUE, Qt.AlignCenter, bold=True)


def cover(bk: Book, res_all=None):
    """ปก: the title, the project, what the book holds (roof → piles, with
    a numbered section of the house), the standards, the result and the
    signature boxes."""
    import datetime as _dt
    bk.page("", "cover", sign=False)
    mm, p = bk.mm, bk.p
    i = bk.info
    p.setPen(QPen(BLUE, 3))
    p.drawRect(QRectF(6 * mm, 6 * mm, bk.W - 12 * mm, bk.H - 12 * mm))
    p.fillRect(QRectF(6 * mm, 6 * mm, bk.W - 12 * mm, 40 * mm), QColor("#1E3A8A"))
    bk.text(14, 10, 380, 20, "รายการคำนวณโครงสร้าง", 20, QColor("white"), Qt.AlignLeft | Qt.AlignVCenter, True)
    bk.text(14, 30, 380, 12, "STRUCTURAL CALCULATION  ·  คอนกรีตเสริมเหล็ก", 9, QColor("#BFDBFE"))
    rows = (("โครงการ", i.get("project", "")), ("เจ้าของ", i.get("owner", "")), ("สถานที่", i.get("place", "")),
            ("ผู้คำนวณ", i.get("engineer", "")), ("วันที่", i.get("date") or _thai_date(_dt.date.today())))
    for k, (lab, val) in enumerate(rows):
        bk.text(16, 56 + k * 14, 40, 12, lab, 8.5, QColor("#374151"), bold=True)
        bk.text(56, 56 + k * 14, 170, 12, f":  {val}", 8.5)
        p.setPen(QPen(QColor("#D1D5DB"), 1))
        p.drawLine(QPointF(56 * mm, (68 + k * 14) * mm), QPointF(226 * mm, (68 + k * 14) * mm))
    _house_sketch(bk, 250, 54, 140, 120)
    bk.text(250, 176, 140, 8, "ลำดับรายการคำนวณ: จากหลังคา ลงถึงเสาเข็ม", 5.8, BLUE, Qt.AlignCenter)
    y = 132
    bk.text(16, y, 220, 9, "เนื้อหาในเล่ม", 7.5, BLUE, bold=True)
    for k, (_key, num, th, _en) in enumerate(CHAPTERS):
        bk.text(20, y + 10 + k * 8.2, 210, 8, f"{num}.  {th}", 6.4)
    y2 = y + 10 + len(CHAPTERS) * 8.2 + 4
    bk.text(16, y2, 220, 8, "มาตรฐานที่ใช้", 7.0, BLUE, bold=True)
    bk.text(20, y2 + 7, 216, 7, "วสท. 011008 (คอนกรีต SDM) · ACI 318 · มยผ. 1301/1302-61 (แผ่นดินไหว)", 5.6)
    bk.text(20, y2 + 13, 216, 7, "มยผ. 1311-50 (ลม) · กฎกระทรวงกำหนดการรับน้ำหนัก ความต้านทาน ความคงทนของอาคาร", 5.6)
    if res_all is not None:
        ms = res_all.get("members") or []
        bad = sum(1 for m in ms if not m.ok)
        ok = not bad
        p.setPen(QPen(GREEN if ok else RED, 1.4))
        p.setBrush(QColor("#ECFDF5") if ok else QColor("#FEF2F2"))
        p.drawRoundedRect(QRectF(16 * mm, (y2 + 23) * mm, 220 * mm, 13 * mm), 2 * mm, 2 * mm)
        p.setBrush(Qt.NoBrush)
        bk.text(20, y2 + 23, 212, 13, (f"✓ ผลการตรวจสอบ: ผ่านทุกรายการ ({len(ms)} ชิ้นส่วน)" if ok
                                       else f"✗ ผลการตรวจสอบ: ไม่ผ่าน {bad} จาก {len(ms)} ชิ้นส่วน"),
                7.5, GREEN if ok else RED, bold=True)
    for k, lab in enumerate(("ผู้คำนวณ", "วิศวกรผู้ตรวจสอบ")):
        bx = 250 + k * 72
        p.setPen(QPen(INK, 1))
        p.drawRect(QRectF(bx * mm, 186 * mm, 66 * mm, 30 * mm))
        bk.text(bx + 2, 187, 62, 7, lab, 5.6, QColor("#374151"))
        bk.text(bx + 2, 201, 62, 7, "(..........................................)", 5.6, align=Qt.AlignCenter)
        bk.text(bx + 2, 208, 62, 7, i.get("engineer", "") if k == 0 else "เลขทะเบียน ...................", 5.0,
                QColor("#374151"), Qt.AlignCenter)
    bk.text(16, 262, 300, 8, "เอกสารนี้ต้องให้วิศวกรโยธาผู้มีใบอนุญาตตรวจสอบและลงนามรับรองก่อนก่อสร้าง", 5.8, ORANGE)
    bk.text(200, 262, 196, 8, "คำนวณโครงสร้างโดย WANICNSURVEY", 6, align=Qt.AlignRight | Qt.AlignVCenter)


def _thai_date(d) -> str:
    months = ("มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม", "มิถุนายน", "กรกฎาคม", "สิงหาคม",
              "กันยายน", "ตุลาคม", "พฤศจิกายน", "ธันวาคม")
    return f"{d.day} {months[d.month - 1]} {d.year + 543}"


def behaviour_pages(bk: Book, members, title: str, tag: str, limit: int = 8):
    """พฤติกรรมแรง: the load-behaviour pictures (slabs, footings) of the most
    stressed member of each mark, four to a page — drawn as on screen, then
    placed on the sheet."""
    from PySide6.QtGui import QImage
    from core import wanic_calc_view as V
    best = {}
    for m in members:
        pic = getattr(m, "picture", None)
        if not pic:
            continue
        mk = pic.get("mark") or m.name.split(" ", 1)[0]
        if mk not in best or m.ratio > best[mk].ratio:
            best[mk] = m
    picks = sorted(best.values(), key=lambda m: m.name)[:limit]
    for start in range(0, len(picks), 4):
        bk.page(title, f"{tag}-{start // 4 + 1}")
        for i, m in enumerate(picks[start:start + 4]):
            img = QImage(1520, 792, QImage.Format_ARGB32)     # 760 × 396 at 2× — the text reads on A4
            img.setDevicePixelRatio(2.0)
            img.fill(QColor("white"))
            pp = QPainter(img)
            V.draw_any(pp, QRectF(6, 4, 748, 388), m.picture, m.name)
            pp.end()
            x, y = 12 + (i % 2) * 192, 34 + (i // 2) * 104
            bk.p.drawImage(QRectF(x * bk.mm, y * bk.mm, 188 * bk.mm, 98 * bk.mm), img)
            bk.p.setPen(QPen(QColor("#D1D5DB"), 1))
            bk.p.drawRect(QRectF(x * bk.mm, y * bk.mm, 188 * bk.mm, 98 * bk.mm))


#: มาตรฐานที่ใช้ และใช้ตรงไหน — roof to piles (the owner: «แจ้งมาด้วยว่าใส่ตรงจุดไหน»)
STANDARDS_MAP = (
    ("ทั้งอาคาร", "กฎกระทรวงกำหนดการออกแบบโครงสร้างอาคาร … พ.ศ. 2566 ข้อ 7",
     "ชุดน้ำหนักบรรทุก 1.4D + 1.7L · ลม 0.75(1.4D + 1.7L) + 1.6W, 0.9D + 1.6W · แผ่นดินไหว 0.75(1.4D + 1.7L) + 1.0E, 0.9D + 1.0E"),
    ("ทั้งอาคาร", "กฎกระทรวง 2566 ข้อ 8", "ตัวคูณลดกำลัง φ ดัด 0.90 · เฉือน 0.85 · เสาปลอกเดี่ยว 0.70 "
     "(ไม่ระบุการควบคุมคุณภาพ: 0.75 · 0.70 · 0.60)"),
    ("1 หลังคา", "กฎกระทรวง 2566 ข้อ 11 · ประกาศ มท. 2567 ตาราง 7", "น้ำหนักจรหลังคา 50 กก./ตร.ม. · แรงลม 60–160 กก./ตร.ม. "
     "ตามความสูงและภูมิประเทศ · แรงยก Cp 0.7"),
    ("1 หลังคา", "ประกาศ มท. 2567 ตาราง 1", "ระยะแอ่นตัวโครงหลังคา ≤ L/180 (ไม่มีฝ้า) – L/360 (ฝ้าฉาบ)"),
    ("2 พื้น", "กฎกระทรวง 2566 ข้อ 11 · วสท. 011008", "น้ำหนักจรบ้านพักอาศัย 200 กก./ตร.ม. (เดิม 150) · "
     "หนาขั้นต่ำกันแอ่น · ระยะแอ่น ≤ L/240"),
    ("2 บันได", "กฎกระทรวง 2566 ข้อ 11", "บันไดบ้านพักอาศัย 200 กก./ตร.ม. · บันไดหนีไฟ 400"),
    ("3 คาน", "วสท. 011008 · ประกาศ มท. 2567 ตาราง 1", "φMn φVn · แผนภาพต้องอยู่ในเส้นกำลัง · แอ่นตัวระยะยาว ≤ L/240 · "
     "ปลายติดเสา Mu− ≥ wL²/16"),
    ("4 เสา / ตอม่อ", "วสท. 011008 · ACI 318", "แผนภาพ P-M · emin 15 มม. + 0.03h · ขยายโมเมนต์เสาชะลูด · "
     "เหล็กยืน 1–4 % (ความปลอดภัยสูงกว่าเกณฑ์ 8 %)"),
    ("4 เสา (แรงด้านข้าง)", "มยผ. 1301/1302-61 · กฎกระทรวงแผ่นดินไหว 2564 · ประกาศ มท. 2567 ผนวก ข",
     "43 จังหวัด (บริเวณ 1–3) คิดแผ่นดินไหวอัตโนมัติ · V = Cs·W · ตรวจเสาทั้ง 0.75(1.4D+1.7L)+E และ 0.9D+E"),
    ("5 ฐานราก", "วสท. 011008 · ผลเจาะสำรวจดิน", "แรงดันดิน q ≤ qa (ผู้ใช้กรอก ค่าเริ่มต้น 5 ตัน/ตร.ม.) · "
     "เฉือนทางเดียว/ทะลุ φ 0.85 · ฐานแต่ละจุดออกแบบตามแรงของตัวเอง"),
    ("6 เสาเข็ม", "ผลทดสอบเข็ม / สูตร Hiley", "แรงต่อต้น ≤ กำลังเข็มที่ปลอดภัย"),
    ("ความปลอดภัยเพิ่ม", "สูงกว่าเกณฑ์ (ผู้ออกแบบเลือก)", "ไม่ลดน้ำหนักจรตามจำนวนชั้น (ข้อ 13 ยอมให้ลด) · "
     "เผื่อ 2 % ในการเลือกเหล็กเสา · คานคอดิน ตอม่อ เสาชั้น 1 หน้าตัดเดียวกัน"),
)


def standards_page(bk: Book):
    bk.page("มาตรฐานที่ใช้ และใช้ตรงไหน (หลังคา → เสาเข็ม)", "Standards")
    mm, p = bk.mm, bk.p
    widths = [42, 104, 240]
    rows = [("ส่วนของอาคาร", "มาตรฐาน / ข้อ", "ใช้อย่างไร")] + [tuple(r) for r in STANDARDS_MAP]
    y = 32.0
    flags = int(Qt.AlignLeft | Qt.AlignVCenter | Qt.TextWordWrap)
    for k, row in enumerate(rows):                       # the cells wrap: every word of the clause shows
        f = _font(5.4 * mm, bold=(k == 0))
        p.setFont(f)
        hs = [p.boundingRect(QRectF(0, 0, (w - 3) * mm, 1000 * mm), flags, t).height() / mm for w, t in zip(widths, row)]
        h = max(hs) + 3.0
        x = 10.0
        for w, t in zip(widths, row):
            if k == 0:
                p.fillRect(QRectF(x * mm, y * mm, w * mm, h * mm), QColor("#E0E7FF"))
            p.setPen(QPen(INK, 1))
            p.drawRect(QRectF(x * mm, y * mm, w * mm, h * mm))
            p.drawText(QRectF((x + 1.5) * mm, y * mm, (w - 3) * mm, h * mm), flags, t)
            x += w
        y += h


def contents_page(bk: Book, starts: dict):
    """สารบัญ: every chapter with the page it starts on (from a first pass)."""
    bk.page("สารบัญ", "Contents")
    rows = [("ลำดับ", "รายการ", "หน้า")]
    for key, num, th, _en in CHAPTERS:
        rows.append((num, th, str(starts[key])) if key in starts
                    else ((num, QColor("#9CA3AF")), (th + " — ไม่มีในโครงการนี้", QColor("#9CA3AF")), ""))
    bk.table(60, 40, [24, 220, 30], rows, 10, left=True)


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
    right = [("น้ำหนักบรรทุกจรขั้นต่ำ (กฎกระทรวง 2566 ข้อ 11)", ""),
             ("บ้านพักอาศัย ห้องต่าง ๆ ระเบียง บันได", "200 กก./ตร.ม."), ("อาคารชุด หอพัก โรงแรม (ห้องนอน)", "200 กก./ตร.ม."),
             ("สำนักงาน ธนาคาร ห้องเรียน", "250 กก./ตร.ม."), ("อาคารพาณิชย์ (ขายปลีก)", "400 กก./ตร.ม."),
             ("คลังสินค้า โรงงาน", "500 กก./ตร.ม."), ("หลังคา · กันสาด คสล. · ดาดฟ้า", "50 · 100 · 200 กก./ตร.ม."),
             ("น้ำหนักคอนกรีต", f"{b_['concrete']:,.0f} กก./ลบ.ม."),
             ("ผนังก่ออิฐมอญ อิฐบล็อก", "180 กก./ตร.ม."), ("ผนังอิฐมวลเบา", "90 กก./ตร.ม."),
             ("ผนังยิปซัม โครงไม้", "25 กก./ตร.ม."),
             ("แรงลม เมือง/ชานเมือง สูงไม่เกิน 10 / 10–20 / 20–40 ม.", "60 / 80 / 120 กก./ตร.ม."),
             ("แรงลม โล่งหรือชายฝั่งทะเล สูงไม่เกิน 10 / 10–20 / 20–40 ม.", "100 / 120 / 160 กก./ตร.ม."),
             ("ตัวคูณลดกำลัง φ (กฎกระทรวง 2566 ข้อ 8" + (", ควบคุมคุณภาพ)" if b_.get("qc", True) else ", ไม่ระบุการควบคุม)"),
              f"ดัด {C.phi(b_, 'flex'):.2f} · เฉือน {C.phi(b_, 'shear'):.2f} · เสาปลอกเกลียว {C.phi(b_, 'spiral'):.3g} · "
              f"เสาปลอกเดี่ยว {C.phi(b_, 'tied'):.2f}")]
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
    ext = getattr(res, "Mext", (0.0, 0.0))                 # exterior ends built into columns: wL²/16
    if i == 0:
        ML = max(ML, ext[0])
    if i == len(res.spans) - 1:
        MR = max(MR, ext[1])
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
            bk.text((X(x) / mm), y - 9, (X(x + sp.L) - X(x)) / mm, 6,
                    f"{'ยื่น ' if sp.cant else ''}W={sp.w:,.0f}" if sp.cant else f"W={sp.w:,.1f} kg/m", 5,
                    align=Qt.AlignCenter)
            bk.text((X(x) / mm), y + 2, (X(x + sp.L) - X(x)) / mm, 6, f"L= {sp.L:.2f} m.", 5,
                    align=Qt.AlignCenter)
            x += sp.L
        ends = [0.0]
        for sp in res.spans:
            ends.append(ends[-1] + sp.L)
            for a_, P in sp.P:
                px = X(ends[-2] + a_)
                p.setPen(QPen(RED, 1.2))
                p.drawLine(QPointF(px, base - 7 * mm), QPointF(px, base - 1.5 * mm))
                bk.text(px / mm + 0.5, y - 13, 30, 5, f"P={P:,.0f} kg", 4.6, RED)
            for a_, b2, wu in sp.U:
                p.fillRect(QRectF(X(ends[-2] + a_), base - 4.5 * mm, X(ends[-2] + b2) - X(ends[-2] + a_), 2.4 * mm),
                           QColor(124, 58, 237, 90))
                bk.text(X(ends[-2] + a_) / mm, y - 13, 40, 5, f"+{wu:,.0f} kg/m", 4.6, QColor("#7C3AED"))
            p.setPen(QPen(INK, 1))
        for x in (getattr(res, "supports", None) or ends):
            cx = X(x)
            p.setBrush(Qt.NoBrush)
            p.drawPolygon(QPolygonF([QPointF(cx, base + 1.5 * mm), QPointF(cx - 1.5 * mm, base + 4 * mm),
                                     QPointF(cx + 1.5 * mm, base + 4 * mm)]))
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


def beam_plain(res) -> tuple:
    """Per span, in plain words: the moment and the shear that act against
    what the beam can take (ตัน-ม. / ตัน), with the share used."""
    caps = getattr(res, "caps", None) or {}
    n = 24
    out, ok_all = [], True
    for i, sp in enumerate(res.spans):
        M = res.M[i * (n + 1):(i + 1) * (n + 1)]
        V = res.V[i * (n + 1):(i + 1) * (n + 1)]
        mp, mn, v = max(max(M), 0.0), max(-min(M), 0.0), max(abs(x) for x in V)
        out.append(f"ช่วงที่ {i + 1} ยาว {sp.L:.2f} ม. · น้ำหนักบนคาน {sp.w:,.0f} กก./ม.")
        for lab, act, cap in (("โมเมนต์กลางช่วง", mp, caps.get("M+")), ("โมเมนต์ที่หัวเสา", mn, caps.get("M-")),
                              ("แรงเฉือน", v, caps.get("V"))):
            if act <= 1.0 or not cap:
                continue
            unit = "ตัน" if lab == "แรงเฉือน" else "ตัน-ม."
            ok = act <= cap * (1 + 1e-9)
            t = (f"   {lab} {act / 1000:,.2f} · รับได้ {cap / 1000:,.2f} {unit} · ใช้ไป {act / cap * 100:,.0f} % "
                 + ("ผ่าน" if ok else "ไม่ผ่าน"))
            ok_all = ok_all and ok
            out.append(t)
        if i >= 1:                                   # the two spans whose tables are on the page
            if len(res.spans) > 2:
                worst = max(range(len(res.spans)), key=lambda j: max(abs(v) for v in
                                                                      res.M[j * (n + 1):(j + 1) * (n + 1)]))
                out.append(f"(อีก {len(res.spans) - 2} ช่วง · ช่วงที่รับแรงมากที่สุดคือช่วงที่ {worst + 1} "
                           "· ดูตารางสรุปท้ายเล่ม)")
            break
    return out, ok_all


def beam_pages(bk: Book, res_all, b_, fc):
    k = 0
    beams = [m for m in res_all["members"]
             if m.group == "beam" and m.diagram is not None and hasattr(m.diagram, "spec")]
    # จากบนลงล่าง: the roof ring beams, the upper floors, the ground beams last
    beams.sort(key=lambda m: (bool(m.diagram.ground), -int(m.diagram.level)))
    for m in beams:
        res = m.diagram
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
        lines, ok_all = beam_plain(res)
        bk.text(272, 133, 124, 6, "อธิบายง่าย: แรงที่กระทำ เทียบกับ แรงที่รับได้", 5.6, bold=True)
        bk.plain(272, 140, 124, lines + [m.plain_text()], ok_all and m.ok, 4.9)


def column_pages(bk: Book, res_all, b_, fc):
    # จากบนลงล่าง: the top floor's columns first, the stumps (floor −1) last
    cards = sorted(res_all.get("cards") or [], key=lambda c: (-c["floor"], c["x"], c["y"]))
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
                cap = 0.80 * C.phi(b_, "tied") * (0.85 * fc * (Ag - As) + C.fy_of(main, b_) * As)
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
            f_ = (sum(C.factors(b_)) / 2.0) or 1.0            # back to the load in use (no safety factor)
            bk.plain(x, yy + 9 + 9 * 7.0, 82, [f"น้ำหนักที่ลงเสา ≈ {c['P'] / f_ / 1000:,.1f} ตัน",
                                              f"เสารับได้ ≈ {cap / f_ / 1000:,.1f} ตัน",
                                              f"ใช้กำลังไป {c['P'] / cap * 100 if cap else 999:,.0f} % → "
                                              + ("ผ่าน" if ok else "ไม่ผ่าน")], ok, 5.0)


def list_page(bk: Book, title: str, tag: str, members):
    bk.page(title, tag)
    rows = [("ชิ้นส่วน", "แรงที่กระทำ", "แรงที่รับได้", "อัตราส่วน", "อธิบายง่าย")]
    for m in members:
        rows.append((m.name, m.demand, m.capacity, f"{m.ratio:.2f}",
                     (f"ใช้กำลังไป {m.ratio * 100:,.0f} % · ผ่าน", GREEN) if m.ok
                     else (f"ใช้กำลังไป {m.ratio * 100:,.0f} % · ไม่ผ่าน", RED)))
    y = 34
    for chunk in range(0, len(rows), 30):
        y = bk.table(10, y, [88, 118, 100, 20, 58], rows[chunk:chunk + 30], 7.0, left=True)
        if chunk + 30 < len(rows):
            bk.page(title, tag)
            y = 34


def reserve_page(bk: Book, members):
    """สรุปสำหรับเจ้าของอาคาร — how much more each member can take, in
    kg/m², kg per metre or tonnes per column / footing."""
    from core import wanic_calc as C2
    rows = [m for m in members if m.qty and m.qty_unit]
    if not rows:
        return
    bk.page("สรุปกำลังสำรอง (อธิบายแบบเข้าใจง่าย)", "Reserve")
    bk.text(12, 32, 380, 7, "แรงที่ลงมา เทียบกับแรงที่ชิ้นส่วนรับได้ เมื่อหักลบกันแล้ว ยังรับน้ำหนักเพิ่มได้อีกเท่าไร "
            "(ค่าเป็นน้ำหนักใช้งาน — ไม่รวมตัวคูณความปลอดภัย)", 5.8, bold=True)
    y = 42
    for g, t, ok in C2.reserve_summary(members):
        bk.text(14, y, 380, 7, ("✓ " if ok else "✗ ") + t, 6.0, GREEN if ok else RED, bold=True)
        y += 8
    y += 4
    tab = [("ชิ้นส่วน", "อัตราส่วน", "รับเพิ่มได้อีก / เกินกำลัง")]
    for m in rows:
        tab.append((m.name, f"{m.ratio:.2f}", (m.reserve_text(), GREEN if m.ok else RED)))
    per = 22
    for k in range(0, len(tab) - 1, per):
        if k:
            bk.page("สรุปกำลังสำรอง (อธิบายแบบเข้าใจง่าย)", "Reserve")
            y = 34
        bk.table(10, y, [130, 30, 230], [tab[0]] + tab[1 + k:1 + k + per], 7.0, left=True)
    bk.text(12, 244, 290, 6, "คิดแบบเส้นตรง: ถ้าน้ำหนักเพิ่มเป็นสัดส่วน แรงในชิ้นส่วนเพิ่มตาม · พื้น = คน/ของวางเพิ่ม "
            "(น้ำหนักจร) · เสา/ฐานราก = น้ำหนักลงต่อต้น/ฐาน", 5.0)


def pile_page(bk: Book, data, b_):
    """เสาเข็ม: each type used by a footing mark — section, length, how the
    safe load was found, the numbers, and the marks on it."""
    from core import wanic_building as B2
    from core import wanic_pile as PL
    lib = B2.library_of(data)
    used = {}
    for m, sp in lib.items():
        if sp.get("kind") == "footing" and int(sp.get("piles") or 0) > 0:
            used.setdefault(PL.type_of_spec(sp), []).append(f"{m} ({int(sp['piles'])} ต้น)")
    if not used:
        return
    bk.page("เสาเข็ม (กำลังรับน้ำหนักต่อต้น)", "Pile")
    types = PL.types_of(data, b_)
    y = 34
    for k in ("P1", "P2"):
        if k not in used:
            continue
        t = types[k]
        c = PL.capacity(t)
        bk.text(12, y, 380, 8, f"เสาเข็ม {k} — {c['name']} ยาว {c['len']:.2f} ม. · {PL.METHODS[t.get('method', 'given')]}",
                7.0, BLUE, bold=True)
        y += 9
        for ln in c["lines"]:
            bk.text(16, y, 380, 6.5, ln, 5.8)
            y += 6.8
        bk.text(16, y, 380, 7, f"ใช้กับฐานราก: {', '.join(used[k])}", 5.8, GREEN, bold=True)
        y += 13
    bk.text(12, 244, 380, 6, "Qa = Qult / FS (สถิต 2.0 · พลวัต 2.5 · สูตรการตอก 3.0 · ข้อมูลดิน 2.5) และไม่เกินกำลังตัวเข็ม "
            "0.25 fc′ Ac · ผลทดสอบต้องมาจากเข็มทดสอบในพื้นที่จริง รับรองโดยวิศวกร", 5.0)


def stair_page(bk: Book, dz: dict, b_: dict):
    """บันได คสล.: the developed section along the walking line (steps,
    waist, landing, bars, supports), the step checks and every span."""
    mm, p = bk.mm, bk.p
    lay = dz["layout"]
    bk.page(dz["title"], "Stair")
    R_, g, w, t = lay["R"], lay["g"], lay["w"], dz["t"]
    # the developed section: flight 1, the landing, flight 2 (unfolded)
    segs = []                                          # (x0, run, z0, n, kind)
    x = 0.0
    for i, f in enumerate(lay["flights"]):
        if i == 1:
            segs.append((x, w, f["z0"], 0, "land"))
            x += w
        segs.append((x, f["L"], f["z0"], f["n"], "flight"))
        x += f["L"]
    Ltot, H = x, lay["H"]
    X0, Y0, Wd, Hd = 24.0, 124.0, 214.0, 82.0
    sc = min(Wd / max(Ltot, 0.1), Hd / max(H, 0.1))

    def P(xx, zz):
        return QPointF((X0 + xx * sc) * mm, (Y0 - zz * sc) * mm)
    p.setPen(QPen(INK, 1.4))
    p.setBrush(QColor(220, 220, 220, 120))
    cos = dz["cos"]
    for x0, run, z0, n, kind in segs:
        if kind == "land":
            p.drawRect(QRectF(P(x0, z0).x(), P(x0, z0).y(), run * sc * mm, t * sc * mm))
            bk.text(X0 + (x0 + run / 2) * sc - 15, Y0 - z0 * sc - 7, 30, 5, f"ชานพัก +{z0:.2f}", 4.6,
                    align=Qt.AlignCenter)
            continue
        r = R_
        poly = [P(x0, z0)]
        for k in range(n):
            poly += [P(x0 + k * g, z0 + (k + 1) * r), P(x0 + (k + 1) * g, z0 + (k + 1) * r)]
        tv = t / cos
        poly += [P(x0 + run, z0 + n * r - tv), P(x0, z0 - tv)]
        p.drawPolygon(QPolygonF(poly))
        # the main bars: along the soffit at the cover
        p.setPen(QPen(RED, 1.6))
        c = (C2_COVER + 0.006) / cos
        p.drawLine(P(x0, z0 - tv + c), P(x0 + run, z0 + n * r - tv + c))
        p.setPen(QPen(INK, 1.4))
    for x0, run, z0, n, kind in segs:
        if kind == "land":
            p.setPen(QPen(RED, 1.6))
            p.drawLine(P(x0, z0 - t + C2_COVER + 0.006), P(x0 + run, z0 - t + C2_COVER + 0.006))
            p.setPen(QPen(INK, 1.4))
            # the landing beam under the far edge
            bw, bh = 0.15, 0.35
            p.setBrush(QColor(180, 180, 180))
            p.drawRect(QRectF(P(x0 + run - bw, z0).x(), P(x0, z0).y(), bw * sc * mm, bh * sc * mm))
            bk.text(X0 + (x0 + run) * sc - 14, Y0 - (z0 - bh) * sc + 1, 30, 5, "คาน BS1", 4.6)
            p.setBrush(QColor(220, 220, 220, 120))
    # supports: the floor beams at the foot and the top
    p.setBrush(Qt.NoBrush)
    for xx, zz in ((0.0, -t / cos), (Ltot, H - t / cos)):
        c = P(xx, zz)
        p.drawPolygon(QPolygonF([c, c + QPointF(-2 * mm, 3.5 * mm), c + QPointF(2 * mm, 3.5 * mm)]))
    bk.text(10, Y0 + 6, 380, 6, f"รูปตัดตามแนวเดิน (คลี่) · ระยะราบรวม {Ltot:.2f} ม. · สูง {H:.2f} ม. · "
            f"{lay['n']} ลูกตั้ง × {R_ * 100:.1f} ซม. · ลูกนอน {g * 100:.0f} ซม. · หนา {t * 100:.0f} ซม.", 5.2)
    bk.text(10, Y0 + 12, 380, 6, f"เหล็กหลัก {dz['bars']} (เส้นแดง ด้านล่าง ตามลาด) · เหล็กกันร้าว {dz['temp']} ตามขวาง · "
            f"ระยะหุ้ม {C2_COVER * 100:.0f} ซม.", 5.2, RED)
    # the step checks
    rows = [("รายการ (กฎกระทรวง 55)", "ค่า", "เกณฑ์")]
    for a, v, lim, ok in dz["geo"]:
        rows.append((a, (v, GREEN if ok else RED), lim))
    bk.table(248, 34, [64, 34, 50], rows, 6.4, left=True)
    loads = [("น้ำหนัก (กก./ตร.ม.)", "ลาดเอียง", "ชานพัก"),
             ("คงที่", f"{dz['dead_inc']:,.0f}", f"{dz['dead_land']:,.0f}"),
             ("จร", f"{dz['ll']:,.0f}", f"{dz['ll']:,.0f}"),
             ("wu (1.4D + 1.7L)", f"{dz['wu_inc']:,.0f}", f"{dz['wu_land']:,.0f}")]
    bk.table(248, 34 + 6.4 * len(rows) + 4, [64, 42, 42], loads, 6.4, left=True)
    # every span
    y = 150
    tab = [("ช่วง", "พาด ม.", "Mu กก.-ม./ม.", "φMn", "Vu กก./ม.", "φVc", "หนาขั้นต่ำ L/20", "As ใช้/ต่ำสุด ซม²/ม.",
            "อัตรา", "รับเพิ่มได้อีก / หมายเหตุ")]
    for f, m in zip(dz["flights"], dz["members"][1:1 + len(dz["flights"])]):
        tab.append((f"ช่วงที่ {f['i']} ({f['n']} ลูกตั้ง)", f"{f['span']:.2f}", f"{f['Mu']:,.0f}", f"{f['cap']:,.0f}",
                    f"{f['Vu']:,.0f}", f"{f['vc']:,.0f}", f"{f['t_min'] * 100:.1f} ซม.",
                    f"{dz['As']:.2f} / {dz['As_min']:.2f}", (f"{m.ratio:.2f}", GREEN if m.ok else RED),
                    ("; ".join(f["notes"]) or m.reserve_text(), GREEN if m.ok else RED)))
    if dz["beam"]:
        bm = dz["beam"]
        m = dz["members"][-1]
        tab.append(("คานรับชานพัก BS1", f"{bm['L']:.2f}", f"{bm['res'].Mmax:,.0f}", "", f"{bm['res'].Vmax:,.0f}", "",
                    "", "", (f"{bm['ratio']:.2f}", GREEN if m.ok else RED),
                    (f"{bm['text']} · w = {bm['w']:,.0f} กก./ม. · " + m.reserve_text(), GREEN if m.ok else RED)))
    bk.table(10, y, [42, 15, 23, 17, 21, 17, 27, 33, 13, 176], tab, 7.0, left=True)
    bk.text(12, 244, 380, 6, "ท้องบันไดออกแบบเป็นพื้นทางเดียวพาดตามแนวบันได (ชานพักพาดรวมกับช่วงบันได รับด้วยคาน BS1) · "
            "M = wL²/8 · เหล็กกันร้าว ≥ 0.0025bt (SR24) / 0.0018bt (SD40)", 4.6)


C2_COVER = 0.020


def column_capacity(spec, b_) -> float:
    """The axial load a column can take (factored, kg) — as the column cards."""
    fc = b_["fc"]
    b, h = float(spec.get("b", 0.2)), float(spec.get("h", 0.2))
    main = R.parse_bar(spec.get("main"))
    Ag = b * h * 1e4
    As = (main.n * main.area) if main and main.n else 0.0
    if b_["method"] == "SDM":
        return 0.80 * C.phi(b_, "tied") * (0.85 * fc * (Ag - As) + C.fy_of(main, b_) * As)
    return 0.85 * Ag * (0.25 * fc + C.fs_of(main, b_) * (As / Ag if Ag else 0.0))


def checkload_page(bk: Book, res_all, data):
    """Checkload — Wcol, Wcol-Area and Wfloor of every ground-floor column."""
    from core import wanic_calc as C2
    try:
        ck = C2.checkload(data, res_all)
    except Exception:                                # noqa: BLE001 - the page is optional
        return
    if not ck["rows"]:
        return
    lo, hi = ck["range"]
    head = ("เสา", "ตำแหน่ง", "พื้นที่รับ ตร.ม.", "Wcol ตัน", "Wcol-Area ตัน", "ต่าง %", "Wfloor กก./ตร.ม.",
            "เสารับได้ ตัน", "ใช้ไป %", "ผล")
    b_ = res_all["basis"]
    caps = {}                                         # (x, y) of a ground-floor column → its capacity in use, tonnes
    f_ = (sum(C2.factors(b_)) / 2.0) or 1.0
    for c in res_all.get("cards") or []:
        if c["floor"] == 0:
            caps[(round(c["x"], 2), round(c["y"], 2))] = column_capacity(c["spec"], b_) / f_ / 1000.0
    per = 24
    rows = ck["rows"]
    for k in range(0, len(rows), per):
        bk.page("ตรวจน้ำหนักลงเสา (Checkload)", "Checkload")
        bk.text(12, 32, 380, 7, f"น้ำหนักลงเสาชั้นล่างรวม {ck['total'] / 1000:,.1f} ตัน · พื้นที่รับรวม {ck['area']:,.1f} ตร.ม. "
                f"(ทุกชั้น + หลังคา) · เฉลี่ย {ck['mean']:,.0f} กก./ตร.ม. (บ้าน คสล. ทั่วไป {lo:,.0f}–{hi:,.0f})",
                6.0, bold=True)
        tab = [head]
        for r in rows[k:k + per]:
            col = GREEN if r["ok"] and r["note"] == "ปกติ" else ORANGE if r["ok"] else RED
            cap = caps.get((round(r["x"], 2), round(r["y"], 2)))
            use = r["W"] / 1000.0 / cap * 100 if cap else None
            tab.append((r["mark"], f"({r['x']:.2f}, {r['y']:.2f})", f"{r['A']:,.2f}", f"{r['W'] / 1000:,.2f}",
                        f"{r['WA'] / 1000:,.2f}", f"{r['diff']:+.0f}", f"{r['Wf']:,.0f}",
                        f"{cap:,.1f}" if cap else "—",
                        (f"{use:,.0f}", GREEN if use <= 100 else RED) if use is not None else "—", (r["note"], col)))
        y = bk.table(10, 42, [16, 30, 30, 22, 30, 18, 34, 28, 20, 156], tab, 6.6, left=True)
        if k == 0:
            heavy = max(rows, key=lambda r: r["W"])
            cap = caps.get((round(heavy["x"], 2), round(heavy["y"], 2)))
            bk.plain(12, y + 3, 380, [
                "อธิบายง่าย: Wcol คือน้ำหนักจริงที่ลงเสาแต่ละต้น (ตัน) · «เสารับได้» คือน้ำหนักที่เสาต้นนั้นรับได้ "
                "(ไม่รวมค่าความปลอดภัย) · «ใช้ไป %» ไม่เกิน 100 = เสารับได้",
                f"เสาที่รับน้ำหนักมากที่สุด {heavy['mark']} ที่ ({heavy['x']:.2f}, {heavy['y']:.2f}): น้ำหนักที่กระทำ "
                f"{heavy['W'] / 1000:,.1f} ตัน" + (f" · รับได้ {cap:,.1f} ตัน · ใช้กำลังไป {heavy['W'] / 1000 / cap * 100:,.0f} %"
                                                   if cap else "")],
                bool(cap) and heavy["W"] / 1000 <= cap, 5.4)
        bk.text(12, 244, 380, 6, "Wcol = น้ำหนักใช้งานที่ลงเสาจากการคำนวณคาน · Wcol-Area = พื้นที่รับ × ค่าเฉลี่ยทั้งอาคาร · "
                "Wfloor = Wcol ÷ พื้นที่ — ค่าที่ต่างมากแสดงว่ามีน้ำหนักพิเศษหรือข้อมูลผิด ควรตรวจทาน", 5.0)


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
    for the permit). The pages go from the roof down to the piles, with a
    contents page — the book is laid out twice: once to learn where each
    chapter starts, once to write it."""
    import os
    import tempfile
    from core import wanic_calc_cards as CC
    CC.attach_lateral_moments(res_all, data)
    if critical:
        res_all = CC.critical_members(res_all)
    fd, tmp = tempfile.mkstemp(suffix=".pdf")
    os.close(fd)
    try:
        starts = _write(res_all, data, tmp, info, critical, None)
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass
    starts = {k: v + 1 for k, v in starts.items() if k != "_n"}     # the contents page comes in front
    return _write(res_all, data, path, info, critical, starts)["_n"]


def _write(res_all, data, path, info, critical, starts) -> dict:
    b_ = res_all["basis"]
    fc = b_["fc"]
    from core import wanic_calc_cards as CC
    bk = Book(path, info)
    at = {}
    last = []

    def chapter(key=None):
        """A chapter starts on the next page; the one before is dropped when
        it wrote no page (a flat roof, no piles)."""
        if last and bk.n < at[last[-1]]:
            del at[last[-1]]
        if key:
            at[key] = bk.n + 1
            last.append(key)
    cover(bk, res_all)
    if starts is not None:
        contents_page(bk, starts)
    basis_page(bk, b_)
    standards_page(bk)
    # 1 roof: the roof members, the truss, the purlins, the steel frame
    chapter("roof")
    CC.roof_page(bk, res_all)
    if (data or {}).get("truss"):
        from core import wanic_truss as T
        from core.wanic_truss_view import truss_pages
        try:
            tp, td = T.design_of(data)
            truss_pages(bk, tp, td)
        except ValueError:
            pass
    if (data or {}).get("purlin"):
        from core import wanic_purlin as PU
        from core.wanic_purlin_view import purlin_pages
        pp, pr = PU.design_of(data)
        purlin_pages(bk, pp, pr)
    if (data or {}).get("steel"):
        from core import wanic_steel as S
        from core.wanic_steel_view import steel_pages
        steel_pages(bk, S.design_building(data))
    # 2 slabs and stairs
    chapter("slab")
    CC.slab_pages(bk, res_all, data, critical)
    behaviour_pages(bk, [m for m in res_all["members"] if m.group == "slab"], "พฤติกรรมแรง — พื้น", "SlabLoad")
    if (data or {}).get("flatslab"):
        from core import wanic_flatslab as FS
        from core.wanic_flatslab_view import flatslab_pages
        fp, fr = FS.design_of(data)
        flatslab_pages(bk, fp, fr)
    for dz in res_all.get("stairs") or []:
        if not critical or not all(m.ok for m in dz["members"]):
            stair_page(bk, dz, b_)
    # 3 beams, 4 columns, 5 footings, 6 piles
    chapter("beam")
    beam_pages(bk, res_all, b_, fc)
    chapter("column")
    column_pages(bk, res_all, b_, fc)
    chapter("footing")
    CC.footing_pages(bk, res_all, data, critical)
    behaviour_pages(bk, [m for m in res_all["members"] if m.group == "footing"], "พฤติกรรมแรง — ฐานราก",
                    "FootLoad")
    chapter("pile")
    pile_page(bk, data, b_)
    # 7 lateral, 8 summary
    if (data or {}).get("lateral"):
        from core import wanic_lateral as LT
        from core.wanic_lateral_view import lateral_pages
        chapter("lateral")
        lateral_pages(bk, LT.analyse(data))
    ms = res_all["members"]
    chapter("summary")
    list_page(bk, "สรุปผลการตรวจสอบทุกชิ้นส่วน", "Summary", ms)
    reserve_page(bk, ms)
    checkload_page(bk, res_all, data)
    advice_page(bk, res_all, data)
    chapter()
    at["_n"] = bk.n
    bk.close()
    return at
