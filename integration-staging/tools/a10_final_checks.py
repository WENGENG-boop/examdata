#!/usr/bin/env python3
"""A10 closing checks for the Phase A integration (run AFTER the ledger is closed).

Validates:
  1. artifact existence (api package, tools, tests, report, patch, evidence);
  2. the API probe re-runs offline and reports A10_PROBE: PASS (82/82),
     verifying - never rewriting - the stored transcript;
  3. the api package imports only the staged tree and stdlib: it never imports
     the original application (no `import app` / `from examdata import ...`),
     and no staged file names an original absolute path;
  4. containment: every A10 changed file is inside a Phase A writable root, and
     no __pycache__/.pyc leaked under the staged source or tests;
  5. the staged suite transcript reports 576 passed and no failures, and the
     ledger exit codes agree with the recorded failures;
  6. ledger: 27 tasks, A10 staged_pass, 7 gates closed, no merged_pass, A10 fields;
  7. sha256 manifest of both Phase A roots (excluding this transcript).

Writes (and prints) the transcript to
  docs/integration/execution/evidence/A10/final_checks.txt  (override with --out)
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
EV = EXEC / "evidence" / "A10"
STAGING = WS / "integration-staging"
SRC = STAGING / "src"
API = SRC / "examdata_integration" / "api"
PROBE = STAGING / "tools" / "a10_probe_api.py"
ROOTS = [STAGING, EXEC]

sys.path.insert(0, str(SRC))

EXPECTED_TASK_IDS = ["A%02d" % i for i in range(16)] + ["B%02d" % i for i in range(11)]
ROOT_STRINGS = [STAGING.relative_to(WS).as_posix() + "/", EXEC.relative_to(WS).as_posix() + "/"]
EXPECTED_PROBE_SCENARIOS = 82
EXPECTED_PYTEST = "576 passed"

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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(EV / "final_checks.txt"))
    args = ap.parse_args()
    out_path = Path(args.out)
    out_path = (out_path if out_path.is_absolute() else WS / out_path).resolve()

    lines: list[str] = []

    def emit(s: str = "") -> None:
        lines.append(s)

    emit("=== A10 final checks (isolated v2 API: integration-staging/tools/a10_final_checks.py) ===")
    emit(f"generated_at_local: {datetime.now().astimezone().isoformat(timespec='seconds')}")
    emit(f"generated_at_utc:   {datetime.now(timezone.utc).isoformat(timespec='seconds')}")
    emit(f"cwd: {Path.cwd()}")
    emit()

    # ---- 1. artifact existence -------------------------------------------------
    emit("--- 1. artifact existence ---")
    required = [
        "integration-staging/src/examdata_integration/api/__init__.py",
        "integration-staging/src/examdata_integration/api/envelope.py",
        "integration-staging/src/examdata_integration/api/pagination.py",
        "integration-staging/src/examdata_integration/api/dataset.py",
        "integration-staging/src/examdata_integration/api/view.py",
        "integration-staging/src/examdata_integration/api/links.py",
        "integration-staging/src/examdata_integration/api/openapi.py",
        "integration-staging/src/examdata_integration/api/app.py",
        "integration-staging/tests/test_api_envelope.py",
        "integration-staging/tests/test_api_routes.py",
        "integration-staging/tests/test_api_pagination.py",
        "integration-staging/tests/test_api_links_openapi.py",
        "integration-staging/tests/test_api_dataset.py",
        "integration-staging/tools/a10_probe_api.py",
        "integration-staging/tools/a10_final_checks.py",
        "integration-staging/tools/a10_close_patch.py",
        "integration-staging/runtime/ledger-patches/A10_close.json",
        "docs/integration/execution/A10_REPORT.md",
        "docs/integration/execution/execution-ledger.json",
        "docs/integration/execution/evidence/A10/api_stdout.txt",
        "docs/integration/execution/evidence/A10/pytest_run_stdout.txt",
        "docs/integration/execution/evidence/A10/final_checks.txt",
    ]
    missing_files = [r for r in required if not (WS / r).is_file()]
    emit(f"missing={missing_files}")
    check("artifacts.all_present", not missing_files)

    # ---- 2. API probe (re-run; the transcript is read-only evidence) -----------
    emit()
    emit("--- 2. API probe re-run (transcript is not rewritten) ---")
    try:
        env = dict(os.environ)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"] = "1"
        proc = subprocess.run([sys.executable, str(PROBE)],
                              cwd=str(STAGING), env=env, capture_output=True, text=True)
        text = proc.stdout
        ok_lines = sum(1 for ln in text.splitlines() if ln.startswith("[ok]"))
        fail_lines = [ln for ln in text.splitlines() if ln.startswith("[FAIL]")]
        emit(f"exit={proc.returncode} ok_scenarios={ok_lines} fail_scenarios={fail_lines}")
        check("probe.pass", proc.returncode == 0 and "A10_PROBE: PASS" in text
              and "A10_PROBE: FAIL" not in text, f"rc={proc.returncode}")
        check("probe.scenario_count", ok_lines == EXPECTED_PROBE_SCENARIOS
              and not fail_lines, f"ok={ok_lines}")

        stored = EV / "api_stdout.txt"
        stored_text = stored.read_text(encoding="utf-8")
        stored_ok = sum(1 for ln in stored_text.splitlines() if ln.startswith("[ok]"))
        emit(f"stored_transcript ok_scenarios={stored_ok} (left untouched)")
        check("probe.transcript_matches", "A10_PROBE: PASS" in stored_text
              and stored_ok == EXPECTED_PROBE_SCENARIOS)
    except Exception as e:  # noqa: BLE001
        check("probe.pass", False, f"exception={e!r}")

    # ---- 3. the api package imports only the staged tree ----------------------
    emit()
    emit("--- 3. api package import containment ---")
    try:
        offenders: list[str] = []
        for p in sorted(API.glob("*.py")):
            body = p.read_text(encoding="utf-8")
            for pat in FORBIDDEN_IMPORT_PATTERNS:
                if pat.search(body):
                    offenders.append(f"{rel(p)}::{pat.pattern}")
        emit(f"forbidden_references={offenders}")
        check("import.no_original_app_reference", not offenders)
        check("import.api_package_present", len(list(API.glob("*.py"))) == 8,
              str(len(list(API.glob("*.py")))))
    except Exception as e:  # noqa: BLE001
        check("import.no_original_app_reference", False, f"exception={e!r}")

    # ---- 4. pytest transcript ---------------------------------------------------
    emit()
    emit("--- 4. staged suite transcript ---")
    try:
        text = (EV / "pytest_run_stdout.txt").read_text(encoding="utf-8")
        ok = EXPECTED_PYTEST in text and " failed" not in text
        emit(f"'{EXPECTED_PYTEST}'={ok}")
        check("pytest.transcript_576_passed", ok)
    except Exception as e:  # noqa: BLE001
        check("pytest.transcript_576_passed", False, f"exception={e!r}")

    # ---- 5. ledger state --------------------------------------------------------
    emit()
    emit("--- 5. ledger state ---")
    led: dict = {}
    by_id: dict = {}
    try:
        led = load_json(EXEC / "execution-ledger.json")
        by_id = {t.get("task_id"): t for t in led.get("tasks", [])}
        a10 = by_id.get("A10", {})
        codes = a10.get("exit_codes", [])
        nonzero = [c for c in codes if c not in (0, None)]
        failures = a10.get("failures") or []
        emit(f"A10 exit_codes={codes} nonzero={nonzero} failures={len(failures)}")
        check("ledger.exit_codes_consistent",
              bool(codes) and len(nonzero) == len(failures) and set(nonzero) <= {1},
              f"codes={codes} nonzero={nonzero} failures={len(failures)}")

        tasks = led.get("tasks", [])
        ids = [t.get("task_id") for t in tasks]
        gates = led.get("gates", {})
        open_gates = [g for g, v in gates.items() if v.get("open")]
        statuses: dict[str, int] = {}
        for t in tasks:
            statuses[t["status"]] = statuses.get(t["status"], 0) + 1
        emit(f"task_count={len(ids)} unique={len(set(ids))} "
             f"statuses={json.dumps(statuses, sort_keys=True)}")
        emit(f"A10_status={a10.get('status')} gates={len(gates)} open={open_gates}")
        check("ledger.count_unique_27",
              len(ids) == 27 and len(set(ids)) == 27
              and not [t for t in EXPECTED_TASK_IDS if t not in ids]
              and not [t for t in ids if t not in EXPECTED_TASK_IDS])
        check("ledger.a10_staged_pass", a10.get("status") == "staged_pass",
              f"A10={a10.get('status')}")
        check("ledger.no_merged_pass", "merged_pass" not in statuses)
        check("ledger.gates_closed", len(gates) == 7 and not open_gates, f"open={open_gates}")
        expected_roots = [STAGING.as_posix(), EXEC.as_posix()]
        check("ledger.a10_write_roots",
              a10.get("allowed_write_roots") == expected_roots
              and led.get("allowed_write_roots") == expected_roots)
        check("ledger.a10_record_fields",
              bool(a10.get("evidence_paths")) and bool(a10.get("input_hashes"))
              and bool(a10.get("commands")) and bool(a10.get("changed_files"))
              and bool(a10.get("test_results")) and bool(a10.get("remaining_gaps"))
              and (a10.get("next_action") or "").strip() != "")
    except Exception as e:  # noqa: BLE001
        check("ledger.load_and_validate", False, f"exception={e!r}")

    # ---- 6. containment ---------------------------------------------------------
    emit()
    emit("--- 6. containment of the A10 write set ---")
    try:
        a10 = by_id.get("A10", {})
        outside = [f for f in a10.get("changed_files", [])
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

    # ---- 7. sha256 manifest -----------------------------------------------------
    emit()
    emit("--- 7. artifact inventory + sha256 manifest (excluding this transcript) ---")
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
    emit("--- 8. verdict ---")
    failed = [(n, d) for n, ok, d in checks if not ok]
    for n, ok, d in checks:
        emit(f"{n}: {'PASS' if ok else 'FAIL'}{(' (' + d + ')') if d and not ok else ''}")
    ok_all = not failed
    emit(f"A10_FINAL_CHECKS_JSON: {'PASS' if ok_all else 'FAIL'}")
    emit(f"FINAL_CHECKS: {'PASS' if ok_all else 'FAIL'}")

    text = "\n".join(lines) + "\n"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text, encoding="utf-8", newline="\n")
    sys.stdout.write(text)
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
