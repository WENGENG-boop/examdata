"""Full (untruncated) MS dump for qids and their direct children.

usage: python tmp_p3dump.py qid1 qid2 ...
"""
import sys
from pathlib import Path

from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parent
eng = create_engine(f"sqlite:///{ROOT / '.data' / 'examdata.db'}")

qids = [int(a) for a in sys.argv[1:] if a.isdigit()]

with eng.connect() as c:
    for qid in qids:
        rows = c.execute(text(
            "SELECT id, number_label, parent_id, marks, replace(stem_text,char(10),' ') "
            "FROM question WHERE id=:q OR parent_id=:q ORDER BY id"), {'q': qid}).fetchall()
        print(f'===== {qid} =====')
        for r in rows:
            print(f'Q {r[0]} lbl={r[1]} parent={r[2]} mk={r[3]}')
            print(f'  STEM: {r[4][:700]}')
        ids = ','.join(str(r[0]) for r in rows)
        ms = c.execute(text(
            f"SELECT question_id, number_path, marks, replace(answer_text,char(10),' | ') "
            f"FROM mark_scheme_entry WHERE question_id IN ({ids}) ORDER BY id")).fetchall()
        for m in ms:
            print(f'MS {m[0]} [{m[1]}] {m[2]}mk: {m[3]}')
