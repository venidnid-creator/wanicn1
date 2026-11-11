# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2569 (2026) นายเวนิช ธัมมะวงษ์ วิศวกรสำรวจ — ReadWanicn2027
"""งานสารบรรณ: the official letters and registers of the Prime Minister's
Office Regulation on Correspondence (ระเบียบสำนักนายกรัฐมนตรีว่าด้วยงานสารบรรณ
พ.ศ. ๒๕๒๖ and its amendments ฉบับที่ ๒ ๒๕๔๘, ๓ ๒๕๖๐, ๔ ๒๕๖๔).

* Six kinds of letter, ten forms: ภายนอก, ภายใน, ประทับตรา, สั่งการ (คำสั่ง
  ระเบียบ ข้อบังคับ), ประชาสัมพันธ์ (ประกาศ แถลงการณ์ ข่าว), and the records
  an officer makes or receives (หนังสือรับรอง รายงานการประชุม บันทึก) -- each
  as HTML for the document editor, filled from the fields the user typed,
  in TH SarabunPSK 16 pt with the Garuda where the form has one.
* The registers of ข้อ ๒๙/๑ (ฉบับที่ ๔) as spreadsheet column sets.
* File names of ภาคผนวก ๗ (ปีพุทธศักราช_รหัสส่วนราชการ_เลขที่.pdf) and the
  Roman codes of the ministries and provinces listed there.

The layouts follow the regulation's forms as commonly used; the 2526
regulation's own sheets (แบบที่ ๑ ...) are the reference to check against.
"""
from __future__ import annotations

import html
from dataclasses import dataclass

FONT = "TH SarabunPSK"
#: Shown when TH SarabunPSK is not installed: TLWG's free version of it.
FONT_FALLBACK = "Laksaman"
SIZE_PT = 16
THAI_DIGITS = str.maketrans("0123456789", "๐๑๒๓๔๕๖๗๘๙")


def thai_digits(text: str) -> str:
    return text.translate(THAI_DIGITS)


@dataclass(frozen=True)
class Form:
    key: str
    group: str                    # the six kinds
    name: str
    garuda: str                   # "big" (3 cm), "small" (1.5 cm) or ""
    fields: tuple                 # (key, label, default)


_COMMON_SIGN = (("signer", "ชื่อผู้ลงนาม (ตัวบรรจง)", "(.................................)"),
                ("position", "ตำแหน่ง", "................................."))

