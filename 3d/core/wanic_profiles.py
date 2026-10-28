# SPDX-License-Identifier: GPL-3.0-or-later
# WANICNSURVEY 3D — "WANIC โปรไฟล์": parametric profiles swept along paths.
"""Parametric cross-sections (steel, concrete, civil / survey work) swept
along a path of edges into one group that remembers how it was made.

The 2D part (:func:`profile_outline`) is pure Python: an outline and its
holes in metres, counter-clockwise, in the section's own (u, v) plane
(u across, v up). :func:`build_member` places it on the path with the
app's own Follow Me engine (:func:`core.sweep.sweep_profile`) and returns
a ready :class:`core.group.Group`; the caller inserts it with
``InsertGroupCommand`` (one undo step).

The group's ``ext["wanic_profiles"]`` keeps the family, the dimensions, the
placement and the path, so the member can be rebuilt with new sizes, and
the takeoff reads its true length along the path (not its bounding box).

Weights are computed from the drawn area × 7,850 kg/m³ (no root fillets),
so they read a little under the mill tables — stated wherever shown.
"""
from __future__ import annotations

import math

EXT_KEY = "wanic_profiles"
STEEL_DENSITY = 7850.0
CIRCLE_SEGMENTS = 24

# ---------------------------------------------------------------------------
# 2D outlines (millimetres in, metres out)
# ---------------------------------------------------------------------------


def _area(loop) -> float:
    return 0.5 * sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1)
                     in zip(loop, loop[1:] + loop[:1]))


def _ccw(loop):
    return loop if _area(loop) > 0 else loop[::-1]


def _cw(loop):
    return loop[::-1] if _area(loop) > 0 else loop


def _circle(r, cx=0.0, cy=0.0, n=CIRCLE_SEGMENTS):
    return [(cx + r * math.cos(2 * math.pi * i / n),
             cy + r * math.sin(2 * math.pi * i / n)) for i in range(n)]


def _rect(w, h, cx=0.0, cy=0.0):
    return [(cx - w / 2, cy - h / 2), (cx + w / 2, cy - h / 2),
            (cx + w / 2, cy + h / 2), (cx - w / 2, cy + h / 2)]


def _i_shape(p):
    H, B, tw, tf = p["H"], p["B"], p["tw"], p["tf"]
    h, b, w = H / 2, B / 2, tw / 2
    return [(-b, -h), (b, -h), (b, -h + tf), (w, -h + tf), (w, h - tf),
            (b, h - tf), (b, h), (-b, h), (-b, h - tf), (-w, h - tf),
            (-w, -h + tf), (-b, -h + tf)], []


def _channel(p):
    H, B, tw, tf = p["H"], p["B"], p["tw"], p["tf"]
    h = H / 2
    return [(0, -h), (B, -h), (B, -h + tf), (tw, -h + tf), (tw, h - tf),
            (B, h - tf), (B, h), (0, h)], []


def _lip_channel(p):
    H, B, C, t = p["H"], p["B"], p["C"], p["t"]
    h = H / 2
    return [(0, -h), (B, -h), (B, -h + C), (B - t, -h + C), (B - t, -h + t),
            (t, -h + t), (t, h - t), (B - t, h - t), (B - t, h - C),
            (B, h - C), (B, h), (0, h)], []


def _angle(p):
    A, B, t = p["A"], p["B"], p["t"]
    return [(0, 0), (B, 0), (B, t), (t, t), (t, A), (0, A)], []


def _box(p):
    H, B, t = p["H"], p["B"], p["t"]
    return _rect(B, H), [_rect(B - 2 * t, H - 2 * t)]


def _pipe(p):
    D, t = p["D"], p["t"]
    return _circle(D / 2), [_circle(D / 2 - t)]


def _pipe_inner(p):
    D, t = p["D"], p["t"]
    return _circle(D / 2 + t), [_circle(D / 2)]


def _round(p):
    return _circle(p["D"] / 2), []


def _rect_section(p):
    return _rect(p["b"], p["h"]), []


def _flat(p):
    return _rect(p["B"], p["t"]), []


def _t_beam(p):
    bf, hf, bw, h = p["bf"], p["hf"], p["bw"], p["h"]
    return [(-bw / 2, 0), (bw / 2, 0), (bw / 2, h - hf), (bf / 2, h - hf),
            (bf / 2, h), (-bf / 2, h), (-bf / 2, h - hf), (-bw / 2, h - hf)], []


