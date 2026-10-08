import sqlite3, json, sys
con = sqlite3.connect('file:.data/examdata.db?mode=ro', uri=True)
con.row_factory = sqlite3.Row
cur = con.cursor()

qids = [55608, 55803, 55511, 56581, 56196, 56279, 53549, 53271, 54972, 54994, 51126]
for q in qids:
    row = cur.execute('''select q.id, q.paper_id, q.number_label, q.marks, q.display_order,
                         p.paper_no, p.marks_total, p.question_count, d.id as doc_id, d.title, d.paper_code, d.year, d.series_id, d.doc_type
                         from question q join paper p on p.id=q.paper_id join document d on d.id=p.document_id
                         where q.id=?''', (q,)).fetchone()
    print('='*100)
    print('QID', q, dict(row))
    print('--- FULL STEM ---')
    st = cur.execute('select stem_text from question where id=?', (q,)).fetchone()[0]
    print(st[:3000])
    print('--- SIBLINGS (same paper, same document) ---')
    sibs = cur.execute('''select q.id, q.number_label, q.marks, q.display_order, substr(q.stem_text,1,120) as st,
                          (select group_concat(tn.code, ',') from question_taxonomy qt join taxonomy_node tn on tn.id=qt.node_id where qt.question_id=q.id) as codes
                          from question q where q.paper_id=? order by q.display_order''', (row['paper_id'],)).fetchall()
    for s in sibs:
        print('   ', s['id'], '|', s['number_label'], '|', s['marks'], 'mk | ord', s['display_order'], '| codes:', s['codes'], '|', (s['st'] or '').replace('\n', ' ')[:110])
    print()
con.close()
