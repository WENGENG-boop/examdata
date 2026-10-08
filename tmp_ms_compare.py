"""只读对比：对所有 matched MS 跑 index_ms_questions，输出 JSON 快照。

用法: python tmp_ms_compare.py <out.json> [subject_ids...]
默认 subject 19..26。
"""
import json
import sqlite3
import sys
import time

sys.path.insert(0, "src")

from examdata.core.config import get_settings
from examdata.core.storage import ContentAddressedStore
from examdata.edexcel_papers.pipeline import index_ms_questions


def main() -> None:
    out_path = sys.argv[1] if len(sys.argv) > 1 else "tmp_ms_compare.json"
    subjects = [int(x) for x in sys.argv[2:]] or [19, 20, 21, 22, 23, 24, 25, 26]
    settings = get_settings()
    store = ContentAddressedStore(settings.artifacts_dir)
    con = sqlite3.connect("file:.data/examdata.db?mode=ro", uri=True)
    cur = con.cursor()

    results = []
    for sid in subjects:
        rows = cur.execute(
            """
            select ms.id, ms.document_id, ms.matched_paper_document_id
            from mark_scheme ms
            join document d on d.id = ms.document_id
            where d.subject_id = ? and ms.matched_paper_document_id is not null
            order by ms.id
            """,
            (sid,),
        ).fetchall()
        print(f"subject {sid}: {len(rows)} matched MS", flush=True)
        for ms_id, ms_doc_id, qp_doc_id in rows:
            row = cur.execute(
                """
                select a.storage_key
                from document d
                join document_revision r on r.id = d.current_revision_id
                join artifact a on a.id = r.artifact_id
                where d.id = ?
                """,
                (ms_doc_id,),
            ).fetchone()
            qp_paths = [
                r[0]
                for r in cur.execute(
                    """
                    select q.number_path from question q
                    join paper p on p.id = q.paper_id
                    where p.document_id = ?
                    """,
                    (qp_doc_id,),
                ).fetchall()
                if r[0]
            ]
            record = {
                "ms_id": ms_id,
                "ms_doc": ms_doc_id,
                "qp_doc": qp_doc_id,
                "n_qp_paths": len(qp_paths),
            }
            t0 = time.time()
            if not row or not row[0]:
                record["error"] = "no artifact key"
            else:
                path = store.path_for_key(row[0])
                if not path.exists():
                    record["error"] = f"artifact missing: {path}"
                else:
                    data = path.read_bytes()
                    index, source = index_ms_questions(data, qp_paths)
                    record["n_index"] = len(index)
                    record["source"] = source
                    record["paths"] = sorted(item["question"] for item in index)
            record["seconds"] = round(time.time() - t0, 2)
            results.append(record)
            flag = (
                "!!"
                if "error" in record or record.get("n_index", -1) == 0
                else "  "
            )
            print(
                f"{flag} ms={ms_id} doc={ms_doc_id} qp={qp_doc_id} "
                f"n={record.get('n_index')} src={record.get('source')} "
                f"{record['seconds']}s {record.get('error', '')}",
                flush=True,
            )

    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(
            {"subjects": subjects, "results": results},
            fh,
            ensure_ascii=False,
            indent=1,
        )
    print(f"written {out_path}: {len(results)} records", flush=True)


if __name__ == "__main__":
    main()
