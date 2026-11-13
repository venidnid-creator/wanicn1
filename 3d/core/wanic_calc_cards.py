# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
"""รายการคำนวณแบบการ์ด (booklet cards) — footings, slabs, the roof frame,
and the earthquake/wind moment on the beams; plus the choice to print only
the critical member of each mark.

Standards (as the basis page states):
- concrete: วสท. 011008 / ACI 318 — SDM U = 1.4D + 1.7L, φ 0.90 bending,
  0.85 shear; or WSD (ข้อบัญญัติ กทม. 2522) fs = 0.5 fy ≤ 1,700 ksc,
  fc = 0.375 fc′, j ≈ 0.875;
- footings: soil pressure on the service load; bending at the column face,
  one-way shear at d from the face (Vc = 0.53 √fc′ b d), punching at d/2
  round the stump (Vc = 1.06 √fc′ b0 d) — φ 0.85 (SDM);
- slabs: ACI 318-63 Method 2 coefficients (วสท.), short and long span,
  continuous / discontinuous edges; one-way slabs wL²/10 (continuous) or
  wL²/8; As,min 0.0018 b t (SD40) / 0.0025 b t (SR24); spacing ≤ 3t, 45 cm;
- the roof: steel / timber members by allowable stress (AISC ASD, Fb =
  0.60 Fy), deflection L/180."""
from __future__ import annotations

import math

from core import wanic_calc as C
from core import wanic_rc as R

#: (negative at a continuous edge, positive, negative at a discontinuous edge)
#: for m = 1.0 … 0.5 — the same table as wanic_calc.SLAB_COEF
_MS = [1.0, 0.9, 0.8, 0.7, 0.6, 0.5]


def coef(m: float, disc: int) -> tuple:
    rows = C.SLAB_COEF[max(0, min(4, disc))]
    m = max(0.5, min(1.0, m))
    for i in range(5):
        if _MS[i + 1] - 1e-9 <= m <= _MS[i] + 1e-9:
            f = (_MS[i] - m) / 0.1
            return tuple(a + (b - a) * f for a, b in zip(rows[i], rows[i + 1]))
    return rows[-1]


def _as_need(M, b_cm, d_cm, bar, b_):
    """Steel (cm²) for M (kg·m) on a width b (cm)."""
    if M <= 0:
        return 0.0
    if b_["method"] == "SDM":
        fc, fy = b_["fc"], C.fy_of(bar, b_)
        Rn = M * 100 / (0.9 * b_cm * d_cm * d_cm)
        disc = 1 - 2 * Rn / (0.85 * fc)
        if disc <= 0:
            return float("inf")
        return 0.85 * fc / fy * (1 - math.sqrt(disc)) * b_cm * d_cm
    return M * 100 / (C.fs_of(bar, b_) * 0.875 * d_cm)


def _spacing(As_per_m, bar, t):
    """The spacing (m) of ``bar`` for As (cm²/m), ≤ 3t and ≤ 0.45, down to 2.5 cm."""
    if not bar or As_per_m <= 0:
        return 0.0
    s = bar.area / As_per_m
    s = min(s, 3 * t, 0.45)
    return math.floor(s * 40) / 40


# ---- footings ------------------------------------------------------------------------

