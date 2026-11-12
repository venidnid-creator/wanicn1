# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
"""แบบงานเหล็กรูปพรรณ — added to the S set when the building has designed
steel (data["steel"], data["truss"] or data["purlin"]):

- มาตรฐานสัญลักษณ์งานเชื่อม: the AWS A2.4 weld symbols used on the sheets
  (fillet, groove / butt, all round, field weld, the arrow and the other
  side), with the minimum fillet sizes of AWS D1.1 by the thicker part;
- รอยต่อเหล็กรูปพรรณ: a typical column–beam and beam–beam shear connection
  (double clip angles welded all round), its table for every WF beam the
  steel design chose (angle, length, weld size), the base plates of the
  designed columns (plate, anchor bolts, grout), the Truss heel with its weld
  lengths, the tie-rod turnbuckle, and the notes of the steel work.

Sizes follow from the designed sections: the clip-angle length about 0.6 of
the beam depth (bolts/welds in the web), the leg 50/65/75 mm by the depth,
the fillet weld the AWS minimum for the thicker plate, never less than
the beam web needs (0.707·w·Fv over two lines ≥ the web's shear 0.4 Fy·tw)."""
from __future__ import annotations

import math

from core import wanic_drawings as D

FY = 2450.0
FV_WELD = 0.30 * 4900.0            # E70 fillet: 0.30 Fu (ksc)


def min_fillet(t_mm: float) -> int:
    """AWS D1.1 Table 5.8: the minimum fillet leg (mm) by the thicker part."""
    return 3 if t_mm <= 6 else 5 if t_mm <= 13 else 6 if t_mm <= 19 else 8


def clip_angle(d_mm: float) -> str:
    return "L 50×50×6" if d_mm <= 300 else "L 65×65×6" if d_mm <= 450 else "L 75×75×6"


def connection_rows(data) -> list:
    """One row per WF section the steel design chose for the beams:
    (section, depth mm, angle, angle length mm, weld mm, web shear kg, weld capacity kg)."""
    if not (data or {}).get("steel"):
        return []
    from core import wanic_steel as S
    res = S.design_building(data)
    rows, seen = [], set()
    for r in res["beams"]:
        s = r["check"].sec
        if s.label in seen:
            continue
        seen.add(s.label)
        d_mm, tw_mm = s.d * 10, s.tw * 10
        L_ang = max(60.0, math.floor(0.6 * (d_mm - 2 * s.tf * 10) / 10) * 10)
        w = max(min_fillet(max(tw_mm, 6.0)), 4)
        Vw = 0.40 * FY * s.d * s.tw                                # the web's shear capacity, kg
        cap = 2 * 2 * 0.707 * w / 10 * L_ang / 10 * FV_WELD         # two angles, two lines each
        while cap < Vw and w < 12:
            w += 1
            cap = 2 * 2 * 0.707 * w / 10 * L_ang / 10 * FV_WELD
        rows.append((s.label, d_mm, clip_angle(d_mm), L_ang, w, Vw, cap))
    return rows


def plate_rows(data) -> list:
    if not (data or {}).get("steel"):
        return []
    from core import wanic_steel as S
    res = S.design_building(data)
    out = {}
    for c in res["columns"]:
        p = c.get("plate")
        if p:
            key = (c["check"].sec.label, p["N"], p["B"], p["t"], p["bolts"])
            out[key] = out.get(key, 0) + 1
    return [k + (n,) for k, n in sorted(out.items())]


# ---- drawing helpers -----------------------------------------------------------------

