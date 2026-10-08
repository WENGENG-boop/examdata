"""Read-only richer context dump for r3 self-judge: full group + MS + labels.

usage: python tmp_r3_ctx.py <qid> [<qid> ...]
"""
import sys
from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parent
eng = create_engine(f"sqlite:///{ROOT / '.data' / 'examdata.db'}")
s = Session(eng)


def show(qid, ms_limit=1400, stem_limit=1200):
    row = s.execute(text("""
      SELECT q.id, q.paper_id, q.parent_id, q.number_label, q.marks,
             substr(replace(q.stem_text,char(10),' '),1,:sl)
      FROM question q WHERE q.id=:q"""), {'q': qid, 'sl': stem_limit}).fetchone()
    if not row:
        print(f'Q {qid} NOT FOUND')
        return
    q_id, pid, par, num, marks, stem = row
    root = par or q_id
    print(f'===== Q {qid} paper={pid} parent={par} #{num} {marks}mk root={root}')
    print(f'STEM: {stem}')
    print('--- group members ---')
    for g in s.execute(text("""
      SELECT q.id, q.number_label, q.marks, q.display_order,
             substr(replace(q.stem_text,char(10),' '),1,300), tn.code
      FROM question q
      LEFT JOIN question_taxonomy qt ON qt.question_id=q.id
      LEFT JOIN taxonomy_node tn ON tn.id=qt.node_id
      WHERE q.id=:r OR q.parent_id=:r ORDER BY q.display_order"""), {'r': root}):
        print(f'  {g[0]} #{g[1]} {g[2]}mk [{g[5] or "-"}] {g[4]}')
    print('--- mark scheme ---')
    for ms in s.execute(text("""
      SELECT number_path, marks, substr(replace(answer_text,char(10),' | '),1,:ml)
      FROM mark_scheme_entry WHERE question_id=:q ORDER BY id"""), {'q': root, 'ml': ms_limit}):
        print(f'  MS [{ms[0]}] {ms[1]}mk: {ms[2]}')
    print()


for a in sys.argv[1:]:
    show(int(a))
