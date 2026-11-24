# SPDX-License-Identifier: GPL-3.0-or-later
"""หน้าจอ «จ้างเหมาบุคคล»: โครงสร้างหน่วยงาน (กอง/หน่วยงานย่อย/ตำแหน่ง), งานที่จะจ้างและค่างาน,
สัญญาจ้างและการตรวจรับ/เบิกจ่ายรายเดือน, สรุปงบแยกตามกอง."""
from __future__ import annotations

import calendar

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QGroupBox, QHBoxLayout, QLabel, QMenu,
                               QMessageBox, QPushButton, QSplitter, QTableWidget, QTableWidgetItem, QTabWidget,
                               QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget)

from . import PRODUCT_TH
from . import hire as H
from . import hire_reports as HR
from . import thaidate as TD
from .i18n import T
from .pages_budget import RED, GREEN, _buttons, _page, fy_spin, m
from .widgets import (MUTED, FormDialog, error, fill, fit_to_screen, need_selection, px, selected_id, table)


def _do(parent, fn, *a, **k):
    try:
        return fn(*a, **k)
    except Exception as exc:  # noqa: BLE001
        error(parent, exc)
        return None


def _menu_at(widget, items):
    menu = QMenu(widget)
    for label, fn in items:
        if label is None:
            menu.addSeparator()
        else:
            menu.addAction(T(label), fn)
    menu.exec(widget.cursor().pos())


class HirePage(QWidget):
    def __init__(self, win):
        super().__init__()
        self.win = win
        w, lay = _page("จ้างเหมาบริการบุคคลธรรมดา (แยกตามกอง)",
                       "ปริมาณงาน → ค่างาน → ขอจ้าง/TOR/บก.06 → สัญญา (แบบฉบับที่ 3) → ตรวจรับ/เบิกจ่ายรายเดือน "
                       "ภายในงบของกอง · ไม่มีค่าปรับ/หลักประกัน (ว 727)")
        QVBoxLayout(self).addWidget(w)
        top = QHBoxLayout()
        top.addWidget(QLabel(T("ปีงบประมาณ")))
        self.fy = fy_spin()
        top.addWidget(self.fy)
        top.addWidget(QLabel(T("กอง")))
        self.div = QComboBox()
        self.div.setMinimumWidth(px(300))
        top.addWidget(self.div)
        top.addStretch(1)
        lay.addLayout(top)
        self.tabs = QTabWidget()
        self.org, self.jobs, self.cons, self.summ = OrgTab(self), JobTab(self), ContractTab(self), SummaryTab(self)
        for t, name in ((self.summ, "สรุปตามกอง"), (self.org, "โครงสร้างหน่วยงาน"), (self.jobs, "งานที่จะจ้าง · ค่างาน"),
                        (self.cons, "สัญญาจ้าง · ตรวจรับรายเดือน")):
            self.tabs.addTab(t, T(name))
        lay.addWidget(self.tabs, 1)
        self.fy.valueChanged.connect(self.refresh)
        self.div.currentIndexChanged.connect(self._tab_refresh)
        self.tabs.currentChanged.connect(self._tab_refresh)

    @property
    def store(self):
        return self.win.store

    def did(self):
        return self.div.currentData()

    def refresh(self):
        s = self.store
        fy = self.fy.value()
        key = f"hire_assigned_{fy}"             # กองของรายการงบ: อ่านจากคำชี้แจงครั้งแรกที่เปิดปีนั้น
        if s.divisions() and s.budget_items(fy) and not s.setting(key):
            s.assign_divisions(fy)
            s.set_setting(key, "1")
        cur = self.did()
        self.div.blockSignals(True)
        self.div.clear()
        self.div.addItem(T("ทุกกอง"), None)
        for d in s.divisions():
            self.div.addItem(d["name"], d["id"])
        i = self.div.findData(cur)
        self.div.setCurrentIndex(max(0, i))
        self.div.blockSignals(False)
        self._tab_refresh()

    def _tab_refresh(self, *_):
        self.tabs.currentWidget().refresh()

    def changed(self):
        self.win.refresh()


