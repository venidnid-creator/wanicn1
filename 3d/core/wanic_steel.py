# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
"""เหล็กรูปพรรณ: steel WF / H beams and columns of the building, and their
base plates — allowable stress design (AISC ASD, as Thai practice).

- beams: the building's beam lines above the ground (the same continuous
  beam analysis as the RC design, at service loads); bending Fb = 0.66 Fy
  when the compression flange is braced within Lc, else the lateral-torsional
  Fb = 843,700 Cb / (Lb·d/Af) (≤ 0.60 Fy); shear 0.40 Fy on the web;
  deflection L/360 under the service load;
- columns: the load each column carries (from the roof down, floor by
  floor) with a minimum eccentricity; Fa from KL/r against Cc, the
  interaction fa/Fa + Cm·fb/((1 − fa/F′e)·Fb) ≤ 1 (fa/Fa > 0.15) else
  fa/Fa + fb/Fb ≤ 1;
- base plates on the RC stumps: bearing 0.35 fc′, t = √(3 fp m² / 0.75 Fy).

The sections are the JIS / มอก. 1227 rolled shapes; their properties are
computed from the plate dimensions (fillets left out — a little on the safe
side). Units: kg, cm, ksc unless named."""
from __future__ import annotations

import math
from dataclasses import dataclass

E = 2.04e6


@dataclass
class WF:
    label: str
    d: float           # cm
    bf: float
    tw: float
    tf: float
    kg_m: float

    @property
    def A(self):
        return 2 * self.bf * self.tf + (self.d - 2 * self.tf) * self.tw

    @property
    def Ix(self):
        hw = self.d - 2 * self.tf
        return (self.bf * self.d ** 3 - (self.bf - self.tw) * hw ** 3) / 12

    @property
    def Iy(self):
        hw = self.d - 2 * self.tf
        return 2 * self.tf * self.bf ** 3 / 12 + hw * self.tw ** 3 / 12

    @property
    def Sx(self):
        return self.Ix / (self.d / 2)

    @property
    def rx(self):
        return math.sqrt(self.Ix / self.A)

    @property
    def ry(self):
        return math.sqrt(self.Iy / self.A)


def _wf(H, B, tw, tf, kg):
    return WF(f"{'H' if H == B else 'WF'} {H:g}×{B:g}×{tw:g}×{tf:g}", H / 10, B / 10, tw / 10, tf / 10, kg)


#: the rolled shapes, lightest first — WF for beams, H (and wide WF) for columns
BEAMS = sorted([_wf(*r) for r in ((100, 50, 5, 7, 9.3), (125, 60, 6, 8, 13.2), (150, 75, 5, 7, 14.0),
                                  (175, 90, 5, 8, 18.1), (200, 100, 5.5, 8, 21.3), (250, 125, 6, 9, 29.6),
                                  (300, 150, 6.5, 9, 36.7), (350, 175, 7, 11, 49.6), (400, 200, 8, 13, 66.0),
                                  (450, 200, 9, 14, 76.0), (500, 200, 10, 16, 89.6), (600, 200, 11, 17, 106.0))],
               key=lambda s: s.kg_m)
COLUMNS = sorted([_wf(*r) for r in ((100, 100, 6, 8, 17.2), (125, 125, 6.5, 9, 23.8), (150, 150, 7, 10, 31.5),
                                    (175, 175, 7.5, 11, 40.2), (200, 200, 8, 12, 49.9), (250, 250, 9, 14, 72.4),
                                    (300, 300, 10, 15, 94.0), (350, 350, 12, 19, 137.0),
                                    (400, 400, 13, 21, 172.0))], key=lambda s: s.kg_m)


def lookup(label: str):
    for s in BEAMS + COLUMNS:
        if s.label == label:
            return s
    return None


# ---- the checks --------------------------------------------------------------------------

