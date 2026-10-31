# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
"""The building model as a 2D drawing set (แบบก่อสร้าง), sheet by sheet.

Laid out like the standard house drawings of the Department of Public
Works and Town & Country Planning that the user studied: A3 landscape
sheets at 1:100 with a title column on the right (project, sign-off boxes
for architect and engineers, sheet title, scale, date, drawing number and
sheet code), and the same sheet families:

* **A** — สถาปัตยกรรม: index and notes, site plan, floor plans, roof plan,
  elevations, sections, door/window and finish schedules, enlarged
  bathroom plans;
* **S** — โครงสร้าง: notes, foundation plan, beam/slab plans per level,
  roof framing plan, footing/column/beam/slab schedules;
* **SN** — สุขาภิบาล: notes and symbols, sanitary plans;
* **EE** — ไฟฟ้า: notes, symbols and load schedule, lighting/power plans;
* **M** — เครื่องกล: notes, ventilation/air-conditioning plan.

Everything is drawn from the building data (:func:`core.wanic_building
.elements`), not from the 3D mesh, so plans, elevations and sections agree
with the BOQ.  The output is a list of :class:`Sheet` — vector items in
paper millimetres (y up) — that :func:`dxf_bytes` writes as DXF and the
panel prints to PDF.

Pure Python: no Qt.
"""
from __future__ import annotations

import datetime
import math

from core import wanic_building as B
from core import wanic_catalog as CAT
from core.wanic_sign import FULL, NAME, ROLE

#: A3 landscape, millimetres.
PAPER = (420.0, 297.0)
MARGIN = 10.0
TB_W = 62.0                       # title column width
SCALES = (50, 75, 100, 125, 150, 200, 250, 300)
PLAN_SCALES = (100, 125, 150, 200, 250, 300)    # plans: 1:100 as standard

LAYERS = {
    "frame": 7, "title": 7, "wall": 7, "cut": 7, "column": 7, "grid": 1,
    "dim": 3, "text": 7, "door": 4, "window": 4, "fixture": 6, "roof": 5,
    "struct": 2, "rebar": 1, "hidden": 8, "pipe": 4, "elec": 6, "hatch": 8,
    "mech": 5,
    # the site map (road set): road yellow, PI cyan, start/end red, labels white
    "sat": 2, "satpi": 4, "satred": 1, "sattext": 7, "satgrid": 8, "halo": 8, "photo": 8,
}


# ---------------------------------------------------------------------------
# Sheet and primitives
# ---------------------------------------------------------------------------

class Sheet:
    """One drawing sheet: vector items in paper mm (origin lower left)."""

    def __init__(self, code: str, title: str, scale: str = "-",
                 group: str = "A"):
        self.code, self.title, self.scale, self.group = code, title, scale, \
            group
        self.items: list = []
        self.number = 0
        self.colors: dict = {}           # layer → (r, g, b) for the PDF pen

    # primitives — every one carries its layer and line weight (mm)
    def line(self, a, b, layer="wall", w=0.25, dash=False):
        self.items.append(("line", (a[0], a[1], b[0], b[1]), layer, w, dash))

    def poly(self, pts, layer="wall", w=0.25, closed=True, dash=False):
        if len(pts) >= 2:
            self.items.append(("poly", [tuple(p) for p in pts], layer, w,
                               closed, dash))

    def rect(self, x0, y0, x1, y1, layer="frame", w=0.25, dash=False):
        self.poly([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], layer, w, True,
                  dash)

    def fill(self, pts, layer="hatch", gray=0.6, rgb=None):
        """A filled polygon: grey level, or ``rgb`` (0–255) in the PDF."""
        it = ("fill", [tuple(p) for p in pts], layer, gray)
        self.items.append(it + (tuple(rgb),) if rgb else it)

    def image(self, box, data: bytes, layer="image"):
        """A picture (PNG/JPEG bytes) stretched over ``box`` (x0, y0, x1, y1)
        -- printed in the PDF under everything else; a DXF keeps only the
        lines drawn over it."""
        self.items.append(("image", tuple(box), layer, data))

    def circle(self, c, r, layer="grid", w=0.25):
        self.items.append(("circle", (c[0], c[1], r), layer, w))

    def arc(self, c, r, a0, a1, layer="door", w=0.18):
        """Arc from angle a0 to a1 (degrees, counter-clockwise)."""
        self.items.append(("arc", (c[0], c[1], r, a0, a1), layer, w))

    def text(self, p, s, h=2.5, align="left", layer="text", bold=False,
             angle=0.0):
        """``align``: left / center / right, at the baseline (y)."""
        if s is None or str(s) == "":
            return
        self.items.append(("text", (p[0], p[1]), str(s), h, align, layer,
                           bold, angle))

    def count(self, kind=None, layer=None) -> int:
        return sum(1 for it in self.items
                   if (kind is None or it[0] == kind) and
                   (layer is None or it[2 if it[0] != "text" else 5] ==
                    layer))

    def texts(self) -> list[str]:
        return [it[2] for it in self.items if it[0] == "text"]


class View:
    """Model metres → paper mm: ``p = origin + (m - m0) / scale * 1000``."""

    def __init__(self, sheet, scale, m0, origin):
        self.sh, self.k = sheet, 1000.0 / scale
        self.m0, self.o = m0, origin

    def __call__(self, x, y):
        return (self.o[0] + (x - self.m0[0]) * self.k,
                self.o[1] + (y - self.m0[1]) * self.k)

    def len(self, v):
        return v * self.k


def fit_scale(extent_m, box_mm, choices=SCALES) -> int:
    """The largest standard scale whose drawing of ``extent_m`` (w, h in
    metres) fits ``box_mm``."""
    w, h = max(extent_m[0], 1e-6), max(extent_m[1], 1e-6)
    for s in choices:
        if w * 1000 / s <= box_mm[0] and h * 1000 / s <= box_mm[1]:
            return s
    return choices[-1]


# ---------------------------------------------------------------------------
# Title block (the right-hand column)
# ---------------------------------------------------------------------------

#: Sign-off boxes down the column, as on the standard drawings.
SIGN_ROLES = [("สถาปัตยกรรม", "", "สถาปนิก"),
              ("วิศวกรรม", "โครงสร้าง", "วิศวกร"),
              ("วิศวกรรม", "สุขาภิบาล", "วิศวกร"),
              ("วิศวกรรม", "ไฟฟ้า", "วิศวกร"),
              ("วิศวกรรม", "เครื่องกล", "วิศวกร")]


def frame(sh: Sheet, info: dict, total: int, roles=None):
    """The title column; ``roles`` replaces the sign-off boxes
    (``[(line1, line2, title)]``)."""
    W, H = PAPER
    m = MARGIN
    sh.rect(m, m, W - m, H - m, "frame", 0.5)
    x0, x1 = W - m - TB_W, W - m
    sh.line((x0, m), (x0, H - m), "frame", 0.5)
    cx = (x0 + x1) / 2
    y = H - m

    def band(hgt, w=0.25):
        nonlocal y
        y -= hgt
        sh.line((x0, y), (x1, y), "title", w)
        return y

    # Project block (no government emblem: the owner's own drawing).
    band(30)
    sh.text((cx, y + 22), info.get("office") or "WANICNSURVEY", 3.2,
            "center", "title", True)
    sh.text((cx, y + 15), "แบบก่อสร้าง", 3.0, "center", "title")
    sh.text((cx, y + 8), info.get("owner") or "", 2.4, "center", "title")
    band(18)
    sh.text((x0 + 2, y + 14), "โครงการ", 2.0, "left", "title")
    proj = info.get("project") or "อาคาร"
    for i, line in enumerate(_wrap(proj, 26)[:2]):
        sh.text((cx, y + 9 - i * 4.5), line, 3.0, "center", "title", True)
    band(9)
    sh.text((x0 + 2, y + 5.5), "สถานที่", 2.0, "left", "title")
    sh.text((x0 + 14, y + 5.5), (info.get("location") or "")[:30], 2.2,
            "left", "title")
    for l1, l2, who in (roles or SIGN_ROLES):
        band(11)
        sh.line((x0 + 22, y), (x0 + 22, y + 11), "title", 0.18)
        sh.text((x0 + 2, y + 7), l1, 2.0, "left", "title")
        # a long second line (โครงสร้าง/ระบายน้ำ) is set smaller to stay in its cell
        sh.text((x0 + 2, y + 2.8), l2, 2.0 if len(l2) <= 12 else 1.6, "left", "title")
        sh.text((x1 - 2, y + 1.5), who, 1.8, "right", "title")
        name = (info.get("signers") or {}).get(l1 + l2, "")
        if name:
            sh.text((x0 + 24, y + 5), name, 2.0, "left", "title")
    # The program's signature (every development carries it).
    band(16, 0.35)
    # room to sign above the name (the label is left out on purpose)
    sh.line((cx - 20, y + 10), (cx + 20, y + 10), "title", 0.13, True)
    sh.text((cx, y + 6.5), f"({NAME})", 2.4, "center", "title", True)
    sh.text((cx, y + 2.5), ROLE, 2.0, "center", "title")
    band(14)
    sh.text((x0 + 2, y + 10.5), "แสดงแบบ", 2.0, "left", "title")
    for i, line in enumerate(_wrap(sh.title, 24)[:2]):
        sh.text((cx, y + 6 - i * 4), line, 2.8, "center", "title", True)
    band(7)
    sh.text((x0 + 2, y + 2.2), "มาตราส่วน", 2.0, "left", "title")
    sh.text((x0 + 26, y + 2.2), sh.scale, 2.2, "left", "title")
    band(7)
    sh.text((x0 + 2, y + 2.2), "วัน/เดือน/ปี", 2.0, "left", "title")
    sh.text((x0 + 26, y + 2.2), info.get("date") or thai_date(), 2.2, "left",
            "title")
    band(7)
    sh.text((x0 + 2, y + 2.2), "เลขที่แบบ", 2.0, "left", "title")
    sh.text((x0 + 26, y + 2.2), info.get("drawing_no") or "-", 2.2, "left",
            "title")
    # Sheet code | number / total
    sh.line((x0 + TB_W * 0.58, m), (x0 + TB_W * 0.58, y), "title", 0.35)
    mid = (y + m) / 2
    sh.text((x0 + TB_W * 0.29, mid - 2.5), sh.code, 6.0, "center", "title",
            True)
    sh.text((x0 + TB_W * 0.79, mid + 0.5), str(sh.number), 5.0, "center",
            "title", True)
    sh.text((x0 + TB_W * 0.79, mid - 5.5), f"/ {total}", 2.4, "center",
            "title")
    # footer
    sh.text((m + 1, m - 4.5), f"จัดทำด้วย WANICNSURVEY · {FULL}", 1.8,
            "left", "title")
    sh.text((x0 - 2, m - 4.5), "A3  " + sh.scale, 1.8, "right", "title")


def thai_date(d=None) -> str:
    d = d or datetime.date.today()
    months = ["ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.", "ก.ค.",
              "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค."]
    return f"{d.day} {months[d.month - 1]} {d.year + 543}"


_MARKS = set(chr(c) for c in list(range(0x0E31, 0x0E32)) +
             list(range(0x0E33, 0x0E3B)) + list(range(0x0E47, 0x0E4F)))
_LEAD = set("เแโใไ")


def _cut_at(word: str, i: int) -> int:
    """A syllable-safe split index ≤ i (never before a vowel/tone mark nor
    after a leading vowel)."""
    i = min(i, len(word))
    while 1 < i < len(word) and (word[i] in _MARKS or word[i - 1] in _LEAD
                                 or word[i] in "ะา"):
        i -= 1
    return max(i, 1)


def _wrap(text: str, n: int) -> list[str]:
    """Wrap Thai/latin text near ``n`` characters: at spaces, and inside
    long Thai runs (no spaces between words) at syllable-safe points."""
    out, cur = [], ""
    for w in str(text).split(" "):
        while w:
            room = n - len(cur) - (1 if cur else 0)
            if len(w) <= room:
                cur = f"{cur} {w}" if cur else w
                w = ""
            elif len(w) <= n and cur:
                out.append(cur)
                cur = ""
            else:
                take = room if room >= 6 else n
                if take == n and cur:
                    out.append(cur)
                    cur = ""
                i = _cut_at(w, take)
                if 0 < len(w) - i < 4:                  # no 1–3 letter tail
                    i = _cut_at(w, max(len(w) - 4, 1))
                piece, w = w[:i], w[i:]
                cur = f"{cur} {piece}" if cur else piece
                out.append(cur)
                cur = ""
    if cur:
        out.append(cur)
    return out or [""]


def drawing_area():
    """The free drawing area (x0, y0, x1, y1) in mm."""
    return (MARGIN + 5, MARGIN + 5, PAPER[0] - MARGIN - TB_W - 5,
            PAPER[1] - MARGIN - 5)


def caption(sh, p, title, scale_txt):
    """``แปลนพื้นชั้น 1`` underlined with ``มาตราส่วน 1:100`` below."""
    sh.text(p, title, 4.0, "center", "text", True)
    w = len(title) * 2.0 + 10
    sh.line((p[0] - w / 2, p[1] - 1.2), (p[0] + w / 2, p[1] - 1.2), "text",
            0.5)
    sh.text((p[0], p[1] - 6), f"มาตราส่วน {scale_txt}", 2.6, "center")


def notes_block(sh, x, y, title, lines, h=2.4, width=60):
    """A numbered/plain notes column; returns the y below it."""
    sh.text((x, y), title, 3.4, "left", "text", True)
    sh.line((x, y - 1.2), (x + len(title) * 1.9 + 4, y - 1.2), "text", 0.35)
    y -= 6
    for ln in lines:
        for part in _wrap(ln, width):
            sh.text((x, y), part, h)
            y -= h * 1.65
        y -= h * 0.3
    return y


