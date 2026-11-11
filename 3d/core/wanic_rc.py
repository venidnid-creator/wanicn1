# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
"""ออกแบบโครงสร้าง คสล.: the reinforcement of the building's members —
read from the marks (F, PC, C, GB/B/RB, S) the building designer keeps —
checked against the basic detailing rules, and taken off by bar size.

These are DETAILING checks (minimum and maximum steel, bar spacing, ties
and stirrups, cover, lap lengths) in the spirit of the วสท. / ACI rules
and the DPT standard drawings, not a strength design: the member sizes and
bars are the designer's, and the drawings still need an engineer's check.

Bars are written as the drawings write them: ``4-DB12`` (four bars),
``DB12@0.15`` / ``RB9@0.20`` (a spacing in metres), ``RB6@0.15`` (ties).
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

#: Yield strength (ksc) of the bar grades: RB = SR24, DB = SD40 (the
#: standard drawings' defaults).
FY = {"RB": 2400.0, "DB": 4000.0}
GRADE = {"RB": "SR24", "DB": "SD40"}
#: Bar sizes on the Thai market (mm).
SIZES = {"RB": (6, 9, 12, 15, 19, 25), "DB": (10, 12, 16, 20, 25, 28, 32)}
COVER = {"footing": 0.075, "stump": 0.040, "column": 0.035, "beam": 0.030, "slab": 0.020}
WASTE = 0.05                                    # cutting waste on the take-off
TIE_WIRE_KG_PER_T = 20.0                        # ลวดผูกเหล็ก

_BAR = re.compile(r"^\s*(?:(\d+)\s*[-×x]\s*)?(RB|DB|SR|SD)\s*(\d+)\s*(?:@\s*([\d.]+))?\s*$", re.I)


@dataclass
class Bar:
    kind: str                 # "RB" or "DB"
    d: int                    # diameter, mm
    n: int = 0                # a count ("4-DB12") …
    s: float = 0.0            # … or a spacing in m ("DB12@0.15")
    text: str = ""

    @property
    def area(self) -> float:
        """One bar's area, cm²."""
        return math.pi * (self.d / 10.0) ** 2 / 4.0

    @property
    def kg_m(self) -> float:
        """Weight per metre (0.00617 d², kg/m)."""
        return 0.00617 * self.d * self.d

    @property
    def fy(self) -> float:
        return FY[self.kind]


def parse_bar(text) -> Bar | None:
    """``"4-DB12"`` → Bar(DB, 12, n=4); ``"RB9@0.20"`` → Bar(RB, 9, s=0.20);
    ``None`` for text that is not a bar."""
    m = _BAR.match(str(text or "").replace("Ø", "").replace("ø", ""))
    if not m:
        return None
    kind = m.group(2).upper()
    kind = {"SR": "RB", "SD": "DB"}.get(kind, kind)
    return Bar(kind, int(m.group(3)), int(m.group(1) or 0), float(m.group(4) or 0.0), str(text).strip())


def lap_length(bar: Bar) -> float:
    """Tension lap (ม.): 40 d for deformed bars, 48 d with hooks for round
    bars, and never under 0.30 m (the standard drawings' notes)."""
    k = 40 if bar.kind == "DB" else 48
    return max(k * bar.d / 1000.0, 0.30)


@dataclass
class Check:
    ok: bool
    text: str


@dataclass
class Result:
    mark: str
    kind: str
    checks: list = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(c.ok for c in self.checks)

    def lines(self) -> list[str]:
        return [("✓ " if c.ok else "⚠ ") + c.text for c in self.checks]


def _need(ok, good, bad) -> Check:
    return Check(bool(ok), good if ok else bad)


