# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
"""BOQ ตามหลักเกณฑ์ 2569: the measuring rules, waste, labour and hand-off.

Expected numbers are worked by hand from the criteria (กรมบัญชีกลาง 2569,
ส่วนที่ 4 pp. 63–72) and ว480; WANIC tools are signed by นายเวนิช ธัมมะวงษ์
วิศวกรสำรวจ.
"""
from __future__ import annotations

import io
import math
import zipfile

from core import wanic_building as B
from core import wanic_quantities as Q
from core import wanic_recipes2569 as RC
from core import wanic_std2569 as S
from core import wanic_takeoff as T
from core import wanic_sign


def close(a, b, tol=1e-6):
    return math.isclose(a, b, rel_tol=tol, abs_tol=1e-6)


def _one_room():
    d = B.default_data()
    d["floors"][0]["rooms"] = [dict(id="a", name="ห้องนอน", x=0, y=0, w=3.0,
                                    d=3.0)]
    return d


def _by(result, start):
    return [ln for ln in result["lines"] if ln["desc"].startswith(start)]


def test_rules_from_the_criteria():
    assert S.q2(1.005) == 1.01 and S.q2(2.344) == 2.34
    net, tot, _how = S.excavation(1.0, 1.0, 1.5)
    assert close(net, 1.5) and close(tot, 1.95)            # +30 %
    net, tot, _how = S.excavation(1.0, 1.0, 2.5)
    assert close(net, 2.0 * 2.0 * 2.5) and close(tot, net)  # +0.50 m/side
    assert S.REBAR_WASTE["RB6"] == 5 and S.REBAR_WASTE["DB12"] == 9
    assert S.REBAR_WASTE["DB25"] == 15
    assert S.parse_bar("4-DB12") == (4, "DB12", None)
    assert S.parse_bar("RB6@0.15") == (None, "RB6", 0.15)
    assert S.parse_bar("xx") is None
    assert S.bar_count(1.0, 0.15) == 7
    assert S.steel_pieces(12.0, "gable")[1] == 3            # 12.36 m
    assert S.steel_pieces(17.5, "hip")[1] == 4              # 18.375 m
    prices = {"ไม้อัดดำ หนา 20 มม.": 520, "ไม้ยาง 1½\"×3\"": 420,
              "ตะปูตอกไม้ 3\"": 38}
    assert close(S.formwork_unit_price(prices), 403.74)
    assert close(S.wall_area(3.0, 0.2, 3.0, 0.4, 1.8), 2.8 * 2.6 - 1.8)
    assert S.labour("1.7a") == 421 and S.labour("1.10.2") == 3900
    assert S.excavation_labour_code(17.0, 1.5) == "1.3.1c"
    assert S.excavation_labour_code(150.0, 0.8) == "1.3.1a"


def test_recipes_were_transcribed():
    assert len(RC.RECIPES) >= 250
    brick = RC.find("6.1")
    assert brick["unit"] == "ตร.ม."
    assert brick["items"][0]["qty"] == 138
    k3 = RC.find("2.2")
    assert k3["items"][0]["qty"] == 320                     # ค.3 cement kg
    cost, missing = RC.unit_cost(RC.find("1.1"), {
        "ปูนซีเมนต์ผสม (มอก. 80/2566)": 2.6, "ทรายหยาบ": 480,
        "หินเบอร์ 1-2": 560})
    assert not missing
    assert close(cost, 260 * 2.6 + 0.62 * 480 + 1.03 * 560 + 180 * 0.0164)


