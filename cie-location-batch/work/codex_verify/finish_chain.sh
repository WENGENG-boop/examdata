#!/usr/bin/env bash
# finish_chain.sh — post-batch pipeline for the remaining volumes.
#
# For each key (default: worker order, 9396 excluded — already cleaned): poll
# check_batches.py until the codex batches are complete, then run the local
# chain serially:
#   collect_records -> merge_agent_visual -> HOLD gate (local_visual_verified)
#   -> replace_service_index --apply -> import_index -> cleanup_paper
# Pass keys as arguments to override the default list.
# No codex usage here, so it is safe to run alongside the batch worker.
# Every step's output goes to finish-logs/<slug>.log; the master log is
# finish_chain.log. Stop by creating finish_chain.stop next to this script.
set -u
cd "$(dirname "$0")" || exit 9
PY="C:/Users/weo/AppData/Local/Python/pythoncore-3.14-64/python.exe"
KEYS=(8386/2026/Jun/11 0509/2026/Jun/11 0413/2026/Jun/11 9709/2024/Jun/11 9715/2023/Nov/21)
if [ "$#" -gt 0 ]; then KEYS=("$@"); fi
LOG="finish_chain.log"
LOGDIR="finish-logs"
mkdir -p "$LOGDIR"
DEADLINE=$(( $(date +%s) + 21600 ))

say() { echo "[$(date '+%F %T')] $*" | tee -a "$LOG"; }

say "chain start (pid $$); deadline $(date -d @"$DEADLINE" '+%F %T')"
for key in "${KEYS[@]}"; do
  slug=${key//\//-}
  klog="$LOGDIR/$slug.log"
  stale=0
  while :; do
    if [ -e finish_chain.stop ]; then say "stop file present; exit"; exit 0; fi
    out=$(PYTHONIOENCODING=utf-8 "$PY" check_batches.py "$key" 2>&1); rc=$?
    if [ "$rc" -eq 0 ]; then say "$key batches complete"; break; fi
    if [ "$rc" -eq 4 ]; then say "$key STALE: $out — skipping"; stale=1; break; fi
    if [ "$(date +%s)" -gt "$DEADLINE" ]; then
      say "$key still incomplete at deadline: $out"; exit 0
    fi
    sleep 120
  done
  [ "$stale" -eq 1 ] && continue

  say "$key: collect_records"
  if ! PYTHONIOENCODING=utf-8 "$PY" collect_records.py "$key" >>"$klog" 2>&1; then
    say "$key CHAIN-FAILED at collect (see $klog)"; continue
  fi
  say "$key: merge_agent_visual"
  if ! PYTHONIOENCODING=utf-8 "$PY" ../merge_agent_visual.py "$key" "$slug-records.json" >>"$klog" 2>&1; then
    say "$key CHAIN-FAILED at merge (see $klog)"; continue
  fi
  merge_report="../$slug-agent-merge.json"
  if [ ! -f "$merge_report" ]; then
    say "$key CHAIN-HOLD (merge report missing: $merge_report); skipping replace/import/cleanup"; continue
  fi
  verified=$(PYTHONIOENCODING=utf-8 "$PY" -c "import json,sys;print(json.load(open(sys.argv[1],encoding='utf-8')).get('local_visual_verified'))" "$merge_report" 2>/dev/null)
  if [ "$verified" != "True" ]; then
    say "$key CHAIN-HOLD (local_visual_verified=$verified); skipping replace/import/cleanup"; continue
  fi
  say "$key: replace_service_index --apply"
  if ! PYTHONIOENCODING=utf-8 "$PY" ../../tools/replace_service_index.py "$key" --apply >>"$klog" 2>&1; then
    say "$key CHAIN-FAILED at replace (see $klog)"; continue
  fi
  say "$key: import_index"
  if ! PYTHONIOENCODING=utf-8 "$PY" ../../tools/import_index.py "$key" >>"$klog" 2>&1; then
    say "$key CHAIN-FAILED at import (see $klog)"; continue
  fi
  say "$key: cleanup_paper"
  PYTHONIOENCODING=utf-8 "$PY" ../../tools/cleanup_paper.py "$key" >>"$klog" 2>&1
  rc=$?
  case "$rc" in
    0) say "$key CHAIN-OK cleaned";;
    1) say "$key cleanup REFUSED (conditions); see $klog";;
    2) say "$key cleanup RESIDUAL; see $klog";;
    *) say "$key cleanup rc=$rc; see $klog";;
  esac
done
say "chain done"
