# -*- coding: utf-8 -*-
"""Combined footings for two columns whose single footings would overlap.

Spread (no piles): a rectangle centred on the resultant of the two column
loads, so the soil pressure is uniform; length so each column keeps the
projection of its single footing; width from the allowable soil pressure
[SOIL]. Along the length it is a beam loaded up by the soil and down by
the columns; across, a band under each column (c + d wide) cantilevers
from the column face [STATICS], [EIT1007-FOOT].

On piles: the pile group is centred on the resultant, in one row (up to
three piles) or two rows, at three pile sizes apart; along the length the
cap is a beam loaded up by the pile reactions and down by the columns
[QD-PILE], [STATICS].

Both check punching shear 0.53√fc' at d/2 round each column and one-way
shear 0.29√fc' at d from the column faces [EIT1007-FOOT].
"""
from __future__ import annotations

import math

from ..standards import cite
from .materials import CONCRETE_KG_M3
from .sections import load_piles

GAP = 0.10                 # clear distance below which two footings are combined, m
MAX_COMBINED_PILES = 10


def _overlap(b, f1, f2) -> bool:
    (x1, y1), (x2, y2) = f1.center(b), f2.center(b)
    return abs(x1 - x2) < (f1.width + f2.width) / 2 + GAP and abs(y1 - y2) < (f1.length + f2.length) / 2 + GAP


def _round_up(v, step):
    return math.ceil(v / step - 1e-9) * step


def _beam_moments(L, up, downs):
    """Largest sagging (+, bottom steel) and hogging (−, top steel) moments
    along a beam 0…L with upward loads ``up`` [(x, P)] and downward
    ``downs`` [(x, P)] (uniform loads given as many small ones)."""
    pos = neg = 0.0
    for k in range(401):
        x = L * k / 400
        m = sum(P * (x - a) for a, P in up if a < x) - sum(P * (x - a) for a, P in downs if a < x)
        pos, neg = max(pos, m), min(neg, m)
    return pos, -neg


def _one_way(V, width, d, mat):
    return V <= mat.vc_beam * width * 100 * d


def _punch_ok(P_net, c_cm, d, mat):
    bo = 4 * (c_cm + d)
    return P_net <= mat.vc_punch * bo * d


