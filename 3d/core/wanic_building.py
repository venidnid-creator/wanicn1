# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
# WANICNSURVEY 3D — "WANIC ออกแบบอาคาร": room plan → structure → roof.
"""From a plan of rectangular rooms (per floor) to a 3D reinforced-concrete
frame and a steel roof frame, ready for the takeoff.

Layout rules (simple, predictable, all editable afterwards):

- a column stands at every room corner of a floor (shared corners count
  once); a footing (F) and a stump (PC) carry each ground-floor column;
- beams run along every room edge, split at the columns on that edge:
  ground beams (GB) at ±0.00, floor beams (B) at upper levels, roof beams
  (RB) at the top;
- one slab per room (S1 on the ground, S2 above), walls optional, split
  around doors and windows; straight concrete stairs between floors;
- floors without rooms are skipped: the floors that have rooms stack up
  from the ground in order (a plan drawn on «ชั้น 3» alone is a one-storey
  building, never a roof floating over nothing);
- the roof follows the top floor's plan: the plan is covered by the fewest
  rectangles (overlapping where an L / T wing runs into the main block, so
  the slopes meet in valleys), each with a gable (จั่ว) or hip (ปั้นหยา)
  frame — ridge, hips, rafters, purlins, king posts — and a roof skin
  whose area the takeoff bills.

Member sizes are starting values only — nothing here designs or checks
structural strength; a civil engineer sets the real sizes.

Every generated group carries ``ext["wanic_building"] = {"part", "kind",
"mark"}`` so a rebuild replaces exactly what an earlier build made, and the
section record of :mod:`core.wanic_profiles` (resizable, true length).
"""
from __future__ import annotations

import math

from core import wanic_profiles as P

EXT_KEY = "wanic_building"
TAKEOFF_KEY = "wanic_takeoff"

ROOM_PRESETS = [
    ("ห้องนอน", 3.0, 3.0), ("ห้องนอนใหญ่", 4.0, 4.0),
    ("ห้องนั่งเล่น", 4.0, 4.0), ("ห้องครัว", 3.0, 3.0),
    ("ห้องน้ำ", 1.5, 2.0), ("ห้องเก็บของ", 2.0, 2.0),
    ("ระเบียง", 3.0, 1.5), ("ที่จอดรถ", 3.0, 5.5),
]

DEFAULT_SETTINGS = {
    "floor_h": 3.0, "grid": 0.5,
    "footing_w": 1.0, "footing_t": 0.3, "footing_depth": 1.5,
    "stump": 0.2, "col": 0.2,
    "gb_b": 0.2, "gb_h": 0.4, "b_b": 0.2, "b_h": 0.4,
    "rb_b": 0.2, "rb_h": 0.4, "slab_t": 0.10,
    "walls": True, "wall_t": 0.10,
    "roof": "hip", "pitch": 30.0, "overhang": 0.6,
    "rafter_sp": 1.0, "purlin_sp": 0.8,
    "ridge": "C 150×65×20×3.2", "hip": "C 150×65×20×3.2",
    "rafter": "C 150×65×20×3.2", "purlin": "C 75×45×15×2.3",
    "post": "C 100×50×20×2.3", "skin": True, "roof_mode": "plan",
    "door_w": 0.9, "door_h": 2.0, "win_w": 1.2, "win_h": 1.1,
    "win_sill": 0.9, "stair_w": 1.0, "riser_max": 0.18, "going": 0.25,
    "stair_t": 0.15, "fascia": True, "fascia_h": 0.20, "fascia_t": 0.025,
    "band": 0.10, "tile": "R1", "tiles_m2": 0.0, "caps": True,
    "tile_color": "ตามวัสดุ", "tiles_3d": True,
}


#: Room types and standard sizes, chosen separately (as in the plan tools
#: designers know): a type names the room, a size sets w × d.
ROOM_TYPES = ["ห้องนอน", "ห้องนอนใหญ่", "ห้องนั่งเล่น", "ห้องรับแขก",
              "ห้องครัว", "ห้องรับประทานอาหาร", "ห้องน้ำ", "ห้องทำงาน",
              "ห้องเก็บของ", "ห้องซักล้าง", "ห้องพระ", "โถงทางเดิน",
              "บันได", "ระเบียง", "ชานพัก", "ที่จอดรถ"]
ROOM_SIZES = [(3.0, 3.0), (3.0, 2.0), (2.0, 3.0), (4.0, 4.0), (4.0, 3.0),
              (3.0, 4.0), (4.0, 2.0), (3.5, 3.5), (3.5, 3.0), (3.5, 2.0),
              (4.5, 4.0), (5.0, 4.0), (1.5, 2.0), (1.5, 1.5), (1.5, 3.0),
              (2.0, 2.0), (2.5, 2.0), (3.0, 1.5), (3.0, 5.5), (6.0, 3.0)]

# ---------------------------------------------------------------------------
# Member library (เบอร์ชิ้นส่วน): sizes in metres, bars as "4-DB12" /
# "RB6@0.15". Every footing / stump / column / beam / slab carries a mark;
# a mark can be set per column point or per beam span.
# ---------------------------------------------------------------------------

LIB_KINDS = {"footing": "ฐานราก", "stump": "เสาตอม่อ", "column": "เสา",
             "beam": "คาน", "slab": "พื้น"}
LIB_FIELDS = {
    "footing": [("w", "กว้าง (ม.)"), ("l", "ยาว (ม.)"), ("t", "หนา (ม.)"),
                ("depth", "ลึกถึงใต้ฐาน (ม.)"), ("bars", "เหล็กตะแกรง"),
                ("sand", "ทรายรอง (ม.)"), ("lean", "คอนกรีตหยาบ (ม.)"),
                ("piles", "เสาเข็ม/ฐาน (ต้น)"), ("pile_b", "เข็มกว้าง (ม.)"),
                ("pile_len", "เข็มยาว (ม.)")],
    "stump": [("b", "กว้าง (ม.)"), ("h", "ลึก (ม.)"), ("main", "เหล็กยืน"),
              ("tie", "เหล็กปลอก")],
    "column": [("b", "กว้าง (ม.)"), ("h", "ลึก (ม.)"), ("main", "เหล็กยืน"),
               ("tie", "เหล็กปลอก")],
    "beam": [("b", "กว้าง (ม.)"), ("h", "ลึก (ม.)"), ("top", "เหล็กบน"),
             ("bot", "เหล็กล่าง"), ("stir", "เหล็กปลอก")],
    "slab": [("t", "หนา (ม.)"), ("bars", "เหล็กเสริม 2 ทาง"),
             ("ground", "พื้นวางบนดิน (1/0)")],
}
DEFAULT_LIB = {
    "F1": {"kind": "footing", "w": 1.0, "l": 1.0, "t": 0.3, "depth": 1.5,
           "bars": "DB12@0.15", "sand": 0.05, "lean": 0.05, "piles": 0,
           "pile_b": 0.18, "pile_len": 6.0},
    "PC1": {"kind": "stump", "b": 0.2, "h": 0.2, "main": "4-DB12",
            "tie": "RB6@0.15"},
    "C1": {"kind": "column", "b": 0.2, "h": 0.2, "main": "4-DB12",
           "tie": "RB6@0.15"},
    "GB1": {"kind": "beam", "b": 0.2, "h": 0.4, "top": "2-DB12",
            "bot": "2-DB12", "stir": "RB6@0.15"},
    "B1": {"kind": "beam", "b": 0.2, "h": 0.4, "top": "2-DB12",
           "bot": "2-DB12", "stir": "RB6@0.15"},
    "RB1": {"kind": "beam", "b": 0.2, "h": 0.4, "top": "2-DB12",
            "bot": "2-DB12", "stir": "RB6@0.15"},
    "S1": {"kind": "slab", "t": 0.10, "bars": "RB9@0.20", "ground": 1},
    "S2": {"kind": "slab", "t": 0.10, "bars": "RB9@0.20", "ground": 0},
}
#: Default mark per role (F, PC, C at a column point; beams per level).
ROLE_DEFAULT = {"F": "F1", "PC": "PC1", "C": "C1", "GB": "GB1", "B": "B1",
                "RB": "RB1", "S1": "S1", "S2": "S2"}
ROLE_KIND = {"F": "footing", "PC": "stump", "C": "column"}


def new_floor() -> dict:
    return {"rooms": [], "openings": [], "stairs": [], "fixtures": []}


def default_data() -> dict:
    return {"floors": [new_floor()], "settings": dict(DEFAULT_SETTINGS)}


