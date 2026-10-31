# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
# WANICNSURVEY 3D — "WANIC ออกแบบถนน": survey points to sections and volumes.
"""Road design from a survey, headless (no Qt): the engine behind the
«WANIC ออกแบบถนน» panel.

1. :func:`parse_points` reads the total-station / GPS file
   (``P,N,E,Z,D`` and its variants; N against E told apart by size, the
   way a Thai UTM file is written: N 1 600 000, E 700 000).
2. :func:`centerline_from_codes` orders the shots coded ``CL`` into the
   axis (the code RoadOne's section survey uses, ``93.445:CL>21``).
3. :func:`analyse` builds the TIN, samples the profile, the cross sections
   and the earthworks with the CAD's road engine (:mod:`core.road`), over a
   grade line of PVIs with vertical curves and a crowned template.
4. :func:`terrain_mesh` / :func:`corridor_mesh` give the ground and the
   finished road as triangles for the 3D model, :func:`earthworks_csv`
   and :func:`dxf_document` the table and the drawings.

Coordinates stay in metres; the 3D model is placed relative to
:attr:`Analysis.origin` (UTM millions do not survive float32 vertices).
"""
from __future__ import annotations

import csv
import io
import math
import re
from dataclasses import dataclass, field
from typing import Optional

from core.road import alignment as A
from core.road import profile as P
from core.road import tin as T

Point = tuple[float, float]
ORDERS = ("auto", "PNEZD", "PENZD", "NEZD", "ENZD")
CL_CODES = ("CL", "C/L", "C.L.", "CEN", "CENTER", "CENTRE", "ศก")


@dataclass
class Shot:
    name: str
    e: float
    n: float
    z: float
    code: str = ""


# -- 1. the survey file ------------------------------------------------------------------

def _num(cell: str) -> Optional[float]:
    try:
        return float(cell.strip().replace(",", "."))
    except ValueError:
        return None


def _cells(line: str) -> list[str]:
    if ";" in line:
        return [c.strip() for c in next(csv.reader(io.StringIO(line), delimiter=";"))]
    if "\t" in line:
        return [c.strip() for c in line.split("\t")]
    if "," in line:
        return [c.strip() for c in next(csv.reader(io.StringIO(line)))]
    return line.split()


def _digits(v: float) -> int:
    return len(str(int(abs(v)))) if abs(v) >= 1 else 1


def sniff_order(rows: list[list[str]]) -> str:
    """The column order of the first data row: a name first or not, and
    E before N when the second coordinate is the longer number."""
    for cells in rows:
        nums = [_num(c) for c in cells]
        if len(cells) >= 4 and all(v is not None for v in nums[1:4]):
            # a point number is short and whole; a coordinate first is not
            name_first = nums[0] is None or ("." not in cells[0] and abs(nums[0]) < 100000) \
                or (len(cells) >= 5 and nums[3] is not None)
            if name_first:
                return "PENZD" if _digits(nums[2]) > _digits(nums[1]) else "PNEZD"
        if len(cells) >= 3 and all(v is not None for v in nums[:3]):
            return "ENZD" if _digits(nums[1]) > _digits(nums[0]) else "NEZD"
    return "PNEZD"


def parse_points(text: str, order: str = "auto") -> list[Shot]:
    """The shots of a points file. Header and comment rows are skipped;
    ``order`` is one of :data:`ORDERS`. Raises ValueError when nothing
    reads, so a wrong file says so instead of importing nothing."""
    rows = []
    for raw in text.splitlines():
        line = raw.strip().lstrip("﻿")
        if line and not line.startswith(("#", "//")):
            rows.append(_cells(line))
    if order == "auto":
        order = sniff_order(rows)
    if order not in ORDERS:
        raise ValueError(f"unknown column order {order}")
    idx = {c: i for i, c in enumerate(order)}
    out: list[Shot] = []
    auto = 1
    for cells in rows:
        need = max(idx["N"], idx["E"], idx["Z"]) + 1
        if len(cells) < need:
            continue
        n, e, z = (_num(cells[idx[k]]) for k in "NEZ")
        if n is None or e is None or z is None:
            continue
        name = cells[idx["P"]] if "P" in idx else str(auto)
        code = cells[idx["D"]] if "D" in idx and len(cells) > idx["D"] else ""
        out.append(Shot(name, e, n, z, code.strip()))
        auto += 1
    if not out:
        raise ValueError("ไม่พบจุดในไฟล์ (ตรวจลำดับคอลัมน์ P,N,E,Z,D)")
    return out


