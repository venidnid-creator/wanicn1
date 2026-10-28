# SPDX-License-Identifier: GPL-3.0-or-later
"""WANICNSURVEY start screen: pick 2D drafting or the 3D model.

The suite installs as::

    <install dir>\\launcher\\wanicnsurvey.exe   (this window)
    <install dir>\\cad\\ingecad.exe             WANICNSURVEY CAD (2D)
    <install dir>\\3d\\ingetrazo.exe            WANICNSURVEY 3D

From a source checkout the sibling folders' main.py run instead.
Usage: ``wanicnsurvey [file]`` - a file on the command line goes straight
to the program that opens it.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from PySide6.QtCore import QProcess, QSettings, QSize, Qt
from PySide6.QtGui import QFont, QIcon, QPixmap
from PySide6.QtWidgets import (QApplication, QFileDialog, QFrame, QHBoxLayout,
                               QLabel, QListWidget, QListWidgetItem,
                               QMessageBox, QPushButton, QVBoxLayout, QWidget)

PRODUCT = "WANICNSURVEY"
TAGLINE = "สำรวจ · เขียนแบบ 2 มิติ · ขึ้นโมเดล 3 มิติ — ใช้งานได้ฟรี"
DEVELOPER = "พัฒนาโดย นายเวนิช ธัมมะวงษ์ วิศวกรสำรวจ · 2569"
CREDIT = ("พัฒนาต่อยอดจากซอฟต์แวร์เสรี IngeCAD และ IngeTrazo "
          "ของ Marco Sumari Tellez · GPL-3.0 · ใช้งานได้ฟรี")

NAVY, ORANGE, BRASS, IVORY, MUTED = "#0F2A44", "#C46420", "#C9A14A", "#F6F3EC", "#55657A"

CAD_EXT = {".dwg", ".dxf"}
MODEL_EXT = {".igz", ".skp", ".dae", ".obj", ".stl", ".glb", ".gltf"}


def _frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def suite_root() -> Path:
    """The folder that holds cad/, 3d/ and launcher/."""
    if _frozen():
        return Path(sys.executable).resolve().parent.parent
    return Path(__file__).resolve().parent.parent


def asset(name: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent / "branding"))
    for p in (base / name, base / "branding" / name, base / "png" / name,
              base / "branding" / "png" / name):
        if p.exists():
            return p
    return base / name


def command(which: str) -> list[str] | None:
    root = suite_root()
    if _frozen():
        exe = root / which / ("ingecad.exe" if which == "cad" else "ingetrazo.exe")
        return [str(exe)] if exe.exists() else None
    script = root / which / "main.py"
    return [sys.executable, str(script)] if script.exists() else None


def start(which: str, files=()) -> bool:
    cmd = command(which)
    if not cmd:
        return False
    result = QProcess.startDetached(cmd[0], cmd[1:] + [str(f) for f in files])
    return bool(result[0] if isinstance(result, tuple) else result)


def program_for(path: Path) -> str | None:
    ext = path.suffix.lower()
    if ext in CAD_EXT:
        return "cad"
    if ext in MODEL_EXT:
        return "3d"
    return None


# ---- recent files --------------------------------------------------------

def recent_cad() -> list[Path]:
    """IngeCAD keeps them in %APPDATA%\\IngeCAD\\recent.json."""
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    try:
        data = json.loads((base / "IngeCAD" / "recent.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    out = [Path(p) for p in data if isinstance(p, str)] if isinstance(data, list) else []
    return [p for p in out if p.exists()][:8]


def recent_3d() -> list[Path]:
    raw = QSettings("WANICNSURVEY", "WANICNSURVEY 3D").value("recent_files", []) or []
    if isinstance(raw, str):
        raw = [raw]
    return [Path(p) for p in raw if p and Path(p).exists()][:8]


# ---- the window ----------------------------------------------------------

class Card(QPushButton):
    def __init__(self, icon: Path, title: str, subtitle: str, accent: str) -> None:
        super().__init__()
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(118)
        self.setObjectName("card")
        self.setStyleSheet(f"""
            QPushButton#card {{ background: white; border: 1px solid #D9D4C7;
                border-radius: 14px; text-align: left; padding: 18px; }}
            QPushButton#card:hover {{ border: 2px solid {accent}; background: #FFFDF8; }}
            QPushButton#card:focus {{ border: 2px solid {accent}; }}""")
        row = QHBoxLayout(self)
        row.setContentsMargins(20, 16, 20, 16)
        row.setSpacing(18)
        pic = QLabel()
        pic.setPixmap(QPixmap(str(icon)).scaled(72, 72, Qt.KeepAspectRatio,
                                                Qt.SmoothTransformation))
        pic.setAttribute(Qt.WA_TransparentForMouseEvents)
        row.addWidget(pic)
        col = QVBoxLayout()
        col.setSpacing(4)
        t = QLabel(title)
        t.setStyleSheet(f"font-size: 22px; font-weight: 700; color: {NAVY};")
        s = QLabel(subtitle)
        s.setStyleSheet(f"font-size: 13px; color: {MUTED};")
        s.setWordWrap(True)
        for w in (t, s):
            w.setAttribute(Qt.WA_TransparentForMouseEvents)
            col.addWidget(w)
        row.addLayout(col, 1)


