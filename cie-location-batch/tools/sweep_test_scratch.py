"""一次性：删除 tmp/_test_pipeline 下的测试输出 PNG（可重生成），保留文本夹具。

白名单精确到两个文件；逐段拒绝 reparse point；结果追加 cleanup.jsonl。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import batchlib as B

TARGETS = [
    B.TMP / "_test_pipeline" / "ms-p6-1a.png",
    B.TMP / "_test_pipeline" / "qp-p2-q1.png",
]


def has_reparse(p: Path) -> bool:
    cur = p
    while True:
        if cur.exists() and (cur.is_symlink() or cur.is_junction()):
            return True
        if cur == cur.parent:
            return False
        cur = cur.parent


def main() -> int:
    dry = "--dry-run" in sys.argv
    deleted, freed, files, problems = 0, 0, [], []
    base = (B.TMP / "_test_pipeline").resolve()
    for t in TARGETS:
        try:
            rp = t.resolve()
        except OSError as e:
            problems.append(f"resolve {t}: {e}")
            continue
        if rp.parent != base:
            problems.append(f"outside whitelist dir: {rp}")
            continue
        if has_reparse(rp):
            problems.append(f"reparse point refused: {rp}")
            continue
        if not rp.is_file():
            problems.append(f"not a file / gone: {rp}")
            continue
        size = rp.stat().st_size
        if dry:
            print(f"del {size:>10,}  {rp}")
        else:
            rp.unlink()
            print(f"del {size:>10,}  {rp}")
        deleted += 1
        freed += size
        files.append(str(rp))
    mode = "dry_run" if dry else "executed"
    print(f"test_scratch_sweep[{mode}]: files={deleted} freed_bytes={freed} problems={len(problems)}")
    for p in problems:
        print("  PROBLEM:", p)
    if not dry and deleted:
        B.append_jsonl(
            B.CLEANUP,
            {
                "stage": "test_scratch_sweep",
                "key": "*",
                "at": B.now_iso(),
                "deleted": deleted,
                "freed_bytes": freed,
                "files": files,
                "problems": problems,
                "note": "tmp/_test_pipeline 测试输出 PNG（由 tools/test_pipeline.py 每次运行重生成）；文本夹具保留",
            },
        )
    return 0 if not problems else 1


if __name__ == "__main__":
    raise SystemExit(main())
