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


# -- EE-03.. the lighting and the socket plans --------------------------------------------------

def _base(sh, E, k, colw=70.0, left=0.0):
    """The floor plan under the electrical layers: grid and sizes, walls and
    doors, the stair (numbered), the fittings, the rooms clear of the stair."""
    x0, y0, x1, y1 = D.drawing_area()
    bx = D.bbox(E, 3.2)
    box = (x0 + left, y0 + 16, x1 - colw, y1)
    fits = (bx[2] - bx[0]) * 1000 / 75 <= box[2] - box[0] and (bx[3] - bx[1]) * 1000 / 75 <= box[3] - box[1] - 14
    v, sc = D.plan_view(sh, E, box=box, pad=3.2, scale=75 if fits else None)
    t = float(E["settings"].get("wall_t") or 0.1)
    D.draw_grid(sh, v, E, ext=3.0, at=(1.6, 2.3))
    D.draw_walls(sh, v, E, k, t, None, swings=True, tags=False)
    D.draw_stairs(sh, v, E, k)
    D.draw_fixtures(sh, v, E, k, labels=False)
    return v, sc


def _free_spot(rm, items, boxes):
    """The point of the room farthest from its symbols (and off the stair)."""
    best, bp = -1.0, (rm["x"] + rm["w"] / 2, rm["y"] + rm["d"] / 2)
    for i in (0.2, 0.3, 0.5, 0.7, 0.8):
        for j in (0.10, 0.22, 0.5, 0.78, 0.90):
            p = (rm["x"] + rm["w"] * i, rm["y"] + rm["d"] * j)
            if any(b[0] - 0.55 < p[0] < b[2] + 0.55 and b[1] - 0.18 < p[1] < b[3] + 0.18 for b in boxes):
                continue
            dw = min(p[0] - rm["x"], rm["x"] + rm["w"] - p[0], p[1] - rm["y"], rm["y"] + rm["d"] - p[1])
            d = min([abs(p[0] - q[0]) + abs(p[1] - q[1]) * 1.6 for q in items] + [dw * 2.2] or [9.0])
            if d > best + 0.05:
                best, bp = d, p
    return bp


def _room_label(sh, v, E, k, rm, spot):
    p = v(*spot)
    D.masked_text(sh, (p[0], p[1] + 1.2), rm.get("name") or "ห้อง", 2.5, "center", True)


def _doors(E, k, rm):
    from core import wanic_building as B
    return [op for op in E["openings"] if op["floor"] == k and op["type"] != "window" and
            B._on_edge(rm, float(op["op"]["x"]), float(op["op"]["y"]), tol=0.06)]


def _edge_of(rm, x, y):
    """(edge name, inward normal) of the room edge through (x, y)."""
    d = {"W": abs(x - rm["x"]), "E": abs(x - rm["x"] - rm["w"]), "S": abs(y - rm["y"]), "N": abs(y - rm["y"] - rm["d"])}
    e = min(d, key=d.get)
    return e, {"W": (1, 0), "E": (-1, 0), "S": (0, 1), "N": (0, -1)}[e]


def _switch_spot(E, k, rm, inner):
    """By the first door, on its latch side, just inside the wall."""
    ds = _doors(E, k, rm)
    x0, y0, x1, y1 = inner
    if not ds:
        return (x0 + 0.15, y0 + 0.30)
    op = ds[0]["op"]
    x, y = float(op["x"]), float(op["y"])
    w = float(op.get("w") or 0.9)
    e, n = _edge_of(rm, x, y)
    if e in ("S", "N"):
        sx = min(max(x + w / 2 + 0.20, x0 + 0.12), x1 - 0.12)
        sy = y0 + 0.12 if e == "S" else y1 - 0.12
    else:
        sy = min(max(y + w / 2 + 0.20, y0 + 0.12), y1 - 0.12)
        sx = x0 + 0.12 if e == "W" else x1 - 0.12
    return (sx, sy)


