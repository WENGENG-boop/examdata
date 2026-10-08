"""把 propose.py 的草稿变成一份 schema 合法、可立即导入的定位索引初稿。

用途：让子 agent 一开始就有一份**结构正确**的索引，只需视觉核验与修正，
不必从零手写几十条 JSON。

诚实性约定：初稿里每一题都写 `uncertain: true`，`notes` 说明是文字层初稿、
尚未视觉核验。核验通过后由 agent 改成 `uncertain: false` 并改写 notes。
**未核验的初稿绝不允许清理原件**（cleanup_paper 会检查 verification.jsonl）。
"""
from __future__ import annotations

import argparse
import io
import json
import re
import sys
from pathlib import Path

import batchlib as B
import paperlib as P

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

PARENT_RE = re.compile(r"^(.*)\([a-z]\)(?:\([ivx]+\))?$")
DRAFT_NOTE = "草稿：题号与区域来自文字层+矢量线，尚未视觉核验；核验后请改写 notes 并置 uncertain=false"
MAX_REGIONS = 25


def norm_bbox(raw):
    if not isinstance(raw, (list, tuple)) or len(raw) != 4:
        return None
    try:
        box = [round(float(v), 3) for v in raw]
    except (TypeError, ValueError):
        return None
    if box[2] <= box[0] or box[3] <= box[1]:
        return None
    return box


def regions_of(candidate):
    out = []
    raw = candidate.get("regions")
    if not isinstance(raw, list) or not raw:
        raw = [{"page": candidate.get("page"), "bbox": candidate.get("bbox")}]
    for item in raw:
        if not isinstance(item, dict):
            continue
        page = item.get("page")
        box = norm_bbox(item.get("bbox"))
        if isinstance(page, int) and page >= 1 and box:
            out.append({"page": page, "bbox": box})
    return out[:MAX_REGIONS]


def build(key: str) -> dict:
    path = P.proposal_path(key) if hasattr(P, "proposal_path") else None
    if path is None:
        subject, year, season, paper = key.split("/")
        path = B.WORK / "proposals" / subject / f"{year}-{season}-{paper}.json"
    proposal = json.loads(Path(path).read_bytes().decode("utf-8"))
    candidates = [c for c in (proposal.get("question_candidates") or [])
                  if isinstance(c, dict) and isinstance(c.get("question"), str)]
    ids = [c["question"] for c in candidates]
    id_set = set(ids)

    children = {qid: [] for qid in ids}
    parents = {}
    for qid in ids:
        match = PARENT_RE.match(qid)
        parent = None
        while match:
            candidate_parent = match.group(1)
            if candidate_parent in id_set:
                parent = candidate_parent
                break
            match = PARENT_RE.match(candidate_parent)
        parents[qid] = parent
        if parent:
            children[parent].append(qid)

    ms_by_label = {}
    for row in (proposal.get("ms_candidates") or []):
        if not isinstance(row, dict):
            continue
        label = row.get("label")
        box = norm_bbox(row.get("row_bbox"))
        page = row.get("page")
        if not isinstance(label, str) or not box or not isinstance(page, int):
            continue
        if row.get("page_has_table_header") is False:
            continue
        ms_by_label.setdefault(label, []).append({"page": page, "bbox": box})

    questions = []
    for candidate in candidates:
        qid = candidate["question"]
        regions = regions_of(candidate)
        if not regions:
            continue
        marks = candidate.get("marks")
        if children.get(qid):
            marks = None
        elif not isinstance(marks, int):
            marks = None
        questions.append({
            "question": qid,
            "parent": parents[qid],
            "text": (candidate.get("text") or "")[:50000],
            "marks": marks,
            "qp": regions,
            "ms": ms_by_label.get(qid, [])[:MAX_REGIONS],
            "uncertain": True,
            "notes": DRAFT_NOTE[:2000],
        })

    documents = []
    for role in ("qp", "ms"):
        sha = proposal.get(f"{role}_sha256")
        if isinstance(sha, str) and sha:
            documents.append({"role": role, "sha256": sha})

    return {
        "schema_version": "1",
        "board": "cie",
        "identity": proposal["identity"],
        "coordinate_system": "unrotated_pdf_points_top_left",
        "page_base": 1,
        "documents": documents,
        "questions": questions,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("key")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--out")
    args = parser.parse_args()

    data = build(args.key)
    text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"

    if args.write or args.out:
        subject, year, season, paper = args.key.split("/")
        target = Path(args.out) if args.out else (
            B.INDEXES / subject / f"{year}-{season}-{paper}" / "cie-index.json")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(text.encode("utf-8"))
        print(f"写入 {target}")
    else:
        print(text)

    questions = data["questions"]
    top = [q for q in questions if q["parent"] is None]
    with_ms = [q for q in questions if q["ms"]]
    print(f"题数 {len(questions)}（顶层 {len(top)}）  有 MS 区域 {len(with_ms)}  "
          f"documents {[d['role'] for d in data['documents']]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
