import sqlite3, json, sys
con = sqlite3.connect('.data/examdata.db')
con.row_factory = sqlite3.Row
cur = con.cursor()

print("=== paper 1351 nodes ===")
rows = cur.execute("""
SELECT q.id, q.parent_id, q.kind, q.number_label, q.number_path, q.display_order, q.marks,
       substr(coalesce(q.stem_text,''),1,90) AS stem_head
FROM question q WHERE q.paper_id=1351 ORDER BY q.id
""").fetchall()
for r in rows:
    print(dict(r))

print("\n=== taxonomy for paper 1351 nodes ===")
rows = cur.execute("""
SELECT t.question_id, t.node_id, n.code, n.name, t.source, t.confidence
FROM question_taxonomy t JOIN taxonomy_node n ON n.id=t.node_id
WHERE t.question_id IN (SELECT id FROM question WHERE paper_id=1351)
ORDER BY t.question_id
""").fetchall()
for r in rows:
    print(dict(r))

print("\n=== MS entries for MS id 1523 ===")
rows = cur.execute("""
SELECT m.id, m.question_id, m.number_label, m.number_path, m.marks, substr(coalesce(m.answer_text,''),1,80) AS ans_head
FROM mark_scheme_entry m WHERE m.mark_scheme_id=1523 ORDER BY m.id
""").fetchall()
for r in rows:
    print(dict(r))

print("\n=== paper row 1351 ===")
r = cur.execute("SELECT * FROM paper WHERE id=1351").fetchone()
print(dict(r) if r else None)
con.close()
