"""Probe: why do 3 math MS docs still index 0 entries? (read-only)

doc 1461 (ms 881, WME01 Jan 2024), 1462 (ms 882, WST03 Jan 2024),
1491 (ms 884, WMA11 Jan 2025).
Also probe the 6 unmatched chem/phys MS with their candidate QPs:
chem 814/818/1089 -> QPs 803/793/1066 ; phys 1048/1052/1063 -> 1028/1041/1025.
"""
import sqlite3
import sys
from pathlib import Path

import pymupdf

sys.path.insert(0, "src")
from examdata.edexcel_papers.pipeline import index_ms_questions  # noqa: E402

DB = "file:.data/examdata.db?mode=ro"
# (ms_doc, qp_doc_override or None to use matched)
CASES = [
    (1461, None),
    (1462, None),
    (1491, None),
    (814, 803),
    (818, 793),
    (1089, 1066),
    (1048, 1028),
    (1052, 1041),
    (1063, 1025),
]


def main() -> int:
    con = sqlite3.connect(DB, uri=True)
    cur = con.cursor()
    for doc_id, qp_override in CASES:
        row = cur.execute(
            "SELECT ms.id, ms.matched_paper_document_id FROM mark_scheme ms WHERE ms.document_id = ?",
            (doc_id,),
        ).fetchone()
        ms_id, qp_doc = row if row else (None, None)
        if qp_override is not None:
            qp_doc = qp_override
        key_row = cur.execute(
            """SELECT a.storage_key FROM document d
            JOIN document_revision dr ON dr.id = d.current_revision_id
            JOIN artifact a ON a.id = dr.artifact_id WHERE d.id = ?""",
            (doc_id,),
        ).fetchone()
        if key_row is None:
            print(f"doc {doc_id}: no artifact")
            continue
        qp_paths = [
            r[0]
            for r in cur.execute(
                """SELECT q.number_path FROM question q JOIN paper p ON p.id = q.paper_id
                WHERE p.document_id = ?""",
                (qp_doc,),
            )
        ]
        data = Path(f".data/artifacts/{key_row[0]}").read_bytes()
        try:
            index, source = index_ms_questions(data, qp_paths)
        except Exception as exc:  # noqa: BLE001
            print(f"doc {doc_id} (ms={ms_id}, qp={qp_doc}): EXC {type(exc).__name__}: {exc}")
            continue
        got = {item["question"] for item in index}
        missing = [p for p in qp_paths if p not in got]
        print(
            f"doc {doc_id} (ms={ms_id}, qp={qp_doc}): {len(index)}/{len(qp_paths)} "
            f"indexed, source={source}"
        )
        if missing:
            print(f"   missing({len(missing)}): {missing[:25]}")
        if not index:
            # dump a peek of page 1 text to understand the layout
            with pymupdf.open(stream=data, filetype="pdf") as pdf:
                text = pdf[0].get_text()[:600]
                print(f"   page1 text: {text!r}")
                print(f"   pages: {len(pdf)}, first-rect={pdf[0].rect}, rot={pdf[0].rotation}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
