"""Compact batch viewer for review-export batches.

Usage: python tmp_show_batch.py <slug> <batch> [stem_chars]
"""
import json
import sqlite3
import sys
from pathlib import Path

slug, batch = sys.argv[1], sys.argv[2]
nchars = int(sys.argv[3]) if len(sys.argv) > 3 else 140
root = Path('.data/tagging/review-export') / slug

points = json.load(open(root / f'points-{slug}.json', encoding='utf-8'))
print('== points', slug)
for unit, pts in points['units'].items():
    print(f'  {unit}: ' + ', '.join(p['code'] for p in pts))

con = sqlite3.connect('file:.data/examdata.db?mode=ro', uri=True)
cur = con.cursor()
print(f'== batch {batch}')
items = [json.loads(l) for l in open(root / 'batches' / f'{batch}.jsonl', encoding='utf-8') if l.strip()]
qids = [it['question_id'] for it in items]
unit_of = {it['question_id']: it.get('unit_code') for it in items}
print('n =', len(qids))
for qid in qids:
    q = cur.execute('select id,number_path,marks,stem_text,parent_id from question where id=?', (qid,)).fetchone()
    if q is None:
        print(qid, 'NOT FOUND'); continue
    tags = cur.execute('''select n.code,qt.confidence,qt.reviewed,n.name from question_taxonomy qt join taxonomy_node n on qt.node_id=n.id where qt.question_id=?''', (qid,)).fetchall()
    stem = (q[3] or '').replace('\n', ' ')
    print(f"{q[0]} | {q[1]} | m={q[2]} | unit={unit_of[qid]} | " + ' ; '.join(f"{c}:{conf:.2f}[{nm[:36]}]" for c, conf, rv, nm in tags))
    print('   ', stem[:nchars])
    if q[4]:
        p = cur.execute('select number_path,stem_text from question where id=?', (q[4],)).fetchone()
        pstem = (p[1] or '').replace('\n', ' ')
        print(f'   [P {p[0]}]', pstem[:nchars])
