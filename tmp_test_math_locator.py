"""Verify locator fix: math QP/MS parse; regression on wst/chemistry."""
import sqlite3
import sys

import pymupdf

from examdata.paperqa.locator import index_questions, locate
from examdata.edexcel_papers.pipeline import index_ms_questions

DB = "file:.data/examdata.db?mode=ro"


def artifact_path(cur, doc_id):
    row = cur.execute(
        """
        SELECT a.storage_key FROM document d
        JOIN document_revision dr ON dr.id = d.current_revision_id
        JOIN artifact a ON a.id = dr.artifact_id
        WHERE d.id = ?
        """,
        (doc_id,),
    ).fetchone()
    return f".data/artifacts/{row[0]}" if row else None


def check_qp(path, label, want_sample=None):
    data = open(path, "rb").read()
    index = index_questions(data, "qp")
    paths = [item["question"] for item in index]
    print(f"{label}: {len(paths)} paths")
    print(f"   first 12: {paths[:12]}")
    if want_sample:
        for q in want_sample:
            with pymupdf.open(stream=data, filetype="pdf") as pdf:
                try:
                    clips = locate(pdf, q, "qp")
                    pages = [p + 1 for p, _ in clips]
                    print(f"   locate {q!r}: pages {pages}")
                except Exception as exc:
                    print(f"   locate {q!r}: FAILED {exc}")
    return paths


def main():
    con = sqlite3.connect(DB, uri=True)
    cur = con.cursor()

    # math QP doc 1338
    qp_path = artifact_path(cur, 1338)
    qp_paths = check_qp(qp_path, "math QP 1338 (wme02-01)", want_sample=["1", "3", "8"])

    # math MS doc 1563 (wma11-01) — needs wanted paths from its QP; use qp 1338 paths
    ms_path = artifact_path(cur, 1563)
    ms_data = open(ms_path, "rb").read()
    index, source = index_ms_questions(ms_data, qp_paths)
    print(f"math MS 1563 vs QP1338 paths: {len(index)} matched, source={source}")

    # math MS with its own QP: find wma11 QP doc
    row = cur.execute(
        """
        SELECT d.id FROM document d
        WHERE d.subject_id=24 AND d.doc_type='question_paper' AND d.paper_code='wma11-01'
        ORDER BY d.id DESC LIMIT 1
        """
    ).fetchone()
    if row:
        wma_qp = artifact_path(cur, row[0])
        qp_paths2 = check_qp(wma_qp, f"math QP {row[0]} (wma11-01)")
        index2, source2 = index_ms_questions(ms_data, qp_paths2)
        print(f"math MS 1563 vs QP{row[0]} paths: {len(index2)} matched, source={source2}")
        if index2:
            print(f"   sample: {[i['question'] for i in index2[:10]]}")

    # regression: wst03 QP (bare numbers)
    check_qp(artifact_path(cur, 517), "wst03 QP 517 (regression)")

    # regression: chemistry QP doc 1287
    check_qp(artifact_path(cur, 1287), "chem QP 1287 (regression)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
