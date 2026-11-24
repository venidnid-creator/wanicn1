# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
"""ง3/ง6: บัญชี สพฐ. — the second price source, for สพฐ. jobs only."""
from __future__ import annotations

from core import wanic_building as B
from core import wanic_obec as O
from core import wanic_quantities as Q

# lines as the book's PDF gives them (marks out of place, as QtPdf reads it)
BOOK = """\
CODE รายการ หน่วย ค่าวัสดุ ค่าแรง หมายเหตุ
A1016 ทรายหยาบ ลบ.ม. 510 - .
A3011 ขนาด Ø 3 นิว้ ยาว 3.00 - 3.50 เมตร ตน้ 28 - .
A3012 ตะปูขนาดต่างๆ กก. 47 -
A4005 คอนกรีตผสมเสร็จ 240 กก./ตร.ซม. / 210 กก./ตร.ซม. ลบ.ม. 2,470 - 1. โครงสร้างติดดิน
A4019 ปนู ซีเมนตผ์ สม ( 50 ก.ก./ถงุ ) ถงุ 133 - .
A5000 เหล็กเสน้ กลมผิวเรียบ SR.24 ขนาด RB 6 มม. ( 2.22 กก./เสน้ ) ตนั 21,850 4,400 .
A5012 เหลก็ เสน้ กลมผิวขอ้ออ้ย SD.40 ขนาด DB 12 มม. (8.88 กก./เสน้ ) ตนั 21,150 3,600 .
A2019 ค่าเครื่องจกัร (Pre-Bore) เมตร 200 รวมคา่ แรง
A2000 เสาเข็ม คอร. . ขนาด 0.18 x 0.18 x 21.00 ม.
B2011 ฝา้ยิปซ่มั บอรด์ หนา9 มม. ครา่ วโลหะชบุ สงักะสี ตร.ม. 258 75 ธรรมดา
B4074 ผนังยิปซ่มั บอรด์ หนา9 มม.ครา่ วเหล็กชบุ สงักะสีดา้นเดียว ตร.ม. 300 80
C2015 ถังบา บดันา ้เสียแบบรวม ไม่มีระบบอดัอากาศ ขนาด 1,600 ลิตร ชดุ 5,739 1,800
B10015 สีทากระเบือ้งหลงัคา ตร.ม. 59 28 .
"""


def _items():
    return O.parse_text(BOOK)


def _job(**kw):
    d = B.default_data()
    d["floors"][0]["rooms"] = [dict(id="a", name="ห้องนอน", x=0, y=0, w=4.0, d=4.0)]
    d["province"] = "ขอนแก่น"
    d.update(kw)
    return d


def test_the_book_lines_are_read():
    it = {x["code"]: x for x in _items()}
    assert it["A4005"]["unit"] == "ลบ.ม." and it["A4005"]["mat"] == 2470 \
        and it["A4005"]["lab"] is None
    assert it["A5000"]["mat"] == 21850 and it["A5000"]["lab"] == 4400
    # «รวมค่าแรง»: the material price already holds the labour
    assert it["A2019"]["mat"] == 200 and it["A2019"]["lab"] is None \
        and it["A2019"]["note"].startswith("รวม")
    assert "A2000" not in it                         # a tiered row with no price on it
    assert it["B10015"]["mat"] == 59                 # five-digit codes too


def test_price_keys_in_our_units():
    items = _items()
    assert O.key_price("RB6", "กก.", items)[0] == 21.85          # ตัน → กก.
    assert O.key_price("DB12", "กก.", items)[0] == 21.15
    assert O.key_price("ปูนซีเมนต์ผสม (มอก. 80/2566)", "กก.", items)[0] == 2.66
    v, it = O.key_price("คอนกรีตผสมเสร็จ 240 กก./ตร.ซม. (ลูกบาศก์)", "ลบ.ม.", items)
    assert v == 2470 and it["code"] == "A4005"
    assert O.key_price('ไม้ค้ำยันยูคาลิปตัส ศก. 3" ยาว 3 ม.', "ต้น", items)[0] == 28
    assert O.key_price("ทรายหยาบ", "ลบ.ม.", items)[0] == 510


