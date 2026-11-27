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
#: The sizes doors and windows are made and sold in (กว้าง × สูง, metres),
#: with what each is usually for — the «ขนาดมาตรฐาน» choice of the panel.
STANDARD_SIZES = {
    "door": [(0.70, 2.00, "ประตูห้องน้ำ"), (0.80, 2.00, "ประตูห้องน้ำ/ห้องเก็บของ"),
             (0.90, 2.00, "ประตูห้องนอน/ห้องทั่วไป"), (1.00, 2.00, "ประตูทางเข้าบานเดี่ยว"),
             (1.20, 2.00, "ประตูบานคู่เล็ก"), (1.50, 2.00, "ประตูบานคู่"),
             (1.60, 2.00, "ประตูบานคู่ทางเข้า"), (1.80, 2.00, "ประตูบานคู่/บานเลื่อน 2 บาน"),
             (2.00, 2.05, "ประตูบานเลื่อนอลูมิเนียม 2 บาน"),
             (2.40, 2.05, "ประตูบานเลื่อนอลูมิเนียม 4 บาน"),
             (3.00, 2.05, "ประตูบานเลื่อนอลูมิเนียม 4 บาน (กว้าง)")],
    "window": [(0.40, 0.50, "ช่องแสง/บานเกล็ดห้องน้ำ"), (0.50, 1.00, "หน้าต่างบานเดี่ยวแคบ"),
               (0.60, 1.10, "หน้าต่างบานเดี่ยว"), (0.80, 1.10, "หน้าต่างบานเดี่ยว"),
               (1.00, 1.10, "หน้าต่างบานคู่เล็ก"), (1.20, 1.10, "หน้าต่างบานคู่"),
               (1.20, 1.20, "หน้าต่างบานคู่/บานเลื่อน"), (1.50, 1.20, "หน้าต่างบานเลื่อน 2 บาน"),
               (1.60, 1.20, "หน้าต่างบานเลื่อน 2 บาน"), (1.80, 1.20, "หน้าต่างบานเลื่อน 2 บาน"),
               (2.00, 1.20, "หน้าต่างบานเลื่อน 4 บาน"), (2.40, 1.20, "หน้าต่างบานเลื่อน 4 บาน"),
               (1.20, 1.50, "หน้าต่างสูง (ห้องนั่งเล่น)"), (1.80, 1.50, "หน้าต่างสูง (ห้องนั่งเล่น)")],
}


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
    "D15": dict(kind="door", name="ประตูไม้สักบานเปิดเดี่ยว ลูกฟักแกะลาย", w=0.90,
                h=2.00, frame="teak", leaf="teak", leaves=1, glass=0.0, slide=False,
                panels=True),
    "D16": dict(kind="door", name="ประตูไม้สักบานเปิดคู่ ลูกฟักแกะลาย", w=1.60,
                h=2.00, frame="teak", leaf="teak", leaves=2, glass=0.0, slide=False,
                panels=True),
    "D17": dict(kind="door", name="ประตูกระจกเปลือยบานเปิดคู่ (เทมเปอร์ 10 มม.)",
                w=1.60, h=2.10, frame="alu", leaf="alu", leaves=2, glass=0.95,
                slide=False),
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
    # -- ประตู-หน้าต่างอลูมิเนียมสำเร็จรูป (ขนาดมาตรฐานตามแคตตาล็อกผู้ผลิต) --
    # ``transom``: fixed glass over the leaves (m); ``side``: a fixed glass
    # side light (m); ``fixed``: leaves of a slider that do not move
    "D6": dict(kind="door", name="ประตูอลูมิเนียมบานเปิดเดี่ยว", w=0.90, h=2.05,
               frame="alu", leaf="alu", leaves=1, glass=0.8, slide=False),
    "D7": dict(kind="door", name="ประตูอลูมิเนียมบานเปิดคู่", w=1.60, h=2.05,
               frame="alu", leaf="alu", leaves=2, glass=0.8, slide=False),
    "D8": dict(kind="door", name="ประตูอลูมิเนียมบานเลื่อน 2 บาน", w=1.80, h=2.05,
               frame="alu", leaf="alu", leaves=2, glass=0.85, slide=True),
    "D9": dict(kind="door", name="ประตูอลูมิเนียมบานเลื่อน 4 บาน", w=2.80, h=2.05,
               frame="alu", leaf="alu", leaves=4, glass=0.85, slide=True),
    "D10": dict(kind="door", name="ประตูอลูมิเนียมบานเลื่อน + ติดตาย", w=1.80,
                h=2.05, frame="alu", leaf="alu", leaves=2, glass=0.85, slide=True,
                fixed=1),
    "D11": dict(kind="door", name="ประตูอลูมิเนียมบานเปิด + ช่องแสงบน", w=0.90,
                h=2.45, frame="alu", leaf="alu", leaves=1, glass=0.85,
                slide=False, transom=0.40),
    "D12": dict(kind="door", name="ประตูอลูมิเนียมบานเปิดคู่ + ช่องแสงบน", w=1.60,
                h=2.45, frame="alu", leaf="alu", leaves=2, glass=0.85,
                slide=False, transom=0.40),
    "D13": dict(kind="door", name="ประตูอลูมิเนียมบานเปิด + ติดตายข้าง", w=1.30,
                h=2.05, frame="alu", leaf="alu", leaves=1, glass=0.85,
                slide=False, side=0.40),
    "D14": dict(kind="door", name="ประตูอลูมิเนียมบานเลื่อน 2 บาน + ช่องแสงบน",
                w=1.80, h=2.45, frame="alu", leaf="alu", leaves=2, glass=0.85,
                slide=True, transom=0.40),
    "W6": dict(kind="window", name="หน้าต่างอลูมิเนียมบานเลื่อน 4 บาน", w=2.40,
               h=1.10, sill=0.90, frame="alu", leaf="alu", leaves=4, glass=0.85,
               slide=True),
    "W7": dict(kind="window", name="หน้าต่างอลูมิเนียมบานเลื่อน + ติดตาย", w=1.80,
               h=1.10, sill=0.90, frame="alu", leaf="alu", leaves=2, glass=0.85,
               slide=True, fixed=1),
    "W8": dict(kind="window", name="หน้าต่างอลูมิเนียมบานกระทุ้งคู่", w=1.20,
               h=1.10, sill=0.90, frame="alu", leaf="alu", leaves=2, glass=0.85,
               slide=False),
    "W9": dict(kind="window", name="หน้าต่างอลูมิเนียมบานเปิดคู่ + ช่องแสงบน",
               w=1.20, h=1.50, sill=0.60, frame="alu", leaf="alu", leaves=2,
               glass=0.85, slide=False, transom=0.40),
    "W10": dict(kind="window", name="หน้าต่างอลูมิเนียมบานติดตาย (Fix)", w=1.80,
                h=1.50, sill=0.60, frame="alu", leaf="none", leaves=0, glass=0.9,
                slide=False),
    "W11": dict(kind="window", name="หน้าต่างอลูมิเนียมบานเปิดเดี่ยว", w=0.60,
                h=1.10, sill=0.90, frame="alu", leaf="alu", leaves=1, glass=0.85,
                slide=False),
}
DEFAULT_STYLE = {"door": "D1", "window": "W1"}


