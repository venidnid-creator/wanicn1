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
from PySide6.QtGui import QAction, QBrush, QColor, QFont, QFontDatabase, QKeySequence
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QColorDialog, QComboBox, QDialog, QFileDialog,
                               QFormLayout, QFrame, QHBoxLayout, QInputDialog, QMenu, QMenuBar, QPushButton,
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
    "ROUNDUP": lambda a: _round_away(_num(a[0]), int(_num(a[1])) if len(a) > 1 else 0, up=True),
    "ROUNDDOWN": lambda a: _round_away(_num(a[0]), int(_num(a[1])) if len(a) > 1 else 0, up=False),
    "MOD": lambda a: math.fmod(_num(a[0]), _num(a[1])) if _num(a[1]) else _div0(),
    "PRODUCT": lambda a: math.prod(_nums(a)) if _nums(a) else 0.0,
    "SUMIF": lambda a: sum(_numeric(v) for k, v in zip(_flat([a[0]]), _flat([a[2] if len(a) > 2 else a[0]]))
                           if _meets(k, a[1])),
    "COUNTIF": lambda a: float(sum(1 for k in _flat([a[0]]) if _meets(k, a[1]))),
    "AVERAGEIF": lambda a: _avg([_numeric(v) for k, v in zip(_flat([a[0]]), _flat([a[2] if len(a) > 2 else a[0]]))
                                 if _meets(k, a[1]) and _is_num(v)]),
    "AND": lambda a: all(bool(x) for x in _flat(a)),
    "OR": lambda a: any(bool(x) for x in _flat(a)),
    "NOT": lambda a: not a[0],
    "CONCAT": lambda a: "".join(_fmt(x) for x in _flat(a)),
    "CONCATENATE": lambda a: "".join(_fmt(x) for x in _flat(a)),
    "LEN": lambda a: float(len(_fmt(a[0]))),
    "TODAY": lambda a: _today(),
    "BAHTTEXT": lambda a: _bahttext(_num(a[0])),
}


def _is_num(v) -> bool:
    try:
        _num(v)
        return not isinstance(v, str) or bool(v.strip())
    except (FormulaError, ValueError, TypeError):
        return False


def _numeric(v) -> float:
    try:
        return float(_num(v))
    except (FormulaError, ValueError, TypeError):
        return 0.0


def _round_away(x, d, up):
    f = 10 ** d
    v = abs(x) * f
    v = math.ceil(v - 1e-9) if up else math.floor(v + 1e-9)
    return math.copysign(v / f, x)


def _div0():
    raise FormulaError("#DIV/0!")


def _avg(vals):
    return sum(vals) / len(vals) if vals else _div0()


def _meets(value, crit) -> bool:
    """Excel criteria: 5, ">5", "<>0", "=ก", "ก" (text equal)."""
    if isinstance(crit, (int, float)) and not isinstance(crit, bool):
        try:
            return float(_num(value)) == float(crit)
        except (FormulaError, ValueError, TypeError):
            return False
    c = str(crit)
    m = re.match(r"^(<=|>=|<>|<|>|=)?(.*)$", c)
    op, rhs = m.group(1) or "=", m.group(2)
    try:
        b = float(rhs.replace(",", ""))
    except ValueError:
        b = None
    if b is not None:                       # a number to compare: text cells never match
        try:
            a = float(_num(value))
        except (FormulaError, ValueError, TypeError):
            return op == "<>"
    else:
        a, b = _fmt(value), rhs
    return {"=": a == b, "<>": a != b, "<": a < b, ">": a > b, "<=": a <= b, ">=": a >= b}[op]


def _today():
    import datetime as dt
    d = dt.date.today()
    return f"{d.day}/{d.month}/{d.year + 543}"


def _bahttext(x):
    from .procure import baht_text
    return baht_text(x)
