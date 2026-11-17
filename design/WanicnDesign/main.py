# -*- coding: utf-8 -*-
"""WanicnDesign — main menu window.

Working buttons in this version:
  Open      เปิดไฟล์โครงการ (.json)
  แบบร่าง   วาดกริดและร่างเสา → ไฟล์ DXF หรือ AutoCAD ที่เปิดอยู่
  ปริมาณ    ถอดปริมาณ ประมาณราคา (ปร.4) ปรับค่าแรง ว480 และส่งออก Excel
  Close     ปิดโปรแกรม
Other buttons show what they will do; they arrive in later phases.
"""
import os
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

from wanicndesign.model import Project
from wanicndesign.rates import DATA_DIR, Rates

APP_TITLE = "WanicnDesign"
OVERRIDE = os.path.join(DATA_DIR, "labour_override.json")

MENU_ROWS = [
    ("ค่าเริ่มต้น", "แบบร่าง"),
    ("สถาปัตย์", "โครงสร้าง"),
    ("ระบบ", "ปริมาณ"),
    ("รูปด้าน", "รูปตัด"),
    ("Help", "Sketchup"),
    ("ข้อกำหนด", "พื้น"),
    ("หลังคา", "คาน"),
    ("เสา", "ฐานราก"),
    ("สารบัญ", "ดู"),
    ("SKU", "Close"),
]

PLANNED = {
    "ค่าเริ่มต้น": "ตั้งชื่อโครงการ หัวแบบ จำนวนชั้นและระดับชั้น",
    "สถาปัตย์": "แปลนสถาปัตย์ ประตูหน้าต่าง สุขภัณฑ์",
    "โครงสร้าง": "แปลนโครงสร้างและรายละเอียด",
    "ระบบ": "ไฟฟ้าและสุขาภิบาล",
    "รูปด้าน": "รูปด้าน 4 ด้าน", "รูปตัด": "รูปตัด A-A, B-B",
    "Sketchup": "ส่งข้อมูลไป SketchUp", "ข้อกำหนด": "ข้อกำหนดวัสดุ fc', fy, WSD/USD",
    "พื้น": "ออกแบบพื้น", "หลังคา": "ออกแบบหลังคาและโครงถัก", "คาน": "ออกแบบคาน",
    "เสา": "ออกแบบเสา", "ฐานราก": "ออกแบบฐานรากและเสาเข็ม", "สารบัญ": "สารบัญแบบ",
    "ดู": "เปิด-ปิดการแสดงชิ้นส่วน", "SKU": "SketchUp", "Help": "คู่มือการใช้งาน",
}


