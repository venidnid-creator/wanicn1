# -*- coding: utf-8 -*-
"""Calculation report (Excel): summary, roof, slabs, beams, columns, footings."""
from __future__ import annotations

from ..standards import LIVE_LOADS, REFS, STATUS_TEXT
from .design import DesignResult
from .materials import CODES

NOTE = ("ผลคำนวณเบื้องต้นด้วยวิธีหน่วยแรงใช้งาน (WSD) ต้องให้วิศวกรโยธาผู้มีใบอนุญาต"
        "ตรวจสอบและลงนามก่อนนำไปใช้")


def _sheet(wb, title, headers, rows, widths):
    from openpyxl.styles import Font, PatternFill
    from openpyxl.utils import get_column_letter
    ws = wb.create_sheet(title)
    ws.append(headers)
    for c in ws[1]:
        c.font = Font(bold=True)
        c.fill = PatternFill("solid", fgColor="DDEBF7")
    red = PatternFill("solid", fgColor="F8CBAD")
    for r in rows:
        ws.append(list(r))
        if r and "NG" in r[-3:]:
            for c in ws[ws.max_row]:
                c.fill = red
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    return ws


def ok(x) -> str:
    return "OK" if x else "NG"


def write_report(res: DesignResult, path: str) -> None:
    from openpyxl import Workbook
    from openpyxl.styles import Font
    b, mat = res.building, res.concrete
    wb = Workbook()
    ws = wb.active
    ws.title = "สรุป"
    ws.append([f"รายการคำนวณโครงสร้าง — {b.name}"])
    ws["A1"].font = Font(bold=True, size=14)
    ws.append([NOTE])
    ws.append([])
    use = next((t for k, t, _v in LIVE_LOADS if k == b.occupancy), b.occupancy)
    rows = [
        ("กฎหมาย", "กฎกระทรวง กำหนดการออกแบบโครงสร้างอาคาร ... พ.ศ. 2566" if b.design_code != "MR6"
         else "กฎกระทรวง ฉบับที่ 6 (พ.ศ. 2527) ตามบทเฉพาะกาล ข้อ 25"),
        ("ตัวคูณลดกำลัง (ข้อ 8)", "มีการระบุมาตรฐานงานก่อสร้างและการควบคุมคุณภาพ" if b.quality_control
         else "ไม่มีการระบุมาตรฐานงานก่อสร้างและการควบคุมคุณภาพ"),
        ("เกณฑ์การออกแบบ", CODES.get(b.design_code, b.design_code)),
        ("ประเภทการใช้อาคาร", use),
        ("ลดน้ำหนักจรสำหรับเสาและฐานราก", ("ใช้ (กฎกระทรวง ฉบับที่ 6 ข้อ 16 ตามบทเฉพาะกาล)" if b.design_code == "MR6"
                                            else "ใช้ (กฎกระทรวง พ.ศ. 2566 ข้อ 13–14)") if b.ll_reduction else "ไม่ใช้"),
        ("กำลังอัดคอนกรีต fc' (ทรงกระบอก)", f"{mat.fc_prime:g} ksc"),
        ("หน่วยแรงอัดที่ยอมให้ fc", f"{mat.fc:.1f} ksc"),
        ("n = Es/Ec", mat.n),
        ("เหล็กข้ออ้อย", f"{mat.main_grade} fs = {mat.fs('DB'):g} ksc"),
        ("เหล็กเส้นกลม", f"{mat.tie_grade} fs = {mat.fs('RB'):g} ksc"),
        ("ขนาดอาคาร (แนวกริด)", f"{b.xs[-1]:.2f} x {b.ys[-1]:.2f} ม."),
        ("จำนวนชั้น", len(b.levels)),
        ("ฐานราก", f"{b.foundation.kind} {b.foundation.pile} ยาว {b.foundation.pile_length:g} ม."),
        ("จำนวนเสาเข็มรวม", res.total_piles()),
        ("ผลรวม", "ผ่านทุกรายการ" if res.ok else "มีรายการไม่ผ่าน ดูแถวสีแดง"),
    ]
    for r in rows:
        ws.append(list(r))
    for w in res.warnings:
        ws.append(["⚠", w])
    ws.column_dimensions["A"].width = 38
    ws.column_dimensions["B"].width = 60

    if res.roof:
        r = res.roof
        _sheet(wb, "หลังคา", ["รายการ", "ค่า", "หน่วย", "ผล", "หมายเหตุ"], [
            ("น้ำหนักลงคานหลังคา (ต่อพื้นที่ราบ)", round(r.load_plan, 1), "กก./ตร.ม.", "", ""),
            ("พื้นที่หลังคา (ราบ)", round(r.plan_area, 2), "ตร.ม.", "", ""),
            ("พื้นที่หลังคา (ตามลาด)", round(r.slope_area, 2), "ตร.ม.", "", ""),
            ("สันหลังคา", round(r.ridge, 2), "ม.", "", ""),
            ("ตะเข้สัน (รวม)", round(r.hips, 2), "ม.", "", ""),
            ("เชิงชาย", round(r.eave, 2), "ม.", "", ""),
            (f"แป {r.purlin.section} ช่วง {r.purlin.span:.2f} ม.",
             f"Mx {r.purlin.mx:.1f} My {r.purlin.my:.1f}", "กก.-ม.",
             f"Sx {r.purlin.sx_req:.2f}≤{r.purlin.zx} Sy {r.purlin.sy_req:.2f}≤{r.purlin.zy}",
             ok(r.purlin.ok), f"{r.purlin.source} · แอ่น {r.purlin.deflection:.2f}≤{r.purlin.defl_limit:.2f} ซม."),
            (f"จันทัน {r.rafter.section} ช่วง {r.rafter.span:.2f} ม.", f"Mx {r.rafter.mx:.1f}",
             "กก.-ม.", f"Sx {r.rafter.sx_req:.2f}≤{r.rafter.zx}", ok(r.rafter.ok),
             f"{r.rafter.source} · แอ่น {r.rafter.deflection:.2f}≤{r.rafter.defl_limit:.2f} ซม."),
            ("น้ำหนักเหล็กโครงหลังคาโดยประมาณ", round(r.steel_kg, 0), "กก.", "", ""),
            ("อ้างอิง", r.refs, "", "", ""),
        ], [42, 22, 10, 30, 6, 40])

    _sheet(wb, "พื้น", ["ชั้น", "แผ่น", "Mark", "ชนิด", "Lx", "Ly", "m", "W กก./ตร.ม.",
                        "M+ กก.-ม./ม.", "M- กก.-ม./ม.", "หนา ม.", "d ต้องการ ซม.", "เหล็กล่างช่วงสั้น",
                        "เหล็กล่างช่วงยาว", "เหล็กบน", "ผล", "หมายเหตุ", "อ้างอิง"],
           [(s.level, s.panel, s.mark, f"{s.kind} กรณี {s.case}" if s.case else s.kind, s.lx, s.ly,
             round(s.m, 2), round(s.load), round(s.m_pos, 1), round(s.m_neg, 1), s.thickness,
             round(s.d_req, 1), s.bars_short, s.bars_long, s.bars_top, ok(s.ok), s.note, s.refs)
            for s in res.slabs],
           [7, 12, 6, 16, 6, 6, 6, 10, 10, 10, 7, 10, 14, 14, 12, 5, 30, 40])
    if res.trusses:
        rows = []
        for t in res.trusses:
            for g, label in (("top", "จันทันบน"), ("bottom", "จันทันล่าง"), ("web", "เหล็กค้ำ/เสาตั้ง")):
                ratio, text = t.ratios[g]
                rows.append((t.mark, t.line, round(t.span, 2), round(t.spacing, 2), label, t.sections[g].name,
                             round(t.sections[g].r, 2), text, round(ratio, 3), ok(ratio <= 1.0),
                             f"{t.note} ; ปฏิกิริยา {t.reaction:,.0f} กก. ; น้ำหนัก {t.weight:,.0f} กก.", t.refs))
        _sheet(wb, "โครงถักหลังคา", ["Mark", "แนว", "ช่วง ม.", "ระยะห่าง ม.", "ชิ้นส่วน", "หน้าตัด", "r ซม.",
                                      "แรง", "อัตราส่วน", "ผล", "หมายเหตุ", "อ้างอิง"], rows,
               [6, 6, 7, 9, 14, 14, 7, 28, 9, 5, 50, 40])
    if res.stairs:
        _sheet(wb, "บันได", ["ชื่อ", "ชั้นล่าง", "ช่อง", "ชนิด", "จำนวนลูกตั้ง", "ลูกตั้ง ม.", "ลูกนอน ม.",
                             "ช่วง ม.", "กว้างต่อช่วง ม.", "หนา ม.", "W ช่วงลาด กก./ตร.ม.", "M กก.-ม./ม.",
                             "d ต้องการ ซม.", "เหล็กหลัก (ล่าง)", "เหล็กบนที่ปลาย", "เหล็กกันร้าว", "ผล",
                             "หมายเหตุ", "อ้างอิง"],
               [(st.name, st.level, st.panel, st.kind, st.risers, round(st.riser, 3), st.tread, round(st.span, 2),
                 round(st.width, 2), st.thickness, round(st.load), round(st.moment), round(st.d_req, 1),
                 st.bars_main, st.bars_top, st.bars_temp, ok(st.ok), st.note, st.refs) for st in res.stairs],
               [6, 8, 10, 9, 8, 8, 8, 7, 9, 7, 11, 10, 9, 12, 12, 12, 5, 44, 40])
    _sheet(wb, "คาน", ["ชั้น", "แนว", "ช่วง", "Mark", "b ม.", "h ม.", "ยาว ม.", "w กก./ม.",
                       "M- กก.-ม.", "M+ กก.-ม.", "V กก.", "d ต้องการ ซม.", "As บน ซม.²", "As ล่าง ซม.²",
                       "เหล็กบน", "เหล็กล่าง", "ปลอก", "h ไม่ตรวจแอ่น ม.", "ผล", "หมายเหตุ", "อ้างอิง"],
           [(x.level, x.line, x.span, x.mark, x.b, x.h, x.length, round(x.w), round(x.m_neg),
             round(x.m_pos), round(x.v), round(x.d_req, 1), round(x.as_top, 2), round(x.as_bot, 2),
             x.top, x.bottom, x.stirrup, round(x.h_min, 2), ok(x.ok), x.note, x.refs) for x in res.beams],
           [7, 5, 10, 6, 6, 6, 7, 9, 9, 9, 9, 9, 9, 9, 10, 10, 12, 10, 5, 34, 40])
    _sheet(wb, "เสา", ["ตำแหน่ง", "ช่วงเสา", "Mark", "สูง ม.", "P กก.", "P จร กก.", "b ม.", "h ม.", "pg",
                       "เหล็กยืน", "ปลอก", "ลดน้ำหนักจร กก.", "MD x", "ML x", "MD y", "ML y",
                       "แรงอัดร่วมโมเมนต์ (อัตราส่วน · Pu · λ δ Mu/φMn)", "ผล", "หมายเหตุ", "อ้างอิง"],
           [(c.node, c.segment, c.mark, round(c.height, 2), round(c.load), round(c.live), c.b, c.h,
             round(c.pg, 4), c.bars, c.ties, round(c.live_reduced), round(c.m_dx), round(c.m_lx), round(c.m_dy),
             round(c.m_ly), c.slender, ok(c.ok), c.note, c.refs) for c in res.columns],
           [9, 16, 6, 7, 10, 9, 6, 6, 8, 10, 12, 12, 8, 8, 8, 8, 60, 5, 30, 40])
    if res.frames:
        _sheet(wb, "เสถียรภาพชั้น", ["ช่วงเสา", "ทิศ", "Q = ΣPu·Δo/(Vus·lc)", "ผล", "หมายเหตุ"],
               [(st.level, st.direction, round(st.q, 4), "เซ" if st.sway else "ไม่เซ",
                 "Q > 0.05 ต้องขยายโมเมนต์จากแรงด้านข้างด้วย δs = 1/(1−Q)" if st.sway else "")
                for st in res.frames.stability], [16, 6, 20, 8, 60])
    _sheet(wb, "ฐานราก", ["ตำแหน่ง", "Mark", "ชนิด", "P กก.", "เสาเข็ม", "จำนวน", "รับ/ต้น กก.",
                          "กว้าง ม.", "ยาว ม.", "หนา ม.", "เหล็ก X", "เหล็ก Y", "ผล", "หมายเหตุ", "อ้างอิง"],
           [(f.node, f.mark, f.kind, round(f.load), f.pile, f.piles, f.pile_capacity, f.width,
             f.length, f.thickness, f.bars_x, f.bars_y, ok(f.ok), f.note, f.refs) for f in res.footings],
           [9, 6, 7, 10, 8, 7, 10, 7, 7, 7, 10, 10, 5, 36, 40])
    if res.fire:
        f = res.fire
        rows = [("พื้นที่อาคารรวม (ประมาณจากแปลนกริด)", round(f.area, 1), "ตร.ม.", ""),
                ("จำนวนชั้น", f.storeys, "", ""), ("ความสูง", round(f.height, 2), "ม.", ""),
                ("ต้องมีอัตราการทนไฟ (ข้อ 22)", "ต้อง" if f.applies else "ไม่ต้อง", "", "MR2566-23")]
        rows += [("เหตุ", r, "", "MR2566-23") for r in f.reasons]
        rows += [(f"ชั้น {n}", f"เสา คาน ผนังรับน้ำหนัก {h:g} ชม. พื้น {s:g} ชม.", "", "MR2566-23")
                 for n, h, s in f.floors]
        if f.applies:
            rows.append(("โครงหลังคา", f"{f.roof_hours:g} ชม." if f.roof_hours else "ไม่บังคับ", "", "MR2566-23"))
        rows += [("หมายเหตุ", x, "", "MR2566-23") for x in f.notes]
        _sheet(wb, "การทนไฟ", ["รายการ", "ค่า", "หน่วย", "อ้างอิง"], rows, [36, 70, 8, 14])
    if res.wind:
        _wind_sheet(wb, res)
    if res.seismic:
        _seismic_sheet(wb, res)
    references_sheet(wb, res.all_refs())
    wb.save(path)