# =========================================================== structure
class OrgTab(QWidget):
    def __init__(self, page: HirePage):
        super().__init__()
        self.p = page
        lay = QVBoxLayout(self)
        sp = QSplitter(Qt.Horizontal)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels([T("กอง / หน่วยงานย่อย"), T("ประเภท"), T("ผู้อำนวยการ/หัวหน้า"),
                                   T("เจ้าหน้าที่ผู้ขอจ้าง")])
        self.tree.itemSelectionChanged.connect(self.show_positions)
        self.tree.itemDoubleClicked.connect(lambda *_: self.edit_div())
        sp.addWidget(self.tree)
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        self.pos_title = QLabel(T("ตำแหน่ง"))
        self.pos_title.setObjectName("section")
        rl.addWidget(self.pos_title)
        self.pos = table(["ตำแหน่ง", "สาย", "ประเภท", "จำนวน", "หมายเหตุ"], stretch=0)
        self.pos.doubleClicked.connect(lambda *_: self.edit_pos())
        rl.addWidget(self.pos, 1)
        self.budget = QLabel()
        self.budget.setWordWrap(True)
        rl.addWidget(self.budget)
        row, _ = _buttons(("เพิ่มตำแหน่ง", self.add_pos), ("แก้ไขตำแหน่ง", self.edit_pos), ("ลบตำแหน่ง", self.del_pos))
        rl.addLayout(row)
        sp.addWidget(right)
        sp.setSizes([px(620), px(560)])
        lay.addWidget(sp, 1)
        row, _ = _buttons(("เพิ่มกอง", self.add_top, True), ("เพิ่มหน่วยงานย่อย", self.add_sub),
                          ("แก้ไข", self.edit_div), ("ลบ", self.del_div), (None, None),
                          ("กำหนดกองให้รายการงบประมาณ", self.assign),
                          ("โหลดโครงสร้าง อบต.ไม้ขาว", self.seed))
        lay.addLayout(row)

    def refresh(self):
        s = self.p.store
        cur = self.cur()
        self.tree.clear()

        def add(parent, d):
            it = QTreeWidgetItem([d["name"], d["kind"] or "", d["head_pos"] or d["head_name"] or "",
                                  d["officer_pos"] or d["officer_name"] or ""])
            it.setData(0, Qt.UserRole, d["id"])
            (parent.addChild(it) if parent else self.tree.addTopLevelItem(it))
            for c in s.divisions(d["id"]):
                add(it, c)
            if d["id"] == cur:
                self.tree.setCurrentItem(it)
        for d in s.divisions():
            add(None, d)
        self.tree.expandAll()
        for i in range(4):
            self.tree.resizeColumnToContents(i)
        self.show_positions()

    def cur(self):
        it = self.tree.currentItem()
        return it.data(0, Qt.UserRole) if it else None

    def show_positions(self):
        s = self.p.store
        did = self.cur()
        rows = s.positions(did) if did else []
        fill(self.pos, [[r["title"], r["line"], r["kind"], int(r["count"] or 0), r["note"]] for r in rows],
             ids=[r["id"] for r in rows])
        if not did:
            self.pos_title.setText(T("ตำแหน่ง — เลือกกองทางซ้าย"))
            self.budget.setText("")
            return
        d = s.division(did)
        self.pos_title.setText(T("ตำแหน่ง") + f" · {d['name']} · " + T("รวม") +
                               f" {sum(int(r['count'] or 0) for r in rows)} " + T("อัตรา"))
        top = s.top_division(did)
        fy = self.p.fy.value()
        b, hb = s.division_budget(fy, top["id"]), s.division_budget(fy, top["id"], hire_only=True)
        self.budget.setText(f"{T('งบประมาณของ')}{top['name']} {T('ปี')} {fy}: {b['items']} {T('รายการ')} "
                            f"{m(b['budget'])} {T('บาท')} · {H.HIRE_ITEM} {m(hb['budget'])} "
                            f"({T('คงเหลือ')} <b>{m(hb['available'])}</b>)")

    # ---- divisions
    def _div_dialog(self, values, parent_ok=True):
        s = self.p.store
        parents = [(None, "— (เป็นกอง)")] + [(d["id"], d["name"]) for d in s.divisions(all_levels=True)
                                              if d["id"] != values.get("id")]
        f = [("kind", "ประเภท", "edit-combo", H.UNIT_KINDS), ("name", "ชื่อ", "text"),
             ("parent_id", "สังกัด", "combo", parents),
             ("aliases", "ชื่อย่อในคำชี้แจง (คั่นด้วย ,)", "text"),
             ("head_name", "ผู้อำนวยการ/หัวหน้า (ชื่อ)", "text"), ("head_pos", "ตำแหน่ง", "text"),
             ("officer_name", "เจ้าหน้าที่ผู้ขอจ้าง (ชื่อ)", "text"), ("officer_pos", "ตำแหน่ง ", "text"),
             ("note", "หมายเหตุ", "multi")]
        dlg = FormDialog(self, T("กอง / หน่วยงานย่อย"), f, values,
                         hints=dict(aliases="เช่น กองการศึกษาฯ, กองการศึกษา", head_pos="ผู้อำนวยการกอง…"))
        return dlg.values() if dlg.exec() else None

    def add_top(self):
        v = self._div_dialog(dict(kind="กอง", parent_id=None))
        if v and _do(self, self.p.store.save_division, v):
            self.p.changed()

    def add_sub(self):
        did = self.cur()
        if not did:
            return need_selection(self)
        v = self._div_dialog(dict(kind="หน่วยงานย่อย", parent_id=did))
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
        if QMessageBox.question(self, PRODUCT_TH, T("ลบกอง/หน่วยงานนี้? (รายการงบและงานที่ผูกไว้จะไม่ระบุกอง)")) \
                == QMessageBox.Yes:
            if _do(self, self.p.store.delete_division, did) is not False:
                self.p.changed()

    def seed(self):
        s = self.p.store
        replace = False
        if s.divisions():
            if QMessageBox.question(self, PRODUCT_TH, T("มีโครงสร้างอยู่แล้ว — แทนที่ด้วยโครงสร้าง อบต.ไม้ขาว ทั้งหมด?")) \
                    != QMessageBox.Yes:
                return
            replace = True
            for d in s.divisions(all_levels=True)[::-1]:
                s.run("UPDATE budget_items SET division_id=NULL WHERE division_id=?", (d["id"],))
                s.run("UPDATE hire_jobs SET division_id=NULL WHERE division_id=?", (d["id"],))
            if s.q("SELECT 1 FROM hire_contracts WHERE status='ทำสัญญาแล้ว'"):
                return error(self, ValueError("มีสัญญาที่ยังมีผลอยู่ — แก้ไขโครงสร้างทีละกองแทน"))
            s.run("DELETE FROM positions")
            s.run("DELETE FROM divisions")
        n = _do(self, s.seed_structure, replace=replace)
        if n:
            fy = self.p.fy.value()
            k = s.assign_divisions(fy)
            s.set_setting(f"hire_assigned_{fy}", "1")
            QMessageBox.information(self, PRODUCT_TH, T(f"สร้าง {n} กอง และกำหนดกองให้รายการงบปี {fy} {k} รายการ "
                                                        "(จากคำชี้แจง) — ตรวจสอบและแก้ไขได้"))
            self.p.changed()

    def assign(self):
        if AssignDialog(self, self.p.store, self.p.fy.value()).exec():
            self.p.changed()

    # ---- positions
    def _pos_dialog(self, values):
        s = self.p.store
        divs = [(d["id"], d["name"]) for d in s.divisions(all_levels=True)]
        f = [("division_id", "กอง/หน่วยงาน", "combo", divs), ("title", "ตำแหน่ง", "text"),
             ("line", "สาย", "combo", [("", "(อัตโนมัติจากชื่อตำแหน่ง)")] + [(x, x) for x in H.LINES]),
             ("kind", "ประเภทบุคลากร", "edit-combo", [""] + H.KINDS), ("count", "จำนวน (อัตรา)", "int"),
             ("note", "หมายเหตุ", "text")]
        dlg = FormDialog(self, T("ตำแหน่ง"), f, values)
        if not dlg.exec():
            return None
        v = dlg.values()
        line, kind = H.classify(v["title"])
        v["line"] = v["line"] or line
        v["kind"] = v["kind"] or kind
        return v

    def add_pos(self):
        did = self.cur()
        if not did:
            return need_selection(self)
        v = self._pos_dialog(dict(division_id=did, count=1))
        if v and _do(self, self.p.store.save_position, v):
            self.show_positions()

    def edit_pos(self):
        pid = selected_id(self.pos)
        if not pid:
            return need_selection(self)
        row = self.p.store.one("SELECT * FROM positions WHERE id=?", (pid,))
        v = self._pos_dialog(dict(row))
        if v and _do(self, self.p.store.save_position, v, pid) is not None:
            self.show_positions()

    def del_pos(self):
        pid = selected_id(self.pos)
        if pid and QMessageBox.question(self, PRODUCT_TH, T("ลบตำแหน่งนี้?")) == QMessageBox.Yes:
            self.p.store.delete_position(pid)
            self.show_positions()


