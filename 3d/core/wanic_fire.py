# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
"""การทนไฟของโครงสร้างหลัก — กฎกระทรวง พ.ศ. 2566 ข้อ 21–24 and ประกาศ
กระทรวงมหาดไทย 2567 ข้อ 32 ตาราง 17–18 (ข12, from WanicnDesign).

ข้อ 21: higher than three storeys — the fire escape parts and the main
structure non-combustible. ข้อ 22: a fire-resistance rating is needed for
(1) warehouses, theatres, hotels, condominiums, hospitals; (2) commercial,
industrial, education and public-health buildings over 1,000 m² in all or
on one floor; (3) offices of three storeys or more over 1,000 m²; (4)
high-rise and large buildings and assembly halls. ข้อ 23: floors 1–4 from
the top 1 hour (2 hours for theatres, hospitals, schools, high-rise),
5–14 two hours, 15 and lower three hours for columns and beams (slabs 2);
the roof 1 hour unless the building is no more than 1,000 m². ข้อ 24: the
cover by the Minister's announcement (ตาราง 18).

What the program cannot know (fuel stores, sprinklers, the full meaning of
high-rise and large buildings) stays the designer's; 23 m or higher is
taken as high-rise.
"""
from __future__ import annotations

import math

HIGH_RISE = 23.0
#: the uses of calc["use"] (wanic_calc.OCCUPANCY) in ข้อ 22 (1) / (2) and the 2-hour top floors
GROUP_1 = {"warehouse", "assembly", "condo", "hospital"}
GROUP_2 = {"retail", "shophouse", "warehouse", "school", "hospital"}
TWO_HOURS_TOP = {"assembly", "hospital", "school"}
#: ตาราง 17: the least thickness for 1 / 2 / 3 hours, mm — (slabs and walls, columns)
MIN_THICKNESS = {1: (80, 200), 2: (115, 250), 3: (145, 280)}
#: ตาราง 18 (selected rows): the cover to the column bars for 1 / 2 / 3 hours, mm
COVER_COLUMN = {1: 40, 2: 50, 3: 50}


def requirements(data) -> dict:
    """{"applies", "reasons", "hours": {floor: h}, "roof", "notes", "storeys", "area", "height", "use"}
    — floor 0 is the ground floor."""
    from core import wanic_building as B
    from core import wanic_calc as C
    E = B.elements(data or {})
    b_ = C.basis(data or {})
    n = int(E["n"])
    use = str(b_.get("use") or "")
    xs = [r["x"] for f in E["floors"] for r in f["rooms"]] + [r["x"] + r["w"] for f in E["floors"] for r in f["rooms"]]
    ys = [r["y"] for f in E["floors"] for r in f["rooms"]] + [r["y"] + r["d"] for f in E["floors"] for r in f["rooms"]]
    plan = (max(xs) - min(xs)) * (max(ys) - min(ys)) if xs else 0.0
    area = sum(r["w"] * r["d"] for f in E["floors"] for r in f["rooms"])
    height = n * float(E["H"])
    reasons = []
    if use in GROUP_1:
        reasons.append("ข้อ 22 (1) คลังสินค้า โรงมหรสพ โรงแรม อาคารชุด หรือสถานพยาบาล")
    if use in GROUP_2 and (area > 1000 or plan > 1000):
        reasons.append("ข้อ 22 (2) อาคารพาณิชยกรรม อุตสาหกรรม การศึกษา การสาธารณสุข พื้นที่เกิน 1,000 ตร.ม.")
    if use == "office" and n >= 3 and (area > 1000 or plan > 1000):
        reasons.append("ข้อ 22 (3) สำนักงานสูงตั้งแต่สามชั้น พื้นที่เกิน 1,000 ตร.ม.")
    high = height >= HIGH_RISE
    if high or use == "assembly":
        reasons.append("ข้อ 22 (4) อาคารสูง (≥ 23 ม.) / อาคารขนาดใหญ่ / หอประชุม")
    out = {"applies": bool(reasons), "reasons": reasons, "hours": {}, "roof": 0.0, "notes": [],
           "storeys": n, "area": area, "height": height, "use": use}
    if n > 3:
        out["notes"].append("ข้อ 21 อาคารสูงเกินสามชั้น: ช่องทางหนีไฟและโครงสร้างหลักต้องเป็นวัสดุไม่ติดไฟ")
    if not reasons:
        out["notes"].append("ไม่เข้าข่ายข้อ 22 ตามประเภทการใช้อาคาร พื้นที่ และความสูงในโปรแกรม "
                            "(ผู้ออกแบบต้องยืนยันประเภทและขนาดอาคาร)")
        return out
    top = 2 if (use in TWO_HOURS_TOP or high) else 1
    for f in range(n):
        k = n - f                                     # 1 = the top floor
        out["hours"][f] = top if k <= 4 else (2 if k <= 14 else 3)
    roof_free = area <= 1000 and use not in ("assembly", "hospital")
    out["roof"] = 0.0 if roof_free else 1.0
    out["notes"].append("หลังคาไม่ต้องมีอัตราการทนไฟ (ข้อ 23 (4) (ก) พื้นที่รวมไม่เกิน 1,000 ตร.ม.)" if roof_free else
                        "โครงหลังคาต้องทนไฟ 1 ชม. เว้นแต่สูงจากพื้นเกิน 8 ม. และมีระบบดับเพลิงอัตโนมัติ (ข้อ 23 (4) (ข))")
    out["notes"].append("ระยะหุ้มคอนกรีตตามตาราง 18 (ข้อ 24): คาน/พื้น 20 มม. สำหรับ 1 ชม.; 2–3 ชม. ขึ้นกับความกว้างและการยึดรั้ง")
    return out


