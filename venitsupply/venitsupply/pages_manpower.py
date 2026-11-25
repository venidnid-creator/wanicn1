# SPDX-License-Identifier: GPL-3.0-or-later
"""หน้าจออัตรากำลัง: โครงสร้างตามสายการบังคับบัญชา (กอง › ฝ่าย › งาน › ตำแหน่ง), มาตรฐานกำหนดตำแหน่ง,
ภาระงานรายตำแหน่ง และตารางวิเคราะห์ว่าต้องการคนเพิ่มกี่คน."""
from __future__ import annotations

import re

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QHBoxLayout, QLabel, QLineEdit,
                               QListWidget, QMessageBox, QPlainTextEdit, QSplitter, QTableWidget, QTableWidgetItem,
                               QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget)

from . import PRODUCT_TH
from . import hire as H
from . import hire_reports as HR
from . import manpower as M
from .i18n import T
from .pages_budget import GREEN, RED, _buttons
from .widgets import MUTED, FormDialog, error, fill, fit_to_screen, need_selection, px, selected_id, table

AMBER = "#B45309"


def _do(parent, fn, *a, **k):
    try:
        return fn(*a, **k)
    except Exception as exc:  # noqa: BLE001
        error(parent, exc)
        return None


def _bb(dlg, ok="บันทึก"):
    bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
    bb.button(QDialogButtonBox.Ok).setText(T(ok))
    bb.button(QDialogButtonBox.Ok).setObjectName("primary")
    bb.button(QDialogButtonBox.Cancel).setText(T("ยกเลิก"))
    bb.accepted.connect(dlg.accept)
    bb.rejected.connect(dlg.reject)
    return bb


def _short(a) -> str:
    s = a.get("short")
    if s is None:
        return ""
    return f"+{s}" if s > 0 else str(s)


