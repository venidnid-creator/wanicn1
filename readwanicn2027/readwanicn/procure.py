# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2569 (2026) นายเวนิช ธัมมะวงษ์ วิศวกรสำรวจ — ReadWanicn2027
"""Price reduction after the bid (ว651), the work plan (ว124) and the
domestic-material plans (ว78) from a bill of quantities (ปร.4).

Everything here is plain Python: reading the bill from a spreadsheet,
a document or a PDF, the calculation and the saved project file.
The reports are in procure_report.py and the window in procure_view.py.

Sources (กรมบัญชีกลาง):
- ว651  ที่ กค (กวจ) 0405.3/ว651 ลว. 26 ก.ย. 2568 — แนวทางการปรับลดราคาในแบบแสดงรายการ ปริมาณงาน และราคา
- ว124  แนวทางเร่งรัดการปฏิบัติงานตามสัญญา — แผนการทำงาน (Money, %PLAN, %ACC PLAN), เกณฑ์ ½ / ¾ / ครบกำหนด
- ว78   แนวทางตามกฎกระทรวงพัสดุที่รัฐส่งเสริม (ฉบับที่ 2) 2563 — พัสดุในประเทศ ≥ 60 % (มูลค่า),
        เหล็กในประเทศ ≥ 90 % (ปริมาณ), ภาคผนวก 1–3
"""
from __future__ import annotations

import json
import math
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

THAI_DIGITS = str.maketrans("๐๑๒๓๔๕๖๗๘๙", "0123456789")

DOMESTIC_MIN = 60.0          # ว78: พัสดุที่ผลิตในประเทศ ≥ ร้อยละ 60 ของมูลค่าพัสดุ
STEEL_MIN = 90.0             # ว78: เหล็กที่ผลิตในประเทศ ≥ ร้อยละ 90 ของปริมาณเหล็ก
EXEMPT_DAYS = 60             # ว78: สัญญาไม่เกิน 60 วัน ไม่ต้องทำแผน
EXEMPT_AMOUNT = 500_000.0    # ว78: วงเงินไม่เกิน 500,000 บาท ไม่ต้องทำแผน
VAT_FACTOR = 1.07           # ครุภัณฑ์จัดซื้อ: คิดเฉพาะภาษีมูลค่าเพิ่ม
SOUTH_UPLIFT = 1.05         # ว651 ตัวอย่างที่ 2: งานใน 3 จังหวัดชายแดนภาคใต้ ราคากลางบวกเพิ่มร้อยละ 5
# ว651 มีตัวอย่าง 4 งาน: key → (ชื่องานในแบบ, คำในหัวคอลัมน์ปริมาณ, บวกเพิ่ม)
WORK_TYPES = {
    "building": ("งานก่อสร้างอาคาร", "จำนวน", 1.0),
    "building_south": ("งานก่อสร้างอาคาร", "จำนวน", SOUTH_UPLIFT),
    "road": ("งานก่อสร้างทาง สะพาน และท่อเหลี่ยม", "ปริมาณ", 1.0),
    "irrigation": ("งานก่อสร้างชลประทาน", "ปริมาณ", 1.0),
}
WORK_TYPE_NAMES = {
    "building": "1. งานก่อสร้างอาคาร",
    "building_south": "2. งานก่อสร้างอาคาร ใน 3 จังหวัดชายแดนภาคใต้ (บวกเพิ่มร้อยละ 5)",
    "road": "3. งานก่อสร้างทาง สะพาน และท่อเหลี่ยม",
    "irrigation": "4. งานก่อสร้างชลประทาน",
}
SOUTH_NOTE = "(กรณีงานก่อสร้างใน 3 จังหวัดชายแดนภาคใต้ ได้แก่ จังหวัดยะลา จังหวัดปัตตานี และจังหวัดนราธิวาส)"
STEEL_DENSITY = 7850.0       # กก./ลบ.ม.
DEFAULT_BAR_LENGTH = 6.0     # ม. ต่อท่อน เมื่อไม่ได้ระบุความยาว
# ว124 ข้อ 2.2: ผลงานสะสมขั้นต่ำเมื่อพ้นเวลา ½, ¾ และครบกำหนด
CHECKPOINTS = ((0.5, 25.0, "เกิน 1 ใน 2 ของระยะเวลา"), (0.75, 65.0, "เกิน 3 ใน 4 ของระยะเวลา"),
               (1.0, 85.0, "ครบกำหนดส่งมอบ"))


# -- numbers and words ---------------------------------------------------------------------

def num(v):
    """A number from a cell: 1,234.50 / ๑๒๓ / '-' / '' → float or None."""
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v) if math.isfinite(v) else None
    s = str(v).translate(THAI_DIGITS).strip().replace(",", "").replace("฿", "").replace(" ", "")
    if s in ("", "-", "–", "—"):
        return None
    neg = s.startswith("(") and s.endswith(")")
    s = s.strip("()")
    try:
        x = float(s)
    except ValueError:
        return None
    return -x if neg else x


def text(v) -> str:
    """Cell text, with Thai digits written as Arabic digits (๓ → 3)."""
    if v is None:
        return ""
    if isinstance(v, float):
        return f"{v:g}"
    s = str(v).translate(THAI_DIGITS).replace("\r", " ").replace("\n", " ")
    return CONTROL_RE.sub(" ", s).strip()        # Excel's line feeds (\x0b) and other control characters


CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def arabic(s) -> str:
    return str(s or "").translate(THAI_DIGITS)


THAI_MONTHS = ("มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม", "มิถุนายน", "กรกฎาคม", "สิงหาคม",
               "กันยายน", "ตุลาคม", "พฤศจิกายน", "ธันวาคม")
THAI_MONTHS_SHORT = ("ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.", "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค.")


def iso_date(s):
    """datetime.date from 'YYYY-MM-DD', or None (old files kept free text)."""
    import datetime as dt
    try:
        return dt.date.fromisoformat(str(s)[:10])
    except (TypeError, ValueError):
        return None


def thai_date(s) -> str:
    """'2026-11-14' → '14 พฤศจิกายน 2569' (Arabic digits, Buddhist year); other text unchanged."""
    d = iso_date(s)
    if d is None:
        return arabic(s)
    return f"{d.day} {THAI_MONTHS[d.month - 1]} {d.year + 543}"


def month_labels(start, n: int) -> list:
    """Calendar month of each plan month from the start date: ['พ.ย. 69', 'ธ.ค. 69', …] or [] without a date."""
    d = iso_date(start)
    if d is None:
        return []
    out = []
    for k in range(n):
        m = d.month - 1 + k
        y, m = d.year + m // 12, m % 12
        out.append(f"{THAI_MONTHS_SHORT[m]} {(y + 543) % 100:02d}")
    return out


def r2(x: float) -> float:
    """Round to satang, half away from zero (as money is written)."""
    return math.floor(abs(x) * 100 + 0.5 + 1e-9) / 100 * (1 if x >= 0 else -1)


def money(x, blank_zero=False) -> str:
    if x is None or (blank_zero and abs(x) < 0.005):
        return ""
    return f"{x:,.2f}"


