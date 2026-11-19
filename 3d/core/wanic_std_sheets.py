# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
"""The architecture sheets laid out like the standard house drawing sets
(the sheet order, the three-panel A-01 and the A-02 specification text);
written from the published standard, drawn by this program — the title
column stays the program's own.

* :func:`a_index` — A-01 «สารบัญแบบ รายการวัสดุ»: the A sheet list, the
  material list by code (floor □, wall △, ceiling ○, skirting, cornice,
  roof) and the drawing symbols with the material hatches.
* :func:`a_spec` — A-02 «รายการประกอบแบบ»: the general specification
  (purpose, layout and levels, floors, walls, ceilings, roof, doors and
  windows, bathrooms, painting, structure, sanitary, electrical), with the
  building data, the storey rules and the abbreviations.
"""
from __future__ import annotations

from core import wanic_building as B
from core import wanic_catalog as CAT
from core import wanic_drawings as D

ROW = 6.2                     # the standard's ruled row (mm on A3)
HEAD = 8.0


def _panel(sh, x, y0, y1, w, title, cols):
    """A full-height ruled panel: title band, column heads, empty rows to
    the bottom (as the standard draws them). Returns (row tops, xs)."""
    sh.rect(x, y0, x + w, y1, "text", 0.35)
    sh.line((x, y1 - HEAD), (x + w, y1 - HEAD), "text", 0.35)
    sh.text((x + w / 2, y1 - HEAD + 2.6), title, 3.2, "center", "text", True)
    yh = y1 - HEAD
    xs, cx = [], x
    for head, cw in cols:
        xs.append(cx)
        sh.text((cx + cw / 2, yh - ROW + 2.0), head, 2.2, "center", "text")
        cx += cw
    xs.append(x + w)
    sh.line((x, yh - ROW), (x + w, yh - ROW), "text", 0.25)
    tops, y = [], yh - ROW
    while y - ROW >= y0 - 0.01:
        tops.append(y)
        y -= ROW
        sh.line((x, y), (x + w, y), "text", 0.13)
    for cx in xs[1:-1]:
        sh.line((cx, y0), (cx, yh), "text", 0.18)
    return tops, xs


def _floor_mark(sh, p, n):
    sh.rect(p[0] - 1.9, p[1] - 1.9, p[0] + 1.9, p[1] + 1.9, "text", 0.25)
    sh.text((p[0], p[1] - 0.8), str(n), 2.0, "center", "text", True)


def _ceiling_mark(sh, p, n):
    sh.circle(p, 2.1, "text", 0.25)
    sh.text((p[0], p[1] - 0.8), str(n), 2.0, "center", "text", True)


def material_rows(E, fcodes):
    """[(kind, number|None, text)] — the materials by group as the
    standard lists them; kind: head / floor / wall / ceil / text."""
    s = E["settings"]
    out = [("head", None, "พื้น")]
    for code, (tag, name) in fcodes.items():
        name = name.split(" (รวม")[0]
        out.append(("floor", int(tag[1:]) if tag[1:].isdigit() else tag, name))
    out.append(("head", None, "ผนัง"))
    for n, text in D.WALL_TYPES.items():
        out.append(("wall", n, text))
    out.append(("head", None, "ฝ้าเพดาน"))
    for i, (key, (name, _lab, _fr, _sub, main)) in enumerate(B.CEILING_TYPES.items(), 1):
        out.append(("ceil", i, f"{name} [แขวน @{main:.2f} ม.]"))
    out.append(("ceil", len(B.CEILING_TYPES) + 1,
                "ฝ้าชายคา ระแนงไม้เทียมเว้นร่อง กรุมุ้งกันแมลง โครงคร่าวซีลาย [ฝ้าภายนอก]"))
    out.append(("text", None, "  * เหนือฝ้าเพดานใต้หลังคา ปูฉนวนกันความร้อนใยแก้ว หนา 3\" "
                              "หุ้มฟอยล์อลูมิเนียม"))
    out.append(("head", None, "บัวเชิงผนัง"))
    sk = B.SKIRTING_TYPES.get(s.get("skirting_type", "ceramic"), B.SKIRTING_TYPES["ceramic"])[0]
    out.append(("text", "FB1", f"{sk} [ห้องทั่วไป ยกเว้นห้องน้ำ]"))
    out.append(("head", None, "มอบฝ้าเพดาน"))
    out.append(("text", "CB1", f"{B.CORNICE[0]} ทาสี [ทุกห้องที่มีฝ้าเพดาน]"))
    out.append(("head", None, "หลังคา"))
    if E["settings"].get("roof", "none") != "none":
        tile = CAT.roof_tile(s)[1]["name"]
        out.append(("text", "R1", f"{tile} ลาด {float(s.get('pitch') or 0):.0f} องศา"))
        out.append(("text", "", "ติดตั้งตามมาตรฐานผู้ผลิต มุงเรียงตามที่ปรากฏในแบบ"))
    else:
        out.append(("text", "R1", "หลังคาดาดฟ้า คสล. ทำระบบกันซึม ลาดเอียง 1:100 สู่ท่อระบายน้ำ"))
    return out


def a_index(sh, sheets, E, fcodes):
    """A-01 «สารบัญแบบ รายการวัสดุ» in the standard's three panels."""
    x0, y0, x1, y1 = D.drawing_area()
    w1, w2 = 82.0, 128.0
    w3 = x1 - x0 - w1 - w2
    # 1 — the A sheet list
    tops, xs = _panel(sh, x0, y0, y1, w1, "รายการแบบสถาปัตยกรรม (A)",
                      [("เลขที่", 15.0), ("แบบแสดง", w1 - 15.0)])
    rows = [(s.code, s.title) for s in sheets if s.group == "A"]
    for top, (code, title) in zip(tops, rows):
        sh.text((xs[0] + 7.5, top - ROW + 2.0), code, 2.2, "center")
        sh.text((xs[1] + 1.5, top - ROW + 2.0), D._wrap(title, 40)[0], 2.2)
    # 2 — the material list
    x2 = x0 + w1
    tops, xs = _panel(sh, x2, y0, y1, w2, "รายการวัสดุ",
                      [("สัญลักษณ์", 18.0), ("รายการ", w2 - 18.0)])
    lines = []
    for kind, n, text in material_rows(E, fcodes):
        parts = D._wrap(text, 78)
        lines.append((kind, n, parts[0]))
        lines += [("text", None, "      " + p) for p in parts[1:]]
    for top, (kind, n, text) in zip(tops, lines):
        cy, sx = top - ROW / 2, xs[0] + 9.0
        by = top - ROW + 2.0
        if kind == "head":
            sh.text((sx, by), text, 1.95, "center", "text", True)
            continue
        if kind == "floor":
            _floor_mark(sh, (sx, cy), n)
        elif kind == "wall":
            D.wall_tag(sh, (sx, cy - 0.6), n, 1.9)
        elif kind == "ceil":
            _ceiling_mark(sh, (sx, cy), n)
        elif n:
            sh.text((sx, by), str(n), 2.1, "center")
        sh.text((xs[1] + 2, by), text, 2.2)
    # 3 — the drawing symbols
    symbols(sh, x2 + w2, y0, y1, w3)


def symbols(sh, x, y0, y1, w):
    """«รายการสัญลักษณ์ประกอบแบบ» as the standard draws it."""
    sh.rect(x, y0, x + w, y1, "text", 0.35)
    sh.line((x, y1 - HEAD), (x + w, y1 - HEAD), "text", 0.35)
    sh.text((x + w / 2, y1 - HEAD + 2.6), "รายการสัญลักษณ์ประกอบแบบ", 3.2, "center", "text", True)
    sx, tx = x + 22, x + 50
    y = y1 - HEAD
    F = max(1.0, min(1.8, (y1 - HEAD - y0) / 156.0))
    sizes = iter([30, 9, 9, 11, 15, 19, 13, 10, 10, 10, 10])

    def pre():
        nonlocal y, cur
        cur = next(sizes)
        y -= 6 + cur * (F - 1) / 2 if cur == 30 else cur * (F - 1) / 2

    def rule(_dy):
        nonlocal y
        y -= cur + cur * (F - 1) / 2
        sh.line((x, y + 3), (x + w, y + 3), "text", 0.13)
    cur = 0
    pre()

    # grid dimensions
    gx = x + 12
    sh.circle((gx, y - 9), 3.0, "grid", 0.25)
    sh.text((gx, y - 9.9), "1", 2.4, "center", "grid")
    sh.line((gx, y - 6), (gx, y - 26), "grid", 0.13, True)
    sh.circle((gx - 6, y - 19), 2.8, "grid", 0.25)
    sh.text((gx - 6, y - 19.9), "A", 2.2, "center", "grid")
    sh.line((gx - 3.2, y - 19), (gx + 8, y - 19), "grid", 0.13, True)
    sh.text((gx + 3, y - 23), "แนวเสา", 2.0)
    for i, (txt, ends) in enumerate((("ระยะศูนย์กลางถึงศูนย์กลาง", "cc"),
                                     ("ระยะศูนย์กลางถึงริม", "ce"),
                                     ("ระยะจากริมถึงริม", "ee"))):
        yy = y - 2 - i * 9
        a, b = x + 30, x + 50
        sh.line((a, yy), (b, yy), "dim", 0.18)
        for t, kind in ((a, ends[0]), (b, ends[1])):
            sh.line((t, yy - 2), (t, yy + 2), "dim", 0.18)
            if kind == "c":
                sh.line((t - 1, yy - 1), (t + 1, yy + 1), "dim", 0.3)
            else:
                sh.circle((t, yy), 0.5, "dim", 0.18)
        sh.text((b + 3, yy - 0.8), txt, 2.1)
    rule(30)
    pre()
    # door / window tags
    sh.text((sx, y - 0.8 - 2), "ป1", 2.4, "center", "door", True)
    sh.text((tx - 8, y - 2.8), "ใช้กำหนดหมายเลขประตู ในแบบเพื่ออ้างอิงถึง", 2.1)
    rule(9)
    pre()
    hex_tag(sh, (sx, y - 2), "น1", 2.4)
    sh.text((tx - 8, y - 2.8), "ใช้กำหนดหมายเลขหน้าต่าง ในแบบเพื่ออ้างอิงถึง", 2.1)
    rule(9)
    pre()
    # detail reference
    sh.circle((sx - 6, y - 3), 3.2, "text", 0.25)
    sh.line((sx - 9.2, y - 3), (sx - 2.8, y - 3), "text", 0.18)
    sh.text((sx - 6, y - 2.2), "1", 1.8, "center")
    sh.text((sx - 6, y - 5.3), "A-NO", 1.4, "center")
    sh.line((sx - 2.8, y - 3), (sx + 10, y - 3), "text", 0.18)
    sh.text((tx - 8, y - 1.6), "แบบขยายทั่วไป", 2.1)
    sh.text((tx - 8, y - 5.0), "แผ่นที่ ที่อ้างอิงไปถึง", 2.1)
    rule(11)
    pre()
    # north
    D.north(sh, (sx, y - 7.5), 4.5)
    sh.text((tx - 8, y - 6.8), "ทิศเหนือ", 2.1)
    rule(15)
    pre()
    # elevation key
    cx, cy, r = sx, y - 9, 4.0
    sh.poly([(cx, cy + r * 1.6), (cx + r * 1.6, cy), (cx, cy - r * 1.6), (cx - r * 1.6, cy)], "text", 0.25)
    sh.circle((cx, cy), r, "text", 0.25)
    for (dx, dy), lab in (((0, 1), "3"), ((1, 0), "4"), ((0, -1), "1"), ((-1, 0), "2")):
        tip = (cx + dx * r * 1.6, cy + dy * r * 1.6)
        nx, ny = -dy, dx
        sh.fill([tip, (cx + dx * r * 0.9 + nx * 2.2, cy + dy * r * 0.9 + ny * 2.2),
                 (cx + dx * r * 0.9 - nx * 2.2, cy + dy * r * 0.9 - ny * 2.2)], "hatch", 0.0)
        sh.text((cx + dx * (r + 4.3), cy + dy * (r + 4.3) - 0.8), lab, 1.9, "center", "text", True)
    sh.text((tx - 8, y - 7.6), "1,2,3,4 ชื่อรูปด้าน แสดงทิศทางตามแนวชี้บอก", 2.1)
    sh.text((tx - 8, y - 11.0), "A-NO.  แผ่นที่ ที่อ้างอิงไปถึง", 2.1)
    rule(19)
    pre()
    # section mark
    for k, sx_ in enumerate((sx - 8, sx + 8)):
        sh.circle((sx_, y - 4), 3.0, "text", 0.25)
        sh.fill([(sx_ - 3, y - 3.2), (sx_ + 3, y - 3.2), (sx_, y + 1.2)], "hatch", 0.0)
        sh.line((sx_ - 3, y - 4), (sx_ + 3, y - 4), "text", 0.18)
        sh.text((sx_, y - 6.6), "A-NO.", 1.3, "center")
    sh.line((sx - 5, y - 4), (sx + 5, y - 4), "text", 0.3, True)
    sh.text((tx - 8, y - 2.2), "ชื่อรูปตัดอาคาร", 2.1)
    sh.text((tx - 8, y - 5.6), "แผ่นที่ ที่อ้างอิงไปถึง", 2.1)
    rule(13)
    pre()
    # hatches, two per row like the standard
    pairs = [("brick", "ผนังก่ออิฐครึ่งแผ่น", "glasswall", "ผนังกระจก"),
             ("conc", "คอนกรีต", "glass", "กระจก"),
             ("steel", "เหล็ก", "soil", "ดิน"),
             ("wood", "ไม้แต่งผิว", "slope", "แนวเรียงลาด")]
    for k1, t1, k2, t2 in pairs:
        for i, (kind, txt) in enumerate(((k1, t1), (k2, t2))):
            bx = x + 4 + i * w / 2
            hatch(sh, kind, bx, y - 6, bx + 16, y - 1)
            sh.text((bx + 19, y - 4.4), txt, 2.1)
        rule(10)
        if (k1, t1) != pairs[-1][:2]:
            pre()


def hatch(sh, kind, a, b, c, d):
    """A material swatch in the box (a, b)–(c, d)."""
    if kind == "slope":
        sh.text((a, b + 1.4), "SLOPE 1:100", 1.8)
        sh.line((a, b + 0.8), (c, b + 0.8), "text", 0.18)
        sh.line((c - 1.5, b + 2.0), (c, b + 0.8), "text", 0.18)
        return
    if kind == "brick":
        sh.line((a, b), (c, b), "wall", 0.3)
        sh.line((a, d), (c, d), "wall", 0.3)
        for i in range(8):
            t = a + i * (c - a) / 8
            sh.line((t, b), (t + 2.0, d), "hatch", 0.13)
        return
    if kind == "glasswall":
        for yy in (b + 1.5, d - 1.5):
            sh.line((a, yy), (c, yy), "wall", 0.25)
        sh.line((a, (b + d) / 2), (c, (b + d) / 2), "hatch", 0.13)
        return
    sh.rect(a, b, c, d, "text", 0.18)
    if kind == "conc":
        for px, py in ((0.2, 0.3), (0.45, 0.7), (0.7, 0.35), (0.85, 0.75), (0.32, 0.8), (0.6, 0.15)):
            q = (a + px * (c - a), b + py * (d - b))
            sh.poly([q, (q[0] + 0.9, q[1] + 0.3), (q[0] + 0.3, q[1] + 0.8)], "hatch", 0.13)
    elif kind == "glass":
        sh.line((a + 6, b + 1), (a + 9, d - 1), "hatch", 0.13)
        sh.line((a + 8, b + 1), (a + 11, d - 1), "hatch", 0.13)
    elif kind == "steel":
        for i in range(9):
            t = a + i * (c - a) / 9
            sh.line((t, b), (min(t + 2.5, c), d), "hatch", 0.18)
    elif kind == "soil":
        for i in range(6):
            t = a + i * (c - a) / 6
            sh.line((t, b), (min(t + 2.6, c), d), "hatch", 0.13)
            sh.line((min(t + 2.6, c), b), (t, d), "hatch", 0.13)
    elif kind == "wood":
        for f in (0.3, 0.55, 0.8):
            yy = b + f * (d - b)
            sh.poly([(a + 1, yy), (a + 5, yy + 0.6), (a + 9, yy - 0.4), (c - 1, yy + 0.3)], "hatch", 0.13,
                    closed=False)


#: รายการประกอบแบบ — general specification (the standard sets' A-02,
#: worded for any house this program draws)
SPEC = [
    ("1.", "วัตถุประสงค์", [
        "แบบชุดนี้จัดทำเพื่อใช้ประกอบการขออนุญาตก่อสร้างและการก่อสร้างอาคารพักอาศัย "
        "ผู้รับจ้างต้องก่อสร้างให้ถูกต้องตามแบบและรายการประกอบแบบ และกฎหมายควบคุมอาคาร"]),
    ("2.", "รายละเอียดประกอบแบบ", []),
    ("2.1", "การวางผังและระดับ", [
        "ผู้รับจ้างจะต้องทำการวางผังบริเวณให้ถูกต้องเรียบร้อยตามกฎหมายควบคุมอาคาร "
        "และกำหนดระดับของอาคารและระดับพื้นที่ก่อสร้างต้องมีความลาดเอียง "
        "เพื่อการระบายน้ำตามรูปแบบรายการที่กำหนด ก่อนดำเนินการต่อไป"]),
    ("2.2", "งานสถาปัตยกรรม", []),
    ("ก.", "งานพื้น", [
        "- พื้น ค.ส.ล. ทำผิวขัดมันเรียบ หรือผิวขัดหยาบ ให้แต่งระดับผิว ค.ส.ล. ด้วยปูนทราย"
        "ให้เรียบสม่ำเสมอ หรือมีความลาดเอียงไปสู่ด้านนอกอาคาร",
        "- พื้น ค.ส.ล. ปูกระเบื้องเซรามิค ผิวด้าน ขนาดตามแบบระบุ พื้นห้องน้ำใช้กระเบื้องเซรามิค"
        "ผิวด้าน ตาม มอก. 2508-2555 น้ำยากันซึม ใช้ของที่ผลิตในประเทศ",
        "- พื้นไม้ ใช้ไม้เนื้อแข็ง ตีเข้าลิ้น อบแห้ง อัดสนิท ขัดให้เรียบแล้วเคลือบด้วยน้ำยาเคลือบเงาไม้",
        "หมายเหตุ การเตรียมผิวพื้นและการปูกระเบื้องให้ทำตามมาตรฐานวิชาช่างที่ดี"]),
    ("ข.", "งานผนัง", [
        "- ผนังทั่วไปก่ออิฐมอญครึ่งแผ่น อิฐต้องเป็นอิฐที่แกร่ง เผาสุกเสมอ ไม่บิดเบี้ยว "
        "ต้องพรมน้ำให้ชุ่มก่อนก่อ",
        "- การก่อชนคาน เสา หรือเอ็น ค.ส.ล. ต้องเสียบเหล็ก RB6 มม. ทุกระยะไม่เกิน 40 ซม. "
        "โดยยื่นออกมา 25 ซม. และฝังในเสาหรือคาน ค.ส.ล. 10 ซม.",
        "- การก่อชนกันเป็นมุม การก่อเว้นช่องสำหรับติดตั้งประตูหน้าต่าง และทุกระยะที่เกิน 2 เมตร "
        "ของความสูงผนัง และทุกระยะที่เกิน 3 เมตร ของความยาวผนัง ให้ทำเอ็น หรือทับหลัง ค.ส.ล. "
        "หนาเท่าผนังที่ก่อสร้างและกว้าง 10 ซม. เสริมเหล็ก 2-RB6 มม. และมีปลอกเหล็ก RB6 @0.20 ม.",
        "- ผนังบุกระเบื้องเซรามิค ขนาดตามแบบรายการที่ระบุ ใช้กระเบื้องดินเผาเคลือบชนิดบุผนังภายใน "
        "ตาม มอก. 2508-2555"]),
    ("ค.", "งานฝ้าเพดาน", [
        "- ให้ใช้ฝ้าเพดานตามรูปแบบรายการที่ระบุ",
        "- ใช้โครงคร่าวเหล็กชุบสังกะสี สำหรับยึดแผ่นฝ้า ตาม มอก. 863-2532 ติดตั้งตามมาตรฐานผู้ผลิต"]),
    ("ง.", "งานหลังคา", [
        "- โครงหลังคา ตามที่ได้กำหนดไว้ในรูปแบบและรายการวิศวกรรมโครงสร้าง",
        "- วัสดุหลังคา ตามรายการวัสดุ (R1) ติดตั้งตามมาตรฐานผู้ผลิต"]),
    ("จ.", "งานประตู-หน้าต่าง และอุปกรณ์", [
        "- รายละเอียดตามระบุในแบบขยายประตู-หน้าต่าง และอุปกรณ์",
        "- ประตู-หน้าต่างอลูมิเนียม ใช้อลูมิเนียม ตาม มอก. 284-2530 เคลือบผิวด้วยสีผง "
        "POLAR POWDER COAT POLYESTER",
        "- ประตูบานเปิดทั่วไปใช้บานพับประตู ผลิตภัณฑ์ ตาม มอก. 759-2531 ขนาด 4x3\" บานละ 3 จุด "
        "ติดตั้งตามกรรมวิธีผู้ผลิต",
        "- กลอนทั่วไปใช้กลอนโลหะชุบโครเมียม ผลิตภัณฑ์ภายในประเทศ",
        "- กุญแจลูกบิดทั่วไป ใช้แบบลิ้นคู่ ล็อคได้ ผิว SATIN CHROME ประเภท STANDARD DUTY "
        "ผลิตภัณฑ์ภายในประเทศ"]),
    ("ฉ.", "งานห้องน้ำ-ส้วม และสุขภัณฑ์", [
        "- รายละเอียดตามระบุในแบบขยายห้องน้ำ-ส้วม สุขภัณฑ์ และอุปกรณ์ประกอบ",
        "- การเดินท่อน้ำประปา-ท่อน้ำทิ้ง-ท่อส้วม ให้เป็นไปตามรูปแบบและรายการวิศวกรรมสุขาภิบาล"]),
    ("ช.", "งานสี", [
        "- งานทาสีผนังคอนกรีต-ปูนภายนอก: สีรองพื้น ใช้สีรองพื้นสำหรับปูนใหม่ ผลิตภัณฑ์เดียวกับสีทับหน้า "
        "สีทับหน้า ใช้สีอะครีลิค 100% กึ่งเงากึ่งด้านสำหรับทาภายนอก ตาม มอก. 2321-2549",
        "- งานทาสีผนังคอนกรีต-ปูนภายใน: สีรองพื้น ใช้สีรองพื้นสำหรับปูนใหม่ ผลิตภัณฑ์เดียวกับสีทับหน้า "
        "สีทับหน้า ใช้สีอะครีลิค 100% สำหรับทาภายใน ตาม มอก. 272-2549 เกรด A",
        "- งานทาสีฝ้าภายนอก ไม้ไฟเบอร์ซีเมนต์บอร์ด ไม้สังเคราะห์: สีรองพื้นสำหรับปูนเก่าหรือไฟเบอร์ซีเมนต์บอร์ด "
        "สีทับหน้า ใช้สีอะครีลิค 100% สำหรับทาไม้สังเคราะห์หรือไฟเบอร์ซีเมนต์บอร์ด",
        "- งานทาสีเหล็กและไม้: สีรองพื้นเหล็กกันสนิม หรือสีรองพื้นกันยางไม้ (ALUMINIUM WOOD PRIMER) "
        "สีทับหน้า ใช้สีน้ำมัน ตาม มอก. 327-2538",
        "- งานทาสีพื้นไม้ปาร์เก้: สีรองพื้น และสีทับหน้า ใช้สีโพลียูรีเทนสำหรับพื้นไม้ ตามมาตรฐานผู้ผลิต",
        "วิธีการและขั้นตอนการทาสี ให้ทารองพื้น 1 เที่ยว สีทับหน้า 2 เที่ยว โดยส่วนผสมใช้ตามมาตรฐานผู้ผลิต",
        "หมายเหตุ วัสดุต่างๆ ดังกล่าวข้างต้น สามารถเปลี่ยนแปลงได้ตามความเหมาะสมและวัตถุประสงค์ของผู้ว่าจ้าง"]),
    ("2.3", "งานฐานรากและโครงสร้าง ค.ส.ล.", [
        "ตามที่ได้กำหนดไว้ในแบบและรายการวิศวกรรมโครงสร้าง ส่วนรายละเอียดอื่นๆ ให้ดำเนินการ"
        "ตามมาตรฐานงานก่อสร้าง"]),
    ("2.4", "งานวิศวกรรมสุขาภิบาล", [
        "ให้ติดตั้งตามแบบวิศวกรรมสุขาภิบาลและมาตรฐานการประปาฯ"]),
    ("2.5", "งานวิศวกรรมไฟฟ้า", [
        "ให้ติดตั้งตามแบบวิศวกรรมไฟฟ้าและมาตรฐานการไฟฟ้าฯ"]),
]


