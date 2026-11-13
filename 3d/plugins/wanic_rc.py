# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
"""WANIC ออกแบบโครงสร้าง คสล.: the structure of the building designer's
plan, step by step — grid, footings and piles, stumps, ground beams,
slabs, columns and beams, the roof frame, then the reinforcement and its
take-off. Every member type (เบอร์) is edited here: its size and bars,
checked against the detailing rules (:mod:`core.wanic_rc`) as it is typed.

The data is the building designer's own (its library of marks): this
panel is a second door onto it, so the plan, the 3D model, the drawings
and the BOQ all follow what is set here."""
from __future__ import annotations

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QFileDialog, QHBoxLayout, QHeaderView, QLabel, QListWidget,
                               QListWidgetItem, QMessageBox, QPushButton, QTableWidget,
                               QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget)

from core import wanic_building as B
from core import wanic_rc as R

TITLE = "ออกแบบโครงสร้าง คสล."
STEPS = [("grid", "1  กริด / เส้นแกน"), ("footing", "2  ฐานราก + เข็ม"), ("stump", "3  ตอม่อ"),
         ("ground", "4  คานคอดิน"), ("slab", "5  พื้น คสล."), ("upper", "6  เสา + คาน"),
         ("roof", "7  โครงหลังคา"), ("rebar", "8  เหล็กเสริม/BOQ"), ("calc", "9  คำนวณโครงสร้าง")]
#: which library marks each step edits, and which parts of the model it selects
STEP_MARKS = {"footing": ("footing",), "stump": ("stump",), "ground": ("beam:ground",),
              "slab": ("slab",), "upper": ("column", "beam:upper")}
STEP_KINDS = {"footing": ("footing", "pile", "cap", "lean", "sand"), "stump": ("stump",),
              "ground": ("beam",), "slab": ("slab",), "upper": ("column", "beam"),
              "roof": ("ridge", "hip", "rafter", "purlin", "post", "wallplate", "tiebeam", "strut",
                       "brace", "rbeam", "valley")}


