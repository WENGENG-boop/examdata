import sys
from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
ROOT = Path(__file__).resolve().parent
eng = create_engine(f"sqlite:///{ROOT / '.data' / 'examdata.db'}")
s = Session(eng)
for pid in [int(x) for x in sys.argv[1:]]:
    print(f'===== paper {pid}')
    for sb in s.execute(text("""
      SELECT q.id, q.number_label, q.marks, substr(replace(q.stem_text,char(10),' '),1,72), tn.code
      FROM question q LEFT JOIN question_taxonomy qt ON qt.question_id=q.id
      LEFT JOIN taxonomy_node tn ON tn.id=qt.node_id
      WHERE q.paper_id=:p ORDER BY q.display_order"""), {'p': pid}):
        print(f'  {sb[0]} #{sb[1]} {sb[2]}mk [{sb[4] or "-"}] {sb[3]}')
