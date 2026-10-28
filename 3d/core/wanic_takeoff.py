# SPDX-License-Identifier: GPL-3.0-or-later
# WANICNSURVEY 3D — "WANIC ถอดปริมาณ": quantity takeoff and Thai BOQ pricing.
"""Unit-rate pricing on top of the model's geometry (no GUI here).

A *rate* (รายการราคา) says: "every object whose <layer | material | BIM
class | name> is <value> is billed by its <quantity> at <material price> +
<labour price> per unit". Rates live in the document (plugin data), so a
model carries its own price list. One object may be billed by several rates
(a wall: concrete m³, formwork m², paint m²) — each rate is one BOQ line.

Quantities come from the same honest measures the rest of the app uses
(:mod:`core.bim`): areas from faces, volume ONLY for a watertight set (an
open shell has no volume, and it is reported, never guessed).

The BOQ follows the Thai convention (แบบ ปร.4): ค่าวัสดุ and ค่าแรง
priced separately per unit, totals per category, then Factor F and VAT.
"""
from __future__ import annotations

import csv
import io
import math
import zipfile
from xml.sax.saxutils import escape

# ---------------------------------------------------------------------------
# Vocabulary
# ---------------------------------------------------------------------------

#: What a rate is matched by → Thai label.
MATCH_BY = {
    "layer": "เลเยอร์",
    "material": "วัสดุ",
    "ifc": "คลาส BIM",
    "name": "ชื่อกลุ่ม/คอมโพเนนต์",
    "all": "ทุกวัตถุ",
}

#: Quantity kinds → (Thai label, default unit).
QTY_KINDS = {
    "volume": ("ปริมาตร", "ลบ.ม."),
    "area": ("พื้นที่ผิวทั้งหมด", "ตร.ม."),
    "net_area": ("พื้นที่สุทธิ (หักช่องเปิด)", "ตร.ม."),
    "top_area": ("พื้นที่ผิวบน (มองจากด้านบน)", "ตร.ม."),
    "side_area": ("พื้นที่ด้านข้าง (ผนัง)", "ตร.ม."),
    "length": ("ความยาว", "ม."),
    "count": ("จำนวนชิ้น", "ชิ้น"),
    "steel_kg": ("น้ำหนักเหล็ก (ปริมาตร × 7,850)", "กก."),
    "metrado": ("ปริมาณตามคลาส BIM", ""),
}

STEEL_DENSITY = 7850.0


def new_rate(**kw) -> dict:
    rate = {"id": "", "category": "", "code": "", "desc": "", "by": "layer",
            "value": "", "qty": "area", "unit": "ตร.ม.", "factor": 1.0,
            "mat": 0.0, "lab": 0.0, "note": ""}
    rate.update(kw)
    return rate


def default_data() -> dict:
    return {"rates": [], "settings": {"project": "", "owner": "",
                                      "location": "", "factor_f": 1.0,
                                      "vat": 7.0}}


#: Starting lines a user can add and then price (units only — no prices
#: are invented: every price starts at 0 and is the user's to fill).
SAMPLE_RATES = [
    ("งานดิน", "1.1", "งานขุดดิน", "ifc", "IfcFooting", "volume", "ลบ.ม."),
    ("งานโครงสร้าง", "2.1", "คอนกรีตโครงสร้าง (ฐานราก)", "ifc", "IfcFooting", "volume", "ลบ.ม."),
    ("งานโครงสร้าง", "2.2", "คอนกรีตโครงสร้าง (เสา)", "ifc", "IfcColumn", "volume", "ลบ.ม."),
    ("งานโครงสร้าง", "2.3", "คอนกรีตโครงสร้าง (คาน)", "ifc", "IfcBeam", "volume", "ลบ.ม."),
    ("งานโครงสร้าง", "2.4", "คอนกรีตพื้น", "ifc", "IfcSlab", "volume", "ลบ.ม."),
    ("งานโครงสร้าง", "2.5", "เหล็กเสริม", "ifc", "IfcReinforcingBar", "steel_kg", "กก."),
    ("งานสถาปัตยกรรม", "3.1", "ผนังก่ออิฐ", "ifc", "IfcWall", "side_area", "ตร.ม."),
    ("งานสถาปัตยกรรม", "3.2", "ฉาบปูนผนัง (2 ด้าน)", "ifc", "IfcWall", "side_area", "ตร.ม."),
    ("งานสถาปัตยกรรม", "3.3", "ประตู", "ifc", "IfcDoor", "count", "ชุด"),
    ("งานสถาปัตยกรรม", "3.4", "หน้าต่าง", "ifc", "IfcWindow", "count", "ชุด"),
    ("งานหลังคา", "4.1", "มุงหลังคา", "ifc", "IfcRoof", "top_area", "ตร.ม."),
]


