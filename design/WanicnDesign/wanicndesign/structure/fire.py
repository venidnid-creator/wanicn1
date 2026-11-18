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
    refs: str = "MR2566-23"


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
