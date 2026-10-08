"""Build the B04 merge/rollback proposals.

Proposal only: nothing is merged, deployed or reverted. Every hash is computed
from the files on disk, and every entry is derived from the B04 candidate
manifest, the A14 merge map and the B03 merge proposal, so nothing is typed by
hand (the one carried value that cannot be recomputed in Phase B is the app.py
base hash, which is mirrored verbatim from the A14 record because the original
tree is never read here).

B04 registers the staged v2 routes in the shared application. Relative to its
parent (the B03 contracts/catalog candidate) it adds exactly one new module,
the composition hook ``src/examdata/integration/api/compose.py``, and it plans
one edit to the shared application ``examdata/src/examdata/api/app.py`` which
is deferred until the human release. The candidate container itself stays
staging-only.
"""

from __future__ import annotations

import hashlib
import json
import os
import pathlib
import sys
from datetime import datetime, timezone, timedelta

WS = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
RUN = os.path.dirname(os.path.abspath(__file__))
CANDIDATE = os.path.join(RUN, "candidates", "b04-routes-v1")
OUT = os.path.join(WS, "docs", "integration", "execution")

CST = timezone(timedelta(hours=8))

CANDIDATE_MANIFEST = os.path.join(CANDIDATE, "B04_CANDIDATE_MANIFEST.json")
CANDIDATE_MANIFEST_NAME = "B04_CANDIDATE_MANIFEST.json"
PARENT = os.path.join(
    WS, "integration-staging", "runtime", "b03-rehearsal-2026-10-07", "candidates",
    "b03-contracts-catalog-v1",
)
PARENT_MANIFEST_NAME = "B03_CANDIDATE_MANIFEST.json"
PARENT_MANIFEST = os.path.join(PARENT, PARENT_MANIFEST_NAME)
A14_MAP = os.path.join(OUT, "A14_MERGE_MAP.json")
LEDGER = os.path.join(OUT, "execution-ledger.json")
R0104_MERGE = os.path.join(OUT, "R0104_MERGE_PROPOSAL.json")
B03_MERGE = os.path.join(OUT, "B03_MERGE_PROPOSAL.json")
NEW_MODULE_SOURCE = os.path.join(RUN, "tools", "compose.py")

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
    "integration-staging/runtime/b02-rehearsal-20261006/candidates/**",
    "integration-staging/runtime/b03-rehearsal-2026-10-07/candidates/b03-contracts-catalog-v1/**",
    "integration-staging/runtime/b04-rehearsal-2026-10-07/candidates/b04-routes-v1/**",
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

SKIP_DIRS = {"__pycache__", ".pytest_cache"}


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


def tree_digest(base: str, exclude: tuple[str, ...] = ()) -> dict:
    """Re-implementation of the recorded candidate digest rule.

    sha256 over 'path\\0sha256\\n' for every file under the root, sorted by
    path, skipping __pycache__/.pytest_cache and the named manifest itself.
    Recomputed here so the before/after digests in this proposal are verified
    from disk rather than trusted from the manifest.
    """
    root = pathlib.Path(base)
    entries: list[tuple[str, str]] = []
    for p in sorted(root.rglob("*")):
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        if p.is_file():
            r = p.relative_to(root).as_posix()
            if r in exclude:
                continue
            entries.append((r, sha256_file(str(p))))
    digest = hashlib.sha256()
    for r, h in entries:
        digest.update(f"{r}\0{h}\n".encode("utf-8"))
    return {"files": len(entries), "excludes": list(exclude), "sha256": digest.hexdigest()}


def a14_b04_record() -> dict:
    """The B04 planned original edit, mirrored verbatim from the A14 map."""
    for entry in load_json(A14_MAP).get("planned_original_edits", []):
        if entry.get("packet") == "B04":
            return entry
    raise ValueError("no B04 planned original edit found in the A14 merge map")


