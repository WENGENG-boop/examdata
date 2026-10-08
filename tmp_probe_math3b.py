"""Probe: dump full words for 1461 p7/p10, 1462 p7/p10, 1491 p6/p7 (read-only)."""
import sqlite3
import sys
from pathlib import Path

import pymupdf

sys.path.insert(0, "src")

DB = "file:.data/examdata.db?mode=ro"
CASES = [(1461, [7, 10]), (1462, [7, 10]), (1491, [6, 7, 8])]


def main() -> int:
    con = sqlite3.connect(DB, uri=True)
    cur = con.cursor()
    for doc_id, pages in CASES:
        key_row = cur.execute(
            """SELECT a.storage_key FROM document d
            JOIN document_revision dr ON dr.id = d.current_revision_id
            JOIN artifact a ON a.id = dr.artifact_id WHERE d.id = ?""",
            (doc_id,),
        ).fetchone()
        data = Path(f".data/artifacts/{key_row[0]}").read_bytes()
        with pymupdf.open(stream=data, filetype="pdf") as pdf:
            for page_no in pages:
                page = pdf[page_no - 1]
                print(f"\n##### doc {doc_id} page {page_no} #####")
                words = []
                for word in page.get_text("words"):
                    rect = pymupdf.Rect(word[:4]) * page.rotation_matrix
                    words.append((round(rect.y0, 1), round(rect.x0, 1), round(rect.x1, 1), word[4]))
                words.sort()
                # group into lines by y
                line: list = []
                last_y = None
                for y, x0, x1, text in words:
                    if last_y is None or abs(y - last_y) <= 2.0:
                        line.append((x0, text))
                    else:
                        print("  " + f"{last_y:7.1f} | " + " ".join(f"{t}@{x:.0f}" for x, t in line))
                        line = [(x0, text)]
                    last_y = y
                if line:
                    print("  " + f"{last_y:7.1f} | " + " ".join(f"{t}@{x:.0f}" for x, t in line))
    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
