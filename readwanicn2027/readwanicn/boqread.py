# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2569 (2026) นายเวนิช ธัมมะวงษ์ วิศวกรสำรวจ — ReadWanicn2027
"""«ถอดแบบตาม BOQ»: read a set of construction drawings (PDF) and write the bill of
quantities as CSV in the Comptroller General's form (หลักเกณฑ์ราคากลางงานก่อสร้าง 2569,
แบบ ปร.1 แบบแสดงรายการ ปริมาณงาน และราคา ค่างานต้นทุน), one file per kind of work
(อาคาร · ทาง · ชลประทาน · อื่น ๆ), with a page-by-page report of what could not be read.

What is read, honestly:
- a bill of quantities printed in the set (ปร.4 / ปร.5 / ปร.1 tables), with real text or the
  old Thai font encodings (AngsanaUPC/DSN style, decoded here) — every line, as printed;
- each drawing sheet's number and title (from its text, or by OCR of the title block when the
  text is drawn as lines or the page is a scan), its discipline and kind of work;
- on sheets that carry real text: the tags (ป1 น1 D1 W1 F1 C1 B1 GB1 พ1 ผ1 ฝ1 …) are counted.
What is not: lengths, areas and volumes measured off a drawing, or tags inside symbols on a
scan — those sheets are listed for the user to measure with the take-off tools."""
from __future__ import annotations

import csv
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

THAI_DIGITS = str.maketrans("๐๑๒๓๔๕๖๗๘๙", "0123456789")

# -- old Thai font encodings -------------------------------------------------------------------

#: glyphs of the legacy Thai fonts (Latin-1/Latin Extended-A code points), besides the common
#: shift of +0xD2B that maps ก…ฺ onto U+00D6…U+010F
LEGACY = {"đ": "เ", "Ē": "แ", "ē": "โ", "Ĕ": "ใ", "ĕ": "ไ", "ė": "ๆ", "Ę": "็", "ę": "่", "Ě": "้", "ě": "๊",
          "Ĝ": "๋", "ĝ": "์", "Ğ": "ํ", "Š": "่", "š": "้", "Ŝ": "้", "Ť": "์", "Ŧ": "ั", "ŗ": "ั", "Ţ": "๋",
          "Ũ": "็", "ŉ": "่", "Ø": "Ø", "\u05ce": "Ø"}


THAI = "\u0e00-\u0e7f"
_MARK_AA = re.compile(f"(?<=[{THAI}])\\?(?=า)")
_MARK = re.compile(f"(?<=[{THAI}])\\?(?=[{THAI}])")


def fix_marks(s: str) -> str:
    """A Thai tone mark drawn as one glyph with the vowel (ไม้โท on top of a vowel, ้ํ of น้ำ) has no
    text in some PDFs and comes out as «?»: แปลนพื?นชั?น → แปลนพื้นชั้น, ห้องน?า → ห้องน้ำ."""
    if "?" not in s:
        return s
    return _MARK.sub("\u0e49", _MARK_AA.sub("\u0e49\u0e4d", s)).replace("\u0e4d\u0e32", "\u0e33")


def looks_legacy(text: str) -> bool:
    letters = [c for c in text if not c.isspace() and not c.isdigit()]
    if len(letters) < 20:
        return False
    odd = sum(1 for c in letters if 0xD6 <= ord(c) <= 0x168)
    thai = sum(1 for c in letters if 0xE00 <= ord(c) <= 0xE7F)
    return odd > 0.3 * len(letters) and odd > thai


def decode_legacy(s: str) -> str:
    out = []
    for ch in s:
        o = ord(ch)
        if ch in LEGACY:
            out.append(LEGACY[ch])
        elif 0xD6 <= o <= 0x110 and 0xE00 <= o + 0xD2B <= 0xE3A:
            out.append(chr(o + 0xD2B))
        else:
            out.append(ch)
    return "".join(out).replace("ํา", "ำ").replace("ํ่า", "่ำ").replace("ํ้า", "้ำ")


# -- pages -----------------------------------------------------------------------------------------

DISCIPLINES = (("SN", "สุขาภิบาล"), ("EE", "ไฟฟ้า"), ("ME", "เครื่องกล"), ("AC", "ปรับอากาศ"),
               ("A", "สถาปัตยกรรม"), ("S", "โครงสร้าง"), ("E", "ไฟฟ้า"), ("M", "เครื่องกล"),
               ("P", "สุขาภิบาล"), ("C", "โยธา"), ("R", "งานทาง"), ("L", "ภูมิสถาปัตย์"))
