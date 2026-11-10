# SPDX-License-Identifier: GPL-3.0-or-later
"""The five themes: one Qt style sheet filled with each theme's colours."""
from __future__ import annotations

THEMES = {
    "บลูพริ้นท์": dict(bg="#0B1F33", panel="#10283F", bar="#0E2238", text="#E6EEF7", muted="#8FA8C2",
                       accent="#F5B400", accent_text="#1A1A1A", border="#1F3D5C", canvas="#081726",
                       hover="#1A3B5C", input="#0D2338"),
    "สว่าง": dict(bg="#F4F6F9", panel="#FFFFFF", bar="#FFFFFF", text="#1C2733", muted="#5E6B78",
                  accent="#1F6FEB", accent_text="#FFFFFF", border="#D6DCE3", canvas="#E9EDF2",
                  hover="#E4ECF7", input="#FFFFFF"),
    "มืด": dict(bg="#1E1F22", panel="#26272B", bar="#2B2D31", text="#E3E3E3", muted="#9A9DA3",
                accent="#5AA9FF", accent_text="#0E0E0E", border="#3A3C41", canvas="#17181A",
                hover="#34363B", input="#2F3136"),
    "ทองเวนิช": dict(bg="#F3EEE4", panel="#FBF8F2", bar="#0F2A44", text="#1D2633", muted="#6B6252",
                     accent="#C9A227", accent_text="#0F2A44", border="#DDD3BF", canvas="#E8E1D3",
                     hover="#EFE5CF", input="#FFFFFF", bar_text="#F3EEE4"),
    "เขียวสำรวจ": dict(bg="#EEF5EF", panel="#FFFFFF", bar="#14532D", text="#13261A", muted="#4E6B56",
                       accent="#16A34A", accent_text="#FFFFFF", border="#CFE3D3", canvas="#E2EEE4",
                       hover="#DCEFE0", input="#FFFFFF", bar_text="#ECFDF3"),
}
DEFAULT = "บลูพริ้นท์"

_QSS = """
QWidget {{ background: {bg}; color: {text}; font-size: 10pt; }}
QMainWindow, QDialog {{ background: {bg}; }}
#TopBar, #ToolRow {{ background: {bar}; border-bottom: 1px solid {border}; }}
#TopBar QLabel, #ToolRow QToolButton {{ background: transparent; color: {bar_text}; }}
#TopBar QLabel#Title {{ font-size: 15pt; font-weight: bold; }}
#TopBar QLabel#Subtitle {{ color: {muted}; font-size: 9pt; }}
#ToolRow QToolButton {{ border: none; border-radius: 6px; padding: 4px 8px; min-width: 64px; }}
#ToolRow QToolButton:hover {{ background: {hover}; color: {text}; }}
#ToolRow QToolButton:checked {{ background: {accent}; color: {accent_text}; }}
#Side, #RightSide {{ background: {panel}; border: 1px solid {border}; }}
#Side QLabel#Head, #RightSide QLabel#Head {{ font-weight: bold; padding: 6px; }}
QListWidget, QTableWidget, QTreeWidget {{ background: {panel}; border: 1px solid {border};
    alternate-background-color: {hover}; }}
QListWidget::item:selected, QTableWidget::item:selected {{ background: {accent}; color: {accent_text}; }}
QHeaderView::section {{ background: {bar}; color: {bar_text}; border: 0; padding: 4px; }}
QPushButton {{ background: {panel}; border: 1px solid {border}; border-radius: 6px; padding: 5px 12px; }}
QPushButton:hover {{ background: {hover}; }}
QPushButton#Primary {{ background: {accent}; color: {accent_text}; border: none; font-weight: bold; }}
QComboBox, QLineEdit, QDoubleSpinBox, QSpinBox {{ background: {input}; border: 1px solid {border};
    border-radius: 5px; padding: 3px 6px; }}
QTabWidget::pane {{ border: 1px solid {border}; }}
QTabBar::tab {{ background: {panel}; padding: 6px 16px; border: 1px solid {border}; }}
QTabBar::tab:selected {{ background: {accent}; color: {accent_text}; }}
QScrollArea, #Canvas {{ background: {canvas}; border: none; }}
QStatusBar {{ background: {bar}; color: {bar_text}; }}
QToolTip {{ background: {panel}; color: {text}; border: 1px solid {border}; }}
QMenu {{ background: {panel}; border: 1px solid {border}; }}
QMenu::item:selected {{ background: {accent}; color: {accent_text}; }}
"""


def stylesheet(name: str) -> str:
    c = dict(THEMES.get(name, THEMES[DEFAULT]))
    c.setdefault("bar_text", c["text"])
    return _QSS.format(**c)


def colors(name: str) -> dict:
    c = dict(THEMES.get(name, THEMES[DEFAULT]))
    c.setdefault("bar_text", c["text"])
    return c
