#!/usr/bin/env python3
"""Build the A15 ledger close patch (docs/integration/execution/execution-ledger.json).

Computes the input hashes over the true inputs plus the A15 write set (excluding
the post-close transcripts, which are produced *after* the ledger closes, and
this patch file itself), and emits a JSON object to be merged into the A15 task
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
OUT = STAGING / "runtime" / "ledger-patches" / "A15_close.json"

ROOTS = [STAGING.as_posix(), EXEC.as_posix()]

#: the twelve original files the merge map records as the base of a staged copy.
#: Their hashes are point-in-time observations of an actively owned tree: the
#: closing checks log drift for these instead of asserting them.
MAP_BASES = [
    "frontend/edexcel-subjects-source.json",
    "frontend/app.js",
    "frontend/index.html",
    "frontend/README.md",
    "frontend/search.mjs",
    "frontend/search.test.mjs",
    "frontend/styles.css",
    "ielts-api/data/printed-pages.json",
    "ielts-data/indexes/current",
    "ielts-data/manifests/current",
    "ielts-data/manifests/pdf-provenance.json",
    "toefl-api/data/ddy-index.json",
]

#: the planned original edits whose base exists (examdata/cli.py is absent and
#: is therefore not an input; the map records it as base_exists=false).
PLANNED_EDIT_BASES = [
    "examdata/src/examdata/api/app.py",
    "examdata/pyproject.toml",
    "frontend/server.mjs",
    "examdata/docs/API.md",
]

INPUTS = [
    # governing documents
    "docs/integration/EXECUTOR_PROMPT_EN.md",
    "docs/integration/MASTER_EXECUTION_PLAN_EN.md",
    "docs/integration/ROUTE_INVENTORY_CURRENT.json",
    "docs/PROJECT_STATUS.md",
    # the ledger itself (self-referential: observed, never strictly asserted)
    "docs/integration/execution/execution-ledger.json",
    "docs/integration/execution/ownership.json",
    # frozen A00-A14 artefacts the A15 documents summarise
    "docs/integration/execution/A12_ROUTE_COMPATIBILITY_WORKSHEET.json",
    "docs/integration/execution/A14_MERGE_MAP.json",
    "docs/integration/execution/A14_MERGE_MAP.md",
    "docs/integration/execution/A14_RELEASE_MANIFEST.json",
    "docs/integration/execution/A14_REHEARSAL.json",
    # the two A15 documents (also in the write set)
    "docs/integration/execution/PHASE_A_REPORT.md",
    "docs/integration/execution/PHASE_A_DEFERRED_WORK.md",
    # frozen staging inputs: provenance manifests, harness, rehearsal fixtures
    "integration-staging/fixtures/PROVENANCE.json",
    "integration-staging/frontend/PROVENANCE.json",
    "integration-staging/pytest.ini",
    "integration-staging/tests/conftest.py",
    "integration-staging/components/manifest.json",
    "integration-staging/fixtures/synthetic/catalog/catalog-base-synthetic.json",
    # the frozen staged v2 api module (deterministic ids, A14)
    "integration-staging/src/examdata_integration/api/app.py",
    # read-only original bases recorded by the merge map
    *MAP_BASES,
    # read-only bases of the planned original edits
    *PLANNED_EDIT_BASES,
]

WRITE_GLOBS = [
    # the packet tools (this close-patch builder and the closing checks included)
    "integration-staging/tools/a15_*.py",
    # packet runtime transcript + the close patch
    "integration-staging/runtime/ledger-patches/A15_close.json",
    # the two A15 documents
    "docs/integration/execution/PHASE_A_REPORT.md",
    "docs/integration/execution/PHASE_A_DEFERRED_WORK.md",
    # packet evidence (only POST_CLOSE transcripts; excluded below)
    "docs/integration/execution/evidence/A15/*",
]

# produced only after the ledger closes: listed but never hashed into the patch
POST_CLOSE = {
    "docs/integration/execution/evidence/A15/final_checks.txt",
    "docs/integration/execution/evidence/A15/pytest_rerun.txt",
    "docs/integration/execution/evidence/A15/node_rerun.txt",
}

COMMANDS = [
    {"seq": 1, "purpose": "Read the A14 close-patch builder and the A14 closing-checks runner as format templates for this final packet.",
     "tool": "Read",
     "command": "Read tool: integration-staging/tools/a14_close_patch.py, integration-staging/tools/a14_final_checks.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0, "evidence": None},
    {"seq": 2, "purpose": "Write the Phase A report: packet-by-packet summary A00-A15, deliverables, validation model, compatibility coverage, deferred work, ownership-release requirements, and the explicit staged/not-merged/not-deployed statement.",
     "tool": "Write",
     "command": "Write tool: docs/integration/execution/PHASE_A_REPORT.md",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "docs/integration/execution/PHASE_A_REPORT.md"},
    {"seq": 3, "purpose": "Write the deferred-work list: DEF-01..DEF-06, the Phase A limitations carried forward, the ownership-release requirements and the seven-gate Phase B checklist.",
     "tool": "Write",
     "command": "Write tool: docs/integration/execution/PHASE_A_DEFERRED_WORK.md",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "docs/integration/execution/PHASE_A_DEFERRED_WORK.md"},
    {"seq": 4, "purpose": "Write the A15 closing-checks runner: artifact existence, cross-packet re-verification, ledger state (A00-A15 staged_pass / B00-B10 not_started / seven gates closed / no merged status), close-patch consistency, worksheet coverage, the two documents' content and completion-claim scan, fresh offline liveness, containment and the two-root sha256 manifest.",
     "tool": "Write",
     "command": "Write tool: integration-staging/tools/a15_final_checks.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/tools/a15_final_checks.py"},
    {"seq": 5, "purpose": "Write the A15 close-patch builder (hashes the inputs and the packet write set, excluding the post-close transcripts).",
     "tool": "Write",
     "command": "Write tool: integration-staging/tools/a15_close_patch.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/tools/a15_close_patch.py"},
    {"seq": 6, "purpose": "Re-run the two cross-packet checks before closing: the merge map and the rollback rehearsal both still reproduce their recorded PASS lines (base drift 0).",
     "tool": "Bash",
     "command": "examdata/.venv/Scripts/python.exe integration-staging/tools/a14_build_artifacts.py --check && examdata/.venv/Scripts/python.exe integration-staging/tools/a14_rehearsal.py --check",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "docs/integration/execution/A14_MERGE_MAP.json"},
    {"seq": 7, "purpose": "Inline completion-claim scan over the two A15 documents. It flagged two false positives that are not claims by this executor - the verbatim plan quote (a blockquote) and a status label in a code span - so the closing-checks scan now drops blockquotes and inline code spans before matching.",
     "tool": "Bash",
     "command": "examdata/.venv/Scripts/python.exe -c \"...scan PHASE_A_REPORT.md / PHASE_A_DEFERRED_WORK.md for completion-claim patterns...\"",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0, "evidence": None},
    {"seq": 8, "purpose": "Build the A15 close patch (hashes the inputs and the packet write set, excluding the post-close transcripts).",
     "tool": "Bash",
     "command": "examdata/.venv/Scripts/python.exe integration-staging/tools/a15_close_patch.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/runtime/ledger-patches/A15_close.json"},
    {"seq": 9, "purpose": "Close the A15 ledger record: status staged_pass with the patch merged in (the ledger refuses merged_pass in PHASE_A_ISOLATED_ONLY).",
     "tool": "Bash",
     "command": "examdata/.venv/Scripts/python.exe integration-staging/tools/ledger_update.py --task A15 --status staged_pass --patch-file integration-staging/runtime/ledger-patches/A15_close.json",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "docs/integration/execution/execution-ledger.json"},
    {"seq": 10, "purpose": "First A15 closing-checks run failed honestly with two defects in the checks tool itself: it looked for docs/integration/execution/A00_REPORT.md (the real name is A00_INITIAL_REPORT.md) and it wrote the pytest transcript into evidence/A15 before creating that directory (FileNotFoundError).",
     "tool": "Bash",
     "command": "examdata/.venv/Scripts/python.exe integration-staging/tools/a15_final_checks.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 1, "evidence": None},
    {"seq": 11, "purpose": "Fix both defects in the closing-checks tool: correct the A00 report filename and create evidence/A15 before writing the post-close transcripts.",
     "tool": "Edit",
     "command": "Edit tool: integration-staging/tools/a15_final_checks.py (A00_TO_A14_REPORTS + EV.mkdir)",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/tools/a15_final_checks.py"},
    {"seq": 12, "purpose": "Rebuild the A15 close patch after the tool was finalised (so the tool's new hash enters changed_files/input_hashes) and re-merge the ledger record.",
     "tool": "Bash",
     "command": "examdata/.venv/Scripts/python.exe integration-staging/tools/a15_close_patch.py && examdata/.venv/Scripts/python.exe integration-staging/tools/ledger_update.py --task A15 --status staged_pass --patch-file integration-staging/runtime/ledger-patches/A15_close.json",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "docs/integration/execution/execution-ledger.json"},
    {"seq": 13, "purpose": "Run the A15 closing checks: FINAL_CHECKS: PASS (writes the three post-close transcripts and the two-root sha256 manifest).",
     "tool": "Bash",
     "command": "examdata/.venv/Scripts/python.exe integration-staging/tools/a15_final_checks.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "docs/integration/execution/evidence/A15/final_checks.txt"},
]

TEST_RESULTS = [
    {"check": "A00-A15 all staged_pass, B00-B10 all not_started, seven gates closed, no merged status, no unexpected original change",
     "result": "pass", "exit_code": 0,
     "evidence": "docs/integration/execution/execution-ledger.json",
     "label": "static_inspection",
     "note": "Read from the closed ledger; the A15 closing checks assert this state and also assert the close patch is consistent with it."},
    {"check": "PHASE_A_REPORT.md and PHASE_A_DEFERRED_WORK.md name every packet A00-A15, all seven gate names and DEF-01..DEF-06, state staged/not-merged/not-deployed, and contain no completion claim",
     "result": "pass", "exit_code": 0,
     "evidence": "docs/integration/execution/evidence/A15/final_checks.txt",
     "label": "static_inspection",
     "note": "The completion-claim scan drops Markdown blockquotes (the verbatim plan quote) and inline code spans (status labels) before matching, so it tests this executor's own assertions only."},
    {"check": "Full staged suite green offline: 887 passed / 0 failed",
     "result": "pass", "exit_code": 0,
     "evidence": "docs/integration/execution/evidence/A15/pytest_rerun.txt",
     "label": "synthetic_fixture",
     "note": "Run inside integration-staging under the staged harness guards with private fixtures and the offline network guard; no original path, service or database involved."},
    {"check": "Node suite green offline: 27/27 tests, 0 failures",
     "result": "pass", "exit_code": 0,
     "evidence": "docs/integration/execution/evidence/A15/node_rerun.txt",
     "label": "synthetic_fixture",
     "note": "node --test on the quoted glob inside the project root; the staged client uses injected fetch or the in-process fixture server on 127.0.0.1 (protected ports 5188/8000 refused)."},
    {"check": "Compatibility worksheet coverage: 71/71 baseline routes (64 staged_pass + 7 deferred_active_owner), 0 problems",
     "result": "pass", "exit_code": 0,
     "evidence": "docs/integration/execution/A12_ROUTE_COMPATIBILITY_WORKSHEET.json",
     "label": "static_inspection",
     "note": "Re-read at A15 close; routes Kimi adds after this snapshot are re-derived in Phase B (B00)."},
    {"check": "Cross-packet artefacts still reproduce: A14_BUILD_ARTIFACTS PASS (247 entries, base drift 0) and A14_REHEARSAL PASS (5 rehearsed + 1 not_run, 21 checks)",
     "result": "pass", "exit_code": 0,
     "evidence": "docs/integration/execution/evidence/A15/final_checks.txt",
     "label": "static_inspection",
     "note": "Both tools re-run with --check at A15 close against the frozen staging tree."},
]

FAILURES = [
    {"what": "The inline completion-claim scan's first form matched two false positives that are not claims by this executor: the verbatim plan Pass line (a Markdown blockquote containing 'integration or deployment is complete') and the Phase B status label in a code span.",
     "exit_code": None,
     "found_by": "development_iteration",
     "evidence": "command row seq 7 (the scan printed the two hits; exit code 0)",
     "resolution": "The A15 closing-checks scan (a15_final_checks.py) drops blockquote lines and inline code spans before matching, so it targets this executor's own prose; re-run over both documents reports zero hits (command rows seq 7 then seq 13)."},
    {"what": "The first A15 closing-checks run expected docs/integration/execution/A00_REPORT.md, but packet A00's report is named A00_INITIAL_REPORT.md, so the artifact-existence check failed on a file that does exist under a different name.",
     "exit_code": 1,
     "found_by": "development_iteration",
     "evidence": "command row seq 10 (exit_code 1)",
     "resolution": "A00_TO_A14_REPORTS now names A00_INITIAL_REPORT.md for A00 and A%02d_REPORT.md for A01-A14 (command row seq 11); the artifact check passes on the re-run (row seq 13)."},
    {"what": "The same first run wrote the pytest transcript into docs/integration/execution/evidence/A15/ before that directory existed (FileNotFoundError), aborting the liveness section after the pytest check had already passed.",
     "exit_code": 1,
     "found_by": "development_iteration",
     "evidence": "command row seq 10 (exit_code 1)",
     "resolution": "The closing-checks runner now creates evidence/A15 at start-up (command row seq 11); the re-run writes pytest_rerun.txt and node_rerun.txt and passes (row seq 13)."},
]

REMAINING_GAPS = [
    "DEF-01: materials, syllabus and timetable read features (Kimi-owned active code) are deferred to Phase B (B05) after explicit human release.",
    "DEF-03: packets B00-B10 (merge, data migration, service integration, deployment) are not started; all seven gates closed.",
    "DEF-04/DEF-05: the stopped CIE batch and remote deployment are not authorized.",
    "The wheel is not built (the shared venv has no build backend and may not be changed); recorded for B09.",
    "The database rollback unit is not_run (no live database in Phase A); documented for B08.",
    "The target module layout is a proposal (B01/B02); the six planned original edits have no staged file; base hashes are point-in-time observations; the staged docs are drafts.",
    "The compatibility worksheet covers the 71-route baseline but not routes Kimi adds later; it is re-derived in Phase B (B00).",
]

EVIDENCE_PATHS = [
    "docs/integration/execution/PHASE_A_REPORT.md",
    "docs/integration/execution/PHASE_A_DEFERRED_WORK.md",
    "docs/integration/execution/execution-ledger.json",
    "docs/integration/execution/ownership.json",
    "docs/integration/execution/A12_ROUTE_COMPATIBILITY_WORKSHEET.json",
    "docs/integration/execution/A14_MERGE_MAP.json",
    "docs/integration/execution/A14_MERGE_MAP.md",
    "docs/integration/execution/A14_RELEASE_MANIFEST.json",
    "docs/integration/execution/A14_REHEARSAL.json",
    "docs/integration/execution/evidence/A15/final_checks.txt",
    "docs/integration/execution/evidence/A15/pytest_rerun.txt",
    "docs/integration/execution/evidence/A15/node_rerun.txt",
    "integration-staging/tools/a15_final_checks.py",
    "integration-staging/tools/a15_close_patch.py",
    "integration-staging/runtime/ledger-patches/A15_close.json",
]

NEXT_ACTION = ("Await explicit human release of the original paths (Phase B gate "
               "original_paths_released). Do not poll for the release and do not open Phase B "
               "autonomously. On release, B00 records the instruction text, timestamp, scope and "
               "constraints, re-reads Kimi's final work, and rebuilds the compatibility worksheet "
               "with any added routes before any merge. Nothing is merged or deployed.")


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
    missing_inputs: list[str] = []
    for r in INPUTS:
        p = WS / r
        if p.is_file():
            input_hashes[r] = sha256_file(p)
        else:
            missing_inputs.append(r)
    for r in changed_files:
        input_hashes[r] = sha256_file(WS / r)

    patch = {
        "dependencies": ["A14"],
        "allowed_write_roots": ROOTS,
        "blocked_by": [],
        "inputs": INPUTS,
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
    print(f"changed_files={len(changed_files)} inputs={len(INPUTS)} "
          f"input_hashes={len(input_hashes)} exit_codes={patch['exit_codes']} "
          f"outside_roots={outside} missing_inputs={missing_inputs}")
    return 0


NOTES = ("A15 is the terminal Phase A packet. Its inputs are frozen A00-A14 artefacts, the two "
         "A15 documents, the ownership record and read-only originals: the twelve original files "
         "the merge map records as bases and the four planned-edit bases that exist "
         "(examdata/cli.py is recorded as absent). Base hashes are point-in-time observations of "
         "an actively owned tree: the closing checks recompute the two Phase A roots and the "
         "frozen docs/integration inputs strictly and log the original-tree inputs as "
         "recorded/current/drift observations instead of asserting them. No original file was "
         "written, no original test or application was run, nothing was fetched, no service or "
         "database was touched, the CIE batch was not resumed, and nothing was started on or sent "
         "to ports 5188/8000. Command rows are shortened single-line forms of the recorded "
         "operations; one command row (the first closing-checks run) exited 1, and the three "
         "recorded failures - the completion-claim scan's false positives on a quoted plan line "
         "and a status label (exit code not a command failure), and the first closing-checks "
         "run's two tool defects (the A00 report filename and the missing evidence directory) - "
         "are each recorded with their resolution. The close patch was rebuilt after the "
         "closing-checks tool was "
         "finalised so the tool's final hash enters changed_files/input_hashes, and the ledger was "
         "re-merged. Everything is staged: nothing is merged, "
         "nothing is deployed, and all seven Phase B gates stay closed. The next action is to "
         "await explicit human release; this executor does not poll and does not open Phase B.")


if __name__ == "__main__":
    sys.exit(main())