def opening_sketch(spec) -> list:
    """The elevation of a type as boxes in 0..1 (x across, y up) for the
    picker's thumbnails: [(x0, y0, x1, y1, what)], what = frame | leaf |
    glass | fixed | arrow (slide) | swing (hinge side)."""
    out = [(0.0, 0.0, 1.0, 1.0, "frame")]
    h = float(spec.get("h", 2.0))
    w = float(spec.get("w", 1.0))
    top = 1.0 - float(spec.get("transom", 0.0)) / h
    right = 1.0 - float(spec.get("side", 0.0)) / w
    if spec.get("transom"):
        out.append((0.04, top + 0.02, 0.96, 0.96, "fixed"))
    if spec.get("side"):
        out.append((right + 0.02, 0.04, 0.96, top - 0.02, "fixed"))
    n = int(spec.get("leaves", 0))
    if n == 0:
        out.append((0.04, 0.04, 0.96, top - 0.02, "fixed"))
        return out
    lw = (right - 0.04 - 0.04) / n
    fixed = int(spec.get("fixed", 0))
    for k in range(n):
        x0 = 0.04 + k * lw
        x1 = x0 + lw - 0.01
        what = "fixed" if k >= n - fixed else ("glass" if spec.get("glass") else "leaf")
        out.append((x0, 0.04, x1, top - 0.02, what))
        if what != "fixed":
            out.append((x0, 0.04, x1, top - 0.02,
                        "arrow" if spec.get("slide") else
                        ("swing_r" if k % 2 == 0 else "swing_l")))
    return out


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
    "LV2": ("อ่างล้างหน้าวางบนเคาน์เตอร์ 2 อ่าง พร้อมเคาน์เตอร์หินและตู้ (ครบชุด)",
            "2.6.6", 461, 1.40, 0.55, 0.80, 0.15),
    "BT2": ("อ่างอาบน้ำตั้งพื้นทรงรี (Freestanding) พร้อมก๊อกตั้งพื้น", "2.6.7", 1025,
            1.60, 0.80, 0.0, 0.60),
}

