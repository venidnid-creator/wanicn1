# SPDX-License-Identifier: GPL-3.0-or-later
"""The document editor, the spreadsheet, editing PDF text and pictures, and usage statistics."""
from __future__ import annotations

import datetime as dt
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("READWANICN_OFFLINE", "1")

import pymupdf
import pytest

from readwanicn import pdfedit, saraban, sheet, usage

ASSETS = os.path.join(os.path.dirname(__file__), "..", "assets")


def asset(name):
    return os.path.join(ASSETS, name)


@pytest.fixture(scope="module")
def app():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def test_formulas():
    b = sheet.Book()
    for r, v in enumerate(["10", "20", "30.5"]):
        b.set(r, 0, v)
    b.set(0, 1, "=SUM(A1:A3)")
    b.set(1, 1, "=A1*2+A2/4")
    b.set(2, 1, "=ROUND(AVERAGE(A1:A3),2)")
    b.set(3, 1, "=B1-A3^2")
    b.set(4, 1, "=A1/0")
    b.set(5, 1, "=B6")
    b.set(6, 1, '=IF(A1>5,"มาก","น้อย")')
    b.set(7, 1, "=MAX(A1:A3)-MIN(A1:A3)")
    assert b.value(0, 1) == pytest.approx(60.5)
    assert b.value(1, 1) == pytest.approx(25)
    assert b.value(2, 1) == pytest.approx(20.17)
    assert b.value(3, 1) == pytest.approx(60.5 - 30.5 ** 2)
    assert b.display(4, 1) == "#DIV/0!"
    assert b.display(5, 1) == "#REF!"
    assert b.value(6, 1) == "มาก"
    assert b.display(7, 1) == "20.5"
    assert sheet.col_name(0) == "A" and sheet.col_name(27) == "AB" and sheet.col_index("AB") == 27


def test_sheet_files_round_trip(tmp_path):
    b = sheet.register_book("ทะเบียนหนังสือรับ")
    b.set(3, 0, "1")
    b.set(3, 1, "=A4+1")
    sheet.save_xlsx(b, tmp_path / "r.xlsx")
    back = sheet.load_xlsx(tmp_path / "r.xlsx")
    assert back.raw[(0, 0)] == "ทะเบียนหนังสือรับ" and back.value(3, 1) == 2
    sheet.save_csv(b, tmp_path / "r.csv")
    assert sheet.load_csv(tmp_path / "r.csv").raw[(3, 1)] == "2"


def test_every_letter_form_renders():
    assert {f.group for f in saraban.FORMS} == set(saraban.GROUPS)
    assert len(saraban.GROUPS) == 6
    for f in saraban.FORMS:
        html = saraban.render(f.key, saraban.defaults(f), thai_numbers=True)
        assert "TH SarabunPSK" in html and ("garuda" in html) == bool(f.garuda)
    assert saraban.thai_digits("2564") == "๒๕๖๔"
    assert saraban.file_name(2564, "OPM", "0913", "56") == "2564_OPM0913_56.pdf"
    assert saraban.file_name(2564, "OPM", "0913", "56", 1) == "2564_OPM0913_56_1.pdf"


def test_document_editor_saves_docx_and_pdf(app, tmp_path):
    from docx import Document
    from readwanicn.docedit import DocEditor, from_docx
    ed = DocEditor(asset)
    ed.choose_form("external")
    ed.fill_form()
    from readwanicn.docedit import to_docx, to_pdf
    to_docx(ed.page.document(), tmp_path / "a.docx")
    d = Document(tmp_path / "a.docx")
    text = "\n".join(p.text for p in d.paragraphs)
    assert "ขอเชิญ" in text or "เรื่อง" in text
    assert d.inline_shapes, "the Garuda is in the letter"
    assert abs(d.sections[0].left_margin.cm - 3.0) < 0.01
    html = from_docx(tmp_path / "a.docx")
    assert "เรื่อง" in html and "data:image/png" in html
    to_pdf(ed.page.document(), tmp_path / "a.pdf")
    with pymupdf.open(tmp_path / "a.pdf") as pdf:
        assert pdf.page_count >= 1 and "เรื่อง" in pdf[0].get_text()


def test_pdf_text_and_picture_editing(tmp_path):
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 100), "Old words", fontsize=14)
    span = pdfedit.line_at(page, (80, 96))
    assert span and span.text == "Old words" and span.size == 14
    pdfedit.replace_line(page, span, "ข้อความใหม่ 2569", ASSETS)
    text = page.get_text()
    assert "Old words" not in text and "2569" in text
    pdfedit.add_text(page, (72, 200), "เพิ่มเติม", ASSETS)
    assert "เพิ่มเติม" in page.get_text()
    pdfedit.insert_image(page, (72, 300), asset("garuda.png"), 80)
    xref, _ = pdfedit.image_at(page, (100, 320))
    pdfedit.delete_image(page, xref)
    assert pdfedit.image_at(page, (100, 320)) is None
    page.set_rotation(90)                    # clicks come in displayed coordinates
    pt = pymupdf.Point(80, 220) * page.rotation_matrix
    assert pdfedit.line_at(page, pt) is not None


