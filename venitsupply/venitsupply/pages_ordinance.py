# SPDX-License-Identifier: GPL-3.0-or-later
"""หน้าต่าง «นำเข้าข้อบัญญัติ»: เลือกปีงบประมาณ → เลือกไฟล์ (PDF/ตาราง) → อ่าน → ตรวจรายการ → บันทึก."""
from __future__ import annotations

from html import escape
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QApplication, QComboBox, QDialog, QFileDialog,
                               QGroupBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
                               QMessageBox, QProgressBar, QPushButton, QSpinBox, QSplitter,
                               QTextBrowser, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget)

from . import PRODUCT_TH
from . import budget as B
from . import thaidate as TD
from .i18n import T
from .widgets import MUTED, error

RED, GREEN = "#C72B1E", "#0E7F4F"
DATA = Path(B.__file__).resolve().parent / "data"
BUNDLED = {  # ข้อบัญญัติในชุดโปรแกรม (อ่านจากต้นฉบับแล้ว)
    "อบต.ไม้ขาว ปี 2570": ("maikhao_2570.csv", "องค์การบริหารส่วนตำบลไม้ขาว",
                          "https://www.maikhaow.go.th/ebook_banyad/detail/18/data.html"),
    "อบต.ไม้ขาว ปี 2569": ("maikhao_2569.csv", "องค์การบริหารส่วนตำบลไม้ขาว",
                          "https://www.maikhaow.go.th/ebook_banyad/detail/14/data.html"),
}


def m(v) -> str:
    return f"{float(v or 0):,.2f}"


def rows_to_items(rows) -> tuple[list[dict], dict]:
    """A table (header + rows) in the «รายงานประมาณการรายจ่าย» layout → items, meta."""
    import re
    head = [str(h).strip() for h in rows[0]]
    est = [(i, int(mm.group(1))) for i, h in enumerate(head)
           for mm in [re.match(r"ประมาณการ\s*(25\d\d)", h)] if mm]
    if not est:
        raise ValueError("ไม่พบคอลัมน์ «ประมาณการ ปปปป» ในหัวตาราง")
    col, fy = max(est, key=lambda c: c[1])
    di = head.index("คำชี้แจง") if "คำชี้แจง" in head else None
    items = []
    for r in rows[1:]:
        r = [str(x).strip() for x in r] + [""] * len(head)
        if not r[5]:
            continue
        amt = B._num(r[col]) or 0.0
        items.append({"แผนงาน": r[0], "งาน": r[1], "งบ": r[2], "หมวด": r[3], "ประเภท": r[4], "รายการ": r[5],
                      "amount": amt, "คำชี้แจง": r[di] if di is not None else ""})
    plans: dict[str, float] = {}
    for it in items:
        plans[it["แผนงาน"]] = plans.get(it["แผนงาน"], 0) + it["amount"]
    return items, dict(fy=fy, plans=plans, total=sum(plans.values()), total_stated=None,
                       details=sum(1 for it in items if it["คำชี้แจง"]), agency="")