def _curb(p):
    bb, bt, h = p["bb"], p["bt"], p["h"]
    # Back face vertical at u = 0, front face battered toward the road (+u).
    return [(0, 0), (bb, 0), (bt, h), (0, h)], []


def _curb_gutter(p):
    W, tg, bc, hc, d = p["W"], p["tg"], p["bc"], p["hc"], p["d"]
    # Gutter toward +u, curb at the back (u = 0..bc); bottom flat at v = 0.
    return [(0, 0), (bc + W, 0), (bc + W, tg), (bc, tg + d), (bc, hc),
            (0, hc)], []


def _u_ditch(p):
    b, d, t, tb = p["b"], p["d"], p["t"], p["tb"]
    hb = b / 2
    return [(-hb - t, -tb), (hb + t, -tb), (hb + t, d), (hb, d), (hb, 0),
            (-hb, 0), (-hb, d), (-hb - t, d)], []


def _trap_lining(p):
    b, d, z, t = p["b"], p["d"], p["z"], p["t"]
    hb = b / 2
    k = t * math.sqrt(1 + z * z)
    inner = [(-(hb + z * d), d), (-hb, 0), (hb, 0), (hb + z * d, d)]
    outer = [(hb + z * d + k, d), (hb - z * t + k, -t),
             (-(hb - z * t + k), -t), (-(hb + z * d + k), d)]
    return inner + outer, []


def _box_culvert(p):
    W, H, t = p["W"], p["H"], p["t"]
    return (_rect(W + 2 * t, H + 2 * t, 0, (H + 2 * t) / 2),
            [_rect(W, H, 0, (H + 2 * t) / 2)])


def _road(p):
    W, s, t = p["W"], p["s"] / 100.0, p["t"]
    hw = W / 2
    drop = hw * s
    return [(-hw, -drop - t), (0, -t), (hw, -drop - t), (hw, -drop), (0, 0),
            (-hw, -drop)], []


def _embankment(p):
    bt, h, z = p["bt"], p["h"], p["z"]
    hb = bt / 2 + z * h
    return [(-hb, 0), (hb, 0), (bt / 2, h), (-bt / 2, h)], []


# ---------------------------------------------------------------------------
# The library
# ---------------------------------------------------------------------------

#: family key → {name, group, params [(key, label)], fn, ifc, steel, presets}
FAMILIES: dict = {}


def _fam(key, name, group, params, fn, ifc="", steel=False, presets=()):
    FAMILIES[key] = {"key": key, "name": name, "group": group,
                     "params": params, "fn": fn, "ifc": ifc, "steel": steel,
                     "presets": list(presets)}


_HP = [("H", "ความสูง H"), ("B", "ความกว้างปีก B"), ("tw", "ความหนาเอว tw"),
       ("tf", "ความหนาปีก tf")]
_fam("h", "เหล็กรูปพรรณ H (ไวด์แฟลงจ์)", "เหล็กรูปพรรณ", _HP, _i_shape,
     "IfcBeam", True, [
         ("H 100×100×6×8", dict(H=100, B=100, tw=6, tf=8)),
         ("H 125×125×6.5×9", dict(H=125, B=125, tw=6.5, tf=9)),
         ("H 150×150×7×10", dict(H=150, B=150, tw=7, tf=10)),
         ("H 175×175×7.5×11", dict(H=175, B=175, tw=7.5, tf=11)),
         ("H 200×200×8×12", dict(H=200, B=200, tw=8, tf=12)),
         ("H 250×250×9×14", dict(H=250, B=250, tw=9, tf=14)),
         ("H 300×300×10×15", dict(H=300, B=300, tw=10, tf=15)),
         ("H 150×75×5×7", dict(H=150, B=75, tw=5, tf=7)),
         ("H 200×100×5.5×8", dict(H=200, B=100, tw=5.5, tf=8)),
         ("H 250×125×6×9", dict(H=250, B=125, tw=6, tf=9)),
         ("H 300×150×6.5×9", dict(H=300, B=150, tw=6.5, tf=9)),
         ("H 350×175×7×11", dict(H=350, B=175, tw=7, tf=11)),
         ("H 400×200×8×13", dict(H=400, B=200, tw=8, tf=13)),
     ])
