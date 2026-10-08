"""Read-only family dump: for each qid, show the question row, its children (parent_id),
and all MS entries attached to any of them.

usage: python tmp_fam.py qid1 qid2 ...
"""
import sys
from pathlib import Path

from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parent
eng = create_engine(f"sqlite:///{ROOT / '.data' / 'examdata.db'}")

with eng.connect() as c:
    for arg in sys.argv[1:]:
        if not arg.isdigit():
            continue
        qid = int(arg)
        rows = c.execute(text(
            "SELECT id, number_label, parent_id, marks, substr(replace(stem_text,char(10),' '),1,320) "
            "FROM question WHERE id=:q OR parent_id=:q ORDER BY id"), {'q': qid}).fetchall()
        print(f'===== qid {qid} (family {len(rows)})')
        ids = [r[0] for r in rows]
        for r in rows:
            tag = 'P' if r[2] is None else f'c({r[2]})'
            print(f'  {r[0]} [{tag}] {r[1]} {r[3]}mk | {r[4][:240]}')
        qmarks = ",".join(str(i) for i in ids)
        ms = c.execute(text(
            f"SELECT question_id, number_path, substr(replace(answer_text,char(10),' | '),1,320) "
            f"FROM mark_scheme_entry WHERE question_id IN ({qmarks}) ORDER BY id")).fetchall()
        for m in ms:
            print(f'  MS {m[0]} [{m[1]}]: {m[2][:300]}')
