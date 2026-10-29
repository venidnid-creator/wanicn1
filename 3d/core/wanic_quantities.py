# SPDX-License-Identifier: GPL-3.0-or-later
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
from core import wanic_profiles as P
from core import wanic_recipes2569 as RC
from core import wanic_std2569 as S
from core.wanic_sign import footer

GROUPS = [
    ("earth", "หมวดงานดินและฐานราก"),
    ("column", "หมวดงานเสาตอม่อและเสา"),
    ("beam", "หมวดงานคาน"),
    ("slab", "หมวดงานพื้น"),
    ("stair", "หมวดงานบันได"),
    ("rebar", "หมวดงานเหล็กเสริมคอนกรีต"),
    ("wall", "หมวดงานผนัง ฉาบปูน และทาสี"),
    ("opening", "หมวดงานประตู-หน้าต่าง"),
    ("finish", "หมวดงานพื้นผิวและฝ้าเพดาน"),
    ("roof", "หมวดงานหลังคา"),
]
GROUP_TH = dict(GROUPS)

CONCRETE = "คอนกรีตผสมเสร็จ 240 กก./ตร.ซม. (ลูกบาศก์)"

DEFAULT_OPTIONS = {"finishes": True, "paint": True, "roofing": "tile",
                   "ready_mix": True, "wall_recipe": "6.1",
                   "plaster_recipe": "7.2", "floor_recipe": "9.30",
                   "slab_sand": 0.05, "gb_sand": 0.05}


def options_of(data) -> dict:
    o = dict(DEFAULT_OPTIONS)
    o.update((data or {}).get("boq_options") or {})
    return o


def prices_of(data) -> dict:
    p = S.empty_prices()
    p.update({k: float(v) for k, v in ((data or {}).get("prices") or {})
              .items() if _isnum(v)})
    return p


def labour_of(data) -> dict:
    """ว480 rates, with the user's overrides (code → baht)."""
    out = {k: float(v[2]) for k, v in S.LABOUR.items()}
    for k, v in ((data or {}).get("labour") or {}).items():
        if _isnum(v):
            out[k] = float(v)
    return out


def _isnum(v) -> bool:
    try:
        return math.isfinite(float(v))
    except (TypeError, ValueError):
        return False


# ---------------------------------------------------------------------------

class _Bill:
    def __init__(self, prices, labour):
        self.lines = []
        self.prices = prices
        self.labour = labour

    def add(self, group, desc, net, unit, *, waste=0.0, mat=0.0,
            mat_key="", lab_code="", lab=None, basis="", ref="", note=""):
        if net is None or net <= 1e-9:
            return None
        qty = S.q2(net * (1 + waste / 100.0))
        if mat_key and not mat:
            mat = float(self.prices.get(mat_key) or 0.0)
        if lab is None:
            lab = float(self.labour.get(lab_code, 0.0)) if lab_code else 0.0
        ln = {"group": group, "desc": desc, "net": net, "waste": waste,
              "qty": qty, "unit": unit, "mat": round(float(mat), 2),
              "lab": round(float(lab), 2), "mat_key": mat_key,
              "lab_code": lab_code, "basis": basis, "ref": ref,
              "note": note}
        ln["mat_total"] = round(qty * ln["mat"], 2)
        ln["lab_total"] = round(qty * ln["lab"], 2)
        ln["total"] = round(ln["mat_total"] + ln["lab_total"], 2)
        self.lines.append(ln)
        return ln


def recipe_price(code, prices) -> tuple[float, str]:
    rc = RC.find(code)
    if rc is None:
        return 0.0, f"ไม่พบสูตร {code}"
    cost, missing = RC.unit_cost(rc, prices)
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

