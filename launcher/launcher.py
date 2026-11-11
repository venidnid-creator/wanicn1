# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
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
DEVELOPER = "ลิขสิทธิ์ © 2569 นายเวนิช ธัมมะวงษ์ วิศวกรสำรวจ"
CREDIT = ("พัฒนาต่อยอดจากซอฟต์แวร์เสรี IngeCAD และ IngeTrazo "
          "ของ Marco Sumari Tellez · GPL-3.0 · ใช้งานได้ฟรี")

NAVY, ORANGE, BRASS, IVORY, MUTED = "#0F2A44", "#C46420", "#C9A14A", "#F6F3EC", "#55657A"

#: The developer and how to support the work (shown beside the programs).
FREE_USE = "โปรแกรมใช้ได้ฟรี ไม่มีค่าลิขสิทธิ์"
SUPPORT = "สนใจสนับสนุนผู้พัฒนา สามารถทำได้ที่"
BANK = "ธนาคารกรุงศรีอยุธยา สาขาโลตัส ถลาง ภูเก็ต"
ACCOUNT_NAME = "นายเวนิช ธัมมะวงษ์"
ACCOUNT_NO = "666-1-32472-1"
ACCOUNT_TYPE = "บัญชีออมทรัพย์"

CAD_EXT = {".dwg", ".dxf"}
MODEL_EXT = {".igz", ".skp", ".dae", ".obj", ".stl", ".glb", ".gltf"}


def _frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def suite_root() -> Path:
    """The folder that holds cad/, 3d/ and launcher/."""
    if _frozen():
        return Path(sys.executable).resolve().parent.parent
    return Path(__file__).resolve().parent.parent


CONTACT_TEXT = "ติดต่อผู้พัฒนาระบบ"
CONTACT_PHONE = "093-5838348"
CONTACT_QR = "contact-qr.png"          # LINE: https://line.me/ti/p/E-p-C9tCEx (tools/qr.py)
CONTACT_LINE = "https://line.me/ti/p/E-p-C9tCEx"
SCRIPT_FONT = "Charm-Bold.ttf"         # ลายมือไทย Charm (SIL Open Font License)


def thai_script_font(px: int) -> QFont:
    """The bundled Thai calligraphic face at ``px`` pixels; the system Thai
    face when it cannot be loaded."""
    from PySide6.QtGui import QFontDatabase
    fid = QFontDatabase.addApplicationFont(str(asset(SCRIPT_FONT)))
    fams = QFontDatabase.applicationFontFamilies(fid) if fid >= 0 else []
    f = QFont(fams[0]) if fams else QFont("Leelawadee UI")
    f.setPixelSize(px)
    f.setBold(True)
    return f


def _version() -> str:
    """The installed version (the installer writes it beside the program)."""
    for p in (Path(getattr(sys, "_MEIPASS", "")) / "VERSION",
              Path(sys.executable).resolve().parent / "VERSION",
              Path(__file__).resolve().parent / "VERSION"):
        try:
            return p.read_text(encoding="utf-8").strip()
        except OSError:
            continue
    return "dev"


def asset(name: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent / "branding"))
    for p in (base / name, base / "branding" / name, base / "png" / name,
              base / "branding" / "png" / name, base / "fonts" / name,
              base / "branding" / "fonts" / name):
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

#: The five themes (the same names and colours as ReadWanicn2027).
THEMES = {
    "blueprint": dict(th="บลูพริ้นท์", en="Blueprint", bg="#0B1F33", bar="#0E2238", side="#081726",
                      side_text="#E6EEF7", side_muted="#9DB4CC", side_border="#23466B", text="#E6EEF7",
                      muted="#A9BED3", accent="#F5B400", accent_ink="#1A1A1A", accent_text="#F5B400",
                      border="#23466B", card="#10283F", chip="#1A3B5C", nav_on="#1A3B5C", dark=True),
    "light": dict(th="สว่าง", en="Light", bg="#F4F6F9", bar="#FFFFFF", side="#FFFFFF", side_text="#1C2733",
                  side_muted="#556372", side_border="#D6DCE3", text="#1C2733", muted="#556372",
                  accent="#1F6FEB", accent_ink="#FFFFFF", accent_text="#1F5FCC", border="#D6DCE3",
                  card="#FFFFFF", chip="#E4ECF7", nav_on="#E4ECF7", dark=False),
    "dark": dict(th="มืด", en="Dark", bg="#18191C", bar="#1E1F22", side="#141517", side_text="#E8E8E8",
                 side_muted="#A0A4AB", side_border="#34363B", text="#E8E8E8", muted="#A9ADB3",
                 accent="#5AA9FF", accent_ink="#0E0E0E", accent_text="#7DBBFF", border="#34363B",
                 card="#232428", chip="#2F3136", nav_on="#2F3136", dark=True),
    "gold": dict(th="ทองเวนิช", en="Venit Gold", bg="#F3EEE4", bar="#FBF8F2", side="#0F2A44",
                 side_text="#F3EEE4", side_muted="#C9BFA9", side_border="#2A4A6B", text="#1D2633",
                 muted="#5C5446", accent="#C9A227", accent_ink="#0F2A44", accent_text="#8A6D12",
                 border="#DDD3BF", card="#FBF8F2", chip="#EFE5CF", nav_on="#1D4268", dark=False),
    "green": dict(th="เขียวสำรวจ", en="Survey Green", bg="#EEF5EF", bar="#FFFFFF", side="#14532D",
                  side_text="#ECFDF3", side_muted="#B7D9C2", side_border="#2B6B44", text="#13261A",
                  muted="#46604D", accent="#16A34A", accent_ink="#FFFFFF", accent_text="#137A38",
                  border="#CFE3D3", card="#FFFFFF", chip="#DCEFE0", nav_on="#1F6B3D", dark=False),
}
DEFAULT_THEME = "gold"

