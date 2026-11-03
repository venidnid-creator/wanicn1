# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
"""What one generated part costs, for the Properties panel: its main
quantity (ลบ.ม. of concrete, ตร.ม. of wall or plaster, กก. of steel, ม. of
board, ชุด of a door…), the material price per unit (the BOQ's price list —
the province's, หลักเกณฑ์ 2569 recipes), the labour per unit (ว480) and the
amounts. The rows are added to the part's info (``ext["wanic_building"]
["info"]``), so the panel shows them with the rest of the part's data.

Only the part's main work item is priced here; formwork, rebar, paint and
the like are in the full BOQ (ปร.4 / ปร.5).
"""
from __future__ import annotations

from core import wanic_building as B
from core import wanic_quantities as Q
from core import wanic_std2569 as S

STEEL_KG_M3 = 7850.0
CONCRETE_KINDS = ("footing", "stump", "column", "beam", "slab", "stair", "band")
STEEL_KINDS = ("ridge", "hip", "rafter", "purlin", "post", "valley",
               "wallplate", "tiebeam")


def _vol(g) -> float:
    from core import bim
    try:
        return abs(float(bim.face_set_volume(list(g.mesh.faces)) or 0.0))
    except Exception:                                   # noqa: BLE001
        return 0.0


def unit_rates(data) -> dict:
    """{what: (material/unit, labour/unit, unit, labour code, note)}."""
    s = B.settings_of(data)
    o = Q.options_of(data)
    prices, labour = Q.prices_of(data), Q.labour_of(data)
    n = max(B.elements(data)["n"], 1)
    conc_lab = ("1.7b" if n > 1 else "1.7a") if o["ready_mix"] else \
        ("1.6.2b" if n > 1 else "1.6.2a")
    conc_mat = prices.get(Q.CONCRETE, 0.0) if o["ready_mix"] else \
        Q.recipe_price("2.2", prices)[0]
    r = {"concrete": (conc_mat, labour.get(conc_lab, 0.0), "ลบ.ม.", conc_lab,
                      "คอนกรีต (ไม่รวมไม้แบบ เหล็กเสริม)")}
    steel = prices.get("เหล็กรูปพรรณ (ทั่วไป)", 0.0)
    r["steel"] = (steel, labour.get("1.11.1", 0.0), "กก.", "1.11.1",
                  "เหล็กรูปพรรณ (ไม่รวมสีกันสนิม)")
    for ext in (True, False):
        sp = B.wall_spec(s, ext)
        mat, _n = Q.recipe_price(sp["recipe"], prices)
        code = S.wall_labour_code(sp["recipe"])
        r[f"wall:{'ext' if ext else 'int'}"] = (mat, labour.get(code, 0.0),
                                                "ตร.ม.", code, sp["name"])
    pmat, _n = Q.recipe_price(o["plaster_recipe"], prices)
    r["plaster:ext"] = (pmat * (s.get("ext_plaster_t", 0.015) / 0.015),
                        labour.get("2.3.1.2b", 0.0), "ตร.ม.", "2.3.1.2b",
                        "ฉาบปูนผนังภายนอก")
    r["plaster:int"] = (pmat * (s.get("plaster_t", 0.015) / 0.015),
                        labour.get("2.3.1.2a", 0.0), "ตร.ม.", "2.3.1.2a",
                        "ฉาบปูนผนังภายใน")
    fk = "เชิงชายไม้สำเร็จรูป 1\"×8\" + ทับเชิงชาย 1\"×6\""
    r["board"] = (prices.get(fk, 0.0), labour.get("2.1.10a", 0.0), "ม.",
                  "2.1.10a", "เชิงชาย/ปั้นลม + ทับ ไม้สำเร็จรูป")
    smat, _n = Q.recipe_price("5.41", prices)
    r["soffit"] = (smat, labour.get("2.2.1c", 0.0), "ตร.ม.", "2.2.1c",
                   "ฝ้าชายคาระแนงไม้เทียม")
    return r


def _qty(g, kind, info) -> tuple:
    """(rate key, quantity) of a part."""
    v = _vol(g)
    if kind in CONCRETE_KINDS:
        return "concrete", v
    if kind in STEEL_KINDS:
        return "steel", v * STEEL_KG_M3
    rows = dict(info)
    if kind == "wall":
        t = B.wall_spec({**B.DEFAULT_SETTINGS}, True)["t"]
        try:
            t = float(rows.get("ความหนาเนื้อผนัง", "").split()[0]) / 100.0
        except (ValueError, IndexError):
            pass
        ext = "ภายนอก" in rows.get("ชนิด", "")
        return ("wall:ext" if ext else "wall:int"), (v / t if t else 0.0)
    if kind == "plaster":
        try:
            t = float(rows.get("ความหนา", "").split()[0]) / 100.0
        except (ValueError, IndexError):
            t = 0.015
        ext = "ภายนอก" in rows.get("ชนิด", "")
        return ("plaster:ext" if ext else "plaster:int"), (v / t if t else 0.0)
    if kind in ("fascia", "barge"):
        try:
            return "board", float(rows.get("ความยาว", "").split()[0])
        except (ValueError, IndexError):
            return "board", 0.0
    return "", 0.0


def price_rows(g, rates) -> list:
    rec = ((g.ext or {}).get(B.EXT_KEY)) or {}
    kind = rec.get("kind", "")
    key, qty = _qty(g, kind, rec.get("info") or [])
    if not key or qty <= 0 or key not in rates:
        return []
    mat, lab, unit, code, what = rates[key]
    rows = [("— ราคา —", what),
            ("ปริมาณ", f"{qty:,.3f} {unit}"),
            ("ราคาวัสดุ/หน่วย", f"{mat:,.2f} บาท/{unit}" if mat else
             "ยังไม่มีราคา (เลือกจังหวัด/ใส่ราคาใน BOQ)"),
            ("ค่าแรง/หน่วย", f"{lab:,.2f} บาท/{unit} (ว480 {S.w480_code(code)})"),
            ("ค่าวัสดุ", f"{qty * mat:,.2f} บาท"),
            ("ค่าแรง", f"{qty * lab:,.2f} บาท"),
            ("รวม", f"{qty * (mat + lab):,.2f} บาท (ยังไม่คูณ Factor F)")]
    return rows


def annotate(groups, data) -> int:
    """Add the price rows to every part that has a main work item."""
    rates = unit_rates(data)
    n = 0
    for g in groups:
        rows = price_rows(g, rates)
        if not rows:
            continue
        ext = dict(g.ext or {})
        rec = dict(ext.get(B.EXT_KEY) or {})
        rec["info"] = [r for r in (rec.get("info") or []) if r and r[0] != "— ราคา —"
                       and r[0] not in ("ปริมาณ", "ราคาวัสดุ/หน่วย", "ค่าแรง/หน่วย",
                                        "ค่าวัสดุ", "ค่าแรง", "รวม")]
        rec["info"] += [[k, v] for k, v in rows]
        ext[B.EXT_KEY] = rec
        g.ext = ext
        n += 1
    return n
