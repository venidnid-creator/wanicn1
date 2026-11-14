#!/usr/bin/env bash
# สร้างไฟล์ติดตั้ง RoadWay (.rbz) — ทดสอบก่อน แล้วบีบอัด src/ เป็น dist/RoadWay-<รุ่น>.rbz
set -euo pipefail
cd "$(dirname "$0")"
ver=$(sed -n "s/.*VERSION *= *'\([0-9.]*\)'.*/\1/p" src/roadway.rb)
for f in src/roadway.rb src/roadway/*.rb; do ruby -c "$f" >/dev/null; done
ruby test/test_pure.rb >/dev/null
ruby test/test_smoke.rb >/dev/null
python3 tools/make_icons.py >/dev/null
mkdir -p dist
out="dist/RoadWay-$ver.rbz"
rm -f "$out"
(cd src && zip -qr -X "../$out" roadway.rb roadway)
echo "$out"
unzip -l "$out" | tail -1
