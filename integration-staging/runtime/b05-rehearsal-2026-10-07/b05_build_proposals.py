"""Build the B05 merge/rollback proposals.

Proposal only: nothing is merged, deployed or reverted. Every hash is computed
from the files on disk, and every entry is derived from the B05 candidate
manifest, the A14 merge map, the R0104 merge proposal and the B04 merge
proposal, so nothing is typed by hand (the values that cannot be recomputed in
Phase B are mirrored verbatim from the frozen records because the original tree
is never read here).

B05 is the active-owner seam: one new module
``src/examdata/integration/adapters/active_owner.py`` plus two rewritten
carried modules (``api/dataset.py``, ``api/app.py``) that read the five feature
families through that seam. Relative to its parent (the B04 routes candidate)
nothing else changes. The two rewrites supersede the staged bytes recorded by
R0104_MERGE_PROPOSAL.json RP-0005 (dataset.py) and A14 MM-0015 (app.py); the
whole integration package is new relative to the original project, so every
release-required entry is add_file semantics. The candidate container itself
stays staging-only.
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
CANDIDATE = os.path.join(RUN, "candidates", "b05-adapters-v1")
OUT = os.path.join(WS, "docs", "integration", "execution")

CST = timezone(timedelta(hours=8))

CANDIDATE_MANIFEST = os.path.join(CANDIDATE, "B05_CANDIDATE_MANIFEST.json")
CANDIDATE_MANIFEST_NAME = "B05_CANDIDATE_MANIFEST.json"
PARENT = os.path.join(
    WS, "integration-staging", "runtime", "b04-rehearsal-2026-10-07", "candidates",
    "b04-routes-v1",
)
PARENT_MANIFEST_NAME = "B04_CANDIDATE_MANIFEST.json"
PARENT_MANIFEST = os.path.join(PARENT, PARENT_MANIFEST_NAME)
A14_MAP = os.path.join(OUT, "A14_MERGE_MAP.json")
LEDGER = os.path.join(OUT, "execution-ledger.json")
R0104_MERGE = os.path.join(OUT, "R0104_MERGE_PROPOSAL.json")
B04_MERGE = os.path.join(OUT, "B04_MERGE_PROPOSAL.json")
NEW_MODULE_SOURCE = os.path.join(RUN, "tools", "active_owner.py")
EDITED_SOURCES = {
    "src/examdata/integration/api/dataset.py": os.path.join(RUN, "tools", "dataset.py"),
    "src/examdata/integration/api/app.py": os.path.join(RUN, "tools", "app.py"),
}
SOURCE_EDITS_DIFF = os.path.join(RUN, "evidence", "source_edits.diff")

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
    "integration-staging/runtime/b05-rehearsal-2026-10-07/candidates/b05-adapters-v1/**",
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


def file_set(base: str) -> set:
    root = pathlib.Path(base)
    out: set = set()
    for p in sorted(root.rglob("*")):
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        if p.is_file():
            out.add(p.relative_to(root).as_posix())
    return out


def a14_entry(entry_id: str) -> dict:
    for entry in load_json(A14_MAP).get("entries", []):
        if entry.get("id") == entry_id:
            return entry
    raise ValueError(f"A14 entry {entry_id} not found in the merge map")


def r0104_entry(entry_id: str) -> dict:
    for entry in load_json(R0104_MERGE).get("entries", []):
        if entry.get("id") == entry_id:
            return entry
    raise ValueError(f"R0104 entry {entry_id} not found in the merge proposal")


def digest_checks(manifest: dict, edited_by_path: dict) -> dict:
    recorded_parent = manifest["lineage"]["parent_tree"]
    recorded_candidate = manifest["candidate_tree"]
    parent_now = tree_digest(PARENT, (PARENT_MANIFEST_NAME,))
    candidate_now = tree_digest(CANDIDATE, (CANDIDATE_MANIFEST_NAME,))
    new_module = manifest.get("new_module", {})
    module_path = os.path.join(CANDIDATE, new_module.get("staged_path", ""))
    module_sha = sha256_file(module_path) if os.path.isfile(module_path) else None
    source_sha = sha256_file(NEW_MODULE_SOURCE) if os.path.isfile(NEW_MODULE_SOURCE) else None

    b04_derived = load_json(B04_MERGE).get("derived_from", {}) if os.path.isfile(B04_MERGE) else {}
    b04_crossref = bool(b04_derived) and (
        b04_derived.get("candidate_manifest_sha256") == sha256_file(PARENT_MANIFEST)
        and (b04_derived.get("candidate_tree") or {}).get("sha256") == recorded_parent["sha256"]
    )

    edited_checks: dict[str, bool] = {}
    for edit in manifest.get("edited_files", []):
        path = edit["path"]
        staged = os.path.join(CANDIDATE, path)
        source = EDITED_SOURCES.get(path, edit.get("source", ""))
        parent_file = os.path.join(PARENT, path)
        edited_checks[path] = bool(
            os.path.isfile(staged)
            and os.path.isfile(source)
            and sha256_file(staged) == edit.get("written_sha256")
            and sha256_file(source) == edit.get("source_sha256")
            and sha256_file(parent_file) == edit.get("parent_sha256")
            and edit.get("written_sha256") != edit.get("parent_sha256")
        )

    candidate_files = file_set(CANDIDATE) - {CANDIDATE_MANIFEST_NAME}
    parent_files = file_set(PARENT)
    new_files = sorted(candidate_files - parent_files)
    changed = sorted(r for r in parent_files & candidate_files
                     if sha256_file(os.path.join(PARENT, r))
                     != sha256_file(os.path.join(CANDIDATE, r)))

    a14_dataset = a14_entry("MM-0017")
    a14_app = a14_entry("MM-0015")
    rp0005 = r0104_entry("RP-0005")
    dataset_edit = edited_by_path["src/examdata/integration/api/dataset.py"]
    app_edit = edited_by_path["src/examdata/integration/api/app.py"]
    supersession = {
        "dataset_chain": (
            a14_dataset.get("staged_sha256") == rp0005.get("staged_sha256_before")
            and rp0005.get("staged_sha256_after") == dataset_edit.get("parent_sha256")
            and rp0005.get("proposed_target") == a14_dataset.get("proposed_target")
        ),
        "app_chain": (
            a14_app.get("staged_sha256") == app_edit.get("parent_sha256")
            and a14_app.get("proposed_target") == "examdata/src/examdata/integration/api/app.py"
        ),
    }

    return {
        "candidate_tree_reverified": (
            candidate_now["files"] == recorded_candidate["files"]
            and candidate_now["sha256"] == recorded_candidate["sha256"]
        ),
        "parent_tree_reverified": (
            parent_now["files"] == recorded_parent["files"]
            and parent_now["sha256"] == recorded_parent["sha256"]
        ),
        "b04_merge_crossref_matches": b04_crossref,
        "new_module_source_matches": (
            module_sha is not None
            and module_sha == new_module.get("written_sha256")
            and source_sha == new_module.get("source_sha256")
        ),
        "edited_files_source_matches": all(edited_checks.values()),
        "new_files_exactly_one_vs_parent": new_files == [
            "src/examdata/integration/adapters/active_owner.py"
        ],
        "only_the_two_edited_files_changed_vs_parent": changed == sorted(EDITED_SOURCES),
        "supersession_chains_match": all(supersession.values()),
        "supersession_chain_detail": supersession,
        "note": "tree digests recomputed from disk at proposal time with the recorded rule "
        "(sha256 over 'path\\0sha256\\n', sorted, __pycache__/.pytest_cache skipped, named "
        "manifest excluded); the B04 cross-reference checks this candidate's recorded parent "
        "against B04_MERGE_PROPOSAL.json's derived_from; the new-module and edited-file "
        "checks compare the candidate files against both the private tooling sources and the "
        "manifest; the file-set comparison excludes only the candidate's own manifest "
        "because the child carries a byte-identical copy of the parent's manifest; the "
        "supersession chains re-verify the A14 and R0104 records that the two "
        "rewritten staged files supersede (dataset: A14 MM-0017 -> R0104 RP-0005 -> B05; "
        "app: A14 MM-0015 -> B05)",
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
    a14_record = a14_entry("MM-0015")

    a14_unchanged: bool | None = None
    if os.path.isfile(R0104_MERGE):
        recorded = load_json(R0104_MERGE).get("derived_from", {})
        a14_unchanged = recorded.get("a14_merge_map_sha256") == a14_sha

    edited_by_path = {e["path"]: e for e in manifest.get("edited_files", [])}
    checks = digest_checks(manifest, edited_by_path)

    new_module = manifest["new_module"]
    dataset_edit = edited_by_path["src/examdata/integration/api/dataset.py"]
    app_edit = edited_by_path["src/examdata/integration/api/app.py"]
    candidate_rel = rel(CANDIDATE)
    module_staged_rel = rel(os.path.join(CANDIDATE, new_module["staged_path"]))
    dataset_staged_rel = rel(os.path.join(CANDIDATE, dataset_edit["path"]))
    app_staged_rel = rel(os.path.join(CANDIDATE, app_edit["path"]))

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
            "sha_note": "the before digest covers the parent (B04) file set with B04's own "
            "manifest excluded (its digest rule); the after digest covers the candidate file "
            "set with B05's own manifest excluded; both use the same function and rule",
            "status": "proposal_only_not_merged",
        },
        {
            "id": "BP-0002",
            "change": "new_module_active_owner_seam",
            "staged_path": module_staged_rel,
            "staged_sha256_before": None,
            "staged_sha256_after": new_module["written_sha256"],
            "kind": "new_file",
            "proposed_target": "examdata/src/examdata/integration/adapters/active_owner.py",
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
            "change": "rewrite_integration_dataset_for_the_seam",
            "staged_path": dataset_staged_rel,
            "staged_sha256_before": dataset_edit["parent_sha256"],
            "staged_sha256_after": dataset_edit["written_sha256"],
            "kind": "staged_file_rewrite",
            "proposed_target": "examdata/src/examdata/integration/api/dataset.py",
            "proposed_target_origin": "A14_MERGE_MAP.json entry MM-0017 via "
            "R0104_MERGE_PROPOSAL.json RP-0005; the B05 bytes supersede the R0104-repaired "
            "bytes",
            "phase_b_action": "add_file at the proposed target with the B05 bytes (the whole "
            "integration package is new relative to the original project; there is no "
            "existing original file to edit; A14 observed the target as not existing)",
            "reversal": "delete_file at the proposed target, and only if the target's current "
            "sha256 still equals staged_sha256_after",
            "supersedes": {
                "proposal": "R0104_MERGE_PROPOSAL.json RP-0005",
                "superseded_staged_sha256_after": dataset_edit["parent_sha256"],
                "chain": "A14 MM-0017 (5801f31c...) -> R0104 RP-0005 -> B05",
            },
            "gates_required_for_this_action": ["original_paths_released"],
            "release_required": True,
            "sha_note": "staged_sha256_before is the R0104-repaired staged version this "
            "rewrite replaces; the chain is re-verified in "
            "digest_checks.supersession_chain_detail",
            "status": "proposal_only_not_merged",
        },
        {
            "id": "BP-0004",
            "change": "rewrite_integration_app_for_the_seam",
            "staged_path": app_staged_rel,
            "staged_sha256_before": app_edit["parent_sha256"],
            "staged_sha256_after": app_edit["written_sha256"],
            "kind": "staged_file_rewrite",
            "proposed_target": "examdata/src/examdata/integration/api/app.py",
            "proposed_target_origin": "A14_MERGE_MAP.json entry MM-0015; the B05 bytes "
            "supersede the A14-staged bytes",
            "phase_b_action": "add_file at the proposed target with the B05 bytes (the whole "
            "integration package is new relative to the original project; there is no "
            "existing original file to edit; A14 observed the target as not existing)",
            "reversal": "delete_file at the proposed target, and only if the target's current "
            "sha256 still equals staged_sha256_after",
            "supersedes": {
                "proposal": "A14_MERGE_MAP.json MM-0015",
                "superseded_staged_sha256": app_edit["parent_sha256"],
                "chain": "A14 MM-0015 -> B05",
            },
            "gates_required_for_this_action": ["original_paths_released"],
            "release_required": True,
            "sha_note": "staged_sha256_before is the A14-staged version this rewrite "
            "replaces; the chain is re-verified in "
            "digest_checks.supersession_chain_detail",
            "status": "proposal_only_not_merged",
        },
    ]

    merge = {
        "proposal_version": "b05-merge-proposal/1",
        "packet": "B05",
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
            "source_edits_diff": rel(SOURCE_EDITS_DIFF),
            "source_edits_diff_sha256": sha256_file(SOURCE_EDITS_DIFF)
            if os.path.isfile(SOURCE_EDITS_DIFF) else None,
        },
        "digest_checks": checks,
        "scope_note": (
            "B05 adds exactly one new file relative to its parent (the B04 routes candidate) "
            "- the active-owner seam src/examdata/integration/adapters/active_owner.py - and "
            "rewrites exactly two carried modules so the five feature families "
            "(materials, syllabuses, timetable seasons, events, windows) are read through "
            "that seam: src/examdata/integration/api/dataset.py and "
            "src/examdata/integration/api/app.py. Everything else in the candidate is a "
            "byte-identical carry of B04. The staged bytes of the two rewritten modules "
            "supersede the bytes recorded by R0104_MERGE_PROPOSAL.json RP-0005 (dataset.py) "
            "and A14 MM-0015 (app.py); the whole integration package is new relative to the "
            "original project, so every release-required entry is add_file semantics. The "
            "composition hook and the shared-application registration remain as proposed in "
            "B04_MERGE_PROPOSAL.json and are not re-proposed here. The product/test payload "
            "inside the candidate is the R04 payload already proposed in "
            "R0104_MERGE_PROPOSAL.json and the packaging already proposed in "
            "B02_MERGE_PROPOSAL.json; nothing is re-proposed here. Proposal only: nothing in "
            "this file has been applied to the original project. All seven gates remain "
            "closed; the original merge stays blocked until an explicit human release."
        ),
        "action_level_gate_model": ACTION_LEVEL_GATE_MODEL,
        "frozen_evidence_never_touched": FROZEN,
        "gate_state_at_generation": ledger,
        "counts": {
            "entries": len(entries),
            "entries_requiring_release": sum(1 for e in entries if e["release_required"]),
            "staging_only_entries": sum(1 for e in entries if not e["release_required"]),
            "new_files_vs_parent": manifest["counts"]["new_files_added_by_b05"],
            "edited_files_rewritten": manifest["counts"]["edited_files_rewritten_by_b05"],
        },
        "entries": entries,
        "not_merged": True,
        "requirements_for_merge": [
            "explicit human release opening original_paths_released with an explicit scope",
            "apply the three release-required entries: add "
            "examdata/src/examdata/integration/adapters/active_owner.py, install the B05 "
            "bytes at examdata/src/examdata/integration/api/dataset.py (superseding R0104 "
            "RP-0005) and at examdata/src/examdata/integration/api/app.py (superseding A14 "
            "MM-0015); every entry is add_file semantics because the integration package is "
            "new relative to the original project",
            "verify the candidate tree digest (the container entry's staged_sha256_after, "
            "recomputed with the recorded rule) immediately before any original write",
            "apply the B04-proposed composition hook and the shared-application "
            "registration of the staged v2 routes per B04_MERGE_PROPOSAL.json (not "
            "re-proposed here)",
            "re-run the isolated staged suite against the frozen B05 candidate before any "
            "original write, and re-run the B05 route probe plus the suite against the "
            "merged tree afterwards",
        ],
    }

    rollback = {
        "proposal_version": "b05-rollback-proposal/1",
        "packet": "B05",
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
                "staged_file_changes": "the one added module and the two rewritten modules "
                "live only inside the candidate tree: the container tree delete removes "
                "them; per entry, a rewrite is reversed by restoring the parent's staged "
                "bytes (sha256_to_restore)",
            },
            "original_level": {
                "merged_add_file": "delete_file at the proposed target, and only if its "
                "sha256 still equals sha256_at_proposal",
                "merged_staged_file_rewrite": "delete_file at the proposed target, and only "
                "if its sha256 still equals sha256_at_proposal; the superseded A14/R0104 "
                "staged versions are never restored because the target never existed in the "
                "original project",
            },
            "never": [
                "never touch docs/integration/execution/evidence/**",
                "never touch integration-staging/runtime/phase-b/** sealed transcripts",
                "never touch the frozen R04 candidate under r0104-repair-20261006/candidates/**",
                "never touch the frozen B02 candidate under b02-rehearsal-20261006/candidates/**",
                "never touch the frozen B03 candidate under b03-rehearsal-2026-10-07/candidates/**",
                "never touch the frozen B04 candidate under b04-rehearsal-2026-10-07/candidates/**",
                "never restore the live execution ledger from a private copy",
            ],
        },
        "guards": [
            "verify the resolved absolute path and its sha256 (or tree digest) before any delete",
            "no delete ever targets a protected original in Phase B private rehearsal",
            "planned original writes are reversible only after the human release",
            "the two rewritten targets never existed in the original project; their "
            "original-level reversal is a delete, never a restore of the superseded staged "
            "versions",
            "all seven gates remain closed during rollback",
        ],
        "counts": {
            "entries": len(entries),
            "staging_level": {
                "reversible_by_tree_delete": sum(
                    1 for e in entries if e["kind"] == "staging_candidate_tree"
                ),
                "entries_removed_with_the_tree": sum(
                    1 for e in entries if e["kind"] != "staging_candidate_tree"
                ),
            },
            "original_level": {
                "reversible_by_target_delete": sum(
                    1 for e in entries if e["proposed_target"]
                ),
                "reversible_by_restore_base": 0,
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
                "staging_level_reversal": (
                    "delete the candidate tree, and only if its current tree digest still "
                    "equals sha256_at_proposal"
                    if e["kind"] == "staging_candidate_tree"
                    else "remove the staged file; the candidate then differs from its "
                    "recorded digest and is rebuilt from the parent if needed"
                    if e["kind"] == "new_file"
                    else "restore the parent's staged bytes (sha256_to_restore) inside the "
                    "candidate; the candidate itself stays private"
                ),
                "original_level_reversal": (
                    "not applicable: no original-project target proposed"
                    if not e["proposed_target"]
                    else "delete_file at the proposed target, and only if its sha256 still "
                    "equals sha256_at_proposal; never restore a sealed snapshot"
                    if e["kind"] == "new_file"
                    else "delete_file at the proposed target, and only if its sha256 still "
                    "equals sha256_at_proposal; the superseded A14/R0104 staged versions are "
                    "never restored because the target never existed in the original project"
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
        "# B05 merge proposal (private rehearsal only)",
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
        f"- B05 adds {m['counts']['new_files_vs_parent']} new file and rewrites "
        f"{m['counts']['edited_files_rewritten']} carried modules relative to the parent "
        "(the active-owner seam; everything else is a byte-identical carry of B04)",
        f"- A14 merge map byte-unchanged: `{m['derived_from']['a14_merge_map_byte_unchanged']}`",
        "",
        "## Digest and cross-reference checks",
        "",
        "| Check | Result |",
        "| --- | --- |",
        f"| candidate tree re-verified from disk | `{m['digest_checks']['candidate_tree_reverified']}` |",
        f"| parent tree re-verified from disk | `{m['digest_checks']['parent_tree_reverified']}` |",
        f"| matches B04 merge proposal's derived_from | "
        f"`{m['digest_checks']['b04_merge_crossref_matches']}` |",
        f"| new module matches the tooling source | "
        f"`{m['digest_checks']['new_module_source_matches']}` |",
        f"| edited files match the tooling sources | "
        f"`{m['digest_checks']['edited_files_source_matches']}` |",
        f"| new files vs parent exactly the seam module | "
        f"`{m['digest_checks']['new_files_exactly_one_vs_parent']}` |",
        f"| only the two edited files changed vs parent | "
        f"`{m['digest_checks']['only_the_two_edited_files_changed_vs_parent']}` |",
        f"| A14/R0104 supersession chains | "
        f"`{m['digest_checks']['supersession_chains_match']}` |",
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
        "# B05 rollback proposal (private rehearsal only)",
        "",
        f"Generated: {r['generated_at']}  ",
        f"Status: `{r['status']}`  ",
        f"Entries: {r['counts']['entries']} "
        f"(staging level: {r['counts']['staging_level']['reversible_by_tree_delete']} tree "
        f"delete, {r['counts']['staging_level']['entries_removed_with_the_tree']} removed "
        f"with the tree; original level: "
        f"{r['counts']['original_level']['reversible_by_target_delete']} target delete, "
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
    write_json(os.path.join(OUT, "B05_MERGE_PROPOSAL.json"), merge)
    write_json(os.path.join(OUT, "B05_ROLLBACK_PROPOSAL.json"), rollback)
    write_text(os.path.join(OUT, "B05_MERGE_PROPOSAL.md"), merge_md(merge))
    write_text(os.path.join(OUT, "B05_ROLLBACK_PROPOSAL.md"), rollback_md(rollback))
    print(json.dumps(merge["counts"], ensure_ascii=False))
    print(json.dumps(rollback["counts"], ensure_ascii=False))
    print(json.dumps(merge["gate_state_at_generation"]["gates"], ensure_ascii=False))
    print(json.dumps({k: v for k, v in merge["digest_checks"].items()
                      if k not in ("note", "supersession_chain_detail")},
                     ensure_ascii=False))
    failed_checks = [k for k, v in merge["digest_checks"].items()
                     if k not in ("note", "supersession_chain_detail") and not v]
    if failed_checks:
        print(f"ERROR: digest checks failed: {failed_checks}", file=sys.stderr)
        return 1
    if not merge["gate_state_at_generation"]["all_closed"]:
        print("ERROR: a gate is open", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
