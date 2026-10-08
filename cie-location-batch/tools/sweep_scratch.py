"""清掉各卷 tmp 目录里的 OCR 中间产物（绝不碰 PDF / PNG / 索引 / 日志）。

背景：`run_ocr` 把 `_ocr_list.txt` / `_ocr_out.tsv`（以及 ocr_index 的 `_idx_list.txt` /
`_idx_out.tsv`）写进本卷 tmp 目录，早期 `cleanup_paper.collect_targets` 的白名单没有它们，
于是每卷都会留下一份 1 MB 级的残留。`probe_*.json` 同理（调试产物）。

只删白名单名字。每个目标先解析成绝对路径、核对在本卷 `tmp/<subject>/<year>-<season>-<paper>/`
内、逐段拒绝符号链接/junction/重解析点，然后一次一个 `Path.unlink()`，绝不 rmtree。
结果追加到 `cleanup.jsonl`（stage=scratch_sweep）。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import batchlib as B
import cleanup_paper as C
import paperlib as P

sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def scratch_files(tmp_dir: Path) -> list[Path]:
    out = []
    if not tmp_dir.is_dir():
        return out
    for entry in sorted(tmp_dir.iterdir()):
        if not entry.is_file():
            continue
        if entry.name in C.SCRATCH_NAMES or any(entry.match(g) for g in C.SCRATCH_GLOBS):
            out.append(entry)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="清掉各卷 tmp 里的 OCR 中间产物")
    parser.add_argument("keys", nargs="*", help="留空则扫全部 tmp 卷目录")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    root = Path(B.TMP)
    if args.keys:
        dirs = [P.paper_tmp(k) for k in args.keys]
    else:
        dirs = [p for subj in sorted(root.iterdir()) if subj.is_dir()
                for p in sorted(subj.iterdir()) if p.is_dir()]

    removed, freed, refused = [], 0, []
    for tmp_dir in dirs:
        targets = scratch_files(tmp_dir)
        if not targets:
            continue
        for target in targets:
            problem = C.unsafe_component(root, target)
            if problem:
                refused.append(f"{target}: {problem}")
                continue
            size = target.stat().st_size
            if args.dry_run:
                removed.append((str(target), size))
                freed += size
                continue
            try:
                target.unlink()
            except OSError as exc:
                refused.append(f"{target}: {exc}")
                continue
            if target.exists():
                refused.append(f"{target}: 删除后仍然存在")
                continue
            removed.append((str(target), size))
            freed += size
        leftover = [t for t in targets if t.exists()]
        if leftover and not args.dry_run:
            refused.append(f"{tmp_dir}: 残留 {len(leftover)} 个")

    label = "scratch_sweep_dry_run" if args.dry_run else "scratch_sweep"
    for path, size in removed:
        print(f"  del {size:>9,}  {path}")
    for item in refused:
        print(f"  REFUSED {item}")
    print(f"{label}: files={len(removed)} freed_bytes={freed} refused={len(refused)}")
    if not args.dry_run:
        B.append_jsonl(B.CLEANUP, {
            "stage": label, "key": "*", "at": B.now_iso(),
            "deleted": len(removed), "freed_bytes": freed,
            "files": [p for p, _ in removed][:200],
            "problems": refused,
            "note": "OCR 中间产物与 probe 调试文件；白名单外文件一律未动",
        })
    return 1 if refused else 0


if __name__ == "__main__":
    raise SystemExit(main())
