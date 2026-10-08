"""只读：dump 指定文档页的竖线 + 指定 y 窗口的词序列。

用法: python tmp_probe_lines.py <doc_id>:<page>:<y> [<doc_id>:<page>:<y> ...]
"""
import sqlite3
import sys

import pymupdf

sys.path.insert(0, "src")

from examdata.core.config import get_settings
from examdata.core.storage import ContentAddressedStore


def main() -> None:
    settings = get_settings()
    store = ContentAddressedStore(settings.artifacts_dir)
    con = sqlite3.connect("file:.data/examdata.db?mode=ro", uri=True)
    targets = []
    for arg in sys.argv[1:]:
        doc, page, y = arg.split(":")
        targets.append((int(doc), int(page), float(y)))
    by_doc: dict[int, list] = {}
    for doc, page, y in targets:
        by_doc.setdefault(doc, []).append((page, y))
    for doc_id in sorted(by_doc):
        row = con.execute(
            """
            select a.storage_key from document d
            join document_revision r on r.id = d.current_revision_id
            join artifact a on a.id = r.artifact_id where d.id = ?
            """,
            (doc_id,),
        ).fetchone()
        if not row:
            print(f"doc {doc_id}: not found")
            continue
        path = store.path_for_key(row[0])
        with pymupdf.open(path) as pdf:
            for page_no, y in sorted(by_doc[doc_id]):
                page = pdf[page_no - 1]
                bounds = page.rect
                rot = page.rotation_matrix
                print(f"===== doc {doc_id} p{page_no} W={round(bounds.width)} y0={y} =====")
                vlines = []
                hlines = []
                for drawing in page.get_drawings():
                    rect = pymupdf.Rect(drawing["rect"]) * rot
                    if rect.width < 1.5 and rect.height > 10:
                        vlines.append(round(rect.x0, 1))
                    elif rect.height < 1.5 and rect.width > bounds.width * 0.1:
                        hlines.append((round(rect.y0, 1), round(rect.width, 1)))
                print(f"   vlines: {sorted(set(vlines))}")
                print(f"   hlines: {sorted(set(hlines))}")
                words = []
                for w in page.get_text("words"):
                    rect = pymupdf.Rect(w[:4]) * rot
                    if y - 30 <= rect.y0 <= y + 70 and rect.x0 < bounds.width * 0.62:
                        words.append((rect, w[4]))
                words.sort(key=lambda t: (round(t[0].y0, 1), t[0].x0))
                cur = None
                for rect, text in words:
                    key = round(rect.y0 / 3)
                    if key != cur:
                        cur = key
                        print(f"   y={round(rect.y0,1):>6}: ", end="")
                    print(f"{text!r}@{round(rect.x0,1)} ", end="")
                print()


if __name__ == "__main__":
    main()
