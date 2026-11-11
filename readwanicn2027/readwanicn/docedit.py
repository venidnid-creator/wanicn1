# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2569 (2026) นายเวนิช ธัมมะวงษ์ วิศวกรสำรวจ — ReadWanicn2027
"""The document editor (เอกสาร): an A4 page to type on in a Thai font, the
official-letter forms of งานสารบรรณ to start from, and .docx / PDF out
(.docx in too). The page is a QTextDocument; :func:`to_docx` and
:func:`from_docx` carry paragraphs, runs, alignment, indents, tables and
pictures across."""
from __future__ import annotations

import base64
import io
from pathlib import Path

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QMarginsF, QSizeF, Qt, QUrl
from PySide6.QtGui import (QColor, QFont, QFontDatabase, QImage, QPageLayout, QPageSize, QPdfWriter,
                           QTextBlockFormat, QTextCharFormat, QTextCursor, QTextDocument, QTextFrameFormat,
                           QTextImageFormat, QTextListFormat, QTextTableFormat)
from PySide6.QtWidgets import (QCheckBox, QColorDialog, QComboBox, QFileDialog, QFontComboBox, QFormLayout,
                               QFrame, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPlainTextEdit,
                               QPushButton, QScrollArea, QSpinBox, QSplitter, QTextEdit, QToolButton,
                               QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget)

from . import saraban

PX_PER_CM = 96 / 2.54
#: The page: A4 with the margins official letters use (left 3 cm, right 2 cm, top 2.5 cm, bottom 2 cm).
PAGE_W_CM, PAGE_H_CM = 21.0, 29.7
MARGINS_CM = (3.0, 2.5, 2.0, 2.0)          # left, top, right, bottom


def register_thai_fonts(asset) -> str:
    """Load the bundled Laksaman (TLWG's TH Sarabun) and return the family
    to type in: TH SarabunPSK / TH Sarabun New when installed, else Laksaman."""
    for name in ("Laksaman.ttf", "Laksaman-Bold.ttf"):
        QFontDatabase.addApplicationFont(asset(name))
    families = set(QFontDatabase.families())
    for fam in ("TH SarabunPSK", "TH Sarabun New", "TH SarabunIT๙", "Laksaman"):
        if fam in families:
            return fam
    return saraban.FONT_FALLBACK


# -- .docx out and in ------------------------------------------------------------------

def _qimage(doc: QTextDocument, name: str):
    res = doc.resource(QTextDocument.ImageResource, QUrl(name))
    if isinstance(res, QImage):
        return res
    try:
        from PySide6.QtGui import QPixmap
        if isinstance(res, QPixmap):
            return res.toImage()
    except Exception:
        pass
    img = QImage(name)
    return img if not img.isNull() else None


def _png_bytes(img: QImage) -> bytes:
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QIODevice.WriteOnly)
    img.save(buf, "PNG")
    return bytes(ba)


def _apply_block(par, block, Pt, Cm, WD_ALIGN):
    bf = block.blockFormat()
    al = bf.alignment()
    if al & Qt.AlignHCenter:
        par.alignment = WD_ALIGN.CENTER
    elif al & Qt.AlignRight:
        par.alignment = WD_ALIGN.RIGHT
    elif al & Qt.AlignJustify:
        par.alignment = WD_ALIGN.JUSTIFY
    pf = par.paragraph_format
    pf.space_before = Pt(bf.topMargin() * 0.75)
    pf.space_after = Pt(bf.bottomMargin() * 0.75)
    if bf.textIndent():
        pf.first_line_indent = Cm(bf.textIndent() / PX_PER_CM)
    if bf.leftMargin():
        pf.left_indent = Cm(bf.leftMargin() / PX_PER_CM)