def Fb_of(s: WF, Lb_cm: float, Fy: float, Cb: float = 1.0) -> float:
    Af = s.bf * s.tf
    Lc = min(637 * s.bf / math.sqrt(Fy), 1_406_000 / ((s.d / Af) * Fy))
    if Lb_cm <= Lc:
        return 0.66 * Fy
    return min(0.60 * Fy, 843_700 * Cb / (Lb_cm * s.d / Af))


def Fa_of(klr: float, Fy: float) -> float:
    Cc = math.sqrt(2 * math.pi ** 2 * E / Fy)
    if klr <= Cc:
        fs = 5 / 3 + 3 * (klr / Cc) / 8 - (klr / Cc) ** 3 / 8
        return (1 - klr ** 2 / (2 * Cc ** 2)) * Fy / fs
    return 12 * math.pi ** 2 * E / (23 * klr ** 2)


@dataclass
class Check:
    sec: WF
    ratio: float
    text: str                     # the governing numbers, for the table and the booklet

    @property
    def ok(self):
        return self.ratio <= 1.0 + 1e-9


def beam_check(s: WF, L: float, M: float, V: float, Lb: float, Fy: float, defl: float = 360.0,
               w: float = 0.0) -> Check:
    """L, Lb in m; M kg·m (the largest of ±); V kg; w kg/m (service, for the deflection)."""
    fb = abs(M) * 100 / s.Sx
    Fb = Fb_of(s, Lb * 100, Fy)
    fv = abs(V) / (s.d * s.tw)
    Fv = 0.40 * Fy
    dmax = 5 * (w / 100) * (L * 100) ** 4 / (384 * E * s.Ix) if w else 0.0
    dall = L * 100 / defl
    r = max(fb / Fb, fv / Fv, dmax / dall if dall else 0.0)
    return Check(s, r, f"fb {fb:,.0f}/Fb {Fb:,.0f} · fv {fv:,.0f}/Fv {Fv:,.0f} · Δ {dmax * 10:.1f}/{dall * 10:.1f} มม.")


def column_check(s: WF, P: float, M: float, H: float, Fy: float, K: float = 1.0) -> Check:
    """P kg, M kg·m about the strong axis, H the storey height (m)."""
    klr = K * H * 100 / s.ry
    Fa = Fa_of(klr, Fy)
    fa = P / s.A
    fb = abs(M) * 100 / s.Sx
    Fb = 0.60 * Fy
    if fa / Fa > 0.15:
        Fe = 12 * math.pi ** 2 * E / (23 * (K * H * 100 / s.rx) ** 2)
        r = fa / Fa + 0.85 * fb / ((1 - fa / Fe) * Fb) if fa < Fe else 9.9
    else:
        r = fa / Fa + fb / Fb
    if klr > 200:
        r = max(r, 9.9)
    return Check(s, r, f"fa {fa:,.0f}/Fa {Fa:,.0f} · fb {fb:,.0f}/Fb {Fb:,.0f} · KL/r {klr:.0f}")


def pick(cands, test):
    """The lightest section whose check passes (else the heaviest, failing)."""
    last = None
    for s in cands:
        last = test(s)
        if last.ok:
            return last
    return last


def base_plate(s: WF, P: float, M: float, fc: float, Fy: float) -> dict:
    """Plate N×B (cm) round the column + 5 cm each side, the bearing
    P/A ± 6M/(B·N²) ≤ 0.35 fc′, and the thickness from the larger cantilever."""
    N = math.ceil((s.d + 10) / 2.5) * 2.5
    B = math.ceil((s.bf + 10) / 2.5) * 2.5
    fp_all = 0.35 * fc
    while True:
        fmax = P / (B * N) + 6 * abs(M) * 100 / (B * N * N)
        if fmax <= fp_all or N > 120:
            break
        N += 2.5
        B += 2.5
    m = (N - 0.95 * s.d) / 2
    n = (B - 0.80 * s.bf) / 2
    c = max(m, n)
    t = math.sqrt(3 * fmax * c * c / (0.75 * Fy)) * 10                       # mm
    t = max(9.0, math.ceil(t / 3 - 1e-6) * 3)
    bolts = "4-Ø16 มม." if P < 20_000 else "4-Ø20 มม."
    return {"N": N, "B": B, "fp": fmax, "fp_all": fp_all, "t": t, "bolts": bolts + " ยาวฝัง 40 ซม."}