def check(mark: str, spec: dict) -> Result:
    """The detailing checks of one mark of the library."""
    kind = spec.get("kind", "")
    r = Result(mark, kind)
    C = r.checks.append
    if kind == "footing":
        w, l, t = (float(spec.get(k, 0) or 0) for k in ("w", "l", "t"))
        bar = parse_bar(spec.get("bars"))
        C(_need(t >= 0.20, f"ความหนาฐาน {t:.2f} ม. (ไม่น้อยกว่า 0.20 ม.)",
                f"ฐานหนา {t:.2f} ม. — บางกว่า 0.20 ม."))
        if not bar or not bar.s:
            C(Check(False, f"เหล็กตะแกรง «{spec.get('bars', '')}» อ่านไม่ได้ — เขียนแบบ DB12@0.15"))
            return r
        rho = 0.0018 if bar.kind == "DB" else 0.0020
        need = rho * 100 * t * 100                          # cm² per metre width
        have = bar.area / bar.s
        C(_need(have >= need - 1e-9, f"เหล็กตะแกรง {have:.2f} ≥ {need:.2f} ตร.ซม./ม. ({rho} bt)",
                f"เหล็กตะแกรง {have:.2f} ตร.ซม./ม. น้อยกว่าขั้นต่ำ {need:.2f} ({rho} bt)"))
        smax = min(3 * t, 0.45)
        C(_need(bar.s <= smax + 1e-9, f"ระยะเรียง {bar.s:.2f} ≤ {smax:.2f} ม. (3t, 0.45 ม.)",
                f"ระยะเรียง {bar.s:.2f} ม. ห่างเกิน {smax:.2f} ม."))
        C(_need(bar.d >= 12 if bar.kind == "DB" else bar.d >= 12,
                f"เหล็ก Ø{bar.d} มม. (ไม่เล็กกว่า 12 มม.)", f"เหล็ก Ø{bar.d} มม. เล็กกว่า 12 มม."))
        C(Check(True, f"ระยะหุ้ม {COVER['footing'] * 100:.1f} ซม. · ทาบเหล็ก {lap_length(bar):.2f} ม."))
        if int(spec.get("piles") or 0) >= 1:
            pb = float(spec.get("pile_b") or 0.18)
            C(_need(min(w, l) >= pb + 2 * 0.15, f"ขอบฐานห่างเข็มไม่น้อยกว่า 0.15 ม.",
                    f"ฐาน {min(w, l):.2f} ม. แคบไป — ขอบห่างเข็ม {pb:.2f} ม. น้อยกว่า 0.15 ม."))
    elif kind in ("stump", "column"):
        b, h = float(spec.get("b", 0) or 0), float(spec.get("h", 0) or 0)
        main, tie = parse_bar(spec.get("main")), parse_bar(spec.get("tie"))
        C(_need(min(b, h) >= 0.15, f"หน้าตัด {b:.2f}×{h:.2f} ม. (ด้านแคบไม่น้อยกว่า 0.15 ม.)",
                f"หน้าตัด {b:.2f}×{h:.2f} ม. — ด้านแคบเล็กกว่า 0.15 ม."))
        if not main or not main.n:
            C(Check(False, f"เหล็กยืน «{spec.get('main', '')}» อ่านไม่ได้ — เขียนแบบ 4-DB12"))
        else:
            ag = b * h * 1e4
            rho = main.n * main.area / ag if ag else 0.0
            C(_need(0.01 - 1e-9 <= rho <= 0.08, f"เหล็กยืน {main.n}-{main.kind}{main.d} = {rho * 100:.2f}% "
                    f"ของหน้าตัด (1–8%)", f"เหล็กยืน {rho * 100:.2f}% ของหน้าตัด — ต้องอยู่ระหว่าง 1–8%"))
            C(_need(main.n >= 4, f"เหล็กยืน {main.n} เส้น (อย่างน้อย 4)", f"เหล็กยืน {main.n} เส้น — น้อยกว่า 4"))
            C(_need(main.d >= 12, f"เหล็กยืน Ø{main.d} มม. (ไม่เล็กกว่า 12)",
                    f"เหล็กยืน Ø{main.d} มม. เล็กกว่า 12 มม."))
            C(Check(True, f"ทาบเหล็กยืน {lap_length(main):.2f} ม. ({'40' if main.kind == 'DB' else '48'}d)"))
        if not tie or not tie.s:
            C(Check(False, f"เหล็กปลอก «{spec.get('tie', '')}» อ่านไม่ได้ — เขียนแบบ RB6@0.15"))
        elif main and main.n:
            smax = min(16 * main.d / 1000.0, 48 * tie.d / 1000.0, min(b, h))
            C(_need(tie.s <= smax + 1e-9, f"ปลอก @{tie.s:.2f} ≤ {smax:.2f} ม. (16d, 48dปลอก, ด้านแคบ)",
                    f"ปลอก @{tie.s:.2f} ม. ห่างเกิน {smax:.2f} ม. (16d, 48dปลอก, ด้านแคบ)"))
    elif kind == "beam":
        b, h = float(spec.get("b", 0) or 0), float(spec.get("h", 0) or 0)
        top, bot, stir = (parse_bar(spec.get(k)) for k in ("top", "bot", "stir"))
        d = h - COVER["beam"] - 0.006 - 0.006                   # to the bars' centre
        C(_need(b >= 0.15 and h >= 0.25, f"หน้าตัด {b:.2f}×{h:.2f} ม.",
                f"หน้าตัด {b:.2f}×{h:.2f} ม. — เล็กกว่า 0.15×0.25 ม."))
        for name, bar in (("เหล็กล่าง", bot), ("เหล็กบน", top)):
            if not bar or not bar.n:
                C(Check(False, f"{name} «{spec.get('bot' if bar is bot else 'top', '')}» อ่านไม่ได้ — "
                               "เขียนแบบ 2-DB12"))
                continue
            rmin = 14.0 / bar.fy if bar is bot else 0.0     # the tension (bottom) steel
            need = rmin * b * 100 * d * 100
            have = bar.n * bar.area
            if bar is top:
                C(_need(bar.n >= 2, f"{name} {bar.n} เส้น (อย่างน้อย 2 เส้น · เหล็กยึดปลอก/รับโมเมนต์ลบ)",
                        f"{name} {bar.n} เส้น — น้อยกว่า 2 เส้น"))
                continue
            C(_need(have >= need - 1e-9 and bar.n >= 2,
                    f"{name} {have:.2f} ≥ {need:.2f} ตร.ซม. (14/fy, อย่างน้อย 2 เส้น)",
                    f"{name} {have:.2f} ตร.ซม. น้อยกว่าขั้นต่ำ {need:.2f} (14/fy) หรือน้อยกว่า 2 เส้น"))
            rho = have / (b * 100 * d * 100) if b and d > 0 else 0
            if rho > 0.04:
                C(Check(False, f"{name} {rho * 100:.1f}% — เกิน 4% ของหน้าตัด"))
        if not stir or not stir.s:
            C(Check(False, f"เหล็กปลอก «{spec.get('stir', '')}» อ่านไม่ได้ — เขียนแบบ RB6@0.15"))
        else:
            smax = min(d / 2, 0.30)
            C(_need(stir.s <= smax + 1e-9, f"ปลอก @{stir.s:.2f} ≤ {smax:.2f} ม. (d/2, 0.30 ม.) · "
                    f"ปลายคานช่วง 2h ใช้ @{min(stir.s, d / 4):.2f}",
                    f"ปลอก @{stir.s:.2f} ม. ห่างเกิน d/2 = {smax:.2f} ม."))
        if bot and bot.n:
            C(Check(True, f"ทาบเหล็ก {lap_length(bot):.2f} ม. · ระยะหุ้ม {COVER['beam'] * 100:.0f} ซม."))
    elif kind == "slab":
        t = float(spec.get("t", 0) or 0)
        bar = parse_bar(spec.get("bars"))
        C(_need(t >= 0.10, f"พื้นหนา {t:.2f} ม. (ไม่น้อยกว่า 0.10 ม.)", f"พื้นหนา {t:.2f} ม. — บางกว่า 0.10 ม."))
        if not bar or not bar.s:
            C(Check(False, f"เหล็กเสริม «{spec.get('bars', '')}» อ่านไม่ได้ — เขียนแบบ RB9@0.20"))
            return r
        rho = 0.0018 if bar.kind == "DB" else 0.0025
        need = rho * 100 * t * 100
        have = bar.area / bar.s
        C(_need(have >= need - 1e-9, f"เหล็กเสริม {have:.2f} ≥ {need:.2f} ตร.ซม./ม. ({rho} bt)",
                f"เหล็กเสริม {have:.2f} ตร.ซม./ม. น้อยกว่าขั้นต่ำ {need:.2f} ({rho} bt)"))
        smax = min(3 * t, 0.45)
        C(_need(bar.s <= smax + 1e-9, f"ระยะเรียง {bar.s:.2f} ≤ {smax:.2f} ม. (3t, 0.45 ม.)",
                f"ระยะเรียง {bar.s:.2f} ม. ห่างเกิน {smax:.2f} ม."))
    return r


