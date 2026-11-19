# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
"""แบบระบบสุขาภิบาล (SN) laid out as the standard house plans of กรมโยธาธิการ
และผังเมือง do: SN-01 the sheet list, the pipe types and the symbols;
SN-02, SN-03 the specification. The words and the drawings are this
program's own; only the arrangement follows the standard."""
from __future__ import annotations

import math

from core import wanic_drawings as D

ROW = 6.4
HEAD = 9.0

#: the pipes: (name, mark, pipe, slope)
PIPES = [("โสโครก", "S", "ท่อ PVC ชั้น 8.5 ตามมาตรฐาน มอก. 17", "1 : 100"),
         ("ระบายน้ำทิ้ง", "W", "ท่อ PVC ชั้น 8.5 ตามมาตรฐาน มอก. 17", "1 : 100"),
         ("ระบายอากาศ", "V", "ท่อ PVC ชั้น 8.5 ตามมาตรฐาน มอก. 17", "-"),
         ("ประปา", "CW", "ท่อ PVC ชั้น 13.5 ตามมาตรฐาน มอก. 17", "-"),
         ("น้ำทิ้งจากครัว", "K", "ท่อ PVC ชั้น 8.5 ตามมาตรฐาน มอก. 17", "1 : 100"),
         ("ระบายน้ำฝน", "RL", "ท่อ PVC ชั้น 8.5 ตามมาตรฐาน มอก. 17", "1 : 100"),
         ("ระบายน้ำรอบอาคาร", "-", "ท่อคอนกรีต หรือรางระบายน้ำ คสล.", "ตามแบบ")]


# -- the symbols, each drawn in a cell centred at (x, y), about 14 mm wide -----------------

def _line_sym(mark, dash=None, w=0.45):
    def f(sh, x, y):
        if dash is None:
            sh.line((x - 7, y), (x + 7, y), "text", w)
        else:
            u = x - 7
            while u < x + 7:
                sh.line((u, y), (min(u + dash[0], x + 7), y), "text", w)
                u += dash[0] + dash[1]
        sh.text((x, y + 0.8), mark, 1.9, "center")
    return f


def _circle_mark(mark, ring=False, dot=False):
    def f(sh, x, y):
        sh.circle((x - 3, y), 1.6, "text", 0.3)
        if ring:
            sh.circle((x - 3, y), 0.9, "text", 0.25)
        if dot:
            sh.circle((x - 3, y), 0.35, "text", 0.5)
        sh.text((x - 0.6, y - 0.8), mark, 1.9)
    return f


def _box_mark(mark, trap=False):
    def f(sh, x, y):
        sh.text((x - 6.5, y - 0.8), mark, 1.8)
        sh.rect(x - 1.6, y - 1.3, x + 1.0, y + 1.3, "text", 0.3)
        if trap:
            sh.poly([(x - 1.0, y - 1.3), (x - 1.0, y - 2.6), (x + 0.4, y - 2.6), (x + 0.4, y - 1.3)], "text", 0.25,
                    closed=False)
        else:
            sh.line((x - 1.6, y - 1.3), (x + 1.0, y + 1.3), "text", 0.2)
        sh.line((x + 1.0, y), (x + 7, y), "text", 0.35)
    return f


def _valve(kind):
    def f(sh, x, y):
        sh.line((x - 7, y), (x - 2, y), "text", 0.35)
        sh.line((x + 2, y), (x + 7, y), "text", 0.35)
        if kind == "gate":
            sh.poly([(x - 2, y - 1.4), (x + 2, y + 1.4), (x + 2, y - 1.4), (x - 2, y + 1.4)], "text", 0.3)
        elif kind == "ball":
            sh.circle((x, y), 1.4, "text", 0.3)
            sh.line((x, y + 1.4), (x, y + 3.0), "text", 0.3)
            sh.line((x - 1.2, y + 3.0), (x + 1.2, y + 3.0), "text", 0.3)
        elif kind == "check":
            sh.poly([(x - 2, y - 1.4), (x + 2, y + 1.4), (x + 2, y - 1.4), (x - 2, y + 1.4)], "text", 0.3)
            sh.line((x - 0.4, y - 1.4), (x + 0.4, y + 1.4), "text", 0.3)
        elif kind == "float":
            sh.poly([(x - 2, y - 1.4), (x + 2, y + 1.4), (x + 2, y - 1.4), (x - 2, y + 1.4)], "text", 0.3)
            sh.circle((x, y + 2.6), 0.9, "text", 0.3)
        elif kind == "meter":
            sh.circle((x, y), 1.8, "text", 0.3)
            sh.text((x, y - 0.75), "M", 1.6, "center", "text", True)
        elif kind == "flex":
            sh.rect(x - 2, y - 0.8, x + 2, y + 0.8, "text", 0.3)
            for i in range(4):
                sh.line((x - 1.5 + i, y - 0.8), (x - 1.5 + i, y + 0.8), "text", 0.15)
        elif kind == "reducer":
            sh.poly([(x - 2, y - 1.4), (x + 2, y - 0.7), (x + 2, y + 0.7), (x - 2, y + 1.4)], "text", 0.3)
    return f


def _sym_up(sh, x, y):
    sh.circle((x - 4, y), 1.0, "text", 0.3)
    sh.circle((x - 4, y), 0.35, "text", 0.5)
    sh.line((x - 3, y), (x + 7, y), "text", 0.35)


def _sym_wye(sh, x, y):
    sh.line((x - 7, y), (x + 7, y), "text", 0.35)
    sh.line((x - 1, y), (x + 3, y + 3), "text", 0.35)
    for xx in (x - 4, x + 4):
        sh.line((xx, y - 0.8), (xx, y + 0.8), "text", 0.25)


def _sym_avc(side=False, cap=False):
    def f(sh, x, y):
        sh.text((x - 7, y - 0.8), "AVC.", 1.7)
        if side:
            sh.poly([(x, y + 2), (x, y - 1), (x + 3, y - 1)], "text", 0.3, closed=False)
            sh.rect(x - 0.6, y + 2, x + 0.6, y + 3, "text", 0.3)
        elif cap:
            sh.line((x + 0.5, y - 2), (x + 0.5, y + 1.5), "text", 0.3)
            sh.poly([(x - 0.8, y + 1.5), (x + 1.8, y + 1.5), (x + 1.2, y + 2.8), (x - 0.2, y + 2.8)], "text", 0.3)
        else:
            sh.circle((x + 0.5, y), 1.2, "text", 0.3)
            sh.line((x + 0.5, y - 1.2), (x + 0.5, y + 1.2), "text", 0.3)
            sh.line((x + 1.7, y), (x + 7, y), "text", 0.35)
    return f


def _sym_vtr(sh, x, y):
    sh.line((x - 2, y - 1.6), (x - 2, y + 1.6), "text", 0.35)
    sh.line((x - 3.6, y + 1.6), (x - 0.4, y + 1.6), "text", 0.35)
    sh.text((x + 0.2, y - 0.8), "VTR", 1.8)


def _sym_co(mark, side=False):
    def f(sh, x, y):
        sh.text((x - 7, y - 0.8), mark, 1.7)
        sh.line((x, y - 1.4), (x, y + 1.4), "text", 0.4)
        sh.line((x + 0.7, y - 1.4), (x + 0.7, y + 1.4), "text", 0.25)
        sh.line((x + 0.7, y), (x + 7, y), "text", 0.35)
        if side:
            sh.line((x - 1.5, y + 1.4), (x - 1.5, y - 2.5), "text", 0.3)
    return f


def _sym_plug(sh, x, y):
    sh.poly([(x - 3, y + 1.2), (x - 4, y + 1.2), (x - 4, y - 1.2), (x - 3, y - 1.2)], "text", 0.3, closed=False)
    sh.line((x - 3, y), (x + 7, y), "text", 0.35)


def _sym_head(sh, x, y):
    sh.line((x, y + 3.5), (x, y + 1.6), "text", 0.3)
    sh.rect(x - 0.9, y - 2.4, x + 0.9, y + 1.6, "text", 0.3)
    for yy in (y - 1.4, y - 0.4, y + 0.6):
        sh.line((x - 0.9, yy), (x + 0.9, yy), "text", 0.15)


def _sym_strainer(sh, x, y):
    sh.line((x - 7, y), (x + 7, y), "text", 0.35)
    sh.line((x - 1, y), (x + 1.2, y - 2.2), "text", 0.35)
    sh.line((x + 0.2, y - 3.0), (x + 2.2, y - 1.4), "text", 0.3)
    for xx in (x - 3, x + 3):
        sh.line((xx, y - 0.8), (xx, y + 0.8), "text", 0.25)


def _sym_text_box(mark):
    def f(sh, x, y):
        sh.rect(x - 4, y - 1.6, x + 4, y + 1.6, "text", 0.3)
        sh.text((x, y - 0.8), mark, 1.8, "center")
    return f


def _sym_tap(mark, kind="tap"):
    def f(sh, x, y):
        sh.line((x - 7, y), (x - 1, y), "text", 0.2)
        sh.line((x - 2.5, y - 0.8), (x - 2.5, y + 0.8), "text", 0.25)
        if kind == "tap":
            sh.circle((x, y), 0.9, "text", 0.3)
        else:
            sh.poly([(x + 1.6, y - 1.2), (x - 0.4, y), (x + 1.6, y + 1.2)], "text", 0.3, closed=False)
            sh.circle((x + 1.6, y), 1.2, "text", 0.3)
        sh.text((x + 3.0, y - 0.8), mark, 1.7)
    return f


def _sym_wc(sh, x, y):
    sh.rect(x - 4.6, y - 1.6, x - 3.4, y + 1.6, "text", 0.3)
    sh.circle((x - 1.4, y), 1.7, "text", 0.3)
    sh.circle((x - 1.6, y), 0.9, "text", 0.2)
    sh.text((x + 1.2, y - 0.8), "WC.", 1.7)


def _sym_ur(sh, x, y):
    sh.poly([(x - 4, y + 1.6), (x - 1.4, y + 1.6), (x - 1.4, y - 0.4), (x - 2.7, y - 1.6), (x - 4, y - 0.4)],
            "text", 0.3)
    sh.text((x + 1.2, y - 0.8), "UR.", 1.7)


def _sym_lav(sh, x, y):
    sh.rect(x - 4.4, y - 1.8, x - 0.8, y + 1.8, "text", 0.3)
    sh.circle((x - 2.6, y - 0.2), 1.1, "text", 0.25)
    sh.text((x + 1.2, y - 0.8), "LAV.", 1.7)


def _sym_sink(sh, x, y):
    sh.rect(x - 4.6, y - 1.8, x - 0.6, y + 1.8, "text", 0.3)
    sh.rect(x - 4.0, y - 1.2, x - 1.2, y + 1.2, "text", 0.2)
    sh.circle((x - 2.6, y), 0.3, "text", 0.4)
    sh.text((x + 1.0, y - 0.8), "SINK.", 1.6)


def _sym_cb(sh, x, y):
    sh.rect(x - 1.8, y - 1.8, x + 1.8, y + 1.8, "text", 0.3)
    sh.line((x - 1.8, y - 1.8), (x + 1.8, y + 1.8), "text", 0.25)
    sh.line((x - 1.8, y + 1.8), (x + 1.8, y - 1.8), "text", 0.25)


SYMBOLS = [
    [(_line_sym("S", None, 0.6), "ท่อระบายน้ำโสโครก"), (_line_sym("W", None, 0.45), "ท่อระบายน้ำเสีย"),
     (_line_sym("V", (2.4, 1.4), 0.35), "ท่อระบายอากาศ"), (_line_sym("CW", (3.4, 0.8), 0.3), "ท่อน้ำประปา"),
     (_line_sym("HW", (3.4, 0.8), 0.3), "ท่อน้ำร้อน"), (_line_sym("SW", None, 0.8), "ท่อระบายน้ำเสียรวม"),
     (_line_sym("R", None, 0.35), "ท่อระบายน้ำฝน"), (_line_sym("K", None, 0.35), "ท่อระบายน้ำจากครัว"),
     (_line_sym("", (3.0, 1.6), 0.5), "ท่อระบายน้ำภายนอกอาคาร"), (_sym_up, "ท่องอขึ้น / ท่อดิ่ง"),
     (_sym_wye, "สามทางวาย (Y)")],
    [(_circle_mark("RL.", dot=True), "ท่อระบายน้ำฝนแนวดิ่ง"), (_circle_mark("RD.", ring=True), "รูระบายน้ำฝนรูปโดม"),
     (_circle_mark("RFD.", ring=True), "รูระบายน้ำฝนแบบเรียบ"), (_box_mark("SD."), "รูระบายน้ำด้านข้าง"),
     (_box_mark("FD."), "รูระบายน้ำทิ้งที่พื้น"), (_box_mark("FD.", True), "รูระบายน้ำทิ้งที่พื้น (มีที่ดักกลิ่น)"),
     (_sym_co("FCO."), "ช่องเปิดล้างท่อบนพื้น"), (_sym_co("CO."), "ช่องเปิดล้างท่อใต้พื้น"),
     (_sym_plug, "ปลั๊กอุดปลายท่อ"), (_sym_co("SCO.", True), "ช่องเปิดล้างท่อด้านข้าง"),
     (_sym_cb, "บ่อพักท่อระบายน้ำ ฝาปิด คสล.")],
    [(_sym_avc(), "ฝาเปิดท่อระบายอากาศ"), (_sym_avc(cap=True), "ฝาเปิดท่อระบายอากาศ (ฝาครอบ)"),
     (_sym_avc(side=True), "ฝาเปิดท่อระบายอากาศ ชนิดออกด้านข้าง"), (_sym_vtr, "ท่ออากาศผ่านหลังคา"),
     (_valve("gate"), "ประตูน้ำ (GATE VALVE)"), (_valve("ball"), "บอลวาล์ว (BALL VALVE)"),
     (_valve("meter"), "มาตรวัดน้ำ"), (_valve("float"), "วาล์วลูกลอย"),
     (_valve("check"), "วาล์วกันน้ำย้อนกลับ (CHECK VALVE)"), (_valve("flex"), "ข้อต่ออ่อน"),
     (_valve("reducer"), "ข้อต่อลด")],
    [(_sym_head, "หัวกระโหลกพร้อมตะแกรงกรอง"), (_sym_strainer, "ตะแกรงกรองผง (STRAINER)"),
     (_sym_text_box("BP."), "เครื่องสูบน้ำเพิ่มแรงดัน"), (_sym_tap("C."), "ก๊อกน้ำ / ก๊อกสนาม"),
     (_sym_tap("SH.", "shower"), "ฝักบัว"), (_sym_tap("HB.", "shower"), "สายฉีดชำระ"),
     (_sym_wc, "โถส้วม"), (_sym_ur, "โถปัสสาวะชาย"), (_sym_lav, "อ่างล้างหน้า"), (_sym_sink, "อ่างล้างจาน"),
     (_sym_text_box("ST."), "ถังบำบัดน้ำเสียสำเร็จรูป")],
]


def _table(sh, x, y0, y1, title, cols, nrows=None):
    """A ruled table with a title band and column heads, rows to the bottom.
    Returns (row tops, column xs)."""
    w = sum(c[1] for c in cols)
    sh.rect(x, y0, x + w, y1, "text", 0.4)
    sh.line((x, y1 - HEAD), (x + w, y1 - HEAD), "text", 0.35)
    sh.text((x + w / 2, y1 - HEAD + 2.8), title, 3.4, "center", "text", True)
    yh = y1 - HEAD
    xs, cx = [], x
    for head, cw in cols:
        xs.append(cx)
        sh.text((cx + cw / 2, yh - ROW + 2.0), head, 2.4, "center", "text", True)
        cx += cw
    xs.append(x + w)
    sh.line((x, yh - ROW), (x + w, yh - ROW), "text", 0.3)
    rh = ROW if nrows is None else (yh - ROW - y0) / nrows
    tops, y = [], yh - ROW
    while y - rh >= y0 - 0.01:
        tops.append(y)
        y -= rh
        sh.line((x, y), (x + w, y), "text", 0.13)
    for c in xs[1:-1]:
        sh.line((c, y0), (c, yh), "text", 0.2)
    return tops, xs, rh


