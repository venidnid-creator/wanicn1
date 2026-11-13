# SPDX-License-Identifier: GPL-3.0-or-later
"""หน้าจองบประมาณ (ข้อบัญญัติ), จัดซื้อจัดจ้าง และสถิติ."""
from __future__ import annotations

import re

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from html import escape

from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QDialog,
                               QDialogButtonBox, QDoubleSpinBox, QFileDialog, QFormLayout,
                               QFrame, QGridLayout, QGroupBox, QHBoxLayout, QHeaderView,
                               QLabel, QLineEdit, QMenu, QMessageBox, QPlainTextEdit,
                               QProgressBar, QPushButton, QSpinBox, QSplitter, QTableWidget,
                               QTableWidgetItem, QTabWidget, QTextBrowser, QToolTip, QTreeWidget, QTreeWidgetItem,
                               QVBoxLayout, QWidget)

from . import PRODUCT_TH
from . import budget as B
from . import procurement as P
from . import reports as R
from . import thaidate as TD
from .i18n import T
from .widgets import (MUTED, NAVY, FormDialog, ThaiDateEdit, error, fill, need_selection,
                      selected_id, table)

RED, GREEN = "#C72B1E", "#0E7F4F"


def _page(title, hint=""):
    from .app import page
    return page(title, hint)


def _buttons(*specs):
    from .app import buttons
    return buttons(*specs)


def fy_spin(value=None):
    s = QSpinBox()
    s.setRange(2500, 2700)
    s.setValue(value or TD.fiscal_year(TD.today()))
    return s


def m(v) -> str:
    return f"{float(v or 0):,.2f}"


class MoneyCard(QFrame):
    def __init__(self, label):
        super().__init__()
        self.setObjectName("card")
        v = QVBoxLayout(self)
        self.val = QLabel("0.00")
        self.val.setObjectName("cardvalue")
        lab = QLabel(T(label))
        lab.setObjectName("cardlabel")
        v.addWidget(self.val)
        v.addWidget(lab)

    def set(self, value, color=None):
        self.val.setText(m(value))
        self.val.setStyleSheet(f"color:{color}" if color else "")


class BudgetBox(QGroupBox):
    """มีเงินเท่าไร — ครั้งนี้ — เหลือเท่าไร."""

    ROWS = [("budget", "งบประมาณหลังโอน"), ("used", "ใช้ไป/ผูกพัน/จองไว้ (รายการอื่น)"),
            ("available", "คงเหลือก่อนครั้งนี้"), ("this", "ครั้งนี้"), ("after", "คงเหลือหลังครั้งนี้")]

    def __init__(self):
        super().__init__(T("ตรวจสอบงบประมาณ"))
        g = QGridLayout(self)
        self.v = {}
        for i, (k, label) in enumerate(self.ROWS):
            g.addWidget(QLabel(T(label)), i, 0)
            lab = QLabel("-")
            lab.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            lab.setStyleSheet("font-weight:bold")
            g.addWidget(lab, i, 1)
            self.v[k] = lab
        self.bar = QProgressBar()
        self.bar.setTextVisible(True)
        g.addWidget(self.bar, len(self.ROWS), 0, 1, 2)
        self.path = QLabel("")
        self.path.setObjectName("hint")
        self.path.setWordWrap(True)
        g.addWidget(self.path, len(self.ROWS) + 1, 0, 1, 2)
        self.detail = QLabel("")
        self.detail.setWordWrap(True)
        self.detail.setTextFormat(Qt.RichText)
        self.detail.setStyleSheet("font-size:12pt; color:#33415C; background:#F7F4EC; padding:4px;"
                                  "border-radius:6px")
        g.addWidget(self.detail, len(self.ROWS) + 2, 0, 1, 2)

    def show_for(self, store, bid, this, exclude=None):
        if not bid:
            for lab in self.v.values():
                lab.setText("-")
            self.path.setText(T("ยังไม่ได้เลือกรายการงบประมาณ"))
            self.detail.setText("")
            self.bar.setValue(0)
            return None
        b = store.balance(bid, exclude_proc=exclude)
        it = store.budget_item(bid)
        after = b["available"] - this
        vals = dict(budget=b["budget"], used=b["paid"] + b["committed"] + b["reserved"],
                    available=b["available"], this=this, after=after)
        for k, v in vals.items():
            self.v[k].setText(m(v) + " " + T("บาท"))
        self.v["after"].setStyleSheet(f"font-weight:bold; color:{RED if after < 0 else GREEN}")
        used = vals["used"] + this
        self.bar.setValue(int(min(100, used / b["budget"] * 100)) if b["budget"] else 0)
        self.bar.setFormat(f"{T('ใช้')} %p%")
        self.path.setText(f"ข้อบัญญัติปี {it['fy']}: {it['plan']} › {it['task']} › {it['grp']} › "
                          f"{it['category']} › {it['type']}")
        det = (it["detail"] or "").strip()
        if det:
            short = det if len(det) <= 420 else det[:420] + "…"
            self.detail.setText(f"<b>{T('คำชี้แจง')}</b><br>" + escape(short).replace("\n", "<br>"))
            self.detail.setToolTip(det)
        else:
            self.detail.setText(f"<i>{T('ไม่มีคำชี้แจง')}</i>")
        return after