def suggest(spec: dict) -> dict:
    """The smallest change to a mark's bars that passes the checks it
    fails on steel: one more bar (beams, columns) or a closer spacing
    (footings, slabs). The member's size is left as the designer set it."""
    out = dict(spec)
    kind = spec.get("kind")
    for _round in range(12):
        res = check("?", out)
        bad = " ".join(c.text for c in res.checks if not c.ok)
        if not bad:
            break
        if kind == "beam" and "เหล็กล่าง" in bad:
            b_ = parse_bar(out.get("bot"))
            if not b_:
                break
            out["bot"] = f"{max(b_.n, 1) + 1}-{b_.kind}{b_.d}"
        elif kind == "beam" and "เหล็กบน" in bad:
            b_ = parse_bar(out.get("top"))
            out["top"] = f"2-{b_.kind}{b_.d}" if b_ else "2-DB12"
        elif kind == "beam" and "ปลอก" in bad:
            st = parse_bar(out.get("stir"))
            if not st or st.s <= 0.05:
                break
            out["stir"] = f"{st.kind}{st.d}@{st.s - 0.025:.3f}".rstrip("0")
        elif kind in ("stump", "column") and "เหล็กยืน" in bad:
            m = parse_bar(out.get("main"))
            if not m:
                break
            n = m.n + 2 if m.n >= 4 else 4
            out["main"] = f"{n}-{m.kind}{max(m.d, 12)}"
        elif kind in ("stump", "column") and "ปลอก" in bad:
            st = parse_bar(out.get("tie"))
            if not st or st.s <= 0.05:
                break
            out["tie"] = f"{st.kind}{st.d}@{st.s - 0.025:.3f}".rstrip("0")
        elif kind in ("footing", "slab") and ("เหล็ก" in bad or "ระยะเรียง" in bad):
            b_ = parse_bar(out.get("bars"))
            if not b_:
                break
            if b_.s - 0.025 < 0.10 - 1e-9:            # too close: the next bar size instead
                bigger = [d_ for d_ in SIZES[b_.kind] if d_ > b_.d]
                if not bigger:
                    break
                out["bars"] = f"{b_.kind}{bigger[0]}@0.20"
            else:
                out["bars"] = f"{b_.kind}{b_.d}@{b_.s - 0.025:.3f}".rstrip("0")
        else:
            break
    return out


