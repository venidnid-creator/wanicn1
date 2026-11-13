# SPDX-License-Identifier: GPL-3.0-or-later
"""แปลง «รายงานประมาณการรายจ่าย» ในข้อบัญญัติงบประมาณ (PDF จากระบบ e-LAAS) เป็นตาราง CSV.

ใช้กับเครื่องพัฒนา (ต้องมี ``pdftotext`` ของ poppler)::

    python tools/ordinance_pdf.py ข้อบัญญัติ.pdf ออก.csv [หน้าเริ่ม หน้าสุดท้าย]

ระดับรายการดูจากระยะย่อหน้าของบรรทัดในรายงาน:
แผนงาน › งาน › งบ › หมวด › ประเภท › รายการ — บรรทัด «รวม…» ข้ามไป
คอลัมน์ตัวเลข: รายจ่ายจริงปี N-3, N-2, ประมาณการปี N-1, ยอดต่าง (%), ประมาณการปี N
"""
from __future__ import annotations

import csv
import html
import re
import subprocess
import sys
import tempfile
from pathlib import Path

NUM = re.compile(r"^-?[\d,]+(\.\d+)?$")
TITLE = "รายงานประมาณการรายจ่าย"


# รหัสตำแหน่งพิเศษของฟอนต์ไทยรุ่นเก่า (Private Use Area) → อักษรไทยมาตรฐาน
PUA = {0xF700: "ฐ", 0xF701: "ิ", 0xF702: "ี", 0xF703: "ึ", 0xF704: "ื", 0xF705: "่", 0xF706: "้",
       0xF707: "๊", 0xF708: "๋", 0xF709: "์", 0xF70A: "่", 0xF70B: "้", 0xF70C: "๊", 0xF70D: "๋",
       0xF70E: "์", 0xF70F: "ญ", 0xF710: "ั", 0xF711: "ํ", 0xF712: "็", 0xF713: "่", 0xF714: "้",
       0xF715: "๊", 0xF716: "๋", 0xF717: "์", 0xF718: "ุ", 0xF719: "ู", 0xF71A: "ฺ"}


def fix_thai(t: str) -> str:
    t = t.translate(PUA).replace("\u0e4d\u0e32", "\u0e33").replace("\u0e4d\u0e48\u0e32", "\u0e48\u0e33")
    return t.replace("\u0e4d\u0e49\u0e32", "\u0e49\u0e33")


_CACHE: dict = {}


def words(pdf: str, first=None, last=None):
    key = (pdf, first, last)
    if key in _CACHE:
        yield from _CACHE[key]
        return
    pages = list(_words(pdf, first, last))
    _CACHE[key] = pages
    yield from pages


def _words(pdf: str, first=None, last=None):
    with tempfile.TemporaryDirectory() as d:
        out = Path(d) / "bb.html"
        cmd = ["pdftotext", "-bbox-layout"]
        if first:
            cmd += ["-f", str(first)]
        if last:
            cmd += ["-l", str(last)]
        subprocess.run(cmd + [pdf, str(out)], check=True)
        s = out.read_text(encoding="utf-8")
    pages = re.findall(r"<page.*?</page>", s, re.S)
    for pi, page in enumerate(pages, first or 1):
        rows: dict[int, list] = {}
        for w in re.finditer(r'<word xMin="([\d.]+)" yMin="([\d.]+)"[^>]*>([^<]*)</word>', page):
            rows.setdefault(round(float(w.group(2))), []).append(
                (float(w.group(1)), fix_thai(html.unescape(w.group(3)))))
        yield pi, [(y, sorted(rows[y])) for y in sorted(rows)]


def column(x: float) -> int | None:
    """Which number column a word at *x* belongs to (0..4)."""
    for i, edge in enumerate((480, 580, 650, 730)):
        if x < edge:
            return i
    return 4


