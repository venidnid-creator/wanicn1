# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
"""The building model as a 2D drawing set (A, S, SN, EE, M sheets)."""
from __future__ import annotations

import re

from core import wanic_building as B
from core import wanic_drawings as D


def house():
    """Two storeys, an L plan, doors, windows, a stair and a bathroom."""
    d = B.default_data()
    g = [dict(id="r1", name="ห้องนั่งเล่น", x=0, y=0, w=5, d=4),
         dict(id="r2", name="ห้องครัว", x=5, y=0, w=3.5, d=4),
         dict(id="r3", name="ห้องน้ำ", x=5, y=4, w=3.5, d=2.3),
         dict(id="r4", name="ห้องนอน", x=0, y=4, w=5, d=4.3)]
    ops = [dict(id="o1", type="door", style="D2", x=2.5, y=0, w=1.6, h=2.0),
           dict(id="o2", type="window", style="W2", x=6.75, y=0, w=1.4, h=1.2,
                sill=0.9),
           dict(id="o3", type="door", style="D1", x=2.5, y=4, w=0.9, h=2.0),
           dict(id="o4", type="door", style="D3", x=6.0, y=4, w=0.7, h=2.0),
           dict(id="o5", type="window", style="W1", x=0, y=6.0, w=1.2, h=1.1,
                sill=0.9)]
    fx = [dict(id="x1", type="WC1", x=7.8, y=5.8, dir=0),
          dict(id="x2", type="LV", x=6.0, y=6.0, dir=0)]
    d["floors"] = [
        {"rooms": g, "openings": ops, "fixtures": fx,
         "stairs": [dict(id="s1", x=4.2, y=2.0, dir=1, w=1.0)]},
        {"rooms": [dict(r, id=r["id"] + "u", name="ห้องนอน" if i < 2 else
                        r["name"]) for i, r in enumerate(g)],
         "openings": [dict(o, id=o["id"] + "u") for o in ops[1:]],
         "fixtures": [dict(f, id=f["id"] + "u") for f in fx], "stairs": []}]
    return d


INFO = {"project": "บ้านพักอาศัย 2 ชั้น", "owner": "นายทดสอบ",
        "location": "จังหวัดลพบุรี", "drawing_no": "WN-001"}


def test_the_whole_set_numbered_like_the_standard_drawings():
    S = D.build_set(house(), INFO)
    codes = [s.code for s in S]
    assert codes[:4] == ["A-01", "A-02", "A-03", "A-04"]
    for g in ("A-", "S-", "SN-", "EE-", "M-"):
        assert any(c.startswith(g) for c in codes), g
    dw = [s for s in S if s.group != "BOQ"]
    assert [s.number for s in dw] == list(range(1, len(dw) + 1))
    titles = [s.title for s in S]
    for t in ("ผังบริเวณ", "แปลนพื้นชั้น 1", "แปลนพื้นชั้น 2", "แปลนหลังคา",
              "รูปตัด ก-ก รูปตัด ข-ข", "แปลนฐานราก", "แปลนโครงหลังคา",
              "ตารางฐานราก เสา คาน พื้น", "แปลนระบบสุขาภิบาลชั้น 1",
              "แปลนระบบไฟฟ้าชั้น 2", "แบบขยายห้องน้ำ"):
        assert t in titles, t
    # Elevations: all four faces.
    joined = " ".join(titles)
    for t in ("รูปด้านหน้า", "รูปด้านหลัง", "รูปด้านซ้าย", "รูปด้านขวา"):
        assert t in joined


def test_every_sheet_has_the_title_block_and_signature():
    S = D.build_set(house(), INFO)
    drawings = [s for s in S if s.group != "BOQ"]
    for s in S:
        if s.group == "BOQ":
            _in_bounds(s)
            continue
        t = s.texts()
        assert s.code in t and str(s.number) in t and \
            f"/ {len(drawings)}" in t
        assert "บ้านพักอาศัย 2 ชั้น" in t and "WN-001" in t
        assert "(นายเวนิช ธัมมะวงษ์)" in t and "วิศวกรสำรวจ" in t
        for role in ("สถาปัตยกรรม", "โครงสร้าง", "สุขาภิบาล", "ไฟฟ้า",
                     "เครื่องกล"):
            assert role in t
        assert s.scale in t
        _in_bounds(s)


def _in_bounds(s):
    """Everything inside the A3 sheet."""
    if True:
        for it in s.items:
            pts = []
            if it[0] == "line":
                pts = [it[1][:2], it[1][2:]]
            elif it[0] in ("poly", "fill"):
                pts = it[1]
            for x, y in pts:
                assert -1 <= x <= D.PAPER[0] + 1 and -1 <= y <= D.PAPER[1] + 1, \
                    (s.code, it[0])


