"""Generate review decisions from Jev batch records (remaining subjects).

Rules (same as the business pilot):
- single current label == Jev choice -> keep
- Jev choice in multi current labels -> change to choice (converge to single)
- otherwise -> change to choice
- OVERRIDES per subject are applied first.

Validation before writing: every batch row must have a Jev record with a choice,
and the choice code must belong to the resolved unit's point list.

Usage:
  python tmp_gen_jev_decisions.py --subject ial18-biology           # preview
  python tmp_gen_jev_decisions.py --subject ial18-biology --write   # write decisions
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from examdata.core import models as m
from examdata.tagging.corpus import load_points

ROOT = Path(__file__).resolve().parent
DB_URL = f"sqlite:///{ROOT / '.data' / 'examdata.db'}"
REVIEW = ROOT / ".data" / "tagging" / "review-export"

SUBJECTS = {
    "ial-spanish": ["003"],
    "ial18-biology": [f"{i:03d}" for i in range(3, 14)],
    "ial18-chemistry": [f"{i:03d}" for i in range(1, 10)],
    "ial18-economics": [f"{i:03d}" for i in range(1, 12)],
    "ial18-physics": [f"{i:03d}" for i in range(1, 11)],
    "ial18-mathematics": [f"{i:03d}" for i in range(2, 63) if i != 38],
    "ial18-mathematics-extra": [f"{i:03d}" for i in range(1, 14)],
}

POINTS_SUBJECT = {"ial18-mathematics-extra": "ial18-mathematics"}

OVERRIDES: dict[str, dict[int, tuple[str, str]]] = {
    "ial-spanish": {},
    "ial18-biology": {},
    "ial18-chemistry": {},
    "ial18-economics": {},
    "ial18-physics": {},
    "ial18-mathematics": {},
}

LOW_CONF = 0.45


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--subject", required=True)
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    slug = args.subject
    batches = SUBJECTS[slug]
    overrides = OVERRIDES.get(slug, {})

    jev_path = ROOT / f"tmp_jev_{slug}.jsonl"
    jev: dict[int, dict] = {}
    for line in open(jev_path, encoding="utf-8"):
        if line.strip():
            r = json.loads(line)
            jev[r["question_id"]] = r
    print(f"jev records: {len(jev)} ({jev_path.name})")

    eng = create_engine(DB_URL)
    s = Session(eng)
    points_slug = POINTS_SUBJECT.get(slug, slug)
    sub_row = s.execute(select(m.Subject).where(m.Subject.slug == points_slug)).scalar()
    keys = {(sub_row.code or "").strip().lower(), (sub_row.slug or "").strip().lower()}
    keys.discard("")
    points = [p for p in load_points(s) if (p.subject or "").strip().lower() in keys]
    by_unit: dict[str, set[str]] = {}
    for p in points:
        by_unit.setdefault(p.unit_code, set()).add(p.code)
    print(f"points: {len(points)}; units: " + str({k: len(v) for k, v in sorted(by_unit.items())}))

    missing: list[tuple] = []
    review_rows: list[tuple] = []
    per_batch: dict[str, list[dict]] = {}
    total = n_keep = n_change = 0
    for b in batches:
        src = REVIEW / slug / "batches" / f"batch-{b}.jsonl"
        out: list[dict] = []
        for line in open(src, encoding="utf-8"):
            if not line.strip():
                continue
            item = json.loads(line)
            qid = item["question_id"]
            cur = [c["code"] for c in item.get("current") or []]
            r = jev.get(qid)
            if r is None or not r.get("choice"):
                missing.append((qid, b, "no jev choice"))
                continue
            choice, conf = r["choice"], r.get("confidence")
            unit = r.get("unit") or item.get("unit_code")
            if choice not in by_unit.get(unit, set()):
                missing.append((qid, b, f"choice {choice} not in unit {unit}"))
                continue
            if qid in overrides:
                code, reason = overrides[qid]
                if len(cur) == 1 and cur[0] == code:
                    row = {"question_id": qid, "decision": "keep", "reason": reason}
                else:
                    row = {"question_id": qid, "decision": "change", "code": code, "reason": reason}
            elif len(cur) == 1 and cur[0] == choice:
                if r.get("model") == "auto-single-candidate":
                    reason = f"单候选单元（{unit} 仅 1 个内容点）自动确认 {choice}"
                else:
                    reason = f"Jev 复核确认原标签 {choice}（置信度 {conf}）"
                row = {"question_id": qid, "decision": "keep", "reason": reason}
            elif choice in cur:
                row = {"question_id": qid, "decision": "change", "code": choice,
                       "reason": f"Jev 判定 {choice}（置信度 {conf}）与题干相符；原标签多选（{'、'.join(cur)}）收敛为单选"}
            else:
                row = {"question_id": qid, "decision": "change", "code": choice,
                       "reason": f"Jev 判定 {choice}（置信度 {conf}）与题干相符；原标签（{'、'.join(cur)}）不符"}
            out.append(row)
            if row["decision"] == "keep":
                n_keep += 1
            else:
                n_change += 1
            if (conf is not None and conf < LOW_CONF
                    and r.get("model") != "auto-single-candidate"):
                top = r.get("top_probs") or []
                review_rows.append(
                    (b, qid, item.get("number_label"), unit, choice, conf,
                     " | ".join(f"{c}:{p}" for c, p in top[:3]),
                     "、".join(cur), (item.get("stem") or "")[:180].replace("\n", " "))
                )
        per_batch[b] = out
        total += len(out)

    print(f"decisions: {total} (keep {n_keep} / change {n_change}); missing: {len(missing)}")
    for m_ in missing[:30]:
        print("  MISSING", m_)

    review_path = ROOT / f"tmp_jev_review_{slug}.txt"
    with open(review_path, "w", encoding="utf-8") as fh:
        for row in review_rows:
            fh.write("\t".join(str(x) for x in row) + "\n")
    print(f"low-confidence rows (<{LOW_CONF}): {len(review_rows)} -> {review_path.name}")

    if missing:
        print("missing rows present -> NOT writing decisions")
        return
    if not args.write:
        print("preview only (use --write to write decisions files)")
        return

    for b, out in per_batch.items():
        dst = REVIEW / slug / "decisions" / f"batch-{b}.jsonl"
        dst.parent.mkdir(parents=True, exist_ok=True)
        with open(dst, "w", encoding="utf-8") as fh:
            for row in out:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(f"  batch-{b}: {len(out)} decisions -> {dst}")


if __name__ == "__main__":
    main()
