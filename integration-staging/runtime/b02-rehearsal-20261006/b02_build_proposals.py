"""Build the B02 merge/rollback proposals.

Proposal only: nothing is merged, deployed or reverted. Every hash is computed
from the files on disk, and every entry is derived from the B02 candidate
manifest plus the A14 merge map, so nothing is typed by hand.

B02 is a rehearsal container: it is the R04 target-layout candidate plus the
shared-configuration packaging. Its product/test payload is the R04 payload
already proposed in R0104_MERGE_PROPOSAL.json; the new original-project-facing
material in B02 is exactly the `config/` packaging. The candidate tree itself is
a staging-only container and is reversible by deleting it.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import datetime, timezone, timedelta

WS = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
RUN = os.path.dirname(os.path.abspath(__file__))
CANDIDATE = os.path.join(RUN, "candidates", "b02-shared-config-v1")
OUT = os.path.join(WS, "docs", "integration", "execution")

CST = timezone(timedelta(hours=8))

CANDIDATE_MANIFEST = os.path.join(CANDIDATE, "B02_CANDIDATE_MANIFEST.json")
PARENT_MANIFEST = os.path.join(
    WS, "integration-staging", "runtime", "r0104-repair-20261006", "candidates",
    "r04-target-layout-v2", "R04_CANDIDATE_MANIFEST.json",
)
A14_MAP = os.path.join(OUT, "A14_MERGE_MAP.json")
LEDGER = os.path.join(OUT, "execution-ledger.json")
R0104_MERGE = os.path.join(OUT, "R0104_MERGE_PROPOSAL.json")

CONFIG_DIR = os.path.join(WS, "integration-staging", "config")

GATES = [
    "original_paths_released",
    "real_data_write_authorized",
    "existing_service_cutover_authorized",
    "upstream_requests_authorized",
    "cie_resume_authorized",
    "remote_deployment_authorized",
    "original_cleanup_authorized",
]

FROZEN = [
    "docs/integration/execution/evidence/**",
    "integration-staging/runtime/phase-b/**",
    "integration-staging/runtime/r0104-repair-20261006/candidates/**",
    "integration-staging/runtime/b02-rehearsal-20261006/candidates/b02-shared-config-v1/**",
]

ACTION_LEVEL_GATE_MODEL = {
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
}


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


def a14_entries() -> dict:
    data = load_json(A14_MAP)
    by_path = {e["staged_path"]: e for e in data.get("entries", [])}
    excluded = {
        e["staged_path"]: e.get("reason")
        for e in data.get("excluded", data.get("not_merged", []))
    }
    return {"by_path": by_path, "excluded": excluded}


def gate_state() -> dict:
    data = load_json(LEDGER)
    return {
        "ledger_path": rel(LEDGER),
        "ledger_sha256": sha256_file(LEDGER),
        "gates": {g: bool(data["gates"][g]["open"]) for g in GATES},
        "all_closed": not any(data["gates"][g]["open"] for g in GATES),
    }


def build() -> tuple[dict, dict]:
    manifest = load_json(CANDIDATE_MANIFEST)
    a14 = a14_entries()
    now = datetime.now(CST).isoformat(timespec="seconds")
    ledger = gate_state()

    parent_sha = sha256_file(PARENT_MANIFEST)
    a14_sha = sha256_file(A14_MAP)

    a14_unchanged: bool | None = None
    if os.path.isfile(R0104_MERGE):
        recorded = load_json(R0104_MERGE).get("derived_from", {})
        a14_unchanged = recorded.get("a14_merge_map_sha256") == a14_sha

    entries: list[dict] = []
    n = 0

    n += 1
    entries.append(
        {
            "id": f"BP-{n:04d}",
            "change": "candidate_container",
            "staged_path": rel(CANDIDATE),
            "staged_sha256_before": manifest["lineage"]["parent_tree"]["sha256"],
            "staged_sha256_after": manifest["candidate_tree"]["sha256"],
            "kind": "staging_candidate_tree",
            "proposed_target": None,
            "proposed_target_origin": "staging-only rehearsal container: no original-project target",
            "phase_b_action": "keep in integration-staging/ only; no original-project action proposed",
            "reversal": "delete the candidate tree, and only if its current tree digest still "
            "equals staged_sha256_after",
            "gates_required_for_this_action": [],
            "release_required": False,
            "status": "proposal_only_not_merged",
        }
    )

    for name in sorted(os.listdir(CONFIG_DIR)):
        src = os.path.join(CONFIG_DIR, name)
        if not os.path.isfile(src):
            continue
        staged = rel(src)
        a14_entry = a14.get("by_path", {}).get(staged)
        excluded_reason = a14.get("excluded", {}).get(staged)
        if a14_entry is not None:
            target = a14_entry.get("proposed_target")
            origin = f"A14_MERGE_MAP.json entry {a14_entry['id']}"
            verification = a14_entry.get("verification", [])
        elif excluded_reason:
            target = None
            origin = f"A14_MERGE_MAP.json excluded list: {excluded_reason}"
            verification = []
        else:
            target = None
            origin = "no A14 entry: no original-project target proposed"
            verification = []
        is_product = target is not None
        n += 1
        entries.append(
            {
                "id": f"BP-{n:04d}",
                "change": "shared_config_packaging",
                "staged_path": staged,
                "staged_sha256_before": None,
                "staged_sha256_after": sha256_file(src),
                "kind": "new_file",
                "proposed_target": target,
                "proposed_target_origin": origin,
                "phase_b_action": (
                    f"add_file at {target} (new relative to the original project; there is no "
                    "existing original file to edit)"
                    if is_product
                    else "keep in integration-staging/ only; no original-project action proposed"
                ),
                "reversal": (
                    f"delete_file at {target}, and only if the target's current sha256 still "
                    "equals staged_sha256_after"
                    if is_product
                    else "no reversal needed: the file never leaves integration-staging/"
                ),
                "gates_required_for_this_action": (
                    ["original_paths_released"] if is_product else []
                ),
                "release_required": bool(is_product),
                "verification": verification,
                "status": "proposal_only_not_merged",
            }
        )

    merge = {
        "proposal_version": "b02-merge-proposal/1",
        "packet": "B02",
        "generated_by": rel(os.path.abspath(__file__)),
        "generated_at": now,
        "mode": "PHASE_B_PRIVATE_REHEARSAL_ONLY",
        "status": "proposal_only_nothing_merged_not_deployed",
        "derived_from": {
            "candidate_manifest": rel(CANDIDATE_MANIFEST),
            "candidate_manifest_sha256": sha256_file(CANDIDATE_MANIFEST),
            "candidate_tree": manifest["candidate_tree"],
            "candidate_tree_digest_rule": manifest.get("digest_rule"),
            "parent_manifest": rel(PARENT_MANIFEST),
            "parent_manifest_sha256": parent_sha,
            "parent_manifest_sha256_at_build": manifest["lineage"]["parent_manifest_sha256"],
            "parent_tree": manifest["lineage"]["parent_tree"],
            "a14_merge_map": rel(A14_MAP),
            "a14_merge_map_sha256": a14_sha,
            "a14_merge_map_byte_unchanged": a14_unchanged,
        },
        "scope_note": (
            "B02 delta relative to its parent R04 candidate is the shared-configuration "
            "packaging only; the product/test payload inside the candidate is the R04 payload "
            "already proposed in R0104_MERGE_PROPOSAL.json and is not re-proposed here. "
            "Proposal only: nothing in this file has been applied to the original project. "
            "All seven gates remain closed; the original merge stays blocked until an explicit "
            "human release."
        ),
        "action_level_gate_model": ACTION_LEVEL_GATE_MODEL,
        "frozen_evidence_never_touched": FROZEN,
        "gate_state_at_generation": ledger,
        "counts": {
            "entries": len(entries),
            "entries_requiring_release": sum(1 for e in entries if e["release_required"]),
            "staging_only_entries": sum(1 for e in entries if not e["release_required"]),
        },
        "entries": entries,
        "not_merged": True,
        "requirements_for_merge": [
            "explicit human release opening original_paths_released with an explicit scope",
            "re-run the isolated staged suite against the frozen B02 candidate",
            "verify each proposed target's sha256 before and after the add_file",
        ],
    }

    rollback = {
        "proposal_version": "b02-rollback-proposal/1",
        "packet": "B02",
        "generated_by": rel(os.path.abspath(__file__)),
        "generated_at": now,
        "status": "proposal_only_nothing_merged_not_deployed",
        "derived_from": {
            "merge_proposal_entries": len(entries),
            "candidate_manifest": rel(CANDIDATE_MANIFEST),
            "candidate_manifest_sha256": sha256_file(CANDIDATE_MANIFEST),
            "candidate_tree": manifest["candidate_tree"],
        },
        "semantics": {
            "staging_level": {
                "staging_candidate_tree": "delete the candidate tree only if its current tree "
                "digest still equals sha256_at_proposal, recomputed with the rule recorded in "
                "derived_from.candidate_tree_digest_rule (the candidate's own manifest is "
                "excluded, since a file cannot hash itself)",
                "new_file": "delete only if the current file still matches sha256_at_proposal",
            },
            "original_level": {
                "merged_add_file": "delete_file at the proposed target, and only if its sha256 "
                "still equals sha256_at_proposal",
            },
            "never": [
                "never touch docs/integration/execution/evidence/**",
                "never touch integration-staging/runtime/phase-b/** sealed transcripts",
                "never touch the frozen R04 candidate under r0104-repair-20261006/candidates/**",
                "never restore the live execution ledger from a private copy",
            ],
        },
        "guards": [
            "verify the resolved absolute path and its sha256 (or tree digest) before any delete",
            "no delete ever targets a protected original in Phase B private rehearsal",
            "planned original edits are reversible only after the human release",
            "all seven gates remain closed during rollback",
        ],
        "counts": {
            "entries": len(entries),
            "staging_level": {
                "reversible_by_tree_delete": sum(
                    1 for e in entries if e["kind"] == "staging_candidate_tree"
                ),
                "reversible_by_file_delete": sum(1 for e in entries if e["kind"] == "new_file"),
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
                    "sha256_at_proposal; never restore a sealed snapshot"
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


def write_text(path: str, text: str) -> None:
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    print("wrote", rel(path))


def merge_md(m: dict) -> str:
    lines = [
        "# B02 merge proposal (private rehearsal only)",
        "",
        f"Generated: {m['generated_at']}  ",
        f"Status: `{m['status']}`  ",
        f"Entries: {m['counts']['entries']} "
        f"({m['counts']['entries_requiring_release']} require the human release, "
        f"{m['counts']['staging_only_entries']} are staging-only)",
        "",
        "Nothing in this proposal has been applied. All seven gates are closed.",
        "",
        "## Candidate lineage",
        "",
        f"- parent: `{m['derived_from']['parent_manifest']}` "
        f"(sha256 `{m['derived_from']['parent_manifest_sha256'][:12]}`)",
        f"- parent tree: {m['derived_from']['parent_tree']['files']} files, "
        f"sha256 `{m['derived_from']['parent_tree']['sha256'][:12]}`",
        f"- candidate tree: {m['derived_from']['candidate_tree']['files']} files, "
        f"sha256 `{m['derived_from']['candidate_tree']['sha256'][:12]}`",
        f"- A14 merge map byte-unchanged: `{m['derived_from']['a14_merge_map_byte_unchanged']}`",
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
        "| id | change | staged path | proposed target | after | gates |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for e in m["entries"]:
        gates = ", ".join(e["gates_required_for_this_action"]) or "none"
        lines.append(
            f"| {e['id']} | {e['change']} | `{e['staged_path']}` | "
            f"`{e['proposed_target'] or '(staging only)'}` | "
            f"{e['staged_sha256_after'][:12]} | {gates} |"
        )
    lines += ["", "## Requirements before merge", ""]
    lines += [f"- {r}" for r in m["requirements_for_merge"]]
    lines.append("")
    return "\n".join(lines)


def rollback_md(r: dict) -> str:
    lines = [
        "# B02 rollback proposal (private rehearsal only)",
        "",
        f"Generated: {r['generated_at']}  ",
        f"Status: `{r['status']}`  ",
        f"Entries: {r['counts']['entries']} "
        f"(staging level: {r['counts']['staging_level']['reversible_by_tree_delete']} tree delete, "
        f"{r['counts']['staging_level']['reversible_by_file_delete']} file delete; "
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
    lines += ["", "## Never", ""]
    lines += [f"- {g}" for g in r["semantics"]["never"]]
    lines += [
        "",
        "## Entries",
        "",
        "| id | staged path | kind | sha256 at proposal | reversal |",
        "| --- | --- | --- | --- | --- |",
    ]
    for e in r["entries"]:
        lines.append(
            f"| {e['id']} | `{e['staged_path']}` | {e['kind']} | "
            f"{e['sha256_at_proposal'][:12]} | {e['staging_level_reversal']} |"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    merge, rollback = build()
    os.makedirs(OUT, exist_ok=True)
    write_json(os.path.join(OUT, "B02_MERGE_PROPOSAL.json"), merge)
    write_json(os.path.join(OUT, "B02_ROLLBACK_PROPOSAL.json"), rollback)
    write_text(os.path.join(OUT, "B02_MERGE_PROPOSAL.md"), merge_md(merge))
    write_text(os.path.join(OUT, "B02_ROLLBACK_PROPOSAL.md"), rollback_md(rollback))
    print(json.dumps(merge["counts"], ensure_ascii=False))
    print(json.dumps(rollback["counts"], ensure_ascii=False))
    print(json.dumps(merge["gate_state_at_generation"]["gates"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
