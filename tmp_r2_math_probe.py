"""Read-only probe: list questions of a unit whose stem matches a regex, with current label.

usage: python tmp_r2_math_probe.py WDM11 'cascade|Gantt'
"""
import os
import re
import sqlite3
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
db = (ROOT / '.data' / 'examdata.db').as_posix()

_tmpdir = Path(os.environ.get('LOCALAPPDATA', r'C:\Users\weo\AppData\Local')) / 'Temp'
if _tmpdir.is_dir():
    os.environ['TMP'] = os.environ['TEMP'] = str(_tmpdir)

unit, pattern = sys.argv[1], sys.argv[2]
rx = re.compile(pattern, re.I)
rows = None
last_err = None
for attempt in range(8):
    try:
        con = sqlite3.connect(f'file:{db}?mode=ro', uri=True)
        con.execute('pragma temp_store = memory')
        c = con.cursor()
        rows = c.execute("""
            select q.id, q.number_label, q.marks, replace(q.stem_text, char(10), ' '),
                   group_concat(tn.code, ',')
            from question q
            join paper p on p.id = q.paper_id
            left join question_taxonomy qt on qt.question_id = q.id
            left join taxonomy_node tn on tn.id = qt.node_id
            where p.attrs like ?
            group by q.id
            order by q.paper_id, q.display_order
        """, (f'%{unit}%',)).fetchall()
        break
    except sqlite3.OperationalError as e:
        last_err = e
        time.sleep(2)
if rows is None:
    raise last_err
n = 0
for qid, num, marks, stem, codes in rows:
    if not stem or not rx.search(stem):
        continue
    n += 1
    s = ' '.join(stem.split())
    print(f'{qid} #{num} {marks}mk [{codes or "-"}] {s[:190]}')
print(f'--- {n} matches for {unit} /{pattern}/')
