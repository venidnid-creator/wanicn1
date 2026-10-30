# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
"""Material prices by province: books, the commerce office's table, matching."""
from __future__ import annotations

import io
import zipfile

import pytest

from core import wanic_province as P
from core import wanic_std2569 as S

#: Rows as copied from a commerce-office price page (tab separated):
#: code, name, unit, last month, this month.
MOC = "\n".join([
    "รหัส\tรายการ\tหน่วย\tราคาเดือนก่อน\tราคาเดือนนี้",
    "01\tทรายหยาบ\tลบ.ม.\t520.00\t530.00",
    "02\tหินย่อย เบอร์ 1-2\tลบ.ม.\t600\t610",
    "03\tปูนซีเมนต์ผสม (ตราเสือ) 50 กก.\tกก.\t2.70\t2.75",
    "04\tปูนซีเมนต์ปอร์ตแลนด์ (ตราช้าง) 50 กก.\tกก.\t3.20\t3.25",
    "05\tเหล็กเส้นกลม SR24 ขนาด 6 มม.\tกก.\t26.50\t26.00",
    "06\tเหล็กเส้นกลม SR24 ขนาด 9 มม.\tกก.\t25.50\t25.25",
    "07\tเหล็กข้ออ้อย SD40 ขนาด 12 มม.\tกก.\t24.00\t23.80",
    "08\tเหล็กข้ออ้อย SD40 ขนาด 16 มม.\tกก.\t23.90\t23.70",
    "09\tลวดผูกเหล็ก เบอร์ 18\tกก.\t44\t45",
    "10\tอิฐมอญ ขนาด 7x16x3.5 ซม.\tก้อน\t1.10\t1.15",
    "11\tคอนกรีตผสมเสร็จ 240 ksc. (ลูกบาศก์)\tลบ.ม.\t2,300\t2,350",
    "12\tท่อ PVC 4 นิ้ว ชั้น 8.5\tท่อน\t310\t315",
])


def test_77_provinces_in_six_regions():
    assert len(P.PROVINCES) == 77
    assert "บึงกาฬ" in P.PROVINCES and "กรุงเทพมหานคร" in P.PROVINCES
    assert P.region_of("ขอนแก่น") == "ภาคตะวันออกเฉียงเหนือ"


def test_last_month_is_the_one_before():
    import datetime
    assert P.last_month(datetime.date(2026, 10, 30)) == "ก.ย. 2569"
    assert P.last_month(datetime.date(2027, 1, 5)) == "ธ.ค. 2569"


def test_rows_take_this_months_price():
    items = P.parse_rows(P.rows_from_text(MOC))
    assert len(items) == 12                              # the header skipped
    name, unit, price = items[0]
    assert (name, unit, price) == ("ทรายหยาบ", "ลบ.ม.", 530.0)
    assert items[10][2] == 2350.0                        # "2,350"


def test_matching_names_to_the_boq_keys():
    keys = [k for k, _u in S.PRICE_KEYS]
    got = P.match(P.parse_rows(P.rows_from_text(MOC)), keys)
    assert got["ทรายหยาบ"][0] == 530
    assert got["หินเบอร์ 1-2"][0] == 610
    assert got["ปูนซีเมนต์ผสม (มอก. 80/2566)"][0] == 2.75
    assert got["RB6"][0] == 26 and got["RB9"][0] == 25.25
    assert got["DB12"][0] == 23.8 and got["DB16"][0] == 23.7
    assert got["ลวดผูกเหล็ก"][0] == 45
    assert got["อิฐมอญ (อิฐก่อสร้างสามัญ) ขนาด 7 x 16 x 3.5 ซม."][0] == 1.15
    assert got["คอนกรีตผสมเสร็จ 240 กก./ตร.ซม. (ลูกบาศก์)"][0] == 2350
    portland = [k for k in keys if k.startswith("ปูนซีเมนต์ปอร์ตแลนด์")][0]
    assert got[portland][0] == 3.25
    # The pipe matches nothing the BOQ asks for.
    assert all("PVC" not in name for _p, name in got.values())


def test_our_own_exported_csv_reads_back_exactly():
    text = "วัสดุ,หน่วย,ราคา/หน่วย\nDB20,กก.,24.1\nสีกันสนิม,ตร.ม.,26\n"
    got = P.match(P.parse_rows(P.rows_from_text(text)), ["DB20", "สีกันสนิม"])
    assert got == {"DB20": (24.1, "DB20"), "สีกันสนิม": (26.0, "สีกันสนิม")}


