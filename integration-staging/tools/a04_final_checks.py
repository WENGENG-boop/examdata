#!/usr/bin/env python3
"""A04 closing checks for the Phase A integration (run AFTER the ledger is closed).

Validates:
  1. artifact existence;
  2. the schema generator's --check mode is byte-stable (CHECK: PASS 30/30);
  3. the round-trip transcript reports ROUNDTRIP: PASS and carries no coverage
     validate() problem (the self-consistency fix);
  4. every generated schema uses only supported keywords, and every generated
     example validates against its schema;
  5. identity-keys.json mirrors canonical.IDENTITY_KEYS exactly, and
     quality-transitions.json mirrors the transition table;
  6. the staged suite transcript reports 75 passed with no failures, and the
     ledger exit codes agree with the recorded failures;
  7. containment: every A04 changed file is inside a Phase A writable root, and
     no __pycache__/.pyc leaked under the staged source or tests;
  8. ledger: 27 tasks, A04 staged_pass, 7 gates closed, no merged_pass, A04 fields;
  9. sha256 manifest of both Phase A roots (excluding this transcript).

Writes (and prints) the transcript to
  docs/integration/execution/evidence/A04/final_checks.txt  (override with --out)
and exits 0 (PASS) or 1 (FAIL).

Phase A tool (integration-staging/tools/). Stdlib only; nothing original is modified.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.dont_write_bytecode = True

WS = Path(__file__).resolve().parents[2]
EXEC = WS / "docs" / "integration" / "execution"
EV = EXEC / "evidence" / "A04"
STAGING = WS / "integration-staging"
SRC = STAGING / "src"
SCHEMA_DIR = STAGING / "contracts" / "schema"
EXAMPLES = STAGING / "contracts" / "examples"
CONTRACTS = STAGING / "contracts"
GENERATOR = STAGING / "tools" / "a04_generate_schemas.py"
ROOTS = [STAGING, EXEC]

sys.path.insert(0, str(SRC))

EXPECTED_TASK_IDS = ["A%02d" % i for i in range(16)] + ["B%02d" % i for i in range(11)]
ROOT_STRINGS = [STAGING.relative_to(WS).as_posix() + "/", EXEC.relative_to(WS).as_posix() + "/"]

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


def is_within(child: Path, parent: Path) -> bool:
    c, p = os.path.normcase(os.path.realpath(child)), os.path.normcase(os.path.realpath(parent))
    return c == p or c.startswith(p + os.sep)


def schema_filename(schema_id: str) -> str:
    parts = [p for p in schema_id.split("/") if not p.isdigit()]
    return "-".join(parts) + ".schema.json"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(EV / "final_checks.txt"))
    args = ap.parse_args()
    out_path = Path(args.out)
    out_path = (out_path if out_path.is_absolute() else WS / out_path).resolve()

    lines: list[str] = []

    def emit(s: str = "") -> None:
        lines.append(s)

    emit("=== A04 final checks (runner: integration-staging/tools/a04_final_checks.py) ===")
    emit(f"generated_at_local: {datetime.now().astimezone().isoformat(timespec='seconds')}")
    emit(f"generated_at_utc:   {datetime.now(timezone.utc).isoformat(timespec='seconds')}")
    emit(f"cwd: {Path.cwd()}")
    emit()

    from examdata_integration.contracts import canonical, quality
    from examdata_integration.contracts.jsonschema_lite import unsupported_keywords, validate

    # ---- 1. artifact existence -------------------------------------------------
    emit("--- 1. artifact existence ---")
    required = [
        "integration-staging/src/examdata_integration/contracts/__init__.py",
        "integration-staging/src/examdata_integration/contracts/enums.py",
        "integration-staging/src/examdata_integration/contracts/canonical.py",
        "integration-staging/src/examdata_integration/contracts/base.py",
        "integration-staging/src/examdata_integration/contracts/models.py",
        "integration-staging/src/examdata_integration/contracts/ids.py",
        "integration-staging/src/examdata_integration/contracts/quality.py",
        "integration-staging/src/examdata_integration/contracts/completeness.py",
        "integration-staging/src/examdata_integration/contracts/jsonschema_lite.py",
        "integration-staging/contracts/identity-keys.json",
        "integration-staging/contracts/quality-transitions.json",
        "integration-staging/contracts/examples/INDEX.json",
        "integration-staging/tools/a04_generate_schemas.py",
        "integration-staging/tools/a04_roundtrip_fixtures.py",
        "integration-staging/tools/a04_final_checks.py",
        "integration-staging/tests/test_contracts_identity.py",
        "integration-staging/tests/test_contracts_quality.py",
        "integration-staging/tests/test_contracts_completeness.py",
        "integration-staging/tests/test_contracts_schemas.py",
        "integration-staging/runtime/ledger-patches/A04_close.json",
        "docs/integration/execution/A04_IDENTITY_DECISION.md",
        "docs/integration/execution/A04_REPORT.md",
        "docs/integration/execution/execution-ledger.json",
        "docs/integration/execution/evidence/A04/roundtrip_stdout.txt",
        "docs/integration/execution/evidence/A04/pytest_run_stdout.txt",
    ]
    missing_files = [r for r in required if not (WS / r).is_file()]
    emit(f"missing={missing_files}")
    check("artifacts.all_present", not missing_files)

    # ---- 2. generator --check ----------------------------------------------------
    emit()
    emit("--- 2. generator --check (byte-stable) ---")
    try:
        env = dict(os.environ)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        proc = subprocess.run([sys.executable, str(GENERATOR), "--check"],
                              cwd=str(STAGING), env=env, capture_output=True, text=True)
        emit(f"exit={proc.returncode}")
        emit(proc.stdout.strip()[-200:])
        check("generator.check_pass",
              proc.returncode == 0 and "CHECK: PASS (30/30)" in proc.stdout,
              f"rc={proc.returncode}")
    except Exception as e:  # noqa: BLE001
        check("generator.check_pass", False, f"exception={e!r}")

    # ---- 3. round-trip transcript -----------------------------------------------
    emit()
    emit("--- 3. round-trip transcript ---")
    try:
        text = (EV / "roundtrip_stdout.txt").read_text(encoding="utf-8")
        pass_lines = sum(1 for ln in text.splitlines() if ln.endswith(": PASS"))
        coverage_problems = [ln for ln in text.splitlines()
                             if "validate " in ln and "coverage/1" in ln and "no problems" not in ln]
        emit(f"pass_lines={pass_lines} coverage_problems={coverage_problems}")
        check("roundtrip.pass", "ROUNDTRIP: PASS" in text and "ROUNDTRIP: FAIL" not in text)
        check("roundtrip.no_coverage_validate_problem", not coverage_problems)
        check("roundtrip.checks_recorded", pass_lines >= 61, f"pass_lines={pass_lines}")
    except Exception as e:  # noqa: BLE001
        check("roundtrip.pass", False, f"exception={e!r}")

    # ---- 4. schemas + examples ---------------------------------------------------
    emit()
    emit("--- 4. schema subset + example validation ---")
    try:
        schemas = sorted(SCHEMA_DIR.glob("*.schema.json"))
        bad_keywords = {}
        for s in schemas:
            problems = unsupported_keywords(load_json(s))
            if problems:
                bad_keywords[s.name] = problems
        emit(f"schemas={len(schemas)} unsupported={bad_keywords}")
        check("schemas.count_28", len(schemas) == 28, f"count={len(schemas)}")
        check("schemas.only_supported_keywords", not bad_keywords)

        index = load_json(EXAMPLES / "INDEX.json")
        failures, checked = [], 0
        for entry in index["examples"]:
            example = load_json(EXAMPLES / entry["file"])
            if entry["schema"] == "identity-registry/1":
                continue
            schema = load_json(SCHEMA_DIR / schema_filename(entry["schema"]))
            problems = validate(example, schema)
            checked += 1
            if problems:
                failures.append(f"{entry['file']}: {problems}")
        emit(f"examples={len(index['examples'])} validated={checked} failures={failures}")
        check("examples.validate_against_schemas", not failures)
        check("examples.entity_kinds_covered",
              {"container/1", "course/1", "question/1", "answer/1", "asset/1", "coverage/1",
               "region/1", "timetable-event/1", "timetable-window/1", "syllabus/1", "tag/1",
               "material/1", "examination-system/1", "job-status/1"}
              <= {e["schema"] for e in index["examples"]})
    except Exception as e:  # noqa: BLE001
        check("schemas.only_supported_keywords", False, f"exception={e!r}")

    # ---- 5. generated mirrors ----------------------------------------------------
    emit()
    emit("--- 5. identity-keys.json and quality-transitions.json mirrors ---")
    try:
        keys = load_json(CONTRACTS / "identity-keys.json")
        expected_kinds = {
            kind.value: {
                "prefix": canonical.ID_TYPE_PREFIX[kind],
                "identity_keys": list(canonical.IDENTITY_KEYS[kind]),
            }
            for kind in canonical.EntityKind
        }
        emit(f"kinds={len(keys['kinds'])} digest_bytes={keys['normalisation']['digest_bytes']}")
        check("identity_keys.mirror", keys["kinds"] == expected_kinds)
        check("identity_keys.digest_and_sentinels",
              keys["normalisation"]["digest_bytes"] == canonical.DIGEST_BYTES
              and keys["normalisation"]["absent_encoding"] == "\\x00"
              and keys["normalisation"]["explicit_unknown_encoding"] == "\\x01")

        qt = load_json(CONTRACTS / "quality-transitions.json")
        emit(f"transitions={len(qt['transitions'])} forbidden={len(qt['forbidden_basis'])}")
        check("quality_transitions.mirror",
              qt["transitions"] == quality.transition_table()
              and qt["forbidden_basis"] == dict(quality.FORBIDDEN_BASIS))
    except Exception as e:  # noqa: BLE001
        check("identity_keys.mirror", False, f"exception={e!r}")

    # ---- 6. pytest transcript + ledger exit codes --------------------------------
    emit()
    emit("--- 6. staged suite transcript and ledger exit codes ---")
    try:
        text = (EV / "pytest_run_stdout.txt").read_text(encoding="utf-8")
        ok75 = "75 passed" in text and "failed" not in text.lower()
        emit(f"'75 passed'={ok75}")
        check("pytest.transcript_75_passed", ok75)
    except Exception as e:  # noqa: BLE001
        check("pytest.transcript_75_passed", False, f"exception={e!r}")

    try:
        led = load_json(EXEC / "execution-ledger.json")
        by_id = {t.get("task_id"): t for t in led.get("tasks", [])}
        a04 = by_id.get("A04", {})
        codes = a04.get("exit_codes", [])
        nonzero = [c for c in codes if c not in (0, None)]
        failures = a04.get("failures") or []
        emit(f"A04 exit_codes={codes} nonzero={nonzero} failures={len(failures)}")
        check("pytest.ledger_exit_codes_consistent",
              bool(codes) and len(nonzero) == len(failures) and set(nonzero) <= {1},
              f"codes={codes} nonzero={nonzero} failures={len(failures)}")
    except Exception as e:  # noqa: BLE001
        check("pytest.ledger_exit_codes_consistent", False, f"exception={e!r}")

    # ---- 7. containment ----------------------------------------------------------
    emit()
    emit("--- 7. containment of the A04 write set ---")
    try:
        a04 = by_id.get("A04", {})
        outside = [f for f in a04.get("changed_files", [])
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
        emit(f"task_count={len(ids)} unique={len(set(ids))} statuses={json.dumps(all_statuses, sort_keys=True)}")
        emit(f"A04_status={a04.get('status')} gates={len(gates)} open={open_gates}")
        check("ledger.count_unique_27",
              len(ids) == 27 and len(set(ids)) == 27
              and not [t for t in EXPECTED_TASK_IDS if t not in ids]
              and not [t for t in ids if t not in EXPECTED_TASK_IDS])
        check("ledger.a04_staged_pass", a04.get("status") == "staged_pass", f"A04={a04.get('status')}")
        check("ledger.no_merged_pass", "merged_pass" not in all_statuses)
        check("ledger.gates_closed", len(gates) == 7 and not open_gates, f"open={open_gates}")
        check("ledger.a04_write_roots",
              a04.get("allowed_write_roots") == expected_roots
              and led.get("allowed_write_roots") == expected_roots)
        check("ledger.a04_record_fields",
              bool(a04.get("evidence_paths")) and bool(a04.get("input_hashes"))
              and bool(a04.get("commands")) and bool(a04.get("changed_files"))
              and bool(a04.get("test_results")) and bool(a04.get("remaining_gaps"))
              and (a04.get("next_action") or "").strip() != "")
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
    emit(f"A04_FINAL_CHECKS_JSON: {'PASS' if ok_all else 'FAIL'}")
    emit(f"FINAL_CHECKS: {'PASS' if ok_all else 'FAIL'}")

    text = "\n".join(lines) + "\n"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text, encoding="utf-8", newline="\n")
    sys.stdout.write(text)
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
