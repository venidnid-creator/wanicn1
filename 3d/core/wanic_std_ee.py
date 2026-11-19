# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
"""แบบระบบไฟฟ้า (EE) laid out as the standard house plans of กรมโยธาธิการ
และผังเมือง do: EE-01 the sheet list, the specification and the symbols;
EE-02 the main panel (รายละเอียดแผงเมนสวิตช์). The circuits come from the
rooms' services (wanic_mep.plan) — the same ones the 3-D model and the BOQ
use. The wording and the drawings are this program's own."""
from __future__ import annotations

import math

from core import wanic_drawings as D

ROW = 7.2
CONDUIT = {2.5: 15, 4: 15, 6: 20, 10: 25, 16: 25, 25: 32, 35: 32}
MAINS = ((32, 6, 6), (50, 10, 10), (63, 16, 10), (80, 25, 16), (100, 35, 16))   # (A, L/N mm², earth mm²)


def circuits(E) -> dict:
    """The panel: {"circuits": [{no, name, kind, breaker, rcbo, wire, conduit,
    va, load}], "va", "amp", "main", "main_wire", "earth", "meter"}. Lighting
    10 points a circuit, sockets 8, one circuit a water heater and an AC."""
    from core import wanic_mep as MEP
    rooms = MEP.plan({}, E)
    out = []
    lights = sum(r["lights"] for r in rooms)
    outs = sum(r["outlets"] for r in rooms)
    for i in range(max(1, math.ceil(lights / 10))):
        n = min(10, lights - i * 10)
        out.append(dict(name="แสงสว่าง", kind="light", breaker="16AT,1P", rcbo=False, wire=2.5,
                        va=n * 18, load=f"{n} จุด"))
    for i in range(max(1, math.ceil(outs / 8))):
        n = min(8, outs - i * 8)
        out.append(dict(name="เต้ารับ", kind="socket", breaker="16AT,1P", rcbo=True, wire=2.5,
                        va=n * 180, load=f"{n} จุด"))
    for r in rooms:
        nm = r["room"].get("name") or ""
        if r["heater"]:
            w_ = float(r.get("heater_wire") or MEP.heater_wire(r.get("heater_w") or MEP.HEATER_W))
            watts = int(r.get("heater_w") or MEP.HEATER_W)
            out.append(dict(name="เครื่องทำน้ำอุ่น", room=nm, kind="heater",
                            breaker=MEP.WIRES.get(w_, "1P 32 A").replace("1P ", "").replace(" A", "AT") + ",1P",
                            rcbo=True, wire=w_, va=watts, load=f"{watts:,} W"))
        if r["ac"]:
            w_ = float(r.get("ac_wire") or MEP.ac_wire(r["ac"]))
            out.append(dict(name="เครื่องปรับอากาศ", room=nm, kind="ac",
                            breaker=MEP.WIRES.get(w_, "1P 20 A").replace("1P ", "").replace(" A", "AT") + ",1P",
                            rcbo=False, wire=w_, va=int(r["ac"] / 9), load=f"{r['ac']:,} BTU"))
    for i, c in enumerate(out, 1):
        c["no"] = i
        c["conduit"] = CONDUIT.get(c["wire"], 20)
    va = sum(c["va"] for c in out)
    amp = va / 220 * 0.8
    main, mw, ew = next((m for m in MAINS if m[0] >= amp * 1.25), MAINS[-1])
    meter = "15(45)A" if main <= 50 else "30(100)A"
    return {"circuits": out, "va": va, "amp": amp, "main": f"{main}AT,2P", "main_a": main,
            "main_wire": mw, "earth": ew, "meter": meter}


# -- EE-01 ------------------------------------------------------------------------------------