def _xlsx(rows) -> bytes:
    shared, xml_rows = [], []
    for ri, row in enumerate(rows, 1):
        cells = []
        for ci, v in enumerate(row):
            ref = f"{chr(65 + ci)}{ri}"
            if isinstance(v, (int, float)):
                cells.append(f'<c r="{ref}"><v>{v}</v></c>')
            else:
                shared.append(v)
                cells.append(f'<c r="{ref}" t="s"><v>{len(shared) - 1}</v></c>')
        xml_rows.append(f'<row r="{ri}">{"".join(cells)}</row>')
    ns = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("xl/sharedStrings.xml", f"<sst {ns}>" + "".join(
            f"<si><t>{s}</t></si>" for s in shared) + "</sst>")
        z.writestr("xl/worksheets/sheet1.xml",
                   f"<worksheet {ns}><sheetData>{''.join(xml_rows)}"
                   "</sheetData></worksheet>")
    return buf.getvalue()


def test_reading_an_xlsx_file(tmp_path):
    path = tmp_path / "ราคา.xlsx"
    path.write_bytes(_xlsx([["รายการ", "หน่วย", "ราคา"],
                            ["ทรายหยาบ", "ลบ.ม.", 495],
                            ["เหล็กข้ออ้อย SD40 ขนาด 20 มม.", "กก.", 23.5]]))
    items = P.read_file(str(path))
    assert items == [("ทรายหยาบ", "ลบ.ม.", 495.0),
                     ("เหล็กข้ออ้อย SD40 ขนาด 20 มม.", "กก.", 23.5)]
    assert P.match(items, ["DB20"])["DB20"][0] == 23.5