def digest_checks(manifest: dict) -> dict:
    recorded_parent = manifest["lineage"]["parent_tree"]
    recorded_candidate = manifest["candidate_tree"]
    parent_now = tree_digest(PARENT, (PARENT_MANIFEST_NAME,))
    candidate_now = tree_digest(CANDIDATE, (CANDIDATE_MANIFEST_NAME,))
    new_module = manifest.get("new_module", {})
    module_path = os.path.join(CANDIDATE, new_module.get("staged_path", ""))
    module_sha = sha256_file(module_path) if os.path.isfile(module_path) else None
    source_sha = sha256_file(NEW_MODULE_SOURCE) if os.path.isfile(NEW_MODULE_SOURCE) else None
    b03_derived = load_json(B03_MERGE).get("derived_from", {}) if os.path.isfile(B03_MERGE) else {}
    b03_crossref = bool(b03_derived) and (
        b03_derived.get("candidate_manifest_sha256") == sha256_file(PARENT_MANIFEST)
        and (b03_derived.get("candidate_tree") or {}).get("sha256") == recorded_parent["sha256"]
    )
    return {
        "candidate_tree_reverified": (
            candidate_now["files"] == recorded_candidate["files"]
            and candidate_now["sha256"] == recorded_candidate["sha256"]
        ),
        "parent_tree_reverified": (
            parent_now["files"] == recorded_parent["files"]
            and parent_now["sha256"] == recorded_parent["sha256"]
        ),
        "b03_merge_crossref_matches": b03_crossref,
        "new_module_source_matches": (
            module_sha is not None
            and module_sha == new_module.get("written_sha256")
            and source_sha == new_module.get("source_sha256")
        ),
        "note": "tree digests recomputed from disk at proposal time with the recorded rule "
        "(sha256 over 'path\\0sha256\\n', sorted, __pycache__/.pytest_cache skipped, named "
        "manifest excluded); the B03 cross-reference checks this candidate's recorded parent "
        "against B03_MERGE_PROPOSAL.json's derived_from; the new-module check compares the "
        "candidate file against the private tooling source",
    }


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
    now = datetime.now(CST).isoformat(timespec="seconds")
    ledger = gate_state()

    parent_sha = sha256_file(PARENT_MANIFEST)
    a14_sha = sha256_file(A14_MAP)
    a14_record = a14_b04_record()

    a14_unchanged: bool | None = None
    if os.path.isfile(R0104_MERGE):
        recorded = load_json(R0104_MERGE).get("derived_from", {})
        a14_unchanged = recorded.get("a14_merge_map_sha256") == a14_sha

    checks = digest_checks(manifest)

    new_module = manifest["new_module"]
    candidate_rel = rel(CANDIDATE)
    module_staged_rel = rel(os.path.join(CANDIDATE, new_module["staged_path"]))

    entries: list[dict] = [
        {
            "id": "BP-0001",
            "change": "candidate_container",
            "staged_path": candidate_rel,
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
            "sha_note": "the before digest covers the parent file set with B03's own manifest "
            "excluded (its digest rule); the after digest covers the candidate file set with "
            "B04's own manifest excluded; both use the same function and rule",
            "status": "proposal_only_not_merged",
        },
        {
            "id": "BP-0002",
            "change": "new_module_composition_hook",
            "staged_path": module_staged_rel,
            "staged_sha256_before": None,
            "staged_sha256_after": new_module["written_sha256"],
            "kind": "new_file",
            "proposed_target": "examdata/src/examdata/integration/api/compose.py",
            "proposed_target_origin": "derived from the A14 target-layout convention "
            "(candidate src/... maps to examdata/src/...); the file is new since A14, so it "
            "has no A14 entry of its own",
            "phase_b_action": "add_file at the proposed target (new module; no existing "
            "original file is edited by this entry)",
            "reversal": "delete_file at the proposed target, and only if the target's current "
            "sha256 still equals staged_sha256_after",
            "gates_required_for_this_action": ["original_paths_released"],
            "release_required": True,
            "sha_note": "staged_sha256_after is recomputed from the candidate file and equals "
            "both the private tooling source and the manifest's recorded written_sha256",
            "status": "proposal_only_not_merged",
        },
        {
            "id": "BP-0003",
            "change": "register_v2_routes_in_shared_app",
            "staged_path": None,
            "staged_sha256_before": a14_record.get("base_sha256"),
            "staged_sha256_after": None,
            "kind": "planned_edit",
            "proposed_target": a14_record.get("target_path"),
            "proposed_target_origin": "A14_MERGE_MAP.json planned_original_edits (packet B04)",
            "phase_b_action": "no file is staged for this edit by design: the changed bytes "
            "are produced only after the human release; this entry records the planned "
            "change, its base bytes and its reversal",
            "reversal": a14_record.get("reversal"),
            "a14_record": {
                "target_path": a14_record.get("target_path"),
                "base_sha256": a14_record.get("base_sha256"),
                "base_exists": a14_record.get("base_exists"),
                "observed_at": a14_record.get("observed_at"),
                "packet": a14_record.get("packet"),
                "change": a14_record.get("change"),
                "reversal": a14_record.get("reversal"),
                "note": a14_record.get("note"),
            },
            "gates_required_for_this_action": ["original_paths_released"],
            "release_required": True,
            "sha_note": "the base sha256 is carried verbatim from the A14 record (observed "
            f"{a14_record.get('observed_at')}); Phase B never read the original file, so the "
            "base hash must be re-verified at release time before any write",
            "status": "deferred_pending_release",
        },
    ]

    merge = {
        "proposal_version": "b04-merge-proposal/1",
        "packet": "B04",
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
            "parent_tree_including_manifest": manifest["lineage"]["parent_tree_including_manifest"],
            "a14_merge_map": rel(A14_MAP),
            "a14_merge_map_sha256": a14_sha,
            "a14_merge_map_byte_unchanged": a14_unchanged,
        },
        "digest_checks": checks,
        "scope_note": (
            "B04 adds exactly one new file relative to its parent (the B03 contracts/catalog "
            "candidate): the composition hook src/examdata/integration/api/compose.py. The "
            "registration into the shared application is a planned edit to "
            "examdata/src/examdata/api/app.py that stays deferred until the human release "
            "(deferred_pending_release). The product/test payload inside the candidate is the "
            "R04 payload already proposed in R0104_MERGE_PROPOSAL.json and the packaging "
            "already proposed in B02_MERGE_PROPOSAL.json; nothing is re-proposed here. "
            "Proposal only: nothing in this file has been applied to the original project. "
            "All seven gates remain closed; the original merge stays blocked until an "
            "explicit human release."
        ),
        "action_level_gate_model": ACTION_LEVEL_GATE_MODEL,
        "frozen_evidence_never_touched": FROZEN,
        "gate_state_at_generation": ledger,
        "counts": {
            "entries": len(entries),
            "entries_requiring_release": sum(1 for e in entries if e["release_required"]),
            "staging_only_entries": sum(1 for e in entries if not e["release_required"]),
            "new_files_vs_parent": manifest["counts"]["new_files_added_by_b04"],
        },
        "entries": entries,
        "not_merged": True,
        "requirements_for_merge": [
            "explicit human release opening original_paths_released with an explicit scope",
            "apply the two release-required entries: add "
            "examdata/src/examdata/integration/api/compose.py and edit "
            "examdata/src/examdata/api/app.py per the A14 record (register the staged v2 "
            "routes without removing or shadowing any legacy route; keep path ordering and "
            "operation IDs)",
            "re-verify the app.py base sha256 against the A14-recorded value immediately "
            "before the edit (Phase B never read the original file)",
            "verify the candidate tree digest (staged_sha256_after, recomputed with the "
            "recorded rule) immediately before any original write",
            "re-run the isolated staged suite against the frozen B04 candidate before any "
            "original write, and re-run the B04 route probe plus the suite against the "
            "merged tree afterwards",
        ],
    }

    rollback = {
        "proposal_version": "b04-rollback-proposal/1",
        "packet": "B04",
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
            },
            "original_level": {
                "merged_add_file": "delete_file at the proposed target, and only if its "
                "sha256 still equals sha256_at_proposal",
                "merged_planned_edit": "restore the recorded base bytes (sha256_to_restore) "
                "at the proposed target; valid only after the human release has applied the "
                "edit",
            },
            "never": [
                "never touch docs/integration/execution/evidence/**",
                "never touch integration-staging/runtime/phase-b/** sealed transcripts",
                "never touch the frozen R04 candidate under r0104-repair-20261006/candidates/**",
                "never touch the frozen B02 candidate under b02-rehearsal-20261006/candidates/**",
                "never touch the frozen B03 candidate under b03-rehearsal-2026-10-07/candidates/**",
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
                "reversible_by_delete": sum(1 for e in entries if e["kind"] == "new_file"),
                "reversible_by_restore_base": sum(
                    1 for e in entries if e["kind"] == "planned_edit"
                ),
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
                    "not applicable: no original-project target proposed"
                    if not e["proposed_target"]
                    else "delete_file at the proposed target, and only if its sha256 still "
                    "equals sha256_at_proposal; never restore a sealed snapshot"
                    if e["kind"] == "new_file"
                    else "restore the recorded base bytes (sha256_to_restore) at the proposed "
                    "target; only after the human release has applied the edit"
                ),
                "status": "proposal_only_not_merged" if e["kind"] != "planned_edit"
                else "deferred_pending_release",
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
        "# B04 merge proposal (private rehearsal only)",
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
        f"- B04 adds {m['counts']['new_files_vs_parent']} new file relative to the parent "
        "(the composition hook; everything else is a byte-identical carry of B03)",
        f"- A14 merge map byte-unchanged: `{m['derived_from']['a14_merge_map_byte_unchanged']}`",
        "",
        "## Digest and cross-reference checks",
        "",
        "| Check | Result |",
        "| --- | --- |",
        f"| candidate tree re-verified from disk | `{m['digest_checks']['candidate_tree_reverified']}` |",
        f"| parent tree re-verified from disk | `{m['digest_checks']['parent_tree_reverified']}` |",
        f"| matches B03 merge proposal's derived_from | "
        f"`{m['digest_checks']['b03_merge_crossref_matches']}` |",
        f"| new module matches the tooling source | "
        f"`{m['digest_checks']['new_module_source_matches']}` |",
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
        after = e["staged_sha256_after"][:12] if e["staged_sha256_after"] else (
            f"(deferred; base {e['staged_sha256_before'][:12]})"
            if e["staged_sha256_before"] else "(none)"
        )
        lines.append(
            f"| {e['id']} | {e['change']} | `{e['staged_path'] or '(no staged file)'}` | "
            f"`{e['proposed_target'] or '(staging only)'}` | "
            f"{after} | {gates} |"
        )
    lines += ["", "## Requirements before merge", ""]
    lines += [f"- {r}" for r in m["requirements_for_merge"]]
    lines.append("")
    return "\n".join(lines)


