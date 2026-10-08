"""Build the B06 merge/rollback proposals.

Proposal only: nothing is merged, deployed or reverted. Every hash is computed
from the files on disk, and every entry is derived from the B06 candidate
manifest, the B01 merge map, the A14 merge map, the R0104 merge proposal and
the B05 merge proposal, so nothing is typed by hand (the values that cannot be
recomputed in Phase B are mirrored verbatim from the frozen records because
the original tree is never read here).

B06 migrates frontend source discovery: relative to its parent (the B05
adapters candidate) it rewrites three carried modules - ``api/app.py`` (the
discovery projection and the resources wiring), ``api/dataset.py`` (the
frontend-shaped query semantics) and ``api/view.py`` - and adds seventeen
files under ``frontend/`` (fifteen staged files byte-for-byte, thirteen of
them carried from the B01/A14 records MM-0229..MM-0241 plus the two staging
PROVENANCE records that B01 excluded from the merge, plus the rewritten
``server.mjs`` and the new ``tests/server.test.mjs``). The three module
rewrites supersede the bytes recorded by B05_MERGE_PROPOSAL.json BP-0004
(app.py), B05_MERGE_PROPOSAL.json BP-0003 via R0104_MERGE_PROPOSAL.json
RP-0005 (dataset.py) and A14_MERGE_MAP.json MM-0022 (view.py). The whole
integration package is new relative to the original project, so every
release-required module entry is add_file semantics. The frontend entries
carry the B01 records (deferred_pending_release / carried_pending_release) and
the B01 planned original edit for frontend/server.mjs. The candidate container
itself stays staging-only.
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
CANDIDATE = os.path.join(RUN, "candidates", "b06-frontend-v1")
OUT = os.path.join(WS, "docs", "integration", "execution")

CST = timezone(timedelta(hours=8))

CANDIDATE_MANIFEST = os.path.join(CANDIDATE, "B06_CANDIDATE_MANIFEST.json")
CANDIDATE_MANIFEST_NAME = "B06_CANDIDATE_MANIFEST.json"
PARENT = os.path.join(
    WS, "integration-staging", "runtime", "b05-rehearsal-2026-10-07", "candidates",
    "b05-adapters-v1",
)
PARENT_MANIFEST_NAME = "B05_CANDIDATE_MANIFEST.json"
PARENT_MANIFEST = os.path.join(PARENT, PARENT_MANIFEST_NAME)
A14_MAP = os.path.join(OUT, "A14_MERGE_MAP.json")
LEDGER = os.path.join(OUT, "execution-ledger.json")
R0104_MERGE = os.path.join(OUT, "R0104_MERGE_PROPOSAL.json")
B05_MERGE = os.path.join(OUT, "B05_MERGE_PROPOSAL.json")
B01_MAP = os.path.join(
    OUT, "evidence", "B01", "b00b01-20261006T132400", "B01_MERGE_MAP.json",
)
SOURCE_EDITS_DIFF = os.path.join(RUN, "evidence", "source_edits.diff")
STAGED_FRONTEND_ROOT = os.path.join(WS, "integration-staging", "frontend")

EDITED_SOURCES = {
    "src/examdata/integration/api/app.py": os.path.join(RUN, "tools", "app.py"),
    "src/examdata/integration/api/dataset.py": os.path.join(RUN, "tools", "dataset.py"),
    "src/examdata/integration/api/view.py": os.path.join(RUN, "tools", "view.py"),
}
NEW_FRONTEND_SOURCES = {
    "frontend/server.mjs": os.path.join(RUN, "tools", "server.mjs"),
    "frontend/tests/server.test.mjs": os.path.join(RUN, "tools", "tests", "server.test.mjs"),
}
FRONTEND_CHANGES = {
    "frontend/PROVENANCE.json": "keep_frontend_provenance_staging_only",
    "frontend/README.md": "reconcile_frontend_readme",
    "frontend/app.js": "reconcile_frontend_app_js",
    "frontend/client.mjs": "install_frontend_client_mjs",
    "frontend/fixture-server.mjs": "install_frontend_fixture_server",
    "frontend/fixtures/PROVENANCE.json": "keep_frontend_fixtures_provenance_staging_only",
    "frontend/fixtures/catalog.json": "install_frontend_fixtures_catalog",
    "frontend/fixtures/resources.json": "install_frontend_fixtures_resources",
    "frontend/fixtures/syllabi.json": "install_frontend_fixtures_syllabi",
    "frontend/index.html": "reconcile_frontend_index_html",
    "frontend/search.mjs": "verify_frontend_search_mjs",
    "frontend/styles.css": "verify_frontend_styles_css",
    "frontend/tests/client.test.mjs": "install_frontend_tests_client",
    "frontend/tests/flow.test.mjs": "install_frontend_tests_flow",
    "frontend/tests/search.test.mjs": "reconcile_frontend_tests_search",
}
PROVENANCE_PATHS = {"frontend/PROVENANCE.json", "frontend/fixtures/PROVENANCE.json"}
EXPECTED_B01_FRONTEND_IDS = [f"MM-{n:04d}" for n in range(229, 242)]
SERVER_MJS_BASE_SHA = "05406d3aa9bc308abf9117e13281a3b1f88c18a0d8e2ddac3113cd738eb6e810"
SERVER_MJS_RECORDED_AT = "2026-10-06T11:43:31+08:00"

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


def digest_checks(manifest: dict) -> dict:
    recorded_parent = manifest["lineage"]["parent_tree"]
    recorded_candidate = manifest["candidate_tree"]
    parent_now = tree_digest(PARENT, (PARENT_MANIFEST_NAME,))
    candidate_now = tree_digest(CANDIDATE, (CANDIDATE_MANIFEST_NAME,))

    b05_derived = load_json(B05_MERGE).get("derived_from", {})
    b05_crossref = bool(b05_derived) and (
        b05_derived.get("candidate_manifest_sha256") == sha256_file(PARENT_MANIFEST)
        and (b05_derived.get("candidate_tree") or {}).get("sha256")
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

    frontend = manifest.get("frontend", {})
    staged_files = frontend.get("staged_files", [])
    staged_root_ok = rel(frontend.get("staged_root", "")) == rel(STAGED_FRONTEND_ROOT)
    frontend_staged_checks: dict[str, bool] = {}
    for sf in staged_files:
        path = sf["path"]
        cand_file = os.path.join(CANDIDATE, path)
        src_file = os.path.join(STAGED_FRONTEND_ROOT, path.split("/", 1)[1])
        frontend_staged_checks[path] = bool(
            os.path.isfile(cand_file)
            and os.path.isfile(src_file)
            and sha256_file(cand_file) == sf.get("written_sha256")
            and sha256_file(src_file) == sf.get("staged_sha256")
            and sf.get("staged_sha256") == sf.get("written_sha256")
        )

    prov_checks: dict[str, bool] = {}
    for rec in frontend.get("provenance_records", []):
        path = rec["path"]
        cand_file = os.path.join(CANDIDATE, path)
        src_file = os.path.join(STAGED_FRONTEND_ROOT, path.split("/", 1)[1])
        prov_checks[path] = bool(
            os.path.isfile(cand_file)
            and os.path.isfile(src_file)
            and sha256_file(cand_file) == rec.get("candidate_sha256")
            and sha256_file(src_file) == rec.get("staged_sha256")
            and rec.get("recorded_sha256") == rec.get("staged_sha256")
            == rec.get("candidate_sha256")
        )

    new_frontend_checks: dict[str, bool] = {}
    for nf in frontend.get("new_files", []):
        path = nf["path"]
        cand_file = os.path.join(CANDIDATE, path)
        source = NEW_FRONTEND_SOURCES.get(path, nf.get("source", ""))
        new_frontend_checks[path] = bool(
            os.path.isfile(cand_file)
            and os.path.isfile(source)
            and sha256_file(cand_file) == nf.get("written_sha256")
            and sha256_file(source) == nf.get("source_sha256")
            and nf.get("source_sha256") == nf.get("written_sha256")
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
        [sf["path"] for sf in staged_files]
        + [nf["path"] for nf in frontend.get("new_files", [])]
    )

    b01_map = load_json(B01_MAP)
    b01_frontend = [
        e for e in b01_map.get("entries", []) if e.get("group") == "frontend"
    ]
    staged_sha_by_rel = {sf["path"]: sf.get("staged_sha256") for sf in staged_files}
    b01_sha_checks = {
        e["id"]: staged_sha_by_rel.get(e["staged_path"].split("integration-staging/", 1)[1])
        == e.get("staged_sha256")
        for e in b01_frontend
    }
    not_merged_paths = {r.get("staged_path") for r in b01_map.get("not_merged", [])}
    prov_not_merged = all(
        f"integration-staging/{p}" in not_merged_paths for p in sorted(PROVENANCE_PATHS)
    )
    b01_planned = None
    for edit in b01_map.get("planned_original_edits", []):
        if edit.get("target_path") == "frontend/server.mjs":
            b01_planned = edit
            break
    planned_edit_ok = bool(
        b01_planned
        and b01_planned.get("base_sha256") == SERVER_MJS_BASE_SHA
        and b01_planned.get("base_exists") is True
        and b01_planned.get("observed_at") == SERVER_MJS_RECORDED_AT
        and b01_planned.get("packet") == "B06"
        and b01_planned.get("b01_disposition") == "carried_pending_release"
    )
    b01_derived = b01_map.get("derived_from", {})
    b01_a14_anchor = b01_derived.get("sha256") == sha256_file(A14_MAP)

    b01_records_ok = bool(
        [e.get("id") for e in b01_frontend] == EXPECTED_B01_FRONTEND_IDS
        and all(b01_sha_checks.values())
        and all(
            e.get("b01_disposition") == "deferred_pending_release"
            and e.get("b01_reconciliation", {}).get("kind") == "not_attempted_gate_blocked"
            and (e.get("base") is None or e["base"].get("drift") is False)
            for e in b01_frontend
        )
        and prov_not_merged
        and planned_edit_ok
        and b01_a14_anchor
    )

    a14_dataset = a14_entry("MM-0017")
    a14_app = a14_entry("MM-0015")
    a14_view = a14_entry("MM-0022")
    rp0005 = r0104_entry("RP-0005")
    bp0003 = b05_entry("BP-0003")
    bp0004 = b05_entry("BP-0004")
    dataset_edit = edited_by_path["src/examdata/integration/api/dataset.py"]
    app_edit = edited_by_path["src/examdata/integration/api/app.py"]
    view_edit = edited_by_path["src/examdata/integration/api/view.py"]
    supersession = {
        "dataset_chain": bool(
            a14_dataset.get("staged_sha256") == rp0005.get("staged_sha256_before")
            and rp0005.get("staged_sha256_after") == bp0003.get("staged_sha256_before")
            and bp0003.get("staged_sha256_after") == dataset_edit.get("parent_sha256")
            and rp0005.get("proposed_target") == a14_dataset.get("proposed_target")
            == "examdata/src/examdata/integration/api/dataset.py"
            and bp0003.get("proposed_target")
            == "examdata/src/examdata/integration/api/dataset.py"
        ),
        "app_chain": bool(
            a14_app.get("staged_sha256") == bp0004.get("staged_sha256_before")
            and bp0004.get("staged_sha256_after") == app_edit.get("parent_sha256")
            and a14_app.get("proposed_target") == bp0004.get("proposed_target")
            == "examdata/src/examdata/integration/api/app.py"
        ),
        "view_chain": bool(
            a14_view.get("staged_sha256") == view_edit.get("parent_sha256")
            and a14_view.get("proposed_target")
            == "examdata/src/examdata/integration/api/view.py"
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
        "b05_merge_crossref_matches": b05_crossref,
        "edited_files_source_matches": all(edited_checks.values()),
        "new_files_exactly_seventeen_vs_parent": (
            len(added_vs_parent) == 17 and added_vs_parent == expected_new
        ),
        "only_the_three_edited_files_changed_vs_parent": changed == sorted(EDITED_SOURCES),
        "frontend_staged_bytes_match_sources": bool(
            len(staged_files) == 15 and staged_root_ok
            and all(frontend_staged_checks.values())
        ),
        "frontend_provenance_records_match": bool(
            len(frontend.get("provenance_records", [])) == 13
            and all(prov_checks.values())
        ),
        "new_frontend_files_match_sources": bool(
            len(frontend.get("new_files", [])) == 2
            and all(new_frontend_checks.values())
        ),
        "frontend_matches_b01_records": b01_records_ok,
        "supersession_chains_match": all(supersession.values()),
        "supersession_chain_detail": supersession,
        "frontend_check_detail": {
            "staged_root_matches_staging_tree": staged_root_ok,
            "staged_files": frontend_staged_checks,
            "provenance_records": prov_checks,
            "new_files": new_frontend_checks,
            "b01_records": b01_sha_checks,
            "b01_planned_edit_server_mjs": {
                "found": b01_planned is not None,
                "base_sha256": b01_planned.get("base_sha256") if b01_planned else None,
                "observed_at": b01_planned.get("observed_at") if b01_planned else None,
                "packet": b01_planned.get("packet") if b01_planned else None,
                "b01_disposition": b01_planned.get("b01_disposition") if b01_planned else None,
            },
            "b01_a14_anchor_matches": b01_a14_anchor,
            "provenance_in_b01_not_merged": prov_not_merged,
            "node_check_recorded": frontend.get("node_check"),
        },
        "note": "tree digests recomputed from disk at proposal time with the recorded rule "
        "(sha256 over 'path\\0sha256\\n', sorted, __pycache__/.pytest_cache skipped, the named "
        "manifest excluded); the B05 cross-reference checks this candidate's recorded parent "
        "against B05_MERGE_PROPOSAL.json's derived_from; the frontend checks compare the "
        "candidate files against the staged tree under integration-staging/frontend and the "
        "frozen B01 records only (the original tree is never read); the file-set comparison "
        "excludes only the candidate's own manifest because the child carries byte-identical "
        "copies of the parent's manifests; the supersession chains re-verify the B05/R0104/A14 "
        "records that the three rewritten modules supersede (dataset: A14 MM-0017 -> R0104 "
        "RP-0005 -> B05 BP-0003 -> B06; app: A14 MM-0015 -> B05 BP-0004 -> B06; view: A14 "
        "MM-0022 -> B06 parent bytes)",
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

    b05_derived = load_json(B05_MERGE).get("derived_from", {})
    a14_unchanged = b05_derived.get("a14_merge_map_sha256") == a14_sha

    edited_by_path = {e["path"]: e for e in manifest["edited_files"]}
    frontend = manifest["frontend"]
    staged_files = frontend["staged_files"]
    node_files = {nf["path"]: nf for nf in frontend["new_files"]}
    b01_by_rel = {
        e["staged_path"].split("integration-staging/", 1)[1]: e
        for e in b01_map["entries"] if e.get("group") == "frontend"
    }
    b01_planned = next(
        e for e in b01_map["planned_original_edits"]
        if e.get("target_path") == "frontend/server.mjs"
    )

    app_edit = edited_by_path["src/examdata/integration/api/app.py"]
    dataset_edit = edited_by_path["src/examdata/integration/api/dataset.py"]
    view_edit = edited_by_path["src/examdata/integration/api/view.py"]
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
            "sha_note": "the before digest covers the parent (B05) file set with B05's own "
            "manifest excluded (its digest rule); the after digest covers the candidate file "
            "set with B06's own manifest excluded; both use the same function and rule",
            "status": "proposal_only_not_merged",
        },
        {
            "id": "BP-0002",
            "change": "rewrite_integration_app_for_frontend_discovery",
            "staged_path": rel(os.path.join(CANDIDATE, "src/examdata/integration/api/app.py")),
            "staged_sha256_before": app_edit["parent_sha256"],
            "staged_sha256_after": app_edit["written_sha256"],
            "kind": "staged_file_rewrite",
            "proposed_target": "examdata/src/examdata/integration/api/app.py",
            "proposed_target_origin": "A14_MERGE_MAP.json MM-0015 via B05_MERGE_PROPOSAL.json "
            "BP-0004; the B06 bytes supersede the unapplied B05 bytes",
            "phase_b_action": "add_file at the proposed target with the B06 bytes (supersedes the "
            "unapplied B05 proposal BP-0004; the whole integration package is new relative to "
            "the original project; there is no existing original file to edit; A14 observed the "
            "target as not existing)",
            "reversal": rewrite_reversal,
            "supersedes": {
                "proposal": "B05_MERGE_PROPOSAL.json BP-0004",
                "superseded_staged_sha256_after": app_edit["parent_sha256"],
                "chain": "A14 MM-0015 -> B05 BP-0004 -> B06",
            },
            "gates_required_for_this_action": ["original_paths_released"],
            "release_required": True,
            "original_level_reversal_kind": "delete_file",
            "restore_base_sha256": None,
            "sha_note": "staged_sha256_before is the B05 bytes this rewrite replaces; the chain "
            "is re-verified in digest_checks.supersession_chain_detail",
            "status": "proposal_only_not_merged",
        },
        {
            "id": "BP-0003",
            "change": "rewrite_integration_dataset_for_frontend_query_semantics",
            "staged_path": rel(os.path.join(CANDIDATE, "src/examdata/integration/api/dataset.py")),
            "staged_sha256_before": dataset_edit["parent_sha256"],
            "staged_sha256_after": dataset_edit["written_sha256"],
            "kind": "staged_file_rewrite",
            "proposed_target": "examdata/src/examdata/integration/api/dataset.py",
            "proposed_target_origin": "A14_MERGE_MAP.json MM-0017 via "
            "R0104_MERGE_PROPOSAL.json RP-0005 and B05_MERGE_PROPOSAL.json BP-0003; the B06 "
            "bytes supersede the unapplied B05 bytes",
            "phase_b_action": "add_file at the proposed target with the B06 bytes (supersedes the "
            "unapplied B05 proposal BP-0003; the whole integration package is new relative to "
            "the original project; there is no existing original file to edit; A14 observed the "
            "target as not existing)",
            "reversal": rewrite_reversal,
            "supersedes": {
                "proposal": "B05_MERGE_PROPOSAL.json BP-0003",
                "superseded_staged_sha256_after": dataset_edit["parent_sha256"],
                "chain": "A14 MM-0017 -> R0104 RP-0005 -> B05 BP-0003 -> B06",
            },
            "gates_required_for_this_action": ["original_paths_released"],
            "release_required": True,
            "original_level_reversal_kind": "delete_file",
            "restore_base_sha256": None,
            "sha_note": "staged_sha256_before is the B05 bytes this rewrite replaces; the chain "
            "is re-verified in digest_checks.supersession_chain_detail",
            "status": "proposal_only_not_merged",
        },
        {
            "id": "BP-0004",
            "change": "rewrite_integration_view_for_the_resources_wiring",
            "staged_path": rel(os.path.join(CANDIDATE, "src/examdata/integration/api/view.py")),
            "staged_sha256_before": view_edit["parent_sha256"],
            "staged_sha256_after": view_edit["written_sha256"],
            "kind": "staged_file_rewrite",
            "proposed_target": "examdata/src/examdata/integration/api/view.py",
            "proposed_target_origin": "A14_MERGE_MAP.json MM-0022; the B06 parent carried the "
            "A14 bytes unchanged and the B06 bytes supersede them",
            "phase_b_action": "add_file at the proposed target with the B06 bytes (the whole "
            "integration package is new relative to the original project; there is no existing "
            "original file to edit; A14 observed the target as not existing)",
            "reversal": rewrite_reversal,
            "supersedes": {
                "proposal": "A14_MERGE_MAP.json MM-0022",
                "superseded_staged_sha256": view_edit["parent_sha256"],
                "chain": "A14 MM-0022 -> B06 parent bytes (unchanged from A14 to the B06 "
                "parent, verified by sha equality)",
            },
            "gates_required_for_this_action": ["original_paths_released"],
            "release_required": True,
            "original_level_reversal_kind": "delete_file",
            "restore_base_sha256": None,
            "sha_note": "staged_sha256_before is the A14-staged version this rewrite replaces; "
            "the chain is re-verified in digest_checks.supersession_chain_detail",
            "status": "proposal_only_not_merged",
        },
    ]

    for i, sf in enumerate(staged_files):
        path = sf["path"]
        staged_src_rel = f"integration-staging/{path}"
        common = {
            "id": f"BP-{5 + i:04d}",
            "change": FRONTEND_CHANGES[path],
            "staged_path": rel(os.path.join(CANDIDATE, path)),
            "staged_sha256_before": None,
            "staged_sha256_after": sf["written_sha256"],
            "status": "proposal_only_not_merged",
            "staged_source": {
                "staged_path": staged_src_rel,
                "staged_sha256": sf["staged_sha256"],
                "note": "the file is new relative to the B06 parent (B05) candidate; relative "
                "to the B01 staged tree the bytes are unchanged (verified in digest_checks)",
            },
        }
        if path in PROVENANCE_PATHS:
            common.update({
                "kind": "staging_only_artifact",
                "proposed_target": None,
                "proposed_target_origin": "B01_MERGE_MAP.json not_merged exclusion: staging "
                "provenance consumed by B01; not a product file",
                "phase_b_action": "keep in integration-staging/ only; not a product file "
                "(B01 not_merged exclusions)",
                "reversal": "no original-project action to reverse; the file is removed only "
                "with the candidate tree",
                "gates_required_for_this_action": [],
                "release_required": False,
                "original_level_reversal_kind": "none",
                "restore_base_sha256": None,
            })
        else:
            if path not in b01_by_rel:
                raise ValueError(f"staged frontend file {path} has no B01 record")
            b01 = b01_by_rel[path]
            base = b01.get("base") or {}
            target_exists = bool(b01.get("target_observed", {}).get("exists"))
            restore_sha = base.get("sha256_recorded")
            if b01.get("reversal") == "delete_file":
                reversal_kind = "delete_file"
                restore = None
                reversal_text = (
                    "delete_file at the proposed target, and only if the target's current "
                    "sha256 still equals staged_sha256_after; never restore a sealed snapshot"
                )
            elif path == "frontend/tests/search.test.mjs":
                reversal_kind = "reconciliation_note"
                restore = restore_sha
                reversal_text = (
                    "B01 records the reversal restore_base_bytes against the base at "
                    "frontend/search.test.mjs (sha256_to_restore, recorded 1e50f10f...), a "
                    "different path than the proposed target frontend/tests/search.test.mjs "
                    "(which did not exist); the released reconciliation decides the final "
                    "layout; this entry never overwrites the recorded base path and never "
                    "restores a sealed snapshot"
                )
            else:
                reversal_kind = "restore_base_bytes"
                restore = restore_sha
                reversal_text = (
                    "restore the recorded base bytes (sha256_to_restore) at the proposed "
                    "target, and only if the target's current sha256 still equals "
                    "staged_sha256_after; never restore a sealed snapshot"
                )
            act = b01.get("phase_b_action")
            if act == "reconcile_modify":
                action_text = (
                    "reconcile_modify at release: three-way semantic reconciliation against "
                    "the released original tree (B01 deferred it because the gate was closed), "
                    "then write the released reconciliation at the proposed target"
                )
            elif act == "verify_copy":
                action_text = (
                    "verify_copy at release: if the target bytes already match "
                    "staged_sha256_after, write nothing; otherwise reconcile before any write"
                )
            else:
                action_text = "add_file at the proposed target with the B06 candidate bytes"
            common.update({
                "kind": b01["kind"],
                "proposed_target": b01["proposed_target"],
                "proposed_target_origin": f"B01_MERGE_MAP.json {b01['id']} (carried from A14; "
                f"kind {b01['kind']}); the B06 candidate carries the same staged bytes",
                "phase_b_action": action_text,
                "reversal": reversal_text,
                "supersedes": {
                    "record": f"B01_MERGE_MAP.json {b01['id']}",
                    "note": "byte-identical staged bytes; this entry only updates the "
                    "operational record to the B06 candidate (B01 carried the entry "
                    "deferred_pending_release)",
                },
                "b01_record": {
                    "id": b01["id"],
                    "kind": b01["kind"],
                    "phase_b_action": b01.get("phase_b_action"),
                    "reversal": b01.get("reversal"),
                    "b01_disposition": b01.get("b01_disposition"),
                    "base_sha256_recorded": base.get("sha256_recorded"),
                    "base_recorded_at": base.get("recorded_at"),
                    "target_observed_exists": target_exists,
                },
                "gates_required_for_this_action": ["original_paths_released"],
                "release_required": True,
                "original_level_reversal_kind": reversal_kind,
                "restore_base_sha256": restore,
            })
        entries.append(common)

    server_nf = node_files["frontend/server.mjs"]
    server_test_nf = node_files["frontend/tests/server.test.mjs"]
    entries.append({
        "id": "BP-0020",
        "change": "rewrite_frontend_server_for_the_v2_switch",
        "staged_path": rel(os.path.join(CANDIDATE, "frontend/server.mjs")),
        "staged_sha256_before": None,
        "staged_sha256_after": server_nf["written_sha256"],
        "kind": "staged_file_rewrite",
        "proposed_target": "frontend/server.mjs",
        "proposed_target_origin": "B01_MERGE_MAP.json planned_original_edits (packet B06); base "
        "sha256 05406d3a... observed 2026-10-06T11:43:31+08:00",
        "phase_b_action": "reconcile_modify at release: serve the staged v2 client behind the "
        "reversible flag and keep tests/ and fixtures/ out of the static surface (the B01 "
        "planned change); the merged server's production port strategy needs an explicit human "
        "decision - the staged server defaults to an ephemeral port (0) and refuses to bind "
        "5188/8000 as a staging safety measure",
        "reversal": "restore the recorded base bytes (sha256 05406d3a...); never restore a "
        "sealed snapshot",
        "supersedes": {
            "record": "B01_MERGE_MAP.json planned_original_edits frontend/server.mjs",
            "note": "the B01 planned edit was never applied (carried_pending_release); the B06 "
            "candidate supplies the staged bytes it described",
        },
        "b01_record": {
            "id": None,
            "kind": "planned_original_edit",
            "phase_b_action": "reconcile_modify (planned change text in the B01 record)",
            "reversal": b01_planned.get("reversal"),
            "b01_disposition": b01_planned.get("b01_disposition"),
            "base_sha256_recorded": b01_planned.get("base_sha256"),
            "base_recorded_at": b01_planned.get("observed_at"),
            "target_observed_exists": b01_planned.get("base_exists"),
        },
        "gates_required_for_this_action": ["original_paths_released"],
        "release_required": True,
        "original_level_reversal_kind": "restore_base_bytes",
        "restore_base_sha256": SERVER_MJS_BASE_SHA,
        "sha_note": "the staged file is new relative to the B06 parent (B05) candidate; the B01 "
        "planned edit recorded the original target as existing with base 05406d3a...",
        "status": "proposal_only_not_merged",
    })
    entries.append({
        "id": "BP-0021",
        "change": "install_frontend_tests_server",
        "staged_path": rel(os.path.join(CANDIDATE, "frontend/tests/server.test.mjs")),
        "staged_sha256_before": None,
        "staged_sha256_after": server_test_nf["written_sha256"],
        "kind": "new_file",
        "proposed_target": "frontend/tests/server.test.mjs",
        "proposed_target_origin": "B06 candidate: new test-only asset covering the merged "
        "server's static surface; not linked to any B01 record (the B01 MM-0241 record covers "
        "frontend/tests/search.test.mjs only)",
        "phase_b_action": "add_file at the proposed target with the B06 candidate bytes; "
        "test-only asset - keep tests/ and fixtures/ out of the static surface",
        "reversal": "delete_file at the proposed target, and only if the target's current "
        "sha256 still equals staged_sha256_after; never restore a sealed snapshot",
        "gates_required_for_this_action": ["original_paths_released"],
        "release_required": True,
        "original_level_reversal_kind": "delete_file",
        "restore_base_sha256": None,
        "sha_note": "the staged file is new relative to the B06 parent (B05) candidate; no "
        "original-project target is recorded for it",
        "status": "proposal_only_not_merged",
    })

    merge = {
        "proposal_version": "b06-merge-proposal/1",
        "packet": "B06",
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
            "b01_merge_map": rel(B01_MAP),
            "b01_merge_map_sha256": b01_sha,
            "b01_merge_map_sha256_note": "observed at proposal time; the frozen anchor recorded "
            "in the execution ledger is the A14 map sha256 (29940a0b...), not the B01 map, so "
            "this value is recorded for traceability only and is not compared against a frozen "
            "expectation",
            "a14_merge_map": rel(A14_MAP),
            "a14_merge_map_sha256": a14_sha,
            "a14_merge_map_byte_unchanged": a14_unchanged,
            "b01_a14_anchor_matches": checks["frontend_check_detail"]["b01_a14_anchor_matches"],
            "source_edits_diff": rel(SOURCE_EDITS_DIFF),
            "source_edits_diff_sha256": sha256_file(SOURCE_EDITS_DIFF)
            if os.path.isfile(SOURCE_EDITS_DIFF) else None,
        },
        "digest_checks": checks,
        "scope_note": (
            "B06 migrates frontend source discovery: relative to its parent (the B05 adapters "
            "candidate) it rewrites three carried modules - src/examdata/integration/api/app.py "
            "(discovery projection and resources wiring), src/examdata/integration/api/dataset.py "
            "(frontend-shaped query semantics) and src/examdata/integration/api/view.py - and "
            "adds seventeen files under frontend/: fifteen staged files byte-for-byte (thirteen "
            "carried from the B01/A14 records MM-0229..MM-0241, plus the two staging PROVENANCE "
            "records that B01 excluded from the merge), the rewritten frontend/server.mjs (the "
            "B01 planned original edit, packet B06) and the new frontend/tests/server.test.mjs. "
            "Everything else in the candidate is a byte-identical carry of B05. The staged bytes "
            "of the three rewritten modules supersede the bytes recorded by "
            "B05_MERGE_PROPOSAL.json BP-0004 (app.py), B05_MERGE_PROPOSAL.json BP-0003 via "
            "R0104_MERGE_PROPOSAL.json RP-0005 (dataset.py) and A14_MERGE_MAP.json MM-0022 "
            "(view.py); the whole integration package is new relative to the original project, "
            "so every release-required module entry is add_file semantics. The frontend entries "
            "carry the B01 records (deferred_pending_release for MM-0229..MM-0241; "
            "carried_pending_release for the server.mjs planned edit); B01 performed no "
            "reconciliation (three_way=false, gate was closed) and this proposal performs none "
            "either - it re-records the same deferred state against the B06 candidate bytes. "
            "The active-owner seam (B05 BP-0002) and the composition hook and shared-application "
            "registration (B04) remain as proposed in B05/B04 and are not re-proposed here. The "
            "product/test payload inside the candidate is the R04 payload already proposed in "
            "R0104_MERGE_PROPOSAL.json and the packaging already proposed in "
            "B02_MERGE_PROPOSAL.json; nothing is re-proposed here. Proposal only: nothing in "
            "this file has been applied to the original project. All seven gates remain closed; "
            "the original merge stays blocked until an explicit human release."
        ),
        "action_level_gate_model": ACTION_LEVEL_GATE_MODEL,
        "frozen_evidence_never_touched": FROZEN,
        "gate_state_at_generation": ledger,
        "counts": {
            "entries": len(entries),
            "entries_requiring_release": sum(1 for e in entries if e["release_required"]),
            "staging_only_entries": sum(1 for e in entries if not e["release_required"]),
            "new_files_vs_parent": manifest["counts"]["new_files_added_by_b06"],
            "edited_files_rewritten": manifest["counts"]["edited_files_rewritten_by_b06"],
        },
        "entries": entries,
        "not_merged": True,
        "requirements_for_merge": [
            "explicit human release opening original_paths_released with an explicit scope; the "
            "records carried from B01 (deferred_pending_release / carried_pending_release) "
            "become actionable only under that release",
            "apply the three release-required module entries (add_file semantics; the whole "
            "integration package is new relative to the original project): install the B06 "
            "bytes at examdata/src/examdata/integration/api/app.py (superseding the unapplied "
            "B05 proposal BP-0004), examdata/src/examdata/integration/api/dataset.py "
            "(superseding R0104 RP-0005 and the unapplied B05 BP-0003) and "
            "examdata/src/examdata/integration/api/view.py (superseding A14 MM-0022, whose "
            "bytes the B06 parent carried unchanged)",
            "install the fifteen release-required frontend entries with the B06 candidate "
            "bytes: thirteen from B01_MERGE_MAP.json (MM-0229..MM-0241; reconcile_modify for "
            "app.js, index.html, README.md and tests/search.test.mjs; verify_copy for "
            "search.mjs and styles.css - write nothing if the bytes already match), "
            "frontend/server.mjs (the B01 planned original edit) and "
            "frontend/tests/server.test.mjs (new); the two PROVENANCE entries stay "
            "staging-only and are never installed",
            "re-verify every recorded base before writing (B01 base sha256_recorded for the "
            "frontend entries, observed 2026-10-06T10:17:44+08:00; server.mjs base_sha256 "
            "observed 2026-10-06T11:43:31+08:00); abort the affected entry if any base drifted",
            "for the reconcile_modify entries, perform the three-way semantic reconciliation "
            "against the released original tree that B01 deferred (three_way=false, gate was "
            "closed) before writing",
            "the merged static server must keep tests/ and fixtures/ out of the static surface "
            "(B01 MM-0232 note; covered by frontend/tests/server.test.mjs) and its production "
            "port strategy needs an explicit human decision (the staged server defaults to an "
            "ephemeral port and refuses 5188/8000 as a staging safety measure)",
            "verify the candidate tree digest (the container entry's staged_sha256_after, "
            "recomputed with the recorded rule) immediately before any original write",
            "re-run the isolated staged suite against the frozen B06 candidate before any "
            "original write, and re-run the B06 route probe plus the suite against the merged "
            "tree afterwards",
        ],
    }

    rollback = {
        "proposal_version": "b06-rollback-proposal/1",
        "packet": "B06",
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
                "staged_file_changes": "the seventeen added frontend files and the three "
                "rewritten modules live only inside the candidate tree: the container tree "
                "delete removes them; the three rewritten modules can alternatively be reversed "
                "by restoring the parent's staged bytes (staging_sha256_to_restore)",
            },
            "original_level": {
                "merged_add_file": "delete_file at the proposed target, and only if its sha256 "
                "still equals sha256_at_proposal",
                "merged_staged_file_rewrite": "only the frontend/server.mjs rewrite has an "
                "existing original target (restore its recorded base bytes, original_base_"
                "sha256); the three rewritten modules never existed in the original project, "
                "so their original-level reversal is a delete, never a restore of the "
                "superseded staged versions",
                "merged_reconcile_modify": "restore the recorded base bytes (original_base_"
                "sha256) at the proposed target, and only if the target's current sha256 still "
                "equals sha256_at_proposal; never restore a sealed snapshot",
                "merged_verify_copy": "if the release wrote nothing (the bytes already "
                "matched), there is nothing to reverse; otherwise restore the recorded base "
                "bytes, guarded on the target sha",
                "frontend_tests_search_note": "B01 records restore_base_bytes against the base "
                "at frontend/search.test.mjs (a different path than the empty proposed target "
                "frontend/tests/search.test.mjs); the released reconciliation decides the "
                "final layout and this entry never overwrites the recorded base path",
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
                "never restore the live execution ledger from a private copy",
            ],
        },
        "guards": [
            "verify the resolved absolute path and its sha256 (or tree digest) before any delete",
            "no delete ever targets a protected original in Phase B private rehearsal",
            "planned original writes are reversible only after the human release",
            "the three rewritten integration modules never existed in the original project; "
            "their original-level reversal is a delete, never a restore of the superseded "
            "staged versions",
            "the base restores (app.js, index.html, README.md, search.mjs, styles.css, "
            "server.mjs) restore only the sha256 recorded by B01 (frozen records) and abort if "
            "the target drifted from sha256_at_proposal",
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
                    else "removed only with the candidate tree; the file has no separate "
                    "staging reversal"
                    if e["kind"] == "staging_only_artifact"
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
        "# B06 merge proposal (private rehearsal only)",
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
        f"- B06 adds {m['counts']['new_files_vs_parent']} frontend files and rewrites "
        f"{m['counts']['edited_files_rewritten']} carried modules relative to the parent (the "
        "frontend payload plus the discovery/view rewrites; everything else is a byte-identical "
        "carry of B05)",
        f"- A14 merge map byte-unchanged: `{m['derived_from']['a14_merge_map_byte_unchanged']}`; "
        f"B01 merge map sha256 (observation): `{m['derived_from']['b01_merge_map_sha256'][:12]}`",
        "",
        "## Digest and cross-reference checks",
        "",
        "| Check | Result |",
        "| --- | --- |",
        f"| candidate tree re-verified from disk | `{m['digest_checks']['candidate_tree_reverified']}` |",
        f"| parent tree re-verified from disk | `{m['digest_checks']['parent_tree_reverified']}` |",
        f"| matches B05 merge proposal's derived_from | "
        f"`{m['digest_checks']['b05_merge_crossref_matches']}` |",
        f"| edited files match the tooling sources | "
        f"`{m['digest_checks']['edited_files_source_matches']}` |",
        f"| new files vs parent exactly the seventeen frontend files | "
        f"`{m['digest_checks']['new_files_exactly_seventeen_vs_parent']}` |",
        f"| only the three edited files changed vs parent | "
        f"`{m['digest_checks']['only_the_three_edited_files_changed_vs_parent']}` |",
        f"| frontend staged bytes match sources (15) | "
        f"`{m['digest_checks']['frontend_staged_bytes_match_sources']}` |",
        f"| frontend provenance records match (13) | "
        f"`{m['digest_checks']['frontend_provenance_records_match']}` |",
        f"| new frontend files match sources (2) | "
        f"`{m['digest_checks']['new_frontend_files_match_sources']}` |",
        f"| frontend entries match the frozen B01 records | "
        f"`{m['digest_checks']['frontend_matches_b01_records']}` |",
        f"| B05/R0104/A14 supersession chains | "
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
        "# B06 rollback proposal (private rehearsal only)",
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
    write_json(os.path.join(OUT, "B06_MERGE_PROPOSAL.json"), merge)
    write_json(os.path.join(OUT, "B06_ROLLBACK_PROPOSAL.json"), rollback)
    write_text(os.path.join(OUT, "B06_MERGE_PROPOSAL.md"), merge_md(merge))
    write_text(os.path.join(OUT, "B06_ROLLBACK_PROPOSAL.md"), rollback_md(rollback))
    print(json.dumps(merge["counts"], ensure_ascii=False))
    print(json.dumps(rollback["counts"], ensure_ascii=False))
    print(json.dumps(merge["gate_state_at_generation"]["gates"], ensure_ascii=False))
    non_bool = ("note", "supersession_chain_detail", "frontend_check_detail")
    print(json.dumps({k: v for k, v in merge["digest_checks"].items() if k not in non_bool},
                     ensure_ascii=False))
    failed_checks = [k for k, v in merge["digest_checks"].items()
                     if k not in non_bool and not v]
    if failed_checks:
        print(f"ERROR: digest checks failed: {failed_checks}", file=sys.stderr)
        return 1
    counts = merge["counts"]
    if (counts["entries"] != 21 or counts["entries_requiring_release"] != 18
            or counts["staging_only_entries"] != 3 or counts["new_files_vs_parent"] != 17
            or counts["edited_files_rewritten"] != 3):
        print(f"ERROR: unexpected counts {counts}", file=sys.stderr)
        return 1
    if not merge["gate_state_at_generation"]["all_closed"]:
        print("ERROR: a gate is open", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