class AssignDialog(QDialog):
    """กำหนดกองให้รายการงบประมาณ (ค่าเริ่มต้นอ่านจากคำชี้แจง แก้ได้)."""

    def __init__(self, parent, store, fy):
        super().__init__(parent)
        self.s, self.fy = store, fy
        self.setWindowTitle(T("กำหนดกองให้รายการงบประมาณ") + f" {fy}")
        lay = QVBoxLayout(self)
        top = QHBoxLayout()
        self.only = QComboBox()
        for k, label in (("hire", "เฉพาะรายการจ้างเหมาบริการ"), ("use", "หมวดค่าใช้สอยทั้งหมด"),
                         ("none", "รายการที่ยังไม่ระบุกอง"), ("all", "ทุกรายการ")):
            self.only.addItem(T(label), k)
        self.only.currentIndexChanged.connect(self.load)
        top.addWidget(self.only)
        again = QPushButton(T("อ่านกองจากคำชี้แจงอีกครั้ง"))
        again.clicked.connect(self.reread)
        top.addWidget(again)
        top.addStretch(1)
        lay.addLayout(top)
        self.t = table(["แผนงาน", "งาน", "หมวด", "รายการ", "งบประมาณ", "กอง"], stretch=3)
        lay.addWidget(self.t, 1)
        note = QLabel(T("กองอ่านจากท้ายคำชี้แจง เช่น «(กองคลัง)» — รายการที่ไม่มีระบุใช้กองที่พบมากที่สุดในงานเดียวกัน"))
        note.setStyleSheet(f"color:{MUTED}")
        note.setWordWrap(True)
        lay.addWidget(note)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Ok).setText(T("บันทึก"))
        bb.button(QDialogButtonBox.Cancel).setText(T("ยกเลิก"))
        bb.accepted.connect(self.save)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        self.divs = [(None, "—")] + [(d["id"], d["name"]) for d in store.divisions()]
        self.load()
        fit_to_screen(self, px(1200), px(760))

    def load(self):
        k = self.only.currentData()
        rows = self.s.budget_items(self.fy)
        if k == "hire":
            rows = [b for b in rows if b["category"] == "ค่าใช้สอย" and "จ้างเหมา" in b["name"]]
        elif k == "use":
            rows = [b for b in rows if b["category"] == "ค่าใช้สอย"]
        elif k == "none":
            rows = [b for b in rows if not b["division_id"]]
        self.rows = rows
        fill(self.t, [[b["plan"], b["task"], b["category"], b["name"], float(b["amount"] or 0), ""] for b in rows],
             ids=[b["id"] for b in rows])
        for r, b in enumerate(rows):
            c = QComboBox()
            for did, name in self.divs:
                c.addItem(name, did)
            c.setCurrentIndex(max(0, c.findData(b["division_id"])))
            self.t.setCellWidget(r, 5, c)

    def reread(self):
        n = self.s.assign_divisions(self.fy, overwrite=True)
        QMessageBox.information(self, PRODUCT_TH, T(f"กำหนดกองจากคำชี้แจง {n} รายการ"))
        self.load()

    def save(self):
        for r, b in enumerate(self.rows):
            did = self.t.cellWidget(r, 5).currentData()
            if did != b["division_id"]:
                self.s.set_item_division(b["id"], did)
        self.accept()