def _fill_paragraph(qdoc, par, block, family, Pt, Cm, WD_ALIGN):
    _apply_block(par, block, Pt, Cm, WD_ALIGN)
    it = block.begin()
    while not it.atEnd():
        frag = it.fragment()
        if frag.isValid():
            fmt = frag.charFormat()
            if fmt.isImageFormat():
                im = fmt.toImageFormat()
                img = _qimage(qdoc, im.name())
                if img is not None:
                    width_cm = (im.width() or img.width()) / PX_PER_CM
                    par.add_run().add_picture(io.BytesIO(_png_bytes(img)), width=Cm(width_cm))
            else:
                text = frag.text().replace(" ", "\n").replace("￼", "")
                if text:
                    run = par.add_run(text)
                    f = fmt.font()
                    run.font.name = f.family() if f.family() and f.family() != "Sans Serif" else family
                    size = f.pointSizeF() if f.pointSizeF() > 0 else saraban.SIZE_PT
                    run.font.size = Pt(size)
                    run.bold = f.bold() or None
                    run.italic = f.italic() or None
                    run.underline = f.underline() or None
                    c = fmt.foreground().color()
                    if fmt.foreground().style() != Qt.NoBrush and c.isValid() and c != QColor("black"):
                        from docx.shared import RGBColor
                        run.font.color.rgb = RGBColor(c.red(), c.green(), c.blue())
                    _cs_font(run, run.font.name)
        it += 1


def _cs_font(run, family):
    """Thai is a complex script: Word takes its font from the cs slot."""
    from docx.oxml.ns import qn
    rpr = run._element.get_or_add_rPr()
    fonts = rpr.find(qn("w:rFonts"))
    if fonts is None:
        fonts = rpr.makeelement(qn("w:rFonts"), {})
        rpr.append(fonts)
    for slot in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
        fonts.set(qn(slot), family)
    if run.font.size is not None:
        sz = rpr.find(qn("w:szCs"))
        if sz is None:
            sz = rpr.makeelement(qn("w:szCs"), {})
            rpr.append(sz)
        sz.set(qn("w:val"), str(int(run.font.size.pt * 2)))


def to_docx(qdoc: QTextDocument, path, family: str = saraban.FONT) -> None:
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH as WD_ALIGN
    from docx.shared import Cm, Pt

    d = Document()
    sec = d.sections[0]
    sec.page_width, sec.page_height = Cm(PAGE_W_CM), Cm(PAGE_H_CM)
    sec.left_margin, sec.top_margin, sec.right_margin, sec.bottom_margin = (Cm(x) for x in MARGINS_CM)
    normal = d.styles["Normal"]
    normal.font.name = family
    normal.font.size = Pt(saraban.SIZE_PT)
    first = True
    root = qdoc.rootFrame()
    it = root.begin()
    while not it.atEnd():
        frame = it.currentFrame()
        block = it.currentBlock()
        if frame is not None and hasattr(frame, "rows"):              # a table
            table = frame
            t = d.add_table(rows=table.rows(), cols=table.columns())
            for r in range(table.rows()):
                for c in range(table.columns()):
                    cell = table.cellAt(r, c)
                    target = t.cell(r, c)
                    target.paragraphs[0].text = ""
                    cit = cell.begin()
                    firstpar = True
                    while not cit.atEnd():
                        b = cit.currentBlock()
                        if b.isValid():
                            par = target.paragraphs[0] if firstpar else target.add_paragraph()
                            firstpar = False
                            _fill_paragraph(qdoc, par, b, family, Pt, Cm, WD_ALIGN)
                        cit += 1
        elif block.isValid():
            par = d.paragraphs[0] if (first and d.paragraphs) else d.add_paragraph()
            first = False
            _fill_paragraph(qdoc, par, block, family, Pt, Cm, WD_ALIGN)
        it += 1
    d.save(path)


