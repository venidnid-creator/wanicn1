# SPDX-License-Identifier: GPL-3.0-or-later
# WANICNSURVEY 3D — "WANIC ออกแบบอาคาร": room plan → structure → roof.
"""From a plan of rectangular rooms (per floor) to a 3D reinforced-concrete
frame and a steel roof frame, ready for the takeoff.

Layout rules (simple, predictable, all editable afterwards):

- a column stands at every room corner of a floor (shared corners count
  once); a footing (F) and a stump (PC) carry each ground-floor column;
- beams run along every room edge, split at the columns on that edge:
  ground beams (GB) at ±0.00, floor beams (B) at upper levels, roof beams
  (RB) at the top;
- one slab per room (S1 on the ground, S2 above), walls optional;
- the roof covers the top floor's bounding rectangle (+ overhang): gable
  (จั่ว) or hip (ปั้นหยา), with ridge, hips, rafters, purlins, king posts
  and a roof skin whose area the takeoff bills.

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
    "post": "C 100×50×20×2.3", "skin": True,
}


def default_data() -> dict:
    return {"floors": [{"rooms": []}], "settings": dict(DEFAULT_SETTINGS)}


def settings_of(data) -> dict:
    s = dict(DEFAULT_SETTINGS)
    s.update((data or {}).get("settings") or {})
    return s


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
    """The concrete frame (+ walls) as groups, and a count per kind."""
    s = settings_of(data)
    floors = [f.get("rooms") or [] for f in data.get("floors", [])]
    while floors and not floors[-1]:
        floors.pop()
    out, count = [], {}

    def add(g, kind):
        if g is not None:
            out.append(g)
            count[kind] = count.get(kind, 0) + 1

    if not floors or not floors[0]:
        return out, count
    H = float(s["floor_h"])
    n = len(floors)
    base = -float(s["footing_depth"])
    ft = float(s["footing_t"])
    fw = _mm(s["footing_w"])
    st, col = _mm(s["stump"]), _mm(s["col"])
    for (x, y) in nodes(floors[0]):
        add(_member("structure", "footing", "F1", "rect", dict(b=fw, h=fw),
                    [(x, y, base), (x, y, base + ft)], ifc="IfcFooting"),
            "footing")
        add(_member("structure", "stump", "PC1", "rect", dict(b=st, h=st),
                    [(x, y, base + ft), (x, y, 0.0)], ifc="IfcColumn"),
            "stump")
    for k, rooms in enumerate(floors):
        z0, z1 = k * H, (k + 1) * H
        for (x, y) in nodes(rooms):
            add(_member("structure", "column", "C1", "rect",
                        dict(b=col, h=col), [(x, y, z0), (x, y, z1)],
                        ifc="IfcColumn"), "column")
    # Beams per level: the rooms below and above that level share them.
    for lvl in range(n + 1):
        z = lvl * H
        rooms = []
        if lvl < n:
            rooms += floors[lvl]
        if lvl > 0:
            rooms += floors[lvl - 1]
        if lvl == 0:
            mark, b, h = "GB1", s["gb_b"], s["gb_h"]
        elif lvl == n:
            mark, b, h = "RB1", s["rb_b"], s["rb_h"]
        else:
            mark, b, h = "B1", s["b_b"], s["b_h"]
        for p0, p1 in segments(rooms):
            add(_member("structure", "beam", mark, "rect",
                        dict(b=_mm(b), h=_mm(h)),
                        [(p0[0], p0[1], z), (p1[0], p1[1], z)], anchor="tc",
                        ifc="IfcBeam"), "beam")
    t = float(s["slab_t"])
    for k, rooms in enumerate(floors):
        z = k * H
        mark = "S1" if k == 0 else "S2"
        for rm in rooms:
            cx = float(rm["x"]) + float(rm["w"]) / 2
            cy = float(rm["y"]) + float(rm["d"]) / 2
            add(_member("structure", "slab", mark, "rect",
                        dict(b=_mm(rm["w"]), h=_mm(rm["d"])),
                        [(cx, cy, z - t), (cx, cy, z)], ifc="IfcSlab"),
                "slab")
    if s.get("walls"):
        wt = _mm(s["wall_t"])
        half = float(s["col"]) / 2
        for k, rooms in enumerate(floors):
            z0 = k * H
            above_h = s["rb_h"] if k == n - 1 else s["b_h"]
            wh = H - float(above_h)
            if wh <= 0.05:
                continue
            for p0, p1 in segments(rooms):
                dx, dy = p1[0] - p0[0], p1[1] - p0[1]
                L = math.hypot(dx, dy)
                if L <= 2 * half + 0.05:
                    continue
                ux, uy = dx / L, dy / L
                a = (p0[0] + ux * half, p0[1] + uy * half, z0)
                b = (p1[0] - ux * half, p1[1] - uy * half, z0)
                add(_member("structure", "wall", "ผนังก่ออิฐ", "rect",
                            dict(b=wt, h=_mm(wh)), [a, b], anchor="bc",
                            ifc="IfcWall"), "wall")
    return out, count


def roof_lines(data):
    """The roof frame as lines: {"ridge": [...], "hip": [...], "rafter":
    [...], "purlin": [paths…], "post": [...], "skin": [polygons…]} — each
    a list of 3D points (metres). None when there is no roof to make."""
    s = settings_of(data)
    floors = [f.get("rooms") or [] for f in data.get("floors", [])]
    floors = [f for f in floors if f]
    if not floors or s.get("roof") not in ("hip", "gable"):
        return None
    fp = footprint(floors[-1])
    H = float(s["floor_h"])
    z0 = len([f for f in data.get("floors", [])
              if f.get("rooms")]) * H
    ov = float(s["overhang"])
    tan = math.tan(math.radians(float(s["pitch"])))
    x0, y0, x1, y1 = fp[0] - ov, fp[1] - ov, fp[2] + ov, fp[3] + ov
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
    # Rafters on the two long slopes, at spacing along the eave.
    sp = max(float(s["rafter_sp"]), 0.2)
    count = max(int(math.floor(L / sp + 1e-9)), 1)
    xs = [x0 + L * i / count for i in range(count + 1)]
    for x in xs:
        reach = half
        if hip:
            reach = min(half, x - x0, x1 - x)
        if reach <= 0.05:
            continue
        for side in (0, 1):
            ye = y0 if side == 0 else y1
            yt = ye + reach if side == 0 else ye - reach
            out["rafter"].append([P3(x, ye, h(0)), P3(x, yt, h(reach))])
    if hip:                                  # jack rafters on the ends
        cnt = max(int(math.floor(W / sp + 1e-9)), 1)
        for i in range(cnt + 1):
            y = y0 + W * i / cnt
            reach = min(half, y - y0, y1 - y)
            if reach <= 0.05:
                continue
            out["rafter"].append([P3(x0, y, h(0)), P3(x0 + reach, y, h(reach))])
            out["rafter"].append([P3(x1, y, h(0)), P3(x1 - reach, y, h(reach))])
    # Purlins at spacing up the slope (horizontal distance = slope × cos).
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
    # King posts (ดั้ง) under the ridge ends, from the roof beam.
    if zr - z0 > 0.1:
        for xx in ((rx0, rx1) if rx1 - rx0 > 1e-6 else (rx0,)):
            out["post"].append([P3(xx, yc, z0), P3(xx, yc, zr)])
    # The skin: one polygon per slope.
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
    out["z0"], out["swap"] = z0, swap
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


KIND_TH = [("footing", "ฐานราก"), ("stump", "ตอม่อ"), ("column", "เสา"),
           ("beam", "คาน"), ("slab", "พื้น"), ("wall", "ผนัง"),
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
