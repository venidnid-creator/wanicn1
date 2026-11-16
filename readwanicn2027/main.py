# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2569 (2026) นายเวนิช ธัมมะวงษ์ วิศวกรสำรวจ — ReadWanicn2027
"""ReadWanicn2027: welcome, sign in, then the main window."""
from __future__ import annotations

import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QDialog

from readwanicn import APP_NAME, themes
from readwanicn.ui import LoginDialog, MainWindow, WelcomeScreen, asset, check_license


def selftest(out: str) -> int:
    """For the build: the parts loaded only on demand are in the bundle and work."""
    import os
    import tempfile
    app = QApplication(sys.argv[:1])
    from readwanicn import cadimport, docedit, pdfedit, printing, saraban, sheet, snap, usage  # noqa: F401
    import ezdxf
    import pymupdf
    tmp = tempfile.mkdtemp()
    d = ezdxf.new(units=6)
    d.modelspace().add_line((0, 0), (8, 0))
    d.modelspace().add_text("ทดสอบ", height=0.3)
    d.saveas(os.path.join(tmp, "t.dxf"))
    r = cadimport.import_file(os.path.join(tmp, "t.dxf"))
    page = pymupdf.open(r.pdf)[0]
    assert snap.Snapper(page).segs, "no lines to snap to"
    ed = docedit.DocEditor(asset)
    ed.choose_form("external")
    ed.fill_form()
    docedit.to_docx(ed.page.document(), os.path.join(tmp, "a.docx"))
    docedit.to_pdf(ed.page.document(), os.path.join(tmp, "a.pdf"))
    from PySide6.QtPrintSupport import QPrinter
    pr = QPrinter()
    pr.setOutputFormat(QPrinter.PdfFormat)
    pr.setOutputFileName(os.path.join(tmp, "p.pdf"))
    printing.paint_pdf(pr, pymupdf.open(r.pdf))
    # ปรับลดราคา ว651 · ว124 · ว78: read a bill (.xls needs xlrd) and write the three reports
    import xlrd  # noqa: F401
    from readwanicn import procure, procure_report, procure_view  # noqa: F401
    bill = procure.Project(items=[procure.Item("1 งานทดสอบ", header=True, code="1"),
                                  procure.Item("1.1 คอนกรีต", "ลบ.ม.", 10, cost=30000, code="1.1", level=2),
                                  procure.Item("1.2 เหล็ก DB 12 มม.", "กก.", 500, cost=12000, code="1.2", level=2)],
                           mid_price=55000, offer=50000, months=2, days=60)
    procure.auto_plan(bill, 2)
    for kind in ("651", "124", "78"):
        procure_report.write(kind, bill, os.path.join(tmp, f"r{kind}.pdf"), "Laksaman")
    # ถอดแบบตาม BOQ: the reader, its window, and the Thai OCR shipped beside the program
    from readwanicn import boqread, boqread_view  # noqa: F401
    res = boqread.analyse(r.pdf, ocr=False)
    boqread.write_csv(res, os.path.join(tmp, "boq"))
    ocr = boqread.tesseract_path()
    if getattr(sys, "frozen", False):
        assert ocr, "the Thai OCR (tesseract) is not beside the program"
        png = pymupdf.open(r.pdf)[0].get_pixmap().tobytes("png")
        boqread._ocr(png)
    open(out, "w", encoding="utf-8").write(f"ok 1:{r.ratio} ocr:{ocr or '-'}")
    del app
    return 0


def main() -> int:
    if len(sys.argv) == 3 and sys.argv[1] == "--selftest":
        return selftest(sys.argv[2])
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setWindowIcon(QIcon(asset("logo.ico")))
    app.setStyleSheet(themes.stylesheet(themes.DEFAULT))
    from readwanicn import fit
    fit.install(app)                         # every window fits the screen it opens on
    WelcomeScreen().show_for(2200)
    login = LoginDialog()
    if login.exec() != QDialog.Accepted:
        return 0
    if not check_license():                 # a year of use is up and not renewed
        return 0
    window = MainWindow(login.user)
    window.show()
    files = [a for a in sys.argv[1:] if a.lower().endswith((".pdf", ".json"))]
    if files:
        window.open_files(files)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
