"""Build the R0104 private progress ledger.

A private progress record for the R01-R04 repair. This is NOT the live execution
ledger (docs/integration/execution/execution-ledger.json), which is byte-unchanged
and stays the only authoritative ledger.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone, timedelta

WS = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
RUN = os.path.dirname(os.path.abspath(__file__))
EVID = os.path.join(RUN, "evidence")
OUT = os.path.join(WS, "docs", "integration", "execution")

CST = timezone(timedelta(hours=8))

MANIFEST = os.path.join(EVID, "R0104_CHANGE_MANIFEST.json")
LEDGER = os.path.join(WS, "docs", "integration", "execution", "execution-ledger.json")
LAYOUT = os.path.join(
    WS, "docs", "integration", "execution", "evidence", "R0104", "r0104-repair-20261006",
    "R04_LAYOUT_VALIDATION.json",
)

LEDGER_FROZEN = "6d4449d3997b437fd3ea3a1fe7925fc78a7c0adbe0a5d3b793d6a8063101b4ba"


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def rel(path: str) -> str:
    return os.path.relpath(path, WS).replace("\\", "/")


def read(path: str) -> str:
    with open(path, encoding="utf-8", errors="replace") as fh:
        return fh.read()


def count_pytest(text: str) -> dict:
    m = re.search(r"(\d+) failed, (\d+) passed", text)
    if m:
        return {"failed": int(m.group(1)), "passed": int(m.group(2))}
    m = re.search(r"(\d+) passed", text)
    if m:
        return {"failed": 0, "passed": int(m.group(1))}
    return {"failed": None, "passed": None}


def main() -> int:
    manifest = json.load(open(MANIFEST, encoding="utf-8"))
    ledger = json.load(open(LEDGER, encoding="utf-8"))
    layout = json.load(open(LAYOUT, encoding="utf-8"))

    guards = read(os.path.join(EVID, "rerun_r0104_ledger_guards.txt"))
    m = re.search(r"(\d+)/(\d+) checks passed", guards)
    guards_pass, guards_total = (int(m.group(1)), int(m.group(2))) if m else (None, None)

    reg = read(os.path.join(EVID, "rerun_regression_rejections.txt"))
    reg_pass = reg.count("[PASS]")
    reg_fail = reg.count("[FAIL]")

    staged_post = count_pytest(read(os.path.join(EVID, "rerun_staged_suite.txt")))
    staged_pre = count_pytest(read(os.path.join(EVID, "staged_suite_run_pre_fix.txt")))

    probes = layout["probes"]
    imp = [p for p in probes if p["script"] == "r04_import_probe.py"]
    res = [p for p in probes if p["script"] == "r04_resource_probe.py"]

    now = datetime.now(CST).isoformat(timespec="seconds")
    ledger_sha = sha256_file(LEDGER)
    gates_open = sorted(g for g, v in ledger["gates"].items() if v.get("open"))

    data = {
        "ledger_version": "r0104-private-progress-ledger/1",
        "generated_by": rel(os.path.abspath(__file__)),
        "generated_at": now,
        "kind": "private_progress_ledger",
        "note": "Private progress record for the R01-R04 repair. This is NOT the live execution "
        "ledger and does not replace it. The live ledger is byte-unchanged and remains the only "
        "authoritative ledger.",
        "live_execution_ledger": {
            "path": rel(LEDGER),
            "sha256": ledger_sha,
            "expected_frozen_sha256": LEDGER_FROZEN,
            "byte_unchanged": ledger_sha == LEDGER_FROZEN,
            "gates_open": gates_open,
            "all_gates_closed": not gates_open,
            "written_by_this_repair": False,
        },
        "status": "private_repair_complete_pending_human_release",
        "not_claimed": ["merged_pass", "deployment", "full B00/B01 completion"],
        "changed_counts": {
            "edited_staged_files": manifest["counts"]["edited_staged_files"],
            "new_staged_files": manifest["counts"]["new_staged_files"],
            "collateral_tool_edits": manifest["counts"]["collateral_tool_edits"],
            "changed_files_total": manifest["counts"]["changed_files_total"],
            "diff_artifacts": manifest["counts"]["diff_artifacts"],
            "candidates": manifest["counts"]["candidates"],
        },
        "test_counts": {
            "r0104_ledger_guards": {
                "command": "./examdata/.venv/Scripts/python.exe "
                "integration-staging/runtime/r0104-repair-20261006/test_r0104_ledger_guards.py",
                "cwd": "C:/Users/weo/Desktop/api",
                "exit_code": 0,
                "checks_total": guards_total,
                "checks_passed": guards_pass,
                "checks_failed": (guards_total - guards_pass) if guards_total else None,
                "new_suite": True,
                "explanation": "New R01/R02/R03 guard suite written for this repair; all 36 checks "
                "are new, so there is no earlier count to compare against.",
            },
            "isolated_staged_suite": {
                "command": "bash integration-staging/tools/run_staged_tests.sh -q",
                "cwd": "C:/Users/weo/Desktop/api",
                "exit_code": 0,
                "post_fix": staged_post,
                "pre_fix": staged_pre,
                "collected_both_runs": 887,
                "explanation": "The collected test count is unchanged at 887 in both runs. Pre-fix "
                "the run was 886 passed / 1 failed (exit 1): "
                "tests/test_config_resolution.py::test_config_file_outside_staging_refused failed "
                "with a PermissionError message mismatch from runtime/paths.py. The fix introduced "
                "PathOutsideRootError and the test now asserts it, moving that one test from fail "
                "to pass: 886 + 1 = 887 passed, exit 0. The delta is explained entirely by that one "
                "test outcome; no test was added or removed.",
            },
            "preexisting_rejection_suite": {
                "command": "./examdata/.venv/Scripts/python.exe "
                "integration-staging/runtime/r0104-repair-20261006/regression/test_b_ledger_rejections.py",
                "cwd": "C:/Users/weo/Desktop/api",
                "exit_code": 1,
                "checks_total": reg_pass + reg_fail,
                "checks_passed": reg_pass,
                "checks_failed": reg_fail,
                "failing_checks": ["R15b"],
                "suite_modified": False,
                "sealed_reference": "docs/integration/execution/evidence/B00/"
                "b00b01-20261006T132400/b_ledger_rejections_run_f04.txt (18/18 passed pre-fix)",
                "explanation": "Historical control kept byte-identical. 17 of 18 checks pass. R15b "
                "fails by design: it expects guarded_action_gates_missing == "
                "['existing_service_cutover_authorized'], the pre-R03 packet-wide model. Under the "
                "corrected action-level model B02's primary action config_integration needs only "
                "original_paths_released (open), so missing == [] and the guarded action stays "
                "open=False. The corrected expectation is a positive control in the new guard suite.",
            },
            "r04_layout_probes": {
                "command": "./examdata/.venv/Scripts/python.exe "
                "integration-staging/runtime/r0104-repair-20261006/r04_validate_layout.py",
                "cwd": "C:/Users/weo/Desktop/api",
                "exit_code": 0,
                "verdict": layout["verdict"],
                "findings": len(layout["findings"]),
                "probes_total": len(probes),
                "probes_exit0": sum(1 for p in probes if p["exit_code"] == 0),
                "import_probe": {
                    "modules_walked": [p["counts"]["walked"] for p in imp],
                    "entry_points": [p["counts"]["entry_points"] for p in imp],
                    "import_errors": [p["counts"]["errors"] for p in imp],
                    "modules_outside_candidate": [p["counts"]["outside_candidate"] for p in imp],
                },
                "resource_probe": {
                    "entry_points_ok": [p["counts"]["entry_points_ok"] for p in res],
                    "schema_files": [p["counts"]["schema_files"] for p in res],
                    "schema_loaded_ok": [p["counts"]["schema_loaded_ok"] for p in res],
                    "synthetic_node_components_admitted": [
                        p["counts"]["node_components_admitted"] for p in res
                    ],
                    "checks": [p["counts"]["checks"] for p in res],
                    "checks_failed": [p["counts"]["checks_failed"] for p in res],
                },
                "explanation": "Two candidates x two probes = 4 probe runs, all exit 0. Both "
                "candidates produce identical counts, so the numbers are reported as one value per "
                "candidate; the lists above hold one entry per candidate. No PYTHONPATH and no "
                "staging-root override in any probe environment.",
            },
        },
        "artifacts": {
            "change_manifest": rel(MANIFEST),
            "change_manifest_sha256": sha256_file(MANIFEST),
            "merge_proposal": "docs/integration/execution/R0104_MERGE_PROPOSAL.json",
            "rollback_proposal": "docs/integration/execution/R0104_ROLLBACK_PROPOSAL.json",
            "review_report": "docs/integration/execution/R0104_REPAIR_REPORT.md",
            "layout_validation": rel(LAYOUT),
            "diffs": "integration-staging/runtime/r0104-repair-20261006/evidence/DIFFS/",
            "transcripts": [
                rel(os.path.join(EVID, n))
                for n in (
                    "rerun_r0104_ledger_guards.txt",
                    "rerun_regression_rejections.txt",
                    "rerun_staged_suite.txt",
                    "rerun_r04_build.txt",
                    "rerun_r04_validate.txt",
                    "staged_suite_run_pre_fix.txt",
                )
            ],
        },
        "frozen_evidence_written": False,
        "process_observations": [o["id"] for o in manifest.get("process_observations", [])],
        "not_run": manifest["not_run"],
        "remaining_blockers": [
            "original-project reconciliation awaits an explicit human release opening "
            "original_paths_released with an explicit scope",
            "real Node/source validation against the original tree stays not_run (not authorized)",
            "the pre-existing rejection suite keeps its stale R15b expectation until a human decides",
        ],
    }

    os.makedirs(OUT, exist_ok=True)
    jpath = os.path.join(OUT, "R0104_PROGRESS_LEDGER.json")
    with open(jpath, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    print("wrote", rel(jpath))

    t = data["test_counts"]
    md = [
        "# R0104 private progress ledger",
        "",
        f"Generated: {now}  ",
        "Kind: **private progress ledger** (not the live execution ledger).",
        "",
        "The live execution ledger "
        "`docs/integration/execution/execution-ledger.json` is byte-unchanged at "
        f"`{ledger_sha[:12]}…`, all {len(ledger['gates'])} gates `open: false`. "
        "This file is a private progress record and does not replace it.",
        "",
        "Status: `private_repair_complete_pending_human_release`. Not claimed: merged_pass, "
        "deployment, full B00/B01 completion.",
        "",
        "## Changed counts",
        "",
        "| count | value |",
        "| --- | --- |",
        f"| edited staged files | {data['changed_counts']['edited_staged_files']} |",
        f"| new staged files | {data['changed_counts']['new_staged_files']} |",
        f"| collateral staging tool edits | {data['changed_counts']['collateral_tool_edits']} |",
        f"| changed files total | {data['changed_counts']['changed_files_total']} |",
        f"| diff artifacts | {data['changed_counts']['diff_artifacts']} |",
        f"| R04 candidates | {data['changed_counts']['candidates']} |",
        "",
        "## Test counts and what changed",
        "",
        f"- **R01-R03 guards** — exit {t['r0104_ledger_guards']['exit_code']}, "
        f"{t['r0104_ledger_guards']['checks_passed']}/"
        f"{t['r0104_ledger_guards']['checks_total']} checks passed. "
        f"{t['r0104_ledger_guards']['explanation']}",
        f"- **Isolated staged suite** — post-fix exit "
        f"{t['isolated_staged_suite']['exit_code']}, "
        f"{t['isolated_staged_suite']['post_fix']['passed']} passed / "
        f"{t['isolated_staged_suite']['post_fix']['failed']} failed; pre-fix exit 1, "
        f"{t['isolated_staged_suite']['pre_fix']['passed']} passed / "
        f"{t['isolated_staged_suite']['pre_fix']['failed']} failed. "
        f"{t['isolated_staged_suite']['explanation']}",
        f"- **Pre-existing rejection suite** — exit "
        f"{t['preexisting_rejection_suite']['exit_code']}, "
        f"{t['preexisting_rejection_suite']['checks_passed']}/"
        f"{t['preexisting_rejection_suite']['checks_total']} passed, failing: "
        f"{', '.join(t['preexisting_rejection_suite']['failing_checks'])}. "
        f"{t['preexisting_rejection_suite']['explanation']}",
        f"- **R04 layout probes** — exit {t['r04_layout_probes']['exit_code']}, verdict "
        f"`{t['r04_layout_probes']['verdict']}`, findings {t['r04_layout_probes']['findings']}, "
        f"{t['r04_layout_probes']['probes_exit0']}/{t['r04_layout_probes']['probes_total']} "
        f"probes exit 0. {t['r04_layout_probes']['explanation']}",
        "",
        "## Artifacts",
        "",
    ]
    for k, v in data["artifacts"].items():
        if isinstance(v, list):
            md.append(f"- {k}: " + ", ".join(f"`{x}`" for x in v))
        else:
            md.append(f"- {k}: `{v}`")
    md += [
        "",
        "## Remaining blockers",
        "",
    ]
    md += [f"- {b}" for b in data["remaining_blockers"]]
    md += [
        "",
        "## Not run",
        "",
    ]
    md += [f"- {b}" for b in data["not_run"]]
    md.append("")

    mpath = os.path.join(OUT, "R0104_PROGRESS_LEDGER.md")
    with open(mpath, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(md))
    print("wrote", rel(mpath))
    print(json.dumps({"guards": [guards_pass, guards_total], "reg": [reg_pass, reg_fail],
                      "staged_post": staged_post, "staged_pre": staged_pre}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