def sn_index_std(sh, sheets, E=None):
    """SN-01 «สารบัญแบบและสัญลักษณ์ระบบสุขาภิบาล» as the standard: the sheet
    list, the pipe types with their slopes, the symbols."""
    x0, y0, x1, y1 = D.drawing_area()
    W = x1 - x0
    ym = y1 - 118                                          # the upper panels' foot
    # the sheet list
    w1 = W * 0.48
    tops, xs, rh = _table(sh, x0, ym, y1, "สารบัญแบบระบบสุขาภิบาล",
                          [("แผ่นที่", 18.0), ("รายการ", w1 - 18.0 - 30.0), ("หมายเหตุ", 30.0)])
    for top, s in zip(tops, [s for s in sheets if s.group == "SN"]):
        sh.text((xs[0] + 9, top - rh + 2.0), s.code, 2.4, "center")
        sh.text((xs[1] + 2, top - rh + 2.0), D._wrap(s.title, 60)[0], 2.4)
    # the pipe types
    x2 = x0 + w1 + 4
    w2 = x1 - x2
    tops, xs, rh = _table(sh, x2, ym, y1, "ชนิดท่อที่ใช้ในการก่อสร้าง",
                          [("ท่อ", 30.0), ("สัญลักษณ์", 18.0), ("ชนิดท่อ", w2 - 30.0 - 18.0 - 28.0),
                           ("ความลาดแนวนอน", 28.0)], nrows=9)
    for top, (name, mark, pipe, slope) in zip(tops, PIPES):
        by = top - rh / 2 - 0.9
        sh.text((xs[0] + 15, by), name, 2.4, "center")
        sh.text((xs[1] + 9, by), mark, 2.4, "center")
        sh.text((xs[2] + 2, by), pipe, 2.4)
        sh.text((xs[3] + 14, by), slope, 2.4, "center")
    # the symbols
    yt = ym - 5
    sh.rect(x0, y0, x1, yt, "text", 0.4)
    sh.line((x0, yt - HEAD - 2), (x1, yt - HEAD - 2), "text", 0.35)
    sh.text(((x0 + x1) / 2, yt - HEAD + 1.0), "สัญลักษณ์ประกอบแบบระบบสุขาภิบาล", 3.8, "center", "text", True)
    yh = yt - HEAD - 2
    cw = W / 4
    sw = 18.0
    sh.line((x0, yh - ROW), (x1, yh - ROW), "text", 0.3)
    nr = max(len(c) for c in SYMBOLS)
    rh = (yh - ROW - y0) / nr
    for ci, col in enumerate(SYMBOLS):
        cx = x0 + ci * cw
        if ci:
            sh.line((cx, y0), (cx, yh), "text", 0.3)
        sh.line((cx + sw, y0), (cx + sw, yh), "text", 0.18)
        sh.text((cx + sw / 2, yh - ROW + 2.0), "สัญลักษณ์", 2.3, "center", "text", True)
        sh.text((cx + sw + (cw - sw) / 2, yh - ROW + 2.0), "ความหมาย", 2.3, "center", "text", True)
        for ri, (fn, text) in enumerate(col):
            yy = yh - ROW - (ri + 0.5) * rh
            fn(sh, cx + sw / 2, yy)
            sh.text((cx + sw + 2, yy - 0.9), text, 2.3)
    for ri in range(1, nr):
        sh.line((x0, yh - ROW - ri * rh), (x1, yh - ROW - ri * rh), "text", 0.12)


def spec_items(E, part):
    """The specification of the sanitary works: (heading, [items]) in two
    sheets; the design values come from the drawing (people, tank size)."""
    from core import wanic_sanitary as SAN
    design = SAN.design_lines(E) if E is not None else []
    one = [
        ("1. ข้อกำหนดทั่วไป", [
            "1.1 ผู้รับจ้างต้องจัดหาวัสดุ อุปกรณ์ และแรงงาน ติดตั้งระบบสุขาภิบาลให้ครบถ้วนใช้งานได้ตามแบบ "
            "และรายการประกอบแบบนี้ ตามมาตรฐานการติดตั้งระบบสุขาภิบาลของวิศวกรรมสถานแห่งประเทศไทย",
            "1.2 แนวท่อในแบบเป็นแนวโดยประมาณ ผู้รับจ้างต้องตรวจสอบกับแบบสถาปัตยกรรมและแบบโครงสร้าง "
            "และปรับให้เหมาะสมกับสภาพหน้างาน โดยไม่ลดขนาดท่อ",
            "1.3 วัสดุและอุปกรณ์ต้องเป็นของใหม่ ได้มาตรฐาน มอก. หรือเทียบเท่า ก่อนติดตั้งต้องเสนอตัวอย่าง "
            "ให้ผู้ควบคุมงานอนุมัติ",
            "1.4 การเจาะหรือฝังท่อผ่านโครงสร้าง ต้องได้รับความเห็นชอบจากวิศวกรผู้ออกแบบ "
            "ห้ามเจาะผ่านคานและเสา"]),
        ("2. ท่อและข้อต่อ", [
            "2.1 ท่อโสโครก (S) ท่อน้ำทิ้ง (W) ท่อระบายอากาศ (V) ท่อน้ำฝน (RL) ใช้ท่อ PVC ชั้น 8.5 "
            "ท่อประปา (CW) ใช้ท่อ PVC ชั้น 13.5 ตามมาตรฐาน มอก. 17",
            "2.2 ข้อต่อเป็นชนิดเดียวกับท่อ ต่อด้วยน้ำยาประสานท่อตามคำแนะนำของผู้ผลิต "
            "ท่อระบายน้ำใช้ข้อต่อชนิดโค้งกว้าง (Long Sweep) หรือสามทางวาย",
            "2.3 ท่อน้ำร้อน (ถ้ามี) ใช้ท่อ PPR หรือท่อทองแดง หุ้มฉนวนตลอดแนว"]),
        ("3. ระบบระบายน้ำโสโครกและน้ำทิ้ง", [
            "3.1 ท่อแนวนอนวางลาดไม่น้อยกว่า 1 : 100 ท่อโสโครกจากโถส้วมขนาดไม่เล็กกว่า Ø4\" "
            "ท่อน้ำทิ้งจากอ่างและฟลอร์เดรนไม่เล็กกว่า Ø2\"",
            "3.2 น้ำโสโครกต่อเข้าถังบำบัดน้ำเสียสำเร็จรูป น้ำทิ้งจากครัวผ่านบ่อดักไขมันก่อน "
            "น้ำที่ผ่านการบำบัดระบายลงบ่อพักก่อนออกสู่ท่อสาธารณะ",
            "3.3 ทุกจุดเปลี่ยนทิศของท่อแนวนอนและปลายท่อ ติดตั้งช่องเปิดล้างท่อ (FCO / CO) "
            "ระยะห่างไม่เกิน 15 ม.",
            "3.4 ฟลอร์เดรนเป็นชนิดมีที่ดักกลิ่น ตะแกรงสแตนเลส พื้นห้องน้ำลาดเข้าฟลอร์เดรน 1 : 100"]),
        ("4. ระบบท่ออากาศ", [
            "4.1 ต่อท่ออากาศจากท่อโสโครกทุกโถส้วมและจากถังบำบัด ขนาดไม่เล็กกว่าครึ่งหนึ่งของท่อโสโครก "
            "และไม่เล็กกว่า Ø1 1/2\"",
            "4.2 ปลายท่ออากาศสูงพ้นหลังคาไม่น้อยกว่า 0.15 ม. หรือออกด้านข้างอาคาร ติดตั้งหัวกันแมลง",
            "4.3 ท่ออากาศแนวนอนวางลาดกลับสู่ท่อระบายน้ำ ห้ามมีจุดขังน้ำ"]),
        ("5. ระบบระบายน้ำฝน", [
            "5.1 น้ำฝนจากรางน้ำหลังคาลงท่อน้ำฝนแนวดิ่ง (RL) ขนาดไม่เล็กกว่า Ø3\" ระยะห่างไม่เกิน 10 ม. "
            "ปลายท่อลงบ่อพักหรือรางระบายน้ำรอบอาคาร",
            "5.2 ห้ามต่อท่อน้ำฝนเข้าถังบำบัดน้ำเสียหรือท่อโสโครก",
            "5.3 ท่อระบายน้ำรอบอาคารวางลาดไม่น้อยกว่า 1 : 200 มีบ่อพักทุกจุดเปลี่ยนทิศ "
            "และระยะห่างไม่เกิน 12 ม."]),
        ("6. งานดินและการวางท่อใต้ดิน", [
            "6.1 ขุดร่องวางท่อให้ได้แนวและระดับตามแบบ รองพื้นร่องด้วยทรายหยาบบดอัดแน่นหนา 0.10 ม.",
            "6.2 กลบท่อด้วยทรายหยาบสูงพ้นหลังท่อ 0.10 ม. แล้วกลบดินบดอัดเป็นชั้นชั้นละไม่เกิน 0.20 ม.",
            "6.3 ท่อลอดใต้ถนนหรือทางรถ ให้หุ้มด้วยคอนกรีตหรือสอดในปลอกท่อเหล็ก"]),
    ]
    two = [
        ("7. ระบบน้ำประปา", [
            "7.1 ต่อท่อประปาจากมาตรวัดน้ำของการประปา ติดตั้งประตูน้ำหลังมาตรวัดน้ำ "
            "และก่อนเข้าห้องน้ำทุกห้อง",
            "7.2 ท่อประปาฝังดินลึกไม่น้อยกว่า 0.30 ม. ท่อเดินลอยยึดด้วยแคล้มป์ระยะไม่เกิน 1.50 ม. "
            "ท่อแนวดิ่งยึดทุกชั้น",
            "7.3 ท่อในผนังให้ฝังเรียบร้อยก่อนฉาบปูน ปลายท่อที่ยังไม่ต่ออุปกรณ์ให้อุดด้วยปลั๊ก"]),
        ("8. การทดสอบ", [
            "8.1 ท่อประปาทดสอบด้วยแรงดันน้ำไม่น้อยกว่า 1.5 เท่าของแรงดันใช้งาน และไม่น้อยกว่า "
            "7 กก./ตร.ซม. นาน 1 ชั่วโมง ต้องไม่มีการรั่วซึม",
            "8.2 ท่อระบายน้ำทดสอบโดยขังน้ำสูงไม่น้อยกว่า 3.00 ม. นาน 15 นาที ระดับน้ำต้องไม่ลดลง",
            "8.3 ก่อนส่งมอบ ล้างท่อประปาด้วยน้ำสะอาด และฆ่าเชื้อด้วยคลอรีน"]),
        ("9. สุขภัณฑ์และอุปกรณ์", [
            "9.1 สุขภัณฑ์เป็นเคลือบขาว ได้มาตรฐาน มอก. ติดตั้งตามคำแนะนำของผู้ผลิต "
            "ยาแนวรอยต่อกับพื้นและผนังด้วยซิลิโคนกันเชื้อรา",
            "9.2 ก๊อกน้ำ สายฉีดชำระ ฝักบัว เป็นชนิดชุบโครเมียม ทุกจุดจ่ายน้ำติดตั้งวาล์วเปิด-ปิด (Stop Valve)"]),
        ("10. ถังบำบัดน้ำเสียและบ่อดักไขมัน", [
            "10.1 ถังบำบัดน้ำเสียเป็นถังสำเร็จรูปชนิดไร้อากาศมีตัวกลาง ตามมาตรฐาน มอก. 2550 "
            "ขนาดตามจำนวนผู้ใช้ (ดูข้อมูลการออกแบบ)",
            "10.2 วางถังบนทรายบดอัดแน่นหนา 0.10 ม. และคอนกรีตหยาบหนา 0.05 ม. เติมน้ำเต็มถังก่อนกลบดิน",
            "10.3 น้ำทิ้งที่ระบายออกต้องมีคุณภาพตามมาตรฐานควบคุมการระบายน้ำทิ้งจากอาคาร"]),
        ("11. การแขวนและยึดท่อ", [
            "11.1 ท่อเดินลอยใต้พื้นหรือใต้คานแขวนด้วยเหล็กแขวนท่อชุบสังกะสี ระยะแขวนตามตารางในแบบขยาย",
            "11.2 ท่อแนวดิ่งยึดกับผนังหรือเสาด้วยแคล้มป์ทุกระยะไม่เกิน 1.50 ม. และทุกชั้น",
            "11.3 ท่อผ่านผนังหรือพื้น ให้ฝังปลอกท่อ (Sleeve) ไว้ก่อนเทคอนกรีต อุดช่องว่างด้วยวัสดุกันน้ำ"]),
        ("12. ถังเก็บน้ำและเครื่องสูบน้ำ (ถ้ามี)", [
            "12.1 ถังเก็บน้ำเป็นชนิดสแตนเลสหรือพลาสติกเกรดอาหาร วางบนฐาน คสล. ติดตั้งลูกลอยตัดน้ำ",
            "12.2 เครื่องสูบน้ำเพิ่มแรงดันชนิดแรงดันคงที่ ติดตั้งวาล์วกันกลับ ประตูน้ำ และข้อต่ออ่อน "
            "ทั้งด้านดูดและด้านส่ง"]),
        ("ข้อมูลการออกแบบ", list(design)),
    ]
    return one if part == 1 else two


def sn_spec(sh, E, part):
    """SN-02 / SN-03 «รายการประกอบแบบระบบสุขาภิบาล (แผ่นที่ n)» in two columns."""
    x0, y0, x1, y1 = D.drawing_area()
    W = x1 - x0
    cw = (W - 10) / 2
    sh.text((x0 + 2, y1 - 6), f"รายการประกอบแบบระบบสุขาภิบาล (แผ่นที่ {part})", 3.8, "left", "text", True)
    sh.line((x0 + 2, y1 - 7.6), (x0 + 112, y1 - 7.6), "text", 0.4)
    col, y = 0, y1 - 16
    for head, items in spec_items(E, part):
        need = 7 + sum(len(D._wrap(t, 74)) * 5.0 + 1.4 for t in items)
        if y - need < y0 + 4 and col == 0:
            col, y = 1, y1 - 16
        x = x0 + 2 + col * (cw + 8)
        sh.text((x, y), head, 3.3, "left", "text", True)
        y -= 6.4
        for t in items:
            lines = D._wrap(t, 74)
            for j, ln in enumerate(lines):
                sh.text((x + (3 if j == 0 else 8), y), ln, 2.9)
                y -= 5.0
            y -= 1.4
        y -= 3.4


# -- SN-04: the riser diagram ----------------------------------------------------------------

TANK_SIZES = (1000, 1500, 2000, 2500, 3000, 4000, 5000)


def _dashdot(sh, a, b, w=0.3, long=3.4, gap=0.8):
    """A dash-dot line (the water pipe CW)."""
    L = math.hypot(b[0] - a[0], b[1] - a[1]) or 1.0
    ux, uy = (b[0] - a[0]) / L, (b[1] - a[1]) / L
    t = 0.0
    while t < L:
        t1 = min(t + long, L)
        sh.line((a[0] + ux * t, a[1] + uy * t), (a[0] + ux * t1, a[1] + uy * t1), "text", w)
        t = t1 + gap
        if t < L:
            sh.line((a[0] + ux * t, a[1] + uy * t), (a[0] + ux * min(t + 0.25, L), a[1] + uy * min(t + 0.25, L)),
                    "text", w)
        t += 0.25 + gap


def _dashed(sh, a, b, w=0.3):
    sh.line(a, b, "text", w, True)


def _pipe_tag(sh, p, text, angle=0.0, size=2.7):
    sh.text(p, text, size, "center", "text", False, angle)


def _arrow(sh, a, b, w=0.4):
    sh.line(a, b, "text", w)
    L = math.hypot(b[0] - a[0], b[1] - a[1]) or 1.0
    ux, uy = (b[0] - a[0]) / L, (b[1] - a[1]) / L
    sh.fill([b, (b[0] - ux * 2.2 - uy * 0.9, b[1] - uy * 2.2 + ux * 0.9),
             (b[0] - ux * 2.2 + uy * 0.9, b[1] - uy * 2.2 - ux * 0.9)], "hatch", 0.0)


def _gate(sh, x, y, vertical=False):
    if vertical:
        sh.poly([(x - 1.2, y - 1.8), (x + 1.2, y + 1.8), (x - 1.2, y + 1.8), (x + 1.2, y - 1.8)], "text", 0.3)
    else:
        sh.poly([(x - 1.8, y - 1.2), (x + 1.8, y + 1.2), (x + 1.8, y - 1.2), (x - 1.8, y + 1.2)], "text", 0.3)


