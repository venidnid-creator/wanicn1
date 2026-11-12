# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
"""แป · Sag Rod · Tie Rod · ผนังเมทัลชีท — the secondary steel of a roof
on trusses (or rafters) and of a sheeted wall. Allowable stress (ASD).

- purlins (แปเหล็กตัวซี) on the slope: the load splits into the normal
  w·cosθ (bending about the strong axis over the truss spacing) and the
  slope-wise w·sinθ (bending about the weak axis over the spans the sag
  rods leave); fbx/Fb + fby/Fb ≤ 1 with Fb = 0.60 Fy; deflection L/180
  under the normal service load; the wind uplift (suction less the dead
  load) the other way;
- sag rods (เหล็กยึดแป): the slope-wise pull of all the purlins below the
  ridge gathered in the top rod, a threaded round bar 0.60 Fy on 0.75 of
  its area;
- tie rods (ค้ำยันทแยง X-bracing in the end bays of the roof): the wind on
  the gable end wall shared by the braced bays, the diagonal in tension;
- wall girts (แปผนัง) of a metal-sheet wall: wind on the girt spacing,
  bending about the strong axis over the column spacing, the sheet's
  weight about the weak axis.

Units: kg, m, cm, ksc."""
from __future__ import annotations

import math
import re
from dataclasses import dataclass

FY = 2450.0
E = 2.04e6
RODS = (("RB9", 0.9), ("RB12", 1.2), ("RB16", 1.6), ("RB19", 1.9), ("RB25", 2.5))


@dataclass
class LipC:
    label: str
    H: float          # cm
    B: float
    C: float
    t: float

    def _parts(self):
        """Centre-line rectangles (x, y, w, h) — web on x = 0, the section
        symmetric about y = 0 (the strong axis)."""
        h, b, c, t = self.H - self.t, self.B - self.t, self.C - self.t / 2, self.t
        return [(0.0, 0.0, t, h), (b / 2, h / 2, b, t), (b / 2, -h / 2, b, t),
                (b, h / 2 - c / 2, t, c), (b, -h / 2 + c / 2, t, c)]

    @property
    def A(self):
        return sum(w * h for _x, _y, w, h in self._parts())

    @property
    def xc(self):
        return sum(x * w * h for x, _y, w, h in self._parts()) / self.A

    @property
    def Ix(self):
        return sum(w * h ** 3 / 12 + w * h * y * y for _x, y, w, h in self._parts())

    @property
    def Iy(self):
        xc = self.xc
        return sum(h * w ** 3 / 12 + w * h * (x - xc) ** 2 for x, _y, w, h in self._parts())

    @property
    def Sx(self):
        return self.Ix / (self.H / 2)

    @property
    def Sy(self):
        return self.Iy / max(self.xc, self.B - self.xc)

    @property
    def kg_m(self):
        return self.A * 0.785


def lipc(label: str) -> LipC:
    """"C 100×50×20×2.3" (mm) → a lipped channel."""
    nums = [float(v) for v in re.findall(r"\d+(?:\.\d+)?", label)]
    if len(nums) < 4:
        raise ValueError(f"ไม่ใช่เหล็กตัวซี: {label}")
    H, B, C, t = nums[:4]
    return LipC(f"C {H:g}×{B:g}×{C:g}×{t:g}", H / 10, B / 10, C / 10, t / 10)


CATALOG = sorted([lipc(f"C {h}×{b}×{c}×{t}") for h, b, c, t in
                  ((75, 45, 15, 1.6), (75, 45, 15, 2.3), (100, 50, 20, 1.6), (100, 50, 20, 2.3),
                   (100, 50, 20, 3.2), (125, 50, 20, 2.3), (125, 50, 20, 3.2), (150, 50, 20, 2.3),
                   (150, 65, 20, 2.3), (150, 65, 20, 3.2), (200, 75, 20, 3.2), (200, 75, 25, 4.5))],
                 key=lambda s: s.kg_m)

DEFAULTS = {"span": 0.0, "pitch": 0.0, "spacing": 0.0, "slope_len": 0.0, "sag_rods": 1, "section": "",
            "dead": 0.0, "live": 0.0, "wind": 0.0, "auto": True,
            # the gable end wall for the X-bracing, and the sheeted walls
            "eave_h": 0.0, "width": 0.0, "braced_bays": 2,
            "wall_sheet": False, "girt_span": 0.0, "girt_sp": 1.2, "girt": "", "sheet_kg": 5.0}


