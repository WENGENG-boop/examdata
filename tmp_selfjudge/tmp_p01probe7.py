import sqlite3, re
con = sqlite3.connect('file:.data/examdata.db?mode=ro', uri=True)
cur = con.cursor()

def show(qid):
    cur.execute("SELECT id, number_label, marks, kind, stem_text FROM question WHERE id=?", (qid,))
    r = cur.fetchone()
    cur.execute("""SELECT t.code, qt.source FROM question_taxonomy qt JOIN taxonomy_node t ON t.id=qt.node_id WHERE qt.question_id=?""", (qid,))
    tax = cur.fetchall()
    print(f'[{r[0]}] n={r[1]} m={r[2]} kind={r[3]} tax={tax}')
    stem = (r[4] or '')
    print(stem[:700])
    print('-'*80)

for qid in [33392, 33393, 33394, 33395, 33396, 33397, 33398]:
    show(qid)