def _sym(kind):
    def f(sh, x, y):
        if kind == "down":
            sh.circle((x, y), 1.6, "elec", 0.35)
            sh.line((x - 2.6, y), (x + 2.6, y), "elec", 0.25)
            sh.line((x, y - 2.6), (x, y + 2.6), "elec", 0.25)
        elif kind in ("t8", "t8b"):
            L = 5.0 if kind == "t8" else 7.5
            sh.rect(x - L, y - 0.8, x + L, y + 0.8, "elec", 0.35)
            sh.line((x - L, y), (x + L, y), "elec", 0.2)
        elif kind == "wall":
            sh.arc((x, y - 0.6), 2.2, 0, 180, "elec", 0.35)
            sh.line((x - 3.0, y - 0.6), (x + 3.0, y - 0.6), "elec", 0.35)
            sh.line((x, y - 0.6), (x, y + 1.6), "elec", 0.25)
        elif kind == "sw1":
            sh.fill([(x + 0.9 * math.cos(a * math.pi / 6), y + 0.9 * math.sin(a * math.pi / 6)) for a in range(12)],
                    "elec", 0.0)
        elif kind == "sw2":
            sh.fill([(x + 0.9 * math.cos(a * math.pi / 6), y + 0.9 * math.sin(a * math.pi / 6)) for a in range(12)],
                    "elec", 0.0)
            sh.line((x + 0.6, y + 0.6), (x + 2.4, y + 2.4), "elec", 0.35)
            sh.line((x + 2.4, y + 2.4), (x + 3.2, y + 1.6), "elec", 0.35)
        elif kind in ("sock", "sockwp"):
            sh.circle((x, y), 1.8, "elec", 0.35)
            sh.line((x - 1.8, y), (x + 1.8, y), "elec", 0.3)
            if kind == "sockwp":
                sh.rect(x - 2.6, y - 2.6, x + 2.6, y + 2.6, "elec", 0.3)
        elif kind in ("wh", "sb"):
            sh.circle((x, y), 2.2, "elec", 0.35)
            sh.text((x, y - 0.8), "WH" if kind == "wh" else "SB", 1.6, "center", "elec", True)
        elif kind == "bell":
            sh.rect(x - 2.0, y - 1.6, x + 2.0, y + 1.0, "elec", 0.35)
            sh.arc((x, y + 1.0), 2.0, 0, 180, "elec", 0.3)
            sh.text((x, y - 1.2), "B", 1.5, "center", "elec", True)
        elif kind == "lp":
            sh.text((x, y + 1.4), "LP", 1.8, "center", "elec", True)
            sh.rect(x - 2.6, y - 1.8, x + 2.6, y + 0.8, "elec", 0.35)
            sh.fill([(x - 2.6, y - 1.8), (x + 2.6, y - 1.8), (x + 2.6, y + 0.8)], "elec", 0.0)
        elif kind == "ac":
            sh.rect(x - 3.4, y - 1.4, x + 3.4, y + 1.4, "elec", 0.35)
            sh.text((x, y - 0.8), "AC", 1.6, "center", "elec", True)
        elif kind == "run":
            sh.line((x - 5, y), (x + 5, y), "elec", 0.3)
            for xx in (x - 1.5, x + 1.5):
                sh.line((xx - 0.6, y - 1.2), (xx + 0.6, y + 1.2), "elec", 0.25)
        elif kind == "home":
            sh.line((x - 5, y), (x + 3, y), "elec", 0.3)
            sh.fill([(x + 5, y), (x + 2.6, y + 1.0), (x + 2.6, y - 1.0)], "elec", 0.0)
    return f


