# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2569 (2026) นายเวนิช ธัมมะวงษ์ วิศวกรสำรวจ — ReadWanicn2027
"""The windows: welcome screen, sign-in, and the main window."""
from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass, field
from pathlib import Path

import pymupdf
from PySide6.QtCore import QSettings, QSize, Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices, QFont, QIcon, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView, QButtonGroup, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFrame,
    QHBoxLayout, QHeaderView, QInputDialog, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QMainWindow, QMessageBox, QPushButton, QRadioButton, QScrollArea, QSizePolicy, QSplitter,
    QStackedWidget, QTableWidget, QTableWidgetItem, QTabWidget, QToolButton, QVBoxLayout, QWidget,
)

from . import APP_NAME, DEVELOPER, VERSION, auth, license, measure, pdfops, themes, update
from .canvas import TOOLS, PdfCanvas
from .model3d import ModelView, load_model

ASSETS = Path(__file__).resolve().parent.parent / "assets"


def asset(name: str) -> str:
    import sys
    base = Path(getattr(sys, "_MEIPASS", ASSETS.parent)) / "assets"
    return str(base / name)


def logo_pixmap(size: int) -> QPixmap:
    return QPixmap(asset("logo.png")).scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)


# -- welcome and sign-in --------------------------------------------------------------

class WelcomeScreen(QDialog):
    """The logo and a welcome, on its own for a moment while the program starts."""

    def __init__(self, user: str = "", parent=None):
        super().__init__(parent, Qt.FramelessWindowHint | Qt.Dialog)
        self.setFixedSize(560, 360)
        self.setStyleSheet("QDialog{background:qlineargradient(x1:0,y1:0,x2:0,y2:1,"
                           "stop:0 #0F2A44, stop:1 #163B5E);} QLabel{color:#F3EEE4;background:transparent;}")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(30, 26, 30, 20)
        logo = QLabel()
        logo.setPixmap(logo_pixmap(140))
        logo.setAlignment(Qt.AlignCenter)
        lay.addWidget(logo)
        title = QLabel("ยินดีต้อนรับสู่ ReadWanicn2027" + (f"\nคุณ {user}" if user else ""))
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size:20pt;font-weight:bold;")
        lay.addWidget(title)
        sub = QLabel("รวม · บีบอัด · ส่งออก · วัดพื้นที่ ความยาว นับจำนวน · โมเดล 3 มิติ")
        sub.setAlignment(Qt.AlignCenter)
        sub.setStyleSheet("color:#C9A227;font-size:10.5pt;")
        lay.addWidget(sub)
        lay.addStretch(1)
        foot = QLabel(f"รุ่น {VERSION} · พัฒนาโดย {DEVELOPER}")
        foot.setAlignment(Qt.AlignCenter)
        foot.setStyleSheet("color:#9FB3C8;font-size:9pt;")
        lay.addWidget(foot)

    def mousePressEvent(self, _e):
        self.accept()

    def show_for(self, ms: int = 2200):
        QTimer.singleShot(ms, self.accept)
        return self.exec()


class LoginDialog(QDialog):
    PLACEHOLDER = "\u2022" * 10          # the remembered password, never the real one

    def __init__(self, parent=None, users_path=None, settings=None, fetch=True):
        super().__init__(parent)
        self.users_path = users_path
        self.settings = settings or QSettings("WANICNSURVEY", APP_NAME)
        self.user = ""
        self.setWindowTitle(f"{APP_NAME} — เข้าสู่ระบบ")
        self.setWindowIcon(QIcon(asset("logo.ico")))
        self.setFixedWidth(420)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 20, 28, 18)
        logo = QLabel()
        logo.setPixmap(logo_pixmap(90))
        logo.setAlignment(Qt.AlignCenter)
        lay.addWidget(logo)
        t = QLabel(APP_NAME)
        t.setAlignment(Qt.AlignCenter)
        t.setStyleSheet("font-size:17pt;font-weight:bold;")
        lay.addWidget(t)
        s = QLabel("เข้าสู่ระบบเพื่อใช้งานภายในองค์กร")
        s.setAlignment(Qt.AlignCenter)
        lay.addWidget(s)
        lay.addSpacing(6)
        lay.addWidget(QLabel("ชื่อผู้ใช้"))
        self.name = QLineEdit()
        self.name.setPlaceholderText("ชื่อผู้ใช้")
        lay.addWidget(self.name)
        lay.addWidget(QLabel("รหัสผ่าน"))
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.Password)
        self.password.setPlaceholderText("รหัสผ่าน")
        lay.addWidget(self.password)
        from PySide6.QtWidgets import QCheckBox
        row = QHBoxLayout()
        self.remember = QCheckBox("จำรหัสผ่าน")
        row.addWidget(self.remember)
        self.show_pw = QCheckBox("แสดงรหัสผ่าน")
        self.show_pw.toggled.connect(lambda on: self.password.setEchoMode(
            QLineEdit.Normal if on and self.password.text() != self.PLACEHOLDER else QLineEdit.Password))
        row.addWidget(self.show_pw)
        row.addStretch(1)
        lay.addLayout(row)
        self.error = QLabel("")
        self.error.setStyleSheet("color:#DC2626;")
        lay.addWidget(self.error)
        ok = QPushButton("เข้าสู่ระบบ")
        ok.setObjectName("Primary")
        ok.setDefault(True)
        ok.clicked.connect(self.try_login)
        lay.addWidget(ok)
        self.password.returnPressed.connect(self.try_login)
        self.password.textEdited.connect(lambda _t: setattr(self, "_token_in_field", False))
        self.tries = 0
        self._token_in_field = False
        self.stats = StatsBox(self.settings)
        lay.addSpacing(6)
        lay.addWidget(self.stats)
        self._restore()
        if fetch:
            QTimer.singleShot(200, self.stats.refresh)

    def _restore(self):
        user = str(self.settings.value("login/user", "") or "")
        token = str(self.settings.value("login/token", "") or "")
        if user:
            self.name.setText(user)
        if user and auth.check_token(user, token, self.users_path):
            self.remember.setChecked(True)
            self.password.setText(self.PLACEHOLDER)
            self._token_in_field = True

    def try_login(self):
        name = self.name.text().strip()
        ok = (self._token_in_field and self.password.text() == self.PLACEHOLDER and
              auth.check_token(name, str(self.settings.value("login/token", "")), self.users_path))
        ok = ok or auth.check(name, self.password.text(), self.users_path)
        if ok:
            self.user = name
            self.settings.setValue("login/user", name)
            self.settings.setValue("login/token", auth.remember_token(name, self.users_path)
                                   if self.remember.isChecked() else "")
            self.accept()
            return
        self.tries += 1
        self.password.clear()
        self._token_in_field = False
        self.error.setText("ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง" + (" (ลองครั้งที่ %d/5)" % self.tries))
        if self.tries >= 5:
            self.reject()