def footing_rows(res_all, data, critical=False) -> list:
    """Per footing: dict with the card's numbers. ``critical``: the most
    loaded footing of each mark only."""
    from core import wanic_building as B
    E = B.elements(data)
    lib = E["lib"]
    b_ = res_all["basis"]
    fc = b_["fc"]
    D_, L_ = C.factors(b_)
    avg = (D_ + L_) / 2.0
    loads = dict(res_all["columns"])
    stumps = {(round(s["x"], 3), round(s["y"], 3)): s["mark"] for s in E["stumps"]}
    out = []
    for f in E["footings"]:
        k = (round(f["x"], 3), round(f["y"], 3))
        sp = lib.get(f["mark"], {})
        Pu = loads.get(k, 0.0)
        P = Pu / avg
        w, l, t = (float(sp.get(x, 0)) for x in ("w", "l", "t"))
        depth = float(sp.get("depth") or 1.5)
        self_w = w * l * t * b_["concrete"]
        soil_w = w * l * max(depth - t, 0) * 1800.0
        A = w * l
        q = (P + self_w + soil_w) / A if A else 0.0               # kg/m², service
        st = lib.get(stumps.get(k), {}) if stumps.get(k) else {}
        c = float(st.get("b", 0.2))
        bar = R.parse_bar(sp.get("bars"))
        d = t - R.COVER["footing"] - (bar.d / 1000 if bar else 0.012)
        qu = (Pu / A) if A else 0.0                               # net factored upward pressure
        arm = (max(w, l) - c) / 2
        Mu = qu * min(w, l) * arm * arm / 2                       # kg·m across the full width
        As = max(_as_need(Mu, min(w, l) * 100, d * 100, bar, b_), 0.0018 * min(w, l) * 100 * t * 100)
        nbar = math.ceil(As / bar.area) if bar else 0
        if bar and bar.s:
            nbar = max(nbar, int(round((min(w, l) - 0.15) / bar.s)) + 1)
        phi = 0.85 if b_["method"] == "SDM" else 1.0
        vf = 0.53 if b_["method"] == "SDM" else 0.29
        V1 = qu * min(w, l) * max(arm - d, 0.0)
        Vc1 = phi * vf * math.sqrt(fc) * min(w, l) * 100 * d * 100
        b0 = 4 * (c + d)
        V2 = qu * max(A - (c + d) ** 2, 0.0)
        Vc2 = phi * 2 * vf * math.sqrt(fc) * b0 * 100 * d * 100
        piles = int(sp.get("piles") or 0)
        from core import wanic_pile as PL
        pcap = PL.cap_of(sp, data, b_)
        cap = piles * pcap * 1000 if piles else b_["soil"] * 1000 * A
        out.append({"pcap": pcap, "ptype": PL.type_of_spec(sp), "mark": f["mark"], "x": f["x"], "y": f["y"], "w": w, "l": l, "t": t, "depth": depth,
                    "P": P, "q": q, "soil": b_["soil"] * 1000, "cap": cap, "piles": piles, "stump": stumps.get(k, "-"),
                    "c": c, "Mu": Mu, "As": As, "bar": bar, "nbar": nbar, "V1": V1, "Vc1": Vc1, "V2": V2, "Vc2": Vc2,
                    "ok": (P + self_w) <= cap and V1 <= Vc1 and V2 <= Vc2})
    if critical:
        best = {}
        for r in out:
            if r["mark"] not in best or r["P"] > best[r["mark"]]["P"]:
                best[r["mark"]] = r
        out = list(best.values())
    return sorted(out, key=lambda r: (r["mark"], -r["P"]))


