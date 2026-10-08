#!/usr/bin/env python3
"""Build the A11 ledger close patch (docs/integration/execution/execution-ledger.json).

Computes the input hashes over the true inputs plus the A11 write set (excluding
the closing-checks transcript, which is produced *after* the ledger closes, and
this patch file itself), and emits a JSON object to be merged into the A11 task
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
OUT = STAGING / "runtime" / "ledger-patches" / "A11_close.json"

ROOTS = [STAGING.as_posix(), EXEC.as_posix()]

INPUTS = [
    "docs/integration/EXECUTOR_PROMPT_EN.md",
    "docs/integration/MASTER_EXECUTION_PLAN_EN.md",
    "docs/integration/ROUTE_INVENTORY_CURRENT.json",
    "docs/PROJECT_STATUS.md",
    "docs/integration/execution/execution-ledger.json",
    "docs/integration/execution/A10_REPORT.md",
    "docs/integration/execution/evidence/A10/api_stdout.txt",
    "docs/integration/execution/evidence/A10/pytest_run_stdout.txt",
    # frozen A04 contracts the binary transport maps onto (read-only dependency)
    "integration-staging/src/examdata_integration/contracts/models.py",
    "integration-staging/src/examdata_integration/contracts/base.py",
    "integration-staging/src/examdata_integration/contracts/enums.py",
    "integration-staging/src/examdata_integration/contracts/canonical.py",
    "integration-staging/src/examdata_integration/contracts/quality.py",
    "integration-staging/src/examdata_integration/contracts/ids.py",
    "integration-staging/src/examdata_integration/contracts/jsonschema_lite.py",
    # frozen A05/A07/A08 provider layer and A09 catalog the API reads
    "integration-staging/src/examdata_integration/providers/capabilities.py",
    "integration-staging/src/examdata_integration/providers/results.py",
    "integration-staging/src/examdata_integration/providers/registry.py",
    "integration-staging/src/examdata_integration/providers/fixtures.py",
    "integration-staging/src/examdata_integration/catalog/model.py",
    "integration-staging/src/examdata_integration/catalog/store.py",
    "integration-staging/src/examdata_integration/catalog/builder.py",
    "integration-staging/src/examdata_integration/catalog/revision.py",
    # frozen A10 api modules the binary transport extends without editing
    "integration-staging/src/examdata_integration/api/dataset.py",
    "integration-staging/src/examdata_integration/api/pagination.py",
    "integration-staging/src/examdata_integration/api/view.py",
    # frozen A05 provider fixtures the dataset builds its snapshot from
    "integration-staging/fixtures/synthetic/cie/cie-index-synthetic.json",
    "integration-staging/fixtures/synthetic/edexcel/index-synthetic.json",
    "integration-staging/fixtures/synthetic/ielts/questions-synthetic.json",
    # frozen A02-A10 harness the A11 tests run under
    "integration-staging/pytest.ini",
    "integration-staging/tests/conftest.py",
    "integration-staging/tools/run_staged_tests.sh",
    "integration-staging/tools/ledger_update.py",
    "integration-staging/src/examdata_integration/testing/guards.py",
]

WRITE_GLOBS = [
    # A11 binary fixtures: the whole directory is new and packet-owned
    "integration-staging/fixtures/synthetic/binary/*",
    # A11 source files only (dataset/pagination/view are frozen A10 files, untouched)
    "integration-staging/src/examdata_integration/api/__init__.py",
    "integration-staging/src/examdata_integration/api/app.py",
    "integration-staging/src/examdata_integration/api/binary.py",
    "integration-staging/src/examdata_integration/api/envelope.py",
    "integration-staging/src/examdata_integration/api/links.py",
    "integration-staging/src/examdata_integration/api/openapi.py",
    # A11 test files: three new binary modules plus the three updated A10 modules
    "integration-staging/tests/test_api_binary_fixtures.py",
    "integration-staging/tests/test_api_binary_store.py",
    "integration-staging/tests/test_api_binary_transport.py",
    "integration-staging/tests/test_api_envelope.py",
    "integration-staging/tests/test_api_links_openapi.py",
    "integration-staging/tests/test_api_routes.py",
    # A11 tools (the A10 probe was updated in this packet for the new inventory)
    "integration-staging/tools/a10_probe_api.py",
    "integration-staging/tools/a11_*.py",
    # the deterministic fixture generator written by this packet
    "integration-staging/tools/build_binary_fixtures.py",
    "integration-staging/runtime/ledger-patches/A11_close.json",
    "docs/integration/execution/A11_REPORT.md",
    "docs/integration/execution/evidence/A11/*",
]

# produced only after the ledger closes: listed but never hashed into the patch
POST_CLOSE = {
    "docs/integration/execution/evidence/A11/final_checks.txt",
    "docs/integration/execution/evidence/A11/a10_probe_rerun.txt",
}

COMMANDS = [
    {"seq": 1, "purpose": "Create the A11 evidence directory.",
     "tool": "Bash",
     "command": "mkdir -p docs/integration/execution/evidence/A11",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0, "evidence": None},
    {"seq": 2, "purpose": "Write the deterministic binary-fixture generator: 11 small synthetic samples (CIE/edexcel/IELTS PDFs+PNGs), a manifest with whitelisted media types and declared byte hashes, and PROVENANCE; --check verifies without writing.",
     "tool": "Write",
     "command": "Write tool: integration-staging/tools/build_binary_fixtures.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/tools/build_binary_fixtures.py"},
    {"seq": 3, "purpose": "Iterate the generator before the first run (sample set, declared placeholder hashes, crop page numbers): four edits.",
     "tool": "Edit",
     "command": "Edit tool: integration-staging/tools/build_binary_fixtures.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/tools/build_binary_fixtures.py"},
    {"seq": 4, "purpose": "Render the fixtures for the first time (11 samples + manifest.json + PROVENANCE.json).",
     "tool": "Bash",
     "command": "examdata/.venv/Scripts/python.exe integration-staging/tools/build_binary_fixtures.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/fixtures/synthetic/binary/"},
    {"seq": 5, "purpose": "Independent fixture verification (declared hashes, generator sha, provenance coverage): the first script version failed an assertion (see failures).",
     "tool": "Bash",
     "command": "examdata/.venv/Scripts/python.exe - <<'PY' (hash/coverage verification heredoc)",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 1,
     "evidence": "integration-staging/fixtures/synthetic/binary/"},
    {"seq": 6, "purpose": "Corrected verification script: declared hashes + crop pages OK, generator sha OK, PROVENANCE 12 entries cover 12 files, VERIFY: PASS.",
     "tool": "Bash",
     "command": "examdata/.venv/Scripts/python.exe - <<'PY' (corrected verification heredoc)",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/fixtures/synthetic/binary/"},
    {"seq": 7, "purpose": "Write the binary transport core: ContentStore over the frozen manifest (safe names, whitelisted media, byte sizes), ContentLimits budgets, Sample, iter_sample/iter_range/iter_crop_copy with temp-root cleanup, crop conflict detection.",
     "tool": "Write",
     "command": "Write tool: integration-staging/src/examdata_integration/api/binary.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/src/examdata_integration/api/binary.py"},
    {"seq": 8, "purpose": "First store-level probe heredoc exited 1 with a SyntaxError (a walrus expression inside a dict literal).",
     "tool": "Bash",
     "command": "PYTHONPATH=src examdata/.venv/Scripts/python.exe - <<'PY' (store probe heredoc)",
     "cwd": "C:/Users/weo/Desktop/api/integration-staging", "exit_code": 1,
     "evidence": "integration-staging/src/examdata_integration/api/binary.py"},
    {"seq": 9, "purpose": "Second store-level probe heredoc exited 1: an assertion expected BudgetExceeded for a case the verified enforce_budget semantics answer differently.",
     "tool": "Bash",
     "command": "PYTHONPATH=src examdata/.venv/Scripts/python.exe - <<'PY' (store probe heredoc, revised)",
     "cwd": "C:/Users/weo/Desktop/api/integration-staging", "exit_code": 1,
     "evidence": "integration-staging/src/examdata_integration/api/binary.py"},
    {"seq": 10, "purpose": "Revised probe iteration passes: safe names, lookups, range table and etag OK at store level.",
     "tool": "Bash",
     "command": "PYTHONPATH=src examdata/.venv/Scripts/python.exe - <<'PY' (store probe heredoc, third iteration)",
     "cwd": "C:/Users/weo/Desktop/api/integration-staging", "exit_code": 0,
     "evidence": "integration-staging/src/examdata_integration/api/binary.py"},
    {"seq": 11, "purpose": "Flip the five content/crop RouteSpec rows from deferred to implemented and record their binary media types in the single route registry.",
     "tool": "Edit",
     "command": "Edit tool: integration-staging/src/examdata_integration/api/links.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/src/examdata_integration/api/links.py"},
    {"seq": 12, "purpose": "Add BINARY_STATUSES = {206, 304, 416}: transport-level statuses outside the plan 5.2 JSON error map, same carve-out idea as FRAMEWORK_STATUSES.",
     "tool": "Edit",
     "command": "Edit tool: integration-staging/src/examdata_integration/api/envelope.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/src/examdata_integration/api/envelope.py"},
    {"seq": 13, "purpose": "Route/link probe iteration passes against the flipped registry.",
     "tool": "Bash",
     "command": "PYTHONPATH=src examdata/.venv/Scripts/python.exe - <<'PY' (route/link probe heredoc)",
     "cwd": "C:/Users/weo/Desktop/api/integration-staging", "exit_code": 0,
     "evidence": "integration-staging/src/examdata_integration/api/links.py"},
    {"seq": 14, "purpose": "Document the five binary routes in BINARY_ROUTE_RESPONSES (status/media per route) so runtime, spec and advertised links can agree.",
     "tool": "Edit",
     "command": "Edit tool: integration-staging/src/examdata_integration/api/openapi.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/src/examdata_integration/api/openapi.py"},
    {"seq": 15, "purpose": "OpenAPI/binary consistency probe exited 1: the check mis-assumed the method vocabulary (openapi.HTTP_METHODS is an uppercase frozenset including PATCH).",
     "tool": "Bash",
     "command": "PYTHONPATH=src examdata/.venv/Scripts/python.exe -c \"...openapi/binary consistency...\"",
     "cwd": "C:/Users/weo/Desktop/api/integration-staging", "exit_code": 1,
     "evidence": "integration-staging/src/examdata_integration/api/openapi.py"},
    {"seq": 16, "purpose": "Corrected consistency probe passes: BINARY_ROUTE_RESPONSES keys, method vocabulary, documented rows.",
     "tool": "Bash",
     "command": "PYTHONPATH=src examdata/.venv/Scripts/python.exe -c \"...corrected consistency check...\"",
     "cwd": "C:/Users/weo/Desktop/api/integration-staging", "exit_code": 0,
     "evidence": "integration-staging/src/examdata_integration/api/openapi.py"},
    {"seq": 17, "purpose": "Refine binary.py semantics found by the store probes and integration (budget/limit handling, media handling, path safety): three edits.",
     "tool": "Edit",
     "command": "Edit tool: integration-staging/src/examdata_integration/api/binary.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/src/examdata_integration/api/binary.py"},
    {"seq": 18, "purpose": "Inventory the staged src/tests/tools while wiring the app integration.",
     "tool": "Bash",
     "command": "ls src/examdata_integration/ src/examdata_integration/api/ && wc -l src/examdata_integration/api/dataset.py tests/conftest.py",
     "cwd": "C:/Users/weo/Desktop/api/integration-staging", "exit_code": 0, "evidence": None},
    {"seq": 19, "purpose": "Wire ContentStore into create_app and add the five GET/HEAD binary handlers (the app-integration edit series 12430-12600).",
     "tool": "Edit",
     "command": "Edit tool: integration-staging/src/examdata_integration/api/app.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/src/examdata_integration/api/app.py"},
    {"seq": 20, "purpose": "First in-process TestClient smoke exited 1: the five binary routes were not yet documented by the OpenAPI helper (AssertionError listing all five); the transport answers themselves were already observed OK.",
     "tool": "Bash",
     "command": "PYTHONPATH=src examdata/.venv/Scripts/python.exe -c \"...first app smoke...\"",
     "cwd": "C:/Users/weo/Desktop/api/integration-staging", "exit_code": 1,
     "evidence": "integration-staging/src/examdata_integration/api/app.py"},
    {"seq": 21, "purpose": "Export BINARY_ROUTE_RESPONSES and document the binary routes from openapi.py/api/__init__.py (two edits).",
     "tool": "Edit",
     "command": "Edit tool: integration-staging/src/examdata_integration/api/openapi.py + api/__init__.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/src/examdata_integration/api/openapi.py"},
    {"seq": 22, "purpose": "Second smoke exited 1: documented 200 media lists still included application/json for the document routes whose runtime media are pdf/png only.",
     "tool": "Bash",
     "command": "PYTHONPATH=src examdata/.venv/Scripts/python.exe -W ignore::UserWarning -c \"...second app smoke...\"",
     "cwd": "C:/Users/weo/Desktop/api/integration-staging", "exit_code": 1,
     "evidence": "integration-staging/src/examdata_integration/api/openapi.py"},
    {"seq": 23, "purpose": "Align response media type and content filename handling with the documented contract.",
     "tool": "Edit",
     "command": "Edit tool: integration-staging/src/examdata_integration/api/app.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/src/examdata_integration/api/app.py"},
    {"seq": 24, "purpose": "Third in-process smoke passes end to end: ALL_APP_SMOKE: PASS (asset 200/HEAD, range 206, 416, 304, 404, syllabus/material, crop, IELTS 422).",
     "tool": "Bash",
     "command": "PYTHONPATH=src examdata/.venv/Scripts/python.exe -W ignore::UserWarning -c \"...third app smoke...\"",
     "cwd": "C:/Users/weo/Desktop/api/integration-staging", "exit_code": 0,
     "evidence": "integration-staging/src/examdata_integration/api/app.py"},
    {"seq": 25, "purpose": "Intermediate full-suite run after the route flip (before the test updates): the output reported 11 failed / 567 passed; the process exit code was masked to 0 by the `| tail` pipeline (no pipefail) and the failure is recorded in the failures list.",
     "tool": "Bash",
     "command": "bash tools/run_staged_tests.sh --tb=no -q 2>&1 | tail -40",
     "cwd": "C:/Users/weo/Desktop/api/integration-staging", "exit_code": 0,
     "evidence": None},
    {"seq": 26, "purpose": "Update the envelope tests for the binary-statuses carve-out.",
     "tool": "Edit",
     "command": "Edit tool: integration-staging/tests/test_api_envelope.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/tests/test_api_envelope.py"},
    {"seq": 27, "purpose": "Update links/openapi expectations to 34 advertised routes (three edits).",
     "tool": "Edit",
     "command": "Edit tool: integration-staging/tests/test_api_links_openapi.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/tests/test_api_links_openapi.py"},
    {"seq": 28, "purpose": "Replace the five deferred-route tests with binary route registration tests (four edits).",
     "tool": "Edit",
     "command": "Edit tool: integration-staging/tests/test_api_routes.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/tests/test_api_routes.py"},
    {"seq": 29, "purpose": "Full-suite run after the test updates: 579 passed (run_staged_tests.sh collects the whole tests/ tree).",
     "tool": "Bash",
     "command": "bash tools/run_staged_tests.sh tests/test_api_envelope.py tests/test_api_links_openapi.py tests/test_api_routes.py",
     "cwd": "C:/Users/weo/Desktop/api/integration-staging", "exit_code": 0,
     "evidence": None},
    {"seq": 30, "purpose": "Asset identity reconnaissance under an isolated HOME/TEMP: list catalog assets with their declared byte hashes for the transport tests.",
     "tool": "Bash",
     "command": "HOME=$PWD/runtime/home TEMP=$PWD/runtime/tmp python ... (asset identity listing)",
     "cwd": "C:/Users/weo/Desktop/api/integration-staging", "exit_code": 0,
     "evidence": None},
    {"seq": 31, "purpose": "Write the binary store test module (manifest integrity, budgets, iteration, crop copies).",
     "tool": "Write",
     "command": "Write tool: integration-staging/tests/test_api_binary_store.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/tests/test_api_binary_store.py"},
    {"seq": 32, "purpose": "Write the binary transport test module (200/HEAD/206/416/304/404/409, media, filenames).",
     "tool": "Write",
     "command": "Write tool: integration-staging/tests/test_api_binary_transport.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/tests/test_api_binary_transport.py"},
    {"seq": 33, "purpose": "Write the binary fixtures test module (manifest/provenance/generator --check) and one follow-up edit.",
     "tool": "Write",
     "command": "Write tool: integration-staging/tests/test_api_binary_fixtures.py (+1 edit)",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/tests/test_api_binary_fixtures.py"},
    {"seq": 34, "purpose": "First full A11 suite run exited 1: 3 failed, 708 passed (the two transport content tests and the size-mismatch store test; see failures).",
     "tool": "Bash",
     "command": "bash tools/run_staged_tests.sh",
     "cwd": "C:/Users/weo/Desktop/api/integration-staging", "exit_code": 1,
     "evidence": "integration-staging/tests/"},
    {"seq": 35, "purpose": "Targeted re-run of the three failing tests exited 1, reproducing the failures deterministically before the fix.",
     "tool": "Bash",
     "command": "bash tools/run_staged_tests.sh -k \"size_mismatch or asset_content_serves or syllabus_and_material\"",
     "cwd": "C:/Users/weo/Desktop/api/integration-staging", "exit_code": 1,
     "evidence": "integration-staging/tests/"},
    {"seq": 36, "purpose": "Fix app.py: serve content with the sample file name {id}.{extension} (three call sites).",
     "tool": "Edit",
     "command": "Edit tool: integration-staging/src/examdata_integration/api/app.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/src/examdata_integration/api/app.py"},
    {"seq": 37, "purpose": "Fix the size-mismatch store test: write the sample bytes the manifest declares.",
     "tool": "Edit",
     "command": "Edit tool: integration-staging/tests/test_api_binary_store.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/tests/test_api_binary_store.py"},
    {"seq": 38, "purpose": "Targeted re-run after the two fixes passes.",
     "tool": "Bash",
     "command": "bash tools/run_staged_tests.sh -k \"size_mismatch or asset_content_serves or syllabus_and_material\"",
     "cwd": "C:/Users/weo/Desktop/api/integration-staging", "exit_code": 0,
     "evidence": "integration-staging/tests/"},
    {"seq": 39, "purpose": "Full staged suite run to green: 711 passed, 0 failed.",
     "tool": "Bash",
     "command": "bash tools/run_staged_tests.sh",
     "cwd": "C:/Users/weo/Desktop/api/integration-staging", "exit_code": 0,
     "evidence": "integration-staging/tests/"},
    {"seq": 40, "purpose": "Update the A10 probe counts to the post-A11 inventory: 34 implemented / 0 deferred.",
     "tool": "Edit",
     "command": "Edit tool: integration-staging/tools/a10_probe_api.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/tools/a10_probe_api.py"},
    {"seq": 41, "purpose": "A10 probe regression after the count update: A10_PROBE: PASS, 82 scenarios (transcript written to the OS temp dir, transient).",
     "tool": "Bash",
     "command": "examdata/.venv/Scripts/python.exe tools/a10_probe_api.py",
     "cwd": "C:/Users/weo/Desktop/api/integration-staging", "exit_code": 0,
     "evidence": None},
    {"seq": 42, "purpose": "Write the 88-scenario offline binary-transport probe.",
     "tool": "Write",
     "command": "Write tool: integration-staging/tools/a11_probe_binary.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/tools/a11_probe_binary.py"},
    {"seq": 43, "purpose": "First A11 probe run: A11_PROBE: PASS (0 failing).",
     "tool": "Bash",
     "command": "examdata/.venv/Scripts/python.exe tools/a11_probe_binary.py",
     "cwd": "C:/Users/weo/Desktop/api/integration-staging", "exit_code": 0,
     "evidence": "integration-staging/tools/a11_probe_binary.py"},
    {"seq": 44, "purpose": "Capture the probe transcript for evidence (88 [ok], A11_PROBE: PASS).",
     "tool": "Bash",
     "command": "examdata/.venv/Scripts/python.exe tools/a11_probe_binary.py > ../docs/integration/execution/evidence/A11/binary_stdout.txt",
     "cwd": "C:/Users/weo/Desktop/api/integration-staging", "exit_code": 0,
     "evidence": "docs/integration/execution/evidence/A11/binary_stdout.txt"},
    {"seq": 45, "purpose": "Capture the staged-suite transcript for evidence (711 passed).",
     "tool": "Bash",
     "command": "bash tools/run_staged_tests.sh > ../docs/integration/execution/evidence/A11/pytest_run_stdout.txt",
     "cwd": "C:/Users/weo/Desktop/api/integration-staging", "exit_code": 0,
     "evidence": "docs/integration/execution/evidence/A11/pytest_run_stdout.txt"},
    {"seq": 46, "purpose": "Write the A11 report.",
     "tool": "Write", "command": "Write tool: docs/integration/execution/A11_REPORT.md",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "docs/integration/execution/A11_REPORT.md"},
    {"seq": 47, "purpose": "Write the A11 closing-checks runner.",
     "tool": "Write", "command": "Write tool: integration-staging/tools/a11_final_checks.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/tools/a11_final_checks.py"},
    {"seq": 48, "purpose": "Write the A11 ledger close-patch builder.",
     "tool": "Write", "command": "Write tool: integration-staging/tools/a11_close_patch.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/tools/a11_close_patch.py"},
    {"seq": 49, "purpose": "Build the A11 close patch (hashes inputs and the write set, excluding post-close artefacts).",
     "tool": "Bash",
     "command": "examdata/.venv/Scripts/python.exe integration-staging/tools/a11_close_patch.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/runtime/ledger-patches/A11_close.json"},
    {"seq": 50, "purpose": "Close the A11 ledger record: status staged_pass with the patch merged in.",
     "tool": "Bash",
     "command": "examdata/.venv/Scripts/python.exe integration-staging/tools/ledger_update.py --task A11 --status staged_pass --patch-file integration-staging/runtime/ledger-patches/A11_close.json",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "docs/integration/execution/execution-ledger.json"},
    {"seq": 51, "purpose": "Run the A11 closing checks (after the ledger is closed; writes evidence/A11/final_checks.txt and the A10 probe regression transcript).",
     "tool": "Bash",
     "command": "examdata/.venv/Scripts/python.exe integration-staging/tools/a11_final_checks.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": None,
     "evidence": "docs/integration/execution/evidence/A11/final_checks.txt"},
]

TEST_RESULTS = [
    {"check": "Binary probe: 88/88 scenarios PASS offline (A11_PROBE: PASS)",
     "result": "pass", "exit_code": 0,
     "evidence": "docs/integration/execution/evidence/A11/binary_stdout.txt",
     "label": "synthetic_fixture",
     "note": "fixture store integrity (11 samples + manifest.json + PROVENANCE.json = 13 files; real sha256 values on disk; the declared identities stay the frozen placeholders; PROVENANCE has 12 fixture-provenance/1 entries, all labelled synthetic, covering every payload file; generator sha matches the manifest); runtime==spec==advertised==34 route pairs, the five HEAD pairs being exactly the binary rows; asset 200 byte-equal GET/HEAD plus the resources alias; syllabus and material content 200 pdf, syllabus with content-disposition; single byte ranges 206 with content-range (first, suffix and open ranges), unsatisfiable 416 with `bytes */size` and a valid error envelope, bare `bytes=-0` 416, inverted range ignored to 200; conditional 304 via If-None-Match (quoted, weak and list forms) with no body, a non-matching etag still 200; response budgets 413 `response_budget_exceeded` (asset) and `crop_budget_exceeded` (crop) with valid envelopes; crop 409 hash/region conflicts; 404 `content_not_available` for sample-less syllabus/material/crop and `not_found` for unknown identities; POST 405; regionless crop 422 (IELTS question); generator --check PASS; no temp leftovers under integration-staging/runtime/tmp."},
    {"check": "Staged suite passes offline: 711 tests, 0 failures",
     "result": "pass", "exit_code": 0,
     "evidence": "docs/integration/execution/evidence/A11/pytest_run_stdout.txt",
     "label": "synthetic_fixture",
     "note": "135 net new tests over the A10 baseline of 576: 132 collected in the three new binary modules (111 store + 15 transport + 6 fixtures) plus the updated envelope/route/link tests; in the isolated harness with the module and network guards active."},
    {"check": "Runtime routes, the OpenAPI document and the advertised links agree exactly at 34",
     "result": "pass", "exit_code": 0,
     "evidence": "integration-staging/tests/test_api_links_openapi.py",
     "label": "static_inspection",
     "note": "runtime_pairs(app) == spec_pairs(app) == advertised_pairs() (34 each, five of them HEAD); DEFERRED_SPECS is empty; agreement_problems(app) == []."},
    {"check": "Binary fixtures are reproducible: --check reports 13 files matching a fresh render",
     "result": "pass", "exit_code": 0,
     "evidence": "integration-staging/tests/test_api_binary_fixtures.py",
     "label": "synthetic_fixture",
     "note": "build_binary_fixtures.py --check verifies and writes nothing; PROVENANCE.json covers all 12 payload files with fixture-provenance/1 entries."},
    {"check": "The binary transport never touches original paths and leaves no temp files behind",
     "result": "pass", "exit_code": 0,
     "evidence": "integration-staging/tools/a11_probe_binary.py",
     "label": "static_inspection",
     "note": "containment scenario: no crop-/a11-conflict- temp leftovers under integration-staging/runtime/tmp after range, crop and conflict streaming. Path traversal, Windows drive/UNC names and non-whitelisted media are rejected by the store's safe-name/whitelist rules and exercised in the binary store tests."},
]

FAILURES = [
    {"what": "Fixture verification (first version) exited 1: the hash/coverage heredoc failed an assertion while checking the manifest groups.",
     "evidence": "command row seq 5 (exit_code 1)",
     "resolution": "The verification script was corrected (row seq 6) and now reports declared hashes + crop pages OK, generator sha OK, PROVENANCE 12 entries covering 12 files, VERIFY: PASS; the generator's own --check is re-verified in the probe."},
    {"what": "First store probe engaged a SyntaxError (a walrus expression inside a dict literal).",
     "evidence": "command row seq 8 (exit_code 1)",
     "resolution": "Probe script rewritten without the walrus; the next iterations run (rows seq 9-10)."},
    {"what": "Second store probe exited 1: an assertion expected BudgetExceeded for a case the verified enforce_budget semantics answer differently.",
     "evidence": "command row seq 9 (exit_code 1)",
     "resolution": "The scenario was rewritten against the verified budget behaviour; the next iteration passes (row seq 10)."},
    {"what": "OpenAPI/binary consistency probe exited 1: the check mis-assumed openapi.HTTP_METHODS (uppercase frozenset including PATCH).",
     "evidence": "command row seq 15 (exit_code 1)",
     "resolution": "Corrected expectation; the next run passes (row seq 16)."},
    {"what": "First in-process app smoke exited 1: the five binary routes were not yet documented by the OpenAPI helper (AssertionError listing all five); the transport answers themselves were already observed OK.",
     "evidence": "command row seq 20 (exit_code 1)",
     "resolution": "BINARY_ROUTE_RESPONSES documented and exported (row seq 21); the next smoke proceeds to the media check."},
    {"what": "Second app smoke exited 1: documented 200 media lists still included application/json for the document routes.",
     "evidence": "command row seq 22 (exit_code 1)",
     "resolution": "Media lists aligned with the runtime (rows seq 23); the third smoke passes end to end (row seq 24)."},
    {"what": "Intermediate full-suite run after the route flip: the output reported 11 failed / 567 passed - the old tests still expected the five routes to be deferred. The process exit code was masked to 0 by the `| tail` pipeline without pipefail; flagged here so the real regression is not hidden.",
     "evidence": "command row seq 25 (exit_code 0, masked; 11 failed in output)",
     "exit_code_masked": True,
     "resolution": "Test expectations updated to the new inventory (rows seq 26-28); the next full run reports 579 passed (row seq 29)."},
    {"what": "First full A11 suite run exited 1: 3 failed, 708 passed - two transport tests because content responses used the bare id as filename instead of id.extension, and the size-mismatch store test because its setup never wrote the sample bytes.",
     "evidence": "command row seq 34 (exit_code 1)",
     "resolution": "Fixed in app.py (row seq 36) and the test (row seq 37); targeted re-run passes (row seq 38) and the full suite reaches 711 passed (row seq 39)."},
    {"what": "Targeted re-run of the three failing tests exited 1, reproducing the failures deterministically before the fix.",
     "evidence": "command row seq 35 (exit_code 1)",
     "resolution": "Same fixes as the previous entry (rows seq 36-37); re-run passes (row seq 38)."},
]

REMAINING_GAPS = [
    "Only synthetic fixtures and in-process TestClient requests are used: no original database, no upstream fetch, no CIE batch resume, no service start.",
    "The 12 payload files are small synthetic placeholders (not real Cambridge/edexcel/IELTS material); real sample ingestion, hashing and rights review stay a Phase B concern.",
    "Syllabuses and materials content are served from labelled synthetic fixtures; active materials and historical timetable integration remain deferred to the active owner.",
    "206/304/416 are transport-level statuses emitted for binary responses; they are documented in envelope.BINARY_STATUSES as a carve-out outside the plan 5.2 JSON error map (which describes error bodies), analogous to FRAMEWORK_STATUSES 405.",
    "Legacy 71-route compatibility is A12; the frontend proposal is A13; the file-by-file merge map is A14; PHASE_A_REPORT.md is A15.",
    "The staged API is not the production service and is not deployed; the live database, service restart, upstream crawl and CIE batch resume remain Phase B and require explicit human release.",
]

EVIDENCE_PATHS = [
    "docs/integration/execution/A11_REPORT.md",
    "docs/integration/execution/evidence/A11/binary_stdout.txt",
    "docs/integration/execution/evidence/A11/final_checks.txt",
    "docs/integration/execution/evidence/A11/pytest_run_stdout.txt",
    "docs/integration/execution/evidence/A11/a10_probe_rerun.txt",
    "docs/integration/execution/execution-ledger.json",
    "integration-staging/fixtures/synthetic/binary/manifest.json",
    "integration-staging/fixtures/synthetic/binary/PROVENANCE.json",
    "integration-staging/runtime/ledger-patches/A11_close.json",
    "integration-staging/src/examdata_integration/api/__init__.py",
    "integration-staging/src/examdata_integration/api/app.py",
    "integration-staging/src/examdata_integration/api/binary.py",
    "integration-staging/src/examdata_integration/api/envelope.py",
    "integration-staging/src/examdata_integration/api/links.py",
    "integration-staging/src/examdata_integration/api/openapi.py",
    "integration-staging/tests/test_api_binary_fixtures.py",
    "integration-staging/tests/test_api_binary_store.py",
    "integration-staging/tests/test_api_binary_transport.py",
    "integration-staging/tests/test_api_envelope.py",
    "integration-staging/tests/test_api_links_openapi.py",
    "integration-staging/tests/test_api_routes.py",
    "integration-staging/tools/a10_probe_api.py",
    "integration-staging/tools/a11_close_patch.py",
    "integration-staging/tools/a11_final_checks.py",
    "integration-staging/tools/a11_probe_binary.py",
    "integration-staging/tools/build_binary_fixtures.py",
]

NEXT_ACTION = ("A12 - legacy compatibility worksheet (plan section 11): one row for every route of the 71-route "
               "baseline in docs/integration/ROUTE_INVENTORY_CURRENT.json (plus any routes added since), with the "
               "allowed compatibility status per row, the staged v2 equivalent, and the merge-time requirement; then "
               "A13 frontend proposal (copy-only), A14 file-by-file merge map, A15 PHASE_A_REPORT.md.")

NOTES = ("All A11 inputs are synthetic fixtures or frozen contract/provider/catalog/harness sources; no original "
         "file was read and nothing was fetched. Eight recorded commands exited 1 during development and were "
         "resolved in-packet (rows seq 5, 8, 9, 15, 20, 22, 34, 35); one intermediate suite run (row seq 25) "
         "reported 11 failed / 567 passed in its output while its process exit code was masked to 0 by a `| tail` "
         "pipeline without pipefail - it is recorded as a failure with exit_code_masked=true so the regression "
         "signal is not hidden. Trivial exploratory shell calls also exited nonzero without product impact and are "
         "noted here rather than as failures: a wrong-directory `ls` (rc 2), a `jq` call where jq is not installed "
         "(rc 127), and a few session-log/audit scripts that exited 1 by their own audit logic; they ran against "
         "the session event log or trivia and touched no project file. The five binary routes are now implemented, "
         "advertised and documented (34/34/34 pairs, DEFERRED_SPECS empty); the A10 probe was updated only for its "
         "inventory counts and still passes 82/82. Everything is staged: nothing is merged, nothing is deployed, "
         "and all seven Phase B gates stay closed.")


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
        "dependencies": ["A10"],
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