class StatsBox(QFrame):
    """«สถิติผู้ใช้โปรแกรม»: the latest version and its date, the version in
    use, downloads in all and of the latest, computers that ever opened the
    program and the openings -- counted by GitHub on the program's releases."""

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.setObjectName("Stats")
        self.setStyleSheet("QFrame#Stats { border: 1px solid #3A5876; border-radius: 10px; }"
                           "QFrame#Stats QLabel { background: transparent; }")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 8, 12, 8)
        lay.setSpacing(2)
        head = QLabel("📊 <b>สถิติผู้ใช้โปรแกรม</b>")
        lay.addWidget(head)
        self.body = QLabel("กำลังอ่านข้อมูล…")
        self.body.setWordWrap(True)
        self.body.setTextFormat(Qt.RichText)
        lay.addWidget(self.body)
        self.link = QLabel("<a href='#' style='color:#5AA9FF'>↻ อัปเดตตัวเลข</a>")
        self.link.setAlignment(Qt.AlignRight)
        self.link.linkActivated.connect(lambda _h: self.refresh())
        lay.addWidget(self.link)
        cached = self.settings.value("stats/cache", "")
        if cached:
            try:
                self.show_info(update.ReleaseInfo(**json.loads(cached)), cached=True)
            except Exception:
                pass

    def refresh(self):
        if os.environ.get("READWANICN_OFFLINE"):
            self.body.setText(self.body.text() if self.settings.value("stats/cache") else
                              "ยังไม่มีข้อมูล (ออฟไลน์)")
            return
        result = {}

        def work():
            try:
                result["info"] = update.fetch()
                update.ping(self.settings, result["info"])
            except Exception as e:
                result["error"] = e
        th = threading.Thread(target=work, daemon=True)
        th.start()

        def poll():
            if th.is_alive():
                QTimer.singleShot(300, poll)
                return
            if "info" in result:
                self.settings.setValue("stats/cache", json.dumps(result["info"].__dict__))
                self.show_info(result["info"])
            elif not self.settings.value("stats/cache"):
                self.body.setText("ยังไม่มีข้อมูล (ออฟไลน์)")
        QTimer.singleShot(300, poll)

    def show_info(self, info, cached=False):
        lines = []
        if info.latest:
            day = f" ({info.published_th})" if getattr(info, "published_th", "") else ""
            lines.append(f"<span style='color:#E7A93B'>ปรับปรุงล่าสุด v{info.latest}{day}</span>")
            state = "✓ เป็นรุ่นล่าสุดแล้ว" if not info.newer else "⬇ มีรุ่นใหม่ให้ดาวน์โหลด"
            lines.append(f"<span style='color:#5AA9FF'>รุ่นที่ใช้อยู่: v{VERSION} {state}</span>")
        else:
            lines.append(f"รุ่นที่ใช้อยู่: v{VERSION}")
        lines.append(f"ดาวน์โหลดสะสม <b>{info.downloads:,}</b> ครั้ง")
        if info.latest:
            lines.append(f"รุ่นล่าสุด v{info.latest}: {info.latest_downloads:,} ครั้ง")
        lines.append(f"ผู้ใช้งานสะสม <b>{info.users:,}</b> คน (เครื่องที่เคยเปิดใช้)")
        lines.append(f"เปิดใช้งานสะสม {info.opens:,} ครั้ง")
        if info.fetched:
            lines.append(f"<span style='color:#8FA8C2'>ข้อมูล ณ {info.fetched}"
                         f"{' (ล่าสุดที่อ่านได้)' if cached else ''}</span>")
        self.body.setText("<br>".join(lines))


# -- dialogs ------------------------------------------------------------------------

class CombineDialog(QDialog):
    def __init__(self, paths: list, parent=None):
        super().__init__(parent)
        self.setWindowTitle("รวมไฟล์ PDF")
        self.resize(520, 380)
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("ลำดับไฟล์ที่จะรวม (เลื่อนขึ้นลงเพื่อจัดลำดับ):"))
        self.list = QListWidget()
        self.list.setDragDropMode(QAbstractItemView.InternalMove)
        for p in paths:
            self._add(p)
        lay.addWidget(self.list)
        row = QHBoxLayout()
        for text, fn in (("+ เพิ่มไฟล์", self.add_files), ("▲ ขึ้น", lambda: self.move(-1)),
                         ("▼ ลง", lambda: self.move(1)), ("ลบออกจากรายการ", self.remove)):
            b = QPushButton(text)
            b.clicked.connect(fn)
            row.addWidget(b)
        lay.addLayout(row)
        box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        box.button(QDialogButtonBox.Ok).setText("รวมและบันทึก…")
        box.button(QDialogButtonBox.Cancel).setText("ยกเลิก")
        box.accepted.connect(self.accept)
        box.rejected.connect(self.reject)
        lay.addWidget(box)

    def _add(self, path):
        it = QListWidgetItem(Path(path).name)
        it.setData(Qt.UserRole, str(path))
        it.setToolTip(str(path))
        self.list.addItem(it)

    def add_files(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "เลือกไฟล์ PDF", "", "PDF (*.pdf)")
        for p in paths:
            self._add(p)

    def move(self, step):
        r = self.list.currentRow()
        if r < 0 or not 0 <= r + step < self.list.count():
            return
        it = self.list.takeItem(r)
        self.list.insertItem(r + step, it)
        self.list.setCurrentRow(r + step)

    def remove(self):
        r = self.list.currentRow()
        if r >= 0:
            self.list.takeItem(r)

    def paths(self) -> list:
        return [self.list.item(i).data(Qt.UserRole) for i in range(self.list.count())]


class CompressDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("บีบอัดไฟล์ PDF")
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("เลือกระดับคุณภาพ:"))
        self.group = QButtonGroup(self)
        for key, (label, dpi, q) in pdfops.QUALITIES.items():
            rb = QRadioButton(f"{label}  — ภาพ {dpi} dpi, JPEG {q}%")
            rb.setProperty("level", key)
            self.group.addButton(rb)
            lay.addWidget(rb)
            if key == "medium":
                rb.setChecked(True)
        box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        box.button(QDialogButtonBox.Ok).setText("บีบอัดและบันทึก…")
        box.button(QDialogButtonBox.Cancel).setText("ยกเลิก")
        box.accepted.connect(self.accept)
        box.rejected.connect(self.reject)
        lay.addWidget(box)

    def level(self) -> str:
        return self.group.checkedButton().property("level")


# -- the developer: photo, contact, support ------------------------------------------

BANK = "ธนาคารกรุงศรีอยุธยา สาขาโลตัส ถลาง ภูเก็ต"
ACCOUNT_NAME = "นายเวนิช ธัมมะวงษ์"
ACCOUNT_NO = "666-1-32472-1"
NAVY, ORANGE, BRASS = "#0F2A44", "#C46420", "#C9A14A"


