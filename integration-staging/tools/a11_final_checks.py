#!/usr/bin/env python3
"""A11 closing checks for the Phase A integration (run AFTER the ledger is closed).

Validates:
  1. artifact existence (api package incl. binary.py, tools, tests, fixtures,
     report, patch, evidence);
  2. the A11 binary probe re-runs offline and reports A11_PROBE: PASS (88/88),
     verifying - never rewriting - the stored transcript;
  3. the A10 probe still passes as a regression (82/82), writing its fresh
     transcript to evidence/A11/a10_probe_rerun.txt;
  4. the api package imports only the staged tree and stdlib: it never imports
     the original application, and no staged file names an original path;
  5. the binary fixture generator --check re-runs write-free and reports all
     13 files matching a fresh render;
  6. the staged suite transcript reports 711 passed and no failures, and the
     ledger exit codes agree with the recorded failures (a failure flagged
     exit_code_masked is excluded from the nonzero-count comparison);
  7. ledger: 27 tasks, A11 staged_pass, 7 gates closed, no merged_pass, A11 fields;
  8. containment: every A11 changed file is inside a Phase A writable root, and
     no __pycache__/.pyc leaked under the staged source or tests;
  9. sha256 manifest of both Phase A roots (excluding this transcript).

Writes (and prints) the transcript to
  docs/integration/execution/evidence/A11/final_checks.txt  (override with --out)
and exits 0 (PASS) or 1 (FAIL).

Phase A tool (integration-staging/tools/). Stdlib only; nothing original is modified.
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
EV = EXEC / "evidence" / "A11"
STAGING = WS / "integration-staging"
SRC = STAGING / "src"
API = SRC / "examdata_integration" / "api"
PROBE = STAGING / "tools" / "a11_probe_binary.py"
PROBE_A10 = STAGING / "tools" / "a10_probe_api.py"
GENERATOR = STAGING / "tools" / "build_binary_fixtures.py"
BINFIX = STAGING / "fixtures" / "synthetic" / "binary"
ROOTS = [STAGING, EXEC]

sys.path.insert(0, str(SRC))

EXPECTED_TASK_IDS = ["A%02d" % i for i in range(16)] + ["B%02d" % i for i in range(11)]
ROOT_STRINGS = [STAGING.relative_to(WS).as_posix() + "/", EXEC.relative_to(WS).as_posix() + "/"]
EXPECTED_PROBE_SCENARIOS = 88
EXPECTED_A10_SCENARIOS = 82
EXPECTED_PYTEST = "711 passed"
EXPECTED_FIXTURE_FILES = 13
GENERATOR_PASS_LINE = f"BINARY_FIXTURES: PASS ({EXPECTED_FIXTURE_FILES} files match a fresh render)"

#: the api package must never reach the original application or the original
#: package root (`examdata`), only the staged `examdata_integration` tree.
FORBIDDEN_IMPORT_PATTERNS = [
    re.compile(r"^\s*import\s+app\b", re.MULTILINE),
    re.compile(r"^\s*from\s+app\b", re.MULTILINE),
    re.compile(r"^\s*import\s+examdata\b(?!_)", re.MULTILINE),
    re.compile(r"^\s*from\s+examdata\b(?!_)", re.MULTILINE),
    re.compile(r"Desktop", re.IGNORECASE),
]

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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(EV / "final_checks.txt"))
    args = ap.parse_args()
    out_path = Path(args.out)
    out_path = (out_path if out_path.is_absolute() else WS / out_path).resolve()

    lines: list[str] = []

    def emit(s: str = "") -> None:
        lines.append(s)

    emit("=== A11 final checks (binary responses: integration-staging/tools/a11_final_checks.py) ===")
    emit(f"generated_at_local: {datetime.now().astimezone().isoformat(timespec='seconds')}")
    emit(f"generated_at_utc:   {datetime.now(timezone.utc).isoformat(timespec='seconds')}")
    emit(f"cwd: {Path.cwd()}")
    emit()

    # ---- 1. artifact existence -------------------------------------------------
    emit("--- 1. artifact existence ---")
    required = [
        "integration-staging/src/examdata_integration/api/__init__.py",
        "integration-staging/src/examdata_integration/api/app.py",
        "integration-staging/src/examdata_integration/api/binary.py",
        "integration-staging/src/examdata_integration/api/envelope.py",
        "integration-staging/src/examdata_integration/api/links.py",
        "integration-staging/src/examdata_integration/api/openapi.py",
        "integration-staging/fixtures/synthetic/binary/manifest.json",
        "integration-staging/fixtures/synthetic/binary/PROVENANCE.json",
        "integration-staging/tests/test_api_binary_fixtures.py",
        "integration-staging/tests/test_api_binary_store.py",
        "integration-staging/tests/test_api_binary_transport.py",
        "integration-staging/tools/build_binary_fixtures.py",
        "integration-staging/tools/a10_probe_api.py",
        "integration-staging/tools/a11_probe_binary.py",
        "integration-staging/tools/a11_final_checks.py",
        "integration-staging/tools/a11_close_patch.py",
        "integration-staging/runtime/ledger-patches/A11_close.json",
        "docs/integration/execution/A11_REPORT.md",
        "docs/integration/execution/execution-ledger.json",
        "docs/integration/execution/evidence/A11/binary_stdout.txt",
        "docs/integration/execution/evidence/A11/pytest_run_stdout.txt",
        "docs/integration/execution/evidence/A11/final_checks.txt",
    ]
    missing_files = [r for r in required if not (WS / r).is_file()]
    emit(f"missing={missing_files}")
    check("artifacts.all_present", not missing_files)

    fixture_files = sorted(p for p in BINFIX.rglob("*") if p.is_file())
    emit(f"binary_fixture_files={len(fixture_files)}")
    check("artifacts.binary_fixtures_13", len(fixture_files) == EXPECTED_FIXTURE_FILES,
          f"count={len(fixture_files)}")

    # ---- 2. A11 binary probe (re-run; the transcript is read-only evidence) ----
    emit()
    emit("--- 2. A11 binary probe re-run (transcript is not rewritten) ---")
    try:
        proc = subprocess.run([sys.executable, str(PROBE)],
                              cwd=str(STAGING), env=probe_env(), capture_output=True, text=True)
        text = proc.stdout
        ok_lines = sum(1 for ln in text.splitlines() if ln.startswith("[ok]"))
        fail_lines = [ln for ln in text.splitlines() if ln.startswith("[FAIL]")]
        emit(f"exit={proc.returncode} ok_scenarios={ok_lines} fail_scenarios={fail_lines}")
        check("probe.pass", proc.returncode == 0 and "A11_PROBE: PASS" in text
              and "A11_PROBE: FAIL" not in text, f"rc={proc.returncode}")
        check("probe.scenario_count", ok_lines == EXPECTED_PROBE_SCENARIOS
              and not fail_lines, f"ok={ok_lines}")

        stored = EV / "binary_stdout.txt"
        stored_text = stored.read_text(encoding="utf-8")
        stored_ok = sum(1 for ln in stored_text.splitlines() if ln.startswith("[ok]"))
        emit(f"stored_transcript ok_scenarios={stored_ok} (left untouched)")
        check("probe.transcript_matches", "A11_PROBE: PASS" in stored_text
              and stored_ok == EXPECTED_PROBE_SCENARIOS)
    except Exception as e:  # noqa: BLE001
        check("probe.pass", False, f"exception={e!r}")

    # ---- 3. A10 probe regression (re-run; fresh transcript kept as evidence) ----
    emit()
    emit("--- 3. A10 probe regression re-run ---")
    try:
        proc = subprocess.run([sys.executable, str(PROBE_A10)],
                              cwd=str(STAGING), env=probe_env(), capture_output=True, text=True)
        text = proc.stdout
        ok_lines = sum(1 for ln in text.splitlines() if ln.startswith("[ok]"))
        emit(f"exit={proc.returncode} ok_scenarios={ok_lines}")
        check("probe.a10_regression", proc.returncode == 0 and "A10_PROBE: PASS" in text
              and "A10_PROBE: FAIL" not in text, f"rc={proc.returncode}")
        check("probe.a10_scenario_count", ok_lines == EXPECTED_A10_SCENARIOS,
              f"ok={ok_lines}")
        (EV / "a10_probe_rerun.txt").write_text(text, encoding="utf-8", newline="\n")
    except Exception as e:  # noqa: BLE001
        check("probe.a10_regression", False, f"exception={e!r}")

    # ---- 4. the api package imports only the staged tree ----------------------
    emit()
    emit("--- 4. api package import containment ---")
    try:
        offenders: list[str] = []
        for p in sorted(API.glob("*.py")):
            body = p.read_text(encoding="utf-8")
            for pat in FORBIDDEN_IMPORT_PATTERNS:
                if pat.search(body):
                    offenders.append(f"{rel(p)}::{pat.pattern}")
        emit(f"forbidden_references={offenders}")
        check("import.no_original_app_reference", not offenders)
        check("import.api_package_present", len(list(API.glob("*.py"))) == 9,
              str(len(list(API.glob("*.py")))))
    except Exception as e:  # noqa: BLE001
        check("import.no_original_app_reference", False, f"exception={e!r}")

    # ---- 5. fixture generator --check (write-free by construction) -------------
    emit()
    emit("--- 5. binary fixture generator --check (write-free) ---")
    try:
        before = {p: p.stat().st_mtime_ns for p in BINFIX.rglob("*") if p.is_file()}
        proc = subprocess.run([sys.executable, str(GENERATOR), "--check"],
                              cwd=str(WS), env=probe_env(), capture_output=True, text=True)
        after = {p: p.stat().st_mtime_ns for p in BINFIX.rglob("*") if p.is_file()}
        emit(f"exit={proc.returncode} stdout_tail={proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else ''}")
        check("fixtures.generator_check", proc.returncode == 0
              and GENERATOR_PASS_LINE in proc.stdout, f"rc={proc.returncode}")
        check("fixtures.check_writes_nothing", before == after,
              f"changed={[rel(p) for p in before if before.get(p) != after.get(p)]}")
    except Exception as e:  # noqa: BLE001
        check("fixtures.generator_check", False, f"exception={e!r}")

    # ---- 6. pytest transcript ---------------------------------------------------
    emit()
    emit("--- 6. staged suite transcript ---")
    try:
        text = (EV / "pytest_run_stdout.txt").read_text(encoding="utf-8")
        ok = EXPECTED_PYTEST in text and " failed" not in text
        emit(f"'{EXPECTED_PYTEST}'={ok}")
        check("pytest.transcript_711_passed", ok)
    except Exception as e:  # noqa: BLE001
        check("pytest.transcript_711_passed", False, f"exception={e!r}")

    # ---- 7. ledger state --------------------------------------------------------
    emit()
    emit("--- 7. ledger state ---")
    led: dict = {}
    by_id: dict = {}
    try:
        led = load_json(EXEC / "execution-ledger.json")
        by_id = {t.get("task_id"): t for t in led.get("tasks", [])}
        a11 = by_id.get("A11", {})
        codes = a11.get("exit_codes", [])
        nonzero = [c for c in codes if c not in (0, None)]
        failures = a11.get("failures") or []
        masked = [f for f in failures if f.get("exit_code_masked")]
        countable = [f for f in failures if not f.get("exit_code_masked")]
        emit(f"A11 exit_codes={codes} nonzero={nonzero} failures={len(failures)} "
             f"masked={len(masked)}")
        check("ledger.exit_codes_consistent",
              bool(codes) and len(nonzero) == len(countable) and set(nonzero) <= {1},
              f"codes={codes} nonzero={nonzero} failures={len(failures)} masked={len(masked)}")

        tasks = led.get("tasks", [])
        ids = [t.get("task_id") for t in tasks]
        gates = led.get("gates", {})
        open_gates = [g for g, v in gates.items() if v.get("open")]
        statuses: dict[str, int] = {}
        for t in tasks:
            statuses[t["status"]] = statuses.get(t["status"], 0) + 1
        emit(f"task_count={len(ids)} unique={len(set(ids))} "
             f"statuses={json.dumps(statuses, sort_keys=True)}")
        emit(f"A11_status={a11.get('status')} gates={len(gates)} open={open_gates}")
        check("ledger.count_unique_27",
              len(ids) == 27 and len(set(ids)) == 27
              and not [t for t in EXPECTED_TASK_IDS if t not in ids]
              and not [t for t in ids if t not in EXPECTED_TASK_IDS])
        check("ledger.a11_staged_pass", a11.get("status") == "staged_pass",
              f"A11={a11.get('status')}")
        check("ledger.no_merged_pass", "merged_pass" not in statuses)
        check("ledger.gates_closed", len(gates) == 7 and not open_gates, f"open={open_gates}")
        expected_roots = [STAGING.as_posix(), EXEC.as_posix()]
        check("ledger.a11_write_roots",
              a11.get("allowed_write_roots") == expected_roots
              and led.get("allowed_write_roots") == expected_roots)
        check("ledger.a11_record_fields",
              bool(a11.get("evidence_paths")) and bool(a11.get("input_hashes"))
              and bool(a11.get("commands")) and bool(a11.get("changed_files"))
              and bool(a11.get("test_results")) and bool(a11.get("remaining_gaps"))
              and (a11.get("next_action") or "").strip() != "")
    except Exception as e:  # noqa: BLE001
        check("ledger.load_and_validate", False, f"exception={e!r}")

    # ---- 8. containment ---------------------------------------------------------
    emit()
    emit("--- 8. containment of the A11 write set ---")
    try:
        a11 = by_id.get("A11", {})
        outside = [f for f in a11.get("changed_files", [])
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

    # ---- 9. sha256 manifest -----------------------------------------------------
    emit()
    emit("--- 9. artifact inventory + sha256 manifest (excluding this transcript) ---")
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

    # ---- verdict ----------------------------------------------------------------
    emit()
    emit("--- 10. verdict ---")
    failed = [(n, d) for n, ok, d in checks if not ok]
    for n, ok, d in checks:
        emit(f"{n}: {'PASS' if ok else 'FAIL'}{(' (' + d + ')') if d and not ok else ''}")
    ok_all = not failed
    emit(f"A11_FINAL_CHECKS_JSON: {'PASS' if ok_all else 'FAIL'}")
    emit(f"FINAL_CHECKS: {'PASS' if ok_all else 'FAIL'}")

    text = "\n".join(lines) + "\n"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text, encoding="utf-8", newline="\n")
    sys.stdout.write(text)
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
