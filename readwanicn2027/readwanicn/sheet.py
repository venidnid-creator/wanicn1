# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2569 (2026) นายเวนิช ธัมมะวงษ์ วิศวกรสำรวจ — ReadWanicn2027
"""The spreadsheet (ตารางคำนวณ): a grid with A1 references, formulas
(=SUM(A1:A5), =B2*C2, …), .xlsx / .csv in and out, and the registers of
งานสารบรรณ ready to fill. :class:`Formula` does the arithmetic without
``eval`` of user text: it parses a small expression language."""
from __future__ import annotations

import csv
import math
import re
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QFileDialog, QFrame, QHBoxLayout, QInputDialog,
                               QLabel, QLineEdit, QMessageBox, QSpinBox, QTableWidget, QTableWidgetItem,
                               QToolButton, QVBoxLayout, QWidget)

from . import saraban

ROWS, COLS = 200, 26


def col_name(c: int) -> str:
    s = ""
    c += 1
    while c:
        c, r = divmod(c - 1, 26)
        s = chr(65 + r) + s
    return s


def col_index(name: str) -> int:
    n = 0
    for ch in name.upper():
        n = n * 26 + ord(ch) - 64
    return n - 1


_REF = re.compile(r"\$?([A-Za-z]{1,3})\$?(\d+)")


def parse_ref(ref: str):
    m = _REF.fullmatch(ref.strip())
    if not m:
        raise ValueError(ref)
    return int(m.group(2)) - 1, col_index(m.group(1))


# -- formulas ----------------------------------------------------------------------------

class FormulaError(Exception):
    pass


_TOKEN = re.compile(r"\s*(?:(\d+\.?\d*(?:[eE][-+]?\d+)?|\.\d+)|(\$?[A-Za-z]{1,3}\$?\d+(?::\$?[A-Za-z]{1,3}\$?\d+)?)"
                    r"|([A-Za-z_][A-Za-z_0-9]*)|(\"[^\"]*\")|(<=|>=|<>|[-+*/^(),:<>=&%]))")


def _num(v):
    if v is None or v == "":
        return 0.0
    if isinstance(v, bool):
        return float(v)
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return float(str(v).replace(",", ""))
    except ValueError:
        raise FormulaError(f"#VALUE! ({v})")


def _flat(args):
    for a in args:
        if isinstance(a, list):
            yield from _flat(a)
        else:
            yield a


def _nums(args):
    out = []
    for a in _flat(args):
        if isinstance(a, (int, float)) and not isinstance(a, bool):
            out.append(float(a))
        elif isinstance(a, str) and a.strip():
            try:
                out.append(float(a.replace(",", "")))
            except ValueError:
                pass
    return out


FUNCS = {
    "SUM": lambda a: sum(_nums(a)),
    "AVERAGE": lambda a: (sum(_nums(a)) / len(_nums(a))) if _nums(a) else 0.0,
    "MIN": lambda a: min(_nums(a)) if _nums(a) else 0.0,
    "MAX": lambda a: max(_nums(a)) if _nums(a) else 0.0,
    "COUNT": lambda a: float(len(_nums(a))),
    "COUNTA": lambda a: float(sum(1 for x in _flat(a) if x not in (None, ""))),
    "ROUND": lambda a: round(_num(a[0]), int(_num(a[1])) if len(a) > 1 else 0),
    "ABS": lambda a: abs(_num(a[0])),
    "SQRT": lambda a: math.sqrt(_num(a[0])),
    "INT": lambda a: float(math.floor(_num(a[0]))),
    "PI": lambda a: math.pi,
    "SIN": lambda a: math.sin(_num(a[0])),
    "COS": lambda a: math.cos(_num(a[0])),
    "TAN": lambda a: math.tan(_num(a[0])),
    "ATAN2": lambda a: math.atan2(_num(a[1]), _num(a[0])),
    "RADIANS": lambda a: math.radians(_num(a[0])),
    "DEGREES": lambda a: math.degrees(_num(a[0])),
    "POWER": lambda a: _num(a[0]) ** _num(a[1]),
    "IF": lambda a: a[1] if a[0] else (a[2] if len(a) > 2 else 0.0),
}
#: Thai names for the functions menu.
FUNC_TH = {"SUM": "ผลรวม", "AVERAGE": "ค่าเฉลี่ย", "MIN": "ค่าน้อยสุด", "MAX": "ค่ามากสุด",
           "COUNT": "นับตัวเลข", "ROUND": "ปัดเศษ", "ABS": "ค่าสัมบูรณ์", "SQRT": "รากที่สอง"}