def _ortho(sh, a, b, w=0.35):
    """A wiring run a→b with one corner (horizontal first)."""
    if abs(a[0] - b[0]) < 0.05 or abs(a[1] - b[1]) < 0.05:
        sh.line(a, b, "elec", w)
    else:
        sh.poly([a, (b[0], a[1]), b], "elec", w, closed=False)


def _home(sh, p, text, up=True):
    """The home run: a short arrow off the item, to the right, «n/LP» over it."""
    a = (p[0] + 2.0, p[1])
    q = (p[0] + 8.0, p[1] + 2.5)
    sh.line(a, q, "elec", 0.35)
    sh.fill([q, (q[0] - 2.2, q[1] - 0.2), (q[0] - 1.4, q[1] - 1.8)], "elec", 0.0)
    D.masked_text(sh, (q[0] + 0.6, q[1] + 0.2), text, 2.2, "left", True)


def _side_notes(sh, x, y, lines, title="หมายเหตุ"):
    sh.text((x, y), title, 3.0, "left", "text", True)
    sh.line((x, y - 1.3), (x + 20, y - 1.3), "text", 0.3)
    y -= 6.0
    for t in lines:
        for j, ln in enumerate(D._wrap(t, 36)):
            sh.text((x + (3 if j else 0), y), ln, 2.4)
            y -= 4.4
        y -= 1.0
    return y


def _assign(cs, kind, counts):
    """Hand out circuit numbers to a sequence of points (``counts`` per room
    in order): the circuits of ``kind`` filled up in turn."""
    nums = [c["no"] for c in cs if c["kind"] == kind]
    cap = 10 if kind == "light" else 8
    out, i, used = [], 0, 0
    for n in counts:
        room = []
        for _ in range(n):
            if used >= cap and i < len(nums) - 1:
                i, used = i + 1, 0
            room.append(nums[i] if nums else 0)
            used += 1
        out.append(room)
    return out


def ee_light_plan(sh, E, k):
    """แปลนไฟฟ้าแสงสว่าง ชั้น k+1 (the standard's EE-03, EE-04): the lights
    on the ceilings, the switch of each room by its door with its letter,
    the lights of a switch marked with the same letter, the wiring, the
    home run of each circuit «n/LP», the panel."""
    from core import wanic_building as B
    from core import wanic_mep as MEP
    from core import wanic_std_sheets as STD
    x0, y0, x1, y1 = D.drawing_area()
    v, sc = _base(sh, E, k)
    P = circuits(E)
    recs = [r for r in MEP.plan({}, E)]
    allc = _assign(P["circuits"], "light", [r["lights"] for r in recs])
    boxes = D.stair_boxes(E, k)
    letter = 0
    homes = set()
    for rec, nums in zip(recs, allc):
        if rec["floor"] != k:
            continue
        rm = rec["room"]
        inner = B.room_inner(E, rm, k)
        ix0, iy0, ix1, iy1 = inner
        n = rec["lights"]
        cols = max(1, int(round(math.sqrt(n * (ix1 - ix0) / max(iy1 - iy0, 0.1)))))
        rows = max(1, int(math.ceil(n / cols)))
        pts = []
        for j in range(rows):
            row = [(ix0 + (ix1 - ix0) * (i + 0.5) / cols, iy0 + (iy1 - iy0) * (j + 0.5) / rows) for i in range(cols)]
            pts += row if j % 2 == 0 else row[::-1]                 # a snake, for one tidy run
        pts = pts[:n]
        lt = "abcdefghijklmnopqrstuvwxyz"[letter % 26]
        letter += 1
        sw = _switch_spot(E, k, rm, inner)
        _room_label(sh, v, E, k, rm, _free_spot(rm, pts + [sw], boxes))
        q = v(*sw)
        _sym("sw1")(sh, *q)
        sh.text((q[0] + 1.6, q[1] + 1.2), lt, 2.3, "left", "elec", True)
        prev = q
        for p, c in zip(pts, nums):
            pp = v(*p)
            _ortho(sh, prev, pp)
            prev = pp
        for p, c in zip(pts, nums):
            pp = v(*p)
            _sym("down")(sh, *pp)
            sh.text((pp[0] + 1.8, pp[1] - 3.4), lt, 2.1, "left", "elec", True)
            if c not in homes:                                        # the circuit's home run, once
                homes.add(c)
                _home(sh, pp, f"{c}/LP")
    if k == 0:
        lp = _lp_spot(E)
        _sym("lp")(sh, *v(*lp))
    _side_notes(sh, x1 - 66, y1 - 10, [
        "1. ตัวอักษร a, b, c … ที่ดวงโคม คือสวิตช์ที่ควบคุมดวงโคมนั้น",
        "2. n/LP คือสายวงจรย่อยที่ n กลับแผงเมนสวิตช์ LP (ดูรายละเอียดแผงเมนสวิตช์)",
        "3. สายวงจรแสงสว่าง 2-2.5/G2.5 IEC 01 ในท่อ uPVC Ø15 มม. เดินเหนือฝ้า",
        "4. สวิตช์สูงจากพื้น 1.20 ม. ดวงโคมตามสัญลักษณ์งานระบบไฟฟ้า"])
    STD.caption_marks(sh, ((x0 + x1 - 70) / 2 - 50, y0 + 12), f"แปลนไฟฟ้าแสงสว่าง ชั้น {k + 1}", f"1:{sc}",
                      None, None, 100.0)


