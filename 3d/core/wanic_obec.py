# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
"""บัญชีราคาค่าวัสดุและค่าแรงงาน สพฐ. — the second price source, for สพฐ. jobs only.

The owner's order (ง3/ง6): labour from กรมบัญชีกลาง (ว480) first, material
from สำนักงานพาณิชย์จังหวัด first; only where those have no price, and only
in a job of สำนักงานคณะกรรมการการศึกษาขั้นพื้นฐาน (the book itself says it is
for สพฐ. schools and offices only), the สพฐ. book fills the empty items.
Every price it fills says so in หมายเหตุ (code + item) and stays editable.

The attached book (PDF / CSV / text) is read once into items and kept in the
user's folder until it is replaced or deleted (``store_file``), so every
สพฐ. job finds it again; a job turns it on with ``data["obec"] = True``.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

NAME = "บัญชีราคาค่าวัสดุและค่าแรงงาน สพฐ."
SRC = "สพฐ."                                    # price_src / labour_src value
PRODUCT = "WANICNSURVEY"

# Thai marks above/below the line: the PDF text puts them out of place
# («ไมอ้ดั» for «ไม้อัด»), so they are left out when names are compared.
_MARKS = re.compile("[ัิ-ฺ็-๎\\s]")
_NUM = r"(?:\d[\d,]*(?:\.\d+)?|-)"
_CODE = re.compile(r"^\s*([A-Z]\d{4,5})\s+(.+?)\s*$")


def norm(s) -> str:
    t = str(s or "").replace("ำ", "า").replace("×", "x").replace("X", "x")
    t = t.replace("”", '"').replace("″", '"').replace("½", "1/2")
    return _MARKS.sub("", t)


_UNIT_ALIAS = {"เมตร": "ม", "ม": "ม", "ตน": "ตน", "ตรม": "ตรม", "ลบม": "ลบม",
               "กก": "กก", "กโลกรม": "กก", "ชด": "ชด", "แผน": "แผน",
               "ตรฟ": "ตรฟ", "ลบฟ": "ลบฟ", "ตว": "ตว", "อน": "ตว"}


#: the book's units (marks left out, no dots): a word before two numbers
#: that is not one of these is part of the name («ยาว 3.00 - 3.50»)
UNITS = {"ม", "ตน", "ตรม", "ลบม", "กก", "ชด", "แผน", "ตรฟ", "ลบฟ", "ตว",
         "ตน", "เสน", "ถง", "กอน", "หลา", "ลง", "กลอง", "จด", "บอ", "ทอน",
         "มวน", "แกลลอน", "งาน", "เครอง", "ต", "ชน", "ค", "ใบ", "ดวง", "หลง",
         "บาน", "ลตร", "ลก", "ท", "หลอด", "เกลด", "ฟต", "แผง", "หลม", "ทาง", "วง", "ขด", "ปบ",
         "กระปอง", "แทง", "ปาย", "ระบบ", "หอง", "ตารางเมตร", "ลกบาศกเมตร"}


def unit_key(u) -> str:
    k = norm(u).replace(".", "")
    return _UNIT_ALIAS.get(k, k)


def _num(tok):
    if tok is None or tok.strip() in ("-", ""):
        return None
    try:
        return float(tok.replace(",", ""))
    except ValueError:
        return None


def parse_lines(lines) -> list:
    """``[{"code", "desc", "unit", "mat", "lab", "note"}]`` from the book's
    lines «A4005 คอนกรีตผสมเสร็จ 240 … ลบ.ม. 2,470 - หมายเหตุ». A labour
    cell «รวมค่าแรง…» means the material price already holds the labour."""
    out, seen = [], set()
    isnum = re.compile(_NUM + "$").match
    for raw in lines:
        m = _CODE.match(str(raw))
        if not m:
            continue
        code, rest = m.groups()
        if code in seen:
            continue
        t = rest.split()
        for i in range(1, len(t) - 1):
            # «… หน่วย ค่าวัสดุ [ค่าแรง] [หมายเหตุ]»: the first known unit
            # followed by a number (a word like «ยาว 3.00» is the name)
            if unit_key(t[i]) not in UNITS or not isnum(t[i + 1]):
                continue
            mat, j, lab = _num(t[i + 1]), i + 2, None
            if j < len(t) and isnum(t[j]):
                lab, j = _num(t[j]), j + 1
            note = " ".join(t[j:]).strip(" .")       # «รวมค่าแรง…» stays here
            if mat is None and lab is None:
                break
            out.append({"code": code, "desc": " ".join(t[:i]), "unit": t[i],
                        "mat": mat, "lab": lab, "note": note})
            seen.add(code)
            break
    return out


def parse_text(text: str) -> list:
    return parse_lines(str(text or "").splitlines())


def read_pdf(path) -> str:
    """The PDF's text, line by line (QtPdf: nothing to install)."""
    from PySide6.QtCore import QCoreApplication
    from PySide6.QtPdf import QPdfDocument
    _app = QCoreApplication.instance()
    doc = QPdfDocument()
    doc.load(str(path))
    if doc.pageCount() <= 0:
        raise ValueError("เปิดไฟล์ PDF ไม่ได้")
    return "\n".join(doc.getAllText(i).text() for i in range(doc.pageCount()))


