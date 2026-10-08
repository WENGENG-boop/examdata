"""Scan left-column question-number token formats across subjects.

- For the failing math QP: print all number-like tokens (incl. trailing period) per page.
- For already-parsed subjects (chemistry/physics/business/economics/biology): find
  tokens that are number+period in the left column, to assess whether loosening the
  locator regex could create stray anchors in those papers.
"""
import re
import sqlite3
import sys

import pymupdf

DB = "file:.data/examdata.db?mode=ro"
STRICT = re.compile(r"[1-9]\d{0,2}\.")   # only tokens WITH trailing period
LOOSE = re.compile(r"[1-9]\d{0,2}\.?")   # with or without period


def left_col_hits(path, pattern):
    doc = pymupdf.open(path)
    hits = []
    for index in range(len(doc)):
        page = doc[index]
        b = page.rect
        for w in page.get_text("words"):
            x0, y0, text = w[0], w[1], w[4]
            if not (b.height * 0.04 < y0 < b.height * 0.9):
                continue
            if x0 < b.width * 0.125 and pattern.fullmatch(text):
                hits.append((index, round(y0, 1), text))
    doc.close()
    return hits


def artifact_of(cur, doc_id):
    row = cur.execute(
        """
        SELECT a.storage_key FROM document d
        JOIN document_revision dr ON dr.id = d.current_revision_id
        JOIN artifact a ON a.id = dr.artifact_id
        WHERE d.id = ?
        """,
        (doc_id,),
    ).fetchone()
    return row[0] if row else None


def main():
    con = sqlite3.connect(DB, uri=True)
    cur = con.cursor()

    math_doc = 1338
    key = artifact_of(cur, math_doc)
    path = f".data/artifacts/{key}"
    print(f"=== math QP doc {math_doc}: all loose number tokens per page ===")
    hits = left_col_hits(path, LOOSE)
    print(f"total loose tokens: {len(hits)}")
    by_page = {}
    for page, y, text in hits:
        by_page.setdefault(page, []).append(text)
    for page in sorted(by_page):
        print(f"  page {page}: {by_page[page]}")
    strict = [h for h in hits if STRICT.fullmatch(h[2])]
    print(f"  strict (with period): {len(strict)}")

    print()
    print("=== other subjects: number+period tokens in left column (risk scan) ===")
    for slug in [
        "ial18-chemistry",
        "ial18-physics",
        "ial18-business",
        "ial18-economics",
        "ial18-biology",
    ]:
        row = cur.execute(
            """
            SELECT d.id FROM document d
            JOIN subject s ON s.id = d.subject_id
            JOIN parse_run pr ON pr.document_revision_id = d.current_revision_id
            WHERE s.slug = ? AND d.doc_type = 'question_paper' AND pr.status = 'completed'
            ORDER BY d.id DESC LIMIT 1
            """,
            (slug,),
        ).fetchone()
        if not row:
            print(f"  {slug}: no completed QP found")
            continue
        doc_id = row[0]
        key = artifact_of(cur, doc_id)
        if not key:
            print(f"  {slug}: doc {doc_id} has no artifact")
            continue
        hits = left_col_hits(f".data/artifacts/{key}", STRICT)
        print(f"  {slug} (doc {doc_id}): {len(hits)} number+period left-col tokens")
        for page, y, text in hits[:12]:
            print(f"      page {page} y={y} {text!r}")


if __name__ == "__main__":
    sys.exit(main())
