# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
"""จ36 «ตรวจสอบพื้นที่ก่อสร้าง»: which land parcels the road takes, how
much of each (ตร.ม. and ไร่-งาน-ตารางวา), the parcels whose land number is
known and those that are not, and a PDF report with the picture.

The parcels come from a file (KML / KMZ from LandsMaps or Google Earth,
GeoJSON, DXF drawn from the ระวาง, or a CSV of corners); this session could
not reach LandsMaps itself. The road's footprint is what will be built:
from toe to toe of the side slopes (or a right-of-way width), in strips
along the axis; each strip is convex, so a parcel of any shape is clipped
by it exactly (Sutherland–Hodgman) and the pieces summed.

A planning check, not a cadastral survey: the parcel lines are as good as
the file they come from.
"""
from __future__ import annotations

import csv
import io
import json
import math
import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

RAI, NGAN, WA = 1600.0, 400.0, 4.0
PERMISSION = "การนำข้อมูลไปใช้จะต้องได้รับอนุญาตจากเจ้าของพื้นที่แล้วเท่านั้น"
#: keys that hold a land number in KML ExtendedData / GeoJSON properties
NUMBER_KEYS = ("เลขที่ดิน", "parcel_no", "parcelno", "parcel", "land_no", "landno", "lno",
               "เลขโฉนด", "โฉนด", "deed", "deed_no", "number", "name", "ชื่อ")


@dataclass
class Parcel:
    number: str                      # the land number, "" when not known
    ring: list                       # [(e, n)] UTM, not closed
    note: str = ""                   # anything else the file said (ระวาง, ตำบล …)

    @property
    def area(self) -> float:
        return abs(_area(self.ring))


@dataclass
class Taken:
    parcel: Parcel
    area: float                      # m² inside the footprint
    s0: float                        # the stations it spans
    s1: float

    @property
    def share(self) -> float:
        return self.area / self.parcel.area if self.parcel.area > 0 else 0.0


@dataclass
class Check:
    taken: list                      # Taken, along the road
    footprint: float                 # m² of the whole footprint
    outside: float                   # m² of the footprint on no parcel of the file
    strips: list = field(default_factory=list)   # the footprint, [(s, left, right)]
    parcels: list = field(default_factory=list)  # every parcel read
    width_note: str = ""

    @property
    def known(self) -> list:
        return [t for t in self.taken if t.parcel.number]

    @property
    def unknown(self) -> list:
        return [t for t in self.taken if not t.parcel.number]

    @property
    def total(self) -> float:
        return sum(t.area for t in self.taken)


def rai_ngan_wa(m2: float) -> str:
    """1,234.5 ม² → «0-3-8.6» (ไร่-งาน-ตารางวา)."""
    m2 = max(float(m2), 0.0)
    rai = int(m2 // RAI)
    rest = m2 - rai * RAI
    ngan = int(rest // NGAN)
    wa = (rest - ngan * NGAN) / WA
    if round(wa, 1) >= 100:
        ngan, wa = ngan + 1, 0.0
    if ngan >= 4:
        rai, ngan = rai + 1, ngan - 4
    return f"{rai:,}-{ngan}-{wa:.1f}"


# -- geometry ---------------------------------------------------------------------------------

def _area(ring) -> float:
    return 0.5 * sum(p[0] * q[1] - q[0] * p[1] for p, q in zip(ring, ring[1:] + ring[:1]))


def _clip(subject, clip):
    """Sutherland–Hodgman: ``subject`` (any simple polygon) inside the convex
    polygon ``clip`` (counter-clockwise)."""
    out = list(subject)
    for a, b in zip(clip, clip[1:] + clip[:1]):
        if not out:
            break

        def inside(p):
            return (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0]) >= -1e-9

        def cross(p, q):
            dx, dy = q[0] - p[0], q[1] - p[1]
            ex, ey = b[0] - a[0], b[1] - a[1]
            den = dx * ey - dy * ex
            if abs(den) < 1e-15:
                return q
            t = ((a[0] - p[0]) * ey - (a[1] - p[1]) * ex) / den
            return (p[0] + dx * t, p[1] + dy * t)
        src, out = out, []
        for k, q in enumerate(src):
            p = src[k - 1]
            if inside(q):
                if not inside(p):
                    out.append(cross(p, q))
                out.append(q)
            elif inside(p):
                out.append(cross(p, q))
    return out


def _bbox(ring):
    xs, ys = [p[0] for p in ring], [p[1] for p in ring]
    return min(xs), min(ys), max(xs), max(ys)


def inside(p, ring) -> bool:
    x, y = p
    hit = False
    for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1]):
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            hit = not hit
    return hit