def baht_text(amount: float) -> str:
    """จำนวนเงินเป็นตัวอักษร: 4,790,000.00 → สี่ล้านเจ็ดแสนเก้าหมื่นบาทถ้วน"""
    digits = ["", "หนึ่ง", "สอง", "สาม", "สี่", "ห้า", "หก", "เจ็ด", "แปด", "เก้า"]
    places = ["", "สิบ", "ร้อย", "พัน", "หมื่น", "แสน"]

    def say(n: int) -> str:
        if n == 0:
            return ""
        if n >= 1_000_000:
            return say(n // 1_000_000) + "ล้าน" + say(n % 1_000_000)
        out, s = "", str(n)
        for i, ch in enumerate(s):
            d, p = int(ch), len(s) - i - 1
            if d == 0:
                continue
            if p == 1 and d == 1:
                out += "สิบ"
            elif p == 1 and d == 2:
                out += "ยี่สิบ"
            elif p == 0 and d == 1 and len(s) > 1:
                out += "เอ็ด"
            else:
                out += digits[d] + places[p]
        return out

    amount = r2(amount)
    whole, satang = int(amount), int(round((amount - int(amount)) * 100))
    words = (say(whole) or "ศูนย์") + "บาท"
    return words + (say(satang) + "สตางค์" if satang else "ถ้วน")


# -- the bill --------------------------------------------------------------------------------

CODE_RE = re.compile(r"^\s*[-–]?\s*((?:\d+\.)*\d+)\.?\s+(?=\S)")


@dataclass
class Item:
    name: str
    unit: str = ""
    qty: float = 0.0
    mat_unit: float = 0.0
    mat_amt: float = 0.0
    lab_unit: float = 0.0
    lab_amt: float = 0.0
    cost: float = 0.0               # ค่างานต้นทุน (ค่าวัสดุและแรงงาน)
    no: str = ""                    # ลำดับที่ในไฟล์ต้นทาง
    code: str = ""                  # 1.1.2.1 จากชื่อรายการ
    level: int = 1
    header: bool = False            # หัวข้อ/กลุ่มงาน (ไม่มีปริมาณและราคา)
    special: bool = False           # ค่าใช้จ่ายพิเศษตามข้อกำหนด: ไม่ปรับลด
    equip: bool = False             # งานครุภัณฑ์จัดซื้อ: Factor = VAT 1.07
    # ว78
    domestic: float = 100.0         # ร้อยละพัสดุในประเทศ
    steel: bool | None = None       # None = ให้โปรแกรมตัดสินจากชื่อ
    kg_per_unit: float | None = None
    # ว124: ร้อยละของรายการในแต่ละเดือน
    plan: list = field(default_factory=list)

    @property
    def label(self) -> str:
        return self.name.strip()

    @property
    def is_steel(self) -> bool:
        return steel_guess(self) if self.steel is None else bool(self.steel)


def split_code(name: str):
    m = CODE_RE.match(name or "")
    if not m:
        return "", 1
    code = m.group(1)
    return code, code.count(".") + 1


@dataclass
class Project:
    title: str = ""                 # ชื่อโครงการ/งานก่อสร้าง
    agency: str = ""                # หน่วยงานเจ้าของโครงการ
    place: str = ""                 # สถานที่ก่อสร้าง
    contractor: str = ""            # ชื่อผู้รับจ้าง
    contract_no: str = ""
    contract_date: str = ""
    budget: float = 0.0             # วงเงินงบประมาณ
    project_no: str = ""            # เลขที่โครงการ (e-GP)
    work_type: str = "building"     # key of WORK_TYPES (ว651 ตัวอย่าง 4 งาน)
    factor: float = 0.0             # Factor F / Vat ในไฟล์ (0 = ไม่ทราบ)
    mid_price: float = 0.0          # ราคากลาง (รวมค่าใช้จ่ายพิเศษ)
    offer: float = 0.0              # ราคาตามคำเสนอของผู้ชนะ
    special: float = 0.0            # ค่าใช้จ่ายพิเศษตามข้อกำหนด
    months: int = 0                 # ว124
    days: int = 0
    start: str = ""                 # วันเริ่มงาน YYYY-MM-DD (ค.ศ.) ไม่ใส่ก็ได้
    actual: list = field(default_factory=list)   # ว124: ผลงานจริงรายเดือน (% ของทั้งโครงการ)
    source: str = ""                # ไฟล์ที่นำเข้า
    signer: str = ""                # ผู้จัดทำ/ผู้รับจ้าง (ลงชื่อท้ายแผน)
    items: list = field(default_factory=list)

    # -- persistence
    def to_dict(self) -> dict:
        d = asdict(self)
        d["format"] = "readwanicn-procure-1"
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Project":
        d = dict(d)
        d.pop("format", None)
        items = [Item(**{k: v for k, v in it.items() if k in Item.__dataclass_fields__})
                 for it in d.pop("items", [])]
        for it in items:                              # older files kept Thai digits
            it.name, it.unit = arabic(it.name), arabic(it.unit)
        for k in ("title", "agency", "place", "contractor", "contract_no", "project_no"):
            if isinstance(d.get(k), str):
                d[k] = arabic(d[k])
        p = cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})
        p.items = items
        return p

    def save(self, path) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=1), encoding="utf-8")

    @classmethod
    def load(cls, path) -> "Project":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))

    # -- the bill
    @property
    def work(self) -> tuple:
        return WORK_TYPES.get(self.work_type, WORK_TYPES["building"])

    @property
    def uplift(self) -> float:
        return self.work[2]

    @property
    def leaves(self) -> list:
        return [it for it in self.items if not it.header]

    @property
    def cost_total(self) -> float:
        """ค่างานต้นทุนงานก่อสร้าง (ไม่รวมครุภัณฑ์และค่าใช้จ่ายพิเศษ)"""
        return sum(it.cost for it in self.leaves if not it.special and not it.equip)

    @property
    def equip_total(self) -> float:
        return sum(it.cost for it in self.leaves if it.equip and not it.special)

    @property
    def special_items_total(self) -> float:
        return sum(it.cost for it in self.leaves if it.special)


# -- reading tables ---------------------------------------------------------------------------

def _rows_xls(path) -> list:
    import xlrd
    book = xlrd.open_workbook(str(path))
    sheets = []
    for sh in book.sheets():
        rows = [[sh.cell_value(r, c) for c in range(sh.ncols)] for r in range(sh.nrows)]
        sheets.append((sh.name, rows))
    return sheets


def _rows_xlsx(path) -> list:
    from openpyxl import load_workbook
    wb = load_workbook(str(path), data_only=True, read_only=True)
    sheets = []
    for ws in wb.worksheets:
        sheets.append((ws.title, [list(r) for r in ws.iter_rows(values_only=True)]))
    wb.close()
    return sheets


def _rows_csv(path) -> list:
    import csv
    raw = Path(path).read_bytes()
    for enc in ("utf-8-sig", "cp874", "tis-620"):
        try:
            s = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        s = raw.decode("utf-8", "replace")
    return [(Path(path).stem, [r for r in csv.reader(s.splitlines())])]


def _rows_docx(path) -> list:
    import docx
    d = docx.Document(str(path))
    rows, info = [], []
    for p in d.paragraphs:
        if p.text.strip():
            info.append([p.text.strip()])
    for t in d.tables:
        for row in t.rows:
            cells, last = [], None
            for c in row.cells:            # merged cells repeat: keep the first copy only
                cells.append("" if c._tc is last else c.text)
                last = c._tc
            rows.append(cells)
    return [(Path(path).stem, info + rows)]


