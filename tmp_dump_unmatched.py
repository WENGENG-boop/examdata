"""只读：列出 chem/phys/math 所有 matched_paper=NULL 的 MS，并给出同考季 QP 候选。"""
import sqlite3

DB = ".data/examdata.db"
con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
cur = con.cursor()

print("== subjects ==")
for row in cur.execute("select id, code, title from subject order by id"):
    print(row)

for sid in (21, 24, 25):
    print(f"\n===== subject {sid} =====")
    rows = cur.execute(
        """
        select ms.id, ms.document_id, ms.match_method, ms.match_confidence,
               d.series_id, d.paper_code, d.title, d.doc_type,
               (select count(*) from mark_scheme_entry e where e.mark_scheme_id=ms.id) as n
        from mark_scheme ms join document d on d.id = ms.document_id
        where d.subject_id=? and ms.matched_paper_document_id is null
        order by d.series_id, ms.id
        """,
        (sid,),
    ).fetchall()
    for msid, did, method, conf, serid, pcode, title, dtype, n in rows:
        print(f"  ms={msid} doc={did} ser={serid} code={pcode!r} n={n} type={dtype}")
        print(f"      title={title!r}")
        qps = cur.execute(
            "select id, paper_code, title, doc_type from document where subject_id=? and series_id=? and doc_type='question_paper' order by id",
            (sid, serid),
        ).fetchall()
        for qid, qcode, qtitle, qdtype in qps:
            print(f"        qp {qid} code={qcode!r} title={qtitle!r}")
con.close()