def sn_riser(sh, E):
    """ไดอะแกรมระบบสุขาภิบาลแนวดิ่ง (the standard's SN-04), not to scale: the
    floor levels; the soil stack (S → SW Ø4") and the vent (V Ø2") with a
    branch at every floor that has a bathroom, the vent through the roof; the
    septic tank sized for the users; the kitchen's waste through the grease
    trap; the water from the meter to the storage tank, the booster pump with
    its by-pass, up the riser with a valve at every floor."""
    from core import wanic_sanitary as SAN
    from core import wanic_std_sheets as STD
    x0, y0, x1, y1 = D.drawing_area()
    n, H = int(E["n"]), float(E["H"])
    des = SAN.design(E)
    baths = D.bathrooms(E)
    bfl = sorted({k for k, _r in baths}) or [0]
    users = des["users"]
    tank = next((t for t in TANK_SIZES if t >= users * SAN.SEWAGE_L), TANK_SIZES[-1])
    # the vertical scale: the levels spread over the sheet
    yb = y0 + 100                                           # the floor of the ground floor (±0.00)
    kz = min(30.0, (y1 - 40 - yb) / (n * H + 1.2))

    def Y(z):
        return yb + z * kz
    # the levels across
    for f in range(n + 1):
        z = f * H
        sh.line((x0 + 2, Y(z)), (x1 - 2, Y(z)), "text", 0.2)
        name = f"ระดับพื้นชั้น {f + 1}" if f < n else "ระดับหลังคา (อะเส)"
        sh.poly([(x0 + 4, Y(z)), (x0 + 2.6, Y(z) + 2.2), (x0 + 5.4, Y(z) + 2.2)], "text", 0.25)
        sh.text((x0 + 7, Y(z) + 0.8), name, 2.6, "left", "text", True)
        sh.text((x0 + 52, Y(z) + 0.8), "±0.00" if z == 0 else f"+{z:.2f}", 2.6)
    gl = float(E.get("GL", -0.3))
    sh.line((x0 + 2, Y(gl)), (x1 - 2, Y(gl)), "text", 0.15, True)
    sh.text((x1 - 4, Y(gl) - 3.6), f"ระดับดินเดิม {gl:+.2f}", 2.7, "right")
    # the stacks
    xs = x0 + 112                                            # the soil stack
    xv = xs - 9                                              # the vent
    xw = xs + 7                                              # the waste stack
    ztop = max(bfl) * H + 0.2
    zb = gl - 0.30                                           # the underground run
    sh.line((xs, Y(ztop)), (xs, Y(zb)), "text", 0.7)
    sh.line((xw, Y(ztop)), (xw, Y(zb) + 1.4), "text", 0.45)
    _dashed(sh, (xv, Y(zb) + 2.0), (xv, Y(n * H + 0.9)), 0.3)
    _pipe_tag(sh, (xs + 2.2, (Y(ztop) + Y(0)) / 2), 'Ø4"SW', 90)
    _pipe_tag(sh, (xw + 2.2, (Y(ztop) + Y(0)) / 2 - 18), 'Ø2"W', 90)
    _pipe_tag(sh, (xv - 1.6, Y(n * H) - 12), 'Ø2"V', 90)
    sh.line((xv, Y(zb) + 2.0), (xs, Y(zb) + 4.5), "text", 0.3, True)          # the vent off the stack's foot
    # the vent through the roof
    sh.line((xv - 1.8, Y(n * H + 0.9)), (xv + 1.8, Y(n * H + 0.9)), "text", 0.4)
    sh.text((xv + 3, Y(n * H + 0.9) - 0.8), "VTR (ท่ออากาศผ่านหลังคา)", 2.7)
    for k in bfl:                                            # the branches of each floor's bathrooms
        z = k * H
        nb = sum(1 for kk, _r in baths if kk == k) or 1
        _arrow(sh, (xs - 30, Y(z) + 6), (xs, Y(z) + 6), 0.55)
        sh.text((xs - 30, Y(z) + 7.4), f'Ø4"S (WC × {nb})', 2.7)
        _arrow(sh, (xw + 26, Y(z) + 3), (xw, Y(z) + 3), 0.4)
        sh.text((xw + 4, Y(z) + 4.2), 'Ø2"W (FD, LAV)', 2.7)
        _dashed(sh, (xv - 22, Y(z) + 14), (xv, Y(z) + 14), 0.3)
        sh.text((xv - 22, Y(z) + 15.2), 'Ø2"V', 2.7)
    # the septic tank, to its left
    tx, tw, th = xs - 62, 26.0, 22.0
    ty = Y(gl) - 1.5 - th
    sh.line((xs, Y(zb)), (tx + tw, Y(zb)), "text", 0.7)
    sh.line((xw, Y(zb) + 1.4), (xs, Y(zb) + 1.4), "text", 0.45)
    r = 5.0
    sh.poly([(tx + r, ty), (tx + tw - r, ty), (tx + tw, ty + r), (tx + tw, ty + th - r), (tx + tw - r, ty + th),
             (tx + r, ty + th), (tx, ty + th - r), (tx, ty + r)], "text", 0.45)
    i = 0.0
    while i < tw + th:
        a = (tx + max(0.0, i - th), ty + min(th, i))
        b = (tx + min(tw, i), ty + max(0.0, i - tw))
        sh.line(a, b, "hatch", 0.12)
        i += 2.5
    sh.rect(tx + tw / 2 - 2.5, ty + th, tx + tw / 2 + 2.5, ty + th + 1.4, "text", 0.3)
    _arrow(sh, (tx, ty + th - 7), (tx - 20, ty + th - 7), 0.6)
    sh.text((tx - 20, ty + th - 5.6), 'Ø4"SW', 2.7)
    sh.text((tx - 1, ty + th - 11.6), "ต่อลงบ่อพักท่อระบายน้ำ", 2.7, "right")
    st = des["septic"]
    notes = [f"ถังบำบัดน้ำเสียสำเร็จรูป ST ขนาด {st['litres']:,} ลิตร"
             + (f" × {st['count']} ถัง" if st["count"] > 1 else "") + f" (ผู้ใช้ {users} คน)",
             f"ชนิดไร้อากาศมีตัวกลาง มอก. 2550 ขนาด {st['size']} ม.",
             "วางบนทรายบดอัดแน่น 0.10 ม. และคอนกรีตหยาบ 0.05 ม.",
             "การติดตั้งให้เป็นไปตามมาตรฐานผู้ผลิต"]
    for j, t in enumerate(notes):
        sh.text((tx - 4, ty - 7 - j * 4.4), t, 2.7)
    # the kitchen through the grease trap
    if des.get("kitchens"):
        gx = xs + 40
        sh.rect(gx, Y(zb) - 4, gx + 9, Y(zb) + 2, "text", 0.4)
        sh.text((gx + 4.5, Y(zb) - 2.6), "GT", 2.7, "center", "text", True)
        _arrow(sh, (gx + 26, Y(-0.05)), (gx + 9, Y(zb) + 1), 0.4)
        sh.text((gx + 12, Y(-0.05) + 1.2), 'Ø2"K จากซิงก์ครัว', 2.7)
        sh.line((gx, Y(zb) - 1), (xw, Y(zb) - 1), "text", 0.4)
        sh.text((gx - 1, Y(zb) - 7.6), f"บ่อดักไขมัน GT {des['grease']['litres']} ลิตร", 2.7, "right")
    # the water: from the meter (right) to the tank, the pump, up the riser
    xr = xs + 78                                             # the riser
    ztopw = max(bfl) * H + 0.6
    yw = Y(0.25)
    _dashdot(sh, (xr, yw), (xr, Y(ztopw)), 0.35)
    _pipe_tag(sh, (xr + 2.2, (Y(ztopw) + yw) / 2), 'Ø3/4"CW', 90)
    for k in bfl:
        z = k * H + 0.6 if k else 0.6
        _dashdot(sh, (xr, Y(z)), (xr - 16, Y(z)), 0.3)
        _gate(sh, xr - 8, Y(z))
        sh.text((xr - 16, Y(z) + 1.2), "→ ห้องน้ำ", 2.7, "right")
    xt = xr + 60                                             # the tank
    _dashdot(sh, (xr, yw), (xt - 26, yw), 0.35)
    sh.text(((xr + xt - 26) / 2, yw + 1.0), 'Ø3/4"CW', 2.7, "center")
    sh.rect(xt - 30, yw - 2.4, xt - 22, yw + 2.4, "text", 0.35)              # the booster pump
    sh.text((xt - 26, yw - 0.9), "BP", 2.7, "center", "text", True)
    _dashdot(sh, (xt - 22, yw), (xt - 6, yw), 0.35)
    # the by-pass round the pump, with its check valve
    yb2 = yw + 9
    _dashdot(sh, (xr + 20, yw), (xr + 20, yb2), 0.3)
    _dashdot(sh, (xr + 20, yb2), (xt - 10, yb2), 0.3)
    _dashdot(sh, (xt - 10, yb2), (xt - 10, yw), 0.3)
    _gate(sh, (xr + xt - 10) / 2 + 6, yb2)
    sh.line(((xr + xt - 10) / 2 + 5.4, yb2 - 1.2), ((xr + xt - 10) / 2 + 6.6, yb2 + 1.2), "text", 0.3)
    sh.text(((xr + xt) / 2 - 2, yb2 + 1.4), 'Ø3/4" BY PASS', 2.7, "center")
    th2 = 30.0
    sh.rect(xt - 6, yw - 3, xt + 8, yw - 3 + th2, "text", 0.45)               # the storage tank
    for j in range(1, 9):
        sh.line((xt - 6, yw - 3 + j * th2 / 9), (xt + 8, yw - 3 + j * th2 / 9), "hatch", 0.12)
    sh.rect(xt - 8, yw - 5, xt + 10, yw - 3, "text", 0.3)
    _gate(sh, xt + 1, yw - 3 + th2 + 1.6)
    sh.circle((xt + 4, yw - 3 + th2 + 3.2), 0.9, "text", 0.3)
    _dashdot(sh, (xt + 1, yw - 3 + th2 + 1.6), (xt + 30, yw - 3 + th2 + 1.6), 0.3)
    _dashdot(sh, (xt + 30, yw - 3 + th2 + 1.6), (xt + 30, yw), 0.3)
    _dashdot(sh, (xt + 30, yw), (x1 - 8, yw), 0.35)
    sh.circle((x1 - 34, yw), 2.0, "text", 0.3)                                  # the meter
    sh.text((x1 - 34, yw - 0.8), "M", 1.8, "center", "text", True)
    _gate(sh, x1 - 41, yw)
    _gate(sh, x1 - 27, yw)
    sh.text((x1 - 4, yw + 1.4), "จากท่อประปา", 2.7, "right")
    def note(p, q, lines):                                   # a leader with its arrowhead at the item
        sh.line((q[0] - 1.0, q[1]), p, "text", 0.18)
        _ahead(sh, p, q, 2.0, "text")
        for j, t in enumerate(lines):
            sh.text((q[0], q[1] - 0.9 - j * 4.6), t, 2.6)
    note((xt + 8, yw - 3 + th2 * 0.7), (xt + 14, Y(H) + 20),
         [f"ถังเก็บน้ำสำเร็จรูป {tank:,} ลิตร", f"(ผู้ใช้ {users} คน × 200 ลิตร/วัน)",
          'FLOAT VALVE Ø1/2" · BALL VALVE Ø1/2"', "วางบนฐาน คสล. หนา 0.10 ม."])
    note((xt - 26, yw - 2.4), (xt - 52, Y(gl) - 10),
         ["เครื่องสูบน้ำเพิ่มแรงดัน (BOOSTER PUMP)", "ชนิดแรงดันคงที่ ไม่น้อยกว่า 200 วัตต์"])
    note((x1 - 34, yw - 2), (x1 - 56, Y(gl) - 22), ['ชุดมาตรวัดน้ำ Ø1/2"', "(ผู้รับจ้างเป็นผู้ติดตั้ง)"])
    STD.caption_marks(sh, ((x0 + x1) / 2 - 50, y0 + 14), "ไดอะแกรมระบบสุขาภิบาลแนวดิ่ง", "ไม่ตามมาตราส่วน",
                      None, None, 100.0)


# -- SN-05, SN-06: the sanitary plan of a floor ----------------------------------------------

def _cb(sh, c, s=2.2):
    """A catch basin (☒)."""
    sh.rect(c[0] - s, c[1] - s, c[0] + s, c[1] + s, "pipe", 0.45)
    sh.line((c[0] - s, c[1] - s), (c[0] + s, c[1] + s), "pipe", 0.25)
    sh.line((c[0] - s, c[1] + s), (c[0] + s, c[1] - s), "pipe", 0.25)


def _ahead(sh, tip, frm, size=2.2, layer="pipe"):
    """A filled arrowhead at ``tip`` pointing away from ``frm``."""
    L = math.hypot(tip[0] - frm[0], tip[1] - frm[1]) or 1.0
    ux, uy = (tip[0] - frm[0]) / L, (tip[1] - frm[1]) / L
    sh.fill([tip, (tip[0] - ux * size - uy * size * 0.38, tip[1] - uy * size + ux * size * 0.38),
             (tip[0] - ux * size + uy * size * 0.38, tip[1] - uy * size - ux * size * 0.38)], layer, 0.0)


def _flow(sh, a, b, w=0.55):
    """The perimeter drain from a to b (paper): long dashes, an arrow midway."""
    L = math.hypot(b[0] - a[0], b[1] - a[1]) or 1.0
    ux, uy = (b[0] - a[0]) / L, (b[1] - a[1]) / L
    t = 0.0
    while t < L:
        t1 = min(t + 4.5, L)
        sh.line((a[0] + ux * t, a[1] + uy * t), (a[0] + ux * t1, a[1] + uy * t1), "pipe", w)
        t = t1 + 1.6
    m = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
    _ahead(sh, (m[0] + ux * 1.6, m[1] + uy * 1.6), m, 2.6)


def _hatched(sh, c, r, inner=True, hatch=True):
    """A tank in plan: a circle, 45° hatching clipped to it, the inner circle."""
    sh.circle(c, r, "pipe", 0.5)
    if hatch:
        ux, uy, nx, ny = 0.7071, 0.7071, -0.7071, 0.7071
        o = -r + 0.8
        while o < r:
            h = math.sqrt(max(r * r - o * o, 0.0))
            p = (c[0] + nx * o, c[1] + ny * o)
            sh.line((p[0] - ux * h, p[1] - uy * h), (p[0] + ux * h, p[1] + uy * h), "hatch", 0.15)
            o += 0.9
    if inner:
        sh.fill([(c[0] + r * 0.28 * math.cos(i * math.pi / 8), c[1] + r * 0.28 * math.sin(i * math.pi / 8))
                 for i in range(16)], "mask", 0.0)
        sh.circle(c, r * 0.28, "pipe", 0.35)


def _flex(sh, p, q):
    """A flexible joint (ข้อต่ออ่อน) on the pipe p→q, at p."""
    L = math.hypot(q[0] - p[0], q[1] - p[1]) or 1.0
    ux, uy = (q[0] - p[0]) / L, (q[1] - p[1]) / L
    nx, ny = -uy, ux
    a, b = (p[0] - ux * 1.2, p[1] - uy * 1.2), (p[0] + ux * 1.2, p[1] + uy * 1.2)
    sh.fill([(a[0] + nx * 0.7, a[1] + ny * 0.7), (b[0] + nx * 0.7, b[1] + ny * 0.7),
             (b[0] - nx * 0.7, b[1] - ny * 0.7), (a[0] - nx * 0.7, a[1] - ny * 0.7)], "mask", 0.0)
    sh.poly([(a[0] + nx * 0.7, a[1] + ny * 0.7), (b[0] + nx * 0.7, b[1] + ny * 0.7),
             (b[0] - nx * 0.7, b[1] - ny * 0.7), (a[0] - nx * 0.7, a[1] - ny * 0.7)], "pipe", 0.25)
    for i in range(3):
        m = (a[0] + ux * (0.6 + i * 0.6), a[1] + uy * (0.6 + i * 0.6))
        sh.line((m[0] + nx * 0.7, m[1] + ny * 0.7), (m[0] - nx * 0.7, m[1] - ny * 0.7), "pipe", 0.15)


def _fco(sh, c):
    """A cleanout (FCO) at a pipe's end."""
    sh.circle(c, 1.0, "pipe", 0.35)
    sh.line((c[0] - 1.0, c[1]), (c[0] + 1.0, c[1]), "pipe", 0.3)


def _valve(sh, c, vertical=False):
    if vertical:
        sh.poly([(c[0] - 1.0, c[1] - 1.5), (c[0] + 1.0, c[1] + 1.5), (c[0] - 1.0, c[1] + 1.5),
                 (c[0] + 1.0, c[1] - 1.5)], "pipe", 0.3)
    else:
        sh.poly([(c[0] - 1.5, c[1] - 1.0), (c[0] + 1.5, c[1] + 1.0), (c[0] + 1.5, c[1] - 1.0),
                 (c[0] - 1.5, c[1] + 1.0)], "pipe", 0.3)


def _cw_branches(sh, v, rm, n, wall, a0, off, fixtures, at, along, riser=False):
    """The cold water inside a wet room: a pipe along the wall ``off``
    inside it from ``a0`` past every fixture, a branch with a stop valve
    to each (sink, basin, WC, shower)."""
    fx = [f for f in fixtures if f.get("type", "").startswith(("WC", "LV", "SH", "BT", "SK", "UR"))]
    if not fx:
        return
    alongs = [along(n, (float(f["x"]), float(f["y"]))) for f in fx]
    lo, hi = min(alongs + [a0]), max(alongs + [a0])
    _dashdot(sh, v(*at(n, wall, off, lo)), v(*at(n, wall, off, hi)), 0.3)
    for f, a in zip(fx, alongs):
        pf = (float(f["x"]), float(f["y"]))
        tgt = v(*pf)
        st = v(*at(n, wall, off, a))
        L = math.hypot(tgt[0] - st[0], tgt[1] - st[1])
        if L > 1.2:
            k = max(0.0, (L - 1.6) / L)
            end = (st[0] + (tgt[0] - st[0]) * k, st[1] + (tgt[1] - st[1]) * k)
            _dashdot(sh, st, end, 0.25)
        else:
            end = st
        sh.circle(end, 0.65, "pipe", 0.3)                            # the stop valve at the fixture


