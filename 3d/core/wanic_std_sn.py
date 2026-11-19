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