def compute(data) -> dict:
    """``{"lines", "groups", "totals", "rebar", "notes"}`` for the plan."""
    E = B.elements(data)
    s, lib, H, n = E["settings"], E["lib"], E["H"], E["n"]
    o = options_of(data)
    prices, labour = prices_of(data), labour_of(data)
    bill = _Bill(prices, labour)
    notes = []
    rebar: dict[str, float] = {}

    def bars(size_len):
        for size, length in size_len:
            rebar[size] = rebar.get(size, 0.0) + length

    if not n:
        return {"lines": [], "groups": [], "totals": _totals([]),
                "rebar": {}, "notes": ["ยังไม่มีห้องในแปลน"]}

    form_price = S.formwork_unit_price(prices)
    multi = n > 1
    conc_lab = ("1.7b" if multi else "1.7a") if o["ready_mix"] else \
        ("1.6.2b" if multi else "1.6.2a")
    conc_mat = prices.get(CONCRETE, 0.0) if o["ready_mix"] else \
        recipe_price("2.2", prices)[0]
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
            nx, ny = S.bar_count(l, spc), S.bar_count(w, spc)
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
    stump_below = sum(float(lib[e["mark"]]["b"]) * float(lib[e["mark"]]["h"])
                      * (e["z1"] - e["z0"]) for e in E["stumps"])
    if exc:
        bill.add(g, "งานถมดินคืน (ใช้ดินที่ขุด)",
                 exc["qty"] - conc_f - stump_below, "ลบ.ม.",
                 basis=f"ดินขุด {exc['qty']:.2f} − ฐานราก {conc_f:.2f} − "
                       f"เสาตอม่อ {stump_below:.2f}",
                 ref="หลักเกณฑ์ 4.1 ข้อ 1 (การถมคืน)",
                 note="ค่าแรงรวมใน ว480 1.3 (ขุดหลุมฐานรากและถมคืน)")
    for mark, cnt in pile_n.items():
        f = lib[mark]
        bill.add(g, f"เสาเข็ม {float(f['pile_b']):g}×{float(f['pile_b']):g}×"
                    f"{float(f['pile_len']):g} ม. ({mark})", cnt, "ต้น",
                 basis=f"{f['piles']} ต้น/ฐาน", ref="หลักเกณฑ์ 4.1 ข้อ 1",
                 note="ค่าแรงตอกเข็มตาม ว480 1.1–1.2 (ขึ้นกับจำนวน/พื้นที่)")
    bill.add(g, "ทรายรองก้นหลุม (บดอัดด้วยแรงคน)", sand, "ลบ.ม.",
             waste=S.BEDDING_WASTE["ทราย"], mat_key="ทรายหยาบ",
             lab_code="1.5", basis="กว้าง×ยาว×หนาทราย × จำนวนฐาน",
             ref="หลักเกณฑ์ 4.1 ข้อ 2.1 (เผื่อ 25%) · ว480 1.5")
    lean_price, lean_note = recipe_price("1.1", prices)
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
                bars([(tp[1], S.bar_count(clear, tp[2]) * 2 * (b + h))])
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

    # --- 4. Slabs --------------------------------------------------------
    g = "slab"
    for ground, title in ((True, "พื้นวางบนดิน"), (False, "พื้นชั้นบน")):
        vol = soffit = sand_s = 0.0
        basis = {}
        for e in E["slabs"]:
            sl = lib[e["mark"]]
            on_ground = bool(int(sl.get("ground") or 0)) and e["floor"] == 0
            if on_ground != ground:
                continue
            rm = e["room"]
            bw = float(lib[ROLE_beam(e["floor"], n)]["b"])
            area = max(float(rm["w"]) - bw, 0) * max(float(rm["d"]) - bw, 0)
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
        txt = "; ".join(f"{m}: พื้นที่สุทธิ {a:.2f} ตร.ม. × หนา "
                        f"{lib[m]['t']:g}" for m, a in basis.items())
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
        nr, L, Hs = B.stair_geometry(e["st"], s)
        w = float(e["st"].get("w") or s["stair_w"])
        sec = P.section_area("stair", dict(L=L * 1000, H=Hs * 1000, n=nr,
                                           t=float(s["stair_t"]) * 1000))
        vol += sec * w
        slope = math.hypot(L, Hs)
        area += slope * w + 2 * sec + nr * (Hs / nr) * w
        bars([("DB12", S.bar_count(w, 0.15) * slope),
              ("RB9", S.bar_count(slope, 0.20) * w)])
    if vol:
        concrete(g, "บันได", vol, "พื้นที่หน้าตัดขั้นบันได × กว้าง")
        formwork(g, "บันได", area, "ท้องบันได + ข้าง 2 ด้าน + ลูกตั้ง")

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

    # --- 7. Walls, plaster, paint ----------------------------------------
    g = "wall"
    if s.get("walls"):
        wall_a = ext_face = int_face = 0.0
        col_b = float(lib["C1"]["b"])
        for wl in E["walls"]:
            ops = sum(op_w * op_h for op_w, op_h, _sl in
                      (B.opening_size(op, s) for op in wl["openings"]))
            a = S.wall_area(wl["L"], col_b, H, float(lib[wl["beam"]]["h"]),
                            ops)
            wall_a += a
            if wl["exterior"]:
                ext_face += a
                int_face += a
            else:
                int_face += 2 * a
        wp, wnote = recipe_price(o["wall_recipe"], prices)
        rc = RC.find(o["wall_recipe"])
        bill.add(g, rc["name"] if rc else "ผนังก่ออิฐ", wall_a, "ตร.ม.",
                 mat=wp, lab_code="2.3.1a",
                 basis="(ยาวศูนย์–ศูนย์เสา − กว้างเสา)×(สูงพื้นถึงพื้น − "
                       "ลึกคาน) − ช่องเปิด",
                 ref=f"หลักเกณฑ์ 4.2 ข้อ 3.1 · สูตรวัสดุ {o['wall_recipe']}"
                     " · ว480 2.3.1", note=wnote)
        pp, pnote = recipe_price(o["plaster_recipe"], prices)
        bill.add(g, "ฉาบปูนเรียบ ผนังภายใน", int_face, "ตร.ม.", mat=pp,
                 lab_code="2.3.2a", basis="พื้นที่ผนังด้านภายในทุกด้าน",
                 ref=f"หลักเกณฑ์ 4.2 ข้อ 3.2 · สูตรวัสดุ "
                     f"{o['plaster_recipe']} · ว480 2.3.1.2", note=pnote)
        bill.add(g, "ฉาบปูนเรียบ ผนังภายนอก", ext_face, "ตร.ม.", mat=pp,
                 lab_code="2.3.2b", basis="พื้นที่ผนังด้านนอกอาคาร",
                 ref=f"หลักเกณฑ์ 4.2 ข้อ 3.2 · สูตรวัสดุ "
                     f"{o['plaster_recipe']} · ว480 2.3.1.2", note=pnote)
        if o["paint"]:
            bill.add(g, "ทาสีน้ำอะครีลิค ภายใน (รองพื้น 1 + จริง 2 เที่ยว)",
                     int_face, "ตร.ม.",
                     mat_key="สีน้ำอะครีลิค ภายใน (ต่อ ตร.ม.)",
                     lab_code="2.8.1a", basis="เท่าพื้นที่ฉาบภายใน",
                     ref="สูตรวัสดุ 10.2 · ว480 2.8.1")
            bill.add(g, "ทาสีน้ำอะครีลิค ภายนอก (รองพื้น 1 + จริง 2 เที่ยว)",
                     ext_face, "ตร.ม.",
                     mat_key="สีน้ำอะครีลิค ภายนอก (ต่อ ตร.ม.)",
                     lab_code="2.8.1b", basis="เท่าพื้นที่ฉาบภายนอก",
                     ref="สูตรวัสดุ 10.1 · ว480 2.8.1")

    # --- 8. Doors and windows --------------------------------------------
    g = "opening"
    sets: dict[tuple, list] = {}
    for op in E["openings"]:
        key = (op["type"], op["name"])
        sets.setdefault(key, [0, op["w"] * op["h"]])[0] += 1
    for (kind, name), (cnt, a) in sorted(sets.items()):
        if kind == "window":
            lab = a * labour.get("2.5.2b", 0.0)
            ref = "หลักเกณฑ์ 4.2 ข้อ 5 · ว480 2.5.2 (วงกบหน้าต่าง)"
            key = "หน้าต่าง (ชุด)"
        else:
            lab = a * (labour.get("2.5.2a", 0.0) + labour.get("2.5.3", 0.0))
            ref = "หลักเกณฑ์ 4.2 ข้อ 5 · ว480 2.5.2 + 2.5.3 (วงกบ + บาน)"
            key = "ประตู (ชุด)"
        bill.add(g, f"{name} พร้อมวงกบ บาน และอุปกรณ์", cnt, "ชุด",
                 mat_key=key, lab=lab,
                 basis=f"นับตามแบบ · ค่าแรง {a:.2f} ตร.ม./ชุด", ref=ref)

    # --- 9. Finishes -----------------------------------------------------
    g = "finish"
    if o["finishes"]:
        wt = float(s["wall_t"])
        floor_a = sum(max(float(e["room"]["w"]) - wt, 0) *
                      max(float(e["room"]["d"]) - wt, 0) for e in E["slabs"])
        fp, fnote = recipe_price(o["floor_recipe"], prices)
        rc = RC.find(o["floor_recipe"])
        bill.add(g, rc["name"] if rc else "พื้นปูกระเบื้อง", floor_a, "ตร.ม.",
                 mat=fp, lab_code="2.4.6",
                 basis="พื้นที่ริมผนังถึงริมผนังทุกห้อง",
                 ref=f"หลักเกณฑ์ 4.2 ข้อ 4.2 · สูตรวัสดุ {o['floor_recipe']}"
                     " · ว480 2.4.6", note=fnote)
        bill.add(g, "ฝ้าเพดานยิปซัมบอร์ด 9 มม. โครงคร่าว T-bar", floor_a,
                 "ตร.ม.", mat_key="ฝ้ายิปซัม 9 มม. โครง T-bar (วัสดุ)",
                 lab_code="2.2.2", basis="พื้นที่ห้อง (ผนังถึงผนัง)",
                 ref="หลักเกณฑ์ 4.2 ข้อ 2.1 · สูตรวัสดุ 5.42 · ว480 2.2.2")

    # --- 10. Roof --------------------------------------------------------
    g = "roof"
    lines = B.roof_lines(data)
    if lines:
        roof = s["roof"]
        per: dict[str, float] = {}
        for kind in ("ridge", "hip", "rafter", "post"):
            for path in lines[kind]:
                per[s[kind]] = per.get(s[kind], 0.0) + P.path_length(path)
        for pl in lines["purlin"]:
            per[s["purlin"]] = per.get(s["purlin"], 0.0) + \
                P.path_length(pl["path"], pl["closed"])
        paint_a = 0.0
        for label, length in per.items():
            fam, params = B.steel_lookup(label)
            kgm = P.weight_per_m(fam, params)
            with_w, pieces = S.steel_pieces(length, roof)
            kg = pieces * S.STEEL_BAR_LENGTH * kgm
            bill.add(g, f"โครงหลังคาเหล็ก {label}", kg, "กก.",
                     mat_key="เหล็กรูปพรรณ (ทั่วไป)", lab_code="1.11.1",
                     basis=f"ยาว {length:.2f} ม. + {S.STEEL_ROOF_WASTE[roof]:g}%"
                           f" = {with_w:.2f} ม. → {pieces} ท่อน × 6 ม. × "
                           f"{kgm:.2f} กก./ม.",
                     ref="หลักเกณฑ์ 4.1 ข้อ 6.3 · ว480 1.11.1")
            paint_a += pieces * S.STEEL_BAR_LENGTH * _perimeter(fam, params)
        bill.add(g, "ทาสีกันสนิมโครงหลังคาเหล็ก", paint_a, "ตร.ม.",
                 mat_key="สีกันสนิม", lab_code="2.8.3",
                 basis="เส้นรอบรูปหน้าตัด × ความยาวทุกท่อน",
                 ref="หลักเกณฑ์ 4.1 ข้อ 6.4 · ว480 2.8.3")
        slope = sum(_area3(p) for p in lines["skin"])
        if o["roofing"] == "metal":
            bill.add(g, "มุงหลังคาเหล็กรีดลอน (Metal Sheet)", slope, "ตร.ม.",
                     waste=S.ROOFING_WASTE.get(roof, 3.0),
                     mat_key="กระเบื้องคอนกรีต (รวมอุปกรณ์)",
                     lab_code="2.1.8", basis="พื้นที่ตามแนวลาดเอียง",
                     ref="หลักเกณฑ์ 4.2 ข้อ 1.4 · ว480 2.1.8")
        else:
            bill.add(g, "มุงกระเบื้องคอนกรีต (รวมครอบและอุปกรณ์)", slope,
                     "ตร.ม.", waste=S.ROOFING_WASTE.get(roof, 3.0),
                     mat_key="กระเบื้องคอนกรีต (รวมอุปกรณ์)",
                     lab_code="2.1.3", basis="พื้นที่ตามแนวลาดเอียง",
                     ref="หลักเกณฑ์ 4.2 ข้อ 1.1, 1.4 (เผื่อ 3%/5%) · "
                         "ว480 2.1.3")

    # Formwork labour tier by the project's total formwork area.
    tier = "1.8.1a" if form_total[0] >= 5000 else "1.8.1b"
    for ln in bill.lines:
        if ln["lab_code"].startswith("1.8.1"):
            ln["lab_code"] = tier
            ln["lab"] = round(labour.get(tier, 0.0), 2)
            ln["lab_total"] = round(ln["qty"] * ln["lab"], 2)
            ln["total"] = round(ln["mat_total"] + ln["lab_total"], 2)
    if not any(prices.values()):
        notes.append("ยังไม่มีราคาวัสดุ — กรอกราคาจากสำนักงานพาณิชย์จังหวัด "
                     "(หรือกด «ราคาตัวอย่าง» เพื่อทดลอง)")
    notes.append("ขนาดชิ้นส่วนและเหล็กเสริมเป็นค่าเริ่มต้น — "
                 "วิศวกรผู้ออกแบบต้องกำหนดตามแบบจริง")
    groups = []
    for key, th in GROUPS:
        rows = [ln for ln in bill.lines if ln["group"] == key]
        if rows:
            groups.append((key, th, rows))
    return {"lines": bill.lines, "groups": groups,
            "totals": _totals(bill.lines), "rebar": rebar, "notes": notes,
            "footer": footer("WANIC ออกแบบอาคาร")}


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


