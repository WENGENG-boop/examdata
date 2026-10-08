"""Second introspection: maths-extra mapping + distinct tagged questions."""
import json
import sqlite3

con = sqlite3.connect('.data/examdata.db')
cur = con.cursor()

print('=== distinct questions by assigned_by ===')
for row in cur.execute(
    "SELECT assigned_by, COUNT(DISTINCT question_id) FROM question_taxonomy GROUP BY 1"
):
    print(row)

print('=== total distinct tagged questions ===')
print(cur.execute('SELECT COUNT(DISTINCT question_id) FROM question_taxonomy').fetchone())

print('=== taxonomy_node cols ===')
cols = [r[1] for r in cur.execute('PRAGMA table_info(taxonomy_node)')]
print(cols)

print('=== nodes with unit WMA01 / WMA11 ===')
for row in cur.execute(
    "SELECT id, code, unit_code, subject_id FROM taxonomy_node WHERE unit_code IN ('WMA01','WMA11') LIMIT 8"
):
    print(row)

print('=== sample extra batch-001 first row ===')
with open('tmp_jev_full_batches/ial18-mathematics-extra/batches/batch-001.jsonl', encoding='utf-8') as fh:
    rec = json.loads(fh.readline())
qid = rec['question_id']
print('qid', qid, 'paper_code', rec['paper_code'], 'unit', rec['unit_code'],
      'current', [c['code'] for c in rec.get('current', [])])

print('=== that question in DB ===')
row = cur.execute(
    'SELECT q.id, q.number_label, p.paper_code, p.attrs, d.subject_id, s.slug '
    'FROM question q JOIN paper p ON p.id=q.paper_id JOIN document d ON d.id=p.document_id '
    'JOIN subject s ON s.id=d.subject_id WHERE q.id=?', (qid,)).fetchone()
print(row)

print('=== its taxonomy rows ===')
for r in cur.execute(
    'SELECT qt.id, qt.node_id, tn.code, tn.unit_code, qt.source, qt.assigned_by, qt.reviewed '
    'FROM question_taxonomy qt JOIN taxonomy_node tn ON tn.id=qt.node_id WHERE qt.question_id=?',
    (qid,),
):
    print(r)

print('=== sample mathematics batch-001 first row ===')
with open('tmp_jev_full_batches/ial18-mathematics/batches/batch-001.jsonl', encoding='utf-8') as fh:
    rec2 = json.loads(fh.readline())
qid2 = rec2['question_id']
print('qid', qid2, 'paper_code', rec2['paper_code'], 'unit', rec2['unit_code'],
      'current', [c['code'] for c in rec2.get('current', [])])
row2 = cur.execute(
    'SELECT q.id, p.paper_code, p.attrs, d.subject_id, s.slug '
    'FROM question q JOIN paper p ON p.id=q.paper_id JOIN document d ON d.id=p.document_id '
    'JOIN subject s ON s.id=d.subject_id WHERE q.id=?', (qid2,)).fetchone()
print(row2)
for r in cur.execute(
    'SELECT qt.id, tn.code, tn.unit_code, qt.source, qt.assigned_by, qt.reviewed '
    'FROM question_taxonomy qt JOIN taxonomy_node tn ON tn.id=qt.node_id WHERE qt.question_id=?',
    (qid2,),
):
    print(r)

print('=== extra decisions applied.jsonl head ===')
try:
    with open('.data/tagging/review-export/ial18-mathematics-extra/decisions/applied.jsonl', encoding='utf-8') as fh:
        for i, line in enumerate(fh):
            if i >= 3:
                break
            print(line.strip()[:200])
except FileNotFoundError:
    print('no applied.jsonl')

print('=== ial-maths nodes with unit WMA11 count ===')
print(cur.execute(
    "SELECT COUNT(*) FROM taxonomy_node WHERE subject_id=16 AND unit_code LIKE 'WMA1%'"
).fetchone())
print(cur.execute(
    "SELECT COUNT(*) FROM taxonomy_node WHERE subject_id=24 AND unit_code LIKE 'WMA1%'"
).fetchone())
