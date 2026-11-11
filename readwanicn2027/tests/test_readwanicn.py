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
    assert auth.check("Wanicn", "Thammawong", users)
    assert not auth.check("Wanicn", "Thommawogn", users)               # the old password
    assert not auth.check("wanicn2", "Thammawong", users)
    token = auth.remember_token("Wanicn", users)
    assert auth.check_token("Wanicn", token, users) and not auth.check_token("Wanicn", "x", users)
    auth.set_password("Wanicn", "ใหม่1234", users)
    assert auth.check("Wanicn", "ใหม่1234", users) and not auth.check("Wanicn", "Thammawong", users)
    assert not auth.check_token("Wanicn", token, users)                  # a new password forgets
    assert "ใหม่1234" not in users.read_text()


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
    exe = lambda n, v: {"name": f"readwanicn2027-setup-{v}.exe", "download_count": n}
    releases = [
        {"tag_name": "readwanicn-v2027.1.0", "html_url": "u1", "assets": [
            exe(12, "2027.1.0"), {"name": update.INSTALL_FILE, "download_count": 7},
            {"name": update.OPEN_FILE, "download_count": 40}]},
        {"tag_name": "readwanicn-v2027.2.0", "html_url": "u2", "published_at": "2027-03-05T02:00:00Z",
         "assets": [exe(5, "2027.2.0"), exe(1, "2027.2.0"), {"name": update.OPEN_FILE, "download_count": 3}]},
        {"tag_name": "v2026.10.31", "assets": [{"name": "x.exe", "download_count": 999}]},   # the CAD's own
    ]
    info = update.parse(releases, "2027.1.0")
    assert info.downloads == 18 and info.latest == "2027.2.0" and info.newer and info.url == "u2"
    assert info.latest_downloads == 6 and info.users == 7 and info.opens == 43
    assert info.published_th == "5 มี.ค. 2570"
    assert not update.parse(releases, "2027.2.0").newer


def test_the_window_opens_measures_and_switches_themes(sample, tmp_path):
    from PySide6.QtWidgets import QApplication

    from readwanicn import themes
    from readwanicn.ui import LoginDialog, MainWindow
    QApplication.instance() or QApplication([])
    login = LoginDialog(users_path=tmp_path / "u.json")
    login.name.setText("Wanicn")
    login.password.setText("Thammawong")
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


def test_a_year_of_use_then_a_renewal_code(tmp_path):
    import datetime as dt

    from readwanicn import license
    path = tmp_path / "license.json"
    start = dt.date(2027, 1, 10)
    lic = license.License(path, start)
    assert not lic.expired and lic.days_left == 365
    later = license.License(path, start + dt.timedelta(days=366))
    assert later.expired and later.install_id == lic.install_id
    assert not later.renew("0000-0000-0000")
    code = license.renewal_code(later.install_id, 1)
    assert later.renew(code.lower().replace("-", " "))
    assert not later.expired and later.until == start + dt.timedelta(days=366 + 365)
    again = license.License(path, start + dt.timedelta(days=400))
    assert not again.renew(code)                            # a code opens one year only
    assert again.renew(license.renewal_code(again.install_id, 2))
    other = license.License(tmp_path / "other.json", start)
    assert license.renewal_code(other.install_id, 1) != code or other.install_id == lic.install_id


def test_the_expired_dialog_takes_the_code(tmp_path):
    import datetime as dt

    from PySide6.QtWidgets import QApplication, QMessageBox

    from readwanicn import license
    from readwanicn.ui import ExpiredDialog, support_panel
    QApplication.instance() or QApplication([])
    lic = license.License(tmp_path / "l.json", dt.date(2027, 1, 1))
    lic.today = dt.date(2028, 2, 1)
    d = ExpiredDialog(lic)
    d.code.setText("bad")
    d.try_code()
    assert "ไม่ถูกต้อง" in d.error.text()
    QMessageBox.information = staticmethod(lambda *a, **k: None)
    d.code.setText(license.renewal_code(lic.install_id, 1))
    d.try_code()
    assert not lic.expired
    support_panel().grab()


def test_remember_password_signs_in_without_typing(tmp_path):
    from PySide6.QtCore import QSettings
    from PySide6.QtWidgets import QApplication

    from readwanicn.ui import LoginDialog
    QApplication.instance() or QApplication([])
    settings = QSettings(str(tmp_path / "s.ini"), QSettings.IniFormat)
    users = tmp_path / "u.json"
    first = LoginDialog(users_path=users, settings=settings, fetch=False)
    first.name.setText("Wanicn")
    first.password.setText("Thammawong")
    first.remember.setChecked(True)
    first.try_login()
    assert first.user == "Wanicn"
    settings.sync()
    assert "Thammawong" not in open(tmp_path / "s.ini", encoding="utf-8").read()
    again = LoginDialog(users_path=users, settings=settings, fetch=False)
    assert again.name.text() == "Wanicn" and again.remember.isChecked()
    again.try_login()
    assert again.user == "Wanicn"
    # unticked: the next time asks for the password
    again.remember.setChecked(False)
    again.try_login()
    third = LoginDialog(users_path=users, settings=settings, fetch=False)
    assert third.password.text() == "" and not third.remember.isChecked()