# -- 2. the axis -----------------------------------------------------------------------------

def is_cl(code: str, codes=CL_CODES) -> bool:
    c = code.strip().upper()
    return any(c == k.upper() or re.match(rf"^{re.escape(k.upper())}[\s\-_]*\d*$", c) for k in codes)


def _name_key(name: str):
    m = re.search(r"\d+", name)
    return int(m.group()) if m else None


def centerline_from_codes(shots: list[Shot], codes=CL_CODES) -> list[Point]:
    """The axis through the shots coded centreline, in survey order: by
    point number when every one is numbered and that order runs along
    the road, otherwise a nearest-neighbour chain from the shot farthest
    from the others' centre (one end of the road)."""
    cl = [s for s in shots if is_cl(s.code, codes)]
    if len(cl) < 2:
        return []
    keys = [_name_key(s.name) for s in cl]
    pts: list[Point]
    if all(k is not None for k in keys):
        by_number = [(s.e, s.n) for _k, s in sorted(zip(keys, cl), key=lambda t: t[0])]
    else:
        by_number = None
    # the chain: start at an end, always the nearest unused shot next
    rest = [(s.e, s.n) for s in cl]
    cx = sum(p[0] for p in rest) / len(rest)
    cy = sum(p[1] for p in rest) / len(rest)
    start = max(rest, key=lambda p: (p[0] - cx) ** 2 + (p[1] - cy) ** 2)
    chain = [start]
    rest.remove(start)
    while rest:
        last = chain[-1]
        nxt = min(rest, key=lambda p: (p[0] - last[0]) ** 2 + (p[1] - last[1]) ** 2)
        chain.append(nxt)
        rest.remove(nxt)
    pts = chain
    if by_number is not None and A.polyline_length(by_number) <= A.polyline_length(chain) * 1.05:
        pts = by_number
    # one shot per position
    clean: list[Point] = []
    for p in pts:
        if not clean or math.dist(p, clean[-1]) > 1e-6:
            clean.append(p)
    return clean


# -- 3. the analysis ------------------------------------------------------------------------

@dataclass
class Settings:
    step: float = 25.0
    half_width: float = 15.0
    sample: float = 0.5
    width: float = 6.0
    crown: float = 2.5
    shoulder: float = 1.0
    shoulder_slope: float = 4.0
    cut_hv: float = 1.5
    fill_hv: float = 2.0
    method: str = "prismoidal"
    max_edge: float = 0.0           # 0: keep every triangle of the TIN

    def template(self) -> P.Template:
        return P.Template(self.width, self.cut_hv, self.fill_hv, self.crown,
                          self.shoulder, self.shoulder_slope)


@dataclass
class Section:
    s: float
    ground: list
    design: Optional[list]
    z_ground: Optional[float]       # on the axis (NGL)
    z_design: Optional[float]
    cut: float = 0.0
    fill: float = 0.0


@dataclass
class Analysis:
    axis: list
    tin: T.Tin
    pvis: list                      # [(s, z, vc)]
    grade: list                     # (s, z), curves sampled
    curves: list
    profile: list                   # ProfilePoint
    sections: list                  # Section
    rows: list                      # EarthworksRow
    settings: Settings
    origin: tuple = (0.0, 0.0, 0.0)
    warnings: list = field(default_factory=list)

    @property
    def length(self) -> float:
        return A.polyline_length(self.axis)

    @property
    def cut_total(self) -> float:
        return self.rows[-1].cut_total if self.rows else 0.0

    @property
    def fill_total(self) -> float:
        return self.rows[-1].fill_total if self.rows else 0.0


def build_tin(shots: list[Shot], max_edge: float = 0.0) -> T.Tin:
    return T.build_tin([(s.e, s.n, s.z) for s in shots],
                       max_edge=max_edge if max_edge > 0 else None, name="TERRAIN")


