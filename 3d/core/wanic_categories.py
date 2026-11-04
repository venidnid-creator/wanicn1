# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
"""The 15 หมวดงาน of a building BOQ, the way an estimator files the work.

Every BOQ line, every generated part and every layer belongs to one of
them: 1 งานเตรียมพื้นที่ … 15 งานอื่นๆ. :func:`line_category` reads a bill
line (its หมวด by the 2569 rules and its description) and
:func:`kind_category` reads a generated part's kind.
"""
from __future__ import annotations

#: (เลขหมวด, ชื่อหมวด, ไอคอน, ตัวอย่างงาน)
CATEGORIES = (
    (1, "งานเตรียมพื้นที่", "🚧", "ถางป่า ขุดตอ ปรับพื้นที่ รั้วชั่วคราว ผังอาคาร"),
    (2, "งานดิน", "⛏️", "ขุดดิน ถมดิน ทรายรองพื้น บดอัด"),
    (3, "งานฐานราก", "🧱", "เสาเข็ม ฐานราก ตอม่อ คอนกรีตหยาบ"),
    (4, "งานโครงสร้างคอนกรีต", "🏗️", "เสา คาน พื้น บันได ค.ส.ล. ไม้แบบ เหล็กเสริม"),
    (5, "งานโครงสร้างเหล็ก", "🔩", "โครงหลังคาเหล็ก อกไก่ จันทัน แป ดั้ง อะเส สีกันสนิม"),
    (6, "งานผนัง/ฉาบ", "🧰", "ก่อผนัง เสาเอ็น ทับหลัง ฉาบปูน บุกระเบื้องผนัง"),
    (7, "งานหลังคา", "🏠", "มุงกระเบื้อง ครอบ เชิงชาย ปั้นลม รางน้ำ ฉนวน"),
    (8, "งานประตูหน้าต่าง", "🚪", "วงกบ บานประตู หน้าต่าง กระจก อุปกรณ์"),
    (9, "งานสี", "🎨", "สีน้ำอะครีลิค สีน้ำมัน สีย้อมไม้"),
    (10, "งานพื้น/ฝ้า", "🔲", "ปูกระเบื้อง เทปูนทราย ฝ้าเพดาน ฝ้าชายคา บัว"),
    (11, "งานสุขาภิบาล", "🚿", "สุขภัณฑ์ ท่อประปา ท่อน้ำทิ้ง ถังบำบัด"),
    (12, "งานไฟฟ้า", "💡", "สายไฟ ท่อร้อยสาย ดวงโคม เต้ารับ ตู้ไฟ"),
    (13, "งานปรับอากาศ", "❄️", "เครื่องปรับอากาศ ท่อน้ำยา พัดลมระบายอากาศ"),
    (14, "งานภายนอก", "🌳", "ถนน ทางเท้า รางระบายน้ำ รั้ว ภูมิทัศน์"),
    (15, "งานอื่นๆ", "📦", "งานเบ็ดเตล็ด"),
    # after the work: what the price is built differently for (หลักเกณฑ์
    # 2569 · ปร.2) — bought equipment carries VAT, not Factor F; equipment
    # made on site is construction (× F); supplies and durables are bought
    # as they are (no F)
    (16, "ครุภัณฑ์จัดซื้อ", "🛒", "ครุภัณฑ์ที่ซื้อสำเร็จ · บวกภาษีมูลค่าเพิ่ม 7% ไม่คูณ Factor F (ปร.2)"),
    (17, "ครุภัณฑ์จัดจ้าง", "🛠️", "ครุภัณฑ์ที่จ้างทำ/ติดตั้งในงาน · คูณ Factor F เหมือนค่างาน"),
    (18, "วัสดุ", "🧺", "วัสดุสิ้นเปลืองที่จัดหาให้ · ไม่คูณ Factor F"),
    (19, "วัสดุคงทน", "🪑", "วัสดุคงทนที่จัดหาให้ · ไม่คูณ Factor F"),
)
#: หมวด whose price is NOT multiplied by Factor F (shown in ปร.4 row 2,
#: ค่าครุภัณฑ์จัดซื้อ) and those that add VAT on top of the price.
NO_F = (16, 18, 19)
ADD_VAT = (16,)
EXTRA = (16, 17, 18, 19)
NAME = {no: name for no, name, _i, _e in CATEGORIES}
ICON = {no: icon for no, _n, icon, _e in CATEGORIES}