class Formula:
    """Recursive descent over: comparison < & < + - < * / < ^ < unary < atom."""

    def __init__(self, text: str, get, depth=0):
        self.toks = [t for t in _TOKEN.findall(text)]
        self.rest = _TOKEN.sub("", text).strip()
        if self.rest:
            raise FormulaError(f"#NAME? ({self.rest})")
        self.toks = [next(x for x in t if x) for t in self.toks]
        self.i = 0
        self.get = get

    def peek(self):
        return self.toks[self.i] if self.i < len(self.toks) else None

    def take(self, want=None):
        t = self.peek()
        if want is not None and t != want:
            raise FormulaError(f"#ERROR! ต้องการ {want}")
        self.i += 1
        return t

    def run(self):
        v = self.comparison()
        if self.peek() is not None:
            raise FormulaError("#ERROR!")
        return v

    def comparison(self):
        v = self.concat()
        while self.peek() in ("=", "<", ">", "<=", ">=", "<>"):
            op = self.take()
            w = self.concat()
            a, b = (v, w) if isinstance(v, str) or isinstance(w, str) else (_num(v), _num(w))
            v = {"=": a == b, "<": a < b, ">": a > b, "<=": a <= b, ">=": a >= b, "<>": a != b}[op]
        return v

    def concat(self):
        v = self.additive()
        while self.peek() == "&":
            self.take()
            v = f"{_fmt(v)}{_fmt(self.additive())}"
        return v

    def additive(self):
        v = self.term()
        while self.peek() in ("+", "-"):
            op = self.take()
            w = self.term()
            v = _num(v) + _num(w) if op == "+" else _num(v) - _num(w)
        return v

    def term(self):
        v = self.power()
        while self.peek() in ("*", "/"):
            op = self.take()
            w = self.power()
            if op == "*":
                v = _num(v) * _num(w)
            else:
                if _num(w) == 0:
                    raise FormulaError("#DIV/0!")
                v = _num(v) / _num(w)
        return v

    def power(self):
        v = self.unary()
        if self.peek() == "^":
            self.take()
            v = _num(v) ** _num(self.power())
        return v

    def unary(self):
        if self.peek() == "-":
            self.take()
            return -_num(self.unary())
        if self.peek() == "+":
            self.take()
        v = self.atom()
        if self.peek() == "%":
            self.take()
            v = _num(v) / 100
        return v

    def atom(self):
        t = self.take()
        if t is None:
            raise FormulaError("#ERROR!")
        if t == "(":
            v = self.comparison()
            self.take(")")
            return v
        if t[0] == '"':
            return t[1:-1]
        if t[0].isdigit() or t[0] == ".":
            return float(t)
        if _REF.fullmatch(t.split(":")[0]) and (":" in t or _REF.fullmatch(t)):
            if ":" in t:
                a, b = t.split(":")
                (r1, c1), (r2, c2) = parse_ref(a), parse_ref(b)
                return [self.get(r, c) for r in range(min(r1, r2), max(r1, r2) + 1)
                        for c in range(min(c1, c2), max(c1, c2) + 1)]
            return self.get(*parse_ref(t))
        name = t.upper()
        if name in ("TRUE", "FALSE"):
            return name == "TRUE"
        if name not in FUNCS:
            raise FormulaError(f"#NAME? ({t})")
        self.take("(")
        args = []
        if self.peek() != ")":
            args.append(self.comparison())
            while self.peek() == ",":
                self.take()
                args.append(self.comparison())
        self.take(")")
        try:
            return FUNCS[name](args)
        except FormulaError:
            raise
        except (ValueError, IndexError, ZeroDivisionError, OverflowError):
            raise FormulaError("#NUM!")