def sample_rates() -> list[dict]:
    out = []
    for i, (cat, code, desc, by, value, qty, unit) in enumerate(SAMPLE_RATES):
        factor = 2.0 if "2 ด้าน" in desc else 1.0
        out.append(new_rate(id=f"s{i + 1}", category=cat, code=code, desc=desc,
                            by=by, value=value, qty=qty, unit=unit,
                            factor=factor))
    return out


# ---------------------------------------------------------------------------
# What there is to measure
# ---------------------------------------------------------------------------

def _most_common(values, default=""):
    counts: dict = {}
    for v in values:
        if v:
            counts[v] = counts.get(v, 0) + 1
    if not counts:
        return default
    return max(counts.items(), key=lambda kv: kv[1])[0]


def _measure(faces) -> dict:
    """Raw measures of a face set, all in metres."""
    from core import bim
    faces = list(faces)
    area = sum(f.area() for f in faces)
    net = sum(bim.face_net_area(f) for f in faces)
    top = 0.0
    side = 0.0
    for f in faces:
        try:
            nz = f.normal().z()
        except Exception:
            nz = 0.0
        a = bim.face_net_area(f)
        if nz > 0.2:
            top += a
        elif abs(nz) <= 0.2:
            side += a
    dx, dy, dz = bim._extents(faces) if faces else (0.0, 0.0, 0.0)
    return {"area": area, "net_area": net, "top_area": top,
            "side_area": side, "length": max(dx, dy, dz),
            "volume": bim.face_set_volume(faces) if faces else None,
            "extents": (dx, dy, dz)}


def _group_faces(g):
    if getattr(g, "xform", None) is not None or getattr(g, "children", None):
        from core.group import world_mesh
        return list(world_mesh(g).faces)
    return list(g.mesh.faces)


def collect_items(scene) -> list[dict]:
    """Every measurable thing in the model, as takeoff items:

    - each BIM-tagged object (faces or group) — the BIM tray's objects;
    - each untagged top-level group or component;
    - untagged loose faces, bucketed by (layer, material).

    An item: ``{"key", "label", "kind", "name", "layer", "material", "ifc",
    "faces", "group", "count", <measures>…}``."""
    from core import bim
    from core.layers import DEFAULT_LAYER, layer_of
    try:
        from core.group import effective_material
    except Exception:                                    # pragma: no cover
        effective_material = lambda g: None             # noqa: E731

    items: list[dict] = []
    tagged_faces = set()
    for obj in bim.collect_objects(scene):
        g = obj.get("group")
        faces = obj.get("faces")
        if g is not None:
            faces = _group_faces(g)
            layer = getattr(g, "layer", None) or DEFAULT_LAYER
            mat = (effective_material(g) or
                   _most_common(f.attrs.get("mat") for f in faces))
            key = ("group", id(g))
        else:
            tagged_faces.update(id(f) for f in faces)
            layer = _most_common((layer_of(f) for f in faces), DEFAULT_LAYER)
            mat = _most_common(f.attrs.get("mat") for f in faces)
            key = obj["key"]
        m = _measure(faces)
        _, _, (metrado, unit) = bim.class_quantities(obj["class"], faces)
        items.append({"key": key, "label": obj["name"] or obj["class"],
                      "kind": "bim", "name": obj["name"] or "",
                      "layer": layer, "material": mat or "",
                      "ifc": obj["class"], "faces": faces, "group": g,
                      "count": 1, "metrado": metrado, "metrado_unit": unit,
                      **m})
    for g in scene.groups:
        if getattr(g, "ifc", None):
            continue
        faces = _group_faces(g)
        if not faces:
            continue
        mat = (effective_material(g) or
               _most_common(f.attrs.get("mat") for f in faces))
        items.append({"key": ("group", id(g)), "label": g.name,
                      "kind": "group", "name": g.name or "",
                      "layer": getattr(g, "layer", None) or DEFAULT_LAYER,
                      "material": mat or "", "ifc": "", "faces": faces,
                      "group": g, "count": 1, "metrado": None,
                      "metrado_unit": "", **_measure(faces)})
    buckets: dict = {}
    for f in scene.loose_mesh.faces:
        if id(f) in tagged_faces or f.attrs.get("ifc"):
            continue
        k = (layer_of(f), f.attrs.get("mat") or "")
        buckets.setdefault(k, []).append(f)
    for (layer, mat), faces in sorted(buckets.items()):
        label = f"พื้นผิวอิสระ · {layer}" + (f" · {mat}" if mat else "")
        items.append({"key": ("loose", layer, mat), "label": label,
                      "kind": "loose", "name": "", "layer": layer,
                      "material": mat, "ifc": "", "faces": faces,
                      "group": None, "count": None, "metrado": None,
                      "metrado_unit": "", **_measure(faces)})
    return items


