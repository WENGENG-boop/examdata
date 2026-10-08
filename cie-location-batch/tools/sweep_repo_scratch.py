# -*- coding: utf-8 -*-
"""一次性：清扫仓库范围内可再生的临时 scratch（审计后白名单，逐条显式）。

白名单：
  - examdata/.pytest_cache/examdata-tests-*（11 个 pytest basetemp 工件副本，审计确认为
    .data/artifacts 的真字节副本、无 reparse、测试可重生成）
  - examdata/pytest-of-weo、cie-location-batch/pytest-of-weo（pytest basetemp 输出）
  - examdata/tmp_sample_crops、tmp_final_crop、tmp_check_crops、tmp_q14_page12.png
    （本会话裁剪/核验临时图，可再生）
  - cie-location-batch/numfix_hys75ig9、numfix_md0ccec5（numfix 测试存根输出）

安全规则（代码强制）：
  - 目标必须位于 examdata/ 或 cie-location-batch/ 之下，且不落在保护前缀内
  - 目标自身与内部任何 reparse point（符号链接/junction）→ 整目标拒删
  - 目标内 600 秒内仍有写入 → 整目标拒删
  - 逐文件 unlink（失败 chmod 重试），自底向上 rmdir，复核消失，残留写实
  - 绝不 rmtree；只动白名单路径
结果：每目标一条 cleanup.jsonl（stage=repo_scratch_sweep）+ 汇总 + 删除清单文件。
"""
from __future__ import annotations

import os
import stat
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import batchlib as B
from cleanup_paper import is_reparse_point, unsafe_component

E = Path("C:/Users/weo/Desktop/api/examdata")
BATCH = Path(B.BATCH_ROOT)
ALLOWED_ROOTS = (E, BATCH)
PROTECTED = (
    Path(B.SERVICE_DATA_DIR),
    E / ".data",
    E / ".git",
    BATCH / "indexes",
    BATCH / "tmp",
)
FRESH_SECONDS = 600
DRY = "--dry-run" in sys.argv

TESTS_IDS = ("16halq6w", "1qcxd0gh", "8hvs737u", "a2ag7w26", "blc35ye1", "c3ba4yyp",
             "dnikgyrn", "rrgku3xj", "wi5rucj2", "yummiznj", "yzpr2dbo")

TARGETS = (
    [(E / ".pytest_cache" / f"examdata-tests-{i}", "pytest_basetemp_artifact_copy")
     for i in TESTS_IDS]
    + [
        (E / "pytest-of-weo", "pytest_basetemp"),
        (E / "tmp_sample_crops", "session_crop_pngs"),
        (E / "tmp_final_crop", "session_crop_pngs"),
        (E / "tmp_check_crops", "session_crop_pngs"),
        (E / "tmp_q14_page12.png", "session_crop_png"),
        (BATCH / "numfix_hys75ig9", "test_stub_output"),
        (BATCH / "numfix_md0ccec5", "test_stub_output"),
        (BATCH / "pytest-of-weo", "pytest_basetemp"),
    ]
)

NOTES = {
    "pytest_basetemp_artifact_copy": "pytest basetemp 工件副本（.data/artifacts 真字节副本；审计确认无 reparse；测试可重生成）",
    "pytest_basetemp": "pytest basetemp 输出（可重生成）",
    "session_crop_pngs": "本会话裁剪/核验临时 PNG（可重生成）",
    "session_crop_png": "本会话裁剪/核验临时 PNG（可重生成）",
    "test_stub_output": "numfix 测试存根输出（单文件小 JSON）",
}

MANIFEST = Path(str(B.WORK)) / "repo_scratch_sweep_manifest.txt"


def protected(path: Path) -> str | None:
    s = str(path).lower()
    for p in PROTECTED:
        ps = str(p).lower()
        if s == ps or s.startswith(ps + os.sep):
            return f"位于保护前缀 {p}"
    return None


def inside_roots(path: Path) -> bool:
    s = str(path).lower()
    return any(s.startswith(str(r).lower() + os.sep) for r in ALLOWED_ROOTS)


def collect(target: Path):
    if not target.exists():
        return [], [], "absent"
    if is_reparse_point(target):
        return [], [], "目标是链接/重解析点"
    root = E if str(target).lower().startswith(str(E).lower() + os.sep) else BATCH
    bad = unsafe_component(root, target)
    if bad:
        return [], [], bad
    files, dirs = [], []
    newest = 0.0
    if target.is_file():
        st = target.lstat()
        files.append(target)
        newest = st.st_mtime
    else:
        for dirpath, dirnames, filenames in os.walk(str(target), followlinks=False):
            d = Path(dirpath)
            dirs.append(d)
            for name in dirnames:
                p = d / name
                if is_reparse_point(p):
                    return [], [], f"内部含重解析点：{p}"
            for name in filenames:
                p = d / name
                try:
                    st = p.lstat()
                except OSError as exc:
                    return [], [], f"lstat 失败：{p} ({exc})"
                if is_reparse_point(p):
                    return [], [], f"内部含链接文件：{p}"
                files.append(p)
                if st.st_mtime > newest:
                    newest = st.st_mtime
    if newest and (time.time() - newest) < FRESH_SECONDS:
        return [], [], f"目标内 {int(time.time() - newest)} 秒前仍有写入，拒删"
    return files, dirs, None