def auto_pvis(tin: T.Tin, axis: list, every: float = 100.0, raise_by: float = 0.5,
              vc: float = 60.0) -> list:
    """A first grade line to start from: a PVI every ``every`` metres on
    the ground smoothed over that span, ``raise_by`` above it (a road
    sits on a low embankment), with a vertical curve at each inner PVI."""
    length = A.polyline_length(axis)
    ground = [(p.s, p.z) for p in P.ground_profile(tin, axis, max(2.0, every / 20.0))
              if p.z is not None]
    if len(ground) < 2:
        return []
    n = max(1, int(round(length / every)))
    out = []
    for k in range(n + 1):
        s = length * k / n
        near = [z for s_, z in ground if abs(s_ - s) <= every / 2.0] or \
            [min(ground, key=lambda g: abs(g[0] - s))[1]]
        out.append((length if k == n else round(s, 3), round(sum(near) / len(near) + raise_by, 3),
                    0.0 if k in (0, n) else vc))
    return out


def analyse(shots: list[Shot], axis: list, pvis: list, settings: Settings,
            tin: Optional[T.Tin] = None) -> Analysis:
    """Everything the panel shows, from the shots, the axis, the PVIs
    ``[(station, elevation, vertical-curve length)]`` and the settings."""
    if len(axis) < 2:
        raise ValueError("ยังไม่มีแนวศูนย์กลางทาง (ต้องมีจุดรหัส CL อย่างน้อย 2 จุด "
                         "หรือเลือกเส้นในโมเดล)")
    tin = tin or build_tin(shots, settings.max_edge)
    if not tin.triangles:
        raise ValueError("สร้างพื้นผิว TIN ไม่ได้ (จุดน้อยหรืออยู่ในแนวเดียวกัน)")
    warnings = []
    pvis = sorted([(float(s), float(z), float(v or 0.0)) for s, z, v in pvis], key=lambda p: p[0])
    # a table shows stations to the millimetre: the first and last PVI
    # that close to the axis's ends are its ends, or the end section
    # falls past the grade and loses its design
    length = A.polyline_length(axis)
    if pvis and abs(pvis[0][0]) < 0.01:
        pvis[0] = (0.0,) + pvis[0][1:]
    if pvis and abs(pvis[-1][0] - length) < 0.01:
        pvis[-1] = (length,) + pvis[-1][1:]
    grade: list = []
    curves: list = []
    if len(pvis) >= 2:
        base = [(s, z) for s, z, _v in pvis]
        lengths = [v for _s, _z, v in pvis]
        curves = P.vertical_curves(base, lengths)
        grade = P.grade_with_curves(base, lengths)
        for (s, _z, v) in pvis:
            c = next((c for c in curves if abs(c.s - s) < 1e-9), None)
            if v > 0 and c is not None and c.length < v - 1e-6:
                warnings.append(f"โค้งดิ่งที่ {A.format_station(s, 3)} ยาวเกินช่วงทาง "
                                f"ลดเหลือ {c.length:.3f} ม.")
    else:
        warnings.append("ยังไม่มีเส้นระดับออกแบบ (ต้องมี PVI อย่างน้อย 2 จุด) "
                        "— แสดงเฉพาะระดับดินเดิม")
    template = settings.template()
    prof = P.ground_profile(tin, axis, settings.step)
    sections = []
    for st in A.stations(axis, settings.step):
        regular = abs(st.s / settings.step - round(st.s / settings.step)) < 1e-6
        if not regular and st.s > 1e-6 and abs(st.s - A.polyline_length(axis)) > 1e-6:
            continue
        ground = P.cross_section(tin, st, settings.half_width, settings.sample)
        if len(ground) < 2:
            warnings.append(f"สถานี {A.format_station(st.s, 3)} อยู่นอกพื้นผิว — ข้าม")
            continue
        zd = P.grade_at(grade, st.s) if grade else None
        design = P.design_section(ground, zd, template) if zd is not None else None
        cut, fill = P.areas(ground, design) if design else (0.0, 0.0)
        sections.append(Section(st.s, ground, design, P._z_on(ground, 0.0), zd, cut, fill))
    rows = P.earthworks(tin, axis, grade, settings.step, template, settings.half_width,
                        settings.sample, settings.method) if grade else []
    xs = [p[0] for p in tin.points]
    ys = [p[1] for p in tin.points]
    zs = [p[2] for p in tin.points]
    origin = (math.floor(min(xs) / 100.0) * 100.0, math.floor(min(ys) / 100.0) * 100.0,
              math.floor(min(zs)))
    return Analysis(axis, tin, pvis, grade, curves, prof, sections, rows, settings, origin,
                    warnings)