# ================================================================ structure
class OrgTab(QWidget):
    """กอง › ฝ่าย › งาน (tree) + ตำแหน่งของหน่วยงานที่เลือก (กรอบ/ครอง/ว่าง/ภาระงาน/ขาด)."""

    POS_HEAD = ["ตำแหน่ง", "ระดับ", "ประเภท", "กรอบ", "มีคนครอง", "ว่าง", "ภาระงาน (คน)", "ต้องการ", "ขาด/เกิน",
                "ข้อเสนอ"]

    def __init__(self, page):
        super().__init__()
        self.p = page
        lay = QVBoxLayout(self)
        sp = QSplitter(Qt.Horizontal)
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels([T("ส่วนราชการ (สายการบังคับบัญชา)"), T("กรอบ"), T("ครอง"), T("ว่าง")])
        self.tree.itemSelectionChanged.connect(self.show_positions)
        self.tree.itemDoubleClicked.connect(lambda *_: self.edit_div())
        ll.addWidget(self.tree, 1)
        row, _ = _buttons(("เพิ่มกอง", self.add_top, True), ("เพิ่มหน่วยงานย่อย", self.add_sub),
                          ("แก้ไข", self.edit_div), ("ลบ", self.del_div))
        ll.addLayout(row)
        sp.addWidget(left)
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        self.title = QLabel(T("ตำแหน่ง"))
        self.title.setObjectName("section")
        rl.addWidget(self.title)
        self.route = QLabel()
        self.route.setWordWrap(True)
        self.route.setTextFormat(Qt.RichText)
        rl.addWidget(self.route)
        self.pos = table(self.POS_HEAD, stretch=9)
        hh = self.pos.horizontalHeader()
        hh.setSectionResizeMode(0, hh.ResizeMode.Interactive)
        hh.resizeSection(0, px(250))
        self.pos.doubleClicked.connect(lambda *_: self.workload())
        rl.addWidget(self.pos, 1)
        self.sum = QLabel()
        self.sum.setWordWrap(True)
        self.sum.setTextFormat(Qt.RichText)
        rl.addWidget(self.sum)
        row, _ = _buttons(("เพิ่มตำแหน่ง", self.add_pos), ("แก้ไขตำแหน่ง", self.edit_pos), ("ลบตำแหน่ง", self.del_pos),
                          (None, None), ("ภาระงาน (ปริมาณงาน)…", self.workload, True),
                          ("พิมพ์เอกสาร 4/5", self.print_pos), ("สร้างงานจ้างเหมาจากตำแหน่งนี้", self.make_job))
        rl.addLayout(row)
        sp.addWidget(right)
        sp.setSizes([px(470), px(820)])
        lay.addWidget(sp, 1)
        row, _ = _buttons((None, None), ("กำหนดกองให้รายการงบประมาณ", self.assign),
                          ("โหลดโครงสร้าง อบต.ไม้ขาว (แผนอัตรากำลัง 2570–2572)", self.seed))
        lay.addLayout(row)

    # ---- tree
    def refresh(self):
        s = self.p.store
        cur = self.cur()
        self.tree.clear()
        bold = QFont()
        bold.setBold(True)

        def add(parent, d):
            a = s.unit_analysis(d["id"])
            it = QTreeWidgetItem([d["name"], str(a["frame"]), str(a["occupied"]), str(a["vacant"])])
            it.setData(0, Qt.UserRole, d["id"])
            for c in (1, 2, 3):
                it.setTextAlignment(c, Qt.AlignCenter)
            if a["vacant"]:
                it.setForeground(3, QColor(AMBER))
            if d["kind"] == "กอง":
                it.setFont(0, bold)
            (parent.addChild(it) if parent else self.tree.addTopLevelItem(it))
            for c in s.divisions(d["id"]):
                add(it, c)
            if d["id"] == cur:
                self.tree.setCurrentItem(it)
        for d in s.divisions():
            add(None, d)
        self.tree.expandToDepth(1)
        self.tree.setColumnWidth(0, px(330))
        for c in (1, 2, 3):
            self.tree.setColumnWidth(c, px(52))
        if self.tree.currentItem() is None and self.tree.topLevelItemCount():
            self.tree.setCurrentItem(self.tree.topLevelItem(0))
        self.show_positions()

    def cur(self):
        it = self.tree.currentItem()
        return it.data(0, Qt.UserRole) if it else None

    def pid(self):
        return selected_id(self.pos)

    def show_positions(self):
        s = self.p.store
        did = self.cur()
        rows = s.positions(did) if did else []
        data = [s.position_analysis(p["id"]) for p in rows]
        fill(self.pos, [[a["position"]["title"], a["position"]["level"] or "", a["position"]["kind"] or "",
                         a["frame"], a["occupied"], a["vacant"], f"{a['fte']:.2f}" if a["has_load"] else "",
                         a["need"] if a["need"] is not None else "", _short(a), HR.proposal_text(a)] for a in data],
             ids=[p["id"] for p in rows])
        for r, a in enumerate(data):
            if a["vacant"]:
                self.pos.item(r, 5).setForeground(QColor(AMBER))
            if a["short"] is not None:
                self.pos.item(r, 8).setForeground(QColor(RED if a["short"] > 0 else GREEN))
            if a["position"]["is_head"]:
                f = self.pos.item(r, 0).font()
                f.setBold(True)
                self.pos.item(r, 0).setFont(f)
        if not did:
            self.title.setText(T("ตำแหน่ง — เลือกหน่วยงานทางซ้าย"))
            self.route.setText("")
            self.sum.setText("")
            return
        d = s.division(did)
        self.title.setText(" › ".join(u["name"] for u in reversed(s.chain(did))))
        steps = [f"{(r[1] + ' ') if r[1] else ''}<i>{r[2]}</i>" for r in s.route(did)]
        self.route.setText(f"<span style='color:{MUTED}'>{T('เส้นทางเสนอเอกสาร')}:</span> " + " → ".join(steps))
        a = s.unit_analysis(did)
        fy = self.p.fy.value()
        top = s.top_division(did)
        hb = s.division_budget(fy, top["id"], hire_only=True)
        self.sum.setText(
            f"{T('รวมหน่วยงานนี้')} ({d['kind']}): {T('กรอบ')} <b>{a['frame']}</b> · {T('มีคนครอง')} <b>{a['occupied']}</b> · "
            f"{T('ว่าง')} <b style='color:{AMBER}'>{a['vacant']}</b> · {T('วิเคราะห์ภาระงานแล้ว')} {a['analysed']}/"
            f"{a['positions']} {T('ตำแหน่ง')}"
            + (f" · {T('ภาระงาน')} {a['fte']:.2f} {T('คน')} · <b style='color:{RED}'>{T('ขาด')} {a['short']}</b>"
               if a["analysed"] else "")
            + f"<br>{T('งบจ้างเหมาบุคคลของ')}{top['name']} {T('ปี')} {fy}: {hb['budget']:,.2f} "
            f"({T('คงเหลือ')} {hb['available']:,.2f})")

    # ---- divisions
    def _div_dialog(self, values):
        s = self.p.store
        parents = [(None, "— (เป็นกอง/ส่วนราชการ)")] + [(d["id"], d["name"]) for d in s.divisions(all_levels=True)
                                                       if d["id"] != values.get("id")]
        f = [("kind", "ประเภท", "edit-combo", H.UNIT_KINDS), ("name", "ชื่อ", "text"),
             ("parent_id", "สังกัด", "combo", parents),
             ("aliases", "ชื่อย่อในคำชี้แจง (คั่นด้วย ,)", "text"),
             ("head_pos", "ตำแหน่งหัวหน้า (ผู้ให้ความเห็น)", "text"), ("head_name", "ชื่อหัวหน้า", "text"),
             ("officer_pos", "ตำแหน่งผู้เสนอเรื่อง", "text"), ("officer_name", "ชื่อผู้เสนอเรื่อง", "text"),
             ("note", "หมายเหตุ", "multi")]
        dlg = FormDialog(self, T("กอง / ฝ่าย / งาน"), f, values,
                         hints=dict(aliases="เช่น กองการศึกษาฯ, กองการศึกษา",
                                    head_pos="ว่าง = ไม่อยู่ในเส้นทางเสนอเอกสาร"))
        return dlg.values() if dlg.exec() else None

    def add_top(self):
        v = self._div_dialog(dict(kind="กอง", parent_id=None))
        if v and _do(self, self.p.store.save_division, v):
            self.p.changed()

    def add_sub(self):
        did = self.cur()
        if not did:
            return need_selection(self)
        kind = {"กอง": "ฝ่าย", "ฝ่าย": "งาน"}.get(self.p.store.division(did)["kind"], "หน่วยงานย่อย")
        v = self._div_dialog(dict(kind=kind, parent_id=did))
        if v and _do(self, self.p.store.save_division, v):
            self.p.changed()

    def edit_div(self):
        did = self.cur()
        if not did:
            return need_selection(self)
        v = self._div_dialog(dict(self.p.store.division(did)))
        if v and _do(self, self.p.store.save_division, v, did):
            self.p.changed()

    def del_div(self):
        did = self.cur()
        if not did:
            return need_selection(self)
        if QMessageBox.question(self, PRODUCT_TH, T("ลบหน่วยงานนี้และตำแหน่งในหน่วยงาน? (ต้องลบหน่วยงานย่อยก่อน)")) \
                == QMessageBox.Yes:
            if _do(self, self.p.store.delete_division, did) is not False:
                self.p.changed()

    def seed(self):
        s = self.p.store
        replace = bool(s.divisions())
        if replace and QMessageBox.question(
                self, PRODUCT_TH, T("แทนที่โครงสร้างเดิมทั้งหมดด้วยโครงสร้าง อบต.ไม้ขาว ตามแผนอัตรากำลัง 3 ปี (2570–2572)? "
                                    "ภาระงานที่กรอกไว้จะถูกลบ")) != QMessageBox.Yes:
            return
        n = _do(self, s.seed_manpower, replace=replace)
        if n:
            fy = self.p.fy.value()
            k = s.assign_divisions(fy)
            s.set_setting(f"hire_assigned_{fy}", "1")
            QMessageBox.information(self, PRODUCT_TH, T(
                f"สร้าง {n['units']} หน่วยงาน {n['positions']} ตำแหน่ง กรอบ {n['frame']} อัตรา (ว่าง {n['vacant']}) "
                f"และกำหนดกองให้รายการงบปี {fy} {k} รายการ — ตรวจสอบและแก้ไขได้"))
            self.p.changed()

    def assign(self):
        from .pages_hire import AssignDialog
        if AssignDialog(self, self.p.store, self.p.fy.value()).exec():
            self.p.changed()

    # ---- positions
    def _pos_dialog(self, values):
        s = self.p.store
        divs = [(d["id"], d["name"]) for d in s.divisions(all_levels=True)]
        f = [("division_id", "หน่วยงาน", "combo", divs), ("title", "ตำแหน่ง", "text"),
             ("level", "ระดับ", "edit-combo", ["", "ต้น", "กลาง", "ปก./ชก.", "ปง./ชง.", "คศ.", "ปก.", "ชก.", "ปง.", "ชง."]),
             ("kind", "ประเภท", "edit-combo", M.STAFF_TYPES), ("line", "สายงาน (ค่างานจ้างเหมา)", "combo", H.LINES),
             ("count", "กรอบอัตรากำลัง", "int"), ("occupied", "มีคนครอง", "int"),
             ("position_no", "เลขที่ตำแหน่ง", "text"), ("note", "หมายเหตุ", "text")]
        dlg = FormDialog(self, T("ตำแหน่ง"), f, values)
        if not dlg.exec():
            return None
        v = dlg.values()
        v["count"], v["occupied"] = int(v["count"]), int(v["occupied"])
        return v

    def add_pos(self):
        did = self.cur()
        if not did:
            return need_selection(self)
        v = self._pos_dialog(dict(division_id=did, count=1, occupied=1, line="ทั่วไป"))
        if v and _do(self, self.p.store.save_position, v):
            self.refresh()

    def edit_pos(self):
        pid = self.pid()
        if not pid:
            return need_selection(self)
        v = self._pos_dialog(dict(self.p.store.position(pid)))
        if v and _do(self, self.p.store.save_position, v, pid) is not None:
            self.refresh()

    def del_pos(self):
        pid = self.pid()
        if pid and QMessageBox.question(self, PRODUCT_TH, T("ลบตำแหน่งนี้ (รวมภาระงานที่กรอกไว้)?")) == QMessageBox.Yes:
            self.p.store.delete_position(pid)
            self.refresh()

    def workload(self):
        pid = self.pid()
        if not pid:
            return need_selection(self)
        if WorkloadDialog(self, self.p.store, pid).exec():
            self.refresh()

    def print_pos(self):
        pid = self.pid()
        if not pid:
            return need_selection(self)
        from .pages_hire import _menu_at
        s, win = self.p.store, self.p.win
        _menu_at(self, [("เอกสารหมายเลข 4 บัญชีแสดงการคำนวณจำนวนอัตรากำลัง",
                         lambda: win.preview(HR.position_workload_sheet(s, pid))),
                        ("เอกสารหมายเลข 5 บัญชีแสดงปริมาณงานย้อนหลัง 3 ปี",
                         lambda: win.preview(HR.position_history_sheet(s, pid)))])

    def make_job(self):
        pid = self.pid()
        if not pid:
            return need_selection(self)
        a = self.p.store.position_analysis(pid)
        if not a["has_load"]:
            return error(self, ValueError("กรอกภาระงาน (เวลาต่อราย และปริมาณงาน) ของตำแหน่งนี้ก่อน"))
        jid = _do(self, self.p.store.job_from_position, pid)
        if jid:
            QMessageBox.information(self, PRODUCT_TH, T("สร้างงานจ้างเหมาแล้ว — ไปที่แท็บ «งานที่จะจ้าง · ค่างาน»"))
            self.p.tabs.setCurrentWidget(self.p.jobs)
            self.p.changed()


