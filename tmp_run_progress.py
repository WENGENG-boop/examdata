"""只读：run 进度监控 — 各科目已存文档/已切分/最新 parse 状态。

用法: python tmp_run_progress.py [slug...]
"""
import json
import sqlite3
import sys

sys.path.insert(0, "src")


def main() -> None:
    slugs = sys.argv[1:]
    con = sqlite3.connect("file:.data/examdata.db?mode=ro", uri=True)
    cur = con.cursor()

    if slugs:
        placeholders = ",".join("?" for _ in slugs)
        subjects = cur.execute(
            f"select id, slug from subject where slug in ({placeholders}) order by id",
            slugs,
        ).fetchall()
    else:
        subjects = cur.execute("select id, slug from subject order by id").fetchall()

    for sid, slug in subjects:
        n_rev = cur.execute(
            """select count(*) from document_revision dr
               join document d on d.id=dr.document_id where d.subject_id=?""",
            (sid,),
        ).fetchone()[0]
        n_docs = cur.execute(
            "select count(*) from document where subject_id=?", (sid,)
        ).fetchone()[0]
        n_papers = cur.execute(
            "select count(*) from paper p join document d on d.id=p.document_id where d.subject_id=?",
            (sid,),
        ).fetchone()[0]
        n_questions = cur.execute(
            """select count(*) from question q join paper p on q.paper_id=p.id
               join document d on d.id=p.document_id where d.subject_id=?""",
            (sid,),
        ).fetchone()[0]
        # latest parse_run status distribution
        rows = cur.execute(
            """select pr.status, count(*) from parse_run pr
               join document_revision dr on dr.id=pr.document_revision_id
               join document d on d.id=dr.document_id
               where d.subject_id=? and pr.parser_version='edexcel-papers-1'
               group by pr.status""",
            (sid,),
        ).fetchall()
        statuses = {s: n for s, n in rows}
        print(
            f"{slug}: docs={n_docs} revs={n_rev} papers={n_papers} questions={n_questions} parse_runs={statuses}"
        )


if __name__ == "__main__":
    main()