class RCPanel(QWidget):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.step = "footing"
        self._loading = False
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(300)
        self._timer.timeout.connect(self._refresh_if_shown)
        self._stale = False
        lay = QHBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)
        self.steps = QListWidget()
        self.steps.setFixedWidth(176)
        self.steps.setWordWrap(True)
        for key, label in STEPS:
            it = QListWidgetItem(label)
            it.setData(Qt.UserRole, key)
            it.setSizeHint(QSize(168, 40))
            self.steps.addItem(it)
        self.steps.currentRowChanged.connect(self._pick)
        lay.addWidget(self.steps)
        col = QVBoxLayout()
        self.title = QLabel()
        self.title.setStyleSheet("font-size: 15px; font-weight: 700;")
        col.addWidget(self.title)
        self.note = QLabel()
        self.note.setWordWrap(True)
        col.addWidget(self.note)
        self.table = QTableWidget(0, 0)
        self.table.verticalHeader().hide()
        self.table.itemChanged.connect(self._edited)
        self.table.currentCellChanged.connect(lambda *_: self._show_checks())
        self.table.cellDoubleClicked.connect(lambda *_: self.fix_member() if self.step == "calc" else None)
        col.addWidget(self.table, 2)
        self.checks = QTextEdit()
        self.checks.setReadOnly(True)
        self.checks.setMinimumHeight(120)
        col.addWidget(self.checks, 1)
        from core.wanic_calc_view import DiagramWidget
        self.diagram = DiagramWidget()
        self.diagram.setMinimumHeight(300)
        col.addWidget(self.diagram, 2)
        self._calc = None
        row = QHBoxLayout()
        self.fix = QPushButton("ปรับเหล็กให้ผ่านขั้นต่ำ")
        self.fix.setToolTip("เพิ่มจำนวนเหล็ก / ลดระยะเรียง / เพิ่มขนาดเหล็ก ให้เบอร์ที่เลือกผ่านการตรวจ "
                            "(ไม่เปลี่ยนขนาดหน้าตัด)")
        self.fix.clicked.connect(self.fix_selected)
        row.addWidget(self.fix)
        self.advice_btn = QPushButton("แก้ตามคำแนะนำ (ทุกเบอร์)")
        self.advice_btn.setToolTip("ปรับขนาด/เหล็กของทุกเบอร์ที่ไม่ผ่าน ตามคำแนะนำ แล้วคำนวณซ้ำจนผ่าน "
                                   "(รวมข้อกำหนดเหล็กขั้นต่ำ) — ถามยืนยันก่อน")
        self.advice_btn.clicked.connect(self.apply_advice)
        row.addWidget(self.advice_btn)
        self.fix_one_btn = QPushButton("แก้ชิ้นที่เลือกให้ผ่าน…")
        self.fix_one_btn.setStyleSheet("font-weight: 700; color: #B91C1C;")
        self.fix_one_btn.setToolTip("เลือกแถวที่ไม่ผ่าน (หรือดับเบิลคลิกแถว) — กรอก/แก้ค่าที่แนะนำ "
                                    "แล้วอัปเดตโมเดลและคำนวณใหม่")
        self.fix_one_btn.clicked.connect(self.fix_member)
        row.addWidget(self.fix_one_btn)
        self.select_btn = QPushButton("เลือกชิ้นส่วนในโมเดล")
        self.select_btn.clicked.connect(self.select_in_model)
        row.addWidget(self.select_btn)
        self.build_btn = QPushButton("สร้าง/อัปเดตโครงสร้างในโมเดล")
        self.build_btn.setStyleSheet("font-weight: 700;")
        self.build_btn.clicked.connect(self.build_model)
        row.addWidget(self.build_btn)
        self.export_btn = QPushButton("รายงานโครงสร้าง (.xlsx)")
        self.export_btn.clicked.connect(self.export)
        row.addWidget(self.export_btn)
        self.basis_btn = QPushButton("ค่าที่ใช้ออกแบบ…")
        self.basis_btn.setToolTip("วิธีออกแบบ SDM/WSD · fc′ · fy · น้ำหนักบรรทุกจร · ดิน · เสาเข็ม")
        self.basis_btn.clicked.connect(self.edit_basis)
        row.addWidget(self.basis_btn)
        self.pdf_btn = QPushButton("รายการคำนวณ (.pdf)")
        self.pdf_btn.clicked.connect(self.export_pdf)
        row.addWidget(self.pdf_btn)
        self.book_btn = QPushButton("รูปเล่มรายการคำนวณ A4 (.pdf)")
        self.book_btn.setToolTip("ปก · ข้อกำหนด · คานทุกแนวพร้อม Load/Shear/Moment Diagram และตาราง · "
                                 "การ์ดเสาทุกชั้น · ฐานราก · หลังคา · สรุป — พร้อมช่องลงนามผู้คำนวณ")
        self.book_btn.clicked.connect(self.export_book)
        self.lat_btn = QPushButton("แรงด้านข้าง (แผ่นดินไหว/ลม)…")
        self.lat_btn.setToolTip("มยผ. 1301/1302-61 · มยผ. 1311-50 หรือสูตรเดิม · แรงแต่ละชั้น · ตรวจเสา P-M")
        self.lat_btn.clicked.connect(self.edit_lateral)
        row.addWidget(self.book_btn)
        row.addWidget(self.lat_btn)
        self.est_btn = QPushButton("ประมาณราคาเอกชน 8 หมวด…")
        self.est_btn.clicked.connect(self.edit_estimate)
        row.addWidget(self.est_btn)
        self.loads_btn = QPushButton("น้ำหนักเพิ่มบนคาน…")
        self.loads_btn.setToolTip("น้ำหนักจุด (ถังน้ำ แอร์) / น้ำหนักแผ่ (ผนังบนคาน ระเบียง) ที่ไม่มีในผัง")
        self.loads_btn.clicked.connect(self.edit_beam_loads)
        row.addWidget(self.loads_btn)
        self.cant_btn = QPushButton("คานยื่น…")
        self.cant_btn.setToolTip("คานยื่นออกจากเสา ปลายลอย (ระเบียง กันสาด)")
        self.cant_btn.clicked.connect(self.edit_cantilevers)
        row.addWidget(self.cant_btn)
        self.stair_btn = QPushButton("บันได คสล.…")
        self.stair_btn.setToolTip("บันไดช่วงตรง / ตัว L / สองช่วง — ขนาดขั้นตามกฎกระทรวง 55 · ท้องบันได · เหล็ก · คานชานพัก")
        self.stair_btn.clicked.connect(self.edit_stairs)
        row.addWidget(self.stair_btn)
        self.free_btn = QPushButton("ชิ้นส่วนเขียนอิสระ…")
        self.free_btn.setToolTip("คาน/เสา/ผนัง จากเส้นที่วาดในโมเดล (ตรง เอียง โค้ง) — "
                                 "วาดเส้น → เลือก → คลิกขวา «แปลงเส้นที่เลือกเป็น…»")
        self.free_btn.clicked.connect(self.edit_free)
        row.addWidget(self.free_btn)
        self.pile_btn = QPushButton("เสาเข็ม 2 ขนาด / กำลังเข็ม…")
        self.pile_btn.setToolTip("เสาเข็ม P1/P2 · กำลังจากผลทดสอบสถิต/พลวัต · บันทึกการตอก (Hiley) · ข้อมูลเจาะดิน")
        self.pile_btn.clicked.connect(self.edit_piles)
        row.addWidget(self.pile_btn)
        self.check_btn = QPushButton("Checkload (ตรวจน้ำหนักลงเสา)…")
        self.check_btn.setToolTip("Wcol · Wcol-Area · Wfloor ทุกเสา เทียบค่าเฉลี่ยทั้งอาคารและช่วงปกติ")
        self.check_btn.clicked.connect(self.show_checkload)
        row.addWidget(self.check_btn)
        row.addStretch(1)
        col.addLayout(row)
        self.roof_row = QWidget()
        rr = QHBoxLayout(self.roof_row)
        rr.setContentsMargins(0, 0, 0, 0)
        rr.addWidget(QLabel("ทรงหลังคา:"))
        self.roof_btns = {}
        for k, v in B.ROOF_TYPES.items():
            b = QPushButton(v.split(" (")[0])
            b.setCheckable(True)
            b.clicked.connect(lambda _=False, key=k: self.set_roof(key))
            self.roof_btns[k] = b
            rr.addWidget(b)
        rr.addSpacing(12)
        for text, preset in (("โครงเหล็ก", B.STEEL_FRAME), ("โครงไม้", B.TIMBER_FRAME)):
            b = QPushButton(text)
            b.clicked.connect(lambda _=False, p=preset: self.set_frame(p))
            rr.addWidget(b)
        rr.addSpacing(12)
        self.truss_btn = QPushButton("ออกแบบ Truss…")
        self.truss_btn.setToolTip("โครงถักเหล็ก Howe / Pratt / Fink / Warren / โค้ง — วิเคราะห์ Matrix "
                                  "เลือกขนาดเหล็กท่อ/กล่อง/ตัวซี และแผ่นเหล็กรองฐาน")
        self.truss_btn.clicked.connect(self.edit_truss)
        rr.addWidget(self.truss_btn)
        self.steel_btn = QPushButton("ออกแบบเหล็กรูปพรรณ…")
        self.steel_btn.setToolTip("เสา H / คาน WF (ASD) จัดกลุ่มตามเบอร์ พร้อมแผ่นเหล็กรองฐาน")
        self.steel_btn.clicked.connect(self.edit_steel)
        rr.addWidget(self.steel_btn)
        self.purlin_btn = QPushButton("แป / Sag Rod / Tie Rod…")
        self.purlin_btn.setToolTip("แปเหล็กตัวซี · เหล็กยึดแป · ค้ำยันทแยง X-Bracing · แปผนังเมทัลชีท")
        self.purlin_btn.clicked.connect(self.edit_purlin)
        rr.addWidget(self.purlin_btn)
        rr.addStretch(1)
        col.addWidget(self.roof_row)
        self.grid_btn = QPushButton("โหมดกริด: สร้างผังจากเส้นแกน…")
        self.grid_btn.setStyleSheet("font-weight: 700;")
        self.grid_btn.setToolTip("กำหนดระยะแกน 1-2-3 / A-B-C และจำนวนชั้น — ห้องทุกช่อง เสาทุกจุดตัด คานตามแนวกริด")
        self.grid_btn.clicked.connect(self.edit_grid)
        col.addWidget(self.grid_btn)
        self.flat_btn = QPushButton("พื้นไร้คาน Flat Slab + Drop Panel (DDM)…")
        self.flat_btn.setToolTip("ความหนาขั้นต่ำ · โมเมนต์แถบเสา/แถบกลาง · เหล็กเสริม · แรงเฉือนทะลุ")
        self.flat_btn.clicked.connect(self.edit_flatslab)
        col.addWidget(self.flat_btn)
        self.status = QLabel()
        self.status.setWordWrap(True)
        col.addWidget(self.status)
        lay.addLayout(col, 1)
        self.steps.setCurrentRow(1)

    # -- the building designer's data
    def building(self):
        return getattr(self.app.window, "_wanic_building", None)

    def data(self):
        bp = self.building()
        return bp.data() if bp is not None else B.default_data()

    def elements(self):
        return B.elements(self.data())

    # -- refreshing
    def schedule(self):
        if not self._loading:
            self._timer.start()

    def _refresh_if_shown(self):
        if not self.isVisible():
            self._stale = True
            return
        self.refresh()

    def showEvent(self, e):
        super().showEvent(e)
        if self._stale:
            self._stale = False
            self.refresh()

    def _pick(self, row):
        if row < 0:
            return
        self.step = STEPS[row][0]
        self.refresh()

    def _marks(self, E):
        """The library marks of the current step, in plan order."""
        lib = E["lib"]
        used_ground = {e["mark"] for e in E["beams"] if e.get("ground")}
        used_upper = {e["mark"] for e in E["beams"] if not e.get("ground")}
        out = []
        for spec in STEP_MARKS.get(self.step, ()):
            kind, _, which = spec.partition(":")
            for m in B.marks_of(lib, kind):
                if which == "ground" and m not in used_ground and not m.startswith("GB"):
                    continue
                if which == "upper" and (m in used_ground and m not in used_upper):
                    continue
                if m not in out:
                    out.append(m)
        return out

    def refresh(self):
        E = self.elements()
        label = dict(STEPS)[self.step]
        self.title.setText(label)
        self.roof_row.setVisible(self.step == "roof")
        self.grid_btn.setVisible(self.step == "grid")
        self.flat_btn.setVisible(self.step == "slab")
        self.fix.setVisible(self.step in STEP_MARKS)
        self.advice_btn.setVisible(self.step == "calc")
        self.fix_one_btn.setVisible(self.step == "calc")
        calc = self.step == "calc"
        self.diagram.setVisible(calc)
        self.checks.setVisible(not calc)
        self.basis_btn.setVisible(calc)
        self.pdf_btn.setVisible(calc)
        self.book_btn.setVisible(calc)
        self.loads_btn.setVisible(calc or self.step in ("upper", "ground"))
        self.cant_btn.setVisible(calc or self.step in ("upper", "ground"))
        self.check_btn.setVisible(calc)
        self.stair_btn.setVisible(calc or self.step == "slab")
        self.pile_btn.setVisible(calc or self.step == "footing")
        self.free_btn.setVisible(calc or self.step == "upper")
        self.select_btn.setVisible(not calc and self.step != "rebar")
        self._loading = True
        try:
            if self.step == "grid":
                self._grid(E)
            elif self.step == "roof":
                self._roof(E)
            elif self.step == "rebar":
                self._rebar(E)
            elif self.step == "calc":
                self._calc_step()
            else:
                self._members(E)
        finally:
            self._loading = False
        self._show_checks()

    def _fill(self, heads, rows, editable=()):
        self.table.clear()
        self.table.setColumnCount(len(heads))
        self.table.setHorizontalHeaderLabels(heads)
        self.table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            for c, v in enumerate(row):
                it = QTableWidgetItem(str(v))
                if c not in editable:
                    it.setFlags(it.flags() & ~Qt.ItemIsEditable)
                self.table.setItem(r, c, it)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.ResizeToContents)
        hh.setStretchLastSection(True)

    def _grid(self, E):
        xs, ys = R.grid_axes(E)
        nx, ny = R.axis_names(len(xs), False), R.axis_names(len(ys), True)
        rows = [(f"แกน {n}", f"{x:.2f}", f"{x - xs[i - 1]:.2f}" if i else "—") for i, (n, x) in
                enumerate(zip(nx, xs))]
        rows += [(f"แกน {n}", f"{y:.2f}", f"{y - ys[i - 1]:.2f}" if i else "—") for i, (n, y) in
                 enumerate(zip(ny, ys))]
        self._fill(["เส้นแกน", "ตำแหน่ง (ม.)", "ระยะช่วง (ม.)"], rows)
        long_ = [r for r in rows if r[2] != "—" and float(r[2]) > 4.0 + 1e-6]
        src = "โหมดกริด" if (self.data() or {}).get("grid") else "ผังห้องในแผง «ออกแบบอาคาร»"
        self.note.setText(f"กริดมาจาก{src} — แกนตัวเลข {len(xs)} เส้น × "
                          f"แกนตัวอักษร {len(ys)} เส้น · เสา {len(E['columns'])} ต้น · "
                          f"ฐานราก {len(E['footings'])} ฐาน"
                          + (f"\n⚠ ช่วงเสาเกิน 4.00 ม. {len(long_)} ช่วง — ตรวจขนาดคานให้รับได้" if long_ else ""))
        self.table.setProperty("marks", [])

    def _members(self, E):
        lib = E["lib"]
        marks = self._marks(E)
        kinds = sorted({lib[m]["kind"] for m in marks}) or ["footing"]
        fields = []
        for k in kinds:
            for key, th in B.LIB_FIELDS[k]:
                if key not in [f[0] for f in fields]:
                    fields.append((key, th))
        count = {}
        for group in ("footings", "stumps", "columns", "beams", "slabs"):
            for e in E[group]:
                count[e["mark"]] = count.get(e["mark"], 0) + 1
        rows = []
        for m in marks:
            sp = lib[m]
            res = R.check(m, sp)
            rows.append([m, B.LIB_KINDS[sp["kind"]], count.get(m, 0)] +
                        [sp.get(k, "") for k, _t in fields] + ["✓ ผ่าน" if res.ok else "⚠ ตรวจสอบ"])
        self._fill(["เบอร์", "ชนิด", "จำนวน"] + [th for _k, th in fields] + ["ผลตรวจ"], rows,
                   editable=range(3, 3 + len(fields)))
        for r, m in enumerate(marks):
            it = self.table.item(r, self.table.columnCount() - 1)
            it.setForeground(QColor("#15803D") if R.check(m, lib[m]).ok else QColor("#B45309"))
        self.table.setProperty("marks", marks)
        self.table.setProperty("fields", [k for k, _t in fields])
        notes = {"footing": "ฐานแผ่ / ฐานบนเสาเข็ม — ขนาด เหล็กตะแกรง ความลึก ทรายรอง คอนกรีตหยาบ และเสาเข็ม",
                 "stump": "ตอม่อจากหลังฐานรากถึงคานคอดิน — หน้าตัด เหล็กยืน เหล็กปลอก",
                 "ground": "คานคอดิน (GB) รับผนังและพื้นชั้นล่าง — หน้าตัด เหล็กบน/ล่าง เหล็กปลอก",
                 "slab": "พื้นวางบนดิน / พื้นวางบนคาน — ความหนาและเหล็กเสริม 2 ทาง",
                 "upper": "เสาและคานชั้นบนถึงคานหลังคา (RB) — หน้าตัดและเหล็กเสริม"}
        self.note.setText(notes.get(self.step, "") + " · แก้ในตารางได้เลย (ดับเบิลคลิกช่อง) "
                          "แล้วกด «สร้าง/อัปเดตโครงสร้างในโมเดล»")

    def _roof(self, E):
        s = E["settings"]
        for k, b in self.roof_btns.items():
            b.setChecked(s.get("roof") == k)
        keys = [("ridge", "อกไก่"), ("hip", "ตะเฆ่สัน"), ("rafter", "จันทัน"), ("purlin", "แป"),
                ("post", "ดั้ง"), ("wallplate", "อะเส"), ("tiebeam", "ขื่อ / คานรับดั้ง"),
                ("strut", "ตุ๊กตา / ค้ำยัน")]
        rows = [(th, s.get(k, ""), "ไม้" if B.is_timber(s.get(k, "")) else "เหล็กรูปพรรณ") for k, th in keys]
        rows += [("ความชัน", f"{float(s['pitch']):g}°", ""), ("ชายคายื่น", f"{float(s['overhang']):.2f} ม.", ""),
                 ("ระยะจันทัน (ไม่เกิน)", f"{float(s['rafter_sp']):.2f} ม.", ""),
                 ("ระยะแป (ไม่เกิน)", f"{float(s['purlin_sp']):.2f} ม.", "")]
        self._fill(["ชิ้นส่วน", "ขนาด", "วัสดุ"], rows)
        self.table.setProperty("marks", [])
        self.note.setText(f"ทรง {B.ROOF_TYPES.get(s.get('roof'), 'ไม่สร้างหลังคา')} · โครงถักวางบนผนัง/แนวเสา "
                          "สมมาตรรอบอกไก่ · ขนาดรายชิ้นแก้ได้ที่แผง «ออกแบบอาคาร» ▸ หลังคา")

    def _rebar(self, E):
        T = R.takeoff(E)
        rows = [(k, v["grade"], f"{v['m']:,.1f}", f"{v['kg']:,.2f}") for k, v in T["bars"].items()]
        rows.append(("รวมเหล็กเสริม", "", "", f"{T['kg']:,.2f}"))
        rows.append(("ลวดผูกเหล็ก", "", "", f"{T['wire']:,.2f}"))
        names = {"footing": "ฐานราก", "stump": "ตอม่อ", "column": "เสา", "beam": "คาน", "slab": "พื้น"}
        for k, v in T["concrete"].items():
            rows.append((f"คอนกรีต{names.get(k, k)}", "", "", f"{v:,.3f} ลบ.ม."))
        rows.append(("คอนกรีตรวม", "", "", f"{sum(T['concrete'].values()):,.3f} ลบ.ม."))
        self._fill(["รายการ", "ชั้นคุณภาพ", "ความยาว (ม.)", "น้ำหนัก (กก.) / ปริมาตร"], rows)
        self.table.setProperty("marks", [])
        res = R.check_library(E["lib"])
        bad = [m for m, r in res.items() if not r.ok]
        self.note.setText(f"เหล็กเสริมทั้งหลัง {T['kg']:,.1f} กก. (เผื่อเศษ {int(R.WASTE * 100)}%) · "
                          f"ทาบเหล็ก 40d (DB) / 48d (RB) · "
                          + (f"⚠ เบอร์ที่ยังไม่ผ่านการตรวจ: {', '.join(bad)}" if bad else "✓ ทุกเบอร์ผ่านการตรวจ"))

    def _calc_step(self):
        from core import wanic_pile as PL
        from core import wanic_calc as C
        try:
            self._calc = C.analyse(self.data())
        except Exception as e:                       # noqa: BLE001 - shown, never a crash
            self._calc = None
            self._fill(["ข้อผิดพลาด"], [(f"คำนวณไม่ได้: {e}",)])
            return
        names = {"roof": "หลังคา", "slab": "พื้น", "beam": "คาน", "column": "เสา", "footing": "ฐานราก/เข็ม",
                 "stair": "บันได"}
        ms = self._calc["members"]
        from core import wanic_advice as AD
        try:
            tips = AD.advice_by_member(self._calc, self.data())
        except Exception:                            # noqa: BLE001 - advice never breaks the table
            tips = {}
        rows = [(names[m.group], m.name, m.demand, m.capacity, f"{m.ratio:.2f}",
                 "✓ ผ่าน" if m.ok else "✗ ไม่ผ่าน", m.reserve_text(), tips.get(m.name, "")) for m in ms]
        self._fill(["กลุ่ม", "ชิ้นส่วน", "แรงที่เกิด", "กำลังที่รับได้", "อัตราส่วน", "ผล",
                    "รับเพิ่มได้อีก (ภาษาง่าย)", "คำแนะนำ (เพิ่มอะไร จุดไหน)"], rows)
        for r_, m in enumerate(ms):
            it = self.table.item(r_, 6)
            if it is not None:
                it.setForeground(QColor("#15803D") if m.ok else QColor("#B91C1C"))
        for r, m in enumerate(ms):
            for c in (4, 5):
                self.table.item(r, c).setForeground(QColor("#15803D") if m.ok else QColor("#B91C1C"))
        self.table.setProperty("marks", [])
        b_ = self._calc["basis"]
        bad = sum(1 for m in ms if not m.ok)
        self.note.setText(
            f"{b_['method']} · fc′ {b_['fc']:g} · LL พื้น {b_['ll_floor']:g} / หลังคา {b_['ll_roof']:g} กก./ตร.ม. · "
            f"ดิน {b_['soil']:g} ตัน/ตร.ม. · {PL.pile_text(self.data(), b_)} — "
            + (f"✗ ไม่ผ่าน {bad} รายการ: แก้ขนาด/เหล็กในขั้น 2–6 แล้วคำนวณใหม่" if bad else "✓ ผ่านทุกรายการ")
            + "\n" + "\n".join(("✓ " if ok else "✗ ") + t for _g, t, ok in C.reserve_summary(ms))
            + "\nเครื่องมือช่วยคำนวณ — ต้องให้วิศวกรโยธาผู้มีใบอนุญาตตรวจและลงนามก่อนก่อสร้าง")
        first = next((i for i, m in enumerate(ms) if m.diagram is not None), -1)
        if first >= 0:
            self.table.setCurrentCell(first, 1)

    def _show_checks(self):
        if self.step == "calc":
            r = self.table.currentRow()
            ms = (self._calc or {}).get("members") or []
            if 0 <= r < len(ms) and ms[r].diagram is not None:
                self.diagram.show_result(ms[r].diagram, ms[r].name)
            else:
                self.diagram.show_result(None)
            return
        marks = self.table.property("marks") or []
        r = self.table.currentRow()
        if not marks:
            self.checks.setPlainText("")
            return
        m = marks[r] if 0 <= r < len(marks) else marks[0]
        res = R.check(m, self.elements()["lib"][m])
        self.checks.setPlainText(f"ตรวจเหล็กเสริม เบอร์ {m}\n" + "\n".join(res.lines()) +
                                 "\n\n(ตรวจข้อกำหนดการเสริมเหล็กขั้นต่ำตามหลัก วสท./ACI และแบบมาตรฐาน "
                                 "— ไม่ใช่การคำนวณกำลัง ต้องให้วิศวกรตรวจรับรอง)")

    # -- editing
    def _edited(self, item):
        if self._loading:
            return
        marks = self.table.property("marks") or []
        fields = self.table.property("fields") or []
        r, c = item.row(), item.column() - 3
        if not (0 <= r < len(marks)) or not (0 <= c < len(fields)):
            return
        bp = self.building()
        if bp is None:
            return
        m, key = marks[r], fields[c]
        spec = dict(self.elements()["lib"][m])
        txt = item.text().strip()
        old = spec.get(key)
        if isinstance(old, (int, float)) and not isinstance(old, bool):
            try:
                spec[key] = type(old)(float(txt)) if isinstance(old, int) else float(txt)
            except ValueError:
                self.status.setText(f"«{txt}» ไม่ใช่ตัวเลข")
                QTimer.singleShot(0, self.refresh)
                return
        else:
            spec[key] = txt
        # สมมาตรและสมดุล: the bars balanced, the shape the designer typed kept
        from core import wanic_advice as AD
        typed = dict(spec)
        spec = AD.balance_spec(spec, keep_shape=True)
        adj = [f"{AD._fmt(k, v)}" for k, v in spec.items() if typed.get(k) != v]
        self._loading = True
        try:
            bp.set_library(m, spec)
        finally:
            self._loading = False
        self.status.setText(f"บันทึกเบอร์ {m} แล้ว" + (f" · จัดให้สมมาตร/สมดุล: {', '.join(adj)}" if adj else "")
                            + " — กด «สร้าง/อัปเดตโครงสร้างในโมเดล» เพื่อปรับโมเดล")
        QTimer.singleShot(0, self.refresh)

    def fix_selected(self):
        marks = self.table.property("marks") or []
        bp = self.building()
        if not marks or bp is None:
            return
        r = max(self.table.currentRow(), 0)
        targets = [marks[r]] if r < len(marks) else marks
        lib = self.elements()["lib"]
        done = []
        for m in targets:
            new = R.suggest(lib[m])
            if new != lib[m]:
                bp.set_library(m, new)
                done.append(f"{m}: " + ", ".join(f"{k} {new[k]}" for k in new if new[k] != lib[m].get(k)))
        self.status.setText("ปรับแล้ว — " + " · ".join(done) if done else "เบอร์นี้ผ่านการตรวจแล้ว")
        self.refresh()

    def set_roof(self, key):
        bp = self.building()
        if bp is None:
            return
        i = bp.roof.findData(key)
        if i >= 0:
            bp.roof.setCurrentIndex(i)
        self.refresh()

    def set_frame(self, preset):
        bp = self.building()
        if bp is not None and hasattr(bp, "_frame_preset"):
            bp._frame_preset(preset)
        self.refresh()

    def build_model(self):
        bp = self.building()
        if bp is None:
            QMessageBox.information(self, TITLE, "ไม่พบแผง «ออกแบบอาคาร»")
            return
        parts = ("structure", "roof") if self.step in ("roof", "rebar", "grid") else ("structure",)
        bp.build(parts)
        self.status.setText(bp.status.text())

    def select_in_model(self):
        kinds = STEP_KINDS.get(self.step)
        if not kinds:
            return
        scene = self.app.scene
        want_ground = {"ground": True, "upper": False}.get(self.step)
        out = []
        for g in scene.groups:
            rec = ((g.ext or {}).get(B.EXT_KEY)) or {}
            if rec.get("kind") not in kinds:
                continue
            if rec.get("kind") == "beam" and want_ground is not None:
                is_gb = any("คานคอดิน" in str(r[1]) for r in rec.get("info") or [] if len(r) > 1)
                if is_gb != want_ground:
                    continue
            out.append(g)
        scene.selection.clear()
        scene.selection.update(out)
        scene.bump_view()
        self.app.viewport.update()
        self.status.setText(f"เลือก {len(out)} ชิ้นในโมเดล" if out else
                            "ยังไม่มีชิ้นส่วนนี้ในโมเดล — กด «สร้าง/อัปเดตโครงสร้างในโมเดล» ก่อน")

    def edit_basis(self):
        from PySide6.QtWidgets import QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout
        from core import wanic_calc as C
        bp = self.building()
        if bp is None:
            return
        d = bp.data()
        b_ = C.basis(d)
        dlg = QDialog(self)
        dlg.setWindowTitle("ค่าที่ใช้ออกแบบ")
        form = QFormLayout(dlg)
        preset = QComboBox()
        preset.addItem("— เลือกชุดค่ามาตรฐาน —", "")
        for k, (th, _v) in C.PRESETS.items():
            preset.addItem(th, k)
        form.addRow("ชุดค่ามาตรฐาน", preset)
        use = QComboBox()
        use.addItem("— เลือกประเภทการใช้อาคาร (กฎกระทรวง ฉบับที่ 6) —", 0.0)
        for th, ll in C.LIVE_LOADS:
            use.addItem(f"{th} — {ll:g} กก./ตร.ม.", ll)
        form.addRow("ประเภทการใช้อาคาร", use)
        meth = QComboBox()
        meth.addItem("กำลัง (SDM) วสท. 011008", "SDM")
        meth.addItem("หน่วยแรงใช้งาน (WSD)", "WSD")
        meth.setCurrentIndex(0 if b_["method"] == "SDM" else 1)
        form.addRow("วิธีออกแบบคอนกรีต", meth)
        spins = {}
        for key, th, lo, hi in (("fc", "fc′ คอนกรีต (กก./ตร.ซม.)", 150, 500),
                                ("ll_floor", "น้ำหนักบรรทุกจรพื้น (กก./ตร.ม.)", 0, 1000),
                                ("ll_roof", "น้ำหนักบรรทุกจรหลังคา (กก./ตร.ม.)", 0, 200),
                                ("finish", "วัสดุปูพื้น + ฝ้า (กก./ตร.ม.)", 0, 300),
                                ("wall_kg_m2", "ผนัง (กก./ตร.ม.)", 0, 500),
                                ("soil", "ดินรับน้ำหนักปลอดภัย (ตัน/ตร.ม.)", 1, 100),
                                ("pile_cap", "เสาเข็มรับน้ำหนักปลอดภัย (ตัน/ต้น)", 1, 200),
                                ("fy_steel", "Fy เหล็กรูปพรรณ (กก./ตร.ซม.)", 1000, 5000)):
            sp_ = QDoubleSpinBox()
            sp_.setRange(lo, hi)
            sp_.setDecimals(1)
            sp_.setValue(float(b_[key]))
            spins[key] = sp_
            form.addRow(th, sp_)
        fy = QDoubleSpinBox()
        fy.setRange(2400, 5000)
        fy.setDecimals(0)
        fy.setValue(float(b_["fy_db"]))
        form.addRow("fy เหล็กข้ออ้อย (กก./ตร.ซม.)", fy)
        spins["fy_db"] = fy

        def apply_preset(_i=0):
            k = preset.currentData()
            if not k:
                return
            v = C.PRESETS[k][1]
            meth.setCurrentIndex(0 if v["method"] == "SDM" else 1)
            spins["fc"].setValue(v["fc"])
            fy.setValue(v["fy_db"])

        def apply_use(_i=0):
            ll = use.currentData()
            if ll:
                spins["ll_floor"].setValue(ll)

        preset.currentIndexChanged.connect(apply_preset)
        use.currentIndexChanged.connect(apply_use)
        from PySide6.QtWidgets import QLineEdit
        texts = {}
        for key, th in (("project", "โครงการ"), ("owner", "เจ้าของ"), ("place", "สถานที่"),
                        ("engineer", "ผู้คำนวณ (ลงนาม)"), ("qualification", "คุณวุฒิ / เลขทะเบียน")):
            ed = QLineEdit(str(b_.get(key, "") or ""))
            texts[key] = ed
            form.addRow(th, ed)
        box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        box.button(QDialogButtonBox.Ok).setText("ตกลง")
        box.button(QDialogButtonBox.Cancel).setText("ยกเลิก")
        box.accepted.connect(dlg.accept)
        box.rejected.connect(dlg.reject)
        form.addRow(box)
        if dlg.exec() != QDialog.Accepted:
            return
        calc = dict(d.get("calc") or {})
        calc["method"] = meth.currentData()
        for k, sp_ in spins.items():
            calc[k] = sp_.value()
        for k, ed in texts.items():
            calc[k] = ed.text().strip()
        d["calc"] = calc
        bp._write(d)
        self.refresh()

    def edit_truss(self):
        from core.wanic_truss_view import TrussDialog
        bp = self.building()
        if bp is None:
            return
        d = bp.data()
        dlg = TrussDialog(self, d)
        if dlg.exec() != TrussDialog.Accepted:
            return
        d["truss"] = dlg.params()
        bp._write(d)
        self.status.setText("บันทึก Truss แล้ว — รวมในรูปเล่มรายการคำนวณ A4")
        self.refresh()

    def edit_grid(self):
        from core.wanic_grid_view import GridDialog
        bp = self.building()
        if bp is None:
            return
        d = bp.data()
        dlg = GridDialog(self, d)
        if dlg.exec() != GridDialog.Accepted:
            return
        has = any(f.get("rooms") for f in d.get("floors") or [])
        if has and QMessageBox.question(self, "โหมดกริด", "แทนที่ผังห้องเดิมทุกชั้นด้วยผังจากกริด?") \
                != QMessageBox.Yes:
            return
        sx, sy, n, omit = dlg.values()
        R.apply_grid(d, sx, sy, n, omit, inner_walls=dlg.inner_walls())
        bp._write(d)
        self.status.setText(f"สร้างผังจากกริดแล้ว: {len(sx) + 1} × {len(sy) + 1} แกน · {n} ชั้น")
        self.refresh()

    def apply_advice(self):
        """Apply the advice to every failing mark, after a confirmation that
        lists the changes; the RC designer's undo brings it back."""
        import copy
        from core import wanic_advice as AD
        bp = self.building()
        if bp is None:
            return
        d = bp.data()
        trial = copy.deepcopy(d)
        done = AD.apply_fixes(trial)
        if not done:
            QMessageBox.information(self, TITLE, "ทุกชิ้นส่วนผ่านแล้ว — ไม่มีอะไรต้องแก้")
            return
        if QMessageBox.question(self, TITLE, "จะปรับเบอร์ต่อไปนี้ให้ผ่าน:\n\n" + "\n".join(f"• {t}" for t in done)
                                + "\n\nตกลงหรือไม่? (แก้คืนได้ด้วย Undo)") != QMessageBox.Yes:
            return
        d["library"] = trial.get("library") or {}
        bp._write(d)
        self._rebuild_after_fix(f"ปรับตามคำแนะนำแล้ว {len(done)} เบอร์")

    def _rebuild_after_fix(self, what: str):
        """The model follows the new sizes; then the calculation again."""
        bp = self.building()
        try:
            bp.build(("structure", "roof"))
            built = " · อัปเดตโมเดลแล้ว"
        except Exception as e:                       # noqa: BLE001 - shown, never a crash
            built = f" · อัปเดตโมเดลไม่ได้: {e}"
        self.refresh()
        if self.step != "calc":                      # the table shows another step: a fresh calculation
            from core import wanic_calc as C
            try:
                self._calc = C.analyse(self.data())
            except Exception:                        # noqa: BLE001 - the status only
                self._calc = None
        bad = sum(1 for m in (self._calc or {}).get("members") or [] if not m.ok)
        self.status.setText(what + built + (" · ✓ ผ่านทุกรายการ" if not bad else f" · ยังไม่ผ่าน {bad} รายการ"))

    def fix_member(self):
        """แก้ชิ้นที่เลือก: the advice and the passing values of the selected
        failing row, editable; saved to its mark, the model rebuilt."""
        from core import wanic_advice as AD
        from core.wanic_fix_view import FixDialog, apply
        if self.step != "calc" or not self._calc:
            return
        r = self.table.currentRow()
        ms = self._calc.get("members") or []
        if not (0 <= r < len(ms)):
            QMessageBox.information(self, TITLE, "เลือกแถวที่ไม่ผ่าน (สีแดง) ในตารางก่อน")
            return
        m = ms[r]
        if m.ok:
            QMessageBox.information(self, TITLE, f"{m.name} ผ่านแล้ว — เลือกแถวที่ไม่ผ่าน (สีแดง)")
            return
        bp = self.building()
        if bp is None:
            return
        d = bp.data()
        fix = AD.member_fix(self._calc, d, m)
        if not fix:
            QMessageBox.information(self, TITLE, "ไม่มีคำแนะนำสำหรับรายการนี้ — แก้ขนาดในขั้นที่เกี่ยวข้อง")
            return
        dlg = FixDialog(self, m, fix, d)
        if dlg.exec() != FixDialog.Accepted:
            return
        apply(d, fix, dlg.values())
        bp._write(d)
        self._rebuild_after_fix(f"แก้ {fix['key']} แล้ว")

    def edit_beam_loads(self):
        from core.wanic_beamload_view import BeamLoadDialog
        bp = self.building()
        if bp is None:
            return
        d = bp.data()
        dlg = BeamLoadDialog(self, d)
        if dlg.exec() != BeamLoadDialog.Accepted:
            return
        d["beam_loads"] = dlg.loads()
        bp._write(d)
        self._rebuild_after_fix(f"บันทึกน้ำหนักเพิ่มบนคาน {len(d['beam_loads'])} รายการ")

    def edit_cantilevers(self):
        from core.wanic_beamload_view import CantileverDialog
        bp = self.building()
        if bp is None:
            return
        d = bp.data()
        dlg = CantileverDialog(self, d)
        if dlg.exec() != CantileverDialog.Accepted:
            return
        d["cantilevers"] = dlg.cantilevers()
        bp._write(d)
        self._rebuild_after_fix(f"บันทึกคานยื่น {len(d['cantilevers'])} ตัว")

    def edit_free(self):
        from core.wanic_free_view import FreeListDialog
        bp = self.building()
        if bp is None:
            return
        d = bp.data()
        dlg = FreeListDialog(self, d)
        if dlg.exec() != FreeListDialog.Accepted:
            return
        n = dlg.apply(d)
        bp._write(d)
        self._rebuild_after_fix(f"ชิ้นส่วนเขียนอิสระ {n} ชิ้น")

    def convert_selection(self):
        """แปลงเส้นที่เลือกเป็น คาน / เสา / ผนัง (เขียนแบบอิสระ)."""
        from core import wanic_free as FR
        from core.wanic_free_view import FreeConvertDialog
        bp = self.building()
        if bp is None:
            return
        scene = self.app.scene
        edges = [e for e in scene.selection if hasattr(e, "v0") and hasattr(e, "v1")]
        chains = FR.chains_from_edges(edges)
        try:                                          # editing inside a group: to world metres
            from plugins.wanic_profiles import _matrix_of
            m = _matrix_of(scene, getattr(scene, "edit_group", None))
        except Exception:                             # noqa: BLE001
            m = None
        if m is not None:
            from PySide6.QtGui import QVector3D
            for ch in chains:
                ch["pts"] = [tuple(round(c, 4) for c in (lambda q: (q.x(), q.y(), q.z()))(m.map(QVector3D(*p))))
                             for p in ch["pts"]]
        if not chains:
            QMessageBox.information(self, TITLE, "เลือกเส้นที่วาดไว้ในโมเดลก่อน (เส้นตรง เส้นโค้ง เส้นเอียง หรือเส้นดิ่ง)")
            return
        d = bp.data()
        FR.model_to_building(chains, d)               # model z (lifted) → the building's levels
        dlg = FreeConvertDialog(self, d, chains)
        if dlg.exec() != FreeConvertDialog.Accepted:
            return
        n = dlg.apply(d, chains)
        bp._write(d)
        self._rebuild_after_fix(f"แปลงเป็น คาน {n['beams']} · เสา {n['columns']} · ผนัง {n['walls']} ชิ้น")

    def edit_piles(self):
        from core.wanic_pile_view import PileDialog
        bp = self.building()
        if bp is None:
            return
        d = bp.data()
        dlg = PileDialog(self, d)
        if dlg.exec() != PileDialog.Accepted:
            return
        dlg.apply(d)
        bp._write(d)
        self._rebuild_after_fix("บันทึกเสาเข็ม P1/P2 แล้ว")

    def edit_stairs(self):
        from core.wanic_stair_view import StairDialog
        bp = self.building()
        if bp is None:
            return
        d = bp.data()
        dlg = StairDialog(self, d)
        if dlg.exec() != StairDialog.Accepted:
            return
        n = dlg.apply(d)
        bp._write(d)
        self._rebuild_after_fix(f"บันทึกบันได {n} ชุด")

    def show_checkload(self):
        from core import wanic_calc as C
        from core.wanic_beamload_view import CheckloadDialog
        d = self.data()
        try:
            res = self._calc or C.analyse(d)
            ck = C.checkload(d, res)
        except Exception as e:                       # noqa: BLE001 - shown, never a crash
            QMessageBox.warning(self, TITLE, f"ตรวจน้ำหนักลงเสาไม่ได้: {e}")
            return
        CheckloadDialog(self, ck).exec()

    def edit_estimate(self):
        from core.wanic_private_est_view import PrivateEstDialog
        bp = self.building()
        if bp is None:
            return
        d = bp.data()
        dlg = PrivateEstDialog(self, d)
        if dlg.exec() != PrivateEstDialog.Accepted:
            return
        d["private_est"] = dlg.params()
        bp._write(d)
        self.status.setText("บันทึกค่าประมาณราคางานเอกชนแล้ว")

    def edit_lateral(self):
        from core.wanic_lateral_view import LateralDialog
        bp = self.building()
        if bp is None:
            return
        d = bp.data()
        dlg = LateralDialog(self, d)
        if dlg.exec() != LateralDialog.Accepted:
            return
        d["lateral"] = dlg.params()
        bp._write(d)
        self.status.setText("บันทึกแรงด้านข้างแล้ว — รวมในรูปเล่มรายการคำนวณ A4")
        self.refresh()

    def edit_flatslab(self):
        from core.wanic_flatslab_view import FlatSlabDialog
        bp = self.building()
        if bp is None:
            return
        d = bp.data()
        dlg = FlatSlabDialog(self, d)
        if dlg.exec() != FlatSlabDialog.Accepted:
            return
        d["flatslab"] = dlg.params()
        bp._write(d)
        self.status.setText("บันทึกพื้นไร้คานแล้ว — รวมในรูปเล่มรายการคำนวณ A4")
        self.refresh()

    def edit_purlin(self):
        from core.wanic_purlin_view import PurlinDialog
        bp = self.building()
        if bp is None:
            return
        d = bp.data()
        dlg = PurlinDialog(self, d)
        if dlg.exec() != PurlinDialog.Accepted:
            return
        d["purlin"] = dlg.params()
        bp._write(d)
        self.status.setText("บันทึกแป / Sag Rod / Tie Rod แล้ว — รวมในรูปเล่มรายการคำนวณ A4")
        self.refresh()

    def edit_steel(self):
        from core.wanic_steel_view import SteelDialog
        bp = self.building()
        if bp is None:
            return
        d = bp.data()
        dlg = SteelDialog(self, d)
        if dlg.exec() != SteelDialog.Accepted:
            return
        d["steel"] = dlg.params()
        bp._write(d)
        self.status.setText("บันทึกการออกแบบเหล็กรูปพรรณแล้ว — รวมในรูปเล่มรายการคำนวณ A4")
        self.refresh()

    def export_pdf(self):
        from core import wanic_calc as C
        from core.wanic_calc_view import report_pdf
        path, _ = QFileDialog.getSaveFileName(self, "รายการคำนวณโครงสร้าง", "รายการคำนวณโครงสร้าง.pdf",
                                              "PDF (*.pdf)")
        if not path:
            return
        report_pdf(C.analyse(self.data()), self.data(), path)
        self.status.setText(f"บันทึกรายการคำนวณแล้ว: {path}")

    def export_book(self):
        from core import wanic_calc as C
        from core.wanic_calc_book import make_book
        path, _ = QFileDialog.getSaveFileName(self, "รูปเล่มรายการคำนวณ", "รายการคำนวณโครงสร้าง (A4).pdf",
                                              "PDF (*.pdf)")
        if not path:
            return
        d = self.data()
        b_ = C.basis(d)
        info = {k: b_.get(k, "") for k in ("project", "owner", "place", "engineer", "qualification")}
        crit = QMessageBox.question(
            self, "รูปเล่มรายการคำนวณ",
            "พิมพ์เฉพาะชิ้นส่วนที่รับน้ำหนักมากที่สุดของแต่ละเบอร์ (คาน เสา พื้น ฐานราก)?\n"
            "«Yes» = เล่มสั้นสำหรับขออนุญาต · «No» = พิมพ์ทุกชิ้นส่วน") == QMessageBox.Yes
        n = make_book(C.analyse(d), d, path, info, critical=crit)
        self.status.setText(f"บันทึกรูปเล่มรายการคำนวณ {n} หน้าแล้ว: {path}")

    def export(self):
        path, _ = QFileDialog.getSaveFileName(self, "รายงานโครงสร้าง คสล.", "โครงสร้าง คสล.xlsx",
                                              "ตารางคำนวณ (*.xlsx)")
        if not path:
            return
        R.report_xlsx(self.elements(), path)
        self.status.setText(f"บันทึกรายงานแล้ว: {path}")


def setup(app) -> None:
    panel = RCPanel(app)
    dock = app.add_panel(TITLE, panel)
    app.window._wanic_rc = panel
    app.on_document_changed(panel.schedule)

    def show():
        app.show_panel(dock)
        dock.raise_()
        panel.refresh()

    def context(menu, selection):
        if any(hasattr(e, "v0") and hasattr(e, "v1") for e in selection):
            from PySide6.QtCore import QTimer as _T
            menu.addAction("แปลงเส้นที่เลือกเป็น คาน / เสา / ผนัง…",
                           lambda: _T.singleShot(0, panel.convert_selection))

    if hasattr(app, "add_context_menu"):
        app.add_context_menu(context)

    app.add_menu_action("WANIC ออกแบบโครงสร้าง คสล.…", show,
                        tip="กริด ฐานราก ตอม่อ คานคอดิน พื้น เสา คาน ถึงโครงหลังคา "
                            "แก้เหล็กเสริมและตรวจข้อกำหนด สรุปเหล็กเสริมเป็น Excel")