# -- coordinates ---------------------------------------------------------------------------------

def wgs84_to_utm(lat: float, lon: float, zone: int = 47, datum: str = "WGS84") -> tuple:
    """(E, N) on the UTM ``zone`` (northern hemisphere) — Snyder's forward
    Transverse Mercator; Indian 1975 through the Thai three-parameter shift."""
    from core import wanic_road as R
    if datum == "Indian1975":
        d = tuple(-v for v in R.INDIAN1975_TO_WGS84)
        lat, lon = R._shift(lat, lon, R.ELLIPSOIDS["WGS84"], R.ELLIPSOIDS["Indian1975"], d)
    a, inv_f = R.ELLIPSOIDS[datum]
    f = 1.0 / inv_f
    e2 = f * (2 - f)
    ep2 = e2 / (1 - e2)
    k0 = 0.9996
    phi, lam = math.radians(lat), math.radians(lon)
    lam0 = math.radians((zone - 1) * 6 - 180 + 3)
    n = a / math.sqrt(1 - e2 * math.sin(phi) ** 2)
    t = math.tan(phi) ** 2
    c = ep2 * math.cos(phi) ** 2
    A = math.cos(phi) * (lam - lam0)
    m = a * ((1 - e2 / 4 - 3 * e2 ** 2 / 64 - 5 * e2 ** 3 / 256) * phi
             - (3 * e2 / 8 + 3 * e2 ** 2 / 32 + 45 * e2 ** 3 / 1024) * math.sin(2 * phi)
             + (15 * e2 ** 2 / 256 + 45 * e2 ** 3 / 1024) * math.sin(4 * phi)
             - (35 * e2 ** 3 / 3072) * math.sin(6 * phi))
    e = 500000.0 + k0 * n * (A + (1 - t + c) * A ** 3 / 6
                             + (5 - 18 * t + t * t + 72 * c - 58 * ep2) * A ** 5 / 120)
    nn = k0 * (m + n * math.tan(phi) * (A * A / 2 + (5 - t + 9 * c + 4 * c * c) * A ** 4 / 24
                                        + (61 - 58 * t + t * t + 600 * c - 330 * ep2) * A ** 6 / 720))
    return e, nn


# -- the parcel files ------------------------------------------------------------------------------

def _number_from(props: dict) -> str:
    low = {str(k).strip().lower(): v for k, v in (props or {}).items()}
    for k in NUMBER_KEYS:
        v = low.get(k.lower())
        if v not in (None, ""):
            m = re.search(r"\d[\d/\-]*", str(v))
            if m:
                return m.group(0)
    return ""


def _note_from(props: dict) -> str:
    keep = []
    for k, v in (props or {}).items():
        if v in (None, "") or str(k).lower() in ("name", "description", "styleurl"):
            continue
        if re.search(r"ระวาง|utm|ตำบล|tambon|อำเภอ|amphoe|หน้าสำรวจ|survey", str(k), re.I):
            keep.append(f"{k} {v}")
    return " · ".join(keep[:3])


def _to_utm(pts, zone, datum):
    """lon/lat pairs → UTM, UTM left as they are."""
    if pts and all(abs(x) <= 180 and abs(y) <= 90 for x, y in pts):
        return [wgs84_to_utm(y, x, zone, datum) for x, y in pts]
    return [(float(x), float(y)) for x, y in pts]


def _open_ring(pts):
    pts = [p for k, p in enumerate(pts) if k == 0 or math.dist(p, pts[k - 1]) > 1e-6]
    if len(pts) > 1 and math.dist(pts[0], pts[-1]) < 1e-6:
        pts = pts[:-1]
    return pts


