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


def _pipe_tag(sh, p, text, angle=0.0, size=2.3):
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
    sh.text((x0 + 7, Y(gl) - 3.2), f"ระดับดินเดิม {gl:+.2f}", 2.3)
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
    sh.text((xv + 3, Y(n * H + 0.9) - 0.8), "VTR (ท่ออากาศผ่านหลังคา)", 2.3)
    for k in bfl:                                            # the branches of each floor's bathrooms
        z = k * H
        nb = sum(1 for kk, _r in baths if kk == k) or 1
        _arrow(sh, (xs - 30, Y(z) + 6), (xs, Y(z) + 6), 0.55)
        sh.text((xs - 30, Y(z) + 7.4), f'Ø4"S (WC × {nb})', 2.3)
        _arrow(sh, (xw + 26, Y(z) + 3), (xw, Y(z) + 3), 0.4)
        sh.text((xw + 4, Y(z) + 4.2), 'Ø2"W (FD, LAV)', 2.2)
        _dashed(sh, (xv - 22, Y(z) + 14), (xv, Y(z) + 14), 0.3)
        sh.text((xv - 22, Y(z) + 15.2), 'Ø2"V', 2.3)
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
    sh.text((tx - 20, ty + th - 5.6), 'Ø4"SW', 2.3)
    sh.text((tx - 1, ty + th - 11.6), "ต่อลงบ่อพักท่อระบายน้ำ", 2.3, "right")
    st = des["septic"]
    notes = [f"ถังบำบัดน้ำเสียสำเร็จรูป ST ขนาด {st['litres']:,} ลิตร"
             + (f" × {st['count']} ถัง" if st["count"] > 1 else "") + f" (ผู้ใช้ {users} คน)",
             f"ชนิดไร้อากาศมีตัวกลาง มอก. 2550 ขนาด {st['size']} ม.",
             "วางบนทรายบดอัดแน่น 0.10 ม. และคอนกรีตหยาบ 0.05 ม.",
             "การติดตั้งให้เป็นไปตามมาตรฐานผู้ผลิต"]
    for j, t in enumerate(notes):
        sh.text((tx - 4, ty - 7 - j * 4.4), t, 2.4)
    # the kitchen through the grease trap
    if des.get("kitchens"):
        gx = xs + 40
        sh.rect(gx, Y(zb) - 4, gx + 9, Y(zb) + 2, "text", 0.4)
        sh.text((gx + 4.5, Y(zb) - 2.6), "GT", 2.0, "center", "text", True)
        _arrow(sh, (gx + 26, Y(-0.05)), (gx + 9, Y(zb) + 1), 0.4)
        sh.text((gx + 12, Y(-0.05) + 1.2), 'Ø2"K จากซิงก์ครัว', 2.2)
        sh.line((gx, Y(zb) - 1), (xw, Y(zb) - 1), "text", 0.4)
        sh.text((gx - 1, Y(zb) - 7.6), f"บ่อดักไขมัน GT {des['grease']['litres']} ลิตร", 2.2, "right")
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
        sh.text((xr - 16, Y(z) + 1.2), "→ ห้องน้ำ", 2.2, "right")
    xt = xr + 60                                             # the tank
    _dashdot(sh, (xr, yw), (xt - 26, yw), 0.35)
    sh.text(((xr + xt - 26) / 2, yw + 1.0), 'Ø3/4"CW', 2.3, "center")
    sh.rect(xt - 30, yw - 2.4, xt - 22, yw + 2.4, "text", 0.35)              # the booster pump
    sh.text((xt - 26, yw - 0.9), "BP", 2.0, "center", "text", True)
    _dashdot(sh, (xt - 22, yw), (xt - 6, yw), 0.35)
    # the by-pass round the pump, with its check valve
    yb2 = yw + 9
    _dashdot(sh, (xr + 20, yw), (xr + 20, yb2), 0.3)
    _dashdot(sh, (xr + 20, yb2), (xt - 10, yb2), 0.3)
    _dashdot(sh, (xt - 10, yb2), (xt - 10, yw), 0.3)
    _gate(sh, (xr + xt - 10) / 2 + 6, yb2)
    sh.line(((xr + xt - 10) / 2 + 5.4, yb2 - 1.2), ((xr + xt - 10) / 2 + 6.6, yb2 + 1.2), "text", 0.3)
    sh.text(((xr + xt) / 2 - 2, yb2 + 1.4), 'Ø3/4" BY PASS', 2.1, "center")
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
    sh.text((x1 - 4, yw + 1.4), "จากท่อประปา", 2.2, "right")
    def note(p, q, lines):
        sh.circle(p, 0.45, "text", 0.2)
        sh.line(p, q, "text", 0.15)
        w = max(len(t) for t in lines) * 1.25
        sh.line(q, (q[0] + w, q[1]), "text", 0.15)
        for j, t in enumerate(lines):
            sh.text((q[0] + 1, q[1] + 0.9 - j * 4.4), t, 2.3)
    note((xt + 8, yw - 3 + th2 * 0.7), (xt + 14, yw - 3 + th2 + 22),
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
    sh.rect(c[0] - s, c[1] - s, c[0] + s, c[1] + s, "pipe", 0.4)
    sh.line((c[0] - s, c[1] - s), (c[0] + s, c[1] + s), "pipe", 0.25)
    sh.line((c[0] - s, c[1] + s), (c[0] + s, c[1] - s), "pipe", 0.25)


def _flow(sh, a, b, w=0.5):
    """The perimeter drain from a to b (paper), dashed, with an arrow midway."""
    sh.line(a, b, "pipe", w, True)
    L = math.hypot(b[0] - a[0], b[1] - a[1]) or 1.0
    ux, uy = (b[0] - a[0]) / L, (b[1] - a[1]) / L
    m = ((a[0] + b[0]) / 2 + ux * 1.5, (a[1] + b[1]) / 2 + uy * 1.5)
    sh.fill([m, (m[0] - ux * 2.4 - uy * 1.0, m[1] - uy * 2.4 + ux * 1.0),
             (m[0] - ux * 2.4 + uy * 1.0, m[1] - uy * 2.4 - ux * 1.0)], "pipe", 0.0)


def _tank(sh, c, r, hatch=True):
    sh.circle(c, r, "pipe", 0.45)
    if hatch:
        i = -r
        while i < r:
            h = math.sqrt(max(r * r - i * i, 0.0))
            a = (c[0] + i - h * 0.0, c[1])
            sh.line((c[0] + i * 0.7071 - h * 0.7071, c[1] + i * 0.7071 + h * 0.7071 - 2 * i * 0.7071),
                    (c[0] + i * 0.7071 + h * 0.7071, c[1] - i * 0.7071 + h * 0.7071 - 2 * h * 0.7071 + 0.0),
                    "hatch", 0.12)
            i += 1.2
    sh.circle(c, r * 0.22, "pipe", 0.25)


def _outline(E, k):
    rms = [s["room"] for s in E["slabs"] if s["floor"] == k] or [s["room"] for s in E["slabs"]]
    return (min(r["x"] for r in rms), min(r["y"] for r in rms),
            max(r["x"] + r["w"] for r in rms), max(r["y"] + r["d"] for r in rms))


def sn_plan_std(sh, E, k):
    """แปลนระบบสุขาภิบาลชั้น k+1 as the standard (SN-05, SN-06). The ground
    floor: the drain round the building (concrete Ø0.20 ม. ลาด 1:200, catch
    basins at the corners and no more than 12 m apart, the flow, the start
    0.60 m deep, the outlet), the septic tank by the bathroom and the soil
    pipes to it, the grease trap by the kitchen, the water from the meter to
    the storage tank and the pump, a branch with a valve to each wet room,
    the roof's downpipes; the notes on the tanks. Upper floors: the stacks
    and risers of each bathroom."""
    from core import wanic_sanitary as SAN
    from core import wanic_std_sheets as STD
    v, sc = D.plan_view(sh, E, pad=4.6)
    t = float(E["settings"].get("wall_t") or 0.1)
    D.draw_grid(sh, v, E, ext=3.7, at=(2.2, 2.9))
    D.draw_walls(sh, v, E, k, t, None, swings=True, tags=False)
    D.draw_stairs(sh, v, E, k)
    D.draw_fixtures(sh, v, E, k, labels=False)
    for sl in (s for s in E["slabs"] if s["floor"] == k):          # the rooms and their levels
        rm = sl["room"]
        p = v(rm["x"] + rm["w"] / 2, rm["y"] + rm["d"] / 2)
        z = float(sl.get("z", 0.0)) - (0.05 if (rm.get("name") or "").startswith("ห้องน้ำ") else 0.0)
        sh.text((p[0], p[1] + 1.4), rm.get("name") or "ห้อง", 2.6, "center", "text", True)
        sh.text((p[0], p[1] - 2.6), "±0.00" if abs(z) < 0.005 else f"{z:+.2f}", 2.3, "center")
    bx0, by0, bx1, by1 = _outline(E, k)
    baths = [rm for kk, rm in D.bathrooms(E) if kk == k]
    fixtures = [f["fx"] for f in E["fixtures"] if f["floor"] == k]
    x0, y0, x1, y1 = D.drawing_area()
    des = SAN.design(E)
    notes = []
    if k == 0:
        o = 1.6                                                     # the drain 1.60 m outside the walls
        X0, Y0, X1, Y1 = bx0 - o, by0 - o, bx1 + o, by1 + o
        corners = [(X0, Y1), (X1, Y1), (X1, Y0), (X0, Y0)]
        # catch basins: the corners and along each side, no more than 12 m apart
        cbs = []
        for a, b in zip(corners, corners[1:] + corners[:1]):
            L = math.hypot(b[0] - a[0], b[1] - a[1])
            nseg = max(1, math.ceil(L / 12.0))
            for i in range(nseg):
                cbs.append((a[0] + (b[0] - a[0]) * i / nseg, a[1] + (b[1] - a[1]) * i / nseg))
        out = (X1, Y0)                                              # the outlet: the front-right corner
        start = (X0, Y1)                                            # the start (the far corner), 0.60 m deep
        for path in ([(X0, Y1), (X1, Y1), (X1, Y0)], [(X0, Y1), (X0, Y0), (X1, Y0)]):
            for a, b in zip(path, path[1:]):
                L = math.hypot(b[0] - a[0], b[1] - a[1])
                nseg = max(1, math.ceil(L / 12.0))
                for i in range(nseg):
                    pa = (a[0] + (b[0] - a[0]) * i / nseg, a[1] + (b[1] - a[1]) * i / nseg)
                    pb = (a[0] + (b[0] - a[0]) * (i + 1) / nseg, a[1] + (b[1] - a[1]) * (i + 1) / nseg)
                    da, db = v(*pa), v(*pb)
                    L2 = math.hypot(db[0] - da[0], db[1] - da[1]) or 1
                    ux, uy = (db[0] - da[0]) / L2, (db[1] - da[1]) / L2
                    _flow(sh, (da[0] + ux * 2.4, da[1] + uy * 2.4), (db[0] - ux * 2.4, db[1] - uy * 2.4))
        for c in cbs:
            _cb(sh, v(*c))
        po = v(*out)
        _flow(sh, (po[0], po[1] - 2.4), (po[0], po[1] - 16))
        notes.append((v((X0 + X1) / 2, Y1), "ท่อคอนกรีตท้องตลาด Ø0.20 ม. ลาด 1 : 200", "up"))
        notes.append((v(*start), "จุดต้นท่อลึก 0.60 ม.", "upl"))
        notes.append(((po[0], po[1] - 12), "ต่อลงบ่อพักท่อระบายน้ำสาธารณะ", "downr"))
        notes.append((v(X1, (Y0 + Y1) / 2), "บ่อพักท่อระบายน้ำ 0.40 × 0.40 ม. ฝา คสล.", "right"))
        # the septic tank outside the (first) bathroom, the grease trap outside the kitchen
        def outside(rm, gap=0.55):
            cx, cy = rm["x"] + rm["w"] / 2, rm["y"] + rm["d"] / 2
            ds = [(cx - bx0, (bx0 - gap, cy)), (bx1 - cx, (bx1 + gap, cy)),
                  (cy - by0, (cx, by0 - gap)), (by1 - cy, (cx, by1 + gap))]
            return min(ds)[1]
        st = des["septic"]
        r_st = 0.55
        if baths:
            ct = outside(baths[0], r_st + 0.12)
            _tank(sh, v(*ct), v.len(r_st))
            # the soil pipes: each WC to the tank (orthogonal), the waste (FD, LAV) too
            for fx in fixtures:
                typ = fx.get("type", "")
                p = (float(fx["x"]), float(fx["y"]))
                soil = typ.startswith("WC") or typ == "UR"
                if not (soil or typ.startswith(("LV", "FD", "SH", "BT"))):
                    continue
                q = (p[0], ct[1]) if abs(ct[0] - p[0]) > abs(ct[1] - p[1]) else (ct[0], p[1])
                sh.poly([v(*p), v(*q), v(*ct)], "pipe", 0.6 if soil else 0.35, closed=False)
                lp = v(*p)
                sh.text((lp[0] + 1.4, lp[1] - 3.2), 'S Ø4"' if soil else 'W Ø2"', 1.9, "left", "pipe")
            fdp = v(baths[0]["x"] + baths[0]["w"] * 0.5, baths[0]["y"] + baths[0]["d"] * 0.28)
            sh.rect(fdp[0] - 1.1, fdp[1] - 1.1, fdp[0] + 1.1, fdp[1] + 1.1, "pipe", 0.3)
            sh.text((fdp[0] + 1.8, fdp[1] - 3.4), 'FD Ø2"', 2.0)
            cb = min(cbs, key=lambda c: math.hypot(c[0] - ct[0], c[1] - ct[1]))
            sh.line(v(*ct), v(*cb), "pipe", 0.35)                    # the treated water to the drain
            notes.append((v(*ct), f"ถังบำบัดน้ำเสียสำเร็จรูป ST {st['litres']:,} ลิตร", "right"))
        kit = [s["room"] for s in E["slabs"] if s["floor"] == k and "ครัว" in (s["room"].get("name") or "")]
        if kit:
            cg = outside(kit[0], 0.45)
            _tank(sh, v(*cg), v.len(0.30), hatch=False)
            sinks = [fx for fx in fixtures if fx.get("type", "").startswith("SK")]
            src = (float(sinks[0]["x"]), float(sinks[0]["y"])) if sinks else \
                (kit[0]["x"] + kit[0]["w"] / 2, kit[0]["y"] + kit[0]["d"] / 2)
            q = (src[0], cg[1]) if abs(cg[0] - src[0]) > abs(cg[1] - src[1]) else (cg[0], src[1])
            sh.poly([v(*src), v(*q), v(*cg)], "pipe", 0.35, closed=False)
            cb = min(cbs, key=lambda c: math.hypot(c[0] - cg[0], c[1] - cg[1]))
            sh.line(v(*cg), v(*cb), "pipe", 0.35)
            notes.append((v(*cg), f"ถังดักไขมันสำเร็จรูป GT {des['grease']['litres']} ลิตร", "right"))
        # the water: the meter at the front, the storage tank and the pump, the branches
        mt = (bx0 + 1.4, Y0 - 0.9)                                  # the meter at the front, left
        pm, pt = v(*mt), v(bx0 + 1.4, by0 - 0.8)
        sh.circle(pm, 1.8, "pipe", 0.3)
        sh.text((pm[0], pm[1] - 0.8), "M", 1.7, "center", "pipe", True)
        notes.append((pm, 'ชุดมาตรวัดน้ำ Ø1/2" (ผู้รับจ้างเป็นผู้ติดตั้ง)', "downl"))
        _tank(sh, pt, v.len(0.45), hatch=False)
        sh.rect(pt[0] - 9.5, pt[1] - 1.8, pt[0] - 5.5, pt[1] + 1.8, "pipe", 0.3)
        sh.text((pt[0] - 7.5, pt[1] - 0.8), "BP", 1.6, "center", "pipe", True)
        notes.append((pt, "ถังเก็บน้ำสำเร็จรูป + เครื่องสูบน้ำ (BP)", "left"))
        _dashdot(sh, (pm[0], pm[1] + 1.8), (pm[0], pt[1] - v.len(0.45)), 0.3)
        wet = baths + kit
        ym = v(0, by0 - 0.35)[1]                                    # the CW main along the front
        _dashdot(sh, (pt[0] - 5.5, pt[1]), (pt[0] - v.len(0.45), pt[1]), 0.3)
        xs_ = [v(rm["x"] + rm["w"] * 0.25, 0)[0] for rm in wet]
        if xs_:
            _dashdot(sh, (pt[0] + v.len(0.45), pt[1]), (pt[0] + 6, pt[1]), 0.3)
            _dashdot(sh, (pt[0] + 6, pt[1]), (pt[0] + 6, ym), 0.3)
            _dashdot(sh, (pt[0] + 6, ym), (max(xs_), ym), 0.3)
            for rm, xq in zip(wet, xs_):
                yt = v(0, rm["y"] + 0.4)[1]
                _dashdot(sh, (xq, ym), (xq, yt), 0.3)
                _gate(sh, xq, (ym + v(0, by0)[1]) / 2, vertical=True)
                sh.text((xq + 1.6, yt - 3.6), 'Ø1/2"CW', 2.0)
            sh.text(((pt[0] + 6 + max(xs_)) / 2, ym + 1.0), 'Ø3/4"CW', 2.2, "center")
        # the roof's downpipes at the corners into the nearest catch basin
        if E["settings"].get("roof", "none") != "none":
            for c in ((bx0, by1), (bx1, by1), (bx0, by0)):
                pq = v(*c)
                sh.circle(pq, 1.1, "pipe", 0.3)
                sh.circle(pq, 0.3, "pipe", 0.5)
                cb = min(cbs, key=lambda q: math.hypot(q[0] - c[0], q[1] - c[1]))
                sh.line(pq, v(*cb), "pipe", 0.25)
            pq = v(bx0, by1)
            sh.text((pq[0] + 1.6, pq[1] + 1.4), 'RL Ø2 1/2"', 2.0)
        groups = (("ถังบำบัดน้ำเสีย", [f"ถังบำบัดน้ำเสียสำเร็จรูปชนิดไร้อากาศมีตัวกลาง",
                                      f"ขนาด {st['litres']:,} ลิตร" + (f" × {st['count']} ถัง" if st["count"] > 1 else "")
                                      + f" สำหรับผู้ใช้ {des['users']} คน",
                                      f"มอก. 2550 ขนาด {st['size']} ม.", "การติดตั้งให้เป็นไปตามมาตรฐานผู้ผลิต"]),
                  ("ถังดักไขมัน", [f"ถังดักไขมันสำเร็จรูป ขนาดไม่น้อยกว่า {des['grease']['litres']} ลิตร",
                                    f"ขนาดภายนอก {des['grease']['size']} ม.", "รับน้ำจากซิงก์ครัว",
                                    "ตักไขมันทุก 1–2 สัปดาห์"]))
        for i, (head, lines) in enumerate(groups):                  # the tank notes, two columns, lower right
            sw = x1 - 186 + i * 94
            y_ = y0 + 50
            sh.text((sw, y_), head, 3.2, "left", "text", True)
            sh.line((sw, y_ - 1.4), (sw + len(head) * 2.0, y_ - 1.4), "text", 0.35)
            y_ -= 7
            for ln in lines:
                sh.text((sw, y_), ln, 2.5)
                y_ -= 4.8
    else:
        # upper floors: each bathroom's soil stack and CW riser by its outer wall
        for rm in baths:
            cs = v(rm["x"] + rm["w"] - 0.25, rm["y"] + rm["d"] - 0.25)          # the outer corner, over the tank
            sh.circle(cs, 1.6, "pipe", 0.45)
            sh.circle(cs, 0.5, "pipe", 0.6)
            notes.append((cs, 'ท่อโสโครกแนวดิ่ง Ø4"SW ลงถังบำบัด · Ø2"V ขึ้นหลังคา', "right"))
            for fx in fixtures:
                if not (rm["x"] <= float(fx["x"]) <= rm["x"] + rm["w"] and rm["y"] <= float(fx["y"]) <= rm["y"] + rm["d"]):
                    continue
                typ = fx.get("type", "")
                p = v(float(fx["x"]), float(fx["y"]))
                soil = typ.startswith("WC")
                sh.poly([p, (p[0], cs[1]), cs], "pipe", 0.6 if soil else 0.35, closed=False)
                sh.text((p[0] + 1.4, p[1] - 3.2), 'S Ø4"' if soil else 'W Ø2"', 1.9, "left", "pipe")
            cw = v(rm["x"] + rm["w"] - 0.25, rm["y"] + rm["d"] - 0.60)
            sh.circle(cw, 1.0, "pipe", 0.3)
            notes.append((cw, 'ท่อประปาแนวดิ่ง Ø3/4"CW พร้อมประตูน้ำ', "right"))
    # the notes, on shelves outside the plan
    bxr = v(_outline(E, k)[2] + (1.6 if k == 0 else 0.6), 0)[0]
    used = []
    for p, text, side in notes:
        lx = v(_outline(E, k)[0] - (1.6 if k == 0 else 0.6), 0)[0] - 4
        tx = bxr + 4 if side in ("right", "upr", "downr") else (lx if side in ("left", "downl", "upl") else p[0])
        ty = p[1] + (9 if side in ("up", "upr", "upl") else -9 if side in ("downr", "downl") else 0)
        while any(abs(ty - u) < 5.2 and abs(tx - ux) < 60 for ux, u in used):
            ty -= 5.4
        used.append((tx, ty))
        sh.circle(p, 0.45, "text", 0.2)
        sh.line(p, (tx, ty), "text", 0.15)
        w = len(text) * 1.2
        if side in ("left", "downl", "upl"):
            sh.line((tx - w, ty), (tx, ty), "text", 0.15)
            sh.text((tx - 1, ty + 0.9), text, 2.3, "right")
        else:
            sh.line((tx, ty), (tx + w, ty), "text", 0.15)
            sh.text((tx + 1, ty + 0.9), text, 2.3)
    STD.caption_marks(sh, ((x0 + x1) / 2 - 60, y0 + 12), f"แปลนระบบสุขาภิบาลชั้น {k + 1}", f"1:{sc}",
                      None, None, 100.0)
