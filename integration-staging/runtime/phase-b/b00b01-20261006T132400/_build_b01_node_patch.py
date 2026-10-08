"""Build the B01 ledger patch recording the Node-discovery validation (seq 7)."""
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

node_script = "integration-staging/runtime/phase-b/b00b01-20261006T132400/b01_validate_node_discovery.py"
gen = "integration-staging/runtime/phase-b/b00b01-20261006T132400/b01_build_outputs.py"
node_evidence = f"{EV}/B01_NODE_DISCOVERY.json"

commands = list(b01.get("commands") or [])
commands.append({
    "seq": 7,
    "purpose": "B01 Node component discovery validation (staging layout) and "
               "private target-layout import probe (F03-GUARD-DEP); 5/5 checks",
    "tool": "python",
    "command": "examdata/.venv/Scripts/python.exe "
               "integration-staging/runtime/phase-b/b00b01-20261006T132400/"
               "b01_validate_node_discovery.py",
    "cwd": "C:\\Users\\weo\\Desktop\\api",
    "exit_code": 0,
    "evidence": f"{EV}/b01_node_discovery_run.txt",
})

changed = list(b01.get("changed_files") or [])
for p in [node_script, node_evidence]:
    if p not in changed:
        changed.append(p)

test_results = list(b01.get("test_results") or [])
test_results.append({
    "check": "Node component discovery: exactly one synthetic component admitted "
             "(fake_cli, labelled synthetic), entry point inside the deployment "
             "root, escaping code_location refused; real components not_run",
    "result": "pass",
    "exit_code": 0,
    "evidence": f"{EV}/b01_node_discovery_run.txt",
    "label": "private_candidate",
})

evidence_paths = sorted(set(b01.get("evidence_paths") or []) |
                        {f"{EV}/b01_node_discovery_run.txt", node_evidence})

input_hashes = dict(b01.get("input_hashes") or {})
input_hashes[node_script] = sha(node_script)
input_hashes[gen] = sha(gen)

patch = {
    "commands": commands,
    "exit_codes": [c["exit_code"] for c in commands],
    "changed_files": changed,
    "test_results": test_results,
    "evidence_paths": evidence_paths,
    "input_hashes": input_hashes,
    "next_action": (
        "B01 release-independent work done (F01 fixed, F03 layout validated, Node "
        "discovery validated, all suggested outputs written). Resume the "
        "released-tree three-way reconciliation only on an explicit human release "
        "with the four elements; otherwise apply the F03-GUARD-DEP fix in a fresh "
        "private candidate and re-validate. B01 stays partial; no entry merged."
    ),
}

out = RUN / "b01_ledger_patch_node.json"
out.write_text(json.dumps(patch, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({
    "patch": str(out),
    "command_seqs": [c["seq"] for c in commands],
    "exit_codes": patch["exit_codes"],
    "node_script_sha256": input_hashes[node_script],
}, indent=2))
