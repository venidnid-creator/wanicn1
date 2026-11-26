# Repository and module map

## Top level

| Path | What |
|---|---|
| `launcher/` | Start screen «WANICNSURVEY 2027». `launcher.py` (THEMES ×5, `TEXT` in 7 languages + `LANGUAGES` menu, `THEME_NAMES`, CARDS 2D/3D/RC/ROAD, developer panel, stats corner, `_offer_update`), `stats.py` (GitHub release counts, `summary` = WANICNSURVEY tags `v…` only, notes, installer URL, `newer`, `latest_line`), `update_dialog.py` («มีเวอร์ชันใหม่» window), `wanic_license.py` (1 year of use), `wanic_login.py`. Passes `WANIC_LANG`, `WANIC_START_PANEL`, `WANIC_SESSION` to the programs. Spec `launcher.spec` (hiddenimports stats, wanic_login, wanic_license, update_dialog). |
| `cad/` | WANICNSURVEY CAD (2D) — fork of IngeCAD (synced to 0.8.0). Thai i18n `cad/i18n/th/ui.json` (+ es kept complete: a test demands it). WANIC additions: `formats/pdf_in.py` (PDFIMPORT), `core/paper_blocks.py` (A0–A4 frames), `core/ezdxf_patches._register_bundled_fonts`, `resources/fonts/Venit-*.ttf`, plugins `topografia`, `terreno`. Spec `cad/packaging/ingecad.spec`. |
| `3d/` | WANICNSURVEY 3D — fork of IngeTrazo (synced to 0.6.2.1). WANIC plugins `3d/plugins/wanic_*.py` (auto-discovered, `setup(app)`); engineering in `3d/core/wanic_*.py` (never helpers in `plugins/` — they would load as plugins). `3d/core/road/{alignment,tin,profile}.py` must stay **byte-for-byte** the CAD's (`cad/plugins/topografia/…`) — a test compares them; put road additions in `wanic_road.py`. |
| `readwanicn2027/` | ReadWanicn2027 (Thai PDF program), released separately (`readwanicn-v…`, workflow `readwanicn-windows.yml`). Newer 2027.4.x lives on branch `claude/zen-feynman-ptcfng`. |
| `design/WanicnDesign` (branch `claude/awesome-pasteur-y5g1in`) | The owner's other design program; ข12 took ideas from it (rewritten ourselves). |
| `branding/` | Icons, developer photo, QR, fonts (`Charm-*`, `Venit-*` + `Venit-OFL.txt`). |
| `installer/` | Inno Setup script, `release-notes.md` (shown on the Release and in the update window). |
| `docs/WANIC-HANDOFF.md` | Live Thai log — read first, update after every step. |
| `WANIC-CHANGELOG.md` | Changelog per version (Thai, signature block). |
| `.github/workflows/build-windows.yml` | Installer: inputs `version`, `release`; jobs converters (LibreDWG) + windows (pytest of WANIC tests, freeze CAD/3D/launcher, smoke test, Inno Setup, artifact, optional Release). Add every new 3D test file to its pytest list. |

## 3D plugins (dock panels)
`wanic_building.py` ออกแบบอาคาร (`window._wanic_building`: `data()`, `_write(d)`, `refresh`, `build(parts)`, BoqDialog,
DrawingDialog, stale banner `_show_stale`, `recalc_structure`, `calc_note`) · `wanic_rc.py` ออกแบบโครงสร้าง คสล.
(`window._wanic_rc`, 9 steps, `_all_pass` → `B.recalc_all`) · `wanic_road.py` ออกแบบถนน (`window._wanic_road`:
RoadPanel, PavementDesignDialog, ResultsDialog, RoadSheetsDialog, CentreFitDialog, LandCheckDialog) ·
`wanic_takeoff.py` ถอดปริมาณ ปร.1–ปร.4 · `wanic_profiles.py` โปรไฟล์.

## 3D core modules

### Building, model, drawings
| Module | Purpose |
|---|---|
| `wanic_building` | Plan → elements `B.elements(data)` (footings, stumps, columns, beams, slabs, walls, stairs, lib, settings, floors); library marks; roofs; stairs geometry; holes; `struct_stamp` / `calc_current` / `recalc_all` (changed model → calculate again). |
| `wanic_catalog`, `wanic_categories` | Fittings and how each is billed; the 15 หมวดงาน. |
| `wanic_drawings` | The drawing set `D.build_set` (G A S SN EE M BOQ), `Sheet` primitives, `frame` (title column), `dxf_bytes`, `_DXF_SUB` (cp874 mapping), `_bars`, `drawing_area`. |
| `wanic_std_sheets`, `wanic_std_sn`, `wanic_std_ee`, `wanic_std_m` | Sheets like the กรมโยธาธิการ standard sets (A, SN-01..10, EE-01..06, M-01..02). |
| `wanic_struct_sheets`, `wanic_steel_sheets`, `wanic_stair_sheets` | S sheets from the calculation (beam profiles per line, footing/column/slab details), steel and stair details. |
| `wanic_opening_sym` | Door/window swing symbols (one for plan and sheets). |
| `wanic_mep`, `wanic_mep_view`, `wanic_sanitary` | Services per room, septic/grease trap by users. |
| `wanic_roofclip`, `wanic_partprice`, `wanic_tabs`, `wanic_ui`, `wanic_sign`, `wanic_downloads`, `wanic_license`, `wanic_login` | Roof overlap, live part price, panel tabs, safe buttons, the developer's signature, download counter, licence, sign-in. |

