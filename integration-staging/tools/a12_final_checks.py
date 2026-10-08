#!/usr/bin/env python3
"""A12 closing checks for the Phase A integration (run AFTER the ledger is closed).

Validates:
  1. artifact existence (legacy package incl. registry.json, the five legacy
     test modules, the six A12 tools, worksheet, report, patch, evidence);
  2. the stored compatibility probe is read-only evidence: its facts are
     asserted exactly as recorded and the six-source sha256 chain is recomputed
     against the bytes on disk -- the probe is never re-run;
  3. registry and worksheet facts: 71/71 baseline rows, status/mechanism/
     coverage counts, deferred rows with reasons, and the recorded chains
     (registry sources, worksheet sources, static rescan) agreeing with disk;
  4. the legacy package, the legacy tests and the A12 tools never import the
     original application (`app`, `examdata`), and the product/test code never
     names an original desktop path;
  5. fresh liveness: `--collect-only` reports 856 collected and a targeted run
     of the five legacy test files passes 145 (stdout+stderr kept in
     evidence/A12/legacy_rerun.txt);
  6. ledger: 27 tasks, A12 staged_pass, 7 gates closed, no merged_pass, A12
     fields present; the three rc!=0 commands (two development fixes and the
     bootstrap run of these checks) and the three exit-code-masked pipeline
     runs plus one pre-close finding reconcile with the recorded exit codes;
  7. containment: every A12 changed file is inside a Phase A writable root and
     no __pycache__/.pyc leaked under the staged source or tests;
  8. sha256 manifest of both Phase A roots (excluding this transcript).

Writes (and prints) the transcript to
  docs/integration/execution/evidence/A12/final_checks.txt  (override with --out)
and exits 0 (PASS) or 1 (FAIL). The first run bootstraps the two transcripts
final_checks.txt / legacy_rerun.txt and therefore exits 1 by construction;
after any checks-tool repairs the re-run must pass.

Phase A tool (integration-staging/tools/). Stdlib only; nothing original is
modified or executed; compat_probe.json is read, never rewritten.
"""
from __future__ import annotations

import argparse
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
EXEC = WS / "docs" / "integration" / "execution"
EV = EXEC / "evidence" / "A12"
STAGING = WS / "integration-staging"
SRC = STAGING / "src"
LEGACY = SRC / "examdata_integration" / "legacy"
TOOLS = STAGING / "tools"
ROOTS = [STAGING, EXEC]

EXPECTED_TASK_IDS = ["A%02d" % i for i in range(16)] + ["B%02d" % i for i in range(11)]
ROOT_STRINGS = [STAGING.relative_to(WS).as_posix() + "/", EXEC.relative_to(WS).as_posix() + "/"]

EXPECTED_REGISTRY_ROWS = 71
EXPECTED_COLLECTED = 856
EXPECTED_LEGACY_PASSED = 145
EXPECTED_DEFERRED = 7
EXPECTED_TOTAL_TEST_IDS = 142
EXPECTED_ADAPTER_PARAMS = 21
EXPECTED_STATIC_PARAMS = 71

EXPECTED_STATUS_COUNTS = {"staged_pass": 64, "deferred_active_owner": 7}
EXPECTED_MECHANISMS = {
    "add_v2_adapter_keep_legacy_defaults": 21,
    "keep_legacy_only": 16,
    "bridge_node_cli_keep_legacy_payload": 20,
    "keep_legacy_namespace": 7,
    "deferred_active_owner": 7,
}
EXPECTED_COVERAGE_KINDS = {"fixture_translation": 14, "static_contract": 24,
                           "envelope_contract": 33}