def check_library(lib: dict) -> dict:
    return {m: check(m, spec) for m, spec in lib.items()}


# ---- take-off -------------------------------------------------------------------------

def _add(out, bar: Bar, metres: float) -> None:
    if bar is None or metres <= 0:
        return
    key = f"{bar.kind}{bar.d}"
    rec = out.setdefault(key, {"grade": GRADE[bar.kind], "m": 0.0, "kg": 0.0})
    rec["m"] += metres
    rec["kg"] += metres * bar.kg_m


def _mesh(out, bar, a, b, cover):
    """A two-way mat over a×b: bars both ways at the spacing, with hooks."""
    if not bar or not bar.s:
        return
    hook = 12 * bar.d / 1000.0
    na = int(math.floor(max(b - 2 * cover, 0) / bar.s)) + 1
    nb = int(math.floor(max(a - 2 * cover, 0) / bar.s)) + 1
    _add(out, bar, na * (a - 2 * cover + 2 * hook) + nb * (b - 2 * cover + 2 * hook))


def takeoff(E) -> dict:
    """{"bars": {"DB12": {"grade", "m", "kg"}…}, "concrete": {kind: m³},
    "by_mark": {mark: {"n", "concrete", "kg"}}, "kg", "wire"} for the
    elements of :func:`core.wanic_building.elements` — the structure's
    reinforcement, waste included."""
    lib = E["lib"]
    bars: dict = {}
    conc: dict = {}
    marks: dict = {}

    def mark_rec(m):
        return marks.setdefault(m, {"n": 0, "concrete": 0.0, "kg": 0.0})

    def run(m, fn):
        before = sum(v["kg"] for v in bars.values())
        fn()
        mark_rec(m)["kg"] += sum(v["kg"] for v in bars.values()) - before

    for f in E["footings"]:
        sp = lib.get(f["mark"], {})
        w, l, t = (float(sp.get(k, 0) or 0) for k in ("w", "l", "t"))
        mark_rec(f["mark"])["n"] += 1
        mark_rec(f["mark"])["concrete"] += w * l * t
        conc["footing"] = conc.get("footing", 0.0) + w * l * t
        run(f["mark"], lambda sp=sp, w=w, l=l: _mesh(bars, parse_bar(sp.get("bars")), w, l,
                                                    COVER["footing"]))
    for kind, items in (("stump", E["stumps"]), ("column", E["columns"])):
        for c in items:
            sp = lib.get(c["mark"], {})
            b, h = float(sp.get("b", 0) or 0), float(sp.get("h", 0) or 0)
            L = abs(float(c["z1"]) - float(c["z0"]))
            mark_rec(c["mark"])["n"] += 1
            mark_rec(c["mark"])["concrete"] += b * h * L
            conc[kind] = conc.get(kind, 0.0) + b * h * L

            def col(sp=sp, b=b, h=h, L=L, kind=kind):
                main, tie = parse_bar(sp.get("main")), parse_bar(sp.get("tie"))
                if main and main.n:
                    _add(bars, main, main.n * (L + lap_length(main)))
                if tie and tie.s:
                    cv = COVER[kind]
                    per = 2 * (b + h - 4 * cv) + 2 * 0.10            # with 135° hooks
                    _add(bars, tie, (int(L / tie.s) + 1) * per)
            run(c["mark"], col)
    for e in E["beams"]:
        sp = lib.get(e["mark"], {})
        b, h = float(sp.get("b", 0) or 0), float(sp.get("h", 0) or 0)
        L = math.dist(e["p0"], e["p1"])
        mark_rec(e["mark"])["n"] += 1
        mark_rec(e["mark"])["concrete"] += b * h * L
        conc["beam"] = conc.get("beam", 0.0) + b * h * L

        def beam(sp=sp, b=b, h=h, L=L):
            for k in ("top", "bot"):
                bar = parse_bar(sp.get(k))
                if bar and bar.n:
                    _add(bars, bar, bar.n * (L + 2 * 12 * bar.d / 1000.0))
            st = parse_bar(sp.get("stir"))
            if st and st.s:
                cv = COVER["beam"]
                _add(bars, st, (int(L / st.s) + 1) * (2 * (b + h - 4 * cv) + 0.20))
        run(e["mark"], beam)
    for s_ in E["slabs"]:
        sp = lib.get(s_["mark"], {})
        rm = s_["room"]
        a, b_, t = float(rm["w"]), float(rm["d"]), float(sp.get("t", 0) or 0)
        mark_rec(s_["mark"])["n"] += 1
        mark_rec(s_["mark"])["concrete"] += a * b_ * t
        conc["slab"] = conc.get("slab", 0.0) + a * b_ * t
        run(s_["mark"], lambda sp=sp, a=a, b_=b_: _mesh(bars, parse_bar(sp.get("bars")), a, b_,
                                                       COVER["slab"]))
    for v in bars.values():
        v["m"] *= 1 + WASTE
        v["kg"] *= 1 + WASTE
    for v in marks.values():
        v["kg"] *= 1 + WASTE
    kg = sum(v["kg"] for v in bars.values())
    return {"bars": dict(sorted(bars.items(), key=lambda kv: (kv[0][:2], int(kv[0][2:])))),
            "concrete": conc, "by_mark": marks, "kg": kg,
            "wire": kg / 1000.0 * TIE_WIRE_KG_PER_T}


