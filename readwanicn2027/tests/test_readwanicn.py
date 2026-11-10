# SPDX-License-Identifier: GPL-3.0-or-later
"""ReadWanicn2027: sign-in, PDF tools, exports, take-off and the windows."""
from __future__ import annotations

import os
import zipfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("READWANICN_OFFLINE", "1")

import pymupdf
import pytest

from readwanicn import auth, measure, pdfops, update
from tests.sample import make, plan_pt


@pytest.fixture
def sample(tmp_path):
    return make(str(tmp_path / "plan.pdf"))


def test_the_first_account_signs_in_and_nothing_else_does(tmp_path):
    users = tmp_path / "users.json"
    assert auth.check("Wanicn", "Thommawogn", users)
    assert not auth.check("Wanicn", "thommawogn", users)
    assert not auth.check("wanicn2", "Thommawogn", users)
    auth.set_password("Wanicn", "ใหม่1234", users)
    assert auth.check("Wanicn", "ใหม่1234", users) and not auth.check("Wanicn", "Thommawogn", users)
    assert "Thommawogn" not in users.read_text()


def test_combine_and_compress_at_three_levels(sample, tmp_path):
    out = tmp_path / "all.pdf"
    assert pdfops.combine([sample, sample], str(out)) == 6
    sizes = {}
    for level in ("high", "medium", "low"):
        r = pdfops.compress(sample, str(tmp_path / f"{level}.pdf"), level)
        assert r.after <= r.before
        sizes[level] = r.after
        assert pymupdf.open(tmp_path / f"{level}.pdf").page_count == 3
    assert sizes["low"] <= sizes["medium"] <= sizes["high"]
    with pytest.raises(ValueError):
        pdfops.compress(sample, str(tmp_path / "x.pdf"), "best")


def test_page_edits_and_exports(sample, tmp_path):
    doc = pymupdf.open(sample)
    pdfops.rotate_page(doc, 0)
    assert doc[0].rotation == 90
    pdfops.delete_pages(doc, [2])
    assert doc.page_count == 2
    assert pdfops.export_excel(doc, tmp_path / "a.xlsx", "plan") > 0
    assert zipfile.is_zipfile(tmp_path / "a.xlsx")
    pdfops.export_csv(doc, tmp_path / "a.csv")
    text = (tmp_path / "a.csv").read_text(encoding="utf-8-sig")
    assert "Brick wall" in text
    pdfops.export_word(doc, tmp_path / "a.docx", "plan")
    assert zipfile.is_zipfile(tmp_path / "a.docx")


def test_lengths_areas_counts_at_1_100_and_calibrated(tmp_path):
    s = measure.Scale.ratio(100)
    length = measure.Measurement("length", 0, [(0, 0), (plan_pt(4), 0), (plan_pt(4), plan_pt(3))], s)
    assert length.value == pytest.approx(7.0)
    area = measure.Measurement("area", 0, [(0, 0), (plan_pt(5), 0), (plan_pt(5), plan_pt(4)), (0, plan_pt(4))], s)
    assert area.value == pytest.approx(20.0) and area.perimeter == pytest.approx(18.0)
    count = measure.Measurement("count", 0, [(1, 1), (2, 2), (3, 3)], s)
    assert count.value == 3
    cal = measure.Scale.calibrated(plan_pt(8), 8.0)
    assert cal.m_per_pt == pytest.approx(s.m_per_pt)
    measure.report_excel([length, area, count], tmp_path / "r.xlsx")
    from openpyxl import load_workbook
    wb = load_workbook(tmp_path / "r.xlsx")
    assert wb.sheetnames == ["รายการวัด", "สรุป"]
    measure.report_csv([length, area, count], tmp_path / "r.csv")
    assert "พื้นที่" in (tmp_path / "r.csv").read_text(encoding="utf-8-sig")


def test_new_version_and_download_count():
    releases = [
        {"tag_name": "readwanicn-v2027.1.0", "html_url": "u1", "assets": [{"download_count": 12}]},
        {"tag_name": "readwanicn-v2027.2.0", "html_url": "u2", "assets": [{"download_count": 5},
                                                                          {"download_count": 1}]},
        {"tag_name": "v2026.10.31", "assets": [{"download_count": 999}]},     # the CAD's own
    ]
    info = update.parse(releases, "2027.1.0")
    assert info.downloads == 18 and info.latest == "2027.2.0" and info.newer and info.url == "u2"
    assert not update.parse(releases, "2027.2.0").newer


def test_the_window_opens_measures_and_switches_themes(sample, tmp_path):
    from PySide6.QtWidgets import QApplication

    from readwanicn import themes
    from readwanicn.ui import LoginDialog, MainWindow
    QApplication.instance() or QApplication([])
    login = LoginDialog(users_path=tmp_path / "u.json")
    login.name.setText("Wanicn")
    login.password.setText("Thommawogn")
    login.try_login()
    assert login.user == "Wanicn"
    w = MainWindow("Wanicn")
    w.open_files([sample])
    assert w.current is not None and w.page_list.count() == 3
    w.add_measurement("area", [(0, 0), (plan_pt(4), 0), (plan_pt(4), plan_pt(4)), (0, plan_pt(4))])
    assert w.table.rowCount() == 1 and "16.000" in w.table.item(0, 3).text()
    for name in themes.THEMES:
        w.apply_theme(name)
    assert len(themes.THEMES) == 5
    w.zoom_by(2.0)
    assert w.zoom_label.text() == "200%"
    w.model.rotate(30)
    w.grab()