#: decorations and screens drawn and modelled with the fittings but not
#: billed as sanitary ware (name, w, d, z0, height)
DECOR = {
    "GP": ("ฉากกั้นอาบน้ำกระจกนิรภัยใส 10 มม.", 0.90, 0.03, 0.0, 2.00),
    "PL": ("กระถางต้นไม้ประดับ", 0.40, 0.40, 0.0, 0.90),
    # furniture and appliances (the owner: «ห้องนอน รวมไปถึงเครื่องใช้ไฟฟ้า») —
    # shown in the plan and the 3D, never billed in the construction BOQ
    "BED": ("เตียงนอน 5 ฟุต พร้อมหัวเตียง", 1.60, 2.10, 0.0, 1.00),
    "BED1": ("เตียงเดี่ยว 3.5 ฟุต พร้อมหัวเตียง", 1.10, 2.05, 0.0, 0.95),
    "NS": ("โต๊ะข้างเตียง + โคมไฟ", 0.45, 0.40, 0.0, 0.55),
    "WR": ("ตู้เสื้อผ้า บานเปิด", 1.20, 0.60, 0.0, 2.00),
    "ARM": ("เก้าอี้นวม", 0.75, 0.75, 0.0, 0.80),
    "TB": ("โต๊ะข้าง", 0.50, 0.50, 0.0, 0.45),
    "TV": ("ทีวีติดผนัง 43\" + ตู้วางทีวี", 1.20, 0.40, 0.0, 1.30),
    "DK": ("โต๊ะทำงาน + เก้าอี้", 1.00, 0.55, 0.0, 0.75),
    "FR": ("ตู้เย็น 2 ประตู", 0.65, 0.65, 0.0, 1.70),
    "WM": ("เครื่องซักผ้าฝาหน้า", 0.60, 0.60, 0.0, 0.85),
}
# the owner (27 Nov): every room type its full set — the office, the meeting room, the
# recreation room and the hotel-style reception (shown, never billed in the construction BOQ)
DECOR.update({
    "PC": ("โต๊ะทำงานคอมพิวเตอร์ + จอ + เก้าอี้สำนักงาน + รางเดินสายไฟ", 1.40, 0.70, 0.0, 0.75),
    "COF": ("มุมกาแฟ: เคาน์เตอร์ + เครื่องชงกาแฟ + ตู้เย็นเล็ก", 1.20, 0.55, 0.0, 0.90),
    "SOF": ("โซฟา 3 ที่นั่ง", 2.00, 0.85, 0.0, 0.85),
    "CT": ("โต๊ะกลางรับแขก", 1.00, 0.55, 0.0, 0.40),
    "WCH": ("เก้าอี้นั่งรอ 3 ที่นั่ง", 1.70, 0.60, 0.0, 0.85),
    "BS": ("ชั้นหนังสือ / ตู้เอกสาร", 1.00, 0.35, 0.0, 1.90),
    "MT8": ("โต๊ะประชุม 8 ที่นั่ง พร้อมเก้าอี้ และช่องปลั๊ก/HDMI กลางโต๊ะ", 3.20, 2.10, 0.0, 0.75),
    "MT12": ("โต๊ะประชุม 12 ที่นั่ง พร้อมเก้าอี้ และช่องปลั๊ก/HDMI กลางโต๊ะ", 4.40, 2.30, 0.0, 0.75),
    "SCR": ("จอแสดงผล 86\" + ลำโพงซาวด์บาร์ + กล้องประชุมทางไกล", 2.40, 0.12, 0.0, 2.10),
    "PJ": ("โปรเจกเตอร์ติดเพดาน", 0.40, 0.35, 2.45, 0.20),
    "GT": ("โต๊ะพูล/โต๊ะเกม", 2.30, 1.30, 0.0, 0.80),
    "RCP": ("เคาน์เตอร์ต้อนรับ (แบบโรงแรม) + ผนังโลโก้ด้านหลัง", 3.00, 1.40, 0.0, 2.40),
    # the kitchen (owner, 27 Nov: «ห้องครัวด้วย สวยๆ»): a run of base cabinets under a stone top
    # with wall cabinets over it, the hob with its hood, the dining table
    "KB": ("ตู้ครัวล่าง + ท็อปหิน + ตู้แขวนด้านบน (ช่วง 0.60 ม.)", 0.60, 0.60, 0.0, 2.20),
    "HOB": ("เตาแก๊ส 2 หัวฝังท็อป + เครื่องดูดควัน + ตู้ล่าง", 0.80, 0.60, 0.0, 2.20),
    "MW": ("ตู้วางไมโครเวฟ/เตาอบ (สูง)", 0.60, 0.60, 0.0, 2.20),
    "DT": ("โต๊ะรับประทานอาหาร 4 ที่นั่ง พร้อมเก้าอี้", 1.30, 1.50, 0.0, 0.75),
    # ห้องอาบน้ำ (owner, 27 Nov): the shower's wet zone a step down behind a stone curb
    "WZ": ("โซนเปียกฝักบัว พื้นลดระดับ 5 ซม. ขอบหินกันน้ำ + รางระบายน้ำ", 1.20, 1.20, 0.0, 0.05),
    "BN": ("ม้านั่งไม้ในห้องอาบน้ำ + ชั้นวางผ้าเช็ดตัว", 1.00, 0.40, 0.0, 0.45),
})
#: the furniture / appliance codes (DECOR, not billed)
FURNITURE = ("BED", "BED1", "NS", "WR", "ARM", "TB", "TV", "DK", "FR", "WM",
             "PC", "COF", "SOF", "CT", "WCH", "BS", "MT8", "MT12", "SCR", "PJ", "GT", "RCP",
             "KB", "HOB", "MW", "DT", "WZ", "BN")