def script_font(px: int) -> QFont:
    """Charm, a Thai calligraphic face (SIL OFL), for the contact number."""
    from PySide6.QtGui import QFontDatabase
    fid = QFontDatabase.addApplicationFont(asset("Charm-Bold.ttf"))
    families = QFontDatabase.applicationFontFamilies(fid) if fid >= 0 else []
    f = QFont(families[0]) if families else QFont()
    f.setPixelSize(px)
    return f


def contact_row() -> QWidget:
    w = QWidget()
    w.setStyleSheet("background: white;")
    row = QHBoxLayout(w)
    row.setContentsMargins(0, 0, 0, 0)
    qr = QLabel()
    qpix = QPixmap(asset("contact-qr.png"))
    if not qpix.isNull():
        qm = qpix.scaled(110, 110, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        qr.setPixmap(qm)
        qr.setFixedSize(qm.size())
    qr.setToolTip("สแกนด้วยมือถือเพื่อเพิ่มเพื่อนทาง LINE กับผู้พัฒนา")
    row.addWidget(qr)
    text = QLabel(f"ติดต่อผู้พัฒนาระบบ<br><span style='font-size:21px'>{license.CONTACT_PHONE}</span>"
                  "<br><span style='font-size:13px;color:#06C755'>สแกนเพิ่มเพื่อน LINE</span>")
    text.setAlignment(Qt.AlignCenter)
    text.setWordWrap(True)
    text.setTextInteractionFlags(Qt.TextSelectableByMouse)
    text.setFont(script_font(16))
    text.setStyleSheet(f"color:{NAVY}; background: white;")
    row.addWidget(text, 1)
    return w


def support_panel() -> QFrame:
    """The developer's poster, the LINE QR and number, free use and the
    account to support him -- the same as the WANICNSURVEY start page."""
    box = QFrame()
    box.setObjectName("Support")
    box.setStyleSheet("QFrame#Support { background: white; border: 1px solid #D9D4C7; border-radius: 8px; }"
                      "QFrame#Support QLabel { background: white; }")
    col = QVBoxLayout(box)
    col.setContentsMargins(12, 12, 12, 12)
    col.setSpacing(6)
    photo = QLabel()
    pix = QPixmap(asset("developer.jpg"))
    if not pix.isNull():
        pm = pix.scaledToWidth(262, Qt.SmoothTransformation)
        photo.setPixmap(pm)
        photo.setFixedSize(pm.size())
    col.addWidget(photo, 0, Qt.AlignHCenter)
    col.addWidget(contact_row())
    free = QLabel("โปรแกรมใช้ได้ฟรี ไม่มีค่าลิขสิทธิ์")
    free.setAlignment(Qt.AlignCenter)
    free.setStyleSheet(f"font-size:14px; font-weight:700; color:{ORANGE};")
    col.addWidget(free)
    info = QLabel(f"<div style='color:{NAVY}; font-size:12px'>สนใจสนับสนุนผู้พัฒนา สามารถทำได้ที่<br>"
                  f"<b>{BANK}</b><br>ชื่อบัญชี <b>{ACCOUNT_NAME}</b><br>"
                  f"เลขที่บัญชี <b style='font-size:15px'>{ACCOUNT_NO}</b><br>บัญชีออมทรัพย์</div>")
    info.setAlignment(Qt.AlignCenter)
    info.setWordWrap(True)
    info.setTextInteractionFlags(Qt.TextSelectableByMouse)
    col.addWidget(info)
    copy = QPushButton("คัดลอกเลขที่บัญชี")
    copy.setCursor(Qt.PointingHandCursor)
    copy.setStyleSheet(f"QPushButton {{ background:{BRASS}; color:white; border:none; border-radius:6px;"
                       " padding:6px 12px; } QPushButton:hover { background:#B08A36; }")

    def _copy():
        from PySide6.QtWidgets import QApplication
        QApplication.clipboard().setText(ACCOUNT_NO.replace("-", ""))
        copy.setText("คัดลอกแล้ว ✓")
    copy.clicked.connect(_copy)
    col.addWidget(copy)
    thanks = QLabel("ขอบคุณที่ใช้งานและสนับสนุนครับ")
    thanks.setAlignment(Qt.AlignCenter)
    thanks.setStyleSheet("font-size:11px; color:#55657A;")
    col.addWidget(thanks)
    return box


class ExpiredDialog(QDialog):
    """A year is up: contact the developer for a renewal code, type it in."""

    def __init__(self, lic: "license.License", parent=None, warning: bool = False):
        super().__init__(parent)
        self.lic = lic
        self.setWindowTitle(f"{APP_NAME} — " + ("ใกล้หมดอายุการใช้งาน" if warning else "หมดอายุการใช้งาน"))
        self.setWindowIcon(QIcon(asset("logo.ico")))
        self.setFixedWidth(460)
        self.setStyleSheet("QDialog, QLabel { background: white; color: #0F2A44; }"
                           "QLineEdit { background:white; color:#0F2A44; border:1px solid #C9CED6; border-radius:5px;"
                           " padding:5px; font-size:13pt; }")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 18)
        logo = QLabel()
        logo.setPixmap(logo_pixmap(72))
        logo.setAlignment(Qt.AlignCenter)
        lay.addWidget(logo)
        if warning:
            head = f"อายุการใช้งานจะหมดในอีก {lic.days_left} วัน (วันที่ {lic.until:%d/%m/%Y})"
        else:
            head = "หมดอายุการใช้งาน"
        title = QLabel(head)
        title.setAlignment(Qt.AlignCenter)
        title.setWordWrap(True)
        title.setStyleSheet(f"font-size:17pt; font-weight:bold; color:{'#B45309' if warning else '#DC2626'};")
        lay.addWidget(title)
        msg = QLabel("โปรแกรมนี้ใช้งานได้ครั้งละ 1 ปี กรุณาติดต่อผู้พัฒนาเพื่อขอรหัสผ่านต่ออายุการใช้งาน "
                     "โดยแจ้งรหัสเครื่องด้านล่าง")
        msg.setWordWrap(True)
        msg.setAlignment(Qt.AlignCenter)
        lay.addWidget(msg)
        idl = QLabel(f"รหัสเครื่อง: <b style='font-size:15pt'>{lic.install_id}</b> · ครั้งที่ต่ออายุ "
                     f"<b>{int(lic.data['n']) + 1}</b>")
        idl.setAlignment(Qt.AlignCenter)
        idl.setTextInteractionFlags(Qt.TextSelectableByMouse)
        lay.addWidget(idl)
        lay.addWidget(contact_row())
        lay.addWidget(QLabel("รหัสผ่านต่ออายุ (จากผู้พัฒนา):"))
        self.code = QLineEdit()
        self.code.setPlaceholderText("XXXX-XXXX-XXXX")
        lay.addWidget(self.code)
        self.error = QLabel("")
        self.error.setStyleSheet("color:#DC2626;")
        lay.addWidget(self.error)
        row = QHBoxLayout()
        ok = QPushButton("ยืนยันรหัสผ่าน")
        ok.setStyleSheet("background:#C9A14A; color:white; border:none; border-radius:6px; padding:7px 14px;")
        ok.clicked.connect(self.try_code)
        row.addWidget(ok)
        later = QPushButton("ใช้งานต่อ" if warning else "ปิดโปรแกรม")
        later.clicked.connect(self.reject)
        row.addWidget(later)
        lay.addLayout(row)
        self.code.returnPressed.connect(self.try_code)

    def try_code(self):
        if self.lic.renew(self.code.text()):
            QMessageBox.information(self, APP_NAME, f"ต่ออายุแล้ว ใช้งานได้ถึงวันที่ {self.lic.until:%d/%m/%Y}")
            self.accept()
        else:
            self.error.setText("รหัสผ่านไม่ถูกต้อง กรุณาตรวจสอบกับผู้พัฒนา")


