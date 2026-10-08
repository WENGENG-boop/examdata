"""一次性：删除 work/ 中 0472/0580 已 cleaned 卷的核验辅助 PNG（只删 PNG）。

范围（逐文件，绝不递归删目录）：
  work/*.png                —— 顶层 10 张（_dotcheck_*、_p10_*、_p3top）
  work/_p11_strips/*.png    —— 4 张（0472/2026/Jun/22 Q5@p11 边界条带）
  work/sheets/*.png         —— 14 张（0472 页脚/边界/probe 条带）
  work/zoom/*.png           —— 19 张（0580/2024/Jun/11 M14/M22 gap/tight 核验）

只删 PNG；.html、脚本、proposals、drafts、JSON、日志一律不动。

门禁（三个卷全部通过才删；任一失败整体拒绝）：
  0472/2026/Jun/21、0472/2026/Jun/22、0580/2024/Jun/11：
  stage=cleaned + cleanup.jsonl 有 freed>0 的 cleaned 记录 + 批次索引存在 +
  服务索引存在 + 自 cleaned 以来无未解决错误（复用 sweep_work_media.gate）。

安全：绝对路径逐个 unlink；逐段拒绝 symlink/junction/reparse point；删除后逐个
复核消失；结果追加 cleanup.jsonl（stage=work_media_sweep_ext）。
默认 dry-run；--apply 执行。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import batchlib as B
import cleanup_paper as C
import sweep_work_media as W

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

KEYS = ["0472/2026/Jun/21", "0472/2026/Jun/22", "0580/2024/Jun/11"]

NOTE = (
    "work/ 顶层 _dotcheck_*/_p10_*/_p3top、_p11_strips/、sheets/、zoom/ 共 47 张核验辅助 PNG；"
    "分属 0472/2026/Jun/21、0472/2026/Jun/22、0580/2024/Jun/11 三卷（均已 cleaned）。"
    "门禁=三卷 stage cleaned + cleanup 记录 freed>0 + 批次索引 + 服务索引 + 无新未解决错误；"
    "核验结论保存在 verification.jsonl，图片可由原件重渲染；.html/脚本/proposals/JSON 未动。"
)


def collect() -> list[Path]:
    out: list[Path] = []
    work = Path(B.WORK)
    for p in sorted(work.glob("*.png")):
        if p.is_file():
            out.append(p)
    for sub in ("_p11_strips", "sheets", "zoom"):
        d = work / sub
        if d.is_dir():
            out += [p for p in sorted(d.glob("*.png")) if p.is_file()]
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    papers = json.loads(B.PAPERS.read_text(encoding="utf-8"))
    cleanup_records = C.read_jsonl(B.CLEANUP)
    root = Path(B.WORK)

    problems: list[str] = []
    for key in KEYS:
        probs, info = W.gate(key, papers, cleanup_records)
        print(f"gate {key}: {'OK' if not probs else 'FAIL'} {json.dumps(info, ensure_ascii=False)}")
        problems += [f"{key}: {p}" for p in probs]

    targets = collect()
    print(f"候选目标 {len(targets)} 个 / {sum(t.stat().st_size for t in targets):,} 字节")
    for t in targets:
        print("  target", t.relative_to(root))

    if problems:
        print("门禁失败，拒绝删除：")
        for p in problems:
            print("  SKIP:", p)
        return 1

    removed: list[tuple[str, int]] = []
    refused: list[str] = []
    freed = 0
    for t in targets:
        problem = C.unsafe_component(root, t)
        if problem:
            refused.append(f"{t}: {problem}")
            continue
        size = t.stat().st_size
        if args.apply:
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

    for p, s in removed:
        print(f"  {'del' if args.apply else 'would-del'} {s:>9,}  {p}")
    for r in refused:
        print("  REFUSED", r)
    mode = "applied" if args.apply else "dry_run"
    print(f"work_media_sweep_ext[{mode}]: files={len(removed)} freed_bytes={freed} refused={len(refused)}")

    if args.apply and removed:
        B.append_jsonl(B.CLEANUP, {
            "stage": "work_media_sweep_ext",
            "key": "*",
            "at": B.now_iso(),
            "deleted": len(removed),
            "freed_bytes": freed,
            "keys": KEYS,
            "files": [p for p, _ in removed],
            "problems": refused,
            "note": NOTE,
        })
    return 1 if refused else 0


if __name__ == "__main__":
    raise SystemExit(main())
