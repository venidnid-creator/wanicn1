# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
"""แรงด้านข้าง: earthquake and wind on the building, level by level, and the
columns' check under them.

Earthquake (แรงสถิตเทียบเท่า):
- มยผ. 1301/1302-61 (current): SDS = ⅔·Fa·Ss, SD1 = ⅔·Fv·S1 (Ss, S1 of the
  district from the standard's table; Fa, Fv by the site class), T = 0.02·H
  (RC frame) / 0.0466·H^0.9 (steel), Sa = SDS (T ≤ SD1/SDS) else SD1/T,
  Cs = Sa·I/R, V = Cs·W, Fx = V·wx·hx^k / Σ wi·hi^k (k 1 → 2 for T 0.5 → 2.5 s);
- กฎกระทรวง 2550 (old, the option): V = Z·I·K·C·S·W, C = 1/(15√T) ≤ 0.12,
  T = 0.09·hn/√D, C·S ≤ 0.14, Ft = 0.07·T·V ≤ 0.25V when T > 0.7 s.

Wind:
- มยผ. 1311-50 (current, static procedure): p = Iw·q·Ce·Cg·Cp, q = ½ρV50²
  (ρ 1.25 kg/m³) by the wind zone, Ce of the terrain, Cg = 2.0, Cp 0.8
  windward + 0.5 leeward;
- กฎกระทรวง ฉบับที่ 6 (2527) (old): 50 / 80 / 120 / 160 kg/m² by height
  (≤ 10 / 10–20 / 20–40 / > 40 m).

The weights W are the dead loads from the gravity analysis (the same
load path, level by level). Each storey's shear is shared equally by its
columns (a frame of equal columns), the column moment V·h/2, checked with
the gravity load on its P-M curve: U = 0.75(1.4D + 1.7L + 1.87E) or
0.75(1.4D + 1.7L + 1.6W) (วสท.)."""
from __future__ import annotations

import math

#: Site coefficients (มยผ. 1301/1302-61 = ASCE 7) — Ss 0.25 … 1.25, S1 0.1 … 0.5
FA = {"A": (0.8,) * 5, "B": (1.0,) * 5, "C": (1.2, 1.2, 1.1, 1.0, 1.0), "D": (1.6, 1.4, 1.2, 1.1, 1.0),
      "E": (2.5, 1.7, 1.2, 0.9, 0.9)}
FV = {"A": (0.8,) * 5, "B": (1.0,) * 5, "C": (1.7, 1.6, 1.5, 1.4, 1.3), "D": (2.4, 2.0, 1.8, 1.6, 1.5),
      "E": (3.5, 3.2, 2.8, 2.4, 2.4)}
SITE_TH = {"A": "A หินแข็ง", "B": "B หิน", "C": "C ดินแข็งมาก/หินอ่อน", "D": "D ดินแข็ง", "E": "E ดินอ่อน"}
#: R (response modification) — the frame systems of มยผ. 1301/1302-61
SYSTEMS = {"rc_omf": ("โครงต้านแรงดัด คสล. ความเหนียวธรรมดา", 3.0),
           "rc_imf": ("โครงต้านแรงดัด คสล. ความเหนียวปานกลาง", 5.0),
           "rc_smf": ("โครงต้านแรงดัด คสล. ความเหนียวพิเศษ", 8.0),
           "steel_omf": ("โครงต้านแรงดัดเหล็ก ความเหนียวธรรมดา", 3.5)}
#: the old Z by zone, and K by system (กฎกระทรวง 2550)
ZONE_Z = {"0": 0.0, "1": 0.1875, "2": 0.375, "3": 0.75, "4": 1.0}
K_OLD = {"rc_omf": 1.0, "rc_imf": 0.8, "rc_smf": 0.67, "steel_omf": 1.0}
#: basic wind speed V50 (m/s) and the typhoon factor by wind zone (มยผ. 1311-50)
WIND_ZONES = {"1": (25.0, 1.0), "2": (27.0, 1.0), "3": (29.0, 1.0), "4A": (25.0, 1.2), "4B": (25.0, 1.08)}

DEFAULTS = {"eq_on": False, "standard": "new", "Ss": 0.25, "S1": 0.08, "site": "D", "system": "rc_omf", "I": 1.0,
            "zone": "1", "S_old": 1.2, "wind_std": "new", "wind_zone": "1", "terrain": "A", "Iw": 1.0}


def _interp(table, v, steps):
    if v <= steps[0]:
        return table[0]
    for (a, b), (fa, fb) in zip(zip(steps, steps[1:]), zip(table, table[1:])):
        if v <= b:
            return fa + (fb - fa) * (v - a) / (b - a)
    return table[-1]


