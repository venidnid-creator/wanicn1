# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
# WANICNSURVEY 3D — ถอดปริมาณงานอาคารตามหลักเกณฑ์กรมบัญชีกลาง พ.ศ. 2569
"""Bill of quantities of a WANIC ออกแบบอาคาร plan, measured the way the
2569 criteria say (:mod:`core.wanic_std2569`) rather than from the 3D mesh:

* earthwork from each footing's plan size and depth, +30 % (≤ 2 m) or
  0.50 m each side (> 2 m); backfill = excavation − footings − stumps;
* concrete by element (area × length), no overlaps: columns run floor to
  floor, beams between column faces, slabs between beams;
* formwork in m² (sides of footings, columns, beams; soffits of suspended
  beams and slabs) priced by A(0.133) + B(0.774) + C(0.25), props 1.5 per
  metre of beam soffit / m² of slab soffit;
* reinforcing bars measured straight from the library's bar schedule,
  summed by size, then each size's waste; tie wire 30 kg per tonne;
* walls centre-to-centre of columns less the column width, floor to floor
  less the beam above, less the openings; plaster and paint on each face
  (inside / outside priced apart);
* the steel roof frame by section, +3 % (gable) / +5 % (hip), counted in
  6 m pieces, then kilograms; roofing on the slope with 3 % / 5 % waste.

Every line keeps the arithmetic it came from (``basis``) and the page or
ว480 item it follows (``ref``), and its quantity is rounded to 2 decimals.

พัฒนาและรับรองโดย นายเวนิช ธัมมะวงษ์ วิศวกรสำรวจ
"""
from __future__ import annotations

import math

from core import wanic_building as B
from core import wanic_catalog as CAT
from core import wanic_profiles as P
from core import wanic_recipes2569 as RC
from core import wanic_std2569 as S
from core import wanic_w480 as W480
from core.wanic_sign import footer

GROUPS = [
    ("prep", "หมวดงานเตรียมพื้นที่"),
    ("earth", "หมวดงานดินและฐานราก"),
    ("column", "หมวดงานเสาตอม่อและเสา"),
    ("beam", "หมวดงานคาน"),
    ("slab", "หมวดงานพื้น"),
    ("stair", "หมวดงานบันได"),
    ("rebar", "หมวดงานเหล็กเสริมคอนกรีต"),
    ("wall", "หมวดงานผนัง ฉาบปูน และทาสี"),
    ("opening", "หมวดงานประตู-หน้าต่าง"),
    ("sanitary", "หมวดงานสุขภัณฑ์และอุปกรณ์"),
    ("finish", "หมวดงานพื้นผิวและฝ้าเพดาน"),
    ("roof", "หมวดงานหลังคา"),
    ("plumbing", "หมวดงานระบบประปาและสุขาภิบาล"),
    ("electric", "หมวดงานระบบไฟฟ้า"),
    ("hvac", "หมวดงานระบบปรับอากาศและระบายอากาศ"),
    ("external", "หมวดงานภายนอกอาคาร"),
    ("misc", "หมวดงานอื่นๆ"),
]
GROUP_TH = dict(GROUPS)

CONCRETE = "คอนกรีตผสมเสร็จ 240 กก./ตร.ซม. (ลูกบาศก์)"

DEFAULT_OPTIONS = {"finishes": True, "paint": True, "roofing": "tile",
                   "ready_mix": True, "wall_recipe": "6.1",
                   "plaster_recipe": "7.2", "floor_recipe": "9.30",
                   "slab_sand": 0.05, "gb_sand": 0.05, "boq_by": "cat15",
                   # เฟอร์นิเจอร์ (owner, 27 Nov): billed as ครุภัณฑ์ (หมวด 16 — no Factor F, + VAT 7 %),
                   # labour (fitting, delivery) a share of the material bought, at most 30 %
                   "furniture": True, "furn_lab_pct": 30.0}
FURN_LAB_MAX = 30.0
FURN_KEY = "ครุภัณฑ์: "                 # the price key of a furniture piece: «ครุภัณฑ์: <name>»


def options_of(data) -> dict:
    o = dict(DEFAULT_OPTIONS)
    o.update((data or {}).get("boq_options") or {})
    return o


#: A material priced by the kilogram above this (baht) was read from a list
#: that prices it by the tonne (rebar, cement, wire …): it is per tonne.
KG_PER_TONNE_ABOVE = 400.0
_KG_KEYS = None


def kg_keys() -> set:
    """Every price key whose unit is the kilogram (the standard keys and
    the 2569 recipe materials)."""
    global _KG_KEYS
    if _KG_KEYS is None:
        keys = {k for k, u in S.PRICE_KEYS if u == "กก."}
        for rc in RC.RECIPES:
            keys |= {it["name"] for it in rc.get("items", []) if it.get("unit") == "กก."}
        _KG_KEYS = keys
    return _KG_KEYS


def sane_price(key: str, value: float) -> float:
    """The price per the key's unit: a per-kilogram price that is really a
    per-tonne one (21,400 for a steel bar that costs 21.40 บาท/กก.) is
    divided by 1,000 — the mistake that put เสาเอ็น at 31,711 บาท/ม."""
    v = float(value)
    if key in kg_keys() and v > KG_PER_TONNE_ABOVE:
        return v / 1000.0
    return v


def prices_of(data) -> dict:
    p = S.empty_prices()
    obec = bool((data or {}).get("obec"))
    src = (data or {}).get("price_src") or {}
    p.update({k: sane_price(k, v) for k, v in ((data or {}).get("prices") or {})
              .items() if _isnum(v)
              # a สพฐ. price counts only in a สพฐ. job (ง6)
              and (obec or src.get(k) != "สพฐ.")})
    return p


def labour_of(data) -> dict:
    """ว480 rates, with the user's overrides (code → baht)."""
    out = {k: float(v[2]) for k, v in S.LABOUR.items()}
    obec = bool((data or {}).get("obec"))
    lsrc = (data or {}).get("labour_src") or {}
    for k, v in ((data or {}).get("labour") or {}).items():
        if _isnum(v) and (obec or k not in lsrc):
            out[S.ALIASES.get(k, k)] = float(v)
    return out


def _isnum(v) -> bool:
    try:
        return math.isfinite(float(v))
    except (TypeError, ValueError):
        return False


# ---------------------------------------------------------------------------

class _Bill:
    def __init__(self, prices, labour, zero=False):
        self.lines = []
        self.prices = prices
        self.labour = labour
        self.zero = zero                              # no province yet: every price 0

    def add(self, group, desc, net, unit, *, waste=0.0, mat=None,
            mat_key="", lab_code="", lab=None, basis="", ref="", note="", only=None):
        if net is None or net <= 1e-9:
            return None                               # only what the model has (qty > 0)
        qty = S.q2(net * (1 + waste / 100.0))
        # ทุกรายการต้องมีทั้งราคาวัสดุและค่าแรง (the owner): a line needs both,
        # except the ones that are one side by nature — a labour item (ค่าแรง…,
        # ขุดดิน, ทำความสะอาด), or a material whose labour is in another line
        # (the roof sheets and their caps, props, tie wire); a missing one is
        # «ยังไม่มีราคา» (orange) until it is priced
        side = only or one_sided(desc, unit, ref)
        need_mat = side not in ("lab", "none")
        need_lab = side not in ("mat", "none")
        mat = 0.0 if mat is None else mat
        if mat_key and not mat:
            mat = float(self.prices.get(mat_key) or 0.0)
        if not lab_code and lab is None and need_lab:
            # a line with no ว480 code still has its labour price: typed in the
            # «ค่าแรง» table under «ค่าแรง: <the line>» (the owner — both prices)
            lab_code = OWN_LAB + (mat_key or desc)
        if lab is None:
            lab = float(self.labour.get(lab_code, 0.0)) if lab_code else 0.0
        if self.zero:
            mat = lab = 0.0
        missing = ([] if not need_mat or float(mat) > 0 else ["ค่าวัสดุ"]) + \
            ([] if not need_lab or float(lab) > 0 else ["ค่าแรง"])
        if side in ("lab", "mat") and not note:
            note = "ค่าแรงอย่างเดียว" if side == "lab" else "ค่าวัสดุอย่างเดียว (ค่าแรงรวมในรายการที่เกี่ยวข้อง)"
        ln = {"group": group, "desc": desc, "net": net, "waste": waste,
              "qty": qty, "unit": unit, "mat": round(float(mat), 2),
              "lab": round(float(lab), 2), "mat_key": mat_key,
              "lab_code": lab_code, "basis": basis, "ref": ref,
              "note": note, "missing": missing}
        ln["mat_total"] = round(qty * ln["mat"], 2)
        ln["lab_total"] = round(qty * ln["lab"], 2)
        ln["total"] = round(ln["mat_total"] + ln["lab_total"], 2)
        self.lines.append(ln)
        return ln


OWN_LAB = "ค่าแรง: "                  # the key of a labour price with no ว480 code
LAB_ONLY = ("ค่าแรง", "งานขุดดิน", "งานถมดิน", "ทำความสะอาด", "ตัดกระเบื้อง", "ถางป่า", "วางผังอาคาร")
MAT_ONLY = ("ไม้ค้ำยัน", "ลวดผูกเหล็ก")


def one_sided(desc, unit, ref) -> str | None:
    """«lab» / «mat» for a line that is one side by nature, else None (both)."""
    d = str(desc or "")
    if "ใช้ดินที่ขุด" in d:
        return "none"                                 # the dug soil back: no material, labour in the dig
    if d.startswith(LAB_ONLY):
        return "lab"
    if d.startswith(MAT_ONLY) or "ค่าแรงรวม" in str(ref or "") or "ค่าแรงอยู่" in str(ref or ""):
        return "mat"
    if unit == "แผ่น" and ("กระเบื้อง" in d or d.startswith("ครอบ")):
        return "mat"                                  # sheets / caps: labour in «ค่าแรงมุง…»
    return None


#: Recipe item names that mean a price-list key under another name.
ALIASES = {"เหล็กเสริม RB Ø 6 มม.": "RB6", "เหล็กเสริม RB Ø 9 มม.": "RB9",
           "ตะปู": "ตะปูตอกไม้ 3\"", "น้ำผสมคอนกรีต": None}
#: A material the province's list seldom names, priced as the one that does
#: the same job when it has no price of its own: plaster is laid with the
#: mixed cement «สำหรับงานก่อ ฉาบ» (มอก. 80), the plaster admixture as the
#: masonry one.
FALLBACKS = {"ปูนซีเมนต์ผสม (Silica Cement)": "ปูนซีเมนต์ผสม (มอก. 80/2566)",
             "น้ำยาผสมปูนฉาบ": "น้ำยาผสมปูนก่อ"}