# ================================================================ jobs
class JobTab(QWidget):
    TASK_HEAD = ["ลักษณะงานที่ปฏิบัติ", "นาที/ราย", "ราย/ปี", "นาที/ปี", "คน"]

    def __init__(self, page: HirePage):
        super().__init__()
        self.p = page
        lay = QVBoxLayout(self)
        sp = QSplitter(Qt.Horizontal)
        self.t = table(["กอง", "งานที่จะจ้าง", "สาย", "คุณวุฒิ", "คน", "ค่างาน/เดือน", "สัญญา"], stretch=1)
        self.t.horizontalHeader().setMinimumSectionSize(px(40))
        self.t.itemSelectionChanged.connect(self.show_tasks)
        self.t.doubleClicked.connect(lambda *_: self.edit())
        sp.addWidget(self.t)
        g = QGroupBox(T("บัญชีแสดงการคำนวณปริมาณงาน (แก้ไขในตารางได้)"))
        gl = QVBoxLayout(g)
        self.tasks = QTableWidget(0, len(self.TASK_HEAD))
        self.tasks.setHorizontalHeaderLabels([T(h) for h in self.TASK_HEAD])
        self.tasks.horizontalHeader().setStretchLastSection(False)
        hh = self.tasks.horizontalHeader()
        hh.setSectionResizeMode(hh.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(0, hh.ResizeMode.Stretch)
        self.tasks.verticalHeader().setVisible(False)
        self.tasks.itemChanged.connect(self._recalc)
        gl.addWidget(self.tasks, 1)
        self.result = QLabel()
        self.result.setWordWrap(True)
        self.result.setTextFormat(Qt.RichText)
        gl.addWidget(self.result)
        row, _ = _buttons(("เพิ่มแถว", self.add_row), ("ลบแถว", self.del_row), (None, None),
                          ("บันทึกปริมาณงาน", self.save_tasks, True))
        gl.addLayout(row)
        sp.addWidget(g)
        sp.setSizes([px(720), px(520)])
        lay.addWidget(sp, 1)
        row, _ = _buttons(("งานใหม่", self.new, True), ("แก้ไข", self.edit), ("ลบ", self.delete), (None, None),
                          ("อัตราค่างาน…", self.rates), ("พิมพ์เอกสาร", self.print_menu),
                          ("ทำสัญญาจ้างจากงานนี้", self.contract))
        lay.addLayout(row)
        self._loading = False

    def refresh(self):
        s = self.p.store
        jobs = s.jobs(self.p.did())
        rows = []
        for j in jobs:
            v = s.job_value(j)
            n = s.one("SELECT COUNT(*) AS n FROM hire_contracts WHERE job_id=? AND status!='ยกเลิก'", (j["id"],))["n"]
            rows.append([(j["division"] or "").replace("กองการศึกษา ศาสนา และวัฒนธรรม", "กองการศึกษาฯ")
                         .replace("กองสาธารณสุขและสิ่งแวดล้อม", "กองสาธารณสุขฯ"), j["title"], j["line"], j["qualification"], f"{v['fte']:.2f}",
                         float(v["monthly"]), n])
        cur = self.jid()
        fill(self.t, rows, ids=[j["id"] for j in jobs])
        for r, j in enumerate(jobs):
            if j["id"] == cur:
                self.t.selectRow(r)
        self.show_tasks()

    def jid(self):
        return selected_id(self.t)

    def show_tasks(self):
        self._loading = True
        jid = self.jid()
        self.tasks.setRowCount(0)
        for t in (self.p.store.tasks(jid) if jid else []):
            self._append(t["task"], t["minutes"], t["volume"])
        self._loading = False
        self._recalc()

    def _append(self, task="", minutes=0, volume=0):
        r = self.tasks.rowCount()
        self.tasks.insertRow(r)
        for c, v in enumerate((task, f"{minutes:g}", f"{volume:g}", "", "")):
            it = QTableWidgetItem(str(v))
            if c:
                it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            if c >= 3:
                it.setFlags(it.flags() & ~Qt.ItemIsEditable)
                it.setForeground(QColor(MUTED))
            self.tasks.setItem(r, c, it)

    def _rows(self):
        out = []
        for r in range(self.tasks.rowCount()):
            def num(c):
                try:
                    return float((self.tasks.item(r, c).text() or "0").replace(",", ""))
                except (ValueError, AttributeError):
                    return 0.0
            task = (self.tasks.item(r, 0).text() if self.tasks.item(r, 0) else "").strip()
            out.append((task, num(1), num(2)))
        return out

    def _recalc(self, *_):
        if self._loading:
            return
        self._loading = True
        per = float(self.p.store.setting("work_minutes_year") or H.WORK_MINUTES_YEAR)
        total = fte = 0.0
        for r, (task, mi, vol) in enumerate(self._rows()):
            share = round(mi * vol / per, 2)
            total += mi * vol
            fte += share
            self.tasks.item(r, 3).setText(f"{mi * vol:,.0f}")
            self.tasks.item(r, 4).setText(f"{share:.2f}")
        self._loading = False
        jid = self.jid()
        if not jid:
            self.result.setText(T("เลือกงานทางซ้าย หรือกด «งานใหม่»"))
            return
        j = self.p.store.job(jid)
        v = self.p.store.job_value(j)
        color = GREEN if 0.5 <= fte <= 1.5 else RED
        notes = "".join(f"<br>• {n}" for n in v["notes"])
        self.result.setText(
            f"{T('รวมเวลา')} {total:,.0f} {T('นาที/ปี')} ÷ {per:,.0f} = <b style='color:{color}'>{fte:.2f} {T('คน')}</b>"
            f" · {T('ค่างานสาย')}{j['line']} {j['qualification']} {m(v['base'])} + {v['difficulty']:g}% = "
            f"{m(v['suggested'])} · <b>{T('ใช้')} {m(v['monthly'])} {T('บาท/เดือน')}</b> "
            f"({T('วันละ')} {m(v['daily'])}){notes}")

    def add_row(self):
        if not self.jid():
            return need_selection(self)
        self._loading = True
        self._append()
        self._loading = False
        self.tasks.setCurrentCell(self.tasks.rowCount() - 1, 0)
        self.tasks.editItem(self.tasks.item(self.tasks.rowCount() - 1, 0))

    def del_row(self):
        r = self.tasks.currentRow()
        if r >= 0:
            self.tasks.removeRow(r)
            self._recalc()

    def save_tasks(self):
        jid = self.jid()
        if not jid:
            return need_selection(self)
        self.p.store.set_tasks(jid, [x for x in self._rows() if x[0]])
        self.refresh()

    def _dialog(self, values):
        s = self.p.store
        quals = []
        for _, q, _ in s.hire_rates():
            if q not in quals:
                quals.append(q)
        f = [("division_id", "กอง", "combo", [(d["id"], d["name"]) for d in s.divisions(all_levels=True)]),
             ("title", "งานที่จะจ้าง", "text"), ("line", "สายงาน", "combo", H.LINES),
             ("qualification", "คุณวุฒิ", "edit-combo", quals),
             ("difficulty", "ปรับตามความยากของงาน (%)", "num"),
             ("monthly", "ค่าจ้าง/เดือน (0 = ใช้ค่างานที่คำนวณ)", "money"),
             ("work_place", "สถานที่ปฏิบัติงาน", "text"), ("work_hours", "วันเวลาทำงาน", "text"),
             ("background", "ความเป็นมา (TOR ข้อ 1)", "multi"), ("objective", "วัตถุประสงค์ (TOR ข้อ 2)", "multi"),
             ("qualifications", "คุณสมบัติผู้ยื่นข้อเสนอ (TOR ข้อ 3)", "multi"),
             ("scope", "ขอบเขตงาน (TOR ข้อ 4 — ว่าง = ใช้รายการปริมาณงาน)", "multi"), ("note", "หมายเหตุ", "text")]
        dlg = FormDialog(self, T("งานที่จะจ้าง"), f, values)
        return dlg.values() if dlg.exec() else None

    def new(self):
        did = self.p.did() or (self.p.store.divisions()[0]["id"] if self.p.store.divisions() else None)
        if not did:
            return error(self, ValueError("สร้างโครงสร้างหน่วยงาน (กอง) ก่อน"))
        v = self._dialog(dict(division_id=did, line="ทั่วไป", qualification="ปวส./อนุปริญญา",
                              work_hours="วันจันทร์ถึงวันศุกร์ เวลา 08.30 น. ถึง 16.30 น."))
        if v:
            jid = _do(self, self.p.store.save_job, v)
            if jid:
                self.refresh()
                for r in range(self.t.rowCount()):
                    if self.t.item(r, 0).data(Qt.UserRole) == jid:
                        self.t.selectRow(r)

    def edit(self):
        jid = self.jid()
        if not jid:
            return need_selection(self)
        v = self._dialog(dict(self.p.store.job(jid)))
        if v and _do(self, self.p.store.save_job, v, jid):
            self.refresh()

    def delete(self):
        jid = self.jid()
        if jid and QMessageBox.question(self, PRODUCT_TH, T("ลบงานนี้?")) == QMessageBox.Yes:
            _do(self, self.p.store.delete_job, jid)
            self.refresh()

    def rates(self):
        if RatesDialog(self, self.p.store).exec():
            self.refresh()

    def print_menu(self):
        jid = self.jid()
        if not jid:
            return need_selection(self)
        s, win = self.p.store, self.p.win
        _menu_at(self, [("บัญชีแสดงการคำนวณปริมาณงาน", lambda: win.preview(HR.workload_sheet(s, jid))),
                        ("ขอบเขตของงาน (TOR)", lambda: win.preview(HR.tor(s, jid))),
                        ("ราคากลาง แบบ บก.06", lambda: win.preview(HR.bk06(s, jid)))])

    def contract(self):
        jid = self.jid()
        if not jid:
            return need_selection(self)
        j = self.p.store.job(jid)
        start, end = TD.fiscal_range(self.p.fy.value())
        today = TD.today()
        if start < today <= end:
            start = today.replace(day=1)
        if ContractDialog(self, self.p, None, dict(job_id=jid, division_id=j["division_id"], start=str(start),
                                                   end=str(end))).exec():
            self.p.tabs.setCurrentWidget(self.p.cons)
            self.p.changed()


class RatesDialog(QDialog):
    def __init__(self, parent, store):
        super().__init__(parent)
        self.s = store
        self.setWindowTitle(T("อัตราค่างานจ้างเหมาบริการบุคคล"))
        lay = QVBoxLayout(self)
        info = QLabel(T("อัตราเริ่มต้นเทียบค่าตอบแทนตามคุณวุฒิ — ตรวจสอบกับหนังสือ มท 0808.2/ว 9636 "
                        "และประกาศ/มติ ก.อบต. ก.จ. ก.ท. ที่หน่วยงานใช้อยู่ แล้วแก้ไขให้ตรง"))
        info.setWordWrap(True)
        lay.addWidget(info)
        self.t = QTableWidget(0, 3)
        self.t.setHorizontalHeaderLabels([T("สาย"), T("คุณวุฒิ"), T("อัตรา (บาท/เดือน)")])
        self.t.horizontalHeader().setSectionResizeMode(1, self.t.horizontalHeader().ResizeMode.Stretch)
        self.t.verticalHeader().setVisible(False)
        for line, q, rate in store.hire_rates():
            self._add(line, q, rate)
        lay.addWidget(self.t, 1)
        row, _ = _buttons(("เพิ่มแถว", lambda: self._add("ทั่วไป", "", 0)),
                          ("ลบแถว", lambda: self.t.removeRow(self.t.currentRow())), (None, None),
                          ("คืนค่าเริ่มต้น", self.reset))
        lay.addLayout(row)
        g = FormDialog.__new__(FormDialog)   # reuse field factories without a dialog
        g.w = {}
        self.minw = g._make("min_wage_day", "money", None, store.setting("min_wage_day"), None)
        self.mins = g._make("work_minutes_year", "int", None, store.setting("work_minutes_year"), None)
        for label, w in (("ค่าจ้างขั้นต่ำต่อวัน (เตือนเมื่อต่ำกว่า)", self.minw),
                         ("นาทีทำงานต่อปี (230 วัน × 6 ชม. = 82,800)", self.mins)):
            r = QHBoxLayout()
            r.addWidget(QLabel(T(label)))
            r.addWidget(w)
            lay.addLayout(r)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Ok).setText(T("บันทึก"))
        bb.button(QDialogButtonBox.Cancel).setText(T("ยกเลิก"))
        bb.accepted.connect(self.save)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        fit_to_screen(self, px(720), px(600))

    def _add(self, line, q, rate):
        r = self.t.rowCount()
        self.t.insertRow(r)
        c = QComboBox()
        c.addItems(H.LINES)
        c.setCurrentText(line)
        self.t.setCellWidget(r, 0, c)
        self.t.setItem(r, 1, QTableWidgetItem(q))
        it = QTableWidgetItem(f"{rate:,.0f}")
        it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.t.setItem(r, 2, it)

    def reset(self):
        self.t.setRowCount(0)
        for row in H.DEFAULT_RATES:
            self._add(*row)

    def save(self):
        rows = []
        for r in range(self.t.rowCount()):
            q = (self.t.item(r, 1).text() if self.t.item(r, 1) else "").strip()
            try:
                rate = float((self.t.item(r, 2).text() or "0").replace(",", ""))
            except (ValueError, AttributeError):
                rate = 0
            if q:
                rows.append((self.t.cellWidget(r, 0).currentText(), q, rate))
        self.s.set_hire_rates(rows)
        self.s.set_setting("min_wage_day", f"{self.minw.value():g}")
        self.s.set_setting("work_minutes_year", f"{self.mins.value():g}")
        self.accept()