# ================================================================ budget
class BudgetPage(QWidget):
    COLS = ["รายการ", "ตามข้อบัญญัติ", "โอน/เพิ่มเติม", "งบหลังโอน", "จองเงิน", "ก่อหนี้ผูกพัน",
            "เบิกจ่ายแล้ว", "คงเหลือ", "% ใช้"]

    def __init__(self, win):
        super().__init__()
        self.win = win
        w, lay = _page("งบประมาณ", "ข้อบัญญัติงบประมาณรายจ่าย — แผนงาน › งาน › งบ › หมวด › ประเภท › รายการ "
                       "· คงเหลือ = งบหลังโอน − จองเงิน − ก่อหนี้ผูกพัน − เบิกจ่ายแล้ว")
        QVBoxLayout(self).addWidget(w)
        top = QHBoxLayout()
        top.addWidget(QLabel(T("ปีงบประมาณ")))
        self.fy = fy_spin()
        self.fy.valueChanged.connect(self.refresh)
        top.addWidget(self.fy)
        self.years = QComboBox()
        self.years.setToolTip(T("ข้อบัญญัติที่มีในโปรแกรม"))
        self.years.activated.connect(lambda i: self.fy.setValue(self.years.itemData(i)))
        top.addWidget(self.years)
        self.cards = {}
        for k in ("งบประมาณหลังโอน", "จองเงิน + ก่อหนี้ผูกพัน", "เบิกจ่ายแล้ว", "คงเหลือ"):
            self.cards[k] = MoneyCard(k)
            top.addWidget(self.cards[k], 1)
        lay.addLayout(top)
        orow = QHBoxLayout()
        self.ord = QLabel("")
        self.ord.setWordWrap(True)
        self.ord.setTextInteractionFlags(Qt.TextBrowserInteraction)
        self.ord.setOpenExternalLinks(True)
        orow.addWidget(self.ord, 1)
        ob = QPushButton(T("ข้อมูลข้อบัญญัติ…"))
        ob.clicked.connect(self.edit_ordinance)
        orow.addWidget(ob)
        lay.addLayout(orow)
        split = QSplitter(Qt.Horizontal)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels([T(c) for c in self.COLS])
        self.tree.setAlternatingRowColors(True)
        h = self.tree.header()
        h.setSectionResizeMode(QHeaderView.ResizeToContents)
        h.setSectionResizeMode(0, QHeaderView.Interactive)
        h.setStretchLastSection(False)
        self.tree.setColumnWidth(0, 380)
        self.tree.itemDoubleClicked.connect(lambda *_: self.edit())
        self.tree.currentItemChanged.connect(lambda *_: self.show_detail())
        split.addWidget(self.tree)
        self.info = QTextBrowser()
        self.info.setStyleSheet("background:white; border:1px solid #DCD6C8; border-radius:8px;")
        split.addWidget(self.info)
        split.setSizes([1100, 360])
        lay.addWidget(split, 1)
        row, _ = _buttons(("เพิ่มรายการ", self.add, True), ("แก้ไข", self.edit), ("ลบ", self.delete),
                          (None, None), ("โอนงบประมาณ", self.transfer), ("เพิ่ม/ลดงบประมาณ", self.change),
                          ("ประวัติการโอน", self.history), ("นำเข้าข้อบัญญัติ", self.import_),
                          ("คัดลอกจากปีก่อน", self.copy), ("รายงาน", self.report))
        lay.addLayout(row)

    def refresh(self):
        s = self.win.store
        fy = self.fy.value()
        self.years.blockSignals(True)
        self.years.clear()
        for y in s.ordinance_years():
            self.years.addItem(f"{T('ข้อบัญญัติปี')} {y}", y)
        self.years.setCurrentIndex(self.years.findData(fy))
        self.years.blockSignals(False)
        o = s.ordinance(fy)
        if o["items"]:
            src = f" · <a href='{escape(o['source'])}'>{T('ต้นฉบับ')}</a>" if o["source"] else ""
            self.ord.setText(f"<b>{escape(o['title'] or T('ข้อบัญญัติปี') + ' ' + str(fy))}</b>"
                             f"{' · ' + escape(o['agency']) if o['agency'] else ''} · {o['items']:,} "
                             f"{T('รายการ')} · {T('รวมตามข้อบัญญัติ')} {m(o['amount'])} {T('บาท')}{src}")
        else:
            self.ord.setText(f"<span style='color:{RED}'>ยังไม่มีข้อบัญญัติปีงบประมาณ {fy} — "
                             "กด «นำเข้าข้อบัญญัติ» หรือ «คัดลอกจากปีก่อน» แล้วแก้ไขให้ตรงข้อบัญญัติปีนี้ "
                             "(แต่ละปีโครงสร้างไม่จำเป็นต้องเหมือนกัน)</span>")
        self.tree.clear()
        self.info.setHtml("")
        rows = s.budget_summary(fy)
        tot = dict(budget=0, reserved=0, committed=0, paid=0, available=0)
        nodes = {}
        sums = {}

        def node(path):
            if path in nodes:
                return nodes[path]
            parent = node(path[:-1]) if len(path) > 1 else None
            it = QTreeWidgetItem([path[-1]])
            f = it.font(0)
            f.setBold(True)
            it.setFont(0, f)
            if parent is None:
                self.tree.addTopLevelItem(it)
            else:
                parent.addChild(it)
            nodes[path] = it
            sums[path] = [0.0] * 7
            return it

        for r in rows:
            b = r["item"]
            path = (b["plan"], b["task"], b["grp"], b["category"], b["type"])
            if b["type"] == b["name"]:          # ประเภทที่เป็นรายการเดียว — ไม่ต้องซ้อนอีกชั้น
                path = path[:4]
            parent = node(path)
            vals = [r["approved"], r["changes"], r["budget"], r["reserved"], r["committed"], r["paid"],
                    r["available"]]
            leaf = QTreeWidgetItem([b["name"]] + [m(v) for v in vals] + [self._pct(r)])
            leaf.setData(0, Qt.UserRole, b["id"])
            leaf.setToolTip(0, f"{b['type']} › {b['name']}" + (f"\n{b['note']}" if b["note"] else ""))
            self._style(leaf, r["available"])
            parent.addChild(leaf)
            for i in range(1, len(path) + 1):
                acc = sums[path[:i]]
                for j, v in enumerate(vals):
                    acc[j] += v
            for k in tot:
                tot[k] += r[k]
        for path, vals in sums.items():
            it = nodes[path]
            for j, v in enumerate(vals):
                it.setText(j + 1, m(v))
            used = vals[3] + vals[4] + vals[5]
            it.setText(8, f"{used / vals[2] * 100:.1f}" if vals[2] else "-")
            self._style(it, vals[6])
        self.tree.expandToDepth(3)
        self.cards["งบประมาณหลังโอน"].set(tot["budget"])
        self.cards["จองเงิน + ก่อหนี้ผูกพัน"].set(tot["reserved"] + tot["committed"])
        self.cards["เบิกจ่ายแล้ว"].set(tot["paid"])
        self.cards["คงเหลือ"].set(tot["available"], GREEN)

    @staticmethod
    def _pct(r):
        used = r["reserved"] + r["committed"] + r["paid"]
        return f"{used / r['budget'] * 100:.1f}" if r["budget"] else "-"

    def _style(self, it, available):
        for c in range(1, 9):
            it.setTextAlignment(c, Qt.AlignRight | Qt.AlignVCenter)
        it.setForeground(7, QColor(RED if available < 0 else GREEN))

    def current(self):
        it = self.tree.currentItem()
        return it.data(0, Qt.UserRole) if it else None

    def dialog(self, title, values):
        plans = [n for _, n in B.PLANS]
        dlg = FormDialog(self, title, [
            ("plan", "แผนงาน", "edit-combo", plans), ("task", "งาน", "edit-combo", B.TASKS),
            ("grp", "งบ", "edit-combo", B.GROUPS), ("category", "หมวด", "edit-combo", B.CATEGORIES),
            ("type", "ประเภท", "edit-combo", []), ("name", "รายการ/โครงการ", "multi"),
            ("amount", "จำนวนเงินตามข้อบัญญัติ (บาท)", "money"), ("detail", "คำชี้แจง", "multi"),
            ("note", "หมายเหตุ", "text")], values)
        grp, cat, typ = dlg.w["grp"][1], dlg.w["category"][1], dlg.w["type"][1]

        def on_cat():
            cur = typ.currentText() or values.get("type", "")
            typ.blockSignals(True)
            typ.clear()
            typ.addItems(B.STRUCTURE.get(grp.currentText(), {}).get(cat.currentText(), []))
            typ.setEditText(cur)
            typ.blockSignals(False)

        def on_grp():
            cur = cat.currentText() or values.get("category", "")
            cat.blockSignals(True)
            cat.clear()
            cat.addItems(list(B.STRUCTURE.get(grp.currentText(), {})) or B.CATEGORIES)
            if cur in [cat.itemText(i) for i in range(cat.count())] or grp.currentText() not in B.STRUCTURE:
                cat.setEditText(cur)
            cat.blockSignals(False)
            on_cat()

        grp.currentTextChanged.connect(on_grp)
        cat.currentTextChanged.connect(on_cat)
        on_grp()
        return dlg

    def add(self):
        cur = self.current()
        base = dict(self.win.store.budget_item(cur)) if cur else {}
        base.update(name="", amount=0, note="", detail="")
        dlg = self.dialog(T("เพิ่มรายการงบประมาณ"), base)
        if dlg.exec():
            try:
                self.win.store.save_budget_item(dict(dlg.values(), fy=self.fy.value()))
            except Exception as exc:  # noqa: BLE001
                return error(self, exc)
            self.refresh()

    def edit(self):
        bid = self.current()
        if not bid:
            return need_selection(self)
        dlg = self.dialog(T("แก้ไข"), dict(self.win.store.budget_item(bid)))
        if dlg.exec():
            try:
                self.win.store.save_budget_item(dlg.values(), bid)
            except Exception as exc:  # noqa: BLE001
                return error(self, exc)
            self.refresh()

    def delete(self):
        bid = self.current()
        if not bid:
            return need_selection(self)
        if QMessageBox.question(self, PRODUCT_TH, T("ลบรายการนี้?")) == QMessageBox.Yes:
            try:
                self.win.store.delete_budget_item(bid)
            except Exception as exc:  # noqa: BLE001
                return error(self, exc)
            self.refresh()

    def _items(self):
        return [(b["id"], f"{b['task']} › {b['type']} › {b['name'][:50]}  "
                 f"({T('คงเหลือ')} {m(self.win.store.balance(b['id'])['available'])})")
                for b in self.win.store.budget_items(self.fy.value())]

    def transfer(self):
        dlg = FormDialog(self, T("โอนงบประมาณ"), [
            ("src", "โอนลดจาก", "combo", self._items()), ("dst", "โอนเพิ่มให้", "combo", self._items()),
            ("amount", "จำนวนเงิน (บาท)", "money"), ("date", "วันที่", "date"),
            ("doc", "เลขที่คำสั่ง/บันทึก", "text"), ("note", "หมายเหตุ", "text")], dict(src=self.current()))
        if dlg.exec():
            v = dlg.values()
            try:
                self.win.store.transfer(v["src"], v["dst"], v["amount"], v["date"], v["doc"], v["note"])
            except Exception as exc:  # noqa: BLE001
                return error(self, exc)
            self.refresh()

    def change(self):
        dlg = FormDialog(self, T("เพิ่ม/ลดงบประมาณ"), [
            ("item", "รายการ", "combo", self._items()), ("kind", "ชนิด", "combo", B.CHANGE_KINDS[2:]),
            ("amount", "จำนวนเงิน (บาท)", "money"), ("date", "วันที่", "date"),
            ("doc", "เลขที่เอกสาร", "text"), ("note", "หมายเหตุ", "text")], dict(item=self.current()))
        if dlg.exec():
            v = dlg.values()
            try:
                self.win.store.change_budget(v["item"], v["kind"], v["amount"], v["date"], v["doc"], v["note"])
            except Exception as exc:  # noqa: BLE001
                return error(self, exc)
            self.refresh()

    def history(self):
        rows = self.win.store.budget_changes(fy=self.fy.value())
        d = QDialog(self)
        d.setWindowTitle(T("ประวัติการโอน"))
        d.resize(1100, 520)
        v = QVBoxLayout(d)
        t = table(["วันที่", "ชนิด", "รายการ", "จำนวนเงิน", "เลขที่เอกสาร", "หมายเหตุ"], stretch=2)
        fill(t, [[TD.thai(c["date"]), c["kind"], f"{c['type']} › {c['name']}", float(c["amount"]), c["doc_no"],
                  c["note"]] for c in rows], ids=[c["id"] for c in rows])
        v.addWidget(t)
        row, _ = _buttons(("ลบรายการที่เลือก", lambda: self._del_change(t, d)), (None, None),
                          ("ปิด", d.accept))
        v.addLayout(row)
        d.exec()
        self.refresh()

    def _del_change(self, t, d):
        cid = selected_id(t)
        if cid and QMessageBox.question(d, PRODUCT_TH, T("ลบรายการนี้?")) == QMessageBox.Yes:
            self.win.store.delete_change(cid)
            t.removeRow(t.currentRow())

    def show_detail(self):
        bid = self.current()
        it = self.tree.currentItem()
        if not it:
            return
        if not bid:
            self.info.setHtml(f"<h3>{escape(it.text(0))}</h3><p>{T('งบหลังโอน')} {it.text(3)} {T('บาท')}<br>"
                              f"{T('คงเหลือ')} {it.text(7)} {T('บาท')}</p>")
            return
        s = self.win.store
        b = s.budget_item(bid)
        bal = s.balance(bid)
        det = escape(b["detail"] or "").replace("\n", "<br>") or f"<i>{T('ไม่มีคำชี้แจง')}</i>"
        procs = s.q("SELECT number, title, status, amount, contract_amount FROM procurements "
                    "WHERE budget_item_id=? ORDER BY id", (bid,))
        plist = "".join(f"<li>{escape(p['number'])} {escape(p['title'][:50])} — {escape(p['status'])} "
                        f"{m(p['contract_amount'] or p['amount'])}</li>" for p in procs)
        self.info.setHtml(
            f"<p style='color:{MUTED}'>{T('ข้อบัญญัติปี')} {b['fy']} · {escape(b['plan'])} › {escape(b['task'])} › "
            f"{escape(b['grp'])} › {escape(b['category'])} › {escape(b['type'])}</p>"
            f"<h3>{escape(b['name'])}</h3>"
            f"<p>{T('ตามข้อบัญญัติ')} <b>{m(b['amount'])}</b> · {T('งบหลังโอน')} <b>{m(bal['budget'])}</b> · "
            f"{T('คงเหลือ')} <b style='color:{GREEN}'>{m(bal['available'])}</b> {T('บาท')}</p>"
            f"<p><b>{T('คำชี้แจง')}</b><br>{det}</p>"
            + (f"<p style='color:{MUTED}'>{escape(b['note'])}</p>" if b["note"] else "")
            + (f"<p><b>{T('การจัดซื้อจัดจ้างที่ใช้รายการนี้')}</b></p><ul>{plist}</ul>" if plist else ""))

    def edit_ordinance(self):
        fy = self.fy.value()
        o = self.win.store.ordinance(fy)
        dlg = FormDialog(self, f"{T('ข้อมูลข้อบัญญัติ…')} {fy}", [
            ("title", "ชื่อข้อบัญญัติ", "text"), ("agency", "หน่วยงาน", "text"),
            ("source", "ที่มา (ลิงก์/เลขที่ประกาศ)", "text"), ("total", "งบประมาณรายจ่ายทั้งสิ้น (บาท)", "money"),
            ("note", "หมายเหตุ", "multi")],
            dict(o, title=o["title"] or f"ข้อบัญญัติงบประมาณรายจ่ายประจำปีงบประมาณ พ.ศ. {fy}"))
        if dlg.exec():
            self.win.store.save_ordinance(fy, **dlg.values())
            self.refresh()

    def import_(self):
        menu = QMenu(self)
        for y in (2570, 2569):
            menu.addAction(f"{T('ข้อบัญญัติ อบต.ไม้ขาว ปี')} {y} ({T('ในชุดโปรแกรม')})",
                           lambda yy=y: self.import_maikhao(yy))
        menu.addSeparator()
        menu.addAction(T("จากตารางรายงานประมาณการรายจ่าย (.csv/.xlsx)…"), self.import_ordinance_file)
        menu.addAction(T("จากตารางทั่วไป 7 คอลัมน์ (.csv/.xlsx)…"), self.import_simple)
        menu.exec(self.cursor().pos())

    def _ordinance(self, rows, what, **meta):
        s = self.win.store
        years = [int(m_) for h in rows[0] for m_ in re.findall(r"ประมาณการ\s*(25\d\d)", str(h))]
        if not years:
            return error(self, ValueError("ไม่พบคอลัมน์ «ประมาณการ ปปปป» ในหัวตาราง"))
        fy = max(years)
        replace = False
        if s.budget_items(fy):
            ans = QMessageBox.question(
                self, PRODUCT_TH, f"มีงบประมาณปี {fy} อยู่แล้ว\n"
                "ใช่ = แทนที่ข้อบัญญัติปีนี้ทั้งหมด (รายการที่มีการจัดซื้ออ้างอิงจะลบไม่ได้) · ไม่ใช่ = เพิ่มต่อท้าย",
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel)
            if ans == QMessageBox.Cancel:
                return
            replace = ans == QMessageBox.Yes
        try:
            got = s.import_ordinance(rows, replace=replace, **meta)
        except Exception as exc:  # noqa: BLE001
            return error(self, exc)
        hist = ", ".join(f"{k} {y}" for k, y in sorted(got["history"], key=lambda x: x[1]))
        QMessageBox.information(self, PRODUCT_TH, f"{what}\n\nงบประมาณปี {got['fy']}: {got['budget']} รายการ "
                                f"(ใช้เฉพาะปีนี้)\nตัวเลขอ้างอิงสำหรับเปรียบเทียบหลายปี: {hist or '-'}")
        self.fy.setValue(got["fy"])
        self.refresh()

    def import_maikhao(self, year=2570):
        from pathlib import Path

        from .demo import ORDINANCE_SOURCES
        path = Path(B.__file__).resolve().parent / "data" / f"maikhao_{year}.csv"
        self._ordinance(B.read_table(path), f"นำเข้าข้อบัญญัติงบประมาณรายจ่ายประจำปี {year} "
                        "องค์การบริหารส่วนตำบลไม้ขาว อ.ถลาง จ.ภูเก็ต",
                        agency="องค์การบริหารส่วนตำบลไม้ขาว", source=ORDINANCE_SOURCES.get(year, ""))

    def import_ordinance_file(self):
        path, _ = QFileDialog.getOpenFileName(self, T("นำเข้าจากตาราง"), "", "ตาราง (*.xlsx *.csv)")
        if path:
            try:
                rows = B.read_table(path)
            except Exception as exc:  # noqa: BLE001
                return error(self, exc)
            self._ordinance(rows, T("นำเข้าแล้ว"))

    def import_simple(self):
        path, _ = QFileDialog.getOpenFileName(self, T("นำเข้าจากตาราง"), "",
                                              "ตาราง (*.xlsx *.csv)")
        if not path:
            return
        try:
            n = self.win.store.import_budget(self.fy.value(), B.read_table(path))
        except Exception as exc:  # noqa: BLE001
            return error(self, exc)
        QMessageBox.information(self, PRODUCT_TH, f"{T('นำเข้าแล้ว')} {n} {T('รายการ')}\n"
                                "(คอลัมน์: แผนงาน, งาน, งบ, หมวด, ประเภท, รายการ, จำนวนเงิน, หมายเหตุ)")
        self.refresh()

    def copy(self):
        fy = self.fy.value()
        if QMessageBox.question(self, PRODUCT_TH, f"คัดลอกโครงสร้างงบประมาณปี {fy - 1} มาเป็นปี {fy} "
                                "(รวมจำนวนเงิน — แก้ไขภายหลังได้)?") == QMessageBox.Yes:
            n = self.win.store.copy_budget_year(fy - 1, fy)
            QMessageBox.information(self, PRODUCT_TH, f"{T('คัดลอกแล้ว')} {n} {T('รายการ')}")
            self.refresh()

    def report(self):
        menu = QMenu(self)
        for label, level in (("ทุกรายการ", None), ("สรุปตามแผนงาน", "plan"), ("สรุปตามงาน", "task"),
                             ("สรุปตามงบ", "grp"), ("สรุปตามหมวด", "category"), ("สรุปตามประเภท", "type")):
            menu.addAction(T(label), lambda lv=level: self.win.preview(
                R.budget_status(self.win.store, self.fy.value(), lv)))
        menu.addSeparator()
        for label, level in (("เปรียบเทียบหลายปี ตามแผนงาน", "plan"), ("เปรียบเทียบหลายปี ตามหมวด", "category"),
                             ("เปรียบเทียบหลายปี ตามประเภท", "type")):
            menu.addAction(T(label), lambda lv=level: self.win.preview(R.budget_compare(self.win.store, lv)))
        menu.exec(self.cursor().pos())