FORMS = (
    Form("external", "๑. หนังสือภายนอก", "หนังสือภายนอก", "big", (
        ("no", "ที่", "ศธ ........./........"),
        ("office", "ส่วนราชการเจ้าของหนังสือ และที่ตั้ง", "ส่วนราชการ ...................\nที่ตั้ง ..................."),
        ("date", "วัน เดือน ปี", "................................."),
        ("subject", "เรื่อง", "................................."),
        ("to", "เรียน", "................................."),
        ("ref", "อ้างถึง (ถ้ามี)", ""),
        ("enclosure", "สิ่งที่ส่งมาด้วย (ถ้ามี)", ""),
        ("body", "ข้อความ", "ตามที่ ...................................................\n"
                            "บัดนี้ ...................................................\n"
                            "จึงเรียนมาเพื่อโปรดทราบ"),
        ("closing", "คำลงท้าย", "ขอแสดงความนับถือ"),
        *_COMMON_SIGN,
        ("owner", "ส่วนราชการเจ้าของเรื่อง", "................................."),
        ("tel", "โทร.", ""), ("fax", "โทรสาร", ""), ("email", "ไปรษณีย์อิเล็กทรอนิกส์", ""),
        ("copy", "สำเนาส่ง (ถ้ามี)", ""))),
    Form("internal", "๒. หนังสือภายใน", "หนังสือภายใน (บันทึกข้อความ)", "small", (
        ("office", "ส่วนราชการ", "................................."),
        ("no", "ที่", "................................."),
        ("date", "วันที่", "................................."),
        ("subject", "เรื่อง", "................................."),
        ("to", "เรียน", "................................."),
        ("body", "ข้อความ", "...................................................\n"
                            "จึงเรียนมาเพื่อโปรดพิจารณา"),
        *_COMMON_SIGN)),
    Form("stamped", "๓. หนังสือประทับตรา", "หนังสือประทับตรา", "big", (
        ("no", "ที่", "................................."),
        ("to", "ถึง", "................................."),
        ("body", "ข้อความ", "..................................................."),
        ("office", "ส่วนราชการที่ส่งหนังสือออก", "................................."),
        ("date", "วัน เดือน ปี", "................................."),
        ("owner", "ส่วนราชการเจ้าของเรื่อง", "................................."),
        ("tel", "โทร.", ""), ("fax", "โทรสาร", ""), ("email", "ไปรษณีย์อิเล็กทรอนิกส์", ""))),
    Form("order", "๔. หนังสือสั่งการ", "๔.๑ คำสั่ง", "big", (
        ("office", "ส่วนราชการที่ออกคำสั่ง", "................................."),
        ("no", "ที่ (เลขที่/ปี)", "........../........"),
        ("subject", "เรื่อง", "................................."),
        ("body", "ข้อความ", "...................................................\n"
                            "ทั้งนี้ ตั้งแต่ ................................. เป็นต้นไป"),
        ("date", "สั่ง ณ วันที่", "................................."),
        *_COMMON_SIGN)),
    Form("regulation", "๔. หนังสือสั่งการ", "๔.๒ ระเบียบ", "big", (
        ("office", "ส่วนราชการที่ออกระเบียบ", "................................."),
        ("subject", "ว่าด้วย", "................................."),
        ("edition", "ฉบับที่ (ถ้ามี)", ""),
        ("year", "พ.ศ.", "........"),
        ("body", "ข้อความ (เหตุผลและอำนาจ แล้วเป็นข้อ ๆ)",
         "โดยที่เป็นการสมควร ...................................................\n"
         "อาศัยอำนาจตามความใน ................................. จึงวางระเบียบไว้ ดังต่อไปนี้\n"
         "ข้อ ๑ ระเบียบนี้เรียกว่า \"................................................\"\n"
         "ข้อ ๒ ระเบียบนี้ให้ใช้บังคับตั้งแต่ ................................. เป็นต้นไป\n"
         "ข้อ ๓ ..................................................."),
        ("date", "ประกาศ ณ วันที่", "................................."),
        *_COMMON_SIGN)),
    Form("bylaw", "๔. หนังสือสั่งการ", "๔.๓ ข้อบังคับ", "big", (
        ("office", "ส่วนราชการที่ออกข้อบังคับ", "................................."),
        ("subject", "ว่าด้วย", "................................."),
        ("edition", "ฉบับที่ (ถ้ามี)", ""),
        ("year", "พ.ศ.", "........"),
        ("body", "ข้อความ (เหตุผลและอำนาจ แล้วเป็นข้อ ๆ)",
         "โดยที่เป็นการสมควร ...................................................\n"
         "อาศัยอำนาจตามความใน ................................. จึงวางข้อบังคับไว้ ดังต่อไปนี้\n"
         "ข้อ ๑ ข้อบังคับนี้เรียกว่า \"................................................\"\n"
         "ข้อ ๒ ข้อบังคับนี้ให้ใช้บังคับตั้งแต่ ................................. เป็นต้นไป\n"
         "ข้อ ๓ ..................................................."),
        ("date", "ประกาศ ณ วันที่", "................................."),
        *_COMMON_SIGN)),
    Form("announcement", "๕. หนังสือประชาสัมพันธ์", "๕.๑ ประกาศ", "big", (
        ("office", "ส่วนราชการที่ออกประกาศ", "................................."),
        ("subject", "เรื่อง", "................................."),
        ("body", "ข้อความ", "..................................................."),
        ("date", "ประกาศ ณ วันที่", "................................."),
        *_COMMON_SIGN)),
    Form("statement", "๕. หนังสือประชาสัมพันธ์", "๕.๒ แถลงการณ์", "big", (
        ("office", "ส่วนราชการที่ออกแถลงการณ์", "................................."),
        ("subject", "เรื่อง", "................................."),
        ("edition", "ฉบับที่", "........"),
        ("body", "ข้อความ", "..................................................."),
        ("issuer", "ส่วนราชการ (ท้ายแถลงการณ์)", "................................."),
        ("date", "วัน เดือน ปี", "................................."))),
    Form("news", "๕. หนังสือประชาสัมพันธ์", "๕.๓ ข่าว", "", (
        ("office", "ส่วนราชการที่ออกข่าว", "................................."),
        ("subject", "เรื่อง", "................................."),
        ("edition", "ฉบับที่", "........"),
        ("body", "ข้อความ", "..................................................."),
        ("issuer", "ส่วนราชการ (ท้ายข่าว)", "................................."),
        ("date", "วัน เดือน ปี", "................................."))),
    Form("certificate", "๖. หนังสือที่เจ้าหน้าที่ทำขึ้นหรือรับไว้เป็นหลักฐานในราชการ",
         "๖.๑ หนังสือรับรอง", "big", (
             ("no", "ที่", "................................."),
             ("office", "ส่วนราชการ และที่ตั้ง", "................................."),
             ("body", "ข้อความ", "หนังสือฉบับนี้ให้ไว้เพื่อรับรองว่า .................................\n"
                                 "..................................................."),
             ("date", "ให้ไว้ ณ วันที่", "................................."),
             *_COMMON_SIGN)),
    Form("minutes", "๖. หนังสือที่เจ้าหน้าที่ทำขึ้นหรือรับไว้เป็นหลักฐานในราชการ",
         "๖.๒ รายงานการประชุม", "", (
             ("subject", "รายงานการประชุม (ชื่อคณะที่ประชุม)", "................................."),
             ("edition", "ครั้งที่", "......./......."),
             ("date", "เมื่อ (วัน เดือน ปี)", "................................."),
             ("place", "ณ", "................................."),
             ("present", "ผู้มาประชุม", "๑. ................................. ประธาน\n๒. ................................."),
             ("absent", "ผู้ไม่มาประชุม (ถ้ามี)", ""),
             ("guests", "ผู้เข้าร่วมประชุม (ถ้ามี)", ""),
             ("start", "เริ่มประชุมเวลา", "........ น."),
             ("body", "ข้อความ", "ระเบียบวาระที่ ๑ .................................\n"
                                 "ระเบียบวาระที่ ๒ ................................."),
             ("end", "เลิกประชุมเวลา", "........ น."),
             ("signer", "ผู้จดรายงานการประชุม", "(.................................)"))),
    Form("memo", "๖. หนังสือที่เจ้าหน้าที่ทำขึ้นหรือรับไว้เป็นหลักฐานในราชการ",
         "๖.๓ บันทึก", "", (
             ("to", "เรียน (ผู้บังคับบัญชา)", "................................."),
             ("body", "ข้อความ", "..................................................."),
             *_COMMON_SIGN,
             ("date", "วัน เดือน ปี", "................................."))),
)
GROUPS = tuple(dict.fromkeys(f.group for f in FORMS))
BY_KEY = {f.key: f for f in FORMS}