def recipe_price(code, prices) -> tuple[float, str]:
    rc = RC.find(code)
    if rc is None:
        return 0.0, f"ไม่พบสูตร {code}"
    p = dict(prices)
    for name, key in ALIASES.items():
        if not p.get(name):
            p[name] = prices.get(key, 0.0) if key else 0.0164
    for name, key in FALLBACKS.items():
        if not p.get(name) and p.get(key):
            p[name] = p[key]
    # «ไม้แบบคิด 50 %» is formwork per m² (A·B·C formula).
    for it in rc["items"]:
        if it["name"].startswith("ไม้แบบ") and it["unit"] == "ตร.ม.":
            p.setdefault(it["name"], S.formwork_unit_price(prices))
    cost, missing = RC.unit_cost(rc, p)
    note = ""
    if missing:
        note = "ยังไม่มีราคา: " + ", ".join(missing[:3]) + \
            (" …" if len(missing) > 3 else "")
    return cost, note


def _area3(poly) -> float:
    nx = ny = nz = 0.0
    for i, a in enumerate(poly):
        b = poly[(i + 1) % len(poly)]
        nx += (a[1] - b[1]) * (a[2] + b[2])
        ny += (a[2] - b[2]) * (a[0] + b[0])
        nz += (a[0] - b[0]) * (a[1] + b[1])
    return 0.5 * math.sqrt(nx * nx + ny * ny + nz * nz)


def _perimeter(fam, params) -> float:
    outer, _holes = P.profile_outline(fam, params)
    return sum(math.hypot(outer[i][0] - outer[i - 1][0],
                          outer[i][1] - outer[i - 1][1])
               for i in range(len(outer)))


# ---------------------------------------------------------------------------

def priced(data) -> dict:
    """The bill as the user sees and sends it: every price 0 until the
    province is chosen (ราคากลางต้องเป็นของจังหวัดที่ก่อสร้าง); each line says
    what it still lacks (``missing``), the totals how many lack a price."""
    return compute(data, gate=True)


def missing_lines(result) -> list:
    """The lines with no price yet, the BOQ shows them orange."""
    return [ln for ln in (result or {}).get("lines") or [] if ln.get("missing")]