# =========================================================== contracts
class ContractDialog(FormDialog):
    def __init__(self, parent, page: HirePage, cid=None, values=None):
        s = page.store
        self.s, self.page, self.cid = s, page, cid
        values = dict(s.contract(cid)) if cid else dict(values or {})
        fy = TD.fiscal_year(values.get("start") or TD.today())
        jobs = s.jobs()
        items = []
        for d in s.divisions():
            for b in s.hire_budget_items(fy, d["id"]):
                bal = s.balance(b["id"])
                items.append((b["id"], f"{d['name']} · {b['task']} · {b['name']} "
                                       f"({T('คงเหลือ')} {m(bal['available'])})"))
        if not items:
            items = [(b["id"], f"{b['task']} · {b['name']}") for b in s.budget_items(fy)
                     if b["category"] == "ค่าใช้สอย" and "จ้างเหมา" in b["name"]]
        if not values.get("budget_item_id") and values.get("division_id"):
            own = s.hire_budget_items(fy, s.top_division(values["division_id"])["id"])
            if own:
                values["budget_item_id"] = own[0]["id"]
        if values.get("job_id") and not values.get("monthly"):
            values["monthly"] = s.job_value(s.job(values["job_id"]))["monthly"]
        f = [("job_id", "งานที่จะจ้าง", "combo", [(j["id"], f"{j['division'] or ''} · {j['title']}") for j in jobs]),
             ("division_id", "กอง", "combo", [(d["id"], d["name"]) for d in s.divisions(all_levels=True)]),
             ("budget_item_id", f"รายการงบ ปี {fy}", "combo", items),
             ("person", "ผู้รับจ้าง (ชื่อ-สกุล)", "text"), ("id_card", "เลขประจำตัวประชาชน", "text"),
             ("address", "ที่อยู่", "text"), ("start", "วันเริ่มสัญญา", "date"), ("end", "วันสิ้นสุดสัญญา", "date"),
             ("monthly", "ค่าจ้างต่อเดือน", "money"), ("bank", "ธนาคาร", "text"), ("bank_branch", "สาขา", "text"),
             ("account_name", "ชื่อบัญชี", "text"), ("account_no", "เลขที่บัญชี", "text"),
             ("inspector", "ผู้ตรวจรับพัสดุ", "text"), ("contract_no", "เลขที่สัญญา (ว่าง = อัตโนมัติ)", "text"),
             ("note", "หมายเหตุ", "text")]
        super().__init__(parent, T("สัญญาจ้างเหมาบริการบุคคลธรรมดา"), f, values)
        self.total = QLabel()
        self.total.setTextFormat(Qt.RichText)
        self.add_row(self.total)
        for k in ("start", "end"):
            self.w[k][1].dateChanged.connect(self._total)
        self.w["monthly"][1].valueChanged.connect(self._total)
        self.w["job_id"][1].currentIndexChanged.connect(self._job)
        self._total()

    def _job(self):
        jid = self.w["job_id"][1].currentData()
        if not jid:
            return
        j = self.s.job(jid)
        dc = self.w["division_id"][1]
        dc.setCurrentIndex(max(0, dc.findData(j["division_id"])))
        self.w["monthly"][1].setValue(self.s.job_value(j)["monthly"])

    def _total(self, *_):
        v = self.values()
        try:
            plan = self.s.plan_months(v["start"], v["end"], v["monthly"])
        except ValueError as exc:
            self.total.setText(f"<span style='color:{RED}'>{exc}</span>")
            return
        tot = sum(x["amount"] for x in plan)
        part = [f"{H.month_name(x['month'])} {x['days']} {T('วัน')} = {m(x['amount'])}" for x in plan if not x["full"]]
        self.total.setText(f"{len(plan)} {T('งวด')} · {T('รวมตามสัญญา')} <b>{m(tot)}</b> {T('บาท')} "
                           f"({T('วันละ')} {m(v['monthly'] / 30)})" + (" · " + ", ".join(part) if part else ""))

    def accept(self):
        if _do(self, self.s.save_contract, self.values(), self.cid):
            super().accept()