def test_one_room_house_quantities():
    d = _one_room()
    r = Q.compute(d)
    exc = _by(r, "งานขุดดินฐานราก")[0]
    assert close(exc["net"], 4 * 1.0 * 1.0 * 1.5) and exc["waste"] == 30
    assert exc["qty"] == 7.8
    assert exc["lab"] == 181                                # small job
    fill = _by(r, "งานถมดินคืน")[0]
    assert close(fill["net"], 7.8 - 4 * 0.3 - 4 * 0.2 * 0.2 * 1.2)
    sand = _by(r, "ทรายรองก้นหลุม")[0]
    assert sand["waste"] == 25 and sand["qty"] == S.q2(4 * 0.05 * 1.25)
    footing = _by(r, "คอนกรีตโครงสร้าง ผสมเสร็จ 240 กก./ตร.ซม. — ฐานราก")[0]
    assert close(footing["net"], 4 * 0.3) and footing["lab"] == 421
    # Beams between column faces: 4 spans × (3 − 0.2) at each level.
    gb = _by(r, "คอนกรีตโครงสร้าง ผสมเสร็จ 240 กก./ตร.ซม. — คานคอดิน")[0]
    assert close(gb["net"], 4 * 2.8 * 0.2 * 0.4)
    # Slab between beams.
    s1 = _by(r, "คอนกรีตโครงสร้าง ผสมเสร็จ 240 กก./ตร.ซม. — พื้นวางบนดิน")[0]
    assert close(s1["net"], 2.8 * 2.8 * 0.10)
    # Walls: (c-c − column) × (floor to floor − roof beam), no openings.
    wall = _by(r, "ผนังก่ออิฐมอญ")[0]
    assert close(wall["net"], 4 * 2.8 * 2.6)
    ext = _by(r, "ฉาบปูนเรียบ ผนังภายนอก")[0]
    inn = _by(r, "ฉาบปูนเรียบ ผนังภายใน")[0]
    assert close(ext["net"], wall["net"]) and close(inn["net"], wall["net"])
    # Rebar waste by size, tie wire 30 kg per tonne.
    db12 = _by(r, "เหล็กเสริม DB12")[0]
    assert db12["waste"] == 9 and close(db12["lab"], 3.9)
    total = sum(ln["qty"] for ln in r["lines"]
                if ln["desc"].startswith("เหล็กเสริม "))
    tie = _by(r, "ลวดผูกเหล็ก")[0]
    assert close(tie["net"], total * 30 / 1000)
    # Roof steel in 6 m pieces, hip waste 5 %.
    steel = _by(r, "โครงหลังคาเหล็ก")
    assert steel and all("ท่อน" in ln["basis"] for ln in steel)
    roofing = _by(r, "มุงกระเบื้องคอนกรีต")[0]
    assert roofing["waste"] == 5
    assert all(ln["qty"] == round(ln["qty"], 2) for ln in r["lines"])


def test_openings_and_interior_walls():
    d = B.default_data()
    d["floors"][0]["rooms"] = [dict(id="a", x=0, y=0, w=3, d=3),
                               dict(id="b", x=3, y=0, w=3, d=3)]
    d["floors"][0]["openings"] = [{"id": "o1", "type": "door", "x": 1.5,
                                   "y": 0.0}]
    r = Q.compute(d)
    wall = _by(r, "ผนังก่ออิฐมอญ")[0]
    assert close(wall["net"], 7 * 2.8 * 2.6 - 0.9 * 2.0)
    inn = _by(r, "ฉาบปูนเรียบ ผนังภายใน")[0]
    ext = _by(r, "ฉาบปูนเรียบ ผนังภายนอก")[0]
    # The middle wall is plastered on both faces, inside.
    assert close(inn["net"] - ext["net"], 2 * 2.8 * 2.6)
    frame = _by(r, "D1 ประตูบานเปิดเดี่ยว ไม้ 0.90×2.00 ม. — วงกบ")[0]
    leaf = _by(r, "D1 ประตูบานเปิดเดี่ยว ไม้ 0.90×2.00 ม. — บาน")[0]
    assert frame["qty"] == 1 and close(frame["lab"], 1.8 * 103)
    assert leaf["qty"] == 1 and close(leaf["lab"], 1.8 * 108)
    assert _by(r, "D1 ประตูบานเปิดเดี่ยว ไม้ 0.90×2.00 ม. — อุปกรณ์")[0]["lab"] \
        == 103


def test_member_library_and_marks():
    d = _one_room()
    d["library"] = {"F2": {"kind": "footing", "w": 1.5, "l": 1.5, "t": 0.4,
                           "depth": 1.5, "bars": "DB16@0.15", "sand": 0.05,
                           "lean": 0.05, "piles": 4, "pile_b": 0.18,
                           "pile_len": 6.0}}
    d["assign"] = {B.node_key(0, 0): {"F": "F2"}}
    E = B.elements(d)
    marks = sorted(e["mark"] for e in E["footings"])
    assert marks == ["F1", "F1", "F1", "F2"]
    assert B.marks_of(B.library_of(d), "footing") == ["F1", "F2"]
    r = Q.compute(d)
    footing = _by(r, "คอนกรีตโครงสร้าง ผสมเสร็จ 240 กก./ตร.ซม. — ฐานราก")[0]
    assert close(footing["net"], 3 * 0.3 + 1.5 * 1.5 * 0.4)
    piles = _by(r, "เสาเข็ม")[0]
    assert piles["qty"] == 4 and piles["unit"] == "ต้น"
    assert _by(r, "เหล็กเสริม DB16")
    # A wrong mark falls back to the default.
    d["assign"] = {B.node_key(0, 0): {"F": "C1"}}
    assert {e["mark"] for e in B.elements(d)["footings"]} == {"F1"}


