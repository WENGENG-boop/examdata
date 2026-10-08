import sqlite3, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
con = sqlite3.connect(f"file:{ROOT / '.data' / 'examdata.db'}?mode=ro", uri=True)
c = con.cursor()
for qid in [int(x) for x in sys.argv[1:]]:
    rows = c.execute("""select tn.code, qt.source, qt.assigned_by, qt.confidence, qt.reviewed
        from question_taxonomy qt join taxonomy_node tn on tn.id=qt.node_id
        where qt.question_id=?""", (qid,)).fetchall()
    print(qid, rows)
