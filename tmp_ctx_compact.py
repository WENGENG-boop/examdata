"""Compact read-only context dump (same data as tmp_bio_ctx.py, smaller output)."""
import sys
from pathlib import Path
from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parent
eng = create_engine(f"sqlite:///{ROOT / '.data' / 'examdata.db'}")

qids = [int(x) for x in sys.argv[1:]]
with eng.connect() as c:
    for qid in qids:
        row = c.execute(text("""
          SELECT q.id, q.paper_id, q.parent_id, q.number_label, q.marks,
                 substr(replace(q.stem_text,char(10),' '),1,220)
          FROM question q WHERE q.id=:q"""), {'q': qid}).fetchone()
        if not row:
            print(f'Q {qid} NOT FOUND')
            continue
        q_id, pid, par, num, marks, stem = row
        own = c.execute(text("""
          SELECT tn.code FROM question_taxonomy qt JOIN taxonomy_node tn ON tn.id=qt.node_id
          WHERE qt.question_id=:q"""), {'q': qid}).fetchall()
        print(f'Q {qid} p={pid} par={par} #{num} {marks}mk cur={",".join(r[0] for r in own) or "-"}')
        print(f'  stem: {stem}')
        if par:
            prow = c.execute(text("""
              SELECT q.id, q.number_label, q.marks, tn.code,
                     substr(replace(q.stem_text,char(10),' '),1,260)
              FROM question q
              LEFT JOIN question_taxonomy qt ON qt.question_id=q.id
              LEFT JOIN taxonomy_node tn ON tn.id=qt.node_id
              WHERE q.id=:q"""), {'q': par}).fetchone()
            if prow:
                print(f'  PARENT {prow[0]} #{prow[1]} {prow[2]}mk [{prow[3] or "-"}]: {prow[4]}')
        for ms in c.execute(text("""
          SELECT number_path, substr(replace(answer_text,char(10),' | '),1,300)
          FROM mark_scheme_entry WHERE question_id=:q ORDER BY id LIMIT 2"""), {'q': qid}):
            print(f'  MS[{ms[0]}]: {ms[1]}')
        # group = contiguous block of same top-level question in this paper
        allq = c.execute(text("""
          SELECT q.id, q.number_label, q.marks,
                 substr(replace(q.stem_text,char(10),' '),1,60), tn.code, q.display_order
          FROM question q
          LEFT JOIN question_taxonomy qt ON qt.question_id=q.id
          LEFT JOIN taxonomy_node tn ON tn.id=qt.node_id
          WHERE q.paper_id=:p ORDER BY q.display_order"""), {'p': pid}).fetchall()
        groups, cur = [], []
        for r in allq:
            if not str(r[1]).startswith('(') and cur:
                groups.append(cur)
                cur = []
            cur.append(r)
        if cur:
            groups.append(cur)
        grp = next((g for g in groups if any(r[0] == qid for r in g)), [])
        for r in grp:
            mark = '>>' if r[0] == qid else '  '
            print(f'  {mark} {r[0]} #{r[1]} [{r[4] or "-"}] {r[3]}')
        print()
