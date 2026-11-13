# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2569 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ)
"""หน้าต่างหลักของ «พัสดุเวนิช» (VENIT SUPPLY)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtCore import QSettings, Qt, QUrl
from PySide6.QtGui import QAction, QDesktopServices, QGuiApplication, QIcon, QPixmap
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QFileDialog,
                               QFormLayout, QFrame, QGridLayout, QGroupBox,
                               QHBoxLayout, QLabel, QLineEdit, QListWidget,
                               QListWidgetItem, QMainWindow, QMessageBox,
                               QPushButton, QScrollArea, QSpinBox, QSplitter, QStackedWidget,
                               QTextBrowser, QVBoxLayout, QWidget)

from . import DEVELOPER, PRODUCT_EN, PRODUCT_TH, QUALIFICATION, __version__
from . import db as DB
from . import i18n
from . import reports as R
from . import thaidate as TD
from .i18n import T
from .widgets import (NAVY, ORANGE, FormDialog, fit_to_screen, make_style, pt, px, scrolled, error, fill, need_selection,
                      selected_id, table)

FREE_USE = "โปรแกรมใช้ได้ฟรี ไม่มีค่าลิขสิทธิ์"
SUPPORT = "สนใจสนับสนุนผู้พัฒนา สามารถทำได้ที่"
BANK = "ธนาคารกรุงศรีอยุธยา สาขาโลตัส ถลาง ภูเก็ต"
ACCOUNT_NAME = "นายเวนิช ธัมมะวงษ์"
ACCOUNT_NO = "666-1-32472-1"
ACCOUNT_TYPE = "บัญชีออมทรัพย์"
CONTACT_PHONE = "093-5838348"
CONTACT_LINE = "https://line.me/ti/p/E-p-C9tCEx"


def asset_path(name) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return base / "assets" / name


def default_db() -> Path:
    docs = Path.home() / "Documents"
    folder = (docs if docs.exists() else Path.home()) / "VenitSupply"
    folder.mkdir(parents=True, exist_ok=True)
    return folder / "พัสดุ.vsdb"


def page(title, hint=""):
    w = QWidget()
    w.setObjectName("page")
    lay = QVBoxLayout(w)
    lay.setContentsMargins(22, 16, 22, 16)
    t = QLabel(T(title))
    t.setObjectName("title")
    lay.addWidget(t)
    if hint:
        h = QLabel(T(hint))
        h.setObjectName("hint")
        h.setWordWrap(True)
        lay.addWidget(h)
    return w, lay


def buttons(*specs):
    row = QHBoxLayout()
    out = []
    for text, fn, *primary in specs:
        if text is None:
            row.addStretch(1)
            continue
        b = QPushButton(T(text))
        if primary:
            b.setObjectName("primary")
        b.clicked.connect(fn)
        row.addWidget(b)
        out.append(b)
    return row, out


def save_report(parent, rep: R.Report, kind="pdf"):
    ext = "pdf" if kind == "pdf" else "xlsx"
    name = rep.title.replace(" ", "_") + "." + ext
    filt = "PDF (*.pdf)" if kind == "pdf" else "ตารางคำนวณ (*.xlsx)"
    path, _ = QFileDialog.getSaveFileName(parent, T("บันทึก"), str(default_db().parent / name), filt)
    if not path:
        return None
    try:
        (R.to_pdf if kind == "pdf" else R.to_xlsx)(rep, path)
    except Exception as exc:  # noqa: BLE001
        error(parent, exc)
        return None
    QDesktopServices.openUrl(QUrl.fromLocalFile(path))
    return path


# =================================================================== pages
class HomePage(QWidget):
    def __init__(self, win):
        super().__init__()
        self.win = win
        w, lay = page("หน้าหลัก")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(w)
        self.sub = QLabel()
        self.sub.setObjectName("hint")
        lay.addWidget(self.sub)
        body = QHBoxLayout()
        lay.addLayout(body, 1)
        left = QVBoxLayout()
        body.addLayout(left, 3)
        self.grid = QGridLayout()
        left.addLayout(self.grid)
        self.cards = {}
        keys = ["งบประมาณปีนี้", "จองเงิน + ก่อหนี้ผูกพัน", "เบิกจ่ายแล้ว", "งบประมาณคงเหลือ",
                "ครุภัณฑ์ที่ใช้อยู่", "มูลค่าครุภัณฑ์", "มูลค่าสุทธิ", "ค่าเสื่อมปีนี้",
                "รายการวัสดุ", "มูลค่าวัสดุคงเหลือ", "ยืมอยู่", "ตรวจแล้ว"]
        self.cardlabels = {}
        for i, k in enumerate(keys):
            f = QFrame()
            f.setObjectName("card")
            v = QVBoxLayout(f)
            val = QLabel("0")
            val.setObjectName("cardvalue")
            lab = QLabel(T(k))
            lab.setObjectName("cardlabel")
            v.addWidget(val)
            v.addWidget(lab)
            self.grid.addWidget(f, i // 4, i % 4)
            self.cards[k] = val
            self.cardlabels[k] = lab
        lists = QHBoxLayout()
        left.addLayout(lists, 1)
        g1 = QGroupBox(T("วัสดุต่ำกว่าจุดสั่งซื้อ"))
        self.low = QListWidget()
        self.low.setWordWrap(True)
        QVBoxLayout(g1).addWidget(self.low)
        g2 = QGroupBox(T("เกินกำหนดคืน"))
        self.over = QListWidget()
        self.over.setWordWrap(True)
        QVBoxLayout(g2).addWidget(self.over)
        g3 = QGroupBox(T("สถานะครุภัณฑ์"))
        self.status = QListWidget()
        QVBoxLayout(g3).addWidget(self.status)
        for g in (g1, g2, g3):
            lists.addWidget(g)
        dev = QScrollArea()
        dev.setWidgetResizable(True)
        dev.setFrameShape(QFrame.NoFrame)
        dev.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        dev.setWidget(self.developer_panel())
        dev.setFixedWidth(px(350))
        body.addWidget(dev, 0)

    def developer_panel(self):
        f = QFrame()
        f.setObjectName("card")
        f.setFixedWidth(px(330))
        v = QVBoxLayout(f)
        v.setAlignment(Qt.AlignTop)
        photo = QLabel()
        pm = QPixmap(str(asset_path("developer.jpg")))
        if not pm.isNull():
            photo.setPixmap(pm.scaledToWidth(px(110), Qt.SmoothTransformation))
        v.addWidget(photo, 0, Qt.AlignHCenter)
        name = QLabel(f"<b>{DEVELOPER}</b><br>{QUALIFICATION}")
        name.setAlignment(Qt.AlignCenter)
        v.addWidget(name)
        free = QLabel(f"<b style='color:{ORANGE}'>{T(FREE_USE)}</b>")
        free.setAlignment(Qt.AlignCenter)
        free.setWordWrap(True)
        v.addWidget(free)
        c = QLabel(f"{T('ติดต่อผู้พัฒนาระบบ')}<br>โทร {CONTACT_PHONE}")
        c.setAlignment(Qt.AlignCenter)
        v.addWidget(c)
        qr = QLabel()
        q = QPixmap(str(asset_path("contact-qr.png")))
        if not q.isNull():
            qr.setPixmap(q.scaledToWidth(px(96), Qt.SmoothTransformation))
        qr.setCursor(Qt.PointingHandCursor)
        qr.mousePressEvent = lambda e: QDesktopServices.openUrl(QUrl(CONTACT_LINE))
        v.addWidget(qr, 0, Qt.AlignHCenter)
        ql = QLabel(T("สแกนเพิ่มเพื่อน LINE"))
        ql.setObjectName("hint")
        ql.setAlignment(Qt.AlignCenter)
        v.addWidget(ql)
        bank = QLabel(f"<span style='font-size:{pt(12)}pt'>{T(SUPPORT)}<br>{BANK}<br>{ACCOUNT_TYPE} "
                      f"{ACCOUNT_NAME}</span><br>"
                      f"<b style='font-size:{pt(17)}pt; color:{NAVY}'>{ACCOUNT_NO}</b>")
        bank.setAlignment(Qt.AlignCenter)
        bank.setWordWrap(True)
        v.addWidget(bank)
        cp = QPushButton(T("คัดลอกเลขบัญชี"))

        def copy():
            QGuiApplication.clipboard().setText(ACCOUNT_NO.replace("-", ""))
            cp.setText(T("คัดลอกแล้ว"))
        cp.clicked.connect(copy)
        v.addWidget(cp)
        return f

    def refresh(self):
        s = self.win.store.summary()
        self.sub.setText(f"{self.win.store.setting('org_name') or ''}   ·   "
                         f"{T('ปีงบประมาณ')} {s['fy']}   ·   {T('ไฟล์ฐานข้อมูล')}: {Path(self.win.store.path).name}")
        vals = {"งบประมาณปีนี้": f"{s['b_budget']:,.2f}", "จองเงิน + ก่อหนี้ผูกพัน": f"{s['b_bound']:,.2f}",
                "เบิกจ่ายแล้ว": f"{s['b_paid']:,.2f}", "งบประมาณคงเหลือ": f"{s['b_left']:,.2f}",
                "ครุภัณฑ์ที่ใช้อยู่": f"{s['assets']:,}", "มูลค่าครุภัณฑ์": f"{s['asset_value']:,.2f}",
                "มูลค่าสุทธิ": f"{s['book_value']:,.2f}", "ค่าเสื่อมปีนี้": f"{s['dep_year']:,.2f}",
                "รายการวัสดุ": f"{s['materials']:,}", "มูลค่าวัสดุคงเหลือ": f"{s['material_value']:,.2f}",
                "ยืมอยู่": f"{s['loans_open']:,}  ({T('เกินกำหนดคืน')} {s['overdue']})",
                "ตรวจแล้ว": f"{s['inspected']:,} / {s['to_inspect']:,}"}
        self.cardlabels["ตรวจแล้ว"].setText(f"{T('ตรวจแล้ว')} ({T('ปีงบประมาณ')} {s['inspect_fy']})")
        for k, v in vals.items():
            self.cards[k].setText(v)
        self.low.clear()
        for m in s["low_stock"]:
            self.low.addItem(f"{m['code']} {m['name']} — {T('คงเหลือ')} {R.qty(m['qty'])} {m['unit']}")
        if not s["low_stock"]:
            self.low.addItem(T("ไม่มี"))
        self.over.clear()
        for ln in self.win.store.overdue():
            self.over.addItem(f"{ln['number']} {ln['asset_name']} — {ln['borrower']} "
                              f"({T('กำหนดคืน')} {TD.thai(ln['due_date'])})")
        if not self.over.count():
            self.over.addItem(T("ไม่มี"))
        self.status.clear()
        for k, n in s["by_status"].items():
            self.status.addItem(f"{T(k)}: {n:,}")


class AssetPage(QWidget):
    HEAD = ["เลขรหัสครุภัณฑ์", "รายการ ", "ประเภท", "ยี่ห้อ", "วันที่ได้มา", "ราคาต่อหน่วย (บาท)",
            "หน่วยงาน", "สถานที่ตั้ง", "ผู้รับผิดชอบ", "สถานะ"]

    def __init__(self, win):
        super().__init__()
        self.win = win
        w, lay = page("ครุภัณฑ์", "ทะเบียนครุภัณฑ์ — เลขรหัส ประวัติ ผู้รับผิดชอบ และค่าเสื่อมราคา "
                      "(ราคาต่อหน่วยตั้งแต่เกณฑ์ที่ตั้งไว้ คิดค่าเสื่อมแบบเส้นตรง)")
        QVBoxLayout(self).addWidget(w)
        top = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText(T("ค้นหา…"))
        self.search.textChanged.connect(self.refresh)
        self.filter = QComboBox()
        self.filter.addItem(T("ทุกสถานะ"), None)
        for s in DB.STATUSES:
            self.filter.addItem(T(s), s)
        self.filter.currentIndexChanged.connect(self.refresh)
        top.addWidget(self.search, 1)
        top.addWidget(self.filter)
        lay.addLayout(top)
        self.t = table(self.HEAD, stretch=1)
        self.t.doubleClicked.connect(self.edit)
        lay.addWidget(self.t, 1)
        row, _ = buttons(("เพิ่ม", self.add, True), ("แก้ไข", self.edit), ("ลบ", self.delete),
                         (None, None), ("ทะเบียนคุม", self.card), ("ยืมครุภัณฑ์", self.lend),
                         ("จำหน่าย", self.dispose), ("ส่งออกตาราง", self.export))
        lay.addLayout(row)

    def refresh(self):
        rows = self.win.store.assets(self.search.text().strip(), self.filter.currentData())
        fill(self.t, [[a["number"], a["name"], a["category"], " ".join(
            x for x in (a["brand"], a["model"]) if x), TD.thai(a["acquire_date"]), float(a["price"] or 0),
            a["department"], a["location"], a["custodian"], T(a["status"])] for a in rows],
            ids=[a["id"] for a in rows])

    def fields(self):
        s = self.win.store
        cats = [(c["id"], f"{c['code']} {c['name']}") for c in s.categories("asset")]
        return [
            ("number", "เลขรหัสครุภัณฑ์", "text"), ("category_id", "ประเภท", "combo", cats),
            ("name", "รายการ ", "text"), ("brand", "ยี่ห้อ", "text"), ("model", "รุ่น", "text"),
            ("serial", "หมายเลขเครื่อง", "text"),
            ("unit", "หน่วยนับ", "edit-combo", ["เครื่อง", "ตัว", "ชุด", "คัน", "หลัง", "อัน"]),
            ("acquire_date", "วันที่ได้มา", "date"), ("price", "ราคาต่อหน่วย (บาท)", "money"),
            ("method", "วิธีได้มา", "edit-combo", DB.METHODS),
            ("budget", "แหล่งเงิน", "edit-combo", DB.BUDGETS),
            ("document_no", "เลขที่เอกสาร", "text"), ("vendor", "ผู้ขาย/ผู้รับจ้าง", "text"),
            ("department", "หน่วยงาน", "edit-combo", [d["name"] for d in s.departments()]),
            ("location", "สถานที่ตั้ง", "text"),
            ("custodian", "ผู้รับผิดชอบ", "edit-combo", [p["name"] for p in s.people()]),
            ("life_years", "อายุการใช้งาน (ปี)", "num"), ("salvage", "ราคาซาก (บาท)", "money"),
            ("status", "สถานะ", "combo", [x for x in DB.STATUSES if x != "จำหน่ายแล้ว"]),
            ("note", "หมายเหตุ", "multi"),
        ]

    def add(self):
        s = self.win.store
        first = s.categories("asset")[0]
        dlg = FormDialog(self, T("ครุภัณฑ์ใหม่"), self.fields(),
                         dict(life_years=first["life_years"], salvage=s.fnum("salvage", 1), status="ใช้งาน",
                              unit="เครื่อง"), hints={"number": T("เว้นว่างให้โปรแกรมออกเลขให้")})
        cat = dlg.w["category_id"][1]
        life = dlg.w["life_years"][1]

        def on_cat():
            r = s.one("SELECT life_years FROM categories WHERE id=?", (cat.currentData(),))
            if r:
                life.setValue(r["life_years"])
        cat.currentIndexChanged.connect(on_cat)
        if dlg.exec():
            try:
                s.save_asset(dlg.values())
            except Exception as exc:  # noqa: BLE001
                return error(self, exc)
            self.win.refresh()

    def edit(self, *_):
        aid = selected_id(self.t)
        if aid is None:
            return need_selection(self)
        a = dict(self.win.store.asset(aid))
        dlg = FormDialog(self, T("แก้ไขครุภัณฑ์"), self.fields(), a)
        if dlg.exec():
            try:
                self.win.store.save_asset(dlg.values(), aid)
            except Exception as exc:  # noqa: BLE001
                return error(self, exc)
            self.win.refresh()

    def delete(self):
        aid = selected_id(self.t)
        if aid is None:
            return need_selection(self)
        if QMessageBox.question(self, PRODUCT_TH, T("ลบรายการนี้?")) == QMessageBox.Yes:
            self.win.store.delete_asset(aid)
            self.win.refresh()

    def card(self):
        aid = selected_id(self.t)
        if aid is None:
            return need_selection(self)
        self.win.preview(R.asset_card(self.win.store, aid))

    def lend(self):
        aid = selected_id(self.t)
        if aid is None:
            return need_selection(self)
        self.win.loans.lend(aid)

    def dispose(self):
        aid = selected_id(self.t)
        if aid is None:
            return need_selection(self)
        a = self.win.store.asset(aid)
        dlg = FormDialog(self, f"{T('จำหน่ายครุภัณฑ์')} {a['number']}", [
            ("date", "วันที่จำหน่าย", "date"), ("method", "วิธีจำหน่าย", "combo", DB.DISPOSALS),
            ("amount", "จำนวนเงินที่ได้ (บาท)", "money"), ("doc", "เลขที่เอกสาร", "text")])
        if dlg.exec():
            v = dlg.values()
            self.win.store.dispose(aid, v["date"], v["method"], v["amount"], v["doc"])
            self.win.refresh()

    def export(self):
        save_report(self, R.asset_list(self.win.store, self.filter.currentData()), "xlsx")


class MaterialPage(QWidget):
    def __init__(self, win):
        super().__init__()
        self.win = win
        w, lay = page("วัสดุ", "บัญชีวัสดุ — รับเข้า เบิกจ่าย คงเหลือ คิดราคาแบบเข้าก่อนออกก่อน (FIFO)")
        QVBoxLayout(self).addWidget(w)
        self.search = QLineEdit()
        self.search.setPlaceholderText(T("ค้นหา…"))
        self.search.textChanged.connect(self.refresh)
        lay.addWidget(self.search)
        sp = QSplitter(Qt.Vertical)
        self.t = table(["รหัส", "ชื่อวัสดุ", "ประเภท", "หน่วยนับ", "คงเหลือ", "มูลค่า", "จุดสั่งซื้อ",
                        "สถานที่ตั้ง"])
        self.t.itemSelectionChanged.connect(self.show_card)
        self.t.doubleClicked.connect(self.edit)
        self.c = table(["วันที่", "รับจาก", "เลขที่เอกสาร", "ราคาต่อหน่วย (บาท)", "รับ", "จ่าย",
                        "คงเหลือ", "มูลค่า", "หมายเหตุ"], stretch=1)
        sp.addWidget(self.t)
        sp.addWidget(self.c)
        lay.addWidget(sp, 1)
        row, _ = buttons(("เพิ่มวัสดุ", self.add, True), ("แก้ไข", self.edit), ("ลบ", self.delete),
                         (None, None), ("รับเข้า", self.receive), ("เบิกจ่าย", self.issue),
                         ("ใบเบิก", self.slip), ("บัญชีวัสดุ", self.card))
        lay.addLayout(row)

    def refresh(self):
        rows = self.win.store.materials(self.search.text().strip())
        fill(self.t, [[m["code"], m["name"], m["category"], m["unit"], R.qty(m["qty"]), float(m["value"]),
                       R.qty(m["min_qty"]), m["location"]] for m in rows], ids=[m["id"] for m in rows],
             right=(4, 6))
        for r, m in enumerate(rows):
            if m["min_qty"] and m["qty"] <= m["min_qty"]:
                self.t.item(r, 4).setForeground(Qt.red)
        self.show_card()

    def show_card(self):
        mid = selected_id(self.t)
        if mid is None:
            self.c.setRowCount(0)
            return
        card = self.win.store.card(mid)
        fill(self.c, [[TD.thai(x["date"]), (x["party"] or "") + (f" ({x['department']})" if x["department"] else ""),
                       x["doc_no"], float(round(x["unit_price"], 2)),
                       R.qty(x["qty"]) if x["kind"] == "in" else "", R.qty(x["qty"]) if x["kind"] == "out" else "",
                       R.qty(x["bal_qty"]), float(x["bal_val"]), x["note"]] for x in card],
             ids=[x["id"] for x in card], right=(4, 5, 6))

    def fields(self):
        cats = [(c["id"], f"{c['code']} {c['name']}") for c in self.win.store.categories("material")]
        return [("code", "รหัส", "text"), ("name", "ชื่อวัสดุ", "text"), ("category_id", "ประเภท", "combo", cats),
                ("unit", "หน่วยนับ", "edit-combo", ["ชิ้น", "รีม", "กล่อง", "ด้าม", "ขวด", "ลิตร", "ถุง", "ม้วน"]),
                ("min_qty", "จุดสั่งซื้อ", "num"), ("location", "สถานที่ตั้ง", "text")]

    def add(self):
        dlg = FormDialog(self, T("เพิ่มวัสดุ"), self.fields(), dict(unit="ชิ้น"),
                         hints={"code": T("เว้นว่างให้โปรแกรมออกเลขให้")})
        if dlg.exec():
            try:
                self.win.store.save_material(dlg.values())
            except Exception as exc:  # noqa: BLE001
                return error(self, exc)
            self.win.refresh()

    def edit(self, *_):
        mid = selected_id(self.t)
        if mid is None:
            return need_selection(self)
        m = dict(self.win.store.one("SELECT * FROM materials WHERE id=?", (mid,)))
        dlg = FormDialog(self, T("แก้ไข"), self.fields(), m)
        if dlg.exec():
            self.win.store.save_material(dlg.values(), mid)
            self.win.refresh()

    def delete(self):
        mid = selected_id(self.t)
        if mid is None:
            return need_selection(self)
        if QMessageBox.question(self, PRODUCT_TH, T("ลบรายการนี้?")) == QMessageBox.Yes:
            self.win.store.delete_material(mid)
            self.win.refresh()

    def receive(self):
        mid = selected_id(self.t)
        if mid is None:
            return need_selection(self)
        dlg = FormDialog(self, T("รับวัสดุเข้าคลัง"), [
            ("date", "วันที่", "date"), ("qty", "จำนวน", "num"), ("price", "ราคาต่อหน่วย (บาท)", "money"),
            ("doc", "เลขที่เอกสาร", "text"), ("party", "รับจาก", "text"), ("note", "หมายเหตุ", "text")])
        if dlg.exec():
            v = dlg.values()
            try:
                self.win.store.receive(mid, v["date"], v["qty"], v["price"], v["doc"], v["party"], v["note"])
            except Exception as exc:  # noqa: BLE001
                return error(self, exc)
            self.win.refresh()

    def issue(self):
        mid = selected_id(self.t)
        if mid is None:
            return need_selection(self)
        s = self.win.store
        dlg = FormDialog(self, T("เบิกจ่ายวัสดุ"), [
            ("date", "วันที่", "date"), ("qty", "จำนวน", "num"), ("doc", "เลขที่เอกสาร", "text"),
            ("party", "ผู้เบิก", "edit-combo", [p["name"] for p in s.people()]),
            ("department", "หน่วยงานผู้เบิก", "edit-combo", [d["name"] for d in s.departments()]),
            ("note", "หมายเหตุ", "text")])
        if dlg.exec():
            v = dlg.values()
            try:
                mv = s.issue(mid, v["date"], v["qty"], v["doc"], v["party"], v["department"], v["note"])
            except Exception as exc:  # noqa: BLE001
                return error(self, exc)
            self.win.refresh()
            self.win.preview(R.issue_slip(s, [mv]))

    def slip(self):
        mv = selected_id(self.c)
        if mv is None:
            return need_selection(self)
        row = self.win.store.one("SELECT kind FROM moves WHERE id=?", (mv,))
        if row and row["kind"] == "out":
            self.win.preview(R.issue_slip(self.win.store, [mv]))
        else:
            need_selection(self)

    def card(self):
        mid = selected_id(self.t)
        if mid is None:
            return need_selection(self)
        self.win.preview(R.stock_card(self.win.store, mid))


class LoanPage(QWidget):
    def __init__(self, win):
        super().__init__()
        self.win = win
        w, lay = page("ยืม-คืน", "การยืมพัสดุ — บันทึกผู้ยืม กำหนดส่งคืน และติดตามการคืน (หมวด 9 ส่วนที่ 3)")
        QVBoxLayout(self).addWidget(w)
        self.open_only = QCheckBox(T("แสดงเฉพาะที่ยังไม่คืน"))
        self.open_only.toggled.connect(self.refresh)
        lay.addWidget(self.open_only)
        self.t = table(["เลขรหัสครุภัณฑ์", "รายการ ", "ผู้ยืม", "หน่วยงาน", "วัตถุประสงค์", "วันที่ยืม",
                        "กำหนดคืน", "วันที่คืน", "สภาพเมื่อคืน"], stretch=1)
        lay.addWidget(self.t, 1)
        row, _ = buttons(("ยืมครุภัณฑ์", lambda: self.lend(None), True), ("คืนครุภัณฑ์", self.back),
                         (None, None), ("พิมพ์ PDF", self.pdf))
        lay.addLayout(row)

    def refresh(self):
        rows = self.win.store.loans(self.open_only.isChecked())
        today = str(TD.today())
        fill(self.t, [[x["number"], x["asset_name"], x["borrower"], x["department"], x["purpose"],
                       TD.thai(x["date_out"]), TD.thai(x["due_date"]),
                       TD.thai(x["date_back"]) or T("ยังไม่คืน"), x["condition_back"]] for x in rows],
             ids=[x["id"] for x in rows])
        for r, x in enumerate(rows):
            if not x["date_back"] and x["due_date"] and x["due_date"] < today:
                self.t.item(r, 6).setForeground(Qt.red)

    def lend(self, aid):
        s = self.win.store
        items = [(a["id"], f"{a['number']} {a['name']}") for a in s.assets(include_disposed=False)]
        dlg = FormDialog(self, T("ยืมครุภัณฑ์"), [
            ("asset", "ครุภัณฑ์", "combo", items), ("borrower", "ผู้ยืม", "edit-combo", [p["name"] for p in s.people()]),
            ("department", "หน่วยงาน", "edit-combo", [d["name"] for d in s.departments()]),
            ("purpose", "วัตถุประสงค์", "text"), ("date_out", "วันที่ยืม", "date"),
            ("due", "กำหนดคืน", "date"), ("note", "หมายเหตุ", "text")], dict(asset=aid))
        if dlg.exec():
            v = dlg.values()
            try:
                s.lend(v["asset"], v["borrower"], v["date_out"], v["due"], v["purpose"], v["department"], v["note"])
            except Exception as exc:  # noqa: BLE001
                return error(self, exc)
            self.win.refresh()
            self.win.go(self.win.pages.index(self))

    def back(self):
        lid = selected_id(self.t)
        if lid is None:
            return need_selection(self)
        dlg = FormDialog(self, T("คืนครุภัณฑ์"), [
            ("date", "วันที่คืน", "date"), ("cond", "สภาพเมื่อคืน", "edit-combo", DB.INSPECT_RESULTS[:3])])
        if dlg.exec():
            v = dlg.values()
            self.win.store.give_back(lid, v["date"], v["cond"])
            self.win.refresh()

    def pdf(self):
        self.win.preview(R.loans_report(self.win.store, self.open_only.isChecked()))


class InspectPage(QWidget):
    def __init__(self, win):
        super().__init__()
        self.win = win
        w, lay = page("ตรวจสอบประจำปี", "ข้อ 213 — คณะกรรมการตรวจสอบพัสดุตรวจนับพัสดุคงเหลือ "
                      "ณ วันสิ้นปีงบประมาณ (30 ก.ย.) แล้วรายงานภายใน 30 วันทำการ")
        QVBoxLayout(self).addWidget(w)
        top = QHBoxLayout()
        top.addWidget(QLabel(T("ปีงบประมาณ")))
        self.fy = QSpinBox()
        self.fy.setRange(2500, 2700)
        self.fy.setValue(TD.fiscal_year(TD.today()) - 1)   # the year just ended
        self.fy.valueChanged.connect(self.refresh)
        top.addWidget(self.fy)
        top.addSpacing(20)
        top.addWidget(QLabel(T("ตั้งผลที่เลือกเป็น")))
        self.result = QComboBox()
        for r in DB.INSPECT_RESULTS:
            self.result.addItem(T(r), r)
        top.addWidget(self.result)
        b = QPushButton(T("บันทึกผลการตรวจ"))
        b.setObjectName("primary")
        b.clicked.connect(self.save)
        top.addWidget(b)
        top.addStretch(1)
        lay.addLayout(top)
        self.t = table(["เลขรหัสครุภัณฑ์", "รายการ ", "สถานที่ตั้ง", "ผู้รับผิดชอบ", "สถานะ", "ผลการตรวจ",
                        "หมายเหตุ"], stretch=1)
        from PySide6.QtWidgets import QAbstractItemView
        self.t.setSelectionMode(QAbstractItemView.ExtendedSelection)
        lay.addWidget(self.t, 1)
        row, _ = buttons((None, None), ("พิมพ์ PDF", self.pdf), ("ส่งออกตาราง", self.export))
        lay.addLayout(row)

    def refresh(self):
        rows = self.win.store.inspection(self.fy.value())
        fill(self.t, [[x["asset"]["number"], x["asset"]["name"], x["asset"]["location"], x["asset"]["custodian"],
                       T(x["asset"]["status"]), T(x["result"]) if x["result"] else T("ยังไม่ได้ตรวจ"), x["note"]]
                      for x in rows], ids=[x["asset"]["id"] for x in rows])
        for r, x in enumerate(rows):
            if not x["result"]:
                self.t.item(r, 5).setForeground(Qt.darkYellow)

    def save(self):
        rows = sorted({i.row() for i in self.t.selectedIndexes()})
        if not rows:
            return need_selection(self)
        for r in rows:
            aid = self.t.item(r, 0).data(Qt.UserRole)
            self.win.store.inspect(self.fy.value(), aid, self.result.currentData())
        self.win.refresh()

    def pdf(self):
        self.win.preview(R.inspection_report(self.win.store, self.fy.value()))

    def export(self):
        save_report(self, R.inspection_report(self.win.store, self.fy.value()), "xlsx")


class ReportPage(QWidget):
    def __init__(self, win):
        super().__init__()
        self.win = win
        w, lay = page("รายงาน", "รายงานเป็นแบบฟอร์มราชการภาษาไทย")
        QVBoxLayout(self).addWidget(w)
        top = QHBoxLayout()
        self.list = QListWidget()
        self.list.setFixedWidth(px(360))
        self.kinds = [("บัญชีครุภัณฑ์", lambda s: R.asset_list(s)),
                      ("รายงานค่าเสื่อมราคาประจำปี", lambda s: R.depreciation_year(s, self.fy.value())),
                      ("รายงานวัสดุคงเหลือ", lambda s: R.material_balance(s)),
                      ("ทะเบียนการยืมพัสดุ", lambda s: R.loans_report(s)),
                      ("รายงานผลการตรวจสอบพัสดุประจำปี", lambda s: R.inspection_report(s, self.fy.value())),
                      ("ทะเบียนการจำหน่ายพัสดุ", lambda s: R.disposal_report(s)),
                      ("รายงานสถานะการใช้จ่ายงบประมาณ", lambda s: R.budget_status(s, self.fy.value())),
                      ("สถานะงบประมาณตามหมวด", lambda s: R.budget_status(s, self.fy.value(), "category")),
                      ("ทะเบียนคุมการจัดซื้อจัดจ้าง", lambda s: R.proc_register(s, self.fy.value())),
                      ("ทะเบียนคุมการเบิกจ่ายเงิน", lambda s: R.payment_register(s, self.fy.value()))]
        for k, _ in self.kinds:
            self.list.addItem(T(k))
        self.list.currentRowChanged.connect(self.show)
        side = QVBoxLayout()
        fyrow = QHBoxLayout()
        fyrow.addWidget(QLabel(T("ปีงบประมาณ")))
        self.fy = QSpinBox()
        self.fy.setRange(2500, 2700)
        self.fy.setValue(TD.fiscal_year(TD.today()))
        self.fy.valueChanged.connect(lambda: self.show(self.list.currentRow()))
        fyrow.addWidget(self.fy)
        side.addLayout(fyrow)
        side.addWidget(self.list, 1)
        brow, _ = buttons(("พิมพ์ PDF", self.pdf, True), ("ส่งออกตาราง", self.xlsx))
        side.addLayout(brow)
        top.addLayout(side)
        self.view = QTextBrowser()
        self.view.setStyleSheet("background: white;")
        top.addWidget(self.view, 1)
        lay.addLayout(top, 1)
        self.current = None

    def show(self, i):
        if i < 0:
            return
        self.current = self.kinds[i][1](self.win.store)
        self.view.setHtml(self.current.html())

    def open(self, rep):
        self.current = rep
        self.list.blockSignals(True)
        self.list.clearSelection()
        self.list.setCurrentRow(-1)
        self.list.blockSignals(False)
        self.view.setHtml(rep.html())

    def refresh(self):
        if self.list.currentRow() >= 0:
            self.show(self.list.currentRow())

    def pdf(self):
        if self.current:
            save_report(self, self.current, "pdf")

    def xlsx(self):
        if self.current:
            save_report(self, self.current, "xlsx")


class SettingsPage(QWidget):
    KEYS = [("org_name", "ชื่อหน่วยงาน"), ("org_code", "รหัสหน่วยงาน"), ("org_address", "ที่อยู่")]
    SIGN = [("officer", "เจ้าหน้าที่พัสดุ"), ("head_officer", "หัวหน้าเจ้าหน้าที่"),
            ("head", "หัวหน้าหน่วยงานของรัฐ")]

    def __init__(self, win):
        super().__init__()
        self.win = win
        w, lay = page("ตั้งค่า")
        QVBoxLayout(self).addWidget(w)
        cols = QHBoxLayout()
        lay.addLayout(cols, 1)
        left = QVBoxLayout()
        cols.addLayout(left, 1)
        self.e = {}
        g = QGroupBox(T("ข้อมูลหน่วยงาน"))
        f = QFormLayout(g)
        for k, label in self.KEYS:
            self.e[k] = QLineEdit()
            f.addRow(T(label), self.e[k])
        left.addWidget(g)
        g = QGroupBox(T("ผู้ลงนาม"))
        f = QFormLayout(g)
        for k, label in self.SIGN:
            self.e[k] = QLineEdit()
            self.e[k + "_pos"] = QLineEdit()
            r = QHBoxLayout()
            r.addWidget(self.e[k], 3)
            r.addWidget(self.e[k + "_pos"], 2)
            f.addRow(T(label), r)
        left.addWidget(g)
        g = QGroupBox(T("การคิดค่าเสื่อมและเลขรหัส"))
        f = QFormLayout(g)
        for k, label in [("threshold", "เกณฑ์ราคาบันทึกเป็นสินทรัพย์ (บาท)"), ("salvage", "ราคาซาก (บาท)"),
                         ("number_format", "รูปแบบเลขรหัสครุภัณฑ์")]:
            self.e[k] = QLineEdit()
            f.addRow(T(label), self.e[k])
        hint = QLabel("{org} = รหัสหน่วยงาน · {type} = รหัสประเภท · {seq:04d} = ลำดับ · {fy} = ปีงบประมาณ")
        hint.setObjectName("hint")
        f.addRow(hint)
        left.addWidget(g)
        g = QGroupBox(T("การจัดซื้อจัดจ้างและการเบิกจ่าย"))
        f = QFormLayout(g)
        for k, label in [("specific_limit", "วงเงินวิธีเฉพาะเจาะจง (บาท)"),
                         ("wht_rate", "ภาษีหัก ณ ที่จ่าย (%)"), ("wht_min", "หักภาษีเมื่อจ่ายตั้งแต่ (บาท)"),
                         ("fine_rate", "ค่าปรับซื้อ/เช่า (% ต่อวัน)"), ("fine_rate_hire", "ค่าปรับจ้าง (% ต่อวัน)")]:
            self.e[k] = QLineEdit()
            f.addRow(T(label), self.e[k])
        left.addWidget(g)
        b = QPushButton(T("บันทึกการตั้งค่า"))
        b.setObjectName("primary")
        b.clicked.connect(self.save)
        left.addWidget(b)
        left.addStretch(1)
        g = QGroupBox(T("ประเภทครุภัณฑ์และอายุการใช้งาน"))
        v = QVBoxLayout(g)
        self.cats = table(["รหัส", "ประเภท", "อายุการใช้งาน (ปี)"], stretch=1)
        from PySide6.QtWidgets import QAbstractItemView
        self.cats.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed)
        v.addWidget(self.cats)
        note = QLabel("ค่าเริ่มต้นแก้ไขได้ — ให้ตรวจกับหลักเกณฑ์อายุการใช้งานของกรมบัญชีกลางที่หน่วยงานใช้")
        note.setObjectName("hint")
        note.setWordWrap(True)
        v.addWidget(note)
        cols.addWidget(g, 1)

    def refresh(self):
        st = self.win.store.settings()
        for k, e in self.e.items():
            e.setText(st.get(k, ""))
        rows = self.win.store.categories("asset")
        fill(self.cats, [[c["code"], c["name"], f"{c['life_years']:g}"] for c in rows], ids=[c["id"] for c in rows])

    def save(self):
        s = self.win.store
        for k, e in self.e.items():
            s.set_setting(k, e.text().strip())
        for r in range(self.cats.rowCount()):
            try:
                life = float(self.cats.item(r, 2).text())
            except ValueError:
                life = 5
            s.save_category("asset", self.cats.item(r, 0).text(), self.cats.item(r, 1).text(), life,
                            self.cats.item(r, 0).data(Qt.UserRole))
        QMessageBox.information(self, PRODUCT_TH, T("บันทึกแล้ว"))
        self.win.refresh()


# ============================================================ main window
NAV = ["หน้าหลัก", "งบประมาณ", "จัดซื้อจัดจ้าง", "สถิติ", "ครุภัณฑ์", "วัสดุ", "ยืม-คืน", "ตรวจสอบประจำปี", "รายงาน", "ตั้งค่า"]


class MainWindow(QMainWindow):
    def __init__(self, path=None):
        super().__init__()
        self.cfg = QSettings("Venit", "VenitSupply")
        path = path or self.cfg.value("last_db") or str(default_db())
        self.store = DB.Store(path)
        self.cfg.setValue("last_db", str(path))
        self.setWindowTitle(f"{PRODUCT_TH} ({PRODUCT_EN}) {__version__}")
        icon = asset_path("venitsupply.png")
        if icon.exists():
            self.setWindowIcon(QIcon(str(icon)))
        fit_to_screen(self, 1500, 920)
        central = QWidget()
        h = QHBoxLayout(central)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)
        side = QWidget()
        side.setStyleSheet(f"background:{NAVY};")
        side.setFixedWidth(px(230))
        sv = QVBoxLayout(side)
        sv.setContentsMargins(0, 14, 0, 10)
        brand = QLabel(f"<div style='color:white; font-size:{pt(22)}pt'><b>{T('พัสดุเวนิช')}</b></div>"
                       f"<div style='color:#C9A14A; font-size:{pt(12)}pt'>{PRODUCT_TH if i18n.LANG == 'en' else PRODUCT_EN}</div>"
                       f"<div style='color:#AFC0D2; font-size:{pt(11)}pt'>{T('โปรแกรมบริหารพัสดุภาคเวนิช FC')}</div>")
        brand.setAlignment(Qt.AlignCenter)
        sv.addWidget(brand)
        self.nav = QListWidget()
        self.nav.setObjectName("nav")
        for n in NAV:
            QListWidgetItem(T(n), self.nav)
        sv.addWidget(self.nav, 1)
        ver = QLabel(f"<span style='color:#7F93A8; font-size:{pt(10)}pt'>{__version__}<br>"
                     f"© 2569 {DEVELOPER}</span>")
        ver.setAlignment(Qt.AlignCenter)
        sv.addWidget(ver)
        h.addWidget(side)
        self.stack = QStackedWidget()
        h.addWidget(self.stack, 1)
        self.setCentralWidget(central)
        from .pages_budget import BudgetPage, ProcPage, StatsPage
        self.home = HomePage(self)
        self.budget = BudgetPage(self)
        self.procs = ProcPage(self)
        self.stats = StatsPage(self)
        self.assets = AssetPage(self)
        self.materials = MaterialPage(self)
        self.loans = LoanPage(self)
        self.inspect = InspectPage(self)
        self.reports = ReportPage(self)
        self.settings_page = SettingsPage(self)
        self.pages = [self.home, self.budget, self.procs, self.stats, self.assets, self.materials, self.loans, self.inspect, self.reports,
                      self.settings_page]
        for p in self.pages:
            self.stack.addWidget(scrolled(p))
        self.nav.currentRowChanged.connect(self.go)
        self._menus()
        mf = self.menuBar().font()
        mf.setPointSizeF(pt(17))                  # the menu bar was too small on Windows
        self.menuBar().setFont(mf)
        self.nav.setCurrentRow(0)
        self._backfill()
        self.refresh()

    def _menus(self):
        m = self.menuBar().addMenu(T("ไฟล์"))
        for text, fn in [("ฐานข้อมูลใหม่…", self.new_db), ("เปิดฐานข้อมูล…", self.open_db)]:
            a = QAction(T(text), self)
            a.triggered.connect(fn)
            m.addAction(a)
        m.addSeparator()
        a = QAction(T("ออก"), self)
        a.triggered.connect(self.close)
        m.addAction(a)
        lang = self.menuBar().addMenu(T("ภาษา"))
        for code, name in (("th", "ไทย"), ("en", "English")):
            a = QAction(name, self)
            a.setCheckable(True)
            a.setChecked(i18n.LANG == code)
            a.triggered.connect(lambda _=False, c=code: self.switch_lang(c))
            lang.addAction(a)
        hm = self.menuBar().addMenu(T("ช่วยเหลือ"))
        a = QAction(T("เกี่ยวกับโปรแกรม"), self)
        a.triggered.connect(self.about)
        hm.addAction(a)

    def _backfill(self):
        """ลงทะเบียนครุภัณฑ์/วัสดุย้อนหลังจากการซื้อที่ตรวจรับหรือเบิกจ่ายแล้ว (เจ้าของอนุมัติ 13 พ.ย. 2569)."""
        try:
            n = self.store.register_missing()
        except Exception:  # noqa: BLE001 — never block opening the file
            return
        if n:
            from PySide6.QtCore import QTimer
            QTimer.singleShot(400, lambda: QMessageBox.information(
                self, PRODUCT_TH, f"ลงทะเบียนครุภัณฑ์/รับวัสดุเข้าคลังย้อนหลังให้แล้ว {n} รายการ\n"
                "จากการซื้อที่ตรวจรับหรือเบิกจ่ายแล้ว — ดูได้ที่หน้า «ครุภัณฑ์» และ «วัสดุ»"))
            self.refresh()

    def go(self, i):
        if self.nav.currentRow() != i:
            self.nav.setCurrentRow(i)
        self.stack.setCurrentIndex(i)
        self.pages[i].refresh()

    def refresh(self):
        self.pages[self.stack.currentIndex()].refresh()

    def preview(self, rep):
        self.go(self.pages.index(self.reports))
        self.reports.open(rep)

    def switch_lang(self, code):
        self.cfg.setValue("lang", code)
        i18n.set_lang(code)
        w = MainWindow(self.store.path)
        w.show()
        QApplication.instance()._main = w
        self.close()

    def new_db(self):
        path, _ = QFileDialog.getSaveFileName(self, T("ฐานข้อมูลใหม่…"), str(default_db().parent),
                                              "พัสดุเวนิช (*.vsdb)")
        if path:
            if not path.endswith(".vsdb"):
                path += ".vsdb"
            self.switch_db(path)

    def open_db(self):
        path, _ = QFileDialog.getOpenFileName(self, T("เปิดฐานข้อมูล…"), str(default_db().parent),
                                              "พัสดุเวนิช (*.vsdb)")
        if path:
            self.switch_db(path)

    def switch_db(self, path):
        self.store.close()
        self.store = DB.Store(path)
        self.cfg.setValue("last_db", path)
        self.go(0)
        self._backfill()

    def about(self):
        QMessageBox.about(self, T("เกี่ยวกับโปรแกรม"),
                          f"<h2>{PRODUCT_TH} ({PRODUCT_EN})</h2><p>รุ่น {__version__}</p>"
                          f"<p>โปรแกรมบริหารพัสดุภาครัฐ ตามระเบียบกระทรวงการคลังว่าด้วยการจัดซื้อจัดจ้าง"
                          f"และการบริหารพัสดุภาครัฐ พ.ศ. 2560 หมวด 9</p>"
                          f"<p>ผู้พัฒนา {DEVELOPER} {QUALIFICATION}<br>{FREE_USE}</p>"
                          "<p>สัญญาอนุญาต GPL-3.0</p>")

    def closeEvent(self, e):  # noqa: N802 (Qt)
        self.store.close()
        super().closeEvent(e)


def selftest(out_dir) -> int:
    """Used by the installer build: data, reports, PDF writing and the PDF reader all load."""
    from . import demo
    import importlib
    importlib.import_module("pdfminer.high_level")      # the PDF reader must be bundled
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    s = demo.fill(DB.Store(":memory:"))
    assert round(s.ordinance(2570)["amount"]) == 205000000
    pid = s.procurements(2570)[0]["id"]
    for name, rep in (("budget", R.budget_status(s, 2570, "plan")), ("request", R.proc_request(s, pid)),
                      ("assets", R.asset_list(s))):
        R.to_pdf(rep, out / f"{name}.pdf")
        assert (out / f"{name}.pdf").stat().st_size > 1000
    R.to_xlsx(R.proc_register(s, 2570), out / "register.xlsx")
    (out / "selftest-ok.txt").write_text(f"{PRODUCT_EN} {__version__} OK", encoding="utf-8")
    return 0


def main(argv=None):
    argv = argv if argv is not None else sys.argv
    if "--selftest" in argv:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        app = QApplication(argv)
        i = argv.index("--selftest")
        return selftest(argv[i + 1] if len(argv) > i + 1 else "selftest")
    app = QApplication(argv)
    app.setApplicationName(PRODUCT_EN)
    app.setStyleSheet(make_style())
    i18n.set_lang(QSettings("Venit", "VenitSupply").value("lang", "th"))
    path = next((a for a in argv[1:] if a.endswith(".vsdb")), None)
    w = MainWindow(path)
    app._main = w
    g = app.primaryScreen().availableGeometry() if app.primaryScreen() else None
    if g is not None and (g.width() < 1600 or g.height() < 950):
        w.showMaximized()                 # small or scaled screens: use all of it
    else:
        w.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
