#!/usr/bin/env python3
"""Build the A06 ledger close patch (docs/integration/execution/execution-ledger.json).

Computes the input hashes over the true inputs plus the A06 write set (excluding
the closing-checks transcript, which is produced *after* the ledger closes, and
this patch file itself), and emits a JSON object to be merged into the A06 task
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
OUT = STAGING / "runtime" / "ledger-patches" / "A06_close.json"

ROOTS = [STAGING.as_posix(), EXEC.as_posix()]

INPUTS = [
    "docs/integration/EXECUTOR_PROMPT_EN.md",
    "docs/integration/MASTER_EXECUTION_PLAN_EN.md",
    "docs/integration/ROUTE_INVENTORY_CURRENT.json",
    "docs/PROJECT_STATUS.md",
    "docs/integration/execution/execution-ledger.json",
    "docs/integration/execution/A05_REPORT.md",
    "docs/integration/execution/evidence/A05/final_checks.txt",
    "docs/integration/execution/evidence/A05/pytest_run_stdout.txt",
    # original gateway sources inspected read-only for the spawn contract
    # (point-in-time hashes: Kimi may edit these concurrently)
    "examdata/src/examdata/api/ielts.py",
    "examdata/src/examdata/api/toefl.py",
    "examdata/src/examdata/core/config.py",
    "examdata/src/examdata/api/security.py",
    # frozen A02-A05 harness the A06 tests run under
    "integration-staging/pytest.ini",
    "integration-staging/tests/conftest.py",
    "integration-staging/tools/run_staged_tests.sh",
    "integration-staging/tools/ledger_update.py",
    "integration-staging/src/examdata_integration/testing/guards.py",
    "integration-staging/src/examdata_integration/testing/node_guard.py",
]

WRITE_GLOBS = [
    "integration-staging/src/examdata_integration/runtime/*.py",
    "integration-staging/src/examdata_integration/testing/runtime_support.py",
    "integration-staging/components/*",
    "integration-staging/components/**/*",
    "integration-staging/config/*",
    "integration-staging/tools/a06_*.py",
    "integration-staging/tests/test_config_*.py",
    "integration-staging/tests/test_runner_*.py",
    "integration-staging/runtime/ledger-patches/A06_close.json",
    "docs/integration/execution/A06_REPORT.md",
    "docs/integration/execution/evidence/A06/*.txt",
]

# produced only after the ledger closes: listed but never hashed into the patch
POST_CLOSE = {
    "docs/integration/execution/evidence/A06/final_checks.txt",
}

COMMANDS = [
    {"seq": 1, "purpose": "Create the A06 directories (components, config, runtime scratch, evidence).",
     "tool": "Bash",
     "command": "mkdir -p integration-staging/components/fake-node-cli integration-staging/config integration-staging/runtime/tmp integration-staging/runtime/ledger-patches docs/integration/execution/evidence/A06",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0, "evidence": None},
    {"seq": 2, "purpose": "Write the synthetic Node CLI component, its manifest and a provenance note.",
     "tool": "Write",
     "command": "Write tool: integration-staging/components/fake-node-cli/fake-cli.mjs, components/manifest.json, components/README.md",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/components/manifest.json"},
    {"seq": 3, "purpose": "Write the runtime package: settings, manifest, classification, redact, runner, doctor, __init__.",
     "tool": "Write",
     "command": "Write tool: integration-staging/src/examdata_integration/runtime/{settings,manifest,classification,redact,runner,doctor,__init__}.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/src/examdata_integration/runtime/"},
    {"seq": 4, "purpose": "Write the A06 test-only fixture helpers and the config examples.",
     "tool": "Write",
     "command": "Write tool: integration-staging/src/examdata_integration/testing/runtime_support.py, config/{staging.env.example,staging-config.example.json,README.md}",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/config/staging.env.example"},
    {"seq": 5, "purpose": "First inline smoke run of NodeRunner over the fake CLI (real node subprocesses).",
     "tool": "Bash",
     "command": "PYTHONPATH=integration-staging/src examdata/.venv/Scripts/python.exe -c \"<inline NodeRunner smoke: ok/env/nonzero/slow/flood/cancel>\"",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 1,
     "evidence": "integration-staging/src/examdata_integration/runtime/runner.py"},
    {"seq": 6, "purpose": "Fix the three runner defects the smoke run surfaced (case-insensitive Windows env; absolute deployment root for relative component paths; join readers before classifying).",
     "tool": "Edit",
     "command": "Edit tool: integration-staging/src/examdata_integration/runtime/{runner,manifest,settings}.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/src/examdata_integration/runtime/runner.py"},
    {"seq": 7, "purpose": "Re-run the inline smoke; all classifications and cleanup evidence now correct.",
     "tool": "Bash",
     "command": "PYTHONPATH=integration-staging/src examdata/.venv/Scripts/python.exe -c \"<inline NodeRunner smoke re-run>\"",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/src/examdata_integration/runtime/runner.py"},
    {"seq": 8, "purpose": "Write the four A06 test modules (configuration, manifest/doctor, runner classification, runner bounds).",
     "tool": "Write",
     "command": "Write tool: integration-staging/tests/{test_config_resolution,test_config_manifest,test_runner_classification,test_runner_limits}.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/tests/"},
    {"seq": 9, "purpose": "First staged-suite run: 3 test-side assumption errors (ConfigLayer values; a parametrised case id).",
     "tool": "Bash", "command": "bash integration-staging/tools/run_staged_tests.sh -q",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 1,
     "evidence": "docs/integration/execution/evidence/A06/pytest_run_stdout.txt"},
    {"seq": 10, "purpose": "Fix the three test-side assumptions (no product change).",
     "tool": "Edit",
     "command": "Edit tool: integration-staging/tests/test_config_resolution.py, test_config_manifest.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/tests/"},
    {"seq": 11, "purpose": "Re-run the staged suite to green (232 passed).",
     "tool": "Bash", "command": "bash integration-staging/tools/run_staged_tests.sh -q",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "docs/integration/execution/evidence/A06/pytest_run_stdout.txt"},
    {"seq": 12, "purpose": "Run the 31-scenario offline runtime probe and capture its transcript.",
     "tool": "Bash",
     "command": "examdata/.venv/Scripts/python.exe integration-staging/tools/a06_probe_runner.py > docs/integration/execution/evidence/A06/runner_stdout.txt",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "docs/integration/execution/evidence/A06/runner_stdout.txt"},
    {"seq": 13, "purpose": "Write the A06 report.",
     "tool": "Write", "command": "Write tool: docs/integration/execution/A06_REPORT.md",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "docs/integration/execution/A06_REPORT.md"},
    {"seq": 14, "purpose": "Write the A06 closing-checks runner.",
     "tool": "Write", "command": "Write tool: integration-staging/tools/a06_final_checks.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/tools/a06_final_checks.py"},
    {"seq": 15, "purpose": "Write the A06 ledger close-patch builder.",
     "tool": "Write", "command": "Write tool: integration-staging/tools/a06_close_patch.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/tools/a06_close_patch.py"},
    {"seq": 16, "purpose": "Run the A06 closing checks (after the ledger is closed).",
     "tool": "Bash",
     "command": "examdata/.venv/Scripts/python.exe integration-staging/tools/a06_final_checks.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": None,
     "evidence": "docs/integration/execution/evidence/A06/final_checks.txt"},
]

TEST_RESULTS = [
    {"check": "Runtime probe: 31/31 scenarios PASS offline over real node (A06_PROBE: PASS)",
     "result": "pass", "exit_code": 0,
     "evidence": "docs/integration/execution/evidence/A06/runner_stdout.txt",
     "label": "synthetic_fixture",
     "note": "Configuration precedence, manifest admission, ok/env/echo, the failure classifications, stderr redaction, whitelist rejections, spaces in paths, timeout/overflow/cancellation cleanup evidence, queue-full and the read-only doctor."},
    {"check": "Staged suite passes offline: 232 tests (91 new A06 + 141 A03-A05), 0 failures",
     "result": "pass", "exit_code": 0,
     "evidence": "docs/integration/execution/evidence/A06/pytest_run_stdout.txt",
     "label": "synthetic_fixture",
     "note": "23 configuration + 27 manifest/doctor + 29 runner-classification + 12 runner-bounds, in the isolated harness with the module and network guards active."},
    {"check": "Every runner failure has a stable, distinct internal classification and error code",
     "result": "pass", "exit_code": 0,
     "evidence": "integration-staging/tests/test_runner_classification.py",
     "label": "synthetic_fixture",
     "note": "14 RunnerOutcome values; ERROR_CODES is a frozen table; OUTCOME_PRECEDENCE is deterministic; ok and business_failure are the only non-infrastructure outcomes."},
    {"check": "Timeout/overflow/cancellation terminate the process tree and record no orphan",
     "result": "pass", "exit_code": 0,
     "evidence": "integration-staging/tests/test_runner_classification.py",
     "label": "synthetic_fixture",
     "note": "cleanup evidence: terminated, method in (taskkill_tree, kill), waited, returncode set, readers not alive, pid_alive_after not True."},
    {"check": "Configuration precedence and manifest validation (unknown keys, bad values, invalid components not admitted)",
     "result": "pass", "exit_code": 0,
     "evidence": "integration-staging/tests/test_config_resolution.py",
     "label": "synthetic_fixture",
     "note": "explicit > environment > file > manifest defaults > default; legacy aliases warn; conflicting aliases raise; secrets reported set/unset only; ensure_directories refuses paths outside staging."},
]

FAILURES = [
    {"what": "First inline smoke run of NodeRunner failed: node exited 1 because the child environment was nearly empty.",
     "evidence": "command row seq 5 (exit_code 1)",
     "resolution": "Windows environment names are case-insensitive (the inherited key is 'Path', not 'PATH'); the allowlist lookup used a case-sensitive match. Fixed with a case-insensitive NodeRunner._set_env used by the constructor and child_environment. Two further defects were found and fixed in the same pass: relative component locations resolved against the wrong base (fixed by making the deployment root absolute in settings.resolve_config, manifest.parse_component, manifest.load_manifest_set and NodeRunner.__init__), and a reader-thread race could set the overflow flag while the process was exiting on its own (fixed by joining the reader threads before classification and only terminating when the process is still running)."},
    {"what": "First A06 staged-suite run exited 1: 3 tests failed (test_full_precedence_order, test_config_file_layer, test_problem_code_reported[not_relative_path_abs]).",
     "evidence": "command row seq 9 (exit_code 1); the failing transcript was replaced by the passing re-run",
     "resolution": "All three were test-side assumption errors, no product change: ConfigLayer values are 'manifest_default' and 'config_file' (not 'manifest'/'file'), and a parametrised manifest case needed its display id separated from the expected problem code. The runtime layer was not weakened."},
]

REMAINING_GAPS = [
    "The runner starts only the synthetic fake_cli fixture: no real Node gateway adapter exists yet (A10/A11) and there is no network or database access; network_mode stays 'offline'.",
    "The manifest declares one component; real component discovery is A07-A11.",
    "The runner concurrency bound is process-local, not a global limit across Uvicorn workers, so initial deployment stays at one worker until shared source limiting exists (plan 6.4).",
    "path_escapes_root is defensive: any '..' or drive/root prefix is already rejected as not_relative_path, so a relative declaration cannot reach the root-escape branch (documented by construction).",
    "Secret redaction requires the caller to pass secrets=; the runner cannot guess which value is a secret.",
    "Real-data behaviour and any promotion to verified stay Phase B behind the write-authorization gate.",
]

EVIDENCE_PATHS = [
    "docs/integration/execution/A06_REPORT.md",
    "docs/integration/execution/evidence/A06/final_checks.txt",
    "docs/integration/execution/evidence/A06/pytest_run_stdout.txt",
    "docs/integration/execution/evidence/A06/runner_stdout.txt",
    "docs/integration/execution/execution-ledger.json",
    "integration-staging/components/fake-node-cli/fake-cli.mjs",
    "integration-staging/components/manifest.json",
    "integration-staging/config/README.md",
    "integration-staging/config/staging-config.example.json",
    "integration-staging/config/staging.env.example",
    "integration-staging/runtime/ledger-patches/A06_close.json",
    "integration-staging/src/examdata_integration/runtime/__init__.py",
    "integration-staging/src/examdata_integration/runtime/classification.py",
    "integration-staging/src/examdata_integration/runtime/doctor.py",
    "integration-staging/src/examdata_integration/runtime/manifest.py",
    "integration-staging/src/examdata_integration/runtime/redact.py",
    "integration-staging/src/examdata_integration/runtime/runner.py",
    "integration-staging/src/examdata_integration/runtime/settings.py",
    "integration-staging/src/examdata_integration/testing/runtime_support.py",
    "integration-staging/tests/test_config_manifest.py",
    "integration-staging/tests/test_config_resolution.py",
    "integration-staging/tests/test_runner_classification.py",
    "integration-staging/tests/test_runner_limits.py",
    "integration-staging/tools/a06_close_patch.py",
    "integration-staging/tools/a06_final_checks.py",
    "integration-staging/tools/a06_probe_runner.py",
]

NEXT_ACTION = ("A07 - CIE and Edexcel read adapters over synthetic fixtures (plan section 11): map the A03 synthetic "
               "fixtures onto the frozen contracts through the provider protocol and the A06 runner, preserving native "
               "identity, question hierarchy, table structures, conflicts and provenance - offline, private fixtures only.")


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def rel(p: Path) -> str:
    return p.relative_to(WS).as_posix()


def node_version() -> str:
    try:
        proc = subprocess.run(["node", "--version"], capture_output=True, text=True, timeout=15)
        return (proc.stdout or proc.stderr or "").strip() or "unknown"
    except Exception:  # noqa: BLE001
        return "unavailable"


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
        "dependencies": ["A05"],
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
        "notes": (
            f"node runtime used by the probe: {node_version()} (C:/Program Files/nodejs/node). "
            "The four original gateway sources under examdata/src are point-in-time hashes: "
            "Kimi Code may edit the original tree concurrently, so their hashes record what was "
            "inspected, not a frozen dependency."),
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
