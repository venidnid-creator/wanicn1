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


# -- 3. the pavement ------------------------------------------------------------------------

#: Pavement structures to start from, top layer first: (name, thickness m,
#: colour). Thicknesses are the usual ones of the DRR (ทช.) and DOH (ทล.)
#: standard drawings for a light-to-medium traffic road; the standard sheet
#: chosen for the project's traffic and subgrade CBR governs -- every value
#: is editable in the panel.
PAVEMENTS = {
    "drr-ac": ("ทช. ถนนลาดยาง ผิวแอสฟัลต์คอนกรีต (AC)", "asphalt", [
        ("ผิวทางแอสฟัลต์คอนกรีต (AC)", 0.05, (0.15, 0.15, 0.17)),
        ("ชั้นพื้นทางหินคลุก", 0.20, (0.62, 0.60, 0.56)),
        ("ชั้นรองพื้นทางวัสดุมวลรวม", 0.20, (0.80, 0.66, 0.42))]),
    "drr-st": ("ทช. ถนนลาดยาง ผิวเคลือบแอสฟัลต์ 2 ชั้น (DBST)", "asphalt", [
        ("ผิวทางลาดยางเคลือบผิว 2 ชั้น (DBST)", 0.025, (0.18, 0.18, 0.20)),
        ("ชั้นพื้นทางหินคลุก", 0.20, (0.62, 0.60, 0.56)),
        ("ชั้นรองพื้นทางลูกรัง", 0.15, (0.78, 0.45, 0.30))]),
    "drr-rc": ("ทช. ถนนคอนกรีตเสริมเหล็ก", "concrete", [
        ("ผิวทางคอนกรีตเสริมเหล็ก", 0.20, (0.80, 0.80, 0.77)),
        ("ชั้นพื้นทางหินคลุก", 0.15, (0.62, 0.60, 0.56)),
        ("ชั้นรองพื้นทางวัสดุมวลรวม", 0.20, (0.80, 0.66, 0.42))]),
    "doh-ac": ("ทล. ถนนลาดยาง ผิวแอสฟัลต์คอนกรีต (AC)", "asphalt", [
        ("ผิวทาง AC (Wearing Course)", 0.05, (0.12, 0.12, 0.14)),
        ("ชั้นรองผิว AC (Binder Course)", 0.05, (0.25, 0.25, 0.27)),
        ("ชั้นพื้นทางหินคลุก", 0.20, (0.62, 0.60, 0.56)),
        ("ชั้นรองพื้นทางวัสดุมวลรวม", 0.20, (0.80, 0.66, 0.42)),
        ("ชั้นวัสดุคัดเลือก ก", 0.30, (0.70, 0.56, 0.36))]),
    "doh-rc": ("ทล. ถนนคอนกรีต (JRCP)", "concrete", [
        ("ผิวทางคอนกรีตเสริมเหล็ก (JRCP)", 0.25, (0.82, 0.82, 0.79)),
        ("ชั้นพื้นทางหินคลุก", 0.15, (0.62, 0.60, 0.56)),
        ("ชั้นรองพื้นทางวัสดุมวลรวม", 0.20, (0.80, 0.66, 0.42)),
        ("ชั้นวัสดุคัดเลือก ก", 0.30, (0.70, 0.56, 0.36))]),
    "custom": ("กำหนดเอง", "asphalt", []),
}


def pavement_layers(key: str) -> list:
    return [list(layer) for layer in PAVEMENTS.get(key, PAVEMENTS["drr-ac"])[2]]


def pavement_kind(key: str) -> str:
    return PAVEMENTS.get(key, PAVEMENTS["drr-ac"])[1]


