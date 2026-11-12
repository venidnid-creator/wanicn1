# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
"""คำแนะนำเมื่อคำนวณไม่ผ่าน — for every member that fails, what to add and
where so that it passes, found by re-checking with the same rules:

- beams (วสท. 011008 / ACI 318): the bottom bars at mid-span and the top
  bars over the supports needed for the moments (same bar size, else one
  size up); when the section is too small for steel alone (ρ > 0.75 ρb or
  the moment over Mc), the depth that carries it; the stirrup spacing for
  the shear near the supports (≤ d/2), or a wider/deeper beam when
  Vs > 2.1 √fc′ b d;
- columns: more bars of the same size (ρ ≤ 2.5 %, economical), else a larger column, each
  re-checked on the P-M curve;
- slabs: the bar spacing needed for both spans (≤ 3t, 45 cm), else the next
  bar size, else a thicker slab (≥ perimeter / 180 for two-way slabs);
- footings: the footing size the soil needs (with its own weight), or the
  number of piles; a thicker footing when the punching shear fails;
- roof members: the lightest section of the same family that carries the
  moment and keeps the deflection within L/180.

Each piece of advice names the member, where on it, the step of the RC
designer where its mark is edited, and the numbers."""
from __future__ import annotations

import math

from core import wanic_calc as C
from core import wanic_rc as R

DB_SIZES = (10, 12, 16, 20, 25, 28)
RB_SIZES = (6, 9, 12)


def _step(res) -> str:
    return "ขั้น 4 คานคอดิน" if getattr(res, "ground", False) else "ขั้น 6 เสา + คาน"


def _need_as(M, b, d, fy, fc, method):
    """cm² for M (kg·m) on b, d (m); inf when the section cannot take it."""
    if M <= 0:
        return 0.0
    if method == "SDM":
        Rn = M * 100 / (0.9 * b * 100 * (d * 100) ** 2)
        disc = 1 - 2 * Rn / (0.85 * fc)
        if disc <= 0:
            return float("inf")
        rho = 0.85 * fc / fy * (1 - math.sqrt(disc))
        rho_b = 0.85 * 0.85 * fc / fy * 6120 / (6120 + fy)
        if rho > 0.75 * rho_b:
            return float("inf")
        return rho * b * 100 * d * 100
    fs = min(0.5 * fy, 1700.0)
    n = 2.04e6 / (15100 * math.sqrt(fc))
    k = 1 / (1 + fs / (n * 0.375 * fc))
    Mc = 0.5 * 0.375 * fc * k * (1 - k / 3) * b * 100 * (d * 100) ** 2 / 100
    if M > Mc:
        return float("inf")
    return M * 100 / (fs * 0.875 * d * 100)


def _depth_for(M, b, fy, fc, method):
    """The effective depth (m) that carries M with steel at half the maximum."""
    if method == "SDM":
        rho_b = 0.85 * 0.85 * fc / fy * 6120 / (6120 + fy)
        rho = 0.375 * rho_b
        Rn = 0.9 * rho * fy * (1 - 0.59 * rho * fy / fc)
    else:
        fs = min(0.5 * fy, 1700.0)
        n = 2.04e6 / (15100 * math.sqrt(fc))
        k = 1 / (1 + fs / (n * 0.375 * fc))
        Rn = 0.5 * 0.375 * fc * k * (1 - k / 3)
    return math.sqrt(M * 100 / (Rn * b * 100)) / 100


