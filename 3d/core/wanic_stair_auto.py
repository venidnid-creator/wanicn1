# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
"""บันไดอัตโนมัติ: a stair designed for the storey height and placed where
the user chooses (กลาง / ซ้าย / ขวา × หน้า / หลัง of the building).

The design, as the standard house plans of กรมโยธาธิการฯ draw it and never
below กฎกระทรวง ฉบับที่ 55 (2543) ข้อ 22:
- risers of equal height, at most 0.18 m (the law allows 0.20) — n =
  ⌈H / 0.18⌉, R = H / n (3.00 m → 17 × 0.176 m);
- goings 0.25 m (the law asks ≥ 0.22), so 2R + G stays within the
  comfortable 0.60–0.65 m;
- width 1.00 m (the law asks ≥ 0.80 m for a house);
- two flights with a landing half-way (each flight rises ≤ 3.00 m as the
  law asks), the landing as deep as the stair is wide;
- the stair stands against the chosen outside wall, its first step at the
  chosen end, the second flight turning toward the inside of the building.

``design(data, where, w, typ)`` returns the stair dict and a report;
``apply(data, stair)`` puts it on every floor that has one above it."""
from __future__ import annotations

import copy
import math

from core import wanic_building as B

#: the six places offered (key, Thai): across (left/centre/right) × along (front/back)
PLACES = {("left", "front"): "ซ้าย-หน้า", ("center", "front"): "กลาง-หน้า", ("right", "front"): "ขวา-หน้า",
          ("left", "back"): "ซ้าย-หลัง", ("center", "back"): "กลาง-หลัง", ("right", "back"): "ขวา-หลัง"}
RISER_MAX = 0.18                     # recommended (the law: 0.20)
GOING = 0.25                         # recommended (the law: ≥ 0.22)
LAW = {"riser": 0.20, "going": 0.22, "width": 0.80, "flight_rise": 3.00}
AUTO_ID = "sa"                       # the id prefix of an automatic stair


def footprint(data) -> tuple:
    """(x0, y0, x1, y1) of the ground floor's rooms."""
    rooms = (data.get("floors") or [{}])[0].get("rooms") or []
    if not rooms:
        return (0.0, 0.0, 0.0, 0.0)
    return (min(r["x"] for r in rooms), min(r["y"] for r in rooms),
            max(r["x"] + r["w"] for r in rooms), max(r["y"] + r["d"] for r in rooms))


def risers_for(H, g=GOING, two_flights=True) -> int:
    """The number of risers: an even number for two equal flights, each
    riser ≤ 0.20 m (the law), the step 2R + G nearest 0.63 m (the
    comfortable stride) — 3.00 m → 16 × 0.1875 m as the standard plans."""
    lo = max(2, math.ceil(H / 0.19 - 1e-9))          # a margin under the law's 0.20 m
    hi = max(lo, math.ceil(H / 0.15))
    cands = [n for n in range(lo, hi + 1) if not two_flights or n % 2 == 0] or [lo]
    return min(cands, key=lambda n: abs(2 * H / n + g - 0.63))


def settings_for(data, typ="U") -> dict:
    """The settings with the balanced riser and the recommended going."""
    s = dict(B.settings_of(data))
    s["going"] = max(float(s.get("going") or GOING), GOING)
    H = float(s["floor_h"])
    n = risers_for(H, s["going"], typ != "straight")
    s["riser_max"] = H / n + 1e-6                     # stair_geometry: ⌈H / riser_max⌉ = n
    return s


