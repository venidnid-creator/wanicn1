# Engineering and drawing conventions (keep consistent)

## The single-source rules (owner, 25 Nov 2026) — never break them
1. **Drawings follow the calc book.** What passed in the calculation is exactly what the S sheets (PDF and DXF — one
   list of `Sheet.items`) show: same bars, counts, spacings, written the same way.
   - Spacing text: always `wanic_rc.spacing(s)` (0.125 stays «0.125», 0.2 → «0.20»). Never `f"{s:.2f}"`.
   - Beam end stirrups: `wanic_rc.end_stirrups(spec)` → (2h, min(s, d/4) rounded down to 2.5 cm, ≥ 5 cm) — the calc
     check text, S-08 beam detail («2h @e · กลางช่วง @s») and the beam profiles all use it.
   - Beams: every top/bottom bar of the spec runs the whole span; sections at L, M, R show the full counts (as the
     booklet's L/M/R table). No L/4, L/5 cut-offs.
   - Footings: the booklet reports the bars the drawing shows `nbar = mesh_count(width, s)` and fails when
     `nbar < need`; S-09 draws that many and writes «(nx×ny เส้น)».
2. **One change updates all.** Bar counts come only from `R.stirrup_count(L, spec)` and `R.mesh_count(width, s)` —
   in the calc book, the drawings, the BOQ (`wanic_quantities`) and the cutting list (`wanic_cutting`). Never a local
   formula. Test: `test_one_change_updates_the_calc_the_drawings_the_boq_and_the_cutting_list`.
3. **A changed model is calculated again, every item.** `B.struct_stamp(data)` fingerprints everything but prices,
   schedule, province (`B.NOT_STRUCTURAL`); `B.recalc_all` stamps `data["calc_stamp"]` only when every member passes;
   the building panel shows the orange banner + «🔄 คำนวณโครงสร้างใหม่ทุกรายการ»; drawing export, BOQ export and the
   calc book recalculate first (`panel.calc_note()`); failing items are reported in the export message.
4. **Every sheet explains its terms** for lay readers (`wanic_glossary`): box where nothing is drawn, else a pointer in
   the bottom margin; one G sheet for the whole set. New technical words on a sheet → add to `TERMS`. Tables of
   curves etc. also get plain sentences (`RS.plain_words`).
5. **No text over text** on any sheet (test `test_no_text_over_another_on_any_road_sheet`; text angles −90…90°).
6. **Permission text** «การนำข้อมูลไปใช้จะต้องได้รับอนุญาตจากเจ้าของพื้นที่แล้วเท่านั้น» bottom right of every road
   sheet (`RS.PERMISSION`), in the LC-01 report and above the title block of the paper blocks.

## Units and basis
- kg, m (cm for sections), ksc = kg/cm²; concrete 2,400 kg/m³.
- Basis defaults (`wanic_calc.DEFAULTS`): SDM วสท. 011008, U = 1.4D + 1.7L, φ 0.90/0.85/0.70; fc′ 240, SD40 4000,
  SR24 2400, SS400 Fy 2450; LL by กฎกระทรวง 2566 (house floor 200), roof 30, finish 50, wall 180, soil 10 t/m², pile 8 t.
  WSD option = ข้อบัญญัติ กทม. 2522. LL reduction (กฎกระทรวง 2566 ข้อ 13) never for the ข้อ 14 uses (`C.OCCUPANCY`).
- Steel/timber roof and structural steel: AISC ASD. Slabs: ACI 318-63 Method 2. Flat slab: DDM, punching 1.06√fc′ b0 d.
- Lateral: มยผ. 1301/1302-61 by province (ข5), wind มยผ. 1311-50; frames + drift (`wanic_frame`).
- Fire: กฎกระทรวง 2566 ข้อ 21–24 + ประกาศ มท. 2567 ตาราง 17–18; column cover set automatically.
- Covers `R.COVER` = footing 0.075, stump 0.040, column 0.035, beam 0.030, slab 0.020 (fire may raise column cover).
- `tools/verify_hand_calc.py` compares the program with textbook hand formulas — keep it passing
  (`tests/test_wanic_hand_verify.py`); it checks single footings (`combined_footings = []`).

## Drawings
- Sheets are `D.Sheet` items in paper mm; PDF via `plugins.wanic_building.render_pdf`, DXF via `D.dxf_bytes` (ANSI_874).
- Characters outside cp874 must be mapped in `D._DXF_SUB` (− « » √ Δ ≥ ×…; √ Δ ≥ as AutoCAD `\U+XXXX`). Test with
  `D.dxf_text(t).encode("cp874")`.
- `render_pdf` fonts switch off `calt`/`case`/`liga` so a PDF of ours reads back as characters (PDFIMPORT).
- Title column `D.frame` (all programs): header centred, one-line names centred, sign lines with the title at the end.
- Road set (`RS.build_road_set`): G (with glossary sheet) PP ST VT SD TS QS — **no DR** (owner, item 38).
- Fonts: Thai fonts in programs; the 2D paper blocks use «เวนิช» (Venit = Charm renamed, OFL; ship `Venit-OFL.txt`).

## Roads
- Surveyed axis → `smooth_axis` (true arcs every 1 m); PI design `alignment_from_pis(step=1)`; `fit_radius` refines the
  4 % grid by golden section to the designer's round radius.
- Entry speed V = √(127 R (e + f)), f by ทถ-2-104, rounded down to 5 km/h, ≤ 120.
- «ปรับค่ากึ่งกลาง»: `fit_centreline` (Douglas-Peucker at several tolerances, least-squares tangents, the fewest PIs
  within 1.25× the best RMS + 0.01, refit without shots > max(1 m, 3·RMS)); CL shots moved N E onto the line, Z by the
  ground slope; the panel keeps the fitted axis and its PIs.
- Pavement: the design must give «6. สรุปการออกแบบ» before the layer table or the 3D model.
- Site check: parcel files only (no live LandsMaps); footprint toe-to-toe or ROW width, strips clipped by
  Sutherland–Hodgman; rai-ngan-wa 1600/400/4 m²; LC-01 with UTM grid, zone, key-point coordinates.

## Data in the building document
`data["calc"]`, `["grid"]`, `["truss"]`, `["steel"]`, `["purlin"]`, `["flatslab"]`, `["lateral"]`, `["private_est"]`,
`["beam_loads"]`, `["cantilevers"]`, `["combined_footings"]`, `["schedule"]`, `["obec"]`, `["calc_stamp"]`,
`["calc_at"]`, prices `["prices"]`, `["price_src"]`, `["labour"]` — always write through `bp._write(d)`.