class ContractTab(QWidget):
    HEAD = ["เลขที่สัญญา", "กอง", "งาน", "ผู้รับจ้าง", "เริ่ม", "สิ้นสุด", "ค่าจ้าง/เดือน", "ตามสัญญา",
            "จ่ายแล้ว", "สถานะ"]

    def __init__(self, page: HirePage):
        super().__init__()
        self.p = page
        lay = QVBoxLayout(self)
        sp = QSplitter(Qt.Vertical)
        self.t = table(self.HEAD, stretch=2)
        self.t.itemSelectionChanged.connect(self.show_months)
        self.t.doubleClicked.connect(lambda *_: self.edit())
        sp.addWidget(self.t)
        g = QGroupBox(T("งวดรายเดือน — ตรวจรับเฉพาะวันที่ส่งงานครบถ้วน (สัญญาข้อ 7)"))
        gl = QVBoxLayout(g)
        self.months = table(["งวดเดือน", "วันตามสัญญา", "วันส่งงานครบ", "จำนวนเงิน", "ตรวจรับเมื่อ",
                             "เบิกจ่าย", "หมายเหตุ"], stretch=6)
        gl.addWidget(self.months, 1)
        self.info = QLabel()
        self.info.setTextFormat(Qt.RichText)
        gl.addWidget(self.info)
        row, _ = _buttons(("ตรวจรับงวดที่เลือก", self.inspect, True), ("เบิกจ่ายงวดที่เลือก", self.pay),
                          (None, None), ("ใบตรวจรับ/ขอเบิกงวดนี้", self.print_month))
        gl.addLayout(row)
        sp.addWidget(g)
        sp.setSizes([px(330), px(330)])
        lay.addWidget(sp, 1)
        row, _ = _buttons(("สัญญาใหม่", self.new, True), ("แก้ไข", self.edit), ("ลงนามสัญญา", self.sign),
                          ("ยกเลิกสัญญา", self.cancel), (None, None), ("พิมพ์เอกสาร", self.print_menu))
        lay.addLayout(row)

    def refresh(self):
        s = self.p.store
        cs = s.contracts(self.p.fy.value(), self.p.did())
        cur = self.cid()
        rows = []
        for c in cs:
            total = s.contract_total(c["start"], c["end"], c["monthly"])
            rows.append([c["contract_no"], c["division"], c["job"], c["person"], TD.thai(c["start"]),
                         TD.thai(c["end"]), float(c["monthly"]), float(total),
                         float(s.paid(c["proc_id"]) if c["proc_id"] else 0), T(c["status"])])
        fill(self.t, rows, ids=[c["id"] for c in cs])
        colors = {"ร่าง": "#B45309", "ทำสัญญาแล้ว": "#1A5FA6", "สิ้นสุด": "#55657A", "ยกเลิก": RED}
        for r, c in enumerate(cs):
            self.t.item(r, 9).setForeground(QColor(colors.get(c["status"], "#000")))
            if c["id"] == cur:
                self.t.selectRow(r)
        self.show_months()

    def cid(self):
        return selected_id(self.t)

    def month(self):
        return selected_id(self.months)

    def show_months(self):
        s = self.p.store
        cid = self.cid()
        ms = s.months(cid) if cid else []
        fill(self.months, [[H.month_name(x["month"]), x["planned_days"], x["days"] if x["inspect_date"] else "",
                            float(x["amount"]), TD.thai(x["inspect_date"]), T("จ่ายแล้ว") if x["payment_id"] else "",
                            x["note"]] for x in ms], ids=[x["month"] for x in ms])
        for r, x in enumerate(ms):
            col = "#D3E8FB" if x["payment_id"] else ("#FDE3C8" if x["inspect_date"] else None)
            if col:
                for c in range(self.months.columnCount()):
                    self.months.item(r, c).setBackground(QColor(col))
        if not cid:
            self.info.setText(T("เลือกสัญญาด้านบน"))
            return
        c = s.contract(cid)
        b = s.balance(c["budget_item_id"])
        paid = sum(x["amount"] for x in ms if x["payment_id"])
        self.info.setText(f"{T('จ่ายแล้ว')} {m(paid)} · {T('งวดคงเหลือ')} {sum(1 for x in ms if not x['payment_id'])} · "
                          f"{T('งบของกองคงเหลือ')} <b>{m(b['available'])}</b> {T('บาท')} · "
                          f"<span style='color:{MUTED}'>{T('ส้มอ่อน = ตรวจรับแล้ว · ฟ้า = เบิกจ่ายแล้ว')}</span>")

    def new(self):
        fy = self.p.fy.value()
        start, end = TD.fiscal_range(fy)
        did = self.p.did()
        if ContractDialog(self, self.p, None, dict(division_id=did, start=str(start), end=str(end))).exec():
            self.p.changed()

    def edit(self):
        cid = self.cid()
        if not cid:
            return need_selection(self)
        if ContractDialog(self, self.p, cid).exec():
            self.p.changed()

    def sign(self):
        cid = self.cid()
        if not cid:
            return need_selection(self)
        c = self.p.store.contract(cid)
        dlg = FormDialog(self, T("ลงนามสัญญา"), [("date", "วันที่ลงนาม", "date")], dict(date=c["start"]))
        if dlg.exec() and _do(self, self.p.store.sign_contract, cid, dlg.values()["date"]) is not False:
            self.p.changed()

    def cancel(self):
        cid = self.cid()
        if cid and QMessageBox.question(self, PRODUCT_TH, T("ยกเลิกสัญญานี้? (งวดที่ยังไม่จ่ายคืนงบให้กอง)")) \
                == QMessageBox.Yes:
            _do(self, self.p.store.cancel_contract, cid)
            self.p.changed()

    def inspect(self):
        cid, mth = self.cid(), self.month()
        if not (cid and mth):
            return need_selection(self)
        x = self.p.store.one("SELECT * FROM hire_months WHERE contract_id=? AND month=?", (cid, mth))
        y, mo = (int(a) for a in mth.split("-"))
        last = TD.parse(f"{mth}-{calendar.monthrange(y, mo)[1]:02d}")
        dlg = FormDialog(self, T("ตรวจรับงาน") + " " + H.month_name(mth),
                         [("days", f"วันที่ส่งงานครบถ้วน (จาก {x['planned_days']} วัน)", "int"),
                          ("date", "วันที่ตรวจรับ", "date"), ("note", "หมายเหตุ", "text")],
                         dict(days=x["days"], date=x["inspect_date"] or str(min(TD.today(), last)), note=x["note"]))
        if dlg.exec():
            v = dlg.values()
            if _do(self, self.p.store.inspect_month, cid, mth, int(v["days"]), v["date"], v["note"]) is not None:
                self.p.changed()

    def pay(self):
        cid, mth = self.cid(), self.month()
        if not (cid and mth):
            return need_selection(self)
        dlg = FormDialog(self, T("เบิกจ่าย") + " " + H.month_name(mth),
                         [("date", "วันที่จ่าย", "date"), ("voucher", "เลขที่ใบสำคัญ/ฎีกา", "text")])
        if dlg.exec():
            v = dlg.values()
            if _do(self, self.p.store.pay_month, cid, mth, v["date"], v["voucher"]):
                self.p.changed()

    def print_month(self):
        cid, mth = self.cid(), self.month()
        if not (cid and mth):
            return need_selection(self)
        self.p.win.preview(HR.monthly_inspection(self.p.store, cid, mth))

    def print_menu(self):
        s, win, cid = self.p.store, self.p.win, self.cid()
        items = []
        if cid:
            c = s.contract(cid)
            items += [("รายงานขอจ้าง", lambda: win.preview(HR.hire_request(s, cid)))]
            if c["job_id"]:
                items += [("ขอบเขตของงาน (TOR)", lambda: win.preview(HR.tor(s, c["job_id"], contract=c))),
                          ("ราคากลาง แบบ บก.06", lambda: win.preview(HR.bk06(s, c["job_id"], c))),
                          ("บัญชีแสดงการคำนวณปริมาณงาน", lambda: win.preview(HR.workload_sheet(s, c["job_id"])))]
            items += [("สัญญาจ้างงานบริการ (แบบฉบับที่ 3)", lambda: win.preview(HR.contract_doc(s, cid))), (None, None)]
        fy, did = self.p.fy.value(), self.p.did()
        items.append(("ทะเบียนคุมสัญญาจ้างเหมาบุคคล", lambda: win.preview(HR.hire_register(s, fy, did))))
        _menu_at(self, items)


