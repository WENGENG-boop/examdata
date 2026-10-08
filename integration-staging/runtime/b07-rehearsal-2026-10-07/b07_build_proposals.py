"""Build the B07 merge/rollback proposals.

Proposal only: nothing is merged, deployed or reverted. Every hash is computed
from the files on disk, and every entry is derived from the B07 candidate
manifest, the B01 merge map, the A14 merge map, the R0104 merge proposal, the
B05 merge proposal and the B06 merge proposal, so nothing is typed by hand
(the values that cannot be recomputed in Phase B are mirrored verbatim from
the frozen records because the original tree is never read here).

B07 integrates jobs, coverage and diagnostics: relative to its parent (the B06
frontend candidate) it rewrites two carried modules - ``api/app.py`` (coverage
and jobs route wiring with sanitized public diagnostics) and ``api/dataset.py``
(the read-only operations projections) - and adds twelve operations files: the
new modules ``src/examdata/integration/operations/jobs.py`` and ``published.py``
(read-only views over a configured operations root) plus the ten-file synthetic
``operations-root`` fixture subtree under
``fixtures/synthetic/operations/operations-root/``. The two module rewrites
supersede the bytes recorded by B06_MERGE_PROPOSAL.json BP-0002 (app.py) and
BP-0003 (dataset.py). The B01 records MM-0221..MM-0228 map the flat operations
fixtures from integration-staging/fixtures/synthetic/operations into the
original test-fixtures directory (deferred_pending_release, add_file); the B07
fixture entries extend the same directory mapping under the new operations-root/
subtree, and MM-0043..MM-0045 fix the operations package target convention.
The candidate container itself stays staging-only.
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
CANDIDATE = os.path.join(RUN, "candidates", "b07-operations-v1")
OUT = os.path.join(WS, "docs", "integration", "execution")

CST = timezone(timedelta(hours=8))

CANDIDATE_MANIFEST = os.path.join(CANDIDATE, "B07_CANDIDATE_MANIFEST.json")
CANDIDATE_MANIFEST_NAME = "B07_CANDIDATE_MANIFEST.json"
PARENT = os.path.join(
    WS, "integration-staging", "runtime", "b06-rehearsal-2026-10-07", "candidates",
    "b06-frontend-v1",
)
PARENT_MANIFEST_NAME = "B06_CANDIDATE_MANIFEST.json"
PARENT_MANIFEST = os.path.join(PARENT, PARENT_MANIFEST_NAME)
A14_MAP = os.path.join(OUT, "A14_MERGE_MAP.json")
LEDGER = os.path.join(OUT, "execution-ledger.json")
R0104_MERGE = os.path.join(OUT, "R0104_MERGE_PROPOSAL.json")
B05_MERGE = os.path.join(OUT, "B05_MERGE_PROPOSAL.json")
B06_MERGE = os.path.join(OUT, "B06_MERGE_PROPOSAL.json")
B01_MAP = os.path.join(
    OUT, "evidence", "B01", "b00b01-20261006T132400", "B01_MERGE_MAP.json",
)
SOURCE_EDITS_DIFF = os.path.join(RUN, "evidence", "source_edits.diff")
FIXTURE_ROOT = os.path.join(RUN, "tools", "operations-root")

EDITED_SOURCES = {
    "src/examdata/integration/api/app.py": os.path.join(RUN, "tools", "app.py"),
    "src/examdata/integration/api/dataset.py": os.path.join(RUN, "tools", "dataset.py"),
}
NEW_MODULE_SOURCES = {
    "src/examdata/integration/operations/jobs.py": os.path.join(RUN, "tools", "jobs.py"),
    "src/examdata/integration/operations/published.py": os.path.join(
        RUN, "tools", "published.py"
    ),
}
FIXTURE_CHANGES = {
    "fixtures/synthetic/operations/operations-root/PROVENANCE.json":
        "install_operations_root_fixture_provenance",
    "fixtures/synthetic/operations/operations-root/README.md":
        "install_operations_root_readme",
    "fixtures/synthetic/operations/operations-root/cie-batch-8888-stale/checkpoint.json":
        "install_operations_root_checkpoint_cie_batch_8888_stale",
    "fixtures/synthetic/operations/operations-root/cie-batch-8888/checkpoint.json":
        "install_operations_root_checkpoint_cie_batch_8888",
    "fixtures/synthetic/operations/operations-root/cie-location-batch/checkpoint.json":
        "install_operations_root_checkpoint_cie_location_batch",
    "fixtures/synthetic/operations/operations-root/expected-manifest.json":
        "install_operations_root_expected_manifest",
    "fixtures/synthetic/operations/operations-root/run-ok-stale/checkpoint.json":
        "install_operations_root_checkpoint_run_ok_stale",
    "fixtures/synthetic/operations/operations-root/run-ok/checkpoint.json":
        "install_operations_root_checkpoint_run_ok",
    "fixtures/synthetic/operations/operations-root/run-partial/checkpoint.json":
        "install_operations_root_checkpoint_run_partial",
    "fixtures/synthetic/operations/operations-root/unsupported/checkpoint.json":
        "install_operations_root_checkpoint_unsupported",
}
EXPECTED_B01_FIXTURE_IDS = [f"MM-{n:04d}" for n in range(221, 229)]
EXPECTED_B01_OPERATION_IDS = [f"MM-{n:04d}" for n in range(43, 46)]
EXPECTED_TARGET_PREFIX_FIXTURES = "examdata/tests/integration/fixtures/synthetic/operations/"
EXPECTED_TARGET_PREFIX_OPERATIONS = "examdata/src/examdata/integration/operations/"

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
    "integration-staging/runtime/b06-rehearsal-2026-10-07/candidates/b06-frontend-v1/**",
    "integration-staging/runtime/b07-rehearsal-2026-10-07/candidates/b07-operations-v1/**",
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


def b05_entry(entry_id: str) -> dict:
    for entry in load_json(B05_MERGE).get("entries", []):
        if entry.get("id") == entry_id:
            return entry
    raise ValueError(f"B05 entry {entry_id} not found in the merge proposal")


def b06_entry(entry_id: str) -> dict:
    for entry in load_json(B06_MERGE).get("entries", []):
        if entry.get("id") == entry_id:
            return entry
    raise ValueError(f"B06 entry {entry_id} not found in the merge proposal")


def digest_checks(manifest: dict) -> dict:
    recorded_parent = manifest["lineage"]["parent_tree"]
    recorded_candidate = manifest["candidate_tree"]
    parent_now = tree_digest(PARENT, (PARENT_MANIFEST_NAME,))
    candidate_now = tree_digest(CANDIDATE, (CANDIDATE_MANIFEST_NAME,))

    b06_derived = load_json(B06_MERGE).get("derived_from", {})
    b06_crossref = bool(b06_derived) and (
        b06_derived.get("candidate_manifest_sha256") == sha256_file(PARENT_MANIFEST)
        and (b06_derived.get("candidate_tree") or {}).get("sha256")
        == recorded_parent["sha256"]
    )

    edited_by_path = {e["path"]: e for e in manifest.get("edited_files", [])}
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

    operations = manifest.get("operations", {})
    new_modules = operations.get("new_modules", [])
    module_checks: dict[str, bool] = {}
    for nm in new_modules:
        path = nm["path"]
        cand_file = os.path.join(CANDIDATE, path)
        source = NEW_MODULE_SOURCES.get(path, nm.get("source", ""))
        module_checks[path] = bool(
            os.path.isfile(cand_file)
            and os.path.isfile(source)
            and sha256_file(cand_file) == nm.get("written_sha256")
            and sha256_file(source) == nm.get("source_sha256")
            and nm.get("source_sha256") == nm.get("written_sha256")
        )

    fixture_files = operations.get("fixture_files", [])
    fixture_root_ok = rel(operations.get("fixture_root", "")) == rel(FIXTURE_ROOT)
    fixture_checks: dict[str, bool] = {}
    for ff in fixture_files:
        path = ff["path"]
        cand_file = os.path.join(CANDIDATE, path)
        src_file = os.path.join(FIXTURE_ROOT, path.split("operations-root/", 1)[1])
        fixture_checks[path] = bool(
            os.path.isfile(cand_file)
            and os.path.isfile(src_file)
            and sha256_file(cand_file) == ff.get("written_sha256")
            and sha256_file(src_file) == ff.get("source_sha256")
            and ff.get("source_sha256") == ff.get("written_sha256")
        )

    prov_checks: dict[str, bool] = {}
    for rec in operations.get("provenance_records", []):
        path = rec["path"]
        cand_file = os.path.join(CANDIDATE, path)
        src_file = os.path.join(FIXTURE_ROOT, path.split("operations-root/", 1)[1])
        prov_checks[path] = bool(
            os.path.isfile(cand_file)
            and os.path.isfile(src_file)
            and sha256_file(cand_file) == rec.get("candidate_sha256")
            and sha256_file(src_file) == rec.get("staged_sha256")
            and rec.get("recorded_sha256") == rec.get("staged_sha256")
            == rec.get("candidate_sha256")
        )

    candidate_files = file_set(CANDIDATE) - {CANDIDATE_MANIFEST_NAME}
    parent_files = file_set(PARENT)
    added_vs_parent = sorted(candidate_files - parent_files)
    changed = sorted(
        r for r in parent_files & candidate_files
        if sha256_file(os.path.join(PARENT, r))
        != sha256_file(os.path.join(CANDIDATE, r))
    )
    expected_new = sorted(
        [nm["path"] for nm in new_modules] + [ff["path"] for ff in fixture_files]
    )

    b01_map = load_json(B01_MAP)
    b01_by_id = {e["id"]: e for e in b01_map.get("entries", [])}
    fixture_precedent_ok = all(
        eid in b01_by_id
        and b01_by_id[eid].get("kind") == "new_file"
        and b01_by_id[eid].get("phase_b_action") == "add_file"
        and b01_by_id[eid].get("b01_disposition") == "deferred_pending_release"
        and b01_by_id[eid]["staged_path"].startswith(
            "integration-staging/fixtures/synthetic/operations/"
        )
        and b01_by_id[eid]["proposed_target"].startswith(EXPECTED_TARGET_PREFIX_FIXTURES)
        for eid in EXPECTED_B01_FIXTURE_IDS
    )
    operations_precedent_ok = all(
        eid in b01_by_id
        and b01_by_id[eid].get("kind") == "new_file"
        and b01_by_id[eid].get("phase_b_action") == "add_file"
        and b01_by_id[eid].get("b01_disposition") == "deferred_pending_release"
        and b01_by_id[eid]["proposed_target"].startswith(EXPECTED_TARGET_PREFIX_OPERATIONS)
        for eid in EXPECTED_B01_OPERATION_IDS
    )
    b01_text = json.dumps(b01_map, ensure_ascii=False)
    a14_text = json.dumps(load_json(A14_MAP), ensure_ascii=False)
    no_prior_operations_root = bool(
        "operations-root" not in b01_text
        and "jobs.py" not in b01_text
        and "published.py" not in b01_text
        and "operations-root" not in a14_text
        and "jobs.py" not in a14_text
        and "published.py" not in a14_text
    )

    a14_dataset = a14_entry("MM-0017")
    a14_app = a14_entry("MM-0015")
    rp0005 = r0104_entry("RP-0005")
    bp0003 = b05_entry("BP-0003")
    bp0004 = b05_entry("BP-0004")
    b06_bp0002 = b06_entry("BP-0002")
    b06_bp0003 = b06_entry("BP-0003")
    dataset_edit = edited_by_path["src/examdata/integration/api/dataset.py"]
    app_edit = edited_by_path["src/examdata/integration/api/app.py"]
    supersession = {
        "dataset_chain": bool(
            a14_dataset.get("staged_sha256") == rp0005.get("staged_sha256_before")
            and rp0005.get("staged_sha256_after") == bp0003.get("staged_sha256_before")
            and bp0003.get("staged_sha256_after") == b06_bp0003.get("staged_sha256_before")
            and b06_bp0003.get("staged_sha256_after") == dataset_edit.get("parent_sha256")
            and rp0005.get("proposed_target") == a14_dataset.get("proposed_target")
            == "examdata/src/examdata/integration/api/dataset.py"
            and bp0003.get("proposed_target") == b06_bp0003.get("proposed_target")
            == "examdata/src/examdata/integration/api/dataset.py"
        ),
        "app_chain": bool(
            a14_app.get("staged_sha256") == bp0004.get("staged_sha256_before")
            and bp0004.get("staged_sha256_after") == b06_bp0002.get("staged_sha256_before")
            and b06_bp0002.get("staged_sha256_after") == app_edit.get("parent_sha256")
            and a14_app.get("proposed_target") == bp0004.get("proposed_target")
            == "examdata/src/examdata/integration/api/app.py"
            and b06_bp0002.get("proposed_target")
            == "examdata/src/examdata/integration/api/app.py"
        ),
    }

    b06_a14_unchanged = b06_derived.get("a14_merge_map_sha256") == sha256_file(A14_MAP)

    return {
        "candidate_tree_reverified": (
            candidate_now["files"] == recorded_candidate["files"]
            and candidate_now["sha256"] == recorded_candidate["sha256"]
        ),
        "parent_tree_reverified": (
            parent_now["files"] == recorded_parent["files"]
            and parent_now["sha256"] == recorded_parent["sha256"]
        ),
        "b06_merge_crossref_matches": b06_crossref,
        "edited_files_source_matches": all(edited_checks.values()),
        "new_files_exactly_twelve_vs_parent": (
            len(added_vs_parent) == 12 and added_vs_parent == expected_new
        ),
        "only_the_two_edited_files_changed_vs_parent": changed == sorted(EDITED_SOURCES),
        "new_modules_match_sources": bool(
            len(new_modules) == 2 and all(module_checks.values())
        ),
        "operations_fixture_files_match_sources": bool(
            len(fixture_files) == 10 and fixture_root_ok and all(fixture_checks.values())
        ),
        "operations_provenance_records_match": bool(
            len(operations.get("provenance_records", [])) == 9
            and all(prov_checks.values())
        ),
        "operations_target_conventions_match_b01": bool(
            fixture_precedent_ok and operations_precedent_ok and no_prior_operations_root
        ),
        "supersession_chains_match": all(supersession.values()),
        "supersession_chain_detail": supersession,
        "operations_check_detail": {
            "new_modules": module_checks,
            "fixture_root_matches_staging_tools": fixture_root_ok,
            "fixture_files": fixture_checks,
            "provenance_records": prov_checks,
            "b01_fixture_precedent": fixture_precedent_ok,
            "b01_operations_precedent": operations_precedent_ok,
            "no_prior_operations_root_or_new_modules_in_b01_or_a14": no_prior_operations_root,
            "b06_a14_anchor_matches": b06_a14_unchanged,
        },
        "note": "tree digests recomputed from disk at proposal time with the recorded rule "
        "(sha256 over 'path\\0sha256\\n', sorted, __pycache__/.pytest_cache skipped, the named "
        "manifest excluded); the B06 cross-reference checks this candidate's recorded parent "
        "against B06_MERGE_PROPOSAL.json's derived_from; the operations checks compare the "
        "candidate files against the staging-owned tools/operations-root sources and the "
        "frozen B01 records only (the original tree is never read); the file-set comparison "
        "excludes only the candidate's own manifest (the child carries byte-identical copies "
        "of the parent's files, including the B06 manifest, so they appear in both sets); the "
        "supersession chains re-verify the B05/R0104/A14 and B06 records that the two "
        "rewritten modules supersede (dataset: A14 MM-0017 -> R0104 RP-0005 -> B05 BP-0003 -> "
        "B06 BP-0003 -> B07; app: A14 MM-0015 -> B05 BP-0004 -> B06 BP-0002 -> B07)",
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
    b01_map = load_json(B01_MAP)
    b01_sha = sha256_file(B01_MAP)
    checks = digest_checks(manifest)

    b06_derived = load_json(B06_MERGE).get("derived_from", {})
    a14_unchanged = b06_derived.get("a14_merge_map_sha256") == a14_sha

    edited_by_path = {e["path"]: e for e in manifest["edited_files"]}
    operations = manifest["operations"]
    new_modules = {nm["path"]: nm for nm in operations["new_modules"]}
    fixture_files = operations["fixture_files"]

    app_edit = edited_by_path["src/examdata/integration/api/app.py"]
    dataset_edit = edited_by_path["src/examdata/integration/api/dataset.py"]
    candidate_rel = rel(CANDIDATE)

    rewrite_reversal = (
        "delete_file at the proposed target, and only if the target's current sha256 still "
        "equals staged_sha256_after; the superseded staged versions are never restored because "
        "the target never existed in the original project"
    )

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
            "original_level_reversal_kind": "none",
            "restore_base_sha256": None,
            "sha_note": "the before digest covers the parent (B06) file set with B06's own "
            "manifest excluded (its digest rule); the after digest covers the candidate file "
            "set with B07's own manifest excluded; both use the same function and rule",
            "status": "proposal_only_not_merged",
        },
        {
            "id": "BP-0002",
            "change": "rewrite_integration_app_for_operations_routes_and_diagnostics",
            "staged_path": rel(os.path.join(CANDIDATE, "src/examdata/integration/api/app.py")),
            "staged_sha256_before": app_edit["parent_sha256"],
            "staged_sha256_after": app_edit["written_sha256"],
            "kind": "staged_file_rewrite",
            "proposed_target": "examdata/src/examdata/integration/api/app.py",
            "proposed_target_origin": "A14_MERGE_MAP.json MM-0015 via B05_MERGE_PROPOSAL.json "
            "BP-0004 and B06_MERGE_PROPOSAL.json BP-0002; the B07 bytes supersede the "
            "unapplied B06 bytes",
            "phase_b_action": "add_file at the proposed target with the B07 bytes (supersedes "
            "the unapplied B06 proposal BP-0002; the whole integration package is new relative "
            "to the original project; there is no existing original file to edit; A14 observed "
            "the target as not existing)",
            "reversal": rewrite_reversal,
            "supersedes": {
                "proposal": "B06_MERGE_PROPOSAL.json BP-0002",
                "superseded_staged_sha256_after": app_edit["parent_sha256"],
                "chain": "A14 MM-0015 -> B05 BP-0004 -> B06 BP-0002 -> B07",
            },
            "gates_required_for_this_action": ["original_paths_released"],
            "release_required": True,
            "original_level_reversal_kind": "delete_file",
            "restore_base_sha256": None,
            "sha_note": "staged_sha256_before is the B06 bytes this rewrite replaces; the chain "
            "is re-verified in digest_checks.supersession_chain_detail",
            "status": "proposal_only_not_merged",
        },
        {
            "id": "BP-0003",
            "change": "rewrite_integration_dataset_for_operations_projections",
            "staged_path": rel(
                os.path.join(CANDIDATE, "src/examdata/integration/api/dataset.py")
            ),
            "staged_sha256_before": dataset_edit["parent_sha256"],
            "staged_sha256_after": dataset_edit["written_sha256"],
            "kind": "staged_file_rewrite",
            "proposed_target": "examdata/src/examdata/integration/api/dataset.py",
            "proposed_target_origin": "A14_MERGE_MAP.json MM-0017 via "
            "R0104_MERGE_PROPOSAL.json RP-0005, B05_MERGE_PROPOSAL.json BP-0003 and "
            "B06_MERGE_PROPOSAL.json BP-0003; the B07 bytes supersede the unapplied B06 bytes",
            "phase_b_action": "add_file at the proposed target with the B07 bytes (supersedes "
            "the unapplied B06 proposal BP-0003; the whole integration package is new relative "
            "to the original project; there is no existing original file to edit; A14 observed "
            "the target as not existing)",
            "reversal": rewrite_reversal,
            "supersedes": {
                "proposal": "B06_MERGE_PROPOSAL.json BP-0003",
                "superseded_staged_sha256_after": dataset_edit["parent_sha256"],
                "chain": "A14 MM-0017 -> R0104 RP-0005 -> B05 BP-0003 -> B06 BP-0003 -> B07",
            },
            "gates_required_for_this_action": ["original_paths_released"],
            "release_required": True,
            "original_level_reversal_kind": "delete_file",
            "restore_base_sha256": None,
            "sha_note": "staged_sha256_before is the B06 bytes this rewrite replaces; the chain "
            "is re-verified in digest_checks.supersession_chain_detail",
            "status": "proposal_only_not_merged",
        },
    ]

    module_entries = [
        (
            "BP-0004",
            "src/examdata/integration/operations/jobs.py",
            "add_operations_jobs_module_read_only_views",
            "read-only job views over a configured operations root: stopped jobs stay stopped "
            "and nothing is resumed or written back",
        ),
        (
            "BP-0005",
            "src/examdata/integration/operations/published.py",
            "add_operations_published_module_sanitized_projections",
            "sanitized published-coverage projections: derived statuses and percentages with "
            "no raw paths, keys or secrets on any leaf",
        ),
    ]
    for entry_id, path, change, purpose in module_entries:
        nm = new_modules[path]
        entries.append({
            "id": entry_id,
            "change": change,
            "staged_path": rel(os.path.join(CANDIDATE, path)),
            "staged_sha256_before": None,
            "staged_sha256_after": nm["written_sha256"],
            "kind": "new_file",
            "proposed_target": f"examdata/{path}",
            "proposed_target_origin": "B01_MERGE_MAP.json MM-0043..MM-0045 fixed the target "
            "directory convention examdata/src/examdata/integration/operations/ for the "
            "operations package; this module is new since A14/B01 and has no record of its own",
            "phase_b_action": f"add_file at the proposed target with the B07 candidate bytes "
            f"({purpose})",
            "reversal": "delete_file at the proposed target, and only if the target's current "
            "sha256 still equals staged_sha256_after; never restore a sealed snapshot",
            "gates_required_for_this_action": ["original_paths_released"],
            "release_required": True,
            "original_level_reversal_kind": "delete_file",
            "restore_base_sha256": None,
            "sha_note": "new module relative to the A14/B01 records and to the B06 parent "
            "candidate (no B01/A14 record mentions it); bytes verified against the staging "
            "tools copy in digest_checks",
            "status": "proposal_only_not_merged",
        })

    for i, ff in enumerate(fixture_files):
        path = ff["path"]
        rel_within_root = path.split("operations-root/", 1)[1]
        entries.append({
            "id": f"BP-{6 + i:04d}",
            "change": FIXTURE_CHANGES[path],
            "staged_path": rel(os.path.join(CANDIDATE, path)),
            "staged_sha256_before": None,
            "staged_sha256_after": ff["written_sha256"],
            "kind": "new_file",
            "proposed_target": f"examdata/tests/integration/fixtures/synthetic/operations/"
            f"operations-root/{rel_within_root}",
            "proposed_target_origin": "B01_MERGE_MAP.json MM-0221..MM-0228 mapped "
            "integration-staging/fixtures/synthetic/operations/ into "
            "examdata/tests/integration/fixtures/synthetic/operations/ "
            "(deferred_pending_release, add_file); this file extends the same mapping under "
            "the new operations-root/ subtree and has no record of its own",
            "phase_b_action": "add_file at the proposed target with the B07 candidate bytes "
            "(labelled synthetic operations fixture)",
            "reversal": "delete_file at the proposed target, and only if the target's current "
            "sha256 still equals staged_sha256_after; never restore a sealed snapshot",
            "staged_source": {
                "staged_path": rel(os.path.join(FIXTURE_ROOT, rel_within_root)),
                "staged_sha256": ff["source_sha256"],
                "note": "staging-owned synthetic fixture; new relative to the B07 parent (B06) "
                "candidate; bytes unchanged between tools/operations-root and the candidate "
                "(verified in digest_checks)",
            },
            "gates_required_for_this_action": ["original_paths_released"],
            "release_required": True,
            "original_level_reversal_kind": "delete_file",
            "restore_base_sha256": None,
            "sha_note": "synthetic operations fixture (labelled; the only credential-shaped "
            "value anywhere is the fixture-labelled synthetic control string); no original "
            "target is recorded for it and none existed at A14/B01",
            "status": "proposal_only_not_merged",
        })

    merge = {
        "proposal_version": "b07-merge-proposal/1",
        "packet": "B07",
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
            "b05_merge_proposal": rel(B05_MERGE),
            "b05_merge_proposal_sha256": sha256_file(B05_MERGE),
            "b06_merge_proposal": rel(B06_MERGE),
            "b06_merge_proposal_sha256": sha256_file(B06_MERGE),
            "b06_merge_crossref_matches": checks["b06_merge_crossref_matches"],
            "b01_merge_map": rel(B01_MAP),
            "b01_merge_map_sha256": b01_sha,
            "b01_merge_map_sha256_note": "observed at proposal time; the frozen anchor recorded "
            "in the execution ledger is the A14 map sha256 (29940a0b...), not the B01 map, so "
            "this value is recorded for traceability only and is not compared against a frozen "
            "expectation",
            "a14_merge_map": rel(A14_MAP),
            "a14_merge_map_sha256": a14_sha,
            "a14_merge_map_byte_unchanged": a14_unchanged,
            "a14_byte_anchor_matches": checks["operations_check_detail"]["b06_a14_anchor_matches"],
            "source_edits_diff": rel(SOURCE_EDITS_DIFF),
            "source_edits_diff_sha256": sha256_file(SOURCE_EDITS_DIFF)
            if os.path.isfile(SOURCE_EDITS_DIFF) else None,
        },
        "digest_checks": checks,
        "scope_note": (
            "B07 integrates jobs, coverage and diagnostics: relative to its parent (the B06 "
            "frontend candidate) it rewrites two carried modules - "
            "src/examdata/integration/api/app.py (coverage and jobs route wiring with sanitized "
            "public diagnostics) and src/examdata/integration/api/dataset.py (read-only "
            "operations projections) - and adds twelve operations files: the new modules "
            "src/examdata/integration/operations/jobs.py and "
            "src/examdata/integration/operations/published.py (read-only views over a "
            "configured operations root; no resume, no write-back) plus the ten-file synthetic "
            "operations-root fixture subtree under "
            "fixtures/synthetic/operations/operations-root/. Everything else in the candidate "
            "is a byte-identical carry of B06. The staged bytes of the two rewritten modules "
            "supersede the bytes recorded by B06_MERGE_PROPOSAL.json BP-0002 (app.py) and "
            "BP-0003 (dataset.py), which themselves superseded B05_MERGE_PROPOSAL.json "
            "BP-0004/BP-0003 and, behind them, A14 MM-0015 / A14 MM-0017 via R0104 RP-0005; "
            "the whole integration package is new relative to the original project, so every "
            "release-required module entry is add_file semantics. The ten fixture entries "
            "extend the B01 MM-0221..MM-0228 directory mapping under the new operations-root/ "
            "subtree (all deferred_pending_release in B01); the two operations modules follow "
            "the B01 MM-0043..MM-0045 target convention; no B01 or A14 record mentions "
            "operations-root, jobs.py or published.py. B01 performed no reconciliation "
            "(three_way=false, gate was closed) and this proposal performs none either - it "
            "records the deferred state against the B07 candidate bytes; the eighteen "
            "release-required B06 entries remain as filed in B06_MERGE_PROPOSAL.json and are "
            "not re-proposed here. The active-owner seam (B05 BP-0002), the composition hook "
            "(B04), the product/test payload (R04) and the packaging (B02) remain as proposed "
            "and are not re-proposed. Proposal only: nothing in this file has been applied to "
            "the original project. All seven gates remain closed; the original merge stays "
            "blocked until an explicit human release."
        ),
        "action_level_gate_model": ACTION_LEVEL_GATE_MODEL,
        "frozen_evidence_never_touched": FROZEN,
        "gate_state_at_generation": ledger,
        "counts": {
            "entries": len(entries),
            "entries_requiring_release": sum(1 for e in entries if e["release_required"]),
            "staging_only_entries": sum(1 for e in entries if not e["release_required"]),
            "new_files_vs_parent": manifest["counts"]["new_files_added_by_b07"],
            "edited_files_rewritten": manifest["counts"]["edited_files_rewritten_by_b07"],
        },
        "entries": entries,
        "not_merged": True,
        "requirements_for_merge": [
            "explicit human release opening original_paths_released with an explicit scope; "
            "the records carried from B01 (deferred_pending_release) become actionable only "
            "under that release; B07 does not re-propose the eighteen release-required B06 "
            "entries - the human release decision covers B06_MERGE_PROPOSAL.json and this "
            "B07 delta together, or the affected entries stay deferred",
            "apply the two release-required module rewrites (add_file semantics; the whole "
            "integration package is new relative to the original project): install the B07 "
            "bytes at examdata/src/examdata/integration/api/app.py (superseding the unapplied "
            "B06 proposal BP-0002) and examdata/src/examdata/integration/api/dataset.py "
            "(superseding the unapplied B06 proposal BP-0003)",
            "install the two new operations modules at "
            "examdata/src/examdata/integration/operations/jobs.py and "
            "examdata/src/examdata/integration/operations/published.py (the B01 "
            "MM-0043..MM-0045 target convention)",
            "install the ten release-required operations fixtures under "
            "examdata/tests/integration/fixtures/synthetic/operations/operations-root/ (the "
            "B01 MM-0221..MM-0228 directory mapping extended under the new subtree); the "
            "sibling flat fixture files filed by B01 are untouched by this proposal",
            "re-verify every recorded base before writing and re-verify the candidate tree "
            "digest (the container entry's staged_sha256_after, recomputed with the recorded "
            "rule) immediately before any original write",
            "keep the merged operations views read-only (no resume, no restart, no write-back "
            "to any operations root) and the public diagnostics sanitized (no raw paths, keys "
            "or secrets) after merge",
            "re-run the isolated staged suite and the B07 route probe against the frozen B07 "
            "candidate before any original write, and re-run both against the merged tree "
            "afterwards",
            "the operations-root fixtures are labelled synthetic controls: the merged product "
            "must never point a default configuration at a real operations root without the "
            "applicable release, and no real credential may be staged or fabricated",
        ],
    }

    rollback = {
        "proposal_version": "b07-rollback-proposal/1",
        "packet": "B07",
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
                "staged_file_changes": "the twelve added operations files and the two rewritten "
                "modules live only inside the candidate tree: the container tree delete "
                "removes them; the two rewritten modules can alternatively be reversed by "
                "restoring the parent's staged bytes (staging_sha256_to_restore)",
            },
            "original_level": {
                "merged_add_file": "delete_file at the proposed target, and only if its "
                "sha256 still equals sha256_at_proposal",
                "rewritten_modules_note": "the two rewritten integration modules (app.py, "
                "dataset.py) never existed in the original project (A14 observed the targets "
                "as not existing), so their original-level reversal is a delete, never a "
                "restore of the superseded staged versions",
                "b06_entries_note": "the eighteen release-required B06 entries (frontend files "
                "and the view.py rewrite) are reversed exactly as recorded in "
                "B06_ROLLBACK_PROPOSAL.json; B07 does not re-propose or re-state them",
            },
            "never": [
                "never touch docs/integration/execution/evidence/**",
                "never touch integration-staging/runtime/phase-b/** sealed transcripts",
                "never touch the frozen R04 candidate under r0104-repair-20261006/candidates/**",
                "never touch the frozen B02 candidate under b02-rehearsal-20261006/candidates/**",
                "never touch the frozen B03 candidate under "
                "b03-rehearsal-2026-10-07/candidates/b03-contracts-catalog-v1/**",
                "never touch the frozen B04 candidate under "
                "b04-rehearsal-2026-10-07/candidates/b04-routes-v1/**",
                "never touch the frozen B05 candidate under "
                "b05-rehearsal-2026-10-07/candidates/b05-adapters-v1/**",
                "never touch the frozen B06 candidate under "
                "b06-rehearsal-2026-10-07/candidates/b06-frontend-v1/**",
                "never restore the live execution ledger from a private copy",
            ],
        },
        "guards": [
            "verify the resolved absolute path and its sha256 (or tree digest) before any delete",
            "no delete ever targets a protected original in Phase B private rehearsal",
            "planned original writes are reversible only after the human release",
            "the two rewritten integration modules never existed in the original project; "
            "their original-level reversal is a delete, never a restore of the superseded "
            "staged versions",
            "no B07 entry restores base bytes or reconciles: every release-required B07 change "
            "is an add whose reversal is a guarded delete_file",
            "the eighteen release-required B06 entries keep the reversal semantics recorded in "
            "B06_ROLLBACK_PROPOSAL.json",
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
                "reversible_by_restore_parent_bytes": sum(
                    1 for e in entries
                    if e["kind"] == "staged_file_rewrite" and e["staged_sha256_before"]
                ),
            },
            "original_level": {
                "reversible_by_target_delete": sum(
                    1 for e in entries
                    if e["original_level_reversal_kind"] == "delete_file"
                ),
                "reversible_by_restore_base": sum(
                    1 for e in entries
                    if e["original_level_reversal_kind"] == "restore_base_bytes"
                ),
                "reconciliation_cases": sum(
                    1 for e in entries
                    if e["original_level_reversal_kind"] == "reconciliation_note"
                ),
                "no_original_action": sum(
                    1 for e in entries
                    if e["original_level_reversal_kind"] == "none"
                ),
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
                "staging_sha256_to_restore": (
                    e["staged_sha256_before"] if e["kind"] == "staged_file_rewrite" else None
                ),
                "original_base_sha256": e.get("restore_base_sha256"),
                "staging_level_reversal": (
                    "delete the candidate tree, and only if its current tree digest still "
                    "equals sha256_at_proposal"
                    if e["kind"] == "staging_candidate_tree"
                    else "restore the parent's staged bytes (staging_sha256_to_restore) inside "
                    "the candidate; the candidate itself stays private"
                    if e["staged_sha256_before"]
                    else "remove the staged file; it does not exist in the parent candidate, "
                    "so the candidate then differs from its recorded digest and is rebuilt "
                    "from the parent if needed"
                ),
                "original_level_reversal": (
                    "not applicable: no original-project target proposed"
                    if e["original_level_reversal_kind"] == "none"
                    else e["reversal"]
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
        "# B07 merge proposal (private rehearsal only)",
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
        f"- B07 adds {m['counts']['new_files_vs_parent']} operations files and rewrites "
        f"{m['counts']['edited_files_rewritten']} carried modules relative to the parent (the "
        "operations payload plus the coverage/jobs wiring; everything else is a byte-identical "
        "carry of B06)",
        f"- A14 merge map byte-unchanged: `{m['derived_from']['a14_merge_map_byte_unchanged']}`; "
        f"B01 merge map sha256 (observation): `{m['derived_from']['b01_merge_map_sha256'][:12]}`",
        "",
        "## Digest and cross-reference checks",
        "",
        "| Check | Result |",
        "| --- | --- |",
        f"| candidate tree re-verified from disk | `{m['digest_checks']['candidate_tree_reverified']}` |",
        f"| parent tree re-verified from disk | `{m['digest_checks']['parent_tree_reverified']}` |",
        f"| matches B06 merge proposal's derived_from | "
        f"`{m['digest_checks']['b06_merge_crossref_matches']}` |",
        f"| edited files match the tooling sources | "
        f"`{m['digest_checks']['edited_files_source_matches']}` |",
        f"| new files vs parent exactly the twelve operations files | "
        f"`{m['digest_checks']['new_files_exactly_twelve_vs_parent']}` |",
        f"| only the two edited files changed vs parent | "
        f"`{m['digest_checks']['only_the_two_edited_files_changed_vs_parent']}` |",
        f"| new operations modules match sources (2) | "
        f"`{m['digest_checks']['new_modules_match_sources']}` |",
        f"| operations fixture files match sources (10) | "
        f"`{m['digest_checks']['operations_fixture_files_match_sources']}` |",
        f"| operations provenance records match (9) | "
        f"`{m['digest_checks']['operations_provenance_records_match']}` |",
        f"| operations target conventions match the B01 records | "
        f"`{m['digest_checks']['operations_target_conventions_match_b01']}` |",
        f"| A14/B05/B06 supersession chains | "
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
        "# B07 rollback proposal (private rehearsal only)",
        "",
        f"Generated: {r['generated_at']}  ",
        f"Status: `{r['status']}`  ",
        f"Entries: {r['counts']['entries']} "
        f"(staging level: {r['counts']['staging_level']['reversible_by_tree_delete']} tree "
        f"delete, {r['counts']['staging_level']['entries_removed_with_the_tree']} removed "
        f"with the tree, "
        f"{r['counts']['staging_level']['reversible_by_restore_parent_bytes']} restorable to "
        "parent bytes; original level: "
        f"{r['counts']['original_level']['reversible_by_target_delete']} target delete, "
        f"{r['counts']['original_level']['reversible_by_restore_base']} restore base, "
        f"{r['counts']['original_level']['reconciliation_cases']} reconciliation cases, "
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
    write_json(os.path.join(OUT, "B07_MERGE_PROPOSAL.json"), merge)
    write_json(os.path.join(OUT, "B07_ROLLBACK_PROPOSAL.json"), rollback)
    write_text(os.path.join(OUT, "B07_MERGE_PROPOSAL.md"), merge_md(merge))
    write_text(os.path.join(OUT, "B07_ROLLBACK_PROPOSAL.md"), rollback_md(rollback))
    print(json.dumps(merge["counts"], ensure_ascii=False))
    print(json.dumps(rollback["counts"], ensure_ascii=False))
    print(json.dumps(merge["gate_state_at_generation"]["gates"], ensure_ascii=False))
    non_bool = ("note", "supersession_chain_detail", "operations_check_detail")
    print(json.dumps({k: v for k, v in merge["digest_checks"].items() if k not in non_bool},
                     ensure_ascii=False))
    failed_checks = [k for k, v in merge["digest_checks"].items()
                     if k not in non_bool and not v]
    if failed_checks:
        print(f"ERROR: digest checks failed: {failed_checks}", file=sys.stderr)
        return 1
    counts = merge["counts"]
    if (counts["entries"] != 15 or counts["entries_requiring_release"] != 14
            or counts["staging_only_entries"] != 1 or counts["new_files_vs_parent"] != 12
            or counts["edited_files_rewritten"] != 2):
        print(f"ERROR: unexpected counts {counts}", file=sys.stderr)
        return 1
    if not merge["gate_state_at_generation"]["all_closed"]:
        print("ERROR: a gate is open", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
