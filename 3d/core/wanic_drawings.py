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


#: wall types tagged on the plans (a triangle with the number)
WALL_TYPES = {
    1: "ผนังภายนอก ก่ออิฐมอญครึ่งแผ่น ฉาบปูนเรียบสองด้าน ทาสีภายนอก",
    2: "ผนังภายใน ก่ออิฐมอญครึ่งแผ่น ฉาบปูนเรียบสองด้าน ทาสีภายใน",
    3: "ผนังห้องน้ำ ก่ออิฐมอญครึ่งแผ่น ฉาบปูน บุกระเบื้องด้านใน สูงถึงฝ้า",
}


def wall_type(E, w) -> int:
    """1 exterior, 2 interior, 3 along a bathroom."""
    (x0, y0), (x1, y1) = w["p0"], w["p1"]
    L = math.hypot(x1 - x0, y1 - y0) or 1.0
    mx, my = (x0 + x1) / 2, (y0 + y1) / 2
    nx, ny = (y1 - y0) / L, -(x1 - x0) / L
    for k, rm in bathrooms(E):
        if k != w["floor"]:
            continue
        for sg in (-1, 1):
            px, py = mx + nx * 0.06 * sg, my + ny * 0.06 * sg
            if rm["x"] <= px <= rm["x"] + rm["w"] and rm["y"] <= py <= rm["y"] + rm["d"]:
                return 3
    return 1 if w["exterior"] else 2


def wall_tag(sh, p, n, r=2.6):
    """The wall-type triangle with its number."""
    h = r * 1.6
    sh.poly([(p[0] - r, p[1] - h / 3), (p[0] + r, p[1] - h / 3), (p[0], p[1] + h * 2 / 3)],
            "text", 0.25)
    sh.text((p[0], p[1] - h / 3 + 0.6), str(n), 2.0, "center", "text", bold=True)


def draw_wall_tags(sh, v, E, k, t):
    """One tag per wall long enough, off its face (outside for exterior
    walls), clear of the openings."""
    rooms = E["floors"][k]["rooms"]
    placed = opening_on_wall(E, k)
    used = []
    for w in (w for w in E["walls"] if w["floor"] == k):
        (x0, y0), (x1, y1) = w["p0"], w["p1"]
        L = w["L"]
        if L < 1.2:
            continue
        ux, uy = (x1 - x0) / L, (y1 - y0) / L
        cuts = sorted((s_ - el["w"] / 2, s_ + el["w"] / 2) for ww, s_, el in placed if ww is w)
        # the widest clear stretch of the wall
        best, a = (0.0, 0.0), 0.3
        for c0, c1 in cuts + [(L - 0.3, L)]:
            if c0 - a > best[1] - best[0]:
                best = (a, c0)
            a = max(a, c1)
        if best[1] - best[0] < 0.5:
            continue
        sm = (best[0] + best[1]) / 2
        no = outward(w, rooms) if w["exterior"] else (-uy, ux)
        d = t / 2 + (0.55 if w["exterior"] else 0.35)
        q = (x0 + ux * sm + no[0] * d, y0 + uy * sm + no[1] * d)
        if not w["exterior"] and any(
                kk == k and rm["x"] <= q[0] <= rm["x"] + rm["w"] and rm["y"] <= q[1] <= rm["y"] + rm["d"]
                for kk, rm in bathrooms(E)):
            # keep the bathroom clear: tag the wall from the other side
            q = (x0 + ux * sm - no[0] * d, y0 + uy * sm - no[1] * d)
        if any(math.hypot(q[0] - u[0], q[1] - u[1]) < 0.8 for u in used):
            continue
        used.append(q)
        wall_tag(sh, v(*q), wall_type(E, w))


def wall_legend(sh, x, y, E):
    """Key to the wall tags (only the types used)."""
    used = sorted({wall_type(E, w) for w in E["walls"]})
    sh.text((x, y), "สัญลักษณ์ผนัง", 2.4, "left", "text", bold=True)
    for i, n in enumerate(used):
        yy = y - 5.5 - i * 5.0
        wall_tag(sh, (x + 3, yy + 1.0), n, 2.0)
        sh.text((x + 7, yy), WALL_TYPES[n], 2.0, "left", "text")


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
        # by position only: two openings at the same place must not make
        # the sort compare their dicts
        cuts = sorted(((s_ - el["w"] / 2, s_ + el["w"] / 2, el)
                       for ww, s_, el in placed if ww is w), key=lambda c: (c[0], c[1]))
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
    if el["op"].get("swing") == "out":            # เปิดออกนอก
        inn = side
    leaves = max(1, int(spec.get("leaves") or 1))
    if spec.get("slide"):
        for off, (a, b) in ((t * 0.15, (c0, (c0 + c1) / 2 + 0.05)),
                            (-t * 0.15, ((c0 + c1) / 2 - 0.05, c1))):
            p = (p0[0] + u[0] * a + n[0] * off, p0[1] + u[1] * a + n[1] * off)
            q = (p0[0] + u[0] * b + n[0] * off, p0[1] + u[1] * b + n[1] * off)
            sh.line(v(*p), v(*q), "door", 0.35)
        return
    if leaves == 1:
        hinges = [(c1, -1)] if el["op"].get("hinge") == "right" else [(c0, 1)]
    else:
        hinges = [(c0, 1), (c1, -1)]
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
    symbols_legend(sh, x0 + 264, y1 - 6, min(60.0, x1 - x0 - 266))


def symbols_legend(sh, x, y, w=60.0):
    """สัญลักษณ์แบบ: each symbol drawn as it appears on the sheets, with
    what it means — dimensions, wall hatches, tags, section and detail
    marks, levels and grid lines."""
    sh.text((x, y), "สัญลักษณ์แบบ", 3.4, "left", "text", True)
    rh = 7.5
    sx, tx = x + 12, x + 25
    yy = y - 7
    sh.rect(x, yy - 16 * rh - 1, x + w, yy + 3.5, "text", 0.25)
    sh.line((x + 23.5, yy + 3.5), (x + 23.5, yy - 16 * rh - 1), "text", 0.18)

    def row(text):
        nonlocal yy
        sh.text((tx, yy - 0.8), text, 1.9)
        sh.line((x, yy - rh / 2 - 0.5), (x + w, yy - rh / 2 - 0.5), "text", 0.1)
        yy -= rh

    def dim(kind):
        a, b = sx - 9, sx + 9
        sh.line((a, yy), (b, yy), "dim", 0.13)
        for t in (a, b):
            if kind == "arrow":
                sh.poly([(t, yy), (t + (1.6 if t == a else -1.6), yy + 0.6),
                         (t + (1.6 if t == a else -1.6), yy - 0.6)], "dim", 0.13)
            elif kind == "tick":
                sh.line((t - 0.8, yy - 0.8), (t + 0.8, yy + 0.8), "dim", 0.25)
            else:
                sh.circle((t, yy), 0.5, "dim", 0.13)
            sh.line((t, yy - 1.4), (t, yy + 1.4), "dim", 0.13)
        sh.text((sx, yy + 0.8), "2.00", 1.6, "center", "dim")
    dim("arrow")
    row("ระยะ ริม – ริม")
    dim("tick")
    row("ระยะ ริม – ศูนย์กลาง")
    dim("dot")
    row("ระยะ ศูนย์กลาง – ศูนย์กลาง")
    sh.line((sx - 9, yy - 1), (sx - 5, yy + 1.2), "text", 0.13)
    sh.line((sx - 5, yy + 1.2), (sx + 9, yy + 1.2), "text", 0.13)
    sh.text((sx + 2, yy + 1.6), "ระบุ", 1.6, "center")
    row("เส้นชี้แสดงรายละเอียด")
    for kind, text in (("brick", "ผนังก่ออิฐฉาบปูน"), ("conc", "ผนัง/โครงสร้าง ค.ส.ล."),
                       ("light", "ผนังโครงเบา (ยิปซัม/ไฟเบอร์ซีเมนต์)"), ("soil", "รูปตัดดิน")):
        a, b = sx - 9, sx + 9
        if kind == "soil":
            sh.line((a, yy - 1), (b, yy - 1), "cut", 0.35)
            for i in range(9):
                sh.line((a + i * 2, yy - 1), (a + i * 2 + 1.5, yy + 1), "hatch", 0.13)
        else:
            sh.rect(a, yy - 1.2, b, yy + 1.2, "wall", 0.3)
            if kind == "brick":
                for i in range(1, 6):
                    sh.line((a + i * 3, yy - 1.2), (a + i * 3, yy + 1.2), "hatch", 0.13)
            elif kind == "conc":
                sh.fill([(a, yy - 1.2), (b, yy - 1.2), (b, yy + 1.2), (a, yy + 1.2)], "hatch", 0.55)
            else:
                sh.line((a, yy), (b, yy), "hatch", 0.13, True)
        row(text)
    # room tag
    sh.rect(sx - 8, yy - 2.2, sx + 8, yy + 2.2, "text", 0.18)
    sh.text((sx, yy + 0.3), "ชื่อห้อง", 1.6, "center", "text", True)
    sh.text((sx, yy - 1.9), "พ1  ฝ1  ±0.00", 1.3, "center")
    row("ชื่อห้อง วัสดุพื้น ฝ้า ระดับพื้น")
    sh.text((sx, yy - 0.8), "ป1", 2.4, "center", "door")
    row("หมายเลขประตู (ตารางประตู)")
    sh.circle((sx, yy), 2.4, "window", 0.18)
    sh.text((sx, yy - 0.9), "น1", 2.0, "center", "window")
    row("หมายเลขหน้าต่าง (ตารางหน้าต่าง)")
    wall_tag(sh, (sx, yy), 1, 2.2)
    row("หมายเลขชนิดผนัง (ตามสัญลักษณ์ผนัง)")
    # section mark
    sh.circle((sx - 5, yy), 2.6, "text", 0.25)
    sh.line((sx - 7.6, yy), (sx - 2.4, yy), "text", 0.18)
    sh.text((sx - 5, yy + 0.4), "ก", 1.6, "center")
    sh.text((sx - 5, yy - 2.0), "A-08", 1.2, "center")
    sh.line((sx - 2.4, yy), (sx + 8, yy), "text", 0.35, True)
    row("แนวตัด (รูปตัด / เลขแผ่น)")
    sh.circle((sx, yy), 2.8, "text", 0.25)
    sh.line((sx - 2.8, yy), (sx + 2.8, yy), "text", 0.18)
    sh.text((sx, yy + 0.5), "1", 1.6, "center")
    sh.text((sx, yy - 2.0), "S-09", 1.2, "center")
    row("แบบขยาย (เลข / แผ่นที่)")
    sh.poly([(sx - 1.5, yy + 1.5), (sx + 1.5, yy + 1.5), (sx, yy)], "dim", 0.18)
    sh.line((sx - 5, yy), (sx + 8, yy), "dim", 0.13)
    sh.text((sx + 3, yy + 0.6), "+0.00", 1.5)
    row("ระดับ (อ้างอิง ±0.00 = พื้นชั้น 1)")
    sh.circle((sx, yy), 2.6, "grid", 0.25)
    sh.text((sx, yy - 0.9), "A", 2.2, "center", "grid")
    row("แนวเสา (กริดไลน์)")
    yy -= 2
    sh.text((x, yy - 1), "หมายเหตุ: ใช้ตัวเลขที่เขียนกำกับ ห้ามวัดจากแบบ", 1.8)


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
    section_marks(sh, v, E, k)
    draw_wall_tags(sh, v, E, k, t)
    x0, y0, x1, y1 = drawing_area()
    north(sh, (x1 - 10, y1 - 12))
    wall_legend(sh, x0 + 4, y0 + 30, E)
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
        for a, b in L.get("valleys") or []:           # ตะเข้ราง
            sh.line(v(a[0], a[1]), v(b[0], b[1]), "roof", 0.5, True)
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
    lm = 30.0                       # room on the left for the wall note
    bw, bh = box[2] - box[0] - 40 - lm, box[3] - box[1] - 40
    sc = fit_scale((umax - umin, ztop - zmin), (bw, bh), PLAN_SCALES)
    sh.scale = f"1:{sc}"
    k = 1000.0 / sc
    ox = box[0] + 4 + lm + (bw - (umax - umin) * k) / 2
    oy = box[1] + 28 + max(0.0, (bh - (ztop - zmin) * k) / 2)

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
    # ground, columns at the corners of the faces, glazing bars
    for i in range(int((umax - umin) / 0.6)):
        uu = umin + 0.3 + i * 0.6
        sh.line(P(uu, 0), P(uu - 0.25, -0.25), "hatch", 0.13)
    for el in E["openings"]:
        if el["type"] != "window":
            continue
        ox_, oy_ = float(el["op"]["x"]), float(el["op"]["y"])
        rooms = E["floors"][el["floor"]]["rooms"]
        if not any(abs(outward(w, rooms)[0] - nx) < 1e-6 and abs(outward(w, rooms)[1] - ny) < 1e-6
                   and w["floor"] == el["floor"] and any(o is el["op"] for o in w["openings"])
                   for w in E["walls"] if w["exterior"]):
            continue
        uc = u_of(ox_, oy_)
        lo = el["floor"] * H + el["sill"]
        sh.line(P(uc - el["w"] / 2, lo + el["h"] * 0.5), P(uc + el["w"] / 2, lo + el["h"] * 0.5),
                "window", 0.1)
    # levels: floors, ceilings, the ring beam and the ridge
    marks = [(0.0, "ระดับพื้นชั้น 1")]
    for f in range(n):
        if f:
            marks.append((f * H, f"ระดับพื้นชั้น {f + 1}"))
    marks.append((n * H, "ระดับหลังคาน"))
    if L and L.get("skin"):
        marks.append((max(p[2] for poly in L["skin"] for p in poly), "ระดับสันหลังคา"))
    _levels(sh, P, umax - 0.2, marks)
    # notes
    if L:
        tile = CAT.roof_tile(E["settings"])[1]["name"]
        top = max(p[2] for poly in L["skin"] for p in poly) if L.get("skin") else n * H
        sh.text(P((umin + umax) / 2, top + 0.45), f"หลังคา{tile[:38]}", 2.0, "center", "text")
    # the wall note outside the building, its leader to the wall face
    wall_u = [u for f in range(n) for w in _ext_walls(E, f, side)
              for u in (u_of(*w["p0"]), u_of(*w["p1"]))]
    if wall_u:
        wl = min(wall_u)
        tip = P(wl + 0.25, H * 0.35)
        lab = (min(P(umin, 0)[0], P(wl, 0)[0] - 4), P(0, H * 0.80)[1])
        sh.line(tip, (lab[0], lab[1] - 1.2), "text", 0.13)
        sh.circle(tip, 0.5, "text", 0.18)
        sh.line((lab[0] - 28, lab[1] - 1.2), (lab[0], lab[1] - 1.2), "text", 0.13)
        sh.text((lab[0] - 28, lab[1]), "ผนังก่ออิฐฉาบปูนเรียบ ทาสี", 1.9, "left", "text")
    # heights of the doors and windows: sill and head off the floor, a
    # chain on the left of each opening
    done_dims = set()
    for f in range(n):
        for w in _ext_walls(E, f, side):
            for op in w["openings"]:
                el = next((o for o in E["openings"] if o["op"] is op), None)
                if el is None:
                    continue
                uc = u_of(float(op["x"]), float(op["y"]))
                key = (round(uc, 2), f)
                if key in done_dims:
                    continue
                done_dims.add(key)
                du = uc - el["w"] / 2 - 0.25
                z0 = f * H
                chain = [z0] + ([z0 + el["sill"]] if el["sill"] > 0.01 else []) + \
                    [z0 + el["sill"] + el["h"]]
                for za, zb in zip(chain, chain[1:]):
                    a_, b_ = P(du, za), P(du, zb)
                    sh.line(a_, b_, "dim", 0.13)
                    for q in (a_, b_):
                        sh.line((q[0] - 0.7, q[1] - 0.7), (q[0] + 0.7, q[1] + 0.7), "dim", 0.25)
                        sh.line((q[0] - 0.4, q[1]), (q[0] + 1.6, q[1]), "dim", 0.13)
                    sh.text((a_[0] - 0.7, (a_[1] + b_[1]) / 2), f"{zb - za:.2f}", 1.6,
                            "center", "dim", angle=90)
    # grid bubbles under the face
    xs_, ys_ = grids(E)
    names = [(x, str(i + 1)) for i, x in enumerate(xs_)] if ax[1] == 0 else \
        [(y, axis_name(i)) for i, y in enumerate(ys_)]
    for g, nm in names:
        q = P(g * (ax[0] or ax[1]), 0)
        sh.line((q[0], q[1] - 1), (q[0], q[1] - 5), "grid", 0.13, True)
        sh.circle((q[0], q[1] - 8), 3.0, "grid", 0.25)
        sh.text((q[0], q[1] - 9.2), nm, 2.6, "center", "grid")
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


# ---------------------------------------------------------------------------
# Building sections in detail (รูปตัดอาคาร) — X and Y, one through a bathroom
# ---------------------------------------------------------------------------

THAI_CUTS = ["ก", "ข", "ค", "ง", "จ", "ฉ", "ช", "ซ", "ฌ", "ญ"]