EXPECTED_ALLOWED_STATUSES = [
    "not_started", "fixture_ready", "staged_pass", "merged_pass",
    "deferred_active_owner", "blocked", "not_applicable_with_reason",
]
EXPECTED_DEFERRED_IDS = {
    "GET__api_v1_materials",
    "GET__api_v1_materials_cie_in_paper",
    "GET__api_v1_materials_material_id",
    "GET__api_v1_materials_material_id_content",
    "GET__api_v1_timetable",
    "GET__api_v1_timetable_seasons",
    "GET__api_v1_timetable_windows",
}
#: probe.sources chain: each expectation is (recorded path, sha256)
EXPECTED_CHAIN = {
    "registry": ("integration-staging/src/examdata_integration/legacy/registry.json",
                 "f9e1870b79616bbb06baefeed810ac9272ad7d227cf161085cee34d3bc6f2f78"),
    "worksheet": ("docs/integration/execution/A12_ROUTE_COMPATIBILITY_WORKSHEET.json",
                  "76ce0abc077b389aa17c7e946a101553d3ddb4a02ce74abfc59d766026b8ee34"),
    "a01_worksheet": ("docs/integration/execution/A01_ROUTE_COMPATIBILITY_WORKSHEET.json",
                      "984d60bf5a08adab5a03e109e8dc76602ae54a3ebeadd68309eced187ca773fc"),
    "full_suite_evidence": ("docs/integration/execution/evidence/A12/pytest_run_stdout.txt",
                            "22ed094396db65f85b27af7e7a29c361854868d445e070ded9c9d0b72f038df8"),
    "collect_stdout": ("docs/integration/execution/evidence/A12/collect_only_stdout.txt",
                       "927285e03408330d67fe9e241dc726bcc7d53a5bbbce28e432adf2bffc323d6d"),
    "legacy_run_stdout": ("docs/integration/execution/evidence/A12/legacy_tests_stdout.txt",
                          "6a9e5da3fd64dfdf3d3fc46d965b3d6fdb1dfccda2ec739fca3bf21363f709b7"),
}
EXPECTED_SOURCE_HASHES = {
    "examdata/src/examdata/api/app.py": "753749fac1361481034e0920c0543e3e621c0d638c21558c73852fd3237fef5d",
    "examdata/src/examdata/api/unified.py": "9568b295d15e837e69a879cfc7dabf53f16a42d61a7a9c2859ec386fdacbe4c1",
    "examdata/src/examdata/api/ielts.py": "9d79ee009086f72e0fc2c2a94ad679c359d42d0f1e970b15a75915cce03511d3",
    "examdata/src/examdata/api/toefl.py": "051449da09363e1c2d392c5a57f809b9d3a30cd2feabcdca4dffaacf73d17934",
}
EXPECTED_REGISTRY_SOURCES = {
    "worksheet": ("docs/integration/execution/A01_ROUTE_COMPATIBILITY_WORKSHEET.json",
                  "984d60bf5a08adab5a03e109e8dc76602ae54a3ebeadd68309eced187ca773fc"),
    "shape_extract": ("docs/integration/execution/evidence/A12/legacy_shape_extract.json",
                      "7e0d4d46683d94ab897c79ce56cbdfff71712384889c08e6b97923dd2e7d00f9"),
    "build_tool": ("integration-staging/tools/a12_build_registry.py",
                   "9bdbb0a22c6392b766760820d46b302a877628dcb69cf83e494f2f5fdc8b730d"),
}
EXPECTED_WORKSHEET_SOURCES = {
    "a01_worksheet": ("docs/integration/execution/A01_ROUTE_COMPATIBILITY_WORKSHEET.json",
                      "984d60bf5a08adab5a03e109e8dc76602ae54a3ebeadd68309eced187ca773fc"),
    "registry": ("integration-staging/src/examdata_integration/legacy/registry.json",
                 "f9e1870b79616bbb06baefeed810ac9272ad7d227cf161085cee34d3bc6f2f78"),
    "build_tool": ("integration-staging/tools/a12_build_worksheet.py",
                   "aa90485cc1d25a24adf67a10f07ea83d383e9ef8a211fdc02aac5c0d350ccb8f"),
    "shape_rescan_tool": ("integration-staging/tools/a12_extract_legacy_shapes.py",
                          "062e03942b9c9642ffa00fe2216833a3de769b49afc3667203bdf988e59ef0e6"),
}
EXPECTED_WORKSHEET_COLUMNS = [
    "method", "legacy_path", "source_file", "handler", "native_parameters",
    "legacy_defaults", "legacy_success_shape", "legacy_error_shape",
    "binary_behavior", "side_effects", "provider", "v2_target",
    "compatibility_strategy", "fixture_ids", "test_ids", "status",
    "evidence_path", "deferred_reason", "row_id", "mechanism", "coverage_kind",
    "owner", "notes",
]
EXPECTED_EXTRA_ROW_KEYS = ["row_origin", "handler_doc_line", "line", "a01_proposal"]

LEGACY_FILES = [
    "tests/test_legacy_adapters.py",
    "tests/test_legacy_bridge_contracts.py",
    "tests/test_legacy_decisions.py",
    "tests/test_legacy_parity.py",
    "tests/test_legacy_translate.py",
]

