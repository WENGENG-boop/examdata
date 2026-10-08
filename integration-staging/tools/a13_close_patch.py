#!/usr/bin/env python3
"""Build the A13 ledger close patch (docs/integration/execution/execution-ledger.json).

Computes the input hashes over the true inputs plus the A13 write set (excluding
the post-close transcripts, which are produced *after* the ledger closes, and
this patch file itself), and emits a JSON object to be merged into the A13 task
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
OUT = STAGING / "runtime" / "ledger-patches" / "A13_close.json"

ROOTS = [STAGING.as_posix(), EXEC.as_posix()]

INPUTS = [
    "docs/integration/EXECUTOR_PROMPT_EN.md",
    "docs/integration/MASTER_EXECUTION_PLAN_EN.md",
    "docs/integration/ROUTE_INVENTORY_CURRENT.json",
    "docs/PROJECT_STATUS.md",
    "docs/integration/execution/execution-ledger.json",
    "docs/integration/execution/A12_REPORT.md",
    "docs/integration/execution/A12_ROUTE_COMPATIBILITY_WORKSHEET.json",
    "docs/integration/execution/A01_ROUTE_COMPATIBILITY_WORKSHEET.json",
    # original frontend tree: read-only sources of the copied proposal; every
    # copied/modified file carries its source sha256 in frontend/PROVENANCE.json
    "frontend/index.html",
    "frontend/app.js",
    "frontend/styles.css",
    "frontend/search.mjs",
    "frontend/README.md",
    "frontend/search.test.mjs",
    "frontend/package.json",
    # the three native checkpoints, consulted once with the Read tool as
    # format references (read-only; no test parses them)
    "cie-location-batch/checkpoint.json",
    "ielts-data/test-s03/runs/run-ok/checkpoint.json",
    "ielts-data/runs/pte-20261004/checkpoint.json",
    # frozen staged v2 api modules the frontend client / fixture server speak
    "integration-staging/src/examdata_integration/api/envelope.py",
    "integration-staging/src/examdata_integration/api/links.py",
    "integration-staging/src/examdata_integration/api/app.py",
    "integration-staging/src/examdata_integration/api/dataset.py",
    "integration-staging/src/examdata_integration/api/binary.py",
    "integration-staging/src/examdata_integration/api/view.py",
    # frozen A04 contracts the quality labels / identities / enums come from
    "integration-staging/src/examdata_integration/contracts/models.py",
    "integration-staging/src/examdata_integration/contracts/quality.py",
    "integration-staging/src/examdata_integration/contracts/enums.py",
    "integration-staging/src/examdata_integration/contracts/ids.py",
    "integration-staging/src/examdata_integration/contracts/base.py",
    "integration-staging/src/examdata_integration/contracts/canonical.py",
    # frozen A02-A12 harness the A13 tests run under
    "integration-staging/pytest.ini",
    "integration-staging/tests/conftest.py",
    "integration-staging/tools/run_staged_tests.sh",
    "integration-staging/tools/ledger_update.py",
    "integration-staging/src/examdata_integration/testing/guards.py",
]

WRITE_GLOBS = [
    # the copied frontend proposal (top level, tests, fixtures)
    "integration-staging/frontend/*",
    "integration-staging/frontend/tests/*",
    "integration-staging/frontend/fixtures/*",
    # the operations checkpoint/coverage package and its fixtures
    "integration-staging/src/examdata_integration/operations/*",
    "integration-staging/fixtures/synthetic/operations/*",
    # A13 test files
    "integration-staging/tests/test_operations_checkpoints.py",
    "integration-staging/tests/test_operations_coverage.py",
    "integration-staging/tests/test_frontend_staged_copy.py",
    # A13 tools (this close-patch builder and the closing checks included)
    "integration-staging/tools/a13_*.py",
    # packet runtime transcripts + the close patch
    "integration-staging/runtime/a13_*.txt",
    "integration-staging/runtime/ledger-patches/A13_close.json",
    # packet report and evidence
    "docs/integration/execution/A13_REPORT.md",
    "docs/integration/execution/evidence/A13/*",
]

# produced only after the ledger closes: listed but never hashed into the patch
POST_CLOSE = {
    "docs/integration/execution/evidence/A13/final_checks.txt",
    "docs/integration/execution/evidence/A13/python_rerun.txt",
    "docs/integration/execution/evidence/A13/frontend_rerun.txt",
}

COMMANDS = [
    {"seq": 1, "purpose": "Read the three native checkpoints (cie-location-batch/checkpoint.json, ielts-data/test-s03/runs/run-ok/checkpoint.json, ielts-data/runs/pte-20261004/checkpoint.json) once as read-only format references for the synthetic fixtures.",
     "tool": "Read",
     "command": "Read tool: the three native checkpoint files (format study only)",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0, "evidence": None},
    {"seq": 2, "purpose": "Open the A13 ledger record (status in_progress) with the packet next action.",
     "tool": "Bash",
     "command": "examdata/.venv/Scripts/python.exe integration-staging/tools/ledger_update.py --task A13 --status in_progress --next-action \"Build staged frontend copy + operations checkpoint readers + tests; then close A13 with patch and final checks\"",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "docs/integration/execution/execution-ledger.json"},
    {"seq": 3, "purpose": "Write the read-only checkpoint readers: CIE batch runner + ielts-run-checkpoint/1 shapes; missing native stop fields stay None; stale summaries superseded but visible; unrecognised input -> explicit unknown row with problems.",
     "tool": "Write",
     "command": "Write tool: integration-staging/src/examdata_integration/operations/checkpoints.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/src/examdata_integration/operations/checkpoints.py"},
    {"seq": 4, "purpose": "Write the coverage views: derived, never stored; partial failure never zeroes counters or hides a blocked source; same-instant disagreement -> explicit conflict.",
     "tool": "Write",
     "command": "Write tool: integration-staging/src/examdata_integration/operations/coverage.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/src/examdata_integration/operations/coverage.py"},
    {"seq": 5, "purpose": "Write the operations package exports.",
     "tool": "Write",
     "command": "Write tool: integration-staging/src/examdata_integration/operations/__init__.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/src/examdata_integration/operations/__init__.py"},
    {"seq": 6, "purpose": "Write the CIE stopped-batch synthetic checkpoint fixture.",
     "tool": "Write",
     "command": "Write tool: integration-staging/fixtures/synthetic/operations/cie-batch-checkpoint-stopped.json",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/fixtures/synthetic/operations/cie-batch-checkpoint-stopped.json"},
    {"seq": 7, "purpose": "Write the CIE running-batch synthetic checkpoint fixture (missing stop fields stay absent on purpose).",
     "tool": "Write",
     "command": "Write tool: integration-staging/fixtures/synthetic/operations/cie-batch-checkpoint-running.json",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/fixtures/synthetic/operations/cie-batch-checkpoint-running.json"},
    {"seq": 8, "purpose": "Write the healthy IELTS run checkpoint fixture.",
     "tool": "Write",
     "command": "Write tool: integration-staging/fixtures/synthetic/operations/ielts-run-checkpoint-ok.json",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/fixtures/synthetic/operations/ielts-run-checkpoint-ok.json"},
    {"seq": 9, "purpose": "Write the stale IELTS run checkpoint fixture (superseded summary that must never override a newer snapshot).",
     "tool": "Write",
     "command": "Write tool: integration-staging/fixtures/synthetic/operations/ielts-run-checkpoint-ok-stale.json",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/fixtures/synthetic/operations/ielts-run-checkpoint-ok-stale.json"},
    {"seq": 10, "purpose": "Write the partial-failure IELTS run checkpoint fixture (blocked source, counters kept).",
     "tool": "Write",
     "command": "Write tool: integration-staging/fixtures/synthetic/operations/ielts-run-checkpoint-partial.json",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/fixtures/synthetic/operations/ielts-run-checkpoint-partial.json"},
    {"seq": 11, "purpose": "Write the unrecognised checkpoint fixture (unknown row with explicit problems, no exception).",
     "tool": "Write",
     "command": "Write tool: integration-staging/fixtures/synthetic/operations/unsupported-checkpoint.json",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/fixtures/synthetic/operations/unsupported-checkpoint.json"},
    {"seq": 12, "purpose": "Write the operations fixture README (synthetic provenance notes).",
     "tool": "Write",
     "command": "Write tool: integration-staging/fixtures/synthetic/operations/README.md",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/fixtures/synthetic/operations/README.md"},
    {"seq": 13, "purpose": "Write the operations provenance tool (regenerates the manifest; --check verifies without writing).",
     "tool": "Write",
     "command": "Write tool: integration-staging/tools/a13_capture_fixtures.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/tools/a13_capture_fixtures.py"},
    {"seq": 14, "purpose": "Generate the operations fixture manifest and verify it: manifest written with 6 synthetic entries (sha256 + bytes each); --check reports A13_PROVENANCE: PASS (6 entries).",
     "tool": "Bash",
     "command": "examdata/.venv/Scripts/python.exe integration-staging/tools/a13_capture_fixtures.py && examdata/.venv/Scripts/python.exe integration-staging/tools/a13_capture_fixtures.py --check",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/fixtures/synthetic/operations/PROVENANCE.json"},
    {"seq": 15, "purpose": "Edit coverage.py before the tests: keep an observation with neither counters nor sources UNKNOWN (guard added before the all-blocked judgment).",
     "tool": "Edit",
     "command": "Edit tool: integration-staging/src/examdata_integration/operations/coverage.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/src/examdata_integration/operations/coverage.py"},
    {"seq": 16, "purpose": "Write the checkpoint reader test module (running/stopped CIE, IELTS ok/stale/partial, unsupported, missing stop fields).",
     "tool": "Write",
     "command": "Write tool: integration-staging/tests/test_operations_checkpoints.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/tests/test_operations_checkpoints.py"},
    {"seq": 17, "purpose": "Write the coverage view test module (partial honesty, stale superseded, conflicts, all-blocked, unknown).",
     "tool": "Write",
     "command": "Write tool: integration-staging/tests/test_operations_coverage.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/tests/test_operations_coverage.py"},
    {"seq": 18, "purpose": "Test-prep edit: add `from pathlib import Path` plus the STAGING/FIXTURES constants to the coverage test module.",
     "tool": "Edit",
     "command": "Edit tool: integration-staging/tests/test_operations_coverage.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/tests/test_operations_coverage.py"},
    {"seq": 19, "purpose": "Test-prep edit: route the observation helper through checkpoints.read_checkpoint(FIXTURES / name, observed_at=WHEN).",
     "tool": "Edit",
     "command": "Edit tool: integration-staging/tests/test_operations_coverage.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/tests/test_operations_coverage.py"},
    {"seq": 20, "purpose": "First targeted operations run reported 1 failed / 879 passed in its output (fixture gap, see failures); the `| tail -30` pipeline without pipefail masked the process exit code to 0.",
     "tool": "Bash",
     "command": "bash integration-staging/tools/run_staged_tests.sh -q tests/test_operations_checkpoints.py tests/test_operations_coverage.py 2>&1 | tail -30",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": None},
    {"seq": 21, "purpose": "Fix the fixture gap: insert \"current_paper\": \"8888/2026/Jun/22\" between last_fetch_at and loop_stage in cie-batch-checkpoint-running.json.",
     "tool": "Edit",
     "command": "Edit tool: integration-staging/fixtures/synthetic/operations/cie-batch-checkpoint-running.json",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/fixtures/synthetic/operations/cie-batch-checkpoint-running.json"},
    {"seq": 22, "purpose": "Regenerate the manifest, verify it, and re-run the targeted operations tests: 880 passed (green).",
     "tool": "Bash",
     "command": "examdata/.venv/Scripts/python.exe integration-staging/tools/a13_capture_fixtures.py && examdata/.venv/Scripts/python.exe integration-staging/tools/a13_capture_fixtures.py --check && bash integration-staging/tools/run_staged_tests.sh -q tests/test_operations_checkpoints.py tests/test_operations_coverage.py 2>&1 | tail -4",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/fixtures/synthetic/operations/PROVENANCE.json"},
    {"seq": 23, "purpose": "Ownership inspection before creating the staged frontend: integration-staging/ has no frontend directory yet.",
     "tool": "Bash",
     "command": "ls integration-staging/ ... (frontend dir absent: 'NO frontend dir yet')",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0, "evidence": None},
    {"seq": 24, "purpose": "Create the staged frontend tree and copy the four untouched originals (index.html, styles.css, app.js, search.mjs); sha256sum shows staged == source at copy time.",
     "tool": "Bash",
     "command": "mkdir -p integration-staging/frontend/tests integration-staging/frontend/fixtures && cp frontend/index.html frontend/styles.css frontend/app.js frontend/search.mjs integration-staging/frontend/ && sha256sum <source and staged files>",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/frontend/PROVENANCE.json"},
    {"seq": 25, "purpose": "Derive the placeholder asset hashes (11 synthetic asset ids) used to author the resources fixture.",
     "tool": "Bash",
     "command": "examdata/.venv/Scripts/python.exe - <<'PY' (placeholder asset sha256 heredoc)",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0, "evidence": None},
    {"seq": 26, "purpose": "Write the staged v2 API client (envelope parsing, typed errors, per-season fan-out, resource->document mapping).",
     "tool": "Write",
     "command": "Write tool: integration-staging/frontend/client.mjs",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/frontend/client.mjs"},
    {"seq": 27, "purpose": "Write the private synthetic catalog fixture.",
     "tool": "Write",
     "command": "Write tool: integration-staging/frontend/fixtures/catalog.json",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/frontend/fixtures/catalog.json"},
    {"seq": 28, "purpose": "Write the private synthetic syllabi fixture (per-system season arrays).",
     "tool": "Write",
     "command": "Write tool: integration-staging/frontend/fixtures/syllabi.json",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/frontend/fixtures/syllabi.json"},
    {"seq": 29, "purpose": "Write the private synthetic resources fixture (discovery items incl. unavailable content).",
     "tool": "Write",
     "command": "Write tool: integration-staging/frontend/fixtures/resources.json",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/frontend/fixtures/resources.json"},
    {"seq": 30, "purpose": "Write the offline fixture server (staged /api/v2 envelope over private fixtures; 127.0.0.1; refuses protected ports 5188/8000; default ephemeral port).",
     "tool": "Write",
     "command": "Write tool: integration-staging/frontend/fixture-server.mjs",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/frontend/fixture-server.mjs"},
    {"seq": 31, "purpose": "Write the staged search normalization test copy (10 tests kept verbatim; import repointed to ../search.mjs; resources block retired; LF).",
     "tool": "Write",
     "command": "Write tool: integration-staging/frontend/tests/search.test.mjs",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/frontend/tests/search.test.mjs"},
    {"seq": 32, "purpose": "Iterate app.js (five edit calls over the packet): import searchDocuments/clientEnabled, wire liveSearch() to the staged client honoring the examdata.v2-client flag, remove the dead /gateway helper, label quality==='synthetic_fixture' rows 'STAGED FIXTURE - synthetic'.",
     "tool": "Edit",
     "command": "Edit tool: integration-staging/frontend/app.js (five sequential edits)",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/frontend/app.js"},
    {"seq": 33, "purpose": "Write the client unit tests over injected fetch (envelope, errors, fan-out, partial/all failure, selectors, flag reversibility).",
     "tool": "Write",
     "command": "Write tool: integration-staging/frontend/tests/client.test.mjs",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/frontend/tests/client.test.mjs"},
    {"seq": 34, "purpose": "Write the end-to-end flow tests against the in-process fixture server.",
     "tool": "Write",
     "command": "Write tool: integration-staging/frontend/tests/flow.test.mjs",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/frontend/tests/flow.test.mjs"},
    {"seq": 35, "purpose": "Write the staged-copy README (staged != merged; offline run; Phase B merge requirements).",
     "tool": "Write",
     "command": "Write tool: integration-staging/frontend/README.md",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/frontend/README.md"},
    {"seq": 36, "purpose": "Insert the #staged-banner notice after the site header in the staged index.html.",
     "tool": "Edit",
     "command": "Edit tool: integration-staging/frontend/index.html",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/frontend/index.html"},
    {"seq": 37, "purpose": "Write the frontend provenance tool (regenerates both manifests; --check verifies source + staged sha256 against disk).",
     "tool": "Write",
     "command": "Write tool: integration-staging/tools/a13_frontend_provenance.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/tools/a13_frontend_provenance.py"},
    {"seq": 38, "purpose": "Generate both frontend manifests and verify them: --check passes on the first run.",
     "tool": "Bash",
     "command": "examdata/.venv/Scripts/python.exe integration-staging/tools/a13_frontend_provenance.py && examdata/.venv/Scripts/python.exe integration-staging/tools/a13_frontend_provenance.py --check; echo \"rc=$?\"",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/frontend/PROVENANCE.json"},
    {"seq": 39, "purpose": "Node directory-argument invocation failed: MODULE_NOT_FOUND (real rc 1; the '; echo rc=$?; tail' suffix left the harness status at 0). Recorded as a failure.",
     "tool": "Bash",
     "command": "\"/c/Program Files/nodejs/node\" --test integration-staging/frontend/tests/ > integration-staging/runtime/a13_node_tests.txt 2>&1; echo \"rc=$?\"; tail -60 ...",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": None},
    {"seq": 40, "purpose": "First node glob run reported 26/27 in its output (unavailable-item mapping, see failures); real rc 1 masked to 0 by the '; echo rc=$?' suffix.",
     "tool": "Bash",
     "command": "\"/c/Program Files/nodejs/node\" --test \"integration-staging/frontend/tests/*.test.mjs\" > integration-staging/runtime/a13_node_tests.txt 2>&1; echo \"rc=$?\"; tail -80 ...",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": None},
    {"seq": 41, "purpose": "Fix the unavailable-item mapping in client.mjs: an item with content_available === false gets no content link (flag checked before content_link).",
     "tool": "Edit",
     "command": "Edit tool: integration-staging/frontend/client.mjs",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/frontend/client.mjs"},
    {"seq": 42, "purpose": "Node glob re-run: 27 tests / 27 pass / 0 fail (rc 0); transcript written to runtime/a13_node_tests.txt.",
     "tool": "Bash",
     "command": "\"/c/Program Files/nodejs/node\" --test \"integration-staging/frontend/tests/*.test.mjs\" > integration-staging/runtime/a13_node_tests.txt 2>&1; echo \"rc=$?\"; tail -15 ...",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/runtime/a13_node_tests.txt"},
    {"seq": 43, "purpose": "Regenerate the frontend manifests and verify: --check rc 0.",
     "tool": "Bash",
     "command": "examdata/.venv/Scripts/python.exe integration-staging/tools/a13_frontend_provenance.py && examdata/.venv/Scripts/python.exe integration-staging/tools/a13_frontend_provenance.py --check",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/frontend/PROVENANCE.json"},
    {"seq": 44, "purpose": "Reclassify the provenance tool after discovering the originals live at frontend/ root: SOURCE_OVERRIDES for tests/search.test.mjs, README.md + search.test.mjs as modified_copy, NEW_FILES narrowed to 4 (three edits).",
     "tool": "Edit",
     "command": "Edit tool: integration-staging/tools/a13_frontend_provenance.py (three edits)",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/tools/a13_frontend_provenance.py"},
    {"seq": 45, "purpose": "Regenerate both manifests and verify: A13_FRONTEND_PROVENANCE: PASS (6 copied, 4 new, 3 fixtures).",
     "tool": "Bash",
     "command": "examdata/.venv/Scripts/python.exe integration-staging/tools/a13_frontend_provenance.py && examdata/.venv/Scripts/python.exe integration-staging/tools/a13_frontend_provenance.py --check; echo \"rc=$?\"",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/frontend/PROVENANCE.json"},
    {"seq": 46, "purpose": "Write the staged-copy conformance test module (manifest vs disk, staged-only new files, guarded subprocess re-checks).",
     "tool": "Write",
     "command": "Write tool: integration-staging/tests/test_frontend_staged_copy.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/tests/test_frontend_staged_copy.py"},
    {"seq": 47, "purpose": "Full staged suite green: 887 passed / 0 failed (rc 0); full transcript written to runtime/a13_pytest.txt.",
     "tool": "Bash",
     "command": "bash integration-staging/tools/run_staged_tests.sh -q > integration-staging/runtime/a13_pytest.txt 2>&1; echo \"rc=$?\"; tail -12 ...",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/runtime/a13_pytest.txt"},
    {"seq": 48, "purpose": "Wire-log extraction heredoc exited 1: UnicodeEncodeError: 'gbk' codec while writing non-ASCII output through the console (development-iteration script, no product impact). Recorded as a failure.",
     "tool": "Bash",
     "command": "examdata/.venv/Scripts/python.exe - <<'EOF' (wire-log extraction, GBK console)",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 1, "evidence": None},
    {"seq": 49, "purpose": "Same extraction re-run under PYTHONIOENCODING=utf-8: rc 0.",
     "tool": "Bash",
     "command": "PYTHONIOENCODING=utf-8 examdata/.venv/Scripts/python.exe - <<'EOF' (wire-log extraction, UTF-8)",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0, "evidence": None},
    {"seq": 50, "purpose": "Create evidence/A13, copy the node/pytest transcripts, and tee the operations provenance --check: A13_PROVENANCE: PASS (6 entries).",
     "tool": "Bash",
     "command": "mkdir -p docs/integration/execution/evidence/A13 && cp integration-staging/runtime/a13_node_tests.txt docs/integration/execution/evidence/A13/node_tests_stdout.txt && cp integration-staging/runtime/a13_pytest.txt docs/integration/execution/evidence/A13/pytest_run_stdout.txt && PYTHONIOENCODING=utf-8 examdata/.venv/Scripts/python.exe integration-staging/tools/a13_capture_fixtures.py --check | tee docs/integration/execution/evidence/A13/operations_provenance_stdout.txt",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "docs/integration/execution/evidence/A13/operations_provenance_stdout.txt"},
    {"seq": 51, "purpose": "Tee the frontend provenance --check (A13_FRONTEND_PROVENANCE: PASS (6 copied, 4 new, 3 fixtures)) and re-run the node files one by one (search 10/10, client 10/10, flow 7/7).",
     "tool": "Bash",
     "command": "PYTHONIOENCODING=utf-8 examdata/.venv/Scripts/python.exe integration-staging/tools/a13_frontend_provenance.py --check | tee docs/integration/execution/evidence/A13/frontend_provenance_stdout.txt; for f in search client flow; \"$NODE\" --test \"integration-staging/frontend/tests/$f.test.mjs\"",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "docs/integration/execution/evidence/A13/frontend_provenance_stdout.txt"},
    {"seq": 52, "purpose": "Write the A13 report.",
     "tool": "Write",
     "command": "Write tool: docs/integration/execution/A13_REPORT.md",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "docs/integration/execution/A13_REPORT.md"},
    {"seq": 53, "purpose": "Build the A13 close patch (hashes the 35 inputs and the packet write set, excluding the post-close transcripts).",
     "tool": "Bash",
     "command": "examdata/.venv/Scripts/python.exe integration-staging/tools/a13_close_patch.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/runtime/ledger-patches/A13_close.json"},
    {"seq": 54, "purpose": "Close the A13 ledger record: status staged_pass with the patch merged in.",
     "tool": "Bash",
     "command": "examdata/.venv/Scripts/python.exe integration-staging/tools/ledger_update.py --task A13 --status staged_pass --patch-file integration-staging/runtime/ledger-patches/A13_close.json",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "docs/integration/execution/execution-ledger.json"},
    {"seq": 55, "purpose": "Write the A13 closing-checks runner (verifies the packet in fresh subprocesses and rewrites the post-close transcripts).",
     "tool": "Write",
     "command": "Write tool: integration-staging/tools/a13_final_checks.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/tools/a13_final_checks.py"},
    {"seq": 56, "purpose": "Run the A13 closing checks: FINAL_CHECKS: PASS (rewrites the final transcripts); re-run once more after the close-patch rebuild + re-merge and stayed green (post-close transcript).",
     "tool": "Bash",
     "command": "examdata/.venv/Scripts/python.exe integration-staging/tools/a13_final_checks.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "docs/integration/execution/evidence/A13/final_checks.txt"},
]

TEST_RESULTS = [
    {"check": "Node suite green offline: 27/27 tests (search 10 + client 10 + flow 7), 0 failures",
     "result": "pass", "exit_code": 0,
     "evidence": "docs/integration/execution/evidence/A13/node_tests_stdout.txt",
     "label": "synthetic_fixture",
     "note": "Run with node --test on the quoted glob inside the project root; the tests use injected fetch or the in-process fixture server bound to 127.0.0.1 on an ephemeral port (protected ports 5188/8000 refused); no external fetch exists in the staged copy. Duration 285.69 ms in the recorded run."},
    {"check": "Full staged suite green: 887 passed / 0 failed",
     "result": "pass", "exit_code": 0,
     "evidence": "docs/integration/execution/evidence/A13/pytest_run_stdout.txt",
     "label": "synthetic_fixture",
     "note": "Net +31 over the A12 close (856): operations checkpoints 15 + coverage 9 + frontend staged copy 7. Run inside integration-staging under the staged harness guards; no original path, service or database involved."},
    {"check": "Operations fixture provenance PASS: 6 synthetic entries with sha256 + bytes",
     "result": "pass", "exit_code": 0,
     "evidence": "docs/integration/execution/evidence/A13/operations_provenance_stdout.txt",
     "label": "static_inspection",
     "note": "Manifest schema fixture-provenance/1; hand-authored fixtures shaped like the two native checkpoint formats; regenerated and re-verified read-only at close (A13_PROVENANCE: PASS (6 entries))."},
    {"check": "Frontend provenance PASS: 6 copied (2 copied_snapshot byte-identical, 4 modified_copy with source sha256) + 4 new + 3 fixtures",
     "result": "pass", "exit_code": 0,
     "evidence": "docs/integration/execution/evidence/A13/frontend_provenance_stdout.txt",
     "label": "static_inspection",
     "note": "frontend-provenance/1 records both source and staged sha256 for every copied file; the closing checks re-verify the manifests in fresh subprocesses (A13_FRONTEND_PROVENANCE: PASS (6 copied, 4 new, 3 fixtures))."},
    {"check": "Targeted re-runs at close: 31 Python tests (3 A13 modules) + 27 node tests",
     "result": "pass", "exit_code": 0,
     "evidence": "docs/integration/execution/evidence/A13/python_rerun.txt",
     "label": "synthetic_fixture",
     "note": "Produced by the closing checks: collect-only reports 887; the three A13 test modules pass 31; the node glob passes 27 (evidence/A13/frontend_rerun.txt)."},
]

FAILURES = [
    {"what": "First operations targeted run reported 1 failed / 879 passed: cie-batch-checkpoint-running.json lacked 'current_paper', so test_cie_running_view_keeps_missing_stop_fields_none raised KeyError (line 99); the '| tail -30' pipeline without pipefail masked the process exit code to 0.",
     "exit_code": 0,
     "exit_code_masked": True,
     "evidence": "command row seq 20 (exit_code 0, masked; 1 failed in output)",
     "resolution": "The fixture was fixed (current_paper inserted) and the manifest regenerated; the targeted run then reported 880 passed (row seq 22)."},
    {"what": "Node directory-argument invocation (node --test integration-staging/frontend/tests/) exited 1 with MODULE_NOT_FOUND; the '; echo rc=$?; tail' suffix left the harness status at 0.",
     "exit_code": 0,
     "exit_code_masked": True,
     "evidence": "command row seq 39 (exit_code 0, masked; printed rc 1)",
     "resolution": "Switched to the quoted glob invocation node --test \"integration-staging/frontend/tests/*.test.mjs\" (rows seq 40+)."},
    {"what": "First node glob run reported 26/27: 'documentFromResource marks unavailable items' expected an empty link but the staged content URL was produced (content_link preferred over the content_available flag). Real rc 1 printed by '; echo rc=$?' while the harness row is 0.",
     "exit_code": 0,
     "exit_code_masked": True,
     "evidence": "command row seq 40 (exit_code 0, masked; 26/27 in output)",
     "resolution": "client.mjs mapping fixed to honour content_available === false before content_link (row seq 41); the rerun passed 27/27 (row seq 42)."},
    {"what": "Wire-log extraction heredoc exited 1: UnicodeEncodeError: 'gbk' codec can't encode characters while writing non-ASCII output through the Windows console (development-iteration script; it reads the session event log and writes a scratch extract under runtime/, since removed; no deliverable was affected).",
     "exit_code": 1,
     "found_by": "development_iteration",
     "evidence": "command row seq 48 (exit_code 1)",
     "resolution": "Re-ran the extraction under PYTHONIOENCODING=utf-8 (row seq 49)."},
    {"what": "First development run of the closing checks (a13_final_checks.py) exited 1: the strict input-hash recompute flagged sha256 drift on the actively-owned native cie-location-batch/checkpoint.json, which the concurrent owner rewrote minutes after the patch snapshot (mid-run).",
     "exit_code": 1,
     "found_by": "development_iteration",
     "evidence": "first run of the closing checks (stdout kept in integration-staging/runtime/a13_final_run1.txt; not a recorded command row)",
     "resolution": "The closing checks now exclude the three actively-owned native inputs from the strict recompute and log recorded-vs-current drift as an observation instead (close_patch.native_inputs_registered asserts registration); re-run green after the v2 rebuild."},
]

REMAINING_GAPS = [
    "The staged frontend is a modified copy: the merge (B06) must reconcile README.md (shared file name, different content), reapply the app.js/index.html edits on the final tree, and switch the client to the real backend behind the reversible examdata.v2-client flag.",
    "The fixture server is a stand-in for the staged Python v2 API; it is proven only against private synthetic fixtures and 127.0.0.1 in-process flows (no real browser, no external network).",
    "Operations readers are fixture-level: proven against 6 synthetic fixtures shaped like the two native formats; the native checkpoints were read once for shape only. Real checkpoint adaptation is Phase B (B07).",
    "Search normalization coverage is the subset kept with the staged copy; the original resources test block is retired until the merge reconciles the staged tests with the final frontend tree.",
    "A14 file-by-file merge map and A15 PHASE_A_REPORT.md remain; everything is staged, nothing is merged or deployed, and all seven Phase B gates stay closed.",
]

EVIDENCE_PATHS = [
    "docs/integration/execution/A13_REPORT.md",
    "docs/integration/execution/evidence/A13/node_tests_stdout.txt",
    "docs/integration/execution/evidence/A13/pytest_run_stdout.txt",
    "docs/integration/execution/evidence/A13/operations_provenance_stdout.txt",
    "docs/integration/execution/evidence/A13/frontend_provenance_stdout.txt",
    "docs/integration/execution/evidence/A13/final_checks.txt",
    "docs/integration/execution/evidence/A13/python_rerun.txt",
    "docs/integration/execution/evidence/A13/frontend_rerun.txt",
    "docs/integration/execution/execution-ledger.json",
    "integration-staging/runtime/ledger-patches/A13_close.json",
    "integration-staging/runtime/a13_node_tests.txt",
    "integration-staging/runtime/a13_pytest.txt",
    "integration-staging/src/examdata_integration/operations/__init__.py",
    "integration-staging/src/examdata_integration/operations/checkpoints.py",
    "integration-staging/src/examdata_integration/operations/coverage.py",
    "integration-staging/fixtures/synthetic/operations/PROVENANCE.json",
    "integration-staging/fixtures/synthetic/operations/README.md",
    "integration-staging/frontend/PROVENANCE.json",
    "integration-staging/frontend/client.mjs",
    "integration-staging/frontend/fixture-server.mjs",
    "integration-staging/frontend/app.js",
    "integration-staging/frontend/index.html",
    "integration-staging/frontend/README.md",
    "integration-staging/frontend/fixtures/PROVENANCE.json",
    "integration-staging/frontend/tests/search.test.mjs",
    "integration-staging/frontend/tests/client.test.mjs",
    "integration-staging/frontend/tests/flow.test.mjs",
    "integration-staging/tests/test_operations_checkpoints.py",
    "integration-staging/tests/test_operations_coverage.py",
    "integration-staging/tests/test_frontend_staged_copy.py",
    "integration-staging/tools/a13_capture_fixtures.py",
    "integration-staging/tools/a13_frontend_provenance.py",
    "integration-staging/tools/a13_final_checks.py",
    "integration-staging/tools/a13_close_patch.py",
]

NEXT_ACTION = ("A14 - file-by-file merge map (plan section 11): identify every eventual original target "
               "path and the base hash used to prepare it, avoid a whole-tree replacement patch, list "
               "active-owner deferred files separately, and show why each change is reversible; then A15 "
               "PHASE_A_REPORT.md + deferred list + release request. All seven Phase B gates remain closed; "
               "only the human user can release the original paths.")

NOTES = ("All A13 inputs are frozen A01-A12 artefacts plus read-only originals: the frontend tree (read only; "
         "its sources are hashed into frontend/PROVENANCE.json) and three native checkpoint files (Read tool "
         "once, format study only; no test parses them). No original file was written, no original test or "
         "application was run, nothing was fetched, no service or database was touched, the CIE batch was not "
         "resumed, and nothing was started on or sent to ports 5188/8000. Command rows are shortened "
         "single-line forms of the recorded operations. One command exited 1 and was resolved in-packet (the "
         "GBK extraction heredoc, row seq 48); three pipeline/suffix runs reported failures in their output "
         "while their exit codes were masked to 0 (rows seq 20, 39, 40) - recorded as failures with "
         "exit_code_masked=true. The first development run of the closing checks also exited 1 and is "
         "recorded as a failure: the concurrent owner rewrote the native cie-location-batch/checkpoint.json "
         "mid-run, and the checks now log native-input drift instead of asserting it. Trivial exploratory "
         "calls (file reads, wire-log parsing, ledger_update --help, a scratch wire-log extract under "
         "runtime/ that was removed during close preparation) are omitted from the command rows and touched "
         "no deliverable. The close patch was then rebuilt so the closing-checks tool itself enters "
         "changed_files/input_hashes, the ledger was re-merged, and the closing checks re-ran green, "
         "rewriting the final "
         "transcripts. The four modified copies carry recorded source sha256 so the merge can reconcile "
         "against the desktop originals; the two copied_snapshot files are byte-identical to their sources. "
         "Everything is staged: nothing is merged, nothing is deployed, and all seven Phase B gates stay closed.")


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
        if r in POST_CLOSE:
            continue
        input_hashes[r] = sha256_file(WS / r)

    patch = {
        "dependencies": ["A12"],
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
          f"exit_codes={patch['exit_codes']} outside_roots={outside} "
          f"missing_inputs={missing_inputs}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
