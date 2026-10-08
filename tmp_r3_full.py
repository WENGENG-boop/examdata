"""Full context dump for r3 accounting review: full stem, parent full stem, MS entries (up to 900 chars each).

Usage: ./.venv/Scripts/python.exe -X utf8 tmp_r3_full.py 12345 23456 ...
"""
import sys
from pathlib import Path
from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parent
eng = create_engine(f"sqlite:///{ROOT / '.data' / 'examdata.db'}")

with eng.connect() as c:
    for qid in [int(x) for x in sys.argv[1:]]:
        row = c.execute(text("""
            SELECT q.id, q.paper_id, q.parent_id, q.number_label, q.marks,
                   replace(q.stem_text,char(10),' | ')
            FROM question q WHERE q.id=:q"""), {'q': qid}).fetchone()
        if not row:
            print(f'== Q {qid} NOT FOUND')
            continue
        q_id, pid, par, num, marks, stem = row
        print(f'== Q {q_id} paper={pid} parent={par} #{num} {marks}mk')
        print(f'   STEM: {stem[:1100]}')
        if par:
            pr = c.execute(text("""
                SELECT q.id, q.number_label, q.marks, replace(q.stem_text,char(10),' | ')
                FROM question q WHERE q.id=:q"""), {'q': par}).fetchone()
            if pr:
                print(f'   PARENT {pr[0]} #{pr[1]} {pr[2]}mk: {pr[3][:600]}')
        for ms in c.execute(text("""
                SELECT number_path, marks, replace(answer_text,char(10),' | ')
                FROM mark_scheme_entry WHERE question_id=:q ORDER BY id"""), {'q': qid}):
            print(f'   MS [{ms[0]}] {ms[1]}mk: {ms[2][:900]}')
        print()
