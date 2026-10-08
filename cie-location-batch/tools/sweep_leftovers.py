"""清扫已 cleaned 卷 tmp 目录的残留与共享诊断 scratch（绝不 rmtree）。

范围（仅以下四类，逐文件 unlink）：
  A. tmp/<subj>/<year>-<season>-<paper>/ 中 stage=cleaned 的卷 —— 清理轮之后新产生的
     probe/裁剪图/页面图/scratch 脚本/dump/tsv/html/montage.pdf 等全部剩余文件
  B. tmp/_diag_crops/    —— 修复轮诊断裁剪图（可由原件重渲染，验证结论在 verification.jsonl）
  C. tmp/_test_pipeline/ —— pipeline 测试 scratch
  D. tmp/_*（根层散落 scratch 文件）

不触碰：任何非 cleaned 卷目录（conflict/failed 原件保留）、indexes/、work/、日志、
旧试点目录 cie-index-batch-2026-10-01。

安全：绝对路径逐个删除；逐段拒绝 symlink/junction/reparse point；删除后逐个复核消失；
结果追加 cleanup.jsonl（stage=leftover_sweep），不覆盖历史。
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import batchlib as B
import cleanup_paper as C

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

TMP = Path(B.TMP)
SHARED = ("_diag_crops", "_test_pipeline")


def cleaned_keys() -> set[str]:
    papers = json.loads(Path(B.PAPERS).read_text(encoding="utf-8"))
    papers = papers["papers"] if isinstance(papers, dict) and "papers" in papers else papers
    return {k for k, v in papers.items() if v.get("stage") == "cleaned"}


def collect() -> list[tuple[str, Path]]:
    done = cleaned_keys()
    out: list[tuple[str, Path]] = []

    for subj in sorted(TMP.iterdir()):
        if not subj.is_dir() or subj.name.startswith("_"):
            continue
        for d in sorted(subj.iterdir()):
            if not d.is_dir():
                continue
            parts = d.name.split("-")
            if len(parts) != 3:
                continue
            key = f"{subj.name}/{parts[0]}/{parts[1]}/{parts[2]}"
            if key not in done:
                continue
            for p in sorted(d.rglob("*")):
                if p.is_file():
                    out.append((key, p))

    for name in SHARED:
        d = TMP / name
        if d.is_dir():
            for p in sorted(d.rglob("*")):
                if p.is_file():
                    out.append((name, p))

    for p in sorted(TMP.glob("_*")):
        if p.is_file():
            out.append(("tmp_root", p))

    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    targets = collect()
    groups: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    removed, freed, refused = [], 0, []

    for key, t in targets:
        problem = C.unsafe_component(TMP, t)
        if problem:
            refused.append(f"{t}: {problem}")
            continue
        try:
            size = t.stat().st_size
        except OSError as exc:
            refused.append(f"{t}: stat 失败 {exc}")
            continue
        if args.dry_run:
            removed.append((str(t), size))
            freed += size
            groups[key][0] += 1
            groups[key][1] += size
            continue
        try:
            t.unlink()
        except OSError as exc:
            refused.append(f"{t}: {exc}")
            continue
        if t.exists():
            refused.append(f"{t}: 删除后仍然存在")
            continue
        removed.append((str(t), size))
        freed += size
        groups[key][0] += 1
        groups[key][1] += size

    label = "leftover_sweep_dry_run" if args.dry_run else "leftover_sweep"
    for p, s in removed[:60]:
        print(f"  del {s:>10,}  {p}")
    if len(removed) > 60:
        print(f"  ... 其余 {len(removed) - 60} 个省略")
    print("--- groups ---")
    for k in sorted(groups):
        n, b = groups[k]
        print(f"  {k:24s} files={n:4d} bytes={b:,}")
    for r in refused:
        print(f"  REFUSED {r}")
    print(f"{label}: files={len(removed)} freed_bytes={freed} refused={len(refused)}")

    if not args.dry_run:
        B.append_jsonl(B.CLEANUP, {
            "stage": label,
            "key": "*",
            "at": B.now_iso(),
            "deleted": len(removed),
            "freed_bytes": freed,
            "groups": {k: {"files": v[0], "bytes": v[1]} for k, v in sorted(groups.items())},
            "files": [p for p, _ in removed][:500],
            "problems": refused,
            "note": ("已 cleaned 卷 tmp 的清理轮后残留（probe/裁剪图/dump/scratch）与共享诊断 "
                     "_diag_crops/_test_pipeline/tmp 根层 _* scratch；全部可由原件重渲染或为一次性"
                     "诊断产物；验证结论保存在 verification.jsonl。非 cleaned 卷原件一律未触碰。"),
        })
    return 1 if refused else 0


if __name__ == "__main__":
    raise SystemExit(main())