# =========================================================== procurement
class LineTable(QTableWidget):
    """รายละเอียดพัสดุ: รายการ จำนวน หน่วย ราคา ลงทะเบียนเป็น ประเภท."""

    HEAD = ["รายการ", "จำนวน", "หน่วย", "ราคาต่อหน่วย", "จำนวนเงิน", "ลงทะเบียนเป็น", "ประเภท"]
    TARGETS = [("", "ไม่ลงทะเบียน"), ("asset", "ครุภัณฑ์"), ("material", "วัสดุ")]

    def __init__(self, store, on_change):
        super().__init__(0, len(self.HEAD))
        self.store = store
        self.on_change = on_change
        self.setHorizontalHeaderLabels([T(h) for h in self.HEAD])
        h = self.horizontalHeader()
        h.setSectionResizeMode(QHeaderView.ResizeToContents)
        h.setSectionResizeMode(0, QHeaderView.Stretch)
        for c, wd in ((5, 130), (6, 190)):
            h.setSectionResizeMode(c, QHeaderView.Fixed)
            self.setColumnWidth(c, wd)
        self.verticalHeader().setVisible(False)
        self.itemChanged.connect(self._changed)
        self._busy = False

    def add(self, name="", qty=1, unit="", price=0.0, target="", category_id=None):
        self._busy = True
        r = self.rowCount()
        self.insertRow(r)
        for c, v in enumerate([name, f"{qty:g}", unit, f"{price:,.2f}", ""]):
            it = QTableWidgetItem(v)
            if c in (1, 3, 4):
                it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            if c == 4:
                it.setFlags(it.flags() & ~Qt.ItemIsEditable)
            self.setItem(r, c, it)
        tc = QComboBox()
        for k, label in self.TARGETS:
            tc.addItem(T(label), k)
        tc.setCurrentIndex(max(0, tc.findData(target)))
        cc = QComboBox()
        self.setCellWidget(r, 5, tc)
        self.setCellWidget(r, 6, cc)
        tc.currentIndexChanged.connect(lambda *_: self._cats(tc, cc))
        self._cats(tc, cc, category_id)
        self._busy = False
        self._changed()

    def _cats(self, tc, cc, cid=None):
        cc.clear()
        kind = tc.currentData()
        if kind:
            for c in self.store.categories(kind):
                cc.addItem(f"{c['code']} {c['name']}", c["id"])
            if cid:
                cc.setCurrentIndex(max(0, cc.findData(cid)))
        cc.setEnabled(bool(kind))

    @staticmethod
    def _num(it):
        try:
            return float((it.text() if it else "0").replace(",", "") or 0)
        except ValueError:
            return 0.0

    def _changed(self, *_):
        if self._busy:
            return
        self._busy = True
        for r in range(self.rowCount()):
            amt = self._num(self.item(r, 1)) * self._num(self.item(r, 3))
            if self.item(r, 4):
                self.item(r, 4).setText(f"{amt:,.2f}")
        self._busy = False
        self.on_change()

    def total(self):
        return round(sum(self._num(self.item(r, 1)) * self._num(self.item(r, 3))
                         for r in range(self.rowCount())), 2)

    def values(self):
        out = []
        for r in range(self.rowCount()):
            name = self.item(r, 0).text().strip() if self.item(r, 0) else ""
            if not name:
                continue
            out.append(dict(name=name, qty=self._num(self.item(r, 1)), unit=self.item(r, 2).text().strip(),
                            unit_price=self._num(self.item(r, 3)), target=self.cellWidget(r, 5).currentData(),
                            category_id=self.cellWidget(r, 6).currentData()))
        return out