def table(sh, x, y, cols, rows, h=2.3, row_h=6.0, head_h=7.0):
    """A ruled table; ``cols`` = [(header, width_mm, align)]. Returns the y
    below it."""
    W = sum(c[1] for c in cols)
    y0 = y
    if head_h > 0:                       # 0: rows only (a total under a table)
        sh.rect(x, y - head_h, x + W, y, "text", 0.35)
        cx = x
        for head, w, _al in cols:
            sh.text((cx + w / 2, y - head_h + 2.3), head, h, "center", "text",
                    True)
            cx += w
        y -= head_h
    else:
        sh.line((x, y), (x + W, y), "text", 0.35)
    for row in rows:
        sh.line((x, y - row_h), (x + W, y - row_h), "text", 0.18)
        cx = x
        for (head, w, al), val in zip(cols, row):
            tx = cx + 1.5 if al == "left" else cx + w - 1.5 if al == "right" \
                else cx + w / 2
            sh.text((tx, y - row_h + 1.9), val, h, al)
            cx += w
        y -= row_h
    cx = x
    for _head, w, _al in cols:
        sh.line((cx, y0), (cx, y), "text", 0.18)
        cx += w
    sh.line((cx, y0), (cx, y), "text", 0.18)
    sh.line((x, y), (x + W, y), "text", 0.35)
    return y


# ---------------------------------------------------------------------------
# Model helpers
# ---------------------------------------------------------------------------

def axis_name(i: int) -> str:
    letters = "ABCDEFGHJKLMNPQRSTUVWXYZ"
    return letters[i] if i < len(letters) else f"A{i - len(letters) + 1}"


def grids(E):
    xs = sorted({round(c["x"], 3) for c in E["footings"]})
    ys = sorted({round(c["y"], 3) for c in E["footings"]})
    return xs, ys


def bbox(E, pad=0.0):
    xs, ys = grids(E)
    if not xs:
        return (0, 0, 1, 1)
    return (xs[0] - pad, ys[0] - pad, xs[-1] + pad, ys[-1] + pad)


def outward(wall, rooms):
    """Unit normal of a wall pointing away from its room (exterior walls)."""
    (x0, y0), (x1, y1) = wall["p0"], wall["p1"]
    L = math.hypot(x1 - x0, y1 - y0) or 1.0
    nx, ny = (y1 - y0) / L, -(x1 - x0) / L
    mx, my = (x0 + x1) / 2, (y0 + y1) / 2
    for rm in rooms:
        px, py = mx + nx * 0.05, my + ny * 0.05
        if rm["x"] - 1e-6 <= px <= rm["x"] + rm["w"] + 1e-6 and \
                rm["y"] - 1e-6 <= py <= rm["y"] + rm["d"] + 1e-6:
            return (-nx, -ny)
    return (nx, ny)


def opening_codes(E) -> dict:
    """``{(style, w, h, sill): "ป1" / "น1" …}`` numbered like the standard
    drawings (doors ป, windows น)."""
    seen: dict = {}
    nd = nw = 0
    for o in sorted(E["openings"], key=lambda o: (o["type"] != "door",
                                                  o["op"].get("style") or "",
                                                  -o["w"], -o["h"])):
        key = (o["op"].get("style") or "", round(o["w"], 2), round(o["h"], 2),
               round(o["sill"], 2))
        if key in seen:
            continue
        if o["type"] == "door":
            nd += 1
            seen[key] = f"ป{nd}"
        else:
            nw += 1
            seen[key] = f"น{nw}"
    return seen


def op_code(o, codes) -> str:
    return codes.get((o["op"].get("style") or "", round(o["w"], 2),
                      round(o["h"], 2), round(o["sill"], 2)), "")


def finish_codes(E):
    """Floor finishes as พ1, พ2 … with their description."""
    from core import wanic_recipes2569 as RC
    codes: dict = {}
    for sl in E["slabs"]:
        f = CAT.finish_of(sl["room"])
        c = f["floor"]
        if c and c not in codes:
            rc = RC.find(c)
            codes[c] = (f"พ{len(codes) + 1}",
                        (rc["name"] if rc else c)[:80])
    return codes


def opening_on_wall(E, k):
    """[(wall, s, opening-element)] for floor ``k`` — where each opening
    sits along its wall."""
    out = []
    ops = [o for o in E["openings"] if o["floor"] == k]
    for w in (w for w in E["walls"] if w["floor"] == k):
        for op in w["openings"]:
            el = next((o for o in ops if o["op"] is op), None)
            if el is None:
                continue
            (x0, y0) = w["p0"]
            s = math.hypot(float(op["x"]) - x0, float(op["y"]) - y0)
            out.append((w, s, el))
    return out


# ---------------------------------------------------------------------------
# Plan drawing (shared by A, S, SN, EE, M plans)
# ---------------------------------------------------------------------------

def draw_grid(sh, v, E, dims=True, bubbles=True):
    xs, ys = grids(E)
    if not xs:
        return
    x0, y0, x1, y1 = xs[0], ys[0], xs[-1], ys[-1]
    ext = 2.2
    for i, x in enumerate(xs):
        sh.line(v(x, y0 - ext), v(x, y1 + ext), "grid", 0.13, True)
        if bubbles:
            c = v(x, y1 + ext)
            sh.circle((c[0], c[1] + 3.5), 3.5, "grid", 0.25)
            sh.text((c[0], c[1] + 2.4), str(i + 1), 3.0, "center", "grid")
    for j, y in enumerate(ys):
        sh.line(v(x0 - ext, y), v(x1 + ext, y), "grid", 0.13, True)
        if bubbles:
            c = v(x0 - ext, y)
            sh.circle((c[0] - 3.5, c[1]), 3.5, "grid", 0.25)
            sh.text((c[0] - 3.5, c[1] - 1.1), axis_name(j), 3.0, "center",
                    "grid")
    if dims:
        dim_chain(sh, v, xs, y1 + 0.8, "x")
        dim_chain(sh, v, [xs[0], xs[-1]], y1 + 1.4, "x")
        dim_chain(sh, v, ys, x0 - 0.8, "y")
        dim_chain(sh, v, [ys[0], ys[-1]], x0 - 1.4, "y")


def dim_chain(sh, v, vals, at, axis):
    """A chain of dimensions along x (at model y) or y (at model x)."""
    if len(vals) < 2:
        return
    for a, b in zip(vals, vals[1:]):
        if axis == "x":
            p, q = v(a, at), v(b, at)
            sh.line(p, q, "dim", 0.13)
            for t in (p, q):
                sh.line((t[0] - 0.8, t[1] - 0.8), (t[0] + 0.8, t[1] + 0.8),
                        "dim", 0.25)
                sh.line((t[0], t[1] - 1.2), (t[0], t[1] + 1.2), "dim", 0.13)
            sh.text(((p[0] + q[0]) / 2, p[1] + 0.9), f"{b - a:.2f}", 2.2,
                    "center", "dim")
        else:
            p, q = v(at, a), v(at, b)
            sh.line(p, q, "dim", 0.13)
            for t in (p, q):
                sh.line((t[0] - 0.8, t[1] - 0.8), (t[0] + 0.8, t[1] + 0.8),
                        "dim", 0.25)
                sh.line((t[0] - 1.2, t[1]), (t[0] + 1.2, t[1]), "dim", 0.13)
            sh.text((p[0] - 0.9, (p[1] + q[1]) / 2), f"{b - a:.2f}", 2.2,
                    "center", "dim", angle=90)


def draw_walls(sh, v, E, k, t, codes=None, swings=True, tags=True):
    """Walls of floor ``k`` as two lines ``t`` thick, broken at openings,
    with door swings and window sashes."""
    walls = [w for w in E["walls"] if w["floor"] == k]
    rooms = E["floors"][k]["rooms"]
    lib, s = E["lib"], E["settings"]
    placed = opening_on_wall(E, k)
    for w in walls:
        (x0, y0), (x1, y1) = w["p0"], w["p1"]
        L = w["L"]
        if L < 1e-6:
            continue
        ux, uy = (x1 - x0) / L, (y1 - y0) / L
        nx, ny = -uy, ux
        cuts = sorted((s_ - el["w"] / 2, s_ + el["w"] / 2, el)
                      for ww, s_, el in placed if ww is w)
        spans, a = [], 0.0
        for c0, c1, _el in cuts:
            spans.append((a, max(a, c0)))
            a = max(a, c1)
        spans.append((a, L))
        for a, b in spans:
            if b - a < 1e-6:
                continue
            for sgn in (-1, 1):
                p = (x0 + ux * a + nx * t / 2 * sgn, y0 + uy * a + ny * t / 2 * sgn)
                q = (x0 + ux * b + nx * t / 2 * sgn, y0 + uy * b + ny * t / 2 * sgn)
                sh.line(v(*p), v(*q), "wall", 0.5 if w["exterior"] else 0.35)
        for c0, c1, el in cuts:
            # jambs
            for c in (c0, c1):
                p = (x0 + ux * c + nx * t / 2, y0 + uy * c + ny * t / 2)
                q = (x0 + ux * c - nx * t / 2, y0 + uy * c - ny * t / 2)
                sh.line(v(*p), v(*q), "wall", 0.35)
            if el["type"] == "door":
                if swings:
                    _door(sh, v, (x0, y0), (ux, uy), (nx, ny), c0, c1, t, el,
                          w, rooms)
            else:
                for off in (-t / 2, 0.0, t / 2):
                    p = (x0 + ux * c0 + nx * off, y0 + uy * c0 + ny * off)
                    q = (x0 + ux * c1 + nx * off, y0 + uy * c1 + ny * off)
                    sh.line(v(*p), v(*q), "window", 0.18)
            if tags and codes is not None:
                cm = (c0 + c1) / 2
                no = outward(w, rooms) if w["exterior"] else (-nx, -ny)
                d = t / 2 + 0.45
                if not w["exterior"]:
                    cm = c1 + 0.25
                tp = v(x0 + ux * cm + no[0] * d, y0 + uy * cm + no[1] * d)
                code = op_code(el, codes)
                if el["type"] == "door":
                    sh.text((tp[0], tp[1] - 1.1), code, 2.4, "center", "door")
                else:
                    sh.circle(tp, 2.6, "window", 0.18)
                    sh.text((tp[0], tp[1] - 1.0), code, 2.2, "center",
                            "window")
    # columns
    cs = float(lib.get("C1", {}).get("b", 0.2))
    for c in (c for c in E["columns"] if c["floor"] == k):
        b = float(lib.get(c["mark"], {}).get("b", cs))
        h = float(lib.get(c["mark"], {}).get("h", b))
        pts = [v(c["x"] - b / 2, c["y"] - h / 2), v(c["x"] + b / 2, c["y"] - h / 2),
               v(c["x"] + b / 2, c["y"] + h / 2), v(c["x"] - b / 2, c["y"] + h / 2)]
        sh.fill(pts, "column", 0.15)
        sh.poly(pts, "column", 0.35)
    _ = s


def _door(sh, v, p0, u, n, c0, c1, t, el, wall, rooms):
    """Leaf line and 90° swing into the room on the hinge side."""
    spec = CAT.OPENING_TYPES.get(el["op"].get("style") or "D1",
                                 CAT.OPENING_TYPES["D1"])
    side = outward(wall, rooms) if wall["exterior"] else n
    inn = (-side[0], -side[1])
    leaves = max(1, int(spec.get("leaves") or 1))
    if spec.get("slide"):
        for off, (a, b) in ((t * 0.15, (c0, (c0 + c1) / 2 + 0.05)),
                            (-t * 0.15, ((c0 + c1) / 2 - 0.05, c1))):
            p = (p0[0] + u[0] * a + n[0] * off, p0[1] + u[1] * a + n[1] * off)
            q = (p0[0] + u[0] * b + n[0] * off, p0[1] + u[1] * b + n[1] * off)
            sh.line(v(*p), v(*q), "door", 0.35)
        return
    hinges = [(c0, 1)] if leaves == 1 else [(c0, 1), (c1, -1)]
    leaf = (c1 - c0) / len(hinges)
    for hs, sgn in hinges:
        hp = (p0[0] + u[0] * hs + inn[0] * t / 2, p0[1] + u[1] * hs + inn[1] * t / 2)
        tip = (hp[0] + inn[0] * leaf, hp[1] + inn[1] * leaf)
        sh.line(v(*hp), v(*tip), "door", 0.35)
        a_open = math.degrees(math.atan2(inn[1], inn[0]))
        a_shut = math.degrees(math.atan2(u[1] * sgn, u[0] * sgn))
        a0, a1 = sorted((a_open, a_shut))
        if a1 - a0 > 180:
            a0, a1 = a1, a0 + 360
        sh.arc(v(*hp), v.len(leaf), a0, a1, "door", 0.13)


def draw_rooms(sh, v, E, k, fcodes=None, area=True):
    for sl in (s for s in E["slabs"] if s["floor"] == k):
        rm = sl["room"]
        cx, cy = rm["x"] + rm["w"] / 2, rm["y"] + rm["d"] / 2
        p = v(cx, cy)
        sh.text((p[0], p[1] + 1.5), rm.get("name") or "ห้อง", 2.8, "center",
                "text", True)
        if area:
            sh.text((p[0], p[1] - 2.5), f"{rm['w'] * rm['d']:.2f} ตร.ม.", 2.0,
                    "center")
        if fcodes:
            f = CAT.finish_of(rm)
            fc = fcodes.get(f["floor"], ("", ""))[0]
            lv = f"±{sl['z']:.2f}" if sl["z"] == 0 else f"+{sl['z']:.2f}"
            tag = f"{fc}  {'ฝ1' if f['ceiling'] else ''}  {lv}".strip()
            sh.text((p[0], p[1] - 6.0), tag, 2.0, "center")


def draw_stairs(sh, v, E, k):
    s = E["settings"]
    for st in (x for x in E["stairs"] if x["floor"] == k):
        pts = B.stair_rect(st["st"], s)
        sh.poly([v(*p) for p in pts], "wall", 0.25)
        n, L, _H = B.stair_geometry(st["st"], s)
        a, b, c, d = pts
        for i in range(1, n):
            f = i / n
            p = (a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f)
            q = (d[0] + (c[0] - d[0]) * f, d[1] + (c[1] - d[1]) * f)
            sh.line(v(*p), v(*q), "wall", 0.13)
        m0 = ((a[0] + d[0]) / 2, (a[1] + d[1]) / 2)
        m1 = ((b[0] + c[0]) / 2, (b[1] + c[1]) / 2)
        sh.line(v(*m0), v(*m1), "dim", 0.18)
        e = v(*m1)
        sh.text((e[0], e[1] + 1.2), "ขึ้น", 2.0, "center", "dim")