def a_spec(sh, E, info):
    """A-02 «รายการประกอบแบบ» in two columns, then the building data, the
    storey rules and the abbreviations in the third."""
    x0, y0, x1, y1 = D.drawing_area()
    sh.rect(x0, y0, x1, y1, "text", 0.35)
    colw = (x1 - x0 - 10) / 3
    n_chars = int(colw / 1.62)
    sh.text((x0 + 4, y1 - 8), "รายการประกอบแบบอาคาร" + (f" {info.get('project')}" if info.get("project") else ""),
            3.2, "left", "text", True)
    col, x, y = 0, x0 + 4, y1 - 16
    h, lead = 2.25, 3.7

    def nl(dy=lead):
        nonlocal y, x, col
        y -= dy
        if y < y0 + 6 and col < 1:
            col += 1
            x, y = x0 + 6 + colw * col, y1 - 10

    for num, head, body in SPEC:
        top = len(num) <= 2 and num[0].isdigit()
        sub = num[0].isdigit() and not top
        ind = 0 if top or sub else 4
        bold = top or sub
        sh.text((x + ind, y), f"{num} {head}" if num[0].isdigit() else f"{num} {head}", h + (0.4 if top else 0.1),
                "left", "text", bold)
        if top:
            sh.line((x + ind + 6, y - 0.9), (x + ind + 6 + len(head) * 1.75, y - 0.9), "text", 0.25)
        nl(lead + 0.6)
        for para in body:
            for i, part in enumerate(D._wrap(para, n_chars - 6)):
                sh.text((x + ind + 4 + (2 if i and para.startswith("-") else 0), y), part, h)
                nl()
        nl(1.2)
    # third column: the building data, the storey rules, the abbreviations
    x3 = x0 + 8 + colw * 2
    sh.line((x3 - 3, y0), (x3 - 3, y1), "text", 0.18)
    y3 = D.notes_block(sh, x3, y1 - 8, "ข้อมูลอาคาร",
                       list(info.get("summary") or []) + (D.storey_rules(E) if E else []), 2.15,
                       int(colw / 1.55))
    y3 = D.notes_block(sh, x3, y3 - 4, "หมายเหตุทั่วไป", D.A_NOTES, 2.15, int(colw / 1.55))
    y3 -= 4
    sh.text((x3, y3), "อักษรย่อ", 3.0, "left", "text", True)
    y3 -= 4.6
    for ab, full in D.ABBREVIATIONS:
        if y3 < y0 + 3:
            break
        sh.text((x3 + 1, y3), ab, 1.9, "left", "text", True)
        sh.text((x3 + 18, y3), full, 1.9)
        y3 -= 3.3


# ---------------------------------------------------------------------------
# A2 — floor plans as the standard draws them
# ---------------------------------------------------------------------------

def sheet_ref(sheets, *starts) -> str:
    """The code of the first sheet whose title starts with one of ``starts``."""
    for s in sheets or []:
        if any(s.title.startswith(t) for t in starts):
            return s.code
    return ""


def room_tag(sh, p, E, rm, sl, fcodes, knockout=False):
    """ชื่อห้อง over □ floor number · level · ○ ceiling number
    (``knockout``: on a white patch, over the lines behind it)."""
    if knockout:
        name = rm.get("name") or "ห้อง"
        hw = max(len(name) * 1.25, 11.0)
        sh.fill([(p[0] - hw, p[1] - 5.4), (p[0] + hw, p[1] - 5.4), (p[0] + hw, p[1] + 4.6),
                 (p[0] - hw, p[1] + 4.6)], "mask", 1.0)
    sh.text((p[0], p[1] + 1.2), rm.get("name") or "ห้อง", 2.8, "center", "text", True)
    pc, _wc, cc = D.room_codes(E, rm, fcodes).split()
    lv = f"±{sl['z']:.2f}" if sl["z"] == 0 else f"+{sl['z']:.2f}"
    y = p[1] - 3.2
    has_c = cc[1:].isdigit()
    w = 4.0 + 11.0 + (5.0 if has_c else 0.0)
    x = p[0] - w / 2
    sh.rect(x, y - 1.9, x + 3.8, y + 1.9, "text", 0.25)
    sh.text((x + 1.9, y - 0.8), pc[1:] if pc[1:].isdigit() else "-", 2.0, "center", "text", True)
    sh.text((x + 4.6, y - 0.8), lv, 2.0)
    if has_c:
        _ceiling_mark(sh, (x + w - 2.1, y), cc[1:])


def opening_dims(sh, v, E, k, off=0.75):
    """The inner dimension chain along every exterior wall: the wall's ends
    and both jambs of each opening on it (as the standard plans)."""
    rooms = E["floors"][k]["rooms"]
    placed = D.opening_on_wall(E, k)
    for w in (w for w in E["walls"] if w["floor"] == k and w["exterior"]):
        (x0, y0), (x1, y1) = w["p0"], w["p1"]
        L = w["L"]
        if L < 0.6:
            continue
        ux, uy = (x1 - x0) / L, (y1 - y0) / L
        if abs(ux) > 1e-6 and abs(uy) > 1e-6:
            continue                               # slanted: none
        stops = [0.0, L]
        for ww, s_, el in placed:
            if ww is w:
                stops += [s_ - el["w"] / 2, s_ + el["w"] / 2]
        stops = sorted({round(min(max(s_, 0.0), L), 3) for s_ in stops})
        if len(stops) <= 2:
            continue
        no = D.outward(w, rooms)
        if abs(uy) < 1e-6:                          # along x
            at = y0 + no[1] * off
            xs_ = [x0 + ux * s_ for s_ in stops]
            D.dim_chain(sh, v, sorted(xs_), at, "x")
        else:
            at = x0 + no[0] * off
            ys_ = [y0 + uy * s_ for s_ in stops]
            D.dim_chain(sh, v, sorted(ys_), at, "y")


def section_mark(sh, q, tag, ref, look):
    """The standard's section mark: a circle split by a line (name over the
    sheet it is drawn on) with a black triangle pointing the way it looks."""
    r = 3.4
    lx, ly = look
    nx, ny = -ly, lx
    tip = (q[0] + lx * (r + 3.4), q[1] + ly * (r + 3.4))
    b = (q[0] + lx * r * 0.8, q[1] + ly * r * 0.8)
    sh.fill([tip, (b[0] + nx * r * 0.6, b[1] + ny * r * 0.6), (b[0] - nx * r * 0.6, b[1] - ny * r * 0.6)],
            "hatch", 0.0)
    sh.circle(q, r, "text", 0.35)
    sh.line((q[0] - r, q[1]), (q[0] + r, q[1]), "text", 0.18)
    sh.text((q[0], q[1] + 0.7), tag, 2.4, "center", "text", True)
    sh.text((q[0], q[1] - 2.5), ref or "-", 1.5, "center")


def detail_ref(sh, p, code, ref, label):
    """«ST.1 / A-13  บันได ดูแบบขยาย»: an oval-ended tag with the detail
    name over its sheet, and what it is."""
    w, h = 5.2, 3.0
    sh.poly([(p[0] - w, p[1] + h), (p[0] + w, p[1] + h), (p[0] + w + 1.5, p[1]),
             (p[0] + w, p[1] - h), (p[0] - w, p[1] - h), (p[0] - w - 1.5, p[1])], "text", 0.25)
    sh.line((p[0] - w - 1.5, p[1]), (p[0] + w + 1.5, p[1]), "text", 0.18)
    sh.text((p[0], p[1] + 0.7), code, 1.9, "center", "text", True)
    sh.text((p[0], p[1] - 2.3), ref or "-", 1.5, "center")
    sh.text((p[0] + w + 3.0, p[1] + 0.6), label, 2.2, "left", "text", True)
    sh.text((p[0] + w + 3.0, p[1] - 2.4), "ดูแบบขยาย", 2.0)


def elev_key(sh, p, refs, r=4.2):
    """The four-pointer key: 1 front · 2 left · 3 back · 4 right, each with
    the sheet its elevation is on."""
    cx, cy = p
    R = r * 1.75
    sh.poly([(cx, cy + R), (cx + R, cy), (cx, cy - R), (cx - R, cy)], "text", 0.25)
    sh.circle((cx, cy), r, "text", 0.25)
    for (dx, dy), n in (((0, -1), 1), ((-1, 0), 2), ((0, 1), 3), ((1, 0), 4)):
        nx, ny = -dy, dx
        sh.fill([(cx + dx * R, cy + dy * R), (cx + dx * r * 0.7 + nx * 2.6, cy + dy * r * 0.7 + ny * 2.6),
                 (cx + dx * r * 0.7 - nx * 2.6, cy + dy * r * 0.7 - ny * 2.6)], "hatch", 0.0)
        tx, ty = cx + dx * (R + 3.4), cy + dy * (R + 3.4)
        sh.circle((tx, ty), 2.9, "text", 0.25)
        sh.line((tx - 2.9, ty), (tx + 2.9, ty), "text", 0.13)
        sh.text((tx, ty + 0.5), str(n), 1.9, "center", "text", True)
        sh.text((tx, ty - 2.2), refs.get(n, "-"), 1.3, "center")


#: the elevation numbers of the key → our elevation titles
ELEV_NO = {1: "รูปด้านหน้า", 2: "รูปด้านซ้าย", 3: "รูปด้านหลัง", 4: "รูปด้านขวา"}


def elev_refs(sheets) -> dict:
    out = {}
    for n, title in ELEV_NO.items():
        for s in sheets or []:
            if title in s.title:
                out[n] = s.code
                break
    return out


def tag_spot(E, k, rm):
    """Where the room tag goes: the room's centre, or — when a stair sits
    there — the middle of the widest free strip beside the stair."""
    cx, cy = rm["x"] + rm["w"] / 2, rm["y"] + rm["d"] / 2
    for e in (e for e in E["stairs"] if e["floor"] in (k, k - 1)):
        pl = B.stair_plan(e["st"], E["settings"])
        pts = [q for poly in pl["polys"] for q in poly]
        x0, x1 = min(q[0] for q in pts), max(q[0] for q in pts)
        y0, y1 = min(q[1] for q in pts), max(q[1] for q in pts)
        if not (x0 - 0.3 <= cx <= x1 + 0.3 and y0 - 0.3 <= cy <= y1 + 0.3):
            continue
        strips = [(y0 - rm["y"], (cx, (rm["y"] + y0) / 2)), (rm["y"] + rm["d"] - y1, (cx, (y1 + rm["y"] + rm["d"]) / 2)),
                  (x0 - rm["x"], ((rm["x"] + x0) / 2, cy)), (rm["x"] + rm["w"] - x1, ((x1 + rm["x"] + rm["w"]) / 2, cy))]
        for size, spot in strips:                  # the front strip first (the way in)
            if size >= 0.8:
                return spot
        return max(strips)[1]
    return cx, cy


# ---------------------------------------------------------------------------
# A3 — elevations as the standard draws them
# ---------------------------------------------------------------------------

def level_ruler(sh, P, u_wall, x_rule, marks):
    """The levels on the left as the standard: ▽ +3.00 ระดับพื้นชั้น 2 on a
    dash-dot line from the building, and the chain of heights with the
    total beside them."""
    zs = sorted({round(z, 3): lab for z, lab in marks}.items())
    last = None
    for z, lab in zs:
        y = P(u_wall, z)[1]
        x_b = P(u_wall, z)[0]
        sh.line((x_rule, y), (x_b - 1.0, y), "grid", 0.13, True)
        tx = x_rule + 5.0
        ty = y + 0.8 if last is None or y + 0.8 >= last + 3.2 else last + 3.2
        sh.poly([(tx, y), (tx - 1.5, y + 2.2), (tx + 1.5, y + 2.2)], "dim", 0.18)
        t = f"{'±' if abs(z) < 1e-6 else ('+' if z > 0 else '')}{z:.2f}"
        sh.text((tx + 2.4, ty), f"{t} {lab}", 2.0, "left", "dim")
        last = ty
    # the chain of heights, and the total on its left
    ys = [P(u_wall, z)[1] for z, _l in zs]
    for x, pairs in ((x_rule - 2.0, list(zip(zs, zs[1:]))), (x_rule - 8.0, [(zs[0], zs[-1])])):
        if len(zs) < 2:
            break
        for (za, _a), (zb, _b) in pairs:
            ya, yb = P(u_wall, za)[1], P(u_wall, zb)[1]
            sh.line((x, ya), (x, yb), "dim", 0.13)
            for yy in (ya, yb):
                sh.line((x - 0.8, yy - 0.8), (x + 0.8, yy + 0.8), "dim", 0.25)
                sh.line((x - 1.2, yy), (x + 1.2, yy), "dim", 0.13)
            sh.text((x - 0.9, (ya + yb) / 2), f"{zb - za:.2f}", 2.0, "center", "dim", angle=90)
    return ys


def bottom_chain(sh, P, us, z, umin_roof, umax_roof, y_off=7.0):
    """Under the elevation: the eaves overhangs and the axis spacings, then
    the overall size between the outer axes (as the standard)."""
    y = P(0, z)[1] - y_off
    stops = sorted(set([round(u, 3) for u in us] + [round(umin_roof, 3), round(umax_roof, 3)]))
    xs = [P(u, z)[0] for u in stops]
    for (a, ua), (b, ub) in zip(zip(xs, stops), zip(xs[1:], stops[1:])):
        sh.line((a, y), (b, y), "dim", 0.13)
        sh.text(((a + b) / 2, y + 0.9), f"{ub - ua:.2f}", 2.0, "center", "dim")
    for x in xs:
        sh.line((x, y - 1.2), (x, y + 1.2), "dim", 0.13)
        sh.line((x - 0.8, y - 0.8), (x + 0.8, y + 0.8), "dim", 0.25)
    g = sorted(us)
    if len(g) >= 2:
        a, b = P(g[0], z)[0], P(g[-1], z)[0]
        y2 = y - 5.5
        sh.line((a, y2), (b, y2), "dim", 0.13)
        for x in (a, b):
            sh.line((x, y2 - 1.2), (x, y2 + 1.2), "dim", 0.13)
            sh.line((x - 0.8, y2 - 0.8), (x + 0.8, y2 + 0.8), "dim", 0.25)
        sh.text(((a + b) / 2, y2 + 0.9), f"{g[-1] - g[0]:.2f}", 2.0, "center", "dim")
    return y - 5.5


def roof_hatch(sh, poly2d, step):
    """Tile lines down the slope seen from the front: vertical lines kept
    inside the projected roof face."""
    if len(poly2d) < 3:
        return
    xs = [p[0] for p in poly2d]
    area = 0.0
    for (x0, y0), (x1, y1) in zip(poly2d, poly2d[1:] + poly2d[:1]):
        area += x0 * y1 - x1 * y0
    if abs(area) < 4.0:                                  # seen edge-on
        return
    x = min(xs) + step / 2
    while x < max(xs):
        hits = []
        for (x0, y0), (x1, y1) in zip(poly2d, poly2d[1:] + poly2d[:1]):
            if (x0 - x) * (x1 - x) < 0 and abs(x1 - x0) > 1e-9:
                hits.append(y0 + (y1 - y0) * (x - x0) / (x1 - x0))
        hits.sort()
        for a, b in zip(hits[::2], hits[1::2]):
            if b - a > 0.6:
                sh.line((x, a + 0.2), (x, b - 0.2), "hatch", 0.1)
        x += step


def roof_notes(sh, P, L, u_of, label, pitch, wall_u, z_eave):
    """The roof's label on a leader (right of the roof), the eaves overhang
    dimensions and, where the roof is seen from its end, the slope angle."""
    pts = [(u_of(p[0], p[1]), p[2]) for poly in L["skin"] for p in poly]
    u0, u1 = min(p[0] for p in pts), max(p[0] for p in pts)
    zt = max(p[1] for p in pts)
    ze = min(p[1] for p in pts)
    # the label
    tip = P(u1 - 0.25 * (u1 - u0), ze + 0.55 * (zt - ze))
    lab = (P(u1, 0)[0] + 8, P(0, zt)[1] + 2)
    sh.circle(tip, 0.5, "text", 0.18)
    sh.line(tip, (lab[0], lab[1] - 1.2), "text", 0.13)
    sh.line((lab[0], lab[1] - 1.2), (lab[0] + len(label) * 1.05 + 2, lab[1] - 1.2), "text", 0.13)
    sh.text((lab[0] + 1, lab[1]), label, 2.0)
    # the overhangs, measured from the wall faces at the eaves
    if wall_u:
        w0, w1 = min(wall_u), max(wall_u)
        y = P(0, ze)[1] - 4.5                        # under the fascia
        for a, b in ((u0, w0), (w1, u1)):
            if b - a < 0.05:
                continue
            pa, pb = P(a, ze)[0], P(b, ze)[0]
            sh.line((pa, y), (pb, y), "dim", 0.13)
            for x in (pa, pb):
                sh.line((x, y - 1.2), (x, y + 1.2), "dim", 0.13)
                sh.line((x - 0.7, y - 0.7), (x + 0.7, y + 0.7), "dim", 0.25)
                sh.line((x, y - 1.2), (x, P(0, ze)[1]), "dim", 0.1, True)
            sh.text(((pa + pb) / 2, y + 0.9), f"{b - a:.2f}", 1.9, "center", "dim")
    # the slope, when the ridge is seen end-on (gable / hip end)
    tops = [p[0] for p in pts if p[1] > zt - 0.02]
    if pitch and tops and (max(tops) - min(tops)) < 0.5 * (u1 - u0):
        kk = (P(1, 0)[0] - P(0, 0)[0])
        slope_angle(sh, P, u0, ze, pitch, 1, kk)
        slope_angle(sh, P, u1, ze, pitch, -1, kk)


def hex_tag(sh, p, text, r=2.5, layer="window"):
    """The standard's window / door number: a hexagon round the code."""
    import math as _m
    pts = [(p[0] + r * 1.15 * _m.cos(_m.radians(a)), p[1] + r * _m.sin(_m.radians(a)))
           for a in (0, 60, 120, 180, 240, 300)]
    sh.poly(pts, layer, 0.2)
    sh.text((p[0], p[1] - 0.8), text, 1.9, "center", layer)


def elev_opening(sh, P, uc, lo, el, code):
    """A door or window on an elevation as the standard draws it: the
    frame (double line), the leaves and how they open (swing «<», awning
    «^», slide arrow, louvres), the head drip above, and the number in a
    hexagon."""
    from core import wanic_catalog as CAT_
    from core import wanic_opening_sym as OS
    w, h = el["w"], el["h"]
    hi = lo + h
    lay = "window" if el["type"] == "window" else "door"
    a, b = uc - w / 2, uc + w / 2
    _c, spec = CAT_.opening_type(el["op"])
    kind = OS.kind_of(spec, _c)
    f = 0.05                                             # frame
    sh.rect(*P(a, lo), *P(b, hi), lay, 0.3)
    sh.rect(*P(a + f, lo + f), *P(b - f, hi - f), lay, 0.13)
    # the head drip (คิ้วกันน้ำ) over the opening
    sh.rect(*P(a - 0.1, hi + 0.02), *P(b + 0.1, hi + 0.08), lay, 0.18)
    if el["type"] == "window" and el.get("sill", 0) > 0.05:
        sh.rect(*P(a - 0.04, lo - 0.05), *P(b + 0.04, lo), lay, 0.13)
    n = max(1, int(spec.get("leaves") or 1))
    lw = (w - 2 * f) / n
    for i in range(n):
        x0, x1 = a + f + i * lw, a + f + (i + 1) * lw
        if i:
            sh.line(P(x0, lo + f), P(x0, hi - f), lay, 0.18)
        y0, y1 = lo + f, hi - f
        if kind == "swing":
            hinge_left = (i % 2 == 0) if n > 1 else True
            hx, ox = (x0, x1) if hinge_left else (x1, x0)
            sh.line(P(ox, y0), P(hx, (y0 + y1) / 2), lay, 0.13, True)
            sh.line(P(ox, y1), P(hx, (y0 + y1) / 2), lay, 0.13, True)
        elif kind == "awning":                          # opens out at the bottom: «^» dashed
            sh.line(P(x0, y0), P((x0 + x1) / 2, y1), lay, 0.13, True)
            sh.line(P(x1, y0), P((x0 + x1) / 2, y1), lay, 0.13, True)
        elif kind == "louvre":
            z = y0 + 0.08
            while z < y1 - 0.04:
                sh.line(P(x0, z), P(x1, z), lay, 0.1)
                z += 0.09
    if float(spec.get("glass") or 0) >= 0.5 and kind != "louvre":   # glass: the three slashes
        for i in range(n):
            gx = a + f + (i + 0.5) * lw
            gz = lo + h * 0.68
            for d_ in (-0.06, 0.0, 0.06):
                sh.line(P(gx + d_ - 0.04, gz - 0.06), P(gx + d_ + 0.04, gz + 0.06), lay, 0.1)
    if kind == "slide":
        ym = lo + h * 0.42
        p0, p1 = P(a + w * 0.2, ym), P(b - w * 0.2, ym)
        sh.line(p0, p1, lay, 0.13)
        sh.line(p1, (p1[0] - 1.2, p1[1] + 0.6), lay, 0.13)
        sh.line(p1, (p1[0] - 1.2, p1[1] - 0.6), lay, 0.13)
    if code:
        if w < 0.9:                                  # a narrow one: the tag beside it
            q = P(b, lo + h * 0.72)
            q = (q[0] + 4.2, q[1])
        else:
            q = P(a + min(0.32, w * 0.3), lo + h * 0.72)
        hex_tag(sh, q, code, 2.4, lay)


def roof_skin(sh, P, L, u_of, nx, ny, k):
    """The roof: a heavy outline, the tiles (dense lines down the slope and
    the courses along it) on the faces toward the viewer, and the fascia
    board under the eaves."""
    allp = [p for poly in L["skin"] for p in poly]
    dmin = min(p[0] * nx + p[1] * ny for p in allp)
    dmax = max(p[0] * nx + p[1] * ny for p in allp)
    for poly in L["skin"]:
        pp = [P(u_of(p[0], p[1]), p[2]) for p in poly]
        vis = sum((p[0] * nx + p[1] * ny) for p in poly) / max(len(poly), 1)
        if vis > dmax - 0.6 * (dmax - dmin):
            roof_hatch(sh, pp, max(0.7, 0.09 * k))
            ys = [q[1] for q in pp]
            yy = min(ys) + 0.45 * k
            while yy < max(ys) - 0.2 * k:              # tile courses
                hits = []
                for (x0, y0), (x1, y1) in zip(pp, pp[1:] + pp[:1]):
                    if (y0 - yy) * (y1 - yy) < 0 and abs(y1 - y0) > 1e-9:
                        hits.append(x0 + (x1 - x0) * (yy - y0) / (y1 - y0))
                hits.sort()
                for xa, xb in zip(hits[::2], hits[1::2]):
                    sh.line((xa, yy), (xb, yy), "hatch", 0.1)
                yy += 0.45 * k
    # the outline heavy (edges no other face shares, or faces seen edge-on),
    # the joints between faces thin
    edges = {}
    for poly in L["skin"]:
        pp = [P(u_of(p[0], p[1]), p[2]) for p in poly]
        ar = abs(sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(pp, pp[1:] + pp[:1]))) / 2
        for p0, p1 in zip(pp, pp[1:] + pp[:1]):
            key = tuple(sorted(((round(p0[0], 1), round(p0[1], 1)), (round(p1[0], 1), round(p1[1], 1)))))
            if key[0] != key[1]:
                edges.setdefault(key, []).append(ar)
    for (p0, p1), ars in edges.items():
        heavy = len(ars) == 1 or all(a < 4.0 for a in ars)
        sh.line(p0, p1, "roof", 0.5 if heavy else 0.18)
    # barge boards (ปั้นลม) along a gable seen end-on: a band under each slope
    pts2 = [(u_of(p[0], p[1]), p[2]) for p in allp]
    zt_ = max(p[1] for p in pts2)
    tops = [p[0] for p in pts2 if p[1] > zt_ - 0.02]
    ze_ = min(p[1] for p in pts2)
    if tops and max(tops) - min(tops) < 0.05:
        ut = tops[0]
        lo_u = [p[0] for p in pts2 if p[1] < ze_ + 0.02]
        for ue in (min(lo_u), max(lo_u)):
            sh.line(P(ue, ze_ - 0.2), P(ut, zt_ - 0.2 / max(0.3, abs(ut - ue)) * abs(ut - ue)), "roof", 0.18)
    # the fascia (เชิงชาย) under the lowest edge
    us = [u_of(p[0], p[1]) for p in allp]
    ze = min(p[2] for p in allp)
    u0, u1 = min(us), max(us)
    sh.poly([P(u0 - 0.02, ze), P(u1 + 0.02, ze), P(u1 - 0.03, ze - 0.2), P(u0 + 0.03, ze - 0.2)], "roof", 0.35)
    sh.line(P(u0 + 0.03, ze - 0.12), P(u1 - 0.03, ze - 0.12), "roof", 0.13)


def slope_angle(sh, P, u, ze, pitch, side, k):
    """The slope's angle at an eave seen end-on: a dash-dot level, an arc,
    and the angle written along the arc (as the standard)."""
    import math as _m
    c = P(u, ze)
    r = 9.0
    if side > 0:                                       # left eave, slope going up-right
        sh.line(c, (c[0] + r + 3, c[1]), "grid", 0.13, True)
        sh.arc(c, r, 0, pitch, "dim", 0.18)
        a = _m.radians(pitch / 2)
        sh.text((c[0] + (r + 2.2) * _m.cos(a), c[1] + (r + 2.2) * _m.sin(a) - 0.6), f"{pitch:.0f}°", 2.0, "left",
                "dim", angle=pitch / 2)
    else:
        sh.line(c, (c[0] - r - 3, c[1]), "grid", 0.13, True)
        sh.arc(c, r, 180 - pitch, 180, "dim", 0.18)
        a = _m.radians(180 - pitch / 2)
        sh.text((c[0] + (r + 2.2) * _m.cos(a), c[1] + (r + 2.2) * _m.sin(a) - 0.6), f"{pitch:.0f}°", 2.0, "right",
                "dim", angle=-pitch / 2)


