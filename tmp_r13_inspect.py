"""r13: inspect the 16 structure-mismatch WPS docs (read-only).

For each doc: DB question rows vs fresh-parsed nodes, plus per-question
taxonomy/MS counts and override flags. Prints side-by-side trees.

Usage: ./.venv/Scripts/python.exe -X utf8 tmp_r13_inspect.py [--doc 3555] [--render]
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
from examdata.edexcel_papers.pipeline import (  # noqa: E402
    _artifact_path as _ap,
    build_question_tree,
    _region_text,
)
from examdata.paperqa.locator import index_questions, is_ciphered  # noqa: E402

DB = ROOT / ".data/examdata.db"

DOCS16 = [3555, 3556, 3566, 3627, 3598, 3628, 3666, 3578, 3609, 3487, 3553, 3590, 3554, 3564, 3591, 3625]


def artifact_path(cur, doc_id):
    row = cur.execute(
        """SELECT a.storage_key FROM document d
           JOIN document_revision r ON r.id = d.current_revision_id
           JOIN artifact a ON a.id = r.artifact_id WHERE d.id = ?""",
        (doc_id,),
    ).fetchone()
    return ROOT / ".data/artifacts" / row["storage_key"] if row else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--doc", type=int, default=0)
    ap.add_argument("--render", action="store_true")
    args = ap.parse_args()

    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    docs = [args.doc] if args.doc else DOCS16
    for doc_id in docs:
        d = cur.execute(
            "SELECT id, title, year, paper_code FROM document WHERE id=?", (doc_id,)
        ).fetchone()
        paper = cur.execute("SELECT id FROM paper WHERE document_id=?", (doc_id,)).fetchone()
        print("=" * 100)
        print(f"doc {doc_id} | {d['title']} | year={d['year']} | code={d['paper_code']}")
        if not paper:
            print("  NO PAPER ROW")
            continue
        pid = paper["id"]
        qs = cur.execute(
            "SELECT id, parent_id, number_path, number_label, display_order, depth, kind, marks, "
            "has_override, substr(stem_text,1,90) stem FROM question WHERE paper_id=? ORDER BY display_order",
            (pid,),
        ).fetchall()
        print(f"-- DB questions ({len(qs)}) --")
        for q in qs:
            tax = cur.execute(
                "SELECT COUNT(*) FROM question_taxonomy WHERE question_id=?", (q["id"],)
            ).fetchone()[0]
            mse = cur.execute(
                "SELECT COUNT(*) FROM mark_scheme_entry WHERE question_id=?", (q["id"],)
            ).fetchone()[0]
            stem = " ".join((q["stem"] or "").split())
            print(
                f"  q{q['id']} d{q['depth']} path={q['number_path']!r} kind={q['kind']} "
                f"marks={q['marks']} ovr={q['has_override']} tax={tax} ms={mse} stem={stem[:70]!r}"
            )
        path = artifact_path(cur, doc_id)
        if path is None or not path.exists():
            print("  artifact missing")
            continue
        data = path.read_bytes()
        nodes = build_question_tree(index_questions(data, "qp"))
        print(f"-- code nodes ({len(nodes)}) --")
        with pymupdf.open(stream=data, filetype="pdf") as pdf:
            ciphered = is_ciphered(pdf)
            for n in nodes:
                reg = n["regions"][0]
                t = _region_text(pdf, n["regions"], ciphered=ciphered)
                t = " ".join((t or "").split())
                print(
                    f"  path={n['number_path']!r} depth={n.get('depth')} marks={n.get('marks')} "
                    f"page={reg['page']} y={reg['bbox'][1]:.0f} text={t[:70]!r}"
                )
            if args.render:
                for pno in range(min(3, pdf.page_count)):
                    pix = pdf[pno].get_pixmap(dpi=110)
                    out = ROOT / f"tmp_r13_doc{doc_id}_p{pno+1}.png"
                    pix.save(out)
                    print(f"  rendered {out.name}")
    con.close()


if __name__ == "__main__":
    main()