#: Thai names for the functions menu.
FUNC_TH = {"SUM": "ผลรวม", "AVERAGE": "ค่าเฉลี่ย", "MIN": "ค่าน้อยสุด", "MAX": "ค่ามากสุด",
           "COUNT": "นับตัวเลข", "COUNTA": "นับช่องที่มีข้อมูล", "ROUND": "ปัดเศษ", "ROUNDUP": "ปัดขึ้น",
           "ROUNDDOWN": "ปัดลง", "SUMIF": "ผลรวมตามเงื่อนไข", "COUNTIF": "นับตามเงื่อนไข",
           "AVERAGEIF": "ค่าเฉลี่ยตามเงื่อนไข", "IF": "ถ้า…แล้ว", "PRODUCT": "ผลคูณ", "MOD": "เศษจากการหาร",
           "ABS": "ค่าสัมบูรณ์", "SQRT": "รากที่สอง", "POWER": "ยกกำลัง", "CONCAT": "ต่อข้อความ",
           "LEN": "ความยาวข้อความ", "TODAY": "วันที่วันนี้", "BAHTTEXT": "จำนวนเงินเป็นตัวอักษร"}


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


_REF_IN = re.compile(r'(\"[^\"]*\")|(\$?)([A-Za-z]{1,2})(\$?)(\d+)(?![\w(])')


def shift_refs(formula: str, dr: int, dc: int) -> str:
    """=A1+B$2 moved by (dr, dc), as Excel does when a formula is copied: $ keeps a row or column."""
    if not formula.startswith("="):
        return formula

    def one(m):
        if m.group(1):
            return m.group(1)
        cd, col, rd, row = m.group(2), m.group(3), m.group(4), int(m.group(5))
        c = col_index(col) if cd else max(0, col_index(col) + dc)
        r = row if rd else max(1, row + dr)
        return f"{cd}{col_name(c)}{rd}{r}"
    return "=" + _REF_IN.sub(one, formula[1:])


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

