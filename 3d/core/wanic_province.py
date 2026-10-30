# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
"""Material prices by province (ราคาวัสดุก่อสร้าง สำนักงานพาณิชย์จังหวัด).

The program carries no official prices: the Ministry of Commerce publishes
them every month for each province.  This module keeps one *price book* per
province on the user's computer, reads the commerce office's table (Excel
.xlsx, CSV, or rows copied from the web page), and matches its item names to
the materials the BOQ asks for.

Pure Python — no Qt — so it is tested on its own.
"""
from __future__ import annotations

import csv
import datetime
import difflib
import io
import json
import os
import re
import zipfile
from xml.etree import ElementTree as ET

#: The 77 provinces, by region (as the commerce ministry groups them).
REGIONS = {
    "กรุงเทพฯ และปริมณฑล": [
        "กรุงเทพมหานคร", "นนทบุรี", "ปทุมธานี", "สมุทรปราการ", "สมุทรสาคร",
        "นครปฐม"],
    "ภาคกลาง": [
        "พระนครศรีอยุธยา", "อ่างทอง", "ลพบุรี", "สิงห์บุรี", "ชัยนาท", "สระบุรี",
        "นครนายก", "สุพรรณบุรี", "กาญจนบุรี", "ราชบุรี", "เพชรบุรี",
        "ประจวบคีรีขันธ์", "สมุทรสงคราม"],
    "ภาคตะวันออก": [
        "ชลบุรี", "ระยอง", "จันทบุรี", "ตราด", "ฉะเชิงเทรา", "ปราจีนบุรี",
        "สระแก้ว"],
    "ภาคเหนือ": [
        "เชียงใหม่", "เชียงราย", "ลำปาง", "ลำพูน", "แม่ฮ่องสอน", "น่าน", "พะเยา",
        "แพร่", "อุตรดิตถ์", "ตาก", "สุโขทัย", "พิษณุโลก", "พิจิตร", "เพชรบูรณ์",
        "กำแพงเพชร", "นครสวรรค์", "อุทัยธานี"],
    "ภาคตะวันออกเฉียงเหนือ": [
        "นครราชสีมา", "บุรีรัมย์", "สุรินทร์", "ศรีสะเกษ", "อุบลราชธานี",
        "ยโสธร", "อำนาจเจริญ", "ชัยภูมิ", "ขอนแก่น", "อุดรธานี", "เลย",
        "หนองคาย", "บึงกาฬ", "หนองบัวลำภู", "มหาสารคาม", "ร้อยเอ็ด",
        "กาฬสินธุ์", "สกลนคร", "นครพนม", "มุกดาหาร"],
    "ภาคใต้": [
        "นครศรีธรรมราช", "กระบี่", "พังงา", "ภูเก็ต", "สุราษฎร์ธานี", "ระนอง",
        "ชุมพร", "สงขลา", "สตูล", "ตรัง", "พัทลุง", "ปัตตานี", "ยะลา",
        "นราธิวาส"],
}
PROVINCES = [p for ps in REGIONS.values() for p in ps]
assert len(PROVINCES) == len(set(PROVINCES)) == 77

#: Where the user reads the official prices (opened in the browser).
PRICE_SITE = ("https://index.tpso.go.th/construction-material-prices/"
              "prices-building-materials")


def market_search_url(item: str, province: str) -> str:
    """A web search for the item's shop price in the province."""
    from urllib.parse import quote_plus
    q = f"ราคา {item} {province} ร้านวัสดุก่อสร้าง"
    return "https://www.google.com/search?q=" + quote_plus(q)

#: MOC Open Data — average construction-material prices by province
#: (ราคาวัสดุก่อสร้าง สนค.), https://data.moc.go.th/OpenData/CSIProductIndexes
API = "https://dataapi.moc.go.th"