def weld_symbol(sh, p, size, kind="fillet", both=False, field=False, around=False, length=None):
    """An AWS weld symbol whose arrow points at ``p`` (paper mm): the leader up
    and right to a reference line with the symbol under it (arrow side)."""
    x, y = p
    sh.line((x, y), (x + 6, y + 6), "dim", 0.18)
    sh.line((x, y), (x + 1.6, y + 0.4), "dim", 0.18)
    sh.line((x, y), (x + 0.4, y + 1.6), "dim", 0.18)
    rx, ry = x + 6, y + 6
    sh.line((rx, ry), (rx + 16, ry), "dim", 0.18)
    sx = rx + 6
    if kind == "fillet":
        sh.poly([(sx, ry), (sx, ry - 2.4), (sx + 2.4, ry)], "dim", 0.18)
        if both:
            sh.poly([(sx, ry), (sx, ry + 2.4), (sx + 2.4, ry)], "dim", 0.18)
    else:                                                     # single V groove
        sh.poly([(sx - 1.4, ry - 2.4), (sx, ry), (sx + 1.4, ry - 2.4)], "dim", 0.18, closed=False)
    sh.text((sx - 1.0, ry - 2.2), f"{size}", 1.7, "right", "dim")
    if length:
        sh.text((sx + 3.2, ry - 2.2), f"{length}", 1.6, "left", "dim")
    if around:
        sh.circle((rx, ry), 1.0, "dim", 0.18)
    if field:
        sh.line((rx, ry), (rx, ry + 3.5), "dim", 0.18)
        sh.fill([(rx, ry + 3.5), (rx + 2.4, ry + 2.8), (rx, ry + 2.1)], "dim", 0.0)


def _wf_elev(sh, x, y, d, bf, tf, k, upright=True, length=40.0):
    """A WF in elevation: an upright column (flanges vertical) or a beam."""
    if upright:
        sh.rect(x, y, x + d * k, y + length, "struct", 0.4)
        sh.line((x + tf * k, y), (x + tf * k, y + length), "struct", 0.25)
        sh.line((x + (d - tf) * k, y), (x + (d - tf) * k, y + length), "struct", 0.25)
    else:
        sh.rect(x, y, x + length, y + d * k, "struct", 0.4)
        sh.line((x, y + tf * k), (x + length, y + tf * k), "struct", 0.25)
        sh.line((x, y + (d - tf) * k), (x + length, y + (d - tf) * k), "struct", 0.25)


# ---- the sheets ----------------------------------------------------------------------

WELD_SYMBOLS = [
    ("fillet", False, False, False, "รอยเชื่อมพอก (Fillet) ด้านลูกศร · ตัวเลข = ขนาดขาเชื่อม (มม.)"),
    ("fillet", True, False, False, "รอยเชื่อมพอกสองด้าน (ด้านลูกศรและด้านตรงข้าม)"),
    ("groove", False, False, False, "รอยเชื่อมชนบากร่องตัววี (Single-V Groove) เชื่อมเต็มหน้าตัด"),
    ("fillet", False, False, True, "วงกลมที่มุม = เชื่อมรอบ (All Around)"),
    ("fillet", False, True, False, "ธงที่มุม = เชื่อมที่หน้างาน (Field Weld)"),
]


