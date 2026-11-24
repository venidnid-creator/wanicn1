# SPDX-License-Identifier: GPL-3.0-or-later
"""เอกสารจ้างเหมาบริการบุคคลธรรมดา: บัญชีคำนวณปริมาณงาน, รายงานขอจ้าง, TOR, ราคากลาง บก.06,
สัญญาจ้าง (แบบฉบับที่ 3 ราชกิจจานุเบกษา 21 ก.ย. 2569) และใบตรวจรับ/ขอเบิกรายเดือน."""
from __future__ import annotations

import re
from html import escape

from . import thaidate as TD
from .hire import month_name
from .reports import Report, money

THAI_DIGITS = str.maketrans("0123456789", "๐๑๒๓๔๕๖๗๘๙")
DOTS = "........................................"


def _e(v) -> str:
    return escape("" if v is None else str(v))


def _p(text) -> str:
    """A paragraph with a first-line indent, as in Thai official letters."""
    return f"<p style='text-indent:2.5em; margin:4px 0'>{text}</p>"


def baht_text(n) -> str:
    """จำนวนเงินเป็นตัวอักษร: 12,500.50 → หนึ่งหมื่นสองพันห้าร้อยบาทห้าสิบสตางค์."""
    digits = ["", "หนึ่ง", "สอง", "สาม", "สี่", "ห้า", "หก", "เจ็ด", "แปด", "เก้า"]
    places = ["", "สิบ", "ร้อย", "พัน", "หมื่น", "แสน"]

    def read(num: int) -> str:
        if num == 0:
            return ""
        if num >= 1_000_000:
            return read(num // 1_000_000) + "ล้าน" + read(num % 1_000_000)
        out, s = "", str(num)
        for i, ch in enumerate(s):
            d, pos = int(ch), len(s) - i - 1
            if d == 0:
                continue
            if pos == 1 and d == 1:
                out += "สิบ"
            elif pos == 1 and d == 2:
                out += "ยี่สิบ"
            elif pos == 0 and d == 1 and len(s) > 1:
                out += "เอ็ด"
            else:
                out += digits[d] + places[pos]
        return out

    n = round(float(n or 0), 2)
    baht, satang = int(n), int(round((n - int(n)) * 100))
    words = (read(baht) or "ศูนย์") + "บาท"
    return words + (read(satang) + "สตางค์" if satang else "ถ้วน")


def _division(store, did):
    return store.division(did) if did else None


def _signers_for(store, did, approve=True):
    """ผู้ขอ/เจ้าหน้าที่ของกอง และ ผอ.กอง (ถ้ามี) แล้วตามด้วยเจ้าหน้าที่พัสดุ หัวหน้าเจ้าหน้าที่ ผู้อนุมัติ."""
    st = store.settings()
    d = _division(store, did)
    out = []
    if d is not None:
        top = store.top_division(d["id"])
        out.append(("ผู้ขอ", d["officer_name"] or top["officer_name"], d["officer_pos"] or top["officer_pos"]
                    or f"เจ้าหน้าที่{top['name']}"))
        out.append(("ผู้เสนอ", top["head_name"], top["head_pos"] or f"ผู้อำนวยการ{top['name']}"))
    out.append(("", st.get("officer"), st.get("officer_pos")))
    out.append(("", st.get("head_officer"), st.get("head_officer_pos")))
    if approve:
        out.append(("ผู้อนุมัติ", st.get("head"), st.get("head_pos")))
    return out


# -------------------------------------------------------------- 1. ปริมาณงาน
def _xl_workload(title, sub, rows, per_year, extra_head=(), extra=None):
    """Sheet rows with formulas: E = C×D, F = ROUND(E/นาทีต่อปี, 2), totals with SUM."""
    out = [[title], [sub], ["ลำดับที่", "ลักษณะงานที่ปฏิบัติ", "เวลาที่ใช้ต่อราย (นาที)", "ปริมาณงาน (ต่อปี)",
                            "เวลาทั้งหมดต่อปี (นาที)", "จำนวนคนที่ต้องการ", *extra_head]]
    first = len(out) + 1
    n = 0
    side = None
    for x in rows:
        if x.get("side") and x["side"] != side:
            side = x["side"]
            out.append(["", side])
        n += 1
        r = len(out) + 1
        out.append([n, x["task"], float(x["minutes"] or 0), float(x["volume"] or 0), f"=C{r}*D{r}",
                    f"=ROUND(E{r}/{per_year:g},2)", *((extra or {}).get(id(x), []))])
    last = len(out)
    out.append(["", "รวม", "", "", f"=SUM(E{first}:E{last})", f"=SUM(F{first}:F{last})"])
    return out


def workload_sheet(store, jid) -> Report:
    j = store.job(jid)
    w = store.workload(jid)
    r = Report(store, "บัญชีแสดงการคำนวณปริมาณงาน", f"งาน {j['title']} · {j['division'] or ''}")
    r.header = ["ลำดับที่", "ลักษณะงานที่ปฏิบัติ", "เวลาที่ใช้ต่อราย (นาที)", "ปริมาณงาน (ต่อปี)",
                "เวลาทั้งหมดต่อปี (นาที)", "จำนวนคนที่ต้องการ"]
    r.align = ["center", "left", "right", "right", "right", "right"]
    side, n = None, 0
    for x in w["rows"]:
        if x.get("side") and x["side"] != side:
            side = x["side"]
            r.rows.append(["", f"【{side}】", "", "", "", ""])
        n += 1
        r.rows.append([n, x["task"], f"{x['minutes']:,.0f}", f"{x['volume']:,.0f}", f"{x['total']:,.0f}",
                       f"{x['share']:.2f}"])
    r.totals = ["", "รวม", "", "", f"{w['total']:,.0f}", f"{w['fte']:.2f}"]
    v = store.job_value(j)
    r.after = (f"<p>หมายเหตุ: จำนวนคน = เวลาทั้งหมดต่อปี ÷ {w['per_year']:,.0f} นาที "
               "(วันทำงาน 230 วัน × 6 ชั่วโมง × 60 นาที) คิดทีละรายการแล้วรวม · "
               f"สาย{_e(j['line'])} คุณวุฒิ {_e(j['qualification'])} · ค่างานที่เสนอ {money(v['monthly'])} บาท/เดือน</p>"
               + "".join(f"<p>• {_e(n)}</p>" for n in v["notes"]))
    r.signers = [("ผู้กรอกข้อมูล", "", "")] + [x for x in _signers_for(store, j["division_id"], approve=False)[1:2]]
    r.sheets = [("ปริมาณงาน", _xl_workload(r.title, r.subtitle, w["rows"], w["per_year"]))]
    r.sheet_widths = [8, 60, 14, 14, 16, 14]
    return r


def position_workload_sheet(store, pid) -> Report:
    """เอกสารหมายเลข 4 — บัญชีแสดงการคำนวณจำนวนอัตรากำลัง (ลักษณะงานตามมาตรฐานกำหนดตำแหน่ง แยกตามด้าน)."""
    p = store.position(pid)
    a = store.position_analysis(pid)
    per = float(store.setting("work_minutes_year") or 82800)
    rows = [dict(r) for r in store.pos_load(pid)]
    units = " ".join(u["name"] for u in store.chain(p["division_id"]))
    r = Report(store, "บัญชีแสดงการคำนวณจำนวนอัตรากำลังในการขออนุมัติ",
               f"ตำแหน่ง {p['title']}{(' (' + p['level'] + ')') if p['level'] else ''} · {units}")
    r.head_html = (f"<p align=right>เอกสารหมายเลข 4</p><p align=center style='font-size:18pt'><b>{_e(r.title)}</b>"
                   f"<br>{_e(store.setting('org_name') or '')}<br>{_e(r.subtitle)}"
                   + (f" · เลขที่ตำแหน่ง {_e(p['position_no'])}" if p["position_no"] else "") + "</p>")
    r.header = ["ลำดับที่", "ลักษณะงานที่ปฏิบัติ", "เวลาที่ใช้ต่อราย (นาที)", "ปริมาณงาน (ต่อปี)",
                "เวลาทั้งหมดต่อปี (นาที)", "จำนวนตำแหน่งที่ต้องการ"]
    r.align = ["center", "left", "right", "right", "right", "right"]
    side, n = None, 0
    for x in rows:
        if x["side"] != side:
            side = x["side"]
            r.rows.append(["", f"【{side or 'ลักษณะงาน'}】", "", "", "", ""])
        n += 1
        tot = (x["minutes"] or 0) * (x["volume"] or 0)
        r.rows.append([n, x["task"], f"{x['minutes'] or 0:,.0f}", f"{x['volume'] or 0:,.0f}", f"{tot:,.0f}",
                       f"{round(tot / per, 2):.2f}"])
    r.totals = ["", "รวม", "", "", f"{a['total']:,.0f}", f"{a['fte']:.2f}"]
    r.after = (f"<p>สรุป: กรอบอัตรากำลัง {a['frame']} · มีคนครอง {a['occupied']} · ว่าง {a['vacant']} · "
               f"ภาระงานเทียบได้ {a['fte']:.2f} คน → ต้องการ {a['need'] if a['need'] is not None else '-'} คน"
               + (f" · <b>ขาด {a['short']} คน</b>" if a["short"] and a["short"] > 0 else "")
               + "</p><p style='font-size:11pt'>ลักษณะงานนำมาจากมาตรฐานกำหนดตำแหน่ง · จำนวนคน = เวลาทั้งหมดต่อปี ÷ "
               f"{per:,.0f} นาที (230 วัน × 6 ชั่วโมง) คิดทีละรายการ (ทศนิยม 2 ตำแหน่ง) แล้วรวม</p>")
    r.signers = [("ผู้กรอกข้อมูล", "", ""), ("", store.setting("palad") or "", store.setting("palad_pos") or "")]
    r.sheets = [("เอกสาร 4", _xl_workload(r.title, r.subtitle, rows, per))]
    r.sheet_widths = [8, 70, 14, 14, 16, 16]
    return r


def position_history_sheet(store, pid) -> Report:
    """เอกสารหมายเลข 5 — บัญชีแสดงปริมาณงานย้อนหลัง 3 ปี."""
    p = store.position(pid)
    rows = [dict(r) for r in store.pos_load(pid)]
    fy = TD.fiscal_year(TD.today())
    units = " ".join(u["name"] for u in store.chain(p["division_id"]))
    r = Report(store, "บัญชีแสดงปริมาณงานย้อนหลัง 3 ปี เพื่อขออนุมัติ", f"ตำแหน่ง {p['title']} · สังกัด {units}")
    r.head_html = (f"<p align=right>เอกสารหมายเลข 5</p><p align=center style='font-size:18pt'><b>{_e(r.title)}</b>"
                   f"<br>{_e(store.setting('org_name') or '')}<br>{_e(r.subtitle)}</p>")
    r.header = ["ลำดับที่", "ลักษณะงานที่ปฏิบัติ", f"ปีงบประมาณ {fy - 3}", f"ปีงบประมาณ {fy - 2}",
                f"ปีงบประมาณ {fy - 1}", "หมายเหตุ"]
    r.align = ["center", "left", "right", "right", "right", "left"]
    side, n = None, 0
    xl = [[r.title], [r.subtitle], r.header]
    for x in rows:
        if x["side"] != side:
            side = x["side"]
            r.rows.append(["", f"【{side or 'ลักษณะงาน'}】", "", "", "", ""])
            xl.append(["", side])
        n += 1
        vals = [x["y1"] or 0, x["y2"] or 0, x["y3"] or 0]
        r.rows.append([n, x["task"], *[f"{v:,.0f}" for v in vals], ""])
        xl.append([n, x["task"], *vals, ""])
    r.signers = [("ผู้กรอกข้อมูล", "", ""), ("", store.setting("palad") or "", store.setting("palad_pos") or "")]
    r.sheets = [("เอกสาร 5", xl)]
    r.sheet_widths = [8, 70, 14, 14, 14, 20]
    return r


def proposal_text(a) -> str:
    """ข้อเสนอจากผลวิเคราะห์ของตำแหน่ง."""
    if a.get("need") is None:
        return "ยังไม่ได้กรอกปริมาณงาน"
    s = a["short"]
    if s > 0:
        fill = min(s, a["vacant"])
        over = s - fill
        t = [f"ขาด {s} คน"]
        if fill:
            t.append(f"สรรหาบรรจุตำแหน่งว่าง {fill}")
        if over:
            t.append(f"เกินกรอบ {over} → เสนอปรับกรอบ/จ้างเหมาบริการ")
        else:
            t.append("ระหว่างสรรหาใช้จ้างเหมาบริการได้")
        return " · ".join(t)
    if s < 0:
        return f"ภาระงานน้อยกว่าคนที่มี {-s} คน — ทบทวนการมอบหมายงาน"
    return "เหมาะสม"


def manpower_report(store, did=None) -> Report:
    """ตารางวิเคราะห์อัตรากำลัง: กรอบ / มีคนครอง / ว่าง / ภาระงาน / ต้องการ / ขาด — ตามสายการบังคับบัญชา."""
    rows = store.manpower_rows(did)
    title = "ตารางวิเคราะห์อัตรากำลังและปริมาณงาน"
    sub = store.division(did)["name"] if did else "ทุกส่วนราชการ"
    r = Report(store, title, sub, landscape=True)
    r.header = ["ส่วนราชการ / ตำแหน่ง", "ระดับ", "ประเภท", "กรอบ", "มีคนครอง", "ว่าง", "ภาระงาน (คน)",
                "ต้องการ", "ขาด(+)/เกิน(−)", "ข้อเสนอ"]
    r.align = ["left", "center", "left", "center", "center", "center", "right", "center", "center", "left"]
    xl = [[title], [sub], r.header]
    for x in rows:
        ind = "　" * x["depth"]
        if x["kind"] == "unit":
            d = x["division"]
            r.rows.append([f"{ind}▸ {d['name']}", "", d["kind"], x["frame"], x["occupied"], x["vacant"],
                           f"{x['fte']:.2f}" if x["analysed"] else "", x["need"] or "",
                           (f"+{x['short']}" if x["short"] else "") if x["analysed"] else "",
                           f"วิเคราะห์แล้ว {x['analysed']}/{x['positions']} ตำแหน่ง"])
            xl.append([f"{ind}{d['name']}", "", d["kind"], x["frame"], x["occupied"], x["vacant"],
                       x["fte"] if x["analysed"] else "", x["need"] or "", x["short"] if x["analysed"] else "", ""])
        else:
            p = x["position"]
            need = x["need"]
            sh = x["short"]
            r.rows.append([f"{ind}{p['title']}", p["level"] or "", p["kind"] or "", x["frame"], x["occupied"],
                           x["vacant"], f"{x['fte']:.2f}" if x["has_load"] else "", need if need is not None else "",
                           ("" if sh is None else (f"+{sh}" if sh > 0 else str(sh))), proposal_text(x)])
            rr = len(xl) + 1
            xl.append([f"{ind}{p['title']}", p["level"] or "", p["kind"] or "", x["frame"], x["occupied"],
                       f"=D{rr}-E{rr}", x["fte"] if x["has_load"] else "",
                       (f"=IF(G{rr}>0,MAX(1,ROUND(G{rr},0)),\"\")" if x["has_load"] else ""),
                       (f"=IF(H{rr}=\"\",\"\",H{rr}-E{rr})" if x["has_load"] else ""), proposal_text(x)])
    tops = [x for x in rows if x["kind"] == "unit" and x["depth"] == 0]
    tot = {k: sum(x[k] for x in tops) for k in ("frame", "occupied", "vacant", "short", "need")}
    r.totals = ["รวม", "", "", tot["frame"], tot["occupied"], tot["vacant"], "", tot["need"] or "",
                f"+{tot['short']}" if tot["short"] else "", ""]
    r.after = ("<p style='font-size:11pt'>ภาระงาน (คน) = ผลรวมเวลาทั้งหมดต่อปี ÷ 82,800 นาที จากบัญชีคำนวณจำนวนอัตรากำลัง"
               "ของแต่ละตำแหน่ง · ต้องการ = ปัดเศษตั้งแต่ .50 ขึ้น · ขาด = ต้องการ − มีคนครอง · "
               "ตำแหน่งที่ยังไม่กรอกปริมาณงานจะไม่นำมาคำนวณ</p>")
    r.signers = [("ผู้จัดทำ", "", ""), ("", store.setting("palad") or "", store.setting("palad_pos") or "")]
    r.sheets = [("วิเคราะห์อัตรากำลัง", xl)]
    r.sheet_widths = [48, 10, 22, 8, 10, 8, 12, 10, 12, 50]
    return r


# ------------------------------------------------------- บันทึกข้อความ
LEGAL_DEFAULT = [
    "พระราชบัญญัติสภาตำบลและองค์การบริหารส่วนตำบล พ.ศ. 2537 และที่แก้ไขเพิ่มเติมจนถึงปัจจุบัน "
    "มาตรา 59 (2) มาตรา 60 มาตรา 67 (9)",
    "พระราชบัญญัติการจัดซื้อจัดจ้างและการบริหารพัสดุภาครัฐ พ.ศ. 2560 มาตรา 4 มาตรา 8 มาตรา 9 มาตรา 55 (3) "
    "มาตรา 56 วรรคหนึ่ง (2) (ข)",
    "ระเบียบกระทรวงการคลังว่าด้วยการจัดซื้อจัดจ้างและการบริหารพัสดุภาครัฐ พ.ศ. 2560 ข้อ 21 ข้อ 22 ข้อ 79",
    "กฎกระทรวงกำหนดวงเงินการจัดซื้อจัดจ้างพัสดุโดยวิธีเฉพาะเจาะจง วงเงินการจัดซื้อจัดจ้างที่ไม่ทำข้อตกลงเป็นหนังสือ "
    "และวงเงินการจัดซื้อจัดจ้างในการแต่งตั้งผู้ตรวจรับพัสดุ พ.ศ. 2560 ข้อ 1 และข้อ 5",
    "ระเบียบกระทรวงมหาดไทยว่าด้วยการรับเงิน การเบิกจ่ายเงิน การฝากเงิน การเก็บรักษาเงิน และการตรวจเงินขององค์กร"
    "ปกครองส่วนท้องถิ่น พ.ศ. 2566 และที่แก้ไขเพิ่มเติม",
    "หนังสือกระทรวงมหาดไทย ที่ มท 0808.2/ว 9636 ลงวันที่ 10 กันยายน 2567 เรื่อง หลักเกณฑ์และแนวทางการจ้างเหมาบริการ"
    "ขององค์กรปกครองส่วนท้องถิ่น",
    "หนังสือคณะกรรมการวินิจฉัยปัญหาการจัดซื้อจัดจ้างและการบริหารพัสดุภาครัฐ ด่วนที่สุด ที่ กค (กวจ) 0405.2/ว 877 "
    "ลงวันที่ 8 ธันวาคม 2568 เรื่อง ซ้อมความเข้าใจงานจ้างเหมาบริการ (บุคคลธรรมดา)",
    "หนังสือคณะกรรมการวินิจฉัยปัญหาการจัดซื้อจัดจ้างและการบริหารพัสดุภาครัฐ ด่วนที่สุด ที่ กค (กวจ) 0405.2/ว 727 "
    "ลงวันที่ 22 กันยายน 2569 (ยกเว้นค่าปรับและหลักประกันสัญญางานจ้างเหมาบริการบุคคลธรรมดา)",
    "หนังสือคณะกรรมการวินิจฉัยปัญหาการจัดซื้อจัดจ้างและการบริหารพัสดุภาครัฐ ด่วนที่สุด ที่ กค (กวจ) 0405.4/ว 159 "
    "ลงวันที่ 20 มีนาคม 2566 เรื่อง แนวทางปฏิบัติในการจัดทำร่างรายละเอียดขอบเขตของงานทั้งโครงการ (TOR)",
    "หนังสือกรมบัญชีกลาง ด่วนที่สุด ที่ กค 0433.2/ว 206 ลงวันที่ 1 พฤษภาคม 2562 เรื่อง คู่มือแนวทางการประกาศ"
    "รายละเอียดข้อมูลราคากลางและการคำนวณราคากลาง",
]


def legal_refs(store) -> list[str]:
    raw = (store.setting("hire_legal") or "").strip()
    return [x.strip() for x in raw.splitlines() if x.strip()] if raw else list(LEGAL_DEFAULT)


def _thai_long(d) -> str:
    d = TD.parse(d) or TD.today()
    return f"{d.day} เดือน {TD.MONTHS[d.month - 1]} พ.ศ. {d.year + 543}"


def budget_text(store, bid, division_name="", exclude_proc=None) -> str:
    """«ข้อบัญญัติ… ประจำปีงบประมาณ พ.ศ. … แผนงาน… งาน… งบ… หมวด… ประเภท… งบประมาณตั้งไว้ … บาท (…)
    งบประมาณที่ได้รับของ<กอง> … คงเหลือ …» — ตามรูปแบบบันทึกจริงของหน่วยงาน."""
    if not bid:
        return "ข้อบัญญัติงบประมาณรายจ่ายประจำปี (ระบุรายการงบประมาณ)"
    it = store.budget_item(bid)
    b = store.balance(bid, exclude_proc=exclude_proc)
    org = store.setting("org_name") or ""
    detail = (it["detail"] or "").split("\n")[0]
    detail = re.sub(r"\s*\([^)]*\)\s*$", "", detail)[:220]
    def pre(word, v):
        v = (v or "").strip()
        return v if not v or v.startswith(word) else word + v
    return (f"ข้อบัญญัติ{_e(org)} ประจำปีงบประมาณ พ.ศ. {it['fy']} {_e(pre('แผนงาน', it['plan']))} "
            f"{_e(pre('งาน', it['task']))} {_e(pre('งบ', it['grp']))} {_e(pre('หมวด', it['category']))} "
            f"ประเภท{_e(it['type'])} รายการ{_e(it['name'])}"
            + (f" {_e(detail)}" if detail else "")
            + f" งบประมาณตั้งไว้ {money(b['budget'])} บาท ({baht_text(b['budget'])})"
            + (f" ของ{_e(division_name)}" if division_name else "")
            + f" ใช้ไปแล้ว/ผูกพัน {money(b['budget'] - b['available'])} บาท "
            f"งบประมาณคงเหลือ {money(b['available'])} บาท ({baht_text(b['available'])})")


def memo(store, did, no, date, subject, sections, sender, route=None, closing="จึงเรียนมาเพื่อโปรดพิจารณา") -> Report:
    """บันทึกข้อความ: ส่วนราชการ ที่ วันที่ เรื่อง เรียน + หัวข้อ (เรื่องเดิม ข้อเท็จจริง ข้อระเบียบ ข้อพิจารณา)
    + ผู้เสนอ + ความเห็นตามสายการบังคับบัญชาจนถึงคำสั่งนายก."""
    st = store.settings()
    units = " ".join(u["name"] for u in store.chain(did)) if did else ""
    org = st.get("org_name") or ""
    phone = f" โทร {st.get('org_phone')}" if st.get("org_phone") else ""
    prefix = st.get("doc_prefix") or ""
    head_pos = (st.get("head_pos") or "")
    to = "นายก" + org if org else "นายกองค์การบริหารส่วนตำบล"
    if head_pos.startswith("นายก"):
        to = head_pos
    r = Report(store, "บันทึกข้อความ", subject)
    r.head_html = (
        "<p align=center style='font-size:24pt'><b>บันทึกข้อความ</b></p>"
        f"<p style='margin:0'><b>ส่วนราชการ</b> {_e(units)} {_e(org)}{_e(phone)}</p>"
        f"<p style='margin:0'><b>ที่</b> {_e(prefix)}{'/' if prefix else ''}{_e(no or '........')}"
        f"   <b>วันที่</b> {_thai_long(date)}</p>"
        f"<p style='margin:0'><b>เรื่อง</b> {_e(subject)}</p><hr>"
        f"<p><b>เรียน</b> {_e(to)}</p>")
    body = []
    for head, paras in sections:
        if head:
            body.append(f"<p style='margin:0'><b>{_e(head)}</b></p>")
        for x in paras:
            body.append(_p(x))
    body.append(_p(closing))
    role, name, pos = sender
    body.append(f"<p align=center><br>(ลงชื่อ)........................................................{_e(role)}"
                f"<br>( {_e(name) or DOTS} )<br>{_e(pos)}</p>")
    for role, name, pos in (route or []):
        if role.startswith("คำสั่ง"):
            body.append(f"<p style='margin:0'><b>คำสั่ง{_e(pos)}</b><br>☐ เห็นชอบ/อนุมัติ/ลงนามแล้ว "
                        f" ☐ ไม่อนุมัติ เพราะ{DOTS}</p>")
        else:
            body.append(f"<p style='margin:0'><b>{_e(role)}</b><br>☐ เห็นควรพิจารณาอนุมัติ "
                        f" ☐ ไม่ควรอนุมัติ เพราะ{DOTS}</p>")
        body.append(f"<p align=center style='margin:0'>(ลงชื่อ)................................................"
                    f"<br>( {_e(name) or DOTS} )<br>{_e(pos)}<br></p>")
    r.before = "".join(body)
    r.signers = []
    return r


def _contract_ctx(store, cid):
    c = store.contract(cid)
    j = store.job(c["job_id"]) if c["job_id"] else None
    title = j["title"] if j else "งานบริการ"
    p = store.procurement(c["proc_id"]) if c["proc_id"] else None
    total = store.contract_total(c["start"], c["end"], c["monthly"])
    route = store.route(c["division_id"])
    sender = ("ผู้เสนอ",) + tuple(route[0][1:]) if route and route[0][0] == "ผู้เสนอ" else ("ผู้เสนอ", "", "")
    rest = [x for x in route if x[0] != "ผู้เสนอ"]
    top = store.top_division(c["division_id"]) if c["division_id"] else None
    subject = (f"ขออนุมัติจ้างเหมาบริการบุคคลธรรมดา {title} {top['name'] if top else ''} "
               f"ระยะเวลา {TD.thai(c['start'], False)} ถึง {TD.thai(c['end'], False)}")
    return c, j, title, p, total, sender, rest, top, subject


def hire_approval_memo(store, cid) -> Report:
    """ขั้นที่ 1 — บันทึกขออนุมัติจ้าง (เหตุผล ปริมาณงาน งบประมาณ ข้อกฎหมาย มอบหมายผู้จัดทำ TOR/ราคากลาง และผู้ตรวจรับ)."""
    c, j, title, p, total, sender, rest, top, subject = _contract_ctx(store, cid)
    w = store.workload(j["id"]) if j else None
    pos_txt = ""
    if j and j["position_id"]:
        a = store.position_analysis(j["position_id"])
        pos_txt = (f" ตำแหน่ง{a['position']['title']} มีกรอบอัตรากำลัง {a['frame']} อัตรา มีคนครอง {a['occupied']} "
                   f"ว่าง {a['vacant']} ภาระงานเทียบได้ {a['fte']:.2f} คน")
    tor_by = c["tor_by"] or DOTS
    insp = c["inspector"] or DOTS
    facts = [f"{_e(top['name'] if top else '')} มีภารกิจ{_e(title)}{_e(pos_txt)} "
             f"{'ปริมาณงานส่วนที่ต้องจ้างเหมาตามบัญชีแสดงการคำนวณปริมาณงานเทียบได้ ' + format(w['fte'], '.2f') + ' คน ' if w else ''}"
             "บุคลากรที่มีอยู่ไม่เพียงพอต่อปริมาณงาน จึงมีความจำเป็นต้องจ้างเหมาบริการบุคคลธรรมดา โดยมุ่งผลสำเร็จของงาน"
             f"เป็นสำคัญ ระยะเวลา {TD.thai(c['start'], False)} ถึง {TD.thai(c['end'], False)} อัตราเดือนละ "
             f"{money(c['monthly'])} บาท รวมเป็นเงิน {money(total)} บาท ({baht_text(total)})"]
    legal = [f"3.{i} {_e(x)}" for i, x in enumerate(legal_refs(store), 1)]
    prop = [f"4.1 เห็นควรอนุมัติให้ดำเนินการจ้างเหมาบริการบุคคลธรรมดา {_e(title)} ตามข้อ 2 โดยวิธีเฉพาะเจาะจง "
            "(ตามนัยข้อระเบียบ/ข้อกฎหมาย ข้อ 3) โดยเบิกจ่ายจากงบประมาณตามข้อ 1",
            f"4.2 เห็นควรมอบหมายให้ {_e(tor_by)} ตำแหน่ง {_e(c['tor_by_pos'] or DOTS)} เป็นผู้จัดทำร่างขอบเขตของงาน "
            "(Terms of Reference : TOR) รวมทั้งกำหนดหลักเกณฑ์การพิจารณาคัดเลือกข้อเสนอและกำหนดราคากลาง "
            "แล้วรายงานผลภายใน 10 วัน นับจากวันที่ได้รับทราบการมอบหมาย",
            f"4.3 เห็นควรมอบหมายให้ {_e(insp)} ตำแหน่ง {_e(c['inspector_pos'] or DOTS)} เป็นผู้ตรวจรับพัสดุ "
            "ตรวจรับงานเป็นรายเดือน (งวดระหว่างสัญญาภายใน 3 วันทำการ งวดสุดท้ายภายใน 5 วันทำการ "
            "หลังจากผู้รับจ้างส่งมอบงาน)"]
    secs = [("1. เรื่องเดิม", [budget_text(store, c["budget_item_id"], top["name"] if top else "", c["proc_id"])]),
            ("2. ข้อเท็จจริง", facts), ("3. ข้อระเบียบ/ข้อกฎหมาย", legal),
            ("4. ข้อพิจารณา/ข้อเสนอ", ["เพื่อให้การจัดจ้างเป็นไปด้วยความถูกต้องตามระเบียบและหนังสือสั่งการที่เกี่ยวข้อง "
                                      "เห็นควรดำเนินการ ดังนี้"] + prop)]
    date = c["doc1_date"] or (p["date_request"] if p else None)
    return memo(store, c["division_id"], c["doc1_no"], date, subject, secs, sender, rest,
                closing="จึงเรียนมาเพื่อโปรดพิจารณาอนุมัติ")


def tor_report_memo(store, cid) -> Report:
    """ขั้นที่ 2 — รายงานผลการดำเนินการจัดทำร่างขอบเขตของงาน (TOR)."""
    c, j, title, p, total, sender, rest, top, subject = _contract_ctx(store, cid)
    s = ("ผู้จัดทำร่างขอบเขตของงาน", c["tor_by"] or "", c["tor_by_pos"] or "")
    first = _thai_long(c["doc1_date"]) if c["doc1_date"] else DOTS
    secs = [("เรื่องเดิม", [f"ตามบันทึกข้อความ ที่ {_e(store.setting('doc_prefix') or '')}"
                           f"{'/' if store.setting('doc_prefix') else ''}{_e(c['doc1_no'] or DOTS)} ลงวันที่ {first} "
                           f"เรื่อง {_e(subject)} และได้มอบหมายผู้จัดทำร่างขอบเขตของงาน (Terms of Reference : TOR) "
                           f"โดยเบิกจ่ายจาก{budget_text(store, c['budget_item_id'], top['name'] if top else '', c['proc_id'])}"]),
            ("ข้อเท็จจริง", ["บัดนี้ ข้าพเจ้าได้ดำเนินการกำหนดร่างขอบเขตของงาน รวมทั้งกำหนดหลักเกณฑ์การพิจารณาคัดเลือก"
                            f"ข้อเสนอ สำหรับการจ้างเหมาบริการบุคคลธรรมดา {_e(title)} เรียบร้อยแล้ว "
                            "รายละเอียดปรากฏตามเอกสารแนบท้ายบันทึกข้อความฉบับนี้"]),
            ("ข้อกฎหมาย/ข้อระเบียบ", ["3.1 พระราชบัญญัติการจัดซื้อจัดจ้างและการบริหารพัสดุภาครัฐ พ.ศ. 2560 มาตรา 8 มาตรา 9",
                                     "3.2 ระเบียบกระทรวงการคลังว่าด้วยการจัดซื้อจัดจ้างและการบริหารพัสดุภาครัฐ พ.ศ. 2560 "
                                     "ข้อ 21 วรรคแรก",
                                     "3.3 หนังสือคณะกรรมการวินิจฉัยฯ ด่วนที่สุด ที่ กค (กวจ) 0405.4/ว 159 ลงวันที่ 20 มีนาคม "
                                     "2566 เรื่อง แนวทางปฏิบัติในการจัดทำร่างรายละเอียดขอบเขตของงาน (TOR)"]),
            ("ข้อพิจารณา/ข้อเสนอแนะ", ["ผู้จัดทำร่างขอบเขตของงานได้ดำเนินการจัดทำร่างขอบเขตของงาน (Terms of Reference : TOR) "
                                      "เรียบร้อยแล้ว จึงขอรายงานผลมาเพื่อพิจารณาให้ความเห็นชอบและอนุมัติต่อไป"])]
    return memo(store, c["division_id"], c["doc2_no"], c["doc2_date"],
                "รายงานผลการดำเนินการจัดทำร่างขอบเขตของงาน (Terms of Reference : TOR) จ้างเหมาบริการบุคคลธรรมดา "
                f"{title}", secs, s, rest)


def price_report_memo(store, cid) -> Report:
    """ขั้นที่ 4 — รายงานผลการกำหนดราคากลาง (แนบแบบ บก.06)."""
    c, j, title, p, total, sender, rest, top, subject = _contract_ctx(store, cid)
    s = ("ผู้กำหนดราคากลาง", c["tor_by"] or "", c["tor_by_pos"] or "")
    pre = store.setting("doc_prefix") or ""
    ref = lambda no, d: f"ที่ {_e(pre)}{'/' if pre else ''}{_e(no or DOTS)} ลงวันที่ {_thai_long(d) if d else DOTS}"
    secs = [("เรื่องเดิม", [f"1.1 ตามบันทึกข้อความ {ref(c['doc1_no'], c['doc1_date'])} เรื่อง {_e(subject)} "
                           "และได้มอบหมายผู้กำหนดราคากลาง",
                           f"1.2 ตามบันทึกข้อความ {ref(c['doc2_no'], c['doc2_date'])} เรื่อง รายงานผลการดำเนินการจัดทำ"
                           "ร่างขอบเขตของงาน (TOR) ซึ่งได้รับความเห็นชอบและอนุมัติแล้ว"]),
            ("ข้อเท็จจริง", [f"บัดนี้ ข้าพเจ้าได้ดำเนินการกำหนดราคากลาง สำหรับการจ้างเหมาบริการบุคคลธรรมดา "
                            f"{_e(title)} เป็นเงินทั้งสิ้น {money(total)} บาท ({baht_text(total)}) "
                            f"อัตราเดือนละ {money(c['monthly'])} บาท โดยเทียบค่าตอบแทนตามคุณวุฒิและปริมาณงาน "
                            "รายละเอียดปรากฏตามแบบ บก.06 และเอกสารที่แนบท้ายบันทึกข้อความฉบับนี้"]),
            ("ข้อกฎหมาย/ข้อระเบียบ", ["3.1 พระราชบัญญัติการจัดซื้อจัดจ้างและการบริหารพัสดุภาครัฐ พ.ศ. 2560 มาตรา 4 (ราคากลาง)",
                                     "3.2 หนังสือกรมบัญชีกลาง ด่วนที่สุด ที่ กค 0433.2/ว 206 ลงวันที่ 1 พฤษภาคม 2562 "
                                     "เรื่อง คู่มือแนวทางการประกาศรายละเอียดข้อมูลราคากลางและการคำนวณราคากลาง",
                                     "3.3 หนังสือกระทรวงมหาดไทย ที่ มท 0808.2/ว 9636 ลงวันที่ 10 กันยายน 2567"]),
            ("ข้อพิจารณา/ข้อเสนอแนะ", ["ผู้กำหนดราคากลางได้ดำเนินการจัดทำราคากลางเรียบร้อยแล้ว "
                                      "จึงขอรายงานผลมาเพื่อพิจารณาให้ความเห็นชอบและอนุมัติต่อไป"])]
    return memo(store, c["division_id"], c["doc3_no"], c["doc3_date"],
                f"รายงานผลการกำหนดราคากลาง จ้างเหมาบริการบุคคลธรรมดา {title}", secs, s, rest)


# ------------------------------------------------------------------- 2. TOR
def tor(store, jid, months=12, contract=None) -> Report:
    j = store.job(jid)
    v = store.job_value(j)
    c = contract
    monthly = c["monthly"] if c else v["monthly"]
    total = store.contract_total(c["start"], c["end"], monthly) if c else monthly * months
    period = (f"{TD.thai(c['start'], False)} ถึง {TD.thai(c['end'], False)}" if c
              else f"{months} เดือน นับแต่วันลงนามในสัญญา")
    tasks = store.tasks(jid)
    scope = (j["scope"] or "").strip()
    if scope:
        scope_html = "<br>".join(_e(x) for x in scope.splitlines())
    else:
        side, parts, n = None, [], 0
        for t in tasks:
            if (t["side"] or "") != side:
                side = t["side"] or ""
                if side:
                    parts.append(f"<br><u>{_e(side)}</u>")
            n += 1
            parts.append(f"<br>4.{n} {_e(t['task'])}")
        scope_html = "".join(parts)
    org = store.setting("org_name") or ""
    top = store.top_division(j["division_id"]) if j["division_id"] else None
    bud = budget_text(store, c["budget_item_id"], top["name"] if top else "", c["proc_id"]) if c else DOTS
    pre = store.setting("doc_prefix") or ""
    ref = (f"1.2 บันทึกข้อความที่ {_e(pre)}{'/' if pre else ''}{_e(c['doc1_no'] or DOTS)} เรื่อง ขออนุมัติจ้างเหมาบริการ"
           f"บุคคลธรรมดา {_e(j['title'])} ลงวันที่ {_thai_long(c['doc1_date']) if c['doc1_date'] else DOTS}"
           if c else "")
    quals = j["qualifications"] or (
        "3.1 มีความสามารถตามกฎหมาย<br>3.2 ไม่เป็นบุคคลล้มละลาย<br>3.3 ไม่อยู่ระหว่างเลิกกิจการ<br>"
        "3.4 ไม่เป็นบุคคลซึ่งอยู่ระหว่างถูกระงับการยื่นข้อเสนอหรือทำสัญญากับหน่วยงานของรัฐตามมาตรา 106 วรรคสาม<br>"
        "3.5 ไม่เป็นบุคคลซึ่งถูกแจ้งเวียนชื่อให้เป็นผู้ทิ้งงานของหน่วยงานของรัฐตามมาตรา 109<br>"
        "3.6 คุณสมบัติหรือไม่มีลักษณะต้องห้ามอื่นตามที่คณะกรรมการนโยบายประกาศกำหนดในราชกิจจานุเบกษา<br>"
        f"3.7 เป็นบุคคลธรรมดา คุณวุฒิ {_e(j['qualification'])} หรือมีความรู้ความสามารถเหมาะสมกับงานที่จ้าง")
    sections = [
        ("1. ความเป็นมา", f"1.1 {bud}" + (f"<br>{ref}" if ref else "")
         + (f"<br>{_e(j['background'])}" if j["background"] else "")),
        ("2. วัตถุประสงค์", _e(j["objective"] or f"เพื่อให้งาน{j['title']} ของ{(top['name'] if top else org)} "
                                                 "สำเร็จลุล่วงตามขอบเขตของงาน โดยมุ่งผลสำเร็จของงานเป็นสำคัญ")),
        ("3. คุณสมบัติผู้ประสงค์จะเสนอราคา", quals),
        ("4. รายละเอียดขอบเขตของงานที่จะดำเนินการจัดจ้าง", f"จ้างเหมาบริการบุคคลธรรมดา {_e(j['title'])} "
                                                         "(ลักษณะงานตามมาตรฐานกำหนดตำแหน่ง) มีรายละเอียดดังนี้" + scope_html),
        ("5. กำหนดเวลาส่งมอบงาน", f"ระยะเวลาจ้าง {period} ส่งมอบงานเป็นรายเดือน "
                                  f"ณ {_e(j['work_place'] or (top['name'] if top else '') + ' ' + org)} · "
                                  f"{_e(j['work_hours'])}"),
        ("6. หลักเกณฑ์การพิจารณาคัดเลือกข้อเสนอ", f"{_e(org)} จะพิจารณาตัดสินโดยใช้เกณฑ์ราคา"),
        ("7. วงเงินงบประมาณ", f"{money(total)} บาท ({baht_text(total)}) อัตราเดือนละ {money(monthly)} บาท "
                              "รวมภาษีอากรและค่าใช้จ่ายทั้งปวงแล้ว"),
        ("8. งวดงานและการจ่ายเงิน", "แบ่งจ่ายเป็นรายเดือนตามเดือนปฏิทิน เมื่อผู้รับจ้างส่งมอบงานและผู้ตรวจรับพัสดุ"
                                    "ตรวจรับถูกต้องครบถ้วนแล้ว เดือนที่ทำงานไม่เต็มเดือนคิดเป็นรายวัน โดยถือว่าหนึ่งเดือนมี 30 วัน"),
        ("9. อัตราค่าปรับ", "ไม่กำหนดค่าปรับ (ยกเว้นตามหนังสือคณะกรรมการวินิจฉัยฯ ที่ กค (กวจ) 0405.2/ว 727 "
                            "ลงวันที่ 22 กันยายน 2569) — กรณีส่งงานไม่ครบจ่ายเฉพาะวันที่ส่งมอบงานครบถ้วน"),
        ("10. การกำหนดระยะเวลารับประกันความชำรุดบกพร่อง", "ไม่มี (งานบริการ) และไม่ต้องวางหลักประกันสัญญา"),
    ]
    r = Report(store, "ร่างรายละเอียดขอบเขตของงาน (Terms of Reference : TOR)",
               f"จ้างเหมาบริการบุคคลธรรมดา {j['title']} {top['name'] if top else ''} ด้วยวิธีเฉพาะเจาะจง")
    r.head_html = (f"<p align=center style='font-size:18pt'><b>{_e(r.title)}</b><br>{_e(r.subtitle)}<br>"
                   "******************************************</p>")
    r.before = "".join(f"<p><b>{_e(h)}</b><br>{body}</p>" for h, body in sections)
    r.signers = [("ผู้จัดทำร่างขอบเขตของงาน", (c["tor_by"] if c else "") or "", (c["tor_by_pos"] if c else "") or "")]
    return r


# ------------------------------------------------------------------ 3. บก.06
def bk06(store, jid, contract=None, months=12) -> Report:
    j = store.job(jid)
    v = store.job_value(j)
    c = contract
    monthly = c["monthly"] if c else v["monthly"]
    total = store.contract_total(c["start"], c["end"], monthly) if c else monthly * months
    bud = store.balance(c["budget_item_id"])["budget"] if c and c["budget_item_id"] else 0.0
    org = store.setting("org_name") or ""
    top = store.top_division(j["division_id"]) if j["division_id"] else None
    r = Report(store, "ตารางแสดงวงเงินงบประมาณที่ได้รับจัดสรรและรายละเอียดค่าใช้จ่าย",
               "การจัดซื้อจัดจ้างที่มิใช่งานก่อสร้าง")
    r.head_html = (f"<p align=right><b>แบบ บก.06</b></p><p align=center style='font-size:18pt'><b>{_e(r.title)}</b>"
                   f"<br>{_e(r.subtitle)}</p>")
    d3 = (c["doc3_date"] if c else None) or TD.today()
    lines = [f"1. ชื่อโครงการ จ้างเหมาบริการบุคคลธรรมดา {_e(j['title'])}",
             f"2. หน่วยงานเจ้าของโครงการ {_e(top['name'] if top else '')} {_e(org)}",
             f"3. วงเงินงบประมาณที่ได้รับจัดสรร {money(bud) if bud else DOTS} บาท" + (f" ({baht_text(bud)})" if bud else ""),
             f"4. วันที่กำหนดราคากลาง (ราคาอ้างอิง) ณ วันที่ {_thai_long(d3)}",
             f" เป็นเงิน {money(total)} บาท ({baht_text(total)})",
             f" ราคา/หน่วย (ถ้ามี) เดือนละ {money(monthly)} บาท (วันละ {money(monthly / 30)} บาท)",
             "5. แหล่งที่มาของราคากลาง (ราคาอ้างอิง)",
             f" 5.1 อัตราค่างานสาย{_e(j['line'])} คุณวุฒิ {_e(j['qualification'])} {money(v['base'])} บาท/เดือน "
             f"ปรับตามความยากของงาน {v['difficulty']:g} % (ตามหนังสือ มท 0808.2/ว 9636)",
             f" 5.2 บัญชีแสดงการคำนวณปริมาณงาน เทียบได้ {v['fte']:.2f} คน",
             " 5.3 ราคาที่เคยจ้างครั้งหลังสุดภายในระยะเวลาสองปีงบประมาณ (ถ้ามี)",
             "6. รายชื่อผู้รับผิดชอบกำหนดราคากลาง",
             f" 6.1 {_e((c['tor_by'] if c else '') or DOTS)} ตำแหน่ง {_e((c['tor_by_pos'] if c else '') or DOTS)}"]
    r.before = "".join(f"<p style='margin:0'>{x}</p>" for x in lines)
    r.signers = [("ผู้กำหนดราคากลาง", (c["tor_by"] if c else "") or "", (c["tor_by_pos"] if c else "") or "")]
    return r


# -------------------------------------------------------- 4. รายงานขอจ้าง
def hire_request(store, cid) -> Report:
    c = store.contract(cid)
    j = store.job(c["job_id"]) if c["job_id"] else None
    p = store.procurement(c["proc_id"])
    total = store.contract_total(c["start"], c["end"], c["monthly"])
    b = store.balance(c["budget_item_id"], exclude_proc=c["proc_id"])
    it = store.budget_item(c["budget_item_id"])
    org = store.setting("org_name") or ""
    title = j["title"] if j else "งานบริการ"
    r = Report(store, "รายงานขอจ้าง", f"เลขที่ {p['number']}  วันที่ {TD.thai(p['date_request'])}")
    r.before = (
        f"<p>เรียน {_e(store.setting('head_pos') or 'หัวหน้าหน่วยงานของรัฐ')}</p>"
        + _p(f"ด้วย {_e(c['division'] or '')} {_e(org)} มีความประสงค์จะจ้างเหมาบริการบุคคลธรรมดา "
             f"งาน{_e(title)} ระยะเวลา {TD.thai(c['start'], False)} ถึง {TD.thai(c['end'], False)} "
             "ซึ่งได้รับอนุมัติเงินงบประมาณตามข้อบัญญัติงบประมาณรายจ่ายประจำปีงบประมาณ "
             f"พ.ศ. {it['fy']} {_e(it['plan'])} {_e(it['task'])} {_e(it['grp'])} หมวด{_e(it['category'])} "
             f"ประเภท{_e(it['type'])} รายการ{_e(it['name'])} งบหลังโอน {money(b['budget'])} บาท")
        + _p("เพื่อให้เป็นไปตามพระราชบัญญัติการจัดซื้อจัดจ้างและการบริหารพัสดุภาครัฐ พ.ศ. 2560 มาตรา 56 วรรคหนึ่ง (2) (ข) "
             "และระเบียบกระทรวงการคลังว่าด้วยการจัดซื้อจัดจ้างและการบริหารพัสดุภาครัฐ พ.ศ. 2560 ข้อ 22 ข้อ 79 "
             "จึงขอรายงานขอจ้าง ดังนี้")
        + "<table cellpadding=2 width='100%'>"
        + "".join(f"<tr><td width='36%' valign=top>{_e(k)}</td><td>{v}</td></tr>" for k, v in [
            ("1. เหตุผลและความจำเป็นที่จะจ้าง", _e(p["reason"])),
            ("2. ขอบเขตของงานหรือรายละเอียดคุณลักษณะเฉพาะ", "ตามขอบเขตของงาน (TOR) แนบท้าย"),
            ("3. ราคากลางของพัสดุที่จะจ้าง", f"{money(total)} บาท (ตามแบบ บก.06 แนบท้าย)"),
            ("4. วงเงินที่จะจ้าง", f"{money(total)} บาท ({baht_text(total)}) เดือนละ {money(c['monthly'])} บาท"),
            ("5. กำหนดเวลาที่ต้องการใช้พัสดุ", f"{TD.thai(c['start'], False)} ถึง {TD.thai(c['end'], False)}"),
            ("6. วิธีที่จะจ้างและเหตุผล", "วิธีเฉพาะเจาะจง เนื่องจากวงเงินไม่เกินที่กำหนดในกฎกระทรวง "
                                          "(มาตรา 56 วรรคหนึ่ง (2) (ข))"),
            ("7. หลักเกณฑ์การพิจารณาคัดเลือกข้อเสนอ", "เกณฑ์ราคา"),
            ("8. การขออนุมัติแต่งตั้งผู้ตรวจรับพัสดุ", _e(c["inspector"] or DOTS)),
            ("9. ตรวจสอบงบประมาณ", f"คงเหลือก่อนครั้งนี้ {money(b['available'])} บาท · ครั้งนี้ {money(total)} บาท · "
                                   f"คงเหลือหลังครั้งนี้ <b>{money(b['available'] - total)}</b> บาท"),
        ]) + "</table>"
        + _p("จึงเรียนมาเพื่อโปรดพิจารณา หากเห็นชอบขอได้โปรดอนุมัติให้ดำเนินการตามรายละเอียดข้างต้น "
             "และลงนามในคำสั่งแต่งตั้งผู้ตรวจรับพัสดุ"))
    r.signers = _signers_for(store, c["division_id"])
    return r


# ------------------------------------------------------------- 5. สัญญาจ้าง
def contract_doc(store, cid) -> Report:
    """แบบสัญญาจ้างงานบริการ (ประเภทจ้างเหมาบริการบุคคลธรรมดา) — ข้อความตามประกาศฯ (ฉบับที่ 3) 2569."""
    c = store.contract(cid)
    j = store.job(c["job_id"]) if c["job_id"] else None
    st = store.settings()
    org = st.get("org_name") or DOTS
    months = store.plan_months(c["start"], c["end"], c["monthly"])
    total = sum(m["amount"] for m in months)
    full_m = sum(1 for m in months if m["full"])
    part_d = sum(m["days"] for m in months if not m["full"])
    span = (f"{full_m} เดือน" if full_m else "") + (f" {part_d} วัน" if part_d else "")
    sign = TD.parse(c["sign_date"]) or TD.today()
    title = j["title"] if j else DOTS
    hours = j["work_hours"] if j else "วันจันทร์ถึงวันศุกร์ เวลา 08.30 น. ถึง 16.30 น."
    r = Report(store, f"สัญญาจ้างงานบริการ{title}", "(ประเภทจ้างเหมาบริการบุคคลธรรมดา)")
    r.before = (
        f"<p align=right>สัญญาเลขที่ {_e(c['contract_no'])}</p>"
        + _p(f"สัญญาฉบับนี้ทำขึ้น ณ {_e(org)} {_e(st.get('org_address') or '')} "
             f"เมื่อวันที่ {sign.day} เดือน {TD.MONTHS[sign.month - 1]} พ.ศ. {sign.year + 543} ระหว่าง {_e(org)} "
             f"โดย {_e(st.get('head') or DOTS)} {_e(st.get('head_pos') or '')} ซึ่งต่อไปในสัญญานี้เรียกว่า "
             f"“ผู้ว่าจ้าง” ฝ่ายหนึ่ง กับ {_e(c['person'])} อยู่บ้านเลขที่ {_e(c['address'] or DOTS)} "
             f"ผู้ถือบัตรประจำตัวประชาชนเลขที่ {_e(c['id_card'] or DOTS)} ดังปรากฏตามสำเนาบัตรประจำตัวประชาชน"
             "แนบท้ายสัญญานี้ ซึ่งต่อไปในสัญญานี้เรียกว่า “ผู้รับจ้าง” อีกฝ่ายหนึ่ง")
        + _p("คู่สัญญาได้ตกลงกันมีข้อความดังต่อไปนี้")
        + "<p><b>ข้อ 1 ข้อตกลงว่าจ้าง</b></p>"
        + _p(f"1.1 ผู้ว่าจ้างตกลงจ้างและผู้รับจ้างตกลงรับจ้างทำงานบริการ{_e(title)} "
             "ตามข้อกำหนดและเงื่อนไขแห่งสัญญานี้รวมทั้งเอกสารแนบท้ายสัญญา")
        + _p("1.2 ข้อตกลงว่าจ้างตามสัญญานี้มุ่งเน้นผลสำเร็จของงานที่จ้างเป็นสำคัญ และผู้รับจ้างมีหน้าที่รับผิดชอบ"
             "เฉพาะการทำงานที่จ้างให้สำเร็จ โดยไม่มีหน้าที่ทำงานอื่นให้แก่ผู้ว่าจ้างนอกเหนือจากงานที่ระบุไว้ในข้อ 1.1")
        + _p(f"1.3 สัญญานี้มีกำหนดระยะเวลาการจ้าง {span.strip()} "
             f"โดยผู้รับจ้างจะต้องเริ่มทำงานตั้งแต่วันที่ {TD.thai(c['start'], False)} ถึงวันที่ {TD.thai(c['end'], False)} "
             f"คิดเป็นเงินค่าจ้างตามสัญญาทั้งสิ้น {money(total)} บาท ({baht_text(total)}) "
             "ซึ่งได้รวมค่าภาษีอากรใด ๆ (ถ้ามี) และค่าใช้จ่ายทั้งปวงด้วยแล้ว")
        + _p("1.4 ผู้รับจ้างขอรับรองว่าผู้รับจ้างมีคุณสมบัติ ความสามารถ และทักษะในการทำงานที่จ้างให้สำเร็จ"
             "ตามวัตถุประสงค์ของสัญญานี้ และจะไม่กระทำการใดอันจะก่อให้เกิดความเสียหายต่อผู้ว่าจ้างและภาพลักษณ์ของผู้ว่าจ้าง")
        + "<p><b>ข้อ 2 เอกสารอันเป็นส่วนหนึ่งของสัญญา</b></p>"
        + _p("เอกสารแนบท้ายสัญญาดังต่อไปนี้ให้ถือเป็นส่วนหนึ่งของสัญญานี้ 2.1 ผนวก 1 (รายละเอียดของงานที่จ้างบริการ / "
             "ขอบเขตของงาน) จำนวน ..... หน้า 2.2 ผนวก 2 (ใบเสนอราคา) จำนวน ..... หน้า "
             "ความใดในเอกสารแนบท้ายสัญญาที่ขัดหรือแย้งกับข้อความในสัญญานี้ ให้ใช้ข้อความในสัญญานี้บังคับ "
             "และในกรณีที่เอกสารแนบท้ายสัญญาขัดแย้งกันเอง ผู้รับจ้างจะต้องปฏิบัติตามคำวินิจฉัยของผู้ว่าจ้าง "
             "คำวินิจฉัยของผู้ว่าจ้างให้ถือเป็นที่สุด และผู้รับจ้างไม่มีสิทธิเรียกร้องค่าจ้าง ค่าเสียหาย "
             "หรือค่าใช้จ่ายใด ๆ เพิ่มเติมจากผู้ว่าจ้างทั้งสิ้น")
        + "<p><b>ข้อ 3 การจ่ายเงินค่าจ้าง</b></p>"
        + _p(f"ผู้ว่าจ้างตกลงจ่ายค่าจ้างตามข้อ 1.3 ให้แก่ผู้รับจ้างรวมเป็นจำนวน {len(months)} งวด "
             f"โดยคิดเป็นรายเดือนตามเดือนปฏิทินในอัตราเดือนละ {money(c['monthly'])} บาท ({baht_text(c['monthly'])}) "
             "ซึ่งได้รวมค่าภาษีอากรใด ๆ (ถ้ามี) และค่าใช้จ่ายทั้งปวงด้วยแล้ว โดยจะจ่ายให้เมื่อผู้รับจ้างได้ทำงาน"
             "ที่จ้างบริการเสร็จเรียบร้อยตามสัญญาในแต่ละงวดเดือนปฏิทินนั้น ๆ และผู้ว่าจ้างหรือผู้แทนของผู้ว่าจ้าง"
             "ได้ตรวจรับงานในแต่ละเดือนไว้เรียบร้อยแล้ว")
        + _p("ในกรณีที่การจ้างบริการเดือนแรกและเดือนสุดท้ายเป็นการจ้างบริการไม่เต็มเดือนปฏิทิน ให้คิดค่าจ้างเป็นรายวัน"
             "ตามจำนวนวันที่จ้างบริการจริง โดยให้ถือว่าหนึ่งเดือนปฏิทินมี 30 (สามสิบ) วัน ซึ่งเมื่อคำนวณค่าจ้าง"
             f"ตามสัญญานี้เป็นรายวันจะคิดเป็นจำนวนเงินวันละ {money(c['monthly'] / 30)} บาท "
             f"({baht_text(round(c['monthly'] / 30, 2))})")
        + _p(f"การจ่ายเงินตามเงื่อนไขแห่งสัญญานี้ ผู้ว่าจ้างจะโอนเงินเข้าบัญชีเงินฝากธนาคารของผู้รับจ้าง "
             f"ชื่อธนาคาร {_e(c['bank'] or DOTS)} สาขา {_e(c['bank_branch'] or DOTS)} "
             f"ชื่อบัญชี {_e(c['account_name'] or c['person'])} เลขที่บัญชี {_e(c['account_no'] or DOTS)} "
             "ทั้งนี้ ผู้รับจ้างตกลงเป็นผู้รับภาระเงินค่าธรรมเนียมหรือค่าบริการอื่นใดเกี่ยวกับการโอน "
             "รวมทั้งค่าใช้จ่ายอื่นใด (ถ้ามี) ที่ธนาคารเรียกเก็บ และยินยอมให้มีการหักเงินดังกล่าวจากจำนวนเงินโอนในงวดนั้น ๆ")
        + "<p><b>ข้อ 4 กำหนดเวลาการทำงานและสิทธิของผู้ว่าจ้างในการบอกเลิกสัญญา</b></p>"
        + _p(f"ผู้ว่าจ้างมีสถานะเป็นองค์กรปกครองส่วนท้องถิ่น มีเวลาทำการตามปกติใน{_e(hours)} "
             "ซึ่งผู้รับจ้างตกลงที่จะทำงานที่จ้างตามสัญญานี้ภายในช่วงระยะเวลาทำการของผู้ว่าจ้างดังกล่าว "
             "เว้นแต่คู่สัญญาจะได้ตกลงกันไว้เป็นอย่างอื่นตามเอกสารแนบท้ายสัญญาผนวก 1 "
             "โดยมีกำหนดระยะเวลาตามข้อ 1.3")
        + _p("ถ้าผู้รับจ้างมิได้ลงมือทำงานภายในกำหนดเวลา หรือไม่สามารถทำงานได้ตามสัญญา หรือไม่สามารถทำงานให้แล้วเสร็จ"
             "ตามกำหนดเวลา หรือมีเหตุให้เชื่อได้ว่าผู้รับจ้างไม่สามารถทำงานได้ตามสัญญา หรือไม่สามารถทำงานให้แล้วเสร็จ"
             "ภายในกำหนดเวลา หรือจะแล้วเสร็จล่าช้าเกินกว่ากำหนดเวลา หรือผู้รับจ้างทำผิดสัญญาข้อใดข้อหนึ่ง "
             "หรือไม่เป็นไปตามเอกสารแนบท้ายสัญญาผนวก 1 ผู้ว่าจ้างมีสิทธิที่จะบอกเลิกสัญญานี้ได้ "
             "และการใช้สิทธิบอกเลิกสัญญานั้นไม่กระทบสิทธิของผู้ว่าจ้างที่จะเรียกค่าเสียหายจากผู้รับจ้างอีกด้วย "
             "การที่ผู้ว่าจ้างไม่ใช้สิทธิบอกเลิกสัญญาดังกล่าวข้างต้นนั้น ไม่เป็นเหตุให้ผู้รับจ้างพ้นจากความรับผิดตามสัญญา")
        + "<p><b>ข้อ 5 การจ้างช่วง</b></p>"
        + _p("ผู้รับจ้างต้องมาทำงานตามสัญญานี้ด้วยตนเอง และผู้รับจ้างจะต้องไม่เอางานทั้งหมดหรือแต่บางส่วนแห่งสัญญานี้"
             "ไปจ้างช่วงอีกทอดหนึ่ง")
        + "<p><b>ข้อ 6 ความรับผิดชอบของผู้รับจ้าง</b></p>"
        + _p("ในระหว่างการทำงานบริการตามสัญญานี้ ถ้าผู้รับจ้างได้กระทำการหรืองดเว้นกระทำการใด ๆ อันเป็นการละเมิด"
             "ต่อบุคคลหรือทรัพย์สินของผู้ว่าจ้างหรือของผู้อื่น ผู้รับจ้างจะต้องรับผิดชอบชดใช้ค่าสินไหมทดแทนที่เกิดขึ้น"
             "เต็มจำนวนทุกกรณีในบรรดาความเสียหายที่เกิดขึ้นทั้งสิ้น เว้นแต่ผู้รับจ้างจะพิสูจน์ได้ว่าความเสียหาย"
             "ดังกล่าวเกิดขึ้นเพราะเหตุสุดวิสัย ผู้รับจ้างจะต้องรับผิดต่ออุบัติเหตุ ความเสียหาย หรือภยันตรายใด ๆ "
             "อันเกิดจากการปฏิบัติงานของผู้รับจ้าง ความเสียหายใด ๆ อันเกิดแก่งานที่ผู้รับจ้างได้ทำขึ้น "
             "แม้จะเกิดขึ้นเพราะเหตุสุดวิสัยก็ตาม ผู้รับจ้างจะต้องรับผิดชอบโดยซ่อมแซมหรือแก้ไขให้คืนดีหรือเปลี่ยน"
             "ให้ใหม่โดยค่าใช้จ่ายของผู้รับจ้างเองทั้งสิ้น เว้นแต่ความเสียหายนั้นเกิดจากความผิดของผู้ว่าจ้าง "
             "หากผู้ว่าจ้างถูกเรียกร้องหรือฟ้องร้องหรือต้องชดใช้ค่าเสียหายให้แก่บุคคลภายนอกไปแล้ว ผู้รับจ้าง"
             "จะต้องดำเนินการใด ๆ เพื่อให้มีการว่าต่างแก้ต่างให้แก่ผู้ว่าจ้างโดยค่าใช้จ่ายของผู้รับจ้างเอง "
             "รวมทั้งผู้รับจ้างจะต้องชดใช้ค่าเสียหายนั้น ๆ ตลอดจนค่าใช้จ่ายใด ๆ อันเกิดจากการถูกเรียกร้องหรือ"
             "ถูกฟ้องร้องให้แก่ผู้ว่าจ้างทันที")
        + "<p><b>ข้อ 7 การตรวจรับงานจ้างบริการ</b></p>"
        + _p("เมื่อผู้ว่าจ้างได้ตรวจรับงานจ้างบริการที่ส่งมอบและเห็นว่าถูกต้องครบถ้วนเป็นไปตามสัญญาแล้ว ผู้ว่าจ้าง"
             "จะออกหลักฐานการรับมอบเป็นหนังสือไว้ให้ เพื่อผู้รับจ้างนำมาเป็นหลักฐานประกอบการขอรับเงินค่างานจ้างบริการนั้น "
             "ถ้าผลของการตรวจรับงานจ้างบริการปรากฏว่างานจ้างบริการที่ผู้รับจ้างส่งมอบไม่ถูกต้องครบถ้วน "
             "หรือไม่เป็นไปตามสัญญา ผู้ว่าจ้างทรงไว้ซึ่งสิทธิที่จะไม่รับงานจ้างบริการนั้น ในกรณีที่ผู้รับจ้าง"
             "ส่งมอบงานจ้างบริการถูกต้องแต่ไม่ครบจำนวน หรือส่งมอบครบจำนวนแต่ไม่ถูกต้องทั้งหมด ผู้ว่าจ้าง"
             "จะตรวจรับงานจ้างบริการเฉพาะส่วนที่ถูกต้องก็ได้ โดยคำนวณค่าจ้างเป็นอัตราค่าจ้างเฉลี่ยรายวัน"
             "เฉพาะวันที่ผู้รับจ้างได้ส่งมอบงานครบถ้วน")
        + "<p><b>ข้อ 8 การบังคับค่าเสียหาย และค่าใช้จ่าย</b></p>"
        + _p("ในกรณีที่ผู้รับจ้างกระทำการใด ๆ ก็ตาม จนเป็นเหตุให้เกิดค่าเสียหายหรือค่าใช้จ่ายแก่ผู้ว่าจ้าง ผู้รับจ้าง"
             "ต้องชดใช้ค่าเสียหาย หรือค่าใช้จ่ายดังกล่าวให้แก่ผู้ว่าจ้างโดยสิ้นเชิง เมื่อได้รับแจ้งเป็นหนังสือจากผู้ว่าจ้าง "
             "หากผู้รับจ้างไม่ชดใช้ให้ถูกต้องครบถ้วน ให้ผู้ว่าจ้างมีสิทธิที่จะหักเอาจากจำนวนเงินค่าจ้างบริการ"
             "ที่ต้องชำระตามสัญญาได้ทันที นอกจากนี้ ผู้รับจ้างจะต้องรับผิดชอบในค่าเสียหายและค่าใช้จ่ายที่เพิ่มขึ้นทั้งหมด "
             "หากบังคับค่าเสียหาย หรือค่าใช้จ่ายจากเงินค่าจ้างที่ต้องชำระแล้วยังไม่เพียงพอ ผู้รับจ้างยินยอมชำระ"
             "ส่วนที่เหลือที่ยังขาดอยู่จนครบถ้วนตามจำนวนค่าเสียหาย หรือค่าใช้จ่ายนั้น ภายในกำหนด 15 (สิบห้า) วัน "
             "นับถัดจากวันที่ได้รับแจ้งเป็นหนังสือจากผู้ว่าจ้าง หากมีเงินค่าจ้างตามสัญญาที่หักไว้จ่ายเป็นค่าเสียหาย "
             "หรือค่าใช้จ่ายแล้ว ยังเหลืออยู่อีกเท่าใด ผู้ว่าจ้างจะคืนให้แก่ผู้รับจ้างทั้งหมดโดยไม่มีดอกเบี้ย "
             "ภายใน 15 (สิบห้า) วัน นับถัดจากวันที่หักค่าเสียหายหรือค่าใช้จ่ายเสร็จเรียบร้อยแล้ว")
        + _p("สัญญานี้ทำขึ้นเป็นสองฉบับ มีข้อความถูกต้องตรงกัน คู่สัญญาได้อ่านและเข้าใจข้อความโดยละเอียดตลอดแล้ว "
             "จึงได้ลงลายมือชื่อพร้อมทั้งประทับตรา (ถ้ามี) ไว้เป็นสำคัญต่อหน้าพยาน และคู่สัญญาต่างยึดถือไว้ฝ่ายละหนึ่งฉบับ"))
    r.signers = [("ผู้ว่าจ้าง", st.get("head"), st.get("head_pos")), ("ผู้รับจ้าง", c["person"], ""),
                 ("พยาน", "", ""), ("พยาน", "", "")]
    r.after = ("<p style='font-size:10pt'>แบบสัญญาตามประกาศคณะกรรมการนโยบายการจัดซื้อจัดจ้างและการบริหารพัสดุภาครัฐ "
               "เรื่อง แบบสัญญาเกี่ยวกับการจัดซื้อจัดจ้างฯ (ฉบับที่ 3) ราชกิจจานุเบกษา 21 กันยายน 2569 · "
               "ผนวก 1 รายละเอียดของงานที่จ้างบริการต้องสอดคล้องกับแบบสัญญานี้ (หนังสือ ว 727)</p>")
    return r


# -------------------------------------------------- 6. ตรวจรับ/ขอเบิกรายเดือน
def monthly_inspection(store, cid, month) -> Report:
    c = store.contract(cid)
    m = store.one("SELECT * FROM hire_months WHERE contract_id=? AND month=?", (cid, month))
    j = store.job(c["job_id"]) if c["job_id"] else None
    title = j["title"] if j else "งานบริการ"
    full = m["days"] == m["planned_days"]
    r = Report(store, "ใบตรวจรับงานจ้างเหมาบริการ และขอเบิกเงิน",
               f"สัญญาเลขที่ {c['contract_no']} · งวดเดือน {month_name(month)}")
    r.header = ["รายการ", "วันทำงานตามสัญญา", "วันที่ส่งมอบงานครบถ้วน", "อัตราค่าจ้าง", "จำนวนเงิน"]
    r.align = ["left", "center", "center", "right", "right"]
    rate = f"เดือนละ {money(c['monthly'])}" if full and m["planned_days"] == 30 else f"วันละ {money(c['monthly'] / 30)}"
    r.rows = [[f"จ้างเหมาบริการ{title} ({c['person']})", m["planned_days"], m["days"], rate, float(m["amount"])]]
    r.totals = ["รวมเป็นเงิน", "", "", "", float(m["amount"])]
    r.before = _p(
        f"ตามที่ {_e(store.setting('org_name') or '')} ได้ทำสัญญาจ้าง {_e(c['person'])} ให้{_e(title)} "
        f"สังกัด {_e(c['division'] or '')} ตั้งแต่วันที่ {TD.thai(c['start'], False)} ถึงวันที่ {TD.thai(c['end'], False)} "
        f"อัตราเดือนละ {money(c['monthly'])} บาท นั้น ผู้ตรวจรับพัสดุได้ตรวจรับงานประจำเดือน{month_name(month)} "
        f"เมื่อวันที่ {TD.thai(m['inspect_date'], False) if m['inspect_date'] else DOTS} แล้ว "
        + ("ปรากฏว่าผู้รับจ้างได้ปฏิบัติงานถูกต้องครบถ้วนตามสัญญา" if full else
           f"ปรากฏว่าผู้รับจ้างส่งมอบงานครบถ้วน {m['days']} วัน จาก {m['planned_days']} วัน "
           "จึงตรวจรับเฉพาะส่วนที่ถูกต้อง โดยคำนวณค่าจ้างเป็นอัตราเฉลี่ยรายวันตามสัญญาข้อ 7")
        + f" จึงขอเบิกเงินค่าจ้างจำนวน {money(m['amount'])} บาท ({baht_text(m['amount'])})")
    r.after = "" if not m["note"] else f"<p>หมายเหตุ: {_e(m['note'])}</p>"
    r.signers = [("ผู้ตรวจรับพัสดุ", c["inspector"], "")] + _signers_for(store, c["division_id"])[:2]
    return r


def hire_register(store, fy, division_id=None) -> Report:
    r = Report(store, "ทะเบียนคุมสัญญาจ้างเหมาบริการบุคคลธรรมดา", f"ปีงบประมาณ พ.ศ. {fy}", landscape=True)
    r.header = ["สัญญาเลขที่", "กอง", "งาน", "ผู้รับจ้าง", "ระยะเวลา", "ค่าจ้าง/เดือน", "ตามสัญญา", "จ่ายแล้ว",
                "คงค้าง", "สถานะ"]
    r.align = ["left", "left", "left", "left", "center", "right", "right", "right", "right", "center"]
    t = [0.0, 0.0, 0.0]
    for c in store.contracts(fy, division_id):
        if c["status"] == "ยกเลิก":
            continue
        total = store.contract_total(c["start"], c["end"], c["monthly"])
        paid = store.paid(c["proc_id"]) if c["proc_id"] else 0
        left = total - paid if c["status"] != "สิ้นสุด" else 0
        r.rows.append([c["contract_no"], c["division"], c["job"], c["person"],
                       f"{TD.thai(c['start'])} – {TD.thai(c['end'])}", float(c["monthly"]), float(total),
                       float(paid), float(left), c["status"]])
        t = [t[0] + total, t[1] + paid, t[2] + left]
    r.totals = ["", "", "", "รวม", "", "", *t, ""]
    return r


def division_summary(store, fy) -> Report:
    r = Report(store, "สรุปงบจ้างเหมาบริการบุคคลภายนอกแยกตามกอง", f"ปีงบประมาณ พ.ศ. {fy}", landscape=True)
    r.header = ["กอง", "งบหลังโอน", "จอง/ผูกพัน", "เบิกจ่ายแล้ว", "คงเหลือ", "สัญญา", "ค่าจ้างต่อเดือน (ที่มีผล)"]
    r.align = ["left", "right", "right", "right", "right", "center", "right"]
    t = [0.0] * 4
    for x in store.hire_summary(fy):
        vals = [x["budget"], x["committed"], x["paid"], x["available"]]
        r.rows.append([x["division"]["name"], *[float(v) for v in vals], x["contracts"], float(x["monthly"])])
        t = [a + b for a, b in zip(t, vals)]
    r.totals = ["รวม", *t, "", ""]
    return r


__all__ = ["THAI_DIGITS"]
