import sqlite3, json, sys
con = sqlite3.connect('file:.data/examdata.db?mode=ro', uri=True)
con.row_factory = sqlite3.Row
cur = con.cursor()

qids = [55608, 55803, 55511, 56581, 56196, 56279, 53549, 53271, 54972, 54994, 51126]
print('=== QUESTIONS ===')
for q in qids:
    rows = cur.execute('select q.id, q.paper_id, q.number_label, q.marks, q.display_order, substr(q.stem_text,1,400) as stem from question q where q.id=?', (q,)).fetchall()
    for r in rows:
        print(dict(r))
    if not rows:
        print(q, 'NOT FOUND')

print()
print('=== TAXONOMY ===')
for q in qids:
    rows = cur.execute('''select qt.question_id, qt.node_id, qt.source, qt.confidence, qt.assigned_by, qt.reviewed, tn.code, tn.name, tn.node_type
                          from question_taxonomy qt join taxonomy_node tn on tn.id=qt.node_id
                          where qt.question_id=?''', (q,)).fetchall()
    print(q, [dict(r) for r in rows])

print()
print('=== MARK SCHEME ===')
for q in qids:
    rows = cur.execute('select * from mark_scheme_entry where question_id=?', (q,)).fetchall()
    print(f'--- {q}: {len(rows)} rows')
    for r in rows:
        d = dict(r)
        for k, v in d.items():
            if isinstance(v, str) and len(v) > 1500:
                d[k] = v[:1500] + ' ...[TRUNC len=%d]' % len(v)
        print(json.dumps(d, ensure_ascii=False))
con.close()