SYMBOLS = [
    ("down", "ดวงโคมดาวน์ไลท์ ติดฝังฝ้าเพดาน หลอด LED ขั้วเกลียว E27 ไม่น้อยกว่า 7 วัตต์"),
    ("t8", "ดวงโคม LED TUBE (T8) แบบเปลือย ติดลอย หลอด 1 × 10 วัตต์"),
    ("t8b", "ดวงโคม LED TUBE (T8) แบบเปลือย ติดลอย หลอด 1 × 20 วัตต์"),
    ("wall", "ดวงโคมไฟกิ่งนอกอาคาร กันน้ำ หลอด LED E27 ไม่น้อยกว่า 7 วัตต์"),
    ("sw1", "สวิตช์ทางเดียว 16A 250V ติดฝังผนัง สูงจากพื้น 1.20 ม."),
    ("sw2", "สวิตช์สองทาง 16A 250V ติดฝังผนัง สูงจากพื้น 1.20 ม."),
    ("sock", "เต้ารับไฟฟ้าคู่ มีขั้วสายดิน 16A 250V ติดฝังผนัง สูงจากพื้น 0.30 ม. (เว้นแต่ระบุ)"),
    ("sockwp", "เต้ารับไฟฟ้าคู่ มีขั้วสายดิน ชนิดมีฝาปิดกันน้ำ (ห้องน้ำ ครัว นอกอาคาร)"),
    ("wh", "กล่องต่อสายเครื่องทำน้ำอุ่น ติดผนังสูงจากพื้น 1.80 ม. (ใช้วงจรเฉพาะ + RCBO)"),
    ("ac", "จุดต่อไฟเครื่องปรับอากาศ ใช้วงจรเฉพาะ ขนาดตามตารางในแผงเมน"),
    ("bell", "กริ่งไฟฟ้า ติดผนังต่ำกว่าฝ้าเพดานประมาณ 0.20 ม."),
    ("sb", "สวิตช์กริ่ง ชนิดกันน้ำ ติดเสาประตูรั้ว สูงจากพื้น 1.50 ม."),
    ("lp", "แผงเมนสวิตช์ (LP) ติดผนัง สูงจากพื้นถึงขอบบนตู้ 1.80 ม."),
    ("run", "แนวเดินสายไฟฟ้าในท่อร้อยสาย (ขีด = จำนวนสาย)"),
    ("home", "สายวงจรย่อยกลับแผง (เลขวงจรตามแผงเมนสวิตช์)"),
]

NOTES = [
    ("รายละเอียดข้อกำหนด", None),
    ("1. การติดตั้งให้เป็นไปตามมาตรฐานการติดตั้งทางไฟฟ้าสำหรับประเทศไทย ของ วสท. ฉบับล่าสุด "
     "และข้อกำหนดของการไฟฟ้าส่วนภูมิภาค / การไฟฟ้านครหลวง", 0),
    ("2. ข้อกำหนดการเดินสายไฟฟ้า", 0),
    ("2.1 สายวงจรย่อยแสงสว่าง สายแยกจากสวิตช์เข้าดวงโคม และสายดิน ใช้สาย IEC 01 ขนาด 2.5 ตร.มม. "
     "เดินในท่อร้อยสายอโลหะชนิดยูพีวีซี (uPVC)", 1),
    ("2.2 สายวงจรย่อยเต้ารับไฟฟ้า และสายดิน ใช้สาย IEC 01 ขนาด 2.5 ตร.มม. เดินในท่อร้อยสาย uPVC", 1),
    ("2.3 วงจรเครื่องทำน้ำอุ่นและเครื่องปรับอากาศ ใช้วงจรเฉพาะ ขนาดสายตามแผงเมนสวิตช์", 1),
    ("2.4 รหัสสีของสายไฟฟ้า: สายมีไฟ (L) สีน้ำตาล · สายนิวทรัล (N) สีฟ้า · สายดิน (G) สีเขียวแถบเหลือง", 1),
    ("3. วงจรเต้ารับ วงจรห้องน้ำ เครื่องทำน้ำอุ่น และเต้ารับนอกอาคาร ต้องมีเครื่องตัดไฟรั่ว (RCBO) "
     "ขนาดพิกัดกระแสรั่ว 30 mA", 0),
    ("4. หลักดินแท่งเหล็กหุ้มทองแดง Ø14.2 มม. ยาว 2.40 ม. ความต้านทานดินไม่เกิน 5 โอห์ม "
     "ต่อลงดินที่แผงเมนสวิตช์เพียงจุดเดียว", 0),
    ("5. ท่อร้อยสายฝังในผนัง / พื้น ใช้ท่อ uPVC ท่อเดินลอยนอกอาคารใช้ท่อโลหะ (EMT / IMC) "
     "ยึดด้วยแคล้มป์ทุกระยะไม่เกิน 1.50 ม.", 0),
    ("6. วัสดุอุปกรณ์ไฟฟ้าทั้งหมดต้องเป็นของใหม่ ได้มาตรฐาน มอก. หรือเทียบเท่า "
     "ก่อนติดตั้งให้เสนอตัวอย่างให้ผู้ควบคุมงานอนุมัติ", 0),
    ("7. ก่อนจ่ายไฟให้ทดสอบความเป็นฉนวนของสาย ขั้วสายดินของเต้ารับ และการทำงานของเครื่องตัดไฟรั่วทุกตัว", 0),
]