def _lp_spot(E):
    """The panel: on the inner face of the front wall of the first room,
    near its left end."""
    from core import wanic_building as B
    sl = next((s for s in E["slabs"] if s["floor"] == 0), None)
    if sl is None:
        return (0.3, 0.3)
    x0, y0, x1, y1 = B.room_inner(E, sl["room"], 0)
    return (x0 + 0.45, y0 + 0.12)


def _socket_spots(E, k, rm, inner, n):
    """``n`` socket places along the room's walls, clear of its doors and
    windows: the middles of the longest free stretches first."""
    from core import wanic_building as B
    x0, y0, x1, y1 = inner
    ops = [op for op in E["openings"] if op["floor"] == k and
           B._on_edge(rm, float(op["op"]["x"]), float(op["op"]["y"]), tol=0.06)]
    walls = [("S", (x0, y0), (x1, y0)), ("E", (x1, y0), (x1, y1)), ("N", (x1, y1), (x0, y1)), ("W", (x0, y1), (x0, y0))]
    free = []
    for name, a, b in walls:
        horiz = name in ("S", "N")
        lo, hi = (min(a[0], b[0]), max(a[0], b[0])) if horiz else (min(a[1], b[1]), max(a[1], b[1]))
        cuts = []
        for op in ops:
            e, _n = _edge_of(rm, float(op["op"]["x"]), float(op["op"]["y"]))
            if e != name:
                continue
            c = float(op["op"]["x"] if horiz else op["op"]["y"])
            w = float(op["op"].get("w") or 0.9)
            cuts.append((c - w / 2 - 0.15, c + w / 2 + 0.15))
        s0 = lo + 0.25
        for c0, c1 in sorted(cuts) + [(hi - 0.25, hi)]:
            if c0 - s0 > 0.3:
                free.append((c0 - s0, name, (s0 + c0) / 2))
            s0 = max(s0, c1)
    free.sort(reverse=True)
    out = []
    for L, name, m in free[:n]:
        if name == "S":
            out.append((m, y0 + 0.10))
        elif name == "N":
            out.append((m, y1 - 0.10))
        elif name == "E":
            out.append((x1 - 0.10, m))
        else:
            out.append((x0 + 0.10, m))
    return out


