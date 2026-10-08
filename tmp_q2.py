import sqlite3
con = sqlite3.connect('file:.data/examdata.db?mode=ro', uri=True)
con.row_factory = sqlite3.Row
for q in (49100,46844,46889,46891,47004,48448,46376):
    r = con.execute("SELECT id,number_label,marks,kind,parent_id FROM question WHERE id=?",(q,)).fetchone()
    if not r: print(q,'NOT FOUND'); continue
    tags = con.execute("SELECT node_id,assigned_by,confidence,reviewed FROM question_taxonomy WHERE question_id=? ORDER BY node_id",(q,)).fetchall()
    tn=[]
    for t in tags:
        n = con.execute("SELECT code FROM taxonomy_node WHERE id=?",(t['node_id'],)).fetchone()
        tn.append(f"{n['code']}({t['assigned_by']},c={t['confidence']},r={t['reviewed']})")
    print(f"{q} {r['number_label']} parent={r['parent_id']} | {'; '.join(tn)}")