def defaults(form: Form) -> dict:
    return {k: v for k, _label, v in form.fields}


# -- HTML for the editor --------------------------------------------------------------

def _e(text: str) -> str:
    return html.escape(text or "").replace("\n", "<br>")


def _p(text, align="left", indent_cm=0.0, bold=False, size=SIZE_PT, top=0, left_cm=0.0) -> str:
    style = (f"margin:{top}px 0 0 0; text-align:{align}; font-size:{size}pt;"
             f" text-indent:{indent_cm}cm; margin-left:{left_cm}cm;")
    inner = f"<b>{text}</b>" if bold else text
    return f'<p style="{style}">{inner}</p>'


def _body(text: str) -> str:
    """Each paragraph of the body indented 2.5 cm, as the regulation sets it."""
    return "".join(_p(_e(line), "justify", 2.5) for line in (text or "").split("\n") if line.strip())


def _line_row(label: str, value: str) -> str:
    return _p(f"<b>{label}</b>&nbsp;&nbsp;{_e(value)}") if value else ""


def _garuda(size: str, garuda_uri: str) -> str:
    if not size:
        return ""
    cm = 3.0 if size == "big" else 1.5
    px = int(cm / 2.54 * 96)
    return f'<img src="{garuda_uri}" width="{px}" height="{int(px * 1.09)}">'