def compute(data, gate: bool = False) -> dict:
    """``{"lines", "groups", "totals", "rebar", "notes"}`` for the plan.
    ``gate``: no province chosen → no material price and no labour rate."""
    E = B.elements(data)
    s, lib, H, n = E["settings"], E["lib"], E["H"], E["n"]
    o = options_of(data)
    prices, labour = prices_of(data), labour_of(data)
    zero = gate and not str((data or {}).get("province") or "")
    if zero:
        prices = S.empty_prices()
        labour = {k: 0.0 for k in labour}
    bill = _Bill(prices, labour, zero)
    need: dict[str, str] = {}

    def rprice(code, prices_):
        rc = RC.find(code)
        for it in (rc or {}).get("items", []):
            if "price" not in it:
                need.setdefault(it["name"], it["unit"])
        return recipe_price(code, prices_)
    notes = []
    rebar: dict[str, float] = {}

    def bars(size_len):
        for size, length in size_len:
            rebar[size] = rebar.get(size, 0.0) + length

    if not n:
        return {"lines": [], "groups": [], "totals": _totals([]),
                "rebar": {}, "need": {}, "notes": ["ยังไม่มีห้องในแปลน"],
                "province": str((data or {}).get("province") or ""),
                "price_month": str((data or {}).get("price_month") or ""),
                "price_ref": price_ref(str((data or {}).get("province") or ""),
                                       str((data or {}).get("price_month")
                                           or ""))}

    form_price = S.formwork_unit_price(prices)
    multi = n > 1
    conc_lab = ("1.7b" if multi else "1.7a") if o["ready_mix"] else \
        ("1.6.2b" if multi else "1.6.2a")
    conc_mat = prices.get(CONCRETE, 0.0) if o["ready_mix"] else \
        rprice("2.2", prices)[0]
    conc_desc = "คอนกรีตโครงสร้าง " + ("ผสมเสร็จ 240 กก./ตร.ซม." if
                                       o["ready_mix"] else "ค.3 (ผสมเอง)")
    form_total = [0.0]

    def concrete(group, what, vol, basis):
        bill.add(group, f"{conc_desc} — {what}", vol, "ลบ.ม.",
                 mat=conc_mat, lab_code=conc_lab, basis=basis,
                 ref="หลักเกณฑ์ 4.1 ข้อ 2.3 · ว480 " + conc_lab[:3])

    def formwork(group, what, area, basis):
        form_total[0] += area
        return bill.add(group, f"ไม้แบบหล่อคอนกรีต — {what}", area, "ตร.ม.",
                        mat=form_price, lab_code="1.8.1b", basis=basis,
                        ref="หลักเกณฑ์ 4.1 ข้อ 3.1.1 A(0.133)+B(0.774)+C(0.25)"
                            " · ว480 1.8.1")

    def props(group, what, count, basis):
        bill.add(group, f"ไม้ค้ำยัน — {what}", count, "ต้น",
                 mat_key=S.PROP_NAME, basis=basis,
                 ref="หลักเกณฑ์ 4.1 ข้อ 3.1.2–3.1.3 (1.5 ท่อน)",
                 note="ค่าแรงรวมในงานไม้แบบ")

    # --- 1. Earthwork and footings ----------------------------------------
    g = "earth"
    by_mark: dict[str, int] = {}
    for e in E["footings"]:
        by_mark[e["mark"]] = by_mark.get(e["mark"], 0) + 1
    exc_net = exc_tot = 0.0
    exc_basis, sand = [], 0.0
    lean = conc_f = form_f = 0.0
    deepest = 0.0
    f_basis, pile_n = [], {}
    for mark, cnt in by_mark.items():
        f = lib[mark]
        w, l, t = float(f["w"]), float(f["l"]), float(f["t"])
        depth = float(f["depth"])
        deepest = max(deepest, depth)
        dig_depth = depth if depth <= S.EXCAVATION_DEEP else \
            depth + float(f.get("sand") or 0) + float(f.get("lean") or 0)
        net, tot, how = S.excavation(w, l, dig_depth)
        exc_net += net * cnt
        exc_tot += tot * cnt
        exc_basis.append(f"{mark}: {w:g}×{l:g}×{dig_depth:g} × {cnt} ({how})")
        sand += w * l * float(f.get("sand") or 0) * cnt
        lean += w * l * float(f.get("lean") or 0) * cnt
        conc_f += w * l * t * cnt
        form_f += 2 * (w + l) * t * cnt
        f_basis.append(f"{mark}: {w:g}×{l:g}×{t:g} × {cnt}")
        sp = S.parse_bar(f.get("bars", ""))
        if sp and sp[2]:
            _n, size, spc = sp
            from core import wanic_rc as RC_                # the calc book's and the drawings' count
            nx, ny = RC_.mesh_count(l, spc), RC_.mesh_count(w, spc)
            bars([(size, (nx * w + ny * l) * cnt)])
        if int(f.get("piles") or 0) > 0:
            pile_n[mark] = pile_n.get(mark, 0) + int(f["piles"]) * cnt
    code = S.excavation_labour_code(exc_tot, deepest)
    shallow = deepest <= S.EXCAVATION_DEEP
    exc = bill.add(g, "งานขุดดินฐานราก", exc_net if shallow else exc_tot,
                   "ลบ.ม.", waste=S.EXCAVATION_WASTE if shallow else 0.0,
                   lab_code=code, basis="; ".join(exc_basis),
                   ref="หลักเกณฑ์ 4.1 ข้อ 1 (ลึก ≤ 2 ม. เผื่อ 30% / ลึกเกิน "
                       "2 ม. เผื่อข้างละ 0.50 ม.) · ว480 1.3.1")
    gl = float(E.get("GL", 0.0))
    stump_below = sum(float(lib[e["mark"]]["b"]) * float(lib[e["mark"]]["h"])
                      * max(min(e["z1"], gl) - e["z0"], 0.0) for e in E["stumps"])
    if exc:
        bill.add(g, "งานถมดินคืน (ใช้ดินที่ขุด)",
                 exc["qty"] - conc_f - stump_below, "ลบ.ม.",
                 basis=f"ดินขุด {exc['qty']:.2f} − ฐานราก {conc_f:.2f} − "
                       f"เสาตอม่อ {stump_below:.2f}",
                 ref="หลักเกณฑ์ 4.1 ข้อ 1 (การถมคืน)",
                 note="ค่าแรงรวมใน ว480 1.3 (ขุดหลุมฐานรากและถมคืน)")
    for mark, cnt in pile_n.items():
        f = lib[mark]
        nm = f.get("pile_name") or f"เสาเข็ม {float(f['pile_b']):g}×{float(f['pile_b']):g}"
        bill.add(g, f"{nm} ยาว {float(f['pile_len']):g} ม. ({mark}{' · ' + f['pile'] if f.get('pile') else ''})",
                 cnt, "ต้น",
                 basis=f"{f['piles']} ต้น/ฐาน", ref="หลักเกณฑ์ 4.1 ข้อ 1",
                 note="ค่าแรงตอกเข็มตาม ว480 1.1–1.2 (ขึ้นกับจำนวน/พื้นที่)")
    bill.add(g, "ทรายรองก้นหลุม (บดอัดด้วยแรงคน)", sand, "ลบ.ม.",
             waste=S.BEDDING_WASTE["ทราย"], mat_key="ทรายหยาบ",
             lab_code="1.5", basis="กว้าง×ยาว×หนาทราย × จำนวนฐาน",
             ref="หลักเกณฑ์ 4.1 ข้อ 2.1 (เผื่อ 25%) · ว480 1.5")
    lean_price, lean_note = rprice("1.1", prices)
    bill.add(g, "คอนกรีตหยาบรองก้นหลุม 1:3:5", lean, "ลบ.ม.",
             mat=lean_price, lab_code="1.6.1",
             basis="กว้าง×ยาว×หนา × จำนวนฐาน",
             ref="หลักเกณฑ์ 4.1 ข้อ 2.2 · สูตรวัสดุ 1.1 · ว480 1.6.1",
             note=lean_note)
    concrete(g, "ฐานราก", conc_f, "; ".join(f_basis))
    formwork(g, "ฐานราก", form_f, "2×(กว้าง+ยาว)×หนา × จำนวนฐาน")

    # --- 2. Stumps and columns --------------------------------------------
    g = "column"
    gb_h = float(lib["GB1"]["h"])
    for kind, rows, label in (("stump", E["stumps"], "เสาตอม่อ"),
                              ("column", E["columns"], "เสา")):
        vol = area = 0.0
        basis = {}
        for e in rows:
            c = lib[e["mark"]]
            b, h = float(c["b"]), float(c["h"])
            height = e["z1"] - e["z0"]
            vol += b * h * height
            if kind == "stump":
                clear = height - gb_h
            else:
                lvl = e["floor"] + 1
                above = [lib[bm["mark"]]["h"] for bm in E["beams"]
                         if bm["level"] == lvl and (
                             (abs(bm["p0"][0] - e["x"]) < 1e-6 and
                              abs(bm["p0"][1] - e["y"]) < 1e-6) or
                             (abs(bm["p1"][0] - e["x"]) < 1e-6 and
                              abs(bm["p1"][1] - e["y"]) < 1e-6))]
                clear = height - (max(above) if above else 0.0)
            area += 2 * (b + h) * max(clear, 0.0)
            key = (e["mark"], round(height, 3))
            basis[key] = basis.get(key, 0) + 1
            sp = S.parse_bar(c.get("main", ""))
            if sp and sp[0]:
                bars([(sp[1], sp[0] * height)])
            tp = S.parse_bar(c.get("tie", ""))
            if tp and tp[2]:
                bars([(tp[1], S.bar_count(height, tp[2]) * 2 * (b + h))])
        txt = "; ".join(f"{m}: {lib[m]['b']:g}×{lib[m]['h']:g}×{hh:g} × {k}"
                        for (m, hh), k in basis.items())
        concrete(g, label, vol, txt)
        formwork(g, label, area, "2×(กว้าง+ลึก)×ความสูงใต้ท้องคาน")

    # --- 3. Beams --------------------------------------------------------
    g = "beam"
    for which, title in (("ground", "คานคอดิน"), ("mid", "คานชั้นบน"),
                         ("roof", "คานหลังคา")):
        vol = area = soffit = sand_gb = 0.0
        basis = {}
        for e in E["beams"]:
            kind = "ground" if e["ground"] else "roof" if e["roof"] else "mid"
            if kind != which:
                continue
            bm = lib[e["mark"]]
            b, h = float(bm["b"]), float(bm["h"])
            L = math.hypot(e["p1"][0] - e["p0"][0], e["p1"][1] - e["p0"][1])
            clear = max(L - _col_half(E, lib, e["p0"], e["level"]) -
                        _col_half(E, lib, e["p1"], e["level"]), 0.0)
            vol += b * h * clear
            basis[e["mark"]] = basis.get(e["mark"], 0.0) + clear
            if kind == "ground":
                area += 2 * h * clear
                sand_gb += b * clear * float(o["gb_sand"])
            else:
                t = _slab_t_at(E, lib, e)
                area += (b + 2 * (h - t) if t else b + 2 * h) * clear
                soffit += clear
            sp = S.parse_bar(bm.get("top", ""))
            if sp and sp[0]:
                bars([(sp[1], sp[0] * L)])
            sp = S.parse_bar(bm.get("bot", ""))
            if sp and sp[0]:
                bars([(sp[1], sp[0] * L)])
            tp = S.parse_bar(bm.get("stir", ""))
            if tp and tp[2]:
                from core import wanic_rc as RC_            # the calc book's count: closer over 2h at the ends
                bars([(tp[1], RC_.stirrup_count(clear, bm) * 2 * (b + h))])
        if not vol:
            continue
        txt = "; ".join(f"{m}: {lib[m]['b']:g}×{lib[m]['h']:g}× ยาวสุทธิ "
                        f"{L_:.2f} ม." for m, L_ in basis.items())
        if sand_gb:
            bill.add(g, f"ทรายรองใต้{title}", sand_gb, "ลบ.ม.",
                     waste=S.BEDDING_WASTE["ทราย"], mat_key="ทรายหยาบ",
                     lab_code="1.4", basis="กว้าง×ยาวสุทธิ×หนาทราย",
                     ref="หลักเกณฑ์ 4.1 ข้อ 2.1 (เผื่อ 25%) · ว480 1.4")
        concrete(g, title, vol, txt + " (ความยาวระหว่างหน้าเสา)")
        formwork(g, title, area,
                 "ข้าง 2×ลึก" if which == "ground"
                 else "ท้อง + ข้าง 2×(ลึก−หนาพื้น)")
        if soffit:
            props(g, title, soffit * S.PROPS_PER_M_BEAM,
                  f"ท้องคานยาว {soffit:.2f} ม. × 1.5")

    # --- 3b. เขียนแบบอิสระ: free beams and columns ----------------------
    from core import wanic_free as FR
    fr = FR.free_of(data)
    for key, g_, title in (("beams", "beam", "คาน (เขียนอิสระ: เอียง/โค้ง)"), ("columns", "column", "เสา (เขียนอิสระ)")):
        vol = area = 0.0
        txt = []
        for el in fr[key]:
            spec = lib.get(el.get("mark"), lib["B1" if key == "beams" else "C1"])
            b, h = float(spec.get("b", 0.2)), float(spec.get("h", 0.2))
            L = FR.length3(el["pts"]) if key == "beams" else float(el["z1"]) - float(el["z0"])
            vol += b * h * L
            area += (b + 2 * h if key == "beams" else 2 * (b + h)) * L
            txt.append(f"{el.get('mark')} {b:g}×{h:g}×{L:.2f}")
            main = [spec.get("top", ""), spec.get("bot", "")] if key == "beams" else [spec.get("main", "")]
            for t_ in main:
                sp = S.parse_bar(t_ or "")
                if sp and sp[0]:
                    bars([(sp[1], sp[0] * L)])
            tp = S.parse_bar(spec.get("stir" if key == "beams" else "tie", "") or "")
            if tp and tp[2]:
                from core import wanic_rc as RC_
                n_ = RC_.stirrup_count(L, spec) if key == "beams" else S.bar_count(L, tp[2])
                bars([(tp[1], n_ * 2 * (b + h))])
        if vol:
            concrete(g_, title, vol, "; ".join(txt) + " (ยาวตามแนวจริง)")
            formwork(g_, title, area, "ท้อง + ข้าง 2 ด้าน" if key == "beams" else "รอบเสา")

    # --- 4. Slabs --------------------------------------------------------
    g = "slab"
    holes = B.holes_by_floor(E)                       # ช่องบันได: not cast, not tiled, no ceiling
    for ground, title in ((True, "พื้นวางบนดิน"), (False, "พื้นชั้นบน")):
        vol = soffit = sand_s = 0.0
        basis = {}
        planks: dict = {}                             # พื้นสำเร็จรูป: mark → area
        for e in E["slabs"]:
            sl = lib[e["mark"]]
            on_ground = bool(int(sl.get("ground") or 0)) and e["floor"] == 0
            if on_ground != ground:
                continue
            if not ground and B.is_precast(sl):
                rm = e["room"]
                bw = float(lib[ROLE_beam(e["floor"], n)]["b"])
                area = max(float(rm["w"]) - bw, 0) * max(float(rm["d"]) - bw, 0)
                area = max(area - B.hole_area((rm["x"], rm["y"], rm["x"] + rm["w"], rm["y"] + rm["d"]),
                                              holes.get(e["floor"]) or []), 0.0)
                planks[e["mark"]] = planks.get(e["mark"], 0.0) + area
                vol += area * float(sl.get("topping") or 0.05)      # the cast-in-place topping only
                basis[e["mark"]] = basis.get(e["mark"], 0.0) + area
                sp = S.parse_bar(sl.get("bars", ""))
                if sp and sp[2]:
                    w_, d_ = float(rm["w"]), float(rm["d"])
                    bars([(sp[1], S.bar_count(d_, sp[2]) * w_ + S.bar_count(w_, sp[2]) * d_)])
                continue
            rm = e["room"]
            bw = float(lib[ROLE_beam(e["floor"], n)]["b"])
            area = max(float(rm["w"]) - bw, 0) * max(float(rm["d"]) - bw, 0)
            area = max(area - B.hole_area((rm["x"], rm["y"], rm["x"] + rm["w"], rm["y"] + rm["d"]),
                                          holes.get(e["floor"]) or []), 0.0)
            t = float(sl["t"])
            vol += area * t
            basis[e["mark"]] = basis.get(e["mark"], 0.0) + area
            if ground:
                sand_s += area * float(o["slab_sand"])
            else:
                soffit += area
            sp = S.parse_bar(sl.get("bars", ""))
            if sp and sp[2]:
                w_, d_ = float(rm["w"]), float(rm["d"])
                bars([(sp[1], S.bar_count(d_, sp[2]) * w_ +
                       S.bar_count(w_, sp[2]) * d_)])
        if not vol:
            continue
        for m_, a_ in planks.items():
            nm = f"แผ่นพื้นคอนกรีตสำเร็จรูป ({m_}) วางบนคาน"
            bill.add(g, nm, a_, "ตร.ม.", mat_key=f"แผ่นพื้นสำเร็จรูป {m_} (ราคาผู้ผลิต รวมขนส่ง)",
                     basis="พื้นที่สุทธิระหว่างคาน (หักช่องเปิด)",
                     ref="ราคาผู้ผลิต · ค่าแรงวางแผ่นตามท้องตลาด")
        txt = "; ".join(f"{m}: พื้นที่สุทธิ {a:.2f} ตร.ม. × หนา "
                        f"{(float(lib[m].get('topping') or 0.05) if B.is_precast(lib[m]) else float(lib[m]['t'])):g}"
                        + (" (topping บนพื้นสำเร็จรูป)" if B.is_precast(lib[m]) else "")
                        for m, a in basis.items())
        if sand_s:
            bill.add(g, "ทรายรองพื้น (บดอัดด้วยแรงคน)", sand_s, "ลบ.ม.",
                     waste=S.BEDDING_WASTE["ทราย"], mat_key="ทรายหยาบ",
                     lab_code="1.4", basis="พื้นที่พื้นสุทธิ × หนาทราย",
                     ref="หลักเกณฑ์ 4.1 ข้อ 2.1 (เผื่อ 25%) · ว480 1.4")
        concrete(g, title, vol, txt + " (พื้นที่ระหว่างคาน)")
        if soffit:
            formwork(g, title, soffit, "ท้องพื้นสุทธิ")
            props(g, title, soffit * S.PROPS_PER_M2_SLAB,
                  f"ท้องพื้น {soffit:.2f} ตร.ม. × 1.5")

    # --- 5. Stairs -------------------------------------------------------
    g = "stair"
    vol = area = 0.0
    for e in E["stairs"]:
        lay = B.stair_layout(e["st"], s)
        w = lay["w"]
        ts = float(s["stair_t"])
        for fi, f in enumerate(lay["flights"]):
            nr, L, Hs = f["n"], f["L"], f["n"] * lay["R"]
            tl_ = B.landing_t(lay, ts)
            fill = dict(d=tl_ * 1000 if f["z0"] > 1e-6 else 0.0,           # as the 3D model: full at the
                        tl=0.0 if fi == len(lay["flights"]) - 1 else tl_ * 1000)  # landing joints
            sec = P.section_area("stair", dict(L=L * 1000, H=Hs * 1000, n=nr, t=ts * 1000, **fill))
            vol += sec * w
            slope = math.hypot(L, Hs)
            area += slope * w + 2 * sec + nr * (Hs / nr) * w
            bars([("DB12", S.bar_count(w, 0.15) * slope),
                  ("RB9", S.bar_count(slope, 0.20) * w)])
        for ld in lay["landings"]:
            xs = [q[0] for q in ld["pts"]]
            ys = [q[1] for q in ld["pts"]]
            a_ = (max(xs) - min(xs)) * (max(ys) - min(ys))
            vol += a_ * B.landing_t(lay, ts)
            area += a_ + 2 * (max(xs) - min(xs) + max(ys) - min(ys)) * ts
            bars([("DB12", S.bar_count(max(ys) - min(ys), 0.15) * (max(xs) - min(xs))),
                  ("RB9", S.bar_count(max(xs) - min(xs), 0.20) * (max(ys) - min(ys)))])
        z_ = e["floor"] * E["H"]
        for sb in B.stair_beams(e["st"], s, z_, B.stair_cols(E, e["floor"])):       # คานรับบันได SB1 / SB2
            Lb = math.dist(sb["p0"][:2], sb["p1"][:2])
            vol += sb["b"] * sb["h"] * Lb
            area += (sb["b"] + 2 * sb["h"]) * Lb
            bars([("DB12", 4 * Lb), ("RB6", S.bar_count(Lb, 0.15) * 2 * (sb["b"] + sb["h"]))])
        for sp_ in B.stair_posts(e["st"], s, z_, B.stair_cols(E, e["floor"])):      # เสารับคานชานพัก
            Hp = sp_["p1"][2] - sp_["p0"][2]
            vol += sp_["b"] ** 2 * Hp
            area += 4 * sp_["b"] * Hp
            bars([("DB12", 4 * Hp), ("RB6", S.bar_count(Hp, 0.15) * 4 * sp_["b"])])
    if vol:
        concrete(g, "บันได", vol, "พื้นที่หน้าตัดขั้นบันได × กว้าง + ชานพัก + คาน/เสารับบันได")
        formwork(g, "บันได", area, "ท้องบันได + ข้าง 2 ด้าน + ลูกตั้ง")
    outline = B.building_outline(E)
    rail = sum(B.stair_railing(e["st"], s, B.floor_bounds(E, e["floor"]))["length"] for e in E["stairs"]) + sum(
        math.dist(a, b) for e in E["stairs"] if e["floor"] + 1 < E["n"]
        for a, b in B.well_railing(e["st"], s, outline))
    if rail:                                          # ราวบันได as the standard plans
        posts = sum(len(B.stair_railing(e["st"], s, B.floor_bounds(E, e["floor"]))["posts"]) for e in E["stairs"])
        bill.add(g, B.RAIL_TEXT, rail, "ม.", waste=5.0, mat_key="ราวบันไดไม้เนื้อแข็ง 2\"x4\"",
                 basis=f"ราวบันไดตามแนวลาด + ราวกันตกรอบช่องบันไดชั้นบน รวม {rail:.2f} ม. · "
                       f"ลูกกรงบันได {posts} ต้น (ทุกขั้น) สูง {B.RAIL_H:.2f} ม.",
                 ref="แบบมาตรฐานกรมโยธาธิการและผังเมือง (แบบขยายบันได)")

    # --- 6. Reinforcing bars by size --------------------------------------
    g = "rebar"
    total_kg = 0.0
    for size in sorted(rebar, key=lambda k: (k[:2], int(k[2:]))):
        length = rebar[size]
        kg = length * S.REBAR_KG_M[size]
        w = float(S.REBAR_WASTE[size])
        ln = bill.add(g, f"เหล็กเสริม {size}", kg, "กก.", waste=w,
                      mat_key=size,
                      lab=labour.get(S.rebar_labour_key(size), 0.0) / 1000.0,
                      lab_code=S.rebar_labour_key(size),
                      basis=f"ยาวรวม {length:.2f} ม. × {S.REBAR_KG_M[size]} "
                            f"กก./ม.",
                      ref=f"หลักเกณฑ์ 4.1 ข้อ 4 (เผื่อ {w:g}%) · ว480 "
                          f"{S.rebar_labour_key(size)} (บาท/ตัน ÷ 1,000)")
        if ln:
            total_kg += ln["qty"]
    bill.add(g, "ลวดผูกเหล็ก", total_kg * S.TIE_WIRE_PER_TONNE / 1000.0,
             "กก.", mat_key="ลวดผูกเหล็ก",
             basis=f"เหล็กเสริมรวม {total_kg:,.2f} กก. × 30/1,000",
             ref="หลักเกณฑ์ 4.1 ข้อ 4 (30 กก./ตัน)",
             note="ค่าแรงรวมในงานผูกเหล็ก")

    # --- 7. Walls, plaster, wall tiles, paint ----------------------------
    g = "wall"
    col_b = float(lib["C1"]["b"])
    tiles: dict[str, float] = {}
    if s.get("walls"):
        wall_a = ext_face = int_face = 0.0
        by_type: dict = {}
        band_w = float(s.get("band", 0.10))
        for wl in E["walls"]:
            ops = sum(op_w * op_h for op_w, op_h, _sl in
                      (B.opening_size(op, s) for op in wl["openings"]))
            bh = float(lib[wl["beam"]]["h"])
            a = S.wall_area(wl["L"], col_b, H, bh, ops)
            net = a
            if band_w > 0:
                for op in wl["openings"]:
                    ow, oh, sill = B.opening_size(op, s)
                    net -= band_w * B.band_length(
                        ow, oh, sill, op.get("type", "door") != "window",
                        band_w, H - bh)
                net = max(net, 0.0)
            wall_a += a
            sp = B.wall_spec(s, bool(wl["exterior"]))
            key = (bool(wl["exterior"]), sp["recipe"])
            by_type[key] = by_type.get(key, 0.0) + net
            if wl["exterior"]:
                ext_face += a
                int_face += a
            else:
                int_face += 2 * a
        # Brick infill from the top ring beam up to the roof on gable ends
        # and the sides of a shed roof (outside plaster on one face).
        if s.get("roof") in B.ROOF_TYPES:
            for inf in B.gable_infill(data):
                a = float(inf["area"])
                wall_a += a
                sp = B.wall_spec(s, True)
                key = (True, sp["recipe"])
                by_type[key] = by_type.get(key, 0.0) + a
                ext_face += a
        # free walls (เขียนอิสระ, straight or curved): interior brick, plaster both faces
        from core import wanic_free as FR
        for wl in FR.free_of(data)["walls"]:
            hh = float(wl.get("h") or 0.0) or H - float(lib["B1"]["h"])
            a = FR.length2(wl["pts"]) * hh
            wall_a += a
            sp = B.wall_spec(s, bool(wl.get("exterior")))
            key = (bool(wl.get("exterior")), sp["recipe"])
            by_type[key] = by_type.get(key, 0.0) + a
            int_face += a if wl.get("exterior") else 2 * a
            ext_face += a if wl.get("exterior") else 0.0
        # Wall tiles inside rooms that have them (bathroom, kitchen …).
        for e in E["slabs"]:
            rm = e["room"]
            fin = CAT.finish_of(rm)
            if not fin["wall_tile"] or fin["tile_h"] <= 0:
                continue
            k = e["floor"]
            th = min(fin["tile_h"], H - float(lib["B1"]["h"]))
            per = 2 * (float(rm["w"]) + float(rm["d"])) - 4 * col_b
            cut = 0.0
            for op in E["openings"]:
                if op["floor"] != k or not B._on_edge(
                        rm, float(op["op"]["x"]), float(op["op"]["y"])):
                    continue
                cut += op["w"] * max(0.0, min(op["sill"] + op["h"], th)
                                     - op["sill"])
            area = max(per * th - cut, 0.0)
            tiles[fin["wall_tile"]] = tiles.get(fin["wall_tile"], 0.0) + area
        tile_a = sum(tiles.values())
        # เสาเอ็น–ทับหลัง ค.ส.ล. round every opening (4 sides; a door has
        # none at the floor), as the 3D band.
        band = float(s.get("band", 0.10))
        band_m = 0.0
        if band > 0:
            for op in E["openings"]:
                above = "RB1" if op["floor"] == n - 1 else "B1"
                wh = H - float(lib[above]["h"])
                band_m += B.band_length(op["w"], op["h"], op["sill"],
                                        op["type"] != "window", band, wh)
        wall_a -= band_m * band
        for (ext, code), area in sorted(by_type.items(), key=lambda kv: not kv[0][0]):
            wp, wnote = rprice(code, prices)
            rc = RC.find(code)
            side = "ผนังภายนอก" if ext else "ผนังภายใน"
            bill.add(g, f"{side} — " + (rc["name"] if rc else B.WALL_TYPES[code][0]),
                     area, "ตร.ม.", mat=wp, lab_code=S.wall_labour_code(code),
                     basis="(ยาวศูนย์–ศูนย์เสา − กว้างเสา)×(สูงพื้นถึงพื้น − "
                           "ลึกคาน) − ช่องเปิด − เสาเอ็น/ทับหลัง",
                     ref=f"หลักเกณฑ์ 4.2 ข้อ 3.1 · สูตรวัสดุ {code}"
                         " · ว480 2.3.1", note=wnote)
        if band_m:
            full = max(B.wall_spec(s, True)["t"], B.wall_spec(s, False)["t"]) >= 0.15
            code = "4.2" if full else "4.1"
            bp_, bn_ = rprice(code, prices)
            bill.add(g, f"เสาเอ็นและคานทับหลัง ค.ส.ล. รอบประตู-หน้าต่าง "
                        f"(กว้าง {band * 100:.0f} ซม.)", band_m, "ม.", mat=bp_,
                     lab_code="2.3.1f" if full else "2.3.1e",
                     basis="รอบช่องเปิดทั้ง 4 ด้าน (ประตูไม่มีด้านพื้น)",
                     ref=f"สูตรวัสดุ {code} · ว480 2.3.1", note=bn_)
        pp, pnote = rprice(o["plaster_recipe"], prices)
        bill.add(g, "ฉาบปูนเรียบ ผนังภายใน", int_face - tile_a, "ตร.ม.",
                 mat=pp, lab_code="2.3.1.2a",
                 basis="พื้นที่ผนังด้านภายในทุกด้าน − ส่วนที่บุกระเบื้อง",
                 ref=f"หลักเกณฑ์ 4.2 ข้อ 3.2 · สูตรวัสดุ "
                     f"{o['plaster_recipe']} · ว480 2.3.1.2", note=pnote)
        po = B.wall_spec(s, True)["po"]
        bill.add(g, f"ฉาบปูนเรียบ ผนังภายนอก (หนา {po * 100:g} ซม.)", ext_face,
                 "ตร.ม.", mat=pp * (po / 0.015 if po > 0 else 1.0),
                 lab_code="2.3.1.2b", basis="พื้นที่ผนังด้านนอกอาคาร",
                 ref=f"หลักเกณฑ์ 4.2 ข้อ 3.2 · สูตรวัสดุ "
                     f"{o['plaster_recipe']} · ว480 2.3.1.2", note=pnote)
        if tile_a:
            bp, bnote = rprice("7.1", prices)
            bill.add(g, "ฉาบปูนทรายรองพื้น (สำหรับบุกระเบื้องผนัง)", tile_a,
                     "ตร.ม.", mat=bp, lab_code="2.3.1.2d",
                     basis="เท่าพื้นที่บุกระเบื้อง",
                     ref="หลักเกณฑ์ 4.2 ข้อ 3.2 · สูตรวัสดุ 7.1 · ว480 2.3.1.2",
                     note=bnote)
            for code, area in tiles.items():
                rc = RC.find(code)
                name = rc["name"] if rc else f"ผนังบุกระเบื้อง (สูตร {code})"
                tp, tnote = rprice(code, prices)
                bill.add(g, name, area, "ตร.ม.", mat=tp,
                         lab_code=CAT.wall_tile_labour_code(name),
                         basis="(เส้นรอบห้อง − กว้างเสา) × ความสูงบุ − ช่องเปิด",
                         ref=f"หลักเกณฑ์ 4.2 ข้อ 3.3 · สูตรวัสดุ {code} · "
                             "ว480 2.3.1.3", note=tnote)
        if o["paint"]:
            bill.add(g, "ทาสีน้ำอะครีลิค ภายใน (รองพื้น 1 + จริง 2 เที่ยว)",
                     int_face - tile_a, "ตร.ม.",
                     mat_key="สีน้ำอะครีลิค ภายใน (ต่อ ตร.ม.)",
                     lab_code="2.8.1a", basis="เท่าพื้นที่ฉาบเรียบภายใน",
                     ref="สูตรวัสดุ 10.2 · ว480 2.8.1")
            bill.add(g, "ทาสีน้ำอะครีลิค ภายนอก (รองพื้น 1 + จริง 2 เที่ยว)",
                     ext_face, "ตร.ม.",
                     mat_key="สีน้ำอะครีลิค ภายนอก (ต่อ ตร.ม.)",
                     lab_code="2.8.1b", basis="เท่าพื้นที่ฉาบภายนอก",
                     ref="สูตรวัสดุ 10.1 · ว480 2.8.1")

    # --- 8. Doors and windows: frame, leaves, hardware, glass ------------
    g = "opening"
    sets: dict[tuple, int] = {}
    for op in E["openings"]:
        code, _spec = CAT.opening_type(op["op"])
        key = (code, round(op["w"], 3), round(op["h"], 3))
        sets[key] = sets.get(key, 0) + 1
    for (code, w, h), cnt in sorted(sets.items()):
        spec = CAT.OPENING_TYPES[code]
        door = spec["kind"] == "door"
        area = w * h
        tag = f"{code} {spec['name']} {w:.2f}×{h:.2f} ม."
        ref = "หลักเกณฑ์ 4.2 ข้อ 5.1–5.2"
        if spec["frame"] == "alu":
            bill.add(g, f"{tag} — ชุดอลูมิเนียมพร้อมกระจกและอุปกรณ์", cnt, "ชุด",
                     mat_key=f"{tag} (ชุดอลูมิเนียม)", basis="นับตามแบบ",
                     ref=ref, note="ราคาวัสดุพร้อมติดตั้งจากการสืบราคา")
            continue
        fl = "2.5.2a" if door else "2.5.2b"
        bill.add(g, f"{tag} — วงกบ", cnt, "ชุด", mat_key=f"{tag} — วงกบ",
                 lab=area * labour.get(fl, 0.0),
                 basis=f"นับตามแบบ · ค่าแรง {area:.2f} ตร.ม./ชุด",
                 ref=f"{ref} · ว480 2.5.2")
        if spec["leaves"] and spec["leaf"] != "none":
            lc = ("2.5.3b" if spec["leaf"] == "prefab" else "2.5.3") \
                if door else "2.5.3c"
            leaf_a = area / spec["leaves"]
            bill.add(g, f"{tag} — บาน", cnt * spec["leaves"], "บาน",
                     mat_key=f"{tag} — บาน", lab=leaf_a * labour.get(lc, 0.0),
                     basis=f"{spec['leaves']} บาน/ชุด · ค่าแรง {leaf_a:.2f} "
                           "ตร.ม./บาน", ref=f"{ref} · ว480 2.5.3")
        if spec["slide"]:
            sc = "2.5.5" if door else "2.5.6"
            bill.add(g, f"{tag} — อุปกรณ์บานเลื่อน (ราง ลูกล้อ กุญแจ มือจับ)",
                     cnt, "ชุด", mat_key=f"{tag} — อุปกรณ์", lab_code=sc,
                     basis="นับตามแบบ", ref=f"{ref} · ว480 {sc}")
        elif door:
            bill.add(g, f"{tag} — อุปกรณ์ (ลูกบิด กุญแจ บานพับ กันชน)", cnt,
                     "ชุด", mat_key=f"{tag} — อุปกรณ์", lab_code="2.5.4",
                     basis="นับตามแบบ", ref=f"{ref} · ว480 2.5.4")
        if spec["glass"] > 0:
            sqft = area * spec["glass"] * CAT.SQFT_PER_M2
            bill.add(g, f"{tag} — กระจกใส 5 มม.", sqft * cnt, "ตร.ฟ.",
                     mat_key="กระจกใส 5 มม.", lab_code="2.5.7",
                     basis=f"{area * spec['glass']:.2f} ตร.ม. × 10.764 × {cnt}",
                     ref=f"{ref} (กระจกคิดเป็น ตร.ฟ.) · ว480 2.5.7")

    # --- 9. Sanitary ware --------------------------------------------------
    g = "sanitary"
    fx: dict[str, int] = {}
    for e in E["fixtures"]:
        t = e["fx"].get("type")
        if t in CAT.SANITARY:
            fx[t] = fx.get(t, 0) + 1
    for t, cnt in fx.items():
        name, item, _rate, *_r = CAT.SANITARY[t]
        bill.add(g, name, cnt, "ชุด", mat_key=name, lab_code=item,
                 basis="นับตามแบบ", ref=f"ว480 {item}")

    # --- 10. Floors and ceilings by room ----------------------------------
    g = "finish"
    if o["finishes"]:
        wt = float(s["wall_t"])
        floors: dict[str, float] = {}
        ceiling = 0.0
        for e in E["slabs"]:
            rm = e["room"]
            fin = CAT.finish_of(rm, o["floor_recipe"])
            a = max(float(rm["w"]) - wt, 0) * max(float(rm["d"]) - wt, 0)
            a = max(a - B.hole_area((rm["x"], rm["y"], rm["x"] + rm["w"], rm["y"] + rm["d"]),
                                    holes.get(e["floor"]) or []), 0.0)
            floors[fin["floor"]] = floors.get(fin["floor"], 0.0) + a
            if fin["ceiling"]:
                ceiling += a
        for code, a in floors.items():
            rc = RC.find(code)
            name = rc["name"] if rc else f"พื้น (สูตร {code})"
            fp, fnote = rprice(code, prices)
            lc = CAT.floor_labour_code(code, name)
            bill.add(g, name, a, "ตร.ม.", mat=fp, lab_code=lc,
                     basis="พื้นที่ริมผนังถึงริมผนัง",
                     ref=f"หลักเกณฑ์ 4.2 ข้อ 4.2 · สูตรวัสดุ {code} · "
                         f"ว480 {lc[:5]}", note=fnote)
        # interior ceilings by type (dry rooms / wet rooms), with the
        # frame, wall angle and hangers (ครบชุด) in the material price
        ceil: dict = {}
        cper: dict = {}
        soffit_a = 0.0
        for e in E["slabs"]:
            rm, k = e["room"], e["floor"]
            ct = B.ceiling_on(E, rm, k)
            if ct == "none" or not CAT.finish_of(rm, o["floor_recipe"])["ceiling"]:
                if k < E["n"] - 1 and B.ceiling_type(s, rm) != "none":   # no board: the slab soffit is finished
                    x0, y0, x1, y1 = B.room_inner(E, rm, k)
                    soffit_a = soffit_a + (x1 - x0) * (y1 - y0) - B.hole_area((x0, y0, x1, y1),
                                                                              holes.get(k + 1) or [])
                continue
            x0, y0, x1, y1 = B.room_inner(E, rm, k)
            ceil[ct] = ceil.get(ct, 0.0) + (x1 - x0) * (y1 - y0) - B.hole_area((x0, y0, x1, y1),
                                                                                holes.get(k + 1) or [])
            cper[ct] = cper.get(ct, 0.0) + 2 * ((x1 - x0) + (y1 - y0))
        for ct, area in ceil.items():
            name, lab, frame, sub, main = B.CEILING_TYPES[ct]
            bill.add(g, name, area, "ตร.ม.",
                     mat_key=f"{name} (วัสดุครบชุด)",
                     lab=float(W480.rate(lab)) if lab != "2.2.2" else None,
                     lab_code=lab,
                     basis=f"พื้นที่ห้องระหว่างผิวผนัง · โครงซอย @{sub:.2f} ม. "
                           f"โครงหลัก/ลวดแขวน @{main:.2f} ม. ฉากริมผนัง {cper[ct]:.1f} ม.",
                     ref=f"หลักเกณฑ์ 4.2 ข้อ 2.1 · สูตรวัสดุ 5.42 · ว480 {lab}")
        if soffit_a > 0:                              # ฝ้าเฉพาะชั้นบนสุด: below, the slab's soffit
            pp_, pn_ = rprice(o["plaster_recipe"], prices)
            bill.add(g, "ฉาบปูนเรียบท้องพื้น ค.ส.ล. (ชั้นที่ไม่มีฝ้า)", soffit_a, "ตร.ม.", mat=pp_,
                     lab_code="2.3.1.2a", basis="พื้นที่ห้องชั้นล่างที่ไม่มีฝ้า (ฝ้าเฉพาะชั้นบนสุด)",
                     ref=f"หลักเกณฑ์ 4.2 ข้อ 3.2 · สูตรวัสดุ {o['plaster_recipe']} · ว480 2.3.1.2", note=pn_)
            if o["paint"]:
                bill.add(g, "ทาสีน้ำอะครีลิค ท้องพื้น (รองพื้น 1 + จริง 2 เที่ยว)", soffit_a, "ตร.ม.",
                         mat_key="สีน้ำอะครีลิค ภายใน (ต่อ ตร.ม.)", lab_code="2.8.1a",
                         basis="เท่าพื้นที่ฉาบท้องพื้น", ref="สูตรวัสดุ 10.2 · ว480 2.8.1")
        # skirting / cornice (ปุ่มบัวผนัง)
        # บัวเชิงผนัง by type (each room its own — dragged onto it — or the house's)
        sk_len: dict = {}
        for e in E["slabs"]:
            sk = B.room_skirting(s, e["room"])
            if sk and B._has_trim(E, e["room"], "skirting", e["floor"]):
                sk_len[sk] = sk_len.get(sk, 0.0) + B.trim_length(E, e["room"], e["floor"])
        for sk, L in sk_len.items():
            name, lab, _h, _t, rate = B.SKIRTING_TYPES[sk]
            bill.add(g, name, L, "ม.", mat_key=f"{name} (วัสดุ)", lab=float(rate),
                     lab_code=lab, basis="รอบห้องตามผิวผนัง หักช่องประตู "
                                         "(ห้องที่บุกระเบื้องผนังสูง ≥ 1.20 ม. ไม่มีบัว)",
                     ref=f"ว480 {lab}")
        if s.get("cornice"):
            name, lab, _h, _t = B.CORNICE
            L = 0.0
            for e in E["slabs"]:
                if B._has_trim(E, e["room"], "cornice", e["floor"]):
                    x0, y0, x1, y1 = B.room_inner(E, e["room"], e["floor"])
                    L += 2 * ((x1 - x0) + (y1 - y0))
            bill.add(g, name, L, "ม.", mat_key=f"{name} (วัสดุ)", lab_code=lab,
                     basis="รอบห้องที่มีฝ้า", ref="ว480 2.2.5")

    # --- 11. Roof --------------------------------------------------------
    g = "roof"
    lines = B.roof_lines(data)
    if lines:
        # a มะนิลา is hipped (its waste and tiling are the hip's)
        roof = "hip" if s["roof"] == "manila" else s["roof"]
        tcode, tile = CAT.roof_tile(s)
        per: dict[str, float] = {}
        for kind in ("ridge", "hip", "rafter", "post"):
            n2 = 2 if s.get(f"dbl_{kind}") else 1          # วางคู่: 2 ตัว
            for path in lines[kind]:
                per[s[kind]] = per.get(s[kind], 0.0) + n2 * P.path_length(path)
        for path in lines.get("valleys") or []:          # ตะเฆ่ราง
            n2 = 2 if s.get("dbl_valley") else 1
            per[s["hip"]] = per.get(s["hip"], 0.0) + n2 * P.path_length(path)
        for pl in lines["purlin"]:
            per[s["purlin"]] = per.get(s["purlin"], 0.0) + \
                P.path_length(pl["path"], pl["closed"])
        for key, kind in (("wallplate", "plate"), ("tiebeam", "tie"),
                          ("tiebeam", "rbeam"), ("strut", "strut"),
                          ("strut", "brace")):    # อะเส ขื่อ คานรับดั้ง ตุ๊กตา ค้ำยัน
            n2 = 2 if kind == "plate" and s.get("dbl_wallplate") else 1
            for path in lines.get(kind) or []:
                per[s[key]] = per.get(s[key], 0.0) + n2 * P.path_length(path)
        paint_a = 0.0
        for label, length in per.items():
            fam, params = B.steel_lookup(label)
            kgm = P.weight_per_m(fam, params)
            with_w, pieces = S.steel_pieces(length, roof)
            kg = pieces * S.STEEL_BAR_LENGTH * kgm
            bill.add(g, f"โครงหลังคาเหล็ก {label}", kg, "กก.",
                     mat_key="เหล็กรูปพรรณ (ทั่วไป)", lab_code="1.11.1",
                     basis=f"ยาว {length:.2f} ม. + {S.STEEL_ROOF_WASTE.get(roof, 3.0):g}%"
                           f" = {with_w:.2f} ม. → {pieces} ท่อน × 6 ม. × "
                           f"{kgm:.2f} กก./ม.",
                     ref="หลักเกณฑ์ 4.1 ข้อ 6.3 · ว480 1.11.1")
            paint_a += pieces * S.STEEL_BAR_LENGTH * _perimeter(fam, params)
        heads = len(lines.get("heads") or []) if s.get("head_plate", True) and \
            (lines.get("plate") or lines.get("tie")) else 0
        if heads:
            pk, bk = B.head_plate_kg()
            hp = B.HEAD_PLATE
            bill.add(g, f"เพลทหัวเสา PL {hp['b'] * 1000:.0f}×{hp['b'] * 1000:.0f}×"
                        f"{hp['t'] * 1000:.0f} มม.", heads * pk, "กก.",
                     mat_key="เหล็กรูปพรรณ (ทั่วไป)", lab_code="1.11.3",
                     basis=f"{heads} หัวเสา × {pk:.2f} กก.",
                     ref="ว480 1.11.3 (ตัดประกอบ/เชื่อม)")
            bill.add(g, f"J-bolt {hp['n']}-{hp['bolt']} ฝังหัวเสา {hp['embed']:.2f} ม.",
                     heads * bk, "กก.", mat_key=hp["bolt"],
                     lab=labour.get("1.10.2", 0.0) / 1000.0, lab_code="1.10.2",
                     basis=f"{heads} หัวเสา × {hp['n']} เส้น × "
                           f"{hp['embed'] + hp['hook'] + hp['stick']:.2f} ม. × 0.888 กก./ม.",
                     ref="ว480 1.10.2 (บาท/ตัน ÷ 1,000)")
            paint_a += heads * 2 * hp["b"] * hp["b"]
        if s.get("fish_plate", True):
            nf = len(B.fish_joints(lines, s))
            if nf:
                lp_, hp_, tp_ = B.FISH_PLATE
                bill.add(g, f"เหล็กประกับหางปลา PL {lp_ * 1000:.0f}×{hp_ * 1000:.0f}×{tp_ * 1000:.0f} มม. "
                            "(ยึดจันทันกับอะเส ตะเฆ่ อกไก่)", nf * B.fish_plate_kg(), "กก.",
                         mat_key="เหล็กรูปพรรณ (ทั่วไป)", lab_code="1.11.3",
                         basis=f"{nf} จุด × 2 แผ่น × {B.fish_plate_kg() / 2:.2f} กก.",
                         ref="ว480 1.11.3 (ตัดประกอบ/เชื่อม)")
                paint_a += nf * 2 * 2 * lp_ * hp_
        bill.add(g, "ทาสีกันสนิมโครงหลังคาเหล็ก", paint_a, "ตร.ม.",
                 mat_key="สีกันสนิม", lab_code="2.8.3",
                 basis="เส้นรอบรูปหน้าตัด × ความยาวทุกท่อน",
                 ref="หลักเกณฑ์ 4.1 ข้อ 6.4 · ว480 2.8.3")
        eave = sum(P.path_length(p) for p in lines["eave"])
        barge = sum(P.path_length(p) for p in lines["barge"])
        if s.get("fascia", True):
            fk = "เชิงชายไม้สำเร็จรูป 1\"×8\" + ทับเชิงชาย 1\"×6\""
            bill.add(g, "เชิงชาย + ทับเชิงชาย ไม้สำเร็จรูป (ไม้เทียม)", eave,
                     "ม.", mat_key=fk, lab_code="2.1.10a",
                     basis="ความยาวตามแนวชายคาทุกด้าน",
                     ref="ว480 2.1.10 (เชิงชาย + ทับเชิงชาย)")
            bill.add(g, "ปั้นลม + ทับปั้นลม ไม้สำเร็จรูป (ไม้เทียม)", barge,
                     "ม.", mat_key=fk, lab_code="2.1.10a",
                     basis="ความยาวตามแนวลาดหน้าจั่ว",
                     ref="ว480 2.1.10")
            if tcode != "R7":
                bill.add(g, "ปิดนก (P.V.C) สำเร็จรูป", eave, "ม.",
                         mat_key="ปิดนก P.V.C สำเร็จรูป", lab_code="2.1.10b",
                         basis="ความยาวตามแนวชายคา", ref="ว480 2.1.10")
        slope = sum(_area3(p) for p in lines["skin"])
        waste = S.ROOFING_WASTE.get(roof, 3.0)
        la, lr, lv = tile["lab"]
        if la == "2.1.1" and roof == "hip":
            la = "2.1.1h"
        if tile["unit"] == "ตร.ม.":
            bill.add(g, tile["name"], slope, "ตร.ม.", waste=waste,
                     mat_key=tile["name"], lab_code=la,
                     basis="พื้นที่ตามแนวลาดเอียง",
                     ref=f"หลักเกณฑ์ 4.2 ข้อ 1.4 · ว480 {la[:5]}")
        else:
            per = CAT.tiles_per_m2(tile, s)
            ew, el = tile["eff"]
            bill.add(g, tile["name"], slope * per, "แผ่น", waste=waste,
                     mat_key=tile["name"],
                     basis=f"พื้นที่ลาดเอียง {slope:.2f} ตร.ม. × {per:.2f} แผ่น/"
                           f"ตร.ม. ตามคู่มือผู้ผลิต (ระยะใช้งาน {ew:.2f}×{el:.2f} ม./แผ่น)",
                     ref=f"หลักเกณฑ์ 4.2 ข้อ 1.1 (เผื่อ {waste:g}%)")
            bill.add(g, f"ค่าแรงมุง{tile['name']}", slope, "ตร.ม.",
                     lab_code=la, basis="พื้นที่ตามแนวลาดเอียง",
                     ref=f"หลักเกณฑ์ 4.2 ข้อ 1.4 · ว480 {la[:5]}")
        # Special cap pieces where ridges, hips and verges meet (SCG/CPAC).
        if s.get("caps", True) and tile["unit"] != "ตร.ม.":
            from core import wanic_roofclip as RCL
            acc = RCL.accessories(lines)
            for key in ("gable_end", "verge_end", "hip_end", "two_way",
                        "three_way", "four_way"):
                if acc.get(key):
                    nm = f"{CAT.ACCESSORIES[key]} ({tile['name'].split(' ')[0]})"
                    bill.add(g, nm, acc[key], "แผ่น", mat_key=nm,
                             basis="นับจากจุดต่อของสัน ตะเข้ และปั้นลม",
                             ref="หลักเกณฑ์ 4.2 ข้อ 1.2 (ค่าแรงรวมในงานครอบ)")
        if s.get("gutters", True):
            runs = B.gutter_runs(lines, s)
            glen = sum(math.hypot(b_[0] - a_[0], b_[1] - a_[1]) for a_, b_, _n in runs)
            if glen > 0.05:
                bill.add(g, "รางน้ำชายคาไวนิล/สังกะสี 6\" พร้อมตะขอแขวนและข้อต่อ", glen, "ม.",
                         mat_key="รางน้ำชายคา 6\" (รวมตะขอ/ข้อต่อ)", lab_code="2.1.10c",
                         basis="ความยาวแนวชายคาที่น้ำไหลลง", ref="ว480 2.1.10")
                spouts = sum(max(2, 1 + int(math.ceil(math.hypot(b_[0] - a_[0], b_[1] - a_[1])
                                                     / 10.0))) for a_, b_, _n in runs)
                spouts = max(len(runs), spouts - len(runs))       # corners are shared
                h_sp = E["n"] * E["H"] + B.floor_lift(s)
                bill.add(g, "ท่อลงน้ำ (งวงช้าง) PVC Ø 3\" พร้อมแคลมป์และข้องอ", spouts * h_sp, "ม.",
                         mat_key="ท่อลงน้ำ PVC 3\" (รวมแคลมป์/ข้องอ)",
                         basis=f"{spouts} จุด × สูง {h_sp:.2f} ม.", ref="มยผ. 1201")
        valley = float(lines.get("valley") or 0.0)
        if valley > 0.05:
            bill.add(g, "รางน้ำตะเข้สำเร็จรูป (สแตนเลส)", valley, "ม.",
                     mat_key="รางน้ำตะเข้สำเร็จรูป (สแตนเลส)",
                     lab_code="2.1.10c", basis="ความยาวแนวตะเข้ราง (หลังคาตัว L/T)",
                     ref="ว480 2.1.10")
            cut = {"2.1.3": "2.1.3c", "2.1.7": "2.1.7r"}.get(tile["lab"][0])
            if cut:
                bill.add(g, "ตัดกระเบื้องตะเข้ราง", valley, "ม.", lab_code=cut,
                         basis="ความยาวแนวตะเข้ราง", ref=f"ว480 {cut[:5]}")
        if s.get("soffit", True):
            soffit = B.soffit_area(data)
            if soffit > 0.01:
                sp_, snote = rprice("5.41", prices)
                bill.add(g, "ฝ้าชายคาระแนงไม้เทียม โครงคร่าวเหล็กชุบสังกะสี "
                            "พร้อมมุ้งกันแมลง", soffit, "ตร.ม.", mat=sp_,
                         lab_code="2.2.1c",
                         basis="พื้นที่ใต้ชายคา จากหน้าคานถึงเชิงชาย",
                         ref="หลักเกณฑ์ 4.2 ข้อ 2.1 · สูตรวัสดุ 5.41 · "
                             "ว480 2.2.1 (ฝ้าตีเว้นร่อง ไม้เทียม)", note=snote)
        if s.get("caps", True):
            ridge = sum(P.path_length(p) for p in lines["ridge"])
            hips = sum(P.path_length(p) for p in lines["hip"])
            cap_unit = "ม." if tile["unit"] == "ตร.ม." else "แผ่น"
            for label, length, lc in (("ครอบสัน", ridge, lr),
                                      ("ครอบตะเข้สัน", hips, lr),
                                      ("ครอบข้าง/ครอบปั้นลม", barge, lv)):
                if length <= 0:
                    continue
                if cap_unit == "แผ่น":
                    each = tile["verge"] if lc == lv else tile["cap"]
                    pieces = length / each
                    bill.add(g, f"{label} — {tile['cap_name']}", pieces,
                             "แผ่น", waste=3.0, mat_key=tile["cap_name"],
                             basis=f"ยาว {length:.2f} ม. × {1 / each:.1f} แผ่น/ม.",
                             ref="หลักเกณฑ์ 4.2 ข้อ 1.2 (เผื่อ 3%)")
                else:
                    bill.add(g, f"{label} — {tile['cap_name']}", length, "ม.",
                             waste=3.0, mat_key=tile["cap_name"],
                             basis=f"ยาว {length:.2f} ม.",
                             ref="หลักเกณฑ์ 4.2 ข้อ 1.2 (เผื่อ 3%)")
                bill.add(g, f"ค่าแรง{label}", length, "ม.", lab_code=lc,
                         basis="ความยาวตามแนวสัน/ตะเข้/ปั้นลม",
                         ref=f"ว480 {lc[:5]}")

    # Formwork labour tier by the project's total formwork area.
    tier = "1.8.1a" if form_total[0] >= 5000 else "1.8.1b"
    for ln in bill.lines:
        if ln["lab_code"].startswith("1.8.1"):
            ln["lab_code"] = tier
            ln["lab"] = round(labour.get(tier, 0.0), 2)
            ln["lab_total"] = round(ln["qty"] * ln["lab"], 2)
            ln["total"] = round(ln["mat_total"] + ln["lab_total"], 2)
    province = str((data or {}).get("province") or "")
    month = str((data or {}).get("price_month") or "")
    src = (data or {}).get("price_src") or {}
    where = (data or {}).get("price_note") or {}
    items = (data or {}).get("price_item") or {}
    unpriced = set()
    if province:
        for ln in bill.lines:
            k = ln["mat_key"]
            if not k:
                continue
            note = market_note(province, src.get(k), prices.get(k) or 0,
                               where.get(k, ""), items.get(k, ""))
            if note:
                ln["note"] = (ln["note"] + " · " if ln["note"] else "") + note
                if not prices.get(k):
                    unpriced.add(k)
        lsrc = (data or {}).get("labour_src") or {}
        if (data or {}).get("obec"):
            for ln in bill.lines:
                it = lsrc.get(ln["lab_code"])
                if it and ln["lab"]:
                    ln["note"] = (ln["note"] + " · " if ln["note"] else "") + \
                        f"ไม่มีในบัญชี ว480 — ใช้ค่าแรง สพฐ. ({it})"
            notes.append("งานของ สพฐ.: ค่าแรงใช้บัญชี ว480 กรมบัญชีกลางก่อน ราคาวัสดุใช้"
                         f"พาณิชย์จังหวัด{province}ก่อน — ที่ไม่มีจึงใช้บัญชี สพฐ. "
                         "(หมายเหตุบอกรหัสในบัญชี แก้ไขได้)")
        if unpriced:
            notes.append(f"ไม่พบราคาที่จังหวัด{province}ประกาศ {len(unpriced)} "
                         "รายการ — ให้สืบราคาตามท้องตลาด ณ จังหวัดนี้ แล้วกรอกใน"
                         "แท็บ «ฐานข้อมูลราคา»")
    if not province:
        notes.append("ยังไม่ได้เลือกจังหวัด — เลือกจังหวัดด้านบนเพื่อใช้ราคาวัสดุ"
                     "ของสำนักงานพาณิชย์จังหวัดนั้น")
    if not any(prices.values()):
        notes.append("ยังไม่มีราคาวัสดุ — กรอกราคาจากสำนักงานพาณิชย์จังหวัด "
                     "(หรือกด «ราคาตัวอย่าง» เพื่อทดลอง)")
    notes.append("ขนาดชิ้นส่วนและเหล็กเสริมเป็นค่าเริ่มต้น — "
                 "วิศวกรผู้ออกแบบต้องกำหนดตามแบบจริง")
    from core import wanic_mep as MEP

    def _mep_add(group, desc, qty, unit, **kw):
        return bill.add(group, desc, qty, unit, **kw)
    MEP.bill(data, E, _mep_add, labour)
    # วัตถุที่คัดลอกในโมเดล (owner, 27 Nov): more material and price, as built anew
    from core import wanic_copies as CP
    CP.copy_lines((data or {}).get("copies") or [], list(bill.lines), bill.add)
    from core import wanic_categories as CG
    for ln in bill.lines:
        ln["cat"] = CG.line_category(ln["group"], ln["desc"])
    # the items typed in for หมวด 16–19 (ครุภัณฑ์ วัสดุ)
    for it in (data or {}).get("extra_items") or []:
        try:
            cat = int(it.get("cat", 16))
            qty = float(it.get("qty") or 0)
        except (TypeError, ValueError):
            continue
        if cat not in CG.EXTRA or qty <= 0:
            continue
        ln = bill.add("extra", str(it.get("desc") or CG.NAME[cat]), qty,
                      str(it.get("unit") or "ชุด"), mat=float(it.get("mat") or 0),
                      lab=float(it.get("lab") or 0),
                      ref=CG.CATEGORIES[cat - 1][3], note=str(it.get("note") or ""))
        if ln is not None:
            ln["cat"] = cat
            ln["extra_id"] = it.get("id", "")
    # เฟอร์นิเจอร์และเครื่องใช้ในโมเดล → หมวด 16 ครุภัณฑ์: no Factor F, VAT 7 %, labour ≤ 30 % of
    # the material (the owner — editable in the options)
    if o.get("furniture", True):
        from core import wanic_catalog as CATF
        pct = min(max(float(o.get("furn_lab_pct", FURN_LAB_MAX) or 0.0), 0.0), FURN_LAB_MAX)
        counts: dict = {}
        for e in E["fixtures"]:
            t = (e.get("fx") or {}).get("type")
            if t in CATF.FURNITURE and t not in ("WZ",):
                counts[t] = counts.get(t, 0) + 1
        for t, n_ in sorted(counts.items(), key=lambda kv: CATF.DECOR[kv[0]][0]):
            name = CATF.DECOR[t][0]
            key = FURN_KEY + name
            need.setdefault(key, "ชุด")                   # listed in the price table to be typed in
            mp = 0.0 if zero else float(prices.get(key) or 0.0)
            ln = bill.add("extra", f"ครุภัณฑ์: {name}", n_, "ชุด", mat=mp, mat_key=key,
                          lab=round(mp * pct / 100.0, 2),
                          basis=f"เฟอร์นิเจอร์ในโมเดล {n_} ชุด · ค่าแรงติดตั้ง/ขนส่ง {pct:g} % ของค่าวัสดุ",
                          ref="หมวด 16 ครุภัณฑ์ — ไม่คูณ Factor F · บวกภาษีมูลค่าเพิ่ม 7 %",
                          note="กรอกราคาในแท็บฐานข้อมูลราคา (ชื่อ «" + key + "»)")
            if ln is not None:
                ln["cat"] = 16
                ln["furniture"] = t
    groups = []
    if o.get("boq_by", "cat15") == "cat15":
        # the 15 หมวดงาน (งานเตรียมพื้นที่ … งานอื่นๆ)
        for no, _name, _icon, _ex in CG.CATEGORIES:
            rows = [ln for ln in bill.lines if ln["cat"] == no]
            if rows:
                groups.append((f"c{no}", CG.title(no), rows))
    else:
        for key, th in GROUPS:
            rows = [ln for ln in bill.lines if ln["group"] == key]
            if rows:
                groups.append((key, th, rows))
        for no in CG.EXTRA:
            rows = [ln for ln in bill.lines if ln.get("cat") == no]
            if rows:
                groups.append((f"c{no}", CG.title(no), rows))
    for ln in bill.lines:
        if ln["mat_key"]:
            need.setdefault(ln["mat_key"], S.price_unit(ln["mat_key"]) or
                            ln["unit"])
    if form_total[0]:
        for k, _q, u in S.FORMWORK_RECIPE:
            need.setdefault(k, u)
    return {"lines": bill.lines, "groups": groups, "need": need,
            "totals": _totals(bill.lines), "rebar": rebar, "notes": notes,
            "province": province, "price_month": month,
            "price_ref": price_ref(province, month),
            "footer": footer("WANIC ออกแบบอาคาร"),
            "zero": zero, "missing": sum(1 for ln in bill.lines if ln.get("missing"))}