_fam("i", "เหล็กไอบีม (I-beam)", "เหล็กรูปพรรณ", _HP, _i_shape, "IfcBeam",
     True, [
         ("I 100×75×5×8", dict(H=100, B=75, tw=5, tf=8)),
         ("I 150×75×5.5×9.5", dict(H=150, B=75, tw=5.5, tf=9.5)),
         ("I 200×100×7×10", dict(H=200, B=100, tw=7, tf=10)),
         ("I 250×125×7.5×12.5", dict(H=250, B=125, tw=7.5, tf=12.5)),
         ("I 300×150×8×13", dict(H=300, B=150, tw=8, tf=13)),
     ])
_fam("c", "เหล็กรางน้ำ (Channel)", "เหล็กรูปพรรณ", _HP, _channel, "IfcMember",
     True, [
         ("[ 75×40×5×7", dict(H=75, B=40, tw=5, tf=7)),
         ("[ 100×50×5×7.5", dict(H=100, B=50, tw=5, tf=7.5)),
         ("[ 125×65×6×8", dict(H=125, B=65, tw=6, tf=8)),
         ("[ 150×75×6.5×10", dict(H=150, B=75, tw=6.5, tf=10)),
         ("[ 200×80×7.5×11", dict(H=200, B=80, tw=7.5, tf=11)),
     ])
_fam("lc", "เหล็กตัวซีลิป (Lip channel)", "เหล็กรูปพรรณ",
     [("H", "ความสูง H"), ("B", "ความกว้าง B"), ("C", "ลิป C"),
      ("t", "ความหนา t")], _lip_channel, "IfcMember", True, [
         ("C 75×45×15×2.3", dict(H=75, B=45, C=15, t=2.3)),
         ("C 100×50×20×2.3", dict(H=100, B=50, C=20, t=2.3)),
         ("C 100×50×20×3.2", dict(H=100, B=50, C=20, t=3.2)),
         ("C 125×50×20×2.3", dict(H=125, B=50, C=20, t=2.3)),
         ("C 125×50×20×3.2", dict(H=125, B=50, C=20, t=3.2)),
         ("C 150×50×20×2.3", dict(H=150, B=50, C=20, t=2.3)),
         ("C 150×65×20×3.2", dict(H=150, B=65, C=20, t=3.2)),
     ])
_fam("l", "เหล็กฉาก (Angle)", "เหล็กรูปพรรณ",
     [("A", "ขา A"), ("B", "ขา B"), ("t", "ความหนา t")], _angle, "IfcMember",
     True, [
         ("L 25×25×3", dict(A=25, B=25, t=3)),
         ("L 40×40×4", dict(A=40, B=40, t=4)),
         ("L 50×50×5", dict(A=50, B=50, t=5)),
         ("L 65×65×6", dict(A=65, B=65, t=6)),
         ("L 75×75×6", dict(A=75, B=75, t=6)),
         ("L 100×100×10", dict(A=100, B=100, t=10)),
     ])
_fam("box", "เหล็กกล่อง (Tube)", "เหล็กรูปพรรณ",
     [("H", "ความสูง H"), ("B", "ความกว้าง B"), ("t", "ความหนา t")], _box,
     "IfcMember", True, [
         ("□ 25×25×1.2", dict(H=25, B=25, t=1.2)),
         ("□ 50×50×2.3", dict(H=50, B=50, t=2.3)),
         ("□ 75×75×3.2", dict(H=75, B=75, t=3.2)),
         ("□ 100×100×3.2", dict(H=100, B=100, t=3.2)),
         ("▭ 50×25×1.6", dict(H=50, B=25, t=1.6)),
         ("▭ 100×50×2.3", dict(H=100, B=50, t=2.3)),
         ("▭ 150×50×3.2", dict(H=150, B=50, t=3.2)),
     ])
_fam("pipe", "ท่อเหล็กกลม (Pipe)", "เหล็กรูปพรรณ",
     [("D", "เส้นผ่านศูนย์กลางนอก D"), ("t", "ความหนา t")], _pipe,
     "IfcMember", True, [
         ('ø 1/2" (21.7×2.0)', dict(D=21.7, t=2.0)),
         ('ø 1" (34.0×2.3)', dict(D=34.0, t=2.3)),
         ('ø 1 1/2" (48.6×2.3)', dict(D=48.6, t=2.3)),
         ('ø 2" (60.5×2.3)', dict(D=60.5, t=2.3)),
         ('ø 3" (89.1×2.8)', dict(D=89.1, t=2.8)),
         ('ø 4" (114.3×3.2)', dict(D=114.3, t=3.2)),
     ])