class _Placer:
    """Lays furniture in a room ``w`` × ``d`` (local plan, corner at 0, 0): every piece back to a
    wall (or free in the middle), never over a door's way in (its width + 0.30 m, 1.0 m into the
    room) nor a tall piece in front of a window — the owner: «ไม่ให้ตรงกับประตูทางเข้าและหน้าต่าง»."""

    def __init__(self, w, d, openings, wall=0.08):
        self.w, self.d, self.wall = w, d, wall
        self.busy = []                               # (x0, y0, x1, y1, tall_only)
        self.walls_open = {"S": [], "N": [], "W": [], "E": []}
        for kind, ox, oy, ow in openings or []:
            side = min((("S", abs(oy)), ("N", abs(oy - d)), ("W", abs(ox)), ("E", abs(ox - w))),
                       key=lambda t: t[1])[0]
            c = ox if side in ("S", "N") else oy
            self.walls_open[side].append((kind, c, ow))
            half = ow / 2 + (0.15 if kind == "door" else 0.05)
            deep = 1.00 if kind == "door" else 0.60
            if side == "S":
                r = (c - half, 0.0, c + half, deep)
            elif side == "N":
                r = (c - half, d - deep, c + half, d)
            elif side == "W":
                r = (0.0, c - half, deep, c + half)
            else:
                r = (w - deep, c - half, w, c + half)
            self.busy.append(r + (kind != "door",))
        self.out = []

    def has_door(self, side):
        return any(k == "door" for k, _c, _w in self.walls_open[side])

    def free(self, r, tall):
        x0, y0, x1, y1 = r
        if x0 < self.wall - 1e-6 or y0 < self.wall - 1e-6 or x1 > self.w - self.wall + 1e-6 or \
                y1 > self.d - self.wall + 1e-6:
            return False
        for b in self.busy:
            if b[4] and not tall:
                continue                             # under a window sill: low pieces may stand
            if x0 < b[2] - 1e-6 and b[0] < x1 - 1e-6 and y0 < b[3] - 1e-6 and b[1] < y1 - 1e-6:
                return False
        return True

    def place(self, code, sides=("N", "E", "W", "S"), at=0.5, gap=0.0, clear=0.0, tall=None):
        """Back to the first wall of ``sides`` with room, as near ``at`` (fraction along it) as
        it goes; ``clear``: the free space kept in front of it. Returns (x, y) or None."""
        if code in DECOR:
            _n, pw, pd, z0, ph = DECOR[code]
        elif code in SANITARY:
            _n, _i, _r, pw, pd, z0, ph = SANITARY[code]
            pd = max(pd, 0.60) if code.startswith("SK") else pd     # a sink stands in a 0.60 counter
            if code == "BT2":                                        # the freestanding bath as modelled,
                pw, pd = 1.85, 1.05                                  # with its floor mixer
        else:
            return None
        tall = (z0 + ph > 1.0 and z0 < 1.0) if tall is None else tall
        for side in sides:
            along = side in ("S", "N")
            L = self.w if along else self.d
            cands = []
            k = 0.0
            while k <= L:
                cands.append(k)
                k += 0.05
            cands.sort(key=lambda v: abs(v - at * L))
            for c in cands:
                if along:
                    x0, x1 = c - pw / 2, c + pw / 2
                    y0, y1 = (self.wall + gap, self.wall + gap + pd) if side == "S" else \
                        (self.d - self.wall - gap - pd, self.d - self.wall - gap)
                    keep = (x0, y1, x1, y1 + clear) if side == "S" else (x0, y0 - clear, x1, y0)
                    cx, cy, dir_ = c, (y0 + y1) / 2, 0
                else:
                    y0, y1 = c - pw / 2, c + pw / 2
                    x0, x1 = (self.wall + gap, self.wall + gap + pd) if side == "W" else \
                        (self.w - self.wall - gap - pd, self.w - self.wall - gap)
                    keep = (x1, y0, x1 + clear, y1) if side == "W" else (x0 - clear, y0, x0, y1)
                    cx, cy, dir_ = (x0 + x1) / 2, c, 1
                if self.free((x0, y0, x1, y1), tall):
                    self.busy.append((x0, y0, x1, y1, False))
                    if clear > 0:
                        self.busy.append(keep + (False,))
                    self.out.append((code, round(cx, 3), round(cy, 3), dir_))
                    return cx, cy
        return None

    def centre(self, code, dir_=0, at=(0.5, 0.5)):
        """Free-standing (a meeting table, a game table) round ``at`` (fractions)."""
        if code not in DECOR:
            return None
        _n, pw, pd, _z, _h = DECOR[code]
        sx, sy = (pw, pd) if dir_ == 0 else (pd, pw)
        best = None
        for i in range(-12, 13):
            for j in range(-12, 13):
                cx, cy = self.w * at[0] + i * 0.05, self.d * at[1] + j * 0.05
                r = (cx - sx / 2, cy - sy / 2, cx + sx / 2, cy + sy / 2)
                if self.free(r, False):
                    dist = abs(i) + abs(j)
                    if best is None or dist < best[0]:
                        best = (dist, cx, cy, r)
        if best is None:
            return None
        self.busy.append(best[3] + (False,))
        self.out.append((code, round(best[1], 3), round(best[2], 3), dir_))
        return best[1], best[2]

    def ceiling(self, code, x, y, dir_=0):
        self.out.append((code, round(x, 3), round(y, 3), dir_))


def _quiet_sides(pl, order=("N", "E", "W", "S")):
    """The walls with no door first (the bed's head, the screen, the counter go there)."""
    return tuple(sorted(order, key=lambda sd: (pl.has_door(sd), order.index(sd))))