class ProcDialog(QDialog):
    def __init__(self, page, pid=None, kind="ซื้อ"):
        super().__init__(page)
        self.page = page
        self.store = s = page.win.store
        self.pid = pid
        p = dict(s.procurement(pid)) if pid else dict(kind=kind, vendor_vat=1)
        self.locked = bool(pid) and p.get("status") not in ("ขออนุมัติ", "อนุมัติแล้ว")
        self.setWindowTitle(f"{T('จัดซื้อจัดจ้าง')} — {p.get('number') or T('รายการใหม่')}")
        self.resize(1500, 860)
        outer = QHBoxLayout(self)
        left = QVBoxLayout()
        outer.addLayout(left, 3)
        f = QFormLayout()
        left.addLayout(f)
        self.kind = QComboBox()
        for k in P.KINDS:
            self.kind.addItem(T(k), k)
        self.kind.setCurrentIndex(P.KINDS.index(p.get("kind") or kind))
        self.date = ThaiDateEdit(p.get("date_request"))
        r1 = QHBoxLayout()
        r1.addWidget(self.kind)
        r1.addWidget(QLabel(T("วันที่")))
        r1.addWidget(self.date)
        self.number = QLineEdit(p.get("number") or "")
        self.number.setPlaceholderText(T("เว้นว่างให้โปรแกรมออกเลขให้"))
        r1.addWidget(QLabel(T("เลขที่")))
        r1.addWidget(self.number)
        f.addRow(T("ประเภทการจัดหา"), r1)
        self.title = QLineEdit(p.get("title") or "")
        f.addRow(T("รายการ/โครงการ"), self.title)
        self.reason = QPlainTextEdit(p.get("reason") or "")
        self.reason.setFixedHeight(56)
        f.addRow(T("เหตุผลและความจำเป็น"), self.reason)
        fy = page.fy.value()
        if not pid and TD.fiscal_year(self.date.iso()) != fy:      # a request for another year
            start, end = TD.fiscal_range(fy)
            self.date.set_iso(str(min(max(TD.today(), start), end)))
        self.bitem = QComboBox()
        self.bitem.setMinimumContentsLength(40)
        self.fy_label = QLabel("")
        self.fy_label.setObjectName("hint")
        self._fill_items(p.get("budget_item_id"))
        self.date.dateChanged.connect(lambda *_: self._fill_items(self.bitem.currentData(), keep_name=True))
        br = QHBoxLayout()
        br.addWidget(self.bitem, 1)
        br.addWidget(self.fy_label)
        f.addRow(T("งบประมาณจากข้อบัญญัติ"), br)
        self.lines = LineTable(s, self.update_box)
        left.addWidget(QLabel(f"<b>{T('รายละเอียดพัสดุ')}</b>"))
        left.addWidget(self.lines, 1)
        lr, _ = _buttons(("เพิ่มแถว", lambda: self.lines.add()), ("ลบแถว", self._del_line), (None, None))
        left.addLayout(lr)
        g = QFormLayout()
        self.amount = QDoubleSpinBox()
        self.amount.setRange(0, 1e12)
        self.amount.setDecimals(2)
        self.amount.setGroupSeparatorShown(True)
        self.amount.setValue(p.get("amount") or 0)
        self.auto = QCheckBox(T("ใช้ยอดรวมจากรายละเอียดพัสดุ"))
        self.auto.setChecked(not pid)
        ar = QHBoxLayout()
        ar.addWidget(self.amount, 1)
        ar.addWidget(self.auto)
        g.addRow(T("วงเงินที่จะจัดหา (รวม VAT)"), ar)
        self.median = QDoubleSpinBox()
        self.median.setRange(0, 1e12)
        self.median.setGroupSeparatorShown(True)
        self.median.setValue(p.get("median_price") or 0)
        g.addRow(T("ราคากลาง (บาท)"), self.median)
        self.method = QComboBox()
        self.method.addItems(P.METHODS)
        if p.get("method"):
            self.method.setCurrentText(p["method"])
        self.method_hint = QLabel("")
        self.method_hint.setObjectName("hint")
        mr = QHBoxLayout()
        mr.addWidget(self.method, 1)
        mr.addWidget(self.method_hint)
        g.addRow(T("วิธีจัดซื้อจัดจ้าง"), mr)
        self.due = ThaiDateEdit(p.get("due_date") or str(TD.today()))
        g.addRow(T("กำหนดเวลาที่ต้องการใช้/ส่งมอบ"), self.due)
        self.requester = QLineEdit(p.get("requester") or "")
        g.addRow(T("ผู้ขอ/หน่วยงานที่ขอ"), self.requester)
        self.committee = QLineEdit(p.get("committee") or "")
        g.addRow(T("ผู้ตรวจรับ/คณะกรรมการ"), self.committee)
        self.egp = QLineEdit(p.get("egp_no") or "")
        g.addRow(T("เลขที่โครงการ e-GP"), self.egp)
        self.rent_from = ThaiDateEdit(p.get("rent_from") or str(TD.today()))
        self.rent_to = ThaiDateEdit(p.get("rent_to") or str(TD.fiscal_range(fy)[1]))
        rr = QHBoxLayout()
        rr.addWidget(self.rent_from)
        rr.addWidget(QLabel(T("ถึง")))
        rr.addWidget(self.rent_to)
        self.rent_row = QWidget()
        self.rent_row.setLayout(rr)
        g.addRow(T("ระยะเวลาเช่า"), self.rent_row)
        self.exch = QComboBox()
        self.exch.addItem("—", None)
        for a in s.assets(include_disposed=False):
            self.exch.addItem(f"{a['number']} {a['name']}", a["id"])
        if p.get("exchange_asset_id"):
            self.exch.setCurrentIndex(max(0, self.exch.findData(p["exchange_asset_id"])))
        g.addRow(T("พัสดุที่นำไปแลกเปลี่ยน"), self.exch)
        self.note = QLineEdit(p.get("note") or "")
        g.addRow(T("หมายเหตุ"), self.note)
        # right: the money
        right = QVBoxLayout()
        outer.addLayout(right, 2)
        self.box = BudgetBox()
        right.addWidget(self.box)
        right.addLayout(g)
        self.warn = QLabel("")
        self.warn.setWordWrap(True)
        right.addWidget(self.warn)
        right.addStretch(1)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Ok).setText(T("บันทึก"))
        bb.button(QDialogButtonBox.Ok).setObjectName("primary")
        bb.button(QDialogButtonBox.Cancel).setText(T("ยกเลิก"))
        bb.accepted.connect(self.save)
        bb.rejected.connect(self.reject)
        right.addWidget(bb)
        for ln in (s.lines(pid) if pid else []):
            self.lines.add(ln["name"], ln["qty"], ln["unit"], ln["unit_price"], ln["target"], ln["category_id"])
        if not pid:
            self.lines.add()
        for sig in (self.amount.valueChanged, self.bitem.currentIndexChanged, self.auto.toggled,
                    self.kind.currentIndexChanged):
            sig.connect(self.update_box)
        if self.locked:
            for wdg in (self.kind, self.bitem, self.lines, self.amount, self.median, self.method, self.auto):
                wdg.setEnabled(False)
            self.warn.setText(T("ออกใบสั่ง/ทำสัญญาแล้ว — แก้ไขได้เฉพาะหมายเหตุ ผู้ตรวจรับ กำหนดส่ง และเลข e-GP"))
        self.update_box()

    def _fill_items(self, current=None, keep_name=False):
        """รายการงบประมาณของข้อบัญญัติปีเดียวกับวันที่ขอ (แต่ละปีใช้ข้อบัญญัติของปีนั้น)."""
        s = self.store
        fy = TD.fiscal_year(self.date.iso())
        old = s.budget_item(current) if current else None
        self.bitem.blockSignals(True)
        self.bitem.clear()
        self.bitem.addItem(T("— เลือกรายการงบประมาณ —"), None)
        for b in s.budget_items(fy, procurement_only=True):
            self.bitem.addItem(f"{b['task']} › {b['type']} › {b['name'][:60]}", b["id"])
            self.bitem.setItemData(self.bitem.count() - 1, b["detail"][:400] if b["detail"] else "",
                                   Qt.ToolTipRole)
        i = 0
        if old is not None:
            i = self.bitem.findData(old["id"])
            if i < 0 and keep_name:          # same item in the new year's ordinance, if it is there
                for b in s.budget_items(fy, procurement_only=True):
                    if (b["task"], b["type"], b["name"]) == (old["task"], old["type"], old["name"]):
                        i = self.bitem.findData(b["id"])
                        break
            if i < 0 and not keep_name and old["fy"] == fy:
                self.bitem.addItem(f"{old['task']} › {old['type']} › {old['name'][:60]}", old["id"])
                i = self.bitem.count() - 1
        self.bitem.setCurrentIndex(max(0, i))
        self.bitem.blockSignals(False)
        n = self.bitem.count() - 1
        self.fy_label.setText(f"{T('ข้อบัญญัติปี')} {fy}" + ("" if n else f" — {T('ยังไม่มีในโปรแกรม')}"))
        if hasattr(self, "box"):
            self.update_box()

    def _del_line(self):
        r = self.lines.currentRow()
        if r >= 0:
            self.lines.removeRow(r)
            self.update_box()

    def update_box(self, *_):
        if self.auto.isChecked():
            self.amount.blockSignals(True)
            self.amount.setValue(self.lines.total())
            self.amount.blockSignals(False)
        kind = self.kind.currentData()
        self.rent_row.setEnabled(kind == "เช่า")
        self.exch.setEnabled(kind == "แลกเปลี่ยน")
        limit = self.store.fnum("specific_limit", P.SPECIFIC_LIMIT)
        sug = P.suggest_method(self.amount.value(), limit)
        self.method_hint.setText(f"{T('แนะนำ')}: {sug.replace('วิธี', '')}")
        if not self.pid and not getattr(self, "_method_touched", False):
            self.method.blockSignals(True)
            self.method.setCurrentText(sug)
            self.method.blockSignals(False)
        after = self.box.show_for(self.store, self.bitem.currentData(), self.amount.value(), self.pid)
        if not self.locked:
            if after is not None and after < 0:
                self.warn.setText(f"<b style='color:{RED}'>{T('งบประมาณไม่พอ')} — {T('ขาด')} {m(-after)} {T('บาท')}</b>")
            elif self.method.currentText() == P.METHODS[0] and self.amount.value() > limit:
                self.warn.setText(f"<span style='color:{RED}'>วงเงินเกิน {limit:,.0f} บาท — "
                                  "วิธีเฉพาะเจาะจงใช้ได้เฉพาะกรณีตามมาตรา 56 (2) (ก)–(ฉ)</span>")
            else:
                self.warn.setText("")

    def save(self):
        if not self.bitem.currentData() and QMessageBox.question(
                self, PRODUCT_TH, T("ยังไม่ได้เลือกรายการงบประมาณ — บันทึกต่อหรือไม่?")) != QMessageBox.Yes:
            return
        kind = self.kind.currentData()
        d = dict(kind=kind, number=self.number.text().strip(), title=self.title.text().strip(),
                 reason=self.reason.toPlainText().strip(), budget_item_id=self.bitem.currentData(),
                 amount=self.amount.value(), median_price=self.median.value(),
                 method=self.method.currentText(), date_request=self.date.iso(), due_date=self.due.iso(),
                 requester=self.requester.text().strip(), committee=self.committee.text().strip(),
                 egp_no=self.egp.text().strip(), note=self.note.text().strip(),
                 rent_from=self.rent_from.iso() if kind == "เช่า" else None,
                 rent_to=self.rent_to.iso() if kind == "เช่า" else None,
                 exchange_asset_id=self.exch.currentData() if kind == "แลกเปลี่ยน" else None)
        if not self.pid:
            d["fy"] = TD.fiscal_year(d["date_request"])
        try:
            self.pid = self.store.save_procurement(d, None if self.locked else self.lines.values(), self.pid)
        except Exception as exc:  # noqa: BLE001
            return error(self, exc)
        self.accept()


