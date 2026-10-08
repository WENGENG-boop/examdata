import sqlite3, json
con = sqlite3.connect('file:.data/examdata.db?mode=ro', uri=True)
con.row_factory = sqlite3.Row
qids = [49095,49101,49102,49103,49104,49109,49120,49123,49125,49136,64168,64172,64173,64177,64178,64181,64182,64183,64188,64189,64190,64193,64195,64196,64200]
print("### batch-028 qids: paper & current tags")
for q in qids:
    r = con.execute("""SELECT q.id,q.number_label,q.marks,q.kind,q.parent_id,p.document_id,d.paper_code,d.title
        FROM question q JOIN paper p ON p.id=q.paper_id JOIN document d ON d.id=p.document_id WHERE q.id=?""",(q,)).fetchone()
    if not r: print(q,"NOT FOUND"); continue
    tags = con.execute("SELECT node_id,assigned_by,confidence,reviewed FROM question_taxonomy WHERE question_id=? ORDER BY node_id",(q,)).fetchall()
    tn = []
    for t in tags:
        n = con.execute("SELECT code,name FROM taxonomy_node WHERE id=?",(t['node_id'],)).fetchone()
        tn.append(f"{n['code']}({t['assigned_by']},r={t['reviewed']})")
    print(f"{q} {r['number_label']} {r['marks']}m kind={r['kind']} parent={r['parent_id']} doc={r['document_id']} {r['paper_code']} | {'; '.join(tn)}")
print()
print("### siblings 64167-64200 current tags")
for q in range(64167,64201):
    r = con.execute("""SELECT q.id,q.number_label,q.parent_id FROM question q WHERE q.id=?""",(q,)).fetchone()
    if not r: continue
    tags = con.execute("SELECT node_id,assigned_by,confidence,reviewed FROM question_taxonomy WHERE question_id=? ORDER BY node_id",(q,)).fetchall()
    tn = []
    for t in tags:
        n = con.execute("SELECT code FROM taxonomy_node WHERE id=?",(t['node_id'],)).fetchone()
        tn.append(f"{n['code']}({t['assigned_by']},c={t['confidence']},r={t['reviewed']})")
    print(f"{q} {r['number_label']} parent={r['parent_id']} | {'; '.join(tn)}")
