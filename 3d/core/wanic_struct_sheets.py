# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
"""แบบโครงสร้างจากผลออกแบบ (S sheets drawn from the designed members):

- รายละเอียดคาน — every continuous beam line in elevation: the supports on
  their grid bubbles, the spans, the top bars (the corner bars run through,
  the extra bars over each support reach L/4 into the spans either side),
  the bottom bars (the corner bars run through, the extra bars stop L/5
  from the supports), the stirrups, the level, then the section at the
  start, the middle and the end of each span;
- รายละเอียดฐานราก — every footing mark in plan and in section;
- รายละเอียดเสา — the section of every column mark, storey range by storey
  range (stump → floor 1, floor 1 → floor 2, …);
- รายละเอียดพื้น — every slab mark in a continuous section (top bars L/4
  over the supports, bottom bars through) or on the ground (sand bed).

The bars come from the members' library marks — the same ones the
calculation booklet checks. Paper units are mm (origin lower left)."""
from __future__ import annotations

import math

from core import wanic_drawings as D

SECTION_K = 1000.0 / 25          # the sections at 1:25


def _count(text) -> tuple:
    """("3-DB16") → (3, "DB16")."""
    n, name, _d, _s = D._bars(text)
    return n, name


# ---- beam lines -----------------------------------------------------------------------

def beam_lines(E) -> list:
    """Continuous beam lines: [{"level", "dir", "at", "spans": [(s0, s1, mark)], "z"}]
    with s along the line (m), grouped by level, direction and grid line."""
    groups = {}
    for bm in E["beams"]:
        (x0, y0), (x1, y1) = bm["p0"], bm["p1"]
        if abs(y1 - y0) < 1e-6:
            key = (bm["level"], "x", round(y0, 3))
            a, b = sorted((x0, x1))
        elif abs(x1 - x0) < 1e-6:
            key = (bm["level"], "y", round(x0, 3))
            a, b = sorted((y0, y1))
        else:
            continue
        groups.setdefault(key, []).append((a, b, bm["mark"], float(bm.get("z", 0.0))))
    out = []
    for (lvl, d, at), segs in sorted(groups.items()):
        segs.sort()
        run = [segs[0]]
        for s in segs[1:]:
            if abs(s[0] - run[-1][1]) < 1e-6:
                run.append(s)
            else:
                out.append({"level": lvl, "dir": d, "at": at, "spans": run, "z": run[0][3]})
                run = [s]
        out.append({"level": lvl, "dir": d, "at": at, "spans": run, "z": run[0][3]})
    return out


def line_name(E, ln) -> str:
    xs, ys = D.grids(E)
    if ln["dir"] == "x":
        j = min(range(len(ys)), key=lambda i: abs(ys[i] - ln["at"])) if ys else 0
        return f"แนวแกน {D.axis_name(j)}"
    i = min(range(len(xs)), key=lambda i: abs(xs[i] - ln["at"])) if xs else 0
    return f"แนวแกน {i + 1}"


def level_name(E, lvl) -> str:
    return "คานคอดิน" if lvl == 0 else "คานหลังคา" if lvl == E["n"] else f"คานชั้น {lvl + 1}"


def _support_names(E, ln) -> list:
    xs, ys = D.grids(E)
    pts = [ln["spans"][0][0]] + [s[1] for s in ln["spans"]]
    names = []
    for p in pts:
        if ln["dir"] == "x":
            i = min(range(len(xs)), key=lambda i: abs(xs[i] - p)) if xs else 0
            names.append(str(i + 1) if xs and abs(xs[i] - p) < 1e-3 else "")
        else:
            j = min(range(len(ys)), key=lambda j: abs(ys[j] - p)) if ys else 0
            names.append(D.axis_name(j) if ys and abs(ys[j] - p) < 1e-3 else "")
    return names


def section_bars(sh, x, y, b, h, top_n, bot_n, k=SECTION_K, cov=0.035):
    """A beam / column-face section: outline, stirrup, top and bottom bars."""
    w, hh = b * k, h * k
    sh.rect(x, y, x + w, y + hh, "struct", 0.35)
    c = cov * k
    sh.rect(x + c * 0.7, y + c * 0.7, x + w - c * 0.7, y + hh - c * 0.7, "rebar", 0.18)
    for n, yy in ((top_n, y + hh - c), (bot_n, y + c)):
        n = max(int(n), 0)
        for i in range(n):
            bx = x + c + (w - 2 * c) * (i / (n - 1) if n > 1 else 0.5)
            sh.circle((bx, yy), 0.55, "rebar", 0.35)


