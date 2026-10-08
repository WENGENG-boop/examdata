#!/usr/bin/env python3
"""A12 legacy compatibility probe: test-id existence + targeted legacy run.

Runs two offline pytest passes inside `integration-staging` with the shared
venv python (never installing anything, never touching the original app):

1. ``--collect-only -q`` over the staged suite - every test id recorded in
   ``legacy/registry.json`` must exist as a collected node.
2. a targeted run of the five staged legacy test files - must pass, tying the
   registry rows to a fresh, dated green run (the full-suite evidence file
   ``evidence/A12/pytest_run_stdout.txt`` is referenced and hashed too).

Writes ``docs/integration/execution/evidence/A12/compat_probe.json`` plus the
raw stdout of both runs next to it. No network, no database, no service, no
original-application import; bytecode and pytest state stay inside staging.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.dont_write_bytecode = True

WS = Path(__file__).resolve().parents[2]
STAGING = WS / "integration-staging"
EXECUTION = WS / "docs" / "integration" / "execution"
EVIDENCE = EXECUTION / "evidence" / "A12"
REGISTRY_PATH = STAGING / "src" / "examdata_integration" / "legacy" / "registry.json"
WORKSHEET_PATH = EXECUTION / "A12_ROUTE_COMPATIBILITY_WORKSHEET.json"
A01_PATH = EXECUTION / "A01_ROUTE_COMPATIBILITY_WORKSHEET.json"
FULL_SUITE_EVIDENCE = EVIDENCE / "pytest_run_stdout.txt"
COLLECT_STDOUT = EVIDENCE / "collect_only_stdout.txt"
LEGACY_STDOUT = EVIDENCE / "legacy_tests_stdout.txt"
OUT_PATH = EVIDENCE / "compat_probe.json"

LEGACY_FILES = [
    "tests/test_legacy_adapters.py",
    "tests/test_legacy_bridge_contracts.py",
    "tests/test_legacy_decisions.py",
    "tests/test_legacy_parity.py",
    "tests/test_legacy_translate.py",
]

ADAPTER_PREFIX = "tests/test_legacy_adapters.py::test_adapter_fixture_translation["
STATIC_PREFIX = "tests/test_legacy_bridge_contracts.py::test_static_contract["
SELF_EVIDENCE = "docs/integration/execution/evidence/A12/compat_probe.json"

problems: list[str] = []


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def run_pytest(args: list[str], timeout: int = 300) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-c", "pytest.ini", *args,
         "--basetemp", "runtime/pytest-temp", "-o", "cache_dir=runtime/pytest-cache"],
        cwd=str(STAGING), capture_output=True, text=True, encoding="utf-8",
        errors="replace", env=env, timeout=timeout)


def collected_node_ids(stdout: str) -> set[str]:
    ids: set[str] = set()
    for line in stdout.splitlines():
        line = line.strip()
        if line.startswith("tests/") and "::" in line:
            ids.add(line)
    return ids


def parsed_count(stdout: str, word: str) -> int | None:
    match = re.search(rf"(\d+) {word}", stdout)
    return int(match.group(1)) if match else None


def main() -> int:
    for sub in ("pytest-temp", "pytest-cache", "home"):
        (STAGING / "runtime" / sub).mkdir(parents=True, exist_ok=True)

    registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    rows = registry["rows"]

    # ---------------------------------------------------------- collection --
    collect = run_pytest(["tests", "--collect-only", "-q"])
    collect_text = collect.stdout + collect.stderr
    COLLECT_STDOUT.write_text(collect_text, encoding="utf-8", newline="\n")
    if collect.returncode != 0:
        problems.append(f"collect-only exited {collect.returncode}")
    collected = collected_node_ids(collect_text)
    collected_count = parsed_count(collect_text, "tests collected")
    if collected_count is None:
        problems.append("no 'N tests collected' line in collect output")
    elif collected_count != len(collected):
        problems.append(f"collected line count {len(collected)} != summary "
                        f"{collected_count}")
    print(f"[ok] collected {len(collected)} node ids "
          f"(summary says {collected_count}, rc={collect.returncode})")

    # ----------------------------------------------------------- legacy run --
    legacy = run_pytest(LEGACY_FILES + ["-q"])
    legacy_text = legacy.stdout + legacy.stderr
    LEGACY_STDOUT.write_text(legacy_text, encoding="utf-8", newline="\n")
    if legacy.returncode != 0:
        problems.append(f"legacy run exited {legacy.returncode}")
    legacy_passed = parsed_count(legacy_text, "passed")
    legacy_failed = parsed_count(legacy_text, "failed") or 0
    if legacy_failed:
        problems.append(f"legacy run reports {legacy_failed} failed")
    print(f"[ok] legacy run rc={legacy.returncode} passed={legacy_passed} "
          f"failed={legacy_failed}")

    # ------------------------------------------------------- per-row checks --
    row_records: list[dict] = []
    total_ids = 0
    for row in rows:
        ids = row["test_ids"]
        total_ids += len(ids)
        if not ids:
            problems.append(f"row {row['row_id']} has no test ids")
        per_id = {tid: (tid in collected) for tid in ids}
        missing = [tid for tid, ok in per_id.items() if not ok]
        if missing:
            problems.append(f"row {row['row_id']} missing ids: {missing}")
        evidence = row["evidence_path"]
        if evidence == SELF_EVIDENCE:
            kind = "self (this probe)"
        elif (WS / evidence).exists():
            kind = "exists"
        else:
            kind = "missing"
            problems.append(f"row {row['row_id']} evidence missing: {evidence}")
        row_records.append({
            "row_id": row["row_id"],
            "status": row["status"],
            "mechanism": row["mechanism"],
            "owner": row["owner"],
            "test_ids": per_id,
            "all_collected": not missing,
            "evidence_path": evidence,
            "evidence_kind": kind,
        })

    # ------------------------------------------- parameterised cross-checks --
    collected_adapter = {i for i in collected if i.startswith(ADAPTER_PREFIX)}
    registry_adapter = {
        i for row in rows for i in row["test_ids"] if i.startswith(ADAPTER_PREFIX)
    }
    collected_static = {i for i in collected if i.startswith(STATIC_PREFIX)}
    registry_static = {
        i for row in rows for i in row["test_ids"] if i.startswith(STATIC_PREFIX)
    }
    adapter_only_registry = sorted(registry_adapter - collected_adapter)
    adapter_only_collected = sorted(collected_adapter - registry_adapter)
    static_only_registry = sorted(registry_static - collected_static)
    static_only_collected = sorted(collected_static - registry_static)
    for label, only_reg, only_col in (
        ("adapter", adapter_only_registry, adapter_only_collected),
        ("static_contract", static_only_registry, static_only_collected),
    ):
        if only_reg:
            problems.append(f"{label} ids in registry but not collected: {only_reg}")
        if only_col:
            problems.append(f"{label} ids collected but not in registry: {only_col}")
    print(f"[ok] adapter params registry={len(registry_adapter)} "
          f"collected={len(collected_adapter)}")
    print(f"[ok] static_contract params registry={len(registry_static)} "
          f"collected={len(collected_static)}")

    # ------------------------------------------------- full-suite evidence ---
    full_text = FULL_SUITE_EVIDENCE.read_text(encoding="utf-8")
    full_status = ""
    for line in full_text.splitlines():
        if " passed" in line and "=" in line:
            full_status = line.strip()
    full_passed = parsed_count(full_status, "passed") if full_status else None
    if full_passed is None:
        problems.append(f"full-suite evidence line unexpected: {full_status!r}")
    elif full_passed != len(collected):
        problems.append(f"full-suite evidence is stale: {full_passed} passed vs "
                        f"{len(collected)} collected")

    rows_ok = sum(1 for r in row_records if r["all_collected"])
    summary = {
        "registry_rows": len(rows),
        "rows_with_all_test_ids_collected": rows_ok,
        "rows_missing_test_ids": [r["row_id"] for r in row_records
                                  if not r["all_collected"]],
        "total_test_ids": total_ids,
        "collected_total": len(collected),
        "adapter_params": {"registry": len(registry_adapter),
                           "collected": len(collected_adapter),
                           "only_in_registry": adapter_only_registry,
                           "only_in_collection": adapter_only_collected},
        "static_contract_params": {"registry": len(registry_static),
                                   "collected": len(collected_static),
                                   "only_in_registry": static_only_registry,
                                   "only_in_collection": static_only_collected},
        "deferred_rows": sum(1 for r in rows
                             if r["status"] == "deferred_active_owner"),
        "legacy_run": {"exit_code": legacy.returncode,
                       "passed": legacy_passed, "failed": legacy_failed,
                       "files": LEGACY_FILES},
        "full_suite": {"status_line": full_status,
                       "passed": full_passed,
                       "sha256": sha256_file(FULL_SUITE_EVIDENCE)},
        "problems": problems,
    }

    document = {
        "schema": "examdata.integration.compat_probe/1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "generated_at_local": datetime.now().astimezone().isoformat(),
        "plan_ref": ("docs/integration/MASTER_EXECUTION_PLAN_EN.md packet A12 "
                     "(plan 5.5): compatibility probe"),
        "method": ("offline pytest collection + targeted legacy run inside "
                   "integration-staging; no original app import"),
        "sources": {
            "registry": {
                "path": "integration-staging/src/examdata_integration/legacy/registry.json",
                "sha256": sha256_file(REGISTRY_PATH),
            },
            "worksheet": {
                "path": "docs/integration/execution/A12_ROUTE_COMPATIBILITY_WORKSHEET.json",
                "sha256": sha256_file(WORKSHEET_PATH),
            },
            "a01_worksheet": {
                "path": "docs/integration/execution/A01_ROUTE_COMPATIBILITY_WORKSHEET.json",
                "sha256": sha256_file(A01_PATH),
            },
            "full_suite_evidence": {
                "path": "docs/integration/execution/evidence/A12/pytest_run_stdout.txt",
                "sha256": sha256_file(FULL_SUITE_EVIDENCE),
            },
            "collect_stdout": {
                "path": "docs/integration/execution/evidence/A12/collect_only_stdout.txt",
                "sha256": sha256_bytes(collect_text.encode("utf-8")),
            },
            "legacy_run_stdout": {
                "path": "docs/integration/execution/evidence/A12/legacy_tests_stdout.txt",
                "sha256": sha256_bytes(legacy_text.encode("utf-8")),
            },
        },
        "collection": {
            "command": [sys.executable, "-m", "pytest", "-c", "pytest.ini",
                        "tests", "--collect-only", "-q"],
            "cwd": str(STAGING),
            "exit_code": collect.returncode,
            "collected_count": len(collected),
        },
        "legacy_run": summary["legacy_run"],
        "rows": row_records,
        "summary": summary,
        "problems": problems,
    }

    OUT_PATH.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8", newline="\n")
    print(f"[ok] wrote {OUT_PATH.relative_to(WS)}")

    print(f"\nA12_PROBE: {'PASS' if not problems else 'FAIL'} "
          f"({len(problems)} problems)")
    for problem in problems:
        print(f"  problem: {problem}")
    return 0 if not problems else 1


if __name__ == "__main__":
    raise SystemExit(main())