class ProcPage(QWidget):
    HEAD = ["เลขที่", "วันที่ขอ", "ประเภท", "รายการ/โครงการ", "วิธี", "วงเงิน", "ผู้ขาย/ผู้รับจ้าง",
            "ตามใบสั่ง/สัญญา", "เบิกจ่ายแล้ว", "กำหนดส่ง", "สถานะ"]

    def __init__(self, win):
        super().__init__()
        self.win = win
        w, lay = _page("จัดซื้อจัดจ้าง", "ซื้อ · จ้าง · เช่า · แลกเปลี่ยน — ขออนุมัติ › อนุมัติ (จองเงิน) › "
                       "ใบสั่ง/สัญญา (ก่อหนี้ผูกพัน) › ตรวจรับ › เบิกจ่าย · ทุกขั้นตรวจยอดคงเหลือของข้อบัญญัติ")
        QVBoxLayout(self).addWidget(w)
        top = QHBoxLayout()
        top.addWidget(QLabel(T("ปีงบประมาณ")))
        self.fy = fy_spin()
        self.fy.valueChanged.connect(self.refresh)
        top.addWidget(self.fy)
        self.kind = QComboBox()
        self.kind.addItem(T("ทุกประเภท"), None)
        for k in P.KINDS:
            self.kind.addItem(T(k), k)
        self.status = QComboBox()
        self.status.addItem(T("ทุกสถานะ"), None)
        for k in P.STATUSES:
            self.status.addItem(T(k), k)
        self.search = QLineEdit()
        self.search.setPlaceholderText(T("ค้นหา…"))
        for wdg in (self.kind, self.status):
            wdg.currentIndexChanged.connect(self.refresh)
            top.addWidget(wdg)
        self.search.textChanged.connect(self.refresh)
        top.addWidget(self.search, 1)
        lay.addLayout(top)
        sp = QSplitter(Qt.Vertical)
        self.t = table(self.HEAD, stretch=3)
        self.t.itemSelectionChanged.connect(self.detail)
        self.t.doubleClicked.connect(lambda *_: self.edit())
        sp.addWidget(self.t)
        bottom = QWidget()
        bl = QHBoxLayout(bottom)
        bl.setContentsMargins(0, 0, 0, 0)
        self.box = BudgetBox()
        bl.addWidget(self.box, 2)
        self.pays = table(["วันที่", "เลขที่ใบสำคัญ", "จำนวนเงิน", "ภาษีหัก ณ ที่จ่าย", "ค่าปรับ", "จ่ายสุทธิ"],
                          stretch=1)
        pg = QGroupBox(T("การเบิกจ่าย"))
        QVBoxLayout(pg).addWidget(self.pays)
        bl.addWidget(pg, 3)
        sp.addWidget(bottom)
        sp.setSizes([440, 360])
        lay.addWidget(sp, 1)
        new = QPushButton(T("รายการใหม่"))
        new.setObjectName("primary")
        nm = QMenu(new)
        for k in P.KINDS:
            nm.addAction(T("ขอ" + k), lambda kk=k: self.new(kk))
        new.setMenu(nm)
        row, btns = _buttons(("แก้ไข", self.edit), ("ลบ", self.delete), (None, None),
                             ("อนุมัติ", self.approve), ("ออกใบสั่ง/ทำสัญญา", self.order),
                             ("ตรวจรับ", self.inspect), ("เบิกจ่ายเงิน", self.pay), ("ยกเลิก", self.cancel),
                             ("พิมพ์เอกสาร", self.print_menu))
        row.insertWidget(0, new)
        lay.addLayout(row)

    def refresh(self):
        s = self.win.store
        rows = s.procurements(self.fy.value(), self.kind.currentData(), self.status.currentData(),
                              self.search.text().strip())
        fill(self.t, [[p["number"], TD.thai(p["date_request"]), T(p["kind"]), p["title"],
                       (p["method"] or "").replace("วิธี", ""), float(p["amount"] or 0), p["vendor"],
                       float(p["contract_amount"] or 0), float(s.paid(p["id"])), TD.thai(p["due_date"]),
                       T(p["status"])] for p in rows], ids=[p["id"] for p in rows])
        colors = {"ขออนุมัติ": "#B45309", "อนุมัติแล้ว": "#1A5FA6", "ก่อหนี้ผูกพัน": "#6D28D9",
                  "ตรวจรับแล้ว": "#0E7F4F", "เบิกจ่ายแล้ว": "#55657A", "ยกเลิก": RED}
        for r, p in enumerate(rows):
            self.t.item(r, 10).setForeground(QColor(colors.get(p["status"], NAVY)))
        self.detail()

    def pid(self):
        return selected_id(self.t)

    def detail(self):
        pid = self.pid()
        s = self.win.store
        if not pid:
            self.box.show_for(s, None, 0)
            self.pays.setRowCount(0)
            return
        p = s.procurement(pid)
        self.box.show_for(s, p["budget_item_id"], 0 if p["status"] == "ยกเลิก" else
                          max(0.0, (p["contract_amount"] or p["amount"] or 0) - s.paid(pid))
                          if p["status"] != "เบิกจ่ายแล้ว" else 0.0, exclude=pid)
        pays = s.payments(pid)
        fill(self.pays, [[TD.thai(x["date"]), x["voucher_no"], float(x["amount"]), float(x["wht"]),
                          float(x["fine"]), float(x["net"])] for x in pays], ids=[x["id"] for x in pays])

    def new(self, kind):
        if ProcDialog(self, None, kind).exec():
            self.win.refresh()

    def edit(self):
        pid = self.pid()
        if not pid:
            return need_selection(self)
        if ProcDialog(self, pid).exec():
            self.win.refresh()

    def _do(self, fn, *a, **k):
        try:
            fn(*a, **k)
        except Exception as exc:  # noqa: BLE001
            error(self, exc)
            return False
        self.win.refresh()
        return True

    def delete(self):
        pid = self.pid()
        if pid and QMessageBox.question(self, PRODUCT_TH, T("ลบรายการนี้?")) == QMessageBox.Yes:
            self._do(self.win.store.delete_procurement, pid)

    def approve(self):
        pid = self.pid()
        if not pid:
            return need_selection(self)
        dlg = FormDialog(self, T("อนุมัติ"), [("date", "วันที่อนุมัติ", "date")])
        if dlg.exec():
            self._do(self.win.store.approve, pid, dlg.values()["date"])

    def order(self):
        pid = self.pid()
        if not pid:
            return need_selection(self)
        p = self.win.store.procurement(pid)
        ctype = P.CONTRACT_TYPES[2] if (p["amount"] or 0) > 100000 else P.CONTRACT_TYPES[0]
        dlg = FormDialog(self, T("ออกใบสั่ง/ทำสัญญา"), [
            ("vendor", "ผู้ขาย/ผู้รับจ้าง", "text"), ("tax", "เลขประจำตัวผู้เสียภาษี", "text"),
            ("vat", "จดทะเบียนภาษีมูลค่าเพิ่ม", "combo", [(1, "ใช่"), (0, "ไม่ใช่")]),
            ("ctype", "รูปแบบ", "combo", P.CONTRACT_TYPES), ("amount", "จำนวนเงินตามใบสั่ง/สัญญา", "money"),
            ("no", "เลขที่ใบสั่ง/สัญญา", "text"), ("date", "วันที่", "date"), ("due", "กำหนดส่งมอบ", "date"),
            ("egp", "เลขที่โครงการ e-GP", "text")],
            dict(vendor=p["vendor"], tax=p["vendor_tax_id"], vat=p["vendor_vat"], ctype=ctype,
                 amount=p["amount"], no=p["number"], due=p["due_date"], egp=p["egp_no"]))
        if dlg.exec():
            v = dlg.values()
            self._do(self.win.store.order, pid, v["vendor"], v["amount"], v["no"], v["date"], v["due"],
                     v["ctype"], v["egp"], v["vat"], v["tax"])

    def inspect(self):
        pid = self.pid()
        if not pid:
            return need_selection(self)
        s = self.win.store
        dlg = FormDialog(self, T("ตรวจรับ"), [
            ("date", "วันที่ตรวจรับ", "date"), ("fine", "ค่าปรับ (บาท)", "money"), ("note", "หมายเหตุ", "text")],
            dict(fine=s.fine_for(pid, TD.today())))
        dw, fw = dlg.w["date"][1], dlg.w["fine"][1]
        dw.dateChanged.connect(lambda *_: fw.setValue(s.fine_for(pid, dw.iso())))
        reg = QCheckBox(T("ลงทะเบียนครุภัณฑ์/รับวัสดุเข้าคลังตามรายการที่เลือกไว้"))
        reg.setChecked(True)
        dlg.layout().insertRow(3, reg)
        if dlg.exec():
            v = dlg.values()
            self._do(s.inspect_proc, pid, v["date"], v["note"], v["fine"], reg.isChecked())

    def pay(self):
        pid = self.pid()
        if not pid:
            return need_selection(self)
        s = self.win.store
        p = s.procurement(pid)
        left = round((p["contract_amount"] or p["amount"] or 0) - s.paid(pid), 2)
        dlg = FormDialog(self, T("เบิกจ่ายเงิน"), [("date", "วันที่", "date"), ("amount", "จำนวนเงิน (บาท)", "money"),
                                                ("voucher", "เลขที่ใบสำคัญ/ฎีกา", "text"), ("note", "หมายเหตุ", "text")],
                         dict(amount=left))
        info = QLabel()
        aw = dlg.w["amount"][1]

        def upd():
            tax = P.wht(aw.value(), bool(p["vendor_vat"]), s.fnum("wht_rate", 1) / 100, s.fnum("wht_min", P.WHT_MIN))
            taken = sum(x["fine"] for x in s.payments(pid))
            fine = max(0.0, (p["fine"] or 0) - taken)
            info.setText(f"{T('คงค้างตามใบสั่ง/สัญญา')} {m(left)} · {T('ภาษีหัก ณ ที่จ่าย')} {m(tax)} · "
                         f"{T('ค่าปรับ')} {m(fine)} · <b>{T('จ่ายสุทธิ')} {m(aw.value() - tax - fine)}</b>")
        aw.valueChanged.connect(upd)
        upd()
        dlg.layout().insertRow(4, info)
        if dlg.exec():
            v = dlg.values()
            self._do(s.pay, pid, v["amount"], v["date"], v["voucher"], v["note"])

    def cancel(self):
        pid = self.pid()
        if not pid:
            return need_selection(self)
        dlg = FormDialog(self, T("ยกเลิก"), [("reason", "เหตุผล", "text")])
        if dlg.exec():
            self._do(self.win.store.cancel, pid, dlg.values()["reason"])

    def print_menu(self):
        pid = self.pid()
        s = self.win.store
        menu = QMenu(self)
        if pid:
            p = s.procurement(pid)
            menu.addAction(T(f"รายงานขอ{p['kind']}"), lambda: self.win.preview(R.proc_request(s, pid)))
            if p["order_date"]:
                menu.addAction(T("ใบสั่ง/สัญญา"), lambda: self.win.preview(R.purchase_order(s, pid)))
            if p["inspect_date"]:
                menu.addAction(T("ใบตรวจรับพัสดุ"), lambda: self.win.preview(R.inspection_doc(s, pid)))
            menu.addSeparator()
        menu.addAction(T("ทะเบียนคุมการจัดซื้อจัดจ้าง"), lambda: self.win.preview(R.proc_register(s, self.fy.value())))
        menu.addAction(T("ทะเบียนคุมการเบิกจ่ายเงิน"), lambda: self.win.preview(R.payment_register(s, self.fy.value())))
        menu.exec(self.cursor().pos())


