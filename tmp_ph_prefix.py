from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
ROOT = Path(__file__).resolve().parent
eng = create_engine(f"sqlite:///{ROOT / '.data' / 'examdata.db'}")
s = Session(eng)
for r in s.execute(text("""
  SELECT q.id, substr(replace(q.stem_text,char(10),' '),1,120), tn.code
  FROM question q LEFT JOIN question_taxonomy qt ON qt.question_id=q.id
  LEFT JOIN taxonomy_node tn ON tn.id=qt.node_id
  WHERE q.stem_text LIKE '%prefix%' ORDER BY q.id LIMIT 30""")):
    print(r[0], f'[{r[2] or "-"}]', r[1])
