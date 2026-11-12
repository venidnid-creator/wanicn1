# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
"""บันได คสล. — straight, L (a 90° landing) and two-flight (a 180° landing)
stairs: the step sizes against กฎกระทรวง ฉบับที่ 55 (พ.ศ. 2543) for
dwellings (width ≥ 0.80 m, riser ≤ 0.20 m, going ≥ 0.22 m, one flight ≤
3.00 m high, landing ≥ the stair's width) and the comfort rule 2R + T =
0.60–0.65 m; the waist slab designed as a one-way slab spanning along the
flight (the landing in the same span, carried by a landing beam), SDM or
WSD as the building's basis; the landing beam."""
from __future__ import annotations

import math

from core import wanic_building as B
from core import wanic_calc as C
from core import wanic_rc as R

LL_STAIR = 300.0                       # kg/m² — บันได ช่องทางเดิน (กฎกระทรวง ฉบับที่ 6)
DEFAULTS = {"stair_bars": "DB12@0.15", "stair_temp": "RB9@0.15", "stair_ll": LL_STAIR,
            "stair_beam": "0.15x0.35 2-DB12/2-DB12 RB6@0.15"}
COVER = 0.020


def params(s) -> dict:
    out = dict(DEFAULTS)
    for k in DEFAULTS:
        if s.get(k) not in (None, ""):
            out[k] = s[k]
    out["stair_ll"] = float(out["stair_ll"])
    return out


def beam_spec(text: str) -> dict:
    """«0.15x0.35 2-DB12/2-DB12 RB6@0.15» → a beam spec for beam_capacity."""
    try:
        size, bars, stir = text.split()
        b, h = (float(v) for v in size.lower().split("x"))
        bot, top = bars.split("/")
        return {"b": b, "h": h, "bot": bot, "top": top, "stir": stir}
    except ValueError:
        return {"b": 0.15, "h": 0.35, "bot": "2-DB12", "top": "2-DB12", "stir": "RB6@0.15"}


def geometry_checks(lay) -> list:
    """[(item, value, limit, ok)] for the step sizes, in plain Thai."""
    R_, g, w = lay["R"], lay["g"], lay["w"]
    fl_h = max(f["n"] for f in lay["flights"]) * R_
    blondel = 2 * R_ + g
    rows = [("ลูกตั้ง (ความสูงขั้น)", f"{R_ * 100:.1f} ซม.", "ไม่เกิน 20 ซม.", R_ <= 0.20 + 1e-9),
            ("ลูกนอน (ความกว้างขั้น)", f"{g * 100:.1f} ซม.", "ไม่น้อยกว่า 22 ซม.", g >= 0.22 - 1e-9),
            ("ความกว้างบันได", f"{w:.2f} ม.", "ไม่น้อยกว่า 0.80 ม.", w >= 0.80 - 1e-9),
            ("ความสูงต่อช่วง (ไม่มีชานพัก)", f"{fl_h:.2f} ม.", "ไม่เกิน 3.00 ม.", fl_h <= 3.0 + 1e-9),
            ("เดินสบาย 2R + T", f"{blondel * 100:.1f} ซม.", "60–65 ซม. (แนะนำ)", 0.595 <= blondel <= 0.655)]
    if lay["landings"]:
        rows.insert(4, ("ชานพัก", f"กว้าง/ยาว {w:.2f} ม.", "ไม่น้อยกว่าความกว้างบันได", True))
    return rows


def _capacity(bar, t, b_):
    """φMn per metre width (kg·m/m) and the effective depth."""
    d = t - COVER - (bar.d / 2000.0 if bar else 0.006)
    if not (bar and bar.s):
        return 0.0, d, 0.0
    As = bar.area / bar.s                                  # cm²/m
    fc = b_["fc"]
    if b_["method"] == "SDM":
        a = As * C.fy_of(bar, b_) / (0.85 * fc * 100)
        cap = 0.90 * As * C.fy_of(bar, b_) * (d * 100 - a / 2) / 100
    else:
        cap = As * C.fs_of(bar, b_) * 0.875 * d * 100 / 100
    return cap, d, As


