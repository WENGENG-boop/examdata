"""Verify the MS table index fix on the 9 stuck bio docs (read-only).

For each doc: run index_ms_questions, report count/source, missing wanted paths,
and spot-check that region text extraction works for doc 286 (rotated) and 97
(compact + merge).
"""
import sqlite3
import sys
from pathlib import Path

import pymupdf

sys.path.insert(0, "src")
from examdata.edexcel_papers.pipeline import index_ms_questions  # noqa: E402

DB = "file:.data/examdata.db?mode=ro"
DOCS = [97, 117, 119, 171, 175, 211, 242, 245, 286]


def main() -> int:
    con = sqlite3.connect(DB, uri=True)
    cur = con.cursor()
    for doc_id in DOCS:
        ms_id, qp_doc = cur.execute(
            "SELECT ms.id, ms.matched_paper_document_id FROM mark_scheme ms WHERE ms.document_id = ?",
            (doc_id,),
        ).fetchone()
        key = cur.execute(
            """SELECT a.storage_key FROM document d
            JOIN document_revision dr ON dr.id = d.current_revision_id
            JOIN artifact a ON a.id = dr.artifact_id WHERE d.id = ?""",
            (doc_id,),
        ).fetchone()[0]
        qp_paths = [
            r[0]
            for r in cur.execute(
                """SELECT q.number_path FROM question q JOIN paper p ON p.id = q.paper_id
                WHERE p.document_id = ?""",
                (qp_doc,),
            )
        ]
        data = Path(f".data/artifacts/{key}").read_bytes()
        index, source = index_ms_questions(data, qp_paths)
        got = {item["question"] for item in index}
        missing = [p for p in qp_paths if p not in got]
        print(f"doc {doc_id} (ms={ms_id}, qp={qp_doc}): {len(index)}/{len(qp_paths)} indexed, source={source}")
        if missing:
            print(f"   missing: {missing}")
        if doc_id in (97, 286):
            with pymupdf.open(stream=data, filetype="pdf") as pdf:
                for item in index:
                    if item["question"] in ("1(b)(ii)", "3(d)(ii)", "2(a)(iv)"):
                        for region in item["regions"]:
                            page = pdf[region["page"] - 1]
                            text = page.get_text(clip=pymupdf.Rect(region["bbox"]))
                            preview = " ".join(text.split())[:70]
                            print(
                                f"   {item['question']} p{region['page']} "
                                f"bbox={region['bbox']} text={preview!r}"
                            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