def design_combined(b, mat, f1, f2, c1, c2):
    """Combined footing for footings ``f1``, ``f2`` with column results
    ``c1``, ``c2`` (the segments on the footings)."""
    from .design import FootingResult, _footing_bars
    (x1, y1), (x2, y2) = f1.center(b), f2.center(b)
    s = math.hypot(x2 - x1, y2 - y1)
    ux, uy = (x2 - x1) / s, (y2 - y1) / s
    along_x = abs(ux) > abs(uy)
    P1, P2 = f1.load, f2.load
    P = P1 + P2
    xr = P2 * s / P                                     # resultant from column 1
    cc1, cc2 = (c1.b + c1.h) / 2, (c2.b + c2.h) / 2
    e1 = max((f1.width if along_x else f1.length) / 2, cc1 / 2 + 0.15)
    e2 = max((f2.width if along_x else f2.length) / 2, cc2 / 2 + 0.15)
    fnd = b.foundation
    notes = [f"ฐานรากร่วม {f1.node}+{f2.node}"]
    refs = cite("EIT1007-FOOT", mat.ref, "STATICS", "UNIT-WT", "SOIL", "QD-PILE" if fnd.kind == "pile" else "")
    t = max(f1.thickness, f2.thickness)
    ok = True
    if fnd.kind == "spread":
        half = max(xr + e1, s - xr + e2)
        L = _round_up(2 * half, 0.05)
        W = 0.0
        for _ in range(6):
            B = max(_round_up((P + W) / (fnd.soil_qa * L), 0.05), max(cc1, cc2) + 0.30)
            W = CONCRETE_KG_M3 * B * L * t
        q = P / (B * L)                                 # net upward pressure, kg/m²
        start = xr - L / 2                              # footing start, from column 1
        for _ in range(40):
            d = t * 100 - 7.5 - 1.6
            up = [(start + L * (k + 0.5) / 80 - start, q * B * L / 80) for k in range(80)]
            downs = [(-start, P1), (s - start, P2)]
            V_ok = all(_one_way(abs(_shear_at(x, up, downs)), B, d, mat)
                       for c, xc in ((cc1, -start), (cc2, s - start))
                       for x in (xc - c / 2 - d / 100, xc + c / 2 + d / 100) if 0 < x < L)
            P_ok = all(_punch_ok(Pi - q * (c + d / 100) ** 2, c * 100, d, mat) for Pi, c in ((P1, cc1), (P2, cc2)))
            if (V_ok and P_ok) or t >= 1.5:
                break
            t = round(t + 0.05, 2)
        m_pos, m_neg = _beam_moments(L, up, downs)
        bars_long = _footing_bars(mat, max(m_pos, m_neg), B, t, d)
        m_tr = max(Pi / B * ((B - c) / 2) ** 2 / 2 for Pi, c in ((P1, cc1), (P2, cc2)))
        bars_tr = _footing_bars(mat, m_tr, max(cc1, cc2) + d / 100, t, d)
        n_piles, pile, cap = 0, "-", fnd.soil_qa
        if not (V_ok and P_ok):
            ok = False
            notes.append("ความหนาไม่พอรับแรงเฉือน")
        notes.append(f"M+ {m_pos:,.0f} M- {m_neg:,.0f} กก.-ม.; เหล็กขวางใต้เสาในแถบกว้าง c + d")
        if m_neg > 1.0:
            notes.append("ต้องมีเหล็กบนช่วงระหว่างเสา")
        cx = x1 + ux * (xr)
        cy = y1 + uy * (xr)
        width, length = (L, B) if along_x else (B, L)
    else:
        piles = load_piles()
        pile = f1.pile if piles[f1.pile]["capacity_kg"] >= piles[f2.pile]["capacity_kg"] else f2.pile
        size, cap = piles[pile]["size_m"], piles[pile]["capacity_kg"]
        sp = max(3 * size, 0.60)
        e = max(size, 0.25)
        W = 0.0
        for _ in range(6):
            n = max(2, math.ceil((P + W) / cap - 1e-9))
            rows = 1 if n <= 3 else 2
            per_row = math.ceil(n / rows)
            n = rows * per_row
            run = (per_row - 1) * sp
            L = _round_up(max(run + 2 * e, 2 * max(xr, s - xr) + max(cc1, cc2) + 0.30), 0.05)
            B = _round_up(max((rows - 1) * sp + 2 * e, max(cc1, cc2) + 0.30), 0.05)
            W = CONCRETE_KG_M3 * B * L * t
        start = xr - L / 2
        pile_x = [L / 2 - run / 2 + k * sp for k in range(per_row)]          # from the cap start
        R = (P + W) / n
        up = [(px, R * rows) for px in pile_x]
        downs = [(-start, P1), (s - start, P2)] + [(L * (k + 0.5) / 80, W / 80) for k in range(80)]
        for _ in range(40):
            d = t * 100 - 7.5 - 1.6
            V_ok = all(_one_way(abs(_shear_at(x, up, downs)), B, d, mat)
                       for c, xc in ((cc1, -start), (cc2, s - start))
                       for x in (xc - c / 2 - d / 100, xc + c / 2 + d / 100) if 0 < x < L)
            P_ok = all(_punch_ok(Pi, c * 100, d, mat) for Pi, c in ((P1, cc1), (P2, cc2)))
            if (V_ok and P_ok) or t >= 1.5:
                break
            t = round(t + 0.05, 2)
            W = CONCRETE_KG_M3 * B * L * t
        m_pos, m_neg = _beam_moments(L, up, downs)
        bars_long = _footing_bars(mat, max(m_pos, m_neg), B, t, d)
        m_tr = max(R * per_row * max(0.0, sp / 2 - max(cc1, cc2) / 2) if rows == 2 else 0.0, 0.0)
        bars_tr = _footing_bars(mat, m_tr, L, t, d)
        n_piles = n
        if n > MAX_COMBINED_PILES:
            ok = False
            notes.append(f"ใช้เสาเข็ม {n} ต้น เกิน {MAX_COMBINED_PILES}")
        if not (V_ok and P_ok):
            ok = False
            notes.append("ความหนาไม่พอรับแรงเฉือน")
        notes.append(f"เข็ม {rows} แถว แถวละ {per_row} ต้น ระยะ {sp:.2f} ม.; M+ {m_pos:,.0f} M- {m_neg:,.0f} กก.-ม.")
        cx = x1 + ux * xr
        cy = y1 + uy * xr
        width, length = (L, B) if along_x else (B, L)
    fr = FootingResult(f"{f1.node}+{f2.node}", P, "combined", n_piles, pile, cap, round(width, 2),
                       round(length, 2), round(t, 2), bars_long if along_x else bars_tr,
                       bars_tr if along_x else bars_long, CONCRETE_KG_M3 * width * length * t,
                       ok=ok, note=" ; ".join(notes), refs=refs)
    fr.nodes = [f1.node, f2.node]
    fr.cx, fr.cy = cx, cy
    return fr


def _shear_at(x, up, downs):
    return sum(P for a, P in up if a < x) - sum(P for a, P in downs if a < x)


def combine_footings(b, res, mat, col_base) -> list[str]:
    """Replace overlapping pairs of single footings by combined footings.
    ``col_base`` maps a node name to its lowest column segment."""
    notes = []
    done = set()
    fs = list(res.footings)
    pairs = []
    for a in range(len(fs)):
        for c in range(a + 1, len(fs)):
            if _overlap(b, fs[a], fs[c]):
                pairs.append((a, c))
    for a, c in pairs:
        if a in done or c in done:
            notes.append(f"ฐานราก {fs[a].node} และ {fs[c].node} ซ้อนกัน แต่ฐานรากร่วมเกินสองต้นยังไม่รองรับ")
            continue
        done |= {a, c}
        new = design_combined(b, mat, fs[a], fs[c], col_base[fs[a].node], col_base[fs[c].node])
        res.footings[res.footings.index(fs[a])] = new
        res.footings.remove(fs[c])
    return notes
