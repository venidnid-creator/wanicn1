# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
"""The building services a house of these rooms needs, laid out by rule
of thumb from the standards, for หมวด 1, 11–15 of the BOQ and the 3D:

* ไฟฟ้า (วสท. 2001 มาตรฐานการติดตั้งทางไฟฟ้าสำหรับประเทศไทย): ดวงโคม 1 ชุด
  ต่อพื้นที่ไม่เกิน 9 ตร.ม. (ห้องน้ำ/ทางเดิน 1 ชุด), เต้ารับตามชนิดห้อง,
  สวิตช์ตามประตู, วงจรย่อยแสงสว่างไม่เกิน 10 จุด เต้ารับไม่เกิน 8 จุดต่อวงจร
  (เบรกเกอร์ 16/20 A), เครื่องปรับอากาศและเครื่องทำน้ำอุ่นแยกวงจร, สายดิน
* ปรับอากาศ: ห้องนอน 800 BTU/ตร.ม. ห้องนั่งเล่น/รับแขก 900 BTU/ตร.ม. ปัดขึ้น
  เป็นขนาดมาตรฐาน; คอยล์เย็นสูงจากพื้นไม่น้อยกว่า 2.00 ม. ห่างฝ้าไม่น้อยกว่า
  15 ซม.; คอยล์ร้อนห่างผนัง 30 ซม. บนแท่น ค.ส.ล.; ท่อน้ำยา 4 ม. ต่อชุด
* สุขาภิบาล (มยผ. 1201 / กฎกระทรวงสุขลักษณะอาคาร): ท่อประปา PVC ½" ต่อ
  สุขภัณฑ์, ท่อน้ำทิ้ง 2" ท่อโสโครก 4", ท่ออากาศ, ฟลอร์เดรนทุกห้องน้ำ,
  มาตรวัดน้ำ, ถังบำบัดน้ำเสียสำเร็จรูปตามจำนวนผู้อยู่อาศัย (ห้องนอนละ 2 คน),
  บ่อดักไขมันห้องครัว
* ภายนอก: ท่อระบายน้ำรอบอาคารพร้อมบ่อพักทุก 6 ม. ทางเท้า ค.ส.ล. รอบอาคาร
* เตรียมพื้นที่ / อื่นๆ: ปรับพื้นที่ วางผังอาคาร ป้ายโครงการ ทำความสะอาด

Prices are the province's (the BOQ price list) — names here are the keys
the user fills; labour is ว480 where the list has it.
"""
from __future__ import annotations

import math

AC_SIZES = (9000, 12000, 15000, 18000, 24000, 30000, 36000)
AC_BTU_M2 = {"bed": 800, "living": 900}
LIGHT_M2 = 9.0
#: ชนิดห้อง → (ดวงโคมขั้นต่ำ, เต้ารับ, พัดลมระบายอากาศ, ทีวี, แอร์)
ROOM_KINDS = {
    "bed": (1, 3, 0, 1, True),
    "living": (2, 4, 0, 1, True),
    "kitchen": (1, 4, 1, 0, False),
    "wet": (1, 1, 1, 0, False),
    "work": (1, 4, 0, 0, False),
    "pass": (1, 1, 0, 0, False),
    "other": (1, 2, 0, 0, False),
}
WORDS = (("wet", ("ห้องน้ำ", "ส้วม", "สุขา", "อาบน้ำ", "wc", "toilet", "bath")),
         ("bed", ("ห้องนอน", "นอน", "bed")),
         ("living", ("นั่งเล่น", "รับแขก", "โถง", "living", "ห้องรวม", "พักผ่อน")),
         ("kitchen", ("ครัว", "kitchen", "ซักล้าง")),
         ("work", ("ทำงาน", "สำนักงาน", "office", "ประชุม")),
         ("pass", ("ทางเดิน", "ระเบียง", "ชาน", "บันได", "ที่จอดรถ")))


def room_kind(room) -> str:
    name = str((room or {}).get("name") or "").lower()
    for kind, words in WORDS:
        if any(w in name for w in words):
            return kind
    return "other"


def ac_size(area: float, kind: str) -> int:
    need = area * AC_BTU_M2.get(kind, 800)
    for b in AC_SIZES:
        if b >= need:
            return b
    return AC_SIZES[-1]