#: Province codes (มาตรฐานรหัสจังหวัด) the MOC API uses.
CODES = {
    "กรุงเทพมหานคร": "10", "สมุทรปราการ": "11", "นนทบุรี": "12",
    "ปทุมธานี": "13", "พระนครศรีอยุธยา": "14", "อ่างทอง": "15", "ลพบุรี": "16",
    "สิงห์บุรี": "17", "ชัยนาท": "18", "สระบุรี": "19", "ชลบุรี": "20",
    "ระยอง": "21", "จันทบุรี": "22", "ตราด": "23", "ฉะเชิงเทรา": "24",
    "ปราจีนบุรี": "25", "นครนายก": "26", "สระแก้ว": "27", "นครราชสีมา": "30",
    "บุรีรัมย์": "31", "สุรินทร์": "32", "ศรีสะเกษ": "33", "อุบลราชธานี": "34",
    "ยโสธร": "35", "ชัยภูมิ": "36", "อำนาจเจริญ": "37", "บึงกาฬ": "38",
    "หนองบัวลำภู": "39", "ขอนแก่น": "40", "อุดรธานี": "41", "เลย": "42",
    "หนองคาย": "43", "มหาสารคาม": "44", "ร้อยเอ็ด": "45", "กาฬสินธุ์": "46",
    "สกลนคร": "47", "นครพนม": "48", "มุกดาหาร": "49", "เชียงใหม่": "50",
    "ลำพูน": "51", "ลำปาง": "52", "อุตรดิตถ์": "53", "แพร่": "54", "น่าน": "55",
    "พะเยา": "56", "เชียงราย": "57", "แม่ฮ่องสอน": "58", "นครสวรรค์": "60",
    "อุทัยธานี": "61", "กำแพงเพชร": "62", "ตาก": "63", "สุโขทัย": "64",
    "พิษณุโลก": "65", "พิจิตร": "66", "เพชรบูรณ์": "67", "ราชบุรี": "70",
    "กาญจนบุรี": "71", "สุพรรณบุรี": "72", "นครปฐม": "73", "สมุทรสาคร": "74",
    "สมุทรสงคราม": "75", "เพชรบุรี": "76", "ประจวบคีรีขันธ์": "77",
    "นครศรีธรรมราช": "80", "กระบี่": "81", "พังงา": "82", "ภูเก็ต": "83",
    "สุราษฎร์ธานี": "84", "ระนอง": "85", "ชุมพร": "86", "สงขลา": "90",
    "สตูล": "91", "ตรัง": "92", "พัทลุง": "93", "ปัตตานี": "94", "ยะลา": "95",
    "นราธิวาส": "96",
}
assert sorted(CODES) == sorted(PROVINCES)

_TH_MONTHS = ["ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.", "ก.ค.",
              "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค."]


def region_of(province: str) -> str:
    for r, ps in REGIONS.items():
        if province in ps:
            return r
    return ""


def month_label(year: int, month: int) -> str:
    """``(2026, 9)`` → ``ก.ย. 2569`` (a Buddhist-era year is kept)."""
    y = year + 543 if year < 2400 else year
    return f"{_TH_MONTHS[(month - 1) % 12]} {y}"


def last_month(today=None) -> str:
    """The month the rules say to use: the one before this (``ก.ย. 2569``)."""
    d = today or datetime.date.today()
    y, m = (d.year, d.month - 1) if d.month > 1 else (d.year - 1, 12)
    return f"{_TH_MONTHS[m - 1]} {y + 543}"


# ---------------------------------------------------------------------------
# Price books on disk
# ---------------------------------------------------------------------------

def book_dir() -> str:
    """``%APPDATA%\\WANICNSURVEY\\ราคาวัสดุ`` (or ``~/.local/share/…``)."""
    env = os.environ.get("WANIC_PRICE_DIR")
    if env:
        return env
    base = os.environ.get("APPDATA") or os.path.join(
        os.path.expanduser("~"), ".local", "share")
    return os.path.join(base, "WANICNSURVEY", "ราคาวัสดุ")