# -- 4. the outputs -------------------------------------------------------------------------

def terrain_mesh(an: Analysis) -> list:
    """The TIN as triangles of local (x, y, z) about the origin."""
    ox, oy, oz = an.origin
    pts = [(x - ox, y - oy, z - oz) for x, y, z in an.tin.points]
    return [(pts[a], pts[b], pts[c]) for a, b, c in an.tin.triangles]


def _fixed(design: list, template: P.Template) -> list:
    """The design section with exactly one daylight point each side (the
    edge itself repeated when a side has none), so consecutive sections
    have as many points and can be lofted."""
    top = template.top(0.0)
    want = len(top) + 2
    if len(design) == want:
        return design
    left = design[0] if len(design) > len(top) and design[0][0] < top[0][0] - 1e-9 else None
    core = design[1:] if left is not None else design
    right = core[-1] if len(core) > len(top) else None
    core = core[:-1] if right is not None else core
    return [left or core[0]] + core + [right or core[-1]]


def corridor_mesh(an: Analysis, step: float = 5.0) -> list:
    """The finished road and its side slopes as triangles (local
    coordinates), lofted between design sections every ``step`` metres."""
    if not an.grade:
        return []
    template = an.settings.template()
    ox, oy, oz = an.origin
    rings = []
    s = 0.0
    length = an.length
    marks = []
    while s < length - 1e-6:
        marks.append(s)
        s += step
    marks.append(length)
    for s in marks:
        st = A.point_at(an.axis, s)
        zd = P.grade_at(an.grade, s)
        if zd is None:
            rings.append(None)
            continue
        ground = P.cross_section(an.tin, st, an.settings.half_width, an.settings.sample)
        if len(ground) < 2:
            rings.append(None)
            continue
        design = _fixed(P.design_section(ground, zd, template), template)
        ring = []
        for o, z in design:
            x, y = st.offset_point(o)
            ring.append((x - ox, y - oy, z - oz))
        rings.append(ring)
    tris = []
    for r0, r1 in zip(rings, rings[1:]):
        if r0 is None or r1 is None or len(r0) != len(r1):
            continue
        for k in range(len(r0) - 1):
            a, b, c, d = r0[k], r0[k + 1], r1[k + 1], r1[k]
            for tri in ((a, b, c), (a, c, d)):
                if _area3(*tri) > 1e-8:
                    tris.append(tri)
    return tris


def _area3(a, b, c) -> float:
    ux, uy, uz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
    vx, vy, vz = c[0] - a[0], c[1] - a[1], c[2] - a[2]
    return math.sqrt((uy * vz - uz * vy) ** 2 + (uz * vx - ux * vz) ** 2 + (ux * vy - uy * vx) ** 2) / 2


def earthworks_csv(an: Analysis) -> str:
    out = ["สถานี,ระดับดินเดิม,ระดับออกแบบ,พื้นที่ดินตัด (ม²),พื้นที่ดินถม (ม²),"
           "ปริมาตรดินตัด (ม³),ปริมาตรดินถม (ม³),ดินตัดสะสม (ม³),ดินถมสะสม (ม³),สุทธิสะสม (ม³)"]
    for r in an.rows:
        out.append(",".join([
            A.format_station(r.s, 3), "" if r.z_ground is None else f"{r.z_ground:.3f}",
            "" if r.z_design is None else f"{r.z_design:.3f}", f"{r.cut_area:.3f}",
            f"{r.fill_area:.3f}", f"{r.cut_volume:.3f}", f"{r.fill_volume:.3f}",
            f"{r.cut_total:.3f}", f"{r.fill_total:.3f}", f"{r.mass:.3f}"]))
    return "\n".join(out) + "\n"