def match_candidates(items) -> dict:
    """Values offered per match kind (for the rate editor's drop-downs)."""
    out = {k: set() for k in MATCH_BY}
    for it in items:
        if it["layer"]:
            out["layer"].add(it["layer"])
        if it["material"]:
            out["material"].add(it["material"])
        if it["ifc"]:
            out["ifc"].add(it["ifc"])
        if it["name"]:
            out["name"].add(it["name"])
    return {k: sorted(v) for k, v in out.items()}


def rate_matches(rate: dict, item: dict) -> bool:
    by = rate.get("by", "layer")
    if by == "all":
        return True
    want = (rate.get("value") or "").strip()
    if not want:
        return False
    have = item.get({"layer": "layer", "material": "material", "ifc": "ifc",
                     "name": "name"}.get(by, by)) or ""
    return have.strip().casefold() == want.casefold()


def item_quantity(item: dict, qty: str):
    """``(value, problem)`` — value None with a Thai reason when the item
    cannot give that quantity honestly."""
    if qty == "volume":
        v = item.get("volume")
        return (v, None) if v is not None else (
            None, "รูปทรงไม่ปิดสนิท จึงไม่มีปริมาตร")
    if qty == "steel_kg":
        v = item.get("volume")
        return (v * STEEL_DENSITY, None) if v is not None else (
            None, "รูปทรงไม่ปิดสนิท จึงคิดน้ำหนักไม่ได้")
    if qty == "count":
        c = item.get("count")
        return (float(c), None) if c else (
            None, "พื้นผิวอิสระนับเป็นชิ้นไม่ได้ — จัดกลุ่มก่อน")
    if qty == "metrado":
        v = item.get("metrado")
        return (v, None) if v is not None else (
            None, "ไม่มีปริมาณตามคลาส BIM (ติดแท็ก BIM ก่อน)")
    v = item.get(qty)
    return (float(v), None) if v is not None else (None, "ไม่มีค่านี้")


# ---------------------------------------------------------------------------
# Pricing
# ---------------------------------------------------------------------------

def _num(x, default=0.0) -> float:
    try:
        v = float(str(x).replace(",", "").strip())
        return v if math.isfinite(v) else default
    except (TypeError, ValueError):
        return default


def compute(items: list[dict], data: dict) -> dict:
    """Price the takeoff. Returns::

        {"lines": [ {rate…, "quantity", "mat_total", "lab_total", "total",
                     "items": [keys], "problems": [(label, reason)]} ],
         "status": {item_key: "ok" | "no_rate" | "problem"},
         "subtotal", "factor_f", "after_f", "vat_pct", "vat", "grand"}
    """
    rates = data.get("rates", [])
    status = {it["key"]: "no_rate" for it in items}
    lines = []
    for rate in rates:
        factor = _num(rate.get("factor"), 1.0)
        qty_sum = 0.0
        keys, problems = [], []
        for it in items:
            if not rate_matches(rate, it):
                continue
            v, why = item_quantity(it, rate.get("qty", "area"))
            if v is None:
                problems.append((it["label"], why))
                status[it["key"]] = "problem"
                continue
            qty_sum += v
            keys.append(it["key"])
            if status[it["key"]] == "no_rate":
                status[it["key"]] = "ok"
        quantity = qty_sum * factor
        mat_total = quantity * _num(rate.get("mat"))
        lab_total = quantity * _num(rate.get("lab"))
        lines.append({**rate, "quantity": quantity, "mat_total": mat_total,
                      "lab_total": lab_total, "total": mat_total + lab_total,
                      "items": keys, "problems": problems})
    settings = data.get("settings", {})
    subtotal = sum(ln["total"] for ln in lines)
    factor_f = _num(settings.get("factor_f"), 1.0) or 1.0
    after_f = subtotal * factor_f
    vat_pct = _num(settings.get("vat"), 0.0)
    vat = after_f * vat_pct / 100.0
    return {"lines": lines, "status": status, "subtotal": subtotal,
            "factor_f": factor_f, "after_f": after_f, "vat_pct": vat_pct,
            "vat": vat, "grand": after_f + vat}


