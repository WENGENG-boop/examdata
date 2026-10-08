import sqlite3, json
from pathlib import Path

db = sqlite3.connect('file:.data/examdata.db?mode=ro', uri=True)
db.row_factory = sqlite3.Row

qids = [int(l.split()[1]) for l in Path('tmp_selfjudge/r3/ial-englit/WET03-p01.txt').read_text(encoding='utf-8').splitlines()
        if l.startswith('[') and len(l.split()) > 1]

print('pack qids:', len(qids), qids[:5], '...')

qs = db.execute(f"SELECT q.id, q.paper_id, q.number_label, q.marks, q.display_order, substr(q.stem_text,1,90) s "
                f"FROM question q WHERE q.id IN ({','.join('?'*len(qids))})", qids).fetchall()
qmap = {r['id']: r for r in qs}
print('found in question table:', len(qmap))

# taxonomy
tax = db.execute(f"SELECT question_id, node_id, source, confidence, assigned_by, reviewed FROM question_taxonomy "
                 f"WHERE question_id IN ({','.join('?'*len(qids))})", qids).fetchall()
nodes = {r['id']: r for r in db.execute("SELECT id, code, name, node_type, attrs FROM taxonomy_node").fetchall()}
print('taxonomy rows:', len(tax))
from collections import Counter
c = Counter((t['node_id'], t['source'], t['assigned_by'], t['reviewed']) for t in tax)
for k, v in c.most_common(20):
    n = nodes.get(k[0])
    print('  ', k, '->', v, 'node:', n['code'] if n else None, n['name'] if n else None, n['node_type'] if n else None)

# marks distribution
mc = Counter(qmap[q]['marks'] for q in qids if q in qmap)
print('marks distribution:', dict(mc))
missing = [q for q in qids if q not in qmap]
print('missing qids:', missing)

# mark scheme rows
ms = db.execute(f"SELECT question_id, count(*) n FROM mark_scheme_entry WHERE question_id IN ({','.join('?'*len(qids))}) GROUP BY question_id", qids).fetchall()
print('qs with mark scheme rows:', len(ms), 'total rows:', sum(r['n'] for r in ms))
msmap = {r['question_id']: r['n'] for r in ms}
print('qs WITHOUT ms rows:', [q for q in qids if q not in msmap])

# paper info
pids = sorted(set(qmap[q]['paper_id'] for q in qids if q in qmap))
for p in db.execute(f"SELECT id, document_id, paper_no FROM paper WHERE id IN ({','.join('?'*len(pids))})", pids).fetchall():
    print('paper', dict(p))

# stem samples for ms-bearing questions
print('\n--- stem samples ---')
for q in qids[:6]:
    if q in qmap:
        print(q, '|', qmap[q]['number_label'], '|', qmap[q]['marks'], '|', repr(qmap[q]['s'][:80]))