def stacked(data):
    """``(floors, skipped)``: the floors that have rooms, bottom up, each
    ``{"rooms", "openings", "stairs", "src"}`` (``src`` = its index in the
    plan), and how many empty floors were left out."""
    out, skipped = [], 0
    for i, f in enumerate((data or {}).get("floors") or []):
        if f.get("rooms"):
            out.append({"rooms": f.get("rooms") or [],
                        "openings": f.get("openings") or [],
                        "stairs": f.get("stairs") or [],
                        "fixtures": f.get("fixtures") or [], "src": i})
        else:
            skipped += 1
    # Empty floors above the last used one are not "skipped" — just unused.
    last = max((f["src"] for f in out), default=-1)
    total = len((data or {}).get("floors") or [])
    skipped -= max(0, total - 1 - last)
    return out, max(skipped, 0)


def settings_of(data) -> dict:
    s = dict(DEFAULT_SETTINGS)
    s.update((data or {}).get("settings") or {})
    return s


def library_of(data) -> dict:
    """mark → member spec: the defaults, sized from the older settings,
    then the user's own library entries on top."""
    import copy
    s = settings_of(data)
    lib = copy.deepcopy(DEFAULT_LIB)
    lib["F1"].update(w=float(s["footing_w"]), l=float(s["footing_w"]),
                     t=float(s["footing_t"]), depth=float(s["footing_depth"]))
    lib["PC1"].update(b=float(s["stump"]), h=float(s["stump"]))
    lib["C1"].update(b=float(s["col"]), h=float(s["col"]))
    for mark, pre in (("GB1", "gb"), ("B1", "b"), ("RB1", "rb")):
        lib[mark].update(b=float(s[f"{pre}_b"]), h=float(s[f"{pre}_h"]))
    lib["S1"]["t"] = lib["S2"]["t"] = float(s["slab_t"])
    for mark, spec in ((data or {}).get("library") or {}).items():
        if not isinstance(spec, dict):
            continue
        base = dict(lib.get(mark) or {})
        base.update(spec)
        if base.get("kind") in LIB_KINDS:
            lib[str(mark)] = base
    return lib


def marks_of(lib, kind) -> list[str]:
    def key(m):
        digits = "".join(ch for ch in m if ch.isdigit())
        return (m.rstrip("0123456789"), int(digits) if digits else 0, m)
    return sorted((m for m, v in lib.items() if v.get("kind") == kind),
                  key=key)


def node_key(x, y) -> str:
    return f"N:{_r(x):.3f},{_r(y):.3f}"


def span_key(level, p0, p1) -> str:
    a, b = sorted(((_r(p0[0]), _r(p0[1])), (_r(p1[0]), _r(p1[1]))))
    return f"S:{int(level)}:{a[0]:.3f},{a[1]:.3f},{b[0]:.3f},{b[1]:.3f}"


def node_mark(data, lib, x, y, role) -> str:
    """The F / PC / C mark at a column point."""
    rec = ((data or {}).get("assign") or {}).get(node_key(x, y)) or {}
    mark = rec.get(role)
    if mark in lib and lib[mark].get("kind") == ROLE_KIND[role]:
        return mark
    return ROLE_DEFAULT[role]


def beam_mark(data, lib, level, n, p0, p1) -> str:
    rec = ((data or {}).get("assign") or {}).get(span_key(level, p0, p1))
    if rec in lib and lib[rec].get("kind") == "beam":
        return rec
    return ROLE_DEFAULT["GB" if level == 0 else "RB" if level == n else "B"]


def slab_mark(lib, room, floor) -> str:
    m = room.get("slab")
    if m in lib and lib[m].get("kind") == "slab":
        return m
    return ROLE_DEFAULT["S1" if floor == 0 else "S2"]


def _on_edge(room, px, py, tol=1e-6) -> bool:
    x0, y0 = float(room["x"]), float(room["y"])
    x1, y1 = x0 + float(room["w"]), y0 + float(room["d"])
    inside_x = x0 - tol <= px <= x1 + tol
    inside_y = y0 - tol <= py <= y1 + tol
    return ((abs(px - x0) < tol or abs(px - x1) < tol) and inside_y) or \
           ((abs(py - y0) < tol or abs(py - y1) < tol) and inside_x)