def by_category(lines) -> list[tuple[str, list[dict]]]:
    order, groups = [], {}
    for ln in lines:
        cat = (ln.get("category") or "").strip() or "อื่น ๆ"
        if cat not in groups:
            groups[cat] = []
            order.append(cat)
        groups[cat].append(ln)
    return [(c, groups[c]) for c in order]


# ---------------------------------------------------------------------------
# Thai baht in words
# ---------------------------------------------------------------------------

_DIGITS = ["", "หนึ่ง", "สอง", "สาม", "สี่", "ห้า", "หก", "เจ็ด", "แปด", "เก้า"]
_PLACES = ["", "สิบ", "ร้อย", "พัน", "หมื่น", "แสน"]


def _read_under_million(n: int, tail: bool = False) -> str:
    s = str(n)
    out = []
    length = len(s)
    for i, ch in enumerate(s):
        d = int(ch)
        place = length - i - 1
        if d == 0:
            continue
        if place == 1 and d == 1:
            out.append("สิบ")
        elif place == 1 and d == 2:
            out.append("ยี่สิบ")
        elif place == 0 and d == 1 and (length > 1 or tail):
            out.append("เอ็ด")
        else:
            out.append(_DIGITS[d] + _PLACES[place])
    return "".join(out)


def _read_int(n: int) -> str:
    if n == 0:
        return "ศูนย์"
    parts = []
    while n > 0:
        parts.append(n % 1_000_000)
        n //= 1_000_000
    words = ""
    for i in range(len(parts) - 1, -1, -1):
        chunk = parts[i]
        if chunk:
            words += _read_under_million(chunk, tail=i < len(parts) - 1)
        if i > 0:
            words += "ล้าน"
    return words


def baht_text(amount: float) -> str:
    """``1234.5`` → ``หนึ่งพันสองร้อยสามสิบสี่บาทห้าสิบสตางค์``."""
    amount = round(abs(float(amount)) + 1e-9, 2)
    baht = int(amount)
    satang = int(round((amount - baht) * 100))
    if satang == 100:
        baht, satang = baht + 1, 0
    text = _read_int(baht) + "บาท"
    return text + ("ถ้วน" if satang == 0 else _read_int(satang) + "สตางค์")


# ---------------------------------------------------------------------------
# Rate library files (CSV, UTF-8 with BOM so Excel reads Thai)
# ---------------------------------------------------------------------------

RATE_FIELDS = ["category", "code", "desc", "by", "value", "qty", "unit",
               "factor", "mat", "lab", "note"]
RATE_HEADERS = ["หมวด", "รหัส", "รายการ", "ผูกกับ", "ค่า", "คิดจาก", "หน่วย",
                "ตัวคูณ", "ค่าวัสดุต่อหน่วย", "ค่าแรงต่อหน่วย", "หมายเหตุ"]


def rates_to_csv(rates) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(RATE_HEADERS)
    for r in rates:
        w.writerow([r.get(f, "") for f in RATE_FIELDS])
    return "﻿" + buf.getvalue()