# -- 4. the analysis ------------------------------------------------------------------------

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
    pavement: str = "drr-ac"
    layers: Optional[list] = None   # [(name, thickness, colour)], None: the preset's

    def pavement_layers(self) -> list:
        layers = self.layers if self.layers is not None else pavement_layers(self.pavement)
        return [(str(n), float(t), tuple(c)) for n, t, c in layers if float(t) > 0]

    @property
    def structure(self) -> float:
        """Total thickness of the pavement: the earthworks stop under it."""
        return sum(t for _n, t, _c in self.pavement_layers())

    @property
    def finished_width(self) -> float:
        return self.width + 2.0 * self.shoulder

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
    formation: Optional[list] = None   # the subgrade under the pavement, out to daylight


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
    hcurves: list = field(default_factory=list)

    @property
    def designed_length(self) -> float:
        """The length of axis the grade line covers."""
        if not self.grade:
            return 0.0
        return max(0.0, min(self.length, self.grade[-1][0]) - max(0.0, self.grade[0][0]))

    def layer_quantities(self) -> list:
        """(name, thickness, width, volume m³) of each pavement layer, and
        the top layer's area m² as the fifth item."""
        w = self.settings.finished_width
        L = self.designed_length
        return [(n, t, w, t * w * L, w * L) for n, t, _c in self.settings.pavement_layers()]

    @property
    def length(self) -> float:
        return A.polyline_length(self.axis)

    @property
    def cut_total(self) -> float:
        return self.rows[-1].cut_total if self.rows else 0.0

    @property
    def fill_total(self) -> float:
        return self.rows[-1].fill_total if self.rows else 0.0


def formation(design: list, template: P.Template, total: float) -> list:
    """The design section with the pavement taken off: the side slopes as
    they are, and under the finished surface (platform and shoulders) the
    subgrade ``total`` lower -- the line the cut and fill are measured to,
    so the pavement's own materials are not counted as earth."""
    if total <= 0 or not design:
        return design
    top = template.top(0.0)
    lo, hi = top[0][0], top[-1][0]
    left = [p for p in design if p[0] < lo - 1e-9]
    right = [p for p in design if p[0] > hi + 1e-9]
    mid: list = []
    for o, z in design:
        if lo - 1e-9 <= o <= hi + 1e-9 and (not mid or abs(o - mid[-1][0]) > 1e-9):
            mid.append((o, z))
    if len(mid) < 2:
        return design
    eps = min(1e-3, (hi - lo) / 100.0)
    inner = [(o, z - total) for o, z in mid]
    inner[0] = (lo + eps, inner[0][1])
    inner[-1] = (hi - eps, inner[-1][1])
    return left + [mid[0]] + inner + [mid[-1]] + right


def layer_polygons(design: list, template: P.Template, layers: list) -> list:
    """Each pavement layer across the finished width as a closed outline
    of (offset, z), top layer first, with its colour: ``[(name, pts, colour)]``."""
    top = template.top(0.0)
    lo, hi = top[0][0], top[-1][0]
    surface = []
    for o, z in design:
        if lo - 1e-9 <= o <= hi + 1e-9 and (not surface or abs(o - surface[-1][0]) > 1e-9):
            surface.append((o, z))
    out = []
    depth = 0.0
    for name, t, colour in layers:
        upper = [(o, z - depth) for o, z in surface]
        depth += t
        lower = [(o, z - depth) for o, z in surface]
        out.append((name, upper + list(reversed(lower)), colour))
    return out


def _earthworks(tin, axis, grade, settings: Settings) -> list:
    """Cut and fill per station measured to the subgrade (under the
    pavement), volumes between stations prismoidal (the middle section
    measured) or by end areas -- :func:`core.road.profile.earthworks` with
    the formation in place of the finished surface."""
    template = settings.template()
    total = settings.structure

    def section_areas(st):
        zd = P.grade_at(grade, st.s)
        ground = P.cross_section(tin, st, settings.half_width, settings.sample)
        if zd is None or len(ground) < 2:
            return None
        return P.areas(ground, formation(P.design_section(ground, zd, template), template, total))

    rows = []
    cut_total = fill_total = 0.0
    previous = None
    for st in A.stations(axis, settings.step):
        zg = tin.z_at(st.x, st.y)
        zd = P.grade_at(grade, st.s)
        result = section_areas(st)
        if result is None:
            rows.append(P.EarthworksRow(st.s, zg, zd, 0.0, 0.0, 0.0, 0.0, cut_total, fill_total))
            previous = None
            continue
        cut_a, fill_a = result
        cut_v = fill_v = 0.0
        if previous is not None:
            s0, c0, f0 = previous
            length = st.s - s0
            if settings.method == "prismoidal":
                mid = section_areas(A.point_at(axis, (s0 + st.s) / 2.0)) or \
                    ((c0 + cut_a) / 2.0, (f0 + fill_a) / 2.0)
                cut_v = P.prismoidal(c0, mid[0], cut_a, length)
                fill_v = P.prismoidal(f0, mid[1], fill_a, length)
            else:
                cut_v = P.end_area(c0, cut_a, length)
                fill_v = P.end_area(f0, fill_a, length)
        cut_total += cut_v
        fill_total += fill_v
        rows.append(P.EarthworksRow(st.s, zg, zd, cut_a, fill_a, cut_v, fill_v, cut_total, fill_total))
        previous = (st.s, cut_a, fill_a)
    return rows


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
        form = formation(design, template, settings.structure) if design else None
        cut, fill = P.areas(ground, form) if design else (0.0, 0.0)
        sections.append(Section(st.s, ground, design, P._z_on(ground, 0.0), zd, cut, fill, form))
    rows = _earthworks(tin, axis, grade, settings) if grade else []
    hcurves = A.horizontal_curves(axis)
    xs = [p[0] for p in tin.points]
    ys = [p[1] for p in tin.points]
    zs = [p[2] for p in tin.points]
    origin = (math.floor(min(xs) / 100.0) * 100.0, math.floor(min(ys) / 100.0) * 100.0,
              math.floor(min(zs)))
    return Analysis(axis, tin, pvis, grade, curves, prof, sections, rows, settings, origin,
                    warnings, hcurves)