def market_note(province: str, src, price: float, where: str = "",
                item: str = "") -> str:
    """The หมายเหตุ of a line's material price: the commerce office's item
    it came from, or that the province does not announce one."""
    if src == "พาณิชย์" and price:
        return f"ราคาพาณิชย์จ.{province}: {item}" if item else ""
    if src == "ข้างเคียง" and price:
        return (f"ไม่พบราคาที่จังหวัด{province}ประกาศ — ใช้ราคาพาณิชย์จังหวัดข้างเคียง"
                + (f" ({item})" if item else ""))
    if src == "สพฐ." and price:
        return (f"ไม่พบราคาที่จังหวัด{province}ประกาศ — ใช้ราคาวัสดุ สพฐ."
                + (f" ({item})" if item else ""))
    if src == "ตัวอย่าง" and price:
        return "ราคาตัวอย่าง — ไม่ใช่ราคาที่จังหวัดประกาศ"
    if not price:
        return (f"ไม่พบราคาที่จังหวัด{province}ประกาศ — ต้องใช้ราคาตามท้องตลาด "
                f"ณ จังหวัด{province}")
    if src in ("ท้องตลาด", "กรอกเอง", None):
        return (f"ไม่พบราคาที่จังหวัด{province}ประกาศ — ใช้ราคาตามท้องตลาด"
                + (f" ({where})" if where else ""))
    return ""


