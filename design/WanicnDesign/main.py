# -*- coding: utf-8 -*-
"""WanicnDesign — สร้างโมเดลอาคาร คำนวณโครงสร้างตั้งแต่หลังคาถึงเสาเข็ม และทำ BOQ

    python main.py                 เริ่มจากบ้านตัวอย่าง 2 ชั้น
    python main.py โมเดล.json      เปิดโมเดลที่บันทึกไว้
"""
import sys

from PySide6.QtWidgets import QApplication

from wanicndesign.structure.building import Building
from wanicndesign.ui.main_window import MainWindow


def main(argv=None):
    argv = sys.argv if argv is None else argv
    app = QApplication(argv)
    app.setApplicationName("WanicnDesign")
    if len(argv) > 1:
        win = MainWindow(Building.load(argv[1]), argv[1])
    else:
        win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