def design(data, where=("center", "front"), w=1.00, typ="U") -> tuple:
    """(stair, report) — ``report`` has the numbers in words and ``ok``
    (whether it fits inside the ground floor and keeps the law)."""
    s = settings_for(data, typ)
    across, along = where
    x0, y0, x1, y1 = footprint(data)
    t = float(s.get("wall_t") or 0.10)
    # สองช่วง / ตัว L: the landing against the outside wall, the first step inside
    # the house (the owner: ชานพักอยู่อีกด้าน — head and foot swapped); a straight
    # flight still starts at the outside wall and climbs inward
    inward = 1 if along == "front" else 3
    up = inward if typ == "straight" else (inward + 2) % 4
    stair = {"id": AUTO_ID + "1", "x": 0.0, "y": 0.0, "dir": up, "w": float(w),
             "type": typ, "turn": "left", "auto": True}
    # the second flight turns toward the middle of the building
    cx = (x0 + x1) / 2
    want = 1.0 if across == "left" else -1.0 if across == "right" else 1.0
    for turn in ("left", "right"):
        stair["turn"] = turn
        lay = B.stair_layout(stair, s)
        if len(lay["flights"]) < 2 or lay["flights"][1]["p0"][0] * want >= lay["flights"][0]["p0"][0] * want:
            break
    lay = B.stair_layout(stair, s)
    xs = [p[0] for p in lay["rect"]]
    ys = [p[1] for p in lay["rect"]]
    W, D = max(xs) - min(xs), max(ys) - min(ys)
    stair["x"] = (x0 + t / 2 + W / 2) if across == "left" else (x1 - t / 2 - W / 2) if across == "right" else cx
    # a clear floor as deep as the stair is wide in front of the first step (and,
    # upstairs, where one steps off): the stair stands back from the outside wall
    clear = float(w)
    far = clear if typ == "straight" else 0.0         # a straight flight arrives at the far end
    if typ == "straight":
        stair["y"] = (y0 + t / 2 + clear + D / 2) if along == "front" else (y1 - t / 2 - clear - D / 2)
    else:                                             # the landing on the wall, the clear floor inside
        stair["y"] = (y0 + t / 2 + D / 2) if along == "front" else (y1 - t / 2 - D / 2)
    lay = B.stair_layout(stair, s)
    n, R_, g = lay["n"], lay["R"], lay["g"]
    flights = [f["n"] for f in lay["flights"]]
    fits = W + t <= (x1 - x0) + 1e-6 and D + t + clear + far <= (y1 - y0) + 1e-6
    rise_ok = all(k * R_ <= LAW["flight_rise"] + 1e-9 for k in flights)
    ok = fits and R_ <= LAW["riser"] + 1e-9 and g >= LAW["going"] - 1e-9 and w >= LAW["width"] - 1e-9 and rise_ok
    lines = [f"ความสูงชั้น {lay['H']:.2f} ม. → ลูกตั้ง {n} ขั้น สูงขั้นละ {R_ * 100:.2f} ซม. (กฎหมาย ≤ 20 ซม.)",
             f"ลูกนอน {g * 100:.0f} ซม. (กฎหมาย ≥ 22 ซม.) · 2R+G = {(2 * R_ + g):.3f} ม. (เดินสบาย 0.60–0.65)",
             f"กว้าง {w:.2f} ม. (กฎหมาย ≥ 0.80) · " + (
                 f"2 ช่วง ช่วงละ {flights[0]} / {flights[1]} ขั้น สูงช่วงละ ≤ {max(flights) * R_:.2f} ม. · "
                 f"ชานพัก {w:.2f} × {W if typ == 'U' else w:.2f} ม." if len(flights) > 1
                 else f"ช่วงเดียว {flights[0]} ขั้น สูง {flights[0] * R_:.2f} ม."),
             f"พื้นที่บันได {W:.2f} × {D:.2f} ม. ({W * D:.1f} ตร.ม.) · วางที่ {PLACES.get(where, '')} ของอาคาร · "
             f"เว้นพื้นหน้าขั้นแรก {clear:.2f} ม. · พื้นชั้นบนเจาะช่องบันไดพร้อมราวกันตก"]
    if not fits:
        lines.append(f"✗ อาคารเล็กเกินไปสำหรับบันไดนี้ (อาคาร {x1 - x0:.2f} × {y1 - y0:.2f} ม.) — ลดความกว้างหรือขยายห้อง")
    elif not rise_ok:
        lines.append("✗ ช่วงบันไดสูงเกิน 3.00 ม. — ใช้บันไดสองช่วงมีชานพัก")
    else:
        lines.append("✓ ผ่านกฎกระทรวง ฉบับที่ 55 (ลูกตั้ง ลูกนอน ความกว้าง ชานพักทุก ≤ 3.00 ม.)")
    return stair, {"ok": ok, "fits": fits, "lines": lines, "n": n, "R": R_, "g": g, "W": W, "D": D,
                   "flights": flights, "settings": s}


FIRE_ID = "sf"                       # the id prefix of the fire-escape stair (4 storeys and up)


def needs_fire_stair(data) -> bool:
    """4 storeys and up: a second stair, the fire escape (กฎกระทรวง 55 ข้อ 27)."""
    floors = data.get("floors") or []
    return sum(1 for f in floors if f.get("rooms")) >= 4 and not any(
        str(x.get("id", "")).startswith(FIRE_ID) for x in (floors[0].get("stairs") or []))


def apply_fire(data, stair) -> int:
    """The fire-escape stair on every floor below the top (an earlier one is replaced)."""
    n = 0
    for k, f in enumerate((data.get("floors") or [])[:-1]):
        keep = [x for x in f.get("stairs") or [] if not str(x.get("id", "")).startswith(FIRE_ID)]
        f["stairs"] = keep + [dict(copy.deepcopy(stair), id=f"{FIRE_ID}{k + 1}", fire=True)]
        n += 1
    return n