def _sign_block(v: dict, closing: str = "") -> str:
    out = ""
    if closing:
        out += _p(_e(closing), "center", top=18, left_cm=6)
    out += _p("&nbsp;", top=24) + _p("&nbsp;")
    out += _p(_e(v.get("signer", "")), "center", left_cm=6)
    out += _p(_e(v.get("position", "")), "center", left_cm=6)
    return out


def _two_cols(left: str, right: str) -> str:
    return ('<table width="100%" cellspacing="0" cellpadding="0" style="border:none">'
            f'<tr><td width="50%" valign="bottom">{left}</td>'
            f'<td width="50%" valign="bottom" align="right">{right}</td></tr></table>')


def _contacts(v: dict) -> str:
    out = ""
    for key, label in (("owner", ""), ("tel", "โทร. "), ("fax", "โทรสาร "), ("email", "ไปรษณีย์อิเล็กทรอนิกส์ ")):
        if v.get(key):
            out += _p(_e(label + v[key]), size=SIZE_PT)
    return out


def render(form_key: str, values: dict | None = None, garuda_uri: str = "garuda",
           thai_numbers: bool = False) -> str:
    """The letter as HTML, ready for the document editor."""
    form = BY_KEY[form_key]
    v = defaults(form)
    v.update({k: x for k, x in (values or {}).items() if x is not None})
    if thai_numbers:
        v = {k: thai_digits(x) for k, x in v.items()}
    g = _garuda(form.garuda, garuda_uri)
    k = form.key
    parts = []
    if k == "external":
        parts.append(_p(g, "center"))
        office = _e(v["office"])
        parts.append(_two_cols(_p(_e("ที่ " + v["no"])), _p(office, "left", left_cm=0)))
        parts.append(_p(_e(v["date"]), "center", top=8, left_cm=4))
        parts.append(_line_row("เรื่อง", v["subject"]))
        parts.append(_line_row("เรียน", v["to"]))
        parts.append(_line_row("อ้างถึง", v.get("ref", "")))
        parts.append(_line_row("สิ่งที่ส่งมาด้วย", v.get("enclosure", "")))
        parts.append(_body(v["body"]))
        parts.append(_sign_block(v, v.get("closing", "ขอแสดงความนับถือ")))
        parts.append(_contacts(v))
        if v.get("copy"):
            parts.append(_p(_e("สำเนาส่ง " + v["copy"]), top=12))
    elif k == "internal":
        title = '<span style="font-size:29pt"><b>บันทึกข้อความ</b></span>'
        parts.append('<table width="100%" cellspacing="0" cellpadding="0"><tr>'
                     f'<td width="20%" valign="middle">{g}</td>'
                     f'<td width="60%" align="center" valign="middle">{title}</td>'
                     '<td width="20%"></td></tr></table>')
        parts.append(_p(f'<b><span style="font-size:20pt">ส่วนราชการ</span></b>&nbsp;&nbsp;{_e(v["office"])}'))
        parts.append(_two_cols(_p(f'<b><span style="font-size:20pt">ที่</span></b>&nbsp;&nbsp;{_e(v["no"])}'),
                               _p(f'<b><span style="font-size:20pt">วันที่</span></b>&nbsp;&nbsp;{_e(v["date"])}')))
        parts.append(_p(f'<b><span style="font-size:20pt">เรื่อง</span></b>&nbsp;&nbsp;{_e(v["subject"])}'))
        parts.append(_p("<hr>"))
        parts.append(_line_row("เรียน", v["to"]))
        parts.append(_body(v["body"]))
        parts.append(_sign_block(v))
    elif k == "stamped":
        parts.append(_p(g, "center"))
        parts.append(_p(_e("ที่ " + v["no"])))
        parts.append(_p(_e("ถึง " + v["to"]), top=8))
        parts.append(_body(v["body"]))
        parts.append(_p(_e(v["office"]), "center", top=24, left_cm=6))
        parts.append(_p(_e(v["date"]), "center", left_cm=6))
        parts.append(_p("(ประทับตราชื่อส่วนราชการ และลงชื่อย่อกำกับตรา)", "center", left_cm=6, size=14))
        parts.append(_contacts(v))
    elif k in ("order", "announcement"):
        head = "คำสั่ง" if k == "order" else "ประกาศ"
        parts.append(_p(g, "center"))
        parts.append(_p(_e(f"{head}{v['office']}"), "center", bold=True))
        if k == "order":
            parts.append(_p(_e("ที่ " + v["no"]), "center", bold=True))
        parts.append(_p(_e("เรื่อง " + v["subject"]), "center", bold=True))
        parts.append(_p("──────────────", "center"))
        parts.append(_body(v["body"]))
        word = "สั่ง ณ วันที่" if k == "order" else "ประกาศ ณ วันที่"
        parts.append(_p(_e(f"{word} {v['date']}"), "center", top=18, left_cm=3))
        parts.append(_sign_block(v))
    elif k in ("regulation", "bylaw"):
        head = "ระเบียบ" if k == "regulation" else "ข้อบังคับ"
        parts.append(_p(g, "center"))
        parts.append(_p(_e(f"{head}{v['office']}"), "center", bold=True))
        parts.append(_p(_e("ว่าด้วย" + v["subject"]), "center", bold=True))
        if v.get("edition"):
            parts.append(_p(_e(f"(ฉบับที่ {v['edition']})"), "center", bold=True))
        parts.append(_p(_e("พ.ศ. " + v["year"]), "center", bold=True))
        parts.append(_p("──────────────", "center"))
        parts.append(_body(v["body"]))
        parts.append(_p(_e(f"ประกาศ ณ วันที่ {v['date']}"), "center", top=18, left_cm=3))
        parts.append(_sign_block(v))
    elif k in ("statement", "news"):
        head = "แถลงการณ์" if k == "statement" else "ข่าว"
        if g:
            parts.append(_p(g, "center"))
        parts.append(_p(_e(f"{head}{v['office']}"), "center", bold=True))
        parts.append(_p(_e("เรื่อง " + v["subject"]), "center", bold=True))
        parts.append(_p(_e("ฉบับที่ " + v["edition"]), "center", bold=True))
        parts.append(_p("──────────────", "center"))
        parts.append(_body(v["body"]))
        parts.append(_p(_e(v["issuer"]), "center", top=18, left_cm=6))
        parts.append(_p(_e(v["date"]), "center", left_cm=6))
    elif k == "certificate":
        parts.append(_p(g, "center"))
        parts.append(_two_cols(_p(_e("ที่ " + v["no"])), _p(_e(v["office"]))))
        parts.append(_body(v["body"]))
        parts.append(_p(_e(f"ให้ไว้ ณ วันที่ {v['date']}"), "center", top=18, left_cm=3))
        parts.append(_sign_block(v))
    elif k == "minutes":
        parts.append(_p(_e("รายงานการประชุม" + v["subject"]), "center", bold=True))
        parts.append(_p(_e("ครั้งที่ " + v["edition"]), "center", bold=True))
        parts.append(_p(_e("เมื่อ " + v["date"]), "center", bold=True))
        parts.append(_p(_e("ณ " + v["place"]), "center", bold=True))
        parts.append(_p("──────────────", "center"))
        for key, label in (("present", "ผู้มาประชุม"), ("absent", "ผู้ไม่มาประชุม"),
                           ("guests", "ผู้เข้าร่วมประชุม")):
            if v.get(key):
                parts.append(_p(f"<b>{label}</b>", top=6))
                parts.append("".join(_p(_e(x), left_cm=1) for x in v[key].split("\n")))
        parts.append(_p(_e("เริ่มประชุมเวลา " + v["start"]), top=6))
        parts.append(_body(v["body"]))
        parts.append(_p(_e("เลิกประชุมเวลา " + v["end"]), top=6))
        parts.append(_p("&nbsp;", top=18))
        parts.append(_p(_e(v["signer"]), "center", left_cm=6))
        parts.append(_p("ผู้จดรายงานการประชุม", "center", left_cm=6))
    elif k == "memo":
        parts.append(_line_row("เรียน", v["to"]))
        parts.append(_body(v["body"]))
        parts.append(_sign_block(v))
        parts.append(_p(_e(v["date"]), "center", left_cm=6))
    body = "".join(x for x in parts if x)
    return (f'<html><body style="font-family:\'{FONT}\',\'{FONT_FALLBACK}\';'
            f' font-size:{SIZE_PT}pt;">{body}</body></html>')