def section_cuts(E, k):
    """The two cuts for floor ``k``: ``[(axis, at, name, through)]`` — one
    across the building through a bathroom (or the largest room when there
    is none), the other the other way through the middle of the plan.
    ``axis`` "x": the plane x = at (seen along +x); "y": y = at."""
    rooms = E["floors"][k]["rooms"]
    if not rooms:
        return []
    wet = [r for r in rooms if B.is_wet(r)]
    first = (wet or sorted(rooms, key=lambda r: -float(r["w"]) * float(r["d"])))[0]
    xs = [float(r["x"]) for r in rooms] + [float(r["x"]) + float(r["w"]) for r in rooms]
    ys = [float(r["y"]) for r in rooms] + [float(r["y"]) + float(r["d"]) for r in rooms]
    w, d = max(xs) - min(xs), max(ys) - min(ys)
    # the long section runs along the long side: cut across it
    ax1 = "x" if w >= d else "y"
    at1 = float(first["x"]) + float(first["w"]) / 2 if ax1 == "x" else \
        float(first["y"]) + float(first["d"]) / 2
    ax2 = "y" if ax1 == "x" else "x"
    mid = (min(ys) + max(ys)) / 2 if ax2 == "y" else (min(xs) + max(xs)) / 2
    # through a room, not along a wall line
    cand = []
    for r in rooms:
        lo, hi = (float(r["y"]), float(r["y"]) + float(r["d"])) if ax2 == "y" else \
            (float(r["x"]), float(r["x"]) + float(r["w"]))
        cand.append(((lo + hi) / 2, r))
    at2, r2 = min(cand, key=lambda c: abs(c[0] - mid))
    a, b = THAI_CUTS[(2 * k) % 10], THAI_CUTS[(2 * k + 1) % 10]
    return [(ax1, at1, f"{a}-{a}", first.get("name") or "ห้อง"),
            (ax2, at2, f"{b}-{b}", r2.get("name") or "ห้อง")]


def _level(sh, p, z, label, left=True, ty=None):
    """A level mark ▽ +0.00 ระดับ… (``ty``: the text's own height when
    marks close together are stacked apart)."""
    x, y = p
    sh.poly([(x, y), (x - 1.6, y + 2.4), (x + 1.6, y + 2.4)], "dim", 0.18)
    sh.line((x - 12 if left else x - 3, y), (x + 3 if left else x + 12, y), "dim", 0.13)
    t = f"{'±' if abs(z) < 1e-6 else ('+' if z > 0 else '')}{z:.2f}"
    yt = y + 0.8 if ty is None else ty
    if left:
        # the words to the left of the mark, clear of the building
        if ty is not None and abs(ty - (y + 0.8)) > 0.3:
            sh.line((x - 12, y), (x - 13.5, yt - 0.6), "dim", 0.1)
        sh.text((x - 14 if ty is not None and abs(ty - (y + 0.8)) > 0.3 else x - 12.5, yt),
                f"{t} {label}", 2.0, "right", "dim")
        return
    if ty is not None and abs(ty - (y + 0.8)) > 0.3:
        sh.line((x + 1.6, y + 2.4), (x + 2.4, yt), "dim", 0.1)
    sh.text((x + 2.5, yt), f"{t} {label}", 2.0, "left", "dim")


def _levels(sh, P, u, marks, left=False):
    """Level marks at ``u``, their labels kept 3.4 mm apart."""
    last = None
    for z, label in sorted(set(marks)):
        p = P(u, z)
        ty = p[1] + 0.8
        if last is not None and ty < last + 3.4:
            ty = last + 3.4
        _level(sh, p, z, label, left=left, ty=ty)
        last = ty


def section_detail(sh, E, L, cut, box):
    """One building section drawn in detail: footings, ground beams,
    slabs, cut walls (masonry hatched, plaster), cut beams, the doors and
    windows and columns beyond, ceilings, the roof frame (ties, posts,
    rafters, purlins cut), the skin, fascia, level marks, dimension
    strings and grid bubbles, room names."""
    axis, at, name, _through = cut
    H, n, lib, s = E["H"], E["n"], E["lib"], E["settings"]
    xs, ys = grids(E)
    if not xs:
        return 100

    def U(x, y):                         # plan → section abscissa
        return y if axis == "x" else x

    def C(x, y):                         # plan → distance across the plane
        return x if axis == "x" else y
    grid_u = ys if axis == "x" else xs
    ov = float(s.get("overhang") or 0)
    umin, umax = grid_u[0] - ov - 1.2, grid_u[-1] + ov + 1.2
    lab_mm = 42.0                        # room for the level words on the left
    ridge = max((p[2] for poly in (L or {}).get("skin", []) for p in poly), default=n * H + 1)
    zmin, ztop = -1.8, ridge + 0.8
    bw, bh = box[2] - box[0] - 40 - lab_mm, box[3] - box[1] - 26
    sc = fit_scale((umax - umin, ztop - zmin), (bw, bh), (50, 75, 100, 125, 150, 200))
    k = 1000.0 / sc
    ox = box[0] + 28 + lab_mm + (bw - (umax - umin) * k) / 2
    oy = box[1] + 22

    def P(u, z):
        return (ox + (u - umin) * k, oy + (z - zmin) * k)

    def rect(u0, z0, u1, z1, layer="cut", w=0.35, fill=None):
        pts = [P(u0, z0), P(u1, z0), P(u1, z1), P(u0, z1)]
        if fill is not None:
            sh.fill(pts, "hatch", fill)
        sh.poly(pts, layer, w)
    # ground and earth hatch
    gl = -0.30
    sh.line(P(umin, gl), P(umax, gl), "cut", 0.5)
    for i in range(int((umax - umin) / 0.6)):
        u = umin + 0.3 + i * 0.6
        sh.line(P(u, gl), P(u - 0.25, gl - 0.25), "hatch", 0.13)
    # footings, stumps on the cut line (within half a footing)
    for ft in E["footings"]:
        spec = lib.get(ft["mark"], {})
        w_ = float(spec.get("w", 1.0))
        if abs(C(ft["x"], ft["y"]) - at) > w_ / 2 + 1e-6:
            continue
        u = U(ft["x"], ft["y"])
        rect(u - w_ / 2, ft["z0"], u + w_ / 2, ft["z1"], fill=0.75)
        rect(u - w_ / 2 - 0.05, ft["z0"] - 0.10, u + w_ / 2 + 0.05, ft["z0"], "hatch", 0.13)
    for st in E["stumps"]:
        if abs(C(st["x"], st["y"]) - at) > 0.6:
            continue
        b_ = float(lib.get(st["mark"], {}).get("b", 0.2))
        u = U(st["x"], st["y"])
        rect(u - b_ / 2, st["z0"], u + b_ / 2, st["z1"] - 0.4, "cut", 0.3)
    # slabs crossed by the plane
    for sl in E["slabs"]:
        rm = sl["room"]
        lo, hi = (rm["x"], rm["x"] + rm["w"]) if axis == "x" else (rm["y"], rm["y"] + rm["d"])
        if not (lo - 1e-6 <= at <= hi + 1e-6):
            continue
        a, b = (rm["y"], rm["y"] + rm["d"]) if axis == "x" else (rm["x"], rm["x"] + rm["w"])
        t = float(lib.get(sl["mark"], {}).get("t", 0.1))
        top = sl["z"] - sl.get("drop", 0.0)
        rect(float(a), top - t, float(b), top, fill=0.70)
    # beams cut (running across the plane) and beams beyond (along it)
    for bm in E["beams"]:
        (x0_, y0_), (x1_, y1_) = bm["p0"], bm["p1"]
        spec = lib.get(bm["mark"], {})
        b_, h_ = float(spec.get("b", 0.2)), float(spec.get("h", 0.4))
        if axis == "x":
            cross = abs(y0_ - y1_) < 1e-6 and min(x0_, x1_) - 1e-6 <= at <= max(x0_, x1_) + 1e-6
        else:
            cross = abs(x0_ - x1_) < 1e-6 and min(y0_, y1_) - 1e-6 <= at <= max(y0_, y1_) + 1e-6
        if cross:
            u = U(x0_, y0_)
            rect(u - b_ / 2, bm["z"] - h_, u + b_ / 2, bm["z"], fill=0.70)
    # columns beyond: the grid line just past the cut
    beyond = [g for g in (xs if axis == "x" else ys) if g > at + 1e-6]
    nxt = beyond[0] if beyond else None
    if nxt is not None:
        for c in E["columns"]:
            if abs(C(c["x"], c["y"]) - nxt) > 1e-6:
                continue
            b_ = float(lib.get(c["mark"], {}).get("b", 0.2))
            u = U(c["x"], c["y"])
            rect(u - b_ / 2, c["z0"], u + b_ / 2, c["z1"] - 0.4, "hidden", 0.18)
        for ft in E["footings"]:                 # footings beyond, dashed
            if abs(C(ft["x"], ft["y"]) - nxt) > 1e-6:
                continue
            spec = lib.get(ft["mark"], {})
            w_ = float(spec.get("w", 1.0))
            u = U(ft["x"], ft["y"])
            pts = [P(u - w_ / 2, ft["z0"]), P(u + w_ / 2, ft["z0"]),
                   P(u + w_ / 2, ft["z1"]), P(u - w_ / 2, ft["z1"])]
            sh.poly(pts, "hidden", 0.18, True, True)
            sh.poly([P(u - 0.1, ft["z1"]), P(u + 0.1, ft["z1"]), P(u + 0.1, 0.0),
                     P(u - 0.1, 0.0)], "hidden", 0.18, True, True)
    # walls cut: masonry hatched between the plaster faces; an opening on
    # the plane leaves the wall below the sill and above the head
    for wl in E["walls"]:
        (x0_, y0_), (x1_, y1_) = wl["p0"], wl["p1"]
        if axis == "x":
            cross = abs(y0_ - y1_) < 1e-6 and min(x0_, x1_) < at < max(x0_, x1_)
        else:
            cross = abs(x0_ - x1_) < 1e-6 and min(y0_, y1_) < at < max(y0_, y1_)
        if not cross:
            continue
        sp = B.wall_spec(s, bool(wl["exterior"]))
        off = B.wall_offset(E, wl)
        ox_, oy_ = wl.get("out") or (0.0, 0.0)
        u = U(x0_ + ox_ * off, y0_ + oy_ * off)
        z0 = wl["floor"] * H
        wh = H - float(lib[wl["beam"]]["h"])
        segs = [(z0, z0 + wh)]
        for op in wl["openings"]:
            ow, oh, sill = B.opening_size(op, s)
            oc = C(float(op["x"]), float(op["y"]))
            if abs(oc - at) <= ow / 2:
                lo_ = z0 + (0.0 if op.get("type") != "window" else sill)
                segs = [(z0, lo_), (lo_ + oh, z0 + wh)]
                # the frame in section
                rect(u - 0.05, lo_, u + 0.05, lo_ + oh, "window", 0.25)
                if op.get("type") == "window":
                    sh.line(P(u, lo_), P(u, lo_ + oh), "window", 0.18)
        T = sp["t"] / 2
        for a_, b_ in segs:
            if b_ - a_ < 0.01:
                continue
            rect(u - T, a_, u + T, b_, "cut", 0.5, 0.88)
            for d_ in (-T - sp["pi"], T + sp["po"]):
                sh.line(P(u + d_, a_), P(u + d_, b_), "cut", 0.18)
    # rooms crossed: name, the doors / windows on the far wall, the ceiling
    for sl in E["slabs"]:
        rm, kf = sl["room"], sl["floor"]
        lo, hi = (rm["x"], rm["x"] + rm["w"]) if axis == "x" else (rm["y"], rm["y"] + rm["d"])
        if not (lo < at < hi):
            continue
        a, b = (float(rm["y"]), float(rm["y"]) + float(rm["d"])) if axis == "x" else \
            (float(rm["x"]), float(rm["x"]) + float(rm["w"]))
        z = kf * H
        far = float(hi)
        for el in E["openings"]:
            if el["floor"] != kf:
                continue
            ox_, oy_ = float(el["op"]["x"]), float(el["op"]["y"])
            if abs(C(ox_, oy_) - far) > 0.06 or not (a < U(ox_, oy_) < b):
                continue
            uc = U(ox_, oy_)
            lo_ = z + (el["sill"] if el["type"] == "window" else 0.0)
            rect(uc - el["w"] / 2, lo_, uc + el["w"] / 2, lo_ + el["h"],
                 "window" if el["type"] == "window" else "door", 0.18)
            if el["type"] == "window":
                sh.line(P(uc, lo_), P(uc, lo_ + el["h"]), "window", 0.13)
        zc = B.ceiling_z(E, kf)
        if B.ceiling_type(s, rm) != "none":
            x0r, y0r, x1r, y1r = B.room_inner(E, rm, kf)
            ua, ub = (y0r, y1r) if axis == "x" else (x0r, x1r)
            rect(ua, zc - 0.009, ub, zc, "cut", 0.25)
            sh.text(P((ua + ub) / 2, zc - 0.25), f"ฝ้า +{zc - z:.2f}", 1.9, "center", "dim")
        sh.text(P((a + b) / 2, z + 1.25), rm.get("name") or "ห้อง", 2.6, "center", "text", True)
        if B.is_wet(rm):
            sh.text(P((a + b) / 2, z + 0.95), f"พื้นต่ำ {float(s.get('wet_drop') or 0) * 100:.0f} ซม.",
                    1.8, "center", "dim")
    # roof: the skin cut, the frame beyond (rafters, ties, posts), the
    # purlins and the wall plates cut
    if L:
        for poly in L["skin"]:
            seg = _cut_poly(poly, axis, at)
            if seg:
                (ua, za), (ub, zb) = seg
                sh.line(P(ua, za + 0.10), P(ub, zb + 0.10), "roof", 0.7)
                sh.line(P(ua, za), P(ub, zb), "roof", 0.25)
        depth = 1.25
        for key, lay, w_ in (("rafter", "roof", 0.18), ("tie", "struct", 0.25),
                             ("rbeam", "struct", 0.25), ("post", "struct", 0.25),
                             ("ridge", "struct", 0.25), ("hip", "roof", 0.18)):
            for a_, b_ in L.get(key) or []:
                ca, cb = C(a_[0], a_[1]), C(b_[0], b_[1])
                if not (at - 1e-6 <= min(ca, cb) and max(ca, cb) <= at + depth):
                    continue
                if abs(ca - cb) > 1e-6 and key in ("rafter", "tie", "rbeam", "ridge"):
                    continue                         # runs across: cut, below
                sh.line(P(U(a_[0], a_[1]), a_[2]), P(U(b_[0], b_[1]), b_[2]), lay, w_)
        for key in ("tie", "rbeam", "ridge", "plate"):
            for a_, b_ in L.get(key) or []:
                ca, cb = C(a_[0], a_[1]), C(b_[0], b_[1])
                if min(ca, cb) - 1e-6 <= at <= max(ca, cb) + 1e-6 and abs(ca - cb) > 1e-6:
                    u = U(a_[0], a_[1])
                    rect(u - 0.03, a_[2] - 0.15, u + 0.03, a_[2], "struct", 0.25, 0.5)
        for pl in L.get("purlin") or []:
            a_, b_ = pl["path"][0], pl["path"][-1]
            ca, cb = C(a_[0], a_[1]), C(b_[0], b_[1])
            if min(ca, cb) - 1e-6 <= at <= max(ca, cb) + 1e-6 and abs(ca - cb) > 1e-6:
                u = U(a_[0], a_[1])
                rect(u - 0.022, a_[2], u + 0.022, a_[2] + 0.075, "struct", 0.13)
        for e_ in L.get("eave") or []:
            a_, b_ = e_
            ca, cb = C(a_[0], a_[1]), C(b_[0], b_[1])
            if min(ca, cb) - 1e-6 <= at <= max(ca, cb) + 1e-6:
                u = U(a_[0], a_[1])
                rect(u - 0.0125, a_[2] - 0.20, u + 0.0125, a_[2], "cut", 0.35, 0.6)
    # levels on the left
    xl = umin + 0.2
    marks = [(gl, "ระดับดินเดิม"), (0.0, "ระดับพื้นชั้น 1")]
    for f in range(n):
        marks.append((B.ceiling_z(E, f), f"ระดับฝ้าชั้น {f + 1}"))
        if f > 0:
            marks.append((f * H, f"ระดับพื้นชั้น {f + 1}"))
    marks.append((n * H, "ระดับหลังคาน"))
    if L:
        marks.append((ridge, "ระดับสันหลังคา"))
    _levels(sh, P, xl, marks, left=True)
    # vertical dimensions on the right
    xr = P(umax - 0.3, 0)[0]
    zs = sorted({0.0} | {B.ceiling_z(E, f) for f in range(n)} | {f * H for f in range(n + 1)}
                | ({ridge} if L else set()))
    for za, zb in zip(zs, zs[1:]):
        pa, pb = (xr, P(0, za)[1]), (xr, P(0, zb)[1])
        sh.line(pa, pb, "dim", 0.13)
        for q in (pa, pb):
            sh.line((q[0] - 1, q[1] - 1), (q[0] + 1, q[1] + 1), "dim", 0.18)
        sh.text((xr + 1.5, (pa[1] + pb[1]) / 2 - 1), f"{zb - za:.2f}", 2.0, "left", "dim")
    if L:
        roof_leaders(sh, E, L, P, U, C, axis, at, xr + 12)
    # grid: dimension chain and bubbles below
    yb = P(0, zmin + 0.35)[1]
    for g0, g1 in zip(grid_u, grid_u[1:]):
        a_, b_ = P(g0, 0)[0], P(g1, 0)[0]
        sh.line((a_, yb + 6), (b_, yb + 6), "dim", 0.13)
        for q in (a_, b_):
            sh.line((q - 1, yb + 5), (q + 1, yb + 7), "dim", 0.18)
        sh.text(((a_ + b_) / 2, yb + 7), f"{g1 - g0:.2f}", 2.0, "center", "dim")
    names = [str(i + 1) for i in range(len(xs))] if axis == "y" else \
        [axis_name(i) for i in range(len(ys))]
    for g, nm in zip(grid_u, names):
        q = P(g, 0)[0]
        sh.line((q, yb + 3.5), (q, P(0, gl)[1]), "grid", 0.13, True)
        sh.circle((q, yb), 3.0, "grid", 0.25)
        sh.text((q, yb - 1.2), nm, 2.6, "center", "grid")
    return sc