def site_factors(site: str, Ss: float, S1: float) -> tuple:
    return (_interp(FA[site], Ss, (0.25, 0.5, 0.75, 1.0, 1.25)),
            _interp(FV[site], S1, (0.1, 0.2, 0.3, 0.4, 0.5)))


def params_of(data) -> dict:
    return {**DEFAULTS, **((data or {}).get("lateral") or {})}


def level_weights(data) -> list:
    """[(level, height m, W kg)] — the dead weight hung at each floor and
    the roof, from the gravity load path (no live load)."""
    from core import wanic_calc as C
    calc = dict((data or {}).get("calc") or {})
    calc.update(method="WSD", ll_floor=0.0, ll_roof=0.0)
    res = C.analyse({**(data or {}), "calc": calc})
    by = {}
    for c in res["cards"]:
        by[c["floor"]] = by.get(c["floor"], 0.0) + c["P"]
    n = max((f for f in by if f >= 0), default=-1) + 1
    from core import wanic_building as B
    H = float(B.settings_of(data or {})["floor_h"])
    out = []
    for j in range(1, n + 1):
        W = by.get(j - 1, 0.0) - by.get(j, 0.0)
        out.append((j, j * H, max(W, 0.0)))
    return out


def plan_size(data) -> tuple:
    from core import wanic_building as B
    from core import wanic_rc as R
    xs, ys = R.grid_axes(B.elements(data or {}))
    return (max(xs) - min(xs) if xs else 8.0), (max(ys) - min(ys) if ys else 8.0)


def seismic(p: dict, levels: list, D: float) -> dict:
    """{"V", "T", "C" (the coefficient), "F": [per level], "text"}; D the plan
    depth along the shaking (m), used by the old T."""
    W = sum(w for _j, _h, w in levels)
    if not p.get("eq_on"):
        return {"V": 0.0, "W": W, "T": 0.0, "C": 0.0, "F": [0.0] * len(levels),
                "text": "ไม่คิดแรงแผ่นดินไหว (นอกพื้นที่บังคับใช้ หรือยังไม่ได้กรอกค่า Ss / S1 ตามอำเภอ)"}
    hn = max((h for _j, h, _w in levels), default=3.0)
    steel = p["system"].startswith("steel")
    if p["standard"] == "new":
        Fa, Fv = site_factors(p["site"], p["Ss"], p["S1"])
        SDS, SD1 = 2 / 3 * Fa * p["Ss"], 2 / 3 * Fv * p["S1"]
        T = 0.0466 * hn ** 0.9 if steel else 0.02 * hn
        Ts = SD1 / SDS if SDS else 0.0
        Sa = SDS if T <= Ts else (SD1 / T if T else SDS)
        R = SYSTEMS[p["system"]][1]
        Cs = Sa * p["I"] / R
        Cs = max(Cs, 0.01)
        V = Cs * W
        k = 1.0 if T <= 0.5 else (2.0 if T >= 2.5 else 1 + (T - 0.5) / 2)
        Ft = 0.0
        text = (f"มยผ. 1301/1302-61 · ชั้นดิน {p['site']} · Ss {p['Ss']:g} S1 {p['S1']:g} → Fa {Fa:.2f} Fv {Fv:.2f} · "
                f"SDS {SDS:.3f} SD1 {SD1:.3f} · T = {T:.3f} วินาที · Sa {Sa:.3f} · R {R:g} · I {p['I']:g} · "
                f"Cs = {Cs:.4f}")
    else:
        T = 0.09 * hn / math.sqrt(max(D, 1.0))
        Cc = min(1 / (15 * math.sqrt(T)), 0.12)
        S = p["S_old"]
        CS = min(Cc * S, 0.14)
        Z, K = ZONE_Z[p["zone"]], K_OLD[p["system"]]
        Cs = Z * p["I"] * K * CS
        V = Cs * W
        k = 1.0
        Ft = min(0.07 * T * V, 0.25 * V) if T > 0.7 else 0.0
        text = (f"กฎกระทรวง 2550 (สูตรเดิม) · เขต {p['zone']} Z {Z:g} · I {p['I']:g} · K {K:g} · T = 0.09hn/√D = "
                f"{T:.3f} วินาที · C {Cc:.4f} · S {S:g} (CS ≤ 0.14) · V = ZIKCSW → {Cs:.4f}·W")
    den = sum(w * h ** k for _j, h, w in levels) or 1.0
    F = [(V - Ft) * w * h ** k / den for _j, h, w in levels]
    if F:
        F[-1] += Ft
    return {"V": V, "W": W, "T": T, "C": Cs, "F": F, "text": text}