def _rows_pdf(path) -> list:
    import pymupdf
    doc = pymupdf.open(str(path))
    rows = []
    for page in doc:
        for line in page.get_text().splitlines()[:12]:        # title lines carry the project name
            if line.strip():
                rows.append([line.strip()])
        try:
            tabs = page.find_tables()
        except Exception:                                     # an odd page: skip its tables
            continue
        words = page.get_text("words")             # Thai marks stay in order here, unlike extract()
        for t in tabs.tables:
            rows += _table_lines(t, words)
    doc.close()
    return [(Path(path).stem, rows)]


def _words_in(words, box) -> str:
    """The words whose middle is inside a table cell, in reading order."""
    if not box:
        return ""
    x0, y0, x1, y1 = box
    inside = [w for w in words if x0 <= (w[0] + w[2]) / 2 <= x1 and y0 <= (w[1] + w[3]) / 2 <= y1]
    inside.sort(key=lambda w: (round(w[3] / 3), w[0]))
    return " ".join(w[4] for w in inside)


def _table_lines(t, words) -> list:
    """Rows of a PDF table rebuilt from its text lines: the columns come from the table's cells,
    each printed line is a row, and a line holding only words in the name column continues
    the name above (wrapped text, or a table drawn without row lines)."""
    boxes = max((r.cells for r in t.rows[:4]), key=lambda cs: sum(1 for c in cs if c), default=[])
    edges = sorted({round(c[0], 1) for c in boxes if c} | {round(c[2], 1) for c in boxes if c})
    if len(edges) < 3:
        return [[_words_in(words, c) for c in r.cells] for r in t.rows]
    cols = list(zip(edges, edges[1:]))
    x0, y0, x1, y1 = t.bbox
    inside = [w for w in words if x0 - 1 <= (w[0] + w[2]) / 2 <= x1 + 1 and y0 - 1 <= (w[1] + w[3]) / 2 <= y1 + 1]
    inside.sort(key=lambda w: ((w[1] + w[3]) / 2, w[0]))
    lines, cur, cy = [], [], None
    for w in inside:
        y = (w[1] + w[3]) / 2
        if cy is not None and abs(y - cy) > max(2.5, (w[3] - w[1]) * 0.45):
            lines.append(cur)
            cur = []
        cur.append(w)
        cy = y if cy is None or not cur[:-1] else (cy + y) / 2
    if cur:
        lines.append(cur)
    out = []
    for ln in lines:
        cells = [""] * len(cols)
        for w in sorted(ln, key=lambda w: w[0]):
            xm = (w[0] + w[2]) / 2
            k = next((i for i, (a, b) in enumerate(cols) if a - 0.5 <= xm <= b + 0.5), None)
            if k is not None:
                cells[k] = (cells[k] + " " + w[4]).strip()
        out.append(cells)
    return _join_wrapped(out)


def _join_wrapped(rows) -> list:
    """Glue continuation lines: only the widest-text column filled, no number anywhere."""
    if not rows:
        return rows
    n = len(rows[0])
    name_col = max(range(n), key=lambda c: sum(len(r[c]) for r in rows))
    out = []
    for r in rows:
        filled = [c for c in range(n) if r[c]]
        cont = (filled == [name_col] and out and not CODE_RE.match(r[name_col])
                and not any(num(x) is not None for x in r) and out[-1][name_col]
                and _find_header([out[-1]]) < 0)
        if cont:
            out[-1][name_col] += " " + r[name_col]
        else:
            out.append(list(r))
    return out


def read_rows(path) -> list:
    """[(sheet name, rows)] from .xls .xlsx .csv .docx .pdf."""
    ext = Path(path).suffix.lower()
    if ext == ".xls":
        return _rows_xls(path)
    if ext in (".xlsx", ".xlsm"):
        return _rows_xlsx(path)
    if ext in (".csv", ".txt"):
        return _rows_csv(path)
    if ext == ".docx":
        return _rows_docx(path)
    if ext == ".pdf":
        return _rows_pdf(path)
    if ext == ".doc":
        raise ValueError("ไฟล์เอกสารรุ่นเก่า (.doc) — กรุณาบันทึกเป็น .docx ก่อน แล้วนำเข้าอีกครั้ง")
    raise ValueError(f"ยังไม่รองรับไฟล์ชนิด {ext}")


def _norm(s) -> str:
    return re.sub(r"\s+", "", text(s)).lower()


def _find_header(rows) -> int:
    for i, row in enumerate(rows):
        cells = [_norm(c) for c in row]
        has_item = any(c in ("รายการ", "รายการ/รายละเอียด") or c.startswith("รายการ") and len(c) <= 12
                       for c in cells)
        has_unit = any(c == "หน่วย" for c in cells)
        has_qty = any(c.startswith("จำนวน") and "เงิน" not in c or c.startswith("ปริมาณ") for c in cells)
        if has_item and has_unit and has_qty:
            return i
    return -1


def _labels(rows, h) -> list:
    """Column labels from the header row and the one below it (ปร.4 has two)."""
    n = max(len(r) for r in rows[h:h + 3])
    top = [text(c) for c in rows[h]] + [""] * n
    sub = [text(c) for c in rows[h + 1]] + [""] * n if h + 1 < len(rows) else [""] * (2 * n)
    # the second row is a header row only if it has words and no item
    head_words = ("ต่อหน่วย", "จำนวนเงิน", "เป็นเงิน", "ค่าวัสดุ", "ค่าแรง", "ราคา", "factor", "ต้นทุน")
    sub_is_head = any(any(w in _norm(sub[c]) for w in head_words) for c in range(n)) and \
        not any(num(sub[c]) is not None for c in range(n))
    labels, group = [], ""
    for c in range(n):
        if top[c]:
            group = top[c]
        elif not (sub_is_head and sub[c]):
            group = ""
        lab = (top[c] or group)
        if sub_is_head and sub[c]:
            lab = (lab + " " + sub[c]).strip()
        labels.append(_norm(lab))
    return labels, (2 if sub_is_head else 1)


def _map_columns(labels) -> dict:
    col = {}

    def first(pred):
        for i, lab in enumerate(labels):
            if lab and pred(lab):
                return i
        return None

    col["no"] = first(lambda s: s.startswith("ลำดับ") or s == "ที่")
    col["name"] = first(lambda s: s.startswith("รายการ"))
    col["unit"] = first(lambda s: s == "หน่วย" or s.startswith("หน่วย") and "ราคา" not in s and "ต่อ" not in s)
    col["qty"] = first(lambda s: (s.startswith("จำนวน") and "เงิน" not in s) or s.startswith("ปริมาณ"))
    col["mat_unit"] = first(lambda s: "วัสดุ" in s and "ต่อหน่วย" in s and "แรง" not in s)
    col["mat_amt"] = first(lambda s: "วัสดุ" in s and ("จำนวนเงิน" in s or "เป็นเงิน" in s) and "แรง" not in s)
    col["lab_unit"] = first(lambda s: "แรง" in s and "ต่อหน่วย" in s and "วัสดุ" not in s)
    col["lab_amt"] = first(lambda s: "แรง" in s and ("จำนวนเงิน" in s or "เป็นเงิน" in s) and "วัสดุ" not in s)
    col["total"] = first(lambda s: s.startswith("รวม") or "ค่าวัสดุและแรงงาน" in s or "ค่างานต้นทุน" in s)
    col["mid"] = first(lambda s: s.startswith("ราคากลาง") or s.endswith("ราคากลาง"))
    col["amount"] = first(lambda s: s in ("เป็นเงิน", "จำนวนเงิน") or s.startswith("ราคาที่ปรับลด")
                          and "ต่อหน่วย" not in s)
    col["unit_price"] = first(lambda s: s.startswith("ราคาต่อหน่วย"))
    return col


