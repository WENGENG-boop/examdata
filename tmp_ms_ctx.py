"""Compact read-only stem+MS dump for self-judge review (no sibling list).

usage: python tmp_ms_ctx.py qid1 qid2 ...
"""
import sys
from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parent
eng = create_engine(f"sqlite:///{ROOT / '.data' / 'examdata.db'}")
s = Session(eng)

for qid in [int(x) for x in sys.argv[1:]]:
    row = s.execute(text("""
      SELECT q.id, q.paper_id, q.parent_id, q.number_label, q.marks,
             substr(replace(q.stem_text,char(10),' '),1,300)
      FROM question q WHERE q.id=:q"""), {'q': qid}).fetchone()
    if not row:
        print(f'Q {qid} NOT FOUND')
        continue
    q_id, pid, par, num, marks, stem = row
    print(f'== {qid} #{num} {marks}mk parent={par}')
    print(f'   {stem}')
    for ms in s.execute(text("""
      SELECT number_path, marks, substr(replace(answer_text,char(10),' | '),1,400)
      FROM mark_scheme_entry WHERE question_id=:q ORDER BY id"""), {'q': qid}):
        print(f'   MS[{ms[0]}] {ms[1]}mk: {ms[2]}')
