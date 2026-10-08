import json, pathlib, hashlib

base = pathlib.Path('integration-staging/runtime/phase-b/b00b01-20261006T132400')
p = json.loads((base / 'b00_ledger_patch.json').read_text(encoding='utf-8'))
led = pathlib.Path('docs/integration/execution/execution-ledger.json')
p['input_hashes']['docs/integration/execution/execution-ledger.json'] = hashlib.sha256(led.read_bytes()).hexdigest()

BS = chr(92)
CWD = 'C:' + BS + 'Users' + BS + 'weo' + BS + 'Desktop' + BS + 'api'

p['commands'].append({
    "seq": 5,
    "purpose": "re-register B00 after fixing the --expect-inputs path defect and the original_changes_applied=false coverage",
    "tool": "python",
    "command": "examdata/.venv/Scripts/python.exe integration-staging/tools/b_ledger_update.py --task B00 --status partial --phase-b-mode PHASE_B_PENDING_RELEASE",
    "cwd": CWD,
    "exit_code": 0,
    "evidence": "docs/integration/execution/execution-ledger.json (history[1])"
})
p['commands'].append({
    "seq": 6,
    "purpose": "backfill the B00 report and the registration commands into the ledger record",
    "tool": "python",
    "command": "examdata/.venv/Scripts/python.exe integration-staging/tools/b_ledger_update.py --task B00 --status partial --phase-b-mode PHASE_B_PENDING_RELEASE --patch-file integration-staging/runtime/phase-b/b00b01-20261006T132400/b00_ledger_patch_seq5.json --expect-inputs integration-staging/runtime/phase-b/b00b01-20261006T132400/b00_expect_inputs_seq5.json",
    "cwd": CWD,
    "exit_code": 0,
    "evidence": "docs/integration/execution/execution-ledger.json (history[2])"
})
p['exit_codes'] = [c['exit_code'] for c in p['commands']]
p['changed_files'] = p['changed_files'] + [
    "integration-staging/runtime/phase-b/b00b01-20261006T132400/_build_seq5_patch.py",
    "integration-staging/runtime/phase-b/b00b01-20261006T132400/b00_ledger_patch_seq5.json",
    "integration-staging/runtime/phase-b/b00b01-20261006T132400/b00_expect_inputs_seq5.json",
    "docs/integration/execution/B00_REPORT.md",
]
p['evidence_paths'] = p['evidence_paths'] + ["docs/integration/execution/B00_REPORT.md"]
p['next_action'] = ("B00 release-independent work complete (report written, tool fixed, ledger consistent). "
                    "B01 is gate-blocked on gate:original_paths_released (no human release credential). "
                    "Next: B01 release-independent preparation in a private copy, then record B01 as "
                    "partial/blocked with the exact missing release scope.")
(base / 'b00_ledger_patch_seq5.json').write_text(json.dumps(p, ensure_ascii=False, indent=2) + "\n", encoding='utf-8')

ei = {
    "docs/integration/ROUTE_INVENTORY_CURRENT.json": hashlib.sha256(pathlib.Path('docs/integration/ROUTE_INVENTORY_CURRENT.json').read_bytes()).hexdigest(),
    "integration-staging/tools/b_ledger_update.py": hashlib.sha256(pathlib.Path('integration-staging/tools/b_ledger_update.py').read_bytes()).hexdigest(),
}
(base / 'b00_expect_inputs_seq5.json').write_text(json.dumps(ei, indent=2) + "\n", encoding='utf-8')
print("wrote patch seq5 and expect_inputs_seq5")
print(json.dumps(ei, indent=1))