def _path(province: str) -> str:
    safe = re.sub(r'[\\/:*?"<>|]', "_", province)
    return os.path.join(book_dir(), f"{safe}.json")


def load_book(province: str) -> dict | None:
    try:
        with open(_path(province), encoding="utf-8") as fh:
            b = json.load(fh)
    except (OSError, ValueError):
        return None
    if not isinstance(b, dict) or not isinstance(b.get("prices"), dict):
        return None
    return b


def save_book(province: str, prices: dict, month: str = "",
              source: str = "", src: dict | None = None,
              item: dict | None = None) -> dict:
    """Write the province's book; ``src`` says where each price came from
    (``พาณิชย์`` / ``กรอกเอง`` / ``ตัวอย่าง``)."""
    os.makedirs(book_dir(), exist_ok=True)
    book = {"province": province, "month": month,
            "source": source or f"สำนักงานพาณิชย์จังหวัด{province}",
            "updated": datetime.date.today().isoformat(),
            "prices": {k: float(v) for k, v in prices.items()
                       if _num(v) is not None and float(v) > 0}}
    book["src"] = {k: (src or {}).get(k, "พาณิชย์") for k in book["prices"]}
    book["item"] = {k: v for k, v in (item or {}).items() if k in book["prices"]}
    with open(_path(province), "w", encoding="utf-8") as fh:
        json.dump(book, fh, ensure_ascii=False, indent=1)
    return book


def books() -> list[str]:
    """Provinces that have a saved price book."""
    return [p for p in PROVINCES if os.path.exists(_path(p))]


# ---------------------------------------------------------------------------
# Reading the commerce office's table
# ---------------------------------------------------------------------------

def _num(v):
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v or "").strip().replace(",", "").replace("฿", "")
    if not re.fullmatch(r"-?\d+(\.\d+)?", s):
        return None
    return float(s)


_UNITS = ("ลบ.ม.", "ตร.ม.", "ตร.ฟ.", "ลบ.ฟ.", "กก.", "ตัน", "ก้อน", "แผ่น",
          "ถุง", "เส้น", "ท่อน", "ต้น", "ม.", "เมตร", "ชุด", "ลิตร", "แกลลอน",
          "ถัง", "อัน", "ตัว", "บาน", "ม้วน", "คิว", "โหล", "กล่อง", "ลูก")


def _is_unit(s: str) -> bool:
    s = s.strip()
    return bool(s) and len(s) <= 10 and any(s.startswith(u) or s == u
                                             for u in _UNITS)


_FULL_MONTHS = ["มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม",
                "มิถุนายน", "กรกฎาคม", "สิงหาคม", "กันยายน", "ตุลาคม",
                "พฤศจิกายน", "ธันวาคม"]


def _header(cells):
    """Column indices of a header row (``รายการ`` … ``หน่วย`` …), or None."""
    name = next((i for i, c in enumerate(cells)
                 if re.fullmatch(r"(ชื่อ)?รายการ(สินค้า|วัสดุ)?", c)), None)
    if name is None:
        return None
    unit = next((i for i, c in enumerate(cells) if c.startswith("หน่วย")),
                None)
    return {"name": name, "unit": unit}


def detect_month(rows) -> str:
    """``ก.ย. 2569`` from a table's title or header (``ระยะเวลา กันยายน
    2569`` / a ``กันยายน`` column with ``2569`` elsewhere), or ""."""
    month = year = None
    for row in rows[:40]:
        for c in row:
            c = str(c or "")
            for mi, name in enumerate(_FULL_MONTHS):
                if name in c:
                    m = re.search(name + r"\s*(25\d\d)", c)
                    if m:
                        return f"{_TH_MONTHS[mi]} {m.group(1)}"
                    month = month if month is not None else mi
            y = re.search(r"\b(25[5-9]\d)\b", c)
            if y and year is None:
                year = y.group(1)
    if month is not None and year:
        return f"{_TH_MONTHS[month]} {year}"
    return ""