def section_roof_labels(sh, E, L, P, segs, frame, x_right):
    """The roof members named on a section, as the standard: a short,
    tidy leader to each — labels in one column right of the roof, in the
    order of their points (top first) so no two leaders cross — and only
    for members that are drawn where the leader points."""
    s = E["settings"]
    segs = [((ua, za), (ub, zb)) for (ua, za), (ub, zb) in segs if abs(ub - ua) > 0.3]
    if not segs:
        return
    tile = CAT.roof_tile(s)[1]["name"].split(" (")[0]
    zt = max(max(a[1], b[1]) for a, b in segs)
    apex = next(q for sg in segs for q in sg if abs(q[1] - zt) < 1e-6)
    right = [sg for sg in segs if max(sg[0][0], sg[1][0]) > apex[0] + 0.2]
    items = []
    if right and max(abs(a[1] - b[1]) for a, b in right) > 0.2:      # a slope is cut
        (ua, za), (ub, zb) = max(right, key=lambda sg: abs(sg[0][1] - sg[1][1]))
        if za < zb:
            (ua, za), (ub, zb) = (ub, zb), (ua, za)               # from the apex down to the eave

        def on(t, dz=0.0):
            return (ub + (ua - ub) * (1 - t), zb + (za - zb) * (1 - t) + dz)
        items.append((on(0.0, 0.18), "ครอบสันหลังคา"))
        items.append((on(0.0, -0.12), f"อกไก่ {s.get('ridge', '')}"))
        items.append((on(0.30, 0.10), f"หลังคา{tile[:30]}"))
        items.append((on(0.48, -0.02), f"แป {s.get('purlin', '')}"))
        raf = [ln for ln in frame.get("rafter", []) if min(ln[0][0], ln[1][0]) >= apex[0] - 0.05]
        if raf:
            (pa, pb) = max(raf, key=lambda ln: abs(ln[0][0] - ln[1][0]))
            items.append(((pa[0] + (pb[0] - pa[0]) * 0.66, pa[1] + (pb[1] - pa[1]) * 0.66), f"จันทัน {s.get('rafter', '')}"))
        posts = frame.get("post") or []
        if posts:
            (pa, pb) = min(posts, key=lambda ln: abs(ln[0][0] - apex[0]))
            lo_ = pa if pa[1] < pb[1] else pb            # near its foot: the leaders stay apart
            items.append(((lo_[0], lo_[1] + 0.25), f"ดั้ง {s.get('post', '')}"))
        ties = frame.get("tie") or []
        if ties:
            (pa, pb) = max(ties, key=lambda ln: max(ln[0][0], ln[1][0]))
            u = max(pa[0], pb[0]) - 0.6
            items.append(((u, pa[1] + (pb[1] - pa[1]) * ((u - pa[0]) / ((pb[0] - pa[0]) or 1))), f"ขื่อ/อะเส {s.get('tiebeam', '')}"))
        items.append((on(1.0, -0.12), "เชิงชายไม้สังเคราะห์ 1\"x8\" ฝ้าชายคา"))
    else:                                                          # along the ridge: only what is seen
        (ua, za), (ub, zb) = max(segs, key=lambda sg: abs(sg[1][0] - sg[0][0]))
        items.append(((ua + (ub - ua) * 0.75, za + 0.18), "ครอบสันหลังคา"))
        items.append(((ua + (ub - ua) * 0.55, za - 0.6), f"หลังคา{tile[:30]}"))
    pts = [(P(*q), t) for q, t in items]
    pts.sort(key=lambda it: -it[0][1])
    _x0, _y0, x1a, y1a = D.drawing_area()
    width = max(len(t) for _p, t in pts) * 1.05 + 4
    lx = min(max(x_right, max(p[0] for p, _t in pts) + 10), x1a - width - 2)
    gap = 4.6
    ys, last = [], None
    for p, _t in pts:                    # the label at its point's height, pushed down to keep the gap
        y = p[1] + 1.5 if last is None else min(p[1] + 1.5, last - gap)
        ys.append(y)
        last = y
    for (p, text), y in zip(pts, ys):
        sh.circle(p, 0.45, "text", 0.18)
        sh.line(p, (lx - 2.0, y), "text", 0.13)
        sh.line((lx - 2.0, y), (lx + len(text) * 1.05 + 1.5, y), "text", 0.13)
        sh.text((lx, y + 0.7), text, 2.0)


def caption_marks(sh, p, title, scale_txt, mark, ref, width=95.0):
    """The standard's title under a drawing: the name over a long rule,
    «มาตราส่วน ........ 1 : 100» under it, and the drawing's own symbol(s)
    at the end of the rule."""
    x, y = p
    sh.text((x, y + 1.0), title, 4.2, "left", "text", True)
    sh.line((x, y - 0.6), (x + width, y - 0.6), "text", 0.5)
    sh.text((x, y - 5.0), "มาตราส่วน", 2.4)
    sh.text((x + width - 18, y - 5.0), scale_txt.replace(":", " : "), 2.4, "right")
    if mark:
        for i in range(2 if mark != "elev" else 1):
            section_mark(sh, (x + width - 12 + i * 10, y + 2.0), ref[0], ref[1], (0.0, 1.0))


def section_stairs(sh, E, P, U, C, at, rect):
    """The stairs on a section: the flight the plane cuts as a hatched
    waist slab with its steps, the flights and landings beyond in outline,
    the landings cut, and the railing (rail and balusters) — as the
    standard section through the stair."""
    s = E["settings"]
    for e in E["stairs"]:
        lay = B.stair_layout(e["st"], s)
        z_f = e["floor"] * E["H"]
        R, g = lay["R"], lay["g"]
        t = float(s.get("stair_t") or 0.15)
        for fl in lay["flights"]:
            (px, py), (dx, dy), n, w = fl["p0"], fl["d"], fl["n"], fl["w"]
            c_mid = C(px, py)
            du = U(dx, dy)
            if abs(du) < 0.5:
                continue                               # runs across the plane: not in profile
            u0 = U(px, py)
            z0 = z_f + fl["z0"]
            pts = [(u0, z0 + 0.0)]
            for i in range(n):
                u, z = u0 + du * g * i, z0 + R * (i + 1)
                pts += [(u, z), (u + du * g, z)]
            top = [P(*q) for q in pts]
            cut = abs(c_mid - at) <= w / 2 + 1e-6
            beyond = c_mid - w / 2 > at
            if cut:
                # the waist slab under the nosings
                import math as _m
                L_ = g * n
                ang = _m.atan2(R * n, L_)
                off = t / _m.cos(ang)
                ue = u0 + du * g * n
                poly = top + [P(ue, z0 + R * n - off), P(u0 + du * min(g, off * 1.7), z0)]
                sh.fill(poly, "hatch", 0.72)
                sh.poly(poly, "cut", 0.35)
            elif beyond:
                sh.poly(top, "wall", 0.18, closed=False)
                ue = u0 + du * g * n
                sh.line(P(ue, z0 + R * n - t * 1.15), P(u0, z0 - t * 1.15), "wall", 0.18)
        for ld in lay["landings"]:
            xs_ = [q[0] for q in ld["pts"]]
            ys_ = [q[1] for q in ld["pts"]]
            c0, c1 = (min(xs_), max(xs_)) if C(1, 0) else (min(ys_), max(ys_))
            u_a, u_b = (min(ys_), max(ys_)) if C(1, 0) else (min(xs_), max(xs_))
            z = z_f + ld["z"]
            if c0 - 1e-6 <= at <= c1 + 1e-6:
                rect(u_a, z - t, u_b, z, "cut", 0.35, 0.72)
            elif c0 > at:
                sh.rect(*P(u_a, z - t), *P(u_b, z), "wall", 0.18)
        # the railing seen: the rail, the balusters
        rl = B.stair_railing(e["st"], s)
        for a_, b_ in rl["rails"]:
            if min(C(a_[0], a_[1]), C(b_[0], b_[1])) >= at - 0.6:
                sh.line(P(U(a_[0], a_[1]), z_f + a_[2]), P(U(b_[0], b_[1]), z_f + b_[2]), "door", 0.35)
        for a_, b_ in rl["posts"]:
            if C(a_[0], a_[1]) >= at - 0.6:
                sh.line(P(U(a_[0], a_[1]), z_f + a_[2]), P(U(b_[0], b_[1]), z_f + b_[2]), "door", 0.13)


# ---------------------------------------------------------------------------
# A5 — แบบขยายประตู แบบขยายหน้าต่าง (the standard's 4 × 2 cards)
# ---------------------------------------------------------------------------

FRAME_TH = {"wood": "ไม้เนื้อแข็ง 2\" x 4\"", "alu": "อลูมิเนียมอบสีขาว", "teak": "ไม้สัก 2\" x 4\"",
            "pvc": "วงกบ PVC.", "steel": "เหล็กรูปพรรณ ทาสีกันสนิม"}
LEAF_TH = {"wood": "บานไม้ทาสี", "prefab": "บานประตูสำเร็จรูป HDF.", "alu": "กระจกใส หนา 6 มม.",
           "teak": "บานไม้สักลูกฟัก", "pvc": "บานประตู PVC.", "none": "-"}


def opening_kind_th(spec, code) -> str:
    from core import wanic_opening_sym as OS
    k = OS.kind_of(spec, code)
    n = int(spec.get("leaves") or 1)
    if k == "slide":
        return "บานเลื่อน" + (f" {n} บาน" if n > 2 else "สลับ")
    if k == "awning":
        return "บานกระทุ้ง"
    if k == "louvre":
        return "บานเกล็ด"
    if k == "fixed":
        return "ช่องแสงติดตาย"
    return "บานเปิดคู่" if n >= 2 else "บานเปิดเดี่ยว"


def opening_rooms(E, code, codes) -> list:
    """The rooms each opening of ``code`` opens from (for «ติดตั้งบริเวณ»)."""
    names = []
    for el in E["openings"]:
        if D.op_code(el, codes) != code:
            continue
        ox, oy = float(el["op"]["x"]), float(el["op"]["y"])
        for rm in E["floors"][el["floor"]]["rooms"]:
            if rm["x"] - 0.06 <= ox <= rm["x"] + rm["w"] + 0.06 and rm["y"] - 0.06 <= oy <= rm["y"] + rm["d"] + 0.06:
                nm = (rm.get("name") or "").rstrip("0123456789 ")
                if nm and nm not in names:
                    names.append(nm)
    return names


def opening_cards(E, codes) -> list:
    """[(code, key, spec, sample el, count)] — doors first, as numbered."""
    from core import wanic_catalog as CAT_
    out = []
    for key, code in sorted(codes.items(), key=lambda t: (t[1][0] != "ป", int(t[1][1:]))):
        els = [o for o in E["openings"] if D.op_code(o, codes) == code]
        if not els:
            continue
        _c, spec = CAT_.opening_type(els[0]["op"])
        out.append((code, key, spec, els[0], len(els)))
    return out


