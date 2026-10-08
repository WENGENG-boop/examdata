import sqlite3

con = sqlite3.connect('file:.data/examdata.db?mode=ro', uri=True)
cur = con.cursor()

def q(qid):
    r = cur.execute("select id, paper_id, parent_id, number_label, stem_text from question where id=?", (qid,)).fetchone()
    return r

def labels(qid):
    rows = cur.execute("""select t.code, qt.source, qt.confidence from question_taxonomy qt
        join taxonomy_node t on t.id=qt.node_id where qt.question_id=?""", (qid,)).fetchall()
    return [(r[0], r[1], round(r[2],2) if r[2] is not None else None) for r in rows]

def ms(qid):
    rows = cur.execute("select answer_text from mark_scheme_entry where question_id=?", (qid,)).fetchall()
    return [r[0] for r in rows]

print("===== A. 'Complete the table' precedents (subject 16, all units) =====")
rows = cur.execute("""
  select qn.id, qn.number_label, qn.stem_text, d.subject_id
  from question qn
  join paper p on p.id = qn.paper_id
  join document d on d.id = p.document_id
  where d.subject_id = 16 and qn.stem_text like '%omplete the table%'
""").fetchall()
for r in rows:
    qid, lab, st, sid = r
    labs = labels(qid)
    print(f"--- {qid} [{lab}] labs={labs}")
    print("    ", (st or '').replace('\n', ' ')[:200])

print()
print("===== B. key precedent sources/conf =====")
for qid in [57760, 58881, 59824, 57799, 57800, 58358, 59858, 58901, 60377, 58894, 60919, 58356, 58367, 60393, 57794, 59852, 59853, 56959, 57781, 61012, 57778, 56935, 58593, 60918]:
    r = q(qid)
    if r is None:
        print(f"{qid} NOT FOUND")
        continue
    lab = r[3]
    print(f"{qid} [{lab}] labs={labels(qid)}")
    st = (r[4] or '').replace('\n', ' ')
    print("   stem:", st[:160])

print()
print("===== C. full text + MS for pending cluster =====")
for qid in [60917, 60918, 60919, 60920, 60921, 60922]:
    r = q(qid)
    if r is None:
        print(f"{qid} NOT FOUND")
        continue
    print(f"----- {qid} [{r[3]}] parent={r[2]} labs={labels(qid)}")
    print("STEM:", (r[4] or '').replace('\n', ' ')[:600])
    for m in ms(qid):
        print("MS:", (m or '').replace('\n', ' ')[:400])

print()
for qid in [60987, 60988, 60989, 60990, 60991, 60992]:
    r = q(qid)
    if r is None:
        print(f"{qid} NOT FOUND")
        continue
    print(f"----- {qid} [{r[3]}] parent={r[2]} labs={labels(qid)}")
    print("STEM:", (r[4] or '').replace('\n', ' ')[:600])
    for m in ms(qid):
        print("MS:", (m or '').replace('\n', ' ')[:400])

print()
for qid in [61025, 61026, 61027, 61028]:
    r = q(qid)
    if r is None:
        print(f"{qid} NOT FOUND")
        continue
    print(f"----- {qid} [{r[3]}] parent={r[2]} labs={labels(qid)}")
    print("STEM:", (r[4] or '').replace('\n', ' ')[:500])
    for m in ms(qid):
        print("MS:", (m or '').replace('\n', ' ')[:400])

print()
for qid in [60723, 60724, 60725, 60726, 60727]:
    r = q(qid)
    if r is None:
        print(f"{qid} NOT FOUND")
        continue
    print(f"----- {qid} [{r[3]}] parent={r[2]} labs={labels(qid)}")
    print("STEM:", (r[4] or '').replace('\n', ' ')[:500])
    for m in ms(qid):
        print("MS:", (m or '').replace('\n', ' ')[:400])

print()
for qid in [57774, 57775, 57776, 57777, 57778, 57779]:
    r = q(qid)
    if r is None:
        print(f"{qid} NOT FOUND")
        continue
    print(f"----- {qid} [{r[3]}] parent={r[2]} labs={labels(qid)}")
    print("STEM:", (r[4] or '').replace('\n', ' ')[:500])
    for m in ms(qid):
        print("MS:", (m or '').replace('\n', ' ')[:300])

print()
for qid in [58582, 58583, 58584]:
    r = q(qid)
    if r is None:
        print(f"{qid} NOT FOUND")
        continue
    print(f"----- {qid} [{r[3]}] parent={r[2]} labs={labels(qid)}")
    print("STEM:", (r[4] or '').replace('\n', ' ')[:500])
    for m in ms(qid):
        print("MS:", (m or '').replace('\n', ' ')[:300])

print()
for qid in [59382, 59383, 59384, 59385]:
    r = q(qid)
    if r is None:
        print(f"{qid} NOT FOUND")
        continue
    print(f"----- {qid} [{r[3]}] parent={r[2]} labs={labels(qid)}")
    print("STEM:", (r[4] or '').replace('\n', ' ')[:500])
    for m in ms(qid):
        print("MS:", (m or '').replace('\n', ' ')[:300])

print()
print("===== D. table-completion candidates' full stem+MS =====")
for qid in [57768, 58572, 59381, 59849, 60399]:
    r = q(qid)
    if r is None:
        print(f"{qid} NOT FOUND")
        continue
    print(f"----- {qid} [{r[3]}] parent={r[2]} labs={labels(qid)}")
    print("STEM:", (r[4] or '').replace('\n', ' ')[:700])
    for m in ms(qid):
        print("MS:", (m or '').replace('\n', ' ')[:500])
    # also parent
    if r[2]:
        pr = q(r[2])
        print(f"  PARENT {pr[0]} [{pr[3]}] labs={labels(pr[0])}")
        print("  PSTEM:", (pr[4] or '').replace('\n', ' ')[:500])
        for m in ms(pr[0]):
            print("  PMS:", (m or '').replace('\n', ' ')[:300])

print()
print("===== E. 60986 / 58922 / 56944 / 59384 / 58590 / 60993 / 61027 neighbors =====")
for qid in [60985, 60986, 60987, 58921, 58922, 58923, 56944, 58590, 58591, 60992, 60993, 60994, 61026, 61027]:
    r = q(qid)
    if r is None:
        print(f"{qid} NOT FOUND")
        continue
    print(f"----- {qid} [{r[3]}] parent={r[2]} labs={labels(qid)}")
    print("STEM:", (r[4] or '').replace('\n', ' ')[:300])

con.close()