TOTAL_RE = re.compile(r"^(รวม|ยอดรวม|รวมเป็นเงิน|รวมทั้งสิ้น|รวมค่า|วงเงิน|รวม\s*งาน)")


def _cell(row, i):
    return row[i] if i is not None and i < len(row) else None


def parse_rows(rows) -> list:
    """Items from the rows of one table (the header is found by its words)."""
    h = _find_header(rows)
    if h < 0:
        return []
    labels, nhead = _labels(rows, h)
    col = _map_columns(labels)
    if col["name"] is None:
        return []
    items = []
    for row in rows[h + nhead:]:
        name = text(_cell(row, col["name"]))
        if not name:
            continue
        flat = _norm(name)
        if flat in ("รายการ",) or (any(_norm(c) == "หน่วย" for c in row) and flat.startswith("รายการ")):
            continue                                   # header repeated on a new page
        if TOTAL_RE.match(name.strip()) and not CODE_RE.match(name):
            continue                                   # subtotal lines would count twice
        g = lambda k: num(_cell(row, col[k])) or 0.0   # noqa: E731
        qty, mu, ma, lu, la = g("qty"), g("mat_unit"), g("mat_amt"), g("lab_unit"), g("lab_amt")
        if not ma and mu and qty:
            ma = qty * mu
        if not la and lu and qty:
            la = qty * lu
        cost = g("total") or (ma + la) or g("amount") or (qty * g("unit_price"))
        if not cost and g("mid"):
            cost = g("mid")
        code, level = split_code(name)
        it = Item(name=name, unit=text(_cell(row, col["unit"])), qty=qty, mat_unit=mu, mat_amt=ma,
                  lab_unit=lu, lab_amt=la, cost=cost, no=text(_cell(row, col["no"])), code=code, level=level)
        it.header = not qty and not cost
        it.special = "ค่าใช้จ่ายพิเศษ" in name
        it.equip = "ครุภัณฑ์" in name and it.header is False
        items.append(it)
    # levels when the names carry no numbers: a header starts a group
    if items and not any(it.code for it in items):
        for it in items:
            it.level = 1 if it.header else 2
    return items


def _find_factor(rows) -> float:
    for row in rows:
        for i, c in enumerate(row):
            s = _norm(c)
            if s in ("f", "factorf", "factor", "ค่าfactorf") or s.startswith("factorf"):
                for v in row[i + 1:i + 4]:
                    x = num(v)
                    if x and 1.0 < x < 2.0:
                        return x
    return 0.0


INFO_KEYS = (("title", ("ชื่อโครงการ/งานก่อสร้าง", "ชื่อโครงการ", "โครงการ", "กลุ่มงาน/งาน")),
             ("agency", ("หน่วยงานเจ้าของโครงการ/งานก่อสร้าง", "หน่วยงานเจ้าของโครงการ", "หน่วงานเจ้าของโครงการ")),
             ("place", ("สถานที่ก่อสร้าง",)))


def _find_info(rows) -> dict:
    out = {}
    for row in rows[:40]:
        cells = [text(c) for c in row if text(c)]
        for i, s in enumerate(cells):
            for key, words in INFO_KEYS:
                if key in out:
                    continue
                for w in words:
                    if s.startswith(w):
                        rest = s[len(w):].strip(" :")
                        if not rest and i + 1 < len(cells):
                            rest = cells[i + 1]
                        if rest and len(rest) > 3:
                            out[key] = re.sub(r"\s{2,}", " ", rest)
                        break
    return out


def read_bill(path) -> Project:
    """The bill (ปร.4 or a ราคากลาง table) from a file. The sheet with the most items wins."""
    def score(items):
        # a ปร.4 (material and labour columns) beats a sheet that is already a price list
        leaves = [i for i in items if not i.header]
        return len(leaves) + (10_000 if any(i.mat_amt or i.lab_amt for i in leaves) else 0)

    best, best_rows = [], []
    for _name, rows in read_rows(path):
        items = parse_rows(rows)
        if score(items) > score(best):
            best, best_rows = items, rows
    if not best:
        raise ValueError("ไม่พบตารางรายการ — ต้องมีหัวตาราง «รายการ», «หน่วย» และ «จำนวน/ปริมาณ»")
    p = Project(items=best, source=str(path))
    all_rows = [r for _n, rows in read_rows(path) for r in rows] if not best_rows else best_rows
    p.factor = _find_factor(all_rows)
    for k, v in _find_info(all_rows).items():
        setattr(p, k, v)
    _mark_groups(p.items)
    if p.factor:
        p.mid_price = r2(r2(p.cost_total * p.factor) + r2(p.equip_total * VAT_FACTOR) + p.special_items_total)
    return p


def _mark_groups(items) -> None:
    """Lines under a heading named ครุภัณฑ์ / ค่าใช้จ่ายพิเศษ belong to that group."""
    stack = []
    for it in items:
        while stack and stack[-1][0].level >= it.level and it.code:
            stack.pop()
        if it.header:
            stack.append((it, "ครุภัณฑ์" in it.name, "ค่าใช้จ่ายพิเศษ" in it.name))
            continue
        if any(e for _h, e, _s in stack):
            it.equip = True
        if any(s_ for _h, _e, s_ in stack):
            it.special = True


# -- ว651 ---------------------------------------------------------------------------------------

@dataclass
class Reduction:
    mid_net: float = 0.0          # (1) ราคากลางหักค่าใช้จ่ายพิเศษ
    offer_net: float = 0.0        # (2) ราคาเสนอหักค่าใช้จ่ายพิเศษ
    diff: float = 0.0             # (3) = (1) − (2)  «ลดลง»
    pct_down: float = 0.0         # (3) ÷ (1) × 100   «ค่างานลดลง»
    pct_left: float = 100.0       # 100 − ค่างานลดลง   «ค่างานคงเหลือ»
    ratio: float = 1.0            # (2) ÷ (1)


def reduction(mid_price: float, offer: float, special: float = 0.0, uplift: float = 1.0) -> Reduction:
    """The five lines of «การคำนวณร้อยละวัสดุในการจ้าง» (ว651 สิ่งที่ส่งมาด้วย 1).
    `uplift` 1.05 for the three southern border provinces (ราคากลางและค่าใช้จ่ายพิเศษบวกเพิ่มร้อยละ 5)."""
    r = Reduction()
    mid_price, special = r2(mid_price * uplift), r2(special * uplift)
    r.mid_net = r2(mid_price - special)
    r.offer_net = r2(offer - special)
    r.diff = r2(r.mid_net - r.offer_net)
    if r.mid_net > 0:
        r.ratio = r.offer_net / r.mid_net
        r.pct_down = r.diff * 100.0 / r.mid_net
        r.pct_left = 100.0 - r.pct_down
    return r


