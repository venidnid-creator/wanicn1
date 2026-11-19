# -*- coding: utf-8 -*-
"""Roof shapes: geometry for the design, wind, trusses, 3D and quantities.

Shapes:
    hip     ปั้นหยา — four slopes, ridge along the long side
    gable   จั่ว — two slopes, gable ends on the short sides
    shed    เพิงหมาแหงน — one slope across the short side, the low side chosen
    manila  มนิลา (ปั้นหยาผสมจั่ว) — hip at the bottom, a small gable at the top;
            ``manila_ratio`` is the share of the rise taken by the hip part

The regional presets are the roofs commonly built in each region of
Thailand (slope, overhang, covering). They are customary practice, not
rules of the law: the design still checks every value [ROOF-STYLE].
The least slope of each covering is the value commonly published by Thai
roof-tile and sheet makers; use the maker's own manual for the product
[ROOF-MAKER].
"""
from __future__ import annotations

import math
from dataclasses import dataclass

SHAPES = [("hip", "ปั้นหยา"), ("gable", "จั่ว"), ("shed", "เพิงหมาแหงน"), ("manila", "มนิลา (ปั้นหยาผสมจั่ว)")]

#: Least roof slope by covering, degrees (makers' published values; check the product manual).
MIN_SLOPE = {"concrete_tile": 17.0, "ceramic_tile": 25.0, "asbestos": 15.0, "metal_sheet": 5.0}

#: Roofs customary in the four regions: (label, shape, slope, overhang, cover, why).
REGIONS = {
    "central": ("ภาคกลาง — จั่วทรงไทยหลังคาชัน", "gable", 45.0, 1.00, "ceramic_tile",
                "หลังคาชันระบายน้ำฝนเร็ว ระบายความร้อนใต้หลังคา แบบเรือนไทยภาคกลาง"),
    "north": ("ภาคเหนือ — จั่วกาแล ชายคายื่นยาว", "gable", 40.0, 1.50, "ceramic_tile",
              "ชายคายื่นยาวกันแดดฝนและลมหนาว แบบเรือนกาแล (ไม้กาแลเป็นงานประดับ)"),
    "northeast": ("ภาคอีสาน — จั่วลาดปานกลาง", "gable", 35.0, 1.00, "metal_sheet",
                  "จั่วเรียบง่าย ใต้หลังคาโปร่ง แบบเรือนอีสาน มักมุงแผ่นโลหะหรือกระเบื้อง"),
    "south": ("ภาคใต้ — มนิลา/บลานอ (ปั้นหยาผสมจั่ว)", "manila", 30.0, 1.00, "concrete_tile",
              "ปั้นหยาด้านล่างต้านลมมรสุมได้ดี จั่วด้านบนระบายอากาศ แบบเรือนบลานอ"),
}


@dataclass
class RoofGeometry:
    a: float                 # plan size along X with the overhang, m
    c: float                 # along Y
    long: float
    short: float
    run: float               # horizontal run of one slope from eave to the top, m
    rise: float              # height of the roof above the eave, m
    ridge: float             # ridge length, m
    hips: float              # total hip length, m
    verge: float             # verges (ครอบปั้นลม) and, on a shed roof, the high edge, m
    eave: float              # fascia length, m
    along_x: bool            # ridge (or the slope's contour) runs along X

    @property
    def plan_area(self) -> float:
        return self.a * self.c


def geometry(b) -> RoofGeometry:
    r = b.roof
    X, Y = b.plan_size()
    a, c = X + 2 * r.overhang, Y + 2 * r.overhang
    long_, short = max(a, c), min(a, c)
    th = math.radians(r.slope_deg)
    t, cos = math.tan(th), math.cos(th)
    along_x = a >= c
    if r.shape == "shed":
        run = short
        rise = run * t
        return RoofGeometry(a, c, long_, short, run, rise, 0.0, 0.0, 2 * run / cos + long_, long_, along_x)
    run = short / 2
    rise = run * t
    if r.shape == "gable":
        return RoofGeometry(a, c, long_, short, run, rise, long_, 0.0, 4 * run / cos, 2 * long_, along_x)
    if r.shape == "manila":
        f = min(max(r.manila_ratio, 0.1), 0.9)
        h = f * run                                         # plan inset of the hip part
        hips = 4 * math.sqrt(2 * h * h + (f * rise) ** 2)
        return RoofGeometry(a, c, long_, short, run, rise, long_ - 2 * h, hips, 4 * (1 - f) * run / cos,
                            2 * (a + c), along_x)
    hips = 4 * math.sqrt(2 * run * run + rise * rise)
    return RoofGeometry(a, c, long_, short, run, rise, long_ - short, hips, 0.0, 2 * (a + c), along_x)


def faces(b, z: float):
    """Roof planes as 3D polygons (for the viewer)."""
    r = b.roof
    g = geometry(b)
    e = r.overhang
    x0, y0, x1, y1 = -e, -e, b.xs[-1] + e, b.ys[-1] + e
    rise = g.rise
    if not g.along_x:                                       # work along X then swap coordinates back
        def P(u, v, w):
            return (v, u, w)
        x0, y0, x1, y1 = y0, x0, y1, x1
    else:
        def P(u, v, w):
            return (u, v, w)
    ym = (y0 + y1) / 2
    zt = z + rise
    if r.shape == "shed":
        low_front = r.shed_low in ("front", "-")
        ya, yb = (y0, y1) if low_front else (y1, y0)
        return [[P(x0, ya, z), P(x1, ya, z), P(x1, yb, zt), P(x0, yb, zt)],
                [P(x0, yb, z), P(x1, yb, z), P(x1, yb, zt), P(x0, yb, zt)]]        # high wall face
    if r.shape == "gable":
        return [[P(x0, y0, z), P(x1, y0, z), P(x1, ym, zt), P(x0, ym, zt)],
                [P(x0, y1, z), P(x1, y1, z), P(x1, ym, zt), P(x0, ym, zt)]]
    f = 1.0 if r.shape == "hip" else min(max(r.manila_ratio, 0.1), 0.9)
    h = f * (y1 - y0) / 2
    zh = z + f * rise
    xa, xb = x0 + h, x1 - h
    out = [[P(x0, y0, z), P(x1, y0, z), P(xb, y0 + h, zh), P(xb, ym, zt), P(xa, ym, zt), P(xa, y0 + h, zh)],
           [P(x0, y1, z), P(x1, y1, z), P(xb, y1 - h, zh), P(xb, ym, zt), P(xa, ym, zt), P(xa, y1 - h, zh)],
           [P(x0, y0, z), P(x0, y1, z), P(xa, y1 - h, zh), P(xa, y0 + h, zh)],
           [P(x1, y0, z), P(x1, y1, z), P(xb, y1 - h, zh), P(xb, y0 + h, zh)]]
    if r.shape == "manila":                                 # small gable ends above the hips
        out += [[P(xa, y0 + h, zh), P(xa, y1 - h, zh), P(xa, ym, zt)],
                [P(xb, y0 + h, zh), P(xb, y1 - h, zh), P(xb, ym, zt)]]
    return out


def slope_warning(b) -> str:
    r = b.roof
    need = MIN_SLOPE.get(r.cover)
    if need and r.slope_deg + 1e-9 < need:
        return (f"ความลาดหลังคา {r.slope_deg:g}° น้อยกว่าที่ผู้ผลิตวัสดุมุงทั่วไปแนะนำ {need:g}° "
                "(ตรวจกับคู่มือผู้ผลิตของวัสดุที่ใช้)")
    return ""