### Calculation
| Module | Purpose |
|---|---|
| `wanic_calc` | `basis`, PRESETS SDM/WSD, LIVE_LOADS, OCCUPANCY (no-reduction uses), `solve_beam`, slabs (ACI 318-63 M2), P-M, roof, `analyse(data)`, checkload, load cases DL/LL. |
| `wanic_rc` | Bars `parse_bar`, laps, covers `cover_of`, detailing checks, **`spacing`, `end_stirrups`, `stirrup_count`, `mesh_count`** (the single source of bar counts), grid mode. |
| `wanic_calc_cards`, `wanic_calc_book`, `wanic_calc_view` | Booklet cards (footing `nbar`/`need`, slabs, roof), A4 booklet `make_book`, SFD/BMD drawing. |
| `wanic_advice`, `wanic_fix_view`, `wanic_fail_view`, `wanic_autodesign` | Advice, per-member fix, fail dialog, auto-design until passing (`design_footings` combines overlaps). |
| `wanic_frame`, `wanic_lateral(_view)` | Plane frames + drift; seismic/wind. |
| `wanic_combined`, `wanic_pile(_view)` | Combined footings; piles (2 sizes, capacity). |
| `wanic_fire` | Fire rating requirements, cover set automatically. |
| `wanic_truss(_view)`, `wanic_steel(_view)`, `wanic_purlin(_view)`, `wanic_flatslab(_view)` | Truss, steel H/WF, purlins/rods, flat slab DDM. |
| `wanic_stair`, `wanic_stair_view`, `wanic_stair_auto(_view)` | RC stairs, automatic stairs. |
| `wanic_free(_view)`, `wanic_beamload_view`, `wanic_grid_view` | Free drafting, beam loads/cantilevers/Checkload, grid mode. |
| `wanic_standards` | Whether ว480/ว481/2569 documents are current. |

### Quantities and prices
| Module | Purpose |
|---|---|
| `wanic_quantities` | Government BOQ (`Q.priced`, price gate, missing lines, sources). Bar counts via `wanic_rc`. |
| `wanic_takeoff` | ปร.1–ปร.4, own .xlsx writer `_Sheet`/`_xlsx` (CI has **no openpyxl**). |
| `wanic_cutting` | 10 m bar cutting list (counts via `R.stirrup_count`, `R.mesh_count`). |
| `wanic_schedule(_view)` | CPM + S-curve + installments. |
| `wanic_private_est(_view)` | Private estimate 8 categories. |
| `wanic_std2569`, `wanic_recipes2569`, `wanic_w480`, `wanic_factor_f`, `wanic_moc_codes` | 2569 criteria, recipes, ว480 labour, Factor F ว481, MOC product codes. |
| `wanic_province`, `wanic_obec` | Commerce prices by province (+ neighbours, import xlsx/csv/docx/pdf); สพฐ. book (only for สพฐ. jobs). |

### Roads
| Module | Purpose |
|---|---|
| `wanic_road` | Survey import, CL, PI alignment (`alignment_from_pis`, `fit_radius`), **`smooth_axis`**, **`entry_speed`**, **`fit_centreline` / `apply_fit`**, `analyse` (→ `Analysis` with `hcurves`, `se_plan`, `curve_speed`), superelevation, KML/Google Earth, UTM↔WGS84. |
| `wanic_pavement` | AI 1970, Road Note 29, THAI-PAVE steps (vehicle classes → ADT, design CBR), «6. สรุปการออกแบบ». |
| `wanic_road_sheets` | Road set G PP ST VT SD TS QS (no DR), `curve_rows`, `plain_words`, `_glossary`, `PERMISSION`, key plan. |
| `wanic_road_detail`, `wanic_road_furniture` | SD standard sheets; signs TS (`dr_sheets` kept but not in the set). |
| `wanic_glossary` | Plain-language glossary box on every sheet (`TERMS`, `occupied`, `free_spot`, `add_box`, `glossary_sheet`). |
| `wanic_landcheck` | Site check from parcel files (KML/KMZ/GeoJSON/DXF/CSV), footprint strips, rai-ngan-wa, LC-01 report. |
| `wanic_sitemap` | Site map sheet. |
