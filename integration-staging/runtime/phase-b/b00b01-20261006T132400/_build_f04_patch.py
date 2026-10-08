"""Build the B00 ledger patch recording the F04 work.

F04 adds machine-checked dependencies and per-packet gate requirements to
b_ledger_update.py, with rejection tests R14/R15 and positive control R15b.
This patch appends the two new command transcripts (seq 7, 8), the matching
exit codes, a test_result row, refreshes the recorded tool hash, and sets the
next action. It does not change B00's status (still `partial`).
"""
from __future__ import annotations

import json
from pathlib import Path

API = Path(__file__).resolve().parents[4]
LEDGER = API / "docs/integration/execution/execution-ledger.json"
RUN = Path(__file__).resolve().parent

led = json.loads(LEDGER.read_text(encoding="utf-8"))
b00 = {t["task_id"]: t for t in led["tasks"]}["B00"]

EVID = "docs/integration/execution/evidence/B00/b00b01-20261006T132400"
commands = list(b00.get("commands") or [])
commands.append({
    "seq": 7,
    "purpose": "F04 rejection suite R1-R15b: dependency completeness (R14) and "
               "per-packet gate requirement (R15) refuse a staged_pass; "
               "private-preparation-only pass accepted (R15b)",
    "tool": "python",
    "command": "examdata/.venv/Scripts/python.exe "
               "integration-staging/runtime/phase-b/b00b01-20261006T132400/"
               "test_b_ledger_rejections.py",
    "cwd": "C:\\Users\\weo\\Desktop\\api",
    "exit_code": 0,
    "evidence": f"{EVID}/b_ledger_rejections_run_f04.txt",
})
commands.append({
    "seq": 8,
    "purpose": "F04 --validate-only emits packet_checks (dependencies + "
               "per-packet required/missing gates) for every B packet",
    "tool": "python",
    "command": "examdata/.venv/Scripts/python.exe "
               "integration-staging/tools/b_ledger_update.py --validate-only",
    "cwd": "C:\\Users\\weo\\Desktop\\api",
    "exit_code": 0,
    "evidence": f"{EVID}/b_ledger_validate_packet_checks.txt",
})

test_results = list(b00.get("test_results") or [])
test_results.append({
    "check": "Phase B ledger tool F04: staged_pass refused while a dependency is "
             "incomplete (R14) or a packet-required gate is closed without "
             "--private-preparation-only (R15); a private-preparation-only pass "
             "is accepted and records the guarded gate as still missing (R15b)",
    "result": "pass",
    "exit_code": 0,
    "evidence": f"{EVID}/b_ledger_rejections_run_f04.txt",
    "label": "synthetic_fixture",
})

evidence_paths = sorted(set(b00.get("evidence_paths") or []) | {
    f"{EVID}/b_ledger_rejections_run_f04.txt",
    f"{EVID}/b_ledger_validate_packet_checks.txt",
})

patch = {
    "commands": commands,
    "exit_codes": [c["exit_code"] for c in commands],
    "test_results": test_results,
    "evidence_paths": evidence_paths,
    "input_hashes": {
        "docs/integration/ROUTE_INVENTORY_CURRENT.json":
            "946d3e90cbccd54dc9ac9005f36f8f940b6b7d2fe1a5ae515b119d3c00e55baf",
        "docs/integration/execution/execution-ledger.json":
            "88e2191263872122e3b504059abbac5df662ba67c72a28d297e8110c2d2a6395",
        "integration-staging/tools/b_ledger_update.py":
            "ac9b01cbfc2733496f5041aa4cd0ace879a0ac8e40aae97c3c9a951ee1dd62b8",
    },
    "next_action": (
        "B00 release-independent work complete (report written, tool F04 "
        "hardened, ledger consistent). B01 is gate-blocked on "
        "gate:original_paths_released (no human release credential). B01 "
        "release-independent preparation recorded as partial; B02-B10 not "
        "started. Next: await the human four-part release of the original "
        "paths before any released-tree reconciliation (Phase B)."
    ),
}

out = RUN / "b00_ledger_patch_f04.json"
out.write_text(json.dumps(patch, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({
    "patch": str(out),
    "command_seqs": [c["seq"] for c in commands],
    "exit_codes": patch["exit_codes"],
    "test_result_count": len(test_results),
    "evidence_path_count": len(evidence_paths),
}, indent=2))