def price_ref(province: str, month: str = "") -> str:
    """``ราคาวัสดุ: สำนักงานพาณิชย์จังหวัด… ประจำเดือน …`` (or "")."""
    if not province:
        return ""
    office = ("สำนักงานพาณิชย์จังหวัด" + province if province != "กรุงเทพมหานคร"
              else "กระทรวงพาณิชย์ (กรุงเทพมหานคร)")
    return f"ราคาวัสดุ: {office}" + (f" ประจำเดือน {month}" if month else "")


def ROLE_beam(floor, n) -> str:  # noqa: N802 — reads as a lookup
    return B.ROLE_DEFAULT["GB" if floor == 0 else "B"]


def _col_half(E, lib, p, level) -> float:
    """Half the width of the column standing at ``p`` for a beam level."""
    rows = E["stumps"] if level == 0 else [
        c for c in E["columns"] if c["floor"] == level - 1]
    for c in rows:
        if abs(c["x"] - p[0]) < 1e-6 and abs(c["y"] - p[1]) < 1e-6:
            return float(lib[c["mark"]]["b"]) / 2
    return float(lib["C1"]["b"]) / 2


def _slab_t_at(E, lib, beam) -> float:
    """Slab thickness meeting a suspended beam (0 under a roof)."""
    if beam["roof"]:
        return 0.0
    k = beam["level"]
    ts = [float(lib[e["mark"]]["t"]) for e in E["slabs"] if e["floor"] == k]
    return max(ts) if ts else 0.0