# ============================================================= summary
class SummaryTab(QWidget):
    def __init__(self, page: HirePage):
        super().__init__()
        self.p = page
        lay = QVBoxLayout(self)
        self.t = table(["กอง", "งบจ้างเหมาบุคคล (หลังโอน)", "จอง/ผูกพัน", "เบิกจ่ายแล้ว", "คงเหลือ", "สัญญา",
                        "ค่าจ้างต่อเดือน (ที่มีผล)"], stretch=0)
        self.t.doubleClicked.connect(self.open_division)
        lay.addWidget(self.t, 2)
        lab = QLabel(T("สัญญาที่จะสิ้นสุดภายใน 30 วัน"))
        lab.setObjectName("section")
        lay.addWidget(lab)
        self.soon = table(["เลขที่สัญญา", "กอง", "งาน", "ผู้รับจ้าง", "สิ้นสุด", "อีก (วัน)"], stretch=2)
        lay.addWidget(self.soon, 1)
        self.empty = QLabel()
        self.empty.setWordWrap(True)
        lay.addWidget(self.empty)
        row, _ = _buttons(("พิมพ์สรุปตามกอง", lambda: self.p.win.preview(HR.division_summary(self.p.store,
                                                                                               self.p.fy.value()))),
                          ("ทะเบียนคุมสัญญา", lambda: self.p.win.preview(HR.hire_register(self.p.store,
                                                                                          self.p.fy.value()))),
                          (None, None))
        lay.addLayout(row)

    def refresh(self):
        s = self.p.store
        fy = self.p.fy.value()
        rows = s.hire_summary(fy)
        data = [[x["division"]["name"], float(x["budget"]), float(x["committed"]), float(x["paid"]),
                 float(x["available"]), x["contracts"], float(x["monthly"])] for x in rows]
        if rows:
            data.append([T("รวม"), *[float(sum(x[k] for x in rows)) for k in ("budget", "committed", "paid", "available")],
                         sum(x["contracts"] for x in rows), float(sum(x["monthly"] for x in rows))])
        fill(self.t, data, ids=[x["division"]["id"] for x in rows] + ([None] if rows else []))
        for r, x in enumerate(rows):
            if x["budget"] and x["available"] < 0.1 * x["budget"]:
                self.t.item(r, 4).setForeground(QColor(RED))
        if rows:
            f = self.t.font()
            f.setBold(True)
            for c in range(self.t.columnCount()):
                self.t.item(len(rows), c).setFont(f)
        soon = s.ending_soon(30)
        today = TD.today()
        fill(self.soon, [[c["contract_no"], c["division"], c["job"], c["person"], TD.thai(c["end"]),
                          (TD.parse(c["end"]) - today).days] for c in soon], ids=[c["id"] for c in soon])
        if not s.divisions():
            self.empty.setText(T("ยังไม่มีโครงสร้างหน่วยงาน — ไปที่แท็บ «โครงสร้างหน่วยงาน» แล้วกด "
                                 "«โหลดโครงสร้าง อบต.ไม้ขาว» หรือ «เพิ่มกอง»"))
        elif not s.budget_items(fy):
            self.empty.setText(T(f"ยังไม่มีข้อบัญญัติปี {fy} — นำเข้าที่หน้า «งบประมาณ»"))
        else:
            self.empty.setText(T("ดับเบิลคลิกกองเพื่อดูสัญญาของกองนั้น · ตัวเลขแดง = งบคงเหลือน้อยกว่า 10 %"))

    def open_division(self, *_):
        did = selected_id(self.t)
        if did:
            i = self.p.div.findData(did)
            self.p.div.setCurrentIndex(i)
            self.p.tabs.setCurrentWidget(self.p.cons)


__all__ = ["HirePage"]