def read_kml(text: str, zone: int = 47, datum: str = "WGS84") -> list:
    import xml.etree.ElementTree as ET
    root = ET.fromstring(text.encode("utf-8") if isinstance(text, str) else text)

    def tag(e):
        return e.tag.rsplit("}", 1)[-1]
    out = []
    for pm in root.iter():
        if tag(pm) != "Placemark":
            continue
        props = {}
        for e in pm.iter():
            t = tag(e)
            if t in ("name", "description") and e.text:
                props[t] = e.text.strip()
            elif t in ("Data", "SimpleData"):
                key = e.get("name") or ""
                val = e.text if t == "SimpleData" else next(
                    (c.text for c in e if tag(c) == "value"), None)
                if key and val:
                    props[key] = val.strip()
        for poly in (e for e in pm.iter() if tag(e) == "Polygon"):
            outer = next((e for e in poly.iter() if tag(e) == "outerBoundaryIs"), poly)
            coords = next((e for e in outer.iter() if tag(e) == "coordinates"), None)
            if coords is None or not coords.text:
                continue
            pts = []
            for tok in coords.text.split():
                parts = tok.split(",")
                if len(parts) >= 2:
                    pts.append((float(parts[0]), float(parts[1])))
            ring = _open_ring(_to_utm(pts, zone, datum))
            if len(ring) >= 3:
                out.append(Parcel(_number_from(props), ring, _note_from(props)))
    return out


def read_geojson(text: str, zone: int = 47, datum: str = "WGS84") -> list:
    data = json.loads(text)
    feats = data.get("features") if isinstance(data, dict) and "features" in data else [data]
    out = []
    for f in feats or []:
        g = (f or {}).get("geometry") or {}
        props = (f or {}).get("properties") or {}
        polys = [g.get("coordinates") or []] if g.get("type") == "Polygon" else \
            (g.get("coordinates") or []) if g.get("type") == "MultiPolygon" else []
        for poly in polys:
            if not poly:
                continue
            ring = _open_ring(_to_utm([(p[0], p[1]) for p in poly[0]], zone, datum))
            if len(ring) >= 3:
                out.append(Parcel(_number_from(props), ring, _note_from(props)))
    return out


def read_dxf(path: str) -> list:
    """Closed polylines are parcels; a number written inside one (TEXT/MTEXT)
    is its land number."""
    import ezdxf
    doc = ezdxf.readfile(path)
    msp = doc.modelspace()
    rings, labels = [], []
    for e in msp:
        t = e.dxftype()
        if t == "LWPOLYLINE" and (e.closed or len(e) >= 3):
            pts = [(p[0], p[1]) for p in e.get_points("xy")]
            if e.closed or math.dist(pts[0], pts[-1]) < 1e-3:
                rings.append(_open_ring(pts))
        elif t == "POLYLINE" and e.is_closed:
            rings.append(_open_ring([(v.dxf.location[0], v.dxf.location[1]) for v in e.vertices]))
        elif t in ("TEXT", "MTEXT"):
            txt = e.dxf.text if t == "TEXT" else e.plain_text()
            m = re.search(r"\d[\d/\-]*", txt or "")
            if m:
                p = e.dxf.insert
                labels.append(((p[0], p[1]), m.group(0)))
    out = []
    for ring in rings:
        if len(ring) < 3:
            continue
        num = next((n for p, n in labels if inside(p, ring)), "")
        out.append(Parcel(num, ring))
    return out


def read_csv(text: str, zone: int = 47, datum: str = "WGS84") -> list:
    """Rows ``แปลง, E, N[, เลขที่ดิน]`` (corners in order, one parcel per
    first column) — or lat/lon in place of E/N."""
    rows = [r for r in csv.reader(io.StringIO(text)) if r and any(c.strip() for c in r)]
    groups: dict = {}
    for r in rows:
        try:
            x, y = float(r[1].replace(",", "")), float(r[2].replace(",", ""))
        except (IndexError, ValueError):
            continue                                   # a heading
        g = groups.setdefault(r[0].strip(), {"pts": [], "no": ""})
        g["pts"].append((x, y))
        if len(r) > 3 and r[3].strip():
            g["no"] = r[3].strip()
    out = []
    for gid, g in groups.items():
        pts = g["pts"]
        if pts and all(abs(x) <= 90 and abs(y) <= 180 for x, y in pts):   # lat, lon
            pts = [(y, x) for x, y in pts]
        ring = _open_ring(_to_utm(pts, zone, datum))
        if len(ring) >= 3:
            out.append(Parcel(g["no"], ring))
    return out


