import sqlite3, json
from pathlib import Path

db = sqlite3.connect('file:.data/examdata.db?mode=ro', uri=True)
db.row_factory = sqlite3.Row

qids = [int(l.split()[1]) for l in Path('tmp_selfjudge/r3/ial-englit/WET03-p01.txt').read_text(encoding='utf-8').splitlines()
        if l.startswith('[') and len(l.split()) > 1]

# 1) mark scheme sample rows for a few questions
print('=== MARK SCHEME SAMPLES ===')
for q in [49360, 49846, 49969]:
    rows = db.execute("SELECT number_label, substr(answer_text,1,400) a, substr(guidance,1,200) g FROM mark_scheme_entry WHERE question_id=?", (q,)).fetchall()
    print(f'--- qid {q}: {len(rows)} rows')
    for r in rows[:3]:
        print('  label:', r['number_label'])
        print('  answer:', repr(r['a']))
        print('  guidance:', repr(r['g']))

# 2) sibling questions in the same papers: what do other questions look like?
print()
print('=== SIBLINGS PER PAPER ===')
qmeta = {r['id']: r for r in db.execute(
    f"SELECT id, paper_id, number_label, marks, display_order, substr(stem_text,1,120) s FROM question WHERE id IN ({','.join('?'*len(qids))})", qids)}
pids = sorted(set(r['paper_id'] for r in qmeta.values()))
for p in pids:
    sibs = db.execute("SELECT id, number_label, marks, display_order, substr(stem_text,1,100) s FROM question WHERE paper_id=? ORDER BY display_order", (p,)).fetchall()
    print(f'--- paper {p}: {len(sibs)} questions')
    for s in sibs:
        mark = 'PACK' if s['id'] in qmeta else '    '
        print(f"   {mark} {s['id']} n={s['number_label']!r} mk={s['marks']} ord={s['display_order']} | {s['s']!r}")

# 3) taxonomy of siblings (all questions in these papers)
print()
print('=== TAXONOMY OF ALL SIBLING QUESTIONS ===')
allids = [s['id'] for p in pids for s in db.execute("SELECT id FROM question WHERE paper_id=?", (p,)).fetchall()]
rows = db.execute(f"SELECT question_id, node_id FROM question_taxonomy WHERE question_id IN ({','.join('?'*len(allids))})", allids).fetchall()
nodes = {r['id']: (r['code'], r['name']) for r in db.execute("SELECT id, code, name FROM taxonomy_node").fetchall()}
from collections import Counter
c = Counter(nodes.get(r['node_id']) for r in rows)
for k, v in c.most_common():
    print('  ', v, k)