def _fmt(v) -> str:
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    if isinstance(v, float):
        return f"{v:.10g}" if v != int(v) or abs(v) >= 1e15 else str(int(v))
    return "" if v is None else str(v)


class Book:
    """The cells' raw text and their values; formulas recompute on demand."""

    def __init__(self, rows=ROWS, cols=COLS):
        self.rows, self.cols = rows, cols
        self.raw: dict[tuple[int, int], str] = {}

    def set(self, r, c, text):
        if text in (None, ""):
            self.raw.pop((r, c), None)
        else:
            self.raw[(r, c)] = str(text)

    def value(self, r, c, _seen=None):
        text = self.raw.get((r, c), "")
        if not text.startswith("="):
            try:
                return float(text.replace(",", "")) if text.strip() and re.fullmatch(r"[-+]?[\d,]*\.?\d+", text.strip()) else text
            except ValueError:
                return text
        seen = set() if _seen is None else _seen
        if (r, c) in seen:
            raise FormulaError("#REF! (วนซ้ำ)")
        seen = seen | {(r, c)}
        return Formula(text[1:], lambda rr, cc: self.value(rr, cc, seen)).run()

    def display(self, r, c, decimals=None) -> str:
        raw = self.raw.get((r, c), "")
        if decimals is None and not raw.startswith("="):
            return raw                              # as typed: 1520345.120 keeps its zero
        try:
            v = self.value(r, c)
        except FormulaError as e:
            return str(e).split(" ")[0]
        except RecursionError:
            return "#REF!"
        if decimals is not None and isinstance(v, float):
            return f"{v:,.{decimals}f}"
        return _fmt(v)


# -- file in and out ---------------------------------------------------------------------

def save_xlsx(book: Book, path, styles=None, family=saraban.FONT, widths=None):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font
    wb = Workbook()
    ws = wb.active
    ws.title = "แผ่นงาน1"
    styles = styles or {}
    for (r, c), text in book.raw.items():
        cell = ws.cell(row=r + 1, column=c + 1)
        try:
            v = book.value(r, c)
        except FormulaError:
            v = None
        if text.startswith("="):
            cell.value = text
        elif isinstance(v, float):
            cell.value = int(v) if v == int(v) and "." not in text else v
        else:
            cell.value = text
        st = styles.get((r, c), {})
        cell.font = Font(name=family, size=st.get("size", 16), bold=st.get("bold", False),
                         italic=st.get("italic", False))
        if st.get("align"):
            cell.alignment = Alignment(horizontal=st["align"])
    for c, w in (widths or {}).items():
        ws.column_dimensions[col_name(c)].width = max(4, w / 7)
    wb.save(path)


def load_xlsx(path) -> Book:
    from openpyxl import load_workbook
    wb = load_workbook(path)
    ws = wb.active
    book = Book(max(ROWS, ws.max_row + 20), max(COLS, ws.max_column + 2))
    for row in ws.iter_rows():
        for cell in row:
            if cell.value is not None:
                v = cell.value
                book.set(cell.row - 1, cell.column - 1, _fmt(v) if isinstance(v, float) else str(v))
    return book


def save_csv(book: Book, path):
    rows = max((r for r, _ in book.raw), default=-1) + 1
    cols = max((c for _, c in book.raw), default=-1) + 1
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        for r in range(rows):
            w.writerow([book.display(r, c) for c in range(cols)])


def load_csv(path) -> Book:
    data = Path(path).read_bytes()
    for enc in ("utf-8-sig", "cp874", "latin-1"):
        try:
            text = data.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    rows = list(csv.reader(text.splitlines()))
    book = Book(max(ROWS, len(rows) + 20), max(COLS, max((len(r) for r in rows), default=0) + 2))
    for r, row in enumerate(rows):
        for c, v in enumerate(row):
            book.set(r, c, v)
    return book


def register_book(title: str) -> Book:
    """A register of งานสารบรรณ: its title on row 1, the columns on row 3."""
    book = Book()
    book.set(0, 0, title)
    for c, head in enumerate(saraban.REGISTERS[title]):
        book.set(2, c, head)
    return book