#: product/test code must never reach the original application or the original
#: package root (`examdata`), only the staged `examdata_integration` tree. The
#: desktop-path tripwire is applied to the legacy package and tests only: the
#: A12 tools legitimately record absolute cwd strings in the ledger patch.
FORBIDDEN_IMPORT_PATTERNS = [
    re.compile(r"^\s*import\s+app\b", re.MULTILINE),
    re.compile(r"^\s*from\s+app\b", re.MULTILINE),
    re.compile(r"^\s*import\s+examdata\b(?!_)", re.MULTILINE),
    re.compile(r"^\s*from\s+examdata\b(?!_)", re.MULTILINE),
]
DESKTOP_PATTERN = re.compile(r"Desktop", re.IGNORECASE)

checks: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    checks.append((name, bool(ok), detail))


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_json(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def rel(p: Path) -> str:
    return p.relative_to(WS).as_posix()


def probe_env() -> dict:
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    return env


def run_pytest(args: list[str], timeout: int = 300) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-c", "pytest.ini", *args,
         "--basetemp", "runtime/pytest-temp", "-o", "cache_dir=runtime/pytest-cache"],
        cwd=str(STAGING), env=probe_env(), capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=timeout)


def chain_problems(label: str, record: dict,
                   expected: dict[str, tuple[str, str]]) -> list[str]:
    problems: list[str] = []
    for name, (rel_path, exp_sha) in expected.items():
        rec = record.get(name) or {}
        disk = sha256_file(WS / rel_path) if (WS / rel_path).is_file() else None
        if rec.get("path") != rel_path or rec.get("sha256") != exp_sha or disk != exp_sha:
            problems.append(f"{label}.{name}: recorded={rec.get('sha256')} "
                            f"expected={exp_sha} disk={disk}")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(EV / "final_checks.txt"))
    args = ap.parse_args()
    out_path = Path(args.out)
    out_path = (out_path if out_path.is_absolute() else WS / out_path).resolve()

    lines: list[str] = []

    def emit(s: str = "") -> None:
        lines.append(s)

    emit("=== A12 final checks (legacy 71-route compatibility: "
         "integration-staging/tools/a12_final_checks.py) ===")
    emit(f"generated_at_local: {datetime.now().astimezone().isoformat(timespec='seconds')}")
    emit(f"generated_at_utc:   {datetime.now(timezone.utc).isoformat(timespec='seconds')}")
    emit(f"cwd: {Path.cwd()}")
    emit()

    # ---- 1. artifact existence -------------------------------------------------
    emit("--- 1. artifact existence ---")
    required = [
        "integration-staging/src/examdata_integration/legacy/__init__.py",
        "integration-staging/src/examdata_integration/legacy/translate.py",
        "integration-staging/src/examdata_integration/legacy/parity.py",
        "integration-staging/src/examdata_integration/legacy/bridge.py",
        "integration-staging/src/examdata_integration/legacy/decisions.py",
        "integration-staging/src/examdata_integration/legacy/registry.json",
        *[f"integration-staging/{f}" for f in LEGACY_FILES],
        "integration-staging/tools/a12_extract_legacy_shapes.py",
        "integration-staging/tools/a12_build_registry.py",
        "integration-staging/tools/a12_build_worksheet.py",
        "integration-staging/tools/a12_probe_compat.py",
        "integration-staging/tools/a12_final_checks.py",
        "integration-staging/tools/a12_close_patch.py",
        "integration-staging/runtime/ledger-patches/A12_close.json",
        "docs/integration/execution/A12_REPORT.md",
        "docs/integration/execution/A12_ROUTE_COMPATIBILITY_WORKSHEET.json",
        "docs/integration/execution/execution-ledger.json",
        "docs/integration/execution/evidence/A12/legacy_shape_extract.json",
        "docs/integration/execution/evidence/A12/pytest_run_stdout.txt",
        "docs/integration/execution/evidence/A12/collect_only_stdout.txt",
        "docs/integration/execution/evidence/A12/legacy_tests_stdout.txt",
        "docs/integration/execution/evidence/A12/compat_probe.json",
        "docs/integration/execution/evidence/A12/final_checks.txt",
        "docs/integration/execution/evidence/A12/legacy_rerun.txt",
    ]
    missing_files = [r for r in required if not (WS / r).is_file()]
    emit(f"missing={missing_files}")
    check("artifacts.all_present", not missing_files)

    # ---- 2. stored compatibility probe (read-only; never re-run) ---------------
    emit()
    emit("--- 2. stored compat_probe.json facts + six-source chain (read-only) ---")
    try:
        probe = load_json(EV / "compat_probe.json")
        emit(f"schema={probe.get('schema')} generated={probe.get('generated_at_utc')}")
        check("probe.schema", probe.get("schema") == "examdata.integration.compat_probe/1")
        check("probe.problems_empty", probe.get("problems") == [],
              str(probe.get("problems")))
        check("probe.method_offline", "no original app import" in str(probe.get("method")))

        coll = probe.get("collection") or {}
        emit(f"collection rc={coll.get('exit_code')} count={coll.get('collected_count')}")
        check("probe.collection", coll.get("exit_code") == 0
              and coll.get("collected_count") == EXPECTED_COLLECTED,
              f"rc={coll.get('exit_code')} count={coll.get('collected_count')}")

        lr = probe.get("legacy_run") or {}
        check("probe.legacy_run", lr.get("exit_code") == 0
              and lr.get("passed") == EXPECTED_LEGACY_PASSED and lr.get("failed") == 0,
              f"rc={lr.get('exit_code')} passed={lr.get('passed')} failed={lr.get('failed')}")

        summ = probe.get("summary") or {}
        emit(f"summary rows={summ.get('registry_rows')} ids={summ.get('total_test_ids')} "
             f"collected={summ.get('collected_total')} deferred={summ.get('deferred_rows')}")
        check("probe.summary_counts",
              summ.get("registry_rows") == EXPECTED_REGISTRY_ROWS
              and summ.get("rows_with_all_test_ids_collected") == EXPECTED_REGISTRY_ROWS
              and summ.get("rows_missing_test_ids") == []
              and summ.get("total_test_ids") == EXPECTED_TOTAL_TEST_IDS
              and summ.get("collected_total") == EXPECTED_COLLECTED
              and summ.get("deferred_rows") == EXPECTED_DEFERRED)
        ad = summ.get("adapter_params") or {}
        sc = summ.get("static_contract_params") or {}
        check("probe.param_cross_checks",
              ad.get("registry") == EXPECTED_ADAPTER_PARAMS
              and ad.get("collected") == EXPECTED_ADAPTER_PARAMS
              and ad.get("only_in_registry") == [] and ad.get("only_in_collection") == []
              and sc.get("registry") == EXPECTED_STATIC_PARAMS
              and sc.get("collected") == EXPECTED_STATIC_PARAMS
              and sc.get("only_in_registry") == [] and sc.get("only_in_collection") == [])
        full = summ.get("full_suite") or {}
        check("probe.full_suite_evidence_matches",
              full.get("passed") == EXPECTED_COLLECTED
              and full.get("sha256") == EXPECTED_CHAIN["full_suite_evidence"][1]
              and "passed" in str(full.get("status_line")),
              str(full.get("status_line")))

        prows = probe.get("rows") or []
        statuses: dict[str, int] = {}
        for r in prows:
            statuses[r.get("status")] = statuses.get(r.get("status"), 0) + 1
        emit(f"rows={len(prows)} statuses={json.dumps(statuses, sort_keys=True)}")
        check("probe.rows_all_collected",
              len(prows) == EXPECTED_REGISTRY_ROWS
              and len({r.get("row_id") for r in prows}) == EXPECTED_REGISTRY_ROWS
              and all(r.get("all_collected") is True for r in prows))
        check("probe.row_status_counts", statuses == EXPECTED_STATUS_COUNTS,
              json.dumps(statuses, sort_keys=True))
        missing_evidence = [r.get("row_id") for r in prows
                            if not (WS / str(r.get("evidence_path"))).is_file()]
        check("probe.row_evidence_paths_exist", not missing_evidence,
              str(missing_evidence[:8]))

        problems = chain_problems("probe.source", probe.get("sources") or {}, EXPECTED_CHAIN)
        emit(f"chain_problems={problems}")
        check("probe.chain_six_sources", not problems, str(problems))
    except Exception as e:  # noqa: BLE001
        check("probe.read_and_validate", False, f"exception={e!r}")

    # ---- 3. registry and worksheet facts ---------------------------------------
    emit()
    emit("--- 3. registry + worksheet facts and recorded chains ---")
    try:
        reg = load_json(LEGACY / "registry.json")
        emit(f"registry schema={reg.get('schema')} rows={reg.get('row_count')}")
        check("registry.schema_and_rows",
              reg.get("schema") == "examdata.integration.legacy_registry/1"
              and reg.get("row_count") == EXPECTED_REGISTRY_ROWS
              and len(reg.get("rows") or []) == EXPECTED_REGISTRY_ROWS)
        check("registry.allowed_statuses",
              reg.get("allowed_statuses") == EXPECTED_ALLOWED_STATUSES,
              str(reg.get("allowed_statuses")))
        check("registry.mechanisms", reg.get("mechanisms") == EXPECTED_MECHANISMS,
              json.dumps(reg.get("mechanisms"), sort_keys=True))
        sh = reg.get("source_hashes") or {}
        sh_ok = set(sh) == set(EXPECTED_SOURCE_HASHES)
        for k, v in sh.items():
            val = v if isinstance(v, str) else (v or {}).get("sha256")
            if val != EXPECTED_SOURCE_HASHES.get(k) or sha256_file(WS / k) != val:
                sh_ok = False
        check("registry.source_hashes_match_disk", sh_ok, json.dumps(sh, sort_keys=True))
        problems = chain_problems("registry.source", reg.get("sources") or {},
                                  EXPECTED_REGISTRY_SOURCES)
        check("registry.sources_chain", not problems, str(problems))

        wsj = load_json(EXEC / "A12_ROUTE_COMPATIBILITY_WORKSHEET.json")
        emit(f"worksheet schema={wsj.get('schema')}")
        check("worksheet.schema",
              wsj.get("schema") == "examdata.integration.route_compatibility_worksheet/2")
        check("worksheet.columns", wsj.get("columns") == EXPECTED_WORKSHEET_COLUMNS)
        check("worksheet.extra_row_keys",
              wsj.get("extra_row_keys") == EXPECTED_EXTRA_ROW_KEYS)
        wsum = wsj.get("summary") or {}
        check("worksheet.coverage_counts",
              wsum.get("row_count") == EXPECTED_REGISTRY_ROWS
              and wsum.get("baseline_coverage") == "71/71"
              and wsum.get("post_baseline_count") == 0
              and wsum.get("status_counts") == EXPECTED_STATUS_COUNTS
              and wsum.get("mechanism_counts") == EXPECTED_MECHANISMS
              and wsum.get("coverage_kind_counts") == EXPECTED_COVERAGE_KINDS,
              json.dumps(wsum.get("status_counts"), sort_keys=True))
        check("worksheet.problems_empty", wsj.get("problems") == [],
              str(wsj.get("problems")))
        wrows = wsj.get("rows") or []
        check("worksheet.rows_unique",
              len(wrows) == EXPECTED_REGISTRY_ROWS
              and len({r.get("row_id") for r in wrows}) == EXPECTED_REGISTRY_ROWS)
        deferred = [r for r in wrows if r.get("status") == "deferred_active_owner"]
        check("worksheet.deferred_rows",
              len(deferred) == EXPECTED_DEFERRED
              and {r.get("row_id") for r in deferred} == EXPECTED_DEFERRED_IDS
              and all((r.get("deferred_reason") or "").strip() for r in deferred))
        rescan = wsj.get("rescan") or {}
        recorded = rescan.get("recorded_source_hashes") or {}
        fresh = rescan.get("fresh_source_hashes") or {}
        rescan_ok = (rescan.get("method") == "static_ast_no_import"
                     and rescan.get("changed_files") == []
                     and recorded == fresh == EXPECTED_SOURCE_HASHES
                     and all(sha256_file(WS / k) == v for k, v in recorded.items()))
        check("worksheet.rescan_no_drift", rescan_ok)
        owner = wsj.get("active_owner_files") or []
        check("worksheet.active_owner_files_exist",
              len(owner) == 2
              and all(o.get("exists") is True and (WS / str(o.get("path"))).is_file()
                      for o in owner),
              str(owner))
        problems = chain_problems("worksheet.source", wsj.get("sources") or {},
                                  EXPECTED_WORKSHEET_SOURCES)
        check("worksheet.sources_chain", not problems, str(problems))
    except Exception as e:  # noqa: BLE001
        check("registry_worksheet.read_and_validate", False, f"exception={e!r}")

    # ---- 4. import containment (staged product/test/tool code) -----------------
    emit()
    emit("--- 4. legacy package / tests / tools containment scan ---")
    try:
        scan_product = sorted(LEGACY.glob("*.py")) + sorted(STAGING.glob("tests/test_legacy_*.py"))
        scan_tools = sorted(TOOLS.glob("a12_*.py"))
        offenders: list[str] = []
        for p in scan_product + scan_tools:
            body = p.read_text(encoding="utf-8")
            for pat in FORBIDDEN_IMPORT_PATTERNS:
                if pat.search(body):
                    offenders.append(f"{rel(p)}::{pat.pattern}")
        for p in scan_product:
            if DESKTOP_PATTERN.search(p.read_text(encoding="utf-8")):
                offenders.append(f"{rel(p)}::Desktop")
        emit(f"scanned={len(scan_product) + len(scan_tools)} offenders={offenders}")
        check("import.no_original_app_reference", not offenders, str(offenders))
        check("import.scan_coverage",
              len(scan_product) == 10 and len(scan_tools) == 6,
              f"product={len(scan_product)} tools={len(scan_tools)}")
    except Exception as e:  # noqa: BLE001
        check("import.no_original_app_reference", False, f"exception={e!r}")

    # ---- 5. fresh liveness (offline pytest; transcript kept as evidence) -------
    emit()
    emit("--- 5. fresh liveness: collect-only + targeted legacy run ---")
    try:
        for sub in ("pytest-temp", "pytest-cache", "tmp", "home"):
            (STAGING / "runtime" / sub).mkdir(parents=True, exist_ok=True)
        collect = run_pytest(["tests", "--collect-only", "-q"])
        collect_text = collect.stdout + collect.stderr
        node_lines = [ln for ln in collect_text.splitlines()
                      if ln.strip().startswith("tests/") and "::" in ln]
        m = re.search(r"(\d+)\s+tests?\s+collected", collect_text)
        count = int(m.group(1)) if m else None
        emit(f"collect rc={collect.returncode} summary_count={count} node_ids={len(node_lines)}")
        check("liveness.collect_856",
              collect.returncode == 0 and count == EXPECTED_COLLECTED
              and len(node_lines) == EXPECTED_COLLECTED,
              f"rc={collect.returncode} count={count} nodes={len(node_lines)}")

        legacy = run_pytest(list(LEGACY_FILES) + ["-q"])
        legacy_text = legacy.stdout + legacy.stderr
        tail = legacy_text.strip().splitlines()[-1] if legacy_text.strip() else ""
        emit(f"legacy rc={legacy.returncode} tail={tail}")
        mf = re.search(r"(\d+) failed", legacy_text)
        failed_count = int(mf.group(1)) if mf else 0
        mp = re.search(r"(\d+) passed", legacy_text)
        passed_count = int(mp.group(1)) if mp else None
        check("liveness.legacy_145_passed",
              legacy.returncode == 0 and passed_count == EXPECTED_LEGACY_PASSED
              and failed_count == 0,
              f"rc={legacy.returncode} passed={passed_count} failed={failed_count}")
        (EV / "legacy_rerun.txt").write_text(legacy_text, encoding="utf-8", newline="\n")
    except Exception as e:  # noqa: BLE001
        check("liveness.collect_856", False, f"exception={e!r}")

    # ---- 6. ledger state --------------------------------------------------------
    emit()
    emit("--- 6. ledger state ---")
    led: dict = {}
    a12: dict = {}
    try:
        led = load_json(EXEC / "execution-ledger.json")
        by_id = {t.get("task_id"): t for t in led.get("tasks", [])}
        a12 = by_id.get("A12", {})
        codes = a12.get("exit_codes", [])
        nonzero = [c for c in codes if c not in (0, None)]
        failures = a12.get("failures") or []
        masked = [f for f in failures if f.get("exit_code_masked")]
        preclose = [f for f in failures if f.get("found_by") == "pre_close_verification"]
        rc1 = [f for f in failures if f.get("exit_code") == 1
               and not f.get("exit_code_masked")]
        emit(f"A12 exit_codes={codes} nonzero={nonzero} failures={len(failures)} "
             f"masked={len(masked)} preclose={len(preclose)} rc1={len(rc1)}")
        check("ledger.exit_codes_consistent",
              bool(codes) and set(nonzero) <= {1} and len(nonzero) == len(rc1) == 3,
              f"codes={codes} nonzero={nonzero} rc1={len(rc1)}")
        check("ledger.failure_bookkeeping",
              len(failures) == 7 and len(masked) == 3 and len(preclose) == 1,
              f"failures={len(failures)} masked={len(masked)} preclose={len(preclose)}")

        tasks = led.get("tasks", [])
        ids = [t.get("task_id") for t in tasks]
        gates = led.get("gates", {})
        open_gates = [g for g, v in gates.items() if v.get("open")]
        statuses: dict[str, int] = {}
        for t in tasks:
            statuses[t["status"]] = statuses.get(t["status"], 0) + 1
        emit(f"task_count={len(ids)} unique={len(set(ids))} "
             f"statuses={json.dumps(statuses, sort_keys=True)}")
        emit(f"A12_status={a12.get('status')} gates={len(gates)} open={open_gates}")
        check("ledger.count_unique_27",
              len(ids) == 27 and len(set(ids)) == 27
              and not [t for t in EXPECTED_TASK_IDS if t not in ids]
              and not [t for t in ids if t not in EXPECTED_TASK_IDS])
        check("ledger.a12_staged_pass", a12.get("status") == "staged_pass",
              f"A12={a12.get('status')}")
        check("ledger.no_merged_pass", "merged_pass" not in statuses)
        check("ledger.gates_closed", len(gates) == 7 and not open_gates,
              f"open={open_gates}")
        expected_roots = [STAGING.as_posix(), EXEC.as_posix()]
        check("ledger.a12_write_roots",
              a12.get("allowed_write_roots") == expected_roots
              and led.get("allowed_write_roots") == expected_roots)
        check("ledger.a12_dependencies", a12.get("dependencies") == ["A11"],
              str(a12.get("dependencies")))
        check("ledger.a12_record_fields",
              bool(a12.get("evidence_paths")) and bool(a12.get("input_hashes"))
              and bool(a12.get("commands")) and bool(a12.get("changed_files"))
              and bool(a12.get("test_results")) and bool(a12.get("remaining_gaps"))
              and (a12.get("next_action") or "").strip() != "")
    except Exception as e:  # noqa: BLE001
        check("ledger.load_and_validate", False, f"exception={e!r}")

    # ---- 7. containment of the A12 write set ------------------------------------
    emit()
    emit("--- 7. containment of the A12 write set ---")
    try:
        outside = [f for f in a12.get("changed_files", [])
                   if not any(f.replace("\\", "/").startswith(r) for r in ROOT_STRINGS)]
        emit(f"changed_files_outside_roots={outside}")
        check("containment.changed_files_inside_roots", not outside)

        leaks = []
        for sub in ("src", "tests"):
            for p in (STAGING / sub).rglob("*"):
                if p.is_dir() and p.name == "__pycache__":
                    leaks.append(rel(p))
                elif p.is_file() and p.suffix in (".pyc", ".pyo"):
                    leaks.append(rel(p))
        emit(f"pycache_leaks={leaks}")
        check("containment.no_bytecode_under_src_tests", not leaks)
    except Exception as e:  # noqa: BLE001
        check("containment.changed_files_inside_roots", False, f"exception={e!r}")

    # ---- 8. sha256 manifest ------------------------------------------------------
    emit()
    emit("--- 8. artifact inventory + sha256 manifest (excluding this transcript) ---")
    all_files: list[Path] = []
    for root in ROOTS:
        for p in sorted(root.rglob("*")):
            if p.is_file() and p.resolve() != out_path:
                all_files.append(p)
    for p in all_files:
        emit(rel(p))
    emit()
    emit("--- manifest ---")
    for p in all_files:
        emit(f"{sha256_file(p)} *{rel(p)}")

    # ---- verdict -----------------------------------------------------------------
    emit()
    emit("--- 9. verdict ---")
    failed = [(n, d) for n, ok, d in checks if not ok]
    for n, ok, d in checks:
        emit(f"{n}: {'PASS' if ok else 'FAIL'}{(' (' + d + ')') if d and not ok else ''}")
    ok_all = not failed
    emit(f"A12_FINAL_CHECKS_JSON: {'PASS' if ok_all else 'FAIL'}")
    emit(f"FINAL_CHECKS: {'PASS' if ok_all else 'FAIL'}")

    text = "\n".join(lines) + "\n"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text, encoding="utf-8", newline="\n")
    sys.stdout.write(text)
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
