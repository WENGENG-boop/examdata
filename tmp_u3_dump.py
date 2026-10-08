"""Read-only dump of papers for given qids: paper meta + all questions with labels."""
import sys
from pathlib import Path
from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parent
eng = create_engine(f"sqlite:///{ROOT / '.data' / 'examdata.db'}")
with eng.connect() as c:
    qids = [int(x) for x in sys.argv[1:]]
    rows = c.execute(text(
        f"SELECT id, paper_id FROM question WHERE id IN ({','.join(map(str, qids))})")).fetchall()
    papers = sorted({r[1] for r in rows})
    print('qid->paper:', {r[0]: r[1] for r in rows})
    pcols = [r[1] for r in c.execute(text("PRAGMA table_info(paper)")).fetchall()]
    for pid in papers:
        print(f'\n===== PAPER {pid} =====')
        for r in c.execute(text('SELECT * FROM paper WHERE id=:p'), {'p': pid}):
            d = dict(zip(pcols, r))
            keep = {k: v for k, v in d.items() if v not in (None, '') and k not in ('id',)}
            print('  META:', keep)
        total = 0
        for q in c.execute(text("""
            SELECT q.id, q.number_label, q.parent_id, q.marks,
                   substr(replace(q.stem_text,char(10),' '),1,70),
                   tn.code
            FROM question q
            LEFT JOIN question_taxonomy qt ON qt.question_id=q.id
            LEFT JOIN taxonomy_node tn ON tn.id=qt.node_id
            WHERE q.paper_id=:p ORDER BY q.display_order"""), {'p': pid}):
            m = q[3] or 0
            try:
                m = int(m)
            except Exception:
                m = 0
            if q[2] is None:
                total += m
            print(f'  {q[0]} #{q[1]} par={q[2]} {q[3]}mk [{q[5] or "-"}] {q[4]}')
        print(f'  TOP-LEVEL MARKS TOTAL = {total}')
