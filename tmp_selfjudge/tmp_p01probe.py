import sqlite3, sys, json
con = sqlite3.connect('file:.data/examdata.db?mode=ro', uri=True)
cur = con.cursor()

def tax_for(qid):
    cur.execute("""SELECT t.code, qt.source, qt.confidence, qt.assigned_by, qt.reviewed
                   FROM question_taxonomy qt JOIN taxonomy_node t ON t.id=qt.node_id
                   WHERE qt.question_id=? ORDER BY t.code""", (qid,))
    return cur.fetchall()

def show_q(qid):
    cur.execute("SELECT id, number_label, marks, kind, substr(stem_text,1,150) FROM question WHERE id=?", (qid,))
    r = cur.fetchone()
    if not r:
        print(f'[{qid}] NOT FOUND'); return
    print(f'[{qid}] n={r[1]} m={r[2]} kind={r[3]}')
    print('   stem:', (r[4] or '').replace(chr(10),' ')[:150])
    for t in tax_for(qid):
        print('   TAX:', t)

# target questions
for qid in [29432, 30725, 30134, 32409, 33850, 32630, 34002, 32627, 33857, 33354, 29802, 32403, 29434, 33363, 34000, 31844, 29797, 32405, 32626, 33856, 33567, 29440]:
    show_q(qid)
    print()
