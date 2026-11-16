# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
"""สัญลักษณ์ประตู-หน้าต่าง: one geometry for the plan on screen and the
drawing sheets, as the standard sets draw them — a swinging leaf with its
90° arc on the side it opens to (เปิดเข้า / เปิดออก, hinge left or right,
one or two leaves), a sliding pair with arrows, a casement window's arcs
(outward by default), an awning window's dashed «V», louvres as ticks and a
fixed light as a single line.

``symbol(op, p0, p1, rooms, t)`` returns world primitives (metres):
``{"lines": [(a, b)], "dashed": [(a, b)], "arcs": [(centre, r, a0, a1)],
"arrows": [(tail, tip)], "label": (pos, text) | None, "inward": bool}`` —
angles in degrees, counter-clockwise, ``a0 < a1``."""
from __future__ import annotations

import math

from core import wanic_catalog as CAT


def _inside(rooms, x, y) -> bool:
    return any(rm["x"] - 1e-6 <= x <= rm["x"] + rm["w"] + 1e-6 and
               rm["y"] - 1e-6 <= y <= rm["y"] + rm["d"] + 1e-6 for rm in rooms)


def wall_sides(p0, p1, rooms):
    """(u, n, out, exterior): the wall's direction, its normal, the normal
    pointing outside (for an exterior wall) and whether it is exterior."""
    L = math.hypot(p1[0] - p0[0], p1[1] - p0[1]) or 1.0
    u = ((p1[0] - p0[0]) / L, (p1[1] - p0[1]) / L)
    n = (u[1], -u[0])
    mx, my = (p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2
    a = _inside(rooms, mx + n[0] * 0.05, my + n[1] * 0.05)
    b = _inside(rooms, mx - n[0] * 0.05, my - n[1] * 0.05)
    exterior = not (a and b)
    out = (-n[0], -n[1]) if a and not b else n
    return u, n, out, exterior


def kind_of(spec, code) -> str:
    """swing / slide / awning / louvre / fixed — how the leaves move."""
    name = spec.get("name", "")
    if spec.get("slide"):
        return "slide"
    if not int(spec.get("leaves") or 0) or "ติดตาย" in name and "บาน" not in name.replace("ติดตาย", ""):
        return "fixed"
    if "กระทุ้ง" in name:
        return "awning"
    if "เกล็ด" in name:
        return "louvre"
    return "swing"


def symbol(op, p0, p1, rooms, t=0.15, w=None) -> dict:
    """The symbol of opening ``op`` on the wall p0–p1 (see the module doc)."""
    code, spec = CAT.opening_type(op)
    width = float(w or op.get("w") or spec.get("w") or 0.9)
    u, n, out, exterior = wall_sides(p0, p1, rooms)
    # the side the leaves open to: into the building (or the wall's normal side
    # inside it) — or outside / the other side when the opening says «out»
    side = out if exterior else n
    window = spec.get("kind") == "window"
    swing = op.get("swing") or ("out" if window else "in")
    inn = side if swing == "out" else (-side[0], -side[1])
    cx, cy = float(op["x"]), float(op["y"])
    c0, c1 = -width / 2, width / 2

    def at(a, off=0.0, d=inn):
        return (cx + u[0] * a + d[0] * off, cy + u[1] * a + d[1] * off)
    res = {"lines": [], "dashed": [], "arcs": [], "arrows": [], "label": None, "inward": swing != "out",
           "kind": kind_of(spec, code)}
    k = res["kind"]
    leaves = max(1, int(spec.get("leaves") or 1))
    if k == "slide":
        mid = 0.0
        for off, (a, b) in ((t * 0.15, (c0, mid + 0.05)), (-t * 0.15, (mid - 0.05, c1))):
            res["lines"].append((at(a, off, n), at(b, off, n)))
        res["arrows"].append((at(c0 + width * 0.12, t * 0.15 + 0.10, n), at(mid - 0.04, t * 0.15 + 0.10, n)))
        res["arrows"].append((at(c1 - width * 0.12, -t * 0.15 - 0.10, n), at(mid + 0.04, -t * 0.15 - 0.10, n)))
        return res
    if k == "fixed":
        res["lines"].append((at(c0, 0.0, n), at(c1, 0.0, n)))
        return res
    if k == "louvre":
        res["lines"].append((at(c0, 0.0, n), at(c1, 0.0, n)))
        steps = max(3, int(width / 0.08))
        for i in range(1, steps):
            a = c0 + width * i / steps
            res["lines"].append((at(a - 0.03, -t * 0.35), at(a + 0.03, t * 0.35)))
        return res
    if k == "awning":                                   # pushed out at the bottom: a dashed V to the outside
        res["lines"].append((at(c0, 0.0, n), at(c1, 0.0, n)))
        depth = min(0.35, width * 0.4)
        res["dashed"].append((at(c0, t / 2), at(0.0, t / 2 + depth)))
        res["dashed"].append((at(0.0, t / 2 + depth), at(c1, t / 2)))
        res["label"] = (at(0.0, t / 2 + depth + 0.14), "กระทุ้ง")
        return res
    # swinging leaves (doors and casement windows)
    if leaves == 1:
        hinges = [(c1, -1)] if op.get("hinge") == "right" else [(c0, 1)]
    else:
        hinges = [(c0, 1), (c1, -1)]
    leaf = width / len(hinges)
    for hs, sgn in hinges:
        hp = at(hs, t / 2)
        tip = (hp[0] + inn[0] * leaf, hp[1] + inn[1] * leaf)
        res["lines"].append((hp, tip))
        a_open = math.degrees(math.atan2(inn[1], inn[0]))
        a_shut = math.degrees(math.atan2(u[1] * sgn, u[0] * sgn))
        a0, a1 = sorted((a_open, a_shut))
        if a1 - a0 > 180:
            a0, a1 = a1, a0 + 360
        res["arcs"].append((hp, leaf, a0, a1))
    if window:
        res["lines"].append((at(c0, 0.0, n), at(c1, 0.0, n)))
    word = "ออก" if swing == "out" else "เข้า"
    res["label"] = (at(0.0, t / 2 + leaf * 0.55), ("เปิด" + word) if not window else ("เปิด" + word))
    return res


#: the legend, in the order the sheets draw it: (code of a sample, plain words)
LEGEND = (("D1", "in", "ประตูเปิดเข้า"),
          ("D1", "out", "ประตูเปิดออก"),
          ("D2", "in", "ประตูบานเปิดคู่"),
          ("D4", "in", "ประตูบานเลื่อน"),
          ("W1", "out", "หน้าต่างเปิดออก"),
          ("W2", "out", "หน้าต่างบานเลื่อน"),
          ("W3", "out", "หน้าต่างบานกระทุ้ง"),
          ("W5", "out", "หน้าต่างบานเกล็ด"),
          ("W4", "out", "กระจกติดตาย"))