def roof_leaders(sh, E, L, P, U, C, axis, at, lx):
    """Name the roof's parts on a section, each with a leader to a label
    column at paper x ``lx`` (as the standard sets do), and mark the
    pitch with its slope symbol."""
    s = E["settings"]
    segs = [sg for sg in (_cut_poly(poly, axis, at) for poly in L["skin"]) if sg]
    segs = [((ua, za), (ub, zb)) for (ua, za), (ub, zb) in segs if abs(ub - ua) > 0.3]
    if not segs:
        return
    # the slope on the right (falling to the right); else the longest
    right = [sg for sg in segs if (sg[1][1] - sg[0][1]) * (sg[1][0] - sg[0][0]) < 0] or segs
    (ua, za), (ub, zb) = max(right, key=lambda sg: max(sg[0][0], sg[1][0]))
    if ua > ub:
        (ua, za), (ub, zb) = (ub, zb), (ua, za)

    def on(t, dz=0.0):
        return P(ua + (ub - ua) * t, za + (zb - za) * t + dz)
    hi = (ua, za) if za > zb else (ub, zb)
    lo = (ub, zb) if za > zb else (ua, za)
    tile = CAT.roof_tile(s)[1]["name"]
    st = lambda k_, d_="": str(s.get(k_) or d_)        # noqa: E731
    items = [(P(hi[0], hi[1] + 0.16), "ครอบสันหลังคา"),
             (on(0.35, 0.10), f"หลังคา{tile[:26]}"),
             (on(0.50, 0.04), f"แปเหล็ก {st('purlin')}"),
             (on(0.65, -0.05), f"จันทันเหล็ก {st('rafter')}"),
             (P(hi[0], hi[1] - 0.10), f"อกไก่เหล็ก {st('ridge')}")]
    if L.get("post"):
        items.append((P(hi[0], (hi[1] + E["n"] * E["H"]) / 2), f"ดั้งเหล็ก {st('post')}"))
    if s.get("wall_plate", True):
        items.append((P(lo[0] - math.copysign(float(s.get('overhang') or 0.6), lo[0] - hi[0]),
                        E["n"] * E["H"] + 0.05), f"อะเสเหล็ก {st('wallplate')}"))
    items.append((P(lo[0], lo[1] - 0.10), "เชิงชายไม้สังเคราะห์ 1×8\" · ฝ้าชายคา"))
    items.sort(key=lambda it: -it[0][1])
    ytop = items[0][0][1] + 4
    for i, (pt, text) in enumerate(items):
        ty = ytop - i * 4.2
        sh.circle(pt, 0.35, "text", 0.18)
        sh.line(pt, (lx - 1, ty + 0.7), "text", 0.13)
        sh.line((lx - 1, ty + 0.7), (lx + 1, ty + 0.7), "text", 0.13)
        sh.text((lx + 1.5, ty), text, 1.9, "left", "text")
    # the slope symbol: a small triangle under the right slope with its angle
    m = on(0.5, 0.45)
    run = 6.0
    k_ = abs((zb - za) / (ub - ua)) if ub != ua else 0
    rise = run * k_
    sgn = -1 if zb < za else 1
    a_ = (m[0] - run / 2, m[1])
    b_ = (m[0] + run / 2, m[1])
    c_ = (b_[0], m[1] + sgn * rise) if sgn > 0 else (a_[0], m[1] + rise)
    sh.poly([a_, b_, c_], "dim", 0.18)
    sh.text((m[0], m[1] + rise + 1.2), f"ลาดเอียง {float(s['pitch']):g}°", 1.9, "center", "dim")


def a_section_sheet(sh, E, L, k):
    """Floor ``k``'s pair of sections, stacked as in the standard sets."""
    x0, y0, x1, y1 = drawing_area()
    cuts = section_cuts(E, k)
    midy = (y0 + y1) / 2
    scales = []
    for i, cut in enumerate(cuts):
        box = (x0, midy + 2, x1, y1) if i == 0 else (x0, y0, x1, midy - 2)
        sc = section_detail(sh, E, L, cut, box)
        scales.append(sc)
        note = f" (ตัดผ่าน{cut[3]})" if i == 0 else ""
        caption(sh, (x0 + 60, box[1] + 8), f"รูปตัด {cut[2]}{note}", f"1:{sc}")
    if len(cuts) == 2:
        sh.line((x0, midy), (x1, midy), "frame", 0.25)
    sh.scale = f"1:{max(scales)}" if scales else "-"
    return max(scales) if scales else 100


