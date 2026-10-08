"""只读：dump 某文档 PDF 每页每行的最左两个词（_ms_anchors 实际输入）。

用法: python tmp_probe_leftcol.py <doc_id> [<doc_id> ...]
"""
import sqlite3
import sys

import pymupdf

sys.path.insert(0, "src")

from examdata.core.config import get_settings
from examdata.core.storage import ContentAddressedStore


def dump(con, store, doc_id: int) -> None:
    row = con.execute(
        """
        select d.doc_type, d.paper_code, a.storage_key
        from document d
        join document_revision r on r.id = d.current_revision_id
        join artifact a on a.id = r.artifact_id
        where d.id = ?
        """,
        (doc_id,),
    ).fetchone()
    if not row:
        print(f"doc {doc_id}: not found")
        return
    doc_type, code, key = row
    path = store.path_for_key(key)
    print(f"===== doc {doc_id} type={doc_type} code={code} =====", flush=True)
    with pymupdf.open(path) as pdf:
        for index, page in enumerate(pdf):
            if index == 0:
                continue
            bounds = page.rect
            rotation = page.rotation_matrix
            lines: dict[int, list] = {}
            for w in page.get_text("words"):
                rect = pymupdf.Rect(w[:4]) * rotation
                if not bounds.height * 0.04 < rect.y0 < bounds.height * 0.9:
                    continue
                lines.setdefault(round(rect.y0 / 3), []).append((rect, w[4]))
            if not lines:
                continue
            print(f"-- page {index + 1} --")
            for key_ in sorted(lines):
                words = sorted(lines[key_], key=lambda t: t[0].x0)
                head = words[0][0]
                if head.x0 >= bounds.width * 0.25:
                    continue
                shown = " | ".join(
                    f"{t[1]!r}@{round(t[0].x0, 1)},{round(t[0].y0, 1)}"
                    for t in words[:3]
                )
                print("   " + shown)


def main() -> None:
    settings = get_settings()
    store = ContentAddressedStore(settings.artifacts_dir)
    con = sqlite3.connect("file:.data/examdata.db?mode=ro", uri=True)
    for doc_id in [int(x) for x in sys.argv[1:]]:
        dump(con, store, doc_id)


if __name__ == "__main__":
    main()
