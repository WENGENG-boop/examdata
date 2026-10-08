"""WME03 evidence: label distribution + per-label stem examples + keyword scan.

usage: python wme03_ev.py [keyword1 keyword2 ...]
"""
import re
import sqlite3
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
con = sqlite3.connect(f"file:{ROOT / '.data' / 'examdata.db'}?mode=ro", uri=True)
c = con.cursor()


def norm(t):
    t = (t or "").lower()
    t = re.sub(r"\s+", " ", t)
    return t.strip()


rows = c.execute("""
    select tn.code, count(*) from question q
    join question_taxonomy qt on qt.question_id = q.id
    join taxonomy_node tn on tn.id = qt.node_id
    where tn.code like 'WME03-%' group by tn.code order by tn.code
""").fetchall()
print("== label distribution ==")
for code, n in rows:
    print(f"  {code}: {n}")

print()
for code, _ in rows:
    print(f"== {code} examples ==")
    for qid, num, par, stem in c.execute("""
        select q.id, q.number_label, q.parent_id, q.stem_text from question q
        join question_taxonomy qt on qt.question_id = q.id
        join taxonomy_node tn on tn.id = qt.node_id
        where tn.code = ? order by q.id limit 16
    """, (code,)):
        s = norm(stem)[:140]
        print(f"  {qid} #{num} par={par} | {s}")
    print()

if len(sys.argv) > 1:
    cands = []
    for qid, stem, code in c.execute("""
            select q.id, q.stem_text, tn.code from question q
            join question_taxonomy qt on qt.question_id = q.id
            join taxonomy_node tn on tn.id = qt.node_id
            where tn.code like 'WME03-%' and q.stem_text is not null"""):
        cands.append((qid, norm(stem), code))
    for kw in sys.argv[1:]:
        k = norm(kw)
        hits = [(qid, ns, code) for qid, ns, code in cands if k in ns]
        dist = Counter(h[2] for h in hits)
        print(f"### KEYWORD {kw!r}: {len(hits)} hits; labels: {dict(dist.most_common(10))}")
        for qid, ns, code in hits[:6]:
            print(f"    ex {qid} [{code}] {ns[:110]}")
        print()