def dxf_document(an: Analysis, hscale: float = 1.0, vscale: float = 10.0,
                 text_height: float = 2.0, columns: int = 3):
    """An ezdxf document with the plan (axis, stations, section lines),
    the profile (grid, ground, grade with its curves and PVI labels, bands)
    and every cross section with its labels and areas -- in real metres,
    one drawing unit a metre (the profile's vertical exaggerated)."""
    import ezdxf

    doc = ezdxf.new("R2010", setup=True)
    doc.header["$INSUNITS"] = 6
    msp = doc.modelspace()
    layers = {"WANIC-แนวทาง": 7, "WANIC-สถานี": 1, "WANIC-ดินเดิม": 3, "WANIC-ออกแบบ": 1,
              "WANIC-กริด": 8, "WANIC-ข้อความ": 7}
    for name, color in layers.items():
        if name not in doc.layers:
            doc.layers.add(name, color=color)
    h = text_height

    def text(s, pos, height=h, rot=0.0, align="MIDDLE_CENTER", layer="WANIC-ข้อความ"):
        from ezdxf.enums import TextEntityAlignment
        t = msp.add_text(s, height=height, dxfattribs={"layer": layer, "rotation": rot})
        t.set_placement(pos, align=getattr(TextEntityAlignment, align))

    def line(a, b, layer="WANIC-กริด"):
        msp.add_line(a, b, dxfattribs={"layer": layer})

    def poly(pts, layer):
        if len(pts) >= 2:
            msp.add_lwpolyline(pts, dxfattribs={"layer": layer})

    ox, oy = an.origin[0], an.origin[1]
    # the plan, in its true place
    poly(an.axis, "WANIC-แนวทาง")
    for st in A.stations(an.axis, an.settings.step):
        if abs(st.s / an.settings.step - round(st.s / an.settings.step)) > 1e-6:
            continue
        hw = an.settings.half_width
        line(st.offset_point(-hw), st.offset_point(hw), "WANIC-สถานี")
        label = A.format_station(st.s, 0)
        rot = (st.angle + 90.0) % 360.0
        if 90.0 < rot <= 270.0:
            rot -= 180.0
        text(label, st.offset_point(-(hw + h + 0.45 * h * len(label))), h, rot)
    # the profile, below the plan's extents
    zs = [p.z for p in an.profile if p.z is not None] + [z for _s, z in an.grade]
    if not zs:
        return doc
    datum = math.floor(min(zs)) - 1.0
    top = math.ceil(max(zs)) + 1.0
    x0 = ox
    y0 = oy - (top - datum) * vscale - 40.0 * h
    band = 9.0 * h
    length = an.length

    def pd(s, z):
        return (x0 + s * hscale, y0 + (z - datum) * vscale)
    level = datum
    while level <= top + 1e-9:
        y = pd(0, level)[1]
        line((x0, y), (x0 + length * hscale, y))
        text(f"{level:.3f}", (x0 - h, y), 0.8 * h, align="MIDDLE_RIGHT")
        text(f"{level:.3f}", (x0 + length * hscale + h, y), 0.8 * h, align="MIDDLE_LEFT")
        level += 1.0
    yb = y0 - 3 * band
    for p in an.profile:
        x = pd(p.s, datum)[0]
        line((x, yb), (x, pd(0, top)[1]))
        text(A.format_station(p.s, 3), (x, yb + 0.5 * band), 0.8 * h, 90.0)
        if p.z is not None:
            text(f"{p.z:.3f}", (x, yb + 1.5 * band), 0.8 * h, 90.0)
        zd = P.grade_at(an.grade, p.s) if an.grade else None
        if zd is not None:
            text(f"{zd:.3f}", (x, yb + 2.5 * band), 0.8 * h, 90.0)
    for k, title in enumerate(("สถานี", "ระดับดินเดิม", "ระดับออกแบบ", "")):
        line((x0 - 14 * h, yb + k * band), (x0 + length * hscale, yb + k * band))
        if title:
            text(title, (x0 - 13 * h, yb + (k + 0.5) * band), 0.8 * h, align="MIDDLE_LEFT")
    poly([pd(p.s, p.z) for p in an.profile if p.z is not None], "WANIC-ดินเดิม")
    if an.grade:
        poly([pd(s, z) for s, z in an.grade], "WANIC-ออกแบบ")
        base = [(s, z) for s, z, _v in an.pvis]
        for (s0, z0), (s1, z1), g in zip(base, base[1:], P.grade_slopes(base)):
            a, b = pd(s0, z0), pd(s1, z1)
            ang = math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))
            text(f"G = {g:+.3f} %", ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2 + 1.5 * h), h, ang)
        for c in an.curves:
            x, y = pd(c.s, c.z)
            line((x, y), (x, y + 14 * h), "WANIC-ข้อความ")
            for k, s_ in enumerate((f"PVI STA. {A.format_station(c.s, 3)}", f"ELEV. = {c.z:.3f}",
                                    f"VC. = {c.length:.3f}", f"MO. = {c.middle_ordinate:+.3f}")):
                text(s_, (x + 0.6 * h, y + 14 * h - (k + 0.5) * 1.3 * h), h, align="MIDDLE_LEFT")
    text(f"รูปตัดตามยาว   ราบ 1:{1000 / hscale:g}   ดิ่ง 1:{1000 / vscale:g}",
         (x0, pd(0, top)[1] + 3 * h), 1.5 * h, align="MIDDLE_LEFT")
    # the cross sections, under the profile's bands
    hw = an.settings.half_width
    sv = 1.0
    cell_w = 2 * hw + 30 * h
    cell_h = 0.0
    for sec in an.sections:
        zz = [z for _o, z in sec.ground] + ([z for _o, z in sec.design] if sec.design else [])
        cell_h = max(cell_h, (math.ceil(max(zz)) - math.floor(min(zz)) + 2) * sv + 10 * h)
    ytop = yb - 10 * h
    for k, sec in enumerate(an.sections):
        col, row = k % columns, k // columns
        zz = [z for _o, z in sec.ground] + ([z for _o, z in sec.design] if sec.design else [])
        sd = math.floor(min(zz)) - 1.0
        cx = x0 + col * cell_w + hw + 8 * h
        cy = ytop - (row + 1) * cell_h + 6 * h

        def sp(o, z, cx=cx, cy=cy, sd=sd):
            return (cx + o, cy + (z - sd) * sv)
        st_top = math.ceil(max(zz)) + 1.0
        line(sp(-hw, sd), sp(hw, sd))
        line(sp(-hw, sd), sp(-hw, st_top))
        level = sd
        while level <= st_top + 1e-9:
            line(sp(-hw - 0.8 * h, level), sp(-hw, level))
            text(f"{level:.0f}", sp(-hw - 1.2 * h, level), 0.8 * h, align="MIDDLE_RIGHT")
            level += 1.0
        line(sp(0, sd), sp(0, st_top), "WANIC-ออกแบบ")
        poly([sp(o, z) for o, z in sec.ground], "WANIC-ดินเดิม")
        text(f"STA. {A.format_station(sec.s, 3)}", (cx, cy - 2 * h), h)
        if sec.z_ground is not None:
            text(f"NGL = {sec.z_ground:.3f}", (cx, cy - 3.6 * h), 0.8 * h)
        if sec.design:
            poly([sp(o, z) for o, z in sec.design], "WANIC-ออกแบบ")
            half = an.settings.width / 2.0
            for o in (-half, 0.0, half):
                z = P._z_on(sec.design, o)
                if z is not None:
                    text(f"{z:.3f}", (sp(o, z)[0], sp(o, z)[1] + 1.6 * h), 0.8 * h)
            text(f"ดินตัด {sec.cut:.3f} ม²", (cx + hw + 2 * h, cy + 1.5 * h), 0.8 * h,
                 align="MIDDLE_LEFT")
            text(f"ดินถม {sec.fill:.3f} ม²", (cx + hw + 2 * h, cy), 0.8 * h, align="MIDDLE_LEFT")
    return doc
