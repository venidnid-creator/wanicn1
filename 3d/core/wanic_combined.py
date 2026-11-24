# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
"""ฐานรากร่วม: two columns on one footing when their single footings would
overlap (ข12, from WanicnDesign).

A rectangle centred on the resultant of the two column loads, so the soil
pressure is uniform; the length keeps each column the projection of its
single footing, the width from the allowable soil pressure [SOIL]. Along
the length it is a beam loaded up by the soil and down by the columns;
across, a band under each column (c + d wide) cantilevers from the column
face [STATICS], [วสท. 1007-34 / ACI 318 §13.3].

Checks (SDM, ksc and cm): one-way shear at d from the column faces
Vu ≤ 0.85·0.53√f'c·b·d, punching at d/2 round each column
Vu ≤ 0.85·1.06√f'c·bo·d; the steel As = Mu / (0.9·fy·0.9d), at least
0.0018·b·t, DB12 at 0.10–0.25 m.
"""
from __future__ import annotations

import math

GAP = 0.10                     # clear distance below which two footings are combined, m
COVER = 0.075                  # to the bar centre, m
BAR_AREA = 1.131               # DB12, cm²
STEP = 0.05


def _up(v, step=STEP):
    return math.ceil(v / step - 1e-9) * step


def overlap(p1, s1, p2, s2) -> bool:
    """Two footings (centre, (w, l)) closer than GAP clear."""
    return abs(p1[0] - p2[0]) < (s1[0] + s2[0]) / 2 + GAP and \
        abs(p1[1] - p2[1]) < (s1[1] + s2[1]) / 2 + GAP


def pairs(sq: dict) -> tuple:
    """``sq`` {(x, y): (w, l)} → ([(a, b)] pairs to combine, [notes]) — a
    footing overlapping two others is left for the engineer (a footing for
    more than two columns is not designed here)."""
    keys = sorted(sq)
    hits = [(a, b) for i, a in enumerate(keys) for b in keys[i + 1:] if overlap(a, sq[a], b, sq[b])]
    count = {}
    for a, b in hits:
        count[a] = count.get(a, 0) + 1
        count[b] = count.get(b, 0) + 1
    out, notes = [], []
    for a, b in hits:
        if count[a] > 1 or count[b] > 1:
            notes.append(f"ฐานราก ({a[0]:.2f}, {a[1]:.2f}) และ ({b[0]:.2f}, {b[1]:.2f}) ซ้อนกัน แต่ฐานรากร่วม"
                         "เกินสองเสายังไม่รองรับ — วิศวกรออกแบบเอง")
            continue
        if abs(a[0] - b[0]) > 1e-6 and abs(a[1] - b[1]) > 1e-6:
            notes.append(f"ฐานราก ({a[0]:.2f}, {a[1]:.2f}) และ ({b[0]:.2f}, {b[1]:.2f}) ซ้อนกันในแนวทแยง — "
                         "วิศวกรออกแบบเอง")
            continue
        out.append((a, b))
    return out, notes


def _moments(L, up, downs):
    pos = neg = 0.0
    for k in range(401):
        x = L * k / 400
        m = sum(P * (x - a) for a, P in up if a < x) - sum(P * (x - a) for a, P in downs if a < x)
        pos, neg = max(pos, m), min(neg, m)
    return pos, -neg


def _shear(x, up, downs):
    return sum(P for a, P in up if a < x) - sum(P for a, P in downs if a < x)


def _bars(Mu, b, t, d_cm, fy) -> tuple:
    """(text, As cm²) — DB12 spacing for Mu kg·m on a width b m."""
    As = Mu * 100 / (0.9 * fy * 0.9 * d_cm) if Mu > 0 else 0.0
    As = max(As, 0.0018 * b * 100 * t * 100)
    s = b * BAR_AREA / As if As else 0.25
    s = max(0.10, min(0.25, math.floor(s / 0.025 + 1e-9) * 0.025))
    return f"DB12@{s:.3f}".rstrip("0").rstrip("."), As


