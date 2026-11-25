# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
"""ตารางตัดเหล็ก (Bar Cutting List) and the cutting plan from 10 m stock (ข12, from WanicnDesign).

Every bar of the model is listed with its shape, cutting length and number
— alike elements counted together — then the pieces of each size are cut
from stock bars by first-fit decreasing: the bars to buy, the offcut and
the cutting patterns.

Rules (the program's detailing, as the drawings): covers ``R.COVER``; laps
``R.lap_length`` (40d deformed, 48d round, ≥ 0.30 m); 90° hooks 12d at
the ends of beam and slab bars and the column feet (0.25 m on the
footing mesh, as S-09); stirrups and ties closed with two 135° hooks of
6d ≥ 75 mm; a bar longer than a stock bar is cut in pieces lapped by its
lap length. Weights 0.00617·d² kg/m.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from core import wanic_rc as R

STOCK = 10.0


@dataclass
class Item:
    group: str                   # ฐานราก / ตอม่อ / เสา / คาน / พื้น
    mark: str
    bar: str                     # "ตะแกรงล่าง ตามยาว", "เหล็กบน", "ปลอก" …
    size: str                    # "DB12"
    shape: str                   # "ตรง" / "งอ 90° 2 ปลาย" / "ปลอกปิด 135°" …
    length: float                # m, the cutting length of one bar (≤ STOCK after splitting)
    count: int                   # bars in all

    @property
    def total(self) -> float:
        return self.length * self.count


@dataclass
class Plan:
    size: str
    bars: int
    used: float
    pieces: int
    patterns: list = field(default_factory=list)      # [(n stock bars, [piece lengths])]

    @property
    def bought(self) -> float:
        return self.bars * STOCK

    @property
    def waste_pct(self) -> float:
        return 100 * (1 - self.used / self.bought) if self.bars else 0.0


def kg_m(size: str) -> float:
    d = int("".join(ch for ch in size if ch.isdigit()) or 0)
    return 0.00617 * d * d


def _hook(bar) -> float:
    return 12 * bar.d / 1000.0


def _tie(bar, b, h, cover) -> float:
    return 2 * (b + h - 4 * cover) + 2 * max(6 * bar.d / 1000.0, 0.075)


def _split(length, bar):
    """A bar longer than the stock: (n pieces, each length) lapped by its lap."""
    if length <= STOCK + 1e-9:
        return 1, length
    lap = R.lap_length(bar)
    k = math.ceil((length - lap) / (STOCK - lap) - 1e-9)
    return k, (length + (k - 1) * lap) / k


def items(E) -> list:
    """Every bar of the model's structure, alike ones counted together."""
    lib = E["lib"]
    acc: dict = {}

    def add(group, mark, label, bar, shape, length, n):
        if bar is None or n <= 0 or length <= 0:
            return
        k, L = _split(length, bar)
        key = (group, mark, label, f"{bar.kind}{bar.d}", shape if k == 1 else shape + f" (ต่อทาบ {k} ท่อน)",
               round(L, 2))
        acc[key] = acc.get(key, 0) + n * k

    # footings: the bottom mesh both ways, bent up at the ends
    cv = R.COVER["footing"]
    for f in E["footings"]:
        sp = lib.get(f["mark"], {})
        w, l_, t = (float(sp.get(k, 0) or 0) for k in ("w", "l", "t"))
        up = max(0.15, t - 2 * cv)
        for label, txt, span, across in (("ตะแกรงล่าง แนว X", sp.get("bars"), w, l_),
                                         ("ตะแกรงล่าง แนว Y", sp.get("bars_y") or sp.get("bars"), l_, w)):
            bar = R.parse_bar(txt)
            if bar and bar.s:
                n = int(math.floor(max(across - 2 * cv, 0) / bar.s)) + 1
                add("ฐานราก", f["mark"], label, bar, "งอขึ้น 2 ปลาย", span - 2 * cv + 2 * up, n)
        top = R.parse_bar(sp.get("top"))
        if top and top.s:
            n = int(math.floor(max(min(w, l_) - 2 * cv, 0) / top.s)) + 1
            add("ฐานราก", f["mark"], "เหล็กบน (ฐานรากร่วม)", top, "งอ 90° 2 ปลาย",
                max(w, l_) - 2 * cv + 2 * _hook(top), n)
    # stumps and columns: the main bars a storey each with the lap above, the foot on the
    # footing mesh, the hook into the top beam; the ties
    n_fl = int(E["n"])
    for group, rows in (("ตอม่อ", E["stumps"]), ("เสา", E["columns"])):
        for c in rows:
            sp = lib.get(c["mark"], {})
            b, h = float(sp.get("b", 0.2) or 0.2), float(sp.get("h", 0.2) or 0.2)
            L = abs(float(c["z1"]) - float(c["z0"]))
            main, tie = R.parse_bar(sp.get("main")), R.parse_bar(sp.get("tie"))
            top_floor = group == "เสา" and int(c.get("floor", 0)) == n_fl - 1
            if main and main.n:
                if group == "ตอม่อ":
                    length, shape = L + 0.25 + R.lap_length(main), "งอฉาก 0.25 ม. ที่ฐาน"
                elif top_floor:
                    length, shape = L - R.COVER["beam"] + _hook(main), "งอ 90° เข้าคานบนสุด"
                else:
                    length, shape = L + R.lap_length(main), "ตรง (ทาบเหนือพื้น)"
                add(group, c["mark"], "เหล็กยืน", main, shape, length, main.n)
            if tie and tie.s:
                cv_ = R.COVER["stump" if group == "ตอม่อ" else "column"]
                add(group, c["mark"], "ปลอก", tie, "ปลอกปิด ขอ 135°", _tie(tie, b, h, cv_), int(L / tie.s) + 1)
    # beams: collinear spans of a mark on a level are one run — the top bars continuous over
    # it, the bottom bars span by span, both with 90° hooks into the end columns
    runs: dict = {}
    for e in E["beams"]:
        (x0, y0), (x1, y1) = e["p0"], e["p1"]
        horiz = abs(y1 - y0) < 1e-6
        key = (e["level"], e["mark"], "x" if horiz else "y", round(y0 if horiz else x0, 3))
        runs.setdefault(key, []).append(e)
    for (lvl, mark, axis, _c), segs in runs.items():
        sp = lib.get(mark, {})
        b, h = float(sp.get("b", 0.2) or 0.2), float(sp.get("h", 0.4) or 0.4)
        along = sorted(((min(e["p0"][0], e["p1"][0]), max(e["p0"][0], e["p1"][0])) if axis == "x" else
                        (min(e["p0"][1], e["p1"][1]), max(e["p0"][1], e["p1"][1])) for e in segs))
        chains, cur = [], None                                 # contiguous stretches
        for a, z in along:
            if cur and abs(a - cur[1]) < 1e-6:
                cur[1] = z
                cur[2].append(z - a)
            else:
                cur = [a, z, [z - a]]
                chains.append(cur)
        cv = R.COVER["beam"]
        top, bot, stir = R.parse_bar(sp.get("top")), R.parse_bar(sp.get("bot")), R.parse_bar(sp.get("stir"))
        for a, z, spans in chains:
            if top and top.n:
                add("คาน", mark, "เหล็กบน (ต่อเนื่อง)", top, "งอ 90° 2 ปลาย", z - a + 0.2 - 2 * cv + 2 * _hook(top),
                    top.n)
            for L in spans:
                if bot and bot.n:
                    add("คาน", mark, "เหล็กล่าง (รายช่วง)", bot, "งอ 90° 2 ปลาย", L + 0.2 - 2 * cv + 2 * _hook(bot),
                        bot.n)
                if stir and stir.s:
                    add("คาน", mark, "เหล็กปลอก", stir, "ปลอกปิด ขอ 135°", _tie(stir, b, h, cv), int(L / stir.s) + 1)
    # slabs: the mesh both ways, hooked
    cv = R.COVER["slab"]
    for s_ in E["slabs"]:
        sp = lib.get(s_["mark"], {})
        rm = s_["room"]
        a, b = float(rm["w"]), float(rm["d"])
        bar = R.parse_bar(sp.get("bars"))
        if bar and bar.s:
            n_a = int(math.floor(max(b - 2 * cv, 0) / bar.s)) + 1
            n_b = int(math.floor(max(a - 2 * cv, 0) / bar.s)) + 1
            add("พื้น", s_["mark"], "ตะแกรง แนว X", bar, "งอ 90° 2 ปลาย", a - 2 * cv + 2 * _hook(bar), n_a)
            add("พื้น", s_["mark"], "ตะแกรง แนว Y", bar, "งอ 90° 2 ปลาย", b - 2 * cv + 2 * _hook(bar), n_b)
    order = {"ฐานราก": 0, "ตอม่อ": 1, "เสา": 2, "คาน": 3, "พื้น": 4}
    return [Item(g, m, lb, sz, sh, L, n) for (g, m, lb, sz, sh, L), n in
            sorted(acc.items(), key=lambda kv: (order.get(kv[0][0], 9), kv[0][1], kv[0][2], -kv[0][5]))]


