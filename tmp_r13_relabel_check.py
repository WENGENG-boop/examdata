"""r13: verify dry-run matching content (read-only).

For every doc in tmp_r13_dry.json:
- query old questions from DB (unchanged by the dry run);
- re-parse the PDF, get per-node text;
- every kept old question maps to relabeled target or its own path;
- compare old stem vs new text (similarity ratio); flag low matches.

Writes tmp_r13_relabel_check.out
"""
from __future__ import annotations

import difflib
import json
import re
import sqlite3
import sys
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
from examdata.edexcel_papers.pipeline import (  # noqa: E402
    build_question_tree,
    _region_text,
)
from examdata.paperqa.locator import index_questions, is_ciphered  # noqa: E402

DB = ROOT / ".data/examdata.db"


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip().lower()


def artifact_path(cur, doc_id):
    row = cur.execute(
        """SELECT a.storage_key FROM document d
           JOIN document_revision r ON r.id = d.current_revision_id
           JOIN artifact a ON a.id = r.artifact_id WHERE d.id = ?""",
        (doc_id,),
    ).fetchone()
    return ROOT / ".data/artifacts" / row["storage_key"] if row else None


def main():
    recs = json.load(open(ROOT / "tmp_r13_dry.json", encoding="utf-8"))
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    out = []
    n_rel = n_flag = n_keep = 0
    for r in recs:
        doc_id = r["doc"]
        paper = cur.execute("SELECT id FROM paper WHERE document_id=?", (doc_id,)).fetchone()
        old_qs = {
            q["id"]: q
            for q in cur.execute(
                "SELECT id, number_path, stem_text FROM question WHERE paper_id=?",
                (paper["id"],),
            )
        }
        relabel = {x["qid"]: x for x in r["relabeled"]}
        deleted = {x["qid"] for x in r["deleted"]}
        path = artifact_path(cur, doc_id)
        data = path.read_bytes()
        nodes = build_question_tree(index_questions(data, "qp"))
        with pymupdf.open(stream=data, filetype="pdf") as pdf:
            ciphered = is_ciphered(pdf)
            texts = {
                n["number_path"]: _region_text(pdf, n["regions"], ciphered=ciphered)
                for n in nodes
            }
        out.append(f"===== doc {doc_id} {r['title'][:70]} old={r['n_old_q']} new={r['n_new_nodes']}")
        for qid, q in sorted(old_qs.items()):
            if qid in deleted:
                continue
            n_keep += 1
            new_path = relabel[qid]["new"] if qid in relabel else q["number_path"]
            new_text = texts.get(new_path)
            if new_text is None:
                out.append(f"  !! q{qid} {q['number_path']} -> {new_path}: MISSING new text")
                n_flag += 1
                continue
            a, b = norm(q["stem_text"])[:400], norm(new_text)[:400]
            sim = difflib.SequenceMatcher(None, a, b).ratio() if a and b else 0.0
            tag = ""
            if qid in relabel:
                n_rel += 1
                tag = f"REL {q['number_path']} -> {new_path}"
            if sim < 0.55:
                n_flag += 1
                out.append(
                    f"  FLAG q{qid} {tag or q['number_path']} sim={sim:.2f}\n"
                    f"    OLD: {a[:150]!r}\n    NEW: {b[:150]!r}"
                )
            elif qid in relabel:
                out.append(f"  ok   q{qid} {tag} sim={sim:.2f} | {a[:70]!r}")
    out.append(f"\nTOTAL kept={n_keep} relabeled={n_rel} flagged={n_flag}")
    txt = "\n".join(out)
    (ROOT / "tmp_r13_relabel_check.out").write_text(txt + "\n", encoding="utf-8")
    print(txt)
    con.close()


if __name__ == "__main__":
    main()
