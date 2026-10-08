"""Build r5 batch for ial-geography WGE01: 22 targeted corrections.

All 22 targets verified against MS refs (tmp_r5_verify.txt + tmp_ms_refs_direct.txt).
Writes tmp_jev_full_batches_r3/ial-geography/batches/batch-001.jsonl and
tmp_r5_targets.json (for post-ingest cross-check).
"""
import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB = ROOT / '.data' / 'examdata.db'
OUT_BATCH = ROOT / 'tmp_jev_full_batches_r3' / 'ial-geography' / 'batches' / 'batch-001.jsonl'
OUT_TARGETS = ROOT / 'tmp_r5_targets.json'

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
    (52567, 'WGE01-1.4.3', 'parent of 52568-52570 (all -> 1.4.3)'),
    (52683, 'WGE01-1.4.2', 'parent of 52684/52685 (-> 1.4.2)'),
]

con = sqlite3.connect(f'file:{DB}?mode=ro', uri=True)
con.row_factory = sqlite3.Row
cur = con.cursor()

rows = []
targets_out = []
print(f'{"qid":>6} {"paper":>10} {"label":>6} {"mk":>4}  {"cur":<12} -> {"target":<12} stem')
for qid, target, note in TARGETS:
    q = cur.execute(
        'select id, paper_id, number_label, parent_id, marks, stem_text from question where id=?',
        (qid,)).fetchone()
    if not q:
        print(f'{qid}: NOT FOUND'); continue
    paper = cur.execute('select paper_no from paper where id=?', (q['paper_id'],)).fetchone()
    paper_code = paper['paper_no'] if paper else None
    tax = cur.execute(
        'select n.code, n.name, t.confidence, t.assigned_by, t.reviewed '
        'from question_taxonomy t join taxonomy_node n on n.id=t.node_id '
        'where t.question_id=? order by n.code', (qid,)).fetchall()
    current = [{'assigned_by': t['assigned_by'], 'code': t['code'], 'confidence': t['confidence'],
                'name': t['name'], 'reviewed': t['reviewed']} for t in tax]
    row = {'current': current, 'number_label': q['number_label'], 'paper_code': paper_code,
           'question_id': qid, 'stem': q['stem_text'], 'unit_code': 'WGE01'}
    rows.append(row)
    targets_out.append({'question_id': qid, 'target': target, 'note': note,
                        'current': [t['code'] for t in tax], 'paper_code': paper_code,
                        'number_label': q['number_label']})
    cur_s = ','.join(t['code'] for t in tax)
    stem_head = (q['stem_text'] or '')[:60].replace('\n', ' ')
    mk = q['marks'] if q['marks'] is not None else '-'
    print(f'{qid:>6} {paper_code:>10} {q["number_label"]!r:>6} {mk:>4}  {cur_s:<12} -> {target:<12} {stem_head}')

rows.sort(key=lambda r: r['question_id'])
OUT_BATCH.parent.mkdir(parents=True, exist_ok=True)
with open(OUT_BATCH, 'w', encoding='utf-8') as f:
    for r in rows:
        f.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + '\n')
with open(OUT_TARGETS, 'w', encoding='utf-8') as f:
    json.dump(targets_out, f, ensure_ascii=False, indent=1)
print(f'\nwrote {len(rows)} rows -> {OUT_BATCH}')
print(f'wrote {len(targets_out)} targets -> {OUT_TARGETS}')

print('\n--- children current tags ---')
for pid in (52567, 52683):
    kids = cur.execute(
        'select q.id, q.number_label, q.marks, '
        ' (select group_concat(n.code) from question_taxonomy t '
        '  join taxonomy_node n on n.id=t.node_id where t.question_id=q.id) codes '
        'from question q where q.parent_id=? order by q.display_order, q.id', (pid,)).fetchall()
    print(f'parent {pid}: ' + '; '.join(f'{k["id"]} {k["number_label"]} {k["marks"]}mk [{k["codes"]}]' for k in kids))
con.close()
