# -*- coding: utf-8 -*-
"""Command line:

    python -m wanicndesign estimate PROJECT.json -o BOQ.xlsx [--prices P.json] [--labour-up 5]
    python -m wanicndesign plan PROJECT.json -o PLAN.dxf          (DXF file)
    python -m wanicndesign plan PROJECT.json --autocad            (draw in running AutoCAD)
    python -m wanicndesign labour [--set CODE RATE]               (show or update ค่าแรง)
    python -m wanicndesign prices PROJECT.json -o prices.json     (price list to fill in)
    python -m wanicndesign design BUILDING.json -o OUTDIR          (model → structure → ราคากลาง)
    python -m wanicndesign province BUILDING.json จังหวัด ตาราง.xlsx  (ราคาวัสดุพาณิชย์จังหวัด)
    python -m wanicndesign contract A.json B.json --name "โครงการ" -o OUT.xlsx  (หลายอาคาร สัญญาเดียว)
"""
from __future__ import annotations

import argparse
import os
import sys

from .model import Project
from .rates import DATA_DIR, Rates

from .rates import override_path

OVERRIDE = override_path()


def _rates(args) -> Rates:
    prices = Rates.load_prices(args.prices) if getattr(args, "prices", None) else {}
    r = Rates(override_file=OVERRIDE, prices=prices)
    if getattr(args, "labour_up", None):
        r.scale_labour(args.labour_up)
    return r


def cmd_estimate(args) -> int:
    from .estimate import estimate
    est = estimate(Project.load(args.project), _rates(args))
    out = args.output or os.path.splitext(args.project)[0] + "-BOQ.xlsx"
    est.to_csv(out[:-5] + ".csv") if out.endswith(".xlsx") else None
    (est.to_xlsx if out.endswith(".xlsx") else est.to_csv)(out)
    print(f"รายการ {len(est.rows)} บรรทัด  ค่าวัสดุ {est.material_total:,.2f}  "
          f"ค่าแรง {est.labour_total:,.2f}  รวม {est.total:,.2f} บาท")
    print(f"บันทึก {out}")
    return 0


def cmd_plan(args) -> int:
    from .cad.base import draw_grid
    project = Project.load(args.project)
    if args.autocad:
        from .cad.acad_backend import AcadBackend
        b = AcadBackend()
    else:
        from .cad.dxf_backend import DxfBackend
        out = args.output or os.path.splitext(args.project)[0] + "-plan.dxf"
        b = DxfBackend(out)
    draw_grid(project, b)
    b.finish()
    print("วาดกริดและร่างเสาเรียบร้อย" + ("" if args.autocad else f" → {b.path}"))
    return 0


def cmd_prices(args) -> int:
    import json
    from .quantities import takeoff
    out = args.output or "prices.json"
    current = Rates.load_prices(out) if os.path.exists(out) else {}
    from .estimate import Estimate
    rates = Rates()
    keys = Estimate("", takeoff(Project.load(args.project), rates), rates).needed_materials()
    data = {k: current.get(k, 0) for k in keys}
    data.update({k: v for k, v in current.items() if k not in data})
    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print(f"บันทึกรายการราคาวัสดุ {len(data)} รายการ → {out} (กรอกราคาต่อหน่วยแล้วใช้ --prices)")
    return 0


def cmd_province(args) -> int:
    """Read the commerce office's price table into the province's price book."""
    from . import province as P
    from .estimate import Estimate
    from .quantities import takeoff
    from .structure.building import Building
    from .structure.design import design
    from .structure.to_project import to_project
    if args.province not in P.PROVINCES:
        print(f"ไม่รู้จักจังหวัด {args.province}")
        return 2
    b = Building.load(args.building)
    rates = Rates()
    need = Estimate("", takeoff(to_project(design(b)), rates), rates).needed_materials()
    rows, month = P.read_table(args.file)
    found = P.match(rows, list(need), need)
    old = P.load_book(args.province) or {"prices": {}, "src": {}, "item": {}}
    prices = {**old["prices"], **{k: v for k, (v, _n) in found.items()}}
    src = {**old.get("src", {}), **{k: "พาณิชย์" for k in found}}
    item = {**old.get("item", {}), **{k: n for k, (_v, n) in found.items()}}
    P.save_book(args.province, prices, args.month or month, src=src, item=item)
    have, missing = P.coverage(prices, need)
    print(f"อ่านตาราง {len(rows)} รายการ ({month or 'ไม่ระบุเดือน'}) จับคู่ได้ {len(found)} รายการ; "
          f"มีราคา {have}/{len(need)} วัสดุ → {P.book_dir()}")
    for k in missing:
        print(f"  ยังไม่มีราคา: {k} ({need[k]})")
    return 0