def _outline(E, k):
    rms = [s["room"] for s in E["slabs"] if s["floor"] == k] or [s["room"] for s in E["slabs"]]
    return (min(r["x"] for r in rms), min(r["y"] for r in rms),
            max(r["x"] + r["w"] for r in rms), max(r["y"] + r["d"] for r in rms))


def _side(rm, box, prefer=("N", "E", "W", "S")):
    """The exterior side of a room nearest the outside: (name, wall coordinate, outward normal)."""
    bx0, by0, bx1, by1 = box
    d = {"W": rm["x"] - bx0, "E": bx1 - rm["x"] - rm["w"], "S": rm["y"] - by0, "N": by1 - rm["y"] - rm["d"]}
    best = min(prefer, key=lambda k_: (round(d[k_], 3), prefer.index(k_)))
    wall = {"W": bx0, "E": bx1, "S": by0, "N": by1}[best]
    n = {"W": (-1, 0), "E": (1, 0), "S": (0, -1), "N": (0, 1)}[best]
    return best, wall, n


def _perim(rect, a, b):
    """The shorter way round the rectangle ``rect`` from point a to point b
    (both on its edge), as a list of points."""
    x0, y0, x1, y1 = rect
    W, H = x1 - x0, y1 - y0
    P = 2 * (W + H)

    def t(p):
        x, y = p
        if abs(y - y0) < 1e-6:
            return x - x0
        if abs(x - x1) < 1e-6:
            return W + (y - y0)
        if abs(y - y1) < 1e-6:
            return W + H + (x1 - x)
        return 2 * W + H + (y1 - y)
    corners = [(0.0, (x0, y0)), (W, (x1, y0)), (W + H, (x1, y1)), (2 * W + H, (x0, y1))]
    ta, tb = t(a), t(b)
    fwd = (tb - ta) % P
    out = [a]
    if fwd <= P / 2:
        for tc, c in sorted(corners, key=lambda q: (q[0] - ta) % P):
            if 0 < (tc - ta) % P < fwd:
                out.append(c)
    else:
        for tc, c in sorted(corners, key=lambda q: (ta - q[0]) % P):
            if 0 < (ta - tc) % P < P - fwd:
                out.append(c)
    out.append(b)
    return out


def _snap(rect, p):
    """The point of the rectangle's edge nearest p."""
    x0, y0, x1, y1 = rect
    x, y = min(max(p[0], x0), x1), min(max(p[1], y0), y1)
    d = [(abs(x - x0), (x0, y)), (abs(x - x1), (x1, y)), (abs(y - y0), (x, y0)), (abs(y - y1), (x, y1))]
    return min(d)[1]


def _labels(sh, notes, col_x, ytop, ybot, size=2.6):
    """The notes in a column at ``col_x``, top to bottom in the order of
    their points, each on a horizontal leader ending in an arrowhead at its
    point (the standard's way); kept 6 mm apart, pushed up from ``ybot``."""
    items = sorted(notes, key=lambda t: -t[0][1])
    ys, last = [], ytop + 8
    for p, lines in items:                                   # downwards: no closer than the one above
        ty = min(p[1], ytop, last - 6.4)
        ys.append(ty)
        last = ty - 4.6 * (len(lines) - 1)
    floor_ = ybot
    for i in range(len(items) - 1, -1, -1):                  # upwards: off the floor and the one below
        h = 4.6 * (len(items[i][1]) - 1)
        if ys[i] - h < floor_:
            ys[i] = floor_ + h
        floor_ = ys[i] + 6.4
    for (p, lines), ty in zip(items, ys):                    # level from the text, one turn down to the item
        knee = (p[0] + 4.0, ty) if abs(ty - p[1]) > 0.4 else None
        sh.line((col_x - 1.2, ty), knee or p, "text", 0.18)
        if knee:
            sh.line(knee, p, "text", 0.18)
        _ahead(sh, p, knee or (col_x, ty), 2.0, "text")
        for j, ln in enumerate(lines):
            sh.text((col_x, ty - 0.9 - j * 4.6), ln, size)


def sn_plan_std(sh, E, k):
    """แปลนระบบสุขาภิบาลชั้น k+1 as the standard (SN-05, SN-06): the floor
    plan (walls, doors, the stair, the rooms and their levels, the
    fixtures), the sizes; the ground floor's drain round the building
    (concrete Ø0.20 ม. ลาด 1:200, catch basins at the corners and no more
    than 12 m apart, the flow, the start 0.60 m deep, the outlet), the
    septic tank outside the bathroom with the bathroom's pipes gathered
    outside the wall into it (flexible joints where they leave the
    building, a cleanout at the far end), the grease trap outside the
    kitchen, the water: meter, storage tank and pump at the front, the main
    round the building with a valve into each wet room, the downpipes;
    upstairs each bathroom's pipes gathered to its stack. Every note is in
    one column on the right with an arrow to its item."""
    from core import wanic_sanitary as SAN
    from core import wanic_std_sheets as STD
    x0, y0, x1, y1 = D.drawing_area()
    colw = 104.0
    v, sc = D.plan_view(sh, E, box=(x0, y0 + 16, x1 - colw, y1), pad=4.6)
    t = float(E["settings"].get("wall_t") or 0.1)
    D.draw_grid(sh, v, E, ext=3.7, at=(2.2, 2.9))
    D.draw_walls(sh, v, E, k, t, None, swings=True, tags=False)
    D.draw_stairs(sh, v, E, k)
    D.draw_fixtures(sh, v, E, k, labels=False)
    boxes = D.stair_boxes(E, k)
    for sl in (s_ for s_ in E["slabs"] if s_["floor"] == k):          # the rooms and their levels
        rm = sl["room"]
        cx, cy = D.label_spot(rm, boxes)
        p = v(cx, cy)
        z = float(sl.get("z", 0.0)) - (0.05 if (rm.get("name") or "").startswith("ห้องน้ำ") else 0.0)
        D.masked_text(sh, (p[0], p[1] + 1.4), rm.get("name") or "ห้อง", 2.7, "center", True)
        D.masked_text(sh, (p[0], p[1] - 2.8), "±0.00" if abs(z) < 0.005 else f"{z:+.2f}", 2.4)
    box = _outline(E, k)
    bx0, by0, bx1, by1 = box
    baths = [rm for kk, rm in D.bathrooms(E) if kk == k]
    kit = [s_["room"] for s_ in E["slabs"] if s_["floor"] == k and "ครัว" in (s_["room"].get("name") or "")]
    fixtures = [f["fx"] for f in E["fixtures"] if f["floor"] == k]
    des = SAN.design(E)
    notes = []
    col_x = x1 - colw + 8

    def in_room(fx, rm):
        return rm["x"] - 0.01 <= float(fx["x"]) <= rm["x"] + rm["w"] + 0.01 and \
            rm["y"] - 0.01 <= float(fx["y"]) <= rm["y"] + rm["d"] + 0.01

    def along(n, q):                 # the coordinate along a wall with normal n
        return q[1] if n[0] else q[0]

    def at(n, wall, off, a):         # the point off the wall (outward) at ``a`` along it
        return (wall + n[0] * off, a) if n[0] else (a, wall + n[1] * off)
    if k == 0:
        o = 1.6
        X0, Y0, X1, Y1 = bx0 - o, by0 - o, bx1 + o, by1 + o
        corners = [(X0, Y1), (X1, Y1), (X1, Y0), (X0, Y0)]
        cbs = []
        for a_, b_ in zip(corners, corners[1:] + corners[:1]):
            L = math.hypot(b_[0] - a_[0], b_[1] - a_[1])
            nseg = max(1, math.ceil(L / 12.0))
            for i in range(nseg):
                cbs.append((a_[0] + (b_[0] - a_[0]) * i / nseg, a_[1] + (b_[1] - a_[1]) * i / nseg))
        start, out = (X1, Y1), (X0, Y0)                             # the start at the back right, out at the front left
        for path in ([(X1, Y1), (X0, Y1), (X0, Y0)], [(X1, Y1), (X1, Y0), (X0, Y0)]):
            for a_, b_ in zip(path, path[1:]):
                L = math.hypot(b_[0] - a_[0], b_[1] - a_[1])
                nseg = max(1, math.ceil(L / 12.0))
                for i in range(nseg):
                    pa = (a_[0] + (b_[0] - a_[0]) * i / nseg, a_[1] + (b_[1] - a_[1]) * i / nseg)
                    pb = (a_[0] + (b_[0] - a_[0]) * (i + 1) / nseg, a_[1] + (b_[1] - a_[1]) * (i + 1) / nseg)
                    da, db = v(*pa), v(*pb)
                    L2 = math.hypot(db[0] - da[0], db[1] - da[1]) or 1
                    ux, uy = (db[0] - da[0]) / L2, (db[1] - da[1]) / L2
                    _flow(sh, (da[0] + ux * 2.6, da[1] + uy * 2.6), (db[0] - ux * 2.6, db[1] - uy * 2.6))
        for c in cbs:
            _cb(sh, v(*c))
        po = v(*out)
        _flow(sh, (po[0], po[1] - 2.6), (po[0], po[1] - 14))
        # the drain's sizes: 1.60 from the walls, both ways
        for a_, b_, q in (((X0, by0 - 0.0), (bx0, by0), "x"),):
            pass
        ytop_d = v(0, Y1)[1] + 4
        sh.line(v(X1, Y1), (v(X1, 0)[0], ytop_d + 1.4), "dim", 0.12)
        sh.line(v(bx1, by1), (v(bx1, 0)[0], ytop_d + 1.4), "dim", 0.12)
        STD._hdim(sh, v(bx1, 0)[0], v(X1, 0)[0], ytop_d, f"{o:.2f}")
        notes.append((v(X1, (Y0 + Y1) / 2 + 0.6), ["ท่อคอนกรีตท้องตลาด Ø0.20 ม. ลาด 1 : 200"]))
        notes.append(((v(X1, Y1)[0] + 2.2, v(X1, Y1)[1]), ["จุดต้นท่อลึก 0.60 ม."]))
        cb_note = min(cbs, key=lambda c: (abs(c[0] - X1), -c[1] if c[1] < Y1 else 9))
        cbn = v(X1, Y0)
        notes.append(((cbn[0] + 2.2, cbn[1]), ["บ่อพักท่อระบายน้ำสำเร็จรูป",
                                                                                 "ขนาด 0.40 × 0.40 ม. พร้อมฝา คสล."]))
        sh.text((po[0] + 2.0, po[1] - 14), "ต่อลงบ่อพักท่อระบายน้ำสาธารณะ", 2.4)
        # the septic tank and the bathroom's pipes
        st = des["septic"]
        r_st = 0.5
        used = []
        for bi, rm in enumerate(baths[:1]):
            side, wall, n = _side(rm, box, ("N", "E", "W", "S"))
            used.append(side)
            lo = (rm["y"] if n[0] else rm["x"]) + 0.15
            hi = (rm["y"] + rm["d"] if n[0] else rm["x"] + rm["w"]) - 0.15
            ct = at(n, wall, 0.98, (lo + hi) / 2)
            _hatched(sh, v(*ct), v.len(r_st))
            col_off = 0.32
            mine = [fx for fx in fixtures if in_room(fx, rm)]
            ats = []
            for fx in mine:
                typ = fx.get("type", "")
                if not (typ.startswith(("WC", "UR", "LV", "SH", "BT", "FD"))):
                    continue
                soil = typ.startswith(("WC", "UR"))
                pf = (float(fx["x"]), float(fx["y"]))
                a_ = along(n, pf)
                pw = at(n, wall, 0.0, a_)
                pc = at(n, wall, col_off, a_)
                sh.line(v(*pf), v(*pc), "pipe", 0.7 if soil else 0.4)
                _flex(sh, v(*at(n, wall, 0.12, a_)), v(*pc))
                ats.append(a_)
            fda = (lo + hi) / 2 - 0.4
            fd = (rm["x"] + rm["w"] * 0.5, rm["y"] + rm["d"] * 0.35)        # the floor drain
            fq = v(*fd)
            sh.rect(fq[0] - 1.1, fq[1] - 1.1, fq[0] + 1.1, fq[1] + 1.1, "pipe", 0.3)
            sh.circle(fq, 0.6, "pipe", 0.2)
            a_ = along(n, fd)
            sh.line(fq, v(*at(n, wall, col_off, a_)), "pipe", 0.4)
            ats.append(a_)
            ca = along(n, ct)
            ats.append(ca)
            amin, amax = min(ats), max(ats)
            sh.line(v(*at(n, wall, col_off, amin)), v(*at(n, wall, col_off, amax)), "pipe", 0.8)
            for e_ in (amin, amax):
                if abs(e_ - ca) > 0.05:
                    _fco(sh, v(*at(n, wall, col_off, e_)))
            pa_, pb_ = v(*at(n, wall, col_off, ca)), v(*at(n, wall, 0.98 - r_st, ca))
            sh.line(pa_, pb_, "pipe", 0.8)
            _ahead(sh, pb_, pa_, 2.4)
            cb = min(cbs, key=lambda c: math.hypot(c[0] - ct[0], c[1] - ct[1]))
            pt0, pt1 = v(*ct), v(*cb)
            sh.line(pt0, pt1, "pipe", 0.45)
            _flex(sh, ((pt0[0] + pt1[0]) / 2, (pt0[1] + pt1[1]) / 2), pt1)
            notes.append((v(*at(n, wall, 0.98 + r_st, ca)), [f"ถังบำบัดน้ำเสียสำเร็จรูป {st['litres']:,} ลิตร"]))
            notes.append((v(*at(n, wall, col_off, (amin + ca) / 2)), ['ท่อ PVC Ø4"S / Ø2"W ลาด 1 : 100']))
            notes.append((fq, ['FD Ø2" (ฟลอร์เดรนกันกลิ่น)']))
        # the grease trap outside the kitchen
        for rm in kit[:1]:
            side, wall, n = _side(rm, box, tuple(x for x in ("E", "W", "N", "S") if x not in used) or ("E",))
            used.append(side)
            sinks = [fx for fx in fixtures if fx.get("type", "").startswith("SK") and in_room(fx, rm)]
            src = (float(sinks[0]["x"]), float(sinks[0]["y"])) if sinks else \
                (rm["x"] + rm["w"] / 2, rm["y"] + rm["d"] / 2)
            cg = at(n, wall, 0.75, along(n, src))
            _hatched(sh, v(*cg), v.len(0.30), inner=True, hatch=False)
            pw = v(*at(n, wall, 0.75 - 0.30, along(n, src)))
            sh.line(v(*src), pw, "pipe", 0.45)
            _ahead(sh, pw, v(*src), 2.0)
            _flex(sh, v(*at(n, wall, 0.12, along(n, src))), pw)
            cb = min(cbs, key=lambda c: math.hypot(c[0] - cg[0], c[1] - cg[1]))
            sh.line(v(*cg), v(*cb), "pipe", 0.45)
            notes.append((v(*at(n, wall, 1.05, along(n, src))), [f"ถังดักไขมันสำเร็จรูป {des['grease']['litres']} ลิตร"]))
        # the water at the front right: meter, storage tank, pump; the main round the building
        tk = (bx1 - 1.3, by0 - 0.85)
        pm = v(bx1 - 1.3, Y0 - 0.9)
        pt = v(*tk)
        r_tk = v.len(0.38)
        sh.rect(pt[0] - v.len(0.5), pt[1] - v.len(0.5), pt[0] + v.len(0.5), pt[1] + v.len(0.5), "pipe", 0.2, True)
        _hatched(sh, pt, r_tk, inner=False)
        sh.circle(pm, 1.6, "pipe", 0.35)
        sh.text((pm[0], pm[1] - 0.7), "M", 1.6, "center", "pipe", True)
        _valve(sh, (pm[0], pm[1] + 3.2), True)
        pp = v(bx1 - 1.3, Y0 - 2.4)                                # on to the public main, at the front
        _dashdot(sh, (pm[0], pm[1] - 1.6), (pm[0], pp[1]), 0.3)
        _valve(sh, (pm[0], pm[1] - 4.0), True)
        sh.line((pp[0] - 1.6, pp[1]), (pp[0] + 1.6, pp[1]), "pipe", 0.6)       # capped, ready for the tap
        for i in range(-6, 7):
            xx = pp[0] + i * 3.0
            sh.line((xx, pp[1] - 2.0), (xx + 1.8, pp[1] - 2.0), "pipe", 0.5)
        notes.append(((pp[0] + 2.0, pp[1] - 2.0), ["รอรับน้ำประปาจากท่อประปาสาธารณะหน้าบ้าน",
                                                   'ท่อ PVC Ø1/2" ชั้น 13.5 (ตามข้อกำหนดการประปา)']))
        _dashdot(sh, (pm[0], pm[1] + 1.6), (pm[0], pt[1] - r_tk), 0.3)
        bp = (pt[0] - v.len(0.95), pt[1])
        sh.rect(bp[0] - 2.0, bp[1] - 1.6, bp[0] + 2.0, bp[1] + 1.6, "pipe", 0.35)
        sh.text((bp[0], bp[1] - 0.7), "BP", 1.6, "center", "pipe", True)
        _dashdot(sh, (pt[0] - r_tk, pt[1]), (bp[0] + 2.0, bp[1]), 0.3)
        ring = (bx0 - 0.25, by0 - 0.25, bx1 + 0.25, by1 + 0.25)
        m0 = (bx1 - 2.3, by0 - 0.25)
        _dashdot(sh, (bp[0] - 2.0, bp[1]), v(*m0), 0.3) if False else None
        _dashdot(sh, (bp[0] - 2.0, bp[1]), (bp[0] - 4.0, bp[1]), 0.3)
        _dashdot(sh, (bp[0] - 4.0, bp[1]), (bp[0] - 4.0, v(0, m0[1])[1]), 0.3)
        mstart = (v.inv(bp[0] - 4.0, 0)[0] if hasattr(v, "inv") else bx1 - 2.4, m0[1])
        for rm in baths[:1] + kit[:1]:
            side, wall, n = _side(rm, box, ("E", "N", "W", "S"))
            ent = at(n, wall, 0.25, (rm["y"] + rm["d"] * 0.15) if n[0] else (rm["x"] + rm["w"] * 0.85))
            ent = _snap(ring, ent)
            path = _perim(ring, _snap(ring, mstart), ent)
            for a_, b_ in zip(path, path[1:]):
                _dashdot(sh, v(*a_), v(*b_), 0.3)
            pin = v(*at(n, wall, -0.25, along(n, ent)))
            _dashdot(sh, v(*ent), pin, 0.3)
            pv = v(*at(n, wall, 0.12, along(n, ent)))
            _valve(sh, pv, vertical=not n[0])
            _cw_branches(sh, v, rm, n, wall, along(n, ent), -0.25,
                         [fx for fx in fixtures if in_room(fx, rm)], at, along)
        notes.append((v(*_snap(ring, (bx1 + 0.25, (by0 + by1) / 2))), ['ท่อประปา PVC Ø3/4"CW']))
        notes.append((pt, [f"ถังเก็บน้ำสำเร็จรูป {next((t_ for t_ in TANK_SIZES if t_ >= des['users'] * SAN.SEWAGE_L), TANK_SIZES[-1]):,} ลิตร",
                           'วางบนฐาน คสล. หนา 0.10 ม. · FLOAT VALVE Ø1/2"'.replace(" · ", " ")]))
        notes.append((bp, ["เครื่องสูบน้ำเพิ่มแรงดัน (BOOSTER PUMP)", "ชนิดแรงดันคงที่ ไม่น้อยกว่า 200 วัตต์"]))
        notes.append((pm, ['ชุดมาตรวัดน้ำ Ø1/2" (ผู้รับจ้างเป็นผู้ติดตั้ง)']))
        if E["settings"].get("roof", "none") != "none":
            for c in ((bx0, by1), (bx1, by1), (bx0, by0)):
                pq = v(*c)
                sh.circle(pq, 1.2, "pipe", 0.3)
                sh.circle(pq, 0.35, "pipe", 0.6)
                cb = min(cbs, key=lambda q: math.hypot(q[0] - c[0], q[1] - c[1]))
                pc = v(*cb)
                sh.line(pq, pc, "pipe", 0.3)
                _ahead(sh, (pc[0] - (2.2 if pc[0] > pq[0] else -2.2) * 0.7, pc[1] - (2.2 if pc[1] > pq[1] else -2.2) * 0.7), pq, 2.0)
            notes.append((v(bx1, by1), ['ท่อน้ำฝน RL Ø2 1/2" ลงบ่อพัก']))
        # the tanks' specification, under the column
        groups = (("ถังบำบัดน้ำเสีย", [f"ถังบำบัดน้ำเสียสำเร็จรูปชนิดไร้อากาศมีตัวกลาง",
                                      f"ขนาด {st['litres']:,} ลิตร" + (f" × {st['count']} ถัง" if st["count"] > 1 else "")
                                      + f" สำหรับผู้ใช้ {des['users']} คน",
                                      f"มอก. 2550 ขนาด {st['size']} ม.", "การติดตั้งให้เป็นไปตามมาตรฐานผู้ผลิต"]),
                  ("ถังดักไขมัน", [f"ถังดักไขมันสำเร็จรูป ไม่น้อยกว่า {des['grease']['litres']} ลิตร",
                                    f"ขนาดภายนอก {des['grease']['size']} ม. รับน้ำจากซิงก์ครัว",
                                    "ตักไขมันทุก 1–2 สัปดาห์"]))
        y_ = y0 + 64
        for head, lines in groups:
            sh.text((col_x, y_), head, 3.2, "left", "text", True)
            sh.line((col_x, y_ - 1.4), (col_x + len(head) * 2.0, y_ - 1.4), "text", 0.35)
            y_ -= 6.5
            for ln in lines:
                sh.text((col_x, y_), ln, 2.5)
                y_ -= 4.6
            y_ -= 4
        ybot = y0 + 76
    else:
        for rm in baths:
            side, wall, n = _side(rm, box, ("N", "E", "W", "S"))
            inner = -0.18                                            # under the slab, inside the wall
            mine = [fx for fx in fixtures if in_room(fx, rm)]
            lo = (rm["y"] if n[0] else rm["x"]) + 0.25
            hi = (rm["y"] + rm["d"] if n[0] else rm["x"] + rm["w"]) - 0.25
            cs = at(n, wall, inner, hi)
            pcs = v(*cs)
            ats = [hi]
            for fx in mine:
                typ = fx.get("type", "")
                if not typ.startswith(("WC", "UR", "LV", "SH", "BT", "FD")):
                    continue
                soil = typ.startswith(("WC", "UR"))
                pf = (float(fx["x"]), float(fx["y"]))
                a_ = along(n, pf)
                sh.line(v(*pf), v(*at(n, wall, inner, a_)), "pipe", 0.7 if soil else 0.4)
                ats.append(a_)
            amin = min(ats)
            sh.line(v(*at(n, wall, inner, amin)), pcs, "pipe", 0.8)
            _fco(sh, v(*at(n, wall, inner, amin)))
            sh.circle(pcs, 1.8, "pipe", 0.5)
            sh.circle(pcs, 0.8, "pipe", 0.4)
            cw = v(*at(n, wall, -0.42, hi - 0.10))
            sh.circle(cw, 1.0, "pipe", 0.3)
            sh.line((cw[0] - 0.7, cw[1] - 0.7), (cw[0] + 0.7, cw[1] + 0.7), "pipe", 0.25)
            _cw_branches(sh, v, rm, n, wall, hi - 0.10, -0.42, mine, at, along, riser=True)
            notes.append((pcs, ['ท่อโสโครกแนวดิ่ง Ø4"SW ลงถังบำบัด', 'ท่ออากาศ Ø2"V ขึ้นทะลุหลังคา']))
            notes.append((cw, ['ท่อประปาแนวดิ่ง Ø3/4"CW พร้อมประตูน้ำ']))
            notes.append((v(*at(n, wall, inner, (amin + hi) / 2)), ['ท่อ PVC Ø4"S / Ø2"W แขวนใต้พื้น ลาด 1 : 100']))
        ybot = y0 + 20
    _labels(sh, notes, col_x, y1 - 12, ybot)
    STD.caption_marks(sh, ((x0 + x1 - colw) / 2 - 50, y0 + 12), f"แปลนระบบสุขาภิบาลชั้น {k + 1}", f"1:{sc}",
                      None, None, 100.0)


