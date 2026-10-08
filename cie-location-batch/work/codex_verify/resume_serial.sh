#!/usr/bin/env bash
# Wait until 21:16 local (codex quota reset ~21:15), then resume the serial
# codex vision worker over the remaining volume keys (5 volumes + 9396).
# Idempotent: run_batches.py skips batches whose result JSON is already valid.
# Stop conditions: rc=4 (quota) -> wait 15 min, retry once; otherwise exit.
# Cancel: create file resume_serial.stop next to this script.
set -u
cd "$(dirname "$0")" || exit 9
STOP_FILE="resume_serial.stop"
KEYS=(0413/2026/Jun/11 0509/2026/Jun/11 8386/2026/Jun/11 9709/2024/Jun/11 9715/2023/Nov/21 9396/2023/Nov/11)

TARGET=$(date -d 'today 21:16' +%s)
NOW=$(date +%s)
if [ "$NOW" -lt "$TARGET" ]; then
  SLEEP=$((TARGET - NOW))
  echo "resume_serial: waiting ${SLEEP}s until $(date -d @"$TARGET" '+%H:%M:%S') (now $(date '+%H:%M:%S'))"
  sleep "$SLEEP"
fi
if [ -e "$STOP_FILE" ]; then echo "resume_serial: stop file present; exit"; exit 0; fi

echo "resume_serial: start $(date '+%F %T') keys=${KEYS[*]}"
bash run_worker.sh "${KEYS[@]}"
rc=$?
echo "resume_serial: run_worker rc=$rc $(date '+%F %T')"
if [ $rc -eq 4 ]; then
  echo "resume_serial: quota still exhausted; retry once after 15 min"
  sleep 900
  if [ -e "$STOP_FILE" ]; then echo "resume_serial: stop file present; exit"; exit 0; fi
  bash run_worker.sh "${KEYS[@]}"
  rc=$?
  echo "resume_serial: retry rc=$rc $(date '+%F %T')"
fi
echo "resume_serial: done rc=$rc"
exit $rc