def parse(pdf: str, first=None, last=None) -> tuple[list[dict], dict]:
    known = [47, 57, 67, 77, 87, 98]
    path = ["", "", "", "", ""]
    items: list[dict] = []
    years = None
    in_section = first is not None
    pending: list[str] = []      # text rows waiting for their numbers
    pend_y = None
    last_item = None
    last_num_y = None
    for pi, rows in words(pdf, first, last):
        flat = " ".join(t for _, ws in rows for _, t in ws)
        if TITLE in flat and "รายละเอียด" not in flat:
            in_section = True
        elif "รายงานรายละเอียดประมาณการรายจ่าย" in flat and in_section:
            break
        if not in_section:
            continue
        if years is None:
            ys = re.findall(r"ปี (25\d\d)", flat)
            if len(ys) >= 4:
                years = [int(y) for y in ys[:4]]
        pending, pend_y, last_item, last_num_y = [], None, None, None
        for y, ws in rows:
            text = [(x, t) for x, t in ws if x < 395]
            nums = {}
            for x, t in ws:
                if x >= 395 and NUM.match(t.replace("%", "")):
                    nums[column(x)] = float(t.replace(",", ""))
            x0 = text[0][0] if text else None
            name = " ".join(t for _, t in text).strip()
            if text and (name.startswith("รวม") or x0 > 120):
                continue                       # subtotal, page header, footer
            lvl = None
            if x0 is not None:
                lvl = min(range(len(known)), key=lambda i: abs(known[i] - x0))
                if abs(known[lvl] - x0) > 4:
                    continue
            if text and not nums:
                # continuation of a wrapped name: close to the previous row, same level
                if last_item is not None and last_num_y is not None and y - last_num_y < 20 \
                        and lvl == last_item["_lvl"]:
                    last_item["รายการ"] += name
                    if last_item["_type_is_self"]:
                        last_item["ประเภท"] = last_item["รายการ"]
                    last_num_y = None
                    continue
                if pending and pend_y is not None and y - pend_y < 20 and lvl == pending[0]:
                    pending[1] += name    # a header or item wrapped over two lines
                    pend_y = y
                    if pending[0] == 4:
                        path[4] = pending[1]
                    continue
                # a header (or the first line of an item whose numbers come next)
                pending = [lvl, name]
                pend_y = y
                if lvl < 4:
                    path[lvl] = name
                    for k in range(lvl + 1, 5):
                        path[k] = ""
                    pending = []
                elif lvl == 4:
                    path[4] = name
                last_item = None
                continue
            if nums and 4 in nums:
                if text:
                    lv, nm = lvl, name
                    if pending and pending[0] == lvl and pend_y is not None and y - pend_y < 20:
                        nm = pending[1] + name          # a name over three lines: numbers on the middle one
                        if lvl == 5 and path[4] == pending[1]:
                            path[4] = ""
                elif pending:
                    lv, nm = pending
                else:
                    continue
                if lv < 4:
                    continue
                self_type = lv == 4
                if self_type:
                    path[4] = nm
                it = {"แผนงาน": path[0], "งาน": path[1], "งบ": path[2], "หมวด": path[3],
                      "ประเภท": path[4] or nm, "รายการ": nm,
                      "y0": nums.get(0, 0.0), "y1": nums.get(1, 0.0), "y2": nums.get(2, 0.0),
                      "amount": nums[4], "_lvl": lv, "_type_is_self": self_type, "หน้า": pi,
                      "_notype": lv == 5 and not path[4], "หมายเหตุ": ""}
                items.append(it)
                last_item = it
                last_num_y = y
                pending, pend_y = [], None
    # บางหน้าในต้นฉบับไม่มีหัว «ประเภท» — เติมจากรายการชื่อเดียวกันในหมวดเดียวกัน
    known_type = {(it["หมวด"], it["รายการ"]): it["ประเภท"] for it in items if not it["_notype"]
                  and it["ประเภท"] != it["รายการ"]}
    for it in items:
        if it["_notype"]:
            t = known_type.get((it["หมวด"], it["รายการ"]))
            if not t and it["หมวด"] == "ค่าใช้สอย" and it["รายการ"].startswith("โครงการ"):
                t = "รายจ่ายเกี่ยวเนื่องกับการปฏิบัติราชการที่ไม่เข้าลักษณะรายจ่ายงบรายจ่ายอื่น ๆ"
            it["ประเภท"] = t or "(ไม่ระบุประเภทในต้นฉบับ)"
            it["หมายเหตุ"] = f"ประเภทเติมโดยโปรแกรม (ต้นฉบับหน้า {it['หน้า']} ไม่มีหัวประเภท)"
    return items, dict(years=years or [])


DETAIL_TITLE = "รายงานรายละเอียดประมาณการรายจ่าย"
AMOUNT = re.compile(r"([\d,]+)\s*บาท")
MARKS = re.compile(r"[\u0e31\u0e34-\u0e3a\u0e47-\u0e4e\s]")


def skeleton(t: str) -> str:
    """Consonants and leading vowels only — survives broken tone marks and spacing."""
    return MARKS.sub("", fix_thai(t)).replace("ำ", "า")


def _clusters(rows, tol=4.0):
    """Merge rows whose y differ by ≤ tol (amount and name sit 1–2 pt apart)."""
    out = []
    for y, ws in rows:
        if out and y - out[-1][0] <= tol:
            out[-1][1].extend(ws)
        else:
            out.append([y, list(ws)])
    return [(y, sorted(ws)) for y, ws in out]


