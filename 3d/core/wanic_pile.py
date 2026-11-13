# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
"""เสาเข็ม 2 ขนาด · กำลังเข็มจากผลทดสอบ — two pile types (P1, P2) the
footing marks choose from, each with its section, length and how its safe
load is known:

- ``given``   — the safe load stated (t / pile);
- ``static``  — a static load test: Qa = Qult / FS (FS 2.0);
- ``dynamic`` — a dynamic load test (PDA / seismic): Qa = Qult / FS (2.5);
- ``hiley``   — the driving record, Hiley: Qu = e·W·H / (S + C/2), FS 3.0;
- ``soil``    — boring data: Qult = Σ fs·perimeter·thickness + qb·area, FS 2.5;

then never more than the pile itself carries: 0.25 fc′ Ac (structural).
Section properties are typical values — check them with the maker."""
from __future__ import annotations

import math

#: sections: key → (name, shape, width or Ø (m), area (m²), perimeter (m), fc′ ksc)
SECTIONS = {
    "I18": ("เข็มตัวไอ I-0.18", "I", 0.18, 0.0230, 0.80, 350),
    "I22": ("เข็มตัวไอ I-0.22", "I", 0.22, 0.0340, 0.96, 350),
    "I26": ("เข็มตัวไอ I-0.26", "I", 0.26, 0.0470, 1.12, 350),
    "I30": ("เข็มตัวไอ I-0.30", "I", 0.30, 0.0620, 1.30, 350),
    "S25": ("เข็มสี่เหลี่ยมตัน 0.25×0.25", "square", 0.25, 0.0625, 1.00, 350),
    "S30": ("เข็มสี่เหลี่ยมตัน 0.30×0.30", "square", 0.30, 0.0900, 1.20, 350),
    "S35": ("เข็มสี่เหลี่ยมตัน 0.35×0.35", "square", 0.35, 0.1225, 1.40, 350),
    "S40": ("เข็มสี่เหลี่ยมตัน 0.40×0.40", "square", 0.40, 0.1600, 1.60, 350),
    "D30": ("เข็มกลมกลวง (สปัน) Ø0.30", "round", 0.30, 0.0452, 0.94, 600),
    "D35": ("เข็มกลมกลวง (สปัน) Ø0.35", "round", 0.35, 0.0584, 1.10, 600),
    "D40": ("เข็มกลมกลวง (สปัน) Ø0.40", "round", 0.40, 0.0754, 1.26, 600),
    "D50": ("เข็มกลมกลวง (สปัน) Ø0.50", "round", 0.50, 0.1131, 1.57, 600),
    "B35": ("เข็มเจาะ Ø0.35", "round", 0.35, 0.0962, 1.10, 240),
    "B50": ("เข็มเจาะ Ø0.50", "round", 0.50, 0.1963, 1.57, 240),
    "B60": ("เข็มเจาะ Ø0.60", "round", 0.60, 0.2827, 1.88, 240),
}
METHODS = {"given": "กำหนดค่ารับน้ำหนักปลอดภัยเอง", "static": "ทดสอบแบบสถิต (Static Load Test)",
           "dynamic": "ทดสอบแบบพลวัต (Dynamic Load Test)", "hiley": "บันทึกการตอก (สูตร Hiley)",
           "soil": "ข้อมูลเจาะสำรวจดิน (แรงเสียดทาน + แรงแบกทาน)"}
FS_DEFAULT = {"given": 1.0, "static": 2.0, "dynamic": 2.5, "hiley": 3.0, "soil": 2.5}

DEFAULT_TYPES = {
    "P1": {"section": "I18", "len": 6.0, "method": "given", "Qa": 8.0},
    "P2": {"section": "I22", "len": 12.0, "method": "static", "Qult": 40.0},
}


def types_of(data, b_=None) -> dict:
    """The building's pile types (P1, P2); P1 defaults to the basis' safe
    load per pile so an old document keeps its numbers."""
    own = (data or {}).get("piles") or {}
    out = {}
    for k, d in DEFAULT_TYPES.items():
        t = dict(d)
        if k == "P1" and b_ is not None:
            t["Qa"] = float(b_.get("pile_cap", t["Qa"]))
        t.update(own.get(k) or {})
        out[k] = t
    return out


