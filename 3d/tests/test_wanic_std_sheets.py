# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
"""A-01 / A-02 laid out like the standard house drawing sets."""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(__file__))

from core import wanic_drawings as D  # noqa: E402
from test_wanic_drawings import INFO, house  # noqa: E402


def _sheets():
    return {s.title: s for s in D.build_set(house(), INFO, ("A",))}


def test_a01_three_panels_and_material_codes():
    S = _sheets()
    a01 = S["สารบัญแบบ รายการวัสดุ"]
    assert a01.code == "A-01"
    t = a01.texts()
    for head in ("รายการแบบสถาปัตยกรรม (A)", "รายการวัสดุ", "รายการสัญลักษณ์ประกอบแบบ",
                 "พื้น", "ผนัง", "ฝ้าเพดาน", "บัวเชิงผนัง", "มอบฝ้าเพดาน", "หลังคา"):
        assert head in t, head
    assert "A-02" in t and "รายการประกอบแบบ" in t           # the sheet list
    assert any(D.WALL_TYPES[1] in x for x in t)
    assert "รายการวัสดุประกอบแบบ" not in S                  # folded into A-01


def test_a02_specification_and_cp874():
    S = _sheets()
    a02 = S["รายการประกอบแบบ"]
    assert a02.code == "A-02"
    t = " ".join(a02.texts())
    for k in ("วัตถุประสงค์", "การวางผังและระดับ", "งานพื้น", "งานผนัง", "งานฝ้าเพดาน", "งานหลังคา",
              "งานสี", "มอก. 2508-2555", "งานวิศวกรรมไฟฟ้า", "อักษรย่อ"):
        assert k in t, k
    for s in (S["สารบัญแบบ รายการวัสดุ"], a02):
        for x in s.texts():
            D.dxf_text(x).encode("cp874")                      # DXF-safe text only


def test_door_window_cards_like_the_standard():
    S = _sheets()
    cards = next(s for t, s in S.items() if t.startswith("แบบขยายประตู แบบขยายหน้าต่าง"))
    t = cards.texts()
    for k in ("ชนิดบาน", "วงกบ", "กรอบบาน", "บาน", "อุปกรณ์", "จำนวน", "หมายเหตุ", "ป1", "น1"):
        assert k in t, k
    assert any(x.startswith("ติดตั้งบริเวณ") for x in t)
    for x in t:
        D.dxf_text(x).encode("cp874")


def test_slab_joint_and_stair_flight_sheets():
    """The standard's S-16 (slab sections, column joints, the rib) and one RC
    stair flight a sheet, with their bars and sizes."""
    sheets = D.build_set(house(), INFO)
    sl = next(s for s in sheets if s.title == "รายละเอียดพื้น รอยต่อเสา ครีบ คสล.")
    t = " ".join(sl.texts())
    assert "(ด้านสั้น)" in t and "รอยต่อเสา" in t and "แบบขยายครีบ คสล. รอบอาคาร" in t
    fl = [s for s in sheets if s.title.startswith("รายละเอียดบันได คสล.")]
    for s in fl:
        t = " ".join(s.texts())
        assert "เหล็กหลัก" in t and "ทุกมุม" in t and "@" in t


def test_sn_index_symbols_and_specification():
    """SN-01 as the standard (sheet list, pipe types, drawn symbols) and the
    specification on SN-02, SN-03 with the design values."""
    sheets = [s for s in D.build_set(house(), INFO) if s.group == "SN"]
    assert [s.title for s in sheets[:3]] == ["สารบัญแบบและสัญลักษณ์ระบบสุขาภิบาล",
                                             "รายการประกอบแบบ (แผ่นที่ 1)", "รายการประกอบแบบ (แผ่นที่ 2)"]
    t = " ".join(sheets[0].texts())
    for w in ("ชนิดท่อที่ใช้ในการก่อสร้าง", "สัญลักษณ์ประกอบแบบระบบสุขาภิบาล", "ประตูน้ำ (GATE VALVE)", "SN-03"):
        assert w in t, w
    assert "ข้อมูลการออกแบบ" in " ".join(sheets[2].texts())


