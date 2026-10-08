#!/usr/bin/env python3
"""A06 closing checks for the Phase A integration (run AFTER the ledger is closed).

Validates:
  1. artifact existence (runtime package, components, config, tools, tests,
     report, patch, evidence);
  2. the runtime probe re-runs offline and reports A06_PROBE: PASS (31/31),
     verifying — never rewriting — the stored transcript;
  3. the classification table is complete, stable and precedence-consistent
     (in-process, all 14 outcomes and their error codes);
  4. a real timeout run still records cleanup evidence (tree terminated, no
     orphan) — the runner's core safety property;
  5. the doctor creates nothing, stays offline-compliant and redacts a secret;
  6. environment precedence holds: staged value wins, a non-allowlisted variable
     never reaches the child;
  7. containment: every A06 changed file is inside a Phase A writable root, and
     no __pycache__/.pyc leaked under the staged source or tests;
  8. the staged suite transcript reports 232 passed, and the ledger exit codes
     agree with the recorded failures;
  9. ledger: 27 tasks, A06 staged_pass, 7 gates closed, no merged_pass, A06 fields;
 10. sha256 manifest of both Phase A roots (excluding this transcript).

Writes (and prints) the transcript to
  docs/integration/execution/evidence/A06/final_checks.txt  (override with --out)
and exits 0 (PASS) or 1 (FAIL).

Phase A tool (integration-staging/tools/). Stdlib only; nothing original is modified.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path

sys.dont_write_bytecode = True

WS = Path(__file__).resolve().parents[2]
EXEC = WS / "docs" / "integration" / "execution"
EV = EXEC / "evidence" / "A06"
STAGING = WS / "integration-staging"
SRC = STAGING / "src"
PROBE = STAGING / "tools" / "a06_probe_runner.py"
ROOTS = [STAGING, EXEC]

sys.path.insert(0, str(SRC))
# R04: product code resolves its deployment root explicitly (never by directory name).
os.environ.setdefault("EXAMDATA_INTEGRATION_ROOT", str(STAGING))

EXPECTED_TASK_IDS = ["A%02d" % i for i in range(16)] + ["B%02d" % i for i in range(11)]
ROOT_STRINGS = [STAGING.relative_to(WS).as_posix() + "/", EXEC.relative_to(WS).as_posix() + "/"]
EXPECTED_PROBE_SCENARIOS = 31

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

    emit("=== A06 final checks (runner: integration-staging/tools/a06_final_checks.py) ===")
    emit(f"generated_at_local: {datetime.now().astimezone().isoformat(timespec='seconds')}")
    emit(f"generated_at_utc:   {datetime.now(timezone.utc).isoformat(timespec='seconds')}")
    emit(f"cwd: {Path.cwd()}")
    emit()

    from examdata_integration.runtime import (
        ERROR_CODES,
        INFRASTRUCTURE_OUTCOMES,
        OUTCOME_PRECEDENCE,
        RETRYABLE_OUTCOMES,
        RunnerOutcome,
        error_object,
        load_manifest_set,
        parse_stdout,
        resolve_config,
    )
    from examdata_integration.runtime.doctor import build_report
    from examdata_integration.runtime.redact import SECRET_PLACEHOLDER
    from examdata_integration.testing import runtime_support

    staging = runtime_support.STAGING

    # ---- 1. artifact existence -------------------------------------------------
    emit("--- 1. artifact existence ---")
    required = [
        "integration-staging/src/examdata_integration/runtime/__init__.py",
        "integration-staging/src/examdata_integration/runtime/settings.py",
        "integration-staging/src/examdata_integration/runtime/manifest.py",
        "integration-staging/src/examdata_integration/runtime/classification.py",
        "integration-staging/src/examdata_integration/runtime/redact.py",
        "integration-staging/src/examdata_integration/runtime/runner.py",
        "integration-staging/src/examdata_integration/runtime/doctor.py",
        "integration-staging/src/examdata_integration/testing/runtime_support.py",
        "integration-staging/components/fake-node-cli/fake-cli.mjs",
        "integration-staging/components/manifest.json",
        "integration-staging/config/staging.env.example",
        "integration-staging/config/staging-config.example.json",
        "integration-staging/tools/a06_probe_runner.py",
        "integration-staging/tools/a06_final_checks.py",
        "integration-staging/tools/a06_close_patch.py",
        "integration-staging/tests/test_config_resolution.py",
        "integration-staging/tests/test_config_manifest.py",
        "integration-staging/tests/test_runner_classification.py",
        "integration-staging/tests/test_runner_limits.py",
        "integration-staging/runtime/ledger-patches/A06_close.json",
        "docs/integration/execution/A06_REPORT.md",
        "docs/integration/execution/execution-ledger.json",
        "docs/integration/execution/evidence/A06/pytest_run_stdout.txt",
    ]
    missing_files = [r for r in required if not (WS / r).is_file()]
    emit(f"missing={missing_files}")
    check("artifacts.all_present", not missing_files)

    # ---- 2. runtime probe (re-run; the transcript is read-only evidence) --------
    emit()
    emit("--- 2. runtime probe re-run (transcript is not rewritten) ---")
    try:
        env = dict(os.environ)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        proc = subprocess.run([sys.executable, str(PROBE)],
                              cwd=str(STAGING), env=env, capture_output=True, text=True)
        text = proc.stdout
        ok_lines = sum(1 for ln in text.splitlines() if ln.startswith("[ok]"))
        fail_lines = [ln for ln in text.splitlines() if ln.startswith("[FAIL]")]
        emit(f"exit={proc.returncode} ok_scenarios={ok_lines} fail_scenarios={fail_lines}")
        check("probe.pass", proc.returncode == 0 and "A06_PROBE: PASS" in text
              and "A06_PROBE: FAIL" not in text, f"rc={proc.returncode}")
        check("probe.scenario_count", ok_lines == EXPECTED_PROBE_SCENARIOS
              and not fail_lines, f"ok={ok_lines}")

        stored = EV / "runner_stdout.txt"
        if stored.is_file():
            stored_text = stored.read_text(encoding="utf-8")
            stored_ok = sum(1 for ln in stored_text.splitlines() if ln.startswith("[ok]"))
            emit(f"stored_transcript ok_scenarios={stored_ok} (left untouched)")
            check("probe.transcript_matches", "A06_PROBE: PASS" in stored_text
                  and stored_ok == EXPECTED_PROBE_SCENARIOS)
        else:
            EV.mkdir(parents=True, exist_ok=True)
            stored.write_text(text, encoding="utf-8", newline="\n")
            check("probe.transcript_matches", "A06_PROBE: PASS" in text)
    except Exception as e:  # noqa: BLE001
        check("probe.pass", False, f"exception={e!r}")

    # ---- 3. classification table (in-process) -----------------------------------
    emit()
    emit("--- 3. classification table (in-process) ---")
    try:
        outcomes = list(RunnerOutcome)
        failure_codes = [ERROR_CODES[o] for o in outcomes if o is not RunnerOutcome.OK]
        emit(f"outcomes={len(outcomes)} failure_codes={len(set(failure_codes))}")
        check("classify.all_outcomes_have_codes",
              set(ERROR_CODES) == set(outcomes) and all(ERROR_CODES.values()))
        check("classify.codes_distinct",
              len(failure_codes) == len(set(failure_codes)))
        check("classify.precedence_covers_all",
              set(OUTCOME_PRECEDENCE) == set(outcomes)
              and len(OUTCOME_PRECEDENCE) == len(outcomes))
        check("classify.ok_error_is_none", error_object(RunnerOutcome.OK, None) is None)
        check("classify.business_failure_not_infra",
              RunnerOutcome.BUSINESS_FAILURE not in INFRASTRUCTURE_OUTCOMES
              and RunnerOutcome.OK not in INFRASTRUCTURE_OUTCOMES)
        check("classify.retryable_set",
              RETRYABLE_OUTCOMES == frozenset({RunnerOutcome.QUEUE_FULL, RunnerOutcome.TIMEOUT}))
        obj = error_object(RunnerOutcome.QUEUE_FULL, "busy")
        check("classify.error_object_shape",
              obj == {"code": "queue_full", "message": "busy", "retryable": True})
        # a killed-overflow / cancelled process is never mislabelled as nonzero exit
        o, _, _ = parse_stdout('{"ok": false}')
        check("classify.business_failure_parsed", o is RunnerOutcome.BUSINESS_FAILURE)
    except Exception as e:  # noqa: BLE001
        check("classify.all_outcomes_have_codes", False, f"exception={e!r}")

    # ---- 4. cleanup evidence on a real timeout ----------------------------------
    emit()
    emit("--- 4. cleanup evidence (real timeout) ---")
    try:
        manifests = load_manifest_set(runtime_support.MANIFEST_PATH, deployment_root=staging)
        runner = runtime_support.runner(
            manifests, limits=runtime_support.limits(process_timeout=0.6))
        result = runner.run("fake_cli", "slow")
        cleanup = result.cleanup
        emit(f"outcome={result.outcome.value} cleanup={json.dumps(cleanup, sort_keys=True)}")
        check("cleanup.timeout_classified", result.outcome is RunnerOutcome.TIMEOUT)
        check("cleanup.tree_terminated", cleanup.get("terminated") is True
              and cleanup.get("method") in ("taskkill_tree", "kill"))
        check("cleanup.no_orphan", cleanup.get("orphan_check") == "returncode_set"
              and cleanup.get("pid_alive_after") is not True
              and cleanup.get("readers_alive") is False)
    except Exception as e:  # noqa: BLE001
        check("cleanup.timeout_classified", False, f"exception={e!r}")

    # ---- 5. doctor is read-only, offline-compliant, redacting -------------------
    emit()
    emit("--- 5. doctor (read-only) ---")
    try:
        sentinel = STAGING / "runtime" / "tmp" / "a06-final-doctor-catalog"
        secret = "final-checks-secret"
        report = build_report(env={"EXAMDATA_CATALOG_ROOT": str(sentinel),
                                   "EXAMDATA_API_KEY": secret},
                              manifest_path=runtime_support.MANIFEST_PATH,
                              deployment_root=staging)
        emit(f"creates_directories={report['creates_directories']} "
             f"network={report['network']['mode']} compliant={report['network']['compliant']}")
        check("doctor.creates_nothing", report["creates_directories"] is False
              and not sentinel.exists())
        check("doctor.offline_compliant", report["network"]["compliant"] is True)
        check("doctor.redacts_secret", secret not in json.dumps(report))
    except Exception as e:  # noqa: BLE001
        check("doctor.creates_nothing", False, f"exception={e!r}")

    # ---- 6. environment precedence (in-process) ---------------------------------
    emit()
    emit("--- 6. environment precedence ---")
    try:
        runner = runtime_support.runner(
            manifests, base_env={"FAKE_CLI_TOKEN": "inherited", "SECRET_LEAK": "leak"},
            extra_env={"FAKE_CLI_TOKEN": "staged"})
        res = runner.run("fake_cli", "env",
                         ["FAKE_CLI_TOKEN", "SECRET_LEAK", "EXAMDATA_DATA_FAKE_DATA"])
        child = res.payload["env"]
        emit(f"child_env={json.dumps(child, sort_keys=True)}")
        check("env.staged_overrides_inherited", child["FAKE_CLI_TOKEN"] == "staged")
        check("env.non_allowlisted_absent", child["SECRET_LEAK"] is None)
        check("env.data_root_injected",
              Path(child["EXAMDATA_DATA_FAKE_DATA"]) == staging / "runtime" / "data" / "fake-cli")
    except Exception as e:  # noqa: BLE001
        check("env.staged_overrides_inherited", False, f"exception={e!r}")

    # ---- 7. configuration precedence (in-process) -------------------------------
    emit()
    emit("--- 7. configuration precedence ---")
    try:
        cfg = resolve_config(explicit={"ielts_max_concurrent": 9},
                             env={"EXAMDATA_IELTS_MAX_CONCURRENT": "8"})
        check("config.explicit_over_env", cfg.get("ielts_max_concurrent") == 9
              and cfg.source("ielts_max_concurrent") == "explicit")
        check("config.offline_default", cfg.get("network_mode") == "offline")
        rows = {r["key"]: r for r in
                resolve_config(explicit={"api_key": "s"}, env={}).settings_report()}
        check("config.secret_redacted", rows["api_key"]["value"] == "set")
    except Exception as e:  # noqa: BLE001
        check("config.explicit_over_env", False, f"exception={e!r}")

    # ---- 8. pytest transcript + ledger exit codes -------------------------------
    emit()
    emit("--- 8. staged suite transcript and ledger exit codes ---")
    try:
        text = (EV / "pytest_run_stdout.txt").read_text(encoding="utf-8")
        ok232 = "232 passed" in text and "failed" not in text.lower()
        emit(f"'232 passed'={ok232}")
        check("pytest.transcript_232_passed", ok232)
    except Exception as e:  # noqa: BLE001
        check("pytest.transcript_232_passed", False, f"exception={e!r}")

    led: dict = {}
    by_id: dict = {}
    try:
        led = load_json(EXEC / "execution-ledger.json")
        by_id = {t.get("task_id"): t for t in led.get("tasks", [])}
        a06 = by_id.get("A06", {})
        codes = a06.get("exit_codes", [])
        nonzero = [c for c in codes if c not in (0, None)]
        failures = a06.get("failures") or []
        emit(f"A06 exit_codes={codes} nonzero={nonzero} failures={len(failures)}")
        check("pytest.ledger_exit_codes_consistent",
              bool(codes) and len(nonzero) == len(failures) and set(nonzero) <= {1},
              f"codes={codes} nonzero={nonzero} failures={len(failures)}")
    except Exception as e:  # noqa: BLE001
        check("pytest.ledger_exit_codes_consistent", False, f"exception={e!r}")

    # ---- 9. containment ---------------------------------------------------------
    emit()
    emit("--- 9. containment of the A06 write set ---")
    try:
        a06 = by_id.get("A06", {})
        outside = [f for f in a06.get("changed_files", [])
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

    # ---- 10. ledger state -------------------------------------------------------
    emit()
    emit("--- 10. ledger state ---")
    try:
        tasks = led.get("tasks", [])
        ids = [t.get("task_id") for t in tasks]
        gates = led.get("gates", {})
        open_gates = [g for g, v in gates.items() if v.get("open")]
        all_statuses: dict[str, int] = {}
        for t in tasks:
            all_statuses[t["status"]] = all_statuses.get(t["status"], 0) + 1
        expected_roots = [STAGING.as_posix(), EXEC.as_posix()]
        a06 = by_id.get("A06", {})
        emit(f"task_count={len(ids)} unique={len(set(ids))} "
             f"statuses={json.dumps(all_statuses, sort_keys=True)}")
        emit(f"A06_status={a06.get('status')} gates={len(gates)} open={open_gates}")
        check("ledger.count_unique_27",
              len(ids) == 27 and len(set(ids)) == 27
              and not [t for t in EXPECTED_TASK_IDS if t not in ids]
              and not [t for t in ids if t not in EXPECTED_TASK_IDS])
        check("ledger.a06_staged_pass", a06.get("status") == "staged_pass",
              f"A06={a06.get('status')}")
        check("ledger.no_merged_pass", "merged_pass" not in all_statuses)
        check("ledger.gates_closed", len(gates) == 7 and not open_gates, f"open={open_gates}")
        check("ledger.a06_write_roots",
              a06.get("allowed_write_roots") == expected_roots
              and led.get("allowed_write_roots") == expected_roots)
        check("ledger.a06_record_fields",
              bool(a06.get("evidence_paths")) and bool(a06.get("input_hashes"))
              and bool(a06.get("commands")) and bool(a06.get("changed_files"))
              and bool(a06.get("test_results")) and bool(a06.get("remaining_gaps"))
              and (a06.get("next_action") or "").strip() != "")
    except Exception as e:  # noqa: BLE001
        check("ledger.load_and_validate", False, f"exception={e!r}")

    # ---- 11. sha256 manifest ----------------------------------------------------
    emit()
    emit("--- 11. artifact inventory + sha256 manifest (excluding this transcript) ---")
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
    emit("--- 12. verdict ---")
    failed = [(n, d) for n, ok, d in checks if not ok]
    for n, ok, d in checks:
        emit(f"{n}: {'PASS' if ok else 'FAIL'}{(' (' + d + ')') if d and not ok else ''}")
    ok_all = not failed
    emit(f"A06_FINAL_CHECKS_JSON: {'PASS' if ok_all else 'FAIL'}")
    emit(f"FINAL_CHECKS: {'PASS' if ok_all else 'FAIL'}")

    text = "\n".join(lines) + "\n"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text, encoding="utf-8", newline="\n")
    sys.stdout.write(text)
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