def fixture_rect(fx):
    spec = CAT.SANITARY.get(fx.get("type"), ("", "", 0, 0.5, 0.5, 0, 0))
    w, d = float(spec[3]), float(spec[4])
    if int(fx.get("dir", 0)) % 2:
        w, d = d, w
    x, y = float(fx["x"]), float(fx["y"])
    return [(x - w / 2, y - d / 2), (x + w / 2, y - d / 2),
            (x + w / 2, y + d / 2), (x - w / 2, y + d / 2)]


def draw_fixtures(sh, v, E, k, labels=True):
    for f in (x for x in E["fixtures"] if x["floor"] == k):
        fx = f["fx"]
        pts = fixture_rect(fx)
        sh.poly([v(*p) for p in pts], "fixture", 0.25)
        t = fx.get("type", "")
        c = v(float(fx["x"]), float(fx["y"]))
        if t.startswith("WC"):
            sh.circle(c, v.len(0.16), "fixture", 0.18)
        elif t in ("LV", "SK1", "SK2"):
            sh.circle(c, v.len(0.12), "fixture", 0.18)
        if labels:
            sh.text((c[0], c[1] - 0.9), t, 1.6, "center", "fixture")


def north(sh, p, r=6):
    sh.circle(p, r, "text", 0.25)
    sh.fill([(p[0], p[1] + r), (p[0] - r * 0.45, p[1] - r * 0.6),
             (p[0], p[1] - r * 0.25)], "text", 0.0)
    sh.poly([(p[0], p[1] + r), (p[0] + r * 0.45, p[1] - r * 0.6),
             (p[0], p[1] - r * 0.25)], "text", 0.25)
    sh.text((p[0], p[1] + r + 1.5), "N", 3.0, "center", "text", True)


def plan_view(sh, E, box=None, pad=3.4, scale=None):
    """A View fitting the building (with grid bubbles) into ``box``."""
    x0, y0, x1, y1 = box or drawing_area()
    bx = bbox(E, pad)
    room = (x1 - x0, y1 - y0 - 14)
    sc = scale or fit_scale((bx[2] - bx[0], bx[3] - bx[1]), room,
                            PLAN_SCALES)
    sh.scale = f"1:{sc}"
    k = 1000.0 / sc
    w, h = (bx[2] - bx[0]) * k, (bx[3] - bx[1]) * k
    ox = x0 + (x1 - x0 - w) / 2
    oy = y0 + 14 + (y1 - y0 - 14 - h) / 2
    return View(sh, sc, (bx[0], bx[1]), (ox, oy)), sc


# ---------------------------------------------------------------------------
# A — architecture
# ---------------------------------------------------------------------------

A_NOTES = [
    "1. ขนาดในแบบเป็นเมตร ยกเว้นระบุเป็นอย่างอื่น ระยะทั้งหมดให้ตรวจสอบที่หน้างานก่อนก่อสร้าง",
    "2. ระดับ ±0.00 คือระดับพื้นชั้นล่างสำเร็จ ระดับดินเดิมให้ตรวจสอบที่หน้างาน",
    "3. ผนังก่ออิฐมอญครึ่งแผ่น ฉาบปูนเรียบทั้งสองด้าน มีเสาเอ็นและคานทับหลัง ค.ส.ล. 0.10 ม. รอบช่องเปิดและทุกระยะไม่เกิน 3.00 ม.",
    "4. วัสดุพื้น ผนัง ฝ้า ตามตารางวัสดุตกแต่ง (พ/ฝ) และสัญลักษณ์ในแปลน",
    "5. ประตู-หน้าต่าง ตามตารางประตู-หน้าต่าง (ป/น) ขนาดเป็นขนาดช่องเปิด",
    "6. งานโครงสร้าง สุขาภิบาล ไฟฟ้า ให้ดูแบบหมวด S, SN, EE ประกอบ",
    "7. วัสดุและการก่อสร้างให้เป็นไปตามมาตรฐาน มยผ. และ มอก. ที่เกี่ยวข้อง",
    "8. ห้ามวัดขนาดจากแบบ หากแบบขัดแย้งกันให้แจ้งผู้ออกแบบก่อนดำเนินการ",
]
SYMBOLS = [("ป1", "รหัสประตู"), ("น1", "รหัสหน้าต่าง"), ("พ1", "วัสดุพื้น"),
           ("ฝ1", "ฝ้าเพดาน"), ("±0.00", "ระดับพื้น"), ("grid", "แนวเสา (กริด)")]


def sheet_index(sheets, group, sh, x, y, w=190):
    rows = [(s.code, s.title, str(s.number)) for s in sheets
            if s.group == group]
    return table(sh, x, y, [("แผ่นที่", 24, "center"), ("รายการแบบ", w - 44,
                                                        "left"),
                            ("หน้า", 20, "center")], rows)


def a_index(sh, sheets, info):
    x0, y0, x1, y1 = drawing_area()
    sh.text((x0 + 95, y1 - 6), "สารบัญแบบสถาปัตยกรรม", 4.0, "center", "text",
            True)
    sheet_index(sheets, "A", sh, x0, y1 - 12, 190)
    y = notes_block(sh, x0 + 200, y1 - 6, "รายการประกอบแบบงานสถาปัตยกรรม",
                    A_NOTES, 2.3, 58)
    y = notes_block(sh, x0 + 200, y - 4, "ข้อมูลอาคาร",
                    info.get("summary") or [], 2.3, 58)
    sh.text((x0 + 200, y - 4), "สัญลักษณ์", 3.4, "left", "text", True)
    yy = y - 10
    for sym, desc in SYMBOLS:
        if sym == "grid":
            sh.circle((x0 + 207, yy + 1), 2.6, "grid", 0.25)
            sh.text((x0 + 207, yy), "1", 2.4, "center", "grid")
        else:
            sh.text((x0 + 204, yy), sym, 2.6, "left", "text", True)
        sh.text((x0 + 222, yy), desc, 2.3)
        yy -= 6


def a_site(sh, E, info):
    x0, y0, x1, y1 = drawing_area()
    bx = bbox(E)
    set_back = float(info.get("setback") or 3.0)
    lot = (bx[0] - set_back, bx[1] - set_back - 2.0, bx[2] + set_back,
           bx[3] + set_back)
    sc = fit_scale((lot[2] - lot[0] + 4, lot[3] - lot[1] + 4),
                   (x1 - x0 - 100, y1 - y0 - 20), (100, 150, 200, 250, 300,
                                                   400, 500))
    sh.scale = f"1:{sc}"
    k = 1000.0 / sc
    w, h = (lot[2] - lot[0]) * k, (lot[3] - lot[1]) * k
    v = View(sh, sc, (lot[0], lot[1]), (x0 + 10 + (x1 - x0 - 110 - w) / 2,
                                        y0 + 20 + (y1 - y0 - 30 - h) / 2))
    sh.poly([v(lot[0], lot[1]), v(lot[2], lot[1]), v(lot[2], lot[3]),
             v(lot[0], lot[3])], "grid", 0.35, True, True)
    for rm in (r for f in E["floors"][:1] for r in f["rooms"]):
        pts = B.room_corners(rm)
        sh.fill([v(*p) for p in pts], "hatch", 0.85)
        sh.poly([v(*p) for p in pts], "wall", 0.5)
    rl = info.get("roof_rects") or []
    ov = float(E["settings"].get("overhang") or 0)
    for r in rl:
        sh.poly([v(r[0] - ov, r[1] - ov), v(r[2] + ov, r[1] - ov),
                 v(r[2] + ov, r[3] + ov), v(r[0] - ov, r[3] + ov)], "roof",
                0.18, True, True)
    dim_chain(sh, v, [lot[0], bx[0]], bx[1] + (bx[3] - bx[1]) / 2, "x")
    dim_chain(sh, v, [bx[2], lot[2]], bx[1] + (bx[3] - bx[1]) / 2, "x")
    dim_chain(sh, v, [lot[1], bx[1]], bx[0] + (bx[2] - bx[0]) / 2, "y")
    dim_chain(sh, v, [bx[3], lot[3]], bx[0] + (bx[2] - bx[0]) / 2, "y")
    c = v((bx[0] + bx[2]) / 2, (bx[1] + bx[3]) / 2)
    sh.text(c, "อาคาร", 3.0, "center", "text", True)
    sh.text(v((lot[0] + lot[2]) / 2, lot[1] + 0.6), "ทางเข้า / ถนนสาธารณะ", 2.6,
            "center")
    north(sh, (x1 - 110, y1 - 15))
    caption(sh, ((x0 + x1 - 100) / 2, y0 + 8), "ผังบริเวณ", f"1:{sc}")
    notes_block(sh, x1 - 95, y1 - 6, "หลักเกณฑ์ผังบริเวณประกอบการขออนุญาต", [
        "1. แนวเขตที่ดินในแบบเป็นแนวสมมติ ให้ปรับตามโฉนด/หนังสือรับรองจริง",
        "2. ผนังที่มีช่องเปิด ประตู หน้าต่าง ช่องระบายอากาศ ระเบียง ต้องห่างแนวเขตที่ดิน"
        "ไม่น้อยกว่า 2.00 ม. (อาคารสูงไม่เกิน 9.00 ม.) และ 3.00 ม. (สูงเกิน 9.00 ม. "
        "แต่ไม่ถึง 23.00 ม.)",
        "3. ผนังทึบที่ห่างแนวเขตน้อยกว่าที่กำหนด ต้องได้รับความยินยอมเป็นหนังสือจากเจ้าของที่ดินข้างเคียง",
        "4. ต้องมีที่ว่างไม่น้อยกว่า 30% ของพื้นที่ดิน (อาคารอยู่อาศัย)",
        "5. ระยะร่นจากถนนสาธารณะ ระดับดิน และการระบายน้ำ ให้เป็นไปตามกฎหมายควบคุม"
        "อาคารและข้อบัญญัติท้องถิ่น",
        f"6. ระยะในแบบแสดงระยะร่นสมมติ {set_back:.2f} ม. รอบอาคาร",
    ], 2.2, 50)


def a_floor(sh, E, k, codes, fcodes):
    v, sc = plan_view(sh, E)
    t = float(E["settings"].get("wall_t") or 0.1)
    draw_grid(sh, v, E)
    draw_walls(sh, v, E, k, t, codes)
    draw_rooms(sh, v, E, k, fcodes)
    draw_stairs(sh, v, E, k)
    draw_fixtures(sh, v, E, k)
    x0, y0, x1, y1 = drawing_area()
    north(sh, (x1 - 10, y1 - 12))
    name = "แปลนพื้นชั้น 1" if k == 0 else f"แปลนพื้นชั้น {k + 1}"
    caption(sh, ((x0 + x1) / 2, y0 + 6), name, f"1:{sc}")
    return sc


def a_roof(sh, E, L):
    v, sc = plan_view(sh, E, pad=3.2)
    draw_grid(sh, v, E, dims=True)
    s = E["settings"]
    if L:
        for poly in L["skin"]:
            sh.poly([v(p[0], p[1]) for p in poly], "roof", 0.25)
        for k in ("ridge", "hip"):
            for a, b in L[k]:
                sh.line(v(a[0], a[1]), v(b[0], b[1]), "roof", 0.5)
        for a, b in L.get("eave") or []:
            sh.line(v(a[0], a[1]), v(b[0], b[1]), "roof", 0.5)
        for r in L["rects"]:
            cx, cy = (r[0] + r[2]) / 2, (r[1] + r[3]) / 2
            for dx, dy in ((0, -1), (0, 1)):
                p = v(cx, cy + dy * (r[3] - r[1]) / 4)
                q = (p[0], p[1] + dy * 8)
                sh.line(p, q, "dim", 0.25)
                sh.line(q, (q[0] - 1, q[1] - dy * 2), "dim", 0.25)
                sh.line(q, (q[0] + 1, q[1] - dy * 2), "dim", 0.25)
                sh.text((p[0] + 2, p[1] + dy * 4), f"ลาด {s['pitch']:.0f}°",
                        2.0, "left", "dim")
    _code, tile = CAT.roof_tile(s)
    x0, y0, x1, y1 = drawing_area()
    sh.text((x0, y0 + 20), f"วัสดุมุง: {tile.get('name', '')}", 2.4)
    sh.text((x0, y0 + 15), f"ชายคายื่น {float(s['overhang']):.2f} ม. · "
            f"เชิงชาย/ปั้นลม · ครอบสัน ครอบตะเข้", 2.4)
    north(sh, (x1 - 10, y1 - 12))
    caption(sh, ((x0 + x1) / 2, y0 + 6), "แปลนหลังคา", f"1:{sc}")


def _ext_walls(E, k, n):
    rooms = E["floors"][k]["rooms"]
    return [w for w in E["walls"] if w["floor"] == k and w["exterior"] and
            abs(outward(w, rooms)[0] - n[0]) < 1e-6 and
            abs(outward(w, rooms)[1] - n[1]) < 1e-6]


