"""只读：per-subject 状态表 — spec 点数/试卷数/题目数/已标注数。

用法: python tmp_subject_state.py [--json out.json]
"""
import json
import sqlite3
import sys

sys.path.insert(0, "src")


def main() -> None:
    out_path = None
    if "--json" in sys.argv:
        out_path = sys.argv[sys.argv.index("--json") + 1]
    con = sqlite3.connect("file:.data/examdata.db?mode=ro", uri=True)
    cur = con.cursor()

    # spec points per subject via attrs.subject
    points: dict[str, int] = {}
    for (attrs,) in cur.execute("select attrs from taxonomy_node where board_id=2"):
        if not attrs:
            continue
        try:
            slug = json.loads(attrs).get("subject")
        except Exception:
            continue
        if slug:
            points[slug] = points.get(slug, 0) + 1

    subjects = cur.execute(
        "select id, slug from subject where qualification_id=4 order by id"
    ).fetchall()

    out = []
    for sid, slug in subjects:
        row = {"slug": slug, "spec_points": points.get(slug, 0)}

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
        row["tagged"] = one(
            "select count(distinct qt.question_id) from question_taxonomy qt "
            "join question q on q.id=qt.question_id join paper p on q.paper_id=p.id "
            "join document d on p.document_id=d.id where d.subject_id=?",
            sid,
        )
        row["tag_rows"] = one(
            "select count(*) from question_taxonomy qt "
            "join question q on q.id=qt.question_id join paper p on q.paper_id=p.id "
            "join document d on p.document_id=d.id where d.subject_id=?",
            sid,
        )
        out.append(row)

    if out_path:
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(out, fh, ensure_ascii=False, indent=1)

    print(
        f"{'slug':28s} {'spec':>5s} {'qp':>4s} {'ms':>4s} {'papers':>6s} {'questions':>9s} {'tagged':>7s} {'tagrows':>7s}"
    )
    for r in out:
        print(
            f"{r['slug']:28s} {r['spec_points']:5d} {r['qp_docs']:4d} {r['ms_docs']:4d} "
            f"{r['papers']:6d} {r['questions']:9d} {r['tagged']:7d} {r['tag_rows']:7d}"
        )
    print(f"written {out_path}" if out_path else "done")


if __name__ == "__main__":
    main()
