# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2569 (2026) นายเวนิช ธัมมะวงษ์ วิศวกรสำรวจ — ReadWanicn2027
"""พิมพ์: a print preview, then the printer. PDF pages are drawn at the
printer's resolution (capped at 300 dpi) and fitted to the paper; the
document editor and the spreadsheet print their QTextDocument."""
from __future__ import annotations

import pymupdf
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QImage, QPageLayout, QPainter
from PySide6.QtPrintSupport import QPrintDialog, QPrinter, QPrintPreviewDialog


def _preview(parent, title, paint, orientation=None) -> bool:
    printer = QPrinter(QPrinter.HighResolution)
    printer.setDocName(title)
    if orientation is not None:
        printer.setPageOrientation(orientation)
    dlg = QPrintPreviewDialog(printer, parent)
    dlg.setWindowTitle(f"ตัวอย่างก่อนพิมพ์ — {title}")
    dlg.resize(1000, 760)
    dlg.paintRequested.connect(paint)
    return bool(dlg.exec())


def _pages(doc, printer, current):
    """The pages the print dialog asked for (all, a range, or the current one)."""
    n = doc.page_count
    if printer.printRange() == QPrinter.PageRange and printer.fromPage() > 0:
        return list(range(printer.fromPage() - 1, min(printer.toPage(), n)))
    if printer.printRange() == QPrinter.CurrentPage:
        return [current]
    return list(range(n))


def paint_pdf(printer, doc, current=0):
    painter = QPainter()
    if not painter.begin(printer):
        return
    try:
        dpi = min(300, printer.resolution())
        first = True
        for i in _pages(doc, printer, current):
            page = doc[i]
            if not first:
                printer.newPage()
            first = False
            z = dpi / 72.0
            pix = page.get_pixmap(matrix=pymupdf.Matrix(z, z), alpha=False)
            img = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format_RGB888)
            area = QRectF(painter.viewport())
            s = min(area.width() / img.width(), area.height() / img.height())
            w, h = img.width() * s, img.height() * s
            target = QRectF(area.x() + (area.width() - w) / 2, area.y() + (area.height() - h) / 2, w, h)
            painter.setRenderHint(QPainter.SmoothPixmapTransform)
            painter.drawImage(target, img)
    finally:
        painter.end()


def print_pdf(parent, doc, current=0, title="เอกสาร"):
    r = doc[current].rect
    orient = QPageLayout.Landscape if r.width > r.height else QPageLayout.Portrait
    printer = QPrinter(QPrinter.HighResolution)
    printer.setDocName(title)
    printer.setPageOrientation(orient)
    printer.setFromTo(1, doc.page_count)
    dlg = QPrintDialog(printer, parent)
    dlg.setWindowTitle("พิมพ์")
    dlg.setOption(QPrintDialog.PrintCurrentPage, True)
    dlg.setOption(QPrintDialog.PrintPageRange, True)
    if dlg.exec() != QPrintDialog.Accepted:
        return False
    paint_pdf(printer, doc, current)
    return True


def print_text_document(parent, qdoc, title, margins_mm=(30, 25, 20, 20), landscape=False):
    """A QTextDocument (or a function making a fresh copy of one) on A4 with the given margins (left, top, right, bottom), after a preview."""
    from PySide6.QtCore import QMarginsF, QSizeF
    from PySide6.QtGui import QPageSize

    def paint(printer):
        printer.setPageSize(QPageSize(QPageSize.A4))
        printer.setPageOrientation(QPageLayout.Landscape if landscape else QPageLayout.Portrait)
        l, t, r, b = margins_mm
        printer.setPageMargins(QMarginsF(l, t, r, b), QPageLayout.Millimeter)
        copy = qdoc() if callable(qdoc) else qdoc.clone()
        fmt = copy.rootFrame().frameFormat()
        fmt.setMargin(0)
        copy.rootFrame().setFrameFormat(fmt)
        copy.documentLayout().setPaintDevice(printer)
        copy.setPageSize(QSizeF(printer.pageLayout().paintRectPixels(printer.resolution()).size()))
        copy.print_(printer)
    return _preview(parent, title, paint)
