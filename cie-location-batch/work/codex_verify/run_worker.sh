#!/usr/bin/env bash
# Codex vision batch worker: runs run_batches.py for one or more volume keys.
# Retries a key on exit 3 (batch FAILED, e.g. transient codex start collision).
# Stops immediately on exit 4 (quota / rate-limit marker).
# Must be launched with the base interpreter's sibling bash (Medium IL),
# never from the uv venv python (Low IL breaks codex arg0 temp dirs).
# Usage: bash run_worker.sh <subject/year/season/paper> [more keys...]
set -u
BASE="C:/Users/weo/AppData/Local/Python/pythoncore-3.14-64/python.exe"
cd "$(dirname "$0")" || exit 9
echo "worker start: $* (pid $$)"
for key in "$@"; do
  rc=1
  for attempt in 1 2 3; do
    PYTHONIOENCODING=utf-8 "$BASE" run_batches.py "$key"
    rc=$?
    if [ $rc -eq 0 ]; then break; fi
    if [ $rc -eq 4 ]; then
      echo "WORKER-STOP quota at $key"
      exit 4
    fi
    echo "attempt $attempt failed for $key (rc=$rc)"
    sleep 15
  done
  if [ $rc -ne 0 ]; then
    echo "WORKER-STOP at $key (rc=$rc)"
    exit $rc
  fi
done
echo "WORKER-ALL-DONE: $*"
