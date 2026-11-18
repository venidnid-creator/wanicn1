# -*- coding: utf-8 -*-
"""Fire resistance of the main structure — กฎกระทรวง พ.ศ. 2566 ข้อ 21–24
[MR2566-23].

ข้อ 21: a building higher than three storeys — the fire escape parts and the
main structure are of non-combustible material.

ข้อ 22: these buildings need a fire-resistance rating of the main structure:
(1) warehouses, theatres, hotels, condominiums, hospitals; (2) commercial,
industrial, education and public health buildings with more than 1,000 m²
in all or on one floor; (3) offices of three storeys or more with more than
1,000 m²; (4) high-rise and large buildings and assembly halls.

ข้อ 23: floors 1–4 counted from the top 1 hour (2 hours for fuel stores,
high-rise buildings, theatres, hospitals, public health and education
buildings); floors 5–14 2 hours; from the 15th down and basements 3 hours
for columns, walls and beams, 2 hours for slabs; the roof structure 1 hour
unless the building has no more than 1,000 m² (not a theatre, hospital or
assembly hall), or the roof is more than 8 m above the floor with
sprinklers or heat protection. ข้อ 24: the concrete cover for the rating
follows the Minister's announcement.

What the program cannot know (fuel storage, sprinklers, the full
definitions of high-rise and large buildings) is left to the designer;
the program only flags buildings 23 m or higher as high-rise.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

HIGH_RISE = 23.0                   # m — the usual definition of อาคารสูง (to be confirmed by the designer)
GROUP_1 = {"industrial", "assembly", "apartment", "hospital"}
GROUP_2 = {"commercial", "industrial", "school", "hospital"}
TWO_HOURS_TOP = {"assembly", "hospital", "school"}


@dataclass
class FireResult:
    storeys: int
    area: float
    height: float
    applies: bool
    reasons: list = field(default_factory=list)
    floors: list = field(default_factory=list)     # (level, hours columns/beams, hours slab)
    roof_hours: float = 0.0
    notes: list = field(default_factory=list)
    refs: str = "MR2566-23, MI2567-32"


def requirements(b) -> FireResult:
    floors = [lv for lv in b.levels if lv.slab in ("suspended", "on_ground")]
    storeys = len(floors)
    plan = b.xs[-1] * b.ys[-1]
    area = plan * max(1, storeys)
    height = b.levels[-1].elevation - b.levels[0].elevation if b.levels else 0.0
    use = b.occupancy
    reasons = []
    if use in GROUP_1:
        reasons.append("ข้อ 22 (1) คลังสินค้า โรงมหรสพ โรงแรม อาคารชุด หรือสถานพยาบาล")
    if use in GROUP_2 and (area > 1000 or plan > 1000):
        reasons.append("ข้อ 22 (2) อาคารพาณิชยกรรม อุตสาหกรรม การศึกษา การสาธารณสุข พื้นที่เกิน 1,000 ตร.ม.")
    if use == "office" and storeys >= 3 and (area > 1000 or plan > 1000):
        reasons.append("ข้อ 22 (3) สำนักงานสูงตั้งแต่สามชั้น พื้นที่เกิน 1,000 ตร.ม.")
    high = height >= HIGH_RISE
    if high or use == "assembly":
        reasons.append("ข้อ 22 (4) อาคารสูง/อาคารขนาดใหญ่/หอประชุม")
    out = FireResult(storeys, area, height, bool(reasons), reasons)
    if storeys > 3:
        out.notes.append("ข้อ 21 อาคารสูงเกินสามชั้น: ส่วนประกอบของช่องทางหนีไฟและโครงสร้างหลักต้องเป็นวัสดุไม่ติดไฟ")
    if not out.applies:
        out.notes.append("ไม่เข้าข่ายข้อ 22 จากข้อมูลในโปรแกรม (ผู้ออกแบบต้องยืนยันประเภทและขนาดอาคาร)")
        return out
    top_hours = 2.0 if (use in TWO_HOURS_TOP or high) else 1.0
    for k, lv in enumerate(reversed(floors)):
        n = k + 1                                    # 1 = top floor
        if n <= 4:
            out.floors.append((lv.name, top_hours, top_hours))
        elif n <= 14:
            out.floors.append((lv.name, 2.0, 2.0))
        else:
            out.floors.append((lv.name, 3.0, 2.0))
    roof_free = area <= 1000 and use not in ("assembly", "hospital")
    out.roof_hours = 0.0 if roof_free else 1.0
    if roof_free:
        out.notes.append("หลังคาไม่ต้องมีอัตราการทนไฟ (ข้อ 23 (4) (ก) พื้นที่รวมไม่เกิน 1,000 ตร.ม.)")
    else:
        out.notes.append("โครงหลังคาต้องทนไฟ 1 ชม. เว้นแต่สูงจากพื้นเกิน 8 ม. และมีระบบดับเพลิงอัตโนมัติ (ข้อ 23 (4) (ข))")
    out.notes.append("ระยะหุ้มคอนกรีตให้ได้อัตราการทนไฟตามที่รัฐมนตรีประกาศ (ข้อ 24)")
    return out


#: ประกาศ มท. 2567 ข้อ 32 ตาราง 17: least thickness for 1/2/3 hours, mm (slabs and walls, columns).
MIN_THICKNESS = {1: (80, 200), 2: (115, 250), 3: (145, 280)}
#: ตาราง 18 (selected rows), cover to the reinforcement for 1/2/3 hours, mm.
COVER_COLUMN = {1: 40, 2: 50, 3: 50}          # columns with the least side 300 mm or more


def check_members(res) -> list[str]:
    """Compare the designed slabs and columns with ตาราง 17 and the column
    covers with ตาราง 18 for the ratings of ข้อ 23 [MI2567-32]; failing
    members are marked."""
    f = res.fire
    if f is None or not f.applies:
        return []
    from .rules import column_cover
    out = []
    hours = {name: int(math.ceil(h)) for name, h, _s in f.floors}
    names = [lv.name for lv in res.building.levels]
    for s in res.slabs:
        h = hours.get(s.level)
        if h and s.kind != "on-ground" and s.thickness * 1000 + 1e-6 < MIN_THICKNESS[h][0]:
            s.ok = False
            s.note = (s.note + " ; " if s.note else "") + f"ทนไฟ {h} ชม. ต้องหนา ≥ {MIN_THICKNESS[h][0]} มม."
    for c in res.columns:
        top = next((n for n in names if c.segment.endswith(n)), None)
        h = hours.get(top)
        if not h:
            continue
        need = MIN_THICKNESS[h][1]
        if min(c.b, c.h) * 1000 + 1e-6 < need:
            c.ok = False
            c.note = (c.note + " ; " if c.note else "") + f"ทนไฟ {h} ชม. ด้านแคบต้อง ≥ {need} มม."
    cov = column_cover(res.concrete) * 10
    for h in sorted(set(hours.values())):
        if cov + 1e-6 < COVER_COLUMN[h]:
            out.append(f"ทนไฟ {h} ชม.: ระยะหุ้มเสาต้อง ≥ {COVER_COLUMN[h]} มม. (ใช้อยู่ {cov:.0f} มม.) — ตาราง 18")
    out.append("ระยะหุ้มคาน พื้น เพื่อการทนไฟ ตามตาราง 18 (คาน/พื้น 20 มม. สำหรับ 1 ชม.; 2–3 ชม. ขึ้นกับความกว้าง"
               "และการยึดรั้ง) ไม่น้อยกว่าตาราง 13")
    f.notes += out
    return out