def read_file(path) -> list:
    """Items from the attached list: PDF, or CSV/TXT with the columns
    รหัส, รายการ, หน่วย, ค่าวัสดุ, ค่าแรง (หมายเหตุ)."""
    p = Path(path)
    ext = p.suffix.lower()
    if ext == ".pdf":
        return parse_text(read_pdf(p))
    raw = p.read_bytes()
    for enc in ("utf-8-sig", "cp874"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise ValueError("อ่านไฟล์ไม่ได้ (ต้องเป็น UTF-8 หรือ TIS-620)")
    if ext == ".csv":
        import csv
        import io
        items = []
        for row in csv.reader(io.StringIO(text)):
            row = [c.strip() for c in row] + [""] * 6
            if not re.fullmatch(r"[A-Z]\d{4,5}", row[0]):
                continue
            mat, lab = _num(row[3]), _num(row[4])
            if mat is None and lab is None:
                continue
            items.append({"code": row[0], "desc": row[1], "unit": row[2],
                          "mat": mat, "lab": lab, "note": row[5]})
        return items
    return parse_text(text)


# --------------------------------------------------------------------------
# the attached book, kept in the user's folder until replaced or deleted

def store_file() -> Path:
    env = os.environ.get("WANIC_OBEC_FILE")
    if env:
        return Path(env)
    base = os.environ.get("APPDATA") or os.path.join(Path.home(), ".config")
    return Path(base) / PRODUCT / "obec_prices.json"


def load_store() -> dict:
    """``{"name", "items"}`` of the attached book, or {} when none."""
    try:
        d = json.loads(store_file().read_text(encoding="utf-8"))
        return d if isinstance(d, dict) and d.get("items") else {}
    except (OSError, ValueError):
        return {}


def save_store(items, name: str) -> dict:
    d = {"name": str(name), "items": list(items)}
    f = store_file()
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    return d


def clear_store():
    try:
        store_file().unlink()
    except FileNotFoundError:
        pass


# --------------------------------------------------------------------------
# finding the book's item for a price key / a BOQ line

#: price keys whose book item is in another unit, or named apart:
#: key → (every piece the item's name holds, the book's unit, × to our unit)
KEY_RULES = {
    "ปูนซีเมนต์ผสม (มอก. 80/2566)": (["ปนซเมนตผสม(50"], "ถุง", 1 / 50),
    "ปูนซีเมนต์ผสม (Silica Cement)": (["ปนซเมนตผสมกอฉาบ"], "ถุง", 1 / 50),
    "ปูนซีเมนต์ปอร์ตแลนด์ (มอก. 15-2562) หรือปูนซีเมนต์ไฮดรอลิก (มอก. 2594-2567)":
        (["ปนซเมนตปอรตแลนด(50"], "ถุง", 1 / 50),
    "หินเบอร์ 1-2": (["หนยอยเบอร2"], "ลบ.ม.", 1.0),
    "คอนกรีตผสมเสร็จ 240 กก./ตร.ซม. (ลูกบาศก์)": (["คอนกรตผสมเสรจ240"], "ลบ.ม.", 1.0),
    "ลวดผูกเหล็ก": (["ลวดผกเหลก"], "กก.", 1.0),
    'ไม้ยาง 1½"×3"': (["ไมคราว"], "ลบ.ฟ.", 1.0),
    'ตะปูตอกไม้ 3"': (["ตะปขนาดตางๆ"], "กก.", 1.0),
    'ไม้ค้ำยันยูคาลิปตัส ศก. 3" ยาว 3 ม.': (["Ø3นวยาว3.00"], "ต้น", 1.0),
    "กระจกใส 5 มม.": (["กระจกแผนใสหนา5มม"], "ตร.ฟ.", 1.0),
    "ไม้อัดดำ หนา 20 มม.": (["ไมอด", "20มม"], "แผ่น", 1.0),
    "ปิดนก P.V.C สำเร็จรูป": (["ปดกนนก"], "ม.", 1.0),
    # the concrete-tile caps (the ลอนคู่ ones are named in full, these not)
    "ครอบสันโค้ง/ครอบตะเข้สัน กระเบื้องคอนกรีต": (["=ครอบสนโคง"], "แผ่น", 1.0),
    "ครอบโค้งสามทาง (กระเบื้องคอนกรีต)": (["=ครอบโคง3ทาง"], "แผ่น", 1.0),
    "ครอบโค้งสี่ทาง (กระเบื้องคอนกรีต)": (["=ครอบโคง4ทาง"], "แผ่น", 1.0),
}
for _d in (6, 9, 12, 15, 19, 25):
    KEY_RULES[f"RB{_d}"] = ([f"SR.24ขนาดRB{_d}มม"], "ตัน", 1 / 1000)
for _d in (12, 16, 20, 25, 28, 32):
    KEY_RULES[f"DB{_d}"] = ([f"ขนาดDB{_d}มม"], "ตัน", 1 / 1000)


def _find_rule(items, pieces, unit):
    u = unit_key(unit)
    for it in items:
        n = norm(it["desc"])
        if unit_key(it["unit"]) == u and all(
                (n == p[1:]) if p.startswith("=") else (p in n) for p in pieces) \
                and it.get("mat"):
            return it
    return None


def _nums(s) -> set:
    return {x.rstrip("0").rstrip(".") if "." in x else x
            for x in re.findall(r"\d+(?:\.\d+)?", str(s or "").replace(",", ""))}


def _grams(s) -> set:
    return {s[i:i + 2] for i in range(len(s) - 1)}


def _clean(desc) -> str:
    d = str(desc or "").split(" — ")[0]
    return re.sub(r"\(รวม[^)]*\)|พร้อม\S*", "", d)


def similarity(a, b) -> float:
    """0…1: how alike two item names are (character pairs). Not alike at
    all when the first word of one is not in the other (ฝ้า… is not
    ผนัง…) or the numbers disagree (240 กก. is not 180 กก., Ø ½" not Ø 1")."""
    ca, cb = _clean(a), _clean(b)
    na, nb = norm(ca), norm(cb)
    ga, gb = _grams(na), _grams(nb)
    if not ga or not gb:
        return 0.0
    wa = norm((ca.split() or [""])[0])
    wb = norm((cb.split() or [""])[0])
    if not ((len(wa) >= 3 and wa in nb) or (len(wb) >= 3 and wb in na)):
        return 0.0
    xa, xb = _nums(ca), _nums(cb)
    if xa and xb and not (xa & xb):
        return 0.0
    s = 2 * len(ga & gb) / (len(ga) + len(gb))
    return s + (0.1 if xa & xb else 0.0)


THRESHOLD = 0.55


def match(desc, unit, items, side="mat"):
    """The book's item most like ``desc`` in the same unit that has a
    price on ``side`` (mat / lab), or None when nothing is near enough."""
    u = unit_key(unit)
    best, score = None, THRESHOLD
    for it in items:
        if unit_key(it["unit"]) != u or not it.get(side):
            continue
        s = similarity(desc, it["desc"])
        if s > score:
            best, score = it, s
    return best


def key_price(key, unit, items):
    """``(price per our unit, item)`` for a price key, or (0, None)."""
    rule = KEY_RULES.get(key)
    if rule:
        it = _find_rule(items, rule[0], rule[1])
        return (round(it["mat"] * rule[2], 4), it) if it else (0.0, None)
    it = match(key, unit, items, "mat")
    return (float(it["mat"]), it) if it else (0.0, None)


def item_text(it) -> str:
    return f"{it['code']} {it['desc']}"


def note_of(it, side="mat") -> str:
    what = "ราคาวัสดุ" if side == "mat" else "ค่าแรง"
    return f"ใช้{what} สพฐ. ({item_text(it)})"


def fill(data, result, items) -> dict:
    """Fill the job's EMPTY prices from the book (สพฐ. jobs only): the
    material keys the bill needs and the labour of the lines that have no
    ว480 code. Writes ``prices``/``price_src``/``price_item`` and
    ``labour``/``labour_src`` into ``data``; returns what it filled
    ``{"mat": n, "lab": n}``. Nothing for a job that is not สพฐ.'s."""
    if not (data or {}).get("obec") or not items:
        return {"mat": 0, "lab": 0}
    prices = dict(data.get("prices") or {})
    src = dict(data.get("price_src") or {})
    item = dict(data.get("price_item") or {})
    labour = dict(data.get("labour") or {})
    lsrc = dict(data.get("labour_src") or {})
    from core import wanic_std2569 as S
    nm = nl = 0
    need = dict((result or {}).get("need") or {})
    for ln in (result or {}).get("lines") or []:
        if ln.get("mat_key"):
            need.setdefault(ln["mat_key"], ln["unit"])
    for k, u in need.items():
        if _has(prices.get(k)):
            continue                                # พาณิชย์จังหวัด / typed in: first
        v, it = key_price(k, S.price_unit(k) or u, items)
        if v > 0:
            prices[k], src[k], item[k] = v, SRC, item_text(it)
            nm += 1
    from core import wanic_quantities as Q
    for ln in (result or {}).get("lines") or []:
        code = ln.get("lab_code") or ""
        if not code.startswith(Q.OWN_LAB) or _has(labour.get(code)):
            continue                                # ว480 (กรมบัญชีกลาง) first
        it = match(ln["desc"], ln["unit"], items, "lab") or \
            match(code[len(Q.OWN_LAB):], ln["unit"], items, "lab")
        if it:
            labour[code], lsrc[code] = float(it["lab"]), item_text(it)
            nl += 1
    data["prices"], data["price_src"], data["price_item"] = prices, src, item
    data["labour"], data["labour_src"] = labour, lsrc
    return {"mat": nm, "lab": nl}


def strip(data) -> int:
    """Take every สพฐ. price out of a job (it is not สพฐ.'s any more)."""
    n = 0
    prices = dict(data.get("prices") or {})
    src = dict(data.get("price_src") or {})
    item = dict(data.get("price_item") or {})
    for k in [k for k, v in src.items() if v == SRC]:
        prices.pop(k, None), src.pop(k, None), item.pop(k, None)
        n += 1
    labour = dict(data.get("labour") or {})
    for k in list((data.get("labour_src") or {})):
        labour.pop(k, None)
        n += 1
    data["prices"], data["price_src"], data["price_item"] = prices, src, item
    data["labour"], data["labour_src"] = labour, {}
    return n


def _has(v) -> bool:
    try:
        return float(v) > 0
    except (TypeError, ValueError):
        return False
