# -*- coding: utf-8 -*-
"""Wind load — กฎกระทรวง พ.ศ. 2566 ข้อ 17 [MR2566-17].

For a building rectangular (or nearly) in plan, not higher than 40 m and
not higher than three times its least width, the wind pressure may be
taken from the law's tables, by the height of the part of the building:

    table 1, urban / suburban:  ≤ 10 m 60, 10–20 m 80, 20–40 m 120 kg/m²
    table 2, open / coastal:    ≤ 10 m 100, 10–20 m 120, 20–40 m 160 kg/m²

and public buildings of 1,000 m² or more add 15%. Other buildings need the
detailed method announced by the Minister.

The pressure acts on the projected facade (and the roof's projected
height at the top); each level takes the facade from mid-storey below to
mid-storey above. The floor forces go to the frame lines as for the
earthquake (rigid floors, stiffness, eccentricity of the facade centre)
[STATICS], then the members are checked with the combinations of
ข้อ 6 (2) and ข้อ 7 (2):

    strength:   0.75(1.4D + 1.7L) + 1.6W,   0.9D + 1.6W   (beams, columns)
    allowable:  D + 0.75(L + W),            0.6D + W      (piles, soil)

with the strength reduction factors of ข้อ 8 [MR2566-8].
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from ..standards import cite
from .materials import FY
from .seismic import (BAR_OPTIONS, MemberCheck, _add, _bars_fit, _pile_points, as_for, column_bars, lateral_forces,
                      parse_bars, phi_mn_at, phi_mn_beam, pm_curve, tie_spacing)
from .sections import bar_area, load_piles, pick_bars

BANDS = [(10.0, 60.0, 100.0), (20.0, 80.0, 120.0), (40.0, 120.0, 160.0)]    # top of band, urban, open
TERRAINS = [("urban", "เมืองหรือชานเมือง (ตารางที่ 1)"), ("open", "โล่งหรือชายฝั่งทะเล (ตารางที่ 2)")]
PUBLIC_USES = {"assembly", "commercial", "school", "hospital"}
PUBLIC_FACTOR = 1.15
DRIFT_ADVICE = 1 / 400          # serviceability, not a rule of the law
STIRRUP = "RB6"
REFS = cite("MR2566-17", "MI2567-22", "MR2566-6", "MR2566-7", "MR2566-8", "STATICS", "ACI318-STIFF", "EIT1008")


@dataclass
class WindLevel:
    level: str
    z0: float
    z1: float
    fx: float           # force at the level, wind along X, kg
    fy: float
    vx: float           # storey shear below the level
    vy: float
    drift_x: float      # storey drift ratio Δ/h
    drift_y: float
    note: str = ""


@dataclass
class WindResult:
    terrain: str
    public: bool
    height: float
    least_width: float
    applicable: bool
    pressures: list = field(default_factory=list)      # (band text, kg/m²)
    levels: list = field(default_factory=list)
    checks: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    refs: str = REFS

    @property
    def ok(self) -> bool:
        return self.applicable and all(c.ok for c in self.checks)

    @property
    def base_shear(self) -> tuple[float, float]:
        return (self.levels[0].vx, self.levels[0].vy) if self.levels else (0.0, 0.0)


def pressure(z: float, terrain: str, public: bool) -> float:
    """Wind pressure (kg/m²) on the part of the building at height ``z`` m."""
    col = 1 if terrain == "urban" else 2
    q = next((band[col] for band in BANDS if z <= band[0] + 1e-9), BANDS[-1][col])
    return q * (PUBLIC_FACTOR if public else 1.0)


def force_on(z0: float, z1: float, width: float, terrain: str, public: bool) -> float:
    """Wind force on a strip of facade from height z0 to z1 (m) and ``width`` m."""
    if z1 <= z0:
        return 0.0
    edges = sorted({z0, z1} | {band[0] for band in BANDS if z0 < band[0] < z1})
    return sum(pressure((a + c) / 2, terrain, public) * (c - a) * width for a, c in zip(edges, edges[1:]))


def roof_rise(b) -> float:
    if not any(lv.slab == "roof" for lv in b.levels):
        return 0.0
    from .roofs import geometry
    return geometry(b).rise


IMPORTANCE = [("low", "น้อย (อาคารเกษตร อาคารชั่วคราว)"), ("normal", "ปกติ"),
              ("high", "มาก (ชุมนุมคน > 300 คน โรงเรียน > 250 คน ฯลฯ)"),
              ("very_high", "สูงมาก (โรงพยาบาลฉุกเฉิน สถานีดับเพลิง โรงไฟฟ้า ฯลฯ)")]


def is_public(b) -> bool:
    """+15%: a public building of 1,000 m² or more [MR2566-17], or a building of
    high or very high importance (ประกาศ มท. 2567 ข้อ 22 ตาราง 6) [MI2567-22]."""
    w = b.wind
    if w.importance in ("high", "very_high"):
        return True
    if w.public in ("yes", "no"):
        return w.public == "yes"
    floors = sum(1 for lv in b.levels if lv.slab in ("suspended", "precast", "on_ground"))
    return b.occupancy in PUBLIC_USES and b.xs[-1] * b.ys[-1] * max(1, floors) >= 1000.0


def level_forces(b):
    """``(F_x, F_y, rows)`` — wind force at every level for wind along X
    (on the facade of width = building depth in Y) and along Y."""
    lv = b.levels
    n = len(lv)
    ground = lv[0].elevation
    top = lv[-1].elevation
    rise = roof_rise(b)
    pub = is_public(b)
    t = b.wind.terrain
    e = b.roof.overhang if rise else 0.0
    Fx, Fy, rows = [0.0] * n, [0.0] * n, []
    for li in range(n):
        z0 = ground if li == 0 else (lv[li - 1].elevation + lv[li].elevation) / 2
        z1 = (lv[li].elevation + lv[li + 1].elevation) / 2 if li + 1 < n else top
        Fx[li] = force_on(z0 - ground, z1 - ground, b.ys[-1], t, pub)
        Fy[li] = force_on(z0 - ground, z1 - ground, b.xs[-1], t, pub)
        if li == n - 1 and rise:
            Fx[li] += force_on(top - ground, top - ground + rise, b.ys[-1] + 2 * e, t, pub)
            Fy[li] += force_on(top - ground, top - ground + rise, b.xs[-1] + 2 * e, t, pub)
        rows.append((lv[li].name, z0 - ground, (z1 if li + 1 < n else top + rise) - ground))
    return Fx, Fy, rows


def analyse(b, res, col_at, z_base):
    lv = b.levels
    n = len(lv)
    rise = roof_rise(b)
    H = lv[-1].elevation - lv[0].elevation + rise
    least = min(b.xs[-1], b.ys[-1])
    pub = is_public(b)
    ok = H <= 40.0 + 1e-9 and H <= 3 * least + 1e-9
    out = WindResult(b.wind.terrain, pub, H, least, ok)
    for text, z in (("สูงไม่เกิน 10 ม.", 5.0), ("10–20 ม.", 15.0), ("20–40 ม.", 30.0)):
        out.pressures.append((text, pressure(z, b.wind.terrain, pub)))
    if not ok:
        out.warnings.append(f"NG อาคารสูง {H:.1f} ม. เกิน 40 ม. หรือเกิน 3 เท่าความกว้างน้อยที่สุด {least:.1f} ม. "
                            "ต้องคำนวณแรงลมด้วยวิธีที่รัฐมนตรีประกาศ (เช่น มยผ. 1311)")
    Fx, Fy, rows = level_forces(b)
    centres = [(b.xs[-1] / 2, b.ys[-1] / 2)] * n                   # the facade centre
    cf, bf, drift = lateral_forces(b, res, col_at, z_base, {"x": Fx, "y": Fy}, centres, 0.0, first=0)
    vx = vy = 0.0
    for li in reversed(range(n)):
        vx += Fx[li]
        vy += Fy[li]
        hs = lv[li].elevation - lv[li - 1].elevation if li else 0.0
        dx = drift["x"][li] / hs if hs else 0.0
        dy = drift["y"][li] / hs if hs else 0.0
        note = "การเคลื่อนตัวเกิน h/400 (คำแนะนำด้านการใช้งาน)" if max(dx, dy) > DRIFT_ADVICE else ""
        out.levels.append(WindLevel(rows[li][0], rows[li][1], rows[li][2], Fx[li], Fy[li], vx, vy, dx, dy, note))
    out.levels.reverse()
    return out, cf, bf


def _delta_s(res, li, d):
    return next((st.delta_s for st in getattr(res.frames, "stability", []) if st.li == li and st.direction == d),
                1.0)


def check_columns(b, res, out, cf, col_at, mat) -> bool:
    fc, fy = mat.fc_usd, FY[mat.main_grade]       # ข้อ 29 (5)
    changed = False
    for (i, j, li), c in col_at.items():
        name = b.node_name(i, j)
        D, L = c.load - c.live, c.live
        worst = None
        for d in ("x", "y"):
            M, N, _V, _mb = cf.get((name, li, d), (0.0, 0.0, 0.0, 0.0))
            M *= _delta_s(res, li, d)                                    # sway magnifier
            o = "y" if d == "x" else "x"
            md, ml = (c.m_dx, c.m_lx) if d == "x" else (c.m_dy, c.m_ly)
            mdo, mlo = (c.m_dx, c.m_lx) if o == "x" else (c.m_dy, c.m_ly)
            combos = [(0.75 * (1.4 * D + 1.7 * L) + 1.6 * N, 0.75 * (1.4 * md + 1.7 * ml) + 1.6 * M,
                       0.75 * (1.4 * mdo + 1.7 * mlo)),
                      (0.9 * D - 1.6 * N, 0.9 * md + 1.6 * M, 0.9 * mdo)]
            while True:
                r = max(_ratio(c, d, pu, mu, mo, fc, fy) for pu, mu, mo in combos)
                if r[0] <= 1.0:
                    break
                did, grew = _strengthen(c)
                changed = changed or grew
                if not did:
                    break
            if worst is None or r[0] > worst[0][0]:
                worst = (r, d)
        r, d = worst
        ok = r[0] <= 1.0
        if not ok:
            c.ok = False
            c.note = _add(c.note, "ไม่ผ่านการตรวจแรงลม")
        c.refs = _ref(c.refs)
        out.checks.append(MemberCheck("column", f"{name} {c.segment}", d, f"Pu {r[1]:,.0f} Mu {r[2]:,.0f}",
                                      f"φMn {r[3]:,.0f}", round(float(r[0]), 3), "", bool(ok),
                                      f"{c.b:.2f}×{c.h:.2f} {c.bars}"))
    return changed


def _ratio(c, d, pu, mu, mo, fc, fy):
    n, size = parse_bars(c.bars)
    out = 0.0
    caps = []
    for dd, m in ((d, mu), ("y" if d == "x" else "x", mo)):
        depth, width = (c.b * 100, c.h * 100) if dd == "x" else (c.h * 100, c.b * 100)
        cap = phi_mn_at(pm_curve(depth, width, column_bars(n, size, depth, width), fc, fy), pu) / 100
        caps.append(cap)
        out += math.inf if cap <= 0 and m > 0 else (m / cap if cap > 0 else 0.0)
    return out, pu, mu, caps[0]


def _strengthen(c) -> tuple[bool, bool]:
    """More bars, or else a larger section: ``(changed, section grew)``."""
    n, size = parse_bars(c.bars)
    ag = c.b * c.h * 1e4
    for nn, ss in BAR_OPTIONS:
        if nn * bar_area(ss) > n * bar_area(size) + 1e-9 and nn * bar_area(ss) <= 0.04 * ag \
                and _bars_fit(nn, ss, min(c.b, c.h) * 100):
            c.bars, c.pg = f"{nn}-{ss}", nn * bar_area(ss) / ag
            c.note = _add(c.note, "เพิ่มเหล็กรับแรงลม")
            return True, False
    if max(c.b, c.h) >= 0.60:
        return False, False
    c.b, c.h = round(c.b + 0.05, 2), round(c.h + 0.05, 2)
    c.pg = n * bar_area(size) / (c.b * c.h * 1e4)
    c.note = _add(c.note, "ขยายหน้าตัดรับแรงลม")
    return True, True


def _ref(refs):
    parts = [p.strip() for p in (refs or "").split(",") if p.strip()]
    for code in ("MR2566-17", "MR2566-7"):
        if code not in parts:
            parts.append(code)
    return ", ".join(parts)


def check_beams(b, res, out, bf, mat):
    fc, fy = mat.fc_usd, FY[mat.main_grade]       # ข้อ 29 (5)
    for x in res.beams:
        if id(x) not in bf:
            continue
        MW, VW = bf[id(x)]
        bw, d = x.b * 100, x.h * 100 - x.d_off
        MD = max(0.0, x.m_neg - x.m_neg_live)
        mu_neg = 0.75 * (1.4 * MD + 1.7 * x.m_neg_live) + 1.6 * MW
        mu_pos = max(0.0, 1.6 * MW - 0.9 * MD)
        notes, ok = [], True
        nt, st = parse_bars(x.top)
        nb, sb = parse_bars(x.bottom)
        as_t, as_b = nt * bar_area(st), nb * bar_area(sb)
        need_t = as_for(mu_neg * 100, bw, d, fc, fy)
        need_b = as_for(mu_pos * 100, bw, d, fc, fy)
        if need_t is None or need_b is None:
            ok = False
            notes.append("หน้าตัดคานเล็กเกินไปสำหรับแรงลม")
        else:
            if need_t > as_t + 1e-9:
                n, s = pick_bars(need_t, bw)
                x.top, as_t = f"{n}-{s}", n * bar_area(s)
                notes.append("เพิ่มเหล็กบนรับแรงลม")
            if need_b > as_b + 1e-9:
                n, s = pick_bars(need_b, bw)
                x.bottom, as_b = f"{n}-{s}", n * bar_area(s)
                notes.append("เพิ่มเหล็กล่างรับแรงลม")
        vu = 0.75 * 1.7 * x.v + 1.6 * VW
        s_need = tie_spacing(vu, bw, d, fc)
        if s_need is None:
            ok = False
            notes.append("แรงเฉือนเกินกำลังหน้าตัด")
        else:
            cur = float(x.stirrup.split("@")[1]) * 100
            if s_need < cur:
                s_new = max(5.0, math.floor(s_need / 2.5 + 1e-9) * 2.5)
                x.stirrup = f"{STIRRUP}@{s_new / 100:.3f}".rstrip("0").rstrip(".")
                notes.append("ลดระยะเหล็กปลอกรับแรงลม")
        cap_t = phi_mn_beam(as_t, bw, d, fc, fy) / 100
        cap_b = phi_mn_beam(as_b, bw, d, fc, fy) / 100
        ratio = max(mu_neg / cap_t if cap_t else 99, mu_pos / cap_b if cap_b else 99)
        if ratio > 1.0 + 1e-6:
            ok = False
        if notes:
            x.note = _add(x.note, " ; ".join(notes))
        if not ok:
            x.ok = False
        x.refs = _ref(x.refs)
        out.checks.append(MemberCheck("beam", f"{x.level} {x.span}", "", f"Mu- {mu_neg:,.0f} Mu+ {mu_pos:,.0f} "
                                      f"Vu {vu:,.0f}", f"φMn- {cap_t:,.0f} φMn+ {cap_b:,.0f}",
                                      round(ratio, 3), x.stirrup, ok, f"บน {x.top} ล่าง {x.bottom}"))


def check_footings(b, res, out, cf, col_at, mat):
    from .design import design_footing
    piles = load_piles()
    for k, f in enumerate(res.footings):
        i, j = b.parse_node(f.node)
        c = col_at[(i, j, 0)]
        D, L = c.load - c.live, c.live
        new, P_design = f, f.load
        for _it in range(8):
            worst = (-1.0, None)
            for d in ("x", "y"):
                _M, N, _V, Mb = cf.get((f.node, 0, d), (0.0, 0.0, 0.0, 0.0))
                md, ml = (c.m_dx, c.m_lx) if d == "x" else (c.m_dy, c.m_ly)
                for P, M in ((D + 0.75 * L + 0.75 * N, md + 0.75 * ml + 0.75 * Mb),    # ข้อ 6 (2)
                             (0.6 * D - N, 0.6 * md + Mb)):
                    if new.kind == "pile":
                        pts = _pile_points(new.piles, piles[new.pile]["size_m"])
                        arm = [(p[0] if d == "x" else p[1]) for p in pts]
                        s2 = sum(a * a for a in arm)
                        extra = M * max(abs(a) for a in arm) / s2 if s2 else 0.0
                        rmax = (P + new.weight) / len(pts) + extra
                    else:
                        A, S = new.width * new.length, new.width * new.length ** 2 / 6
                        rmax = (P + new.weight) / A + M / S
                    if rmax / new.pile_capacity > worst[0]:
                        worst = (rmax / new.pile_capacity, (P, M, rmax, new.pile_capacity, d))
            if worst[0] <= 1.0 or not new.ok:
                break
            P_design *= worst[0] * 1.02
            new = design_footing(b, mat, f.node, P_design, c.b, c.h)
        ratio, (P, M, rmax, cap, d) = worst
        if new is not f:
            new.load = f.load
            new.note = _add(new.note, "เพิ่มเสาเข็ม/ขยายฐานรับแรงลม")
            res.footings[k] = new
        ok = ratio <= 1.0
        if not ok:
            new.ok = False
            new.note = _add(new.note, "ไม่ผ่านการตรวจแรงลม")
        new.refs = _ref(new.refs)
        unit = "กก./ต้น" if new.kind == "pile" else "กก./ตร.ม."
        out.checks.append(MemberCheck("footing", f.node, d, f"P {P:,.0f} กก. M {M:,.0f} กก.-ม.",
                                      f"{rmax:,.0f} ≤ {cap:,.0f} {unit}", round(ratio, 3), "", ok, ""))


def run(b, res, mat, col_at, z_base) -> WindResult:
    for _ in range(6):
        out, cf, bf = analyse(b, res, col_at, z_base)
        if not check_columns(b, res, out, cf, col_at, mat):
            break
    check_beams(b, res, out, bf, mat)
    check_footings(b, res, out, cf, col_at, mat)
    return out
