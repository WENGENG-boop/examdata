import sqlite3
con = sqlite3.connect('file:.data/examdata.db?mode=ro', uri=True)
con.row_factory = sqlite3.Row
qids = [67693, 67695, 67699, 67701, 67704, 67706, 67713, 67716]
for qid in qids:
    r = con.execute("""SELECT q.id, q.number_label, q.display_order, q.stem_text,
        q.parent_id, q.paper_id, q.marks, q.kind, q.depth,
        EXISTS(SELECT 1 FROM question c WHERE c.parent_id=q.id) AS has_children
        FROM question q WHERE q.id=?""", (qid,)).fetchone()
    if not r:
        print(f"--- {qid} NOT FOUND"); continue
    print(f"=== {qid} num={r['number_label']} order={r['display_order']} marks={r['marks']} kind={r['kind']} depth={r['depth']} has_children={r['has_children']} parent={r['parent_id']}")
    print((r['stem_text'] or '')[:1500].replace(chr(10),' | '))
    p = con.execute("""SELECT p.id, p.paper_no, d.paper_code, d.year, d.title FROM paper p
        LEFT JOIN document d ON d.id = p.document_id WHERE p.id=?""", (r['paper_id'],)).fetchone()
    print("   paper:", dict(p) if p else None)
    kids = con.execute("SELECT id, number_label, display_order, substr(stem_text,1,400) as t FROM question WHERE parent_id=? ORDER BY display_order", (qid,)).fetchall()
    for k in kids:
        print(f"   >> kid {k['id']} {k['number_label']} order={k['display_order']}: {(k['t'] or '')[:350]}")
con.close()