def elevation(sh, E, L, side, box):
    """Elevation looking at the face whose outward normal is ``side``:
    (0,-1) front/south, (1,0) right, (0,1) back, (-1,0) left."""
    H, n = E["H"], E["n"]
    nx, ny = side
    # horizontal axis along the face, left→right as seen from outside
    ax = (-ny, nx) if (nx, ny) != (0, 0) else (1, 0)
    ax = (-ax[0], -ax[1]) if (nx, ny) in ((0, -1), (1, 0)) else ax
    ax = (1, 0) if side == (0, -1) else (0, 1) if side == (1, 0) else \
        (-1, 0) if side == (0, 1) else (0, -1)

    def u_of(x, y):
        return x * ax[0] + y * ax[1]
    xs, ys = grids(E)
    pts = [(x, y) for x in xs for y in ys] or [(0, 0)]
    us = [u_of(x, y) for x, y in pts]
    ov = float(E["settings"].get("overhang") or 0)
    umin, umax = min(us) - ov - 0.5, max(us) + ov + 0.5
    ztop = n * H + 3.0
    zmin = -0.6
    bw, bh = box[2] - box[0] - 22, box[3] - box[1] - 12
    sc = fit_scale((umax - umin, ztop - zmin), (bw, bh), PLAN_SCALES)
    sh.scale = f"1:{sc}"
    k = 1000.0 / sc
    ox = box[0] + (bw - (umax - umin) * k) / 2
    oy = box[1] + 12

    def P(u, z):
        return (ox + (u - umin) * k, oy + (z - zmin) * k)
    sh.line(P(umin, 0), P(umax, 0), "cut", 0.7)
    # walls of every floor facing this side (outline + openings)
    for f in range(n):
        for w in _ext_walls(E, f, side):
            a, b = sorted((u_of(*w["p0"]), u_of(*w["p1"])))
            z0, z1 = f * H, (f + 1) * H
            sh.rect(*P(a, z0), *P(b, z1), "wall", 0.35)
            for op in w["openings"]:
                el = next((o for o in E["openings"] if o["op"] is op), None)
                if el is None:
                    continue
                uc = u_of(float(op["x"]), float(op["y"]))
                lo, hi = z0 + el["sill"], z0 + el["sill"] + el["h"]
                sh.rect(*P(uc - el["w"] / 2, lo), *P(uc + el["w"] / 2, hi),
                        "window" if el["type"] == "window" else "door", 0.25)
                if el["type"] == "window":
                    sh.line(P(uc, lo), P(uc, hi), "window", 0.13)
                else:
                    sh.line(P(uc + el["w"] / 2 - 0.1, lo + el["h"] * 0.45),
                            P(uc + el["w"] / 2 - 0.1, lo + el["h"] * 0.55),
                            "door", 0.25)
    # roof: the skin's outline seen from this side
    if L:
        for poly in L["skin"]:
            sh.poly([P(u_of(p[0], p[1]), p[2]) for p in poly], "roof", 0.25)
    # levels
    for f in range(n + 1):
        z = f * H
        p = P(umax, z)
        sh.line(p, (p[0] + 8, p[1]), "dim", 0.13)
        sh.text((p[0] + 9, p[1] - 1), f"{'±' if z == 0 else '+'}{z:.2f}", 2.2,
                "left", "dim")
    return sc


def a_elevations(sh, E, L, sides):
    x0, y0, x1, y1 = drawing_area()
    mid = (x0 + x1) / 2
    names = {(0, -1): "รูปด้านหน้า", (1, 0): "รูปด้านขวา", (0, 1): "รูปด้านหลัง",
             (-1, 0): "รูปด้านซ้าย"}
    for i, side in enumerate(sides):
        box = (x0, y0, mid - 5, y1) if i == 0 else (mid + 5, y0, x1, y1)
        sc = elevation(sh, E, L, side, box)
        caption(sh, ((box[0] + box[2]) / 2, y0 + 6), names[side], f"1:{sc}")


def section(sh, E, L, axis, box):
    """Section cut across the building: ``axis`` "x" cuts at mid-x looking
    along +x (shows y–z), "y" cuts at mid-y (shows x–z)."""
    H, n, lib = E["H"], E["n"], E["lib"]
    xs, ys = grids(E)
    if not xs:
        return 100
    if axis == "x":
        cut = (xs[0] + xs[-1]) / 2
        cut = min(xs, key=lambda x: abs(x - cut)) + 0.01
        umin, umax = ys[0], ys[-1]
    else:
        cut = (ys[0] + ys[-1]) / 2
        cut = min(ys, key=lambda y: abs(y - cut)) + 0.01
        umin, umax = xs[0], xs[-1]
    ov = float(E["settings"].get("overhang") or 0)
    umin, umax = umin - ov - 0.5, umax + ov + 0.5
    ztop, zmin = n * H + 3.0, -2.0
    bw, bh = box[2] - box[0] - 22, box[3] - box[1] - 12
    sc = fit_scale((umax - umin, ztop - zmin), (bw, bh), PLAN_SCALES)
    sh.scale = f"1:{sc}"
    k = 1000.0 / sc
    ox = box[0] + (bw - (umax - umin) * k) / 2
    oy = box[1] + 12

    def P(u, z):
        return (ox + (u - umin) * k, oy + (z - zmin) * k)
    sh.line(P(umin, 0), P(umax, 0), "cut", 0.5)
    # slabs cut
    for sl in E["slabs"]:
        rm = sl["room"]
        lo, hi = (rm["x"], rm["x"] + rm["w"]) if axis == "x" else \
            (rm["y"], rm["y"] + rm["d"])
        if not (lo <= cut <= hi):
            continue
        a, b = (rm["y"], rm["y"] + rm["d"]) if axis == "x" else \
            (rm["x"], rm["x"] + rm["w"])
        t = float(lib.get(sl["mark"], {}).get("t", 0.1))
        pts = [P(a, sl["z"] - t), P(b, sl["z"] - t), P(b, sl["z"]),
               P(a, sl["z"])]
        sh.fill(pts, "cut", 0.2)
        sh.poly(pts, "cut", 0.5)
    # beams and walls crossing the cut line
    for bm in E["beams"]:
        (x0_, y0_), (x1_, y1_) = bm["p0"], bm["p1"]
        if axis == "x":
            crosses = abs(y0_ - y1_) < 1e-6 and min(x0_, x1_) <= cut <= \
                max(x0_, x1_)
            u = y0_
        else:
            crosses = abs(x0_ - x1_) < 1e-6 and min(y0_, y1_) <= cut <= \
                max(y0_, y1_)
            u = x0_
        if not crosses:
            continue
        spec = lib.get(bm["mark"], {})
        b_, h_ = float(spec.get("b", 0.2)), float(spec.get("h", 0.4))
        pts = [P(u - b_ / 2, bm["z"] - h_), P(u + b_ / 2, bm["z"] - h_),
               P(u + b_ / 2, bm["z"]), P(u - b_ / 2, bm["z"])]
        sh.fill(pts, "cut", 0.2)
        sh.poly(pts, "cut", 0.5)
        for f in range(n):
            if bm["level"] == f + 1:
                w0 = P(u - 0.05, f * H)
                w1 = P(u + 0.05, bm["z"] - h_)
                sh.rect(w0[0], w0[1], w1[0], w1[1], "wall", 0.35)
    # footings under the cut line
    for ft in E["footings"]:
        on = abs(ft["x"] - cut) < 0.5 if axis == "x" else \
            abs(ft["y"] - cut) < 0.5
        if not on:
            continue
        spec = lib.get(ft["mark"], {})
        u = ft["y"] if axis == "x" else ft["x"]
        w_ = float(spec.get("w", 1.0))
        sh.rect(*P(u - w_ / 2, ft["z0"]), *P(u + w_ / 2, ft["z1"]), "cut", 0.35)
        sh.rect(*P(u - 0.1, ft["z1"]), *P(u + 0.1, 0), "cut", 0.25)
    # roof cut
    if L:
        for poly in L["skin"]:
            seg = _cut_poly(poly, axis, cut)
            if seg:
                (ua, za), (ub, zb) = seg
                sh.line(P(ua, za), P(ub, zb), "roof", 0.6)
    for f in range(n + 1):
        z = f * H
        p = P(umax, z)
        sh.line(p, (p[0] + 8, p[1]), "dim", 0.13)
        sh.text((p[0] + 9, p[1] - 1), f"{'±' if z == 0 else '+'}{z:.2f}", 2.2,
                "left", "dim")
    return sc


def _cut_poly(poly, axis, cut):
    """Where a planar roof facet meets the cutting plane: ((u,z),(u,z))."""
    i = 0 if axis == "x" else 1
    j = 1 - i
    hits = []
    for a, b in zip(poly, poly[1:] + poly[:1]):
        if (a[i] - cut) * (b[i] - cut) <= 0 and abs(a[i] - b[i]) > 1e-9:
            t = (cut - a[i]) / (b[i] - a[i])
            hits.append((a[j] + (b[j] - a[j]) * t, a[2] + (b[2] - a[2]) * t))
    if len(hits) >= 2:
        hits.sort()
        return hits[0], hits[-1]
    return None


def a_sections(sh, E, L):
    x0, y0, x1, y1 = drawing_area()
    mid = (x0 + x1) / 2
    for i, (axis, name) in enumerate((("x", "รูปตัด ก-ก"), ("y", "รูปตัด ข-ข"))):
        box = (x0, y0, mid - 5, y1) if i == 0 else (mid + 5, y0, x1, y1)
        sc = section(sh, E, L, axis, box)
        caption(sh, ((box[0] + box[2]) / 2, y0 + 6), name, f"1:{sc}")


def a_schedules(sh, E, codes, fcodes):
    x0, y0, x1, y1 = drawing_area()
    sh.text((x0, y1 - 5), "ตารางประตู-หน้าต่าง", 4.0, "left", "text", True)
    count: dict = {}
    for o in E["openings"]:
        c = op_code(o, codes)
        count[c] = count.get(c, 0) + 1
    x = x0
    y = y1 - 12
    for key, code in sorted(codes.items(), key=lambda t: (t[1][0] != "ป",
                                                          int(t[1][1:]))):
        style, w, h, sill = key
        spec = CAT.OPENING_TYPES.get(style) or CAT.OPENING_TYPES[
            "D1" if code.startswith("ป") else "W1"]
        k = 1000.0 / 50
        bw, bh = w * k, h * k
        if x + max(bw, 40) > x1:
            x, y = x0, y - 70
        base = y - 52
        sh.rect(x, base, x + bw, base + bh, "door" if code.startswith("ป")
                else "window", 0.35)
        leaves = max(1, int(spec.get("leaves") or 1))
        for i in range(1, leaves):
            sh.line((x + bw * i / leaves, base), (x + bw * i / leaves,
                                                  base + bh), "window", 0.18)
        if spec.get("glass"):
            sh.rect(x + 2, base + bh * 0.2, x + bw - 2, base + bh - 2,
                    "window", 0.13)
        sh.text((x + bw / 2, base + bh + 3), code, 3.2, "center", "text", True)
        sh.text((x, base - 4), spec["name"][:28], 2.0)
        sh.text((x, base - 7.5), f"ขนาด {w:.2f}×{h:.2f} ม."
                + (f" ขอบล่าง {sill:.2f}" if sill else ""), 2.0)
        sh.text((x, base - 11), f"จำนวน {count.get(code, 0)} ชุด", 2.0)
        x += max(bw, 40) + 10
    # finish schedule
    rows = [(c, d) for _k, (c, d) in sorted(fcodes.items(),
                                            key=lambda t: t[1][0])]
    rows.append(("ฝ1", "ฝ้าเพดานยิปซัมบอร์ด 9 มม. โครงคร่าวเหล็กชุบสังกะสี ฉาบรอยต่อเรียบ ทาสี"))
    yy = min(y - 75, y0 + 70)
    sh.text((x0, yy + 6), "ตารางวัสดุตกแต่ง (พื้น/ฝ้า)", 3.6, "left", "text",
            True)
    table(sh, x0, yy, [("รหัส", 18, "center"), ("รายละเอียด", 250, "left")],
          rows)
    caption(sh, ((x0 + x1) / 2, y0 + 4), "ตารางประตู-หน้าต่าง / วัสดุตกแต่ง",
            "1:50")


def a_bathrooms(sh, E):
    x0, y0, x1, y1 = drawing_area()
    baths = [(sl["floor"], sl["room"]) for sl in E["slabs"]
             if (sl["room"].get("name") or "").startswith("ห้องน้ำ")]
    if not baths:
        return False
    x = x0 + 10
    y_top = y1 - 10
    t = float(E["settings"].get("wall_t") or 0.1)
    for i, (k, rm) in enumerate(baths[:4]):
        sc = 50 if rm["w"] <= 3.5 and rm["d"] <= 3.5 else 75
        kk = 1000.0 / sc
        if x + rm["w"] * kk > x1:
            x, y_top = x0 + 10, y_top - 120
        v = View(sh, sc, (rm["x"], rm["y"]), (x, y_top - rm["d"] * kk - 10))
        pts = B.room_corners(rm)
        for a, b in zip(pts, pts[1:] + pts[:1]):
            sh.line(v(*a), v(*b), "wall", 0.5)
        inner = [(pts[0][0] + t / 2, pts[0][1] + t / 2),
                 (pts[1][0] - t / 2, pts[1][1] + t / 2),
                 (pts[2][0] - t / 2, pts[2][1] - t / 2),
                 (pts[3][0] + t / 2, pts[3][1] - t / 2)]
        sh.poly([v(*p) for p in inner], "wall", 0.25)
        draw_fixtures(sh, v, {"fixtures": [f for f in E["fixtures"]
                                           if f["floor"] == k and
                                           _inside(f["fx"], rm)]}, k)
        fd = v(rm["x"] + rm["w"] * 0.7, rm["y"] + rm["d"] * 0.3)
        sh.rect(fd[0] - 1.5, fd[1] - 1.5, fd[0] + 1.5, fd[1] + 1.5, "pipe",
                0.25)
        sh.text((fd[0] + 2.5, fd[1] - 0.8), "FD", 2.0, "left", "pipe")
        dim_chain(sh, v, [rm["x"], rm["x"] + rm["w"]], rm["y"] - 0.35, "x")
        dim_chain(sh, v, [rm["y"], rm["y"] + rm["d"]], rm["x"] - 0.35, "y")
        f = CAT.finish_of(rm)
        sh.text((x, y_top - rm["d"] * kk - 18),
                f"{rm.get('name')} (ชั้น {k + 1}) 1:{sc} · ผนังกรุกระเบื้องสูง "
                f"{f['tile_h']:.2f} ม. · พื้นต่ำกว่าห้องข้างเคียง 0.05 ม.", 2.2)
        x += rm["w"] * kk + 30
    caption(sh, ((x0 + x1) / 2, y0 + 4), "แบบขยายห้องน้ำ", "1:50")
    return True


def _inside(fx, rm):
    return rm["x"] - 1e-6 <= float(fx["x"]) <= rm["x"] + rm["w"] + 1e-6 and \
        rm["y"] - 1e-6 <= float(fx["y"]) <= rm["y"] + rm["d"] + 1e-6


# ---------------------------------------------------------------------------
# S — structure
# ---------------------------------------------------------------------------

