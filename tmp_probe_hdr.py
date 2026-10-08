"""Probe: print full 'Notes for question' header lines for math MS docs (read-only)."""
import sqlite3
import sys
from pathlib import Path

import pymupdf

DB = "file:.data/examdata.db?mode=ro"
CASES = [(1461, [7, 10, 13, 15, 17, 19, 21, 23]), (1462, [6, 7, 10, 13, 16]), (1491, [6, 7])]


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
            print(f"##### doc {doc_id} pages={pdf.page_count}", flush=True)
            for index, page in enumerate(pdf):
                if index == 0:
                    continue
                rot = page.rotation_matrix
                words = []
                for word in page.get_text("words"):
                    rect = pymupdf.Rect(word[:4]) * rot
                    words.append((round(rect.y0, 1), round(rect.x0, 1), word[4]))
                words.sort()
                lines: dict[float, list] = {}
                for y, x0, text in words:
                    lines.setdefault(round(y / 3), []).append((x0, text))
                for key in sorted(lines):
                    texts = [t.strip().lower() for _x, t in lines[key]]
                    if "notes" in texts[:5]:
                        line = sorted(lines[key])
                        print(
                            f"  p{index + 1}: " + " ".join(f"{t}@{x:.0f}" for x, t in line),
                            flush=True,
                        )
    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