WORKS = ("อาคาร", "ทาง", "ชลประทาน", "อื่น ๆ")
ROAD_WORDS = ("ถนน", "ทาง", "ผิวจราจร", "ไหล่ทาง", "ช่องจราจร", "สะพาน", "ท่อเหลี่ยม", "ท่อลอด", "ทางเท้า",
              "ลาดยาง", "แอสฟัลท์", "แอสฟัลต์", "หินคลุก", "รองพื้นทาง", "กม.", "สายทาง")
WATER_WORDS = ("ชลประทาน", "ฝาย", "คลอง", "อ่างเก็บน้ำ", "ประตูระบายน้ำ", "ท่อส่งน้ำ", "คันกั้นน้ำ", "สระ",
               "ขุดลอก", "หินทิ้ง", "หินเรียง", "ทำนบ")
BUILDING_WORDS = ("อาคาร", "บ้าน", "ตึก", "แปลนพื้น", "รูปด้าน", "หลังคา", "ห้องน้ำ", "ประตู", "หน้าต่าง",
                  "ศูนย์", "โรงเรียน", "ที่พัก", "สำนักงาน")
TITLE_WORDS = ("แปลน", "รูปด้าน", "รูปตัด", "แบบขยาย", "ผัง", "รายการ", "ตาราง", "ขยาย", "แบบ", "หมวด", "สารบัญ",
               "ระบบ", "ไดอะแกรม", "ผังบริเวณ", "ฐานราก", "โครงหลังคา", "คาน", "เสา", "พื้น")
SHEET_RE = re.compile(r"\b(SN|EE|ME|AC|[ASEMPCRL])\s?[-–]\s?(\d{1,3}[A-Z]?)\b")
TAG_RE = re.compile(r"^(?:[ปนพผฝ]\d{1,2}|(?:D|W|DW|F|C|B|GB|RB|ST|SL|S|P|BF|SF)\d{1,2}[A-Z]?)$")


@dataclass
class Page:
    no: int                       # 1-based
    kind: str = ""                # ตาราง BOQ · แบบ (มีข้อความ) · แบบ (ข้อความเป็นเส้น) · ภาพสแกน · ข้อความ · ว่าง
    sheet: str = ""               # A-04
    title: str = ""               # แปลนพื้นชั้น 1
    discipline: str = ""
    work: str = ""
    status: str = ""              # อ่านได้ · อ่านได้บางส่วน · อ่านไม่ได้
    note: str = ""
    items: int = 0
    tags: dict = field(default_factory=dict)


@dataclass
class Line:
    work: str
    bill: str                     # the bill's own title (one set can hold several bills)
    group: str                    # หมวดงาน…
    section: str                  # 2.1 งานหลังคา
    name: str
    qty: float | None
    unit: str
    mat_u: float | None = None
    mat: float | None = None
    lab_u: float | None = None
    lab: float | None = None
    total: float | None = None
    note: str = ""
    page: int = 0
    sure: bool = True             # False: the row was put together from pieces — check it


@dataclass
class Result:
    path: str
    pages: list
    lines: list
    tags: dict                    # tag → {page: count}
    project: str = ""
    ocr: bool = False

    def by_work(self) -> dict:
        out = defaultdict(list)
        for ln in self.lines:
            out[ln.work or "อื่น ๆ"].append(ln)
        return dict(out)

    def summary(self) -> dict:
        c = Counter(p.status for p in self.pages)
        return {"ทั้งหมด": len(self.pages), **{k: c.get(k, 0) for k in ("อ่านได้", "อ่านได้บางส่วน", "อ่านไม่ได้")}}


def _num(s):
    s = str(s).translate(THAI_DIGITS).replace(",", "").strip()
    if not re.fullmatch(r"-?\d+(?:\.\d+)?", s):
        return None
    return float(s)


def _work_of(text: str, default: str = "") -> str:
    """Kind of work from the words on a page: a road or irrigation sheet names several of its own
    things; one stray word (ทาง, สระ) is not enough."""
    t = text or ""
    water = sum(1 for w in WATER_WORDS if w in t)
    road = sum(1 for w in ROAD_WORDS if w in t)
    building = sum(1 for w in BUILDING_WORDS if w in t)
    if water >= 2 and water > building:
        return "ชลประทาน"
    if road >= 3 and road > building:
        return "ทาง"
    if building:
        return "อาคาร"
    return default


def _discipline(sheet: str) -> str:
    m = SHEET_RE.search(sheet or "")
    if not m:
        return ""
    return dict(DISCIPLINES).get(m.group(1), "")


# -- text lines in reading orientation ------------------------------------------------------------

