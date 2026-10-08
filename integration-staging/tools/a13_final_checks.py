#!/usr/bin/env python3
"""A13 closing checks for the Phase A integration (run AFTER the ledger is closed).

Validates:
  1. artifact existence (operations package + synthetic fixtures, the staged
     frontend copy incl. provenance manifests, the three A13 test modules, the
     four A13 tools, runtime transcripts, close patch, report, evidence);
  2. fresh provenance re-verification: both provenance tools are re-run with
     --check (private fixtures, no network) and must reproduce the recorded
     PASS lines;
  3. manifest facts: the 6-entry operations fixture manifest and the frontend
     provenance manifest (6 copied = 4 modified + 2 byte-identical snapshots,
     4 new staged-only files, 3 private fixtures) reconcile byte-for-byte with
     disk, including each recorded source sha256;
  4. the operations package, the three A13 tests and the four A13 tools never
     import the original application (`app`, `examdata`), and neither product
     code nor the staged frontend ever names an original desktop path;
  5. fresh liveness: `--collect-only` reports 887 collected and a targeted run
     of the three A13 test modules passes 31 (stdout+stderr kept in
     evidence/A13/python_rerun.txt);
  6. fresh node liveness: the staged frontend test suite runs offline under
     node --test and passes 27/27 (kept in evidence/A13/frontend_rerun.txt);
  7. ledger state: 27 tasks, A13 staged_pass with dependencies ["A12"], all
     seven Phase B gates closed, no merged_pass anywhere; the single rc=1
     command row (GBK heredoc), the second rc=1 development run of this
     tool (concurrent native-input drift) and the three exit-code-masked
     pipeline runs reconcile with the recorded exit codes;
  8. close patch consistency: changed files inside the Phase A roots, the
     three POST_CLOSE transcripts never listed as changed files, the report
     and every A13 deliverable present, input hashes recomputed against disk
     (excluding the self-referential ledger and the three actively-owned
     native checkpoints, whose drift is observed and logged, never asserted),
     and exit_codes identical to the ledger record;
  9. containment: no __pycache__/.pyc leaked under staged src/tests/frontend;
 10. sha256 manifest of both Phase A roots (excluding this transcript).

Writes (and prints) the transcript to
  docs/integration/execution/evidence/A13/final_checks.txt  (override with --out)
and exits 0 (PASS) or 1 (FAIL). The first run is expected to pass; it creates
the three POST_CLOSE transcripts (final_checks.txt, python_rerun.txt,
frontend_rerun.txt) that are excluded from the close patch by construction.

Phase A tool (integration-staging/tools/). Stdlib only; nothing original is
modified or executed; the native checkpoints and the original frontend are
read-only inputs, never written.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.dont_write_bytecode = True

WS = Path(__file__).resolve().parents[2]
EXEC = WS / "docs" / "integration" / "execution"
EV = EXEC / "evidence" / "A13"
STAGING = WS / "integration-staging"
SRC = STAGING / "src"
OPS_PKG = SRC / "examdata_integration" / "operations"
OPS_FIXTURES = STAGING / "fixtures" / "synthetic" / "operations"
FE = STAGING / "frontend"
TOOLS = STAGING / "tools"
ROOTS = [STAGING, EXEC]

EXPECTED_TASK_IDS = ["A%02d" % i for i in range(16)] + ["B%02d" % i for i in range(11)]
ROOT_STRINGS = [STAGING.relative_to(WS).as_posix() + "/", EXEC.relative_to(WS).as_posix() + "/"]

EXPECTED_COLLECTED = 887
EXPECTED_TARGETED_PASSED = 31
EXPECTED_NODE_TESTS = 27
EXPECTED_NODE_PASS = 27
EXPECTED_NODE_FAIL = 0

EXPECTED_OPS_ENTRIES = 6
EXPECTED_FRONTEND_KINDS = {"modified_copy": 4, "copied_snapshot": 2, "new_file": 4}
EXPECTED_FIXTURE_PATHS = {"catalog.json", "syllabi.json", "resources.json"}
LEDGER_REL = "docs/integration/execution/execution-ledger.json"
#: read-only to the executor but actively owned by Kimi (native materials);
#: their recorded hash is a build-time snapshot and drift is logged, not asserted
ACTIVE_OWNER_INPUTS = {
    "cie-location-batch/checkpoint.json",
    "ielts-data/test-s03/runs/run-ok/checkpoint.json",
    "ielts-data/runs/pte-20261004/checkpoint.json",
}

OPS_PROVENANCE_LINE = "A13_PROVENANCE: PASS (6 entries)"
FRONTEND_PROVENANCE_LINE = "A13_FRONTEND_PROVENANCE: PASS (6 copied, 4 new, 3 fixtures)"

A13_TESTS = [
    "tests/test_operations_checkpoints.py",
    "tests/test_operations_coverage.py",
    "tests/test_frontend_staged_copy.py",
]
A13_TOOLS = [
    "tools/a13_capture_fixtures.py",
    "tools/a13_frontend_provenance.py",
    "tools/a13_final_checks.py",
    "tools/a13_close_patch.py",
]

#: product/test code must never reach the original application or the original
#: package root (`examdata`), only the staged `examdata_integration` tree. The
#: desktop-path tripwire is applied to product code and the staged frontend:
#: the A13 tools legitimately record absolute cwd strings in the ledger patch.
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


def node_exe() -> str | None:
    candidate = Path("C:/Program Files/nodejs/node.exe")
    if candidate.is_file():
        return str(candidate)
    return shutil.which("node")


def node_count(text: str, label: str) -> int | None:
    m = (re.search(r"(?:\u2139|#)\s*" + label + r"\s+(\d+)", text)
         or re.search(r"^" + label + r"\s+(\d+)", text, re.MULTILINE))
    return int(m.group(1)) if m else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(EV / "final_checks.txt"))
    args = ap.parse_args()
    out_path = Path(args.out)
    out_path = (out_path if out_path.is_absolute() else WS / out_path).resolve()

    lines: list[str] = []

    def emit(s: str = "") -> None:
        lines.append(s)

    emit("=== A13 final checks (frontend proposal copy + operations checkpoint "
         "readers: integration-staging/tools/a13_final_checks.py) ===")
    emit(f"generated_at_local: {datetime.now().astimezone().isoformat(timespec='seconds')}")
    emit(f"generated_at_utc:   {datetime.now(timezone.utc).isoformat(timespec='seconds')}")
    emit(f"cwd: {Path.cwd()}")
    emit()

    # ---- 1. artifact existence -------------------------------------------------
    emit("--- 1. artifact existence ---")
    required = [
        "integration-staging/src/examdata_integration/operations/__init__.py",
        "integration-staging/src/examdata_integration/operations/checkpoints.py",
        "integration-staging/src/examdata_integration/operations/coverage.py",
        "integration-staging/fixtures/synthetic/operations/PROVENANCE.json",
        "integration-staging/fixtures/synthetic/operations/README.md",
        "integration-staging/fixtures/synthetic/operations/cie-batch-checkpoint-running.json",
        "integration-staging/fixtures/synthetic/operations/cie-batch-checkpoint-stopped.json",
        "integration-staging/fixtures/synthetic/operations/ielts-run-checkpoint-ok-stale.json",
        "integration-staging/fixtures/synthetic/operations/ielts-run-checkpoint-ok.json",
        "integration-staging/fixtures/synthetic/operations/ielts-run-checkpoint-partial.json",
        "integration-staging/fixtures/synthetic/operations/unsupported-checkpoint.json",
        "integration-staging/frontend/index.html",
        "integration-staging/frontend/app.js",
        "integration-staging/frontend/styles.css",
        "integration-staging/frontend/search.mjs",
        "integration-staging/frontend/README.md",
        "integration-staging/frontend/client.mjs",
        "integration-staging/frontend/fixture-server.mjs",
        "integration-staging/frontend/PROVENANCE.json",
        "integration-staging/frontend/fixtures/PROVENANCE.json",
        "integration-staging/frontend/fixtures/catalog.json",
        "integration-staging/frontend/fixtures/syllabi.json",
        "integration-staging/frontend/fixtures/resources.json",
        "integration-staging/frontend/tests/search.test.mjs",
        "integration-staging/frontend/tests/client.test.mjs",
        "integration-staging/frontend/tests/flow.test.mjs",
        *[f"integration-staging/{t}" for t in A13_TESTS],
        *[f"integration-staging/{t}" for t in A13_TOOLS],
        "integration-staging/runtime/a13_pytest.txt",
        "integration-staging/runtime/a13_node_tests.txt",
        "integration-staging/runtime/ledger-patches/A13_close.json",
        "docs/integration/execution/A13_REPORT.md",
        "docs/integration/execution/execution-ledger.json",
        "docs/integration/execution/evidence/A13/node_tests_stdout.txt",
        "docs/integration/execution/evidence/A13/pytest_run_stdout.txt",
        "docs/integration/execution/evidence/A13/operations_provenance_stdout.txt",
        "docs/integration/execution/evidence/A13/frontend_provenance_stdout.txt",
    ]
    missing_files = [r for r in required if not (WS / r).is_file()]
    emit(f"required={len(required)} missing={missing_files}")
    check("artifacts.all_present", not missing_files, str(missing_files))

    # ---- 2. fresh provenance re-verification (--check; no writes) ----------------
    emit()
    emit("--- 2. fresh provenance re-verification (both tools with --check) ---")
    try:
        cap = subprocess.run(
            [sys.executable, str(TOOLS / "a13_capture_fixtures.py"), "--check"],
            cwd=str(WS), env=probe_env(), capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=120)
        cap_text = (cap.stdout + cap.stderr).strip()
        cap_first = cap_text.splitlines()[0] if cap_text else ""
        emit(f"operations rc={cap.returncode} line={cap_first}")
        check("provenance.operations_recheck",
              cap.returncode == 0 and OPS_PROVENANCE_LINE in cap_text,
              f"rc={cap.returncode} out={cap_text[:200]}")

        fe = subprocess.run(
            [sys.executable, str(TOOLS / "a13_frontend_provenance.py"), "--check"],
            cwd=str(WS), env=probe_env(), capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=120)
        fe_text = (fe.stdout + fe.stderr).strip()
        fe_first = fe_text.splitlines()[0] if fe_text else ""
        emit(f"frontend rc={fe.returncode} line={fe_first}")
        check("provenance.frontend_recheck",
              fe.returncode == 0 and FRONTEND_PROVENANCE_LINE in fe_text,
              f"rc={fe.returncode} out={fe_text[:200]}")
    except Exception as e:  # noqa: BLE001
        check("provenance.operations_recheck", False, f"exception={e!r}")

    # ---- 3. manifest facts (ops fixtures + frontend provenance) -----------------
    emit()
    emit("--- 3. manifest facts: operations fixtures + frontend provenance ---")
    try:
        ops = load_json(OPS_FIXTURES / "PROVENANCE.json")
        entries = ops.get("entries") or []
        emit(f"operations schema={ops.get('schema')} entries={len(entries)} "
             f"summary={json.dumps(ops.get('summary'), sort_keys=True)}")
        check("ops_manifest.schema_and_scope",
              ops.get("schema") == "fixture-provenance/1"
              and "A13" in str(ops.get("scope"))
              and (ops.get("summary") or {}).get("entries") == EXPECTED_OPS_ENTRIES,
              f"schema={ops.get('schema')} summary={ops.get('summary')}")
        bad_ops: list[str] = []
        for e in entries:
            p = WS / str(e.get("path"))
            if not p.is_file():
                bad_ops.append(f"{e.get('path')}:missing")
                continue
            if sha256_file(p) != e.get("sha256"):
                bad_ops.append(f"{e.get('path')}:sha256")
            if p.stat().st_size != e.get("bytes"):
                bad_ops.append(f"{e.get('path')}:bytes")
            if e.get("label") != "synthetic_fixture" or e.get("kind") != "synthetic":
                bad_ops.append(f"{e.get('path')}:label")
        emit(f"operations manifest problems={bad_ops}")
        check("ops_manifest.entries_reconcile",
              len(entries) == EXPECTED_OPS_ENTRIES and not bad_ops, str(bad_ops))
        check("ops_manifest.all_synthetic",
              all(e.get("label") == "synthetic_fixture" for e in entries)
              and (ops.get("summary") or {}).get("synthetic") == EXPECTED_OPS_ENTRIES)

        fep = load_json(FE / "PROVENANCE.json")
        ffiles = fep.get("files") or []
        kinds: dict[str, int] = {}
        for f in ffiles:
            kinds[f.get("kind")] = kinds.get(f.get("kind"), 0) + 1
        emit(f"frontend provenance_version={fep.get('provenance_version')} "
             f"files={len(ffiles)} kinds={json.dumps(kinds, sort_keys=True)}")
        check("frontend_manifest.header",
              fep.get("provenance_version") == "frontend-provenance/1"
              and fep.get("generated_by") == "tools/a13_frontend_provenance.py"
              and fep.get("source_root") == "frontend"
              and fep.get("staged_root") == "integration-staging/frontend")
        check("frontend_manifest.kind_counts", kinds == EXPECTED_FRONTEND_KINDS,
              json.dumps(kinds, sort_keys=True))
        bad_fe: list[str] = []
        for f in ffiles:
            staged = FE / str(f.get("path"))
            if not staged.is_file():
                bad_fe.append(f"{f.get('path')}:staged_missing")
                continue
            if sha256_file(staged) != f.get("staged_sha256"):
                bad_fe.append(f"{f.get('path')}:staged_sha256")
            kind = f.get("kind")
            if kind in ("modified_copy", "copied_snapshot"):
                src = WS / str(f.get("source_path"))
                if not src.is_file():
                    bad_fe.append(f"{f.get('path')}:source_missing")
                elif sha256_file(src) != f.get("source_sha256"):
                    bad_fe.append(f"{f.get('path')}:source_drift")
                if kind == "copied_snapshot" and f.get("source_sha256") != f.get("staged_sha256"):
                    bad_fe.append(f"{f.get('path')}:snapshot_not_identical")
                if kind == "modified_copy":
                    if f.get("source_sha256") == f.get("staged_sha256"):
                        bad_fe.append(f"{f.get('path')}:modified_but_identical")
                    if not f.get("changes"):
                        bad_fe.append(f"{f.get('path')}:changes_empty")
                if kind == "copied_snapshot" and f.get("changes"):
                    bad_fe.append(f"{f.get('path')}:snapshot_has_changes")
            elif kind == "new_file":
                if f.get("source_path") is not None or f.get("source_sha256") is not None:
                    bad_fe.append(f"{f.get('path')}:new_file_has_source")
            else:
                bad_fe.append(f"{f.get('path')}:unknown_kind")
        emit(f"frontend manifest problems={bad_fe}")
        check("frontend_manifest.entries_reconcile", not bad_fe, str(bad_fe))

        fx = load_json(FE / "fixtures" / "PROVENANCE.json")
        fxfiles = fx.get("files") or []
        bad_fx: list[str] = []
        for f in fxfiles:
            p = FE / "fixtures" / str(f.get("path"))
            if not p.is_file():
                bad_fx.append(f"{f.get('path')}:missing")
                continue
            if sha256_file(p) != f.get("sha256"):
                bad_fx.append(f"{f.get('path')}:sha256")
            if p.stat().st_size != f.get("size_bytes"):
                bad_fx.append(f"{f.get('path')}:size")
        emit(f"fixtures kind={fx.get('fixture_kind')} files={len(fxfiles)} "
             f"problems={bad_fx}")
        check("fixture_manifest.reconcile",
              fx.get("provenance_version") == "fixture-provenance/1"
              and fx.get("fixture_kind") == "synthetic"
              and {f.get("path") for f in fxfiles} == EXPECTED_FIXTURE_PATHS
              and not bad_fx, str(bad_fx))
    except Exception as e:  # noqa: BLE001
        check("manifests.read_and_validate", False, f"exception={e!r}")

    # ---- 4. containment scans ----------------------------------------------------
    emit()
    emit("--- 4. operations package / A13 tests / A13 tools containment scan ---")
    try:
        scan_product = (sorted(OPS_PKG.glob("*.py"))
                        + [STAGING / t for t in A13_TESTS])
        scan_tools = sorted(TOOLS.glob("a13_*.py"))
        offenders: list[str] = []
        for p in scan_product + scan_tools:
            body = p.read_text(encoding="utf-8")
            for pat in FORBIDDEN_IMPORT_PATTERNS:
                if pat.search(body):
                    offenders.append(f"{rel(p)}::{pat.pattern}")
        for p in scan_product:
            if DESKTOP_PATTERN.search(p.read_text(encoding="utf-8")):
                offenders.append(f"{rel(p)}::Desktop")
        fe_scanned = 0
        for p in sorted(FE.rglob("*")):
            if p.is_file():
                fe_scanned += 1
                try:
                    if DESKTOP_PATTERN.search(p.read_text(encoding="utf-8")):
                        offenders.append(f"{rel(p)}::Desktop")
                except UnicodeDecodeError:
                    pass
        emit(f"scanned product={len(scan_product)} tools={len(scan_tools)} "
             f"frontend_files={fe_scanned} offenders={offenders}")
        check("import.no_original_app_reference", not offenders, str(offenders))
        check("import.scan_coverage",
              len(scan_product) == 6 and len(scan_tools) == 4,
              f"product={len(scan_product)} tools={len(scan_tools)}")
    except Exception as e:  # noqa: BLE001
        check("import.no_original_app_reference", False, f"exception={e!r}")

    # ---- 5. fresh liveness (offline pytest; transcript kept as evidence) --------
    emit()
    emit("--- 5. fresh liveness: collect-only + targeted A13 run ---")
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
        check("liveness.collect_887",
              collect.returncode == 0 and count == EXPECTED_COLLECTED
              and len(node_lines) == EXPECTED_COLLECTED,
              f"rc={collect.returncode} count={count} nodes={len(node_lines)}")

        targeted = run_pytest(list(A13_TESTS) + ["-q"])
        targeted_text = targeted.stdout + targeted.stderr
        tail = targeted_text.strip().splitlines()[-1] if targeted_text.strip() else ""
        emit(f"targeted rc={targeted.returncode} tail={tail}")
        mf = re.search(r"(\d+) failed", targeted_text)
        failed_count = int(mf.group(1)) if mf else 0
        mp = re.search(r"(\d+) passed", targeted_text)
        passed_count = int(mp.group(1)) if mp else None
        check("liveness.targeted_31_passed",
              targeted.returncode == 0 and passed_count == EXPECTED_TARGETED_PASSED
              and failed_count == 0,
              f"rc={targeted.returncode} passed={passed_count} failed={failed_count}")
        (EV / "python_rerun.txt").write_text(targeted_text, encoding="utf-8", newline="\n")
    except Exception as e:  # noqa: BLE001
        check("liveness.collect_887", False, f"exception={e!r}")

    # ---- 6. fresh node liveness (offline; transcript kept as evidence) ----------
    emit()
    emit("--- 6. fresh node liveness: staged frontend suite (27 tests) ---")
    try:
        node = node_exe()
        if not node:
            check("node.node_available", False, "node.exe not found")
        else:
            nr = subprocess.run(
                [node, "--test", "integration-staging/frontend/tests/*.test.mjs"],
                cwd=str(WS), env=probe_env(), capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=180)
            ntext = nr.stdout + nr.stderr
            nt = node_count(ntext, "tests")
            np = node_count(ntext, "pass")
            nf = node_count(ntext, "fail")
            emit(f"node rc={nr.returncode} tests={nt} pass={np} fail={nf}")
            check("node.run_27_pass",
                  nr.returncode == 0 and nt == EXPECTED_NODE_TESTS
                  and np == EXPECTED_NODE_PASS and nf == EXPECTED_NODE_FAIL,
                  f"rc={nr.returncode} tests={nt} pass={np} fail={nf}")
            (EV / "frontend_rerun.txt").write_text(ntext, encoding="utf-8", newline="\n")
    except Exception as e:  # noqa: BLE001
        check("node.run_27_pass", False, f"exception={e!r}")

    # ---- 7. ledger state ----------------------------------------------------------
    emit()
    emit("--- 7. ledger state ---")
    led: dict = {}
    a13: dict = {}
    try:
        led = load_json(EXEC / "execution-ledger.json")
        by_id = {t.get("task_id"): t for t in led.get("tasks", [])}
        a13 = by_id.get("A13", {})
        codes = a13.get("exit_codes", [])
        commands = a13.get("commands", [])
        nonzero = [c for c in codes if c not in (0, None)]
        failures = a13.get("failures") or []
        masked = [f for f in failures if f.get("exit_code_masked")]
        rc1 = [f for f in failures if f.get("exit_code") == 1
               and not f.get("exit_code_masked")]
        row_rc1 = [f for f in rc1 if "seq 48" in str(f.get("evidence"))]
        dev_rc1 = [f for f in rc1 if "a13_final_run1" in str(f.get("evidence"))]
        emit(f"A13 exit_codes n={len(codes)} nonzero={nonzero} failures={len(failures)} "
             f"masked={len(masked)} rc1={len(rc1)} row_rc1={len(row_rc1)} "
             f"dev_rc1={len(dev_rc1)} commands={len(commands)}")
        check("ledger.exit_codes_consistent",
              bool(codes) and len(codes) == len(commands) == 56
              and set(nonzero) <= {1} and len(nonzero) == 1
              and len(row_rc1) == 1 and len(rc1) == len(row_rc1) + len(dev_rc1) == 2,
              f"codes={len(codes)} nonzero={nonzero} rc1={len(rc1)}")
        check("ledger.failure_bookkeeping",
              len(failures) == 5 and len(masked) == 3,
              f"failures={len(failures)} masked={len(masked)}")

        tasks = led.get("tasks", [])
        ids = [t.get("task_id") for t in tasks]
        gates = led.get("gates", {})
        open_gates = [g for g, v in gates.items() if (v or {}).get("open")]
        statuses: dict[str, int] = {}
        for t in tasks:
            statuses[t["status"]] = statuses.get(t["status"], 0) + 1
        emit(f"task_count={len(ids)} unique={len(set(ids))} "
             f"statuses={json.dumps(statuses, sort_keys=True)}")
        emit(f"A13_status={a13.get('status')} gates={len(gates)} open={open_gates}")
        check("ledger.count_unique_27",
              len(ids) == 27 and len(set(ids)) == 27
              and not [t for t in EXPECTED_TASK_IDS if t not in ids]
              and not [t for t in ids if t not in EXPECTED_TASK_IDS])
        check("ledger.a13_staged_pass", a13.get("status") == "staged_pass",
              f"A13={a13.get('status')}")
        check("ledger.no_merged_pass", "merged_pass" not in statuses)
        check("ledger.gates_closed", len(gates) == 7 and not open_gates,
              f"open={open_gates}")
        expected_roots = [STAGING.as_posix(), EXEC.as_posix()]
        check("ledger.a13_write_roots",
              a13.get("allowed_write_roots") == expected_roots
              and led.get("allowed_write_roots") == expected_roots)
        check("ledger.a13_dependencies", a13.get("dependencies") == ["A12"],
              str(a13.get("dependencies")))
        check("ledger.a13_record_fields",
              bool(a13.get("evidence_paths")) and bool(a13.get("input_hashes"))
              and bool(a13.get("commands")) and bool(a13.get("changed_files"))
              and bool(a13.get("test_results")) and bool(a13.get("remaining_gaps"))
              and (a13.get("next_action") or "").strip() != "")
    except Exception as e:  # noqa: BLE001
        check("ledger.load_and_validate", False, f"exception={e!r}")

    # ---- 8. close patch consistency ----------------------------------------------
    emit()
    emit("--- 8. close patch consistency (changed files, inputs, exit codes) ---")
    try:
        patch = load_json(STAGING / "runtime" / "ledger-patches" / "A13_close.json")
        cf = patch.get("changed_files") or []
        outside = [f for f in cf
                   if not any(f.replace("\\", "/").startswith(r) for r in ROOT_STRINGS)]
        post_close = {
            "docs/integration/execution/evidence/A13/final_checks.txt",
            "docs/integration/execution/evidence/A13/python_rerun.txt",
            "docs/integration/execution/evidence/A13/frontend_rerun.txt",
        }
        fc_rel = "integration-staging/tools/a13_final_checks.py"
        deliverable_substrings = [
            "integration-staging/src/examdata_integration/operations/checkpoints.py",
            "integration-staging/src/examdata_integration/operations/coverage.py",
            "integration-staging/fixtures/synthetic/operations/unsupported-checkpoint.json",
            "integration-staging/tests/test_operations_checkpoints.py",
            "integration-staging/tests/test_frontend_staged_copy.py",
            "integration-staging/tools/a13_capture_fixtures.py",
            "integration-staging/tools/a13_frontend_provenance.py",
            "integration-staging/tools/a13_close_patch.py",
            "docs/integration/execution/A13_REPORT.md",
        ]
        emit(f"changed_files={len(cf)} final_checks_registered={fc_rel in cf} "
             f"outside_roots={outside} post_close_listed={sorted(set(cf) & post_close)}")
        check("close_patch.changed_files_inside_roots", not outside, str(outside))
        check("close_patch.post_close_not_listed", not (set(cf) & post_close))
        check("close_patch.deliverables_listed",
              all(d in cf for d in deliverable_substrings),
              str([d for d in deliverable_substrings if d not in cf]))
        check("close_patch.final_checks_registered",
              fc_rel in cf and len(cf) >= 40,
              f"n={len(cf)} registered={fc_rel in cf}")

        ih = patch.get("input_hashes") or {}
        bad_ih: list[str] = []
        for r, h in ih.items():
            if r == LEDGER_REL or r in ACTIVE_OWNER_INPUTS:
                continue
            p = WS / r
            if not p.is_file():
                bad_ih.append(f"{r}:missing")
            elif sha256_file(p) != h:
                bad_ih.append(f"{r}:sha256")
        native_obs = []
        for r in sorted(ACTIVE_OWNER_INPUTS):
            p = WS / r
            cur = sha256_file(p) if p.is_file() else None
            native_obs.append(f"{r}: recorded={str(ih.get(r))[:12]} "
                              f"current={str(cur)[:12]} drift={ih.get(r) != cur}")
        emit(f"input_hashes={len(ih)} recompute_problems={bad_ih} "
             f"active_owner_observations={native_obs}")
        check("close_patch.input_hashes_recompute", not bad_ih, str(bad_ih))
        check("close_patch.native_inputs_registered",
              all(isinstance(ih.get(r), str) and len(ih.get(r, "")) == 64
                  for r in ACTIVE_OWNER_INPUTS),
              str({r: ih.get(r) for r in ACTIVE_OWNER_INPUTS}))
        check("close_patch.input_hash_count",
              len(ih) == 35 + len(cf), f"{len(ih)} vs 35+{len(cf)}")
        check("close_patch.exit_codes_match_ledger",
              patch.get("exit_codes") == a13.get("exit_codes"))
        check("close_patch.meta",
              patch.get("dependencies") == ["A12"]
              and patch.get("blocked_by") == []
              and patch.get("allowed_write_roots") == [STAGING.as_posix(), EXEC.as_posix()],
              json.dumps({k: patch.get(k) for k in
                          ("dependencies", "blocked_by", "allowed_write_roots")}))
    except Exception as e:  # noqa: BLE001
        check("close_patch.load_and_validate", False, f"exception={e!r}")

    # ---- 9. containment of the A13 write set -------------------------------------
    emit()
    emit("--- 9. containment of the A13 write set ---")
    try:
        outside = [f for f in (a13.get("changed_files") or [])
                   if not any(f.replace("\\", "/").startswith(r) for r in ROOT_STRINGS)]
        emit(f"ledger_changed_files_outside_roots={outside}")
        check("containment.changed_files_inside_roots", not outside)

        leaks = []
        for sub in ("src", "tests", "frontend"):
            for p in (STAGING / sub).rglob("*"):
                if p.is_dir() and p.name == "__pycache__":
                    leaks.append(rel(p))
                elif p.is_file() and p.suffix in (".pyc", ".pyo"):
                    leaks.append(rel(p))
        emit(f"pycache_leaks={leaks}")
        check("containment.no_bytecode_under_staging", not leaks)
    except Exception as e:  # noqa: BLE001
        check("containment.changed_files_inside_roots", False, f"exception={e!r}")

    # ---- 10. sha256 manifest -------------------------------------------------------
    emit()
    emit("--- 10. artifact inventory + sha256 manifest (excluding this transcript) ---")
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

    # ---- verdict -------------------------------------------------------------------
    emit()
    emit("--- 11. verdict ---")
    failed = [(n, d) for n, ok, d in checks if not ok]
    for n, ok, d in checks:
        emit(f"{n}: {'PASS' if ok else 'FAIL'}{(' (' + d + ')') if d and not ok else ''}")
    ok_all = not failed
    emit(f"A13_FINAL_CHECKS_JSON: {'PASS' if ok_all else 'FAIL'}")
    emit(f"FINAL_CHECKS: {'PASS' if ok_all else 'FAIL'}")

    text = "\n".join(lines) + "\n"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text, encoding="utf-8", newline="\n")
    sys.stdout.write(text)
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
