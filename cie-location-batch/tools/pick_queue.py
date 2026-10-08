"""从已发现的身份里挑出下一批要处理的卷，并打上 claim 防止重复派发。

- 只挑 kind in (paired, qp_only)：ms_only 没有 QP，按规则不处理
- 跳过已终态的卷（cleaned / imported_verified / ambiguous / 已知 HTTP 停止项）
- 排序：paired 优先，年份新的优先，同科目内按卷号；科目之间轮转，保证覆盖面
- `--claim` 会把选中的卷在 work/state.json 里标成 queued，下一批不会再选中
"""
from __future__ import annotations

import argparse
import collections
import io
import json
import sys

import batchlib as B
import pipelinestate as S

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DONE_STAGES = {"cleaned", "ambiguous", "imported_verified"}
SKIP_STAGES = {"download_failed", "download_interrupted", "stop_blocked", "conflict",
               "validation_partial", "index_failed", "import_failed", "readback_failed",
               "validation_failed", "blocked"}


def cleaned_keys() -> set[str]:
    """cleanup.jsonl 里已 cleaned 的 key —— 真终态，loop 不该再挑。"""
    return {r["key"] for r in B.read_jsonl(B.CLEANUP) if r.get("stage") == "cleaned"}


def candidates(kinds, min_year, max_year, exclude_subjects, skip_stages=None):
    skip = SKIP_STAGES if skip_stages is None else set(skip_stages)
    papers = B.read_json(B.PAPERS, {}) or {}
    mirror = S.load_all()
    done = cleaned_keys()
    rows = []
    for key, entry in papers.items():
        if not isinstance(entry, dict):
            continue
        if key in done:
            continue
        kind = entry.get("kind")
        if kind not in kinds:
            continue
        subject = entry.get("subject") or key.split("/")[0]
        if subject in exclude_subjects:
            continue
        year = entry.get("year")
        if not isinstance(year, int) or not (min_year <= year <= max_year):
            continue
        stage = (mirror.get(key) or {}).get("stage") or entry.get("stage") or "discovered"
        if stage in DONE_STAGES or stage in skip:
            continue
        rows.append({"key": key, "kind": kind, "subject": subject, "year": year,
                     "season": entry.get("season"), "paper": entry.get("paper"),
                     "stage": stage})
    return rows


def interleave(rows):
    """科目内按年份新→旧排序，科目之间轮转，避免整批集中在同一个科目。"""
    by_subject = collections.defaultdict(list)
    for row in rows:
        by_subject[row["subject"]].append(row)
    season_rank = {"Nov": 0, "Jun": 1, "Mar": 2}
    for subject in by_subject:
        by_subject[subject].sort(
            key=lambda r: (-(r["year"] or 0), season_rank.get(r["season"], 9),
                           str(r["paper"] or "")))
    order = sorted(by_subject, key=lambda s: (len(by_subject[s]), s))
    out = []
    index = 0
    while True:
        added = False
        for subject in order:
            bucket = by_subject[subject]
            if index < len(bucket):
                out.append(bucket[index])
                added = True
        if not added:
            break
        index += 1
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=8)
    parser.add_argument("--kinds", default="paired,qp_only")
    parser.add_argument("--min-year", type=int, default=B.YEAR_START)
    parser.add_argument("--max-year", type=int, default=B.YEAR_END)
    parser.add_argument("--exclude-subjects", default="")
    parser.add_argument("--claim", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--stats", action="store_true")
    args = parser.parse_args()

    kinds = {k.strip() for k in args.kinds.split(",") if k.strip()}
    exclude = {s.strip() for s in args.exclude_subjects.split(",") if s.strip()}
    rows = interleave(candidates(kinds, args.min_year, args.max_year, exclude))

    if args.stats:
        by_kind = collections.Counter(r["kind"] for r in rows)
        by_stage = collections.Counter(r["stage"] for r in rows)
        print(f"可处理卷 {len(rows)}  kind={dict(by_kind)}")
        print(f"阶段分布 {dict(by_stage)}")
        print(f"涉及科目 {len({r['subject'] for r in rows})}")
        return 0

    picked = rows[: args.limit]
    if args.claim:
        for row in picked:
            S.update(row["key"], stage="queued", queued_at=B.now_iso(),
                     queued_kind=row["kind"], queued_subject=row["subject"])
        B.set_checkpoint(last_queue_at=B.now_iso(), last_queue_size=len(picked))

    if args.json:
        print(json.dumps(picked, ensure_ascii=False, indent=2))
    else:
        for row in picked:
            print(f"{row['key']}\t{row['kind']}\t{row['stage']}")
        print(f"--- 选中 {len(picked)} / 可处理 {len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
