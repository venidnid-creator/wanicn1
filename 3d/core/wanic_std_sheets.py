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
            sh.line(P(ox, y0), P(hx, (y0 + y1) / 2), lay, 0.1)
            sh.line(P(ox, y1), P(hx, (y0 + y1) / 2), lay, 0.1)
        elif kind == "awning":
            sh.line(P(x0, y0), P((x0 + x1) / 2, y1), lay, 0.1)
            sh.line(P(x1, y0), P((x0 + x1) / 2, y1), lay, 0.1)
        elif kind == "louvre":
            z = y0 + 0.08
            while z < y1 - 0.04:
                sh.line(P(x0, z), P(x1, z), lay, 0.1)
                z += 0.09
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