def fit_in_row(b, dia_mm, stir_mm=6) -> int:
    """How many bars fit in one row of a beam b (m) wide: clear spacing
    ≥ max(25 mm, the bar) (วสท./ACI), cover 30 mm, the stirrup."""
    clear = max(25.0, dia_mm)
    room = b * 1000 - 2 * R.COVER["beam"] * 1000 - 2 * stir_mm
    return max(2, int((room + clear) // (dia_mm + clear)))


def _bars_for(As, bar, kind="DB", b=None):
    """(n, dia) — the same size first, as many as fit in one row of the
    beam (else up to 6), then larger sizes."""
    sizes = DB_SIZES if kind == "DB" else RB_SIZES
    start = bar.d if bar else 12
    for d in [s for s in sizes if s >= start]:
        a1 = math.pi * (d / 10) ** 2 / 4
        n = max(2, math.ceil(As / a1))
        if n <= (fit_in_row(b, d) if b else 6):
            return n, d
    d = sizes[-1]
    return max(2, math.ceil(As / (math.pi * (d / 10) ** 2 / 4))), d


def beam_advice(m, b_) -> list:
    res = m.diagram
    spec = res.spec
    bw, h = float(spec.get("b", 0.2)), float(spec.get("h", 0.4))
    d = h - R.COVER["beam"] - 0.012
    fc, method = b_["fc"], b_["method"]
    top, bot, st = R.parse_bar(spec.get("top")), R.parse_bar(spec.get("bot")), R.parse_bar(spec.get("stir"))
    fy_t, fy_b = C.fy_of(top, b_), C.fy_of(bot, b_)
    cap = C.beam_capacity(spec, b_, fc)
    out = []
    where = f"{res.mark} ({_step(res)})"
    deeper = 0.0
    if res.Mmax > cap["bot"] + 1e-6:
        As = _need_as(res.Mmax, bw, d, fy_b, fc, method)
        if math.isfinite(As):
            n, dia = _bars_for(As, bot, bot.kind if bot else "DB", bw)
            out.append(f"{where}: เพิ่มเหล็กล่างกลางช่วงเป็น {n}-{(bot.kind if bot else 'DB')}{dia} "
                       f"(As ต้องการ {As:.2f} ซม.²)")
        else:
            deeper = max(deeper, _depth_for(res.Mmax, bw, fy_b, fc, method))
    if res.Mmin < 0 and -res.Mmin > cap["top"] + 1e-6:
        As = _need_as(-res.Mmin, bw, d, fy_t, fc, method)
        if math.isfinite(As):
            n, dia = _bars_for(As, top, top.kind if top else "DB", bw)
            out.append(f"{where}: เพิ่มเหล็กบนเหนือหัวเสาเป็น {n}-{(top.kind if top else 'DB')}{dia} "
                       f"ยาวเข้าช่วง L/4 (As ต้องการ {As:.2f} ซม.²)")
        else:
            deeper = max(deeper, _depth_for(-res.Mmin, bw, fy_t, fc, method))
    if deeper:
        h_new = math.ceil((deeper + R.COVER["beam"] + 0.012) * 20) / 20
        out.append(f"{where}: หน้าตัดเล็กเกินไปสำหรับโมเมนต์ — เพิ่มความลึกคานเป็นอย่างน้อย {h_new * 100:.0f} ซม. "
                   f"(หรือกว้างขึ้น) แล้วคำนวณเหล็กใหม่")
    if res.Vmax > cap["V"] + 1e-6:
        phi = 0.85 if method == "SDM" else 1.0
        vc = (0.53 if method == "SDM" else 0.29) * math.sqrt(fc) * bw * 100 * d * 100
        vs_need = res.Vmax / phi - vc
        vs_max = (2.1 if method == "SDM" else 1.32) * math.sqrt(fc) * bw * 100 * d * 100
        if vs_need > vs_max:
            out.append(f"{where}: แรงเฉือนเกินกำลังหน้าตัด — ขยายความกว้าง/ความลึกคาน")
        elif st:
            fyv = C.fy_of(st, b_) if method == "SDM" else C.fs_of(st, b_)
            s = 2 * st.area * fyv * d * 100 / vs_need / 100
            s = min(s, d / 2)
            s = math.floor(s * 40) / 40
            if s >= 0.05:
                out.append(f"{where}: ลดระยะเหล็กปลอกช่วง L/4 จากหัวเสาเป็น {st.kind}{st.d}@{s:.3f}".rstrip("0")
                           + " ม.")
            else:
                big = 9 if st.d < 9 else 12
                out.append(f"{where}: เปลี่ยนเหล็กปลอกเป็น RB{big} (หรือ DB10) แล้วตรวจระยะใหม่")
    return out


def column_advice(m, data, b_) -> list:
    from core import wanic_building as B
    lib = B.library_of(data)
    mark = m.name.split(" ")[0]
    spec = dict(lib.get(mark, {}))
    dia = m.diagram
    if dia is None or not spec:
        return [f"{mark} (ขั้น 6): เพิ่มขนาดเสาหรือเหล็กยืน"]
    Pu, Mu = dia.Pu, dia.Mu
    main = R.parse_bar(spec.get("main"))
    b, h = float(spec.get("b", 0.2)), float(spec.get("h", 0.2))
    kind = main.kind if main else "DB"
    d0 = main.d if main else 12
    for d in [s for s in DB_SIZES if s >= d0]:
        for n in range(max(4, main.n if main else 4), 17, 2):
            if n * math.pi * (d / 10) ** 2 / 4 > 0.025 * b * h * 1e4:     # ρ ≤ 2.5 %: economical
                break
            sp = dict(spec, main=f"{n}-{kind}{d}")
            if C.pm_ratio(C.pm_curve(sp, b_), Mu, Pu) <= 1.0:
                return [f"{mark} (ขั้น 6 เสา): เพิ่มเหล็กยืนเป็น {n}-{kind}{d} (ขนาดเสาเดิม {b * 100:.0f}×{h * 100:.0f} ซม.)"]
    for add in range(1, 9):
        nb, nh = b + 0.05 * add, h + 0.05 * add
        for n in (4, 6, 8):
            sp = dict(spec, b=nb, h=nh, main=f"{n}-{kind}{max(d0, 12)}")
            if C.pm_ratio(C.pm_curve(sp, b_), Mu, Pu) <= 1.0:
                return [f"{mark} (ขั้น 6 เสา): ขยายเสาเป็น {nb * 100:.0f}×{nh * 100:.0f} ซม. "
                        f"เหล็กยืน {n}-{kind}{max(d0, 12)}"]
    return [f"{mark} (ขั้น 6 เสา): ขยายเสาให้ใหญ่กว่า {b * 100 + 40:.0f} ซม. หรือใช้เสาเหล็ก"]


def slab_advice(row, b_) -> list:
    from core import wanic_calc_cards as CC
    bar = row["bar"]
    t = row["t"]
    mark = row["mark"]
    need = min((s for s in row["s"].values() if s), default=0.0)
    if bar and need >= 0.10:
        return [f"{mark} (ขั้น 5 พื้น): ลดระยะเรียงเหล็กเป็น {bar.kind}{bar.d}@{need:.3f}".rstrip("0")
                + " ม. (ใช้ค่าน้อยสุดของเหล็กบน/ล่างทั้งสองทาง)"]
    for d in (12, 16):
        a1 = math.pi * (d / 10) ** 2 / 4
        s = min(a1 / max(v, 1e-9) for v in row["As"].values())
        s = math.floor(min(s, 3 * t, 0.45) * 40) / 40
        if s >= 0.10:
            return [f"{mark} (ขั้น 5 พื้น): เปลี่ยนเหล็กเป็น DB{d}@{s:.3f}".rstrip("0") + " ม."]
    tmin = 2 * (row["S"] + row["L"]) / 180
    t_new = max(math.ceil(tmin * 100) / 100, t + 0.02)
    return [f"{mark} (ขั้น 5 พื้น): เพิ่มความหนาพื้นเป็น {t_new * 100:.0f} ซม. (ไม่น้อยกว่าเส้นรอบรูป/180 = "
            f"{tmin * 100:.1f} ซม.) แล้วตรวจเหล็กใหม่"]


def footing_advice(row, b_) -> list:
    mark = row["mark"]
    out = []
    load = row["P"] * 1.10                                     # + the footing and soil (about 10 %)
    if row["piles"]:
        n = math.ceil(load / (b_["pile_cap"] * 1000))
        if n > row["piles"]:
            out.append(f"{mark} (ขั้น 2 ฐานราก): เพิ่มเสาเข็มเป็น {n} ต้น ({b_['pile_cap']:g} ตัน/ต้น) "
                       "และขยายฐานให้วางเข็มได้")
    else:
        if row["q"] > row["soil"] + 1e-6:
            side = math.ceil(math.sqrt(load / (b_["soil"] * 1000)) * 10) / 10
            n = math.ceil(load / (b_["pile_cap"] * 1000))
            out.append(f"{mark} (ขั้น 2 ฐานราก): ขยายฐานเป็น {side:.2f}×{side:.2f} ม. "
                       f"หรือใช้เสาเข็ม {n} ต้น ({b_['pile_cap']:g} ตัน/ต้น)")
    if row["V2"] > row["Vc2"] or row["V1"] > row["Vc1"]:
        t_new = row["t"] + 0.05
        out.append(f"{mark} (ขั้น 2 ฐานราก): เพิ่มความหนาฐานเป็น {t_new * 100:.0f} ซม. (แรงเฉือนทะลุ/ทางเดียวเกิน)")
    return out


def roof_advice(m, b_) -> list:
    from core import wanic_building as B
    label = m.name.split(" ", 1)[1].split(" — ")[0] if " " in m.name else ""
    res = m.diagram
    if res is None or not res.spans:
        return []
    L = res.spans[0].L
    w = res.spans[0].w
    M = max(res.Mmax, 1e-9)
    try:
        cur = C.section(label)
    except Exception:                                      # noqa: BLE001 - not a catalogued section
        return [f"{m.name}: ใช้หน้าตัดที่ใหญ่ขึ้น หรือลดระยะห่าง/ช่วง"]
    if cur["timber"]:
        return [f"{m.name}: ใช้ไม้หน้าตัดใหญ่ขึ้น หรือลดระยะห่าง (ไม้)"]
    E = b_["e_steel"]
    fam = label.split(" ")[0]
    cands = []
    for name, _f, _p in B.steel_presets():
        if not name.startswith(fam):
            continue
        s = C.section(name)
        if s["timber"] or s["S"] <= 0:
            continue
        cap = 0.60 * b_["fy_steel"] * 1e4 * s["S"]
        defl = 5 * w * L ** 4 / (384 * E * 1e4 * s["I"]) if s["I"] else 1e9
        if M <= cap and defl <= L / b_["defl"]:
            cands.append((s["kg_m"], name))
    if cands:
        return [f"{m.name}: เปลี่ยนเป็น {min(cands)[1]} (ขั้น 7 / แผงออกแบบอาคาร ▸ หลังคา) "
                f"หรือลดระยะห่าง/ช่วงลง"]
    return [f"{m.name}: ลดช่วงด้วยค้ำยัน/ตุ๊กตา หรือเปลี่ยนเป็นเหล็กรูปพรรณหน้าตัดใหญ่"]


def advise(res_all, data) -> list:
    """[(member name, [advice…])] for every failing member."""
    from core import wanic_calc_cards as CC
    b_ = res_all["basis"]
    out = []
    for m in res_all["members"]:
        if m.ok:
            continue
        try:
            if m.group == "beam" and m.diagram is not None and hasattr(m.diagram, "spec"):
                tips = beam_advice(m, b_)
            elif m.group == "column":
                tips = column_advice(m, data, b_)
            elif m.group == "roof":
                tips = roof_advice(m, b_)
            else:
                tips = []
        except Exception as e:                             # noqa: BLE001 - advice never breaks the calc
            tips = [f"(คำนวณคำแนะนำไม่ได้: {e})"]
        if tips:
            out.append((m.name, tips))
    for row in CC.slab_rows(res_all, data):
        if not row["ok"]:
            out.append((f"พื้น {row['mark']} {row['name']} {row['S']:.2f}×{row['L']:.2f} ม.", slab_advice(row, b_)))
    for row in CC.footing_rows(res_all, data):
        if not row["ok"]:
            tips = footing_advice(row, b_)
            if tips:
                out.append((f"ฐานราก {row['mark']} ที่ ({row['x']:.2f}, {row['y']:.2f})", tips))
    return out


def advice_by_member(res_all, data) -> dict:
    """member name → joined advice text (for the calculation table)."""
    return {name: " · ".join(tips) for name, tips in advise(res_all, data)}


# ---- per mark: the fix of the library mark from its worst member --------------------

class _Worst:
    """A stand-in BeamResult with the worst moments and shear of a mark."""

    def __init__(self, res):
        self.spec, self.mark, self.ground = res.spec, res.mark, res.ground
        self.Mmax, self.Mmin, self.Vmax = res.Mmax, res.Mmin, res.Vmax


def mark_fixes(res_all, data) -> list:
    """[(mark, {field: value}, text)] — one change per library mark that makes
    its worst member pass (beams, columns, slabs, footings)."""
    from core import wanic_building as B
    from core import wanic_calc_cards as CC
    b_ = res_all["basis"]
    fc, method = b_["fc"], b_["method"]
    lib = B.library_of(data)
    out = []
    # beams
    worst = {}
    for m in res_all["members"]:
        r = m.diagram
        if m.group != "beam" or r is None or not hasattr(r, "spec"):
            continue
        w = worst.setdefault(r.mark, _Worst(r))
        w.Mmax, w.Mmin, w.Vmax = max(w.Mmax, r.Mmax), min(w.Mmin, r.Mmin), max(w.Vmax, r.Vmax)
    for mark, w in worst.items():
        spec = dict(lib.get(mark, w.spec))
        cap = C.beam_capacity(spec, b_, fc)
        if w.Mmax <= cap["bot"] and -min(w.Mmin, 0) <= cap["top"] and w.Vmax <= cap["V"]:
            continue
        ch = {}
        bw, h = float(spec.get("b", 0.2)), float(spec.get("h", 0.4))
        for _round in range(8):
            d = h - R.COVER["beam"] - 0.012
            top, bot, st = R.parse_bar(spec.get("top")), R.parse_bar(spec.get("bot")), R.parse_bar(spec.get("stir"))
            Ab = _need_as(w.Mmax, bw, d, C.fy_of(bot, b_), fc, method)
            At = _need_as(-min(w.Mmin, 0), bw, d, C.fy_of(top, b_), fc, method)
            if not (math.isfinite(Ab) and math.isfinite(At)):
                h = round(h + 0.05, 2)
                ch["h"] = h
                spec["h"] = h
                continue
            if Ab > (bot.n * bot.area if bot else 0):
                n, dia = _bars_for(Ab, bot, bot.kind if bot else "DB", bw)
                ch["bot"] = spec["bot"] = f"{n}-{bot.kind if bot else 'DB'}{dia}"
            if At > (top.n * top.area if top else 0):
                n, dia = _bars_for(At, top, top.kind if top else "DB", bw)
                ch["top"] = spec["top"] = f"{n}-{top.kind if top else 'DB'}{dia}"
            cap = C.beam_capacity(spec, b_, fc)
            if w.Vmax > cap["V"] and st:
                phi = 0.85 if method == "SDM" else 1.0
                vc = (0.53 if method == "SDM" else 0.29) * math.sqrt(fc) * bw * 100 * d * 100
                vs = w.Vmax / phi - vc
                vmax = (2.1 if method == "SDM" else 1.32) * math.sqrt(fc) * bw * 100 * d * 100
                if vs > vmax:
                    h = round(h + 0.05, 2)
                    ch["h"] = spec["h"] = h
                    continue
                fyv = C.fy_of(st, b_) if method == "SDM" else C.fs_of(st, b_)
                s_ = math.floor(min(2 * st.area * fyv * d * 100 / vs / 100, d / 2) * 40) / 40
                if s_ < 0.075:
                    st = R.parse_bar(f"RB9@{0.15}")
                    s_ = math.floor(min(2 * st.area * fyv * d * 100 / vs / 100, d / 2) * 40) / 40
                    ch["stir"] = spec["stir"] = f"RB9@{max(s_, 0.05):.3f}".rstrip("0")
                else:
                    ch["stir"] = spec["stir"] = f"{st.kind}{st.d}@{s_:.3f}".rstrip("0")
            break
        if ch:
            text = ", ".join(f"{_TH.get(k, k)} {v * 100:.0f} ซม." if k == "h" else f"{_TH.get(k, k)} {v}"
                             for k, v in ch.items())
            out.append((mark, ch, f"{mark}: {text}"))
    # columns: the worst P-M of the mark
    worst_c = {}
    for m in res_all["members"]:
        if m.group == "column" and m.diagram is not None:
            mark = m.name.split(" ")[0]
            if mark not in worst_c or m.ratio > worst_c[mark].ratio:
                worst_c[mark] = m
    for mark, m in worst_c.items():
        if m.ok:
            continue
        tip = column_advice(m, data, b_)[0]
        spec = dict(lib.get(mark, {}))
        ch = {}
        import re
        mm = re.search(r"(\d+)×(\d+) ซม\. เหล็กยืน (\d+-[A-Z]+\d+)", tip)
        if mm:
            ch = {"b": int(mm.group(1)) / 100, "h": int(mm.group(2)) / 100, "main": mm.group(3)}
        else:
            mm = re.search(r"เหล็กยืนเป็น (\d+-[A-Z]+\d+)", tip)
            if mm:
                ch = {"main": mm.group(1)}
        if ch:
            out.append((mark, ch, tip))
    # slabs: the smallest spacing any panel of the mark needs
    rows = [r for r in CC.slab_rows(res_all, data) if not r["ok"]]
    by = {}
    for r in rows:
        need = min((x for x in r["s"].values() if x), default=1.0)
        if r["mark"] not in by or need < by[r["mark"]][1]:
            by[r["mark"]] = (r, need)
    for mark, (r, _need) in by.items():
        tip = slab_advice(r, b_)[0]
        import re
        mm = re.search(r"(RB|DB)(\d+)@([\d.]+)", tip)
        if mm:
            out.append((mark, {"bars": f"{mm.group(1)}{mm.group(2)}@{float(mm.group(3)):.3f}".rstrip("0")}, tip))
        else:
            mm = re.search(r"ความหนาพื้นเป็น (\d+) ซม", tip)
            if mm:
                out.append((mark, {"t": int(mm.group(1)) / 100}, tip))
    # footings: the most loaded of each mark
    best = {}
    for r in CC.footing_rows(res_all, data):
        if r["mark"] not in best or r["P"] > best[r["mark"]]["P"]:
            best[r["mark"]] = r
    for mark, r in best.items():
        if r["ok"]:
            continue
        load = r["P"] * 1.10
        ch = {}
        if r["piles"]:
            ch["piles"] = max(r["piles"], math.ceil(load / (b_["pile_cap"] * 1000)))
        elif r["q"] > r["soil"]:
            side = math.ceil(math.sqrt(load / (b_["soil"] * 1000)) * 10) / 10
            ch["w"] = ch["l"] = side
        if r["V2"] > r["Vc2"] or r["V1"] > r["Vc1"] or ch.get("w"):
            side = ch.get("w", r["w"])
            ch["t"] = max(r["t"], math.ceil(max(0.25, side / 5) * 20) / 20)
        if ch:
            text = ", ".join(f"{_TH.get(k, k)} {v}" for k, v in ch.items())
            out.append((mark, ch, f"{mark}: {text}"))
    return out


_TH = {"top": "เหล็กบน", "bot": "เหล็กล่าง", "stir": "ปลอก", "h": "ลึก", "main": "เหล็กยืน", "bars": "เหล็กพื้น",
       "t": "หนา (ม.)", "w": "กว้าง (ม.)", "l": "ยาว (ม.)", "piles": "เสาเข็ม (ต้น)", "b": "กว้าง (ม.)"}


def _fmt(k, v) -> str:
    if k in ("h", "b") and isinstance(v, (int, float)):
        return f"{_TH.get(k, k).split(' ')[0]} {v * 100:.0f} ซม."
    if k in ("w", "l", "t") and isinstance(v, (int, float)):
        return f"{_TH.get(k, k).split(' ')[0]} {v:.2f} ม."
    return f"{_TH.get(k, k)} {v}"


def apply_fixes(data, rounds: int = 4) -> list:
    """Apply the per-mark fixes to data["library"] and re-analyse until
    everything passes (the loads change with the sizes), then the detailing
    minimums; returns one line per changed mark with its final values."""
    from core import wanic_building as B
    before = B.library_of(data)
    for _ in range(rounds):
        res = C.analyse(data)
        fixes = mark_fixes(res, data)
        if not fixes:
            break
        lib = dict((data.get("library") or {}))
        for mark, ch, _text in fixes:
            spec = dict(lib.get(mark) or {})
            spec.update(ch)
            lib[mark] = spec
        data["library"] = lib
    # the detailing minimums (14/fy, ρ ≥ 1 %, 0.0018 bt …) on every mark
    full = B.library_of(data)
    lib = dict(data.get("library") or {})
    for mark, r in R.check_library(full).items():
        if r.ok:
            continue
        new = R.suggest(full[mark])
        ch = {k: v for k, v in new.items() if full[mark].get(k) != v}
        if ch:
            spec = dict(lib.get(mark) or {})
            spec.update(ch)
            lib[mark] = spec
    data["library"] = lib
    after = B.library_of(data)
    step = {"footing": "ขั้น 2 ฐานราก", "stump": "ขั้น 3 ตอม่อ", "slab": "ขั้น 5 พื้น", "column": "ขั้น 6 เสา",
            "beam": "ขั้น 4/6 คาน"}
    out = []
    for mark in sorted(after):
        old, new = before.get(mark, {}), after[mark]
        ch = {k: v for k, v in new.items() if old.get(k) != v}
        if ch:
            was = ", ".join(_fmt(k, old.get(k)) for k in ch if old.get(k) is not None)
            out.append(f"{mark} ({step.get(new.get('kind'), '')}): " + ", ".join(_fmt(k, v) for k, v in ch.items())
                       + (f"  (เดิม {was})" if was else ""))
    return out
