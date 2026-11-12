# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
"""ออกแบบ Truss: steel roof trusses from the form to the steel sizes.

- the form: six standard trusses (Howe, Pratt, Fink, Warren, king-post /
  scissor-free gable, parallel chords), an ARCHED truss (top and bottom
  chords on circles, Warren webs — the warehouse truss) and a truss of the
  user's own nodes and members;
- the analysis: the matrix stiffness method of a pin-jointed plane truss
  (axial members only), supports pinned or on rollers, the roof's purlin
  loads at the top-chord nodes and the self weight;
- the design: allowable stress (AISC ASD, as Thai practice): tension
  0.60 Fy on the gross area, compression Fa from KL/r against Cc, KL/r
  ≤ 200 (300 in tension); the lightest section of the chosen family that
  passes, one size for the top chord, one for the bottom chord, one for
  the webs;
- the bearing: a base plate under each support on its stub column.

Units: kg, m (stresses in ksc = kg/cm²)."""
from __future__ import annotations

import math
from dataclasses import dataclass, field

FY = 2450.0                    # SS400 / STK400 (ksc)
E = 2.04e6

TYPES = {"howe": "Howe", "pratt": "Pratt", "fink": "Fink (W)", "warren": "Warren",
         "kingpost": "จั่วธรรมดา (ดั้ง-ค้ำยัน)", "parallel": "คอร์ดขนาน (หลังคาแบน)",
         "arch": "Truss โค้ง", "custom": "เขียนเอง"}


# ---- sections -------------------------------------------------------------------------

@dataclass
class Sec:
    label: str
    A: float                   # cm²
    r: float                   # least radius of gyration, cm
    kg_m: float


def _pipe(D, t):
    d = D - 2 * t
    A = math.pi * (D * D - d * d) / 4 / 100                     # mm² → cm²
    I = math.pi * (D ** 4 - d ** 4) / 64 / 1e4                  # mm⁴ → cm⁴
    return Sec(f"Dia.{D:g}x{t:g}", A, math.sqrt(I / A), A * 0.785)


def _box(H, B, t):
    A = (B * H - (B - 2 * t) * (H - 2 * t)) / 100
    Ix = (B * H ** 3 - (B - 2 * t) * (H - 2 * t) ** 3) / 12 / 1e4
    Iy = (H * B ** 3 - (H - 2 * t) * (B - 2 * t) ** 3) / 12 / 1e4
    return Sec(f"{'□' if H == B else '▭'}{H:g}x{B:g}x{t:g}", A, math.sqrt(min(Ix, Iy) / A), A * 0.785)


def _lipc(H, B, C, t):
    # thin-walled centre line: web H-t, flanges B-t, lips C-t/2
    h, b, c = H - t, B - t, C - t / 2
    A = t * (h + 2 * b + 2 * c)
    xs = [(b / 2, b * t), (0.0, h * t), (b, 2 * c * t)]          # web at x=0, flanges' centres, lips
    A2 = A / 2
    xb = (b * t * b + 2 * c * t * b) / A                         # centroid x
    Iy = (2 * (t * b ** 3 / 12 + b * t * (b / 2 - xb) ** 2) + h * t * xb ** 2 + 2 * c * t * (b - xb) ** 2)
    Ix = t * h ** 3 / 12 + 2 * b * t * (h / 2) ** 2 + 2 * (t * c ** 3 / 12 + c * t * (h / 2 - c / 2) ** 2)
    A, Ix, Iy = A / 100, Ix / 1e4, Iy / 1e4
    return Sec(f"C{H:g}x{B:g}x{C:g}x{t:g}", A, math.sqrt(min(Ix, Iy) / A), A * 0.785)