def from_docx(path) -> str:
    """A .docx as HTML for the editor: paragraphs with alignment, indents
    and runs, tables, and inline pictures (as data URIs)."""
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH as WD_ALIGN
    from docx.oxml.ns import qn

    d = Document(path)
    out = []

    def para_html(p):
        align = {WD_ALIGN.CENTER: "center", WD_ALIGN.RIGHT: "right",
                 WD_ALIGN.JUSTIFY: "justify"}.get(p.alignment, "left")
        pf = p.paragraph_format
        style = f"text-align:{align};"
        if pf.first_line_indent:
            style += f"text-indent:{pf.first_line_indent.cm:.2f}cm;"
        if pf.left_indent:
            style += f"margin-left:{pf.left_indent.cm:.2f}cm;"
        runs = []
        for r in p.runs:
            blips = r._element.findall(".//" + qn("a:blip"))
            for blip in blips:
                rid = blip.get(qn("r:embed"))
                part = d.part.related_parts.get(rid)
                if part is not None:
                    b64 = base64.b64encode(part.blob).decode()
                    ext = r._element.find(".//" + qn("wp:extent"))
                    w = int(int(ext.get("cx")) / 9525) if ext is not None else 120
                    runs.append(f'<img src="data:image/png;base64,{b64}" width="{w}">')
            t = (r.text or "").replace("&", "&amp;").replace("<", "&lt;").replace("\n", "<br>")
            if not t:
                continue
            css = ""
            if r.font.size:
                css += f"font-size:{r.font.size.pt:g}pt;"
            if r.font.name:
                css += f"font-family:'{r.font.name}';"
            if r.font.color is not None and r.font.color.rgb is not None:
                css += f"color:#{r.font.color.rgb};"
            if r.bold:
                t = f"<b>{t}</b>"
            if r.italic:
                t = f"<i>{t}</i>"
            if r.underline:
                t = f"<u>{t}</u>"
            runs.append(f'<span style="{css}">{t}</span>' if css else t)
        return f'<p style="{style}">{"".join(runs) or "&nbsp;"}</p>'

    body = d.element.body
    for child in body.iterchildren():
        if child.tag == qn("w:p"):
            from docx.text.paragraph import Paragraph
            out.append(para_html(Paragraph(child, d)))
        elif child.tag == qn("w:tbl"):
            from docx.table import Table
            t = Table(child, d)
            rows = []
            for row in t.rows:
                cells = "".join(f"<td>{''.join(para_html(p) for p in cell.paragraphs)}</td>" for cell in row.cells)
                rows.append(f"<tr>{cells}</tr>")
            out.append(f'<table width="100%" border="1" cellspacing="0" cellpadding="3">{"".join(rows)}</table>')
    return f"<html><body>{''.join(out)}</body></html>"


def to_pdf(qdoc: QTextDocument, path) -> None:
    writer = QPdfWriter(str(path))
    writer.setResolution(300)
    layout = QPageLayout(QPageSize(QPageSize.A4), QPageLayout.Portrait,
                         QMarginsF(MARGINS_CM[0] * 10, MARGINS_CM[1] * 10, MARGINS_CM[2] * 10,
                                   MARGINS_CM[3] * 10), QPageLayout.Millimeter)
    writer.setPageLayout(layout)
    copy = clone_with_images(qdoc)
    fmt = copy.rootFrame().frameFormat()
    fmt.setMargin(0)
    copy.rootFrame().setFrameFormat(fmt)
    # lay out at the writer's resolution on the printable area: no added margin, no page numbers
    copy.documentLayout().setPaintDevice(writer)
    copy.setPageSize(QSizeF(writer.pageLayout().paintRectPixels(writer.resolution()).size()))
    copy.print_(writer)


def clone_with_images(qdoc: QTextDocument) -> QTextDocument:
    copy = qdoc.clone()
    for name in _image_names(qdoc):                  # clone() does not carry added resources
        img = _qimage(qdoc, name)
        if img is not None:
            copy.addResource(QTextDocument.ImageResource, QUrl(name), img)
    return copy


def _image_names(qdoc):
    names = set()
    block = qdoc.begin()
    while block.isValid():
        it = block.begin()
        while not it.atEnd():
            frag = it.fragment()
            if frag.isValid() and frag.charFormat().isImageFormat():
                names.add(frag.charFormat().toImageFormat().name())
            it += 1
        block = block.next()
    return names


# -- the widget --------------------------------------------------------------------------

class Page(QTextEdit):
    """A sheet of A4 on screen: white, the official margins inside."""

    def __init__(self, family: str, parent=None):
        super().__init__(parent)
        self.setAcceptRichText(True)
        self.setFixedWidth(int(PAGE_W_CM * PX_PER_CM))
        self.setMinimumHeight(int(PAGE_H_CM * PX_PER_CM))
        self.setStyleSheet("QTextEdit { background: white; color: black; border: 1px solid #B8C2CC; }")
        self.family = family
        self.reset()

    def reset(self):
        doc = self.document()
        f = QFont(self.family)
        f.setPointSizeF(saraban.SIZE_PT)
        doc.setDefaultFont(f)
        fmt = doc.rootFrame().frameFormat()
        left, top, right, bottom = (x * PX_PER_CM for x in MARGINS_CM)
        fmt.setLeftMargin(left)
        fmt.setTopMargin(top)
        fmt.setRightMargin(right)
        fmt.setBottomMargin(bottom)
        doc.rootFrame().setFrameFormat(fmt)