def cmd_design(args) -> int:
    from .estimate import for_design
    from .structure.building import Building
    from .structure.design import design
    from .structure.drawing import write_dxf
    from .structure.report import write_report
    from .structure.to_project import to_project
    building = Building.load(args.building)
    out = args.output or os.path.splitext(args.building)[0] + "-out"
    os.makedirs(out, exist_ok=True)
    res = design(building)
    write_report(res, os.path.join(out, "รายการคำนวณ.xlsx"))
    write_dxf(res, os.path.join(out, "แบบโครงสร้าง.dxf"))
    from .structure.sheets import write_sheets_dxf, write_sheets_pdf
    write_sheets_dxf(res, os.path.join(out, "แบบก่อสร้าง.dxf"))
    write_sheets_pdf(res, os.path.join(out, "แบบก่อสร้าง.pdf"))
    from .structure.cutting import write_cutting_xlsx
    _items, plans = write_cutting_xlsx(res, os.path.join(out, "ตารางตัดเหล็ก.xlsx"))
    print("เหล็กเส้น 10 ม.: " + ", ".join(f"{p.size} {p.bars} เส้น (เศษ {p.waste_pct:.1f}%)" for p in plans))
    project = to_project(res)
    project.save(os.path.join(out, "ปริมาณ-โครงการ.json"))
    est = for_design(res, _rates(args))
    est.to_xlsx(os.path.join(out, "ราคากลาง-ปร.xlsx"))
    print(f"หลังคา {res.roof.load_plan:.0f} กก./ตร.ม. แป {res.roof.purlin.section} "
          f"จันทัน {res.roof.rafter.section}" if res.roof else "ไม่มีหลังคา")
    print(f"พื้น {len(res.slabs)} แผ่น  คาน {len(res.beams)} ช่วง  เสา {len(res.columns)} ท่อน  "
          f"ฐานราก {len(res.footings)} ฐาน  เสาเข็มรวม {res.total_piles()} ต้น")
    print("ผลรวม: " + ("ผ่านทุกรายการ" if res.ok else "มีรายการไม่ผ่าน"))
    for w in res.warnings:
        print("  ⚠ " + w)
    print(f"ค่าวัสดุ {est.material_total:,.2f}  ค่าแรง {est.labour_total:,.2f}  ค่างานต้นทุน {est.total:,.2f}  "
          f"Factor F {est.factor:.4f}  ราคากลาง {est.grand:,.2f} บาท")
    if est.missing_prices():
        print(f"  วัสดุที่ยังไม่มีราคา {len(est.missing_prices())} รายการ (ดูแผ่น ราคาวัสดุ)")
    print(f"บันทึกผลใน {out}")
    return 0


def cmd_contract(args) -> int:
    """Several buildings in one contract: Factor F from the cost of the whole contract (ข้อ 9.3 ข้อ 3)."""
    from .estimate import contract_for_designs
    from .structure.building import Building
    from .structure.design import design
    results = [design(Building.load(p)) for p in args.buildings]
    con = contract_for_designs(args.name, results, _rates(args) if args.prices else None)
    out = args.output or "ราคากลาง-สัญญา.xlsx"
    con.to_xlsx(out)
    for label, est in con.items:
        print(f"  {label}: ค่างานต้นทุน {est.total:,.2f} × F {est.factor:.4f} = {est.construction:,.2f}")
    print(f"รวม {len(con.items)} อาคาร ค่างานต้นทุน {con.total:,.2f}  Factor F {con.factor:.4f}  "
          f"ราคากลาง {con.grand:,.2f} บาท → {out}")
    return 0


def cmd_labour(args) -> int:
    r = Rates(override_file=OVERRIDE)
    if args.set:
        code, rate = args.set
        r.set_labour(code, float(rate))
        print(f"อัปเดต {code} = {float(rate):,.2f} บาท (บันทึกใน {OVERRIDE})")
        return 0
    print(r.source)
    for code, it in r.labour.items():
        print(f"{code:10} {it['rate']:>8,.2f}  {it['unit']:6} {it['name']}")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="wanicndesign")
    sub = p.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("estimate", help="ถอดปริมาณและประมาณราคา")
    e.add_argument("project")
    e.add_argument("-o", "--output")
    e.add_argument("--prices", help="ไฟล์ JSON ราคาวัสดุ {รายการ: ราคาต่อหน่วย}")
    e.add_argument("--labour-up", type=float, help="ปรับค่าแรงทุกรายการเป็นร้อยละ")
    e.set_defaults(func=cmd_estimate)
    pl = sub.add_parser("plan", help="วาดกริดและร่างเสา")
    pl.add_argument("project")
    pl.add_argument("-o", "--output")
    pl.add_argument("--autocad", action="store_true", help="วาดใน AutoCAD ที่เปิดอยู่")
    pl.set_defaults(func=cmd_plan)
    pr = sub.add_parser("prices", help="สร้างไฟล์ราคาวัสดุให้กรอก")
    pr.add_argument("project")
    pr.add_argument("-o", "--output")
    pr.set_defaults(func=cmd_prices)
    d = sub.add_parser("design", help="คำนวณโครงสร้างจากโมเดล แล้วทำ BOQ")
    d.add_argument("building")
    d.add_argument("-o", "--output")
    d.add_argument("--prices")
    d.add_argument("--labour-up", type=float)
    d.set_defaults(func=cmd_design)
    pv = sub.add_parser("province", help="นำเข้าตารางราคาวัสดุของสำนักงานพาณิชย์จังหวัด (.xlsx/.csv)")
    pv.add_argument("building")
    pv.add_argument("province")
    pv.add_argument("file")
    pv.add_argument("--month", help="เดือนของราคา เช่น \"ต.ค. 2569\"")
    pv.set_defaults(func=cmd_province)
    ct = sub.add_parser("contract", help="ราคากลางหลายอาคารในสัญญาเดียว (Factor F จากค่างานรวม)")
    ct.add_argument("buildings", nargs="+")
    ct.add_argument("--name", default="โครงการก่อสร้าง")
    ct.add_argument("-o", "--output")
    ct.add_argument("--prices")
    ct.add_argument("--labour-up", type=float)
    ct.set_defaults(func=cmd_contract)
    lb = sub.add_parser("labour", help="ดูหรืออัปเดตค่าแรง ว480")
    lb.add_argument("--set", nargs=2, metavar=("CODE", "RATE"))
    lb.set_defaults(func=cmd_labour)
    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
