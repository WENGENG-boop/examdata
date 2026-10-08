import sqlite3, sys
db = sqlite3.connect('file:.data/examdata.db?mode=ro', uri=True)
qid = int(sys.argv[1])
pid = db.execute("select paper_id from question where id=?", (qid,)).fetchone()[0]
print(f"paper_id={pid}")
rows = db.execute("""select q.id, q.number_path, q.marks, substr(q.stem_text,1,90),
  (select group_concat(tn.code) from question_taxonomy qt join taxonomy_node tn on tn.id=qt.node_id where qt.question_id=q.id)
  from question q where q.paper_id=? order by q.display_order""", (pid,)).fetchall()
for r in rows:
    print(f"[{r[0]}] {r[1]} {r[2]}mk {r[4]}")
    print("   ", (r[3] or "").replace("\n"," | ")[:120])
