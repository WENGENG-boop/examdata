#!/usr/bin/env python3
"""Build the A05 ledger close patch (docs/integration/execution/execution-ledger.json).

Computes the input hashes over the true inputs plus the A05 write set (excluding
the closing-checks transcript, which is produced *after* the ledger closes, and
this patch file itself), and emits a JSON object to be merged into the A05 task
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
OUT = STAGING / "runtime" / "ledger-patches" / "A05_close.json"

ROOTS = [STAGING.as_posix(), EXEC.as_posix()]

INPUTS = [
    "docs/integration/EXECUTOR_PROMPT_EN.md",
    "docs/integration/MASTER_EXECUTION_PLAN_EN.md",
    "docs/integration/ROUTE_INVENTORY_CURRENT.json",
    "docs/PROJECT_STATUS.md",
    "docs/integration/execution/execution-ledger.json",
    "docs/integration/execution/A04_REPORT.md",
    "docs/integration/execution/A04_IDENTITY_DECISION.md",
    "docs/integration/execution/evidence/A04/final_checks.txt",
    "docs/integration/execution/evidence/A04/pytest_run_stdout.txt",
    "integration-staging/fixtures/PROVENANCE.json",
    "integration-staging/fixtures/synthetic/ielts/questions-synthetic.json",
    "integration-staging/fixtures/synthetic/cie/cie-index-synthetic.json",
    "integration-staging/fixtures/synthetic/edexcel/index-synthetic.json",
    "integration-staging/src/examdata_integration/contracts/models.py",
    "integration-staging/src/examdata_integration/contracts/canonical.py",
    "integration-staging/src/examdata_integration/contracts/enums.py",
]

WRITE_GLOBS = [
    "integration-staging/src/examdata_integration/providers/*.py",
    "integration-staging/tools/a05_*.py",
    "integration-staging/tests/test_providers_*.py",
    "integration-staging/runtime/ledger-patches/A05_close.json",
    "docs/integration/execution/A05_REPORT.md",
    "docs/integration/execution/evidence/A05/*.txt",
]

# produced only after the ledger closes: listed but never hashed into the patch
POST_CLOSE = {
    "docs/integration/execution/evidence/A05/final_checks.txt",
}

COMMANDS = [
    {"seq": 1, "purpose": "Create the provider package and the A05 evidence directory.",
     "tool": "Bash",
     "command": "mkdir -p integration-staging/src/examdata_integration/providers integration-staging/runtime/ledger-patches docs/integration/execution/evidence/A05",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0, "evidence": None},
    {"seq": 2, "purpose": "Write the provider layer: capabilities, results, protocol, registry, fixtures, __init__.",
     "tool": "Write",
     "command": "Write tool: integration-staging/src/examdata_integration/providers/{capabilities,results,protocol,registry,fixtures,__init__}.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/src/examdata_integration/providers/"},
    {"seq": 3, "purpose": "Write and run the 20-scenario offline dispatch probe.",
     "tool": "Bash",
     "command": "examdata/.venv/Scripts/python.exe integration-staging/tools/a05_probe_dispatch.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "docs/integration/execution/evidence/A05/dispatch_stdout.txt"},
    {"seq": 4, "purpose": "Write the A05 test modules (registry semantics; fixture mapping).",
     "tool": "Write",
     "command": "Write tool: integration-staging/tests/test_providers_registry.py, test_providers_fixtures.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/tests/"},
    {"seq": 5, "purpose": "First staged-suite run (3 defects surfaced: 1 real, 2 test-side).",
     "tool": "Bash", "command": "bash integration-staging/tools/run_staged_tests.sh -q",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 1,
     "evidence": "docs/integration/execution/evidence/A05/pytest_run_stdout.txt"},
    {"seq": 6, "purpose": "Redact filesystem paths in provider exception details (results._sanitize).",
     "tool": "Edit",
     "command": "Edit tool: integration-staging/src/examdata_integration/providers/results.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/src/examdata_integration/providers/results.py"},
    {"seq": 7, "purpose": "Fix the two A05 test-side defects (precedence provider capability; table-question selector).",
     "tool": "Edit",
     "command": "Edit tool: integration-staging/tests/test_providers_registry.py, test_providers_fixtures.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/tests/"},
    {"seq": 8, "purpose": "Re-run the staged suite to green.",
     "tool": "Bash", "command": "bash integration-staging/tools/run_staged_tests.sh -q",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "docs/integration/execution/evidence/A05/pytest_run_stdout.txt"},
    {"seq": 9, "purpose": "Re-run the dispatch probe after the redaction change.",
     "tool": "Bash",
     "command": "examdata/.venv/Scripts/python.exe integration-staging/tools/a05_probe_dispatch.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "docs/integration/execution/evidence/A05/dispatch_stdout.txt"},
    {"seq": 10, "purpose": "Write the A05 report.",
     "tool": "Write", "command": "Write tool: docs/integration/execution/A05_REPORT.md",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "docs/integration/execution/A05_REPORT.md"},
    {"seq": 11, "purpose": "Write the A05 closing-checks runner.",
     "tool": "Write", "command": "Write tool: integration-staging/tools/a05_final_checks.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/tools/a05_final_checks.py"},
    {"seq": 12, "purpose": "Write the A05 ledger close-patch builder.",
     "tool": "Write", "command": "Write tool: integration-staging/tools/a05_close_patch.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/tools/a05_close_patch.py"},
    {"seq": 13, "purpose": "Run the A05 closing checks (after the ledger is closed).",
     "tool": "Bash",
     "command": "examdata/.venv/Scripts/python.exe integration-staging/tools/a05_final_checks.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": None,
     "evidence": "docs/integration/execution/evidence/A05/final_checks.txt"},
]

TEST_RESULTS = [
    {"check": "Dispatch probe: 20/20 scenarios PASS offline (A05_PROBE: PASS)",
     "result": "pass", "exit_code": 0,
     "evidence": "docs/integration/execution/evidence/A05/dispatch_stdout.txt",
     "label": "synthetic_fixture",
     "note": "Capability filtering, alias routing, partial/unavailable/all-fail, empty-vs-unsupported, no-provider-requested and error precedence, over the A03 synthetic fixtures."},
    {"check": "Staged suite passes offline: 141 tests (66 new A05 + 75 A03/A04), 0 failures",
     "result": "pass", "exit_code": 0,
     "evidence": "docs/integration/execution/evidence/A05/pytest_run_stdout.txt",
     "label": "synthetic_fixture",
     "note": "Registry semantics and fixture mapping, in the isolated harness with the module and network guards active."},
    {"check": "Registry semantics: filtering precedes dispatch; unsupported != empty; filter_rejected; deterministic precedence",
     "result": "pass", "exit_code": 0,
     "evidence": "integration-staging/tests/test_providers_registry.py",
     "label": "synthetic_fixture",
     "note": "A spy provider asserts the provider is never called for an unsupported capability or an uninterpretable filter."},
    {"check": "Fixture mapping: hierarchy, tables, grouped alternatives, missing answer slot, conflicts and gaps preserved",
     "result": "pass", "exit_code": 0,
     "evidence": "integration-staging/tests/test_providers_fixtures.py",
     "label": "synthetic_fixture",
     "note": "Every emitted model is synthetic and every answer stays unverified; coverage arithmetic is self-consistent."},
    {"check": "Provider exception detail is path-redacted (no local path in the public error surface)",
     "result": "pass", "exit_code": 0,
     "evidence": "integration-staging/tests/test_providers_registry.py",
     "label": "static_inspection",
     "note": "results._sanitize replaces drive-rooted and POSIX paths with <path> while keeping the exception type."},
]

FAILURES = [
    {"what": "First A05 staged-suite run exited 1: 3 tests failed (test_cie_table_question_maps_to_a_table_payload; test_provider_exception_is_sanitized; test_error_precedence_is_deterministic).",
     "evidence": "command row seq 5 (exit_code 1); the failing transcript was replaced by the passing re-run",
     "resolution": "One real defect and two test-side defects. Real: results._sanitize bounded length but did not remove filesystem paths, so a provider exception carrying C:\\private\\path\\secret.db leaked the path into the public error message - fixed by redacting drive-rooted/POSIX paths to <path> (the exception type is still reported). Test-side: the precedence test registered its 'unsupported' provider with the capability it dispatched for, so the provider succeeded; and the CIE table test used a gate filter instead of target narrowing. Both tests were corrected; the provider layer was not weakened."},
]

REMAINING_GAPS = [
    "No real-data adapter exists yet: providers read only the A03 synthetic fixtures. Real CIE/Edexcel/IELTS/TOEFL read adapters are A07/A08.",
    "tags, materials and timetable are intentionally unimplemented (no fixture; owned by the active owner), so those capabilities return a typed unsupported result - recorded as deferred_active_owner, not a defect.",
    "The capability model is the plan's ten read operations; write operations are out of scope for the read-only integration.",
    "results._sanitize redaction is a conservative path heuristic (drive-rooted and POSIX paths); the v2 layer (A10) sanitizes again, and neither is a substitute for not emitting secrets in the first place.",
    "Real-data behaviour, cross-source reconciliation and any promotion to verified stay Phase B behind the write-authorization gate.",
]

EVIDENCE_PATHS = [
    "docs/integration/execution/A05_REPORT.md",
    "docs/integration/execution/evidence/A05/dispatch_stdout.txt",
    "docs/integration/execution/evidence/A05/final_checks.txt",
    "docs/integration/execution/evidence/A05/pytest_run_stdout.txt",
    "docs/integration/execution/execution-ledger.json",
    "integration-staging/runtime/ledger-patches/A05_close.json",
    "integration-staging/src/examdata_integration/providers/__init__.py",
    "integration-staging/src/examdata_integration/providers/capabilities.py",
    "integration-staging/src/examdata_integration/providers/fixtures.py",
    "integration-staging/src/examdata_integration/providers/protocol.py",
    "integration-staging/src/examdata_integration/providers/registry.py",
    "integration-staging/src/examdata_integration/providers/results.py",
    "integration-staging/tests/test_providers_fixtures.py",
    "integration-staging/tests/test_providers_registry.py",
    "integration-staging/tools/a05_close_patch.py",
    "integration-staging/tools/a05_final_checks.py",
    "integration-staging/tools/a05_probe_dispatch.py",
]

NEXT_ACTION = ("A06 - configuration and the controlled Node runner (plan section 11): freeze the gateway spawn "
               "contract, an environment template and a confined Node runner that resolves only inside the staged "
               "tree, with tests for missing executable, spaces in paths, invalid/multiple JSON values, non-zero "
               "exit, stderr redaction, queue-full, output overflow, timeout, cancellation, process cleanup and "
               "environment precedence - all offline.")


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
        "dependencies": ["A04"],
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