def ee_index_std(sh, sheets, E):
    """EE-01 «สารบัญแบบงานระบบไฟฟ้า สัญลักษณ์ และรายละเอียดข้อกำหนด»."""
    x0, y0, x1, y1 = D.drawing_area()
    W = x1 - x0
    wl = W * 0.47
    # the sheet list
    yt = y1 - 6
    sh.text((x0 + 2, yt), "สารบัญแบบงานระบบไฟฟ้า", 3.4, "left", "text", True)
    sh.line((x0 + 2, yt - 1.4), (x0 + 52, yt - 1.4), "text", 0.35)
    ee = [s for s in sheets if s.group == "EE"]
    rows = max(len(ee) + 2, 8)
    top = yt - 4
    sh.rect(x0, top - ROW * (rows + 1), x0 + wl, top, "text", 0.45)
    sh.line((x0 + 22, top - ROW * (rows + 1)), (x0 + 22, top), "text", 0.25)
    sh.text((x0 + 11, top - ROW + 2.2), "แผ่นที่", 2.6, "center", "text", True)
    sh.text((x0 + 22 + (wl - 22) / 2, top - ROW + 2.2), "แสดงแบบ", 2.6, "center", "text", True)
    for i in range(rows + 1):
        sh.line((x0, top - ROW * (i + 1)), (x0 + wl, top - ROW * (i + 1)), "text", 0.3 if i == 0 else 0.13)
    for i, s in enumerate(ee):
        yy = top - ROW * (i + 2) + 2.2
        sh.text((x0 + 11, yy), s.code, 2.6, "center")
        sh.text((x0 + 25, yy), s.title, 2.6)
    # the specification under it
    y = top - ROW * (rows + 1) - 8
    for text, lvl in NOTES:
        if lvl is None:
            sh.text((x0 + 2, y), text, 3.0, "left", "text", True)
            sh.line((x0 + 2, y - 1.3), (x0 + 42, y - 1.3), "text", 0.3)
            y -= 6.4
            continue
        for j, ln in enumerate(D._wrap(text, 84 - lvl * 4)):
            sh.text((x0 + 2 + lvl * 4 + (4 if j else 0), y), ln, 2.5)
            y -= 4.4
        y -= 0.9
    # the symbols
    xs = x0 + wl + 6
    ws = x1 - xs
    sh.text((xs + 2, yt), "สัญลักษณ์งานระบบไฟฟ้า", 3.4, "left", "text", True)
    sh.line((xs + 2, yt - 1.4), (xs + 50, yt - 1.4), "text", 0.35)
    rh = min(12.0, (top - y0 - 4 - ROW) / len(SYMBOLS))
    sh.rect(xs, top - ROW - rh * len(SYMBOLS), x1, top, "text", 0.45)
    sh.line((xs + 22, top - ROW - rh * len(SYMBOLS)), (xs + 22, top), "text", 0.25)
    sh.text((xs + 11, top - ROW + 2.2), "สัญลักษณ์", 2.6, "center", "text", True)
    sh.text((xs + 22 + (ws - 22) / 2, top - ROW + 2.2), "รายละเอียด", 2.6, "center", "text", True)
    sh.line((xs, top - ROW), (x1, top - ROW), "text", 0.3)
    for i, (kind, text) in enumerate(SYMBOLS):
        yc = top - ROW - rh * (i + 0.5)
        _sym(kind)(sh, xs + 11, yc)
        lines = D._wrap(text, int((ws - 26) / 1.45))
        for j, ln in enumerate(lines[:2]):
            sh.text((xs + 25, yc - 0.9 + (len(lines[:2]) - 1) * 2.2 - j * 4.4), ln, 2.5)
        sh.line((xs, top - ROW - rh * (i + 1)), (x1, top - ROW - rh * (i + 1)), "text", 0.13)