def beam_profile(sh, E, ln, x0, ytop, width, k_max=1000.0 / 30) -> float:
    """One beam line from ``ytop`` down; returns the y below it."""
    lib = E["lib"]
    spans = ln["spans"]
    s0 = spans[0][0]
    total = spans[-1][1] - s0
    k = min(k_max, (width - 20) / max(total, 0.5))
    x = x0 + 10
    names = _support_names(E, ln)
    hmax = max(float(lib.get(m, {}).get("h", 0.4)) for _a, _b, m, _z in spans)
    # heading: the line, its level
    sh.text((x0, ytop), f"{level_name(E, ln['level'])} {line_name(E, ln)}", 3.0, "left", "text", True)
    sh.text((x0 + width, ytop), f"ระดับ {ln['z']:+.2f}", 2.4, "right", "struct")
    yb = ytop - 20 - hmax * k                         # beam soffit
    ytopbeam = yb + hmax * k
    # supports: grid bubbles, column stubs, span dimensions
    pts = [spans[0][0]] + [s[1] for s in spans]
    for i, p in enumerate(pts):
        px = x + (p - s0) * k
        sh.line((px, ytopbeam + 13), (px, yb - 6), "grid", 0.13, True)
        if names[i]:
            sh.circle((px, ytopbeam + 15.5), 2.6, "grid", 0.25)
            sh.text((px, ytopbeam + 14.6), names[i], 2.2, "center", "grid")
        cb = 0.2 * k
        sh.rect(px - cb / 2, yb - 5, px + cb / 2, yb, "struct", 0.3)
        sh.rect(px - cb / 2, ytopbeam, px + cb / 2, ytopbeam + 4, "struct", 0.3, True)
    for (a, b_, m, _z) in spans:
        pa, pb = x + (a - s0) * k, x + (b_ - s0) * k
        sh.line((pa, ytopbeam + 9), (pb, ytopbeam + 9), "dim", 0.13)
        for t in (pa, pb):
            sh.line((t - 0.7, ytopbeam + 8.3), (t + 0.7, ytopbeam + 9.7), "dim", 0.25)
        sh.text(((pa + pb) / 2, ytopbeam + 9.7), f"{b_ - a:.2f}", 2.0, "center", "dim")
        sh.rect((pa + pb) / 2 - 5, ytopbeam + 3, (pa + pb) / 2 + 5, ytopbeam + 7, "struct", 0.25)
        sh.text(((pa + pb) / 2, ytopbeam + 3.9), m, 2.2, "center", "struct", True)
    # the beam and its bars
    sh.poly([(x, yb), (x + total * k, yb), (x + total * k, ytopbeam), (x, ytopbeam)], "struct", 0.4)
    cv = 1.2
    ytb, ybb = ytopbeam - cv, yb + cv
    sh.line((x - 1.5, ytb), (x + total * k + 1.5, ytb), "rebar", 0.45)          # top corner bars, through
    sh.line((x - 1.5, ybb), (x + total * k + 1.5, ybb), "rebar", 0.45)          # bottom corner bars, through
    for xe in (x - 1.5, x + total * k + 1.5):                                     # end hooks down / up
        sh.line((xe, ytb), (xe, ytb - min(4.0, hmax * k * 0.5)), "rebar", 0.45)
        sh.line((xe, ybb), (xe, ybb + min(4.0, hmax * k * 0.5)), "rebar", 0.45)
    for i, p in enumerate(pts):                                                   # extra top bars at supports
        left = spans[i - 1] if i > 0 else None
        right = spans[i] if i < len(spans) else None
        marks = [s[2] for s in (left, right) if s]
        nt = max(_count(lib.get(m, {}).get("top"))[0] for m in marks)
        if nt <= 2:
            continue
        la = (left[1] - left[0]) / 4 if left else 0.0
        lb = (right[1] - right[0]) / 4 if right else 0.0
        px = x + (p - s0) * k
        sh.line((px - la * k, ytb - 1.0), (px + lb * k, ytb - 1.0), "rebar", 0.45)
        sh.text((px + 0.1 * k + 1.5, ytopbeam + 1.2), f"{nt}-{_count(lib[marks[0]].get('top'))[1]}", 1.8, "left", "rebar")
        if la:
            sh.text((px - la * k / 2, ytb - 3.6), "L/4", 1.6, "center", "dim")
        if lb:
            sh.text((px + lb * k / 2, ytb - 3.6), "L/4", 1.6, "center", "dim")
    for (a, b_, m, _z) in spans:
        spec = lib.get(m, {})
        nb, bname = _count(spec.get("bot"))
        nt, tname = _count(spec.get("top"))
        pa, pb = x + (a - s0) * k, x + (b_ - s0) * k
        L = b_ - a
        if nb > 2:                                                                # extra bottom bars, L/5 off
            sh.line((pa + L / 5 * k, ybb + 1.0), (pb - L / 5 * k, ybb + 1.0), "rebar", 0.45)
        sh.text(((pa + pb) / 2, yb - 3.2), f"{nb}-{bname}", 1.8, "center", "rebar")
        sh.text(((pa + pb) / 2 + 12, ytopbeam + 1.0), f"{min(nt, 2) if nt else 0}-{tname} ตลอดแนว", 1.6, "left",
                "rebar")
        _n, sname, _d, ss = D._bars(spec.get("stir"))
        if ss:
            step = ss * k
            every = max(1, int(math.ceil(2.6 / step)))
            t = pa + 0.05 * k
            j = 0
            while t < pb - 0.05 * k:
                if j % every == 0:
                    sh.line((t, ybb + 0.3), (t, ytb - 0.3), "rebar", 0.13)
                t += step
                j += 1
            sh.text(((pa + pb) / 2, yb - 6.0), f"ป.{sname}@{ss:.2f}", 1.6, "center", "rebar")
    # sections at the start, the middle and the end of each span
    ys = yb - 13
    sec_h = 0
    for (a, b_, m, _z) in spans:
        spec = lib.get(m, {})
        b, h = float(spec.get("b", 0.2)), float(spec.get("h", 0.4))
        nt, tname = _count(spec.get("top"))
        nb, bname = _count(spec.get("bot"))
        pa, pb = x + (a - s0) * k, x + (b_ - s0) * k
        sk = min(SECTION_K, (pb - pa) / 3 / max(b + 0.25, 0.3))
        for frac, tn, bn in ((0.12, nt, min(nb, 2)), (0.5, min(nt, 2), nb), (0.88, nt, min(nb, 2))):
            cx = pa + (pb - pa) * frac
            sx = cx - b * sk / 2
            sy = ys - h * sk
            section_bars(sh, sx, sy, b, h, tn, bn, sk)
            sh.text((cx, ys + 1.2), f"{tn}-{tname}", 1.5, "center", "rebar")
            sh.text((cx, sy - 2.6), f"{bn}-{bname}", 1.5, "center", "rebar")
            sec_h = max(sec_h, h * sk)
        sh.text(((pa + pb) / 2, ys - sec_h - 6.0), f"{b * 100:.0f}×{h * 100:.0f} ซม.", 1.6, "center", "struct")
    return ys - sec_h - 12


