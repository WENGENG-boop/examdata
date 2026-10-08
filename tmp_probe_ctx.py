"""只读：对 scan 输出中指定文档的每个裸数字锚点，dump 所在行完整上下文。

用法: python tmp_probe_ctx.py <doc_id> [<doc_id> ...]
"""
import sqlite3
import sys

import pymupdf

sys.path.insert(0, "src")

from examdata.core.config import get_settings
from examdata.core.storage import ContentAddressedStore

SCAN = "tmp_scan_bare_out.txt"


def parse_scan(doc_ids: set[int]):
    entries: dict[int, list[tuple[int, str, float, float, float]]] = {}
    with open(SCAN, encoding="utf-8") as fh:
        for line in fh:
            parts = line.split()
            if len(parts) < 9 or not parts[0][0].isdigit():
                continue
            doc = int(parts[2].split("=")[1])
            if doc not in doc_ids:
                continue
            page = int(parts[3][1:])
            token = parts[4].strip("'")
            x = float(parts[5].split("=")[1])
            y = float(parts[6].split("=")[1])
            entries.setdefault(doc, []).append((page, token, x, y, 0.0))
    return entries


def dump(con, store, doc_id: int, targets: list) -> None:
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
    by_page: dict[int, list] = {}
    for t in targets:
        by_page.setdefault(t[0], []).append(t)
    with pymupdf.open(path) as pdf:
        for page_no in sorted(by_page):
            if page_no - 1 >= len(pdf):
                continue
            page = pdf[page_no - 1]
            bounds = page.rect
            rotation = page.rotation_matrix
            words = []
            for w in page.get_text("words"):
                rect = pymupdf.Rect(w[:4]) * rotation
                words.append((rect, w[4]))
            words.sort(key=lambda t: (round(t[0].y0, 1), t[0].x0))
            for _page, token, x, y, _ in sorted(by_page[page_no], key=lambda t: t[3]):
                print(f"-- p{page_no} target {token!r}@{x},{y} W={round(bounds.width)} --")
                sel = [
                    (rect, text)
                    for rect, text in words
                    if y - 8 <= rect.y0 <= y + 8 and rect.x0 < bounds.width * 0.62
                ]
                sel.sort(key=lambda t: t[0].x0)
                print(
                    "   " + " | ".join(
                        f"{t[1]!r}@{round(t[0].x0,1)},{round(t[0].y0,1)}" for t in sel
                    )
                )


def main() -> None:
    settings = get_settings()
    store = ContentAddressedStore(settings.artifacts_dir)
    con = sqlite3.connect("file:.data/examdata.db?mode=ro", uri=True)
    doc_ids = {int(x) for x in sys.argv[1:]}
    entries = parse_scan(doc_ids)
    for doc_id in sorted(doc_ids):
        if doc_id in entries:
            dump(con, store, doc_id, entries[doc_id])
        else:
            print(f"doc {doc_id}: no bare entries in scan")


if __name__ == "__main__":
    main()
