"""Verify the 22 r5 targets: qid stem + MS ref occurrences (own + parent rows).

Prints one section per item: stem head, current tags, refs found in the
question's own MS rows and its parent's MS rows, plus the dump lines from
tmp_ms_refs_direct.txt mentioning the qid.
"""
import re
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DUMP = ROOT / 'tmp_ms_refs_direct.txt'

TARGETS = [
    (52176, 'WGE01-1.3.6', 'Arctic economic opportunities (1.3.6.3)'),
    (52180, 'WGE01-1.4.2', 'NAFTA trade patterns (1.4.2.2)'),
    (52181, 'WGE01-1.4.2', 'trade bloc advantage (1.4.2.2)'),
    (52182, 'WGE01-1.4.2', 'SEZs (1.4.2.2)'),
    (52266, 'WGE01-1.3.1', 'Philippines cyclone (1.3.1.2)'),
    (52267, 'WGE01-1.3.2', 'Philippines volcano losses (1.3.2.2)'),
    (52269, 'WGE01-1.3.2', 'regional droughts mega-disaster (1.3.2.3)'),
    (52558, 'WGE01-1.3.3', 'monitoring/prediction (1.3.3.3)'),
    (52562, 'WGE01-1.3.5', 'S America sea-level (1.3.5.3)'),
    (52568, 'WGE01-1.4.3', 'Microsoft brand value (1.4.3.1)'),
    (52569, 'WGE01-1.4.3', 'ranking changes (1.4.3.1)'),
    (52570, 'WGE01-1.4.3', 'global consumers/brands (1.4.3.1)'),
    (52571, 'WGE01-1.4.3', 'weakly connected developing (1.4.3.2)'),
    (52583, 'WGE01-1.4.2', 'FDI change (1.4.2.2)'),
    (52671, 'WGE01-1.3.1', 'cyclone track distribution (1.3.1.2)'),
    (52672, 'WGE01-1.3.1', 'cyclone track cause (1.3.1.2)'),
    (52678, 'WGE01-1.3.5', 'China methane trend (1.3.5.1)'),
    (52684, 'WGE01-1.4.2', 'FTZ year (1.4.2.2)'),
    (52685, 'WGE01-1.4.2', 'FTZ 2015 distribution (1.4.2.2)'),
    (52697, 'WGE01-1.3.4', 'long-term natural climate (1.3.4.2)'),
    (52567, 'WGE01-1.4.3', 'parent of 52568-52571 (all -> 1.4.3)'),
    (52683, 'WGE01-1.4.2', 'parent of 52684/52685 (-> 1.4.2)'),
]

dump_lines = DUMP.read_text(encoding='utf-8').splitlines()

con = sqlite3.connect(f'file:{ROOT / ".data" / "examdata.db"}?mode=ro', uri=True)
con.row_factory = sqlite3.Row
cur = con.cursor()

REF_RE = re.compile(r'\((\d+\.\d+\.\d+(?:\.\d+)?)\)')


def show_refs(rows, label):
    n = 0
    for r in rows:
        for col in ('answer_text', 'guidance'):
            txt = r[col] or ''
            for m in REF_RE.finditer(txt):
                n += 1
                a = max(0, m.start() - 100)
                b = min(len(txt), m.end() + 80)
                seg = txt[a:b].replace('\n', ' ')
                print(f'    {label} MS#{r["id"]} [{r["number_label"]}] {col} ({m.group(1)}) :: ...{seg}...')
    return n


for qid, target, hint in TARGETS:
    q = cur.execute(
        'select id, paper_id, number_label, parent_id, marks, stem_text '
        'from question where id=?', (qid,)).fetchone()
    if not q:
        print(f'==== {qid}: NOT FOUND ====')
        continue
    tags = cur.execute(
        'select group_concat(n.code) c from question_taxonomy t '
        'join taxonomy_node n on n.id=t.node_id where t.question_id=?',
        (qid,)).fetchone()['c']
    print('=' * 100)
    print(f'{qid} #{q["number_label"]} paper={q["paper_id"]} par={q["parent_id"]} '
          f'{q["marks"]}mk target={target} cur={tags}')
    print(f'  HINT: {hint}')
    print(f'  STEM: {(q["stem_text"] or "")[:280].replace(chr(10), " ")}')
    own = cur.execute(
        'select id, number_label, answer_text, guidance from mark_scheme_entry '
        'where question_id=? order by id', (qid,)).fetchall()
    n = show_refs(own, 'own')
    if q['parent_id']:
        par = cur.execute(
            'select id, number_label, answer_text, guidance from mark_scheme_entry '
            'where question_id=? order by id', (q['parent_id'],)).fetchall()
        n += show_refs(par, f'par{q["parent_id"]}')
    if not n:
        print('    (no refs in own/parent MS rows)')
    kids = cur.execute(
        'select q.id, q.number_label, q.marks, '
        ' (select group_concat(n.code) from question_taxonomy t '
        '  join taxonomy_node n on n.id=t.node_id where t.question_id=q.id) codes, '
        ' substr(q.stem_text,1,90) s '
        'from question q where q.parent_id=? order by q.display_order, q.id', (qid,)).fetchall()
    if kids:
        print(f'  CHILDREN of {qid}:')
        for k in kids:
            print(f'    {k["id"]} {k["number_label"]!r} {k["marks"]}mk [{k["codes"] or "-"}] '
                  f'{(k["s"] or "")[:80]!r}')
    for i, ln in enumerate(dump_lines):
        if f'q={qid} ' in ln:
            print(f'  DUMP[{i + 1}]: {ln.strip()}')
            if i + 1 < len(dump_lines) and dump_lines[i + 1].startswith('     '):
                print(f'           {dump_lines[i + 1].strip()[:220]}')

con.close()