def parse_rows(rows) -> list[tuple[str, str, float]]:
    """``[(name, unit, price)]`` from table rows.

    With a header row (``รหัสหมวด · ชื่อหมวดสินค้า · รหัส · รายการ · หน่วย ·
    กันยายน`` as the commerce ministry's table has) the columns are taken
    from it.  Without one, the name is the text just before the unit (or the
    longest text) and the price the last number after the name — a row with
    last month's and this month's prices gives this month."""
    out = []
    head = None
    for row in rows:
        cells = [re.sub(r"\s+", " ", str(c if c is not None else "")).strip()
                 for c in row]
        h = _header(cells)
        if h:
            head = h
            continue
        nums = [(i, _num(c)) for i, c in enumerate(cells)]
        nums = [(i, n) for i, n in nums if n is not None]
        if not nums:
            continue
        if head and head["name"] < len(cells):
            ni, name = head["name"], cells[head["name"]]
            u = head["unit"]
            unit = cells[u] if u is not None and u < len(cells) else ""
        else:
            texts = [(i, c) for i, c in enumerate(cells)
                     if c and _num(c) is None]
            ui = next((i for i, c in texts if _is_unit(c)), None)
            unit = cells[ui] if ui is not None else ""
            names = [(i, c) for i, c in texts if not _is_unit(c)]
            if not names:
                continue
            before = [t for t in names if ui is not None and t[0] < ui]
            ni, name = before[-1] if before else max(names,
                                                      key=lambda t: len(t[1]))
        after = [n for i, n in nums if i > ni]
        if not after and head:
            continue
        price = (after or [nums[-1][1]])[-1]
        if price <= 0 or len(name) < 2 or _num(name) is not None:
            continue
        out.append((name, unit, price))
    return out


def rows_from_text(text: str) -> list[list[str]]:
    """Rows of pasted text (tabs from a web page / Excel) or CSV; a cell
    wrapped over two lines in quotes stays one cell."""
    text = text.lstrip("\ufeff")
    delim = "\t" if "\t" in text else ","
    return [r for r in csv.reader(io.StringIO(text), delimiter=delim)
            if any(c.strip() for c in r)]


