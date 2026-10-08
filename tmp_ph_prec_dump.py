import sys
from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
ROOT = Path(__file__).resolve().parent
eng = create_engine(f"sqlite:///{ROOT / '.data' / 'examdata.db'}")
s = Session(eng)
for unit in ['WPH11','WPH12','WPH13','WPH14','WPH15','WPH16']:
    rows = s.execute(text("""
      SELECT q.id, tn.code, q.marks, substr(replace(q.stem_text,char(10),' '),1,400)
      FROM question q
      JOIN question_taxonomy qt ON qt.question_id=q.id
      JOIN taxonomy_node tn ON tn.id=qt.node_id
      WHERE tn.code LIKE :u
      ORDER BY tn.code, q.id
    """), {'u': unit+'%'}).fetchall()
    with open(f'tmp_ph_prec_{unit}.txt','w',encoding='utf-8') as f:
        cur=None
        for qid, code, marks, stem in rows:
            if code!=cur:
                cur=code; f.write(f'\n## {code}\n')
            f.write(f'  {qid} {marks}mk | {stem}\n')
    print(unit, len(rows))