#: the families, lightest first (มอก. 107 pipes, square/rectangular tubes, lipped C)
CATALOG = {
    "pipe": sorted([_pipe(D, t) for D, t in ((27.2, 2.3), (34.0, 2.3), (42.7, 2.3), (42.7, 3.2), (48.6, 2.3),
                                             (48.6, 3.2), (60.5, 2.3), (60.5, 3.2), (76.3, 3.2), (89.1, 3.2),
                                             (101.6, 3.2), (114.3, 3.5), (139.8, 4.5))], key=lambda s: s.kg_m),
    "box": sorted([_box(H, B, t) for H, B, t in ((25, 25, 1.6), (38, 38, 1.6), (50, 50, 2.0), (50, 50, 2.3),
                                                 (75, 75, 2.3), (75, 75, 3.2), (100, 100, 2.3), (100, 100, 3.2),
                                                 (125, 125, 3.2), (150, 150, 4.5), (100, 50, 2.3),
                                                 (150, 50, 3.2))], key=lambda s: s.kg_m),
    "lc": sorted([_lipc(H, B, C, t) for H, B, C, t in ((75, 45, 15, 2.3), (100, 50, 20, 2.3), (100, 50, 20, 3.2),
                                                       (125, 50, 20, 3.2), (150, 50, 20, 3.2), (150, 65, 20, 3.2),
                                                       (200, 75, 20, 3.2))], key=lambda s: s.kg_m),
}
FAMILY_TH = {"pipe": "เหล็กท่อกลม", "box": "เหล็กกล่อง", "lc": "เหล็กตัวซี"}


def allowable(sec: Sec, L: float, compression: bool) -> tuple[float, float]:
    """(allowable force kg, KL/r) — ASD: tension 0.6Fy·A, compression Fa(KL/r)."""
    klr = L * 100 / sec.r
    if not compression:
        return 0.60 * FY * sec.A, klr
    Cc = math.sqrt(2 * math.pi ** 2 * E / FY)
    if klr <= Cc:
        fs = 5 / 3 + 3 * (klr / Cc) / 8 - (klr / Cc) ** 3 / 8
        Fa = (1 - klr ** 2 / (2 * Cc ** 2)) * FY / fs
    else:
        Fa = 12 * math.pi ** 2 * E / (23 * klr ** 2)
    return Fa * sec.A, klr


# ---- geometry -----------------------------------------------------------------------------

@dataclass
class Truss:
    nodes: list                       # [(x, y)] m
    members: list                     # [(i, j, group)] group: "top" / "bottom" / "web"
    supports: dict                    # node → "pin" | "roller"
    top: list = field(default_factory=list)       # top-chord nodes (for the purlin loads)
    kind: str = ""