def save_xlsx(book: Book, path, styles=None, family=saraban.FONT, widths=None, spans=None):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
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
                         italic=st.get("italic", False), underline="single" if st.get("underline") else None,
                         color=st["fg"].lstrip("#").upper() if st.get("fg") else None)
        if st.get("bg"):
            cell.fill = PatternFill("solid", fgColor=st["bg"].lstrip("#").upper())
        if st.get("fmt") == "comma":
            cell.number_format = "#,##0.00"
        elif st.get("fmt") == "percent":
            cell.number_format = "0.00%"
        if st.get("align"):
            cell.alignment = Alignment(horizontal=st["align"])
    for c, w in (widths or {}).items():
        ws.column_dimensions[col_name(c)].width = max(4, w / 7)
    for r, c, h, w in spans or []:
        if h > 1 or w > 1:
            ws.merge_cells(start_row=r + 1, start_column=c + 1, end_row=r + h, end_column=c + w)
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
        self._undo, self._redo = [], []
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.menu_bar = QMenuBar()
        self.menu_bar.setNativeMenuBar(False)
        lay.addWidget(self.menu_bar)
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
        self.grid.setContextMenuPolicy(Qt.CustomContextMenu)
        self.grid.customContextMenuRequested.connect(self._context_menu)
        self.grid.installEventFilter(self)
        lay.addWidget(self.grid, 1)
        self.status = QLabel("")
        self.status.setContentsMargins(8, 2, 8, 2)
        lay.addWidget(self.status)
        self.grid.itemSelectionChanged.connect(self._summary)
        self._menus()
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
        from .fit import FlowLayout
        bar = QFrame()
        bar.setObjectName("ToolRow")
        col = QVBoxLayout(bar)
        col.setContentsMargins(6, 4, 6, 4)
        row = FlowLayout(None, 0, 2, 2)
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
        row = FlowLayout(None, 0, 2, 2)
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
        row = FlowLayout(None, 0, 2, 2)
        for text, tip, fn in (("↶ เลิกทำ", "เลิกทำ (Ctrl+Z)", self.undo), ("↷ ทำซ้ำ", "ทำซ้ำ (Ctrl+Y)", self.redo),
                              ("✂ ตัด", "ตัด (Ctrl+X)", self.cut), ("📋 คัดลอก", "คัดลอก (Ctrl+C)", self.copy),
                              ("📥 วาง", "วาง (Ctrl+V) — วางจาก Excel ได้ สูตรเลื่อนอ้างอิงตามตำแหน่ง", self.paste),
                              ("📄 วางเฉพาะค่า", "วางเฉพาะค่าที่คำนวณแล้ว (Ctrl+Shift+V)", lambda: self.paste(values=True)),
                              ("⬇ เติมลง", "คัดลอกช่องบนสุดลงทุกช่องที่เลือก (Ctrl+D)", lambda: self.fill(down=True)),
                              ("➡ เติมขวา", "คัดลอกช่องซ้ายสุดไปทางขวา (Ctrl+R)", lambda: self.fill(down=False)),
                              ("A→Z", "เรียงจากน้อยไปมาก ตามคอลัมน์ที่เลือก", lambda: self.sort(True)),
                              ("Z→A", "เรียงจากมากไปน้อย ตามคอลัมน์ที่เลือก", lambda: self.sort(False)),
                              ("🔎 ค้นหา/แทนที่", "ค้นหาและแทนที่ (Ctrl+F / Ctrl+H)", self.find_replace)):
            row.addWidget(self._tool(text, tip, fn))
        u = self._tool("ข", "ขีดเส้นใต้", lambda on: self._style(underline=on), True)
        u.setStyleSheet("text-decoration:underline;")
        row.addWidget(u)
        for text, tip, fn in (("🎨 สีตัวอักษร", "สีตัวอักษร", lambda: self.pick_color("fg")),
                              ("🪣 สีพื้น", "สีพื้นช่อง", lambda: self.pick_color("bg")),
                              (",", "รูปแบบตัวเลขมีจุลภาค 1,234.56", lambda: self._style(fmt="comma")),
                              ("%", "รูปแบบร้อยละ", lambda: self._style(fmt="percent")),
                              ("⊞ ผสานเซลล์", "ผสานช่องที่เลือก / ยกเลิกการผสาน", self.merge),
                              ("↔ พอดีข้อความ", "ปรับความกว้างคอลัมน์ให้พอดีข้อความ", self.autofit)):
            row.addWidget(self._tool(text, tip, fn))
        row.addStretch(1)
        col.addLayout(row)
        return bar

    # -- display
    def refresh(self):
        cur = (self.grid.currentRow(), self.grid.currentColumn())
        picked = [(i.row(), i.column()) for i in self.grid.selectedIndexes()]
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
        if cur[0] >= 0:                            # the cell and the selection stay where they were
            from PySide6.QtCore import QItemSelectionModel
            self.grid.setCurrentCell(*cur, QItemSelectionModel.NoUpdate)
            sm = self.grid.selectionModel()
            for r, c in picked:
                if r < self.grid.rowCount() and c < self.grid.columnCount():
                    sm.select(self.grid.model().index(r, c), QItemSelectionModel.Select)
        self._busy = False

    def _paint(self, r, c, dec=None):
        if r >= self.grid.rowCount() or c >= self.grid.columnCount():
            return
        st0 = self.styles.get((r, c), {})
        text = self.book.display(r, c, dec)
        if st0.get("fmt"):
            try:
                v0 = self.book.value(r, c)
            except FormulaError:
                v0 = None
            if isinstance(v0, float) and not isinstance(v0, bool):
                d = 2 if dec is None else dec
                text = f"{v0:,.{d}f}" if st0["fmt"] == "comma" else f"{v0 * 100:,.{d}f}%"
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
        f.setUnderline(st.get("underline", False))
        it.setFont(f)
        it.setForeground(QBrush(QColor(st["fg"])) if st.get("fg") else QBrush())
        it.setBackground(QBrush(QColor(st["bg"])) if st.get("bg") else QBrush())
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
        self._push()
        self.book.set(item.row(), item.column(), item.text())
        self._recalc()
        self.formula.setText(self.book.raw.get((item.row(), item.column()), ""))

    def _commit_formula(self):
        r, c = self.grid.currentRow(), self.grid.currentColumn()
        if r < 0:
            return
        self._push()
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
        self._push()
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

    # -- Excel-like menus, clipboard, undo
    def _menus(self):
        mb = self.menu_bar

        def add(menu, text, fn, key=None):
            a = QAction(text, self)
            if key:
                a.setShortcut(QKeySequence(key))
                a.setShortcutContext(Qt.WidgetWithChildrenShortcut)
            a.triggered.connect(lambda _=False: fn())
            menu.addAction(a)
            self.addAction(a)
            return a
        f = mb.addMenu("แฟ้ม")
        add(f, "📄 สร้างใหม่", self.new, "Ctrl+N")
        add(f, "📂 เปิด…", self.open, "Ctrl+O")
        add(f, "💾 บันทึก", self.save, "Ctrl+S")
        add(f, "💾 บันทึกเป็น…", lambda: self.save(True), "Ctrl+Shift+S")
        f.addSeparator()
        add(f, "🖨 พิมพ์…", self.print_sheet, "Ctrl+P")
        e = mb.addMenu("แก้ไข")
        add(e, "↶ เลิกทำ", self.undo, "Ctrl+Z")
        add(e, "↷ ทำซ้ำ", self.redo, "Ctrl+Y")
        e.addSeparator()
        add(e, "✂ ตัด", self.cut, "Ctrl+X")
        add(e, "📋 คัดลอก", self.copy, "Ctrl+C")
        add(e, "📥 วาง", self.paste, "Ctrl+V")
        add(e, "📄 วางเฉพาะค่า", lambda: self.paste(values=True), "Ctrl+Shift+V")
        add(e, "⬇ เติมลง", lambda: self.fill(down=True), "Ctrl+D")
        add(e, "➡ เติมขวา", lambda: self.fill(down=False), "Ctrl+R")
        e.addSeparator()
        add(e, "⌫ ล้างข้อมูล", self.clear_cells)
        add(e, "เลือกทั้งหมด", self.grid.selectAll, "Ctrl+A")
        add(e, "🔎 ค้นหา/แทนที่…", self.find_replace, "Ctrl+F")
        add(e, "แทนที่…", self.find_replace, "Ctrl+H")
        i = mb.addMenu("แทรก")
        add(i, "แถวเหนือแถวนี้", lambda: self.insert(rows=True))
        add(i, "คอลัมน์ทางซ้าย", lambda: self.insert(rows=False))
        add(i, "ƒ ฟังก์ชัน…", self.insert_func, "Shift+F3")
        add(i, "Σ ผลรวมอัตโนมัติ", self.auto_sum, "Alt+=")
        r = mb.addMenu("รูปแบบ")
        add(r, "ตัวหนา", lambda: self._toggle("bold"), "Ctrl+B")
        add(r, "ตัวเอียง", lambda: self._toggle("italic"), "Ctrl+I")
        add(r, "ขีดเส้นใต้", lambda: self._toggle("underline"), "Ctrl+U")
        add(r, "🎨 สีตัวอักษร…", lambda: self.pick_color("fg"))
        add(r, "🪣 สีพื้นช่อง…", lambda: self.pick_color("bg"))
        r.addSeparator()
        add(r, "ชิดซ้าย", lambda: self._style(align="left"))
        add(r, "กึ่งกลาง", lambda: self._style(align="center"))
        add(r, "ชิดขวา", lambda: self._style(align="right"))
        r.addSeparator()
        add(r, "ตัวเลขมีจุลภาค 1,234.56", lambda: self._style(fmt="comma"))
        add(r, "ร้อยละ %", lambda: self._style(fmt="percent"))
        add(r, "ตัวเลขทั่วไป", lambda: self._style(fmt=""))
        add(r, "⊞ ผสานเซลล์ / ยกเลิก", self.merge)
        add(r, "↔ ความกว้างคอลัมน์พอดีข้อความ", self.autofit)
        add(r, "ล้างรูปแบบ", self.clear_format)
        d = mb.addMenu("ข้อมูล")
        add(d, "A→Z เรียงจากน้อยไปมาก", lambda: self.sort(True))
        add(d, "Z→A เรียงจากมากไปน้อย", lambda: self.sort(False))
        g = mb.addMenu("สูตร")
        add(g, "Σ ผลรวมอัตโนมัติ", self.auto_sum)
        add(g, "ƒ แทรกฟังก์ชัน…", self.insert_func)
        add(g, "คำนวณใหม่", self._recalc, "F9")

    def _context_menu(self, pos):
        m = QMenu(self)
        for text, fn in (("✂ ตัด", self.cut), ("📋 คัดลอก", self.copy), ("📥 วาง", self.paste),
                         ("📄 วางเฉพาะค่า", lambda: self.paste(values=True))):
            m.addAction(text, fn)
        m.addSeparator()
        for text, fn in (("แทรกแถว", lambda: self.insert(rows=True)), ("แทรกคอลัมน์", lambda: self.insert(rows=False)),
                         ("ลบแถว", lambda: self.remove(rows=True)), ("ลบคอลัมน์", lambda: self.remove(rows=False)),
                         ("⌫ ล้างข้อมูล", self.clear_cells)):
            m.addAction(text, fn)
        m.addSeparator()
        m.addAction("⊞ ผสานเซลล์ / ยกเลิก", self.merge)
        m.addAction("🪣 สีพื้นช่อง…", lambda: self.pick_color("bg"))
        m.exec(self.grid.viewport().mapToGlobal(pos))

    def eventFilter(self, obj, e):
        from PySide6.QtCore import QEvent
        if obj is self.grid and e.type() == QEvent.KeyPress and self.grid.state() != QAbstractItemView.EditingState:
            if e.key() in (Qt.Key_Delete, Qt.Key_Backspace) and not e.modifiers():
                self.clear_cells()
                return True
        return super().eventFilter(obj, e)

    def _snapshot(self):
        return (dict(self.book.raw), {k: dict(v) for k, v in self.styles.items()}, list(getattr(self, "spans", [])),
                self.book.rows, self.book.cols)

    def _restore(self, snap):
        raw, styles, spans, rows, cols = snap
        self.book.raw, self.styles, self.spans = dict(raw), styles, list(spans)
        self.book.rows, self.book.cols = rows, cols
        self.refresh()

    def _push(self):
        self._undo.append(self._snapshot())
        del self._undo[:-100]
        self._redo.clear()

    def undo(self):
        if self._undo:
            self._redo.append(self._snapshot())
            self._restore(self._undo.pop())

    def redo(self):
        if self._redo:
            self._undo.append(self._snapshot())
            self._restore(self._redo.pop())

    def _rect(self):
        cells = self._cells()
        rs, cs = [r for r, _ in cells], [c for _, c in cells]
        return min(rs), min(cs), max(rs), max(cs)

    def copy(self, values=False):
        r0, c0, r1, c1 = self._rect()
        rows = []
        for r in range(r0, r1 + 1):
            rows.append("\t".join((self.book.display(r, c) if values else self.book.raw.get((r, c), ""))
                                  for c in range(c0, c1 + 1)))
        text = "\n".join(rows)
        QApplication.clipboard().setText(text)
        self._clip = (text, r0, c0)
        return text

    def cut(self):
        self.copy()
        self.clear_cells()

    def paste(self, values=False):
        """Paste text from here or from Excel (tab-separated); formulas copied here move their
        references with the cells, as in Excel; «values» keeps only the worked-out values."""
        text = QApplication.clipboard().text()
        if not text:
            return
        r0, c0 = max(0, self.grid.currentRow()), max(0, self.grid.currentColumn())
        clip = getattr(self, "_clip", None)
        ours = bool(clip) and clip[0] == text
        dr, dc = (r0 - clip[1], c0 - clip[2]) if ours else (0, 0)
        lines = text.replace("\r\n", "\n").rstrip("\n").split("\n")
        cells = [ln.split("\t") for ln in lines]
        vals = {}
        if values and ours:                              # worked out at the source before anything moves
            for i, row in enumerate(cells):
                for j, v in enumerate(row):
                    if v.strip().startswith("="):
                        try:
                            vals[(i, j)] = _fmt(self.book.value(clip[1] + i, clip[2] + j))
                        except FormulaError:
                            vals[(i, j)] = ""
        self._push()
        self.book.rows = max(self.book.rows, r0 + len(cells))
        self.book.cols = max(self.book.cols, c0 + max(len(row) for row in cells))
        for i, row in enumerate(cells):
            for j, v in enumerate(row):
                v = v.strip()
                if v.startswith("="):
                    v = vals.get((i, j), "") if values else shift_refs(v, dr, dc)
                self.book.set(r0 + i, c0 + j, v)
        self.refresh()
        self.record("ตารางคำนวณ: วาง")

    def fill(self, down=True):
        r0, c0, r1, c1 = self._rect()
        self._push()
        if down:
            for c in range(c0, c1 + 1):
                src = self.book.raw.get((r0, c), "")
                for r in range(r0 + 1, r1 + 1):
                    self.book.set(r, c, shift_refs(src, r - r0, 0))
                    if (r0, c) in self.styles:
                        self.styles[(r, c)] = dict(self.styles[(r0, c)])
        else:
            for r in range(r0, r1 + 1):
                src = self.book.raw.get((r, c0), "")
                for c in range(c0 + 1, c1 + 1):
                    self.book.set(r, c, shift_refs(src, 0, c - c0))
        self.refresh()

    def sort(self, ascending=True):
        """Sort the rows of the selection (or of the table under its header row) by the current column."""
        r0, c0, r1, c1 = self._rect()
        key_c = self.grid.currentColumn() if self.grid.currentColumn() >= 0 else c0
        if r0 == r1:                                     # one cell: the used block below its first row
            used = [r for r, _ in self.book.raw]
            cols = [c for _, c in self.book.raw]
            r0, r1 = min(used, default=0) + 1, max(used, default=0)
            c0, c1 = min(cols, default=0), max(cols, default=0)
        self._push()
        rows = [{c: self.book.raw.get((r, c)) for c in range(c0, c1 + 1)} for r in range(r0, r1 + 1)]

        def key(row):
            v = row.get(key_c) or ""
            try:
                return (0, float(v.replace(",", "")), "")
            except ValueError:
                return (1, 0.0, v)
        full = [row for row in rows if row.get(key_c)]
        blank = [row for row in rows if not row.get(key_c)]     # empty rows stay at the end, as in Excel
        rows = sorted(full, key=key, reverse=not ascending) + blank
        for i, row in enumerate(rows):
            for c, v in row.items():
                self.book.set(r0 + i, c, v)
        self.refresh()

    def find_replace(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("ค้นหาและแทนที่")
        form = QFormLayout(dlg)
        what, by = QLineEdit(), QLineEdit()
        form.addRow("ค้นหา", what)
        form.addRow("แทนที่ด้วย", by)
        note = QLabel("")
        form.addRow(note)
        row = QHBoxLayout()

        def find_next():
            cells = sorted(k for k, v in self.book.raw.items() if what.text() and what.text() in v)
            if not cells:
                note.setText("ไม่พบข้อความ")
                return
            cur = (self.grid.currentRow(), self.grid.currentColumn())
            nxt = next((k for k in cells if k > cur), cells[0])
            self.grid.setCurrentCell(*nxt)
            note.setText(f"พบ {len(cells)} ช่อง")

        def replace_all():
            note.setText(f"แทนที่แล้ว {self.replace_all(what.text(), by.text())} ช่อง")
        for text, fn in (("ค้นหาถัดไป", find_next), ("แทนที่ทั้งหมด", replace_all), ("ปิด", dlg.accept)):
            b = QPushButton(text)
            b.clicked.connect(fn)
            row.addWidget(b)
        form.addRow(row)
        dlg.show()
        self._find_dialog = dlg
        return dlg

    def replace_all(self, what, by) -> int:
        if not what:
            return 0
        self._push()
        n = 0
        for k, v in list(self.book.raw.items()):
            if what in v:
                self.book.set(*k, v.replace(what, by))
                n += 1
        self.refresh()
        return n

    def _toggle(self, key):
        r, c = self._cells()[0]
        self._style(**{key: not self.styles.get((r, c), {}).get(key, False)})

    def pick_color(self, which, color=None):
        c = color or QColorDialog.getColor(QColor("#000000" if which == "fg" else "#FFF2CC"), self,
                                           "สีตัวอักษร" if which == "fg" else "สีพื้นช่อง")
        if c and c.isValid():
            self._style(**{which: c.name()})

    def clear_format(self):
        self._push()
        for rc in self._cells():
            self.styles.pop(rc, None)
        self.refresh()

    def merge(self):
        r0, c0, r1, c1 = self._rect()
        self._push()
        spans = list(getattr(self, "spans", []))
        if any(s_[0] == r0 and s_[1] == c0 for s_ in spans) or (r0 == r1 and c0 == c1):
            self.spans = [s_ for s_ in spans if not (s_[0] == r0 and s_[1] == c0)]
        else:
            self.spans = spans + [(r0, c0, r1 - r0 + 1, c1 - c0 + 1)]
            self.styles.setdefault((r0, c0), {}).setdefault("align", "center")
        self.refresh()

    def autofit(self):
        r0, c0, r1, c1 = self._rect()
        fm = self.grid.fontMetrics()
        for c in range(c0, c1 + 1):
            texts = [self.book.display(r, c, self.decimals) for (r, cc) in self.book.raw if cc == c]
            w = max([fm.horizontalAdvance(t) for t in texts] + [60])
            self.grid.setColumnWidth(c, min(600, int(w * 1.15) + 24))

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
        self._push()
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
        self._push()
        self._shift(at, -1, rows)
        self.refresh()

    def clear_cells(self):
        self._push()
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
            save_xlsx(self.book, path, self.styles, saraban.FONT, widths, getattr(self, "spans", []))
            self.path = path
        self.record("บันทึกตารางคำนวณ")
        return path
