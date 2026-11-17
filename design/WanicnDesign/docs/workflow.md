# ลำดับการทำงานของระบบ QD (จากคู่มือ 5 หน้า)

ระบบทำงานร่วมกัน 3 ส่วน: AutoCAD (แปลน และเมนู Mainmenu), SketchUp (ปลั๊กอิน
Quickdesign / QuickSteel) และการแลกเปลี่ยนไฟล์ผ่านโฟลเดอร์ `C:\SKUDWG`

## ลำดับหลัก (ตามคู่มือ)
1. **แปลนใน AutoCAD** วาดแปลนและกำหนดขนาด/ระดับ
2. **Export 3D** — ส่งข้อมูลแปลนจาก AutoCAD ออกเป็นไฟล์ข้อความ (text file)
3. **SketchUp** อ่านไฟล์ข้อความแล้วสร้างโมเดล 3 มิติ โดยเลือกคำสั่งตามประเภทงาน:
   - *Draw Building* (อาคาร): Door → Home → Frame → Roof → CoverRoof → Stair
   - *Draw Factory* (โรงงาน/โกดัง): Door → Home → QuickSteel (WF, Truss, InTruss, Purlin)
   - ชั้นของโมเดลแยกเป็น layer เปิด/ปิดการมองเห็นได้
4. **Decoration** — เพิ่มส่วนตกแต่งก่อนส่งออก (ทำใน SketchUp ก่อน Export)
5. **Export to DWG** — เลือกฉาก (scene) ทีละฉาก: Front, Rear, Left, Right, A-A, B-B
   แล้วส่งออกเป็น `C:\SKUDWG\<ชื่อฉาก>.dwg` (เมนู File → Export → 2D Graphic)
6. **Elev. And Section ใน AutoCAD** — เมนู Mainmenu → Section:
   - `SketchUp` ดึงไฟล์ภาพตัดจาก `C:\SKUDWG\...`, คัดลอกเส้นกริดจากหน้าด้านไปยังภาพตัด
   - `Decor.` เปิดเมนูบล็อกหน้าด้านและภาพตัด
   - `Landscape` เปิดเมนูตกแต่งภูมิทัศน์
   - `D-W` เลือกชื่อประตู/หน้าต่างแล้วคลิกจุดวาง รายการ: D1, D2, D3, W1, W2, W3
     เลือก `S` สำหรับมุมด้านข้าง และ `E`/`F` สำหรับมุมด้านหน้า
   - `Vport` วาง viewport ของภาพตัดลงในเลย์เอาต์ "Plan"

## หมายเหตุ
- ฉากใน SketchUp คือ Front, Rear, Left, Right, A-A, B-B
- เส้นทางไฟล์ที่ระบุในคู่มือ: `C:\SKUDWG\`
- ตัวเลือกประตูหน้าต่างที่เห็น: D1, D2, D3, W1, W2, W3
- เอกสารนี้สรุปจากคู่มือเท่านั้น ยังไม่ได้ตรวจกับโค้ดต้นฉบับ