VAT_PCT = 7.0


def _totals(lines) -> dict:
    """Material, labour, the ค่างานต้นทุน (หมวด 1–15 and 17), Factor F
    (กรมบัญชีกลาง ว 481, งานก่อสร้างอาคาร: no advance payment, no
    retention, VAT 7 % — the usual case; the takeoff can set others), and
    what is priced without F: ครุภัณฑ์จัดซื้อ + VAT 7 %, วัสดุ, วัสดุคงทน.
    ``with_f`` is the whole price: work × F + those."""
    from core import wanic_categories as CG
    mat = round(sum(ln["mat_total"] for ln in lines), 2)
    lab = round(sum(ln["lab_total"] for ln in lines), 2)
    no_f = [ln for ln in lines if ln.get("cat") in CG.NO_F]
    cost = round(sum(ln["total"] for ln in lines) - sum(ln["total"] for ln in no_f), 2)
    buy = round(sum(ln["total"] for ln in no_f if ln.get("cat") in CG.ADD_VAT), 2)
    buy_vat = round(buy * VAT_PCT / 100.0, 2)
    supply = round(sum(ln["total"] for ln in no_f if ln.get("cat") not in CG.ADD_VAT), 2)
    F, note = factor_f(cost)
    after_f = round(cost * F, 2)
    return {"mat": mat, "lab": lab, "total": round(mat + lab, 2), "work": cost,
            "F": F, "f_note": note, "after_f": after_f, "equip": buy,
            "equip_vat": buy_vat, "supply": supply,
            "no_f": round(buy + buy_vat + supply, 2),
            "with_f": round(after_f + buy + buy_vat + supply, 2)}


