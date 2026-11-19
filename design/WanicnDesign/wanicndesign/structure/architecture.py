# -*- coding: utf-8 -*-
"""Architectural work of the model (stage 7): floor finishes, ceilings,
doors and windows, bathrooms with wall tiles and sanitary ware.

Each item carries the labour code of the Comptroller General's list ว480
(26 มิ.ย. 2569) [W480]; quantities are net, by the measuring rules of the
2569 criteria [CGD2569] (openings deducted from walls, paint not on tiles).
"""
from __future__ import annotations

#: Floor finishes: key -> (BOQ item, ว480 labour code).
FLOOR_FINISHES = {
    "screed": ("เทปูนทรายปรับระดับพร้อมขัดมัน", "2.4.1"),
    "ceramic_16": ("ปูกระเบื้องเซรามิค 8\"×8\"–16\"×16\"", "2.4.6c"),
    "ceramic_24": ("ปูกระเบื้องเซรามิค 18\"×18\"–24\"×24\"", "2.4.6d"),
    "granito": ("ปูกระเบื้องแกรนิตโต้ 12\"×12\"–16\"×16\"", "2.4.8"),
    "granito_20": ("ปูกระเบื้องแกรนิตโต้ 18\"×18\"–20\"×20\"", "2.4.8b"),
    "none": ("", ""),
}
FLOOR_LABELS = [("ceramic_16", "กระเบื้องเซรามิค 8–16 นิ้ว"), ("ceramic_24", "กระเบื้องเซรามิค 18–24 นิ้ว"),
                ("granito", "แกรนิตโต้ 12–16 นิ้ว"), ("granito_20", "แกรนิตโต้ 18–20 นิ้ว"),
                ("screed", "ปูนขัดมัน"), ("none", "ไม่มี")]
CEILINGS = {"gypsum": ("ฝ้าแผ่นยิปซัมฉาบรอยต่อเรียบ", "2.2.2"), "none": ("", "")}
CEILING_LABELS = [("gypsum", "ฝ้ายิปซัมฉาบเรียบ"), ("none", "ไม่มีฝ้า")]

#: A bathroom: floor tiles 8–16", wall tiles to WET_TILE_HEIGHT, these fixtures.
WET_FLOOR = "ceramic_16"
WET_TILE_HEIGHT = 2.00
WALL_TILE = ("ผนังบุกระเบื้องเซรามิค 8\"×8\"–12\"×12\"", "2.3.3a")
FIXTURES = {
    "toilet": ("โถส้วมนั่งราบชนิดมีหม้อน้ำ พร้อมอุปกรณ์", "2.6.1"),
    "basin": ("อ่างล้างหน้าพร้อมอุปกรณ์", "2.6.6"),
    "shower": ("ฝักบัวก้านแข็งพร้อมวาล์ว", "2.6.9"),
    "spray": ("สายชำระพร้อมสต๊อปวาล์ว", "2.6.11"),
    "paper": ("ที่ใส่กระดาษชำระ", "2.6.13"),
    "soap": ("ที่ใส่สบู่", "2.6.15"),
    "towel": ("ราวแขวนผ้า", "2.6.19"),
    "mirror": ("กระจกเงาสำเร็จรูป", "2.6.20"),
    "drain": ("ตะแกรงกรองผงพร้อมที่ดักกลิ่น", "2.6.25"),
}
SQFT_PER_M2 = 10.7639


def level_rooms(b, lv):
    """Floor bays of a level with rooms: [(bay name, area, wet)]."""
    if lv.slab in ("roof", "none"):
        return []
    out = []
    for i, j in b.panels(lv.name):
        area = (b.xs[i + 1] - b.xs[i]) * (b.ys[j + 1] - b.ys[j])
        name = b.panel_name(i, j)
        out.append((name, area, name in lv.wet_bays))
    return out


def openings_on(b, lv, a, c) -> list[str]:
    seg = b.segment_name(a, c)
    return [e.split(":", 1)[1] for e in lv.openings if e.split(":", 1)[0] == seg]


def wet_wall_tiles(b, lv, bay: str) -> float:
    """Wall tile area round one bathroom, less its door openings, m²."""
    xpart, ypart = bay.split("/")
    i, j = int(xpart.split("-")[0]) - 1, ord(ypart.split("-")[0]) - ord("A")
    c = [(i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1)]
    area = 0.0
    for k in range(4):
        a, d = c[k], c[(k + 1) % 4]
        length = abs(b.xs[d[0]] - b.xs[a[0]]) + abs(b.ys[d[1]] - b.ys[a[1]]) - b.column_width
        holes = 0.0
        for name in openings_on(b, lv, a, d):
            o = b.opening_type(name)
            if o:
                holes += o.width * min(o.height, WET_TILE_HEIGHT)
        area += max(0.0, length * WET_TILE_HEIGHT - holes)
    return area