def design(st, s, b_, title="บันได") -> dict:
    """One stair: its layout, the step checks, every flight's span, loads,
    moments, steel and shear, the landing beam; and Members for the
    calculation table."""
    lay = B.stair_layout(st, s)
    p = params(s)
    D_, L_ = C.factors(b_)
    conc = float(b_.get("concrete", 2400.0))
    t = float(st.get("t") or s["stair_t"])
    R_, g, w = lay["R"], lay["g"], lay["w"]
    cos = g / math.hypot(g, R_)
    fin = float(b_.get("finish", 50.0))
    dead_inc = conc * (t / cos + R_ / 2) + fin * (1 + R_ / g)        # per m² of plan
    dead_land = conc * t + fin
    ll = p["stair_ll"]
    wu_inc = D_ * dead_inc + L_ * ll
    wu_land = D_ * dead_land + L_ * ll
    bar = R.parse_bar(st.get("bars") or p["stair_bars"])
    temp = R.parse_bar(st.get("temp") or p["stair_temp"])
    cap, d, As = _capacity(bar, t, b_)
    fc = b_["fc"]
    sdm = b_["method"] == "SDM"
    vc = (0.85 * 0.53 if sdm else 0.29) * math.sqrt(fc) * 100 * d * 100   # kg per m width
    as_min = (0.0018 if bar and C.fy_of(bar, b_) >= 4000 else 0.0025) * 100 * t * 100
    as_temp = (temp.area / temp.s) if temp and temp.s else 0.0
    as_tmin = (0.0018 if temp and C.fy_of(temp, b_) >= 4000 else 0.0025) * 100 * t * 100
    flights = []
    members = []
    land_R = 0.0                       # kg per m of the landing beam
    n_f = len(lay["flights"])
    for i, f in enumerate(lay["flights"]):
        run = f["L"]
        if n_f == 1:
            span, parts = run, [(0.0, run, wu_inc)]
        elif i == 0:
            span, parts = run + w, [(0.0, run, wu_inc), (run, run + w, wu_land)]
        else:
            span, parts = run + w, [(0.0, w, wu_land), (w, w + run, wu_inc)]
        sp = C.Span(span, 0.0, U=[(a, b, q) for a, b, q in parts])
        res = C.solve_beam([sp])
        Mu, Vu = res.Mmax, res.Vmax
        res.caps = {"M+": cap, "M-": cap, "V": vc, "lab_M": "φMn" if sdm else "Ma",
                    "lab_V": "φVc" if sdm else "Vc"}
        t_min = span / 20.0
        r = max(Mu / cap if cap else 9.9, Vu / vc if vc else 9.9)
        if n_f > 1:
            land_R += res.reactions[1] if i == 0 else res.reactions[0]
        notes = []
        if cap and Mu > cap:
            notes.append(f"โมเมนต์เกินกำลัง {Mu / cap:.2f} เท่า")
        if vc and Vu > vc:
            notes.append(f"แรงเฉือนเกินกำลังคอนกรีต {Vu / vc:.2f} เท่า")
        if t < t_min - 1e-9:
            notes.append(f"ท้องบันไดบางกว่าขั้นต่ำ L/20 = {t_min * 100:.1f} ซม. (กันแอ่นตัว)")
        if As < as_min:
            notes.append(f"เหล็กหลักน้อยกว่าขั้นต่ำ {as_min:.2f} ตร.ซม./ม.")
        if as_temp < as_tmin:
            notes.append(f"เหล็กกันร้าวน้อยกว่าขั้นต่ำ {as_tmin:.2f} ตร.ซม./ม.")
        name = f"{title} · ช่วงที่ {i + 1}" if n_f > 1 else title
        short = As < as_min or as_temp < as_tmin or t < t_min - 1e-9
        flights.append({"i": i + 1, "n": f["n"], "run": run, "span": span, "parts": parts, "res": res,
                        "Mu": Mu, "Vu": Vu, "cap": cap, "vc": vc, "ratio": r, "notes": notes, "t_min": t_min})
        m = C.Member("stair", name, f"Mu = {Mu:,.0f} กก.-ม./ม. · Vu = {Vu:,.0f} กก./ม. (ช่วง {span:.2f} ม.)",
                     f"φMn = {cap:,.0f} ({st.get('bars') or p['stair_bars']}) · φVc = {vc:,.0f}",
                     max(r, 1.01) if short else r,
                     "; ".join(notes) or f"wu ลาดเอียง {wu_inc:,.0f} · ชานพัก {wu_land:,.0f} กก./ตร.ม.", res,
                     qty=0.0 if short and r <= 1 else wu_inc, qty_unit="กก./ตร.ม. (คนเดินขึ้นลง/ของ)",
                     qty_factor=L_)
        res.mark, res.spec, res.level, res.axis, res.line, res.z, res.ground = \
            "ST", {"b": 1.0, "h": t}, 0, "x", 0.0, 0.0, False
        members.append(m)
    beam = None
    if n_f > 1:
        bs = beam_spec(p["stair_beam"])
        Lb = (2 * w + B.STAIR_GAP) if lay["type"] == "U" else w
        wb = land_R + D_ * bs["b"] * bs["h"] * conc
        bres = C.solve_beam([C.Span(Lb, wb)])
        bcap = C.beam_capacity(bs, b_, fc)
        bres.caps = {"M+": bcap["bot"], "M-": bcap["top"], "V": bcap["V"], "Vc": bcap["Vc"],
                     "lab_M": "φMn" if sdm else "Ma", "lab_V": "φVn" if sdm else "Va"}
        br = max(bres.Mmax / bcap["bot"] if bcap["bot"] else 9.9, bres.Vmax / bcap["V"] if bcap["V"] else 9.9)
        beam = {"spec": bs, "text": p["stair_beam"], "L": Lb, "w": wb, "res": bres, "ratio": br}
        members.append(C.Member("stair", f"{title} · คานรับชานพัก (BS1)",
                                f"Mu = {bres.Mmax:,.0f} กก.-ม. · Vu = {bres.Vmax:,.0f} กก. (ยาว {Lb:.2f} ม.)",
                                f"φMn {bcap['bot']:,.0f} · φVn {bcap['V']:,.0f} ({p['stair_beam']})", br,
                                f"w = {wb:,.0f} กก./ม. จากบันไดทั้ง {n_f} ช่วง", bres,
                                qty=wb / ((D_ + L_) / 2), qty_unit="กก. ต่อเมตรของคาน"))
    geo = geometry_checks(lay)
    bad = [g_ for g_ in geo if not g_[3] and "แนะนำ" not in g_[2]]
    members.insert(0, C.Member("stair", f"{title} · ขนาดขั้น (กฎกระทรวง 55)",
                               " · ".join(f"{a} {v}" for a, v, _l, _o in geo[:3]),
                               "ลูกตั้ง ≤ 20 ซม. · ลูกนอน ≥ 22 ซม. · กว้าง ≥ 0.80 ม. · ช่วงละ ≤ 3.00 ม.",
                               max(R_ / 0.20, 0.22 / g, 0.80 / w,
                                   max(f["n"] for f in lay["flights"]) * R_ / 3.0),
                               "; ".join(f"{a} {v} ({lim})" for a, v, lim, _o in bad) or "ผ่านทุกข้อ"))
    return {"title": title, "layout": lay, "t": t, "dead_inc": dead_inc, "dead_land": dead_land, "ll": ll,
            "wu_inc": wu_inc, "wu_land": wu_land, "bars": st.get("bars") or p["stair_bars"],
            "temp": st.get("temp") or p["stair_temp"], "As": As, "As_min": as_min, "As_temp": as_temp,
            "As_tmin": as_tmin, "d": d, "flights": flights, "beam": beam, "geo": geo, "members": members,
            "cos": cos}