def _wind_sheet(wb, res):
    w = res.wind
    rows = [("กฎหมาย", "กฎกระทรวง พ.ศ. 2566 ข้อ 17 (หน่วยแรงลมตามตาราง)", "", "MR2566-17"),
            ("สภาพภูมิประเทศ", "เมืองหรือชานเมือง (ตารางที่ 1)" if w.terrain == "urban"
             else "โล่งหรือชายฝั่งทะเล (ตารางที่ 2)", "", "MR2566-17"),
            ("อาคารสาธารณะ ≥ 1,000 ตร.ม. (+15%)", "ใช่" if w.public else "ไม่ใช่", "", "MR2566-17"),
            ("ความสูงอาคาร (ถึงสันหลังคา)", round(w.height, 2), "ม.", ""),
            ("ความกว้างน้อยที่สุด", round(w.least_width, 2), "ม.", ""),
            ("ใช้ตารางได้ (สูง ≤ 40 ม. และ ≤ 3 เท่าความกว้าง)", "ได้" if w.applicable else "ไม่ได้", "", "MR2566-17")]
    rows += [(f"หน่วยแรงลม {t}", q, "กก./ตร.ม.", "MR2566-17") for t, q in w.pressures]
    rows += [("การรวมน้ำหนัก (กำลัง)", "0.75(1.4D + 1.7L) + 1.6W ; 0.9D + 1.6W", "", "MR2566-7"),
             ("การรวมน้ำหนัก (หน่วยแรงใช้งาน) เสาเข็ม/ดิน", "D + 0.75(L + W) ; 0.6D + W", "", "MR2566-6"),
             ("ตัวคูณลดกำลัง", "ตามข้อ 8 (มี/ไม่มีการควบคุมคุณภาพ)", "", "MR2566-8")]
    rows += [("⚠", x, "", "") for x in w.warnings]
    _sheet(wb, "แรงลม", ["รายการ", "ค่า", "หน่วย", "อ้างอิง"], rows, [44, 60, 10, 14])
    _sheet(wb, "แรงลม-ชั้น", ["ชั้น", "ช่วงความสูง ม.", "Fx กก.", "Fy กก.", "Vx กก.", "Vy กก.", "Δx/h", "Δy/h",
                             "หมายเหตุ"],
           [(lv.level, f"{lv.z0:.2f}–{lv.z1:.2f}", round(lv.fx), round(lv.fy), round(lv.vx), round(lv.vy),
             round(lv.drift_x, 5), round(lv.drift_y, 5), lv.note) for lv in w.levels],
           [8, 14, 10, 10, 10, 10, 9, 9, 40])
    kinds = {"column": "เสา", "beam": "คาน", "footing": "ฐานราก"}
    _sheet(wb, "แรงลม-ชิ้นส่วน", ["ชิ้นส่วน", "ตำแหน่ง", "ทิศ", "แรง", "กำลัง", "อัตราส่วน", "ปลอก", "ผล", "หมายเหตุ"],
           [(kinds[c.kind], c.where, c.direction, c.demand, c.capacity, c.ratio, c.detail, ok(c.ok), c.note)
            for c in w.checks], [8, 18, 5, 34, 26, 9, 14, 5, 40])


