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
    "manual": ("กรอกจำนวนเอง", "หน่วย"),
}

#: The three parts of a Thai government price estimate (หลักเกณฑ์ 2569).
SECTIONS = {
    "work": "ค่างานต้นทุน (ปร.1)",
    "equip": "ครุภัณฑ์จัดซื้อ (ปร.2)",
    "special": "ค่าใช้จ่ายพิเศษ (ปร.3)",
}

#: Pricing method: the government one multiplies the construction cost by
#: Factor F (which already holds overhead, interest, profit and VAT) and
#: adds VAT only to purchased equipment and special expenses; the private
#: one adds VAT on top of everything.
METHODS = {"gov": "ราคากลางราชการ (Factor F รวม VAT แล้ว)",
           "private": "งานเอกชน (บวก VAT ทั้งหมด)"}

STEEL_DENSITY = 7850.0


def new_rate(**kw) -> dict:
    rate = {"id": "", "category": "", "code": "", "desc": "", "by": "layer",
            "value": "", "qty": "area", "unit": "ตร.ม.", "factor": 1.0,
            "mat": 0.0, "lab": 0.0, "note": "", "section": "work",
            "manual_qty": 0.0}
    rate.update(kw)
    return rate


DEFAULT_SETTINGS = {
    "project": "", "owner": "", "location": "", "drawing_no": "",
    "date": "", "area_m2": 0.0, "factor_f": 1.0, "vat": 7.0,
    "method": "gov", "adv_pay": 0.0, "retention": 0.0, "interest": 6.0,
    "chair": "", "member1": "", "member2": "",
    "preparer": "นายเวนิช ธัมมะวงษ์", "preparer_role": "วิศวกรสำรวจ",
}


def default_data() -> dict:
    return {"rates": [], "settings": dict(DEFAULT_SETTINGS)}


