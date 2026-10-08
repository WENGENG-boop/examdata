"""Dump ALL WME02-labeled questions with normalized stems, one line each."""
import re
import sqlite3
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / 'wme02_listing.txt'
BOILER = re.compile(r'(leave blank|question \d+ continued|do not write|total \d+ marks|turn over|_+)')


def norm(t):
    t = (t or '').lower()
    t = BOILER.sub(' ', t)
    t = re.sub(r'[^a-z0-9]+', ' ', t)
    return ' '.join(t.split())


def q(sql, args=()):
    last = None
    for i in range(60):
        try:
            con = sqlite3.connect(f'file:{ROOT / ".data" / "examdata.db"}?mode=ro',
                                  uri=True, timeout=30)
            try:
                return con.execute(sql, args).fetchall()
            finally:
                con.close()
        except sqlite3.OperationalError as e:
            last = e
            time.sleep(6)
    raise SystemExit(f'db fail {last}')


rows = q('''select tn.code, q.id, q.parent_id, q.number_label, q.marks, q.stem_text
  from question q
  join question_taxonomy qt on qt.question_id = q.id
  join taxonomy_node tn on tn.id = qt.node_id
  where tn.code like 'WME02-%'
  order by tn.code, q.id''')
with open(OUT, 'w', encoding='utf-8') as log:
    cur = None
    for code, qid, par, num, marks, stem in rows:
        if code != cur:
            cur = code
            log.write(f'##### {code}\n')
        log.write(f'{qid} p={par} #{num} {marks}mk | {norm(stem)[:150]}\n')
print('rows:', len(rows), '->', OUT)
