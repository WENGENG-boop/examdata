"""Probe: dump left-column tokens + rules for math MS docs 1461/1462/1491 (read-only)."""
import sqlite3
import sys
from pathlib import Path

import pymupdf

sys.path.insert(0, "src")
from examdata.edexcel_papers.pipeline import (  # noqa: E402
    _MS_LEAD,
    _MS_NUMBER,
    _MS_COMPACT,
    _ms_rules,
)

DB = "file:.data/examdata.db?mode=ro"
CASES = [(1461, None), (1462, None), (1491, None)]


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
        qp_paths = [
            r[0]
            for r in cur.execute(
                """SELECT q.number_path FROM question q JOIN paper p ON p.id = q.paper_id
                WHERE p.document_id = ? ORDER BY q.display_order""",
                (qp_doc,),
            )
        ]
        print(f"\n##### doc {doc_id} (ms={ms_id}, qp={qp_doc}) wanted={qp_paths}")
        data = Path(f".data/artifacts/{key_row[0]}").read_bytes()
        with pymupdf.open(stream=data, filetype="pdf") as pdf:
            for index, page in enumerate(pdf):
                if index == 0:
                    continue
                bounds = page.rect
                rotation = page.rotation_matrix
                rules = _ms_rules(page, bounds, rotation)
                rows = []
                for word in page.get_text("words"):
                    rect = pymupdf.Rect(word[:4]) * rotation
                    if not bounds.height * 0.04 < rect.y0 < bounds.height * 0.9:
                        continue
                    if rect.x0 >= 140:
                        continue
                    text = _MS_LEAD.sub("", word[4])
                    if not text or not text[0].isdigit() and not text.startswith("("):
                        continue
                    rows.append((round(rect.y0, 1), round(rect.x0, 1), text))
                if not rows:
                    continue
                rows.sort()
                print(f"  page {index + 1} (w={bounds.width:.0f}): rules={[round(r,1) for r in rules]}")
                for y, x, text in rows:
                    mark = ""
                    if _MS_NUMBER.fullmatch(text):
                        mark = "NUM"
                    elif _MS_COMPACT.fullmatch(text):
                        mark = "CMP"
                    print(f"      y={y:7.1f} x={x:6.1f} {text!r} {mark}")
    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
