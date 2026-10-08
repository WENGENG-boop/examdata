"""Build the R0104 merge/rollback proposals.

Proposal only: nothing is merged, deployed or reverted. Every entry is derived
from the change manifest produced by r0104_build_manifest.py, so hashes are
computed from the files on disk rather than typed by hand.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import datetime, timezone, timedelta

WS = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
RUN = os.path.dirname(os.path.abspath(__file__))
EVID = os.path.join(RUN, "evidence")
OUT = os.path.join(WS, "docs", "integration", "execution")

CST = timezone(timedelta(hours=8))

MANIFEST = os.path.join(EVID, "R0104_CHANGE_MANIFEST.json")
A14_MAP = os.path.join(WS, "docs", "integration", "execution", "A14_MERGE_MAP.json")
LEDGER = os.path.join(WS, "docs", "integration", "execution", "execution-ledger.json")
LAYOUT_VALIDATION = os.path.join(
    WS, "docs", "integration", "execution", "evidence", "R0104", "r0104-repair-20261006",
    "R04_LAYOUT_VALIDATION.json",
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


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def rel(path: str) -> str:
    return os.path.relpath(path, WS).replace("\\", "/")


def a14_targets() -> dict:
    with open(A14_MAP, encoding="utf-8") as fh:
        data = json.load(fh)
    return {e["staged_path"]: e.get("proposed_target") for e in data["entries"]}


def load_manifest() -> dict:
    with open(MANIFEST, encoding="utf-8") as fh:
        return json.load(fh)


def gate_state() -> dict:
    with open(LEDGER, encoding="utf-8") as fh:
        data = json.load(fh)
    return {
        "ledger_path": rel(LEDGER),
        "ledger_sha256": sha256_file(LEDGER),
        "gates": {g: bool(data["gates"][g]["open"]) for g in GATES},
        "all_closed": not any(data["gates"][g]["open"] for g in GATES),
    }


def build() -> tuple[dict, dict]:
    manifest = load_manifest()
    targets = a14_targets()
    now = datetime.now(CST).isoformat(timespec="seconds")
    ledger = gate_state()

    entries = []
    n = 0

    def derive_target(staged: str) -> str | None:
        if staged.startswith("integration-staging/src/examdata_integration/"):
            tail = staged[len("integration-staging/src/examdata_integration/"):]
            return f"examdata/src/examdata/integration/{tail}"
        if staged.startswith("integration-staging/tests/"):
            tail = staged[len("integration-staging/tests/"):]
            return f"examdata/tests/integration/{tail}"
        return None

    for group_key in ("edited_files", "new_files"):
        for item in manifest[group_key]:
            n += 1
            staged = item["path"]
            is_product = staged.startswith("integration-staging/src/") or staged.startswith(
                "integration-staging/tests/"
            )
            target = targets.get(staged)
            target_origin = "A14_MERGE_MAP.json entry"
            if target is None and is_product:
                target = derive_target(staged)
                target_origin = (
                    "derived from the A14 target-layout convention (this file is new since A14, "
                    "so it has no A14 entry)"
                )
            if target is None:
                target_origin = "staging-only tooling: no original-project target proposed"
            entries.append(
                {
                    "id": f"RP-{n:04d}",
                    "finding": item["finding"],
                    "group": item["group"],
                    "staged_path": staged,
                    "staged_sha256_before": item["sha256_before"],
                    "staged_sha256_after": item["sha256_after"],
                    "baseline_source": item["baseline_source"],
                    "diff_artifact": item["diff_artifact"],
                    "diff_sha256": item.get("diff_sha256"),
                    "kind": "new_file" if item["sha256_before"] is None else "modified_staged_file",
                    "proposed_target": target,
                    "proposed_target_origin": target_origin,
                    "phase_b_action": (
                        "add_file at the proposed target (the whole integration package is new "
                        "relative to the original project; there is no existing original file to edit)"
                        if is_product
                        else "keep in integration-staging/ only; no original-project action proposed"
                    ),
                    "reversal": (
                        "delete_file at the proposed target, and only if the target's current sha256 "
                        "still equals staged_sha256_after"
                        if is_product
                        else "no reversal needed: the file never leaves integration-staging/"
                    ),
                    "gates_required_for_this_action": (
                        ["original_paths_released"] if is_product else []
                    ),
                    "release_required": bool(is_product),
                    "status": "proposal_only_not_merged",
                }
            )

    for item in manifest["collateral_tool_edits"]:
        n += 1
        entries.append(
            {
                "id": f"RP-{n:04d}",
                "finding": item["finding"],
                "group": item["group"],
                "staged_path": item["path"],
                "staged_sha256_before": item["sha256_before"],
                "staged_sha256_after": item["sha256_after"],
                "baseline_source": item["baseline_source"],
                "diff_artifact": None,
                "diff_sha256": None,
                "kind": "staging_tooling_edit",
                "proposed_target": None,
                "proposed_target_origin": "staging-only tooling: no original-project target proposed",
                "phase_b_action": "keep in integration-staging/ only; no original-project action proposed",
                "reversal": "remove the added os.environ.setdefault(EXAMDATA_INTEGRATION_ROOT, ...) "
                "line (exact line recorded in the change manifest)",
                "gates_required_for_this_action": [],
                "release_required": False,
                "status": "proposal_only_not_merged",
                "added_lines": item.get("added_lines"),
            }
        )

    merge = {
        "proposal_version": "r0104-merge-proposal/1",
        "generated_by": rel(os.path.abspath(__file__)),
        "generated_at": now,
        "mode": "PHASE_A_PRIVATE_ONLY",
        "status": "proposal_only_nothing_merged_not_deployed",
        "derived_from": {
            "change_manifest": rel(MANIFEST),
            "change_manifest_sha256": sha256_file(MANIFEST),
            "a14_merge_map": rel(A14_MAP),
            "a14_merge_map_sha256": sha256_file(A14_MAP),
            "a14_merge_map_byte_unchanged": True,
        },
        "scope_note": (
            "One entry per R01-R04 changed file. Proposal only: nothing in this file has been "
            "applied to the original project. All seven gates remain closed. The original merge "
            "stays blocked until an explicit human release; see gates_required_for_this_action "
            "on each entry."
        ),
        "action_level_gate_model": {
            "principle": "A gate is required only for the action that performs that effect. "
            "Private preparation never satisfies an original-action prerequisite.",
            "private_preparation": {
                "gates_required": [],
                "note": "reading, staging, private copies, offline validation, synthetic fixtures: "
                "no gate required and none is opened",
            },
            "original_path_write": {
                "gates_required": ["original_paths_released"],
                "note": "any write into the original project requires the human release",
            },
            "other_actions": {
                "real_data_write": "real_data_write_authorized",
                "existing_service_cutover": "existing_service_cutover_authorized",
                "upstream_request": "upstream_requests_authorized",
                "cie_resume": "cie_resume_authorized",
                "remote_deployment": "remote_deployment_authorized",
                "original_cleanup": "original_cleanup_authorized",
            },
        },
        "gate_state_at_generation": ledger,
        "counts": {
            "entries": len(entries),
            "product_or_test_entries_requiring_release": sum(
                1 for e in entries if e["release_required"]
            ),
            "staging_only_entries": sum(1 for e in entries if not e["release_required"]),
        },
        "entries": entries,
        "not_merged": True,
        "requirements_for_merge": [
            "explicit human release opening original_paths_released with an explicit scope",
            "re-run the isolated staged suite against the frozen candidate",
            "verify each proposed target's sha256 before and after the add_file",
        ],
    }

    rollback = {
        "proposal_version": "r0104-rollback-proposal/1",
        "generated_by": rel(os.path.abspath(__file__)),
        "generated_at": now,
        "status": "proposal_only_nothing_merged_not_deployed",
        "derived_from": {
            "merge_proposal_entries": len(entries),
            "change_manifest": rel(MANIFEST),
            "change_manifest_sha256": sha256_file(MANIFEST),
        },
        "semantics": {
            "staging_level": {
                "modified_staged_file": "restore the recorded staged_sha256_before bytes only if "
                "the current staged file still matches staged_sha256_after; never restore a sealed "
                "snapshot",
                "new_file": "delete only if the current file still matches staged_sha256_after",
                "staging_tooling_edit": "remove the recorded added line",
            },
            "original_level": {
                "merged_add_file": "delete_file at the proposed target, and only if its sha256 "
                "still equals staged_sha256_after",
            },
            "never": [
                "never touch docs/integration/execution/evidence/**",
                "never touch integration-staging/runtime/phase-b/** sealed transcripts",
                "never restore the live execution ledger from a private copy",
            ],
        },
        "guards": [
            "verify the resolved absolute path and its sha256 before any delete/restore",
            "no delete or restore ever targets a protected original in Phase A",
            "planned original edits are reversible only after the human release",
            "all seven gates remain closed during rollback",
        ],
        "counts": {
            "entries": len(entries),
            "staging_level": {
                "reversible_by_delete": sum(1 for e in entries if e["kind"] == "new_file"),
                "reversible_by_restore": sum(1 for e in entries if e["kind"] == "modified_staged_file"),
                "reversible_by_line_removal": sum(1 for e in entries if e["kind"] == "staging_tooling_edit"),
            },
            "original_level": {
                "reversible_by_delete": sum(1 for e in entries if e["proposed_target"]),
                "no_original_action": sum(1 for e in entries if not e["proposed_target"]),
            },
        },
        "gate_state_at_generation": ledger,
        "entries": [
            {
                "id": e["id"],
                "staged_path": e["staged_path"],
                "proposed_target": e["proposed_target"],
                "kind": e["kind"],
                "sha256_at_proposal": e["staged_sha256_after"],
                "sha256_to_restore": e["staged_sha256_before"],
                "staging_level_reversal": e["reversal"],
                "original_level_reversal": (
                    "delete_file at the proposed target, and only if its sha256 still equals "
                    "staged_sha256_after; never restore a sealed snapshot"
                    if e["proposed_target"]
                    else "not applicable: no original-project target proposed"
                ),
                "status": "proposal_only_not_merged",
            }
            for e in entries
        ],
    }
    return merge, rollback


def write_json(path: str, data: dict) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    print("wrote", rel(path))


def merge_md(m: dict) -> str:
    lines = [
        "# R0104 merge proposal (private preparation only)",
        "",
        f"Generated: {m['generated_at']}  ",
        f"Status: `{m['status']}`  ",
        f"Entries: {m['counts']['entries']} "
        f"({m['counts']['product_or_test_entries_requiring_release']} require the human release, "
        f"{m['counts']['staging_only_entries']} are staging-only tooling)",
        "",
        "Nothing in this proposal has been applied. All seven gates are closed.",
        "",
        "## Action-level gate model",
        "",
        "A gate is required only for the action that performs that effect.",
        "A private-preparation pass never satisfies an original-action prerequisite.",
        "",
        "| Action | Gate required |",
        "| --- | --- |",
        "| private preparation (read, stage, copy, offline validate) | none |",
        "| write into the original project | `original_paths_released` |",
        "| real data write | `real_data_write_authorized` |",
        "| existing service cutover | `existing_service_cutover_authorized` |",
        "| upstream request | `upstream_requests_authorized` |",
        "| CIE resume | `cie_resume_authorized` |",
        "| remote deployment | `remote_deployment_authorized` |",
        "| original cleanup | `original_cleanup_authorized` |",
        "",
        "## Entries",
        "",
        "| id | finding | staged path | proposed target | before | after | gates |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for e in m["entries"]:
        gates = ", ".join(e["gates_required_for_this_action"]) or "none"
        lines.append(
            f"| {e['id']} | {e['finding']} | `{e['staged_path']}` | "
            f"`{e['proposed_target'] or '(staging only)'}` | "
            f"{(e['staged_sha256_before'] or 'none')[:12]} | {e['staged_sha256_after'][:12]} | {gates} |"
        )
    lines += [
        "",
        "## Requirements before merge",
        "",
    ]
    lines += [f"- {r}" for r in m["requirements_for_merge"]]
    lines.append("")
    return "\n".join(lines)


def rollback_md(r: dict) -> str:
    lines = [
        "# R0104 rollback proposal (private preparation only)",
        "",
        f"Generated: {r['generated_at']}  ",
        f"Status: `{r['status']}`  ",
        f"Entries: {r['counts']['entries']} "
        f"(staging level: {r['counts']['staging_level']['reversible_by_delete']} delete, "
        f"{r['counts']['staging_level']['reversible_by_restore']} restore, "
        f"{r['counts']['staging_level']['reversible_by_line_removal']} line removal; "
        f"original level: {r['counts']['original_level']['reversible_by_delete']} delete, "
        f"{r['counts']['original_level']['no_original_action']} no original action)",
        "",
        "Nothing has been merged, so nothing is currently pending rollback. This file states how "
        "each change would be reversed.",
        "",
        "## Guards",
        "",
    ]
    lines += [f"- {g}" for g in r["guards"]]
    lines += [
        "",
        "## Never",
        "",
    ]
    lines += [f"- {g}" for g in r["semantics"]["never"]]
    lines += [
        "",
        "## Entries",
        "",
        "| id | staged path | kind | restore to | reversal |",
        "| --- | --- | --- | --- | --- |",
    ]
    for e in r["entries"]:
        lines.append(
            f"| {e['id']} | `{e['staged_path']}` | {e['kind']} | "
            f"{(e['sha256_to_restore'] or 'delete')[:12]} | {e['staging_level_reversal']} |"
        )
    lines.append("")
    return "\n".join(lines)


def write_text(path: str, text: str) -> None:
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    print("wrote", rel(path))


def main() -> int:
    merge, rollback = build()
    os.makedirs(OUT, exist_ok=True)
    write_json(os.path.join(OUT, "R0104_MERGE_PROPOSAL.json"), merge)
    write_json(os.path.join(OUT, "R0104_ROLLBACK_PROPOSAL.json"), rollback)
    write_text(os.path.join(OUT, "R0104_MERGE_PROPOSAL.md"), merge_md(merge))
    write_text(os.path.join(OUT, "R0104_ROLLBACK_PROPOSAL.md"), rollback_md(rollback))
    print(json.dumps(merge["counts"], ensure_ascii=False))
    print(json.dumps(rollback["counts"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
