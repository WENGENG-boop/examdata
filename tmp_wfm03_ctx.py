import sqlite3
con = sqlite3.connect('file:.data/examdata.db?mode=ro', uri=True)
con.row_factory = sqlite3.Row

qids = [67693, 67695, 67699, 67701, 67704, 67706, 67713, 67716]
roots = {}
for qid in qids:
    r = con.execute("SELECT id, parent_id FROM question WHERE id=?", (qid,)).fetchone()
    pid = r['parent_id']
    cur = pid
    while cur is not None:
        rr = con.execute("SELECT id, parent_id FROM question WHERE id=?", (cur,)).fetchone()
        if rr['parent_id'] is None:
            break
        cur = rr['parent_id']
    roots[qid] = cur if cur is not None else qid

seen = set()
for qid, root in roots.items():
    if root in seen: continue
    seen.add(root)
    r = con.execute("SELECT id, number_label, stem_text FROM question WHERE id=?", (root,)).fetchone()
    print(f"\n########## ROOT {root} num={r['number_label']}")
    print((r['stem_text'] or '')[:1600].replace(chr(10),' | '))
    fam = [root]
    frontier = [root]
    while frontier:
        nxt = []
        for f in frontier:
            kids = con.execute("SELECT id FROM question WHERE parent_id=?", (f,)).fetchall()
            for k in kids:
                nxt.append(k['id']); fam.append(k['id'])
        frontier = nxt
    for f in fam:
        q = con.execute("SELECT id, number_label, substr(stem_text,1,260) as t FROM question WHERE id=?", (f,)).fetchone()
        tax = con.execute("""SELECT tn.code, qt.source FROM question_taxonomy qt
            JOIN taxonomy_node tn ON tn.id = qt.node_id WHERE qt.question_id=?""", (f,)).fetchall()
        taxs = "; ".join(f"{t['code']}({t['source']})" for t in tax) if tax else "--UNTAGGED--"
        mark = " <<<" if f in qids else ""
        print(f"  [{f}] {q['number_label']}: {(q['t'] or '')[:180].replace(chr(10),' / ')}")
        print(f"      TAX: {taxs}{mark}")
con.close()