# -- registers (ข้อ ๒๙/๑) --------------------------------------------------------------

REGISTERS = {
    "ทะเบียนหนังสือรับ": ["เลขทะเบียนรับ", "ที่", "ลงวันที่", "จาก", "ถึง", "เรื่อง", "การปฏิบัติ", "หมายเหตุ"],
    "ทะเบียนหนังสือส่ง": ["เลขทะเบียนส่ง", "ที่", "ลงวันที่", "จาก", "ถึง", "เรื่อง", "การปฏิบัติ", "หมายเหตุ"],
    "บัญชีหนังสือส่งเก็บ": ["ลำดับที่", "ที่", "ลงวันที่", "เรื่อง", "รหัสแฟ้ม", "กำหนดเก็บ", "หมายเหตุ"],
    "ทะเบียนหนังสือเก็บ": ["ลำดับที่", "วัน เดือน ปี", "ที่", "ลงวันที่", "เรื่อง", "รหัสแฟ้ม",
                           "เก็บถึง พ.ศ.", "หมายเหตุ"],
    "บัญชีส่งมอบหนังสือครบ ๒๐ ปี": ["ลำดับที่", "รหัสแฟ้ม", "ที่", "ลงวันที่", "เลขทะเบียนรับ",
                                    "เรื่อง", "หมายเหตุ"],
    "บัญชีหนังสือครบ ๒๐ ปีที่ขอเก็บเอง": ["ลำดับที่", "รหัสแฟ้ม", "ที่", "ลงวันที่", "เรื่อง", "หมายเหตุ"],
    "บัญชีฝากหนังสือ": ["ลำดับที่", "รหัสแฟ้ม", "ที่", "ลงวันที่", "เรื่อง", "กำหนดเก็บ", "หมายเหตุ"],
    "บัญชีหนังสือขอทำลาย": ["ลำดับที่", "รหัสแฟ้ม", "ที่", "ลงวันที่", "เรื่อง", "การพิจารณา", "หมายเหตุ"],
}