_fam("flat", "เหล็กแบน", "เหล็กรูปพรรณ",
     [("B", "ความกว้าง B"), ("t", "ความหนา t")], _flat, "IfcMember", True, [
         ("แบน 25×3", dict(B=25, t=3)), ("แบน 50×6", dict(B=50, t=6)),
         ("แบน 100×9", dict(B=100, t=9)),
     ])
_fam("round", "เหล็กเส้นกลม / หน้าตัดกลมตัน", "เหล็กรูปพรรณ",
     [("D", "เส้นผ่านศูนย์กลาง D")], _round, "IfcReinforcingBar", True, [
         ("RB 6", dict(D=6)), ("RB 9", dict(D=9)), ("DB 12", dict(D=12)),
         ("DB 16", dict(D=16)), ("DB 20", dict(D=20)), ("DB 25", dict(D=25)),
     ])
_fam("rect", "หน้าตัดสี่เหลี่ยม (คาน/เสา คสล., ไม้)", "คอนกรีตและไม้",
     [("b", "ความกว้าง b"), ("h", "ความสูง h")], _rect_section, "IfcBeam",
     False, [
         ("คาน 200×400", dict(b=200, h=400)),
         ("คาน 250×500", dict(b=250, h=500)),
         ("เสา 200×200", dict(b=200, h=200)),
         ("เสา 300×300", dict(b=300, h=300)),
         ('ไม้ 2"×4" (50×100)', dict(b=50, h=100)),
         ('ไม้ 2"×6" (50×150)', dict(b=50, h=150)),
     ])
_fam("tbeam", "คานรูปตัว T", "คอนกรีตและไม้",
     [("bf", "ความกว้างปีก bf"), ("hf", "ความหนาพื้น hf"),
      ("bw", "ความกว้างเอว bw"), ("h", "ความสูงรวม h")], _t_beam, "IfcBeam",
     False, [("T 1000×100×250×500", dict(bf=1000, hf=100, bw=250, h=500))])
_fam("pile", "เสาเข็มกลม คสล.", "คอนกรีตและไม้",
     [("D", "เส้นผ่านศูนย์กลาง D")], _round, "IfcPile", False, [
         ("เข็มเจาะ ø350", dict(D=350)), ("เข็มเจาะ ø500", dict(D=500)),
         ("เข็มเจาะ ø600", dict(D=600)),
     ])
_fam("curb", "คันหิน (Kerb)", "งานทางและระบายน้ำ",
     [("bb", "ความกว้างฐาน"), ("bt", "ความกว้างบน"), ("h", "ความสูง")], _curb,
     "", False, [("คันหิน 150/125×300", dict(bb=150, bt=125, h=300))])
_fam("curb_gutter", "คันหินรางตื้น (Curb & gutter)", "งานทางและระบายน้ำ",
     [("W", "ความกว้างราง"), ("tg", "ความหนาราง (ปลาย)"),
      ("bc", "ความกว้างคันหิน"), ("hc", "ความสูงคันหินรวม"),
      ("d", "ความลึกราง (ลาดเข้าหาคันหิน)")], _curb_gutter, "", False,
     [("คันหินรางตื้น 300+150", dict(W=300, tg=150, bc=150, hc=400, d=0))])
_fam("u_ditch", "รางระบายน้ำตัวยู (U-ditch)", "งานทางและระบายน้ำ",
     [("b", "ความกว้างภายใน"), ("d", "ความลึกภายใน"), ("t", "ความหนาผนัง"),
      ("tb", "ความหนาพื้น")], _u_ditch, "", False, [
         ("ราง U 300×300", dict(b=300, d=300, t=100, tb=100)),
         ("ราง U 400×500", dict(b=400, d=500, t=120, tb=120)),
     ])
_fam("trap", "คูระบายน้ำคางหมู (ดาดคอนกรีต)", "งานทางและระบายน้ำ",
     [("b", "ความกว้างก้นคู"), ("d", "ความลึก"),
      ("z", "ลาดข้าง 1 : z (z ไม่มีหน่วย)"), ("t", "ความหนาดาด")],
     _trap_lining, "", False,
     [("คู ก้น 500 ลึก 600 ลาด 1:1.5", dict(b=500, d=600, z=1.5, t=100))])
