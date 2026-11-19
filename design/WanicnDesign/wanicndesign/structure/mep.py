# -*- coding: utf-8 -*-
"""Electrical and plumbing quantities of a house, measured from the model.

What is measured (from the building): the rooms (slab bays of every floor
with rooms), their areas, the bathrooms and their fixtures, the distance of
each room from the switchboard and from the water meter along the grid
(right-angle runs) plus the riser between floors.

What is the user's (``Building.mep``, project defaults shown in the BOQ
note): how many light points per area, sockets per room, air-conditioner
points, the cable and pipe types, and the allowance on the measured runs.
No law or standard fixes these counts for a house; the program does not
pretend one does.

Labour follows ว480 หมวด 3–4 (26 มิ.ย. 2569) [W480-MEP]; the pipe fittings,
hangers and testing follow the percentages printed under 3.7–3.8: material
a share of the pipe price, labour 30 % of that material.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass

from ..rates import DATA_DIR

with open(os.path.join(DATA_DIR, "labour_mep_2569.json"), encoding="utf-8") as _f:
    MEP_DATA = json.load(_f)

WATER_FIXTURES = ("toilet", "basin", "shower", "spray")       # need a water point and a stop valve
DRAIN = {"toilet": '4"', "basin": '2"', "shower": '2"', "drain": '2"'}

#: price-book keys of the materials (the user's prices; per the BOQ unit)
K_PIPE_WATER = 'ท่อ PVC ชั้น 8.5 ขนาด {d} (ประปา)'
K_PIPE_DRAIN = 'ท่อ PVC ชั้น 8.5 ขนาด {d} (ระบายน้ำ)'
K_CABLE = "สายไฟ {t} 2x{s} ตร.มม."
K_CONDUIT = "ท่อร้อยสาย PVC สีเหลือง {d} มม."
K_LIGHT = "โคมดาวน์ไลท์ LED 6\" พร้อมหลอด"
K_SWITCH = "สวิตช์ทางเดียว 1 ช่อง พร้อมฝาและบ็อกซ์"
K_SOCKET = "เต้ารับคู่มีกราวด์ พร้อมฝาและบ็อกซ์"
K_AC = "เต้ารับ/จุดต่อเครื่องปรับอากาศ พร้อมสาย"
K_BREAKER = "เบรกเกอร์ลูกย่อย 2P"
K_PANEL = "ตู้ควบคุมไฟฟ้า (Consumer Unit) พร้อมติดตั้ง"
K_VALVE = 'สต๊อปวาล์ว 1/2"'
K_SEPTIC = "ถังบำบัดน้ำเสียสำเร็จรูป พร้อมติดตั้ง"


@dataclass
class Mep:
    """Electrical and plumbing defaults of the project (all editable)."""
    enabled: bool = True
    panel: str = "1A"              # grid node of the switchboard
    meter: str = "1A"              # grid node of the water meter / building water inlet
    light_area: float = 9.0        # m² of floor per light point (at least one per room)
    sockets: int = 2               # duplex sockets per room (none in bathrooms)
    ac_points: int = 0             # air-conditioner points in the whole building
    cable: str = "VAF"             # VAF (300 V, clipped) or VVF (750 V)
    conduit: bool = False          # cables in yellow PVC conduit
    lights_per_circuit: int = 10
    sockets_per_circuit: int = 8
    drop: float = 1.5              # m of cable or pipe down/up the wall to each point
    allowance: float = 10.0        # % on every measured run (bends, laps)
    service_water: float = 10.0    # m of 3/4" pipe from the public main to the meter
    septic: int = 1                # septic tanks (supplier's set)


def _node_xy(b, name: str):
    xs, ys = b.xs, b.ys
    for i in range(len(xs)):
        for j in range(len(ys)):
            if b.node_name(i, j) == name.upper():
                return xs[i], ys[j]
    return 0.0, 0.0


def rooms(b):
    """[(level, elevation, bay, area, wet, centre x, centre y)] of every floor with rooms."""
    out = []
    for lv in b.levels:
        if lv.slab in ("roof", "none", "deck"):
            continue
        for i, j in b.panels(lv.name):
            x0, x1, y0, y1 = b.xs[i], b.xs[i + 1], b.ys[j], b.ys[j + 1]
            name = b.panel_name(i, j)
            out.append((lv.name, lv.elevation, name, (x1 - x0) * (y1 - y0), name in lv.wet_bays,
                        (x0 + x1) / 2, (y0 + y1) / 2))
    return out


def _run(b, node, x, y, z, m: Mep) -> float:
    """Right-angle run from a grid node at ground level to a room centre at level z, with one drop."""
    nx, ny = _node_xy(b, node)
    base = b.levels[0].elevation if b.levels else 0.0
    return (abs(x - nx) + abs(y - ny) + max(0.0, z - base) + m.drop) * (1 + m.allowance / 100)


def _circuit(b, node, x, y, z, area, n, m: Mep) -> float:
    """One home run from the board to the room, then point to point (spacing √(area/n)) with a drop at each."""
    if n <= 0:
        return 0.0
    within = (n - 1) * ((area / n) ** 0.5 + m.drop)
    return _run(b, node, x, y, z, m) + within * (1 + m.allowance / 100)


def mep_lines(b) -> list[dict]:
    """BOQ lines (dicts for model.Project.mep) of the electrical and plumbing works."""
    m = b.mep
    if not m.enabled:
        return []
    out = []

    def add(section, item, qty, unit, code="", note="", mats=(), labour_pct=0.0):
        if qty and qty > 0:
            out.append({"section": section, "item": item, "qty": round(qty, 3), "unit": unit, "code": code,
                        "note": note, "mats": [list(x) for x in mats], "labour_pct": labour_pct})

    rs = rooms(b)
    dry = [r for r in rs if not r[4]]
    # ---- electrical ----------------------------------------------------------
    E = "งานระบบไฟฟ้า"
    lights = sockets = 0
    l_run = s_run = 0.0
    for lvn, z, bay, area, wet, x, y in rs:
        n_l = max(1, round(area / max(m.light_area, 1.0)))
        n_s = 0 if wet else m.sockets
        lights += n_l
        sockets += n_s
        l_run += _circuit(b, m.panel, x, y, z, area, n_l, m)
        s_run += _circuit(b, m.panel, x, y, z, area, n_s, m)
    switches = len(rs)
    t = "VAF" if m.cable.upper() != "VVF" else "VVF"
    c_l, c_s = ("4.21/VAF (300 Volt) 1.5 sq.mm.", "4.23/VAF/G (300 Volt) 2.5/1.5 sq.mm.") if t == "VAF" else \
        ("4.22/VVF (750 Volt) 1.5 sq.mm.", "4.24/VVF/G (750 Volt) 2.5/1.5 sq.mm.")
    how = (f"ห้องละ 1 แนวจากตู้ไฟ {m.panel} ถึงกึ่งกลางห้อง (แนวตั้งฉาก + ระยะขึ้นชั้น) แล้วต่อจุดถึงจุด "
           f"ระยะ √(พื้นที่/จุด) ลงจุดละ {m.drop:g} ม. เผื่อ {m.allowance:g}%")
    add(E, f"เดินสาย {t} 2x1.5 ตร.มม. วงจรแสงสว่าง", l_run, "เมตร", c_l, how,
        [(K_CABLE.format(t=t, s="1.5"), 1.0)])
    add(E, f"เดินสาย {t}/G 2x2.5/1.5 ตร.มม. วงจรเต้ารับ", s_run, "เมตร", c_s, how,
        [(K_CABLE.format(t=t + "/G", s="2.5"), 1.0)])
    if m.conduit:
        add(E, "ท่อร้อยสาย PVC สีเหลือง 15 มม.", l_run + s_run, "เมตร", "4.44/PVC Conduit (yellow) dia 15 mm.",
            "ตามความยาวสาย", [(K_CONDUIT.format(d=15), 1.0)])
    add(E, "โคมดาวน์ไลท์ 4\"–6\" พร้อมหลอด", lights, "ชุด", "4.58/โคม Downlight/ขนาด dia 4\" - 6\"",
        f"1 จุดต่อพื้นที่ {m.light_area:g} ตร.ม. อย่างน้อยห้องละ 1 จุด (ค่าเริ่มต้นของโครงการ)", [(K_LIGHT, 1.0)])
    add(E, "สวิตช์ทางเดียว 1 ช่อง", switches, "ชุด", "4.53/Switch and receptacle/Single Switch 1 Gang",
        "ห้องละ 1 ชุด", [(K_SWITCH, 1.0)])
    add(E, "เต้ารับคู่มีกราวด์ 2P+G", sockets, "ชุด", "4.53/Switch and receptacle/Duplex Receptacle 2P + G",
        f"ห้องละ {m.sockets} ชุด (ไม่ติดในห้องน้ำ)", [(K_SOCKET, 1.0)])
    if m.ac_points:
        add(E, "จุดต่อเครื่องปรับอากาศ (สายและเต้ารับ)", m.ac_points, "จุด",
            "4.53/Switch and receptacle/Single Receptacle 2P + G", "จำนวนตามที่กำหนด", [(K_AC, 1.0)])
    circuits = -(-lights // max(m.lights_per_circuit, 1)) + -(-sockets // max(m.sockets_per_circuit, 1)) + m.ac_points
    add(E, "เบรกเกอร์ลูกย่อย 2P", circuits, "ชุด", "4.57/C.B. 2 Pole (10, 15, 20, 30. 40 AT)",
        f"แสงสว่าง {m.lights_per_circuit} จุด/วงจร เต้ารับ {m.sockets_per_circuit} จุด/วงจร "
        "เครื่องปรับอากาศ 1 วงจร/เครื่อง", [(K_BREAKER, 1.0)])
    add(E, "ตู้ควบคุมไฟฟ้า (Consumer Unit)", 1, "ชุด", "", "ราคาผู้ขายรวมติดตั้ง (ว480 ไม่มีรายการ)",
        [(K_PANEL, 1.0)])
    # ---- plumbing --------------------------------------------------------------
    P = "งานระบบประปา สุขาภิบาล"
    extra = MEP_DATA["pipe_extra"]
    wet_rooms = [r for r in rs if r[4]]
    fx = {k: len(wet_rooms) for k in WATER_FIXTURES + ("drain",)}      # one of each fixture per bathroom
    if wet_rooms:
        w_run = sum(_circuit(b, m.meter, x, y, z, area, len(WATER_FIXTURES), m) for _l, z, _b, area, _w, x, y in wet_rooms)
        small = [k for k, d in DRAIN.items() if d == '2"']
        d_run = {'4"': sum(_run(b, m.meter, x, y, z, m) for _l, z, _b, _a, _w, x, y in wet_rooms),
                 '2"': sum(_circuit(b, m.meter, x, y, z, area, len(small), m) for _l, z, _b, area, _w, x, y in wet_rooms)}
        measured = f"วัดจากมาตรวัดน้ำ/บ่อ {m.meter} แนวตั้งฉาก + ระยะขึ้นชั้น เผื่อ {m.allowance:g}%"
        pipes = [("3.8", '1/2"', w_run, K_PIPE_WATER, "ท่อประปา PVC 1/2\" ถึงสุขภัณฑ์", measured),
                 ("3.8", '3/4"', m.service_water, K_PIPE_WATER, "ท่อประปา PVC 3/4\" จากท่อเมนถึงมาตรวัดน้ำ",
                  "ความยาวตามที่กำหนด")]
        pipes += [("3.7", d, run, K_PIPE_DRAIN, f"ท่อระบายน้ำ PVC {d}", measured) for d, run in sorted(d_run.items())]
        for sec, d, run, key, label, note in pipes:
            if run <= 0:
                continue
            k = key.format(d=d)
            add(P, label, run, "เมตร", f"{sec}/Dia {d}", note, [(k, 1.0)])
            r = extra[sec]
            for part, txt in (("fittings", "ข้อต่อ อุปกรณ์ท่อ"), ("hangers", "เหล็กยึดท่อ"),
                              ("test", "ทดสอบ ทำความสะอาด ทาสัญลักษณ์ท่อ")):
                add(P, f"{txt} ({label})", run, "เมตร", "",
                    f"วัสดุ {r[part] * 100:g}% ของราคาท่อ ค่าแรง {r['labour'] * 100:g}% ของค่าวัสดุ (ว480 {sec})",
                    [(k, r[part])], labour_pct=r["labour"])
        valves = sum(fx[k] for k in ("toilet", "basin", "spray"))
        add(P, 'สต๊อปวาล์ว 1/2"', valves, "ชุด", '3.11/STOP VALVE - Dia 1/2"', "โถส้วม อ่างล้างหน้า สายชำระ",
            [(K_VALVE, 1.0)])
        add(P, "ถังบำบัดน้ำเสียสำเร็จรูป", m.septic, "ชุด", "", "ราคาผู้ขายรวมติดตั้ง (ว480 ไม่มีรายการ)",
            [(K_SEPTIC, 1.0)])
    return out