def rates_from_csv(text: str) -> list[dict]:
    text = text.lstrip("﻿")
    rows = list(csv.reader(io.StringIO(text)))
    if not rows:
        return []
    head = [h.strip() for h in rows[0]]
    idx = {}
    for f, h in zip(RATE_FIELDS, RATE_HEADERS):
        if h in head:
            idx[f] = head.index(h)
        elif f in head:
            idx[f] = head.index(f)
    out = []
    by_th = {v: k for k, v in MATCH_BY.items()}
    qty_th = {v[0]: k for k, v in QTY_KINDS.items()}
    for i, row in enumerate(rows[1:]):
        if not any(c.strip() for c in row):
            continue
        get = lambda f: row[idx[f]].strip() if f in idx and idx[f] < len(row) else ""  # noqa: E731
        by = get("by")
        by = by_th.get(by, by) if by else "layer"
        qty = get("qty")
        qty = qty_th.get(qty, qty) if qty else "area"
        out.append(new_rate(
            id=f"i{i + 1}", category=get("category"), code=get("code"),
            desc=get("desc"), by=by if by in MATCH_BY else "layer",
            value=get("value"), qty=qty if qty in QTY_KINDS else "area",
            unit=get("unit") or QTY_KINDS.get(qty, ("", ""))[1],
            factor=_num(get("factor"), 1.0) or 1.0, mat=_num(get("mat")),
            lab=_num(get("lab")), note=get("note")))
    return out


# ---------------------------------------------------------------------------
# BOQ export: CSV and a dependency-free .xlsx
# ---------------------------------------------------------------------------

BOQ_HEADERS = ["ลำดับ", "รายการ", "จำนวน", "หน่วย", "ค่าวัสดุ ราคาต่อหน่วย",
               "ค่าวัสดุ จำนวนเงิน", "ค่าแรงงาน ราคาต่อหน่วย",
               "ค่าแรงงาน จำนวนเงิน", "รวมค่าวัสดุและค่าแรงงาน", "หมายเหตุ"]


def boq_rows(result: dict):
    """The BOQ as typed rows: (kind, cells). kind ∈ head, cat, line, sum,
    total. Numbers stay numbers."""
    rows = []
    for ci, (cat, lines) in enumerate(by_category(result["lines"]), 1):
        rows.append(("cat", [str(ci), cat, None, "", None, None, None, None,
                             None, ""]))
        cm = cl = 0.0
        for ln in lines:
            label = (f"{ln['code']} " if ln.get("code") else "") + (ln.get("desc") or "")
            note = ln.get("note") or ""
            if ln["problems"]:
                note = (note + " " if note else "") + \
                    f"(วัดไม่ได้ {len(ln['problems'])} วัตถุ)"
            rows.append(("line", ["", label, ln["quantity"], ln.get("unit", ""),
                                  _num(ln.get("mat")), ln["mat_total"],
                                  _num(ln.get("lab")), ln["lab_total"],
                                  ln["total"], note]))
            cm += ln["mat_total"]
            cl += ln["lab_total"]
        rows.append(("sum", ["", f"รวม{cat}", None, "", None, cm, None, cl,
                             cm + cl, ""]))
    r = result
    rows.append(("total", ["", "รวมค่าก่อสร้าง (ค่าวัสดุและค่าแรงงาน)", None,
                           "", None, None, None, None, r["subtotal"], ""]))
    if abs(r["factor_f"] - 1.0) > 1e-12:
        rows.append(("total", ["", f"รวมค่าก่อสร้างคูณ Factor F ({r['factor_f']:g})",
                               None, "", None, None, None, None, r["after_f"],
                               ""]))
    if r["vat_pct"]:
        rows.append(("total", ["", f"ภาษีมูลค่าเพิ่ม {r['vat_pct']:g}%", None, "",
                               None, None, None, None, r["vat"], ""]))
    rows.append(("total", ["", "รวมราคาทั้งสิ้น", None, "", None, None, None,
                           None, r["grand"], ""]))
    rows.append(("words", ["", f"({baht_text(r['grand'])})", None, "", None,
                           None, None, None, None, ""]))
    return rows


def boq_csv(result: dict, settings: dict) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["แบบสรุปราคาค่าก่อสร้าง (BOQ)"])
    for k, label in (("project", "โครงการ"), ("owner", "เจ้าของงาน"),
                     ("location", "สถานที่")):
        if settings.get(k):
            w.writerow([f"{label}: {settings[k]}"])
    w.writerow(BOQ_HEADERS)
    for _kind, cells in boq_rows(result):
        w.writerow(["" if c is None else (f"{c:.2f}" if isinstance(c, float)
                                          else c) for c in cells])
    return "﻿" + buf.getvalue()


