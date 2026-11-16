# SPDX-License-Identifier: GPL-3.0-or-later
"""«ถอดแบบตาม BOQ»: the bill printed in a drawing set read into ปร.1 CSV by kind of work,
every page reported (อ่านได้ / อ่านได้บางส่วน / อ่านไม่ได้), the old Thai font decoded,
sheet numbers OCR missed filled from their neighbours."""
from __future__ import annotations

import csv
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("READWANICN_OFFLINE", "1")

import pymupdf

from readwanicn import boqread as B

FONT = os.path.join(os.path.dirname(__file__), "..", "assets", "Laksaman.ttf")
COLS = {"ลำดับที่": 40, "รายการ": 200, "จำนวน": 420, "หน่วย": 470, "ราคาหน่วยละ": 520, "จำนวนเงิน": 590,
        "รวมค่าวัสดุ": 700, "หมายเหตุ": 780}


def _text(page, x, y, s, size=9):
    page.insert_text((x, y), s, fontname="th", fontfile=FONT, fontsize=size)


def make_set(path):
    doc = pymupdf.open()
    # 1: a bill (ปร.4) with a group, a section, items and a total
    p = doc.new_page(width=842, height=595)
    _text(p, 200, 40, "รายการประมาณราคาค่าก่อสร้าง อาคารเรียน 2 ชั้น (ทดสอบ)", 12)
    _text(p, 760, 60, "แบบ ปร.4")
    for name, x in COLS.items():
        _text(p, x, 100, name)
    rows = [("1", "หมวดงานโครงสร้าง", "", ""),
            ("", "- ขุดดิน", "47", "ลบ.ม."),
            ("", "- คอนกรีตโครงสร้าง 1:2:4", "25", "ลบ.ม."),
            ("", "1.1 งานเหล็กรูปพรรณ", "", ""),
            ("", "- C 100 x 50 x 20 x 3.2 มม.", "693", "กก."),
            ("2", "หมวดงานสถาปัตยกรรม", "", ""),
            ("", "- ผนังก่ออิฐมอญครึ่งแผ่น", "120", "ตร.ม."),
            ("", "รวมหมวดงานสถาปัตยกรรม", "", "")]
    y = 125
    for no, name, qty, unit in rows:
        if no:
            _text(p, 40, y, no)
        _text(p, 60, y, name)
        if qty:
            _text(p, 420, y, qty)
            _text(p, 470, y, unit)
            _text(p, 520, y, "100")
        y += 20
    _text(p, 700, 560, "แผ่นที่ 1 / 1")
    # 2: a drawing with real text: sheet number, title, tags
    p = doc.new_page(width=842, height=595)
    for k in range(12):
        _text(p, 60 + 50 * (k % 6), 100 + 40 * (k // 6), "ป1" if k % 3 else "น2")
    _text(p, 80, 300, "หมายเหตุ ให้ตรวจสอบระยะในสนามก่อนก่อสร้าง ทุกจุด ตามรายการประกอบแบบ " * 2)
    for k in range(20):
        _text(p, 60, 340 + 10 * k, f"ระยะ {k}.00 ม. ผนัง ก่ออิฐ ฉาบปูน เรียบ")
    p.draw_rect(pymupdf.Rect(20, 20, 822, 575))
    _text(p, 720, 520, "แปลนพื้นชั้น 1")
    _text(p, 740, 560, "A-04")
    # 3: an empty page
    doc.new_page(width=842, height=595)
    doc.save(path)


def test_set_reads_bill_and_reports_each_page(tmp_path):
    src = tmp_path / "ชุดแบบ.pdf"
    make_set(src)
    res = B.analyse(src, ocr=False)
    assert [p.status for p in res.pages] == ["อ่านได้", "อ่านได้บางส่วน", "อ่านไม่ได้"]
    names = [ln.name for ln in res.lines]
    assert names == ["ขุดดิน", "คอนกรีตโครงสร้าง 1:2:4", "C 100 x 50 x 20 x 3.2 มม.", "ผนังก่ออิฐมอญครึ่งแผ่น"]
    first = res.lines[0]
    assert (first.qty, first.unit, first.group, first.work) == (47, "ลบ.ม.", "หมวดงานโครงสร้าง", "อาคาร")
    assert first.mat_u == 100
    assert res.lines[2].section.startswith("1.1 งานเหล็กรูปพรรณ")
    assert res.lines[3].group == "หมวดงานสถาปัตยกรรม"
    assert "อาคารเรียน 2 ชั้น" in first.bill
    sheet = res.pages[1]
    assert sheet.sheet == "A-04" and sheet.discipline == "สถาปัตยกรรม"
    assert sheet.tags == {"ป1": 8, "น2": 4}
    assert res.tags["ป1"] == {2: 8}

    files = B.write_csv(res, tmp_path / "out", {"place": "ทดสอบ"})
    names = [f.name for f in files]
    assert any("ปร.1 งานอาคาร" in n for n in names)
    assert any("ป้ายที่นับจากแบบ" in n for n in names)
    assert any("รายงานการอ่านแบบ" in n for n in names)
    rows = list(csv.reader(open(next(f for f in files if "ปร.1" in f.name), encoding="utf-8-sig")))
    assert rows[0][-1] == "แบบ ปร.1"
    assert rows[7] == B.PR1_HEADERS
    body = [r[:4] for r in rows[8:]]
    assert body == [["1", "หมวดงานโครงสร้าง", "", ""], ["1.1", "ขุดดิน", "47", "ลบ.ม."],
                    ["1.2", "คอนกรีตโครงสร้าง 1:2:4", "25", "ลบ.ม."], ["1.3", "งานเหล็กรูปพรรณ", "", ""],
                    ["1.3.1", "C 100 x 50 x 20 x 3.2 มม.", "693", "กก."], ["2", "หมวดงานสถาปัตยกรรม", "", ""],
                    ["2.1", "ผนังก่ออิฐมอญครึ่งแผ่น", "120", "ตร.ม."]]
    report = list(csv.reader(open(next(f for f in files if "รายงาน" in f.name), encoding="utf-8-sig")))
    assert report[3][:2] == ["1", "อ่านได้"] and report[5][:2] == ["3", "อ่านไม่ได้"]


def test_old_thai_font_decoded():
    # «หมวดงานโครงสร้าง» and «เหล็กเสริม SR 24 Ø 6 มม.» as the old fonts store them
    enc = "".join(chr(ord(c) - 0xD2B) if "ก" <= c <= "ฺ" else c for c in "หมวดงานโครงสร้าง")
    assert B.decode_legacy(enc) == "หมวดงานโครงสร้าง"
    assert B.decode_legacy("đĀúĘ").startswith("เ")
    assert B.decode_legacy("SR 24 Ø 6") == "SR 24 Ø 6"
    assert B.looks_legacy(enc * 3)
    assert not B.looks_legacy("หมวดงานโครงสร้าง " * 3)


def test_sheet_numbers_from_neighbours():
    pages = [B.Page(no=i + 1, kind="ภาพสแกน", sheet=s, status="อ่านได้บางส่วน", note="")
             for i, s in enumerate(["", "A-02", "A-03", "", "A-05", "A-08", "A-07", "S-01", "", "S-03", ""])]
    B._fix_sequence(pages)
    assert [p.sheet for p in pages] == ["A-01", "A-02", "A-03", "A-04", "A-05", "A-06", "A-07", "S-01", "S-02",
                                        "S-03", "S-04"]
    assert pages[5].note.startswith("เลขแผ่นคาดจากลำดับแผ่น (อ่านได้ «A-08»)")


def test_ocr_title_block_text():
    text = "สำนักสถาปัตยกรรม\nอธิบตีกรมโยธาธิการและผังเมือง\nแสตงแบบ\nแปลนพื้นชั้น 1\nมาตราส่วน 1:100\nA-O4"
    assert B._sheet_from_text(text, ocr=True) == ("A-04", "แปลนพื้นชั้น 1")
    assert B.thai_join("แบ บ ขยาย ห น้ า ต่ า ง A-01") == "แบบขยายหน้าต่าง A-01"
    assert B._work_of("ถนนลาดยาง ไหล่ทาง ผิวจราจร กม.") == "ทาง"
    assert B._work_of("ฝาย คลอง ส่งน้ำ") == "ชลประทาน"
    assert B._work_of("แปลนพื้น บ้าน ทางเดิน") == "อาคาร"


def test_dialog_shows_result(tmp_path):
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    from readwanicn.boqread_view import BoqDialog
    src = tmp_path / "ชุดแบบ.pdf"
    make_set(src)
    d = BoqDialog(src)
    import time
    end = time.time() + 60
    while not d.res and time.time() < end:
        app.processEvents()
        time.sleep(0.02)
    assert d.res and d.items.rowCount() == 4 and d.pages.rowCount() == 3
    assert d.csv_btn.isEnabled()
    d.reject()
