# -*- coding: utf-8 -*-
"""WanicnDesign — สร้างโมเดลอาคาร คำนวณโครงสร้างตั้งแต่หลังคาถึงเสาเข็ม และทำราคากลาง

    python main.py                 เริ่มจากบ้านตัวอย่าง 2 ชั้น
    python main.py โมเดล.json      เปิดโมเดลที่บันทึกไว้
    python main.py --check         ตรวจว่าโปรแกรมและข้อมูลครบ (ใช้ทดสอบชุดติดตั้ง) แล้วออก
"""
import os
import sys


def check() -> int:
    """Self-test of an installed copy: every data table loads, the example designs, prices and plans."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    import tempfile

    from wanicndesign import materials, province
    from wanicndesign.estimate import OFFICIAL_FF, for_design
    from wanicndesign.rates import Rates
    from wanicndesign.schedule import plan
    from wanicndesign.standards import provinces
    from wanicndesign.structure.design import design
    from wanicndesign.structure.mep import MEP_DATA
    tmp = tempfile.mkdtemp(prefix="wanicndesign-check-")
    os.environ["WANIC_PRICE_DIR"] = tmp                  # never touch the user's price books
    os.environ["WANIC_DESIGN_DIR"] = tmp
    r = Rates()
    assert len(r.labour) > 200 and len(materials.RECIPES) > 200, "labour or material tables missing"
    assert len(OFFICIAL_FF["tables"]) == 12 and MEP_DATA["labour"], "Factor F or ว480 MEP tables missing"
    assert len(provinces()["provinces"]) == 77 and len(province.PROVINCES) == 77, "province data missing"
    from wanicndesign.ui.main_window import default_building
    res = design(default_building())
    est = for_design(res)
    p = plan(est)
    out = os.path.join(tmp, "check.xlsx")
    est.to_xlsx(out)
    assert os.path.getsize(out) > 10000 and p.days > 0
    print(f"WanicnDesign OK: {len(res.beams)} beams, {len(res.footings)} footings, "
          f"cost {est.total:,.2f}, Factor F {est.factor:.4f}, {p.days} days")
    return 0


def main(argv=None):
    argv = sys.argv if argv is None else argv
    if "--check" in argv:
        return check()
    from PySide6.QtWidgets import QApplication

    from wanicndesign.ui.main_window import MainWindow
    app = QApplication(argv)
    app.setApplicationName("WanicnDesign")
    app.setOrganizationName("WANICNSURVEY")
    files = [a for a in argv[1:] if not a.startswith("-")]
    if files:
        win = MainWindow(Building.load(files[0]), files[0])
    else:
        win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
