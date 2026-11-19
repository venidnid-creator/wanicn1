# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2569 (2026) นายเวนิช ธัมมะวงษ์ วิศวกรสำรวจ — ReadWanicn2027
"""The take-off as the Comptroller General's forms (หลักเกณฑ์การคำนวณราคากลางงานก่อสร้าง พ.ศ. 2569),
ready to print on A4:

    ปร.4      แบบสรุปราคากลางงานก่อสร้าง
    ปร.1 (ก)  แบบสรุปค่าก่อสร้าง ค่างานต้นทุน (× Factor F)
    ปร.1      แบบแสดงรายการ ปริมาณงาน และราคา ค่างานต้นทุน
    ปร.2      แบบแสดงรายการ ปริมาณงาน และราคา ค่าครุภัณฑ์จัดซื้อ (ถ้ามี)
    ปร.3      แบบแสดงรายการ ปริมาณงาน และราคา ค่าใช้จ่ายพิเศษตามข้อกำหนด (ถ้ามี)

Quantities come from the bill printed in the set; where the set is only drawings, the lines the
drawings name (doors, windows … counted from their tags) are listed, and the groups of work are
laid out for the quantities measured with the take-off tools. Prices left blank are to be filled."""
from __future__ import annotations

import datetime as dt
import re
from collections import defaultdict
from pathlib import Path

from . import procure as P
from . import procure_report as R
from .procure_report import C, N, Q, Para, Report, Table

DOTS = "................................................"
VAT = 7.0
#: the groups of a building bill, for a set of drawings without one
BUILDING_GROUPS = ("หมวดงานโครงสร้าง", "หมวดงานสถาปัตยกรรม", "หมวดงานระบบสุขาภิบาล", "หมวดงานระบบไฟฟ้า",
                   "หมวดงานอื่น ๆ")
TAG_GROUP = {"ป": 1, "น": 1, "D": 1, "W": 1, "DW": 1, "พ": 1, "ผ": 1, "ฝ": 1}


def _head(rep: Report, code: str, title: str, info: dict, attach: str = ""):
    rep.p(f"แบบ {code}", align="right", bold=True, size=11)
    rep.p(title, align="center", bold=True, size=14)
    for line in (f"ชื่อโครงการงานก่อสร้าง  {info.get('project') or DOTS}",
                 f"สถานที่ก่อสร้าง  {info.get('place') or DOTS}",
                 f"แบบเลขที่  {info.get('drawing_no') or DOTS}",
                 f"หน่วยงานเจ้าของโครงการงานก่อสร้าง  {info.get('owner') or DOTS}",
                 attach,
                 f"คำนวณราคากลาง เมื่อวันที่  {info.get('date') or P.thai_date(dt.date.today().isoformat())}"):
        if line:
            rep.p(line, size=11)


def _sign(rep: Report, info: dict):
    """(ลงชื่อ) …… ตำแหน่ง — the dotted lines one under the other, the names centred under them."""
    rows = []
    people = [("ประธานกรรมการกำหนดราคากลาง", ""), ("กรรมการกำหนดราคากลาง", ""), ("กรรมการกำหนดราคากลาง", ""),
              ("ผู้ถอดแบบและคำนวณราคา", info.get("preparer") or "")]
    for role, name in people:
        rows += [[C(""), C("(ลงชื่อ)", align="right"), C(DOTS[:36], align="center"), C(role)],
                 [C(""), C(""), C(f"( {name or DOTS[:34]} )", align="center"), C("")]]
    rep.p(" ", size=6)
    rep.blocks.append(Table([], rows, [22, 10, 36, 32], 10.5, border=0))


def _kind(ln) -> str:
    t = f"{ln.group} {ln.section} {ln.name}"
    if "ค่าใช้จ่ายพิเศษ" in t:
        return "special"
    if "ครุภัณฑ์" in t:
        return "equip"
    return "work"


def _amounts(ln):
    mat = ln.mat if ln.mat is not None else (ln.qty * ln.mat_u if ln.qty and ln.mat_u else None)
    lab = ln.lab if ln.lab is not None else (ln.qty * ln.lab_u if ln.qty and ln.lab_u else None)
    tot = ln.total if ln.total is not None else ((mat or 0) + (lab or 0) if (mat or lab) else None)
    return mat, lab, tot