def footing_pages(bk, res_all, data, critical=False):
    from core.wanic_calc_book import BLUE, GREEN, RED
    rows = footing_rows(res_all, data, critical)
    per = 4
    for start in range(0, len(rows), per):
        bk.page("ฐานราก", f"Foot-{start // per + 1}")
        for i, r in enumerate(rows[start:start + per]):
            x, y = 12 + i * 97, 40
            yy = bk.table(x, y, [20, 22, 22, 20], [("NO.", "กว้าง(ซม.)", "ยาว(ซม.)", "หนา(ซม.)"),
                                                   ((r["mark"], BLUE), (f"{r['w'] * 100:.0f}", BLUE),
                                                    (f"{r['l'] * 100:.0f}", BLUE), (f"{r['t'] * 100:.0f}", BLUE))], 7.5)
            bar = r["bar"]
            body = [("Footing", "", ("OK" if r["ok"] else "NG", GREEN if r["ok"] else RED)),
                    ("P (ใช้งาน)", "kg.", f"{r['P']:,.0f}"),
                    ("Mx / My", "kg.-m.", "0.00 / 0.00"),
                    ("แรงดันดิน q", "kg./m²", f"{r['q']:,.0f}"),
                    ("ความลึก", "m.", f"{r['depth']:.2f}"),
                    ("เสาเข็ม" if r["piles"] else "ดินรับได้", "", f"{r['piles']} ต้น" if r["piles"]
                     else f"{r['soil']:,.0f} kg/m²"),
                    ("รับน้ำหนักได้", "kg.", f"{r['cap']:,.0f}"),
                    ("ตอม่อ", "", f"{r['stump']} {r['c'] * 100:.0f}×{r['c'] * 100:.0f} ซม."),
                    ("โมเมนต์ Mu", "kg-m", f"{r['Mu']:,.2f}"),
                    ("As", "cm²", "—" if r["As"] == float("inf") else f"{r['As']:.2f}"),
                    ("เหล็กตามยาว", (f"{bar.kind}{bar.d}" if bar else "-", BLUE), (str(r["nbar"]), BLUE)),
                    ("เหล็กตามกว้าง", (f"{bar.kind}{bar.d}" if bar else "-", BLUE), (str(r["nbar"]), BLUE)),
                    ("เฉือนทางเดียว Vu", "kg.", f"{r['V1']:,.0f}"),
                    ("φVc ทางเดียว", "kg.", f"{r['Vc1']:,.0f}"),
                    ("เฉือนทะลุ Vu", "kg.", f"{r['V2']:,.0f}"),
                    ("φVc ทะลุ", "kg.", f"{r['Vc2']:,.0f}")]
            bk.table(x, yy + 2, [34, 18, 36], body, 7.0, left=True)
            bk.text(x, yy + 4 + len(body) * 7.0, 86, 6, f"Grid ({r['x']:.2f}, {r['y']:.2f})", 5.2)
        bk.text(12, 238, 290, 6, "อ้างอิง วสท. 011008 / ACI 318: แรงดันดินจากน้ำหนักใช้งาน · โมเมนต์ที่ผิวตอม่อ · φVc ทางเดียว = φ0.53√fc′bd", 5.0)
        bk.text(12, 244, 290, 6, "เฉือนทางเดียวที่ระยะ d · เฉือนทะลุที่ d/2 รอบตอม่อ φVc = φ1.06√fc′b0d · As ≥ 0.0018bt", 5.0)


# ---- slabs ---------------------------------------------------------------------------

def slab_rows(res_all, data, critical=False) -> list:
    from core import wanic_building as B
    E = B.elements(data)
    lib = E["lib"]
    b_ = res_all["basis"]
    D_, L_ = C.factors(b_)
    level_rooms = {}
    for sl in E["slabs"]:
        level_rooms.setdefault(sl.get("floor", 0), []).append(sl["room"])
    out = []
    for sl in E["slabs"]:
        sp = lib.get(sl["mark"], {})
        if sl.get("ground") or sp.get("ground"):
            continue
        rm = sl["room"]
        t = float(sp.get("t", 0.10))
        S, Lg = sorted((float(rm["w"]), float(rm["d"])))
        dead = t * b_["concrete"] + b_["finish"]
        wu = D_ * dead + L_ * b_["ll_floor"]
        disc = C.discontinuous_edges(rm, level_rooms.get(sl.get("floor", 0), []))
        m = S / Lg
        bar = R.parse_bar(sp.get("bars"))
        d = t - R.COVER["slab"] - (bar.d / 2000.0 if bar else 0.005)
        asmin = (0.0025 if bar and bar.kind == "RB" else 0.0018) * 100 * t * 100
        if m < 0.5:
            Ms_p = wu * S * S / (10.0 if disc <= 2 else 8.0)
            Ms_n = wu * S * S / 10.0 if disc <= 2 else 0.0
            Ml_p = Ml_n = 0.0
            kind = "One-way Slab"
        else:
            cn, cp, cd = coef(m, disc)
            ln, lp, ld = coef(1.0, disc)
            Ms_n, Ms_p = max(cn, cd) * wu * S * S, cp * wu * S * S
            Ml_n, Ml_p = max(ln, ld) * wu * S * S, lp * wu * S * S
            kind = "Two-way Slab"
        dcm = d * 100
        need = {k: max(_as_need(v, 100, dcm, bar, b_), asmin) if v > 0 else asmin
                for k, v in (("s+", Ms_p), ("s-", Ms_n), ("l+", Ml_p), ("l-", Ml_n))}
        sp_ = {k: _spacing(v, bar, t) for k, v in need.items()}
        ok = bar is not None and bar.s and all(bar.s <= s + 1e-6 for s in sp_.values() if s)
        out.append({"mark": sl["mark"], "name": rm.get("name", ""), "S": S, "L": Lg, "m": m, "t": t, "d": d,
                    "bar": bar, "wu": wu, "dead": dead, "ll": b_["ll_floor"], "fin": b_["finish"], "kind": kind,
                    "M": {"s+": Ms_p, "s-": Ms_n, "l+": Ml_p, "l-": Ml_n}, "As": need, "s": sp_, "ok": ok,
                    "disc": disc})
    if critical:
        best = {}
        for r in out:
            if r["mark"] not in best or r["S"] * r["L"] > best[r["mark"]]["S"] * best[r["mark"]]["L"]:
                best[r["mark"]] = r
        out = list(best.values())
    return out


