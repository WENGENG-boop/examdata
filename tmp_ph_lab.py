import sys
from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
ROOT = Path(__file__).resolve().parent
eng = create_engine(f"sqlite:///{ROOT / '.data' / 'examdata.db'}")
s = Session(eng)
for qid in [int(x) for x in sys.argv[1:]]:
    r = s.execute(text("""SELECT q.id, q.number_label, q.marks, tn.code,
        substr(replace(q.stem_text,char(10),' '),1,110)
        FROM question q LEFT JOIN question_taxonomy qt ON qt.question_id=q.id
        LEFT JOIN taxonomy_node tn ON tn.id=qt.node_id WHERE q.id=:q"""), {'q':qid}).fetchone()
    if r: print(f'{r[0]} #{r[1]} {r[2]}mk [{r[3] or "-"}] {r[4]}')
    else: print(f'{qid} NOT FOUND')