# ============================================================ statistics
SERIES = [("requested", "วงเงินที่ขอ", "#2A78D6"), ("committed", "ก่อหนี้ผูกพัน", "#EB6834"),
          ("paid", "เบิกจ่ายแล้ว", "#1BAF7A")]


class BarChart(QWidget):
    """Grouped bars, one axis, legend, hover tooltip — drawn with QPainter."""

    def __init__(self):
        super().__init__()
        self.rows = []
        self.setMinimumHeight(300)
        self.setMouseTracking(True)
        self._hits = []

    def set_rows(self, rows):
        self.rows = rows
        self.update()

    @staticmethod
    def _nice(v):
        if v <= 0:
            return 1.0
        import math
        e = 10 ** math.floor(math.log10(v))
        for k in (1, 2, 2.5, 5, 10):
            if v <= k * e:
                return k * e
        return 10 * e

    def paintEvent(self, _):  # noqa: N802 (Qt)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor("#FCFCFB"))
        f = QFont(self.font())
        f.setPointSize(11)
        p.setFont(f)
        W, H = self.width(), self.height()
        left, right, top, bottom = 96, 16, 40, 34
        x = left
        for _, label, color in SERIES:       # legend
            p.setBrush(QColor(color))
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(QRectF(x, 12, 14, 14), 3, 3)
            p.setPen(QColor("#0B0B0B"))
            p.drawText(QPointF(x + 20, 24), T(label))
            x += 30 + p.fontMetrics().horizontalAdvance(T(label)) + 18
        self._hits = []
        if not self.rows:
            return
        vmax = self._nice(max(max(r[k] for k, _, _ in SERIES) for r in self.rows))
        ph = H - top - bottom
        pw = W - left - right
        p.setPen(QPen(QColor("#E4E2DC"), 1))
        for i in range(5):
            y = top + ph - ph * i / 4
            p.drawLine(QPointF(left, y), QPointF(W - right, y))
            p.setPen(QColor("#52514E"))
            p.drawText(QRectF(0, y - 10, left - 8, 20), Qt.AlignRight | Qt.AlignVCenter, f"{vmax * i / 4:,.0f}")
            p.setPen(QPen(QColor("#E4E2DC"), 1))
        n = len(self.rows)
        slot = pw / n
        bw = max(2.0, min(28.0, (slot * 0.8 - 4) / 3))
        step = max(1, int(n / 16) + (1 if n > 16 else 0))
        for i, r in enumerate(self.rows):
            x0 = left + i * slot + (slot - (bw * 3 + 4)) / 2
            for j, (k, label, color) in enumerate(SERIES):
                h = ph * r[k] / vmax
                rect = QRectF(x0 + j * (bw + 2), top + ph - h, bw, h)
                if h > 0:
                    path = QPainterPath()
                    rad = min(4.0, bw / 2, h)
                    path.addRoundedRect(rect.adjusted(0, 0, 0, rad), rad, rad)
                    p.save()
                    p.setClipRect(QRectF(rect.left(), rect.top(), rect.width(), h))
                    p.fillPath(path, QColor(color))
                    p.restore()
                self._hits.append((QRectF(x0 + j * (bw + 2) - 1, top, bw + 2, ph), r, label, r[k]))
            if i % step == 0:
                p.setPen(QColor("#52514E"))
                p.drawText(QRectF(left + i * slot - 20, top + ph + 4, slot + 40, 22), Qt.AlignHCenter, r["label"])
        p.setPen(QPen(QColor("#8A8984"), 1))
        p.drawLine(QPointF(left, top + ph), QPointF(W - right, top + ph))

    def mouseMoveEvent(self, e):  # noqa: N802 (Qt)
        for rect, r, label, v in self._hits:
            if rect.contains(e.position()):
                QToolTip.showText(e.globalPosition().toPoint(),
                                  f"<b>{r['label']}</b><br>{T(label)}: {v:,.2f} {T('บาท')}<br>"
                                  f"{T('จำนวนรายการขอ')}: {r['count']}", self)
                return
        QToolTip.hideText()