def _totals(lines) -> dict:
    mat = round(sum(ln["mat_total"] for ln in lines), 2)
    lab = round(sum(ln["lab_total"] for ln in lines), 2)
    return {"mat": mat, "lab": lab, "total": round(mat + lab, 2)}


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
            out.append(new_rate(
                id=f"std{gi}.{li}", category=th, code=f"{gi}.{li}",
                desc=ln["desc"], by="all", value="", qty="manual",
                manual_qty=ln["qty"], unit=ln["unit"], mat=ln["mat"],
                lab=ln["lab"], note=note, section="work"))
    return out


def csv_text(result) -> str:
    import csv
    import io
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["หมวด", "ลำดับ", "รายการ", "ปริมาณสุทธิ", "เผื่อ %",
                "ปริมาณ", "หน่วย", "ค่าวัสดุ/หน่วย", "ค่าวัสดุ",
                "ค่าแรง/หน่วย", "ค่าแรง", "รวม", "ที่มา", "การคำนวณ"])
    for gi, (_k, th, rows) in enumerate(result["groups"], 1):
        for li, ln in enumerate(rows, 1):
            w.writerow([th, f"{gi}.{li}", ln["desc"], f"{ln['net']:.4f}",
                        f"{ln['waste']:g}", f"{ln['qty']:.2f}", ln["unit"],
                        f"{ln['mat']:.2f}", f"{ln['mat_total']:.2f}",
                        f"{ln['lab']:.2f}", f"{ln['lab_total']:.2f}",
                        f"{ln['total']:.2f}", ln["ref"], ln["basis"]])
    t = result["totals"]
    w.writerow(["", "", "รวมค่างานต้นทุน", "", "", "", "", "",
                f"{t['mat']:.2f}", "", f"{t['lab']:.2f}", f"{t['total']:.2f}",
                "", ""])
    w.writerow([result.get("footer", footer())])
    return buf.getvalue()