def settings_of(data) -> dict:
    s = dict(DEFAULT_SETTINGS)
    s.update((data or {}).get("settings") or {})
    return s


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
    # A WANIC profile member knows its true length along its path (a bent
    # gutter or a ring beam is longer than its bounding box).
    try:
        from core.wanic_profiles import member_record
    except Exception:                                    # pragma: no cover
        member_record = lambda g: None                  # noqa: E731
    for it in items:
        rec = member_record(it["group"]) if it["group"] is not None else None
        if rec and rec.get("length"):
            it["length"] = float(rec["length"])
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
         "subtotal" (ค่างานต้นทุน), "factor_f", "after_f" (ค่าก่อสร้าง),
         "equip", "equip_vat", "special", "special_vat",
         "vat_pct", "vat" (all VAT added), "grand" (ราคากลาง), "method"}
    """
    rates = data.get("rates", [])
    status = {it["key"]: "no_rate" for it in items}
    lines = []
    for rate in rates:
        factor = _num(rate.get("factor"), 1.0)
        qty_sum = 0.0
        keys, problems = [], []
        if rate.get("qty") == "manual":
            qty_sum = _num(rate.get("manual_qty"))
        else:
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
        section = rate.get("section") or "work"
        if section not in SECTIONS:
            section = "work"
        lines.append({**rate, "section": section, "quantity": quantity,
                      "mat_total": mat_total, "lab_total": lab_total,
                      "total": mat_total + lab_total, "items": keys,
                      "problems": problems})
    settings = settings_of(data)
    method = settings.get("method") if settings.get("method") in METHODS \
        else "gov"
    subtotal = sum(ln["total"] for ln in lines if ln["section"] == "work")
    equip = sum(ln["total"] for ln in lines if ln["section"] == "equip")
    special = sum(ln["total"] for ln in lines if ln["section"] == "special")
    factor_f = _num(settings.get("factor_f"), 1.0) or 1.0
    after_f = subtotal * factor_f
    vat_pct = _num(settings.get("vat"), 0.0)
    v = vat_pct / 100.0
    equip_vat, special_vat = equip * v, special * v
    if method == "gov":
        vat = equip_vat + special_vat
    else:
        vat = (after_f + equip + special) * v
    grand = after_f + equip + special + vat
    return {"lines": lines, "status": status, "subtotal": subtotal,
            "factor_f": factor_f, "after_f": after_f, "equip": equip,
            "equip_vat": equip_vat, "special": special,
            "special_vat": special_vat, "vat_pct": vat_pct, "vat": vat,
            "grand": grand, "method": method}


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
               "factor", "mat", "lab", "note", "section", "manual_qty"]
RATE_HEADERS = ["หมวด", "รหัส", "รายการ", "ผูกกับ", "ค่า", "คิดจาก", "หน่วย",
                "ตัวคูณ", "ค่าวัสดุต่อหน่วย", "ค่าแรงต่อหน่วย", "หมายเหตุ", "ส่วน",
                "จำนวนที่กรอกเอง"]


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
    sec_th = {v: k for k, v in SECTIONS.items()}
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
            lab=_num(get("lab")), note=get("note"),
            section=sec_th.get(get("section"), get("section"))
            if sec_th.get(get("section"), get("section")) in SECTIONS
            else "work", manual_qty=_num(get("manual_qty"))))
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

    def tot(label, value):
        rows.append(("total", ["", label, None, "", None, None, None, None,
                               value, ""]))
    tot("รวมค่างานต้นทุน (ค่าวัสดุและค่าแรงงาน)", r["subtotal"])
    if abs(r["factor_f"] - 1.0) > 1e-12:
        tot(f"ค่าก่อสร้าง = ค่างานต้นทุน × Factor F ({r['factor_f']:g})",
            r["after_f"])
    if r.get("equip"):
        tot("ค่าครุภัณฑ์จัดซื้อ (ก่อน VAT)", r["equip"])
    if r.get("special"):
        tot("ค่าใช้จ่ายพิเศษตามข้อกำหนด (ก่อน VAT)", r["special"])
    if r["vat"]:
        what = ("ของครุภัณฑ์และค่าใช้จ่ายพิเศษ" if r.get("method") == "gov"
                else "")
        tot(f"ภาษีมูลค่าเพิ่ม {r['vat_pct']:g}% {what}".strip(), r["vat"])
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
    def __init__(self, name, landscape=True):
        self.name = name
        self.rows = []          # list of list of (value, style)
        self.merges = []
        self.widths = []
        self.landscape = landscape

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
        orient = "landscape" if self.landscape else "portrait"
        out.append(f'<pageSetup paperSize="9" orientation="{orient}" '
                   'fitToWidth="1" fitToHeight="0"/>')
        out.append("</worksheet>")
        return "".join(out)


# style ids (see _STYLES): 0 normal, 1 bold, 2 title, 3 header, 4 text cell,
# 5 number cell, 6 bold text cell, 7 bold number cell, 8 centred text cell,
# 9 bold right (form code), 10 centred plain (signatures), 11 Factor F cell
_FONT = "TH Sarabun New"
_STYLES = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
<numFmts count="2"><numFmt numFmtId="164" formatCode="#,##0.00"/><numFmt numFmtId="165" formatCode="0.0000"/></numFmts>
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
<cellXfs count="12">
<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>
<xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1"/>
<xf numFmtId="0" fontId="2" fillId="0" borderId="0" xfId="0" applyFont="1" applyAlignment="1"><alignment horizontal="center"/></xf>
<xf numFmtId="0" fontId="1" fillId="2" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1"><alignment horizontal="center" vertical="center" wrapText="1"/></xf>
<xf numFmtId="0" fontId="0" fillId="0" borderId="1" xfId="0" applyBorder="1" applyAlignment="1"><alignment vertical="top" wrapText="1"/></xf>
<xf numFmtId="164" fontId="0" fillId="0" borderId="1" xfId="0" applyNumberFormat="1" applyBorder="1"/>
<xf numFmtId="0" fontId="1" fillId="0" borderId="1" xfId="0" applyFont="1" applyBorder="1"/>
<xf numFmtId="164" fontId="1" fillId="0" borderId="1" xfId="0" applyNumberFormat="1" applyFont="1" applyBorder="1"/>
<xf numFmtId="0" fontId="0" fillId="0" borderId="1" xfId="0" applyBorder="1" applyAlignment="1"><alignment horizontal="center" vertical="top"/></xf>
<xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1" applyAlignment="1"><alignment horizontal="right"/></xf>
<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0" applyAlignment="1"><alignment horizontal="center"/></xf>
<xf numFmtId="165" fontId="0" fillId="0" borderId="1" xfId="0" applyNumberFormat="1" applyBorder="1"/>
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
    _sign(sh, settings, 10)
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



# ---------------------------------------------------------------------------
# The government forms (หลักเกณฑ์การคำนวณราคากลางงานก่อสร้าง พ.ศ. 2569):
# ปร.1 ค่างานต้นทุน · ปร.1 (ก) สรุปค่าก่อสร้าง · ปร.2 ครุภัณฑ์จัดซื้อ ·
# ปร.2 (ก) สรุปค่าครุภัณฑ์ · ปร.3 ค่าใช้จ่ายพิเศษ · ปร.4 สรุปราคากลาง
# ---------------------------------------------------------------------------

_TH_MONTHS = ["มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม",
              "มิถุนายน", "กรกฎาคม", "สิงหาคม", "กันยายน", "ตุลาคม",
              "พฤศจิกายน", "ธันวาคม"]


def thai_date(d=None) -> str:
    import datetime
    d = d or datetime.date.today()
    return f"{d.day} {_TH_MONTHS[d.month - 1]} {d.year + 543}"


_DOTS = "................................................"


def _hdr(sh, code, title, st, ncols, attach=None):
    last = _col(ncols - 1)
    r = sh.add([""] * (ncols - 1) + [f"แบบ {code}"], style=9)
    r = sh.add([title] + [""] * (ncols - 1), style=2)
    sh.merges.append(f"A{r}:{last}{r}")
    lines = [f"ชื่อโครงการงานก่อสร้าง  {st.get('project') or _DOTS}",
             f"สถานที่ก่อสร้าง  {st.get('location') or _DOTS}",
             f"แบบเลขที่  {st.get('drawing_no') or _DOTS}",
             f"หน่วยงานเจ้าของโครงการงานก่อสร้าง  {st.get('owner') or _DOTS}"]
    if attach:
        lines.append(attach)
    lines.append(f"คำนวณราคากลาง เมื่อวันที่  {st.get('date') or thai_date()}")
    for text in lines:
        r = sh.add([text] + [""] * (ncols - 1), style=0)
        sh.merges.append(f"A{r}:{last}{r}")


def _sign(sh, st, ncols):
    last = _col(ncols - 1)
    sh.add([""] * ncols)
    for role, key in (("ประธานกรรมการกำหนดราคากลาง", "chair"),
                      ("กรรมการกำหนดราคากลาง", "member1"),
                      ("กรรมการกำหนดราคากลาง", "member2")):
        r = sh.add([f"(ลงชื่อ) ......................................  {role}"]
                   + [""] * (ncols - 1), style=10)
        sh.merges.append(f"A{r}:{last}{r}")
        name = st.get(key) or ".........................................."
        r = sh.add([f"( {name} )"] + [""] * (ncols - 1), style=10)
        sh.merges.append(f"A{r}:{last}{r}")
        sh.add([""] * ncols)
    # The person who measured and priced the drawings, and the program's
    # signature (WANIC tools carry their developer's name on every form).
    from core.wanic_sign import NAME, ROLE, footer
    prep = st.get("preparer") or NAME
    role = st.get("preparer_role") or ROLE
    for text in ("(ลงชื่อ) ......................................  "
                 "ผู้ถอดแบบและคำนวณราคา", f"( {prep} )", f"ตำแหน่ง {role}"):
        r = sh.add([text] + [""] * (ncols - 1), style=10)
        sh.merges.append(f"A{r}:{last}{r}")
    sh.add([""] * ncols)
    r = sh.add([footer("WANIC ถอดปริมาณ")] + [""] * (ncols - 1), style=0)
    sh.merges.append(f"A{r}:{last}{r}")


def _two_row_head(sh, top, sub, spans):
    """A two-row table head: ``spans`` = {first col: last col} merged
    across in the top row; every other column merges down."""
    r1 = sh.add(top, style=3)
    r2 = sh.add(sub, style=3)
    c = 0
    while c < len(top):
        if c in spans:
            sh.merges.append(f"{_col(c)}{r1}:{_col(spans[c])}{r1}")
            c = spans[c] + 1
        else:
            sh.merges.append(f"{_col(c)}{r1}:{_col(c)}{r2}")
            c += 1


def _pages(nrows, per=28):
    return max(1, math.ceil(nrows / per))


def _section_lines(result, section):
    return [ln for ln in result["lines"] if ln.get("section", "work") == section]


def _pr1(result, st) -> _Sheet:
    sh = _Sheet("ปร.1")
    sh.widths = [8, 44, 11, 9, 13, 15, 13, 15, 17, 16]
    _hdr(sh, "ปร.1", "แบบแสดงรายการ ปริมาณงาน และราคา ค่างานต้นทุน", st, 10)
    _two_row_head(sh, ["ลำดับที่", "รายการ", "จำนวน", "หน่วย", "ค่าวัสดุ", "",
                       "ค่าแรงงาน", "", "รวมค่าวัสดุและค่าแรงงาน", "หมายเหตุ"],
                  ["", "", "", "", "ราคาต่อหน่วย", "จำนวนเงิน", "ราคาต่อหน่วย",
                   "จำนวนเงิน", "", ""], {4: 5, 6: 7})
    work = _section_lines(result, "work")
    if not work:
        sh.add(["", "(ไม่มีรายการ)"] + [""] * 8, styles=[4] * 10)
    for ci, (cat, lines) in enumerate(by_category(work), 1):
        sh.add([str(ci), cat] + [""] * 8, styles=[8, 6] + [4] * 8)
        cm = cl = 0.0
        for li, ln in enumerate(lines, 1):
            note = ln.get("note") or ""
            if ln["problems"]:
                note = (note + " " if note else "") + \
                    f"(วัดไม่ได้ {len(ln['problems'])} วัตถุ)"
            sh.add([ln.get("code") or f"{ci}.{li}", ln.get("desc") or "",
                    ln["quantity"], ln.get("unit", ""), _num(ln.get("mat")),
                    ln["mat_total"], _num(ln.get("lab")), ln["lab_total"],
                    ln["total"], note], styles=[8, 4, 5, 8, 5, 5, 5, 5, 5, 4])
            cm += ln["mat_total"]
            cl += ln["lab_total"]
        sh.add(["", f"รวม{cat}", None, "", None, cm, None, cl, cm + cl, ""],
               styles=[4, 6, 4, 4, 4, 7, 4, 7, 7, 4])
    sh.add(["", "รวมค่างานต้นทุน", None, "", None,
            sum(ln["mat_total"] for ln in work), None,
            sum(ln["lab_total"] for ln in work), result["subtotal"], ""],
           styles=[4, 6, 4, 4, 4, 7, 4, 7, 7, 4])
    _sign(sh, st, 10)
    return sh


def _pr1k(result, st, pr1_rows) -> _Sheet:
    sh = _Sheet("ปร.1 (ก)", landscape=False)
    sh.widths = [8, 40, 17, 11, 17, 14]
    _hdr(sh, "ปร.1 (ก)", "แบบสรุปค่าก่อสร้าง ค่างานต้นทุน", st, 6,
         attach=f"แบบ ปร.1 ที่แนบ จำนวน {_pages(pr1_rows)} หน้า")
    sh.add(["ลำดับที่", "รายการ", "ค่างานต้นทุน", "Factor F", "ค่าก่อสร้าง",
            "หมายเหตุ"], style=3)
    F = result["factor_f"]
    work = _section_lines(result, "work")
    for ci, (cat, lines) in enumerate(by_category(work), 1):
        cost = sum(ln["total"] for ln in lines)
        sh.add([str(ci), cat, cost, F, cost * F, ""],
               styles=[8, 4, 5, 11, 5, 4])
    sh.add(["", "รวมค่าก่อสร้าง", result["subtotal"], None, result["after_f"],
            ""], styles=[4, 6, 7, 4, 7, 4])
    r = sh.add(["", "เงื่อนไขการใช้ตาราง Factor F", "", "", "", ""], style=1)
    sh.merges.append(f"B{r}:F{r}")
    for label, key in (("อัตราเงินค่าจ้างล่วงหน้า", "adv_pay"),
                       ("อัตราเงินประกันผลงาน", "retention"),
                       ("อัตราดอกเบี้ยเงินกู้", "interest"),
                       ("อัตราภาษีมูลค่าเพิ่ม", "vat")):
        r = sh.add(["", f"{label}  {_num(st.get(key)):g} %", "", "", "", ""])
        sh.merges.append(f"B{r}:F{r}")
    area = _num(st.get("area_m2"))
    avg = (f"{result['after_f'] / area:,.2f}" if area > 0 else "........")
    r = sh.add(["", f"ขนาดหรือเนื้อที่อาคาร  {area:,.2f}  ตารางเมตร  เฉลี่ย  "
                    f"{avg}  บาทต่อตารางเมตร", "", "", "", ""])
    sh.merges.append(f"B{r}:F{r}")
    _sign(sh, st, 6)
    return sh


def _pr2(result, st) -> _Sheet:
    sh = _Sheet("ปร.2")
    sh.widths = [8, 44, 11, 9, 13, 15, 13, 15, 17, 16]
    _hdr(sh, "ปร.2", "แบบแสดงรายการ ปริมาณงาน และราคา ค่าครุภัณฑ์จัดซื้อ",
         st, 10)
    _two_row_head(sh, ["ลำดับที่", "รายการ", "จำนวน", "หน่วย", "ค่าครุภัณฑ์", "",
                       "ค่าติดตั้ง", "", "รวมค่าครุภัณฑ์", "หมายเหตุ"],
                  ["", "", "", "", "ราคาต่อหน่วย", "จำนวนเงิน", "ราคาต่อหน่วย",
                   "จำนวนเงิน", "", ""], {4: 5, 6: 7})
    eq = _section_lines(result, "equip")
    if not eq:
        sh.add(["", "(ไม่มีรายการ)"] + [""] * 8, styles=[4] * 10)
    for i, ln in enumerate(eq, 1):
        sh.add([ln.get("code") or str(i), ln.get("desc") or "",
                ln["quantity"], ln.get("unit", ""), _num(ln.get("mat")),
                ln["mat_total"], _num(ln.get("lab")), ln["lab_total"],
                ln["total"], ln.get("note") or ""],
               styles=[8, 4, 5, 8, 5, 5, 5, 5, 5, 4])
    sh.add(["", "รวม", None, "", None, sum(ln["mat_total"] for ln in eq),
            None, sum(ln["lab_total"] for ln in eq), result["equip"], ""],
           styles=[4, 6, 4, 4, 4, 7, 4, 7, 7, 4])
    _sign(sh, st, 10)
    return sh


def _pr2k(result, st, pr2_rows) -> _Sheet:
    sh = _Sheet("ปร.2 (ก)")
    sh.widths = [8, 38, 14, 13, 15, 14, 13, 15, 17, 14]
    _hdr(sh, "ปร.2 (ก)", "แบบสรุปค่าครุภัณฑ์จัดซื้อ", st, 10,
         attach=f"แบบ ปร.2 ที่แนบ จำนวน {_pages(pr2_rows)} หน้า")
    _two_row_head(sh, ["ลำดับที่", "รายการ", "ค่าครุภัณฑ์", "", "", "ค่าติดตั้ง",
                       "", "", "รวม", "หมายเหตุ"],
                  ["", "", "ค่าครุภัณฑ์", "ค่าภาษีมูลค่าเพิ่ม", "จำนวนเงิน",
                   "ค่าติดตั้ง", "ค่าภาษีมูลค่าเพิ่ม", "จำนวนเงิน",
                   "ค่าครุภัณฑ์จัดซื้อ", ""], {2: 4, 5: 7})
    v = result["vat_pct"] / 100.0
    tot = [0.0] * 7
    eq = _section_lines(result, "equip")
    if not eq:
        sh.add(["", "(ไม่มีรายการ)"] + [""] * 8, styles=[4] * 10)
    for i, ln in enumerate(eq, 1):
        m, lb = ln["mat_total"], ln["lab_total"]
        vals = [m, m * v, m * (1 + v), lb, lb * v, lb * (1 + v),
                (m + lb) * (1 + v)]
        tot = [a + b for a, b in zip(tot, vals)]
        sh.add([ln.get("code") or str(i), ln.get("desc") or ""] + vals + [""],
               styles=[8, 4] + [5] * 7 + [4])
    sh.add(["", "รวม"] + tot + [""], styles=[4, 6] + [7] * 7 + [4])
    _sign(sh, st, 10)
    return sh


def _pr3(result, st) -> _Sheet:
    sh = _Sheet("ปร.3", landscape=False)
    sh.widths = [8, 50, 18, 20, 18]
    _hdr(sh, "ปร.3",
         "แบบแสดงรายการ ปริมาณงาน และราคา ค่าใช้จ่ายพิเศษตามข้อกำหนด", st, 5)
    sh.add(["ลำดับที่", "รายการ", "จำนวนหน่วย", "ค่าใช้จ่ายรวม (ค่าก่อสร้าง)",
            "หมายเหตุ"], style=3)
    v = result["vat_pct"] / 100.0
    sp = _section_lines(result, "special")
    if not sp:
        sh.add(["", "(ไม่มีรายการ)", "", "", ""], styles=[4] * 5)
    for i, ln in enumerate(sp, 1):
        sh.add([ln.get("code") or str(i), ln.get("desc") or "",
                f"{ln['quantity']:,.2f} {ln.get('unit', '')}".strip(),
                ln["total"] * (1 + v),
                ("รวมภาษีมูลค่าเพิ่ม " f"{result['vat_pct']:g}%"
                 + (f" · {ln['note']}" if ln.get("note") else ""))],
               styles=[8, 4, 8, 5, 4])
    sh.add(["", "รวมค่าใช้จ่ายพิเศษตามข้อกำหนดทุกรายการ", "",
            result["special"] + result["special_vat"], ""],
           styles=[4, 6, 4, 7, 4])
    r = sh.add(["", "แนบแบบแสดงการคำนวณและเหตุผลความจำเป็นของแต่ละรายการ",
                "", "", ""])
    sh.merges.append(f"B{r}:E{r}")
    _sign(sh, st, 5)
    return sh


def _pr4(result, st) -> _Sheet:
    sh = _Sheet("ปร.4", landscape=False)
    sh.widths = [8, 58, 20, 18]
    _hdr(sh, "ปร.4", "แบบสรุปราคากลางงานก่อสร้างอาคาร", st, 4,
         attach="แบบ ปร.1 (ก) ปร.2 (ก) และ ปร.3 (ถ้ามี) ที่แนบ จำนวน "
                f"{1 + bool(result['equip']) + bool(result['special'])} ชุด")
    sh.add(["ลำดับที่", "รายการ", "ค่าก่อสร้าง", "หมายเหตุ"], style=3)
    rows = [("1", "ค่างานต้นทุน × Factor F (ตามแบบ ปร.1 (ก))",
             result["after_f"], f"Factor F {result['factor_f']:.4f}"),
            ("2", "ค่าครุภัณฑ์จัดซื้อ (ตามแบบ ปร.2 (ก))",
             result["equip"] + result["equip_vat"], "รวมภาษีมูลค่าเพิ่ม"),
            ("3", "ค่าใช้จ่ายพิเศษตามข้อกำหนด (ถ้ามี) (ตามแบบ ปร.3)",
             result["special"] + result["special_vat"], "รวมภาษีมูลค่าเพิ่ม")]
    if result.get("method") == "private":
        rows.append(("4", f"ภาษีมูลค่าเพิ่ม {result['vat_pct']:g}% ของค่าก่อสร้าง "
                          "(งานเอกชน)", result["after_f"] * result["vat_pct"] / 100,
                     ""))
    for no, label, val, note in rows:
        sh.add([no, label, val, note], styles=[8, 4, 5, 4])
    sh.add(["", "รวมค่าก่อสร้างทั้งโครงการงานก่อสร้าง", result["grand"], ""],
           styles=[4, 6, 7, 4])
    sh.add(["", "ราคากลาง", result["grand"], ""], styles=[4, 6, 7, 4])
    r = sh.add(["", f"ราคากลาง (ตัวอักษร)  ({baht_text(result['grand'])})", "",
                ""], styles=[4, 6, 4, 4])
    sh.merges.append(f"B{r}:D{r}")
    _sign(sh, st, 4)
    return sh


def pr_sheets(result, settings, items=None):
    st = dict(DEFAULT_SETTINGS)
    st.update(settings or {})
    pr1 = _pr1(result, st)
    pr2 = _pr2(result, st)
    sheets = [_pr4(result, st), _pr1k(result, st, len(pr1.rows)), pr1,
              _pr2k(result, st, len(pr2.rows)), pr2, _pr3(result, st),
              _boq_sheet(result, st)]
    if items is not None:
        sheets.append(_detail_sheet(items, result))
    return sheets


def boq_xlsx_bytes(result: dict, settings: dict, items=None) -> bytes:
    """The full workbook: ปร.4, ปร.1 (ก), ปร.1, ปร.2 (ก), ปร.2, ปร.3, a
    one-sheet BOQ and (with ``items``) the object detail."""
    return _xlsx(pr_sheets(result, settings, items))


def _xlsx(sheets) -> bytes:
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