def rows_from_xlsx(data: bytes) -> list[list[str]]:
    """Every sheet's rows of an .xlsx file (no extra library needed)."""
    ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    z = zipfile.ZipFile(io.BytesIO(data))
    shared = []
    if "xl/sharedStrings.xml" in z.namelist():
        root = ET.fromstring(z.read("xl/sharedStrings.xml"))
        for si in root.findall("m:si", ns):
            shared.append("".join(t.text or "" for t in si.iter(
                f"{{{ns['m']}}}t")))
    rows = []
    sheets = sorted(n for n in z.namelist()
                    if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", n))
    for name in sheets:
        root = ET.fromstring(z.read(name))
        for r in root.iter(f"{{{ns['m']}}}row"):
            cells = {}
            for c in r.findall("m:c", ns):
                ref = c.get("r", "")
                col = 0
                for ch in re.match(r"[A-Z]*", ref).group(0):
                    col = col * 26 + ord(ch) - 64
                t = c.get("t")
                v = c.find("m:v", ns)
                if t == "s" and v is not None:
                    val = shared[int(v.text)]
                elif t == "inlineStr":
                    val = "".join(x.text or "" for x in c.iter(
                        f"{{{ns['m']}}}t"))
                else:
                    val = v.text if v is not None else ""
                cells[col - 1 if col else len(cells)] = val
            if cells:
                rows.append([cells.get(i, "") for i in range(max(cells) + 1)])
    return rows


def read_file(path: str) -> list[tuple[str, str, float]]:
    return read_table(path)[0]


def read_table(path: str) -> tuple[list, str]:
    """``(items, month)`` of a price file (.xlsx / .csv / text)."""
    rows = _file_rows(path)
    return parse_rows(rows), detect_month(rows)


def _file_rows(path: str) -> list:
    with open(path, "rb") as fh:
        data = fh.read()
    if data[:2] == b"PK":
        return rows_from_xlsx(data)
    if data[:5] == b"%PDF-":
        raise ValueError("ไฟล์ PDF อ่านเป็นตารางไม่ได้ — เลือกดาวน์โหลดเป็น Excel "
                         "หรือคัดลอกตารางจากหน้าเว็บมาวาง")
    if data[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
        raise ValueError("ไฟล์ .xls รุ่นเก่า — เปิดใน Excel แล้วบันทึกเป็น .xlsx "
                         "หรือ CSV ก่อน หรือคัดลอกตารางมาวาง")
    for enc in ("utf-8-sig", "cp874", "tis-620"):
        try:
            text = data.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        text = data.decode("utf-8", "replace")
    return rows_from_text(text)


# ---------------------------------------------------------------------------
# Matching the commerce office's names to the BOQ's material keys
# ---------------------------------------------------------------------------

def _norm(s: str) -> str:
    s = s.lower().replace("×", "x").replace("”", '"').replace("“", '"')
    s = re.sub(r"[()\[\]{},;:•\-–—/]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _bar(name: str):
    """``RB6`` / ``DB16`` from a commerce-office rebar name, or None."""
    n = _norm(name)
    m = re.fullmatch(r"(rb|db)\s*(\d{1,2})", n)
    if m:
        return f"{m.group(1).upper()}{int(m.group(2))}"
    if "เหล็ก" not in n or not re.search(
            r"เส้น|เสริม|sr|sd|rb|db|ข้ออ้อย|กลม", n):
        return None
    if re.search(r"ตะแกรง|wire|รูปพรรณ|กล่อง|แผ่น|ฉาก|ท่อ", n):
        return None
    m = re.search(r"(\d{1,2})\s*(?:มม|mm)", n)
    if not m:
        return None
    d = int(m.group(1))
    deformed = bool(re.search(r"ข้ออ้อย|sd|\bdb", n))
    return f"{'DB' if deformed else 'RB'}{d}"


# Unit conversion: the commerce office's unit → the BOQ's unit.
_SAME = [{"ม.", "เมตร", "ม"}, {"ตร.ม.", "ตารางเมตร", "ตร.ม"},
         {"ลบ.ม.", "ลูกบาศก์เมตร", "คิว", "ลบ.ม"}, {"ตร.ฟ.", "ตร.ฟุต", "ตารางฟุต"},
         {"ลบ.ฟ.", "ลบ.ฟุต", "ลูกบาศก์ฟุต"}, {"กก.", "กิโลกรัม", "กก"},
         {"ต้น"}, {"แผ่น"}, {"ก้อน"}, {"ลิตร"}, {"ท่อน"}, {"ชุด"}, {"อัน"},
         {"ตัว"}, {"บาน"}, {"เส้น"}, {"ถุง"}]


def _u(s: str) -> str:
    return re.sub(r"\s+", "", str(s or "")).strip()


def unit_factor(name: str, unit: str, target: str):
    """Multiply the commerce price by this to get the price per ``target``
    (``ตัน``→``กก.`` 1/1000, a 50 kg bag → 1/50, 100 bricks a bag → 1/100,
    ตร.ฟ.→ตร.ม. 10.764 …); None when it cannot be converted safely."""
    u, t = _u(unit), _u(target)
    if not t or not u:
        return 1.0
    for grp in _SAME:
        g = {_u(x) for x in grp}
        if u in g and t in g:
            return 1.0
    if t == "กก.":
        if u == "ตัน":
            return 0.001
        m = (re.search(r"บรรจุ\s*([\d.]+)\s*กก", name) or
             re.search(r"(?:นน\.?|น้ำหนัก)\s*(?:สุทธิ)?\s*([\d.]+)\s*กก", name))
        if m and u in ("ถุง", "ลัง", "กระสอบ", "ท่อน", "ม้วน", "ถัง", "เส้น"):
            return 1.0 / float(m.group(1))
        m = re.search(r"น้ำหนักต่อขด\s*([\d.]+)\s*-\s*([\d.]+)\s*กก", name)
        if m and u in ("ม้วน", "ขด"):
            return 2.0 / (float(m.group(1)) + float(m.group(2)))
    if t == "ก้อน":
        m = re.search(r"(\d+)\s*ก้อน\s*/", unit + " " + name)
        if m:
            return 1.0 / float(m.group(1))
    if t == "ตร.ม." and u in ("ตร.ฟ.", "ตร.ฟุต"):
        return 10.7639
    if t == "ตร.ฟ." and u == "ตร.ม.":
        return 1 / 10.7639
    if t == "ลิตร":
        m = re.search(r"([\d.]+)\s*ลิตร", name)
        if m and u in ("ถัง", "กระป๋อง", "แกลลอน", "ขวด"):
            return 1.0 / float(m.group(1))
        if u == "แกลลอน":
            return 1 / 3.785
    if t == "ตร.ม." and u == "กล่อง":
        m = re.search(r"(\d+)\s*แผ่น\s*/\s*กล่อง", name)
        z = re.search(r"(\d+(?:\.\d+)?)\s*x\s*(\d+(?:\.\d+)?)\s*(ซม|นิ้ว|\"|”)?",
                      name)
        if m and z:
            a, b = float(z.group(1)), float(z.group(2))
            cm = z.group(3) == "ซม" or max(a, b) > 24
            area = a * b * (1e-4 if cm else 0.00064516)
            return 1.0 / (area * float(m.group(1)))
    return None


#: key pattern → (commerce-name pattern, preferred pattern). The first row
#: of the province table that fits (the preferred one if any) is used.
_RULES = [
    (r"^ทรายหยาบ", r"^ทรายหยาบ", None),
    (r"^ทรายละเอียด", r"^ทรายละเอียด", None),
    (r"^ทรายถม", r"^ทรายถม", None),
    (r"^หิน(เบอร์|ย่อย)|^หิน\s*1", r"^หิน(ย่อย|\s*เบอร์|\s*1|ก่อสร้าง)",
     r"เบอร์\s*1|1\s*-\s*2"),
    (r"silica", r"^ปูนซีเมนต์.*(ซิลิ|silica)", None),
    (r"^ปูนซีเมนต์ปอร์ตแลนด์", r"^ปูนซีเมนต์(ปอร์ตแลนด์|ไฮดรอลิก)",
     r"ประเภท\s*1|มอก\.?\s*15"),
    (r"^ปูนซีเมนต์ผสม", r"^ปูนซีเมนต์ผสม", r"มอก\.?\s*80"),
    (r"^คอนกรีต.*ผสมเสร็จ", None, None),                     # by strength
    (r"^ลวดผูก", r"^ลวดผูกเหล็ก", None),
    (r"^ตะปู", r"^ตะปูตอกไม้", r"(^|\D)3\s*(นิ้ว|\")"),
    (r"ไม้อัด", r"^(แผ่น)?ไม้อัด(?!ซีเมนต์)", r"20\s*มม|2(\.0)?\s*ซม|เบอร์\s*20"),
    (r"^ไม้ยาง", r"^ไม้ยาง", r"(1\s*1/2|1½)\s*\"?\s*x\s*3"),
    (r"ยูคาลิปตัส|ไม้ค้ำยัน", r"ยูคาลิปตัส", r"3\s*นิ้ว\s*ยาว\s*3"),
    (r"^อิฐมอญ|อิฐก่อสร้างสามัญ", r"^อิฐ(มอญ|ก่อสร้างสามัญ)",
     r"7\s*x\s*16"),
    (r"^กระจกใส.*5", r"^กระจกใส.*(^|\D)5\s*มม", None),
    (r"^ปูนกาว", r"^ปูนกาว", None),
    (r"ยาแนว", r"^(ปูน)?ยาแนว", None),
    (r"^น้ำยาผสมปูน", r"^น้ำยาผสมปูน", None),
    (r"^กระเบื้องคอนกรีต", r"^กระเบื้องคอนกรีตมุงหลังคา", r"ซีแพค|cpac"),
    (r"^ครอบสันโค้ง", r"^ครอบสันโค้ง.*(คอนกรีต|ซีแพค|cpac)", None),
    (r"^เหล็กรูปพรรณ", r"^เหล็ก(ตัวซี|รางน้ำ|ฉาก)",
     r"100\s*x\s*50\s*x\s*20.*3\.2|3\.2.*100\s*x\s*50"),
    (r"^กระเบื้อง.*เซรามิ.*12", r"^กระเบื้อง.*(เซรามิ|ปูพื้น).*(12\s*x\s*12|30\s*x\s*30)",
     None),
    (r"^กระเบื้อง.*เซรามิ.*8", r"^กระเบื้อง.*(เซรามิ|ปูพื้น).*(8\s*x\s*8|20\s*x\s*20)",
     None),
]


def _strength(s: str):
    m = re.search(r"ผสมเสร็จ\D*?(\d{3})", s)
    return m.group(1) if m else None


def match(items, keys, units=None, cutoff: float = 0.8) -> dict:
    """``{key: (price per the key's unit, source_name)}``.

    Each BOQ key looks for its rows in the province table — rebar by size
    and grade, ready-mixed concrete by strength, the rest by the rules above
    (a preferred brand/size first), and lastly the same name — and only a
    row whose unit converts to the key's unit (``units[key]``) is used."""
    units = units or {}
    rows = [(str(n), str(u or ""), float(p), _norm(str(n)))
            for n, u, p in items if _num(p) is not None and float(p) > 0]
    out: dict = {}

    def take(key, cands, prefer=None):
        best = None
        for n, u, p, nn in cands:
            f = unit_factor(n, u, units.get(key, ""))
            if f is None:
                continue
            if prefer and re.search(prefer, nn):
                out[key] = (round(p * f, 4), n)
                return True
            if best is None:
                best = (round(p * f, 4), n)
        if best:
            out[key] = best
        return best is not None

    for key in dict.fromkeys(keys):
        nk = _norm(key)
        bar = _bar(key)
        if bar:
            cands = [r for r in rows if _bar(r[0]) == bar]
            take(key, cands, r"sd\.?\s*40|sr\.?\s*24")
            continue
        rule = next((r for r in _RULES if re.search(r[0], nk)), None)
        if rule:
            if rule[1] is None:                    # ready-mixed by strength
                st = _strength(nk)
                cands = [r for r in rows if r[3].startswith("คอนกรีต")
                         and "ผสมเสร็จ" in r[3] and _strength(r[3]) == st]
                take(key, cands, r"ซีแพค|cpac")
            else:
                cands = [r for r in rows if re.search(rule[1], r[3])]
                take(key, cands, rule[2])
            continue
        same = [r for r in rows if r[3] == nk]
        if same:
            take(key, same)
            continue
        scored = [(difflib.SequenceMatcher(None, r[3], nk).ratio(), r)
                  for r in rows]
        scored = [t for t in scored if t[0] >= cutoff]
        if scored:
            take(key, [max(scored, key=lambda t: t[0])[1]])
    return out


def coverage(prices: dict, need) -> tuple[int, list[str]]:
    """How many of the needed keys are priced, and the missing ones."""
    need = list(need)
    missing = [k for k in need if not (_num(prices.get(k)) or 0) > 0]
    return len(need) - len(missing), missing


# ---------------------------------------------------------------------------
# Online: MOC Open Data API (run on the user's computer)
# ---------------------------------------------------------------------------

class FetchError(Exception):
    pass


def _records(payload):
    if isinstance(payload, dict):
        for k in ("data", "result", "results", "items", "records"):
            if isinstance(payload.get(k), list):
                return payload[k]
        return []
    return payload if isinstance(payload, list) else []


def _field(rec, *names):
    for n in names:
        if n in rec and rec[n] not in (None, ""):
            return rec[n]
    low = {str(k).lower(): v for k, v in rec.items()}
    for n in names:
        if low.get(n.lower()) not in (None, ""):
            return low[n.lower()]
    return None


def latest_items(records) -> tuple[list, str]:
    """``([(name, unit, price)], "ก.ย. 2569")`` — each item's newest price."""
    best: dict = {}
    for rec in _records(records):
        if not isinstance(rec, dict):
            continue
        name = _field(rec, "com_name_th", "commodity_name_th", "com_name",
                      "product_name", "name_th", "name")
        price = _num(_field(rec, "price", "price_value", "avg_price", "value"))
        if not name or price is None or price <= 0:
            continue
        y = int(_num(_field(rec, "year", "yr")) or 0)
        m = int(_num(_field(rec, "month", "mn")) or 0)
        unit = str(_field(rec, "units", "unit", "unit_th") or "")
        code = str(_field(rec, "com_code", "code") or name)
        if code not in best or (y, m) > best[code][0]:
            best[code] = ((y, m), (re.sub(r"\s+", " ", str(name)).strip(),
                                   unit, price))
    if not best:
        return [], ""
    ym = max(v[0] for v in best.values())
    items = [v[1] for v in best.values()]
    return items, (month_label(*ym) if ym[0] else "")


def fetch_online(province: str, today=None, opener=None,
                 timeout: float = 120.0, progress=None,
                 years_back: int = 3) -> tuple[list, str, str]:
    """Download the province's prices for the latest announced month from
    the MOC Open Data API.

    The API answers a whole year at a time; this year is asked first and,
    when it holds nothing yet (early in the year, or not announced), the
    year before, and so on — the newest month found is the one used.

    Returns ``(items, month, url)``; raises :class:`FetchError` with a Thai
    message the panel shows as is.  ``opener(url, timeout)`` → bytes is for
    tests; ``progress(text)`` reports each try; ``WANIC_OFFLINE`` turns the
    network off."""
    if os.environ.get("WANIC_OFFLINE"):
        raise FetchError("ปิดการเชื่อมต่อออนไลน์ไว้ (WANIC_OFFLINE)")
    code = CODES.get(province)
    if not code:
        raise FetchError(f"ไม่รู้จักรหัสจังหวัด «{province}»")
    if opener is None:
        def opener(url, timeout):
            import urllib.request
            req = urllib.request.Request(url, headers={
                "User-Agent": "WANICNSURVEY", "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
    say = progress or (lambda _t: None)
    d = today or datetime.date.today()
    errors: list = []
    paths = ["csi-product-indexes", "csi-indexes"]
    for y in range(d.year, d.year - years_back, -1):
        for path in list(paths):
            url = (f"{API}/{path}?province_code={code}"
                   f"&from_year={y}&to_year={y}")
            say(f"กำลังขอราคาจังหวัด{province} ปี {y + 543} …")
            try:
                raw = opener(url, timeout)
                payload = json.loads(raw.decode("utf-8-sig"))
            except Exception as e:                      # noqa: BLE001
                errors.append(f"{path} ปี {y + 543}: {e}")
                continue
            # This path answers: keep using it for the earlier years.
            paths = [path]
            items, month = latest_items(payload)
            if items:
                return items, month, url
            errors.append(f"ปี {y + 543}: ยังไม่มีราคาประกาศ")
            break
        if not any("ยังไม่มีราคาประกาศ" in e for e in errors[-1:]) and \
                len(paths) > 1:
            break                    # neither path answered: stop trying
    detail = "; ".join(errors) or "ไม่มีข้อมูลราคาของจังหวัดนี้"
    raise FetchError("ดึงราคาจากกระทรวงพาณิชย์ไม่สำเร็จ — " + detail)