def _col(i: int) -> str:
    s = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


class _Sheet:
    def __init__(self, name):
        self.name = name
        self.rows = []          # list of list of (value, style)
        self.merges = []
        self.widths = []

    def add(self, cells, style=0, styles=None):
        self.rows.append([(c, (styles[i] if styles else style))
                          for i, c in enumerate(cells)])
        return len(self.rows)

    def xml(self) -> str:
        out = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
               '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
               'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">',
               '<sheetPr><pageSetUpPr fitToPage="1"/></sheetPr>']
        if self.widths:
            out.append("<cols>")
            for i, w in enumerate(self.widths, 1):
                out.append(f'<col min="{i}" max="{i}" width="{w}" customWidth="1"/>')
            out.append("</cols>")
        out.append("<sheetData>")
        for r, row in enumerate(self.rows, 1):
            out.append(f'<row r="{r}">')
            for c, (val, st) in enumerate(row):
                ref = f"{_col(c)}{r}"
                if val is None or val == "":
                    out.append(f'<c r="{ref}" s="{st}"/>')
                elif isinstance(val, (int, float)) and not isinstance(val, bool):
                    out.append(f'<c r="{ref}" s="{st}"><v>{float(val)!r}</v></c>')
                else:
                    out.append(f'<c r="{ref}" s="{st}" t="inlineStr"><is><t xml:space="preserve">'
                               f'{escape(str(val))}</t></is></c>')
            out.append("</row>")
        out.append("</sheetData>")
        if self.merges:
            out.append(f'<mergeCells count="{len(self.merges)}">')
            out += [f'<mergeCell ref="{m}"/>' for m in self.merges]
            out.append("</mergeCells>")
        out.append('<pageMargins left="0.5" right="0.4" top="0.6" bottom="0.6" '
                   'header="0.3" footer="0.3"/>')
        out.append('<pageSetup paperSize="9" orientation="landscape" fitToWidth="1" '
                   'fitToHeight="0"/>')
        out.append("</worksheet>")
        return "".join(out)