def furnish(name: str, w: float, d: float, openings=(), wall: float = 0.08) -> list:
    """The furniture of a room by its type (its name), clear of its doors and windows:
    [(code, x, y, dir)] from the room's corner. Each set only in its own room type —
    beds only in a bedroom, the office set only in an office … (owner, 27 Nov)."""
    n = str(name or "")
    pl = _Placer(w, d, openings, wall)
    quiet = _quiet_sides(pl)
    if n.startswith("ห้องนอน"):
        big = w >= 3.0 and d >= 3.0
        bed = "BED" if big else "BED1"
        head = quiet[0]
        p = pl.place(bed, (head,) + tuple(sd for sd in quiet if sd != head), clear=0.6, tall=True)
        if p:
            _n, bw, _bd, _z, _h = DECOR[bed]
            for sgn in (-1, 1):                      # the bedside tables each side of the head
                side = pl.out[-1 if sgn < 0 else -1]
                (_c, bx, by, bdir) = [o for o in pl.out if o[0] == bed][0]
                if bdir == 0:
                    at = (bx + sgn * (bw / 2 + 0.25)) / w
                    pl.place("NS", (head,), at=at)
                else:
                    at = (by + sgn * (bw / 2 + 0.25)) / d
                    pl.place("NS", (head,), at=at)
                del side
        pl.place("WR", quiet[1:] + quiet[:1], at=0.15, clear=0.6)
        opp = {"N": "S", "S": "N", "E": "W", "W": "E"}[head]
        pl.place("TV", (opp,) + quiet, at=0.5)
        if big:
            pl.place("DK", quiet[1:] + quiet[:1], at=0.85, clear=0.5)
            pl.place("ARM", tuple(reversed(quiet)), at=0.1)
        return pl.out
    if n.startswith("ห้องทำงาน"):
        for at in (0.25, 0.75, 0.25, 0.75):
            if not pl.place("PC", quiet, at=at, clear=0.7):
                break
        pl.place("COF", tuple(reversed(quiet)), at=0.85)
        pl.place("BS", quiet, at=0.05)
        if pl.place("SOF", tuple(reversed(quiet)), at=0.4, clear=0.4):
            pl.centre("CT", at=(0.5, 0.5))
        pl.place("WCH", ("S", "W", "E", "N"), at=0.6)
        pl.place("PL", ("E", "W", "N", "S"), at=0.02)
        return pl.out
    if n.startswith("ห้องประชุม"):
        big = w * d >= 30.0 and max(w, d) >= 6.0
        tb = "MT12" if big else "MT8"
        long_x = w >= d
        if not pl.centre(tb, 0 if long_x else 1):
            pl.centre("MT8", 0 if long_x else 1)
        short = ("E", "W") if long_x else ("N", "S")
        side = next((sd for sd in short if not pl.has_door(sd)), short[0])
        pl.place("SCR", (side,), at=0.5, tall=False)
        pl.ceiling("PJ", w / 2 if long_x else w / 2, d / 2, 0 if long_x else 1)
        pl.place("COF", tuple(sd for sd in ("N", "S", "E", "W") if sd not in short), at=0.9)
        pl.place("PL", ("N", "S", "E", "W"), at=0.02)
        return pl.out
    if n.startswith("ห้องสันทนาการ"):
        pl.place("TV", quiet, at=0.5)
        if pl.place("SOF", tuple(reversed(quiet)), at=0.5, clear=0.45):
            pl.centre("CT", at=(0.5, 0.45))
        if w * d >= 18.0:
            pl.centre("GT", 0 if w >= d else 1, at=(0.5, 0.75))
        pl.place("BS", quiet[1:] + quiet[:1], at=0.1)
        pl.place("ARM", quiet[1:] + quiet[:1], at=0.8)
        pl.place("ARM", tuple(reversed(quiet)), at=0.15)
        pl.place("PL", ("E", "W", "N", "S"), at=0.02)
        return pl.out
    if n.startswith(("ห้องต้อนรับ", "ล็อบบี้", "โถงต้อนรับ")):
        pl.place("RCP", quiet, at=0.5, clear=0.9)
        if pl.place("SOF", tuple(reversed(quiet)), at=0.5, clear=0.45):
            pl.centre("CT", at=(0.5, 0.4))
        pl.place("WCH", tuple(reversed(quiet)), at=0.2)
        for _k in range(2):
            pl.place("PL", ("E", "W", "N", "S"), at=0.02)
        return pl.out
    if n.startswith(("ห้องอาบน้ำ", "อาบน้ำ")):
        # a bathing room without a WC: the shower in a stepped-down wet zone behind a glass
        # screen in one corner, the bath (freestanding when there is room) on the quiet wall,
        # the vanity with its mirror, a towel rail, a bench, a plant
        side = quiet[0]
        corner = 0.0 if side in ("N", "S") else 0.0
        if pl.place("WZ", (side,), at=0.02, tall=False):
            wz = pl.out[-1]
            # the shower set on the wall behind the wet zone, the drain in it
            sx_, sy_ = wz[1], wz[2]
            if side == "N":
                sy_ = d - wall - 0.10
            elif side == "S":
                sy_ = wall + 0.10
            elif side == "E":
                sx_ = w - wall - 0.10
            else:
                sx_ = wall + 0.10
            pl.out.append(("SH", round(sx_, 3), round(sy_, 3), wz[3]))
            pl.out.append(("FD", wz[1], wz[2], wz[3]))
            # the glass screen along the wet zone's open side
            _c, wx, wy, wd = wz
            if wd == 0:
                pl.out.append(("GP", round(wx + 0.62, 3), wy, 1))
            else:
                pl.out.append(("GP", wx, round(wy + 0.62, 3), 0))
        bath = "BT2" if w * d >= 7.5 else "BT"
        pl.place(bath, (side,) + quiet[1:], at=0.6, clear=0.5, tall=False)
        lv = "LV2" if max(w, d) >= 3.0 else "LV"
        if pl.place(lv, quiet[1:] + quiet[:1], at=0.5, clear=0.6, tall=False):
            _c, lx, ly, ld = pl.out[-1]
            # the mirror on the wall over the basin
            if ld == 0:
                ly = wall + 0.02 if ly < d / 2 else d - wall - 0.02
            else:
                lx = wall + 0.02 if lx < w / 2 else w - wall - 0.02
            pl.out.append(("MR", round(lx, 3), round(ly, 3), ld))
        pl.place("TR", quiet[1:] + quiet[:1], at=0.1, tall=False)
        pl.place("BN", tuple(reversed(quiet)), at=0.5)
        pl.place("PL", ("E", "W", "N", "S"), at=0.98)
        del corner
        return pl.out
    if n.startswith("ห้องครัว"):
        # one straight run on the quietest wall, as a kitchen designer lays it: the fridge at the
        # end, a cabinet, the sink (under the window is fine: low), cabinets, the hob, a tall unit
        side = quiet[0]
        along = side in ("S", "N")
        L = (w if along else d) - 2 * wall
        run = [("FR", 0.65), ("KB", 0.60), ("SK1", 0.80), ("KB", 0.60), ("HOB", 0.80), ("KB", 0.60),
               ("MW", 0.60)]
        while sum(r[1] for r in run) > L - 0.05 and len(run) > 3:
            run.pop(1 if run[1][0] == "KB" else -1)
        pos = wall + 0.02
        start = (L - sum(r[1] for r in run)) / 2 + wall
        pos = start
        for code, ln in run:
            at = (pos + ln / 2) / (w if along else d)
            # the wall cabinets / hood are tall: they keep off a window; the sink may stand under it
            pl.place(code, (side,), at=at, tall=False if code == "SK1" else None)
            pos += ln
        # a floor drain (ตะแกรงกรองผง + ที่ดักกลิ่น) in front of the sink — the grey water of the
        # sink and the floor run out through the drain system (wanic_mep: outside the building)
        for c_, sx_, sy_, sd_ in list(pl.out):
            if c_ == "SK1":
                fx_ = sx_ if side in ("N", "S") else (sx_ + (0.75 if side == "W" else -0.75))
                fy_ = sy_ if side in ("E", "W") else (sy_ + (0.75 if side == "S" else -0.75))
                pl.out.append(("FD", round(fx_, 3), round(fy_, 3), sd_))
        if w >= 2.8 and d >= 2.8:
            pl.centre("DT", 0 if w >= d else 1, at=(0.5, 0.45))
        pl.place("PL", ("E", "W", "N", "S"), at=0.02)
        return pl.out
    if n.startswith(("ห้องนั่งเล่น", "ห้องรับแขก")):
        pl.place("TV", quiet, at=0.5)
        if pl.place("SOF", tuple(reversed(quiet)), at=0.5, clear=0.45):
            pl.centre("CT", at=(0.5, 0.5))
        pl.place("ARM", quiet[1:] + quiet[:1], at=0.2)
        pl.place("PL", ("E", "W", "N", "S"), at=0.02)
        return pl.out
    return []