class DocEditor(QWidget):
    """Forms on the left, the page in the middle, a ribbon of Thai-named tools on top."""

    def __init__(self, asset, record=lambda name: None, parent=None):
        super().__init__(parent)
        self.asset = asset
        self.record = record
        self.family = register_thai_fonts(asset)
        self.path = None
        self.garuda_path = asset("garuda.png")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self._ribbon())
        split = QSplitter()
        split.addWidget(self._forms())
        scroll = QScrollArea()
        scroll.setAlignment(Qt.AlignHCenter)
        scroll.setWidgetResizable(False)
        self.page = Page(self.family)
        self.page.currentCharFormatChanged.connect(self._sync_format)
        scroll.setWidget(self.page)
        split.addWidget(scroll)
        split.setSizes([330, 900])
        lay.addWidget(split, 1)
        self._load_garuda()

    # -- ribbon
    def _tool(self, text, tip, fn, checkable=False):
        b = QToolButton()
        b.setText(text)
        b.setToolTip(tip)
        b.setCheckable(checkable)
        b.setMinimumHeight(30)
        b.clicked.connect(fn)
        return b

    def _ribbon(self):
        bar = QFrame()
        bar.setObjectName("ToolRow")
        col = QVBoxLayout(bar)
        col.setContentsMargins(6, 4, 6, 4)
        row1 = QHBoxLayout()
        for text, tip, fn in (("📄 ใหม่", "เอกสารเปล่า", self.new),
                              ("📂 เปิด", "เปิดไฟล์เอกสาร (.docx) หรือหน้าเว็บ (.html)", self.open),
                              ("💾 บันทึก", "บันทึกเป็นไฟล์เอกสาร (.docx)", self.save),
                              ("💾 บันทึกเป็น…", "บันทึกเป็นไฟล์ใหม่", lambda: self.save(as_new=True)),
                              ("📑 บันทึกเป็น PDF", "บันทึกเป็น PDF ขนาด A4 ตามระยะขอบหนังสือราชการ", self.save_pdf),
                              ("🖨 พิมพ์", "พิมพ์ไปที่เครื่องพิมพ์ (Ctrl+P) ดูตัวอย่างก่อนพิมพ์ได้", self.print_doc),
                              ("↶ เลิกทำ", "เลิกทำ (Ctrl+Z)", lambda: self.page.undo()),
                              ("↷ ทำซ้ำ", "ทำซ้ำ (Ctrl+Y)", lambda: self.page.redo())):
            row1.addWidget(self._tool(text, tip, fn))
        row1.addStretch(1)
        col.addLayout(row1)
        row2 = QHBoxLayout()
        self.font_box = QFontComboBox()
        self.font_box.setCurrentFont(QFont(self.family))
        self.font_box.currentFontChanged.connect(lambda f: self._merge(family=f.family()))
        self.font_box.setToolTip("แบบอักษร (ค่าเริ่มต้น TH SarabunPSK)")
        row2.addWidget(self.font_box)
        self.size_box = QSpinBox()
        self.size_box.setRange(6, 96)
        self.size_box.setValue(saraban.SIZE_PT)
        self.size_box.setSuffix(" พอยต์")
        self.size_box.valueChanged.connect(lambda v: self._merge(size=v))
        row2.addWidget(self.size_box)
        self.bold = self._tool("ห", "ตัวหนา (Ctrl+B)", lambda on: self._merge(bold=on), True)
        self.bold.setStyleSheet("font-weight:bold;")
        self.italic = self._tool("อ", "ตัวเอียง (Ctrl+I)", lambda on: self._merge(italic=on), True)
        self.italic.setStyleSheet("font-style:italic;")
        self.underline = self._tool("ข", "ขีดเส้นใต้ (Ctrl+U)", lambda on: self._merge(underline=on), True)
        self.underline.setStyleSheet("text-decoration:underline;")
        for b in (self.bold, self.italic, self.underline):
            row2.addWidget(b)
        row2.addWidget(self._tool("🎨", "สีตัวอักษร", self.color))
        for text, tip, al in (("⯇", "ชิดซ้าย", Qt.AlignLeft), ("☰", "กึ่งกลาง", Qt.AlignHCenter),
                              ("⯈", "ชิดขวา", Qt.AlignRight), ("▤", "เต็มบรรทัด (กระจาย)", Qt.AlignJustify)):
            row2.addWidget(self._tool(text, tip, lambda _=False, a=al: self.page.setAlignment(a)))
        row2.addWidget(self._tool("⇥ ย่อหน้า", "เยื้องบรรทัดแรก 2.5 ซม. ตามระเบียบ", self.indent))
        row2.addWidget(self._tool("• รายการ", "รายการแบบสัญลักษณ์", self.bullets))
        row2.addWidget(self._tool("🖼 รูป", "แทรกรูปภาพ", self.insert_image))
        row2.addWidget(self._tool("▦ ตาราง", "แทรกตาราง", self.insert_table))
        row2.addWidget(self._tool("๑๒๓ เลขไทย", "เปลี่ยนตัวเลขในส่วนที่เลือก (หรือทั้งเอกสาร) เป็นเลขไทย",
                                  self.to_thai_digits))
        row2.addStretch(1)
        col.addLayout(row2)
        return bar

    # -- forms
    def _forms(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(6, 6, 6, 6)
        head = QLabel("<b>แบบหนังสือราชการ (ระเบียบงานสารบรรณ)</b>")
        lay.addWidget(head)
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        groups = {}
        for f in saraban.FORMS:
            g = groups.get(f.group)
            if g is None:
                g = QTreeWidgetItem([f.group])
                self.tree.addTopLevelItem(g)
                groups[f.group] = g
            it = QTreeWidgetItem([f.name])
            it.setData(0, Qt.UserRole, f.key)
            g.addChild(it)
        self.tree.expandAll()
        self.tree.setMaximumHeight(230)
        self.tree.currentItemChanged.connect(lambda cur, _p: self.choose_form(cur.data(0, Qt.UserRole))
                                             if cur and cur.data(0, Qt.UserRole) else None)
        lay.addWidget(self.tree)
        self.fields_box = QScrollArea()
        self.fields_box.setWidgetResizable(True)
        self.fields_w = QWidget()
        self.fields = QFormLayout(self.fields_w)
        self.fields.setRowWrapPolicy(QFormLayout.WrapAllRows)     # label above its box: the panel is narrow
        self.fields.setVerticalSpacing(4)
        from PySide6.QtWidgets import QLayout
        self.fields.setSizeConstraint(QLayout.SetMinimumSize)      # scroll rather than squeeze
        self.fields_box.setWidget(self.fields_w)
        lay.addWidget(self.fields_box, 1)
        self.thai_num = QCheckBox("ใช้เลขไทย")
        self.thai_num.setChecked(True)
        lay.addWidget(self.thai_num)
        row = QHBoxLayout()
        go = QPushButton("📝 สร้างหนังสือลงหน้ากระดาษ")
        go.setObjectName("Primary")
        go.clicked.connect(self.fill_form)
        row.addWidget(go)
        lay.addLayout(row)
        row = QHBoxLayout()
        gb = QPushButton("ตราครุฑ/ตราหน่วยงาน…")
        gb.setToolTip("เลือกไฟล์รูปตราที่ใช้หัวหนังสือ (ควรเป็นภาพความละเอียดสูง พื้นโปร่งใสหรือพื้นขาว)")
        gb.clicked.connect(self.choose_garuda)
        row.addWidget(gb)
        nb = QPushButton("ตั้งชื่อไฟล์…")
        nb.setToolTip("ชื่อไฟล์ตามภาคผนวก ๗: ปีพุทธศักราช_รหัสส่วนราชการ_เลขที่หนังสือ.pdf")
        nb.clicked.connect(self.name_file)
        row.addWidget(nb)
        lay.addLayout(row)
        self.inputs = {}
        self.form_key = None
        return w

    def choose_form(self, key):
        self.form_key = key
        while self.fields.rowCount():
            self.fields.removeRow(0)
        self.inputs = {}
        for k, label, default in saraban.BY_KEY[key].fields:
            if k in ("body", "present", "office") and ("\n" in default or k == "body"):
                ed = QPlainTextEdit(default)
                ed.setMinimumHeight(110 if k == "body" else 60)
            else:
                ed = QLineEdit(default)
            ed.setMinimumHeight(max(ed.minimumHeight(), 28))
            self.inputs[k] = ed
            self.fields.addRow(label, ed)
        self.fields_w.adjustSize()

    def values(self) -> dict:
        return {k: (w.toPlainText() if isinstance(w, QPlainTextEdit) else w.text())
                for k, w in self.inputs.items()}

    def fill_form(self):
        if not self.form_key:
            QMessageBox.information(self, "เอกสาร", "เลือกแบบหนังสือทางซ้ายก่อน")
            return
        self.page.reset()
        self.page.setHtml(saraban.render(self.form_key, self.values(), "garuda", self.thai_num.isChecked()))
        self.page.reset()
        self.record(f"สร้างหนังสือ: {saraban.BY_KEY[self.form_key].name}")

    # -- garuda
    def _load_garuda(self):
        img = QImage(self.garuda_path)
        if not img.isNull():
            self.page.document().addResource(QTextDocument.ImageResource, QUrl("garuda"), img)

    def choose_garuda(self):
        path, _ = QFileDialog.getOpenFileName(self, "เลือกไฟล์ตรา", "", "รูปภาพ (*.png *.jpg *.jpeg *.bmp)")
        if path:
            self.garuda_path = path
            self._load_garuda()
            if self.form_key:
                self.fill_form()

    def name_file(self):
        from PySide6.QtWidgets import QDialog, QDialogButtonBox
        dlg = QDialog(self)
        dlg.setWindowTitle("ตั้งชื่อไฟล์ตามภาคผนวก ๗")
        form = QFormLayout(dlg)
        import datetime as dt
        year = QSpinBox()
        year.setRange(2500, 2700)
        year.setValue(dt.date.today().year + 543)
        code = QComboBox()
        code.setEditable(True)
        for name, c in list(saraban.MINISTRIES.items()) + list(saraban.PROVINCES.items()):
            code.addItem(f"{c} — {name}", c)
        office = QLineEdit("0913")
        no = QLineEdit("56")
        att = QSpinBox()
        att.setRange(0, 99)
        out = QLineEdit()
        out.setReadOnly(True)

        def show():
            c = code.currentData() or code.currentText().split(" ")[0]
            out.setText(saraban.file_name(year.value(), c, office.text(), no.text(), att.value()))
        for w in (year, att):
            w.valueChanged.connect(show)
        for w in (office, no):
            w.textChanged.connect(show)
        code.currentIndexChanged.connect(show)
        form.addRow("ปีพุทธศักราช", year)
        form.addRow("รหัสตัวอักษรโรมัน", code)
        form.addRow("เลขประจำของส่วนราชการเจ้าของเรื่อง", office)
        form.addRow("เลขที่หนังสือ (ทะเบียนส่ง)", no)
        form.addRow("สิ่งที่ส่งมาด้วยลำดับที่ (0 = ตัวหนังสือ)", att)
        form.addRow("ชื่อไฟล์", out)
        box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        box.button(QDialogButtonBox.Ok).setText("บันทึก PDF ด้วยชื่อนี้…")
        box.button(QDialogButtonBox.Cancel).setText("ปิด")
        box.accepted.connect(dlg.accept)
        box.rejected.connect(dlg.reject)
        form.addRow(box)
        show()
        if dlg.exec():
            self.save_pdf(out.text())

    # -- formatting
    def _merge(self, family=None, size=None, bold=None, italic=None, underline=None, color=None):
        fmt = QTextCharFormat()
        if family:
            fmt.setFontFamilies([family])
        if size:
            fmt.setFontPointSize(size)
        if bold is not None:
            fmt.setFontWeight(QFont.Bold if bold else QFont.Normal)
        if italic is not None:
            fmt.setFontItalic(italic)
        if underline is not None:
            fmt.setFontUnderline(underline)
        if color is not None:
            fmt.setForeground(color)
        cur = self.page.textCursor()
        if not cur.hasSelection():
            cur.select(QTextCursor.WordUnderCursor)
        cur.mergeCharFormat(fmt)
        self.page.mergeCurrentCharFormat(fmt)
        self.page.setFocus()

    def _sync_format(self, fmt: QTextCharFormat):
        for w in (self.size_box, self.bold, self.italic, self.underline):
            w.blockSignals(True)
        if fmt.fontPointSize() > 0:
            self.size_box.setValue(int(round(fmt.fontPointSize())))
        self.bold.setChecked(fmt.fontWeight() >= QFont.Bold)
        self.italic.setChecked(fmt.fontItalic())
        self.underline.setChecked(fmt.fontUnderline())
        for w in (self.size_box, self.bold, self.italic, self.underline):
            w.blockSignals(False)

    def color(self):
        c = QColorDialog.getColor(Qt.black, self, "สีตัวอักษร")
        if c.isValid():
            self._merge(color=c)

    def indent(self):
        cur = self.page.textCursor()
        bf = cur.blockFormat()
        bf.setTextIndent(0 if bf.textIndent() else 2.5 * PX_PER_CM)
        cur.setBlockFormat(bf)

    def bullets(self):
        self.page.textCursor().createList(QTextListFormat.ListDisc)

    def insert_image(self, path=None):
        if not path:
            path, _ = QFileDialog.getOpenFileName(self, "แทรกรูปภาพ", "", "รูปภาพ (*.png *.jpg *.jpeg *.bmp *.gif)")
        if not path:
            return
        img = QImage(path)
        if img.isNull():
            QMessageBox.warning(self, "เอกสาร", "เปิดรูปภาพนี้ไม่ได้")
            return
        name = f"img-{Path(path).name}"
        self.page.document().addResource(QTextDocument.ImageResource, QUrl(name), img)
        fmt = QTextImageFormat()
        fmt.setName(name)
        width = min(img.width(), int((PAGE_W_CM - 5) * PX_PER_CM))
        fmt.setWidth(width)
        fmt.setHeight(img.height() * width / max(1, img.width()))
        self.page.textCursor().insertImage(fmt)

    def insert_table(self):
        fmt = QTextTableFormat()
        fmt.setCellPadding(4)
        fmt.setCellSpacing(0)
        fmt.setBorder(1)
        self.page.textCursor().insertTable(3, 3, fmt)

    def to_thai_digits(self):
        cur = self.page.textCursor()
        if not cur.hasSelection():
            cur.select(QTextCursor.Document)
        doc = self.page.document()
        start, end = cur.selectionStart(), cur.selectionEnd()
        c = QTextCursor(doc)
        c.beginEditBlock()
        pos = start
        while pos < end:
            c.setPosition(pos)
            c.setPosition(pos + 1, QTextCursor.KeepAnchor)
            ch = c.selectedText()
            if ch.isdigit() and ch in "0123456789":
                fmt = c.charFormat()
                c.insertText(saraban.thai_digits(ch), fmt)
            pos += 1
        c.endEditBlock()

    # -- files
    def new(self):
        self.page.clear()
        self.page.reset()
        self.path = None

    def open(self, path=None):
        if not path:
            path, _ = QFileDialog.getOpenFileName(self, "เปิดเอกสาร", "", "เอกสาร (*.docx *.html *.htm *.txt)")
        if not path:
            return
        p = Path(path)
        if p.suffix.lower() == ".docx":
            self.page.setHtml(from_docx(path))
        elif p.suffix.lower() in (".html", ".htm"):
            self.page.setHtml(p.read_text(encoding="utf-8", errors="ignore"))
        else:
            self.page.setPlainText(p.read_text(encoding="utf-8", errors="ignore"))
        self.page.reset()
        self._load_garuda()
        self.path = path if p.suffix.lower() == ".docx" else None
        self.record("เปิดเอกสาร")

    def save(self, as_new=False):
        path = self.path
        if as_new or not path:
            path, _ = QFileDialog.getSaveFileName(self, "บันทึกเอกสาร", "หนังสือ.docx", "เอกสาร (*.docx)")
        if not path:
            return
        to_docx(self.page.document(), path, self.family if self.family != "Laksaman" else saraban.FONT)
        self.path = path
        self.record("บันทึกเอกสาร (.docx)")
        return path

    def print_doc(self):
        from . import printing
        doc = self.page.document()
        if printing.print_text_document(self, lambda: clone_with_images(doc), "เอกสาร",
                                        tuple(x * 10 for x in MARGINS_CM)):
            self.record("พิมพ์เอกสาร")

    def save_pdf(self, name: str = ""):
        path, _ = QFileDialog.getSaveFileName(self, "บันทึกเป็น PDF", name or "หนังสือ.pdf", "PDF (*.pdf)")
        if not path:
            return
        to_pdf(self.page.document(), path)
        self.record("บันทึกเอกสารเป็น PDF")
        return path