def plans(rows: list) -> list:
    """First-fit decreasing of the pieces of each size into stock bars."""
    by: dict = {}
    for it in rows:
        by.setdefault(it.size, []).extend([it.length] * it.count)
    out = []
    for size, pieces in sorted(by.items(), key=lambda kv: (kv[0][:2], kg_m(kv[0]))):
        pieces.sort(reverse=True)
        bins, free = [], []
        for p in pieces:
            p = min(p, STOCK)
            for i, f in enumerate(free):
                if p <= f + 1e-9:
                    bins[i].append(p)
                    free[i] -= p
                    break
            else:
                bins.append([p])
                free.append(STOCK - p)
        pat: dict = {}
        for b_ in bins:
            k = tuple(round(x, 2) for x in b_)
            pat[k] = pat.get(k, 0) + 1
        out.append(Plan(size, len(bins), sum(pieces), len(pieces),
                        sorted(((n, list(k)) for k, n in pat.items()), key=lambda t: (-t[0], -sum(t[1])))))
    return out


def cuts_text(cuts) -> str:
    """[4.43, 4.43, 1.11] → "4.43 × 2 + 1.11"."""
    out = []
    for c in sorted(set(cuts), reverse=True):
        n = sum(1 for x in cuts if abs(x - c) < 1e-9)
        out.append(f"{c:.2f}" + (f" × {n}" if n > 1 else ""))
    return " + ".join(out)


