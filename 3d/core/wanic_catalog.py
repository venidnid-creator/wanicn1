# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
# WANICNSURVEY 3D — แคตตาล็อกประตู หน้าต่าง สุขภัณฑ์ และวัสดุผิวห้อง
"""What a plan of WANIC ออกแบบอาคาร can be fitted with, and how each item
is billed by the 2569 criteria:

* doors and windows by type (``D1`` … ``W5``) — a set is billed as its
  parts, as หลักเกณฑ์ 4.2 ข้อ 5.2 lists them: frame (ชุด), leaves (บาน),
  hardware (ชุด) and glass (ตร.ฟ.), each with its ว480 2.5 labour;
* sanitary ware and bathroom fittings, counted in ชุด with ว480 2.6;
* room finishes (floor, wall tiles, ceiling) by room type, from the unit
  material recipes of the criteria.

Sizes are the usual Thai residential ones and can be changed per item.
"""
from __future__ import annotations

import re

SQFT_PER_M2 = 10.7639

# ---------------------------------------------------------------------------
# Doors and windows
# ---------------------------------------------------------------------------

#: code → spec. ``frame``: wood | alu; ``leaf``: wood | prefab | alu |
#: none; ``leaves``: number of leaves; ``glass``: share of the opening
#: glazed (0–1); ``slide``: a sliding set.
OPENING_TYPES = {
    "D1": dict(kind="door", name="ประตูบานเปิดเดี่ยว ไม้", w=0.90, h=2.00,
               frame="wood", leaf="wood", leaves=1, glass=0.0, slide=False),
    "D2": dict(kind="door", name="ประตูบานเปิดคู่ ไม้", w=1.60, h=2.00,
               frame="wood", leaf="wood", leaves=2, glass=0.0, slide=False),
    "D3": dict(kind="door", name="ประตูห้องน้ำ PVC/UPVC สำเร็จรูป", w=0.70,
               h=2.00, frame="wood", leaf="prefab", leaves=1, glass=0.0,
               slide=False),
    "D4": dict(kind="door", name="ประตูบานเลื่อนไม้", w=1.80, h=2.00,
               frame="wood", leaf="wood", leaves=2, glass=0.0, slide=True),
    "D5": dict(kind="door", name="ประตูกระจกกรอบอลูมิเนียม", w=0.90, h=2.00,
               frame="alu", leaf="alu", leaves=1, glass=0.8, slide=False),
    "W1": dict(kind="window", name="หน้าต่างบานเปิดคู่ ไม้", w=1.20, h=1.10,
               sill=0.90, frame="wood", leaf="wood", leaves=2, glass=0.7,
               slide=False),
    "W2": dict(kind="window", name="หน้าต่างบานเลื่อนอลูมิเนียม", w=1.20,
               h=1.10, sill=0.90, frame="alu", leaf="alu", leaves=2,
               glass=0.85, slide=True),
    "W3": dict(kind="window", name="หน้าต่างบานกระทุ้ง อลูมิเนียม", w=0.60,
               h=1.10, sill=0.90, frame="alu", leaf="alu", leaves=1,
               glass=0.85, slide=False),
    "W4": dict(kind="window", name="ช่องแสงกระจกติดตาย", w=0.60, h=0.60,
               sill=1.80, frame="wood", leaf="none", leaves=0, glass=0.85,
               slide=False),
    "W5": dict(kind="window", name="หน้าต่างบานเกล็ดกระจก", w=0.60, h=1.10,
               sill=0.90, frame="alu", leaf="alu", leaves=1, glass=0.9,
               slide=False),
}
DEFAULT_STYLE = {"door": "D1", "window": "W1"}


def opening_type(op) -> tuple[str, dict]:
    """``(code, spec)`` of an opening; old plans (no style) get the default
    of their kind."""
    kind = "window" if op.get("type") == "window" else "door"
    code = op.get("style")
    spec = OPENING_TYPES.get(code)
    if spec is None or spec["kind"] != kind:
        code = DEFAULT_STYLE[kind]
        spec = OPENING_TYPES[code]
    return code, spec


def types_of(kind) -> list[tuple[str, dict]]:
    return [(c, s) for c, s in OPENING_TYPES.items() if s["kind"] == kind]


# ---------------------------------------------------------------------------
# Sanitary ware (ว480 2.6) — plan size w × d (m) and the 3D block height
# ---------------------------------------------------------------------------

