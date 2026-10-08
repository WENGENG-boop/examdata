import sqlite3, re, sys
con = sqlite3.connect('file:.data/examdata.db?mode=ro', uri=True)
cur = con.cursor()

def paper_of(qid):
    cur.execute("SELECT paper_id FROM question WHERE id=?", (qid,))
    r = cur.fetchone()
    return r[0] if r else None

def paper_questions(pid):
    cur.execute("""SELECT q.id, q.number_label, q.marks, q.kind,
                          (SELECT group_concat(t.code, ',') FROM question_taxonomy qt JOIN taxonomy_node t ON t.id=qt.node_id WHERE qt.question_id=q.id) AS codes
                   FROM question q WHERE q.paper_id=? ORDER BY q.display_order, q.id""", (pid,))
    return cur.fetchall()

def stem(qid, n=110):
    cur.execute("SELECT stem_text FROM question WHERE id=?", (qid,))
    r = cur.fetchone()
    return re.sub(r'\s+',' ', (r[0] or ''))[:n] if r else ''

seen = {}
for qid in [int(x) for x in sys.argv[1:]]:
    pid = paper_of(qid)
    if pid in seen:
        continue
    seen[pid] = 1
    print(f'===== paper {pid} (via {qid}) =====')
    for r in paper_questions(pid):
        mark = ' <<<' if r[0]==qid else ''
        print(f'  [{r[0]}] n={r[1]} m={r[2]} {r[3]} codes={r[4]}{mark}')
        if r[0]==qid:
            print(f'        stem: {stem(qid)}')
    print()