def check(s, xr, L, B_, t, Pu1, Pu2, c1, c2, fc=240.0) -> dict:
    """The shear of a combined footing L long, B_ wide, t thick whose centre
    is ``xr`` from column 1 (the columns ``s`` apart): the worst one-way
    shear V1 against φVc1 at d from the column faces, the worst punching V2
    against φVc2 at d/2 round a column; M+ / M- along the length (kg, kg·m)."""
    rt = math.sqrt(fc)
    d = (t - COVER) * 100                               # cm
    start = xr - L / 2
    qu = (Pu1 + Pu2) / (B_ * L)
    up = [(L * (k + 0.5) / 80, (Pu1 + Pu2) / 80) for k in range(80)]
    downs = [(-start, Pu1), (s - start, Pu2)]
    V1 = max([abs(_shear(x, up, downs)) for c, xc in ((c1, -start), (c2, s - start))
              for x in (xc - c / 2 - d / 100, xc + c / 2 + d / 100) if 0 < x < L] + [0.0])
    V2, Vc2 = 0.0, 1.0
    for Pi, c in ((Pu1, c1), (Pu2, c2)):
        v = Pi - qu * (c + d / 100) ** 2
        cap = 0.85 * 1.06 * rt * 4 * (c * 100 + d) * d
        if v / cap > V2 / Vc2:
            V2, Vc2 = v, cap
    m_pos, m_neg = _moments(L, up, downs)
    return {"V1": V1, "Vc1": 0.85 * 0.53 * rt * B_ * 100 * d, "V2": max(V2, 0.0), "Vc2": Vc2,
            "Mpos": m_pos, "Mneg": m_neg, "d": d}


def design(p1, p2, Pu1, Pu2, D_, c1, c2, qa_t, conc=2400.0, fc=240.0, fy=4000.0,
           s1=(1.0, 1.0), s2=(1.0, 1.0), t0=0.30) -> dict:
    """The combined footing of columns at ``p1``, ``p2`` (m) with factored
    loads Pu1, Pu2 (kg; service = Pu / D_), column sides c1, c2 (m), single
    footings s1, s2 (w, l): {"w", "l", "t", "cx", "cy", "bars", "bars_tr",
    "top", "q", "ok", "notes", "Mpos", "Mneg"} — w along x, l along y."""
    s = math.dist(p1, p2)
    along_x = abs(p2[0] - p1[0]) >= abs(p2[1] - p1[1])
    ux, uy = ((p2[0] - p1[0]) / s, (p2[1] - p1[1]) / s) if s else (1.0, 0.0)
    P1, P2 = Pu1 / D_, Pu2 / D_
    P = P1 + P2 or 1.0
    xr = P2 * s / P                                     # the resultant, from column 1
    e1 = max((s1[0] if along_x else s1[1]) / 2, c1 / 2 + 0.15)
    e2 = max((s2[0] if along_x else s2[1]) / 2, c2 / 2 + 0.15)
    L = _up(2 * max(xr + e1, s - xr + e2))
    t = max(t0, 0.30)
    B_ = max(c1, c2) + 0.30
    for _ in range(8):
        B_ = max(_up((P + B_ * L * t * conc) / (qa_t * 1000.0 * L)), max(c1, c2) + 0.30)
    ok = False
    for _ in range(40):
        ck = check(s, xr, L, B_, t, Pu1, Pu2, c1, c2, fc)
        if ck["V1"] <= ck["Vc1"] and ck["V2"] <= ck["Vc2"]:
            ok = True
            break
        if t >= 1.50:
            break
        t = round(t + 0.05, 2)
    d = (t - COVER) * 100
    start = xr - L / 2
    up = [(L * (k + 0.5) / 80, (Pu1 + Pu2) / 80) for k in range(80)]
    downs = [(-start, Pu1), (s - start, Pu2)]
    m_pos, m_neg = _moments(L, up, downs)
    bars, _as = _bars(max(m_pos, m_neg), B_, t, d, fy)
    m_tr = max(Pi / B_ * ((B_ - c) / 2) ** 2 / 2 for Pi, c in ((Pu1, c1), (Pu2, c2)))
    bars_tr, _ = _bars(m_tr, max(c1, c2) + d / 100, t, d, fy)
    top = _bars(m_neg, B_, t, d, fy)[0] if m_neg > 1.0 else ""
    q = (P + B_ * L * t * conc) / (B_ * L) / 1000.0
    cx, cy = p1[0] + ux * xr, p1[1] + uy * xr
    notes = [f"แรงลัพธ์ห่างเสาแรก {xr:.2f} ม. · ยาว {L:.2f} กว้าง {B_:.2f} หนา {t:.2f} ม. · "
             f"q = {q:.2f} ตัน/ตร.ม. · M+ {m_pos:,.0f} M- {abs(m_neg):,.0f} กก.-ม."]
    if not ok:
        notes.append("ความหนาไม่พอรับแรงเฉือน (ถึง 1.50 ม.) — วิศวกรออกแบบเอง")
    if top:
        notes.append(f"มีเหล็กบน {top} ช่วงระหว่างเสา")
    w, l_ = (L, B_) if along_x else (B_, L)
    return {"w": round(w, 2), "l": round(l_, 2), "t": round(t, 2), "cx": round(cx, 3), "cy": round(cy, 3),
            "bars": bars if along_x else bars_tr, "bars_y": bars_tr if along_x else bars, "top": top,
            "q": q, "ok": ok and q <= qa_t + 1e-6, "notes": notes, "Mpos": m_pos, "Mneg": m_neg,
            "along_x": along_x}