#: code → (name, ว480 code, labour baht/ชุด, w, d, z0, height)
SANITARY = {
    "WC1": ("โถส้วมนั่งราบชนิดมีหม้อน้ำ พร้อมอุปกรณ์", "2.6.1", 461,
            0.40, 0.70, 0.0, 0.75),
    "WC2": ("โถส้วมนั่งยอง ชนิดราดน้ำ", "2.6.2", 154, 0.45, 0.60, 0.0, 0.15),
    "UR": ("โถปัสสาวะชายพร้อมวาล์วกด", "2.6.4", 461, 0.40, 0.35, 0.45, 0.60),
    "LV": ("อ่างล้างหน้าพร้อมอุปกรณ์ (ครบชุด)", "2.6.6", 461, 0.55, 0.45,
           0.65, 0.20),
    "BT": ("อ่างอาบน้ำพร้อมอุปกรณ์ แบบธรรมดา", "2.6.7", 1025, 1.50, 0.75,
           0.0, 0.55),
    "SH": ("ฝักบัวก้านแข็งพร้อมวาล์วเปิด-ปิด", "2.6.9", 174, 0.25, 0.20,
           1.90, 0.10),
    "SP": ("สายชำระพร้อมสต๊อปวาล์ว", "2.6.11", 72, 0.15, 0.10, 0.50, 0.15),
    "TP": ("ที่ใส่กระดาษชำระ (เจาะยึดสกรู)", "2.6.13", 72, 0.15, 0.10, 0.70,
           0.12),
    "SD": ("ที่ใส่สบู่ (เจาะยึดสกรู)", "2.6.15", 72, 0.15, 0.10, 1.10, 0.08),
    "TR": ("ราวแขวนผ้า (เจาะยึดสกรู)", "2.6.19", 72, 0.60, 0.08, 1.40, 0.05),
    "MR": ("กระจกเงาสำเร็จรูป (เจาะยึดสกรู)", "2.6.20", 72, 0.45, 0.04,
           1.20, 0.60),
    "GB": ("ราวจับคนพิการ (โถส้วม/อ่างล้างหน้า)", "2.6.22", 108, 0.70, 0.10,
           0.70, 0.05),
    "FD": ("ตะแกรงกรองผงพร้อมที่ดักกลิ่น", "2.6.25", 77, 0.10, 0.10, 0.0,
           0.01),
    "FT": ("ก๊อกน้ำล้างพื้น", "2.6.23", 26, 0.10, 0.10, 0.45, 0.10),
    "SK1": ("ซิงค์สแตนเลส 1 หลุมพร้อมก๊อกคอยาว (ครบชุด)", "2.6.31", 308,
            0.80, 0.50, 0.80, 0.10),
    "SK2": ("ซิงค์สแตนเลส 2 หลุมพร้อมก๊อกคอยาว (ครบชุด)", "2.6.30", 328,
            1.20, 0.50, 0.80, 0.10),
}

#: The fittings «ชุดห้องน้ำมาตรฐาน» puts into a bathroom, with where along
#: the room (fractions of w, d) each goes.
BATHROOM_SET = [("WC1", 0.25, 0.80), ("SP", 0.08, 0.80), ("TP", 0.45, 0.92),
                ("LV", 0.75, 0.85), ("MR", 0.75, 0.97), ("SH", 0.80, 0.15),
                ("SD", 0.95, 0.30), ("TR", 0.30, 0.05), ("FD", 0.70, 0.30)]
KITCHEN_SET = [("SK1", 0.50, 0.88), ("FD", 0.50, 0.50)]


# ---------------------------------------------------------------------------
# Room finishes
# ---------------------------------------------------------------------------

#: room type → (floor recipe, wall tile recipe or "", tile height m,
#: ceiling: True/False)
ROOM_FINISH = {
    "ห้องน้ำ": ("9.26", "7.16", 2.00, True),
    "ห้องครัว": ("9.30", "7.16", 0.60, True),
    "ห้องซักล้าง": ("9.26", "7.16", 1.20, True),
    "ระเบียง": ("9.26", "", 0.0, False),
    "ชานพัก": ("9.26", "", 0.0, False),
    "ที่จอดรถ": ("9.3", "", 0.0, False),
}
DEFAULT_FINISH = ("9.30", "", 0.0, True)


def finish_of(room, default_floor=None) -> dict:
    """The room's finishes: its own choices over its type's defaults
    (``default_floor`` replaces the floor of rooms with no type default)."""
    name = (room.get("name") or "").strip()
    base = DEFAULT_FINISH
    if default_floor:
        base = (default_floor,) + DEFAULT_FINISH[1:]
    for key, val in ROOM_FINISH.items():
        if name.startswith(key):
            base = val
            break
    fl, wt, th, ce = base
    f = room.get("finish") or {}
    return {"floor": f.get("floor", fl), "wall_tile": f.get("wall_tile", wt),
            "tile_h": float(f.get("tile_h", th)),
            "ceiling": bool(f.get("ceiling", ce))}


def _inches(name) -> float:
    m = re.search(r'(\d+)\s*"\s*x\s*(\d+)', name or "")
    return float(m.group(1)) if m else 0.0


def floor_labour_code(recipe_code, name) -> str:
    """ว480 2.4 row for a floor recipe (by its tile size)."""
    if recipe_code in ("9.3", "9.4", "9.5", "9.6"):
        return "2.4.1"
    if "แกรนิตโต้" in (name or ""):
        return "2.4.8b" if _inches(name) >= 18 else "2.4.8"
    s = _inches(name)
    if s and s <= 4:
        return "2.4.6"
    if s and s <= 6:
        return "2.4.6b"
    if s >= 18:
        return "2.4.6d"
    return "2.4.6c"


def wall_tile_labour_code(name) -> str:
    """ว480 2.3.1.3 row for a wall tile recipe."""
    s = _inches(name)
    if s and s <= 6:
        return "2.3.3b"
    if s >= 18:
        return "2.3.3c"
    return "2.3.3a"