def wind(p: dict, levels: list, B_: float, top_extra: float = 0.0) -> dict:
    """The wind across a face B_ (m) wide: {"V", "F": [per level], "p": [kg/m²], "text"};
    ``top_extra`` the height above the top level that catches wind (the
    roof's average projected height), hung on the top level."""
    H = levels[0][1] if levels else 3.0
    F, ps = [], []
    for idx, (_j, h, _w) in enumerate(levels):
        hb = levels[idx - 1][1] if idx else 0.0
        trib = (h - hb) / 2 + ((levels[idx + 1][1] - h) / 2 if idx + 1 < len(levels) else top_extra)
        if p["wind_std"] == "new":
            V50, Tf = WIND_ZONES[p["wind_zone"]]
            q = 0.5 * 1.25 * V50 ** 2 / 9.81                       # kg/m²
            Ce = max((h / 10) ** 0.2, 0.9) if p["terrain"] == "A" else max(0.7 * (h / 12) ** 0.3, 0.7)
            pr = p["Iw"] * q * Tf * Ce * 2.0 * (0.8 + 0.5)
        else:
            pr = 50.0 if h <= 10 else 80.0 if h <= 20 else 120.0 if h <= 40 else 160.0
        ps.append(pr)
        F.append(pr * trib * B_)
    if p["wind_std"] == "new":
        V50, Tf = WIND_ZONES[p["wind_zone"]]
        q = 0.5 * 1.25 * V50 ** 2 / 9.81
        text = (f"มยผ. 1311-50 · เขตลม {p['wind_zone']} V50 {V50:g} ม./วินาที · q = {q:.1f} กก./ตร.ม. · TF {Tf:g} · "
                f"ภูมิประเทศ {'A โล่ง' if p['terrain'] == 'A' else 'B ชานเมือง'} · Iw {p['Iw']:g} · Cg 2.0 · "
                f"Cp 0.8 + 0.5")
    else:
        text = "กฎกระทรวง ฉบับที่ 6 (2527) (สูตรเดิม) · ≤10 ม. 50 · 10–20 ม. 80 · 20–40 ม. 120 · >40 ม. 160 กก./ตร.ม."
    return {"V": sum(F), "F": F, "p": ps, "text": text, "H": H}


def analyse(data) -> dict:
    """Both actions in both directions and the column checks."""
    from core import wanic_calc as C
    p = params_of(data)
    lv = level_weights(data)
    Lx, Ly = plan_size(data)
    eq = {"X": seismic(p, lv, Lx), "Y": seismic(p, lv, Ly)}
    from core import wanic_building as B
    s_ = B.settings_of(data or {})
    rise = 0.0
    if s_.get("roof") in B.ROOF_TYPES:
        rise = min(Lx, Ly) / 2 * math.tan(math.radians(float(s_.get("pitch", 20) or 20)))
    # wind along X loads the face Ly wide (and the roof's gable / slope above it, half its rise on average)
    wd = {"X": wind(p, lv, Ly, rise / 2), "Y": wind(p, lv, Lx, rise / 2)}
    grav = C.analyse(data)
    b_ = grav["basis"]
    H = float(B.settings_of(data or {})["floor_h"])
    checks = []
    nfl = len(lv)
    for f in range(nfl):
        cols = [c for c in grav["cards"] if c["floor"] == f]
        if not cols:
            continue
        acts = (("แผ่นดินไหว", eq, 1.87), ("ลม", wd, 1.6)) if p.get("eq_on") else (("ลม", wd, 1.6),)
        for act, res, fac in acts:
            for d_ in ("X", "Y"):
                Vs = sum(res[d_]["F"][f:])                       # the storey shear under level f+1 and up
                Vc = Vs / len(cols)
                Mc = Vc * H / 2
                worst = None
                for c in cols:
                    curve = C.pm_curve(c["spec"], b_)
                    Pu = 0.75 * c["P"] if b_["method"] == "SDM" else 0.75 * 1.55 * c["P"]
                    Mu = 0.75 * fac * Mc
                    r = C.pm_ratio(curve, Mu, Pu)
                    if worst is None or r > worst[0]:
                        worst = (r, c, Pu, Mu)
                r, c, Pu, Mu = worst
                checks.append({"floor": f, "action": act, "dir": d_, "V": Vs, "Vc": Vc, "Mu": Mu, "Pu": Pu,
                               "ratio": r, "col": f"{c['mark']} ({c['x']:.2f}, {c['y']:.2f})", "n": len(cols)})
    return {"params": p, "levels": lv, "eq": eq, "wind": wd, "checks": checks, "size": (Lx, Ly), "H": H}