def grid_axes(E) -> tuple[list, list]:
    """The grid lines of the plan: the distinct x and y of its columns."""
    xs = sorted({round(c["x"], 3) for c in E["columns"] + E["stumps"]})
    ys = sorted({round(c["y"], 3) for c in E["columns"] + E["stumps"]})
    return xs, ys


def axis_names(n: int, letters: bool) -> list[str]:
    if not letters:
        return [str(i + 1) for i in range(n)]
    out = []
    for i in range(n):
        s, k = "", i
        while True:
            s = chr(65 + k % 26) + s
            k = k // 26 - 1
            if k < 0:
                break
        out.append(s)
    return out


def report_xlsx(E, path) -> None:
    """สรุปโครงสร้าง คสล.: the checks of every mark, the members by mark
    and the reinforcement by bar size — written with the program's own
    .xlsx writer (the one the BOQ uses), no extra library needed."""
    from pathlib import Path
    from core import wanic_building as B
    from core.wanic_takeoff import _Sheet, _xlsx
    lib = E["lib"]
    s1 = _Sheet("ตรวจเหล็กเสริม", landscape=True)
    s1.widths = [10, 14, 60, 12, 90]
    s1.add(["เบอร์", "ชนิด", "ขนาด / เหล็กเสริม", "ผล", "รายละเอียด"], style=3)
    for mark in sorted(lib):
        sp = lib[mark]
        res = check(mark, sp)
        fields = ", ".join(f"{th} {sp.get(k, '')}" for k, th in B.LIB_FIELDS.get(sp.get("kind"), [])
                           if k in sp)
        s1.add([mark, B.LIB_KINDS.get(sp.get("kind"), sp.get("kind")), fields,
                "ผ่าน" if res.ok else "ตรวจสอบ", " · ".join(res.lines())])
    T = takeoff(E)
    s2 = _Sheet("ปริมาณตามเบอร์", landscape=False)
    s2.widths = [10, 14, 10, 18, 18]
    s2.add(["เบอร์", "ชนิด", "จำนวน", "คอนกรีต (ลบ.ม.)", "เหล็กเสริม (กก.)"], style=3)
    for mark, v in sorted(T["by_mark"].items()):
        s2.add([mark, B.LIB_KINDS.get(lib.get(mark, {}).get("kind"), ""), v["n"],
                round(v["concrete"], 3), round(v["kg"], 2)])
    s3 = _Sheet("เหล็กเสริมตามขนาด", landscape=False)
    s3.widths = [16, 14, 16, 16]
    s3.add(["ขนาด", "ชั้นคุณภาพ", "ความยาว (ม.)", "น้ำหนัก (กก.)"], style=3)
    for key, v in T["bars"].items():
        s3.add([key, v["grade"], round(v["m"], 1), round(v["kg"], 2)])
    s3.add(["รวม", "", "", round(T["kg"], 2)])
    s3.add(["ลวดผูกเหล็ก", "", "", round(T["wire"], 2)])
    s3.add([f"รวมเผื่อเศษ {int(WASTE * 100)}% แล้ว · ลวดผูก {TIE_WIRE_KG_PER_T:g} กก./ตัน", "", "", ""])
    Path(path).write_bytes(_xlsx([s1, s2, s3]))