# style ids (see _STYLES): 0 normal, 1 bold, 2 title, 3 header, 4 text cell,
# 5 number cell, 6 bold text cell, 7 bold number cell, 8 centred text cell
_FONT = "TH Sarabun New"
_STYLES = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
<numFmts count="1"><numFmt numFmtId="164" formatCode="#,##0.00"/></numFmts>
<fonts count="3">
<font><sz val="14"/><name val="{_FONT}"/><family val="2"/></font>
<font><b/><sz val="14"/><name val="{_FONT}"/><family val="2"/></font>
<font><b/><sz val="18"/><name val="{_FONT}"/><family val="2"/></font>
</fonts>
<fills count="3">
<fill><patternFill patternType="none"/></fill>
<fill><patternFill patternType="gray125"/></fill>
<fill><patternFill patternType="solid"><fgColor rgb="FFDCE6F1"/><bgColor indexed="64"/></patternFill></fill>
</fills>
<borders count="2">
<border><left/><right/><top/><bottom/><diagonal/></border>
<border><left style="thin"><color auto="1"/></left><right style="thin"><color auto="1"/></right><top style="thin"><color auto="1"/></top><bottom style="thin"><color auto="1"/></bottom><diagonal/></border>
</borders>
<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
<cellXfs count="9">
<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>
<xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1"/>
<xf numFmtId="0" fontId="2" fillId="0" borderId="0" xfId="0" applyFont="1" applyAlignment="1"><alignment horizontal="center"/></xf>
<xf numFmtId="0" fontId="1" fillId="2" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1"><alignment horizontal="center" vertical="center" wrapText="1"/></xf>
<xf numFmtId="0" fontId="0" fillId="0" borderId="1" xfId="0" applyBorder="1" applyAlignment="1"><alignment vertical="top" wrapText="1"/></xf>
<xf numFmtId="164" fontId="0" fillId="0" borderId="1" xfId="0" applyNumberFormat="1" applyBorder="1"/>
<xf numFmtId="0" fontId="1" fillId="0" borderId="1" xfId="0" applyFont="1" applyBorder="1"/>
<xf numFmtId="164" fontId="1" fillId="0" borderId="1" xfId="0" applyNumberFormat="1" applyFont="1" applyBorder="1"/>
<xf numFmtId="0" fontId="0" fillId="0" borderId="1" xfId="0" applyBorder="1" applyAlignment="1"><alignment horizontal="center" vertical="top"/></xf>
</cellXfs>
<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>
</styleSheet>"""


def _boq_sheet(result, settings) -> _Sheet:
    sh = _Sheet("BOQ")
    sh.widths = [7, 46, 12, 9, 13, 15, 13, 15, 17, 20]
    sh.add(["แบบสรุปราคาค่าก่อสร้าง (BOQ)"] + [""] * 9, style=2)
    sh.merges.append("A1:J1")
    for k, label in (("project", "โครงการ"), ("owner", "เจ้าของงาน"),
                     ("location", "สถานที่ก่อสร้าง")):
        if settings.get(k):
            r = sh.add([f"{label}: {settings[k]}"] + [""] * 9, style=1)
            sh.merges.append(f"A{r}:J{r}")
    r = sh.add(BOQ_HEADERS, style=3)
    for kind, cells in boq_rows(result):
        if kind == "line":
            styles = [8, 4, 5, 8, 5, 5, 5, 5, 5, 4]
        elif kind == "cat":
            styles = [8, 6, 4, 4, 4, 4, 4, 4, 4, 4]
        elif kind == "words":
            styles = [4, 6, 4, 4, 4, 4, 4, 4, 4, 4]
        else:
            styles = [4, 6, 7, 4, 7, 7, 7, 7, 7, 4]
        r = sh.add(cells, styles=styles)
        if kind == "words":
            sh.merges.append(f"B{r}:I{r}")
    return sh


def _detail_sheet(items, result) -> _Sheet:
    sh = _Sheet("รายละเอียดวัตถุ")
    sh.widths = [36, 16, 18, 16, 13, 13, 13, 12, 26, 14]
    sh.add(["วัตถุ", "เลเยอร์", "วัสดุ", "คลาส BIM", "พื้นที่ (ตร.ม.)",
            "พื้นที่สุทธิ (ตร.ม.)", "ปริมาตร (ลบ.ม.)", "ความยาว (ม.)",
            "รายการราคาที่ใช้", "สถานะ"], style=3)
    used: dict = {}
    for ln in result["lines"]:
        for k in ln["items"]:
            used.setdefault(k, []).append(ln.get("code") or ln.get("desc") or "?")
    state_th = {"ok": "มีราคา", "no_rate": "ยังไม่มีราคา",
                "problem": "วัดไม่ได้บางรายการ"}
    for it in items:
        sh.add([it["label"], it["layer"], it["material"], it["ifc"],
                it["area"], it["net_area"], it["volume"], it["length"],
                ", ".join(used.get(it["key"], [])),
                state_th.get(result["status"].get(it["key"]), "")],
               styles=[4, 4, 4, 4, 5, 5, 5, 5, 4, 4])
    return sh


def boq_xlsx_bytes(result: dict, settings: dict, items=None) -> bytes:
    sheets = [_boq_sheet(result, settings)]
    if items is not None:
        sheets.append(_detail_sheet(items, result))
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml",
                   '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                   '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                   '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                   '<Default Extension="xml" ContentType="application/xml"/>'
                   '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
                   '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
                   + "".join(f'<Override PartName="/xl/worksheets/sheet{i}.xml" '
                             'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
                             for i in range(1, len(sheets) + 1))
                   + '</Types>')
        z.writestr("_rels/.rels",
                   '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                   '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
                   '</Relationships>')
        z.writestr("xl/workbook.xml",
                   '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                   '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                   'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>'
                   + "".join(f'<sheet name="{escape(s.name)}" sheetId="{i}" r:id="rId{i}"/>'
                             for i, s in enumerate(sheets, 1))
                   + '</sheets></workbook>')
        z.writestr("xl/_rels/workbook.xml.rels",
                   '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                   '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   + "".join(f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{i}.xml"/>'
                             for i in range(1, len(sheets) + 1))
                   + f'<Relationship Id="rId{len(sheets) + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
                   '</Relationships>')
        z.writestr("xl/styles.xml", _STYLES)
        for i, s in enumerate(sheets, 1):
            z.writestr(f"xl/worksheets/sheet{i}.xml", s.xml())
    return buf.getvalue()