def test_old_xls_is_refused_with_advice(tmp_path):
    path = tmp_path / "old.xls"
    path.write_bytes(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\0" * 64)
    with pytest.raises(ValueError, match="xlsx"):
        P.read_file(str(path))


def test_thai_windows_csv(tmp_path):
    path = tmp_path / "cp874.csv"
    path.write_bytes("ทรายหยาบ,ลบ.ม.,500\n".encode("cp874"))
    assert P.read_file(str(path)) == [("ทรายหยาบ", "ลบ.ม.", 500.0)]


def test_books_per_province(tmp_path, monkeypatch):
    monkeypatch.setenv("WANIC_PRICE_DIR", str(tmp_path))
    assert P.books() == [] and P.load_book("ขอนแก่น") is None
    P.save_book("ขอนแก่น", {"ทรายหยาบ": 510, "RB6": 0, "DB12": "x"},
                "ก.ย. 2569", src={"ทรายหยาบ": "กรอกเอง"})
    b = P.load_book("ขอนแก่น")
    assert b["prices"] == {"ทรายหยาบ": 510.0}           # zeros and junk dropped
    assert b["month"] == "ก.ย. 2569" and b["src"] == {"ทรายหยาบ": "กรอกเอง"}
    assert b["source"] == "สำนักงานพาณิชย์จังหวัดขอนแก่น"
    assert P.books() == ["ขอนแก่น"]


def test_coverage():
    n, missing = P.coverage({"a": 1, "b": 0}, ["a", "b", "c"])
    assert n == 1 and missing == ["b", "c"]


def test_the_bill_names_the_province_and_month():
    from core import wanic_quantities as Q
    from core import wanic_building as B
    d = B.default_data()
    d["floors"][0]["rooms"].append(
        {"id": "r1", "name": "ห้องนอน", "x": 0, "y": 0, "w": 3, "d": 3})
    r = Q.compute(d)
    assert r["province"] == "" and r["price_ref"] == ""
    assert any("ยังไม่ได้เลือกจังหวัด" in n for n in r["notes"])
    r = Q.compute(dict(d, province="ขอนแก่น", price_month="ก.ย. 2569"))
    assert r["price_ref"] == ("ราคาวัสดุ: สำนักงานพาณิชย์จังหวัดขอนแก่น "
                              "ประจำเดือน ก.ย. 2569")
    assert not any("ยังไม่ได้เลือกจังหวัด" in n for n in r["notes"])
    assert "กรุงเทพมหานคร" in Q.price_ref("กรุงเทพมหานคร")


def test_the_pr_header_prints_the_price_reference():
    from core import wanic_takeoff as T
    td = T.default_data()
    td["settings"]["price_ref"] = "ราคาวัสดุ: สำนักงานพาณิชย์จังหวัดขอนแก่น"
    td["rates"] = [T.new_rate(id="x", category="ก", desc="ทราย", qty="manual",
                              manual_qty=1, unit="ลบ.ม.", mat=500, lab=0)]
    data = T.boq_xlsx_bytes(T.compute([], td), T.settings_of(td))
    z = zipfile.ZipFile(io.BytesIO(data))
    strings = z.read("xl/sharedStrings.xml").decode("utf-8") \
        if "xl/sharedStrings.xml" in z.namelist() else "".join(
            z.read(n).decode("utf-8") for n in z.namelist()
            if n.startswith("xl/worksheets/"))
    assert "สำนักงานพาณิชย์จังหวัดขอนแก่น" in strings


def test_province_codes():
    assert len(P.CODES) == 77
    assert P.CODES["กรุงเทพมหานคร"] == "10" and P.CODES["ภูเก็ต"] == "83"
    assert P.month_label(2026, 9) == "ก.ย. 2569"


def test_recipe_rebar_names_match_too():
    keys = ["RB6", "เหล็กเสริม RB Ø 6 มม.", "DB12", "เหล็กเสริม DB Ø 12 มม.",
            "เหล็กรูปพรรณ (ทั่วไป)"]
    got = P.match([("เหล็กเส้นกลม SR24 ขนาด 6 มม.", "กก.", 26.0),
                   ("เหล็กข้ออ้อย SD40 ขนาด 12 มม.", "กก.", 23.8),
                   ("ตะแกรงเหล็กสำเร็จรูป 4 มม.", "ตร.ม.", 30.0)], keys)
    assert got["RB6"][0] == got["เหล็กเสริม RB Ø 6 มม."][0] == 26.0
    assert got["DB12"][0] == got["เหล็กเสริม DB Ø 12 มม."][0] == 23.8
    assert P._bar("ตะแกรงเหล็กสำเร็จรูป 4 มม.") is None


API_JSON = [
    {"com_code": "A1", "com_name_th": "ทรายหยาบ", "province_code": "83",
     "province_name": "ภูเก็ต", "year": 2026, "month": 8, "units": "ลบ.ม.",
     "price": 600.0},
    {"com_code": "A1", "com_name_th": "ทรายหยาบ", "province_code": "83",
     "province_name": "ภูเก็ต", "year": 2026, "month": 9, "units": "ลบ.ม.",
     "price": 620.0},
    {"com_code": "B2", "com_name_th": "เหล็กข้ออ้อย SD40 ขนาด 12 มม.",
     "year": 2026, "month": 9, "units": "กก.", "price": 24.4},
    {"com_code": "C3", "com_name_th": "ของไม่มีราคา", "year": 2026,
     "month": 9, "units": "ชิ้น", "price": 0},
]


def test_latest_items_take_the_newest_month():
    items, month = P.latest_items(API_JSON)
    assert month == "ก.ย. 2569"
    assert sorted(items) == [("ทรายหยาบ", "ลบ.ม.", 620.0),
                             ("เหล็กข้ออ้อย SD40 ขนาด 12 มม.", "กก.", 24.4)]
    assert P.latest_items({"data": API_JSON})[1] == "ก.ย. 2569"


def test_fetch_online_with_a_fake_api(monkeypatch):
    import datetime
    import json
    monkeypatch.delenv("WANIC_OFFLINE", raising=False)
    seen = []

    def opener(url, timeout):
        seen.append(url)
        return json.dumps(API_JSON).encode()
    items, month, url = P.fetch_online("ภูเก็ต", datetime.date(2026, 10, 30),
                                       opener)
    assert month == "ก.ย. 2569" and len(items) == 2
    assert "province_code=83" in seen[0] and "from_year=2026" in seen[0]

    def broken(url, timeout):
        raise OSError("no network")
    with pytest.raises(P.FetchError, match="ไม่สำเร็จ"):
        P.fetch_online("ภูเก็ต", opener=broken)
    monkeypatch.setenv("WANIC_OFFLINE", "1")
    with pytest.raises(P.FetchError):
        P.fetch_online("ภูเก็ต", opener=opener)


def test_fetch_falls_back_to_the_latest_announced_month(monkeypatch):
    """Nothing announced this year yet → last year's newest month."""
    import datetime
    import json
    monkeypatch.delenv("WANIC_OFFLINE", raising=False)
    last_year = [dict(r, year=2025, month=12) for r in API_JSON]
    seen, said = [], []

    def opener(url, timeout):
        seen.append(url)
        if "csi-indexes" in url:
            raise TimeoutError("The read operation timed out")
        return json.dumps(last_year if "from_year=2025" in url else []).encode()
    items, month, url = P.fetch_online("ภูเก็ต", datetime.date(2026, 1, 3),
                                       opener, progress=said.append)
    assert month == "ธ.ค. 2568" and "from_year=2025" in url
    # Once one path answers, the other is not asked again.
    assert sum("csi-indexes" in u for u in seen) == 0
    assert any("2569" in t for t in said) and any("2568" in t for t in said)


def test_fetch_reports_timeouts_of_both_paths(monkeypatch):
    monkeypatch.delenv("WANIC_OFFLINE", raising=False)
    seen = []

    def slow(url, timeout):
        seen.append(url)
        raise TimeoutError("The read operation timed out")
    with pytest.raises(P.FetchError, match="timed out"):
        P.fetch_online("ภูเก็ต", opener=slow)
    assert len(seen) == 2                    # one year, both paths, then stop


#: The ministry's table (index.tpso.go.th) as downloaded/copied: a title,
#: the period line, a header row, rows whose category name is longer than
#: the item name, and an item wrapped over two lines.
TPSO = [
    ["ราคาวัสดุก่อสร้างจังหวัดภูเก็ต (ราคาเงินสด ไม่รวมภาษีมูลค่าเพิ่ม ไม่รวมค่าขนส่ง)"],
    ["ระยะเวลา กันยายน 2569", "", "สำนักงานพาณิชย์จังหวัดภูเก็ต"],
    ["รหัสหมวด", "ชื่อหมวดสินค้า", "รหัส", "รายการ", "หน่วย", "กันยายน"],
    ["01", "วัสดุถม/รองพื้น", "0101010100100000", "ทรายหยาบ", "ลบ.ม.", "650.00"],
    ["02", "วัสดุและอุปกรณ์งานโครงสร้างเหล็ก", "0201010100100000",
     "เหล็กข้ออ้อย SD40 ขนาด 12 มม.", "กก.", "24.90"],
    ["03", "ชิ้นส่วนโครงสร้างสำเร็จรูป", "0303010101500000",
     "เสาเข็มคอนกรีตอัดแรง รูปสี่เหลี่ยมตัน ขนาด 0.18\nx 0.18 ม. ยาว 10.00 ม.",
     "ท่อน", "3,074.77"],
]


def test_the_ministry_table_layout_and_month():
    items = P.parse_rows(TPSO)
    assert items[0] == ("ทรายหยาบ", "ลบ.ม.", 650.0)
    assert items[1] == ("เหล็กข้ออ้อย SD40 ขนาด 12 มม.", "กก.", 24.9)
    assert items[2][0].startswith("เสาเข็มคอนกรีตอัดแรง") and \
        items[2][0].endswith("ยาว 10.00 ม.") and items[2][2] == 3074.77
    assert P.detect_month(TPSO) == "ก.ย. 2569"
    assert P.match(items, ["ทรายหยาบ", "DB12"]) == {
        "ทรายหยาบ": (650.0, "ทรายหยาบ"),
        "DB12": (24.9, "เหล็กข้ออ้อย SD40 ขนาด 12 มม.")}


def test_copied_web_rows_without_a_header():
    text = ("01\tวัสดุถม/รองพื้น\t0101010100100000\tทรายหยาบ\tลบ.ม.\t650.00\n"
            '03\tชิ้นส่วนโครงสร้างสำเร็จรูป\t0303010101500000\t"เสาเข็ม 0.18\n'
            'x 0.18 ม."\tท่อน\t3,074.77\n')
    items = P.parse_rows(P.rows_from_text(text))
    assert items[0] == ("ทรายหยาบ", "ลบ.ม.", 650.0)       # not the category
    assert items[1] == ("เสาเข็ม 0.18 x 0.18 ม.", "ท่อน", 3074.77)


def test_xlsx_from_the_ministry(tmp_path):
    path = tmp_path / "ภูเก็ต.xlsx"
    path.write_bytes(_xlsx(TPSO[:5]))
    items, month = P.read_table(str(path))
    assert month == "ก.ย. 2569" and items[0] == ("ทรายหยาบ", "ลบ.ม.", 650.0)


def test_pdf_is_refused_with_advice(tmp_path):
    path = tmp_path / "x.pdf"
    path.write_bytes(b"%PDF-1.7 ...")
    with pytest.raises(ValueError, match="Excel"):
        P.read_file(str(path))


def test_market_price_notes():
    from core import wanic_quantities as Q
    assert Q.market_note("ภูเก็ต", "พาณิชย์", 650) == ""
    assert "ต้องใช้ราคาตามท้องตลาด ณ จังหวัดภูเก็ต" in Q.market_note(
        "ภูเก็ต", None, 0)
    assert Q.market_note("ภูเก็ต", "ท้องตลาด", 55, "ร้าน ก. 29 ต.ค.") == (
        "ไม่พบราคาที่จังหวัดภูเก็ตประกาศ — ใช้ราคาตามท้องตลาด (ร้าน ก. 29 ต.ค.)")
    from core import wanic_building as B
    d = B.default_data()
    d["floors"][0]["rooms"].append(
        {"id": "r1", "name": "ห้องนอน", "x": 0, "y": 0, "w": 3, "d": 3})
    d.update(province="ภูเก็ต", prices={"DB12": 24.9, "RB6": 27},
             price_src={"DB12": "พาณิชย์", "RB6": "ท้องตลาด"},
             price_note={"RB6": "ร้าน ข."})
    r = Q.compute(d)
    by = {ln["mat_key"]: ln["note"] for ln in r["lines"] if ln["mat_key"]}
    assert "ไม่พบราคา" not in by["DB12"]
    assert "ใช้ราคาตามท้องตลาด (ร้าน ข.)" in by["RB6"]
    assert any("ไม่พบราคาที่จังหวัดภูเก็ตประกาศ" in n for n in r["notes"])
    rates = Q.to_rates(r)                                # ปร.4 หมายเหตุ
    assert any("ร้าน ข." in x["note"] for x in rates)
    assert "q=" in P.market_search_url("ทรายหยาบ", "ภูเก็ต")


#: Phuket, September 2569, as the ministry's site lists it (several brands
#: and strengths of ready-mixed concrete, cement by the ton, bagged items).
PHUKET = [
    ["รหัสหมวด", "ชื่อหมวดสินค้า", "รหัส", "รายการ", "หน่วย", "กันยายน"],
    ["01", "วัสดุเทหล่อกับที่", "0101010100100000",
     "คอนกรีตผสมเสร็จรูปลูกบาศก์ 180 กก./ตร.ซม. และ รูปทรงกระบอก 140กก./ตร.ซม. ตราซีแพค",
     "ลบ.ม.", "2,900.00"],
    ["01", "วัสดุเทหล่อกับที่", "0101010100200000",
     "คอนกรีตผสมเสร็จรูปลูกบาศก์ 210 กก./ตร.ซม. และ รูปทรงกระบอก 180 กก./ตร.ซม. ตราซีแพค",
     "ลบ.ม.", "2,960.00"],
    ["01", "วัสดุเทหล่อกับที่", "0101010100300000",
     "คอนกรีตผสมเสร็จรูปลูกบาศก์ 240 กก./ตร.ซม. และรูปทรงกระบอก 210 กก./ตร.ซม. ตราซีแพค",
     "ลบ.ม.", "3,020.00"],
    ["01", "วัสดุเทหล่อกับที่", "0101010100400000",
     "คอนกรีตผสมเสร็จรูปลูกบาศก์ 280 กก./ตร.ซม. และ รูปทรงกระบอก 240 กก./ตร.ซม. ตราซีแพค",
     "ลบ.ม.", "3,080.00"],
    ["15", "วัสดุซีเมนต์", "1502030100100000",
     "ปูนซีเมนต์ผสม ปูนถุง บรรจุ 50 กก./ถุง ตราเสือ", "ตัน", "2,950.00"],
    ["15", "วัสดุซีเมนต์", "1506010106400000",
     "ปูนกาวซีเมนต์ บรรจุ 20 กก./ถุง ตราจระเข้ รุ่นเกเตอร์", "ถุง", "180.00"],
    ["04", "เหล็ก", "0401020101100000",
     "เหล็กเส้นกลมผิวข้ออ้อย SD.30 มอก. 24-2559 ขนาดเส้นผ่านศูนย์กลาง 12 มม. ยาว 10 เมตร",
     "ตัน", "23,500.00"],
    ["04", "เหล็ก", "0401020200300000",
     "เหล็กเส้นกลมผิวข้ออ้อย SD.40 ยาว 10 เมตร ศก. 12 มม.", "ตัน", "24,400.00"],
    ["02", "วัสดุก่อ", "0205010101300000",
     "อิฐมอญ บรรจุ 100 ก้อน/ถุง ขนาด 6 x 14 x 3 ซม. ตรา GIANT KINGKONG",
     "100 ก้อน/ถุง", "150.00"],
    ["04", "เหล็ก", "0402040200400000",
     "เหล็กตัวซี (Light Lip Channel Steel) หนา 3.2 มม. ยาว 6 เมตร ขนาด 100 x 50 x 20 มม. น้ำหนัก 34.0 กก./ท่อน",
     "ท่อน", "1,020.00"],
    ["09", "วัสดุแผ่น", "0915010100400000", "กระจกใส หนา 5 มม.", "ตร.ฟุต",
     "55.00"],
]


def test_phuket_prices_reach_the_boq_units():
    keys = {"คอนกรีตผสมเสร็จ 240 กก./ตร.ซม. (ลูกบาศก์)": "ลบ.ม.",
            "ปูนซีเมนต์ผสม (มอก. 80/2566)": "กก.", "ปูนกาวซีเมนต์ หนา 5 มม.": "กก.",
            "DB12": "กก.", "อิฐมอญ (อิฐก่อสร้างสามัญ) ขนาด 7 x 16 x 3.5 ซม.": "ก้อน",
            "เหล็กรูปพรรณ (ทั่วไป)": "กก.", "กระจกใส 5 มม.": "ตร.ฟ.",
            "ปูนซีเมนต์ปอร์ตแลนด์ (มอก. 15-2562) หรือปูนซีเมนต์ไฮดรอลิก "
            "(มอก. 2594-2567)": "กก."}
    got = P.match(P.parse_rows(PHUKET), list(keys), keys)
    c240 = got["คอนกรีตผสมเสร็จ 240 กก./ตร.ซม. (ลูกบาศก์)"]
    assert c240[0] == 3020.0 and "240" in c240[1] and "ตราซีแพค" in c240[1]
    assert got["ปูนซีเมนต์ผสม (มอก. 80/2566)"][0] == 2.95        # ตัน → กก.
    assert got["ปูนกาวซีเมนต์ หนา 5 มม."][0] == 9.0               # 180 / 20 กก.
    assert got["DB12"][0] == 24.4 and "SD.40" in got["DB12"][1]   # not SD.30
    assert got["อิฐมอญ (อิฐก่อสร้างสามัญ) ขนาด 7 x 16 x 3.5 ซม."][0] == 1.5
    assert got["เหล็กรูปพรรณ (ทั่วไป)"][0] == 30.0                # 1020 / 34
    assert got["กระจกใส 5 มม."][0] == 55.0
    # No Portland cement in the table: nothing is guessed for it.
    assert not any(k.startswith("ปูนซีเมนต์ปอร์ตแลนด์") for k in got)


def test_unit_factors():
    assert P.unit_factor("x", "ตัน", "กก.") == 0.001
    assert P.unit_factor("ยาแนว บรรจุ 1 กก./ถุง", "ถุง", "กก.") == 1.0
    assert P.unit_factor("x", "ตร.ฟุต", "ตร.ม.") == 10.7639
    assert P.unit_factor("สี ขนาด 18.925 ลิตร", "ถัง", "ลิตร") == 1 / 18.925
    assert P.unit_factor("สีน้ำ 18.925 ลิตร", "ถัง", "ตร.ม.") is None
    assert P.unit_factor("ทรายหยาบ", "ลบ.ม.", "ลบ.ม.") == 1.0
    f = P.unit_factor("กระเบื้อง ขนาด 12x12 (11แผ่น/กล่อง)", "กล่อง", "ตร.ม.")
    assert abs(1 / f - 11 * 0.3048 ** 2) < 1e-6


def test_the_bill_note_names_the_commerce_item():
    from core import wanic_quantities as Q
    assert Q.market_note("ภูเก็ต", "พาณิชย์", 3020, "", "คอนกรีต … ตราซีแพค") == \
        "ราคาพาณิชย์จ.ภูเก็ต: คอนกรีต … ตราซีแพค"