def write_xlsx(E, path) -> dict:
    """ตารางตัดเหล็ก.xlsx: the list, the cutting plan and the purchase by size."""
    from pathlib import Path
    from core.wanic_takeoff import _Sheet, _xlsx
    rows = items(E)
    pl = plans(rows)
    s1 = _Sheet("ตารางตัดเหล็ก", landscape=True)
    s1.widths = [10, 8, 26, 9, 30, 12, 9, 14, 14]
    s1.add(["ชิ้นส่วน", "เบอร์", "เหล็ก", "ขนาด", "รูปร่าง", "ยาว/ท่อน (ม.)", "จำนวน", "ยาวรวม (ม.)", "น้ำหนัก (กก.)"],
           style=3)
    for it in rows:
        s1.add([it.group, it.mark, it.bar, it.size, it.shape, round(it.length, 2), it.count, round(it.total, 2),
                round(it.total * kg_m(it.size), 2)])
    s2 = _Sheet("แผนตัดเหล็ก 10 ม.", landscape=True)
    s2.widths = [9, 12, 80, 14]
    s2.add(["ขนาด", "จำนวนเส้น", "ตัดเป็น (ม.)", "เศษต่อเส้น (ม.)"], style=3)
    for p in pl:
        for n, cuts in p.patterns:
            s2.add([p.size, n, cuts_text(cuts), round(STOCK - sum(cuts), 2)])
    s3 = _Sheet("สั่งซื้อเหล็ก", landscape=False)
    s3.widths = [9, 12, 14, 14, 14, 12]
    s3.add(["ขนาด", "ซื้อ (เส้น 10 ม.)", "ใช้จริง (ม.)", "เศษ (%)", "น้ำหนักซื้อ (กก.)", "ท่อน"], style=3)
    kg = 0.0
    for p in pl:
        w = p.bought * kg_m(p.size)
        kg += w
        s3.add([p.size, p.bars, round(p.used, 2), round(p.waste_pct, 1), round(w, 1), p.pieces])
    s3.add(["รวม", sum(p.bars for p in pl), "", "", round(kg, 1), ""])
    s3.add(["ตัดจากเหล็กเส้นยาว 10 ม. แบบ first-fit decreasing · ทาบ 40d (ข้ออ้อย) / 48d (กลม) ≥ 0.30 ม. · "
            "ขอ 90° 12d · ปลอก 135° 6d ≥ 75 มม.", "", "", "", "", ""])
    Path(path).write_bytes(_xlsx([s1, s2, s3]))
    return {"items": len(rows), "bars": sum(p.bars for p in pl), "kg": kg}