def parse_details(pdf: str, first=None, last=None) -> list[dict]:
    """คำชี้แจงจาก «รายงานรายละเอียดประมาณการรายจ่าย»: [{name, amount, text, page}]."""
    entries: list[dict] = []
    started = False
    cur = None
    name_open = False
    for pi, rows in words(pdf, first, last):
        rows = _clusters(rows)
        top = " ".join(t for y, ws in rows if y < 110 for _, t in ws)
        if DETAIL_TITLE in top and "สารบัญ" not in top:
            started = True
        if not started:
            continue
        for y, ws in rows:
            if y < 40:                          # page number
                continue
            text_w = [(x, t) for x, t in ws if x < 400]
            line = " ".join(t for _, t in ws)
            x0 = ws[0][0]
            right = " ".join(t for x, t in ws if x >= 400)     # the amount column of a header
            m = AMOUNT.search(right)
            if "จำนวน" in right and m:
                name = " ".join(t for x, t in text_w if t != "จำนวน").strip()
                cur = dict(name=name, amount=float(m.group(1).replace(",", "")), text=[], page=pi,
                           x=text_w[0][0] if text_w else x0)
                entries.append(cur)
                name_open = True
                continue
            if re.search(r"รวม\s+[\d,]+\s*บาท", right) or (x0 > 200 and line.startswith("แผนงาน")) \
                    or line.startswith("ประมาณการรายจ่ายรวมทั้งสิ้น"):
                cur, name_open = None, False    # a sum line or a new plan: the item is over
                continue
            if cur is None:
                continue
            if name_open and abs(x0 - cur["x"]) < 3 and x0 < 150 and not cur["text"]:
                cur["name"] += line            # the name wrapped onto a second line
                continue
            name_open = False
            if x0 < 150:                        # a type header between items
                cur = None
                continue
            cur["text"].append(line.strip())
    for e in entries:
        e["text"] = reflow(e["text"])
        del e["x"]
    return entries


THAI = re.compile(r"[\u0e00-\u0e7f]")
PARA = re.compile(r"^(-|\(\d+\)|•)")


def reflow(lines: list[str]) -> str:
    """Join the PDF's wrapped lines; keep a new line before «-», «(1)», «1.» items."""
    out = ""
    for ln in (x.strip() for x in lines):
        if not ln:
            continue
        if not out:
            out = ln
        elif PARA.match(ln):
            out += "\n" + ln
        elif THAI.match(out[-1]) and THAI.match(ln[0]):
            out += ln                       # Thai wraps inside a phrase: no space
        else:
            out += " " + ln
    return out


def attach_details(items: list[dict], details: list[dict]) -> int:
    """Give each item its คำชี้แจง: same amount, same name skeleton, in document order."""
    ptr = 0
    n = 0
    pool = [it for it in items if it["amount"] > 0]
    for d in details:
        dk = skeleton(d["name"])
        for j in range(ptr, min(len(pool), ptr + 60)):
            it = pool[j]
            ik = skeleton(it["รายการ"])
            if abs(it["amount"] - d["amount"]) < 0.5 and (ik.startswith(dk[:12]) or dk.startswith(ik[:12])):
                text = d["text"]
                # a detail block may repeat the item name on its first line
                first = text.split("\n", 1)[0] if text else ""
                if first and skeleton(first) and (ik.startswith(skeleton(first)) or skeleton(first) == ik):
                    text = text.split("\n", 1)[1] if "\n" in text else ""
                it["คำชี้แจง"] = text
                ptr = j + 1
                n += 1
                break
    return n


def write_csv(items, meta, out):
    ys = meta["years"] or [0, 0, 0, 0]
    with open(out, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["แผนงาน", "งาน", "งบ", "หมวด", "ประเภท", "รายการ", f"ประมาณการ {ys[3]}",
                    "หมายเหตุ", f"รายจ่ายจริง {ys[0]}", f"รายจ่ายจริง {ys[1]}", f"ประมาณการ {ys[2]}", "หน้า", "คำชี้แจง"])
        for it in items:
            w.writerow([it["แผนงาน"], it["งาน"], it["งบ"], it["หมวด"], it["ประเภท"], it["รายการ"],
                        f"{it['amount']:.2f}", it["หมายเหตุ"], f"{it['y0']:.2f}", f"{it['y1']:.2f}", f"{it['y2']:.2f}",
                        it["หน้า"], it.get("คำชี้แจง", "")])


if __name__ == "__main__":
    a = sys.argv[1:]
    items, meta = parse(a[0], *(int(x) for x in a[2:4]))
    got = attach_details(items, parse_details(a[0]))
    print(f"คำชี้แจง {got} / {sum(1 for it in items if it['amount'] > 0)} รายการที่มีงบประมาณ")
    write_csv(items, meta, a[1])
    tot = {}
    for it in items:
        tot[it["แผนงาน"]] = tot.get(it["แผนงาน"], 0) + it["amount"]
    for k, v in tot.items():
        print(f"{k:45s} {v:16,.2f}")
    print(f"{'รวม ' + str(len(items)) + ' รายการ':45s} {sum(tot.values()):16,.2f}  ปี {meta['years']}")