# -- the widget --------------------------------------------------------------------------

class SheetEditor(QWidget):
    def __init__(self, family: str, record=lambda name: None, parent=None):
        super().__init__(parent)
        self.family = family
        self.record = record
        self.book = Book()
        self.styles: dict[tuple[int, int], dict] = {}
        self.decimals: int | None = None
        self.path = None
        self._busy = False
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self._ribbon())
        bar = QHBoxLayout()
        bar.setContentsMargins(6, 2, 6, 2)
        self.where = QLabel("A1")
        self.where.setMinimumWidth(60)
        self.where.setAlignment(Qt.AlignCenter)
        self.where.setStyleSheet("font-weight:bold;")
        bar.addWidget(self.where)
        bar.addWidget(QLabel("ƒx"))
        self.formula = QLineEdit()
        self.formula.setPlaceholderText("พิมพ์ค่า หรือสูตรขึ้นต้นด้วย = เช่น =SUM(B2:B10)  =B2*C2  =ROUND(D2,3)")
        self.formula.returnPressed.connect(self._commit_formula)
        bar.addWidget(self.formula, 1)
        lay.addLayout(bar)
        self.grid = QTableWidget(self.book.rows, self.book.cols)
        self.grid.setHorizontalHeaderLabels([col_name(c) for c in range(self.book.cols)])
        self.grid.setVerticalHeaderLabels([str(r + 1) for r in range(self.book.rows)])
        self.grid.setSelectionMode(QAbstractItemView.ExtendedSelection)
        f = QFont(family)
        f.setPointSize(14)
        self.grid.setFont(f)
        self.grid.verticalHeader().setDefaultSectionSize(28)
        self.grid.horizontalHeader().setDefaultSectionSize(110)
        self.grid.setStyleSheet("QTableWidget { background: white; color: black; gridline-color: #D0D7DE; }"
                                "QTableWidget::item:selected { background: #CDE3FF; color: black; }")
        self.grid.currentCellChanged.connect(self._moved)
        self.grid.itemChanged.connect(self._edited)
        self.grid.itemDoubleClicked.connect(self._editing)
        lay.addWidget(self.grid, 1)
        self.status = QLabel("")
        self.status.setContentsMargins(8, 2, 8, 2)
        lay.addWidget(self.status)
        self.grid.itemSelectionChanged.connect(self._summary)
        self.refresh()

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
        row = QHBoxLayout()
        for text, tip, fn in (("📄 ใหม่", "ตารางเปล่า", self.new),
                              ("📂 เปิด", "เปิดตารางคำนวณ (.xlsx) หรือตารางข้อมูล (.csv)", self.open),
                              ("💾 บันทึก", "บันทึกเป็นตารางคำนวณ (.xlsx)", self.save),
                              ("💾 บันทึกเป็น…", "บันทึกเป็นไฟล์ใหม่ (.xlsx หรือ .csv)", lambda: self.save(True)),
                              ("🖨 พิมพ์", "พิมพ์ตารางไปที่เครื่องพิมพ์ (Ctrl+P) ดูตัวอย่างก่อนพิมพ์ได้",
                               self.print_sheet)):
            row.addWidget(self._tool(text, tip, fn))
        row.addSpacing(12)
        self.reg = QComboBox()
        self.reg.addItem("— แบบทะเบียนงานสารบรรณ —")
        for name in saraban.REGISTERS:
            self.reg.addItem(name)
        self.reg.setToolTip("เริ่มตารางจากแบบทะเบียน/บัญชีตามระเบียบงานสารบรรณ")
        self.reg.activated.connect(self._register)
        row.addWidget(self.reg)
        row.addStretch(1)
        col.addLayout(row)
        row = QHBoxLayout()
        b = self._tool("ห", "ตัวหนา", lambda on: self._style(bold=on), True)
        b.setStyleSheet("font-weight:bold;")
        row.addWidget(b)
        i = self._tool("อ", "ตัวเอียง", lambda on: self._style(italic=on), True)
        i.setStyleSheet("font-style:italic;")
        row.addWidget(i)
        for text, tip, al in (("⯇", "ชิดซ้าย", "left"), ("☰", "กึ่งกลาง", "center"), ("⯈", "ชิดขวา", "right")):
            row.addWidget(self._tool(text, tip, lambda _=False, a=al: self._style(align=a)))
        row.addWidget(QLabel(" ทศนิยม"))
        self.dec = QSpinBox()
        self.dec.setRange(-1, 6)
        self.dec.setValue(-1)
        self.dec.setSpecialValueText("อัตโนมัติ")
        self.dec.valueChanged.connect(self._decimals)
        row.addWidget(self.dec)
        row.addSpacing(12)
        row.addWidget(self._tool("Σ ผลรวม", "ผลรวมอัตโนมัติใต้ช่วงที่เลือก", self.auto_sum))
        row.addWidget(self._tool("ƒ ฟังก์ชัน", "แทรกฟังก์ชัน", self.insert_func))
        row.addWidget(self._tool("＋ แถว", "แทรกแถวเหนือแถวที่เลือก", lambda: self.insert(rows=True)))
        row.addWidget(self._tool("＋ คอลัมน์", "แทรกคอลัมน์ทางซ้าย", lambda: self.insert(rows=False)))
        row.addWidget(self._tool("－ แถว", "ลบแถวที่เลือก", lambda: self.remove(rows=True)))
        row.addWidget(self._tool("－ คอลัมน์", "ลบคอลัมน์ที่เลือก", lambda: self.remove(rows=False)))
        row.addWidget(self._tool("⌫ ล้าง", "ล้างข้อมูลในช่องที่เลือก", self.clear_cells))
        row.addStretch(1)
        col.addLayout(row)
        return bar

    # -- display
    def refresh(self):
        self._busy = True
        self.grid.setRowCount(self.book.rows)
        self.grid.setColumnCount(self.book.cols)
        self.grid.setHorizontalHeaderLabels([col_name(c) for c in range(self.book.cols)])
        self.grid.setVerticalHeaderLabels([str(r + 1) for r in range(self.book.rows)])
        self.grid.clearContents()
        self.grid.clearSpans()
        for r, c, h, w in getattr(self, "spans", []):
            self.grid.setSpan(r, c, h, w)
        dec = None if self.decimals is None else self.decimals
        for (r, c) in list(self.book.raw):
            self._paint(r, c, dec)
        self._busy = False

    def _paint(self, r, c, dec=None):
        if r >= self.grid.rowCount() or c >= self.grid.columnCount():
            return
        text = self.book.display(r, c, dec)
        it = self.grid.item(r, c)
        if it is None:
            it = QTableWidgetItem()
            self.grid.setItem(r, c, it)
        it.setText(text)
        st = self.styles.get((r, c), {})
        f = QFont(self.family)
        f.setPointSize(14)
        f.setBold(st.get("bold", False))
        f.setItalic(st.get("italic", False))
        it.setFont(f)
        try:
            v = self.book.value(r, c)
        except FormulaError:
            v = ""
        al = {"left": Qt.AlignLeft, "center": Qt.AlignHCenter, "right": Qt.AlignRight}.get(
            st.get("align"), Qt.AlignRight if isinstance(v, float) else Qt.AlignLeft)
        it.setTextAlignment(al | Qt.AlignVCenter)
        it.setToolTip(self.book.raw.get((r, c), "") if self.book.raw.get((r, c), "").startswith("=") else "")

    def _recalc(self):
        self._busy = True
        for (r, c) in list(self.book.raw):
            self._paint(r, c, self.decimals)
        self._busy = False

    def _moved(self, r, c, *_):
        if r < 0:
            return
        self.where.setText(f"{col_name(c)}{r + 1}")
        self.formula.setText(self.book.raw.get((r, c), ""))

    def _editing(self, item):
        self._busy = True
        item.setText(self.book.raw.get((item.row(), item.column()), ""))
        self._busy = False

    def _edited(self, item):
        if self._busy:
            return
        self.book.set(item.row(), item.column(), item.text())
        self._recalc()
        self.formula.setText(self.book.raw.get((item.row(), item.column()), ""))

    def _commit_formula(self):
        r, c = self.grid.currentRow(), self.grid.currentColumn()
        if r < 0:
            return
        self.book.set(r, c, self.formula.text())
        self._recalc()
        self.grid.setCurrentCell(min(r + 1, self.book.rows - 1), c)
        self.record("ตารางคำนวณ: ใส่สูตร" if self.formula.text().startswith("=") else "ตารางคำนวณ: ใส่ค่า")

    def _summary(self):
        vals = []
        for it in self.grid.selectedIndexes():
            try:
                v = self.book.value(it.row(), it.column())
            except FormulaError:
                continue
            if isinstance(v, float):
                vals.append(v)
        if len(vals) > 1:
            self.status.setText(f"ผลรวม {sum(vals):,.3f}   ค่าเฉลี่ย {sum(vals) / len(vals):,.3f}   "
                                f"นับ {len(vals)}   น้อยสุด {min(vals):,.3f}   มากสุด {max(vals):,.3f}")
        else:
            self.status.setText("")

    # -- editing tools
    def _cells(self):
        return sorted({(i.row(), i.column()) for i in self.grid.selectedIndexes()}) or \
            [(self.grid.currentRow(), self.grid.currentColumn())]

    def _style(self, **kw):
        for rc in self._cells():
            self.styles.setdefault(rc, {}).update(kw)
            self._busy = True
            self._paint(*rc, self.decimals)
            self._busy = False

    def _decimals(self, v):
        self.decimals = None if v < 0 else v
        self._recalc()

    def auto_sum(self):
        cells = self._cells()
        cols = sorted({c for _, c in cells})
        last = max(r for r, _ in cells)
        first = min(r for r, _ in cells)
        if len(cells) == 1:                   # one cell: sum the numbers above it
            r, c = cells[0]
            top = r - 1
            while top >= 0 and isinstance(self.book.value(top, c), float):
                top -= 1
            if top + 1 > r - 1:
                return
            self.book.set(r, c, f"=SUM({col_name(c)}{top + 2}:{col_name(c)}{r})")
        else:
            for c in cols:
                self.book.set(last + 1, c, f"=SUM({col_name(c)}{first + 1}:{col_name(c)}{last + 1})")
        self._recalc()
        self.record("ตารางคำนวณ: ผลรวมอัตโนมัติ")

    def insert_func(self):
        items = [f"{k} — {v}" for k, v in FUNC_TH.items()]
        choice, ok = QInputDialog.getItem(self, "แทรกฟังก์ชัน", "ฟังก์ชัน", items, 0, False)
        if ok:
            name = choice.split(" ")[0]
            cells = self._cells()
            rng = f"{col_name(cells[0][1])}{cells[0][0] + 1}:{col_name(cells[-1][1])}{cells[-1][0] + 1}"
            self.formula.setText(f"={name}({rng if len(cells) > 1 else ''})")
            self.formula.setFocus()

    def _shift(self, at, n, rows):
        def move(d):
            out = {}
            for (r, c), v in d.items():
                k = r if rows else c
                if n < 0 and at <= k < at - n:
                    continue
                if k >= at:
                    k += n
                out[(k, c) if rows else (r, k)] = v
            return out
        self.book.raw = move(self.book.raw)
        self.styles = move(self.styles)

    def insert(self, rows=True):
        at = self.grid.currentRow() if rows else self.grid.currentColumn()
        self._shift(max(0, at), 1, rows)
        if rows:
            self.book.rows += 1
        else:
            self.book.cols += 1
        self.refresh()

    def remove(self, rows=True):
        at = self.grid.currentRow() if rows else self.grid.currentColumn()
        if at < 0:
            return
        self._shift(at, -1, rows)
        self.refresh()

    def clear_cells(self):
        for rc in self._cells():
            self.book.raw.pop(rc, None)
        self.refresh()

    def _register(self, idx):
        if idx <= 0:
            return
        title = self.reg.itemText(idx)
        self.load_book(register_book(title))
        heads = saraban.REGISTERS[title]
        self.spans = [(0, 0, 1, len(heads))]
        self.styles = {(0, 0): {"bold": True, "align": "center"}}
        fm = self.grid.fontMetrics()
        for c, head in enumerate(heads):
            self.grid.setColumnWidth(c, 320 if head == "เรื่อง" else max(90, fm.horizontalAdvance(head) * 14 // 10 + 24))
        for c in range(len(saraban.REGISTERS[title])):
            self.styles[(2, c)] = {"bold": True, "align": "center"}
        self.refresh()
        self.reg.setCurrentIndex(0)
        self.record(f"ตารางคำนวณ: {title}")

    # -- printing
    def to_html(self) -> str:
        """The used part of the sheet as an HTML table in the Thai font, for printing."""
        import html as H
        if not self.book.raw:
            return "<p></p>"
        rows = max(r for r, _ in self.book.raw) + 1
        cols = max(c for _, c in self.book.raw) + 1
        spans = {(r, c): (h, w) for r, c, h, w in getattr(self, "spans", [])}
        hidden = {(r + i, c + j) for (r, c), (h, w) in spans.items() for i in range(h) for j in range(w)} - set(spans)
        out = [f'<table border="1" cellspacing="0" cellpadding="3" style="border-collapse:collapse;'
               f'font-family:\'{self.family}\'; font-size:14pt;">']
        for r in range(rows):
            out.append("<tr>")
            for c in range(cols):
                if (r, c) in hidden:
                    continue
                st = self.styles.get((r, c), {})
                text = H.escape(self.book.display(r, c, self.decimals))
                try:
                    num = isinstance(self.book.value(r, c), float)
                except FormulaError:
                    num = False
                align = st.get("align") or ("right" if num else "left")
                if st.get("bold"):
                    text = f"<b>{text}</b>"
                if st.get("italic"):
                    text = f"<i>{text}</i>"
                h, w = spans.get((r, c), (1, 1))
                out.append(f'<td align="{align}" rowspan="{h}" colspan="{w}">{text or "&nbsp;"}</td>')
            out.append("</tr>")
        out.append("</table>")
        return "".join(out)

    def print_sheet(self):
        from PySide6.QtGui import QTextDocument
        from . import printing
        cols = max((c for _, c in self.book.raw), default=0) + 1

        def make():
            d = QTextDocument()
            d.setHtml(self.to_html())
            return d
        if printing.print_text_document(self, make, "ตาราง", (15, 15, 15, 15), landscape=cols > 6):
            self.record("พิมพ์ตารางคำนวณ")

    # -- files
    def load_book(self, book: Book):
        self.book = book
        self.styles = {}
        self.spans = []
        self.refresh()
        self.grid.setCurrentCell(0, 0)
        self.formula.setText(self.book.raw.get((0, 0), ""))

    def new(self):
        self.load_book(Book())
        self.path = None

    def open(self, path=None):
        if not path:
            path, _ = QFileDialog.getOpenFileName(self, "เปิดตาราง", "",
                                                  "ตารางคำนวณ (*.xlsx);;ตารางข้อมูล (*.csv)")
        if not path:
            return
        try:
            book = load_xlsx(path) if path.lower().endswith(".xlsx") else load_csv(path)
        except Exception as e:                       # noqa: BLE001 - shown to the user
            QMessageBox.warning(self, "ตารางคำนวณ", f"เปิดไฟล์ไม่ได้\n{e}")
            return
        self.load_book(book)
        self.path = path if path.lower().endswith(".xlsx") else None
        self.record("เปิดตารางคำนวณ")

    def save(self, as_new=False):
        path = self.path
        if as_new or not path:
            path, _ = QFileDialog.getSaveFileName(self, "บันทึกตาราง", "ตาราง.xlsx",
                                                  "ตารางคำนวณ (*.xlsx);;ตารางข้อมูล (*.csv)")
        if not path:
            return
        if path.lower().endswith(".csv"):
            save_csv(self.book, path)
        else:
            widths = {c: self.grid.columnWidth(c) for c in range(self.book.cols)}
            save_xlsx(self.book, path, self.styles, saraban.FONT, widths)
            self.path = path
        self.record("บันทึกตารางคำนวณ")
        return path