def designs(data, b_=None) -> list:
    """Every stair of the building, designed."""
    E = B.elements(data)
    s = E["settings"]
    b_ = b_ or C.basis(data)
    out = []
    for e in E["stairs"]:
        k = e["floor"]
        title = f"บันได ชั้น {k + 1}→{k + 2} · {B.STAIR_TYPES[B.stair_type(e['st'])].split(' (')[0]}"
        dz = design(e["st"], s, b_, title)
        dz["floor"] = k
        dz["st"] = e["st"]
        out.append(dz)
    return out


BAR_STEPS = ["DB12@0.20", "DB12@0.15", "DB12@0.125", "DB12@0.10", "DB16@0.15", "DB16@0.125", "DB16@0.10",
             "DB20@0.125", "DB20@0.10"]
TEMP_STEPS = ["RB9@0.20", "RB9@0.15", "RB9@0.125", "DB10@0.15", "DB10@0.125", "DB12@0.15"]
BEAM_STEPS = ["0.15x0.35 2-DB12/2-DB12 RB6@0.15", "0.20x0.40 2-DB12/3-DB12 RB6@0.15",
              "0.20x0.40 2-DB16/3-DB16 RB6@0.15", "0.20x0.50 2-DB16/3-DB16 RB9@0.15",
              "0.25x0.50 3-DB16/4-DB16 RB9@0.15", "0.25x0.60 3-DB20/4-DB20 RB9@0.15"]


def _passes(dz) -> bool:
    return all(f["ratio"] <= 1.0 for f in dz["flights"]) and dz["As"] >= dz["As_min"] - 1e-9 \
        and dz["As_temp"] >= dz["As_tmin"] - 1e-9 and all(f["t_min"] <= dz["t"] + 1e-9 for f in dz["flights"])


