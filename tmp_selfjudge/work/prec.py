"""Precedent search: find DB questions by stem substring, show their labels.

usage: python prec.py <unit> <substr> [limit]
"""
import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
con = sqlite3.connect(f"file:{ROOT / '.data' / 'examdata.db'}?mode=ro", uri=True)
c = con.cursor()
WS = re.compile(r"\s+")

unit = sys.argv[1]
pat = sys.argv[2]
lim = int(sys.argv[3]) if len(sys.argv) > 3 else 40

rows = c.execute(
    """select q.id, q.number_path, coalesce(q.marks,'-'), group_concat(tn.code, ','),
              substr(replace(replace(q.stem_text, char(10), ' '), char(160), ' '), 1, 150)
       from question q
       left join question_taxonomy qt on qt.question_id = q.id
       left join taxonomy_node tn on tn.id = qt.node_id
       where q.stem_text like ? and tn.code like ?
       group by q.id
       order by q.id limit ?""",
    (f'%{pat}%', f'{unit}%', lim)).fetchall()
print(f"[{unit}] find '{pat}': {len(rows)} rows")
for r in rows:
    print(f"[{r[0]}] {r[1]} m={r[2]} codes={r[3]} :: {WS.sub(' ', r[4])}")