def slab_pages(bk, res_all, data, critical=False):
    from PySide6.QtCore import QRectF
    from PySide6.QtGui import QPen

    from core.wanic_calc_book import BLUE, GREEN, INK, RED
    rows = slab_rows(res_all, data, critical)
    per = 4
    mm = bk.mm
    for start in range(0, len(rows), per):
        bk.page("พื้น", f"Slab-{start // per + 1}")
        for i, r in enumerate(rows[start:start + per]):
            x = 12 + i * 97
            sc = 60.0 / max(r["L"], 1.0)                       # the panel drawn ≤ 60 mm
            pw, ph = r["L"] * sc, r["S"] * sc
            bk.p.setPen(QPen(INK, 2))
            bk.p.drawRect(QRectF((x + 10) * mm, (100 - ph) * mm, pw * mm, ph * mm))
            bk.text(x + 10, 100 - ph - 8, pw, 6, f"{r['L']:.2f}", 5.5, align=0x84)
            bk.text(x, 100 - ph, 9, ph, f"{r['S']:.2f}", 5.5, align=0x84)
            bk.text(x + 10, 101, pw, 6, f"({r['mark']}) {r['name']}", 5.5, BLUE, align=0x84)
            bar = r["bar"]
            bn = f"{bar.kind}{bar.d}" if bar else "-"
            fmt = lambda s: f"{bn}@{s:.3f}".rstrip("0").rstrip(".") if s else "-"   # noqa: E731
            body = [("น้ำหนักบรรทุกจร", "kg/m²", (f"{r['ll']:.2f}", BLUE)),
                    ("ปูพื้น + ฝ้า", "kg/m²", (f"{r['fin']:.2f}", BLUE)),
                    ("Short Span (S)", "m.", f"{r['S']:.2f}"), ("Long Span (L)", "m.", f"{r['L']:.2f}"),
                    ("m = S/L", "", f"{r['m']:.2f}"), ("หนา (t)", "cm.", (f"{r['t'] * 100:.0f}", BLUE)),
                    ("d", "cm.", f"{r['d'] * 100:.1f}"), ("ขนาดเหล็ก", "", (bn, BLUE)),
                    ("น้ำหนักรวม wu", "kg/m²", f"{r['wu']:,.2f}"),
                    ("Ms+", "kg-m", f"{r['M']['s+']:,.2f}"), ("Ms−", "kg-m", f"{r['M']['s-']:,.2f}"),
                    ("Ml+", "kg-m", f"{r['M']['l+']:,.2f}"), ("Ml−", "kg-m", f"{r['M']['l-']:,.2f}"),
                    ("@ เหล็กล่างสั้น", "m.", fmt(r["s"]["s+"])), ("@ เหล็กบนสั้น", "m.", fmt(r["s"]["s-"])),
                    ("@ เหล็กล่างยาว", "m.", fmt(r["s"]["l+"])), ("@ เหล็กบนยาว", "m.", fmt(r["s"]["l-"])),
                    ("ใช้ตามแบบ", "", (fmt(bar.s) if bar and bar.s else "-", BLUE)),
                    (r["kind"], f"ไม่ต่อเนื่อง {r['disc']}", ("OK" if r["ok"] else "NG", GREEN if r["ok"] else RED))]
            bk.table(x, 110, [44, 20, 26], body, 6.8, left=True)
        bk.text(12, 244, 290, 6, "อ้างอิง วสท. / ACI 318-63 วิธีที่ 2 · พื้นทางเดียว wL²/10 (ต่อเนื่อง)", 5.0)
        bk.text(12, 250, 290, 6, "As ≥ 0.0018bt (SD40) / 0.0025bt (SR24) · ระยะเรียง ≤ 3t และ ≤ 45 ซม.", 5.0)


