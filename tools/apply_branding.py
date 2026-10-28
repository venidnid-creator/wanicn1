"""Apply WANICNSURVEY branding to the upstream sources (idempotent check)."""
import json, re, shutil, sys
from pathlib import Path
W = Path(__file__).resolve().parent.parent
CAD, T3D, BR = W/'cad', W/'3d', W/'branding'

def sub(path, old, new, count=1):
    p = Path(path); s = p.read_text(encoding='utf-8')
    n = s.count(old)
    if n == 0: sys.exit(f'NOT FOUND in {p}: {old[:70]!r}')
    if count and n != count: sys.exit(f'{n} matches (want {count}) in {p}: {old[:70]!r}')
    p.write_text(s.replace(old, new), encoding='utf-8')

# ---------- CAD ----------
m = CAD/'main.py'
sub(m, 'QCoreApplication.setApplicationName("IngeCAD")\n    QCoreApplication.setOrganizationName("IngeCAD")',
       'from core import branding\n    QCoreApplication.setApplicationName(branding.APP_NAME)\n    QCoreApplication.setOrganizationName(branding.ORG_NAME)')
sub(m, 'i18n.set_language(str(QSettings().value("language", "en")))',
       'from core import branding\n    i18n.set_language(str(QSettings().value("language", branding.DEFAULT_LANGUAGE)))')
for f in ['views/main_window.py','views/document_tabs.py','views/recovery_dialog.py']:
    p = CAD/f; s = p.read_text(encoding='utf-8')
    s2 = s.replace('f"IngeCAD — ', 'f"{_BRAND} — ').replace('f"IngeCAD {__version__}"', 'f"{_BRAND} {__version__}"')
    assert s2 != s, f
    s2 = s2.replace('\nfrom __future__ import annotations\n', '\nfrom __future__ import annotations\n\nfrom core.branding import APP_NAME as _BRAND\n', 1)
    assert '_BRAND\n' in s2, f
    p.write_text(s2, encoding='utf-8')
p = CAD/'views/startup_dialog.py'
sub(p, 'self.setWindowTitle(tr("IngeCAD"))', 'self.setWindowTitle(_BRAND)')
sub(p, 'heading = QLabel(f"IngeCAD {__version__}")', 'heading = QLabel(f"{_BRAND} {__version__}")')
sub(p, '\nfrom __future__ import annotations\n', '\nfrom __future__ import annotations\n\nfrom core.branding import APP_NAME as _BRAND\n')
sub(CAD/'views/main_window.py', '        help_menu = menu_bar.addMenu(tr("Help"))\n',
    '        from core import companion\n        companion.install_menu(self, menu_bar, tr)\n\n        help_menu = menu_bar.addMenu(tr("Help"))\n')
sub(CAD/'views/about_dialog.py', '''        para("<b style='font-size:15px'>IngeCAD</b> "''',
    '''        from core import branding
        para(f"<b style='font-size:15px'>{branding.APP_NAME}</b><br>"
             f"พัฒนาต่อยอดโดย <b>{branding.DEVELOPER}</b> ({branding.YEAR})<br>"
             f"<small>สร้างจากซอฟต์แวร์เสรี {branding.UPSTREAM} — GPL-3.0</small>")
        para("<b style='font-size:15px'>IngeCAD</b> "''')
# icons
shutil.copy(BR/'wanicnsurvey-cad.svg', CAD/'resources/ingecad.svg')
shutil.copy(BR/'wanicnsurvey-cad.ico', CAD/'resources/icons/ingecad.ico')
for s in [16,24,32,48,64,128,256,512]:
    shutil.copy(BR/f'png/wanicnsurvey-cad-{s}.png', CAD/f'resources/icons/ingecad_{s}.png')

# ---------- 3D ----------
m = T3D/'main.py'
sub(m, 'app.setApplicationName("IngeTrazo")\n    app.setOrganizationName("IngeTrazo")',
       'from core import branding\n    app.setApplicationName(branding.APP_NAME)\n    app.setOrganizationName(branding.ORG_NAME)')
sub(m, '''        else:
            saved = "en"
    i18n.set_language(str(saved))''', '''        else:
            from core import branding
            saved = branding.DEFAULT_LANGUAGE
    i18n.set_language(str(saved))''')
sub(T3D/'core/platform_choice.py', 'QCoreApplication.setOrganizationName("IngeTrazo")\n    QCoreApplication.setApplicationName("IngeTrazo")',
    'from core import branding\n    QCoreApplication.setOrganizationName(branding.ORG_NAME)\n    QCoreApplication.setApplicationName(branding.APP_NAME)')
p = T3D/'views/main_window.py'
sub(p, 'self.setWindowTitle(f"IngeTrazo — {self._workspace.title()}{marker}")', 'self.setWindowTitle(f"{_BRAND} — {self._workspace.title()}{marker}")')
sub(p, 'self.setWindowTitle(f"IngeTrazo — {name}{marker}")', 'self.setWindowTitle(f"{_BRAND} — {name}{marker}")')
sub(p, '        help_menu = menubar.addMenu(tr("Help"))\n',
    '        from core import companion\n        companion.install_menu(self, menubar, tr)\n\n        help_menu = menubar.addMenu(tr("Help"))\n')
s = p.read_text(encoding='utf-8')
s = s.replace('\nfrom __future__ import annotations\n', '\nfrom __future__ import annotations\n\nfrom core.branding import APP_NAME as _BRAND\n', 1)
assert 'as _BRAND\n' in s; p.write_text(s, encoding='utf-8')
p = T3D/'views/outliner.py'
sub(p, 'tr("Rename selected") + " — IngeTrazo"', 'tr("Rename selected") + " — WANICNSURVEY 3D"')
sub(p, 'tr("Materials") + " — IngeTrazo"', 'tr("Materials") + " — WANICNSURVEY 3D"')
sub(T3D/'views/about_dialog.py', '''        para("<b style='font-size:15px'>IngeTrazo</b> "''',
    '''        from core import branding
        para(f"<b style='font-size:15px'>{branding.APP_NAME}</b><br>"
             f"พัฒนาต่อยอดโดย <b>{branding.DEVELOPER}</b> ({branding.YEAR})<br>"
             f"<small>สร้างจากซอฟต์แวร์เสรี {branding.UPSTREAM} — GPL-3.0</small>")
        para("<b style='font-size:15px'>IngeTrazo</b> "''')
shutil.copy(BR/'wanicnsurvey-3d.svg', T3D/'resources/icons/ingetrazo.svg')
shutil.copy(BR/'wanicnsurvey-3d.ico', T3D/'resources/icons/ingetrazo.ico')
shutil.copy(BR/'png/wanicnsurvey-3d-512.png', T3D/'resources/icons/ingetrazo_master.png')
for s in [16,32,48,64,128,256,512]:
    shutil.copy(BR/f'png/wanicnsurvey-3d-{s}.png', T3D/f'resources/icons/ingetrazo_{s}.png')

# ---------- Thai packs: product names ----------
packs = [CAD/'i18n/th/ui.json', CAD/'plugins/topografia/i18n/th/ui.json',
         CAD/'plugins/terreno/i18n/th/ui.json', T3D/'i18n/th.json']
n = 0
for p in packs:
    d = json.loads(p.read_text(encoding='utf-8'))
    for k, v in d.items():
        v2 = v.replace('IngeCAD', 'WANICNSURVEY CAD').replace('IngeTrazo', 'WANICNSURVEY 3D')
        if v2 != v: d[k] = v2; n += 1
    p.write_text(json.dumps(d, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print('branding applied; Thai strings renamed:', n)