def make(kind: str, span: float, rise: float, panels: int = 6, depth: float = 0.6,
         radius: float = 0.0) -> Truss:
    """A truss of ``kind`` over ``span`` (m), ``rise`` at mid-span (m),
    ``panels`` (even), ``depth`` for arched / parallel trusses (m)."""
    n = max(2, int(panels) + int(panels) % 2)
    xs = [span * i / n for i in range(n + 1)]
    if kind in ("arch", "parallel"):
        if kind == "arch":
            R = radius or (span * span / 4 + rise * rise) / (2 * rise)          # the top chord's circle

            def ytop(x):
                return math.sqrt(max(R * R - (x - span / 2) ** 2, 0.0)) - (R - rise) + depth
        else:
            def ytop(x):
                return depth
        nodes = [(x, 0.0 if kind == "parallel" else max(ytop(x) - depth, 0.0)) for x in xs]   # bottom
        nodes += [(x, ytop(x)) for x in xs]                                                    # top
        bot = list(range(0, n + 1))
        top = list(range(n + 1, 2 * n + 2))
        mem = [(bot[i], bot[i + 1], "bottom") for i in range(n)] + \
              [(top[i], top[i + 1], "top") for i in range(n)]
        mem += [(bot[i], top[i], "web") for i in range(n + 1)]
        for i in range(n):                          # Warren / Pratt diagonals towards mid-span
            if xs[i] < span / 2:
                mem.append((bot[i], top[i + 1], "web") if kind == "arch" else (top[i], bot[i + 1], "web"))
            else:
                mem.append((top[i], bot[i + 1], "web") if kind == "arch" else (bot[i], top[i + 1], "web"))
        return Truss(nodes, mem, {bot[0]: "pin", bot[-1]: "roller"}, top, kind)
    # triangular trusses: bottom chord on y = 0, top chord to the apex
    def yt(x):
        return rise * (1 - abs(x - span / 2) / (span / 2))
    if kind == "fink":                         # the W: 4 rafter panels, 3 bottom panels, no verticals
        nodes = [(0.0, 0.0), (span / 3, 0.0), (2 * span / 3, 0.0), (span, 0.0),
                 (span / 4, yt(span / 4)), (span / 2, rise), (3 * span / 4, yt(3 * span / 4))]
        mem = [(0, 1, "bottom"), (1, 2, "bottom"), (2, 3, "bottom"),
               (0, 4, "top"), (4, 5, "top"), (5, 6, "top"), (6, 3, "top"),
               (1, 4, "web"), (1, 5, "web"), (2, 5, "web"), (2, 6, "web")]
        return Truss(nodes, mem, {0: "pin", 3: "roller"}, [0, 4, 5, 6, 3], kind)
    if kind == "kingpost":                     # ดั้ง + ค้ำยัน: 4 panels, struts to the king post's foot
        n = 4
        xs = [span * i / n for i in range(n + 1)]
    nodes = [(x, 0.0) for x in xs]
    top_ids = [0]
    for i in range(1, n):
        nodes.append((xs[i], yt(xs[i])))
        top_ids.append(len(nodes) - 1)
    top_ids.append(n)
    mem = [(i, i + 1, "bottom") for i in range(n)]
    mem += [(top_ids[i], top_ids[i + 1], "top") for i in range(n)]
    mid = n // 2
    for i in range(1, n):
        mem.append((i, top_ids[i], "web"))                             # verticals
    for i in range(n):
        left = i < mid
        if kind in ("howe", "kingpost"):         # diagonals down to mid-span (compression)
            mem.append((top_ids[i], i + 1, "web") if left else (i, top_ids[i + 1], "web"))
        elif kind == "warren":
            mem.append((i, top_ids[i + 1], "web") if i % 2 == 0 else (top_ids[i], i + 1, "web"))
        else:                                    # pratt: diagonals up to mid-span (tension)
            mem.append((i, top_ids[i + 1], "web") if left else (top_ids[i], i + 1, "web"))
    seen, uniq = set(), []
    for a, b, g in mem:                          # the end diagonals fall on the chords: keep the chord
        key = (min(a, b), max(a, b))
        if a != b and key not in seen:
            seen.add(key)
            uniq.append((a, b, g))
    return Truss(nodes, uniq, {0: "pin", n: "roller"}, top_ids, kind)


def custom(nodes, members, supports) -> Truss:
    """A truss of the user's own: nodes [(x, y)], members [(i, j, group)]."""
    top = sorted({i for a, b, g in members if g == "top" for i in (a, b)})
    return Truss(list(nodes), list(members), dict(supports), top, "custom")


# ---- the stiffness method ---------------------------------------------------------------

def solve(t: Truss, loads: dict, EA: float = 1.0) -> dict:
    """``loads`` = {node: (Fx, Fy)} kg (Fy downwards negative). Returns
    {"force": [N per member, + tension], "reactions": {node: (Rx, Ry)},
    "length": [L]}."""
    nn = len(t.nodes)
    K = [[0.0] * (2 * nn) for _ in range(2 * nn)]
    lens = []
    for a, b, _g in t.members:
        (x1, y1), (x2, y2) = t.nodes[a], t.nodes[b]
        L = math.hypot(x2 - x1, y2 - y1)
        lens.append(L)
        c, s = (x2 - x1) / L, (y2 - y1) / L
        k = EA / L
        m = [[c * c, c * s], [c * s, s * s]]
        for i_, ni in enumerate((a, b)):
            for j_, nj in enumerate((a, b)):
                sg = 1 if i_ == j_ else -1
                for p in range(2):
                    for q in range(2):
                        K[2 * ni + p][2 * nj + q] += sg * k * m[p][q]
    F = [0.0] * (2 * nn)
    for nd, (fx, fy) in loads.items():
        F[2 * nd] += fx
        F[2 * nd + 1] += fy
    fixed = set()
    for nd, kind in t.supports.items():
        fixed.add(2 * nd + 1)
        if kind == "pin":
            fixed.add(2 * nd)
    free = [i for i in range(2 * nn) if i not in fixed]
    A = [[K[r][c] for c in free] + [F[r]] for r in free]
    m_ = len(free)
    for c in range(m_):
        piv = max(range(c, m_), key=lambda r: abs(A[r][c]))
        if abs(A[piv][c]) < 1e-12:
            raise ValueError("โครง Truss ไม่มีเสถียรภาพ (unstable) — ตรวจชิ้นส่วนและจุดรองรับ")
        A[c], A[piv] = A[piv], A[c]
        for r in range(m_):
            if r != c:
                f = A[r][c] / A[c][c]
                if f:
                    A[r] = [A[r][j] - f * A[c][j] for j in range(m_ + 1)]
    u = [0.0] * (2 * nn)
    for i, dof in enumerate(free):
        u[dof] = A[i][m_] / A[i][i]
    force = []
    for (a, b, _g), L in zip(t.members, lens):
        (x1, y1), (x2, y2) = t.nodes[a], t.nodes[b]
        c, s = (x2 - x1) / L, (y2 - y1) / L
        force.append(EA / L * (c * (u[2 * b] - u[2 * a]) + s * (u[2 * b + 1] - u[2 * a + 1])))
    reac = {}
    for nd in t.supports:
        rx = sum(K[2 * nd][j] * u[j] for j in range(2 * nn)) - F[2 * nd]
        ry = sum(K[2 * nd + 1][j] * u[j] for j in range(2 * nn)) - F[2 * nd + 1]
        reac[nd] = (rx, ry)
    return {"force": force, "reactions": reac, "length": lens}


