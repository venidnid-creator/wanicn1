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
    "stair_t": 0.15,
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
    return {"rooms": [], "openings": [], "stairs": []}


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
                        "stairs": f.get("stairs") or [], "src": i})
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
         "slabs": [], "walls": [], "openings": [], "stairs": [], "n": n,
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
    """(width, height, sill) of an opening, defaults from the settings."""
    if op.get("type") == "window":
        return (float(op.get("w") or s["win_w"]),
                float(op.get("h") or s["win_h"]),
                float(op.get("sill") if op.get("sill") is not None
                      else s["win_sill"]))
    return (float(op.get("w") or s["door_w"]),
            float(op.get("h") or s["door_h"]), 0.0)


def opening_name(op, s):
    w, h, _sill = opening_size(op, s)
    kind = "หน้าต่าง" if op.get("type") == "window" else "ประตู"
    return f"{kind} {w:.2f}×{h:.2f} ม."


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
    return out, count


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
        cur = half
        for sdist, op in _openings_on(p0, p1, wl["openings"]):
            ow, oh, sill = opening_size(op, s)
            a = max(half, sdist - ow / 2)
            b = min(L - half, sdist + ow / 2)
            if b - a < 0.1:
                continue
            top = min(sill + oh, wh)
            piece(cur, a, z0, wh)
            piece(a, b, z0, sill)                       # under a window
            piece(a, b, z0 + top, wh - top)             # over the opening
            kind = "window" if op.get("type") == "window" else "door"
            add(_member("structure", kind, opening_name(op, s), "rect",
                        dict(b=40.0, h=_mm(top - sill)),
                        [at(a, z0 + sill), at(b, z0 + sill)], anchor="bc",
                        ifc="IfcWindow" if kind == "window" else "IfcDoor",
                        name=opening_name(op, s)), kind)
            cur = max(cur, b)
        piece(cur, L - half, z0, wh)


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


def _roof_rect(rect, z0, s):
    """The frame lines of one rectangular roof (see :func:`roof_lines`)."""
    ov = float(s["overhang"])
    tan = math.tan(math.radians(float(s["pitch"])))
    x0, y0, x1, y1 = rect[0] - ov, rect[1] - ov, rect[2] + ov, rect[3] + ov
    swap = (y1 - y0) > (x1 - x0)            # ridge along the long side
    if swap:
        x0, y0, x1, y1 = y0, x0, y1, x1
    L, W = x1 - x0, y1 - y0
    half = W / 2

    def h(dist):                            # roof height at a distance
        return z0 + (dist - ov) * tan       # in from the eave line

    def P3(x, y, z):
        return (y, x, z) if swap else (x, y, z)

    out = {"ridge": [], "hip": [], "rafter": [], "purlin": [], "post": [],
           "skin": []}
    zr = h(half)
    yc = y0 + half
    hip = s["roof"] == "hip"
    rx0, rx1 = (x0 + half, x1 - half) if hip else (x0, x1)
    if rx1 - rx0 > 1e-6:
        out["ridge"].append([P3(rx0, yc, zr), P3(rx1, yc, zr)])
    if hip:
        for cx, cy, ex in ((x0, y0, rx0), (x0, y1, rx0), (x1, y0, rx1),
                           (x1, y1, rx1)):
            out["hip"].append([P3(cx, cy, h(0)), P3(ex, yc, zr)])
    sp = max(float(s["rafter_sp"]), 0.2)
    count = max(int(math.floor(L / sp + 1e-9)), 1)
    for i in range(count + 1):
        x = x0 + L * i / count
        reach = min(half, x - x0, x1 - x) if hip else half
        if reach <= 0.05:
            continue
        out["rafter"].append([P3(x, y0, h(0)), P3(x, y0 + reach, h(reach))])
        out["rafter"].append([P3(x, y1, h(0)), P3(x, y1 - reach, h(reach))])
    if hip:                                  # jack rafters on the ends
        cnt = max(int(math.floor(W / sp + 1e-9)), 1)
        for i in range(cnt + 1):
            y = y0 + W * i / cnt
            reach = min(half, y - y0, y1 - y)
            if reach <= 0.05:
                continue
            out["rafter"].append([P3(x0, y, h(0)), P3(x0 + reach, y, h(reach))])
            out["rafter"].append([P3(x1, y, h(0)), P3(x1 - reach, y, h(reach))])
    psp = max(float(s["purlin_sp"]), 0.1) * math.cos(math.radians(
        float(s["pitch"])))
    d = 0.05
    while d < half - 0.05:
        if hip:
            if L - 2 * d > 1e-6 and W - 2 * d > 1e-6:
                out["purlin"].append({"closed": True, "path": [
                    P3(x0 + d, y0 + d, h(d)), P3(x1 - d, y0 + d, h(d)),
                    P3(x1 - d, y1 - d, h(d)), P3(x0 + d, y1 - d, h(d))]})
        else:
            for yy in (y0 + d, y1 - d):
                out["purlin"].append({"closed": False, "path": [
                    P3(x0, yy, h(d)), P3(x1, yy, h(d))]})
        d += psp
    if zr - z0 > 0.1:
        for xx in ((rx0, rx1) if rx1 - rx0 > 1e-6 else (rx0,)):
            out["post"].append([P3(xx, yc, z0), P3(xx, yc, zr)])
    e = [P3(x0, y0, h(0)), P3(x1, y0, h(0)), P3(x1, y1, h(0)),
         P3(x0, y1, h(0))]
    r0, r1 = P3(rx0, yc, zr), P3(rx1, yc, zr)
    if hip:
        if abs(rx1 - rx0) < 1e-6:                   # square plan: a pyramid
            out["skin"] = [[e[0], e[1], r0], [e[1], e[2], r0],
                           [e[2], e[3], r0], [e[3], e[0], r0]]
        else:
            out["skin"] = [[e[0], e[1], r1, r0], [e[1], e[2], r1],
                           [e[2], e[3], r0, r1], [e[3], e[0], r0]]
    else:
        out["skin"] = [[e[0], e[1], r1, r0], [e[2], e[3], r0, r1]]
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
           "skin": [], "rects": rects, "z0": z0}
    for rect in rects:
        part = _roof_rect(rect, z0, s)
        for k in ("ridge", "hip", "rafter", "purlin", "post", "skin"):
            out[k] += part[k]
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
    if s.get("skin") and lines["skin"]:
        lift = float(params.get("H", params.get("D", params.get("A", 80))))
        g = roof_skin(lines["skin"], lift / 1000.0)
        if g is not None:
            add(_tag(g, "roof", "skin", "หลังคา"), "skin")
    return out, count


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
           ("purlin", "แป"), ("post", "ดั้ง"), ("skin", "แผ่นหลังคา")]


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
