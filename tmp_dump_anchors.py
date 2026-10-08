"""只读：dump 指定文档的 _ms_anchors 全部锚点 + 页面横线位置。

用法: python tmp_dump_anchors.py <doc_id> [<doc_id> ...]
"""
import sqlite3
import sys

import pymupdf

sys.path.insert(0, "src")

from examdata.core.config import get_settings
from examdata.core.storage import ContentAddressedStore
from examdata.edexcel_papers.pipeline import _MS_MAIN, _ms_anchors, _ms_rules


def main() -> None:
    settings = get_settings()
    store = ContentAddressedStore(settings.artifacts_dir)
    con = sqlite3.connect("file:.data/examdata.db?mode=ro", uri=True)
    for ms_doc in [int(x) for x in sys.argv[1:]]:
        row = con.execute(
            """
            select ms.id, ms.matched_paper_document_id, a.storage_key
            from mark_scheme ms
            join document d on d.id = ms.document_id
            join document_revision r on r.id = d.current_revision_id
            join artifact a on a.id = r.artifact_id
            where ms.document_id = ?
            """,
            (ms_doc,),
        ).fetchone()
        if not row:
            print(f"doc {ms_doc}: no MS row")
            continue
        ms_id, qp_doc, key = row
        wanted = {
            r[0]
            for r in con.execute(
                """
                select q.number_path from question q
                join paper p on p.id = q.paper_id
                where p.document_id = ?
                """,
                (qp_doc,),
            )
            if r[0]
        }
        compact = {p.replace("(", "").replace(")", ""): p for p in wanted}
        path = store.path_for_key(key)
        print(f"===== ms={ms_id} doc={ms_doc} qp_doc={qp_doc} wanted={len(wanted)} =====")
        print("wanted: " + " ".join(sorted(wanted)))
        data = path.read_bytes()
        with pymupdf.open(stream=data, filetype="pdf") as pdf:
            anchors = _ms_anchors(pdf, wanted)
            pages: dict[int, list] = {}
            for idx, tok, rect in anchors:
                pages.setdefault(idx, []).append((tok, rect))
            for idx in sorted(pages):
                width = pdf[idx].rect.width
                rules = _ms_rules(pdf[idx], pdf[idx].rect, pdf[idx].rotation_matrix)
                print(f"-- p{idx+1} W={round(width)} rules={[round(r,1) for r in rules]}")
                for tok, rect in sorted(pages[idx], key=lambda t: t[1][1]):
                    acc = tok in wanted or tok.replace("(", "").replace(")", "") in compact
                    kind = "MAIN" if _MS_MAIN.fullmatch(tok) else "alpha"
                    print(
                        f"   {tok!r:>16} x={round(rect[0],1):>6} y={round(rect[1],1):>6} "
                        f"frac={rect[0]/width:.3f} {kind} accepted={int(acc)}"
                    )


if __name__ == "__main__":
    main()