#: Keeping periods of ข้อ ๕๗ (ฉบับที่ ๒), for the «กำหนดเก็บ» column.
RETENTION = ("ไม่น้อยกว่า ๑๐ ปี (ปกติ)", "ไม่น้อยกว่า ๕ ปี (คู่สำเนาที่มีต้นเรื่องค้นได้จากที่อื่น)",
             "ไม่น้อยกว่า ๑ ปี (เรื่องธรรมดาสามัญที่เกิดเป็นประจำ)",
             "ไม่น้อยกว่า ๕ ปี (เอกสารการเงินที่ สตง. ตรวจแล้ว)", "เก็บตลอดไป (คุณค่าทางประวัติศาสตร์)",
             "ตามกฎหมาย/ระเบียบเฉพาะ (หนังสือลับ หลักฐานทางอรรถคดี)")

# -- ภาคผนวก ๗: file names and codes ------------------------------------------------------

MINISTRIES = {
    "สำนักนายกรัฐมนตรี": "OPM", "กระทรวงกลาโหม": "MOD", "กระทรวงการคลัง": "MOF",
    "กระทรวงการต่างประเทศ": "MFA", "กระทรวงการท่องเที่ยวและกีฬา": "MOTS",
    "กระทรวงการพัฒนาสังคมและความมั่นคงของมนุษย์": "SDHS",
    "กระทรวงการอุดมศึกษา วิทยาศาสตร์ วิจัยและนวัตกรรม": "HESI", "กระทรวงเกษตรและสหกรณ์": "MOAC",
    "กระทรวงคมนาคม": "MOT", "กระทรวงดิจิทัลเพื่อเศรษฐกิจและสังคม": "MDES",
    "กระทรวงทรัพยากรธรรมชาติและสิ่งแวดล้อม": "MNRE", "กระทรวงพลังงาน": "MENE",
    "กระทรวงพาณิชย์": "MOC", "กระทรวงมหาดไทย": "MOI", "กระทรวงยุติธรรม": "MOJ",
    "กระทรวงแรงงาน": "MOL", "กระทรวงวัฒนธรรม": "MCUL", "กระทรวงศึกษาธิการ": "MOE",
    "กระทรวงสาธารณสุข": "MOPH", "กระทรวงอุตสาหกรรม": "MIND", "สำนักงานพระพุทธศาสนาแห่งชาติ": "ONAB",
    "สำนักงานคณะกรรมการพิเศษเพื่อประสานงานโครงการอันเนื่องมาจากพระราชดำริ": "RDPB",
    "สำนักงานราชบัณฑิตยสภา": "ORST", "สำนักงานตำรวจแห่งชาติ": "RTP",
    "สำนักงานป้องกันและปราบปรามการฟอกเงิน": "AMLO",
    "สำนักงานคณะกรรมการป้องกันและปราบปรามการทุจริตในภาครัฐ": "PACC",
}
PROVINCES = {
    "กระบี่": "KBI", "กรุงเทพมหานคร": "BKK", "กาญจนบุรี": "KRI", "กาฬสินธุ์": "KSN", "กำแพงเพชร": "KPT",
    "ขอนแก่น": "KKN", "จันทบุรี": "CHI", "ฉะเชิงเทรา": "CCO", "ชลบุรี": "CBI", "ชัยนาท": "CNT",
    "ชัยภูมิ": "CPM", "ชุมพร": "CPN", "เชียงราย": "CRI", "เชียงใหม่": "CMI", "ตรัง": "TRG", "ตราด": "TRT",
    "ตาก": "TAK", "นครนายก": "NYK", "นครปฐม": "NPT", "นครพนม": "NPM", "นครราชสีมา": "NMA",
    "นครศรีธรรมราช": "NRT", "นครสวรรค์": "NSN", "นนทบุรี": "NBI", "นราธิวาส": "NWT", "น่าน": "NAN",
    "บึงกาฬ": "BKN", "บุรีรัมย์": "BRM", "ปทุมธานี": "PTE", "ประจวบคีรีขันธ์": "PKN", "ปราจีนบุรี": "PRI",
    "ปัตตานี": "PTN", "พะเยา": "PYO", "พระนครศรีอยุธยา": "AYA", "พังงา": "PNA", "พัทลุง": "PLG",
    "พิจิตร": "PCK", "พิษณุโลก": "PLK", "เพชรบุรี": "PBI", "เพชรบูรณ์": "PNB", "แพร่": "PRE",
    "ภูเก็ต": "PKT", "มหาสารคาม": "MKM", "มุกดาหาร": "MDH", "แม่ฮ่องสอน": "MSN", "ยโสธร": "YST",
    "ยะลา": "YLA", "ร้อยเอ็ด": "RET", "ระนอง": "RNG", "ระยอง": "RYG", "ราชบุรี": "RBR", "ลพบุรี": "LRI",
    "ลำปาง": "LPG", "ลำพูน": "LPN", "เลย": "LEI", "ศรีสะเกษ": "SSK", "สกลนคร": "SNK", "สงขลา": "SKA",
    "สตูล": "STN", "สมุทรปราการ": "SPK", "สมุทรสงคราม": "SKM", "สมุทรสาคร": "SKN", "สระแก้ว": "SKW",
    "สระบุรี": "SRI", "สิงห์บุรี": "SBR", "สุโขทัย": "STI", "สุพรรณบุรี": "SPB", "สุราษฎร์ธานี": "SNI",
    "สุรินทร์": "SRN", "หนองคาย": "NKI", "หนองบัวลำภู": "NBP", "อ่างทอง": "ATG", "อำนาจเจริญ": "ACR",
    "อุดรธานี": "UDN", "อุตรดิตถ์": "UTT", "อุทัยธานี": "UTI", "อุบลราชธานี": "UBN",
}