# ---- the building ------------------------------------------------------------------------

STEEL_DEFAULTS = {"beams": True, "columns": True, "lb": 0.5, "ecc": 0.05, "defl": 360.0, "group": True}


def settings(data) -> dict:
    return {**STEEL_DEFAULTS, **((data or {}).get("steel") or {})}


def design_building(data) -> dict:
    """The beams above the ground and the columns from the ground floor up,
    in steel: {"beams": [row], "columns": [row], "weight": kg, "settings"}.
    Each row: name, L/H, the forces, the Check, (columns) the base plate."""
    from core import wanic_calc as C
    st = settings(data)
    calc = dict((data or {}).get("calc") or {})
    calc["method"] = "WSD"                         # ASD steel: the service loads
    res = C.analyse({**(data or {}), "calc": calc})
    b_ = res["basis"]
    Fy = float(b_["fy_steel"])
    fc = float(b_["fc"])
    beams, cols = [], []
    weight = 0.0
    if st["beams"]:
        for name, br in res["beams"].items():
            if getattr(br, "level", 0) <= 0 and not getattr(br, "z", 0):
                continue                           # ground beams stay RC
            if getattr(br, "ground", False):
                continue
            Lmax = max(sp.L for sp in br.spans)
            wmax = max(sp.w for sp in br.spans)
            M = max(abs(br.Mmax), abs(br.Mmin))
            chk = pick(BEAMS, lambda s: beam_check(s, Lmax, M, br.Vmax, Lmax * float(st["lb"]), Fy,
                                                   float(st["defl"]), wmax))
            length = sum(sp.L for sp in br.spans)
            beams.append({"name": name, "L": Lmax, "length": length, "M": M, "V": br.Vmax, "check": chk,
                          "w": wmax, "key": (getattr(br, "mark", ""), getattr(br, "level", 0))})
    if st["columns"]:
        for c in res["cards"]:
            if c["floor"] < 0:
                continue
            H = float(c.get("H") or 3.0)
            M = c["P"] * float(st["ecc"])
            chk = pick(COLUMNS, lambda s: column_check(s, c["P"], M, H, Fy))
            row = {"name": f"{c['mark']} ชั้น {c['floor'] + 1} ({c['x']:.2f}, {c['y']:.2f})", "H": H,
                   "P": c["P"], "M": M, "check": chk, "floor": c["floor"], "key": (c["mark"], c["floor"])}
            cols.append(row)
    if st["group"]:
        # one size per mark and floor (กลุ่มเดียวกันใช้หน้าตัดเดียวกัน): the heaviest of the group
        for rows, redo in ((beams, lambda r, s: beam_check(s, r["L"], r["M"], r["V"], r["L"] * float(st["lb"]),
                                                           Fy, float(st["defl"]), r["w"])),
                           (cols, lambda r, s: column_check(s, r["P"], r["M"], r["H"], Fy))):
            big = {}
            for r in rows:
                if r["key"] not in big or r["check"].sec.kg_m > big[r["key"]].kg_m:
                    big[r["key"]] = r["check"].sec
            for r in rows:
                r["check"] = redo(r, big[r["key"]])
    for r in cols:
        if r["floor"] == 0:
            r["plate"] = base_plate(r["check"].sec, r["P"], r["M"], fc, Fy)
        weight += r["check"].sec.kg_m * r["H"]
    weight += sum(r["check"].sec.kg_m * r["length"] for r in beams)
    return {"beams": beams, "columns": cols, "weight": weight, "settings": st, "basis": b_}