def _lines(page, legacy: bool):
    """[(y, x, w, text)] with x/y turned so every line reads left to right, top to bottom."""
    out = []
    for b in page.get_text("dict")["blocks"]:
        for ln in b.get("lines", []):
            t = "".join(s["text"] for s in ln["spans"])
            if legacy:
                t = decode_legacy(t)
            t = " ".join(fix_marks(t).split())
            if not t:
                continue
            x0, y0, x1, y1 = ln["bbox"]
            cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
            dx, dy = ln["dir"]
            if abs(dx) >= abs(dy):
                x, y, w = (cx, cy, x1 - x0) if dx > 0 else (-cx, -cy, x1 - x0)
            else:
                x, y, w = (cy, -cx, y1 - y0) if dy > 0 else (-cy, cx, y1 - y0)
            out.append((y, x, w, t))
    return out


HEADER_KEYS = {"no": ("ลำดับ",), "name": ("รายการ",), "qty": ("จำนวน", "ปริมาณ"), "unit": ("หน่วย",),
               "note": ("หมายเหตุ",)}


def _tables(lines):
    """Each bill table on the page: (header y, columns {key: x}, x-range)."""
    heads = [ln for ln in lines if ln[3] in ("รายการ",)]
    tables = []
    for hy, hx, _w, _t in heads:
        band = [ln for ln in lines if abs(ln[0] - hy) < 30]
        cols = {}
        for y, x, w, t in band:
            for key, words in HEADER_KEYS.items():
                if key not in cols and any(t.startswith(wd) for wd in words) and len(t) <= 12:
                    if key == "qty" and t.startswith("จำนวนเงิน"):
                        continue
                    cols[key] = x
        if not {"name", "qty", "unit"} <= set(cols):
            continue
        money = sorted(x for y, x, w, t in band if t.startswith(("ราคาหน่วยละ", "ราคาต่อหน่วย", "จำนวนเงิน", "เป็นเงิน"))
                       and x > cols["unit"])
        total = [x for y, x, w, t in band if (t.startswith("รวมค่าวัสดุ") or t.startswith("รวม")) and x > cols["unit"]]
        cols["money"] = money[:4]
        if total:
            cols["total"] = min(total, key=lambda v: abs(v - (money[-1] if money else v)))
        tables.append((hy, cols))
    tables.sort()
    return tables


def _parse_bill(lines, page_no, title_hint=""):
    """Bill rows of one page (each table on it)."""
    tables = _tables(lines)
    rows_out, bills = [], []
    for k, (hy, cols) in enumerate(tables):
        nxt = tables[k + 1][0] if k + 1 < len(tables) else float("inf")
        title = ""
        for y, x, w, t in lines:                    # the bill's title above its header
            if hy - 140 < y < hy and t.startswith(("รายการประมาณราคา", "แบบแสดงรายการ", "ชื่อโครงการ", "โครงการ")):
                title = t
        title = re.sub(r"^(รายการประมาณราคาค่าก่อสร้าง|แบบแสดงรายการ.*?ต้นทุน|ชื่อโครงการ(งานก่อสร้าง)?|โครงการ)\s*", "",
                       title or title_hint).strip()
        if title.count("(") > title.count(")"):
            title += ")"
        ends = [y for y, x, w, t in lines if hy < y < nxt and (t.startswith("แผ่นที่") or "เป็นเงินประมาณ" in t
                                                                 or t.startswith("รวมค่าวัสดุและค่าแรงงาน"))]
        end = min(ends) if ends else nxt - 90
        x_no, x_name, x_qty, x_unit = cols.get("no", cols["name"] - 150), cols["name"], cols["qty"], cols["unit"]
        money = cols["money"]
        body = [ln for ln in lines if hy + 12 < ln[0] < end - 4 and ln[3] not in ("แบบ ปร.4", "แบบ ปร.5", "แบบ ปร.1")]
        band = defaultdict(list)
        for y, x, w, t in body:
            band[round(y / 6)].append((y, x, w, t))
        keys = sorted(band)
        merged, cur, last = [], [], None
        for kk in keys:                             # rows are ~20 pt apart: neighbours of 6 pt belong together
            if last is not None and kk - last > 1:
                merged.append(cur)
                cur = []
            cur += band[kk]
            last = kk
        if cur:
            merged.append(cur)
        for row in merged:
            cells = defaultdict(list)
            for y, x, w, t in sorted(row, key=lambda r: r[1]):
                left = x - w / 2
                if x < (x_no + x_name) / 2 - 40 and len(t) <= 6 and (_num(t) is not None or re.fullmatch(r"[\d.]+", t)):
                    cells["no"].append(t)
                elif x < (x_name + x_qty) / 2 or left < x_qty - 40:
                    cells["name"].append(t)
                elif x < (x_qty + x_unit) / 2:
                    cells["qty"].append(t)
                elif x < x_unit + 25:
                    cells["unit"].append(t)
                else:
                    cells["money"].append((x, t))
            name = " ".join(cells["name"]).strip()
            if not name:
                continue
            qty = _num(" ".join(cells["qty"])) if cells["qty"] else None
            unit = " ".join(cells["unit"]).strip()
            vals = [None] * 5
            for x, t in cells["money"]:
                v = _num(t)
                if v is None:
                    continue
                pos = money + [cols.get("total", 1e9)]
                j = min(range(len(pos)), key=lambda i: abs(pos[i] - x)) if pos else 4
                vals[min(j, 4)] = v
            rows_out.append(dict(bill=title, no=" ".join(cells["no"]), name=name, qty=qty, unit=unit, vals=vals,
                                 page=page_no))
        bills.append(title)
    return rows_out, bills