# -- 5. the outputs -------------------------------------------------------------------------

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


def _aci(colour) -> int:
    """The nearest of a few AutoCAD colours for an (r, g, b) in 0..1."""
    table = {1: (1, 0, 0), 2: (1, 1, 0), 3: (0, 1, 0), 4: (0, 1, 1), 5: (0, 0, 1), 6: (1, 0, 1),
             7: (1, 1, 1), 8: (0.5, 0.5, 0.5), 9: (0.75, 0.75, 0.75), 30: (1, 0.5, 0),
             32: (0.65, 0.33, 0), 40: (1, 0.75, 0), 42: (0.65, 0.5, 0), 250: (0.2, 0.2, 0.2)}
    return min(table, key=lambda k: sum((a - b) ** 2 for a, b in zip(table[k], colour)))


def dxf_document(an: Analysis, hscale: float = 1.0, vscale: float = 10.0,
                 text_height: float = 2.0, columns: int = 3, section_text: float = 0.35):
    """An ezdxf document with the plan (axis, stations, section lines and
    the horizontal curves' PI / PC / PT and data), the profile (grid,
    ground, grade with its vertical curves and PVI labels, bands), every
    cross section at true scale with its pavement layers, labels and
    areas, and the pavement quantities -- one drawing unit a metre (the
    profile's vertical exaggerated). Text is in the WANIC-TH style
    (Tahoma), which has Thai glyphs, so Thai reads in any CAD."""
    import ezdxf
    from ezdxf.enums import TextEntityAlignment

    doc = ezdxf.new("R2010", setup=True)
    doc.header["$INSUNITS"] = 6
    if "WANIC-TH" not in doc.styles:
        doc.styles.add("WANIC-TH", font="tahoma.ttf")
    msp = doc.modelspace()
    layers = {"WANIC-แนวทาง": 7, "WANIC-สถานี": 1, "WANIC-โค้งราบ": 4, "WANIC-ดินเดิม": 3,
              "WANIC-ออกแบบ": 1, "WANIC-คันทาง": 6, "WANIC-กริด": 8, "WANIC-ข้อความ": 7}
    template = an.settings.template()
    pave = an.settings.pavement_layers()
    for k, (name, _t, colour) in enumerate(pave):
        layers[f"WANIC-ชั้นทาง-{k + 1}"] = _aci(colour)
    for name, color in layers.items():
        if name not in doc.layers:
            doc.layers.add(name, color=color)
    h = text_height

    def text(s, pos, height=h, rot=0.0, align="MIDDLE_CENTER", layer="WANIC-ข้อความ"):
        t = msp.add_text(s, height=height, dxfattribs={"layer": layer, "rotation": rot,
                                                       "style": "WANIC-TH"})
        t.set_placement(pos, align=getattr(TextEntityAlignment, align))

    def line(a, b, layer="WANIC-กริด"):
        msp.add_line(a, b, dxfattribs={"layer": layer})

    def poly(pts, layer, closed=False):
        if len(pts) >= 2:
            msp.add_lwpolyline(pts, close=closed, dxfattribs={"layer": layer})

    ox, oy = an.origin[0], an.origin[1]
    # -- the plan, in its true place
    poly(an.axis, "WANIC-แนวทาง")
    hw = an.settings.half_width
    for st in A.stations(an.axis, an.settings.step):
        if abs(st.s / an.settings.step - round(st.s / an.settings.step)) > 1e-6:
            continue
        line(st.offset_point(-hw), st.offset_point(hw), "WANIC-สถานี")
        label = A.format_station(st.s, 0)
        rot = (st.angle + 90.0) % 360.0
        if 90.0 < rot <= 270.0:
            rot -= 180.0
        text(label, st.offset_point(-(hw + h + 0.45 * h * len(label))), h, rot)
    for c in an.hcurves:
        if c.radius > 0:
            line(c.pc, c.pi, "WANIC-โค้งราบ")
            line(c.pi, c.pt, "WANIC-โค้งราบ")
            for point, name, s_ in ((c.pc, "PC", c.s_pc), (c.pt, "PT", c.s_pt)):
                msp.add_circle(point, 0.4 * h, dxfattribs={"layer": "WANIC-โค้งราบ"})
                text(f"{name} STA. {A.format_station(s_, 3)}", (point[0], point[1] - 1.5 * h),
                     0.8 * h, layer="WANIC-โค้งราบ")
        msp.add_circle(c.pi, 0.5 * h, dxfattribs={"layer": "WANIC-โค้งราบ"})
        mid = ((c.pc[0] + c.pt[0]) / 2.0, (c.pc[1] + c.pt[1]) / 2.0)
        ux, uy = c.pi[0] - mid[0], c.pi[1] - mid[1]
        n = math.hypot(ux, uy) or 1.0
        x0, y0 = c.pi[0] + ux / n * 8 * h + 2 * h, c.pi[1] + uy / n * 8 * h + 6 * h
        for k, s_ in enumerate(curve_table_lines(c)):
            text(s_, (x0, y0 - k * 1.5 * h), h, align="MIDDLE_LEFT", layer="WANIC-โค้งราบ")
    # -- the profile, below the plan's extents
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
    last = -1e9
    for p in an.profile:
        x = pd(p.s, datum)[0]
        line((x, yb), (x, pd(0, top)[1]))
        if x - last < 1.6 * h:
            continue
        last = x
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
    # the horizontal curves along the profile: PC to PT marked over the bands
    for c in an.hcurves:
        if c.radius > 0:
            a, b = pd(c.s_pc, top), pd(c.s_pt, top)
            line((a[0], a[1] + 2 * h), (b[0], b[1] + 2 * h), "WANIC-โค้งราบ")
            text(f"PI-{c.number}  R = {c.radius:.3f}  Δ = {A.format_dms(c.delta)} {c.side}",
                 ((a[0] + b[0]) / 2, a[1] + 3.2 * h), 0.8 * h, layer="WANIC-โค้งราบ")
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
         (x0, pd(0, top)[1] + 6 * h), 1.5 * h, align="MIDDLE_LEFT")
    # -- the cross sections at true scale, under the profile's bands
    t = section_text
    cell_w = 2 * hw + 18 * t + 14 * t
    cell_h = 0.0
    for sec in an.sections:
        zz = [z for _o, z in sec.ground] + ([z for _o, z in sec.design] if sec.design else [])
        cell_h = max(cell_h, (math.ceil(max(zz)) - math.floor(min(zz)) + 2) + 14 * t)
    ytop = yb - 10 * h
    for k, sec in enumerate(an.sections):
        col, row = k % columns, k // columns
        zz = [z for _o, z in sec.ground] + ([z for _o, z in sec.design] if sec.design else [])
        if sec.formation:
            zz += [z for _o, z in sec.formation]
        sd = math.floor(min(zz)) - 1.0
        cx = x0 + col * cell_w + hw + 6 * t
        cy = ytop - (row + 1) * cell_h + 8 * t

        def sp(o, z, cx=cx, cy=cy, sd=sd):
            return (cx + o, cy + (z - sd))
        st_top = math.ceil(max(zz)) + 1.0
        line(sp(-hw, sd), sp(hw, sd))
        line(sp(-hw, sd), sp(-hw, st_top))
        level = sd
        while level <= st_top + 1e-9:
            line(sp(-hw - 0.4, level), sp(-hw, level))
            text(f"{level:.0f}", sp(-hw - 0.6, level), t, align="MIDDLE_RIGHT")
            level += 1.0
        line(sp(0, sd), sp(0, st_top), "WANIC-ออกแบบ")
        poly([sp(o, z) for o, z in sec.ground], "WANIC-ดินเดิม")
        text(f"STA. {A.format_station(sec.s, 3)}", (cx, cy - 2.2 * t), 1.3 * t)
        if sec.z_ground is not None:
            text(f"NGL = {sec.z_ground:.3f}", (cx, cy - 4.2 * t), t)
        if sec.design:
            poly([sp(o, z) for o, z in sec.design], "WANIC-ออกแบบ")
            if sec.formation and pave:
                poly([sp(o, z) for o, z in sec.formation], "WANIC-คันทาง")
                for j, (_name, outline, _c) in enumerate(layer_polygons(sec.design, template, pave)):
                    poly([sp(o, z) for o, z in outline], f"WANIC-ชั้นทาง-{j + 1}", closed=True)
            # left edge ends at its point, right edge starts at its, the
            # axis above both: three numbers 6 m apart never run together
            half = an.settings.width / 2.0
            for o, dx, dy, align in ((-half, -0.2, 1.0, "BOTTOM_RIGHT"), (0.0, 0.0, 2.6, "BOTTOM_CENTER"),
                                     (half, 0.2, 1.0, "BOTTOM_LEFT")):
                z = P._z_on(sec.design, o)
                if z is not None:
                    q = sp(o, z)
                    text(f"{z:.3f}", (q[0] + dx, q[1] + dy * t), t, align=align)
            xr = cx + hw + 1.0
            text(f"ดินตัด  {sec.cut:.3f} ม²", (xr, cy + 3.0 * t), t, align="MIDDLE_LEFT")
            text(f"ดินถม  {sec.fill:.3f} ม²", (xr, cy + 1.4 * t), t, align="MIDDLE_LEFT")
    # -- the pavement: legend and quantities beside the first section row
    if pave:
        qx, qy = x0 + columns * cell_w + 4 * h, ytop - 2 * h
        title = PAVEMENTS.get(an.settings.pavement, ("กำหนดเอง",))[0]
        text(f"โครงสร้างชั้นทาง: {title}", (qx, qy), h, align="MIDDLE_LEFT")
        text(f"ผิวทางกว้าง {an.settings.width:.2f} ม. ไหล่ทางข้างละ {an.settings.shoulder:.2f} ม. "
             f"ยาว {an.designed_length:,.3f} ม.", (qx, qy - 1.8 * h), 0.8 * h, align="MIDDLE_LEFT")
        for j, (name, th, w, vol, area) in enumerate(an.layer_quantities()):
            y = qy - (j + 2) * 1.8 * h - h
            msp.add_lwpolyline([(qx, y - 0.5 * h), (qx + 2 * h, y - 0.5 * h), (qx + 2 * h, y + 0.5 * h),
                                (qx, y + 0.5 * h)], close=True,
                               dxfattribs={"layer": f"WANIC-ชั้นทาง-{j + 1}"})
            extra = f"  (พื้นที่ผิว {area:,.2f} ม²)" if j == 0 else ""
            text(f"{name}  หนา {th:.3f} ม.  ปริมาตร {vol:,.2f} ม³{extra}", (qx + 3 * h, y), 0.8 * h,
                 align="MIDDLE_LEFT")
    return doc


def curve_table_lines(c) -> list:
    """The data block of a horizontal curve, the way a road plan writes it."""
    fs = A.format_station
    head = f"PI-{c.number}  STA. {fs(c.s_pi, 3)}"
    if c.radius <= 0:
        return [head, f"Δ = {A.format_dms(c.delta)} {c.side}", "(จุดหักมุม ไม่มีโค้ง)"]
    return [head, f"Δ = {A.format_dms(c.delta)} {c.side}", f"R = {c.radius:.3f} ม.",
            f"T = {c.tangent:.3f} ม.", f"L = {c.length:.3f} ม.", f"E = {c.external:.3f} ม.",
            f"M = {c.middle_ordinate:.3f} ม.", f"PC STA. {fs(c.s_pc, 3)}", f"PT STA. {fs(c.s_pt, 3)}"]
