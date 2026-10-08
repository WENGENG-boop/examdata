"""Dump _ms_anchors pre/post gate for given MS docs + per-page calib tokens.

用法: python tmp_anchor_dump.py <ms_doc> [<ms_doc> ...]
pre = margin 1e9 (no gate), post = real margin (current code).
Also prints per-page calib tokens (the predicate tokens used for page_calib).
"""
import sqlite3
import sys

import pymupdf

sys.path.insert(0, "src")

from examdata.core.config import get_settings
from examdata.core.storage import ContentAddressedStore
import examdata.edexcel_papers.pipeline as P

REAL = P._MS_BARE_MARGIN


def calib_tokens(pdf):
    out = {}
    for index, page in enumerate(pdf):
        if index == 0:
            continue
        bounds = page.rect
        rotation = page.rotation_matrix
        toks = []
        for word in page.get_text("words"):
            rect = pymupdf.Rect(word[:4]) * rotation
            if not bounds.height * 0.04 < rect.y0 < bounds.height * 0.9:
                continue
            if rect.x0 >= bounds.width * P._MS_NUMBER_X:
                continue
            token = P._normalize_ms_token(word[4])
            if not any(ch.isalpha() for ch in token):
                continue
            if not (
                P._MS_NUMBER.match(token)
                or P._MS_COMPACT.fullmatch(token)
                or P._MS_PART.fullmatch(token)
            ):
                continue
            toks.append((token, round(rect.x0, 1), round(rect.y0, 1)))
        if toks:
            out[index + 1] = toks
    return out


def main() -> None:
    settings = get_settings()
    store = ContentAddressedStore(settings.artifacts_dir)
    con = sqlite3.connect("file:.data/examdata.db?mode=ro", uri=True)
    for arg in sys.argv[1:]:
        doc = int(arg)
        row = con.execute(
            """
            select a.storage_key, ms.matched_paper_document_id
            from document d
            join document_revision r on r.id = d.current_revision_id
            join artifact a on a.id = r.artifact_id
            left join mark_scheme ms on ms.document_id = d.id
            where d.id = ?
            """,
            (doc,),
        ).fetchone()
        if not row or not row[0]:
            print(f"doc={doc}: no artifact")
            continue
        qp_doc = row[1]
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
        data = store.path_for_key(row[0]).read_bytes()
        with pymupdf.open(stream=data, filetype="pdf") as pdf:
            cal = calib_tokens(pdf)
            P._MS_BARE_MARGIN = 1e9
            pre = P._ms_anchors(pdf, wanted)
            P._MS_BARE_MARGIN = REAL
            post = P._ms_anchors(pdf, wanted)
        P._MS_BARE_MARGIN = REAL
        print(f"===== doc={doc} qp={qp_doc} wanted={sorted(wanted)} =====")
        print("-- calib tokens per page --")
        for p, toks in sorted(cal.items()):
            print(f"  p{p}: " + " ".join(f"{t}@{x},{y}" for t, x, y in toks))
        print("-- PRE anchors --")
        for i, t, r in pre:
            print(f"  p{i+1} {t!r} x={r[0]:.1f} y={r[1]:.1f}")
        print("-- POST anchors --")
        for i, t, r in post:
            print(f"  p{i+1} {t!r} x={r[0]:.1f} y={r[1]:.1f}")
        print()


if __name__ == "__main__":
    main()