def s_notes(E):
    lib = E["lib"]
    piles = [m for m, sp in lib.items() if sp.get("kind") == "footing" and
             int(sp.get("piles") or 0)]
    lines = [
        "ให้ใช้มาตรฐานกรมโยธาธิการและผังเมือง มยผ. 1101–1106 และมาตรฐาน วสท. "
        "(วสท. 011008 อาคารคอนกรีตเสริมเหล็กโดยวิธีกำลัง) เป็นรายการประกอบแบบทั่วไป",
        "1. คอนกรีต: หากไม่ระบุเป็นอย่างอื่น ใช้ ค.3 กำลังอัดประลัยทรงกระบอกอายุ 28 วัน "
        "ไม่น้อยกว่า 210 กก./ตร.ซม. (ลูกบาศก์ 240 กก./ตร.ซม.)",
        "2. เหล็กเสริม: Ø6, Ø9 มม. ใช้เหล็กกลม SR24 (fy ไม่น้อยกว่า 2,400 กก./ตร.ซม.) ตั้งแต่ "
        "Ø12 มม. ขึ้นไปใช้เหล็กข้ออ้อย SD40 (fy ไม่น้อยกว่า 4,000 กก./ตร.ซม.)",
        "3. ระยะหุ้มคอนกรีต: ฐานราก 7.5 ซม. เสา 3.5 ซม. คาน 3.0 ซม. พื้น 2.0 ซม. "
        "(ตรวจสอบกับมาตรฐานที่ใช้ออกแบบ)",
        "4. ระยะทาบเหล็ก: เหล็กข้ออ้อยไม่น้อยกว่า 40 เท่า เหล็กกลมไม่น้อยกว่า 48 เท่า"
        "ของเส้นผ่านศูนย์กลาง พร้อมงอขอ",
        "5. ฐานราก: " + ("ใช้ฐานรากเสาเข็ม (" + ", ".join(piles) + ") ความยาว"
                         "เสาเข็มให้ตรวจสอบตามสภาพชั้นดิน" if piles else
                         "ใช้ฐานรากแผ่ เมื่อดินรับน้ำหนักบรรทุกปลอดภัยไม่น้อยกว่า "
                         "10 ตัน/ตร.ม. หากน้อยกว่าให้ใช้ฐานรากเสาเข็ม") +
        " ชนิดฐานรากในอาคารเดียวกันให้ใช้ชนิดเดียว",
        "6. เหล็กรูปพรรณโครงหลังคา: fy ไม่น้อยกว่า 2,400 กก./ตร.ซม. เชื่อมไฟฟ้าตลอดแนวสัมผัส "
        "ทาสีกันสนิม 2 ชั้นก่อนทาสีจริง",
        "7. ส่วนที่สัมผัสดินหรือน้ำ (พื้นห้องน้ำ ดาดฟ้า ถังเก็บน้ำ) ให้ผสมน้ำยากันซึม",
        "8. ถอดแบบหล่อ: ข้างคาน/เสา ไม่น้อยกว่า 2 วัน ท้องคาน/ท้องพื้น ไม่น้อยกว่า 14 วัน (หรือเมื่อ"
        "คอนกรีตได้กำลัง 70%) บ่มคอนกรีตต่อเนื่องอย่างน้อย 7 วัน",
        "9. ขนาดชิ้นส่วนและเหล็กเสริมในแบบนี้มาจากคลังชิ้นส่วนของโปรแกรม วิศวกรผู้ออกแบบ"
        "ต้องคำนวณ ตรวจสอบ และลงนามรับรองก่อนนำไปใช้ขออนุญาตหรือก่อสร้าง",
    ]
    return lines


def s_index(sh, sheets, E):
    x0, y0, x1, y1 = drawing_area()
    sh.text((x0 + 95, y1 - 6), "สารบัญแบบวิศวกรรมโครงสร้าง", 4.0, "center",
            "text", True)
    sheet_index(sheets, "S", sh, x0, y1 - 12, 190)
    notes_block(sh, x0 + 200, y1 - 6, "รายการประกอบแบบงานโครงสร้าง",
                s_notes(E), 2.2, 60)


def s_foundation(sh, E):
    v, sc = plan_view(sh, E)
    draw_grid(sh, v, E)
    lib = E["lib"]
    for ft in E["footings"]:
        spec = lib.get(ft["mark"], {})
        w, l_ = float(spec.get("w", 1)), float(spec.get("l", spec.get("w", 1)))
        sh.rect(*v(ft["x"] - w / 2, ft["y"] - l_ / 2),
                *v(ft["x"] + w / 2, ft["y"] + l_ / 2), "struct", 0.35)
        st = lib.get(next((s["mark"] for s in E["stumps"]
                           if s["x"] == ft["x"] and s["y"] == ft["y"]), "PC1"),
                     {})
        b = float(st.get("b", 0.2))
        pts = [v(ft["x"] - b / 2, ft["y"] - b / 2), v(ft["x"] + b / 2, ft["y"] - b / 2),
               v(ft["x"] + b / 2, ft["y"] + b / 2), v(ft["x"] - b / 2, ft["y"] + b / 2)]
        sh.fill(pts, "column", 0.15)
        for px, py in B.pile_points(spec, ft["x"], ft["y"]):
            sh.circle(v(px, py), v.len(float(spec.get("pile_b", 0.18)) / 2),
                      "struct", 0.18)
        p = v(ft["x"] + w / 2, ft["y"] + l_ / 2)
        sh.text((p[0] + 0.8, p[1] + 0.6), f"{ft['mark']}", 2.4, "left",
                "struct", True)
    x0, y0, x1, y1 = drawing_area()
    caption(sh, ((x0 + x1) / 2, y0 + 6), "แปลนฐานราก", f"1:{sc}")


def s_beams(sh, E, lvl):
    v, sc = plan_view(sh, E)
    draw_grid(sh, v, E)
    lib = E["lib"]
    for bm in (b for b in E["beams"] if b["level"] == lvl):
        b = float(lib.get(bm["mark"], {}).get("b", 0.2))
        (x0, y0), (x1, y1) = bm["p0"], bm["p1"]
        L = math.hypot(x1 - x0, y1 - y0) or 1
        nx, ny = -(y1 - y0) / L, (x1 - x0) / L
        for sg in (-1, 1):
            sh.line(v(x0 + nx * b / 2 * sg, y0 + ny * b / 2 * sg),
                    v(x1 + nx * b / 2 * sg, y1 + ny * b / 2 * sg), "struct",
                    0.35, True)
        m = v((x0 + x1) / 2 + nx * 0.25, (y0 + y1) / 2 + ny * 0.25)
        sh.text(m, bm["mark"], 2.2, "center", "struct", True,
                90 if abs(x1 - x0) < 1e-6 else 0)
    cols = [c for c in E["columns"] if c["floor"] == min(lvl, E["n"] - 1)] \
        if lvl < E["n"] else [c for c in E["columns"] if c["floor"] == E["n"] - 1]
    for c in cols:
        b = float(lib.get(c["mark"], {}).get("b", 0.2))
        pts = [v(c["x"] - b / 2, c["y"] - b / 2), v(c["x"] + b / 2, c["y"] - b / 2),
               v(c["x"] + b / 2, c["y"] + b / 2), v(c["x"] - b / 2, c["y"] + b / 2)]
        sh.fill(pts, "column", 0.15)
        p = v(c["x"] - b / 2, c["y"] - b / 2)
        sh.text((p[0] - 0.5, p[1] - 3), c["mark"], 1.8, "right", "struct")
    if lvl < E["n"]:
        for sl in (s for s in E["slabs"] if s["floor"] == lvl):
            rm = sl["room"]
            a = v(rm["x"], rm["y"])
            b_ = v(rm["x"] + rm["w"], rm["y"] + rm["d"])
            sh.line(a, b_, "struct", 0.13)
            c = v(rm["x"] + rm["w"] / 2, rm["y"] + rm["d"] / 2)
            sh.circle(c, 4, "struct", 0.25)
            sh.text((c[0], c[1] - 1.1), sl["mark"], 2.4, "center", "struct",
                    True)
    x0_, y0_, x1_, y1_ = drawing_area()
    name = "แปลนคานคอดิน และพื้นชั้น 1" if lvl == 0 else \
        "แปลนคานหลังคา" if lvl == E["n"] else f"แปลนคาน และพื้นชั้น {lvl + 1}"
    caption(sh, ((x0_ + x1_) / 2, y0_ + 6), name, f"1:{sc}")


def s_roof_frame(sh, E, L):
    v, sc = plan_view(sh, E, pad=3.2)
    draw_grid(sh, v, E, dims=True)
    s = E["settings"]
    if L:
        for a, b in L["rafter"]:
            sh.line(v(a[0], a[1]), v(b[0], b[1]), "struct", 0.35)
        for pl in L["purlin"]:
            pts = [v(p[0], p[1]) for p in pl["path"]]
            sh.poly(pts, "struct", 0.13, pl.get("closed", False))
        for k in ("ridge", "hip"):
            for a, b in L[k]:
                sh.line(v(a[0], a[1]), v(b[0], b[1]), "struct", 0.6)
        for a, b in L.get("eave") or []:
            sh.line(v(a[0], a[1]), v(b[0], b[1]), "roof", 0.25)
    x0, y0, x1, y1 = drawing_area()
    lines = [f"อกไก่ {s['ridge']}", f"ตะเข้สัน {s['hip']}",
             f"จันทัน {s['rafter']} @ ไม่เกิน {float(s['rafter_sp']):.2f} ม.",
             f"แป {s['purlin']} @ {float(s['purlin_sp']):.2f} ม.",
             f"ความลาดหลังคา {float(s['pitch']):.0f}°  ชายคา "
             f"{float(s['overhang']):.2f} ม."]
    for i, t in enumerate(lines):
        sh.text((x0, y0 + 30 - i * 4.5), t, 2.4)
    caption(sh, ((x0 + x1) / 2, y0 + 6), "แปลนโครงหลังคา", f"1:{sc}")


def s_schedules(sh, E):
    x0, y0, x1, y1 = drawing_area()
    lib = E["lib"]
    used = {e["mark"] for key in ("footings", "stumps", "columns", "beams",
                                  "slabs") for e in E[key]}
    y = y1 - 6
    sh.text((x0, y), "ตารางฐานราก", 3.6, "left", "text", True)
    rows = []
    for m in sorted(k for k in used if lib.get(k, {}).get("kind") == "footing"):
        sp = lib[m]
        n = sum(1 for f in E["footings"] if f["mark"] == m)
        piles = int(sp.get("piles") or 0)
        rows.append((m, f"{float(sp['w']):.2f}×{float(sp['l']):.2f}",
                     f"{float(sp['t']):.2f}", f"{float(sp['depth']):.2f}",
                     sp.get("bars", ""), (f"{piles} ต้น {float(sp['pile_b']):.2f}×"
                                          f"{float(sp['pile_len']):.0f} ม.")
                     if piles else "ฐานแผ่", str(n)))
    y = table(sh, x0, y - 3, [("เบอร์", 18, "center"), ("กว้าง×ยาว (ม.)", 32,
                                                       "center"),
                              ("หนา", 16, "center"), ("ลึก", 16, "center"),
                              ("เหล็กตะแกรง", 34, "center"),
                              ("เสาเข็ม", 46, "center"), ("จำนวน", 16, "center")],
              rows)
    y -= 8
    sh.text((x0, y), "ตารางเสาตอม่อ / เสา", 3.6, "left", "text", True)
    rows = []
    for m in sorted(k for k in used if lib.get(k, {}).get("kind") in
                    ("stump", "column")):
        sp = lib[m]
        rows.append((m, "ตอม่อ" if sp["kind"] == "stump" else "เสา",
                     f"{float(sp['b']):.2f}×{float(sp['h']):.2f}", sp.get("main", ""),
                     sp.get("tie", "")))
    y = table(sh, x0, y - 3, [("เบอร์", 18, "center"), ("ชนิด", 20, "center"),
                              ("ขนาด (ม.)", 28, "center"),
                              ("เหล็กยืน", 30, "center"),
                              ("เหล็กปลอก", 30, "center")], rows)
    # section sketches
    sx = x0 + 135
    for m in sorted(k for k in used if lib.get(k, {}).get("kind") in
                    ("stump", "column")):
        sp = lib[m]
        _section_sketch(sh, (sx, y + 4), float(sp["b"]), float(sp["h"]),
                        sp.get("main", ""), m)
        sx += 30
    y -= 8
    sh.text((x0, y), "ตารางคาน", 3.6, "left", "text", True)
    rows = []
    beams = sorted(k for k in used if lib.get(k, {}).get("kind") == "beam")
    for m in beams:
        sp = lib[m]
        rows.append((m, f"{float(sp['b']):.2f}×{float(sp['h']):.2f}",
                     sp.get("top", ""), sp.get("bot", ""), sp.get("stir", "")))
    y2 = table(sh, x0, y - 3, [("เบอร์", 18, "center"), ("ขนาด (ม.)", 28,
                                                         "center"),
                               ("เหล็กบน", 30, "center"), ("เหล็กล่าง", 30,
                                                           "center"),
                               ("เหล็กปลอก", 30, "center")], rows)
    sx = x0 + 145
    for m in beams:
        sp = lib[m]
        _section_sketch(sh, (sx, y2 + 4), float(sp["b"]), float(sp["h"]),
                        f"{sp.get('top', '')}/{sp.get('bot', '')}", m)
        sx += 28
    y = y2 - 8
    sh.text((x0, y), "ตารางพื้น", 3.6, "left", "text", True)
    rows = []
    for m in sorted(k for k in used if lib.get(k, {}).get("kind") == "slab"):
        sp = lib[m]
        rows.append((m, f"{float(sp['t']):.2f}", sp.get("bars", ""),
                     "พื้นวางบนดิน" if int(sp.get("ground") or 0) else "พื้นวางบนคาน"))
    table(sh, x0, y - 3, [("เบอร์", 18, "center"), ("หนา (ม.)", 22, "center"),
                          ("เหล็กเสริม 2 ทาง", 40, "center"),
                          ("ชนิด", 40, "center")], rows)
    caption(sh, ((x0 + x1) / 2, y0 + 4), "ตารางโครงสร้าง", "-")


