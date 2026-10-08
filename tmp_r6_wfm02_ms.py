"""Read-only probe: full MS entries (answer_text/guidance/raw) for given qids."""
import sys
from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parent
eng = create_engine(f"sqlite:///{ROOT / '.data' / 'examdata.db'}")
s = Session(eng)

for qid in [int(x) for x in sys.argv[1:]]:
    row = s.execute(text("""
      SELECT q.id, q.number_label, q.marks FROM question q WHERE q.id=:q"""), {'q': qid}).fetchone()
    print(f'===== Q {qid} #{row[1]} {row[2]}mk')
    for ms in s.execute(text("""
      SELECT number_path, marks, answer_text, guidance, raw
      FROM mark_scheme_entry WHERE question_id=:q ORDER BY id"""), {'q': qid}):
        for name, val in zip(('path', 'marks', 'ans', 'guid', 'raw'), ms):
            if val:
                print(f'  {name}: {str(val)[:1500]}')
        print('  ---')
    print()
