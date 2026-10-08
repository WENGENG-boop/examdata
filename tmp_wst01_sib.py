import sqlite3, sys, re
con=sqlite3.connect('file:.data/examdata.db?mode=ro',uri=True)
con.execute('pragma temp_store = memory')
cur=con.cursor()
def label(qid):
    rows=list(cur.execute("""select tn.code from question_taxonomy qt
        join taxonomy_node tn on tn.id=qt.node_id
        where qt.question_id=? order by qt.id""",(qid,)))
    return '、'.join(r[0] for r in rows)
def stem(qid,n=100):
    st=(cur.execute("select stem_text from question where id=?",(qid,)).fetchone() or [''])[0] or ''
    return re.sub(r'\s+',' ',st)[:n]
seen=set()
for q in sys.argv[1:]:
    q=int(q)
    r=cur.execute("select id,parent_id,number_label,marks from question where id=?",(q,)).fetchone()
    if not r: print(q,'NOT FOUND'); continue
    pid=r[1] or q
    if pid in seen: continue
    seen.add(pid)
    pr=cur.execute("select id,parent_id,number_label,marks,stem_text from question where id=?",(pid,)).fetchone()
    print(f'== parent {pid} num={pr[2]} mk={pr[3]} cur={label(pid)} | {stem(pid,90)}')
    kids=list(cur.execute("select id,number_label,marks,display_order from question where parent_id=? order by display_order",(pid,)))
    if not kids: kids=[(pid,pr[2],pr[3],0)]
    for k in kids:
        mark=f'{k[2]}mk' if k[2] is not None else '?mk'
        print(f'   {k[0]} {k[1]} {mark} cur={label(k[0])} | {stem(k[0],95)}')