def s_beam_details(sh, E, lines):
    x0, y0, x1, y1 = D.drawing_area()
    y = y1 - 6
    for ln in lines:
        y = beam_profile(sh, E, ln, x0 + 4, y, x1 - x0 - 8)
    D.caption(sh, ((x0 + x1) / 2, y0 + 6), "รายละเอียดคาน", "1:30 (หน้าตัด 1:25)")


def beam_sheets(E, per_sheet_mm=None) -> list:
    """The beam lines shared out over sheets (as many as fit one under the
    other): [[line, …], …]."""
    lib = E["lib"]
    x0, y0, x1, y1 = D.drawing_area()
    room = (y1 - 6) - (y0 + 16)
    sheets, cur, used = [], [], 0.0
    for ln in beam_lines(E):
        spans = ln["spans"]
        total = spans[-1][1] - spans[0][0]
        k = min(1000.0 / 30, (x1 - x0 - 28) / max(total, 0.5))
        hmax = max(float(lib.get(m, {}).get("h", 0.4)) for _a, _b, m, _z in spans)
        sk = SECTION_K
        need = 20 + hmax * k + 10 + hmax * sk + 12
        if cur and used + need > room:
            sheets.append(cur)
            cur, used = [], 0.0
        cur.append(ln)
        used += need
    if cur:
        sheets.append(cur)
    return sheets


