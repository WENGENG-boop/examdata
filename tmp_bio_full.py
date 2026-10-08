"""Dump FULL stem + FULL MS for given qids (no truncation)."""
import sys
from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parent
eng = create_engine(f"sqlite:///{ROOT / '.data' / 'examdata.db'}")
s = Session(eng)

for qid in [int(x) for x in sys.argv[1:]]:
    row = s.execute(text("""
      SELECT q.id, q.paper_id, q.parent_id, q.number_label, q.marks, q.stem_text
      FROM question q WHERE q.id=:q"""), {'q': qid}).fetchone()
    if not row:
        print(f'Q {qid} NOT FOUND'); continue
    q_id, pid, par, num, marks, stem = row
    print(f'===== Q {qid} paper_id={pid} parent={par} #{num} {marks}mk')
    print(f'STEM:\n{stem}\n')
    for ms in s.execute(text("""
      SELECT number_path, marks, answer_text
      FROM mark_scheme_entry WHERE question_id=:q ORDER BY id"""), {'q': qid}):
        print(f'MS [{ms[0]}] {ms[1]}mk:\n{ms[2]}\n')
    print()
