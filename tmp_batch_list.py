"""List batch rows (from a SELFJUDGE pack) with paper/question context."""
import glob
import re
import sys
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent
c = sqlite3.connect(str(ROOT / '.data' / 'examdata.db'))
c.row_factory = sqlite3.Row

unit = sys.argv[1]
f = ROOT / 'tmp_selfjudge' / 'unt' / 'ial18-mathematics' / f'{unit}-p01.txt'
qids = []
for ln in open(f, encoding='utf-8'):
    m = re.match(r'\[(\d+)\]\s+(\d+)\s', ln)
    if m:
        qids.append(int(m.group(2)))

print(f'# {unit}: {len(qids)} rows')
for qid in qids:
    r = c.execute("""
      SELECT q.id, q.paper_id, p.paper_no, d.year, q.number_label, q.marks, q.page_from, q.page_to,
             q.parent_id, tn.code, substr(replace(q.stem_text,char(10),' '),1,160) st
      FROM question q JOIN paper p ON p.id=q.paper_id JOIN document d ON d.id=p.document_id
      LEFT JOIN question_taxonomy qt ON qt.question_id=q.id
      LEFT JOIN taxonomy_node tn ON tn.id=qt.node_id
      WHERE q.id=?""", (qid,)).fetchone()
    print(f"{r['id']} p{r['paper_id']} {r['paper_no']}/{r['year']} #{r['number_label']} "
          f"{r['marks']}mk pg{r['page_from']}-{r['page_to']} par={r['parent_id']} [{r['code'] or '-'}]")
    print(f"    {r['st']}")
