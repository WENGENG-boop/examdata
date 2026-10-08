"""Compact context dump for r6 WMA13 review: stem + MS + compact sibling codes."""
import sys
from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parent
eng = create_engine(f"sqlite:///{ROOT / '.data' / 'examdata.db'}")
s = Session(eng)

ms_len = 900
_papers_done = set()
if sys.argv[1].startswith('--ms='):
    ms_len = int(sys.argv[1].split('=')[1])
    qids = [int(x) for x in sys.argv[2:]]
else:
    qids = [int(x) for x in sys.argv[1:]]

for qid in qids:
    row = s.execute(text("""
      SELECT q.id, q.paper_id, q.parent_id, q.number_label, q.marks,
             substr(replace(q.stem_text,char(10),' '),1,160)
      FROM question q WHERE q.id=:q"""), {'q': qid}).fetchone()
    if not row:
        print(f'Q {qid} NOT FOUND'); continue
    q_id, pid, par, num, marks, stem = row
    print(f'===== Q {qid} p={pid} par={par} #{num} {marks}mk')
    print(f'STEM: {stem}')
    for ms in s.execute(text("""
      SELECT number_path, marks, substr(replace(answer_text,char(10),' | '),1,:L)
      FROM mark_scheme_entry WHERE question_id=:q ORDER BY id"""), {'q': qid, 'L': ms_len}):
        print(f'MS [{ms[0]}] {ms[1]}mk: {ms[2]}')
    if pid not in _papers_done:
        _papers_done.add(pid)
        codes = s.execute(text("""
          SELECT q.id, q.number_label, tn.code
          FROM question q
          LEFT JOIN question_taxonomy qt ON qt.question_id=q.id
          LEFT JOIN taxonomy_node tn ON tn.id=qt.node_id
          WHERE q.paper_id=:p ORDER BY q.display_order"""), {'p': pid}).fetchall()
        seen = {}
        for c in codes:
            seen.setdefault(c[0], (c[1], set()))[1].add(c[2] or '-')
        print('SIBCODES: ' + ' '.join(f'{k}:{"/".join(sorted(v[1]))}' for k, v in seen.items()))
    print()