#: Every word of the start screen, in Thai and English.
TEXT = {
    "th": dict(
        suite="2027 · ชุดโปรแกรมสำรวจ เขียนแบบ ออกแบบ", ready="พร้อมใช้งาน · รุ่น {v}", theme="ธีม",
        hero="จากหมุดสำรวจ สู่แบบก่อสร้างและปริมาณงาน",
        hero_sub="สำรวจ เขียนแบบ 2 มิติ ขึ้นโมเดล 3 มิติ ออกแบบโครงสร้าง คสล. พร้อมเหล็กเสริม "
                 "และถอดปริมาณงาน (BOQ) ในชุดโปรแกรมเดียว",
        start="เริ่มงานใหม่  →", new="ใหม่", open="เปิดไฟล์…", drop="ลากไฟล์มาวางที่หน้าต่างนี้ได้",
        link_title="ข้อมูลเชื่อมกันทั้งชุด",
        link_sub="แบบ 2 มิติ โมเดล 3 มิติ และบัญชีปริมาณงานมาจากข้อมูลชุดเดียวกัน",
        recent="ไฟล์ล่าสุด", no_recent="ยังไม่มีไฟล์ — กดการ์ดด้านบนหรือ «เปิดไฟล์…»",
        nav=["หน้าหลัก", "เขียนแบบ 2 มิติ", "โมเดล 3 มิติ", "ออกแบบโครงสร้าง คสล.", "ออกแบบถนน",
             "ถอดปริมาณ / BOQ", "เปิดไฟล์", "สถิติผู้ใช้โปรแกรม"],
        cards=[("เขียนแบบ 2 มิติ", "แปลน รูปด้าน รูปตัด งานสำรวจ ภูมิประเทศ เส้นชั้นความสูง และดินตัด-ดินถม"),
               ("โมเดล 3 มิติ", "ขึ้นรูป ดัน-ดึง ออกแบบอาคาร หลังคาตามแบบมาตรฐาน วัดระยะ และภาพทัศนียภาพ"),
               ("ออกแบบโครงสร้าง คสล.", "กริด ฐานราก เสาเข็ม ตอม่อ เสา คาน พื้น ถึงโครงหลังคา "
                                        "พร้อมเหล็กเสริมและบัญชีปริมาณงาน"),
               ("ออกแบบถนน", "แนวทาง รูปตัดตามยาว-ตามขวาง ดินตัด-ดินถม ชั้นทาง ทช./ทล. และแบบมาตรฐาน")],
        dev="ผู้พัฒนา", dev_role="วิศวกรสำรวจ", stats="สถิติผู้ใช้โปรแกรม",
        contact=CONTACT_TEXT, line="สแกนเพิ่มเพื่อน LINE", free=FREE_USE, support=SUPPORT, bank=BANK,
        acc_name=f"ชื่อบัญชี {ACCOUNT_NAME}", acc_no="เลขที่บัญชี", acc_type=ACCOUNT_TYPE,
        copy="คัดลอกเลขที่บัญชี", copied="คัดลอกแล้ว ✓", thanks="ขอบคุณที่ใช้งานและสนับสนุนครับ",
        credit=CREDIT, update="↻ อัปเดตตัวเลข",
        missing="ไม่พบโปรแกรมในโฟลเดอร์ติดตั้ง — ลองติดตั้ง WANICNSURVEY ใหม่",
        cannot="ไฟล์ชนิดนี้ยังเปิดด้วย WANICNSURVEY ไม่ได้", open_title="เปิดไฟล์"),
    "en": dict(
        suite="2027 · Survey · Drafting · Design suite", ready="Ready · version {v}", theme="Theme",
        hero="From survey pegs to construction drawings and quantities",
        hero_sub="Survey, 2D drafting, 3D modelling, reinforced-concrete design with rebar and "
                 "quantity take-off (BOQ) in one suite",
        start="New project  →", new="NEW", open="Open file…", drop="You can drop files on this window",
        link_title="One model, every output",
        link_sub="The 2D drawings, the 3D model and the bill of quantities come from the same data",
        recent="Recent files", no_recent="No files yet — pick a card above or «Open file…»",
        nav=["Home", "2D drafting", "3D model", "RC structure design", "Road design", "Take-off / BOQ",
             "Open file", "User statistics"],
        cards=[("2D drafting", "Plans, elevations, sections, survey, terrain, contours, cut and fill"),
               ("3D model", "Push/pull modelling, building design, standard roofs, measuring and renderings"),
               ("RC structure design", "Grid, footings, piles, stubs, columns, beams and slabs up to the "
                                       "roof frame, with rebar and quantities"),
               ("Road design", "Alignment, profiles and cross-sections, cut and fill, pavement layers, "
                               "standard drawings")],
        dev="Developer", dev_role="Survey engineer", stats="User statistics",
        contact="Contact the developer", line="Scan to add on LINE", free="Free to use, no licence fee",
        support="To support the developer:", bank="Krungsri Bank, Lotus Thalang branch, Phuket",
        acc_name="Account name: Venit Thammawong", acc_no="Account", acc_type="Savings account",
        copy="Copy account number", copied="Copied ✓", thanks="Thank you for using and supporting it",
        credit="Built on the free software IngeCAD and IngeTrazo by Marco Sumari Tellez · GPL-3.0 · "
               "free to use", update="↻ Refresh",
        missing="The program is not in the install folder — reinstall WANICNSURVEY",
        cannot="WANICNSURVEY cannot open this kind of file yet", open_title="Open file"),
}

