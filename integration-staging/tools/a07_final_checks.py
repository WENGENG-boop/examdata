#!/usr/bin/env python3
"""A07 closing checks for the Phase A integration (run AFTER the ledger is closed).

Validates:
  1. artifact existence (adapters package, fixtures, provenance, tools, tests,
     report, patch, evidence);
  2. the adapter probe re-runs offline and reports A07_PROBE: PASS (42/42),
     verifying — never rewriting — the stored transcript;
  3. the fixture provenance manifest is fresh (capture tool --check);
  4. the two adapter fixtures are labelled synthetic and carry no verified content;
  5. containment: every A07 changed file is inside a Phase A writable root, and no
     __pycache__/.pyc leaked under the staged source or tests;
  6. the staged suite transcript reports 326 passed, and the ledger exit codes
     agree with the recorded failures;
  7. ledger: 27 tasks, A07 staged_pass, 7 gates closed, no merged_pass, A07 fields;
  8. sha256 manifest of both Phase A roots (excluding this transcript).

Writes (and prints) the transcript to
  docs/integration/execution/evidence/A07/final_checks.txt  (override with --out)
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
from datetime import datetime, timezone
from pathlib import Path

sys.dont_write_bytecode = True

WS = Path(__file__).resolve().parents[2]
EXEC = WS / "docs" / "integration" / "execution"
EV = EXEC / "evidence" / "A07"
STAGING = WS / "integration-staging"
SRC = STAGING / "src"
PROBE = STAGING / "tools" / "a07_probe_adapters.py"
CAPTURE = STAGING / "tools" / "a07_capture_adapter_fixtures.py"
ROOTS = [STAGING, EXEC]

sys.path.insert(0, str(SRC))

EXPECTED_TASK_IDS = ["A%02d" % i for i in range(16)] + ["B%02d" % i for i in range(11)]
ROOT_STRINGS = [STAGING.relative_to(WS).as_posix() + "/", EXEC.relative_to(WS).as_posix() + "/"]
EXPECTED_PROBE_SCENARIOS = 42

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

    emit("=== A07 final checks (adapters: integration-staging/tools/a07_final_checks.py) ===")
    emit(f"generated_at_local: {datetime.now().astimezone().isoformat(timespec='seconds')}")
    emit(f"generated_at_utc:   {datetime.now(timezone.utc).isoformat(timespec='seconds')}")
    emit(f"cwd: {Path.cwd()}")
    emit()

    # ---- 1. artifact existence -------------------------------------------------
    emit("--- 1. artifact existence ---")
    required = [
        "integration-staging/src/examdata_integration/adapters/__init__.py",
        "integration-staging/src/examdata_integration/adapters/problems.py",
        "integration-staging/src/examdata_integration/adapters/reader.py",
        "integration-staging/src/examdata_integration/adapters/documents.py",
        "integration-staging/src/examdata_integration/adapters/answers.py",
        "integration-staging/src/examdata_integration/adapters/regions.py",
        "integration-staging/src/examdata_integration/adapters/bundle.py",
        "integration-staging/src/examdata_integration/adapters/cie.py",
        "integration-staging/src/examdata_integration/adapters/edexcel.py",
        "integration-staging/fixtures/synthetic/adapters/cie-index-adapters.json",
        "integration-staging/fixtures/synthetic/adapters/edexcel-index-adapters.json",
        "integration-staging/fixtures/synthetic/adapters/PROVENANCE.json",
        "integration-staging/fixtures/synthetic/adapters/README.md",
        "integration-staging/tools/a07_capture_adapter_fixtures.py",
        "integration-staging/tools/a07_probe_adapters.py",
        "integration-staging/tools/a07_final_checks.py",
        "integration-staging/tools/a07_close_patch.py",
        "integration-staging/tests/test_adapters_reader.py",
        "integration-staging/tests/test_adapters_documents.py",
        "integration-staging/tests/test_adapters_answers.py",
        "integration-staging/tests/test_adapters_regions.py",
        "integration-staging/tests/test_adapters_cie.py",
        "integration-staging/tests/test_adapters_edexcel.py",
        "integration-staging/tests/test_adapters_provenance.py",
        "integration-staging/runtime/ledger-patches/A07_close.json",
        "docs/integration/execution/A07_REPORT.md",
        "docs/integration/execution/execution-ledger.json",
        "docs/integration/execution/evidence/A07/adapters_stdout.txt",
        "docs/integration/execution/evidence/A07/pytest_run_stdout.txt",
    ]
    missing_files = [r for r in required if not (WS / r).is_file()]
    emit(f"missing={missing_files}")
    check("artifacts.all_present", not missing_files)

    # ---- 2. adapter probe (re-run; the transcript is read-only evidence) --------
    emit()
    emit("--- 2. adapter probe re-run (transcript is not rewritten) ---")
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
        check("probe.pass", proc.returncode == 0 and "A07_PROBE: PASS" in text
              and "A07_PROBE: FAIL" not in text, f"rc={proc.returncode}")
        check("probe.scenario_count", ok_lines == EXPECTED_PROBE_SCENARIOS
              and not fail_lines, f"ok={ok_lines}")

        stored = EV / "adapters_stdout.txt"
        stored_text = stored.read_text(encoding="utf-8")
        stored_ok = sum(1 for ln in stored_text.splitlines() if ln.startswith("[ok]"))
        emit(f"stored_transcript ok_scenarios={stored_ok} (left untouched)")
        check("probe.transcript_matches", "A07_PROBE: PASS" in stored_text
              and stored_ok == EXPECTED_PROBE_SCENARIOS)
    except Exception as e:  # noqa: BLE001
        check("probe.pass", False, f"exception={e!r}")

    # ---- 3. fixture provenance is fresh -----------------------------------------
    emit()
    emit("--- 3. fixture provenance (capture --check) ---")
    try:
        env = dict(os.environ)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"] = "1"
        proc = subprocess.run([sys.executable, str(CAPTURE), "--check"],
                              cwd=str(STAGING), env=env, capture_output=True, text=True)
        emit(f"exit={proc.returncode} out={proc.stdout.strip()!r}")
        check("provenance.fresh", proc.returncode == 0
              and "A07_PROVENANCE: PASS" in proc.stdout)
    except Exception as e:  # noqa: BLE001
        check("provenance.fresh", False, f"exception={e!r}")

    # ---- 4. fixtures are synthetic ----------------------------------------------
    emit()
    emit("--- 4. adapter fixtures are synthetic ---")
    try:
        fixture_dir = STAGING / "fixtures" / "synthetic" / "adapters"
        fixtures = sorted(p for p in fixture_dir.glob("*.json") if p.name != "PROVENANCE.json")
        kinds = {p.name: json.loads(p.read_text(encoding="utf-8")).get("fixture_kind")
                 for p in fixtures}
        emit(f"fixtures={kinds}")
        check("fixtures.two_synthetic",
              len(fixtures) == 2 and all(v == "synthetic" for v in kinds.values()))
        manifest = load_json(fixture_dir / "PROVENANCE.json")
        check("fixtures.provenance_entries", manifest.get("summary", {}).get("entries") == 2
              and len(manifest.get("entries", [])) == 2)
        # no fixture may carry a 'verified' status
        check("fixtures.not_verified",
              all(json.loads(p.read_text(encoding="utf-8")).get("verification", {})
                  .get("status") == "synthetic" for p in fixtures))
    except Exception as e:  # noqa: BLE001
        check("fixtures.two_synthetic", False, f"exception={e!r}")

    # ---- 5. pytest transcript ---------------------------------------------------
    emit()
    emit("--- 5. staged suite transcript ---")
    try:
        text = (EV / "pytest_run_stdout.txt").read_text(encoding="utf-8")
        ok = "326 passed" in text and " failed" not in text
        emit(f"'326 passed'={ok}")
        check("pytest.transcript_326_passed", ok)
    except Exception as e:  # noqa: BLE001
        check("pytest.transcript_326_passed", False, f"exception={e!r}")

    # ---- 6. ledger state --------------------------------------------------------
    emit()
    emit("--- 6. ledger state ---")
    led: dict = {}
    by_id: dict = {}
    try:
        led = load_json(EXEC / "execution-ledger.json")
        by_id = {t.get("task_id"): t for t in led.get("tasks", [])}
        a07 = by_id.get("A07", {})
        codes = a07.get("exit_codes", [])
        nonzero = [c for c in codes if c not in (0, None)]
        failures = a07.get("failures") or []
        emit(f"A07 exit_codes={codes} nonzero={nonzero} failures={len(failures)}")
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
        emit(f"A07_status={a07.get('status')} gates={len(gates)} open={open_gates}")
        check("ledger.count_unique_27",
              len(ids) == 27 and len(set(ids)) == 27
              and not [t for t in EXPECTED_TASK_IDS if t not in ids]
              and not [t for t in ids if t not in EXPECTED_TASK_IDS])
        check("ledger.a07_staged_pass", a07.get("status") == "staged_pass",
              f"A07={a07.get('status')}")
        check("ledger.no_merged_pass", "merged_pass" not in statuses)
        check("ledger.gates_closed", len(gates) == 7 and not open_gates, f"open={open_gates}")
        expected_roots = [STAGING.as_posix(), EXEC.as_posix()]
        check("ledger.a07_write_roots",
              a07.get("allowed_write_roots") == expected_roots
              and led.get("allowed_write_roots") == expected_roots)
        check("ledger.a07_record_fields",
              bool(a07.get("evidence_paths")) and bool(a07.get("input_hashes"))
              and bool(a07.get("commands")) and bool(a07.get("changed_files"))
              and bool(a07.get("test_results")) and bool(a07.get("remaining_gaps"))
              and (a07.get("next_action") or "").strip() != "")
    except Exception as e:  # noqa: BLE001
        check("ledger.load_and_validate", False, f"exception={e!r}")

    # ---- 7. containment ---------------------------------------------------------
    emit()
    emit("--- 7. containment of the A07 write set ---")
    try:
        a07 = by_id.get("A07", {})
        outside = [f for f in a07.get("changed_files", [])
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

    # ---- 8. sha256 manifest -----------------------------------------------------
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

    # ---- verdict ----------------------------------------------------------------
    emit()
    emit("--- 9. verdict ---")
    failed = [(n, d) for n, ok, d in checks if not ok]
    for n, ok, d in checks:
        emit(f"{n}: {'PASS' if ok else 'FAIL'}{(' (' + d + ')') if d and not ok else ''}")
    ok_all = not failed
    emit(f"A07_FINAL_CHECKS_JSON: {'PASS' if ok_all else 'FAIL'}")
    emit(f"FINAL_CHECKS: {'PASS' if ok_all else 'FAIL'}")

    text = "\n".join(lines) + "\n"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text, encoding="utf-8", newline="\n")
    sys.stdout.write(text)
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