def suggest(st, s, b_) -> tuple:
    """(changes to the stair {"t", "bars", "temp"}, beam spec text or None,
    advice lines) — the thinnest waist ≥ L/20 and the least steel that
    pass; the landing beam's first size that passes."""
    dz = design(st, s, b_)
    span = max(f["span"] for f in dz["flights"])
    t0 = max(dz["t"], math.ceil(span / 20.0 * 100 - 1e-6) / 100)
    best = None
    for k in range(0, 16):
        t = round(t0 + k * 0.01, 2)
        for bars in BAR_STEPS:
            for temp in TEMP_STEPS:
                trial = dict(st, t=t, bars=bars, temp=temp)
                if _passes(design(trial, s, b_)):
                    best = {"t": t, "bars": bars, "temp": temp}
                    break
            if best:
                break
        if best:
            break
    tips = []
    ch = {}
    if best:
        if abs(best["t"] - dz["t"]) > 1e-9:
            ch["t"] = best["t"]
            tips.append(f"เพิ่มความหนาท้องบันไดเป็น {best['t'] * 100:.0f} ซม. (≥ ช่วง {span:.2f} ม. ÷ 20)")
        if best["bars"] != dz["bars"]:
            ch["bars"] = best["bars"]
            tips.append(f"เหล็กหลักตามแนวบันไดเป็น {best['bars']} (เหล็กล่าง วางตามลาดและต่อเข้าชานพัก)")
        if best["temp"] != dz["temp"]:
            ch["temp"] = best["temp"]
            tips.append(f"เหล็กกันร้าว (ตามขวาง) เป็น {best['temp']}")
        if dz["layout"]["type"] == "straight" and span > 3.6:
            tips.append("หรือเปลี่ยนเป็นบันไดตัว L / สองช่วง เพื่อให้ช่วงพาดสั้นลง (มีคานรับชานพัก)")
    else:
        tips.append("ช่วงพาดยาวเกินไป — เปลี่ยนเป็นบันไดตัว L / สองช่วง หรือเพิ่มคานรับกลางช่วง")
    beam = None
    if dz["beam"] and dz["beam"]["ratio"] > 1.0:
        trial = dict(st, **ch)
        for text in BEAM_STEPS:
            s2 = dict(s, stair_beam=text)
            if (design(trial, s2, b_)["beam"] or {}).get("ratio", 9) <= 1.0:
                beam = text
                tips.append(f"คานรับชานพัก BS1 เป็น {text}")
                break
    return ch, beam, tips


def find_stair(data, sid):
    for f in data.get("floors") or []:
        for stp in f.get("stairs") or []:
            if stp.get("id") == sid:
                return stp
    return None


def apply_all(data) -> list:
    """Fix every failing stair in data (the stair dicts and the landing
    beam setting); returns one line per stair changed."""
    b_ = C.basis(data)
    s = B.settings_of(data)
    out = []
    for dz in designs(data, b_):
        if all(m.ok for m in dz["members"][1:]):
            continue
        ch, beam, _tips = suggest(dz["st"], s, b_)
        stp = find_stair(data, dz["st"].get("id"))
        if stp is not None and ch:
            stp.update(ch)
        if beam:
            st_ = dict(data.get("settings") or {})
            st_["stair_beam"] = beam
            data["settings"] = st_
            s = B.settings_of(data)
        if ch or beam:
            out.append(f"{dz['title']}: " + " · ".join(
                [f"หนา {ch['t'] * 100:.0f} ซม." if "t" in ch else "", ch.get("bars", ""), ch.get("temp", ""),
                 f"คานชานพัก {beam}" if beam else ""]).strip(" ·").replace(" ·  · ", " · "))
    return out


def advice_for(m, res_all, data) -> list:
    """The advice of a failing stair row of the calculation table."""
    b_ = res_all["basis"]
    s = B.settings_of(data)
    for dz in res_all.get("stairs") or []:
        if m.name.startswith(dz["title"]):
            if "ขนาดขั้น" in m.name:
                tips = []
                lay = dz["layout"]
                if lay["R"] > 0.20:
                    tips.append(f"ลูกตั้งสูงเกิน 20 ซม. — ลดค่า «ลูกตั้งสูงสุด» ในค่าอาคาร (ตอนนี้ {lay['R'] * 100:.1f} ซม.)")
                if lay["g"] < 0.22:
                    tips.append("ลูกนอนแคบกว่า 22 ซม. — เพิ่มค่า «ลูกนอน» ในค่าอาคาร")
                if lay["w"] < 0.80:
                    tips.append("บันไดแคบกว่า 0.80 ม. — เพิ่มความกว้างบันได")
                if max(f["n"] for f in lay["flights"]) * lay["R"] > 3.0:
                    tips.append("ช่วงเดียวสูงเกิน 3.00 ม. — เปลี่ยนเป็นบันไดตัว L หรือสองช่วง (มีชานพัก)")
                return tips
            return suggest(dz["st"], s, b_)[2]
    return []