def ee_power_plan(sh, E, k):
    """แปลนเต้ารับไฟฟ้า ชั้น k+1 (the standard's EE-05, EE-06): the sockets on
    the walls (their height where it is not 0.30 m), the water heaters'
    boxes, the air-conditioners' points, the wiring and the home runs
    «n/LP» of every circuit; the panel."""
    from core import wanic_building as B
    from core import wanic_mep as MEP
    from core import wanic_std_sheets as STD
    x0, y0, x1, y1 = D.drawing_area()
    v, sc = _base(sh, E, k)
    P = circuits(E)
    cs = P["circuits"]
    recs = [r for r in MEP.plan({}, E)]
    allc = _assign(cs, "socket", [r["outlets"] for r in recs])
    heaters = iter([c for c in cs if c["kind"] == "heater"])
    acs = iter([c for c in cs if c["kind"] == "ac"])
    boxes = D.stair_boxes(E, k)
    homes = set()
    for rec, nums in zip(recs, allc):
        heater = next(heaters) if rec["heater"] else None
        acc = next(acs) if rec["ac"] else None
        if rec["floor"] != k:
            continue
        rm = rec["room"]
        inner = B.room_inner(E, rm, k)
        wet = rec["kind"] == "wet" or "ครัว" in (rm.get("name") or "")
        spots = _socket_spots(E, k, rm, inner, rec["outlets"])
        taken = list(spots)
        from core import wanic_std_sn as SNS                    # the wiring along the walls, round the room
        ix0, iy0, ix1, iy1 = inner
        ring = (ix0 + 0.10, iy0 + 0.10, ix1 - 0.10, iy1 - 0.10)
        on = [SNS._snap(ring, p) for p in spots]

        def _t(q):
            x, y = q
            W_, H_ = ring[2] - ring[0], ring[3] - ring[1]
            if abs(y - ring[1]) < 1e-6:
                return x - ring[0]
            if abs(x - ring[2]) < 1e-6:
                return W_ + y - ring[1]
            if abs(y - ring[3]) < 1e-6:
                return W_ + H_ + ring[2] - x
            return 2 * W_ + H_ + ring[3] - y
        order = sorted(range(len(on)), key=lambda i: _t(on[i]))
        for a_, b_ in zip(order, order[1:]):
            path = SNS._perim(ring, on[a_], on[b_])
            sh.poly([v(*q) for q in path], "elec", 0.3, closed=False)
        spots = [on[i] for i in order]
        nums = [nums[i] for i in order] if len(nums) == len(order) else nums
        for i, (p, c) in enumerate(zip(spots, nums)):
            pp = v(*p)
            _sym("sockwp" if wet else "sock")(sh, *pp)
            if wet:                                                  # the height, toward the room
                cxr = (inner[0] + inner[2]) / 2
                left = p[0] > cxr
                sh.text((pp[0] + (-3.0 if left else 3.0), pp[1] - 3.6), "+1.20M", 2.1,
                        "right" if left else "left", "elec", True)
            if c not in homes:
                homes.add(c)
                _home(sh, pp, f"{c}/LP")
        if heater is not None:
            ix0, iy0, ix1, iy1 = inner
            sh_fx = next((f["fx"] for f in E["fixtures"] if f["floor"] == k and f["fx"].get("type") == "SH" and
                          D._inside(f["fx"], rm)), None)
            hp = (float(sh_fx["x"]), float(sh_fx["y"])) if sh_fx else (ix1 - 0.15, (iy0 + iy1) / 2)
            taken.append(hp)
            hq = v(*hp)
            _sym("wh")(sh, *hq)
            _home(sh, hq, f"{heater['no']}/LP")
        if acc is not None and rec.get("ac_wall"):
            wl = rec["ac_wall"]
            mx, my = (wl["p0"][0] + wl["p1"][0]) / 2, (wl["p0"][1] + wl["p1"][1]) / 2
            ix0, iy0, ix1, iy1 = inner
            cx, cy = (ix0 + ix1) / 2, (iy0 + iy1) / 2
            dx, dy = cx - mx, cy - my                                 # into the room
            L = math.hypot(dx, dy) or 1.0
            if abs(dx) > abs(dy):
                mx, my = (ix0 + 0.35 if dx > 0 else ix1 - 0.35), min(max(my, iy0 + 0.6), iy1 - 0.6)
            else:
                mx, my = min(max(mx, ix0 + 0.6), ix1 - 0.6), (iy0 + 0.2 if dy > 0 else iy1 - 0.2)
            taken.append((mx, my))
            aq = v(mx, my)
            _sym("ac")(sh, *aq)
            ty = aq[1] + (4.2 if dy > 0 and abs(dy) >= abs(dx) else -4.6)
            D.masked_text(sh, (aq[0], ty), f"{acc['no']}/LP  {acc['load']}", 2.1, "center", True)
        _room_label(sh, v, E, k, rm, _free_spot(rm, taken, boxes))
    if k == 0:
        _sym("lp")(sh, *v(*_lp_spot(E)))
    _side_notes(sh, x1 - 66, y1 - 10, [
        "1. เต้ารับสูงจากพื้น 0.30 ม. เว้นแต่ระบุ (+1.20M = สูง 1.20 ม. ห้องน้ำ ครัว ชนิดมีฝาปิดกันน้ำ)",
        "2. n/LP คือสายวงจรย่อยที่ n กลับแผงเมนสวิตช์ LP",
        "3. สายวงจรเต้ารับ 2-2.5/G2.5 IEC 01 ในท่อ uPVC Ø15 มม. เดินในผนังและเหนือฝ้า",
        "4. เครื่องทำน้ำอุ่นและเครื่องปรับอากาศใช้วงจรเฉพาะ ขนาดสายตามแผงเมนสวิตช์",
        "5. วงจรเต้ารับ ห้องน้ำ และเครื่องทำน้ำอุ่น มีเครื่องตัดไฟรั่ว (RCBO) 30 mA"])
    STD.caption_marks(sh, ((x0 + x1 - 70) / 2 - 50, y0 + 12), f"แปลนเต้ารับไฟฟ้า ชั้น {k + 1}", f"1:{sc}",
                      None, None, 100.0)


