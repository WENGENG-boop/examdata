"""清掉各卷 tmp 里的逐页渲染图与裁剪图（保留 PDF）。

规范要求「看完删除临时裁剪图，逐页图也及时清理」。这些 PNG 全部可以从保留下来的
PDF 按同一 bbox 重新渲染，属于纯可再生中间产物，因此即便该卷还没走完
（conflict / validation_partial）也可以安全清除，PDF 一律不动。

只删 `tmp/<subject>/<year>-<season>-<paper>/` 下的 `pages/*.png`、`crops/*.png`
和该层散落的 `*.png`。每个目标先解析成绝对路径、核对在本卷目录内、逐段拒绝
符号链接/junction/重解析点，然后一次一个 `Path.unlink()`，绝不 rmtree。
结果追加到 `cleanup.jsonl`（stage=image_sweep）。
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

DONE_STAGES = {"cleaned", "imported_verified", "imported_verified_done"}
IMAGE_DIRS = ("pages", "crops")


def image_targets(tmp_dir: Path) -> list[Path]:
    out: list[Path] = []
    if not tmp_dir.is_dir():
        return out
    for name in IMAGE_DIRS:
        sub = tmp_dir / name
        if sub.is_dir():
            out.extend(sorted(p for p in sub.rglob("*") if p.is_file()))
    out.extend(sorted(p for p in tmp_dir.glob("*.png") if p.is_file()))
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="清掉各卷 tmp 里的逐页图与裁剪图（保留 PDF）")
    parser.add_argument("keys", nargs="*", help="留空则扫全部 tmp 卷目录")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    root = Path(B.TMP)
    papers = json.loads(Path(B.PAPERS).read_text(encoding="utf-8"))

    if args.keys:
        keys = list(args.keys)
    else:
        keys = []
        for subj in sorted(root.iterdir()):
            if not subj.is_dir() or subj.name.startswith("_"):
                continue
            for paper in sorted(subj.iterdir()):
                if not paper.is_dir():
                    continue
                parts = paper.name.split("-")
                if len(parts) != 3:
                    continue
                keys.append(f"{subj.name}/{parts[0]}/{parts[1]}/{parts[2]}")

    removed, freed, refused, violations = [], 0, [], []
    for key in keys:
        stage = (papers.get(key) or {}).get("stage")
        if stage in DONE_STAGES:
            tmp_dir = P.paper_tmp(key)
            if image_targets(tmp_dir):
                violations.append(f"{key}: stage={stage} 仍有图片残留，交由 cleanup_paper 处理")
            continue
        tmp_dir = P.paper_tmp(key)
        targets = image_targets(tmp_dir)
        if not targets:
            continue
        pdfs = list(tmp_dir.glob("*.pdf"))
        if not pdfs:
            refused.append(f"{key}: 无 PDF，跳过（图片可能是唯一线索）")
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
        if not args.dry_run:
            leftover = [t for t in targets if t.exists()]
            if leftover:
                refused.append(f"{tmp_dir}: 残留 {len(leftover)} 个")
            if not list(tmp_dir.glob("*.pdf")):
                refused.append(f"{key}: PDF 在清理后消失，异常")

    label = "image_sweep_dry_run" if args.dry_run else "image_sweep"
    for path, size in removed[:40]:
        print(f"  del {size:>9,}  {path}")
    if len(removed) > 40:
        print(f"  ... 其余 {len(removed) - 40} 个省略")
    for item in refused:
        print(f"  REFUSED {item}")
    for item in violations:
        print(f"  VIOLATION {item}")
    print(f"{label}: files={len(removed)} freed_bytes={freed} refused={len(refused)} violations={len(violations)}")
    if not args.dry_run:
        def _key_of(path: str) -> str:
            try:
                rel = Path(path).resolve().relative_to(root.resolve()).parts
            except ValueError:
                return "?"
            return f"{rel[0]}/{rel[1]}" if len(rel) > 1 else "?"

        B.append_jsonl(B.CLEANUP, {
            "stage": label, "key": "*", "at": B.now_iso(),
            "deleted": len(removed), "freed_bytes": freed,
            "keys": sorted({_key_of(p) for p, _ in removed}),
            "problems": refused + violations,
            "note": "逐页渲染图与裁剪图；可从保留的 PDF 按同一 bbox 重新渲染；PDF、索引、日志一律未动",
        })
    return 1 if refused or violations else 0


if __name__ == "__main__":
    raise SystemExit(main())