def tag_lines(res, work: str = "อาคาร") -> list:
    """Lines from the tags counted on the drawings (doors, windows, finishes …)."""
    from .boqread import Line, tag_meaning
    out = []
    for tag in sorted(res.tags, key=lambda t: (t.rstrip("0123456789"), int(re.sub(r"\D", "", t) or 0))):
        n = sum(res.tags[tag].values())
        what = tag_meaning(tag) or "ป้ายในแบบ"
        unit = "ชุด" if what in ("ประตู", "หน้าต่าง", "ประตู-หน้าต่าง") else "จุด"
        pages = ", ".join(str(p) for p in sorted(res.tags[tag]))
        out.append(Line(work=work, bill="", group="รายการที่นับจากป้ายในแบบ (ตรวจกับแบบอีกครั้ง)", section="",
                        name=f"{what} {tag}", qty=float(n), unit=unit, page=min(res.tags[tag]), sure=False,
                        note=f"นับจากป้ายหน้า {pages}"))
    return out


def forms(res, info: dict, lines: list | None = None) -> list:
    """The reports ปร.4, ปร.1 (ก), ปร.1, ปร.2, ปร.3 of one bill."""
    lines = list(res.lines if lines is None else lines)
    F = float(info.get("factor") or 0.0)
    kinds = defaultdict(list)
    for ln in lines:
        kinds[_kind(ln)].append(ln)
    work = kinds["work"]
    drawings_only = not lines
    if drawings_only:
        work = tag_lines(res)

    # ปร.1
    pr1 = Report("ปร.1", landscape=True)
    _head(pr1, "ปร.1", "แบบแสดงรายการ ปริมาณงาน และราคา ค่างานต้นทุน", info)
    head = [[C("ลำดับที่", align="center", rowspan=2), C("รายการ", align="center", rowspan=2),
             C("จำนวน", align="center", rowspan=2), C("หน่วย", align="center", rowspan=2),
             C("ค่าวัสดุ", align="center", colspan=2), C("ค่าแรงงาน", align="center", colspan=2),
             C("รวมค่าวัสดุและค่าแรงงาน", align="center", rowspan=2), C("หมายเหตุ", align="center", rowspan=2)],
            [C("ราคาต่อหน่วย", align="center"), C("จำนวนเงิน", align="center"),
             C("ราคาต่อหน่วย", align="center"), C("จำนวนเงิน", align="center")]]
    body, groups = [], []
    order = []
    by_group = defaultdict(list)
    for ln in work:
        g = ln.group or "รายการ"
        if g not in by_group:
            order.append(g)
        by_group[g].append(ln)
    if drawings_only:                          # the groups to fill from the take-off tools
        for g in BUILDING_GROUPS:
            if g not in by_group:
                order.append(g)
                by_group[g] = []
    grand_m = grand_l = grand_t = 0.0
    for gi, g in enumerate(order, 1):
        body.append([C(gi, align="center", bold=True), C(g, bold=True)] + [C("")] * 8)
        sm = sl = st = 0.0
        sec, k, n_in = None, 0, 0
        for ln in by_group[g]:
            if ln.section and ln.section != sec:
                sec = ln.section
                k += 1
                n_in = 0
                body.append([C(f"{gi}.{k}", align="center"), C(re.sub(r"^\d+(\.\d+)+\s*", "", sec), bold=True)]
                            + [C("")] * 8)
            if sec:
                n_in += 1
                code = f"{gi}.{k}.{n_in}"
            else:
                k += 1
                code = f"{gi}.{k}"
            mat, lab, tot = _amounts(ln)
            sm += mat or 0
            sl += lab or 0
            st += tot or 0
            note = ln.note or (f"หน้า {ln.page}" if ln.page else "")
            body.append([C(code, align="center"), C(ln.name, indent=1), Q(ln.qty) if ln.qty else C(""),
                         C(ln.unit, align="center"), N(ln.mat_u), N(mat), N(ln.lab_u), N(lab), N(tot),
                         C(note, size=8)])
        if not by_group[g]:
            body.append([C(""), C("(ถอดปริมาณด้วยเครื่องมือวัด/รูปทรง แล้วกรอกรายการ)", indent=1)] + [C("")] * 8)
        body.append([C(""), C(f"รวม{g}", bold=True, align="right"), C(""), C(""), C(""), N(sm or None, bold=True),
                     C(""), N(sl or None, bold=True), N(st or None, bold=True), C("")])
        groups.append((g, st))
        grand_m, grand_l, grand_t = grand_m + sm, grand_l + sl, grand_t + st
    body.append([C(""), C("รวมค่างานต้นทุน", bold=True, align="right"), C(""), C(""), C(""),
                 N(grand_m or None, bold=True, bg=R.GREY), C(""), N(grand_l or None, bold=True, bg=R.GREY),
                 N(grand_t or None, bold=True, bg=R.GREY), C("")])
    pr1.blocks.append(Table(head, body, [6, 36, 7, 6, 8, 10, 8, 10, 11, 9], 9))
    if drawings_only:
        pr1.p("หมายเหตุ  ชุดแบบนี้ไม่มีตาราง BOQ — รายการที่นับจากป้ายในแบบมาจากข้อความในแบบ ตรวจกับแบบอีกครั้ง "
              "ส่วนความยาว พื้นที่ ปริมาตร ให้ถอดด้วยเครื่องมือวัด/รูปทรงของโปรแกรม แล้วกรอกในตารางคำนวณนี้", size=10)
    _sign(pr1, info)

    # ปร.1 (ก)
    pr1k = Report("ปร.1 (ก)")
    _head(pr1k, "ปร.1 (ก)", "แบบสรุปค่าก่อสร้าง ค่างานต้นทุน", info, "แบบ ปร.1 ที่แนบ")
    rows = [[C(i, align="center"), C(g), N(t or None), Q(F, 4, align="center") if F else C(""),
             N(t * F if F and t else None), C("")] for i, (g, t) in enumerate(groups, 1)]
    after_f = grand_t * F if F else 0.0
    rows.append([C(""), C("รวมค่าก่อสร้าง", bold=True, align="right"), N(grand_t or None, bold=True), C(""),
                 N(after_f or None, bold=True, bg=R.GREY), C("")])
    pr1k.blocks.append(Table([[C("ลำดับที่", align="center"), C("รายการ", align="center"),
                               C("ค่างานต้นทุน", align="center"), C("Factor F", align="center"),
                               C("ค่าก่อสร้าง", align="center"), C("หมายเหตุ", align="center")]],
                             rows, [8, 40, 16, 11, 16, 9], 10))
    pr1k.p(f"Factor F  {F:.4f}" if F else "Factor F  ........ (กรอกตามตาราง Factor F ของกรมบัญชีกลาง)", size=11)
    _sign(pr1k, info)

    # ปร.2 ครุภัณฑ์
    eq = kinds["equip"]
    pr2 = Report("ปร.2", landscape=True)
    _head(pr2, "ปร.2", "แบบแสดงรายการ ปริมาณงาน และราคา ค่าครุภัณฑ์จัดซื้อ", info)
    rows, eq_tot = [], 0.0
    for i, ln in enumerate(eq, 1):
        mat, lab, tot = _amounts(ln)
        eq_tot += tot or 0
        rows.append([C(i, align="center"), C(ln.name), Q(ln.qty) if ln.qty else C(""), C(ln.unit, align="center"),
                     N(ln.mat_u), N(mat), N(ln.lab_u), N(lab), N(tot), C("")])
    if not rows:
        rows.append([C(""), C("(ไม่มีรายการ)")] + [C("")] * 8)
    rows.append([C(""), C("รวม", bold=True, align="right")] + [C("")] * 6 + [N(eq_tot or None, bold=True), C("")])
    pr2.blocks.append(Table([[C("ลำดับที่", align="center", rowspan=2), C("รายการ", align="center", rowspan=2),
                              C("จำนวน", align="center", rowspan=2), C("หน่วย", align="center", rowspan=2),
                              C("ค่าครุภัณฑ์", align="center", colspan=2), C("ค่าติดตั้ง", align="center", colspan=2),
                              C("รวมค่าครุภัณฑ์", align="center", rowspan=2), C("หมายเหตุ", align="center", rowspan=2)],
                             [C("ราคาต่อหน่วย", align="center"), C("จำนวนเงิน", align="center"),
                              C("ราคาต่อหน่วย", align="center"), C("จำนวนเงิน", align="center")]],
                            rows, [6, 36, 7, 6, 8, 10, 8, 10, 11, 9], 9))
    _sign(pr2, info)

    # ปร.3 ค่าใช้จ่ายพิเศษ
    sp = kinds["special"]
    pr3 = Report("ปร.3")
    _head(pr3, "ปร.3", "แบบแสดงรายการ ปริมาณงาน และราคา ค่าใช้จ่ายพิเศษตามข้อกำหนด", info)
    rows, sp_tot = [], 0.0
    for i, ln in enumerate(sp, 1):
        _m, _l, tot = _amounts(ln)
        sp_tot += tot or 0
        rows.append([C(i, align="center"), C(ln.name), C(f"{P.money(ln.qty) if ln.qty else ''} {ln.unit}".strip()),
                     N(tot), C("")])
    if not rows:
        rows.append([C(""), C("(ไม่มีรายการ)"), C(""), C(""), C("")])
    rows.append([C(""), C("รวมค่าใช้จ่ายพิเศษตามข้อกำหนดทุกรายการ", bold=True, align="right"), C(""),
                 N(sp_tot or None, bold=True), C("")])
    pr3.blocks.append(Table([[C("ลำดับที่", align="center"), C("รายการ", align="center"),
                              C("จำนวนหน่วย", align="center"), C("ค่าใช้จ่ายรวม", align="center"),
                              C("หมายเหตุ", align="center")]], rows, [8, 50, 14, 16, 12], 10))
    _sign(pr3, info)

    # ปร.4 สรุปราคากลาง
    vat = VAT / 100
    pr4 = Report("ปร.4")
    _head(pr4, "ปร.4", f"แบบสรุปราคากลางงานก่อสร้าง{work_name(lines, res)}", info,
          "แบบ ปร.1 (ก) ปร.2 และ ปร.3 (ถ้ามี) ที่แนบ")
    eq_v, sp_v = eq_tot * (1 + vat), sp_tot * (1 + vat)
    grand = after_f + eq_v + sp_v
    rows = [[C(1, align="center"), C("ค่างานต้นทุน × Factor F (ตามแบบ ปร.1 (ก))"), N(after_f or None),
             C(f"Factor F {F:.4f}" if F else "ยังไม่กรอก Factor F")],
            [C(2, align="center"), C("ค่าครุภัณฑ์จัดซื้อ (ตามแบบ ปร.2)"), N(eq_v or None), C("รวมภาษีมูลค่าเพิ่ม")],
            [C(3, align="center"), C("ค่าใช้จ่ายพิเศษตามข้อกำหนด (ถ้ามี) (ตามแบบ ปร.3)"), N(sp_v or None),
             C("รวมภาษีมูลค่าเพิ่ม")],
            [C(""), C("รวมค่าก่อสร้างทั้งโครงการงานก่อสร้าง", bold=True, align="right"), N(grand or None, bold=True),
             C("")],
            [C(""), C("ราคากลาง", bold=True, align="right"), N(grand or None, bold=True, bg=R.GREY), C("")]]
    pr4.blocks.append(Table([[C("ลำดับที่", align="center"), C("รายการ", align="center"),
                              C("ค่าก่อสร้าง", align="center"), C("หมายเหตุ", align="center")]],
                            rows, [10, 52, 20, 18], 10.5))
    pr4.p(f"ราคากลาง (ตัวอักษร)  ({P.baht_text(grand)})" if grand else
          "ราคากลาง (ตัวอักษร)  (" + DOTS + ")", size=11)
    _sign(pr4, info)
    return [pr4, pr1k, pr1, pr2, pr3]


