"""一次性白名单清理：work scratch 目录与 tmp_dl 冒烟测试产物（绝不 rmtree）。

范围（仅以下四项，逐文件 Path.unlink）：
  A. work/tmp_spec/      —— 本批次 lead-band 诊断的探针 PDF/PNG、OCR 中间产物、一次性脚本与规格 JSON
  B. work/msrows/        —— 8 张 MS 行裁剪 PNG
  C. work/msrows.html    —— 上述 PNG 的查看器（删除图片后即成死链）
  D. Desktop/api/tmp_dl/ —— 早前会话 session_f424afc5（2026-09-29「验证所有api调用」）用 curl 对
     本地服务做冒烟测试的下载产物（cie_qp.pdf=0580_s24_qp_11、cie_both.zip 同卷 qp+ms、edx_q1.png）

依据：全批次与仓库 grep 无任何代码/流程引用；用户要求「本机不保留试卷 PDF/图片，只留定位信息」；
      以上内容均可随时由服务重新下载。结论均已记录于 verification.jsonl / errors.jsonl。

安全：绝对路径逐个删除；从白名单根起逐段拒绝 symlink/junction/reparse point；
      删除后逐个复核消失；结果追加 cleanup.jsonl（stage=work_scratch_sweep），不覆盖历史。
"""
from __future__ import annotations

import argparse
import os
import stat
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import batchlib as B

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BATCH = Path("C:/Users/weo/Desktop/api/cie-location-batch")
DESKTOP_API = Path("C:/Users/weo/Desktop/api")

# 每个白名单根：只删根内的常规文件
ROOTS = [
    BATCH / "work" / "tmp_spec",
    BATCH / "work" / "msrows",
    DESKTOP_API / "tmp_dl",
]
# 单文件白名单
FILES = [
    BATCH / "work" / "msrows.html",
]

REPARSE = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)


def reparse_or_link(p: Path) -> bool:
    try:
        st = os.lstat(p)
    except OSError:
        return True
    if stat.S_ISLNK(st.st_mode):
        return True
    return bool(getattr(st, "st_file_attributes", 0) & REPARSE)


def unsafe_path(root: Path, target: Path) -> str | None:
    """从 root 起逐段检查 target 的每个组成部分（含自身）。"""
    try:
        rel = target.resolve().relative_to(root.resolve())
    except ValueError:
        return f"不在白名单根 {root} 内"
    cur = root.resolve()
    for part in rel.parts:
        cur = cur / part
        if reparse_or_link(cur):
            return f"组件 {cur} 是 symlink/junction/reparse point"
    return None


def collect() -> list[tuple[Path, Path]]:
    out = []
    for root in ROOTS:
        if not root.is_dir():
            continue
        for p in sorted(root.rglob("*")):
            if p.is_file():
                out.append((root, p))
    for f in FILES:
        if f.is_file():
            out.append((f.parent, f))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    targets = collect()
    removed, freed, refused = [], 0, []
    for root, t in targets:
        problem = unsafe_path(root, t)
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

    label = "work_scratch_sweep_dry_run" if args.dry_run else "work_scratch_sweep"
    for p, s in removed:
        print(f"  del {s:>10,}  {p}")
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
            "files": [p for p, _ in removed][:400],
            "problems": refused,
            "note": ("work/tmp_spec + work/msrows + work/msrows.html 诊断 scratch；"
                     "tmp_dl 为 session_f424afc5 冒烟测试下载（0580_s24 qp/ms + edx 裁剪），"
                     "非批次工件、可重新下载；无任何代码引用"),
        })
    return 1 if refused else 0


if __name__ == "__main__":
    raise SystemExit(main())
