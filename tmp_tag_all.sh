#!/usr/bin/env bash
# Serial tagging for all Edexcel subjects that have questions.
# Usage: bash tmp_tag_all.sh   (run from examdata/, after the big download/split run completes)
set -uo pipefail
cd "$(dirname "$0")"
export PYTHONIOENCODING=utf-8
PY=./.venv/Scripts/python.exe

SUBJECTS=$($PY - <<'EOF'
import sqlite3
db = sqlite3.connect('file:.data/examdata.db?mode=ro', uri=True)
rows = db.execute("""
  select s.slug from subject s where s.qualification_id=4
  and exists (select 1 from paper p join question q on q.paper_id=p.id join document d on d.id=p.document_id where d.subject_id=s.id)
  order by s.slug
""").fetchall()
print(' '.join(r[0] for r in rows))
EOF
)
echo "subjects with questions: $SUBJECTS"
for slug in $SUBJECTS; do
  echo "=== tagging $slug ==="
  $PY -m examdata.tagging assign --subject "$slug" --replace --write --json > "tmp_tag_${slug}.json" 2> "tmp_tag_${slug}.err"
  echo "exit=$? slug=$slug"
done
echo "TAG ALL DONE"
