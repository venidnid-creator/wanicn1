# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
"""ประมาณราคางานเอกชน — the same measured quantities as the government BOQ
(:mod:`core.wanic_quantities`), priced the private way:

- eight categories: 1 งานเตรียมการ · 2 งานโครงสร้าง · 3 งานสถาปัตยกรรม ·
  4 งานระบบสุขาภิบาล · 5 งานระบบไฟฟ้า · 6 งานระบบปรับอากาศ ·
  7 งานภายนอกอาคาร · 8 งานอื่นๆ;
- the waste (เผื่อเสีย) the contractor's own, by kind — RB, DB12–16, DB20,
  DB25+, concrete, roofing, structural steel — each editable;
- the steel designed in the structure windows (Truss, WF/H, purlins) added
  by weight when they are set;
- each line's unit prices editable (kept by its description);
- no Factor F: overhead and profit (ค่าดำเนินการและกำไร) as a percentage
  of the direct cost, then VAT 7 %."""
from __future__ import annotations

import math
from pathlib import Path

CATS = [(1, "งานเตรียมการ"), (2, "งานโครงสร้าง"), (3, "งานสถาปัตยกรรม"), (4, "งานระบบสุขาภิบาล"),
        (5, "งานระบบไฟฟ้า"), (6, "งานระบบปรับอากาศ"), (7, "งานภายนอกอาคาร"), (8, "งานอื่นๆ")]
CAT_TH = dict(CATS)
GROUP_CAT = {"prep": 1, "earth": 2, "column": 2, "beam": 2, "slab": 2, "stair": 2, "rebar": 2,
             "wall": 3, "opening": 3, "finish": 3, "roof": 3, "sanitary": 4, "plumbing": 4,
             "electric": 5, "hvac": 6, "external": 7, "misc": 8}

#: the contractor's waste by kind (%), editable
WASTE = {"RB": 8.0, "DB12-16": 10.0, "DB20": 11.0, "DB25+": 12.0, "concrete": 3.0, "roofing": 5.0,
         "steel": 5.0}
WASTE_TH = {"RB": "เหล็กกลม RB", "DB12-16": "เหล็กข้ออ้อย DB12–DB16", "DB20": "เหล็กข้ออ้อย DB20",
            "DB25+": "เหล็กข้ออ้อย DB25 ขึ้นไป", "concrete": "คอนกรีต", "roofing": "วัสดุมุงหลังคา",
            "steel": "เหล็กรูปพรรณ / โครงหลังคาเหล็ก"}

DEFAULTS = {"overhead": 5.0, "vat": True, "waste": {}, "prices": {}, "steel_price": 0.0, "steel_lab": 0.0}


def settings(data) -> dict:
    p = {**DEFAULTS, **((data or {}).get("private_est") or {})}
    p["waste"] = {**WASTE, **(p.get("waste") or {})}
    return p


def waste_kind(ln: dict) -> str:
    d = ln["desc"]
    if d.startswith("เหล็กเสริม"):
        size = d.replace("เหล็กเสริม", "").strip().split()[0] if d.replace("เหล็กเสริม", "").strip() else ""
        if size.startswith("RB"):
            return "RB"
        try:
            n = int("".join(ch for ch in size[2:] if ch.isdigit()))
        except ValueError:
            return ""
        return "DB12-16" if n <= 16 else "DB20" if n <= 20 else "DB25+"
    if "คอนกรีต" in d and ln["unit"] == "ลบ.ม.":
        return "concrete"
    if ln["group"] == "roof" and ("กระเบื้อง" in d or "เมทัลชีท" in d or "แผ่น" in ln["unit"]):
        return "roofing" if ln.get("waste") else ""
    if "โครงหลังคาเหล็ก" in d and ln["unit"] == "กก.":
        return "steel"
    return ""


def _cat_of(ln) -> int:
    if ln["group"] == "roof" and "โครงหลังคา" in ln["desc"]:
        return 2
    return GROUP_CAT.get(ln["group"], 8)


