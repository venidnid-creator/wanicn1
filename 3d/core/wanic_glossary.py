# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
"""คำอธิบายศัพท์ (the owner, 25 พ.ย. 69): every sheet of the survey/road set
explains, in words anyone can follow, the technical terms that appear on
it — a small box in an empty part of the sheet — and one sheet explains
every term of the whole set.

The terms are found from the sheet's own texts (``TERMS``: label, pattern,
meaning). The box goes where nothing is drawn: the sheet's lines, texts and
fills are laid on a grid of 2 mm cells and the box takes the free rectangle
nearest the lower right corner of the drawing area; when no rectangle holds
every term, fewer terms and a pointer to the glossary sheet.
"""
from __future__ import annotations

import math
import re

#: (label, pattern on the sheet's texts, meaning in plain Thai)
TERMS = [
    ("STA / กม.", r"\bSTA\b|กม\. \d+\+|\d\+\d{3}", "ระยะทางจากจุดเริ่มต้นถนน เช่น 0+145.00 = กิโลเมตรที่ 0 บวก 145 เมตร"),
    ("CL", r"\bCL\b|C/L", "เส้นกึ่งกลางถนน (Center Line)"),
    ("BM", r"\bBM\b", "หมุดหลักฐานที่รู้ค่าระดับแน่นอน ใช้อ้างอิงระดับตอนสำรวจและก่อสร้าง"),
    ("MSL / ระดับ รทก.", r"\bMSL\b|ระดับ MSL", "ความสูงเทียบระดับน้ำทะเลปานกลาง หน่วยเมตร"),
    ("E / N", r"\bE \d|\bN \d|ตะวันออก \(E\)|เหนือ \(N\)", "พิกัดบนแผนที่ระบบ UTM: E ไปทางตะวันออก N ไปทางเหนือ หน่วยเมตร"),
    ("UTM / WGS84", r"\bUTM\b|\bWGS", "ระบบพิกัดแผนที่มาตรฐานที่ใช้กับ GPS"),
    ("GNSS / RTK", r"\bGNSS\b|\bRTK\b", "การสำรวจด้วยดาวเทียม (GPS) หาตำแหน่งได้ละเอียดระดับเซนติเมตร"),
    ("PI", r"\bPI\b|PI-\d|PI STA", "จุดที่แนวทางตรงสองเส้นมาตัดกัน (จุดหักของแนว) ถนนจริงโค้งเลี่ยงจุดนี้"),
    ("POT", r"\bPOT\b", "หมุดบนแนวทางตรง ใช้กำหนดแนวถนน"),
    ("PC / PT", r"\bPC\b|\bPT\b", "จุดเริ่มโค้ง / จุดสิ้นสุดโค้ง (ทางตรงต่อกับโค้งที่จุดนี้)"),
    ("R รัศมี", r"\bR\s*=|R \(ม\.\)|\bR \d", "ความกว้างของโค้ง ยิ่งรัศมีมาก โค้งยิ่งกว้าง ขับได้เร็วและปลอดภัย"),
    ("Δ มุมเบี่ยง", r"Δ", "มุมที่ถนนเลี้ยวซ้ายหรือขวา (องศา ลิปดา ฟิลิปดา)"),
    ("L ความยาวโค้ง", r"\bL\s*=|L \(ม\.\)", "ระยะทางตามโค้ง (โค้งราบหรือโค้งดิ่ง)"),
    ("V ความเร็ว", r"\bV\s*=|V \(กม\.", "ความเร็วรถสูงสุดที่ปลอดภัยเมื่อเข้าโค้ง (กม./ชม.)"),
    ("PVI", r"\bPVI\b", "จุดที่ความลาดของถนนเปลี่ยน เช่น จากขึ้นเนินเป็นลงเนิน"),
    ("BVC / EVC", r"\bBVC\b|\bEVC\b", "จุดเริ่ม / จุดสิ้นสุดโค้งดิ่ง"),
    ("โค้งคว่ำ / หงาย", r"Crest|Sag|โค้งคว่ำ|โค้งหงาย", "โค้งบนยอดเนิน (Crest) / โค้งในท้องแอ่ง (Sag)"),
    ("G / ความลาด %", r"[+-]\d+\.\d+%|\bg1\b|\bG\s*=", "ความลาดของถนน เช่น +0.89% คือสูงขึ้น 0.89 ม. ทุก 100 ม. (ลบคือลง)"),
    ("K", r"\bK\s*=|\bK\b", "ความยาวโค้งดิ่งต่อความลาดที่เปลี่ยน 1% ยิ่งมากยิ่งขับนุ่มนวล"),
    ("ระดับดินเดิม", r"ระดับดินเดิม|ระดับดิน\b", "ระดับพื้นดินตามธรรมชาติที่สำรวจได้ก่อนก่อสร้าง"),
    ("ระดับออกแบบ", r"ระดับออกแบบ", "ระดับผิวถนนที่จะก่อสร้าง"),
    ("CT / CR", r"\bCT\b|\bCR\b", "CT = ระดับดินเดิมที่กึ่งกลางถนน · CR = ระดับผิวถนนที่ออกแบบที่กึ่งกลาง"),
    ("C.R. หลังเต่า", r"C\.R\.|หลังเต่า", "ความลาดผิวถนนจากกึ่งกลางลงสองข้าง ให้น้ำฝนไหลออก"),
    ("ดินขุด / ดินถม", r"ขุด|ถม", "ดินขุด = ส่วนที่ต้องตักออก · ดินถม = ส่วนที่ต้องเอาดินมาเติมให้ถึงระดับ"),
    ("ปริมาตรสะสม", r"สะสม", "ผลรวมปริมาตรดินจากจุดเริ่มต้นถึงสถานีนั้น ใช้วางแผนขนดิน"),
    ("Prismoidal", r"Prismoidal", "วิธีคำนวณปริมาตรดินระหว่างรูปตัดสองรูปที่ละเอียดกว่าวิธีเฉลี่ยพื้นที่"),
    ("ไหล่ทาง", r"ไหล่ทาง", "ส่วนข้างผิวจราจร ให้รถจอดฉุกเฉินและรองรับขอบถนน"),
    ("ลาด 1:n", r"(?<![\d.])1\s*:\s*\d(\.\d+)?(?![\d,])", "ความลาดของคันดิน เช่น 1:2 คือสูง 1 ม. ต่อระยะราบ 2 ม."),
    ("ชั้นทาง", r"Base|Subbase|พื้นทาง|รองพื้นทาง|Surface", "ชั้นวัสดุที่ซ้อนกันใต้ผิวถนน: ผิวทาง (Surface) พื้นทาง (Base) รองพื้นทาง (Subbase)"),
    ("AC", r"\bAC\b|A\.C\.|Asphalt", "ผิวถนนลาดยางแอสฟัลต์คอนกรีต"),
    ("PRIME / TACK COAT", r"PRIME|TACK", "ยางที่ราดก่อนปูผิว ให้ชั้นทางยึดติดกัน"),
    ("CBR", r"\bCBR\b", "ค่าความแข็งแรงของดิน ยิ่งมากยิ่งรับน้ำหนักได้ดี"),
    ("PROCTOR", r"PROCTOR|DENSITY", "การทดสอบหาความแน่นของดินบดอัด ใช้ตรวจงานบดอัด"),
    ("SE ยกโค้ง", r"\bSE\b|ยกโค้ง|\be \(%\)", "การยกขอบนอกโค้งให้สูงกว่าขอบใน ช่วยให้รถเข้าโค้งได้มั่นคง"),
    ("NC / FULL SE", r"\bNC\b|FULL SE", "NC = จุดเริ่มเปลี่ยนจากหลังเต่าปกติ · FULL SE = ช่วงที่ยกโค้งเต็มที่"),
    ("Lt / Lr", r"\bLt\b|\bLr\b", "ระยะที่ใช้ค่อยๆ เปลี่ยนความลาดผิวถนนก่อนเข้าโค้ง"),
    ("W ขยายผิว", r"\bW \(ม\.\)|ขยายผิว", "ความกว้างผิวจราจรที่เพิ่มในโค้ง ให้รถใหญ่เลี้ยวได้"),
    ("Rmin", r"Rmin", "รัศมีโค้งที่เล็กที่สุดที่ปลอดภัยตามความเร็วออกแบบ"),
    ("ADT", r"\bADT\b", "ปริมาณรถเฉลี่ยต่อวัน (คัน/วัน)"),
    ("Ø ท่อ", r"Ø", "ขนาดเส้นผ่านศูนย์กลาง"),
    ("Hc", r"\bHc\b", "ความหนาดินถมเหนือหลังท่อ"),
    ("Q", r"\bQ \(", "ปริมาณน้ำที่ท่อระบายได้ (ลบ.ม. ต่อวินาที)"),
    ("Manning n", r"Manning", "ค่าความขรุขระของผิวท่อ ใช้คำนวณการไหลของน้ำ"),
    ("GUARD RAIL", r"GUARD RAIL", "ราวกันอันตรายเหล็กข้างทาง กันรถตกถนน"),
    ("GUIDE POST", r"GUIDE POST", "หลักนำทางข้างโค้ง ช่วยให้เห็นแนวโค้งตอนกลางคืน"),
    ("THERMOPLASTIC", r"THERMOPLASTIC", "สีตีเส้นจราจรชนิดหลอมร้อน ทนทานและสะท้อนแสง"),
    ("ทถ- / ทล-", r"ทถ-|ทล-", "เลขแบบมาตรฐานของกรมทางหลวงชนบท / กรมทางหลวง"),
    ("ไร่-งาน-ตร.ว.", r"ไร่", "หน่วยพื้นที่ที่ดิน: 1 ไร่ = 4 งาน = 1,600 ตร.ม. · 1 งาน = 100 ตร.ว. = 400 ตร.ม. · 1 ตร.ว. = 4 ตร.ม."),
    ("เลขที่ดิน", r"เลขที่ดิน", "เลขประจำแปลงในระวางของกรมที่ดิน (ไม่ใช่เลขโฉนด) ใช้ค้นแปลงใน LandsMaps"),
    ("มาตราส่วน 1:n", r"มาตราส่วน|1:\d{2,}", "ขนาดในแบบเทียบกับของจริง เช่น 1:1000 คือ 1 มม. ในแบบเท่ากับ 1 ม."),
]

