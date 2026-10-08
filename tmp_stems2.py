import sqlite3, textwrap
c = sqlite3.connect('file:.data/examdata.db?mode=ro', uri=True)
c.execute('PRAGMA temp_store=MEMORY')
qids = [52174, 52175, 52265, 52268, 52269, 52561, 52562, 52567, 52568, 52569, 52570, 52584, 52684, 52685, 52698, 52188, 52189]
for qid in qids:
    r = c.execute("select number_label, marks, stem_text from question where id=?", (qid,)).fetchone()
    stem = (r[2] or '')[:260]
    labs = [l[0] for l in c.execute("select tn.code from question_taxonomy qt join taxonomy_node tn on tn.id=qt.node_id where qt.question_id=? order by tn.code", (qid,))]
    print(f"===== q={qid} #{r[0]} m={r[1]} labels={labs}")
    print(textwrap.fill(stem, 140)); print()