@dataclass
class Row:
    name: str
    demand: str
    capacity: str
    ratio: float
    note: str = ""

    @property
    def ok(self):
        return self.ratio <= 1.0 + 1e-9


def rod_for(T: float) -> tuple:
    """(name, ratio) — the smallest threaded rod with 0.60 Fy on 0.75 A."""
    for name, d in RODS:
        cap = 0.60 * FY * 0.75 * math.pi * d * d / 4
        if T <= cap:
            return name, T / cap, cap
    name, d = RODS[-1]
    cap = 0.60 * FY * 0.75 * math.pi * d * d / 4
    return name, T / cap, cap


def purlin_check(s: LipC, L: float, sp: float, pitch: float, dead: float, live: float, wind: float,
                 sag: int) -> tuple:
    """(ratio, text, (Mx, My), uplift ratio). Loads per m² of slope
    (dead incl. the sheet), live per m² of plan, wind suction per m²."""
    th = math.radians(pitch)
    w = (dead + live * math.cos(th)) * sp + s.kg_m                 # kg/m along the purlin, gravity
    wn, wt = w * math.cos(th), w * math.sin(th)
    Mx = wn * L * L / 8
    Ls = L / (sag + 1)
    My = wt * Ls * Ls / 8 if sag else wt * L * L / 8
    Fb = 0.60 * FY
    fbx, fby = Mx * 100 / s.Sx, My * 100 / s.Sy
    r = fbx / Fb + fby / Fb
    dl = 5 * (wn / 100) * (L * 100) ** 4 / (384 * E * s.Ix)
    rd = dl / (L * 100 / 180)
    # the wind suction (Cp 0.7 × the wind pressure) less the dead load
    up = max(0.7 * wind * sp - (dead * sp + s.kg_m) * math.cos(th), 0.0)
    Mu = up * L * L / 8
    ru = Mu * 100 / s.Sx / (Fb * 4 / 3)                             # wind: ⅓ increase
    ratio = max(r, rd, ru)
    text = (f"Mx {Mx:,.1f} · My {My:,.1f} กก.-ม. · fbx/Fb + fby/Fb = {r:.2f} · Δ {dl * 10:.1f}/"
            f"{L * 1000 / 180:.1f} มม. · แรงยกลม {up:,.1f} กก./ม.")
    return ratio, text, (Mx, My), ru


def params_of(data) -> dict:
    """data["purlin"] with the gaps filled from the building, its truss and
    the design basis."""
    from core import wanic_building as B
    from core import wanic_calc as C
    p = {**DEFAULTS, **((data or {}).get("purlin") or {})}
    s = B.settings_of(data or {})
    b_ = C.basis(data or {})
    tr = (data or {}).get("truss") or {}
    if not p["pitch"]:
        p["pitch"] = float(s.get("pitch", 20) or 20)
    if not p["span"]:
        p["span"] = float(tr.get("spacing") or 0) or float(s.get("rafter_sp", 1.0))
    if not p["spacing"]:
        p["spacing"] = float(s.get("purlin_sp", 0.32)) if not tr else 1.0
    if not p["dead"]:
        p["dead"] = C.tile_weight(s)
    if not p["live"]:
        p["live"] = float(b_["ll_roof"])
    if not p["wind"]:
        p["wind"] = float(b_["wind"])
    if not p["section"]:
        p["section"] = s.get("purlin", "C 75×45×15×2.3")
    width = 0.0
    try:
        from core import wanic_truss as T
        width = T.params_of(data or {})["span"]
    except Exception:                                    # noqa: BLE001 - no building
        width = 8.0
    if not p["width"]:
        p["width"] = width
    if not p["slope_len"]:
        p["slope_len"] = round(p["width"] / 2 / math.cos(math.radians(p["pitch"])), 2)
    if not p["eave_h"]:
        p["eave_h"] = float(s.get("floor_h", 3.0)) * max(1, len((data or {}).get("floors") or [1]))
    if not p["girt_span"]:
        p["girt_span"] = p["span"]
    if not p["girt"]:
        p["girt"] = "C 100×50×20×2.3"
    return p