class OrdinanceDialog(QDialog):
    """อ่านข้อบัญญัติของปีงบประมาณที่เลือก แล้วแสดงรายการให้ตรวจก่อนบันทึก."""

    def __init__(self, page, fy=None):
        super().__init__(page)
        self.page = page
        self.store = page.win.store
        self.rows = None            # table rows ready for Store.import_ordinance
        self.items: list[dict] = []
        self.meta: dict = {}
        self.setWindowTitle(T("นำเข้าข้อบัญญัติงบประมาณรายจ่าย (PDF หรือตาราง)"))
        self.resize(1500, 900)
        lay = QVBoxLayout(self)

        g = QGroupBox(T("1. ปีงบประมาณของข้อบัญญัติ"))
        gl = QHBoxLayout(g)
        self.fy = QSpinBox()
        self.fy.setRange(2500, 2700)
        cur = TD.fiscal_year(TD.today())
        self.fy.setValue(fy or cur)
        gl.addWidget(QLabel(T("ปีงบประมาณ พ.ศ.")))
        gl.addWidget(self.fy)
        for label, y in ((f"{T('ปีปัจจุบัน')} {cur}", cur), (f"{T('ปีถัดไป')} {cur + 1}", cur + 1)):
            b = QPushButton(label)
            b.clicked.connect(lambda _=False, yy=y: self.fy.setValue(yy))
            gl.addWidget(b)
        self.fy_state = QLabel("")
        gl.addWidget(self.fy_state, 1)
        self.fy.valueChanged.connect(self.check)
        lay.addWidget(g)

        g = QGroupBox(T("2. เลือกเอกสารข้อบัญญัติ"))
        gl = QHBoxLayout(g)
        pick = QPushButton(T("เลือกไฟล์ PDF / ตาราง…"))
        pick.setObjectName("primary")
        pick.clicked.connect(self.pick)
        gl.addWidget(pick)
        gl.addWidget(QLabel(T("หรือข้อบัญญัติในชุดโปรแกรม")))
        self.bundled = QComboBox()
        self.bundled.addItem("—", None)
        for k in BUNDLED:
            self.bundled.addItem(k, k)
        self.bundled.activated.connect(self.use_bundled)
        gl.addWidget(self.bundled)
        self.file = QLabel("")
        self.file.setObjectName("hint")
        gl.addWidget(self.file, 1)
        self.bar = QProgressBar()
        self.bar.setVisible(False)
        self.bar.setFixedWidth(260)
        gl.addWidget(self.bar)
        lay.addWidget(g)

        g = QGroupBox(T("3. ตรวจรายการที่อ่านได้"))
        gv = QVBoxLayout(g)
        self.summary = QLabel(T("ยังไม่ได้อ่านไฟล์"))
        self.summary.setWordWrap(True)
        self.summary.setTextFormat(Qt.RichText)
        gv.addWidget(self.summary)
        f = QHBoxLayout()
        self.title = QLineEdit()
        self.agency = QLineEdit(self.store.setting("org_name") or "")
        self.source = QLineEdit()
        for label, wdg, st in ((T("ชื่อข้อบัญญัติ"), self.title, 3), (T("หน่วยงาน"), self.agency, 2),
                               (T("ที่มา"), self.source, 2)):
            f.addWidget(QLabel(label))
            f.addWidget(wdg, st)
        gv.addLayout(f)
        self.search = QLineEdit()
        self.search.setPlaceholderText(T("ค้นหา…"))
        self.search.textChanged.connect(self.fill_tree)
        gv.addWidget(self.search)
        sp = QSplitter(Qt.Horizontal)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels([T("รายการ"), T("จำนวนเงิน (บาท)"), T("คำชี้แจง")])
        h = self.tree.header()
        h.setSectionResizeMode(0, QHeaderView.Stretch)
        h.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        h.setStretchLastSection(False)
        self.tree.currentItemChanged.connect(lambda *_: self.show_item())
        sp.addWidget(self.tree)
        self.detail = QTextBrowser()
        sp.addWidget(self.detail)
        sp.setSizes([980, 420])
        gv.addWidget(sp, 1)
        lay.addWidget(g, 1)

        row = QHBoxLayout()
        row.addStretch(1)
        self.save_btn = QPushButton(T("บันทึกเป็นข้อบัญญัติ"))
        self.save_btn.setObjectName("primary")
        self.save_btn.setEnabled(False)
        self.save_btn.clicked.connect(self.save)
        cancel = QPushButton(T("ยกเลิก"))
        cancel.clicked.connect(self.reject)
        row.addWidget(self.save_btn)
        row.addWidget(cancel)
        lay.addLayout(row)
        self.check()

    # ---------------------------------------------------------- reading
    def pick(self):
        path, _ = QFileDialog.getOpenFileName(self, T("เลือกไฟล์ PDF / ตาราง…"), "",
                                              "ข้อบัญญัติ (*.pdf *.xlsx *.csv)")
        if path:
            self.read(path)

    def use_bundled(self, i):
        key = self.bundled.itemData(i)
        if not key:
            return
        fname, agency, src = BUNDLED[key]
        self.read(str(DATA / fname), agency=agency, source=src)

    def read(self, path, agency=None, source=None):
        self.file.setText(Path(path).name)
        self.bar.setVisible(True)
        self.bar.setValue(0)
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            if path.lower().endswith(".pdf"):
                from . import ordinance_pdf as O
                O._CACHE.clear()

                def progress(i, n):
                    self.bar.setMaximum(n)
                    self.bar.setValue(i)
                    self.bar.setFormat(f"{T('อ่านหน้า')} %v / %m")
                    QApplication.processEvents()
                items, meta = O.read_ordinance(path, progress)
                rows = O.to_rows(items, meta)
                items = [dict(it, amount=it["amount"]) for it in items]
            else:
                rows = B.read_table(path)
                items, meta = rows_to_items(rows)
        except Exception as exc:  # noqa: BLE001
            QApplication.restoreOverrideCursor()
            self.bar.setVisible(False)
            return error(self, f"อ่านไฟล์ไม่ได้: {exc}")
        QApplication.restoreOverrideCursor()
        self.bar.setVisible(False)
        if not items:
            return error(self, "ไม่พบ «รายงานประมาณการรายจ่าย» ในไฟล์นี้")
        self.rows, self.items, self.meta = rows, items, meta
        if meta.get("agency") or agency:
            self.agency.setText(agency or meta["agency"])
        if source is not None:
            self.source.setText(source)
        elif not self.source.text():
            self.source.setText(Path(path).name)
        if meta.get("fy") and meta["fy"] != self.fy.value():
            ans = QMessageBox.question(
                self, PRODUCT_TH, f"เอกสารนี้เป็นข้อบัญญัติปีงบประมาณ {meta['fy']} "
                f"แต่เลือกปี {self.fy.value()} ไว้\nเปลี่ยนเป็นปี {meta['fy']} หรือไม่?")
            if ans == QMessageBox.Yes:
                self.fy.setValue(meta["fy"])
        self.title.setText(f"ข้อบัญญัติงบประมาณรายจ่ายประจำปีงบประมาณ พ.ศ. {meta.get('fy') or self.fy.value()}")
        self.fill_tree()
        self.check()

    # ----------------------------------------------------------- showing
    def fill_tree(self):
        self.tree.clear()
        q = self.search.text().strip()
        nodes = {}
        sums = {}
        for it in self.items:
            if q and q not in it["รายการ"] and q not in it["ประเภท"] and q not in it.get("คำชี้แจง", ""):
                continue
            if not it["amount"]:
                continue
            path = (it["แผนงาน"], it["งาน"], it["งบ"], it["หมวด"])
            if it["ประเภท"] != it["รายการ"]:
                path += (it["ประเภท"],)
            parent = None
            for i in range(1, len(path) + 1):
                key = path[:i]
                if key not in nodes:
                    n = QTreeWidgetItem([key[-1], "", ""])
                    f = n.font(0)
                    f.setBold(True)
                    n.setFont(0, f)
                    (parent.addChild(n) if parent else self.tree.addTopLevelItem(n))
                    nodes[key] = n
                    sums[key] = 0.0
                sums[key] += it["amount"]
                parent = nodes[key]
            leaf = QTreeWidgetItem([it["รายการ"], m(it["amount"]), "✓" if it.get("คำชี้แจง") else "—"])
            leaf.setData(0, Qt.UserRole, it)
            leaf.setTextAlignment(1, Qt.AlignRight | Qt.AlignVCenter)
            parent.addChild(leaf)
        for key, n in nodes.items():
            n.setText(1, m(sums[key]))
            n.setTextAlignment(1, Qt.AlignRight | Qt.AlignVCenter)
        self.tree.expandToDepth(1 if not q else 5)

    def show_item(self):
        n = self.tree.currentItem()
        it = n.data(0, Qt.UserRole) if n else None
        if not it:
            self.detail.setHtml(f"<h3>{escape(n.text(0)) if n else ''}</h3><p>{n.text(1) if n else ''} บาท</p>")
            return
        det = escape(it.get("คำชี้แจง") or "").replace("\n", "<br>") or f"<i>{T('ไม่มีคำชี้แจง')}</i>"
        self.detail.setHtml(
            f"<p style='color:{MUTED}'>{escape(it['แผนงาน'])} › {escape(it['งาน'])} › {escape(it['งบ'])} › "
            f"{escape(it['หมวด'])} › {escape(it['ประเภท'])}</p><h3>{escape(it['รายการ'])}</h3>"
            f"<p>{T('จำนวนเงิน')} <b>{m(it['amount'])}</b> {T('บาท')}</p><p><b>{T('คำชี้แจง')}</b><br>{det}</p>")

    def check(self):
        fy = self.fy.value()
        o = self.store.ordinance(fy)
        if o["items"]:
            self.fy_state.setText(f"<span style='color:#B45309'>ปี {fy} มีข้อบัญญัติในโปรแกรมแล้ว "
                                  f"{o['items']:,} รายการ ({m(o['amount'])} บาท) — บันทึกแล้วจะถามว่าแทนที่หรือไม่</span>")
        else:
            self.fy_state.setText(f"<span style='color:{GREEN}'>ปี {fy} ยังไม่มีข้อบัญญัติในโปรแกรม</span>")
        if not self.items:
            self.save_btn.setEnabled(False)
            self.save_btn.setText(T("บันทึกเป็นข้อบัญญัติ"))
            return
        meta = self.meta
        n = sum(1 for it in self.items if it["amount"])
        stated = meta.get("total_stated")
        ok = stated is None or abs(stated - meta["total"]) < 1
        plans = "".join(f"<tr><td>{escape(k)}</td><td align=right>{m(v)}</td></tr>"
                        for k, v in meta["plans"].items())
        mismatch = meta.get("fy") and meta["fy"] != fy
        self.summary.setText(
            f"<b>อ่านได้ {n:,} รายการที่มีงบประมาณ</b> (ทั้งหมด {len(self.items):,} บรรทัด) · "
            f"รวม <b>{m(meta['total'])}</b> บาท · "
            + (f"<span style='color:{GREEN}'>ตรงกับ «งบประมาณรายจ่ายทั้งสิ้น» ในเล่ม {m(stated)} ✓</span>"
               if stated is not None and ok else
               f"<span style='color:{RED}'>ไม่ตรงกับยอดในเล่ม {m(stated)} — ตรวจก่อนบันทึก</span>"
               if stated is not None else "")
            + f" · มีคำชี้แจง {meta.get('details', 0):,} รายการ"
            + (f"<br><span style='color:{RED}'>เอกสารเป็นข้อบัญญัติปี {meta['fy']} ไม่ใช่ปี {fy}</span>"
               if mismatch else "")
            + f"<br><span style='color:{MUTED}'>ยอดแต่ละแผนงานแสดงในรายการด้านล่าง "
              "— คลิกรายการเพื่อดูคำชี้แจง</span>")
        del plans
        self.save_btn.setEnabled(True)
        self.save_btn.setText(f"{T('บันทึกเป็นข้อบัญญัติปี')} {fy}")

    # ------------------------------------------------------------ saving
    def save(self):
        fy = self.fy.value()
        s = self.store
        if self.meta.get("fy") and self.meta["fy"] != fy and QMessageBox.question(
                self, PRODUCT_TH, f"เอกสารนี้เป็นข้อบัญญัติปี {self.meta['fy']}\n"
                f"ยืนยันบันทึกเป็นงบประมาณปี {fy} หรือไม่?") != QMessageBox.Yes:
            return
        replace = False
        if s.budget_items(fy):
            ans = QMessageBox.question(
                self, PRODUCT_TH, f"มีข้อบัญญัติปี {fy} อยู่แล้ว\nใช่ = แทนที่ทั้งหมด "
                "(รายการที่มีการจัดซื้ออ้างอิงจะลบไม่ได้) · ไม่ใช่ = เพิ่มต่อท้าย",
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel)
            if ans == QMessageBox.Cancel:
                return
            replace = ans == QMessageBox.Yes
        rows = [list(r) for r in self.rows]
        if self.meta.get("fy") and self.meta["fy"] != fy:      # save under the year chosen
            rows[0] = [str(h).replace(f"ประมาณการ {self.meta['fy']}", f"ประมาณการ {fy}") for h in rows[0]]
        try:
            got = s.import_ordinance(rows, replace=replace, fy=fy, title=self.title.text().strip(),
                                     agency=self.agency.text().strip(), source=self.source.text().strip())
            stated = self.meta.get("total_stated")
            if stated:
                s.save_ordinance(fy, total=stated)
        except Exception as exc:  # noqa: BLE001
            return error(self, exc)
        QMessageBox.information(self, PRODUCT_TH, f"บันทึกข้อบัญญัติปี {got['fy']} แล้ว {got['budget']:,} รายการ")
        self.accept()


__all__ = ["OrdinanceDialog", "QWidget"]