# -- OCR of a title block ------------------------------------------------------------------------

def tesseract_path() -> str:
    """The OCR program: beside the program (Windows installer), on PATH, or nothing."""
    here = Path(__file__).resolve().parent.parent
    exe_dir = Path(sys.executable).resolve().parent      # the installed program's folder
    for cand in (exe_dir / "tesseract" / "tesseract.exe", here / "tesseract" / "tesseract.exe",
                 here / "tesseract" / "tesseract",
                 Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Tesseract-OCR" / "tesseract.exe"):
        if cand.exists():
            return str(cand)
    return shutil.which("tesseract") or ""


def _ocr(png: bytes, psm: int = 6) -> tuple:
    exe = tesseract_path()
    if not exe:
        return "", 0.0
    with tempfile.TemporaryDirectory() as d:
        src = os.path.join(d, "p.png")
        Path(src).write_bytes(png)
        env = dict(os.environ)
        td = Path(exe).parent / "tessdata"
        if td.exists():
            env["TESSDATA_PREFIX"] = str(td)
        kw = dict(capture_output=True, timeout=120, env=env)
        if os.name == "nt":
            kw["creationflags"] = 0x08000000           # no console window
        r = subprocess.run([exe, src, os.path.join(d, "o"), "-l", "tha+eng", "--psm", str(psm), "tsv"],
                           check=False, **kw)
        if r.returncode != 0 or not os.path.exists(os.path.join(d, "o.tsv")):
            return "", 0.0
        with open(os.path.join(d, "o.tsv"), encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh, delimiter="\t", quoting=csv.QUOTE_NONE))
    words = [(r["text"], float(r["conf"])) for r in rows if (r.get("text") or "").strip() and r["conf"] != "-1"]
    lines, cur, key = [], [], None
    for r in rows:
        if not (r.get("text") or "").strip():
            continue
        k = (r["block_num"], r["par_num"], r["line_num"])
        if k != key and cur:
            lines.append(" ".join(cur))
            cur = []
        key = k
        cur.append(r["text"].strip())
    if cur:
        lines.append(" ".join(cur))
    conf = sum(c for _w, c in words) / len(words) if words else 0.0
    return "\n".join(lines), conf


def thai_join(s: str) -> str:
    """OCR puts a space between Thai letters; take them out (Thai has no spaces inside words)."""
    s = re.sub(r"(?<=[\u0E00-\u0E7F]) (?=[\u0E00-\u0E7F])", "", s)
    return " ".join(s.split())


def _strip(page, frac, dpi):
    """The title-block strip as PNG: the right 16 % of a landscape sheet (its bottom `frac`),
    else the bottom 16 %."""
    import pymupdf
    r = page.rect
    if r.width >= r.height:
        clip = pymupdf.Rect(r.width * 0.84, r.height * (1 - frac), r.width, r.height)
    else:
        clip = pymupdf.Rect(0, r.height * (1 - 0.16 * frac), r.width, r.height)
    zoom = dpi / 72.0
    if r.width > 1500:                                # scans placed near pixel size: read at the scan's own
        zoom = 1.4 * dpi / 200.0                      # resolution
    return page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), clip=clip, alpha=False).tobytes("png")


def _title_block(page):
    """OCR of the title block, plus its sheet-number box read again sharper."""
    text, conf = _ocr(_strip(page, 1.0, 200))
    text = "\n".join(thai_join(ln) for ln in text.splitlines())
    corner, _c = _ocr(_strip(page, 0.1, 300))
    return text + "\n" + corner, conf


def _thai_share(s: str) -> float:
    letters = [c for c in s if not c.isspace()]
    return sum(1 for c in letters if 0xE00 <= ord(c) <= 0xE7F) / len(letters) if letters else 0.0


def _is_show(ln: str) -> bool:
    """the «แสดงแบบ» label, as OCR spells it"""
    return len(ln) <= 9 and ln.startswith("แส") and ln.endswith("บบ")


