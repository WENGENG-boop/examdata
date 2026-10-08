"""删除已验收完成卷遗留在 work/ 与旧试点目录的中间图片与 PDF（只删白名单）。

背景：
- 9715/2023/Nov/21 与 0509/2026/Jun/11 的视觉核验中间产物散落在 work/ 顶层与
  子目录（页面图、裁剪图、clip 测试图）；
- 9709/2024/Jun/11 旧试点 cie-index-batch-2026-10-01 留有 2 个 PDF 与 61 张图。

永久索引、日志、sheets、proposals、脚本一律不动。

每卷门禁（全部满足才进入删除）：
1. papers.json stage == "cleaned"（cleanup_paper 六项条件通过后才会到 cleaned）；
2. cleanup.jsonl 存在该 key 的 cleaned 记录且 freed_bytes > 0；
3. 批次永久索引 indexes/<subject>/<year>-<season>-<paper>/cie-index.json 存在；
4. 服务索引 <SERVICE>/question_indexes/cie/<qp_sha256>.json 存在；
5. 自最后 cleaned 记录以来无未解决 errors.jsonl 记录（复用 cleanup_paper.unresolved_errors）；
6. 9709 试点：2 个 PDF 的 sha256 必须与 papers.json 的 qp_document/ms_document.sha256 一致。

安全：逐文件 Path.unlink；目标必须位于白名单根（work/ 或试点目录）内；逐段拒绝
符号链接/junction/重解析点；目录内非 .png 文件与未列入白名单的同类文件只报告不删。
默认 dry-run；--apply 执行并追加 cleanup.jsonl（stage=work_media_sweep）。
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

PILOT = Path("C:/Users/weo/Desktop/api/cie-index-batch-2026-10-01")
SERVICE_INDEX_DIR = B.SERVICE_DATA_DIR / "question_indexes" / "cie"

PLAN: dict[str, dict] = {
    "9715/2023/Nov/21": {
        "root": B.WORK,
        "dirs": ("9715-final-region-crops", "9715-current-crops", "9715-rendered"),
        "globs": ("9715-final-crops-*.png", "9715-current-crops-*.png", "9715-clip-test-*.png"),
        "pdf_glob": "9715*.pdf",
        "pdfs": (),
        "sha_pairs": (),
    },
    "0509/2026/Jun/11": {
        "root": B.WORK,
        "dirs": ("0509-page-images", "0509-current-crops", "0509-ms-layout-crops"),
        "globs": (),
        "pdf_glob": "0509*.pdf",
        "pdfs": (),
        "sha_pairs": (),
    },
    "9709/2024/Jun/11": {
        "root": PILOT,
        "dirs": ("review/all-question-crops",),
        "globs": ("review/*.png",),
        "pdf_glob": None,  # PILOT 全树 PDF 单独核对
        "pdfs": ("9709/2024-Jun-11/9709_s24_qp_11.pdf",
                 "9709/2024-Jun-11/9709_s24_ms_11.pdf"),
        "sha_pairs": (("9709/2024-Jun-11/9709_s24_qp_11.pdf", "qp_sha256"),
                      ("9709/2024-Jun-11/9709_s24_ms_11.pdf", "ms_sha256")),
    },
}


def gate(key: str, papers: dict, cleanup_records: list[dict]) -> tuple[list[str], dict]:
    rec = papers.get(key) or {}
    problems: list[str] = []
    info: dict = {"stage": rec.get("stage")}
    if rec.get("stage") != "cleaned":
        problems.append(f"stage={rec.get('stage')!r}，不是 cleaned")
    cleaned = [r for r in cleanup_records
               if r.get("key") == key and r.get("stage") == "cleaned"]
    freed_ok = any(int(r.get("freed_bytes") or 0) > 0 for r in cleaned)
    info["cleaned_records"] = len(cleaned)
    info["cleaned_freed_ok"] = freed_ok
    if not freed_ok:
        problems.append("cleanup.jsonl 没有 freed_bytes>0 的 cleaned 记录")
    last_cleaned_at = max((str(r.get("at") or "") for r in cleaned), default="")

    subject, year, season, paper = key.split("/")
    index_file = B.index_dir(subject, int(year), season, paper) / "cie-index.json"
    info["index_path"] = str(index_file)
    if not index_file.is_file():
        problems.append(f"批次永久索引不存在：{index_file}")

    qp_sha = rec_sha(rec, "qp_sha256")
    svc = SERVICE_INDEX_DIR / f"{qp_sha}.json"
    info["service_index_path"] = str(svc)
    declared = str(rec.get("service_index_path") or "")
    if declared and Path(declared).name != svc.name:
        problems.append(f"service_index_path 与 qp_document.sha256 不一致：{declared}")
    if not qp_sha or not svc.is_file():
        problems.append(f"服务索引不存在：{svc}")

    since = max(last_cleaned_at, str(rec.get("stage_at") or ""))
    bad = C.unresolved_errors(key, since or None)
    info["unresolved_since_cleaned"] = len(bad)
    if bad:
        problems.append(f"自 cleaned 以来仍有 {len(bad)} 条未解决错误："
                        f"{json.dumps(bad[-1], ensure_ascii=False)[:160]}")
    return problems, info


def rec_sha(rec: dict, field: str) -> str:
    """兼容两代 papers.json 字段：旧 qp_sha256/ms_sha256 → 新 qp_document.sha256。"""
    if field in ("qp_sha256", "ms_sha256"):
        role = field[:2]
        return str((rec.get(f"{role}_document") or {}).get("sha256")
                   or rec.get(field) or "")
    return str(rec.get(field) or "")


def sha_check(plan: dict, root: Path, rec: dict) -> list[str]:
    problems: list[str] = []
    for rel, field in plan.get("sha_pairs") or ():
        path = root / rel
        if not path.is_file():
            continue
        expect = rec_sha(rec, field)
        actual = B.sha256_file(path)
        if not expect or actual != expect:
            problems.append(f"{path} sha256={actual[:16]}… 与 papers.json {field}="
                            f"{expect[:16]}… 不一致，拒绝删除")
    return problems


def collect(plan: dict, root: Path) -> tuple[list[Path], list[Path]]:
    targets: list[Path] = []
    extras: list[Path] = []
    for name in plan["dirs"]:
        base = root / name
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_file():
                continue
            if path.suffix.lower() == ".png":
                targets.append(path)
            else:
                extras.append(path)
    for pattern in plan["globs"]:
        for path in sorted(root.glob(pattern)):
            if path.is_file() and path.suffix.lower() == ".png":
                targets.append(path)
    for rel in plan["pdfs"]:
        path = root / rel
        if path.is_file():
            targets.append(path)
    seen: set[str] = set()
    uniq: list[Path] = []
    for path in targets:
        if str(path) not in seen:
            seen.add(str(path))
            uniq.append(path)
    return uniq, extras


def coverage_problems(key: str, plan: dict, root: Path, targets: list[Path],
                      extras: list[Path]) -> list[str]:
    problems: list[str] = []
    covered = {str(p) for p in targets}
    universe: list[Path] = []
    if plan.get("pdf_glob"):
        universe += [p for p in root.glob(plan["pdf_glob"]) if p.is_file()]
    subject = key.split("/")[0]
    universe += [p for p in root.glob(f"{subject}*.png") if p.is_file()]
    if key == "9709/2024/Jun/11":
        universe += [p for p in root.rglob("*.png") if p.is_file()]
        allowed_pdf = {str(root / rel) for rel in plan["pdfs"]}
        universe += [p for p in root.rglob("*.pdf") if p.is_file()
                     and str(p) not in allowed_pdf]
    for path in universe:
        if str(path) not in covered:
            problems.append(f"{key}: 未列入白名单的同类文件（不删，待人工确认）：{path}")
    for path in extras:
        problems.append(f"{key}: 白名单目录内非 png 文件（不删）：{path}")
    return problems


def do_delete(targets: list[Path], root: Path, apply: bool) -> tuple[list, list, int]:
    removed: list[tuple[str, int]] = []
    refused: list[str] = []
    freed = 0
    for target in targets:
        problem = C.unsafe_component(root, target)
        if problem:
            refused.append(problem)
            continue
        if not target.exists():
            refused.append(f"{target} 已不存在（竞态）")
            continue
        try:
            size = target.stat().st_size
        except OSError:
            size = 0
        if not apply:
            removed.append((str(target), size))
            freed += size
            continue
        try:
            target.unlink()
        except OSError as exc:
            refused.append(f"{target} 删除失败：{exc}")
            continue
        if target.exists():
            refused.append(f"{target} 删除后仍然存在")
            continue
        removed.append((str(target), size))
        freed += size
    return removed, refused, freed


def main() -> int:
    parser = argparse.ArgumentParser(description="删除 work/ 与旧试点里已完成卷的中间图片/PDF")
    parser.add_argument("--key", action="append", default=None,
                        help="只处理指定 key（可多次），默认全部白名单 key")
    parser.add_argument("--apply", action="store_true", help="真正删除；默认 dry-run")
    args = parser.parse_args()

    papers = json.loads(B.PAPERS.read_text(encoding="utf-8"))
    cleanup_records = C.read_jsonl(B.CLEANUP)
    keys = args.key or list(PLAN)

    total_deleted = 0
    total_freed = 0
    all_refused: list[str] = []
    all_problems: list[str] = []
    skipped: list[tuple[str, list[str]]] = []
    per_key: dict[str, dict] = {}

    for key in keys:
        plan = PLAN.get(key)
        if not plan:
            all_refused.append(f"{key}: 不在白名单计划内")
            continue
        root = plan["root"]
        print(f"== {key}  (root={root})")
        if not root.is_dir():
            skipped.append((key, [f"根目录不存在：{root}"]))
            print(f"   SKIP 根目录不存在：{root}")
            continue

        problems, info = gate(key, papers, cleanup_records)
        problems += sha_check(plan, root, papers.get(key) or {})
        targets, extras = collect(plan, root)
        all_problems += coverage_problems(key, plan, root, targets, extras)
        target_bytes = sum(t.stat().st_size for t in targets if t.exists())
        print(f"   gate={'OK' if not problems else 'FAIL'}  info={json.dumps(info, ensure_ascii=False)}")
        print(f"   候选目标 {len(targets)} 个 / {target_bytes:,} 字节")
        if problems:
            skipped.append((key, problems))
            for item in problems:
                print(f"   SKIP: {item}")
            continue

        removed, refused, freed = do_delete(targets, root, args.apply)
        if args.apply:
            residual = [str(t) for t in targets if t.exists()]
            if residual:
                refused += [f"{p} 删除后仍然存在" for p in residual]
        for path, size in removed[:12]:
            print(f"   {'del' if args.apply else 'would-del'} {size:>9,}  {path}")
        if len(removed) > 12:
            print(f"   ... 其余 {len(removed) - 12} 个省略")
        for item in refused:
            print(f"   REFUSED {item}")
        total_deleted += len(removed)
        total_freed += freed
        all_refused += refused
        per_key[key] = {"files": len(removed), "freed_bytes": freed, "root": str(root)}
        print(f"   {'已删除' if args.apply else 'DRY-RUN'} files={len(removed)} freed={freed:,}")

    print(f"--- work_media_sweep{' (apply)' if args.apply else ' (dry-run)'}: "
          f"files={total_deleted} freed_bytes={total_freed} "
          f"refused={len(all_refused)} problems={len(all_problems)} skipped={len(skipped)}")
    for key, reasons in skipped:
        print(f"   SKIPPED {key}: {'; '.join(reasons)[:300]}")
    for item in all_problems:
        print(f"   PROBLEM {item}")

    if args.apply and (total_deleted or all_refused or all_problems):
        B.append_jsonl(B.CLEANUP, {
            "at": B.now_iso(),
            "stage": "work_media_sweep",
            "key": "*",
            "deleted": total_deleted,
            "freed_bytes": total_freed,
            "keys": sorted(per_key),
            "per_key": per_key,
            "problems": all_refused + all_problems,
            "note": "work/ 与旧试点中间图片/PDF；门禁=stage cleaned+cleaned记录+批次索引+"
                    "服务索引+无新未解决错误；9709 PDF 删前核对 sha256；"
                    "永久索引、日志、sheets、脚本未动",
        })
        print("   已追加 cleanup.jsonl stage=work_media_sweep")

    return 1 if (all_refused or all_problems) else 0


if __name__ == "__main__":
    raise SystemExit(main())