def file_name(year_be: int, code: str, office_no: str, doc_no: str, attachment: int = 0) -> str:
    """ภาคผนวก ๗ ข้อ ๔.๓: ปีพุทธศักราช_รหัสส่วนราชการ+เลขประจำ_เลขที่หนังสือ[_ลำดับสิ่งที่ส่งมาด้วย].pdf
    in Arabic digits, with ``_`` for any space or reserved character."""
    import re

    def clean(s):
        s = str(s).translate(str.maketrans("๐๑๒๓๔๕๖๗๘๙", "0123456789"))
        return re.sub(r"[^0-9A-Za-z]+", "_", s).strip("_")
    name = f"{int(year_be)}_{clean(code)}{clean(office_no)}_{clean(doc_no)}"
    if attachment:
        name += f"_{int(attachment)}"
    return name + ".pdf"


EMAIL_RECEIPT = ("ได้รับอีเมลของท่านแล้ว\n{office}\n{tel}\n\nYour e-mail is well received.\n"
                 "{office_en}\n{tel_en}")
EMAIL_DISCLAIMER = (
    "อีเมล (และ/หรือเอกสารแนบ) นี้เป็นข้อมูลที่เป็นความลับ และอาจเป็นข้อมูลที่เป็นเอกสิทธิ์เฉพาะบุคคล "
    "การนำข้อมูลดังกล่าวไปใช้หรือเปิดเผยให้บุคคลอื่นใดล่วงรู้ เป็นการกระทำที่ไม่ได้รับอนุญาต "
    "หากท่านมิได้เป็นบุคคลที่อีเมลฉบับนี้ระบุถึงแล้ว กรุณาลบอีเมลนี้ออกจากคอมพิวเตอร์ที่ท่านรับ "
    "ทั้งนี้ ขอขอบคุณหากท่านได้แจ้งผู้ส่งถึงการจัดส่งอีเมลผิดพลาดด้วย\n\n"
    "This e-mail (and/or attachments) is confidential and may be privileged. Use or disclosure of it "
    "by anyone other than a designated addressee is unauthorized. If you are not an intended "
    "recipient, please delete this e-mail from the computer on which you received it. We thank you "
    "for notifying us immediately.")
CERTIFIED_COPY = "สำเนาถูกต้อง\n\n(ลงชื่อ) ...............................\n(...............................)\nตำแหน่ง ...............................\nวันที่ ..............................."
