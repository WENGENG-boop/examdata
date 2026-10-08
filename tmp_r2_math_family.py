import sqlite3, sys, re

db = sqlite3.connect('file:.data/examdata.db?mode=ro', uri=True)
db.execute('pragma temp_store = memory')

seen = set()
for qid in sys.argv[1:]:
    qid = int(qid)
    row = db.execute('select paper_id from question where id=?', (qid,)).fetchone()
    if not row:
        print(qid, 'no question')
        continue
    pid = row[0]
    if pid in seen:
        continue
    seen.add(pid)
    rows = db.execute('''
        select q.id, q.number_label, q.marks, q.stem_text,
          (select group_concat(tn.code, '/') from question_taxonomy qt
             join taxonomy_node tn on tn.id = qt.node_id
            where qt.question_id = q.id) code
          from question q where q.paper_id = ? order by q.display_order''', (pid,)).fetchall()
    print(f'===== PAPER {pid} (via qid {qid}) | {len(rows)} questions')
    for r in rows:
        s = re.sub(r'\s+', ' ', r[3] or '')[:78]
        print(r[0], r[1], f'{r[2]}mk', r[4], '|', s)
