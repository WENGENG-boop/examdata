"""r2 calibration probe: full taxonomy text + usage patterns.

usage: python tmp_r2tax2.py full <code> [<code> ...]
       python tmp_r2tax2.py find <substr> [limit]
       python tmp_r2tax2.py bycode <code> [limit]
"""
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
con = sqlite3.connect(f"file:{ROOT / '.data' / 'examdata.db'}?mode=ro", uri=True)
c = con.cursor()

mode = sys.argv[1]
if mode == 'full':
    for code in sys.argv[2:]:
        r = c.execute("select code, name, attrs from taxonomy_node where code=?", (code,)).fetchone()
        if not r:
            print(f"\n### {code} NOT FOUND")
            continue
        print(f"\n### {r[0]}\nNAME: {r[1]}")
        a = json.loads(r[2] or '{}')
        print("TEXT:", a.get('text'))
elif mode == 'find':
    pat = sys.argv[2]
    lim = int(sys.argv[3]) if len(sys.argv) > 3 else 60
    rows = c.execute("""select q.id, q.number_path, tn.code, substr(replace(replace(q.stem_text, char(10), ' '), char(160), ' '), 1, 150)
                        from question q
                        join question_taxonomy qt on qt.question_id = q.id
                        join taxonomy_node tn on tn.id = qt.node_id
                        where tn.code like 'WCH12%' and replace(q.stem_text, char(160), ' ') like ?
                        order by q.id limit ?""", (f'%{pat}%', lim)).fetchall()
    print(f"find '{pat}': {len(rows)} rows (limit {lim})")
    for r in rows:
        print(f"[{r[0]}] {r[1]} {r[2]} :: {r[3]}")
elif mode == 'bycode':
    code = sys.argv[2]
    lim = int(sys.argv[3]) if len(sys.argv) > 3 else 100
    rows = c.execute("""select q.id, q.number_path, substr(replace(replace(q.stem_text, char(10), ' '), char(160), ' '), 1, 130)
                        from question q
                        join question_taxonomy qt on qt.question_id = q.id
                        join taxonomy_node tn on tn.id = qt.node_id
                        where tn.code = ? order by q.id limit ?""", (code, lim)).fetchall()
    print(f"bycode {code}: {len(rows)} rows")
    for r in rows:
        print(f"[{r[0]}] {r[1]} :: {r[2]}")
