# -*- coding: utf-8 -*-
"""Detailing rules of ประกาศกระทรวงมหาดไทย เรื่อง การออกแบบโครงสร้างอาคาร ...
พ.ศ. 2567 ข้อ 29 [MI2567-29D], [MI2567-29C], and the site notes that
follow from the province (ผนวก ก, ข) and กฎกระทรวง ฉบับที่ 72.

Units: cm, ksc, kg.
"""
from __future__ import annotations

import math

from .materials import FY
from .sections import BAR_DIA

# ---------------------------------------------------------------------------
# Concrete cover, cast in place — ข้อ 29 (13) ตาราง 13
# ---------------------------------------------------------------------------
COVER_EARTH = 7.5            # cast against and permanently exposed to earth
COVER_EXPOSED_BIG = 5.0      # exposed to earth or weather, bars > 16 mm
COVER_EXPOSED = 4.0          # … bars ≤ 16 mm
COVER_SLAB = 2.0             # not exposed: slabs, walls, joists (bars ≤ 36 mm)
COVER_BEAM = 3.0             # not exposed: beams, main bars and stirrups
COVER_COLUMN = 3.5           # not exposed: columns, ties or spirals


def cover_factor(mat) -> float:
    """+20% when fc' < 210 ksc or without quality control — ตาราง 13 (ง)."""
    return 1.2 if (not mat.qc or mat.fc_prime < 210) else 1.0


def beam_offset(mat, exposed: bool, db: float = 1.6, tie: float = 0.6) -> float:
    """Top of beam to the centre of the main bars, cm."""
    c = (COVER_EXPOSED_BIG if db > 1.6 else COVER_EXPOSED) if exposed else COVER_BEAM
    return c * cover_factor(mat) + tie + db / 2


def slab_offset(mat, db: float = 0.9) -> float:
    return COVER_SLAB * cover_factor(mat) + db / 2


def footing_offset(mat, db: float = 1.6) -> float:
    """To the upper layer of the bottom mat."""
    return COVER_EARTH * cover_factor(mat) + 1.5 * db


def column_cover(mat) -> float:
    """To the ties: the exposed value, so that the stub below the ground beams is covered too."""
    return COVER_EXPOSED * cover_factor(mat)


# ---------------------------------------------------------------------------
# Minimum steel and spacing — ข้อ 29 (11)
# ---------------------------------------------------------------------------
SLAB_MIN_THICKNESS = 0.08     # m, (ง)
COLUMN_MIN_SIDE = 0.20        # m, (ข)
FOOTING_MIN_SPREAD = 0.20     # m, (ก) spread footings, short piles in soft soil
FOOTING_MIN_PILE = 0.35       # m, (ก) other pile footings


def slab_min_ratio(grade: str, on_ground: bool = False) -> float:
    """(ฉ): round bars 0.0025, SD30 0.0020, SD40 0.0018, higher grades 0.0018×4000/fy ≥ 0.0014,
    slab on grade 0.0015."""
    if on_ground:
        return 0.0015
    fy = FY[grade]
    if grade.startswith("SR") or fy <= 2400:
        return 0.0025
    if fy <= 3000:
        return 0.0020
    return 0.0018 if fy <= 4000 else max(0.0014, 0.0018 * 4000 / fy)


def slab_max_spacing(t_m: float, two_way: bool) -> float:
    """(ช): ≤ 3t and ≤ 300 mm; ≤ 2t at the critical sections of two-way slabs. cm."""
    return min((2 if two_way else 3) * t_m * 100, 30.0)


def beam_rho_min(fc: float, fy: float) -> float:
    """(ญ) 1): 0.25√fc'/fy and 1.4/fy in MPa = 0.80√fc'/fy and 14/fy in ksc."""
    return max(0.80 * math.sqrt(fc), 14.0) / fy


def stirrup_max_spacing(av: float, fyt: float, bw: float, d: float, fc: float) -> float:
    """(ญ) 3): Av ≥ 0.062√fc' bw s/fyt and 0.35 bw s/fyt (MPa) → 0.20√fc' and 3.5 (ksc);
    s ≤ d/2 ≤ 600 mm. cm."""
    s_av = av * fyt / (max(0.20 * math.sqrt(fc), 3.5) * bw)
    return min(s_av, d / 2, 60.0)


def tie_bar(main: str) -> str:
    """(จ) 3) ก): ≥ 6 mm for bars ≤ 12 mm, ≥ 9 mm for 16–20 mm, ≥ 10 mm for 25–28 mm,
    ≥ 12 mm for 32 mm and over."""
    d = BAR_DIA[main] * 10
    if d <= 12:
        return "RB6"
    if d <= 20:
        return "RB9"
    if d <= 28:
        return "DB10"
    return "DB12"


def tie_spacing_max(main: str, tie: str, least_side_cm: float) -> float:
    """(จ) 3) ข): ≤ 16 main-bar diameters, 48 tie diameters, the least side. cm."""
    return min(16 * BAR_DIA[main], 48 * BAR_DIA[tie], least_side_cm)


# ---------------------------------------------------------------------------
# Site
# ---------------------------------------------------------------------------
SOLAR_FREE = 20.0             # kg/m², กฎกระทรวง ฉบับที่ 72