def s_weld_standard(sh, E):
    x0, y0, x1, y1 = D.drawing_area()
    y = y1 - 10
    sh.text((x0 + 6, y), "มาตรฐานสัญลักษณ์งานเชื่อม (AWS A2.4)", 3.6, "left", "text", True)
    y -= 14
    for kind, both, field, around, text in WELD_SYMBOLS:
        weld_symbol(sh, (x0 + 14, y), 6, kind, both, field, around)
        sh.text((x0 + 50, y + 5), text, 2.4)
        y -= 18
    y -= 4
    sh.text((x0 + 6, y), "ขนาดรอยเชื่อมพอกต่ำสุด (AWS D1.1) ตามความหนาชิ้นที่หนากว่า", 3.0, "left", "text", True)
    rows = [("ความหนาชิ้นงาน (มม.)", "ขนาดขาเชื่อมต่ำสุด (มม.)"), ("ไม่เกิน 6", "3"), ("6 – 13", "5"),
            ("13 – 19", "6"), ("เกิน 19", "8")]
    yy = y - 4
    for i, (a, b) in enumerate(rows):
        sh.rect(x0 + 10, yy - 7, x0 + 70, yy, "text", 0.25)
        sh.rect(x0 + 70, yy - 7, x0 + 120, yy, "text", 0.25)
        sh.text((x0 + 40, yy - 5), a, 2.2, "center", "text", i == 0)
        sh.text((x0 + 95, yy - 5), b, 2.2, "center", "text", i == 0)
        yy -= 7
    notes = ["ลวดเชื่อมไฟฟ้า E70XX (E7016 / E7018) ตาม AWS A5.1 · กำลังรับแรงเฉือนของรอยเชื่อม 0.30 Fu",
             "ผิวงานต้องสะอาด ปราศจากสนิม สี น้ำมัน ก่อนเชื่อม · เคาะสแลกออกทุกชั้น",
             "รอยเชื่อมชนเต็มหน้าตัดให้บากร่องตามความหนา และเชื่อมกลับด้านหลังเมื่อระบุ",
             "ตรวจรอยเชื่อมด้วยสายตาทุกจุด รอยเชื่อมรับแรงหลักตรวจด้วยน้ำยาแทรกซึม (PT) ตามที่ผู้ควบคุมงานกำหนด"]
    D.notes_block(sh, x0 + 160, y1 - 10, "ข้อกำหนดงานเชื่อม", notes, 2.4, 70)
    D.caption(sh, ((x0 + x1) / 2, y0 + 6), "มาตรฐานงานเชื่อม", "ไม่ระบุมาตราส่วน")


