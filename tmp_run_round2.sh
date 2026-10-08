#!/usr/bin/env bash
# Round-2 convergence re-check: export changed questions, re-run Jev, decisions, apply.
# Run after round-1 apply has been written for all subjects.
set -u
cd "C:/Users/weo/Desktop/api/examdata" || exit 1
PY=./.venv/Scripts/python.exe
SLUGS="ial-accounting ial-englang ial-englit ial-french ial-geography ial-german ial-greek ial-history ial-law ial-maths ial-psychology ial-spanish ial18-biology ial18-business ial18-chemistry ial18-economics ial18-it ial18-mathematics ial18-mathematics-extra ial18-physics"

echo "=== r2 export $(date) ==="
$PY -X utf8 tmp_jev_r2_export.py || exit 1

echo "=== r2 jev $(date) ==="
for slug in $SLUGS; do
  if [ -d "tmp_jev_full_batches_r2/$slug/batches" ]; then
    echo "--- $slug start $(date)"
    $PY -X utf8 tmp_jev_batch.py --subject "$slug" \
      --batches-dir "tmp_jev_full_batches_r2/$slug/batches" \
      --out "tmp_jev_full_r2_$slug.jsonl" --skip-problems || echo "FAILED $slug"
    echo "--- $slug done $(date)"
  fi
done

echo "=== r2 decisions $(date) ==="
for slug in $SLUGS; do
  if [ -d "tmp_jev_full_batches_r2/$slug/batches" ]; then
    $PY -X utf8 tmp_jev_full_decisions.py --subject "$slug" --write \
      --batch-root tmp_jev_full_batches_r2 \
      --out-root tmp_jev_full_decisions_r2 \
      --jev-template 'tmp_jev_full_r2_{slug}.jsonl'
  fi
done

echo "=== r2 apply dry-run $(date) ==="
for slug in $SLUGS; do
  if [ -d "tmp_jev_full_batches_r2/$slug/batches" ]; then
    $PY -X utf8 tmp_jev_full_apply.py --subject "$slug" \
      --batch-root tmp_jev_full_batches_r2 \
      --decisions-root tmp_jev_full_decisions_r2
  fi
done

echo "=== round2 pipeline finished $(date) ==="