def _section_sketch(sh, p, b, h, bars, mark, k=60.0):
    """A small cross-section (k mm per metre) with corner bars."""
    w, hh = b * k, h * k
    x, y = p[0], p[1]
    sh.rect(x, y, x + w, y + hh, "struct", 0.35)
    c = 3.0
    sh.rect(x + c * 0.6, y + c * 0.6, x + w - c * 0.6, y + hh - c * 0.6,
            "rebar", 0.13)
    for bx, by in ((x + c, y + c), (x + w - c, y + c), (x + c, y + hh - c),
                   (x + w - c, y + hh - c)):
        sh.circle((bx, by), 0.6, "rebar", 0.25)
    sh.text((x + w / 2, y + hh + 2), mark, 2.2, "center", "struct", True)
    sh.text((x + w / 2, y - 3), bars[:14], 1.6, "center", "struct")


# ---------------------------------------------------------------------------
# SN — sanitary
# ---------------------------------------------------------------------------

SN_NOTES = [
    "1. ท่อโสโครก (S) ท่อน้ำทิ้ง (W) และท่ออากาศ (V) ใช้ท่อ PVC ชั้น 8.5 ท่อประปา (CW) "
    "ใช้ท่อ PVC ชั้น 13.5 ต่อด้วยน้ำยาประสานท่อ",
    "2. ความลาดท่อแนวนอน: ท่อโสโครกและท่อน้ำทิ้งไม่น้อยกว่า 1:100 (ตามแบบ)",
    "3. ท่อโสโครกจากโถส้วม Ø4\" ลงบ่อบำบัดน้ำเสียสำเร็จรูป ท่อน้ำทิ้ง Ø2\" ผ่านบ่อดักไขมัน"
    "ก่อนระบายสู่ท่อสาธารณะ",
    "4. ทุกจุดเปลี่ยนทิศท่อโสโครกให้มีช่องทำความสะอาด (FCO/CO) ปลายท่ออากาศสูงพ้นหลังคา",
    "5. ทดสอบท่อประปาด้วยแรงดันไม่น้อยกว่า 1.5 เท่าของแรงดันใช้งาน นาน 1 ชั่วโมง",
    "6. ท่อในแบบเป็นแนวโดยประมาณ ให้ปรับตามสภาพหน้างาน",
]
SN_SYMBOLS = [("S", "ท่อโสโครก"), ("W", "ท่อน้ำทิ้ง"), ("V", "ท่ออากาศ"),
              ("CW", "ท่อน้ำประปา"), ("FD", "ท่อระบายน้ำที่พื้น"),
              ("FCO", "ช่องทำความสะอาดที่พื้น"), ("ST", "บ่อบำบัดน้ำเสีย"),
              ("GT", "บ่อดักไขมัน"), ("M", "มาตรวัดน้ำ")]


def sn_index(sh, sheets):
    x0, y0, x1, y1 = drawing_area()
    sh.text((x0 + 95, y1 - 6), "สารบัญแบบระบบสุขาภิบาล", 4.0, "center", "text",
            True)
    y = sheet_index(sheets, "SN", sh, x0, y1 - 12, 190)
    y = notes_block(sh, x0, y - 10, "สัญลักษณ์", [f"{a:<5}  {b}" for a, b in
                                              SN_SYMBOLS], 2.4, 60)
    notes_block(sh, x0 + 200, y1 - 6, "รายการประกอบแบบงานระบบสุขาภิบาล",
                SN_NOTES, 2.3, 60)


def sn_plan(sh, E, k):
    v, sc = plan_view(sh, E)
    t = float(E["settings"].get("wall_t") or 0.1)
    draw_grid(sh, v, E, dims=False)
    draw_walls(sh, v, E, k, t, None, swings=False, tags=False)
    draw_rooms(sh, v, E, k, area=False)
    draw_fixtures(sh, v, E, k)
    xs, ys = grids(E)
    yc = ys[0] - 1.0                       # sewer collector outside
    yw = ys[0] - 0.45                      # water main
    tank = (xs[0] - 1.6, yc)
    gt = (xs[0] - 1.6, ys[0] + 0.6)
    meter = (xs[-1] + 1.4, yw)
    if k == 0:
        _box(sh, v, tank, 1.2, 0.8, "ST บ่อบำบัด")
        _box(sh, v, gt, 0.5, 0.5, "GT")
        _box(sh, v, meter, 0.3, 0.3, "M")
        sh.line(v(gt[0], gt[1] - 0.25), v(tank[0], tank[1] + 0.4), "pipe",
                0.35, True)
    drops = []
    for f in (x for x in E["fixtures"] if x["floor"] == k):
        fx = f["fx"]
        p = (float(fx["x"]), float(fx["y"]))
        typ = fx.get("type", "")
        soil = typ.startswith("WC") or typ == "UR"
        lay, size = ("S", "Ø4\"") if soil else ("W", "Ø2\"")
        if typ.startswith("SK") and k == 0:
            sh.line(v(*p), v(p[0], gt[1]), "pipe", 0.35, True)
            sh.line(v(p[0], gt[1]), v(gt[0] + 0.25, gt[1]), "pipe", 0.35,
                    True)
        else:
            sh.line(v(*p), v(p[0], yc), "pipe", 0.5 if soil else 0.35,
                    not soil)
            drops.append(p[0])
        q = v(*p)
        sh.text((q[0] + 1.5, q[1] + 1.5), f"{lay} {size}", 1.8, "left", "pipe")
        # cold water: from the main up to the fixture, offset 0.15 m
        wx = p[0] + 0.15
        sh.line(v(wx, yw), v(wx, p[1]), "pipe", 0.18, True)
        drops.append(None)
    xs_d = [x for x in drops if x is not None]
    if xs_d:
        sh.line(v(min(xs_d + [tank[0] + 0.6]), yc), v(max(xs_d), yc), "pipe",
                0.5)
        c = v((min(xs_d) + max(xs_d)) / 2, yc)
        sh.text((c[0], c[1] - 3), "ท่อรวม Ø4\" ลาด 1:100 ไปบ่อบำบัด", 1.8,
                "center", "pipe")
        sh.line(v(meter[0] - 0.15, yw), v(min(x + 0.15 for x in xs_d), yw),
                "pipe", 0.18, True)
        c = v(meter[0], yw)
        sh.text((c[0] - 2, c[1] + 1.5), "CW Ø¾\" จากมาตรวัดน้ำ", 1.8, "right",
                "pipe")
    for sl in (s for s in E["slabs"] if s["floor"] == k):
        if (sl["room"].get("name") or "").startswith("ห้องน้ำ"):
            rm = sl["room"]
            c = v(rm["x"] + rm["w"] * 0.7, rm["y"] + rm["d"] * 0.3)
            sh.rect(c[0] - 1.2, c[1] - 1.2, c[0] + 1.2, c[1] + 1.2, "pipe",
                    0.25)
            sh.text((c[0] + 2, c[1] - 0.8), "FD Ø2\"", 1.8, "left", "pipe")
    x0, y0, x1, y1 = drawing_area()
    sh.text((x0, y0 + 20), "เส้นทึบ = ท่อโสโครก S · เส้นประหนา = ท่อน้ำทิ้ง W · "
            "เส้นประบาง = ท่อประปา CW (PVC ชั้น 13.5 Ø½\"–¾\")", 2.2)
    caption(sh, ((x0 + x1) / 2, y0 + 6), f"แปลนระบบสุขาภิบาลชั้น {k + 1}",
            f"1:{sc}")


def _box(sh, v, c, w, d, label):
    sh.rect(*v(c[0] - w / 2, c[1] - d / 2), *v(c[0] + w / 2, c[1] + d / 2),
            "pipe", 0.35)
    p = v(c[0], c[1] - d / 2)
    sh.text((p[0], p[1] - 3), label, 2.0, "center", "pipe")


# ---------------------------------------------------------------------------
# EE — electrical
# ---------------------------------------------------------------------------

EE_NOTES = [
    "1. การติดตั้งให้เป็นไปตามมาตรฐานการติดตั้งทางไฟฟ้าสำหรับประเทศไทย (วสท.) "
    "และข้อกำหนดของการไฟฟ้าส่วนภูมิภาค/นครหลวง",
    "2. สายไฟฟ้าใช้ สาย THW/VAF ตาม มอก. 11 เดินในท่อ PVC หรือ EMT ขนาดตามแบบ "
    "วงจรแสงสว่าง 2.5 ตร.มม. วงจรเต้ารับ 4 ตร.มม. พร้อมสายดิน",
    "3. แผงย่อย (LP) มีเมนเบรกเกอร์ชนิดป้องกันไฟรั่ว (RCBO/RCD 30 mA) ต่อลงดิน "
    "ด้วยหลักดินทองแดง Ø5/8\" ยาว 2.40 ม.",
    "4. เต้ารับเป็นชนิดมีขั้วสายดิน สูง 0.30 ม. จากพื้น (ห้องน้ำ/ครัว 1.20 ม.) สวิตช์สูง 1.20 ม.",
    "5. จำนวนและตำแหน่งดวงโคมเป็นค่าเริ่มต้นตามพื้นที่ห้อง ให้วิศวกรไฟฟ้าตรวจสอบ"
    "และคำนวณโหลดก่อนใช้งาน",
]
EE_SYMBOLS = [("light", "ดวงโคมดาวน์ไลท์ / โคมเพดาน 20 W"),
              ("switch", "สวิตช์ทางเดียว สูง 1.20 ม."),
              ("socket", "เต้ารับคู่มีสายดิน สูง 0.30 ม."),
              ("ac", "เต้ารับ/จุดเครื่องปรับอากาศ"),
              ("panel", "แผงไฟฟ้าย่อย LP"), ("run", "แนวเดินสาย (ท่อร้อยสาย)")]


def ee_points(E, k):
    """Default points per room: lights by area, a switch by the first door,
    sockets on the walls."""
    pts = []
    for sl in (s for s in E["slabs"] if s["floor"] == k):
        rm = sl["room"]
        a = rm["w"] * rm["d"]
        name = rm.get("name") or ""
        n_l = max(1, math.ceil(a / 9.0))
        cols = max(1, round(math.sqrt(n_l * rm["w"] / max(rm["d"], 0.1))))
        rows = max(1, math.ceil(n_l / cols))
        for i in range(cols):
            for j in range(rows):
                pts.append(("light", rm["x"] + rm["w"] * (i + 0.5) / cols,
                            rm["y"] + rm["d"] * (j + 0.5) / rows, rm))
        bath = name.startswith("ห้องน้ำ")
        n_s = 0 if bath else 3 if name.startswith("ห้องครัว") else 2
        spots = [(rm["x"] + 0.3, rm["y"] + rm["d"] / 2),
                 (rm["x"] + rm["w"] - 0.3, rm["y"] + rm["d"] / 2),
                 (rm["x"] + rm["w"] / 2, rm["y"] + rm["d"] - 0.3)]
        for x, y in spots[:n_s]:
            pts.append(("socket", x, y, rm))
        if name.startswith("ห้องนอน"):
            pts.append(("ac", rm["x"] + rm["w"] / 2, rm["y"] + 0.3, rm))
        door = next((o for o in E["openings"] if o["floor"] == k and
                     o["type"] == "door" and _on_room(o["op"], rm)), None)
        if door:
            sx, sy = float(door["op"]["x"]), float(door["op"]["y"])
            sx = min(max(sx + 0.6, rm["x"] + 0.2), rm["x"] + rm["w"] - 0.2)
            sy = min(max(sy, rm["y"] + 0.2), rm["y"] + rm["d"] - 0.2)
        else:
            sx, sy = rm["x"] + 0.3, rm["y"] + 0.3
        pts.append(("switch", sx, sy, rm))
    return pts


def _on_room(op, rm, tol=0.06):
    x, y = float(op["x"]), float(op["y"])
    return rm["x"] - tol <= x <= rm["x"] + rm["w"] + tol and \
        rm["y"] - tol <= y <= rm["y"] + rm["d"] + tol


def ee_loads(E):
    """Circuits of the panel: lighting per floor, sockets ≤ 8 per circuit,
    one per air-conditioner."""
    out = []
    for k in range(E["n"]):
        P = ee_points(E, k)
        nl = sum(1 for p in P if p[0] == "light")
        ns = sum(1 for p in P if p[0] == "socket")
        na = sum(1 for p in P if p[0] == "ac")
        out.append((f"แสงสว่างชั้น {k + 1}", nl, nl * 20, "16 A"))
        for i in range(0, ns, 8):
            c = min(8, ns - i)
            out.append((f"เต้ารับชั้น {k + 1}", c, c * 180, "20 A"))
        for _ in range(na):
            out.append(("เครื่องปรับอากาศ", 1, 1500, "20 A"))
    return out


def ee_index(sh, sheets, E):
    x0, y0, x1, y1 = drawing_area()
    sh.text((x0 + 95, y1 - 6), "สารบัญแบบระบบไฟฟ้า", 4.0, "center", "text",
            True)
    y = sheet_index(sheets, "EE", sh, x0, y1 - 12, 190)
    sh.text((x0, y - 10), "สัญลักษณ์", 3.4, "left", "text", True)
    yy = y - 18
    for kind, desc in EE_SYMBOLS:
        ee_symbol(sh, kind, (x0 + 6, yy + 1))
        sh.text((x0 + 14, yy), desc, 2.4)
        yy -= 7
    loads = ee_loads(E)
    rows = [(str(i + 1), d, str(n), f"{w:,}", cb) for i, (d, n, w, cb) in
            enumerate(loads)]
    total = sum(w for _d, _n, w, _cb in loads)
    rows.append(("", "รวม", "", f"{total:,}", ""))
    sh.text((x0 + 200, y1 - 6), "ตารางโหลดแผงย่อย LP (1 เฟส 230 V)", 3.4,
            "left", "text", True)
    yy = table(sh, x0 + 200, y1 - 10, [("วงจร", 14, "center"),
                                       ("รายการ", 52, "left"),
                                       ("จุด", 14, "center"),
                                       ("วัตต์", 22, "right"),
                                       ("เบรกเกอร์", 22, "center")], rows,
               2.1, 5.2, 6.0)
    amp = total / 230.0 / 0.8
    main = next((m for m in (32, 40, 50, 63, 80, 100) if m >= amp * 1.25), 100)
    sh.text((x0 + 200, yy - 5), f"กระแสโหลดประมาณ {amp:.1f} A → เมนเบรกเกอร์ "
            f"{main} A (RCBO 30 mA) · มิเตอร์ {('15(45)' if main <= 45 else '30(100)')} A",
            2.2)
    notes_block(sh, x0 + 200, yy - 14, "รายการประกอบแบบงานระบบไฟฟ้า",
                EE_NOTES, 2.2, 60)


