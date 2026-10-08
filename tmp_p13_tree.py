import sys
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
eng = create_engine("sqlite:///.data/examdata.db")
s = Session(eng)
qids = [int(x) for x in open('tmp_p13_qids.txt').read().split()]
rows = s.execute(text("""SELECT q.id, q.paper_id, q.parent_id, q.number_label, q.marks, substr(q.stem_text,1,110), d.title, d.year, d.component, d.variant
FROM question q JOIN paper p ON p.id=q.paper_id JOIN document d ON d.id=p.document_id
WHERE q.id IN (%s)""" % ','.join(map(str,qids)))).fetchall()
bypaper = {}
for r in rows:
    bypaper.setdefault((r[1], r[6], r[7], r[8], r[9]), []).append(r)
for (pid, title, year, comp, var), rs in sorted(bypaper.items()):
    print(f"\n########## paper {pid} | {title}")
    for r in sorted(rs, key=lambda x: (x[4] is None, x[4] or 0, x[0])):
        print(f"  q{r[0]} parent={r[2]} {r[3]!r} {r[4]}mk | {(r[5] or '').strip()[:100]}")
