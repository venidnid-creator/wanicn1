# -*- coding: utf-8 -*-
"""WanicnDesign — โครงโปรแกรมเมนูหลัก (เริ่มต้นจากภาพหน้าจอ Mainmenu V6)

สถานะ: โครงหน้าจอเท่านั้น ยังไม่มีตรรกะการคำนวณ
ปุ่มที่ยังไม่ได้เชื่อมฟังก์ชันจะแสดงข้อความ "ยังไม่ได้พัฒนา"
"""
import tkinter as tk
from tkinter import messagebox

APP_TITLE = "WanicnDesign — Mainmenu V6"

# ตารางปุ่มตามภาพ Mainmenu V6 (ซ้าย, ขวา) ต่อแถว
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


class MainMenu(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.resizable(False, False)
        self.file_name = tk.StringVar(value="")

        top = tk.Frame(self, padx=10, pady=8)
        top.pack(fill="x")
        tk.Button(top, text="Open", width=8, command=self.on_open).pack(side="left")
        tk.Entry(top, textvariable=self.file_name, width=24).pack(side="left", padx=6)

        grid = tk.Frame(self, padx=10, pady=4)
        grid.pack()
        for r, (left, right) in enumerate(MENU_ROWS):
            for c, label in enumerate((left, right)):
                tk.Button(grid, text=label, width=12,
                          command=lambda n=label: self.on_menu(n)
                          ).grid(row=r, column=c, padx=4, pady=3)

    def on_open(self):
        messagebox.showinfo(APP_TITLE, "ยังไม่ได้พัฒนา: เปิดไฟล์แบบ")

    def on_menu(self, name):
        if name == "Close":
            self.destroy()
            return
        messagebox.showinfo(APP_TITLE, f"ยังไม่ได้พัฒนา: {name}")


if __name__ == "__main__":
    MainMenu().mainloop()
