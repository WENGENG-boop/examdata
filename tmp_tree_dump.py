import sqlite3
c = sqlite3.connect('file:.data/examdata.db?mode=ro', uri=True)
c.execute('PRAGMA temp_store=MEMORY')
pids = [c.execute("select paper_id from question where id=?", (q,)).fetchone()[0] for q in (52165, 52263, 52552, 52668)]
for pid in pids:
    meta = c.execute("select doc.year, doc.paper_code from paper p join document doc on doc.id=p.document_id where p.id=?", (pid,)).fetchone()
    print(f"\n########## paper {pid} {meta[1]} {meta[0]} ##########")
    qs = list(c.execute("select id, parent_id, number_label, marks from question where paper_id=? order by id", (pid,)))
    def labs(qid):
        return [r[0].split('-')[-1] for r in c.execute("select tn.code from question_taxonomy qt join taxonomy_node tn on tn.id=qt.node_id where qt.question_id=? order by tn.code", (qid,))]
    for qid, par, nl, mk in qs:
        depth = 0; p = par
        while p:
            depth += 1
            p = c.execute("select parent_id from question where id=?", (p,)).fetchone()[0]
        print(f"{'  '*depth}{qid} #{nl} m={mk} labels={labs(qid)}")
