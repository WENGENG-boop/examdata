"""Compact context dump for r7 accounting batch: stem, parent, MS entries.

usage: ./.venv/Scripts/python.exe -X utf8 tmp_r7_acct_ctx.py QID [QID ...]
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
             substr(replace(q.stem_text,char(10),' '),1,400)
      FROM question q WHERE q.id=:q"""), {'q': qid}).fetchone()
    if not row:
        print(f'Q {qid} NOT FOUND'); continue
    q_id, pid, par, num, marks, stem = row
    print(f'== Q {qid} #{num} {marks}mk parent={par}')
    print(f'  STEM: {stem}')
    if par:
        prow = s.execute(text("""
          SELECT q.id, q.number_label, q.marks,
                 substr(replace(q.stem_text,char(10),' '),1,300)
          FROM question q WHERE q.id=:q"""), {'q': par}).fetchone()
        if prow:
            print(f'  PARENT {prow[0]} #{prow[1]} {prow[2]}mk: {prow[3]}')
    ms = list(s.execute(text("""
      SELECT number_path, marks, substr(replace(answer_text,char(10),' | '),1,300)
      FROM mark_scheme_entry WHERE question_id=:q ORDER BY id"""), {'q': qid}))
    for m in ms:
        print(f'  MS [{m[0]}] {m[1]}mk: {m[2]}')
    if not ms:
        print('  MS: (none)')
