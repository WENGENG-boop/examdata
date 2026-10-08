"""Dump all rows of a paper, or search eval stems (accounting self-judgment helper)."""
import sys
from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parent
eng = create_engine(f"sqlite:///{ROOT / '.data' / 'examdata.db'}")
s = Session(eng)


def label_of(qid):
    r = s.execute(text("""
      SELECT tn.code FROM question_taxonomy qt JOIN taxonomy_node tn ON tn.id=qt.node_id
      WHERE qt.question_id=:q"""), {'q': qid}).fetchone()
    return r[0] if r else '-'


def brief(t, n=120):
    if not t:
        return ''
    t = ' '.join(t.replace('\n', ' ').split())
    return t[:n]


mode = sys.argv[1]
if mode == 'paper':
    for pid in [int(x) for x in sys.argv[2:]]:
        print(f'===== paper {pid} =====')
        rows = s.execute(text("""
          SELECT q.id, q.number_path, q.marks, q.depth, q.parent_id, substr(q.stem_text,1,170)
          FROM question q WHERE q.paper_id=:p ORDER BY q.display_order"""), {'p': pid}).fetchall()
        for r in rows:
            print(f'{r[0]} #{r[1]} {r[2]}mk d={r[3]} par={r[4]} [{label_of(r[0])}] {brief(r[5])}')
elif mode == 'row':
    for qid in [int(x) for x in sys.argv[2:]]:
        r = s.execute(text("""
          SELECT q.id, q.paper_id, q.number_path, q.number_label, q.marks, q.depth, q.parent_id,
                 q.display_order, q.stem_text
          FROM question q WHERE q.id=:q"""), {'q': qid}).fetchone()
        if not r:
            print(f'Q {qid} NOT FOUND')
            continue
        print(f'== {r[0]} p{r[1]} #{r[2]} label={r[3]!r} {r[4]}mk d={r[5]} par={r[6]} order={r[7]} [{label_of(r[0])}]')
        print(f'   stem: {brief(r[8], 800)}')
        for ms in s.execute(text("""
          SELECT number_path, substr(replace(coalesce(answer_text,''),char(10),' | '),1,600)
          FROM mark_scheme_entry WHERE question_id=:q ORDER BY id"""), {'q': qid}):
            print(f'   MS[{ms[0]}]: {brief(ms[1], 600)}')
        print()
elif mode == 'eval':
    for term in sys.argv[2:]:
        rows = s.execute(text("""
          SELECT q.id, q.paper_id, q.number_path, q.marks, substr(q.stem_text,1,220)
          FROM question q WHERE q.stem_text LIKE :t ORDER BY q.paper_id, q.display_order LIMIT 120"""),
          {'t': f'%{term}%'}).fetchall()
        print(f'===== search {term!r}: {len(rows)} rows (cap 120) =====')
        for r in rows:
            print(f'{r[0]} p{r[1]} #{r[2]} {r[3]}mk [{label_of(r[0])}] {brief(r[4], 150)}')