def test_hand_off_to_pr_forms_keeps_the_totals_and_signature():
    d = _one_room()
    d["prices"] = dict(S.SAMPLE_PRICES)
    r = Q.compute(d)
    td = T.default_data()
    td["rates"] = Q.to_rates(r)
    res = T.compute([], td)
    assert close(res["subtotal"], r["totals"]["total"], 1e-6)
    assert {ln["category"] for ln in res["lines"]} <= set(Q.GROUP_TH.values())
    data = T.boq_xlsx_bytes(res, T.settings_of(td))
    z = zipfile.ZipFile(io.BytesIO(data))
    text = "".join(z.read(n).decode("utf-8") for n in z.namelist()
                   if n.startswith("xl/worksheets/"))
    assert wanic_sign.NAME in text and wanic_sign.ROLE in text
    assert "ผู้ถอดแบบและคำนวณราคา" in text
    assert wanic_sign.FULL in Q.csv_text(r)


def test_empty_plan():
    r = Q.compute(B.default_data())
    assert r["lines"] == [] and r["notes"]


def test_fascia_doors_windows_sanitary_and_bathroom_tiles():
    from core import wanic_catalog as CAT
    d = B.default_data()
    d["floors"][0]["rooms"] = [
        dict(id="a", name="ห้องนอน", x=0, y=0, w=4, d=3),
        dict(id="b", name="ห้องน้ำ", x=4, y=0, w=2, d=3)]
    d["floors"][0]["openings"] = [
        {"id": "o1", "type": "door", "style": "D3", "x": 4.0, "y": 1.5},
        {"id": "o2", "type": "window", "style": "W1", "x": 2.0, "y": 3.0,
         "w": 1.5, "h": 1.2},
        {"id": "o3", "type": "window", "style": "W2", "x": 0.0, "y": 1.5}]
    d["floors"][0]["fixtures"] = [
        {"id": "x1", "type": "WC1", "x": 5.0, "y": 2.5},
        {"id": "x2", "type": "LV", "x": 5.5, "y": 2.5}]
    r = Q.compute(d)
    # A custom-sized window keeps its size; its glass is billed in ตร.ฟ.
    glass = _by(r, "W1 หน้าต่างบานเปิดคู่ ไม้ 1.50×1.20 ม. — กระจก")[0]
    assert glass["unit"] == "ตร.ฟ."
    assert close(glass["net"], 1.5 * 1.2 * 0.7 * CAT.SQFT_PER_M2)
    assert _by(r, "W1 หน้าต่างบานเปิดคู่ ไม้ 1.50×1.20 ม. — บาน")[0]["qty"] == 2
    # Prefab bathroom door leaf: ว480 2.5.3 บานสำเร็จรูป 77 บาท/ตร.ม.
    leaf = _by(r, "D3 ")[1]
    assert close(leaf["lab"], 0.7 * 2.0 * 77)
    alu = _by(r, "W2 ")
    assert len(alu) == 1 and alu[0]["unit"] == "ชุด"
    # Sanitary ware with ว480 2.6 labour.
    wc = _by(r, "โถส้วมนั่งราบ")[0]
    assert wc["qty"] == 1 and wc["lab"] == 461
    # Bathroom wall tiles to 2.00 m less the door, on a sand-cement base.
    tile = _by(r, "ผนังบุกระเบื้อง")[0]
    assert close(tile["net"], (2 * (2 + 3) - 4 * 0.2) * 2.0 - 0.7 * 2.0)
    base = _by(r, "ฉาบปูนทรายรองพื้น")[0]
    assert close(base["net"], tile["net"])
    # Floors by room type: 8"x8" in the bathroom.
    assert _by(r, "พื้นปูกระเบื้องดินเผาเคลือบเซรามิค (สีธรรมดา) ขนาด 8")
    # เชิงชาย around the hip roof's eaves (with the 0.6 m overhang).
    fascia = _by(r, "เชิงชาย")[0]
    assert close(fascia["net"], 2 * (6 + 1.2) + 2 * (3 + 1.2))
    assert fascia["lab"] == 74


def test_gable_roof_has_barge_boards():
    d = _one_room()
    d["settings"]["roof"] = "gable"
    lines = B.roof_lines(d)
    assert len(lines["eave"]) == 2 and len(lines["barge"]) == 4
    r = Q.compute(d)
    assert _by(r, "ปั้นลม")[0]["net"] > 0
