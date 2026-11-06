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
    # ระดับพื้นชั้น 1 สูงจากดินเดิม (ม.): ใต้คานคอดินเหลือช่องเดินท่อประปา
    # และท่อน้ำทิ้ง (ใต้ถุน) — ท่อไม่ฝังในคาน
    "floor_lift": 0.60,
    "stump": 0.2, "col": 0.2,
    "gb_b": 0.2, "gb_h": 0.4, "b_b": 0.2, "b_h": 0.4,
    "rb_b": 0.2, "rb_h": 0.4, "slab_t": 0.10,
    "walls": True, "wall_t": 0.10,
    "roof": "hip", "pitch": 30.0, "overhang": 0.6,
    "rafter_sp": 1.0, "purlin_sp": 0.32,
    "ridge": "C 150×65×20×3.2", "hip": "C 150×65×20×3.2",
    "rafter": "C 150×65×20×3.2", "purlin": "C 75×45×15×2.3",
    "post": "C 100×50×20×2.3", "skin": True, "roof_mode": "plan",
    "door_w": 0.9, "door_h": 2.0, "win_w": 1.2, "win_h": 1.1,
    "win_sill": 0.9, "stair_w": 1.0, "riser_max": 0.18, "going": 0.25,
    "stair_t": 0.15, "fascia": True, "fascia_h": 0.20, "fascia_t": 0.025,
    "gutters": True,
    "band": 0.10, "tile": "R1", "tiles_m2": 0.0, "caps": True,
    "tile_color": "ตามวัสดุ", "tiles_3d": True,
    # wet rooms sit lower than the floor they open onto (water stays in)
    "wet_drop": 0.05,
    # eave soffit (ฝ้าชายคา): planks on a galvanised steel frame
    "soffit": True, "soffit_sp": 0.60,
    # walls (มยผ. 1301/1302, วสท.): masonry by สูตรวัสดุ หมวด 6, plaster
    # 1.5 ซม. each side (สูตร 7.2), exterior walls flush with the outer face
    # of the columns, interior walls on the grid line
    "ext_wall": "6.1", "int_wall": "6.1", "plaster_t": 0.015,
    "ext_plaster_t": 0.015, "plaster_3d": True, "wall_flush": True,
    # layers: every generated part on a layer of its own name ("name"),
    # one per type and size ("type"), per type and floor ("floor") or per
    # work category ("category"); "" leaves them on the default layer
    "layer_mode": "name",
    # doors and windows: three places per span (middle, 25 cm off either
    # column), window heads level with the door heads
    "head_h": 2.0, "slot_snap": True,
    # interior ceilings (ฝ้าภายใน): "cline" ยิปซัมฉาบเรียบ โครงซีลาย, "tbar",
    # "none"; wet rooms take fibre-cement on T-bar. Skirting / cornice on
    # request (ปุ่มบัวผนัง)
    "ceiling_type": "cline", "skirting": False, "skirting_type": "ceramic",
    "cornice": False,
    # services by the rooms (ไฟฟ้า ปรับอากาศ สุขาภิบาล ภายนอก)
    "mep": True,
    # roof frame by the tile maker and the usual steel-roof practice:
    # purlins at the tile's batten gauge (ระยะแป = ระยะซ้อนทับที่ผู้ผลิตกำหนด,
    # CPAC 32 ซม.), rafters at most the spacing the tile weight allows, a
    # steel wall plate (อะเส) on the ring beams and a tie beam (ขื่อ/คานรับดั้ง)
    # under every king post (ดั้ง)
    # the spacings set on the panel are the most allowed: a span that does
    # not divide is shared out evenly a little closer (1.00 → 0.98 …)
    "purlin_auto": False, "rafter_auto": False, "purlin_face": "ridge",
    "wall_plate": True, "wallplate": "C 150×65×20×3.2",
    "tie_beams": True, "tiebeam": "C 150×65×20×3.2",
    # column-head plate (เพลทหัวเสา) for the wall plate / tie beams:
    # PL 200×200×9 มม. on 4 J-bolts DB12 cast 0.60 ม. into the column
    "head_plate": True,
    # struts (ตุ๊กตา) and braces (ค้ำยัน) of the king-post trusses
    "struts": True, "strut": "C 100×50×20×2.3", "hip_cap_out": 0.10,
    "truss": "kingpost", "manila_f": 0.5,
    # วางเดี่ยว / วางคู่ (two C back to back) for อกไก่ ตะเฆ่สัน ตะเฆ่ราง ดั้ง อะเส
    "dbl_ridge": False, "dbl_hip": False, "dbl_valley": False, "dbl_post": False,
    "dbl_wallplate": False,
    # outside: the walkway (ทางเท้า) from the outer face, the drain ring
    # (ท่อระบายน้ำ) this far out from the building
    "walk_w": 1.0, "drain_off": 1.5,
}

#: เพลทหัวเสา: กว้าง ยาว หนา (ม.), เหล็ก J-bolt (ขนาด, จำนวน, ฝังลึก ม., ขอ ม., โผล่ ม.)
HEAD_PLATE = {"b": 0.20, "t": 0.009, "bolt": "DB12", "n": 4, "embed": 0.60,
              "hook": 0.08, "stick": 0.05, "edge": 0.05}


def head_plate_kg() -> tuple:
    """(plate kg, J-bolt kg) of one column head."""
    hp = HEAD_PLATE
    plate = hp["b"] * hp["b"] * hp["t"] * 7850.0
    bolt = hp["n"] * (hp["embed"] + hp["hook"] + hp["stick"]) * 0.888
    return plate, bolt


def head_plate(x, y, z):
    """A column-head plate and its four J-bolts at the column (x, y), the
    plate's top at ``z`` (the top of the ring beam)."""
    hp = HEAD_PLATE
    bx = _Boxes((x, y), (1.0, 0.0), z)
    b, t, r = hp["b"] / 2, hp["t"], 0.006
    steel = _paint("metal")
    bx.box(-b, b, -b, b, -t, 0.0, steel)
    e = b - hp["edge"]
    for sx in (-e, e):
        for sy in (-e, e):
            bx.box(sx - r, sx + r, sy - r, sy + r, -hp["embed"], hp["stick"], steel)
            # the J: a hook turned in towards the column centre
            hx = -hp["hook"] if sx > 0 else hp["hook"]
            lo, hi = sorted((sx, sx + hx))
            bx.box(lo, hi, sy - r, sy + r, -hp["embed"], -hp["embed"] + 2 * r, steel)
    pk, bk = head_plate_kg()
    g = bx.group(f"เพลทหัวเสา PL {hp['b'] * 1000:.0f}×{hp['b'] * 1000:.0f}×"
                 f"{t * 1000:.0f} มม. + J-bolt {hp['n']}-{hp['bolt']}",
                 "roof", "headplate", "เพลทหัวเสา", "IfcPlate")
    if g is not None:
        rec = g.ext[EXT_KEY]
        rec["info"] = [["ชนิด", "เพลทหัวเสา ยึดอะเส/ขื่อกับเสา ค.ส.ล."],
                       ["แผ่นเหล็ก", f"{hp['b'] * 1000:.0f}×{hp['b'] * 1000:.0f}×"
                                    f"{t * 1000:.0f} มม. ({pk:.2f} กก.)"],
                       ["J-bolt", f"{hp['n']}-{hp['bolt']} ฝังในเสา {hp['embed']:.2f} ม. "
                                  f"งอขอ {hp['hook'] * 100:.0f} ซม. ({bk:.2f} กก.)"],
                       ["ตำแหน่ง", f"x {x:.2f} y {y:.2f} ระดับ {z:.2f} ม."],
                       ["รายการ BOQ", "หมวด 5 งานโครงสร้างเหล็ก"]]
    return g

#: ระยะจันทันสูงสุด (ม.) ตามน้ำหนักวัสดุมุง: กระเบื้องคอนกรีต/ดินเผา 1.00,
#: ไฟเบอร์ซีเมนต์ 1.20, เหล็กรีดลอน 1.50 — ใช้กับแป C 75×45×15×2.3
RAFTER_MAX = {"concrete": 1.00, "ceramic": 1.00, "fibre": 1.20, "metal": 1.50}


def tile_family(code: str) -> str:
    from core.wanic_catalog import ROOF_TILES
    name = (ROOF_TILES.get(code) or {}).get("name", "")
    if "เหล็ก" in name or "Metal" in name:
        return "metal"
    if "ไฟเบอร์" in name or "ลอน" in name and "คอนกรีต" not in name:
        return "fibre"
    if "ดินเผา" in name or "เซรามิค" in name:
        return "ceramic"
    return "concrete"


def roof_spacing(s) -> tuple:
    """(rafter spacing, purlin spacing along the slope) in metres: the
    set values, or — with ``rafter_auto`` / ``purlin_auto`` — the tile's
    batten gauge (its effective length, ``eff`` of the catalog) and the
    largest rafter spacing its weight allows (:data:`RAFTER_MAX`)."""
    from core.wanic_catalog import ROOF_TILES
    tile = ROOF_TILES.get(s.get("tile")) or {}
    rsp = max(float(s["rafter_sp"]), 0.2)
    psp = max(float(s["purlin_sp"]), 0.1)
    if s.get("purlin_auto") and tile.get("eff"):
        psp = float(tile["eff"][1])
    if s.get("rafter_auto"):
        rsp = RAFTER_MAX[tile_family(s.get("tile"))]
    return rsp, psp

#: สูตรวัสดุงานก่อผนัง (หลักเกณฑ์ 2569 หมวด 6) → (ชื่อ, ความหนาเนื้อผนัง ม.)
WALL_TYPES = {
    "6.1": ("ผนังก่ออิฐมอญครึ่งแผ่น", 0.07),
    "6.2": ("ผนังก่ออิฐมอญเต็มแผ่น", 0.16),
    "6.3": ("ผนังก่ออิฐกลวงครึ่งแผ่น", 0.11),
    "6.4": ("ผนังก่ออิฐกลวงเต็มแผ่น", 0.25),
    "6.5": ("ผนังก่ออิฐทนไฟครึ่งแผ่น", 0.11),
    "6.6": ("ผนังก่อคอนกรีตบล็อก 7 ซม.", 0.07),
    "6.7": ("ผนังก่อคอนกรีตบล็อก 9 ซม.", 0.09),
    "6.8": ("ผนังก่อคอนกรีตบล็อกช่องลม 9 ซม.", 0.09),
    "6.10": ("ผนังก่ออิฐมวลเบา 7.5 ซม.", 0.075),
    "6.11": ("ผนังก่ออิฐมวลเบา 10 ซม.", 0.10),
    "6.12": ("ผนังก่ออิฐมวลเบา 12.5 ซม.", 0.125),
    "6.13": ("ผนังก่ออิฐมวลเบา 15 ซม.", 0.15),
    "6.14": ("ผนังก่ออิฐมวลเบา 20 ซม.", 0.20),
    "6.15": ("ผนังก่อบล็อกแก้ว 8 ซม.", 0.08),
}
#: ความหนาปูนฉาบที่เลือกได้ (ม.)
PLASTER_T = (0.010, 0.0125, 0.015, 0.020, 0.025)


def wall_spec(s, exterior: bool) -> dict:
    """Masonry recipe, name, masonry thickness ``t``, plaster thickness
    inside ``pi`` and outside ``po`` and the finished thickness ``T`` of an
    exterior or interior wall."""
    code = str(s.get("ext_wall" if exterior else "int_wall") or "6.1")
    if code not in WALL_TYPES:
        code = "6.1"
    name, t = WALL_TYPES[code]
    pi = max(float(s.get("plaster_t") or 0.0), 0.0)
    po = max(float(s.get("ext_plaster_t") or pi), 0.0) if exterior else pi
    return {"recipe": code, "name": name, "t": t, "pi": pi, "po": po,
            "T": t + pi + po, "exterior": exterior}

#: Rooms whose floor is set down ``wet_drop`` (ห้องน้ำ ห้องส้วม ห้องอาบน้ำ…).
WET_WORDS = ("ห้องน้ำ", "ห้องส้วม", "ส้วม", "สุขา", "ห้องอาบน้ำ", "อาบน้ำ",
             "wc", "toilet", "bath")


def is_wet(room) -> bool:
    name = str((room or {}).get("name") or "").lower()
    return any(w in name for w in WET_WORDS)


def room_at(rooms, x, y):
    """The room whose rectangle holds the point (the smallest one)."""
    best = None
    for rm in rooms:
        if float(rm["x"]) - 1e-6 <= x <= float(rm["x"]) + float(rm["w"]) + 1e-6 \
                and float(rm["y"]) - 1e-6 <= y <= float(rm["y"]) + float(rm["d"]) + 1e-6:
            if best is None or float(rm["w"]) * float(rm["d"]) < \
                    float(best["w"]) * float(best["d"]):
                best = rm
    return best


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


