# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — WANICNSURVEY
"""แก้ชิ้นส่วนที่ไม่ผ่าน — the window opened from a failing row of the
calculation table: what fails and why, the advice, and the member's fields
filled with the values that pass (the changed ones marked) for the designer
to accept or edit; «บันทึก» writes the mark, rebuilds the model and
recalculates."""
from __future__ import annotations

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import (QDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout)

from core import wanic_building as B

KIND_TH = {"beam": "คาน", "column": "เสา", "slab": "พื้น", "footing": "ฐานราก", "roof": "โครงหลังคา",
           "stump": "ตอม่อ"}
NUMERIC = {"b", "h", "t", "w", "l", "depth", "sand", "lean", "piles", "pile_b", "pile_len", "ground"}


def _show(v) -> str:
    if isinstance(v, float):
        return f"{v:g}"
    return "" if v is None else str(v)


class FixDialog(QDialog):
    def __init__(self, parent, member, fix: dict, data: dict):
        super().__init__(parent)
        self.setWindowTitle("แก้ชิ้นส่วนที่ไม่ผ่าน")
        self.setMinimumWidth(640)
        self.fix = fix
        lay = QVBoxLayout(self)
        head = QLabel(f"<b style='font-size:15px'>{member.name}</b><br>"
                      f"<span style='color:#B91C1C'>✗ ไม่ผ่าน (อัตราส่วน {member.ratio:.2f})</span><br>"
                      f"แรงที่เกิด: {member.demand}<br>กำลังที่รับได้: {member.capacity}")
        head.setWordWrap(True)
        lay.addWidget(head)
        tips = QLabel("<b>คำแนะนำ — เพิ่มอะไร จุดไหน:</b><br>" + "<br>".join(f"→ {t}" for t in fix["advice"])
                      if fix["advice"] else "<b>คำแนะนำ:</b> ปรับค่าด้านล่างแล้วคำนวณใหม่")
        tips.setWordWrap(True)
        tips.setStyleSheet("background:#FFF7D6;padding:8px;border-radius:6px")
        lay.addWidget(tips)
        form = QFormLayout()
        self.edits = {}
        if fix["target"] == "lib":
            lib = B.library_of(data)
            spec = lib.get(fix["key"], {})
            E = B.elements(data)
            used = sum(1 for key in ("footings", "stumps", "columns", "beams", "slabs") for e in E[key]
                       if e.get("mark") == fix["key"])
            note = QLabel(f"แก้ที่เบอร์ <b>{fix['key']}</b> ({KIND_TH.get(spec.get('kind'), '')}) — มีผลกับทุกชิ้นที่ใช้เบอร์นี้ "
                          f"({used} ชิ้น) · ค่าที่แนะนำคิดจากชิ้นที่วิกฤตที่สุดของเบอร์นี้ จึงผ่านทุกชิ้น")
            note.setWordWrap(True)
            lay.addWidget(note)
            for k, th in B.LIB_FIELDS.get(spec.get("kind"), []):
                cur = spec.get(k)
                new = fix["changes"].get(k, cur)
                ed = QLineEdit(_show(new))
                if k in fix["changes"]:
                    pal = ed.palette()
                    pal.setColor(QPalette.Base, QColor("#FEF3C7"))
                    ed.setPalette(pal)
                    th = f"{th}  (เดิม {_show(cur)})"
                self.edits[k] = ed
                form.addRow(th, ed)
        else:
            s = B.settings_of(data)
            key = fix["key"]
            cur = s.get(key, "")
            ed = QLineEdit(_show(fix["changes"].get(key, cur)))
            if key in fix["changes"]:
                pal = ed.palette()
                pal.setColor(QPalette.Base, QColor("#FEF3C7"))
                ed.setPalette(pal)
            self.edits[key] = ed
            form.addRow(f"หน้าตัด ({key})  (เดิม {cur})", ed)
        lay.addLayout(form)
        info = QLabel("ช่องสีเหลือง = ค่าที่แนะนำให้ผ่าน (แก้เองได้) · เมื่อบันทึก โปรแกรมจัดให้สมมาตรและสมดุล "
                      "(เสาจัตุรัส เหล็กยืนหาร 4 ลงตัว · คานเหล็กบน-ล่างขนาดเดียวกัน · ฐานรากจัตุรัส) "
                      "แล้วอัปเดตโมเดลและคำนวณใหม่")
        info.setWordWrap(True)
        lay.addWidget(info)
        b = QHBoxLayout()
        b.addStretch(1)
        ok = QPushButton("บันทึก อัปเดตโมเดล และคำนวณใหม่")
        ok.setStyleSheet("font-weight:700")
        ok.clicked.connect(self.accept)
        cancel = QPushButton("ยกเลิก")
        cancel.clicked.connect(self.reject)
        b.addWidget(ok)
        b.addWidget(cancel)
        lay.addLayout(b)

    def values(self) -> dict:
        out = {}
        for k, ed in self.edits.items():
            t = ed.text().strip()
            if k in NUMERIC:
                try:
                    v = float(t)
                    out[k] = int(v) if k in ("piles", "ground") else v
                except ValueError:
                    continue
            else:
                out[k] = t
        return out


def apply(data: dict, fix: dict, values: dict) -> dict:
    """Write the values into the library mark or the roof setting."""
    if fix["target"] == "lib":
        from core import wanic_advice as AD
        full = B.library_of(data).get(fix["key"], {})
        ch = AD.balanced_changes(full, {k: v for k, v in values.items() if full.get(k) != v})
        lib = dict(data.get("library") or {})
        spec = dict(lib.get(fix["key"]) or {})
        spec.update(ch)
        lib[fix["key"]] = spec
        data["library"] = lib
    else:
        s = dict(data.get("settings") or {})
        s.update(values)
        data["settings"] = s
    return data