@dataclass
class Row651:
    item: Item
    cost: float = 0.0
    factor: float = 0.0
    mid: float = 0.0               # ราคากลาง (ก่อนบวกเพิ่ม)
    mid_up: float = 0.0            # ราคากลางบวกเพิ่มร้อยละ 5 (= mid เมื่อไม่ใช่ 3 จังหวัดภาคใต้)
    reduced: float = 0.0
    unit_price: float = 0.0
    adjusted: float = 0.0          # เศษสตางค์ที่ปรับในรายการนี้ (*)


@dataclass
class Result651:
    rows: list
    red: Reduction
    factor: float
    uplift: float
    groups: list                   # ตารางสรุป: [(ชื่อ, ค่างานต้นทุน, factor, ราคากลาง, บวกเพิ่ม, ปรับลด)]
    mid_total: float
    mid_up_total: float
    reduced_total: float
    adjust_row: int = -1           # ดัชนีใน rows ที่รับเศษ
    warnings: list = field(default_factory=list)


def effective_factor(p: Project) -> float:
    """Factor F: the one in the file when it gives the ราคากลาง entered, else the one that does."""
    cost = p.cost_total
    target = p.mid_price - special_total(p) - r2(p.equip_total * VAT_FACTOR)
    if cost <= 0:
        return p.factor or 1.0
    if p.factor and abs(cost * p.factor - target) <= max(1.0, 0.00005 * target):
        return p.factor
    return target / cost if target > 0 else (p.factor or 1.0)


def special_total(p: Project) -> float:
    """ค่าใช้จ่ายพิเศษ: the entered amount, or the special lines of the bill."""
    return p.special if p.special else p.special_items_total


def compute_651(p: Project) -> Result651:
    sp = special_total(p)
    up = p.uplift
    red = reduction(p.mid_price, p.offer, sp, up)
    f = effective_factor(p)
    rows, warn = [], []
    for it in p.items:
        row = Row651(item=it)
        if not it.header:
            row.cost = it.cost
            if it.special:
                row.factor = 1.0
                row.mid = r2(it.cost)
                row.mid_up = r2(row.mid * up)
                row.reduced = row.mid_up                    # ค่าใช้จ่ายพิเศษไม่ปรับลด
            else:
                row.factor = VAT_FACTOR if it.equip else f
                row.mid = it.cost * row.factor              # not rounded: the total is ค่างานต้นทุน × F
                row.mid_up = row.mid * up
                row.reduced = r2(row.mid_up * red.ratio)
        rows.append(row)
    if p.special and not p.special_items_total:
        it = Item(name="ค่าใช้จ่ายพิเศษตามข้อกำหนด", unit="งาน", qty=1, cost=p.special, special=True,
                  code="", level=1)
        rows.append(Row651(item=it, cost=p.special, factor=1.0, mid=r2(p.special),
                           mid_up=r2(p.special * up), reduced=r2(p.special * up)))
    # (*) ส่วนต่างให้ปรับในรายการใดรายการหนึ่ง ยกเว้นค่าใช้จ่ายพิเศษ: the largest line takes the satang
    target = r2(p.offer)
    got = r2(sum(r.reduced for r in rows))
    adj = -1
    if p.offer > 0 and abs(target - got) >= 0.005:
        cands = [i for i, r in enumerate(rows) if not r.item.header and not r.item.special]
        if cands:
            adj = max(cands, key=lambda i: rows[i].reduced)
            rows[adj].adjusted = r2(target - got)
            rows[adj].reduced = r2(rows[adj].reduced + rows[adj].adjusted)
            if abs(rows[adj].adjusted) > 1.0:
                warn.append(f"ส่วนต่าง {rows[adj].adjusted:,.2f} บาท มากกว่า 1 บาท — "
                            "ตรวจราคากลาง/Factor F ให้ตรงกับรายการ")
    for r in rows:
        if not r.item.header and r.item.qty:
            r.unit_price = r2(r.reduced / r.item.qty)
    mid_total = sum(r.mid for r in rows)
    groups = []
    for name, pick, fac in (("งานก่อสร้าง", lambda it: not it.equip and not it.special, f),
                            ("งานครุภัณฑ์จัดซื้อ", lambda it: it.equip and not it.special, VAT_FACTOR),
                            ("ค่าใช้จ่ายพิเศษตามข้อกำหนด", lambda it: it.special, 1.0)):
        sel = [r for r in rows if not r.item.header and pick(r.item)]
        groups.append((name, sum(r.cost for r in sel), fac, r2(sum(r.mid for r in sel)),
                       r2(sum(r.mid_up for r in sel)), r2(sum(r.reduced for r in sel))))
    mid_total = sum(r.mid for r in rows)
    mid_total = r2(mid_total)
    if p.mid_price and abs(mid_total - r2(p.mid_price)) > 1.0:
        warn.append(f"ราคากลางรวมรายการ {mid_total:,.2f} ไม่เท่ากับราคากลางที่กรอก {p.mid_price:,.2f}")
    if p.offer > p.mid_price > 0:
        warn.append("ราคาเสนอสูงกว่าราคากลาง — ดู ว651 ข้อ 1.2.4 (ต่อรองราคา หรือยกเลิกถ้าสูงกว่าวงเงิน)")
    if p.budget and p.offer > p.budget:
        warn.append("ราคาเสนอสูงกว่าวงเงินงบประมาณ — ว651 ข้อ (2.3) ให้ยกเลิกการจัดซื้อจัดจ้าง")
    return Result651(rows=rows, red=red, factor=f, uplift=up, groups=groups, mid_total=mid_total,
                     mid_up_total=r2(r2(mid_total) * up),
                     reduced_total=r2(sum(r.reduced for r in rows)), adjust_row=adj, warnings=warn)


def subtotals(rows, key) -> dict:
    """Header row index → sum of `key` over the lines under it (by the 1.2.3 numbering)."""
    out = {}
    for i, r in enumerate(rows):
        if not r.item.header:
            continue
        lvl, s = r.item.level, 0.0
        for r2_ in rows[i + 1:]:
            if r2_.item.header and r2_.item.level <= lvl:
                break
            if not r2_.item.header:
                s += getattr(r2_, key)
        out[i] = s
    return out


# -- ว124 -----------------------------------------------------------------------------------------

def month_days(months: int, days: int) -> list:
    """Days in each month of the plan: 30 each, the last takes what is left."""
    months = max(1, int(months or 1))
    days = int(days or 30 * months)
    base = [30] * months
    base[-1] = max(1, days - 30 * (months - 1))
    return base


