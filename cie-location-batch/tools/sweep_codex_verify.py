"""一次性：删除 work/codex_verify 下可再生的工具性产物。

白名单（仅此三项）：
  fresh_venv_test/  —— 评估用的一次性 venv 副本（~14MB，可再生，无脚本引用）
  smoke/            —— smoke 测试的 prompt/err/out 文本
  __pycache__/      —— 字节码缓存

保留（一律不动）：records/manifest/batch JSON、snap-report、logs/、finish-logs/、
textdump/pen-dump、脚本。verification.jsonl 已含六卷全部核验记录，records JSON 为冗余副本。

安全：逐文件 unlink；目标必须位于 work/codex_verify/ 内；逐段拒绝 symlink/junction/
重解析点；删后逐个复核消失；空目录自底向上 rmdir（仅空目录，非递归强删）。
结果追加 cleanup.jsonl（stage=codex_verify_sweep）。默认 dry-run；--apply 执行。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import batchlib as B
import cleanup_paper as C

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(B.WORK) / "codex_verify"
WHITELIST_DIRS = ("fresh_venv_test", "smoke", "__pycache__")

NOTE = (
    "work/codex_verify 下可再生产物（fresh_venv_test venv 副本、smoke 文本、__pycache__）；"
    "records/manifest/batch/snap-report/logs/finish-logs/textdump/脚本全部保留；"
    "核验结论已存 verification.jsonl（六卷共 2431 条）。"
)


def collect() -> tuple[list[Path], list[Path]]:
    files: list[Path] = []
    dirs: list[Path] = []
    for name in WHITELIST_DIRS:
        base = ROOT / name
        if not base.is_dir():
            continue
        for p in sorted(base.rglob("*")):
            if p.is_file() or p.is_symlink():
                files.append(p)
            elif p.is_dir():
                dirs.append(p)
        dirs.append(base)
    return files, dirs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    if not ROOT.is_dir():
        print(f"根目录不存在：{ROOT}")
        return 1

    files, dirs = collect()
    total = sum(f.stat().st_size for f in files if f.exists() and not f.is_symlink())
    print(f"目标文件 {len(files)} 个 / {total:,} 字节；待清理空目录 {len(dirs)} 个")
    for f in files[:10]:
        print("  target", f.relative_to(ROOT))
    if len(files) > 10:
        print(f"  ... 其余 {len(files) - 10} 个省略")

    removed: list[tuple[str, int]] = []
    refused: list[str] = []
    freed = 0
    for f in files:
        problem = C.unsafe_component(ROOT, f)
        if problem:
            refused.append(f"{f}: {problem}")
            continue
        try:
            size = f.stat().st_size
        except OSError:
            size = 0
        if not args.apply:
            removed.append((str(f), size))
            freed += size
            continue
        try:
            f.unlink()
        except OSError as exc:
            refused.append(f"{f}: 删除失败 {exc}")
            continue
        if f.exists() or f.is_symlink():
            refused.append(f"{f}: 删除后仍然存在")
            continue
        removed.append((str(f), size))
        freed += size

    dirs_removed = 0
    if args.apply:
        for d in sorted(dirs, key=lambda p: len(p.parts), reverse=True):
            if C.unsafe_component(ROOT, d):
                continue
            try:
                d.rmdir()  # 仅空目录
                dirs_removed += 1
            except OSError:
                pass
        residual = [f for f in files if f.exists()]
        if residual:
            refused += [f"{p} 删除后仍然存在" for p in residual]

    for p, s in removed[:10]:
        print(f"  {'del' if args.apply else 'would-del'} {s:>9,}  {p}")
    if len(removed) > 10:
        print(f"  ... 其余 {len(removed) - 10} 个省略")
    for r in refused:
        print("  REFUSED", r)
    mode = "applied" if args.apply else "dry_run"
    print(f"codex_verify_sweep[{mode}]: files={len(removed)} freed_bytes={freed} "
          f"dirs_rmdir={dirs_removed} refused={len(refused)}")

    if args.apply and removed:
        B.append_jsonl(B.CLEANUP, {
            "stage": "codex_verify_sweep",
            "key": "*",
            "at": B.now_iso(),
            "deleted": len(removed),
            "freed_bytes": freed,
            "dirs_rmdir": dirs_removed,
            "files": [p for p, _ in removed],
            "problems": refused,
            "note": NOTE,
        })
        print("   已追加 cleanup.jsonl stage=codex_verify_sweep")
    return 1 if refused else 0


if __name__ == "__main__":
    raise SystemExit(main())
