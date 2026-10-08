"""只读扫描：所有 matched MS 的 _ms_anchors 中裸数字锚点的 x/页宽分布。

用法: python tmp_scan_bare.py [out.txt]
"""
import sys

import pymupdf

sys.path.insert(0, "src")

from examdata.core.config import get_settings
from examdata.core.storage import ContentAddressedStore
from examdata.edexcel_papers.pipeline import _MS_MAIN, _ms_anchors
import sqlite3

OUT = sys.argv[1] if len(sys.argv) > 1 else "tmp_scan_bare_out.txt"


def main() -> None:
    settings = get_settings()
    store = ContentAddressedStore(settings.artifacts_dir)
    con = sqlite3.connect("file:.data/examdata.db?mode=ro", uri=True)
    rows = con.execute(
        """
        select ms.id, ms.document_id, ms.matched_paper_document_id
        from mark_scheme ms
        join document d on d.id = ms.document_id
        where d.subject_id between 19 and 26
          and ms.matched_paper_document_id is not null
        order by ms.id
        """
    ).fetchall()
    print(f"{len(rows)} matched MS", flush=True)
    bare: list[str] = []
    alpha_fracs: list[float] = []
    n_docs = 0
    n_err = 0
    for ms_id, ms_doc, qp_doc in rows:
        key_row = con.execute(
            """
            select a.storage_key from document d
            join document_revision r on r.id = d.current_revision_id
            join artifact a on a.id = r.artifact_id where d.id = ?
            """,
            (ms_doc,),
        ).fetchone()
        if not key_row or not key_row[0]:
            continue
        path = store.path_for_key(key_row[0])
        if not path.exists():
            continue
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
        if not wanted:
            continue
        compact = {p.replace("(", "").replace(")", ""): p for p in wanted}
        data = path.read_bytes()
        try:
            with pymupdf.open(stream=data, filetype="pdf") as pdf:
                anchors = _ms_anchors(pdf, wanted)
                for idx, tok, rect in anchors:
                    width = pdf[idx].rect.width
                    frac = rect[0] / width
                    acc = tok in wanted or tok.replace("(", "").replace(")", "") in compact
                    if _MS_MAIN.fullmatch(tok):
                        bare.append(
                            f"{frac:.3f} ms={ms_id} doc={ms_doc} p{idx+1} "
                            f"{tok!r} x={round(rect[0],1)} y={round(rect[1],1)} "
                            f"W={round(width)} accepted={int(acc)}"
                        )
                    else:
                        alpha_fracs.append(frac)
        except Exception as exc:  # noqa: BLE001
            n_err += 1
            print(f"!! ms={ms_id} doc={ms_doc}: {exc}", flush=True)
            continue
        n_docs += 1
        if n_docs % 50 == 0:
            print(f"  ... {n_docs} docs done", flush=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write(f"docs scanned: {n_docs}, errors: {n_err}\n")
        fh.write(f"alpha anchors: {len(alpha_fracs)}\n")
        if alpha_fracs:
            alpha_fracs.sort()
            n = len(alpha_fracs)
            fh.write(
                "alpha frac min/p05/p50/p95/max: "
                f"{alpha_fracs[0]:.3f} {alpha_fracs[n//20]:.3f} "
                f"{alpha_fracs[n//2]:.3f} {alpha_fracs[n*19//20]:.3f} "
                f"{alpha_fracs[-1]:.3f}\n"
            )
        fh.write(f"bare anchors: {len(bare)}\n")
        for line in bare:
            fh.write(line + "\n")
    print(f"written {OUT}", flush=True)


if __name__ == "__main__":
    main()