def elements(data) -> dict:
    """Every structural and architectural element of the plan, with its
    mark and position — the one inventory both the 3D build and the
    standard quantities (:mod:`core.wanic_quantities`) read."""
    s = settings_of(data)
    lib = library_of(data)
    floors, _skipped = stacked(data)
    n = len(floors)
    H = float(s["floor_h"])
    E = {"footings": [], "stumps": [], "columns": [], "beams": [],
         "slabs": [], "walls": [], "openings": [], "stairs": [],
         "fixtures": [], "n": n,
         "H": H, "lib": lib, "settings": s, "floors": floors}
    if not floors:
        return E
    rooms_of = [f["rooms"] for f in floors]
    ground = set()
    for rooms in rooms_of:
        ground |= set(nodes(rooms))
    for (x, y) in sorted(ground):
        fm = node_mark(data, lib, x, y, "F")
        f = lib[fm]
        base = -float(f["depth"])
        top = base + float(f["t"])
        E["footings"].append({"mark": fm, "x": x, "y": y, "z0": base,
                              "z1": top})
        E["stumps"].append({"mark": node_mark(data, lib, x, y, "PC"),
                            "x": x, "y": y, "z0": top, "z1": 0.0})
    for k in range(n):
        pts = set()
        for j in range(k, n):
            pts |= set(nodes(rooms_of[j]))
        for (x, y) in sorted(pts):
            E["columns"].append({"mark": node_mark(data, lib, x, y, "C"),
                                 "x": x, "y": y, "z0": k * H,
                                 "z1": (k + 1) * H, "floor": k})
    beam_at = {}
    for lvl in range(n + 1):
        rooms = []
        if lvl < n:
            rooms += rooms_of[lvl]
        if lvl > 0:
            rooms += rooms_of[lvl - 1]
        for p0, p1 in segments(rooms):
            mark = beam_mark(data, lib, lvl, n, p0, p1)
            E["beams"].append({"mark": mark, "level": lvl, "p0": p0,
                               "p1": p1, "z": lvl * H, "ground": lvl == 0,
                               "roof": lvl == n})
            beam_at[(lvl, p0, p1)] = mark
    for k, rooms in enumerate(rooms_of):
        for rm in rooms:
            E["slabs"].append({"mark": slab_mark(lib, rm, k), "room": rm,
                               "floor": k, "z": k * H})
    for k, f in enumerate(floors):
        for p0, p1 in segments(f["rooms"]):
            mx, my = (p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2
            sides = sum(1 for rm in f["rooms"] if _on_edge(rm, mx, my))
            above = beam_at.get((k + 1, p0, p1)) or ROLE_DEFAULT[
                "RB" if k == n - 1 else "B"]
            E["walls"].append({
                "floor": k, "p0": p0, "p1": p1,
                "L": math.hypot(p1[0] - p0[0], p1[1] - p0[1]),
                "exterior": sides <= 1, "beam": above,
                "openings": [op for _s, op in
                             _openings_on(p0, p1, f["openings"])]})
        for op in f["openings"]:
            w, h, sill = opening_size(op, s)
            E["openings"].append({"floor": k, "op": op, "w": w, "h": h,
                                  "sill": sill, "type": op.get("type", "door"),
                                  "name": opening_name(op, s)})
        for stp in f["stairs"]:
            E["stairs"].append({"floor": k, "st": stp})
        for fx in f.get("fixtures") or []:
            E["fixtures"].append({"floor": k, "fx": fx})
    return E


def pile_points(f, x, y):
    """Pile centres under a footing (1–4 piles, else none)."""
    n = int(f.get("piles") or 0)
    if n <= 0:
        return []
    dx, dy = float(f["w"]) / 4, float(f["l"]) / 4
    if n == 1:
        return [(x, y)]
    if n == 2:
        return [(x - dx, y), (x + dx, y)]
    if n == 3:
        return [(x - dx, y - dy), (x + dx, y - dy), (x, y + dy)]
    return [(x - dx, y - dy), (x + dx, y - dy), (x + dx, y + dy),
            (x - dx, y + dy)][:4]


def steel_presets() -> list[tuple[str, str, dict]]:
    """Every steel preset as (label, family, params)."""
    out = []
    for key in ("lc", "c", "box", "h", "i", "l", "pipe"):
        for label, p in P.FAMILIES[key]["presets"]:
            out.append((label, key, dict(p)))
    return out


def steel_lookup(label: str):
    for lab, fam, p in steel_presets():
        if lab == label:
            return fam, p
    return "lc", dict(P.FAMILIES["lc"]["presets"][0][1])


# ---------------------------------------------------------------------------
# Plan geometry
# ---------------------------------------------------------------------------

def _r(v: float) -> float:
    return round(float(v), 3)


def room_corners(room):
    x, y, w, d = (float(room[k]) for k in ("x", "y", "w", "d"))
    return [(x, y), (x + w, y), (x + w, y + d), (x, y + d)]


def nodes(rooms) -> list[tuple[float, float]]:
    """Column points: every room corner, once."""
    seen = {}
    for rm in rooms:
        for p in room_corners(rm):
            seen[(_r(p[0]), _r(p[1]))] = True
    return sorted(seen)


def segments(rooms, extra_nodes=()) -> list[tuple[tuple, tuple]]:
    """Beam spans: room edges split at every column standing on them, each
    span once."""
    pts = set(nodes(rooms)) | {(_r(a), _r(b)) for a, b in extra_nodes}
    out = set()
    for rm in rooms:
        c = [(_r(a), _r(b)) for a, b in room_corners(rm)]
        for i in range(4):
            a, b = c[i], c[(i + 1) % 4]
            if a == b:
                continue
            dx, dy = b[0] - a[0], b[1] - a[1]
            length = math.hypot(dx, dy)
            on = []
            for p in pts:
                # Collinear with the edge and within it.
                cross = (p[0] - a[0]) * dy - (p[1] - a[1]) * dx
                if abs(cross) > 1e-6 * length:
                    continue
                t = ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / (length ** 2)
                if -1e-9 <= t <= 1 + 1e-9:
                    on.append((t, p))
            on.sort()
            for (_t0, p0), (_t1, p1) in zip(on, on[1:]):
                if p0 != p1:
                    out.add(tuple(sorted((p0, p1))))
    return sorted(out)


def footprint(rooms):
    xs = [p[0] for rm in rooms for p in room_corners(rm)]
    ys = [p[1] for rm in rooms for p in room_corners(rm)]
    if not xs:
        return None
    return min(xs), min(ys), max(xs), max(ys)


def snap_room(room, others, grid=0.5, reach=0.3):
    """Snap a dragged room: its edges to the other rooms' edges within
    ``reach`` (metres), else its corner to the grid."""
    x, y, w, d = (float(room[k]) for k in ("x", "y", "w", "d"))

    def best(v, size, lines):
        cand = []
        for ln in lines:
            for off in (0.0, size):
                if abs(v + off - ln) <= reach:
                    cand.append((abs(v + off - ln), ln - off))
        if cand:
            return min(cand)[1]
        return round(v / grid) * grid if grid > 0 else v
    xs = [p[0] for o in others for p in room_corners(o)]
    ys = [p[1] for o in others for p in room_corners(o)]
    out = dict(room)
    out["x"], out["y"] = _r(best(x, w, xs)), _r(best(y, d, ys))
    return out


# ---------------------------------------------------------------------------
# Doors, windows, stairs (plan helpers)
# ---------------------------------------------------------------------------

def snap_to_segment(x, y, segs, reach=0.4):
    """The nearest point on a beam span within ``reach`` metres:
    ``(px, py, (p0, p1))`` or ``None``."""
    best = None
    for p0, p1 in segs:
        dx, dy = p1[0] - p0[0], p1[1] - p0[1]
        L2 = dx * dx + dy * dy
        if L2 < 1e-12:
            continue
        t = max(0.0, min(1.0, ((x - p0[0]) * dx + (y - p0[1]) * dy) / L2))
        px, py = p0[0] + t * dx, p0[1] + t * dy
        dist = math.hypot(x - px, y - py)
        if dist <= reach and (best is None or dist < best[0]):
            best = (dist, (_r(px), _r(py), (p0, p1)))
    return None if best is None else best[1]


def _openings_on(p0, p1, openings, tol=0.06):
    """Openings standing on span p0→p1: [(s, opening)] with ``s`` the
    distance of its centre from p0."""
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    L = math.hypot(dx, dy)
    out = []
    if L < 1e-9:
        return out
    ux, uy = dx / L, dy / L
    for op in openings:
        ox, oy = float(op["x"]) - p0[0], float(op["y"]) - p0[1]
        s = ox * ux + oy * uy
        if abs(ox * uy - oy * ux) <= tol and -1e-6 <= s <= L + 1e-6:
            out.append((s, op))
    out.sort(key=lambda t: t[0])
    return out


def opening_size(op, s):
    """(width, height, sill) of an opening: its own, else its type's
    (:mod:`core.wanic_catalog`) when it has one, else the settings'."""
    from core.wanic_catalog import opening_type
    _code, spec = opening_type(op)
    styled = bool(op.get("style"))
    if op.get("type") == "window":
        dw, dh = (spec["w"], spec["h"]) if styled else (s["win_w"], s["win_h"])
        dsill = spec.get("sill", s["win_sill"]) if styled else s["win_sill"]
        return (float(op.get("w") or dw), float(op.get("h") or dh),
                float(op.get("sill") if op.get("sill") is not None
                      else dsill))
    dw, dh = (spec["w"], spec["h"]) if styled else (s["door_w"], s["door_h"])
    return (float(op.get("w") or dw), float(op.get("h") or dh), 0.0)


def opening_name(op, s):
    from core.wanic_catalog import opening_type
    w, h, _sill = opening_size(op, s)
    code, spec = opening_type(op)
    return f"{code} {spec['name']} {w:.2f}×{h:.2f} ม."


_DIRS = [(1.0, 0.0), (0.0, 1.0), (-1.0, 0.0), (0.0, -1.0)]


def stair_geometry(st, s):
    """(risers, run length, rise) of a flight for the floor height."""
    H = float(s["floor_h"])
    n = max(2, math.ceil(H / max(float(s["riser_max"]), 0.05) - 1e-9))
    return n, n * float(s["going"]), H


def stair_rect(st, s):
    """The flight's plan rectangle as 4 corners (for drawing and picking)."""
    n, L, _H = stair_geometry(st, s)
    rx, ry = _DIRS[int(st.get("dir", 1)) % 4]
    tx, ty = ry, -rx
    w = float(st.get("w") or s["stair_w"])
    cx, cy = float(st["x"]), float(st["y"])
    a = (cx - rx * L / 2, cy - ry * L / 2)
    pts = []
    for su, sw in ((0, -1), (1, -1), (1, 1), (0, 1)):
        pts.append((a[0] + rx * L * su + tx * w / 2 * sw,
                    a[1] + ry * L * su + ty * w / 2 * sw))
    return pts


# ---------------------------------------------------------------------------
# Members
# ---------------------------------------------------------------------------

def _tag(g, part, kind, mark):
    ext = dict(g.ext or {})
    ext[EXT_KEY] = {"part": part, "kind": kind, "mark": mark}
    g.ext = ext
    return g


def _member(part, kind, mark, family, params, path, anchor="c", ifc="",
            name=None, closed=False, offset=(0.0, 0.0)):
    g = P.build_member({"family": family, "params": params, "path": path,
                        "anchor": anchor, "ifc": ifc, "name": name or mark,
                        "closed": closed, "offset": offset})
    if isinstance(g, str):
        return None
    return _tag(g, part, kind, mark)


def _mm(v):
    return float(v) * 1000.0


def structure_members(data) -> tuple[list, dict]:
    """The concrete frame, piles, walls, doors, windows and stairs as
    groups, and a count per kind — sized from the member library."""
    E = elements(data)
    s, lib = E["settings"], E["lib"]
    out, count = [], {}

    def add(g, kind):
        if g is not None:
            out.append(g)
            count[kind] = count.get(kind, 0) + 1

    if not E["n"]:
        return out, count
    for e in E["footings"]:
        f = lib[e["mark"]]
        add(_member("structure", "footing", e["mark"], "rect",
                    dict(b=_mm(f["w"]), h=_mm(f["l"])),
                    [(e["x"], e["y"], e["z0"]), (e["x"], e["y"], e["z1"])],
                    ifc="IfcFooting"), "footing")
        for px, py in pile_points(f, e["x"], e["y"]):
            pb = _mm(f.get("pile_b") or 0.18)
            add(_member("structure", "pile", "เสาเข็ม", "rect",
                        dict(b=pb, h=pb),
                        [(px, py, e["z0"] - float(f.get("pile_len") or 6.0)),
                         (px, py, e["z0"])], ifc="IfcPile",
                        name=f"เสาเข็ม {e['mark']}"), "pile")
    for e in E["stumps"]:
        c = lib[e["mark"]]
        add(_member("structure", "stump", e["mark"], "rect",
                    dict(b=_mm(c["b"]), h=_mm(c["h"])),
                    [(e["x"], e["y"], e["z0"]), (e["x"], e["y"], e["z1"])],
                    ifc="IfcColumn"), "stump")
    for e in E["columns"]:
        c = lib[e["mark"]]
        add(_member("structure", "column", e["mark"], "rect",
                    dict(b=_mm(c["b"]), h=_mm(c["h"])),
                    [(e["x"], e["y"], e["z0"]), (e["x"], e["y"], e["z1"])],
                    ifc="IfcColumn"), "column")
    for e in E["beams"]:
        b = lib[e["mark"]]
        p0, p1, z = e["p0"], e["p1"], e["z"]
        add(_member("structure", "beam", e["mark"], "rect",
                    dict(b=_mm(b["b"]), h=_mm(b["h"])),
                    [(p0[0], p0[1], z), (p1[0], p1[1], z)], anchor="tc",
                    ifc="IfcBeam"), "beam")
    for e in E["slabs"]:
        rm, t = e["room"], float(lib[e["mark"]]["t"])
        cx = float(rm["x"]) + float(rm["w"]) / 2
        cy = float(rm["y"]) + float(rm["d"]) / 2
        add(_member("structure", "slab", e["mark"], "rect",
                    dict(b=_mm(rm["w"]), h=_mm(rm["d"])),
                    [(cx, cy, e["z"] - t), (cx, cy, e["z"])], ifc="IfcSlab"),
            "slab")
    if s.get("walls"):
        _walls(E, add)
    for e in E["stairs"]:
        add(stair_member(e["st"], s, e["floor"] * E["H"]), "stair")
    for e in E["fixtures"]:
        add(fixture_member(e["fx"], e["floor"] * E["H"]), "fixture")
    return out, count


def fixture_member(fx, z):
    """A sanitary fitting as a simple block (size from the catalog)."""
    from core.wanic_catalog import SANITARY
    spec = SANITARY.get(fx.get("type"))
    if spec is None:
        return None
    name, _item, _rate, w, d, z0, height = spec
    if int(fx.get("dir", 0)) % 2:
        w, d = d, w
    x, y = float(fx["x"]), float(fx["y"])
    return _member("structure", "fixture", fx["type"], "rect",
                   dict(b=_mm(w), h=_mm(d)),
                   [(x, y, z + z0), (x, y, z + z0 + max(height, 0.01))],
                   ifc="IfcSanitaryTerminal", name=name)


def _walls(E, add):
    s, lib, H = E["settings"], E["lib"], E["H"]
    wt = _mm(s["wall_t"])
    half = float(lib["C1"]["b"]) / 2
    for wl in E["walls"]:
        z0 = wl["floor"] * H
        wh = H - float(lib[wl["beam"]]["h"])
        if wh <= 0.05:
            continue
        p0, p1, L = wl["p0"], wl["p1"], wl["L"]
        if L <= 2 * half + 0.05:
            continue
        ux, uy = (p1[0] - p0[0]) / L, (p1[1] - p0[1]) / L

        def at(dist, z):
            return (p0[0] + ux * dist, p0[1] + uy * dist, z)

        def piece(a, b, z, height):
            if b - a > 0.02 and height > 0.02:
                add(_member("structure", "wall", "ผนังก่ออิฐ", "rect",
                            dict(b=wt, h=_mm(height)),
                            [at(a, z), at(b, z)], anchor="bc",
                            ifc="IfcWall"), "wall")
        band = float(s.get("band", 0.10))
        wtm = float(s["wall_t"])
        cur = half
        for sdist, op in _openings_on(p0, p1, wl["openings"]):
            ow, oh, sill = opening_size(op, s)
            door = op.get("type") != "window"
            a = max(half + band, sdist - ow / 2)
            b = min(L - half - band, sdist + ow / 2)
            if b - a < 0.1:
                continue
            top = min(sill + oh, wh)
            lo = 0.0 if door else max(sill - band, 0.0)
            piece(cur, a - band, z0, wh)
            piece(a - band, b + band, z0, lo)           # under a window
            hi = min(top + band, wh)
            piece(a - band, b + band, z0 + hi, wh - hi)  # over the opening
            if band > 0:
                add(opening_band(p0, (ux, uy), z0, a, b, sill if not door
                                 else 0.0, top, wtm, band, wh, door), "band")
            kind = "door" if door else "window"
            add(opening_set(op, s, p0, (ux, uy), z0, a, b, sill, top, wtm),
                kind)
            cur = max(cur, b + band)
        piece(cur, L - half, z0, wh)


# ---------------------------------------------------------------------------
# Doors and windows as real sets, and the concrete band round them
# ---------------------------------------------------------------------------

class _Boxes:
    """Oriented boxes in one mesh, in wall coordinates: ``s`` along the
    wall from ``p0``, ``d`` across it (0 = wall centre), ``z`` up."""

    def __init__(self, p0, u, z0=0.0):
        from core.mesh import Mesh
        self.mesh = Mesh()
        self.p0, self.u, self.z0 = p0, u, z0
        self.n = (-u[1], u[0])

    def P(self, s, d, z):
        from PySide6.QtGui import QVector3D
        return QVector3D(self.p0[0] + self.u[0] * s + self.n[0] * d,
                         self.p0[1] + self.u[1] * s + self.n[1] * d,
                         self.z0 + z)

    def box(self, s0, s1, d0, d1, z0, z1, attrs=None):
        if s1 - s0 < 1e-4 or d1 - d0 < 1e-4 or z1 - z0 < 1e-4:
            return
        from PySide6.QtGui import QVector3D
        c = self.P((s0 + s1) / 2, (d0 + d1) / 2, (z0 + z1) / 2)
        quads = [
            [(s0, d0, z0), (s1, d0, z0), (s1, d1, z0), (s0, d1, z0)],
            [(s0, d0, z1), (s1, d0, z1), (s1, d1, z1), (s0, d1, z1)],
            [(s0, d0, z0), (s1, d0, z0), (s1, d0, z1), (s0, d0, z1)],
            [(s0, d1, z0), (s1, d1, z0), (s1, d1, z1), (s0, d1, z1)],
            [(s0, d0, z0), (s0, d1, z0), (s0, d1, z1), (s0, d0, z1)],
            [(s1, d0, z0), (s1, d1, z0), (s1, d1, z1), (s1, d0, z1)],
        ]
        for q in quads:
            pts = [self.P(*v) for v in q]
            nrm = QVector3D.crossProduct(pts[1] - pts[0], pts[2] - pts[0])
            mid = (pts[0] + pts[2]) * 0.5
            if QVector3D.dotProduct(nrm, mid - c) < 0:
                pts = pts[::-1]
            f = self.mesh.add_face(pts)
            if attrs and f is not None:
                f.attrs.update(attrs)

    def group(self, name, part, kind, mark, ifc):
        from core.group import Group
        if not self.mesh.faces:
            return None
        g = Group(self.mesh, name=name)
        g.ifc = {"class": ifc, "name": name}
        return _tag(g, part, kind, mark)


def _paint(key, opacity=None):
    from core.wanic_catalog import COLORS
    a = {"color": COLORS[key]}
    if opacity is not None:
        a["opacity"] = opacity
    return a


def opening_set(op, s, p0, u, z, a, b, sill, top, wt):
    """One door or window as a set: frame (วงกบ), leaves (บาน), glass and a
    handle, painted — a single group (one IfcDoor / IfcWindow)."""
    from core.wanic_catalog import opening_type
    code, spec = opening_type(op)
    bx = _Boxes(p0, u, z)
    alu = spec["frame"] == "alu"
    fw = 0.04 if alu else 0.05                  # frame face
    fd = min(0.10, wt) / 2                      # frame depth (half)
    gap = 0.002
    frame = _paint("alu" if alu else "wood_dark")
    door = spec["kind"] == "door"
    bottom = 0.0 if door else sill
    # Frame: two jambs and a head; a sill on a window.
    bx.box(a, a + fw, -fd, fd, bottom, top, frame)
    bx.box(b - fw, b, -fd, fd, bottom, top, frame)
    bx.box(a + fw + gap, b - fw - gap, -fd, fd, top - fw, top, frame)
    if not door:
        bx.box(a + fw + gap, b - fw - gap, -fd, fd, sill, sill + fw, frame)
    i0, i1 = a + fw + gap, b - fw - gap
    j0, j1 = (bottom + 0.01 if door else sill + fw + gap), top - fw - gap
    n = max(int(spec["leaves"]), 0)
    glass = _paint("glass", 0.35)
    if n == 0:                                   # fixed glass
        bx.box(i0, i1, -0.003, 0.003, j0, j1, glass)
    else:
        lw = (i1 - i0) / n
        leaf_col = _paint("pvc" if spec["leaf"] == "prefab" else
                          "alu" if spec["leaf"] == "alu" else "wood")
        for k in range(n):
            s0 = i0 + k * lw + gap
            s1 = i0 + (k + 1) * lw - gap
            d_off = (0.02 if k % 2 else -0.02) if spec["slide"] else 0.0
            if code == "W5":                     # louvres
                zz = j0
                while zz + 0.09 <= j1:
                    bx.box(s0, s1, -0.03, 0.03, zz, zz + 0.006, glass)
                    zz += 0.10
                bx.box(s0, s0 + 0.03, -0.03, 0.03, j0, j1, leaf_col)
                bx.box(s1 - 0.03, s1, -0.03, 0.03, j0, j1, leaf_col)
                continue
            if spec["glass"] > 0:
                st = 0.04 if spec["leaf"] == "alu" else 0.06
                d0, d1 = -0.0175 + d_off, 0.0175 + d_off
                bx.box(s0, s0 + st, d0, d1, j0, j1, leaf_col)
                bx.box(s1 - st, s1, d0, d1, j0, j1, leaf_col)
                bx.box(s0 + st, s1 - st, d0, d1, j1 - st, j1, leaf_col)
                bx.box(s0 + st, s1 - st, d0, d1, j0, j0 + st, leaf_col)
                if door and spec["glass"] < 0.9 and j1 - j0 > 1.2:
                    # A kick rail low on a glazed door.
                    bx.box(s0 + st, s1 - st, d0, d1, j0 + st + 0.001,
                           j0 + 0.30, leaf_col)
                    g0 = j0 + 0.301
                else:
                    g0 = j0 + st + 0.001
                bx.box(s0 + st, s1 - st, -0.003 + d_off, 0.003 + d_off,
                       g0, j1 - st, glass)
            else:
                bx.box(s0, s1, -0.0175 + d_off, 0.0175 + d_off, j0, j1,
                       leaf_col)
                # Two raised panels so a solid leaf reads as a door.
                if door and j1 - j0 > 1.2:
                    pc = _paint("wood_dark") if spec["leaf"] == "wood" \
                        else _paint("alu")
                    for z0p, z1p in ((j0 + 0.15, j0 + 0.85),
                                     (j0 + 1.05, j1 - 0.15)):
                        bx.box(s0 + 0.08, s1 - 0.08, 0.0175 + d_off,
                               0.0215 + d_off, z0p, z1p, pc)
                        bx.box(s0 + 0.08, s1 - 0.08, -0.0215 + d_off,
                               -0.0175 + d_off, z0p, z1p, pc)
            if door and not spec["slide"]:
                hx = s1 - 0.07 if k == n - 1 else s0 + 0.07
                hz = bottom + 1.0
                metal = _paint("metal")
                bx.box(hx - 0.015, hx + 0.015, 0.0175 + d_off,
                       0.07 + d_off, hz - 0.015, hz + 0.015, metal)
                bx.box(hx - 0.015, hx + 0.015, -0.07 + d_off,
                       -0.0175 + d_off, hz - 0.015, hz + 0.015, metal)
    kind = "door" if door else "window"
    name = opening_name(op, s)
    return bx.group(name, "structure", kind, name,
                    "IfcDoor" if door else "IfcWindow")


def opening_band(p0, u, z, a, b, sill, top, wt, band, wh, door):
    """The reinforced-concrete band (เสาเอ็น–ทับหลัง) round an opening:
    two posts and a lintel, and a sill beam under a window."""
    bx = _Boxes(p0, u, z)
    conc = _paint("concrete")
    d0, d1 = -wt / 2, wt / 2
    lo = 0.0 if door else max(sill - band, 0.0)
    hi = min(top + band, wh)
    bx.box(a - band, a, d0, d1, lo, hi, conc)
    bx.box(b, b + band, d0, d1, lo, hi, conc)
    if top + band <= wh + 1e-6:
        bx.box(a + 0.001, b - 0.001, d0, d1, top, top + band, conc)
    if not door and sill - band >= -1e-6:
        bx.box(a + 0.001, b - 0.001, d0, d1, sill - band, sill, conc)
    return bx.group("เสาเอ็น-ทับหลัง ค.ส.ล.", "structure", "band",
                    "เสาเอ็น-ทับหลัง", "IfcBeam")


def band_length(w, h, sill, door, band, wh) -> float:
    """Metres of เสาเอ็น/ทับหลัง round one opening (as the 3D band)."""
    lo = 0.0 if door else max(sill - band, 0.0)
    hi = min(sill + h + band, wh) if not door else min(h + band, wh)
    L = 2 * (hi - lo)
    if (0.0 if door else sill) + h + band <= wh + 1e-6:
        L += w
    if not door and sill - band >= -1e-6:
        L += w
    return L


def stair_member(stp, s, z):
    n, L, H = stair_geometry(stp, s)
    rx, ry = _DIRS[int(stp.get("dir", 1)) % 4]
    tx, ty = ry, -rx
    w = float(stp.get("w") or s["stair_w"])
    cx, cy = float(stp["x"]), float(stp["y"])
    ax, ay = cx - rx * L / 2, cy - ry * L / 2
    path = [(ax - tx * w / 2, ay - ty * w / 2, z),
            (ax + tx * w / 2, ay + ty * w / 2, z)]
    return _member("structure", "stair", "บันได คสล.", "stair",
                   dict(L=_mm(L), H=_mm(H), n=n, t=_mm(s["stair_t"])), path,
                   anchor="bl", ifc="IfcStair", name="บันได คสล.")


# ---------------------------------------------------------------------------
# Roofs
# ---------------------------------------------------------------------------

def plan_rectangles(rooms):
    """Cover the plan with few rectangles, each as large as the plan allows
    (they overlap where a wing runs into the main block — that is what makes
    the roofs meet in valleys). Returns [(x0, y0, x1, y1)]."""
    xs = sorted({_r(p[0]) for rm in rooms for p in room_corners(rm)})
    ys = sorted({_r(p[1]) for rm in rooms for p in room_corners(rm)})
    nx, ny = len(xs) - 1, len(ys) - 1
    if nx < 1 or ny < 1:
        return []

    def inside(cx, cy):
        return any(rm["x"] - 1e-9 <= cx <= rm["x"] + rm["w"] + 1e-9
                   and rm["y"] - 1e-9 <= cy <= rm["y"] + rm["d"] + 1e-9
                   for rm in rooms)
    full = [[inside((xs[i] + xs[i + 1]) / 2, (ys[j] + ys[j + 1]) / 2)
             for j in range(ny)] for i in range(nx)]
    area = [[(xs[i + 1] - xs[i]) * (ys[j + 1] - ys[j]) for j in range(ny)]
            for i in range(nx)]
    covered = [[False] * ny for _ in range(nx)]
    rects = []
    while any(full[i][j] and not covered[i][j]
              for i in range(nx) for j in range(ny)):
        best = None
        for i0 in range(nx):
            for i1 in range(i0, nx):
                for j0 in range(ny):
                    for j1 in range(j0, ny):
                        ok, new, tot = True, 0.0, 0.0
                        for i in range(i0, i1 + 1):
                            for j in range(j0, j1 + 1):
                                if not full[i][j]:
                                    ok = False
                                    break
                                tot += area[i][j]
                                if not covered[i][j]:
                                    new += area[i][j]
                            if not ok:
                                break
                        if ok and new > 1e-9:
                            key = (new, tot)
                            if best is None or key > best[0]:
                                best = (key, (i0, i1, j0, j1))
        if best is None:
            break
        i0, i1, j0, j1 = best[1]
        for i in range(i0, i1 + 1):
            for j in range(j0, j1 + 1):
                covered[i][j] = True
        rects.append((xs[i0], ys[j0], xs[i1 + 1], ys[j1 + 1]))
    return rects


def _roof_rect(rect, z0, s, others=(), cols=(), lift=0.0):
    """The frame lines of one rectangular roof (see :func:`roof_lines`).

    A gable end that runs into another roof (``others``: their eave boxes)
    is hipped instead, so it dives under that roof rather than poking a
    gable out through it — the usual way an L or T wing is framed."""
    ov = float(s["overhang"])
    tan = math.tan(math.radians(float(s["pitch"])))
    x0, y0, x1, y1 = rect[0] - ov, rect[1] - ov, rect[2] + ov, rect[3] + ov
    swap = (y1 - y0) > (x1 - x0)            # ridge along the long side
    if swap:
        x0, y0, x1, y1 = y0, x0, y1, x1
    L, W = x1 - x0, y1 - y0
    half = W / 2

    def h(dist):                            # roof height at a distance
        # ``lift`` = the rafter depth: a rafter's underside sits on the
        # ring beam / column heads at the wall line (dist = overhang).
        return z0 + lift + (dist - ov) * tan

    def P3(x, y, z):
        return (y, x, z) if swap else (x, y, z)

    def covered(xx):
        px, py, _z = P3(xx, y0 + half, 0.0)
        return any(o[0] - 1e-6 <= px <= o[2] + 1e-6 and
                   o[1] - 1e-6 <= py <= o[3] + 1e-6 for o in others)

    out = {"ridge": [], "hip": [], "rafter": [], "purlin": [], "post": [],
           "skin": [], "eave": [], "barge": []}
    zr = h(half)
    yc = y0 + half
    if s["roof"] == "hip":
        h0 = h1 = True
    else:
        h0, h1 = covered(x0), covered(x1)
    rx0 = x0 + half if h0 else x0
    rx1 = x1 - half if h1 else x1
    if rx1 < rx0:
        rx0 = rx1 = (x0 + x1) / 2
    if rx1 - rx0 > 1e-6:
        out["ridge"].append([P3(rx0, yc, zr), P3(rx1, yc, zr)])
    for hipped, cx, ex in ((h0, x0, rx0), (h1, x1, rx1)):
        if hipped:
            for cy in (y0, y1):
                out["hip"].append([P3(cx, cy, h(0)), P3(ex, yc, zr)])
    sp = max(float(s["rafter_sp"]), 0.2)
    big = 1e9
    # Rafters (จันทัน) on every column line (จันทันเอก on the column heads),
    # and between them at no more than the set spacing (จันทันพราง).
    stations = {round(x0, 4), round(x1, 4)}
    for c in cols:
        cx = c[1] if swap else c[0]
        if x0 + 1e-6 < cx < x1 - 1e-6:
            stations.add(round(cx, 4))
    stations = sorted(stations)
    xs = []
    for a_, b_ in zip(stations, stations[1:]):
        n_ = max(int(math.ceil((b_ - a_) / sp - 1e-9)), 1)
        xs += [a_ + (b_ - a_) * k / n_ for k in range(n_)]
    xs.append(stations[-1])
    for x in xs:
        reach = min(half, (x - x0) if h0 else big, (x1 - x) if h1 else big)
        if reach <= 0.05:
            continue
        out["rafter"].append([P3(x, y0, h(0)), P3(x, y0 + reach, h(reach))])
        out["rafter"].append([P3(x, y1, h(0)), P3(x, y1 - reach, h(reach))])
    cnt = max(int(math.floor(W / sp + 1e-9)), 1)
    for hipped, ex, sgn in ((h0, x0, 1), (h1, x1, -1)):
        if not hipped:                       # jack rafters on a hipped end
            continue
        for i in range(cnt + 1):
            y = y0 + W * i / cnt
            reach = min(half, y - y0, y1 - y)
            if reach <= 0.05:
                continue
            out["rafter"].append([P3(ex, y, h(0)),
                                  P3(ex + sgn * reach, y, h(reach))])
    psp = max(float(s["purlin_sp"]), 0.1) * math.cos(math.radians(
        float(s["pitch"])))
    d = 0.05
    while d < half - 0.05:
        a0 = x0 + d if h0 else x0
        a1 = x1 - d if h1 else x1
        if a1 - a0 > 1e-6:
            if h0 and h1:
                out["purlin"].append({"closed": True, "path": [
                    P3(a0, y0 + d, h(d)), P3(a1, y0 + d, h(d)),
                    P3(a1, y1 - d, h(d)), P3(a0, y1 - d, h(d))]})
            elif h0:
                out["purlin"].append({"closed": False, "path": [
                    P3(a1, y0 + d, h(d)), P3(a0, y0 + d, h(d)),
                    P3(a0, y1 - d, h(d)), P3(a1, y1 - d, h(d))]})
            elif h1:
                out["purlin"].append({"closed": False, "path": [
                    P3(a0, y0 + d, h(d)), P3(a1, y0 + d, h(d)),
                    P3(a1, y1 - d, h(d)), P3(a0, y1 - d, h(d))]})
            else:
                for yy in (y0 + d, y1 - d):
                    out["purlin"].append({"closed": False, "path": [
                        P3(a0, yy, h(d)), P3(a1, yy, h(d))]})
        d += psp
    if zr - z0 > 0.1:
        for xx in ((rx0, rx1) if rx1 - rx0 > 1e-6 else (rx0,)):
            out["post"].append([P3(xx, yc, z0), P3(xx, yc, zr)])
    e = [P3(x0, y0, h(0)), P3(x1, y0, h(0)), P3(x1, y1, h(0)),
         P3(x0, y1, h(0))]
    # Eave lines (เชิงชาย) and, on a gable end, the rakes (ปั้นลม).
    out["eave"] = [[e[0], e[1]], [e[3], e[2]]]
    for hipped, xx, pair in ((h0, x0, (e[0], e[3])), (h1, x1, (e[1], e[2]))):
        if hipped:
            out["eave"].append(list(pair))
        else:
            out["barge"].append([P3(xx, y0, h(0)), P3(xx, yc, zr)])
            out["barge"].append([P3(xx, y1, h(0)), P3(xx, yc, zr)])
    r0, r1 = P3(rx0, yc, zr), P3(rx1, yc, zr)

    def poly(*pts):
        outp = []
        for p in pts:
            if not outp or math.dist(outp[-1], p) > 1e-9:
                outp.append(p)
        if len(outp) > 1 and math.dist(outp[0], outp[-1]) < 1e-9:
            outp.pop()
        return outp
    out["skin"] = [poly(e[0], e[1], r1, r0), poly(e[2], e[3], r0, r1)]
    if h1:
        out["skin"].append(poly(e[1], e[2], r1))
    if h0:
        out["skin"].append(poly(e[3], e[0], r0))
    return out


def roof_lines(data):
    """The roof frame as lines: {"ridge": [...], "hip": [...], "rafter":
    [...], "purlin": [{"path", "closed"}…], "post": [...], "skin":
    [polygons…], "rects": [...], "z0"} — 3D points in metres. ``None``
    when there is no roof to make."""
    s = settings_of(data)
    floors, _skipped = stacked(data)
    if not floors or s.get("roof") not in ("hip", "gable"):
        return None
    top = floors[-1]["rooms"]
    z0 = len(floors) * float(s["floor_h"])
    if s.get("roof_mode") == "bbox":
        fp = footprint(top)
        rects = [fp]
    else:
        rects = plan_rectangles(top)
    out = {"ridge": [], "hip": [], "rafter": [], "purlin": [], "post": [],
           "skin": [], "eave": [], "barge": [], "rects": rects, "z0": z0,
           "valley": 0.0}
    ov = float(s["overhang"])
    from core import wanic_roofclip as RC
    boxes = [(r[0] - ov, r[1] - ov, r[2] + ov, r[3] + ov) for r in rects]
    # A wing's gable end that runs into an earlier (larger) roof is hipped.
    fam, prm = steel_lookup(s["rafter"])
    lift = float(prm.get("H", prm.get("D", prm.get("A", 0.0)))) / 1000.0
    cols = nodes(top)
    parts = [_roof_rect(rect, z0, s, boxes[:i], cols, lift) for i, rect in
             enumerate(rects)]
    roofs = [RC.Roof((r[0] - ov, r[1] - ov, r[2] + ov, r[3] + ov),
                     part["skin"]) for r, part in zip(rects, parts)]
    many = len(rects) > 1
    kept = {}
    for i, (rect, part) in enumerate(zip(rects, parts)):
        if not many:
            for k in ("ridge", "hip", "rafter", "purlin", "post", "skin"):
                out[k] += part[k]
        else:
            # Trim what lies under a neighbouring roof (L / T plans).
            for k in ("ridge", "hip", "rafter"):
                for a, b in part[k]:
                    out[k] += RC.clip_segment(a, b, i, roofs)
            for pl in part["purlin"]:
                for seg in RC.clip_path(pl["path"], i, roofs, pl["closed"]):
                    out["purlin"].append({"closed": False, "path": seg})
            for a, b in part["post"]:
                if not RC.hidden(b, i, roofs):
                    out["post"].append([a, b])
            kept[i] = []
            for poly in part["skin"]:
                kept[i] += RC.clip_facet(poly, i, roofs)
            out["skin"] += kept[i]
        for k in ("eave", "barge"):
            for a, b in part[k]:
                out[k] += RC.clip_segment(a, b, i, roofs) if many \
                    else [[a, b]]
    out["eave"] = _merge_collinear(out["eave"])
    if many:
        out["valley"] = RC.valley_length(kept, roofs)
    return out


def _merge_collinear(edges):
    """Axis-aligned edges with overlapping runs on one line become one."""
    lines = {}
    for a, b in edges:
        along_x = abs(a[1] - b[1]) < 1e-9
        key = (along_x, round(a[1] if along_x else a[0], 4), round(a[2], 4))
        k = 0 if along_x else 1
        lines.setdefault(key, []).append(tuple(sorted((a[k], b[k]))))
    out = []
    for (along_x, c, z), runs in sorted(lines.items()):
        runs.sort()
        merged = [list(runs[0])]
        for lo, hi in runs[1:]:
            if lo <= merged[-1][1] + 1e-6:
                merged[-1][1] = max(merged[-1][1], hi)
            else:
                merged.append([lo, hi])
        for lo, hi in merged:
            out.append([(lo, c, z), (hi, c, z)] if along_x
                       else [(c, lo, z), (c, hi, z)])
    return out


def _outside(a, b, boxes):
    """The parts of the axis-aligned edge a→b that lie outside every box
    (x0, y0, x1, y1) — where another roof does not cover it."""
    along_x = abs(a[1] - b[1]) < 1e-9
    k = 0 if along_x else 1
    c = a[1] if along_x else a[0]
    lo, hi = sorted((a[k], b[k]))
    pieces = [(lo, hi)]
    for bx in boxes:
        clo, chi = (bx[1], bx[3]) if along_x else (bx[0], bx[2])
        if not clo + 1e-6 < c < chi - 1e-6:
            continue
        cut_lo, cut_hi = (bx[0], bx[2]) if along_x else (bx[1], bx[3])
        nxt = []
        for p0, p1 in pieces:
            if cut_hi <= p0 or cut_lo >= p1:
                nxt.append((p0, p1))
                continue
            if cut_lo > p0:
                nxt.append((p0, cut_lo))
            if cut_hi < p1:
                nxt.append((cut_hi, p1))
        pieces = nxt
    z = a[2]
    out = []
    for p0, p1 in pieces:
        if p1 - p0 > 0.05:
            out.append([(p0, c, z), (p1, c, z)] if along_x
                       else [(c, p0, z), (c, p1, z)])
    return out


def roof_members(data) -> tuple[list, dict]:
    s = settings_of(data)
    lines = roof_lines(data)
    out, count = [], {}
    if lines is None:
        return out, count

    def add(g, kind):
        if g is not None:
            out.append(g)
            count[kind] = count.get(kind, 0) + 1

    names = {"ridge": "อกไก่", "hip": "ตะเฆ่สัน", "rafter": "จันทัน",
             "purlin": "แป", "post": "ดั้ง"}
    for kind in ("ridge", "hip", "rafter", "post"):
        fam, params = steel_lookup(s[kind])
        for path in lines[kind]:
            add(_member("roof", kind, names[kind], fam, params, path,
                        anchor="tc" if kind != "post" else "c",
                        ifc="IfcMember", name=f"{names[kind]} {s[kind]}"),
                kind)
    fam, params = steel_lookup(s["purlin"])
    for pl in lines["purlin"]:
        add(_member("roof", "purlin", "แป", fam, params, pl["path"],
                    anchor="bc", ifc="IfcMember", closed=pl["closed"],
                    name=f"แป {s['purlin']}"), "purlin")
    if s.get("fascia", True):
        fp = dict(b=_mm(s.get("fascia_t", 0.025)), h=_mm(s.get("fascia_h", 0.20)))
        for path in lines["eave"]:
            add(_member("roof", "fascia", "เชิงชาย", "rect", fp, path,
                        anchor="tc", ifc="IfcMember", name="เชิงชาย"),
                "fascia")
        for path in lines["barge"]:
            add(_member("roof", "barge", "ปั้นลม", "rect", fp, path,
                        anchor="tc", ifc="IfcMember", name="ปั้นลม"),
                "barge")
    from core.wanic_catalog import COLORS, roof_tile, tile_color
    _tc, tile = roof_tile(s)
    tcolor = tile_color(s)
    for g in out:
        k = ((g.ext or {}).get(EXT_KEY) or {}).get("kind")
        if k in ("fascia", "barge"):
            g.material = {"color": COLORS["fascia"]}
    lift = float(params.get("H", params.get("D", params.get("A", 80)))) / 1000.0
    if s.get("skin") and lines["skin"]:
        g = roof_skin(lines["skin"], lift)
        if g is not None:
            g.material = {"color": tuple(c * 0.55 for c in tcolor),
                          "mat": "แผ่นรองหลังคา"}
            add(_tag(g, "roof", "skin", "หลังคา"), "skin")
        if s.get("tiles_3d", True):
            add(roof_tiles(lines, s, lift + 0.01), "tiles")
    if s.get("caps", True) and s.get("skin"):
        # Ridge and hip caps (ครอบสัน / ครอบตะเข้สัน) and, on a gable, the
        # verge caps (ครอบข้าง/ครอบปั้นลม), sitting on the covering.
        amp = tile["wave"][2]
        for kind, paths, name in (("ridge", lines["ridge"], "ครอบสัน"),
                                  ("hip", lines["hip"], "ครอบตะเข้สัน"),
                                  ("barge", lines["barge"], "ครอบข้าง")):
            for path in paths:
                add(cap_barrel(path, 0.13, tcolor, name, lift + amp + 0.02),
                    "cap")
    return out, count


# ---------------------------------------------------------------------------
# The covering as tiles you can see, and the cap pieces
# ---------------------------------------------------------------------------

def _wave(kind, period, amp, u):
    t = (u / period) % 1.0
    if kind == "trap":                              # metal-sheet ribs
        if t < 0.10:
            f = 1.0
        elif t < 0.20:
            f = 1.0 - (t - 0.10) / 0.10
        elif t < 0.90:
            f = 0.0
        else:
            f = (t - 0.90) / 0.10
        return amp * f
    f = 0.5 - 0.5 * math.cos(2 * math.pi * t)
    if kind == "s":                                 # Spanish S: pan + roll
        f += 0.18 * math.sin(4 * math.pi * t)
    return amp * f


def _clip2(cell, poly):
    """Sutherland–Hodgman: a 2D polygon clipped by a convex one (CCW)."""
    out = cell
    n = len(poly)
    for k in range(n):
        if not out:
            break
        (ax, ay), (bx, by) = poly[k], poly[(k + 1) % n]

        def inside(p):
            return (bx - ax) * (p[1] - ay) - (by - ay) * (p[0] - ax) >= -1e-12
        src, out = out, []
        for i in range(len(src)):
            p, q = src[i], src[(i + 1) % len(src)]
            ip, iq = inside(p), inside(q)
            if ip:
                out.append(p)
            if ip != iq:
                dx, dy = q[0] - p[0], q[1] - p[1]
                ex, ey = bx - ax, by - ay
                den = ex * dy - ey * dx
                if abs(den) > 1e-15:
                    t = (ex * (ay - p[1]) - ey * (ax - p[0])) / den
                    out.append((p[0] + dx * t, p[1] + dy * t))
    clean = []
    for p in out:
        if not clean or abs(p[0] - clean[-1][0]) + abs(p[1] - clean[-1][1]) \
                > 1e-9:
            clean.append(p)
    while len(clean) > 1 and abs(clean[0][0] - clean[-1][0]) + \
            abs(clean[0][1] - clean[-1][1]) <= 1e-9:
        clean.pop()
    return clean


def roof_tiles(lines, s, lift):
    """The covering as rows of tiles (or sheets) following the chosen
    profile, laid on every visible piece of the roof — one painted group.
    Pure display: the takeoff bills the flat covering's area."""
    from PySide6.QtGui import QVector3D

    from core.group import Group
    from core.mesh import Mesh
    from core.wanic_catalog import roof_tile, tile_color
    _code, tile = roof_tile(s)
    kind, period, amp, course, step = tile["wave"]
    color = tile_color(s)
    pitch = math.radians(float(s["pitch"]))
    sin_p = math.sin(pitch) or 1.0
    eave_z = min((p[2] for poly in lines["skin"] for p in poly),
                 default=0.0)
    cw = max(period / 6.0, 0.03)
    mesh = Mesh()
    attrs = {"color": tuple(color)}
    for poly in lines["skin"]:
        if len(poly) < 3:
            continue
        a3 = [QVector3D(*p) for p in poly]
        nrm = QVector3D.crossProduct(a3[1] - a3[0], a3[2] - a3[0])
        if nrm.length() < 1e-12:
            continue
        nrm = nrm.normalized()
        if nrm.z() < 0:
            nrm = -nrm
        u = QVector3D(-nrm.y(), nrm.x(), 0.0)
        if u.length() < 1e-9:
            continue
        u = u.normalized()
        v = QVector3D.crossProduct(nrm, u).normalized()
        if v.z() < 0:
            u, v = -u, -v
        ref = a3[0]
        uu0 = QVector3D.dotProduct(ref, u)
        vr0 = (ref.z() - eave_z) / sin_p

        def to2(p):
            return (QVector3D.dotProduct(p, u),
                    (p.z() - eave_z) / sin_p)

        def to3(uu, vr, off):
            return ref + u * (uu - uu0) + v * (vr - vr0) + nrm * off
        p2 = [to2(p) for p in a3]
        # CCW in (u, v)
        area2 = sum(p2[i][0] * p2[(i + 1) % len(p2)][1] -
                    p2[(i + 1) % len(p2)][0] * p2[i][1]
                    for i in range(len(p2)))
        if area2 < 0:
            p2 = p2[::-1]
        umin, umax = min(p[0] for p in p2), max(p[0] for p in p2)
        vmin, vmax = min(p[1] for p in p2), max(p[1] for p in p2)
        rows = []
        if course > 0:
            k0 = int(math.floor(vmin / course))
            k = k0
            while k * course < vmax:
                rows.append((max(k * course, vmin),
                             min((k + 1) * course, vmax), k))
                k += 1
        else:
            rows.append((vmin, vmax, 0))

        def off(uu, vr, k):
            o = lift + _wave(kind, period, amp, uu)
            if course > 0 and step > 0:
                o += step * (1.0 - (vr - k * course) / course)
            return o
        c0 = int(math.floor(umin / cw))
        c1 = int(math.ceil(umax / cw))
        for va, vb, k in rows:
            for c in range(c0, c1):
                ua, ub = c * cw, (c + 1) * cw
                cell = _clip2([(ua, va), (ub, va), (ub, vb), (ua, vb)], p2)
                if len(cell) < 3:
                    continue
                f = mesh.add_face([to3(x, y, off(x, y, k)) for x, y in cell])
                if f is not None:
                    f.attrs.update(attrs)
                # The lip where this course laps over the one below.
                if course > 0 and step > 0 and abs(va - k * course) < 1e-9 \
                        and k * course > vmin + 1e-6:
                    bot = [p for p in cell if abs(p[1] - va) < 1e-9]
                    if len(bot) >= 2:
                        (xa, _), (xb, _) = sorted(bot)[0], sorted(bot)[-1]
                        if xb - xa > 1e-4:
                            hi = step
                            lo_a = off(xa, va, k) - hi
                            lo_b = off(xb, va, k) - hi
                            g = mesh.add_face([
                                to3(xa, va, lo_a), to3(xb, va, lo_b),
                                to3(xb, va, off(xb, va, k)),
                                to3(xa, va, off(xa, va, k))])
                            if g is not None:
                                g.attrs.update(attrs)
    if not mesh.faces:
        return None
    g = Group(mesh, name=f"กระเบื้องหลังคา — {tile['name']}")
    g.ifc = {"class": "IfcCovering", "name": tile["name"]}
    return _tag(g, "roof", "tiles", tile["name"])


def cap_barrel(path, radius, color, name, lift):
    """A half-round cap (ครอบสันโค้ง) along a ridge, hip or verge."""
    from PySide6.QtGui import QVector3D

    from core.group import Group
    from core.mesh import Mesh
    a = QVector3D(*path[0])
    b = QVector3D(*path[1])
    t = b - a
    if t.length() < 0.05:
        return None
    t = t.normalized()
    side = QVector3D.crossProduct(t, QVector3D(0, 0, 1))
    if side.length() < 1e-9:
        return None
    side = side.normalized()
    up = QVector3D.crossProduct(side, t).normalized()
    if up.z() < 0:
        up = -up
    a = a + up * lift
    b = b + up * lift
    n = 8
    ring = [side * (radius * math.cos(math.pi * k / n)) +
            up * (radius * 0.75 * math.sin(math.pi * k / n))
            for k in range(n + 1)]
    mesh = Mesh()
    attrs = {"color": tuple(color)}
    for k in range(n):
        f = mesh.add_face([a + ring[k], b + ring[k], b + ring[k + 1],
                           a + ring[k + 1]])
        if f is not None:
            f.attrs.update(attrs)
    for end in (a, b):
        f = mesh.add_face([end + r for r in ring])
        if f is not None:
            f.attrs.update(attrs)
    g = Group(mesh, name=name)
    g.ifc = {"class": "IfcCovering", "name": name}
    return _tag(g, "roof", "cap", name)


def roof_skin(polys, lift=0.0):
    """The roof covering as one group of planar faces, raised ``lift``
    metres to sit on the purlins; tagged IfcRoof so the takeoff bills its
    area (an open shell — area only, no volume)."""
    from PySide6.QtGui import QVector3D

    from core.group import Group
    from core.mesh import Mesh
    mesh = Mesh()
    for poly in polys:
        pts = [QVector3D(*p) for p in poly]
        if len(pts) < 3:
            continue
        n = QVector3D.crossProduct(pts[1] - pts[0], pts[2] - pts[0])
        if n.length() < 1e-12:
            continue
        n = n.normalized()
        if n.z() < 0:
            pts, n = pts[::-1], -n
        mesh.add_face([p + n * lift for p in pts])
    if not mesh.faces:
        return None
    g = Group(mesh, name="หลังคา")
    g.ifc = {"class": "IfcRoof", "name": "หลังคา"}
    return g


def build(data, parts=("structure", "roof")):
    """All generated groups for ``parts`` and a Thai summary line."""
    groups, count = [], {}
    if "structure" in parts:
        g, c = structure_members(data)
        groups += g
        count.update(c)
    if "roof" in parts:
        g, c = roof_members(data)
        groups += g
        count.update(c)
    return groups, count


KIND_TH = [("footing", "ฐานราก"), ("pile", "เสาเข็ม"), ("stump", "ตอม่อ"), ("column", "เสา"),
           ("beam", "คาน"), ("slab", "พื้น"), ("wall", "ผนัง"),
           ("door", "ประตู"), ("window", "หน้าต่าง"), ("stair", "บันได"),
           ("ridge", "อกไก่"), ("hip", "ตะเฆ่สัน"), ("rafter", "จันทัน"),
           ("purlin", "แป"), ("post", "ดั้ง"), ("fascia", "เชิงชาย"),
           ("barge", "ปั้นลม"), ("cap", "ครอบสัน/ครอบข้าง"),
           ("band", "เสาเอ็น-ทับหลัง"), ("fixture", "สุขภัณฑ์"),
           ("tiles", "กระเบื้อง"),
           ("skin", "แผ่นหลังคา")]


def summary(count) -> str:
    parts = [f"{th} {count[k]}" for k, th in KIND_TH if count.get(k)]
    return " · ".join(parts) if parts else "ไม่มีชิ้นส่วน"


def generated(scene, parts=("structure", "roof")):
    """Top-level groups an earlier build made for ``parts``."""
    out = []
    for g in scene.groups:
        rec = ((getattr(g, "ext", None) or {}).get(EXT_KEY)) or {}
        if rec.get("part") in parts:
            out.append(g)
    return out


def takeoff_rates(data) -> list[dict]:
    """Price lines (prices 0 — the user's to fill) for everything a build
    makes, matched by member name, for WANIC ถอดปริมาณ."""
    from core.wanic_takeoff import new_rate
    s = settings_of(data)
    R = []

    def add(cat, code, desc, value, qty, unit, factor=1.0):
        R.append(new_rate(id=f"wb{len(R) + 1}", category=cat, code=code,
                          desc=desc, by="name", value=value, qty=qty,
                          unit=unit, factor=factor))
    add("งานฐานราก", "1.1", "คอนกรีตฐานราก F1", "F1", "volume", "ลบ.ม.")
    add("งานฐานราก", "1.2", "คอนกรีตตอม่อ PC1", "PC1", "volume", "ลบ.ม.")
    add("งานโครงสร้าง", "2.1", "คอนกรีตเสา C1", "C1", "volume", "ลบ.ม.")
    add("งานโครงสร้าง", "2.2", "คอนกรีตคานคอดิน GB1", "GB1", "volume", "ลบ.ม.")
    add("งานโครงสร้าง", "2.3", "คอนกรีตคานชั้นบน B1", "B1", "volume", "ลบ.ม.")
    add("งานโครงสร้าง", "2.4", "คอนกรีตคานหลังคา RB1", "RB1", "volume", "ลบ.ม.")
    add("งานโครงสร้าง", "2.5", "คอนกรีตพื้นชั้นล่าง S1", "S1", "volume", "ลบ.ม.")
    add("งานโครงสร้าง", "2.6", "คอนกรีตพื้นชั้นบน S2", "S2", "volume", "ลบ.ม.")
    if s.get("walls"):
        add("งานสถาปัตยกรรม", "3.1", "ผนังก่ออิฐ (พื้นที่ 1 ด้าน)",
            "ผนังก่ออิฐ", "side_area", "ตร.ม.", 0.5)
        add("งานสถาปัตยกรรม", "3.2", "ฉาบปูนผนัง (2 ด้าน)", "ผนังก่ออิฐ",
            "side_area", "ตร.ม.")
    floors, _sk = stacked(data)
    ops = sorted({(op.get("type", "door"), opening_name(op, s))
                  for f in floors for op in f["openings"]})
    for i, (kind, label) in enumerate(ops):
        add("งานประตู-หน้าต่าง", f"3.{i + 3}", label, label, "count", "ชุด")
    if any(f["stairs"] for f in floors):
        add("งานโครงสร้าง", "2.7", "คอนกรีตบันได", "บันได คสล.", "volume",
            "ลบ.ม.")
    names = {"ridge": "อกไก่", "hip": "ตะเฆ่สัน", "rafter": "จันทัน",
             "purlin": "แป", "post": "ดั้ง"}
    seen = set()
    for i, kind in enumerate(("ridge", "hip", "rafter", "purlin", "post")):
        label = f"{names[kind]} {s[kind]}"
        if label in seen:
            continue
        seen.add(label)
        add("งานหลังคา", f"4.{i + 1}", f"โครงหลังคาเหล็ก {label}", label,
            "steel_kg", "กก.")
    if s.get("skin"):
        add("งานหลังคา", "4.9", "มุงหลังคา (พื้นที่ตามแนวลาด)", "หลังคา",
            "top_area", "ตร.ม.")
    return R
