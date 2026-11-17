# WanicnDesign

โปรแกรมออกแบบอาคาร ถอดปริมาณ และประมาณราคา เขียนด้วย Python
ลำดับการทำงานอ้างอิงจากคู่มือและวิดีโอของโปรแกรมเดิม (สรุปไว้ใน `docs/workflow.md`)
แต่โค้ดและสูตรคำนวณเขียนใหม่ทั้งหมด ไม่ได้คัดลอกจากโปรแกรมเดิม

## ช่วงที่ 1 (เวอร์ชันนี้): ปริมาณงานและค่าแรง
- ถอดปริมาณ: งานดิน คอนกรีต ไม้แบบ เหล็กเสริม ก่อ ฉาบ ทาสี ประตูหน้าต่าง หลังคา
- การเผื่อตามเกณฑ์กรมบัญชีกลาง พ.ศ. 2569 (เหล็กตามขนาด ขุดดิน ทรายรอง กระเบื้องหลังคา)
- ค่าแรงตามบัญชี **ว480 (26 มิ.ย. 2569)** 78 รายการ ใน `data/labour_2569.json`
- ใบประมาณราคาแบบ ปร.4 ส่งออก Excel พร้อมสูตร (แก้ราคาใน Excel แล้วยอดรวมเปลี่ยนตาม)
- วาดกริดและร่างเสา: บันทึกเป็น DXF หรือวาดลงใน AutoCAD ที่เปิดอยู่ (ผ่าน COM)

## ติดตั้ง
```
pip install -r requirements.txt
```

## ใช้งานผ่านหน้าต่างเมนู (Windows)
```
python main.py
```
กด **Open** เลือกไฟล์โครงการ เช่น `examples/house_8x12.json` แล้วกด **ปริมาณ** หรือ **แบบร่าง**

## ใช้งานผ่านคำสั่ง
```
python -m wanicndesign estimate examples/house_8x12.json -o BOQ.xlsx
python -m wanicndesign prices examples/house_8x12.json -o prices.json
python -m wanicndesign estimate examples/house_8x12.json --prices prices.json -o BOQ.xlsx
python -m wanicndesign estimate examples/house_8x12.json --labour-up 5 -o BOQ.xlsx
python -m wanicndesign labour
python -m wanicndesign labour --set 2.3.1a 110
python -m wanicndesign plan examples/house_8x12.json -o plan.dxf
python -m wanicndesign plan examples/house_8x12.json --autocad
```

## อัปเดตค่าแรง
- ปรับรายการเดียว: `labour --set รหัส ราคา` หรือปุ่ม "แก้ค่าแรงรายการ" ในหน้าต่างปริมาณ
  ค่าที่แก้จะบันทึกแยกไว้ใน `data/labour_override.json` ตาราง ว480 ต้นฉบับไม่ถูกแก้
- ปรับทุกรายการเป็นร้อยละ: `--labour-up 5` หรือปุ่ม "ปรับค่าแรงทั้งหมด %"
- เมื่อมีบัญชีค่าแรงฉบับใหม่ ให้แก้ตารางใน `3d/core/wanic_std2569.py`
  แล้วรัน `python design/WanicnDesign/tools/export_labour.py`

## ราคาวัสดุ
ราคาวัสดุเป็นของผู้ใช้ (สำนักงานพาณิชย์จังหวัดหรือร้านค้า) เริ่มต้นเป็น 0
ใช้คำสั่ง `prices` สร้างไฟล์รายการ แล้วกรอกราคาต่อหน่วย

## ทดสอบ
```
python -m pytest -q tests
```

## ข้อจำกัดของเวอร์ชันนี้
- ปริมาณคอนกรีตคานคิดเต็มความลึก (ยังไม่หักส่วนที่ซ้อนกับพื้น)
- เหล็กเสริมคิดตามความยาวชิ้นส่วน ยังไม่รวมระยะทาบและงอ นอกจากขอปลอก
- กฎทับหลังตามภาคผนวกคู่มือเดิม ยังไม่ได้ตรวจกับโปรแกรมเดิม
- ส่วน AutoCAD (COM) ยังไม่ได้ทดสอบบนเครื่องจริง ทดสอบเฉพาะส่วน DXF
- ปุ่มอื่นในเมนูหลักยังไม่ทำงาน อยู่ในแผนช่วงถัดไป
