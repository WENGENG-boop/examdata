"""只读：重切前后 per-subject 统计快照。

用法: python tmp_split_check.py <out.json>
"""
import json
import sqlite3
import sys

sys.path.insert(0, "src")

from examdata.edexcel_papers.pipeline import PARSER_VERSION


def main() -> None:
    out_path = sys.argv[1] if len(sys.argv) > 1 else "tmp_split_check.json"
    con = sqlite3.connect("file:.data/examdata.db?mode=ro", uri=True)
    cur = con.cursor()

    subjects = cur.execute("select id, code, title from subject order by id").fetchall()
    out = []
    for sid, code, title in subjects:
        row = {"id": sid, "code": code, "title": title}

        def one(sql: str, *args):
            return cur.execute(sql, args).fetchone()[0]

        row["qp_docs"] = one(
            "select count(*) from document where subject_id=? and doc_type='question_paper'", sid
        )
        row["ms_docs"] = one(
            "select count(*) from document where subject_id=? and doc_type='mark_scheme'", sid
        )
        row["papers"] = one(
            "select count(*) from paper p join document d on d.id=p.document_id where d.subject_id=?",
            sid,
        )
        row["questions"] = one(
            "select count(*) from question q join paper p on q.paper_id=p.id "
            "join document d on p.document_id=d.id where d.subject_id=?",
            sid,
        )
        row["questions_with_marks"] = one(
            "select count(*) from question q join paper p on q.paper_id=p.id "
            "join document d on p.document_id=d.id where d.subject_id=? and q.marks is not null",
            sid,
        )
        row["ms_matched"] = one(
            "select count(*) from mark_scheme ms join document d on d.id=ms.document_id "
            "where d.subject_id=? and ms.matched_paper_document_id is not null",
            sid,
        )
        row["ms_unmatched"] = one(
            "select count(*) from mark_scheme ms join document d on d.id=ms.document_id "
            "where d.subject_id=? and ms.matched_paper_document_id is null",
            sid,
        )

        n_regions = 0
        for (attrs,) in cur.execute(
            "select q.attrs from question q join paper p on q.paper_id=p.id "
            "join document d on p.document_id=d.id where d.subject_id=?",
            (sid,),
        ):
            if attrs:
                try:
                    if json.loads(attrs).get("ms_regions"):
                        n_regions += 1
                except Exception:
                    pass
        row["questions_with_ms_regions"] = n_regions

        fails = cur.execute(
            """
            select d.id, pr.error, pr.id
            from parse_run pr
            join document_revision r on r.id = pr.document_revision_id
            join document d on d.id = r.document_id
            where d.subject_id = ? and pr.status = 'failed' and pr.parser_version = ?
            order by pr.id
            """,
            (sid, PARSER_VERSION),
        ).fetchall()
        latest: dict[int, dict] = {}
        for doc_id, error, run_id in fails:
            latest[doc_id] = {"doc": doc_id, "error": (error or "")[:300], "run": run_id}
        row["failed_docs"] = sorted(latest.values(), key=lambda x: x["doc"])
        out.append(row)

    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    for r in out:
        print(
            json.dumps(
                {
                    k: r[k]
                    for k in (
                        "id",
                        "code",
                        "papers",
                        "questions",
                        "questions_with_marks",
                        "questions_with_ms_regions",
                        "ms_matched",
                        "ms_unmatched",
                    )
                },
                ensure_ascii=False,
            )
        )
        if r["failed_docs"]:
            print(f"    failed docs: {[f['doc'] for f in r['failed_docs']]}")
    print(f"written {out_path}")


if __name__ == "__main__":
    main()