def capacity(t: dict) -> dict:
    """{"Qult", "FS", "Qa_geo", "Q_struct", "Qa" (t), "lines", "governs"}."""
    sec = SECTIONS.get(t.get("section"), SECTIONS["I18"])
    name, shape, b, A, per, fc = sec
    fc = float(t.get("fc") or fc)
    L = float(t.get("len") or 6.0)
    m = t.get("method", "given")
    FS = float(t.get("FS") or FS_DEFAULT.get(m, 2.5))
    lines = [f"{name} ยาว {L:.2f} ม. · พื้นที่หน้าตัด ≈ {A:.4f} ตร.ม. · เส้นรอบรูป ≈ {per:.2f} ม."]
    Qult = None
    if m == "given":
        Qa_geo = float(t.get("Qa") or 0.0)
        lines.append(f"กำหนด รับน้ำหนักปลอดภัย {Qa_geo:,.2f} ตัน/ต้น")
    elif m in ("static", "dynamic"):
        Qult = float(t.get("Qult") or 0.0)
        Qa_geo = Qult / FS
        lines.append(f"{METHODS[m]}: Qult = {Qult:,.2f} ตัน · FS = {FS:g} → Qa = {Qa_geo:,.2f} ตัน/ต้น")
    elif m == "hiley":
        W, H = float(t.get("W") or 1.5), float(t.get("H") or 0.5)          # t, m
        S, Cc = float(t.get("S") or 10.0), float(t.get("C") or 25.0)       # mm per blow, mm
        e = float(t.get("eff") or 0.8)
        Qult = e * W * H * 1000.0 / (S + Cc / 2.0)
        Qa_geo = Qult / FS
        lines.append(f"Hiley: Qu = e·W·H / (S + C/2) = {e:g}×{W:g}×{H * 1000:g} / ({S:g} + {Cc:g}/2) = "
                     f"{Qult:,.2f} ตัน · FS = {FS:g} → Qa = {Qa_geo:,.2f} ตัน/ต้น")
        lines.append(f"(ตุ้ม {W:g} ตัน ยกสูง {H:.2f} ม. · ทรุดเฉลี่ย 10 ครั้งสุดท้าย {S:g} มม./ครั้ง)")
    else:                                                                  # soil
        layers = t.get("layers") or [[L, 2.0]]
        qb = float(t.get("qb") or 0.0)
        skin = 0.0
        depth = 0.0
        for th, fs in layers:
            th = min(float(th), max(L - depth, 0.0))
            skin += float(fs) * per * th
            depth += th
        end = qb * A
        Qult = skin + end
        Qa_geo = Qult / FS
        lines.append(f"แรงเสียดทาน Σfs·P·L = {skin:,.2f} ตัน · แรงแบกทานปลาย qb·A = {qb:g}×{A:.4f} = {end:,.2f} ตัน")
        lines.append(f"Qult = {Qult:,.2f} ตัน · FS = {FS:g} → Qa = {Qa_geo:,.2f} ตัน/ต้น")
    Q_struct = 0.25 * fc * A * 10.0                                        # ksc × m² → t (×10⁴/10³)
    lines.append(f"กำลังตัวเข็ม 0.25 fc′ Ac = 0.25×{fc:g}×{A * 1e4:,.0f} ตร.ซม. = {Q_struct:,.2f} ตัน")
    Qa = min(Qa_geo, Q_struct)
    gov = "ดิน/ผลทดสอบ" if Qa_geo <= Q_struct else "กำลังตัวเข็ม"
    lines.append(f"ใช้ Qa = {Qa:,.2f} ตัน/ต้น (ควบคุมโดย{gov})")
    return {"Qult": Qult, "FS": FS, "Qa_geo": Qa_geo, "Q_struct": Q_struct, "Qa": Qa, "lines": lines,
            "governs": gov, "name": name, "shape": shape, "b": b, "len": L}


def type_of_spec(spec: dict) -> str:
    """The pile type of a footing mark (P1 unless it says P2)."""
    t = (spec or {}).get("pile") or "P1"
    return t if t in DEFAULT_TYPES else "P1"


def cap_of(spec: dict, data, b_) -> float:
    """Safe load per pile (t) of a footing mark."""
    return capacity(types_of(data, b_)[type_of_spec(spec)])["Qa"]


def spec_geometry(spec: dict, data, b_) -> dict:
    """pile_b / pile_len of a footing mark from its pile type."""
    c = capacity(types_of(data, b_)[type_of_spec(spec)])
    return {"pile_b": c["b"], "pile_len": c["len"]}


def pile_text(data, b_) -> str:
    """«เข็ม 8 ตัน/ต้น», or with two types «เข็ม P1 9.76 · P2 35.00 ตัน/ต้น»."""
    if not (data or {}).get("piles"):
        return f"เข็ม {float(b_['pile_cap']):g} ตัน/ต้น"
    t = types_of(data, b_)
    return "เข็ม " + " · ".join(f"{k} {capacity(t[k])['Qa']:,.2f}" for k in ("P1", "P2")) + " ตัน/ต้น"
