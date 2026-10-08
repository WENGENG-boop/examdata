#!/usr/bin/env python3
"""Build the A09 ledger close patch (docs/integration/execution/execution-ledger.json).

Computes the input hashes over the true inputs plus the A09 write set (excluding
the closing-checks transcript, which is produced *after* the ledger closes, and
this patch file itself), and emits a JSON object to be merged into the A09 task
record by ``integration-staging/tools/ledger_update.py --patch-file``.

Phase A tool (integration-staging/tools/). Stdlib only.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True

WS = Path(__file__).resolve().parents[2]
STAGING = WS / "integration-staging"
EXEC = WS / "docs" / "integration" / "execution"
OUT = STAGING / "runtime" / "ledger-patches" / "A09_close.json"

ROOTS = [STAGING.as_posix(), EXEC.as_posix()]

INPUTS = [
    "docs/integration/EXECUTOR_PROMPT_EN.md",
    "docs/integration/MASTER_EXECUTION_PLAN_EN.md",
    "docs/integration/ROUTE_INVENTORY_CURRENT.json",
    "docs/PROJECT_STATUS.md",
    "docs/integration/execution/execution-ledger.json",
    "docs/integration/execution/A08_REPORT.md",
    "docs/integration/execution/evidence/A08/final_checks.txt",
    "docs/integration/execution/evidence/A08/pytest_run_stdout.txt",
    # frozen A04 contracts the catalog maps onto (read-only dependency)
    "integration-staging/src/examdata_integration/contracts/models.py",
    "integration-staging/src/examdata_integration/contracts/base.py",
    "integration-staging/src/examdata_integration/contracts/enums.py",
    "integration-staging/src/examdata_integration/contracts/canonical.py",
    "integration-staging/src/examdata_integration/contracts/quality.py",
    "integration-staging/src/examdata_integration/contracts/ids.py",
    # frozen A02-A08 harness the A09 tests run under
    "integration-staging/pytest.ini",
    "integration-staging/tests/conftest.py",
    "integration-staging/tools/run_staged_tests.sh",
    "integration-staging/tools/ledger_update.py",
    "integration-staging/src/examdata_integration/testing/guards.py",
]

WRITE_GLOBS = [
    # A09 source files only: the catalog package is entirely new
    "integration-staging/src/examdata_integration/catalog/__init__.py",
    "integration-staging/src/examdata_integration/catalog/model.py",
    "integration-staging/src/examdata_integration/catalog/store.py",
    "integration-staging/src/examdata_integration/catalog/builder.py",
    "integration-staging/src/examdata_integration/catalog/revision.py",
    "integration-staging/fixtures/synthetic/catalog/*",
    "integration-staging/tools/a09_*.py",
    # A09 test files only: test_catalog_*.py is a new, packet-owned prefix
    "integration-staging/tests/test_catalog_store.py",
    "integration-staging/tests/test_catalog_builder.py",
    "integration-staging/tests/test_catalog_revision.py",
    "integration-staging/runtime/ledger-patches/A09_close.json",
    "docs/integration/execution/A09_REPORT.md",
    "docs/integration/execution/A09_STORE_DECISION.md",
    "docs/integration/execution/evidence/A09/*",
]

# produced only after the ledger closes: listed but never hashed into the patch
POST_CLOSE = {
    "docs/integration/execution/evidence/A09/final_checks.txt",
}

COMMANDS = [
    {"seq": 1, "purpose": "Create the A09 evidence directory.",
     "tool": "Bash",
     "command": "mkdir -p docs/integration/execution/evidence/A09",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0, "evidence": None},
    {"seq": 2, "purpose": "Write the catalog package entry point (docstring only, imports nothing to avoid cycles with frozen modules).",
     "tool": "Write",
     "command": "Write tool: integration-staging/src/examdata_integration/catalog/__init__.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/src/examdata_integration/catalog/__init__.py"},
    {"seq": 3, "purpose": "Write the catalog model: CatalogSource/CatalogEntry/CatalogSnapshot, compute_revision, lossless UNKNOWN encoding.",
     "tool": "Write",
     "command": "Write tool: integration-staging/src/examdata_integration/catalog/model.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/src/examdata_integration/catalog/model.py"},
    {"seq": 4, "purpose": "Write the catalog store: stable IDs, duplicates, collisions, aliases, reference validation, gap mapping.",
     "tool": "Write",
     "command": "Write tool: integration-staging/src/examdata_integration/catalog/store.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/src/examdata_integration/catalog/store.py"},
    {"seq": 5, "purpose": "Write the catalog builder: validate, diff, reject unexplained removals and unsupported quality upgrades.",
     "tool": "Write",
     "command": "Write tool: integration-staging/src/examdata_integration/catalog/builder.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/src/examdata_integration/catalog/builder.py"},
    {"seq": 6, "purpose": "Write the revision publisher: immutable revisions, atomic pointer, compare-and-swap, rollback, cursors.",
     "tool": "Write",
     "command": "Write tool: integration-staging/src/examdata_integration/catalog/revision.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/src/examdata_integration/catalog/revision.py"},
    {"seq": 7, "purpose": "Write the five synthetic catalog mapping fixtures.",
     "tool": "Write",
     "command": "Write tool: integration-staging/fixtures/synthetic/catalog/{catalog-base,catalog-duplicate-native-id,catalog-incomplete-reference,catalog-removal-unexplained,catalog-quality-upgrade-unexplained}-synthetic.json",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/fixtures/synthetic/catalog/"},
    {"seq": 8, "purpose": "Write the fixture-provenance capture tool.",
     "tool": "Write",
     "command": "Write tool: integration-staging/tools/a09_capture_fixtures.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/tools/a09_capture_fixtures.py"},
    {"seq": 9, "purpose": "Generate the A09 fixture provenance manifest (5 entries).",
     "tool": "Bash",
     "command": "examdata/.venv/Scripts/python.exe integration-staging/tools/a09_capture_fixtures.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/fixtures/synthetic/catalog/PROVENANCE.json"},
    {"seq": 10, "purpose": "Inline smoke run of all five fixtures through the builder: each produced exactly the expected problem code (or none).",
     "tool": "Bash",
     "command": "PYTHONPATH=integration-staging/src examdata/.venv/Scripts/python.exe -c \"<inline build of the five catalog fixtures>\"",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/fixtures/synthetic/catalog/"},
    {"seq": 11, "purpose": "Write the three A09 test modules (store, builder, revision).",
     "tool": "Write",
     "command": "Write tool: integration-staging/tests/test_catalog_{store,builder,revision}.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/tests/"},
    {"seq": 12, "purpose": "Run the three A09 test modules to green (43 passed).",
     "tool": "Bash",
     "command": "examdata/.venv/Scripts/python.exe -m pytest integration-staging/tests/test_catalog_store.py integration-staging/tests/test_catalog_builder.py integration-staging/tests/test_catalog_revision.py -q",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/tests/"},
    {"seq": 13, "purpose": "Write the 30-scenario offline catalog probe.",
     "tool": "Write",
     "command": "Write tool: integration-staging/tools/a09_probe_catalog.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/tools/a09_probe_catalog.py"},
    {"seq": 14, "purpose": "First probe run exited 1: the gap-mapping scenario called gap.code.value, but the frozen Gap carries code as a plain string.",
     "tool": "Bash",
     "command": "PYTHONPATH=integration-staging/src examdata/.venv/Scripts/python.exe integration-staging/tools/a09_probe_catalog.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 1,
     "evidence": "integration-staging/tools/a09_probe_catalog.py"},
    {"seq": 15, "purpose": "Fix the probe assertion to compare gap.code to the string value directly.",
     "tool": "Edit",
     "command": "Edit tool: integration-staging/tools/a09_probe_catalog.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/tools/a09_probe_catalog.py"},
    {"seq": 16, "purpose": "Run the probe to green (30/30).",
     "tool": "Bash",
     "command": "examdata/.venv/Scripts/python.exe integration-staging/tools/a09_probe_catalog.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/tools/a09_probe_catalog.py"},
    {"seq": 17, "purpose": "Capture the probe transcript.",
     "tool": "Bash",
     "command": "examdata/.venv/Scripts/python.exe integration-staging/tools/a09_probe_catalog.py > docs/integration/execution/evidence/A09/catalog_stdout.txt",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "docs/integration/execution/evidence/A09/catalog_stdout.txt"},
    {"seq": 18, "purpose": "Run the full staged suite to green (430 passed) and capture the transcript.",
     "tool": "Bash",
     "command": "bash integration-staging/tools/run_staged_tests.sh -q > docs/integration/execution/evidence/A09/pytest_run_stdout.txt",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "docs/integration/execution/evidence/A09/pytest_run_stdout.txt"},
    {"seq": 19, "purpose": "Capture the fixture-provenance check transcript.",
     "tool": "Bash",
     "command": "examdata/.venv/Scripts/python.exe integration-staging/tools/a09_capture_fixtures.py --check > docs/integration/execution/evidence/A09/provenance_check.txt",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "docs/integration/execution/evidence/A09/provenance_check.txt"},
    {"seq": 20, "purpose": "Write the A09 report.",
     "tool": "Write", "command": "Write tool: docs/integration/execution/A09_REPORT.md",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "docs/integration/execution/A09_REPORT.md"},
    {"seq": 21, "purpose": "Write the A09 store decision (the plan 7.2 architecture record).",
     "tool": "Write", "command": "Write tool: docs/integration/execution/A09_STORE_DECISION.md",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "docs/integration/execution/A09_STORE_DECISION.md"},
    {"seq": 22, "purpose": "Write the A09 closing-checks runner.",
     "tool": "Write", "command": "Write tool: integration-staging/tools/a09_final_checks.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/tools/a09_final_checks.py"},
    {"seq": 23, "purpose": "Write the A09 ledger close-patch builder.",
     "tool": "Write", "command": "Write tool: integration-staging/tools/a09_close_patch.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/tools/a09_close_patch.py"},
    {"seq": 24, "purpose": "Run the A09 closing checks (after the ledger is closed).",
     "tool": "Bash",
     "command": "examdata/.venv/Scripts/python.exe integration-staging/tools/a09_final_checks.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": None,
     "evidence": "docs/integration/execution/evidence/A09/final_checks.txt"},
]

TEST_RESULTS = [
    {"check": "Catalog probe: 30/30 scenarios PASS offline (A09_PROBE: PASS)",
     "result": "pass", "exit_code": 0,
     "evidence": "docs/integration/execution/evidence/A09/catalog_stdout.txt",
     "label": "synthetic_fixture",
     "note": "identity stability/determinism + locator round-trip; benign duplicate dedup; duplicate native id recorded and raised; identity collision; alias conflict (atomic); incomplete reference + gap mapping; reproducible revision; empty diff; unexplained/explained removal; unexplained/authoritative quality upgrade; synthetic never authoritative; lossless UNKNOWN; publish + immutable revision; failed publication leaving the pointer untouched; compare-and-swap; rollback; cursor round-trip/tamper/stale/retained."},
    {"check": "Staged suite passes offline: 430 tests (43 new A09 + 387 A02-A08), 0 failures",
     "result": "pass", "exit_code": 0,
     "evidence": "docs/integration/execution/evidence/A09/pytest_run_stdout.txt",
     "label": "synthetic_fixture",
     "note": "15 store + 14 builder + 14 revision tests, in the isolated harness with the module and network guards active. The 4 warnings originate in the frozen A06 runner tests, not in A09."},
    {"check": "A failed build never yields a publishable snapshot and never disturbs the current pointer",
     "result": "pass", "exit_code": 0,
     "evidence": "integration-staging/tests/test_catalog_builder.py",
     "label": "synthetic_fixture",
     "note": "any store problem, unresolved reference, unexplained removal or unsupported quality upgrade returns snapshot=None; publish(None) and a revision that does not match its entries both leave current.json byte-identical."},
    {"check": "A valid build is reproducible and identities round-trip losslessly",
     "result": "pass", "exit_code": 0,
     "evidence": "integration-staging/tests/test_catalog_store.py",
     "label": "synthetic_fixture",
     "note": "the dataset revision is a pure function of the entries (created_at/input_revisions excluded); the explicit UNKNOWN sentinel survives to_dict -> from_dict unchanged, so an identity never silently changes."},
    {"check": "Publication is compare-and-swap with rollback and revision-bound cursors",
     "result": "pass", "exit_code": 0,
     "evidence": "integration-staging/tests/test_catalog_revision.py",
     "label": "synthetic_fixture",
     "note": "a stale builder is refused; republishing the current revision is idempotent; rollback restores the retained previous revision; a tampered cursor is 400 and a cursor whose revision is no longer published is 409."},
]

FAILURES = [
    {"what": "First probe run exited 1: the gap-mapping scenario read `gap.code.value`, but the frozen contract `Gap` stores `code` as a plain string, so the attribute access raised AttributeError.",
     "evidence": "command row seq 14 (exit_code 1)",
     "resolution": "Fixed in a09_probe_catalog.py: the assertion now compares `gap.code == 'unresolved_identity'` directly. Re-run to green (30/30). No other command exited nonzero."},
]

REMAINING_GAPS = [
    "Only synthetic fixtures and a private temp root are used: no original database, no upstream fetch, no CIE batch resume, no service start.",
    "The staged catalog is not the production read index and is not fed by real data; the SQLite catalog decision execution and database migration are Phase B.",
    "No content is promoted past 'unverified'; a synthetic fixture is never authoritative evidence, so a quality promotion on synthetic data is always rejected.",
    "Active materials and historical timetable integration stay deferred to the active owner.",
    "Inherited A06 stderr race (not an A09 regression): the frozen A06 runner's stderr reader thread raises UnicodeDecodeError when a node child is killed mid-write with a non-UTF-8 stderr byte. The A06 runner is frozen, so this is documented and left for an explicitly-authorized future change to runtime/runner.py.",
]

EVIDENCE_PATHS = [
    "docs/integration/execution/A09_REPORT.md",
    "docs/integration/execution/A09_STORE_DECISION.md",
    "docs/integration/execution/evidence/A09/catalog_stdout.txt",
    "docs/integration/execution/evidence/A09/final_checks.txt",
    "docs/integration/execution/evidence/A09/provenance_check.txt",
    "docs/integration/execution/evidence/A09/pytest_run_stdout.txt",
    "docs/integration/execution/execution-ledger.json",
    "integration-staging/fixtures/synthetic/catalog/PROVENANCE.json",
    "integration-staging/fixtures/synthetic/catalog/catalog-base-synthetic.json",
    "integration-staging/fixtures/synthetic/catalog/catalog-duplicate-native-id-synthetic.json",
    "integration-staging/fixtures/synthetic/catalog/catalog-incomplete-reference-synthetic.json",
    "integration-staging/fixtures/synthetic/catalog/catalog-quality-upgrade-unexplained-synthetic.json",
    "integration-staging/fixtures/synthetic/catalog/catalog-removal-unexplained-synthetic.json",
    "integration-staging/runtime/ledger-patches/A09_close.json",
    "integration-staging/src/examdata_integration/catalog/__init__.py",
    "integration-staging/src/examdata_integration/catalog/builder.py",
    "integration-staging/src/examdata_integration/catalog/model.py",
    "integration-staging/src/examdata_integration/catalog/revision.py",
    "integration-staging/src/examdata_integration/catalog/store.py",
    "integration-staging/tests/test_catalog_builder.py",
    "integration-staging/tests/test_catalog_revision.py",
    "integration-staging/tests/test_catalog_store.py",
    "integration-staging/tools/a09_capture_fixtures.py",
    "integration-staging/tools/a09_close_patch.py",
    "integration-staging/tools/a09_final_checks.py",
    "integration-staging/tools/a09_probe_catalog.py",
]

NEXT_ACTION = ("A10 - Isolated v2 API (plan section 11): an application factory under the staged package "
               "(never importing the original app.py), the 5.1 envelope, the 5.2 error map (409 = "
               "identity/revision/hash conflict including a stale cursor), the 5.4 routes, and an OpenAPI "
               "document that agrees with the running staged app. Materials/timetable use clearly labelled "
               "test fixtures only; no link claims an unavailable production feature.")

NOTES = ("All A09 inputs are synthetic fixtures or frozen contract/harness sources; no original file was read "
         "and nothing was fetched. Exactly one command exited nonzero (the first probe run, exit 1, the "
         "Gap.code string-vs-enum attribute error), fixed in the same packet. The catalog package is entirely "
         "new, so no frozen file was edited: the A00-A08 modules and their hashed fixtures are untouched. The "
         "store choice (immutable JSON revision + atomic pointer over SQLite) is recorded in A09_STORE_DECISION.md "
         "with the plan 7.2 measured-fixture-scale justification and the threshold that would force SQLite. "
         "Everything is staged: nothing is merged and nothing is deployed, and all seven Phase B gates stay closed.")


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def rel(p: Path) -> str:
    return p.relative_to(WS).as_posix()


def main() -> int:
    out_rel = rel(OUT)
    write_set: set[str] = set()
    for pattern in WRITE_GLOBS:
        for p in WS.glob(pattern):
            if p.is_file():
                write_set.add(rel(p))
    # the patch file is a meta-artefact of closing: never hashed against itself;
    # POST_CLOSE artefacts are produced after the ledger closes and must not be
    # listed as changed files (their hash would be stale by construction)
    write_set.discard(out_rel)
    write_set -= POST_CLOSE

    changed_files = sorted(write_set)
    roots_rel = [rel(STAGING) + "/", rel(EXEC) + "/"]
    outside = [f for f in changed_files
               if not any(f.startswith(r) for r in roots_rel)]

    input_hashes: dict[str, str] = {}
    for r in INPUTS:
        p = WS / r
        if p.is_file():
            input_hashes[r] = sha256_file(p)
    for r in changed_files:
        if r in POST_CLOSE:
            continue
        input_hashes[r] = sha256_file(WS / r)

    patch = {
        "dependencies": ["A04", "A08"],
        "allowed_write_roots": ROOTS,
        "blocked_by": [],
        "input_hashes": dict(sorted(input_hashes.items())),
        "changed_files": changed_files,
        "commands": COMMANDS,
        "exit_codes": [c["exit_code"] for c in COMMANDS],
        "test_results": TEST_RESULTS,
        "evidence_paths": EVIDENCE_PATHS,
        "failures": FAILURES,
        "remaining_gaps": REMAINING_GAPS,
        "next_action": NEXT_ACTION,
        "notes": NOTES,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(patch, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8", newline="\n")
    print(f"wrote {out_rel}")
    print(f"changed_files={len(changed_files)} input_hashes={len(input_hashes)} "
          f"exit_codes={patch['exit_codes']} outside_roots={outside}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