def slab_mark(lib, room, floor, raised=False) -> str:
    """The room's slab; by default the ground floor lies on the ground
    (S1) unless the building is raised off it (then on the beams, S2)."""
    m = room.get("slab")
    if m in lib and lib[m].get("kind") == "slab":
        return m
    return ROLE_DEFAULT["S1" if floor == 0 and not raised else "S2"]


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
    gl = -floor_lift(s)
    E["GL"] = gl
    for (x, y) in sorted(ground):
        fm = node_mark(data, lib, x, y, "F")
        f = lib[fm]
        base = gl - float(f["depth"])
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
    drop = max(float(s.get("wet_drop") or 0.0), 0.0)
    for k, rooms in enumerate(rooms_of):
        for rm in rooms:
            E["slabs"].append({"mark": slab_mark(lib, rm, k, floor_lift(s) >= 0.30),
                               "room": rm,
                               "floor": k, "z": k * H,
                               "drop": drop if is_wet(rm) else 0.0})
    for k, f in enumerate(floors):
        for p0, p1 in segments(f["rooms"]):
            mx, my = (p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2
            sides = sum(1 for rm in f["rooms"] if _on_edge(rm, mx, my))
            above = beam_at.get((k + 1, p0, p1)) or ROLE_DEFAULT[
                "RB" if k == n - 1 else "B"]
            L = math.hypot(p1[0] - p0[0], p1[1] - p0[1])
            out = (0.0, 0.0)
            if sides <= 1 and L > 1e-9:
                nx, ny = -(p1[1] - p0[1]) / L, (p1[0] - p0[0]) / L
                eps = 0.05
                inside = room_at(f["rooms"], mx + nx * eps, my + ny * eps)
                out = (-nx, -ny) if inside is not None else (nx, ny)
            E["walls"].append({
                "floor": k, "p0": p0, "p1": p1, "L": L, "out": out,
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


def outline_segments(rooms) -> list:
    """The plan's outer edges (the exterior walls / ring beams): segments
    on the edge of only one room."""
    out = []
    for p0, p1 in segments(rooms):
        mx, my = (p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2
        if sum(1 for rm in rooms if _on_edge(rm, mx, my)) <= 1:
            out.append((p0, p1))
    return out


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


#: ระยะจากผิวเสาถึงขอบวงกบ เมื่อวางประตู/หน้าต่างชิดเสา (ม.)
SLOT_GAP = 0.25


def opening_slots(p0, p1, w, col_b, gap=SLOT_GAP) -> list:
    """The three places a door or window may stand on a span (distance of
    its centre from p0): the middle, and next to either column with
    ``gap`` between the column face and the frame — the tidy elevation
    every opening of the plan shares. A span too short for a side slot
    has the middle only."""
    L = math.dist(p0, p1)
    mid = L / 2
    left = col_b / 2 + gap + w / 2
    right = L - col_b / 2 - gap - w / 2
    out = [mid]
    if right - left > w + 0.10 and left < mid - 0.05:
        out = [left, mid, right]
    return out


def snap_opening(x, y, w, segs, col_b, gap=SLOT_GAP, reach=0.4):
    """``(px, py, (p0, p1))``: the slot of :func:`opening_slots` nearest
    the click on the nearest span, or ``None``."""
    hit = snap_to_segment(x, y, segs, reach)
    if hit is None:
        return None
    px, py, (p0, p1) = hit
    L = math.dist(p0, p1)
    if L < 1e-9:
        return None
    s_ = math.dist(p0, (px, py))
    best = min(opening_slots(p0, p1, w, col_b, gap), key=lambda c: abs(c - s_))
    ux, uy = (p1[0] - p0[0]) / L, (p1[1] - p0[1]) / L
    return (_r(p0[0] + ux * best), _r(p0[1] + uy * best), (p0, p1))


def window_sill(s, h) -> float:
    """A window's sill so its head lines up with the door heads
    (``head_h``, 2.00 ม.) — the usual rule of the standard drawings."""
    return round(max(float(s.get("head_h", 2.0)) - float(h), 0.30), 3)


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
        dsill = window_sill(s, float(op.get("h") or dh)) if styled else s["win_sill"]
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

def _tag(g, part, kind, mark, info=None, key=None):
    """Mark a generated group: what made it (part, kind, mark), the short
    ``key`` the takeoff's price lines match (the mark, or e.g. «อกไก่
    C 150×65×20×3.2» — the name members used to carry), and the
    ``info`` rows the Properties panel shows."""
    ext = dict(g.ext or {})
    ext[EXT_KEY] = {"part": part, "kind": kind, "mark": mark,
                    "key": key or mark}
    if info:
        ext[EXT_KEY]["info"] = [[str(k), str(v)] for k, v in info]
    g.ext = ext
    return g


def axis_name(i: int) -> str:
    letters = "ABCDEFGHJKLMNPQRSTUVWXYZ"
    return letters[i] if i < len(letters) else f"A{i - len(letters) + 1}"


class Grid:
    """Grid names of the plan (1, 2, 3 … along x; A, B, C … along y), as on
    the plan and the drawings, to say where a member is."""

    def __init__(self, E):
        self.xs = sorted({round(c["x"], 3) for c in E["footings"]})
        self.ys = sorted({round(c["y"], 3) for c in E["footings"]})

    def _near(self, vals, v, name):
        for i, g in enumerate(vals):
            if abs(g - v) < 1e-3:
                return name(i)
        for i in range(len(vals) - 1):                # between two lines
            if vals[i] < v < vals[i + 1]:
                return f"{name(i)}/{name(i + 1)}"
        return f"{v:.2f}"

    def col(self, x):
        return self._near(self.xs, x, lambda i: str(i + 1))

    def row(self, y):
        return self._near(self.ys, y, axis_name)

    def point(self, x, y) -> str:
        return f"{self.row(y)}-{self.col(x)}"

    def span(self, p0, p1) -> str:
        if abs(p0[1] - p1[1]) < 1e-6:                 # along x: on a row line
            a, b = sorted((p0[0], p1[0]))
            return f"แนว {self.row(p0[1])} ({self.col(a)}–{self.col(b)})"
        a, b = sorted((p0[1], p1[1]))
        return f"แนว {self.col(p0[0])} ({self.row(a)}–{self.row(b)})"

    def area(self, rm) -> str:
        x0, y0 = float(rm["x"]), float(rm["y"])
        x1, y1 = x0 + float(rm["w"]), y0 + float(rm["d"])
        return f"{self.row(y0)}–{self.row(y1)} / {self.col(x0)}–{self.col(x1)}"


def _cm(v) -> str:
    return f"{float(v) * 100:g}"


def _floor_name(k) -> str:
    return f"ชั้น {int(k) + 1}"


#: the roof forms (แบบหลังคา) most built in Thailand
ROOF_TYPES = {"hip": "ปั้นหยา", "gable": "จั่ว",
              "manila": "มะนิลา (ปั้นหยาผสมจั่ว)", "shed": "เพิงหมาแหงน (ลาดเดียว)"}

#: the truss forms (แบบโครงถัก) the roof frame can be made as
TRUSS_TYPES = {"kingpost": "ดั้งกลาง + ตุ๊กตา + ค้ำยัน (King Post)",
               "howe": "Howe — ตุ๊กตาทุกช่วง ค้ำยันเอียงเข้าหาดั้ง",
               "pratt": "Pratt — ตุ๊กตาทุกช่วง ค้ำยันเอียงออกหาผนัง",
               "fink": "Fink (W) — ค้ำยันรูปตัว W ไม่มีตุ๊กตา"}

#: members that can be laid single or double (two C back to back)
DOUBLE_KINDS = ("ridge", "hip", "post", "wallplate")


def _member(part, kind, mark, family, params, path, anchor="c", ifc="",
            name=None, closed=False, offset=(0.0, 0.0), info=None, key=None,
            rotation=0.0, mirror=False):
    g = P.build_member({"family": family, "params": params, "path": path,
                        "anchor": anchor, "ifc": ifc, "name": name or mark,
                        "closed": closed, "offset": offset,
                        "rotation": rotation, "mirror": mirror})
    if isinstance(g, str):
        return None
    return _tag(g, part, kind, mark, info, key)


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
    G = Grid(E)
    for e in E["footings"]:
        f = lib[e["mark"]]
        w, l, t = float(f["w"]), float(f["l"]), float(f["t"])
        add(_member("structure", "footing", e["mark"], "rect",
                    dict(b=_mm(w), h=_mm(l)),
                    [(e["x"], e["y"], e["z0"]), (e["x"], e["y"], e["z1"])],
                    ifc="IfcFooting",
                    name=f"ฐานราก {e['mark']} {_cm(w)}×{_cm(l)}×{_cm(t)} ซม. · "
                         f"{G.point(e['x'], e['y'])}",
                    info=[("ชนิด", "ฐานราก ค.ส.ล."), ("เบอร์", e["mark"]),
                          ("ขนาด", f"{w:.2f} × {l:.2f} × {t:.2f} ม."),
                          ("ตำแหน่ง", G.point(e["x"], e["y"])),
                          ("ระดับใต้ฐาน", f"{e['z0']:+.2f} ม."),
                          ("เหล็กเสริม", f.get("bars", "")),
                          ("คอนกรีต", f"{w * l * t:.3f} ลบ.ม."),
                          ("รายการ BOQ", "งานคอนกรีตโครงสร้าง (ฐานราก)")]),
            "footing")
        for px, py in pile_points(f, e["x"], e["y"]):
            pb = _mm(f.get("pile_b") or 0.18)
            pl = float(f.get("pile_len") or 6.0)
            add(_member("structure", "pile", "เสาเข็ม", "rect",
                        dict(b=pb, h=pb),
                        [(px, py, e["z0"] - pl), (px, py, e["z0"])],
                        ifc="IfcPile",
                        name=f"เสาเข็ม {pb / 10:g}×{pb / 10:g} ซม. ยาว {pl:g} ม. · "
                             f"ฐาน {e['mark']} {G.point(e['x'], e['y'])}",
                        info=[("ชนิด", "เสาเข็ม"), ("ขนาด", f"{pb / 10:g}×{pb / 10:g} ซม."),
                              ("ความยาว", f"{pl:g} ม."),
                              ("ใต้ฐานราก", f"{e['mark']} {G.point(e['x'], e['y'])}")]),
                "pile")
    for e in E["stumps"]:
        c = lib[e["mark"]]
        b, h = float(c["b"]), float(c["h"])
        L = e["z1"] - e["z0"]
        add(_member("structure", "stump", e["mark"], "rect",
                    dict(b=_mm(b), h=_mm(h)),
                    [(e["x"], e["y"], e["z0"]), (e["x"], e["y"], e["z1"])],
                    ifc="IfcColumn",
                    name=f"เสาตอม่อ {e['mark']} {_cm(b)}×{_cm(h)} ซม. · "
                         f"{G.point(e['x'], e['y'])}",
                    info=[("ชนิด", "เสาตอม่อ ค.ส.ล."), ("เบอร์", e["mark"]),
                          ("ขนาด", f"{b:.2f} × {h:.2f} ม. สูง {L:.2f} ม."),
                          ("ตำแหน่ง", G.point(e["x"], e["y"])),
                          ("เหล็กยืน / ปลอก", f"{c.get('main', '')} / {c.get('tie', '')}"),
                          ("คอนกรีต", f"{b * h * L:.3f} ลบ.ม."),
                          ("รายการ BOQ", "งานคอนกรีตโครงสร้าง (เสาตอม่อ)")]),
            "stump")
    for e in E["columns"]:
        c = lib[e["mark"]]
        b, h = float(c["b"]), float(c["h"])
        L = e["z1"] - e["z0"]
        add(_member("structure", "column", e["mark"], "rect",
                    dict(b=_mm(b), h=_mm(h)),
                    [(e["x"], e["y"], e["z0"]), (e["x"], e["y"], e["z1"])],
                    ifc="IfcColumn",
                    name=f"เสา {e['mark']} {_cm(b)}×{_cm(h)} ซม. · "
                         f"{_floor_name(e['floor'])} · {G.point(e['x'], e['y'])}",
                    info=[("ชนิด", "เสา ค.ส.ล."), ("เบอร์", e["mark"]),
                          ("ขนาด", f"{b:.2f} × {h:.2f} ม. สูง {L:.2f} ม."),
                          ("ชั้น", _floor_name(e["floor"])),
                          ("ตำแหน่ง", G.point(e["x"], e["y"])),
                          ("เหล็กยืน / ปลอก", f"{c.get('main', '')} / {c.get('tie', '')}"),
                          ("คอนกรีต", f"{b * h * L:.3f} ลบ.ม."),
                          ("รายการ BOQ", "งานคอนกรีตโครงสร้าง (เสา)")]),
            "column")
    # Beams run between the faces of the columns (stumps at the ground
    # beams) they frame into, not through them: no two solids overlap.
    half_at = {}
    for e in E["stumps"]:
        c = lib[e["mark"]]
        half_at[(0, round(e["x"], 6), round(e["y"], 6))] = (float(c["b"]) / 2,
                                                            float(c["h"]) / 2)
    for e in E["columns"]:
        c = lib[e["mark"]]
        hb = (float(c["b"]) / 2, float(c["h"]) / 2)
        for lvl in (e["floor"] + 1, e["floor"]):       # the column below wins
            half_at.setdefault((lvl, round(e["x"], 6), round(e["y"], 6)), hb)
        half_at[(e["floor"] + 1, round(e["x"], 6), round(e["y"], 6))] = hb
    for e in E["beams"]:
        b = lib[e["mark"]]
        p0, p1, z = e["p0"], e["p1"], e["z"]
        L = math.hypot(p1[0] - p0[0], p1[1] - p0[1])
        if L < 1e-6:
            continue
        ux, uy = (p1[0] - p0[0]) / L, (p1[1] - p0[1]) / L

        def cut(p):
            hb = half_at.get((e["level"], round(p[0], 6), round(p[1], 6)))
            return 0.0 if hb is None else abs(ux) * hb[0] + abs(uy) * hb[1]
        a, c_ = cut(p0), cut(p1)
        if L - a - c_ < 0.02:
            continue
        q0 = (p0[0] + ux * a, p0[1] + uy * a)
        q1 = (p1[0] - ux * c_, p1[1] - uy * c_)
        bw, bh = float(b["b"]), float(b["h"])
        kind_th = ("คานคอดิน" if e["ground"] else "คานหลังคา" if e["roof"]
                   else "คาน")
        where = G.span(p0, p1)
        add(_member("structure", "beam", e["mark"], "rect",
                    dict(b=_mm(bw), h=_mm(bh)),
                    [(q0[0], q0[1], z), (q1[0], q1[1], z)], anchor="tc",
                    ifc="IfcBeam",
                    name=f"{kind_th} {e['mark']} {_cm(bw)}×{_cm(bh)} ซม. · "
                         f"ระดับ {z:+.2f} · {where}",
                    info=[("ชนิด", f"{kind_th} ค.ส.ล."), ("เบอร์", e["mark"]),
                          ("ขนาด", f"{bw:.2f} × {bh:.2f} ม."),
                          ("ระดับหลังคาน", f"{z:+.2f} ม."),
                          ("ตำแหน่ง", where),
                          ("ช่วงศูนย์กลางเสา", f"{L:.2f} ม."),
                          ("ความยาวสุทธิ (ระหว่างหน้าเสา)", f"{L - a - c_:.2f} ม."),
                          ("เหล็กบน / ล่าง / ปลอก",
                           f"{b.get('top', '')} / {b.get('bot', '')} / {b.get('stir', '')}"),
                          ("คอนกรีต", f"{bw * bh * (L - a - c_):.3f} ลบ.ม."),
                          ("รายการ BOQ", "งานคอนกรีตโครงสร้าง (คาน)")]), "beam")
    # Slabs sit inside the beams round them (between the beam faces), a wet
    # room's ``wet_drop`` lower than the floor next to it.
    bw_at = {}
    for e in E["beams"]:
        bw_at[e["level"]] = max(bw_at.get(e["level"], 0.0),
                                float(lib[e["mark"]]["b"]))
    for e in E["slabs"]:
        rm, t = e["room"], float(lib[e["mark"]]["t"])
        inset = bw_at.get(e["floor"], 0.0)
        w = max(float(rm["w"]) - inset, 0.05)
        d = max(float(rm["d"]) - inset, 0.05)
        cx = float(rm["x"]) + float(rm["w"]) / 2
        cy = float(rm["y"]) + float(rm["d"]) / 2
        top = e["z"] - float(e.get("drop") or 0.0)
        rname = rm.get("name") or "ห้อง"
        info = [("ชนิด", "พื้น ค.ส.ล."), ("เบอร์", e["mark"]),
                ("ห้อง", rname), ("ชั้น", _floor_name(e["floor"])),
                ("ตำแหน่ง", G.area(rm)),
                ("ขนาดห้อง", f"{float(rm['w']):.2f} × {float(rm['d']):.2f} ม. หนา {t:.2f} ม."),
                ("ระดับผิวพื้นโครงสร้าง", f"{top:+.3f} ม."),
                ("เหล็กเสริม", lib[e["mark"]].get("bars", "")),
                ("คอนกรีต", f"{float(rm['w']) * float(rm['d']) * t:.3f} ลบ.ม."),
                ("รายการ BOQ", "งานคอนกรีตโครงสร้าง (พื้น)")]
        if e.get("drop"):
            info.insert(7, ("พื้นห้องเปียก", f"ต่ำกว่าพื้นข้างเคียง {e['drop'] * 100:g} ซม."))
        add(_member("structure", "slab", e["mark"], "rect",
                    dict(b=_mm(w), h=_mm(d)),
                    [(cx, cy, top - t), (cx, cy, top)], ifc="IfcSlab",
                    name=f"พื้น {e['mark']} หนา {_cm(t)} ซม. · {rname} · "
                         f"{_floor_name(e['floor'])} · {G.area(rm)}",
                    info=info), "slab")
    if s.get("walls"):
        _walls(E, add)
    for e in E["stairs"]:
        add(stair_member(e["st"], s, e["floor"] * E["H"]), "stair")
    rooms_of = [f["rooms"] for f in E["floors"]]
    drop = max(float(s.get("wet_drop") or 0.0), 0.0)
    for e in E["fixtures"]:
        fx = e["fx"]
        rm = room_at(rooms_of[e["floor"]], float(fx["x"]), float(fx["y"]))
        z = e["floor"] * E["H"] - (drop if is_wet(rm) else 0.0)
        add(fixture_member(fx, z, rm), "fixture")
    if s.get("ceiling_type", "cline") != "none":
        for g, kind in ceiling_members(E, data):
            add(g, kind)
    if s.get("skirting") or s.get("cornice"):
        for g, kind in trim_members(E):
            add(g, kind)
    try:
        from core import wanic_mep
        for g, kind in wanic_mep.members(data, E):
            add(g, kind)
    except ImportError:                                 # pragma: no cover
        pass
    return out, count


# ---------------------------------------------------------------------------
# Ceilings (ฝ้าเพดาน), skirting (บัวเชิงผนัง) and cornice (บัวฝ้า)
# ---------------------------------------------------------------------------

#: ชนิดฝ้าภายใน: (ชื่อ, ว480, โครง, ระยะโครงซอย, ระยะโครงหลัก/ลวดแขวน)
CEILING_TYPES = {
    "cline": ("ฝ้ายิปซัมบอร์ด 9 มม. ฉาบรอยต่อเรียบ โครงคร่าวเหล็กชุบสังกะสี (ซีลาย)",
              "2.2.3", "C-line", 0.40, 1.20),
    "tbar": ("ฝ้ายิปซัมบอร์ด 9 มม. โครงคร่าว T-bar 0.60×1.20 ม.", "2.2.4", "T-bar",
             0.60, 1.20),
    "fc": ("ฝ้าไฟเบอร์ซีเมนต์ 6 มม. โครงคร่าว T-bar (ห้องเปียก)", "2.2.4", "T-bar",
           0.60, 1.20),
}
SKIRTING_TYPES = {
    "ceramic": ("บัวเชิงผนังกระเบื้องเซรามิค สูง 4\"", "2.4.17", 0.10, 0.012, 51),
    "pvc": ("บัวเชิงผนังสำเร็จรูป (พี วี ซี.) สูง 4\"", "2.4.17", 0.10, 0.010, 41),
    "wood": ("บัวเชิงผนังไม้สำเร็จรูป (ไม้เทียม) สูง 4\"", "2.4.17", 0.10, 0.015, 46),
    "granite": ("บัวเชิงผนังหินแกรนิต สูง 4\" (ลบมุม 45°)", "2.4.17", 0.10, 0.015, 179),
    "cement": ("บัวเชิงผนังผิวซีเมนต์ขัดมันเรียบ สูง 4\"", "2.4.17", 0.10, 0.010, 41),
}
CORNICE = ("บัวฝ้า/ไม้มอบฝ้า สำเร็จรูป (ไม้เทียม) 2\"", "2.2.5b", 0.05, 0.02)


def ceiling_type(s, room) -> str:
    t = s.get("ceiling_type", "cline")
    if t == "none":
        return "none"
    return "fc" if is_wet(room) else t


def ceiling_z(E, k) -> float:
    """Top of a floor's ceiling board: the underside of the beams above."""
    lib, H, n = E["lib"], E["H"], E["n"]
    key = "RB1" if k == n - 1 else "B1"
    return (k + 1) * H - float(lib[key]["h"])


def room_inner(E, rm, k):
    """The room's clear rectangle between the plastered wall faces."""
    s, lib = E["settings"], E["lib"]
    rooms = E["floors"][k]["rooms"]
    x0, y0 = float(rm["x"]), float(rm["y"])
    x1, y1 = x0 + float(rm["w"]), y0 + float(rm["d"])
    half = float(lib["C1"]["b"]) / 2
    se, si = wall_spec(s, True), wall_spec(s, False)
    off = max(half - se["po"] - se["t"] / 2, 0.0) if s.get("wall_flush", True) else 0.0
    ext_in = max(se["t"] / 2 + se["pi"] - off, 0.0)
    int_in = si["t"] / 2 + si["pi"]
    if not s.get("walls", True):
        ext_in = int_in = 0.0

    def inset(mx, my):
        n_ = sum(1 for r in rooms if _on_edge(r, mx, my))
        return ext_in if n_ <= 1 else int_in
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    return (x0 + inset(x0, cy), y0 + inset(cx, y0),
            x1 - inset(x1, cy), y1 - inset(cx, y1))


def sloped_ceiling(E, rm, k, lines):
    """Under a lean-to (เพิงหมาแหงน) the top floor's ceiling follows the
    rafters: the four corners of the board just under the rafters, or None
    when the room is not under one roof plane."""
    s = E["settings"]
    if s.get("roof") != "shed" or k != E["n"] - 1 or not lines or not lines.get("skin"):
        return None
    x0, y0, x1, y1 = room_inner(E, rm, k)
    cosp = math.cos(math.radians(float(s["pitch"]))) or 1.0
    under = _dim(s["rafter"]) / cosp + 0.012
    pts = []
    for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
        z = skin_z(x, y, lines["skin"])
        if z is None:
            return None
        pts.append((x, y, z - under))
    # one plane: the fourth corner on the plane of the first three
    (a, b, c, d) = pts
    if abs((a[2] + c[2]) - (b[2] + d[2])) > 0.02:
        return None
    return pts


def ceiling_members(E, data=None):
    """Every room's ceiling: the board under the beams and its frame — the
    furring channels (โครงซอย), main runners (โครงหลัก), the wall angle
    (ฉากริมผนัง) and the hangers (ลวดแขวน/สตัด) up to the structure.
    Under a lean-to roof the top floor's ceiling slopes with the rafters."""
    s, H = E["settings"], E["H"]
    G = Grid(E)
    out = []
    lines = None
    if data is not None and s.get("roof") == "shed":
        try:
            lines = roof_lines(data)
        except Exception:                               # noqa: BLE001 -- flat as before
            lines = None
    for e in E["slabs"]:
        rm, k = e["room"], e["floor"]
        ct = ceiling_type(s, rm)
        if ct == "none" or not (rm.get("finish") or {}).get("ceiling", True):
            continue
        name, lab, frame, sub, main = CEILING_TYPES[ct]
        x0, y0, x1, y1 = room_inner(E, rm, k)
        if x1 - x0 < 0.3 or y1 - y0 < 0.3:
            continue
        slope = sloped_ceiling(E, rm, k, lines)
        if slope is not None:
            from PySide6.QtGui import QVector3D

            from core.group import Group
            from core.mesh import Mesh
            mesh = Mesh()
            q = [QVector3D(*p_) for p_ in slope]
            _prism(mesh, q, QVector3D(0, 0, -0.009), {"color": (0.96, 0.96, 0.94)})
            g = Group(mesh, name=f"ฝ้าลาดเอียงตามจันทัน · {rm.get('name') or 'ห้อง'}")
            g.ifc = {"class": "IfcCovering", "name": "ฝ้าเพดาน"}
            (a_, b_, c_, d_) = slope
            area = math.dist(a_, b_) * math.dist(b_, c_)
            _tag(g, "structure", "ceiling", "ฝ้าเพดาน",
                 [("ชนิด", f"{name} — ลาดเอียงตามแนวจันทัน ยึดโครงคร่าวใต้จันทัน"),
                  ("ห้อง", rm.get("name") or "ห้อง"), ("ชั้น", _floor_name(k)),
                  ("ระดับฝ้า", f"+{min(p_[2] for p_ in slope) - k * H:.2f} ถึง "
                               f"+{max(p_[2] for p_ in slope) - k * H:.2f} ม. จากพื้น"),
                  ("พื้นที่", f"{area:.2f} ตร.ม. (ตามแนวลาด)"),
                  ("รายการ BOQ", "หมวด 10 งานพื้น/ฝ้า")])
            g.ext[EXT_KEY]["key"] = name
            out.append((g, "ceiling"))
            continue
        zc = ceiling_z(E, k)
        area = (x1 - x0) * (y1 - y0)
        rname = rm.get("name") or "ห้อง"
        where = f"{rname} · {_floor_name(k)} · {G.area(rm)}"
        bx = _Boxes((0.0, 0.0), (1.0, 0.0), 0.0)
        board = {"color": (0.96, 0.96, 0.94)} if ct != "fc" else {"color": (0.88, 0.88, 0.86)}
        bx.box(x0, x1, y0, y1, zc - 0.009, zc, board)
        g = bx.group(f"ฝ้าเพดาน · {where}", "structure", "ceiling", "ฝ้าเพดาน",
                     "IfcCovering")
        if g is not None:
            g.ext[EXT_KEY]["key"] = name
            g.ext[EXT_KEY]["info"] = [["ชนิด", name], ["ห้อง", rname],
                                      ["ชั้น", _floor_name(k)],
                                      ["ระดับฝ้า", f"+{zc - k * H:.2f} ม. จากพื้น"],
                                      ["พื้นที่", f"{area:.2f} ตร.ม."],
                                      ["ค่าแรง", f"ว480 {lab}"],
                                      ["รายการ BOQ", "หมวด 10 งานพื้น/ฝ้า"]]
            out.append((g, "ceiling"))
        # the frame above the board
        fb = _Boxes((0.0, 0.0), (1.0, 0.0), 0.0)
        steel = {"color": (0.78, 0.80, 0.82)}
        clip = {"color": (0.55, 0.57, 0.60)}
        z1 = zc
        top = (k + 1) * H - (0.0 if k == E["n"] - 1 else float(E["lib"]["S2"]["t"])
                             if "S2" in E["lib"] else 0.10)
        xs_n = max(int(math.ceil((x1 - x0) / sub - 1e-9)), 1)
        for i in range(xs_n + 1):                    # furring channels along y
            x = min(x0 + i * sub, x1 - 0.019)
            x = max(x, x0 + 0.019)
            fb.box(x - 0.019, x + 0.019, y0 + 0.02, y1 - 0.02, z1, z1 + 0.012, steel)
        ys_n = max(int(math.ceil((y1 - y0) / main - 1e-9)), 1)
        mains = [y0 + (y1 - y0) * (j + 0.5) / ys_n for j in range(ys_n)]
        for y in mains:                              # main runners along x
            fb.box(x0 + 0.02, x1 - 0.02, y - 0.019, y + 0.019, z1 + 0.012,
                   z1 + 0.012 + 0.025, steel)
            nh = max(int(math.ceil((x1 - x0) / main - 1e-9)), 1)
            for i in range(nh):                      # hangers
                x = x0 + (x1 - x0) * (i + 0.5) / nh
                if top - (z1 + 0.037) > 0.02:
                    fb.box(x - 0.003, x + 0.003, y - 0.003, y + 0.003,
                           z1 + 0.037, top, steel)
                    # the fixings: hanger clip on the main runner, a spring
                    # level adjuster (สปริงปรับระดับ), an anchor plate up top
                    fb.box(x - 0.012, x + 0.012, y - 0.022, y + 0.022,
                           z1 + 0.037, z1 + 0.052, clip)
                    za = z1 + 0.15
                    if top - za > 0.08:
                        fb.box(x - 0.008, x + 0.008, y - 0.015, y + 0.015,
                               za, za + 0.05, clip)
                    fb.box(x - 0.025, x + 0.025, y - 0.025, y + 0.025,
                           top - 0.006, top, clip)
        for (a0, b0, a1, b1) in ((x0, y0, x1, y0 + 0.025), (x0, y1 - 0.025, x1, y1),
                                 (x0, y0 + 0.025, x0 + 0.025, y1 - 0.025),
                                 (x1 - 0.025, y0 + 0.025, x1, y1 - 0.025)):
            fb.box(a0, a1, b0, b1, z1, z1 + 0.025, steel)   # wall angle
        g = fb.group(f"โครงคร่าวฝ้า {frame} · {where}", "structure", "ceiling_frame",
                     "โครงคร่าวฝ้า", "IfcMember")
        if g is not None:
            g.ext[EXT_KEY]["info"] = [["ชนิด", f"โครงคร่าวฝ้า {frame} พร้อมฉากริมผนัง "
                                               "และลวด/สตัดแขวน"],
                                      ["อุปกรณ์ยึด", "ตัวยึดโครงหลัก สปริงปรับระดับ "
                                                     "เพลทยึดใต้โครงสร้าง (พุกเหล็ก)"],
                                      ["โครงซอย", f"@{sub:.2f} ม."],
                                      ["โครงหลัก/ตัวแขวน", f"@{main:.2f} ม."],
                                      ["ห้อง", rname], ["รายการ BOQ", "หมวด 10 งานพื้น/ฝ้า"]]
            out.append((g, "ceiling_frame"))
    return out


def trim_length(E, rm, k) -> float:
    """Metres of skirting round a room: its inner perimeter less the doors."""
    x0, y0, x1, y1 = room_inner(E, rm, k)
    per = 2 * ((x1 - x0) + (y1 - y0))
    for op in E["openings"]:
        if op["floor"] == k and op["type"] != "window" and \
                _on_edge(rm, float(op["op"]["x"]), float(op["op"]["y"]), tol=0.06):
            per -= op["w"]
    return max(per, 0.0)


def _has_trim(E, rm, what):
    from core.wanic_catalog import finish_of
    if what == "skirting":
        fin = finish_of(rm)
        return not (fin["wall_tile"] and fin["tile_h"] >= 1.2)
    return (rm.get("finish") or {}).get("ceiling", True) and \
        ceiling_type(E["settings"], rm) != "none"


def trim_members(E):
    """Skirting at the floor and cornice at the ceiling of every room the
    user turned them on for (rooms tiled to 1.20 ม. or more have none)."""
    s, H = E["settings"], E["H"]
    out = []
    drop = max(float(s.get("wet_drop") or 0.0), 0.0)
    for e in E["slabs"]:
        rm, k = e["room"], e["floor"]
        x0, y0, x1, y1 = room_inner(E, rm, k)
        rname = rm.get("name") or "ห้อง"
        for what in ("skirting", "cornice"):
            if not s.get(what) or not _has_trim(E, rm, what):
                continue
            if what == "skirting":
                name, _lab, h, t, _r = SKIRTING_TYPES.get(s.get("skirting_type", "ceramic"),
                                                          SKIRTING_TYPES["ceramic"])
                z0 = k * H - (drop if is_wet(rm) else 0.0)
                color = {"color": (0.82, 0.80, 0.76)}
            else:
                name, _lab, h, t = CORNICE
                z0 = ceiling_z(E, k) - 0.009 - h
                color = {"color": (0.98, 0.98, 0.97)}
            bx = _Boxes((0.0, 0.0), (1.0, 0.0), 0.0)
            bx.box(x0, x1, y0, y0 + t, z0, z0 + h, color)
            bx.box(x0, x1, y1 - t, y1, z0, z0 + h, color)
            bx.box(x0, x0 + t, y0 + t, y1 - t, z0, z0 + h, color)
            bx.box(x1 - t, x1, y0 + t, y1 - t, z0, z0 + h, color)
            L = trim_length(E, rm, k) if what == "skirting" else \
                2 * ((x1 - x0) + (y1 - y0))
            g = bx.group(f"{name} · {rname} · {_floor_name(k)}", "structure", what,
                         name, "IfcCovering")
            if g is not None:
                g.ext[EXT_KEY]["info"] = [["ชนิด", name], ["ห้อง", rname],
                                          ["ความยาว", f"{L:.2f} ม."],
                                          ["รายการ BOQ", "หมวด 10 งานพื้น/ฝ้า"]]
                out.append((g, what))
    return out


def _fixture_frame(fx, room, w, d):
    """(u, front sign) for a fitting: ``u`` runs along its width with the
    front (away from the wall it stands on) on its left."""
    x, y = float(fx["x"]), float(fx["y"])
    along_x = int(fx.get("dir", 0)) % 2 == 0
    if room is not None:
        x0, y0 = float(room["x"]), float(room["y"])
        x1, y1 = x0 + float(room["w"]), y0 + float(room["d"])
    else:
        x0 = y0 = -1e9
        x1 = y1 = 1e9
    if along_x:
        front_pos = (y - y0) <= (y1 - y)          # the wall below → face +y
        return ((1.0, 0.0) if front_pos else (-1.0, 0.0))
    front_pos = (x - x0) <= (x1 - x)              # wall on the left → face +x
    return ((0.0, -1.0) if front_pos else (0.0, 1.0))


def fixture_member(fx, z, room=None):
    """A sanitary fitting modelled as it looks: a close-coupled WC with its
    cistern, a vanity with a counter-top basin and mixer, a shower set
    (valve, riser, rain head), a bath, grab rails, mirror … (sizes from the
    catalog, its back against the nearest wall of the room)."""
    from core.wanic_catalog import COLORS, DECOR, SANITARY
    spec = SANITARY.get(fx.get("type"))
    if spec is None and fx.get("type") in DECOR:
        nm, w_, d_, z_, h_ = DECOR[fx.get("type")]
        spec = (nm, "", 0, w_, d_, z_, h_)
    if spec is None:
        return None
    name, _item, _rate, w, d, z0, height = spec
    t = fx.get("type")
    u = _fixture_frame(fx, room, w, d)
    x, y = float(fx["x"]), float(fx["y"])
    bx = _Boxes((x, y), u, z)
    white = {"color": COLORS["sanitary"]}
    chrome = {"color": (0.80, 0.82, 0.85)}
    dark = {"color": (0.25, 0.25, 0.27)}
    wood = {"color": COLORS["teak"]}
    stone = {"color": (0.86, 0.84, 0.80)}
    mirror = {"color": (0.78, 0.86, 0.92)}
    b = -d / 2                                      # the back, against the wall
    if t == "WC1":
        bx.box(-0.18, 0.18, b, b + 0.17, 0.40, 0.76, white)          # cistern
        bx.box(-0.19, 0.19, b - 0.005, b + 0.18, 0.76, 0.79, white)  # its lid
        bx.frustum(0.0, b + 0.40, 0.11, 0.15, 0.13, 0.18, 0.0, 0.22, white)   # pedestal
        bx.frustum(0.0, b + 0.40, 0.13, 0.18, 0.18, 0.25, 0.22, 0.38, white)  # bowl
        bx.frustum(0.0, b + 0.40, 0.185, 0.255, 0.185, 0.255, 0.38, 0.41, white)  # seat
        bx.box(-0.18, 0.18, b + 0.13, b + 0.20, 0.38, 0.43, white)   # seat hinge
        bx.frustum(0.0, b + 0.085, 0.025, 0.025, 0.025, 0.025, 0.79, 0.80, chrome)  # button
    elif t == "WC2":
        bx.box(-w / 2, w / 2, b, -b, 0.0, 0.05, white)
        bx.frustum(0.0, 0.03, 0.13, 0.20, 0.13, 0.20, 0.05, 0.06, dark)
        bx.box(-0.10, -0.04, b + 0.05, b + 0.15, 0.05, 0.07, white)
        bx.box(0.04, 0.10, b + 0.05, b + 0.15, 0.05, 0.07, white)
    elif t == "LV":
        bx.box(-w / 2 - 0.10, w / 2 + 0.10, b, b + 0.50, 0.15, 0.78, wood)   # vanity
        bx.box(-w / 2 - 0.10, w / 2 + 0.10, b + 0.50, b + 0.51, 0.20, 0.74, {"color": COLORS["teak_dark"]})
        bx.box(-w / 2 - 0.12, w / 2 + 0.12, b, b + 0.53, 0.78, 0.81, stone)  # counter
        bx.frustum(0.0, b + 0.30, 0.17, 0.13, 0.21, 0.16, 0.81, 0.94, white)  # basin
        bx.frustum(0.0, b + 0.30, 0.18, 0.14, 0.18, 0.14, 0.935, 0.94, dark)
        bx.frustum(0.0, b + 0.08, 0.02, 0.02, 0.02, 0.02, 0.81, 1.06, chrome)  # mixer
        bx.box(-0.012, 0.012, b + 0.08, b + 0.20, 1.03, 1.06, chrome)
        bx.box(-0.04, -0.005, b + 0.06, b + 0.10, 1.06, 1.08, chrome)
    elif t == "LV2":
        # a long stone counter on a wood vanity, two vessel basins on top
        bx.box(-w / 2, w / 2, b, b + 0.52, 0.12, 0.76, wood)
        for k_ in range(4):
            x_ = -w / 2 + (k_ + 0.5) * w / 4
            bx.box(x_ - w / 8 + 0.01, x_ + w / 8 - 0.01, b + 0.52, b + 0.53, 0.18, 0.72,
                   {"color": COLORS["teak_dark"]})
        bx.box(-w / 2 - 0.02, w / 2 + 0.02, b, b + 0.55, 0.76, 0.80, stone)
        for x_ in (-w / 4, w / 4):
            bx.frustum(x_, b + 0.30, 0.10, 0.08, 0.20, 0.17, 0.80, 0.95, white)
            bx.frustum(x_, b + 0.30, 0.19, 0.16, 0.19, 0.16, 0.947, 0.95, dark)
            bx.frustum(x_, b + 0.05, 0.016, 0.016, 0.016, 0.016, 0.80, 1.12, chrome)
            bx.box(x_ - 0.01, x_ + 0.01, b + 0.04, b + 0.20, 1.10, 1.12, chrome)
    elif t == "BT2":
        # a freestanding oval bath: a tapered shell on the floor, a floor mixer
        bx.frustum(0.0, 0.0, w / 2 - 0.12, d / 2 - 0.10, w / 2, d / 2, 0.0, 0.58, white)
        bx.frustum(0.0, 0.0, w / 2 - 0.07, d / 2 - 0.07, w / 2 - 0.07, d / 2 - 0.07,
                   0.58, 0.585, {"color": (0.80, 0.86, 0.90)})
        bx.frustum(w / 2 + 0.12, 0.0, 0.02, 0.02, 0.02, 0.02, 0.0, 0.95, chrome)
        bx.box(w / 2 - 0.02, w / 2 + 0.13, -0.01, 0.01, 0.92, 0.95, chrome)
    elif t == "GP":
        # the glass screen: clear panel, a slim chrome frame at its edges
        glass = {"color": (0.82, 0.92, 0.96), "opacity": 0.35}
        bx.box(-w / 2, w / 2, -0.005, 0.005, 0.02, 2.00, glass)
        bx.box(-w / 2, -w / 2 + 0.02, -0.012, 0.012, 0.0, 2.00, chrome)
        bx.box(-w / 2, w / 2, -0.012, 0.012, 0.0, 0.03, chrome)
    elif t == "PL":
        bx.frustum(0.0, 0.0, 0.14, 0.14, 0.19, 0.19, 0.0, 0.40, {"color": (0.70, 0.66, 0.60)})
        leaf = {"color": (0.30, 0.55, 0.28)}
        for k_ in range(5):
            a_ = 2 * math.pi * k_ / 5
            bx.frustum(0.08 * math.cos(a_), 0.08 * math.sin(a_), 0.10, 0.10, 0.02, 0.02,
                       0.40 + 0.05 * k_, 0.80 + 0.04 * k_, leaf)
        bx.frustum(0.0, 0.0, 0.16, 0.16, 0.05, 0.05, 0.40, 0.90, leaf)
    elif t == "SH":
        bx.box(-0.07, 0.07, b, b + 0.015, 0.93, 1.07, chrome)          # valve plate
        bx.box(-0.01, 0.07, b + 0.015, b + 0.05, 0.98, 1.02, chrome)
        bx.frustum(0.0, b + 0.03, 0.012, 0.012, 0.012, 0.012, 1.07, 2.00, chrome)  # riser
        bx.box(-0.012, 0.012, b + 0.02, b + 0.30, 1.98, 2.01, chrome)  # arm
        bx.frustum(0.0, b + 0.30, 0.11, 0.11, 0.11, 0.11, 1.95, 1.97, chrome)  # rain head
        bx.box(-0.40, 0.40, b, b + 0.80, -0.002, 0.0, {"color": (0.70, 0.72, 0.74)})  # wet zone
    elif t == "BT":
        bx.box(-w / 2, w / 2, b, b + 0.06, 0.0, 0.55, white)
        bx.box(-w / 2, w / 2, -b - 0.06, -b, 0.0, 0.55, white)
        bx.box(-w / 2, -w / 2 + 0.06, b, -b, 0.0, 0.55, white)
        bx.box(w / 2 - 0.06, w / 2, b, -b, 0.0, 0.55, white)
        bx.box(-w / 2, w / 2, b, -b, 0.0, 0.10, white)
        bx.frustum(w / 2 - 0.20, b + 0.05, 0.02, 0.02, 0.02, 0.02, 0.55, 0.70, chrome)
    elif t == "UR":
        bx.frustum(0.0, b + 0.16, 0.16, 0.14, 0.19, 0.17, 0.45, 1.05, white)
        bx.frustum(0.0, b + 0.03, 0.015, 0.015, 0.015, 0.015, 1.05, 1.25, chrome)
    elif t == "SP":
        bx.box(-0.03, 0.03, b, b + 0.04, 0.47, 0.53, chrome)
        bx.box(-0.02, 0.02, b + 0.04, b + 0.07, 0.40, 0.55, chrome)
    elif t == "MR":
        bx.box(-w / 2, w / 2, b, b + 0.01, z0, z0 + height, {"color": (0.55, 0.57, 0.60)})
        bx.box(-w / 2 + 0.01, w / 2 - 0.01, b + 0.01, b + 0.015, z0 + 0.01,
               z0 + height - 0.01, mirror)
    elif t in ("TR", "GB"):
        bx.box(-w / 2, -w / 2 + 0.03, b, b + 0.08, z0 - 0.02, z0 + 0.03, chrome)
        bx.box(w / 2 - 0.03, w / 2, b, b + 0.08, z0 - 0.02, z0 + 0.03, chrome)
        bx.box(-w / 2, w / 2, b + 0.06, b + 0.085, z0, z0 + 0.025, chrome)
    elif t in ("TP", "SD"):
        bx.box(-w / 2, w / 2, b, b + d, z0, z0 + height, chrome)
    elif t == "FD":
        bx.box(-w / 2, w / 2, b, -b, -0.004, 0.002, chrome)
    else:
        bx.box(-w / 2, w / 2, b, -b, z0, z0 + max(height, 0.01),
               chrome if t.startswith("SK") else white)
    g = bx.group(name, "structure", "fixture", t, "IfcSanitaryTerminal")
    if g is not None:
        g.ext[EXT_KEY]["info"] = [["ชนิด", name], ["รหัส", t],
                                  ["ระดับติดตั้ง", f"{z0:.2f} ม. จากพื้น" if z0 else "วางบนพื้น"]]
    return g


def wall_offset(E, wl) -> float:
    """How far the wall's centre sits off its grid line, towards the
    outside: an exterior wall stands so that its outside plaster is flush
    with the outer faces of the columns and the beam above (one plumb,
    even face from the ground beam to the ring beam); an interior wall
    stays on the grid line."""
    s, lib = E["settings"], E["lib"]
    if not wl.get("exterior") or not s.get("wall_flush", True):
        return 0.0
    sp = wall_spec(s, True)
    half = float(lib["C1"]["b"]) / 2
    return max(half - sp["po"] - sp["t"] / 2, 0.0)


def _walls(E, add):
    s, lib, H = E["settings"], E["lib"], E["H"]
    G = Grid(E)
    half = float(lib["C1"]["b"]) / 2
    for wl in E["walls"]:
        z0 = wl["floor"] * H
        wh = H - float(lib[wl["beam"]]["h"])
        if wh <= 0.05:
            continue
        p0, p1, L = wl["p0"], wl["p1"], wl["L"]
        if L <= 2 * half + 0.05:
            continue
        ext = bool(wl.get("exterior"))
        sp = wall_spec(s, ext)
        t, T = sp["t"], sp["T"]
        ux, uy = (p1[0] - p0[0]) / L, (p1[1] - p0[1]) / L
        off = wall_offset(E, wl)
        ox, oy = wl.get("out") or (0.0, 0.0)
        # wall-local across axis: +d = left of p0→p1; the outside side
        out_left = (-uy * ox + ux * oy) > 0 if ext else True
        sgn = 1.0 if out_left else -1.0
        c0 = (p0[0] + ox * off, p0[1] + oy * off)     # wall centre line

        def at(dist, z, d=0.0):
            return (c0[0] + ux * dist - uy * d, c0[1] + uy * dist + ux * d, z)

        where = G.span(p0, p1)
        floor_ = _floor_name(wl["floor"])
        side = "ผนังภายนอก" if ext else "ผนังภายใน"
        kind_name = f"{side} {sp['name']}"
        layers = [("ฉาบปูนผนังภายนอก" if ext else "ฉาบปูนผนังภายใน",
                   sgn * (t / 2 + sp["po"] / 2), sp["po"]),
                  ("ฉาบปูนผนังภายใน", -sgn * (t / 2 + sp["pi"] / 2), sp["pi"])]
        aac = sp["recipe"] in ("6.10", "6.11", "6.12", "6.13", "6.14")

        def piece(a, b, z, height):
            if b - a <= 0.02 or height <= 0.02:
                return
            area = (b - a) * height
            add(_member("structure", "wall", kind_name, "rect",
                        dict(b=_mm(t), h=_mm(height)),
                        [at(a, z), at(b, z)], anchor="bc", ifc="IfcWall",
                        name=f"{kind_name} · {floor_} · {where}",
                        key=kind_name,
                        info=[("ชนิด", kind_name),
                              ("สูตรวัสดุ", f"หลักเกณฑ์ 2569 หมวด 6 ข้อ {sp['recipe']}"),
                              ("ความหนาเนื้อผนัง", f"{t * 100:g} ซม."),
                              ("ความหนาฉาบ", f"ใน {sp['pi'] * 100:g} ซม. · "
                                             f"นอก {sp['po'] * 100:g} ซม."),
                              ("ความหนารวม", f"{T * 100:g} ซม."),
                              ("แนวผนัง", "ผิวฉาบนอกเสมอผิวเสาและคาน" if off > 1e-6
                               else "กึ่งกลางเสา"),
                              ("ชั้น", floor_), ("ตำแหน่ง", where),
                              ("ชิ้นนี้", f"ยาว {b - a:.2f} ม. สูง {height:.2f} ม."),
                              ("พื้นที่", f"{area:.2f} ตร.ม."),
                              ("รายการ BOQ", "หมวด 6 งานผนัง/ฉาบ")]),
                "wall")

        def skin(a, b, z, height):
            """Plaster on both faces of a stretch of wall (masonry and the
            concrete bands alike)."""
            if not s.get("plaster_3d", True) or b - a <= 0.02 or height <= 0.02:
                return
            area = (b - a) * height
            for lname, d, pt in layers:
                if pt <= 1e-4:
                    continue
                add(_member("structure", "plaster", lname, "rect",
                            dict(b=_mm(pt), h=_mm(height)),
                            [at(a, z, d), at(b, z, d)], anchor="bc",
                            ifc="IfcCovering",
                            name=f"{lname} หนา {pt * 100:g} ซม. · {floor_} · {where}",
                            key=lname,
                            info=[("ชนิด", lname),
                                  ("สูตรวัสดุ", "หลักเกณฑ์ 2569 หมวด 7 ข้อ "
                                   + ("7.3" if aac else "7.2")),
                                  ("ความหนา", f"{pt * 100:g} ซม."),
                                  ("บนผนัง", kind_name),
                                  ("ชั้น", floor_), ("ตำแหน่ง", where),
                                  ("พื้นที่", f"{area:.2f} ตร.ม."),
                                  ("ค่าแรง", "ว480 2.3.1.2 "
                                   + ("ภายนอก" if "ภายนอก" in lname else "ภายใน"))]),
                    "plaster")
        band = float(s.get("band", 0.10))
        cur = half
        scur = half
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
            # plaster: the wall less the opening itself (it covers the bands)
            bottom = 0.0 if door else sill
            skin(scur, a, z0, wh)
            skin(a, b, z0, bottom)
            skin(a, b, z0 + top, wh - top)
            scur = b
            if band > 0:
                add(opening_band(c0, (ux, uy), z0, a, b, sill if not door
                                 else 0.0, top, t, band, wh, door), "band")
            kind = "door" if door else "window"
            add(opening_set(op, s, c0, (ux, uy), z0, a, b, sill, top, T),
                kind)
            cur = max(cur, b + band)
        piece(cur, L - half, z0, wh)
        skin(scur, L - half, z0, wh)


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

    def frustum(self, s, d, rs0, rd0, rs1, rd1, z0, z1, attrs=None, n=20):
        """An elliptic frustum standing at (s, d): radii (rs0, rd0) at z0
        and (rs1, rd1) at z1, capped both ends (bowls, pedestals, pipes)."""
        if z1 - z0 < 1e-4:
            return
        ring0 = [self.P(s + rs0 * math.cos(2 * math.pi * i / n),
                        d + rd0 * math.sin(2 * math.pi * i / n), z0) for i in range(n)]
        ring1 = [self.P(s + rs1 * math.cos(2 * math.pi * i / n),
                        d + rd1 * math.sin(2 * math.pi * i / n), z1) for i in range(n)]
        faces = [ring1, ring0[::-1]]
        for i in range(n):
            j = (i + 1) % n
            faces.append([ring0[i], ring0[j], ring1[j], ring1[i]])
        # ccw seen from outside: the left normal frame flips when u×n < 0
        flip = self.u[0] * self.n[1] - self.u[1] * self.n[0] < 0
        for q in faces:
            f = self.mesh.add_face(q[::-1] if flip else q)
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
    # A fixed glass transom over the leaves and / or a side light, behind
    # a mullion of the frame section.
    tr = float(spec.get("transom") or 0.0)
    if tr > 0 and j1 - j0 > tr + 0.3:
        mz = j1 - tr
        bx.box(i0, i1, -fd, fd, mz, mz + fw, frame)
        bx.box(i0, i1, -0.003, 0.003, mz + fw + gap, j1, glass)
        j1 = mz - gap
    sd = float(spec.get("side") or 0.0)
    if sd > 0 and i1 - i0 > sd + 0.3:
        mx = i1 - sd
        bx.box(mx, mx + fw, -fd, fd, j0, j1, frame)
        bx.box(mx + fw + gap, i1, -0.003, 0.003, j0, j1, glass)
        i1 = mx - gap
    if n == 0:                                   # fixed glass
        bx.box(i0, i1, -0.003, 0.003, j0, j1, glass)
    else:
        lw = (i1 - i0) / n
        leaf_col = _paint("pvc" if spec["leaf"] == "prefab" else
                          "alu" if spec["leaf"] == "alu" else
                          "teak" if spec["leaf"] == "teak" else "wood")
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
                st = 0.012 if spec["glass"] >= 0.95 else \
                    0.04 if spec["leaf"] == "alu" else 0.06
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
                if door and spec.get("panels") and j1 - j0 > 1.2:
                    # a carved teak leaf: six raised panels (ลูกฟัก) in two
                    # columns, a deeper bead round each
                    pc = _paint("teak_dark")
                    cw = (s1 - s0 - 0.24) / 2
                    rows = ((j0 + 0.12, j0 + 0.70), (j0 + 0.82, j0 + 1.30),
                            (j0 + 1.42, j1 - 0.12))
                    for cx_ in (s0 + 0.08, s0 + 0.16 + cw):
                        for z0p, z1p in rows:
                            for dz0, dz1, sg in ((0.0175, 0.0225, 1), (-0.0225, -0.0175, -1)):
                                bx.box(cx_, cx_ + cw, dz0 + d_off, dz1 + d_off, z0p, z1p, pc)
                                bx.box(cx_ + 0.03, cx_ + cw - 0.03,
                                       dz0 + d_off + (0.004 if sg > 0 else -0.004),
                                       dz1 + d_off + (0.004 if sg > 0 else -0.004),
                                       z0p + 0.03, z1p - 0.03, leaf_col)
                # Two raised panels so a solid leaf reads as a door.
                elif door and j1 - j0 > 1.2:
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


def _dim(label, key="H", default=150.0):
    """A steel section's dimension in metres (H depth, B flange…)."""
    _f, prm = steel_lookup(label)
    for k in (key, "H", "D", "A"):
        if prm.get(k):
            return float(prm[k]) / 1000.0
    return default / 1000.0


def _rafter_stations(rect, s, cols):
    """(axis, positions): where one rectangle's common rafters stand, in
    world coordinates along ``axis`` ("x" or "y") — the column lines, the
    eave ends, the hip apexes, and between them at no more than the set
    spacing. Shared with the hipped ends of the neighbouring roofs, so
    the rafters of two roofs that make one plane line up."""
    ov = float(s["overhang"])
    x0, y0, x1, y1 = rect[0] - ov, rect[1] - ov, rect[2] + ov, rect[3] + ov
    swap = (y1 - y0) > (x1 - x0)
    if swap:
        x0, y0, x1, y1 = y0, x0, y1, x1
    half = (y1 - y0) / 2
    sp, _p = roof_spacing(s)
    stations = {round(x0, 4), round(x1, 4)}
    for c in cols:
        cx = c[1] if swap else c[0]
        if x0 + 1e-6 < cx < x1 - 1e-6:
            stations.add(round(cx, 4))
    extra = set()
    if x1 - x0 > 2 * half + 0.3:            # the hip apexes (ridge ends)
        extra |= {round(x0 + half, 4), round(x1 - half, 4)}
    if s.get("roof") == "manila":           # the small gables' planes
        fm = min(max(float(s.get("manila_f", 0.5)), 0.2), 0.9)
        extra |= {round(x0 + half * fm, 4), round(x1 - half * fm, 4)}
    # an apex a hand's breadth from a column line would put two rafters
    # side by side (one is enough): the column line's rafter stands for it
    near = min(0.45, sp * 0.45)
    stations |= {e for e in extra if all(abs(e - c) >= near for c in stations)}
    stations = sorted(stations)
    xs = []
    for a_, b_ in zip(stations, stations[1:]):
        n_ = max(int(math.ceil((b_ - a_) / sp - 1e-9)), 1)
        xs += [a_ + (b_ - a_) * k / n_ for k in range(n_)]
    xs.append(stations[-1])
    return ("y" if swap else "x"), xs, stations


def _roof_rect(rect, z0, s, others=(), cols=(), lift=0.0, purlin_step=0.0,
               grid=None):
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
           "skin": [], "eave": [], "barge": [], "tie": [], "rbeam": [],
           "strut": [], "brace": []}
    zr = h(half)
    yc = y0 + half
    manila = s["roof"] == "manila"
    if s["roof"] in ("hip", "manila"):
        h0 = h1 = True
    else:
        h0, h1 = covered(x0), covered(x1)
    # how far each hipped end climbs: the whole half width on a hip; on a
    # มะนิลา (hip-and-gable) only part of it, a small gable above
    fm = min(max(float(s.get("manila_f", 0.5)), 0.2), 0.9)
    dd0 = (half * fm if manila and not covered(x0) else half) if h0 else 0.0
    dd1 = (half * fm if manila and not covered(x1) else half) if h1 else 0.0
    rx0 = x0 + dd0
    rx1 = x1 - dd1
    if rx1 < rx0:
        rx0 = rx1 = (x0 + x1) / 2
    if rx1 - rx0 > 1e-6:
        out["ridge"].append([P3(rx0, yc, zr), P3(rx1, yc, zr)])
    for hipped, cx, ex, dd, sg in ((h0, x0, rx0, dd0, 1), (h1, x1, rx1, dd1, -1)):
        if hipped:
            for cy, sy in ((y0, 1), (y1, -1)):
                if dd >= half - 1e-9:
                    out["hip"].append([P3(cx, cy, h(0)), P3(ex, yc, zr)])
                else:
                    out["hip"].append([P3(cx, cy, h(0)), P3(cx + sg * dd, cy + sy * dd, h(dd))])
            if dd < half - 1e-9:
                # the small gable: its rakes (ปั้นลม) and the beam at its foot
                gx = cx + sg * dd
                out["barge"].append([P3(gx, y0 + dd, h(dd)), P3(gx, yc, zr)])
                out["barge"].append([P3(gx, y1 - dd, h(dd)), P3(gx, yc, zr)])
                out["rafter"].append([P3(gx, y0 + dd, h(dd)), P3(gx, y1 - dd, h(dd))])
                out.setdefault("gable", []).append(
                    [P3(gx, y0 + dd, h(dd)), P3(gx, y1 - dd, h(dd)), P3(gx, yc, zr)])
    sp, psp_slope = roof_spacing(s)
    big = 1e9
    # Rafters (จันทัน) on every column line (จันทันเอก on the column heads),
    # at the hip apexes, and between them at no more than the set spacing
    # (จันทันพราง).
    _axis, xs, stations = _rafter_stations(rect, s, cols)
    for x in xs:
        reach = min(half, (x - x0) if h0 and x - x0 < dd0 - 1e-6 else big,
                    (x1 - x) if h1 and x1 - x < dd1 - 1e-6 else big)
        if reach <= 0.05:
            continue
        out["rafter"].append([P3(x, y0, h(0)), P3(x, y0 + reach, h(reach))])
        out["rafter"].append([P3(x, y1, h(0)), P3(x, y1 - reach, h(reach))])
    cnt = max(int(math.ceil(W / sp - 1e-9)), 1)
    jacks = [y0 + W * i / cnt for i in range(cnt + 1)]
    # A hipped end in the same plane as a neighbour's long slope (an L or
    # U plan: the wing's end and the main roof's side make one face): its
    # jack rafters stand where the neighbour's rafters do, so each runs on
    # as one rafter from the eave to the hip — not two staggered sets.
    near = []
    for p in sorted((grid or {}).get("x" if swap else "y", ())):
        if y0 + 0.05 < p < y1 - 0.05 and (not near or p - near[-1] > 0.1):
            near.append(p)
    if near:
        cand = [y0] + near + [y1]
        if all(b_ - a_ <= sp * 1.05 + 1e-6 for a_, b_ in zip(cand, cand[1:])):
            jacks = cand
    for hipped, ex, sgn, dd in ((h0, x0, 1, dd0), (h1, x1, -1, dd1)):
        if not hipped:                       # jack rafters on a hipped end
            continue
        for y in jacks:
            reach = min(dd, y - y0, y1 - y)
            if reach <= 0.05:
                continue
            out["rafter"].append([P3(ex, y, h(0)),
                                  P3(ex + sgn * reach, y, h(reach))])
    psp = psp_slope * math.cos(math.radians(float(s["pitch"])))
    # Purlins (แป) as straight pieces, one per slope: on a hipped end they
    # stop on the hip line, where the member is cut along the hip (see
    # :func:`roof_members`) — not swept round the corner as one ring.
    d = 0.05

    def purlin(p, q):
        if math.dist(p, q) > 0.05:
            out["purlin"].append({"closed": False, "path": [p, q]})
    # Purlins evenly spaced from the first (5 cm in from the fascia) to the
    # top one (4 cm under the ridge — CPAC: แปตัวบนห่างสันไม่เกิน 4 ซม.):
    # the set spacing is the most allowed, a span that does not divide is
    # shared out a little closer (0.32 → 0.31 …). ``step`` comes from the
    # widest roof part so the purlins of slopes that are one plane line up.
    top = half - 0.04
    step = purlin_step if purlin_step else psp
    if not purlin_step:
        n_ = max(int(math.ceil((top - d) / psp - 1e-9)), 1)
        step = (top - d) / n_
    ds = []
    while d < top - 0.02:
        ds.append(d)
        d += step
    if ds and top - ds[-1] > 0.02:
        ds.append(top)
    for d in ds:
        a0 = x0 + min(d, dd0) if h0 else x0
        a1 = x1 - min(d, dd1) if h1 else x1
        if a1 - a0 > 1e-6:
            for yy in (y0 + d, y1 - d):
                purlin(P3(a0, yy, h(d)), P3(a1, yy, h(d)))
            if h0 and d < dd0 - 0.02:
                purlin(P3(a0, y0 + d, h(d)), P3(a0, y1 - d, h(d)))
            if h1 and d < dd1 - 0.02:
                purlin(P3(a1, y0 + d, h(d)), P3(a1, y1 - d, h(d)))
    if zr - z0 > 0.1:
        # King posts (ดั้ง) at the ridge ends and on every column line under
        # the ridge. Each column line carries a tie (ขื่อ) from wall to wall;
        # along the ridge a beam (คานรับดั้ง) sits ON the ties from the first
        # post to the last, and the posts stand on it — tie and beam never
        # cut through each other, and the posts are held both ways.
        db = _dim(s.get("tiebeam", s["ridge"]))
        dr = _dim(s["ridge"])
        px = {round(rx0, 4), round(rx1, 4)}
        for st in stations:
            if rx0 + 0.3 < st < rx1 - 0.3:
                px.add(st)
        beam = rx1 - rx0 > 0.3
        # A concrete beam under the ridge line (a column line along the
        # middle of the plan): the คานรับดั้ง lies ON it, level with the
        # ties, and runs wall to wall; the ties butt on its sides. With no
        # beam there it sits on the ties, from the first post to the last.
        on_beam = beam and sum(1 for c in cols
                               if abs((c[0] if swap else c[1]) - yc) < 1e-4 and
                               x0 + ov - 1e-4 <= (c[1] if swap else c[0]) <= x1 - ov + 1e-4) >= 2
        zb = z0 if on_beam else z0 + (db if beam else 0.0)
        wb = _dim(s.get("tiebeam", s["ridge"]), "B") / 2
        # struts (ตุ๊กตา) from the tie up to the rafters half way to the ridge
        # and braces (ค้ำยัน) from the foot of the post to each strut — the
        # king-post truss of the standard steel roof. All in the plane of
        # the truss and butted, never through each other: the strut stands
        # on the tie's top and its head is cut to the rafter's underside;
        # a brace runs from the post's face to the strut's face, clear of
        # the beam under the posts and of the rafter over the strut.
        dra = _dim(s["rafter"])
        cosp = math.cos(math.radians(float(s["pitch"])))
        hp = _dim(s.get("post", s["ridge"]))
        hs = _dim(s.get("strut", s["post"]))
        hb = hs
        # the wall plate's half width: a tie ends on its face, not in it
        pw = _dim(s["wallplate"], "B") / 2 if s.get("wall_plate") else 0.0
        inner = half - ov                       # wall line to the ridge line
        for xx in sorted(px):
            out["post"].append([P3(xx, yc, zb), P3(xx, yc, max(zr - dr, zb + 0.1))])
            if on_beam:
                out["tie"].append([[P3(xx, y0 + ov + pw, z0), P3(xx, yc - wb, z0)],
                                   [P3(xx, yc + wb, z0), P3(xx, y1 - ov - pw, z0)]])
            else:
                out["tie"].append([[P3(xx, y0 + ov + pw, z0), P3(xx, y1 - ov - pw, z0)]])
            st, br = [], []
            ttype = s.get("truss", "kingpost")
            if s.get("struts", True) and inner > 1.2 and ttype == "kingpost":
                for side in (1, -1):
                    q = yc - side * inner / 2          # half way wall → ridge
                    dist = abs(q - (y0 if side == 1 else y1))
                    zt = h(dist - hs / 2) - dra / cosp     # rafter underside
                    if zt - z0 < 0.35:
                        continue
                    st.append([P3(xx, q, z0), P3(xx, q, zt)])
                    ya = yc - side * hp / 2              # the post's face
                    yb = q + side * hs / 2               # the strut's face
                    run = abs(yb - ya)
                    za, zz = zb + 0.03, zt - 0.10
                    for _k in range(2):                  # clear by the depth
                        ang = math.atan2(max(zz - za, 1e-3), run)
                        lift_ = hb / 2 / max(math.cos(ang), 0.2)
                        za, zz = zb + 0.03 + lift_, zt - 0.10 - lift_
                    if zz - za > 0.05 and run > 0.3:
                        br.append([P3(xx, ya, za), P3(xx, yb, zz)])
            elif s.get("struts", True) and inner > 1.2:
                # the standard truss webs (Howe · Pratt · Fink), panel points
                # as fractions of the half span wall → ridge: verticals
                # (ตุ๊กตา) and diagonals (ค้ำยัน) butting on their faces
                panels = 4 if inner > 2.4 else 2
                pts = [i / panels for i in range(1, panels)]
                if ttype == "howe":
                    verts = pts
                    diags = [(a, b) for a, b in zip(pts, pts[1:] + [1.0])]
                elif ttype == "pratt":
                    verts = pts
                    diags = [(b, a) for a, b in zip(pts, pts[1:] + [1.0])]
                else:                                   # fink (W)
                    verts = []
                    diags = [(2 / 3, 0.5), (2 / 3, 1.0)]
                for side in (1, -1):
                    wall = (y0 + ov) if side == 1 else (y1 - ov)

                    def Y(t):
                        return wall + side * t * inner

                    def under(y, half=0.0):
                        d_ = abs(y - (y0 if side == 1 else y1)) - half
                        return h(d_) - dra / cosp
                    for t in verts:
                        q = Y(t)
                        zt = under(q, hs / 2)
                        if zt - z0 > 0.35:
                            st.append([P3(xx, q, z0), P3(xx, q, zt)])
                    for tb, tt in diags:
                        # bottom end (on the tie / at a vertical / at the
                        # post's foot), top end (under the rafter / at a
                        # vertical / at the post's face)
                        toward = 1 if tt > tb else -1
                        if tb >= 1.0:
                            ya, base = yc - side * hp / 2, zb
                        elif tb in verts:
                            ya, base = Y(tb) + side * toward * hs / 2, z0
                        else:
                            ya, base = Y(tb) + side * toward * hb / 2, z0
                        if tt >= 1.0:
                            yb_ = yc - side * hp / 2
                        elif tt in verts:
                            yb_ = Y(tt) - side * toward * hs / 2
                        else:
                            yb_ = Y(tt)
                        top = under(yb_, hb / 2) if tt < 1.0 else zr - dr - 0.02
                        run = abs(yb_ - ya)
                        # under a vertical's / the post's head: clear of the
                        # rafter; free under the rafter: up against it
                        gap = 0.10 if (tt >= 1.0 or tt in verts) else 0.015
                        za, zz = base + 0.03, top - gap
                        for _k in range(2):
                            ang = math.atan2(max(zz - za, 1e-3), max(run, 1e-3))
                            lift_ = hb / 2 / max(math.cos(ang), 0.2)
                            za, zz = base + 0.03 + lift_, top - gap - lift_
                        if zz - za > 0.05 and run > 0.2:
                            br.append([P3(xx, ya, za), P3(xx, yb_, zz)])
            out["strut"].append(st)
            out["brace"].append(br)
        if on_beam:
            out["rbeam"].append([P3(x0 + ov + pw, yc, zb), P3(x1 - ov - pw, yc, zb)])
            out["rbeam_on_beam"] = True
        elif beam:
            out["rbeam"].append([P3(rx0, yc, zb), P3(rx1, yc, zb)])
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
    # where each hip meets the small gable of a มะนิลา (on a hip: the apex)
    a0 = P3(x0 + dd0, y0 + dd0, h(dd0)) if h0 and dd0 < half - 1e-9 else r0
    b0 = P3(x0 + dd0, y1 - dd0, h(dd0)) if h0 and dd0 < half - 1e-9 else r0
    a1 = P3(x1 - dd1, y0 + dd1, h(dd1)) if h1 and dd1 < half - 1e-9 else r1
    b1 = P3(x1 - dd1, y1 - dd1, h(dd1)) if h1 and dd1 < half - 1e-9 else r1
    out["skin"] = [poly(e[0], e[1], a1, r1, r0, a0), poly(e[2], e[3], b0, r0, r1, b1)]
    if h1:
        out["skin"].append(poly(e[1], e[2], b1, a1))
    if h0:
        out["skin"].append(poly(e[3], e[0], a0, b0))
    return out


def _roof_shed(rect, z0, s, cols=(), lift=0.0, purlin_step=0.0):
    """A เพิงหมาแหงน (shed / lean-to): one slope across the short side,
    low eave on one side, high on the other; rafters wall to wall, purlins
    across the slope, a tie and a post on the high wall at every column
    line, a strut half way."""
    ov = float(s["overhang"])
    tan = math.tan(math.radians(float(s["pitch"])))
    x0, y0, x1, y1 = rect[0] - ov, rect[1] - ov, rect[2] + ov, rect[3] + ov
    swap = (y1 - y0) > (x1 - x0)
    if swap:
        x0, y0, x1, y1 = y0, x0, y1, x1
    W = y1 - y0

    def h(dist):
        return z0 + lift + (dist - ov) * tan

    def P3(x, y, z):
        return (y, x, z) if swap else (x, y, z)
    out = {"ridge": [], "hip": [], "rafter": [], "purlin": [], "post": [],
           "skin": [], "eave": [], "barge": [], "tie": [], "rbeam": [],
           "strut": [], "brace": []}
    _axis, xs, stations = _rafter_stations(rect, dict(s, roof="gable"), cols)
    for x in xs:
        out["rafter"].append([P3(x, y0, h(0)), P3(x, y1, h(W))])
    sp, psp_slope = roof_spacing(s)
    psp = psp_slope * math.cos(math.radians(float(s["pitch"])))
    step = purlin_step or psp
    n_ = max(int(math.ceil((W - 0.10) / step - 1e-9)), 1)
    for i in range(n_ + 1):
        d = 0.05 + (W - 0.10) * i / n_
        out["purlin"].append({"closed": False, "path": [P3(x0, y0 + d, h(d)),
                                                         P3(x1, y0 + d, h(d))]})
    e = [P3(x0, y0, h(0)), P3(x1, y0, h(0)), P3(x1, y1, h(W)), P3(x0, y1, h(W))]
    out["eave"] = [[e[0], e[1]], [e[3], e[2]]]
    out["barge"] = [[e[0], e[3]], [e[1], e[2]]]
    out["skin"] = [[e[0], e[1], e[2], e[3]]]
    dra = _dim(s["rafter"])
    cosp = math.cos(math.radians(float(s["pitch"])))
    pw = _dim(s["wallplate"], "B") / 2 if s.get("wall_plate") else 0.0
    hs = _dim(s.get("strut", s["post"]))
    for st in stations:
        if not (x0 + ov - 1e-6 <= st <= x1 - ov + 1e-6):
            continue
        yh = y1 - ov                                   # the high wall
        zt = h(W - ov - _dim(s["post"]) / 2) - dra / cosp
        if zt - z0 < 0.2:
            continue
        out["tie"].append([[P3(st, y0 + ov + pw, z0), P3(st, yh - pw, z0)]])
        out["post"].append([P3(st, yh - pw - _dim(s["post"]) / 2, z0),
                            P3(st, yh - pw - _dim(s["post"]) / 2, zt)])
        q = y0 + ov + (W - 2 * ov) / 2
        zq = h(q - y0 - hs / 2) - dra / cosp
        out["strut"].append([[P3(st, q, z0), P3(st, q, zq)]] if zq - z0 > 0.3 else [])
        out["brace"].append([])
    return out


def roof_lines(data):
    """The roof frame as lines: {"ridge": [...], "hip": [...], "rafter":
    [...], "purlin": [{"path", "closed"}…], "post": [...], "skin":
    [polygons…], "rects": [...], "z0"} — 3D points in metres. ``None``
    when there is no roof to make."""
    s = settings_of(data)
    floors, _skipped = stacked(data)
    if not floors or s.get("roof") not in ROOF_TYPES:
        return None
    top = floors[-1]["rooms"]
    z0 = len(floors) * float(s["floor_h"])
    if s.get("roof_mode") == "bbox":
        fp = footprint(top)
        rects = [fp]
    else:
        rects = plan_rectangles(top)
    out = {"ridge": [], "hip": [], "rafter": [], "purlin": [], "post": [],
           "skin": [], "eave": [], "barge": [], "rects": rects, "z0": z0, "gable": [],
           "valley": 0.0, "valleys": [], "tie": [], "plate": [], "rbeam": [],
           "strut": [], "brace": []}
    # The steel wall plate (อะเส) on the ring beams lifts the frame by its
    # depth: rafters bear on it, the tie beams sit level with it.
    ph = 0.0
    if s.get("wall_plate") or s.get("tie_beams"):
        for key in (("wallplate",) if s.get("wall_plate") else ()) + \
                (("tiebeam",) if s.get("tie_beams") else ()):
            _f, prm_ = steel_lookup(s[key])
            ph = max(ph, float(prm_.get("H", prm_.get("D", prm_.get("A", 0.0)))) / 1000.0)
    out["plate_h"] = ph
    out["heads"] = nodes(top)
    if s.get("wall_plate"):
        segs = [[(a[0], a[1], z0 + ph), (b[0], b[1], z0 + ph)]
                for a, b in outline_segments(top)]
        out["plate"] = _merge_collinear(segs)
    z0 = z0 + ph
    ov = float(s["overhang"])
    from core import wanic_roofclip as RC
    boxes = [(r[0] - ov, r[1] - ov, r[2] + ov, r[3] + ov) for r in rects]
    # A wing's gable end that runs into an earlier (larger) roof is hipped.
    fam, prm = steel_lookup(s["rafter"])
    lift = float(prm.get("H", prm.get("D", prm.get("A", 0.0)))) / 1000.0
    cols = nodes(top)
    # one purlin step for the whole roof, from its widest part
    _rsp, psp_ = roof_spacing(s)
    psp_h = psp_ * math.cos(math.radians(float(s["pitch"])))
    wide = max(min(b[2] - b[0], b[3] - b[1]) for b in boxes) / 2 - 0.04 - 0.05
    pstep = wide / max(int(math.ceil(wide / psp_h - 1e-9)), 1) if wide > 0 else psp_h
    # where every roof part's common rafters stand (world x / y): a hipped
    # end lines its jack rafters up with them
    grid = {"x": [], "y": []}
    for rect in rects:
        ax_, xs_, _st = _rafter_stations(rect, s, cols)
        grid[ax_] += xs_
    if s.get("roof") == "shed":
        parts = [_roof_shed(rect, z0, s, cols, lift, pstep) for rect in rects]
    else:
        parts = [_roof_rect(rect, z0, s, boxes[:i], cols, lift, pstep, grid)
                 for i, rect in enumerate(rects)]
    roofs = [RC.Roof((r[0] - ov, r[1] - ov, r[2] + ov, r[3] + ov),
                     part["skin"]) for r, part in zip(rects, parts)]
    many = len(rects) > 1
    kept = {}
    for part in parts:
        out["gable"] += part.get("gable") or []
    for i, (rect, part) in enumerate(zip(rects, parts)):
        if not many:
            for k in ("ridge", "hip", "rafter", "purlin", "post", "skin"):
                out[k] += part[k]
            out["tie"] += [seg for grp in part["tie"] for seg in grp]
            out["rbeam"] += part["rbeam"]
            for k in ("strut", "brace"):
                out[k] += [m for grp in part[k] for m in grp]
        else:
            # Trim what lies under a neighbouring roof (L / T plans); a
            # ridge or hip is kept only where it is still a crease of the
            # whole roof (a hip that ends up lying in the face of another
            # wing is no hip — capping it put a "valley" on the wrong side).
            for k in ("ridge", "hip"):
                for a, b in part[k]:
                    for c, d in RC.clip_segment(a, b, i, roofs):
                        out[k] += RC.keep_creases(c, d, roofs, "convex")
            for a, b in part["rafter"]:
                out["rafter"] += RC.clip_segment(a, b, i, roofs)
            for pl in part["purlin"]:
                for seg in RC.clip_path(pl["path"], i, roofs, pl["closed"]):
                    out["purlin"].append({"closed": False, "path": seg})
            kept_posts = []
            for (a, b), tie, st, br in zip(part["post"], part["tie"], part["strut"],
                                           part["brace"]):
                if not RC.hidden(b, i, roofs):
                    out["post"].append([a, b])
                    out["tie"] += tie
                    out["strut"] += st
                    out["brace"] += br
                    kept_posts.append(a)
            # the beam under the posts runs from the first kept post to the
            # last — each end on a tie, never out in the air past one
            for a, b in part["rbeam"]:
                L_ = math.dist(a, b)
                if part.get("rbeam_on_beam"):
                    # on its concrete beam, wall to wall (see below for
                    # where it meets another part's)
                    out["rbeam"].append([a, b])
                    continue
                if L_ < 1e-6 or len(kept_posts) < 2:
                    continue
                ts = sorted(sum((p[k] - a[k]) * (b[k] - a[k]) for k in range(2)) / L_ ** 2
                            for p in kept_posts)
                t0, t1 = max(ts[0], 0.0), min(ts[-1], 1.0)
                if (t1 - t0) * L_ > 0.3:
                    out["rbeam"].append([tuple(a[k] + (b[k] - a[k]) * t0 for k in range(3)),
                                         tuple(a[k] + (b[k] - a[k]) * t1 for k in range(3))])
            kept[i] = []
            for poly in part["skin"]:
                kept[i] += RC.clip_facet(poly, i, roofs)
            out["skin"] += kept[i]
        for k in ("eave", "barge"):
            for a, b in part[k]:
                out[k] += RC.clip_segment(a, b, i, roofs) if many \
                    else [[a, b]]
    out["eave"] = _merge_collinear(out["eave"])
    # one member from end to end: pieces of one line (a hip end and the
    # wing whose slope it shares, or bits a clip left) become one
    # (the clip leaves a few mm between the pieces of two roofs in one plane)
    out["purlin"] = [{"closed": False, "path": seg} for seg in
                     merge_segments([pl["path"] for pl in out["purlin"]], gap=0.03)]
    out["rafter"] = merge_segments(out["rafter"], gap=0.03)
    out["ridge"] = merge_segments(out["ridge"])
    # one คานรับดั้ง crossing another (an L / T plan): the later one butts
    # on the earlier one's sides instead of running through it
    if many and len(out["rbeam"]) > 1:
        wb_ = _dim(s.get("tiebeam", s["ridge"]), "B") / 2
        done = []
        for a, b in out["rbeam"]:
            pieces = [[a, b]]
            for c, d_ in done:
                nxt = []
                for p_, q_ in pieces:
                    cut = _crossing(p_, q_, c, d_)
                    if cut is None or abs(p_[2] - c[2]) > 0.02:
                        nxt.append([p_, q_])
                        continue
                    L_ = math.dist(p_[:2], q_[:2])
                    t0, t1 = cut - wb_ / L_, cut + wb_ / L_
                    if t0 * L_ > 0.1:
                        nxt.append([p_, tuple(p_[k] + (q_[k] - p_[k]) * t0 for k in range(3))])
                    if (1 - t1) * L_ > 0.1:
                        nxt.append([tuple(p_[k] + (q_[k] - p_[k]) * t1 for k in range(3)), q_])
                pieces = nxt
            done += pieces
        out["rbeam"] = done
    if not s.get("tie_beams"):
        out["tie"] = []
        out["rbeam"] = []
        out["strut"] = []
        out["brace"] = []
    if many:
        out["valleys"] = RC.valley_lines(roofs)
        # a valley ends on the ridge / hip junction or the eave corner:
        # snap its ends to the frame points within a few cm
        ends = [p for k in ("ridge", "hip") for seg in out[k] for p in seg]
        for seg in out["valleys"]:
            for i_ in (0, 1):
                near = min(ends, key=lambda q: math.dist(q, seg[i_]), default=None)
                if near is not None and math.dist(near, seg[i_]) < 0.05:
                    seg[i_] = tuple(near)
        out["valley"] = sum(math.dist(a, b) for a, b in out["valleys"]) or \
            RC.valley_length(kept, roofs)
    return out


def _crossing(a, b, c, d):
    """Where plan segment a→b crosses c→d, as a fraction of a→b (strictly
    inside both), or None."""
    rx, ry = b[0] - a[0], b[1] - a[1]
    sx, sy = d[0] - c[0], d[1] - c[1]
    den = rx * sy - ry * sx
    if abs(den) < 1e-12:
        return None
    t = ((c[0] - a[0]) * sy - (c[1] - a[1]) * sx) / den
    u = ((c[0] - a[0]) * ry - (c[1] - a[1]) * rx) / den
    if 1e-6 < t < 1 - 1e-6 and -1e-6 <= u <= 1 + 1e-6:
        return t
    return None


def merge_segments(segs, tol=1e-4, gap=1e-3):
    """Straight 3D segments that lie on one line and touch or overlap
    become one piece — a purlin runs as one member from end to end, not
    as the bits each roof part or clip left."""
    def unit(a, b):
        L = math.dist(a, b)
        return tuple((b[i] - a[i]) / L for i in range(3)), L
    items = []
    for a, b in segs:
        if math.dist(a, b) < 1e-6:
            continue
        u, _L = unit(a, b)
        # a canonical direction
        if (u[0], u[1], u[2]) < (0, 0, 0):
            a, b, u = b, a, tuple(-c for c in u)
        items.append([a, b, u])
    used = [False] * len(items)
    out = []
    for i, (a, b, u) in enumerate(items):
        if used[i]:
            continue
        used[i] = True
        o = a
        lo, hi = 0.0, sum((b[k] - a[k]) * u[k] for k in range(3))
        grow = True
        while grow:
            grow = False
            for j, (c, d_, v) in enumerate(items):
                if used[j] or abs(sum(u[k] * v[k] for k in range(3))) < 1 - 1e-6:
                    continue
                # c on the line through o along u?
                tc = sum((c[k] - o[k]) * u[k] for k in range(3))
                off = math.dist(c, tuple(o[k] + u[k] * tc for k in range(3)))
                if off > tol:
                    continue
                td = sum((d_[k] - o[k]) * u[k] for k in range(3))
                s0, s1 = sorted((tc, td))
                if s0 <= hi + gap and s1 >= lo - gap:
                    lo, hi = min(lo, s0), max(hi, s1)
                    used[j] = True
                    grow = True
        out.append([tuple(o[k] + u[k] * lo for k in range(3)),
                    tuple(o[k] + u[k] * hi for k in range(3))])
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


def _profile_width(label) -> float:
    """Width (m) of a steel section across the member (flange / B / b)."""
    _fam, prm = steel_lookup(label)
    for k in ("B", "b", "D", "A", "H"):
        if prm.get(k):
            return float(prm[k]) / 1000.0
    return 0.05


def _end_planes(path, creases, offsets=None):
    """For each end of the straight member ``path``, the vertical plane it
    is cut by: along the crease line (hip, valley, ridge) it stops on —
    pushed back half that member's width (``offsets``) — or a plumb cut
    square to the member in plan. Each plane is ((x, y), (nx, ny))."""
    a, b = path[0], path[-1]
    tx, ty = b[0] - a[0], b[1] - a[1]
    tl = math.hypot(tx, ty)
    planes = []
    for end, sgn in ((a, -1.0), (b, 1.0)):
        best = None
        # At an apex — where a ridge meets its hips — a member runs up to the
        # ridge end: a square, plumb cut there (set back half the ridge's
        # width for one that meets the ridge side on), not a skew cut along
        # whichever hip happened to be nearest (the wedge-shaped ends).
        meet = [k for k, (c, d) in enumerate(creases)
                if min(math.hypot(end[0] - c[0], end[1] - c[1]),
                       math.hypot(end[0] - d[0], end[1] - d[1])) < 0.05]
        if len(meet) >= 2 and tl > 1e-6:
            nx, ny = tx / tl, ty / tl
            back = 0.0
            for k in meet:
                c, d = creases[k]
                dx, dy = d[0] - c[0], d[1] - c[1]
                dl = math.hypot(dx, dy)
                if dl < 1e-6:
                    continue
                # crosses it square, or runs on into it (the centre jack
                # rafter of a hip end into the ridge): stop on its face
                if abs(nx * dx + ny * dy) / dl < 0.05 or \
                        abs(nx * dy - ny * dx) / dl < 0.05:
                    back = max(back, (offsets[k] if offsets else 0.0) / 2.0)
            planes.append(((end[0] - sgn * nx * back, end[1] - sgn * ny * back),
                           (nx, ny)))
            continue
        if tl > 1e-6:
            for k, (c, d) in enumerate(creases):
                dx, dy = d[0] - c[0], d[1] - c[1]
                dl = math.hypot(dx, dy)
                if dl < 1e-6:
                    continue
                # not the member itself nor one parallel to it
                if abs(tx * dy - ty * dx) / (tl * dl) < 0.05:
                    continue
                u = ((end[0] - c[0]) * dx + (end[1] - c[1]) * dy) / (dl * dl)
                if u < -0.02 or u > 1.02:
                    continue
                px, py = c[0] + dx * u, c[1] + dy * u
                dist = math.hypot(end[0] - px, end[1] - py)
                if dist < 0.03 and (best is None or dist < best[0]):
                    best = (dist, (dx / dl, dy / dl), k)
        if best is None:
            if tl < 1e-6:
                planes.append(None)
                continue
            nx, ny = tx / tl, ty / tl              # plumb, square in plan
            planes.append(((end[0], end[1]), (nx, ny)))
            continue
        (dx, dy), k = best[1], best[2]
        nx, ny = -dy, dx
        if (nx * tx + ny * ty) * sgn < 0:          # normal points outward
            nx, ny = -nx, -ny
        back = (offsets[k] if offsets else 0.0) / 2.0
        planes.append(((end[0] - nx * back, end[1] - ny * back), (nx, ny)))
    return planes


def head_to_rafter(g, path, skins, depth, cap=None):
    """The strut's head cut to the rafter's underside (the roof plane
    ``depth`` under the rafter-top surface): its top end follows the slope
    instead of standing square into the rafter."""
    if g is None or len(path) != 2:
        return g
    zmid = (path[0][2] + path[1][2]) / 2
    from PySide6.QtGui import QVector3D
    moves = []
    for v in list(g.mesh.vertices):
        p = v.position
        if p.z() <= zmid:
            continue
        zs = skin_z(p.x(), p.y(), skins)
        if zs is None:
            continue
        z = zs - depth if cap is None else min(zs - depth, cap)
        moves.append((v, QVector3D(p.x(), p.y(), z)))
    for v, q in moves:
        g.mesh.place_vertex(v, q)
    return g


def cut_member(g, path, planes):
    """Cut the two ends of a straight swept member by vertical planes
    (:func:`_end_planes`): the end rings slide along the member onto the
    plane — a plumb cut, or a mitre along a hip or valley."""
    if g is None or len(path) != 2:
        return g
    from PySide6.QtGui import QVector3D
    a = QVector3D(*path[0])
    b = QVector3D(*path[1])
    t = b - a
    L = t.length()
    if L < 1e-6:
        return g
    t = t / L
    mesh = g.mesh
    moves = []
    for v in list(mesh.vertices):
        s_ = QVector3D.dotProduct(v.position - a, t)
        pl = planes[0] if s_ < L / 2 else planes[1]
        if pl is None:
            continue
        (px, py), (nx, ny) = pl
        n = QVector3D(nx, ny, 0.0)
        den = QVector3D.dotProduct(t, n)
        if abs(den) < 0.15:                       # too oblique: leave square
            continue
        k = QVector3D.dotProduct(QVector3D(px, py, 0.0) - v.position, n) / den
        if abs(k) > 1e-7 and abs(k) < L * 0.45:
            moves.append((v, v.position + t * k))
    for v, q in moves:
        mesh.place_vertex(v, q)
    return g


def mitre_planes(path, others):
    """The vertical cut planes at the two ends of a fascia / barge board
    where it meets another board corner to corner: the plane through the
    corner along the bisector of the two boards (in plan), so the pair
    closes in a neat mitre instead of crossing over each other."""
    planes = []
    a, b = path[0], path[-1]
    for end, far in ((a, b), (b, a)):
        t = (far[0] - end[0], far[1] - end[1])
        tl = math.hypot(*t)
        best = None
        if tl > 1e-9:
            t = (t[0] / tl, t[1] / tl)
            for o in others:
                if o is path:
                    continue
                for oe, of in ((o[0], o[-1]), (o[-1], o[0])):
                    if math.hypot(oe[0] - end[0], oe[1] - end[1]) > 1e-3:
                        continue
                    u = (of[0] - oe[0], of[1] - oe[1])
                    ul = math.hypot(*u)
                    if ul < 1e-9:
                        continue
                    u = (u[0] / ul, u[1] / ul)
                    if abs(t[0] * u[0] + t[1] * u[1]) > 0.98:   # in line
                        continue
                    best = u
        if best is None:
            planes.append(None)
            continue
        bis = (t[0] + best[0], t[1] + best[1])
        bl = math.hypot(*bis)
        planes.append(((end[0], end[1]), (-bis[1] / bl, bis[0] / bl)))
    return planes


def uphill(pt, skins, tol=1e-3):
    """The plan direction up the roof slope at a point of the frame (on
    the facet of ``skins`` that holds it), or ``None``."""
    x, y, z = pt
    for poly in skins:
        if len(poly) < 3:
            continue
        inside = False
        n = len(poly)
        for i in range(n):
            (x1, y1, _), (x2, y2, _) = poly[i][:3], poly[(i + 1) % n][:3]
            if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
                inside = not inside
        if not inside:
            continue
        a, b, c = poly[0], poly[1], poly[2]
        ux, uy, uz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
        vx, vy, vz = c[0] - a[0], c[1] - a[1], c[2] - a[2]
        nx, ny, nz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
        if abs(nz) < 1e-9:
            continue
        if nz < 0:
            nx, ny, nz = -nx, -ny, -nz
        zz = a[2] - (nx * (x - a[0]) + ny * (y - a[1])) / nz
        if abs(zz - z) > tol + 0.02:
            continue
        L = math.hypot(nx, ny)
        if L < 1e-9:
            return None
        return (-nx / L, -ny / L)
    return None


def purlin_facing(path, skins, face="ridge"):
    """The purlin's path turned so its C opens up the slope, towards the
    ridge (the usual way: ปากแปหันขึ้นทางอกไก่) — the section opens to the
    left of the path, so the path runs with the ridge on its left."""
    a, b = path[0], path[-1]
    mid = tuple((a[i] + b[i]) / 2 for i in range(3))
    up = uphill(mid, skins)
    if up is None:
        return path
    if face == "eave":
        up = (-up[0], -up[1])
    dx, dy = b[0] - a[0], b[1] - a[1]
    if -dy * up[0] + dx * up[1] < 0:
        return [b, a]
    return path


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
             "purlin": "แป", "post": "ดั้ง", "valley": "ตะเฆ่ราง"}
    sizes = dict(s, valley=s["hip"])
    # The lines members stop on, and how wide each is (a rafter stops at
    # the face of the hip or ridge, half its width short of the line).
    creases = ([(a, b) for a, b in lines["hip"]] +
               [(a, b) for a, b in lines["valleys"]] +
               [(a, b) for a, b in lines["ridge"]])
    widths = ([_profile_width(s["hip"])] * (len(lines["hip"]) +
                                            len(lines["valleys"])) +
              [_profile_width(s["ridge"])] * len(lines["ridge"]))
    no_width = [0.0] * len(widths)
    ties = lines.get("tie") or []

    def truss_turn(path):
        """A post or strut stands in its truss: the section's depth along
        the tie under it (in the truss plane), so the braces butt on its
        face and nothing crosses it."""
        x, y = path[0][0], path[0][1]
        for a, b in ties:
            dx, dy = b[0] - a[0], b[1] - a[1]
            L_ = math.hypot(dx, dy)
            if L_ < 1e-6:
                continue
            if abs((x - a[0]) * dy - (y - a[1]) * dx) / L_ < 0.02:
                return 90.0 if abs(dx) > abs(dy) else 0.0
        return 0.0
    # the eave end of a hip stays inside the corner of the fascia boards
    ft = float(s.get("fascia_t", 0.025)) if s.get("fascia", True) else 0.0
    hw = _profile_width(s["hip"])
    eave_z = min((p[2] for poly in lines["skin"] for p in poly), default=None)

    def hip_in(path):
        a_, b_ = path[0], path[-1]
        if eave_z is None:
            return path
        lo, hi = (a_, b_) if a_[2] <= b_[2] else (b_, a_)
        if abs(lo[2] - eave_z) > 0.02:
            return path
        Lp = math.hypot(hi[0] - lo[0], hi[1] - lo[1])
        if Lp < 0.3:
            return path
        back = ft / 2 * math.sqrt(2) + hw / 2 + 0.005
        t = back / Lp
        lo2 = tuple(lo[k] + (hi[k] - lo[k]) * t for k in range(3))
        return [lo2, hi] if a_[2] <= b_[2] else [hi, lo2]
    for kind in ("ridge", "hip", "valley", "rafter", "post"):
        fam, params = steel_lookup(sizes[kind])
        paths = lines["valleys"] if kind == "valley" else lines[kind]
        if kind == "hip":
            paths = [hip_in(p_) for p_ in paths]
        dbl = bool(s.get(f"dbl_{kind}"))
        bw = _profile_width(sizes[kind])
        for path in paths:
            L = math.dist(path[0], path[-1])
            kgm = P.weight_per_m(fam, params)
            # วางคู่: two C back to back, their webs on the member's line
            sides = [((bw / 2, 0.0), False), ((-bw / 2, 0.0), True)] if dbl else \
                [((0.0, 0.0), False)]
            for off, mir in sides:
                g = _member("roof", kind, names[kind], fam, params, path,
                            anchor="tc" if kind != "post" else "c",
                            rotation=truss_turn(path) if kind == "post" else 0.0,
                            offset=off, mirror=mir,
                            ifc="IfcMember", key=f"{names[kind]} {sizes[kind]}",
                            name=f"{names[kind]} {sizes[kind]}"
                                 f"{' (วางคู่)' if dbl else ''} · ยาว {L:.2f} ม.",
                            info=[("ชนิด", f"{names[kind]} (โครงหลังคาเหล็ก)"),
                                  ("หน้าตัด", sizes[kind] + (" วางคู่ (2 ตัวประกบ)"
                                                            if dbl else " วางเดี่ยว")),
                                  ("ความยาว", f"{L:.2f} ม."),
                                  ("น้ำหนัก", f"{L * kgm:.2f} กก. ({kgm:.2f} กก./ม.)"),
                                  ("รายการ BOQ", "โครงหลังคาเหล็ก + ทาสีกันสนิม")])
                if kind in ("rafter", "hip", "valley", "ridge"):
                    g = cut_member(g, path, _end_planes(
                        path, creases, widths if kind == "rafter" else no_width))
                elif kind == "post" and g is not None:
                    # under the ridge, and under the rafters that meet it there
                    head_to_rafter(g, path, lines["skin"], lift_of(s) / math.cos(
                        math.radians(float(s["pitch"]))), cap=max(path[0][2], path[-1][2]))
                add(g, kind)
    for kind, key, label, why in (
            ("wallplate", "wallplate", "อะเส",
             "อะเสเหล็กบนคานรัดรอบ รับจันทัน (ยึดเพลทฝังในคาน ค.ส.ล.)"),
            ("tiebeam", "tiebeam", "ขื่อ",
             "ขื่อเหล็กพาดจากอะเสถึงอะเส ตามแนวเสา รับคานรับดั้ง"),
            ("rbeam", "tiebeam", "คานรับดั้ง",
             "คานรับดั้งวางบนขื่อตามแนวอกไก่ ดั้งทุกตัวตั้งบนคานนี้"),
            ("strut", "strut", "ตุ๊กตา",
             "ตุ๊กตาเหล็กจากขื่อขึ้นรับจันทันกลางช่วง (โครงถักแบบดั้งกลาง)"),
            ("brace", "strut", "ค้ำยัน",
             "ค้ำยันจากโคนดั้งไปหัวตุ๊กตา ถ่ายแรงจันทันลงดั้ง")):
        fam, params = steel_lookup(s[key])
        kgm = P.weight_per_m(fam, params)
        for path in lines.get({"wallplate": "plate", "tiebeam": "tie"}.get(kind, kind)) or []:
            if kind in ("strut", "brace") and not s.get("struts", True):
                continue
            L = math.dist(path[0], path[-1])
            if kind == "wallplate" and s.get("dbl_wallplate"):
                bw_ = _profile_width(s[key])
                g2 = _member("roof", kind, label, fam, params, path, anchor="tc",
                             offset=(-bw_ / 2, 0.0), mirror=True, ifc="IfcMember",
                             key=f"{label} {s[key]}", name=f"{label} {s[key]} (วางคู่) · ยาว {L:.2f} ม.",
                             info=[("ชนิด", f"{label} (โครงหลังคาเหล็ก)"),
                                   ("หน้าตัด", f"{s[key]} วางคู่ (2 ตัวประกบ)"),
                                   ("ความยาว", f"{L:.2f} ม."),
                                   ("รายการ BOQ", "หมวด 5 งานโครงสร้างเหล็ก")])
                if g2 is not None:
                    add(cut_member(g2, path, mitre_planes(path, lines.get("plate") or [])), kind)
            g = _member("roof", kind, label, fam, params, path,
                        anchor="c" if kind in ("strut", "brace") else "tc",
                        rotation=truss_turn(path) if kind == "strut" else 0.0,
                        offset=(_profile_width(s[key]) / 2, 0.0)
                        if kind == "wallplate" and s.get("dbl_wallplate") else (0.0, 0.0),
                        ifc="IfcMember", key=f"{label} {s[key]}",
                        name=f"{label} {s[key]} · ยาว {L:.2f} ม.",
                        info=[("ชนิด", f"{label} (โครงหลังคาเหล็ก)"),
                              ("หน้าที่", why), ("หน้าตัด", s[key]),
                              ("ความยาว", f"{L:.2f} ม."),
                              ("น้ำหนัก", f"{L * kgm:.2f} กก. ({kgm:.2f} กก./ม.)"),
                              ("รายการ BOQ", "หมวด 5 งานโครงสร้างเหล็ก")])
            if g is not None and kind == "strut":
                head_to_rafter(g, path, lines["skin"], lift_of(s) / math.cos(
                    math.radians(float(s["pitch"]))))
            elif g is not None and kind == "wallplate":
                g = cut_member(g, path, mitre_planes(path, lines.get("plate") or []))
            elif g is not None and kind == "brace":
                # butt cuts: plumb on the faces of the post and the strut
                a_, b_ = path[0], path[-1]
                dx, dy = b_[0] - a_[0], b_[1] - a_[1]
                dl = math.hypot(dx, dy) or 1.0
                n_ = (dx / dl, dy / dl)
                g = cut_member(g, path, [((a_[0], a_[1]), n_), ((b_[0], b_[1]), n_)])
            add(g, kind)
    if s.get("head_plate", True) and (lines.get("plate") or lines.get("tie")):
        for (x, y) in lines.get("heads") or []:
            add(head_plate(x, y, lines["z0"]), "headplate")
    fam, params = steel_lookup(s["purlin"])
    kgm = P.weight_per_m(fam, params)
    for pl in lines["purlin"]:
        L = P.path_length(pl["path"], pl["closed"])
        if not pl["closed"] and len(pl["path"]) == 2:
            pl = dict(pl, path=purlin_facing(pl["path"], lines["skin"],
                                             s.get("purlin_face", "ridge")))
        g = _member("roof", "purlin", "แป", fam, params, pl["path"],
                    anchor="bc", ifc="IfcMember", closed=pl["closed"],
                    key=f"แป {s['purlin']}",
                    name=f"แป {s['purlin']} · ยาว {L:.2f} ม.",
                    info=[("ชนิด", "แป (โครงหลังคาเหล็ก)"),
                          ("หน้าตัด", s["purlin"]), ("ความยาว", f"{L:.2f} ม."),
                          ("น้ำหนัก", f"{L * kgm:.2f} กก."),
                          ("รายการ BOQ", "โครงหลังคาเหล็ก + ทาสีกันสนิม")])
        if not pl["closed"] and len(pl["path"]) == 2:
            g = cut_member(g, pl["path"], _end_planes(pl["path"], creases))
        add(g, "purlin")
    if s.get("fascia", True):
        fp = dict(b=_mm(s.get("fascia_t", 0.025)), h=_mm(s.get("fascia_h", 0.20)))
        boards = [("fascia", "เชิงชาย", "เชิงชาย + ทับเชิงชาย ไม้สำเร็จรูป", p_)
                  for p_ in lines["eave"]] + \
                 [("barge", "ปั้นลม", "ปั้นลม + ทับปั้นลม ไม้สำเร็จรูป", p_)
                  for p_ in lines["barge"]]
        for kind, label, what, path in boards:
            L = math.dist(path[0], path[-1])
            g = _member("roof", kind, label, "rect", fp, path,
                        anchor="tc", ifc="IfcMember", key=label,
                        name=f"{label} · ยาว {L:.2f} ม.",
                        info=[("ชนิด", what), ("ความยาว", f"{L:.2f} ม."),
                              ("มุม", "ตัดเฉียงชนมุม (บากมุม 45°)"),
                              ("รายการ BOQ", "หมวด 7 งานหลังคา · ว480 2.1.10")])
            add(cut_member(g, path, mitre_planes(path, [b[3] for b in boards])),
                kind)
    from core.wanic_catalog import COLORS, roof_tile, tile_color
    _tc, tile = roof_tile(s)
    tcolor = tile_color(s)
    for g in out:
        k = ((g.ext or {}).get(EXT_KEY) or {}).get("kind")
        if k in ("fascia", "barge"):
            g.material = {"color": COLORS["fascia"]}
    lift = float(params.get("H", params.get("D", params.get("A", 80)))) / 1000.0
    if lines.get("gable"):
        # the small gables of a มะนิลา closed with boards (ปิดหน้าจั่ว)
        g = roof_skin(lines["gable"], 0.0)
        if g is not None:
            g.material = {"color": (0.93, 0.92, 0.88), "mat": "ปิดหน้าจั่ว"}
            add(_tag(g, "roof", "gable", "ปิดหน้าจั่ว",
                     [("ชนิด", "ปิดหน้าจั่วหลังคามะนิลา (ไม้ฝาสำเร็จรูป)")]), "gable")
    if s.get("skin") and lines["skin"]:
        g = roof_skin(lines["skin"], lift)
        if g is not None:
            g.material = {"color": tuple(c * 0.55 for c in tcolor),
                          "mat": "แผ่นรองหลังคา"}
            add(_tag(g, "roof", "skin", "หลังคา"), "skin")
        if s.get("tiles_3d", True):
            add(roof_tiles(lines, s, lift + 0.01), "tiles")
        for path in lines["valleys"]:
            add(valley_gutter(path, lines["skin"], lift + 0.004), "gutter")
    if s.get("caps", True) and s.get("skin"):
        # Ridge and hip caps (ครอบสัน / ครอบตะเข้สัน) and, on a gable, the
        # verge caps (ครอบข้าง) — laid piece by piece at the maker's
        # effective length, each lapping the one below — and the special
        # pieces where they end or meet (หางมน ปิดจั่ว สามทาง สี่ทาง).
        amp = tile["wave"][2]
        up = lift + amp + 0.02
        each = float(tile.get("cap") or 0.33)
        # The hip caps run on past the eave corner by ``hip_cap_out``
        # (10 cm in plan, set in the settings) so the end piece (หางมน)
        # sits clear beyond the fascia, the way a tiler finishes a hip.
        out_ = float(s.get("hip_cap_out", 0.10))
        hips = []
        for a_, b_ in lines["hip"]:
            lo, hi = (a_, b_) if a_[2] <= b_[2] else (b_, a_)
            L2 = math.hypot(hi[0] - lo[0], hi[1] - lo[1])
            t = -out_ / L2 if L2 > 1e-6 else 0.0
            lo2 = tuple(lo[i] + (hi[i] - lo[i]) * t for i in range(3))
            hips.append([lo2, hi] if a_[2] <= b_[2] else [hi, lo2])
        cap_lines = dict(lines, hip=hips)
        if s.get("roof") == "shed":
            # a lean-to has no ridge: its high edge and sloping sides take
            # the side cap (ครอบข้าง / ครอบชายบน) — an L folded over the edge
            for path in lines["ridge"] + high_eaves(lines) + lines["barge"]:
                add(cap_edge(path, lines["skin"], tcolor, up,
                             float(tile.get("verge") or each)), "cap")
        else:
            for kind, paths, name, piece in (
                    ("ridge", lines["ridge"], "ครอบสัน", each),
                    ("hip", cap_lines["hip"], "ครอบตะเข้สัน", each),
                    ("barge", lines["barge"], "ครอบข้าง",
                     float(tile.get("verge") or each))):
                for path in paths:
                    add(cap_pieces(path, 0.13, tcolor, name, up, piece), "cap")
            for kind, pt, name in cap_specials(cap_lines):
                add(cap_dome(pt, 0.15 if kind != "hip_end" else 0.13, tcolor,
                             name, up, kind), "cap")
    if s.get("gutters", True) and lines["eave"]:
        for g, kind in gutter_members(data, lines, s):
            add(g, kind)
    if s.get("soffit", True):
        for g in soffit_members(data, lines, s):
            add(g, ((g.ext or {}).get(EXT_KEY) or {}).get("kind", "soffit"))
    seen_cols = []
    for inf in gable_infill(data, lines):
        add(infill_member(inf), "infill")
        # tie columns (เสาเอ็น) at the ends of each panel, up to the rafters
        t = wall_spec(s, True)["t"]
        for (a, zt), (px, py) in ((inf["prof"][0], inf["p0"]), (inf["prof"][-1], inf["p1"])):
            if zt - inf["z0"] < 0.3 or any(math.hypot(px - q[0], py - q[1]) < 0.05
                                           for q in seen_cols):
                continue
            seen_cols.append((px, py))
            add(_member("roof", "band", "เสาเอ็นผนังหน้าจั่ว", "rect",
                        dict(b=_mm(t), h=_mm(t)),
                        [(px, py, inf["z0"]), (px, py, zt - 0.02)], ifc="IfcColumn",
                        info=[("ชนิด", "เสาเอ็น ค.ส.ล. ผนังหน้าจั่ว/ใต้หลังคา")]), "band")
    return out, count


def _prism(mesh, quad, thick, attrs):
    """A thin plate: the quad ``quad`` (4 QVector3D, any order round) and
    its copy moved by ``thick`` (a QVector3D), closed round the sides."""
    top = list(quad)
    bot = [p + thick for p in quad]
    from PySide6.QtGui import QVector3D
    n = QVector3D.crossProduct(top[1] - top[0], top[2] - top[0])
    if QVector3D.dotProduct(n, thick) > 0:
        top = top[::-1]
        bot = bot[::-1]
    faces = [top, bot[::-1]]
    for i in range(4):
        j = (i + 1) % 4
        faces.append([top[i], bot[i], bot[j], top[j]][::-1])
    for f_ in faces:
        f = mesh.add_face(f_)
        if f is not None and attrs:
            f.attrs.update(attrs)


def cap_edge(path, skins, color, lift, piece=0.30):
    """ครอบข้าง (side cap) along a lean-to's high edge or a verge: a flap
    lying on the roof 0.15 m in from the edge, folded down 0.12 m over the
    fascia/barge, laid in pieces of ``piece`` m."""
    from PySide6.QtGui import QVector3D

    from core.group import Group
    from core.mesh import Mesh
    a = QVector3D(*path[0])
    b = QVector3D(*path[-1])
    t = b - a
    L = t.length()
    if L < 0.05:
        return None
    tn = t.normalized()
    w = QVector3D(-tn.y(), tn.x(), 0.0)
    if w.length() < 1e-6:
        return None
    w = w.normalized()
    mid = (a + b) * 0.5
    zin = skin_z(mid.x() + w.x() * 0.3, mid.y() + w.y() * 0.3, skins)
    zout = skin_z(mid.x() - w.x() * 0.3, mid.y() - w.y() * 0.3, skins)
    if zin is None and zout is not None:
        w = -w
        zin = zout
    if zin is None:
        return None
    slope = (zin - skin_z(mid.x(), mid.y(), skins) if skin_z(mid.x(), mid.y(), skins) is not None
             else 0.0) / 0.3
    up = QVector3D(0, 0, lift)
    a2, b2 = a + up, b + up
    fl = QVector3D(w.x() * 0.15, w.y() * 0.15, slope * 0.15)
    out = QVector3D(-w.x() * 0.012, -w.y() * 0.012, 0.0)
    mesh = Mesh()
    attrs = {"color": tuple(color)}
    n = max(1, int(math.ceil(L / max(piece, 0.05) - 1e-9)))
    th = QVector3D(0, 0, 0.012)
    for k in range(n):
        p0 = a2 + t * (k / n)
        p1 = a2 + t * ((k + 1) / n)
        lap = 0.006 if k % 2 else 0.0
        _prism(mesh, [p0, p1, p1 + fl, p0 + fl], th + QVector3D(0, 0, lap), attrs)
        _prism(mesh, [p0 + out, p1 + out, p1 + out + QVector3D(0, 0, -0.13),
                      p0 + out + QVector3D(0, 0, -0.13)],
               QVector3D(-w.x() * 0.012, -w.y() * 0.012, 0.0), attrs)
    _ = b2
    g = Group(mesh, name=f"ครอบข้าง · {n} แผ่น ยาว {L:.2f} ม.")
    g.ifc = {"class": "IfcCovering", "name": "ครอบข้าง"}
    return _tag(g, "roof", "cap", "ครอบข้าง",
                [("ชนิด", "ครอบข้าง (ครอบชายบน/ครอบปั้นลม) หลังคาเพิง"),
                 ("ความยาว", f"{L:.2f} ม."), ("จำนวน", f"{n} แผ่น"),
                 ("รายการ BOQ", "ครอบหลังคา (หลักเกณฑ์ 4.2 ข้อ 1.2 เผื่อ 3%)")])


def gutter_runs(lines, s):
    """[(a, b, outward (nx, ny))] — the eaves that take a gutter (2-D plan
    ends, the eave height) with the side the water falls off."""
    out = []
    for path in lines["eave"]:
        a, b = path[0], path[-1]
        L = math.hypot(b[0] - a[0], b[1] - a[1])
        if L < 0.3:
            continue
        ux, uy = (b[0] - a[0]) / L, (b[1] - a[1]) / L
        n = (-uy, ux)
        mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
        zi = skin_z(mx + n[0] * 0.3, my + n[1] * 0.3, lines["skin"])
        zo = skin_z(mx - n[0] * 0.3, my - n[1] * 0.3, lines["skin"])
        if zi is not None and zo is not None:
            continue                                   # between two roofs
        if zi is not None:
            n = (-n[0], -n[1])                         # the roof is on the left
        z_in = zi if zi is not None else zo
        if z_in is None or z_in < a[2] + 0.02:
            continue                                   # a high edge: nothing runs off it
        out.append((a, b, n))
    return out


def high_eaves(lines):
    """The eave lines the roof falls away from (a lean-to's top edge)."""
    out = []
    for path in lines["eave"]:
        a, b = path[0], path[-1]
        L = math.hypot(b[0] - a[0], b[1] - a[1])
        if L < 0.3:
            continue
        ux, uy = (b[0] - a[0]) / L, (b[1] - a[1]) / L
        mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
        zs = [skin_z(mx - uy * 0.3 * k, my + ux * 0.3 * k, lines["skin"]) for k in (1, -1)]
        zs = [z for z in zs if z is not None]
        if zs and max(zs) < a[2] - 0.02:
            out.append(path)
    return out


def gutter_members(data, lines, s):
    """รางน้ำชายคา and ท่อลงน้ำ (งวงช้าง): a gutter hung on the fascia
    along every eave, and a downspout from each end of a run (and every
    ~10 m) — a swan-neck back to the wall, down the column face, and a
    shoe onto the walkway."""
    from core import wanic_mep as M
    runs = gutter_runs(lines, s)
    if not runs:
        return []
    gl = -floor_lift(s)
    ov = float(s.get("overhang", 0.6))
    E = elements(data)
    half = float(E["lib"]["C1"]["b"]) / 2
    rooms = E["floors"][0]["rooms"]
    white = {"color": (0.92, 0.92, 0.90)}
    gutters = []
    total = 0.0
    spouts = []
    for a, b, n in runs:
        L = math.hypot(b[0] - a[0], b[1] - a[1])
        total += L
        u = ((b[0] - a[0]) / L, (b[1] - a[1]) / L)
        g = _Boxes((a[0], a[1]), u, 0.0)
        sg = 1.0 if (-u[1] * n[0] + u[0] * n[1]) > 0 else -1.0     # n on the left?
        ze = a[2] - 0.02
        d0, d1 = sorted((sg * 0.02, sg * 0.17))
        g.box(0.0, L, d0, d1, ze - 0.15, ze - 0.14, white)              # bottom
        e0, e1 = sorted((sg * 0.02, sg * 0.028))
        g.box(0.0, L, e0, e1, ze - 0.15, ze - 0.02, white)              # back
        f0, f1 = sorted((sg * 0.162, sg * 0.17))
        g.box(0.0, L, f0, f1, ze - 0.15, ze - 0.04, white)              # lip
        for s_ in (0.0, L - 0.006):
            g.box(s_, s_ + 0.006, d0, d1, ze - 0.15, ze - 0.04, white)  # ends
        gg = g.group(f"รางน้ำชายคา · ยาว {L:.2f} ม.", "roof", "eave_gutter", "รางน้ำชายคา",
                     "IfcPipeSegment")
        if gg is not None:
            gg.ext[EXT_KEY]["info"] = [
                ["ชนิด", "รางน้ำชายคาไวนิล/สังกะสี 6\" แขวนตะขอทุก 0.60 ม."],
                ["ความยาว", f"{L:.2f} ม."], ["ลาด", "ลาดลงท่อลงน้ำ 1:200"],
                ["รายการ BOQ", "หมวด 7 งานหลังคา"]]
            gutters.append(gg)
        k = max(1, int(math.ceil(L / 10.0)))
        cand = [0.15] + [L * i / k for i in range(1, k)] + [L - 0.15]
        for t_ in cand:
            px, py = a[0] + u[0] * t_ + n[0] * 0.095, a[1] + u[1] * t_ + n[1] * 0.095
            inward = [(-n[0], -n[1])]
            if t_ < 0.2:
                inward.append(u)
            elif t_ > L - 0.2:
                inward.append((-u[0], -u[1]))
            spouts.append(((px, py, ze - 0.15), inward))
    legs = []
    seen = []
    for (px, py, pz), inward in spouts:
        if any(math.hypot(px - q[0], py - q[1]) < 0.8 for q in seen):
            continue
        seen.append((px, py))
        back = max(ov - half - 0.06 + 0.095, 0.0)
        wx, wy = px, py
        for ix, iy in inward:
            tx, ty = wx + ix * back, wy + iy * back
            if room_at(rooms, tx, ty) is None:
                wx, wy = tx, ty
        zn = pz - 0.10
        zw = zn - max(math.hypot(wx - px, wy - py), 0.05) * 0.8
        legs += [((px, py, pz), (px, py, zn))]
        if math.hypot(wx - px, wy - py) > 0.03:
            legs += [((px, py, zn), (wx, wy, zw))]
        else:
            zw = zn
        legs += [((wx, wy, zw), (wx, wy, gl + 0.20))]
        ox, oy = wx - inward[0][0] * 0.15, wy - inward[0][1] * 0.15
        legs += [((wx, wy, gl + 0.20), (ox, oy, gl + 0.08))]
    out = [(g, "eave_gutter") for g in gutters]
    g = M._pipes_group(sys_modules_B(), legs, 75.0, (0.92, 0.92, 0.90),
                       f"ท่อลงน้ำ (งวงช้าง) PVC Ø 3\" · {len(seen)} จุด", "downspout",
                       [("ชนิด", "ท่อลงน้ำ PVC Ø 3\" สีขาว คอห่าน (งวงช้าง) ยึดเสาด้วยแคลมป์ทุก 1.50 ม."),
                        ("จำนวน", f"{len(seen)} จุด"),
                        ("ปลายท่อ", "ข้องอลงทางเท้า/รางระบายน้ำ"),
                        ("รายการ BOQ", "หมวด 7 งานหลังคา")], fittings=True)
    if g is not None:
        g.ext[EXT_KEY]["part"] = "roof"
        out.append((g, "downspout"))
    return out


def sys_modules_B():
    import sys as _sys
    return _sys.modules[__name__]


def gable_infill(data, lines=None) -> list:
    """The brick walls between the top ring beam and the roof where the
    roof rises over an outside wall — a gable end (หน้าจั่ว), the high
    side and the two sloping sides of a เพิงหมาแหงน: [{"p0", "p1" (the
    wall's centre line), "z0", "prof": [(dist, z top)…], "t", "area"}].
    The top follows the underside of the rafters, any pitch."""
    lines = lines if lines is not None else roof_lines(data)
    if not lines or not lines.get("skin"):
        return []
    E = elements(data)
    s = E["settings"]
    if not s.get("walls", True) or not E["n"]:
        return []
    k = E["n"] - 1
    z0 = E["n"] * E["H"]
    cosp = math.cos(math.radians(float(s["pitch"]))) or 1.0
    under = _dim(s["rafter"]) / cosp + 0.01
    sp = wall_spec(s, True)
    out = []
    for wl in E["walls"]:
        if wl["floor"] != k or wl["L"] < 0.3:
            continue
        p0, p1, L = wl["p0"], wl["p1"], wl["L"]
        ux, uy = (p1[0] - p0[0]) / L, (p1[1] - p0[1]) / L
        if not wl.get("exterior") and s.get("roof") != "shed":
            # (under a lean-to the ceiling follows the rafters, so every
            # wall goes up to it) — else an inside wall only where two
            # roofs meet at a step (the
            # high side of one shed over the other): close the step
            mx, my = (p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2
            zs = [skin_z(mx - uy * d, my + ux * d, lines["skin"]) for d in (0.6, 0.3, -0.3, -0.6)]
            if any(z_ is None for z_ in zs):
                continue
            # each side's surface carried to the wall line: a step, not a slope
            za, zb = 2 * zs[1] - zs[0], 2 * zs[2] - zs[3]
            if abs(za - zb) < 0.15:
                continue
        off = wall_offset(E, wl)
        ox, oy = wl.get("out") or (0.0, 0.0)
        c0 = (p0[0] + ox * off, p0[1] + oy * off)
        n_ = max(int(L / 0.05), 2)
        prof = []
        for i in range(n_ + 1):
            a = L * i / n_
            zz = skin_z(c0[0] + ux * a, c0[1] + uy * a, lines["skin"])
            prof.append((a, (zz - under) if zz is not None else z0))
        if max(zt - z0 for _a, zt in prof) < 0.25:
            continue
        # keep the corners of the profile only
        keep = [prof[0]]
        for i in range(1, len(prof) - 1):
            (a0, z_0), (a1, z_1), (a2, z_2) = keep[-1], prof[i], prof[i + 1]
            if abs((z_1 - z_0) * (a2 - a0) - (z_2 - z_0) * (a1 - a0)) > 1e-4:
                keep.append(prof[i])
        keep.append(prof[-1])
        keep = [(a, max(zt, z0)) for a, zt in keep]
        area = sum((b - a) * ((za - z0) + (zb - z0)) / 2
                   for (a, za), (b, zb) in zip(keep, keep[1:]))
        out.append({"p0": c0, "p1": (c0[0] + ux * L, c0[1] + uy * L), "z0": z0,
                    "prof": keep, "t": sp["T"], "area": area, "wall": wl})
    return out


def infill_member(inf):
    """One gable/shed infill wall as a closed prism, tagged a wall."""
    from PySide6.QtGui import QVector3D

    from core.group import Group
    from core.mesh import Mesh
    (x0, y0), (x1, y1) = inf["p0"], inf["p1"]
    L = math.hypot(x1 - x0, y1 - y0) or 1.0
    ux, uy = (x1 - x0) / L, (y1 - y0) / L
    nx, ny = -uy, ux
    t = inf["t"] / 2
    z0 = inf["z0"]
    prof = [(a, z0) for a in (inf["prof"][-1][0], inf["prof"][0][0])]
    outline = [(a, z) for a, z in inf["prof"] if True]
    # the face polygon: along the top, back along the bottom
    face = outline + prof
    face = [p for i, p in enumerate(face) if i == 0 or
            abs(p[0] - face[i - 1][0]) + abs(p[1] - face[i - 1][1]) > 1e-6]

    def P3(a, z, d):
        return QVector3D(x0 + ux * a + nx * d, y0 + uy * a + ny * d, z)
    mesh = Mesh()
    front = [P3(a, z, t) for a, z in face]
    back = [P3(a, z, -t) for a, z in face]
    mesh.add_face(front[::-1])
    mesh.add_face(back)
    m = len(face)
    for i in range(m):
        j = (i + 1) % m
        mesh.add_face([front[i], front[j], back[j], back[i]])
    g = Group(mesh, name="ผนังก่ออิฐปิดหน้าจั่ว/ใต้หลังคา")
    g.ifc = {"class": "IfcWall", "name": "ผนังก่ออิฐปิดหน้าจั่ว"}
    g.material = {"color": (0.93, 0.91, 0.86), "mat": "ผนังฉาบปูนทาสี"}
    return _tag(g, "roof", "infill", "ผนังปิดหน้าจั่ว",
                [("ชนิด", "ผนังก่ออิฐฉาบปูนปิดหน้าจั่ว / ใต้หลังคา (ก่อจากคานบนถึงใต้จันทัน)"),
                 ("พื้นที่", f"{inf['area']:.2f} ตร.ม."),
                 ("ความหนารวม", f"{inf['t'] * 100:g} ซม."),
                 ("หมายเหตุ", "ทำเสาเอ็น/ทับหลังตามแนวลาดทุก 2.5 ม. ตามมาตรฐานงานก่อ")])


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


def _barrel(mesh, a, b, side, up, r0, r1, attrs, n=8, close=(True, True)):
    """A half-round from ``a`` (radius r0) to ``b`` (r1) into ``mesh``."""
    def ring(c, r):
        return [c + side * (r * math.cos(math.pi * k / n)) +
                up * (r * 0.75 * math.sin(math.pi * k / n)) for k in range(n + 1)]
    ra, rb = ring(a, r0), ring(b, r1)
    for k in range(n):
        f = mesh.add_face([ra[k], rb[k], rb[k + 1], ra[k + 1]])
        if f is not None:
            f.attrs.update(attrs)
    for end, rr in ((ra, close[0]), (rb, close[1])):
        if rr:
            f = mesh.add_face(list(end))
            if f is not None:
                f.attrs.update(attrs)


def _frame_of(path):
    from PySide6.QtGui import QVector3D
    a = QVector3D(*path[0])
    b = QVector3D(*path[-1])
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
    return a, b, t, side, up


def cap_pieces(path, radius, color, name, lift, piece=0.33):
    """Ridge / hip / verge caps laid piece by piece: each piece
    ``piece`` m long (the maker's effective length), its lower end a
    little wider where it laps over the piece below."""
    from core.group import Group
    from core.mesh import Mesh
    fr = _frame_of(path)
    if fr is None:
        return None
    a, b, t, side, up = fr
    if b.z() > a.z() + 1e-6:                     # lay from the low end up
        a, b, t, side = b, a, -t, -side
        up = up if up.z() >= 0 else -up
    a, b = a + up * lift, b + up * lift
    L = (b - a).length()
    n = max(1, int(math.ceil(L / max(piece, 0.05) - 1e-9)))
    mesh = Mesh()
    attrs = {"color": tuple(color)}
    for k in range(n):
        p0 = a + (b - a) * (k / n)
        p1 = a + (b - a) * ((k + 1) / n)
        # the lap: the low (downhill) end of a piece is the wider one
        _barrel(mesh, p1, p0, side, up, radius, radius * 1.07, attrs)
    if not mesh.faces:
        return None
    g = Group(mesh, name=f"{name} · {n} แผ่น ยาว {L:.2f} ม.")
    g.ifc = {"class": "IfcCovering", "name": name}
    return _tag(g, "roof", "cap", name,
                [("ชนิด", name), ("ความยาว", f"{L:.2f} ม."),
                 ("จำนวน", f"{n} แผ่น (ยาวใช้งาน {piece:.3f} ม./แผ่น)"),
                 ("รายการ BOQ", "ครอบหลังคา (หลักเกณฑ์ 4.2 ข้อ 1.2 เผื่อ 3%)")])


cap_barrel = cap_pieces            # the older name, used by older callers


def cap_specials(lines, tol=0.05):
    """(kind, point, Thai name) of every special cap piece: the foot of a
    hip (ครอบโค้งหางมน) and of a verge (ครอบข้างปิดชาย), a ridge end at a
    gable (ครอบโค้งปิดจั่ว), and where ridges and hips meet (ครอบโค้งสองทาง
    สามทาง สี่ทาง) — the same count :func:`core.wanic_roofclip.accessories`
    bills."""
    from core.wanic_catalog import ACCESSORIES
    pts, out = [], []
    for a, b in lines.get("ridge", []):
        pts += [(a, "r"), (b, "r")]
    for a, b in lines.get("hip", []):
        lo, hi = (a, b) if a[2] <= b[2] else (b, a)
        pts.append((hi, "h"))
        out.append(("hip_end", lo, ACCESSORIES["hip_end"]))
    for a, b in lines.get("barge", []):
        lo, hi = (a, b) if a[2] <= b[2] else (b, a)
        pts.append((hi, "b"))
        out.append(("verge_end", lo, ACCESSORIES["verge_end"]))
    clusters = []
    for p, k in pts:
        for c in clusters:
            if math.dist(p, c["p"]) <= tol:
                c[k] = c.get(k, 0) + 1
                break
        else:
            clusters.append({"p": p, k: 1})
    from core.wanic_roofclip import junction
    for c in clusters:
        kind = junction(c.get("r", 0), c.get("h", 0), c.get("b", 0))
        if kind:
            out.append((kind, c["p"], ACCESSORIES[kind]))
    return out


def cap_dome(pt, radius, color, name, lift, kind=""):
    """A rounded special cap (ครอบปิดหัว / หางมน / สามทาง …) at a point."""
    from PySide6.QtGui import QVector3D

    from core.group import Group
    from core.mesh import Mesh
    c = QVector3D(pt[0], pt[1], pt[2] + lift)
    mesh = Mesh()
    attrs = {"color": tuple(color)}
    m, n = 12, 4
    rings = []
    for i in range(n + 1):
        phi = (math.pi / 2) * i / n
        rr = radius * math.cos(phi)
        zz = radius * 0.75 * math.sin(phi)
        rings.append([c + QVector3D(rr * math.cos(2 * math.pi * j / m),
                                    rr * math.sin(2 * math.pi * j / m), zz)
                      for j in range(m)])
    for i in range(n):
        for j in range(m):
            q = [rings[i][j], rings[i][(j + 1) % m], rings[i + 1][(j + 1) % m],
                 rings[i + 1][j]]
            if i == n - 1:
                q = q[:3]
            f = mesh.add_face(q)
            if f is not None:
                f.attrs.update(attrs)
    f = mesh.add_face(list(reversed(rings[0])))
    if f is not None:
        f.attrs.update(attrs)
    g = Group(mesh, name=name)
    g.ifc = {"class": "IfcCovering", "name": name}
    return _tag(g, "roof", "cap", name,
                [("ชนิด", name), ("จำนวน", "1 แผ่น"),
                 ("รายการ BOQ", "อุปกรณ์ครอบพิเศษ (นับตามจุดต่อ)")])


def valley_gutter(path, skin, lift, width=0.20):
    """The valley gutter (รางน้ำตะเข้สำเร็จรูป สแตนเลส): a V of sheet
    lying on the two roof faces that meet in the valley, ``width`` m each
    side, under the tiles."""
    from PySide6.QtGui import QVector3D

    from core.group import Group
    from core.mesh import Mesh
    from core.wanic_roofclip import plane_of
    a = QVector3D(*path[0])
    b = QVector3D(*path[1])
    t = b - a
    if t.length() < 0.05:
        return None
    mid = (a + b) * 0.5
    faces = []
    for poly in skin:
        if len(poly) < 3:
            continue
        pl = plane_of(poly)
        if pl is None:
            continue
        z = pl[0] * mid.x() + pl[1] * mid.y() + pl[2]
        if abs(z - mid.z()) > 0.02:
            continue
        # does the polygon border the valley here?
        ok = False
        for k in range(len(poly)):
            p, q = poly[k], poly[(k + 1) % len(poly)]
            pq = QVector3D(q[0] - p[0], q[1] - p[1], q[2] - p[2])
            if pq.length() < 1e-6:
                continue
            ap = mid - QVector3D(*p)
            dist = QVector3D.crossProduct(pq.normalized(), ap).length()
            if dist < 0.03:
                ok = True
                break
        if ok:
            cx = sum(p[0] for p in poly) / len(poly)
            cy = sum(p[1] for p in poly) / len(poly)
            faces.append((pl, (cx, cy)))
    mesh = Mesh()
    attrs = {"color": (0.78, 0.80, 0.82)}
    tn = t.normalized()
    for pl, (cx, cy) in faces[:2]:
        n = QVector3D(-pl[0], -pl[1], 1.0).normalized()
        w = QVector3D.crossProduct(n, tn).normalized()
        if QVector3D.dotProduct(w, QVector3D(cx - mid.x(), cy - mid.y(), 0)) < 0:
            w = -w
        off = n * lift
        f = mesh.add_face([a + off, b + off, b + off + w * width,
                           a + off + w * width])
        if f is not None:
            f.attrs.update(attrs)
    if not mesh.faces:
        return None
    L = t.length()
    g = Group(mesh, name=f"รางน้ำตะเข้สำเร็จรูป (สแตนเลส) · ยาว {L:.2f} ม.")
    g.ifc = {"class": "IfcCovering", "name": "รางน้ำตะเข้"}
    return _tag(g, "roof", "gutter", "รางน้ำตะเข้",
                [("ชนิด", "รางน้ำตะเข้สำเร็จรูป (สแตนเลส)"),
                 ("ความยาว", f"{L:.2f} ม."),
                 ("รายการ BOQ", "รางน้ำตะเข้ + ตัดกระเบื้องตะเข้ราง")])


# ---------------------------------------------------------------------------
# Eave soffit (ฝ้าชายคา) with its frame
# ---------------------------------------------------------------------------

def soffit_cells(data, lines=None, s=None):
    """The eave soffit as plan rectangles between the outer face of the
    roof beams and the fascia, and its level: ``(cells, z)`` with cells
    ``[(x0, y0, x1, y1)]`` (each long side along the eave), or ``([],
    None)``. Pure: the BOQ bills the same area the 3D shows."""
    s = s or settings_of(data)
    lines = lines if lines is not None else roof_lines(data)
    if not lines or not lines.get("eave"):
        return [], None
    floors, _sk = stacked(data)
    top = floors[-1]["rooms"]
    lib = library_of(data)
    rb = float(lib.get("RB1", {}).get("b", 0.2)) / 2.0
    ov = float(s["overhang"])
    if ov <= rb + 0.02:
        return [], None
    eaves = [(r[0] - ov, r[1] - ov, r[2] + ov, r[3] + ov) for r in lines["rects"]]
    walls = [(float(rm["x"]) - rb, float(rm["y"]) - rb,
              float(rm["x"]) + float(rm["w"]) + rb,
              float(rm["y"]) + float(rm["d"]) + rb) for rm in top]
    xs = sorted({round(v, 6) for b in eaves + walls for v in (b[0], b[2])})
    ys = sorted({round(v, 6) for b in eaves + walls for v in (b[1], b[3])})

    def inside(boxes, x, y):
        return any(b[0] - 1e-9 <= x <= b[2] + 1e-9 and b[1] - 1e-9 <= y <= b[3] + 1e-9
                   for b in boxes)
    cells = []
    for i in range(len(xs) - 1):
        for j in range(len(ys) - 1):
            cx, cy = (xs[i] + xs[i + 1]) / 2, (ys[j] + ys[j + 1]) / 2
            if inside(eaves, cx, cy) and not inside(walls, cx, cy):
                cells.append([xs[i], ys[j], xs[i + 1], ys[j + 1]])
    # merge runs along x, then along y, into long strips
    def merge(cs, axis):
        cs = sorted(cs, key=lambda c: (c[1 - axis], c[3 - axis], c[axis]))
        out = []
        for c in cs:
            if out:
                p = out[-1]
                same = abs(p[1 - axis] - c[1 - axis]) < 1e-9 and \
                    abs(p[3 - axis] - c[3 - axis]) < 1e-9
                if same and abs(p[2 + axis] - c[axis]) < 1e-9:
                    p[2 + axis] = c[2 + axis]
                    continue
            out.append(list(c))
        return out
    cells = merge(merge(cells, 0), 1)
    z_e = min(a[2] for a, _b in lines["eave"])
    z = z_e - float(s.get("fascia_h", 0.20) if s.get("fascia", True) else 0.0)
    return [tuple(c) for c in cells], z


def soffit_area(data) -> float:
    cells, _z = soffit_cells(data)
    return sum((c[2] - c[0]) * (c[3] - c[1]) for c in cells)


def soffit_members(data, lines, s):
    """The soffit boards (ระแนงไม้เทียม 0.15 ม. เว้นร่อง) and the galvanised
    steel frame above them (โครงคร่าวเหล็กชุบสังกะสี: runners across the
    eave every ``soffit_sp`` m and along both edges) — สูตรวัสดุ 5.41."""
    cells, z = soffit_cells(data, lines, s)
    if not cells:
        return []
    from core.wanic_catalog import COLORS  # noqa: F401  (palette parity)
    boards = _Boxes((0.0, 0.0), (1.0, 0.0), z)
    frame = _Boxes((0.0, 0.0), (1.0, 0.0), z)
    bt, plank, gap = 0.008, 0.15, 0.005
    fw, fh = 0.035, 0.024                     # ซีลาย C-line 35 × 24 มม.
    sp = max(float(s.get("soffit_sp") or 0.60), 0.30)
    board_paint = {"color": (0.90, 0.88, 0.83)}
    steel_paint = {"color": (0.70, 0.72, 0.74)}
    area = 0.0
    for x0, y0, x1, y1 in cells:
        area += (x1 - x0) * (y1 - y0)
        along_x = (x1 - x0) >= (y1 - y0)       # planks run along the eave
        if along_x:
            y = y0
            while y < y1 - 1e-6:
                boards.box(x0, x1, y, min(y + plank, y1), 0.0, bt, board_paint)
                y += plank + gap
            for yy in (y0, y1 - fw):
                frame.box(x0, x1, yy, yy + fw, bt, bt + fh, steel_paint)
            x = x0
            while x < x1 - 1e-6:
                frame.box(x, min(x + fw, x1), y0, y1, bt + fh, bt + 2 * fh,
                          steel_paint)
                x += sp
        else:
            x = x0
            while x < x1 - 1e-6:
                boards.box(x, min(x + plank, x1), y0, y1, 0.0, bt, board_paint)
                x += plank + gap
            for xx in (x0, x1 - fw):
                frame.box(xx, xx + fw, y0, y1, bt, bt + fh, steel_paint)
            y = y0
            while y < y1 - 1e-6:
                frame.box(x0, x1, y, min(y + fw, y1), bt + fh, bt + 2 * fh,
                          steel_paint)
                y += sp
    # the fixings: a hanger (สตัดเกลียว Ø 6 มม.) from every cross runner up
    # to the rafter above at most 1.20 ม. apart, a clip (ตัวยึด) at the
    # runner and a plate (เพลทยึด) under the rafter, and the edge angles
    # (ฉากขอบ) screwed to the wall and behind the fascia
    fix = _Boxes((0.0, 0.0), (1.0, 0.0), 0.0)
    zinc = {"color": (0.55, 0.57, 0.60)}
    rdepth = lift_of(s)
    nh = 0
    for x0, y0, x1, y1 in cells:
        along_x = (x1 - x0) >= (y1 - y0)
        runners = []
        if along_x:
            x = x0
            while x < x1 - 1e-6:
                runners.append([(x + fw / 2, y0 + (y1 - y0) * f) for f in (0.5,)])
                x += 2 * sp if sp < 0.6 else sp
        else:
            y = y0
            while y < y1 - 1e-6:
                runners.append([(x0 + (x1 - x0) * f, y + fw / 2) for f in (0.5,)])
                y += 2 * sp if sp < 0.6 else sp
        for pts in runners:
            for (hx, hy) in pts:
                zr = skin_z(hx, hy, lines.get("skin") or [])
                zb = z + bt + 2 * fh
                if zr is None or zr - rdepth - zb < 0.03:
                    continue
                top = zr - rdepth
                fix.box(hx - 0.003, hx + 0.003, hy - 0.003, hy + 0.003, zb, top, zinc)
                fix.box(hx - 0.02, hx + 0.02, hy - 0.012, hy + 0.012, zb, zb + 0.015, zinc)
                fix.box(hx - 0.03, hx + 0.03, hy - 0.03, hy + 0.03, top - 0.006, top, zinc)
                nh += 1
    g = fix.group(f"อุปกรณ์ยึดฝ้าชายคา (สตัดแขวน {nh} จุด)", "roof", "soffit_fix",
                  "อุปกรณ์ยึดฝ้าชายคา", "IfcFastener")
    out = []
    if g is not None:
        out.append(_tag(g, "roof", "soffit_fix", "อุปกรณ์ยึดฝ้าชายคา",
                        [("ชนิด", "สตัดเกลียว Ø 6 มม. + ตัวยึดโครงซีลาย + เพลทยึดใต้จันทัน"),
                         ("จำนวน", f"{nh} จุด"), ("ระยะ", "ไม่เกิน 1.20 ม.")]))
    info = [("ชนิด", "ฝ้าชายคาระแนงไม้เทียม เว้นร่อง 5 มม. + มุ้งกันแมลง"),
            ("พื้นที่", f"{area:.2f} ตร.ม."), ("ระดับ", f"{z:+.2f} ม."),
            ("สูตรวัสดุ", "5.41 ฝ้าระแนงไม้เทียม (หลักเกณฑ์ 2569)"),
            ("รายการ BOQ", "ฝ้าชายคา (หลักเกณฑ์ 4.2 ข้อ 2.1)")]
    g = boards.group(f"ฝ้าชายคาระแนงไม้เทียม · {area:.2f} ตร.ม.", "roof", "soffit",
                     "ฝ้าชายคา", "IfcCovering")
    if g is not None:
        out.append(_tag(g, "roof", "soffit", "ฝ้าชายคา", info))
    g = frame.group(f"โครงคร่าวฝ้าชายคา เหล็กชุบสังกะสี @{sp:.2f} ม.", "roof",
                    "soffit_frame", "โครงคร่าวฝ้าชายคา", "IfcMember")
    if g is not None:
        out.append(_tag(g, "roof", "soffit_frame", "โครงคร่าวฝ้าชายคา",
                        [("ชนิด", "โครงคร่าวเหล็กชุบสังกะสี (ซีลาย 35×24 มม.)"),
                         ("ระยะ", f"@{sp:.2f} ม. ตั้งฉากแนวชายคา + ขอบสองด้าน"),
                         ("พื้นที่ฝ้า", f"{area:.2f} ตร.ม.")]))
    return out


def lift_of(s) -> float:
    """Depth (m) of the rafter section — the frame's underside is this
    far under the rafter-top lines."""
    _f, prm = steel_lookup(s["rafter"])
    return float(prm.get("H", prm.get("D", prm.get("A", 150)))) / 1000.0


def skin_z(x, y, skins):
    """Height of the rafter-top surface at plan point (x, y) (the highest
    facet over it), or None."""
    best = None
    for poly in skins:
        if len(poly) < 3:
            continue
        inside = False
        n = len(poly)
        for i in range(n):
            (x1, y1), (x2, y2) = poly[i][:2], poly[(i + 1) % n][:2]
            if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
                inside = not inside
        if not inside:
            continue
        a, b, c = poly[0], poly[1], poly[2]
        ux, uy, uz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
        vx, vy, vz = c[0] - a[0], c[1] - a[1], c[2] - a[2]
        nx, ny, nz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
        if abs(nz) < 1e-9:
            continue
        zz = a[2] - (nx * (x - a[0]) + ny * (y - a[1])) / nz
        best = zz if best is None else max(best, zz)
    return best


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


def floor_lift(s) -> float:
    """How far the ground floor stands above the ground (ม.)."""
    try:
        return min(max(float(s.get("floor_lift", 0.60) or 0.0), 0.0), 3.0)
    except (TypeError, ValueError):
        return 0.60


def lift_groups(groups, dz: float):
    """Move generated groups up by ``dz`` (the plans keep ±0.00 = ground
    floor; in 3D the original ground is z = 0)."""
    if abs(dz) < 1e-9:
        return groups
    from PySide6.QtGui import QMatrix4x4

    from core.group import transformed_mesh
    m = QMatrix4x4()
    m.translate(0.0, 0.0, dz)
    for g in groups:
        g.mesh = transformed_mesh(g.mesh, m)
    return groups


def build(data, parts=("structure", "roof")):
    """All generated groups for ``parts`` and a Thai summary line. The
    building is generated with its ground floor at z = 0 and the ground at
    −floor_lift, then raised so the ground sits at z = 0 in the model."""
    groups, count = [], {}
    if "structure" in parts:
        g, c = structure_members(data)
        groups += g
        count.update(c)
    if "roof" in parts:
        g, c = roof_members(data)
        groups += g
        count.update(c)
    try:
        from core import wanic_partprice
        wanic_partprice.annotate(groups, data)
        wanic_partprice.annotate_units(groups)
    except Exception:                                   # noqa: BLE001 -- prices are extra
        pass
    lift_groups(groups, floor_lift(settings_of(data)))
    return groups, count


KIND_TH = [("footing", "ฐานราก"), ("pile", "เสาเข็ม"), ("stump", "ตอม่อ"), ("column", "เสา"),
           ("beam", "คาน"), ("slab", "พื้น"), ("wall", "ผนัง"),
           ("door", "ประตู"), ("window", "หน้าต่าง"), ("stair", "บันได"),
           ("ridge", "อกไก่"), ("hip", "ตะเฆ่สัน"), ("rafter", "จันทัน"),
           ("purlin", "แป"), ("post", "ดั้ง"), ("wallplate", "อะเส"),
           ("tiebeam", "ขื่อ"), ("rbeam", "คานรับดั้ง"), ("strut", "ตุ๊กตา"),
           ("brace", "ค้ำยัน"), ("headplate", "เพลทหัวเสา"),
           ("fascia", "เชิงชาย"),
           ("barge", "ปั้นลม"), ("cap", "ครอบสัน/ครอบข้าง"),
           ("band", "เสาเอ็น-ทับหลัง"), ("plaster", "ผิวฉาบปูน"),
           ("fixture", "สุขภัณฑ์"), ("ceiling", "ฝ้าเพดาน"),
           ("ceiling_frame", "โครงคร่าวฝ้า"), ("skirting", "บัวเชิงผนัง"),
           ("cornice", "บัวฝ้า"), ("ac", "เครื่องปรับอากาศ"), ("light", "ดวงโคม"),
           ("outlet", "สวิตช์/เต้ารับ"), ("panel", "ตู้ไฟ"), ("pipe_supply", "ท่อประปา"),
           ("pipe_drain", "ท่อน้ำทิ้ง"), ("septic", "ถังบำบัด"), ("walkway", "ทางเท้า"),
           ("tiles", "กระเบื้อง"),
           ("eave_gutter", "รางน้ำชายคา"), ("downspout", "ท่อลงน้ำ"),
           ("skin", "แผ่นหลังคา")]


def layer_name(g, mode: str = "name") -> str:
    """The layer a generated part goes on: its own name («เสา C1 20×20 ซม.
    · ชั้น 1 · D-3»), its type and size («เสา C1 20×20 ซม.»), type and
    floor, or its หมวดงาน («04 งานโครงสร้างคอนกรีต»); "" = default layer."""
    from core import wanic_categories as CG
    rec = ((getattr(g, "ext", None) or {}).get(EXT_KEY)) or {}
    name = (getattr(g, "name", "") or rec.get("key") or rec.get("mark") or "").strip()
    if not mode or not name:
        return ""
    parts = [p_.strip() for p_ in name.split(" · ")]
    if mode == "category":
        return CG.layer_title(CG.kind_category(rec.get("kind", "")))
    if mode == "type":
        head = parts[0]
        # «แป C 75×45×15×2.3 · ยาว 4.20 ม.» → «แป C 75×45×15×2.3»
        return head
    if mode == "floor":
        fl = next((p_ for p_ in parts[1:] if p_.startswith("ชั้น")), "")
        return f"{parts[0]} · {fl}" if fl else parts[0]
    # "name": the part's own full name, less a running length
    return " · ".join(p_ for p_ in parts if not p_.startswith("ยาว "))


def assign_layers(groups, mode: str = "name") -> dict:
    """Set ``g.layer`` on every group; {layer name: [groups]}."""
    out: dict = {}
    for g in groups:
        ln = layer_name(g, mode)
        g.layer = ln or None
        if ln:
            out.setdefault(ln, []).append(g)
    return out


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
        kinds = []
        for ext in (True, False):
            sp = wall_spec(s, ext)
            k = f"{'ผนังภายนอก' if ext else 'ผนังภายใน'} {sp['name']}"
            if k not in kinds:
                kinds.append(k)
        for i, k in enumerate(kinds):
            add("งานผนัง/ฉาบ", f"3.{i + 1}", f"{k} (พื้นที่ 1 ด้าน)", k,
                "side_area", "ตร.ม.", 0.5)
        if s.get("plaster_3d", True):
            add("งานผนัง/ฉาบ", "3.3", "ฉาบปูนผนังภายนอก", "ฉาบปูนผนังภายนอก",
                "side_area", "ตร.ม.", 0.5)
            add("งานผนัง/ฉาบ", "3.4", "ฉาบปูนผนังภายใน", "ฉาบปูนผนังภายใน",
                "side_area", "ตร.ม.", 0.5)
        else:
            for k in kinds:
                add("งานผนัง/ฉาบ", "3.3", f"ฉาบปูน {k} (2 ด้าน)", k,
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
             "purlin": "แป", "post": "ดั้ง", "valley": "ตะเฆ่ราง",
             "wallplate": "อะเส", "tiebeam": "ขื่อ (คานรับดั้ง)"}
    sizes = dict(s, valley=s["hip"])
    seen = set()
    kinds = ["ridge", "hip", "rafter", "purlin", "post", "valley"]
    if s.get("wall_plate"):
        kinds.append("wallplate")
    if s.get("tie_beams"):
        kinds.append("tiebeam")
    for i, kind in enumerate(kinds):
        label = f"{names[kind]} {sizes[kind]}"
        if label in seen:
            continue
        seen.add(label)
        add("งานหลังคา", f"4.{i + 1}", f"โครงหลังคาเหล็ก {label}", label,
            "steel_kg", "กก.")
    if s.get("skin"):
        add("งานหลังคา", "4.9", "มุงหลังคา (พื้นที่ตามแนวลาด)", "หลังคา",
            "top_area", "ตร.ม.")
    return R