def rollback_md(r: dict) -> str:
    lines = [
        "# B04 rollback proposal (private rehearsal only)",
        "",
        f"Generated: {r['generated_at']}  ",
        f"Status: `{r['status']}`  ",
        f"Entries: {r['counts']['entries']} "
        f"(staging level: {r['counts']['staging_level']['reversible_by_tree_delete']} tree delete, "
        f"{r['counts']['staging_level']['reversible_by_file_delete']} file delete; "
        f"original level: {r['counts']['original_level']['reversible_by_delete']} delete, "
        f"{r['counts']['original_level']['reversible_by_restore_base']} restore base, "
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
        at = e["sha256_at_proposal"][:12] if e["sha256_at_proposal"] else "(no staged bytes)"
        lines.append(
            f"| {e['id']} | `{e['staged_path'] or '(no staged file)'}` | {e['kind']} | "
            f"{at} | {e['staging_level_reversal']} |"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    merge, rollback = build()
    os.makedirs(OUT, exist_ok=True)
    write_json(os.path.join(OUT, "B04_MERGE_PROPOSAL.json"), merge)
    write_json(os.path.join(OUT, "B04_ROLLBACK_PROPOSAL.json"), rollback)
    write_text(os.path.join(OUT, "B04_MERGE_PROPOSAL.md"), merge_md(merge))
    write_text(os.path.join(OUT, "B04_ROLLBACK_PROPOSAL.md"), rollback_md(rollback))
    print(json.dumps(merge["counts"], ensure_ascii=False))
    print(json.dumps(rollback["counts"], ensure_ascii=False))
    print(json.dumps(merge["gate_state_at_generation"]["gates"], ensure_ascii=False))
    print(json.dumps({k: v for k, v in merge["digest_checks"].items() if k != "note"},
                     ensure_ascii=False))
    failed_checks = [k for k, v in merge["digest_checks"].items() if k != "note" and not v]
    if failed_checks:
        print(f"ERROR: digest checks failed: {failed_checks}", file=sys.stderr)
        return 1
    if not merge["gate_state_at_generation"]["all_closed"]:
        print("ERROR: a gate is open", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
