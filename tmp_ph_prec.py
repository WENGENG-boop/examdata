import sys
from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
ROOT = Path(__file__).resolve().parent
eng = create_engine(f"sqlite:///{ROOT / '.data' / 'examdata.db'}")
s = Session(eng)
unit = sys.argv[1]
rows = s.execute(text("""
  SELECT q.id, tn.code, q.marks, substr(replace(q.stem_text,char(10),' '),1,160)
  FROM question q
  JOIN question_taxonomy qt ON qt.question_id=q.id
  JOIN taxonomy_node tn ON tn.id=qt.node_id
  JOIN paper p ON p.id=q.paper_id
  WHERE tn.code LIKE :u
  ORDER BY tn.code, q.id
"""), {'u': unit+'%'}).fetchall()
print(f'{unit}: {len(rows)} tagged questions')
cur=None
for qid, code, marks, stem in rows:
    if code!=cur:
        cur=code; print(f'\n## {code}')
    print(f'  {qid} {marks}mk | {stem}')
