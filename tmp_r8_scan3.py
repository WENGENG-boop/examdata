"""r8 scan3: full Edexcel QP scan comparing pre-patch anchors (no dot filter)
vs the current source (dot filter with '.' + U+FFFD). Read-only.

Writes tmp_r8_scan3.json / tmp_r8_scan3.out.
"""
from __future__ import annotations

import json
import sqlite3
import sys
import time
from pathlib import Path

import pymupdf

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from examdata.paperqa import locator as L  # noqa: E402

ROOT = Path(__file__).resolve().parent
DB = ROOT / ".data/examdata.db"

_real_dot = L._dot_answer_digit


def _no_filter(words, word):
    return False


def artifact_path(cur, doc_id):
    row = cur.execute(
        """
        SELECT a.storage_key FROM document d
        JOIN document_revision r ON r.id = d.current_revision_id
        JOIN artifact a ON a.id = r.artifact_id WHERE d.id = ?
        """,
        (doc_id,),
    ).fetchone()
    return ROOT / ".data/artifacts" / row["storage_key"] if row else None


def main():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    docs = cur.execute(
        """
        SELECT d.id, d.title, d.doc_type FROM document d JOIN board b ON b.id=d.board_id
        WHERE b.key='edexcel' AND d.doc_type IN ('question_paper','specimen_paper')
        ORDER BY d.id
        """
    ).fetchall()
    report = []
    t0 = time.time()
    for i, d in enumerate(docs):
        path = artifact_path(cur, d["id"])
        if path is None or not path.exists():
            report.append({"doc": d["id"], "title": d["title"], "error": "artifact missing"})
            continue
        try:
            pdf = pymupdf.open(path)
            ciphered = L.is_ciphered(pdf)
            L._dot_answer_digit = _no_filter
            old_anchors, _ = L._anchors(pdf, "qp", ciphered=ciphered)
            L._dot_answer_digit = _real_dot
            new_anchors, _ = L._anchors(pdf, "qp", ciphered=ciphered)
            old_paths = list(dict.fromkeys(a.path for a in old_anchors))
            new_paths = list(dict.fromkeys(a.path for a in new_anchors))
            pdf.close()
        except Exception as exc:
            L._dot_answer_digit = _real_dot
            report.append({"doc": d["id"], "title": d["title"], "error": f"{type(exc).__name__}: {exc}"})
            continue
        if old_paths != new_paths:
            report.append(
                {
                    "doc": d["id"],
                    "title": d["title"],
                    "doc_type": d["doc_type"],
                    "old_only": [p for p in old_paths if p not in new_paths],
                    "new_only": [p for p in new_paths if p not in old_paths],
                    "n_old": len(old_paths),
                    "n_new": len(new_paths),
                }
            )
        if (i + 1) % 200 == 0:
            print(f"  ...{i+1}/{len(docs)} ({time.time()-t0:.0f}s)", flush=True)
    (ROOT / "tmp_r8_scan3.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    changed = [r for r in report if "old_only" in r]
    errors = [r for r in report if "error" in r]
    regressions = [r for r in changed if not r["new_only"] and r["old_only"]]
    with open(ROOT / "tmp_r8_scan3.out", "w", encoding="utf-8") as out:
        print(
            f"docs scanned={len(docs)} changed={len(changed)} errors={len(errors)} regressions={len(regressions)} time={time.time()-t0:.0f}s",
            file=out,
        )
        for r in changed:
            print(f"\ndoc {r['doc']} {r['title'][:70]} ({r['n_old']}->{r['n_new']})", file=out)
            print(f"  old_only: {r['old_only']}", file=out)
            print(f"  new_only: {r['new_only']}", file=out)
        for r in errors:
            print(f"\nERROR doc {r['doc']} {r['title'][:70]}: {r['error']}", file=out)
    print(f"done scanned={len(docs)} changed={len(changed)} errors={len(errors)} regressions={len(regressions)} time={time.time()-t0:.0f}s")
    con.close()


if __name__ == "__main__":
    main()