def ee_symbol(sh, kind, p):
    """One electrical symbol drawn (not a font glyph) at paper point p."""
    if kind == "light":
        sh.circle(p, 1.8, "elec", 0.25)
        sh.line((p[0] - 1.3, p[1] - 1.3), (p[0] + 1.3, p[1] + 1.3), "elec",
                0.18)
        sh.line((p[0] - 1.3, p[1] + 1.3), (p[0] + 1.3, p[1] - 1.3), "elec",
                0.18)
    elif kind == "socket":
        sh.circle(p, 1.4, "elec", 0.25)
        sh.line((p[0] - 1.4, p[1]), (p[0] + 1.4, p[1]), "elec", 0.25)
        sh.line((p[0], p[1] - 1.4), (p[0], p[1] - 2.4), "elec", 0.25)
    elif kind == "ac":
        sh.rect(p[0] - 2.5, p[1] - 1.2, p[0] + 2.5, p[1] + 1.2, "elec", 0.25)
        sh.text((p[0], p[1] - 0.8), "AC", 1.8, "center", "elec")
    elif kind == "panel":
        sh.fill([(p[0] - 3, p[1] - 1.2), (p[0] + 3, p[1] - 1.2),
                 (p[0] + 3, p[1] + 1.2), (p[0] - 3, p[1] + 1.2)], "elec", 0.0)
        sh.text((p[0], p[1] + 2), "LP", 2.4, "center", "elec", True)
    elif kind == "run":
        sh.line((p[0] - 4, p[1]), (p[0] + 4, p[1]), "elec", 0.13, True)
    else:
        sh.text((p[0], p[1] - 1.0), "S", 2.6, "center", "elec", True)


def ee_plan(sh, E, k):
    v, sc = plan_view(sh, E)
    t = float(E["settings"].get("wall_t") or 0.1)
    draw_grid(sh, v, E, dims=False)
    draw_walls(sh, v, E, k, t, None, swings=True, tags=False)
    draw_rooms(sh, v, E, k, area=False)
    pts = ee_points(E, k)
    for kind, x, y, _rm in pts:
        ee_symbol(sh, kind, v(x, y))
    # home runs: each room's lights to its switch
    for _sl in (s for s in E["slabs"] if s["floor"] == k):
        rm = _sl["room"]
        lights = [(x, y) for kd, x, y, r in pts if kd == "light" and r is rm]
        sw = next(((x, y) for kd, x, y, r in pts if kd == "switch" and r is rm),
                  None)
        if sw and lights:
            for a, b in zip([sw] + lights, lights):
                sh.line(v(*a), v(*b), "elec", 0.13, True)
    if k == 0:
        xs, ys = grids(E)
        lp = (xs[0] + 0.35, ys[0] + 0.12) if xs else (0, 0)
        ee_symbol(sh, "panel", v(*lp))
    x0, y0, x1, y1 = drawing_area()
    caption(sh, ((x0 + x1) / 2, y0 + 6), f"แปลนระบบไฟฟ้าชั้น {k + 1}",
            f"1:{sc}")


# ---------------------------------------------------------------------------
# M — mechanical (ventilation / air-conditioning)
# ---------------------------------------------------------------------------

M_NOTES = [
    "1. ห้องน้ำที่ไม่มีหน้าต่างเปิดออกสู่ภายนอก ให้ติดพัดลมระบายอากาศ ขนาดไม่น้อยกว่า "
    "10 เท่าของปริมาตรห้องต่อชั่วโมง",
    "2. ห้องครัวติดเครื่องดูดควัน/พัดลมระบายอากาศ ระบายออกสู่ภายนอกอาคาร",
    "3. เครื่องปรับอากาศแบบแยกส่วน ขนาดโดยประมาณ 750–800 BTU/ชม. ต่อพื้นที่ 1 ตร.ม. "
    "ท่อน้ำทิ้งระบายลงท่อน้ำทิ้งหรือรางระบาย",
    "4. คอยล์ร้อนติดตั้งบนแท่นหรือขายึด ห่างผนังตามคำแนะนำผู้ผลิต",
]


def m_plan(sh, E, k, sheets):
    v, sc = plan_view(sh, E)
    t = float(E["settings"].get("wall_t") or 0.1)
    draw_grid(sh, v, E, dims=False)
    draw_walls(sh, v, E, k, t, None, swings=False, tags=False)
    draw_rooms(sh, v, E, k, area=False)
    for sl in (s for s in E["slabs"] if s["floor"] == k):
        rm = sl["room"]
        name = rm.get("name") or ""
        a = rm["w"] * rm["d"]
        if name.startswith("ห้องน้ำ") or name.startswith("ห้องครัว"):
            p = v(rm["x"] + rm["w"] * 0.3, rm["y"] + rm["d"] * 0.75)
            sh.rect(p[0] - 1.8, p[1] - 1.8, p[0] + 1.8, p[1] + 1.8, "mech",
                    0.25)
            sh.line((p[0] - 1.8, p[1] - 1.8), (p[0] + 1.8, p[1] + 1.8), "mech",
                    0.18)
            sh.text((p[0] + 2.5, p[1] - 0.8), "EF", 2.0, "left", "mech")
        if name.startswith("ห้องนอน"):
            btu = int(math.ceil(a * 800 / 1000.0) * 1000)
            p = v(rm["x"] + rm["w"] / 2, rm["y"] + rm["d"] - 0.25)
            sh.rect(p[0] - 4, p[1] - 1.2, p[0] + 4, p[1] + 1.2, "mech", 0.35)
            sh.text((p[0], p[1] - 4.5), f"FCU {btu:,} BTU", 1.8, "center",
                    "mech")
    x0, y0, x1, y1 = drawing_area()
    notes_block(sh, x1 - 110, y1 - 6, "รายการประกอบแบบงานระบบเครื่องกล",
                M_NOTES, 2.1, 52)
    caption(sh, ((x0 + x1) / 2, y0 + 6),
            f"แปลนระบบปรับอากาศและระบายอากาศชั้น {k + 1}", f"1:{sc}")


# ---------------------------------------------------------------------------
# The set
# ---------------------------------------------------------------------------

GROUP_TH = {"A": "แบบสถาปัตยกรรม", "S": "แบบวิศวกรรมโครงสร้าง",
            "SN": "แบบวิศวกรรมสุขาภิบาล", "EE": "แบบวิศวกรรมไฟฟ้า",
            "M": "แบบวิศวกรรมเครื่องกล", "BOQ": "บัญชีปริมาณงาน (ปร.4)"}


def build_set(data, info=None,
              groups=("A", "S", "SN", "EE", "M", "BOQ")) -> list:
    """Every sheet of the drawing set, numbered, with its title block."""
    info = dict(info or {})
    E = B.elements(data)
    if not E["floors"] or not E["footings"]:
        return []
    L = B.roof_lines(data)
    info.setdefault("roof_rects", (L or {}).get("rects") or [])
    area = sum(sl["room"]["w"] * sl["room"]["d"] for sl in E["slabs"])
    info.setdefault("summary", [
        f"จำนวน {E['n']} ชั้น ความสูงชั้น {E['H']:.2f} ม.",
        f"พื้นที่ใช้สอยรวมประมาณ {area:,.2f} ตร.ม.",
        f"ห้องน้ำ {sum(1 for s in E['slabs'] if (s['room'].get('name') or '').startswith('ห้องน้ำ'))} ห้อง "
        f"ห้องนอน {sum(1 for s in E['slabs'] if (s['room'].get('name') or '').startswith('ห้องนอน'))} ห้อง",
        f"หลังคา {'ปั้นหยา' if E['settings'].get('roof') == 'hip' else 'จั่ว' if E['settings'].get('roof') == 'gable' else 'ไม่มี'} "
        f"ลาด {float(E['settings'].get('pitch') or 0):.0f}°"])
    codes = opening_codes(E)
    fcodes = finish_codes(E)
    plan: list = []                                  # (Sheet, painter)

    def add(group, title, fn, scale="1:100"):
        code = f"{group}-{sum(1 for s, _f in plan if s.group == group) + 1:02d}"
        sh = Sheet(code, title, scale, group)
        plan.append((sh, fn))

    floors = range(E["n"])
    if "A" in groups:
        add("A", "สารบัญแบบ รายการประกอบแบบสถาปัตยกรรม",
            lambda sh, all_: a_index(sh, all_, info), "-")
        add("A", "ผังบริเวณ", lambda sh, _a: a_site(sh, E, info), "1:200")
        for k in floors:
            add("A", f"แปลนพื้นชั้น {k + 1}",
                lambda sh, _a, k=k: _set_scale(sh, a_floor(sh, E, k, codes,
                                                           fcodes)))
        if L:
            add("A", "แปลนหลังคา", lambda sh, _a: a_roof(sh, E, L))
        add("A", "รูปด้านหน้า รูปด้านขวา",
            lambda sh, _a: a_elevations(sh, E, L, [(0, -1), (1, 0)]))
        add("A", "รูปด้านหลัง รูปด้านซ้าย",
            lambda sh, _a: a_elevations(sh, E, L, [(0, 1), (-1, 0)]))
        add("A", "รูปตัด ก-ก รูปตัด ข-ข", lambda sh, _a: a_sections(sh, E, L))
        if E["openings"]:
            add("A", "ตารางประตู-หน้าต่าง วัสดุตกแต่ง",
                lambda sh, _a: a_schedules(sh, E, codes, fcodes), "1:50")
        if any((s["room"].get("name") or "").startswith("ห้องน้ำ")
               for s in E["slabs"]):
            add("A", "แบบขยายห้องน้ำ", lambda sh, _a: a_bathrooms(sh, E),
                "1:50")
    if "S" in groups:
        add("S", "สารบัญแบบ รายการประกอบแบบโครงสร้าง",
            lambda sh, all_: s_index(sh, all_, E), "-")
        add("S", "แปลนฐานราก", lambda sh, _a: s_foundation(sh, E))
        for lvl in range(E["n"] + 1):
            title = "แปลนคานคอดิน พื้นชั้น 1" if lvl == 0 else \
                "แปลนคานหลังคา" if lvl == E["n"] else \
                f"แปลนคาน พื้นชั้น {lvl + 1}"
            add("S", title, lambda sh, _a, lvl=lvl: s_beams(sh, E, lvl))
        if L:
            add("S", "แปลนโครงหลังคา", lambda sh, _a: s_roof_frame(sh, E, L))
        add("S", "ตารางฐานราก เสา คาน พื้น",
            lambda sh, _a: s_schedules(sh, E), "-")
    if "SN" in groups:
        add("SN", "สารบัญแบบ สัญลักษณ์ รายการประกอบแบบสุขาภิบาล",
            lambda sh, all_: sn_index(sh, all_), "-")
        for k in floors:
            add("SN", f"แปลนระบบสุขาภิบาลชั้น {k + 1}",
                lambda sh, _a, k=k: sn_plan(sh, E, k))
    if "EE" in groups:
        add("EE", "สารบัญแบบ สัญลักษณ์ ตารางโหลด รายการประกอบแบบไฟฟ้า",
            lambda sh, all_: ee_index(sh, all_, E), "-")
        for k in floors:
            add("EE", f"แปลนระบบไฟฟ้าชั้น {k + 1}",
                lambda sh, _a, k=k: ee_plan(sh, E, k))
    if "M" in groups:
        for k in floors:
            add("M", f"แปลนระบบปรับอากาศและระบายอากาศชั้น {k + 1}",
                lambda sh, _a, k=k: m_plan(sh, E, k, None))
    sheets = [s for s, _f in plan]
    for i, s in enumerate(sheets, 1):
        s.number = i
    for s, fn in plan:
        fn(s, sheets)
        frame(s, info, len(sheets))
    if "BOQ" in groups:
        sheets += build_boq(data, info)
    return sheets


# ---------------------------------------------------------------------------
# ปร.4 — the bill of quantities at the end of the book
# ---------------------------------------------------------------------------

#: (header, sub-header, width mm, align)
BOQ_COLS = [("ลำดับที่", "", 16, "center"), ("รายการ", "", 134, "left"),
            ("จำนวน", "", 24, "right"), ("หน่วย", "", 18, "center"),
            ("ราคาวัสดุ", "ราคาหน่วยละ", 26, "right"),
            ("", "จำนวนเงิน", 32, "right"),
            ("ค่าแรงงาน", "ราคาหน่วยละ", 26, "right"),
            ("", "จำนวนเงิน", 32, "right"),
            ("รวมค่าวัสดุ", "และค่าแรงงาน", 34, "right"),
            ("หมายเหตุ", "", 44, "left")]
BOQ_ROW = 6.0
BOQ_DESC = 72                       # characters per line of รายการ


def _money(v, show=True) -> str:
    return f"{v:,.2f}" if show and v else ""


def boq_rows(result, show_prices=True):
    """The ปร.4 lines: (kind, cells) — kind "group" / "item" / "total";
    the summary first, as the department's book does."""
    groups = result.get("groups") or []
    summary = [("head", ["", "สรุปงาน"] + [""] * 8)]
    gm = gl = 0.0
    for gi, (_k, th, rows) in enumerate(groups, 1):
        m = sum(r["mat_total"] for r in rows)
        lab = sum(r["lab_total"] for r in rows)
        gm, gl = gm + m, gl + lab
        summary.append(("item", [str(gi), th, "", "รวม", "",
                                 _money(m, show_prices), "",
                                 _money(lab, show_prices),
                                 _money(m + lab, show_prices), ""]))
    summary.append(("total", ["", "รวมค่าวัสดุและค่าแรงงานเป็นเงินประมาณ", "",
                              "", "", _money(gm, show_prices), "",
                              _money(gl, show_prices),
                              _money(gm + gl, show_prices),
                              "ยังไม่รวม Factor F"]))
    body = []
    for gi, (_k, th, rows) in enumerate(groups, 1):
        body.append(("head", [str(gi), th] + [""] * 8))
        for li, ln in enumerate(rows, 1):
            note = (ln.get("note") or "")
            body.append(("item", [
                f"{gi}.{li}", ln["desc"], f"{ln['qty']:,.2f}", ln["unit"],
                _money(ln["mat"], show_prices),
                _money(ln["mat_total"], show_prices),
                _money(ln["lab"], show_prices),
                _money(ln["lab_total"], show_prices),
                _money(ln["total"], show_prices), note]))
        m = sum(r["mat_total"] for r in rows)
        lab = sum(r["lab_total"] for r in rows)
        body.append(("total", ["", f"รวมข้อ {gi} {th}", "", "", "",
                               _money(m, show_prices), "",
                               _money(lab, show_prices),
                               _money(m + lab, show_prices), ""]))
    return summary, body


