# SPDX-License-Identifier: GPL-3.0-or-later
# WANICNSURVEY 3D — ลายเซ็นกำกับงานพัฒนา
"""The developer's signature carried by every WANIC tool: the forms it
prints, the BOQ it exports and the panels it shows.

The name is typed text. A scanned hand signature can be added later as an
image (``SIGNATURE_IMAGE`` beside the program); nothing here invents one.
"""
from __future__ import annotations

from core import branding

NAME = "นายเวนิช ธัมมะวงษ์"
ROLE = "วิศวกรสำรวจ"
FULL = f"{NAME} {ROLE}"
SIGNATURE_IMAGE = "wanic_signature.png"

# branding.DEVELOPER is the same person; keep the two in step.
assert branding.DEVELOPER == FULL, branding.DEVELOPER


def footer(tool: str = "") -> str:
    """One line for the foot of a form, sheet or panel."""
    what = f"{branding.PRODUCT} {tool}".strip()
    return f"จัดทำด้วย {what} — พัฒนาและรับรองโปรแกรมโดย {FULL}"


def sign_lines() -> list[str]:
    """The signature block (dotted line, name, role) for a printed form."""
    return ["(ลงชื่อ) ......................................  ผู้ถอดแบบและคำนวณปริมาณ",
            f"( {NAME} )", f"ตำแหน่ง {ROLE}"]


def label_html(tool: str = "") -> str:
    """Small grey caption for the bottom of a panel."""
    return (f"<span style='color:#6b7280;font-size:11px'>✍ {footer(tool)}"
            "</span>")