#: the room types that get a furniture set by ``furnish``
FURNISHED = ("ห้องนอน", "ห้องครัว", "ห้องอาบน้ำ", "ห้องทำงาน", "ห้องประชุม", "ห้องสันทนาการ", "ห้องต้อนรับ", "ล็อบบี้",
             "โถงต้อนรับ", "ห้องนั่งเล่น", "ห้องรับแขก")

#: The fittings «ชุดห้องน้ำมาตรฐาน» puts into a bathroom, with where along
#: the room (fractions of w, d) each goes.
BATHROOM_SET = [("WC1", 0.25, 0.80), ("SP", 0.08, 0.80), ("TP", 0.45, 0.92),
                ("LV", 0.75, 0.85), ("MR", 0.75, 0.97), ("SH", 0.80, 0.15),
                ("SD", 0.95, 0.30), ("TR", 0.30, 0.05), ("FD", 0.70, 0.30)]
KITCHEN_SET = [("SK1", 0.50, 0.88), ("FD", 0.50, 0.50)]


def bedroom_layout(w: float, d: float, wall: float = 0.08) -> list:
    """ห้องนอน as the owner's plan draws it: the bed's head on the far wall
    (a 5-ft bed, a 3.5-ft one in a small room) with a bedside table and
    lamp each side, the wardrobe against a side wall, the TV on the wall
    facing the bed, an armchair and side table by the window corner (when
    there is room). [(code, x, y, dir)] from the room's corner."""
    out = []
    big = w >= 3.0 and d >= 3.0
    bed, bw, bd = ("BED", 1.60, 2.10) if big else ("BED1", 1.10, 2.05)
    if w < bw + 0.6 or d < bd + 0.6:
        return out
    bx = w / 2 if w < 3.6 else w / 2 + 0.30                    # a little off the wardrobe
    out.append((bed, bx, d - wall - bd / 2, 0))
    for side in (-1, 1):
        nx = bx + side * (bw / 2 + 0.25)
        if wall + 0.22 < nx < w - wall - 0.22:
            out.append(("NS", nx, d - wall - 0.20, 0))
    if w >= 3.0 and bx - bw / 2 - 0.30 > 0.65:                 # wardrobe on the left wall
        out.append(("WR", wall + 0.30, d - wall - 0.70, 1))
    elif d >= bd + 1.4:                                         # or beside the door wall
        out.append(("WR", w - wall - 0.70, wall + 0.30, 0))
    if d >= bd + 1.2:
        out.append(("TV", bx, wall + 0.20, 0))
    if big and d >= bd + 1.6 and w >= 3.4:
        out.append(("ARM", wall + 0.50, wall + 0.55, 0))
        out.append(("TB", wall + 1.10, wall + 0.40, 0))
    return [(c, round(x, 3), round(y, 3), dr) for c, x, y, dr in out]


