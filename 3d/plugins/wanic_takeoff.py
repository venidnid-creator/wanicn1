# SPDX-License-Identifier: GPL-3.0-or-later
# WANICNSURVEY 3D — "WANIC ถอดปริมาณ" (quantity takeoff & Thai BOQ).
# Developed for WANICNSURVEY by นายเวนิช ธัมมะวงษ์ วิศวกรสำรวจ, 2569.
"""ถอดปริมาณและประมาณราคาจากโมเดล 3 มิติ.

A tab in the side tray holds the document's price list (รายการราคา). Each
line binds to objects by layer / material / BIM class / name, measures them
(volume, area, length, count, steel weight…) and prices the quantity with a
material and a labour unit price. Totals carry Factor F and VAT, and the
BOQ exports to Excel (.xlsx, Thai ปร.4 layout) or CSV.

«ตัวตรวจราคา» paints the model: green = priced, red = no price line yet,
orange = a line needs a quantity the object cannot give (e.g. an open shell
has no volume). The pricing logic lives in :mod:`core.wanic_takeoff`.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog,
    QFormLayout, QGridLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QMessageBox, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout,
    QWidget,
)

from core import wanic_takeoff as T

TITLE = "ถอดปริมาณ"

COLS = ["หมวด", "รหัส", "รายการ", "ผูกกับ", "ค่า", "คิดจาก", "หน่วย",
        "ตัวคูณ", "ค่าวัสดุ/หน่วย", "ค่าแรง/หน่วย", "ปริมาณ", "รวมเงิน (บาท)"]
C_CAT, C_CODE, C_DESC, C_BY, C_VALUE, C_QTY, C_UNIT, C_FACTOR, C_MAT, \
    C_LAB, C_QUANTITY, C_TOTAL = range(12)

STATUS_COLORS = {"ok": QColor(46, 160, 67), "no_rate": QColor(220, 53, 69),
                 "problem": QColor(240, 140, 30)}
MAX_PAINT_FACES = 30000


def _money(x: float) -> str:
    return f"{x:,.2f}"


class TakeoffPanel(QWidget):
    def __init__(self, app, parent=None):
        super().__init__(parent)
        self.app = app
        self._loading = False
        self._items: list = []
        self._result = None
        self._candidates = {k: [] for k in T.MATCH_BY}
        self._paint_on = False
        self._paint_cache = None

        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.setSpacing(6)

        head = QLabel("<b>WANIC ถอดปริมาณ</b> — ถอดปริมาณและประมาณราคา (BOQ)")
        head.setWordWrap(True)
        lay.addWidget(head)

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        self.project = QLineEdit()
        self.owner = QLineEdit()
        self.location = QLineEdit()
        for w, label in ((self.project, "โครงการ"), (self.owner, "เจ้าของงาน"),
                         (self.location, "สถานที่")):
            w.editingFinished.connect(self._save)
            form.addRow(label, w)
        row = QHBoxLayout()
        self.factor_f = QDoubleSpinBox()
        self.factor_f.setDecimals(4)
        self.factor_f.setRange(0.0001, 10.0)
        self.factor_f.setSingleStep(0.01)
        self.factor_f.setValue(1.0)
        self.vat = QDoubleSpinBox()
        self.vat.setDecimals(2)
        self.vat.setRange(0.0, 100.0)
        self.vat.setSuffix(" %")
        self.vat.setValue(7.0)
        for w in (self.factor_f, self.vat):
            w.editingFinished.connect(self._save)
        row.addWidget(QLabel("Factor F"))
        row.addWidget(self.factor_f)
        row.addSpacing(10)
        row.addWidget(QLabel("ภาษีมูลค่าเพิ่ม"))
        row.addWidget(self.vat)
        row.addStretch(1)
        form.addRow(row)
        lay.addLayout(form)

        btns = QGridLayout()
        btns.setSpacing(4)

        def button(text, tip, fn, r, c):
            b = QPushButton(text)
            b.setToolTip(tip)
            b.clicked.connect(lambda _=False: fn())
            btns.addWidget(b, r, c)
            return b

        button("➕ เพิ่มรายการ", "เพิ่มรายการราคาใหม่", self.add_rate, 0, 0)
        button("➖ ลบรายการ", "ลบรายการที่เลือกในตาราง", self.delete_rates, 0, 1)
        button("📋 รายการตัวอย่าง",
               "เพิ่มรายการงานก่อสร้างพื้นฐานตามคลาส BIM (ราคาเริ่มที่ 0 — "
               "กรอกราคาของท่านเอง)", self.add_samples, 0, 2)
        button("📥 นำเข้าราคา…", "อ่านบัญชีราคาจากไฟล์ CSV", self.import_rates, 1, 0)
        button("📤 บันทึกบัญชีราคา…", "บันทึกบัญชีราคาเป็น CSV เพื่อใช้กับโครงการอื่น",
               self.export_rates, 1, 1)
        button("📊 ส่งออก BOQ…", "ส่งออกแบบสรุปราคา (Excel .xlsx หรือ CSV)",
               self.export_boq, 1, 2)
        lay.addLayout(btns)

        self.checker = QCheckBox("ตัวตรวจราคา — ระบายสีบนโมเดล "
                                 "(เขียว มีราคา · แดง ยังไม่มีราคา · ส้ม วัดไม่ได้)")
        self.checker.toggled.connect(self._toggle_paint)
        lay.addWidget(self.checker)

        self.table = QTableWidget(0, len(COLS))
        self.table.setHorizontalHeaderLabels(COLS)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.DoubleClicked
                                   | QAbstractItemView.EditKeyPressed
                                   | QAbstractItemView.AnyKeyPressed)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.Interactive)
        hh.setStretchLastSection(True)
        for c, w in ((C_CAT, 110), (C_CODE, 50), (C_DESC, 200), (C_BY, 110),
                     (C_VALUE, 130), (C_QTY, 150), (C_UNIT, 60),
                     (C_FACTOR, 55), (C_MAT, 90), (C_LAB, 90),
                     (C_QUANTITY, 90)):
            self.table.setColumnWidth(c, w)
        self.table.itemChanged.connect(self._item_changed)
        lay.addWidget(self.table, 1)

        self.totals = QLabel()
        self.totals.setWordWrap(True)
        self.totals.setTextInteractionFlags(Qt.TextSelectableByMouse)
        lay.addWidget(self.totals)
        self.summary = QLabel()
        self.summary.setWordWrap(True)
        self.summary.setStyleSheet("color: palette(mid);")
        lay.addWidget(self.summary)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(300)
        self._timer.timeout.connect(self.refresh)

    # ---- document data ----------------------------------------------------
    def data(self) -> dict:
        d = self.app.document_data(None) or T.default_data()
        d.setdefault("rates", [])
        base = T.default_data()["settings"]
        base.update(d.get("settings") or {})
        d["settings"] = base
        return d

    def _write(self, data: dict) -> None:
        self._loading = True
        try:
            self.app.set_document_data(data)
        finally:
            self._loading = False
        self.refresh()

    def _rates_from_table(self) -> list:
        rates = []
        old = {r.get("id"): r for r in self.data()["rates"]}
        for r in range(self.table.rowCount()):
            rid = self.table.item(r, C_CAT).data(Qt.UserRole) if self.table.item(r, C_CAT) else ""
            base = dict(old.get(rid) or T.new_rate(id=rid))

            def text(c):
                it = self.table.item(r, c)
                return it.text().strip() if it else ""

            def combo(c):
                w = self.table.cellWidget(r, c)
                if isinstance(w, QComboBox):
                    data = w.currentData()
                    return data if data is not None else w.currentText().strip()
                return text(c)
            base.update(category=text(C_CAT), code=text(C_CODE),
                        desc=text(C_DESC), by=combo(C_BY),
                        value=combo(C_VALUE) if combo(C_BY) != "all" else "",
                        qty=combo(C_QTY), unit=text(C_UNIT),
                        factor=T._num(text(C_FACTOR), 1.0) or 1.0,
                        mat=T._num(text(C_MAT)), lab=T._num(text(C_LAB)))
            rates.append(base)
        return rates

    def _save(self) -> None:
        if self._loading:
            return
        d = self.data()
        d["rates"] = self._rates_from_table()
        d["settings"].update(project=self.project.text().strip(),
                             owner=self.owner.text().strip(),
                             location=self.location.text().strip(),
                             factor_f=self.factor_f.value(),
                             vat=self.vat.value())
        if d != self.data():
            self._write(d)

    def _next_id(self, rates) -> str:
        used = {r.get("id") for r in rates}
        n = len(rates) + 1
        while f"r{n}" in used:
            n += 1
        return f"r{n}"

    # ---- actions --------------------------------------------------------------
    def add_rate(self, **kw) -> None:
        d = self.data()
        d["rates"] = self._rates_from_table()
        rate = T.new_rate(id=self._next_id(d["rates"]), **kw)
        if not rate.get("unit"):
            rate["unit"] = T.QTY_KINDS.get(rate["qty"], ("", ""))[1]
        d["rates"].append(rate)
        self._write(d)
        self.table.scrollToBottom()
        self.table.selectRow(self.table.rowCount() - 1)

    def delete_rates(self) -> None:
        rows = sorted({i.row() for i in self.table.selectedIndexes()},
                      reverse=True)
        if not rows:
            return
        d = self.data()
        rates = self._rates_from_table()
        for r in rows:
            if 0 <= r < len(rates):
                del rates[r]
        d["rates"] = rates
        self._write(d)

    def add_samples(self) -> None:
        d = self.data()
        d["rates"] = self._rates_from_table()
        have = {(r.get("code"), r.get("desc")) for r in d["rates"]}
        for s in T.sample_rates():
            if (s["code"], s["desc"]) in have:
                continue
            s["id"] = self._next_id(d["rates"])
            d["rates"].append(s)
        self._write(d)

    def import_rates(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "นำเข้าบัญชีราคา", "", "บัญชีราคา CSV (*.csv)")
        if not path:
            return
        try:
            text = Path(path).read_text(encoding="utf-8-sig")
        except UnicodeDecodeError:
            text = Path(path).read_text(encoding="cp874", errors="replace")
        except OSError as e:
            QMessageBox.warning(self, TITLE, f"อ่านไฟล์ไม่ได้: {e}")
            return
        new = T.rates_from_csv(text)
        if not new:
            QMessageBox.information(self, TITLE, "ไม่พบรายการราคาในไฟล์นี้")
            return
        d = self.data()
        d["rates"] = self._rates_from_table()
        if d["rates"]:
            ans = QMessageBox.question(
                self, TITLE,
                f"พบ {len(new)} รายการ\n\nกด «Yes» เพื่อแทนที่บัญชีราคาเดิม\n"
                "กด «No» เพื่อต่อท้ายรายการเดิม",
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel)
            if ans == QMessageBox.Cancel:
                return
            if ans == QMessageBox.Yes:
                d["rates"] = []
        for r in new:
            r["id"] = self._next_id(d["rates"])
            d["rates"].append(r)
        self._write(d)

    def export_rates(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "บันทึกบัญชีราคา", "บัญชีราคา.csv", "บัญชีราคา CSV (*.csv)")
        if not path:
            return
        try:
            Path(path).write_text(T.rates_to_csv(self._rates_from_table()),
                                  encoding="utf-8")
        except OSError as e:
            QMessageBox.warning(self, TITLE, f"บันทึกไม่ได้: {e}")

    def export_boq(self) -> None:
        self.refresh()
        if self._result is None or not self._result["lines"]:
            QMessageBox.information(
                self, TITLE, "ยังไม่มีรายการราคา — กด «เพิ่มรายการ» หรือ "
                "«รายการตัวอย่าง» ก่อน")
            return
        name = (self.data()["settings"].get("project") or "BOQ").strip()
        safe = "".join(ch for ch in name if ch not in '\\/:*?"<>|') or "BOQ"
        path, flt = QFileDialog.getSaveFileName(
            self, "ส่งออกแบบสรุปราคา", f"{safe}.xlsx",
            "Excel (*.xlsx);;CSV (*.csv)")
        if not path:
            return
        settings = self.data()["settings"]
        try:
            if path.lower().endswith(".csv") or flt.startswith("CSV"):
                if not path.lower().endswith(".csv"):
                    path += ".csv"
                Path(path).write_text(T.boq_csv(self._result, settings),
                                      encoding="utf-8")
            else:
                if not path.lower().endswith(".xlsx"):
                    path += ".xlsx"
                Path(path).write_bytes(
                    T.boq_xlsx_bytes(self._result, settings, self._items))
        except OSError as e:
            QMessageBox.warning(self, TITLE, f"บันทึกไม่ได้: {e}")
            return
        flash = getattr(self.app.viewport, "flash_status", None)
        if callable(flash):
            flash(f"ส่งออก BOQ แล้ว: {path}")

    def rate_from_selection(self, selection) -> None:
        """Add a price line bound to the selected object's BIM class,
        layer or material (whichever it has, in that order)."""
        from core.layers import layer_of
        ent = next(iter(selection), None)
        if ent is None:
            return
        ifc = getattr(ent, "ifc", None)
        attrs = getattr(ent, "attrs", None) or {}
        if not ifc:
            ifc = attrs.get("ifc")
        if isinstance(ifc, dict):
            ifc = ifc.get("class")
        if ifc:
            by, value = "ifc", str(ifc)
        else:
            layer = layer_of(ent)
            mat = attrs.get("mat") or getattr(ent, "material", None)
            if layer and layer != "Layer 0":
                by, value = "layer", layer
            elif mat:
                by, value = "material", str(mat)
            else:
                by, value = "layer", layer or "Layer 0"
        qty = "volume" if getattr(ent, "mesh", None) is not None else "area"
        self.add_rate(by=by, value=value, qty=qty, desc=value,
                      unit=T.QTY_KINDS[qty][1])

    # ---- display ----------------------------------------------------------------
    def schedule(self) -> None:
        if not self._loading:
            self._timer.start()

    def refresh(self) -> None:
        try:
            self._items = T.collect_items(self.app.scene)
        except Exception as e:                       # never break the app
            self._items = []
            self.summary.setText(f"วัดโมเดลไม่ได้: {e}")
        self._candidates = T.match_candidates(self._items)
        d = self.data()
        self._result = T.compute(self._items, d)
        self._paint_cache = None
        self._fill(d)
        if self._paint_on:
            self.app.viewport.update()

    def _combo(self, options, current, editable=False):
        cb = QComboBox()
        cb.setEditable(editable)
        for key, label in options:
            cb.addItem(label, key)
        i = cb.findData(current)
        if i < 0 and editable and current:
            cb.addItem(current, current)
            i = cb.count() - 1
        cb.setCurrentIndex(max(i, 0))
        if editable:
            cb.lineEdit().editingFinished.connect(self._save)
            cb.activated.connect(lambda _i: self._save())
        else:
            cb.currentIndexChanged.connect(lambda _i: self._combo_changed())
        return cb

    def _combo_changed(self) -> None:
        if self._loading:
            return
        # A new quantity kind brings its usual unit with it.
        sender = self.sender()
        for r in range(self.table.rowCount()):
            if self.table.cellWidget(r, C_QTY) is sender:
                unit = T.QTY_KINDS.get(sender.currentData(), ("", ""))[1]
                it = self.table.item(r, C_UNIT)
                if unit and it is not None:
                    self._loading = True
                    it.setText(unit)
                    self._loading = False
        self._save()

    def _item_changed(self, _item) -> None:
        if not self._loading:
            self._save()

    def _fill(self, d) -> None:
        self._loading = True
        try:
            self.project.setText(d["settings"].get("project", ""))
            self.owner.setText(d["settings"].get("owner", ""))
            self.location.setText(d["settings"].get("location", ""))
            self.factor_f.setValue(T._num(d["settings"].get("factor_f"), 1.0) or 1.0)
            self.vat.setValue(T._num(d["settings"].get("vat"), 7.0))
            lines = self._result["lines"]
            sel = self.table.currentRow()
            self.table.setRowCount(len(lines))
            for r, ln in enumerate(lines):
                def put(c, text, editable=True, align=None, tip=None):
                    it = QTableWidgetItem(text)
                    if not editable:
                        it.setFlags(it.flags() & ~Qt.ItemIsEditable)
                    if align is not None:
                        it.setTextAlignment(align)
                    if tip:
                        it.setToolTip(tip)
                    self.table.setItem(r, c, it)
                    return it
                put(C_CAT, ln.get("category", "")).setData(Qt.UserRole, ln.get("id", ""))
                put(C_CODE, ln.get("code", ""))
                put(C_DESC, ln.get("desc", ""))
                by = ln.get("by", "layer")
                self.table.setCellWidget(r, C_BY, self._combo(
                    list(T.MATCH_BY.items()), by))
                values = [(v, v) for v in self._candidates.get(by, [])]
                vc = self._combo(values, ln.get("value", ""), editable=True)
                vc.setEnabled(by != "all")
                self.table.setCellWidget(r, C_VALUE, vc)
                self.table.setCellWidget(r, C_QTY, self._combo(
                    [(k, v[0]) for k, v in T.QTY_KINDS.items()],
                    ln.get("qty", "area")))
                put(C_UNIT, ln.get("unit", ""))
                right = int(Qt.AlignRight | Qt.AlignVCenter)
                put(C_FACTOR, f"{T._num(ln.get('factor'), 1.0):g}", align=right)
                put(C_MAT, _money(T._num(ln.get("mat"))), align=right)
                put(C_LAB, _money(T._num(ln.get("lab"))), align=right)
                tip = None
                if ln["problems"]:
                    tip = "วัดไม่ได้:\n" + "\n".join(
                        f"• {a} — {b}" for a, b in ln["problems"][:20])
                q = put(C_QUANTITY, f"{ln['quantity']:,.3f}", False, right,
                        tip or f"วัตถุที่นับรวม {len(ln['items'])} รายการ")
                if ln["problems"]:
                    q.setForeground(STATUS_COLORS["problem"])
                elif not ln["items"]:
                    q.setForeground(STATUS_COLORS["no_rate"])
                    q.setToolTip("ยังไม่มีวัตถุที่ตรงกับรายการนี้")
                put(C_TOTAL, _money(ln["total"]), False, right)
            if 0 <= sel < len(lines):
                self.table.setCurrentCell(sel, 0)
            res = self._result
            parts = [f"รวมค่าวัสดุและค่าแรง <b>{_money(res['subtotal'])}</b> บาท"]
            if abs(res["factor_f"] - 1.0) > 1e-12:
                parts.append(f"× Factor F {res['factor_f']:g} = {_money(res['after_f'])}")
            if res["vat_pct"]:
                parts.append(f"VAT {res['vat_pct']:g}% {_money(res['vat'])}")
            parts.append(f"<br><b>รวมทั้งสิ้น {_money(res['grand'])} บาท</b> "
                         f"({T.baht_text(res['grand'])})")
            self.totals.setText(" · ".join(parts[:-1]) + parts[-1])
            st = list(res["status"].values())
            self.summary.setText(
                f"วัตถุในโมเดล {len(st)} รายการ — มีราคา {st.count('ok')} · "
                f"ยังไม่มีราคา {st.count('no_rate')} · "
                f"วัดไม่ได้ {st.count('problem')}")
        finally:
            self._loading = False

    # ---- viewport colouring ---------------------------------------------------
    def _toggle_paint(self, on: bool) -> None:
        self._paint_on = bool(on)
        if on:
            self.refresh()
        self.app.viewport.update()

    def paint(self, vp, painter) -> None:
        if not self._paint_on or self._result is None:
            return
        from PySide6.QtCore import QPointF
        from PySide6.QtGui import QPainter, QPen, QPolygonF
        painter.setRenderHint(QPainter.Antialiasing)
        status = self._result["status"]
        budget = MAX_PAINT_FACES
        for it in self._items:
            color = STATUS_COLORS.get(status.get(it["key"], "no_rate"))
            fill = QColor(color)
            fill.setAlpha(90)
            edge = QColor(color)
            edge.setAlpha(200)
            painter.setPen(QPen(edge, 1))
            painter.setBrush(fill)
            for f in it["faces"]:
                if budget <= 0:
                    return
                budget -= 1
                pts = []
                for v in getattr(f, "loop", ()):
                    q = vp.world_to_pixel(v.position)
                    if q is None:
                        pts = None
                        break
                    pts.append(QPointF(*q))
                if pts and len(pts) >= 3:
                    painter.drawPolygon(QPolygonF(pts))


def _join_tray(window, dock) -> None:
    tray = getattr(window, "tray", None)
    try:
        if (tray is None or dock.isFloating() or dock.isHidden()
                or window.tabifiedDockWidgets(dock)
                or window.dockWidgetArea(dock) != window.dockWidgetArea(tray)):
            return
        window.tabifyDockWidget(tray, dock)
        tray.raise_()
    except Exception:
        pass


def setup(app) -> None:
    panel = TakeoffPanel(app)
    dock = app.add_panel(TITLE, panel)
    app.window._wanic_takeoff = panel
    app.on_document_changed(panel.schedule)
    app.add_overlay(panel.paint)

    def show():
        app.show_panel(dock)
        dock.raise_()
        panel.refresh()

    app.add_menu_action("WANIC ถอดปริมาณ…", show,
                        tip="ถอดปริมาณวัสดุและประมาณราคาจากโมเดล "
                            "ส่งออก BOQ เป็น Excel")

    def context(menu, selection):
        if not selection:
            return

        def go():
            show()
            panel.rate_from_selection(selection)
        menu.addAction("ตั้งราคาให้วัตถุที่เลือก (ถอดปริมาณ)",
                       lambda: QTimer.singleShot(0, go))

    app.add_context_menu(context)
    QTimer.singleShot(0, lambda: _join_tray(app.window, dock))
    QTimer.singleShot(0, panel.refresh)
