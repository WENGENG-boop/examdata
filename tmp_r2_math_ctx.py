"""Read-only trimmed context: stem, parent, MS, same-parent siblings (labels) for r2 math review.

usage: python tmp_r2_math_ctx.py 37344 37153 ...
"""
import os
import sqlite3
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
db = (ROOT / '.data' / 'examdata.db').as_posix()

_tmpdir = Path(os.environ.get('LOCALAPPDATA', r'C:\Users\weo\AppData\Local')) / 'Temp'
if _tmpdir.is_dir():
    os.environ['TMP'] = os.environ['TEMP'] = str(_tmpdir)


def open_db():
    last = None
    for _ in range(8):
        try:
            con = sqlite3.connect(f'file:{db}?mode=ro', uri=True)
            con.execute('pragma temp_store = memory')
            con.execute('select 1').fetchone()
            return con
        except sqlite3.OperationalError as e:
            last = e
            time.sleep(2)
    raise last


def q1(sql, params=()):
    last = None
    for _ in range(8):
        try:
            return open_db().execute(sql, params).fetchall()
        except sqlite3.OperationalError as e:
            last = e
            time.sleep(2)
    raise last


def clean(t, n):
    return ' '.join((t or '').split())[:n]


for qid in [int(x) for x in sys.argv[1:]]:
    row = q1("""select q.id, q.paper_id, q.parent_id, q.number_label, q.marks, q.stem_text
                       from question q where q.id=?""", (qid,))
    row = row[0] if row else None
    if not row:
        print(f'Q {qid} NOT FOUND')
        continue
    q_id, pid, par, num, marks, stem = row
    print(f'===== Q {qid} paper={pid} parent={par} #{num} {marks}mk')
    print(f'STEM: {clean(stem, 700)}')
    if par:
        prow = q1('select id, number_label, stem_text from question where id=?', (par,))
        if prow:
            prow = prow[0]
            print(f'PARENT {prow[0]} #{prow[1]}: {clean(prow[2], 300)}')
        sibs = q1("""select q.id, q.number_label, coalesce(tn.code,'-')
                            from question q
                            left join question_taxonomy qt on qt.question_id=q.id
                            left join taxonomy_node tn on tn.id=qt.node_id
                            where q.paper_id=? and q.parent_id=? order by q.display_order""",
                  (pid, par))
        print('SAME-PARENT: ' + ', '.join(f'{s[0]}#{s[1]}[{s[2]}]' for s in sibs))
    for ms in q1("""select number_path, marks, answer_text from mark_scheme_entry
                           where question_id=? order by id limit 4""", (qid,)):
        print(f'MS [{ms[0]}] {ms[1]}mk: {clean(ms[2], 600)}')
    print()
