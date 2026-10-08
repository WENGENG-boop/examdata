#!/usr/bin/env python
"""Phase-0 provenance gate and candidate copy for run integration-closure-20261007-c8b4e0c8.

Verifies frozen parent hashes BEFORE copying, copies the frozen candidate into this run's
`candidates/closure-v1`, records one provenance row per file, and computes both the historical
(sorted-WindowsPath) and the new portable posix-v1 tree digests.

Writes only below this run root. Never modifies the parent or any frozen tree.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import shutil
import sys
import datetime

RUN = pathlib.Path(__file__).resolve().parents[1]
WS = RUN.parents[2]
PARENT_RUN = WS / "integration-staging/runtime/b07-reviewfix-20261007-774e4dad"
PARENT = PARENT_RUN / "candidates/b07-operations-v2"
B07V1 = WS / "integration-staging/runtime/b07-rehearsal-2026-10-07/candidates/b07-operations-v1"
B06 = WS / "integration-staging/runtime/b06-rehearsal-2026-10-07/candidates/b06-frontend-v1"
LEDGER = WS / "docs/integration/execution/execution-ledger.json"
MANIFEST = PARENT / "B07R2_CANDIDATE_MANIFEST.json"

EXPECT = {
    "parent_digest": "8171cf1c67c7891fc4c3354a482fb65600886aa0b5b88f9a1a546333c738fa48",
    "parent_files": 222,
    "parent_manifest_sha256": "920f41c1b98199b087a4a8c7dea918c23d0f8144afdfebb87bfb2b2e9bcec9ce",
    "ledger_sha256": "6d4449d3997b437fd3ea3a1fe7925fc78a7c0adbe0a5d3b793d6a8063101b4ba",
    "b07v1_digest": "5df259843b26792910de697b2c646fc413c5b936edf3d95d04baf7afa482c179",
    "b07v1_files": 221,
    "b06_digest": "ffe774db608ff9d86246458a38265f9baa760b40880e48197e84d887f85d53f4",
    "b06_files": 208,
}

SKIP_DIRS = {"__pycache__", ".pytest_cache"}


def sha256_file(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def tree_entries(base: pathlib.Path, exclude: tuple[str, ...] = ()) -> list[tuple[str, str]]:
    """Files under base as (posix rel path, sha256), in WindowsPath (historical) order."""
    rows: list[tuple[str, str]] = []
    for p in sorted(base.rglob("*")):
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        if p.is_file():
            rel = p.relative_to(base).as_posix()
            if rel in exclude:
                continue
            rows.append((rel, sha256_file(p)))
    return rows


def digest(rows: list[tuple[str, str]], order: str) -> dict:
    if order == "posix-v1":
        rows = sorted(rows, key=lambda r: r[0])
    h = hashlib.sha256()
    for rel, fh in rows:
        h.update(f"{rel}\0{fh}\n".encode("utf-8"))
    return {"files": len(rows), "sha256": h.hexdigest(), "order": order}


def now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def main() -> int:
    ev = RUN / "evidence"
    ev.mkdir(parents=True, exist_ok=True)
    problems: list[str] = []
    checks: dict[str, object] = {}

    parent_rows = tree_entries(PARENT, exclude=("B07R2_CANDIDATE_MANIFEST.json",))
    checks["parent_historical"] = digest(parent_rows, "historical")
    checks["parent_posix_v1"] = digest(parent_rows, "posix-v1")
    checks["parent_manifest_sha256"] = sha256_file(MANIFEST)
    checks["ledger_sha256"] = sha256_file(LEDGER)

    b07_rows = tree_entries(B07V1, exclude=("B07_CANDIDATE_MANIFEST.json",))
    checks["b07v1_historical"] = digest(b07_rows, "historical")
    b06_rows = tree_entries(B06, exclude=("B06_CANDIDATE_MANIFEST.json",))
    checks["b06_historical"] = digest(b06_rows, "historical")

    if checks["parent_historical"]["sha256"] != EXPECT["parent_digest"] or \
            checks["parent_historical"]["files"] != EXPECT["parent_files"]:
        problems.append("parent digest mismatch")
    if checks["parent_manifest_sha256"] != EXPECT["parent_manifest_sha256"]:
        problems.append("parent manifest sha256 mismatch")
    if checks["ledger_sha256"] != EXPECT["ledger_sha256"]:
        problems.append("ledger sha256 mismatch")
    if checks["b07v1_historical"]["sha256"] != EXPECT["b07v1_digest"]:
        problems.append("b07 v1 digest mismatch")
    if checks["b06_historical"]["sha256"] != EXPECT["b06_digest"]:
        problems.append("b06 digest mismatch")

    gate = {
        "schema": "closure.provenance_gate/1",
        "run_root": str(RUN),
        "checked_at": now(),
        "expected": EXPECT,
        "observed": checks,
        "problems": problems,
        "verdict": "proceed" if not problems else "stop",
    }
    (ev / "provenance_before_copy.json").write_text(
        json.dumps(gate, indent=2, ensure_ascii=False), encoding="utf8")
    print(json.dumps({"verdict": gate["verdict"], "problems": problems,
                      "parent": checks["parent_historical"],
                      "parent_posix_v1": checks["parent_posix_v1"]}, indent=2))
    if problems:
        return 2

    # Copy parent -> candidates/closure-v1 with per-file provenance.
    dst = RUN / "candidates/closure-v1"
    if dst.exists():
        problems.append("destination already exists")
        return 2
    provenance: list[dict[str, str]] = []
    for rel, fh in parent_rows:
        src_file = PARENT / rel
        dst_file = dst / rel
        dst_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src_file, dst_file)
        provenance.append({"rel": rel, "src_sha256": fh, "dst_sha256": sha256_file(dst_file)})
    # carry the parent manifest verbatim as provenance input
    shutil.copyfile(MANIFEST, dst / "B07R2_CANDIDATE_MANIFEST.json")
    provenance.append({"rel": "B07R2_CANDIDATE_MANIFEST.json",
                       "src_sha256": EXPECT["parent_manifest_sha256"],
                       "dst_sha256": sha256_file(dst / "B07R2_CANDIDATE_MANIFEST.json"),
                       "role": "carried_manifest"})

    mismatches = [r["rel"] for r in provenance if r["src_sha256"] != r["dst_sha256"]]
    copy_doc = {
        "schema": "closure.copy_provenance/1",
        "copied_at": now(),
        "source_root": str(PARENT),
        "destination_root": str(dst),
        "rows": provenance,
        "file_count": len(provenance),
        "hash_mismatches": mismatches,
    }
    (ev / "copy_provenance.json").write_text(
        json.dumps(copy_doc, indent=2, ensure_ascii=False), encoding="utf8")

    # Recompute both digests on the new copy (excluding the carried manifest for parity).
    new_rows = tree_entries(dst, exclude=("B07R2_CANDIDATE_MANIFEST.json",))
    new_hist = digest(new_rows, "historical")
    new_posix = digest(new_rows, "posix-v1")
    digest_doc = {
        "schema": "closure.tree_digest/1",
        "candidate": str(dst),
        "excludes": ["B07R2_CANDIDATE_MANIFEST.json"],
        "historical": new_hist,
        "posix_v1": new_posix,
        "matches_parent": new_hist["sha256"] == EXPECT["parent_digest"],
        "on_disk_files": sum(1 for p in dst.rglob("*") if p.is_file()),
    }
    (ev / "candidate_v1_digest.json").write_text(
        json.dumps(digest_doc, indent=2, ensure_ascii=False), encoding="utf8")
    print(json.dumps(digest_doc, indent=2))
    return 0 if not mismatches else 3


if __name__ == "__main__":
    raise SystemExit(main())
