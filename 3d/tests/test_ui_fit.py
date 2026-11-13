# SPDX-License-Identifier: GPL-3.0-or-later
"""ปรับหน้าจอให้พอดีทุกเครื่อง: rows of buttons wrap, forms wrap, dialogs fit."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtWidgets import (QApplication, QComboBox, QDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit,  # noqa: E402
                               QPushButton, QScrollArea, QVBoxLayout, QWidget)

from core import ui_fit  # noqa: E402

app = QApplication.instance() or QApplication([])


def _panel():
    w = QWidget()
    v = QVBoxLayout(w)
    row = QHBoxLayout()
    for t in ("ปุ่มที่หนึ่งยาวมาก", "ปุ่มที่สองยาวมาก", "ปุ่มที่สามยาวมาก", "ปุ่มที่สี่ยาวมาก", "ปุ่มที่ห้ายาวมาก"):
        row.addWidget(QPushButton(t))
    row.addStretch(1)
    v.addLayout(row)
    f = QFormLayout()
    cb = QComboBox()
    cb.addItem("รายการที่ยาวมาก " * 6)
    f.addRow("ข้อความกำกับยาว ๆ ของช่องกรอก", cb)
    f.addRow("ช่อง", QLineEdit())
    v.addLayout(f)
    return w


def test_panel_rows_wrap_and_shrink():
    w = _panel()
    out = ui_fit.fit(w)
    assert isinstance(out, QScrollArea) and out.widget() is w
    assert not w.findChildren(QHBoxLayout)                 # the button row became a wrapping row
    assert ui_fit.fit(out) is out                           # idempotent
    out.resize(380, 600)
    out.show()
    app.processEvents()
    assert w.width() <= 380                                 # no sideways scrolling
    for b in w.findChildren(QPushButton):                   # every button inside the panel
        r = b.geometry().translated(b.parentWidget().mapTo(w, b.parentWidget().rect().topLeft()))
        assert r.right() <= w.width() + 1, b.text()
    out.hide()


def test_dialog_capped_to_the_screen():
    d = QDialog()
    d.setMinimumSize(5000, 4000)
    QVBoxLayout(d).addWidget(QLabel("x"))
    ui_fit.fit_dialog(d)
    av = d.screen().availableGeometry()
    assert d.minimumWidth() <= av.width() and d.minimumHeight() <= av.height()
    assert d.width() <= av.width() and d.height() <= av.height()
    d.deleteLater()
