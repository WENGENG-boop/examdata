"""把 staged-sXX.jsonl 落盘追加到 verification.jsonl。

安全规则：
  - 落盘前复核当前索引 sha256 == staged 记录的 index_sha256（编译后索引若被改动即中止）
  - 幂等：同 (key, question, role, page, bbox) 且 index_sha256 相同、issues 为空、
    method 属目视核验的记录已存在时跳过该条（不重复追加）
  - 同一文件内重复键只保留最后一条
  - --dry-run 只报告不写
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REVIEW = Path(__file__).resolve().parent / "review"
BATCH_TOOLS = Path(__file__).resolve().parents[2] / "tools"
sys.path.insert(0, str(BATCH_TOOLS))

import batchlib as B  # noqa: E402
import cleanup_paper as C  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="落盘 staged 复核记录")
    parser.add_argument("slice_id", help="如 s07")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    staged = B.read_jsonl(REVIEW / f"staged-{args.slice_id}.jsonl")
    worklist = B.read_json(REVIEW / f"worklist-{args.slice_id}.json")
    if not staged or not worklist:
        print(f"缺少 staged 或 worklist（{args.slice_id}）")
        return 2
    paper = worklist["paper"]
    shas = {str(r.get("index_sha256")) for r in staged}
    current = C.current_index_sha256(paper)
    if len(shas) != 1 or current not in shas:
        print(f"索引 sha 守卫失败：current={current} staged={sorted(shas)}")
        return 2
    sha = current

    existing = set()
    for rec in B.read_jsonl(B.VERIFICATION):
        if rec.get("key") != paper or rec.get("index_sha256") != sha:
            continue
        if rec.get("issues") != [] or rec.get("method") not in C.VISUAL_METHODS:
            continue
        existing.add(C.record_key(rec))

    todo: dict[tuple, dict] = {}
    skipped = 0
    for rec in staged:
        rkey = C.record_key(rec)
        if rkey in existing:
            skipped += 1
            continue
        if rkey in todo:
            skipped += 1
        todo[rkey] = rec

    print(f"paper={paper} sha={sha[:16]}… 待写 {len(todo)} 条，跳过 {skipped} 条"
          + ("（dry-run）" if args.dry_run else ""))
    if not args.dry_run:
        for rec in todo.values():
            B.append_jsonl(B.VERIFICATION, rec)
        print(f"已追加 {len(todo)} 条到 {B.VERIFICATION}")
    B.atomic_write_json(REVIEW / f"apply-report-{args.slice_id}.json", {
        "slice": args.slice_id, "paper": paper, "index_sha256": sha,
        "written": 0 if args.dry_run else len(todo), "skipped": skipped,
        "dry_run": bool(args.dry_run), "at": B.now_iso(),
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
