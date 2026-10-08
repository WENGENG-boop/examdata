"""Dump context for biology pending questions: q, parent, MS, sibling labels."""
import sys
from pathlib import Path
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parent
eng = create_engine(f"sqlite:///{ROOT / '.data' / 'examdata.db'}")
s = Session(eng)

qids = [int(x) for x in sys.argv[1:]]
for qid in qids:
    row = s.execute(text("""
      SELECT q.id, q.paper_id, q.parent_id, q.number_label, q.marks,
             substr(replace(q.stem_text,char(10),' '),1,500)
      FROM question q WHERE q.id=:q"""), {'q': qid}).fetchone()
    if not row:
        print(f'Q {qid} NOT FOUND'); continue
    q_id, pid, par, num, marks, stem = row
    print(f'===== Q {qid} paper_id={pid} parent={par} #{num} {marks}mk')
    print(f'STEM: {stem}')
    if par:
        prow = s.execute(text("""
          SELECT q.id, q.number_label, q.marks,
                 substr(replace(q.stem_text,char(10),' '),1,600)
          FROM question q WHERE q.id=:q"""), {'q': par}).fetchone()
        if prow:
            print(f'PARENT {prow[0]} #{prow[1]} {prow[2]}mk: {prow[3]}')
    for ms in s.execute(text("""
      SELECT number_path, marks, substr(replace(answer_text,char(10),' | '),1,500)
      FROM mark_scheme_entry WHERE question_id=:q ORDER BY id"""), {'q': qid}):
        print(f'MS [{ms[0]}] {ms[1]}mk: {ms[2]}')
    print('--- sibling labels ---')
    for sb in s.execute(text("""
      SELECT q.id, q.number_label, q.marks,
             substr(replace(q.stem_text,char(10),' '),1,70),
             tn.code
      FROM question q
      LEFT JOIN question_taxonomy qt ON qt.question_id=q.id
      LEFT JOIN taxonomy_node tn ON tn.id=qt.node_id
      WHERE q.paper_id=:p ORDER BY q.display_order"""), {'p': pid}):
        print(f'  sib {sb[0]} #{sb[1]} {sb[2]}mk [{sb[4] or "-"}] {sb[3]}')
    print()
