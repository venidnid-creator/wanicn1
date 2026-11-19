# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2569 (2026) นายเวนิช ธัมมะวงษ์ วิศวกรสำรวจ — ReadWanicn2027
"""หน้าต่าง «ถอดแบบตาม BOQ»: อ่านแบบทั้งชุด แสดงผลทีละแผ่น (อ่านได้ / อ่านได้บางส่วน / อ่านไม่ได้)
รายการ BOQ ที่อ่านได้ และส่งออก CSV แบบ ปร.1 แยกตามประเภทงาน"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QSettings, Qt, QThread, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from . import boqread as B

STATUS_COLOR = {"อ่านได้": "#2E7D32", "อ่านได้บางส่วน": "#B26A00", "อ่านไม่ได้": "#C62828"}


class _Worker(QObject):
    progress = Signal(int, int, str)
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, path, ocr):
        super().__init__()
        self.path, self.ocr, self.stop = path, ocr, False

    def run(self):
        try:
            def tick(i, n, text):
                self.progress.emit(i, n, text)
                return not self.stop
            self.done.emit(B.analyse(self.path, ocr=self.ocr, progress=tick))
        except Exception as e:                       # shown in the window, never swallowed
            self.failed.emit(f"{type(e).__name__}: {e}")


def _item(text, color=None, align=None):
    it = QTableWidgetItem("" if text is None else str(text))
    it.setFlags(it.flags() & ~Qt.ItemIsEditable)
    it.setToolTip(it.text())
    if color:
        it.setForeground(QColor(color))
    if align:
        it.setTextAlignment(align)
    return it


def _fit(table: QTableWidget, stretch: int, fixed: dict | None = None):
    h = table.horizontalHeader()
    for c in range(table.columnCount()):
        if fixed and c in fixed:
            h.setSectionResizeMode(c, QHeaderView.Interactive)
            h.resizeSection(c, fixed[c])
        else:
            h.setSectionResizeMode(c, QHeaderView.Stretch if c == stretch else QHeaderView.ResizeToContents)
    table.verticalHeader().setVisible(False)
    table.setAlternatingRowColors(True)
    table.setWordWrap(True)


class BoqDialog(QDialog):
    """อ่านแบบ PDF ทั้งชุด → BOQ แบบ ปร.1 (CSV แยกงานอาคาร งานทาง งานชลประทาน …)"""

    def __init__(self, path, record=None, parent=None):
        super().__init__(parent)
        self.path, self.record, self.res, self.thread = str(path), record, None, None
        self.settings = QSettings("WANICNSURVEY", "ReadWanicn2027")
        self.setWindowTitle(f"ถอดแบบตาม BOQ — {Path(path).name}")
        self.resize(1180, 760)
        lay = QVBoxLayout(self)

        self.head = QLabel(f"กำลังอ่านแบบ <b>{Path(path).name}</b> …")
        self.head.setWordWrap(True)
        self.head.setTextFormat(Qt.RichText)
        lay.addWidget(self.head)
        self.bar = QProgressBar()
        lay.addWidget(self.bar)

        self.tabs = QTabWidget()
        lay.addWidget(self.tabs, 1)
        self.pages = QTableWidget(0, 7)
        self.pages.setHorizontalHeaderLabels(["หน้า", "ผลการอ่าน", "ชนิดหน้า", "เลขแผ่น", "ชื่อแผ่น", "ประเภทงาน",
                                              "หมายเหตุ / สิ่งที่ต้องทำต่อ"])
        _fit(self.pages, 6, {2: 150, 4: 260})
        self.tabs.addTab(self.pages, "ผลการอ่านทีละแผ่น")
        self.items = QTableWidget(0, 8)
        self.items.setHorizontalHeaderLabels(["ประเภทงาน", "หมวด", "รายการ", "จำนวน", "หน่วย", "ค่าวัสดุ/หน่วย",
                                              "ค่าแรง/หน่วย", "หน้า"])
        _fit(self.items, 2)
        self.tabs.addTab(self.items, "รายการ BOQ ที่อ่านได้")
        self.tags = QTableWidget(0, 4)
        self.tags.setHorizontalHeaderLabels(["ป้าย", "ความหมาย", "จำนวน", "พบในหน้า"])
        _fit(self.tags, 3)
        self.tabs.addTab(self.tags, "ป้ายที่นับได้")

        info = QWidget()
        form = QFormLayout(info)
        form.setContentsMargins(0, 0, 0, 0)
        self.f_project, self.f_place = QLineEdit(), QLineEdit()
        self.f_no, self.f_owner = QLineEdit(), QLineEdit()
        for w, ph in ((self.f_project, "ชื่อโครงการงานก่อสร้าง (เว้นว่าง = ใช้ชื่อในตาราง BOQ)"),
                      (self.f_place, "สถานที่ก่อสร้าง"), (self.f_no, "แบบเลขที่"),
                      (self.f_owner, "หน่วยงานเจ้าของโครงการงานก่อสร้าง")):
            w.setPlaceholderText(ph)
        form.addRow("ชื่อโครงการ", self.f_project)
        form.addRow("สถานที่ก่อสร้าง", self.f_place)
        form.addRow("แบบเลขที่", self.f_no)
        form.addRow("หน่วยงานเจ้าของโครงการ", self.f_owner)
        lay.addWidget(info)

        row = QHBoxLayout()
        self.stop_btn = QPushButton("หยุดอ่าน")
        self.stop_btn.clicked.connect(self._stop)
        row.addWidget(self.stop_btn)
        self.other_btn = QPushButton("📂 ถอดแบบไฟล์อื่น…")
        self.other_btn.setToolTip("ล้างผลที่อ่านไว้ แล้วเลือกไฟล์แบบ PDF ชุดใหม่มาอ่าน")
        self.other_btn.clicked.connect(self.choose_other)
        row.addWidget(self.other_btn)
        self.clear_btn = QPushButton("🗑 ล้างข้อมูล")
        self.clear_btn.setToolTip("ล้างผลการอ่านและช่องข้อมูลโครงการทั้งหมด เพื่อเริ่มถอดแบบชุดใหม่")
        self.clear_btn.clicked.connect(lambda: self.clear(ask=True))
        row.addWidget(self.clear_btn)
        row.addStretch(1)
        self.csv_btn = QPushButton("🧾 ส่งออก CSV แบบ ปร.1 (แยกตามประเภทงาน)")
        self.csv_btn.setObjectName("Primary")
        self.csv_btn.setEnabled(False)
        self.csv_btn.clicked.connect(self.export)
        row.addWidget(self.csv_btn)
        close = QPushButton("ปิด")
        close.clicked.connect(self.reject)
        row.addWidget(close)
        lay.addLayout(row)
        self._start()

    # -- reading in the background
    # -- a new set of drawings
    def clear(self, ask: bool = False) -> bool:
        """Forget everything read so far (tables, the result, the project fields)."""
        if self.thread and self.thread.isRunning():
            self._stop()
            self.thread.quit()
            self.thread.wait(5000)
        if ask and self.res and QMessageBox.question(
                self, self.windowTitle(), "ล้างผลการอ่านแบบและข้อมูลโครงการทั้งหมด เพื่อเริ่มถอดแบบชุดใหม่?\n"
                "(ไฟล์ CSV ที่ส่งออกไปแล้วไม่ถูกลบ)") != QMessageBox.Yes:
            return False
        self.res = None
        for t in (self.pages, self.items, self.tags):
            t.clearContents()
            t.setRowCount(0)
        for f in (self.f_project, self.f_place, self.f_no, self.f_owner):
            f.clear()
        self.f_project.setPlaceholderText("ชื่อโครงการงานก่อสร้าง (เว้นว่าง = ใช้ชื่อในตาราง BOQ)")
        self.csv_btn.setEnabled(False)
        self.bar.hide()
        self.stop_btn.hide()
        self.setWindowTitle("ถอดแบบตาม BOQ")
        self.head.setText("ล้างข้อมูลแล้ว — กด <b>«📂 ถอดแบบไฟล์อื่น…»</b> เพื่อเลือกไฟล์แบบ PDF ชุดใหม่")
        self.tabs.setCurrentIndex(0)
        return True

    def choose_other(self):
        base = str(Path(self.path).parent) if self.path else str(Path.home())
        path, _ = QFileDialog.getOpenFileName(self, "เลือกไฟล์แบบ PDF ที่จะถอดแบบ", base, "PDF (*.pdf)")
        if not path:
            return
        self.clear()
        self.read(path)

    def read(self, path):
        """Read a set of drawings (from the start, nothing of the last one kept)."""
        self.path = str(path)
        self.setWindowTitle(f"ถอดแบบตาม BOQ — {Path(path).name}")
        self.head.setText(f"กำลังอ่านแบบ <b>{Path(path).name}</b> …")
        self.bar.setValue(0)
        self.bar.show()
        self.stop_btn.setEnabled(True)
        self.stop_btn.show()
        self._start()

    def _start(self):
        ocr = bool(B.tesseract_path())
        self.thread = QThread(self)
        self.worker = _Worker(self.path, ocr)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.progress.connect(self._progress)
        self.worker.done.connect(self._done)
        self.worker.failed.connect(self._failed)
        self.worker.done.connect(self.thread.quit)
        self.worker.failed.connect(self.thread.quit)
        self.thread.start()

    def _stop(self):
        if self.worker:
            self.worker.stop = True
            self.stop_btn.setEnabled(False)

    def _progress(self, i, n, text):
        self.bar.setMaximum(n)
        self.bar.setValue(i)
        self.bar.setFormat(text)

    def _failed(self, msg):
        self.bar.hide()
        self.stop_btn.hide()
        self.head.setText(f"<span style='color:#C62828'>อ่านแบบไม่สำเร็จ: {msg}</span>")

    def _done(self, res):
        self.res = res
        self.bar.hide()
        self.stop_btn.hide()
        s = res.summary()
        works = res.by_work()
        bits = [f"ทั้งหมด <b>{s['ทั้งหมด']}</b> หน้า",
                f"<span style='color:{STATUS_COLOR['อ่านได้']}'>อ่านได้ <b>{s['อ่านได้']}</b></span>",
                f"<span style='color:{STATUS_COLOR['อ่านได้บางส่วน']}'>อ่านได้บางส่วน <b>{s['อ่านได้บางส่วน']}</b></span>",
                f"<span style='color:{STATUS_COLOR['อ่านไม่ได้']}'>อ่านไม่ได้ <b>{s['อ่านไม่ได้']}</b></span>"]
        lines = (f"รายการ BOQ ที่อ่านได้ <b>{len(res.lines)}</b> รายการ ("
                 + " · ".join(f"งาน{k} {len(v)}" for k, v in works.items()) + ")") if res.lines else \
            "<span style='color:#B26A00'>ในไฟล์นี้ไม่มีตาราง BOQ ที่อ่านได้ — ปริมาณต้องถอดด้วยเครื่องมือวัด/รูปทรง " \
            "(รายชื่อแผ่นอยู่ในรายงานการอ่านแบบ)</span>"
        warn = "" if res.ocr else ("<br><span style='color:#C62828'>เครื่องนี้ไม่มีตัวอ่านภาพ (OCR) — "
                                   "แผ่นที่เป็นภาพสแกนอ่านชื่อแผ่นไม่ได้</span>")
        self.head.setText(f"<b>{Path(self.path).name}</b> · " + " · ".join(bits) + "<br>" + lines + warn
                          + "<br>แผ่นสีส้ม/แดง: โปรแกรมอ่านได้ไม่ครบหรือไม่ชัด — ดูหมายเหตุแล้วพิจารณา/ถอดเพิ่มเอง")
        self.pages.setRowCount(len(res.pages))
        for r, p in enumerate(res.pages):
            col = STATUS_COLOR.get(p.status)
            kind = p.kind.replace(" (ฟอนต์ไทยรุ่นเก่า แปลงให้แล้ว)", " ✓ฟอนต์เก่า")
            for c, v in enumerate((p.no, p.status, kind, p.sheet, p.title, p.work, p.note)):
                self.pages.setItem(r, c, _item(v, col if c in (1, 6) else None))
        self.pages.resizeRowsToContents()
        self.items.setRowCount(len(res.lines))
        num = Qt.AlignRight | Qt.AlignVCenter
        for r, ln in enumerate(res.lines):
            vals = (ln.work, ln.group, ln.name, B._fmt(ln.qty), ln.unit, B._fmt(ln.mat_u), B._fmt(ln.lab_u), ln.page)
            for c, v in enumerate(vals):
                self.items.setItem(r, c, _item(v, None if ln.sure or c != 2 else "#B26A00",
                                               num if c in (3, 5, 6) else None))
        self.tags.setRowCount(len(res.tags))
        for r, (t, where) in enumerate(sorted(res.tags.items())):
            for c, v in enumerate((t, B.tag_meaning(t), sum(where.values()),
                                   " · ".join(f"หน้า {p}: {n}" for p, n in sorted(where.items())))):
                self.tags.setItem(r, c, _item(v))
        self.tabs.setCurrentIndex(1 if res.lines else 0)
        self.csv_btn.setEnabled(True)
        if res.project and not self.f_project.text():
            self.f_project.setPlaceholderText(f"ชื่อโครงการงานก่อสร้าง (เว้นว่าง = {res.project})")

    # -- CSV
    def export(self):
        if not self.res:
            return
        base = self.settings.value("dir", str(Path.home() / "Documents"))
        folder = QFileDialog.getExistingDirectory(self, "เลือกโฟลเดอร์ที่จะบันทึก CSV", base)
        if not folder:
            return
        info = {"project": self.f_project.text().strip(), "place": self.f_place.text().strip(),
                "drawing_no": self.f_no.text().strip(), "owner": self.f_owner.text().strip()}
        files = B.write_csv(self.res, folder, info)
        if self.record:
            self.record("ถอดแบบตาม BOQ: ส่งออก CSV")
        names = "\n".join(f"• {Path(f).name}" for f in files)
        bad = [p for p in self.res.pages if p.status != "อ่านได้"]
        box = QMessageBox(self)
        box.setWindowTitle("ส่งออก CSV แล้ว")
        box.setText(f"บันทึก {len(files)} ไฟล์ที่ {folder}\n\n{names}\n\n"
                    + (f"มี {len(bad)} แผ่นที่อ่านได้ไม่ครบหรือไม่ชัด — ดูไฟล์ «รายงานการอ่านแบบ» "
                       "แล้วพิจารณา/ถอดเพิ่มด้วยเครื่องมือวัด" if bad else "อ่านได้ครบทุกแผ่น"))
        go = box.addButton("เปิดโฟลเดอร์", QMessageBox.AcceptRole)
        box.addButton("ปิด", QMessageBox.RejectRole)
        box.exec()
        if box.clickedButton() is go:
            QDesktopServices.openUrl(QUrl.fromLocalFile(folder))
        if QMessageBox.question(self, self.windowTitle(),
                                "ส่งออกเรียบร้อยแล้ว — ล้างข้อมูลที่อ่านไว้ เพื่อถอดแบบชุดใหม่เลยหรือไม่?") == QMessageBox.Yes:
            self.clear()

    def reject(self):
        if self.thread and self.thread.isRunning():
            self.worker.stop = True
            self.thread.quit()
            self.thread.wait(3000)
        super().reject()
