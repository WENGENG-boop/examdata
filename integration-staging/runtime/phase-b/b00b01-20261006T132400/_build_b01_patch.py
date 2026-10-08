import json, pathlib, hashlib

ROOT = pathlib.Path('C:/Users/weo/Desktop/api')
RUN = ROOT / 'integration-staging/runtime/phase-b/b00b01-20261006T132400'
B01EV = ROOT / 'docs/integration/execution/evidence/B01/b00b01-20261006T132400'
BS = chr(92)
CWD = 'C:' + BS + 'Users' + BS + 'weo' + BS + 'Desktop' + BS + 'api'


def sha(rel):
    return hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()


patch = {
    "dependencies": ["B00"],
    "allowed_write_roots": [
        "C:/Users/weo/Desktop/api/integration-staging",
        "C:/Users/weo/Desktop/api/docs/integration/execution",
    ],
    "input_hashes": {
        "docs/integration/execution/A14_MERGE_MAP.json": sha('docs/integration/execution/A14_MERGE_MAP.json'),
        "docs/integration/execution/evidence/B00/b00b01-20261006T132400/a_sealed_A14_MERGE_MAP.json":
            sha('docs/integration/execution/evidence/B00/b00b01-20261006T132400/a_sealed_A14_MERGE_MAP.json'),
        "examdata/src/examdata/cli.py": sha('examdata/src/examdata/cli.py'),
        "examdata/pyproject.toml": sha('examdata/pyproject.toml'),
        "integration-staging/runtime/phase-b/b00b01-20261006T132400/b01_build_merge_map.py":
            sha('integration-staging/runtime/phase-b/b00b01-20261006T132400/b01_build_merge_map.py'),
        "integration-staging/runtime/phase-b/b00b01-20261006T132400/b01_build_private_copy.py":
            sha('integration-staging/runtime/phase-b/b00b01-20261006T132400/b01_build_private_copy.py'),
        "integration-staging/runtime/phase-b/b00b01-20261006T132400/b01_validate_layout.py":
            sha('integration-staging/runtime/phase-b/b00b01-20261006T132400/b01_validate_layout.py'),
    },
    "changed_files": [
        "integration-staging/runtime/phase-b/b00b01-20261006T132400/b01_build_merge_map.py",
        "integration-staging/runtime/phase-b/b00b01-20261006T132400/b01_build_private_copy.py",
        "integration-staging/runtime/phase-b/b00b01-20261006T132400/b01_validate_layout.py",
        "integration-staging/runtime/phase-b/b00b01-20261006T132400/b01_import_probe.py",
        "integration-staging/runtime/phase-b/b00b01-20261006T132400/private/**",
        "docs/integration/execution/evidence/B01/b00b01-20261006T132400/B01_MERGE_MAP.json",
        "docs/integration/execution/evidence/B01/b00b01-20261006T132400/B01_LAYOUT_VALIDATION.json",
        "docs/integration/execution/evidence/B01/b00b01-20261006T132400/b01_build_merge_map_run.txt",
        "docs/integration/execution/evidence/B01/b00b01-20261006T132400/b01_layout_validation_run.txt",
        "docs/integration/execution/evidence/B01/b00b01-20261006T132400/b01_staged_pytest_rerun.txt",
        "docs/integration/execution/B01_LAYOUT_DECISION.md",
        "docs/integration/execution/B01_REPORT.md",
    ],
    "commands": [
        {"seq": 1,
         "purpose": "build B01_MERGE_MAP.json from the frozen A14 map with F01 corrected",
         "tool": "python",
         "command": "examdata/.venv/Scripts/python.exe integration-staging/runtime/phase-b/b00b01-20261006T132400/b01_build_merge_map.py",
         "cwd": CWD, "exit_code": 0,
         "evidence": "docs/integration/execution/evidence/B01/b00b01-20261006T132400/b01_build_merge_map_run.txt"},
        {"seq": 2,
         "purpose": "build the private candidate at the proposed final layout",
         "tool": "python",
         "command": "examdata/.venv/Scripts/python.exe integration-staging/runtime/phase-b/b00b01-20261006T132400/b01_build_private_copy.py",
         "cwd": CWD, "exit_code": 0,
         "evidence": "integration-staging/runtime/phase-b/b00b01-20261006T132400/private/B01_PRIVATE_COPY_MANIFEST.json"},
        {"seq": 3,
         "purpose": "validate import/resource layout of the private candidate (F03)",
         "tool": "python",
         "command": "examdata/.venv/Scripts/python.exe integration-staging/runtime/phase-b/b00b01-20261006T132400/b01_validate_layout.py",
         "cwd": CWD, "exit_code": 0,
         "evidence": "docs/integration/execution/evidence/B01/b00b01-20261006T132400/B01_LAYOUT_VALIDATION.json"},
        {"seq": 4,
         "purpose": "register B01 private preparation in the ledger",
         "tool": "python",
         "command": "examdata/.venv/Scripts/python.exe integration-staging/tools/b_ledger_update.py --task B01 --status partial --phase-b-mode PHASE_B_PENDING_RELEASE --patch-file integration-staging/runtime/phase-b/b00b01-20261006T132400/b01_ledger_patch.json",
         "cwd": CWD, "exit_code": 0,
         "evidence": "docs/integration/execution/execution-ledger.json (history)"},
        {"seq": 5,
         "purpose": "re-run the isolated staged suite in the private harness (mandatory check)",
         "tool": "python",
         "command": "cd integration-staging && PYTHONDONTWRITEBYTECODE=1 PYTHONIOENCODING=utf-8 ../examdata/.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider",
         "cwd": "C:" + BS + "Users" + BS + "weo" + BS + "Desktop" + BS + "api" + BS + "integration-staging",
         "exit_code": 0,
         "evidence": "docs/integration/execution/evidence/B01/b00b01-20261006T132400/b01_staged_pytest_rerun.txt"},
    ],
    "exit_codes": [0, 0, 0, 0, 0],
    "test_results": [
        {"check": "B01_MERGE_MAP invariants: A14 byte-unchanged, 247 entries all dispositioned, 92 not_merged, CLI target corrected, no entry promoted",
         "result": "pass", "exit_code": 0,
         "evidence": "docs/integration/execution/evidence/B01/b00b01-20261006T132400/b01_build_merge_map_run.txt",
         "label": "static_inspection"},
        {"check": "F01 CLI target: examdata/cli.py does not exist; real entry examdata/src/examdata/cli.py = examdata.cli:app",
         "result": "pass", "exit_code": 0,
         "evidence": "docs/integration/execution/evidence/B01/b00b01-20261006T132400/B01_MERGE_MAP.json",
         "label": "original_read_only"},
        {"check": "F03 layout: 0 modules outside private tree; 49 import; 28/28 schemas load; 3 fail on the test-guard dependency (finding F03-GUARD-DEP)",
         "result": "pass", "exit_code": 0,
         "evidence": "docs/integration/execution/evidence/B01/b00b01-20261006T132400/B01_LAYOUT_VALIDATION.json",
         "label": "private_candidate"},
        {"check": "isolated staged suite re-run in the private harness: 887 passed, 0 failed, 0 skipped (2 warnings: httpx2 deprecation, unknown cache_dir when -p no:cacheprovider)",
         "result": "pass", "exit_code": 0,
         "evidence": "docs/integration/execution/evidence/B01/b00b01-20261006T132400/b01_staged_pytest_rerun.txt",
         "label": "private_candidate"},
    ],
    "evidence_paths": [
        "docs/integration/execution/evidence/B01/b00b01-20261006T132400/B01_MERGE_MAP.json",
        "docs/integration/execution/evidence/B01/b00b01-20261006T132400/B01_LAYOUT_VALIDATION.json",
        "docs/integration/execution/evidence/B01/b00b01-20261006T132400/b01_build_merge_map_run.txt",
        "docs/integration/execution/evidence/B01/b00b01-20261006T132400/b01_layout_validation_run.txt",
        "docs/integration/execution/evidence/B01/b00b01-20261006T132400/b01_staged_pytest_rerun.txt",
        "docs/integration/execution/B01_LAYOUT_DECISION.md",
        "docs/integration/execution/B01_REPORT.md",
    ],
    "remaining_gaps": [
        "gate original_paths_released is closed: no human release credential, so the three-way (old base -> released original -> staged proposal) reconciliation is NOT done",
        "B01 map entries are all carried_pending_release; no entry reconciled or promoted",
        "F03-GUARD-DEP fix not yet applied to a candidate: runtime/{manifest,runner,settings}.py import the test-only ..testing.guards, so examdata.integration.runtime/legacy fail at the target layout",
        "real Node components not released: component discovery stays not_run",
        "wheel / clean-environment install is B09, not claimed here",
    ],
    "next_action": ("B01 release-independent work done (F01 fixed in B01_MERGE_MAP.json, F03 layout validated). "
                    "Resume the released-tree reconciliation only on an explicit human release with the four elements; "
                    "otherwise apply the F03-GUARD-DEP fix in a fresh private candidate and re-validate. B01 stays partial."),
}

(RUN / 'b01_ledger_patch.json').write_text(json.dumps(patch, ensure_ascii=False, indent=2) + "\n", encoding='utf-8')
print("wrote b01_ledger_patch.json")
print(json.dumps({k: (len(v) if isinstance(v, list) else v) for k, v in patch.items()}, indent=1)[:900])