def test_sn_riser_and_floor_plans():
    """SN-04 the riser diagram and the floor plans as the standard: the drain
    round the building, the tanks, the meter, the stacks upstairs."""
    sheets = {s.title: s for s in D.build_set(house(), INFO) if s.group == "SN"}
    t = " ".join(sheets["ไดอะแกรมระบบสุขาภิบาลแนวดิ่ง"].texts())
    assert 'Ø4"SW' in t and "VTR" in t and "BP" in t and "ระดับพื้นชั้น 1" in t
    g = " ".join(sheets["แปลนระบบสุขาภิบาลชั้น 1"].texts())
    assert "ลาด 1 : 200" in g and "ถังบำบัดน้ำเสีย" in g and "มาตรวัดน้ำ" in g
    up = [k for k in sheets if k.startswith("แปลนระบบสุขาภิบาลชั้น") and not k.endswith("1")]
    for k in up:
        assert "ท่อโสโครกแนวดิ่ง" in " ".join(sheets[k].texts()) or "ห้องน้ำ" not in " ".join(sheets[k].texts())


def test_sn_bathrooms_details_and_hangers():
    """SN-07..SN-10 as the standard: the bathrooms at 1:50 with the branch
    sizes, the fixture and drain details, the hanger tables."""
    sheets = {s.title: s for s in D.build_set(house(), INFO) if s.group == "SN"}
    bath = next(v for k, v in sheets.items() if k.startswith("แบบขยายระบบสุขาภิบาลห้องน้ำ"))
    t = " ".join(bath.texts())
    assert "ขนาดท่อย่อยที่ต่อเข้าสุขภัณฑ์" in t and "STOP VALVE" in t and "FCO" in t
    t = " ".join(sheets["แบบขยายการติดตั้งท่อ (แผ่นที่ 1)"].texts())
    assert "( LAV )" in t and "( FLUSH TANK )" in t and "( SH )" in t and "( RFD )" in t
    t = " ".join(sheets["แบบขยายการติดตั้งท่อ (แผ่นที่ 2)"].texts())
    assert "( FD )" in t and "( FCO )" in t and "( CO )" in t and "( AVC )" in t
    t = " ".join(sheets["แบบขยายและตารางระยะการแขวนท่อ"].texts())
    assert "100 (4)" in t and "เส้นผ่านศูนย์กลางเหล็ก (มม.)" in t


def test_ee_lighting_and_socket_plans():
    """EE as the standard: a lighting plan and a socket plan per floor, the
    switches lettered, every circuit's home run «n/LP» matching the panel."""
    from core import wanic_std_ee as EES
    from core import wanic_building as B_
    d = house()
    sheets = D.build_set(d, INFO)
    ee = [s for s in sheets if s.group == "EE"]
    titles = [s.title for s in ee]
    assert any(t.startswith("แปลนไฟฟ้าแสงสว่าง ชั้น") for t in titles)
    assert any(t.startswith("แปลนเต้ารับไฟฟ้า ชั้น") for t in titles)
    E = B_.elements(d)
    nos = {c["no"] for c in EES.circuits(E)["circuits"]}
    runs = set()
    for s in ee:
        for t in s.texts():
            head = t.split("/LP")[0]
            if "/LP" in t and head.isdigit():
                runs.add(int(head))
    assert runs and runs <= nos


def test_m_fans_and_air_conditioners_as_the_standard():
    """M: per floor, the recommended fans (CFM from 10 air changes an hour)
    and the wall-type AC units (BTU), labelled as the standard."""
    from core import wanic_std_m as MS
    assert MS.fan_cfm(4.0, 2.6) == 80 and MS.fan_cfm(16.0, 2.6) == 200
    m = [s for s in D.build_set(house(), INFO) if s.group == "M"]
    assert m and all(s.title.startswith("ตำแหน่งเครื่องปรับอากาศและพัดลมระบายอากาศ ชั้น") for s in m)
    t = " ".join(x for s in m for x in s.texts())
    assert "CEILING FAN" in t and "WALL TYPE" in t