# ---- the roof ------------------------------------------------------------------------

def roof_page(bk, res_all):
    from core.wanic_calc_book import GREEN, RED
    ms = [m for m in res_all["members"] if m.group == "roof"]
    if not ms:
        return
    bk.page("โครงหลังคา", "Roof-1")
    y = 36
    for m in ms:
        if y > 235:
            bk.page("โครงหลังคา", "Roof-2")
            y = 36
        bk.text(14, y, 250, 7, m.name, 6.4, bold=True)
        bk.text(330, y, 60, 7, ("OK" if m.ok else "NG") + f"  ({m.ratio:.2f})", 6.4, GREEN if m.ok else RED,
                bold=True)
        bk.text(24, y + 7, 370, 6, f"แรงที่เกิด: {m.demand}", 5.6)
        bk.text(24, y + 13, 370, 6, f"กำลังที่รับได้: {m.capacity}" + (f"   ·   {m.note}" if m.note else ""), 5.6)
        y += 22
    bk.text(12, 238, 290, 6, "อ้างอิง AISC ASD: Fb = 0.60Fy (เหล็กรูปพรรณ) · Z ต้องการ = M / Fb · การแอ่นตัวไม่เกิน L/180", 5.0)
    bk.text(12, 244, 290, 6, "แรงลมคิดแรงยก Cp 0.7 ใช้หน่วยแรงเพิ่ม ⅓ · ไม้ตามค่าที่ใช้ออกแบบ", 5.0)


# ---- earthquake / wind moments on the beams ---------------------------------------------

def attach_lateral_moments(res_all, data):
    """Me (kg·m) on each beam end from the portal method: the column moments
    above and below a joint (V·h/2 each) shared by the beams that meet there."""
    if not (data or {}).get("lateral"):
        return
    from core import wanic_lateral as LT
    lat = LT.analyse(data)
    by_floor = {}
    for c in lat["checks"]:
        Mc = c["Vc"] * lat["H"] / 2
        by_floor[c["floor"]] = max(by_floor.get(c["floor"], 0.0), Mc)
    for m in res_all["members"]:
        res = m.diagram
        if m.group != "beam" or res is None or not hasattr(res, "level") or getattr(res, "ground", False):
            continue
        lv = int(res.level)
        below = by_floor.get(lv - 1, 0.0)
        above = by_floor.get(lv, 0.0)
        res.me = (below + above) / 2


def critical_members(res_all) -> dict:
    """Keep the most stressed beam of each (mark, level) and the most loaded
    column card of each (mark, floor)."""
    keep, best = [], {}
    for m in res_all["members"]:
        res = m.diagram
        if m.group == "beam" and res is not None and hasattr(res, "spec"):
            key = (res.mark, res.level)
            if key not in best or m.ratio > best[key].ratio:
                best[key] = m
            continue
        keep.append(m)
    keep += list(best.values())
    cards, cb = [], {}
    for c in res_all.get("cards") or []:
        key = (c["mark"], c["floor"])
        if key not in cb or c["P"] > cb[key]["P"]:
            cb[key] = c
    cards = list(cb.values())
    return {**res_all, "members": keep, "cards": cards}