def read_file(path: str, zone: int = 47, datum: str = "WGS84") -> list:
    p = Path(path)
    ext = p.suffix.lower()
    if ext == ".kmz":
        with zipfile.ZipFile(p) as z:
            name = next(n for n in z.namelist() if n.lower().endswith(".kml"))
            return read_kml(z.read(name).decode("utf-8", "replace"), zone, datum)
    if ext == ".dxf":
        return read_dxf(str(p))
    raw = p.read_bytes()
    for enc in ("utf-8-sig", "cp874"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        text = raw.decode("latin-1")
    if ext == ".kml":
        return read_kml(text, zone, datum)
    if ext in (".geojson", ".json"):
        return read_geojson(text, zone, datum)
    if ext in (".csv", ".txt"):
        return read_csv(text, zone, datum)
    raise ValueError("รองรับไฟล์ KML KMZ GeoJSON DXF CSV")


# -- the road's footprint and the check -------------------------------------------------------------

def footprint(an, width: float | None = None, step: float = 2.0) -> list:
    """[(s, left offset, right offset)] along the axis: toe to toe of the
    side slopes from the sections (between them interpolated), or ±width/2."""
    st = an.settings
    if width:
        half = width / 2.0
        offs = None
    else:
        offs = [(sec.s, sec.design[0][0], sec.design[-1][0]) for sec in an.sections if sec.design]
        half = st.width / 2.0 + st.shoulder
    out, s = [], 0.0
    L = an.length
    while True:
        s = min(s, L)
        if offs:
            k = 0
            while k < len(offs) - 1 and offs[k + 1][0] < s:
                k += 1
            if s <= offs[0][0]:
                left, right = offs[0][1], offs[0][2]
            elif s >= offs[-1][0]:
                left, right = offs[-1][1], offs[-1][2]
            else:
                a, b = offs[k], offs[k + 1]
                t = (s - a[0]) / (b[0] - a[0]) if b[0] > a[0] else 0.0
                left, right = a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t
        else:
            left, right = -half, half
        out.append((s, min(left, -0.5), max(right, 0.5)))
        if s >= L - 1e-9:
            break
        s += step
    return out


def check(an, parcels: list, width: float | None = None, step: float = 2.0) -> Check:
    from core.road import alignment as A
    strips = footprint(an, width, step)
    pts = []
    for s, l, r in strips:
        st = A.point_at(an.axis, s)
        pts.append((s, st.offset_point(l), st.offset_point(r)))
    boxes = [(p, _bbox(p.ring)) for p in parcels]
    hits: dict = {}
    total = 0.0
    for (s0, l0, r0), (s1, l1, r1) in zip(pts, pts[1:]):
        quad = [l0, r0, r1, l1]
        if _area(quad) < 0:
            quad.reverse()
        qa = abs(_area(quad))
        total += qa
        qb = _bbox(quad)
        for p, b in boxes:
            if b[2] < qb[0] or b[0] > qb[2] or b[3] < qb[1] or b[1] > qb[3]:
                continue
            piece = _clip(p.ring, quad)
            a = abs(_area(piece)) if len(piece) >= 3 else 0.0
            if a > 1e-4:
                h = hits.setdefault(id(p), [p, 0.0, s0, s1])
                h[1] += a
                h[2], h[3] = min(h[2], s0), max(h[3], s1)
    taken = [Taken(p, a, s0, s1) for p, a, s0, s1 in hits.values() if a >= 0.05]
    taken.sort(key=lambda t: t.s0)
    note = (f"เขตทางกว้าง {width:g} ม." if width else "จากตีนลาดดินตัด-ถมถึงตีนลาดอีกข้าง (ตามรูปตัดออกแบบ)")
    return Check(taken, total, max(total - sum(t.area for t in taken), 0.0), strips, list(parcels), note)


# -- the report --------------------------------------------------------------------------------------

def report_sheet(an, chk: Check, info: dict | None = None):
    """One A3 sheet: the plan (parcels, the footprint, the axis) and the table."""
    from core import wanic_drawings as D
    from core.road import alignment as A
    info = dict(info or {})
    sh = D.Sheet("LC-01", "ตรวจสอบพื้นที่ก่อสร้าง (แปลงที่ดินที่แนวทางผ่าน)", "-", "LC")
    X0, Y0, X1, Y1 = D.drawing_area()
    sh.text((X0, Y1 - 4), "ตรวจสอบพื้นที่ก่อสร้าง — แปลงที่ดินที่แนวถนนผ่าน", 3.6, "left", "text", True)
    # the plan, left
    px0, py0, px1, py1 = X0, Y0 + 30, X0 + 190, Y1 - 10
    sh.rect(px0, py0, px1, py1, "text", 0.25)
    near = [t.parcel for t in chk.taken]
    others = [p for p in chk.parcels if p not in near]
    xs = [p[0] for p in an.axis] + [q[0] for p in near for q in p.ring]
    ys = [p[1] for p in an.axis] + [q[1] for p in near for q in p.ring]
    bx = (min(xs), min(ys), max(xs), max(ys))
    k = min((px1 - px0 - 10) / max(bx[2] - bx[0], 1.0), (py1 - py0 - 10) / max(bx[3] - bx[1], 1.0))
    cx, cy = (bx[0] + bx[2]) / 2, (bx[1] + bx[3]) / 2
    mx, my = (px0 + px1) / 2, (py0 + py1) / 2

    def v(p):
        return (mx + (p[0] - cx) * k, my + (p[1] - cy) * k)

    def fits(q):
        return px0 + 1 < q[0] < px1 - 1 and py0 + 1 < q[1] < py1 - 1
    for p in others:
        ring = [v(q) for q in p.ring]
        if all(fits(q) for q in ring):
            sh.poly(ring, "grid", 0.13)
    colours = [(253, 217, 140), (191, 224, 252), (204, 242, 199), (250, 199, 209), (224, 209, 250)]
    known_c = [(191, 224, 252), (204, 242, 199), (224, 209, 250), (199, 236, 236)]
    unknown_c = (253, 200, 140)
    for i, t in enumerate(chk.taken):
        ring = [v(q) for q in t.parcel.ring]
        sh.fill(ring, "hatch", rgb=known_c[i % len(known_c)] if t.parcel.number else unknown_c)
        sh.poly(ring, "wall", 0.25)
    # the footprint and the axis
    from core.road import alignment as A2
    left = [v(A2.point_at(an.axis, s).offset_point(l)) for s, l, _r in chk.strips]
    right = [v(A2.point_at(an.axis, s).offset_point(r)) for s, _l, r in chk.strips]
    sh.poly(left + right[::-1], "roof", 0.35)
    sh.poly([v(p) for p in an.axis], "roof", 0.5, False)
    for i, t in enumerate(chk.taken):
        c = v(_centroid(t.parcel.ring))
        sh.text(c, f"{i + 1}", 2.6, "center", "text", True)
        sh.text((c[0], c[1] - 3.4), t.parcel.number or "ไม่ทราบเลขที่ดิน", 1.7, "center",
                "text" if t.parcel.number else "roof")
    s = 100.0                              # the two ends are labelled as key points
    while s < an.length - 20.0:
        p = A.point_at(an.axis, s)
        q = v(p.offset_point(-(abs(chk.strips[0][1]) + 2.0 / k)))   # beside the footprint
        sh.circle(v((p.x, p.y)), 0.5, "roof", 0.25)
        sh.text((q[0] - 0.8, q[1]), A.format_station(s, 0), 1.6, "right", "dim")
        s += 100.0
    # the UTM grid: lines every round step, E along the bottom and N up the left edge
    def w(q):                                         # paper → UTM
        return (cx + (q[0] - mx) / k, cy + (q[1] - my) / k)
    lo, hi = w((px0, py0)), w((px1, py1))
    span = max(hi[0] - lo[0], hi[1] - lo[1])
    step = next((g for g in (10, 20, 25, 50, 100, 200, 250, 500, 1000, 2000, 5000) if span / g <= 8), 10000)
    e = math.ceil(lo[0] / step) * step
    while e < hi[0]:
        x = v((e, 0))[0]
        if px0 + 3 < x < px1 - 3:
            sh.line((x, py0), (x, py1), "grid", 0.08, True)
            sh.line((x, py0), (x, py0 + 2), "text", 0.18)
            sh.text((x + 0.6, py0 + 2.6), f"E {e:,.0f}", 1.6, "left", "dim", False, 90)
        e += step
    n = math.ceil(lo[1] / step) * step
    while n < hi[1]:
        y = v((0, n))[1]
        if py0 + 3 < y < py1 - 3:
            sh.line((px0, y), (px1, y), "grid", 0.08, True)
            sh.line((px1 - 2, y), (px1, y), "text", 0.18)
            sh.text((px1 - 2.6, y + 0.6), f"N {n:,.0f}", 1.6, "right", "dim")
        n += step
    # the key points (their coordinates in the table on the right)
    keypts = [("เริ่มต้น", 0.0, A.point_at(an.axis, 0.0))]
    for c in getattr(an, "hcurves", []) or []:
        keypts.append((f"PI-{c.number}", c.s_pi, type("P", (), {"x": c.pi[0], "y": c.pi[1]})))
    keypts.append(("สิ้นสุด", an.length, A.point_at(an.axis, an.length)))
    for lab, _s, p in keypts:
        q = v((p.x, p.y))
        sh.circle(q, 0.9, "roof", 0.3)
        if q[0] - len(lab) * 1.1 - 2 < px0:         # near the left edge: on the right, below
            sh.text((q[0] + 1.4, q[1] - 5.0), lab, 1.7, "left", "roof", True)
        else:
            sh.text((q[0] - 1.4, q[1] + 1.4), lab, 1.7, "right", "roof", True)
    D.north(sh, (px1 - 8, py1 - 10), 4)
    zone, datum = int(info.get("zone") or 47), str(info.get("datum") or "WGS84")
    sh.text((px0 + 2, py1 - 4), f"ระบบพิกัด UTM {datum} โซน {zone}N · หน่วยเมตร · "
            f"ตารางกริดทุก {step:,} ม. · มาตราส่วนโดยประมาณ 1:{1000 / k:,.0f}", 2.0, "left", "text", True)

    # the legend, under the plan
    ly = py0 - 6
    sh.line((px0, ly + 1), (px0 + 10, ly + 1), "roof", 0.35)
    sh.text((px0 + 12, ly), "ขอบพื้นที่ก่อสร้าง (" + chk.width_note + ")", 2.0)
    sh.fill([(px0, ly - 7), (px0 + 10, ly - 7), (px0 + 10, ly - 4), (px0, ly - 4)], "hatch",
            rgb=known_c[0])
    sh.text((px0 + 12, ly - 6.5), "แปลงที่แนวถนนผ่าน ทราบเลขที่ดิน (ตัวเลขใหญ่ = ลำดับในตาราง ตัวเล็ก = เลขที่ดิน)", 2.0)
    sh.fill([(px0, ly - 13), (px0 + 10, ly - 13), (px0 + 10, ly - 10), (px0, ly - 10)], "hatch",
            rgb=unknown_c)
    sh.text((px0 + 12, ly - 12.5), "แปลงที่แนวถนนผ่าน ไม่ทราบเลขที่ดิน (ต้องตรวจสอบที่สำนักงานที่ดิน)", 2.0)
    sh.line((px0, ly - 17), (px0 + 10, ly - 17), "grid", 0.13)
    sh.text((px0 + 12, ly - 18), "แปลงที่ดินอื่นในไฟล์", 2.0)
    # the summary and the table, right
    tx = px1 + 6
    lines = [f"แนวถนนยาว {an.length:,.2f} ม. · พื้นที่ก่อสร้างรวม {chk.footprint:,.1f} ตร.ม. "
             f"({rai_ngan_wa(chk.footprint)} ไร่)",
             f"ผ่านที่ดิน {len(chk.taken)} แปลง · ทราบเลขที่ดิน {len(chk.known)} แปลง · "
             f"ไม่ทราบเลขที่ดิน {len(chk.unknown)} แปลง",
             f"เข้าไปในที่ดินรวม {chk.total:,.1f} ตร.ม. ({rai_ngan_wa(chk.total)} ไร่-งาน-ตร.ว.)",
             f"พื้นที่ก่อสร้างที่ไม่อยู่ในแปลงใดของไฟล์ {chk.outside:,.1f} ตร.ม. "
             "(ทางสาธารณะ ที่ราชพัสดุ หรือไม่มีข้อมูล)"]
    y = Y1 - 12
    for t in lines:
        sh.text((tx, y), t, 2.2, "left", "text", t.startswith("ผ่าน"))
        y -= 4.6
    cols = [("ที่", 8, "center"), ("เลขที่ดิน", 20, "center"), ("พื้นที่แปลง (ตร.ม.)", 24, "right"),
            ("เข้าไป (ตร.ม.)", 20, "right"), ("ไร่-งาน-ตร.ว.", 20, "center"), ("%", 10, "right"),
            ("ช่วง กม.", 28, "center")]
    rows = []
    for i, t in enumerate(chk.taken):
        rows.append((str(i + 1), t.parcel.number or "ไม่ทราบ", f"{t.parcel.area:,.1f}", f"{t.area:,.1f}",
                     rai_ngan_wa(t.area), f"{100 * t.share:.1f}",
                     f"{A.format_station(t.s0, 0)}–{A.format_station(t.s1, 0)}"))
    per = 26
    y = D.table(sh, tx, y - 2, cols, rows[:per] or [("-",) + ("",) * 6], 1.9, 4.8, 6.0)
    zone, datum = int(info.get("zone") or 47), str(info.get("datum") or "WGS84")
    sh.text((tx, y - 6), f"พิกัดจุดสำคัญของแนวถนน (UTM {datum} โซน {zone}N)", 2.2, "left", "text", True)
    D.table(sh, tx, y - 8, [("จุด", 22, "center"), ("กม.", 26, "center"), ("E (ม.)", 40, "right"),
                            ("N (ม.)", 42, "right")],
            [(lab, A.format_station(s_, 2), f"{p.x:,.3f}", f"{p.y:,.3f}") for lab, s_, p in keypts[:8]],
            1.9, 4.8, 6.0)
    if len(rows) > per:
        sh.text((tx, Y0 + 30), f"… อีก {len(rows) - per} แปลง (ดูไฟล์ Excel/CSV)", 1.9, "left", "dim")
    sh.text((tx, Y0 + 22), "หมายเหตุ: ตรวจสอบจากข้อมูลแปลงที่ดินในไฟล์ "
            + (info.get("source") or "") + " เพื่อการวางแผนเบื้องต้น", 1.9)
    sh.text((tx, Y0 + 18), "ไม่ใช่การรังวัดของกรมที่ดิน · ก่อนก่อสร้างต้องตรวจสอบหลักฐานและรังวัดแนวเขตจริง", 1.9)
    # จ37: the owner's permission, bottom right
    sh.text((X1 - 1, Y0 + 3), PERMISSION, 2.4, "right", "text", True)
    return sh


def _centroid(ring):
    a = _area(ring)
    if abs(a) < 1e-9:
        return (sum(p[0] for p in ring) / len(ring), sum(p[1] for p in ring) / len(ring))
    cx = cy = 0.0
    for p, q in zip(ring, ring[1:] + ring[:1]):
        f = p[0] * q[1] - q[0] * p[1]
        cx += (p[0] + q[0]) * f
        cy += (p[1] + q[1]) * f
    return (cx / (6 * a), cy / (6 * a))


def write_csv(chk: Check, path: str) -> None:
    from core.road import alignment as A
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["ที่", "เลขที่ดิน", "พื้นที่แปลง (ตร.ม.)", "เข้าไป (ตร.ม.)", "ไร่-งาน-ตร.ว.",
                    "% ของแปลง", "จาก กม.", "ถึง กม.", "หมายเหตุ"])
        for i, t in enumerate(chk.taken, 1):
            w.writerow([i, t.parcel.number or "ไม่ทราบ", f"{t.parcel.area:.2f}", f"{t.area:.2f}",
                        rai_ngan_wa(t.area), f"{100 * t.share:.2f}", A.format_station(t.s0, 2),
                        A.format_station(t.s1, 2), t.parcel.note])