def sweep_one(target: Path, label: str, out_lines: list) -> dict:
    ap = Path(os.path.abspath(str(target)))
    rec = {"stage": "repo_scratch_sweep", "key": "*", "at": B.now_iso(),
           "target": str(ap), "label": label, "note": NOTES.get(label, ""),
           "status": None, "deleted": 0, "freed_bytes": 0, "dirs_removed": 0,
           "exts": {}, "failures": [], "residual_bytes": 0, "files_sample": []}
    if not inside_roots(ap):
        rec["status"] = "refused"
        rec["failures"] = ["不在允许根（examdata/ 或 cie-location-batch/）内"]
        return rec
    guard = protected(ap)
    if guard:
        rec["status"] = "refused"
        rec["failures"] = [guard]
        return rec
    files, dirs, refusal = collect(ap)
    if refusal == "absent":
        rec["status"] = "absent"
        return rec
    if refusal:
        rec["status"] = "refused"
        rec["failures"] = [refusal]
        return rec
    total_bytes = 0
    for p in files:
        try:
            total_bytes += p.lstat().st_size
        except OSError:
            pass
    print(f"[sweep] {ap}  files={len(files)} bytes={total_bytes:,}  label={label}", flush=True)
    out_lines.append(f"## {ap}  ({label})  files={len(files)} bytes={total_bytes}")
    if DRY:
        rec.update(status="dry_run", deleted=len(files), freed_bytes=total_bytes)
        rec["files_sample"] = [str(p) for p in files[:20]]
        return rec
    deleted = freed = 0
    exts = Counter()
    failures = []
    for p in files:
        try:
            size = p.lstat().st_size
        except OSError:
            size = 0
        try:
            os.unlink(p)
        except OSError:
            try:
                os.chmod(p, stat.S_IWRITE | stat.S_IREAD)
                os.unlink(p)
            except OSError as exc:
                failures.append(f"{p} :: {exc}")
                out_lines.append(f"FAIL\t{p}\t{exc}")
                continue
        deleted += 1
        freed += size
        exts[p.suffix.lower() or "(none)"] += 1
        out_lines.append(str(p))
        if deleted % 2000 == 0:
            print(f"  ... {ap} deleted={deleted}/{len(files)}", flush=True)
    dirs_removed = 0
    for d in sorted(dirs, key=lambda x: len(x.parts), reverse=True):
        try:
            os.rmdir(d)
            dirs_removed += 1
        except OSError:
            pass
    residual_bytes = 0
    if ap.exists():
        for dirpath, _dn, filenames in os.walk(str(ap), followlinks=False):
            for name in filenames:
                try:
                    residual_bytes += (Path(dirpath) / name).lstat().st_size
                except OSError:
                    pass
    gone = not ap.exists()
    rec.update({
        "status": "deleted" if (gone and not failures) else "partial",
        "deleted": deleted, "freed_bytes": freed, "dirs_removed": dirs_removed,
        "exts": dict(exts.most_common(15)),
        "failures": failures[:20],
        "residual_bytes": residual_bytes,
        "files_sample": [str(p) for p in files[:20]],
        "files_manifest": str(MANIFEST),
    })
    return rec


def main() -> int:
    t0 = time.time()
    whitelist_names = {f"examdata-tests-{i}" for i in TESTS_IDS}
    extras = sorted(p.name for p in (E / ".pytest_cache").glob("examdata-tests-*")
                    if p.name not in whitelist_names)
    if extras:
        print(f"[warn] 发现白名单外的新 examdata-tests-*（不删）：{extras}", flush=True)
    print(f"[sweep] start targets={len(TARGETS)} dry={DRY}", flush=True)
    out_lines = [f"repo_scratch_sweep manifest  generated_at={B.now_iso()}  dry_run={DRY}",
                 f"extras_not_in_whitelist={extras}"]
    results = [sweep_one(t, label, out_lines) for t, label in TARGETS]
    total_deleted = sum(r["deleted"] for r in results)
    total_freed = sum(r["freed_bytes"] for r in results)
    status_counts = dict(Counter(r["status"] for r in results))
    print(f"[sweep] done deleted={total_deleted} freed={total_freed:,}B "
          f"status={status_counts} elapsed={time.time()-t0:.1f}s", flush=True)
    for r in results:
        line = (f"  {str(r['status']):<8} {r['deleted']:>7} {r['freed_bytes']:>15,}  {r['target']}")
        if r["failures"]:
            line += f"  ! {r['failures'][:1]}"
        print(line, flush=True)
    if not DRY:
        for r in results:
            B.append_jsonl(B.CLEANUP, r)
        B.append_jsonl(B.CLEANUP, {
            "stage": "repo_scratch_sweep_summary", "key": "*", "at": B.now_iso(),
            "targets": len(results), "sum_deleted": total_deleted,
            "sum_freed_bytes": total_freed, "status_counts": status_counts,
            "manifest": str(MANIFEST),
            "note": "仓库 scratch 清扫汇总；删除清单见 manifest"})
        MANIFEST.write_text("\n".join(out_lines) + "\n", encoding="utf-8")
        print(f"[sweep] manifest: {MANIFEST}", flush=True)
    bad = [r for r in results if r["status"] not in ("deleted", "absent")]
    return 2 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
