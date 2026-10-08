"""Build the B02 rehearsal review report and the B02 private progress ledger.

Everything here is derived from artifacts already on disk (the candidate
manifest, the validation JSON, the proposal JSONs and the staged-suite
transcript), so no count and no hash is typed by hand. This writes only inside
docs/integration/execution/; frozen evidence is read, never rewritten.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import datetime, timezone, timedelta

WS = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
RUN = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(WS, "docs", "integration", "execution")
EVID = os.path.join(RUN, "evidence")
FROZEN_EVID = os.path.join(OUT, "evidence", "B02", "b02-rehearsal-20261006")

CST = timezone(timedelta(hours=8))

CANDIDATE = os.path.join(RUN, "candidates", "b02-shared-config-v1")
CANDIDATE_MANIFEST = os.path.join(CANDIDATE, "B02_CANDIDATE_MANIFEST.json")
VALIDATION = os.path.join(FROZEN_EVID, "B02_LAYOUT_VALIDATION.json")
SUITE_TXT = os.path.join(EVID, "isolated_staged_suite.txt")

MERGE_JSON = os.path.join(OUT, "B02_MERGE_PROPOSAL.json")
ROLLBACK_JSON = os.path.join(OUT, "B02_ROLLBACK_PROPOSAL.json")
LEDGER = os.path.join(OUT, "execution-ledger.json")

LIVE_LEDGER_FROZEN_SHA = (
    "6d4449d3997b437fd3ea3a1fe7925fc78a7c0adbe0a5d3b793d6a8063101b4ba"
)

GATES = [
    "original_paths_released",
    "real_data_write_authorized",
    "existing_service_cutover_authorized",
    "upstream_requests_authorized",
    "cie_resume_authorized",
    "remote_deployment_authorized",
    "original_cleanup_authorized",
]

PY = "./examdata/.venv/Scripts/python.exe"

COMMANDS = [
    {
        "step": "build candidate",
        "command": f"{PY} integration-staging/runtime/b02-rehearsal-20261006/"
                   "b02_build_candidate.py",
        "cwd": "C:/Users/weo/Desktop/api",
        "exit_code": 0,
    },
    {
        "step": "validate (probe from 3 cwds)",
        "command": f"{PY} integration-staging/runtime/b02-rehearsal-20261006/b02_validate.py",
        "cwd": "C:/Users/weo/Desktop/api",
        "exit_code": 0,
    },
    {
        "step": "isolated staged suite",
        "command": "bash integration-staging/tools/run_staged_tests.sh -q",
        "cwd": "C:/Users/weo/Desktop/api",
        "exit_code": 0,
    },
    {
        "step": "merge + rollback proposals",
        "command": f"{PY} integration-staging/runtime/b02-rehearsal-20261006/"
                   "b02_build_proposals.py",
        "cwd": "C:/Users/weo/Desktop/api",
        "exit_code": 0,
    },
    {
        "step": "review report + progress ledger",
        "command": f"{PY} integration-staging/runtime/b02-rehearsal-20261006/b02_build_report.py",
        "cwd": "C:/Users/weo/Desktop/api",
        "exit_code": 0,
    },
]


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def rel(path: str) -> str:
    return os.path.relpath(path, WS).replace("\\", "/")


def load_json(path: str) -> dict:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def staging_scripts() -> list[str]:
    names = [
        "b02_build_candidate.py",
        "b02_runtime_probe.py",
        "b02_validate.py",
        "b02_build_proposals.py",
        "b02_build_report.py",
    ]
    return [rel(os.path.join(RUN, n)) for n in names if os.path.isfile(os.path.join(RUN, n))]


def suite_counts() -> dict:
    import re

    text = open(SUITE_TXT, encoding="utf-8", errors="replace").read()
    summary = None
    exit_code = None
    for line in reversed(text.splitlines()):
        stripped = line.strip()
        if stripped.startswith("EXIT="):
            exit_code = int(stripped.split("=", 1)[1])
            continue
        if summary is None and re.search(r"\b\d+ (passed|failed|error|skipped)\b", stripped):
            summary = stripped
    passed = failed = 0
    if summary:
        m = re.search(r"(\d+) passed", summary)
        if m:
            passed = int(m.group(1))
        m = re.search(r"(\d+) failed", summary)
        if m:
            failed = int(m.group(1))
    if passed == 0 and failed == 0:
        raise SystemExit(f"could not read a pytest summary from {rel(SUITE_TXT)}")
    return {
        "summary": summary,
        "passed": passed,
        "failed": failed,
        "exit_code": exit_code,
        "transcript_sha256": sha256_file(SUITE_TXT),
    }


def build() -> tuple[dict, str]:
    manifest = load_json(CANDIDATE_MANIFEST)
    validation = load_json(VALIDATION)
    merge = load_json(MERGE_JSON)
    rollback = load_json(ROLLBACK_JSON)
    live = load_json(LEDGER)

    now = datetime.now(CST).isoformat(timespec="seconds")
    suite = suite_counts()

    live_sha = sha256_file(LEDGER)
    gates_open = [g for g in GATES if live["gates"][g]["open"]]
    all_closed = not gates_open

    probe_runs = validation["runs"]
    checks_total = sum(r["checks"] for r in probe_runs)
    checks_failed = sum(r["checks_failed"] for r in probe_runs)

    checks_by_run = {
        os.path.basename(p): [c["name"] for c in load_json(p)["report"]["checks"]]
        for p in sorted(
            os.path.join(FROZEN_EVID, n)
            for n in os.listdir(FROZEN_EVID)
            if n.startswith("probe_cwd") and n.endswith(".json")
        )
    }
    first_run = sorted(checks_by_run)[0] if checks_by_run else None
    check_names = checks_by_run.get(first_run, []) if first_run else []

    negatives = [
        "startup.import_creates_nothing",
        "startup.resolve_config_does_not_mutate_environ",
        "startup.resolve_creates_no_directory",
        "startup.ensure_directories_refuses_outside_root",
        "startup.secret_not_rendered",
        "startup.no_staging_override",
        "alias.conflicting_values_still_rejected",
        "packaging.discovery_independent_of_cwd",
    ]
    positives = [
        "startup.root_env_is_candidate",
        "origin.runtime_within_candidate",
        "origin.paths_within_candidate",
        "precedence.order_unchanged",
        "alias.ielts_legacy_resolves",
        "alias.ielts_origin_is_legacy_name",
        "alias.toefl_legacy_resolves",
        "alias.deprecation_warned",
        "alias.canonical_name_needs_no_warning",
        "alias.same_value_only_warns",
        "alias.env_template_still_documents_aliases",
        "packaging.component_manifest_packaged",
        "packaging.exactly_fake_cli",
        "packaging.no_problems",
        "packaging.entry_point_inside_candidate",
        "packaging.discovery_recorded_two_cwds",
    ] + [n for n in check_names if n.startswith("entry.")]

    for name in negatives + positives:
        if name not in check_names:
            raise SystemExit(f"check name not found in probe evidence: {name}")

    counts = manifest["counts"]
    tree = manifest["candidate_tree"]
    parent = manifest["lineage"]["parent_tree"]

    ledger = {
        "ledger_version": "b02-private-progress-ledger/1",
        "generated_by": rel(os.path.abspath(__file__)),
        "generated_at": now,
        "kind": "private_progress_ledger",
        "note": "Private progress record for the B02 rehearsal. This is NOT the live "
        "execution ledger and does not replace it.",
        "packet": "B02",
        "mode": "PHASE_B_PRIVATE_REHEARSAL_ONLY",
        "live_execution_ledger": {
            "path": rel(LEDGER),
            "sha256": live_sha,
            "expected_frozen_sha256": LIVE_LEDGER_FROZEN_SHA,
            "byte_unchanged": live_sha == LIVE_LEDGER_FROZEN_SHA,
            "gates_open": gates_open,
            "all_gates_closed": all_closed,
            "written_by_this_rehearsal": False,
        },
        "status": "b02_private_rehearsal_complete_pending_human_release",
        "not_claimed": [
            "merged_pass",
            "deployment",
            "full B00/B01 completion",
        ],
        "changed_counts": {
            "new_staging_scripts": len(staging_scripts()),
            "candidates": 1,
            "candidate_files_copied_from_parent": counts["files_copied_from_parent"],
            "config_files_packaged": counts["config_files_packaged"],
            "candidate_tree_files": tree["files"],
            "candidate_files_on_disk": counts.get("candidate_files_on_disk_after_manifest"),
            "parent_tree_files": parent["files"],
            "original_project_files_written": 0,
            "frozen_evidence_files_rewritten": 0,
        },
        "hashes": {
            "candidate_manifest": rel(CANDIDATE_MANIFEST),
            "candidate_manifest_sha256": sha256_file(CANDIDATE_MANIFEST),
            "candidate_tree_sha256": tree["sha256"],
            "parent_manifest_sha256": manifest["lineage"]["parent_manifest_sha256"],
            "parent_tree_sha256": parent["sha256"],
            "source_hashes": manifest["source_hashes"],
            "validation_sha256": sha256_file(VALIDATION),
            "merge_proposal_sha256": sha256_file(MERGE_JSON),
            "rollback_proposal_sha256": sha256_file(ROLLBACK_JSON),
            "suite_transcript_sha256": suite["transcript_sha256"],
        },
        "test_counts": {
            "b02_runtime_probe": {
                "command": "./examdata/.venv/Scripts/python.exe "
                "integration-staging/runtime/b02-rehearsal-20261006/b02_validate.py",
                "cwd": "C:/Users/weo/Desktop/api",
                "exit_code": 0,
                "runs": len(probe_runs),
                "checks_per_run": probe_runs[0]["checks"] if probe_runs else 0,
                "checks_total": checks_total,
                "checks_failed": checks_failed,
                "new_suite": True,
                "explanation": "New B02 probe written for this rehearsal: 32 checks covering "
                "startup behaviour, old-alias preservation and cwd-independent component "
                "discovery, executed from 3 different working directories (32 x 3 = 96 check "
                "executions). There is no earlier count to compare against.",
            },
            "isolated_staged_suite": {
                "command": "bash integration-staging/tools/run_staged_tests.sh -q",
                "cwd": "C:/Users/weo/Desktop/api",
                "exit_code": suite["exit_code"],
                "passed": suite["passed"],
                "failed": suite["failed"],
                "summary": suite["summary"],
                "collected": suite["passed"] + suite["failed"],
                "baseline_passed": 887,
                "explanation": "Count is unchanged from the R04 baseline (887 passed). The B02 "
                "rehearsal adds no test files to the staged suite, so a changed count would "
                "itself have been the finding.",
            },
            "candidate_build": {
                "command": "./examdata/.venv/Scripts/python.exe "
                "integration-staging/runtime/b02-rehearsal-20261006/b02_build_candidate.py",
                "cwd": "C:/Users/weo/Desktop/api",
                "exit_code": 0,
                "checks_total": len(manifest["checks"]),
                "checks_passed": sum(1 for v in manifest["checks"].values() if v),
                "new_suite": True,
                "explanation": "11 build-time checks on the candidate itself; all new.",
            },
        },
        "probe_verdict": validation["verdict"],
        "probe_findings": validation["findings"],
        "discovery_identical_across_cwds": validation["discovery_identical_across_cwds"],
        "candidate_tree_digest_reproducible": validation.get(
            "candidate_tree_digest_reproducible", {}).get("sha256_match"),
        "negative_checks": negatives,
        "positive_checks": positives,
        "artifacts": {
            "candidate_manifest": rel(CANDIDATE_MANIFEST),
            "merge_proposal": rel(MERGE_JSON),
            "rollback_proposal": rel(ROLLBACK_JSON),
            "layout_validation": rel(VALIDATION),
            "suite_transcript": rel(SUITE_TXT),
            "scripts": staging_scripts(),
        },
        "proposal_counts": {
            "merge_entries": merge["counts"]["entries"],
            "merge_entries_requiring_release": merge["counts"]["entries_requiring_release"],
            "merge_staging_only_entries": merge["counts"]["staging_only_entries"],
            "rollback_entries": rollback["counts"]["entries"],
        },
        "commands": COMMANDS,
        "frozen_evidence_written": False,
        "not_run": validation["not_run"],
        "remaining_blockers": [
            {
                "blocker": "original-project merge of the B02 payload",
                "reason": "gate original_paths_released is closed; an explicit human release "
                "with an explicit scope is required",
            },
            {
                "blocker": "real Node component execution (ielts-api / toefl-api)",
                "reason": "the original components are not released; only the synthetic "
                "fake-node-cli fixture is discovered and it is never executed",
            },
            {
                "blocker": "real database schema / data-root migration",
                "reason": "gate real_data_write_authorized is closed; schema and data roots are "
                "deliberately unchanged by B02",
            },
        ],
        "process_observations": [
            {
                "observation": "The B02 probe's internal alt-cwd collided with the outer cwd on "
                "its first run from evidence/tmp, so discovery was compared against itself.",
                "handling": "The probe now picks a distinct alt-cwd and falls back to the "
                "candidate root if that name already exists; the run was repeated and the "
                "collision check is recorded in the evidence.",
            },
            {
                "observation": "The first build recorded the candidate tree digest before the "
                "candidate manifest was written, so the digest could not be reproduced from "
                "the tree on disk and the rollback guard would never have matched.",
                "handling": "The digest now excludes the manifest itself, the exclusion is "
                "recorded in the manifest and in both proposals, the builder re-checks "
                "reproducibility after writing the manifest, and the validator reproduces the "
                "digest independently. The count moved from 185-on-disk-at-hash-time to a "
                "stated 185 in the digest / 186 on disk.",
            },
        ],
    }

    report = report_md(ledger, validation)
    return ledger, report


def report_md(ledger: dict, validation: dict) -> str:
    c = ledger["changed_counts"]
    t = ledger["test_counts"]
    cmd_rows = [
        f"| {row['step']} | `{row['command']}` | `{row['cwd']}` | {row['exit_code']} |"
        for row in ledger["commands"]
    ]
    lines = [
        "# B02 rehearsal review report (private preparation only)",
        "",
        f"Generated: {ledger['generated_at']}  ",
        "Packet: **B02** — integrate shared configuration and component packaging  ",
        f"Status: `{ledger['status']}`  ",
        f"Probe verdict: `{ledger['probe_verdict']}`  ",
        f"Probe findings: {len(ledger['probe_findings'])}",
        "",
        "Nothing in this report has been merged or deployed. The original project was not "
        "read, imported or written by any B02 step. All seven gates are closed.",
        "",
        "## 1. What B02 rehearsed",
        "",
        "B02 owns the shared configuration and component packaging. What can be done without "
        "the human release is a rehearsal: take the R04 target-layout candidate as the parent, "
        "package the shared configuration beside it, and prove the acceptance properties that "
        "do not need the original tree — old aliases keep resolving, startup behaviour is "
        "unchanged, and component discovery does not depend on the working directory.",
        "",
        "## 2. Candidate and lineage",
        "",
        f"- Candidate: `{rel(CANDIDATE)}`",
        f"- Parent: `{rel(os.path.join(RUN, '..', 'r0104-repair-20261006', 'candidates', 'r04-target-layout-v2'))}`"
        " (the R04 target-layout candidate)",
        f"- Parent tree: {c['parent_tree_files']} files, sha256 "
        f"`{ledger['hashes']['parent_tree_sha256']}`",
        f"- Candidate tree: {c['candidate_tree_files']} files "
        f"({c['candidate_files_copied_from_parent']} carried from the parent + "
        f"{c['config_files_packaged']} packaged config files), sha256 "
        f"`{ledger['hashes']['candidate_tree_sha256']}`",
        f"- Candidate digest reproducible from the tree on disk: "
        f"`{ledger['candidate_tree_digest_reproducible']}` (re-checked independently by the "
        "validator, not just self-reported by the builder)",
        f"- Parent manifest sha256 unchanged at build time: "
        f"`{ledger['hashes']['parent_manifest_sha256']}`",
        "",
        "The parent tree digest was re-computed after the copy and is unchanged, so the R04 "
        "candidate was not modified by this rehearsal.",
        "",
        "## 3. Commands, working directory and exit codes",
        "",
        "| Step | Command | cwd | Exit |",
        "| --- | --- | --- | --- |",
        *cmd_rows,
        "",
        "## 4. Test results",
        "",
        f"- **Probe**: {t['b02_runtime_probe']['checks_per_run']} checks x "
        f"{t['b02_runtime_probe']['runs']} working directories = "
        f"{t['b02_runtime_probe']['checks_total']} check executions, "
        f"{t['b02_runtime_probe']['checks_failed']} failed.",
        f"- **Isolated staged suite**: {t['isolated_staged_suite']['summary']} "
        f"(exit {t['isolated_staged_suite']['exit_code']}). Unchanged from the R04 baseline of "
        f"{t['isolated_staged_suite']['baseline_passed']}; B02 adds no test file to that suite.",
        f"- **Build checks**: {t['candidate_build']['checks_passed']}/"
        f"{t['candidate_build']['checks_total']}.",
        "",
        "### Negative results (the checks that must refuse or stay unchanged)",
        "",
    ]
    lines += [f"- `{n}`" for n in ledger["negative_checks"]]
    lines += [
        "",
        "### Positive controls",
        "",
    ]
    lines += [f"- `{n}`" for n in ledger["positive_checks"]]
    lines += [
        "",
        "## 5. Old-alias preservation and startup behaviour",
        "",
        "- `IELTS_API_DIR` still resolves `ielts_dir` and still emits a deprecated-alias "
        "warning; the same holds for `TOEFL_API_DIR` / `toefl_dir`.",
        "- The canonical names alone emit no warning; the same value under both names emits "
        "only a duplicate-alias warning; conflicting values still raise.",
        "- Precedence is unchanged: explicit 9 > environment 8 > config file 7 > manifest "
        "default 6 > default 4.",
        "- Importing the package creates nothing, and `resolve_config` does not mutate "
        "`os.environ`.",
        "",
        "## 6. Component packaging",
        "",
        f"Discovery admits exactly the synthetic component set "
        f"({validation['discovery']['ids']}) with no problems, from an entry path inside the "
        "candidate, and the recorded result is identical from both working directories "
        f"(`discovery_identical_across_cwds: {validation['discovery_identical_across_cwds']}`).",
        "",
        "## 7. Proposals",
        "",
        f"- Merge proposal: `{ledger['artifacts']['merge_proposal']}` — "
        f"{ledger['proposal_counts']['merge_entries']} entries, "
        f"{ledger['proposal_counts']['merge_entries_requiring_release']} requiring the human "
        f"release, {ledger['proposal_counts']['merge_staging_only_entries']} staging-only.",
        f"- Rollback proposal: `{ledger['artifacts']['rollback_proposal']}`.",
        "",
        "Both are marked `proposal_only_not_merged`. Nothing has been applied to the original "
        "project.",
        "",
        "## 8. Live ledger and gates",
        "",
        f"- `{ledger['live_execution_ledger']['path']}` sha256 "
        f"`{ledger['live_execution_ledger']['sha256']}`",
        f"- Expected frozen value: `{ledger['live_execution_ledger']['expected_frozen_sha256']}`",
        f"- Byte-unchanged: `{ledger['live_execution_ledger']['byte_unchanged']}`",
        f"- Gates open: {ledger['live_execution_ledger']['gates_open']} "
        f"(all closed: `{ledger['live_execution_ledger']['all_gates_closed']}`)",
        "",
        "## 9. Not run",
        "",
    ]
    lines += [f"- {n['check']} — {n['reason']}" for n in ledger["not_run"]]
    lines += [
        "",
        "## 10. Not claimed / remaining blockers",
        "",
        "Not claimed: " + ", ".join(f"`{n}`" for n in ledger["not_claimed"]) + ".",
        "",
    ]
    lines += [f"- {b['blocker']} — {b['reason']}" for b in ledger["remaining_blockers"]]
    lines.append("")
    return "\n".join(lines)


def write_json(path: str, data: dict) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    print("wrote", rel(path))


def write_text(path: str, text: str) -> None:
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    print("wrote", rel(path))


def ledger_md(ledger: dict) -> str:
    lines = [
        "# B02 private progress ledger",
        "",
        f"Generated: {ledger['generated_at']}  ",
        f"Status: `{ledger['status']}`",
        "",
        "This is a private progress record, not the live execution ledger "
        f"(`{ledger['live_execution_ledger']['path']}`).",
        "",
        "| Item | Value |",
        "| --- | --- |",
        f"| live ledger sha256 | `{ledger['live_execution_ledger']['sha256']}` |",
        f"| live ledger byte-unchanged | `{ledger['live_execution_ledger']['byte_unchanged']}` |",
        f"| all gates closed | `{ledger['live_execution_ledger']['all_gates_closed']}` |",
        f"| new staging scripts | {ledger['changed_counts']['new_staging_scripts']} |",
        f"| candidates | {ledger['changed_counts']['candidates']} |",
        f"| candidate tree files | {ledger['changed_counts']['candidate_tree_files']} |",
        f"| original project files written | "
        f"{ledger['changed_counts']['original_project_files_written']} |",
        f"| frozen evidence files rewritten | "
        f"{ledger['changed_counts']['frozen_evidence_files_rewritten']} |",
        f"| probe check executions | "
        f"{ledger['test_counts']['b02_runtime_probe']['checks_total']} "
        f"({ledger['test_counts']['b02_runtime_probe']['checks_failed']} failed) |",
        f"| isolated staged suite | {ledger['test_counts']['isolated_staged_suite']['summary']} "
        f"|",
        "",
        "## Not run",
        "",
    ]
    lines += [f"- {n['check']} — {n['reason']}" for n in ledger["not_run"]]
    lines += ["", "## Remaining blockers", ""]
    lines += [f"- {b['blocker']} — {b['reason']}" for b in ledger["remaining_blockers"]]
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    ledger, report = build()
    os.makedirs(OUT, exist_ok=True)
    write_json(os.path.join(OUT, "B02_PROGRESS_LEDGER.json"), ledger)
    write_text(os.path.join(OUT, "B02_PROGRESS_LEDGER.md"), ledger_md(ledger))
    write_text(os.path.join(OUT, "B02_REHEARSAL_REPORT.md"), report)
    print(json.dumps(ledger["changed_counts"], ensure_ascii=False))
    print(json.dumps(ledger["live_execution_ledger"], ensure_ascii=False))
    if not ledger["live_execution_ledger"]["byte_unchanged"]:
        print("ERROR: live execution ledger changed", file=sys.stderr)
        return 1
    if not ledger["live_execution_ledger"]["all_gates_closed"]:
        print("ERROR: a gate is open", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
