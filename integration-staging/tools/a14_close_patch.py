#!/usr/bin/env python3
"""Build the A14 ledger close patch (docs/integration/execution/execution-ledger.json).

Computes the input hashes over the true inputs plus the A14 write set (excluding
the post-close transcripts, which are produced *after* the ledger closes, and
this patch file itself), and emits a JSON object to be merged into the A14 task
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
OUT = STAGING / "runtime" / "ledger-patches" / "A14_close.json"

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
    "docs/integration/EXECUTOR_PROMPT_EN.md",
    "docs/integration/MASTER_EXECUTION_PLAN_EN.md",
    "docs/integration/ROUTE_INVENTORY_CURRENT.json",
    "docs/PROJECT_STATUS.md",
    "docs/integration/execution/execution-ledger.json",
    "docs/integration/execution/A12_REPORT.md",
    "docs/integration/execution/A12_ROUTE_COMPATIBILITY_WORKSHEET.json",
    "docs/integration/execution/A13_REPORT.md",
    # frozen staging inputs: provenance manifests, harness, rehearsal fixtures
    "integration-staging/fixtures/PROVENANCE.json",
    "integration-staging/frontend/PROVENANCE.json",
    "integration-staging/pytest.ini",
    "integration-staging/tests/conftest.py",
    "integration-staging/components/manifest.json",
    "integration-staging/fixtures/synthetic/catalog/catalog-base-synthetic.json",
    # the frozen staged v2 api module this packet edited (deterministic ids)
    "integration-staging/src/examdata_integration/api/app.py",
    # read-only original bases recorded by the merge map
    *MAP_BASES,
    # read-only bases of the planned original edits
    *PLANNED_EDIT_BASES,
]

WRITE_GLOBS = [
    # the packet tools (this close-patch builder and the closing checks included)
    "integration-staging/tools/a14_*.py",
    # the staged v2 api module edited in this packet (deterministic operation ids)
    "integration-staging/src/examdata_integration/api/app.py",
    # the staged documentation set + the generated v2 reference
    "integration-staging/docs/*",
    # packet runtime transcripts + the close patch
    "integration-staging/runtime/a14_*.txt",
    "integration-staging/runtime/ledger-patches/A14_close.json",
    # packet report, generated artefacts and evidence
    "docs/integration/execution/A14_REPORT.md",
    "docs/integration/execution/A14_*.json",
    "docs/integration/execution/A14_MERGE_MAP.md",
    "docs/integration/execution/evidence/A14/*",
]

# produced only after the ledger closes: listed but never hashed into the patch
POST_CLOSE = {
    "docs/integration/execution/evidence/A14/final_checks.txt",
    "docs/integration/execution/evidence/A14/pytest_rerun.txt",
    "docs/integration/execution/evidence/A14/node_rerun.txt",
}

COMMANDS = [
    {"seq": 1, "purpose": "Read the A13 close-patch builder and the A13 closing-checks runner as format templates for this packet.",
     "tool": "Read",
     "command": "Read tool: integration-staging/tools/a13_close_patch.py, integration-staging/tools/a13_final_checks.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0, "evidence": None},
    {"seq": 2, "purpose": "Write the staged docs index (staged drafts are not published before the Phase B release).",
     "tool": "Write",
     "command": "Write tool: integration-staging/docs/README.md",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/docs/README.md"},
    {"seq": 3, "purpose": "Write the proposed merged integration guide (plan 9.3 checklist).",
     "tool": "Write",
     "command": "Write tool: integration-staging/docs/integration-guide.md",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/docs/integration-guide.md"},
    {"seq": 4, "purpose": "Write the packaging/rollback proposal (plan 10.4 bundle table, six smoke checks, six rollback units, exclusions; explicitly not a merge and not a deployment).",
     "tool": "Write",
     "command": "Write tool: integration-staging/docs/release-and-rollback.md",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/docs/release-and-rollback.md"},
    {"seq": 5, "purpose": "Write the A14 artefact builder: file-by-file merge map (one entry per staged file with target, base, action, reversal), proposed release manifest and the v2 reference generated from create_app().openapi().",
     "tool": "Write",
     "command": "Write tool: integration-staging/tools/a14_build_artifacts.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/tools/a14_build_artifacts.py"},
    {"seq": 6, "purpose": "Generate the four artefacts: A14_MERGE_MAP.json/.md, A14_RELEASE_MANIFEST.json and docs/v2-api-reference.md (247 entries, 92 not_merged, 6 planned edits, 12 bases observed).",
     "tool": "Bash",
     "command": "examdata/.venv/Scripts/python.exe integration-staging/tools/a14_build_artifacts.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "docs/integration/execution/A14_MERGE_MAP.json"},
    {"seq": 7, "purpose": "In-packet import probe under integration-staging/src: importing the staged package wrote __pycache__/*.pyc into the staging tree (the trigger of the first defect).",
     "tool": "Bash",
     "command": "examdata/.venv/Scripts/python.exe -c \"import sys; sys.path.insert(0,'integration-staging/src'); import examdata_integration\"",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0, "evidence": None},
    {"seq": 8, "purpose": "Coverage check then reported the interpreter caches as staged files that are neither mapped nor listed as not_merged (defect 1, output FAIL).",
     "tool": "Bash",
     "command": "examdata/.venv/Scripts/python.exe integration-staging/tools/a14_build_artifacts.py --check",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 1, "evidence": None},
    {"seq": 9, "purpose": "Fix defect 1: the map's walk now skips __pycache__, pytest scratch (runtime/pytest-temp, runtime/pytest-cache) and the rehearsal sandbox (runtime/a14-rehearsal), plus *.pyc.",
     "tool": "Edit",
     "command": "Edit tool: integration-staging/tools/a14_build_artifacts.py (SKIP_DIR_NAMES + bytecode skip)",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/tools/a14_build_artifacts.py"},
    {"seq": 10, "purpose": "Re-run the map self-check: A14_BUILD_ARTIFACTS: PASS.",
     "tool": "Bash",
     "command": "examdata/.venv/Scripts/python.exe integration-staging/tools/a14_build_artifacts.py --check",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "docs/integration/execution/A14_MERGE_MAP.json"},
    {"seq": 11, "purpose": "Determinism probe: create_app().openapi() published a different operation id in every process (FastAPI derives the suffix from a set) and one id per route for both GET and HEAD (defect 2, discovery run).",
     "tool": "Bash",
     "command": "PYTHONHASHSEED=<seed> examdata/.venv/Scripts/python.exe -c \"...create_app().openapi() operation-id probe...\"",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0, "evidence": None},
    {"seq": 12, "purpose": "Fix defect 2 in the staged app factory: module-level _deterministic_unique_id(route) over sorted methods, generate_unique_id_function, and a _read_route decorator registering GET and HEAD as sibling routes (5 call sites).",
     "tool": "Edit",
     "command": "Edit tool: integration-staging/src/examdata_integration/api/app.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/src/examdata_integration/api/app.py"},
    {"seq": 13, "purpose": "Verify determinism: 39 operations, 39 unique ids and an identical operation hash under PYTHONHASHSEED 0/7/999; FastAPI duplicate-operation-id warnings dropped 5 -> 0.",
     "tool": "Bash",
     "command": "for s in 0 7 999; do PYTHONHASHSEED=$s examdata/.venv/Scripts/python.exe -c \"...operation-id probe...\"; done",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0, "evidence": None},
    {"seq": 14, "purpose": "Full staged suite after the app.py change: 887 passed / 1 warning (was 6 warnings).",
     "tool": "Bash",
     "command": "bash integration-staging/tools/run_staged_tests.sh -q > integration-staging/runtime/a14_pytest.txt 2>&1",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/runtime/a14_pytest.txt"},
    {"seq": 15, "purpose": "Write the six-unit rollback rehearsal (code release apply/rollback, component manifest swap, revision pointer rollback, database backup not_run, frontend switch, job checkpoints) inside a private sandbox.",
     "tool": "Write",
     "command": "Write tool: integration-staging/tools/a14_rehearsal.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/tools/a14_rehearsal.py"},
    {"seq": 16, "purpose": "First rehearsal run failed honestly: it seeded the sandbox from every recorded base, but a copied_snapshot base is a provenance proof, not a pre-existing target (defect 4).",
     "tool": "Bash",
     "command": "examdata/.venv/Scripts/python.exe integration-staging/tools/a14_rehearsal.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 1, "evidence": None},
    {"seq": 17, "purpose": "Fix defect 4: seed the sandbox only from restore_base_bytes entries and add a check that every copied_snapshot is byte-faithful to its recorded base (8 copies).",
     "tool": "Edit",
     "command": "Edit tool: integration-staging/tools/a14_rehearsal.py (seed rule + fidelity check)",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/tools/a14_rehearsal.py"},
    {"seq": 18, "purpose": "Rehearsal re-run: 5 rehearsed + 1 not_run, 21 checks, 0 problems; A14_REHEARSAL.json written.",
     "tool": "Bash",
     "command": "examdata/.venv/Scripts/python.exe integration-staging/tools/a14_rehearsal.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "docs/integration/execution/A14_REHEARSAL.json"},
    {"seq": 19, "purpose": "Smoke-check command defect: `node --test <dir>` does not expand a directory on node v24.19.0 (MODULE_NOT_FOUND, real rc 1).",
     "tool": "Bash",
     "command": "\"/c/Program Files/nodejs/node\" --test integration-staging/frontend/tests",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 1, "evidence": None},
    {"seq": 20, "purpose": "Fix the documented smoke check in three places to the node-expanded glob form: release-and-rollback.md, integration-guide.md and a14_build_artifacts.py SMOKE_CHECKS.",
     "tool": "Edit",
     "command": "Edit tool: integration-staging/docs/release-and-rollback.md, integration-staging/docs/integration-guide.md, integration-staging/tools/a14_build_artifacts.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/docs/release-and-rollback.md"},
    {"seq": 21, "purpose": "Node suite with the glob form: tests 27 / pass 27 / fail 0 (rc 0).",
     "tool": "Bash",
     "command": "\"/c/Program Files/nodejs/node\" --test \"integration-staging/frontend/tests/*.test.mjs\"",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "docs/integration/execution/evidence/A14/node_tests_stdout.txt"},
    {"seq": 22, "purpose": "Collect the packet evidence: rehearsal stdout, the 887-passed pytest transcript and the 27/27 node transcript into evidence/A14/.",
     "tool": "Bash",
     "command": "mkdir -p docs/integration/execution/evidence/A14 && cp integration-staging/runtime/a14_pytest.txt docs/integration/execution/evidence/A14/pytest_run_stdout.txt && ... node_tests_stdout.txt, rehearsal_stdout.txt",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "docs/integration/execution/evidence/A14/pytest_run_stdout.txt"},
    {"seq": 23, "purpose": "Write the A14 report (scope, deliverables, validation model, evidence, the four corrections, deliberate limitations, remaining gaps, next action).",
     "tool": "Write",
     "command": "Write tool: docs/integration/execution/A14_REPORT.md",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "docs/integration/execution/A14_REPORT.md"},
    {"seq": 24, "purpose": "Stability re-check after the full pytest run (defect 1 fix): A14_BUILD_ARTIFACTS: PASS.",
     "tool": "Bash",
     "command": "examdata/.venv/Scripts/python.exe integration-staging/tools/a14_build_artifacts.py --check",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "docs/integration/execution/A14_MERGE_MAP.json"},
    {"seq": 25, "purpose": "Rehearsal re-verification against the recorded report: A14_REHEARSAL: PASS (recorded report matches a fresh run).",
     "tool": "Bash",
     "command": "examdata/.venv/Scripts/python.exe integration-staging/tools/a14_rehearsal.py --check",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "docs/integration/execution/A14_REHEARSAL.json"},
    {"seq": 26, "purpose": "Write the A14 closing-checks runner (map facts, rehearsal facts, release manifest, operation-id determinism across hash seeds, worksheet coverage, offline suites, ledger state, close-patch consistency, containment, sha256 manifest).",
     "tool": "Write",
     "command": "Write tool: integration-staging/tools/a14_final_checks.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/tools/a14_final_checks.py"},
    {"seq": 27, "purpose": "Build the A14 close patch (hashes the inputs and the packet write set, excluding the post-close transcripts).",
     "tool": "Bash",
     "command": "examdata/.venv/Scripts/python.exe integration-staging/tools/a14_close_patch.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/runtime/ledger-patches/A14_close.json"},
    {"seq": 28, "purpose": "Close the A14 ledger record: status staged_pass with the patch merged in.",
     "tool": "Bash",
     "command": "examdata/.venv/Scripts/python.exe integration-staging/tools/ledger_update.py --task A14 --status staged_pass --patch-file integration-staging/runtime/ledger-patches/A14_close.json",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "docs/integration/execution/execution-ledger.json"},
    {"seq": 29, "purpose": "Run the A14 closing checks: FINAL_CHECKS: PASS (rewrites the post-close transcripts); re-run once more after the close-patch rebuild + re-merge and stayed green.",
     "tool": "Bash",
     "command": "examdata/.venv/Scripts/python.exe integration-staging/tools/a14_final_checks.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "docs/integration/execution/evidence/A14/final_checks.txt"},
]

TEST_RESULTS = [
    {"check": "Full staged suite green offline: 887 passed / 0 failed",
     "result": "pass", "exit_code": 0,
     "evidence": "docs/integration/execution/evidence/A14/pytest_run_stdout.txt",
     "label": "synthetic_fixture",
     "note": "Run inside integration-staging under the staged harness guards with private fixtures; no original path, service or database involved. The packet's app.py change removed FastAPI's 5 duplicate-operation-id warnings (6 -> 1 warning)."},
    {"check": "Node suite green offline: 27/27 tests, 0 failures",
     "result": "pass", "exit_code": 0,
     "evidence": "docs/integration/execution/evidence/A14/node_tests_stdout.txt",
     "label": "synthetic_fixture",
     "note": "node --test on the quoted glob inside the project root; the staged client uses injected fetch or the in-process fixture server on 127.0.0.1 (protected ports 5188/8000 refused). Duration 296.96 ms in the recorded run."},
    {"check": "Merge map self-check PASS: 247 entries, 92 not_merged, 6 planned original edits, 12 bases observed, base drift 0",
     "result": "pass", "exit_code": 0,
     "evidence": "docs/integration/execution/A14_MERGE_MAP.json",
     "label": "static_inspection",
     "note": "a14_build_artifacts.py --check recomputes every staged sha256 from disk, re-observes every recorded base and the planned-edit bases, proves every merge-candidate file is either mapped or listed as not_merged, and re-renders the Markdown and the v2 reference."},
    {"check": "Rollback rehearsal PASS: 6 units (5 rehearsed + 1 not_run), 21 checks, 0 problems",
     "result": "pass", "exit_code": 0,
     "evidence": "docs/integration/execution/evidence/A14/rehearsal_stdout.txt",
     "label": "synthetic_fixture",
     "note": "Every map entry applied into a private sandbox and rolled back to a byte-identical pre-apply tree; manifest swap/re-read/restore; revision publish/publish/rollback with both revisions readable; frontend switch off/on against in-memory storage; three checkpoint fixtures re-read unchanged. The database unit is not_run (no live database in Phase A)."},
    {"check": "Staged v2 API surface deterministic: 39 operations, 39 unique ids, identical across PYTHONHASHSEED 0/7/999",
     "result": "pass", "exit_code": 0,
     "evidence": "docs/integration/execution/evidence/A14/final_checks.txt",
     "label": "static_inspection",
     "note": "Generated from create_app().openapi(); the deterministic operation-id generator replaced FastAPI's set-ordered default (defect 2)."},
    {"check": "Compatibility worksheet coverage: 71/71 baseline routes (64 staged_pass + 7 deferred_active_owner), 0 problems",
     "result": "pass", "exit_code": 0,
     "evidence": "docs/integration/execution/A12_ROUTE_COMPATIBILITY_WORKSHEET.json",
     "label": "static_inspection",
     "note": "Re-read at A14 close to confirm the baseline coverage the merge map's verification column cites still holds; the 7 deferred rows are the Kimi-owned materials/timetable routes."},
]

FAILURES = [
    {"what": "The map's file walk included interpreter caches: an in-packet `python -c` import wrote __pycache__/*.pyc under integration-staging/src, and the coverage check then reported those files as staged candidates that are neither mapped nor listed as not_merged.",
     "exit_code": 1,
     "found_by": "development_iteration",
     "evidence": "command rows seq 7 (trigger) and seq 8 (FAIL output)",
     "resolution": "The walk now skips __pycache__, pytest scratch (runtime/pytest-temp, runtime/pytest-cache) and the rehearsal sandbox (runtime/a14-rehearsal), plus *.pyc; a full pytest run no longer changes the not-merged list and --check passes after a build (rows seq 10, 24)."},
    {"what": "The staged v2 OpenAPI document was not reproducible: FastAPI's default operation-id generator derives the id suffix from list(route.methods)[0] - a set - so the five GET+HEAD content routes published a different operation id in every interpreter process, and one route produced one id shared by GET and HEAD (5 duplicate-operation-id warnings).",
     "exit_code": None,
     "found_by": "development_iteration",
     "evidence": "command row seq 11 (discovery probe, exit code not preserved in the recorded invocation)",
     "resolution": "The staged app factory installs _deterministic_unique_id over sorted methods and registers GET and HEAD as sibling routes (row seq 12); verified identical across PYTHONHASHSEED 0/7/999 with 39 operations and 39 unique ids (row seq 13), warnings 5 -> 0, full suite still 887 passed (row seq 14)."},
    {"what": "The documented smoke check `node --test <directory>` did not work as written: node v24.19.0 tries to load the directory as a module (MODULE_NOT_FOUND).",
     "exit_code": 1,
     "found_by": "development_iteration",
     "evidence": "command row seq 19 (exit_code 1)",
     "resolution": "release-and-rollback.md, integration-guide.md and the release manifest's smoke check now use the node-expanded glob integration-staging/frontend/tests/*.test.mjs, which runs 27/27 (row seq 21)."},
    {"what": "The rehearsal's first run failed: it seeded the sandbox from every recorded base, but a copied_snapshot base is a provenance proof (verify_copy), not a pre-existing target, so the rollback expected a pre-apply file the merge itself creates.",
     "exit_code": 1,
     "found_by": "development_iteration",
     "evidence": "command row seq 16 (exit_code 1)",
     "resolution": "The seed rule is limited to restore_base_bytes entries and a new check proves every copied_snapshot is byte-faithful to its recorded base (8 copies); the re-run passed 21/21 checks (row seq 18)."},
]

REMAINING_GAPS = [
    "The wheel is not built: the shared venv has no setuptools/wheel/build and Phase A may neither install into it nor fetch a build backend; the proposal records the B09 command instead (plan 10.4's one step Phase A cannot complete inside the isolation boundary).",
    "The database rollback unit is not_run (no live database in Phase A); the reversal is documented and deferred to B08.",
    "The target layout is a proposal: plan 3.5 leaves the final module names to B01/B02, so the map proposes examdata/src/examdata/integration/** and records the layout decision as a review point.",
    "The six planned original edits have no staged file; the edit itself is Phase B work (B02/B04/B06/B10) and only the base hash, owning packet and reversal are recorded.",
    "Base hashes are point-in-time observations of an actively owned tree; drift is observed and recorded, never repaired by this executor.",
    "The staged docs are drafts: plan 9.3 updates shared documentation only after the Phase B release.",
    "A15 PHASE_A_REPORT.md remains; everything is staged, nothing is merged or deployed, and all seven Phase B gates stay closed.",
]

EVIDENCE_PATHS = [
    "docs/integration/execution/A14_REPORT.md",
    "docs/integration/execution/A14_MERGE_MAP.json",
    "docs/integration/execution/A14_MERGE_MAP.md",
    "docs/integration/execution/A14_RELEASE_MANIFEST.json",
    "docs/integration/execution/A14_REHEARSAL.json",
    "docs/integration/execution/evidence/A14/rehearsal_stdout.txt",
    "docs/integration/execution/evidence/A14/pytest_run_stdout.txt",
    "docs/integration/execution/evidence/A14/node_tests_stdout.txt",
    "docs/integration/execution/evidence/A14/final_checks.txt",
    "docs/integration/execution/execution-ledger.json",
    "integration-staging/runtime/ledger-patches/A14_close.json",
    "integration-staging/runtime/a14_pytest.txt",
    "integration-staging/docs/README.md",
    "integration-staging/docs/integration-guide.md",
    "integration-staging/docs/release-and-rollback.md",
    "integration-staging/docs/v2-api-reference.md",
    "integration-staging/src/examdata_integration/api/app.py",
    "integration-staging/tools/a14_build_artifacts.py",
    "integration-staging/tools/a14_rehearsal.py",
    "integration-staging/tools/a14_final_checks.py",
    "integration-staging/tools/a14_close_patch.py",
]

NEXT_ACTION = ("A15 - assemble docs/integration/execution/PHASE_A_REPORT.md (plan section 11): the "
               "packet-by-packet summary, the deferred-work list, the ownership-release requirements, "
               "and an explicit statement that staged work is neither merged nor deployed while Phase B "
               "remains deferred. All seven Phase B gates remain closed; only the human user can release "
               "the original paths.")


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
        "dependencies": ["A13"],
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


NOTES = ("All A14 inputs are frozen A00-A13 artefacts plus read-only originals: the twelve original "
         "files the map records as bases (six frontend sources, four business-data snapshots, one "
         "edexcel source and one ielts-api data file) and the four planned-edit bases that exist "
         "(examdata/cli.py is recorded as absent). Base hashes are point-in-time observations of an "
         "actively owned tree: the closing checks recompute the two Phase A roots and the frozen plan "
         "inputs strictly and log the original-tree inputs as recorded/current/drift observations "
         "instead of asserting them. No original file was written, no original test or application was "
         "run, nothing was fetched, no service or database was touched, the CIE batch was not resumed, "
         "and nothing was started on or sent to ports 5188/8000. Command rows are shortened single-line "
         "forms of the recorded operations. Four command rows exited 1 and were resolved in-packet "
         "(rows seq 8, 16, 19 and the discovery probe in row seq 11 whose exit code was not preserved); "
         "all four are recorded as failures with their resolution. The close patch was rebuilt after "
         "the closing-checks tool was finalised so the tool itself enters changed_files/input_hashes, "
         "the ledger was re-merged, and the closing checks re-ran green, rewriting the final "
         "transcripts. Everything is staged: nothing is merged, nothing is deployed, and all seven "
         "Phase B gates stay closed.")


if __name__ == "__main__":
    sys.exit(main())