#: The cards: (tag, program, 3D panel to open, icon path (24×24 stroke), files)
CARDS = [("2D", "cad", "", "M3 21V3h18v18H3zM3 9h18M9 21V9", "DWG · DXF"),
         ("3D", "3d", "", "M12 2l9 5v10l-9 5-9-5V7l9-5zM12 12l9-5M12 12v10M12 12L3 7", "IGZ · SKP · OBJ"),
         ("RC", "3d", "building", "M4 21V8M12 21V8M20 21V8M2 8h20M4 21h16M8 4h8l4 4H4l4-4z",
          "IGZ · DXF · XLSX"),
         ("ROAD", "3d", "road", "M4 21L10 3M20 21L14 3M12 7v2M12 12v2M12 17v2", "CSV · DXF · PDF")]

#: Thai phrases of the statistics box, for the English screen.
STATS_EN = [("ดาวน์โหลดสะสม", "Downloads"), ("ครั้ง", "times"), ("รุ่นล่าสุด", "Latest"),
            ("ผู้ใช้งานสะสม", "Users"), ("คน (เครื่องที่เคยเปิดใช้)", "(computers that opened it)"),
            ("เปิดใช้งานสะสม", "Openings"), ("ใช้งานอยู่ขณะนี้", "Online now"), ("วันนี้", "today"),
            ("คน", ""), ("ข้อมูล ณ", "As of"), ("ออฟไลน์", "offline"), ("ปรับปรุงล่าสุด", "Updated"),
            ("มีรุ่นใหม่", "New version"), ("รุ่นที่ใช้อยู่", "Installed"),
            ("กำลังอัปเดต…", "updating…")]


def stroke_icon(path: str, color: str, px: int = 34) -> QPixmap:
    """A 24×24 stroke icon drawn at ``px`` in ``color``."""
    from PySide6.QtCore import QByteArray
    from PySide6.QtGui import QPainter
    from PySide6.QtSvg import QSvgRenderer
    svg = (f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' "
           f"stroke='{color}' stroke-width='1.6' stroke-linecap='round' stroke-linejoin='round'>"
           f"<path d='{path}'/></svg>")
    pm = QPixmap(px * 2, px * 2)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    QSvgRenderer(QByteArray(svg.encode())).render(p)
    p.end()
    pm.setDevicePixelRatio(2)
    return pm


