# How to work — tests, screenshots, installers, gotchas

## Tests
- 3D (fast, headless): `cd 3d && QT_QPA_PLATFORM=offscreen python3 -m pytest -q -p no:cacheprovider tests/test_wanic_<x>.py`.
  Run in small sets (a Bash call times out after 2 min; long sets go in the background + `Monitor` on the log).
- The CI list: `grep -o "tests/test_[a-z_0-9]*\.py" .github/workflows/build-windows.yml` (~400 tests). Run the parts
  you touched **and** the hand check (`test_wanic_hand_verify.py`) and `test_wanic_w480_detail.py` before an installer.
- 2D: `cd cad && QT_QPA_PLATFORM=offscreen python3 -m pytest -q -p no:cacheprovider tests/…`. New UI strings need Thai
  **and Spanish** entries (`cad/i18n/{th,es}/ui.json`) — `test_i18n_coverage` fails otherwise.
- Start screen: `3d/tests/test_launcher_*.py`.
- Any button that opens a modal `exec()` must skip it when `WANIC_OFFLINE` is set (tests set it) — otherwise the
  every-button test hangs forever.
- MainWindow (2D) in tests: `win.new_document()` first; set `win.document.dirty = False` before `close()`.

## Screenshots (for the owner's approval)
- Scripts live in the scratchpad (not the repo). Apply the theme (`views.theme.apply_theme(app)`), set
  `WANIC_OFFLINE=1`, exit with `os._exit(0)`.
- Sheets → PDF with `plugins.wanic_building.render_pdf`, then `pdftoppm -r 90..150 -png` (crop with `-x -y -W -H`).
- The 2D canvas needs OpenGL — offscreen it stays blank: show a DXF rendered with ezdxf + matplotlib instead (Thai text
  shows as boxes there; say so) and menus via `w._menu_bar` (the CAD uses its own QMenuBar).
- Fonts for container screenshots: Thai tlwg (Garuda, Loma), Chinese `wqy-zenhei`, Lao `apt-get install fonts-lao`.
- Launcher screenshots: `XDG_CONFIG_HOME` to the scratchpad, patch `StartWindow._fetch_stats`.
- Always send screenshots with `SendUserFile` and wait for «อนุมัติ» before an installer.

## Installer (never a Release unless the owner orders)
1. Add the version to `WANIC-CHANGELOG.md` and `installer/release-notes.md` (Thai, ends with the signature line).
2. `mcp__github__actions_run_trigger` `run_workflow`, `workflow_id: build-windows.yml`,
   `ref: claude/youthful-pascal-ctgtr0`, inputs `{"version": "YYYY.MM.DD.N", "release": false}`.
3. `send_later` ~25 min to check (do not poll). On failure read `get_job_logs(run_id, failed_only=true)`, fix,
   retest locally, rebuild.
4. On success list the artifacts; tell the owner the link `https://github.com/venidnid-creator/wanicn1/actions/runs/<run>`
   → Artifacts → `wanicnsurvey-setup-<version>` (zip with the .exe, kept 90 days); record run/artifact in the handoff.
5. Publish only on «อนุมัติเผยแพร่»: re-run with `"release": true` (or push tag `v<version>`).
- New Python dependencies: add to `cad/requirements.txt`/`3d/requirements.txt`, the `pip install` line of
  `build-windows.yml`, and the PyInstaller spec `hiddenimports` (e.g. `pymupdf` for PDFIMPORT).
- Bundled data (fonts etc.) for the 2D program go under `cad/resources/` (the spec ships the whole folder).

## Git
- Commit after every piece with a clear English message ending with the session's attribution lines; `[skip ci]` while
  awaiting approval. Push `git push -u origin claude/youthful-pascal-ctgtr0`. No model names in commits/artifacts.
- A stop hook insists on a clean tree: commit + push before ending a turn.

## Network/environment (cloud session)
- Blocked hosts so far: engfanatic.tumcivil.com (owner declined to allow — do not ask again), landsmaps.dol.go.th
  (built the file-based site check instead). Package registries and apt work.
- Upstream sync (IngeCAD/IngeTrazo): 3-way `git merge-file` against the tag recorded in NOTICE.md; for files added on
  both sides (Thai i18n) keep ours key by key and fill missing keys from upstream.

## Writing to the owner
- Thai, short, concrete: what was done, numbers, what is not yet verified, then «ขออนุมัติ» and the next planned item.
- When a request is ambiguous, ask with `AskUserQuestion` (options with a recommended first); when a decision is the
  owner's (licence/font choice, publishing, stricter blocking), ask — otherwise proceed.
