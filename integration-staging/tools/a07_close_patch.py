#!/usr/bin/env python3
"""Build the A07 ledger close patch (docs/integration/execution/execution-ledger.json).

Computes the input hashes over the true inputs plus the A07 write set (excluding
the closing-checks transcript, which is produced *after* the ledger closes, and
this patch file itself), and emits a JSON object to be merged into the A07 task
record by ``integration-staging/tools/ledger_update.py --patch-file``.

Phase A tool (integration-staging/tools/). Stdlib only.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True

WS = Path(__file__).resolve().parents[2]
STAGING = WS / "integration-staging"
EXEC = WS / "docs" / "integration" / "execution"
OUT = STAGING / "runtime" / "ledger-patches" / "A07_close.json"

ROOTS = [STAGING.as_posix(), EXEC.as_posix()]

INPUTS = [
    "docs/integration/EXECUTOR_PROMPT_EN.md",
    "docs/integration/MASTER_EXECUTION_PLAN_EN.md",
    "docs/integration/ROUTE_INVENTORY_CURRENT.json",
    "docs/PROJECT_STATUS.md",
    "docs/integration/execution/execution-ledger.json",
    "docs/integration/execution/A06_REPORT.md",
    "docs/integration/execution/evidence/A06/final_checks.txt",
    "docs/integration/execution/evidence/A06/pytest_run_stdout.txt",
    # frozen A04 contracts the adapters map onto (read-only dependency)
    "integration-staging/src/examdata_integration/contracts/models.py",
    "integration-staging/src/examdata_integration/contracts/base.py",
    "integration-staging/src/examdata_integration/contracts/enums.py",
    "integration-staging/src/examdata_integration/contracts/canonical.py",
    # frozen A02-A06 harness the A07 tests run under
    "integration-staging/pytest.ini",
    "integration-staging/tests/conftest.py",
    "integration-staging/tools/run_staged_tests.sh",
    "integration-staging/tools/ledger_update.py",
    "integration-staging/src/examdata_integration/testing/guards.py",
]

WRITE_GLOBS = [
    "integration-staging/src/examdata_integration/adapters/*.py",
    "integration-staging/fixtures/synthetic/adapters/*",
    "integration-staging/tools/a07_*.py",
    "integration-staging/tests/test_adapters_*.py",
    "integration-staging/runtime/ledger-patches/A07_close.json",
    "docs/integration/execution/A07_REPORT.md",
    "docs/integration/execution/evidence/A07/*.txt",
]

# produced only after the ledger closes: listed but never hashed into the patch
POST_CLOSE = {
    "docs/integration/execution/evidence/A07/final_checks.txt",
}

COMMANDS = [
    {"seq": 1, "purpose": "Create the A07 evidence directory.",
     "tool": "Bash",
     "command": "mkdir -p docs/integration/execution/evidence/A07",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0, "evidence": None},
    {"seq": 2, "purpose": "Write the two synthetic adapter fixtures and the packet provenance note.",
     "tool": "Write",
     "command": "Write tool: integration-staging/fixtures/synthetic/adapters/{cie-index-adapters.json,edexcel-index-adapters.json,README.md}",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/fixtures/synthetic/adapters/"},
    {"seq": 3, "purpose": "Write the adapters package: problems, reader, documents, answers, regions, bundle, cie, edexcel, __init__.",
     "tool": "Write",
     "command": "Write tool: integration-staging/src/examdata_integration/adapters/{problems,reader,documents,answers,regions,bundle,cie,edexcel,__init__}.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/src/examdata_integration/adapters/"},
    {"seq": 4, "purpose": "Write the fixture-provenance capture tool.",
     "tool": "Write",
     "command": "Write tool: integration-staging/tools/a07_capture_adapter_fixtures.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/tools/a07_capture_adapter_fixtures.py"},
    {"seq": 5, "purpose": "Generate the adapter fixture provenance manifest.",
     "tool": "Bash",
     "command": "examdata/.venv/Scripts/python.exe integration-staging/tools/a07_capture_adapter_fixtures.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/fixtures/synthetic/adapters/PROVENANCE.json"},
    {"seq": 6, "purpose": "First inline smoke run of the adapters failed: Lineage imported from contracts.base (it lives in contracts.models).",
     "tool": "Bash",
     "command": "PYTHONPATH=integration-staging/src examdata/.venv/Scripts/python.exe -c \"<inline CIE/Edexcel adapter smoke>\"",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 1,
     "evidence": "integration-staging/src/examdata_integration/adapters/"},
    {"seq": 7, "purpose": "Fix the Lineage import in four adapter modules; replace the dead UNKNOWN_DATE placeholder and thread rotations_declared through build_regions.",
     "tool": "Edit",
     "command": "Edit tool: integration-staging/src/examdata_integration/adapters/{cie,edexcel,answers,bundle}.py, regions.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/src/examdata_integration/adapters/"},
    {"seq": 8, "purpose": "Write the seven A07 test modules.",
     "tool": "Write",
     "command": "Write tool: integration-staging/tests/test_adapters_{reader,documents,answers,regions,cie,edexcel,provenance}.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/tests/"},
    {"seq": 9, "purpose": "First adapter-only pytest run exited 1: eight test-side expectation errors (region default declared, none/unknown-mode semantics).",
     "tool": "Bash",
     "command": "examdata/.venv/Scripts/python.exe -m pytest integration-staging/tests/test_adapters_*.py -q",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 1,
     "evidence": "integration-staging/tests/"},
    {"seq": 10, "purpose": "Fix the eight test-side expectations to the settled semantics (no product change).",
     "tool": "Edit",
     "command": "Edit tool: integration-staging/tests/test_adapters_{regions,answers,cie}.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/tests/"},
    {"seq": 11, "purpose": "Re-run the adapter-only suite to green (94 passed).",
     "tool": "Bash",
     "command": "examdata/.venv/Scripts/python.exe -m pytest integration-staging/tests/test_adapters_*.py -q",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/tests/"},
    {"seq": 12, "purpose": "Write the 42-scenario offline adapter probe.",
     "tool": "Write",
     "command": "Write tool: integration-staging/tools/a07_probe_adapters.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/tools/a07_probe_adapters.py"},
    {"seq": 13, "purpose": "First probe run exited 1: two probe-side errors (a 62-char fixture hash, and document-problem ordering).",
     "tool": "Bash",
     "command": "examdata/.venv/Scripts/python.exe integration-staging/tools/a07_probe_adapters.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 1,
     "evidence": "integration-staging/tools/a07_probe_adapters.py"},
    {"seq": 14, "purpose": "Correct the two 62-char cited hashes in the CIE fixture to 64 chars and fix the probe's document-problem ordering expectation.",
     "tool": "Edit",
     "command": "Edit tool: integration-staging/fixtures/synthetic/adapters/cie-index-adapters.json, integration-staging/tools/a07_probe_adapters.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/fixtures/synthetic/adapters/cie-index-adapters.json"},
    {"seq": 15, "purpose": "Re-generate the fixture provenance after the fixture edit.",
     "tool": "Bash",
     "command": "examdata/.venv/Scripts/python.exe integration-staging/tools/a07_capture_adapter_fixtures.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/fixtures/synthetic/adapters/PROVENANCE.json"},
    {"seq": 16, "purpose": "Re-run the probe to green (42/42) and capture the transcript.",
     "tool": "Bash",
     "command": "examdata/.venv/Scripts/python.exe integration-staging/tools/a07_probe_adapters.py > docs/integration/execution/evidence/A07/adapters_stdout.txt",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "docs/integration/execution/evidence/A07/adapters_stdout.txt"},
    {"seq": 17, "purpose": "Run the full staged suite to green (326 passed) and capture the transcript.",
     "tool": "Bash",
     "command": "bash integration-staging/tools/run_staged_tests.sh -q > docs/integration/execution/evidence/A07/pytest_run_stdout.txt",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "docs/integration/execution/evidence/A07/pytest_run_stdout.txt"},
    {"seq": 18, "purpose": "Write the A07 report.",
     "tool": "Write", "command": "Write tool: docs/integration/execution/A07_REPORT.md",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "docs/integration/execution/A07_REPORT.md"},
    {"seq": 19, "purpose": "Write the A07 closing-checks runner.",
     "tool": "Write", "command": "Write tool: integration-staging/tools/a07_final_checks.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/tools/a07_final_checks.py"},
    {"seq": 20, "purpose": "Write the A07 ledger close-patch builder.",
     "tool": "Write", "command": "Write tool: integration-staging/tools/a07_close_patch.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/tools/a07_close_patch.py"},
    {"seq": 21, "purpose": "Run the A07 closing checks (after the ledger is closed).",
     "tool": "Bash",
     "command": "examdata/.venv/Scripts/python.exe integration-staging/tools/a07_final_checks.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": None,
     "evidence": "docs/integration/execution/evidence/A07/final_checks.txt"},
]

TEST_RESULTS = [
    {"check": "Adapter probe: 42/42 scenarios PASS offline (A07_PROBE: PASS)",
     "result": "pass", "exit_code": 0,
     "evidence": "docs/integration/execution/evidence/A07/adapters_stdout.txt",
     "label": "synthetic_fixture",
     "note": "CIE and Edexcel bundles (counts, identities, containers, regions), descendants/ancestor/exact answer resolution, missing-ms/unknown-date/hash-conflict/unknown-rotation problems and their gap mapping, plus 15 read-step and geometry edge cases."},
    {"check": "Staged suite passes offline: 326 tests (94 new A07 + 232 A03-A06), 0 failures",
     "result": "pass", "exit_code": 0,
     "evidence": "docs/integration/execution/evidence/A07/pytest_run_stdout.txt",
     "label": "synthetic_fixture",
     "note": "16 answer + 17 CIE + 14 documents + 13 Edexcel + 6 provenance + 14 reader + 14 regions, in the isolated harness with the module and network guards active. The 4 warnings originate in the frozen A06 runner tests (see report section 9), not in A07."},
    {"check": "The read step is total: missing/unreadable/invalid/wrong-kind/bad-version inputs are problems, never exceptions",
     "result": "pass", "exit_code": 0,
     "evidence": "integration-staging/tests/test_adapters_reader.py",
     "label": "synthetic_fixture",
     "note": "read_index/validate_index return (None, [problem]) and never raise for a data problem; only schema_version '1' is accepted."},
    {"check": "Answer resolution preserves exact/ancestor/descendants/none and never fabricates an answer",
     "result": "pass", "exit_code": 0,
     "evidence": "integration-staging/tests/test_adapters_answers.py",
     "label": "synthetic_fixture",
     "note": "Every emitted answer stays verification='unverified' and content_class='synthetic'; an unreachable answer yields missing_answer with the slot kept."},
    {"check": "Document hashes and region geometry stay honest (conflicts preserved, unverified)",
     "result": "pass", "exit_code": 0,
     "evidence": "integration-staging/tests/test_adapters_documents.py",
     "label": "synthetic_fixture",
     "note": "A cited hash is never rewritten to match the table; a missing mark scheme is its own code; regions are always evidence_status='unverified'."},
]

FAILURES = [
    {"what": "First inline adapter smoke run failed: the four adapter modules imported Lineage from contracts.base, but Lineage lives in contracts.models.",
     "evidence": "command row seq 6 (exit_code 1)",
     "resolution": "Import corrected to contracts.models in cie.py, edexcel.py, answers.py and bundle.py. Two further issues were fixed in the same pass: a dead placeholder in cie.py was replaced with a proper UNKNOWN_DATE problem, and build_regions gained a rotations_declared flag so an index with no page table is not falsely flagged unknown_rotation."},
    {"what": "First adapter-only pytest run exited 1: eight test-side expectation errors (region tests assumed rotations were declared; none/unknown-mode answer tests used the pre-settlement semantics).",
     "evidence": "command row seq 9 (exit_code 1)",
     "resolution": "All eight were test-side expectation errors, no product change: region tests pass declared=False by default, and the none/unknown-mode expectations were updated to the settled semantics (own stated answer wins; unknown mode behaves as none)."},
    {"what": "First adapter probe run exited 1: two probe-side errors.",
     "evidence": "command row seq 13 (exit_code 1)",
     "resolution": "Both were probe/fixture-side, no adapter change: the CIE fixture cited a 62-character hash where 64 was intended (the adapter had correctly preserved it verbatim), corrected to 64 chars and the fixture provenance re-hashed; and the probe expected a fixed order for document_problems on an empty table, corrected to a sorted comparison."},
]

REMAINING_GAPS = [
    "Only synthetic fixtures are read: no original database, no upstream fetch, no CIE batch resume, no service start.",
    "Active materials and historical timetable integration stay deferred to the active owner; the A12 worksheet keeps its deferred_active_owner rows deferred.",
    "No content is promoted past 'unverified'; promotion to verified is a Phase B gate.",
    "Inherited A06 stderr race (not an A07 regression): the frozen A06 runner's stderr reader thread raises UnicodeDecodeError when a node child is killed mid-write with the fixture's non-UTF-8 stderr byte. It reproduces with the A06 tests alone and is fail-closed (stderr dropped, never leaked). The A06 runner is frozen, so this is documented and left for an explicitly-authorized future change to runtime/runner.py.",
    "The CIE adapter supports the four documented answer_resolution modes; a raw index using another mode is reported (unresolved_answer_mode), never guessed.",
]

EVIDENCE_PATHS = [
    "docs/integration/execution/A07_REPORT.md",
    "docs/integration/execution/evidence/A07/adapters_stdout.txt",
    "docs/integration/execution/evidence/A07/final_checks.txt",
    "docs/integration/execution/evidence/A07/pytest_run_stdout.txt",
    "docs/integration/execution/execution-ledger.json",
    "integration-staging/fixtures/synthetic/adapters/PROVENANCE.json",
    "integration-staging/fixtures/synthetic/adapters/README.md",
    "integration-staging/fixtures/synthetic/adapters/cie-index-adapters.json",
    "integration-staging/fixtures/synthetic/adapters/edexcel-index-adapters.json",
    "integration-staging/runtime/ledger-patches/A07_close.json",
    "integration-staging/src/examdata_integration/adapters/__init__.py",
    "integration-staging/src/examdata_integration/adapters/answers.py",
    "integration-staging/src/examdata_integration/adapters/bundle.py",
    "integration-staging/src/examdata_integration/adapters/cie.py",
    "integration-staging/src/examdata_integration/adapters/documents.py",
    "integration-staging/src/examdata_integration/adapters/edexcel.py",
    "integration-staging/src/examdata_integration/adapters/problems.py",
    "integration-staging/src/examdata_integration/adapters/reader.py",
    "integration-staging/src/examdata_integration/adapters/regions.py",
    "integration-staging/tests/test_adapters_answers.py",
    "integration-staging/tests/test_adapters_cie.py",
    "integration-staging/tests/test_adapters_documents.py",
    "integration-staging/tests/test_adapters_edexcel.py",
    "integration-staging/tests/test_adapters_provenance.py",
    "integration-staging/tests/test_adapters_reader.py",
    "integration-staging/tests/test_adapters_regions.py",
    "integration-staging/tools/a07_capture_adapter_fixtures.py",
    "integration-staging/tools/a07_close_patch.py",
    "integration-staging/tools/a07_final_checks.py",
    "integration-staging/tools/a07_probe_adapters.py",
]

NEXT_ACTION = ("A08 - IELTS and TOEFL read adapters over synthetic/copied fixtures (plan section 11): reuse the A07 "
               "adapter shape (reader/documents/answers/regions + a per-system module), preserving the IELTS Q41 "
               "missing-answer slot, table structures, locked jj, unknown dates and bad-cache content - offline, "
               "private fixtures only.")


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
        "dependencies": ["A06"],
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
        "notes": ("All A07 inputs are synthetic fixtures or frozen A04 contract sources; no original file was "
                  "read. The frozen A06 runner's stderr-reader race (see remaining_gaps) is recorded, not fixed."),
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
