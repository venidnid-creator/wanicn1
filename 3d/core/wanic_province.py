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
PRICE_SITE = "https://www.price.moc.go.th"

_TH_MONTHS = ["ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.", "ก.ค.",
              "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค."]


def region_of(province: str) -> str:
    for r, ps in REGIONS.items():
        if province in ps:
            return r
    return ""


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
              source: str = "", src: dict | None = None) -> dict:
    """Write the province's book; ``src`` says where each price came from
    (``พาณิชย์`` / ``กรอกเอง`` / ``ตัวอย่าง``)."""
    os.makedirs(book_dir(), exist_ok=True)
    book = {"province": province, "month": month,
            "source": source or f"สำนักงานพาณิชย์จังหวัด{province}",
            "updated": datetime.date.today().isoformat(),
            "prices": {k: float(v) for k, v in prices.items()
                       if _num(v) is not None and float(v) > 0}}
    book["src"] = {k: (src or {}).get(k, "พาณิชย์") for k in book["prices"]}
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


def parse_rows(rows) -> list[tuple[str, str, float]]:
    """``[(name, unit, price)]`` from table rows of any layout.

    The name is the longest text cell, the unit a cell that looks like one,
    and the price the last number on the row (the commerce office puts the
    price after code, name and unit; a row with ``ราคาเดือนก่อน`` and
    ``ราคาเดือนนี้`` gives this month)."""
    out = []
    for row in rows:
        cells = [str(c if c is not None else "").strip() for c in row]
        nums = [(i, _num(c)) for i, c in enumerate(cells)]
        nums = [(i, n) for i, n in nums if n is not None]
        texts = [(i, c) for i, c in enumerate(cells)
                 if c and _num(c) is None]
        if not nums or not texts:
            continue
        unit = next((c for _i, c in texts if _is_unit(c)), "")
        names = [(i, c) for i, c in texts if not _is_unit(c)]
        if not names:
            continue
        ni, name = max(names, key=lambda t: len(t[1]))
        after = [n for i, n in nums if i > ni]
        price = (after or [nums[-1][1]])[-1]
        if price <= 0 or len(name) < 2:
            continue
        out.append((re.sub(r"\s+", " ", name), unit, price))
    return out


def rows_from_text(text: str) -> list[list[str]]:
    """Rows of pasted text (tabs from a web page / Excel) or CSV."""
    text = text.lstrip("﻿")
    if "\t" in text:
        return [ln.split("\t") for ln in text.splitlines() if ln.strip()]
    return [r for r in csv.reader(io.StringIO(text)) if any(r)]


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
    with open(path, "rb") as fh:
        data = fh.read()
    if data[:2] == b"PK":
        return parse_rows(rows_from_xlsx(data))
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
    return parse_rows(rows_from_text(text))


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
    if "เหล็ก" not in n or not re.search(r"เส้น|sr|sd|ข้ออ้อย|กลม", n):
        return None
    m = re.search(r"(?:ø|ขนาด|dia\.?|⌀)?\s*(\d{1,2})\s*(?:มม|mm)", n)
    if not m:
        return None
    d = int(m.group(1))
    deformed = "ข้ออ้อย" in n or "sd" in n
    return f"{'DB' if deformed else 'RB'}{d}"


#: Words the commerce office uses → the BOQ key (checked before fuzzy).
_RULES = [
    (r"ทรายหยาบ", "ทรายหยาบ"), (r"ทรายละเอียด", "ทรายละเอียด"),
    (r"ทรายถม|ดินถม.*ทราย", "ทรายถม"),
    (r"หิน.*(1\s*-\s*2|1/2|เบอร์ 1)|หินย่อย", "หินเบอร์ 1-2"),
    (r"ซิลิก้า|silica", "ปูนซีเมนต์ผสม (Silica Cement)"),
    (r"ปูนซีเมนต์ปอร์ตแลนด์|ปอร์ตแลนด์|ไฮดรอลิก",
     "ปูนซีเมนต์ปอร์ตแลนด์ (มอก. 15-2562) หรือปูนซีเมนต์ไฮดรอลิก "
     "(มอก. 2594-2567)"),
    (r"ปูนซีเมนต์ผสม", "ปูนซีเมนต์ผสม (มอก. 80/2566)"),
    (r"คอนกรีตผสมเสร็จ.*240", "คอนกรีตผสมเสร็จ 240 กก./ตร.ซม. (ลูกบาศก์)"),
    (r"ลวดผูกเหล็ก", "ลวดผูกเหล็ก"),
    (r"ไม้อัด.*20\s*มม", "ไม้อัดดำ หนา 20 มม."),
    (r"ตะปู.*3", "ตะปูตอกไม้ 3\""),
    (r"อิฐมอญ|อิฐก่อสร้างสามัญ",
     "อิฐมอญ (อิฐก่อสร้างสามัญ) ขนาด 7 x 16 x 3.5 ซม."),
]


def match(items, keys, cutoff: float = 0.62) -> dict:
    """``{key: (price, source_name)}`` for the BOQ keys the table prices.

    Rebar by size and grade, a few fixed words, then the closest name."""
    keys = list(dict.fromkeys(keys))
    nk = {k: _norm(k) for k in keys}
    out: dict = {}
    for name, _unit, price in items:
        key = None
        bar = _bar(name)
        if bar and bar in nk:
            key = bar
        if key is None:
            n = _norm(name)
            for pat, k in _RULES:
                if k in nk and re.search(pat, n):
                    key = k
                    break
        if key is None:
            n = _norm(name)
            if n in nk.values():
                key = next(k for k, v in nk.items() if v == n)
            else:
                best, score = None, 0.0
                for k, v in nk.items():
                    s = difflib.SequenceMatcher(None, n, v).ratio()
                    if s > score:
                        best, score = k, s
                if score >= cutoff:
                    key = best
        if key is not None and key not in out:
            out[key] = (float(price), name)
    return out


def coverage(prices: dict, need) -> tuple[int, list[str]]:
    """How many of the needed keys are priced, and the missing ones."""
    need = list(need)
    missing = [k for k in need if not (_num(prices.get(k)) or 0) > 0]
    return len(need) - len(missing), missing