# ---- footings ------------------------------------------------------------------------

def s_footing_details(sh, E):
    """Every footing mark: plan above, section below (1:40)."""
    x0, y0, x1, y1 = D.drawing_area()
    lib = E["lib"]
    marks = sorted({f["mark"] for f in E["footings"]})
    stump_mark = next((s["mark"] for s in E["stumps"]), None)
    stump = lib.get(stump_mark, {"b": 0.2, "h": 0.2, "main": "4-DB12", "tie": "RB6@0.15"})
    k = 1000.0 / 40
    n = max(len(marks), 1)
    cw = (x1 - x0) / min(n, 4)
    for i, m in enumerate(marks[:8]):
        f = lib.get(m, {})
        w, l, t = float(f.get("w", 1.0)), float(f.get("l", 1.0)), float(f.get("t", 0.3))
        depth = float(f.get("depth") or 1.5)
        sand, lean = float(f.get("sand") or 0.05), float(f.get("lean") or 0.05)
        _n, bname, _d, sp = D._bars(f.get("bars"))
        nbar = int(round((w - 0.15) / sp)) + 1 if sp else 0
        row = i // 4
        cx = x0 + cw * (i % 4) + cw / 2
        top = y1 - 8 - row * 130
        # plan
        sh.rect(cx - w * k / 2, top - l * k, cx + w * k / 2, top, "struct", 0.4)
        sb = float(stump.get("b", 0.2))
        sh.rect(cx - sb * k / 2, top - l * k / 2 - sb * k / 2, cx + sb * k / 2, top - l * k / 2 + sb * k / 2,
                "struct", 0.3)
        sh.line((cx - w * k / 2, top + 3), (cx + w * k / 2, top + 3), "dim", 0.13)
        sh.text((cx, top + 3.8), f"{w:.2f}", 2.0, "center", "dim")
        sh.text((cx - w * k / 2 - 2, top - l * k / 2), f"{l:.2f}", 2.0, "center", "dim", angle=90)
        piles = int(f.get("piles") or 0)
        if piles:
            pb = float(f.get("pile_b") or 0.18)
            for j in range(piles):
                ang = 2 * math.pi * j / piles + (math.pi / 4 if piles == 4 else 0)
                rr = 0 if piles == 1 else min(w, l) * 0.28
                px, py = cx + rr * math.cos(ang) * k, top - l * k / 2 + rr * math.sin(ang) * k
                sh.rect(px - pb * k / 2, py - pb * k / 2, px + pb * k / 2, py + pb * k / 2, "struct", 0.18, True)
        # section
        base = top - l * k - 20 - (depth + t + sand + lean) * k * 0.0
        gy = base
        fb = gy - depth * k
        sh.line((cx - w * k / 2 - 8, gy), (cx + w * k / 2 + 8, gy), "struct", 0.3)
        sh.text((cx + w * k / 2 + 1, gy + 0.8), "ระดับดินเดิม", 1.6)
        sh.rect(cx - w * k / 2, fb - t * k, cx + w * k / 2, fb, "struct", 0.45)
        sh.rect(cx - sb * k / 2, fb, cx + sb * k / 2, gy + 6, "struct", 0.4)
        sh.rect(cx - w * k / 2 - 1, fb - t * k - lean * k, cx + w * k / 2 + 1, fb - t * k, "hatch", 0.18)
        sh.rect(cx - w * k / 2 - 1, fb - t * k - (lean + sand) * k, cx + w * k / 2 + 1,
                fb - t * k - lean * k, "hatch", 0.13, True)
        cov = 0.075 * k
        zb = fb - t * k + cov
        sh.poly([(cx - w * k / 2 + cov, zb + 4), (cx - w * k / 2 + cov, zb),
                 (cx + w * k / 2 - cov, zb), (cx + w * k / 2 - cov, zb + 4)], "rebar", 0.45, closed=False)
        for j in range(max(nbar, 2)):
            bx = cx - w * k / 2 + cov + (w * k - 2 * cov) * j / max(nbar - 1, 1)
            sh.circle((bx, zb + 0.9), 0.4, "rebar", 0.25)
        for s in (-1, 1):
            bx = cx + s * (sb * k / 2 - 1.0)
            sh.poly([(bx, gy + 6), (bx, zb + 1.6), (bx + s * 4, zb + 1.6)], "rebar", 0.4, closed=False)
        sh.text((cx + w * k / 2 + 1, zb + 1), f"{nbar}-{bname} ทั้งสองทาง", 1.7, "left", "rebar")
        sh.text((cx + w * k / 2 + 1, fb - t * k - (lean + sand) * k - 0.5),
                f"ทราย {sand:.2f} คอนกรีตหยาบ {lean:.2f}", 1.6)
        sh.text((cx - w * k / 2 - 3, (gy + fb) / 2), f"{depth:.2f}", 1.8, "center", "dim", angle=90)
        sh.text((cx - w * k / 2 - 3, fb - t * k / 2), f"{t:.2f}", 1.8, "center", "dim", angle=90)
        sh.circle((cx, fb - t * k - (lean + sand) * k - 8), 3.0, "struct", 0.25)
        sh.text((cx, fb - t * k - (lean + sand) * k - 8.9), m, 2.2, "center", "struct", True)
        if piles:
            sh.text((cx, fb - t * k - (lean + sand) * k - 14), f"เสาเข็ม {piles} ต้น ยาว "
                    f"{float(f.get('pile_len') or 6):.2f} ม.", 1.8, "center")
    D.caption(sh, ((x0 + x1) / 2, y0 + 6), "รายละเอียดฐานราก", "1:40")