def _title_from_ocr(text: str) -> str:
    """The sheet's title sits between the approver (อธิบดี…/แสดงแบบ) and the date/scale lines."""
    lines = [ln.strip(" |[]") for ln in text.splitlines()]
    start = 0
    for i, ln in enumerate(lines):
        if ln.startswith("อธิบ") or _is_show(ln):        # OCR misreads: อธิบตี… แสตงแบบ แสดงนบบ
            start = i + 1
    if not start:                                     # approver's line unread: look above the scale/date
        ends = [i for i, ln in enumerate(lines) if any(w in ln for w in ("มาตรา", "เดือน", "ส่วน 1:"))]
        if not ends:
            return ""                                 # no title block: a cover or a photo
        near = [ln for ln in lines[max(0, ends[0] - 4):ends[0]]
                if 4 <= len(ln) <= 50 and _thai_share(ln) >= 0.6 and any(w in ln for w in TITLE_WORDS)]
        return " · ".join(near[-2:])
    out = []
    for ln in lines[start:]:
        if any(w in ln for w in ("เดือน", "เดีอน", "มาตร", "เลขที่", "แผ่นที่", "จำนวนแผ่น")) or ln in ("วัน", "ปี"):
            break
        if re.search(r"\d\s?:\s?\d|\d{5,}|มตรา|มาตร|ขที่|จ้านวน|จำนวน", ln):   # scale/number lines misread
            break
        if _is_show(ln) or len(ln) < 4 or _thai_share(ln) < 0.6:
            continue
        out.append(ln)
    return " · ".join(out[:3])


def _sheet_from_text(text: str, ocr: bool = False):
    t = text.translate(THAI_DIGITS)
    if ocr:                                           # O read for 0, 5/s read for S in a sheet number
        t = re.sub(r"(?<![\w-])[5s]-(\d{2})\b", r"S-\1", t)
        t = re.sub(r"(?<![\w-])([aeAE])-(\d{2})\b", lambda m: f"{m.group(1).upper()}-{m.group(2)}", t)
        t = re.sub(r"\b(SN|EE|ME|AC|[ASEMPCRL])\s?[-–]\s?([0-9O]{1,3})\b",
                   lambda m: f"{m.group(1)}-{m.group(2).replace('O', '0')}", t)
    sheet = ""
    for m in SHEET_RE.finditer(t):
        sheet = f"{m.group(1)}-{m.group(2).zfill(2)}"           # the last one is the sheet's own number
    if ocr:
        return sheet, _title_from_ocr(t)
    title = ""
    for ln in t.splitlines():
        s = " ".join(ln.split())
        if 4 <= len(s) <= 60 and any(s.startswith(w) or f" {w}" in s for w in TITLE_WORDS) \
                and not any(w in s for w in ("ผู้อำนวยการ", "วิศวกร", "สถาปนิก", "อนุมัติ", "ลงชื่อ", "สำนัก",
                                             "อธิบดี", "กรม")):
            title = s
    return sheet, title


# -- the whole set ---------------------------------------------------------------------------------

class _Pages(list):
    """The pages read so far; each one is handed to `on_page` as soon as it is read."""

    def __init__(self, on_page=None):
        super().__init__()
        self.on_page = on_page

    def append(self, pg):
        super().append(pg)
        if self.on_page:
            self.on_page(pg)


