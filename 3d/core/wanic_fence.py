# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
"""รั้วและประตูรั้ว — the owner (27 พ.ย. 69, studied from the กรมโยธาธิการฯ house set «บ้านครอบครัวไทย
ร่วมสมัย 10» pages A-24…A-26, drawn our own way): a fence round the lot of the site plan with a
sliding gate at the front.

The lot is the one the site plan draws (the building's grid ± the setback, 2 m more in front —
``wanic_drawings.a_site``). Along it:

- RC posts 0.20 × 0.20 m every ``fence_sp`` (≤ 3.00 m) on 0.60 × 0.60 × 0.20 m pad footings 0.80 m
  down, a ground beam 0.15 × 0.30 m post to post;
- «steel»: a low wall 0.50 m (half-brick, plastered both sides) on the beam, then square steel
  pickets 1"×1" LG. @ 0.15 m with their tops cut at 45° between 2"×2" rails 3.2 mm — up to
  ``fence_h`` (2.00 m);
  «block»: a solid wall of concrete blocks plastered both sides to ``fence_h``, a coping on top;
- the sliding gate (``gate_w`` 4.00 m) at the middle of the front: a 2"×2" frame, 1"×1" pickets,
  a 4 mm sheet panel below, three Ø 3" wheels on a rail set in the drive, a latch with a padlock
  plate, a stop post.

Everything here is pure: the 3-D, the BOQ and the drawings read the same lines.
"""
from __future__ import annotations

import math

KINDS = {"none": "ไม่มีรั้ว", "steel": "รั้วเหล็กกล่องบนผนังเตี้ย 0.50 ม. + เสา คสล.",
         "block": "รั้วผนังก่อคอนกรีตบล็อกฉาบเรียบ + เสา คสล."}
POST = 0.20
FOOT = (0.60, 0.20, 0.80)            # side, thickness, depth to its underside (m)
BEAM = (0.15, 0.30)                  # ground beam b × h
LOW_WALL = 0.50
PICKET = 0.025                       # 1" square tube
PICKET_SP = 0.15
RAIL = 0.050                         # 2" square tube


def settings(data) -> dict:
    s = dict((data or {}).get("settings") or {})
    info = dict((data or {}).get("drawing_info") or {})
    return {"kind": s.get("fence", "none") if s.get("fence", "none") in KINDS else "none",
            "h": float(s.get("fence_h") or 2.0), "gate_w": float(s.get("gate_w") or 4.0),
            "sp": min(float(s.get("fence_sp") or 3.0), 3.0),
            "setback": float(info.get("setback") or s.get("setback") or 3.0)}


def lot_of(data, setback=None) -> tuple:
    """The lot the site plan draws: (x0, y0, x1, y1); the front is the y0 side."""
    from core import wanic_building as B
    from core import wanic_drawings as D
    E = B.elements(data)
    bx = D.bbox(E)
    sb = settings(data)["setback"] if setback is None else float(setback)
    return (bx[0] - sb, bx[1] - sb - 2.0, bx[2] + sb, bx[3] + sb), bx


def fence_of(data) -> dict | None:
    """{"kind", "lot", "h", "posts": [(x, y)], "runs": [((x, y), (x, y))], "gate": (xa, xb, y)} —
    None with no fence."""
    st = settings(data)
    if st["kind"] == "none":
        return None
    (x0, y0, x1, y1), bx = lot_of(data, st["setback"])
    gw = min(st["gate_w"], (x1 - x0) - 2.0)
    gc = (bx[0] + bx[2]) / 2
    ga, gb = gc - gw / 2, gc + gw / 2
    # the lot's sides, the front split by the gate
    sides = [((x0, y0), (ga, y0)), ((gb, y0), (x1, y0)), ((x1, y0), (x1, y1)),
             ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))]
    runs, posts = [], []
    for a, b in sides:
        L = math.dist(a, b)
        if L < 0.3:
            continue
        runs.append((a, b))
        n = max(int(math.ceil(L / st["sp"] - 1e-9)), 1)
        for i in range(n + 1):
            p = (round(a[0] + (b[0] - a[0]) * i / n, 4), round(a[1] + (b[1] - a[1]) * i / n, 4))
            if p not in posts:
                posts.append(p)
    return {"kind": st["kind"], "lot": (x0, y0, x1, y1), "h": st["h"], "posts": posts, "runs": runs,
            "gate": (ga, gb, y0), "sp": st["sp"]}


def quantities(fc) -> dict:
    """The amounts the BOQ bills (one source with the 3-D and the drawings)."""
    if not fc:
        return {}
    L = sum(math.dist(a, b) for a, b in fc["runs"])
    n_post = len(fc["posts"])
    h = fc["h"]
    clear = L - n_post * POST
    out = {"length": round(L, 3), "posts": n_post,
           "conc_post": round(n_post * POST * POST * (h + FOOT[2] - FOOT[1]), 3),
           "conc_foot": round(n_post * FOOT[0] * FOOT[0] * FOOT[1], 3),
           "conc_beam": round(clear * BEAM[0] * BEAM[1], 3),
           "form": round(n_post * 4 * POST * (h + FOOT[2] - FOOT[1]) + n_post * 4 * FOOT[0] * FOOT[1]
                         + clear * 2 * BEAM[1], 2),
           "dig": round(n_post * (FOOT[0] + 0.2) ** 2 * FOOT[2] + clear * (BEAM[0] + 0.2) * 0.4, 3),
           "gate": 1}
    if fc["kind"] == "steel":
        out["wall"] = round(clear * LOW_WALL, 3)
        n_pk = int(clear / PICKET_SP)
        hp = h - LOW_WALL - 0.05
        tube1 = 0.025 * 4 * 0.0016 * 7850        # 1"×1" × 1.6 mm ≈ kg/m
        tube2 = 0.050 * 4 * 0.0032 * 7850        # 2"×2" × 3.2 mm ≈ kg/m
        out["steel_kg"] = round(n_pk * hp * tube1 + 2 * clear * tube2, 1)
        out["paint"] = round(clear * hp * 0.6, 2)
    else:
        out["wall"] = round(clear * h, 3)
    gh = h - 0.05
    gw = fc["gate"][1] - fc["gate"][0]
    out["gate_kg"] = round((2 * gw + 3 * gh) * 0.050 * 4 * 0.0032 * 7850
                           + int(gw / PICKET_SP) * (gh - 0.5) * 0.025 * 4 * 0.0016 * 7850
                           + gw * 0.5 * 0.004 * 7850, 1)
    out["gate_w"] = round(gw, 2)
    return out