# ============================================================== workload
class WorkloadDialog(QDialog):
    """ภาระงานของตำแหน่ง: ลักษณะงานจากมาตรฐานกำหนดตำแหน่ง แยกด้าน และหัวข้อย่อย (1.1.1 …) ที่นับปริมาณงานได้ —
    เจ้าหน้าที่เติมเวลาต่อรายและปริมาณงานเอง."""

    HEAD = ["ด้าน / ข้อ / หัวข้อย่อย (จากมาตรฐานกำหนดตำแหน่ง)", "นาที/ราย", "ปริมาณ/ปี", "นาที/ปี", "คน",
            "ย้อนหลัง 3 ปี", "ย้อนหลัง 2 ปี", "ย้อนหลัง 1 ปี"]
    BAND = "#E8EEF5"

    def __init__(self, parent, store, pid):
        super().__init__(parent)
        self.s, self.pid = store, pid
        p = store.position(pid)
        self.std = store.standard_for(p["title"])
        self.setWindowTitle(T("ภาระงาน") + f" — {p['title']} · {p['division']}")
        lay = QVBoxLayout(self)
        via = "" if self.std == M.base_title(p["title"]) else f" (ใช้มาตรฐานของ «{self.std}»)"
        has = bool(store.q("SELECT 1 FROM duties WHERE title=?", (self.std,)))
        info = QLabel(T(f"ลักษณะงานจากมาตรฐานกำหนดตำแหน่ง «{self.std}»{via} แยกด้านและหัวข้อย่อย · เติมเวลาที่ใช้ต่อราย "
                        "(นาที) และปริมาณงานต่อปีเองที่หัวข้อย่อย · แถวที่ว่างไม่นำมาคำนวณ")
                     + ("" if has else T(" — ตำแหน่งนี้ยังไม่มีมาตรฐาน: เพิ่มที่แท็บ «มาตรฐานกำหนดตำแหน่ง» หรือปุ่มด้านล่าง")))
        info.setWordWrap(True)
        lay.addWidget(info)
        self.t = QTableWidget(0, len(self.HEAD))
        self.t.setHorizontalHeaderLabels([T(h) for h in self.HEAD])
        hh = self.t.horizontalHeader()
        hh.setSectionResizeMode(hh.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(0, hh.ResizeMode.Stretch)
        self.t.verticalHeader().setVisible(False)
        self.t.setWordWrap(False)
        self.t.itemChanged.connect(self._recalc)
        lay.addWidget(self.t, 1)
        self.res = QLabel()
        self.res.setTextFormat(Qt.RichText)
        lay.addWidget(self.res)
        row, _ = _buttons(("เพิ่มข้อในมาตรฐาน…", self.add_duty), ("เพิ่มหัวข้อย่อย…", self.add_sub),
                          ("แก้ไขข้อความ…", self.edit_row), ("ลบแถว", self.del_row), (None, None))
        lay.addLayout(row)
        lay.addWidget(_bb(self))
        self._busy = False
        self.load(store.load_rows_from_standard(pid))
        fit_to_screen(self, px(1250), px(780))

    def _cell(self, i, c, text, editable=False, band=False, bold=False, italic=False, right=False):
        x = QTableWidgetItem(text)
        x.setFlags((Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable) if editable
                   else (Qt.ItemIsEnabled | Qt.ItemIsSelectable))
        if band:
            x.setBackground(QColor(self.BAND))
        if bold or italic:
            f = x.font()
            f.setBold(bold)
            f.setItalic(italic)
            x.setFont(f)
        if right:
            x.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.t.setItem(i, c, x)
        return x

    def load(self, rows):
        self._busy = True
        self.t.setRowCount(0)
        side = None
        for r in rows:
            if r["side"] != side:
                side = r["side"]
                i = self.t.rowCount()
                self.t.insertRow(i)
                self._cell(i, 0, side or T("ลักษณะงาน"), band=True, bold=True)
                for c in range(1, len(self.HEAD)):
                    self._cell(i, c, "", band=True)
            i = self.t.rowCount()
            self.t.insertRow(i)
            pad = "  " if r.get("level") else ""
            label = f"{pad}{r.get('no') or ''} {r['task']}".rstrip()
            it = self._cell(i, 0, label, italic=r.get("kind") == "head")
            it.setToolTip(r["task"])
            if r.get("kind") == "head":
                it.setData(Qt.UserRole + 1, dict(duty_id=r["duty_id"], side=r["side"], task=r["task"], head=True))
                for c in range(1, len(self.HEAD)):
                    self._cell(i, c, "")
                continue
            it.setData(Qt.UserRole, dict(duty_id=r.get("duty_id"), side=r["side"], task=r["task"]))
            vals = [r.get("minutes"), r.get("volume"), None, None, r.get("y1"), r.get("y2"), r.get("y3")]
            for c, v in enumerate(vals, 1):
                x = self._cell(i, c, "" if not v else f"{v:g}", editable=c not in (3, 4), right=True)
                if c in (3, 4):
                    x.setForeground(QColor(MUTED))
        self._busy = False
        self._recalc()

    def _num(self, r, c):
        try:
            return float((self.t.item(r, c).text() or "0").replace(",", ""))
        except (ValueError, AttributeError):
            return 0.0

    def rows(self):
        out = []
        for r in range(self.t.rowCount()):
            meta = self.t.item(r, 0).data(Qt.UserRole)
            if not meta:
                continue
            out.append(dict(duty_id=meta.get("duty_id"), side=meta.get("side", ""), task=meta.get("task", ""),
                            minutes=self._num(r, 1), volume=self._num(r, 2), y1=self._num(r, 5), y2=self._num(r, 6),
                            y3=self._num(r, 7)))
        return out

    def _recalc(self, *_):
        if self._busy:
            return
        self._busy = True
        per = float(self.s.setting("work_minutes_year") or 82800)
        tot = fte = 0.0
        for r in range(self.t.rowCount()):
            if not self.t.item(r, 0).data(Qt.UserRole):
                continue
            m = self._num(r, 1) * self._num(r, 2)
            sh = round(m / per, 2)
            tot += m
            fte += sh
            self.t.item(r, 3).setText(f"{m:,.0f}" if m else "")
            self.t.item(r, 4).setText(f"{sh:.2f}" if m else "")
        self._busy = False
        p = self.s.position(self.pid)
        occ = p["occupied"] if p["occupied"] is not None else p["count"]
        need = M.need_people(fte)
        short = need - occ if fte else 0
        col = RED if short > 0 else GREEN
        self.res.setText(f"{T('รวม')} {tot:,.0f} {T('นาที/ปี')} ÷ {per:,.0f} = <b>{fte:.2f} {T('คน')}</b> → "
                         f"{T('ต้องการ')} <b>{need}</b> · {T('กรอบ')} {p['count']} · {T('มีคนครอง')} {occ} · "
                         f"<b style='color:{col}'>{T('ขาด') if short > 0 else T('ขาด/เกิน')} {short:+d}</b>")

    def _reload(self):
        """อ่านมาตรฐานใหม่ (หลังเพิ่ม/แก้/ลบข้อ) โดยคงค่าที่กรอกไว้."""
        cur = {r["duty_id"]: r for r in self.rows() if r["duty_id"]}
        rows = self.s.load_rows_from_standard(self.pid)
        for r in rows:
            if r.get("kind") == "leaf" and r["duty_id"] in cur:
                v = cur[r["duty_id"]]
                r.update(minutes=v["minutes"], volume=v["volume"], y1=v["y1"], y2=v["y2"], y3=v["y3"])
        self.load(rows)

    def _selected(self):
        r = self.t.currentRow()
        if r < 0:
            return None
        it = self.t.item(r, 0)
        return it.data(Qt.UserRole) or it.data(Qt.UserRole + 1)

    def add_duty(self):
        f = [("side", "ด้าน", "edit-combo", M.SIDES), ("text", "ลักษณะงานที่ปฏิบัติ (ข้อ)", "multi")]
        dlg = FormDialog(self, T("เพิ่มข้อในมาตรฐานกำหนดตำแหน่ง") + f" — {self.std}", f, dict(side=M.SIDES[0]))
        if dlg.exec():
            v = dlg.values()
            if _do(self, self.s.save_duty, dict(title=self.std, side=v["side"], text=v["text"])):
                self._reload()

    def add_sub(self):
        meta = self._selected()
        if not meta or not meta.get("duty_id"):
            return need_selection(self)
        d = self.s.one("SELECT * FROM duties WHERE id=?", (meta["duty_id"],))
        parent = d["parent_id"] or d["id"]
        main = self.s.one("SELECT * FROM duties WHERE id=?", (parent,))
        dlg = FormDialog(self, T("เพิ่มหัวข้อย่อย"), [("text", f"หัวข้อย่อยของ: {main['text'][:60]}…", "multi")])
        if dlg.exec() and _do(self, self.s.save_duty, dict(parent_id=parent, text=dlg.values()["text"])):
            self._reload()

    def edit_row(self):
        meta = self._selected()
        if not meta or not meta.get("duty_id"):
            return need_selection(self)
        d = self.s.one("SELECT * FROM duties WHERE id=?", (meta["duty_id"],))
        dlg = FormDialog(self, T("แก้ไขข้อความ (มาตรฐานกำหนดตำแหน่ง)"), [("text", "ข้อความ", "multi")],
                         dict(text=d["text"]))
        if dlg.exec() and _do(self, self.s.save_duty, dict(text=dlg.values()["text"]), d["id"]):
            self._reload()

    def del_row(self):
        meta = self._selected()
        if not meta:
            return need_selection(self)
        if meta.get("duty_id"):
            ans = QMessageBox.question(
                self, PRODUCT_TH, T("ลบข้อนี้ (และหัวข้อย่อย) ออกจากมาตรฐานกำหนดตำแหน่ง?\n"
                                    "ไม่ = ล้างเฉพาะตัวเลขที่กรอกของตำแหน่งนี้"),
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel)
            if ans == QMessageBox.Cancel:
                return
            if ans == QMessageBox.Yes:
                self.s.delete_duty(meta["duty_id"])
                return self._reload()
        r = self.t.currentRow()
        for c in (1, 2, 5, 6, 7):
            if self.t.item(r, c):
                self.t.item(r, c).setText("")

    def accept(self):
        rows = [r for r in self.rows() if r["minutes"] or r["volume"] or r["y1"] or r["y2"] or r["y3"]]
        self.s.set_pos_load(self.pid, rows)
        super().accept()


# ============================================================ standards
class StandardsTab(QWidget):
    """มาตรฐานกำหนดตำแหน่ง: ลักษณะงานที่ปฏิบัติของแต่ละตำแหน่ง แยกตามด้าน — เพิ่ม แก้ไข ลบ เลื่อน วางข้อความ."""

    def __init__(self, page):
        super().__init__()
        self.p = page
        lay = QVBoxLayout(self)
        sp = QSplitter(Qt.Horizontal)
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        self.search = QLineEdit()
        self.search.setPlaceholderText(T("ค้นหาตำแหน่ง…"))
        self.search.textChanged.connect(self.load_titles)
        ll.addWidget(self.search)
        self.line = QComboBox()
        for k, lab in (("", "ทุกสายงาน"), ("2", "สายบริหาร (นักบริหารงาน…)"), ("3", "สายวิชาการ"), ("4", "สายทั่วไป"),
                       ("x", "ตำแหน่งที่ยังไม่มีมาตรฐาน")):
            self.line.addItem(T(lab), k)
        self.line.currentIndexChanged.connect(self.load_titles)
        ll.addWidget(self.line)
        self.titles = QListWidget()
        self.titles.currentTextChanged.connect(self.show)
        ll.addWidget(self.titles, 1)
        row, _ = _buttons(("ตำแหน่งใหม่…", self.new_title),)
        ll.addLayout(row)
        sp.addWidget(left)
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        self.head = QLabel()
        self.head.setObjectName("section")
        rl.addWidget(self.head)
        self.t = table(["ด้าน", "ข้อ", "ลักษณะงานที่ปฏิบัติ / หัวข้อย่อย"], stretch=2)
        self.t.setWordWrap(True)
        self.t.doubleClicked.connect(lambda *_: self.edit())
        rl.addWidget(self.t, 1)
        note = QLabel(T("มาตรฐานกำหนดตำแหน่งจากเว็บไซต์ อบต.ไม้ขาว (98 ตำแหน่ง ระดับแรกของสายงาน) อ่านจากไฟล์สแกน "
                        "อาจมีคำผิดเล็กน้อย — ตรวจทานและแก้ได้ · หัวข้อย่อย (1.1.1 …) ใช้กรอกปริมาณงาน "
                        "โปรแกรมเสนอให้จากรายการ «เช่น …» และเพิ่ม/แก้/ลบได้"))
        note.setWordWrap(True)
        note.setStyleSheet(f"color:{MUTED}")
        rl.addWidget(note)
        row, _ = _buttons(("วางข้อความจากมาตรฐาน…", self.paste), ("เพิ่มข้อ", self.add),
                          ("เพิ่มหัวข้อย่อย", self.add_sub, True), ("เสนอหัวข้อย่อยอัตโนมัติ", self.propose),
                          ("แก้ไข", self.edit), ("ลบ", self.delete), ("ขึ้น", lambda: self.move(-1)),
                          ("ลง", lambda: self.move(1)))
        rl.addLayout(row)
        sp.addWidget(right)
        sp.setSizes([px(340), px(900)])
        lay.addWidget(sp, 1)

    def refresh(self):
        self.load_titles()

    def load_titles(self):
        cur = self.titles.currentItem().text() if self.titles.currentItem() else None
        q = self.search.text().strip()
        self.titles.blockSignals(True)
        self.titles.clear()
        s = self.p.store
        counts = {r["title"]: r["n"] for r in s.q("SELECT title, COUNT(*) AS n FROM duties WHERE parent_id IS NULL "
                                                  "GROUP BY title")}
        codes = {}
        for r in s.q("SELECT title, source FROM duties WHERE source LIKE 'มาตรฐานกำหนดตำแหน่ง %' GROUP BY title"):
            m = re.search(r"(\d{4})", r["source"])
            if m:
                codes[r["title"]] = m.group(1)
        want = self.line.currentData()
        for t in s.duty_titles():
            if q and q not in t:
                continue
            c = codes.get(t, "")
            via = s.standard_for(t)
            if t not in counts and via != t and via in counts:
                continue                       # ผู้ช่วย…/หัวหน้า… ใช้มาตรฐานของตำแหน่งหลัก — ไม่แสดงซ้ำ
            if want == "x" and t in counts:
                continue
            if want and want != "x" and not (c.startswith(want) or (want == "2" and c.startswith("1"))):
                continue
            self.titles.addItem((f"{c} " if c else "") + f"{t}" + (f"  ({counts[t]})" if t in counts else ""))
        self.titles.blockSignals(False)
        items = [self.titles.item(i) for i in range(self.titles.count())]
        pick = next((it for it in items if cur and it.text() == cur), items[0] if items else None)
        if pick:
            self.titles.setCurrentItem(pick)
        self.show()

    def title(self):
        it = self.titles.currentItem()
        return re.sub(r"^\d{4} ", "", it.text().split("  (")[0]) if it else None

    def show(self, *_):
        t = self.title()
        rows = self.p.store.duty_rows(t) if t else []
        src = rows[0]["duty"]["source"] if rows else ""
        mains = sum(1 for r in rows if not r["level"])
        self.head.setText(T("มาตรฐานกำหนดตำแหน่ง") + f" — {t or ''}  ({mains} {T('ข้อ')}, "
                          f"{len(rows) - mains} {T('หัวข้อย่อย')})" + (f" · {src}" if src else ""))
        fill(self.t, [[r["duty"]["side"], r["no"], ("\u2003\u2003" if r["level"] else "") + r["duty"]["text"]]
                      for r in rows], ids=[r["duty"]["id"] for r in rows])
        for i, r in enumerate(rows):
            if r["level"]:
                self.t.item(i, 2).setForeground(QColor("#1A5FA6"))
        self.t.resizeRowsToContents()

    def add_sub(self):
        did = selected_id(self.t)
        if not did:
            return need_selection(self)
        d = self.p.store.one("SELECT * FROM duties WHERE id=?", (did,))
        parent = d["parent_id"] or d["id"]
        main = self.p.store.one("SELECT * FROM duties WHERE id=?", (parent,))
        dlg = FormDialog(self, T("เพิ่มหัวข้อย่อย"), [("text", f"หัวข้อย่อยของ: {main['text'][:60]}…", "multi")])
        if dlg.exec() and _do(self, self.p.store.save_duty, dict(parent_id=parent, text=dlg.values()["text"])):
            self.show()

    def propose(self):
        t = self.title()
        if not t:
            return need_selection(self)
        n = sum(self.p.store.add_proposed_subs(r["id"]) for r in
                self.p.store.q("SELECT id FROM duties WHERE title=? AND parent_id IS NULL", (t,)))
        QMessageBox.information(self, PRODUCT_TH, T(f"เพิ่มหัวข้อย่อยที่โปรแกรมเสนอ {n} หัวข้อ "
                                                    "(เฉพาะข้อที่ยังไม่มีหัวข้อย่อยและมีรายการ «เช่น …»)"))
        self.show()

    def new_title(self):
        dlg = FormDialog(self, T("ตำแหน่งใหม่"), [("title", "ชื่อตำแหน่ง (ตามมาตรฐานกำหนดตำแหน่ง)", "text")])
        if dlg.exec() and dlg.values()["title"]:
            self.paste(dlg.values()["title"])

    def paste(self, title=None):
        t = title if isinstance(title, str) else self.title()
        if not t:
            return need_selection(self)
        dlg = PasteStandardDialog(self, self.p.store, t)
        if dlg.exec():
            self.search.clear()
            self.load_titles()
            for i in range(self.titles.count()):
                if re.sub(r"^\d{4} ", "", self.titles.item(i).text().split("  (")[0]) == M.base_title(t):
                    self.titles.setCurrentRow(i)

    def _dlg(self, values):
        f = [("side", "ด้าน", "edit-combo", M.SIDES), ("text", "ลักษณะงานที่ปฏิบัติ", "multi")]
        dlg = FormDialog(self, T("ลักษณะงานที่ปฏิบัติ") + f" — {self.title()}", f, values)
        return dlg.values() if dlg.exec() else None

    def add(self):
        t = self.title()
        if not t:
            return need_selection(self)
        v = self._dlg(dict(side=M.SIDES[0]))
        if v and _do(self, self.p.store.save_duty, dict(title=t, side=v["side"], text=v["text"])):
            self.load_titles()

    def edit(self):
        did = selected_id(self.t)
        if not did:
            return need_selection(self)
        r = self.p.store.one("SELECT * FROM duties WHERE id=?", (did,))
        v = self._dlg(dict(side=r["side"], text=r["text"]))
        if v and _do(self, self.p.store.save_duty, v, did):
            self.show()

    def delete(self):
        did = selected_id(self.t)
        if did and QMessageBox.question(self, PRODUCT_TH, T("ลบลักษณะงานนี้? (ภาระงานที่กรอกไว้ของข้อนี้จะถูกลบด้วย)")) \
                == QMessageBox.Yes:
            self.p.store.delete_duty(did)
            self.load_titles()

    def move(self, step):
        did = selected_id(self.t)
        if not did:
            return need_selection(self)
        self.p.store.move_duty(did, step)
        self.show()
        for r in range(self.t.rowCount()):
            if self.t.item(r, 0).data(Qt.UserRole) == did:
                self.t.selectRow(r)


class PasteStandardDialog(QDialog):
    def __init__(self, parent, store, title):
        super().__init__(parent)
        self.s, self.title_ = store, title
        self.setWindowTitle(T("วางข้อความจากมาตรฐานกำหนดตำแหน่ง") + f" — {title}")
        lay = QVBoxLayout(self)
        lab = QLabel(T("คัดลอกส่วน «หน้าที่และความรับผิดชอบหลัก» จากมาตรฐานกำหนดตำแหน่ง (PDF/Word) มาวางด้านล่าง "
                       "เช่น «๑. ด้านการปฏิบัติการ ๑.๑ … ๒. ด้านการวางแผน ๒.๑ …» — ตรวจตัวอย่างทางขวาก่อนบันทึก"))
        lab.setWordWrap(True)
        lay.addWidget(lab)
        sp = QSplitter(Qt.Horizontal)
        self.txt = QPlainTextEdit()
        self.txt.textChanged.connect(self.preview)
        sp.addWidget(self.txt)
        self.prev = table(["ด้าน", "ลักษณะงานที่ปฏิบัติ"], stretch=1)
        self.prev.setWordWrap(True)
        sp.addWidget(self.prev)
        lay.addWidget(sp, 1)
        self.replace = QComboBox()
        self.replace.addItem(T("เพิ่มต่อจากข้อที่มีอยู่"), False)
        self.replace.addItem(T("แทนที่ข้อเดิมทั้งหมดของตำแหน่งนี้"), True)
        lay.addWidget(self.replace)
        lay.addWidget(_bb(self, "บันทึกเป็นมาตรฐานกำหนดตำแหน่ง"))
        fit_to_screen(self, px(1200), px(720))

    def preview(self):
        rows = M.parse_standard(self.txt.toPlainText())
        fill(self.prev, [[a, b] for a, b in rows])
        self.prev.resizeRowsToContents()

    def accept(self):
        n = _do(self, self.s.import_standard, self.title_, self.txt.toPlainText(), self.replace.currentData(),
                "วางจากมาตรฐานกำหนดตำแหน่ง")
        if n is not None:
            QMessageBox.information(self, PRODUCT_TH, T(f"บันทึก {n} ข้อ"))
            super().accept()


class PickDutiesDialog(QDialog):
    """เลือกลักษณะงานจากมาตรฐานกำหนดตำแหน่ง (สำหรับงานจ้างเหมา)."""

    def __init__(self, parent, store, title):
        super().__init__(parent)
        self.s = store
        self.setWindowTitle(T("เลือกลักษณะงานจากมาตรฐานกำหนดตำแหน่ง"))
        lay = QVBoxLayout(self)
        top = QHBoxLayout()
        top.addWidget(QLabel(T("ตำแหน่ง")))
        self.title = QComboBox()
        self.title.setEditable(True)
        self.title.addItems(store.duty_titles())
        self.title.setCurrentText(store.standard_for(title))
        self.title.currentTextChanged.connect(self.load)
        top.addWidget(self.title, 1)
        lay.addLayout(top)
        self.t = table(["", "ด้าน", "ลักษณะงานที่ปฏิบัติ"], stretch=2)
        self.t.setWordWrap(True)
        lay.addWidget(self.t, 1)
        self.empty = QLabel()
        self.empty.setStyleSheet(f"color:{MUTED}")
        lay.addWidget(self.empty)
        lay.addWidget(_bb(self, "เพิ่มที่เลือก"))
        self.load()
        fit_to_screen(self, px(1100), px(680))

    def load(self, *_):
        rows = [r for r in self.s.duty_rows(self.title.currentText()) if not r["has_subs"]]   # เฉพาะข้อที่กรอกปริมาณงานได้
        fill(self.t, [["", r["duty"]["side"], f"{r['no']} {r['duty']['text']}"] for r in rows],
             ids=[r["duty"]["id"] for r in rows])
        self._task = {r["duty"]["id"]: r["duty"]["text"] for r in rows}
        for i in range(self.t.rowCount()):
            self.t.item(i, 0).setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            self.t.item(i, 0).setCheckState(Qt.Checked)
        self.t.resizeRowsToContents()
        self.empty.setText("" if rows else T("ตำแหน่งนี้ยังไม่มีมาตรฐานกำหนดตำแหน่ง — เพิ่มที่แท็บ «มาตรฐานกำหนดตำแหน่ง»"))

    def chosen(self):
        out = []
        for i in range(self.t.rowCount()):
            if self.t.item(i, 0).checkState() == Qt.Checked:
                out.append(dict(duty_id=self.t.item(i, 0).data(Qt.UserRole), side=self.t.item(i, 1).text(),
                                task=self._task.get(self.t.item(i, 0).data(Qt.UserRole), self.t.item(i, 2).text()),
                                minutes=0, volume=0))
        return out


# ============================================================== analysis
class AnalysisTab(QWidget):
    HEAD = ["ส่วนราชการ / ตำแหน่ง", "ระดับ", "ประเภท", "กรอบ", "มีคนครอง", "ว่าง", "ภาระงาน (คน)", "ต้องการ",
            "ขาด/เกิน", "ข้อเสนอ"]

    def __init__(self, page):
        super().__init__()
        self.p = page
        lay = QVBoxLayout(self)
        self.cards = QLabel()
        self.cards.setTextFormat(Qt.RichText)
        self.cards.setWordWrap(True)
        lay.addWidget(self.cards)
        self.t = table(self.HEAD, stretch=9)
        hh = self.t.horizontalHeader()
        hh.setSectionResizeMode(0, hh.ResizeMode.Interactive)
        hh.resizeSection(0, px(400))
        lay.addWidget(self.t, 1)
        self.only = QComboBox()
        for k, lab in (("all", "แสดงทุกตำแหน่ง"), ("short", "เฉพาะที่ขาดคน"), ("vacant", "เฉพาะที่มีตำแหน่งว่าง"),
                       ("todo", "เฉพาะที่ยังไม่กรอกปริมาณงาน")):
            self.only.addItem(T(lab), k)
        self.only.currentIndexChanged.connect(self.refresh)
        row, _ = _buttons((None, None), ("พิมพ์/ส่งออก ตารางวิเคราะห์", self.print_))
        row.insertWidget(0, self.only)
        lay.addLayout(row)

    def refresh(self):
        s = self.p.store
        rows = s.manpower_rows(self.p.did())
        k = self.only.currentData()
        if k != "all":
            keep = {"short": lambda x: (x.get("short") or 0) > 0, "vacant": lambda x: x["vacant"] > 0,
                    "todo": lambda x: not x.get("has_load")}[k]
            rows = [x for x in rows if x["kind"] == "unit" or keep(x)]
        data, colors = [], []
        for x in rows:
            ind = "　" * x["depth"]
            if x["kind"] == "unit":
                d = x["division"]
                data.append([f"{ind}▸ {d['name']}", "", d["kind"], x["frame"], x["occupied"], x["vacant"],
                             f"{x['fte']:.2f}" if x["analysed"] else "", x["need"] or "",
                             f"+{x['short']}" if x["short"] else "", f"วิเคราะห์แล้ว {x['analysed']}/{x['positions']}"])
            else:
                p = x["position"]
                data.append([f"{ind}{p['title']}", p["level"] or "", p["kind"] or "", x["frame"], x["occupied"],
                             x["vacant"], f"{x['fte']:.2f}" if x["has_load"] else "",
                             x["need"] if x["need"] is not None else "", _short(x), HR.proposal_text(x)])
            colors.append(x)
        fill(self.t, data)
        bold = QFont()
        bold.setBold(True)
        for r, x in enumerate(colors):
            if x["kind"] == "unit":
                for c in range(self.t.columnCount()):
                    self.t.item(r, c).setBackground(QColor("#EEF3F8" if x["depth"] else "#DCE7F3"))
                self.t.item(r, 0).setFont(bold)
            else:
                if x["vacant"]:
                    self.t.item(r, 5).setForeground(QColor(AMBER))
                if x.get("short") is not None:
                    self.t.item(r, 8).setForeground(QColor(RED if x["short"] > 0 else GREEN))
        tops = [x for x in s.manpower_rows(self.p.did()) if x["kind"] == "unit" and x["depth"] == 0]
        f = sum(x["frame"] for x in tops)
        o = sum(x["occupied"] for x in tops)
        v = sum(x["vacant"] for x in tops)
        sh = sum(x["short"] for x in tops)
        an = sum(x["analysed"] for x in tops)
        n = sum(x["positions"] for x in tops)
        self.cards.setText(
            f"<span style='font-size:13pt'>{T('กรอบอัตรากำลัง')} <b>{f}</b> · {T('มีคนครอง')} <b>{o}</b> · "
            f"{T('ตำแหน่งว่าง')} <b style='color:{AMBER}'>{v}</b> · {T('วิเคราะห์ภาระงานแล้ว')} <b>{an}/{n}</b> "
            f"{T('ตำแหน่ง')} · {T('ต้องการคนเพิ่ม')} <b style='color:{RED}'>{sh}</b> {T('คน')}</span>")

    def print_(self):
        self.p.win.preview(HR.manpower_report(self.p.store, self.p.did()))
