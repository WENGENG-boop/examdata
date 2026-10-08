"""r8: quantify repair scope for SEVERE ghost nodes (read-only).

For each SEVERE ghost (from tmp_r8_classify.json):
- moved subtree = children whose text sits before the first "Total for Question M"
  marker with M != own number, plus their descendants (they belong to Q(N-1));
- simulate post-repair QP paths (moved nodes lose the leading N -> N-1);
- re-scan the paper's MS PDF with _ms_anchors(wanted=None) to get the FULL MS row
  list (including rows dropped at split time because they were not in the buggy
  QP path set);
- classify each MS row vs post-repair QP paths: exact/descendant covered, ancestor
  covered, or uncovered (= candidate missing QP node / dropped row to restore).

Outputs: tmp_r8_missing.json (detail), tmp_r8_missing.out (summary).
"""
from __future__ import annotations

import collections
import json
import re
import sqlite3
import sys
from pathlib import Path

import pymupdf

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from examdata.edexcel_papers.pipeline import (  # noqa: E402
    _MS_COMPACT,
    _MS_NUMBER,
    _MS_PART,
    _ms_anchors,
)

ROOT = Path(__file__).resolve().parent
con = sqlite3.connect(ROOT / ".data/examdata.db")
con.row_factory = sqlite3.Row
cur = con.cursor()


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


def renumber(path: str, n: int) -> str:
    if path == str(n):
        return str(n - 1)
    if path.startswith(f"{n}("):
        return f"{n - 1}{path[len(str(n)):]}"
    return path


def artifact_key(doc_id: int) -> str | None:
    r = cur.execute(
        """SELECT a.storage_key FROM document d
           JOIN document_revision r ON r.id = d.current_revision_id
           JOIN artifact a ON a.id = r.artifact_id WHERE d.id = ?""",
        (doc_id,),
    ).fetchone()
    return r["storage_key"] if r else None


cls = json.load(open(ROOT / "tmp_r8_classify.json", encoding="utf-8"))
byp: dict[int, list] = collections.defaultdict(list)
for s in cls["severe"]:
    byp[s["paper"]].append(s)

records = []
for pid, ghosts in sorted(byp.items()):
    p = cur.execute("SELECT paper_no, document_id FROM paper WHERE id = ?", (pid,)).fetchone()
    if p is None:
        continue
    qs = {
        r["id"]: dict(r)
        for r in cur.execute(
            "SELECT id, parent_id, number_label, number_path, display_order, kind, marks, stem_text"
            " FROM question WHERE paper_id = ?",
            (pid,),
        )
    }
    kids: dict[int, list[int]] = collections.defaultdict(list)
    for q in qs.values():
        if q["parent_id"]:
            kids[q["parent_id"]].append(q["id"])

    def desc(qid: int) -> list[int]:
        out, stack = [], [qid]
        while stack:
            x = stack.pop()
            for c in kids.get(x, []):
                out.append(c)
                stack.append(c)
        return out

    # moved subtrees per ghost
    moved: dict[int, int] = {}  # qid -> ghost ownN
    ghost_info = []
    for g in ghosts:
        n = g["ownN"]
        nstem = norm(qs[g["id"]]["stem_text"])
        first_other = g["first_other"][1]
        before_ids = [b[0] for b in g["before"]]
        sub = set()
        for bid in before_ids:
            sub.add(bid)
            sub.update(desc(bid))
        for qid in sub:
            moved[qid] = n
        kids_detail = []
        for k in sorted((qs[c] for c in kids.get(g["id"], [])), key=lambda x: x["display_order"]):
            ks = norm(k["stem_text"])
            pos = nstem.find(ks) if ks else -1
            kids_detail.append(
                {
                    "id": k["id"],
                    "path": k["number_path"],
                    "marks": k["marks"],
                    "kind": k["kind"],
                    "pos": pos,
                    "before": k["id"] in sub,
                    "head": ks[:70],
                }
            )
        ghost_info.append(
            {
                "ghost": g["id"],
                "N": n,
                "markers": g["markers"],
                "first_other": g["first_other"],
                "moved_ids": sorted(sub),
                "kids": kids_detail,
            }
        )

    # post-repair QP path set
    paths_after = {}
    for qid, q in qs.items():
        np_ = renumber(q["number_path"], moved[qid]) if qid in moved else q["number_path"]
        paths_after[qid] = np_
    path_set = set(paths_after.values())

    # MS rows: full scan of MS PDF
    ms_rows = []
    ms_info = []
    for ms in cur.execute(
        "SELECT id, document_id FROM mark_scheme WHERE matched_paper_document_id = ?",
        (p["document_id"],),
    ):
        key = artifact_key(ms["document_id"])
        rows = []
        if key:
            path = ROOT / ".data/artifacts" / key
            try:
                with pymupdf.open(path) as pdf:
                    # wanted = post-repair QP paths: keeps _ms_extend from chaining
                    # junk, while alpha tokens outside wanted are still emitted.
                    anchors = _ms_anchors(pdf, wanted=set(path_set))
                rows = [t[1] for t in anchors]
            except Exception as exc:  # noqa: BLE001
                ms_info.append({"ms": ms["id"], "error": str(exc)})
                rows = []
        seen = []
        for t in rows:
            if t not in seen:
                seen.append(t)
        ms_rows.extend(seen)
        ms_info.append({"ms": ms["id"], "doc": ms["document_id"], "rows": len(seen)})
    seen_all = []
    for t in ms_rows:
        if t not in seen_all:
            seen_all.append(t)

    uncovered, ancestor_only, junk = [], [], []
    for t in seen_all:
        if not (
            _MS_NUMBER.match(t) or _MS_COMPACT.fullmatch(t) or _MS_PART.fullmatch(t)
        ):
            junk.append(t)
            continue
        exact = [qid for qid, p2 in paths_after.items() if p2 == t or p2.startswith(t + "(")]
        anc = [qid for qid, p2 in paths_after.items() if t.startswith(p2 + "(")]
        if exact:
            continue
        if anc:
            ancestor_only.append({"row": t, "parents": [paths_after[a] for a in anc]})
        else:
            uncovered.append({"row": t})

    records.append(
        {
            "paper": pid,
            "paper_no": p["paper_no"],
            "ghosts": ghost_info,
            "moved_total": len(moved),
            "ms_info": ms_info,
            "ms_rows": seen_all,
            "ms_junk": junk,
            "ms_uncovered": uncovered,
            "ms_ancestor_only": ancestor_only,
            "qp_paths": sorted(set(q["number_path"] for q in qs.values())),
            "paths_after": sorted(path_set),
        }
    )

json.dump(records, open(ROOT / "tmp_r8_missing.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)

lines = []
tot_moved = tot_unc = tot_anc = 0
for r in records:
    gN = len(r["ghosts"])
    unc = [u["row"] for u in r["ms_uncovered"]]
    anc = [u["row"] for u in r["ms_ancestor_only"]]
    tot_moved += r["moved_total"]
    tot_unc += len(unc)
    tot_anc += len(anc)
    lines.append(
        f"p{r['paper']} {r['paper_no']}: ghosts={gN} moved={r['moved_total']} "
        f"ms_rows={len(r['ms_rows'])} uncovered={unc} ancestor_only={anc}"
    )
lines.append(f"TOTAL papers={len(records)} moved={tot_moved} ms_uncovered={tot_unc} ms_ancestor_only={tot_anc}")
out = "\n".join(lines)
(ROOT / "tmp_r8_missing.out").write_text(out + "\n", encoding="utf-8")
print(out)
con.close()