_fam("culvert", "ท่อลอดเหลี่ยม (Box culvert)", "งานทางและระบายน้ำ",
     [("W", "ความกว้างช่องภายใน"), ("H", "ความสูงช่องภายใน"),
      ("t", "ความหนา")], _box_culvert, "", False, [
         ("1.20×1.20", dict(W=1200, H=1200, t=200)),
         ("1.80×1.80", dict(W=1800, H=1800, t=200)),
     ])
_fam("rc_pipe", "ท่อระบายน้ำ คสล. (ระบุ ø ภายใน)", "งานทางและระบายน้ำ",
     [("D", "เส้นผ่านศูนย์กลางภายใน D"), ("t", "ความหนาผนัง t")], _pipe_inner,
     "", False, [
         ("ø 0.40", dict(D=400, t=50)), ("ø 0.60", dict(D=600, t=70)),
         ("ø 0.80", dict(D=800, t=80)), ("ø 1.00", dict(D=1000, t=100)),
     ])
_fam("road", "ผิวถนน (มีหลังเต่า)", "งานทางและระบายน้ำ",
     [("W", "ความกว้างผิวจราจร"), ("s", "ความลาดขวาง % (s ไม่มีหน่วย)"),
      ("t", "ความหนาผิว")], _road, "IfcSlab", False, [
         ("ถนน 6.00 ม. ลาด 2% หนา 0.15", dict(W=6000, s=2, t=150)),
         ("ถนน 7.00 ม. ลาด 2% หนา 0.20", dict(W=7000, s=2, t=200)),
     ])
_fam("embank", "คันทาง / คันดิน (ดินถม)", "งานทางและระบายน้ำ",
     [("bt", "ความกว้างบนคัน"), ("h", "ความสูงคัน"),
      ("z", "ลาดข้าง 1 : z (z ไม่มีหน่วย)")], _embankment, "", False,
     [("คันทาง กว้าง 8 ม. สูง 1.5 ม. ลาด 1:2", dict(bt=8000, h=1500, z=2))])

#: Parameters that are plain numbers, not millimetres.
UNITLESS = {"s", "z"}

ANCHORS = {
    "c": "กึ่งกลาง", "tc": "บนกลาง", "bc": "ล่างกลาง", "tl": "บนซ้าย",
    "tr": "บนขวา", "bl": "ล่างซ้าย", "br": "ล่างขวา", "ml": "กลางซ้าย",
    "mr": "กลางขวา",
}


def family_groups() -> list[tuple[str, list[dict]]]:
    order, out = [], {}
    for f in FAMILIES.values():
        if f["group"] not in out:
            out[f["group"]] = []
            order.append(f["group"])
        out[f["group"]].append(f)
    return [(g, out[g]) for g in order]


def default_params(family: str) -> dict:
    fam = FAMILIES[family]
    return dict(fam["presets"][0][1]) if fam["presets"] else {
        k: 100.0 for k, _ in fam["params"]}


def describe(family: str, params: dict) -> str:
    """A label like ``H 200×200×8×12`` (the preset's, when it matches)."""
    fam = FAMILIES[family]
    for label, p in fam["presets"]:
        if all(abs(float(p[k]) - float(params.get(k, 0))) < 1e-9 for k in p):
            return label
    nums = "×".join(f"{float(params[k]):g}" for k, _ in fam["params"])
    return f"{fam['name'].split(' (')[0]} {nums}"


