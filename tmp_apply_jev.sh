#!/bin/bash
# Apply Jev-generated decisions for the 6 remaining subjects, per-file.
# Usage: bash tmp_apply_jev.sh --dry-run|--write
set -u
cd /c/Users/weo/Desktop/api/examdata
PY=./.venv/Scripts/python.exe
MODE=${1:---dry-run}
TAG=${MODE#--}
OUTDIR=tmp_ra_logs
mkdir -p "$OUTDIR"

apply_one() {
  local slug=$1 batch=$2
  local dec=.data/tagging/review-export/$slug/decisions/batch-$batch.jsonl
  local out=$OUTDIR/${TAG}_${slug}-${batch}.json
  if $PY -X utf8 -m examdata.tagging review-apply --subject "$slug" --decisions "$dec" $MODE --json > "$out" 2> "$OUTDIR/${TAG}_err_${slug}-${batch}.txt"; then
    echo "OK  $slug/$batch"
  else
    echo "FAIL $slug/$batch (see $OUTDIR/${TAG}_err_${slug}-${batch}.txt)"
  fi
}

for b in 003; do apply_one ial-spanish "$b"; done
for b in $(seq -f '%03g' 3 13); do apply_one ial18-biology "$b"; done
for b in $(seq -f '%03g' 1 9); do apply_one ial18-chemistry "$b"; done
for b in $(seq -f '%03g' 1 11); do apply_one ial18-economics "$b"; done
for b in $(seq -f '%03g' 1 10); do apply_one ial18-physics "$b"; done
for b in $(seq -f '%03g' 2 62); do [ "$b" = "038" ] && continue; apply_one ial18-mathematics "$b"; done
echo "ALL DONE mode=$MODE"