def design(p: dict) -> dict:
    """{"purlin": (LipC, ratio, text), "rows": [Row], "rod", "tie", "girt"}."""
    rows = []
    sag = int(p["sag_rods"])
    if p.get("auto", True):
        cand = CATALOG
    else:
        cand = [lipc(p["section"])]
    pick = None
    for s in cand:
        r, text, _m, _u = purlin_check(s, p["span"], p["spacing"], p["pitch"], p["dead"], p["live"], p["wind"], sag)
        pick = (s, r, text)
        if r <= 1.0:
            break
    s, r, text = pick
    rows.append(Row(f"แป {s.label} ยาวช่วง {p['span']:.2f} ม. @ {p['spacing']:.2f} ม.", text,
                    f"Fb = 0.60Fy = {0.6 * FY:,.0f} กก./ตร.ซม.", r,
                    f"Sag Rod {sag} แนว/ช่วง" if sag else "ไม่มี Sag Rod"))
    # the sag rod at the ridge: every purlin on the slope hands it its
    # slope-wise share (the spans either side of the rod)
    th = math.radians(p["pitch"])
    n_purlins = max(1, int(round(p["slope_len"] / p["spacing"])) + 1)
    w = (p["dead"] + p["live"] * math.cos(th)) * p["spacing"] + s.kg_m
    share = p["span"] / (sag + 1) if sag else 0.0
    T_sag = w * math.sin(th) * share * n_purlins
    rod = None
    if sag:
        name, rr, cap = rod_for(T_sag)
        rod = name
        rows.append(Row(f"Sag Rod {name} (เกลียวทั้งสองปลาย)", f"T = {T_sag:,.0f} กก. (แป {n_purlins} ตัว/ข้าง)",
                        f"0.60Fy·0.75A = {cap:,.0f} กก.", rr))
    # tie rods: wind on half the gable wall (the eave + the gable triangle)
    # into the roof plane, shared by the braced bays, two slopes
    rise = p["width"] / 2 * math.tan(th)
    area = p["width"] * (p["eave_h"] + rise / 2)
    F = p["wind"] * area / 2
    per = F / max(1, int(p["braced_bays"])) / 2
    diag = math.atan2(p["slope_len"] / 2, p["span"])               # the X over one bay, half a slope deep
    T_tie = per / math.cos(diag)
    tname, tr_, tcap = rod_for(T_tie)
    rows.append(Row(f"Tie Rod (X-Bracing) {tname} ช่วงปลาย {int(p['braced_bays'])} ช่วง",
                    f"ลมหน้าจั่ว {F:,.0f} กก. → T = {T_tie:,.0f} กก./เส้น", f"{tcap:,.0f} กก.", tr_,
                    "ปรับแรงดึงด้วยเกลียวเร่ง (Turnbuckle)"))
    girt = None
    if p.get("wall_sheet"):
        g = lipc(p["girt"]) if not p.get("auto", True) else None
        for c in ([g] if g else CATALOG):
            wx = p["wind"] * p["girt_sp"]
            wy = p["sheet_kg"] * p["girt_sp"] + c.kg_m
            L = p["girt_span"]
            Mx, My = wx * L * L / 8, wy * (L / 2) ** 2 / 8
            rg = (Mx * 100 / c.Sx + My * 100 / c.Sy) / (0.60 * FY * 4 / 3)
            dl = 5 * (wx / 100) * (L * 100) ** 4 / (384 * E * c.Ix) / (L * 100 / 180)
            rg = max(rg, dl)
            girt = (c, rg)
            if rg <= 1.0:
                break
        c, rg = girt
        rows.append(Row(f"แปผนังเมทัลชีท {c.label} ช่วง {p['girt_span']:.2f} ม. @ {p['girt_sp']:.2f} ม.",
                        f"ลม {p['wind']:g} กก./ตร.ม. → Mx {wx * L * L / 8:,.1f} กก.-ม. · แผ่น {p['sheet_kg']:g} กก./ตร.ม.",
                        "Fb·4/3 (แรงลม)", rg, "Sag Rod ผนังกลางช่วง 1 แนว"))
    return {"purlin": pick, "rows": rows, "rod": rod, "tie": tname, "girt": girt, "n_purlins": n_purlins}


def design_of(data) -> tuple:
    p = params_of(data)
    return p, design(p)
