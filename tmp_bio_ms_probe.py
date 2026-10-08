"""Read-only probe: MS doc 97 (bio rms compact numbering) + matched QP paths.

Prints:
- matched QP document + canonical question paths (first 40)
- current _ms_anchors output (page, token)
- all left-column tokens on MS pages (x < 0.16w, y in 4%..90%) that are NOT
  matched by the current _MS_NUMBER, to see the real token shapes
- index_ms_questions result count/source
"""
import re
import sqlite3
import sys
from pathlib import Path

import pymupdf

sys.path.insert(0, "src")
from examdata.edexcel_papers.pipeline import (  # noqa: E402
    _MS_LEAD,
    _MS_NUMBER,
    _ms_anchors,
    index_ms_questions,
)

DB = "file:.data/examdata.db?mode=ro"
DOC_ID = 97


def main() -> int:
    con = sqlite3.connect(DB, uri=True)
    cur = con.cursor()
    row = cur.execute(
        """
        SELECT ms.id, ms.document_id, ms.matched_paper_document_id
        FROM mark_scheme ms WHERE ms.document_id = ?
        """,
        (DOC_ID,),
    ).fetchone()
    print("ms row:", row)
    ms_id, doc_id, qp_doc_id = row

    ms_key = cur.execute(
        """
        SELECT a.storage_key FROM document d
        JOIN document_revision dr ON dr.id = d.current_revision_id
        JOIN artifact a ON a.id = dr.artifact_id WHERE d.id = ?
        """,
        (doc_id,),
    ).fetchone()[0]
    ms_bytes = Path(f".data/artifacts/{ms_key}").read_bytes()

    qp_key = cur.execute(
        """
        SELECT a.storage_key FROM document d
        JOIN document_revision dr ON dr.id = d.current_revision_id
        JOIN artifact a ON a.id = dr.artifact_id WHERE d.id = ?
        """,
        (qp_doc_id,),
    ).fetchone()[0]
    qp_paths = [
        r[0]
        for r in cur.execute(
            """
            SELECT q.number_path FROM question q
            JOIN paper p ON p.id = q.paper_id
            WHERE p.document_id = ? ORDER BY q.id
            """,
            (qp_doc_id,),
        )
    ]
    print(f"matched QP doc {qp_doc_id}, {len(qp_paths)} questions")
    print("first 40 paths:", qp_paths[:40])

    anchors = _ms_anchors(pymupdf.open(stream=ms_bytes, filetype="pdf"))
    print(f"\ncurrent _ms_anchors: {len(anchors)} anchors")
    for page, number, head in anchors[:40]:
        print(f"  page {page} y={head[1]:.1f} x={head[0]:.1f} {number!r}")

    wanted = set(qp_paths)
    compact = {p.replace("(", "").replace(")", ""): p for p in qp_paths}
    print(f"\ncompact map sample: {list(compact.items())[:20]}")

    print("\n--- left-column tokens not matched by current _MS_NUMBER ---")
    with pymupdf.open(stream=ms_bytes, filetype="pdf") as pdf:
        for index, page in enumerate(pdf):
            bounds = page.rect * page.derotation_matrix
            lines: dict[int, list] = {}
            for word in page.get_text("words"):
                if not bounds.height * 0.04 < word[1] < bounds.height * 0.9:
                    continue
                lines.setdefault(round(word[1] / 3), []).append(word)
            for words in lines.values():
                words.sort(key=lambda w: w[0])
                for head in words[:2]:
                    if head[0] >= bounds.width * 0.16:
                        break
                    token = _MS_LEAD.sub("", head[4])
                    if _MS_NUMBER.match(token):
                        continue
                    if re.fullmatch(r"[1-9]\d{0,2}[a-z]{1,10}", token):
                        mark = " <-- compact"
                    else:
                        mark = ""
                    print(
                        f"  p{index} y={head[1]:.1f} x={head[0]:.1f} "
                        f"{token!r} direct={token in wanted} "
                        f"compact={compact.get(token)!r}{mark}"
                    )

    index, source = index_ms_questions(ms_bytes, qp_paths)
    print(f"\nindex_ms_questions: {len(index)} items, source={source}")
    for item in index[:15]:
        print("  ", item["question"], len(item["regions"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
