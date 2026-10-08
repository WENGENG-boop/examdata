"""Normalized stem search: python q.py <unit-prefix> <substr> [limit]
Normalizes NBSP etc. in both stem and pattern."""
import re, sqlite3, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent.parent
con = sqlite3.connect(f"file:{ROOT / '.data' / 'examdata.db'}?mode=ro", uri=True)
c = con.cursor()
unit = sys.argv[1]; pat = sys.argv[2].lower(); lim = int(sys.argv[3]) if len(sys.argv) > 3 else 40

def norm(s):
    if s is None: return ''
    s = s.replace('\u00a0', ' ').replace('\u2009', ' ').replace('\u202f', ' ')
    return re.sub(r'\s+', ' ', s).strip()

rows = c.execute("""
 select q.id, q.number_path, coalesce(q.marks,'-'),
        (select group_concat(tn.code, ',') from question_taxonomy qt
          join taxonomy_node tn on tn.id=qt.node_id
          where qt.question_id=q.id and tn.code like ?) as codes,
        q.stem_text
 from question q order by q.id""", (f'{unit}%',)).fetchall()
hits = 0
for qid, np_, mk, codes, stem in rows:
    if codes is None: continue
    ns = norm(stem).lower()
    if pat in ns:
        hits += 1
        if hits > lim: break
        print(f"[{qid}] {np_} m={mk} codes={codes} :: {norm(stem)[:170]}")
print(f"total shown: {min(hits,lim)}")