# ---- loads, design, base plate ------------------------------------------------------------

@dataclass
class Design:
    truss: Truss
    result: dict
    loads: dict
    pick: dict                        # group → Sec
    rows: list                        # per member: (no, group, L, N, allowable, KL/r, ratio)
    weight: float                     # kg of steel in one truss
    plate: dict
    w_plan: float


def roof_loads(t: Truss, span: float, spacing: float, q_dead: float, q_live: float,
               self_kg_m: float = 0.0) -> dict:
    """Purlin loads at the top-chord nodes: (dead + live per m² of plan) ×
    truss spacing × the plan width each node gathers, plus the self weight."""
    top = sorted(t.top, key=lambda i: t.nodes[i][0])
    loads = {}
    for k, nd in enumerate(top):
        xl = t.nodes[top[k - 1]][0] if k else t.nodes[nd][0]
        xr = t.nodes[top[k + 1]][0] if k + 1 < len(top) else t.nodes[nd][0]
        trib = (xr - xl) / 2
        loads[nd] = (0.0, -(q_dead + q_live) * spacing * trib)
    if self_kg_m:
        for a, b, _g in t.members:
            (x1, y1), (x2, y2) = t.nodes[a], t.nodes[b]
            w = self_kg_m * math.hypot(x2 - x1, y2 - y1) / 2
            for nd in (a, b):
                fx, fy = loads.get(nd, (0.0, 0.0))
                loads[nd] = (fx, fy - w)
    return loads