def steel_lines(data, st) -> list:
    """The designed steel (Truss, WF/H beams and columns, purlins) by weight."""
    out = []
    d = data or {}
    if "truss" in d:
        try:
            from core import wanic_truss as T
            from core import wanic_lateral as L
            p, des = T.design_of(d)
            Lx, Ly = L.plan_size(d)
            length = max(Lx, Ly)
            n = max(2, int(math.floor(length / max(p["spacing"], 0.5))) + 1)
            out.append({"desc": f"โครง Truss เหล็ก ({T.TYPES.get(p['kind'], p['kind'])}) {n} โครง × {des.weight:,.1f} กก.",
                        "net": des.weight * n, "unit": "กก.", "kind": "steel"})
        except Exception:                                    # noqa: BLE001 - not designable: left out
            pass
    if "steel" in d:
        try:
            from core import wanic_steel as S
            res = S.design_building(d)
            if res["weight"]:
                out.append({"desc": f"เหล็กรูปพรรณ เสา H / คาน WF ({len(res['columns'])} เสา · {len(res['beams'])} แนวคาน)",
                            "net": res["weight"], "unit": "กก.", "kind": "steel"})
                plates = [c["plate"] for c in res["columns"] if c.get("plate")]
                if plates:
                    kg = sum(pl["N"] * pl["B"] * pl["t"] / 10 * 7.85 / 1000 for pl in plates)
                    out.append({"desc": f"แผ่นเหล็กรองฐาน {len(plates)} แผ่น", "net": kg, "unit": "กก.", "kind": "steel"})
        except Exception:                                    # noqa: BLE001
            pass
    if "purlin" in d:
        try:
            from core import wanic_purlin as PU
            from core import wanic_lateral as L
            p, res = PU.design_of(d)
            Lx, Ly = L.plan_size(d)
            length = max(Lx, Ly)
            sec = res["purlin"][0]
            kg = res["n_purlins"] * 2 * length * sec.kg_m
            out.append({"desc": f"แปเหล็ก {sec.label} {res['n_purlins']} แถว/ข้าง × 2 ข้าง", "net": kg, "unit": "กก.",
                        "kind": "steel"})
        except Exception:                                    # noqa: BLE001
            pass
    return out


def compute(data) -> dict:
    """{"cats": [(no, name, [line])], "direct", "overhead", "vat", "total", "settings"}."""
    from core import wanic_quantities as Q
    st = settings(data)
    base = Q.compute(data)
    lines = []
    for ln in base["lines"]:
        kind = waste_kind(ln)
        w = float(st["waste"].get(kind, ln["waste"])) if kind else float(ln["waste"])
        qty = round(ln["net"] * (1 + w / 100.0), 2)
        pr = (st["prices"] or {}).get(ln["desc"]) or {}
        mat = float(pr.get("mat", ln["mat"]))
        lab = float(pr.get("lab", ln["lab"]))
        lines.append({"cat": _cat_of(ln), "desc": ln["desc"], "net": ln["net"], "waste": w, "kind": kind,
                      "qty": qty, "unit": ln["unit"], "mat": mat, "lab": lab,
                      "mat_total": round(qty * mat, 2), "lab_total": round(qty * lab, 2)})
    for sl in steel_lines(data, st):
        w = float(st["waste"]["steel"])
        qty = round(sl["net"] * (1 + w / 100.0), 2)
        pr = (st["prices"] or {}).get(sl["desc"]) or {}
        mat = float(pr.get("mat", st["steel_price"]))
        lab = float(pr.get("lab", st["steel_lab"]))
        lines.append({"cat": 2, "desc": sl["desc"], "net": sl["net"], "waste": w, "kind": "steel", "qty": qty,
                      "unit": sl["unit"], "mat": mat, "lab": lab, "mat_total": round(qty * mat, 2),
                      "lab_total": round(qty * lab, 2)})
    for ln in lines:
        ln["total"] = round(ln["mat_total"] + ln["lab_total"], 2)
    cats = [(no, th, [ln for ln in lines if ln["cat"] == no]) for no, th in CATS]
    direct = round(sum(ln["total"] for ln in lines), 2)
    over = round(direct * float(st["overhead"]) / 100.0, 2)
    vat = round((direct + over) * 0.07, 2) if st["vat"] else 0.0
    return {"cats": cats, "lines": lines, "direct": direct, "overhead": over, "vat": vat,
            "total": round(direct + over + vat, 2), "settings": st, "province": base.get("province", "")}