def bathroom_layout(w: float, d: float, wall: float = 0.08) -> list:
    """Fittings for a bathroom ``w`` × ``d`` (grid size, m), laid out along
    its long wall the way a designer would — the wet zone (shower behind a
    glass screen, or a freestanding bath when there is room) at one end,
    the WC in the middle with its spray and paper holder, the vanity (two
    basins on a long counter when it is long enough) with its mirror at
    the other end, a towel rail by the shower, a floor drain in the wet
    zone and, in a big room, a plant. [(code, x, y, dir)] from the room's
    corner; ``dir`` 0 = along x."""
    long_x = w >= d
    L, S = (w, d) if long_x else (d, w)
    back = S - wall                     # the long wall the fittings stand on
    items = []

    def put(code, along, depth_from_back, extra=None):
        items.append((code, along, back - depth_from_back, extra))
    tub = L >= 3.4 and S >= 2.2
    wet = 1.90 if tub else 1.00 if L < 3.2 else 1.20
    if tub:
        put("BT2", wet / 2, 0.80 / 2 + 0.20)
        put("FD", wet / 2, 0.80 + 0.40)
    else:
        put("SH", wet / 2, 0.10)
        put("FD", wet / 2, 0.55)
        put("GP", wet + 0.02, 0.45, "screen")
    put("TR", wet / 2, -0.04 + (S - 2 * wall) if S > 1.6 else 0.04)
    rest = L - wet - 0.10
    vanity = "LV2" if rest >= 2.30 and S >= 1.6 else "LV"
    vw = 1.40 if vanity == "LV2" else 0.60
    wc_x = wet + 0.10 + max((rest - vw) / 2, 0.45)
    if vanity == "LV" and rest < 1.30:
        wc_x = wet + 0.10 + 0.40
    put("WC1", wc_x, 0.35)
    put("SP", wc_x - 0.35, 0.05)
    put("TP", wc_x + 0.35, 0.05)
    vx = L - vw / 2 - 0.05
    if vx - vw / 2 < wc_x + 0.45:                   # no room: the basin on the
        vx = wc_x                                   # opposite wall instead
        items.append((vanity, vx, wall + 0.30, "front"))
        items.append(("MR", vx, wall + 0.02, "front"))
    else:
        put(vanity, vx, (0.55 if vanity == "LV2" else 0.45) / 2)
        put("MR", vx, 0.02)
    if L >= 3.0 and S >= 1.8:
        put("PL", L - 0.30, S - 2 * wall - 0.30)
    out = []
    for code, a, b, extra in items:
        x, y = (a, b) if long_x else (b, a)
        dir_ = 0 if long_x else 1
        if extra == "screen":
            dir_ = 1 - dir_                         # the screen stands across
        out.append((code, round(x, 3), round(y, 3), dir_))
    return out


# ---------------------------------------------------------------------------
# Room finishes
# ---------------------------------------------------------------------------

