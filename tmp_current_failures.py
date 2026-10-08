"""只读：每个文档取最新 parse_run，列出真实当前失败。

用法: python tmp_current_failures.py [out.json]
"""
import json
import sqlite3
import sys

sys.path.insert(0, "src")


def main() -> None:
    out_path = sys.argv[1] if len(sys.argv) > 1 else "tmp_current_failures.json"
    con = sqlite3.connect("file:.data/examdata.db?mode=ro", uri=True)
    cur = con.cursor()

    # latest parse_run id per document (across all revisions of the doc)
    rows = cur.execute(
        """
        select d.subject_id, s.slug, d.id, dr.id, pr.id, pr.status, pr.error, pr.finished_at
        from parse_run pr
        join document_revision dr on dr.id = pr.document_revision_id
        join document d on d.id = dr.document_id
        join subject s on s.id = d.subject_id
        where pr.parser_version = 'edexcel-papers-1'
        order by pr.id
        """
    ).fetchall()

    latest: dict[int, dict] = {}
    for sid, slug, doc_id, rev_id, run_id, status, error, finished in rows:
        latest[doc_id] = {
            "subject_id": sid,
            "slug": slug,
            "doc": doc_id,
            "rev": rev_id,
            "run": run_id,
            "status": status,
            "error": (error or "")[:300],
            "finished": finished,
        }

    failed = [v for v in latest.values() if v["status"] == "failed"]
    failed.sort(key=lambda x: (x["slug"], x["doc"]))

    out = {"total_docs_with_runs": len(latest), "failed": failed}
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)

    by_slug: dict[str, list] = {}
    for f in failed:
        by_slug.setdefault(f["slug"], []).append(f)
    for slug, items in sorted(by_slug.items()):
        print(f"{slug}: {len(items)} failed")
        for f in items:
            print(f"  doc {f['doc']} run {f['run']}: {f['error']}")
    print(f"total docs with runs: {len(latest)}; failed: {len(failed)}; written {out_path}")


if __name__ == "__main__":
    main()