# -- SN-07: the bathrooms at 1:50 and the branch sizes ---------------------------------------

#: ขนาดท่อย่อยที่ต่อเข้าสุขภัณฑ์ (นิ้ว): fitting, mark, CW, S, V, W
BRANCHES = [("โถส้วม (หม้อน้ำ)", "WC.", "1/2", "4", "2", "-"),
            ("โถส้วม (ฟลัชวาล์ว)", "WC1.", "1", "4", "2", "-"),
            ("อ่างล้างหน้า", "LAV.", "1/2", "-", "1 1/2", "2"),
            ("โถปัสสาวะชาย", "UR.", "3/4", "2", "1 1/2", "-"),
            ("ฝักบัว", "SH.", "1/2", "-", "-", "-"),
            ("สายฉีดชำระ", "HB.", "1/2", "-", "-", "-"),
            ("ก๊อกน้ำ", "C.", "1/2", "-", "-", "-"),
            ("อ่างล้างจาน", "SINK.", "1/2", "-", "1 1/2", "2"),
            ("ช่องระบายน้ำทิ้งที่พื้น", "FD.", "-", "-", "-", "2")]


def _clear_columns(fx, E, k, inner, gap=0.03):
    """The fitting slid along its wall off any column standing in the room's
    corner, so nothing is set into the structure."""
    lib = E["lib"]
    fx = dict(fx)
    for _ in range(2):
        rx = D.fixture_rect(fx)
        fx0, fy0 = min(p[0] for p in rx), min(p[1] for p in rx)
        fx1, fy1 = max(p[0] for p in rx), max(p[1] for p in rx)
        for c in (c for c in E["columns"] if c["floor"] == k):
            h = float(lib.get(c["mark"], {}).get("b", 0.2)) / 2
            cx0, cy0, cx1, cy1 = c["x"] - h, c["y"] - h, c["x"] + h, c["y"] + h
            if fx1 <= cx0 or fx0 >= cx1 or fy1 <= cy0 or fy0 >= cy1:
                continue
            # slide the short way out, along the room
            moves = [(cx1 - fx0 + gap, 0), (cx0 - fx1 - gap, 0), (0, cy1 - fy0 + gap), (0, cy0 - fy1 - gap)]
            x0, y0, x1, y1 = inner
            ok = [m for m in moves if x0 - 1e-6 <= fx0 + m[0] and fx1 + m[0] <= x1 + 1e-6 and
                  y0 - 1e-6 <= fy0 + m[1] and fy1 + m[1] <= y1 + 1e-6]
            if ok:
                dx, dy = min(ok, key=lambda m: abs(m[0]) + abs(m[1]))
                fx["x"], fx["y"] = float(fx["x"]) + dx, float(fx["y"]) + dy
    return fx


def _bath_one(sh, E, k, rm, cx, ytop, k_mm, no):
    """One bathroom's sanitary plan at ``k_mm`` mm a metre, its top-left at
    (cx - w/2, ytop): walls, fittings, the soil / waste pipes to the stack
    (upstairs) or out through the wall (ground floor), the vent, the cold
    water with a valve to each fitting; sizes; its notes on the right."""
    from core import wanic_std_sheets as STD
    t = float(E["settings"].get("wall_t") or 0.1)
    W, Dd = float(rm["w"]), float(rm["d"])
    sc = round(1000 / k_mm)
    ox = cx - W * k_mm / 2
    oy = ytop - Dd * k_mm
    v = D.View(sh, sc, (rm["x"], rm["y"]), (ox, oy))
    near = [w for w in E["walls"] if w["floor"] == k and
            min(w["p0"][0], w["p1"][0]) <= rm["x"] + W + 0.01 and max(w["p0"][0], w["p1"][0]) >= rm["x"] - 0.01 and
            min(w["p0"][1], w["p1"][1]) <= rm["y"] + Dd + 0.01 and max(w["p0"][1], w["p1"][1]) >= rm["y"] - 0.01]
    E2 = dict(E, walls=near, columns=[c for c in E["columns"] if c["floor"] == k and
                                      rm["x"] - 0.3 <= c["x"] <= rm["x"] + W + 0.3 and
                                      rm["y"] - 0.3 <= c["y"] <= rm["y"] + Dd + 0.3])
    n0 = len(sh.items)
    D.draw_walls(sh, v, E2, k, t, None, tags=False)
    bb = (*v(rm["x"] - 0.45, rm["y"] - 0.45), *v(rm["x"] + W + 0.45, rm["y"] + Dd + 0.45))
    sh.items[n0:] = STD.clip_items(sh.items[n0:], bb)
    inner = STD._inner(E, k, rm)
    fxs = [f["fx"] for f in STD.bath_fixtures(E, k, rm)]
    fxs = [_clear_columns(STD.fit_inside(f, inner), E, k, inner) for f in fxs]
    for f in fxs:
        STD.fixture_plan(sh, v, f, inner)
    # the sizes, wall to wall
    STD._hdim(sh, v(rm["x"], 0)[0], v(rm["x"] + W, 0)[0], v(0, rm["y"])[1] - 8, f"{W:.2f}")
    STD._vdim(sh, v(rm["x"], 0)[0] - 9, v(0, rm["y"])[1], v(0, rm["y"] + Dd)[1], f"{Dd:.2f}", left=True)
    p = v(rm["x"] + W * 0.42, rm["y"] + Dd * 0.42)
    lv = float(k) * float(E["H"]) - 0.05
    D.masked_text(sh, (p[0], p[1] + 1.2), rm.get("name") or "ห้องน้ำ", 2.6, "center", True)
    D.masked_text(sh, (p[0], p[1] - 3.0), f"{lv:+.2f}", 2.4)
    # the pipes: along the wall that faces out (as the floor plans)
    box = _outline(E, k)
    side, wall, n = _side(rm, box, ("N", "E", "W", "S"))

    def along(q):
        return q[1] if n[0] else q[0]

    def at(off, a):
        return (wall + n[0] * off, a) if n[0] else (a, wall + n[1] * off)
    lo = (rm["y"] if n[0] else rm["x"]) + 0.2
    hi = (rm["y"] + Dd if n[0] else rm["x"] + W) - 0.25
    ground = k == 0
    off_s = 0.30 if ground else -0.16                       # outside the wall downstairs, under the slab upstairs
    notes = []
    ats = []
    soil_any = False
    for f in fxs:
        typ = f.get("type", "")
        if not typ.startswith(("WC", "UR", "LV", "SH", "BT", "FD")):
            continue
        soil = typ.startswith(("WC", "UR"))
        soil_any |= soil
        pf = (float(f["x"]), float(f["y"]))
        a = along(pf)
        sh.line(v(*pf), v(*at(off_s, a)), "pipe", 0.8 if soil else 0.45)
        if ground:
            STD_flex = _flex
            STD_flex(sh, v(*at(0.10, a)), v(*at(off_s, a)))
        ats.append(a)

    fd = next((f for f in fxs if f.get("type") == "FD"), None)
    a_end = hi if not ground else (lo + hi) / 2
    ats.append(a_end)
    if ats:
        amin, amax = min(ats), max(ats)
        sh.line(v(*at(off_s, amin)), v(*at(off_s, amax)), "pipe", 0.9)
        _fco(sh, v(*at(off_s, amin if abs(amin - a_end) > 0.05 else amax)))
        pe = v(*at(off_s, a_end))
        if ground:
            pt = v(*at(off_s + 0.55, a_end))
            sh.line(pe, pt, "pipe", 0.9)
            _ahead(sh, pt, pe, 2.4)
            notes.append((pt, ['Ø4"SW ลงถังบำบัดน้ำเสีย', "ลาด 1 : 100"]))
        else:
            sh.circle(pe, v.len(0.07), "pipe", 0.5)
            sh.circle(pe, v.len(0.03), "pipe", 0.4)
            notes.append((pe, ['ท่อโสโครกแนวดิ่ง Ø4"SW', 'ท่ออากาศ Ø2"V ขึ้นทะลุหลังคา']))
        notes.append((v(*at(off_s, (amin + amax) / 2)), ['ท่อ Ø4"S / Ø2"W' + (" แขวนใต้พื้น" if not ground else " ใต้พื้น")]))
        notes.append((v(*at(off_s, amin if abs(amin - a_end) > 0.05 else amax)), ["FCO ช่องเปิดล้างท่อ"]))
    # the vent, dashed, from the WC to the stack / out of the wall
    wc = next((f for f in fxs if f.get("type", "").startswith("WC")), None)
    if wc is not None:
        a = along((float(wc["x"]), float(wc["y"])))
        pv0, pv1 = v(*at(-0.30, a)), v(*at(-0.30, a_end))
        sh.line(pv0, pv1, "pipe", 0.35, True)
        sh.line(v(float(wc["x"]), float(wc["y"])), pv0, "pipe", 0.35, True)
        notes.append(((pv0[0] + pv1[0]) / 2 + 0.01, ) and (((pv0[0] + pv1[0]) / 2, (pv0[1] + pv1[1]) / 2),
                                                           ['ท่ออากาศ Ø1 1/2"V']))
    # the cold water
    a_cw = hi - 0.10 if not ground else lo
    pcw = v(*at(-0.42, a_cw))
    sh.circle(pcw, 1.0, "pipe", 0.3)
    _cw_branches(sh, v, rm, n, wall, a_cw, -0.42, fxs, lambda n_, w_, o_, a_: at(o_, a_), lambda n_, q_: along(q_))
    notes.append((pcw, ['ท่อประปา Ø3/4"CW' + (" ขึ้นจากใต้พื้น" if ground else " จากท่อแนวดิ่ง"),
                        'ท่อแยก Ø1/2" + STOP VALVE ทุกสุขภัณฑ์']))
    if fd is not None:
        q = v(float(fd["x"]), float(fd["y"]))
        notes.append((q, ['FD Ø2" ฟลอร์เดรนกันกลิ่น']))
    col_x = v(rm["x"] + W, 0)[0] + 14
    _labels(sh, notes, col_x, ytop + 4, oy - 4, 2.4)
    STD.caption_marks(sh, (ox - 4, oy - 26), f"แปลนระบบสุขาภิบาลห้องน้ำ {no}", f"1:{sc}", None, None, 80.0)
    sh.text((ox - 4, oy - 37), "(ท่อประปาเดินใต้พื้น)" if ground else "(ท่อประปาเดินใต้พื้น แขวนใต้ฝ้าชั้นล่าง)", 2.6)
    return oy - 40


