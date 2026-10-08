import sys
from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
ROOT = Path(__file__).resolve().parent
eng = create_engine(f"sqlite:///{ROOT / '.data' / 'examdata.db'}")
s = Session(eng)
for qid in [int(x) for x in sys.argv[1:]]:
    r = s.execute(text("SELECT stem_text FROM question WHERE id=:q"), {'q':qid}).fetchone()
    print(f'===== {qid} STEM:\n{r[0][:1500] if r else "NONE"}\n')
    for i,ms in enumerate(s.execute(text("SELECT number_path, answer_text FROM mark_scheme_entry WHERE question_id=:q ORDER BY id"), {'q':qid})):
        print(f'--- MS{i} [{ms[0]}]:\n{ms[1][:1200]}\n')