def analyse(path, ocr: bool = True, progress=None, on_page=None) -> Result:
    """Read every page; `progress(i, n, text)` returns False to stop."""
    import pymupdf
    doc = pymupdf.open(str(path))
    n = doc.page_count
    use_ocr = ocr and bool(tesseract_path())
    pages, raw, tags = _Pages(on_page), [], defaultdict(dict)
    project = ""
    for i, page in enumerate(doc):
        if progress and progress(i, n, f"หน้า {i + 1}/{n}") is False:
            break
        pg = Page(no=i + 1)
        text = fix_marks(page.get_text())
        legacy = looks_legacy(text)
        if legacy:
            text = decode_legacy(text)
        words = [w for w in text.split() if w.strip()]
        has_img = bool(page.get_images())
        n_draw = len(page.get_drawings()) if len(words) < 30 else 0
        lines = _lines(page, legacy) if words else []
        is_bill = any(t == "รายการ" for _y, _x, _w, t in lines) and ("จำนวน" in text or "ปริมาณ" in text) \
            and "หน่วย" in text and (re.search(r"ปร\.\s?[145]", text) or "ลำดับ" in text)
        if is_bill:
            rows, bills = _parse_bill(lines, i + 1)
            if rows:
                pg.kind = "ตาราง BOQ" + (" (ฟอนต์ไทยรุ่นเก่า แปลงให้แล้ว)" if legacy else "")
                pg.items = sum(1 for r in rows if r["qty"] is not None)
                pg.title = bills[0] if bills else "ตารางประมาณราคา"
                pg.work = _work_of(" ".join(bills), "อาคาร")
                pg.status = "อ่านได้"
                pg.note = (f"อ่านได้ {pg.items} รายการที่มีปริมาณ" if pg.items else
                           "ตารางนี้ไม่มีรายการที่มีปริมาณ (หมวดว่าง/หน้าสรุป) — ตรวจว่าไม่ได้ตกหล่น")
                raw += [(r, pg.work) for r in rows]
                project = project or (bills[0] if bills else "")
                pages.append(pg)
                continue
        if len(words) >= 30:                          # a sheet with real text
            pg.kind = "แบบ (มีข้อความ)" if n_draw or page.get_drawings() else "ข้อความ"
            pg.sheet, pg.title = _sheet_from_text(text)
            found = Counter(w for w in words if TAG_RE.match(w))
            for t, c in found.items():
                tags[t][i + 1] = c
            pg.tags = dict(found)
            pg.discipline = _discipline(pg.sheet)
            pg.work = _work_of(text, "อาคาร" if pg.discipline else "")
            if pg.kind == "ข้อความ":
                pg.status = "อ่านได้บางส่วน"
                pg.note = "หน้าข้อความ/รายการประกอบแบบ — อ่านข้อความได้ ไม่มีปริมาณให้ถอด"
            else:
                pg.status = "อ่านได้บางส่วน"
                pg.note = (f"นับป้ายได้ {sum(found.values())} จุด ({len(found)} ชนิด) — ความยาว พื้นที่ ปริมาตร "
                           "ต้องวัดด้วยเครื่องมือวัด" if found else
                           "อ่านชื่อแผ่นได้ ไม่พบป้าย — ปริมาณต้องวัดด้วยเครื่องมือวัด/รูปทรง")
            pages.append(pg)
            continue
        # no usable text: the letters are drawn as lines, or the page is a scan
        pg.kind = "ภาพสแกน" if has_img and n_draw < 50 else ("แบบ (ข้อความเป็นเส้น)" if n_draw else "ว่าง")
        if pg.kind == "ว่าง":
            pg.status, pg.note = "อ่านไม่ได้", "หน้าว่าง"
            pages.append(pg)
            continue
        if use_ocr:
            if progress and progress(i, n, f"หน้า {i + 1}/{n} · อ่านกรอบชื่อแบบ (OCR)") is False:
                break
            otext, conf = _title_block(page)
            pg.sheet, pg.title = _sheet_from_text(otext, ocr=True)
            pg.discipline = _discipline(pg.sheet)
            pg.work = _work_of(otext, "อาคาร" if pg.discipline else "")
            if pg.sheet or pg.title:
                pg.status = "อ่านได้บางส่วน"
                pg.note = ("อ่านได้เฉพาะเลขและชื่อแผ่นจากภาพ (OCR อาจสะกดผิด)"
                           + (" ภาพไม่ชัด" if conf < 70 else "") + ("" if pg.sheet else " · ไม่พบเลขแผ่น")
                           + " — ตัวหนังสือในแบบเป็นภาพ/เส้น ป้ายและขนาดอ่านอัตโนมัติไม่ได้ "
                           "ให้ถอดด้วยเครื่องมือวัด/รูปทรง")
            else:
                pg.status, pg.work = "อ่านไม่ได้", ""
                pg.note = ("ไม่พบกรอบชื่อแบบ (อาจเป็นภาพปก/ภาพประกอบ)" if pg.kind == "ภาพสแกน" else
                           "อ่านกรอบชื่อแบบไม่ได้") + (" · ภาพไม่ชัด" if 0 < conf < 55 else "")
        else:
            pg.status = "อ่านไม่ได้"
            pg.note = ("ตัวหนังสือในแบบเป็นภาพ/เส้น และเครื่องนี้ไม่มีตัวอ่านภาพ (OCR)"
                       " — ให้ถอดด้วยเครื่องมือวัด/รูปทรง")
        pages.append(pg)
    doc.close()
    _fix_sequence(pages)
    _flag_repeats(pages)
    main = Counter(p.work for p in pages if p.work).most_common(1)
    for p in pages:                                   # a sheet without its own clue belongs to the set
        if not p.work and p.status != "อ่านไม่ได้" and main:
            p.work = main[0][0]
    lines_out = _to_lines(raw)
    return Result(path=str(path), pages=pages, lines=lines_out, tags=dict(tags), project=project, ocr=use_ocr)


def _sheet_key(sheet):
    m = re.fullmatch(r"([A-Z]+)-(\d+)", sheet or "")
    return (m.group(1), int(m.group(2))) if m else None