def _seismic_sheet(wb, res):
    from .seismic import IMPORTANCE, SYSTEMS
    q, s = res.seismic, res.building.seismic
    rows = [
        ("มาตรฐาน", "มยผ. 1301/1302-61 วิธีแรงสถิตเทียบเท่า", "", "DPT1301"),
        ("ข้อมูลพื้นที่", f"Ss {s.ss:g} g, S1 {s.s1:g} g, ชั้นดิน {s.site_class} → Fa {q.fa:.2f}, Fv {q.fv:.2f}"
         if s.mode == "map" else "กรอก SDS, SD1 (และ Sa) จากมาตรฐานโดยตรง", "", "DPT1301, ASCE7"),
        ("SDS = ⅔·Fa·Ss", round(q.sds, 4), "g", "DPT1301"),
        ("SD1 = ⅔·Fv·S1", round(q.sd1, 4), "g", "DPT1301"),
        ("ประเภทความสำคัญ / I", f"{s.category} / {IMPORTANCE[s.category]:g}", "", "DPT1301"),
        ("ประเภทการออกแบบต้านทานแผ่นดินไหว", q.category, "", "DPT1301, ASCE7"),
        ("ระบบโครงสร้าง", f"{SYSTEMS[q.system][0]} R = {q.R:g}, Cd = {q.cd:g}", "", "DPT1301"),
        ("คาบการสั่น T = 0.02·H", round(q.period, 3), "วินาที", "DPT1301"),
        ("Sa", round(q.sa, 4), "g", "DPT1301"),
        ("Cs = Sa·I/R ≥ 0.044·SDS·I ≥ 0.01", round(q.cs, 4), "", "DPT1301, ASCE7"),
        ("น้ำหนักอาคารประสิทธิผล W", round(q.weight), "กก.", "DPT1301"),
        ("แรงเฉือนที่ฐาน V = Cs·W", round(q.base_shear), "กก.", "DPT1301"),
        ("k (การกระจายแรงตามความสูง)", round(q.k, 3), "", "DPT1301"),
        ("การวิเคราะห์", "โครงข้อแข็งระนาบทุกแนวกริด พื้นแข็งเกร็ง แรงบิดโดยบังเอิญ 5% "
         "เสา 0.70Ig คาน 0.35Ig", "", "STATICS, ACI318-STIFF"),
        ("การรวมน้ำหนัก (กำลัง)", "0.75(1.4D + 1.7L) + 1.0E ; 0.9D + 1.0E", "", "MR2566-7"),
        ("การรวมน้ำหนัก (หน่วยแรงใช้งาน) เสาเข็ม/ดิน",
         "D + 0.7E ; D + 0.525E + 0.75L ; 0.6D + 0.7E", "", "MR2566-6"),
    ]
    rows += [("⚠", w, "", "") for w in q.warnings]
    _sheet(wb, "แผ่นดินไหว", ["รายการ", "ค่า", "หน่วย", "อ้างอิง"], rows, [42, 70, 10, 26])
    _sheet(wb, "แผ่นดินไหว-ชั้น", ["ชั้น", "hx ม.", "wx กก.", "Fx กก.", "Vx กก.", "Δx มม.", "Δy มม.",
                                   "Δa มม.", "θ", "ผล", "หมายเหตุ"],
           [(st.level, st.hx, round(st.wx), round(st.fx), round(st.vx), round(st.drift_x * 1000, 1),
             round(st.drift_y * 1000, 1), round(st.limit * 1000), round(st.theta, 4), ok(st.ok), st.note)
            for st in q.storeys], [8, 8, 10, 10, 10, 8, 8, 8, 8, 5, 40])
    kinds = {"column": "เสา", "beam": "คาน", "footing": "ฐานราก"}
    _sheet(wb, "แผ่นดินไหว-ชิ้นส่วน", ["ชิ้นส่วน", "ตำแหน่ง", "ทิศ", "แรง", "กำลัง", "อัตราส่วน",
                                        "รายละเอียดเหล็กปลอก", "ผล", "หมายเหตุ"],
           [(kinds[c.kind], c.where, c.direction, c.demand, c.capacity, c.ratio, c.detail, ok(c.ok), c.note)
            for c in q.checks], [8, 18, 5, 34, 26, 9, 40, 5, 40])


def references_sheet(wb, codes):
    """The standards and documents behind the results, with their status."""
    from openpyxl.styles import Font, PatternFill
    ws = wb.create_sheet("มาตรฐานและที่มา")
    ws.append(["รหัส", "มาตรฐาน / เอกสาร", "ข้อ / ค่าที่ใช้", "สถานะ"])
    for c in ws[1]:
        c.font = Font(bold=True)
        c.fill = PatternFill("solid", fgColor="DDEBF7")
    warn = PatternFill("solid", fgColor="FFF2CC")
    for code in codes:
        r = REFS[code]
        ws.append([r.code, r.title, r.clause, STATUS_TEXT[r.status]])
        if r.status != "document":
            for c in ws[ws.max_row]:
                c.fill = warn
    for col, w in zip("ABCD", (16, 60, 70, 48)):
        ws.column_dimensions[col].width = w