def factor_f(cost: float) -> tuple[float, str]:
    """(Factor F, how it was found) for a building whose ค่างานต้นทุน is
    ``cost`` baht — 1.0 for nothing to price."""
    if cost <= 0:
        return 1.0, ""
    from core import wanic_factor_f as FF
    try:
        r = FF.lookup(cost, kind="building")
        return r.value, r.note()
    except ValueError as e:                        # pragma: no cover - table gap
        return 1.0, str(e)


# ---------------------------------------------------------------------------
# Hand-off to WANIC ถอดปริมาณ (ปร.1–ปร.4)
# ---------------------------------------------------------------------------

def to_rates(result) -> list[dict]:
    """The BOQ as manual-quantity price lines for the takeoff, one category
    per หมวด, so its ปร.1–ปร.4 workbook prints them."""
    from core.wanic_takeoff import new_rate
    out = []
    gi = 0
    for _key, th, rows in result["groups"]:
        gi += 1
        for li, ln in enumerate(rows, 1):
            note = ln["ref"]
            if ln["waste"]:
                note = f"เผื่อ {ln['waste']:g}% · " + note
            if ln["note"]:
                note += " · " + ln["note"]
            cat = ln.get("cat")
            section = ("equip" if cat == 16 else "supply" if cat == 18 else
                       "durable" if cat == 19 else "work")
            out.append(new_rate(
                id=f"std{gi}.{li}", category=th, code=f"{gi}.{li}",
                desc=ln["desc"], by="all", value="", qty="manual",
                manual_qty=ln["qty"], unit=ln["unit"], mat=ln["mat"],
                lab=ln["lab"], note=note, section=section))
    return out