def plan(data, E=None) -> list:
    """One dict per room: what services it gets and where the AC goes."""
    from core import wanic_building as B
    E = E or B.elements(data)
    s = E["settings"]
    out = []
    for e in E["slabs"]:
        rm, k = e["room"], e["floor"]
        kind = room_kind(rm)
        w, d = float(rm["w"]), float(rm["d"])
        area = w * d
        lmin, outl, fan, tv, ac = ROOM_KINDS[kind]
        lights = 1 if kind in ("wet", "pass") and area <= 12 else \
            max(lmin, int(math.ceil(area / LIGHT_M2 - 1e-9)))
        outlets = outl + (int((area - 12) // 10) if area > 12 and kind != "wet" else 0)
        doors = sum(1 for op in E["openings"] if op["floor"] == k and
                    op["type"] != "window" and
                    B._on_edge(rm, float(op["op"]["x"]), float(op["op"]["y"]), tol=0.06))
        rec = {"room": rm, "floor": k, "kind": kind, "area": area,
               "lights": lights, "outlets": outlets, "switches": max(doors, 1),
               "fan": fan, "tv": tv, "ac": 0, "heater": kind == "wet",
               "ac_wall": None}
        if ac and s.get("mep", True):
            rec["ac"] = ac_size(area, kind)
            rec["ac_wall"] = _ac_wall(E, rm, k)
        out.append(rec)
    return out


def _ac_wall(E, rm, k):
    """The exterior wall of the room the AC hangs on: its longest, and on
    it the stretch without an opening; ``(p0, p1, out)`` or ``None``."""
    best = None
    for wl in E["walls"]:
        if wl["floor"] != k or not wl.get("exterior"):
            continue
        from core import wanic_building as B
        mx, my = (wl["p0"][0] + wl["p1"][0]) / 2, (wl["p0"][1] + wl["p1"][1]) / 2
        if not B._on_edge(rm, mx, my):
            continue
        score = wl["L"] - 0.5 * len(wl["openings"])
        if best is None or score > best[0]:
            best = (score, wl)
    return best[1] if best else None


def members(data, E=None):
    """3D: the AC sets (indoor unit on the wall under the ceiling, outdoor
    unit on its pad outside) and the ceiling lights."""
    from core import wanic_building as B
    E = E or B.elements(data)
    s = E["settings"]
    if not s.get("mep", True):
        return []
    out = []
    lib = E["lib"]
    half = float(lib["C1"]["b"]) / 2
    for rec in plan(data, E):
        rm, k = rec["room"], rec["floor"]
        rname = rm.get("name") or "ห้อง"
        zc = B.ceiling_z(E, k) - 0.009
        x0, y0, x1, y1 = B.room_inner(E, rm, k)
        # lights: a grid of downlights / panels on the ceiling
        n = rec["lights"]
        cols = max(1, int(round(math.sqrt(n * (x1 - x0) / max(y1 - y0, 0.1)))))
        rows = max(1, int(math.ceil(n / cols)))
        bx = B._Boxes((0.0, 0.0), (1.0, 0.0), 0.0)
        lamp = {"color": (1.0, 0.97, 0.80)}
        placed = 0
        for j in range(rows):
            for i in range(cols):
                if placed >= n:
                    break
                cx = x0 + (x1 - x0) * (i + 0.5) / cols
                cy = y0 + (y1 - y0) * (j + 0.5) / rows
                bx.box(cx - 0.09, cx + 0.09, cy - 0.09, cy + 0.09, zc - 0.02, zc, lamp)
                placed += 1
        g = bx.group(f"ดวงโคม LED {n} ชุด · {rname} · ชั้น {k + 1}", "structure",
                     "light", "ดวงโคม", "IfcLightFixture")
        if g is not None:
            g.ext[B.EXT_KEY]["info"] = [["ชนิด", "ดวงโคมดาวน์ไลท์ LED 1×18 W"],
                                        ["จำนวน", f"{n} ชุด (1 ชุด/≤ 9 ตร.ม.)"],
                                        ["เต้ารับ", f"{rec['outlets']} ชุด"],
                                        ["สวิตช์", f"{rec['switches']} ชุด"],
                                        ["รายการ BOQ", "หมวด 12 งานไฟฟ้า · ว480 4.58"]]
            out.append((g, "light"))
        wl = rec["ac_wall"]
        if not rec["ac"] or wl is None:
            continue
        p0, p1, L = wl["p0"], wl["p1"], wl["L"]
        ux, uy = (p1[0] - p0[0]) / L, (p1[1] - p0[1]) / L
        ox, oy = wl["out"]
        # the inner face of the wall: the room side of the grid line
        sp = B.wall_spec(s, True)
        off = B.wall_offset(E, wl)
        inner = off - sp["t"] / 2 - sp["pi"]
        mid = L / 2
        # keep clear of openings on that wall
        ops = sorted(sd for sd, _op in B._openings_on(p0, p1, wl["openings"]))
        if ops:
            gaps = [half] + ops + [L - half]
            seg = max(zip(gaps, gaps[1:]), key=lambda ab: ab[1] - ab[0])
            mid = (seg[0] + seg[1]) / 2
        u = (ux, uy)
        # wall-local: d measured towards the room = −out
        sgn = 1.0 if (-uy * -ox + ux * -oy) > 0 else -1.0
        top = zc - 0.15                                  # 15 cm under the ceiling
        bx = B._Boxes(p0, u, 0.0)
        white = {"color": (0.97, 0.97, 0.97)}
        # distance from the grid line to the room-side face, towards the room
        face = -inner
        a0, a1 = sorted((sgn * face, sgn * (face + 0.22)))
        bx.box(mid - 0.42, mid + 0.42, a0, a1, top - 0.29, top, white)
        g = bx.group(f"เครื่องปรับอากาศ {rec['ac']:,} BTU (คอยล์เย็น) · {rname}",
                     "structure", "ac", "เครื่องปรับอากาศ", "IfcUnitaryEquipment")
        if g is not None:
            g.ext[B.EXT_KEY]["info"] = [
                ["ชนิด", f"เครื่องปรับอากาศแยกส่วน ติดผนัง {rec['ac']:,} BTU/ชม."],
                ["ห้อง", f"{rname} {rec['area']:.1f} ตร.ม. × "
                         f"{AC_BTU_M2[rec['kind']]} BTU/ตร.ม."],
                ["ติดตั้ง", f"ใต้ฝ้า 15 ซม. สูงจากพื้น {top - 0.29 - k * E['H']:.2f} ม."],
                ["รายการ BOQ", "หมวด 13 งานปรับอากาศ · ว480 5.1 5.4 5.5 5.6"]]
            out.append((g, "ac"))
        # outdoor unit on its pad, 30 cm off the outside face, at the floor
        z0 = k * E["H"] if k > 0 else 0.08          # on the walkway
        outer = off + sp["t"] / 2 + sp["po"]
        b0, b1 = sorted((-sgn * (outer + 0.30), -sgn * (outer + 0.30 + 0.30)))
        bo = B._Boxes(p0, u, 0.0)
        bo.box(mid - 0.45, mid + 0.45, b0, b1, z0, z0 + 0.10,
               {"color": (0.80, 0.80, 0.78)})
        bo.box(mid - 0.40, mid + 0.40, b0, b1, z0 + 0.10, z0 + 0.10 + 0.55,
               {"color": (0.93, 0.93, 0.92)})
        g = bo.group(f"เครื่องปรับอากาศ {rec['ac']:,} BTU (คอยล์ร้อน) · {rname}",
                     "structure", "ac_out", "คอยล์ร้อน", "IfcUnitaryEquipment")
        if g is not None:
            g.ext[B.EXT_KEY]["info"] = [["ชนิด", "คอยล์ร้อนบนแท่น ค.ส.ล."],
                                        ["ระยะ", "ห่างผนัง 30 ซม."]]
            out.append((g, "ac_out"))
    out += install_members(data, E, plan(data, E))
    return out


# ---------------------------------------------------------------------------
# Where the services go, in 3D (positions by the usual installation heights)
# ---------------------------------------------------------------------------

#: ความสูงติดตั้งจากพื้น (ม.): สวิตช์ 1.20, เต้ารับ 0.30 (ห้องน้ำ/ครัว 1.20),
#: ตู้ไฟ 1.50 (ขอบล่าง), เครื่องทำน้ำอุ่น 1.50
H_SWITCH, H_OUTLET, H_OUTLET_WET, H_PANEL, H_HEATER = 1.20, 0.30, 1.20, 1.50, 1.50
COL = {"device": (0.97, 0.97, 0.95), "panel": (0.85, 0.86, 0.88),
       "supply": (0.25, 0.45, 0.85), "drain": (0.55, 0.55, 0.55),
       "soil": (0.42, 0.42, 0.40), "tank": (0.35, 0.55, 0.40),
       "concrete": (0.78, 0.77, 0.74), "meter": (0.20, 0.30, 0.55),
       "copper": (0.80, 0.50, 0.25), "rod": (0.70, 0.45, 0.20),
       "sign": (0.95, 0.95, 0.90), "post": (0.40, 0.40, 0.42)}


def _edges(x0, y0, x1, y1):
    """The four inner wall faces of a room: (start, direction, length,
    into-the-room normal)."""
    return [((x0, y0), (1.0, 0.0), x1 - x0, (0.0, 1.0)),
            ((x1, y1), (-1.0, 0.0), x1 - x0, (0.0, -1.0)),
            ((x0, y1), (0.0, -1.0), y1 - y0, (1.0, 0.0)),
            ((x1, y0), (0.0, 1.0), y1 - y0, (-1.0, 0.0))]


def _box(B, name, kind, boxes, info=None, ifc="IfcFlowTerminal"):
    """One group of axis-aligned boxes [(x0, y0, z0, x1, y1, z1, colour)]."""
    bx = B._Boxes((0.0, 0.0), (1.0, 0.0), 0.0)
    for x0, y0, z0, x1, y1, z1, c in boxes:
        bx.box(min(x0, x1), max(x0, x1), min(y0, y1), max(y0, y1),
               min(z0, z1), max(z0, z1), {"color": COL.get(c, c) if isinstance(c, str) else c})
    g = bx.group(name, "structure", kind, name, ifc)
    if g is not None and info:
        g.ext[B.EXT_KEY]["info"] = [[str(k), str(v)] for k, v in info]
    return g


def _run(a, b, z0, z1, r, c):
    """A straight pipe/conduit from plan point a to b (axis-aligned legs)
    at heights z0→z1, as boxes of half-size r."""
    out = []
    (ax, ay), (bx_, by) = a, b
    if abs(ax - bx_) > 1e-6:
        out.append((ax, ay - r, z0 - r, bx_, ay + r, z0 + r, c))
    if abs(ay - by) > 1e-6:
        out.append((bx_ - r, ay, z0 - r, bx_ + r, by, z0 + r, c))
    if abs(z1 - z0) > 1e-6:
        out.append((bx_ - r, by - r, z0, bx_ + r, by + r, z1, c))
    return out


def install_members(data, E, rooms):
    """Switches, outlets, the consumer unit, water heaters, exhaust fans,
    supply and drain pipes, floor drains, the septic tank and grease trap,
    the water meter, the drain ring with its manholes, the walkway, the
    earth rod and the project sign — each where it is installed."""
    from core import wanic_building as B
    s, H = E["settings"], E["H"]
    out = []
    top = E["floors"][0]["rooms"]
    xs = [float(r["x"]) for r in top] + [float(r["x"]) + float(r["w"]) for r in top]
    ys = [float(r["y"]) for r in top] + [float(r["y"]) + float(r["d"]) for r in top]
    X0, Y0, X1, Y1 = min(xs), min(ys), max(xs), max(ys)
    drop = max(float(s.get("wet_drop") or 0.0), 0.0)
    panel_done = False
    main_supply = []          # points (x, y) where a room's supply leaves the slab
    soil_points = []
    for rec in rooms:
        rm, k = rec["room"], rec["floor"]
        x0, y0, x1, y1 = B.room_inner(E, rm, k)
        z = k * H - (drop if rec["kind"] == "wet" else 0.0)
        rname = rm.get("name") or "ห้อง"
        devs = []
        # switches beside the doors, on the latch side, 15 cm off the frame
        doors = [op for op in E["openings"] if op["floor"] == k and op["type"] != "window"
                 and B._on_edge(rm, float(op["op"]["x"]), float(op["op"]["y"]), tol=0.06)]
        ops_here = [op for op in E["openings"] if op["floor"] == k and
                    B._on_edge(rm, float(op["op"]["x"]), float(op["op"]["y"]), tol=0.06)]
        for op in doors[:max(rec["switches"], 1)]:
            ox, oy = float(op["op"]["x"]), float(op["op"]["y"])
            w = op["w"]
            if abs(oy - float(rm["y"])) < 0.07 or abs(oy - float(rm["y"]) - float(rm["d"])) < 0.07:
                sx = min(max(ox + w / 2 + 0.15, x0 + 0.1), x1 - 0.1)
                sy = y0 if abs(oy - float(rm["y"])) < 0.07 else y1
                ny = 1 if sy == y0 else -1
                devs.append((sx - 0.035, sy, z + H_SWITCH - 0.06, sx + 0.035,
                             sy + ny * 0.012, z + H_SWITCH + 0.06, "device"))
            else:
                sy = min(max(oy + w / 2 + 0.15, y0 + 0.1), y1 - 0.1)
                sx = x0 if abs(ox - float(rm["x"])) < 0.07 else x1
                nx = 1 if sx == x0 else -1
                devs.append((sx, sy - 0.035, z + H_SWITCH - 0.06, sx + nx * 0.012,
                             sy + 0.035, z + H_SWITCH + 0.06, "device"))
        # outlets spread over the walls, clear of the openings
        hz = H_OUTLET_WET if rec["kind"] in ("wet", "kitchen") else H_OUTLET
        cand = []
        for (sx, sy), (ux, uy), L, (nx, ny) in _edges(x0, y0, x1, y1):
            for f in (0.25, 0.75, 0.5):
                px, py = sx + ux * L * f, sy + uy * L * f
                if any(math.hypot(px - float(op["op"]["x"]), py - float(op["op"]["y"]))
                       < op["w"] / 2 + 0.25 for op in ops_here):
                    continue
                cand.append((px, py, nx, ny))
        for px, py, nx, ny in cand[:rec["outlets"]]:
            devs.append((px - 0.06 * abs(ny), py - 0.06 * abs(nx), z + hz - 0.04,
                         px + 0.06 * abs(ny) + nx * 0.012, py + 0.06 * abs(nx) + ny * 0.012,
                         z + hz + 0.04, "device"))
        g = _box(B, f"สวิตช์ {rec['switches']} · เต้ารับ {rec['outlets']} ชุด · {rname}",
                 "outlet", devs, [("สวิตช์", f"{rec['switches']} ชุด สูง {H_SWITCH:.2f} ม."),
                                  ("เต้ารับคู่มีกราวด์", f"{rec['outlets']} ชุด สูง {hz:.2f} ม."),
                                  ("มาตรฐาน", "วสท. 2001"), ("รายการ BOQ", "หมวด 12 งานไฟฟ้า")],
                 "IfcOutlet")
        if g is not None:
            out.append((g, "outlet"))
        # the consumer unit by the first door of the first living/bed room
        if not panel_done and doors and rec["kind"] in ("living", "bed", "other", "pass"):
            op = doors[0]
            px = min(max(float(op["op"]["x"]) - op["w"] / 2 - 0.45, x0 + 0.25), x1 - 0.25)
            g = _box(B, "ตู้ควบคุมไฟฟ้า (Consumer Unit)", "panel",
                     [(px - 0.20, y0, z + H_PANEL, px + 0.20, y0 + 0.11, z + H_PANEL + 0.40, "panel")],
                     [("ชนิด", "ตู้คอนซูมเมอร์ยูนิต พร้อมเมนเบรกเกอร์และกันดูด"),
                      ("ติดตั้ง", f"ขอบล่างสูง {H_PANEL:.2f} ม."), ("รายการ BOQ", "หมวด 12")],
                     "IfcElectricDistributionBoard")
            if g is not None:
                out.append((g, "panel"))
                rod = (px, Y0 - 0.80)
                g = _box(B, "หลักดิน 5/8\" × 2.40 ม.", "ground_rod",
                         [(rod[0] - 0.008, rod[1] - 0.008, -2.40, rod[0] + 0.008,
                           rod[1] + 0.008, 0.05, "rod")],
                         [("ชนิด", "หลักดินทองแดง 5/8\" ยาว 2.40 ม."), ("รายการ BOQ", "หมวด 12")],
                         "IfcElectricDistributionBoard")
                if g is not None:
                    out.append((g, "ground_rod"))
                panel_done = True
        # wet rooms: water heater, exhaust fan, floor drain
        if rec["kind"] in ("wet", "kitchen"):
            boxes = []
            cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
            zc = B.ceiling_z(E, k) - 0.009
            boxes.append((cx - 0.13, cy - 0.13, zc - 0.03, cx + 0.13, cy + 0.13, zc, "device"))
            if rec["kind"] == "wet":
                boxes.append((x1 - 0.30, y1 - 0.10, z + H_HEATER, x1 - 0.05, y1,
                              z + H_HEATER + 0.35, "device"))
                fd = (cx, cy)
                boxes.append((fd[0] - 0.06, fd[1] - 0.06, z - 0.005, fd[0] + 0.06,
                              fd[1] + 0.06, z + 0.002, "drain"))
            g = _box(B, f"พัดลมระบายอากาศ{' เครื่องทำน้ำอุ่น ฟลอร์เดรน' if rec['kind'] == 'wet' else ''}"
                        f" · {rname}", "fan", boxes,
                     [("พัดลมระบายอากาศ", "8 นิ้ว ติดฝ้า"),
                      ("เครื่องทำน้ำอุ่น", f"สูง {H_HEATER:.2f} ม. วงจรเฉพาะ" if rec["kind"] == "wet" else "-"),
                      ("ฟลอร์เดรน", "Ø 2\" กันกลิ่น" if rec["kind"] == "wet" else "-"),
                      ("รายการ BOQ", "หมวด 11 / 12 / 13")])
            if g is not None:
                out.append((g, "fan"))
            main_supply.append(((x0 + x1) / 2, y0 if abs(y0 - Y0) < abs(y1 - Y1) else y1, k))
            if rec["kind"] == "wet":
                soil_points.append(((x0 + x1) / 2, (y0 + y1) / 2))
    # fixtures: a riser from each up the wall, the supply under the slab
    pipes, drains = [], []
    for e in E["fixtures"]:
        fx = e["fx"]
        x, y = float(fx["x"]), float(fx["y"])
        z = e["floor"] * H
        pipes += _run((x, y), (x, y), -0.30, z + 0.55, 0.0125, "supply")
        drains += _run((x, y), (x, y), -0.45, z, 0.03, "drain")
        main_supply.append((x, y, e["floor"]))
    # the supply main: from the water meter along the front, then to each point
    meter = (X0 - 1.0, Y0 - 1.5)
    for (x, y, _k) in main_supply:
        pipes += _run((meter[0], meter[1]), (x, meter[1]), -0.30, -0.30, 0.0125, "supply")
        pipes += _run((x, meter[1]), (x, y), -0.30, -0.30, 0.0125, "supply")
    if pipes:
        g = _box(B, "ท่อประปา PVC Ø ½\" (ใต้พื้นและท่อขึ้น)", "pipe_supply", pipes,
                 [("ชนิด", "ท่อ PVC ชั้น 13.5 Ø ½\" ฝังใต้ดิน 0.30 ม."), ("รายการ BOQ", "หมวด 11")],
                 "IfcPipeSegment")
        if g is not None:
            out.append((g, "pipe_supply"))
        g = _box(B, "มาตรวัดน้ำ Ø ½\" พร้อมบ่อ", "meter",
                 [(meter[0] - 0.20, meter[1] - 0.15, -0.30, meter[0] + 0.20, meter[1] + 0.15,
                   0.05, "concrete"),
                  (meter[0] - 0.08, meter[1] - 0.05, 0.05, meter[0] + 0.08, meter[1] + 0.05,
                   0.15, "meter")],
                 [("ชนิด", "มาตรวัดน้ำ ½\" พร้อมประตูน้ำ"), ("รายการ BOQ", "หมวด 11")],
                 "IfcFlowMeter")
        if g is not None:
            out.append((g, "meter"))
    # septic tank by the first bathroom, 2 m out from the nearest outside wall
    tank = None
    if soil_points:
        sx, sy = soil_points[0]
        dists = [(sx - X0, (X0 - 2.0, sy)), (X1 - sx, (X1 + 2.0, sy)),
                 (sy - Y0, (sx, Y0 - 2.0)), (Y1 - sy, (sx, Y1 + 2.0))]
        tank = min(dists)[1]
        r = 0.55
        g = _box(B, "ถังบำบัดน้ำเสียสำเร็จรูป", "septic",
                 [(tank[0] - r, tank[1] - r, -1.60, tank[0] + r, tank[1] + r, 0.05, "tank"),
                  (tank[0] - 0.25, tank[1] - 0.25, 0.05, tank[0] + 0.25, tank[1] + 0.25, 0.10,
                   "concrete")],
                 [("ชนิด", "ถังบำบัดน้ำเสียสำเร็จรูปไร้อากาศ"), ("ฝัง", "ใต้ดิน ห่างอาคาร 2.00 ม."),
                  ("รายการ BOQ", "หมวด 11")], "IfcTank")
        if g is not None:
            out.append((g, "septic"))
        for (px, py) in soil_points:
            drains += _run((px, py), (tank[0], py), -0.45, -0.45, 0.05, "soil")
            drains += _run((tank[0], py), tank, -0.45, -0.45, 0.05, "soil")
    if drains:
        g = _box(B, "ท่อน้ำทิ้ง/ท่อโสโครก PVC Ø 2\"–4\" (ใต้พื้น)", "pipe_drain", drains,
                 [("ชนิด", "ท่อน้ำทิ้ง PVC Ø 2\" ท่อโสโครก Ø 4\" ลาด 1:100"),
                  ("รายการ BOQ", "หมวด 11")], "IfcPipeSegment")
        if g is not None:
            out.append((g, "pipe_drain"))
    # grease trap outside each kitchen
    for rec in rooms:
        if rec["kind"] != "kitchen":
            continue
        rm = rec["room"]
        cx = float(rm["x"]) + float(rm["w"]) / 2
        gy = Y1 + 1.0 if float(rm["y"]) + float(rm["d"]) >= Y1 - 1e-6 else Y0 - 1.0
        g = _box(B, "บ่อดักไขมันสำเร็จรูป", "grease",
                 [(cx - 0.25, gy - 0.25, -0.60, cx + 0.25, gy + 0.25, 0.05, "tank")],
                 [("ชนิด", "บ่อดักไขมันสำเร็จรูป"), ("รายการ BOQ", "หมวด 11")], "IfcInterceptor")
        if g is not None:
            out.append((g, "grease"))
    # outside: walkway, the drain ring with manholes, the project sign
    w = 0.60
    walk = [(X0 - w, Y0 - w, -0.02, X1 + w, Y0, 0.08, "concrete"),
            (X0 - w, Y1, -0.02, X1 + w, Y1 + w, 0.08, "concrete"),
            (X0 - w, Y0, -0.02, X0, Y1, 0.08, "concrete"),
            (X1, Y0, -0.02, X1 + w, Y1, 0.08, "concrete")]
    g = _box(B, "ทางเท้ารอบอาคาร ค.ส.ล. กว้าง 0.60 ม. หนา 0.10 ม.", "walkway", walk,
             [("ชนิด", "ทางเท้า ค.ส.ล."), ("รายการ BOQ", "หมวด 14 งานภายนอก")], "IfcSlab")
    if g is not None:
        out.append((g, "walkway"))
    ring, holes = [], []
    rx0, ry0, rx1, ry1 = X0 - 1.0, Y0 - 1.0, X1 + 1.0, Y1 + 1.0
    r = 0.15
    ring += [(rx0, ry0 - r, -0.55, rx1, ry0 + r, -0.25, "concrete"),
             (rx0, ry1 - r, -0.55, rx1, ry1 + r, -0.25, "concrete"),
             (rx0 - r, ry0, -0.55, rx0 + r, ry1, -0.25, "concrete"),
             (rx1 - r, ry0, -0.55, rx1 + r, ry1, -0.25, "concrete")]
    per = 2 * ((rx1 - rx0) + (ry1 - ry0))
    n = max(4, math.ceil(per / 6.0))
    for i in range(n):
        t = per * i / n
        for (ax, ay), (bx_, by), L in (((rx0, ry0), (rx1, ry0), rx1 - rx0),
                                       ((rx1, ry0), (rx1, ry1), ry1 - ry0),
                                       ((rx1, ry1), (rx0, ry1), rx1 - rx0),
                                       ((rx0, ry1), (rx0, ry0), ry1 - ry0)):
            if t <= L + 1e-9:
                f = t / L if L else 0
                hx, hy = ax + (bx_ - ax) * f, ay + (by - ay) * f
                holes.append((hx - 0.30, hy - 0.30, -0.70, hx + 0.30, hy + 0.30, 0.03, "concrete"))
                break
            t -= L
    g = _box(B, f"ท่อระบายน้ำ ค.ส.ล. Ø 0.30 ม. รอบอาคาร + บ่อพัก {len(holes)} บ่อ", "drain_ring",
             ring + holes, [("ชนิด", "ท่อ คสล. Ø 0.30 ม. ห่างอาคาร 1.00 ม."),
                            ("บ่อพัก", f"{len(holes)} บ่อ ทุกระยะไม่เกิน 6 ม."),
                            ("รายการ BOQ", "หมวด 14 งานภายนอก")], "IfcPipeSegment")
    if g is not None:
        out.append((g, "drain_ring"))
    sx, sy = X0 + 1.0, Y0 - 4.0
    g = _box(B, "ป้ายประชาสัมพันธ์โครงการ 1.20×2.40 ม.", "sign",
             [(sx - 0.05, sy - 0.05, 0.0, sx + 0.05, sy + 0.05, 2.80, "post"),
              (sx + 2.35, sy - 0.05, 0.0, sx + 2.45, sy + 0.05, 2.80, "post"),
              (sx - 0.05, sy + 0.05, 1.60, sx + 2.45, sy + 0.08, 2.80, "sign")],
             [("ชนิด", "ป้ายโครงการ"), ("รายการ BOQ", "หมวด 15 งานอื่นๆ")], "IfcSign")
    if g is not None:
        out.append((g, "sign"))
    return out


def bill(data, E, add, labour) -> None:
    """Add หมวด 1, 11–15 lines to the BOQ through ``add(group, desc, qty,
    unit, mat_key=…, lab=…/lab_code=…, basis=…, ref=…, note=…)``."""
    from core import wanic_building as B
    s = E["settings"]
    if not s.get("mep", True) or not E["n"]:
        return
    rooms = plan(data, E)
    top = E["floors"][0]["rooms"]
    xs = [float(r["x"]) for r in top] + [float(r["x"]) + float(r["w"]) for r in top]
    ys = [float(r["y"]) for r in top] + [float(r["y"]) + float(r["d"]) for r in top]
    W, D = max(xs) - min(xs), max(ys) - min(ys)
    footprint = sum(float(r["w"]) * float(r["d"]) for r in top)
    perim = sum(math.dist(a, b) for a, b in B.outline_segments(top))
    unlisted = "ค่าแรงไม่มีในบัญชี ว480 — ราคาพร้อมติดตั้ง (หรือร้อยละ 30–37 ของค่าวัสดุ)"
    W480 = "ว480"

    def lab(code, spec="", note=""):
        from core import wanic_w480 as WL
        return WL.rate(code, spec, note)

    # --- 1 งานเตรียมพื้นที่ ------------------------------------------------
    g = "prep"
    site = (W + 4.0) * (D + 4.0)
    add(g, "ถางป่า ขุดตอ ปรับพื้นที่ก่อสร้าง", site, "ตร.ม.",
        mat_key="ค่าปรับพื้นที่ก่อสร้าง (เหมา/ตร.ม.)",
        basis=f"({W:.2f} + 4) × ({D:.2f} + 4) ม. (อาคาร + รอบละ 2 ม.)",
        ref="งานเตรียมพื้นที่", note=unlisted)
    add(g, "วางผังอาคาร ทำผังบริเวณ (Batter Board)", 1, "งาน",
        mat_key="ค่าวางผังอาคาร (เหมา)", basis="1 งาน ต่ออาคาร", ref="งานเตรียมพื้นที่",
        note=unlisted)

    # --- 11 สุขาภิบาล -------------------------------------------------------
    g = "plumbing"
    fx = [e for e in E["fixtures"]]
    wcs = sum(1 for e in fx if str(e["fx"].get("type", "")).startswith("WC"))
    n_fx = len(fx)
    wets = [r for r in rooms if r["kind"] == "wet"]
    kitchens = [r for r in rooms if r["kind"] == "kitchen"]
    points = n_fx + len(kitchens) + 2                    # + ก๊อกสนาม 2 จุด
    if points:
        supply = points * 3.0 + perim / 2 + 10.0
        add(g, "ท่อประปา PVC ชั้น 13.5 ขนาด Ø ½\" พร้อมข้อต่อ", supply, "ม.",
            mat_key="ท่อ PVC ประปา ½\" ชั้น 13.5 (รวมข้อต่อ)", lab=lab("3.8", "1/2"),
            basis=f"{points} จุด × 3 ม. + ท่อเมนรอบอาคาร {perim / 2:.1f} ม. + จากมาตรวัด 10 ม.",
            ref=f"มยผ. 1201 · {W480} 3.8")
        add(g, "ประตูน้ำ/สต๊อปวาล์ว Ø ½\"", points, "ชุด", mat_key="สต๊อปวาล์ว ½\"",
            lab=lab("3.11", "STOP VALVE"), basis="1 ชุดต่อจุดใช้น้ำ", ref=f"{W480} 3.11")
        add(g, "ก๊อกสนาม Ø ½\"", 2, "ชุด", mat_key="ก๊อกสนาม ½\"",
            lab=lab("3.11", "ก็อกสนาม"), basis="รอบอาคาร 2 จุด", ref=f"{W480} 3.11")
        add(g, "มาตรวัดน้ำ Ø ½\" พร้อมประตูน้ำ", 1, "ชุด", mat_key="มาตรวัดน้ำ ½\"",
            lab=lab("3.12", "Dia 1/2"), basis="1 ชุดต่ออาคาร", ref=f"{W480} 3.12")
    drains = n_fx - wcs + len(kitchens)
    if drains > 0:
        add(g, "ท่อน้ำทิ้ง PVC ชั้น 8.5 ขนาด Ø 2\" พร้อมข้อต่อ", drains * 3.0 + 6.0, "ม.",
            mat_key="ท่อ PVC 2\" ชั้น 8.5 (รวมข้อต่อ)", lab=lab("3.7", "Dia 2\""),
            basis=f"{drains} จุด × 3 ม. + 6 ม. ถึงบ่อพัก", ref=f"{W480} 3.7")
    if wcs:
        add(g, "ท่อโสโครก PVC ชั้น 8.5 ขนาด Ø 4\" พร้อมข้อต่อ", wcs * 3.0 + 4.0, "ม.",
            mat_key="ท่อ PVC 4\" ชั้น 8.5 (รวมข้อต่อ)", lab=lab("3.7", "Dia 4\""),
            basis=f"{wcs} โถ × 3 ม. + 4 ม. ถึงถังบำบัด", ref=f"{W480} 3.7")
        add(g, "ท่ออากาศ PVC Ø 1½\"", wcs * 4.0, "ม.",
            mat_key="ท่อ PVC 1½\" ชั้น 8.5 (รวมข้อต่อ)", lab=lab("3.7", "Dia 1 1/2"),
            basis=f"{wcs} โถ × 4 ม.", ref=f"มยผ. 1201 · {W480} 3.7")
    if wets:
        add(g, "ตะแกรงกันกลิ่น ฟลอร์เดรน (FD) Ø 2\"", len(wets), "ชุด",
            mat_key="ฟลอร์เดรนกันกลิ่น 2\"", lab=lab("3.13", "Dia 2\""),
            basis="1 ชุดต่อห้องน้ำ", ref=f"{W480} 3.13")
    beds = sum(1 for r in rooms if r["kind"] == "bed")
    if wcs or beds:
        persons = max(2 * beds, 4)
        size = next((v for p_, v in ((5, 800), (7, 1000), (10, 1600), (15, 2000))
                     if persons <= p_), 3000)
        add(g, f"ถังบำบัดน้ำเสียสำเร็จรูป {size:,} ลิตร (ผู้อยู่อาศัย {persons} คน)", 1,
            "ชุด", mat_key=f"ถังบำบัดน้ำเสียสำเร็จรูป {size:,} ลิตร (พร้อมติดตั้ง)",
            basis=f"ห้องนอน {beds} ห้อง × 2 คน", ref="กฎกระทรวง/มยผ. ระบบบำบัดน้ำเสีย",
            note=unlisted)
    if kitchens:
        add(g, "บ่อดักไขมันสำเร็จรูป", len(kitchens), "ชุด",
            mat_key="บ่อดักไขมันสำเร็จรูป (พร้อมติดตั้ง)", basis="1 ชุดต่อครัว",
            ref="มยผ. 1201", note=unlisted)

    # --- 12 ไฟฟ้า -----------------------------------------------------------
    g = "electric"
    lights = sum(r["lights"] for r in rooms)
    outlets = sum(r["outlets"] for r in rooms)
    switches = sum(r["switches"] for r in rooms)
    tvs = sum(r["tv"] for r in rooms)
    fans = sum(r["fan"] for r in rooms)
    acs = [r for r in rooms if r["ac"]]
    heaters = sum(1 for r in rooms if r["heater"])
    add(g, "ดวงโคมดาวน์ไลท์ LED 1×18 วัตต์ พร้อมหลอด", lights, "ชุด",
        mat_key="ดวงโคม LED ดาวน์ไลท์ 18 W", lab=lab("4.58", "1 - 18"),
        basis="1 ชุดต่อพื้นที่ ≤ 9 ตร.ม. (ห้องน้ำ/ทางเดิน 1 ชุด)",
        ref=f"วสท. แสงสว่างภายในอาคาร · {W480} 4.58")
    add(g, "สวิตช์ทางเดียว 1 ช่อง พร้อมฝาครอบ", switches, "ชุด",
        mat_key="สวิตช์ทางเดียว 1 ช่อง", lab=lab("4.53", "Single Switch 1"),
        basis="ข้างประตูทุกบาน สูง 1.20 ม.", ref=f"{W480} 4.53")
    add(g, "เต้ารับคู่ 3 ขา มีสายดิน", outlets, "ชุด",
        mat_key="เต้ารับคู่ 3 ขา มีกราวด์", lab=lab("4.53", "Duplex Receptacle 2P + G"),
        basis="ตามชนิดห้อง สูง 0.30 ม. (ห้องน้ำ/ครัว 1.20 ม.)",
        ref=f"วสท. 2001 · {W480} 4.53")
    if tvs:
        add(g, "เต้ารับโทรทัศน์ (TV Outlet)", tvs, "ชุด", mat_key="เต้ารับโทรทัศน์",
            lab=lab("4.53", "T.V. Outlet"), basis="ห้องนอน/ห้องนั่งเล่น", ref=f"{W480} 4.53")
    c_light = max(1, math.ceil(lights / 10))
    c_out = max(1, math.ceil(outlets / 8))
    circuits = c_light + c_out + len(acs) + heaters
    wire = lights * 6.0 + switches * 3.0
    add(g, "สาย VAF 2×1.5 ตร.มม. (วงจรแสงสว่าง)", wire, "ม.",
        mat_key="สาย VAF 2×1.5 ตร.มม.", lab=lab("4.22", "1.5 sq"),
        basis=f"{lights} ดวง × 6 ม. + {switches} สวิตช์ × 3 ม.", ref=f"{W480} 4.22")
    wire2 = outlets * 6.0 + tvs * 8.0
    add(g, "สาย VAF-G 2×2.5 ตร.มม. (วงจรเต้ารับ)", wire2, "ม.",
        mat_key="สาย VAF-G 2×2.5 ตร.มม.", lab=lab("4.24"),
        basis=f"{outlets} เต้ารับ × 6 ม.", ref=f"{W480} 4.24")
    dedicated = (len(acs) + heaters) * 15.0
    if dedicated:
        add(g, "สาย THW 4 ตร.มม. + สายดิน (วงจรแอร์/เครื่องทำน้ำอุ่น)", dedicated * 3,
            "ม.", mat_key="สาย THW 4 ตร.มม.", lab=lab("4.22", "4 sq"),
            basis=f"{len(acs) + heaters} วงจร × 15 ม. × 3 เส้น (L N G)",
            ref=f"วสท. 2001 วงจรเฉพาะ · {W480} 4.22")
    add(g, "ท่อร้อยสายไฟ PVC สีเหลือง Ø 20 มม.", wire + wire2 + dedicated, "ม.",
        mat_key="ท่อ PVC ร้อยสายไฟ 20 มม. (สีเหลือง)", lab=lab("4.44", "20 mm"),
        basis="เท่าความยาวสายทุกวงจร", ref=f"{W480} 4.44")
    add(g, f"ตู้ควบคุมไฟฟ้า (Consumer Unit) {circuits + 2} ช่อง พร้อมเมนเบรกเกอร์ "
           "และกันดูด (RCBO)", 1, "ชุด", mat_key="ตู้คอนซูมเมอร์ยูนิต (พร้อมเมน+RCBO)",
        lab=lab("4.57"), basis=f"วงจรแสงสว่าง {c_light} เต้ารับ {c_out} แอร์ {len(acs)} "
                                f"น้ำอุ่น {heaters} + สำรอง 2", ref=f"วสท. 2001 · {W480} 4.57")
    add(g, "เบรกเกอร์ย่อย 1P (16/20/32 A)", circuits, "ชุด",
        mat_key="เบรกเกอร์ลูกย่อย 1P", lab=lab("4.57"), basis="1 ตัวต่อวงจร",
        ref=f"{W480} 4.57")
    add(g, "หลักดิน (Ground Rod) Ø 5/8\" ยาว 2.40 ม. พร้อมสายต่อหลักดิน", 1, "ชุด",
        mat_key="หลักดิน 5/8\" × 2.40 ม. พร้อมสาย", basis="1 ชุดต่ออาคาร",
        ref="วสท. 2001 การต่อลงดิน", note=unlisted)

    # --- 13 ปรับอากาศ -------------------------------------------------------
    g = "hvac"
    sizes: dict = {}
    for r in acs:
        sizes[r["ac"]] = sizes.get(r["ac"], 0) + 1
    for btu, cnt in sorted(sizes.items()):
        add(g, f"เครื่องปรับอากาศแยกส่วนติดผนัง {btu:,} BTU/ชม. (Inverter)", cnt, "ชุด",
            mat_key=f"เครื่องปรับอากาศติดผนัง {btu:,} BTU", lab=lab("5.1", f"{btu:,}"),
            basis="ห้องนอน 800 / นั่งเล่น 900 BTU ต่อ ตร.ม.",
            ref=f"{W480} 5.1 (ค่าติดตั้งเครื่อง)")
    if acs:
        n = len(acs)
        add(g, "ท่อทองแดง Type L Ø 3/8\" + Ø 1/2\" (ท่อน้ำยา)", n * 4.0 * 2, "ม.",
            mat_key="ท่อทองแดง Type L 3/8\"+1/2\"", lab=lab("5.4", "3/8"),
            basis=f"{n} ชุด × 4 ม. × 2 เส้น", ref=f"{W480} 5.4")
        add(g, "ฉนวนหุ้มท่อน้ำยา หนา 3/4\"", n * 4.0 * 2, "ม.",
            mat_key="ฉนวนหุ้มท่อ 3/4\"", lab=lab("5.6", "1/2\" Thick 3/4"),
            basis=f"{n} ชุด × 4 ม. × 2 เส้น", ref=f"{W480} 5.6")
        add(g, "ท่อน้ำทิ้งแอร์ PVC Ø 3/4\"", n * 4.0, "ม.",
            mat_key="ท่อ PVC 3/4\" ชั้น 8.5", lab=lab("5.5", "3/4"),
            basis=f"{n} ชุด × 4 ม.", ref=f"{W480} 5.5")
        add(g, "แท่นวางคอยล์ร้อน ค.ส.ล./ขาแขวน", n, "ชุด",
            mat_key="แท่นคอยล์ร้อน (พร้อมติดตั้ง)", basis="1 ชุดต่อเครื่อง",
            ref="งานปรับอากาศ", note=unlisted)
    if fans:
        add(g, "พัดลมระบายอากาศ ติดผนัง/ฝ้า 8\"", fans, "ชุด",
            mat_key="พัดลมระบายอากาศ 8\"", lab=lab("5.2"),
            basis="ห้องน้ำ ห้องครัว ห้องละ 1 ชุด", ref=f"{W480} 5.2")

    # --- 14 ภายนอก ----------------------------------------------------------
    g = "external"
    ring = perim + 8 * 1.0                               # 1 ม. นอกแนวผนัง
    add(g, "ท่อระบายน้ำ ค.ส.ล. Ø 0.30 ม. รอบอาคาร", ring, "ม.",
        mat_key="ท่อ คสล. Ø 0.30 ม. (มอก.)", basis=f"รอบอาคารห่าง 1 ม. ({ring:.1f} ม.)",
        ref="งานระบายน้ำภายนอก", note=unlisted)
    pits = max(4, math.ceil(ring / 6.0))
    add(g, "บ่อพัก ค.ส.ล. ขนาด 0.60×0.60 ม. พร้อมฝาตะแกรง", pits, "บ่อ",
        mat_key="บ่อพัก คสล. 0.60×0.60 ม. (พร้อมฝา)", basis="ทุก 6 ม. และทุกมุม",
        ref="งานระบายน้ำภายนอก", note=unlisted)
    walk = (perim + 4 * 0.6) * 0.60 * 0.10
    add(g, "ทางเท้ารอบอาคาร ค.ส.ล. กว้าง 0.60 ม. หนา 0.10 ม.", walk, "ลบ.ม.",
        mat_key="คอนกรีตผสมเสร็จ 240 กก./ตร.ซม. (ลูกบาศก์)",
        lab=lab("1.7", "", "ทางเท้า"), basis=f"({perim:.1f} + 2.4) ม. × 0.60 × 0.10",
        ref=f"{W480} 1.7 (ทางเท้า ทางระบายน้ำ)")

    # --- 15 อื่นๆ ------------------------------------------------------------
    g = "misc"
    add(g, "ป้ายประชาสัมพันธ์โครงการ", 1, "ป้าย", mat_key="ป้ายโครงการ (พร้อมติดตั้ง)",
        basis="1 ป้ายต่อโครงการ", ref="งานอื่นๆ", note=unlisted)
    add(g, "ทำความสะอาดอาคารและพื้นที่ก่อนส่งมอบ", footprint * E["n"], "ตร.ม.",
        mat_key="ค่าทำความสะอาด (ต่อ ตร.ม.)", basis="พื้นที่ใช้สอยทุกชั้น",
        ref="งานอื่นๆ", note=unlisted)
