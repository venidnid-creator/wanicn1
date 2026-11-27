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


def members(data) -> list:
    """The fence and the gate as 3-D groups (part «structure», kinds «fence» / «gate»), the ground
    at −floor_lift as the building's (``B.build`` lifts them with the rest)."""
    from core import wanic_building as B
    fc = fence_of(data)
    if not fc:
        return []
    lift = B.floor_lift(B.settings_of(data))
    gz = -lift
    conc = {"color": (0.80, 0.79, 0.76)}
    plaster = {"color": (0.93, 0.91, 0.86)}
    steel = {"color": (0.18, 0.19, 0.21)}
    h = fc["h"]
    out = []
    # the posts on their footings
    bx = B._Boxes((0.0, 0.0), (1.0, 0.0), gz)
    for x, y in fc["posts"]:
        bx.box(x - FOOT[0] / 2, x + FOOT[0] / 2, y - FOOT[0] / 2, y + FOOT[0] / 2,
               -FOOT[2], -FOOT[2] + FOOT[1], conc)
        bx.box(x - POST / 2, x + POST / 2, y - POST / 2, y + POST / 2, -FOOT[2] + FOOT[1], h + 0.10, plaster)
        bx.box(x - POST / 2 - 0.02, x + POST / 2 + 0.02, y - POST / 2 - 0.02, y + POST / 2 + 0.02,
               h + 0.10, h + 0.15, plaster)                                   # the cap
    g = bx.group(f"เสารั้ว คสล. 0.20×0.20 ม. · {len(fc['posts'])} ต้น", "structure", "fence", "เสารั้ว",
                 "IfcColumn")
    if g is not None:
        out.append(g)
    # every run: ground beam, then the low wall + pickets, or the solid block wall
    for a, b in fc["runs"]:
        L = math.dist(a, b)
        u = ((b[0] - a[0]) / L, (b[1] - a[1]) / L)
        rb = B._Boxes(a, u, gz)
        rb.box(0.0, L, -BEAM[0] / 2, BEAM[0] / 2, -BEAM[1], 0.0, conc)
        if fc["kind"] == "steel":
            rb.box(0.0, L, -0.06, 0.06, 0.0, LOW_WALL, plaster)
            rb.box(-0.0, L, -0.08, 0.08, LOW_WALL, LOW_WALL + 0.04, plaster)         # its coping
            top = h
            for z_ in (LOW_WALL + 0.20, top - 0.25):                                  # the two rails
                rb.box(0.0, L, -RAIL / 2, RAIL / 2, z_, z_ + RAIL, steel)
            s_ = PICKET_SP / 2
            while s_ < L - 0.05:
                rb.box(s_ - PICKET / 2, s_ + PICKET / 2, -PICKET / 2, PICKET / 2, LOW_WALL + 0.04, top, steel)
                s_ += PICKET_SP
        else:
            rb.box(0.0, L, -0.07, 0.07, 0.0, h, plaster)
            rb.box(0.0, L, -0.10, 0.10, h, h + 0.05, plaster)
        g = rb.group(f"รั้ว{'เหล็ก' if fc['kind'] == 'steel' else 'คอนกรีตบล็อก'} ยาว {L:.2f} ม.", "structure",
                     "fence", "รั้ว", "IfcWall")
        if g is not None:
            out.append(g)
    # the sliding gate, shut, on its rail
    ga, gb, gy = fc["gate"]
    gw = gb - ga
    gt = B._Boxes((ga, gy), (1.0, 0.0), gz)
    sheet = {"color": (0.22, 0.24, 0.27)}
    gt.box(-0.3, gw + 0.3, -0.03, 0.03, -0.02, 0.0, steel)                              # the rail
    for k_ in (0.35, gw / 2, gw - 0.35):                                               # the wheels
        gt.frustum(k_, 0.0, 0.038, 0.012, 0.038, 0.012, 0.0, 0.076, steel)
    gt.box(0.0, gw, -RAIL / 2, RAIL / 2, 0.08, 0.08 + RAIL, steel)                      # bottom rail
    gt.box(0.0, gw, -RAIL / 2, RAIL / 2, h - 0.25, h - 0.25 + RAIL, steel)              # top rail
    gt.box(0.0, gw, -RAIL / 2, RAIL / 2, 0.58, 0.58 + RAIL, steel)                      # mid rail
    for s_ in (0.0, gw - RAIL):
        gt.box(s_, s_ + RAIL, -RAIL / 2, RAIL / 2, 0.08, h - 0.20, steel)               # stiles
    gt.box(RAIL, gw - RAIL, -0.004, 0.004, 0.13, 0.58, sheet)                           # 4 mm sheet
    s_ = PICKET_SP / 2
    while s_ < gw - 0.05:
        gt.box(s_ - PICKET / 2, s_ + PICKET / 2, -PICKET / 2, PICKET / 2, 0.63, h, steel)
        s_ += PICKET_SP
    gt.box(-0.02, 0.06, -0.06, 0.06, 1.00, 1.08, {"color": (0.75, 0.65, 0.35)})       # the latch
    g = gt.group(f"ประตูรั้วบานเลื่อน กว้าง {gw:.2f} ม.", "structure", "gate", "ประตูรั้ว", "IfcDoor")
    if g is not None:
        out.append(g)
    return out