# ว124: ลำดับงานก่อสร้าง — ช่วงเวลาของแต่ละหมวดเป็นสัดส่วนของระยะเวลาทั้งสัญญา (เริ่ม, สิ้นสุด)
PHASES = (
    ("prep", "งานเตรียมการ", (0.0, 0.10),
     ("วางผัง", "สำรวจ", "ปรับพื้นที่", "รื้อ", "ถางป่า", "ขุดตอ", "เตรียมพื้นที่", "ป้ายโครงการ", "บ้านพักคนงาน",
      "สำนักงานสนาม", "ที่พักคนงาน")),
    ("found", "งานดินและฐานราก", (0.0, 0.30),
     ("ขุดดิน", "ฐานราก", "เสาเข็ม", "ตอม่อ", "ทรายรอง", "ทรายหยาบ", "คอนกรีตหยาบ", "ถมดิน", "ดินถม", "บดอัด",
      "ถมทราย", "คานคอดิน", "งานดิน")),
    ("struct", "งานโครงสร้าง", (0.10, 0.55),
     ("เสา", "คาน", "พื้น", "บันได", "โครงสร้าง", "คสล", "ค.ส.ล", "กันสาด", "แผ่นพื้น")),
    ("roof", "งานหลังคา", (0.35, 0.65),
     ("หลังคา", "จันทัน", "แป", "อะเส", "ครอบ", "เมทัลชีท", "รางน้ำ", "เชิงชาย", "ปั้นลม", "truss", "ทรัส")),
    ("wall", "งานผนัง", (0.35, 0.65), ("ก่อ", "อิฐ", "บล็อก", "ผนัง", "เอ็น", "ทับหลัง")),
    ("mep", "งานระบบ", (0.40, 0.90),
     ("ไฟฟ้า", "สายไฟ", "ปลั๊ก", "สวิตช์", "โคม", "หลอด", "ประปา", "สุขาภิบาล", "ท่อ", "pvc", "ระบบ", "มิเตอร์",
      "ปั๊ม", "ถังบำบัด", "บ่อเกรอะ", "บ่อซึม", "พัดลม", "ปรับอากาศ", "ดับเพลิง")),
    ("finish", "งานตกแต่ง", (0.55, 0.92),
     ("ฉาบ", "ฝ้า", "กระเบื้อง", "ปู", "ทาสี", "สี", "บัว", "ขัดมัน", "หินขัด", "แกรนิต", "ลามิเนต", "ยาแนว", "กันซึม")),
    ("door", "งานประตูหน้าต่างและสุขภัณฑ์", (0.70, 0.96),
     ("ประตู", "หน้าต่าง", "บานกระทุ้ง", "บานเลื่อน", "วงกบ", "ช่องแสง", "มุ้งลวด", "เหล็กดัด", "สุขภัณฑ์",
      "โถส้วม", "อ่างล้าง", "ก๊อก", "กระจก")),
)
EXTERNAL = ("ext", "งานภายนอก", (0.50, 0.96),
            ("รั้ว", "ถนน", "ลาน", "ทางเดิน", "รางระบาย", "ระบายน้ำ", "บ่อพัก", "คูระบาย", "ท่อระบาย", "ปลูก",
             "สนาม", "ไม้ประดับ", "ที่จอด", "เขื่อนกันดิน"))
HANDOVER = ("handover", "ป้าย ครุภัณฑ์ และส่งมอบงาน (เดือนสุดท้าย)", (1.0, 1.0),
            ("ป้าย", "ครุภัณฑ์", "ทำความสะอาด", "ส่งมอบ", "เก็บกวาด", "เฟอร์นิเจอร์", "โต๊ะ", "เก้าอี้",
             "ตู้เก็บเอกสาร", "อุปกรณ์สำนักงาน"))

# งานทาง สะพาน ท่อเหลี่ยม และชลประทาน: ลำดับก่อน–หลัง (คำที่เจาะจงกว่าอยู่ก่อน — ตัวแรกที่ตรงชนะ)
ROAD_PHASES = (
    ("r_prep", "งานเตรียมการ", (0.0, 0.08),
     ("ถางป่า", "ขุดตอ", "รื้อถอน", "รื้อย้าย", "เตรียมพื้นที่", "วางผัง", "สำรวจ", "clearing", "grubbing")),
    ("r_pile", "งานเสาเข็ม", (0.05, 0.25),
     ("เสาเข็ม", "สกัดหัวเข็ม", "pile")),
    ("r_sub", "งานโครงสร้างส่วนล่าง", (0.15, 0.45),
     ("ตอม่อ", "คานรัดหัว", "กำแพงกันดิน", "หูช้าง", "abutment", "pier", "ฐานราก")),
    ("r_super", "งานโครงสร้างส่วนบน", (0.35, 0.70),
     ("plankgirder", "girder", "คานสะพาน", "คานอัดแรง", "วางคาน", "ยางรอง", "พื้นสะพาน", "topping", "ทับหน้า",
      "แผ่นพื้นสำเร็จ")),
    ("r_rail", "งานราวสะพาน รอยต่อ และแผ่นพื้นต่อเชิงลาด", (0.60, 0.90),
     ("รอยต่อ", "expansion", "ราวสะพาน", "ราวกันตก", "approach", "เชิงลาด", "ท่อระบายน้ำสำเร็จ", "สะพาน")),
    ("r_earth", "งานดินและคันทาง", (0.05, 0.40),
     ("ตัดคันทาง", "ตัดดิน", "ขุดดิน", "ขุดลอก", "ถมคันทาง", "คันทาง", "วัสดุคัดเลือก", "หินผุ", "ดินถม", "ถมดิน",
      "บดอัด", "excavation", "embankment", "earthwork", "งานดิน")),
    ("r_drain", "งานระบายน้ำ ท่อ และดาดคอนกรีต", (0.15, 0.60),
     ("ท่อเหลี่ยม", "ท่อลอด", "ท่อ", "คูระบาย", "รางระบาย", "รางวี", "บ่อพัก", "ระบายน้ำ", "ดาด", "หินเรียง",
      "หินทิ้ง", "ฝาย", "ประตูระบายน้ำ", "อาคารบังคับน้ำ", "culvert", "drain")),
    ("r_subbase", "งานรองพื้นทาง", (0.30, 0.60),
     ("รองพื้นทาง", "subbase", "ลูกรัง", "รื้อชั้น", "ปรับปรุงชั้นทาง")),
    ("r_base", "งานพื้นทาง", (0.45, 0.75), ("พื้นทาง", "หินคลุก", "base")),
    ("r_surface", "งานผิวทาง", (0.65, 0.92),
     ("ไพรม์", "แทค", "prime", "tack", "แอสฟัลต์", "แอสฟัลท์", "asphalt", "ลาดยาง", "ผิวทาง", "ผิวจราจร",
      "ถนนคอนกรีต", "surface", "ไหล่ทาง", "ทางเท้า")),
    ("r_mark", "งานเครื่องหมายจราจรและอุปกรณ์ความปลอดภัย", (0.85, 1.0),
     ("ตีเส้น", "เครื่องหมายจราจร", "หลักนำทาง", "หลักกิโล", "การ์ดเรล", "guardrail", "แผ่นสะท้อน", "หมุดสะท้อน",
      "ราวเหล็ก", "สีจราจร")),
)
ROAD_TYPES = ("road", "irrigation")


def _words(s: str) -> str:
    # «ก่อสร้าง» is not masonry; «ป้ายโครงการ» is a site sign put up first
    return _norm(s).replace("ก่อสร้าง", "").replace("ป้ายโครงการ", "เตรียมพื้นที่")


def _match(s: str, phase) -> bool:
    return any(w in s for w in phase[3])


def phase_of(path: list, road: bool = False):
    """(override phase or None, phase) for a line; `path` = its name then its headings, nearest
    first. In a building bill a heading wins over the line's own words (คอนกรีต under «ฐานราก» is
    foundation); in a road / bridge / irrigation bill the line's own words are the surer guide.
    The other kind's phases are tried after the ones of the bill's kind."""
    words = [_words(x) for x in path]
    order = words if road else words[1:] + words[:1]
    tables = (ROAD_PHASES, PHASES) if road else (PHASES, ROAD_PHASES)
    override = None
    for w in order:
        if not road and _match(w, EXTERNAL):
            override = EXTERNAL
            break
        if _match(w, HANDOVER):
            override = HANDOVER
            break
    base = None
    for table in tables:
        for w in order:
            base = next((ph for ph in table if _match(w, ph)), None)
            if base:
                break
        if base:
            break
    return override, base


