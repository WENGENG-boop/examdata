"""Compact context dump for accounting self-judgment (qid, parent chain, MS, same-question siblings)."""
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


def top_ancestor(qid):
    cur = qid
    for _ in range(6):
        r = s.execute(text("SELECT parent_id FROM question WHERE id=:q"), {'q': cur}).fetchone()
        if not r or r[0] is None:
            return cur
        cur = r[0]
    return cur


def brief(t, n=110):
    if not t:
        return ''
    t = ' '.join(t.replace('\n', ' ').split())
    return t[:n]


for qid in [int(x) for x in sys.argv[1:]]:
    row = s.execute(text("""
      SELECT q.id, q.paper_id, q.parent_id, q.number_path, q.number_label, q.marks,
             q.depth, substr(q.stem_text,1,700), d.title
      FROM question q JOIN paper p ON p.id=q.paper_id JOIN document d ON d.id=p.document_id
      WHERE q.id=:q"""), {'q': qid}).fetchone()
    if not row:
        print(f'Q {qid} NOT FOUND')
        continue
    q_id, pid, par, npath, nlab, marks, depth, stem, doctitle = row
    print(f'## {qid} #{npath} {marks}mk depth={depth} paper={pid} [{doctitle[:40]}] self={label_of(qid)}')
    print(f'   stem: {brief(stem, 300)}')
    if par:
        pr = s.execute(text("SELECT number_path, marks, substr(stem_text,1,300) FROM question WHERE id=:q"), {'q': par}).fetchone()
        if pr:
            print(f'   parent {par} #{pr[0]} {pr[1]}mk [{label_of(par)}]: {brief(pr[2], 220)}')
    for ms in s.execute(text("""
      SELECT number_path, substr(replace(coalesce(answer_text,''),char(10),' | '),1,320)
      FROM mark_scheme_entry WHERE question_id=:q ORDER BY id"""), {'q': qid}):
        print(f'   MS[{ms[0]}]: {brief(ms[1], 320)}')
    top = top_ancestor(qid)
    rows = s.execute(text("""
      SELECT q.id, q.number_path, q.marks, substr(q.stem_text,1,200)
      FROM question q WHERE q.id=:t OR q.parent_id=:t OR q.parent_id IN (SELECT id FROM question WHERE parent_id=:t)
      ORDER BY q.display_order"""), {'t': top}).fetchall()
    for r in rows:
        if r[0] == qid:
            continue
        print(f'   sib {r[0]} #{r[1]} {r[2]}mk [{label_of(r[0])}]: {brief(r[3], 95)}')
    print()
