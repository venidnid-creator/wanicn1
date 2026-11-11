# บันทึกส่งต่องาน (Handoff) — WANICNSURVEY / ReadWanicn2027

ไฟล์นี้เก็บสถานะงานทั้งหมด เพื่อให้ทำต่อได้ทันทีในรอบใหม่ (เมื่อโทเคนหมดหรือเริ่มเซสชันใหม่)
อัปเดตล่าสุด: 2026-11-11 · สาขา `claude/youthful-pascal-ctgtr0` · repo `venidnid-creator/wanicn1`

## กฎที่ผู้ใช้กำหนด (ต้องทำทุกครั้ง)
- ทุกส่วนใหม่ต้อง **ส่งภาพหน้าจอให้อนุมัติก่อน** สร้าง .exe — commit งานที่ยังไม่อนุมัติด้วย `[skip ci]`
- เมนูและข้อความทั้งหมดเป็น **ภาษาไทย** (ไม่ใช้ชื่อยี่ห้อ Word/Excel) · ใช้ **ฟอนต์ไทย**
- หากสงสัยให้ **ถามก่อน** · ตอบผู้ใช้เป็นภาษาไทย
- ก่อน push: `git fetch origin claude/youthful-pascal-ctgtr0 && git rebase origin/claude/youthful-pascal-ctgtr0`
- ห้ามเผยแพร่ GitHub Release เอง ยกเว้นผู้ใช้สั่ง (ReadWanicn: workflow_dispatch `release=true`)

## ReadWanicn2027 (โฟลเดอร์ `readwanicn2027/`)
- รุ่นล่าสุดที่เผยแพร่: **2027.3.0** (Release `readwanicn-v2027.3.0`) — workflow `readwanicn-windows.yml`
- คีย์ใบอนุญาตอยู่ใน GitHub secret `READWANICN_LICENSE_KEY` (ตั้งแล้ว) · รหัสต่ออายุ: `tools/readwanicn_code.py`
- ผู้ใช้ Wanicn / รหัสผ่าน Thammawong

## WANICNSURVEY (cad/ 3d/ launcher/) — workflow `build-windows.yml`
รุ่นที่กำลังสร้าง: **2026.11.11.1** (dispatch, release=false — ผู้ใช้จะลองก่อน ยังไม่เผยแพร่) รวมงานที่อนุมัติแล้วทั้งหมดรวมทั้งคำนวณโครงสร้าง
(รอบแรกล้มเพราะ CI ไม่มี openpyxl → รายงาน RC ใช้ตัวเขียน .xlsx ของโปรแกรมเอง `core.wanic_takeoff._xlsx`):
1. หลังคา: จั่วสมมาตร (โครงถักบนผนังจั่ว), ทรงไทย, จั่วซ้อน, โครงไม้ — `3d/core/wanic_building.py`
2. หน้าเริ่มต้น 2027: ธีม 5 แบบ, ไทย/EN, การ์ด 4 ใบ, แผงผู้พัฒนา — `launcher/launcher.py`
   (ส่ง `WANIC_LANG`, `WANIC_START_PANEL` ให้ 2D/3D — `3d/main.py`, `cad/main.py`)
3. ออกแบบโครงสร้าง คสล. 8 ขั้น — `3d/plugins/wanic_rc.py`, `3d/core/wanic_rc.py`
4. แก้เลือกวัตถุช้า (`views/extension_api.py on_document_changed` กรองการเลือก) และข้อมูลชิ้นส่วนตามขนาดจริง
   (`core/wanic_partprice.py live_rows/refresh`, `core/history.py ScaleGroupCommand`)

อนุมัติแล้ว (อยู่ในตัวติดตั้ง 2026.11.11.1 รอบที่สอง):
5. **คำนวณโครงสร้าง** ขั้น 9 — `3d/core/wanic_calc.py` (โหลด, คานต่อเนื่อง stiffness, SDM/WSD, ASD หลังคา,
   เสา, ฐานราก/เข็ม), `3d/core/wanic_calc_view.py` (SFD/BMD, รายการคำนวณ PDF), ทดสอบ `3d/tests/test_wanic_calc.py`
   ค่าออกแบบ (ผู้ใช้ตกลง): SDM วสท. 011008 (WSD ทางเลือก), fc′ 240, SD40/SR24, SS400 Fy 2450,
   LL พื้น 150 / หลังคา 30 กก./ตร.ม., ลม 50 กก./ตร.ม., ดิน 10 ตัน/ตร.ม., เข็ม I-0.18 ยาว 6 ม. 8 ตัน/ต้น

## งานถัดไป (ลำดับ)
- [x] พื้นแบบสัมประสิทธิ์ วสท. (Method 2) — `slab_moment`, `discontinuous_edges`
- [x] เสา: แรงอัดร่วมโมเมนต์ แผนภาพ P-M — `pm_curve`, `pm_ratio`, `draw_pm`
- [x] แรงลมบนหลังคา: D+W (Cp 0.7, ×4/3) แป/จันทัน + แรงยกที่จุดยึด
- [ ] ส่งภาพให้อนุมัติ → สร้างตัวติดตั้งรุ่นถัดไป (dispatch build-windows.yml พร้อม version ใหม่)
- [x] ตัวติดตั้ง 2026.11.11.1 สร้างสำเร็จ (run 43021651986, artifact wanicnsurvey-setup-2026.11.11.1) ส่งให้ผู้ใช้ลองแล้ว
- [ ] รอผลการลองจากผู้ใช้ · เผยแพร่ Release เมื่อผู้ใช้สั่งเท่านั้น (dispatch build-windows.yml version 2026.11.11.1 release=true)
- [ ] (ตัวเลือก) ธีม 5 แบบในหน้าต่างโปรแกรม 2D/3D · ภาพเหล็กเสริมในโมเดล 3D · ค่าเริ่มต้น GB1 3-DB12

## การทดสอบ/ภาพหน้าจอ
- 3D รันจริงได้ด้วย: `xvfb-run -a -s "-screen 0 1920x1080x24"` + `QT_QPA_PLATFORM=xcb LIBGL_ALWAYS_SOFTWARE=1`
  (ติดตั้ง libxcb-cursor0 libxkbcommon-x11-0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-randr0
  libxcb-render-util0 libxcb-shape0 libxcb-xinerama0 libxcb-xkb1)
- ชุดทดสอบใน CI: ดูบรรทัด pytest ใน `.github/workflows/build-windows.yml`