def apply(data, stair) -> int:
    """The stair on every floor that has a floor above it (the automatic one
    replaces an earlier automatic one; stairs drawn by hand stay); the
    recommended riser and going go into the settings. Returns the floors."""
    floors = data.get("floors") or []
    s = dict(data.get("settings") or {})
    rs = settings_for(data, stair.get("type", "U"))
    s["riser_max"], s["going"] = round(rs["riser_max"], 6), rs["going"]
    data["settings"] = s
    n = 0
    for k, f in enumerate(floors[:-1]):
        keep = [x for x in f.get("stairs") or [] if not str(x.get("id", "")).startswith(AUTO_ID)]
        f["stairs"] = keep + [dict(copy.deepcopy(stair), id=f"{AUTO_ID}{k + 1}")]
        n += 1
    return n


def apply_one(data, stair, floor: int) -> int:
    """The stair on one floor only (from ``floor`` up to the next) — «สร้าง
    เฉพาะชั้นนี้»; the automatic stair already on that floor is replaced."""
    floors = data.get("floors") or []
    if not (0 <= floor < len(floors) - 1):
        return 0
    s = dict(data.get("settings") or {})
    rs = settings_for(data, stair.get("type", "U"))
    s["riser_max"], s["going"] = round(rs["riser_max"], 6), rs["going"]
    data["settings"] = s
    f = floors[floor]
    keep = [x for x in f.get("stairs") or [] if not str(x.get("id", "")).startswith(AUTO_ID)]
    f["stairs"] = keep + [dict(copy.deepcopy(stair), id=f"{AUTO_ID}{floor + 1}")]
    return 1


def check_place(data, stair, s) -> list:
    """คำแนะนำการวาง: [(ok, text)] for a stair moved or turned by hand — inside
    the building, a clear floor of one stair width in front of the first
    step, the landing against an outside wall, no column inside it."""
    x0, y0, x1, y1 = footprint(data)
    lay = B.stair_layout(stair, s)
    xs = [p[0] for p in lay["rect"]]
    ys = [p[1] for p in lay["rect"]]
    tol = 0.02
    out = []
    inside = min(xs) >= x0 - tol and max(xs) <= x1 + tol and min(ys) >= y0 - tol and max(ys) <= y1 + tol
    out.append((inside, "อยู่ในอาคาร" if inside else "บันไดยื่นออกนอกอาคาร — เลื่อนเข้ามาในผัง"))
    f0 = lay["flights"][0]
    (fx, fy), (dx, dy) = f0["p0"], f0["d"]
    w = lay["w"]
    cx, cy = fx - dx * w, fy - dy * w                     # one width in front of the first step
    clear = x0 - tol <= cx <= x1 + tol and y0 - tol <= cy <= y1 + tol
    out.append((clear, f"มีพื้นว่างหน้าขั้นแรก {w:.2f} ม." if clear
                else f"หน้าขั้นแรกต้องมีพื้นว่างอย่างน้อย {w:.2f} ม. — เลื่อน หรือ «กลับหัว-ท้าย»"))
    if lay["landings"]:
        lx = [p[0] for ld in lay["landings"] for p in ld["pts"]]
        ly = [p[1] for ld in lay["landings"] for p in ld["pts"]]
        on_wall = (min(lx) <= x0 + 0.3 or max(lx) >= x1 - 0.3 or min(ly) <= y0 + 0.3 or max(ly) >= y1 - 0.3)
        out.append((on_wall, "ชานพักชิดผนังนอก (มาตรฐาน — มีหน้าต่างให้แสง)" if on_wall
                    else "แนะนำ: ให้ชานพักชิดผนังด้านนอกอาคาร"))
    cols = [(c["x"], c["y"]) for c in B.elements(data)["columns"] if c.get("floor", 0) == 0]
    hit = [c for c in cols if min(xs) + 0.05 < c[0] < max(xs) - 0.05 and min(ys) + 0.05 < c[1] < max(ys) - 0.05]
    out.append((not hit, "ไม่มีเสาในช่องบันได" if not hit else f"มีเสา {len(hit)} ต้นอยู่ในช่องบันได — เลื่อนบันไดหลบเสา"))
    return out


def needs_stairs(data) -> bool:
    """Two storeys or more and no stair on the ground floor yet."""
    floors = data.get("floors") or []
    built = [f for f in floors if f.get("rooms")]
    return len(built) >= 2 and not (floors[0].get("stairs") if floors else None)


def law_check(n, R_, g, w) -> bool:
    return R_ <= LAW["riser"] + 1e-9 and g >= LAW["going"] - 1e-9 and w >= LAW["width"] - 1e-9 and n >= 2


assert math is not None
