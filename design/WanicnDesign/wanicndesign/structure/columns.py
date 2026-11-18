# -*- coding: utf-8 -*-
"""Columns under axial load and bending from gravity loads.

1. Every grid line is analysed as a plane frame (fixed at the footing
   tops, cracked stiffness 0.70 Ig columns / 0.35 Ig beams [ACI318-STIFF])
   under the dead and the live loads of its beams, with the support moments
   of cantilever beams as joint moments [STATICS]. This gives the column
   end moments that a continuous beam on pins cannot, and the hogging
   moments at exterior supports; beam top steel is designed for the larger
   of the two analyses (an envelope).
2. Columns are checked by strength design [EIT1008] for 1.4D and
   1.2D + 1.6L: slenderness k·lu/r with k = 1 (non-sway), ignored up to 22;
   beyond, the moments are magnified by δ = Cm/(1 − Pu/0.75Pc) with Cm = 1,
   EI = 0.4·Ec·Ig/(1 + βdns), not less than M2,min = Pu(1.5 + 0.03h) cm
   [EIT1008-SLENDER]. Bending about both axes is combined linearly,
   Mux/φMnx + Muy/φMny ≤ 1 (the conservative form of the load contour)
   [EIT1008-BIAX].
3. The stability index Q = ΣPu·Δo/(Vus·lc) of each storey says whether the
   storey may be treated as non-sway (Q ≤ 0.05) [EIT1008-SLENDER].
4. Footings take the column base moments: pile loads P/n ± M·x/Σx² or soil
   pressure P/A ± M/S under service loads must stay within the allowable
   values; piles are added or the footing grows when they do not.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from ..standards import cite
from .materials import FY
from .seismic import (BAR_OPTIONS, _add, _bars_fit, _ec, build_frames, column_bars, parse_bars, phi_mn_at,
                      pm_curve)
from .sections import bar_area, load_piles

DIRS = ("x", "y")
LAMBDA_FREE = 22.0             # k·lu/r below which slenderness is ignored (non-sway, M1/M2 = +1)
LAMBDA_MAX = 100.0
Q_SWAY = 0.05


@dataclass
class StoreyStability:
    level: str          # the storey (column segment), e.g. "GB–FL2"
    direction: str
    q: float
    sway: bool
    li: int = 0

    @property
    def delta_s(self) -> float:
        """Sway magnifier 1/(1 − Q) ≥ 1 for the lateral-load moments [EIT1008-SLENDER]."""
        return 1.0 / (1.0 - self.q) if self.sway and self.q < 1 else (1.0 if not self.sway else math.inf)


@dataclass
class GravityFrameResult:
    stability: list = field(default_factory=list)
    beams_raised: int = 0
    refs: str = cite("STATICS", "ACI318-STIFF", "EIT1008", "EIT1008-SLENDER", "EIT1008-BIAX", "EIT1008-LOADS")


def _beam_member_loads(x, part):
    if part == "live":
        return -x.load_w_live, [(a, -P) for a, P in x.load_pts_live]
    q = -(x.load_w - x.load_w_live)
    return q, [(a, -P) for a, P in x.load_pts] + [(a, P) for a, P in x.load_pts_live]


def analyse(b, res, col_at, z_base):
    """Gravity moments into ``col_at`` results and beam hogging moments;
    returns ``(frames, beam_hog, stiffness)`` where ``stiffness[(li, d)]``
    is ΣV/Δ of the storey."""
    frames = build_frames(b, res, col_at, z_base)
    n_lv = len(b.levels)
    for c in col_at.values():
        c.m_dx = c.m_lx = c.m_dy = c.m_ly = 0.0
    cants = [x for x in res.beams if x.kind == "cantilever"]
    beam_hog: dict = {}
    stiff: dict = {}
    li_of = {lv.name: k for k, lv in enumerate(b.levels)}
    for fr in frames:
        d = fr.direction
        node_moments = {"dead": {}, "live": {}}
        for x in cants:
            x0, y0, x1, y1 = x.line_xy
            along_x = abs(y1 - y0) < 1e-9
            if (d == "x") != along_x or abs((y0 if along_x else x0) - fr.coord) > 1e-6:
                continue
            pos, sign = (x0, 1 if x1 > x0 else -1) if along_x else (y0, 1 if y1 > y0 else -1)
            key = (round(pos, 6), li_of[x.level])
            if key not in fr.index:
                continue
            n = fr.index[key]
            for part, M in (("dead", x.m_neg - x.m_neg_live), ("live", x.m_neg_live)):
                # load beyond the left end turns the joint counter-clockwise
                node_moments[part][n] = node_moments[part].get(n, 0.0) - sign * M
        totals = {}
        for part in ("dead", "live"):
            ml = {m: _beam_member_loads(x, part) for m, x in fr.beams}
            loads = {n: (0.0, 0.0, M) for n, M in node_moments[part].items()}
            _disp, mf = fr.solve_with(loads, ml)
            for m, name, li in fr.columns:
                M = float(max(abs(mf[m][2]), abs(mf[m][5])))
                c = col_at[(*_ij(b, name), li)]
                attr = f"m_{'d' if part == 'dead' else 'l'}{d}"
                setattr(c, attr, max(getattr(c, attr), M))
            for m, x in fr.beams:
                totals[m] = totals.get(m, 0.0) + mf[m]
        for m, x in fr.beams:
            f = totals[m]
            hog = float(max(f[2], -f[5], 0.0))
            beam_hog[id(x)] = max(beam_hog.get(id(x), 0.0), hog)
        # lateral stiffness of each storey: a load of 1 kg at every level
        disp, _mf = fr.solve({li: 1.0 * len(fr.level_nodes.get(li, [])) for li in range(n_lv)})
        drift: dict = {}
        for m, _name, li in fr.columns:
            mem = fr.members[m]
            drift[li] = max(drift.get(li, 0.0), abs(float(disp[mem.j][0] - disp[mem.i][0])))
        for li, dr in drift.items():
            V = sum(len(fr.level_nodes.get(k, [])) for k in range(li, n_lv))
            if dr > 0:
                stiff[(li, d)] = stiff.get((li, d), 0.0) + V / dr
    return frames, beam_hog, stiff


def _ij(b, name):
    return b.parse_node(name)


def raise_beam_end_moments(res, mat, beam_hog) -> int:
    """Top steel for the larger of the continuous-beam and frame hogging
    moments; returns how many beams changed."""
    from .design import _beam_design
    n = 0
    for x in res.beams:
        hog = beam_hog.get(id(x), 0.0)
        if hog > x.m_neg + 1e-6:
            x.m_neg = hog
            d_req, at, _ab, top, _bot, stir, ok = _beam_design(mat, x.b, x.h, hog, x.m_pos, x.v)
            if at > x.as_top + 1e-9:
                x.as_top, x.top = at, top
                x.note = _add(x.note, "เหล็กบนตามโมเมนต์ปลายจากโครงข้อแข็ง")
                n += 1
            x.d_req = max(x.d_req, d_req)
            if not ok:
                x.ok = False
                x.note = _add(x.note, "หน้าตัดไม่พอสำหรับโมเมนต์ปลาย")
            x.refs = _add_ref(x.refs, "ACI318-STIFF")
    return n


def _add_ref(refs: str, *codes) -> str:
    parts = [p.strip() for p in (refs or "").split(",") if p.strip()]
    for c in codes:
        if c not in parts:
            parts.append(c)
    return ", ".join(parts)


def magnifier(pu, pd, depth_cm, width_cm, lu_cm, fc):
    """``(λ, δ, slender)`` for bending with ``depth_cm`` in the plane."""
    r = 0.3 * depth_cm
    lam = lu_cm / r
    if lam <= LAMBDA_FREE or pu <= 0:
        return lam, 1.0, False
    ig = width_cm * depth_cm ** 3 / 12
    beta = min(1.0, 1.2 * pd / pu) if pu else 0.0          # βdns, sustained share
    ei = 0.4 * (_ec(fc) / 1e4) * ig / (1 + beta)
    pc = math.pi ** 2 * ei / lu_cm ** 2
    if pu >= 0.75 * pc:
        return lam, math.inf, True
    return lam, max(1.0, 1.0 / (1 - pu / (0.75 * pc))), True


def check_column(b, c, mat, lu: float):
    """Strength check of one column segment; returns ``(ratio, text)`` for
    the worse combination with the moments as magnified."""
    fc, fy = b.fc_prime, FY[mat.main_grade]
    PD, PL = c.load - c.live, c.live
    worst = (0.0, "")
    for pu, mx, my in ((1.4 * PD, 1.4 * c.m_dx, 1.4 * c.m_dy),
                       (1.2 * PD + 1.6 * PL, 1.2 * c.m_dx + 1.6 * c.m_lx, 1.2 * c.m_dy + 1.6 * c.m_ly)):
        n, size = parse_bars(c.bars)
        parts, text = [], []
        for d, m in (("x", mx), ("y", my)):
            depth, width = (c.b * 100, c.h * 100) if d == "x" else (c.h * 100, c.b * 100)
            lam, delta, slender = magnifier(pu, PD, depth, width, lu * 100, fc)
            if slender:
                m = max(m, pu * (1.5 + 0.03 * depth) / 100)            # M2,min
            mu = m * delta
            curve = pm_curve(depth, width, column_bars(n, size, depth, width), fc, fy)
            cap = phi_mn_at(curve, pu) / 100
            parts.append(math.inf if cap <= 0 else mu / cap)
            text.append(f"{d}: λ {lam:.0f}" + (f" δ {delta:.2f}" if slender else "") + f" Mu {mu:,.0f}/{cap:,.0f}")
        ratio = sum(parts)
        if ratio > worst[0]:
            worst = (ratio, f"Pu {pu:,.0f} · " + " · ".join(text))
    return worst


def design_columns(b, res, mat, col_at, z_base) -> GravityFrameResult:
    """Frame analysis, column strength check (adds bars, then enlarges),
    beam end moments; repeats the analysis when a column grows."""
    out = GravityFrameResult()
    for _round in range(4):
        _frames, beam_hog, stiff = analyse(b, res, col_at, z_base)
        grew = False
        for (i, j, li), c in col_at.items():
            lv = b.levels[li]
            lu = c.height - (lv.beam_depth if li > 0 else 0.0)
            ratio, text = check_column(b, c, mat, lu)
            while ratio > 1.0:
                n, size = parse_bars(c.bars)
                ag = c.b * c.h * 1e4
                for nn, ss in BAR_OPTIONS:
                    if nn * bar_area(ss) > n * bar_area(size) + 1e-9 and nn * bar_area(ss) <= 0.04 * ag \
                            and _bars_fit(nn, ss, min(c.b, c.h) * 100):
                        c.bars, c.pg = f"{nn}-{ss}", nn * bar_area(ss) / ag
                        c.note = _add(c.note, "เพิ่มเหล็กรับแรงอัดร่วมกับโมเมนต์")
                        break
                else:
                    if max(c.b, c.h) >= 0.60:
                        break
                    c.b, c.h = round(c.b + 0.05, 2), round(c.h + 0.05, 2)
                    c.pg = n * bar_area(size) / (c.b * c.h * 1e4)
                    c.note = _add(c.note, "ขยายหน้าตัดรับโมเมนต์")
                    grew = True
                ratio, text = check_column(b, c, mat, lu)
            c.slender = f"{ratio:.2f} · {text}"
            if ratio > 1.0:
                c.ok = False
                c.note = _add(c.note, "ไม่ผ่านแรงอัดร่วมกับโมเมนต์")
            c.refs = _add_ref(c.refs, "EIT1008", "EIT1008-LOADS", "EIT1008-SLENDER", "EIT1008-BIAX", "ACI318-STIFF")
        if not grew:
            break
    out.beams_raised = raise_beam_end_moments(res, mat, beam_hog)
    for li in range(len(b.levels)):
        for d in DIRS:
            k = stiff.get((li, d))
            if not k:
                continue
            pu = sum(1.2 * (c.load - c.live) + 1.6 * c.live for (i, j, l2), c in col_at.items() if l2 == li)
            lc = next(c.height for (i, j, l2), c in col_at.items() if l2 == li)
            q = pu / (k * lc)
            seg = next(c.segment for (i, j, l2), c in col_at.items() if l2 == li)
            out.stability.append(StoreyStability(seg, d, q, q > Q_SWAY, li))
    return out


def check_footing_moments(b, res, mat, col_at):
    """Service-load pile reactions or soil pressure with the column base
    moments (dead + live); more piles or a larger footing when needed."""
    from .design import design_footing
    piles = load_piles()
    for k, f in enumerate(res.footings):
        i, j = b.parse_node(f.node)
        c = col_at[(i, j, 0)]
        mx, my = c.m_dx + c.m_lx, c.m_dy + c.m_ly
        if mx <= 0 and my <= 0:
            continue
        new, P = f, f.load
        for _it in range(8):
            if new.kind == "pile":
                from .seismic import _pile_points
                pts = _pile_points(new.piles, piles[new.pile]["size_m"])
                if len(pts) == 1:
                    break                                   # a single pile: the ground beams take the moment
                sx = sum(p[0] ** 2 for p in pts) or 1.0
                sy = sum(p[1] ** 2 for p in pts) or 1.0
                ax = max(abs(p[0]) for p in pts)
                ay = max(abs(p[1]) for p in pts)
                worst = (f.load + new.weight) / len(pts) + mx * ax / sx + my * ay / sy
                cap = new.pile_capacity
            else:
                A = new.width * new.length
                worst = (f.load + new.weight) / A + 6 * mx / (new.width * new.length ** 2) + \
                    6 * my / (new.length * new.width ** 2)
                cap = new.pile_capacity
            if worst <= cap * (1 + 1e-9) or not new.ok:
                break
            P *= worst / cap * 1.02
            new = design_footing(b, mat, f.node, P, c.b, c.h)
        if new is not f:
            new.load = f.load
            new.note = _add(new.note, "เพิ่มเข็ม/ขยายฐานรับโมเมนต์ที่โคนเสา")
            res.footings[k] = new
