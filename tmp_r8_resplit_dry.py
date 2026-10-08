"""r8 dry-run: for each changed doc, recompute the question tree and match old
DB questions to new nodes by region position (page, y0). Read-only.

Writes tmp_r8_resplit_dry.json / tmp_r8_resplit_dry.out
"""
from __future__ import annotations

import json
import sqlite3
import sys
import time
from pathlib import Path

import pymupdf

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from examdata.edexcel_papers.pipeline import (  # noqa: E402
    build_question_tree,
    _region_text,
    _question_marks,
)
from examdata.paperqa.locator import index_questions, is_ciphered  # noqa: E402

ROOT = Path(__file__).resolve().parent
DB = ROOT / ".data/examdata.db"
TOL = 8.0


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
    changed = json.load(open(ROOT / "tmp_r8_scan3.json", encoding="utf-8"))
    docs = [r for r in changed if "old_only" in r]
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    report = []
    t0 = time.time()
    for i, r in enumerate(docs):
        doc_id = r["doc"]
        paper = cur.execute("SELECT id FROM paper WHERE document_id=?", (doc_id,)).fetchone()
        old_qs = cur.execute(
            "SELECT id, number_path, number_label, parent_id, display_order, depth, marks, "
            "page_from, page_to, bbox_from, bbox_to, substr(stem_text,1,120) stem, attrs "
            "FROM question WHERE paper_id=? ORDER BY display_order",
            (paper["id"],),
        ).fetchall()
        path = artifact_path(cur, doc_id)
        data = path.read_bytes()
        nodes = build_question_tree(index_questions(data, "qp"))
        with pymupdf.open(stream=data, filetype="pdf") as pdf:
            ciphered = is_ciphered(pdf)
            texts = {n["number_path"]: _region_text(pdf, n["regions"], ciphered=ciphered) for n in nodes}
            marks = _question_marks(pdf, nodes, texts, ciphered=ciphered)

        # new position index
        new_items = []
        for n in nodes:
            reg = n["regions"][0]
            new_items.append(
                {
                    "path": n["number_path"],
                    "page": reg["page"],
                    "y": reg["bbox"][1],
                    "used": False,
                    "node": n,
                }
            )
        matched, deleted = [], []
        for q in old_qs:
            bf = json.loads(q["bbox_from"]) if q["bbox_from"] else None
            page, y = q["page_from"], bf[1] if bf else None
            best = None
            if page is not None and y is not None:
                for it in new_items:
                    if it["used"] or it["page"] != page:
                        continue
                    d = abs(it["y"] - y)
                    if d <= TOL and (best is None or d < best[0]):
                        best = (d, it)
            if best is not None:
                best[1]["used"] = True
                matched.append(
                    {
                        "qid": q["id"],
                        "old_path": q["number_path"],
                        "new_path": best[1]["path"],
                        "dy": round(best[0], 2),
                        "old_stem": q["stem"],
                        "new_stem": (texts.get(best[1]["path"]) or "")[:120],
                    }
                )
            else:
                tax = cur.execute(
                    "SELECT COUNT(*) FROM question_taxonomy WHERE question_id=?", (q["id"],)
                ).fetchone()[0]
                mse = cur.execute(
                    "SELECT COUNT(*) FROM mark_scheme_entry WHERE question_id=?", (q["id"],)
                ).fetchone()[0]
                deleted.append(
                    {
                        "qid": q["id"],
                        "path": q["number_path"],
                        "page": q["page_from"],
                        "y": round(y, 1) if y is not None else None,
                        "marks": q["marks"],
                        "stem": q["stem"],
                        "tax_rows": tax,
                        "ms_entries": mse,
                    }
                )
        inserted = [
            {
                "path": it["path"],
                "page": it["page"],
                "y": round(it["y"], 1),
                "marks": marks.get(it["path"]),
                "stem": (texts.get(it["path"]) or "")[:120],
            }
            for it in new_items
            if not it["used"]
        ]
        bigdiff = [
            {"qid": m["qid"], "old": m["old_path"], "new": m["new_path"], "dy": m["dy"]}
            for m in matched
            if m["old_stem"] and m["new_stem"] and m["old_stem"][:60] != m["new_stem"][:60]
        ]
        report.append(
            {
                "doc": doc_id,
                "title": r["title"],
                "n_old_q": len(old_qs),
                "n_new_nodes": len(nodes),
                "matched": len(matched),
                "deleted": deleted,
                "inserted": inserted,
                "relabeled": [
                    {"qid": m["qid"], "old": m["old_path"], "new": m["new_path"]}
                    for m in matched
                    if m["old_path"] != m["new_path"]
                ],
                "stem_diff_count": len(bigdiff),
                "stem_diffs": bigdiff[:10],
            }
        )
        if (i + 1) % 10 == 0:
            print(f"  ...{i+1}/{len(docs)} ({time.time()-t0:.0f}s)", flush=True)
    (ROOT / "tmp_r8_resplit_dry.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    tot_del = sum(len(r["deleted"]) for r in report)
    tot_ins = sum(len(r["inserted"]) for r in report)
    tot_rel = sum(len(r["relabeled"]) for r in report)
    tot_sd = sum(r["stem_diff_count"] for r in report)
    with open(ROOT / "tmp_r8_resplit_dry.out", "w", encoding="utf-8") as out:
        print(
            f"docs={len(report)} deleted={tot_del} inserted={tot_ins} relabeled={tot_rel} "
            f"stem_diffs={tot_sd} time={time.time()-t0:.0f}s",
            file=out,
        )
        for r in report:
            print(
                f"\ndoc {r['doc']} {r['title'][:60]} old={r['n_old_q']} new={r['n_new_nodes']} "
                f"matched={r['matched']} del={len(r['deleted'])} ins={len(r['inserted'])} relabel={len(r['relabeled'])}",
                file=out,
            )
            for d in r["deleted"]:
                print(
                    f"  DEL qid={d['qid']} {d['path']} p{d['page']} y{d['y']} marks={d['marks']} "
                    f"tax={d['tax_rows']} ms={d['ms_entries']} stem={d['stem'][:60]!r}",
                    file=out,
                )
            for ins in r["inserted"]:
                print(
                    f"  INS {ins['path']} p{ins['page']} y{ins['y']} marks={ins['marks']} stem={ins['stem'][:60]!r}",
                    file=out,
                )
            for rl in r["relabeled"]:
                print(f"  REL qid={rl['qid']} {rl['old']} -> {rl['new']}", file=out)
            for sd in r["stem_diffs"]:
                print(f"  SDIFF qid={sd['qid']} {sd['old']}->{sd['new']} dy={sd['dy']}", file=out)
    print(
        f"done docs={len(report)} deleted={tot_del} inserted={tot_ins} relabeled={tot_rel} "
        f"stem_diffs={tot_sd} time={time.time()-t0:.0f}s"
    )
    con.close()


if __name__ == "__main__":
    main()
