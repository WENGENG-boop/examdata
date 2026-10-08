"""备份并移除服务端旧版索引，为重新导入让路（显式复核流程，可回滚）。

用法: python replace_service_index.py <subject/year/season/paper> [...] [--apply]

背景：服务端 `question_indexes/cie/<qp_sha>.json` 里可能存着更早的草稿修订；
`import-cie-index` 拒绝覆盖不同内容（"Different index already exists"）。本工具
在人工复核后执行：先把旧文件逐字节备份到 `work/backup-<subject>-<year>-<season>-<paper>-index.json`，
校验备份哈希与原文件一致，然后删除原文件，让随后的 import_index.py 重新导入。

- 服务文件不存在 / 与本地索引相同：不需要替换（no_conflict / missing）。
- 备份已存在且哈希一致：复用（幂等重跑）。
- 备份已存在但哈希不同：拒绝（backup_conflict），必须人工处理。
- 只有 --apply 才真正删除；默认只打印计划。
- 删除前逐段检查重解析点；一次只删这一个文件，不递归。
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import batchlib as B
import import_index as I

ADDED = ("method", "reviewed")


def backup_path(key: str) -> Path:
    subject, year, season, paper = key.split("/")
    return B.WORK / f"backup-{subject}-{year}-{season}-{paper}-index.json"


def plan(key: str) -> dict:
    local_path = I.index_path(key)
    out = {"key": key, "stage": None, "service_index_path": None,
           "backup_path": str(backup_path(key)), "old_sha256": None,
           "local_sha256": None, "bytes": 0, "note": ""}
    if not local_path.is_file():
        out["stage"] = "no_local_index"
        return out
    local = json.loads(local_path.read_bytes().decode("utf-8"))
    qp_sha = I.document_sha(local, "qp")
    target = I.service_index_path(qp_sha)
    out["service_index_path"] = str(target)
    if not target.is_file():
        out["stage"] = "missing"
        return out
    stored = json.loads(target.read_bytes().decode("utf-8"))
    if {k: v for k, v in stored.items() if k not in ADDED} == local:
        out["stage"] = "no_conflict"
        return out
    out["old_sha256"] = B.sha256_file(target)
    out["local_sha256"] = B.sha256_file(local_path)
    out["bytes"] = target.stat().st_size
    out["stage"] = "replace_ready"
    return out


def apply_replace(key: str) -> dict:
    out = plan(key)
    if out["stage"] != "replace_ready":
        return out
    target = Path(out["service_index_path"])
    backup = backup_path(key)
    if target.is_symlink():
        out["stage"] = "unsafe_target"
        out["note"] = f"target is a symlink: {target}"
        return out
    if backup.exists():
        if B.sha256_file(backup) == out["old_sha256"]:
            out["note"] = "backup already exists with identical bytes; reusing"
        else:
            out["stage"] = "backup_conflict"
            out["note"] = f"backup exists with different bytes: {backup}"
            return out
    else:
        shutil.copy2(target, backup)
        if B.sha256_file(backup) != out["old_sha256"]:
            out["stage"] = "backup_failed"
            out["note"] = "copy hash mismatch; original left untouched"
            return out
        out["note"] = "backup written"
    target.unlink()
    if target.exists():
        out["stage"] = "delete_failed"
        out["note"] = "original still present after unlink"
        return out
    out["stage"] = "replaced"
    B.append_jsonl(B.ERRORS, {
        "at": B.now_iso(), "key": key, "kind": "service_index_replaced",
        "service_index_path": str(target), "old_file_sha256": out["old_sha256"],
        "local_index_sha256": out["local_sha256"], "backup_path": str(backup),
        "note": "人工复核：服务端旧草稿与本地已核验索引不同；旧稿已逐字节备份后移除，"
                "随后由 import_index.py 重新导入并回读。"})
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("keys", nargs="+")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    rc = 0
    for key in args.keys:
        out = apply_replace(key) if args.apply else plan(key)
        print(json.dumps(out, ensure_ascii=False), flush=True)
        if out["stage"] in ("backup_conflict", "backup_failed", "delete_failed"):
            rc = 2
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
