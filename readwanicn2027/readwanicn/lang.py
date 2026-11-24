# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2569 (2026) นายเวนิช ธัมมะวงษ์ วิศวกรสำรวจ — ReadWanicn2027
"""ไทย / EN for the program's own screens, like the WANICNSURVEY start screen.

The screens are written in Thai; switching to English walks the window and puts the
English words in place (the Thai is kept on each widget to switch back). Government
forms and reports (ว651, ว124, ว78, saraban letters) stay in Thai: they are official
documents."""
from __future__ import annotations

import os

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import (QAbstractButton, QComboBox, QGroupBox, QLabel, QLineEdit, QTableWidget,
                               QTabWidget, QWidget)

EN = {
    # top bar
    "☰ เมนู": "☰ Menu", "ซ่อน/แสดงแถบเครื่องมือ": "Hide/show the tool rows",
    "ยังไม่ได้เปิดไฟล์": "No file open", "📊 ดาวน์โหลดสะสม — ": "📊 Downloads — ",
    "จำนวนครั้งที่ดาวน์โหลดตัวติดตั้งจากหน้า Releases": "Installer downloads from the Releases page",
    "⬇ มีเวอร์ชันใหม่": "⬇ New version", "🏗 ปรับลดราคา ว651 · ว124 · ว78": "🏗 Price reduction · work plan · materials",
    "📐 ถอดแบบตาม BOQ": "📐 Take-off to BOQ",
    "📊 สถิติการใช้งาน": "📊 Usage", "▤ แผงไฟล์": "▤ Files panel", "▥ แผงวัด": "▥ Measure panel",
    "ธีม": "Theme", "ธีม:": "Theme:", "ภาษา": "Language",
    "บลูพริ้นท์": "Blueprint", "สว่าง": "Light", "มืด": "Dark", "ทองเวนิช": "Venit Gold", "เขียวสำรวจ": "Survey Green",
    # file row
    "เปิดไฟล์": "Open", "นำเข้าแบบ": "Import drawing", "พิมพ์": "Print", "บันทึก": "Save", "บันทึกเป็น": "Save as",
    "บันทึกงานวัด": "Save take-off", "รวมไฟล์": "Combine", "บีบอัด": "Compress", "ลบหน้า": "Delete page",
    "หมุนหน้า": "Rotate page", "ลบไฟล์": "Remove file", "ส่งออกตารางคำนวณ": "Export spreadsheet",
    "ส่งออกตารางข้อมูล": "Export CSV", "ส่งออกเอกสาร": "Export document",
    "เปิดไฟล์ PDF, ไฟล์เขียนแบบ (.dxf .dwg .svg) รูปภาพแบบ หรืองานวัด .json":
        "Open a PDF, a drawing (.dxf .dwg .svg), a picture of a drawing or a take-off .json",
    "นำเข้าไฟล์เขียนแบบ .dxf / .dwg / .svg หรือรูปภาพแบบ แล้ววัดได้ทันทีตามสเกล":
        "Import a .dxf / .dwg / .svg drawing or a picture and measure it to scale",
    "พิมพ์เอกสารไปที่เครื่องพิมพ์ (Ctrl+P)": "Print the document (Ctrl+P)",
    "บันทึกไฟล์ PDF ที่แก้ไข (ลบ/หมุนหน้า)": "Save the edited PDF (pages deleted/rotated)",
    "บันทึก PDF เป็นไฟล์ใหม่": "Save the PDF as a new file",
    "บันทึกรายการวัดทั้งหมดเป็นไฟล์ .json": "Save every measurement as a .json file",
    "รวมหลายไฟล์ PDF เป็นไฟล์เดียว": "Combine several PDFs into one",
    "บีบอัด PDF: คุณภาพสูง / กลาง / ต่ำ": "Compress the PDF: high / medium / low quality",
    "ลบหน้าที่เลือก": "Delete the selected pages", "หมุนหน้า 90°": "Rotate the page 90°",
    "ปิดไฟล์ออกจากรายการ หรือลบไฟล์ทิ้ง": "Close the file or delete it",
    "ข้อความและตารางในเอกสารเป็นไฟล์ตารางคำนวณ (.xlsx)": "Text and tables of the document as a spreadsheet (.xlsx)",
    "ข้อความและตารางในเอกสารเป็นไฟล์ข้อมูลคั่นด้วยจุลภาค (.csv)": "Text and tables of the document as CSV",
    "ข้อความและตารางในเอกสารเป็นไฟล์เอกสาร (.docx)": "Text and tables of the document as a document (.docx)",
    # measure row
    "เลื่อน": "Pan", "ตั้งสเกล": "Set scale", "วัดความยาว": "Length", "คิดพื้นที่": "Area", "นับจำนวน": "Count",
    "แก้ไขข้อความและรูปภาพ": "Edit text and pictures", "รูปทรง ▾": "Shapes ▾", "รูปทรง": "Shapes",
    "อ่านรูปทรงจากแบบ (คลิกในรูป)": "Read the shape from the drawing (click inside)",
    "อ่านรูปทรงจากแบบ ▾": "Read shape ▾", "สี่เหลี่ยม ▾": "Rectangle ▾", "วงกลม ▾": "Circle ▾",
    "สามเหลี่ยม ▾": "Triangle ▾", "สี่เหลี่ยม": "Rectangle", "วงกลม": "Circle", "สามเหลี่ยม": "Triangle",
    "ยึดจุด": "Snap", "รายงานงานวัด": "Take-off report", "ย่อ": "Zoom out", "ขยาย": "Zoom in", "พอดีจอ": "Fit",
    "โมเดล 3 มิติ": "3D model", "ย่อ/ขยายให้พอดีหน้าจอ": "Zoom to fit the screen",
    "ดูและหมุนโมเดล 3 มิติ": "View and turn a 3D model",
    "รายงานงานวัดเป็นไฟล์ตารางคำนวณ (.xlsx) หรือ .csv": "Take-off report as a spreadsheet (.xlsx) or .csv",
    # panels and tabs
    "ไฟล์ที่เปิดอยู่": "Open files", "+ เพิ่ม": "+ Add", "หน้า": "Pages", "เอกสาร PDF": "PDF",
    "สร้างเอกสาร": "Documents", "ตารางคำนวณ": "Spreadsheet", "สเกลแบบ": "Drawing scale",
    "— เลือกสเกลมาตรฐาน —": "— standard scale —", "ใช้": "Use", "ผลรวม": "Totals",
    "ยังไม่มีรายการวัด": "No measurements yet", "รายการวัด": "Measurements", "ลบรายการ": "Delete",
    "ล้างหน้านี้": "Clear page", "ประเภท": "Kind", "รายการ": "Item", "ปริมาณ": "Quantity",
    "ชื่อรายการวัดถัดไป (เช่น ผนังก่ออิฐ, พื้นห้องนอน):": "Name of the next measurement (e.g. brick wall, bedroom floor):",
    "ไม่ใส่ก็ได้": "optional", "ลากไฟล์ PDF มาวางที่นี่": "Drop PDF files here",
    "หรือกดปุ่มด้านล่างเพื่อเปิดไฟล์ (เปิดได้หลายไฟล์พร้อมกัน)": "or press the button below (several files at once)",
    "📂 เปิดไฟล์ PDF": "📂 Open PDF", "📂 เปิดโมเดล (.stl .obj)": "📂 Open model (.stl .obj)",
    "⟲ หมุนซ้าย": "⟲ Turn left", "⟳ หมุนขวา": "⟳ Turn right", "⏯ หมุนอัตโนมัติ": "⏯ Auto-rotate",
    "⌂ มุมมองเริ่มต้น": "⌂ Home view",
    "สเกล 1:N ใช้ได้เมื่อพิมพ์แบบขนาดจริงของกระดาษ หากแบบถูกย่อ ให้ใช้ปุ่ม «ตั้งสเกล» คลิก 2 จุดบนระยะที่รู้ค่า":
        "1:N works when the drawing is at its paper size; if it was shrunk, use «Set scale» and click "
        "2 points a known distance apart",
    # tool hints (status bar)
    "เลื่อน: ลากเพื่อเลื่อนแบบ · Ctrl+ล้อเมาส์ = ย่อ/ขยาย": "Pan: drag the drawing · Ctrl+wheel = zoom",
    "ตั้งสเกล: คลิก 2 จุดบนระยะที่รู้ค่า แล้วใส่ระยะจริง (ม.)": "Set scale: click 2 points a known distance apart, "
                                                               "then type the real distance (m)",
    "วัดความยาว: คลิกทีละจุด · ดับเบิลคลิกหรือ Enter = จบเส้น · Esc = ยกเลิก":
        "Length: click point by point · double-click or Enter = finish · Esc = cancel",
    "คิดพื้นที่: คลิกรอบรูป · ดับเบิลคลิกหรือ Enter = ปิดรูป · Esc = ยกเลิก":
        "Area: click round the shape · double-click or Enter = close · Esc = cancel",
    "นับจำนวน: คลิกทุกจุดที่ต้องการนับ · Enter = จบชุด · Esc = ยกเลิก":
        "Count: click every point to count · Enter = finish · Esc = cancel",
    "รูปทรงสี่เหลี่ยม: คลิกมุมหนึ่ง แล้วคลิกมุมตรงข้าม (ยึดจุดตามเส้นแบบ) → กว้าง × ยาว · พื้นที่ · รอบรูป":
        "Rectangle: click a corner, then the opposite corner (snaps to the drawing) → width × length · area · perimeter",
    "รูปทรงวงกลม: คลิกจุดศูนย์กลาง แล้วคลิกบนเส้นรอบวง → เส้นผ่านศูนย์กลาง · พื้นที่ · รอบรูป":
        "Circle: click the centre, then a point on the circle → diameter · area · perimeter",
    "รูปทรงสามเหลี่ยม: คลิก 3 มุม → ความยาวด้าน · พื้นที่ · รอบรูป":
        "Triangle: click the 3 corners → sides · area · perimeter",
    "อ่านรูปทรงจากแบบ: คลิกภายในรูป (สี่เหลี่ยม วงกลม สามเหลี่ยม หรือรูปปิด) โปรแกรมหาขอบตามเส้นในแบบและอ่านขนาดให้ทันที":
        "Read the shape: click inside a rectangle, circle, triangle or closed outline — the program finds "
        "its edges from the drawing's lines and reads its size",
    # common buttons
    "ตกลง": "OK", "ยกเลิก": "Cancel", "ปิด": "Close",
}

