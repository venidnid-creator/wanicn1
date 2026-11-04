/**
 * WANICNSURVEY usage counter — Google Apps Script web app.
 * Copyright (C) 2026 นายเวนิช ธัมมะวงษ์ (วิศวกรสำรวจ) — GPL-3.0-or-later
 *
 * The start screen calls  <web app url>?id=<random install id>&v=<version>&e=open
 * and shows the answer {online, today, total}.  Only the random id, the
 * version and the time are kept (sheet «installs»: one row per id);
 * nothing else about the user is stored.
 *
 * Deploy (ครั้งเดียว):
 *  1. สร้าง Google Sheet ใหม่ → ส่วนขยาย ▸ Apps Script → วางไฟล์นี้แทนโค้ดเดิม
 *  2. ทำให้ใช้งานได้ ▸ การทำให้ใช้งานได้รายการใหม่ ▸ ประเภท «เว็บแอป»
 *     ดำเนินการในฐานะ: ฉัน · ผู้มีสิทธิ์เข้าถึง: ทุกคน → ทำให้ใช้งานได้
 *  3. คัดลอก URL ที่ลงท้ายด้วย /exec ไปใส่ launcher/stats.py (USAGE_URL)
 *     แล้วออกรุ่นใหม่ — หรือใส่ในเครื่องผู้ใช้: QSettings usage/url
 */
function doGet(e) {
  var p = (e && e.parameter) || {};
  var lock = LockService.getScriptLock();
  lock.waitLock(10000);
  try {
    var ss = SpreadsheetApp.getActiveSpreadsheet();
    var sh = ss.getSheetByName('installs') || ss.insertSheet('installs');
    if (sh.getLastRow() === 0) sh.appendRow(['id', 'first', 'last', 'version', 'opens']);
    var now = new Date();
    var id = String(p.id || '').replace(/[^0-9a-f]/gi, '').slice(0, 32);
    var rows = sh.getLastRow() > 1 ? sh.getRange(2, 1, sh.getLastRow() - 1, 5).getValues() : [];
    if (id && p.e === 'open') {
      var at = -1;
      for (var i = 0; i < rows.length; i++) if (rows[i][0] === id) { at = i; break; }
      if (at < 0) {
        sh.appendRow([id, now, now, String(p.v || '').slice(0, 20), 1]);
        rows.push([id, now, now, p.v, 1]);
      } else {
        sh.getRange(at + 2, 3, 1, 3).setValues([[now, String(p.v || '').slice(0, 20), rows[at][4] + 1]]);
        rows[at][2] = now;
      }
    }
    var online = 0, today = 0;
    var day = Utilities.formatDate(now, 'Asia/Bangkok', 'yyyy-MM-dd');
    for (var j = 0; j < rows.length; j++) {
      var last = new Date(rows[j][2]);
      if (now - last < 15 * 60 * 1000) online++;
      if (Utilities.formatDate(last, 'Asia/Bangkok', 'yyyy-MM-dd') === day) today++;
    }
    var out = {online: online, today: today, total: rows.length};
    return ContentService.createTextOutput(JSON.stringify(out))
      .setMimeType(ContentService.MimeType.JSON);
  } finally {
    lock.releaseLock();
  }
}
