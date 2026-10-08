#!/bin/bash
set -u
cd /c/Users/weo/Desktop/api/cie-location-batch
PY=../examdata/.venv/Scripts/python.exe
OUT=work/coordinate-audit-2026-10-05/deliverables/prep-log-round2.json
LOG=work/coordinate-audit-2026-10-05/_rerender12.log
: > "$LOG"
echo '{"scale":"2","entries":[' > "$OUT"
first=1
for k in '8386/2024/Jun/13' '8386/2024/Jun/11' '8386/2024/Jun/12' '8386/2025/Nov/12' '8386/2025/Jun/12' '8386/2025/Jun/13' '8386/2025/Nov/11' '8386/2025/Nov/13' '8386/2024/Nov/11' '8386/2024/Nov/13' '8386/2024/Nov/12' '0472/2026/Jun/42'; do
  echo "=== $k render ===" >> "$LOG"
  PYTHONIOENCODING=utf-8 "$PY" work/coordinate-audit-2026-10-05/render_regions.py "$k" 2 >> "$LOG" 2>&1
  rc1=$?
  echo "=== $k slices ===" >> "$LOG"
  PYTHONIOENCODING=utf-8 "$PY" work/coordinate-audit-2026-10-05/make_review_slices.py "$k" --cap 80 >> "$LOG" 2>&1
  rc2=$?
  echo "$k render=$rc1 slices=$rc2" 
done
echo ']}' >> "$OUT"
echo DONE