def save_xlsx(result, path, info: dict) -> None:
    """Two sheets: the summary of the eight categories, and the bill."""
    from core.wanic_takeoff import _Sheet, _xlsx, baht_text
    st = result["settings"]
    s1 = _Sheet("สรุปราคา 8 หมวด", landscape=False)
    s1.widths = [8, 50, 20, 20, 22]
    s1.add(["ใบสรุปประมาณราคางานก่อสร้าง (งานเอกชน)"], style=2)
    s1.merges.append("A1:E1")
    for lab in ("project", "owner", "place"):
        th = {"project": "โครงการ", "owner": "เจ้าของ", "place": "สถานที่"}[lab]
        s1.add([f"{th} : {info.get(lab, '')}"], style=0)
    s1.add([])
    s1.add(["ลำดับ", "รายการ", "ค่าวัสดุ (บาท)", "ค่าแรง (บาท)", "รวม (บาท)"], style=3)
    for no, th, rows in result["cats"]:
        m = sum(r["mat_total"] for r in rows)
        lb = sum(r["lab_total"] for r in rows)
        s1.add([no, th, round(m, 2), round(lb, 2), round(m + lb, 2)], styles=[8, 4, 5, 5, 5])
    s1.add(["", "รวมค่าก่อสร้าง (ค่างานต้นทุน)", "", "", result["direct"]], styles=[6, 6, 6, 6, 7])
    s1.add(["", f"ค่าดำเนินการและกำไร {st['overhead']:g}%", "", "", result["overhead"]], styles=[6, 6, 6, 6, 7])
    if st["vat"]:
        s1.add(["", "ภาษีมูลค่าเพิ่ม 7%", "", "", result["vat"]], styles=[6, 6, 6, 6, 7])
    s1.add(["", "รวมราคาทั้งสิ้น", "", "", result["total"]], styles=[6, 6, 6, 6, 7])
    s1.add(["", f"({baht_text(result['total'])})"], style=1)
    s1.add([])
    s1.add(["", "เผื่อเสีย: " + " · ".join(f"{WASTE_TH[k]} {v:g}%" for k, v in st["waste"].items())], style=0)
    s1.add([])
    s1.add(["", "", "", "ผู้ประมาณราคา", info.get("engineer", "")], style=0)
    s1.add(["", "", "", "", info.get("qualification", "")], style=0)
    s2 = _Sheet("รายการประมาณราคา", landscape=True)
    s2.widths = [8, 60, 12, 10, 12, 8, 14, 16, 14, 16, 18]
    s2.add(["ลำดับ", "รายการ", "ปริมาณสุทธิ", "เผื่อ %", "ปริมาณ", "หน่วย", "ค่าวัสดุ/หน่วย", "ค่าวัสดุ",
            "ค่าแรง/หน่วย", "ค่าแรง", "รวม (บาท)"], style=3)
    for no, th, rows in result["cats"]:
        if not rows:
            continue
        s2.add([str(no), th], styles=[6, 6])
        for i, r in enumerate(rows, 1):
            s2.add([f"{no}.{i}", r["desc"], round(r["net"], 2), r["waste"], r["qty"], r["unit"], r["mat"],
                    r["mat_total"], r["lab"], r["lab_total"], r["total"]],
                   styles=[8, 4, 5, 5, 5, 8, 5, 5, 5, 5, 5])
        s2.add(["", f"รวม{th}", "", "", "", "", "", round(sum(r["mat_total"] for r in rows), 2), "",
                round(sum(r["lab_total"] for r in rows), 2), round(sum(r["total"] for r in rows), 2)],
               styles=[6, 6, 6, 6, 6, 6, 6, 7, 6, 7, 7])
    Path(path).write_bytes(_xlsx([s1, s2]))
