#!/usr/bin/env python3
"""Build the A12 ledger close patch (docs/integration/execution/execution-ledger.json).

Computes the input hashes over the true inputs plus the A12 write set (excluding
the post-close transcripts, which are produced *after* the ledger closes, and
this patch file itself), and emits a JSON object to be merged into the A12 task
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
OUT = STAGING / "runtime" / "ledger-patches" / "A12_close.json"

ROOTS = [STAGING.as_posix(), EXEC.as_posix()]

INPUTS = [
    "docs/integration/EXECUTOR_PROMPT_EN.md",
    "docs/integration/MASTER_EXECUTION_PLAN_EN.md",
    "docs/integration/ROUTE_INVENTORY_CURRENT.json",
    "docs/PROJECT_STATUS.md",
    "docs/integration/execution/execution-ledger.json",
    "docs/integration/execution/A11_REPORT.md",
    "docs/integration/execution/A01_ROUTE_COMPATIBILITY_WORKSHEET.json",
    "docs/integration/execution/evidence/A12/legacy_shape_extract.json",
    # the four original api modules: AST-extracted only, never imported/executed;
    # their byte hashes are recorded in the registry and re-checked at close
    "examdata/src/examdata/api/app.py",
    "examdata/src/examdata/api/unified.py",
    "examdata/src/examdata/api/ielts.py",
    "examdata/src/examdata/api/toefl.py",
    # the original query service module recorded read-only for the shape extract
    "examdata/src/examdata/query/service.py",
    # frozen A04 contracts the legacy payloads are shaped against
    "integration-staging/src/examdata_integration/contracts/models.py",
    "integration-staging/src/examdata_integration/contracts/base.py",
    "integration-staging/src/examdata_integration/contracts/enums.py",
    "integration-staging/src/examdata_integration/contracts/canonical.py",
    "integration-staging/src/examdata_integration/contracts/quality.py",
    "integration-staging/src/examdata_integration/contracts/ids.py",
    "integration-staging/src/examdata_integration/contracts/jsonschema_lite.py",
    # frozen provider layer the fixture-translation rows read
    "integration-staging/src/examdata_integration/providers/capabilities.py",
    "integration-staging/src/examdata_integration/providers/results.py",
    "integration-staging/src/examdata_integration/providers/registry.py",
    "integration-staging/src/examdata_integration/providers/fixtures.py",
    # frozen A09 catalog the adapter rows build their dataset from
    "integration-staging/src/examdata_integration/catalog/model.py",
    "integration-staging/src/examdata_integration/catalog/store.py",
    "integration-staging/src/examdata_integration/catalog/builder.py",
    "integration-staging/src/examdata_integration/catalog/revision.py",
    # frozen staged v2 api modules the bridge contracts map onto
    "integration-staging/src/examdata_integration/api/dataset.py",
    "integration-staging/src/examdata_integration/api/binary.py",
    "integration-staging/src/examdata_integration/api/links.py",
    # frozen runner classification the bridge outcome mapping aligns with
    "integration-staging/src/examdata_integration/runtime/classification.py",
    # frozen A05 provider fixtures the dataset snapshot is built from
    "integration-staging/fixtures/synthetic/cie/cie-index-synthetic.json",
    "integration-staging/fixtures/synthetic/edexcel/index-synthetic.json",
    "integration-staging/fixtures/synthetic/ielts/questions-synthetic.json",
    # frozen A02-A11 harness the A12 tests run under
    "integration-staging/pytest.ini",
    "integration-staging/tests/conftest.py",
    "integration-staging/tools/run_staged_tests.sh",
    "integration-staging/tools/ledger_update.py",
    "integration-staging/src/examdata_integration/testing/guards.py",
]

WRITE_GLOBS = [
    # the whole legacy compatibility package is new and packet-owned
    "integration-staging/src/examdata_integration/legacy/*",
    # A12 test files: five new legacy modules
    "integration-staging/tests/test_legacy_*.py",
    # A12 tools (this close-patch builder included)
    "integration-staging/tools/a12_*.py",
    "integration-staging/runtime/ledger-patches/A12_close.json",
    # the A01-baseline worksheet produced by this packet
    "docs/integration/execution/A12_ROUTE_COMPATIBILITY_WORKSHEET.json",
    "docs/integration/execution/A12_REPORT.md",
    "docs/integration/execution/evidence/A12/*",
]

# produced only after the ledger closes: listed but never hashed into the patch
POST_CLOSE = {
    "docs/integration/execution/evidence/A12/final_checks.txt",
    "docs/integration/execution/evidence/A12/legacy_rerun.txt",
}

COMMANDS = [
    {"seq": 1, "purpose": "Create the A12 evidence directory.",
     "tool": "Bash",
     "command": "mkdir -p docs/integration/execution/evidence/A12",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0, "evidence": None},
    {"seq": 2, "purpose": "Write the static AST extractor for the four original FastAPI modules (route list, handler signatures, success/error shapes, native parameters, side effects, source hashes); it never imports or executes the modules.",
     "tool": "Write",
     "command": "Write tool: integration-staging/tools/a12_extract_legacy_shapes.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/tools/a12_extract_legacy_shapes.py"},
    {"seq": 3, "purpose": "Run the extractor: 64 handler shapes from the four api modules plus the module byte hashes, written to the A12 evidence file.",
     "tool": "Bash",
     "command": "examdata/.venv/Scripts/python.exe integration-staging/tools/a12_extract_legacy_shapes.py > docs/integration/execution/evidence/A12/legacy_shape_extract.json",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "docs/integration/execution/evidence/A12/legacy_shape_extract.json"},
    {"seq": 4, "purpose": "Write the v1 payload builders (translate.py): pure functions reproducing the statically extracted success shapes (pagination, question bundles, paper trees, boards, search, IELTS/TOEFL gateway payloads); no I/O.",
     "tool": "Write",
     "command": "Write tool: integration-staging/src/examdata_integration/legacy/translate.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/src/examdata_integration/legacy/translate.py"},
    {"seq": 5, "purpose": "Smoke-verify the payload builders against the extracted shapes (heredoc over legacy_shape_extract.json): every covered shape reproduced at contract level.",
     "tool": "Bash",
     "command": "PYTHONPATH=src examdata/.venv/Scripts/python.exe - <<'PY' (translate-vs-shapes smoke heredoc)",
     "cwd": "C:/Users/weo/Desktop/api/integration-staging", "exit_code": 0,
     "evidence": "integration-staging/src/examdata_integration/legacy/translate.py"},
    {"seq": 6, "purpose": "Write the shape/parity summariser (parity.py) and smoke-verify it against the extracted shapes.",
     "tool": "Write",
     "command": "Write tool: integration-staging/src/examdata_integration/legacy/parity.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/src/examdata_integration/legacy/parity.py"},
    {"seq": 7, "purpose": "Write the node-CLI bridge contract (bridge.py): RunResult -> legacy envelope mapping, outcome vocabulary aligned with runtime.classification.RunnerOutcome.",
     "tool": "Write",
     "command": "Write tool: integration-staging/src/examdata_integration/legacy/bridge.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/src/examdata_integration/legacy/bridge.py"},
    {"seq": 8, "purpose": "Write the registry/decisions vocabulary module (decisions.py): registry loader (rows/row_id/registry_sha256), mechanism and status vocabularies, evidence helpers.",
     "tool": "Write",
     "command": "Write tool: integration-staging/src/examdata_integration/legacy/decisions.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/src/examdata_integration/legacy/decisions.py"},
    {"seq": 9, "purpose": "Write the registry renderer (a12_build_registry.py): one row per baseline route from the A01 worksheet + the shape extract, with the registry sources hashed.",
     "tool": "Write",
     "command": "Write tool: integration-staging/tools/a12_build_registry.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/tools/a12_build_registry.py"},
    {"seq": 10, "purpose": "Iterate the registry builder before the first render (renderer wiring, record assembly): two edits.",
     "tool": "Edit",
     "command": "Edit tool: integration-staging/tools/a12_build_registry.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/tools/a12_build_registry.py"},
    {"seq": 11, "purpose": "Builder dry-run inspection: render the registry object to stdout without writing the file.",
     "tool": "Bash",
     "command": "examdata/.venv/Scripts/python.exe integration-staging/tools/a12_build_registry.py --dry-run",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0, "evidence": None},
    {"seq": 12, "purpose": "First registry render exited 1: KeyError 'path' while wiring the record from the shape extract (the builder assumed a 'path' field the extractor does not emit). Recorded as a failure; fixed in the next row.",
     "tool": "Bash",
     "command": "examdata/.venv/Scripts/python.exe integration-staging/tools/a12_build_registry.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 1,
     "evidence": "integration-staging/tools/a12_build_registry.py"},
    {"seq": 13, "purpose": "Fix the extractor/builder hand-off (source-path mapping): one edit.",
     "tool": "Edit",
     "command": "Edit tool: integration-staging/tools/a12_build_registry.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/tools/a12_build_registry.py"},
    {"seq": 14, "purpose": "Registry render succeeds: 71 baseline rows written to legacy/registry.json (schema examdata.integration.legacy_registry/1).",
     "tool": "Bash",
     "command": "examdata/.venv/Scripts/python.exe integration-staging/tools/a12_build_registry.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/src/examdata_integration/legacy/registry.json"},
    {"seq": 15, "purpose": "Write the payload-builder test module (missing-slot semantics incl. IELTS Q41, question hierarchy, table structures, document hashes).",
     "tool": "Write",
     "command": "Write tool: integration-staging/tests/test_legacy_translate.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/tests/test_legacy_translate.py"},
    {"seq": 16, "purpose": "Write the parity summariser test module.",
     "tool": "Write",
     "command": "Write tool: integration-staging/tests/test_legacy_parity.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/tests/test_legacy_parity.py"},
    {"seq": 17, "purpose": "Write the fixture-translation adapter test module (rows against default_dataset(); 21 adapter params + registry-level checks).",
     "tool": "Write",
     "command": "Write tool: integration-staging/tests/test_legacy_adapters.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/tests/test_legacy_adapters.py"},
    {"seq": 18, "purpose": "Write the registry/decisions test module (loader, row ids, vocabulary, evidence paths).",
     "tool": "Write",
     "command": "Write tool: integration-staging/tests/test_legacy_decisions.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/tests/test_legacy_decisions.py"},
    {"seq": 19, "purpose": "Bridge introspection heredoc exited 1: dataclasses.fields applied to a non-dataclass record (scratch-script misuse, no product impact). Recorded as a failure; rewritten in the next row.",
     "tool": "Bash",
     "command": "PYTHONPATH=src examdata/.venv/Scripts/python.exe - <<'PY' (bridge introspection heredoc)",
     "cwd": "C:/Users/weo/Desktop/api/integration-staging", "exit_code": 1,
     "evidence": "integration-staging/src/examdata_integration/legacy/bridge.py"},
    {"seq": 20, "purpose": "Rewritten introspection series passes: bridge record shape, board parameterisation and payload mapping observed as expected.",
     "tool": "Bash",
     "command": "PYTHONPATH=src examdata/.venv/Scripts/python.exe - <<'PY' (bridge introspection heredoc, rewritten)",
     "cwd": "C:/Users/weo/Desktop/api/integration-staging", "exit_code": 0,
     "evidence": "integration-staging/src/examdata_integration/legacy/bridge.py"},
    {"seq": 21, "purpose": "Write the bridge contract test module (static contract params for all 71 rows + node-bridge envelopes parameterised over ielts/toefl).",
     "tool": "Write",
     "command": "Write tool: integration-staging/tests/test_legacy_bridge_contracts.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/tests/test_legacy_bridge_contracts.py"},
    {"seq": 22, "purpose": "Test-prep edits after adding the bridge module (names/expectations): two edits.",
     "tool": "Edit",
     "command": "Edit tool: integration-staging/tests/test_legacy_bridge_contracts.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/tests/test_legacy_bridge_contracts.py"},
    {"seq": 23, "purpose": "First full legacy run reported 4 failed / 852 passed in its output (adapter serialisation; see failures). The `| tail -60` pipeline without pipefail masked the process exit code to 0.",
     "tool": "Bash",
     "command": "bash tools/run_staged_tests.sh 2>&1 | tail -60",
     "cwd": "C:/Users/weo/Desktop/api/integration-staging", "exit_code": 0,
     "evidence": None},
    {"seq": 24, "purpose": "Targeted reproduction of the four failures; the transcript was truncated and the process exit code is not observable from the record (noted in the failures list).",
     "tool": "Bash",
     "command": "bash tools/run_staged_tests.sh -k \"legacy_adapters\" (truncated transcript)",
     "cwd": "C:/Users/weo/Desktop/api/integration-staging", "exit_code": None,
     "evidence": None},
    {"seq": 25, "purpose": "Fix the adapters' serialisation: use entry.to_dict() instead of dataclasses.asdict (preserves the '__unknown__' token for parent_native_id=UNKNOWN).",
     "tool": "Edit",
     "command": "Edit tool: integration-staging/tests/test_legacy_adapters.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/tests/test_legacy_adapters.py"},
    {"seq": 26, "purpose": "Update the affected adapter expectations (row/unknown-slot forms): two edits.",
     "tool": "Edit",
     "command": "Edit tool: integration-staging/tests/test_legacy_adapters.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/tests/test_legacy_adapters.py"},
    {"seq": 27, "purpose": "Second full legacy run reported 1 failed / 855 passed (translate.legacy_search_page missing the board_source key; see failures). `| tail -30` masked the process exit code to 0.",
     "tool": "Bash",
     "command": "bash tools/run_staged_tests.sh 2>&1 | tail -30",
     "cwd": "C:/Users/weo/Desktop/api/integration-staging", "exit_code": 0,
     "evidence": None},
    {"seq": 28, "purpose": "Locate the failure by filtering on the search row: the [GET__api_v1_search] adapter test reproduces deterministically.",
     "tool": "Bash",
     "command": "bash tools/run_staged_tests.sh -k \"GET__api_v1_search\"",
     "cwd": "C:/Users/weo/Desktop/api/integration-staging", "exit_code": 0,
     "evidence": "integration-staging/tests/test_legacy_adapters.py"},
    {"seq": 29, "purpose": "Fix translate.legacy_search_page: add the board_source parameter and output key to match the extracted v1 shape.",
     "tool": "Edit",
     "command": "Edit tool: integration-staging/src/examdata_integration/legacy/translate.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/src/examdata_integration/legacy/translate.py"},
    {"seq": 30, "purpose": "Update the two tests affected by the search payload fix: two edits.",
     "tool": "Edit",
     "command": "Edit tool: integration-staging/tests/test_legacy_translate.py + test_legacy_adapters.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/tests/test_legacy_translate.py"},
    {"seq": 31, "purpose": "Green confirmation: full staged suite reports 856 passed, 0 failed.",
     "tool": "Bash",
     "command": "bash tools/run_staged_tests.sh",
     "cwd": "C:/Users/weo/Desktop/api/integration-staging", "exit_code": 0,
     "evidence": None},
    {"seq": 32, "purpose": "Capture the full-suite transcript as evidence (856 passed).",
     "tool": "Bash",
     "command": "bash tools/run_staged_tests.sh > ../docs/integration/execution/evidence/A12/pytest_run_stdout.txt",
     "cwd": "C:/Users/weo/Desktop/api/integration-staging", "exit_code": 0,
     "evidence": "docs/integration/execution/evidence/A12/pytest_run_stdout.txt"},
    {"seq": 33, "purpose": "Write the worksheet builder (a12_build_worksheet.py): A01 columns + row_id/mechanism/coverage_kind/owner/notes and the per-row extras, sources hashed, rescan included.",
     "tool": "Write",
     "command": "Write tool: integration-staging/tools/a12_build_worksheet.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/tools/a12_build_worksheet.py"},
    {"seq": 34, "purpose": "Run the worksheet builder: 71 rows, schema route_compatibility_worksheet/2, sources hashed, static rescan shows no drift.",
     "tool": "Bash",
     "command": "examdata/.venv/Scripts/python.exe integration-staging/tools/a12_build_worksheet.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "docs/integration/execution/A12_ROUTE_COMPATIBILITY_WORKSHEET.json"},
    {"seq": 35, "purpose": "Cross-check the worksheet against the registry and re-hash the A01 worksheet (71/71 rows, all chains agree).",
     "tool": "Bash",
     "command": "examdata/.venv/Scripts/python.exe - <<'PY' (worksheet/registry/A01 cross-check heredoc)",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0, "evidence": None},
    {"seq": 36, "purpose": "Capture the collection transcript (856 node ids) as evidence.",
     "tool": "Bash",
     "command": "examdata/.venv/Scripts/python.exe -m pytest -c pytest.ini tests --collect-only -q > ../docs/integration/execution/evidence/A12/collect_only_stdout.txt",
     "cwd": "C:/Users/weo/Desktop/api/integration-staging", "exit_code": 0,
     "evidence": "docs/integration/execution/evidence/A12/collect_only_stdout.txt"},
    {"seq": 37, "purpose": "Capture the targeted legacy run transcript (145 passed) as evidence.",
     "tool": "Bash",
     "command": "examdata/.venv/Scripts/python.exe -m pytest -c pytest.ini tests/test_legacy_*.py -q > ../docs/integration/execution/evidence/A12/legacy_tests_stdout.txt",
     "cwd": "C:/Users/weo/Desktop/api/integration-staging", "exit_code": 0,
     "evidence": "docs/integration/execution/evidence/A12/legacy_tests_stdout.txt"},
    {"seq": 38, "purpose": "Write the offline compatibility probe (a12_probe_compat.py): collect-only over the staged suite, verify every registry test id exists, run the five legacy modules, verify every row's evidence path and the full-suite evidence freshness.",
     "tool": "Write",
     "command": "Write tool: integration-staging/tools/a12_probe_compat.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/tools/a12_probe_compat.py"},
    {"seq": 39, "purpose": "First probe run exited 1 with 20 problems: the bridge rows referenced unparametrised test ids (test_node_bridge_envelope_ielts/_toefl) that pytest collects as [ielts]/[toefl]. The `; echo rc=$?` suffix masked the harness exit code to 0; the probe printed rc 1.",
     "tool": "Bash",
     "command": "examdata/.venv/Scripts/python.exe tools/a12_probe_compat.py; echo rc=$?",
     "cwd": "C:/Users/weo/Desktop/api/integration-staging", "exit_code": 0,
     "evidence": None},
    {"seq": 40, "purpose": "Rename the bridge test to test_node_bridge_envelope (parameterised over both boards; node count unchanged).",
     "tool": "Edit",
     "command": "Edit tool: integration-staging/tests/test_legacy_bridge_contracts.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/tests/test_legacy_bridge_contracts.py"},
    {"seq": 41, "purpose": "Update the registry generator to emit the parameterised ids ::test_node_bridge_envelope[{board}].",
     "tool": "Edit",
     "command": "Edit tool: integration-staging/tools/a12_build_registry.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/tools/a12_build_registry.py"},
    {"seq": 42, "purpose": "Small follow-up builder edit for the parameterised-id emission.",
     "tool": "Edit",
     "command": "Edit tool: integration-staging/tools/a12_build_registry.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/tools/a12_build_registry.py"},
    {"seq": 43, "purpose": "Rebuild the chain: registry (final sha256 f9e1870b...) and worksheet regenerated from the frozen sources.",
     "tool": "Bash",
     "command": "examdata/.venv/Scripts/python.exe integration-staging/tools/a12_build_registry.py && examdata/.venv/Scripts/python.exe integration-staging/tools/a12_build_worksheet.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/src/examdata_integration/legacy/registry.json"},
    {"seq": 44, "purpose": "Refresh the full-suite transcript evidence in the background (post-rename node set).",
     "tool": "Bash",
     "command": "bash tools/run_staged_tests.sh > ../docs/integration/execution/evidence/A12/pytest_run_stdout.txt",
     "cwd": "C:/Users/weo/Desktop/api/integration-staging", "exit_code": 0,
     "evidence": "docs/integration/execution/evidence/A12/pytest_run_stdout.txt"},
    {"seq": 45, "purpose": "Small probe-side edit (evidence-chain path handling).",
     "tool": "Edit",
     "command": "Edit tool: integration-staging/tools/a12_probe_compat.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/tools/a12_probe_compat.py"},
    {"seq": 46, "purpose": "Probe re-run: A12_PROBE: PASS (0 problems), written to the A12 evidence file.",
     "tool": "Bash",
     "command": "examdata/.venv/Scripts/python.exe tools/a12_probe_compat.py",
     "cwd": "C:/Users/weo/Desktop/api/integration-staging", "exit_code": 0,
     "evidence": "docs/integration/execution/evidence/A12/compat_probe.json"},
    {"seq": 47, "purpose": "Pre-close chain verification found an inconsistency (recorded as a failure found by pre-close verification): the probe recorded LF-form text hashes for the collect/legacy transcripts while write_text had applied Windows newline translation (CRLF on disk).",
     "tool": "Bash",
     "command": "examdata/.venv/Scripts/python.exe - <<'PY' (pre-close six-source chain check heredoc)",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0, "evidence": None},
    {"seq": 48, "purpose": "CRLF byte diagnostics: confirm the transcripts on disk are CRLF and that their byte hashes differ from the recorded LF-form hashes.",
     "tool": "Bash",
     "command": "examdata/.venv/Scripts/python.exe - <<'PY' (CRLF byte diagnostics heredoc)",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0, "evidence": None},
    {"seq": 49, "purpose": "Fix the probe's transcript writes to newline=\"\\n\" (first write point).",
     "tool": "Edit",
     "command": "Edit tool: integration-staging/tools/a12_probe_compat.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/tools/a12_probe_compat.py"},
    {"seq": 50, "purpose": "Fix the builder's write to newline=\"\\n\" (second write point).",
     "tool": "Edit",
     "command": "Edit tool: integration-staging/tools/a12_build_worksheet.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/tools/a12_build_worksheet.py"},
    {"seq": 51, "purpose": "Fix the third write point (stdout transcript writer) to newline=\"\\n\".",
     "tool": "Edit",
     "command": "Edit tool: integration-staging/tools/a12_probe_compat.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/tools/a12_probe_compat.py"},
    {"seq": 52, "purpose": "Probe final run: A12_PROBE: PASS; all six recorded source hashes byte-match the bytes on disk.",
     "tool": "Bash",
     "command": "examdata/.venv/Scripts/python.exe tools/a12_probe_compat.py",
     "cwd": "C:/Users/weo/Desktop/api/integration-staging", "exit_code": 0,
     "evidence": "docs/integration/execution/evidence/A12/compat_probe.json"},
    {"seq": 53, "purpose": "Independent sha256 verification of the six-source chain from a fresh script: ALL_SOURCES_OK: True.",
     "tool": "Bash",
     "command": "examdata/.venv/Scripts/python.exe - <<'PY' (independent chain verification heredoc, v2)",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0, "evidence": None},
    {"seq": 54, "purpose": "Cross-check the route inventory against the registry (71/71 baseline rows, no omissions, no duplicates).",
     "tool": "Bash",
     "command": "examdata/.venv/Scripts/python.exe - <<'PY' (route inventory vs registry cross-check heredoc)",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0, "evidence": None},
    {"seq": 55, "purpose": "Cross-check evidence/report numbers against the probe and the transcripts (counts, hashes, statuses).",
     "tool": "Bash",
     "command": "examdata/.venv/Scripts/python.exe - <<'PY' (evidence/report number cross-check heredoc)",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0, "evidence": None},
    {"seq": 56, "purpose": "Write the A12 report.",
     "tool": "Write",
     "command": "Write tool: docs/integration/execution/A12_REPORT.md",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "docs/integration/execution/A12_REPORT.md"},
    {"seq": 57, "purpose": "Write the A12 closing-checks runner.",
     "tool": "Write",
     "command": "Write tool: integration-staging/tools/a12_final_checks.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/tools/a12_final_checks.py"},
    {"seq": 58, "purpose": "Write the A12 ledger close-patch builder.",
     "tool": "Write",
     "command": "Write tool: integration-staging/tools/a12_close_patch.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/tools/a12_close_patch.py"},
    {"seq": 59, "purpose": "Build the A12 close patch (hashes the 40 inputs and the packet write set, excluding the post-close transcripts).",
     "tool": "Bash",
     "command": "examdata/.venv/Scripts/python.exe integration-staging/tools/a12_close_patch.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/runtime/ledger-patches/A12_close.json"},
    {"seq": 60, "purpose": "Close the A12 ledger record: status staged_pass with the patch merged in.",
     "tool": "Bash",
     "command": "examdata/.venv/Scripts/python.exe integration-staging/tools/ledger_update.py --task A12 --status staged_pass --patch-file integration-staging/runtime/ledger-patches/A12_close.json",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "docs/integration/execution/execution-ledger.json"},
    {"seq": 61, "purpose": "Run the A12 closing checks (first/bootstrap run after the ledger closes): exits 1 by construction because the two post-close transcripts it verifies do not exist yet; the run also exposed a checks-tool bug recorded in the failures.",
     "tool": "Bash",
     "command": "examdata/.venv/Scripts/python.exe integration-staging/tools/a12_final_checks.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 1,
     "evidence": "docs/integration/execution/evidence/A12/final_checks.txt"},
    {"seq": 62, "purpose": "Re-run the A12 closing checks after the checks-tool repair: FINAL_CHECKS: PASS (rewrites the final transcripts).",
     "tool": "Bash",
     "command": "examdata/.venv/Scripts/python.exe integration-staging/tools/a12_final_checks.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "docs/integration/execution/evidence/A12/final_checks.txt"},
]

TEST_RESULTS = [
    {"check": "Offline compatibility probe: 71/71 registry rows covered, 0 problems (A12_PROBE: PASS)",
     "result": "pass", "exit_code": 0,
     "evidence": "docs/integration/execution/evidence/A12/compat_probe.json",
     "label": "static_inspection",
     "note": "Registry rows 71, all with every recorded test id collected (142 ids) in the 856-node collection; adapter params 21/21 and static-contract params 71/71 in both directions; deferred rows 7; every row evidence_path exists; legacy run rc=0 with 145 passed / 0 failed; full-suite evidence freshness agrees (856 passed, sha256 22ed094396db65f85b27af7e7a29c361854868d445e070ded9c9d0b72f038df8). The six-source sha256 chain (registry, worksheet, A01 worksheet, full-suite transcript, both stdout transcripts) byte-matches disk."},
    {"check": "Staged suite passes offline: 856 tests, 0 failures",
     "result": "pass", "exit_code": 0,
     "evidence": "docs/integration/execution/evidence/A12/pytest_run_stdout.txt",
     "label": "synthetic_fixture",
     "note": "Net +145 over the A11 baseline of 711, from the five new legacy modules (translate 18, parity 10, adapters 24, decisions 11, bridge contracts 82); run inside integration-staging with the module and network guards active; no original path, service or database involved."},
    {"check": "Targeted legacy re-run at close: 145 passed / 0 failed",
     "result": "pass", "exit_code": 0,
     "evidence": "docs/integration/execution/evidence/A12/legacy_tests_stdout.txt",
     "label": "synthetic_fixture",
     "note": "The five legacy modules collect 145 tests; rerun by the probe and again by the closing checks (evidence/A12/legacy_rerun.txt)."},
    {"check": "Static shape extraction: 64 handler shapes + 4 api-module hashes, AST only",
     "result": "pass", "exit_code": 0,
     "evidence": "docs/integration/execution/evidence/A12/legacy_shape_extract.json",
     "label": "static_inspection",
     "note": "The four original modules (app/unified/ielts/toefl) were parsed without import or execution; their byte hashes recorded before and after the packet show no drift (app.py 753749fa..., unified.py 9568b295..., ielts.py 9d79ee00..., toefl.py 051449da...)."},
    {"check": "Worksheet covers the 71-route baseline: 71/71 rows, 64 staged_pass / 7 deferred_active_owner, rescan without drift",
     "result": "pass", "exit_code": 0,
     "evidence": "docs/integration/execution/A12_ROUTE_COMPATIBILITY_WORKSHEET.json",
     "label": "static_inspection",
     "note": "23 columns + row extras (row_origin/handler_doc_line/line/a01_proposal); mechanisms 21/16/20/7/7; coverage kinds envelope_contract 33 / static_contract 24 / fixture_translation 14; post_baseline_count 0; problems []; the two active-owner router files (materials/timetable) exist - existence checked only, never parsed or executed."},
]

FAILURES = [
    {"what": "First registry render exited 1: KeyError 'path' while wiring the record from the shape extract (the builder assumed a 'path' field the extractor does not emit).",
     "exit_code": 1,
     "evidence": "command row seq 12 (exit_code 1)",
     "resolution": "The extractor/builder hand-off was fixed by edit (row seq 13); the render re-ran green and wrote the 71-row registry.json (row seq 14)."},
    {"what": "Bridge introspection heredoc exited 1: dataclasses.fields applied to a non-dataclass record (scratch-script misuse, no product impact).",
     "exit_code": 1,
     "evidence": "command row seq 19 (exit_code 1)",
     "resolution": "The introspection series was rewritten (row seq 20) and passes; the observed record shape fed the bridge contract tests (row seq 21)."},
    {"what": "First full legacy run reported 4 failed / 852 passed in its output (adapter tests serialised CatalogEntry with dataclasses.asdict, which raises TypeError on parent_native_id=UNKNOWN); the process exit code was masked to 0 by the `| tail -60` pipeline without pipefail.",
     "exit_code": 0,
     "exit_code_masked": True,
     "evidence": "command row seq 23 (exit_code 0, masked; 4 failed in output)",
     "resolution": "Fixed with entry.to_dict() and updated expectations (rows seq 25-26); the next full run reported 1 failed / 855 passed (row seq 27), then green 856 (row seq 31)."},
    {"what": "Second full run reported 1 failed / 855 passed: translate.legacy_search_page did not emit the board_source key the extracted v1 shape requires; the process exit code was masked to 0 by the `| tail -30` pipeline without pipefail.",
     "exit_code": 0,
     "exit_code_masked": True,
     "evidence": "command row seq 27 (exit_code 0, masked; 1 failed in output)",
     "resolution": "Parameter and output key added in translate.py and the two affected tests updated (rows seq 29-30); the suite then reported 856 passed (row seq 31)."},
    {"what": "First compatibility probe run exited 1 with 20 problems: the registry referenced unparametrised bridge test ids (test_node_bridge_envelope_ielts/_toefl) that pytest collects as [ielts]/[toefl]. The `; echo rc=$?` suffix masked the harness exit code to 0; the probe printed rc 1.",
     "exit_code": 0,
     "exit_code_masked": True,
     "evidence": "command row seq 39 (exit_code 0, masked; printed rc 1)",
     "resolution": "Test renamed test_node_bridge_envelope (parameterised) and the registry generator updated to emit ::test_node_bridge_envelope[{board}] (rows seq 40-42); the chain was rebuilt (row seq 43) and the probe reported PASS with 0 problems (row seq 46)."},
    {"what": "Pre-close chain verification found the probe recording LF-form text hashes for the collect/legacy transcripts while write_text had applied Windows newline translation (CRLF on disk); the byte hashes of the same content disagreed.",
     "exit_code": None,
     "found_by": "pre_close_verification",
     "evidence": "command rows seq 47-48",
     "resolution": "All probe/builder output writers fixed to newline=\"\\n\" (rows seq 49-51); the probe re-ran PASS with all six source hashes byte-matching disk (row seq 52) and was independently re-verified (row seq 53, ALL_SOURCES_OK: True)."},
    {"what": "First (bootstrap) run of the closing checks exited 1: by construction the two post-close transcripts did not exist yet, and the run also exposed a bug in the checks tool itself - the six-source chain check unpacked the sha-only expectation map as (path, sha) pairs, raising ValueError('too many values to unpack (expected 2)') and aborting the probe-facts section.",
     "exit_code": 1,
     "evidence": "command row seq 61 (exit_code 1, bootstrap run)",
     "resolution": "The expectation map was changed to (path, sha256) pairs and the ledger predicates were updated; the close patch was rebuilt and the ledger re-merged (rows seq 59-60 re-run), and the closing checks re-ran green (row seq 62, FINAL_CHECKS: PASS)."},
]

REMAINING_GAPS = [
    "Legacy compatibility is proven at the payload/contract level only: no real v1 traffic replay, no node CLI execution, no database merge - all Phase B and closed behind the human release.",
    "The 7 materials/timetable rows stay deferred_active_owner: their source modules were never parsed or executed and depend on the active owner's in-flight changes.",
    "Post-baseline routes are detectable (the worksheet builder appends them as post_baseline_unreviewed) but no route was added during A12 (post_baseline_count 0); any later addition needs review in a later packet.",
    "The node-CLI bridge is contract-level over synthetic RunResult records; no node process and no aggregator directory were involved.",
    "The registry records one probe-level truth per row (evidence_path), not per-row runtime traces.",
    "A13 frontend proposal, A14 file-by-file merge map and A15 PHASE_A_REPORT.md remain; everything is staged, nothing is merged or deployed, and all seven Phase B gates stay closed.",
]

EVIDENCE_PATHS = [
    "docs/integration/execution/A12_REPORT.md",
    "docs/integration/execution/A12_ROUTE_COMPATIBILITY_WORKSHEET.json",
    "docs/integration/execution/evidence/A12/legacy_shape_extract.json",
    "docs/integration/execution/evidence/A12/pytest_run_stdout.txt",
    "docs/integration/execution/evidence/A12/collect_only_stdout.txt",
    "docs/integration/execution/evidence/A12/legacy_tests_stdout.txt",
    "docs/integration/execution/evidence/A12/compat_probe.json",
    "docs/integration/execution/evidence/A12/final_checks.txt",
    "docs/integration/execution/evidence/A12/legacy_rerun.txt",
    "docs/integration/execution/execution-ledger.json",
    "integration-staging/runtime/ledger-patches/A12_close.json",
    "integration-staging/src/examdata_integration/legacy/__init__.py",
    "integration-staging/src/examdata_integration/legacy/bridge.py",
    "integration-staging/src/examdata_integration/legacy/decisions.py",
    "integration-staging/src/examdata_integration/legacy/parity.py",
    "integration-staging/src/examdata_integration/legacy/registry.json",
    "integration-staging/src/examdata_integration/legacy/translate.py",
    "integration-staging/tests/test_legacy_adapters.py",
    "integration-staging/tests/test_legacy_bridge_contracts.py",
    "integration-staging/tests/test_legacy_decisions.py",
    "integration-staging/tests/test_legacy_parity.py",
    "integration-staging/tests/test_legacy_translate.py",
    "integration-staging/tools/a12_build_registry.py",
    "integration-staging/tools/a12_build_worksheet.py",
    "integration-staging/tools/a12_close_patch.py",
    "integration-staging/tools/a12_extract_legacy_shapes.py",
    "integration-staging/tools/a12_final_checks.py",
    "integration-staging/tools/a12_probe_compat.py",
]

NEXT_ACTION = ("A13 - frontend proposal (copy-only): list the frontend files to copy into integration-staging/ "
               "and the integration points, without touching frontend/; then A14 file-by-file merge map (base "
               "hashes, active-owner rows kept separate), A15 PHASE_A_REPORT.md + deferred list + release request. "
               "All seven Phase B gates remain closed; only the human user can release the original paths.")

NOTES = ("All A12 inputs are frozen A01-A11 artefacts plus read-only originals read with AST only; no original file "
         "was written, no original test or application was run, nothing was fetched, no service or database was "
         "touched and the CIE batch was not resumed. Command rows are shortened single-line forms of the recorded "
         "operations. Three commands exited 1 and were resolved in-packet (rows seq 12 and 19, plus the first "
         "bootstrap run of the closing checks, row seq 61); three "
         "pipeline runs (rows seq 23, 27, 39) reported failures in their output while their exit codes were masked "
         "to 0 - they are recorded as failures with exit_code_masked=true; one targeted reproduction (row seq 24) "
         "has a truncated transcript and an unobservable exit code. The bootstrap run of the closing checks "
         "additionally exposed a bug in the checks tool itself (the six-source expectation map was unpacked as "
         "(path, sha) pairs), fixed before the close patch was rebuilt and the ledger re-merged (rows seq 59-60 "
         "re-run) and the closing checks re-ran green (row seq 62). Trivial exploratory shell "
         "calls and session-log/audit helper scripts also exited nonzero without product impact (they ran against "
         "the session event log or scratch logic, touching no project file), and an earlier version of the "
         "independent chain verifier raised a TypeError before its corrected v2 run succeeded (row seq 53); they "
         "are noted here rather than as failures. The four original api modules stayed byte-identical through the "
         "packet; the chain A01 -> registry -> worksheet -> probe -> evidence is sha256-verified end to end. "
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
    for r in INPUTS:
        p = WS / r
        if p.is_file():
            input_hashes[r] = sha256_file(p)
    for r in changed_files:
        if r in POST_CLOSE:
            continue
        input_hashes[r] = sha256_file(WS / r)

    patch = {
        "dependencies": ["A11"],
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