def plan_phases(p: Project) -> list:
    """[(item, override, phase)] for the lines of the bill (a line nobody can place follows the one before)."""
    road = p.work_type in ROAD_TYPES
    out, stack, last = [], [], (None, (ROAD_PHASES[5] if road else PHASES[2]))
    for it in p.items:
        while stack and it.code and stack[-1].code and stack[-1].level >= it.level:
            stack.pop()
        if it.header:
            stack.append(it)
            continue
        path = [it.name] + [h.name for h in reversed(stack)]
        ov, base = phase_of(path, road)
        if base is None and ov is None:
            ov, base = last
        base = base or last[1]
        last = (ov, base)
        out.append((it, ov, base))
    return out


def _spread(lo: float, hi: float, months: int) -> list:
    """Per cent of a line in each month for the window [lo, hi] (in months)."""
    plan = [0.0] * months
    lo, hi = max(0.0, min(lo, months)), max(0.0, min(hi, months))
    if hi - lo < 1e-9:
        plan[min(months - 1, int(lo))] = 100.0
    else:
        for m in range(int(lo), min(months, int(math.ceil(hi - 1e-9)))):
            ov = min(hi, m + 1) - max(lo, m)
            if ov > 0:
                plan[m] = ov / (hi - lo) * 100.0
    plan = [round(x, 2) for x in plan]
    k = max(range(months), key=lambda m: plan[m])
    plan[k] = round(plan[k] + 100.0 - sum(plan), 2)            # each line sums to exactly 100
    return plan


def _s_time(c: float) -> float:
    """Time (0–1) when a share `c` of the work is done on a gentle S-curve: slower at the start
    and at the end, faster in the middle (S(x) = ½x + ½(3x² − 2x³))."""
    lo, hi = 0.0, 1.0
    for _ in range(40):
        x = (lo + hi) / 2
        if 0.5 * x + 0.5 * (3 * x * x - 2 * x ** 3) < c:
            lo = x
        else:
            hi = x
    return (lo + hi) / 2


def auto_plan(p: Project, months: int) -> None:
    """แผนการทำงาน: every line in the order of construction, and work — so money — in every month.

    The lines are sorted by their phase (building: preparation, earthwork and foundations,
    structure, roof and walls, services, finishes, doors/windows and sanitary ware, external works;
    road/bridge/irrigation: preparation, earthwork, piles, substructure, drainage, subbase,
    superstructure, base, surface, railings, markings), then laid one after another along the
    whole contract time by their value, on an S-curve. Each line lasts at least a sixth of the
    contract (a month or more) so neighbouring work overlaps as on site. Signs, equipment
    (ครุภัณฑ์) and handing over fall in the last month; ค่าใช้จ่ายพิเศษ runs evenly through every
    month. The owner edits the per-cent afterwards."""
    months = max(1, int(months))
    res = compute_651(p)
    value = {id(r.item): r.reduced for r in res.rows}
    phases = plan_phases(p)
    work, order = [], {id(it): k for k, it in enumerate(p.items)}
    for it, ov, base in phases:
        if it.special:                    # ค่าใช้จ่ายพิเศษ: through the whole contract
            it.plan = _spread(0.0, float(months), months)
        elif ov is HANDOVER and months > 1:
            it.plan = [0.0] * (months - 1) + [100.0]
        else:
            a, b = (EXTERNAL[2] if ov is EXTERNAL else base[2])
            work.append(((a + b) / 2, order[id(it)], it))
    work.sort(key=lambda w: (w[0], w[1]))
    vals = [max(0.0, value.get(id(it), 0.0)) for _r, _o, it in work]
    total = sum(vals)
    if total <= 0:
        vals, total = [1.0] * len(vals), float(len(vals) or 1)
    dmin = min(float(months), max(1.0, months / 6.0))
    acc = 0.0
    for (_r, _o, it), v in zip(work, vals):
        c0, c1 = acc / total, (acc + v) / total
        acc += v
        lo, hi = _s_time(c0) * months, _s_time(c1) * months
        if hi - lo < dmin:
            mid = (lo + hi) / 2
            lo = min(max(0.0, mid - dmin / 2), months - dmin)
            hi = lo + dmin
        it.plan = _spread(lo, hi, months)
    p.months = months
    if not p.days:
        p.days = 30 * months


@dataclass
class Plan124:
    months: int
    days: list
    lines: list                    # [(item, amount, pct of project, [pct per month])]
    money: list
    acc_money: list
    pct_plan: list
    acc_plan: list
    total: float
    bad_lines: list                # lines whose months do not add to 100
    checks: list                   # [(text, month index, planned acc %, required %)]
    actual: list = field(default_factory=list)       # % ACTUAL per month (None = not yet)
    acc_actual: list = field(default_factory=list)
    diff: list = field(default_factory=list)         # % ACC ACTUAL − % ACC PLAN
    labels: list = field(default_factory=list)       # calendar month of each plan month
    forecast: list = field(default_factory=list)     # % ACC ACTUAL as entered, then on to 100 % by the plan
    last_actual: int = -1                            # index of the last month with an actual


def compute_124(p: Project) -> Plan124:
    months = max(1, int(p.months or 1))
    res = compute_651(p)
    lines, bad = [], []
    total = sum(r.reduced for r in res.rows if not r.item.header) or 0.0
    for r in res.rows:
        if r.item.header:
            continue
        plan = list(r.item.plan or [])[:months] + [0.0] * max(0, months - len(r.item.plan or []))
        if abs(sum(plan) - 100.0) > 0.05:
            bad.append(r.item)
        lines.append((r.item, r.reduced, r.reduced * 100.0 / total if total else 0.0, plan))
    money = [sum(a * pl[m] / 100.0 for _i, a, _p, pl in lines) for m in range(months)]
    acc, s = [], 0.0
    for m in money:
        s += m
        acc.append(s)
    pct = [m * 100.0 / total if total else 0.0 for m in money]
    accp = [a * 100.0 / total if total else 0.0 for a in acc]
    days = month_days(months, p.days)
    checks = []
    cum = [sum(days[:i + 1]) for i in range(months)]
    tot_days = cum[-1]
    for frac, need, words in CHECKPOINTS:
        day = frac * tot_days
        k = next((i for i, c in enumerate(cum) if c >= day - 1e-9), months - 1)
        checks.append((words, k, accp[k], need))
    act = [(p.actual[m] if m < len(p.actual) else None) for m in range(months)]
    acc_act, diff, s_ = [], [], 0.0
    for m, v in enumerate(act):
        if v is None:
            acc_act.append(None)
            diff.append(None)
        else:
            s_ += v
            acc_act.append(s_)
            diff.append(s_ - accp[m])
    # the second line of the chart: the work done so far, then the rest finished as planned
    last = max((m for m, v in enumerate(act) if v is not None), default=-1)
    fc = list(accp)
    if last >= 0:
        done, planned = acc_act[last], accp[last]
        left, plan_left = 100.0 - done, 100.0 - planned
        run = done
        fc = [acc_act[m] if acc_act[m] is not None else None for m in range(last + 1)]
        rest = months - last - 1
        for m in range(last + 1, months):
            share = pct[m] / plan_left if plan_left > 1e-9 else 1.0 / rest
            run += left * share
            fc.append(run)
        for m in range(last + 1):                   # a month left blank inside the entered ones
            if fc[m] is None:
                fc[m] = fc[m - 1] if m else 0.0
    return Plan124(months=months, days=days, lines=lines, money=money, acc_money=acc, pct_plan=pct,
                   acc_plan=accp, total=total, bad_lines=bad, checks=checks, actual=act, acc_actual=acc_act,
                   diff=diff, labels=month_labels(p.start, months), forecast=fc, last_actual=last)


