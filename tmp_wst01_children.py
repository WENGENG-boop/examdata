import sqlite3, sys, re
con=sqlite3.connect('file:.data/examdata.db?mode=ro',uri=True)
con.execute('pragma temp_store = memory')
cur=con.cursor()
def label(qid):
    rows=list(cur.execute("""select tn.code from question_taxonomy qt
        join taxonomy_node tn on tn.id=qt.node_id
        where qt.question_id=? order by qt.id""",(qid,)))
    return '、'.join(r[0] for r in rows)
for q in sys.argv[1:]:
    q=int(q)
    r=cur.execute("select id,parent_id,number_label,marks,stem_text from question where id=?",(q,)).fetchone()
    if not r: print(q,'NOT FOUND'); continue
    print(f'== {q} num={r[2]} mk={r[3]} parent={r[1]} cur={label(q)}')
    kids=list(cur.execute("select id,number_label,marks,display_order from question where parent_id=? order by display_order",(q,)))
    for k in kids:
        st=(cur.execute("select stem_text from question where id=?",(k[0],)).fetchone()[0] or '')
        st=re.sub(r'\s+',' ',st)[:110]
        print(f'   {k[0]} {k[1]} {k[2]}mk cur={label(k[0])} | {st}')
