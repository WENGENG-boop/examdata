import sqlite3, re, sys
con = sqlite3.connect('file:.data/examdata.db?mode=ro', uri=True)
cur = con.cursor()

def ms_for(qid):
    cur.execute("""SELECT number_label, answer_text, guidance FROM mark_scheme_entry WHERE question_id=? ORDER BY id""", (qid,))
    return cur.fetchall()

for qid in [int(x) for x in sys.argv[1:]]:
    cur.execute("SELECT id, number_label, marks, substr(stem_text,1,200) FROM question WHERE id=?", (qid,))
    r = cur.fetchone()
    print(f'===== [{qid}] n={r[1]} m={r[2]}')
    print('  stem:', re.sub(r'\s+',' ', r[3] or '')[:200])
    for n, t, g in ms_for(qid):
        print(f'  MS[{n}]:', re.sub(r'\s+',' ', t or '')[:400])
        if g:
            print(f'    guidance:', re.sub(r'\s+',' ', g or '')[:300])
    print()