class MainMenu(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.resizable(False, False)
        self.project_path = None
        self.project = None
        self.file_name = tk.StringVar(value="(ยังไม่ได้เปิดโครงการ)")

        top = tk.Frame(self, padx=10, pady=8)
        top.pack(fill="x")
        tk.Button(top, text="Open", width=8, command=self.on_open).pack(side="left")
        tk.Entry(top, textvariable=self.file_name, width=26, state="readonly").pack(side="left", padx=6)

        grid = tk.Frame(self, padx=10, pady=4)
        grid.pack()
        for r, pair in enumerate(MENU_ROWS):
            for c, label in enumerate(pair):
                tk.Button(grid, text=label, width=12,
                          command=lambda n=label: self.on_menu(n)).grid(row=r, column=c, padx=4, pady=3)

    # -- helpers --------------------------------------------------------------
    def need_project(self) -> bool:
        if self.project is None:
            messagebox.showinfo(APP_TITLE, "เปิดไฟล์โครงการก่อน (ปุ่ม Open)")
            return False
        return True

    def on_open(self):
        path = filedialog.askopenfilename(title="เปิดโครงการ",
                                          filetypes=[("WanicnDesign project", "*.json")])
        if not path:
            return
        try:
            self.project = Project.load(path)
        except Exception as e:  # show the reason to the user
            messagebox.showerror(APP_TITLE, f"เปิดไฟล์ไม่ได้\n{e}")
            return
        self.project_path = path
        self.file_name.set(self.project.name)

    def on_menu(self, name):
        if name == "Close":
            self.destroy()
        elif name == "แบบร่าง":
            self.draw_plan()
        elif name == "ปริมาณ":
            if self.need_project():
                EstimateWindow(self)
        else:
            messagebox.showinfo(APP_TITLE, f"{name}: {PLANNED.get(name, '')}\n(อยู่ในแผนช่วงถัดไป)")

    def draw_plan(self):
        if not self.need_project():
            return
        from wanicndesign.cad.base import draw_grid
        use_acad = messagebox.askyesno(APP_TITLE, "วาดลงใน AutoCAD ที่เปิดอยู่?\n(ไม่ = บันทึกเป็นไฟล์ DXF)")
        try:
            if use_acad:
                from wanicndesign.cad.acad_backend import AcadBackend
                b = AcadBackend()
            else:
                out = filedialog.asksaveasfilename(defaultextension=".dxf",
                                                   filetypes=[("DXF", "*.dxf")])
                if not out:
                    return
                from wanicndesign.cad.dxf_backend import DxfBackend
                b = DxfBackend(out)
            draw_grid(self.project, b)
            b.finish()
        except Exception as e:
            messagebox.showerror(APP_TITLE, str(e))
            return
        messagebox.showinfo(APP_TITLE, "วาดกริดและร่างเสาเรียบร้อย")


class EstimateWindow(tk.Toplevel):
    """ปริมาณ: price list, labour update and the ปร.4 export."""

    def __init__(self, menu: MainMenu):
        super().__init__(menu)
        self.menu = menu
        self.title("ปริมาณและประมาณราคา")
        self.prices_path = None
        self.rates = Rates(override_file=OVERRIDE)

        bar = tk.Frame(self, padx=8, pady=6)
        bar.pack(fill="x")
        tk.Button(bar, text="ไฟล์ราคาวัสดุ...", command=self.pick_prices).pack(side="left")
        tk.Button(bar, text="ปรับค่าแรงทั้งหมด %", command=self.scale_labour).pack(side="left", padx=4)
        tk.Button(bar, text="แก้ค่าแรงรายการ", command=self.edit_labour).pack(side="left")
        tk.Button(bar, text="ส่งออก Excel (ปร.4)", command=self.export).pack(side="right")

        cols = ("item", "qty", "unit", "mat", "lab", "total", "code")
        heads = ("รายการ", "จำนวน", "หน่วย", "ค่าวัสดุ", "ค่าแรง", "รวม", "รหัส ว480")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=22)
        for c, h, w in zip(cols, heads, (330, 80, 60, 100, 100, 110, 80)):
            self.tree.heading(c, text=h)
            self.tree.column(c, width=w, anchor="w" if c == "item" else "e")
        self.tree.pack(fill="both", expand=True, padx=8)
        self.summary = tk.StringVar()
        tk.Label(self, textvariable=self.summary, anchor="w", padx=8, pady=6).pack(fill="x")
        self.refresh()

    def refresh(self):
        from wanicndesign.estimate import estimate
        self.est = estimate(self.menu.project, self.rates)
        self.tree.delete(*self.tree.get_children())
        for name, rows in self.est.sections():
            self.tree.insert("", "end", values=(f"■ {name}", "", "", "", "", "", ""))
            for r in rows:
                self.tree.insert("", "end", values=(
                    r.line.item, f"{r.line.qty:,.2f}", r.line.unit, f"{r.material_amount:,.2f}",
                    f"{r.labour_amount:,.2f}", f"{r.total:,.2f}", r.line.labour_code))
        self.summary.set(f"ค่าวัสดุ {self.est.material_total:,.2f}   ค่าแรง {self.est.labour_total:,.2f}"
                         f"   รวม {self.est.total:,.2f} บาท")

    def pick_prices(self):
        path = filedialog.askopenfilename(filetypes=[("ราคาวัสดุ", "*.json")])
        if path:
            self.rates.prices = Rates.load_prices(path)
            self.refresh()

    def scale_labour(self):
        pct = simpledialog.askfloat("ปรับค่าแรง", "ปรับค่าแรงทุกรายการกี่เปอร์เซ็นต์ (เช่น 5 หรือ -3)",
                                    parent=self)
        if pct is not None:
            self.rates.scale_labour(pct)
            self.refresh()

    def edit_labour(self):
        code = simpledialog.askstring("แก้ค่าแรง", "รหัสค่าแรง ว480 (เช่น 2.3.1a)", parent=self)
        if not code or code not in self.rates.labour:
            if code:
                messagebox.showerror(APP_TITLE, f"ไม่มีรหัส {code}", parent=self)
            return
        item = self.rates.labour[code]
        rate = simpledialog.askfloat("แก้ค่าแรง", f"{item['name']} ({item['unit']})\nค่าแรงใหม่ (บาท)",
                                     initialvalue=item["rate"], parent=self)
        if rate is not None:
            self.rates.set_labour(code, rate)
            self.refresh()

    def export(self):
        out = filedialog.asksaveasfilename(defaultextension=".xlsx", filetypes=[("Excel", "*.xlsx")],
                                           parent=self)
        if out:
            self.est.to_xlsx(out)
            messagebox.showinfo(APP_TITLE, f"บันทึก {out}", parent=self)


if __name__ == "__main__":
    MainMenu().mainloop()