def test_floor_plan_content():
    S = {s.code: s for s in D.build_set(house(), INFO)}
    p1 = S["A-03"]
    t = p1.texts()
    for name in ("ห้องนั่งเล่น", "ห้องครัว", "ห้องน้ำ", "ห้องนอน"):
        assert name in t
    assert "ป1" in t and "น1" in t                 # door / window codes
    assert "5.00" in t and "3.50" in t             # grid dimensions
    assert {"1", "2", "3", "A", "B"} <= set(t)     # grid bubbles
    assert p1.count("arc") >= 2                    # door swings
    assert p1.scale == "1:100"
    assert any(re.fullmatch(r"พ\d.*±0\.00", x) for x in t)


def test_schedules_and_systems():
    S = {s.code: s for s in D.build_set(house(), INFO)}
    sched = next(s for s in S.values() if s.title.startswith("ตารางประตู"))
    t = " ".join(sched.texts())
    assert "ป1" in t and "น1" in t and "จำนวน" in t and "พ1" in t
    st = next(s for s in S.values() if s.title.startswith("ตารางฐานราก"))
    t = st.texts()
    assert "F1" in t and "GB1" in t and "C1" in t and "S1" in t
    ee = next(s for s in S.values() if s.code == "EE-01")
    t = " ".join(ee.texts())
    assert "ตารางโหลด" in t and "เมนเบรกเกอร์" in t
    sn = next(s for s in S.values() if s.title == "แปลนระบบสุขาภิบาลชั้น 1")
    t = " ".join(sn.texts())
    assert "บ่อบำบัด" in t and "S Ø4\"" in t and "W Ø2\"" in t
    m = next(s for s in S.values() if s.group == "M")
    assert "FCU" in " ".join(m.texts())


def test_only_the_chosen_families():
    S = D.build_set(house(), INFO, ("S",))
    assert S and all(s.group == "S" for s in S)
    assert D.build_set(B.default_data(), INFO) == []


def test_dxf_holds_every_sheet_in_thai():
    S = D.build_set(house(), INFO)
    b = D.dxf_bytes(S)
    text = b.decode("cp874")
    assert "$DWGCODEPAGE\n3\nANSI_874" in text
    assert text.count("\n0\nTEXT\n") == sum(s.count("text") for s in S)
    assert "แปลนพื้นชั้น 1" in text and "%%c" in text and "?" not in \
        "".join(re.findall(r"\n1\n([^\n]*)", text))
    assert text.rstrip().endswith("EOF")
    # sheets side by side
    xs = [float(m) for m in re.findall(r"\n10\n([-\d.]+)", text)]
    assert max(xs) > (len(S) - 1) * D.PAPER[0]


def test_thai_wrap_keeps_syllables():
    lines = D._wrap("การติดตั้งให้เป็นไปตามมาตรฐานการติดตั้งทางไฟฟ้าสำหรับ"
                    "ประเทศไทยและข้อกำหนดของการไฟฟ้าส่วนภูมิภาค", 20)
    assert all(len(x) <= 20 for x in lines)
    marks = "ัิีึืุูำ่้๊๋์็ะา"
    assert all(x[0] not in marks for x in lines)
    assert "".join(lines) == ("การติดตั้งให้เป็นไปตามมาตรฐานการติดตั้งทางไฟฟ้า"
                              "สำหรับประเทศไทยและข้อกำหนดของการไฟฟ้าส่วนภูมิภาค")


def test_the_book_ends_with_por4():
    from core import wanic_std2569 as STD
    d = house()
    d["prices"] = {k: STD.sample_price(k) for k, _u in STD.PRICE_KEYS}
    d.update(province="ลพบุรี", price_month="ก.ย. 2569")
    S = D.build_set(d, dict(INFO, preparer="นายเวนิช ธัมมะวงษ์"))
    boq = [s for s in S if s.group == "BOQ"]
    assert boq and S[-len(boq):] == boq                   # at the end
    assert [s.code for s in boq] == [f"ปร.4-{i}" for i in
                                     range(1, len(boq) + 1)]
    first = " ".join(boq[0].texts())
    for t in ("แบบ ปร.4", "รายการประมาณราคาค่าก่อสร้าง", "สรุปงาน",
              "หมวดงานดินและฐานราก", "รวมค่าวัสดุและค่าแรงงานเป็นเงินประมาณ",
              "สถานที่ก่อสร้าง  จังหวัดลพบุรี", "แบบเลขที่  WN-001",
              "สำนักงานพาณิชย์จังหวัดลพบุรี", "หน่วย : บาท", "ราคาหน่วยละ",
              "จำนวนเงิน", "ค่าแรงงาน", f"แผ่นที่ 1 / {len(boq)}"):
        assert t in first, t
    allt = " ".join(t for s in boq for t in s.texts())
    assert "รวมข้อ 1 หมวดงานดินและฐานราก" in allt
    assert "ผู้ประมาณราคา" in " ".join(boq[-1].texts())
    # The summary total is the BOQ's total.
    from core import wanic_quantities as Q
    total = Q.compute(d)["totals"]["total"]
    assert f"{total:,.2f}" in first
    # Without prices: the department's blank form.
    S2 = D.build_set(d, dict(INFO, boq_prices=False), ("BOQ",))
    assert S2 and all(s.group == "BOQ" for s in S2)
    assert f"{total:,.2f}" not in " ".join(S2[0].texts())
