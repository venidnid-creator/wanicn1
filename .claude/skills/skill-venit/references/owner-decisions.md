# The owner's decisions (keep them — do not ask again)

Quotes are the owner's words; dates are 2026 (Buddhist year 2569).

## Working rules
- Reply in Thai; programs in Thai; no brand names (Word/Excel) in the UI.
- Screenshots → «อนุมัติ» → only then an installer. Unapproved work is committed with `[skip ci]`.
- «ห้ามเผยแพร่ จนกว่าจะอนุมัติให้เผยแพร่» — installers `release=false`; Release only on order.
- Record everything for the next session (handoff + this skill), «สร้างสกิลเก็บไว้ด้วย ตั้งแต่ต้น».
- Study commercial programs (QuickDesign) and Thai-Pave/Thai-Slope for the **workflow only** — never copy code/UI/files.
- Signature everywhere: นายเวนิช ธัมมะวงษ์ · วิศวกรสำรวจ. Developer panel (photo, QR LINE, phone 093-5838348, Krungsri
  666-1-32472-1, free to use) is mandatory.
- Ask when unsure; «ตามที่แนะนำ» / «อนุมัติ» = proceed.

## Structure and calculation
- (27 Nov) Reserve: first «กำลังที่เหลือ ≥ 1 เท่า» (≤ 50 %), then after seeing the cost (+80–90 % steel) the owner
  ordered «แก้ไข ใช้มาตรฐาน วสท.» — default `max_use` 1.0 (วสท. alone); 50 % stays an option in the basis dialog.
  Soil and piles keep their own FS; deflection/least thickness always 100 %.
- (27 Nov) Foundations: user chooses spread or piles (`data["foundation"]`); auto = 3 storeys up on I piles.
- (27 Nov) Separate buildings: calc book, BOQ and drawing set split per building (`B.building_data`).
- (27 Nov) Tell the owner first which requested items are already done (avoid duplicates).
- Basis: SDM วสท. (WSD กทม. 2522 optional), current seismic/wind standards with the old formulas optional.
- «ห้ามลดเองตามประเภทอาคาร» — live-load reduction never automatic for the ข้อ 14 uses.
- «หุ้มเสาอัตโนมัติ» — fire cover of columns set automatically.
- Stairs: head/tail swap, landing at the column line, SB2 spans to the far column, no stair across a column line.
- (25 Nov) «รายการที่ออกแบบผ่านแล้ว แบบ PDF และ DXF ต้องตรงกัน โดยยึดรายการคำนวณเป็นหลัก».
- (25 Nov) «เมื่อมีการเปลี่ยนโมเดล ต้องคำนวณโครงสร้างใหม่ ทุกรายการ ทุกรายการต้องสัมพันธ์กัน».
- (25 Nov) «รวมไปถึงการถอดแบบแปลนเพื่อประมาณราคาด้วย แก้ไข 1 จุด อัปเดตทั้งหมด».
- Open question for the owner: should exports be **blocked** while items fail (now: warn only; the calc book is blocked)?

## Prices and BOQ
- (27 Nov) Furniture in the model is billed as หมวด 16 ครุภัณฑ์จัดซื้อ: no Factor F, + VAT 7 %, labour ≤ 30 % of
  the material (editable option); never in the construction categories 1–15.
- Prices 0 until a province is chosen; sources ว480 labour → พาณิชย์จังหวัด → central → neighbouring province → orange
  rows to type; no ปร. export until every line is priced.
- สพฐ. prices «เฉพาะงาน สพฐ.» — never in another job or the province book.

## Roads
- Cross sections «ตามมาตรฐาน ทช. หรือ ทล.»; no 3D model without «6. สรุปการออกแบบ»; layer table waits for the design.
- THAI-PAVE manual (uploaded PDF) for the steps; Thai-Slope not ordered yet.
- (27 Nov) Pavement methods: **only AI 1970 (asphalt) and Road Note 29 (concrete)**, both tabs selectable;
  PCA 1984 cancelled — do not add it. The owner will send a new brief for the whole road part.
- Curves smooth, PC/PT/R/V shown in survey and plan; tables explained in plain words for everyone.
- «ปรับค่ากึ่งกลาง» — CL shots onto the line to be built, N E Z follow.
- Site check from LandsMaps (done from parcel files — LandsMaps unreachable); «ใส่ค่าพิกัด E N และโซน» on the report.
- Permission text on every sheet; road set without drainage pipes; no symbol over text; glossary on every sheet
  («ทุกแผ่น … คนที่ไม่เข้าใจภาษาช่าง ก็ได้เข้าใจตรงกัน» — chose «กรอบเล็กทุกแผ่น + แผ่นรวม»).

## Start screen and programs
- Update window like ReadWanicn2027 **with the download button** (overrides the 7 Nov «ติดต่อผู้พัฒนาเพื่อรับรุ่นใหม่»).
- Seven languages: ไทย, English, ລາວ, Tiếng Việt, Bahasa Indonesia, 简体中文, 繁體中文 (台灣).
- PDF import into the 2D program as DXF.
- Paper blocks A0–A4 with a beautiful default font named «เวนิช» — chose base «ค. ลายมือ (Charm)».