class StartWindow(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(PRODUCT)
        self.setWindowIcon(QIcon(str(asset("wanicnsurvey.ico"))))
        self.setAcceptDrops(True)
        self.resize(1440, 900)
        self.setObjectName("root")
        self.settings = QSettings(PRODUCT, "launcher")
        theme = str(self.settings.value("ui/theme", DEFAULT_THEME))
        self.theme = theme if theme in THEMES else DEFAULT_THEME
        lang = str(self.settings.value("ui/lang", "th"))
        self.lang = lang if lang in TEXT else "th"
        self._stats_html = ""
        self.stats_label = None
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)
        self.build()
        self._start_stats()

    # -- building the screen (again on a theme or language change) ----------
    @property
    def t(self) -> dict:
        return TEXT[self.lang]

    @property
    def c(self) -> dict:
        return THEMES[self.theme]

    def build(self) -> None:
        while self._layout.count():
            item = self._layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()
        c = self.c
        self.setStyleSheet(f"""
            QWidget#root {{ background: {c['bg']}; }}
            QWidget {{ color: {c['text']}; font-size: 14px; }}
            QLabel {{ background: transparent; }}
            QFrame#side {{ background: {c['side']}; border-right: 1px solid {c['border']}; }}
            QFrame#side QLabel {{ color: {c['side_text']}; }}
            QPushButton#nav {{ background: transparent; color: {c['side_text']}; border: 0;
                border-radius: 10px; text-align: left; padding: 0 14px; min-height: 44px; font-size: 15px; }}
            QPushButton#nav:hover {{ background: {c['nav_on']}; }}
            QPushButton#nav[on="true"] {{ background: {c['nav_on']}; font-weight: 700;
                border-left: 4px solid {c['accent']}; }}
            QFrame#bar {{ background: {c['bar']}; border-bottom: 1px solid {c['border']}; }}
            QPushButton#pill {{ background: transparent; color: {c['text']}; border: 1px solid {c['border']};
                border-radius: 18px; padding: 0 14px; min-height: 36px; }}
            QPushButton#pill:hover {{ border-color: {c['accent']}; }}
            QPushButton#pill[on="true"] {{ background: {c['accent']}; color: {c['accent_ink']};
                border-color: {c['accent']}; font-weight: 700; }}
            QFrame#card {{ background: {c['card']}; border: 1px solid {c['border']}; border-radius: 16px; }}
            QFrame#card[hot="true"] {{ border: 2px solid {c['accent']}; }}
            QPushButton#go {{ background: {c['chip']}; color: {c['text']}; border: 0; border-radius: 10px;
                padding: 0 20px; min-height: 42px; font-weight: 600; }}
            QPushButton#go:hover, QPushButton#go[hot="true"] {{ background: {c['accent']};
                color: {c['accent_ink']}; }}
            QFrame#support {{ background: {c['bar']}; border-left: 1px solid {c['border']}; }}
            QListWidget {{ background: transparent; border: 0; }}
            QListWidget::item {{ padding: 4px 2px; }}
            QListWidget::item:hover {{ background: {c['chip']}; }}
            QScrollArea {{ background: transparent; border: 0; }}
            QScrollArea > QWidget > QWidget {{ background: transparent; }}
            QToolTip {{ background: {c['card']}; color: {c['text']}; border: 1px solid {c['border']}; }}
            """)
        self._layout.addWidget(self._sidebar())
        main = QFrame()
        col = QVBoxLayout(main)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(0)
        col.addWidget(self._top_bar())
        body = QHBoxLayout()
        body.setSpacing(0)
        from PySide6.QtWidgets import QScrollArea
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidget(self._content())
        body.addWidget(scroll, 1)
        side = QScrollArea()
        side.setWidget(self._support_panel())
        side.setWidgetResizable(True)
        side.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        side.setFrameShape(QFrame.NoFrame)
        side.setFixedWidth(316)
        body.addWidget(side)
        col.addLayout(body, 1)
        self._layout.addWidget(main, 1)
        self.refresh()

    def _sidebar(self) -> QFrame:
        c, t = self.c, self.t
        box = QFrame()
        box.setObjectName("side")
        box.setFixedWidth(270)
        col = QVBoxLayout(box)
        col.setContentsMargins(16, 22, 16, 18)
        col.setSpacing(4)
        head = QHBoxLayout()
        logo = QLabel()
        logo.setPixmap(QPixmap(str(asset("wanicnsurvey-128.png"))).scaled(
            52, 52, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        head.addWidget(logo)
        words = QVBoxLayout()
        words.setSpacing(0)
        name = QLabel(f"<span style='font-weight:800'>WANICN</span>"
                      f"<span style='color:{c['accent']}; font-weight:400'>SURVEY</span>")
        name.setStyleSheet("font-size: 21px;")
        sub = QLabel(t["suite"])
        sub.setStyleSheet(f"font-size: 12px; color: {c['side_muted']};")
        sub.setWordWrap(True)
        words.addWidget(name)
        words.addWidget(sub)
        head.addLayout(words, 1)
        col.addLayout(head)
        col.addSpacing(14)
        actions = [lambda: None, lambda: self.launch("cad"), lambda: self.launch("3d"),
                   lambda: self.launch("3d", panel="building"), lambda: self.launch("3d", panel="road"),
                   lambda: self.launch("3d", panel="takeoff"), self.open_file, self._show_stats]
        for i, (label, fn) in enumerate(zip(t["nav"], actions)):
            b = QPushButton(f"  {label}")
            b.setObjectName("nav")
            b.setProperty("on", i == 0)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(fn)
            col.addWidget(b)
        col.addStretch(1)
        who = "นายเวนิช ธัมมะวงษ์" if self.lang == "th" else "Venit Thammawong"
        dev = QLabel(f"{t['dev']}: {who}<br>{t['dev_role']}")
        dev.setStyleSheet(f"font-size: 12px; color: {c['side_muted']};")
        col.addWidget(dev)
        return box

    def _top_bar(self) -> QFrame:
        c, t = self.c, self.t
        bar = QFrame()
        bar.setObjectName("bar")
        bar.setFixedHeight(68)
        row = QHBoxLayout(bar)
        row.setContentsMargins(28, 0, 20, 0)
        row.setSpacing(8)
        dot = QLabel("●")
        dot.setStyleSheet("color: #22C55E; font-size: 12px;")
        row.addWidget(dot)
        ready = QLabel(t["ready"].format(v=_version()))
        ready.setStyleSheet(f"color: {c['muted']};")
        row.addWidget(ready)
        row.addStretch(1)
        lab = QLabel(t["theme"])
        lab.setStyleSheet(f"color: {c['muted']};")
        row.addWidget(lab)
        for key, th in THEMES.items():
            b = QPushButton(th[self.lang])
            b.setObjectName("pill")
            b.setProperty("on", key == self.theme)
            b.setCursor(Qt.PointingHandCursor)
            b.setIcon(self._swatch(th["accent"]))
            b.clicked.connect(lambda _=False, k=key: self.set_theme(k))
            row.addWidget(b)
        row.addSpacing(10)
        for code, label in (("th", "ไทย"), ("en", "EN")):
            b = QPushButton(label)
            b.setObjectName("pill")
            b.setProperty("on", code == self.lang)
            b.setMinimumWidth(58)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _=False, k=code: self.set_lang(k))
            row.addWidget(b)
        return bar

    @staticmethod
    def _swatch(color: str) -> QIcon:
        from PySide6.QtGui import QColor, QPainter
        pm = QPixmap(28, 28)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        p.setBrush(QColor(color))
        p.setPen(QColor("#888888"))
        p.drawEllipse(2, 2, 24, 24)
        p.end()
        return QIcon(pm)

    def _content(self) -> QWidget:
        c, t = self.c, self.t
        page = QWidget()
        col = QVBoxLayout(page)
        col.setContentsMargins(30, 20, 26, 14)
        col.setSpacing(14)
        top = QHBoxLayout()
        words = QVBoxLayout()
        words.setSpacing(6)
        kicker = QLabel("WANICNSURVEY HUB")
        kicker.setStyleSheet(f"color: {c['accent_text']}; font-size: 13px; font-weight: 700; "
                             "letter-spacing: 3px;")
        hero = QLabel(t["hero"])
        hero.setWordWrap(True)
        hero.setStyleSheet("font-size: 27px; font-weight: 700;")
        sub = QLabel(t["hero_sub"])
        sub.setWordWrap(True)
        sub.setStyleSheet(f"color: {c['muted']}; font-size: 15px;")
        for w in (kicker, hero, sub):
            words.addWidget(w)
        top.addLayout(words, 1)
        top.addWidget(self._stats_box(), 0, Qt.AlignTop)
        col.addLayout(top)
        from PySide6.QtWidgets import QGridLayout
        grid = QGridLayout()
        grid.setSpacing(18)
        tints = (["#E4ECF7", "#FDF2D6", "#FDE2E2", "#DDF3E4"] if not c["dark"]
                 else ["#163A5E", "#3D3210", "#4A1F1F", "#163D27"])
        inks = (["#1F5FCC", "#8A6D12", "#B42318", "#137A38"] if not c["dark"]
                else ["#8CC4FF", "#F5C842", "#FF9C9C", "#7FE0A4"])
        for i, ((title, desc), (tag, prog, panel, icon, files)) in enumerate(zip(t["cards"], CARDS)):
            grid.addWidget(self._card(i == 2, tag, title, desc, files, icon, tints[i], inks[i],
                                      lambda _=False, p=prog, pn=panel: self.launch(p, panel=pn)),
                           i // 2, i % 2)
        col.addLayout(grid)
        bottom = QHBoxLayout()
        bottom.setSpacing(18)
        link = QFrame()
        link.setObjectName("card")
        lr = QHBoxLayout(link)
        lr.setContentsMargins(20, 16, 20, 16)
        lr.setSpacing(10)
        for i, word in enumerate(("2D", "3D", "BOQ")):
            if i:
                arrow = QLabel("⇄")
                arrow.setStyleSheet(f"color: {c['muted']};")
                lr.addWidget(arrow)
            chip = QLabel(word)
            chip.setAlignment(Qt.AlignCenter)
            chip.setFixedSize(54, 40)
            chip.setStyleSheet(f"background: {c['chip']}; color: {c['text']}; border-radius: 10px; "
                               "font-weight: 700; font-size: 13px;")
            lr.addWidget(chip)
        lw = QVBoxLayout()
        lt = QLabel(t["link_title"])
        lt.setStyleSheet("font-weight: 700; font-size: 16px;")
        ls = QLabel(t["link_sub"])
        ls.setWordWrap(True)
        ls.setStyleSheet(f"color: {c['muted']};")
        lw.addWidget(lt)
        lw.addWidget(ls)
        lr.addLayout(lw, 1)
        link.setMaximumHeight(110)
        bottom.addWidget(link, 2, Qt.AlignTop)
        rec = QFrame()
        rec.setObjectName("card")
        rc = QVBoxLayout(rec)
        rc.setContentsMargins(18, 14, 18, 14)
        rh = QHBoxLayout()
        rt = QLabel(t["recent"])
        rt.setStyleSheet("font-weight: 700; font-size: 16px;")
        rh.addWidget(rt, 1)
        ob = QPushButton(t["open"])
        ob.setObjectName("go")
        ob.setProperty("hot", True)
        ob.setCursor(Qt.PointingHandCursor)
        ob.clicked.connect(self.open_file)
        rh.addWidget(ob)
        rc.addLayout(rh)
        self.recent = QListWidget()
        self.recent.setMinimumHeight(72)
        self.recent.setMaximumHeight(120)
        self.recent.setWordWrap(True)
        self.recent.itemActivated.connect(self._open_recent)
        self.recent.itemClicked.connect(self._open_recent)
        rc.addWidget(self.recent)
        hint = QLabel(t["drop"])
        hint.setStyleSheet(f"color: {c['muted']}; font-size: 12px;")
        rc.addWidget(hint)
        bottom.addWidget(rec, 1, Qt.AlignTop)
        col.addLayout(bottom)
        col.addStretch(1)
        foot = QLabel(t["credit"] + " · " + DEVELOPER)
        foot.setWordWrap(True)
        foot.setStyleSheet(f"color: {c['muted']}; font-size: 11px;")
        col.addWidget(foot)
        return page

    def _card(self, hot, tag, title, desc, files, icon, tint, ink, fn) -> QFrame:
        c, t = self.c, self.t
        card = QFrame()
        card.setObjectName("card")
        card.setProperty("hot", hot)
        row = QHBoxLayout(card)
        row.setContentsMargins(20, 16, 20, 16)
        row.setSpacing(16)
        pic = QLabel()
        pic.setFixedSize(64, 64)
        pic.setAlignment(Qt.AlignCenter)
        pic.setStyleSheet(f"background: {tint}; border-radius: 14px;")
        pic.setPixmap(stroke_icon(icon, ink))
        row.addWidget(pic, 0, Qt.AlignTop)
        col = QVBoxLayout()
        col.setSpacing(6)
        tags = QHBoxLayout()
        tl = QLabel(tag)
        tl.setStyleSheet(f"background: {tint}; color: {ink}; border-radius: 6px; padding: 2px 10px; "
                         "font-size: 12px; font-weight: 700;")
        tags.addWidget(tl)
        if hot:
            nl = QLabel(t["new"])
            nl.setStyleSheet("background: #DC2626; color: white; border-radius: 6px; padding: 2px 10px; "
                             "font-size: 12px; font-weight: 700;")
            tags.addWidget(nl)
        tags.addStretch(1)
        col.addLayout(tags)
        tt = QLabel(title)
        tt.setStyleSheet("font-size: 21px; font-weight: 700;")
        dd = QLabel(desc)
        dd.setWordWrap(True)
        dd.setStyleSheet(f"color: {c['muted']}; font-size: 13px;")
        col.addWidget(tt)
        col.addWidget(dd)
        fr = QHBoxLayout()
        fl = QLabel(files)
        fl.setStyleSheet(f"color: {c['muted']}; font-size: 12px;")
        fr.addWidget(fl, 1)
        go = QPushButton(t["start"])
        go.setObjectName("go")
        go.setProperty("hot", hot)
        go.setCursor(Qt.PointingHandCursor)
        go.clicked.connect(fn)
        fr.addWidget(go)
        col.addLayout(fr)
        row.addLayout(col, 1)
        return card

    # -- statistics -----------------------------------------------------------
    def _stats_box(self) -> QFrame:
        c, t = self.c, self.t
        box = QFrame()
        box.setObjectName("card")
        box.setFixedWidth(300)
        col = QVBoxLayout(box)
        col.setContentsMargins(14, 10, 14, 10)
        title = QLabel(f"<b>📊 {t['stats']}</b>")
        col.addWidget(title)
        self.stats_label = QLabel()
        self.stats_label.setWordWrap(True)
        self.stats_label.setOpenExternalLinks(True)
        self.stats_label.setStyleSheet("font-size: 12px;")
        col.addWidget(self.stats_label)
        ref = QLabel(f"<a href='#' style='color:{c['accent_text']}'>{t['update']}</a>")
        ref.setStyleSheet("font-size: 11px;")
        ref.linkActivated.connect(lambda _l: self._fetch_stats(False))
        col.addWidget(ref, 0, Qt.AlignRight)
        box.setToolTip("ยอดดาวน์โหลดนับจาก GitHub Releases · ผู้ใช้งานสะสมนับเครื่องที่เคยเปิดโปรแกรม "
                       "(ไม่ส่งข้อมูลส่วนตัว)")
        self._show_stats_text()
        return box

    def _show_stats_text(self) -> None:
        if self.stats_label is None:
            return
        html = self._stats_html
        if self.lang == "en":
            for th, en in STATS_EN:
                html = html.replace(th, en)
        try:
            self.stats_label.setText(html)
        except RuntimeError:                 # the old screen, already rebuilt
            pass

    def _start_stats(self) -> None:
        """Downloads (GitHub) and users (the developer's counter), fetched in
        the background; the last answer shows while offline."""
        from PySide6.QtCore import QTimer
        here = str(Path(__file__).resolve().parent)
        if here not in sys.path:
            sys.path.insert(0, here)
        import stats as ST
        self._ST = ST
        try:
            self._cached = json.loads(self.settings.value("usage/cache") or "{}")
        except (TypeError, ValueError):
            self._cached = {}
        self._stats_html = ST.text({}, self._cached, _version()) + \
            "<br><span style='color:#888'>กำลังอัปเดต…</span>"
        self._show_stats_text()
        self._state = {"busy": False}
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._poll_stats)
        self._fetch_stats(True)
        again = QTimer(self)
        again.timeout.connect(lambda: self._fetch_stats(False))
        again.start(10 * 60 * 1000)

    def _fetch_stats(self, count) -> None:
        import threading
        st = self._state
        if st["busy"]:
            return
        st["busy"], st["info"] = True, None

        def work():
            try:
                st["info"] = self._ST.fetch_all(self.settings, _version(), count=count)
            except Exception as e:                   # noqa: BLE001
                st["info"] = {"downloads_error": str(e)}
        threading.Thread(target=work, daemon=True).start()
        self._timer.start(300)

    def _poll_stats(self) -> None:
        info = self._state.get("info")
        if info is None:
            return
        self._timer.stop()
        self._state["busy"] = False
        keep = {k: v for k, v in info.items() if k in ("downloads", "usage", "at")}
        if keep.get("downloads"):
            self._cached.update(keep)
            self.settings.setValue("usage/cache", json.dumps(self._cached))
        self._stats_html = self._ST.text(info, self._cached, _version())
        self._show_stats_text()

    def _show_stats(self) -> None:
        self._fetch_stats(False)
        if self.stats_label is not None:
            self.stats_label.setFocus()

    # -- the developer ----------------------------------------------------------
    def _support_panel(self) -> QFrame:
        """The developer's photo, free use, and the account to support him."""
        c, t = self.c, self.t
        box = QFrame()
        box.setObjectName("support")
        box.setFixedWidth(300)
        col = QVBoxLayout(box)
        col.setContentsMargins(20, 22, 20, 18)
        col.setSpacing(8)
        photo = QLabel()
        pix = QPixmap(str(asset("developer.jpg")))
        if not pix.isNull():
            pm = pix.scaledToWidth(260, Qt.SmoothTransformation)
            photo.setPixmap(pm)
            photo.setFixedSize(pm.size())
        col.addWidget(photo, 0, Qt.AlignHCenter)
        row = QHBoxLayout()
        row.setSpacing(8)
        qr = QLabel()
        qpix = QPixmap(str(asset(CONTACT_QR)))
        if not qpix.isNull():
            qm = qpix.scaled(120, 120, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            qr.setPixmap(qm)
            qr.setFixedSize(qm.size())
            qr.setStyleSheet("background: white; border-radius: 6px;")
        qr.setToolTip(t["line"])
        row.addWidget(qr)
        contact = QLabel(f"{t['contact']}<br><span style='font-size:22px'>{CONTACT_PHONE}</span>"
                         f"<br><span style='font-size:14px;color:#06C755'>{t['line']}</span>")
        contact.setAlignment(Qt.AlignCenter)
        contact.setWordWrap(True)
        contact.setTextInteractionFlags(Qt.TextSelectableByMouse)
        contact.setFont(thai_script_font(17))
        row.addWidget(contact, 1)
        col.addLayout(row)
        free = QLabel(t["free"])
        free.setAlignment(Qt.AlignCenter)
        free.setWordWrap(True)
        free.setStyleSheet("font-size: 15px; font-weight: 700; color: #E2702A;")
        col.addWidget(free)
        info = QLabel(
            f"<div style='font-size:13px; line-height:140%'>{t['support']}<br><b>{t['bank']}</b><br>"
            f"{t['acc_name']}<br>{t['acc_no']} <b style='font-size:16px'>{ACCOUNT_NO}</b><br>"
            f"<span style='color:{c['muted']}'>{t['acc_type']}</span></div>")
        info.setAlignment(Qt.AlignCenter)
        info.setWordWrap(True)
        info.setTextInteractionFlags(Qt.TextSelectableByMouse)
        col.addWidget(info)
        copy = QPushButton(t["copy"])
        copy.setCursor(Qt.PointingHandCursor)
        copy.setStyleSheet(f"QPushButton {{ background: {BRASS}; color: white; border: none;"
                           " border-radius: 8px; padding: 0 12px; min-height: 40px; font-size: 14px; }"
                           "QPushButton:hover { background: #B08A36; }")

        def _copy() -> None:
            QApplication.clipboard().setText(ACCOUNT_NO.replace("-", ""))
            copy.setText(t["copied"])
        copy.clicked.connect(_copy)
        col.addWidget(copy)
        thanks = QLabel(t["thanks"])
        thanks.setAlignment(Qt.AlignCenter)
        thanks.setStyleSheet(f"font-size: 12px; color: {c['muted']};")
        col.addWidget(thanks)
        col.addStretch(1)
        return box

    # -- settings -----------------------------------------------------------------
    def set_theme(self, key: str) -> None:
        self.theme = key
        self.settings.setValue("ui/theme", key)
        self.build()

    def set_lang(self, code: str) -> None:
        self.lang = code
        self.settings.setValue("ui/lang", code)
        self.build()

    # -- files and programs -------------------------------------------------------
    def refresh(self) -> None:
        self.recent.clear()
        items = [(p, "cad") for p in recent_cad()[:4]] + [(p, "3d") for p in recent_3d()[:4]]
        if not items:
            it = QListWidgetItem(self.t["no_recent"])
            it.setFlags(Qt.NoItemFlags)
            self.recent.addItem(it)
            return
        for p, which in items:
            it = QListWidgetItem(f"{'2D' if which == 'cad' else '3D'}   {p.name}")
            it.setToolTip(str(p))
            it.setData(Qt.UserRole, (which, str(p)))
            self.recent.addItem(it)

    def _open_recent(self, item: QListWidgetItem) -> None:
        data = item.data(Qt.UserRole)
        if data:
            self.launch(data[0], [data[1]])

    def launch(self, which: str, files=(), panel: str = "") -> None:
        os.environ["WANIC_LANG"] = self.lang
        if panel:
            os.environ["WANIC_START_PANEL"] = panel
        else:
            os.environ.pop("WANIC_START_PANEL", None)
        if start(which, files):
            self.close()
        else:
            QMessageBox.warning(self, PRODUCT, self.t["missing"])

    def open_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, self.t["open_title"], "",
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
        QMessageBox.information(self, PRODUCT, self.t["cannot"])

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
    import wanic_login
    if not wanic_login.require():
        return 0
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