def check_license(parent=None, lic: "license.License | None" = None) -> bool:
    """False when the year is up and no renewal code was given."""
    lic = lic or license.License()
    if lic.expired:
        return ExpiredDialog(lic, parent).exec() == QDialog.Accepted
    if lic.days_left <= license.WARN_DAYS:
        ExpiredDialog(lic, parent, warning=True).exec()
    return True


# -- the main window ----------------------------------------------------------------

@dataclass
class OpenFile:
    path: str
    doc: "pymupdf.Document"
    dirty: bool = False
    page: int = 0
    measurements: list = field(default_factory=list)

    @property
    def name(self) -> str:
        return Path(self.path).name


def _button(text: str, icon: str, tip: str, checkable=False) -> QToolButton:
    b = QToolButton()
    b.setText(f"{icon}\n{text}")
    b.setToolTip(tip)
    b.setCheckable(checkable)
    b.setToolButtonStyle(Qt.ToolButtonTextOnly)
    b.setMinimumHeight(52)
    return b


class MainWindow(QMainWindow):
    def __init__(self, user: str = "Wanicn"):
        super().__init__()
        self.user = user
        self.files: list[OpenFile] = []
        self.current: OpenFile | None = None
        self.scale = measure.Scale.ratio(100)
        self.settings = QSettings("WANICNSURVEY", APP_NAME)
        self.setWindowTitle(f"{APP_NAME} — {VERSION}")
        self.setWindowIcon(QIcon(asset("logo.ico")))
        self.resize(1360, 860)
        self.setAcceptDrops(True)
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._top_bar())
        self.tool_rows = QWidget()
        rows = QVBoxLayout(self.tool_rows)
        rows.setContentsMargins(0, 0, 0, 0)
        rows.setSpacing(0)
        rows.addWidget(self._file_row())
        rows.addWidget(self._measure_row())
        root.addWidget(self.tool_rows)
        split = QSplitter()
        self.left = self._left_panel()
        self.right = self._right_panel()
        split.addWidget(self.left)
        split.addWidget(self._centre())
        split.addWidget(self.right)
        split.setSizes([250, 820, 300])
        split.setStretchFactor(1, 1)
        root.addWidget(split, 1)
        self.setCentralWidget(central)
        self.status = self.statusBar()
        self.set_tool("pan")
        self.apply_theme(self.settings.value("theme", themes.DEFAULT))
        self.status.showMessage(f"ยินดีต้อนรับ คุณ {user} · {TOOLS['pan']}")
        QTimer.singleShot(400, self.check_updates)

    # -- building
    def _top_bar(self):
        bar = QFrame()
        bar.setObjectName("TopBar")
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(10, 6, 10, 6)
        self.menu_btn = QPushButton("☰ เมนู")
        self.menu_btn.setToolTip("ซ่อน/แสดงแถบเครื่องมือ")
        self.menu_btn.clicked.connect(lambda: self.tool_rows.setVisible(not self.tool_rows.isVisible()))
        lay.addWidget(self.menu_btn)
        logo = QLabel()
        logo.setPixmap(logo_pixmap(44))
        lay.addWidget(logo)
        col = QVBoxLayout()
        col.setSpacing(0)
        t = QLabel(APP_NAME)
        t.setObjectName("Title")
        col.addWidget(t)
        self.subtitle = QLabel("ยังไม่ได้เปิดไฟล์")
        self.subtitle.setObjectName("Subtitle")
        col.addWidget(self.subtitle)
        lay.addLayout(col)
        lay.addStretch(1)
        self.stats = QLabel("📊 ดาวน์โหลดสะสม — ")
        self.stats.setToolTip("จำนวนครั้งที่ดาวน์โหลดตัวติดตั้งจากหน้า Releases")
        lay.addWidget(self.stats)
        self.update_btn = QPushButton("⬇ มีเวอร์ชันใหม่")
        self.update_btn.setObjectName("Primary")
        self.update_btn.hide()
        self.update_btn.clicked.connect(self.open_update)
        lay.addWidget(self.update_btn)
        for text, fn in (("▤ แผงไฟล์", lambda: self.left.setVisible(not self.left.isVisible())),
                         ("▥ แผงวัด", lambda: self.right.setVisible(not self.right.isVisible()))):
            b = QPushButton(text)
            b.clicked.connect(fn)
            lay.addWidget(b)
        lay.addWidget(QLabel("ธีม:"))
        self.theme = QComboBox()
        self.theme.addItems(list(themes.THEMES))
        self.theme.currentTextChanged.connect(self.apply_theme)
        lay.addWidget(self.theme)
        who = QLabel(f"👤 {self.user}")
        lay.addWidget(who)
        return bar

    def _row(self, buttons):
        row = QFrame()
        row.setObjectName("ToolRow")
        lay = QHBoxLayout(row)
        lay.setContentsMargins(8, 2, 8, 2)
        lay.setSpacing(2)
        for b in buttons:
            if b is None:
                sep = QFrame()
                sep.setFrameShape(QFrame.VLine)
                lay.addWidget(sep)
            else:
                lay.addWidget(b)
        lay.addStretch(1)
        return row

    def _file_row(self):
        spec = [("เปิดไฟล์", "📂", "เปิดไฟล์ PDF (หลายไฟล์ได้) หรืองานวัด .json", self.open_files),
                ("บันทึก", "💾", "บันทึกไฟล์ PDF ที่แก้ไข (ลบ/หมุนหน้า)", self.save_file),
                ("บันทึกเป็น", "🗂", "บันทึก PDF เป็นไฟล์ใหม่", self.save_as),
                ("บันทึกงานวัด", "📝", "บันทึกรายการวัดทั้งหมดเป็นไฟล์ .json", self.save_measurements),
                None,
                ("รวมไฟล์", "🧩", "รวมหลายไฟล์ PDF เป็นไฟล์เดียว", self.combine),
                ("บีบอัด", "🗜", "บีบอัด PDF: คุณภาพสูง / กลาง / ต่ำ", self.compress),
                ("ลบหน้า", "✂", "ลบหน้าที่เลือก", self.delete_pages),
                ("หมุนหน้า", "⟳", "หมุนหน้า 90°", self.rotate_page),
                ("ลบไฟล์", "🗑", "ปิดไฟล์ออกจากรายการ หรือลบไฟล์ทิ้ง", self.delete_file),
                None,
                ("ส่งออกตารางคำนวณ", "📊", "ข้อความและตารางในเอกสารเป็นไฟล์ตารางคำนวณ (.xlsx)", lambda: self.export("xlsx")),
                ("ส่งออกตารางข้อมูล", "🧾", "ข้อความและตารางในเอกสารเป็นไฟล์ข้อมูลคั่นด้วยจุลภาค (.csv)", lambda: self.export("csv")),
                ("ส่งออกเอกสาร", "📄", "ข้อความและตารางในเอกสารเป็นไฟล์เอกสาร (.docx)", lambda: self.export("docx"))]
        buttons = []
        for item in spec:
            if item is None:
                buttons.append(None)
                continue
            text, icon, tip, fn = item
            b = _button(text, icon, tip)
            b.clicked.connect(lambda _=False, f=fn: self._safe(f))
            buttons.append(b)
        return self._row(buttons)

    def _measure_row(self):
        self.tool_buttons = {}
        buttons = []
        for key, text, icon in (("pan", "เลื่อน", "✋"), ("scale", "ตั้งสเกล", "📏"),
                                ("length", "วัดความยาว", "↔"), ("area", "คิดพื้นที่", "⬠"),
                                ("count", "นับจำนวน", "✔")):
            b = _button(text, icon, TOOLS[key], checkable=True)
            b.clicked.connect(lambda _=False, k=key: self.set_tool(k))
            self.tool_buttons[key] = b
            buttons.append(b)
        rep = _button("รายงานงานวัด", "📈", "รายงานงานวัดเป็นไฟล์ตารางคำนวณ (.xlsx) หรือ .csv")
        rep.clicked.connect(lambda: self._safe(self.report))
        buttons += [rep, None]
        for text, icon, fn in (("ย่อ", "➖", lambda: self.zoom_by(1 / 1.25)),):
            b = _button(text, icon, "ย่อ")
            b.clicked.connect(fn)
            buttons.append(b)
        self.zoom_label = QLabel("100%")
        self.zoom_label.setMinimumWidth(52)
        self.zoom_label.setAlignment(Qt.AlignCenter)
        self.zoom_label.setStyleSheet("font-weight:bold;font-size:11pt;background:transparent;")
        buttons.append(self.zoom_label)
        for text, icon, tip, fn in (("ขยาย", "➕", "ขยาย", lambda: self.zoom_by(1.25)),
                                    ("พอดีจอ", "⛶", "ย่อ/ขยายให้พอดีหน้าจอ", self.fit),
                                    ("โมเดล 3 มิติ", "🧊", "ดูและหมุนโมเดล 3 มิติ", self.show_3d)):
            b = _button(text, icon, tip)
            b.clicked.connect(fn)
            buttons.append(b)
        return self._row(buttons)

    def _left_panel(self):
        w = QFrame()
        w.setObjectName("Side")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(6, 6, 6, 6)
        head = QHBoxLayout()
        h = QLabel("ไฟล์ที่เปิดอยู่")
        h.setObjectName("Head")
        head.addWidget(h)
        head.addStretch(1)
        add = QPushButton("+ เพิ่ม")
        add.clicked.connect(lambda: self._safe(self.open_files))
        head.addWidget(add)
        lay.addLayout(head)
        self.file_list = QListWidget()
        self.file_list.currentRowChanged.connect(self.select_file)
        lay.addWidget(self.file_list, 1)
        h = QLabel("หน้า")
        h.setObjectName("Head")
        lay.addWidget(h)
        self.page_list = QListWidget()
        self.page_list.setViewMode(QListWidget.IconMode)
        self.page_list.setIconSize(QSize(96, 120))
        self.page_list.setResizeMode(QListWidget.Adjust)
        self.page_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.page_list.currentRowChanged.connect(self.select_page)
        lay.addWidget(self.page_list, 2)
        return w

    def _centre(self):
        self.tabs = QTabWidget()
        # PDF tab: an empty state until a file is open
        self.pdf_stack = QStackedWidget()
        empty = QWidget()
        e = QVBoxLayout(empty)
        e.addStretch(1)
        logo = QLabel()
        logo.setPixmap(logo_pixmap(110))
        logo.setAlignment(Qt.AlignCenter)
        e.addWidget(logo)
        t = QLabel("ลากไฟล์ PDF มาวางที่นี่")
        t.setAlignment(Qt.AlignCenter)
        t.setStyleSheet("font-size:16pt;font-weight:bold;background:transparent;")
        e.addWidget(t)
        s = QLabel("หรือกดปุ่มด้านล่างเพื่อเปิดไฟล์ (เปิดได้หลายไฟล์พร้อมกัน)")
        s.setAlignment(Qt.AlignCenter)
        s.setStyleSheet("background:transparent;")
        e.addWidget(s)
        b = QPushButton("📂 เปิดไฟล์ PDF")
        b.setObjectName("Primary")
        b.setFixedWidth(200)
        b.clicked.connect(lambda: self._safe(self.open_files))
        e.addWidget(b, 0, Qt.AlignCenter)
        e.addStretch(2)
        self.pdf_stack.addWidget(empty)
        self.scroll = QScrollArea()
        self.scroll.setAlignment(Qt.AlignCenter)
        self.canvas = PdfCanvas()
        self.canvas.finished.connect(self.add_measurement)
        self.canvas.calibrate.connect(self.calibrate)
        self.canvas.zoomRequested.connect(self.zoom_by)
        self.canvas.panBy.connect(self._pan)
        self.scroll.setWidget(self.canvas)
        self.pdf_stack.addWidget(self.scroll)
        self.tabs.addTab(self.pdf_stack, "เอกสาร PDF")
        # 3D tab
        w3 = QWidget()
        l3 = QVBoxLayout(w3)
        l3.setContentsMargins(0, 0, 0, 0)
        row = QHBoxLayout()
        for text, fn in (("📂 เปิดโมเดล (.stl .obj)", self.open_model), ("⟲ หมุนซ้าย", lambda: self.model.rotate(-15)),
                         ("⟳ หมุนขวา", lambda: self.model.rotate(15)), ("⏯ หมุนอัตโนมัติ", self.toggle_spin),
                         ("⌂ มุมมองเริ่มต้น", lambda: self.model.reset_view())):
            b = QPushButton(text)
            b.clicked.connect(lambda _=False, f=fn: self._safe(f))
            row.addWidget(b)
        row.addStretch(1)
        l3.addLayout(row)
        self.model = ModelView()
        l3.addWidget(self.model, 1)
        self.spin = QTimer(self)
        self.spin.timeout.connect(lambda: self.model.rotate(1.5))
        self.tabs.addTab(w3, "โมเดล 3 มิติ")
        return self.tabs

    def _right_panel(self):
        w = QFrame()
        w.setObjectName("RightSide")
        outer = QScrollArea()
        outer.setWidgetResizable(True)
        outer.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        outer.setMinimumWidth(320)
        outer.setWidget(w)
        lay = QVBoxLayout(w)
        lay.setContentsMargins(8, 6, 8, 6)
        h = QLabel("สเกลแบบ")
        h.setObjectName("Head")
        lay.addWidget(h)
        self.scale_label = QLabel()
        lay.addWidget(self.scale_label)
        row = QHBoxLayout()
        self.scale_combo = QComboBox()
        self.scale_combo.addItem("— เลือกสเกลมาตรฐาน —", 0)
        for n in measure.STANDARD_SCALES:
            self.scale_combo.addItem(f"1:{n}", n)
        row.addWidget(self.scale_combo, 1)
        use = QPushButton("ใช้")
        use.clicked.connect(self.use_scale)
        row.addWidget(use)
        lay.addLayout(row)
        hint = QLabel("สเกล 1:N ใช้ได้เมื่อพิมพ์แบบขนาดจริงของกระดาษ หากแบบถูกย่อ ให้ใช้ปุ่ม "
                      "«ตั้งสเกล» คลิก 2 จุดบนระยะที่รู้ค่า")
        hint.setWordWrap(True)
        hint.setStyleSheet("font-size:8.5pt;background:transparent;")
        lay.addWidget(hint)
        lay.addWidget(QLabel("ชื่อรายการวัดถัดไป (เช่น ผนังก่ออิฐ, พื้นห้องนอน):"))
        self.item_name = QLineEdit()
        self.item_name.setPlaceholderText("ไม่ใส่ก็ได้")
        lay.addWidget(self.item_name)
        h = QLabel("ผลรวม")
        h.setObjectName("Head")
        lay.addWidget(h)
        self.total_label = QLabel("ยังไม่มีรายการวัด")
        self.total_label.setWordWrap(True)
        lay.addWidget(self.total_label)
        head = QHBoxLayout()
        h = QLabel("รายการวัด")
        h.setObjectName("Head")
        head.addWidget(h)
        head.addStretch(1)
        for text, fn in (("ลบรายการ", self.delete_measurement), ("ล้างหน้านี้", self.clear_page)):
            b = QPushButton(text)
            b.clicked.connect(fn)
            head.addWidget(b)
        lay.addLayout(head)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["หน้า", "ประเภท", "รายการ", "ปริมาณ"])
        hh = self.table.horizontalHeader()
        for c in (0, 1, 3):
            hh.setSectionResizeMode(c, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.verticalHeader().hide()
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setMinimumHeight(190)
        lay.addWidget(self.table, 1)
        lay.addWidget(support_panel())
        self._show_scale()
        return outer

    # -- helpers
    def _safe(self, fn):
        try:
            fn()
        except Exception as e:                   # shown, never swallowed
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, APP_NAME, f"ทำงานไม่สำเร็จ:\n{type(e).__name__}: {e}")

    def _pan(self, dx, dy):
        h, v = self.scroll.horizontalScrollBar(), self.scroll.verticalScrollBar()
        h.setValue(int(h.value() + dx))
        v.setValue(int(v.value() + dy))

    def _save_path(self, title, name, flt):
        path, _ = QFileDialog.getSaveFileName(self, title, str(Path(self._dir()) / name), flt)
        return path

    def _dir(self):
        return self.settings.value("dir", str(Path.home() / "Documents"))

    def apply_theme(self, name):
        if name not in themes.THEMES:
            name = themes.DEFAULT
        self.setStyleSheet(themes.stylesheet(name))
        c = themes.colors(name)
        self.zoom_label.setStyleSheet(f"font-weight:bold;font-size:11pt;background:transparent;"
                                      f"color:{c['bar_text']};")
        self.model.set_colors(c["canvas"], "#D8E2EC" if name != "ทองเวนิช" else "#E9DDBF", c["border"])
        if self.theme.currentText() != name:
            self.theme.blockSignals(True)
            self.theme.setCurrentText(name)
            self.theme.blockSignals(False)
        self.settings.setValue("theme", name)

    # -- files
    def open_files(self, paths=None):
        if not paths:
            paths, _ = QFileDialog.getOpenFileNames(self, "เปิดไฟล์", self._dir(),
                                                    "PDF หรืองานวัด (*.pdf *.json);;PDF (*.pdf)")
        for p in paths or []:
            if p.lower().endswith(".json"):
                self.load_measurements(p)
                continue
            doc = pymupdf.open(p)
            f = OpenFile(p, doc)
            self.files.append(f)
            it = QListWidgetItem(f"📄 {f.name}")
            it.setToolTip(p)
            self.file_list.addItem(it)
            self.settings.setValue("dir", str(Path(p).parent))
        if self.files:
            self.file_list.setCurrentRow(self.file_list.count() - 1)

    def select_file(self, row):
        if not 0 <= row < len(self.files):
            self.current = None
            self.canvas.set_document(None)
            self.pdf_stack.setCurrentIndex(0)
            self.page_list.clear()
            self.subtitle.setText("ยังไม่ได้เปิดไฟล์")
            self.refresh_table()
            return
        self.current = self.files[row]
        self.pdf_stack.setCurrentIndex(1)
        self.tabs.setCurrentIndex(0)
        self.canvas.measurements = self.current.measurements
        self.canvas.set_document(self.current.doc, self.current.page)
        self.fill_pages()
        self._title()
        self.refresh_table()

    def _title(self):
        f = self.current
        if f:
            self.subtitle.setText(f"{f.name}{' *' if f.dirty else ''} · {f.doc.page_count} หน้า · "
                                  f"หน้า {f.page + 1}")

    def fill_pages(self):
        self.page_list.blockSignals(True)
        self.page_list.clear()
        doc = self.current.doc
        for i in range(doc.page_count):
            pix = doc[i].get_pixmap(matrix=pymupdf.Matrix(0.18, 0.18), alpha=False)
            from PySide6.QtGui import QImage
            img = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format_RGB888).copy()
            it = QListWidgetItem(QIcon(QPixmap.fromImage(img)), f"หน้า {i + 1}")
            self.page_list.addItem(it)
        self.page_list.setCurrentRow(self.current.page)
        self.page_list.blockSignals(False)

    def select_page(self, row):
        if self.current and 0 <= row < self.current.doc.page_count:
            self.current.page = row
            self.canvas.page_no = row
            self.canvas.points = []
            self.canvas.render()
            self._title()

    def save_file(self):
        f = self._need()
        if not f:
            return
        tmp = f.path + ".tmp"
        f.doc.save(tmp, garbage=3, deflate=True)
        f.doc.close()
        os.replace(tmp, f.path)
        f.doc = pymupdf.open(f.path)
        f.dirty = False
        self.select_file(self.files.index(f))
        self.status.showMessage(f"บันทึก {f.path} แล้ว", 5000)

    def save_as(self):
        f = self._need()
        if not f:
            return
        path = self._save_path("บันทึกเป็น", Path(f.path).stem + "-แก้ไข.pdf", "PDF (*.pdf)")
        if path:
            f.doc.save(path, garbage=3, deflate=True)
            self.status.showMessage(f"บันทึก {path} แล้ว", 5000)

    def delete_file(self):
        f = self._need()
        if not f:
            return
        box = QMessageBox(self)
        box.setWindowTitle("ลบไฟล์")
        box.setText(f"«{f.name}»\nต้องการทำอย่างไร?")
        close = box.addButton("ปิดออกจากรายการ", QMessageBox.AcceptRole)
        trash = box.addButton("ลบไฟล์ทิ้งจากเครื่อง", QMessageBox.DestructiveRole)
        box.addButton("ยกเลิก", QMessageBox.RejectRole)
        box.exec()
        if box.clickedButton() not in (close, trash):
            return
        if box.clickedButton() is trash:
            sure = QMessageBox.question(self, "ยืนยันการลบ",
                                        f"ลบไฟล์นี้ออกจากเครื่องถาวร?\n{f.path}")
            if sure != QMessageBox.Yes:
                return
        row = self.files.index(f)
        f.doc.close()
        if box.clickedButton() is trash:
            os.remove(f.path)
        self.files.pop(row)
        self.file_list.takeItem(row)
        self.select_file(min(row, len(self.files) - 1))

    def _need(self):
        if self.current is None:
            QMessageBox.information(self, APP_NAME, "ยังไม่ได้เปิดไฟล์ PDF")
        return self.current

    # -- pdf tools
    def combine(self):
        dlg = CombineDialog([f.path for f in self.files], self)
        if dlg.exec() != QDialog.Accepted or not dlg.paths():
            return
        path = self._save_path("บันทึกไฟล์ที่รวมแล้ว", "รวมไฟล์.pdf", "PDF (*.pdf)")
        if not path:
            return
        n = pdfops.combine(dlg.paths(), path)
        self.open_files([path])
        QMessageBox.information(self, "รวมไฟล์", f"รวม {len(dlg.paths())} ไฟล์ ได้ {n} หน้า\n{path}")

    def compress(self):
        f = self._need()
        if not f:
            return
        dlg = CompressDialog(self)
        if dlg.exec() != QDialog.Accepted:
            return
        level = dlg.level()
        name = {"high": "สูง", "medium": "กลาง", "low": "ต่ำ"}[level]
        path = self._save_path("บันทึกไฟล์ที่บีบอัด", f"{Path(f.path).stem}-บีบอัด{name}.pdf", "PDF (*.pdf)")
        if not path:
            return
        src = f.path
        if f.dirty:
            src = path + ".src.pdf"
            f.doc.save(src)
        r = pdfops.compress(src, path, level)
        if src != f.path:
            os.remove(src)
        QMessageBox.information(self, "บีบอัดไฟล์", f"ก่อน {r.before / 1024:,.0f} KB → หลัง {r.after / 1024:,.0f} KB "
                                f"(เล็กลง {r.saved_percent:.1f}%)\n{path}")

    def delete_pages(self):
        f = self._need()
        if not f:
            return
        rows = sorted({i.row() for i in self.page_list.selectedIndexes()}) or [f.page]
        if len(rows) >= f.doc.page_count:
            QMessageBox.information(self, "ลบหน้า", "ต้องเหลืออย่างน้อย 1 หน้า")
            return
        if QMessageBox.question(self, "ลบหน้า", f"ลบหน้า {', '.join(str(r + 1) for r in rows)}?") != QMessageBox.Yes:
            return
        pdfops.delete_pages(f.doc, rows)
        f.measurements[:] = [m for m in f.measurements if m.page not in rows]
        for m in f.measurements:
            m.page -= sum(1 for r in rows if r < m.page)
        f.page = min(f.page, f.doc.page_count - 1)
        f.dirty = True
        self.select_file(self.files.index(f))

    def rotate_page(self):
        f = self._need()
        if not f:
            return
        pdfops.rotate_page(f.doc, f.page, 90)
        f.dirty = True
        self.canvas.render()
        self.fill_pages()
        self._title()

    def export(self, kind):
        f = self._need()
        if not f:
            return
        flt = {"xlsx": "ตารางคำนวณ (*.xlsx)", "csv": "ตารางข้อมูล (*.csv)", "docx": "เอกสาร (*.docx)"}[kind]
        path = self._save_path("ส่งออก", f"{Path(f.path).stem}.{kind}", flt)
        if not path:
            return
        if kind == "xlsx":
            n = pdfops.export_excel(f.doc, path, f.name)
        elif kind == "csv":
            n = pdfops.export_csv(f.doc, path)
        else:
            n = pdfops.export_word(f.doc, path, f.name)
        self.status.showMessage(f"ส่งออก {path} แล้ว ({n:,} รายการ)", 6000)
        self._offer_open(path)

    def _offer_open(self, path):
        if QMessageBox.question(self, APP_NAME, f"บันทึกแล้ว\n{path}\n\nเปิดไฟล์เลยไหม?") == QMessageBox.Yes:
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    # -- view
    def zoom_by(self, factor):
        self.canvas.zoom = max(0.1, min(8.0, self.canvas.zoom * factor))
        self.canvas.render()
        self.zoom_label.setText(f"{self.canvas.zoom * 100:.0f}%")

    def fit(self):
        if not self.current:
            return
        from .canvas import PX_PER_PT
        w, h = self.canvas.page_size()
        vw = self.scroll.viewport().width() - 50
        vh = self.scroll.viewport().height() - 50
        self.canvas.zoom = max(0.1, min(vw / (w * PX_PER_PT), vh / (h * PX_PER_PT)))
        self.canvas.render()
        self.zoom_label.setText(f"{self.canvas.zoom * 100:.0f}%")

    def show_3d(self):
        self.tabs.setCurrentIndex(1)

    def open_model(self):
        path, _ = QFileDialog.getOpenFileName(self, "เปิดโมเดล 3 มิติ", self._dir(), "โมเดล (*.stl *.obj)")
        if path:
            self.model.set_triangles(load_model(path), Path(path).name)
            self.model.reset_view()

    def toggle_spin(self):
        if self.spin.isActive():
            self.spin.stop()
        else:
            self.spin.start(30)

    # -- measuring
    def set_tool(self, key):
        for k, b in self.tool_buttons.items():
            b.setChecked(k == key)
        self.canvas.set_tool(key)
        self.status.showMessage(TOOLS[key])
        self.canvas.setFocus()

    def _show_scale(self):
        self.scale_label.setText(f"สเกลที่ใช้: <b>{self.scale.label}</b>")

    def use_scale(self):
        n = self.scale_combo.currentData()
        if n:
            self.scale = measure.Scale.ratio(n)
            self._show_scale()

    def calibrate(self, pt_distance):
        metres, ok = QInputDialog.getDouble(self, "ตั้งสเกล", "ระยะจริงระหว่าง 2 จุด (เมตร):", 1.0, 0.001, 1e6, 3)
        if ok:
            self.scale = measure.Scale.calibrated(pt_distance, metres)
            self._show_scale()
            self.status.showMessage(f"ตั้งสเกลแล้ว: {self.scale.label}", 6000)

    def add_measurement(self, kind, points):
        if not self.current:
            return
        m = measure.Measurement(kind, self.current.page, points, self.scale,
                                self.item_name.text().strip(), self.current.name)
        self.current.measurements.append(m)
        self.canvas.update()
        self.refresh_table()
        self.status.showMessage(f"{measure.KINDS[kind]}: {m.text()}", 6000)

    def all_measurements(self):
        return [m for f in self.files for m in f.measurements]

    def refresh_table(self):
        items = self.current.measurements if self.current else []
        self.table.setRowCount(len(items))
        for r, m in enumerate(items):
            for c, v in enumerate((str(m.page + 1), measure.KINDS[m.kind], m.name or "-", m.text())):
                self.table.setItem(r, c, QTableWidgetItem(v))
        t = measure.totals(self.all_measurements())
        if any(t.values()):
            self.total_label.setText(f"ความยาวรวม <b>{t['length']:,.3f}</b> ม.<br>"
                                     f"พื้นที่รวม <b>{t['area']:,.3f}</b> ตร.ม.<br>"
                                     f"นับได้ <b>{int(t['count']):,}</b> จุด")
        else:
            self.total_label.setText("ยังไม่มีรายการวัด")

    def delete_measurement(self):
        if not self.current:
            return
        rows = sorted({i.row() for i in self.table.selectedIndexes()}, reverse=True)
        for r in rows:
            self.current.measurements.pop(r)
        self.canvas.update()
        self.refresh_table()

    def clear_page(self):
        if self.current:
            self.current.measurements[:] = [m for m in self.current.measurements
                                            if m.page != self.current.page]
            self.canvas.update()
            self.refresh_table()

    def report(self):
        items = self.all_measurements()
        if not items:
            QMessageBox.information(self, "รายงาน", "ยังไม่มีรายการวัด")
            return
        path, flt = QFileDialog.getSaveFileName(self, "รายงานงานวัด", str(Path(self._dir()) / "รายงานงานวัด.xlsx"),
                                                "ตารางคำนวณ (*.xlsx);;ตารางข้อมูล (*.csv)")
        if not path:
            return
        if path.lower().endswith(".csv"):
            measure.report_csv(items, path)
        else:
            measure.report_excel(items, path, "รายงานงานวัด ReadWanicn2027", f"จัดทำโดย {self.user}")
        self._offer_open(path)

    def save_measurements(self):
        items = self.all_measurements()
        if not items:
            QMessageBox.information(self, "บันทึกงานวัด", "ยังไม่มีรายการวัด")
            return
        path = self._save_path("บันทึกงานวัด", "งานวัด.json", "งานวัด (*.json)")
        if not path:
            return
        data = {"app": APP_NAME, "version": VERSION, "files": [
            {"path": f.path, "measurements": [
                {"kind": m.kind, "page": m.page, "points": m.points, "name": m.name,
                 "m_per_pt": m.scale.m_per_pt, "scale": m.scale.label} for m in f.measurements]}
            for f in self.files if f.measurements]}
        Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        self.status.showMessage(f"บันทึกงานวัด {path} แล้ว", 5000)

    def load_measurements(self, path):
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        for entry in data.get("files", []):
            if not Path(entry["path"]).exists():
                continue
            self.open_files([entry["path"]])
            f = self.files[-1]
            for m in entry["measurements"]:
                f.measurements.append(measure.Measurement(
                    m["kind"], m["page"], [tuple(p) for p in m["points"]],
                    measure.Scale(m["m_per_pt"], m["scale"]), m.get("name", ""), f.name))
        self.select_file(self.file_list.currentRow())

    # -- updates and download count
    def check_updates(self):
        if os.environ.get("READWANICN_OFFLINE"):
            self.stats.setText("📊 ดาวน์โหลดสะสม — (ออฟไลน์)")
            return
        result = {}

        def work():
            try:
                result["info"] = update.fetch()
            except Exception as e:
                result["error"] = e
        th = threading.Thread(target=work, daemon=True)
        th.start()

        def poll():
            if th.is_alive():
                QTimer.singleShot(300, poll)
                return
            self.show_release(result.get("info"))
        QTimer.singleShot(300, poll)

    def show_release(self, info):
        if info is None:
            self.stats.setText("📊 ดาวน์โหลดสะสม — (ออฟไลน์)")
            return
        self.stats.setText(f"📊 ดาวน์โหลดสะสม {info.downloads:,} ครั้ง")
        self._release = info
        if info.newer:
            self.update_btn.setText(f"⬇ มีเวอร์ชันใหม่ {info.latest}")
            self.update_btn.show()

    def open_update(self):
        info = getattr(self, "_release", None)
        if info and info.url:
            QDesktopServices.openUrl(QUrl(info.url))

    # -- drag and drop
    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        paths = [u.toLocalFile() for u in e.mimeData().urls()
                 if u.toLocalFile().lower().endswith((".pdf", ".json", ".stl", ".obj"))]
        models = [p for p in paths if p.lower().endswith((".stl", ".obj"))]
        if models:
            self.model.set_triangles(load_model(models[-1]), Path(models[-1]).name)
            self.show_3d()
        self._safe(lambda: self.open_files([p for p in paths if p not in models]))

    def closeEvent(self, e):
        dirty = [f.name for f in self.files if f.dirty]
        if dirty and QMessageBox.question(
                self, APP_NAME, "ไฟล์ต่อไปนี้ยังไม่ได้บันทึก:\n" + "\n".join(dirty) + "\n\nปิดโปรแกรมเลยไหม?"
        ) != QMessageBox.Yes:
            e.ignore()
            return
        e.accept()
