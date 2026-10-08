"""Read-only probe: full stem + MS for given qids (no sibling dump)."""
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
             replace(q.stem_text, char(10), ' ')
      FROM question q WHERE q.id=:q"""), {'q': qid}).fetchone()
    if not row:
        print(f'Q {qid} NOT FOUND'); continue
    print(f'===== Q {row[0]} paper={row[1]} parent={row[2]} #{row[3]} {row[4]}mk')
    print('STEM:', row[5])
    for ms in s.execute(text("""
      SELECT number_path, marks, replace(answer_text, char(10), ' | ')
      FROM mark_scheme_entry WHERE question_id=:q ORDER BY id"""), {'q': qid}):
        print(f'MS [{ms[0]}] {ms[1]}mk: {ms[2]}')
    print()