#: room type → (floor recipe, wall tile recipe or "", tile height m,
#: ceiling: True/False)
ROOM_FINISH = {
    "ห้องน้ำ": ("9.26", "7.16", 2.00, True),
    "ห้องอาบน้ำ": ("9.26", "7.16", 2.00, True),
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
        return "2.3.1.3b"
    if s >= 18:
        return "2.3.1.3c"
    return "2.3.1.3a"


# ---------------------------------------------------------------------------
# Roof coverings (หลักเกณฑ์ 4.2 ข้อ 1, ว480 2.1)
# ---------------------------------------------------------------------------

#: code → spec. ``eff`` is the covering one piece gives after the side and
#: end laps (width, length in m) — pieces per m² = 1 / (w × l), as the
#: criteria say (หักความกว้างที่ซ้อนทับตามคู่มือผู้ผลิต); ``cap`` the
#: effective length of one ridge/hip cap; ``lab`` the ว480 rows (area,
#: ridge/hip caps, verge caps) and ``color`` the 3D colour.
ROOF_TILES = {
    "R1": dict(name="กระเบื้องคอนกรีต ซีแพคโมเนีย (ลอนสเปน) 33×42 ซม.",
               size=(0.33, 0.42), eff=(0.30, 0.32), cap=1 / 3.3,
               cap_name="ครอบสันโค้ง/ครอบตะเข้สัน กระเบื้องคอนกรีต",
               lab=("2.1.3", "2.1.3r", "2.1.3v"), color=(0.62, 0.30, 0.22),
               wave=("s", 0.30, 0.045, 0.32, 0.02), verge=0.333,
               unit="แผ่น"),
    "R2": dict(name="กระเบื้องคอนกรีต ซีแพคโมเนีย (ลอนเรียบ/ผิวเรียบ) 33×42 ซม.",
               size=(0.33, 0.42), eff=(0.30, 0.32), cap=1 / 3.3,
               cap_name="ครอบสันโค้ง/ครอบตะเข้สัน กระเบื้องคอนกรีต",
               lab=("2.1.3", "2.1.3r", "2.1.3v"), color=(0.35, 0.36, 0.40),
               wave=("sin", 0.30, 0.012, 0.32, 0.02), verge=0.333,
               unit="แผ่น"),
    "R3": dict(name="กระเบื้องไฟเบอร์ซีเมนต์ลอนคู่ 0.50×1.20 ม.",
               size=(0.50, 1.20), eff=(0.44, 1.00), cap=0.25,
               cap_name="ครอบสันปรับมุม กระเบื้องลอนคู่",
               lab=("2.1.1", "2.1.1r", "2.1.1r"), color=(0.62, 0.62, 0.60),
               wave=("sin", 0.177, 0.05, 1.00, 0.008), verge=0.50,
               unit="แผ่น"),
    "R4": dict(name="กระเบื้องไฟเบอร์ซีเมนต์ลอนคู่ 0.50×1.50 ม.",
               size=(0.50, 1.50), eff=(0.44, 1.30), cap=0.25,
               cap_name="ครอบสันปรับมุม กระเบื้องลอนคู่",
               lab=("2.1.1", "2.1.1r", "2.1.1r"), color=(0.62, 0.62, 0.60),
               wave=("sin", 0.177, 0.05, 1.30, 0.008), verge=0.50,
               unit="แผ่น"),
    "R5": dict(name="กระเบื้องไฟเบอร์ซีเมนต์ลอนเล็ก 0.54×1.20 ม.",
               size=(0.54, 1.20), eff=(0.47, 1.00), cap=0.25,
               cap_name="ครอบสันปรับมุม กระเบื้องลอนเล็ก",
               lab=("2.1.1", "2.1.1r", "2.1.1r"), color=(0.66, 0.64, 0.60),
               wave=("sin", 0.0775, 0.018, 1.00, 0.006), verge=0.50,
               unit="แผ่น"),
    "R6": dict(name="กระเบื้องดินเผาเคลือบเซรามิค 30×40 ซม.",
               size=(0.30, 0.40), eff=(0.26, 0.31), cap=0.30,
               cap_name="ครอบสัน/ครอบตะเข้สัน กระเบื้องเซรามิค",
               lab=("2.1.7", "2.1.7r", "2.1.7v"), color=(0.55, 0.18, 0.15),
               wave=("s", 0.26, 0.04, 0.31, 0.018), verge=0.333,
               unit="แผ่น"),
    "R7": dict(name="หลังคาเหล็กรีดลอน (Metal Sheet) 0.35 มม.",
               size=(0.76, 1.00), eff=(0.76, 1.00), cap=1.00,
               cap_name="ครอบสัน/ครอบข้าง (Flashing) เหล็กรีดลอน",
               lab=("2.1.8", "2.1.8f", "2.1.8f"), color=(0.20, 0.33, 0.45),
               wave=("trap", 0.19, 0.025, 0.0, 0.0), verge=1.0,
               unit="ตร.ม."),
}
DEFAULT_TILE = "R1"


def roof_tile(s) -> tuple[str, dict]:
    code = (s or {}).get("tile") or DEFAULT_TILE
    if code not in ROOF_TILES:
        code = DEFAULT_TILE
    return code, ROOF_TILES[code]


#: pieces per m² as the makers' manuals state them (where they publish a
#: round figure); the rest from the effective cover of one piece
MAKER_PER_M2 = {"R1": 10.0, "R2": 10.0}


def maker_per_m2(spec, code=None) -> float:
    """Pieces per m² for a roofing by its maker's manual (0 for roofing
    sold by the m²)."""
    if spec.get("unit") == "ตร.ม.":
        return 0.0
    if code is None:
        code = next((k for k, v in ROOF_TILES.items() if v is spec), None)
    if code in MAKER_PER_M2:
        return MAKER_PER_M2[code]
    w, l = spec["eff"]
    return round(1.0 / (w * l), 2)


def maker_note(spec, code=None) -> str:
    """One line of the maker's laying data for the roofing."""
    w, l = spec["eff"]
    per = maker_per_m2(spec, code)
    if not per:
        return f"ขายเป็น ตร.ม. · ความกว้างใช้งาน {w * 100:.0f} ซม. · ระยะแป {l * 100:.0f} ซม."
    return (f"ตามคู่มือผู้ผลิต {per:g} แผ่น/ตร.ม. · ขนาดแผ่น {spec['size'][0] * 100:.0f}×"
            f"{spec['size'][1] * 100:.0f} ซม. · ความกว้างใช้งาน {w * 100:.0f} ซม. · "
            f"ระยะแป/ระยะซ้อน {l * 100:.0f} ซม.")


def tiles_per_m2(spec, s=None) -> float:
    """Pieces per m² of slope: the user's figure, else the maker's."""
    own = float((s or {}).get("tiles_m2") or 0)
    if own > 0:
        return own
    per = maker_per_m2(spec)
    if per:
        return per
    w, l = spec["eff"]
    return 1.0 / (w * l)


#: Colours of the 3D parts (RGB 0–1).
COLORS = {
    "wood": (0.55, 0.36, 0.20), "wood_dark": (0.40, 0.25, 0.14),
    "teak": (0.66, 0.40, 0.17), "teak_dark": (0.45, 0.25, 0.10),
    "pvc": (0.93, 0.92, 0.88), "alu": (0.78, 0.80, 0.82),
    "glass": (0.80, 0.90, 0.92), "concrete": (0.80, 0.80, 0.78),   # glass: soft pale aqua
    "metal": (0.30, 0.30, 0.32), "fascia": (0.95, 0.95, 0.93),
    "sanitary": (0.97, 0.97, 0.97),
}


#: Tile colours a concrete / ceramic roof is usually sold in (RGB 0–1).
TILE_COLORS = {
    "แดงอิฐ": (0.70, 0.30, 0.20), "ส้มอิฐ": (0.84, 0.46, 0.30),
    "ส้มอำพัน": (0.80, 0.45, 0.20), "น้ำตาลไม้": (0.45, 0.27, 0.13),
    "แดงเลือดหมู": (0.48, 0.13, 0.10), "ครีมทราย": (0.86, 0.75, 0.56),
    "ขาวประกาย": (0.86, 0.83, 0.77), "เขียวหยก": (0.56, 0.68, 0.50),
    "เขียวมรกต": (0.33, 0.55, 0.35), "เทาดำ": (0.30, 0.31, 0.34),
    "ตามวัสดุ": None,
}


def tile_color(s):
    _c, spec = roof_tile(s)
    return TILE_COLORS.get((s or {}).get("tile_color") or "ตามวัสดุ") \
        or spec["color"]


#: Roof accessories (SCG / CPAC style pieces): key → Thai name.
ACCESSORIES = {
    "ridge": "ครอบสันโค้ง", "verge": "ครอบข้าง",
    "gable_end": "ครอบโค้งปิดจั่ว", "verge_end": "ครอบข้างปิดชาย",
    "hip_end": "ครอบโค้งหางมน", "two_way": "ครอบโค้งสองทาง",
    "three_way": "ครอบโค้งสามทาง", "four_way": "ครอบโค้งสี่ทาง",
}
