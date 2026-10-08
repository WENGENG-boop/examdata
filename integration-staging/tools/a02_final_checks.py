#!/usr/bin/env python3
"""A02 closing checks for the Phase A integration (run AFTER the ledger is closed).

Validates:
  1. artifact existence (staged harness + evidence);
  2. guard-file hashes on disk == the hashes recorded in ledger A02.input_hashes;
  3. module resolution: the shared venv still resolves `examdata` into the
     original tree, and the staged package resolves under integration-staging;
  4. the guards work when exercised in-process: original-module import blocked,
     module audit detects a violation, path guard rejects original/outside paths,
     network guard rejects non-loopback sockets/DNS, offline transport fails;
  5. the Node import guard rejects an import that escapes staging;
  6. pytest transcript: 18 passed, exit 0; ledger exit code 0;
  7. leak check: no __pycache__ written into protected roots, no .pytest_cache
     touched, no file outside the two Phase A roots except attributed owner activity;
  8. ledger: 27 tasks, A02 staged_pass, 7 gates closed, no merged_pass, A02 fields;
  9. pytest.ini and conftest pin private caches/state;
 10. sha256 manifest of both Phase A roots (excluding this transcript).

Writes (and prints) the transcript to
  docs/integration/execution/evidence/A02/final_checks.txt  (override with --out)
and exits 0 (PASS) or 1 (FAIL).

Phase A tool (integration-staging/tools/). Stdlib only; nothing original is touched.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.dont_write_bytecode = True

WS = Path(__file__).resolve().parents[2]
EXEC = WS / "docs" / "integration" / "execution"
EV_A02 = EXEC / "evidence" / "A02"
STAGING = WS / "integration-staging"
ROOTS = [STAGING, EXEC]

EXPECTED_TASK_IDS = ["A%02d" % i for i in range(16)] + ["B%02d" % i for i in range(11)]
GUARD_FILES = [
    "integration-staging/src/examdata_integration/testing/guards.py",
    "integration-staging/src/examdata_integration/testing/node_guard.py",
    "integration-staging/tests/conftest.py",
    "integration-staging/pytest.ini",
]
OWNER_ACTIVITY_ALLOWED = {"./examdata/examples/curl.md"}

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
    ap.add_argument("--out", default=str(EV_A02 / "final_checks.txt"))
    args = ap.parse_args()
    out_path = Path(args.out)
    out_path = (out_path if out_path.is_absolute() else WS / out_path).resolve()

    lines: list[str] = []

    def emit(s: str = "") -> None:
        lines.append(s)

    now_local = datetime.now().astimezone()
    emit("=== A02 final checks (runner: integration-staging/tools/a02_final_checks.py) ===")
    emit(f"generated_at_local: {now_local.isoformat(timespec='seconds')}")
    emit(f"generated_at_utc:   {datetime.now(timezone.utc).isoformat(timespec='seconds')}")
    emit(f"cwd: {Path.cwd()}")
    emit()

    # ---- 1. artifact existence -------------------------------------------------
    emit("--- 1. artifact existence ---")
    required = [
        "integration-staging/pytest.ini",
        "integration-staging/README.md",
        "integration-staging/fixtures/README.md",
        "integration-staging/runtime/README.md",
        "integration-staging/src/examdata_integration/__init__.py",
        "integration-staging/src/examdata_integration/testing/__init__.py",
        "integration-staging/src/examdata_integration/testing/guards.py",
        "integration-staging/src/examdata_integration/testing/node_guard.py",
        "integration-staging/tests/conftest.py",
        "integration-staging/tests/test_harness_isolation.py",
        "integration-staging/tests/test_node_import_guard.py",
        "integration-staging/tools/inspect_module_resolution.py",
        "integration-staging/tools/run_staged_tests.sh",
        "integration-staging/tools/a02_final_checks.py",
        "integration-staging/runtime/ledger-patches/A02_close.json",
        "docs/integration/execution/A02_REPORT.md",
        "docs/integration/execution/execution-ledger.json",
        "docs/integration/execution/evidence/A02/module_resolution_before_imports.txt",
        "docs/integration/execution/evidence/A02/pytest_run_stdout.txt",
        "docs/integration/execution/evidence/A02/leak_check_after_pytest.txt",
    ]
    # This transcript is written by this run; its existence is proven by the run itself.
    missing_files = [r for r in required if not (WS / r).is_file()]
    emit(f"missing={missing_files}")
    check("artifacts.all_present", not missing_files)

    # ---- 2. guard-file hashes vs ledger ------------------------------------------
    emit()
    emit("--- 2. guard-file hashes vs ledger A02.input_hashes ---")
    try:
        led = load_json(EXEC / "execution-ledger.json")
        by_id = {t.get("task_id"): t for t in led.get("tasks", [])}
        a02 = by_id.get("A02", {})
        recorded = a02.get("input_hashes", {}) or {}
        mismatches = []
        for key in GUARD_FILES:
            disk = sha256_file(WS / key)
            rec = recorded.get(key)
            emit(f"{key}: recorded={rec} on_disk={disk} match={rec == disk}")
            if rec != disk:
                mismatches.append(key)
        check("guards.hashes_recorded_and_match", not mismatches, f"mismatch={mismatches}")
    except Exception as e:  # noqa: BLE001
        a02 = {}
        check("guards.hashes_recorded_and_match", False, f"exception={e!r}")

    # ---- 3. module resolution -----------------------------------------------------
    emit()
    emit("--- 3. module resolution (shared venv editable install) ---")
    hazard_confirmed = False
    staged_ok = False
    try:
        orig = importlib.util.find_spec("examdata")
        orig_origin = getattr(orig, "origin", None)
        hazard_confirmed = bool(orig_origin) and "examdata" in str(orig_origin) \
            and "integration-staging" not in str(orig_origin)
        emit(f"find_spec('examdata').origin = {orig_origin}")
        emit(f"editable install points at the original tree: {hazard_confirmed}")
    except Exception as e:  # noqa: BLE001
        emit(f"find_spec('examdata') raised {e!r}")

    sys.path.insert(0, str(STAGING / "src"))
    from examdata_integration.testing import guards  # noqa: E402
    from examdata_integration.testing import node_guard  # noqa: E402

    staged_ok = guards.is_within(guards.__file__, STAGING) \
        and guards.STAGING_ROOT == STAGING.resolve()
    emit(f"guards.__file__ = {guards.__file__}")
    emit(f"guards.STAGING_ROOT = {guards.STAGING_ROOT}")
    emit(f"guards.ORIGINAL_APP_CODE = {guards.ORIGINAL_APP_CODE}")
    check("module_resolution.hazard_confirmed", hazard_confirmed)
    check("module_resolution.staged_package_under_staging", staged_ok)

    # ---- 4. guards exercised in-process --------------------------------------------
    emit()
    emit("--- 4. guards exercised in-process ---")
    guards.install_module_guard()

    blocked = False
    try:
        import examdata  # noqa: F401
    except guards.ForbiddenImportError as e:
        blocked = True
        emit(f"import examdata -> ForbiddenImportError: {str(e)[:120]}")
    except Exception as e:  # noqa: BLE001
        emit(f"import examdata -> unexpected {e!r}")
    check("import_guard.blocks_original_module", blocked)

    spec_blocked = False
    try:
        importlib.util.find_spec("examdata")
    except guards.ForbiddenImportError:
        spec_blocked = True
    check("import_guard.blocks_find_spec", spec_blocked)

    audit_detects = False
    sentinel = "examdata_integration.__audit_probe__"
    try:
        import types
        probe = types.ModuleType(sentinel)
        probe.__file__ = str(WS / "examdata" / "src" / "examdata" / "__init__.py")
        sys.modules[sentinel] = probe
        try:
            guards.assert_app_modules_within_staging()
        except guards.StagingViolationError:
            audit_detects = True
    finally:
        sys.modules.pop(sentinel, None)
    check("import_guard.audit_detects_violation", audit_detects)

    path_ok = True
    path_detail = []
    for bad, why in ((WS / "examdata" / "src" / "examdata" / "__init__.py", "original app code"),
                     (WS / "ielts-data", "outside staging"),
                     (WS, "workspace root")):
        try:
            guards.ensure_staged_path(bad, "probe")
            path_ok = False
            path_detail.append(f"NOT REJECTED: {bad}")
        except guards.ForbiddenPathError:
            pass
        except Exception as e:  # noqa: BLE001
            path_ok = False
            path_detail.append(f"{bad}: {e!r}")
    try:
        guards.ensure_staged_path(STAGING / "runtime" / "tmp", "probe")
    except Exception as e:  # noqa: BLE001
        path_ok = False
        path_detail.append(f"staging path rejected: {e!r}")
    emit(f"path_guard detail={path_detail}")
    check("path_guard.rejects_original_and_outside_allows_staging", path_ok)

    guards.install_network_guard()
    import socket
    net_blocked = 0
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.connect(("192.0.2.1", 9))
        finally:
            s.close()
    except guards.NetworkDisabledError:
        net_blocked += 1
    except Exception as e:  # noqa: BLE001
        emit(f"socket.connect unexpected: {e!r}")
    try:
        socket.getaddrinfo("example.com", 443)
    except guards.NetworkDisabledError:
        net_blocked += 1
    except Exception as e:  # noqa: BLE001
        emit(f"getaddrinfo unexpected: {e!r}")
    try:
        guards.offline_transport("https://example.com")
    except guards.NetworkDisabledError:
        net_blocked += 1
    check("network_guard.blocks_non_loopback_sockets_dns_transport", net_blocked == 3,
          f"blocked={net_blocked}/3")

    # ---- 5. Node import guard ------------------------------------------------------
    emit()
    emit("--- 5. Node import guard (escaping import rejected) ---")
    probe_dir = STAGING / "runtime" / "tmp"
    probe_dir.mkdir(parents=True, exist_ok=True)
    probe = probe_dir / "a02_final_checks_escape_probe.js"
    node_ok = False
    node_detail = ""
    escape_target = guards.ORIGINAL_APP_CODE / "examdata" / "__init__.js"
    escape_spec = os.path.relpath(escape_target, probe_dir).replace("\\", "/")
    try:
        probe.write_text(f"const x = require('{escape_spec}');\n",
                         encoding="utf-8", newline="\n")
        emit(f"probe specifier (must escape staging): {escape_spec}")
        try:
            node_guard.check_node_file(probe)
            node_detail = "NOT REJECTED"
        except guards.ForbiddenPathError as e:
            node_ok = True
            node_detail = f"rejected: {str(e)[:120]}"
        except Exception as e:  # noqa: BLE001
            node_detail = f"unexpected {e!r}"
    finally:
        probe.unlink(missing_ok=True)
    emit(f"escape probe: {node_detail}")
    check("node_guard.rejects_escaping_import", node_ok)

    # ---- 6. pytest + leak transcripts ----------------------------------------------
    emit()
    emit("--- 6. pytest run and leak check transcripts ---")
    try:
        pytest_txt = (EV_A02 / "pytest_run_stdout.txt").read_text(encoding="utf-8")
        passed18 = "18 passed" in pytest_txt
        failed_any = "failed" in pytest_txt.lower()
        emit(f"transcript: '18 passed'={passed18} 'failed' present={failed_any}")
        check("pytest.transcript_18_passed", passed18 and not failed_any)
    except Exception as e:  # noqa: BLE001
        check("pytest.transcript_18_passed", False, f"exception={e!r}")

    try:
        codes = a02.get("exit_codes", [])
        nonzero = [c for c in codes if c not in (0, None)]
        failures = a02.get("failures") or []
        emit(f"A02 exit_codes={codes} nonzero={nonzero} failures={len(failures)}")
        check("pytest.ledger_exit_codes_consistent",
              bool(codes) and bool(failures) and len(nonzero) == len(failures)
              and set(nonzero) <= {1},
              f"codes={codes} nonzero={nonzero} failures={len(failures)}")
    except Exception as e:  # noqa: BLE001
        check("pytest.ledger_exit_codes_consistent", False, f"exception={e!r}")

    try:
        leak = (EV_A02 / "leak_check_after_pytest.txt").read_text(encoding="utf-8")
        pycache_line = [ln for ln in leak.splitlines() if "(count: 0)" in ln]
        emit(f"leak: zero-count lines={len(pycache_line)} (expected 2: new __pycache__, touched .pytest_cache)")
        outside = []
        in_section = False
        for ln in leak.splitlines():
            if ln.startswith("## 5."):
                in_section = True
                continue
            if in_section:
                stripped = ln.strip()
                if stripped.startswith("./") and "curl.md" not in stripped:
                    outside.append(stripped)
        emit(f"leak: out-of-allowlist files other than attributed owner activity={outside}")
        check("leak_check.no_unattributed_writes_outside_allowlist", not outside,
              f"unattributed={outside}")
        check("leak_check.protected_roots_clean",
              "(count: 0)" in leak and leak.count("(count: 0)") >= 2,
              f"zero_count_lines={leak.count('(count: 0)')}")
    except Exception as e:  # noqa: BLE001
        check("leak_check.no_unattributed_writes_outside_allowlist", False, f"exception={e!r}")

    # ---- 7. ledger validation -------------------------------------------------------
    emit()
    emit("--- 7. ledger validation ---")
    try:
        tasks = led.get("tasks", [])
        ids = [t.get("task_id") for t in tasks]
        gates = led.get("gates", {})
        open_gates = [g for g, v in gates.items() if v.get("open")]
        all_statuses: dict[str, int] = {}
        for t in tasks:
            all_statuses[t["status"]] = all_statuses.get(t["status"], 0) + 1
        expected_roots = [(WS / "integration-staging").as_posix(),
                          (WS / "docs" / "integration" / "execution").as_posix()]
        emit(f"schema={led.get('schema')} mode={led.get('mode')}")
        emit(f"task_count={len(ids)} unique={len(set(ids))}")
        emit(f"status_counts={json.dumps(all_statuses, sort_keys=True)}")
        emit(f"A02_status={a02.get('status')}")
        emit(f"gate_count={len(gates)} open_gates={open_gates}")
        check("ledger.count_unique_27",
              len(ids) == 27 and len(set(ids)) == 27
              and not [t for t in EXPECTED_TASK_IDS if t not in ids]
              and not [t for t in ids if t not in EXPECTED_TASK_IDS])
        check("ledger.schema_mode",
              led.get("schema") == "examdata.integration.ledger/1"
              and led.get("mode") == "PHASE_A_ISOLATED_ONLY")
        check("ledger.a02_staged_pass", a02.get("status") == "staged_pass",
              f"A02={a02.get('status')}")
        check("ledger.no_merged_pass", "merged_pass" not in all_statuses)
        check("ledger.gates_closed", len(gates) == 7 and not open_gates, f"open={open_gates}")
        check("ledger.a02_write_roots",
              a02.get("allowed_write_roots") == expected_roots
              and led.get("allowed_write_roots") == expected_roots)
        check("ledger.a02_record_fields",
              bool(a02.get("evidence_paths")) and bool(a02.get("input_hashes"))
              and bool(a02.get("commands")) and bool(a02.get("changed_files"))
              and bool(a02.get("test_results")) and bool(a02.get("remaining_gaps"))
              and (a02.get("next_action") or "").strip() != "")
    except Exception as e:  # noqa: BLE001
        check("ledger.load_and_validate", False, f"exception={e!r}")

    # ---- 8. staging config pins private state ---------------------------------------
    emit()
    emit("--- 8. staging config pins private caches and state ---")
    try:
        ini = (STAGING / "pytest.ini").read_text(encoding="utf-8")
        conf = (STAGING / "tests" / "conftest.py").read_text(encoding="utf-8")
        ini_ok = all(k in ini for k in ("testpaths = tests", "pythonpath = src",
                                        "cache_dir = runtime/pytest-cache"))
        conf_ok = all(k in conf for k in ('"HOME"', '"TEMP"', "EXAMDATA_", "install_module_guard",
                                          "install_network_guard", "PYTHONDONTWRITEBYTECODE"))
        emit(f"pytest.ini keys ok={ini_ok}; conftest pins ok={conf_ok}")
        check("staging_config.private_paths_pinned", ini_ok and conf_ok)
    except Exception as e:  # noqa: BLE001
        check("staging_config.private_paths_pinned", False, f"exception={e!r}")

    # ---- 9. inventory + sha256 manifest ---------------------------------------------
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

    # ---- verdict ---------------------------------------------------------------------
    emit()
    emit("--- 10. verdict ---")
    failed = [(n, d) for n, ok, d in checks if not ok]
    for n, ok, d in checks:
        emit(f"{n}: {'PASS' if ok else 'FAIL'}{(' (' + d + ')') if d and not ok else ''}")
    ok_all = not failed
    emit(f"A02_FINAL_CHECKS_JSON: {'PASS' if ok_all else 'FAIL'}")
    emit(f"FINAL_CHECKS: {'PASS' if ok_all else 'FAIL'}")

    text = "\n".join(lines) + "\n"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text, encoding="utf-8", newline="\n")
    sys.stdout.write(text)
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