def s_steel_connections(sh, E, data):
    x0, y0, x1, y1 = D.drawing_area()
    rows = connection_rows(data)
    k = 1000.0 / 10                                      # 1:10
    # ---- typical column–beam connection (elevation, 1:20)
    kk = 1000.0 / 20
    sh.text((x0 + 6, y1 - 8), "รอยต่อเสา-คานเหล็กทั่วไป (ต่อแบบรับแรงเฉือน)", 3.2, "left", "text", True)
    cx, cy = x0 + 24, y1 - 88
    _wf_elev(sh, cx, cy, 0.15, 0.15, 0.010, kk, True, 72)              # H column, flanges vertical
    face = cx + 0.15 * kk
    by = cy + 30
    gap = 1.0
    _wf_elev(sh, face + gap, by, 0.30, 0.15, 0.009, kk, False, 62)      # WF beam
    sh.rect(face, by + 3, face + 6, by + 0.30 * kk - 3, "rebar", 0.35)   # clip angle on the web
    sh.text((face + 7, by + 0.30 * kk / 2 - 0.8), "ฉากยึด", 1.8, "left", "rebar")
    weld_symbol(sh, (face + 6, by + 5), "w", "fillet", False, False, True)
    weld_symbol(sh, (face, by + 0.30 * kk - 5), "w", "fillet", False, True, False)
    sh.text((cx + 0.15 * kk / 2, cy - 4), "เสาเหล็ก H", 1.9, "center")
    sh.text((face + 40, by - 4), "คาน WF (ฉากยึด 2 ตัว ซ้าย-ขวาเอวคาน)", 1.9, "center")
    # ---- typical beam–beam (elevation, 1:20)
    sh.text((x0 + 108, y1 - 8), "รอยต่อคาน-คานเหล็กทั่วไป", 3.2, "left", "text", True)
    gx, gy = x0 + 112, y1 - 70
    sh.rect(gx, gy, gx + 0.20 * kk, gy + 0.40 * kk, "struct", 0.4)       # the girder cut (I shape)
    sh.line((gx + 0.10 * kk, gy + 0.013 * kk), (gx + 0.10 * kk, gy + (0.40 - 0.013) * kk), "struct", 0.4)
    sh.line((gx, gy + 0.013 * kk), (gx + 0.20 * kk, gy + 0.013 * kk), "struct", 0.25)
    sh.line((gx, gy + (0.40 - 0.013) * kk), (gx + 0.20 * kk, gy + (0.40 - 0.013) * kk), "struct", 0.25)
    bx2 = gx + 0.10 * kk + 0.6
    top2 = gy + (0.40 - 0.013) * kk - 0.5
    sh.poly([(bx2 + 0.10 * kk, top2), (bx2 + 62, top2), (bx2 + 62, top2 - 0.30 * kk), (bx2, top2 - 0.30 * kk),
             (bx2, top2 - 0.04 * kk), (bx2 + 0.10 * kk, top2 - 0.04 * kk)], "struct", 0.4)
    sh.rect(bx2, top2 - 0.27 * kk, bx2 + 6, top2 - 0.07 * kk, "rebar", 0.35)
    weld_symbol(sh, (bx2 + 6, top2 - 0.20 * kk), "w", "fillet", False, False, True)
    sh.text((gx + 0.10 * kk, gy - 4), "คานหลัก (ตัด)", 1.9, "center")
    sh.text((bx2 + 34, top2 - 0.30 * kk - 4), "คานซอย WF บากปีกบนให้พ้นปีกคานหลัก", 1.9, "center")
    # ---- the table from the design
    ty = y1 - 100
    cols = [("หน้าตัดคาน", 34, "c"), ("ลึก (มม.)", 18, "c"), ("ฉากยึด 2 ตัว", 28, "c"), ("ยาว (มม.)", 18, "c"),
            ("ขาเชื่อม w (มม.)", 24, "c"), ("เฉือนเอว (กก.)", 24, "c"), ("รอยเชื่อมรับ (กก.)", 26, "c")]
    xx = x0 + 6
    for head, w, _a in cols:
        sh.rect(xx, ty - 7, xx + w, ty, "text", 0.3)
        sh.text((xx + w / 2, ty - 5), head, 1.9, "center", "text", True)
        xx += w
    yy = ty - 7
    if not rows:
        sh.text((x0 + 8, yy - 5), "ยังไม่ได้ออกแบบเหล็กรูปพรรณ (เสา H / คาน WF) — ขนาดตามแบบ", 2.0)
    for r in rows:
        vals = (r[0], f"{r[1]:.0f}", r[2], f"{r[3]:.0f}", f"{r[4]}", f"{r[5]:,.0f}", f"{r[6]:,.0f}")
        xx = x0 + 6
        for (head, w, _a), v in zip(cols, vals):
            sh.rect(xx, yy - 6, xx + w, yy, "text", 0.2)
            sh.text((xx + w / 2, yy - 4.4), v, 1.9, "center")
            xx += w
        yy -= 6
    # ---- base plates
    py = yy - 14
    plates = plate_rows(data)
    sh.text((x0 + 6, py), "แผ่นเหล็กรองใต้เสา (Base Plate)", 3.2, "left", "text", True)
    py -= 6
    for i, (sec, N, B_, t, bolts, n) in enumerate(plates[:3]):
        ox = x0 + 10 + i * 58
        kk = 1.6                                           # mm per cm (1:6)
        sh.rect(ox, py - N * kk, ox + B_ * kk, py, "struct", 0.4)
        sh.rect(ox + B_ * kk / 2 - 6, py - N * kk / 2 - 6, ox + B_ * kk / 2 + 6, py - N * kk / 2 + 6, "struct", 0.25)
        for dx in (0.18, 0.82):
            for dy in (0.18, 0.82):
                sh.circle((ox + B_ * kk * dx, py - N * kk * dy), 1.0, "rebar", 0.25)
        sh.text((ox + B_ * kk / 2, py + 1.2), f"PL {B_:g}×{N:g} ซม. หนา {t:.0f} มม.", 1.8, "center", "struct", True)
        sh.text((ox + B_ * kk / 2, py - N * kk - 3.2), f"{sec} · {n} ต้น", 1.7, "center")
        sh.text((ox + B_ * kk / 2, py - N * kk - 6.4), bolts, 1.6, "center", "rebar")
    if not plates:
        sh.text((x0 + 8, py - 5), "ขนาดแผ่นเหล็กตามรายการคำนวณเหล็กรูปพรรณ", 2.0)
    sh.text((x0 + 8, py - 60), "ปรับระดับใต้แผ่นด้วยปูนนอนชริงค์เกราท์ หนา 25 มม. · เชื่อมเสากับแผ่นรอบ "
            "ขนาดตามตาราง", 1.8)
    # ---- truss heel and turnbuckle (right column)
    rx = x0 + 200
    ry = y1 - 8
    if (data or {}).get("truss"):
        from core import wanic_truss as T
        try:
            p, des = T.design_of(data)
            sh.text((rx, ry), "ส้นโครง Truss (จุดรองรับ)", 3.2, "left", "text", True)
            ry -= 8
            sh.text((rx, ry), f"แบบ {T.TYPES.get(p['kind'], p['kind'])} · ช่วง {p['span']:.2f} ม.", 2.2)
            ry -= 5
            for no, g, N, L in des.plate.get("weld") or []:
                sh.text((rx + 2, ry), f"ชิ้น {no} ({g}) แรง {N:+,.0f} กก. → เชื่อมพอก 6 มม. ยาวรวม ≥ {L:.0f} ซม.", 1.9)
                ry -= 4.5
            pl = des.plate
            sh.text((rx + 2, ry), f"แผ่นรองส้นโครง PL {pl['side']:.0f}×{pl['side']:.0f} ซม. หนา {pl['t']:.0f} มม. · "
                    f"{pl['bolts']}", 1.9)
            ry -= 10
        except ValueError:
            pass
    if (data or {}).get("purlin") is not None and "purlin" in (data or {}):
        from core import wanic_purlin as PU
        _p, res = PU.design_of(data)
        sh.text((rx, ry), "เกลียวเร่ง (Turnbuckle) ค้ำยันทแยงหลังคา", 3.2, "left", "text", True)
        ty_ = ry - 34
        sh.line((rx + 4, ty_), (rx + 30, ty_ + 14), "rebar", 0.45)
        sh.rect(rx + 30, ty_ + 11, rx + 44, ty_ + 17, "struct", 0.35)
        sh.line((rx + 44, ty_ + 14), (rx + 70, ty_ + 28), "rebar", 0.45)
        sh.text((rx + 46, ty_ + 9), f"เหล็กเส้น {res['tie']} ทำเกลียวสองปลาย + เกลียวเร่ง", 1.8)
        sh.text((rx + 4, ty_ - 4), f"Sag Rod {res['rod'] or '-'} · ขันตึงหลังติดตั้งแปครบ", 1.8)
        ry = ty_ - 12
    notes = ["เหล็กรูปพรรณรีดร้อน SS400 (มอก. 1227) / ASTM A36 · เหล็กแผ่น SS400 · เหล็กรีดเย็น มอก. 1228",
             "สลักเกลียวยึด (Anchor Bolt) เหล็ก SR24 หรือดีกว่า ทำเกลียว พร้อมแหวนและน็อต 2 ตัว",
             "ลวดเชื่อม E70XX · ขนาดรอยเชื่อมไม่น้อยกว่าที่ระบุและไม่น้อยกว่าขนาดต่ำสุดตามความหนา",
             "ทาสีกันสนิม 1 ครั้ง ทาสีจริง 2 ครั้ง · ซ่อมสีรอยเชื่อมหน้างานทุกจุด",
             "ระยะ ระดับ และขนาดในแบบนี้ให้ตรวจกับรายการคำนวณก่อนตัดเหล็ก"]
    D.notes_block(sh, rx, max(ry - 4, y0 + 70), "ข้อกำหนดงานเหล็กรูปพรรณ", notes, 2.2, 66)
    D.caption(sh, ((x0 + x1) / 2, y0 + 6), "รอยต่อเหล็กรูปพรรณ แผ่นรองเสา ส้นโครง Truss", "ตามระบุ")


def has_steel(data) -> bool:
    d = data or {}
    return bool(d.get("steel") or d.get("truss") or ("purlin" in d))
