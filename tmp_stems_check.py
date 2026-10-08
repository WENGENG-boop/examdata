import sqlite3, textwrap
c = sqlite3.connect('file:.data/examdata.db?mode=ro', uri=True)
c.execute('PRAGMA temp_store=MEMORY')
qids = [52171, 52172, 52263, 52552, 52566, 52573, 52582, 52583, 52682, 52696, 52697, 52287, 52286, 52288]
for qid in qids:
    r = c.execute("select number_label, marks, substr(stem_text,1,400) from question where id=?", (qid,)).fetchone()
    print(f"===== q={qid} #{r[0]} marks={r[1]} =====")
    print(textwrap.fill(r[2] or '', 150))
    labs = list(c.execute("select tn.code from question_taxonomy qt join taxonomy_node tn on tn.id=qt.node_id where qt.question_id=? order by tn.code", (qid,)))
    print("labels:", [l[0] for l in labs])
    print()