def sn_bath_std(sh, E, items, first_no=1):
    """SN-07 «แบบขยายระบบสุขาภิบาลห้องน้ำ»: up to two bathrooms side by side
    at 1:50, the branch-size table under them."""
    x0, y0, x1, y1 = D.drawing_area()
    W = x1 - x0
    slot = W / 2
    k_mm = 20.0
    big = max(max(float(rm["w"]), float(rm["d"])) for _k, rm in items)
    if big * k_mm > slot - 82:
        k_mm = (slot - 82) / big
    ybot = y1
    for i, (k, rm) in enumerate(items):
        cx = x0 + slot * i + 14 + float(rm["w"]) * k_mm / 2
        ybot = min(ybot, _bath_one(sh, E, k, rm, cx, y1 - 22, k_mm, first_no + i))
    # the table
    cols = [("สุขภัณฑ์", 52.0), ("สัญลักษณ์", 28.0), ("CW.", 22.0), ("S.", 22.0), ("V.", 22.0), ("W.", 22.0)]
    tw = sum(c[1] for c in cols)
    tx = x0 + (W - tw) / 2
    ty = ybot - 4
    head = 9.0
    rh = 5.6
    th = head + 10.4 + rh * len(BRANCHES)
    sh.rect(tx, ty - th, tx + tw, ty, "text", 0.45)
    sh.text((tx + tw / 2, ty - 6.4), "ขนาดท่อย่อยที่ต่อเข้าสุขภัณฑ์", 3.4, "center", "text", True)
    sh.line((tx, ty - head), (tx + tw, ty - head), "text", 0.3)
    xs = [tx]
    for _h, w in cols:
        xs.append(xs[-1] + w)
    sh.text(((xs[2] + xs[6]) / 2, ty - head - 3.6), "ขนาดท่อ (นิ้ว)", 2.4, "center")
    sh.line((xs[2], ty - head - 5.0), (xs[6], ty - head - 5.0), "text", 0.2)
    for i, (h, w) in enumerate(cols):
        yy = ty - head - (8.8 if i >= 2 else 6.4)
        sh.text(((xs[i] + xs[i + 1]) / 2, yy), h, 2.4, "center", "text", True)
    y = ty - head - 10.4
    sh.line((tx, y), (tx + tw, y), "text", 0.3)
    for c in xs[1:-1]:
        sh.line((c, ty - th), (c, ty - head if c <= xs[2] else ty - head - 5.0), "text", 0.2)
    for row in BRANCHES:
        for i, val in enumerate(row):
            sh.text(((xs[i] + 2) if i == 0 else (xs[i] + xs[i + 1]) / 2, y - rh + 1.6), val, 2.4,
                    "left" if i == 0 else "center")
        y -= rh
        sh.line((tx, y), (tx + tw, y), "text", 0.12)


# -- SN-08, SN-09, SN-10: the installation details and the hangers ---------------------------

def _slab(sh, x0, x1, y, t=7.0, label=True):
    """A floor slab in section, its top at y: outline, concrete stipple."""
    from core import wanic_std_sheets as STD
    sh.line((x0, y), (x1, y), "cut", 0.5)
    sh.line((x0, y - t), (x1, y - t), "cut", 0.5)
    STD._stipple(sh, (x0, y - t), (x1, y), 6.0)
    STD._break_v(sh, x0, y - t, y)
    STD._break_v(sh, x1, y - t, y)
    if label:
        sh.text((x1 - 26, y + 1.2), "ระดับผิวพื้น", 2.3)
        q = (x1 - 6, y)
        sh.poly([q, (q[0] - 1.4, q[1] + 2.2), (q[0] + 1.4, q[1] + 2.2)], "dim", 0.25)


def _wall_v(sh, x, y0, y1, w=5.0):
    sh.line((x, y0), (x, y1), "cut", 0.5)
    sh.line((x + w, y0), (x + w, y1), "cut", 0.5)
    yy = y0
    while yy < y1 - 1:
        sh.line((x, yy), (x + w, min(yy + w, y1)), "hatch", 0.12)
        yy += 2.5


def _vp(sh, x, y0, y1, d=2.4, w=0.35):
    sh.line((x - d / 2, y0), (x - d / 2, y1), "pipe", w)
    sh.line((x + d / 2, y0), (x + d / 2, y1), "pipe", w)


def _hp(sh, y, x0, x1, d=2.4, w=0.35):
    sh.line((x0, y - d / 2), (x1, y - d / 2), "pipe", w)
    sh.line((x0, y + d / 2), (x1, y + d / 2), "pipe", w)


def _note(sh, p, tx, ty, lines, right=True, size=2.4):
    """A leader from the text at (tx, ty) to p, its arrowhead at p."""
    sh.line((tx + (-1.0 if right else 1.0), ty), p, "text", 0.18)
    _ahead(sh, p, (tx, ty), 1.9, "text")
    for j, ln in enumerate(lines):
        sh.text((tx, ty - 0.9 - j * 4.4), ln, size, "left" if right else "right")


def _box_title(sh, cx, y, text):
    """The detail's name in a box (the standard's)."""
    w = len(text) * 2.25 + 12
    sh.rect(cx - w / 2, y - 4.5, cx + w / 2, y + 4.5, "text", 0.45)
    sh.text((cx, y - 1.4), text, 3.4, "center", "text", True)


def _det_lav(sh, ox, oy):
    """อ่างล้างหน้า (LAV): the basin on the wall, the stop valve, the trap,
    the waste down through the slab, the vent up the wall, the air chamber."""
    _wall_v(sh, ox + 4, oy, oy + 92)
    _slab(sh, ox - 6, ox + 66, oy + 20)
    sh.poly([(ox + 9, oy + 52), (ox + 34, oy + 52), (ox + 31, oy + 46), (ox + 12, oy + 46)], "fixture", 0.45)
    sh.line((ox + 22, oy + 52), (ox + 22, oy + 56), "fixture", 0.4)
    sh.line((ox + 22, oy + 56), (ox + 27, oy + 56), "fixture", 0.4)
    xw = ox + 20                                           # the waste
    sh.poly([(xw, oy + 46), (xw, oy + 38), (xw + 4, oy + 34), (xw + 8, oy + 38), (xw + 8, oy + 40), (ox + 12, oy + 40)],
            "pipe", 0.45, closed=False)
    _vp(sh, ox + 12, oy + 4, oy + 40, 2.6)
    _vp(sh, ox + 12, oy + 40, oy + 90, 1.8, 0.3)          # the vent up the wall
    xc = ox + 16                                           # the cold water with its air chamber
    sh.line((xc, oy + 20), (xc, oy + 72), "pipe", 0.4)
    sh.circle((xc, oy + 42), 0.9, "pipe", 0.35)
    sh.line((xc, oy + 42), (ox + 26, oy + 46), "pipe", 0.3)
    sh.line((xc, oy + 72), (xc, oy + 74), "pipe", 0.7)
    for x_, y_, lines in ((ox + 12, oy + 82, ['ท่อระบายอากาศ Ø1 1/2"']), (xc, oy + 73, ["ปลั๊กอุดปลายท่อ (AIR CHAMBER 0.30)"]),
                          (ox + 26, oy + 46, ['STOP VALVE Ø1/2"']), (xw + 4, oy + 34, ['ที่ดักกลิ่น Ø1 1/2"']),
                          (xc, oy + 30, ["ท่อประปา"]), (ox + 12, oy + 10, ['ท่อน้ำทิ้ง Ø2"'])):
        _note(sh, (x_ + 1.4, y_), ox + 70, y_ + 0.0, lines)
    _box_title(sh, ox + 40, oy - 8, "อ่างล้างหน้า ( LAV )")


def _det_wc(sh, ox, oy):
    """โถส้วมชนิดถังน้ำล้าง (FLUSH TANK): the bowl and tank, the stop valve,
    the soil pipe down through the slab with its long bend, the vent."""
    _wall_v(sh, ox + 54, oy, oy + 92)
    _slab(sh, ox - 6, ox + 66, oy + 26)
    sh.poly([(ox + 22, oy + 26), (ox + 22, oy + 34), (ox + 14, oy + 38), (ox + 14, oy + 40), (ox + 40, oy + 40),
             (ox + 42, oy + 34), (ox + 36, oy + 26)], "fixture", 0.45)
    sh.rect(ox + 40, oy + 40, ox + 52, oy + 56, "fixture", 0.45)                # the tank
    _vp(sh, ox + 32, oy + 4, oy + 26, 3.2, 0.45)                               # the soil
    sh.poly([(ox + 30.4, oy + 8), (ox + 34, oy + 4), (ox + 66, oy + 4)], "pipe", 0.45, closed=False)
    sh.poly([(ox + 33.6, oy + 8), (ox + 36, oy + 7.2), (ox + 66, oy + 7.2)], "pipe", 0.45, closed=False)
    _vp(sh, ox + 48, oy + 4, oy + 92, 1.8, 0.3)                                 # the vent
    xc = ox + 44
    sh.line((xc, oy + 26), (xc, oy + 70), "pipe", 0.4)
    sh.line((xc, oy + 44), (ox + 41, oy + 44), "pipe", 0.35)
    sh.circle((xc, oy + 44), 0.9, "pipe", 0.35)
    for x_, y_, lines in ((ox + 48, oy + 80, ['ท่อระบายอากาศ Ø2"']), (xc, oy + 68, ["ปลั๊กอุดปลายท่อ (AIR CHAMBER 0.30)"]),
                          (xc, oy + 44, ['STOP VALVE Ø1/2"']), (ox + 60, oy + 5.6, ['ท่อโสโครก Ø4" ข้องอยาว 90°'])):
        _note(sh, (x_ + 1.4, y_), ox + 72, y_ + (0 if y_ > 20 else 8), lines)
    _box_title(sh, ox + 28, oy - 8, "ส้วมชนิดถังน้ำล้าง ( FLUSH TANK )")


def _det_sh(sh, ox, oy):
    """ฝักบัวอาบน้ำ (SH): the head on its arm, the valve, the air chamber."""
    _wall_v(sh, ox + 4, oy, oy + 92)
    _slab(sh, ox - 6, ox + 40, oy + 20)
    xc = ox + 12
    sh.line((xc, oy + 20), (xc, oy + 82), "pipe", 0.4)
    sh.line((xc, oy + 82), (xc, oy + 84), "pipe", 0.7)
    sh.poly([(xc, oy + 74), (xc + 8, oy + 76), (xc + 10, oy + 74)], "pipe", 0.4, closed=False)
    sh.poly([(xc + 9, oy + 74), (xc + 12, oy + 72), (xc + 7, oy + 71)], "fixture", 0.4)
    _gate(sh, xc + 3, oy + 46)
    sh.line((xc, oy + 46), (xc + 1.2, oy + 46), "pipe", 0.35)
    for x_, y_, lines in ((xc, oy + 83, ["AIR CHAMBER 0.30"]), (xc + 10, oy + 73, ["หัวฝักบัว"]),
                          (xc + 4, oy + 46, ["ก๊อกผสม / วาล์วฝักบัว"]), (xc, oy + 30, ["ท่อประปา"])):
        _note(sh, (x_ + 1.4, y_), ox + 44, y_, lines)
    _box_title(sh, ox + 34, oy - 8, "ฝักบัวอาบน้ำ ( SH )")


def _det_rfd(sh, ox, oy):
    """แบบขยายช่องระบายน้ำฝน (RFD): the flat roof drain in the slab, the pipe down."""
    _slab(sh, ox - 6, ox + 70, oy + 40, 8.0)
    cx = ox + 30
    sh.fill([(cx - 7, oy + 40.1), (cx + 7, oy + 40.1), (cx + 7, oy + 31), (cx - 7, oy + 31)], "mask", 0.0)
    sh.rect(cx - 7, oy + 39, cx + 7, oy + 41, "pipe", 0.45)                     # the grating
    sh.poly([(cx - 6, oy + 39), (cx - 5, oy + 32), (cx + 5, oy + 32), (cx + 6, oy + 39)], "pipe", 0.4)
    _vp(sh, cx, oy + 4, oy + 32, 8.0, 0.45)
    for x_, y_, lines in ((cx + 7, oy + 40, ["ตะแกรงรูระบายน้ำฝนแบบเรียบ (RFD)"]), (cx + 6, oy + 35, ["ฝังในพื้น คสล. ยาแนวกันซึม"]),
                          (cx + 4, oy + 14, ['ท่อน้ำฝน RL Ø3"'])):
        _note(sh, (x_ + 0.6, y_), ox + 74, y_ + 4, lines)
    _box_title(sh, ox + 34, oy - 8, "แบบขยายช่องระบายน้ำฝน ( RFD )")


def _det_fd(sh, ox, oy, fco=False):
    """FD (ช่องระบายน้ำทิ้งที่พื้น) / FCO (ช่องทำความสะอาดท่อที่พื้น): the
    grating (plan above), the body in the slab, the trap or the bend, the
    hanger, the pipe on."""
    from core import wanic_std_sheets as STD
    cx = ox + 26
    sh.circle((cx, oy + 92), 9.0, "pipe", 0.45)                                # the plan of the cover
    if fco:
        sh.circle((cx, oy + 92), 7.0, "pipe", 0.3)
        for i in range(-6, 7, 2):
            h = math.sqrt(max(49 - i * i, 0))
            sh.line((cx + i, oy + 92 - h), (cx + i, oy + 92 + h), "hatch", 0.15)
    else:
        for r in (2.5, 5.0, 7.5):
            sh.circle((cx, oy + 92), r, "pipe", 0.2)
        for a in range(0, 360, 30):
            sh.line((cx + 2.5 * math.cos(math.radians(a)), oy + 92 + 2.5 * math.sin(math.radians(a))),
                    (cx + 7.5 * math.cos(math.radians(a)), oy + 92 + 7.5 * math.sin(math.radians(a))), "pipe", 0.15)
    _note(sh, (cx + 9, oy + 92), ox + 44, oy + 96, ["ฝาสแตนเลส / ทองเหลือง" if fco else "ตะแกรงทองเหลือง (BRASS)"])
    _slab(sh, ox - 8, ox + 80, oy + 70, 8.0)
    sh.fill([(cx - 6, oy + 70.1), (cx + 6, oy + 70.1), (cx + 6, oy + 62), (cx - 6, oy + 62)], "mask", 0.0)
    sh.poly([(cx - 6, oy + 70), (cx - 6, oy + 63), (cx - 3, oy + 60), (cx + 3, oy + 60), (cx + 6, oy + 63), (cx + 6, oy + 70)],
            "pipe", 0.45)
    sh.line((cx - 6, oy + 69), (cx + 6, oy + 69), "pipe", 0.6)
    _vp(sh, cx, oy + 48, oy + 60, 4.0, 0.45)
    if fco:                                                                     # a long bend on to the pipe
        sh.arc((cx + 10, oy + 48), 8.0, 180, 270, "pipe", 0.45)
        sh.arc((cx + 10, oy + 48), 12.0, 180, 270, "pipe", 0.45)
        _hp(sh, oy + 38, cx + 10, ox + 78, 4.0, 0.45)
        _note(sh, (cx + 2, oy + 44), ox + 50, oy + 58, ["ข้องอ 90° รัศมีกว้าง"])
        _note(sh, (ox + 70, oy + 38), ox + 50, oy + 26, ["ชนิดของท่อดูในรายการประกอบแบบ"])
    else:                                                                       # the P-trap
        sh.arc((cx + 6, oy + 44), 6.0, 180, 360, "pipe", 0.45)
        sh.arc((cx + 6, oy + 44), 2.0, 180, 360, "pipe", 0.45)
        sh.line((cx + 12, oy + 44), (cx + 12, oy + 52), "pipe", 0.45)
        sh.line((cx + 8, oy + 44), (cx + 8, oy + 48), "pipe", 0.45)
        sh.arc((cx + 16, oy + 52), 4.0, 90, 180, "pipe", 0.45)
        sh.arc((cx + 16, oy + 52), 8.0, 90, 180, "pipe", 0.45)
        _hp(sh, oy + 58, cx + 16, ox + 78, 4.0, 0.45)
        _note(sh, (cx + 2, oy + 54), ox + 50, oy + 46, ["ช่องระบายน้ำทิ้ง"])
        _note(sh, (cx + 10, oy + 40), ox + 50, oy + 36, ["ที่ดักกลิ่นรูป P"])
        _note(sh, (ox + 70, oy + 58), ox + 50, oy + 26, ["ท่อน้ำทิ้ง (ลาด 1 : 100)"])
    sh.line((ox + 56, oy + 62), (ox + 56, oy + 70 - 8), "pipe", 0.3)          # the hanger
    sh.line((ox + 56, oy + 62), (ox + 56, oy + (40 if fco else 60)), "pipe", 0.3)
    _box_title(sh, ox + 36, oy + 6, "ช่องสำหรับทำความสะอาดท่อที่พื้น ( FCO )" if fco else "ช่องระบายน้ำทิ้งที่พื้น ( FD )")