# -- EE-02 ------------------------------------------------------------------------------------

def _breaker(sh, x, y, h=7.0, two=False):
    """A breaker on a branch going down from the bus at y: the contact, the
    blade open to the right, the trip mark."""
    sh.line((x, y), (x, y - 2.0), "elec", 0.4)
    sh.line((x - 0.9, y - 2.4), (x + 0.9, y - 1.2), "elec", 0.35)        # the trip mark ×
    sh.line((x - 0.9, y - 1.2), (x + 0.9, y - 2.4), "elec", 0.35)
    sh.line((x, y - 2.0 - 0.0), (x + 2.4, y - 2.0 - h * 0.55), "elec", 0.45)
    sh.line((x, y - 2.0 - h * 0.62), (x, y - 2.0 - h), "elec", 0.45)


def ee_panel_std(sh, E):
    """EE-02 «รายละเอียดแผงเมนสวิตช์»: the meter, the service cable, the
    panel LP with its earth and neutral bars, the main breaker and every
    branch (RCBO where the rules ask), the spare ways; each circuit's cable
    and conduit down its line, and what it feeds; the earth rod."""
    x0, y0, x1, y1 = D.drawing_area()
    P = circuits(E)
    cs = P["circuits"]
    spare = max(2, (4 - len(cs) % 4) % 4 + 2)
    n = len(cs) + spare
    W = x1 - x0
    bx0 = x0 + 44                                            # the panel box
    step = max(7.0, min(16.0, (x1 - 10 - bx0 - 44) / n))
    bx1 = bx0 + 44 + step * n + 6
    ytop = y1 - 62
    ybot = ytop - 52
    sh.rect(bx0, ybot, bx1, ytop, "elec", 0.4)
    sh.text((bx1 - 2, ytop + 2.0), "LP", 3.4, "right", "elec", True)
    # the service: meter, L and N down into the panel
    xl, xn = bx0 + 12, bx0 + 18
    sh.text((xl - 4, y1 - 8), f"kWh METER {P['meter']} 1 PHASE 2 WIRE", 2.8, "left", "text", True)
    for xx, t in ((xl, "L"), (xn, "N")):
        sh.text((xx, y1 - 14), t, 2.4, "center")
        sh.poly([(xx, y1 - 16), (xx - 1.0, y1 - 17.6), (xx + 1.0, y1 - 17.6)], "elec", 0.3)
        sh.line((xx, y1 - 17.6), (xx, ytop - 8), "elec", 0.45)
    sh.circle(((xl + xn) / 2, y1 - 34), 3.6, "elec", 0.25)          # the cable's sleeve mark
    sh.line(((xl + xn) / 2 + 3.6, y1 - 34), (bx0 + 70, y1 - 34), "text", 0.18)
    sh.text((bx0 + 40, y1 - 33), f"2-{P['main_wire']} IEC 01-Ø25 mm. uPVC (นอกอาคารเดินในท่อโลหะ)", 2.6)
    # the neutral and earth bars, the main breaker
    gx, nx = bx0 + 8, bx0 + 16
    sh.rect(gx - 1.6, ybot + 8, gx + 1.6, ybot + 22, "elec", 0.35)
    sh.text((gx, ybot + 14), "G", 2.2, "center", "elec", True)
    sh.rect(nx - 1.6, ybot + 8, nx + 1.6, ybot + 22, "elec", 0.35)
    sh.text((nx, ybot + 14), "N", 2.2, "center", "elec", True)
    sh.line((xn, ytop - 8), (nx, ybot + 22), "elec", 0.35)
    xm = bx0 + 28
    sh.line((xl, ytop - 8), (xl, ytop - 10), "elec", 0.45)
    sh.line((xl, ytop - 10), (xm, ytop - 10), "elec", 0.45)
    bus = ytop - 6
    _breaker(sh, xm, bus, 10.0, True)
    _breaker(sh, xm - 4, bus, 10.0, True)
    sh.line((xm - 1.6, bus - 7), (xm + 1.6, bus - 5), "elec", 0.2, True)
    sh.text((xm + 3.0, bus - 4.0), P["main"], 2.4)
    sh.text((xm + 3.0, bus - 8.0), "IC 10kA", 2.4)
    sh.line((xm, bus), (bx0 + 40 + step * (n - 0.5), bus), "elec", 0.8)          # the bus
    sh.line((xm - 4, bus - 12), (xm - 4, ybot + 4), "elec", 0.35)
    sh.text((xm - 4, ybot + 1.0), "N", 2.2, "center")
    sh.text((xm, ybot + 1.0), "L", 2.2, "center")
    # the earth: to the rod, outside the panel
    sh.line((gx, ybot + 8), (gx, ybot - 6), "elec", 0.35)
    sh.line((gx, ybot - 6), (x0 + 16, ybot - 6), "elec", 0.35)
    sh.line((x0 + 16, ybot - 6), (x0 + 16, ybot - 22), "elec", 0.35)
    for i, w in enumerate((6, 4, 2)):
        sh.line((x0 + 16 - w / 2, ybot - 22 - i * 1.4), (x0 + 16 + w / 2, ybot - 22 - i * 1.4), "elec", 0.35)
    sh.text((x0 + 13.6, ybot - 12), f"1-{P['earth']} IEC 01-Ø20 mm. uPVC", 2.4, "left", "text", False, 90)
    sh.text((x0 + 4, ybot - 32), "หลักดินแท่งเหล็กหุ้มทองแดง", 2.6, "left", "text", True)
    sh.text((x0 + 4, ybot - 37), "ขนาด Ø14.2 มม. ยาว 2.40 ม.", 2.5)
    # the branches
    yl = ybot - 66
    for i in range(n):
        x = bx0 + 40 + step * i
        sh.line((x, bus), (x, bus - 4), "elec", 0.45)
        if i < len(cs):
            c = cs[i]
            _breaker(sh, x, bus - 4, 8.0)
            r1 = ("RCBO " if c["rcbo"] else "") + c["breaker"]
            r2 = "IC 6kA" + (" Idn 30mA" if c["rcbo"] else "")
            sh.text((x + 2.4, bus - 11.5), r1, 1.9, "right", "text", c["rcbo"], 90)
            sh.text((x + 4.6, bus - 11.5), r2, 1.7, "right", "text", False, 90)
            sh.line((x, bus - 14), (x, yl + 4), "elec", 0.45)
            sh.text((x + 1.0, ybot + 2.4), str(c["no"]), 2.2)
            sh.poly([(x, yl), (x - 1.0, yl + 2.0), (x + 1.0, yl + 2.0)], "elec", 0.3)
            spec = f"2-{c['wire']:g}/G{c['wire']:g} IEC 01-Ø{c['conduit']} mm. uPVC"
            sh.text((x - 0.8, (ybot + yl) / 2), spec, 2.0, "center", "text", False, 90)
            what = c["name"] + (f" {c['room']}" if c.get("room") else "") + f" ({c['load']})"
            sh.text((x + 0.8, yl - 2.0), what, 2.1, "right", "text", False, 90)
        else:
            sh.line((x, bus - 4), (x, bus - 12), "elec", 0.45)
            sh.text((x + 1.0, ybot + 2.4), str(i + 1), 2.2)
            sh.text((x + 0.8, ybot - 2.0), "ว่าง", 2.2, "right", "text", False, 90)
    sh.text((x0 + 150, y1 - 8), f"โหลดรวม {P['va']:,} VA × 0.8 (ค่าดีมานด์) / 220 V = {P['amp']:.1f} A "
                               f"→ เมน {P['main']} · มิเตอร์ {P['meter']}", 2.6, "left", "text", True)
    sh.text((x0 + 150, y1 - 14), "หมายเหตุ: RCBO หมายถึงเบรกเกอร์ป้องกันไฟรั่วและกระแสเกิน Idn 30 mA", 2.4)
    from core import wanic_std_sheets as STD
    STD.caption_marks(sh, (x0 + 4, y0 + 30), "รายละเอียดแผงเมนสวิตช์", "ไม่ตามมาตราส่วน", None, None,
                      100.0)
