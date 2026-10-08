#!/usr/bin/env python3
"""A05 closing checks for the Phase A integration (run AFTER the ledger is closed).

Validates:
  1. artifact existence (provider package, A05 tools/tests, report, patch, evidence);
  2. the dispatch probe re-runs offline and reports A05_PROBE: PASS (20/20),
     writing its transcript to evidence/A05/dispatch_stdout.txt;
  3. the provider layer's core semantics hold in-process: capability filtering
     precedes dispatch, an unsupported capability is not an empty success, an
     uninterpretable filter is rejected, and error precedence is deterministic;
  4. a fixture that is not labelled synthetic is refused;
  5. exception details are path-redacted (the correction made in this packet);
  6. the staged suite transcript reports 141 passed with no failures, and the
     ledger exit codes agree with the recorded failures;
  7. containment: every A05 changed file is inside a Phase A writable root, and
     no __pycache__/.pyc leaked under the staged source or tests;
  8. ledger: 27 tasks, A05 staged_pass, 7 gates closed, no merged_pass, A05 fields;
  9. sha256 manifest of both Phase A roots (excluding this transcript).

Writes (and prints) the transcript to
  docs/integration/execution/evidence/A05/final_checks.txt  (override with --out)
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
import tempfile
from datetime import datetime, timezone
from pathlib import Path

sys.dont_write_bytecode = True

WS = Path(__file__).resolve().parents[2]
EXEC = WS / "docs" / "integration" / "execution"
EV = EXEC / "evidence" / "A05"
STAGING = WS / "integration-staging"
SRC = STAGING / "src"
FIXTURES = STAGING / "fixtures" / "synthetic"
PROBE = STAGING / "tools" / "a05_probe_dispatch.py"
ROOTS = [STAGING, EXEC]

sys.path.insert(0, str(SRC))

EXPECTED_TASK_IDS = ["A%02d" % i for i in range(16)] + ["B%02d" % i for i in range(11)]
ROOT_STRINGS = [STAGING.relative_to(WS).as_posix() + "/", EXEC.relative_to(WS).as_posix() + "/"]
EXPECTED_PROBE_SCENARIOS = 20

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

    emit("=== A05 final checks (runner: integration-staging/tools/a05_final_checks.py) ===")
    emit(f"generated_at_local: {datetime.now().astimezone().isoformat(timespec='seconds')}")
    emit(f"generated_at_utc:   {datetime.now(timezone.utc).isoformat(timespec='seconds')}")
    emit(f"cwd: {Path.cwd()}")
    emit()

    from examdata_integration.providers import (
        Capability,
        CIEIndexProvider,
        FailingProvider,
        NullProvider,
        ProviderRegistry,
        ProviderResult,
    )

    # ---- 1. artifact existence -------------------------------------------------
    emit("--- 1. artifact existence ---")
    required = [
        "integration-staging/src/examdata_integration/providers/__init__.py",
        "integration-staging/src/examdata_integration/providers/capabilities.py",
        "integration-staging/src/examdata_integration/providers/results.py",
        "integration-staging/src/examdata_integration/providers/protocol.py",
        "integration-staging/src/examdata_integration/providers/registry.py",
        "integration-staging/src/examdata_integration/providers/fixtures.py",
        "integration-staging/tools/a05_probe_dispatch.py",
        "integration-staging/tools/a05_final_checks.py",
        "integration-staging/tools/a05_close_patch.py",
        "integration-staging/tests/test_providers_registry.py",
        "integration-staging/tests/test_providers_fixtures.py",
        "integration-staging/runtime/ledger-patches/A05_close.json",
        "docs/integration/execution/A05_REPORT.md",
        "docs/integration/execution/execution-ledger.json",
        "docs/integration/execution/evidence/A05/pytest_run_stdout.txt",
    ]
    missing_files = [r for r in required if not (WS / r).is_file()]
    emit(f"missing={missing_files}")
    check("artifacts.all_present", not missing_files)

    # ---- 2. dispatch probe (re-run; the transcript is read-only evidence) -------
    emit()
    emit("--- 2. dispatch probe re-run (transcript is not rewritten) ---")
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
        check("probe.pass", proc.returncode == 0 and "A05_PROBE: PASS" in text
              and "A05_PROBE: FAIL" not in text, f"rc={proc.returncode}")
        check("probe.scenario_count", ok_lines == EXPECTED_PROBE_SCENARIOS
              and not fail_lines, f"ok={ok_lines}")

        # the transcript is hashed into the ledger at close time, so it must not be
        # mutated afterwards: verify the stored transcript, and only create it when
        # it is genuinely absent (first run before the ledger closed).
        stored = EV / "dispatch_stdout.txt"
        if stored.is_file():
            stored_text = stored.read_text(encoding="utf-8")
            stored_ok = sum(1 for ln in stored_text.splitlines() if ln.startswith("[ok]"))
            emit(f"stored_transcript ok_scenarios={stored_ok} (left untouched)")
            check("probe.transcript_matches", "A05_PROBE: PASS" in stored_text
                  and stored_ok == EXPECTED_PROBE_SCENARIOS)
        else:
            EV.mkdir(parents=True, exist_ok=True)
            stored.write_text(text, encoding="utf-8", newline="\n")
            check("probe.transcript_matches", "A05_PROBE: PASS" in text)
    except Exception as e:  # noqa: BLE001
        check("probe.pass", False, f"exception={e!r}")

    # ---- 3. provider semantics in-process ---------------------------------------
    emit()
    emit("--- 3. provider semantics (in-process) ---")
    try:
        class _Spy:
            def __init__(self, provider_id, capabilities):
                from examdata_integration.providers import ProviderDescriptor
                from examdata_integration.contracts.enums import ExamSystem
                self.calls = []
                self.descriptor = ProviderDescriptor(
                    provider_id=provider_id, exam_system=ExamSystem.CIE,
                    display_name="spy", capabilities=frozenset(capabilities))

            def query(self, capability, *, filters=None, target=None):
                self.calls.append(Capability.coerce(capability))
                return ProviderResult.success(self.descriptor.provider_id,
                                              Capability.coerce(capability).value)

        reg = ProviderRegistry()
        spy = _Spy("spy", (Capability.DISCOVERY,))
        reg.register(spy)
        unsupported = reg.dispatch(Capability.COURSES, provider_ids=["spy"])
        check("semantics.capability_filtering_precedes_dispatch",
              unsupported.status == "error"
              and unsupported.error["code"] == "unsupported_capability"
              and spy.calls == [])
        check("semantics.unsupported_is_not_empty_success",
              unsupported.items == [] and unsupported.error is not None)

        reg2 = ProviderRegistry()
        spy2 = _Spy("spy2", (Capability.QUESTIONS,))
        reg2.register(spy2)
        rejected = reg2.dispatch(Capability.QUESTIONS, provider_ids=["spy2"],
                                 filters={"year": 2024})
        check("semantics.uninterpretable_filter_rejected",
              rejected.results[0].status.value == "filter_rejected"
              and rejected.results[0].filter_key == "year"
              and spy2.calls == [])

        reg3 = ProviderRegistry()
        reg3.register(NullProvider())
        empty = reg3.dispatch(Capability.DISCOVERY, provider_ids=["null_fixture"])
        check("semantics.empty_success_is_ok", empty.status == "ok"
              and empty.items == [] and empty.error is None)

        reg4 = ProviderRegistry()
        reg4.register(_Spy("unsupported", (Capability.DISCOVERY,)))
        reg4.register(FailingProvider())
        ranked = reg4.dispatch(Capability.COURSES,
                               provider_ids=["failing_fixture", "unsupported"])
        check("semantics.error_precedence_deterministic",
              ranked.status == "error" and ranked.error["code"] == "unsupported_capability")
    except Exception as e:  # noqa: BLE001
        check("semantics.capability_filtering_precedes_dispatch", False, f"exception={e!r}")

    # ---- 4. synthetic-only admission --------------------------------------------
    emit()
    emit("--- 4. synthetic-only admission ---")
    try:
        with tempfile.TemporaryDirectory(dir=str(STAGING / "runtime" / "tmp")) as td:
            bad = Path(td) / "not-synthetic.json"
            bad.write_text(json.dumps({"fixture_kind": "copied_snapshot"}), encoding="utf-8")
            refused = False
            try:
                CIEIndexProvider(bad)
            except ValueError:
                refused = True
            check("admission.non_synthetic_refused", refused)
        ok_provider = CIEIndexProvider(FIXTURES / "cie" / "cie-index-synthetic.json")
        check("admission.synthetic_accepted", ok_provider.query(Capability.DISCOVERY).ok)
    except Exception as e:  # noqa: BLE001
        check("admission.non_synthetic_refused", False, f"exception={e!r}")

    # ---- 5. exception detail is path-redacted -----------------------------------
    emit()
    emit("--- 5. exception detail redaction ---")
    try:
        detail = ProviderResult.failed("p", "courses",
                                       detail=r"RuntimeError: boom at C:\private\path\secret.db").detail
        emit(f"detail={detail!r}")
        check("redaction.path_removed", "private" not in (detail or "")
              and "secret.db" not in (detail or "") and "<path>" in (detail or ""))
        check("redaction.keeps_type", "RuntimeError" in (detail or ""))
    except Exception as e:  # noqa: BLE001
        check("redaction.path_removed", False, f"exception={e!r}")

    # ---- 6. pytest transcript + ledger exit codes --------------------------------
    emit()
    emit("--- 6. staged suite transcript and ledger exit codes ---")
    try:
        text = (EV / "pytest_run_stdout.txt").read_text(encoding="utf-8")
        ok141 = "141 passed" in text and "failed" not in text.lower()
        emit(f"'141 passed'={ok141}")
        check("pytest.transcript_141_passed", ok141)
    except Exception as e:  # noqa: BLE001
        check("pytest.transcript_141_passed", False, f"exception={e!r}")

    led: dict = {}
    by_id: dict = {}
    try:
        led = load_json(EXEC / "execution-ledger.json")
        by_id = {t.get("task_id"): t for t in led.get("tasks", [])}
        a05 = by_id.get("A05", {})
        codes = a05.get("exit_codes", [])
        nonzero = [c for c in codes if c not in (0, None)]
        failures = a05.get("failures") or []
        emit(f"A05 exit_codes={codes} nonzero={nonzero} failures={len(failures)}")
        check("pytest.ledger_exit_codes_consistent",
              bool(codes) and len(nonzero) == len(failures) and set(nonzero) <= {1},
              f"codes={codes} nonzero={nonzero} failures={len(failures)}")
    except Exception as e:  # noqa: BLE001
        check("pytest.ledger_exit_codes_consistent", False, f"exception={e!r}")

    # ---- 7. containment ----------------------------------------------------------
    emit()
    emit("--- 7. containment of the A05 write set ---")
    try:
        a05 = by_id.get("A05", {})
        outside = [f for f in a05.get("changed_files", [])
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

    # ---- 8. ledger state ---------------------------------------------------------
    emit()
    emit("--- 8. ledger state ---")
    try:
        tasks = led.get("tasks", [])
        ids = [t.get("task_id") for t in tasks]
        gates = led.get("gates", {})
        open_gates = [g for g, v in gates.items() if v.get("open")]
        all_statuses: dict[str, int] = {}
        for t in tasks:
            all_statuses[t["status"]] = all_statuses.get(t["status"], 0) + 1
        expected_roots = [STAGING.as_posix(), EXEC.as_posix()]
        a05 = by_id.get("A05", {})
        emit(f"task_count={len(ids)} unique={len(set(ids))} statuses={json.dumps(all_statuses, sort_keys=True)}")
        emit(f"A05_status={a05.get('status')} gates={len(gates)} open={open_gates}")
        check("ledger.count_unique_27",
              len(ids) == 27 and len(set(ids)) == 27
              and not [t for t in EXPECTED_TASK_IDS if t not in ids]
              and not [t for t in ids if t not in EXPECTED_TASK_IDS])
        check("ledger.a05_staged_pass", a05.get("status") == "staged_pass", f"A05={a05.get('status')}")
        check("ledger.no_merged_pass", "merged_pass" not in all_statuses)
        check("ledger.gates_closed", len(gates) == 7 and not open_gates, f"open={open_gates}")
        check("ledger.a05_write_roots",
              a05.get("allowed_write_roots") == expected_roots
              and led.get("allowed_write_roots") == expected_roots)
        check("ledger.a05_record_fields",
              bool(a05.get("evidence_paths")) and bool(a05.get("input_hashes"))
              and bool(a05.get("commands")) and bool(a05.get("changed_files"))
              and bool(a05.get("test_results")) and bool(a05.get("remaining_gaps"))
              and (a05.get("next_action") or "").strip() != "")
    except Exception as e:  # noqa: BLE001
        check("ledger.load_and_validate", False, f"exception={e!r}")

    # ---- 9. sha256 manifest ------------------------------------------------------
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
    emit(f"A05_FINAL_CHECKS_JSON: {'PASS' if ok_all else 'FAIL'}")
    emit(f"FINAL_CHECKS: {'PASS' if ok_all else 'FAIL'}")

    text = "\n".join(lines) + "\n"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text, encoding="utf-8", newline="\n")
    sys.stdout.write(text)
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
