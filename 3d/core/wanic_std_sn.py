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
    for (p, lines), ty in zip(items, ys):
        sh.line((col_x - 1.2, ty), (p[0] + (1.6 if p[0] < col_x else -1.6), p[1]), "text", 0.18)
        _ahead(sh, p, (col_x, ty), 2.0, "text")
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
