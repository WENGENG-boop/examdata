"""一次性：清扫 BATCH_ROOT 三个未覆盖 tmp 目录与 examdata/tmpwork 试卷内容文件。

范围（逐文件白名单，绝不 rmtree）：
  A. tmp/0580fx/**           —— 0580/2024/Jun/11 的 fixture 副本（key 0580fx），
                                内容经浏览器目视确认为 0580/11 May/June 2024；
                                sha 与已 cleaned 卷验证原件不同，属测试产物。
  B. tmp/9709/2026-Mar-12/** —— 由 examdata/tmpwork 的 9709_m26_qp_12.pdf
                                (sha 47a6c66a…) 生成的裁剪图与 manifest；该卷
                                stage=discovered，Phase C 将重新下载重验。
  C. tmp/_scratch/**         —— 0472/0580 draft index、crop 脚本、probe 图等
                                一次性诊断产物（最终索引在 indexes/，备份在 work/）。
  D. examdata/tmpwork 中试卷内容文件（.pdf/.png/.jpg/.zip，及魔数为 PDF/PNG/ZIP
     的 .bin/无后缀文件）；JSON 文本响应、脚本、日志保留。tmpwork 为 gitignored
     测试残留（.gitignore:25）；tests/test_paperqa_locator.py 对 wec11.pdf 有
     skipif 保护，删除后真实样本回归测试安全跳过。

安全：绝对路径逐个删除；逐段拒绝 symlink/junction/reparse point；删除后逐个
复核消失；结果追加 cleanup.jsonl（stage=residual_sweep），不覆盖历史。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import batchlib as B
import cleanup_paper as C

TMP = Path(B.TMP)
EXAMDATA_TMPWORK = Path("C:/Users/weo/Desktop/api/examdata/tmpwork")

BATCH_DIRS = [
    ("0580fx", TMP / "0580fx"),
    ("9709/2026-Mar-12", TMP / "9709" / "2026-Mar-12"),
    ("_scratch", TMP / "_scratch"),
]

TMPWORK_EXTS = {".pdf", ".png", ".jpg", ".jpeg", ".zip"}
BINARY_MAGICS = (b"%PDF", b"\x89PNG", b"\xff\xd8\xff", b"PK\x03\x04")

NOTE = (
    "A) tmp/0580fx/** = 0580/2024/Jun/11 fixture 副本（key 0580fx；内容经浏览器目视确认 "
    "为 0580/11 May/June 2024 封面；sha 与已 cleaned 卷验证原件不同，属测试产物；"
    "提案记录保留在 work/proposals/0580fx/2024-Jun-11.json）。"
    "B) tmp/9709/2026-Mar-12/** = 由 examdata/tmpwork/paperqa-live/python-0/9709_m26_qp_12.pdf "
    "(sha 47a6c66a3223cc5d8ac920040ac8a845d9887d4011cefde42e923d403aea9652) 生成的裁剪图与 "
    "manifest（generated_at 2026-10-03T22:29:29+0800）；该卷 stage=discovered，Phase C 重新下载重验。"
    "C) tmp/_scratch/** = 0472/0580 draft index、crop_9709.py、probe 图等一次性诊断产物"
    "（最终索引在 indexes/，0580 修复前备份在 work/0580-2024-Jun-11-index-before-fix.json）。"
    "D) examdata/tmpwork 试卷内容文件（CIE 0580/9709 与 Edexcel wec11 测试副本及裁剪图、"
    "含试卷的 zip、魔数为 PDF/PNG/ZIP 的 .bin）；tmpwork 为 gitignored 测试残留"
    "（.gitignore:25）；tests/test_paperqa_locator.py 对 wec11.pdf 有 skipif 保护，"
    "删除后真实样本回归测试安全跳过；JSON 文本响应与脚本/日志未触碰。"
)


def batch_targets() -> list[tuple[str, Path]]:
    out: list[tuple[str, Path]] = []
    for label, d in BATCH_DIRS:
        if not d.is_dir():
            continue
        for p in sorted(d.rglob("*")):
            if p.is_file():
                out.append((label, p))
    return out


def tmpwork_targets() -> list[tuple[str, Path]]:
    out: list[tuple[str, Path]] = []
    if not EXAMDATA_TMPWORK.is_dir():
        return out
    for p in sorted(EXAMDATA_TMPWORK.rglob("*")):
        if not p.is_file():
            continue
        ext = p.suffix.lower()
        if ext in TMPWORK_EXTS:
            out.append(("tmpwork", p))
            continue
        if ext in (".bin", ""):
            try:
                with p.open("rb") as fh:
                    head = fh.read(4)
            except OSError:
                continue
            if head.startswith(BINARY_MAGICS):
                out.append(("tmpwork-bin", p))
    return out


def main() -> int:
    dry = "--apply" not in sys.argv
    removed: list[tuple[str, str, int]] = []
    refused: list[str] = []
    groups: dict[str, list[int]] = {}

    plan = [(TMP, batch_targets()), (EXAMDATA_TMPWORK, tmpwork_targets())]
    for root, targets in plan:
        root = root.resolve()
        for label, t in targets:
            problem = C.unsafe_component(root, t)
            if problem:
                refused.append(f"{t}: {problem}")
                continue
            try:
                size = t.stat().st_size
            except OSError as exc:
                refused.append(f"{t}: stat 失败 {exc}")
                continue
            if not dry:
                try:
                    t.unlink()
                except OSError as exc:
                    refused.append(f"{t}: {exc}")
                    continue
                if t.exists():
                    refused.append(f"{t}: 删除后仍然存在")
                    continue
            removed.append((label, str(t), size))
            g = groups.setdefault(label, [0, 0])
            g[0] += 1
            g[1] += size

    freed = sum(s for _, _, s in removed)
    for label, p, s in removed:
        print(f"  del {s:>10,}  [{label}] {p}")
    print("--- groups ---")
    for k in sorted(groups):
        n, b = groups[k]
        print(f"  {k:24s} files={n:4d} bytes={b:,}")
    for r in refused:
        print("  REFUSED", r)
    mode = "dry_run" if dry else "applied"
    print(f"residual_sweep[{mode}]: files={len(removed)} freed_bytes={freed} refused={len(refused)}")

    if not dry and removed:
        B.append_jsonl(B.CLEANUP, {
            "stage": "residual_sweep",
            "key": "*",
            "at": B.now_iso(),
            "deleted": len(removed),
            "freed_bytes": freed,
            "groups": {k: {"files": v[0], "bytes": v[1]} for k, v in sorted(groups.items())},
            "files": [p for _, p, _ in removed][:500],
            "problems": refused,
            "note": NOTE,
        })
    return 1 if refused else 0


if __name__ == "__main__":
    raise SystemExit(main())