# -- the riser diagram and the load schedule (owner, 27 Nov — studied from family10 p. 65) ------

def floor_loads(E) -> list:
    """Per floor: {"floor", "lights", "outlets", "ac": [BTU], "heater": [W]} from the same room
    plan as ``circuits`` (one source)."""
    from core import wanic_mep as MEP
    out = [{"floor": k, "lights": 0, "outlets": 0, "ac": [], "heater": []} for k in range(E["n"])]
    for r in MEP.plan({}, E):
        f = out[min(max(int(r["floor"]), 0), E["n"] - 1)]
        f["lights"] += r["lights"]
        f["outlets"] += r["outlets"]
        if r["ac"]:
            f["ac"].append(int(r["ac"]))
        if r["heater"]:
            f["heater"].append(int(r.get("heater_w") or MEP.HEATER_W))
    return out


def ee_riser_std(sh, E):
    """«ไดอะแกรมไฟฟ้าแนวดิ่งและตารางโหลด»: left, the riser — the utility pole, the service drop,
    the kWh meter, the main cable into LP on the ground floor, the earth rod, and the risers up to
    each floor with what each feeds; right, the load schedule of LP circuit by circuit (the same
    circuits as «รายละเอียดแผงเมนสวิตช์»), the total, the demand, the current and the main."""
    x0, y0, x1, y1 = D.drawing_area()
    P = circuits(E)
    FL = floor_loads(E)
    n = E["n"]
    # -- the riser ------------------------------------------------------------------------------
    gx0, gx1 = x0 + 30, x0 + 110                     # the building, in elevation
    gy = y0 + 70                                     # the ground
    fh = min(42.0, (y1 - 40 - gy) / (n + 0.6))
    sh.line((x0 + 6, gy), (x0 + 166, gy), "cut", 0.5)
    for i in range(0, 160, 4):
        sh.line((x0 + 6 + i, gy), (x0 + 4 + i, gy - 2), "cut", 0.13)
    sh.rect(gx0, gy, gx1, gy + fh * n + 6, "wall", 0.35)
    for k in range(n + 1):
        y_ = gy + fh * k
        sh.line((gx0, y_), (gx1, y_), "wall", 0.25)
        lab = f"พื้นชั้น {k + 1}" if k < n else "ใต้หลังคา"
        sh.text((gx0 - 2, y_ + 1.0), lab, 2.2, "right")
    # the pole, the drop and the meter
    px = x0 + 158
    sh.rect(px - 1.2, gy, px + 1.2, gy + fh * n + 18, "elec", 0.35)
    sh.line((px - 6, gy + fh * n + 14), (px + 6, gy + fh * n + 14), "elec", 0.4)
    sh.text((px, gy + fh * n + 21), "เสาไฟฟ้า กฟภ./กฟน.", 2.4, "center", "text", True)
    ym = gy + min(fh * 0.55, 22)                    # the meter on the outside wall
    mx = gx1 + 10
    sh.line((px, gy + fh * n + 12), (mx, ym + 8), "elec", 0.35)
    sh.text((mx + 6, ym - 7.0), "สายเข้าจากการไฟฟ้า", 2.0)
    sh.rect(mx - 4, ym, mx + 4, ym + 8, "elec", 0.4)
    sh.text((mx, ym + 3.0), "kWh", 2.2, "center", "elec", True)
    sh.text((mx + 6, ym + 1.0), f"มิเตอร์ {P['meter']}", 2.2)
    sh.text((mx + 6, ym - 3.0), "1 เฟส 2 สาย", 2.0)
    # the main into LP
    lx = gx1 - 22
    ly = gy + fh * 0.30
    sh.line((mx - 4, ym + 4), (lx + 6, ym + 4), "elec", 0.45)
    sh.line((lx + 6, ym + 4), (lx + 6, ly + 10), "elec", 0.45)
    sh.text((lx + 8, ym + 5.4), f"2-{P['main_wire']} ตร.มม.", 1.9)
    sh.rect(lx, ly, lx + 12, ly + 10, "elec", 0.45)
    sh.text((lx + 6, ly + 3.4), "LP", 2.8, "center", "elec", True)
    sh.text((lx + 6, ly - 3.2), f"เมน {P['main']}", 2.0, "center")
    # the earth rod
    sh.line((lx + 2, ly), (lx + 2, gy - 14), "elec", 0.35)
    for i, w in enumerate((6, 4, 2)):
        sh.line((lx + 2 - w / 2, gy - 14 - i * 1.4), (lx + 2 + w / 2, gy - 14 - i * 1.4), "elec", 0.35)
    sh.text((lx + 6, gy - 12), f"สายดิน 1-{P['earth']} ตร.มม. → หลักดิน Ø14.2 มม. ยาว 2.40 ม.", 2.0)
    # the risers: one line up the building, a box at each floor with what it feeds
    rx = lx - 10
    sh.line((lx, ly + 5), (rx, ly + 5), "elec", 0.45)
    top = gy + fh * (n - 1) + fh * 0.55
    sh.line((rx, ly + 5), (rx, top), "elec", 0.45)
    for k, f in enumerate(FL):
        y_ = gy + fh * k + fh * 0.55
        sh.rect(rx - 2, y_ - 2, rx + 2, y_ + 2, "elec", 0.35)
        sh.line((rx - 2, y_), (gx0 + 6, y_), "elec", 0.25)
        lines = [f"แสงสว่าง {f['lights']} จุด · เต้ารับ {f['outlets']} จุด"]
        if f["ac"]:
            lines.append(f"เครื่องปรับอากาศ {len(f['ac'])} เครื่อง ({', '.join(f'{b:,}' for b in f['ac'])} BTU)")
        if f["heater"]:
            lines.append(f"เครื่องทำน้ำอุ่น {len(f['heater'])} เครื่อง ({', '.join(f'{w:,}' for w in f['heater'])} W)")
        for i, t in enumerate(lines):                # over the feed line, not through it
            sh.text((gx0 + 6, y_ + 1.4 + (len(lines) - 1 - i) * 3.6), t, 2.1)
    sh.text((rx + 3, top - 1.0), "ท่อร้อยสายแนวดิ่ง", 1.9)
    from core import wanic_std_sheets as STD
    STD.caption_marks(sh, (x0 + 30, y0 + 30), "ไดอะแกรมไฟฟ้าแนวดิ่ง", "ไม่ตามมาตราส่วน", None, None, 100.0)
    # -- the load schedule ---------------------------------------------------------------------
    tx = x1 - 150
    sh.text((tx, y1 - 6), "ตารางโหลดแผงย่อย LP (1 เฟส 2 สาย 220 V)", 3.4, "left", "text", True)
    rows = []
    for c in P["circuits"]:
        what = c["name"] + (f" {c['room']}" if c.get("room") else "")
        rows.append((str(c["no"]), what[:24], c["load"], f"{c['va']:,}",
                     ("RCBO " if c["rcbo"] else "") + c["breaker"], f"2-{c['wire']:g}/G{c['wire']:g}",
                     f"Ø{c['conduit']}"))
    spare = max(2, (4 - len(P["circuits"]) % 4) % 4 + 2)
    for i in range(spare):
        rows.append((str(len(P["circuits"]) + i + 1), "ว่าง (สำรอง)", "-", "-", "16AT,1P", "-", "-"))
    cols = [("วงจร", 10, "center"), ("รายการ", 40, "left"), ("โหลด", 20, "center"), ("VA", 14, "right"),
            ("เบรกเกอร์", 25, "center"), ("สาย ตร.มม.", 22, "center"), ("ท่อ มม.", 13, "center")]
    rh = max(4.4, min(6.0, (y1 - 70 - y0) / (len(rows) + 6)))
    yy = D.table(sh, tx, y1 - 10, cols, rows, 2.0, rh, 6.5)
    W = sum(c[1] for c in cols)
    yy = D.table(sh, tx, yy, [("", 70, "right"), ("", 25, "right"), ("", W - 95, "left")],
                 [("รวมโหลดติดตั้ง (Connected load)", f"{P['va']:,}", "VA"),
                  ("ค่าดีมานด์แฟกเตอร์", "0.8", ""),
                  ("กระแสโหลด", f"{P['amp']:.1f}", "A"),
                  ("เมนเบรกเกอร์ / สายเมน", P["main"], f"2-{P['main_wire']} ตร.มม."),
                  ("ขนาดมิเตอร์", P["meter"], "1 เฟส 2 สาย")], 2.1, rh, 0)
    notes = ["1. วงจรเต้ารับ เครื่องทำน้ำอุ่น ใช้ RCBO Idn 30 mA ตามมาตรฐานการติดตั้งทางไฟฟ้า วสท.",
             "2. สายไฟเป็นสาย IEC 01 เดินในท่อ uPVC ภายในอาคาร ภายนอกอาคารเดินในท่อโลหะ",
             "3. ขนาดมิเตอร์และสายเมนให้ยื่นขอกับการไฟฟ้าตามโหลดรวมนี้",
             "4. ตารางนี้ตรงกับแผ่น «รายละเอียดแผงเมนสวิตช์» ทุกวงจร"]
    for i, t in enumerate(notes):
        sh.text((tx, yy - 6 - i * 4.6), t, 2.1)