def _fix_sequence(pages):
    """A sheet number OCR missed or misread, when the sheets before and after agree on it
    (A-16, ?, A-18 → A-17). Marked for the user to check."""
    keys = [_sheet_key(p.sheet) for p in pages]
    for i, p in enumerate(pages):
        if p.status == "อ่านไม่ได้" or not p.kind.startswith(("ภาพสแกน", "แบบ (ข้อความเป็นเส้น)")):
            continue
        a = next((j for j in range(i - 1, -1, -1) if keys[j]), None)
        b = next((j for j in range(i + 1, len(keys)) if keys[j]), None)
        guess = None
        if a is not None and b is not None and keys[a][0] == keys[b][0] and keys[b][1] - keys[a][1] == b - a:
            guess = (keys[a][0], keys[a][1] + i - a)
        elif b is not None and a is None and keys[b][1] == b - i + 1:
            guess = (keys[b][0], 1)
        elif keys[i] is None and a is not None and (b is None or keys[b][0] != keys[a][0]):
            guess = (keys[a][0], keys[a][1] + i - a)       # the last sheet of its group
        if guess and keys[i] != guess:
            was = p.sheet
            p.sheet = f"{guess[0]}-{guess[1]:02d}"
            keys[i] = guess
            p.discipline = _discipline(p.sheet)
            p.note = (f"เลขแผ่นคาดจากลำดับแผ่น (อ่านได้ «{was}»)" if was else "เลขแผ่นคาดจากลำดับแผ่น") \
                + " ตรวจอีกครั้ง · " + p.note.replace(" · ไม่พบเลขแผ่น", "")


def _flag_repeats(pages):
    seen = {}
    for p in pages:
        if p.sheet and p.sheet in seen:
            p.note = f"เลขแผ่นซ้ำกับหน้า {seen[p.sheet]} — ตรวจอีกครั้ง · " + p.note
        elif p.sheet:
            seen[p.sheet] = p.no


def _to_lines(raw) -> list:
    """Bill rows → lines with their group (หมวด) and section; wrapped names joined."""
    out, group, section = [], "", ""
    seen_bills = {}
    for r, work in raw:
        name, qty = r["name"], r["qty"]
        if name.startswith(("รวม", "สรุป")) or name in ("สรุปงาน",):
            continue
        if "หมวด" in name and qty is None:
            group, section = re.sub(r"^\d+\s*", "", name), ""
            continue
        if re.match(r"^\d+(\.\d+)+\s", name) and qty is None:
            section = name
            continue
        if qty is None and out and not name.startswith(("-", "•")) and out[-1].page == r["page"] \
                and out[-1].bill == r["bill"]:
            out[-1].name += " " + name                     # the rest of a wrapped name
            out[-1].sure = False
            continue
        if qty is None:
            section = section or name
            continue
        mu, ma, lu, la, tot = r["vals"]
        bill = r["bill"]
        seen_bills.setdefault(bill, len(seen_bills) + 1)
        out.append(Line(work=work, bill=bill, group=group, section=section, name=name.lstrip("-• ").strip(), qty=qty,
                        unit=r["unit"], mat_u=mu, mat=ma, lab_u=lu, lab=la, total=tot, page=r["page"],
                        sure=bool(r["unit"])))
    return out


# -- CSV ---------------------------------------------------------------------------------------------

PR1_HEADERS = ["ลำดับที่", "รายการ", "จำนวน", "หน่วย", "ค่าวัสดุ ราคาต่อหน่วย", "ค่าวัสดุ จำนวนเงิน",
               "ค่าแรงงาน ราคาต่อหน่วย", "ค่าแรงงาน จำนวนเงิน", "รวมค่าวัสดุและค่าแรงงาน", "หมายเหตุ"]


def _fmt(v):
    if v is None:
        return ""
    return f"{v:.2f}".rstrip("0").rstrip(".") if abs(v - round(v)) > 1e-9 else str(int(round(v)))


def safe(s: str) -> str:
    s = re.sub(r'[\\/:*?"<>|]+', " ", s or "")
    return " ".join(s.split())[:60] or "งาน"