def design(t: Truss, span: float, spacing: float, q_dead: float, q_live: float, family: str = "pipe",
           fc: float = 240.0) -> Design:
    """Analyse (twice: with an assumed then the chosen self weight) and pick
    the lightest passing section per group."""
    cat = CATALOG[family]
    self_w = 8.0
    pick = {}
    for _round in range(3):
        loads = roof_loads(t, span, spacing, q_dead, q_live, self_w)
        res = solve(t, loads)
        pick = {}
        for grp in ("top", "bottom", "web"):
            idx = [i for i, m in enumerate(t.members) if m[2] == grp]
            for sec in cat:
                ok = True
                for i in idx:
                    N, L = res["force"][i], res["length"][i]
                    cap, klr = allowable(sec, L, N < 0)
                    if abs(N) > cap or klr > (200 if N < 0 else 300):
                        ok = False
                        break
                if ok:
                    pick[grp] = sec
                    break
            else:
                pick[grp] = cat[-1]
        tot_len = sum(res["length"])
        new_w = sum(pick[m[2]].kg_m * L for m, L in zip(t.members, res["length"])) / max(tot_len, 1e-9)
        if abs(new_w - self_w) < 0.5:
            break
        self_w = new_w
    rows = []
    for i, ((a, b, g), N, L) in enumerate(zip(t.members, res["force"], res["length"])):
        cap, klr = allowable(pick[g], L, N < 0)
        rows.append((i + 1, g, L, N, cap, klr, abs(N) / cap if cap else 9.9))
    weight = sum(pick[m[2]].kg_m * L for m, L in zip(t.members, res["length"]))
    R = max(abs(r[1]) for r in res["reactions"].values())
    # base plate on the stub: bearing 0.35 fc′, plate t = √(3 f m² / 0.75 Fy)
    fp = 0.35 * fc
    side = max(15.0, math.ceil(math.sqrt(R / fp) / 2.5) * 2.5)                    # cm
    f = R / (side * side)
    m = side / 2 - 5.0
    tp = max(6.0, math.ceil(math.sqrt(3 * f * m * m / (0.75 * FY)) * 10 / 1.0))    # mm
    # the heel (หัวเสา/ส้นโครง): fillet welds E70 6 มม. of the members meeting
    # at the supports — Fv = 0.30 Fu = 1,470 ksc on the throat 0.707·0.6 cm
    weld_cap = 0.30 * 4900 * 0.707 * 0.6                                           # kg per cm
    heel = []
    for nd in t.supports:
        for k, (a, b, g) in enumerate(t.members):
            if nd in (a, b):
                need = abs(res["force"][k]) / weld_cap
                heel.append((k + 1, g, res["force"][k], max(4.0, math.ceil(need))))
    plate = {"R": R, "side": side, "f": f, "t": tp, "bolts": "2-Ø16 มม. ยึดพุก/เหล็กเดือย",
             "weld": heel, "weld_cap": weld_cap}
    return Design(t, res, loads, pick, rows, weight, plate, q_dead + q_live)


# ---- the building's own truss ---------------------------------------------------------

TRUSS_DEFAULTS = {"kind": "howe", "span": 0.0, "rise": 0.0, "panels": 8, "depth": 0.8, "radius": 0.0,
                  "spacing": 4.0, "dead": 0.0, "live": 0.0, "family": "pipe"}


def params_of(data) -> dict:
    """data["truss"] with the gaps filled from the building: the span across
    the top floor's short side, the rise from the roof pitch, the dead load
    from the covering (plus 10 kg/m² of purlins), the live load from the basis."""
    from core import wanic_building as B
    from core import wanic_calc as C
    p = {**TRUSS_DEFAULTS, **((data or {}).get("truss") or {})}
    s = B.settings_of(data or {})
    b_ = C.basis(data or {})
    if not p["span"]:
        rooms = []
        try:
            fl = C.stacked_floors(data or {})
            rooms = fl[-1]["rooms"] if fl else []
        except Exception:                               # noqa: BLE001 - no building yet
            rooms = []
        if rooms:
            p["span"] = round(min(max(r["x"] + r["w"] for r in rooms) - min(r["x"] for r in rooms),
                                  max(r["y"] + r["d"] for r in rooms) - min(r["y"] for r in rooms)), 2)
        else:
            p["span"] = 12.0
    cosp = math.cos(math.radians(float(s.get("pitch", 20) or 20)))
    if not p["rise"]:
        p["rise"] = round(p["span"] / 2 * math.tan(math.radians(float(s.get("pitch", 20) or 20))), 2)
    if not p["dead"]:
        p["dead"] = round(C.tile_weight(s) / cosp + 10.0, 1)
    if not p["live"]:
        p["live"] = float(b_["ll_roof"])
    return p


def build(p: dict) -> Truss:
    """The truss of the params: the user's own nodes/members when kind is
    "custom", else the generated form."""
    if p.get("kind") == "custom" and p.get("nodes"):
        return custom([tuple(n) for n in p["nodes"]], [tuple(m) for m in p["members"]],
                      {int(k): v for k, v in (p.get("supports") or {}).items()})
    return make(p["kind"], p["span"], p["rise"], p["panels"], p["depth"], p["radius"])


def design_of(data) -> tuple:
    """(params, Design) of the building's truss."""
    p = params_of(data)
    t = build(p)
    from core import wanic_calc as C
    return p, design(t, p["span"], p["spacing"], p["dead"], p["live"], p["family"], C.basis(data or {})["fc"])
