"""词级 dump：打印某页全部词（x 过滤），按 y 分行，用于判断数字是题号还是内容。

用法: python tmp_words.py <doc> <page> [xmax_frac] [y0 y1]
"""
import sqlite3
import sys

import pymupdf

sys.path.insert(0, "src")

from examdata.core.config import get_settings
from examdata.core.storage import ContentAddressedStore


def main() -> None:
    doc_id = int(sys.argv[1])
    page_no = int(sys.argv[2])
    xmax = float(sys.argv[3]) if len(sys.argv) > 3 else 0.45
    y0 = float(sys.argv[4]) if len(sys.argv) > 5 else None
    y1 = float(sys.argv[5]) if len(sys.argv) > 5 else None
    con = sqlite3.connect("file:.data/examdata.db?mode=ro", uri=True)
    row = con.execute(
        """
        select a.storage_key from document d
        join document_revision r on r.id = d.current_revision_id
        join artifact a on a.id = r.artifact_id where d.id = ?
        """,
        (doc_id,),
    ).fetchone()
    store = ContentAddressedStore(get_settings().artifacts_dir)
    data = store.path_for_key(row[0]).read_bytes()
    with pymupdf.open(stream=data, filetype="pdf") as pdf:
        page = pdf[page_no - 1]
        bounds = page.rect
        rot = page.rotation_matrix
        words = []
        for word in page.get_text("words"):
            rect = pymupdf.Rect(word[:4]) * rot
            if rect.x0 >= bounds.width * xmax:
                continue
            if y0 is not None and not (y0 <= rect.y0 <= y1):
                continue
            words.append((rect.y0, rect.x0, word[4]))
        for y, x, t in sorted(words):
            print(f"y={y:6.1f} x={x:6.1f} {t!r}")


if __name__ == "__main__":
    main()