_lang = None


#: the languages of the program's screens: code → the pill's label
LANGS = (("th", "ไทย"), ("en", "EN"), ("lo", "ລາວ"), ("vi", "VI"), ("id", "ID"), ("zh", "简体"), ("zh_tw", "繁體"))
CODES = tuple(c for c, _l in LANGS)


def current() -> str:
    global _lang
    if _lang is None:
        _lang = str(QSettings("WANICNSURVEY", "ReadWanicn2027").value("lang", "") or
                    os.environ.get("WANIC_LANG", "th")).lower().replace("-", "_")
        if _lang not in CODES:
            _lang = "en" if _lang.startswith("en") else "zh_tw" if _lang in ("zh_hant", "tw") else \
                "zh" if _lang.startswith("zh") else "th"
    return _lang


def set_current(code: str) -> None:
    global _lang
    _lang = code if code in CODES else "th"
    QSettings("WANICNSURVEY", "ReadWanicn2027").setValue("lang", _lang)


def translate(text: str, code: str) -> str:
    """The text in a language (line by line for «icon\nword»); English where a word is missing."""
    if not text or code == "th":
        return text
    if "\n" in text and text not in EN:
        return "\n".join(translate(part, code) for part in text.split("\n"))
    en = EN.get(text)
    if en is None:
        return text
    if code == "en":
        return en
    from .lang_more import TABLES
    return TABLES.get(code, {}).get(en, en)


