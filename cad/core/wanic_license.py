# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
"""อายุการใช้งาน WANICNSURVEY — one year of use from the first start, as
ReadWanicn2027; after that the programs ask for a renewal code from the
developer, which opens another year.

The year is kept in the settings folder, a backup copy in the local
application data and (on Windows) the registry. An update, a reinstall over
the old one or a cleaned settings folder therefore never starts a new year:
the count goes on from the first installation. A computer with none of the
three but with folders of an earlier installation (one older than this
licence) counts from the day those folders were made; only a computer with no
trace at all starts a new year on the first start.

The renewal code is ``HMAC-SHA256(key, "WANICNSURVEY:<id>:<n>")`` cut to 12
hex digits: bound to this installation's ID, the renewal number and the
program (a ReadWanicn2027 code does not open WANICNSURVEY). The key is
written into ``_wanic_license_key.py`` when the installer is built (from a
secret of the build, never from the repository); the developer makes codes
with ``tools/wanicnsurvey_code.py`` and the same key.

The same file is shipped in launcher/, cad/core/ and 3d/core/ (the three
programs are frozen apart); a test keeps the copies identical.

This is a reminder to renew, not copy protection.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import json
import os
import secrets
import sys
from pathlib import Path

PRODUCT = "WANICNSURVEY"
PERIOD_DAYS = 365
WARN_DAYS = 30
CONTACT_PHONE = "093-5838348"
CONTACT_LINE = "https://line.me/ti/p/E-p-C9tCEx"
REG_KEY = r"Software\WANICNSURVEY"
FIRST_RELEASE = dt.date(2026, 10, 28)  # no WANICNSURVEY existed before this day

try:                                   # written by the build (in a package: cad/core, 3d/core)
    from ._wanic_license_key import KEY as _KEY  # type: ignore
except ImportError:
    try:                               # the start screen (a top-level module)
        from _wanic_license_key import KEY as _KEY  # type: ignore
    except ImportError:                # running from source
        _KEY = "wanicnsurvey-development-key"

THAI_MONTHS = ("มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม", "มิถุนายน", "กรกฎาคม", "สิงหาคม",
               "กันยายน", "ตุลาคม", "พฤศจิกายน", "ธันวาคม")
THAI_MONTHS_SHORT = ("ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.", "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค.")


def thai_date(d, short: bool = False) -> str:
    """19 พฤศจิกายน 2570 / 19 พ.ย. 70"""
    if d is None:
        return "—"
    if short:
        return f"{d.day} {THAI_MONTHS_SHORT[d.month - 1]} {(d.year + 543) % 100:02d}"
    return f"{d.day} {THAI_MONTHS[d.month - 1]} {d.year + 543}"


def state_file() -> Path:
    base = os.environ.get("APPDATA") or os.path.join(Path.home(), ".config")
    return Path(base) / PRODUCT / "license.json"


def backup_files(path: Path) -> list:
    base = os.environ.get("LOCALAPPDATA") or os.path.join(Path.home(), ".local", "share")
    out = [Path(base) / PRODUCT / "license-backup.json"]
    return [b for b in out if b.resolve() != Path(path).resolve()]


def _reg_read():
    if os.name != "nt" or os.environ.get("WANIC_NO_REGISTRY"):
        return None
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_KEY) as k:
            return json.loads(winreg.QueryValueEx(k, "license")[0])
    except (OSError, ValueError):
        return None


def _reg_write(data: dict) -> None:
    if os.name != "nt" or os.environ.get("WANIC_NO_REGISTRY"):
        return
    try:
        import winreg
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, REG_KEY) as k:
            winreg.SetValueEx(k, "license", 0, winreg.REG_SZ, json.dumps(data))
    except OSError:
        pass


def _born(path) -> "dt.date | None":
    """The day a folder was created (Windows; a birth time elsewhere when the
    system keeps one), None when unknown."""
    try:
        st = os.stat(path)
    except OSError:
        return None
    t = getattr(st, "st_birthtime", None)
    if t is None and os.name == "nt":
        t = st.st_ctime                 # creation time on Windows
    if not t:
        return None
    try:
        return dt.date.fromtimestamp(t)
    except (OverflowError, OSError, ValueError):
        return None


def trace_folders() -> list:
    """Folders an earlier WANICNSURVEY leaves on the computer: the install
    folder (its root above launcher/ cad/ 3d/, kept by an update or a
    reinstall over the old one) and the settings folders of the start screen,
    the 2D and the 3D program (kept even by an uninstall)."""
    out = []
    if getattr(sys, "frozen", False):
        exe = Path(sys.executable).resolve()
        out += [exe.parent, exe.parent.parent]
    for env, names in (("APPDATA", (PRODUCT, "IngeCAD", "IngeTrazo")),
                       ("LOCALAPPDATA", (PRODUCT, "IngeCAD", "IngeTrazo"))):
        base = os.environ.get(env)
        if base:
            out += [Path(base) / n for n in names]
    return out


def earliest_trace(folders=None, today: dt.date | None = None):
    """The first day an earlier installation was on this computer (between the
    first release and today), None when there is no trace."""
    today = today or dt.date.today()
    days = [d for d in (_born(f) for f in (trace_folders() if folders is None else folders)) if d]
    if not days:
        return None
    return min(max(min(days), FIRST_RELEASE), today)


def _valid(data) -> bool:
    return isinstance(data, dict) and {"id", "until", "n"} <= set(data)


def _best(records: list):
    """The record to keep: the most renewals, then the earliest start (a fresh
    year made by a lost file never wins over the first installation)."""
    good = [r for r in records if _valid(r)]
    if not good:
        return None
    return max(good, key=lambda r: (int(r.get("n", 0)), [-ord(c) for c in str(r.get("start", "9999"))]))


def renewal_code(install_id: str, n: int, key: str | None = None) -> str:
    digest = hmac.new((key or _KEY).encode(), f"{PRODUCT}:{install_id.upper()}:{n}".encode(),
                      hashlib.sha256).hexdigest()[:12].upper()
    return "-".join(digest[i:i + 4] for i in range(0, 12, 4))


def _clean(code: str) -> str:
    return "".join(c for c in code.upper() if c.isalnum())


class License:
    def __init__(self, path: Path | None = None, today: dt.date | None = None, backups: list | None = None,
                 registry: bool | None = None, traces: list | None = None):
        self.traces = traces if traces is not None else (trace_folders() if path is None else [])
        self.backups = backups if backups is not None else (backup_files(state_file()) if path is None else [])
        self.registry = (path is None) if registry is None else registry
        self.path = path or state_file()
        self.today = today or dt.date.today()
        self.data = self._load()

    def _load(self) -> dict:
        records = []
        for f in [self.path] + list(self.backups):
            try:
                records.append(json.loads(Path(f).read_text(encoding="utf-8")))
            except (OSError, ValueError):
                pass
        if self.registry:
            records.append(_reg_read())
        data = _best(records)
        first = earliest_trace(self.traces, self.today)
        if data is None:
            start = first or self.today
            data = {"id": secrets.token_hex(4).upper(), "start": start.isoformat(),
                    "until": (start + dt.timedelta(days=PERIOD_DAYS)).isoformat(), "n": 0}
        elif first and int(data.get("n", 0)) == 0:
            # A year started by an update of an installation older than the
            # licence (or a lost record): count from the first installation.
            try:
                started = dt.date.fromisoformat(str(data.get("start", "")))
            except ValueError:
                started = None
            if started is None or first < started:
                data = dict(data, start=first.isoformat(),
                            until=(first + dt.timedelta(days=PERIOD_DAYS)).isoformat())
        self._save(data)
        return data

    def _save(self, data: dict) -> None:
        text = json.dumps(data, indent=1)
        for f in [self.path] + list(self.backups):
            try:
                Path(f).parent.mkdir(parents=True, exist_ok=True)
                Path(f).write_text(text, encoding="utf-8")
            except OSError:
                pass
        if self.registry:
            _reg_write(data)

    @property
    def install_id(self) -> str:
        return self.data["id"]

    @property
    def until(self) -> dt.date:
        return dt.date.fromisoformat(self.data["until"])

    @property
    def start(self):
        try:
            return dt.date.fromisoformat(self.data.get("start", ""))
        except ValueError:
            return None

    @property
    def renewals(self) -> int:
        return int(self.data.get("n", 0))

    @property
    def days_left(self) -> int:
        return (self.until - self.today).days

    @property
    def expired(self) -> bool:
        return self.days_left < 0

    def renew(self, code: str) -> bool:
        """Another year (from today, or from the old end when it is still
        ahead) when ``code`` is the next renewal code of this installation."""
        n = int(self.data["n"]) + 1
        if not hmac.compare_digest(_clean(code), _clean(renewal_code(self.install_id, n))):
            return False
        start = max(self.today, self.until)
        self.data.update(n=n, until=(start + dt.timedelta(days=PERIOD_DAYS)).isoformat())
        self._save(self.data)
        return True


def badge_text(lic: License) -> tuple:
    """(text, colour) of the badge on the start screen."""
    if lic.expired:
        return "🔑 หมดอายุการใช้งาน", "#DC2626"
    color = "#B45309" if lic.days_left <= WARN_DAYS else "#15803D"
    return f"🔑 ใช้ได้ถึง {thai_date(lic.until, short=True)} · เหลือ {lic.days_left:,} วัน", color


def _dialog(lic: License, parent=None, warning: bool = False):
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import (QDialog, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton,
                                   QVBoxLayout)

    class ExpiredDialog(QDialog):
        def __init__(self):
            super().__init__(parent)
            self.setWindowTitle(f"{PRODUCT} — " + ("ใกล้หมดอายุการใช้งาน" if warning else "หมดอายุการใช้งาน"))
            self.setFixedWidth(480)
            self.setStyleSheet("QDialog, QLabel { background: white; color: #0F2A44; font-size: 11pt; }"
                               "QLineEdit { background:white; color:#0F2A44; border:1px solid #C9CED6;"
                               " border-radius:5px; padding:5px; font-size:13pt; }")
            lay = QVBoxLayout(self)
            lay.setContentsMargins(24, 20, 24, 18)
            head = (f"อายุการใช้งานจะหมดในอีก {lic.days_left} วัน (วันที่ {thai_date(lic.until)})"
                    if warning else "หมดอายุการใช้งาน")
            title = QLabel(head)
            title.setAlignment(Qt.AlignCenter)
            title.setWordWrap(True)
            title.setStyleSheet(f"font-size:17pt; font-weight:bold; color:{'#B45309' if warning else '#DC2626'};")
            lay.addWidget(title)
            msg = QLabel("โปรแกรม WANICNSURVEY ใช้งานได้ครั้งละ 1 ปี นับจากวันที่เริ่มใช้งาน "
                         "(ติดตั้งทับหรือติดตั้งใหม่ ยังนับต่อเนื่อง) "
                         "กรุณาติดต่อผู้พัฒนาเพื่อขอรหัสผ่านต่ออายุ โดยแจ้งรหัสเครื่องด้านล่าง")
            msg.setWordWrap(True)
            msg.setAlignment(Qt.AlignCenter)
            lay.addWidget(msg)
            idl = QLabel(f"รหัสเครื่อง: <b style='font-size:15pt'>{lic.install_id}</b> · ครั้งที่ต่ออายุ "
                         f"<b>{lic.renewals + 1}</b>")
            idl.setAlignment(Qt.AlignCenter)
            idl.setTextInteractionFlags(Qt.TextSelectableByMouse)
            lay.addWidget(idl)
            contact = QLabel(f"ติดต่อผู้พัฒนา โทร <b>{CONTACT_PHONE}</b> · "
                             f"<a href='{CONTACT_LINE}'>LINE</a>")
            contact.setOpenExternalLinks(True)
            contact.setAlignment(Qt.AlignCenter)
            lay.addWidget(contact)
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
            if lic.renew(self.code.text()):
                QMessageBox.information(self, PRODUCT, f"ต่ออายุแล้ว ใช้งานได้ถึงวันที่ {thai_date(lic.until)}")
                self.accept()
            else:
                self.error.setText("รหัสผ่านไม่ถูกต้อง กรุณาตรวจสอบกับผู้พัฒนา")

    return ExpiredDialog()


def require(parent=None, lic: License | None = None, warn: bool = True) -> bool:
    """False when the year is up and no renewal code was given (the program
    then closes). ``warn``: show the 30-day reminder (the start screen only)."""
    lic = lic or License()
    if lic.expired:
        from PySide6.QtWidgets import QDialog
        return _dialog(lic, parent).exec() == QDialog.Accepted
    if warn and lic.days_left <= WARN_DAYS:
        _dialog(lic, parent, warning=True).exec()
    return True