def site_notes(b) -> list[str]:
    from ..standards import SEISMIC_ZONE_TEXT, provinces
    out = []
    if b.province:
        data = provinces()
        p = data["provinces"].get(b.province)
        if p:
            g = data["wind_groups"][p["wind_group"]]
            out.append(f"{b.province}: ความเร็วลมอ้างอิงกลุ่ม {p['wind_group']} (V50 {g['v50']} ม./วินาที, "
                       f"TF {g['tf']:g}) ใช้เมื่อคำนวณด้วยวิธีละเอียด มยผ. 1311" + (f" — {p['note']}" if p.get("note") else ""))
            z = p["seismic_zone"]
            if z:
                text = (f"{b.province} อยู่ใน{SEISMIC_ZONE_TEXT[z]} ตามกฎกระทรวงแผ่นดินไหว พ.ศ. 2564 "
                        "อาคารประเภทที่กฎกระทรวงกำหนดต้องออกแบบรับแรงแผ่นดินไหว")
                if not b.seismic.enabled:
                    text += " — ยังไม่ได้เปิดการคำนวณแผ่นดินไหว"
                out.append(text)
            else:
                out.append(f"{b.province} ไม่อยู่ใน 43 จังหวัดของกฎกระทรวงแผ่นดินไหว พ.ศ. 2564 (ประกาศ มท. 2567 ผนวก ข)")
    if b.roof.solar_load > SOLAR_FREE:
        out.append(f"แผงโซลาร์เซลล์ {b.roof.solar_load:g} กก./ตร.ม. เกิน 20 กก./ตร.ม. ถือเป็นการดัดแปลงอาคาร "
                   "(กฎกระทรวง ฉบับที่ 72) ต้องขออนุญาต")
    elif b.roof.solar_load > 0:
        out.append(f"แผงโซลาร์เซลล์ {b.roof.solar_load:g} กก./ตร.ม. ไม่เกิน 20 กก./ตร.ม. ไม่ถือเป็นการดัดแปลงอาคาร "
                   "(กฎกระทรวง ฉบับที่ 72) และคิดเป็นน้ำหนักคงที่ของหลังคาแล้ว")
    if min(b.column_width, b.column_depth) < COLUMN_MIN_SIDE - 1e-9:
        out.append("เสาด้านแคบน้อยกว่า 200 มม. ใช้ได้เฉพาะเสารับหลังคาของอาคารไม่เกิน 2 ชั้นที่สูงไม่เกิน 3 ม. "
                   "หรือเสาย่อยที่ไม่ต่อเนื่อง (ไม่น้อยกว่า 150 มม.) — ประกาศ มท. 2567 ข้อ 29 (11) (ข)")
    if not b.quality_control:
        out.append("ไม่ระบุการควบคุมคุณภาพ: fc ≤ 65 ksc, fc' ในวิธีกำลัง ≤ 150 ksc, ตัวคูณลดกำลังชุดล่าง "
                   "และระยะหุ้มเพิ่ม 20% (ประกาศ มท. 2567 ข้อ 29, กฎกระทรวง พ.ศ. 2566 ข้อ 8)")
    return out


# ---------------------------------------------------------------------------
# Deflection — ประกาศ มท. 2567 ข้อ 8 ตาราง 1 [MI2567-8]
# ---------------------------------------------------------------------------
DEFL_LIVE, DEFL_TOTAL = 360, 240          # floors and beams: L/360 (live), L/240 (dead + live)
LONG_TERM_XI = 2.0                        # sustained load, 5 years or more (ACI 318 9.5.2.5)


def cracked_inertia(b: float, d: float, As: float, n: float) -> float:
    """Cracked transformed section, tension steel only, cm⁴."""
    if As <= 0:
        return b * d ** 3 / 12
    kd = (-n * As + math.sqrt((n * As) ** 2 + 2 * b * n * As * d)) / b
    return b * kd ** 3 / 3 + n * As * (d - kd) ** 2


def beam_deflection(mat, b_m, h_m, d_cm, As_t, As_c, span_m, m_service, live_share, cantilever=False):
    """``(Δ_live, Δ_total incl. long-term, limit_live, limit_total)`` in cm.

    Ie by Branson with Mcr = fr·Ig/yt, fr = 2.0√fc' ksc; immediate
    deflection from the largest service moment, Δ = 5L²M/48EIe (span; the
    end-moment relief is left out, on the safe side) or ML²/3EIe
    (cantilever); long-term multiplier λ = ξ/(1 + 50ρ') on the dead load
    [EIT1007-DEFL]. A cantilever is checked with L = twice its length."""
    b, h, L = b_m * 100, h_m * 100, span_m * 100
    ec = 15100 * math.sqrt(mat.fc_prime)
    n = max(6.0, 2.04e6 / ec)
    ig = b * h ** 3 / 12
    mcr = 2.0 * math.sqrt(mat.fc_prime) * ig / (h / 2)
    ma = max(m_service * 100, 1.0)
    icr = cracked_inertia(b, d_cm, As_t, n)
    r = min(1.0, (mcr / ma) ** 3)
    ie = min(ig, r * ig + (1 - r) * icr)
    coef = 1 / 3 if cantilever else 5 / 48
    delta = coef * ma * L * L / (ec * ie)
    d_live = delta * live_share
    rho_c = As_c / (b * d_cm) if d_cm > 0 else 0.0
    lam = LONG_TERM_XI / (1 + 50 * rho_c)
    total = delta + lam * delta * (1 - live_share)
    L_check = 2 * L if cantilever else L
    return d_live, total, L_check / DEFL_LIVE, L_check / DEFL_TOTAL