def validate(family: str, params: dict):
    """A Thai reason when the dimensions cannot make the section, else None."""
    fam = FAMILIES.get(family)
    if fam is None:
        return "ไม่รู้จักรูปตัดนี้"
    p = {}
    for k, label in fam["params"]:
        try:
            p[k] = float(params[k])
        except (KeyError, TypeError, ValueError):
            return f"กรอก «{label}» ให้เป็นตัวเลข"
        if k not in ("d", "s") and p[k] <= 0:
            return f"«{label}» ต้องมากกว่า 0"
        if p[k] < 0:
            return f"«{label}» ต้องไม่ติดลบ"
    checks = {
        "h": lambda: p["tw"] < p["B"] and 2 * p["tf"] < p["H"],
        "i": lambda: p["tw"] < p["B"] and 2 * p["tf"] < p["H"],
        "c": lambda: p["tw"] < p["B"] and 2 * p["tf"] < p["H"],
        "lc": lambda: 2 * p["t"] < p["B"] and p["C"] > p["t"]
        and 2 * p["C"] < p["H"],
        "l": lambda: p["t"] < min(p["A"], p["B"]),
        "box": lambda: 2 * p["t"] < min(p["H"], p["B"]),
        "pipe": lambda: 2 * p["t"] < p["D"],
        "tbeam": lambda: p["bw"] <= p["bf"] and p["hf"] < p["h"],
        "curb": lambda: p["bt"] <= p["bb"],
        "curb_gutter": lambda: p["tg"] + p["d"] < p["hc"],
    }
    ok = checks.get(family)
    if ok is not None and not ok():
        return "ขนาดขัดกันเอง (ความหนามากเกินความกว้าง/ความสูง)"
    return None


def profile_outline(family: str, params: dict):
    """``(outer, holes)`` in metres, outer CCW and holes CW, (u, v)."""
    fam = FAMILIES[family]
    p = {k: float(params[k]) / (1.0 if k in UNITLESS else 1000.0)
         for k, _ in fam["params"]}
    outer, holes = fam["fn"](p)
    return _ccw(list(outer)), [_cw(list(h)) for h in holes]


def section_area(family: str, params: dict) -> float:
    outer, holes = profile_outline(family, params)
    return abs(_area(outer)) - sum(abs(_area(h)) for h in holes)


def weight_per_m(family: str, params: dict) -> float:
    return section_area(family, params) * STEEL_DENSITY


def placed_outline(family, params, anchor="c", rotation=0.0, mirror=False,
                   offset=(0.0, 0.0)):
    """The outline moved so ``anchor`` sits at (0, 0), then mirrored,
    rotated (degrees, CCW) and shifted by ``offset`` (metres)."""
    outer, holes = profile_outline(family, params)
    xs = [x for x, _ in outer]
    ys = [y for _, y in outer]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    ax = {"l": x0, "r": x1}.get(anchor[-1], (x0 + x1) / 2) \
        if anchor != "c" else (x0 + x1) / 2
    ay = {"t": y1, "b": y0}.get(anchor[0], (y0 + y1) / 2) \
        if anchor != "c" else (y0 + y1) / 2
    a = math.radians(rotation)
    ca, sa = math.cos(a), math.sin(a)
    ou, ov = offset

    def tf(pt):
        x, y = pt[0] - ax, pt[1] - ay
        if mirror:
            x = -x
        return (x * ca - y * sa + ou, x * sa + y * ca + ov)

    outer2 = [tf(q) for q in outer]
    holes2 = [[tf(q) for q in h] for h in holes]
    if mirror:
        outer2, holes2 = outer2[::-1], [h[::-1] for h in holes2]
    return outer2, holes2


# ---------------------------------------------------------------------------
# On the path
# ---------------------------------------------------------------------------

def path_length(points, closed=False) -> float:
    pts = [tuple(p) for p in points]
    n = len(pts)
    segs = n if closed else n - 1
    return sum(math.dist(pts[i], pts[(i + 1) % n]) for i in range(max(segs, 0)))


def section_frame(points):
    """(origin, tangent, u, v) at the path's first point: v is "up" (world Z;
    world Y for a vertical path), u across."""
    from PySide6.QtGui import QVector3D
    p0 = QVector3D(*points[0])
    t = (QVector3D(*points[1]) - p0).normalized()
    up = QVector3D(0, 0, 1)
    if abs(QVector3D.dotProduct(t, up)) > 0.999:
        up = QVector3D(0, 1, 0)
    u = QVector3D.crossProduct(up, t).normalized()
    v = QVector3D.crossProduct(t, u).normalized()
    return p0, t, u, v