def title(no: int) -> str:
    """«4. งานโครงสร้างคอนกรีต»"""
    return f"{no}. {NAME.get(no, NAME[15])}"


def layer_title(no: int) -> str:
    """A layer name that sorts in หมวด order: «04 งานโครงสร้างคอนกรีต»."""
    return f"{no:02d} {NAME.get(no, NAME[15])}"


def line_category(group: str, desc: str) -> int:
    """The หมวดงาน of a bill line from its 2569-rules หมวด (``group`` of
    :mod:`core.wanic_quantities`) and its description."""
    d = desc or ""
    if any(w in d for w in ("ทาสี", "สีน้ำ", "สีน้ำมัน", "สีย้อม")) and \
            "กันสนิม" not in d:
        return 9
    if group == "earth":
        if any(w in d for w in ("ขุดดิน", "ดินถม", "ถมดิน", "ทรายถม", "ทรายรอง",
                                "บดอัด", "กลบ")):
            return 2
        if any(w in d for w in ("ถาง", "ปรับพื้นที่", "ผังอาคาร", "รั้วชั่วคราว")):
            return 1
        return 3
    if group == "column":
        return 3 if "ตอม่อ" in d else 4
    if group in ("beam", "slab", "stair", "rebar"):
        return 4
    if group == "wall":
        return 6
    if group == "opening":
        return 8
    if group == "sanitary":
        return 11
    if group == "finish":
        return 10
    if group == "roof":
        if "ฝ้า" in d:
            return 10
        if any(w in d for w in ("โครงหลังคาเหล็ก", "เหล็กรูปพรรณ", "กันสนิม",
                                "อะเส", "ดั้ง", "จันทัน", "แป ", "อกไก่",
                                "ตะเฆ่", "ขื่อ")) and "กระเบื้อง" not in d:
            return 5
        return 7
    if group == "prep":
        return 1
    if group == "plumbing":
        return 11
    if group == "misc":
        return 15
    if group in ("electric",):
        return 12
    if group in ("hvac",):
        return 13
    if group in ("site", "external"):
        return 14
    return 15


#: generated part kind → หมวดงาน
KIND_CATEGORY = {
    "footing": 3, "pile": 3, "stump": 3,
    "column": 4, "beam": 4, "slab": 4, "stair": 4, "band": 6,
    "ridge": 5, "hip": 5, "rafter": 5, "purlin": 5, "post": 5, "valley": 5,
    "wallplate": 5, "tiebeam": 5, "brace": 5, "headplate": 5, "rbeam": 5, "strut": 5,
    "wall": 6, "plaster": 6,
    "skin": 7, "tiles": 7, "cap": 7, "fascia": 7, "barge": 7, "gutter": 7,
    "door": 8, "window": 8,
    "soffit": 10, "soffit_frame": 10, "ceiling": 10, "ceiling_frame": 10, "soffit_fix": 10,
    "skirting": 10, "cornice": 10, "light": 12, "outlet": 12, "ac": 13,
    "ac_out": 13, "panel": 12, "ground_rod": 12, "fan": 13,
    "pipe_supply": 11, "pipe_drain": 11, "septic": 11, "grease": 11, "meter": 11,
    "walkway": 14, "drain_ring": 14, "drain_pipe": 14, "manhole": 14, "ac_bracket": 13, "sign": 15,
    "fixture": 11,
}


def kind_category(kind: str) -> int:
    return KIND_CATEGORY.get(kind or "", 15)