class StatsPage(QWidget):
    MODES = [("day", "รายวัน"), ("month", "รายเดือน"), ("year", "รายปี (หลายปี)")]

    def __init__(self, win):
        super().__init__()
        self.win = win
        w, lay = _page("สถิติ", "สถิติการจัดซื้อจัดจ้างและการเบิกจ่าย รายวัน รายเดือน รายปี เทียบได้หลายปี")
        QVBoxLayout(self).addWidget(w)
        top = QHBoxLayout()
        self.mode = QComboBox()
        for k, label in self.MODES:
            self.mode.addItem(T(label), k)
        self.mode.setCurrentIndex(1)
        top.addWidget(self.mode)
        self.month = QComboBox()
        for i, name in enumerate(TD.MONTHS):
            self.month.addItem(name, i + 1)
        self.month.setCurrentIndex(TD.today().month - 1)
        self.year = QSpinBox()
        self.year.setRange(2500, 2700)
        self.year.setValue(TD.today().year + 543)
        self.fy = fy_spin()
        self.fy_from = fy_spin(TD.fiscal_year(TD.today()) - 4)
        self.lab_month = QLabel(T("เดือน"))
        self.lab_fy = QLabel(T("ปีงบประมาณ"))
        self.lab_to = QLabel(T("ถึง"))
        for wdg in (self.lab_month, self.month, self.year, self.lab_fy, self.fy_from, self.lab_to, self.fy):
            top.addWidget(wdg)
        top.addStretch(1)
        row, _ = _buttons(("พิมพ์ PDF", self.pdf), ("ส่งออกตาราง", self.xlsx))
        top.addLayout(row)
        lay.addLayout(top)
        for sig in (self.mode.currentIndexChanged, self.month.currentIndexChanged, self.year.valueChanged,
                    self.fy.valueChanged, self.fy_from.valueChanged):
            sig.connect(self.refresh)
        self.cards = {}
        cr = QHBoxLayout()
        for k in ("จำนวนรายการขอ", "วงเงินที่ขอ", "ก่อหนี้ผูกพัน", "เบิกจ่ายแล้ว"):
            self.cards[k] = MoneyCard(k)
            cr.addWidget(self.cards[k])
        lay.addLayout(cr)
        sp = QSplitter(Qt.Vertical)
        self.chart = BarChart()
        sp.addWidget(self.chart)
        tabs = QWidget()
        tl = QHBoxLayout(tabs)
        tl.setContentsMargins(0, 0, 0, 0)
        self.t = table(["ช่วงเวลา", "จำนวน", "วงเงินที่ขอ", "ก่อหนี้ผูกพัน", "เบิกจ่ายแล้ว"], stretch=0)
        tl.addWidget(self.t, 2)
        self.br = {}
        tabs2 = QTabWidget()
        for key, label in (("method", "ตามวิธี"), ("kind", "ตามประเภท"), ("category", "ตามหมวด"),
                           ("vendor", "ตามผู้ขาย/ผู้รับจ้าง")):
            bt = table([label, "จำนวน", "วงเงินที่ขอ", "ก่อหนี้ผูกพัน", "เบิกจ่ายแล้ว"], stretch=0)
            tabs2.addTab(bt, T(label))
            self.br[key] = bt
        tl.addWidget(tabs2, 3)
        sp.addWidget(tabs)
        sp.setSizes([380, 300])
        lay.addWidget(sp, 1)
        self.rows = []

    def refresh(self):
        s = self.win.store
        mode = self.mode.currentData()
        for wdg in (self.lab_month, self.month, self.year):
            wdg.setVisible(mode == "day")
        for wdg in (self.lab_fy, self.fy):
            wdg.setVisible(mode != "day")
        for wdg in (self.fy_from, self.lab_to):
            wdg.setVisible(mode == "year")
        if mode == "day":
            self.rows = s.stats("day", year=self.year.value() - 543, month=self.month.currentData())
            f0 = f1 = TD.fiscal_year(f"{self.year.value() - 543}-{self.month.currentData():02d}-01")
            self.sub = f"{T('เดือน')} {self.month.currentText()} {self.year.value()}"
        elif mode == "month":
            self.rows = s.stats("month", fy=self.fy.value())
            f0 = f1 = self.fy.value()
            self.sub = f"{T('ปีงบประมาณ')} {self.fy.value()}"
        else:
            f0, f1 = sorted((self.fy_from.value(), self.fy.value()))
            self.rows = s.stats("year", fy_from=f0, fy_to=f1)
            self.sub = f"{T('ปีงบประมาณ')} {f0}–{f1}"
        self.chart.set_rows(self.rows)
        fill(self.t, [[r["label"], r["count"], float(r["requested"]), float(r["committed"]), float(r["paid"])]
                      for r in self.rows])
        self.cards["จำนวนรายการขอ"].val.setText(f"{sum(r['count'] for r in self.rows):,}")
        self.cards["วงเงินที่ขอ"].set(sum(r["requested"] for r in self.rows))
        self.cards["ก่อหนี้ผูกพัน"].set(sum(r["committed"] for r in self.rows))
        self.cards["เบิกจ่ายแล้ว"].set(sum(r["paid"] for r in self.rows))
        for key, bt in self.br.items():
            rows = s.breakdown(f0, f1, key)
            fill(bt, [[(T(x["label"]) or "-").replace("วิธี", ""), x["count"], float(x["amount"]),
                       float(x["committed"]), float(x["paid"])] for x in rows])

    def report(self):
        mode = dict(self.MODES)[self.mode.currentData()]
        return R.stats_report(self.win.store, self.rows, f"สถิติการจัดซื้อจัดจ้าง{mode}", self.sub)

    def pdf(self):
        self.win.preview(self.report())

    def xlsx(self):
        from .app import save_report
        save_report(self, self.report(), "xlsx")


__all__ = ["BudgetPage", "ProcPage", "StatsPage", "MUTED", "QAbstractItemView"]