# -- ว78 ------------------------------------------------------------------------------------------

STEEL_WORDS = ("เหล็ก", "ลวดผูก", "wiremesh", "wiremash", "สแตนเลส", "stainless", "plate", "โบลท์", "โบล์ท",
               "bolt", "สลักเกลียว", "rb", "db", "sr24", "sd40", "sd30", "wf", "ท่อเหล็ก", "kg/m")
NOT_STEEL_WORDS = ("ทาสี", "ค่าแรง", "สีกันสนิม", "สีน้ำมัน", "เคลือบสังกะสีด้านหน้า", "ติดสติ๊กเกอร์", "ตาข่าย",
                   "ป้ายชื่อ", "ประตู", "หน้าต่าง", "ข้อต่อ")
MESH_RE = re.compile(r"(?:Ø|ø|ศก\.?|dia\.?)\s*(\d+(?:\.\d+)?)\s*(?:มม|mm)\.?\s*@\s*(\d+(?:\.\d+)?)\s*(ม|m|ซม|cm)",
                     re.I)
REBAR_RE = re.compile(r"\b(?:RB|DB)\s*\.?\s*(\d{1,2})\b", re.I)
KG_M_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(?:kg|กก\.?)\s*/\s*(?:m|ม)\b\.?", re.I)
KG_PIECE_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(?:kg|กก\.?)\s*/\s*(?:ผ|แผ่น|ตัว|ชิ้น|ท่อน|อัน)", re.I)
LENGTH_RE = re.compile(r"ยาว\s*(\d+(?:\.\d+)?)\s*(?:ม\.|เมตร|m\b)", re.I)
PLATE_RE = re.compile(r"(\d+(?:\.\d+)?)\s*[xX×]\s*(\d+(?:\.\d+)?)\s*[xX×]\s*(\d+(?:\.\d+)?)\s*(?:มม|mm)", re.I)
BOLT_RE = re.compile(r"(?:ศก\.?|Ø|ø|dia\.?)\s*(\d+(?:\.\d+)?)\s*[xX×]\s*(\d+(?:\.\d+)?)\s*(?:มม|mm)", re.I)


def steel_guess(it: Item) -> bool:
    if it.header or it.special:
        return False
    s = _norm(it.name)
    if any(w in s for w in NOT_STEEL_WORDS):
        return False
    return any(w in s for w in STEEL_WORDS) or bool(REBAR_RE.search(it.name))


def kg_per_unit(it: Item):
    """Kilograms in one unit of the line, or None when the name does not say."""
    if it.kg_per_unit:
        return it.kg_per_unit
    u = _norm(it.unit)
    if u in ("กก.", "กก", "kg", "กิโลกรัม"):
        return 1.0
    if u in ("ตัน", "ton", "t"):
        return 1000.0
    name = it.name
    m = KG_PIECE_RE.search(name)
    if m:
        return float(m.group(1))
    m = KG_M_RE.search(name)
    if m:
        per_m = float(m.group(1))
        if u in ("ม.", "ม", "เมตร", "m"):
            return per_m
        if u in ("ท่อน", "เส้น"):
            lm = LENGTH_RE.search(name)
            return per_m * (float(lm.group(1)) if lm else DEFAULT_BAR_LENGTH)
    if u in ("ตร.ม.", "ตร.ม", "ตารางเมตร", "m2") and ("mesh" in name.lower() or "mash" in name.lower()
                                                     or "ตะแกรง" in name):
        m = MESH_RE.search(name)
        if m:                                  # two layers of wire each way: 2 × (1/s) m of wire per m²
            d = float(m.group(1)) / 1000.0
            sp = float(m.group(2)) / (100.0 if m.group(3).lower() in ("ซม", "cm") else 1.0)
            return 2.0 / sp * math.pi * d * d / 4.0 * STEEL_DENSITY
    if u in ("แผ่น", "เเผ่น", "ชิ้น"):
        m = PLATE_RE.search(name)
        if m:
            a, b, t = (float(x) / 1000.0 for x in m.groups())
            return a * b * t * STEEL_DENSITY
    if u in ("ตัว", "ชุด", "อัน"):
        m = BOLT_RE.search(name)
        if m:
            d, L = float(m.group(1)) / 1000.0, float(m.group(2)) / 1000.0
            return math.pi * d * d / 4.0 * L * STEEL_DENSITY
    return None


@dataclass
class Plan78:
    materials: list                # [(item, amount, domestic %)]  ภาคผนวก 1
    mat_total: float
    mat_domestic: float
    mat_pct: float
    steel: list                    # [(item, tonnes or None, domestic %)]  ภาคผนวก 2
    steel_t: float
    steel_dom_t: float
    steel_pct: float
    steel_value: float
    missing_weight: list           # steel lines with no weight
    exempt: str                    # why no plan is needed, or ""

    @property
    def mat_ok(self) -> bool:
        return self.mat_pct >= DOMESTIC_MIN - 1e-9

    @property
    def steel_ok(self) -> bool:
        return not self.steel or self.steel_pct >= STEEL_MIN - 1e-9


def compute_78(p: Project) -> Plan78:
    res = compute_651(p)
    mats, steel, missing = [], [], []
    for r in res.rows:
        it = r.item
        if it.header or it.special:
            continue
        if it.is_steel:
            k = kg_per_unit(it)
            t = it.qty * k / 1000.0 if k is not None else None
            if t is None:
                missing.append(it)
            steel.append((it, t, it.domestic, r.reduced))
        else:
            mats.append((it, r.reduced, it.domestic))
    mt = sum(a for _i, a, _d in mats)
    md = sum(a * d / 100.0 for _i, a, d in mats)
    st = sum(t for _i, t, _d, _v in steel if t)
    sd = sum(t * d / 100.0 for _i, t, d, _v in steel if t)
    exempt = ""
    if p.days and p.days <= EXEMPT_DAYS:
        exempt = f"สัญญามีระยะเวลา {p.days} วัน (ไม่เกิน {EXEMPT_DAYS} วัน) — ไม่ต้องจัดทำแผนตาม ว78"
    elif p.offer and p.offer <= EXEMPT_AMOUNT:
        exempt = f"วงเงินจ้าง {p.offer:,.2f} บาท (ไม่เกิน 500,000 บาท) — ไม่ต้องจัดทำแผนตาม ว78"
    return Plan78(materials=[(i, a, d) for i, a, d in mats], mat_total=mt, mat_domestic=md,
                  mat_pct=md * 100.0 / mt if mt else 0.0,
                  steel=[(i, t, d) for i, t, d, _v in steel], steel_t=st, steel_dom_t=sd,
                  steel_pct=sd * 100.0 / st if st else 0.0,
                  steel_value=sum(v for _i, _t, _d, v in steel), missing_weight=missing, exempt=exempt)
