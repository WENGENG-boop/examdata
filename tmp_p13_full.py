from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
eng = create_engine("sqlite:///.data/examdata.db")
s = Session(eng)
papers = [1324, 1329, 1334, 1339, 1343, 1347, 1352]
for pid in papers:
    d = s.execute(text("SELECT d.title FROM paper p JOIN document d ON d.id=p.document_id WHERE p.id=:p"), {'p': pid}).fetchone()
    print(f"\n########## paper {pid} | {d[0]}")
    rows = s.execute(text("""
        SELECT q.id, q.parent_id, q.number_label, q.marks, substr(q.stem_text,1,70),
               (SELECT group_concat(tn.code, ',') FROM question_taxonomy qt JOIN taxonomy_node tn ON tn.id=qt.node_id WHERE qt.question_id=q.id)
        FROM question q WHERE q.paper_id=:p ORDER BY q.display_order, q.id"""), {'p': pid}).fetchall()
    for r in rows:
        print(f"  q{r[0]} par={r[1]} {r[2]!r} {r[3]}mk [{r[5]}] | {(r[4] or '').replace(chr(10),' ').strip()[:75]}")