def checks(data, cover_col_m: float = 0.035) -> list:
    """[(group, mark, floor, name, need mm, have mm, text)] — the slabs and
    columns under the rating's least size (ตาราง 17) and the column cover
    (ตาราง 18); [] when the building needs no rating."""
    from core import wanic_building as B
    req = requirements(data)
    if not req["applies"]:
        return []
    E = B.elements(data or {})
    lib = E["lib"]
    out, seen = [], set()
    for sl in E["slabs"]:
        sp = lib.get(sl["mark"], {})
        f = int(sl.get("floor", 0))
        if sl.get("ground") or sp.get("ground"):
            continue
        h = req["hours"].get(f)                       # the floor slab of storey f
        t = (float(sp.get("topping") or 0.05) + 0.05) if B.is_precast(sp) else float(sp.get("t", 0.10))
        need = MIN_THICKNESS[h][0] if h else 0
        if h and t * 1000 + 1e-6 < need and (sl["mark"], h) not in seen:
            seen.add((sl["mark"], h))
            out.append(("slab", sl["mark"], f, "พื้น", need, t * 1000,
                        f"ทนไฟ {h} ชม. ต้องหนา ≥ {math.ceil(need / 10)} ซม. (ตาราง 17)"))
    for c in E["columns"]:
        sp = lib.get(c["mark"], {})
        f = int(c.get("floor", 0))
        h = req["hours"].get(f)
        if not h:
            continue
        side = min(float(sp.get("b", 0.2)), float(sp.get("h", 0.2))) * 1000
        need = MIN_THICKNESS[h][1]
        if side + 1e-6 < need and (c["mark"], h) not in seen:
            seen.add((c["mark"], h))
            out.append(("column", c["mark"], f, "เสา", need, side,
                        f"ทนไฟ {h} ชม. ด้านแคบต้อง ≥ {need / 10:.0f} ซม. (ตาราง 17)"))
    from core import wanic_rc as R
    for kind, rows in (("stump", E["stumps"]), ("column", E["columns"])):
        for c in rows:
            sp = lib.get(c["mark"], {})
            f = max(int(c.get("floor", 0)), 0)
            h = req["hours"].get(f)
            if not h:
                continue
            have = R.cover_of(sp, kind) * 1000
            if have + 1e-6 < COVER_COLUMN[h] and (c["mark"], "cover", h) not in seen:
                seen.add((c["mark"], "cover", h))
                out.append(("cover", c["mark"], f, "ระยะหุ้มเสา", COVER_COLUMN[h], have,
                            f"ทนไฟ {h} ชม. ระยะหุ้มเหล็กต้อง ≥ {COVER_COLUMN[h] / 10:.0f} ซม. (ตาราง 18)"))
    return out