def a_openings(sh, E, codes, cards):
    """Up to eight cards: the plan symbol, the elevation with its sizes on
    the floor line, the number (○ door / ⬡ window) and the specification
    rows — the standard's «แบบขยายประตู แบบขยายหน้าต่าง»."""
    x0, y0, x1, y1 = D.drawing_area()
    cw, ch = (x1 - x0) / 4, (y1 - y0) / 2
    sh.rect(x0, y0, x1, y1, "text", 0.35)
    for i in range(1, 4):
        sh.line((x0 + i * cw, y0), (x0 + i * cw, y1), "text", 0.25)
    sh.line((x0, y0 + ch), (x1, y0 + ch), "text", 0.35)
    for n, (code, key, spec, el, cnt) in enumerate(cards[:8]):
        cx0, cy1 = x0 + (n % 4) * cw, y1 - (n // 4) * ch
        style, w, h, sill = key
        sc = 50 if w * 20 <= cw - 22 and (sill + h) * 20 <= 62 else 75
        k = 1000.0 / sc
        ground = cy1 - 78
        mid = cx0 + cw / 2 + 4
        u0 = -w / 2

        def P(u, z):
            return (mid + u * k, ground + z * k)
        sh.line((cx0 + 2, ground), (cx0 + cw - 2, ground), "cut", 0.5)
        elev_opening(sh, P, 0.0, sill, el, "")
        # the width over it, the heights on its left
        yt = P(0, sill + h)[1] + 6
        a, b = P(u0, 0)[0], P(-u0, 0)[0]
        sh.line((a, yt), (b, yt), "dim", 0.13)
        for xq in (a, b):
            sh.line((xq, yt - 1.2), (xq, yt + 1.2), "dim", 0.13)
            sh.line((xq - 0.7, yt - 0.7), (xq + 0.7, yt + 0.7), "dim", 0.25)
        sh.text(((a + b) / 2, yt + 0.9), f"{w:.2f}", 2.2, "center", "dim")
        n_leaf = int(spec.get("leaves") or 1)
        if n_leaf >= 3:
            sh.text(((a + b) / 2, yt + 4.0), f"แบ่ง {n_leaf} ช่อง เท่าๆ กัน", 2.0, "center", "dim")
        xl = a - 6
        chain = ([0.0, sill] if sill > 0.01 else [0.0]) + [sill + h]
        for za, zb in zip(chain, chain[1:]):
            pa, pb = P(0, za)[1], P(0, zb)[1]
            sh.line((xl, pa), (xl, pb), "dim", 0.13)
            for yq in (pa, pb):
                sh.line((xl - 0.7, yq - 0.7), (xl + 0.7, yq + 0.7), "dim", 0.25)
                sh.line((xl - 1.2, yq), (a - 1, yq), "dim", 0.1)
            sh.text((xl - 0.9, (pa + pb) / 2), f"{zb - za:.2f}", 2.0, "center", "dim", angle=90)
        if sill > 0.01:
            xt = xl - 5
            pa, pb = P(0, 0)[1], P(0, sill + h)[1]
            sh.line((xt, pa), (xt, pb), "dim", 0.13)
            for yq in (pa, pb):
                sh.line((xt - 0.7, yq - 0.7), (xt + 0.7, yq + 0.7), "dim", 0.25)
            sh.text((xt - 0.9, (pa + pb) / 2), f"{sill + h:.2f}", 2.0, "center", "dim", angle=90)
        # the plan symbol at the top of the card
        D.opening_sample(sh, (mid, cy1 - 11), el["op"], w, 75, word=False)
        # the number, then the rows
        ty = ground - 9
        sh.line((cx0, ground - 4), (cx0 + cw, ground - 4), "text", 0.18)
        if code.startswith("ป"):
            sh.circle((cx0 + cw / 2, ty), 3.6, "text", 0.25)
            sh.text((cx0 + cw / 2, ty - 1.0), code, 2.6, "center", "text", True)
        else:
            hex_tag(sh, (cx0 + cw / 2, ty), code, 3.6, "text")
        frame = FRAME_TH.get(spec.get("frame"), spec.get("frame") or "-")
        glass = float(spec.get("glass") or 0)
        leaf = LEAF_TH.get(spec.get("leaf"), "-")
        if glass >= 0.5 and spec.get("leaf") in ("alu", "wood", "teak"):
            leaf = "กระจกใส หนา 6 มม." if spec.get("leaf") == "alu" else f"{leaf} กรุกระจกใส"
        rooms = opening_rooms(E, code, codes)
        rows = [("ชนิดบาน", opening_kind_th(spec, style)),
                ("วงกบ", frame),
                ("กรอบบาน", frame if spec.get("frame") == "alu" else "-"),
                ("บาน", leaf),
                ("อุปกรณ์", ("ลูกบิด , " if code.startswith("ป") else "") + "มาตรฐานครบชุด"),
                ("จำนวน", f"{cnt} ชุด"),
                ("หมายเหตุ", ("ติดตั้งบริเวณ " + " , ".join(rooms)) if rooms else "")]
        ry = ty - 6
        sh.line((cx0, ry), (cx0 + cw, ry), "text", 0.25)
        rh = (ry - (cy1 - ch)) / len(rows)
        for j, (lab, val) in enumerate(rows):
            yb = ry - (j + 1) * rh
            sh.line((cx0, yb), (cx0 + cw, yb), "text", 0.13)
            sh.text((cx0 + 19, yb + rh / 2 - 0.9), lab, 2.1, "right")
            parts = D._wrap(val, 40)[:2]
            for m, part in enumerate(parts):
                sh.text((cx0 + 23, yb + rh / 2 - 0.8 - m * 2.3 + (1.15 if len(parts) > 1 else 0)),
                        part, 1.9 if len(parts) > 1 else 2.1)
        sh.line((cx0 + 21, ry), (cx0 + 21, cy1 - ch), "text", 0.13)


# ---------------------------------------------------------------------------
# A5-2 — แบบขยายห้องน้ำ WC.n (the standard's bathroom plan at 1:25)
# ---------------------------------------------------------------------------

def bath_fixtures(E, k, rm):
    """The room's own fittings, or — when none are placed — the standard
    set for its size (so the detail is never an empty box)."""
    own = [f for f in E["fixtures"] if f["floor"] == k and D._inside(f["fx"], rm)]
    if own:
        return own
    from core import wanic_catalog as CAT_
    return [{"floor": k, "fx": {"type": c, "x": rm["x"] + px, "y": rm["y"] + py, "dir": d_}}
            for c, px, py, d_ in CAT_.bathroom_layout(float(rm["w"]), float(rm["d"]))]


def bath_groups(E) -> list:
    """Bathrooms of the same size drawn once: [[(floor, room), …], …]."""
    groups: list = []
    for k, rm in D.bathrooms(E):
        key = (round(float(rm["w"]), 2), round(float(rm["d"]), 2))
        for g in groups:
            if g[0] == key:
                g[1].append((k, rm))
                break
        else:
            groups.append([key, [(k, rm)]])
    return [g[1] for g in groups]


FIX_LABEL = {"WC1": "WC.1", "WC2": "WC.1", "LV": "LAV.1", "LV2": "LAV.2", "SH": "SH.", "SP": "SP.",
             "FD": "FD.", "TR": "TR.", "TP": "PH.", "MR": "M.", "PL": "PL.", "GP": "GP.", "BT2": "BT."}


def a_bath_plan(sh, E, group, codes, first_no, sheets=None):
    """แปลนห้องน้ำ WC.n at 1:25: the walls round it (doors, windows, hatch),
    the floor tiles, the fittings with their marks, the fall to the drain,
    the room tag, the dimension chains and axes, the interior-elevation
    marker — and the floor levels underneath, as the standard."""
    k, rm = group[0]
    t = float(E["settings"].get("wall_t") or 0.1)
    x0, y0, x1, y1 = D.drawing_area()
    W, Dd = float(rm["w"]), float(rm["d"])
    sc = next((s_ for s_ in (25, 30, 40, 50) if (W + 2.4) * 1000 / s_ <= (x1 - x0) * 0.80
               and (Dd + 3.2) * 1000 / s_ <= (y1 - y0) - 45), 50)
    kk = 1000.0 / sc
    cx = x0 + (x1 - x0) * 0.40
    origin = (cx - W * kk / 2, y0 + 60 + max(0.0, ((y1 - y0 - 60) - Dd * kk) / 2 - 10))
    v = D.View(sh, sc, (rm["x"], rm["y"]), origin)
    # only the walls round this room, with their doors and windows
    near = []
    for w in E["walls"]:
        if w["floor"] != k:
            continue
        (ax, ay), (bx, by) = w["p0"], w["p1"]
        if (min(ax, bx) <= rm["x"] + W + 0.01 and max(ax, bx) >= rm["x"] - 0.01 and
                min(ay, by) <= rm["y"] + Dd + 0.01 and max(ay, by) >= rm["y"] - 0.01):
            near.append(w)
    E2 = dict(E, walls=near, columns=[c for c in E["columns"] if c["floor"] == k and
                                      rm["x"] - 0.3 <= c["x"] <= rm["x"] + W + 0.3 and
                                      rm["y"] - 0.3 <= c["y"] <= rm["y"] + Dd + 0.3])
    # the floor tiles, 0.30 m
    step = 0.30
    xi0, yi0, xi1, yi1 = rm["x"] + t / 2, rm["y"] + t / 2, rm["x"] + W - t / 2, rm["y"] + Dd - t / 2
    xx = xi0 + step
    while xx < xi1 - 0.02:
        sh.line(v(xx, yi0), v(xx, yi1), "hatch", 0.1)
        xx += step
    yy = yi0 + step
    while yy < yi1 - 0.02:
        sh.line(v(xi0, yy), v(xi1, yy), "hatch", 0.1)
        yy += step
    n0 = len(sh.items)
    D.draw_walls(sh, v, E2, k, t, codes, tags=False)
    bx0, by0 = v(rm["x"] - 0.55, rm["y"] - 0.55)
    bx1, by1 = v(rm["x"] + W + 0.55, rm["y"] + Dd + 0.55)
    sh.items[n0:] = clip_items(sh.items[n0:], (bx0, by0, bx1, by1))
    # the walls cut: 45° hatch in the masonry, clear of the doors and windows
    placed = D.opening_on_wall(E, k)
    for w in near:
        (ax, ay), (bx_, by_) = w["p0"], w["p1"]
        Lw = w["L"]
        if Lw < 0.05:
            continue
        ux, uy = (bx_ - ax) / Lw, (by_ - ay) / Lw
        cuts = sorted((s_ - el["w"] / 2, s_ + el["w"] / 2) for ww, s_, el in placed if ww is w)
        segs, s0 = [], 0.0
        for c0, c1 in cuts + [(Lw, Lw)]:
            if c0 - s0 > 0.02:
                segs.append((s0, c0))
            s0 = max(s0, c1)
        for sa, sb in segs:
            pa = v(ax + ux * sa - uy * t / 2, ay + uy * sa + ux * t / 2)
            pb = v(ax + ux * sb + uy * t / 2, ay + uy * sb - ux * t / 2)
            n1 = len(sh.items)
            _brick_band(sh, pa, pb, 1.2)
            sh.items[n1:] = clip_items(sh.items[n1:], (bx0, by0, bx1, by1))
    # the fittings, drawn as the original draws them
    fx = bath_fixtures(E, k, rm)
    inner = _inner(E, k, rm)
    for f in fx:
        ff = fit_inside(f["fx"], inner)
        q = [v(*p) for p in D.fixture_rect(dict(ff, dir=0 if back_side(ff, inner) in (0, 2) else 1))]
        if f["fx"].get("type") not in ("FD", "MR", "TR", "GP", "SP", "TP", "SH"):
            sh.fill(q, "mask", 1.0)
        fixture_plan(sh, v, f["fx"], inner)
    # the fall to the floor drain
    fd = next((fit_inside(f["fx"], _inner(E, k, rm)) for f in fx if f["fx"].get("type") == "FD"), None)
    if fd is not None:
        far = max(((xi0, yi0), (xi1, yi0), (xi0, yi1), (xi1, yi1)),
                  key=lambda p: (p[0] - float(fd["x"])) ** 2 + (p[1] - float(fd["y"])) ** 2)
        a = (far[0] + (float(fd["x"]) - far[0]) * 0.25, far[1] + (float(fd["y"]) - far[1]) * 0.25)
        b = (far[0] + (float(fd["x"]) - far[0]) * 0.80, far[1] + (float(fd["y"]) - far[1]) * 0.80)
        pa, pb = v(*a), v(*b)
        sh.line(pa, pb, "dim", 0.18)
        import math as _m
        ang = _m.degrees(_m.atan2(pb[1] - pa[1], pb[0] - pa[0]))
        ux, uy = (pb[0] - pa[0]), (pb[1] - pa[1])
        L = _m.hypot(ux, uy) or 1
        ux, uy = ux / L, uy / L
        sh.line(pb, (pb[0] - ux * 2 + uy * 0.8, pb[1] - uy * 2 - ux * 0.8), "dim", 0.18)
        sh.line(pb, (pb[0] - ux * 2 - uy * 0.8, pb[1] - uy * 2 + ux * 0.8), "dim", 0.18)
        if ang > 90 or ang < -90:
            ang += 180
        sh.text(((pa[0] + pb[0]) / 2, (pa[1] + pb[1]) / 2 + 1.0), "ลาดเอียง 1:200", 2.0, "center", "dim",
                angle=ang)
    # the room tag
    sl = next(s_ for s_ in E["slabs"] if s_["room"] is rm)
    room_tag(sh, v(rm["x"] + W * 0.5, rm["y"] + Dd * 0.5), E, rm, sl, D.finish_codes(E), knockout=True)
    # the chains: wall | inside | wall, and the overall between the axes
    D.dim_chain(sh, v, [rm["x"] - t / 2, rm["x"] + t / 2, rm["x"] + W - t / 2, rm["x"] + W + t / 2],
                rm["y"] + Dd + 0.55, "x")
    D.dim_chain(sh, v, [rm["x"], rm["x"] + W], rm["y"] + Dd + 0.95, "x")
    D.dim_chain(sh, v, [rm["y"] - t / 2, rm["y"] + t / 2, rm["y"] + Dd - t / 2, rm["y"] + Dd + t / 2],
                rm["x"] + W + 0.55, "y")
    D.dim_chain(sh, v, [rm["y"], rm["y"] + Dd], rm["x"] + W + 0.95, "y")
    # the axes through the room's sides, with their names
    xs, ys = D.grids(E)
    for i, gx in enumerate(xs):
        if rm["x"] - 0.01 <= gx <= rm["x"] + W + 0.01:
            a, b = v(gx, rm["y"] - 0.5), v(gx, rm["y"] + Dd + 1.5)
            sh.line(a, b, "grid", 0.13, True)
            sh.circle((b[0], b[1] + 3.2), 3.2, "grid", 0.25)
            sh.text((b[0], b[1] + 2.1), str(i + 1), 2.6, "center", "grid")
    for j, gy in enumerate(ys):
        if rm["y"] - 0.01 <= gy <= rm["y"] + Dd + 0.01:
            a, b = v(rm["x"] - 1.3, gy), v(rm["x"] + W + 0.5, gy)
            sh.line(a, b, "grid", 0.13, True)
            sh.circle((a[0] - 3.2, a[1]), 3.2, "grid", 0.25)
            sh.text((a[0] - 3.2, a[1] - 1.0), D.axis_name(j), 2.6, "center", "grid")
    # the sections ① ②: a dash-dot cut line across the room and its mark,
    # looking at the wall the section shows (the original's)
    ref = sheet_ref(sheets, "รูปตัดห้องน้ำ")
    xi0_, yi0_, xi1_, yi1_ = inner
    for i, side in enumerate(bath_sides(E, k, rm)):
        look = {0: (0.0, -1.0), 1: (1.0, 0.0), 2: (0.0, 1.0), 3: (-1.0, 0.0)}[side]
        if side in (0, 2):                       # a line along x, near the far wall
            yc = yi1_ - 0.35 * (yi1_ - yi0_) if side == 0 else yi0_ + 0.35 * (yi1_ - yi0_)
            a, b = v(rm["x"] - 0.4, yc), v(rm["x"] + W + 0.4, yc)
            q = (b[0] + 4.5, b[1])
        else:
            xc = xi0_ + 0.35 * (xi1_ - xi0_) if side == 1 else xi1_ - 0.35 * (xi1_ - xi0_)
            a, b = v(xc, rm["y"] + Dd + 0.4), v(xc, rm["y"] - 0.4)
            q = (b[0], b[1] - 4.5)
        sh.line(a, b, "grid", 0.3, True)
        section_mark(sh, q, str(i + 1), ref, look)
    # the title and the floor levels
    names = " , ".join(f"WC.{first_no + i}" for i in range(len(group)))
    capx = cx - 50
    caption_marks(sh, (capx, y0 + 40), f"แปลนห้องน้ำ {names}", f"1:{sc}", None, None, 100.0)
    sh.text((capx, y0 + 22), "หมายเหตุ", 2.4)
    for i, (kf, r_) in enumerate(group):
        s_ = next(x_ for x_ in E["slabs"] if x_["room"] is r_)
        lv = f"±{s_['z']:.2f}" if abs(s_["z"]) < 1e-6 else f"+{s_['z']:.2f}"
        sh.text((capx + 16, y0 + 22 - i * 4.2),
                f"- ระดับพื้นห้องน้ำ WC.{first_no + i} (ชั้น {kf + 1}) = {lv} ม. (ต่ำกว่าห้องข้างเคียง 0.05 ม.)", 2.3)
    sh.scale = f"1:{sc}"
    return sc


def _clip_seg(a, b, box):
    """Liang–Barsky: the part of a–b inside box, or None."""
    x0, y0, x1, y1 = box
    dx, dy = b[0] - a[0], b[1] - a[1]
    t0, t1 = 0.0, 1.0
    for p_, q_ in ((-dx, a[0] - x0), (dx, x1 - a[0]), (-dy, a[1] - y0), (dy, y1 - a[1])):
        if abs(p_) < 1e-12:
            if q_ < 0:
                return None
            continue
        r = q_ / p_
        if p_ < 0:
            t0 = max(t0, r)
        else:
            t1 = min(t1, r)
        if t0 > t1:
            return None
    return (a[0] + dx * t0, a[1] + dy * t0), (a[0] + dx * t1, a[1] + dy * t1)


def clip_items(items, box):
    """Drawing items kept to ``box`` (paper mm): lines and outlines cut at
    its edge, fills / circles / arcs / text kept only when inside."""
    x0, y0, x1, y1 = box
    inside = lambda p: x0 <= p[0] <= x1 and y0 <= p[1] <= y1     # noqa: E731
    out = []
    for it in items:
        kind = it[0]
        if kind == "line":
            ax, ay, bx, by = it[1]
            c = _clip_seg((ax, ay), (bx, by), box)
            if c:
                out.append(("line", (c[0][0], c[0][1], c[1][0], c[1][1])) + tuple(it[2:]))
        elif kind == "poly":
            pts, closed = it[1], it[4]
            segs = list(zip(pts, pts[1:] + (pts[:1] if closed else [])))
            if all(inside(p) for p in pts):
                out.append(it)
                continue
            for a, b in segs:
                c = _clip_seg(a, b, box)
                if c:
                    out.append(("line", (c[0][0], c[0][1], c[1][0], c[1][1]), it[2], it[3], it[5]))
        elif kind == "fill":
            if all(inside(p) for p in it[1]):
                out.append(it)
        elif kind in ("circle", "arc"):
            if inside(it[1][:2]):
                out.append(it)
        elif kind == "text":
            if inside(it[1]):
                out.append(it)
        else:
            out.append(it)
    return out


def bath_section_layout(E, group):
    """[(sides on the sheet)] — the two sections side by side when they go
    at 1:30 or larger (the original), else one a sheet so each is big."""
    k, rm = group[0]
    ix0, iy0, ix1, iy1 = _inner(E, k, rm)
    x0, y0, x1, y1 = D.drawing_area()
    half = (x1 - x0) / 2
    t_ = float(E["settings"].get("wall_t") or 0.1)
    sides = bath_sides(E, k, rm)
    ok = all((((ix1 - ix0) if s_ in (0, 2) else (iy1 - iy0)) + 2 * t_ + 1.6) * 1000 / 30 + 26 <= half - 4
             for s_ in sides)
    return [sides] if ok else [[sides[0]], [sides[1]]]


def a_bath_sections(sh, E, group, first_no, sides=None, nums=None):
    """รูปตัดห้องน้ำ WC.n ① ② — side by side as the original, or one big
    section to a sheet for a large bathroom."""
    k, rm = group[0]
    sides = sides or bath_sides(E, k, rm)
    nums = nums or list(range(1, len(sides) + 1))
    x0, y0, x1, y1 = D.drawing_area()
    n = len(sides)
    cw = (x1 - x0) / n
    if n == 2:
        sh.line((x0 + cw, y0), (x0 + cw, y1), "frame", 0.25)
    ix0, iy0, ix1, iy1 = _inner(E, k, rm)
    names = ",".join(f"WC.{first_no + i}" for i in range(len(group)))
    used = 0
    t_ = float(E["settings"].get("wall_t") or 0.1)
    for i, side in enumerate(sides):
        Wm = (ix1 - ix0) if side in (0, 2) else (iy1 - iy0)
        span = Wm + 2 * t_ + 1.6
        sc = next((s_ for s_ in (20, 25, 30, 40, 50, 60) if span * 1000 / s_ + 26 <= cw - 4
                   and (E["H"] + 0.6) * 1000 / s_ <= (y1 - y0) - 75), 75)
        used = max(used, sc)
        kk = 1000.0 / sc
        bx0 = x0 + i * cw
        ox = bx0 + 26 + (cw - 30 - span * kk) / 2 + (1.15 + t_) * kk
        oy = y0 + 62 + max(0.0, ((y1 - y0) - 75 - (E["H"] + 0.6) * kk) * 0.5)
        bath_section(sh, E, k, rm, side, ox, oy, sc, nums[i], None, names)
    sh.scale = f"1:{used}"
    return used


# ---------------------------------------------------------------------------
# A5-2 (round 2) — the bathroom as the original draws it
# ---------------------------------------------------------------------------

def _inner(E, k, rm):
    return B.room_inner(E, rm, k)


def back_side(fx, inner) -> int:
    """The wall a fitting stands against: 0 S (y0), 1 E (x1), 2 N (y1), 3 W (x0)."""
    x0, y0, x1, y1 = inner
    x, y = float(fx["x"]), float(fx["y"])
    d_ = [y - y0, x1 - x, y1 - y, x - x0]
    return d_.index(min(d_))


_OUT = {0: (0.0, 1.0), 1: (-1.0, 0.0), 2: (0.0, -1.0), 3: (1.0, 0.0)}      # into the room
_ALONG = {0: (1.0, 0.0), 1: (0.0, 1.0), 2: (-1.0, 0.0), 3: (0.0, -1.0)}


def _ellipse(c, ra, ro, al, ou, n=28):
    import math as _m
    return [(c[0] + al[0] * ra * _m.cos(2 * _m.pi * i / n) + ou[0] * ro * _m.sin(2 * _m.pi * i / n),
             c[1] + al[1] * ra * _m.cos(2 * _m.pi * i / n) + ou[1] * ro * _m.sin(2 * _m.pi * i / n))
            for i in range(n)]


GAP = 0.04                               # fittings stand clear of the wall face (plaster, tiles)


def fit_inside(fx, inner):
    """The fitting moved, if need be, so its outline stays inside the room
    and clear of every wall face (its back GAP off the wall it stands on)."""
    t = str(fx.get("type", ""))
    spec = D.fixture_spec(t) or ("", "", 0, 0.4, 0.4, 0, 0)
    w, d = float(spec[3]), float(spec[4])
    side = back_side(fx, inner)
    hw, hd = (w / 2, d / 2) if side in (0, 2) else (d / 2, w / 2)
    if t in ("FD", "PL"):
        hw = hd = max(w, d) / 2
    x0, y0, x1, y1 = inner
    g = GAP
    x = min(max(float(fx["x"]), x0 + hw + g), x1 - hw - g)
    y = min(max(float(fx["y"]), y0 + hd + g), y1 - hd - g)
    if t not in ("FD", "PL"):                    # the back right on the wall (+ the gap)
        if side == 0:
            y = y0 + hd + g
        elif side == 2:
            y = y1 - hd - g
        elif side == 1:
            x = x1 - hw - g
        else:
            x = x0 + hw + g
    return dict(fx, x=x, y=y)


def fixture_plan(sh, v, fx, inner):
    """A fitting in plan as the original draws it (tank and bowl, basin in
    its counter, shower head and valve, drain grate, rail, mirror …)."""
    fx = fit_inside(fx, inner)
    t = str(fx.get("type", ""))
    spec = D.fixture_spec(t) or ("", "", 0, 0.4, 0.4, 0, 0)
    w, d = float(spec[3]), float(spec[4])
    side = back_side(fx, inner)
    al, ou = _ALONG[side], _OUT[side]
    cx, cy = float(fx["x"]), float(fx["y"])

    def L(a, o):                         # along, out (m) from the back centre
        return (cx + al[0] * a + ou[0] * (o - d / 2), cy + al[1] * a + ou[1] * (o - d / 2))

    def poly(pts, wt=0.25, closed=True):
        sh.poly([v(*p) for p in pts], "fixture", wt, closed)
    if t.startswith("WC1") or t.startswith("UR"):
        poly([L(-w * 0.55, 0), L(w * 0.55, 0), L(w * 0.55, 0.2), L(-w * 0.55, 0.2)])     # tank
        c = L(0, 0.2 + (d - 0.2) / 2)
        poly(_ellipse(c, w / 2, (d - 0.2) / 2, al, ou))
        poly(_ellipse(c, w / 2 - 0.05, (d - 0.2) / 2 - 0.07, al, ou), 0.13)
    elif t.startswith("WC2"):
        poly([L(-w / 2, 0.05), L(w / 2, 0.05), L(w / 2, d), L(-w / 2, d)])
        poly(_ellipse(L(0, d * 0.45), w * 0.22, d * 0.3, al, ou), 0.13)
    elif t == "LV" or t.startswith("SK"):
        poly([L(-w / 2, 0), L(w / 2, 0), L(w / 2, d), L(-w / 2, d)])
        poly(_ellipse(L(0, d * 0.55), w * 0.36, d * 0.30, al, ou), 0.18)
        sh.circle(v(*L(0, d * 0.55)), v.len(0.02), "fixture", 0.13)
        sh.circle(v(*L(0, 0.07)), v.len(0.025), "fixture", 0.18)
    elif t == "LV2":
        poly([L(-w / 2, 0), L(w / 2, 0), L(w / 2, d), L(-w / 2, d)])
        for a_ in (-w / 4, w / 4):
            poly(_ellipse(L(a_, d * 0.55), 0.2, d * 0.3, al, ou), 0.18)
    elif t.startswith("SH"):
        sh.circle(v(*L(0, 0.12)), v.len(0.07), "fixture", 0.25)
        sh.line(v(*L(0, 0.0)), v(*L(0, 0.12)), "fixture", 0.18)
        poly([L(-0.06, 0.0), L(0.06, 0.0), L(0.06, 0.05), L(-0.06, 0.05)], 0.18)
    elif t == "SP":
        poly([L(-0.04, 0), L(0.04, 0), L(0.04, 0.06), L(-0.04, 0.06)], 0.18)
        sh.arc(v(*L(0.0, 0.10)), v.len(0.05), 0, 300, "fixture", 0.13)
    elif t == "FD":
        c = v(cx, cy)
        sh.circle(c, v.len(0.07), "fixture", 0.25)
        for dd_ in (-0.04, 0.0, 0.04):
            sh.line(v(cx - 0.06, cy + dd_), v(cx + 0.06, cy + dd_), "fixture", 0.1)
    elif t == "TR":
        sh.line(v(*L(-w / 2, 0.06)), v(*L(w / 2, 0.06)), "fixture", 0.35)
        for a_ in (-w / 2, w / 2):
            sh.line(v(*L(a_, 0)), v(*L(a_, 0.06)), "fixture", 0.25)
    elif t == "TP":
        poly([L(-0.07, 0), L(0.07, 0), L(0.07, 0.1), L(-0.07, 0.1)], 0.18)
    elif t == "MR":
        sh.line(v(*L(-w / 2, 0.02)), v(*L(w / 2, 0.02)), "fixture", 0.5)
    elif t == "BT2":
        c = L(0, d / 2)
        poly(_ellipse(c, w / 2, d / 2, al, ou))
        poly(_ellipse(c, w / 2 - 0.07, d / 2 - 0.07, al, ou), 0.13)
    elif t == "GP":
        sh.line(v(*L(-w / 2, 0.01)), v(*L(w / 2, 0.01)), "fixture", 0.13)
        sh.line(v(*L(-w / 2, 0.03)), v(*L(w / 2, 0.03)), "fixture", 0.13)
    elif t == "PL":
        sh.circle(v(cx, cy), v.len(min(w, d) / 2), "fixture", 0.18)
    else:
        poly([L(-w / 2, 0), L(w / 2, 0), L(w / 2, d), L(-w / 2, d)], 0.18)
    lab = FIX_LABEL.get(t, t)
    q = v(*L(w / 2 + 0.05, d * 0.6 if t not in ("FD",) else 0.0))
    sh.text((q[0] + 0.5, q[1] - 0.8), lab, 1.8, "left", "fixture")


def fixture_front(sh, P, t, a, b, spec):
    """A fitting seen from the front on the wall it stands against."""
    zb, hh = float(spec[5]), float(spec[6])
    m = (a + b) / 2
    w = b - a
    if t.startswith("WC1"):
        sh.poly([P(m - 0.22, 0.40), P(m + 0.22, 0.40), P(m + 0.22, 0.75), P(m - 0.22, 0.75)], "fixture", 0.25)
        sh.line(P(m - 0.23, 0.72), P(m + 0.23, 0.72), "fixture", 0.13)
        sh.poly([P(m - 0.12, 0.0), P(m + 0.12, 0.0), P(m + 0.19, 0.38), P(m - 0.19, 0.38)], "fixture", 0.25)
        sh.poly([P(m - 0.20, 0.38), P(m + 0.20, 0.38), P(m + 0.20, 0.42), P(m - 0.20, 0.42)], "fixture", 0.18)
        sh.circle(P(m + 0.15, 0.68), 0.6, "fixture", 0.13)
    elif t.startswith("WC2"):
        sh.poly([P(a, 0.0), P(b, 0.0), P(b, 0.15), P(a, 0.15)], "fixture", 0.25)
    elif t == "LV" or t.startswith("SK"):
        top = zb + hh
        sh.poly([P(a, top - 0.05), P(b, top - 0.05), P(b, top), P(a, top)], "fixture", 0.25)
        sh.poly([P(m - w * 0.38, top - 0.05), P(m - w * 0.25, top - 0.20), P(m + w * 0.25, top - 0.20),
                 P(m + w * 0.38, top - 0.05)], "fixture", 0.2, closed=False)
        sh.line(P(m, top - 0.20), P(m, top - 0.32), "fixture", 0.18)
        sh.arc(P(m + 0.04, top - 0.32), 1.0, 180, 360, "fixture", 0.18)
        sh.poly([P(m - 0.02, top), P(m - 0.02, top + 0.15), P(m + 0.08, top + 0.15)], "fixture", 0.2, closed=False)
    elif t == "LV2":
        top = zb + hh
        sh.poly([P(a, 0.0), P(b, 0.0), P(b, top), P(a, top)], "fixture", 0.25)
        sh.line(P(m, 0.08), P(m, top - 0.08), "fixture", 0.13)
        sh.line(P(a, top - 0.06), P(b, top - 0.06), "fixture", 0.13)
    elif t == "MR":
        sh.poly([P(a, zb), P(b, zb), P(b, zb + hh), P(a, zb + hh)], "fixture", 0.3)
        sh.line(P(m - 0.06, zb + hh * 0.55), P(m + 0.04, zb + hh * 0.70), "fixture", 0.1)
        sh.line(P(m - 0.03, zb + hh * 0.50), P(m + 0.07, zb + hh * 0.65), "fixture", 0.1)
    elif t.startswith("SH"):
        sh.circle(P(m, 1.95), 1.8, "fixture", 0.25)
        sh.line(P(m, 1.95), P(m, 1.10), "fixture", 0.2)
        sh.poly([P(m - 0.06, 1.05), P(m + 0.06, 1.05), P(m + 0.06, 1.15), P(m - 0.06, 1.15)], "fixture", 0.25)
    elif t == "SP":
        sh.poly([P(m - 0.03, 0.5), P(m + 0.03, 0.5), P(m + 0.03, 0.62), P(m - 0.03, 0.62)], "fixture", 0.2)
        sh.poly([P(m, 0.5), P(m - 0.05, 0.35), P(m + 0.03, 0.25), P(m + 0.06, 0.40)], "fixture", 0.13, closed=False)
    elif t == "TR":
        sh.line(P(a, zb + 0.03), P(b, zb + 0.03), "fixture", 0.35)
        for x_ in (a, b):
            sh.poly([P(x_ - 0.02, zb - 0.02), P(x_ + 0.02, zb - 0.02), P(x_ + 0.02, zb + 0.06), P(x_ - 0.02, zb + 0.06)],
                    "fixture", 0.2)
    elif t == "TP":
        sh.poly([P(a, zb), P(b, zb), P(b, zb + hh), P(a, zb + hh)], "fixture", 0.2)
        sh.circle(P(m, zb + hh / 2), 1.0, "fixture", 0.13)
    elif t == "BT2":
        sh.poly([P(a + 0.05, 0.0), P(b - 0.05, 0.0), P(b, hh), P(a, hh)], "fixture", 0.25)
    elif t == "UR":
        sh.poly(_ellipse(P(m, 0.75), (b - a) / 2 * (P(1, 0)[0] - P(0, 0)[0]), 0.30 * (P(0, 1)[1] - P(0, 0)[1]),
                         (1, 0), (0, 1)), "fixture", 0.25)
    elif t == "GP":
        sh.poly([P(a, 0.0), P(b, 0.0), P(b, hh), P(a, hh)], "fixture", 0.13)
    else:
        sh.poly([P(a, zb), P(b, zb), P(b, zb + max(hh, 0.05)), P(a, zb + max(hh, 0.05))], "fixture", 0.2)


def fixture_side(sh, P, t, s_wall, sgn, spec):
    """A fitting against a cut wall, seen from its side (it sticks out
    toward the viewer's middle by ``sgn``)."""
    zb, hh, d = float(spec[5]), float(spec[6]), float(spec[4])

    def Q(o, z):
        return P(s_wall + sgn * o, z)
    if t.startswith("WC1"):
        sh.poly([Q(0, 0.40), Q(0.2, 0.40), Q(0.2, 0.75), Q(0, 0.75)], "fixture", 0.25)
        sh.poly([Q(0.12, 0.0), Q(0.42, 0.0), Q(0.66, 0.36), Q(0.68, 0.42), Q(0.16, 0.42), Q(0.16, 0.30)], "fixture", 0.25)
    elif t == "LV" or t.startswith("SK"):
        top = zb + hh
        sh.poly([Q(0, top - 0.05), Q(d, top - 0.05), Q(d, top), Q(0, top)], "fixture", 0.25)
        sh.poly([Q(0.06, top - 0.05), Q(0.12, top - 0.20), Q(d - 0.08, top - 0.20), Q(d - 0.04, top - 0.05)],
                "fixture", 0.2, closed=False)
        sh.line(Q(0.25, top - 0.20), Q(0.25, top - 0.30), "fixture", 0.18)
        sh.poly([Q(0.25, top - 0.30), Q(0.15, top - 0.36), Q(0.0, top - 0.36)], "fixture", 0.18, closed=False)
    elif t == "MR":
        sh.poly([Q(0, zb), Q(0.03, zb), Q(0.03, zb + hh), Q(0, zb + hh)], "fixture", 0.25)
    elif t.startswith("SH"):
        sh.line(Q(0, 1.95), Q(0.15, 1.95), "fixture", 0.2)
        sh.circle(Q(0.17, 1.93), 1.4, "fixture", 0.2)
    elif t == "TR":
        sh.poly([Q(0, zb), Q(0.07, zb), Q(0.07, zb + 0.05), Q(0, zb + 0.05)], "fixture", 0.2)
    elif t == "BT2":
        sh.poly([Q(0.0, 0.0), Q(d, 0.0), Q(d, hh), Q(0.0, hh)], "fixture", 0.25)
    else:
        sh.poly([Q(0, zb), Q(min(d, 0.15), zb), Q(min(d, 0.15), zb + max(hh, 0.05)), Q(0, zb + max(hh, 0.05))],
                "fixture", 0.18)


def bath_sides(E, k, rm) -> list:
    """The two walls the bathroom sections look at: the ones with the most
    fittings (the original: one across the room, one along it)."""
    inner = _inner(E, k, rm)
    fx = [f for f in E["fixtures"] if f["floor"] == k and D._inside(f["fx"], rm)]
    cnt = [sum(1 for f in fx if back_side(f["fx"], inner) == s_) for s_ in range(4)]
    first = max(range(4), key=lambda s_: cnt[s_])
    across = [s_ for s_ in range(4) if s_ % 2 != first % 2]
    second = max(across, key=lambda s_: cnt[s_])
    return [first, second]


def _brick_band(sh, a, b, step=1.1, layer="hatch"):
    """45° hatch inside the paper rectangle a–b (masonry cut)."""
    (xa, ya), (xb, yb) = a, b
    x0, x1, y0, y1 = min(xa, xb), max(xa, xb), min(ya, yb), max(ya, yb)
    s_ = x0 - (y1 - y0)
    while s_ < x1:
        p = (s_, y0)
        q = (s_ + (y1 - y0), y1)
        c = _clip_seg(p, q, (x0, y0, x1, y1))
        if c:
            sh.line(c[0], c[1], layer, 0.1)
        s_ += step


def _concrete(sh, a, b):
    (xa, ya), (xb, yb) = a, b
    x0, x1, y0, y1 = min(xa, xb), max(xa, xb), min(ya, yb), max(ya, yb)
    sh.fill([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], "hatch", 0.82)
    import random as _r
    rnd = _r.Random(int(x0 * 7 + y0 * 13))
    for _i in range(int((x1 - x0) * (y1 - y0) / 6) + 1):
        px, py = x0 + rnd.random() * (x1 - x0), y0 + rnd.random() * (y1 - y0)
        sh.poly([(px, py), (px + 0.5, py + 0.2), (px + 0.15, py + 0.5)], "hatch", 0.1)
    sh.poly([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], "cut", 0.35)


def bath_section(sh, E, k, rm, side, ox, oy, sc, num, ref_sheet, names):
    """รูปตัดห้องน้ำ as the original: the cut walls (hatched, plastered,
    the beam over them), the floor slab and the beams under it, the back
    wall's tiles, its door / window, the fittings (front and side views),
    the ceiling, the heights on the left, the sizes and axes below, the
    room tags — and its title with the section number."""
    kk = 1000.0 / sc
    inner = _inner(E, k, rm)
    x0, y0, x1, y1 = inner
    H = E["H"]
    t = float(E["settings"].get("wall_t") or 0.1)
    zc = B.ceiling_z(E, k) - k * H
    bh = float((E["lib"].get("B1") or {}).get("h", 0.4) or 0.4)
    fin = CAT.finish_of(rm)
    th = min(float(fin.get("tile_h") or 2.0), zc)
    ends = {0: ((x1, y0), (x0, y0)), 1: ((x1, y1), (x1, y0)), 2: ((x0, y1), (x1, y1)), 3: ((x0, y0), (x0, y1))}
    # seen from inside, looking at the wall: left → right
    a_, b_ = ends[side]
    a_, b_ = b_, a_
    import math as _m
    W = _m.dist(a_, b_)
    u = ((b_[0] - a_[0]) / W, (b_[1] - a_[1]) / W)

    def P(s_, z):
        return (ox + s_ * kk, oy + z * kk)

    def S(x, y):
        return (x - a_[0]) * u[0] + (y - a_[1]) * u[1]
    drop = 0.05
    # floor: the room's slab, the next rooms' slabs a step higher, beams under the walls
    _concrete(sh, P(-0.05, -0.10), P(W + 0.05, 0.0))
    for s0, s1 in ((-t - 1.15, -t), (W + t, W + t + 0.45)):
        _concrete(sh, P(s0, drop - 0.10), P(s1, drop))
    for s0, s1 in ((-t - 0.05, 0.05), (W - 0.05, W + t + 0.05)):
        _concrete(sh, P(s0, -0.45), P(s1, drop))
    # the cut walls: masonry hatched between the plaster, the beam over them
    for s0, s1 in ((-t, 0.0), (W, W + t)):
        sh.rect(*P(s0, drop), *P(s1, H - bh), "cut", 0.5)
        _brick_band(sh, P(s0, drop), P(s1, H - bh))
        _concrete(sh, P(s0 - 0.02, H - bh), P(s1 + 0.02, H))
    # the slab / roof beam band over the room
    _concrete(sh, P(-0.05, H - 0.12), P(W + 0.05, H))
    # the back wall: tiles 0.30 to their height, plain above, the ceiling
    z = 0.30
    while z < th - 0.01:
        sh.line(P(0, z), P(W, z), "hatch", 0.1)
        z += 0.30
    sh.line(P(0, th), P(W, th), "wall", 0.25)
    s_ = 0.30
    while s_ < W - 0.01:
        sh.line(P(s_, 0), P(s_, th), "hatch", 0.1)
        s_ += 0.30
    sh.poly([P(0, zc), P(W, zc), P(W, zc + 0.012), P(0, zc + 0.012)], "cut", 0.35)
    ct = E["settings"].get("ceiling_type", "cline")
    keys = list(B.CEILING_TYPES)
    if ct in keys:
        _ceiling_mark(sh, (P(W / 2, 0)[0], P(0, zc + 0.15)[1] + 2), str(keys.index(ct) + 1))
    # the door / window in the back wall
    codes = D.opening_codes(E)
    p0w, p1w = (a_, b_)
    for el in E["openings"]:
        if el["floor"] != k:
            continue
        ox_, oy_ = float(el["op"]["x"]), float(el["op"]["y"])
        dist = abs((ox_ - a_[0]) * (-u[1]) + (oy_ - a_[1]) * u[0])
        if dist > t / 2 + 0.06 or not (-0.05 < S(ox_, oy_) < W + 0.05):
            continue
        sc_ = S(ox_, oy_)
        lo = el["sill"] if el["type"] == "window" else 0.0
        sh.fill([P(sc_ - el["w"] / 2, lo), P(sc_ + el["w"] / 2, lo), P(sc_ + el["w"] / 2, lo + el["h"]),
                 P(sc_ - el["w"] / 2, lo + el["h"])], "mask", 1.0)
        elev_opening(sh, P, sc_, lo, el, D.op_code(el, codes))
    # the fittings: on the back wall from the front, on the cut walls from the side
    fx = [f for f in E["fixtures"] if f["floor"] == k and D._inside(f["fx"], rm)]
    keyz = set()
    left_side, right_side = (side + 3) % 4, (side + 1) % 4
    for f in fx:
        tt = str(f["fx"].get("type", ""))
        spec = D.fixture_spec(tt)
        if not spec or tt == "FD":
            continue
        ff = fit_inside(f["fx"], inner)
        bs = back_side(ff, inner)
        w_ = float(spec[3])
        sc_ = S(float(ff["x"]), float(ff["y"]))
        if bs == side:
            zb_, hh_ = float(spec[5]), max(float(spec[6]), 0.05)
            box = (sc_ - w_ / 2, zb_, sc_ + w_ / 2, zb_ + hh_)
            if tt.startswith("WC1"):
                box = (sc_ - 0.23, 0.0, sc_ + 0.23, 0.76)
            elif tt == "LV" or tt.startswith("SK"):
                box = (sc_ - w_ / 2, zb_ + hh_ - 0.22, sc_ + w_ / 2, zb_ + hh_)
            if not tt.startswith(("SH", "SP", "TR")):     # the fitting hides the tiles behind it
                sh.fill([P(box[0], box[1]), P(box[2], box[1]), P(box[2], box[3]), P(box[0], box[3])], "mask", 1.0)
            fixture_front(sh, P, tt, sc_ - w_ / 2, sc_ + w_ / 2, spec)
            lab_z = float(spec[5]) + float(spec[6]) + 0.05 if not tt.startswith("SH") else 2.05
            q = P(sc_ + w_ / 2, lab_z)
            sh.text((q[0] + 0.6, q[1]), FIX_LABEL.get(tt, tt), 1.9, "left", "fixture")
        elif bs in (left_side, right_side):
            s_wall, sgn = (GAP, 1) if bs == left_side else (W - GAP, -1)
            dpt = float(spec[4])
            if tt.startswith(("WC1", "LV", "SK", "BT")):
                ztop = 0.76 if tt.startswith("WC1") else float(spec[5]) + float(spec[6])
                zbot = 0.0 if tt.startswith(("WC1", "BT")) else ztop - 0.36
                ea, eb = sorted((s_wall, s_wall + sgn * (0.70 if tt.startswith("WC1") else dpt)))
                sh.fill([P(ea, zbot), P(eb, zbot), P(eb, ztop), P(ea, ztop)], "mask", 1.0)
            fixture_side(sh, P, tt, s_wall, sgn, spec)
        else:
            continue
        if tt.startswith("LV") or tt.startswith("SK"):
            keyz.add(round(float(spec[5]) + float(spec[6]), 2))
        if tt == "MR":
            keyz |= {round(float(spec[5]), 2), round(float(spec[5]) + float(spec[6]), 2)}
    # the heights on the left: the fittings' heights, the tiles, the ceiling
    def chain(xmm, zs):
        zs = sorted(set(zs))
        for za, zb in zip(zs, zs[1:]):
            pa, pb = P(0, za)[1], P(0, zb)[1]
            sh.line((xmm, pa), (xmm, pb), "dim", 0.13)
            for yq in (pa, pb):
                sh.line((xmm - 0.7, yq - 0.7), (xmm + 0.7, yq + 0.7), "dim", 0.25)
                sh.line((xmm - 1.2, yq), (xmm + 1.2, yq), "dim", 0.13)
            sh.text((xmm - 0.9, (pa + pb) / 2), f"{zb - za:.2f}", 2.0, "center", "dim", angle=90)
    xl = P(-t - 1.15, 0)[0]
    chain(xl - 8, [0.0] + [z_ for z_ in keyz if 0 < z_ < zc] + [th, zc])
    chain(xl - 15, [0.0, th, zc])
    chain(xl - 22, [0.0, zc])
    # sizes and axes below
    yb = P(0, -0.45)[1] - 9
    xs_ = [P(-t, 0)[0], P(0, 0)[0], P(W, 0)[0], P(W + t, 0)[0]]
    for xa, xb, val in zip(xs_, xs_[1:], (t, W, t)):
        sh.line((xa, yb), (xb, yb), "dim", 0.13)
        sh.text(((xa + xb) / 2, yb + 0.9), f"{val:.2f}", 1.9, "center", "dim")
    for x_ in xs_:
        sh.line((x_ - 0.7, yb - 0.7), (x_ + 0.7, yb + 0.7), "dim", 0.25)
        sh.line((x_, yb - 1.2), (x_, yb + 1.2), "dim", 0.13)
    yb2 = yb - 5.5
    xa, xb = P(-t / 2, 0)[0], P(W + t / 2, 0)[0]
    sh.line((xa, yb2), (xb, yb2), "dim", 0.13)
    for x_ in (xa, xb):
        sh.line((x_ - 0.7, yb2 - 0.7), (x_ + 0.7, yb2 + 0.7), "dim", 0.25)
        sh.line((x_, yb2 - 1.2), (x_, yb2 + 1.2), "dim", 0.13)
    sh.text(((xa + xb) / 2, yb2 + 0.9), f"{W + t:.2f}", 1.9, "center", "dim")
    gx, gy = D.grids(E)
    axes = []
    for s_w, pt in ((-t / 2, a_), (W + t / 2, b_)):
        px, py = pt[0] - u[0] * t / 2 * (1 if s_w < 0 else -1), pt[1] - u[1] * t / 2 * (1 if s_w < 0 else -1)
        for i, g in enumerate(gx):
            if abs(u[0]) > 0.5 and abs(px - g) < 0.03:
                axes.append((s_w, str(i + 1)))
        for j, g in enumerate(gy):
            if abs(u[1]) > 0.5 and abs(py - g) < 0.03:
                axes.append((s_w, D.axis_name(j)))
    for s_w, nm in axes:
        x_ = P(s_w, 0)[0]
        sh.line((x_, yb2 - 2), (x_, yb2 - 7), "grid", 0.13, True)
        sh.circle((x_, yb2 - 10.2), 3.2, "grid", 0.25)
        sh.text((x_, yb2 - 11.3), nm, 2.6, "center", "grid")
    # wall tags on the cut walls, the room tags
    for s_w in (0.25, W - 0.25):
        D.wall_tag(sh, P(s_w, 2.25), 3, 1.9)
    sl = next(s_ for s_ in E["slabs"] if s_["room"] is rm)
    busy = []
    for f in fx:
        tt = str(f["fx"].get("type", ""))
        sp_ = D.fixture_spec(tt)
        ff = fit_inside(f["fx"], inner)
        if sp_ and back_side(ff, inner) == side and float(sp_[5]) < 1.0:
            c_ = S(float(ff["x"]), float(ff["y"]))
            busy.append((c_ - float(sp_[3]) / 2 - 0.1, c_ + float(sp_[3]) / 2 + 0.1))
    free, s0 = [], 0.35
    for lo_b, hi_b in sorted(busy) + [(W - 0.35, W)]:
        free.append((lo_b - s0, (s0 + lo_b) / 2))
        s0 = max(s0, hi_b)
    best = max(free) if free else (0, W / 2)
    room_tag(sh, P(best[1] if best[0] > 0.9 else W * 0.5, 0.42), E, rm, sl, D.finish_codes(E), knockout=True)
    # the next room's tag outside the left wall, on its floor
    mid_l = (a_[0] - u[0] * (t + 0.6) , a_[1] - u[1] * (t + 0.6))
    nb = next((r_ for r_ in E["floors"][k]["rooms"] if r_ is not rm and
               r_["x"] - 0.01 <= mid_l[0] <= r_["x"] + r_["w"] + 0.01 and
               r_["y"] - 0.01 <= mid_l[1] <= r_["y"] + r_["d"] + 0.01), None)
    if nb is not None:
        sl_n = next((s_ for s_ in E["slabs"] if s_["room"] is nb), None)
        if sl_n is not None:
            room_tag(sh, P(-t - 0.6, drop + 0.45), E, nb, sl_n, D.finish_codes(E))
    # the title: name, rule, scale and the section number in its triangle
    cx = P(W / 2, 0)[0] - 45
    caption_marks(sh, (cx, yb2 - 22), f"รูปตัดห้องน้ำ {names}", f"1:{sc}", None, None, 90.0)
    tx, ty = cx + 96, yb2 - 20
    sh.poly([(tx - 5, ty - 2.5), (tx + 5, ty - 2.5), (tx, ty + 5.5)], "text", 0.35)
    sh.circle((tx, ty - 2.5), 3.4, "text", 0.25)
    sh.text((tx, ty - 1.9), str(num), 2.6, "center", "text", True)


# ---------------------------------------------------------------------------
# A5-3 — แบบขยายบันได ST.n: the plans sheet and the section + details sheet
# ---------------------------------------------------------------------------

def _region_walls(E, k, box, t):
    """The walls of floor ``k`` near ``box`` (x0, y0, x1, y1), as an E copy."""
    x0, y0, x1, y1 = box
    near = [w for w in E["walls"] if w["floor"] == k and
            min(w["p0"][0], w["p1"][0]) <= x1 and max(w["p0"][0], w["p1"][0]) >= x0 and
            min(w["p0"][1], w["p1"][1]) <= y1 and max(w["p0"][1], w["p1"][1]) >= y0]
    cols = [c for c in E["columns"] if c["floor"] == k and x0 - 0.3 <= c["x"] <= x1 + 0.3 and
            y0 - 0.3 <= c["y"] <= y1 + 0.3]
    return dict(E, walls=near, columns=cols)


def stair_plan_view(sh, E, e, k, box, sc, upper, sec_ref, num):
    """One floor's plan round the stair at ``sc``: walls (hatched) and doors,
    the stair (numbered treads, ขึ้น / ลง), the tread chain «n @ g = L»,
    the overall sizes, axes, room tags and the section's cut ①."""
    s = E["settings"]
    t = float(s.get("wall_t") or 0.1)
    lay = B.stair_layout(e["st"], s)
    rx = [p[0] for p in lay["rect"]]
    ry = [p[1] for p in lay["rect"]]
    m = 1.0
    reg = (min(rx) - m, min(ry) - m, max(rx) + m, max(ry) + m)
    for rm_ in E["floors"][k]["rooms"]:              # the whole room the stair stands in
        cx_, cy_ = (min(rx) + max(rx)) / 2, (min(ry) + max(ry)) / 2
        if rm_["x"] <= cx_ <= rm_["x"] + rm_["w"] and rm_["y"] <= cy_ <= rm_["y"] + rm_["d"]:
            reg = (min(reg[0], rm_["x"] - 0.6), min(reg[1], rm_["y"] - 0.6),
                   max(reg[2], rm_["x"] + rm_["w"] + 0.6), max(reg[3], rm_["y"] + rm_["d"] + 0.6))
    bx0, by0, bx1, by1 = box
    kk = 1000.0 / sc
    cx, cy = (bx0 + bx1) / 2 - 10, (by0 + by1) / 2 - 6
    v = D.View(sh, sc, ((reg[0] + reg[2]) / 2, (reg[1] + reg[3]) / 2), (cx, cy))
    pa, pb = v(reg[0], reg[1]), v(reg[2], reg[3])
    clip = (pa[0], pa[1], pb[0], pb[1])
    E2 = _region_walls(E, k, reg, t)
    n0 = len(sh.items)
    D.draw_walls(sh, v, E2, k, t, D.opening_codes(E), tags=False)
    for w in E2["walls"]:
        (ax, ay), (bx_, by_) = w["p0"], w["p1"]
        Lw = w["L"]
        if Lw < 0.05:
            continue
        ux, uy = (bx_ - ax) / Lw, (by_ - ay) / Lw
        _brick_band(sh, v(ax - uy * t / 2, ay + ux * t / 2), v(bx_ + uy * t / 2, by_ - ux * t / 2), 1.2)
    n1_ = len(sh.items)
    D.draw_stairs(sh, v, E, k)
    for i_, it in enumerate(sh.items[n1_:], n1_):        # sharper: steps 0.3, outline 0.5
        dashed = it[0] == "line" and it[4] or it[0] == "poly" and it[5]
        if dashed:
            continue
        if it[0] in ("line", "poly") and it[2] == "wall":
            sh.items[i_] = it[:3] + (0.5 if it[0] == "poly" else 0.3,) + it[4:]
        elif it[0] in ("line", "poly") and it[2] == "door":
            sh.items[i_] = it[:3] + (0.4,) + it[4:]
    sh.items[n0:] = clip_items(sh.items[n0:], clip)
    # tread numbers and the chain along the first flight (ground) / second (upper)
    fl = lay["flights"]
    show = fl                                     # every flight numbered and dimensioned (the original)
    first_no = 1
    g = lay["g"]
    no = first_no
    for f in show:
        (px, py), (dx, dy) = f["p0"], f["d"]
        for i in range(f["n"]):
            u = (i + 0.5) * g
            q = v(px + dx * u, py + dy * u)
            sh.text((q[0], q[1] - 0.8), str(no), 2.0, "center")
            no += 1
        # the chain beside the flight (on the side away from the other flight)
        nx, ny = -dy, dx
        side = 1.0 if (nx * (px - (min(rx) + max(rx)) / 2) + ny * (py - (min(ry) + max(ry)) / 2)) > 0 else -1.0
        off = f["w"] / 2 + 0.45
        bx_, by_ = px + nx * off * side, py + ny * off * side
        pts = [(bx_ + dx * g * i, by_ + dy * g * i) for i in range(f["n"] + 1)]
        # every tread: a tick and its 0.25 written across the chain (the original)
        a0, a1 = v(*pts[0]), v(*pts[-1])
        sh.line(a0, a1, "dim", 0.13)
        sgn_out = 1.0 if (v(bx_ + nx * side, by_ + ny * side)[0] - a0[0]) + (v(bx_ + nx * side, by_ + ny * side)[1] - a0[1]) > 0 else -1.0
        for i_, p_ in enumerate(pts):
            q = v(*p_)
            sh.line((q[0] - 0.7, q[1] - 0.7), (q[0] + 0.7, q[1] + 0.7), "dim", 0.25)
            if abs(dx) > abs(dy):
                sh.line((q[0], q[1] - 1.2), (q[0], q[1] + 1.2), "dim", 0.13)
            else:
                sh.line((q[0] - 1.2, q[1]), (q[0] + 1.2, q[1]), "dim", 0.13)
            if i_ < len(pts) - 1:
                c = v((p_[0] + pts[i_ + 1][0]) / 2, (p_[1] + pts[i_ + 1][1]) / 2)
                if abs(dx) > abs(dy):
                    sh.text((c[0] + 0.7, c[1] + nx * 0 + (1.3 if ny * side > 0 else -1.3)), f"{g:.2f}", 1.6,
                            "left" if ny * side > 0 else "right", "dim", angle=90)
                else:
                    out_r = c[0] > v((min(rx) + max(rx)) / 2, 0)[0]      # the chain right of the stair
                    sh.text((c[0] + (1.3 if out_r else -1.3), c[1] - 0.6), f"{g:.2f}", 1.6,
                            "left" if out_r else "right", "dim")
        if abs(dx) > abs(dy):
            mid = v((pts[0][0] + pts[-1][0]) / 2, by_ + ny * side * 0.42)
        else:
            cxp = v(bx_, 0)[0] > v((min(rx) + max(rx)) / 2, 0)[0]
            mid = v(bx_ + (0.62 if cxp else -0.62), (pts[0][1] + pts[-1][1]) / 2)
        if abs(dx) > abs(dy):
            sh.text((mid[0], mid[1] - 0.8), f"{f['n']} @ {g:.2f} = {f['n'] * g:.2f}", 2.0, "center", "dim")
        else:                                            # under the chain's foot, level (no clash with walls)
            lo_ = min(v(*pts[0])[1], v(*pts[-1])[1])
            sh.text((v(bx_, 0)[0], lo_ - 4.0), f"{f['n']} @ {g:.2f} = {f['n'] * g:.2f}", 2.0, "center", "dim")
    # the stair's overall sizes and the axes in the picture
    D.dim_chain(sh, v, [min(rx), max(rx)], min(ry) - 0.6, "x")
    xs, ys = D.grids(E)
    for i, gx in enumerate(xs):
        if reg[0] <= gx <= reg[2]:
            a, b = v(gx, reg[1]), v(gx, reg[3] + 0.3)
            sh.line(a, b, "grid", 0.13, True)
            sh.circle((b[0], b[1] + 3.2), 3.2, "grid", 0.25)
            sh.text((b[0], b[1] + 2.1), str(i + 1), 2.6, "center", "grid")
    for j, gy in enumerate(ys):
        if reg[1] <= gy <= reg[3]:
            a, b = v(reg[0] - 0.3, gy), v(reg[2], gy)
            sh.line(a, b, "grid", 0.13, True)
            sh.circle((a[0] - 3.2, a[1]), 3.2, "grid", 0.25)
            sh.text((a[0] - 3.2, a[1] - 1.0), D.axis_name(j), 2.6, "center", "grid")
    # the room the stair stands in
    for sl in (x for x in E["slabs"] if x["floor"] == k):
        rm = sl["room"]
        if rm["x"] <= (min(rx) + max(rx)) / 2 <= rm["x"] + rm["w"] and rm["y"] <= (min(ry) + max(ry)) / 2 <= rm["y"] + rm["d"]:
            room_tag(sh, v(*tag_spot(E, k, rm)), E, rm, sl, D.finish_codes(E), knockout=True)
            break
    # the cut ① through the first flight, looking along the run
    f0 = fl[0]
    (px, py), (dx, dy) = f0["p0"], f0["d"]
    if abs(dy) > abs(dx):
        a, b = v(px, reg[1] + 0.2), v(px, reg[3] - 0.2)
        sh.line(a, b, "grid", 0.3, True)
        section_mark(sh, (b[0], b[1] + 4), "1", sec_ref, (1.0, 0.0))
    else:
        a, b = v(reg[0] + 0.2, py), v(reg[2] - 0.2, py)
        sh.line(a, b, "grid", 0.3, True)
        section_mark(sh, (b[0] + 4, b[1]), "1", sec_ref, (0.0, 1.0))
    return v


def a_stair_plans(sh, E, e, idx, sheets=None):
    """แบบขยายบันได ST.n (แปลน): the floor below and the floor above, each
    1:50, one over the other (the original)."""
    x0, y0, x1, y1 = D.drawing_area()
    mid = (y0 + y1) / 2
    sh.line((x0, mid), (x1, mid), "frame", 0.25)
    k = e["floor"]
    ref = sheet_ref([s_ for s_ in (sheets or []) if s_.title.startswith(f"แบบขยายบันได ST.{idx} (รูปตัด")], "")
    for j, (kf, upper, box) in enumerate(((k, False, (x0, mid, x1, y1)), (k + 1, True, (x0, y0, x1, mid)))):
        if kf >= E["n"]:
            continue
        stair_plan_view(sh, E, e, kf, (box[0], box[1] + 18, box[2] - 80, box[3]), 50, upper, ref, 1)
        caption_marks(sh, (box[2] - 120, box[1] + 22), f"แปลนชั้น {kf + 1} บันได ST.{idx}", "1:50", None, None, 95.0)
    sh.scale = "1:50"
    return 50


def a_stair_section(sh, E, e, idx):
    """แบบขยายบันได ST.n (รูปตัด): the section ① through the stair at 1:50
    with every riser counted «n @ R = H», the landing, the floors, the
    railing and the detail tags; beside it the details ① railing,
    ② the rail's fixing, ③ the steps, at 1:25 (the original)."""
    s = E["settings"]
    lay = B.stair_layout(e["st"], s)
    R_, g, H = lay["R"], lay["g"], lay["H"]
    fl = lay["flights"]
    n1 = fl[0]["n"]
    L1 = n1 * g
    land = lay["w"] if len(fl) > 1 else 0.0
    ts = float(e["st"].get("t") or s.get("stair_t") or 0.15)
    import math as _m
    ang = _m.atan2(R_, g)
    off = ts / _m.cos(ang)
    x0, y0, x1, y1 = D.drawing_area()
    xm = x0 + (x1 - x0) * 0.62
    sh.line((xm, y0), (xm, y1), "frame", 0.25)
    sc = next((s_ for s_ in (25, 30, 40, 50) if (L1 + land + 2.5) * 1000 / s_ <= (xm - x0) - 62
               and (H + 1.2) * 1000 / s_ <= (y1 - y0) - 60), 50)
    kk = 1000.0 / sc
    ox = x0 + 40 + ((xm - x0) - 62 - (L1 + land + 2.5) * kk) / 2 + 1.9 * kk
    oy = y0 + 52 + ((y1 - y0) - 60 - (H + 1.2) * kk) / 2 + 0.45 * kk

    def P(u, z):
        return (ox + u * kk, oy + z * kk)
    # floors: below, the landing, above (with the opening)
    _concrete(sh, P(-1.9, -0.12), P(0.0, 0.0))
    _concrete(sh, P(-0.25, -0.45), P(0.05, 0.0))
    if land:
        _concrete(sh, P(L1 - g * 0.0, n1 * R_ - ts), P(L1 + land, n1 * R_))
    _concrete(sh, P(L1 + land - 0.05, H - 0.12), P(L1 + land + 1.0, H))
    if len(fl) > 1:
        _concrete(sh, P(-1.9, H - 0.12), P(L1 - (fl[1]["n"]) * g, H))
    # flight 1 cut: a heavy outline (steps and waist), the tread finish with its
    # nosing on every step — the original's sharp line work; flight 2 beyond
    top = [P(0.0, 0.0)]
    for i in range(n1):
        top += [P(i * g, (i + 1) * R_), P((i + 1) * g, (i + 1) * R_)]
    poly = top + [P(L1, n1 * R_ - off), P(g * 0.6, -0.0)]
    sh.fill(poly, "hatch", 0.92)
    sh.poly(poly, "cut", 0.6)
    for i in range(n1):                                  # tread finish + nosing
        z_ = (i + 1) * R_
        sh.poly([P(i * g - 0.025, z_), P(i * g - 0.025, z_ + 0.025), P((i + 1) * g, z_ + 0.025)],
                "cut", 0.3, closed=False)
    if len(fl) > 1:
        n2 = fl[1]["n"]
        z = n1 * R_
        pts = [P(L1, z)]
        u = L1
        for j in range(n2):
            pts += [P(u, z + (j + 1) * R_), P(u - g, z + (j + 1) * R_)]
            u -= g
        sh.poly(pts, "wall", 0.35, closed=False)
        for j in range(n2):
            uu = L1 - j * g
            z_ = z + (j + 1) * R_
            sh.line(P(uu + 0.025, z_ + 0.025), P(uu - g, z_ + 0.025), "wall", 0.2)
        sh.line(P(L1, z - off * 0.3), P(L1 - n2 * g, H - off), "wall", 0.25, True)
    # the riser levels: dashed lines from the ruler to each step (the original)
    xl_ = P(-1.9, 0)[0] - 4
    for i in range(1, lay["n"]):
        zq = i * R_
        if i <= n1:
            u_end = (i - 1) * g
        else:
            u_end = L1 - (i - n1 - 1) * g
        sh.line((xl_ + 1.5, P(0, zq)[1]), (P(u_end, 0)[0] - 1.0, P(0, zq)[1]), "grid", 0.1, True)
    # the railing: the rail 0.90 above the nosings, a baluster on every tread
    hr = B.RAIL_H
    for dz in (0.0, 0.10):
        sh.line(P(0.0, R_ + hr - dz), P(L1, n1 * R_ + R_ + hr - dz), "door", 0.4)
    for i in range(n1):
        u = (i + 0.5) * g
        sh.line(P(u, (i + 1) * R_ + 0.025), P(u, (i + 1.5) * R_ + hr - 0.10), "door", 0.25)
    for uq, zq in ((0.0, R_), (L1, n1 * R_)):
        sh.rect(*P(uq - 0.02, zq), *P(uq + 0.02, zq + R_ + hr + 0.03), "door", 0.4)
    # numbers on the treads
    for i in range(n1):
        q = P((i + 0.5) * g, (i + 1) * R_ + 0.05)
        sh.text(q, str(i + 1), 1.8, "center")
    if len(fl) > 1:
        u = L1
        for j in range(fl[1]["n"]):
            q = P(u - 0.5 * g, n1 * R_ + (j + 1) * R_ + 0.05)
            sh.text(q, str(n1 + j + 1), 1.8, "center")
            u -= g
    # every riser counted on the left, the total, the levels
    xl = P(-1.9, 0)[0] - 4
    n = lay["n"]
    for i in range(n):
        a, b = P(0, i * R_)[1], P(0, (i + 1) * R_)[1]
        sh.line((xl, a), (xl, b), "dim", 0.13)
        sh.line((xl - 0.6, a - 0.6), (xl + 0.6, a + 0.6), "dim", 0.2)
        sh.text((xl - 1.0, (a + b) / 2 - 0.7), f"{R_:.4f}".rstrip("0"), 1.7, "right", "dim")
    sh.line((xl - 0.6, P(0, H)[1] - 0.6), (xl + 0.6, P(0, H)[1] + 0.6), "dim", 0.2)
    xt = xl - 13
    sh.line((xt, P(0, 0)[1]), (xt, P(0, H)[1]), "dim", 0.13)
    for zq in (0.0, H):
        q = P(0, zq)[1]
        sh.line((xt - 0.7, q - 0.7), (xt + 0.7, q + 0.7), "dim", 0.25)
    sh.text((xt - 1.0, (P(0, 0)[1] + P(0, H)[1]) / 2), f"{n} @ {R_:.4f}".rstrip("0") + f" = {H:.2f}", 2.0,
            "center", "dim", angle=90)
    for zq, lab in ((0.0, "ระดับพื้นชั้นล่าง"), (n1 * R_, "ระดับพื้นชานพัก"), (H, "ระดับพื้นชั้นบน")):
        q = (xl + 2.5, P(0, zq)[1])                     # on the left over the riser lines (the original)
        sh.poly([(q[0] + 3, q[1]), (q[0] + 1.6, q[1] + 2.2), (q[0] + 4.4, q[1] + 2.2)], "dim", 0.25)
        sh.text((q[0] + 5.2, q[1] + 0.8), f"{'±' if zq == 0 else '+'}{zq:.2f} {lab}", 2.2, "left", "dim")
    # the tread chain below and the overall
    yb = P(0, -0.45)[1] - 9
    for i in range(n1 + 1):
        xq = P(i * g, 0)[0]
        sh.line((xq - 0.6, yb - 0.6), (xq + 0.6, yb + 0.6), "dim", 0.2)
        sh.line((xq, yb - 1.2), (xq, yb + 1.2), "dim", 0.13)
    sh.line(P(0, 0)[0:1] + (yb,), (P(L1, 0)[0], yb), "dim", 0.13)
    for i in range(n1):                              # each going written up the chain (the original)
        sh.text((P((i + 0.5) * g, 0)[0] + 0.7, yb + 1.2), f"{g:.2f}", 1.8, "left", "dim", angle=90)
    for i in range(n1 + 1):                          # the treads' edges dashed down to the chain
        top_z = i * R_ if i else 0.0
        sh.line(P(i * g, top_z), (P(i * g, 0)[0], yb + 1.2), "grid", 0.1, True)
    # flight 2's treads too (beyond), dashed to a second chain
    if len(fl) > 1:
        n2 = fl[1]["n"]
        yb2_ = yb + 0.0
        u0_ = L1 - n2 * g
        for j in range(n2 + 1):
            xq = P(L1 - j * g, 0)[0]
            sh.line((xq, P(0, n1 * R_ + j * R_)[1]), (xq, P(0, n1 * R_ - ts - 0.05)[1]), "grid", 0.08, True)
    sh.text((P(L1 / 2, 0)[0], yb - 4.2), f"{n1} @ {g:.2f} = {L1:.2f}", 2.2, "center", "dim")
    if land:
        sh.line((P(L1, 0)[0], yb), (P(L1 + land, 0)[0], yb), "dim", 0.13)
        sh.text((P(L1 + land / 2, 0)[0], yb + 0.9), f"{land:.2f}", 1.8, "center", "dim")
        sh.line((P(L1 + land, 0)[0] - 0.6, yb - 0.6), (P(L1 + land, 0)[0] + 0.6, yb + 0.6), "dim", 0.2)
    # the detail tags ① ② ③ as the original: a dash-dot circle round the place,
    # a leader with an arrow, «ดูแบบขยาย» on a rule ending in the split circle
    import math as _m2
    xr_ = P(L1 + land + 1.0, 0)[0] + 3
    for no, (u, z), r_, ty in ((1, (L1, n1 * R_ + R_ + hr * 0.6), 4.5, P(0, H + 0.45)[1]),
                               (2, (L1 * 0.5, n1 * R_ * 0.5 + R_ + hr * 0.7), 4.0, P(0, n1 * R_ + 0.75)[1]),
                               (3, (g * 0.6, R_ * 1.2), 6.0, P(0, n1 * R_ * 0.55)[1])):
        q = P(u, z)
        sh.poly([(q[0] + r_ * _m2.cos(a / 24 * 2 * _m2.pi), q[1] + r_ * _m2.sin(a / 24 * 2 * _m2.pi)) for a in range(24)],
                "text", 0.18, True, True)
        a_ = (q[0] + r_ * 0.75, q[1] + r_ * 0.66)
        sh.line(a_, (xr_, ty), "text", 0.13)
        ux_, uy_ = a_[0] - xr_, a_[1] - ty
        L_ = _m2.hypot(ux_, uy_) or 1
        ux_, uy_ = ux_ / L_, uy_ / L_
        sh.fill([a_, (a_[0] - ux_ * 2.2 + uy_ * 0.7, a_[1] - uy_ * 2.2 - ux_ * 0.7),
                 (a_[0] - ux_ * 2.2 - uy_ * 0.7, a_[1] - uy_ * 2.2 + ux_ * 0.7)], "hatch", 0.0)
        sh.line((xr_, ty), (xr_ + 20, ty), "text", 0.18)
        sh.text((xr_ + 1, ty + 0.8), "ดูแบบขยาย", 2.2)
        c_ = (xr_ + 24, ty)
        sh.circle(c_, 3.6, "text", 0.3)
        sh.line((c_[0] - 3.6, c_[1]), (c_[0] + 3.6, c_[1]), "text", 0.2)
        sh.text((c_[0], c_[1] + 0.6), str(no), 2.4, "center", "text", True)
    caption_marks(sh, (x0 + 30, y0 + 16), f"รูปตัดบันได ST.{idx}", f"1:{sc}", None, None, 110.0)
    tx, ty = x0 + 30 + 116, y0 + 18
    sh.poly([(tx - 5, ty - 2.5), (tx + 5, ty - 2.5), (tx, ty + 5.5)], "text", 0.35)
    sh.text((tx, ty - 1.9), "1", 2.6, "center", "text", True)
    # ---- the details at 1:25 on the right --------------------------------------------------
    k2 = 1000.0 / 25
    bx = xm + 8
    hh = (y1 - y0) / 3

    def title(y, no, scale="1:25"):
        caption_marks(sh, (bx + 10, y + 8), "แบบขยาย", scale, None, None, 100.0)
        sh.circle((bx + 118, y + 8.5), 3.4, "text", 0.25)
        sh.text((bx + 118, y + 7.6), str(no), 2.4, "center", "text", True)
    # ① the railing: post, rail, balusters and their heights
    yb1 = y0 + 2 * hh + 16
    Q = lambda u, z: (bx + 60 + u * k2, yb1 + z * k2)          # noqa: E731
    _concrete(sh, Q(-0.1, -0.15), Q(0.8, 0.0))
    sh.rect(*Q(-0.02, 0.0), *Q(0.02, hr), "door", 0.35)
    sh.rect(*Q(-0.025, hr), *Q(0.025, hr + 0.10), "door", 0.35)          # the rail 2"x4" flat
    heights = [0.0, 0.20, 0.35, 0.50, 0.65, hr]
    for z in heights[1:-1]:
        sh.rect(*Q(-0.012, z - 0.012), *Q(0.012, z + 0.012), "door", 0.25)
    for za, zb in zip(heights, heights[1:]):
        a, b = Q(-0.35, za)[1], Q(-0.35, zb)[1]
        xq = Q(-0.35, 0)[0]
        sh.line((xq, a), (xq, b), "dim", 0.13)
        sh.line((xq - 0.6, a - 0.6), (xq + 0.6, a + 0.6), "dim", 0.2)
        sh.text((xq - 1.0, (a + b) / 2 - 0.7), f"{zb - za:.2f}", 1.8, "right", "dim")
    xq = Q(-0.6, 0)[0]
    sh.line((xq, Q(0, 0)[1]), (xq, Q(0, hr)[1]), "dim", 0.13)
    sh.text((xq - 0.9, Q(0, hr / 2)[1]), f"{hr:.2f}", 1.9, "center", "dim", angle=90)
    for z, lab in ((hr + 0.05, "ราวบันไดไม้เนื้อแข็ง 2\"x4\" วางนอน"), (0.5, "ลูกกรงเหล็กแป๊บดำ 1\" ทาสี"),
                   (0.2, "เหล็กแป๊บ 1\" x 2\" ยึดพื้น")):
        q = Q(0.03, z)
        sh.line(q, (q[0] + 16, q[1]), "text", 0.13)
        sh.text((q[0] + 17, q[1] - 0.7), lab, 1.9)
    title(y0 + 2 * hh, 1)
    # ② the rail fixed to a flat bar on the post, bolted
    yb2 = y0 + hh + 18
    Q2 = lambda u, z: (bx + 40 + u * k2 * 2.5, yb2 - 14 + z * k2 * 2.5)     # noqa: E731
    sh.rect(*Q2(0.0, 0.30), *Q2(0.10, 0.35), "door", 0.35)
    sh.line(Q2(0.0, 0.325), Q2(0.10, 0.325), "door", 0.1)
    sh.rect(*Q2(0.035, 0.12), *Q2(0.065, 0.30), "door", 0.3)
    sh.circle(Q2(0.05, 0.22), 0.9, "door", 0.2)
    for lab, z in (("เหล็กแบน (FB) ขนาด 1\" หนา 6 มม. ทาสีน้ำมัน", 0.20), ("BOLT Ø 10 มม.", 0.14),
                   ("ราวบันไดไม้เนื้อแข็ง 2\"x4\" วางนอน", 0.33)):
        q = Q2(0.10, z)
        sh.line(q, (q[0] + 14, q[1]), "text", 0.13)
        sh.text((q[0] + 15, q[1] - 0.7), lab, 1.9)
    D.dim_chain(sh, lambda x_, y_: Q2(x_, y_), [0.0, 0.10], 0.40, "x")
    title(y0 + hh, 2, "1:10")
    # ③ the steps: tread and riser finishes, the nosing
    yb3 = y0 + 34
    k2 = 1000.0 / 15
    Q3 = lambda u, z: (bx + 34 + u * k2, yb3 + z * k2)            # noqa: E731
    pts = [Q3(-0.1, 0.0)]
    for i in range(3):
        pts += [Q3(i * g, (i + 1) * R_), Q3((i + 1) * g, (i + 1) * R_)]
    sh.fill(pts + [Q3(2 * g, 3 * R_ - off), Q3(-0.1, -off)], "hatch", 0.92)
    sh.poly(pts, "cut", 0.6, closed=False)
    sh.line(Q3(-0.1, -off), Q3(2 * g, 3 * R_ - off), "cut", 0.6)
    for i in range(3):
        sh.rect(*Q3(i * g - 0.025, (i + 1) * R_), *Q3((i + 1) * g, (i + 1) * R_ + 0.025), "door", 0.35)
        sh.rect(*Q3(i * g - 0.025, i * R_ + 0.025), *Q3(i * g, (i + 1) * R_), "door", 0.3)
    D.dim_chain(sh, lambda x_, y_: Q3(x_, y_), [i * g for i in range(4)], -0.25, "x")
    D.dim_chain(sh, lambda x_, y_: Q3(x_, y_), [i * R_ for i in range(4)], -0.25, "y")
    for lab, (u, z) in (("ลูกนอนหนา 1\" จมูกยื่น 0.025 ม.", (2.5 * g, 3 * R_ + 0.03)),
                        ("ลูกตั้งหนา 1\"", (2 * g, 2.5 * R_))):
        q = Q3(u, z)
        sh.line(q, (q[0] + 10, q[1] + 4), "text", 0.13)
        sh.text((q[0] + 11, q[1] + 3.3), lab, 1.9)
    title(y0, 3, "1:15")
    sh.scale = "ตามระบุ"
    return 50


# ---------------------------------------------------------------------------
# แบบขยายราวกันตก — the guard rail round the stair opening (as the
# original's balcony rail sheet: front elevation and section at 1:25)
# ---------------------------------------------------------------------------

def a_guardrail(sh, E):
    s = E["settings"]
    x0, y0, x1, y1 = D.drawing_area()
    xm = (x0 + x1) / 2
    sh.line((xm, y0), (xm, y1), "frame", 0.25)
    hr = B.RAIL_H
    k = 1000.0 / 25
    t = float((E["lib"].get("S1") or {}).get("t", 0.12) or 0.12)
    # ---- front elevation: a 2.40 m run between two posts --------------------
    Lr = 2.40
    ox, oy = x0 + 34, y0 + 110

    def P(u, z):
        return (ox + u * k, oy + z * k)
    _concrete(sh, P(-0.3, -t), P(Lr + 0.3, 0.0))
    for uq in (0.0, Lr):                                     # the posts 2"x2"
        sh.rect(*P(uq - 0.025, 0.0), *P(uq + 0.025, hr), "door", 0.4)
    sh.rect(*P(-0.05, hr), *P(Lr + 0.05, hr + 0.05), "door", 0.45)      # the rail 2"x4" laid flat
    n = int(round(Lr / 0.20))
    for i in range(1, n):                                    # balusters every 0.20
        u = i * Lr / n
        sh.line(P(u, 0.0), P(u, hr), "door", 0.25)
    sh.line(P(0.0, 0.10), P(Lr, 0.10), "door", 0.3)          # the bottom rail
    # sizes: heights on the left, the spacing below
    xl = P(-0.3, 0)[0] - 6
    for za, zb in ((0.0, 0.10), (0.10, hr), (hr, hr + 0.05)):
        a, b = P(0, za)[1], P(0, zb)[1]
        sh.line((xl, a), (xl, b), "dim", 0.13)
        for yq in (a, b):
            sh.line((xl - 0.7, yq - 0.7), (xl + 0.7, yq + 0.7), "dim", 0.25)
        sh.text((xl - 1.0, (a + b) / 2 - 0.7), f"{zb - za:.2f}", 2.0, "right", "dim")
    xt = xl - 12
    sh.line((xt, P(0, 0)[1]), (xt, P(0, hr + 0.05)[1]), "dim", 0.13)
    sh.text((xt - 1.0, P(0, hr / 2)[1]), f"{hr + 0.05:.2f}", 2.0, "center", "dim", angle=90)
    yb = P(0, -t)[1] - 6
    for i in range(n + 1):
        xq = P(i * Lr / n, 0)[0]
        sh.line((xq - 0.6, yb - 0.6), (xq + 0.6, yb + 0.6), "dim", 0.2)
        sh.line((xq, yb - 1.2), (xq, yb + 1.2), "dim", 0.13)
        if i < n:
            sh.text((xq + Lr / n * k / 2, yb + 0.9), f"{Lr / n:.2f}", 1.8, "center", "dim")
    sh.line((P(0, 0)[0], yb), (P(Lr, 0)[0], yb), "dim", 0.13)
    # the labels stacked over the rail, each to its point (the leaders never cross)
    lx = P(0.2, 0)[0]
    for i, (z, lab) in enumerate(((hr + 0.025, 'ราวกันตกไม้เนื้อแข็ง 2"x4" วางนอน ทาสี'),
                                  (hr * 0.6, 'ลูกกรงแป๊บดำ Ø 1" @0.20 ม. ทาสีน้ำมัน'),
                                  (0.10, 'เหล็กกล่อง 1"x2" ยึดพื้นด้วยพุก'))):
        q = P(Lr - 0.25 - i * 0.35, z)
        ty = P(0, hr)[1] + 24 - i * 6
        sh.circle(q, 0.45, "text", 0.18)
        sh.line(q, (lx + len(lab) * 1.05, ty), "text", 0.13)
        sh.line((lx, ty), (lx + len(lab) * 1.05, ty), "text", 0.13)
        sh.text((lx + 0.5, ty + 0.8), lab, 2.0)
    caption_marks(sh, (x0 + 20, y0 + 22), "แบบขยาย ด้านหน้าราวกันตก", "1:25", None, None, 110.0)
    # ---- section through the slab edge ---------------------------------------
    ox2, oy2 = xm + 60, y0 + 110

    def Q(u, z):
        return (ox2 + u * k, oy2 + z * k)
    _concrete(sh, Q(-1.2, -t), Q(0.0, 0.0))
    _concrete(sh, Q(-0.20, -0.40), Q(0.0, -t))              # the edge beam at the opening
    sh.rect(*Q(-0.10, 0.0), *Q(-0.05, hr), "door", 0.4)     # post
    sh.rect(*Q(-0.125, hr), *Q(-0.025, hr + 0.05), "door", 0.45)
    sh.line(Q(-0.075, 0.0), Q(-0.075, hr), "door", 0.2)
    sh.line(Q(-1.2, 0.0), Q(-1.2, hr + 0.4), "grid", 0.1, True)
    for za, zb in ((0.0, hr), (hr, hr + 0.05)):
        a, b = Q(0, za)[1], Q(0, zb)[1]
        xq = Q(0.25, 0)[0]
        sh.line((xq, a), (xq, b), "dim", 0.13)
        for yq in (a, b):
            sh.line((xq - 0.7, yq - 0.7), (xq + 0.7, yq + 0.7), "dim", 0.25)
        sh.text((xq + 1.2, (a + b) / 2 - 0.7), f"{zb - za:.2f}", 2.0, "left", "dim")
    sh.text(Q(0.10, -t - 0.35), "ช่องบันได", 2.2, "left", "text", True)
    tx2 = Q(0.80, 0)[0]
    for z, lab in ((hr + 0.025, 'ราวไม้ 2"x4" วางนอน'), (0.5, 'ลูกกรงแป๊บดำ Ø 1"'),
                   (-t / 2, "พื้น ค.ส.ล. / คานขอบช่องบันได")):
        q = Q(-0.06 if z > 0 else -0.1, z)
        sh.circle(q, 0.45, "text", 0.18)
        sh.line(q, (tx2, q[1]), "text", 0.13)
        sh.line((tx2, q[1]), (tx2 + len(lab) * 1.1, q[1]), "text", 0.13)
        sh.text((tx2 + 0.5, q[1] + 0.8), lab, 2.0)
    caption_marks(sh, (xm + 20, y0 + 22), "แบบขยาย รูปตัดราวกันตก", "1:25", None, None, 110.0)
    sh.scale = "1:25"
    return 25


# ---------------------------------------------------------------------------
# S2 — ตารางเสา, beam sections 1:20 (the original's S-08) and footing details
# ---------------------------------------------------------------------------

def _bar_th(text) -> str:
    """«8-DB12» → «8 DB12 มม.», «RB6@0.15» → «ป. RB6 มม.@0.15»."""
    n, name, _d, s_ = D._bars(text)
    if s_:
        return f"ป. {name} มม.@{s_:.2f}"
    return f"{n} {name} มม." if n else str(text or "")


def _dot(sh, c, r):
    """A main bar in a section: a filled round dot."""
    import math as _m
    sh.fill([(c[0] + r * _m.cos(i * _m.pi / 6), c[1] + r * _m.sin(i * _m.pi / 6)) for i in range(12)], "hatch", 0.0)


def sec_dims(sh, x, y, w, hh, b, h, size=2.3):
    """The size of a section as the original: the width above, the height on
    the left, each with extension lines and a tick (/) at both ends."""
    ya = y + hh + 3.0
    sh.line((x, ya), (x + w, ya), "dim", 0.15)
    for xq in (x, x + w):
        sh.line((xq, y + hh + 0.8), (xq, ya + 1.2), "dim", 0.13)            # extension line
        sh.line((xq - 0.8, ya - 0.8), (xq + 0.8, ya + 0.8), "dim", 0.3)     # tick
    sh.text((x + w / 2, ya + 0.8), f"{b:.2f}", size, "center", "dim")
    xa = x - 3.0
    sh.line((xa, y), (xa, y + hh), "dim", 0.15)
    for yq in (y, y + hh):
        sh.line((x - 0.8, yq), (xa - 1.2, yq), "dim", 0.13)
        sh.line((xa - 0.8, yq - 0.8), (xa + 0.8, yq + 0.8), "dim", 0.3)
    sh.text((xa - 0.8, y + hh / 2), f"{h:.2f}", size, "center", "dim", angle=90)


def stirrup(sh, x0, y0, x1, y1, r=1.4):
    """The stirrup (ป.) with its 135° hooks in the top right corner, as the
    standard and the original: two short legs bent into the core."""
    sh.rect(x0, y0, x1, y1, "rebar", 0.25)
    L = r * 2.2
    for (ax, ay) in ((x1 - r, y1), (x1, y1 - r)):
        sh.line((ax, ay), (ax - L * 0.707, ay - L * 0.707), "rebar", 0.25)


def column_cell(sh, cx, cy, spec, k):
    """A column section centred at (cx, cy) with its size and bars."""
    from core import wanic_struct_sheets as SS
    b, h = float(spec.get("b", 0.2)), float(spec.get("h", 0.2))
    x, y = cx - b * k / 2, cy - h * k / 2 + 4
    n, name = SS._count(spec.get("main"))
    w, hh = b * k, h * k
    sh.rect(x, y, x + w, y + hh, "struct", 0.45)
    c = 0.035 * k
    stirrup(sh, x + c * 0.7, y + c * 0.7, x + w - c * 0.7, y + hh - c * 0.7, max(1.0, c * 0.6))
    n = max(n, 4)
    per = [n // 4 + (1 if i < n % 4 else 0) for i in range(4)]
    corners = [(x + c, y + c), (x + w - c, y + c), (x + w - c, y + hh - c), (x + c, y + hh - c)]
    for i in range(4):
        a, b_ = corners[i], corners[(i + 1) % 4]
        for j in range(per[i]):
            t = j / per[i]
            _dot(sh, (a[0] + (b_[0] - a[0]) * t, a[1] + (b_[1] - a[1]) * t), 0.7)
    sec_dims(sh, x, y, w, hh, b, h)
    sh.text((cx, y - 4.6), _bar_th(spec.get("main")), 2.6, "center")
    sh.text((cx, y - 8.8), _bar_th(spec.get("tie")), 2.6, "center")


def column_schedule(sh, E, x, ytop, ybot, w=70.0):
    """ตารางเสา as the original: a column per column mark, a row per storey
    (top: the roof down to the footing), each cell the section — or an
    arrow when it is the same as the one below; the levels on the left."""
    lib = E["lib"]
    marks = sorted({c["mark"] for c in E["columns"]})
    rows = []                                           # top → bottom
    H = E["H"]
    for f in reversed(range(E["n"])):
        to = "อะเส" if f == E["n"] - 1 else f"พื้นชั้น {f + 2}"
        rows.append((f"{to} +{(f + 1) * H:.2f}", {m: lib.get(m, {}) for m in marks
                     if any(c["mark"] == m and int(c.get("floor", 0)) == f for c in E["columns"])}))
    stump = {}
    for m in marks:
        c0 = next((c for c in E["columns"] if c["mark"] == m and int(c.get("floor", 0)) == 0), None)
        st = next((s["mark"] for s in E["stumps"] if c0 and s["x"] == c0["x"] and s["y"] == c0["y"]), None)
        if st:
            stump[m] = lib.get(st, {})
    rows.append(("พื้นชั้น 1 ±0.00", stump))
    lw = 28.0
    cw = max(26.0, (w - lw) / max(len(marks), 1))
    W = lw + cw * len(marks)
    head = 12.0
    rh = min(80.0, (ytop - ybot - head) / len(rows))
    ybot = ytop - head - rh * len(rows)
    sh.rect(x, ybot, x + W, ytop, "text", 0.4)
    sh.line((x, ytop - head), (x + W, ytop - head), "text", 0.35)
    sh.line((x, ytop), (x + lw, ytop - head), "text", 0.18)          # the split head «เสา / ระดับ»
    sh.text((x + lw - 2, ytop - 4.5), "เสา", 2.2, "right")
    sh.text((x + 2, ytop - head + 2), "ระดับ", 2.2)
    for i, m in enumerate(marks):
        xc = x + lw + i * cw
        sh.line((xc, ybot), (xc, ytop), "text", 0.25)
        sh.text((xc + cw / 2, ytop - head / 2 - 1.0), m, 2.8, "center", "text", True)
    k = 1000.0 / 20
    above = None
    for jt, (lab, cells) in enumerate(rows):                    # top first: the section, then «same as above»
        j = len(rows) - 1 - jt
        yb_ = ybot + j * rh
        sh.line((x, yb_ + rh), (x + W, yb_ + rh), "text", 0.25)
        sh.text((x + 1.5, yb_ + rh - 4.0), lab, 2.6, "left", "text", True)     # the level at the row top line
        if j == 0:
            sh.text((x + 1.5, yb_ + rh / 2), "ตอม่อ", 2.8)
        for i, m in enumerate(marks):
            spec = cells.get(m)
            cxp, cyp = x + lw + (i + 0.5) * cw, yb_ + rh / 2
            if not spec:
                continue
            up = above and above.get(m)
            same = up and up.get("kind") == spec.get("kind") and \
                all(up.get(q) == spec.get(q) for q in ("b", "h", "main", "tie"))
            if same:
                sh.line((cxp, cyp - 6), (cxp, cyp + 6), "text", 0.3)            # «same as above» (the original)
                sh.line((cxp, cyp + 6), (cxp - 2, cyp + 3.5), "text", 0.3)
                sh.line((cxp, cyp + 6), (cxp + 2, cyp + 3.5), "text", 0.3)
            else:
                column_cell(sh, cxp, cyp, spec, k)
        above = cells
    sh.text((x + 1.5, ybot + 1.5), "ฐานราก", 2.6, "left", "text", True)
    caption_marks(sh, (x + 8, ybot - 12), "ตารางเสา", "1:20", None, None, W - 16)
    return W


def beam_card(sh, mark, spec, x, y, k=1000.0 / 20, note=""):
    """A beam section «B1 1:20»: outline, stirrup, bars, the size, the bar
    notes on leaders to the right (the original)."""
    from core import wanic_struct_sheets as SS
    b, h = float(spec.get("b", 0.2)), float(spec.get("h", 0.4))
    w, hh = b * k, h * k
    tn, tname = SS._count(spec.get("top"))
    bn, bname = SS._count(spec.get("bot"))
    sh.rect(x, y, x + w, y + hh, "struct", 0.45)
    c = 0.03 * k
    stirrup(sh, x + c * 0.7, y + c * 0.7, x + w - c * 0.7, y + hh - c * 0.7, max(1.0, c * 0.6))
    for n, yy in ((tn, y + hh - c), (bn, y + c)):
        for i in range(max(n, 1)):
            bx = x + c + (w - 2 * c) * (i / (n - 1) if n > 1 else 0.5)
            _dot(sh, (bx, yy), 0.75)
    sec_dims(sh, x, y, w, hh, b, h)
    for txt, yy in ((f"{tn} {tname} มม.", y + hh - c), (_bar_th(spec.get("stir")), y + hh / 2),
                    (f"{bn} {bname} มม.", y + c)):
        sh.line((x + w - c, yy), (x + w + 7, yy), "text", 0.15)
        sh.text((x + w + 7.5, yy - 0.9), txt, 2.6)
    sh.text((x - 8, y - 10), mark, 4.0, "left", "text", True)
    sh.text((x + w + 22, y - 10), f"1:{1000 / k:.0f}", 3.6, "right")
    sh.line((x - 10, y - 11.8), (x + w + 24, y - 11.8), "text", 0.4)
    if note:
        sh.text(((x - 10 + x + w + 24) / 2, y - 17), note, 2.6, "center")


def s_schedules_std(sh, E):
    """ตารางเสา on the left, every beam's section at 1:20 on the right, the
    footing and slab schedules under them (the original's S-08)."""
    x0, y0, x1, y1 = D.drawing_area()
    lib = E["lib"]
    used = {e["mark"] for key in ("footings", "stumps", "columns", "beams", "slabs") for e in E[key]}
    W = column_schedule(sh, E, x0 + 4, y1 - 18, y0 + 34, 70.0)
    beams = sorted(m for m in used if lib.get(m, {}).get("kind") == "beam")
    # the beam sections: a grid of four over the rest of the sheet (the original);
    # few beams → drawn twice as large (1:10), clearer than the original
    bx0 = x0 + W + 18
    k = 1000.0 / (10 if len(beams) <= 6 else 20)
    per = 3 if k > 60 else 4
    cw = (x1 - bx0) / per
    hmax = max([float(lib[m].get("h", 0.4)) for m in beams] or [0.4]) * k
    cols = sorted(m for m in used if lib.get(m, {}).get("kind") in ("column", "stump"))
    nb, nc = -(-len(beams) // per), -(-len(cols) // per)
    # the rows spread over the whole height (the original fills the sheet)
    rh = max(hmax + 34, (y1 - y0 - 24) / max(nb + nc, 1))
    names = {"GB": "คานคอดิน", "B": "คานชั้นบน", "RB": "คานหลังคา", "BX": "คานยื่น"}
    for i, m in enumerate(beams):
        r, c = divmod(i, per)
        sp = lib[m]
        bw, bh = float(sp.get("b", 0.2)) * k, float(sp.get("h", 0.4)) * k
        yc_ = y1 - 12 - r * rh - rh / 2                  # the row's middle
        note = next((v for p_, v in sorted(names.items(), key=lambda t: -len(t[0])) if m.startswith(p_)), "")
        beam_card(sh, m, sp, bx0 + c * cw + (cw - bw - 44) / 2 + 6, yc_ - bh / 2 + 10, k, note)
    # the columns and stumps at the same scale, rows under the beams (the original's CN row)
    for i, m in enumerate(cols):
        r, c = divmod(i, per)
        sp = lib[m]
        hh = float(sp.get("h", 0.25)) * k
        cxp = bx0 + c * cw + cw / 2 - 6
        cyp = y1 - 12 - (nb + r) * rh - rh / 2 + 10
        column_cell(sh, cxp, cyp, sp, k)
        yt = cyp - hh / 2 - 6
        yt -= 4
        sh.text((cxp - 20, yt - 10), m, 4.0, "left", "text", True)
        sh.text((cxp + 22, yt - 10), f"1:{1000 / k:.0f}", 3.6, "right")
        sh.line((cxp - 22, yt - 11.8), (cxp + 24, yt - 11.8), "text", 0.4)
        sh.text((cxp + 1, yt - 17), "(ตอม่อ ฐานราก – พื้นชั้น 1)" if sp.get("kind") == "stump"
                else "(เสา พื้นชั้น 1 – อะเส)", 2.6, "center")
    sh.scale = "1:20"
    return 20


def _stipple(sh, a, b, dens=5.0):
    """Concrete aggregate marks (no fill) in the paper box a–b."""
    import random as _r
    x0, x1 = sorted((a[0], b[0]))
    y0, y1 = sorted((a[1], b[1]))
    rnd = _r.Random(int(x0 * 11 + y0 * 7))
    for _i in range(int((x1 - x0) * (y1 - y0) / dens) + 1):
        px, py = x0 + 0.4 + rnd.random() * (x1 - x0 - 0.8), y0 + 0.4 + rnd.random() * (y1 - y0 - 0.8)
        if rnd.random() < 0.5:
            sh.poly([(px, py), (px + 0.6, py + 0.15), (px + 0.2, py + 0.55)], "hatch", 0.1)
        else:
            sh.circle((px, py), 0.12, "hatch", 0.1)


def footing_detail(sh, E, mark, n_sec, ox, ytop, sc=25, side=False):
    """One footing as the original (S-09): the section n–n at 1:``sc`` — the
    ground ±0.00 hatched, the stump to «ตอม่อดูขยายเสา», the footing with its
    mesh, lean concrete and sand, piles; the sizes; then the plan with the
    stump, the piles, its sizes and the cut n–n, and the «F1 1:25» box."""
    from core import wanic_struct_sheets as SS
    lib = E["lib"]
    sp = lib[mark]
    w, l_, t = float(sp["w"]), float(sp.get("l", sp["w"])), float(sp["t"])
    ft = next(f for f in E["footings"] if f["mark"] == mark)
    st = next((s for s in E["stumps"] if s["x"] == ft["x"] and s["y"] == ft["y"]), None)
    stsp = lib.get(st["mark"] if st else "PC1", {})
    b = float(stsp.get("b", 0.2))
    gl = float(E.get("GL", 0.0))
    zt = ft["z1"] - gl                                  # the footing's top below the ground
    lean, sand = float(sp.get("lean", 0.05)), float(sp.get("sand", 0.05))
    k = 1000.0 / sc
    oy = ytop - 14 - (0.35) * k

    def P(u, z):
        return (ox + u * k, oy + z * k)
    # the ground and the soil
    sh.line(P(-w / 2 - 0.45, 0.0), P(-b / 2, 0.0), "cut", 0.4)
    sh.line(P(b / 2, 0.0), P(w / 2 + 0.45, 0.0), "cut", 0.4)
    u = -w / 2 - 0.45
    while u < w / 2 + 0.4:
        if not (-b / 2 - 0.05 < u < b / 2):
            sh.line(P(u, 0.0), P(u + 0.06, -0.06), "hatch", 0.1)
        u += 0.08
    q = P(-w / 2 - 0.45, 0.0)
    sh.poly([(q[0] + 1.0, q[1]), (q[0] - 0.4, q[1] + 2.0), (q[0] + 2.4, q[1] + 2.0)], "dim", 0.2)
    sh.text((q[0] + 3.0, q[1] + 0.8), "ระดับดินเดิม ±0.00", 2.0, "left", "dim")
    # the stump (to a break line) and its bars
    top = 0.35
    sh.line(P(-b / 2, zt + t * 0 + 0.0), P(-b / 2, top), "cut", 0.45)
    sh.line(P(b / 2, zt), P(b / 2, top), "cut", 0.45)
    sh.line(P(-b / 2 - 0.05, top), P(b / 2 + 0.05, top + 0.06), "cut", 0.25)
    c = 0.035
    for uu in (-b / 2 + c, b / 2 - c):
        sh.line(P(uu, top), P(uu, zt - t + 0.075), "rebar", 0.35)
        sh.line(P(uu, zt - t + 0.075), P(uu + (0.25 if uu > 0 else -0.25), zt - t + 0.075), "rebar", 0.35)
    z_ = zt - 0.05
    while z_ > zt - t + 0.1:
        sh.line(P(-b / 2 + 0.02, z_), P(b / 2 - 0.02, z_), "rebar", 0.15)
        z_ -= 0.15
    z_ = 0.0 - 0.05
    while z_ > zt:
        sh.line(P(-b / 2 + 0.02, z_), P(b / 2 - 0.02, z_), "rebar", 0.15)
        z_ -= 0.15
    # the footing, lean concrete, sand
    zb = zt - t
    sh.poly([P(-w / 2, zb), P(w / 2, zb), P(w / 2, zt), P(b / 2, zt), P(b / 2, zt), P(-b / 2, zt), P(-w / 2, zt)],
            "cut", 0.5)
    _stipple(sh, P(-w / 2, zb), P(-b / 2, zt))
    _stipple(sh, P(b / 2, zb), P(w / 2, zt))
    _stipple(sh, P(-b / 2, zb + 0.08), P(b / 2, top))
    sh.rect(*P(-w / 2 - 0.05, zb - lean), *P(w / 2 + 0.05, zb), "cut", 0.25)
    _brick_band(sh, P(-w / 2 - 0.05, zb - lean), P(w / 2 + 0.05, zb), 1.0)
    sh.rect(*P(-w / 2 - 0.05, zb - lean - sand), *P(w / 2 + 0.05, zb - lean), "cut", 0.2)
    for i in range(int((w + 0.1) / 0.06)):
        uu = -w / 2 - 0.05 + i * 0.06
        sh.circle(P(uu + 0.03, zb - lean - sand / 2), 0.15, "hatch", 0.1)
    # the mesh: the bars along the cut with both ends bent up (the original), the cross bars as dots
    cov = 0.075
    hook = max(0.15, t - 2 * cov)
    sh.poly([P(-w / 2 + cov, zb + cov + hook), P(-w / 2 + cov, zb + cov), P(w / 2 - cov, zb + cov),
             P(w / 2 - cov, zb + cov + hook)], "rebar", 0.5, closed=False)
    n_, name, _d, s_ = D._bars(sp.get("bars"))
    s_ = s_ or 0.15
    m = int((w - 2 * cov) / s_)
    for i in range(m + 1):
        uu = -w / 2 + cov + 0.03 + i * (w - 2 * cov - 0.06) / max(m, 1)
        _dot(sh, P(uu, zb + cov + 0.025), 0.5)
    # the ring bar (เหล็กรัดรอบ) round the top of the footing: a bar along the cut, a dot at each end
    ring = sp.get("ring") or "RB9"
    zr = zt - cov
    sh.line(P(-w / 2 + cov, zr), P(-b / 2 - 0.02, zr), "rebar", 0.4)
    sh.line(P(b / 2 + 0.02, zr), P(w / 2 - cov, zr), "rebar", 0.4)
    for uu in (-w / 2 + cov + 0.02, w / 2 - cov - 0.02):
        _dot(sh, P(uu, zr - 0.02), 0.5)
    # piles: to a break line under the footing, as the original
    piles = int(sp.get("piles") or 0)
    pb = float(sp.get("pile_b", 0.18))
    pts = B.pile_points(sp, 0.0, 0.0) if piles else []
    plen = 1.0
    for px in sorted({round(p_[0], 3) for p_ in pts}):
        x_a, x_b = P(px - pb / 2, 0)[0], P(px + pb / 2, 0)[0]
        ytop_, ybot_ = P(0, zb - lean - sand)[1], P(0, zb - lean - sand - plen)[1]
        sh.line((x_a, ytop_), (x_a, ybot_), "cut", 0.45)
        sh.line((x_b, ytop_), (x_b, ybot_), "cut", 0.45)
        sh.line((x_a, P(0, zb)[1]), (x_a, ytop_), "cut", 0.3)              # into the footing 0.05+
        sh.line((x_b, P(0, zb)[1]), (x_b, ytop_), "cut", 0.3)
        mx = (x_a + x_b) / 2                                                   # the break (S) line
        sh.poly([(x_a - 1, ybot_), (mx - 0.8, ybot_), (mx, ybot_ + 1.2), (mx + 0.4, ybot_ - 1.2),
                 (mx + 0.8, ybot_), (x_b + 1, ybot_)], "cut", 0.3, closed=False)
    # the labels on the right, level with their points
    tx = P(w / 2 + 0.55, 0)[0]
    labels = [((b / 2, (top + zt) / 2), "ตอม่อ ดูขยายเสา"),
              ((w / 2 - cov - 0.02, zr - 0.02), f"เหล็กรัดรอบ {ring} มม."),
              ((w / 2 - cov, zb + cov + hook * 0.6), "งอขึ้นปลายเหล็กตะแกรง"),
              ((w / 2 - cov - 0.05, zb + cov + 0.02), f"เหล็กตะแกรง {D._bars(sp.get('bars'))[1]} มม.@{(D._bars(sp.get('bars'))[3] or 0.15):.3f} 2 ทาง"),
              ((w / 2, zb - lean / 2), f"คอนกรีตหยาบ 1:3:5 หนา {lean:.2f} ม."),
              ((w / 2, zb - lean - sand / 2), f"ทรายหยาบอัดแน่น หนา {sand:.2f} ม.")]
    if piles:
        labels.append(((max(p_[0] for p_ in pts) + pb / 2, zb - lean - sand - 0.6),
                       f"{sp.get('pile_name') or f'เสาเข็ม {pb:.2f}x{pb:.2f} ม.'} ยาว {float(sp.get('pile_len', 6)):.0f} ม."
                       f" จำนวน {piles} ต้น"))
    last = None
    for (uu, zz), lab in labels:                         # top first, kept 4.5 mm apart
        q = P(uu, zz)
        ty = q[1] if last is None else min(q[1], last - 5.5)
        last = ty
        sh.circle(q, 0.45, "text", 0.2)
        sh.line(q, (tx - 2, ty), "text", 0.15)
        sh.line((tx - 2, ty), (tx + len(lab) * 1.25, ty), "text", 0.15)
        sh.text((tx + 0.5, ty + 0.9), lab, 2.4)
    # heights on the left
    xl = P(-w / 2 - 0.3, 0)[0]
    for za, zb_ in ((zt, 0.0), (zb, zt), (zb - lean - sand, zb)):
        a, b2 = P(0, za)[1], P(0, zb_)[1]
        sh.line((xl, a), (xl, b2), "dim", 0.15)
        for yq in (a, b2):
            sh.line((xl - 1.2, yq), (P(-w / 2, 0)[0] - 1.0, yq), "dim", 0.13)       # extension line
            sh.line((xl - 0.8, yq - 0.8), (xl + 0.8, yq + 0.8), "dim", 0.3)
        sh.text((xl - 1.2, (a + b2) / 2 - 0.9), f"{zb_ - za:.2f}", 2.3, "right", "dim")
    # the width under it and the section's name
    yb = P(0, zb - lean - sand - (1.1 if piles else 0.15))[1] - 4
    # the chain: through the pile centres when on piles (the original), else the stump faces
    xs = sorted({round(v, 3) for v in [-w / 2, w / 2, 0.0] + [p_[0] for p_ in pts]}) if pts else \
        [-w / 2, -b / 2, b / 2, w / 2]
    ys = sorted({round(v, 3) for v in [-l_ / 2, l_ / 2, 0.0] + [p_[1] for p_ in pts]}) if pts else \
        [-l_ / 2, -b / 2, b / 2, l_ / 2]
    D.dim_chain(sh, lambda x_, y_: (P(x_, 0)[0], yb), xs, 0.0, "x")
    D.dim_chain(sh, lambda x_, y_: (P(x_, 0)[0], yb - 5), [-w / 2, w / 2], 0.0, "x")
    for i, xq in enumerate((ox - 4, ox + 4)):
        sh.circle((xq, yb - 13), 3.2, "text", 0.25)
        sh.text((xq, yb - 13.9), str(n_sec), 2.4, "center", "text", True)
    sh.line((ox - 0.8, yb - 13), (ox + 0.8, yb - 13), "text", 0.3)
    # the plan: under the section, or beside it (one footing on the sheet)
    py0 = yb - 38 - l_ * k / 2
    pox = ox
    if side:
        pox = tx + 72 + w / 2 * k
        py0 = P(0, zt)[1] - l_ * k / 2 + 6
    Q = lambda u_, v_: (pox + u_ * k, py0 + v_ * k)               # noqa: E731
    sh.rect(*Q(-w / 2, -l_ / 2), *Q(w / 2, l_ / 2), "cut", 0.5)
    sh.rect(*Q(-b / 2, -b / 2), *Q(b / 2, b / 2), "column", 0.35)
    _brick_band(sh, Q(-b / 2, -b / 2), Q(b / 2, b / 2), 0.8)
    mm = int((w - 2 * cov) / s_)                         # the mesh, dashed (under the concrete)
    for i in range(mm + 1):
        t_ = -w / 2 + cov + i * (w - 2 * cov) / max(mm, 1)
        sh.line(Q(t_, -l_ / 2 + cov), Q(t_, l_ / 2 - cov), "rebar", 0.1, True)
        tl = -l_ / 2 + cov + i * (l_ - 2 * cov) / max(mm, 1)
        sh.line(Q(-w / 2 + cov, tl), Q(w / 2 - cov, tl), "rebar", 0.1, True)
    sh.text((Q(w / 2, 0)[0], Q(0, -l_ / 2)[1] - 5), f"เหล็กตะแกรง {D._bars(sp.get('bars'))[1]}@{s_:.3f} ม. 2 ทาง",
            2.4, "right")
    sh.rect(*Q(-w / 2 + cov, -l_ / 2 + cov), *Q(w / 2 - cov, l_ / 2 - cov), "rebar", 0.3)     # the ring bar
    import math as _m
    for p_ in pts:                                        # the piles: a hexagon with its circle (the original)
        c_ = Q(*p_)
        r_ = pb / 2 * k * 1.15
        sh.poly([(c_[0] + r_ * _m.cos(_m.pi / 6 + i * _m.pi / 3), c_[1] + r_ * _m.sin(_m.pi / 6 + i * _m.pi / 3))
                 for i in range(6)], "struct", 0.35)
        sh.circle(c_, pb / 2 * k * 0.55, "struct", 0.25)
    D.dim_chain(sh, lambda x_, y_: (Q(x_, 0)[0], Q(0, l_ / 2)[1] + 4), xs, 0.0, "x")
    D.dim_chain(sh, lambda x_, y_: (Q(x_, 0)[0], Q(0, l_ / 2)[1] + 10), [-w / 2, w / 2], 0.0, "x")
    D.dim_chain(sh, lambda x_, y_: (Q(-w / 2, 0)[0] - 8, Q(0, y_)[1]), ys, 0.0, "y")
    D.dim_chain(sh, lambda x_, y_: (Q(-w / 2, 0)[0] - 14, Q(0, y_)[1]), [-l_ / 2, l_ / 2], 0.0, "y")
    for (u_, v_) in ((-w / 2, l_ / 2), (w / 2, l_ / 2)):            # extension lines of the chains
        sh.line(Q(u_, v_), (Q(u_, 0)[0], Q(0, l_ / 2)[1] + 11.2), "dim", 0.13)
    for v_ in (-l_ / 2, l_ / 2):
        sh.line(Q(-w / 2, v_), (Q(-w / 2, 0)[0] - 15.2, Q(0, v_)[1]), "dim", 0.13)
    for sx in (-1, 1):                                    # the cut n–n
        e_ = Q(sx * w / 2, 0.0)
        off = 21.0 if sx < 0 else 5.0                       # left: beyond the size chains
        a_ = (e_[0] + sx * off, e_[1])
        sh.line(a_, (a_[0] + sx * 3, a_[1]), "text", 0.4)
        sh.circle((a_[0] + sx * 6.4, a_[1]), 3.2, "text", 0.25)
        sh.text((a_[0] + sx * 6.4, a_[1] - 1.0), str(n_sec), 2.6, "center", "text", True)
    # the name box «F1 1:25»
    by = py0 - l_ * k / 2 - 16
    sh.rect(pox - 22, by, pox + 22, by + 7, "text", 0.35)
    sh.line((pox, by), (pox, by + 7), "text", 0.25)
    sh.text((pox - 11, by + 2.0), mark, 3.4, "center", "text", True)
    sh.text((pox + 11, by + 2.0), f"1:{sc}", 3.2, "center")


def s_footings_std(sh, E, marks):
    """แบบขยายฐานราก — two footings a sheet, side by side (the original)."""
    x0, y0, x1, y1 = D.drawing_area()
    lib = E["lib"]
    big = max(max(float(lib[m]["w"]), float(lib[m].get("l", lib[m]["w"]))) for m in marks)
    if len(marks) == 1:                                   # one footing: section over its plan (the original), large
        sp = lib[marks[0]]
        w, l_ = float(sp["w"]), float(sp.get("l", sp["w"]))
        tall = 0.35 + float(sp["depth"]) + 0.15 + (1.1 if int(sp.get("piles") or 0) else 0.0)
        sc = next((s_ for s_ in (20, 25, 30, 40, 50) if (tall + l_) * 1000 / s_ + 86 <= (y1 - y0)
                   and (w + 0.9) * 1000 / s_ + 75 <= (x1 - x0) * 0.62), 50)
        k = 1000.0 / sc
        ox = x0 + 32 + (w / 2 + 0.45) * k
        footing_detail(sh, E, marks[0], 1, ox, y1 - 2, sc)
        footing_notes(sh, E, marks, x0 + (x1 - x0) * 0.66, y1 - 30, stacked=True)
        sh.scale = f"1:{sc}"
        return sc
    cw = (x1 - x0) / len(marks)
    sc = next((s_ for s_ in (20, 25, 30, 40, 50) if (big + 0.9) * 1000 / s_ <= cw - 80
               and (2 * big + 2.2) * 1000 / s_ <= (y1 - y0) - 80), 50)
    for i, m in enumerate(marks):
        cx = x0 + cw * (i + 0.5) - 30
        footing_detail(sh, E, m, i + 1 + 0, cx, y1 - 4, sc)
    sh.scale = f"1:{sc}"
    return sc


def footing_notes(sh, E, marks, x, y, stacked=False):
    """The footing schedule and the footing notes beside the detail."""
    lib = E["lib"]
    sh.text((x, y), "ตารางฐานราก", 3.2, "left", "text", True)
    rows = []
    for m in marks:
        sp = lib[m]
        piles = int(sp.get("piles") or 0)
        rows.append((m, f"{float(sp['w']):.2f}x{float(sp.get('l', sp['w'])):.2f}", f"{float(sp['t']):.2f}",
                     sp.get("bars", ""), f"{piles} ต้น" if piles else "ฐานแผ่",
                     str(sum(1 for f in E["footings"] if f["mark"] == m))))
    yt = D.table(sh, x, y - 3, [("เบอร์", 14, "center"), ("ขนาด (ม.)", 24, "center"), ("หนา", 12, "center"),
                                ("เหล็กตะแกรง", 26, "center"), ("เสาเข็ม", 18, "center"), ("จำนวน", 14, "center")],
                 rows, 2.1, 5.5, 6.5)
    D.notes_block(sh, x if stacked else x + 130, yt - 12 if stacked else y, "หมายเหตุ", [
        ("1. ฐานรากวางบนเสาเข็ม เสาเข็มต้องรับน้ำหนักปลอดภัยได้ไม่น้อยกว่าที่ระบุในรายการคำนวณ "
         "ตัดหัวเข็มให้ได้ระดับ และฝังหัวเข็มในฐานราก 0.05 ม."
         if any(int(lib[m_].get("piles") or 0) for m_ in marks) else
         "1. ฐานรากแผ่ ใช้เมื่อดินรับน้ำหนักบรรทุกปลอดภัยได้ไม่น้อยกว่า 10 ตัน/ตร.ม."),
        "2. ก่อนเทคอนกรีตฐานราก ให้บดอัดดินก้นหลุม รองด้วยทรายหยาบอัดแน่น หนา 0.05 ม. "
        "และคอนกรีตหยาบ 1:3:5 หนา 0.05 ม.",
        "3. ระยะหุ้มคอนกรีตเหล็กตะแกรงฐานราก 7.5 ซม. ปลายเหล็กงอขอ 90 องศา",
        "4. เหล็กยืนตอม่อ งอฉากวางบนเหล็กตะแกรงยาวไม่น้อยกว่า 0.25 ม.",
        "5. ตำแหน่งและระดับฐานรากให้ตรวจสอบกับแปลนฐานรากและสภาพหน้างาน",
        "6. เหล็กรัดรอบฐานราก วางรอบขอบบนฐานราก ทาบต่อไม่น้อยกว่า 40 เท่าของขนาดเหล็ก",
    ], 2.5, 50 if stacked else 90)


# -- S: slab, column-joint and rib details (the standard's S-16) -------------------------

def _soil(sh, x0, x1, y, depth=3.0, step=2.4):
    """Soil under a line: the standard's small crosses (XXXX)."""
    x = x0
    while x < x1 - step * 0.5:
        sh.line((x, y), (x + step, y - depth), "hatch", 0.12)
        sh.line((x + step, y), (x, y - depth), "hatch", 0.12)
        x += step


def _sand(sh, x0, y0, x1, y1):
    """Compacted sand: fine dots."""
    import random as _r
    rnd = _r.Random(int(x0 * 7 + y0 * 3))
    for _i in range(int((x1 - x0) * (y1 - y0) / 1.6) + 1):
        sh.circle((x0 + 0.3 + rnd.random() * (x1 - x0 - 0.6), y0 + 0.3 + rnd.random() * (y1 - y0 - 0.6)),
                  0.1, "hatch", 0.1)


def _break_v(sh, x, y0, y1):
    """A vertical break line (the S mark) from y0 to y1."""
    m = (y0 + y1) / 2
    sh.poly([(x, y0 - 1.5), (x, m - 1.2), (x - 1.2, m - 0.4), (x + 1.2, m + 0.4), (x, m + 1.2), (x, y1 + 1.5)],
            "cut", 0.25, closed=False)


def _break_h(sh, y, x0, x1):
    m = (x0 + x1) / 2
    sh.poly([(x0 - 1.5, y), (m - 1.2, y), (m - 0.4, y + 1.2), (m + 0.4, y - 1.2), (m + 1.2, y), (x1 + 1.5, y)],
            "cut", 0.25, closed=False)


def _leader(sh, p, tx, ty, text, right=True, size=2.5):
    """A leader from the point p to a text on a short shelf."""
    sh.circle(p, 0.45, "text", 0.2)
    sh.line(p, (tx, ty), "text", 0.15)
    w = len(text) * size * 0.52
    if right:
        sh.line((tx, ty), (tx + w + 2, ty), "text", 0.15)
        sh.text((tx + 1, ty + 0.9), text, size)
    else:
        sh.line((tx - w - 2, ty), (tx, ty), "text", 0.15)
        sh.text((tx - 1, ty + 0.9), text, size, "right")


def _vdim(sh, x, ya, yb, text, size=2.3, left=False):
    """A vertical size with ticks and its text."""
    sh.line((x, ya), (x, yb), "dim", 0.15)
    for yq in (ya, yb):
        sh.line((x - 1.4, yq), (x + 1.4, yq), "dim", 0.13)
        sh.line((x - 0.8, yq - 0.8), (x + 0.8, yq + 0.8), "dim", 0.3)
    if left:
        sh.text((x - 1.2, (ya + yb) / 2 - 0.9), text, size, "right", "dim")
    else:
        sh.text((x + 1.6, (ya + yb) / 2 - 0.9), text, size, "left", "dim")


def _hdim(sh, xa, xb, y, text, size=2.3):
    sh.line((xa, y), (xb, y), "dim", 0.15)
    for xq in (xa, xb):
        sh.line((xq, y - 1.4), (xq, y + 1.4), "dim", 0.13)
        sh.line((xq - 0.8, y - 0.8), (xq + 0.8, y + 0.8), "dim", 0.3)
    sh.text(((xa + xb) / 2, y + 0.9), text, size, "center", "dim")


def _title(sh, x, y, name, scale="1:20", note=""):
    """«S1 1:20» on a rule; the note under it (« · » starts a new line)."""
    """«S1 1:20» on a rule (the standard's detail titles)."""
    sh.text((x, y), f"{name}   {scale}", 3.8, "center", "text", True)
    w = (len(name) + len(scale) + 3) * 1.9
    sh.line((x - w / 2 - 2, y - 1.6), (x + w / 2 + 2, y - 1.6), "text", 0.4)
    for i, ln in enumerate(str(note).split(" · ") if note else []):
        sh.text((x, y - 6.0 - i * 4.2), ln, 2.5, "center")


def slab_section(sh, E, mark, cx, ytop, k=50.0, slot=150.0):
    """A suspended slab across its short span, whole, as the standard's S1,
    S2: the slab on its two beams, the bottom mat with 180° hooks up and the
    top mat with hooks down, both hooked into the beams, the cross bars as
    dots; the thickness, the span between the beam centres «(ด้านสั้น)», the
    bar spacing «#» (both ways) and the title at its own scale."""
    lib = E["lib"]
    sp = lib.get(mark, {})
    t = float(sp.get("t", 0.10))
    _n, bname, _d, s_ = D._bars(sp.get("bars"))
    s_ = s_ or 0.20
    rooms = [s["room"] for s in E["slabs"] if s["mark"] == mark]
    L = min(min(float(r["w"]), float(r["d"])) for r in rooms) if rooms else 3.0
    lvl = next((s["floor"] for s in E["slabs"] if s["mark"] == mark), 1)
    bm = [lib[b["mark"]] for b in E["beams"] if b["level"] == lvl and b["mark"] in lib] or [{"b": 0.2, "h": 0.4}]
    bb, bh = float(bm[0].get("b", 0.2)), float(bm[0].get("h", 0.4))
    sc = next((v for v in (20, 25, 30, 40, 50) if (L + bb) * 1000 / v <= slot - 26), 50)
    k = 1000.0 / sc
    x0 = cx - L * k / 2

    def P(u, z):
        return (x0 + u * k, ytop + z * k)
    hd = min(bh, 0.30)                                          # the beams shown to a break
    # concrete
    sh.line(P(-bb / 2, 0), P(L + bb / 2, 0), "cut", 0.5)
    sh.line(P(bb / 2, -t), P(L - bb / 2, -t), "cut", 0.5)
    for uc in (0.0, L):
        sh.poly([P(uc - bb / 2, 0), P(uc - bb / 2, -hd), P(uc + bb / 2, -hd), P(uc + bb / 2, 0)], "cut", 0.5,
                closed=False)
        _break_h(sh, P(0, -hd)[1], P(uc - bb / 2, 0)[0], P(uc + bb / 2, 0)[0])
    c = 0.025
    e_ = bb / 2 - 0.04                                           # into the beams
    hk = 0.045
    # bottom mat: 180° hooks up at both ends; top mat: hooks down
    sh.poly([P(-e_ + hk, -t + c + hk), P(-e_, -t + c + hk), P(-e_, -t + c), P(L + e_, -t + c), P(L + e_, -t + c + hk),
             P(L + e_ - hk, -t + c + hk)], "rebar", 0.45, closed=False)
    sh.poly([P(-e_, -c - 0.12), P(-e_, -c), P(L + e_, -c), P(L + e_, -c - 0.12)], "rebar", 0.45, closed=False)
    u = bb / 2 + 0.03
    while u < L - bb / 2 - 0.02:                                # the cross bars (dots), both mats
        _dot(sh, P(u, -t + c + 0.014), 0.42)
        _dot(sh, P(u, -c - 0.014), 0.42)
        u += s_
    lab = f"{bname} มม.@{s_:.3f}#".replace("0#", "#").replace("0#", "#")
    um = L / 2 + s_ / 2
    _leader(sh, P(um, -c), P(um, 0)[0] + 2, P(0, 0)[1] + 8, lab)
    _leader(sh, P(um, -t + c), P(um, 0)[0] + 2, P(0, -t)[1] - 8, lab)
    _vdim(sh, P(L + bb / 2, 0)[0] + 8, P(0, -t)[1], P(0, 0)[1], f"{t:.2f}")
    yb = P(0, -hd)[1] - 9
    for uc in (0.0, L):                                         # the span between the beam centres
        sh.line(P(uc, -hd - 0.04), (P(uc, 0)[0], yb - 1.4), "dim", 0.12)
    _hdim(sh, P(0, 0)[0], P(L, 0)[0], yb, f"{L:.2f}")
    sh.text((P(L / 2, 0)[0], yb - 3.8), f"{mark} (ด้านสั้น)", 2.4, "center")
    _title(sh, P(L / 2, 0)[0], yb - 13, mark, f"1:{sc}")
    return yb - 20


def ground_slab(sh, E, mark, x, ytop, k=50.0):
    """A slab on the ground (the standard's S0): against the ground beam with
    an asphalt joint, one mesh, compacted sand under it, the soil."""
    lib = E["lib"]
    sp = lib.get(mark, {})
    t = float(sp.get("t", 0.10))
    sand = 0.10
    _n, bname, _d, s_ = D._bars(sp.get("bars"))
    s_ = s_ or 0.20
    W = 1.6

    def P(u, z):
        return (x + u * k, ytop + z * k)
    bw = 0.20
    sh.rect(*P(-bw, -0.40), *P(0, 0.0), "cut", 0.5)                       # the ground beam
    sh.line(P(0.01, 0.0), P(W, 0.0), "cut", 0.5)
    sh.line(P(0.01, -t), P(W, -t), "cut", 0.5)
    sh.line(P(0.01, 0.0), P(0.01, -t), "cut", 0.3)
    _break_v(sh, P(W, 0)[0], P(0, -t)[1], P(0, 0)[1])
    for z in (-0.02, -t + 0.02):                                          # the asphalt joint
        pass
    sh.fill([P(0.0, 0.0), P(0.01, 0.0), P(0.01, -t), P(0.0, -t)], "hatch", 0.0)
    sh.rect(*P(0.01, -t - sand), *P(W, -t), "cut", 0.2)
    _sand(sh, *P(0.01, -t - sand), *P(W, -t))
    _soil(sh, P(-bw, 0)[0], P(W, 0)[0], P(0, -t - sand)[1], 3.0)
    c = t / 2
    sh.poly([P(0.06, -c + 0.03), P(0.06, -c), P(W - 0.02, -c)], "rebar", 0.45, closed=False)
    u = 0.12
    while u < W - 0.05:
        _dot(sh, (P(u, -c)[0], P(u, -c)[1] + 0.8), 0.45)
        u += s_
    _leader(sh, P(0.005, -0.01), P(0.45, 0)[0], P(0, 0)[1] + 11, "รอยต่ออุดด้วยแอสฟัลท์ หนา 1 ซม.")
    _leader(sh, P(0.6, -c), P(0.8, 0)[0], P(0, 0)[1] + 5.5, f"{bname} มม.@{s_:.3f} #".replace(".000", ""))
    sh.text((P(W / 2 + 0.2, 0)[0], P(0, -t - sand / 2)[1] - 0.9), "ทรายหยาบบดอัดแน่น", 2.3, "center")
    _vdim(sh, P(W, 0)[0] + 5, P(0, -t)[1], P(0, 0)[1], f"{t:.2f}")
    _vdim(sh, P(W, 0)[0] + 5, P(0, -t - sand)[1], P(0, -t)[1], f"{sand:.2f}")
    _title(sh, P(W / 2, 0)[0], P(0, -0.40)[1] - 14, mark, note="(พื้นวางบนดิน)")


def column_joint(sh, E, x, ytop, kind, k=50.0):
    """รอยต่อเสา: ``kind`` "top" — the column ends at the roof beam, its bars
    bent 90° into the beam (0.30); "lap" — the column passes a floor beam,
    the bars lapped 40d above the floor."""
    lib = E["lib"]
    col = next((lib[c["mark"]] for c in E["columns"] if c["mark"] in lib), {"b": 0.2, "h": 0.2})
    cm = next((c["mark"] for c in E["columns"]), "C1")
    b = float(col.get("b", 0.2))
    n, cname, d, _s = D._bars(col.get("main"))
    lvl = E["n"] if kind == "top" else 1
    bms = [b_ for b_ in E["beams"] if b_["level"] == lvl and b_["mark"] in lib]
    bmark = bms[0]["mark"] if bms else ("RB1" if kind == "top" else "B1")
    bh = float(lib.get(bmark, {}).get("h", 0.4))

    def P(u, z):
        return (x + u * k, ytop + z * k)
    c = 0.04
    if kind == "top":
        zb = -bh
        sh.line(P(0, -bh - 0.9), P(0, 0), "cut", 0.5)                      # the column's outer face
        sh.line(P(0, 0), P(b + 0.9, 0), "cut", 0.5)                         # the beam top
        sh.line(P(b, -bh - 0.9), P(b, zb), "cut", 0.5)
        sh.line(P(b, zb), P(b + 0.9, zb), "cut", 0.5)
        _break_h(sh, P(0, -bh - 0.9)[1], P(0, 0)[0], P(b, 0)[0])
        _break_v(sh, P(b + 0.9, 0)[0], P(0, zb)[1], P(0, 0)[1])
        for uu in (c, b - c):                                               # the bars, bent into the beam
            sh.poly([P(uu, -bh - 0.9), P(uu, -c - (0 if uu < b / 2 else 0.03)),
                     P(uu + 0.30, -c - (0 if uu < b / 2 else 0.03))], "rebar", 0.45, closed=False)
        z_ = -bh - 0.85
        while z_ < -c - 0.05:
            sh.line(P(c - 0.01, z_), P(b - c + 0.01, z_), "rebar", 0.2)
            z_ += 0.15
        _hdim(sh, P(c, 0)[0], P(c + 0.30, 0)[0], P(0, 0)[1] + 5, "0.30")
        _leader(sh, P(b - c, -bh - 0.5), P(b + 0.5, 0)[0], P(0, -bh - 0.5)[1], f"{cm} ({n} {cname} มม.)")
        _leader(sh, P(b + 0.6, -bh / 2), P(b + 0.95, 0)[0] + 3, P(0, 0)[1] + 7, f"คาน {bmark}")
        _hdim(sh, P(0, 0)[0], P(b, 0)[0], P(0, -bh - 0.9)[1] - 5, f"{b:.2f}")
        _vdim(sh, P(b + 0.9, 0)[0] + 7, P(0, -bh)[1], P(0, 0)[1], f"{bh:.2f}")
        _title(sh, P(b / 2 + 0.3, 0)[0], P(0, -bh - 0.9)[1] - 15, f"รอยต่อเสา {cm} กับคาน {bmark}",
               note=f"หมายเหตุ เสา {cm} ขึ้นจากฐานราก ถึงคานหลังคา {bmark} · เหล็กยืนงอฉากเข้าคาน ยาว 0.30 ม.")
    else:
        lap = max(0.30, 40 * d / 1000)
        sh.line(P(0, -bh - 0.7), P(0, lap + 0.4), "cut", 0.5)
        sh.line(P(b, -bh - 0.7), P(b, -bh), "cut", 0.5)
        sh.line(P(b, -bh), P(b + 0.8, -bh), "cut", 0.5)
        sh.line(P(b, 0), P(b + 0.8, 0), "cut", 0.5)
        sh.line(P(b, 0), P(b, lap + 0.4), "cut", 0.5)
        _break_h(sh, P(0, -bh - 0.7)[1], P(0, 0)[0], P(b, 0)[0])
        _break_h(sh, P(0, lap + 0.4)[1], P(0, 0)[0], P(b, 0)[0])
        _break_v(sh, P(b + 0.8, 0)[0], P(0, -bh)[1], P(0, 0)[1])
        for uu in (c, b - c):
            inner = 0.02 if uu < b / 2 else -0.02
            sh.poly([P(uu, -bh - 0.7), P(uu, -0.05), P(uu + inner, 0.05), P(uu + inner, lap)], "rebar", 0.45,
                    closed=False)                                           # the lower bars, cranked
            sh.line(P(uu, 0.0), P(uu, lap + 0.4), "rebar", 0.45)            # the upper bars from the floor
        z_ = -bh - 0.65
        while z_ < lap + 0.38:
            sh.line(P(c - 0.01, z_), P(b - c + 0.01, z_), "rebar", 0.2)
            z_ += 0.10 if 0 <= z_ <= lap else 0.15
        _vdim(sh, P(0, 0)[0] - 6, P(0, 0)[1], P(0, lap)[1], f"{lap:.2f}", left=True)
        sh.text((P(0, 0)[0] - 8, P(0, lap / 2)[1] - 5.5), "(40d)", 2.2, "right", "dim")
        _leader(sh, P(b + 0.5, -bh / 2), P(b + 0.85, 0)[0] + 3, P(0, 0)[1] + 5, f"คาน {bmark}")
        _leader(sh, P(b - c, lap / 2), P(b + 0.4, 0)[0], P(0, lap / 2)[1] + 4,
                "ทาบเหล็กยืนเหนือพื้น · ปลอกเสริม @0.10")
        _hdim(sh, P(0, 0)[0], P(b, 0)[0], P(0, -bh - 0.7)[1] - 5, f"{b:.2f}")
        _vdim(sh, P(b + 0.8, 0)[0] + 7, P(0, -bh)[1], P(0, 0)[1], f"{bh:.2f}")
        _title(sh, P(b / 2 + 0.3, 0)[0], P(0, -bh - 0.7)[1] - 15, f"รอยต่อเสา {cm} ที่ระดับพื้นชั้น 2",
               note=f"หมายเหตุ ทาบเหล็กยืนเหนือพื้น 40 เท่า = {lap:.2f} ม. · ปลอกเสริมช่วงทาบ @0.10")


def edge_rib(sh, E, x, ytop, k=50.0):
    """แบบขยายครีบ คสล. รอบอาคาร: the ground beam at the floor edge, a rib
    0.10 thick under it to below the ground, Ø9@0.25 and 1 DB12 at its foot."""
    lib = E["lib"]
    gb = next((b_["mark"] for b_ in E["beams"] if b_["level"] == 0 and b_["mark"] in lib), "GB1")
    bw, bh = float(lib.get(gb, {}).get("b", 0.2)), float(lib.get(gb, {}).get("h", 0.4))
    gl = float(E.get("GL", -0.5))
    zr = min(gl - 0.10, -bh - 0.25)

    def P(u, z):
        return (x + u * k, ytop + z * k)
    sh.rect(*P(0, -bh), *P(bw, 0), "cut", 0.5)
    sh.rect(*P(0, zr), *P(0.10, -bh), "cut", 0.5)                            # the rib on the outer face
    sh.line(P(bw, 0), P(bw + 0.9, 0), "cut", 0.5)                             # the floor slab
    sh.line(P(bw, -0.10), P(bw + 0.9, -0.10), "cut", 0.5)
    _break_v(sh, P(bw + 0.9, 0)[0], P(0, -0.10)[1], P(0, 0)[1])
    sh.line(P(-0.9, gl), P(0, gl), "cut", 0.4)                                 # the ground outside
    _soil(sh, P(-0.9, 0)[0], P(0, 0)[0], P(0, gl)[1], 3.0)
    sh.poly([P(0.05, -0.05), P(0.05, zr + 0.04), P(0.08, zr + 0.04)], "rebar", 0.45, closed=False)
    _dot(sh, (P(0.05, 0)[0], P(0, zr + 0.06)[1]), 0.6)
    for zz, txt in ((0.0, "±0.00"), (gl, f"{gl:+.2f}")):
        q = P(-0.5 if zz else -0.3, zz)
        sh.poly([(q[0], q[1]), (q[0] - 1.4, q[1] + 2.2), (q[0] + 1.4, q[1] + 2.2)], "dim", 0.2)
        sh.text((q[0] + 2.2, q[1] + 0.8), "ระดับพื้น ±0.00" if not zz else f"ระดับดิน {txt}", 2.3, "left", "dim")
    sh.line(P(-0.6, 0), P(0, 0), "dim", 0.13)
    _leader(sh, P(0.05, (zr - bh) / 2), P(0.6, 0)[0] + 4, P(0, (zr - bh) / 2)[1], "Ø9 มม.@0.25")
    _leader(sh, P(0.07, zr + 0.06), P(0.6, 0)[0] + 4, P(0, zr)[1] - 2, "1 DB12 มม.")
    _leader(sh, P(bw / 2 + 0.1, -bh * 0.6), P(0.6, 0)[0] + 4, P(0, -bh * 0.6)[1], f"คาน {gb}")
    _vdim(sh, P(bw + 0.9, 0)[0] + 6, P(0, -bh)[1], P(0, 0)[1], f"{bh:.2f}")
    _vdim(sh, P(bw + 0.9, 0)[0] + 6, P(0, zr)[1], P(0, -bh)[1], f"{-bh - zr:.2f}")
    _hdim(sh, P(0, 0)[0], P(0.10, 0)[0], P(0, zr)[1] - 5, "0.10")
    _title(sh, P(0.2, 0)[0], P(0, zr)[1] - 16, "แบบขยายครีบ คสล. รอบอาคาร")


def s_slab_std(sh, E):
    """ขยายพื้น รอยต่อเสา ครีบ คสล. (the standard's S-16), at 1:20."""
    x0, y0, x1, y1 = D.drawing_area()
    lib = E["lib"]
    k = 50.0
    marks = sorted({s["mark"] for s in E["slabs"]})
    hung = [m for m in marks if not int(lib.get(m, {}).get("ground") or 0)]
    ground = [m for m in marks if int(lib.get(m, {}).get("ground") or 0)]
    W = x1 - x0
    items = [("s", m) for m in hung[:3]] + [("g", m) for m in ground[:1]]
    if D.bathrooms(E):
        items.append(("d", None))
    items = items[:3]
    wt = {"s": 2.2, "g": 1.4, "d": 1.3}                     # the slots: the slab sections widest
    tot = sum(wt[kd] for kd, _m in items)
    xa = x0
    for kind, m in items:                                   # the slabs across the top, each in its slot
        sw = W * wt[kind] / tot
        cx = xa + sw / 2
        xa += sw
        if kind == "s":
            slab_section(sh, E, m, cx, y1 - 30, k, sw)
        elif kind == "g":
            ground_slab(sh, E, m, cx - 40, y1 - 26, k)
        else:
            drop_detail(sh, E, cx, y1 - 42, 100.0)
    ym = y0 + 112                                           # the joints and the rib, the lower half
    column_joint(sh, E, x0 + 30, ym, "top", k)
    if E["n"] > 1:
        column_joint(sh, E, x0 + W * 0.40, ym - 8, "lap", k)
    edge_rib(sh, E, x0 + W * 0.72, ym + 4, k)
    sh.scale = "1:20"
    return 20


def adim(sh, p, q, off, text, size=2.3):
    """An aligned size from p to q (paper), set ``off`` mm to the left of
    p→q: extension lines, the line, ticks, the text along it (the standard's
    sizes along the stair)."""
    import math as _m
    dx, dy = q[0] - p[0], q[1] - p[1]
    L = _m.hypot(dx, dy) or 1.0
    ux, uy = dx / L, dy / L
    nx, ny = -uy, ux
    a = (p[0] + nx * off, p[1] + ny * off)
    b = (q[0] + nx * off, q[1] + ny * off)
    sg = 1 if off >= 0 else -1
    for s0, s1 in ((p, a), (q, b)):
        sh.line((s0[0] + nx * sg * 1.0, s0[1] + ny * sg * 1.0), (s1[0] + nx * sg * 1.4, s1[1] + ny * sg * 1.4),
                "dim", 0.13)
    sh.line(a, b, "dim", 0.15)
    for t in (a, b):
        sh.line((t[0] - 0.8 * (ux + nx), t[1] - 0.8 * (uy + ny)), (t[0] + 0.8 * (ux + nx), t[1] + 0.8 * (uy + ny)),
                "dim", 0.3)
    ang = _m.degrees(_m.atan2(dy, dx))
    if ang > 90 or ang < -90:
        ang += 180
    m = ((a[0] + b[0]) / 2 + nx * sg * 0.9, (a[1] + b[1]) / 2 + ny * sg * 0.9)
    sh.text(m, text, size, "center", "dim", angle=ang)


def drop_detail(sh, E, cx, ytop, k=50.0, drop=0.05):
    """ขยาย พื้นห้องน้ำลดระดับ (the standard's «ขยาย 2»): the beam between a
    room and the bathroom, the bathroom slab ``drop`` lower, both slabs'
    bars hooked into the beam, the beam's bars; the sizes and levels."""
    lib = E["lib"]
    sl = next((lib[s["mark"]] for s in E["slabs"] if s["floor"] > 0 and s["mark"] in lib),
              next((lib[s["mark"]] for s in E["slabs"] if s["mark"] in lib), {"t": 0.10, "bars": "RB9@0.20"}))
    t = float(sl.get("t", 0.10))
    _n, bname, _d, s_ = D._bars(sl.get("bars"))
    bmk = next((b["mark"] for b in E["beams"] if b["level"] == 1 and b["mark"] in lib), "B1")
    bb, bh = float(lib.get(bmk, {}).get("b", 0.2)), float(lib.get(bmk, {}).get("h", 0.4))
    W = 0.40
    x = cx - bb * k / 2

    def P(u, z):
        return (x + u * k, ytop + z * k)
    # concrete: the room slab, the beam, the lower bathroom slab
    sh.poly([P(-W, 0), P(bb, 0), P(bb, -drop), P(bb + W, -drop)], "cut", 0.5, closed=False)
    sh.poly([P(-W, -t), P(0, -t), P(0, -bh), P(bb, -bh), P(bb, -drop - t), P(bb + W, -drop - t)], "cut", 0.5,
            closed=False)
    _break_v(sh, P(-W, 0)[0], P(0, -t)[1], P(0, 0)[1])
    _break_v(sh, P(bb + W, 0)[0], P(0, -drop - t)[1], P(0, -drop)[1])
    c = 0.025
    sh.rect(*P(c, -bh + c), *P(bb - c, -c), "rebar", 0.25)                 # the beam's stirrup and bars
    for uu in (c + 0.015, bb - c - 0.015):
        for zz in (-c - 0.015, -bh + c + 0.015):
            _dot(sh, P(uu, zz), 0.55)
    # the slabs' bars: top bars hooked down into the beam, bottom bars into it
    sh.poly([P(-W, -c), P(bb - c - 0.03, -c), P(bb - c - 0.03, -c - 0.12)], "rebar", 0.45, closed=False)
    sh.poly([P(-W, -t + c), P(c + 0.06, -t + c)], "rebar", 0.45, closed=False)
    sh.poly([P(bb + W, -drop - c), P(c + 0.03, -drop - c), P(c + 0.03, -drop - c - 0.12)], "rebar", 0.45,
            closed=False)
    sh.poly([P(bb + W, -drop - t + c), P(bb - c - 0.06, -drop - t + c)], "rebar", 0.45, closed=False)
    lab = f"{bname} มม.@{(s_ or 0.2):.3f}#".replace("0#", "#").replace("0#", "#")
    _leader(sh, P(-W * 0.2, -c), P(-W * 0.2, 0)[0] + 4, P(0, 0)[1] + 13, lab)
    _leader(sh, P(bb / 2, -bh / 2), P(bb + W * 0.5, 0)[0], P(0, -bh)[1] - 3, f"คาน {bmk}")
    for zz, txt, uu, up in ((0.0, "ระดับพื้นห้อง ±0.00", -W * 0.92, 0.0),
                            (-drop, f"ระดับพื้นห้องน้ำ {-drop:+.2f}", bb + W * 0.35, 6.0)):
        q = P(uu, zz)
        qa = (q[0], q[1] + up)
        if up:
            sh.line(q, qa, "dim", 0.13)
        sh.poly([qa, (qa[0] - 1.4, qa[1] + 2.2), (qa[0] + 1.4, qa[1] + 2.2)], "dim", 0.2)
        sh.text((qa[0] + 2.0, qa[1] + 1.0), txt, 2.3, "left", "dim")
    _vdim(sh, P(bb + W, 0)[0] + 6, P(0, -drop)[1], P(0, 0)[1], f"{drop:.2f}")
    sh.line(P(bb, 0), (P(bb + W, 0)[0] + 7.4, P(0, 0)[1]), "dim", 0.12, True)
    _vdim(sh, P(-W, 0)[0] - 4, P(0, -t)[1], P(0, 0)[1], f"{t:.2f}", left=True)
    _hdim(sh, P(0, 0)[0], P(bb, 0)[0], P(0, -bh)[1] - 5, f"{bb:.2f}")
    _title(sh, P(bb / 2, 0)[0], P(0, -bh)[1] - 15, "ขยาย 1", f"1:{round(1000 / k)}",
           f"(พื้นห้องน้ำลดระดับ {drop:.2f} ม.)")