class RecentList(QListWidget):
    def __init__(self, which: str) -> None:
        super().__init__()
        self.which = which
        self.setFrameShape(QFrame.NoFrame)
        self.setStyleSheet("QListWidget { background: transparent; font-size: 13px; }"
                           "QListWidget::item { padding: 4px 2px; }"
                           "QListWidget::item:hover { background: #ECE6D8; }")
        self.itemActivated.connect(self._open)
        self.itemClicked.connect(self._open)

    def fill(self, paths: list[Path], empty: str) -> None:
        self.clear()
        if not paths:
            item = QListWidgetItem(empty)
            item.setFlags(Qt.NoItemFlags)
            self.addItem(item)
            return
        for p in paths:
            item = QListWidgetItem(p.name)
            item.setToolTip(str(p))
            item.setData(Qt.UserRole, str(p))
            self.addItem(item)

    def _open(self, item: QListWidgetItem) -> None:
        path = item.data(Qt.UserRole)
        if path:
            self.window().launch(self.which, [path])


class StartWindow(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(PRODUCT)
        self.setWindowIcon(QIcon(str(asset("wanicnsurvey.ico"))))
        self.setAcceptDrops(True)
        self.resize(940, 680)
        self.setObjectName("root")
        self.setStyleSheet(f"QWidget#root {{ background: {IVORY}; }}")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(44, 32, 44, 18)
        outer.setSpacing(22)

        # header
        head = QHBoxLayout()
        head.setSpacing(20)
        logo = QLabel()
        logo.setPixmap(QPixmap(str(asset("wanicnsurvey-128.png"))).scaled(
            96, 96, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        head.addWidget(logo)
        words = QVBoxLayout()
        words.setSpacing(4)
        name = QLabel(f"<span style='color:{NAVY}; font-weight:800'>WANICN</span>"
                      f"<span style='color:{ORANGE}; font-weight:300'>SURVEY</span>")
        name.setStyleSheet("font-size: 40px;")
        tag = QLabel(TAGLINE)
        tag.setStyleSheet(f"font-size: 15px; color: {NAVY};")
        dev = QLabel(DEVELOPER)
        dev.setStyleSheet(f"font-size: 12px; color: {MUTED};")
        for w in (name, tag, dev):
            words.addWidget(w)
        head.addLayout(words, 1)
        outer.addLayout(head)

        # the two programs
        cards = QHBoxLayout()
        cards.setSpacing(18)
        cad = Card(asset("wanicnsurvey-cad-128.png"), "เขียนแบบ 2 มิติ",
                   "แปลน รูปตัด งานสำรวจ เส้นชั้นความสูง ดินตัด/ดินถม · DWG / DXF", "#E8772E")
        model = Card(asset("wanicnsurvey-3d-128.png"), "โมเดล 3 มิติ",
                     "ขึ้นรูป ดัน/ดึง วัดระยะ ถอดปริมาณ ภูมิประเทศ · IGZ / SKP", "#3BA3D8")
        cad.clicked.connect(lambda: self.launch("cad"))
        model.clicked.connect(lambda: self.launch("3d"))
        cards.addWidget(cad, 1)
        cards.addWidget(model, 1)
        outer.addLayout(cards)

        # actions
        bar = QHBoxLayout()
        open_btn = QPushButton("เปิดไฟล์…")
        open_btn.setCursor(Qt.PointingHandCursor)
        open_btn.setMinimumHeight(40)
        open_btn.setStyleSheet(f"QPushButton {{ background: {NAVY}; color: white; border: none;"
                               " border-radius: 8px; padding: 0 22px; font-size: 14px; }"
                               "QPushButton:hover { background: #1B4470; }")
        open_btn.clicked.connect(self.open_file)
        bar.addWidget(open_btn)
        bar.addStretch(1)
        hint = QLabel("ลากไฟล์มาวางที่หน้าต่างนี้ได้")
        hint.setStyleSheet(f"font-size: 12px; color: {MUTED};")
        bar.addWidget(hint)
        outer.addLayout(bar)

        # recent files
        lists = QHBoxLayout()
        lists.setSpacing(24)
        self.recent_cad = RecentList("cad")
        self.recent_3d = RecentList("3d")
        for title, colour, widget in (("แบบ 2 มิติล่าสุด", "#C46420", self.recent_cad),
                                      ("โมเดล 3 มิติล่าสุด", "#1F7DB0", self.recent_3d)):
            col = QVBoxLayout()
            col.setSpacing(6)
            lab = QLabel(title)
            lab.setStyleSheet(f"font-size: 14px; font-weight: 700; color: {colour};")
            col.addWidget(lab)
            col.addWidget(widget, 1)
            lists.addLayout(col, 1)
        outer.addLayout(lists, 1)

        foot = QLabel(CREDIT)
        foot.setStyleSheet(f"font-size: 11px; color: {MUTED};")
        foot.setWordWrap(True)
        outer.addWidget(foot)
        self.refresh()

    def refresh(self) -> None:
        self.recent_cad.fill(recent_cad(), "ยังไม่มีแบบ 2 มิติ — กด «เขียนแบบ 2 มิติ» หรือ «เปิดไฟล์…»")
        self.recent_3d.fill(recent_3d(), "ยังไม่มีโมเดล 3 มิติ — กด «โมเดล 3 มิติ» หรือ «เปิดไฟล์…»")

    def launch(self, which: str, files=()) -> None:
        if start(which, files):
            self.close()
        else:
            QMessageBox.warning(self, PRODUCT,
                                "ไม่พบโปรแกรมในโฟลเดอร์ติดตั้ง — ลองติดตั้ง WANICNSURVEY ใหม่")

    def open_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "เปิดไฟล์", "",
            "ไฟล์ที่รองรับ (*.dwg *.dxf *.igz *.skp *.dae *.obj *.stl *.glb *.gltf);;"
            "แบบ 2 มิติ (*.dwg *.dxf);;โมเดล 3 มิติ (*.igz *.skp *.dae *.obj *.stl *.glb *.gltf)")
        if path:
            self.open_paths([Path(path)])

    def open_paths(self, paths: list[Path]) -> None:
        for which in ("cad", "3d"):
            mine = [p for p in paths if program_for(p) == which]
            if mine:
                self.launch(which, mine)
                return
        QMessageBox.information(self, PRODUCT, "ไฟล์ชนิดนี้ยังเปิดด้วย WANICNSURVEY ไม่ได้")

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        paths = [Path(u.toLocalFile()) for u in event.mimeData().urls() if u.isLocalFile()]
        if paths:
            self.open_paths(paths)


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("WANICNSURVEY")
    app.setOrganizationName("WANICNSURVEY")
    font = QFont()
    font.setFamilies(["Leelawadee UI", "Segoe UI", "Noto Sans Thai", "Tahoma"])
    font.setPointSize(10)
    app.setFont(font)
    files = [Path(a) for a in sys.argv[1:] if not a.startswith("-")]
    if files:
        which = program_for(files[0])
        if which and start(which, files):
            return 0
    win = StartWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
