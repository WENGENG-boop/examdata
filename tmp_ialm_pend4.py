import sqlite3

con = sqlite3.connect('file:.data/examdata.db?mode=ro', uri=True)
cur = con.cursor()

def labels(qid):
    rows = cur.execute("""select t.code, t.name, qt.source, qt.confidence from question_taxonomy qt
        join taxonomy_node t on t.id=qt.node_id where qt.question_id=?""", (qid,)).fetchall()
    return [(r[0], r[1], r[2], round(r[3],2) if r[3] is not None else None) for r in rows]

def q(qid):
    r = cur.execute("select id, paper_id, parent_id, number_label, stem_text from question where id=?", (qid,)).fetchone()
    return r

def ms(qid):
    rows = cur.execute("select answer_text from mark_scheme_entry where question_id=?", (qid,)).fetchall()
    return [r[0] for r in rows]

print("===== A. WMA12 / WFM01 taxonomy nodes =====")
rows = cur.execute("select id, code, name from taxonomy_node where code like 'WMA12-%' or code like 'WFM01-%' order by id").fetchall()
for r in rows:
    print(r)
print("total:", len(rows))

print()
print("===== B. subject-24 table precedents full context =====")
for qid in [36496, 36497, 36498, 41009, 41010, 41011, 45981, 45982, 45983]:
    r = q(qid)
    if r is None:
        print(f"{qid} NOT FOUND")
        continue
    print(f"----- {qid} [{r[3]}] parent={r[2]} labs={labels(qid)}")
    print("STEM:", (r[4] or '').replace('\n', ' ')[:700])
    for m in ms(qid):
        print("MS:", (m or '').replace('\n', ' ')[:500])

print()
print("===== C. WMA12-8.x / -5.x / -2.x names again for confirmation =====")
rows = cur.execute("select id, code, name from taxonomy_node where code like 'WMA12-%' order by code").fetchall()
for r in rows:
    print(r)

con.close()
