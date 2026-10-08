#!/usr/bin/env python3
"""Build the A08 ledger close patch (docs/integration/execution/execution-ledger.json).

Computes the input hashes over the true inputs plus the A08 write set (excluding
the closing-checks transcript, which is produced *after* the ledger closes, and
this patch file itself), and emits a JSON object to be merged into the A08 task
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
OUT = STAGING / "runtime" / "ledger-patches" / "A08_close.json"

ROOTS = [STAGING.as_posix(), EXEC.as_posix()]

INPUTS = [
    "docs/integration/EXECUTOR_PROMPT_EN.md",
    "docs/integration/MASTER_EXECUTION_PLAN_EN.md",
    "docs/integration/ROUTE_INVENTORY_CURRENT.json",
    "docs/PROJECT_STATUS.md",
    "docs/integration/execution/execution-ledger.json",
    "docs/integration/execution/A07_REPORT.md",
    "docs/integration/execution/evidence/A07/final_checks.txt",
    "docs/integration/execution/evidence/A07/pytest_run_stdout.txt",
    # frozen A04 contracts the adapters map onto (read-only dependency)
    "integration-staging/src/examdata_integration/contracts/models.py",
    "integration-staging/src/examdata_integration/contracts/base.py",
    "integration-staging/src/examdata_integration/contracts/enums.py",
    "integration-staging/src/examdata_integration/contracts/canonical.py",
    "integration-staging/src/examdata_integration/contracts/quality.py",
    # frozen A07 adapter surface A08 reuses (read-only dependency)
    "integration-staging/src/examdata_integration/adapters/__init__.py",
    "integration-staging/src/examdata_integration/adapters/problems.py",
    "integration-staging/src/examdata_integration/adapters/bundle.py",
    "integration-staging/src/examdata_integration/adapters/reader.py",
    # frozen A03 fixtures + provenance the copied snapshots come from (read-only)
    "integration-staging/fixtures/PROVENANCE.json",
    "integration-staging/fixtures/synthetic/ielts/questions-synthetic.json",
    "integration-staging/fixtures/copied/ielts/indexes-current.json",
    "integration-staging/fixtures/copied/ielts/manifests-current.json",
    "integration-staging/fixtures/copied/ielts/pdf-provenance.json",
    "integration-staging/fixtures/copied/ielts/printed-pages.json",
    "integration-staging/fixtures/copied/toefl/ddy-index.json",
    # frozen A02-A07 harness the A08 tests run under
    "integration-staging/pytest.ini",
    "integration-staging/tests/conftest.py",
    "integration-staging/tools/run_staged_tests.sh",
    "integration-staging/tools/ledger_update.py",
    "integration-staging/src/examdata_integration/testing/guards.py",
]

WRITE_GLOBS = [
    # A08 source files only: adapters/*.py would also match the frozen A07 modules
    "integration-staging/src/examdata_integration/adapters/source_reader.py",
    "integration-staging/src/examdata_integration/adapters/ielts.py",
    "integration-staging/src/examdata_integration/adapters/toefl.py",
    "integration-staging/fixtures/synthetic/ielts-toefl/*",
    "integration-staging/tools/a08_*.py",
    # A08 test files only: test_adapters_*.py would also match the frozen A07 tests
    "integration-staging/tests/test_adapters_source_reader.py",
    "integration-staging/tests/test_adapters_ielts.py",
    "integration-staging/tests/test_adapters_toefl.py",
    "integration-staging/runtime/ledger-patches/A08_close.json",
    "docs/integration/execution/A08_REPORT.md",
    "docs/integration/execution/evidence/A08/*",
]

# produced only after the ledger closes: listed but never hashed into the patch
POST_CLOSE = {
    "docs/integration/execution/evidence/A08/final_checks.txt",
}

COMMANDS = [
    {"seq": 1, "purpose": "Create the A08 evidence directory.",
     "tool": "Bash",
     "command": "mkdir -p docs/integration/execution/evidence/A08",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0, "evidence": None},
    {"seq": 2, "purpose": "Write the A08 read step: source_reader.py (source kinds, containment, KMF URL validation, cache-entry iteration).",
     "tool": "Write",
     "command": "Write tool: integration-staging/src/examdata_integration/adapters/source_reader.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/src/examdata_integration/adapters/source_reader.py"},
    {"seq": 3, "purpose": "Write the four synthetic IELTS/TOEFL fixtures and the packet README.",
     "tool": "Write",
     "command": "Write tool: integration-staging/fixtures/synthetic/ielts-toefl/{ielts-questions-a08-synthetic.json,ielts-audio-synthetic.json,toefl-questions-synthetic.json,toefl-bad-cache-synthetic.json,README.md}",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/fixtures/synthetic/ielts-toefl/"},
    {"seq": 4, "purpose": "Write the fixture-provenance capture tool.",
     "tool": "Write",
     "command": "Write tool: integration-staging/tools/a08_capture_fixtures.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/tools/a08_capture_fixtures.py"},
    {"seq": 5, "purpose": "Generate the A08 fixture provenance manifest (4 entries).",
     "tool": "Bash",
     "command": "examdata/.venv/Scripts/python.exe integration-staging/tools/a08_capture_fixtures.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/fixtures/synthetic/ielts-toefl/PROVENANCE.json"},
    {"seq": 6, "purpose": "Write the IELTS adapters: question set, copied pages/provenance, revision pointers, audio alignment.",
     "tool": "Write",
     "command": "Write tool: integration-staging/src/examdata_integration/adapters/ielts.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/src/examdata_integration/adapters/ielts.py"},
    {"seq": 7, "purpose": "Write the TOEFL adapters: copied reading index, question sets, cache reparse.",
     "tool": "Write",
     "command": "Write tool: integration-staging/src/examdata_integration/adapters/toefl.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/src/examdata_integration/adapters/toefl.py"},
    {"seq": 8, "purpose": "Diagnostic run of validate_kmf_url over the copied reading index: it exited 0 but revealed that the strict validator rejected 51 of 72 legitimate KMF links (the real links carry a trailing /1 question anchor).",
     "tool": "Bash",
     "command": "PYTHONPATH=integration-staging/src examdata/.venv/Scripts/python.exe -c \"<inline validate_kmf_url over copied/toefl/ddy-index.json>\"",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/src/examdata_integration/adapters/source_reader.py"},
    {"seq": 9, "purpose": "Loosen validate_kmf_url to accept an optional trailing alphanumeric question anchor; the URL is still validated, never requested.",
     "tool": "Edit",
     "command": "Edit tool: integration-staging/src/examdata_integration/adapters/source_reader.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/src/examdata_integration/adapters/source_reader.py"},
    {"seq": 10, "purpose": "First inline IELTS smoke run exited 1: answer_verification unknown -> conflicting is not in the frozen transition table (allowed: ['unverified']).",
     "tool": "Bash",
     "command": "PYTHONPATH=integration-staging/src examdata/.venv/Scripts/python.exe -c \"<inline IELTSQuestionsAdapter smoke>\"",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 1,
     "evidence": "integration-staging/src/examdata_integration/adapters/ielts.py"},
    {"seq": 11, "purpose": "Fix _question_quality to pass through unverified before conflicting, so an unresolved conflict is recorded without an illegal jump.",
     "tool": "Edit",
     "command": "Edit tool: integration-staging/src/examdata_integration/adapters/ielts.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/src/examdata_integration/adapters/ielts.py"},
    {"seq": 12, "purpose": "Re-verify validate_kmf_url and the copied reading index: all legitimate links accepted, exactly two unresolved_identity problems for tpo-38-2.",
     "tool": "Bash",
     "command": "PYTHONPATH=integration-staging/src examdata/.venv/Scripts/python.exe -c \"<inline validate_kmf_url + TOEFLReadingIndexAdapter>\"",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/src/examdata_integration/adapters/toefl.py"},
    {"seq": 13, "purpose": "Write the three A08 test modules.",
     "tool": "Write",
     "command": "Write tool: integration-staging/tests/test_adapters_{source_reader,ielts,toefl}.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/tests/"},
    {"seq": 14, "purpose": "Correct the pages test-side expectation: imported provenance assets carry no media_type, so the assertion became 133 assets (9 PDF + 124 with media_type None).",
     "tool": "Edit",
     "command": "Edit tool: integration-staging/tests/test_adapters_ielts.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/tests/test_adapters_ielts.py"},
    {"seq": 15, "purpose": "Run the three A08 test modules to green (61 passed).",
     "tool": "Bash",
     "command": "examdata/.venv/Scripts/python.exe -m pytest integration-staging/tests/test_adapters_source_reader.py integration-staging/tests/test_adapters_ielts.py integration-staging/tests/test_adapters_toefl.py -q",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/tests/"},
    {"seq": 16, "purpose": "Write the 40-scenario offline read-adapter probe.",
     "tool": "Write",
     "command": "Write tool: integration-staging/tools/a08_probe_adapters.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/tools/a08_probe_adapters.py"},
    {"seq": 17, "purpose": "Run the probe to green (40/40) and capture the transcript.",
     "tool": "Bash",
     "command": "examdata/.venv/Scripts/python.exe integration-staging/tools/a08_probe_adapters.py > docs/integration/execution/evidence/A08/adapters_stdout.txt",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "docs/integration/execution/evidence/A08/adapters_stdout.txt"},
    {"seq": 18, "purpose": "Run the full staged suite to green (387 passed) and capture the transcript.",
     "tool": "Bash",
     "command": "bash integration-staging/tools/run_staged_tests.sh -q > docs/integration/execution/evidence/A08/pytest_run_stdout.txt",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "docs/integration/execution/evidence/A08/pytest_run_stdout.txt"},
    {"seq": 19, "purpose": "Capture the fixture-provenance check transcript.",
     "tool": "Bash",
     "command": "examdata/.venv/Scripts/python.exe integration-staging/tools/a08_capture_fixtures.py --check > docs/integration/execution/evidence/A08/provenance_check.txt",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "docs/integration/execution/evidence/A08/provenance_check.txt"},
    {"seq": 20, "purpose": "Write the A08 report.",
     "tool": "Write", "command": "Write tool: docs/integration/execution/A08_REPORT.md",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "docs/integration/execution/A08_REPORT.md"},
    {"seq": 21, "purpose": "Write the A08 closing-checks runner.",
     "tool": "Write", "command": "Write tool: integration-staging/tools/a08_final_checks.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/tools/a08_final_checks.py"},
    {"seq": 22, "purpose": "Write the A08 ledger close-patch builder.",
     "tool": "Write", "command": "Write tool: integration-staging/tools/a08_close_patch.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/tools/a08_close_patch.py"},
    {"seq": 23, "purpose": "Run the A08 closing checks (after the ledger is closed).",
     "tool": "Bash",
     "command": "examdata/.venv/Scripts/python.exe integration-staging/tools/a08_final_checks.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": None,
     "evidence": "docs/integration/execution/evidence/A08/final_checks.txt"},
]

TEST_RESULTS = [
    {"check": "Read-adapter probe: 40/40 scenarios PASS offline (A08_PROBE: PASS)",
     "result": "pass", "exit_code": 0,
     "evidence": "docs/integration/execution/evidence/A08/adapters_stdout.txt",
     "label": "synthetic_fixture",
     "note": "source kinds + containment, KMF URL shape, cache entries, IELTS Q41/hierarchy/table/conflict/variant, audio alignment states, copied page map + revision pointer, TOEFL reading index (one container per passage, no coverage claim, real URLs accepted, two unresolved identities), TOEFL question sets (identity classes, locked jj, unknown dates, bad URL) and cache reparse."},
    {"check": "Staged suite passes offline: 387 tests (61 new A08 + 326 A02-A07), 0 failures",
     "result": "pass", "exit_code": 0,
     "evidence": "docs/integration/execution/evidence/A08/pytest_run_stdout.txt",
     "label": "synthetic_fixture",
     "note": "23 source_reader + 22 IELTS + 16 TOEFL, in the isolated harness with the module and network guards active. The 4 warnings originate in the frozen A06 runner tests (see report section 9), not in A08."},
    {"check": "The read step is total: missing/unreadable/invalid/outside-staging/wrong-kind/bad-version inputs are problems, never exceptions",
     "result": "pass", "exit_code": 0,
     "evidence": "integration-staging/tests/test_adapters_source_reader.py",
     "label": "synthetic_fixture",
     "note": "read_source returns (None, kind, [problem]) and never raises for a data problem; a path outside staging is classified before it is opened; the KMF URL is validated, never requested."},
    {"check": "IELTS mapping preserves the Q41 missing slot, hierarchy, tables, conflicts and audio states and never fabricates an answer",
     "result": "pass", "exit_code": 0,
     "evidence": "integration-staging/tests/test_adapters_ielts.py",
     "label": "synthetic_fixture",
     "note": "Q41 keeps an empty slot (answer_presence=missing); a self-parent is normalised to root with the raw parent kept in the lineage; a synthetic verified audio claim is capped at unverified; every answer stays verification='unverified', content_class='synthetic'."},
    {"check": "TOEFL mapping preserves identity classes, the locked jj set, table rows and bad cache entries",
     "result": "pass", "exit_code": 0,
     "evidence": "integration-staging/tests/test_adapters_toefl.py",
     "label": "copied_snapshot",
     "note": "72 passages / 72 distinct ids with coverage_claimed=False; a restricted jj set is metadata-only; a rejected cache entry is reported (bad_cache_entry), never dropped."},
]

FAILURES = [
    {"what": "First inline IELTS smoke run exited 1: the adapter tried answer_verification unknown -> conflicting, which is not in the frozen A04 transition table (the only permitted step from unknown is unverified).",
     "evidence": "command row seq 10 (exit_code 1)",
     "resolution": "Fixed in ielts.py _question_quality: an unresolved conflict now passes through unverified (STATIC evidence) before the conflicting transition, so the conflict is recorded with its gap and no illegal jump. Two further defects were found by inspection of successful runs and corrected in the same packet (see notes): validate_kmf_url rejected 51/72 legitimate KMF links carrying a trailing /1 anchor, and a pages test asserted a media_type for imported provenance assets that have none."},
]

REMAINING_GAPS = [
    "Only synthetic fixtures and copied snapshots are read: no original database, no upstream fetch, no CIE batch resume, no service start.",
    "Active materials and historical timetable integration stay deferred to the active owner; the A12 worksheet keeps its deferred_active_owner rows deferred.",
    "No content is promoted past 'unverified'; promotion to verified is a Phase B gate. A synthetic audio fixture can never reach verified alignment.",
    "The copied IELTS PDF-import provenance records absolute original paths; these are preserved verbatim as provenance, not rewritten or resolved.",
    "The A03 IELTS question fixture carries no schema_version, so version checking is opt-in and unlabelled copied snapshots are accepted.",
    "Inherited A06 stderr race (not an A08 regression): the frozen A06 runner's stderr reader thread raises UnicodeDecodeError when a node child is killed mid-write with the fixture's non-UTF-8 stderr byte. It reproduces with the A06 tests alone and is fail-closed (stderr dropped, never leaked). The A06 runner is frozen, so this is documented and left for an explicitly-authorized future change to runtime/runner.py.",
]

EVIDENCE_PATHS = [
    "docs/integration/execution/A08_REPORT.md",
    "docs/integration/execution/evidence/A08/adapters_stdout.txt",
    "docs/integration/execution/evidence/A08/final_checks.txt",
    "docs/integration/execution/evidence/A08/provenance_check.txt",
    "docs/integration/execution/evidence/A08/pytest_run_stdout.txt",
    "docs/integration/execution/execution-ledger.json",
    "integration-staging/fixtures/synthetic/ielts-toefl/PROVENANCE.json",
    "integration-staging/fixtures/synthetic/ielts-toefl/README.md",
    "integration-staging/fixtures/synthetic/ielts-toefl/ielts-audio-synthetic.json",
    "integration-staging/fixtures/synthetic/ielts-toefl/ielts-questions-a08-synthetic.json",
    "integration-staging/fixtures/synthetic/ielts-toefl/toefl-bad-cache-synthetic.json",
    "integration-staging/fixtures/synthetic/ielts-toefl/toefl-questions-synthetic.json",
    "integration-staging/runtime/ledger-patches/A08_close.json",
    "integration-staging/src/examdata_integration/adapters/ielts.py",
    "integration-staging/src/examdata_integration/adapters/source_reader.py",
    "integration-staging/src/examdata_integration/adapters/toefl.py",
    "integration-staging/tests/test_adapters_ielts.py",
    "integration-staging/tests/test_adapters_source_reader.py",
    "integration-staging/tests/test_adapters_toefl.py",
    "integration-staging/tools/a08_capture_fixtures.py",
    "integration-staging/tools/a08_close_patch.py",
    "integration-staging/tools/a08_final_checks.py",
    "integration-staging/tools/a08_probe_adapters.py",
]

NEXT_ACTION = ("A09 - Stage catalog and revision publication (plan section 11): a private mapping/catalog store, "
               "a builder, immutable revision manifests and a pointer publisher; tests for duplicate native ids, "
               "collision detection, incomplete references, failed publication, concurrent publishers, a stale "
               "current pointer, rollback and stable cursor references. A failed build must never change the current "
               "pointer and a valid build must be reproducible - offline, private fixtures only.")

NOTES = ("All A08 inputs are synthetic fixtures, copied snapshots or frozen contract/harness sources; no original "
         "file was read and nothing was fetched. Exactly one command exited nonzero (the inline IELTS smoke run, "
         "exit 1, the answer_verification transition defect). Two further defects were found by inspection of "
         "successful runs and corrected in the same packet: validate_kmf_url rejected 51/72 legitimate KMF links "
         "carrying a trailing /1 question anchor (loosened to accept an optional trailing alphanumeric segment; the "
         "URL is still only validated, never requested), and the pages test asserted a media_type for imported "
         "provenance assets that have none (test-side only). The frozen A06 runner's stderr-reader race is recorded "
         "in remaining_gaps, not fixed.")


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
        "dependencies": ["A07", "A03"],
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