def _boq_page(sh, info, result, page, pages):
    W, H = PAPER
    m = MARGIN
    sh.rect(m, m, W - m, H - m, "frame", 0.5)
    x0 = m + 5
    y = H - m - 7
    sh.text((W - m - 5, y), "แบบ ปร.4", 3.0, "right", "title", True)
    proj = info.get("project") or "อาคาร"
    sh.text((W / 2, y), f"รายการประมาณราคาค่าก่อสร้าง  {proj}", 3.6, "center",
            "title", True)
    y -= 6.5
    sh.text((x0, y), f"สถานที่ก่อสร้าง  {info.get('location') or '-'}", 2.6)
    sh.text((x0 + 150, y), f"แบบเลขที่  {info.get('drawing_no') or '-'}", 2.6)
    sh.text((x0 + 260, y), "รายการเลขที่  -", 2.6)
    y -= 5.5
    sh.text((x0, y), f"หน่วยงาน  {info.get('owner') or info.get('office') or '-'}",
            2.6)
    sh.text((x0 + 150, y), f"ประมาณราคาเมื่อวันที่  {info.get('date') or thai_date()}",
            2.6)
    y -= 5.5
    sh.text((x0, y), f"ประมาณการโดย  {info.get('preparer') or NAME}", 2.6)
    ref = result.get("price_ref") or ""
    if ref:
        sh.text((x0 + 150, y), ref, 2.4)
    sh.text((W - m - 5, y), "หน่วย : บาท", 2.6, "right")
    # two-row header
    y -= 3
    top = y
    x = x0
    h1, h2 = 6.0, 6.0
    sh.line((x0, top), (x0 + sum(c[2] for c in BOQ_COLS), top), "text", 0.35)
    for i, (a, b, w, _al) in enumerate(BOQ_COLS):
        if a and b:                                  # spans two columns
            span = w + BOQ_COLS[i + 1][2] if i + 1 < len(BOQ_COLS) and \
                not BOQ_COLS[i + 1][0] else w
            if a in ("ราคาวัสดุ", "ค่าแรงงาน"):
                sh.text((x + span / 2, top - h1 + 1.8), a, 2.4, "center",
                        "text", True)
                sh.line((x, top - h1), (x + span, top - h1), "text", 0.18)
                sh.text((x + w / 2, top - h1 - h2 + 1.8), b, 2.2, "center",
                        "text", True)
            else:
                sh.text((x + w / 2, top - h1 + 1.8), a, 2.4, "center", "text",
                        True)
                sh.text((x + w / 2, top - h1 - h2 + 1.8), b, 2.4, "center",
                        "text", True)
        elif b:
            sh.text((x + w / 2, top - h1 - h2 + 1.8), b, 2.2, "center",
                    "text", True)
        else:
            sh.text((x + w / 2, top - h1 - 1.2), a, 2.4, "center", "text",
                    True)
        x += w
    y = top - h1 - h2
    sh.line((x0, y), (x0 + sum(c[2] for c in BOQ_COLS), y), "text", 0.35)
    return top, y


def build_boq(data, info=None) -> list:
    """The ปร.4 pages (A3, same paper as the drawings) from the BOQ of
    :func:`core.wanic_quantities.compute`, summary first."""
    from core import wanic_quantities as Q
    info = dict(info or {})
    result = Q.compute(data)
    if not result.get("groups"):
        return []
    show = bool(info.get("boq_prices", True))
    summary, body = boq_rows(result, show)
    W, H = PAPER
    bottom = MARGIN + 30
    pages: list = []
    cur = None

    def new_page():
        sh = Sheet(f"ปร.4-{len(pages) + 1}", "รายการประมาณราคาค่าก่อสร้าง (ปร.4)",
                   "-", "BOQ")
        pages.append(sh)
        return sh

    def emit(rows):
        nonlocal cur
        cur = new_page()
        state = {"y": None, "top": None}
        state["top"], state["y"] = _boq_page(cur, info, result, 0, 0)
        tops = [state]
        for kind, cells in rows:
            desc = _wrap(cells[1], BOQ_DESC)
            note = _wrap(cells[9], 23) if cells[9] else [""]
            n = max(len(desc), len(note))
            hgt = BOQ_ROW + (n - 1) * 3.8
            if state["y"] - hgt < bottom:
                _close_table(cur, state)
                cur = new_page()
                state = {}
                state["top"], state["y"] = _boq_page(cur, info, result, 0, 0)
                tops.append(state)
            y = state["y"]
            x = MARGIN + 5
            bold = kind in ("head", "total")
            for ci, (_a, _b, w, al) in enumerate(BOQ_COLS):
                lines = desc if ci == 1 else note if ci == 9 else [cells[ci]]
                for li, t in enumerate(lines):
                    tx = x + 1.5 if al == "left" else x + w - 1.5 \
                        if al == "right" else x + w / 2
                    sh_al = "left" if al == "left" else al
                    cur.text((tx, y - 4.2 - li * 3.8), t,
                             2.0 if ci == 9 else 2.3, sh_al, "text",
                             bold and ci != 9)
                x += w
            state["y"] = y - hgt
            if kind == "total":
                cur.line((MARGIN + 5, state["y"]), (MARGIN + 5 + sum(
                    c[2] for c in BOQ_COLS), state["y"]), "text", 0.25)
        _close_table(cur, state)
        return state["y"]

    emit(summary)
    y = emit(body)
    last = pages[-1]
    # signatures under the last table
    sy = max(y - 10, MARGIN + 18)
    prep = info.get("preparer") or NAME
    role = info.get("preparer_role") or ROLE
    last.text((W - 120, sy), "ลงชื่อ ……………………………………… ผู้ประมาณราคา", 2.6)
    last.text((W - 98, sy - 5), f"({prep})", 2.6, "center")
    last.text((W - 98, sy - 10), role, 2.4, "center")
    for i, sh in enumerate(pages, 1):
        sh.number = i
        sh.text((W - MARGIN - 5, MARGIN - 4.5), f"แผ่นที่ {i} / {len(pages)}",
                2.2, "right", "title")
        sh.text((MARGIN + 1, MARGIN - 4.5), f"จัดทำด้วย WANICNSURVEY · {FULL}",
                1.8, "left", "title")
        sh.text((MARGIN + 5, MARGIN + 4), "หมายเหตุ: ปริมาณตามหลักเกณฑ์การคำนวณ"
                "ราคากลางงานก่อสร้าง พ.ศ. 2569 (เผื่อตามมาตรฐาน) ค่าแรงตามบัญชี ว480 · "
                "ราคารวมนี้ยังไม่คูณ Factor F (ดูแบบ ปร.5)", 2.0)
    return pages


def _close_table(sh, state):
    """Vertical rules of the table from its header to the last row."""
    x = MARGIN + 5
    top, y = state["top"], state["y"]
    for _a, _b, w, _al in BOQ_COLS:
        sh.line((x, top), (x, y), "text", 0.18)
        x += w
    sh.line((x, top), (x, y), "text", 0.18)
    sh.line((MARGIN + 5, y), (x, y), "text", 0.35)


def _set_scale(sh, sc):
    sh.scale = f"1:{sc}"


# ---------------------------------------------------------------------------
# DXF (R12 ASCII, Thai text in ANSI_874) — every sheet side by side
# ---------------------------------------------------------------------------

#: Fill layers that exist for the PDF's photograph only.
DXF_SKIP_FILLS = {"halo", "photo"}


def _dxf_layer(name):
    return name.upper()


_DXF_SUB = {"Ø": "%%c", "ø": "%%c", "±": "%%p", "°": "%%d", "×": "x",
            "½": "1/2", "¾": "3/4", "¼": "1/4", "—": "-", "–": "-", "·": "-",
            "…": "...", "²": "2", "“": '"', "”": '"', "’": "'", "ไม่น้อยกว่า ": ">=",
            "≤": "<=", "→": "->", "\n": " "}


def dxf_text(s: str) -> str:
    """Text a Thai (ANSI_874) DXF can hold: CAD codes for Ø ± °."""
    return "".join(_DXF_SUB.get(c, c) for c in str(s))


def dxf_bytes(sheets, gap=30.0) -> bytes:
    """All sheets in model space, left to right, in paper millimetres (one
    A3 frame each).  Thai text is written in the Thai Windows code page
    (``$DWGCODEPAGE ANSI_874``) which AutoCAD and most CADs read."""
    out = []
    w = out.append

    def code(c, v):
        w(f"{c}\n{v}\n")
    code(0, "SECTION")
    code(2, "HEADER")
    code(9, "$ACADVER")
    code(1, "AC1009")
    code(9, "$DWGCODEPAGE")
    code(3, "ANSI_874")
    code(9, "$INSUNITS")
    code(70, 4)
    code(9, "$EXTMIN")
    code(10, 0.0)
    code(20, 0.0)
    code(9, "$EXTMAX")
    code(10, len(sheets) * (PAPER[0] + gap))
    code(20, PAPER[1])
    code(0, "ENDSEC")
    code(0, "SECTION")
    code(2, "TABLES")
    code(0, "TABLE")
    code(2, "LTYPE")
    code(70, 2)
    code(0, "LTYPE")
    code(2, "CONTINUOUS")
    code(70, 0)
    code(3, "Solid line")
    code(72, 65)
    code(73, 0)
    code(40, 0.0)
    code(0, "LTYPE")
    code(2, "DASHED")
    code(70, 0)
    code(3, "__ __ __")
    code(72, 65)
    code(73, 2)
    code(40, 3.0)
    code(49, 2.0)
    code(49, -1.0)
    code(0, "ENDTAB")
    code(0, "TABLE")
    code(2, "LAYER")
    code(70, len(LAYERS))
    for name, color in LAYERS.items():
        code(0, "LAYER")
        code(2, _dxf_layer(name))
        code(70, 0)
        code(62, color)
        code(6, "CONTINUOUS")
    code(0, "ENDTAB")
    code(0, "TABLE")
    code(2, "STYLE")
    code(70, 1)
    code(0, "STYLE")
    code(2, "THAI")
    code(70, 0)
    code(40, 0.0)
    code(41, 0.8)
    code(50, 0.0)
    code(71, 0)
    code(42, 2.5)
    code(3, "tahoma.ttf")
    code(4, "")
    code(0, "ENDTAB")
    code(0, "ENDSEC")
    code(0, "SECTION")
    code(2, "ENTITIES")
    for i, sh in enumerate(sheets):
        ox = i * (PAPER[0] + gap)
        for it in sh.items:
            kind = it[0]
            if kind == "line":
                (x0, y0, x1, y1), layer, _w, dash = it[1], it[2], it[3], it[4]
                code(0, "LINE")
                code(8, _dxf_layer(layer))
                if dash:
                    code(6, "DASHED")
                code(10, round(x0 + ox, 4))
                code(20, round(y0, 4))
                code(11, round(x1 + ox, 4))
                code(21, round(y1, 4))
            elif kind == "poly":
                pts, layer, _w, closed, dash = it[1], it[2], it[3], it[4], it[5]
                code(0, "POLYLINE")
                code(8, _dxf_layer(layer))
                if dash:
                    code(6, "DASHED")
                code(66, 1)
                code(70, 1 if closed else 0)
                for x, y in pts:
                    code(0, "VERTEX")
                    code(8, _dxf_layer(layer))
                    code(10, round(x + ox, 4))
                    code(20, round(y, 4))
                code(0, "SEQEND")
            elif kind == "fill":
                pts, layer = it[1], it[2]
                # a CAD has no photograph under the lines: the dark plates
                # that keep labels readable on it, white fills and the grey
                # stand-in for the picture would only hide the drawing
                white = (len(it) > 4 and tuple(it[4]) == (255, 255, 255)) or it[3] >= 0.99
                if layer in DXF_SKIP_FILLS or white:
                    continue
                if len(pts) in (3, 4):
                    q = pts if len(pts) == 4 else pts + [pts[-1]]
                    code(0, "SOLID")
                    code(8, _dxf_layer(layer))
                    for j, (x, y) in zip((0, 1, 3, 2), q):
                        code(10 + j, round(x + ox, 4))
                        code(20 + j, round(y, 4))
            elif kind == "circle":
                (cx, cy, r), layer = it[1], it[2]
                code(0, "CIRCLE")
                code(8, _dxf_layer(layer))
                code(10, round(cx + ox, 4))
                code(20, round(cy, 4))
                code(40, round(r, 4))
            elif kind == "arc":
                (cx, cy, r, a0, a1), layer = it[1], it[2]
                code(0, "ARC")
                code(8, _dxf_layer(layer))
                code(10, round(cx + ox, 4))
                code(20, round(cy, 4))
                code(40, round(r, 4))
                code(50, round(a0, 3))
                code(51, round(a1, 3))
            elif kind == "text":
                (x, y), s, h, align, layer, _b, ang = it[1], it[2], it[3], \
                    it[4], it[5], it[6], it[7]
                code(0, "TEXT")
                code(8, _dxf_layer(layer))
                code(7, "THAI")
                code(10, round(x + ox, 4))
                code(20, round(y, 4))
                code(40, round(h, 3))
                code(1, dxf_text(s))
                if ang:
                    code(50, ang)
                if align in ("center", "right"):
                    code(72, 1 if align == "center" else 2)
                    code(11, round(x + ox, 4))
                    code(21, round(y, 4))
    code(0, "ENDSEC")
    code(0, "EOF")
    return "".join(out).encode("cp874", errors="replace")
