"""Read-only: show all WFM02 questions tagged with given codes, with full tag sets."""
import sys
from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parent
eng = create_engine(f"sqlite:///{ROOT / '.data' / 'examdata.db'}")
s = Session(eng)

codes = sys.argv[1:]
q = """
SELECT q.id, p.id, d.title, q.number_label, q.marks, tn.code, qt.reviewed, qt.source, q.parent_id
FROM question_taxonomy qt
JOIN question q ON q.id = qt.question_id
JOIN paper p ON p.id = q.paper_id
JOIN taxonomy_node tn ON tn.id = qt.node_id
LEFT JOIN document d ON d.id = p.document_id
WHERE tn.code IN ({})
ORDER BY p.id, q.display_order
""".format(','.join("'%s'" % c for c in codes))
rows = list(s.execute(text(q)))
by_paper = {}
for r in rows:
    by_paper.setdefault((r[1], r[2]), []).append(r)

for (pid, title), rs in sorted(by_paper.items()):
    print(f'### paper {pid} {title}')
    for r in rs:
        print(f'   qid={r[0]} #{r[3]} {r[4]}mk tag={r[5]} reviewed={r[6]} src={r[7]} parent={r[8]}')
    print()