CELL = 2.0          # mm
LINE_H = 3.6        # mm per line in the box
TEXT_H = 1.8
TITLE = "คำอธิบายศัพท์"


def terms_in(texts) -> list:
    """[(label, meaning)] of the terms that appear in ``texts``, in TERMS order."""
    blob = "\n".join(str(t) for t in texts)
    return [(lab, mean) for lab, pat, mean in TERMS if re.search(pat, blob)]


# -- where nothing is drawn ------------------------------------------------------------------

def _text_box(it):
    (x, y), s, h, align = it[1], it[2], it[3], it[4]
    w = len(s) * h * 0.62
    ang = math.radians(it[7] if len(it) > 7 else 0.0)
    x0 = x - (w if align == "right" else w / 2 if align == "center" else 0.0)
    pts = [(x0, y - h * 0.3), (x0 + w, y - h * 0.3), (x0 + w, y + h * 1.1), (x0, y + h * 1.1)]
    if abs(ang) > 1e-6:
        c, s_ = math.cos(ang), math.sin(ang)
        pts = [(x + (px - x) * c - (py - y) * s_, y + (px - x) * s_ + (py - y) * c) for px, py in pts]
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


def occupied(sheet, area) -> set:
    """The 2 mm cells of ``area`` that something on the sheet touches."""
    x0, y0, x1, y1 = area
    nx, ny = int((x1 - x0) / CELL) + 1, int((y1 - y0) / CELL) + 1
    busy = set()

    def box(a, b, c, d, pad=0.6):
        i0, i1 = int((min(a, c) - pad - x0) // CELL), int((max(a, c) + pad - x0) // CELL)
        j0, j1 = int((min(b, d) - pad - y0) // CELL), int((max(b, d) + pad - y0) // CELL)
        for i in range(max(i0, 0), min(i1, nx - 1) + 1):
            for j in range(max(j0, 0), min(j1, ny - 1) + 1):
                busy.add((i, j))

    def seg(a, b):
        n = max(1, int(math.hypot(b[0] - a[0], b[1] - a[1]) / (CELL / 2)))
        for k in range(n + 1):
            t = k / n
            p = (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
            box(p[0], p[1], p[0], p[1])
    for it in sheet.items:
        kind = it[0]
        if kind == "line":
            x_, y_, u, v = it[1]
            seg((x_, y_), (u, v))
        elif kind == "poly":
            pts = it[1]
            closed = it[4] if len(it) > 4 else True
            for a, b in zip(pts, pts[1:] + (pts[:1] if closed else [])):
                seg(a, b)
        elif kind == "rect":
            a, b, c, d = it[1]
            for p, q in (((a, b), (c, b)), ((c, b), (c, d)), ((c, d), (a, d)), ((a, d), (a, b))):
                seg(p, q)
        elif kind in ("fill",):
            xs, ys = [p[0] for p in it[1]], [p[1] for p in it[1]]
            box(min(xs), min(ys), max(xs), max(ys), 0.2)
        elif kind == "image":
            box(*it[1], 0.2)
        elif kind == "circle":
            cx, cy, r = it[1]
            box(cx - r, cy - r, cx + r, cy + r)
        elif kind == "arc":
            cx, cy, r = it[1][:3]
            box(cx - r, cy - r, cx + r, cy + r)
        elif kind == "text":
            box(*_text_box(it))
    return busy


def free_spot(sheet, w, h, area, busy=None):
    """The lower-left corner of a free ``w`` × ``h`` mm rectangle in ``area``,
    the one nearest the lower right corner; None when there is none."""
    x0, y0, x1, y1 = area
    busy = occupied(sheet, area) if busy is None else busy
    nx, ny = int((x1 - x0) / CELL), int((y1 - y0) / CELL)
    cw, ch = int(math.ceil(w / CELL)) + 1, int(math.ceil(h / CELL)) + 1
    if cw > nx or ch > ny:
        return None
    # the free run upwards from every cell, then rectangles by columns
    up = [[0] * ny for _ in range(nx)]
    for i in range(nx):
        run = 0
        for j in range(ny - 1, -1, -1):
            run = run + 1 if (i, j) not in busy else 0
            up[i][j] = run                       # free cells from j upwards
    best = None
    for j in range(0, ny - ch + 1):
        width = 0
        for i in range(nx - 1, -1, -1):           # from the right
            width = width + 1 if up[i][j] >= ch else 0
            if width >= cw:
                cand = (x0 + i * CELL + CELL / 2, y0 + j * CELL + CELL / 2)
                score = (x1 - (cand[0] + w)) + (cand[1] - y0)        # near the lower right
                if best is None or score < best[0]:
                    best = (score, cand)
                break
    return best[1] if best else None


def _wrap(text, n):
    from core import wanic_drawings as D
    return D._wrap(text, n)


def add_box(sheet, terms, area, ref: str = "", width: float = 118.0) -> int:
    """The box of ``terms`` in the first free spot; as many terms as fit
    (then «ดูทั้งหมดที่แผ่น ref»). Returns the terms shown."""
    if not terms:
        return 0
    busy = occupied(sheet, area)
    label_w = 30.0
    chars = int((width - label_w - 4) / (TEXT_H * 0.62))

    def lines_of(ts):
        return [(lab, _wrap(mean, chars)) for lab, mean in ts]
    for n in range(len(terms), 0, -1):
        rows = lines_of(terms[:n])
        more = n < len(terms) and ref
        h = 6.5 + sum(len(r[1]) for r in rows) * LINE_H + (LINE_H if more else 0) + 1.5
        spot = free_spot(sheet, width, h, area, busy)
        if spot is None:
            continue
        x, y = spot
        top = y + h
        sheet.rect(x, y, x + width, top, "text", 0.18)
        sheet.glossary_box = (x, y, x + width, top)
        sheet.text((x + 2, top - 4.6), TITLE + " (สำหรับผู้อ่านทั่วไป)", 2.2, "left", "text", True)
        yy = top - 4.6 - LINE_H - 0.6
        for lab, parts in rows:
            sheet.text((x + 2, yy), lab, TEXT_H, "left", "text", True)
            for k, t in enumerate(parts):
                sheet.text((x + label_w, yy), t, TEXT_H, "left", "text")
                yy -= LINE_H
        if more:
            sheet.text((x + 2, yy), f"ศัพท์อื่นดูที่แผ่น {ref} (คำอธิบายศัพท์ทั้งชุดแบบ)", TEXT_H, "left", "dim")
        sheet.glossary = [t[0] for t in terms[:n]]
        return n
    # not even one fits: the sheet is full — the line in the page's bottom
    # margin (beside «จัดทำด้วย WANICNSURVEY»), never over the drawing
    if ref:
        from core import wanic_drawings as D
        sheet.text((D.PAPER[0] / 2, D.MARGIN - 4.5),
                   f"คำอธิบายศัพท์ในแผ่นนี้ (สำหรับผู้อ่านทั่วไป) ดูที่แผ่น {ref}", TEXT_H, "center", "dim")
    sheet.glossary = []
    return 0


def glossary_sheet(D, sheets, code: str = "G-03"):
    """The sheet that explains every term of the set, with the sheets it is on."""
    used = {}
    for s in sheets:
        for lab, mean in terms_in(s.texts()):
            used.setdefault(lab, [mean, []])[1].append(s.code)
    g = D.Sheet(code, "คำอธิบายศัพท์ทั้งชุดแบบ", "-", "G")
    X0, Y0, X1, Y1 = D.drawing_area()
    g.text((X0, Y1 - 3), "คำอธิบายศัพท์ทั้งชุดแบบ (สำหรับผู้อ่านทั่วไป)", 3.4, "left", "text", True)
    g.text((X0, Y1 - 9), "ศัพท์ช่างและอักษรย่อที่พบในแบบชุดนี้ อธิบายเป็นภาษาง่าย พร้อมแผ่นที่พบ "
           "ให้เจ้าของงาน ผู้รับเหมา และประชาชนเข้าใจตรงกัน", 2.2)
    rows = []
    for lab, pat, mean in TERMS:
        if lab in used:
            codes = used[lab][1]
            where = ", ".join(sorted(set(c.split("-")[0] for c in codes)))
            rows.append((lab, mean, where))
    col_w = (X1 - X0 - 8) / 2
    per = 0
    x, y = X0, Y1 - 16
    for lab, mean, where in rows:
        parts = _wrap(mean, int((col_w - 34) / (2.0 * 0.62)))
        need = len(parts) * 4.0 + 1.6
        if y - need < Y0 + 4:
            if x > X0:
                break
            x, y = X0 + col_w + 8, Y1 - 16
        g.text((x, y), lab, 2.0, "left", "text", True)
        for k, t in enumerate(parts):
            g.text((x + 32, y), t, 2.0)
            y -= 4.0
        g.text((x + 32, y + 0.9), f"พบในแผ่น {where}", 1.6, "left", "dim")
        y -= 2.6
        per += 1
    return g, per
