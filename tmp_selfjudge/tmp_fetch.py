import sqlite3, sys, json
db = sqlite3.connect('file:.data/examdata.db?mode=ro', uri=True)
qids = [int(x) for x in sys.argv[1:]]
for qid in qids:
    q = db.execute("select q.id, q.number_path, q.marks, q.stem_text, q.kind, q.parent_id from question q where q.id=?", (qid,)).fetchone()
    if not q:
        print(f"=== {qid}: NOT FOUND ==="); continue
    qid_, np, marks, stem, kind, par = q
    codes = [r[0] for r in db.execute("select tn.code from question_taxonomy qt join taxonomy_node tn on tn.id=qt.node_id where qt.question_id=?", (qid,))]
    print(f"=== {qid} path={np} marks={marks} kind={kind} par={par} codes={codes} ===")
    print("STEM:", (stem or "").replace("\n", " | ")[:1500])
    ms = db.execute("select number_path, answer_text, acceptable_answers, guidance from mark_scheme_entry where question_id=?", (qid,)).fetchall()
    for m in ms:
        print(f"MS[{m[0]}]:", (m[1] or "")[:900])
        if m[2]: print("  ACC:", str(m[2])[:300])
        if m[3]: print("  GUID:", str(m[3])[:300])
    print()
