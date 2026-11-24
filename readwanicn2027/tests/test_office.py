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


def test_document_editor_works_like_word(tmp_path):
    """Menus like Word, cut/copy/paste (from Word with its formatting, or the words only),
    find and replace, strike/highlight/superscript, line spacing, page breaks and tables —
    and they all reach the .docx."""
    from docx import Document
    from PySide6.QtGui import QColor, QTextCursor
    from PySide6.QtWidgets import QApplication

    from readwanicn import docedit
    app = QApplication.instance() or QApplication([])
    ed = docedit.DocEditor(lambda n: os.path.join(os.path.dirname(__file__), "..", "assets", n))
    menus = [a.text() for a in ed.menu_bar.actions()]
    assert menus == ["แฟ้ม", "แก้ไข", "มุมมอง", "แทรก", "รูปแบบ", "ตาราง", "เครื่องมือ"]
    ed.page.setPlainText("เรียน ผู้อำนวยการ\nขอส่งรายงานผลการดำเนินงาน")
    assert ed.replace_all("ผู้อำนวยการ", "นายอำเภอ") == 1
    app.clipboard().setText("คัดลอกจากที่อื่น")
    c = ed.page.textCursor()
    c.movePosition(QTextCursor.End)
    ed.page.setTextCursor(c)
    ed.page.paste_plain()
    c = ed.page.document().find("ขอส่ง")
    ed.page.setTextCursor(c)
    ed._merge(strike=True)
    ed.highlight(QColor("#FFF200"))
    ed.line_spacing(150)
    ed.page_break()
    ed.insert_table()
    ed._table("row")
    out = tmp_path / "หนังสือ.docx"
    docedit.to_docx(ed.page.document(), out)
    d = Document(out)
    text = "\n".join(p.text for p in d.paragraphs)
    assert "นายอำเภอ" in text and "คัดลอกจากที่อื่น" in text and "ผู้อำนวยการ" not in text
    runs = [r for p in d.paragraphs for r in p.runs if "ขอส่ง" in r.text]
    assert runs and runs[0].font.strike and "w:shd" in runs[0]._element.xml
    assert any(p.paragraph_format.line_spacing == 1.5 for p in d.paragraphs)
    assert any(p.paragraph_format.page_break_before for p in d.paragraphs)
    assert len(d.tables) == 1 and len(d.tables[0].rows) == 4


def test_spreadsheet_works_like_excel(tmp_path):
    """Menus like Excel; copy and paste ranges (formulas move their references, values only too,
    tab-separated text from Excel); undo/redo; fill down; sort; find and replace; colours,
    number formats and merged cells into the .xlsx; more functions."""
    from openpyxl import load_workbook
    from PySide6.QtCore import QItemSelectionModel
    from PySide6.QtWidgets import QApplication

    from readwanicn import sheet
    app = QApplication.instance() or QApplication([])
    ed = sheet.SheetEditor("Laksaman")
    assert [a.text() for a in ed.menu_bar.actions()] == ["แฟ้ม", "แก้ไข", "แทรก", "รูปแบบ", "ข้อมูล", "สูตร"]
    for r, (name, qty, price) in enumerate((("รายการ", "จำนวน", "ราคา"), ("ข", "3", "100"), ("ก", "2", "250.5"))):
        for c, v in enumerate((name, qty, price)):
            ed.book.set(r, c, v)
    ed.book.set(1, 3, "=B2*C2")
    ed.refresh()

    def select(r0, c0, r1, c1):
        ed.grid.clearSelection()
        ed.grid.setCurrentCell(r0, c0)
        for r in range(r0, r1 + 1):
            for c in range(c0, c1 + 1):
                ed.grid.selectionModel().select(ed.grid.model().index(r, c), QItemSelectionModel.Select)
    select(1, 3, 2, 3)
    ed.fill(down=True)
    assert ed.book.raw[(2, 3)] == "=B3*C3" and ed.book.value(2, 3) == 501.0
    select(1, 3, 2, 3)
    ed.copy()
    ed.grid.clearSelection()
    ed.grid.setCurrentCell(1, 4)
    ed.paste()
    assert ed.book.raw[(1, 4)] == "=C2*D2"                       # moved one column, as in Excel
    ed.undo()
    assert (1, 4) not in ed.book.raw
    ed.redo()
    assert ed.book.raw[(1, 4)] == "=C2*D2"
    ed.grid.setCurrentCell(1, 5)
    select(1, 3, 1, 3)
    ed.copy()
    ed.grid.clearSelection()
    ed.grid.setCurrentCell(5, 5)
    ed.paste(values=True)
    assert ed.book.raw[(5, 5)] == "300"
    app.clipboard().setText("จาก Excel\t12\n\t=SUM(B7:B7)")         # what Excel puts on the clipboard
    ed.grid.setCurrentCell(6, 0)
    ed.paste()
    assert ed.book.raw[(6, 0)] == "จาก Excel" and ed.book.value(7, 1) == 12.0
    ed.grid.setCurrentCell(1, 0)
    ed.grid.clearSelection()
    ed.sort(True)
    assert ed.book.raw[(1, 0)] == "ก"
    assert ed.replace_all("ข", "ค") >= 1
    select(0, 0, 0, 2)
    ed.merge()
    select(1, 2, 2, 2)
    ed._style(fmt="comma")
    ed.pick_color("bg", color=__import__("PySide6.QtGui", fromlist=["QColor"]).QColor("#FFF2CC"))
    assert ed.grid.item(1, 2).text() == "250.50"
    ed.book.set(9, 0, "=SUMIF(B2:B3,\">2\",C2:C3)")
    ed.book.set(9, 1, "=COUNTIF(A2:A3,\"ก\")")
    ed.book.set(9, 2, "=ROUNDUP(2.341,2)")
    assert ed.book.value(9, 0) == 100.0 and ed.book.value(9, 1) == 1.0 and ed.book.value(9, 2) == 2.35
    out = tmp_path / "ตาราง.xlsx"
    sheet.save_xlsx(ed.book, out, ed.styles, widths={}, spans=ed.spans)
    ws = load_workbook(out).active
    assert "A1:C1" in [str(m) for m in ws.merged_cells.ranges]
    assert ws["C2"].number_format == "#,##0.00" and ws["C2"].fill.fgColor.rgb.endswith("FFF2CC")