# ---- columns -------------------------------------------------------------------------

def column_ranges(E) -> list:
    """[(range title, [marks…])] from the stumps up, storey by storey."""
    out = []
    st = sorted({s["mark"] for s in E["stumps"]})
    if st:
        out.append(("ตอม่อ – พื้นชั้น 1", st))
    for f in range(E["n"]):
        ms = sorted({c["mark"] for c in E["columns"] if int(c.get("floor", 0)) == f})
        if ms:
            to = "หลังคา" if f == E["n"] - 1 else f"พื้นชั้น {f + 2}"
            out.append((f"พื้นชั้น {f + 1} – {to}", ms))
    return out


def column_section(sh, x, y, spec, mark, k=SECTION_K):
    b, h = float(spec.get("b", 0.2)), float(spec.get("h", 0.2))
    n, name = _count(spec.get("main"))
    w, hh = b * k, h * k
    sh.rect(x, y, x + w, y + hh, "struct", 0.4)
    c = 0.035 * k
    sh.rect(x + c * 0.7, y + c * 0.7, x + w - c * 0.7, y + hh - c * 0.7, "rebar", 0.18)
    n = max(n, 4)
    per = [n // 4 + (1 if i < n % 4 else 0) for i in range(4)]
    pts = []
    corners = [(x + c, y + c), (x + w - c, y + c), (x + w - c, y + hh - c), (x + c, y + hh - c)]
    for i in range(4):
        a, b_ = corners[i], corners[(i + 1) % 4]
        for j in range(per[i]):
            t = j / per[i]
            pts.append((a[0] + (b_[0] - a[0]) * t, a[1] + (b_[1] - a[1]) * t))
    for p in pts:
        sh.circle(p, 0.6, "rebar", 0.35)
    sh.line((x, y + hh + 2), (x + w, y + hh + 2), "dim", 0.13)
    sh.text((x + w / 2, y + hh + 2.7), f"{b:.2f}", 1.7, "center", "dim")
    sh.text((x - 2.4, y + hh / 2), f"{h:.2f}", 1.7, "center", "dim", angle=90)
    sh.text((x + w / 2, y - 3), f"{n}-{name}", 1.8, "center", "rebar")
    _n, tname, _d, ts = D._bars(spec.get("tie"))
    sh.circle((x + w / 2, y - 8), 2.6, "struct", 0.25)
    sh.text((x + w / 2, y - 8.8), mark, 2.0, "center", "struct", True)
    sh.text((x + w / 2, y - 14), f"ป. {tname}@{ts:.2f}" if ts else "", 1.7, "center", "rebar")
    sh.text((x + w / 2, y - 17.5), f"ขนาด {b * 100:.0f}×{h * 100:.0f} ซม.", 1.6, "center")


def s_column_details(sh, E):
    x0, y0, x1, y1 = D.drawing_area()
    lib = E["lib"]
    y = y1 - 12
    for title, marks in column_ranges(E):
        sh.rect(x0 + 6, y - 2, x0 + 56, y + 5, "text", 0.3)
        sh.text((x0 + 31, y), title, 2.6, "center", "text", True)
        hmax = max(float(lib.get(m, {}).get("h", 0.2)) for m in marks) * SECTION_K
        for i, m in enumerate(marks):
            column_section(sh, x0 + 75 + i * 40, y - hmax + 6, lib.get(m, {}), m)
        y -= hmax + 32
        if y < y0 + 30:
            break
    D.caption(sh, ((x0 + x1) / 2, y0 + 6), "รายละเอียดเสา", "1:25")


# ---- slabs ---------------------------------------------------------------------------

def s_slab_details(sh, E):
    x0, y0, x1, y1 = D.drawing_area()
    lib = E["lib"]
    marks = sorted({s["mark"] for s in E["slabs"]})
    k = 1000.0 / 25
    y = y1 - 14
    for m in marks:
        spec = lib.get(m, {})
        t = float(spec.get("t", 0.10))
        _n, bname, _d, sp = D._bars(spec.get("bars"))
        ground = bool(spec.get("ground"))
        sh.circle((x0 + 8, y - t * k / 2), 3.0, "struct", 0.25)
        sh.text((x0 + 8, y - t * k / 2 - 0.9), m, 2.2, "center", "struct", True)
        xa = x0 + 18
        if ground:
            L = 2.0
            sh.rect(xa, y - t * k, xa + L * k, y, "struct", 0.4)
            sh.rect(xa, y - t * k - 0.05 * k, xa + L * k, y - t * k, "hatch", 0.13, True)
            sh.line((xa + 1, y - t * k / 2), (xa + L * k - 1, y - t * k / 2), "rebar", 0.4)
            sh.text((xa + L * k + 3, y - t * k / 2), f"{bname}@{sp:.2f} ทั้งสองทาง (หรือตะแกรงเหล็ก)", 1.8)
            sh.text((xa + L * k + 3, y - t * k - 2.5), "พื้นวางบนดิน · ทรายอัดแน่นหนา 0.05 ม.", 1.7)
            sh.text((xa - 2.5, y - t * k / 2), f"{t:.2f}", 1.7, "center", "dim", angle=90)
            y -= t * k + 22
            continue
        L = 2.6                                          # two spans drawn short, labelled L
        tot = 2 * L
        kk = min(k, (x1 - xa - 30) / tot)
        sh.rect(xa, y - t * kk, xa + tot * kk, y, "struct", 0.4)
        for s in (0, 1, 2):                              # beams under the supports
            bx = xa + s * L * kk
            sh.rect(bx - 0.1 * kk, y - t * kk - 0.3 * kk, bx + 0.1 * kk, y - t * kk, "struct", 0.35)
        cb = 0.025 * kk
        sh.line((xa + 1, y - t * kk + cb), (xa + tot * kk - 1, y - t * kk + cb), "rebar", 0.4)
        for s in (0, 1, 2):
            bx = xa + s * L * kk
            a = max(xa + 1, bx - L / 4 * kk)
            b_ = min(xa + tot * kk - 1, bx + L / 4 * kk)
            sh.line((a, y - cb), (b_, y - cb), "rebar", 0.4)
            if s == 1:
                sh.text(((a + bx) / 2, y + 1.2), "L/4", 1.6, "center", "dim")
                sh.text(((b_ + bx) / 2, y + 1.2), "L/4", 1.6, "center", "dim")
        sh.text((xa + L * kk / 2, y - t * kk - 14), f"เหล็กล่าง {bname}@{sp:.2f}", 1.7, "center", "rebar")
        sh.text((xa + L * kk, y + 4.0), f"เหล็กบน {bname}@{sp:.2f}", 1.7, "center", "rebar")
        sh.text((xa + tot * kk + 2.5, y - t * kk / 2), f"{t:.2f}", 1.7, "center", "dim", angle=90)
        sh.text((xa + tot * kk + 6, y - t * kk - 3), "L = ช่วงสั้นของแผ่นพื้น", 1.6, "left")
        y -= t * kk + 26
        if y < y0 + 26:
            break
    D.caption(sh, ((x0 + x1) / 2, y0 + 6), "รายละเอียดพื้น", "1:25")


def s_typical_beam(sh, E):
    """รายละเอียดการเสริมเหล็กคานทั่วไป: where the bars stop (L/4 top over
    the supports, L/5 bottom), the cantilever, laps; and the structural notes."""
    x0, y0, x1, y1 = D.drawing_area()
    k = 1000.0 / 50
    xa, yb = x0 + 20, y1 - 80
    L1, L2, h = 5.0, 1.8, 0.5
    tot = L1 + L2
    sh.rect(xa, yb, xa + tot * k, yb + h * k, "struct", 0.4)
    for s in (0, L1):
        bx = xa + s * k
        sh.rect(bx - 0.1 * k, yb - 12, bx + 0.1 * k, yb, "struct", 0.35)
        sh.rect(bx - 0.1 * k, yb + h * k, bx + 0.1 * k, yb + h * k + 10, "struct", 0.35, True)
    c = 1.2
    sh.line((xa - 1, yb + h * k - c), (xa + tot * k - 1, yb + h * k - c), "rebar", 0.45)
    sh.line((xa - 1, yb + c), (xa + L1 * k + 0.1 * k, yb + c), "rebar", 0.45)
    sh.line((xa + L1 * k, yb + c), (xa + tot * k - 1, yb + c), "rebar", 0.45)
    sh.line((xa, yb + h * k - c - 1), (xa + L1 / 4 * k, yb + h * k - c - 1), "rebar", 0.45)
    sh.line((xa + (L1 - L1 / 4) * k, yb + h * k - c - 1), (xa + tot * k - 1, yb + h * k - c - 1), "rebar", 0.45)
    sh.line((xa + L1 / 5 * k, yb + c + 1), (xa + (L1 - L1 / 5) * k, yb + c + 1), "rebar", 0.45)
    for t_ in range(int(tot / 0.2)):
        tx = xa + (0.1 + t_ * 0.2) * k
        sh.line((tx, yb + c), (tx, yb + h * k - c), "rebar", 0.13)
    for a, b_, lab, yy in ((0, L1 / 4, "L1/4", yb + h * k + 14), (L1 - L1 / 4, L1, "L1/4", yb + h * k + 14),
                           (0, L1 / 5, "L1/5", yb - 18), (L1 - L1 / 5, L1, "L1/5", yb - 18),
                           (0, L1, "L1", yb + h * k + 20), (L1, tot, "L2 (คานยื่น)", yb + h * k + 20)):
        pa, pb = xa + a * k, xa + b_ * k
        sh.line((pa, yy), (pb, yy), "dim", 0.13)
        sh.text(((pa + pb) / 2, yy + 0.8), lab, 2.0, "center", "dim")
    notes = ["เหล็กบนเสริมพิเศษเหนือหัวเสา ยื่นเข้าช่วงคาน L/4 ทั้งสองข้าง (L = ช่วงคานด้านนั้น)",
             "เหล็กล่างเสริมพิเศษกลางช่วง หยุดห่างหัวเสา L/5 · เหล็กมุมบนและล่างวิ่งตลอดแนว",
             "คานยื่น: เหล็กบนวิ่งตลอดช่วงยื่นและยึดเข้าช่วงใน ไม่น้อยกว่าช่วงยื่น หรือ L1/4",
             "ระยะต่อทาบเหล็กรับแรงดึงไม่น้อยกว่า 40 เท่า (DB) / 48 เท่า (RB) ของเส้นผ่าศูนย์กลาง "
             "ไม่ต่อทาบเหล็กบนกลางช่วงและเหล็กล่างที่หัวเสา",
             "ปลอกช่วง L/4 จากหัวเสาให้ใช้ระยะตามแบบ ช่วงกลางคานไม่เกิน d/2",
             "ระยะหุ้มคอนกรีต: คาน เสา 3 ซม. · พื้น 2 ซม. · ฐานราก 7.5 ซม. · ส่วนสัมผัสดิน 5 ซม."]
    D.notes_block(sh, x0 + 10, yb - 32, "ข้อกำหนดการเสริมเหล็กคานทั่วไป", notes, 2.4, 120)
    D.caption(sh, ((x0 + x1) / 2, y0 + 6), "รายละเอียดการเสริมเหล็กคานทั่วไป", "1:50")