def english(text: str) -> str:
    """The English of a Thai text (line by line for «icon\nword»), or the text itself."""
    return translate(text, "en")


def tr(text: str) -> str:
    """The text in the current language."""
    return translate(text, current())


def scale_word() -> str:
    code = current()
    if code == "th":
        return "สเกลที่ใช้"
    if code == "en":
        return "Scale in use"
    from .lang_more import SCALE_WORD
    return SCALE_WORD.get(code, "Scale in use")


def _swap(w, prop, get, put):
    orig, cur = w.property(prop), get()
    if orig is None or (cur != orig and cur not in {translate(orig, c) for c in CODES}):
        orig = cur                             # the program changed the text since: that is the Thai now
        w.setProperty(prop, orig)
    put(tr(orig))


def apply(root: QWidget) -> None:
    """Put the current language on a window and everything in it."""
    widgets = [root] + root.findChildren(QWidget)
    for w in widgets:
        if isinstance(w, (QAbstractButton, QLabel)):
            _swap(w, "_th_text", w.text, w.setText)
        if w.toolTip():
            _swap(w, "_th_tip", w.toolTip, w.setToolTip)
        if isinstance(w, QLineEdit) and w.placeholderText():
            _swap(w, "_th_ph", w.placeholderText, w.setPlaceholderText)
        if isinstance(w, QGroupBox):
            _swap(w, "_th_title", w.title, w.setTitle)
        if isinstance(w, QTabWidget):
            for i in range(w.count()):
                _swap(w, f"_th_tab{i}", lambda i=i: w.tabText(i), lambda t, i=i: w.setTabText(i, t))
        if isinstance(w, QComboBox) and w.count() and w.property("_tr_items") is not False:
            for i in range(w.count()):
                _swap(w, f"_th_item{i}", lambda i=i: w.itemText(i), lambda t, i=i: w.setItemText(i, t))
        if isinstance(w, QTableWidget):
            for i in range(w.columnCount()):
                h = w.horizontalHeaderItem(i)
                if h is not None:
                    _swap(w, f"_th_head{i}", h.text, h.setText)
    if root.isWindow() and root.windowTitle():
        _swap(root, "_th_title_win", root.windowTitle, root.setWindowTitle)