def test_matching_is_strict():
    items = _items()
    # the ceiling is not the wall, a 600-litre tank is not a 1,600-litre one,
    # the roof tile is not the tile paint
    m = O.match("ฝ้ายิปซัมบอร์ด 9 มม. ฉาบรอยต่อเรียบ โครงคร่าวเหล็กชุบสังกะสี",
                "ตร.ม.", items)
    assert m and m["code"] == "B2011"
    assert O.match("ถังบำบัดน้ำเสียสำเร็จรูป 600 ลิตร", "ชุด", items, "lab") is None
    assert O.key_price("กระเบื้องคอนกรีต (รวมอุปกรณ์)", "ตร.ม.", items)[1] is None
    assert O.match("ทรายหยาบ", "กก.", items) is None             # another unit


def test_only_a_obec_job_and_only_empty_items(tmp_path, monkeypatch):
    monkeypatch.setenv("WANIC_OBEC_FILE", str(tmp_path / "obec.json"))
    items = _items()
    d = _job(prices={"ทรายหยาบ": 600.0}, price_src={"ทรายหยาบ": "พาณิชย์"})
    r = Q.priced(d)
    assert O.fill(d, r, items) == {"mat": 0, "lab": 0}          # not สพฐ.'s: nothing
    d["obec"] = True
    got = O.fill(d, Q.priced(d), items)
    assert got["mat"] > 0
    assert d["prices"]["ทรายหยาบ"] == 600.0                     # พาณิชย์จังหวัด first
    assert d["price_src"]["RB6"] == "สพฐ." and d["prices"]["RB6"] == 21.85
    assert d["price_item"]["RB6"].startswith("A5000")
    r = Q.priced(d)
    rb = [ln for ln in r["lines"] if ln["mat_key"] == "RB6"][0]
    assert rb["mat"] == 21.85 and "สพฐ." in rb["note"] and "A5000" in rb["note"]
    assert any("งานของ สพฐ." in n for n in r["notes"])
    # the same job marked «not สพฐ.»: the สพฐ. prices do not count
    d["obec"] = False
    assert Q.prices_of(d)["RB6"] == 0 and Q.prices_of(d)["ทรายหยาบ"] == 600
    d["obec"] = True
    assert O.strip(d) > 0 and "RB6" not in d["prices"] and d["prices"]["ทรายหยาบ"] == 600


def test_obec_prices_never_reach_the_province_book(tmp_path, monkeypatch):
    from core import wanic_province as P
    monkeypatch.setattr(P, "book_dir", lambda: str(tmp_path))
    book = P.save_book("ขอนแก่น", {"RB6": 21.85, "ทรายหยาบ": 600},
                       src={"RB6": "สพฐ.", "ทรายหยาบ": "พาณิชย์"})
    assert book["prices"] == {"ทรายหยาบ": 600.0}


def test_the_attached_book_is_remembered_until_deleted(tmp_path, monkeypatch):
    monkeypatch.setenv("WANIC_OBEC_FILE", str(tmp_path / "x" / "obec.json"))
    assert O.load_store() == {}
    O.save_store(_items(), "สพฐ 2569.pdf")
    st = O.load_store()
    assert st["name"] == "สพฐ 2569.pdf" and len(st["items"]) == len(_items())
    O.clear_store()
    assert O.load_store() == {}


def test_csv_list(tmp_path):
    f = tmp_path / "obec.csv"
    f.write_text("รหัส,รายการ,หน่วย,ค่าวัสดุ,ค่าแรง,หมายเหตุ\n"
                 "A1016,ทรายหยาบ,ลบ.ม.,510,-,\nX,หัวข้อ,,,,\n", encoding="utf-8-sig")
    it = O.read_file(f)
    assert it == [{"code": "A1016", "desc": "ทรายหยาบ", "unit": "ลบ.ม.",
                   "mat": 510.0, "lab": None, "note": ""}]
