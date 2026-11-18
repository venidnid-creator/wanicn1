# -*- coding: utf-8 -*-
"""Standards and sources behind every value and formula.

Each reference has a ``status``:

* ``"document"`` — the value was read from a document the user supplied
  (the 2569 criteria, ว480, the QuickDesign manual);
* ``"recall"`` — written from the standard as commonly published, not
  from a copy in this project. Check these against the official edition
  before the results are used for a permit;
* ``"project"`` — data that must come from the project itself (soil
  investigation, pile load tests).

The calculation report lists every reference used, with its status, and
every result row names the references it rests on.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Ref:
    code: str
    title: str
    clause: str
    status: str            # "document" or "recall"

    @property
    def label(self) -> str:
        return f"{self.title} {self.clause}".strip()


REFS = {
    # --- loads ---------------------------------------------------------------
    "MR6-15": Ref("MR6-15", "กฎกระทรวง ฉบับที่ 6 (พ.ศ. 2527) ออกตามความใน พ.ร.บ.ควบคุมอาคาร พ.ศ. 2522",
                  "ข้อ 15 น้ำหนักบรรทุกจรตามประเภทการใช้อาคาร", "recall"),
    "MR6-16": Ref("MR6-16", "กฎกระทรวง ฉบับที่ 6 (พ.ศ. 2527)",
                  "ข้อ 16 การลดน้ำหนักบรรทุกจรสำหรับเสา ตอม่อ และฐานราก", "recall"),
    "MR6-21": Ref("MR6-21", "กฎกระทรวง ฉบับที่ 6 (พ.ศ. 2527)",
                  "หน่วยแรงที่ยอมให้ของคอนกรีตและเหล็กเสริม (fc ≤ 0.375 fc' ไม่เกิน 65 ksc, "
                  "fs ≤ 0.5 fy ไม่เกิน 1,500 ksc)", "recall"),
    "UNIT-WT": Ref("UNIT-WT", "หน่วยน้ำหนักวัสดุที่ใช้ทั่วไปในการออกแบบ",
                   "คอนกรีตเสริมเหล็ก 2,400 กก./ลบ.ม.", "recall"),
    "QD-WALL": Ref("QD-WALL", "คู่มือ QuickDesign ภาคผนวก / เมนู Draw Wall",
                   "น้ำหนักผนัง อิฐ 180, บล็อกเบา 90, ยิปซัม 40, คอนกรีต 10 ซม. 240 กก./ตร.ม.", "document"),
    "QD-ROOF": Ref("QD-ROOF", "คู่มือ QuickDesign ภาคผนวก Roof Calculation",
                   "น้ำหนักวัสดุมุง กระเบื้องคอนกรีต 50, กระเบื้องลอน 30, เหล็กแผ่น 20 กก./ตร.ม.", "document"),
    # --- reinforced concrete, working stress design ----------------------------
    "EIT1007": Ref("EIT1007", "มาตรฐาน วสท. 1007-34 อาคารคอนกรีตเสริมเหล็ก โดยวิธีหน่วยแรงใช้งาน",
                   "หน่วยแรงที่ยอมให้ fc = 0.45 fc', fs: SR24 1,200 / SD30 1,500 / SD40 1,700 ksc", "recall"),
    "EIT1007-SHEAR": Ref("EIT1007-SHEAR", "มาตรฐาน วสท. 1007-34",
                         "แรงเฉือนที่คอนกรีตรับในคาน vc = 0.29√fc', ระยะเหล็กปลอกไม่เกิน d/2", "recall"),
    "EIT1007-MIN": Ref("EIT1007-MIN", "มาตรฐาน วสท. 1007-34",
                       "เหล็กเสริมน้อยที่สุดในคาน As ≥ 14/fy · bd (หรือ 4/3 ของที่ต้องการ)", "recall"),
    "EIT1007-SLAB": Ref("EIT1007-SLAB", "มาตรฐาน วสท. 1007-34 / ACI 318-63 วิธีที่ 2",
                        "ตารางสัมประสิทธิ์โมเมนต์พื้นสองทาง กรณี 1–5 และการถ่ายน้ำหนัก wS/3, "
                        "wS/3·(3−m²)/2", "recall"),
    "QD-SLAB5": Ref("QD-SLAB5", "คู่มือ QuickDesign ภาคผนวก Slab Calculation",
                    "สัมประสิทธิ์กรณี 5 (ไม่ต่อเนื่อง 4 ด้าน) พื้นทางเดียวเมื่อ m < 0.5", "document"),
    "EIT1007-TEMP": Ref("EIT1007-TEMP", "มาตรฐาน วสท. 1007-34",
                        "เหล็กเสริมกันร้าวในพื้น: เหล็กกลม 0.0025 bt, ระยะห่างไม่เกิน 3t หรือ 45 ซม.", "recall"),
    "EIT1007-DEFL": Ref("EIT1007-DEFL", "มาตรฐาน วสท. 1007-34 / ACI 318",
                        "ความลึกน้อยที่สุดของคานเมื่อไม่ตรวจการแอ่นตัว L/16, L/18.5, L/21, L/8 "
                        "คูณ (0.4 + fy/7000)", "recall"),
    "EIT1007-COL": Ref("EIT1007-COL", "มาตรฐาน วสท. 1007-34 (เสาปลอกเดี่ยว รับแรงตามแกน)",
                       "P = 0.85 Ag (0.25 fc' + fs pg), fs = 0.4 fy ≤ 2,100 ksc, pg 1%–8%", "recall"),
    "EIT1007-TIE": Ref("EIT1007-TIE", "มาตรฐาน วสท. 1007-34",
                       "ระยะเหล็กปลอกเสาไม่เกิน 16 เท่าเหล็กยืน 48 เท่าเหล็กปลอก หรือด้านแคบของเสา", "recall"),
    "EIT1007-FOOT": Ref("EIT1007-FOOT", "มาตรฐาน วสท. 1007-34",
                        "แรงเฉือนทะลุ vp = 0.53√fc' ที่ระยะ d/2, แรงเฉือนทางเดียว 0.29√fc' ที่ระยะ d", "recall"),
    # --- steel -----------------------------------------------------------------
    "QD-PURLIN": Ref("QD-PURLIN", "คู่มือ QuickDesign เมนู Design Purlin",
                     "Mx = w cosθ L²/8, My = w sinθ L²/8, Fb = 1,400 ksc, การแอ่นตัว L/240", "document"),
    "AISC-ASD": Ref("AISC-ASD", "AISC ASD / มาตรฐาน วสท. 1003 อาคารเหล็กรูปพรรณ",
                    "หน่วยแรงดัดที่ยอมให้ 0.6 Fy, E = 2,040,000 ksc", "recall"),
    "STEEL-TABLE": Ref("STEEL-TABLE", "ตารางเหล็กตัวซี (data/steel_sections.json)",
                       "ค่าที่ระบุ manual มาจากตารางในคู่มือเดิม ค่า approx เป็นค่าประมาณ", "document"),
    # --- foundations -----------------------------------------------------------
    "QD-PILE": Ref("QD-PILE", "คู่มือ QuickDesign ภาคผนวก Footing Calculation",
                   "น้ำหนักบรรทุกปลอดภัยของเสาเข็มตามชนิดและขนาด (ใช้ประมาณการเท่านั้น)", "document"),
    "SOIL": Ref("SOIL", "ผลเจาะสำรวจดินและผลทดสอบเสาเข็มของโครงการ",
                "ต้องใช้ค่ารับน้ำหนักจริงแทนค่าในตาราง", "project"),
    # --- quantities and prices ---------------------------------------------------
    "CGD2569": Ref("CGD2569", "กรมบัญชีกลาง หลักเกณฑ์การคำนวณราคากลางงานก่อสร้าง (2569)",
                   "ส่วนที่ 4 การคำนวณปริมาณงานและการเผื่อ งานอาคาร", "document"),
    "W480": Ref("W480", "หนังสือกรมบัญชีกลาง ที่ กค 0433.2/ว 480 (26 มิ.ย. 2569)",
                "บัญชีค่าแรงงาน/ดำเนินการสำหรับถอดแบบคำนวณราคากลาง", "document"),
}

#: Live load, kg/m², by use — กฎกระทรวง ฉบับที่ 6 ข้อ 15 (as commonly published).
LIVE_LOADS = [
    ("roof", "หลังคา", 30),
    ("canopy", "กันสาดหรือหลังคาคอนกรีต", 100),
    ("house", "ที่พักอาศัย โรงเรียนอนุบาล ห้องน้ำ ห้องส้วม", 150),
    ("apartment", "ห้องแถว ตึกแถว อาคารชุด หอพัก โรงแรม ห้องคนไข้พิเศษ", 200),
    ("office", "สำนักงาน ธนาคาร", 250),
    ("commercial", "อาคารพาณิชย์ มหาวิทยาลัย วิทยาลัย โรงเรียน โรงพยาบาล", 300),
    ("assembly", "ตลาด ห้างสรรพสินค้า หอประชุม โรงมหรสพ ภัตตาคาร ห้องสมุด ที่จอดรถ", 400),
    ("industrial", "คลังสินค้า โรงกีฬา พิพิธภัณฑ์ อัฒจันทร์ โรงงานอุตสาหกรรม โรงพิมพ์ ห้องเก็บเอกสาร", 500),
    ("archive", "ห้องเก็บหนังสือของห้องสมุด", 600),
]
LIVE_LOAD = {k: v for k, _t, v in LIVE_LOADS}

#: Uses where ข้อ 16 does not allow the live load reduction (as commonly read).
NO_REDUCTION = {"assembly", "industrial", "archive"}

#: Live load reduction by the floor's place counted down from the roof
#: (0 = roof, 1 = first floor below the roof, …) — ข้อ 16.
LL_REDUCTION = [0.0, 0.0, 0.10, 0.20, 0.30, 0.40, 0.50]


def ll_reduction(floors_from_roof: int) -> float:
    return LL_REDUCTION[min(floors_from_roof, len(LL_REDUCTION) - 1)]


STATUS_TEXT = {
    "document": "จากเอกสารที่ได้รับ",
    "recall": "จากมาตรฐานที่เผยแพร่ทั่วไป ต้องตรวจกับฉบับจริงก่อนใช้ขออนุญาต",
    "project": "ต้องใช้ข้อมูลจริงของโครงการ",
}


def cite(*codes: str) -> str:
    """Short reference list for a result row: ``"EIT1007, MR6-15"``."""
    return ", ".join(c for c in codes if c in REFS)


def used(codes) -> list[Ref]:
    seen = []
    for c in codes:
        for part in str(c).split(","):
            part = part.strip()
            if part in REFS and REFS[part] not in seen:
                seen.append(REFS[part])
    return seen