def section_marks(sh, v, E, k):
    """The cut lines of floor ``k``'s sections on its plan, with arrows."""
    xs, ys = grids(E)
    if not xs:
        return
    for axis, at, name, _t in section_cuts(E, k):
        tag = name.split("-")[0]
        if axis == "x":
            a, b = v(at, ys[0] - 2.2), v(at, ys[-1] + 2.2)
            arrow = (1.0, 0.0)
        else:
            a, b = v(xs[0] - 2.2, at), v(xs[-1] + 2.2, at)
            arrow = (0.0, 1.0)
        sh.line(a, b, "grid", 0.35, True)
        for q in (a, b):
            sh.line(q, (q[0] + arrow[0] * 6, q[1] + arrow[1] * 6), "text", 0.5)
            sh.poly([(q[0] + arrow[0] * 6, q[1] + arrow[1] * 6),
                     (q[0] + arrow[0] * 3.5 + arrow[1] * 1.5, q[1] + arrow[1] * 3.5 + arrow[0] * 1.5),
                     (q[0] + arrow[0] * 3.5 - arrow[1] * 1.5, q[1] + arrow[1] * 3.5 - arrow[0] * 1.5)],
                    "text", 0.35)
            sh.circle(q, 3.2, "text", 0.35)
            sh.text((q[0], q[1] - 1.2), tag, 2.8, "center", "text", True)


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
        for k in ("ridge", "hip", "valleys"):
            for a, b in L.get(k) or []:
                sh.line(v(a[0], a[1]), v(b[0], b[1]), "struct", 0.6)
        for a, b in L.get("eave") or []:
            sh.line(v(a[0], a[1]), v(b[0], b[1]), "roof", 0.25)
    x0, y0, x1, y1 = drawing_area()
    lines = [f"อกไก่ {s['ridge']}", f"ตะเข้สัน / ตะเข้ราง {s['hip']}",
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

GROUP_TH = {"G": "ปกและสารบัญ", "A": "แบบสถาปัตยกรรม", "S": "แบบวิศวกรรมโครงสร้าง",
            "SN": "แบบวิศวกรรมสุขาภิบาล", "EE": "แบบวิศวกรรมไฟฟ้า",
            "M": "แบบวิศวกรรมเครื่องกล", "BOQ": "บัญชีปริมาณงาน (ปร.1)"}


def build_set(data, info=None,
              groups=("G", "A", "S", "SN", "EE", "M", "BOQ")) -> list:
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
        f"หลังคา {B.ROOF_TYPES.get(E['settings'].get('roof'), 'ไม่มี')} "
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
        for k in floors:
            cuts = section_cuts(E, k)
            title = " ".join(f"รูปตัด {c[2]}" for c in cuts) or "รูปตัด"
            add("A", title, lambda sh, _a, k=k: _set_scale(sh, a_section_sheet(sh, E, L, k)))
        if info.get("axo_sections"):
            for title, paint in axo_sheets(data):
                add("A", title, paint, "-")
        if E["openings"]:
            add("A", "ตารางประตู-หน้าต่าง วัสดุตกแต่ง",
                lambda sh, _a: a_schedules(sh, E, codes, fcodes), "1:50")
        if any((s["room"].get("name") or "").startswith("ห้องน้ำ")
               for s in E["slabs"]):
            add("A", "แบบขยายห้องน้ำ", lambda sh, _a: a_bathrooms(sh, E),
                "1:50")
            baths = bathrooms(E)
            for i in range(0, len(baths), 2):
                add("A", "รูปด้านภายในห้องน้ำ" + (f" ({i // 2 + 1})" if len(baths) > 2 else ""),
                    lambda sh, _a, rr=baths[i:i + 2]: a_bath_elevations(sh, E, rr), "1:50")
        add("A", "รายการวัสดุประกอบแบบ", lambda sh, _a: a_materials(sh, E, fcodes), "-")
        if L:
            add("A", "แบบขยายเชิงชาย ฝ้าชายคา โครงถักหลังคา",
                lambda sh, _a: detail_eave_truss(sh, E, L), "1:20")
        add("A", "ข้อกำหนดความปลอดภัยในการก่อสร้าง อุปกรณ์ดับเพลิง",
            lambda sh, _a: a_safety(sh, E), "ตามระบุ")
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
        add("S", "แบบขยายเหล็กเสริมฐานรากและคาน",
            lambda sh, _a: s_rebar_details(sh, E), "ตามระบุ")
    if "SN" in groups:
        add("SN", "สารบัญแบบ สัญลักษณ์ รายการประกอบแบบสุขาภิบาล",
            lambda sh, all_: sn_index(sh, all_), "-")
        for k in floors:
            add("SN", f"แปลนระบบสุขาภิบาลชั้น {k + 1}",
                lambda sh, _a, k=k: sn_plan(sh, E, k))
        add("SN", "แบบขยายถังบำบัด บ่อพัก ฟลอร์เดรน", lambda sh, _a: sn_details(sh, E), "1:20")
    if "EE" in groups:
        add("EE", "สารบัญแบบ สัญลักษณ์ ตารางโหลด รายการประกอบแบบไฟฟ้า",
            lambda sh, all_: ee_index(sh, all_, E), "-")
        for k in floors:
            add("EE", f"แปลนระบบไฟฟ้าชั้น {k + 1}",
                lambda sh, _a, k=k: ee_plan(sh, E, k))
        add("EE", "ผังวงจรไฟฟ้า (Single Line Diagram)", lambda sh, _a: ee_single_line(sh, E), "-")
    if "M" in groups:
        for k in floors:
            add("M", f"แปลนระบบปรับอากาศและระบายอากาศชั้น {k + 1}",
                lambda sh, _a, k=k: m_plan(sh, E, k, None))
    sheets = [s for s, _f in plan]
    for i, s in enumerate(sheets, 1):
        s.number = i
    pic = info.get("plan_picture")
    for s, fn in plan:
        fn(s, sheets)
        if pic:
            inset_picture(s, pic)
        frame(s, info, len(sheets))
    boq = build_boq(data, info) if "BOQ" in groups else []
    front = []
    if "G" in groups and (sheets or boq):
        cover = Sheet("ปก", "ปกแบบ", "-", "G")
        cover.number = 0
        g_cover(cover, E, info, sheets, boq)
        toc = Sheet("สารบัญ", "สารบัญแบบ", "-", "G")
        toc.number = 0
        g_contents(toc, E, info, sheets, boq)
        front = [cover, toc]
    return front + sheets + boq


def _item_points(sh):
    """Points every drawn item touches (text: its approximate extent)."""
    pts = []
    for it in sh.items:
        k = it[0]
        if k == "line":
            x0, y0, x1, y1 = it[1]
            pts += [(x0 + (x1 - x0) * t, y0 + (y1 - y0) * t) for t in (0, 0.25, 0.5, 0.75, 1)]
        elif k in ("poly", "fill"):
            ps = list(it[1])
            for a, b in zip(ps, ps[1:] + ps[:1]):
                pts += [(a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
                        for t in (0, 0.25, 0.5, 0.75)]
        elif k in ("circle", "arc"):
            x, y, r = it[1][:3]
            pts += [(x - r, y), (x + r, y), (x, y - r), (x, y + r)]
        elif k == "text":
            (x, y), txt, h, al = it[1], it[2], it[3], it[4]
            w = 0.55 * h * len(txt)
            x0 = x - w if al == "right" else x - w / 2 if al == "center" else x
            pts += [(x0 + w * t, y + h * 0.5) for t in (0, 0.25, 0.5, 0.75, 1)]
        elif k == "image":
            x0, y0, x1, y1 = it[1]
            pts += [(x0, y0), (x1, y1), (x0, y1), (x1, y0), ((x0 + x1) / 2, (y0 + y1) / 2)]
    return pts


def inset_picture(sh, data: bytes, sizes=((100.0, 56.0), (80.0, 45.0), (64.0, 36.0))):
    """The 3D picture of the building in a free corner of a drawing sheet
    (the first corner, largest size first, that nothing else is drawn in).
    Returns the box or None when the sheet has no room."""
    if not data or sh.group in ("G", "BOQ"):
        return None
    X0, Y0, X1, Y1 = drawing_area()
    pts = _item_points(sh)
    for w, h in sizes:
        h_all = h + 5.0                          # the caption under it
        for cx, cy in ((X1 - w - 2, Y1 - h_all - 14), (X0 + 2, Y1 - h_all - 2),
                       (X1 - w - 2, Y0 + 16), (X0 + 2, Y0 + 2)):
            box = (cx - 1.5, cy - 1.5, cx + w + 1.5, cy + h_all + 1.5)
            if any(box[0] <= x <= box[2] and box[1] <= y <= box[3] for x, y in pts):
                continue
            pic = (cx, cy + 5.0, cx + w, cy + 5.0 + h)
            sh.items.insert(0, ("image", pic, "image", data))
            sh.rect(*pic, "frame", 0.25)
            sh.text((cx + w / 2, cy + 1.2), "ภาพทัศนียภาพ 3 มิติ (ประกอบแบบ)", 2.0,
                    "center", "text")
            return pic
    return None


# ---------------------------------------------------------------------------
# Detail sheets like the standard sets: materials, eave & truss, single
# line diagram, sanitary details
# ---------------------------------------------------------------------------

def a_materials(sh, E, fcodes):
    """รายการวัสดุ: floors (พ), walls (ผ), ceilings (ฝ), trims, the roof —
    each with its code and description, as on the standard sets."""
    s = E["settings"]
    x0, y0, x1, y1 = drawing_area()
    sh.text((x0 + 85, y1 - 6), "รายการวัสดุประกอบแบบ", 4.0, "center", "text", True)
    rows = [("พื้น", "")]
    for code, (tag, name) in fcodes.items():
        rows.append((tag, name[:70]))
    rows.append(("ผนัง", ""))
    for i, ext in enumerate((True, False), 1):
        sp = B.wall_spec(s, ext)
        rows.append((f"ผ{i}", f"{'ผนังภายนอก' if ext else 'ผนังภายใน'} {sp['name']} "
                              f"ฉาบปูนเรียบ {sp['po' if ext else 'pi'] * 100:g} ซม. ทาสีน้ำอะครีลิค"))
    if any(CAT.finish_of(sl["room"])["wall_tile"] for sl in E["slabs"]):
        rows.append(("ผ3", "ผนังบุกระเบื้องเซรามิค (ห้องน้ำ/ครัว) ตามความสูงที่ระบุในแบบขยาย"))
    rows.append(("ฝ้าเพดาน", ""))
    for i, (key, (name, lab, frame, sub, main)) in enumerate(B.CEILING_TYPES.items(), 1):
        rows.append((f"ฝ{i}", f"{name} ลวด/สตัดแขวน @{main:.2f} ม."))
    rows.append((f"ฝ{len(B.CEILING_TYPES) + 1}",
                 "ฝ้าชายคาระแนงไม้เทียมเว้นร่อง + มุ้งกันแมลง โครงซีลาย สตัดแขวนใต้จันทัน"))
    rows.append(("บัว", ""))
    if s.get("skirting"):
        rows.append(("บ1", B.SKIRTING_TYPES.get(s.get("skirting_type", "ceramic"),
                                               B.SKIRTING_TYPES["ceramic"])[0]))
    if s.get("cornice"):
        rows.append(("บ2", B.CORNICE[0]))
    rows.append(("หลังคา", ""))
    tile = CAT.roof_tile(s)[1]["name"]
    rows.append(("ล1", f"{tile} ลาด {float(s.get('pitch') or 0):.0f}° บนแป {s['purlin']}"))
    rows.append(("ล2", f"โครงหลังคาเหล็ก: อกไก่/ตะเฆ่ {s['ridge']} จันทัน {s['rafter']} "
                       f"อะเส/ขื่อ {s['tiebeam']} ตุ๊กตา {s.get('strut', '-')}"))
    rows.append(("ล3", "เชิงชาย + ทับเชิงชาย ไม้สำเร็จรูป 1\"×8\" + 1\"×6\" ปิดนก PVC"))
    y = y1 - 12
    cols = [("สัญลักษณ์", 26, "center"), ("รายการวัสดุ", 190, "left")]
    out = []
    for tag, desc in rows:
        out.append((tag if desc else f"[{tag}]", desc))
    table(sh, x0, y, cols, out, 2.3, 6.0)
    # symbols on the right
    xs = x0 + 232
    sh.text((xs, y1 - 6), "สัญลักษณ์ประกอบแบบ", 3.6, "left", "text", True)
    yy = y1 - 18
    items = [("grid", "แนวเสา (กริด) ระยะศูนย์กลางถึงศูนย์กลาง"),
             ("level", "ระดับ (เมตร) ±0.00 = ระดับพื้นชั้น 1"),
             ("cut", "รูปตัดอาคาร ก-ก ข-ข (หัวลูกศรชี้ทางมอง)"),
             ("door", "ป1 รหัสประตู · น1 รหัสหน้าต่าง"),
             ("hatch", "ผนังก่ออิฐฉาบปูน (แรเงา) / คอนกรีตตัด (ทึบ)")]
    for kind, desc in items:
        if kind == "grid":
            sh.circle((xs + 4, yy + 1), 2.6, "grid", 0.25)
            sh.text((xs + 4, yy), "1", 2.4, "center", "grid")
        elif kind == "level":
            _level(sh, (xs + 4, yy), 0.0, "", left=False)
        elif kind == "cut":
            sh.circle((xs + 4, yy + 1), 2.8, "text", 0.35)
            sh.text((xs + 4, yy), "ก", 2.6, "center", "text", True)
        elif kind == "door":
            sh.text((xs + 1, yy), "ป1", 2.6, "left", "text", True)
        else:
            sh.fill([(xs, yy - 1), (xs + 8, yy - 1), (xs + 8, yy + 3), (xs, yy + 3)], "hatch", 0.85)
        sh.text((xs + 14, yy), desc, 2.3)
        yy -= 9


def detail_eave_truss(sh, E, L):
    """แบบขยายเชิงชาย-ฝ้าชายคา (1:20) and the roof truss (1:50): the ring
    beam, column-head plate and J-bolts, wall plate, rafter, purlins, tile,
    fascia, soffit with its frame and hangers; the truss with tie, ridge
    beam, king post, struts and braces."""
    s = E["settings"]
    x0, y0, x1, y1 = drawing_area()
    tan = math.tan(math.radians(float(s.get("pitch") or 30)))
    ov = float(s.get("overhang") or 0.6)
    # --- eave detail, 1:20 -------------------------------------------------
    k = 1000.0 / 20
    ox, oy = x0 + 95, y0 + 75

    def P(u, z):
        return (ox + u * k, oy + z * k)

    def R(u0, z0, u1, z1, layer="cut", w=0.35, fill=None):
        pts = [P(u0, z0), P(u1, z0), P(u1, z1), P(u0, z1)]
        if fill is not None:
            sh.fill(pts, "hatch", fill)
        sh.poly(pts, layer, w)
    lib = E["lib"]
    bh = float(lib["RB1"]["h"])
    half = float(lib["C1"]["b"]) / 2
    R(-half, -bh, half, 0.0, fill=0.75)                    # ring beam
    R(-half, -bh - 0.8, half, -bh, "cut", 0.25)             # column below
    sp = B.wall_spec(s, True)
    R(-half + sp["po"], -bh - 0.8, -half + sp["po"] + sp["t"], -bh, "cut", 0.25, 0.9)
    R(-0.10, -0.009, 0.10, 0.0, "struct", 0.35, 0.3)        # head plate
    for u in (-0.05, 0.05):
        sh.line(P(u, 0.05), P(u, -0.60), "struct", 0.25)
        sh.line(P(u, -0.60), P(u + (0.08 if u < 0 else -0.08), -0.60), "struct", 0.25)
    ph = 0.15
    R(-0.0325, 0.0, 0.0325, ph, "struct", 0.35, 0.5)          # wall plate (C150)
    # rafter line: underside through (0, ph), rising inward (to the left: −u = inside)
    ru = [(-1.6, ph + 1.6 * tan), (ov + 0.05, ph - (ov + 0.05) * tan)]
    sh.line(P(*ru[0]), P(*ru[1]), "struct", 0.5)
    rd = 0.15 / math.cos(math.atan(tan))
    sh.line(P(ru[0][0], ru[0][1] + rd), P(ru[1][0], ru[1][1] + rd), "struct", 0.5)
    # purlins at the batten gauge, tiles over them
    gauge = float(s.get("purlin_sp") or 0.32) * math.cos(math.atan(tan))
    u = ov - 0.05
    while u > -1.55:
        zt = ph - u * tan + rd
        R(u - 0.0225, zt, u + 0.0225, zt + 0.075, "struct", 0.25)
        u -= gauge
    sh.line(P(-1.6, ph + 1.6 * tan + rd + 0.10), P(ov + 0.05, ph - (ov + 0.05) * tan + rd + 0.10),
            "roof", 0.7)
    # fascia at the eave and the soffit under it
    ze = ph - ov * tan + rd
    R(ov, ze - 0.20, ov + 0.025, ze, "cut", 0.35, 0.6)
    zs = ze - 0.20
    R(half, zs, ov, zs + 0.008, "cut", 0.35, 0.4)
    R(half, zs + 0.008, ov, zs + 0.032, "struct", 0.18)
    for uh in (half + 0.25, (half + ov) / 2 + 0.1):
        zr = ph - uh * tan
        if zr > zs + 0.05:
            sh.line(P(uh, zs + 0.032), P(uh, zr), "struct", 0.25)
    notes = [((ov - 0.3, ph - (ov - 0.3) * tan + rd + 0.10),
              "กระเบื้อง " + CAT.roof_tile(s)[1]["name"][:30]),
             ((-0.6, ph + 0.6 * tan + rd + 0.04), f"แป {s['purlin']} หันปากขึ้นอกไก่"),
             ((-0.9, ph + 0.9 * tan + 0.07), f"จันทัน {s['rafter']}"),
             ((ov + 0.012, ze - 0.10), "เชิงชาย + ทับเชิงชาย ไม้สำเร็จรูป 1\"×8\" + 1\"×6\""),
             (((half + ov) / 2, zs + 0.004), "ฝ้าชายคาระแนงไม้เทียม เว้นร่อง + มุ้งกันแมลง"),
             (((half + ov) / 2 + 0.1, zs + 0.10), "โครงซีลาย @0.60 ม. สตัดแขวน Ø6 มม. ใต้จันทัน"),
             ((0.0, ph / 2), f"อะเส {s['wallplate']}"),
             ((0.08, -0.005), "เพลทหัวเสา 200×200×9 มม."),
             ((0.05, -0.40), "J-bolt 4-DB12 ฝังในเสา 0.60 ม. งอขอ 8 ซม."),
             ((-half / 2, -bh / 2), "คานรัดรอบ ค.ส.ล. (RB1)")]
    tx_ = P(ov, 0)[0] + 22
    ty_ = P(0, ph + 0.5 * tan + 0.3)[1]
    for (u, z), t in sorted(notes, key=lambda n: -n[0][1]):
        p_ = P(u, z)
        sh.line(p_, (tx_ - 2, ty_ + 0.8), "dim", 0.13)
        sh.circle(p_, 0.5, "dim", 0.13)
        sh.text((tx_, ty_), t, 2.1, "left", "text")
        ty_ -= 6.5
    caption(sh, (ox + 20, y0 + 8), "แบบขยายเชิงชาย ฝ้าชายคา และหัวเสา", "1:20")
    # --- truss, 1:50 --------------------------------------------------------
    W = 0.0
    if L and L.get("tie"):
        a, b = L["tie"][0]
        W = math.dist(a[:2], b[:2])
    W = W or 6.0
    k2 = 1000.0 / 75
    tx, ty = x0 + 270, y0 + 150

    def Q(u, z):
        return (tx + u * k2, ty + z * k2)
    half_in = W / 2
    hr = (half_in + ov) * tan
    sh.line(Q(-half_in, 0.0), Q(half_in, 0.0), "struct", 0.5)              # tie
    sh.line(Q(-half_in, 0.15), Q(half_in, 0.15), "struct", 0.25)
    sh.line(Q(-half_in - ov, -ov * tan + 0.15), Q(0, hr - ov * tan + 0.15), "struct", 0.5)
    sh.line(Q(half_in + ov, -ov * tan + 0.15), Q(0, hr - ov * tan + 0.15), "struct", 0.5)
    sh.line(Q(0, 0.30), Q(0, hr - ov * tan), "struct", 0.4)               # king post
    sh.rect(*Q(-0.04, 0.15), *Q(0.04, 0.30), "struct", 0.25)               # ridge beam
    for side in (-1, 1):
        q = side * half_in / 2
        zt = (half_in - abs(q)) * tan + 0.15 - 0.15
        sh.line(Q(q, 0.15), Q(q, zt), "struct", 0.35)                       # strut
        sh.line(Q(0, 0.35), Q(q, zt - 0.05), "struct", 0.35)                # brace
        sh.text(Q(q + 0.1 * side, zt / 2), "ตุ๊กตา", 2.0, "left" if side > 0 else "right")
    for side in (-1, 1):
        sh.rect(*Q(side * half_in - 0.1, -0.4), *Q(side * half_in + 0.1, 0.0), "cut", 0.35)
    sh.text(Q(0.15, hr / 2), "ดั้ง", 2.0)
    sh.text(Q(half_in / 4, 0.55), "ค้ำยัน", 2.0)
    sh.text(Q(-half_in + 0.3, -0.35), f"ขื่อ {s['tiebeam']}", 2.0)
    sh.text(Q(-0.6, hr - ov * tan + 0.45), f"อกไก่ {s['ridge']}", 2.0)
    caption(sh, (tx, ty - 22), "รูปโครงถักหลังคา (ดั้ง ตุ๊กตา ค้ำยัน)", "1:75")


def ee_single_line(sh, E):
    """ผังวงจรไฟฟ้า (single line diagram): the meter, the main breaker with
    its earth-leakage device, and every circuit with its breaker, wire and
    load — from the room services the 3D and the BOQ use."""
    from core import wanic_mep as MEP
    x0, y0, x1, y1 = drawing_area()
    rooms = MEP.plan({}, E)
    circ = []
    lights = sum(r["lights"] for r in rooms)
    outs = sum(r["outlets"] for r in rooms)
    for i in range(max(1, math.ceil(lights / 10))):
        n = min(10, lights - i * 10)
        circ.append((f"แสงสว่าง {i + 1}", "1P 16 A", "THW 2×1.5 ตร.มม.", f"{n} จุด", n * 18))
    for i in range(max(1, math.ceil(outs / 8))):
        n = min(8, outs - i * 8)
        circ.append((f"เต้ารับ {i + 1}", "1P 20 A", "THW 2×2.5 + G 2.5", f"{n} จุด", n * 180))
    for r in rooms:
        if r["ac"]:
            circ.append((f"แอร์ {r['room'].get('name') or ''}", "1P 20 A", "THW 2×4 + G 4",
                         f"{r['ac']:,} BTU", int(r['ac'] / 9)))
        if r["heater"]:
            circ.append((f"น้ำอุ่น {r['room'].get('name') or ''}", "1P 32 A", "THW 2×6 + G 6",
                         "4,500 W", 4500))
    total = sum(c[4] for c in circ)
    amp = total / 220 * 0.8
    meter = "15(45) A" if amp <= 30 else "30(100) A" if amp <= 75 else "50(150) A"
    main = next((f"2P {c} A" for c in (32, 50, 63, 80, 100, 125) if c >= amp * 1.1), "2P 150 A")
    sh.text((x0 + 10, y1 - 8), "ผังวงจรไฟฟ้า (SINGLE LINE DIAGRAM)", 4.0, "left", "text", True)
    bx = x0 + 30
    top = y1 - 25
    sh.circle((bx, top), 5, "elec", 0.35)
    sh.text((bx, top - 1), "kWh", 2.4, "center", "elec", True)
    sh.text((bx + 8, top - 1), f"มิเตอร์ กฟภ./กฟน. {meter} 1 เฟส 2 สาย", 2.3)
    sh.line((bx, top - 5), (bx, top - 18), "elec", 0.5)
    sh.rect(bx - 4, top - 26, bx + 4, top - 18, "elec", 0.35)
    sh.text((bx + 8, top - 23), f"เมนเบรกเกอร์ {main} + RCBO 30 mA (ตู้คอนซูมเมอร์ยูนิต)", 2.3)
    sh.text((bx + 8, top - 28), "สายเมน THW 2×16 ตร.มม. + G 10 ในท่อ IMC Ø 1\"  · หลักดิน 5/8\"×2.40 ม.", 2.1)
    bus = top - 34
    sh.line((bx, top - 26), (bx, bus), "elec", 0.5)
    xe = bx + 30 + 46 * max(len(circ) - 1, 1)
    xe = min(xe, x1 - 20)
    step = (xe - bx - 30) / max(len(circ) - 1, 1)
    sh.line((bx, bus), (xe, bus), "elec", 0.7)
    for i, (name, cb, wire, load, va) in enumerate(circ):
        cx = bx + 30 + step * i
        sh.line((cx, bus), (cx, bus - 8), "elec", 0.35)
        sh.rect(cx - 2.5, bus - 14, cx + 2.5, bus - 8, "elec", 0.25)
        sh.line((cx, bus - 14), (cx, bus - 40), "elec", 0.35)
        sh.text((cx, bus - 46), name[:16], 2.1, "center", "text", True)
        sh.text((cx, bus - 51), cb, 2.0, "center")
        sh.text((cx, bus - 56), wire, 1.8, "center")
        sh.text((cx, bus - 61), load, 2.0, "center")
        sh.text((cx, bus - 66), f"{va:,} VA", 1.9, "center")
    sh.text((x0 + 10, y0 + 30), f"โหลดรวม {total:,} VA ประมาณ {total / 220:.1f} A × 0.8 (ค่าดีมานด์) = "
                                f"{amp:.1f} A → มิเตอร์ {meter} เมน {main}", 2.6, "left", "text", True)
    sh.text((x0 + 10, y0 + 22), "การเดินสายและติดตั้งตามมาตรฐานการติดตั้งทางไฟฟ้าสำหรับประเทศไทย (วสท. 2001) "
                                "· วงจรเต้ารับและห้องน้ำมีเครื่องตัดไฟรั่ว 30 mA", 2.2)


def sn_details(sh, E):
    """แบบขยายงานสุขาภิบาล: the septic tank, a manhole and the floor drain."""
    s = E["settings"]
    x0, y0, x1, y1 = drawing_area()
    k = 1000.0 / 20

    def box(ox, oy, w, h, layer="cut", lw=0.35, fill=None):
        pts = [(ox, oy), (ox + w * k, oy), (ox + w * k, oy + h * k), (ox, oy + h * k)]
        if fill is not None:
            sh.fill(pts, "hatch", fill)
        sh.poly(pts, layer, lw)
    # septic tank: section to standard practice
    ox, oy = x0 + 100, y1 - 150
    septic_section(sh, ox, oy, k)
    caption(sh, (ox + 0.55 * k, oy - 24), "แบบขยายถังบำบัดน้ำเสียสำเร็จรูป (รูปตัด)", "1:20")
    septic_table(sh, x0 + 4, y1 - 8)
    oy = y0 + 32
    # manhole
    ox2 = x0 + 140
    box(ox2, oy, 0.8, 0.85, "cut", 0.5, 0.75)
    box(ox2 + 0.1 * k, oy + 0.1 * k, 0.6, 0.75, "cut", 0.35, 1.0)
    sh.line((ox2 - 15, oy + 0.4 * k), (ox2, oy + 0.4 * k), "pipe", 0.6)
    sh.line((ox2 + 0.8 * k, oy + 0.4 * k), (ox2 + 0.8 * k + 15, oy + 0.4 * k), "pipe", 0.6)
    sh.rect(ox2 + 0.1 * k, oy + 0.81 * k, ox2 + 0.7 * k, oy + 0.85 * k, "struct", 0.35)
    sh.text((ox2 + 0.4 * k, oy + 0.95 * k), "ฝาตะแกรงเหล็ก", 2.0, "center")
    sh.text((ox2 - 14, oy + 0.4 * k + 2), "ท่อ คสล. Ø 0.30 ม.", 2.0)
    caption(sh, (ox2 + 0.4 * k, y0 + 10), f"แบบขยายบ่อพัก ค.ส.ล. 0.60×0.60 ม. "
                                           f"(ห่างอาคาร {float(s.get('drain_off', 1.5)):.2f} ม.)", "1:20")
    # floor drain
    ox3 = x0 + 245
    sh.line((ox3, oy + 0.6 * k), (ox3 + 0.8 * k, oy + 0.6 * k), "cut", 0.5)
    box(ox3, oy + 0.45 * k, 0.8, 0.15, "cut", 0.35, 0.7)
    box(ox3 + 0.34 * k, oy + 0.2 * k, 0.12, 0.40, "pipe", 0.35)
    sh.line((ox3 + 0.4 * k, oy + 0.2 * k), (ox3 + 0.4 * k, oy + 0.05 * k), "pipe", 0.35)
    sh.line((ox3 + 0.4 * k, oy + 0.05 * k), (ox3 + 0.8 * k + 10, oy + 0.05 * k), "pipe", 0.35)
    sh.text((ox3 + 0.4 * k, oy + 0.66 * k), "ตะแกรงฟลอร์เดรนกันกลิ่น Ø 2\" · พื้นลาด 1:100", 2.0, "center")
    sh.text((ox3 + 0.82 * k, oy + 0.08 * k), "ท่อน้ำทิ้ง PVC Ø 2\"", 2.0)
    caption(sh, (ox3 + 0.4 * k, y0 + 10), "แบบขยายฟลอร์เดรน", "1:20")


#: prefabricated septic tanks (anaerobic filter): litres → persons, size
SEPTIC_SIZES = [(600, 5, "Ø 0.88 × 1.40"), (800, 7, "Ø 0.98 × 1.45"),
                (1000, 10, "Ø 1.05 × 1.55"), (1200, 12, "Ø 1.10 × 1.65"),
                (1600, 16, "Ø 1.20 × 1.80"), (2000, 20, "Ø 1.35 × 1.90")]


def septic_table(sh, x, y):
    sh.text((x, y), "ตารางเลือกขนาดถังบำบัดน้ำเสียสำเร็จรูป (ไร้อากาศ ชนิดมีตัวกลาง)", 2.4,
            "left", "text", True)
    return table(sh, x, y - 2, [("ขนาด (ลิตร)", 22.0, "center"), ("ผู้ใช้ (คน)", 20.0, "center"),
                                ("ขนาดถังโดยประมาณ (ม.)", 38.0, "center")],
                 [(f"{l_:,}", str(p_), d_) for l_, p_, d_ in SEPTIC_SIZES],
                 h=2.0, row_h=4.4, head_h=5.2)


def septic_section(sh, ox, oy, k):
    """รูปตัดถังบำบัดน้ำเสียสำเร็จรูป ``ox, oy`` = the tank's bottom left
    (paper mm), ``k`` mm per metre."""
    W, Hh = 1.10, 1.60                   # tank Ø × height
    soil = 0.25                          # cover of soil over the shoulder
    gl = oy + (Hh + soil) * k            # the ground line

    def X(m):
        return ox + m * k

    def Y(m):
        return oy + m * k
    # excavation, sand and lean concrete
    sh.poly([(X(-0.30), gl), (X(-0.30), Y(-0.15)), (X(W + 0.30), Y(-0.15)), (X(W + 0.30), gl)],
            "hidden", 0.18, closed=False, dash=True)
    sh.fill([(X(-0.25), Y(-0.15)), (X(W + 0.25), Y(-0.15)), (X(W + 0.25), Y(-0.10)),
             (X(-0.25), Y(-0.10))], "hatch", 0.55)
    sh.rect(X(-0.25), Y(-0.15), X(W + 0.25), Y(-0.10), "cut", 0.25)
    sh.rect(X(-0.25), Y(-0.10), X(W + 0.25), Y(0.0), "cut", 0.18)
    for i in range(int((W + 0.5) / 0.05)):
        sh.circle((X(-0.22 + i * 0.05), Y(-0.05)), 0.25, "hatch", 0.1)
    # ground
    sh.line((X(-0.9), gl), (X(W + 0.9), gl), "cut", 0.6)
    for i in range(int((W + 1.8) / 0.10)):
        xx = X(-0.9 + i * 0.10)
        sh.line((xx, gl), (xx - 1.2, gl - 1.2), "hatch", 0.13)
    # the tank: shell, a baffle and the filter media
    sh.poly([(X(0.05), Y(0)), (X(W - 0.05), Y(0)), (X(W), Y(0.08)), (X(W), Y(Hh - 0.12)),
             (X(W - 0.15), Y(Hh)), (X(0.15), Y(Hh)), (X(0), Y(Hh - 0.12)), (X(0), Y(0.08))],
            "pipe", 0.5)
    sh.line((X(W * 0.45), Y(0.25)), (X(W * 0.45), Y(Hh - 0.10)), "pipe", 0.35)
    for i in range(6):
        for j in range(5):
            sh.circle((X(W * 0.52 + i * 0.075), Y(0.35 + j * 0.13)), 0.9, "hatch", 0.13)
    wl_ = Hh - 0.40                       # the water line
    sh.line((X(0.03), Y(wl_)), (X(W - 0.03), Y(wl_)), "pipe", 0.13, True)
    sh.text((X(W * 0.22), Y(0.55)), "ห้องตกตะกอน", 1.8, "center")
    sh.text((X(W * 0.72), Y(1.05)), "ห้องกรองไร้อากาศ", 1.8, "center")
    sh.text((X(W * 0.72), Y(0.95)), "(ตัวกลางพลาสติก)", 1.6, "center")
    # inlet and outlet tees (outlet 5 cm lower)
    zi, zo = Hh - 0.30, Hh - 0.35
    sh.line((X(-0.9), Y(zi) + 1.2), (X(0.12), Y(zi) + 1.2), "pipe", 0.6)
    sh.line((X(0.12), Y(zi - 0.35)), (X(0.12), Y(zi + 0.15)), "pipe", 0.6)
    sh.line((X(W - 0.12), Y(zo - 0.40)), (X(W - 0.12), Y(zo + 0.15)), "pipe", 0.6)
    sh.line((X(W - 0.12), Y(zo) + 1.2), (X(W + 0.9), Y(zo) + 1.2), "pipe", 0.6)
    # access cover and vent
    sh.rect(X(W / 2 - 0.25), Y(Hh), X(W / 2 + 0.25), gl + 0.05 * k, "pipe", 0.35)
    sh.rect(X(W / 2 - 0.30), gl + 0.05 * k, X(W / 2 + 0.30), gl + 0.09 * k, "struct", 0.35)
    sh.line((X(W - 0.25), Y(Hh - 0.04)), (X(W - 0.25), gl + 0.85 * k), "pipe", 0.35)
    sh.line((X(W - 0.31), gl + 0.85 * k), (X(W - 0.19), gl + 0.85 * k), "pipe", 0.35)

    def lead(pt, tx, ty, text):
        sh.line(pt, (tx, ty + 0.6), "text", 0.13)
        sh.line((tx, ty + 0.6), (tx + (2 if tx > pt[0] else -2), ty + 0.6), "text", 0.13)
        sh.text((tx + (2.5 if tx > pt[0] else -2.5), ty), text, 1.8,
                "left" if tx > pt[0] else "right")
    R = X(W + 1.1)
    lead((X(W - 0.25), gl + 0.6 * k), R, gl + 0.70 * k,
         "ท่อระบายอากาศ PVC Ø 2\" สูงจากดินไม่น้อยกว่า 2.00 ม. ปลายติดหมวกกันฝน")
    lead((X(W / 2 + 0.30), gl + 0.07 * k), R, gl + 0.25 * k,
         "ฝาเปิดถัง Ø 0.50 ม. สูงกว่าดิน 0.05–0.10 ม. (ฝาปิดสนิท)")
    lead((X(W + 0.5), Y(zo) + 1.2), R, Y(zo) - 3, "ท่อออก PVC Ø 4\" → บ่อพัก/ท่อระบายสาธารณะ")
    lead((X(W - 0.12), Y(zo - 0.35)), R, Y(zo - 0.35) - 5, "ท่อ T ออก (ต่ำกว่าท่อเข้า 0.05 ม.)")
    lead((X(W * 0.8), Y(0.5)), R, Y(0.5) - 3, "ถังไฟเบอร์กลาส/PE สำเร็จรูป มอก. 2550-2554")
    lead((X(W + 0.25), Y(-0.05)), R, Y(-0.05) - 6, "ทรายหยาบอัดแน่น 0.10 ม.")
    lead((X(W + 0.2), Y(-0.13)), R, Y(-0.13) - 10, "คอนกรีตหยาบ (Lean) 0.05 ม.")
    lead((X(W + 0.27), Y(0.9)), R, Y(0.9) + 2, "ถมกลับด้วยทราย อัดแน่นเป็นชั้น (ห้ามใช้หิน/เศษปูน)")
    L_ = X(-1.0)
    lead((X(0.12), Y(zi) + 1.2), L_, Y(zi) + 6, "ท่อเข้า PVC Ø 4\" ลาด 1:100 จากส้วม")
    lead((X(0.12), Y(zi - 0.35)), L_, Y(zi - 0.35), "ท่อ T เข้า")
    lead((X(0.2), Y(wl_)), L_, Y(wl_) - 6, "ระดับน้ำในถัง")
    # dimensions
    _dim_v(sh, X(-0.55), Y(0), Y(Hh), f"{Hh:.2f}")
    _dim_v(sh, X(-0.55), Y(Hh), gl, f"{soil:.2f}")
    _dim_v(sh, X(-0.55), Y(-0.15), Y(0), "0.15")
    _dim_h(sh, X(0), X(W), Y(-0.15) - 6, f"Ø {W:.2f}")
    sh.text((X(-0.9), gl + 1.2), "±0.00 ระดับดิน", 1.8)


SAFETY_NOTES = [
    "1. จัดทำรั้ว/โครงป้องกันวัสดุตกหล่นรอบอาคารที่ก่อสร้างตั้งแต่ 2 ชั้นขึ้นไป ตามกฎกระทรวง "
    "ฉบับที่ 4 (พ.ศ. 2526) ออกตามความในพระราชบัญญัติควบคุมอาคาร พ.ศ. 2522",
    "2. โครงเหล็กท่อกลม Ø 1½\" หนา 3.2 มม. ระยะห่าง 2.00 ม. ทั้งทางตั้งและทางนอน "
    "ปิดช่องว่างด้วยผ้าใบหรือตาข่ายกันวัสดุตก",
    "3. ยึดโครงเหล็กเข้ากับโครงสร้างอาคารทุกชั้น ด้วยเหล็กท่อ Ø 1\" ทุกระยะ 2.00 ม.",
    "4. ฐานรองรับเสาโครงเหล็กใช้แผ่นเหล็ก 0.30×0.30 ม. หนา 6 มม. ทุกจุด",
    "5. ความสูงของโครงป้องกันสูงกว่าระดับที่ทำการก่อสร้างไม่น้อยกว่า 2.00 ม. "
    "และเพิ่มความสูงตามการก่อสร้างจนแล้วเสร็จ",
    "6. ผู้ปฏิบัติงานบนที่สูงเกิน 2.00 ม. ต้องสวมเข็มขัดนิรภัย/สายช่วยชีวิต หมวกนิรภัย "
    "และรองเท้านิรภัยตลอดเวลา",
    "7. ติดตั้งเครื่องดับเพลิงชนิดผงเคมีแห้ง ขนาด 4 กก. สูงจากพื้นถึงหูแขวน 1.50 ม. "
    "ในที่มองเห็นและหยิบใช้ได้สะดวก",
    "8. ติดตั้งป้ายเตือนอันตรายและป้ายโครงการให้มองเห็นชัดเจนตลอดระยะเวลาก่อสร้าง",
]


def a_safety(sh, E):
    """ข้อกำหนดความปลอดภัย: the protective steel frame round the building
    (elevation, section, plan strip), the fire-hose cabinet and the hand
    extinguisher — after the standard sets."""
    x0, y0, x1, y1 = drawing_area()
    k = 1000.0 / 100                       # 1:100 for the frame
    ox, oy = x0 + 20, y1 - 118
    bays, tiers = 4, 5
    sh.text((ox, y1 - 6), "ตามกฎกระทรวง ฉบับที่ 4 (พ.ศ. 2526) ออกตามความในพระราชบัญญัติ"
                          "ควบคุมอาคาร พ.ศ. 2522", 2.2, "left", "text", True)
    W, Hh = bays * 2.0 * k, tiers * 2.0 * k
    for i in range(bays + 1):
        x = ox + i * 2.0 * k
        sh.line((x, oy), (x, oy + Hh + 1.0 * k), "struct", 0.4)
        sh.rect(x - 1.5, oy - 0.6, x + 1.5, oy, "struct", 0.25)
    for j in range(tiers + 1):
        y = oy + j * 2.0 * k
        sh.line((ox - 1.0 * k, y), (ox + W + 1.0 * k, y), "struct", 0.35)
        sh.line((ox - 1.0 * k, y + 0.8), (ox + W + 1.0 * k, y + 0.8), "struct", 0.18)
    for i in range(bays):
        for j in range(1, tiers):
            a = (ox + i * 2.0 * k, oy + j * 2.0 * k)
            b = (a[0] + 2.0 * k, a[1] + 2.0 * k)
            sh.line(a, b, "elec", 0.18)
            sh.line((a[0], b[1]), (b[0], a[1]), "elec", 0.18)
    for i in range(bays):
        _dim_h(sh, ox + i * 2.0 * k, ox + (i + 1) * 2.0 * k, oy - 5, "2.00")
    for j in range(tiers):
        _dim_v(sh, ox - 1.0 * k - 4, oy + j * 2.0 * k, oy + (j + 1) * 2.0 * k, "2.00")
    sh.line((ox + 2.6 * k, oy + 7.2 * k), (ox + W + 2.0 * k, oy + Hh + 0.6 * k), "text", 0.13)
    sh.text((ox + W + 2.3 * k, oy + Hh + 0.5 * k),
            "โครงเหล็ก Ø 1½\" หนา 3.2 มม. ระยะห่าง 2.00 ม.", 2.0)
    sh.line((ox + 3.0 * k, oy + 5.0 * k), (ox + W + 2.0 * k, oy + 7.0 * k), "text", 0.13)
    sh.text((ox + W + 2.3 * k, oy + 6.9 * k), "ช่องว่างปิดด้วยผ้าใบ/ตาข่ายกันวัสดุตก", 2.0)
    caption(sh, (ox + W / 2, oy - 14), "รูปด้านหน้า โครงป้องกันวัสดุตกหล่น", "1:100")
    # section
    sx = ox + W + 4.0 * k + 40
    sh.line((sx, oy), (sx, oy + Hh + 1.0 * k), "struct", 0.4)
    sh.line((sx - 1.0 * k, oy), (sx + 4.0 * k, oy), "cut", 0.5)
    sh.line((sx, oy + 4.0 * k), (sx + 2.0 * k, oy + 2.4 * k), "struct", 0.3)
    sh.line((sx, oy + 1.2 * k), (sx + 1.8 * k, oy), "struct", 0.3)
    sh.circle((sx, oy), 3.0, "elec", 0.25)
    for zz, text in ((Hh + 0.8 * k, "ระดับโครงเหล็กป้องกันของตกหล่น (เพิ่มตามความสูงอาคาร)"),
                     (Hh - 1.2 * k, "ระดับความสูงสุดในแต่ละช่วงที่ทำการก่อสร้าง"),
                     (4.0 * k, "ยึดโครงสร้างอาคารด้วยเหล็ก Ø 1\" หนา 3.2 มม. ทุก 2.00 ม."),
                     (0.0, "ฐานรองรับเหล็กแผ่น 0.30×0.30 ม. หนา 6 มม. ทุกจุด")):
        sh.line((sx, oy + zz), (sx + 6, oy + zz + 2), "text", 0.13)
        sh.text((sx + 7, oy + zz + 1.4), text, 1.9)
    _dim_v(sh, sx - 6, oy + Hh - 1.2 * k, oy + Hh + 0.8 * k, "2.00 (min)")
    caption(sh, (sx + 20, oy - 14), "รูปตัด ก", "1:100")
    # fire-hose cabinet and extinguisher at 1:20
    k2 = 1000.0 / 20
    cx, cy = x0 + 20, y0 + 30
    sh.rect(cx, cy, cx + 1.00 * k2, cy + 1.20 * k2, "cut", 0.5)
    sh.rect(cx + 3, cy + 3, cx + 1.00 * k2 - 3, cy + 1.20 * k2 - 3, "elec", 0.25)
    for i in range(7):
        sh.circle((cx + 0.35 * k2, cy + 0.40 * k2 + i * 0), 6 + i * 0.0, "fixture", 0.13)
    for i in range(6):
        sh.rect(cx + 0.18 * k2 + i * 1.8, cy + 0.12 * k2, cx + 0.18 * k2 + i * 1.8 + 1.2,
                cy + 0.75 * k2, "fixture", 0.13)
    sh.rect(cx + 0.72 * k2, cy + 0.12 * k2, cx + 0.84 * k2, cy + 0.60 * k2, "elec", 0.25)
    sh.line((cx + 0.20 * k2, cy + 0.95 * k2), (cx + 0.70 * k2, cy + 0.95 * k2), "fixture", 0.3)
    _dim_h(sh, cx, cx + 1.00 * k2, cy + 1.20 * k2 + 5, "1.00")
    _dim_v(sh, cx + 1.00 * k2 + 6, cy, cy + 1.20 * k2, "1.20")
    sh.rect(cx + 1.00 * k2 + 18, cy, cx + 1.35 * k2 + 18, cy + 1.20 * k2, "cut", 0.4)
    _dim_h(sh, cx + 1.00 * k2 + 18, cx + 1.35 * k2 + 18, cy + 1.20 * k2 + 5, "0.35")
    caption(sh, (cx + 0.65 * k2 + 10, cy - 14), "ตู้ใส่อุปกรณ์ดับเพลิง (สายฉีด ขวาน ถังดับเพลิง)", "1:20")
    ex = cx + 1.35 * k2 + 75
    sh.line((ex - 20, cy), (ex + 30, cy), "cut", 0.5)
    sh.text((ex - 20, cy + 1.2), "±0.00", 1.9)
    sh.rect(ex - 4, cy + 1.00 * k2, ex + 4, cy + 1.45 * k2, "elec", 0.35)
    sh.circle((ex, cy + 1.50 * k2), 2.5, "elec", 0.25)
    _dim_v(sh, ex + 14, cy, cy + 1.50 * k2, "1.50")
    caption(sh, (ex + 5, cy - 14), "ถังดับเพลิงพร้อมอุปกรณ์ติดตั้ง", "1:20")
    notes_block(sh, x0 + 205, y0 + 92, "หมายเหตุความปลอดภัย", SAFETY_NOTES, 2.0, 62)
    _ = E


# ---------------------------------------------------------------------------
# Bathroom interior elevations, rebar details of footings and beams
# ---------------------------------------------------------------------------

def bathrooms(E):
    """[(floor, room)] of every bathroom, in plan order."""
    return [(sl["floor"], sl["room"]) for sl in E["slabs"]
            if (sl["room"].get("name") or "").startswith("ห้องน้ำ")]


def _dim_h(sh, a, b, y, text, layer="dim"):
    sh.line((a, y), (b, y), layer, 0.13)
    for t in (a, b):
        sh.line((t - 0.8, y - 0.8), (t + 0.8, y + 0.8), layer, 0.25)
        sh.line((t, y - 1.2), (t, y + 1.2), layer, 0.13)
    sh.text(((a + b) / 2, y + 0.9), text, 2.0, "center", layer)


def _dim_v(sh, x, a, b, text, layer="dim"):
    sh.line((x, a), (x, b), layer, 0.13)
    for t in (a, b):
        sh.line((x - 0.8, t - 0.8), (x + 0.8, t + 0.8), layer, 0.25)
        sh.line((x - 1.2, t), (x + 1.2, t), layer, 0.13)
    sh.text((x - 0.9, (a + b) / 2), text, 2.0, "center", layer, angle=90)


#: how a fixture shows in an elevation: (bottom, height) when the catalogue
#: gives no height of its own
_FX_FACE = {"WC": "โถส้วม", "UR": "โถปัสสาวะ", "LV": "อ่างล้างหน้า", "SH": "ฝักบัว",
            "BT": "อ่างอาบน้ำ", "SK": "ซิงค์", "FD": "ฟลอร์เดรน"}


def bath_elevation(sh, E, k, rm, side, ox, oy, sc=50):
    """One interior elevation of a bathroom wall (``side`` 0 S, 1 E, 2 N,
    3 W — seen from inside the room): the wall to the ceiling, the tiles
    to their height in 0.30×0.60 courses, the door / window in it, the
    fixtures against it, the levels and the sizes. Returns its width (mm)."""
    kk = 1000.0 / sc
    x0, y0, x1, y1 = B.room_inner(E, rm, k)
    H = E["H"]
    zc = B.ceiling_z(E, k) - k * H                   # ceiling over the floor
    fin = CAT.finish_of(rm)
    th = min(float(fin.get("tile_h") or 2.0), zc)
    # the wall's ends seen from inside, left → right, and its line in plan
    walls = {0: ((x1, y0), (x0, y0)), 1: ((x1, y1), (x1, y0)),
             2: ((x0, y1), (x1, y1)), 3: ((x0, y0), (x0, y1))}
    a, b = walls[side]
    W = math.dist(a, b)
    u = ((b[0] - a[0]) / W, (b[1] - a[1]) / W)

    def P(s_, z):
        return (ox + s_ * kk, oy + z * kk)
    # tiles: courses 0.30 high, joints every 0.60 (staggered half a tile)
    zt = 0.30
    row = 0
    while zt < th - 1e-6:
        sh.line(P(0, zt), P(W, zt), "hatch", 0.09)
        zt += 0.30
    z_ = 0.0
    while z_ < th - 1e-6:
        x_ = 0.30 if row % 2 else 0.60
        while x_ < W - 1e-6:
            sh.line(P(x_, z_), P(x_, min(z_ + 0.30, th)), "hatch", 0.09)
            x_ += 0.60
        z_ += 0.30
        row += 1
    sh.line(P(0, th), P(W, th), "wall", 0.25)
    # openings in this wall
    line_c = {0: rm["y"], 1: rm["x"] + rm["w"], 2: rm["y"] + rm["d"], 3: rm["x"]}[side]
    for o in (o for o in E["openings"] if o["floor"] == k):
        op = o["op"]
        ox_, oy_ = float(op["x"]), float(op["y"])
        on = abs((oy_ if side in (0, 2) else ox_) - line_c) < 0.06
        if not on:
            continue
        s_ = (ox_ - a[0]) * u[0] + (oy_ - a[1]) * u[1]
        w_, h_, sill = float(o["w"]), float(o["h"]), float(o["sill"])
        if s_ + w_ / 2 < 0 or s_ - w_ / 2 > W:
            continue
        lo, hi = max(s_ - w_ / 2, 0.0), min(s_ + w_ / 2, W)
        pts = [P(lo, sill), P(hi, sill), P(hi, sill + h_), P(lo, sill + h_)]
        sh.fill(pts, "hatch", 1.0)                   # no tiles through it
        sh.poly(pts, "window" if o["type"] == "window" else "door", 0.35)
        inset = 0.05
        sh.poly([P(lo + inset, sill + (inset if o["type"] == "window" else 0)),
                 P(hi - inset, sill + (inset if o["type"] == "window" else 0)),
                 P(hi - inset, sill + h_ - inset), P(lo + inset, sill + h_ - inset)],
                "window" if o["type"] == "window" else "door", 0.18)
        if o["type"] == "window":
            sh.line(P((lo + hi) / 2, sill + inset), P((lo + hi) / 2, sill + h_ - inset),
                    "window", 0.13)
        else:
            sh.line(P(hi - 0.12, sill + 0.95), P(hi - 0.20, sill + 0.95), "door", 0.25)
        sh.text(P((lo + hi) / 2, sill + h_ + 0.05), (o.get("name") or "").split(" ")[0],
                1.8, "center", "door")
    # fixtures with their back to this wall
    for f in (f for f in E["fixtures"] if f["floor"] == k and _inside(f["fx"], rm)):
        fx = f["fx"]
        t = str(fx.get("type", ""))
        spec = CAT.SANITARY.get(t)
        if not spec:
            continue
        pts = fixture_rect(fx)
        # a fixture stands against the wall nearest its centre — drawn on
        # that wall's elevation only (not again side-on from the corner)
        fxx, fyy = float(fx["x"]), float(fx["y"])
        gaps = (fyy - y0, x1 - fxx, y1 - fyy, fxx - x0)
        if min(range(4), key=lambda i: gaps[i]) != side:
            continue
        ss = [(p[0] - a[0]) * u[0] + (p[1] - a[1]) * u[1] for p in pts]
        lo, hi = max(min(ss), 0.0), min(max(ss), W)
        if hi - lo < 0.05:
            continue
        zb, hh = float(spec[5]), float(spec[6])
        if t.startswith("SH"):
            sh.circle(P((lo + hi) / 2, 1.95), 0.08 * kk, "fixture", 0.25)
            sh.line(P((lo + hi) / 2, 1.95), P((lo + hi) / 2, 1.10), "fixture", 0.18)
            sh.rect(*P((lo + hi) / 2 - 0.04, 1.05), *P((lo + hi) / 2 + 0.04, 1.15),
                    "fixture", 0.25)
        elif t.startswith("WC"):
            sh.rect(*P(lo + 0.03, 0.0), *P(hi - 0.03, 0.40), "fixture", 0.3)
            if hh > 0.4:
                sh.rect(*P(lo, 0.40), *P(hi, hh), "fixture", 0.3)
        elif t.startswith("LV") or t.startswith("SK"):
            top = (zb + hh) if zb else 0.85
            sh.rect(*P(lo, top - 0.18), *P(hi, top), "fixture", 0.3)
            sh.line(P((lo + hi) / 2, top - 0.18), P((lo + hi) / 2, 0.45), "pipe", 0.18)
            sh.rect(*P((lo + hi) / 2 - 0.02, top), *P((lo + hi) / 2 + 0.02, top + 0.15),
                    "fixture", 0.2)
            if t.startswith("LV") and top + 0.25 < zc:
                sh.rect(*P(lo, top + 0.20), *P(hi, min(top + 0.95, zc - 0.10)),
                        "fixture", 0.18)
                sh.text(P((lo + hi) / 2, min(top + 0.95, zc - 0.10) - 0.15), "กระจกเงา",
                        1.6, "center", "fixture")
        else:
            sh.rect(*P(lo, zb), *P(hi, zb + max(hh, 0.1)), "fixture", 0.3)
        name = next((v for kk_, v in _FX_FACE.items() if t.startswith(kk_)), t)
        sh.text(P((lo + hi) / 2, -0.16), f"{t} {name}", 1.5, "center", "fixture")
    # outline, floor and ceiling
    sh.rect(*P(0, 0), *P(W, zc), "cut", 0.5)
    sh.line(P(-0.15, 0), P(W + 0.15, 0), "cut", 0.7)
    sh.line(P(-0.15, zc), P(W + 0.15, zc), "cut", 0.35)
    sh.text(P(W / 2, th + (zc - th) / 2 - 0.05), "ฉาบปูนเรียบ ทาสีกันชื้น", 1.8, "center")
    _dim_h(sh, P(0, 0)[0], P(W, 0)[0], P(0, -0.50)[1], f"{W:.2f}")
    _dim_v(sh, P(W + 0.30, 0)[0], P(0, 0)[1], P(0, th)[1], f"{th:.2f}")
    _dim_v(sh, P(W + 0.55, 0)[0], P(0, 0)[1], P(0, zc)[1], f"{zc:.2f}")
    _level(sh, P(0, 0), -0.05, "พื้นห้องน้ำ", left=True)
    _level(sh, P(0, zc), zc, "ใต้ฝ้า", left=True)
    return W * kk


def a_bath_elevations(sh, E, rooms):
    """รูปด้านภายในห้องน้ำ: the four walls of each bathroom (two rooms a
    sheet) at 1:50, side by side, named ก ข ค ง round the room."""
    x0, y0, x1, y1 = drawing_area()
    names = ("ก", "ข", "ค", "ง")
    side_name = ("ทิศใต้", "ทิศตะวันออก", "ทิศเหนือ", "ทิศตะวันตก")
    y = y1 - 20
    for k, rm in rooms:
        sc = 50
        kk = 1000.0 / sc
        zc = B.ceiling_z(E, k) - k * E["H"]
        widths = []
        ix0, iy0, ix1, iy1 = B.room_inner(E, rm, k)
        for side in range(4):
            widths.append(((ix1 - ix0) if side in (0, 2) else (iy1 - iy0)) * kk)
        need = sum(widths) + 4 * 44
        if need > x1 - x0:
            sc = 75
            kk = 1000.0 / sc
            widths = [w_ * 50 / 75 for w_ in widths]
        oy = y - zc * kk - 6
        x = x0 + 26
        for side in range(4):
            w_ = bath_elevation(sh, E, k, rm, side, x, oy, sc)
            sh.text((x + w_ / 2, oy - 13), f"รูปด้านภายใน {names[side]}", 2.8, "center",
                    "text", True)
            th_ = min(float(CAT.finish_of(rm).get("tile_h") or 2.0), zc)
            sh.text((x + w_ / 2, oy - 17), f"({side_name[side]}) 1:{sc} · กรุกระเบื้อง "
                                           f"0.30×0.60 สูง {th_:.2f} ม.", 2.0, "center")
            x += w_ + 44
        sh.text((x0 + 2, y + 6), f"{rm.get('name')} · ชั้น {k + 1} · "
                                 f"{rm['w']:.2f}×{rm['d']:.2f} ม. — พื้นต่ำกว่าห้องข้างเคียง "
                                 f"0.05 ม. ลาดเข้าฟลอร์เดรน 1:100", 3.0, "left", "text", True)
        y = oy - 30
    if y - (y0 + 36) >= 66:
        bot = bath_heights_table(sh, x0 + 2, y)
        bath_pipe_section(sh, x0 + 150, y - 4, min(x1 - x0 - 155, 210), y - y0 - 40)
        _ = bot
    notes_block(sh, x0 + 2, y0 + 30, "หมายเหตุ", [
        "1. กระเบื้องผนัง 0.30×0.60 ม. ปูด้วยกาวซีเมนต์ ยาแนวกันเชื้อรา แนวตั้งสลับครึ่งแผ่น",
        "2. ผนังเหนือกระเบื้องฉาบปูนเรียบ ทาสีชนิดกันชื้น ฝ้าเพดานเป็นชนิดกันชื้น",
        "3. ระดับและตำแหน่งสุขภัณฑ์เป็นค่าโดยประมาณ ให้ตรวจสอบกับสุขภัณฑ์ที่ใช้จริง"],
        width=120)
    caption(sh, ((x0 + x1) / 2, y0 + 6), "รูปด้านภายในห้องน้ำ", "1:50")
    return True


#: mounting heights in a bathroom, from its finished floor (มาตรฐานทั่วไป
#: ของแบบบ้าน/อาคารราชการ — ตรวจกับสุขภัณฑ์ที่ใช้จริง)
BATH_HEIGHTS = [
    ("สายฉีดชำระ", "0.30"),
    ("โถส้วมชักโครก (ขอบบนโถ)", "0.40"),
    ("ราวจับ (โถส้วม / อ่างล้างหน้า)", "0.70–0.80"),
    ("ที่ใส่กระดาษชำระ", "0.80"),
    ("อ่างล้างหน้า (ขอบบนอ่าง)", "0.80"),
    ("ก๊อกฝักบัว / วาล์วผสม", "1.00"),
    ("กระจกเงา (ขอบล่าง เหนืออ่าง 0.20)", "1.00"),
    ("ที่ใส่สบู่", "1.20"),
    ("ราวแขวนผ้า", "1.50"),
    ("เต้ารับเครื่องทำน้ำอุ่น (กันน้ำ)", "1.60"),
    ("ฝักบัวก้านแข็ง (เหนือก๊อก 0.80)", "1.80"),
]


def bath_heights_table(sh, x, y):
    """ตารางระดับติดตั้งสุขภัณฑ์และอุปกรณ์ — returns the y below it."""
    sh.text((x, y + 1.5), "ตารางระดับติดตั้งสุขภัณฑ์และอุปกรณ์ (จากระดับพื้นห้องน้ำ)", 2.6,
            "left", "text", True)
    return table(sh, x, y - 1, [("รายการ", 100.0, "left"), ("สูงจากพื้น (ม.)", 36.0, "center")],
                 BATH_HEIGHTS, h=2.1, row_h=4.6, head_h=5.5)


def bath_pipe_section(sh, x, y, w, h):
    """รูปตัดแสดงแนวท่อห้องน้ำ (ไม่ตามมาตราส่วน): the WC dropping into
    the soil pipe to the septic tank, the basin, shower and floor drain
    into the grey-water pipe to the manhole — each falling 1:100, the two
    at different depths so they never cross; the vent from the tank."""
    if w < 120 or h < 62:
        return
    sh.text((x, y + 1.5), "รูปตัดแสดงแนวท่อน้ำทิ้ง/ท่อโสโครกห้องน้ำ (ไม่ตามมาตราส่วน)", 2.6,
            "left", "text", True)
    gy = y - 36.0                         # ground / floor line
    wall_x = x + w * 0.55
    # floor slab and the outside wall
    sh.rect(x, gy - 3, wall_x + 3, gy, "cut", 0.35)
    sh.line((x, gy + 0.6), (wall_x, gy + 0.6), "hatch", 0.13)
    sh.rect(wall_x, gy, wall_x + 3, y - 8, "cut", 0.35)
    sh.line((wall_x + 3, gy), (x + w, gy), "cut", 0.5)
    for i in range(int((x + w - wall_x - 3) / 3)):
        xx = wall_x + 4 + i * 3
        sh.line((xx, gy), (xx - 1.5, gy - 1.5), "hatch", 0.13)
    sh.text((x + 1, gy + 1.5), "พื้นห้องน้ำ -0.05", 1.8)
    # WC
    wx = x + 12
    sh.rect(wx - 4, gy + 9, wx + 1, gy + 19, "fixture", 0.25)
    sh.poly([(wx - 1, gy), (wx + 7, gy), (wx + 9, gy + 8), (wx - 3, gy + 8)], "fixture", 0.25)
    sh.text((wx + 2, gy + 21), "โถส้วม", 1.8, "center")
    # basin
    bx_ = x + 34
    sh.poly([(bx_ - 5, gy + 16), (bx_ + 5, gy + 16), (bx_ + 3, gy + 13), (bx_ - 3, gy + 13)],
            "fixture", 0.25)
    sh.line((bx_, gy + 13), (bx_, gy + 9), "pipe", 0.35)
    sh.arc((bx_ + 1.5, gy + 9), 1.5, 180, 360, "pipe", 0.35)
    sh.line((bx_ + 3, gy + 9), (bx_ + 3, gy), "pipe", 0.35)
    sh.text((bx_, gy + 18), "อ่างล้างหน้า (P-trap)", 1.8, "center")
    # shower + floor drain
    sx_ = x + 52
    sh.line((sx_, gy + 10), (sx_, gy + 27), "pipe", 0.25)
    sh.line((sx_, gy + 27), (sx_ - 4, gy + 27), "pipe", 0.25)
    sh.circle((sx_ - 4, gy + 25.8), 1.2, "fixture", 0.25)
    sh.rect(sx_ - 1, gy - 0.5, sx_ + 2, gy + 0.5, "fixture", 0.25)
    sh.text((sx_, gy + 29), "ฝักบัว · ฟลอร์เดรน", 1.8, "center")
    # soil pipe: deep, to the tank
    zs0, zs1 = gy - 9, gy - 12
    tank_x0 = x + w - 34
    sh.line((wx + 3, gy), (wx + 3, zs0), "pipe", 0.6)
    sh.line((wx + 3, zs0), (tank_x0, zs1), "pipe", 0.6)
    sh.rect(tank_x0, gy - 30, x + w - 8, gy + 1.5, "struct", 0.35)
    sh.line((x + w - 12, gy + 1.5), (x + w - 12, gy + 14), "pipe", 0.35)
    sh.text((x + w - 11, gy + 14.5), "ท่ออากาศ PVC Ø 2\"", 1.7)
    sh.text(((tank_x0 + x + w - 8) / 2, gy - 18), "ถังบำบัดสำเร็จรูป", 1.8, "center")
    sh.text(((tank_x0 + x + w - 8) / 2, gy - 21.5), "(มอก.) ท่อออก Ø 4\"", 1.6, "center")
    sh.text(((wx + tank_x0) / 2, zs0 - 4.5),
            "ท่อโสโครก PVC Ø 4\" ลาดเอียง 1:100 (ลึก 0.75 ม.)", 1.8, "center")
    # grey water: shallow, to the manhole
    zg0, zg1 = gy - 4, gy - 5.5
    mh_x = wall_x + 18
    sh.line((bx_ + 3, gy), (bx_ + 3, zg0), "pipe", 0.35)
    sh.line((sx_ + 0.5, gy - 0.5), (sx_ + 0.5, zg0 + 0.2), "pipe", 0.35)
    sh.line((bx_ + 3, zg0), (mh_x - 4, zg1), "pipe", 0.35, True)
    sh.rect(mh_x - 4, gy - 10, mh_x + 4, gy + 0.8, "struct", 0.35)
    sh.text((mh_x, gy + 2.2), "บ่อพัก", 1.7, "center")
    sh.text(((bx_ + mh_x) / 2 + 6, zg1 + 1.6), "ท่อน้ำทิ้ง PVC Ø 2\" ลาด 1:100 (ลึก 0.35 ม.)",
            1.7, "center")
    sh.text((x, gy - 26),
            "ท่อน้ำทิ้งอยู่สูงกว่าท่อโสโครก ไม่ตัด/ไม่ขี่กัน · ทุกจุดเปลี่ยนทิศใช้ข้อโค้ง 45° 2 ตัว "
            "หรือ Y-branch และมีช่องทำความสะอาด (Cleanout)", 1.7)


def _bars(text):
    """("2-DB12") → (2, "DB12", 12) · ("DB12@0.15") → (0, "DB12", 12, 0.15)."""
    import re
    t = str(text or "")
    m = re.match(r"\s*(\d+)\s*-\s*([A-Z]+)\s*(\d+)", t)
    if m:
        return int(m.group(1)), f"{m.group(2)}{m.group(3)}", int(m.group(3)), 0.0
    m = re.match(r"\s*([A-Z]+)\s*(\d+)\s*@\s*([\d.]+)", t)
    if m:
        return 0, f"{m.group(1)}{m.group(2)}", int(m.group(2)), float(m.group(3))
    return 0, t, 12, 0.0


def s_rebar_details(sh, E):
    """แบบขยายเหล็กเสริมฐานรากและคาน: each footing type in section and
    plan (the mat, the stump's starter bars, cover, lean concrete, sand,
    piles), then each beam type along a span (top and bottom bars, the
    stirrups closer at the supports, laps) with its sections A-A, B-B."""
    x0, y0, x1, y1 = drawing_area()
    lib = E["lib"]
    used = {e["mark"] for key in ("footings", "stumps", "beams") for e in E[key]}
    foots = sorted(m for m in used if lib.get(m, {}).get("kind") == "footing")[:2]
    stump = next((lib[m] for m in sorted(used) if lib.get(m, {}).get("kind") == "stump"),
                 {"b": 0.2, "h": 0.2, "main": "4-DB12", "tie": "RB6@0.15"})
    k = 1000.0 / 25                                   # footings 1:25
    x = x0 + 18
    ytop = y1 - 12
    for m in foots:
        f = lib[m]
        w, l, t = float(f["w"]), float(f["l"]), float(f["t"])
        depth = float(f.get("depth") or 1.5)
        sand, lean = float(f.get("sand") or 0.05), float(f.get("lean") or 0.05)
        n_, bar, dmm, sp = _bars(f.get("bars"))
        base = ytop - (depth + sand + lean + 0.1) * k
        gy = base + (sand + lean + depth) * k           # ground line
        # sand, lean concrete, the footing
        sh.rect(x - 0.05 * k, base, x + (w + 0.05) * k, base + sand * k, "hatch", 0.18)
        sh.fill([(x - 0.05 * k, base + sand * k), (x + (w + 0.05) * k, base + sand * k),
                 (x + (w + 0.05) * k, base + (sand + lean) * k),
                 (x - 0.05 * k, base + (sand + lean) * k)], "hatch", 0.85)
        fb = base + (sand + lean) * k
        sh.rect(x, fb, x + w * k, fb + t * k, "cut", 0.5)
        # the stump up to the ground line
        sb = float(stump["b"])
        cx = x + w * k / 2
        sh.rect(cx - sb * k / 2, fb + t * k, cx + sb * k / 2, gy + 0.3 * k, "cut", 0.5)
        # bottom mat: bars across (dots) and one along with 90° hooks
        cov = 0.075
        zb = fb + cov * k
        nb = max(int(round(w / (sp or 0.15))), 2)
        for i in range(nb + 1):
            bx = x + (cov + (w - 2 * cov) * i / nb) * k
            sh.circle((bx, zb + 0.4), 0.45, "rebar", 0.25)
        hook = min(0.20, t - 2 * cov + 0.05)
        sh.poly([(x + cov * k, zb + hook * k), (x + cov * k, zb - 0.1),
                 (x + (w - cov) * k, zb - 0.1), (x + (w - cov) * k, zb + hook * k)],
                "rebar", 0.45, closed=False)
        # starter bars of the stump, bent 0.30 into the mat
        for sx in (-1, 1):
            bx = cx + sx * (sb / 2 - 0.04) * k
            sh.poly([(bx, gy + 0.3 * k), (bx, zb + 0.9), (bx + sx * 0.30 * k, zb + 0.9)],
                    "rebar", 0.45, closed=False)
        for j in range(1, 6):                            # stump ties
            zz = fb + t * k + j * 0.15 * k
            if zz > gy + 0.25 * k:
                break
            sh.line((cx - (sb / 2 - 0.03) * k, zz), (cx + (sb / 2 - 0.03) * k, zz),
                    "rebar", 0.25)
        piles = int(f.get("piles") or 0)
        if piles:
            pb = float(f.get("pile_b") or 0.18)
            for i in range(min(piles, 2)):
                px_ = x + w * k * ((i + 1) / (min(piles, 2) + 1))
                sh.rect(px_ - pb * k / 2, base - 0.6 * k, px_ + pb * k / 2, fb + 0.05 * k,
                        "cut", 0.35, dash=True)
            sh.text((x + w * k / 2, base - 0.6 * k - 4),
                    f"เสาเข็ม {piles} ต้น {pb:.2f}×{pb:.2f}×{float(f.get('pile_len') or 6):.0f} ม.",
                    2.0, "center")
        sh.line((x - 0.4 * k, gy), (x + (w + 0.4) * k, gy), "cut", 0.35)
        sh.text((x + (w + 0.4) * k, gy + 1), "ระดับดินเดิม", 1.8, "right")
        # notes on the right of it
        tx = x + (w + 0.15) * k + 2
        sh.text((tx, fb + t * k * 0.5), f"{bar}@{sp or 0.15:.2f} ทั้ง 2 ทาง", 2.0)
        sh.text((tx, fb + t * k * 0.5 - 3), "งอฉาก 90° ปลายเหล็ก", 1.8)
        sh.text((tx, fb - 1.5), f"คอนกรีตหยาบ {lean:.2f} ม. · ทรายอัดแน่น {sand:.2f} ม.", 1.8)
        sh.text((tx, gy - 6), f"ตอม่อ {stump['b']:.2f}×{stump['h']:.2f} ม.", 1.8)
        sh.text((tx, gy - 9), f"{stump.get('main', '')} ปลอก {stump.get('tie', '')}", 1.8)
        _dim_h(sh, x, x + w * k, base - 3, f"{w:.2f}")
        _dim_v(sh, x - 6, fb, fb + t * k, f"{t:.2f}")
        _dim_v(sh, x - 11, fb + t * k, gy, f"{(gy - fb - t * k) / k:.2f}")
        sh.text((x + w * k / 2, base - 12), f"รูปตัดฐานราก {m}", 2.8, "center", "text", True)
        sh.text((x + w * k / 2, base - 16), f"{w:.2f}×{l:.2f}×{t:.2f} ม. · ลึก {depth:.2f} ม. · 1:25",
                2.0, "center")
        # plan of the mat
        py = base - 70
        pw, pl = w * k * 0.6, l * k * 0.6               # 1:40 plan
        sh.rect(x, py, x + pw, py + pl, "cut", 0.4)
        nbx = max(int(round(w / (sp or 0.15))), 2)
        nby = max(int(round(l / (sp or 0.15))), 2)
        c_ = cov * k * 0.6
        for i in range(nbx + 1):
            bx = x + c_ + (pw - 2 * c_) * i / nbx
            sh.line((bx, py + c_), (bx, py + pl - c_), "rebar", 0.18)
        for i in range(nby + 1):
            by = py + c_ + (pl - 2 * c_) * i / nby
            sh.line((x + c_, by), (x + pw - c_, by), "rebar", 0.18)
        sh.rect(x + pw / 2 - sb * k * 0.3, py + pl / 2 - sb * k * 0.3,
                x + pw / 2 + sb * k * 0.3, py + pl / 2 + sb * k * 0.3, "cut", 0.35)
        sh.text((x + pw / 2, py - 5), f"แปลนเหล็กเสริมฐานราก {m} 1:40", 2.2, "center",
                "text", True)
        x += max(w * k, pw) + 80
    # beams: a typical span 1:30 and two sections 1:15
    beams = sorted(m for m in used if lib.get(m, {}).get("kind") == "beam")
    seen, kinds = set(), []
    for m in beams:
        sp_ = lib[m]
        key = (sp_.get("b"), sp_.get("h"), sp_.get("top"), sp_.get("bot"), sp_.get("stir"))
        if key in seen:
            continue
        seen.add(key)
        kinds.append((m, sp_, [mm for mm in beams if (lib[mm].get("b"), lib[mm].get("h"),
                                                     lib[mm].get("top"), lib[mm].get("bot"),
                                                     lib[mm].get("stir")) == key]))
    yb = y0 + 78
    if len(kinds) > 1:
        sh.text((x0 + 2, y0 + 20), "คานเบอร์อื่น: รายละเอียดการเสริมเหล็กเหมือนรูปขยายนี้ "
                "ขนาดและจำนวนเหล็กตามตารางคาน", 2.0)
    for m, b_, marks in kinds[:1]:
        kb = 1000.0 / 30
        b, h = float(b_["b"]), float(b_["h"])
        span = 3.0
        cw = 0.20
        bx0 = x0 + 22
        top_n, top_bar, top_d, _ = _bars(b_.get("top"))
        bot_n, bot_bar, bot_d, _ = _bars(b_.get("bot"))
        _n, st_bar, _d, st_sp = _bars(b_.get("stir"))
        st_sp = st_sp or 0.15
        Y = yb
        # columns at both ends, beam between
        for cxm in (0.0, span + cw):
            sh.rect(bx0 + cxm * kb, Y - 0.5 * kb, bx0 + (cxm + cw) * kb, Y + (h + 0.4) * kb,
                    "cut", 0.35)
        sh.rect(bx0 + cw * kb, Y, bx0 + (cw + span) * kb, Y + h * kb, "cut", 0.5)
        cv = 0.03
        # top and bottom bars, run into the columns with 90° hooks
        ytb, ybb = Y + (h - cv - 0.01) * kb, Y + (cv + 0.01) * kb
        xa, xb = bx0 + 0.04 * kb, bx0 + (span + 2 * cw - 0.04) * kb
        sh.poly([(xa, ytb - 0.25 * kb), (xa, ytb), (xb, ytb), (xb, ytb - 0.25 * kb)],
                "rebar", 0.5, closed=False)
        sh.poly([(xa, ybb + 0.25 * kb), (xa, ybb), (xb, ybb), (xb, ybb + 0.25 * kb)],
                "rebar", 0.5, closed=False)
        # stirrups: s/2 over L/4 at each support, s in the middle
        q = span / 4
        z_ = 0.05
        while z_ <= span - 0.05 + 1e-6:
            xs_ = bx0 + (cw + z_) * kb
            sh.line((xs_, Y + cv * kb), (xs_, Y + (h - cv) * kb), "rebar", 0.18)
            near = z_ < q or z_ > span - q
            z_ += st_sp / 2 if near else st_sp
        _dim_h(sh, bx0 + cw * kb, bx0 + (cw + q) * kb, Y - 5, f"L/4 @{st_sp / 2:.3f}")
        _dim_h(sh, bx0 + (cw + q) * kb, bx0 + (cw + span - q) * kb, Y - 5, f"L/2 @{st_sp:.2f}")
        _dim_h(sh, bx0 + (cw + span - q) * kb, bx0 + (cw + span) * kb, Y - 5,
               f"L/4 @{st_sp / 2:.3f}")
        sh.text((bx0 + (cw + span / 2) * kb, Y + h * kb + 7),
                f"เหล็กบน {b_.get('top', '')} · เหล็กล่าง {b_.get('bot', '')} · "
                f"ปลอก {st_bar} (ช่วงหัวเสา @{st_sp / 2:.3f} กลางช่วง @{st_sp:.2f})",
                2.0, "center")
        sh.text((bx0 + (cw + span / 2) * kb, Y - 13),
                f"รูปขยายคาน {', '.join(marks)} {b:.2f}×{h:.2f} ม. 1:30", 2.8, "center",
                "text", True)
        sh.text((bx0 + (cw + span / 2) * kb, Y - 17),
                "ต่อทาบเหล็กบนช่วงกลางคาน เหล็กล่างที่หัวเสา ระยะทาบ 40d (DB) / 48d (RB)",
                1.8, "center")
        for cxm, lab in ((cw + 0.6, "A"), (cw + span / 2, "B")):
            xx = bx0 + cxm * kb
            sh.line((xx, Y - 2), (xx, Y + h * kb + 2), "dim", 0.25, dash=True)
            sh.text((xx + 1, Y + h * kb + 2.5), lab, 2.2, "left", "dim", True)
        # sections A-A (support) and B-B (mid span) 1:15
        ks = 1000.0 / 15
        for i, (lab, n_top, n_bot) in enumerate((("A-A (ที่หัวเสา)", top_n, bot_n),
                                                 ("B-B (กลางช่วง)", top_n, bot_n))):
            sx = bx0 + (span + 2 * cw) * kb + 25 + i * (b * ks + 32)
            sh.rect(sx, Y, sx + b * ks, Y + h * ks, "cut", 0.5)
            sh.rect(sx + cv * ks, Y + cv * ks, sx + (b - cv) * ks, Y + (h - cv) * ks,
                    "rebar", 0.25)
            sh.line((sx + (b - cv) * ks, Y + (h - cv) * ks),
                    (sx + (b - cv - 0.05) * ks, Y + (h - cv - 0.05) * ks), "rebar", 0.25)
            for nn, yy in ((max(n_top, 2), Y + (h - cv - 0.012) * ks),
                           (max(n_bot, 2), Y + (cv + 0.012) * ks)):
                for j in range(nn):
                    bxx = sx + (cv + 0.012 + (b - 2 * cv - 0.024) * j / max(nn - 1, 1)) * ks
                    sh.circle((bxx, yy), 0.9, "rebar", 0.35)
            sh.text((sx + b * ks / 2, Y + h * ks + 2.5), b_.get("top", ""), 1.8, "center")
            sh.text((sx + b * ks / 2, Y - 3.5), b_.get("bot", ""), 1.8, "center")
            sh.text((sx + b * ks + 1.5, Y + h * ks / 2), st_bar, 1.6, "left")
            sh.text((sx + b * ks / 2, Y - 9), f"รูปตัด {lab}", 2.2, "center", "text", True)
            _dim_h(sh, sx, sx + b * ks, Y + h * ks + 6, f"{b:.2f}")
    notes_block(sh, x1 - 120, y1 - 10, "หมายเหตุเหล็กเสริม", [
        "1. ระยะหุ้มคอนกรีต: ฐานราก 7.5 ซม. ตอม่อ/เสา 3.5 ซม. คาน 3.0 ซม. พื้น 2.0 ซม.",
        "2. เหล็กปลอกงอขอ 135° ยาวไม่น้อยกว่า 6d ระยะแรกห่างผิวเสา 5 ซม.",
        "3. ระยะทาบ: เหล็กข้ออ้อย 40d เหล็กเส้นกลม 48d (มีขอ) ห้ามต่อทาบในตำแหน่งเดียวกันเกิน 50%",
        "4. เหล็กเสริมตามมาตรฐาน มอก. 24 (SD40) และ มอก. 20 (SR24)"], width=118)
    caption(sh, ((x0 + x1) / 2, y0 + 4), "แบบขยายเหล็กเสริมฐานรากและคาน", "ตามระบุ")
    return True


# ---------------------------------------------------------------------------
# รูปตัดทัศนียภาพ: the building cut open along a section line and drawn as a
# parallel 3D view, hidden lines removed, the cut walls / beams / slabs
# filled black — vectors, so the PDF and the DXF carry the same drawing
# ---------------------------------------------------------------------------

#: parts left out of the cut-away view: the covering (the frame shows, as
#: the standard 3D sections do), small fixings, services and the yard
AXO_SKIP = {"tiles", "skin", "cap", "headplate", "ceiling_frame", "soffit_fix",
            "light", "outlet", "panel", "ground_rod", "fan", "pipe_supply",
            "pipe_drain", "septic", "grease", "meter", "walkway", "drain_ring",
            "drain_pipe", "manhole", "ac_out", "ac_bracket", "sign", "gutter"}


def _axo_geometry(groups):
    import numpy as np
    tris, hard = [], []
    for g in groups:
        rec = (getattr(g, "ext", None) or {}).get(B.EXT_KEY) or {}
        if rec.get("kind") in AXO_SKIP or getattr(g, "hidden", False):
            continue
        for f in g.mesh.faces:
            for a, b, c in f.triangulate():
                tris.append(((a.x(), a.y(), a.z()), (b.x(), b.y(), b.z()),
                             (c.x(), c.y(), c.z())))
        for e in g.mesh.edges:
            if getattr(e, "soft", False) or getattr(e, "hidden", False):
                continue
            p0, p1 = e.v0.position, e.v1.position
            hard.append(((p0.x(), p0.y(), p0.z()), (p1.x(), p1.y(), p1.z())))
    return (np.array(tris, dtype=float).reshape(-1, 3, 3),
            np.array(hard, dtype=float).reshape(-1, 2, 3),
            np.empty((0, 2, 3)), np.empty((0, 2, 3)))


def section_axo(groups, cut, yaw_off=35.0, pitch=26.0):
    """The cut-away drawing of ``groups`` along ``cut`` (a
    :func:`section_cuts` entry): the part on the near side of the cut is
    taken away and the rest seen from there, obliquely from above —
    a :class:`core.hlr.HlrDrawing` (camera-plane metres)."""
    from PySide6.QtGui import QVector3D

    from core import hlr
    from core.camera import OrbitCamera
    from core.section import SectionPlane
    axis, at = cut[0], float(cut[1])
    geo = _axo_geometry(groups)
    if not len(geo[0]):
        return None
    if axis == "x":
        plane = SectionPlane(QVector3D(at, 0, 0), QVector3D(-1, 0, 0), active=True)
        yaw = 180.0 + yaw_off
    else:
        plane = SectionPlane(QVector3D(0, at, 0), QVector3D(0, -1, 0), active=True)
        yaw = -90.0 - yaw_off

    class _Cut:
        show_section_cuts = True

        def active_section(self):
            return plane
    pts = geo[0].reshape(-1, 3)
    lo, hi = pts.min(axis=0), pts.max(axis=0)
    cam = OrbitCamera()
    cam.perspective = False
    cam.yaw, cam.pitch = math.radians(yaw), math.radians(pitch)
    cam.fit_box(QVector3D(*lo), QVector3D(*hi))
    return hlr.hlr_drawing(_Cut(), cam, geometry=geo)


def a_axo_sheet(sh, dr, cut, k):
    """One cut-away on a sheet: fitted to the drawing area, the cut faces
    filled, the cut chords heavy, outlines medium, the rest fine."""
    x0, y0, x1, y1 = drawing_area()
    if dr is None or not len(dr.segs):
        sh.text(((x0 + x1) / 2, (y0 + y1) / 2), "ไม่มีชิ้นส่วนสำหรับรูปตัด", 4, "center")
        return
    import numpy as np
    xs = np.concatenate([dr.segs[:, 0], dr.segs[:, 2]])
    ys = np.concatenate([dr.segs[:, 1], dr.segs[:, 3]])
    w, h = float(xs.max() - xs.min()) or 1.0, float(ys.max() - ys.min()) or 1.0
    bw, bh = (x1 - x0) - 20, (y1 - y0) - 34
    sc = min(bw / w, bh / h)
    ox = x0 + 10 + (bw - w * sc) / 2 - float(xs.min()) * sc
    oy = y0 + 24 + (bh - h * sc) / 2 - float(ys.min()) * sc

    def P(x, y):
        return (ox + x * sc, oy + y * sc)
    from core import hlr
    for loop in dr.loops:
        if len(loop) >= 3:
            sh.fill([P(*q) for q in loop], "hatch", 0.18)
    widths = {getattr(hlr, "KIND_CUT", 2): 0.35, getattr(hlr, "KIND_PROFILE", 1): 0.25}
    for (a, b, c, d), kind in zip(dr.segs, dr.kinds):
        sh.line(P(a, b), P(c, d), "cut" if kind == getattr(hlr, "KIND_CUT", 2) else "wall",
                widths.get(int(kind), 0.13))
    caption(sh, ((x0 + x1) / 2, y0 + 10),
            f"รูปตัดทัศนียภาพ {cut[2]} (ตัดผ่าน{cut[3]})", "ภาพ 3 มิติ ไม่ระบุมาตราส่วน")


def axo_sheets(data, group="A"):
    """(Sheet, painter) for every floor's two cuts as cut-away 3D views."""
    E = B.elements(data)
    if not E["floors"] or not E["footings"]:
        return []
    d = dict(data, settings=dict(data.get("settings") or {}, tiles_3d=False))
    groups, _c = B.build(d)
    out = []
    seen = set()
    for k in range(E["n"]):
        for cut in section_cuts(E, k):
            key = (cut[0], round(float(cut[1]), 3))
            if key in seen:                 # the same plane cuts every floor
                continue
            seen.add(key)

            def paint(sh, _a, cut=cut, k=k):
                a_axo_sheet(sh, section_axo(groups, cut), cut, k)
            out.append((f"รูปตัดทัศนียภาพ {cut[2]}", paint))
    return out


def build_sections(data, info=None) -> list:
    """The building sections alone: one sheet per floor (X and Y, the
    first through a bathroom), framed and numbered."""
    info = dict(info or {})
    E = B.elements(data)
    if not E["floors"] or not E["footings"]:
        return []
    L = B.roof_lines(data)
    out = []
    for k in range(E["n"]):
        cuts = section_cuts(E, k)
        sh = Sheet(f"A-S{k + 1}", " ".join(f"รูปตัด {c[2]}" for c in cuts) or "รูปตัด",
                   "-", "A")
        out.append(sh)
    painters = [lambda sh, i=i: _set_scale(sh, a_section_sheet(sh, E, L, i))
                for i in range(len(out))]
    if info.get("axo_sections"):
        for title, paint in axo_sheets(data):
            out.append(Sheet(f"A-S{len(out) + 1}", title, "-", "A"))
            painters.append(lambda sh, p=paint: p(sh, None))
    for i, (sh, paint) in enumerate(zip(out, painters), 1):
        sh.number = i
        paint(sh)
        frame(sh, info, len(out))
    return out


# ---------------------------------------------------------------------------
# Front matter: the cover and the contents (สารบัญ), as the standard sets
# open (แบบบ้านเพื่อประชาชน / บ้านสานฝัน …) — no emblem, the owner's own set
# ---------------------------------------------------------------------------

def g_cover(sh, E, info, sheets, boq):
    W, H_ = PAPER
    m = MARGIN
    sh.rect(m, m, W - m, H_ - m, "frame", 0.7)
    sh.rect(m + 3, m + 3, W - m - 3, H_ - m - 3, "frame", 0.25)
    cx = W / 2
    if info.get("cover_image"):
        return _cover_with_picture(sh, E, info, sheets, boq)
    sh.text((cx, H_ - 48), "แบบก่อสร้าง", 9.0, "center", "title", True)
    proj = info.get("project") or "อาคาร"
    for i, line in enumerate(_wrap(proj, 40)[:2]):
        sh.text((cx, H_ - 72 - i * 12), line, 10.0, "center", "title", True)
    y = H_ - 104
    for line in info.get("summary") or []:
        sh.text((cx, y), line, 4.0, "center", "text")
        y -= 7
    if info.get("location"):
        sh.text((cx, y - 3), f"สถานที่ก่อสร้าง {info['location']}", 4.2, "center", "text")
        y -= 10
    if info.get("owner"):
        sh.text((cx, y - 3), f"เจ้าของ {info['owner']}", 4.2, "center", "text")
        y -= 10
    groups = []
    for g, th in GROUP_TH.items():
        n = sum(1 for s in sheets if s.group == g) if g != "BOQ" else len(boq)
        if n and g != "G":
            groups.append(f"{th} {n} แผ่น")
    y -= 6
    for i, line in enumerate(groups):
        sh.text((cx, y - i * 6.5), "• " + line, 3.4, "center", "text")
    yb = m + 42
    sh.line((cx - 45, yb + 8), (cx + 45, yb + 8), "title", 0.13, True)
    sh.text((cx, yb + 3), f"({NAME})", 4.2, "center", "title", True)
    sh.text((cx, yb - 3), ROLE, 3.4, "center", "title")
    sh.text((cx, m + 18), f"{info.get('office') or 'WANICNSURVEY'} · "
                          f"{info.get('date') or thai_date()}", 3.0, "center", "title")
    sh.text((cx, m + 10), f"จัดทำด้วย WANICNSURVEY · {FULL}", 2.2, "center", "title")


def _cover_with_picture(sh, E, info, sheets, boq):
    """The cover with the building as the 3D model shows it (the picture
    the export took of the model) under the title, the summary and the
    sheet families beside each other beneath it."""
    W, H_ = PAPER
    m = MARGIN
    cx = W / 2
    sh.text((cx, H_ - 28), "แบบก่อสร้าง", 7.0, "center", "title", True)
    proj = info.get("project") or "อาคาร"
    sh.text((cx, H_ - 42), _wrap(proj, 60)[0], 7.0, "center", "title", True)
    box = (cx - 115, H_ - 178, cx + 115, H_ - 52)
    sh.image(box, info["cover_image"])
    sh.rect(*box, "frame", 0.25)
    sh.text((box[2], box[1] - 3.5), "ภาพจำลองอาคารจากโมเดล 3 มิติ", 2.2, "right", "text")
    y = box[1] - 12
    lines = list(info.get("summary") or [])
    if info.get("location"):
        lines.append(f"สถานที่ก่อสร้าง {info['location']}")
    if info.get("owner"):
        lines.append(f"เจ้าของ {info['owner']}")
    for i, line in enumerate(lines[:7]):
        sh.text((cx - 112, y - i * 6.0), line, 3.4, "left", "text")
    groups = []
    for g, th in GROUP_TH.items():
        n = sum(1 for s in sheets if s.group == g) if g != "BOQ" else len(boq)
        if n and g != "G":
            groups.append(f"{th} {n} แผ่น")
    for i, line in enumerate(groups[:7]):
        sh.text((cx + 18, y - i * 6.0), "• " + line, 3.2, "left", "text")
    yb = m + 30
    sh.line((cx - 45, yb + 8), (cx + 45, yb + 8), "title", 0.13, True)
    sh.text((cx, yb + 3), f"({NAME})", 4.0, "center", "title", True)
    sh.text((cx, yb - 3), ROLE, 3.2, "center", "title")
    sh.text((cx, m + 12), f"{info.get('office') or 'WANICNSURVEY'} · "
                          f"{info.get('date') or thai_date()} · จัดทำด้วย WANICNSURVEY · {FULL}",
            2.4, "center", "title")


def g_contents(sh, E, info, sheets, boq):
    """สารบัญ: every family with its sheet range and first page, the bill
    of quantities after them — like the contents page of the standard
    house sets."""
    W, H_ = PAPER
    m = MARGIN
    sh.rect(m, m, W - m, H_ - m, "frame", 0.5)
    cx = W / 2
    sh.text((cx, H_ - 30), "สารบัญ", 6.0, "center", "title", True)
    proj = info.get("project") or "อาคาร"
    sh.text((cx, H_ - 42), proj, 4.6, "center", "title", True)
    sub = f"อาคาร {E['n']} ชั้น"
    sh.fill([(cx - 50, H_ - 57), (cx + 50, H_ - 57), (cx + 50, H_ - 49), (cx - 50, H_ - 49)],
            "hatch", 0.85)
    sh.text((cx, H_ - 55), sub, 3.6, "center", "title", True)
    cols = [(m + 30, m + 175), (cx + 15, W - m - 30)]
    left = [g for g in ("A", "S", "SN", "EE", "M") if any(s.group == g for s in sheets)]
    y = H_ - 78
    x0, x1 = cols[0]
    sh.text((x1, y + 8), "หน้า", 3.4, "right", "title", True)
    for g in left:
        mine = [s for s in sheets if s.group == g]
        sh.text((x0, y), f"{GROUP_TH[g]}", 4.0, "left", "title", True)
        y -= 8
        rng = f"แผ่นที่ {mine[0].code} ถึงแผ่นที่ {mine[-1].code}" if len(mine) > 1 \
            else f"แผ่นที่ {mine[0].code}"
        sh.circle((x0 + 6, y + 1), 0.9, "text", 0.9)
        sh.text((x0 + 10, y), rng, 3.2, "left", "text")
        sh.line((x0 + 10 + len(rng) * 1.7, y + 0.2), (x1 - 12, y + 0.2), "dim", 0.1, True)
        sh.text((x1, y), str(mine[0].number), 3.2, "right", "text")
        y -= 13
    x0, x1 = cols[1]
    y = H_ - 78
    sh.text((x1, y + 8), "หน้า", 3.4, "right", "title", True)
    if boq:
        first = len(sheets) + 1
        sh.text((x0, y), "บัญชีแสดงปริมาณวัสดุและแรงงาน (BOQ)", 4.0, "left", "title", True)
        y -= 8
        rng = f"แบบ ปร.1 จำนวน {len(boq)} แผ่น"
        sh.circle((x0 + 6, y + 1), 0.9, "text", 0.9)
        sh.text((x0 + 10, y), rng, 3.2, "left", "text")
        sh.line((x0 + 10 + len(rng) * 1.7, y + 0.2), (x1 - 12, y + 0.2), "dim", 0.1, True)
        sh.text((x1, y), str(first), 3.2, "right", "text")
        y -= 13
    sh.text((x0, y), "รายการประกอบแบบและสัญลักษณ์", 4.0, "left", "title", True)
    y -= 8
    for g in left:
        idx = next((s for s in sheets if s.group == g), None)
        if idx is None:
            continue
        sh.circle((x0 + 6, y + 1), 0.9, "text", 0.9)
        sh.text((x0 + 10, y), f"{GROUP_TH[g]} — แผ่นที่ {idx.code}", 3.0, "left", "text")
        sh.text((x1, y), str(idx.number), 3.0, "right", "text")
        y -= 7
    sh.text((cx, m + 14), f"({NAME}) {ROLE}", 2.8, "center", "title")
    sh.text((cx, m + 7), f"จัดทำด้วย WANICNSURVEY · {FULL}", 2.0, "center", "title")


# ---------------------------------------------------------------------------
# ปร.1 — the bill of quantities at the end of the book (2569 form names)
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
    """The ปร.1 lines: (kind, cells) — kind "group" / "item" / "total";
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
    from core import wanic_quantities as Q
    t = result.get("totals") or Q._totals(result.get("lines") or [])
    summary.append(("total", ["", "รวมค่าวัสดุและค่าแรงงาน", "",
                              "", "", _money(gm, show_prices), "",
                              _money(gl, show_prices),
                              _money(gm + gl, show_prices), ""]))
    F = t.get("F", 1.0)
    summary.append(("item", ["", "ค่างานต้นทุน (หมวด 1–15 และ 17 ครุภัณฑ์จัดจ้าง)", "", "",
                             "", "", "", "", _money(t.get("work", gm + gl), show_prices),
                             ""]))
    summary.append(("item", ["", "Factor F (ว 481 งานก่อสร้างอาคาร)", "", "", "", "",
                             "", "", f"× {F:.4f}" if show_prices else "",
                             "ค่าจ้างล่วงหน้า 0% ประกันผลงาน 0% VAT 7%"]))
    summary.append(("item", ["", "ค่างานต้นทุน × Factor F", "", "", "", "", "", "",
                             _money(t.get("after_f", (gm + gl) * F), show_prices), ""]))
    if t.get("no_f"):
        summary.append(("item", ["", f"ครุภัณฑ์จัดซื้อ + ภาษีมูลค่าเพิ่ม {Q.VAT_PCT:g}%",
                                 "", "", "", "", "", "",
                                 _money(t["equip"] + t["equip_vat"], show_prices),
                                 "ไม่คูณ Factor F (ปร.2)"]))
        summary.append(("item", ["", "วัสดุ และวัสดุคงทน", "", "", "", "", "", "",
                                 _money(t["supply"], show_prices), "ไม่คูณ Factor F"]))
    summary.append(("total", ["", "รวมเป็นเงินทั้งสิ้น (รวม Factor F แล้ว)", "", "",
                              "", "", "", "", _money(t.get("with_f", (gm + gl) * F),
                                                     show_prices),
                              "ราคานี้รวม Factor F แล้ว"]))
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
    sh.text((W - m - 5, y), "แบบ ปร.1", 3.0, "right", "title", True)
    proj = info.get("project") or "อาคาร"
    sh.text((W / 2, y), "แบบแสดงรายการ ปริมาณงาน และราคา ค่างานต้นทุน  "
            f"{proj}", 3.6, "center", "title", True)
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
    """The ปร.1 pages (A3, same paper as the drawings) from the BOQ of
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
        sh = Sheet(f"ปร.1-{len(pages) + 1}", "แบบแสดงรายการ ปริมาณงาน และราคา ค่างานต้นทุน (ปร.1)",
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
                "ราคาแต่ละรายการคือค่างานต้นทุน · ราคารวมทั้งสิ้นในสรุปงานรวม Factor F แล้ว "
                "(ว 481 งานอาคาร)", 2.0)
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
