# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
"""ระบบสุขาภิบาลตามจำนวนผู้ใช้ — how many people live in the house (the
setting ``users``, else two per bedroom, at least four), and from it the
septic tank (the smallest prefabricated anaerobic tank rated for them), the
grease trap of the kitchen and the screen pit before the public drain.
The tables are WANICNSURVEY's own recommendations for dwellings."""
from __future__ import annotations

import math

from core import wanic_building as B

#: prefabricated anaerobic septic tanks with media: (litres, users, size)
SEPTIC_SIZES = [(600, 5, "Ø 0.88 × 1.40"), (800, 7, "Ø 0.98 × 1.45"),
                (1000, 10, "Ø 1.05 × 1.55"), (1200, 12, "Ø 1.10 × 1.65"),
                (1600, 16, "Ø 1.20 × 1.80"), (2000, 20, "Ø 1.35 × 1.90")]
#: grease traps for a house kitchen: (litres, users up to, outside size w × l × h m)
GT_SIZES = [(30, 4, "0.30 × 0.45 × 0.35"), (50, 8, "0.40 × 0.55 × 0.40"),
            (100, 15, "0.50 × 0.70 × 0.50"), (150, 25, "0.60 × 0.80 × 0.55"),
            (200, 40, "0.70 × 0.90 × 0.60")]
#: the screen pit: inside w × l, depth (m), the screen
SCREEN_PIT = {"w": 0.40, "l": 0.40, "depth": 0.60, "wall": 0.10, "screen": "ตะแกรงสแตนเลส ช่องห่าง 10 มม. ถอดล้างได้",
              "pipe": "Ø4\""}
SEWAGE_L = 200.0                        # litres per person per day (house, design)


def _floors(data):
    """The floors of a building document, or of an inventory (B.elements)."""
    if "lib" in (data or {}):
        return data["floors"]
    return B.stacked(data)[0]


def bedrooms(data) -> int:
    floors = _floors(data)
    return sum(1 for f in floors for rm in f["rooms"] if "นอน" in (rm.get("name") or ""))


def kitchens(data) -> int:
    floors = _floors(data)
    return sum(1 for f in floors for rm in f["rooms"] if "ครัว" in (rm.get("name") or ""))


def users_of(data) -> int:
    """จำนวนผู้ใช้: the setting, else 2 per bedroom (at least 4)."""
    s = (data or {}).get("settings") or {}
    try:
        n = int(float(s.get("users") or 0))
    except (TypeError, ValueError):
        n = 0
    return n if n > 0 else max(4, 2 * bedrooms(data))


def septic_pick(users: int) -> dict:
    """The tank(s) for ``users``: the smallest size rated for them; past the
    largest, several of the largest."""
    for lit, n, size in SEPTIC_SIZES:
        if users <= n:
            return {"litres": lit, "users": n, "size": size, "count": 1}
    lit, n, size = SEPTIC_SIZES[-1]
    return {"litres": lit, "users": n, "size": size, "count": math.ceil(users / n)}


def grease_pick(users: int) -> dict:
    for lit, n, size in GT_SIZES:
        if users <= n:
            return {"litres": lit, "users": n, "size": size, "count": 1}
    lit, n, size = GT_SIZES[-1]
    return {"litres": lit, "users": n, "size": size, "count": math.ceil(users / n)}


def design(data) -> dict:
    """Everything the SN sheets print about the sizes."""
    u = users_of(data)
    st = septic_pick(u)
    gt = grease_pick(u)
    own = bool(((data or {}).get("settings") or {}).get("users"))
    return {"users": u, "users_from": "กำหนดเอง" if own else f"ห้องนอน {bedrooms(data)} ห้อง × 2 คน (ขั้นต่ำ 4)",
            "septic": st, "grease": gt, "screen": dict(SCREEN_PIT), "sewage": u * SEWAGE_L,
            "kitchens": kitchens(data)}


def design_lines(data) -> list:
    d = design(data)
    st, gt, sp = d["septic"], d["grease"], d["screen"]
    many = f" × {st['count']} ถัง" if st["count"] > 1 else ""
    return [f"ผู้ใช้อาคาร {d['users']} คน ({d['users_from']})",
            f"น้ำเสียออกแบบ {SEWAGE_L:,.0f} ลิตร/คน/วัน = {d['sewage']:,.0f} ลิตร/วัน",
            f"ถังบำบัดน้ำเสียสำเร็จรูป ST {st['litres']:,} ลิตร{many} (รองรับ {st['users']} คน/ถัง) {st['size']} ม.",
            f"บ่อดักไขมัน GT {gt['litres']} ลิตร (ถึง {gt['users']} คน) ขนาดภายนอก {gt['size']} ม. "
            "รับน้ำจากซิงก์ครัว",
            f"บ่อพักตะแกรง SP ภายใน {sp['w']:.2f} × {sp['l']:.2f} ลึก {sp['depth']:.2f} ม. {sp['screen']} "
            "ก่อนระบายสู่ท่อสาธารณะ"]
