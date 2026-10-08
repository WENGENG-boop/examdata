"""Build the B01 ledger patch recording the suggested-outputs build (seq 6)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
LEDGER = ROOT / "docs/integration/execution/execution-ledger.json"
RUN = Path(__file__).resolve().parent
EV = "docs/integration/execution/evidence/B01/b00b01-20261006T132400"


def sha(rel: str) -> str:
    return hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()


b01 = {t["task_id"]: t for t in
       json.loads(LEDGER.read_text(encoding="utf-8"))["tasks"]}["B01"]

gen = "integration-staging/runtime/phase-b/b00b01-20261006T132400/b01_build_outputs.py"
new_outputs = [
    "docs/integration/execution/B01_MERGE_MAP.md",
    "docs/integration/execution/B01_RECONCILIATION_DIFF.md",
    "docs/integration/execution/B01_TEST_REPORT.md",
    "docs/integration/execution/B01_ROLLBACK_PLAN.json",
]

commands = list(b01.get("commands") or [])
commands.append({
    "seq": 6,
    "purpose": "B01 suggested outputs: B01_MERGE_MAP.md, "
               "B01_RECONCILIATION_DIFF.md, B01_TEST_REPORT.md, "
               "B01_ROLLBACK_PLAN.json (derived from the frozen B01 map)",
    "tool": "python",
    "command": "examdata/.venv/Scripts/python.exe "
               "integration-staging/runtime/phase-b/b00b01-20261006T132400/"
               "b01_build_outputs.py",
    "cwd": "C:\\Users\\weo\\Desktop\\api",
    "exit_code": 0,
    "evidence": f"{EV}/b01_build_outputs_run.txt",
})

changed = list(b01.get("changed_files") or [])
for p in [gen, *new_outputs]:
    if p not in changed:
        changed.append(p)

test_results = list(b01.get("test_results") or [])
test_results.append({
    "check": "B01 suggested outputs generated from B01_MERGE_MAP.json: "
             "B01_MERGE_MAP.md (247 entries + 92 not_merged + 9 active_owner + 6 "
             "planned edits), B01_RECONCILIATION_DIFF.md, B01_TEST_REPORT.md, "
             "B01_ROLLBACK_PLAN.json (247 + 6 reversible actions, F01 semantics)",
    "result": "pass",
    "exit_code": 0,
    "evidence": f"{EV}/b01_build_outputs_run.txt",
    "label": "static_inspection",
})

evidence_paths = sorted(set(b01.get("evidence_paths") or []) |
                        {f"{EV}/b01_build_outputs_run.txt", *new_outputs})

input_hashes = dict(b01.get("input_hashes") or {})
input_hashes[gen] = sha(gen)

patch = {
    "commands": commands,
    "exit_codes": [c["exit_code"] for c in commands],
    "changed_files": changed,
    "test_results": test_results,
    "evidence_paths": evidence_paths,
    "input_hashes": input_hashes,
    "next_action": (
        "B01 release-independent work done (F01 fixed in B01_MERGE_MAP.json, F03 "
        "layout validated, all suggested outputs written). Resume the released-tree "
        "three-way reconciliation only on an explicit human release with the four "
        "elements; otherwise apply the F03-GUARD-DEP fix in a fresh private "
        "candidate and re-validate. B01 stays partial; no entry merged."
    ),
}

out = RUN / "b01_ledger_patch_outputs.json"
out.write_text(json.dumps(patch, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({
    "patch": str(out),
    "command_seqs": [c["seq"] for c in commands],
    "exit_codes": patch["exit_codes"],
    "changed_files_added": [p for p in [gen, *new_outputs]],
    "gen_sha256": input_hashes[gen],
}, indent=2))