def _det_co(sh, ox, oy):
    """CO (ช่องทำความสะอาดท่อใต้พื้น): the stack down through the slab,
    the 45° wye on the horizontal pipe, its plug, the hangers."""
    _slab(sh, ox - 8, ox + 80, oy + 82, 8.0)
    xs = ox + 22
    _vp(sh, xs, oy + 50, oy + 96, 4.0, 0.45)
    sh.poly([(xs - 2, oy + 50), (xs + 12, oy + 36), (xs + 16, oy + 36)], "pipe", 0.45, closed=False)
    sh.poly([(xs + 2, oy + 50), (xs + 14, oy + 38)], "pipe", 0.45, closed=False)
    _hp(sh, oy + 34, ox - 6, ox + 78, 4.0, 0.45)
    sh.line((ox - 6, oy + 30), (ox - 6, oy + 38), "pipe", 0.6)                 # the plug
    for xh in (ox + 8, ox + 60):
        sh.line((xh, oy + 74), (xh, oy + 36), "pipe", 0.3)
    _note(sh, (xs + 2, oy + 90), ox + 44, oy + 92, ["ท่อแนวดิ่ง"])
    _note(sh, (ox - 6, oy + 34), ox + 44, oy + 24, ["ช่องสำหรับทำความสะอาดอุดด้วยปลั๊ก"])
    _note(sh, (xs + 10, oy + 40), ox + 44, oy + 16, ["ข้อต่อสามทางวาย (Y) 45°"])
    _box_title(sh, ox + 36, oy + 4, "ช่องสำหรับทำความสะอาดท่อใต้พื้น ( CO )")


def _det_avc(sh, ox, oy):
    """AVC: the vent's wall cap, front and section."""
    cx, cy = ox + 18, oy + 60
    sh.arc((cx, cy), 12.0, 180, 360, "pipe", 0.45)
    for r in (3.0, 6.0, 9.0):
        sh.arc((cx, cy), r, 180, 360, "pipe", 0.2)
    sh.line((cx - 12, cy), (cx + 12, cy), "pipe", 0.45)
    _wall_v(sh, ox + 48, oy + 40, oy + 82, 6.0)
    sh.rect(ox + 44, cy - 10, ox + 48, cy + 10, "pipe", 0.45)                  # the louvred cap
    for i in range(5):
        sh.line((ox + 44, cy - 8 + i * 4), (ox + 41, cy - 10 + i * 4), "pipe", 0.3)
    _hp(sh, cy, ox + 54, ox + 76, 5.0, 0.45)
    _note(sh, (ox + 44, cy + 9), ox + 2, oy + 88, ["ฝาครอบกันแมลง สแตนเลส"], right=True)
    _note(sh, (ox + 70, cy + 2.5), ox + 58, oy + 34, ['ท่ออากาศ Ø2"V'])
    _box_title(sh, ox + 38, oy + 24, "แบบขยายฝาเปิดท่อระบายอากาศ ( AVC )")


def sn_fixture_details(sh, E):
    """SN-08 «แบบขยายการติดตั้งท่อ (แผ่นที่ 1)»: LAV, FLUSH TANK, SH, RFD."""
    x0, y0, x1, y1 = D.drawing_area()
    W = x1 - x0
    _det_lav(sh, x0 + 8, y1 - 108)
    _det_wc(sh, x0 + W * 0.50, y1 - 108)
    _det_sh(sh, x0 + 8, y0 + 18)
    _det_rfd(sh, x0 + W * 0.33, y0 + 18)
    D.notes_block(sh, x0 + W * 0.72, y0 + 96, "หมายเหตุ", [
        "1. ระดับติดตั้งสุขภัณฑ์และอุปกรณ์ ให้ตรวจสอบกับแบบสถาปัตยกรรมและคำแนะนำของผู้ผลิต",
        "2. ทุกจุดจ่ายน้ำติดตั้ง STOP VALVE และท่อกันกระแทก (AIR CHAMBER) ยาวไม่น้อยกว่า 0.30 ม.",
        "3. ท่อระบายน้ำทุกจุดต้องมีที่ดักกลิ่น และต่อท่ออากาศตามแบบ"], 2.6, 40)


def sn_drain_details(sh, E):
    """SN-09 «แบบขยายการติดตั้งท่อ (แผ่นที่ 2)»: FD, FCO, CO, AVC."""
    x0, y0, x1, y1 = D.drawing_area()
    W = x1 - x0
    _det_fd(sh, x0 + 10, y1 - 122)
    _det_fd(sh, x0 + W * 0.52, y1 - 122, fco=True)
    _det_co(sh, x0 + 10, y0 + 6)
    _det_avc(sh, x0 + W * 0.56, y0 + 6)


HANGER_SPACING = [("15 (1/2)", "2.4", "2.0", "1.2", "0.9"), ("20 (3/4)", "3.0", "2.4", "1.2", "1.0"),
                  ("25 (1)", "3.0", "2.4", "1.2", "1.0"), ("32 (1 1/4)", "3.0", "2.4", "1.8", "1.2"),
                  ("40 (1 1/2)", "3.6", "3.0", "1.8", "1.3"), ("50 (2)", "3.6", "3.0", "1.8", "1.5"),
                  ("65 (2 1/2)", "4.5", "3.0", "2.4", "1.8"), ("80 (3)", "4.5", "3.6", "2.4", "2.0"),
                  ("100 (4)", "4.5", "4.0", "2.4", "2.4")]
HANGER_ROD = [("15 – 40 (1/2 – 1 1/2)", "9"), ("50 – 80 (2 – 3)", "12"), ("100 – 150 (4 – 6)", "15")]


def _rows(sh, x, y, cols, rows, head, size=2.4, rh=5.6):
    """A plain table: ``head`` lines over the columns, then the rows."""
    w = sum(c for c in cols)
    xs = [x]
    for c in cols:
        xs.append(xs[-1] + c)
    hh = 5.6 * len(head)
    sh.rect(x, y - hh - rh * len(rows), x + w, y, "text", 0.45)
    for j, line in enumerate(head):
        for i, t in enumerate(line):
            if t:
                sh.text(((xs[i] + xs[i + 1]) / 2, y - 4.0 - j * 5.6), t, size, "center", "text", True)
    sh.line((x, y - hh), (x + w, y - hh), "text", 0.3)
    yy = y - hh
    for r in rows:
        for i, t in enumerate(r):
            sh.text(((xs[i] + xs[i + 1]) / 2, yy - rh + 1.6), t, size, "center")
        yy -= rh
        sh.line((x, yy), (x + w, yy), "text", 0.12)
    for c in xs[1:-1]:
        sh.line((c, y - hh - rh * len(rows)), (c, y - hh), "text", 0.2)
    return y - hh - rh * len(rows)


def sn_hangers(sh, E):
    """SN-10 «แบบขยายและตารางระยะการแขวนท่อ»: the hanger in section and
    along the pipe, the notes, the spacing and the rod tables."""
    x0, y0, x1, y1 = D.drawing_area()
    W = x1 - x0
    # the hanger, section
    cx, ys = x0 + 50, y1 - 40
    _slab(sh, x0 + 14, x0 + 92, ys, 7.0, label=False)
    sh.text((x0 + 16, ys + 1.2), "พื้น คสล.", 2.3)
    sh.line((cx, ys - 7), (cx, ys - 26), "pipe", 0.35)
    sh.circle((cx, ys - 32), 5.0, "pipe", 0.45)
    sh.circle((cx, ys - 32), 3.6, "hatch", 0.2)
    sh.poly([(cx - 5.6, ys - 30), (cx, ys - 26), (cx + 5.6, ys - 30)], "pipe", 0.35, closed=False)
    sh.arc((cx, ys - 32), 5.8, 180, 360, "pipe", 0.4)
    _note(sh, (cx, ys - 7), x0 + 104, ys + 2, ["โบลต์ฝังหรือพุกเหล็กชุบสังกะสี", "(กรณีอาคารเดิมให้ยึดด้วยพุกเหล็ก)"])
    _note(sh, (cx, ys - 20), x0 + 104, ys - 14, ["เหล็กแขวน (เหล็กเส้นชุบสังกะสี)"])
    _note(sh, (cx + 5.8, ys - 32), x0 + 104, ys - 24, ["เหล็กรัดท่อ (CLEVIS HANGER)"])
    _note(sh, (cx + 3.6, ys - 34), x0 + 104, ys - 32, ["ท่อ"])
    # along the pipe
    ya = y1 - 112
    _slab(sh, x0 + 6, x0 + 150, ya, 7.0, label=False)
    _hp(sh, ya - 34, x0 + 10, x0 + 146, 6.0, 0.45)
    for xh in (x0 + 40, x0 + 80, x0 + 120):
        sh.line((xh, ya - 7), (xh, ya - 31), "pipe", 0.35)
        sh.arc((xh, ya - 34), 3.6, 180, 360, "pipe", 0.4)
    for xj in (x0 + 26, x0 + 100):
        sh.rect(xj - 2, ya - 38, xj + 2, ya - 30, "pipe", 0.35)
    _box_title(sh, x0 + 78, ya - 52, "แบบขยายเหล็กแขวนท่อ")
    D.notes_block(sh, x0 + 6, ya - 66, "หมายเหตุ", [
        "1. ท่อแต่ละท่อนต้องมีที่ยึดแขวนหรือรองรับอย่างน้อยหนึ่งแห่ง",
        "2. ทุกชั้นของอาคาร และทุกช่วงข้อต่อ ระยะไม่เกินตามตาราง",
        "3. ท่อแนวดิ่งยึดกับผนังหรือเสาทุกระยะไม่เกิน 1.50 ม. และทุกชั้น",
        "4. ท่อที่ผ่านผนังหรือพื้นให้ใส่ปลอกท่อ (SLEEVE) อุดด้วยวัสดุกันน้ำ"], 2.6, 72)
    # the tables
    tx = x0 + W * 0.56
    sh.text((tx, y1 - 8), "ระยะระหว่างที่ยึดท่อที่แขวนท่อหรือที่รองรับท่อ", 3.2, "left", "text", True)
    sh.text((tx, y1 - 13), "ต่าง ๆ ในแนวดิ่งและแนวนอน", 3.2, "left", "text", True)
    yb = _rows(sh, tx, y1 - 18, [30, 24, 24, 24, 24],
               HANGER_SPACING, [("ขนาดท่อ", "ท่อเหล็กอาบสังกะสี", "", "ท่อ PVC", ""),
                                ("มม. (นิ้ว)", "แนวดิ่ง (ม.)", "แนวนอน (ม.)", "แนวดิ่ง (ม.)", "แนวนอน (ม.)")])
    sh.text((tx, yb - 12), "ขนาดของเหล็กเส้นที่ใช้แขวนท่อเดินในแนวระดับ", 3.2, "left", "text", True)
    _rows(sh, tx, yb - 17, [60, 46], HANGER_ROD, [("ขนาดท่อ มม. (นิ้ว)", "เส้นผ่านศูนย์กลางเหล็ก (มม.)")])


# -- the details, drawn again (round 2): continuous pipes, fittings clear of the wall, tidy notes

