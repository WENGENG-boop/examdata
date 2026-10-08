"""Show WPH12 questions by taxonomy code (all, not just r2), with stem snippet and r2 flag."""
import sqlite3, sys, json
from pathlib import Path

con = sqlite3.connect('file:.data/examdata.db?mode=ro', uri=True)
c = con.cursor()

r2 = set()
APPLIED = Path('tmp_jev_full_decisions/ial18-physics/applied.jsonl')
for line in open(APPLIED, encoding='utf-8'):
    e = json.loads(line)
    if e.get('status')=='applied' and e.get('decision')=='change':
        r2.add(e['question_id'])

codes = sys.argv[1:]
for code in codes:
    print(f'===== {code} =====')
    rows = c.execute("""
      SELECT q.id, q.number_label, q.marks, d.paper_code, substr(replace(q.stem_text,char(10),' '),1,150)
      FROM question q
      JOIN question_taxonomy qt ON qt.question_id=q.id
      JOIN taxonomy_node tn ON tn.id=qt.node_id
      JOIN paper p ON p.id=q.paper_id
      JOIN document d ON d.id=p.document_id
      WHERE tn.code=? AND d.paper_code LIKE 'wph12%'
      ORDER BY q.id""", (code,)).fetchall()
    for r in rows:
        flag = 'R2' if r[0] in r2 else '  '
        print(f'  {flag} {r[0]} {r[3]} #{r[1]} {r[2]}mk | {r[4]}')
    print(f'  total {len(rows)}')
