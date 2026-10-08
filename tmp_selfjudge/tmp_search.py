import sqlite3, sys
db = sqlite3.connect('file:.data/examdata.db?mode=ro', uri=True)
pat = sys.argv[1]
lim = int(sys.argv[2]) if len(sys.argv)>2 else 20
rows = db.execute("""select q.id, q.number_path, q.marks, substr(q.stem_text,1,110),
  (select group_concat(tn.code) from question_taxonomy qt join taxonomy_node tn on tn.id=qt.node_id where qt.question_id=q.id)
  from question q where q.stem_text like ? limit ?""", (f'%{pat}%', lim)).fetchall()
for r in rows:
    print(f"[{r[0]}] {r[1]} {r[2]}mk codes={r[4]}")
    print("   ", (r[3] or "").replace("\n"," | ")[:150])
