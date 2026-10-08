import sqlite3

con = sqlite3.connect('file:.data/examdata.db?mode=ro', uri=True)
cur = con.cursor()


def labels(qid):
    rows = cur.execute(
        """select t.code, qt.source, qt.confidence from question_taxonomy qt
           join taxonomy_node t on t.id=qt.node_id where qt.question_id=?""",
        (qid,)).fetchall()
    return [(r[0], r[1], round(r[2], 2) if r[2] is not None else None) for r in rows]


def paper_of(qid):
    return cur.execute("select paper_id from question where id=?", (qid,)).fetchone()[0]


print("===== A. all 'complete the table' parts in DB =====")
rows = cur.execute("""
  select q.id, q.number_label, q.parent_id, d.subject_id, substr(q.stem_text,1,130)
  from question q join paper p on p.id=q.paper_id join document d on d.id=p.document_id
  where lower(q.stem_text) like '%complete the table%'
  order by q.id
""").fetchall()
for qid, lab, par, sid, st in rows:
    pst = ''
    if par:
        r = cur.execute("select substr(stem_text,1,90) from question where id=?", (par,)).fetchone()
        pst = (r[0] or '').replace('\n', ' ')
    print(f"--- {qid} [{lab}] subj={sid} parent={par} labs={labels(qid)}")
    print("    stem:", (st or '').replace('\n', ' '))
    print("    pstem:", pst)

print()
print("===== B. papers of the 5 WMA02 trapezium questions + 57128: all qids =====")
for anchor in [57767, 58571, 59378, 59848, 60398, 57128]:
    pid = paper_of(anchor)
    print(f"### paper {pid} (anchor {anchor})")
    for qid, lab, par, st in cur.execute(
            "select id, number_label, parent_id, substr(stem_text,1,110) from question "
            "where paper_id=? order by id", (pid,)).fetchall():
        print(f"  {qid} [{lab}] par={par} labs={labels(qid)}")
        print("      ", (st or '').replace('\n', ' '))

print()
print("===== C. all MS rows on paper of 60724 (Q13 insects) =====")
pid = paper_of(60724)
for qid, lab, num in cur.execute(
        "select id, number_label, paper_id from question where paper_id=? order by id",
        (pid,)).fetchall():
    mss = cur.execute(
        "select answer_text from mark_scheme_entry where question_id=?", (qid,)).fetchall()
    if mss:
        for mm in mss:
            print(f"--- MS {qid} [{num}]:", (mm[0] or '').replace('\n', ' ')[:400])

print()
print("===== D. all MS rows on paper of 60918 (Q9 parametric) =====")
pid = paper_of(60918)
for qid, num in cur.execute(
        "select id, number_label from question where paper_id=? order by id",
        (pid,)).fetchall():
    mss = cur.execute(
        "select answer_text from mark_scheme_entry where question_id=?", (qid,)).fetchall()
    if mss:
        for mm in mss:
            print(f"--- MS {qid} [{num}]:", (mm[0] or '').replace('\n', ' ')[:400])

print()
print("===== E. search MS text for 240 / 16e / 3.8 (insects) =====")
for qid, txt in cur.execute(
        "select question_id, substr(answer_text,1,200) from mark_scheme_entry "
        "where answer_text like '%240%' or answer_text like '%16e%'").fetchall():
    print(f"--- {qid}:", (txt or '').replace('\n', ' '))

print()
print("===== F. search MS text for 8cos / parametric (60918 paper) =====")
for qid, txt in cur.execute(
        "select question_id, substr(answer_text,1,200) from mark_scheme_entry "
        "where answer_text like '%8cos%' or answer_text like '%parametric%'").fetchall():
    print(f"--- {qid}:", (txt or '').replace('\n', ' '))

con.close()