def write_csv(res: Result, folder, info: dict | None = None) -> list:
    """One ปร.1 CSV per kind of work and bill, a CSV of the tags counted, and the reading report."""
    info = info or {}
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    stem = safe(Path(res.path).stem)
    written = []
    for work, lines in res.by_work().items():
        bills = defaultdict(list)
        for ln in lines:
            bills[ln.bill].append(ln)
        for bk, (bill, items) in enumerate(bills.items(), 1):
            suffix = f"-{bk}" if len(bills) > 1 else ""
            f = folder / f"{stem} - ปร.1 งาน{work.replace(' ', '')}{suffix}.csv"
            with open(f, "w", newline="", encoding="utf-8-sig") as fh:
                w = csv.writer(fh)
                w.writerow(["", "", "", "", "", "", "", "", "", "แบบ ปร.1"])
                w.writerow(["แบบแสดงรายการ ปริมาณงาน และราคา ค่างานต้นทุน"])
                w.writerow([f"ชื่อโครงการงานก่อสร้าง  {info.get('project') or bill or '..........'}"])
                w.writerow([f"สถานที่ก่อสร้าง  {info.get('place') or '..........'}"])
                w.writerow([f"แบบเลขที่  {info.get('drawing_no') or '..........'}"])
                w.writerow([f"หน่วยงานเจ้าของโครงการงานก่อสร้าง  {info.get('owner') or '..........'}"])
                w.writerow([f"ประเภทงาน  งาน{work} · ถอดจากไฟล์ {Path(res.path).name}"])
                w.writerow(PR1_HEADERS)
                grp_no, k, n_in, cur_g, cur_s = 0, 0, 0, None, None
                for ln in items:
                    if ln.group != cur_g:
                        grp_no += 1
                        k = 0
                        cur_g, cur_s = ln.group, None
                        w.writerow([str(grp_no), ln.group or "รายการ"] + [""] * 8)
                    if ln.section != cur_s:
                        cur_s = ln.section
                        if cur_s:
                            k += 1
                            n_in = 0
                            w.writerow([f"{grp_no}.{k}", re.sub(r"^\d+(\.\d+)+\s*", "", cur_s)] + [""] * 8)
                    if cur_s:
                        n_in += 1
                        code = f"{grp_no}.{k}.{n_in}"
                    else:
                        k += 1
                        code = f"{grp_no}.{k}"
                    note = f"หน้า {ln.page}" + ("" if ln.sure else " · ตรวจชื่อรายการ")
                    w.writerow([code, ln.name, _fmt(ln.qty), ln.unit, _fmt(ln.mat_u), _fmt(ln.mat), _fmt(ln.lab_u),
                                _fmt(ln.lab), _fmt(ln.total), note])
            written.append(f)
    if res.tags:
        f = folder / f"{stem} - ป้ายที่นับจากแบบ.csv"
        sheets = {p.no: p for p in res.pages}
        with open(f, "w", newline="", encoding="utf-8-sig") as fh:
            w = csv.writer(fh)
            w.writerow(["ป้าย", "ความหมาย (โดยประมาณ)", "จำนวนรวม", "พบในหน้า (แผ่น: จำนวน)", "หมายเหตุ"])
            for tag in sorted(res.tags, key=lambda t: (t.rstrip("0123456789"), int(re.sub(r"\D", "", t) or 0))):
                where = res.tags[tag]
                w.writerow([tag, tag_meaning(tag), sum(where.values()),
                            " · ".join(f"{sheets[p].sheet or 'หน้า ' + str(p)}: {c}" for p, c in sorted(where.items())),
                            "นับจากข้อความในแบบ — ตรวจกับแบบอีกครั้ง"])
        written.append(f)
    f = folder / f"{stem} - รายงานการอ่านแบบ.csv"
    with open(f, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        s = res.summary()
        w.writerow([f"รายงานการอ่านแบบ: {Path(res.path).name}"])
        w.writerow([f"ทั้งหมด {s['ทั้งหมด']} หน้า · อ่านได้ {s['อ่านได้']} · อ่านได้บางส่วน {s['อ่านได้บางส่วน']} · "
                    f"อ่านไม่ได้ {s['อ่านไม่ได้']}" + ("" if res.ocr else " · เครื่องนี้ไม่มีตัวอ่านภาพ (OCR)")])
        w.writerow(["หน้า", "ผลการอ่าน", "ชนิดหน้า", "เลขแผ่น", "ชื่อแผ่น", "หมวดแบบ", "ประเภทงาน", "รายการที่อ่านได้",
                    "หมายเหตุ / สิ่งที่ต้องทำต่อ"])
        for p in res.pages:
            w.writerow([p.no, p.status, p.kind, p.sheet, p.title, p.discipline, p.work, p.items or "", p.note])
    written.append(f)
    return written


TAG_MEANINGS = {"ป": "ประตู", "น": "หน้าต่าง", "พ": "วัสดุผิวพื้น", "ผ": "วัสดุผิวผนัง", "ฝ": "ฝ้าเพดาน",
                "D": "ประตู", "W": "หน้าต่าง", "DW": "ประตู-หน้าต่าง", "F": "ฐานราก", "C": "เสา", "B": "คาน",
                "GB": "คานคอดิน", "RB": "คานหลังคา", "S": "พื้น", "SL": "พื้น", "ST": "บันได", "P": "เสาเข็ม",
                "BF": "ฐานราก", "SF": "ฐานรากแผ่"}


def tag_meaning(tag: str) -> str:
    return TAG_MEANINGS.get(tag.rstrip("0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ") or tag[:1], "")