def _fillet(pts, r):
    """A polyline with its corners rounded (radius r), for pipe bends."""
    if len(pts) < 3 or r <= 0:
        return list(pts)
    out = [pts[0]]
    for a, b, c in zip(pts, pts[1:], pts[2:]):
        u = (a[0] - b[0], a[1] - b[1])
        w = (c[0] - b[0], c[1] - b[1])
        lu, lw = math.hypot(*u) or 1, math.hypot(*w) or 1
        rr = min(r, lu / 2, lw / 2)
        p0 = (b[0] + u[0] / lu * rr, b[1] + u[1] / lu * rr)
        p1 = (b[0] + w[0] / lw * rr, b[1] + w[1] / lw * rr)
        for i in range(7):                                   # a quadratic Bézier through the corner
            t = i / 6
            out.append(((1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * b[0] + t * t * p1[0],
                        (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * b[1] + t * t * p1[1]))
    out.append(pts[-1])
    return out


def _pipe(sh, pts, d, w=0.4, r=None, sockets=(), mask=True):
    """A pipe along ``pts`` (paper), ``d`` wide: both walls, continuous, the
    bends rounded; a socket (a short wider band) at each point of ``sockets``."""
    pts = _fillet(pts, d * 1.6 if r is None else r)
    if mask:
        for a, b in zip(pts, pts[1:]):
            L = math.hypot(b[0] - a[0], b[1] - a[1]) or 1
            nx, ny = -(b[1] - a[1]) / L * d / 2, (b[0] - a[0]) / L * d / 2
            sh.fill([(a[0] + nx, a[1] + ny), (b[0] + nx, b[1] + ny), (b[0] - nx, b[1] - ny), (a[0] - nx, a[1] - ny)],
                    "mask", 0.0)
    for side in (-1, 1):
        sh.poly(D._offset_line(pts, side * d / 2), "pipe", w, closed=False)
    for s in sockets:
        (x, y), vertical = s if isinstance(s[0], tuple) else (s, True)
        if vertical:
            sh.rect(x - d / 2 - 0.5, y - 1.3, x + d / 2 + 0.5, y + 1.3, "pipe", 0.3)
        else:
            sh.rect(x - 1.3, y - d / 2 - 0.5, x + 1.3, y + d / 2 + 0.5, "pipe", 0.3)


def _wall_on_slab(sh, xa, xb, ybot, ytop):
    """A wall standing on the slab: its two faces, the brick hatch, a break at the top."""
    from core import wanic_std_sheets as STD
    sh.fill([(xa, ybot), (xb, ybot), (xb, ytop), (xa, ytop)], "mask", 0.0)
    sh.line((xa, ybot), (xa, ytop), "cut", 0.5)
    sh.line((xb, ybot), (xb, ytop), "cut", 0.5)
    y = ybot
    while y < ytop - 0.5:
        sh.line((xa, y), (xb, min(y + (xb - xa), ytop)), "hatch", 0.12)
        y += 2.4
    STD._break_h(sh, ytop, xa, xb)


def _notes(sh, items, col_x, right=True, size=2.4, gap=5.4):
    """Notes in an aligned column: each leader runs level from its text and
    turns once to its item (arrowhead at the item); kept ``gap`` mm apart."""
    items = sorted(items, key=lambda t: -t[0][1])
    ys, last = [], 1e9
    for p, lines in items:
        ty = min(p[1], last - gap)
        ys.append(ty)
        last = ty - 4.4 * (len(lines) - 1)
    for (p, lines), ty in zip(items, ys):
        knee = (p[0] + (5.0 if right else -5.0), ty) if abs(ty - p[1]) > 0.4 else p
        sh.line((col_x - (1.0 if right else -1.0), ty), knee, "text", 0.18)
        if knee is not p:
            sh.line(knee, p, "text", 0.18)
        _ahead(sh, p, knee if knee is not p else (col_x, ty), 1.9, "text")
        for j, ln in enumerate(lines):
            sh.text((col_x, ty - 0.9 - j * 4.4), ln, size, "left" if right else "right")


def _floor_mark(sh, x, y, text="ระดับผิวพื้น"):
    sh.poly([(x, y), (x - 1.4, y + 2.2), (x + 1.4, y + 2.2)], "dim", 0.25)
    sh.text((x + 2.2, y + 0.9), text, 2.3)


def _det_lav(sh, ox, oy):
    """อ่างล้างหน้า (LAV): the wall on the slab, the basin in front of its
    face, the trap and the waste down through the slab, the vent up, the
    cold water with its stop valve and air chamber."""
    from core import wanic_std_sheets as STD
    ys = oy + 22                                            # the floor
    xa, xb = ox + 4, ox + 9
    _slab(sh, ox - 8, ox + 64, ys, 7.0, label=False)
    xf = xb                                                 # the wall's face
    xw, xc = xf + 4.0, xf + 9.0                             # the waste / vent, the cold water
    _pipe(sh, [(xw, ys + 22), (xw, oy + 6), (ox + 62, oy + 6)], 3.4, sockets=[((xw, ys + 20), True)])
    _pipe(sh, [(xw, ys + 22), (xw, oy + 94)], 2.2, 0.35)
    sh.line((xw - 2.2, oy + 94), (xw + 2.2, oy + 94), "pipe", 0.6)
    _pipe(sh, [(xf + 19, ys + 32), (xf + 19, ys + 22), (xf + 24, ys + 22), (xf + 24, ys + 26),
               (xw + 1.7, ys + 26)], 2.4, 0.35, r=2.2)                 # the P-trap and its arm
    _pipe(sh, [(xc, ys - 7), (xc, ys + 52)], 1.6, 0.35)
    sh.line((xc - 1.3, ys + 52), (xc + 1.3, ys + 52), "pipe", 0.7)      # the air chamber's cap
    _pipe(sh, [(xc, ys + 29), (xf + 13, ys + 29)], 1.2, 0.3)
    _gate(sh, xf + 13, ys + 29)
    # the basin in front of the wall's face (masked: the pipes run behind it)
    bas = [(xf, ys + 40), (xf + 30, ys + 40), (xf + 27, ys + 32), (xf + 4, ys + 32), (xf, ys + 35)]
    sh.fill(bas, "mask", 0.0)
    sh.poly(bas, "fixture", 0.5)
    sh.line((xf + 19, ys + 32), (xf + 19, ys + 31), "fixture", 0.4)
    sh.poly([(xf + 18, ys + 40), (xf + 18, ys + 44), (xf + 24, ys + 44)], "fixture", 0.45, closed=False)
    _wall_on_slab(sh, xa, xb, ys, oy + 98)
    _floor_mark(sh, ox + 46, ys)
    _notes(sh, [((xw + 1.1, oy + 82), ['ท่อระบายอากาศ Ø1 1/2"']),
                ((xc + 0.8, ys + 51), ["ปลั๊กอุดปลายท่อ (AIR CHAMBER 0.30 ม.)"]),
                ((xf + 14.8, ys + 29), ['STOP VALVE Ø1/2"']),
                ((xf + 25.2, ys + 23), ['ที่ดักกลิ่น Ø1 1/2"']),
                ((xc + 0.8, ys + 12), ["ท่อประปา"]),
                ((ox + 40, oy + 7.7), ['ท่อน้ำทิ้ง Ø2"'])], ox + 70)
    _box_title(sh, ox + 40, oy - 6, "อ่างล้างหน้า ( LAV )")


def _det_wc(sh, ox, oy):
    """ส้วมชนิดถังน้ำล้าง (FLUSH TANK): the wall on the right, the bowl and
    the tank in front of it, the soil down through the slab and its long
    bend, the vent up the wall, the cold water to the stop valve."""
    ys = oy + 26
    xa, xb = ox + 60, ox + 65
    _slab(sh, ox - 6, ox + 72, ys, 7.0, label=False)
    xf = xa                                                  # the wall's face (to the left)
    xs = xf - 20                                             # the soil, under the bowl's outlet
    _pipe(sh, [(xs, ys + 2), (xs, oy + 6), (ox + 72, oy + 6)], 4.4, r=6.0, sockets=[((xs, ys - 9), True)])
    xv = xf - 3.0
    _pipe(sh, [(xv, oy + 6), (xv, oy + 96)], 2.2, 0.35)                 # the vent, off the soil's run
    sh.line((xv - 2.2, oy + 96), (xv + 2.2, oy + 96), "pipe", 0.6)
    xc = xf - 7.0
    _pipe(sh, [(xc, ys - 7), (xc, ys + 58)], 1.6, 0.35)
    sh.line((xc - 1.3, ys + 58), (xc + 1.3, ys + 58), "pipe", 0.7)
    _pipe(sh, [(xc, ys + 22), (xf - 12.5, ys + 22)], 1.2, 0.3)
    _gate(sh, xf - 11, ys + 22)
    # the tank and the bowl, in front of the wall's face
    tank = [(xf - 15, ys + 30), (xf, ys + 30), (xf, ys + 50), (xf - 15, ys + 50)]
    bowl = [(xf - 15, ys + 30), (xf - 40, ys + 30), (xf - 40, ys + 27), (xf - 34, ys + 20), (xf - 30, ys + 12),
            (xf - 30, ys), (xf - 16, ys), (xf - 16, ys + 12), (xf - 15, ys + 30)]
    for poly in (tank, bowl):
        sh.fill(poly, "mask", 0.0)
        sh.poly(poly, "fixture", 0.5)
    sh.rect(xf - 41, ys + 30, xf - 14, ys + 32, "fixture", 0.35)       # the seat
    _wall_on_slab(sh, xa, xb, ys, oy + 98)
    _floor_mark(sh, ox + 2, ys)
    _notes(sh, [((xv - 1.1, oy + 84), ['ท่อระบายอากาศ Ø2"']),
                ((xc - 0.8, ys + 57), ["ปลั๊กอุดปลายท่อ (AIR CHAMBER 0.30 ม.)"]),
                ((xf - 12.8, ys + 22.4), ['STOP VALVE Ø1/2"']),
                ((xc - 0.8, ys + 6), ["ท่อประปา"]),
                ((xs - 2.2, ys - 14), ['ท่อโสโครก Ø4"']),
                ((ox + 46, oy + 8.2), ['ข้องอยาว 90° ลงท่อโสโครก'])], ox - 10, right=False)
    _box_title(sh, ox + 34, oy - 6, "ส้วมชนิดถังน้ำล้าง ( FLUSH TANK )")


def _det_sh(sh, ox, oy):
    """ฝักบัวอาบน้ำ (SH): the cold water up the wall's face to the mixing
    valve, the arm and the head, the air chamber at the top."""
    ys = oy + 22
    xa, xb = ox + 4, ox + 9
    _slab(sh, ox - 8, ox + 44, ys, 7.0, label=False)
    xc = xb + 3.0
    _pipe(sh, [(xc, ys - 7), (xc, ys + 66)], 1.6, 0.35)
    sh.line((xc - 1.3, ys + 66), (xc + 1.3, ys + 66), "pipe", 0.7)
    _pipe(sh, [(xc, ys + 56), (xc + 10, ys + 58), (xc + 13, ys + 56)], 1.2, 0.3, r=1.5)
    head = [(xc + 11, ys + 56), (xc + 16, ys + 54), (xc + 12, ys + 52)]
    sh.fill(head, "mask", 0.0)
    sh.poly(head, "fixture", 0.45)
    sh.rect(xc + 1.0, ys + 27, xc + 5.0, ys + 33, "fixture", 0.45)    # the mixing valve
    sh.line((xc + 5.0, ys + 30), (xc + 9.0, ys + 30), "fixture", 0.45)
    _wall_on_slab(sh, xa, xb, ys, oy + 98)
    _floor_mark(sh, ox + 30, ys)
    _notes(sh, [((xc + 0.8, ys + 65), ["AIR CHAMBER 0.30 ม."]), ((xc + 15, ys + 54), ["หัวฝักบัว"]),
                ((xc + 9.0, ys + 30), ["วาล์วผสม / ก๊อกฝักบัว"]), ((xc + 0.8, ys + 10), ["ท่อประปา Ø1/2\""])], ox + 52)
    _box_title(sh, ox + 34, oy - 6, "ฝักบัวอาบน้ำ ( SH )")


def _det_rfd(sh, ox, oy):
    """ช่องระบายน้ำฝน (RFD): the drain set in the roof slab, the pipe down
    and its bend, continuous."""
    ys = oy + 54
    _slab(sh, ox - 6, ox + 66, ys, 8.0, label=False)
    cx = ox + 26
    _pipe(sh, [(cx, ys - 6), (cx, oy + 8), (ox + 66, oy + 8)], 6.0, r=8.0, sockets=[((cx, ys - 12), True)])
    body = [(cx - 7, ys + 0.6), (cx + 7, ys + 0.6), (cx + 6, ys - 6), (cx - 6, ys - 6)]
    sh.fill(body, "mask", 0.0)
    sh.poly(body, "pipe", 0.45)
    sh.rect(cx - 8, ys, cx + 8, ys + 1.6, "pipe", 0.5)
    _floor_mark(sh, ox - 2, ys + 0.2, "ระดับผิวพื้นหลังคา")
    _notes(sh, [((cx + 8, ys + 1), ["ตะแกรงรูระบายน้ำฝนแบบเรียบ (RFD)"]),
                ((cx + 6.5, ys - 4), ["ฝังในพื้น คสล. ยาแนวกันซึม"]),
                ((cx + 3, oy + 30), ['ท่อน้ำฝน RL Ø3"']), ((ox + 52, oy + 11), ["ข้องอยาว 90° ลงบ่อพัก"])], ox + 74)
    _box_title(sh, ox + 34, oy - 6, "แบบขยายช่องระบายน้ำฝน ( RFD )")


def _det_fd(sh, ox, oy, fco=False):
    """FD / FCO: the cover in plan, then in section: the body in the slab,
    the pipe down — through a P-trap (FD) or a long bend (FCO) — and on,
    one continuous pipe, held by its hanger."""
    cx = ox + 26
    cy = oy + 96
    sh.circle((cx, cy), 9.0, "pipe", 0.45)
    if fco:
        sh.circle((cx, cy), 7.0, "pipe", 0.3)
        for i in range(-6, 7, 2):
            h = math.sqrt(max(49 - i * i, 0))
            sh.line((cx + i, cy - h), (cx + i, cy + h), "hatch", 0.15)
    else:
        for r in (2.5, 5.0, 7.5):
            sh.circle((cx, cy), r, "pipe", 0.2)
        for a in range(0, 360, 30):
            ca, sa = math.cos(math.radians(a)), math.sin(math.radians(a))
            sh.line((cx + 2.5 * ca, cy + 2.5 * sa), (cx + 7.5 * ca, cy + 7.5 * sa), "pipe", 0.15)
    ys = oy + 70
    _slab(sh, ox - 8, ox + 76, ys, 8.0, label=False)
    if fco:
        path = [(cx, ys - 7), (cx, oy + 36), (ox + 76, oy + 36)]
        _pipe(sh, path, 4.0, r=9.0, sockets=[((cx, ys - 14), True), ((ox + 62, oy + 36), False)])
    else:
        path = [(cx, ys - 7), (cx, oy + 40), (cx + 9, oy + 40), (cx + 9, oy + 50), (ox + 76, oy + 50)]
        _pipe(sh, path, 4.0, r=4.0, sockets=[((ox + 62, oy + 50), False)])
    body = [(cx - 7, ys + 0.5), (cx + 7, ys + 0.5), (cx + 7, ys - 5), (cx + 3, ys - 8), (cx - 3, ys - 8), (cx - 7, ys - 5)]
    sh.fill(body, "mask", 0.0)
    sh.poly(body, "pipe", 0.45)
    sh.line((cx - 7, ys - 0.8), (cx + 7, ys - 0.8), "pipe", 0.6)
    yh = oy + (36 if fco else 50) + 2.4
    sh.line((ox + 52, ys - 8), (ox + 52, yh), "pipe", 0.3)                        # the hanger
    sh.line((ox + 49.5, yh), (ox + 54.5, yh), "pipe", 0.4)
    _floor_mark(sh, ox + 56, ys)
    notes = [((cx + 9, cy), ["ฝาสแตนเลส / ทองเหลือง" if fco else "ตะแกรงทองเหลือง (BRASS OR BRONZE)"]),
             ((ox + 52, yh + 8), ["เหล็กแขวนท่อ"]),
             ((ox + 72, oy + (36 if fco else 50) + 2.0), ["ชนิดของท่อดูในรายการประกอบแบบ"])]
    if fco:
        notes.append(((cx + 4, oy + 42), ["ข้องอ 90° รัศมีกว้าง"]))
    else:
        notes += [((cx + 2, oy + 58), ["ช่องระบายน้ำทิ้ง"]), ((cx + 11, oy + 44), ["ที่ดักกลิ่นรูป P"])]
    _notes(sh, notes, ox + 84)
    _box_title(sh, ox + 40, oy + 12, "ช่องสำหรับทำความสะอาดท่อที่พื้น ( FCO )" if fco else "ช่องระบายน้ำทิ้งที่พื้น ( FD )")


def _det_co(sh, ox, oy):
    """CO: the stack down through the slab and into the run by a 45° wye;
    the run's end plugged as the cleanout; the hangers. All continuous."""
    ys = oy + 84
    _slab(sh, ox - 8, ox + 76, ys, 8.0, label=False)
    xs = ox + 26
    yr = oy + 36
    _pipe(sh, [(xs, ys + 14), (xs, yr + 16), (xs + 12, yr + 3)], 4.0, r=4.0, sockets=[((xs, ys - 14), True)])
    _pipe(sh, [(ox - 4, yr), (ox + 76, yr)], 4.0, sockets=[((ox + 8, yr), False), ((ox + 62, yr), False)])
    sh.rect(ox - 6, yr - 3, ox - 4, yr + 3, "pipe", 0.6)                          # the plug
    for xh in (ox + 16, ox + 56):
        sh.line((xh, ys - 8), (xh, yr + 2.4), "pipe", 0.3)
        sh.line((xh - 2.5, yr + 2.4), (xh + 2.5, yr + 2.4), "pipe", 0.4)
    _floor_mark(sh, ox + 56, ys)
    _notes(sh, [((xs + 2, ys + 10), ["ท่อแนวดิ่ง"]), ((ox + 56, ys - 20), ["เหล็กแขวนท่อ"]),
                ((xs + 9, yr + 6), ["ข้อต่อสามทางวาย (Y) 45°"]), ((ox - 4, yr - 3), ["ช่องสำหรับทำความสะอาด อุดด้วยปลั๊ก"])],
           ox + 84)
    _box_title(sh, ox + 40, oy + 12, "ช่องสำหรับทำความสะอาดท่อใต้พื้น ( CO )")


def _det_avc(sh, ox, oy):
    """AVC: the vent's wall cap — the front, and the section through the wall."""
    cx, cy = ox + 16, oy + 62
    sh.arc((cx, cy), 12.0, 180, 360, "pipe", 0.45)
    for r in (3.0, 6.0, 9.0):
        sh.arc((cx, cy), r, 180, 360, "pipe", 0.2)
    sh.line((cx - 12, cy), (cx + 12, cy), "pipe", 0.45)
    xa, xb = ox + 46, ox + 52
    _pipe(sh, [(xa - 1, cy), (ox + 76, cy)], 5.0)
    _wall_on_slab(sh, xa, xb, oy + 38, oy + 88)
    sh.fill([(xa - 4, cy - 10), (xa, cy - 10), (xa, cy + 10), (xa - 4, cy + 10)], "mask", 0.0)
    sh.rect(xa - 4, cy - 10, xa, cy + 10, "pipe", 0.45)                            # the louvred cap
    for i in range(5):
        sh.line((xa - 4, cy - 8 + i * 4), (xa - 7, cy - 10 + i * 4), "pipe", 0.3)
    _notes(sh, [((xa - 4, cy + 8), ["ฝาครอบกันแมลง สแตนเลส"]), ((ox + 70, cy + 2.5), ['ท่ออากาศ Ø2"V']),
                ((xa + 3, oy + 80), ["ผนัง"])], ox + 84)
    sh.text((cx, cy - 16), "รูปด้าน", 2.4, "center")
    sh.text((xa + 3, oy + 32), "รูปตัด", 2.4, "center")
    _box_title(sh, ox + 40, oy + 12, "แบบขยายฝาเปิดท่อระบายอากาศ ( AVC )")


def sn_fixture_details(sh, E):
    """SN-08 «แบบขยายการติดตั้งท่อ (แผ่นที่ 1)»: LAV, FLUSH TANK, SH, RFD."""
    x0, y0, x1, y1 = D.drawing_area()
    W = x1 - x0
    _det_lav(sh, x0 + 10, y1 - 112)
    _det_wc(sh, x0 + W * 0.66, y1 - 112)
    _det_sh(sh, x0 + 10, y0 + 18)
    _det_rfd(sh, x0 + W * 0.36, y0 + 18)
    D.notes_block(sh, x0 + W * 0.74, y0 + 96, "หมายเหตุ", [
        "1. ระดับติดตั้งสุขภัณฑ์และอุปกรณ์ ให้ตรวจสอบกับแบบสถาปัตยกรรมและคำแนะนำของผู้ผลิต",
        "2. ทุกจุดจ่ายน้ำติดตั้ง STOP VALVE และท่อกันกระแทก (AIR CHAMBER) ยาวไม่น้อยกว่า 0.30 ม.",
        "3. ท่อระบายน้ำทุกจุดต้องมีที่ดักกลิ่น และต่อท่ออากาศตามแบบ"], 2.6, 38)


def sn_drain_details(sh, E):
    """SN-09 «แบบขยายการติดตั้งท่อ (แผ่นที่ 2)»: FD, FCO, CO, AVC."""
    x0, y0, x1, y1 = D.drawing_area()
    W = x1 - x0
    _det_fd(sh, x0 + 10, y1 - 118)
    _det_fd(sh, x0 + W * 0.52, y1 - 118, fco=True)
    _det_co(sh, x0 + 10, y0 + 4)
    _det_avc(sh, x0 + W * 0.52, y0 + 4)