def build_member(spec: dict):
    """A Group holding ``spec``'s section swept along its path, or a Thai
    reason (str) when it cannot be built.

    ``spec``: {"family", "params", "anchor", "rotation", "mirror",
    "offset", "path": [[x, y, z], …], "closed", "name", "layer", "ifc"}"""
    from PySide6.QtGui import QVector3D

    from core.group import Group
    from core.mesh import Mesh
    from core.sweep import sweep_profile

    why = validate(spec["family"], spec["params"])
    if why:
        return why
    pts = [tuple(float(c) for c in p) for p in spec["path"]]
    closed = bool(spec.get("closed"))
    # Drop repeated points: a zero-length span stops the sweep.
    clean = []
    for p in pts:
        if not clean or math.dist(p, clean[-1]) > 1e-7:
            clean.append(p)
    if closed and len(clean) > 2 and math.dist(clean[0], clean[-1]) < 1e-7:
        clean.pop()
    if len(clean) < (3 if closed else 2):
        return "เส้นทางสั้นเกินไป — เลือกเส้นอย่างน้อย 1 เส้น"
    outer, holes = placed_outline(
        spec["family"], spec["params"], spec.get("anchor", "c"),
        float(spec.get("rotation", 0.0)), bool(spec.get("mirror")),
        tuple(spec.get("offset", (0.0, 0.0))))
    # The section stands across the FIRST segment at the first point; the
    # sweep projects it onto each joint (a mitre at a closed path's start).
    p0, _t, u, v = section_frame(clean)

    def lift(q):
        return p0 + u * q[0] + v * q[1]

    mesh = Mesh()
    face = mesh.add_face([lift(q) for q in outer],
                         [[lift(q) for q in h] for h in holes] or None)
    path = [QVector3D(*p) for p in clean]
    if not sweep_profile(mesh, face, path, closed):
        return ("กวาดรูปตัดตามเส้นนี้ไม่ได้ (เส้นย้อนกลับ 180° หรือหักมุม"
                "แคบเกินไป)")
    label = spec.get("name") or describe(spec["family"], spec["params"])
    g = Group(mesh, name=label)
    if spec.get("layer"):
        g.layer = spec["layer"]
    if spec.get("ifc"):
        g.ifc = {"class": spec["ifc"], "name": label}
    record = {k: spec.get(k) for k in ("family", "anchor", "rotation",
                                       "mirror", "offset", "closed")}
    record.update(params={k: float(v) for k, v in spec["params"].items()},
                  path=[list(p) for p in clean], label=label,
                  length=path_length(clean, closed),
                  area=section_area(spec["family"], spec["params"]))
    g.ext = {EXT_KEY: record}
    return g


def member_record(group):
    ext = getattr(group, "ext", None) or {}
    rec = ext.get(EXT_KEY)
    return rec if isinstance(rec, dict) else None


def iter_members(scene):
    """Every WANIC profile member in the model (top level and nested)."""
    def walk(groups):
        for g in groups:
            if member_record(g) is not None:
                yield g
            kids = getattr(g, "children", None)
            if kids:
                yield from walk(kids)
    yield from walk(scene.groups)


def schedule(scene) -> list[dict]:
    """Members summed by label: count, total length (m), section area (m²),
    volume (m³) and, for steel, weight (kg)."""
    rows: dict = {}
    for g in iter_members(scene):
        rec = member_record(g)
        fam = FAMILIES.get(rec.get("family"), {})
        key = (rec.get("family"), rec.get("label"))
        row = rows.setdefault(key, {
            "label": rec.get("label", g.name), "family": fam.get("name", ""),
            "count": 0, "length": 0.0, "area": float(rec.get("area") or 0.0),
            "steel": bool(fam.get("steel"))})
        row["count"] += 1
        row["length"] += float(rec.get("length") or 0.0)
    out = []
    for row in rows.values():
        row["volume"] = row["area"] * row["length"]
        row["weight"] = row["volume"] * STEEL_DENSITY if row["steel"] else None
        out.append(row)
    out.sort(key=lambda r: (r["family"], r["label"]))
    return out


def schedule_csv(rows) -> str:
    import csv
    import io
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["รูปตัด", "ประเภท", "จำนวน (ชิ้น)", "ความยาวรวม (ม.)",
                "พื้นที่หน้าตัด (ตร.ซม.)", "ปริมาตร (ลบ.ม.)",
                "น้ำหนักโดยประมาณ (กก.)"])
    for r in rows:
        w.writerow([r["label"], r["family"], r["count"], f"{r['length']:.3f}",
                    f"{r['area'] * 1e4:.2f}", f"{r['volume']:.4f}",
                    "" if r["weight"] is None else f"{r['weight']:.2f}"])
    return "﻿" + buf.getvalue()