def work_name(lines, res) -> str:
    w = next((ln.work for ln in lines if ln.work), "") or next((p.work for p in res.pages if p.work), "")
    return {"อาคาร": "อาคาร", "ทาง": "ทาง", "ชลประทาน": "ชลประทาน"}.get(w, "")


def safe(s: str) -> str:
    s = re.sub(r'[\\/:*?"<>|]+', " ", s or "")
    return " ".join(s.split())[:60] or "งาน"


def write(res, folder, info: dict, pdf: bool = True, family: str = "Laksaman") -> list:
    """One workbook ปร.4 · ปร.1 (ก) · ปร.1 · ปร.2 · ปร.3 per bill in the set (and its PDF), ready for A4."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    stem = safe(Path(res.path).stem)
    bills = defaultdict(list)
    for ln in res.lines:
        bills[ln.bill].append(ln)
    if not bills:
        bills[""] = []
    out = []
    for k, (bill, lines) in enumerate(bills.items(), 1):
        inf = dict(info)
        inf["project"] = info.get("project") or bill or res.project
        suffix = f"-{k}" if len(bills) > 1 else ""
        reps = forms(res, inf, lines)
        x = folder / f"{stem} - ปร.1-ปร.4{suffix}.xlsx"
        R.to_xlsx(reps, x)
        out.append(x)
        if pdf:
            import pymupdf
            fam = R.report_family(family)
            pdfp = x.with_suffix(".pdf")
            merged = pymupdf.open()
            for i, rep in enumerate(reps):
                part = folder / f".{stem}.part{i}.pdf"
                R.to_pdf(rep, part, fam)
                with pymupdf.open(str(part)) as d:
                    merged.insert_pdf(d)
                part.unlink(missing_ok=True)
            merged.save(str(pdfp), garbage=3, deflate=True)
            merged.close()
            R.number_pages(pdfp, True)
            out.append(pdfp)
    return out


__all__ = ["forms", "write", "tag_lines", "Para"]
