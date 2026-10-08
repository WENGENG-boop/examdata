import sqlite3, json
con = sqlite3.connect('file:.data/examdata.db?mode=ro', uri=True)
con.row_factory = sqlite3.Row
cur = con.cursor()

print('=== TABLES ===')
for r in cur.execute("select name from sqlite_master where type='table' order by name"):
    print(' ', r['name'])

print('=== SCHEMA question ===')
for r in cur.execute("PRAGMA table_info(question)"):
    print(' ', r['name'], r['type'])
print('=== SCHEMA mark_scheme_entry ===')
for r in cur.execute("PRAGMA table_info(mark_scheme_entry)"):
    print(' ', r['name'], r['type'])


def qdump(qid, trunc=6000):
    print(f'\n########## QID {qid} ##########')
    rows = cur.execute('select * from question where id=?', (qid,)).fetchall()
    if not rows:
        print('  NOT FOUND')
        return
    for r in rows:
        d = dict(r)
        for k, v in d.items():
            if isinstance(v, str) and len(v) > trunc:
                d[k] = v[:trunc] + f' ...[TRUNC len={len(v)}]'
        print('QUESTION:', json.dumps(d, ensure_ascii=False, indent=1))
    print('-- TAXONOMY:')
    for r in cur.execute('''select qt.*, tn.code, tn.name, tn.node_type from question_taxonomy qt
                            join taxonomy_node tn on tn.id=qt.node_id where qt.question_id=?''', (qid,)):
        print('  ', json.dumps(dict(r), ensure_ascii=False))
    print('-- MS rows:')
    for r in cur.execute('select * from mark_scheme_entry where question_id=?', (qid,)):
        d = dict(r)
        for k, v in d.items():
            if isinstance(v, str) and len(v) > 2500:
                d[k] = v[:2500] + f' ...[TRUNC len={len(v)}]'
        print('  ', json.dumps(d, ensure_ascii=False))


def paperdump(qid, stemlen=150):
    row = cur.execute('select paper_id from question where id=?', (qid,)).fetchone()
    if not row:
        print(f'no paper for {qid}')
        return
    pid = row['paper_id']
    print(f'\n===== PAPER {pid} (from qid {qid}) =====')
    for r in cur.execute('''select q.id, q.number_label, q.marks, q.display_order,
              substr(q.stem_text,1,?) as stem, group_concat(tn.code, '|') as codes
        from question q
        left join question_taxonomy qt on qt.question_id=q.id
        left join taxonomy_node tn on tn.id=qt.node_id
        where q.paper_id=? group by q.id order by q.display_order, q.id''', (stemlen, pid)):
        print(json.dumps(dict(r), ensure_ascii=False))


qdump(55608)
paperdump(55608)
qdump(56196)
paperdump(56196)
qdump(56279)
qdump(53271)
qdump(53549, trunc=3000)
qdump(54972, trunc=3000)
qdump(54994, trunc=3000)
con.close()