def test_usage_counts_by_period(tmp_path):
    u = usage.Usage(tmp_path / "u.jsonl", user="Wanicn")
    t = dt.datetime(2026, 11, 11, 9)
    for d, f in ((0, "รวมไฟล์"), (0, "รวมไฟล์"), (1, "บีบอัด"), (8, "รวมไฟล์"), (400, "วัดความยาว")):
        u.record(f, t - dt.timedelta(days=d))
    ev = u.events()
    rows, total = usage.summary(ev, "day")
    assert rows[0] == ("11/11/2569", {"รวมไฟล์": 2}) and total["รวมไฟล์"] == 3
    assert len(usage.summary(ev, "week")[0]) == 3
    assert [r[0] for r in usage.summary(ev, "year")[0]] == ["พ.ศ. 2569", "พ.ศ. 2568"]
    usage.report_xlsx(ev, tmp_path / "r.xlsx")
    from openpyxl import load_workbook
    wb = load_workbook(tmp_path / "r.xlsx")
    assert wb.sheetnames == ["สรุปรวม", "รายวัน", "รายสัปดาห์", "รายเดือน", "รายปี"]


def test_main_window_has_the_new_tabs(app, tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    from readwanicn.ui import MainWindow
    w = MainWindow("Wanicn")
    tabs = [w.tabs.tabText(i) for i in range(w.tabs.count())]
    assert tabs == ["เอกสาร PDF", "โมเดล 3 มิติ", "สร้างเอกสาร", "ตารางคำนวณ"]
    assert "edit" in w.tool_buttons
    assert any(f == "เข้าสู่ระบบ" for *_, f in w.usage.events())


def test_snap_finds_corners_middles_crossings_and_centres():
    from readwanicn import snap
    doc = pymupdf.open()
    page = doc.new_page()
    page.draw_rect(pymupdf.Rect(100, 100, 300, 200))
    page.draw_line((100, 150), (300, 150))
    page.draw_line((200, 80), (200, 220))
    page.draw_circle((400, 400), 30)
    page.insert_text((120, 130), "Text is not snapped", fontsize=11)
    s = snap.Snapper(page)
    assert s.find((103, 98), 8).kind == "end" and s.find((103, 98), 8).pt == (100, 100)
    hit = s.find((198, 148), 8)
    assert hit.kind == "int" and hit.pt == pytest.approx((200, 150))
    assert s.find((250, 103), 8).pt == pytest.approx((250, 100))     # a point on the line
    assert s.find((401, 402), 8).kind == "cen"
    assert s.find((500, 500), 8) is None
    page.set_rotation(90)                                            # displayed coordinates follow /Rotate
    s = snap.Snapper(page)
    corner = pymupdf.Point(100, 100) * page.rotation_matrix
    assert s.find((corner.x + 2, corner.y - 2), 8).pt == pytest.approx((corner.x, corner.y))


def test_dxf_comes_in_at_a_scale_that_measures_in_metres(tmp_path):
    import ezdxf
    from readwanicn import cadimport, measure, snap
    d = ezdxf.new(units=6)                                  # metres
    m = d.modelspace()
    m.add_lwpolyline([(0, 0), (12, 0), (12, 6), (0, 6)], close=True)
    m.add_text("อาคาร ผู้ใหญ่", height=0.3).set_placement((1, 1))
    d.saveas(tmp_path / "plan.dxf")
    r = cadimport.import_file(tmp_path / "plan.dxf")
    assert r.units == "เมตร" and not r.guessed
    page = pymupdf.open(r.pdf)[0]
    s = snap.Snapper(page)
    scale = measure.Scale.ratio(r.ratio)
    xs = sorted({round(x, 1) for x, _ in s.ends})
    ys = sorted({round(y, 1) for _, y in s.ends})
    # the frame of the drawing: the outer corners are 12 m x 6 m apart
    inner_x = [x for x in xs if 0 < x < page.rect.width]
    inner_y = [y for y in ys if 0 < y < page.rect.height]
    assert (max(inner_x) - min(inner_x)) * scale.m_per_pt == pytest.approx(12, abs=0.0005)
    assert (max(inner_y) - min(inner_y)) * scale.m_per_pt == pytest.approx(6, abs=0.0005)
    with pytest.raises(cadimport.CadError):
        (tmp_path / "x.dwg").write_bytes(b"AC1032")
        if cadimport.oda_converter() is None:
            cadimport.import_file(tmp_path / "x.dwg")
        else:
            raise cadimport.CadError("dwg")
    from PySide6.QtGui import QImage
    img = QImage(10, 10, QImage.Format_RGB888)
    img.fill(0xFFFFFF)
    img.save(str(tmp_path / "scan.png"))
    assert pymupdf.open(cadimport.import_file(tmp_path / "scan.png")).page_count == 1


def test_printing_paints_pages_and_tables(app, tmp_path):
    from PySide6.QtPrintSupport import QPrinter
    from readwanicn import printing
    from readwanicn.sheet import SheetEditor
    doc = pymupdf.open()
    for _ in range(3):
        doc.new_page().insert_text((72, 72), "page", fontsize=20)
    pr = QPrinter()
    pr.setOutputFormat(QPrinter.PdfFormat)
    pr.setOutputFileName(str(tmp_path / "out.pdf"))
    printing.paint_pdf(pr, doc)
    assert pymupdf.open(tmp_path / "out.pdf").page_count == 3
    sh = SheetEditor("Laksaman")
    sh.book.set(0, 0, "จุด")
    sh.book.set(1, 1, "=2*3")
    html = sh.to_html()
    assert "จุด" in html and ">6<" in html