#: where a material price came from (``data["price_src"]``), in the words of the status
SOURCE_TH = {"พาณิชย์": "พาณิชย์จังหวัดที่ก่อสร้าง", "ข้างเคียง": "พาณิชย์จังหวัดข้างเคียง",
             "ส่วนกลาง": "ราคาส่วนกลาง (กรุงเทพมหานคร)", "สพฐ.": "บัญชีราคา สพฐ.",
             "ท้องตลาด": "สืบราคาท้องตลาด/กรอกเอง", "กรอกเอง": "สืบราคาท้องตลาด/กรอกเอง",
             "ตัวอย่าง": "ราคาตัวอย่าง (ไม่ใช่ราคาจริง)"}


def price_status(data, result) -> dict:
    """การหาราคาวัสดุตอนนี้ (owner, 27 Nov — «หลังจากนำข้อมูลเข้ามาทั้ง 2 กรณีแล้ว ยังมีอีกกี่รายการ
    ที่ยังไม่ได้บันทึก»): of the materials the bill needs, how many are priced and from where
    (the province, which neighbouring provinces, central, typed in) and how many are still
    missing — as kinds of material and as BOQ lines (one line may need several materials,
    one material may be in several lines)."""
    data = data or {}
    prices = prices_of(data)
    src = data.get("price_src") or {}
    item = data.get("price_item") or {}
    need = list((result or {}).get("need") or {})
    by: dict = {}
    neighbours: dict = {}
    missing = []
    for k in need:
        if not float(prices.get(k) or 0) > 0:
            missing.append(k)
            continue
        th = SOURCE_TH.get(src.get(k), "สืบราคาท้องตลาด/กรอกเอง")
        by[th] = by.get(th, 0) + 1
        if src.get(k) == "ข้างเคียง":
            nb = str(item.get(k, "")).split(":", 1)[0].replace("จ.", "").strip() or "ไม่ระบุ"
            neighbours[nb] = neighbours.get(nb, 0) + 1
    lines = missing_lines(result)
    return {"province": str(data.get("province") or ""), "need": len(need), "priced": len(need) - len(missing),
            "by": by, "neighbours": neighbours, "missing": missing, "lines": len((result or {}).get("lines") or []),
            "missing_lines": len(lines), "missing_line_names": [ln["desc"] for ln in lines]}


def status_rows(st: dict) -> list:
    """The status as rows (for the CSV and the window)."""
    rows = [["สถานะการหาราคาวัสดุ (ณ วันที่บันทึก)"],
            ["จังหวัดที่ก่อสร้าง", st["province"] or "ยังไม่ได้เลือก"],
            ["วัสดุที่ต้องมีราคา (ชนิด)", st["need"]],
            ["มีราคาแล้ว (ชนิด)", st["priced"]]]
    for th, n in sorted(st["by"].items(), key=lambda t: -t[1]):
        rows.append(["  — " + th, n])
    for nb, n in sorted(st["neighbours"].items(), key=lambda t: -t[1]):
        rows.append(["      จังหวัด" + nb, n])
    rows += [["ยังไม่มีราคา (ชนิด)", len(st["missing"])],
             ["บรรทัด BOQ ทั้งหมด", st["lines"]],
             ["บรรทัด BOQ ที่ยังไม่มีราคา (แถวสีส้ม)", st["missing_lines"]],
             ["หมายเหตุ", "วัสดุ 1 ชนิดอาจอยู่หลายบรรทัด และ 1 บรรทัดอาจใช้วัสดุหลายชนิด — "
                          "ตัวเลขชนิดกับบรรทัดจึงไม่เท่ากัน · บรรทัดจะหายจากสีส้มเมื่อวัสดุทุกชนิดของบรรทัดนั้นมีราคา"]]
    if st["missing"]:
        rows.append(["วัสดุที่ยังไม่มีราคา", " · ".join(st["missing"])])
    return rows


def csv_text(result, status: dict | None = None) -> str:
    import csv
    import io
    buf = io.StringIO()
    w = csv.writer(buf)
    if status is not None:
        for r in status_rows(status):
            w.writerow(r)
        w.writerow([])
    w.writerow(["หมวด", "ลำดับ", "รายการ", "ปริมาณสุทธิ", "เผื่อ %",
                "ปริมาณ", "หน่วย", "ค่าวัสดุ/หน่วย", "ค่าวัสดุ",
                "ค่าแรง/หน่วย", "ค่าแรง", "รวม", "ที่มา", "การคำนวณ", "หมายเหตุ", "สถานะราคา"])
    for gi, (_k, th, rows) in enumerate(result["groups"], 1):
        for li, ln in enumerate(rows, 1):
            w.writerow([th, f"{gi}.{li}", ln["desc"], f"{ln['net']:.4f}",
                        f"{ln['waste']:g}", f"{ln['qty']:.2f}", ln["unit"],
                        f"{ln['mat']:.2f}", f"{ln['mat_total']:.2f}",
                        f"{ln['lab']:.2f}", f"{ln['lab_total']:.2f}",
                        f"{ln['total']:.2f}", ln["ref"], ln["basis"], ln.get("note", ""),
                        ("ยังไม่มี" + "และ".join(ln["missing"])) if ln.get("missing") else "มีราคาแล้ว"])
    t = result["totals"]
    w.writerow(["", "", "รวมค่างานต้นทุน", "", "", "", "", "",
                f"{t['mat']:.2f}", "", f"{t['lab']:.2f}", f"{t['total']:.2f}",
                "", ""])
    w.writerow([result.get("footer", footer())])
    return buf.getvalue()
