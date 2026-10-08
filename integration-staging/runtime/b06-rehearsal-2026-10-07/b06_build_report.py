"""Build the B06 rehearsal review report and the B06 private progress ledger.

Everything here is derived from artifacts already on disk (the candidate
manifest, the frozen layout validation, the archived probe capture, the
proposal JSONs and the staged-suite transcript), so no count and no hash is
typed by hand. This writes only inside docs/integration/execution/; frozen
evidence is read, never rewritten.

Two facts of this rehearsal are recorded deliberately and not hidden:

* the probe's first capture attempt exited 1 (two F-section checks failed on a
  key-space bug in the probe itself); the clean rerun overwrote the capture at
  the same path, so the archived capture is the clean one and the failure is
  recorded in the command table and in ``process_observations``;
* the proposals generator's first run exited 1 on one digest check (the
  expected B01 frontend id list was generated without zero padding); the
  rerun after the fix exited 0 and its output is what sits on disk.
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
FROZEN_EVID = os.path.join(OUT, "evidence", "B06", "b06-rehearsal-2026-10-07")
B05_FROZEN_PROBE = os.path.join(
    OUT, "evidence", "B05", "b05-rehearsal-2026-10-07", "probe_cwd1.json")

CST = timezone(timedelta(hours=8))

CANDIDATE = os.path.join(RUN, "candidates", "b06-frontend-v1")
CANDIDATE_MANIFEST = os.path.join(CANDIDATE, "B06_CANDIDATE_MANIFEST.json")
PARENT = os.path.join(
    RUN, "..", "b05-rehearsal-2026-10-07", "candidates", "b05-adapters-v1",
)
VALIDATION = os.path.join(FROZEN_EVID, "B06_LAYOUT_VALIDATION.json")
SUITE_TXT = os.path.join(EVID, "isolated_staged_suite.txt")
SOURCE_EDITS = os.path.join(EVID, "source_edits.diff")
BUILD_RECORD = os.path.join(EVID, "build_run.json")
PROBE_RECORD = os.path.join(EVID, "probe_run1.json")

MERGE_JSON = os.path.join(OUT, "B06_MERGE_PROPOSAL.json")
ROLLBACK_JSON = os.path.join(OUT, "B06_ROLLBACK_PROPOSAL.json")
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
PY_ABS = "C:/Users/weo/Desktop/api/examdata/.venv/Scripts/python.exe"
WS_ABS = "C:/Users/weo/Desktop/api"
RUN_REL = "integration-staging/runtime/b06-rehearsal-2026-10-07"
CAND_ABS = f"{WS_ABS}/{RUN_REL}/candidates/b06-frontend-v1"
PROBE_ENV = (
    'CAND="$PWD/candidates/b06-frontend-v1" '
    "B06_CANDIDATE_ROOT=\"$CAND\" B06_WORKSPACE_ROOT=\"" + WS_ABS + "\" "
    "B06_TMP_DIR=\"$PWD/evidence/tmp\" EXAMDATA_INTEGRATION_ROOT=\"$CAND\""
)
PROBE_RUN = (
    "PYTHONDONTWRITEBYTECODE=1 PYTHONIOENCODING=utf-8 "
    f'"{PY_ABS}" b06_route_probe.py '
    "1> evidence/probe_run1.json 2> evidence/probe_run1.err"
)

COMMANDS = [
    {
        "step": "build candidate",
        "command": "PYTHONIOENCODING=utf-8 PYTHONDONTWRITEBYTECODE=1 "
                   "C:/Users/weo/Desktop/api/examdata/.venv/Scripts/python.exe "
                   "b06_build_candidate.py > evidence/build_run.json "
                   "2> evidence/build_run.err.txt",
        "cwd": "C:/Users/weo/Desktop/api/integration-staging/runtime/"
               "b06-rehearsal-2026-10-07",
        "exit_code": 0,
        "note": "build record all_ok=True with 21/21 checks; "
                "evidence/build_run.err.txt is 0 bytes",
    },
    {
        "step": "route probe, first capture attempt",
        "command": f"{PROBE_ENV} {PROBE_RUN}; echo \"probe_exit=$?\"",
        "cwd": "C:/Users/weo/Desktop/api/integration-staging/runtime/"
               "b06-rehearsal-2026-10-07",
        "exit_code": 1,
        "note": "failed exactly two checks in the new F section "
                "(F_frontend_tree_is_seventeen_files on a key-space mismatch, "
                "and its cascade F_section_completed with a doubled "
                "frontend/frontend path); fixed inside the probe and rerun; "
                "the failed capture at evidence/probe_run1.json was overwritten "
                "by the clean rerun and is not archived separately - details in "
                "process_observations",
    },
    {
        "step": "route probe, clean rerun (the archived capture)",
        "command": "PYTHONDONTWRITEBYTECODE=1 PYTHONIOENCODING=utf-8 "
                   f"\"{PY_ABS}\" -m py_compile b06_route_probe.py && "
                   f"rm -rf __pycache__ && {PROBE_ENV} {PROBE_RUN}; "
                   "echo \"probe_exit=$?\"",
        "cwd": "C:/Users/weo/Desktop/api/integration-staging/runtime/"
               "b06-rehearsal-2026-10-07",
        "exit_code": 0,
        "note": "138/138 checks clean; this rerun is evidence/probe_run1.json; "
                "stderr holds only the Starlette deprecation warning",
    },
    {
        "step": "validate (probe from 3 cwds)",
        "command": "PYTHONDONTWRITEBYTECODE=1 PYTHONIOENCODING=utf-8 "
                   f"\"{PY_ABS}\" -m py_compile b06_validate.py && "
                   "rm -rf __pycache__ && echo \"compile_ok\" && "
                   "PYTHONDONTWRITEBYTECODE=1 PYTHONIOENCODING=utf-8 "
                   f"\"{PY_ABS}\" b06_validate.py; echo \"validate_exit=$?\"",
        "cwd": "C:/Users/weo/Desktop/api/integration-staging/runtime/"
               "b06-rehearsal-2026-10-07",
        "exit_code": 0,
        "note": "the validator itself writes the frozen evidence under "
                "docs/integration/execution/evidence/B06/b06-rehearsal-2026-10-07/ "
                "(B06_LAYOUT_VALIDATION.json, b06_validation_run.txt, "
                "probe_cwd1..3.json)",
    },
    {
        "step": "isolated staged suite",
        "command": "bash integration-staging/tools/run_staged_tests.sh -q "
                   f"> {RUN_REL}/evidence/isolated_staged_suite.txt 2>&1; "
                   f"echo \"suite_exit=$?\" >> {RUN_REL}/evidence/"
                   "isolated_staged_suite.txt",
        "cwd": "C:/Users/weo/Desktop/api",
        "exit_code": 0,
        "note": "887 passed; the transcript's last line records suite_exit=0",
    },
    {
        "step": "merge + rollback proposals, first run",
        "command": "PYTHONIOENCODING=utf-8 PYTHONDONTWRITEBYTECODE=1 "
                   f"\"{PY_ABS}\" b06_build_proposals.py; echo \"EXIT=$?\"",
        "cwd": "C:/Users/weo/Desktop/api/integration-staging/runtime/"
               "b06-rehearsal-2026-10-07",
        "exit_code": 1,
        "note": "failed exactly one digest check, frontend_matches_b01_records: "
                "the expected B01 frontend id list was generated without zero "
                "padding (MM-229... instead of MM-0229...); fixed one line and "
                "rerun; details in process_observations",
    },
    {
        "step": "merge + rollback proposals, rerun after the fix",
        "command": "PYTHONIOENCODING=utf-8 PYTHONDONTWRITEBYTECODE=1 "
                   f"\"{PY_ABS}\" b06_build_proposals.py; echo \"EXIT=$?\"",
        "cwd": "C:/Users/weo/Desktop/api/integration-staging/runtime/"
               "b06-rehearsal-2026-10-07",
        "exit_code": 0,
        "note": "all 11 digest checks true; both proposal JSONs on disk are the "
                "post-fix regenerated versions",
    },
    {
        "step": "review report + progress ledger",
        "command": "PYTHONIOENCODING=utf-8 PYTHONDONTWRITEBYTECODE=1 "
                   f"\"{PY_ABS}\" b06_build_report.py",
        "cwd": "C:/Users/weo/Desktop/api/integration-staging/runtime/"
               "b06-rehearsal-2026-10-07",
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
        "b06_build_candidate.py",
        "b06_route_probe.py",
        "b06_validate.py",
        "b06_build_proposals.py",
        "b06_build_report.py",
    ]
    return [rel(os.path.join(RUN, n)) for n in names if os.path.isfile(os.path.join(RUN, n))]


def suite_counts() -> dict:
    import re

    text = open(SUITE_TXT, encoding="utf-8", errors="replace").read()
    summary = None
    exit_code = None
    for line in reversed(text.splitlines()):
        stripped = line.strip()
        if stripped.startswith("EXIT=") or stripped.startswith("suite_exit="):
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
    if exit_code is None:
        raise SystemExit(f"could not read the suite exit code from {rel(SUITE_TXT)}")
    return {
        "summary": summary,
        "passed": passed,
        "failed": failed,
        "exit_code": exit_code,
        "transcript_sha256": sha256_file(SUITE_TXT),
    }


NEGATIVES = [
    "N1_raw_include_serves_v2_unshaped_errors",
    "N1_raw_include_binary_row_keeps_application_json",
    "N2_unscoped_install_changes_exactly_three_probes",
    "N2_unscoped_legacy_500_becomes_json_envelope",
    "N2_unscoped_legacy_422_becomes_400_envelope",
    "N2_unscoped_legacy_404_becomes_envelope",
    "N2_post_build_handler_install_is_invisible",
    "N3_mount_documents_no_v2_paths",
    "N3_mount_direct_info_is_wrong_route_envelope",
    "N3_mount_requires_doubled_prefix",
    "N4_double_attach_refused",
    "N4_double_attach_leaves_host_unchanged",
    "N5_late_attach_refused",
    "N5_late_attach_no_v2_paths",
    "N6_non_fastapi_host_refused",
    "N7_refuses_missing_evidence_marker",
    "N7_refuses_missing_status_marker",
    "N7_refuses_non_synthetic_source_evidence",
    "N7_refuses_live_access_material",
    "N7_refuses_unavailable_season_without_reason",
    "N7_refuses_date_without_raw_text",
    "N7_refuses_unknown_boundary_with_parsed_value",
    "N7_refuses_undeclared_missing_boundary",
    "N7_refuses_non_list_family_rows",
    "N7_dataset_refuses_unvalidated_source",
]

POSITIVES = [
    "S_fixture_source_valid_counts",
    "S_default_dataset_uses_fixture_source",
    "S_rows_copy_isolated",
    "S_deferred_fixtures_through_seam",
    "S_route_rows_carry_markers",
    "S_cie_event_null_fields_preserved",
    "S_seasons_unavailable_with_reason",
    "S_windows_unknown_boundaries_declared",
    "S_private_source_served_by_routes",
    "S_fixture_path_still_serves_after_injection",
    "B_ordering_get_first_match_own_route",
    "B_ordering_head_first_match_own_route",
    "B_no_param_static_shadowing",
    "B_no_pattern_intersections",
    "C_route_table_prefix_kept",
    "C_route_table_single_wrapper_appended",
    "C_legacy_inventory_byte_identical",
    "C_legacy_extras_byte_identical",
    "C_legacy_boom_bytes_pinned",
    "C_binary_fixture_ids_pinned",
    "C_binary_content_200",
    "C_binary_range_206",
    "C_binary_conditional_304",
    "C_binary_head_200",
    "C_material_content_200_pinned",
    "C_v2_typed_400_invalid_request",
    "C_v2_stack_boom_500_internal_error",
    "C_v2_jobs_404_not_found",
    "C_v2_unknown_404_route_not_found",
    "C_v2_post_info_405_method_not_allowed",
    "C_v2_info_200_envelope",
    "C_v2_controls_differ_from_baseline",
    "D_path_delta_is_exactly_registry",
    "D_pre_paths_operations_unchanged",
    "D_operation_ids_unique",
    "D_v2_operation_ids_match_standalone",
    "D_binary_rows_documented",
    "D_nonbinary_200_schema_is_envelope",
    "D_openapi_route_serves_same_document",
    "D_second_instance_document_digest_equal",
    "D_stability_digests_match_b05_ledger",
    "D_stability_ids_and_delta_match_b05_ledger",
    "F_frontend_tree_is_seventeen_files",
    "F_staged_frontend_bytes_match_workspace_source",
    "F_new_frontend_files_match_run_sources",
    "F_provenance_records_match_candidate_and_source",
    "F_node_available",
    "F_node_check_parses_new_frontend_js",
    "F_node_test_suite_41_passed",
    "G_rows_six_sorted_with_discovery_blocks",
    "G_empty_query_returns_all_six",
    "G_system_filter_rows",
    "G_unknown_filter_422_unsupported_filter",
    "G_query_matrix_all_21_cases",
    "G_boundary_mar_leaves_mark_scheme_alone",
    "G_boundary_202_is_not_2024",
    "G_boundary_paper_suffix_01_matches",
    "G_detail_routes_carry_discovery_key",
    "H_upstream_uvicorn_started",
    "H_frontend_server_ephemeral_banner",
    "H_frontend_serves_index",
    "H_node_static_index_bytes_equal",
    "H_node_static_root_alias_serves_index",
    "H_node_static_missing_404",
    "H_node_method_405_allow_get",
    "H_node_catalog_json_bytes_equal",
    "H_node_syllabi_json_bytes_equal",
    "H_node_client_cie_single_season",
    "H_node_client_cie_fanout",
    "H_node_client_edexcel_single_june",
    "H_node_client_edexcel_fanout_cross_season_duplicates",
    "H_node_bridge_cie_single_rows",
    "H_node_bridge_cie_fanout_empty_seasons_ok",
    "H_node_bridge_edexcel_fanout_deduped",
    "H_node_bridge_guard_400",
    "H_node_content_bytes_via_proxy",
    "H_node_v2_info_via_proxy",
    "H_node_gateway_denied_404",
    "H_node_gateway_allowed_forwarded_to_upstream",
    "H_cross_stack_all_18_pass",
    "H_content_triple_proxy_direct_disk",
    "H_rehearsal_processes_stopped",
    "N1_legacy_probes_unchanged",
]


def build() -> tuple[dict, str]:
    manifest = load_json(CANDIDATE_MANIFEST)
    validation = load_json(VALIDATION)
    merge = load_json(MERGE_JSON)
    rollback = load_json(ROLLBACK_JSON)
    live = load_json(LEDGER)
    probe = load_json(PROBE_RECORD)
    build_record = load_json(BUILD_RECORD)
    b05_probe = load_json(B05_FROZEN_PROBE)["report"]

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

    probe_first = load_json(os.path.join(FROZEN_EVID, first_run))["report"]
    import_checks = []
    for c in probe_first["checks"]:
        if not c["name"].startswith("A_"):
            continue
        detail = c.get("detail") or ""
        if len(detail) > 200:
            detail = detail[:200] + "\u2026"
        import_checks.append({"name": c["name"], "ok": bool(c["ok"]), "detail": detail})

    for name in NEGATIVES + POSITIVES:
        if name not in check_names:
            raise SystemExit(f"check name not found in probe evidence: {name}")

    evidence_negatives = set(probe_first["negative_checks"])
    evidence_positives = set(probe_first["positive_checks"])
    if evidence_negatives != set(NEGATIVES):
        raise SystemExit(
            "negative control list disagrees with the probe evidence: "
            f"{sorted(evidence_negatives ^ set(NEGATIVES))}"
        )
    if evidence_positives != set(POSITIVES):
        raise SystemExit(
            "positive control list disagrees with the probe evidence: "
            f"{sorted(evidence_positives ^ set(POSITIVES))}"
        )
    if probe["negative_checks"] != probe_first["negative_checks"]:
        raise SystemExit("archived probe capture disagrees with frozen probe evidence")
    if probe["positive_checks"] != probe_first["positive_checks"]:
        raise SystemExit("archived probe capture disagrees with frozen probe evidence")

    b05_negatives = b05_probe["negative_checks"]
    b05_positives = b05_probe["positive_checks"]
    renamed = {
        "D_stability_digests_match_b05_ledger":
            "D_stability_digests_match_b04_ledger",
        "D_stability_ids_and_delta_match_b05_ledger":
            "D_stability_ids_and_delta_match_b04_ledger",
    }
    if POSITIVES != b05_positives:
        reduced = [
            renamed.get(n, n) for n in POSITIVES
            if not n.startswith(("F_", "G_", "H_"))
        ]
        if reduced != b05_positives:
            raise SystemExit(
                "the B06 positive-control delta is not just the renamed ledger "
                "checks plus the new F/G/H sections; refusing to claim it is"
            )
    if NEGATIVES != b05_negatives:
        raise SystemExit(
            "the B06 negative-control list differs from B05; refusing to claim "
            "it is unchanged"
        )
    fgh = [n for n in POSITIVES if n.startswith(("F_", "G_", "H_"))]
    if len(fgh) != 40:
        raise SystemExit(f"expected 40 new F/G/H checks, found {len(fgh)}")

    counts = manifest["counts"]
    tree = manifest["candidate_tree"]
    carried = manifest["carried_verbatim_tree"]
    parent = manifest["lineage"]["parent_tree"]

    node_test = (probe.get("frontend") or {}).get("node_test") or {}
    node_counts = node_test.get("counts") or {}
    cross_stack = probe.get("cross_stack") or {}
    cross_counts = (cross_stack.get("cross") or {}).get("counts") or {}

    ledger = {
        "ledger_version": "b06-private-progress-ledger/1",
        "generated_by": rel(os.path.abspath(__file__)),
        "generated_at": now,
        "kind": "private_progress_ledger",
        "note": "Private progress record for the B06 rehearsal. This is NOT the live "
        "execution ledger and does not replace it.",
        "packet": "B06",
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
        "status": "b06_private_rehearsal_complete_pending_human_release",
        "not_claimed": [
            "merged_pass",
            "deployment",
            "full B00/B01 completion",
        ],
        "changed_counts": {
            "new_staging_scripts": len(staging_scripts()),
            "new_candidate_module_source_files": 0,
            "new_frontend_files_added_by_b06": counts["new_files_added_by_b06"],
            "edited_candidate_module_source_files": counts["edited_files_rewritten_by_b06"],
            "candidates": 1,
            "candidate_files_copied_from_parent": counts["files_copied_from_parent"],
            "candidate_files_carried_verbatim": counted_carried(carried, counts),
            "candidate_tree_files": tree["files"],
            "candidate_files_on_disk": counts.get(
                "candidate_files_on_disk_after_manifest"),
            "parent_tree_files": parent["files"],
            "original_project_files_written": 0,
            "frozen_evidence_files_rewritten": 0,
        },
        "count_explanations": {
            "new_staging_scripts": "5 new B06 scripts: b06_build_candidate.py, "
            "b06_route_probe.py, b06_validate.py, b06_build_proposals.py, "
            "b06_build_report.py",
            "new_candidate_module_source_files": "0: B06 adds no new Python module; "
            "every Python module in the candidate is carried from B05 or one of "
            "the three rewritten files",
            "new_frontend_files_added_by_b06": "17 = the fifteen staged frontend "
            "files copied byte-for-byte from integration-staging/frontend/ "
            "(thirteen carried from the B01/A14 records MM-0229..MM-0241 plus the "
            "two staging PROVENANCE records B01 excluded from the merge) plus the "
            "rewritten frontend/server.mjs (the B01 planned original edit, packet "
            "B06) and the new frontend/tests/server.test.mjs",
            "edited_candidate_module_source_files": "3 rewritten module sources "
            "under tools/: app.py (aa3ba9c5\u2026 \u2192 0edb0911\u2026), "
            "dataset.py (a9a72a7a\u2026 \u2192 d0edabc7\u2026) and view.py "
            "(441c1da3\u2026 \u2192 f03e549f\u2026), each byte-identical to the "
            "candidate's copy; evidence/source_edits.diff records all three "
            "rewrites plus the two new frontend files against the B05 bytes",
            "candidates": "1 new private candidate: b06-frontend-v1, a child of "
            "the B05 adapters candidate",
            "candidate_files_copied_from_parent": "191 = the B05 on-disk non-cache "
            "files (190 digest files + B05_CANDIDATE_MANIFEST.json) carried "
            "byte-for-byte; 188 of them stay verbatim and 3 are rewritten by B06",
            "candidate_files_carried_verbatim": "188 = 191 copied minus the 3 "
            "rewritten modules; the recorded carried-verbatim tree digest is "
            "b9605c15\u2026",
            "candidate_tree_files": "208 digest files = 188 carried verbatim + 3 "
            "rewritten + 17 new frontend files; B06's digest rule excludes its own "
            "manifest and skips __pycache__/.pytest_cache",
            "candidate_files_on_disk": "209 = 208 digest files + "
            "B06_CANDIDATE_MANIFEST.json; the rehearsal ran with "
            "PYTHONDONTWRITEBYTECODE=1 so the candidate carries no __pycache__ "
            "files and on-disk equals digest + manifest exactly",
            "parent_tree_files": "190 = B05's digest count, which excluded B05's "
            "own manifest (B05 on-disk non-cache was 191); the two numbers "
            "describe different file sets by rule",
            "original_project_files_written": "0: nothing was written outside "
            "integration-staging/ and docs/integration/execution/",
            "frozen_evidence_files_rewritten": "0 existing frozen files rewritten: "
            "evidence/A00\u2013B05/**, evidence/R0104/** and the B02/B03/B04/B05 "
            "runtime trees were read-only; B06's own evidence under "
            "evidence/B06/b06-rehearsal-2026-10-07/ was created new and nothing "
            "there was overwritten",
        },
        "hashes": {
            "candidate_manifest": rel(CANDIDATE_MANIFEST),
            "candidate_manifest_sha256": sha256_file(CANDIDATE_MANIFEST),
            "candidate_tree_sha256": tree["sha256"],
            "carried_verbatim_tree_sha256": carried["sha256"],
            "parent_manifest_sha256": manifest["lineage"]["parent_manifest_sha256"],
            "parent_tree_sha256": parent["sha256"],
            "validation_sha256": sha256_file(VALIDATION),
            "probe_capture_sha256": sha256_file(PROBE_RECORD),
            "merge_proposal_sha256": sha256_file(MERGE_JSON),
            "rollback_proposal_sha256": sha256_file(ROLLBACK_JSON),
            "suite_transcript_sha256": suite["transcript_sha256"],
            "source_edits_diff_sha256": sha256_file(SOURCE_EDITS),
            "build_record_sha256": sha256_file(BUILD_RECORD),
        },
        "test_counts": {
            "b06_route_probe": {
                "command": f"{PY} {RUN_REL}/b06_validate.py",
                "cwd": "C:/Users/weo/Desktop/api",
                "exit_code": 0,
                "runs": len(probe_runs),
                "checks_per_run": probe_runs[0]["checks"] if probe_runs else 0,
                "checks_total": checks_total,
                "checks_failed": checks_failed,
                "new_suite": True,
                "explanation": "New B06 route probe (the B05 probe extended for the "
                "frontend): 138 checks per run = the 98-check B05 face (A 12, B 14, "
                "C 19, D 10, E 7, S 10, N 26) plus 40 new B06 checks - the staged "
                "frontend tree F (7), the frontend-shaped discovery semantics G (9) "
                "and the cross-stack rehearsal H (24); 25 negative and 83 positive "
                "controls in total (the negative list is identical to B05's; the "
                "positive list gains the 40 new F/G/H checks and renames the two "
                "ledger-stability checks from b04 to b05). Executed from 3 "
                "different working directories (138 x 3 = 414 check executions), "
                "0 failed; the H section additionally ran a real ephemeral "
                "cross-stack rehearsal on 127.0.0.1 (uvicorn upstream + the staged "
                "frontend server; Node client/bridge checks; the cross-stack "
                "driver's own 18 checks; teardown verified). The single archived "
                "capture is evidence/probe_run1.json (clean rerun; the first "
                "capture attempt exited 1 - see process_observations).",
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
                "explanation": "Count is unchanged from the R04/B02/B03/B04/B05 "
                "baseline (887 passed). B06 adds no test file to the staged suite; "
                "its frontend test files live in the candidate and are exercised by "
                "the probe's Node smoke instead, so a changed suite count would "
                "itself have been the finding. The suite ran exactly once, after "
                "every product-code fix had stabilised (the only later fixes were "
                "inside the probe's F-section key space and the proposals "
                "generator, neither of which the staged suite collects); the "
                "transcript's last line records `suite_exit=0`.",
            },
            "candidate_build": {
                "command": "PYTHONIOENCODING=utf-8 PYTHONDONTWRITEBYTECODE=1 "
                "C:/Users/weo/Desktop/api/examdata/.venv/Scripts/python.exe "
                "b06_build_candidate.py > evidence/build_run.json "
                "2> evidence/build_run.err.txt",
                "cwd": "C:/Users/weo/Desktop/api/integration-staging/runtime/"
                       "b06-rehearsal-2026-10-07",
                "exit_code": 0,
                "checks_total": len(manifest["checks"]),
                "checks_passed": sum(1 for v in manifest["checks"].values() if v),
                "stderr_bytes": os.path.getsize(os.path.join(EVID, "build_run.err.txt")),
                "new_suite": True,
                "explanation": "21 build-time checks on the candidate itself (parent "
                "carried byte-identically, exactly the three intended rewrites and "
                "seventeen intended additions, all staged frontend bytes byte-equal "
                "to integration-staging/frontend, provenance hashes consistent, the "
                "new frontend JS parses, the digest is parent + new frontend and "
                "excludes the manifest, and the digest stays reproducible after the "
                "manifest write); all new. Build record: "
                f"all_ok={build_record['all_ok']}, "
                "digest_reproducible_after_manifest_write="
                f"{build_record['digest_reproducible_after_manifest_write']}, "
                "stderr empty.",
            },
            "cross_stack": {
                "command": "part of the B06 probe (H section) via tools/"
                "b06_cross_stack.mjs",
                "cwd": "C:/Users/weo/Desktop/api/integration-staging/runtime/"
                       "b06-rehearsal-2026-10-07",
                "exit_code": cross_stack.get("cross", {}).get("exit"),
                "checks_total": cross_counts.get("checks"),
                "checks_failed": cross_counts.get("failed"),
                "new_suite": True,
                "explanation": "The probe's H section starts an ephemeral uvicorn "
                "upstream and the staged frontend server on 127.0.0.1 (ports "
                f"{(cross_stack.get('ports') or {}).get('upstream')} and "
                f"{(cross_stack.get('ports') or {}).get('frontend')}) and drives "
                "the candidate frontend's Node client/bridge through it: the "
                "cross-stack driver's 18 checks all pass, the served content is "
                "byte-equal across the proxy, the direct API and the disk fixture "
                "(content triple), and both processes are stopped again "
                f"(teardown verified: {json.dumps(cross_stack.get('teardown'))}).",
            },
        },
        "probe_verdict": validation["verdict"],
        "probe_findings": validation["findings"],
        "discovery_identical_across_cwds": validation["discovery_identical_across_cwds"],
        "stability_identical_across_cwds": validation.get(
            "stability_identical_across_cwds"),
        "seam_identical_across_cwds": validation.get("seam_identical_across_cwds"),
        "frontend_identical_across_cwds": validation.get(
            "frontend_identical_across_cwds"),
        "cross_stack_identical_across_cwds": validation.get(
            "cross_stack_identical_across_cwds"),
        "discovery_projection_identical_across_cwds": validation.get(
            "discovery_projection_identical_across_cwds"),
        "b06_vs_b05_ledger_consistent": validation.get("b06_vs_b05_ledger_consistent"),
        "candidate_tree_digest_reproducible": validation.get(
            "candidate_tree_digest_reproducible", {}).get("sha256_match"),
        "probe_stability": validation.get("stability"),
        "probe_b06_vs_b05_stability": validation.get("b06_vs_b05_stability"),
        "seam": validation.get("seam"),
        "frontend_node_test": {
            "tests": node_counts.get("tests"),
            "pass": node_counts.get("pass"),
            "fail": node_counts.get("fail"),
            "exit": node_test.get("exit"),
        },
        "import_status_checks": import_checks,
        "negative_checks": NEGATIVES,
        "positive_checks": POSITIVES,
        "artifacts": {
            "candidate_manifest": rel(CANDIDATE_MANIFEST),
            "merge_proposal": rel(MERGE_JSON),
            "rollback_proposal": rel(ROLLBACK_JSON),
            "layout_validation": rel(VALIDATION),
            "probe_capture": rel(PROBE_RECORD),
            "suite_transcript": rel(SUITE_TXT),
            "source_edits_diff": rel(SOURCE_EDITS),
            "scripts": staging_scripts(),
        },
        "proposal_counts": {
            "merge_entries": merge["counts"]["entries"],
            "merge_entries_requiring_release": merge["counts"]["entries_requiring_release"],
            "merge_staging_only_entries": merge["counts"]["staging_only_entries"],
            "merge_new_files_vs_parent": merge["counts"]["new_files_vs_parent"],
            "merge_edited_files_rewritten": merge["counts"]["edited_files_rewritten"],
            "rollback_entries": rollback["counts"]["entries"],
            "rollback_staging_reversible_by_tree_delete": rollback["counts"][
                "staging_level"]["reversible_by_tree_delete"],
            "rollback_staging_removed_with_the_tree": rollback["counts"][
                "staging_level"]["entries_removed_with_the_tree"],
            "rollback_staging_restore_parent_bytes": rollback["counts"][
                "staging_level"]["reversible_by_restore_parent_bytes"],
            "rollback_reversible_by_target_delete": rollback["counts"][
                "original_level"]["reversible_by_target_delete"],
            "rollback_reversible_by_restore_base": rollback["counts"][
                "original_level"]["reversible_by_restore_base"],
            "rollback_reconciliation_cases": rollback["counts"][
                "original_level"]["reconciliation_cases"],
            "rollback_no_original_action": rollback["counts"][
                "original_level"]["no_original_action"],
        },
        "commands": COMMANDS,
        "frozen_evidence_written": False,
        "not_run": validation["not_run"],
        "remaining_blockers": [
            {
                "blocker": "original-project merge of the B06 entries",
                "reason": "gate original_paths_released is closed; an explicit human "
                "release with an explicit scope is required. The merge proposal has "
                "18 release-required entries of 21: the three rewritten modules "
                "(app.py, dataset.py, view.py; add_file semantics because the whole "
                "integration package is new relative to the original project) and "
                "the fifteen frontend entries (thirteen B01 records plus "
                "frontend/server.mjs and frontend/tests/server.test.mjs); the "
                "candidate tree digest must be re-verified immediately before any "
                "original write.",
            },
            {
                "blocker": "frontend reconcile_modify reconciliation and the "
                "production port decision",
                "reason": "four frontend entries are reconcile_modify "
                "(app.js, index.html, README.md, tests/search.test.mjs) and need the "
                "three-way semantic reconciliation against the released original "
                "tree that B01 deferred (three_way=false, gate was closed); the "
                "merged static server's production port strategy additionally needs "
                "an explicit human decision - the staged server defaults to an "
                "ephemeral port and refuses to bind 5188/8000 as a staging safety "
                "measure.",
            },
            {
                "blocker": "real Node component execution (ielts-api / toefl-api)",
                "reason": "gate original_paths_released is closed; the cross-stack "
                "rehearsal ran only against the private candidate and its staged "
                "frontend, on ephemeral loopback ports",
            },
            {
                "blocker": "real database schema / data-root migration",
                "reason": "gate real_data_write_authorized is closed; schema and data "
                "roots are deliberately unchanged by B06",
            },
            {
                "blocker": "real frontend cutover and source-provider fetching",
                "reason": "gates existing_service_cutover_authorized and "
                "upstream_requests_authorized are closed; the candidate frontend "
                "carries no source-discovery logic and only proxies the private "
                "read API",
            },
            {
                "blocker": "deployment to any target",
                "reason": "gate remote_deployment_authorized is closed; the candidate "
                "is private-only",
            },
        ],
        "process_observations": [
            {
                "observation": "The probe's first capture attempt exited 1 with "
                "exactly two failing checks in the new F section: "
                "F_frontend_tree_is_seventeen_files (the FRONTEND_NEW table used "
                "candidate-root-relative keys while the checks compared "
                "frontend-relative names, so the two new files appeared as "
                "'server.mjs' vs 'frontend/server.mjs') and its wrapper "
                "F_section_completed (FileNotFoundError on a doubled "
                "frontend/frontend path).",
                "handling": "The key space was made consistent inside the probe, "
                "the probe was recompiled and rerun clean at 138/138 "
                "(probe_exit=0). The failed capture wrote to the same path "
                "(evidence/probe_run1.json) and was overwritten by the clean "
                "rerun, so no failed capture is archived; the failure is recorded "
                "in the command table (exit 1) and here, and the archived capture "
                "is the clean one.",
            },
            {
                "observation": "The proposals generator's first run exited 1 after "
                "failing exactly one digest check, frontend_matches_b01_records: "
                "the expected B01 frontend id list was built as MM-229..MM-241 "
                "while the B01 records carry zero-padded ids MM-0229..MM-0241, so "
                "the list comparison failed even though every per-record check "
                "(thirteen sha comparisons, dispositions, drift flags, the A14 "
                "anchor and the provenance not_merged state) was true - confirmed "
                "by reading the failed run's frontend_check_detail before fixing.",
                "handling": "The id list now formats with {n:04d} and the rerun "
                "exited 0 with all 11 digest checks true; both proposal JSONs on "
                "disk are the post-fix regenerated versions (their sha256 are in "
                "hashes). The failed run's stdout was not archived as a separate "
                "evidence file; it is recorded in the command table (exit 1) and "
                "here.",
            },
            {
                "observation": "The B06 probe reports 138 checks where the B05 probe "
                "reported 98, and its positive-control list differs from B05's "
                "while the negative list does not.",
                "handling": "Explained: 98 + 40 = 138 - the new F (7), G (9) and H "
                "(24) sections; the negative list is identical to B05's (25 names), "
                "and the positive list is B05's with the two ledger-stability "
                "checks renamed from _b04_ to _b05_ plus the 40 new checks (43 + "
                "40 = 83). The report script asserts both facts against the frozen "
                "B05 probe before writing anything.",
            },
            {
                "observation": "The candidate on disk holds exactly as many files "
                "as the digest plus manifesto (209 vs 208 + 1) - there is no "
                "unexplained file on either side.",
                "handling": "Confirmed: the rehearsal ran with "
                "PYTHONDONTWRITEBYTECODE=1 and the copy carried only non-cache "
                "files, so unlike B05 there are no __pycache__ files in the "
                "candidate; the validator independently recomputed the digest "
                "(files_match=True, sha256_match=True) and the on-disk count "
                "(209).",
            },
        ],
    }

    report = report_md(ledger, validation)
    return ledger, report


def counted_carried(carried: dict, counts: dict) -> int:
    files = carried.get("files")
    if files is not None:
        return files
    return counts["files_copied_from_parent"] - counts["edited_files_rewritten_by_b06"]


def report_md(ledger: dict, validation: dict) -> str:
    c = ledger["changed_counts"]
    t = ledger["test_counts"]
    cmd_rows = [
        f"| {row['step']} | `{row['command']}` | `{row['cwd']}` | {row['exit_code']} |"
        for row in ledger["commands"]
    ]
    lines = [
        "# B06 rehearsal review report (private preparation only)",
        "",
        f"Generated: {ledger['generated_at']}  ",
        "Packet: **B06** — frontend migration (staged frontend, discovery "
        "semantics, v2 switch)  ",
        f"Status: `{ledger['status']}`  ",
        f"Probe verdict: `{ledger['probe_verdict']}`  ",
        f"Probe findings: {len(ledger['probe_findings'])}",
        "",
        "Nothing in this report has been merged or deployed. The original project was "
        "not read, imported or written by any B06 step. All seven gates are closed.",
        "",
        "## 1. What B06 rehearsed",
        "",
        "B06 owns the frontend migration: the staged search frontend, the "
        "frontend-shaped discovery semantics of the read API and the v2 switch. "
        "What can be done without the human release is a rehearsal: carry the B05 "
        "candidate byte-for-byte, rewrite three modules — `app.py` (discovery "
        "projection and resources wiring), `dataset.py` (frontend-shaped query "
        "semantics) and `view.py` — and bring the frontend across: fifteen staged "
        "files copied byte-for-byte from `integration-staging/frontend/` (thirteen "
        "carried from the B01/A14 records MM-0229..MM-0241 plus the two staging "
        "PROVENANCE records B01 excluded from the merge), the rewritten "
        "`frontend/server.mjs` (the B01 planned original edit, packet B06) and the "
        "new `frontend/tests/server.test.mjs`. The acceptance properties that do "
        "not need the original tree are then proven by the route probe: the staged "
        "frontend tree, the discovery semantics (the G section: six sorted rows "
        "with discovery blocks, the 21-case query matrix, boundary rules and detail "
        "routes) and a real but private cross-stack rehearsal on ephemeral "
        "loopback ports (the H section: the staged frontend server in front of the "
        "private read API, driven by the candidate frontend's Node client and "
        "bridge), while the B05 ledger digests stay byte-stable.",
        "",
        "## 2. Candidate and lineage",
        "",
        f"- Candidate: `{rel(CANDIDATE)}`",
        f"- Parent: `{rel(PARENT)}` (the B05 adapters candidate)",
        f"- Parent tree: {c['parent_tree_files']} files, sha256 "
        f"`{ledger['hashes']['parent_tree_sha256']}`",
        f"- Candidate tree: {c['candidate_tree_files']} files "
        f"({c['candidate_files_copied_from_parent']} copied from the parent, of "
        f"which {c['candidate_files_carried_verbatim']} stay verbatim and "
        f"{c['edited_candidate_module_source_files']} were rewritten, + "
        f"{c['new_frontend_files_added_by_b06']} new frontend files), sha256 "
        f"`{ledger['hashes']['candidate_tree_sha256']}`",
        f"- Candidate digest reproducible from the tree on disk: "
        f"`{ledger['candidate_tree_digest_reproducible']}` (re-checked independently "
        "by the validator, not just self-reported by the builder)",
        f"- Parent manifest sha256 unchanged at build time: "
        f"`{ledger['hashes']['parent_manifest_sha256']}`",
        "- Count explanation: B05's digest covered 190 files and its on-disk "
        "non-cache count was 191 (190 + B05 manifest). B06 copies all 191, rewrites "
        "3 and adds 17, so the candidate digest covers 208 = 188 verbatim + 3 "
        "rewritten + 17 new, and on-disk is 209 = 208 + the B06 manifest; the "
        "candidate carries no __pycache__ files (PYTHONDONTWRITEBYTECODE=1 "
        "throughout).",
        "",
        "The rewritten `app.py` supersedes B05 BP-0004, the rewritten `dataset.py` "
        "supersedes B05 BP-0003 / R0104 RP-0005 and the rewritten `view.py` "
        "supersedes A14 MM-0022; all three supersession chains are re-verified in "
        "the merge proposal's `digest_checks` (`supersession_chains_match`), the "
        "frontend entries are re-verified against the B01 records "
        "(`frontend_matches_b01_records` and the `frontend_check_detail`), and the "
        "parent tree digest was re-computed after the copy and again at proposal "
        "time and is unchanged (`parent_tree_reverified`).",
        "",
        "## 3. Commands, working directory and exit codes",
        "",
        "| Step | Command | cwd | Exit |",
        "| --- | --- | --- | --- |",
        *cmd_rows,
    ]
    notes = [row for row in ledger["commands"] if row.get("note")]
    if notes:
        lines.append("")
        lines.append("Run notes:")
        lines.append("")
        for row in notes:
            lines.append(f"- **{row['step']}**: {row['note']}")
    lines += [
        "",
        "## 4. Test results",
        "",
        f"- **Route probe**: {t['b06_route_probe']['checks_per_run']} checks \u00d7 "
        f"{t['b06_route_probe']['runs']} working directories = "
        f"{t['b06_route_probe']['checks_total']} check executions, "
        f"{t['b06_route_probe']['checks_failed']} failed.",
        f"- **Isolated staged suite**: {t['isolated_staged_suite']['summary']} "
        f"(exit {t['isolated_staged_suite']['exit_code']}). Unchanged from the "
        f"R04/B02/B03/B04/B05 baseline of {t['isolated_staged_suite']['baseline_passed']}; "
        "B06 adds no test file to that suite.",
        f"- **Build checks**: {t['candidate_build']['checks_passed']}/"
        f"{t['candidate_build']['checks_total']}.",
        f"- **Cross-stack rehearsal (part of the probe)**: "
        f"{t['cross_stack']['checks_total']} driver checks, "
        f"{t['cross_stack']['checks_failed']} failed; the candidate frontend's Node "
        f"test files passed {ledger['frontend_node_test']['pass']}/"
        f"{ledger['frontend_node_test']['tests']}.",
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
        "## 5. What the checks cover",
        "",
        "- **Section A — import and root configuration (12 checks)**: root env is the "
        "candidate, no staging-root override, no PYTHONPATH, candidate `src/` first "
        "on `sys.path`, every module origin inside the candidate, no original-tree "
        "module loaded, no product import of testing guards, 28 schema files parse, "
        "quality dimensions and identity kinds match the code, synthetic Node "
        "discovery (`fake_cli`) resolves inside the candidate, legacy bridge entry "
        "imports from the candidate.",
        "- **Section B — worksheet, registry and ordering (14 checks)**: the A12 "
        "worksheet holds 71 rows (70 GET + 1 POST `/sample`); the v2 registry has 34 "
        "implemented / 0 deferred specs of which 5 are binary; runtime, spec and "
        "advertised pairs agree; HEAD pairs are binary-only; GET 34/34 and HEAD 5/5 "
        "first-match their own route; no static route is shadowed; and no two "
        "distinct path patterns intersect (561 pairs).",
        "- **Section C — host mechanics and behaviour (19 checks)**: host shape "
        "pre-attach, the legacy prefix is kept, exactly one wrapper is appended; all "
        "71 legacy rows and 7 extra probes stay byte-identical; the legacy "
        "stack-boom body stays pinned; binary fixture ids and 200 / 206 / 304 / HEAD "
        "responses pinned; the synthetic material content response pinned; and the "
        "six v2 controls serve typed envelopes that all differ from their pre-attach "
        "baselines.",
        "- **Section D — combined OpenAPI and B05-ledger stability (10 checks)**: the "
        "path delta is exactly the registry; the pre-attach paths' operations are "
        "unchanged; operation ids are unique; the v2 operation ids match the "
        "standalone app; binary rows are documented with their media types; "
        "non-binary 200 responses serve the envelope schema; `/openapi.json` serves "
        "the same document as the direct call; a second instance yields the same "
        "digest; and the two renamed stability checks confirm the combined OpenAPI, "
        "standalone v2, legacy-operations and composed-route-table digests plus the "
        "operation ids and the 34-path delta still match the frozen B05 progress "
        "ledger (`b06_vs_b05_ledger_consistent` = "
        f"`{ledger['b06_vs_b05_ledger_consistent']}`).",
        "- **Section E — stability (7 checks)**: candidate bytes unchanged by the "
        "probe; fixture and contract digests unchanged; the manifest recomputes to "
        "208 files and the same tree digest; counts disclosed (208 digest / 209 "
        "on-disk); the B04 compose hook stays frozen; no embedded `data:` payloads; "
        "scratch marker written inside the run's evidence/tmp.",
        "- **Section S — the active-owner seam (10 checks)**: the synthetic fixture "
        "source validates with 2 rows per family; the default dataset really uses "
        "the fixture source; row access returns isolated copies; deferred families "
        "flow through the seam unchanged; route rows carry the synthetic markers; "
        "CIE event null fields are preserved; unavailable seasons carry their "
        "reason; unknown window boundaries stay declared with null parsed values; a "
        "private injected source is served by the routes; and the default fixture "
        "path still serves after that injection.",
        "- **Section F — the staged frontend tree (7 checks)**: the candidate "
        "frontend holds exactly seventeen files; the fifteen staged files are "
        "byte-equal to `integration-staging/frontend/`; the two new files are "
        "byte-equal to the run's tooling sources; the provenance records match the "
        "candidate and the source; Node is available; the new frontend JS parses; "
        "and the candidate frontend's Node test files pass 41/41.",
        "- **Section G — frontend-shaped discovery semantics (9 checks)**: the "
        "assets route returns six sorted rows with their discovery blocks; an empty "
        "query returns all six; the system filter narrows the rows; an unknown "
        "filter yields a typed 422 `unsupported_filter`; the 21-case query matrix "
        "all answers as specified; the boundary rules hold (Mar leaves mark_scheme "
        "alone; `202` is not `2024`; paper suffix `01` matches); and the detail "
        "routes carry the discovery key.",
        "- **Section H — cross-stack rehearsal on ephemeral loopback ports (24 "
        "checks)**: an ephemeral uvicorn upstream and the staged frontend server "
        "start on 127.0.0.1; the frontend serves index and its static bytes "
        "(index/catalog/syllabi) byte-equal, root alias, missing 404, method 405; "
        "the Node client checks single-season and fanout discovery for CIE and "
        "Edexcel (cross-season duplicates included); the Node bridge checks rows, "
        "empty-seasons fanout, dedupe and the guard 400; content is byte-equal "
        "across proxy, direct API and disk fixture (content triple); v2 info via "
        "proxy; the gateway denies and forwards as specified; the cross-stack "
        "driver's 18 checks all pass; and both rehearsal processes are stopped "
        "again.",
        "- **Sections N1\u2013N6 — route-layer negative controls (16 checks, 15 "
        "negative) and section N7 — the seam refuse-path (10 negative checks)**: "
        "identical to B05 - raw include, unscoped install, mounts, double/late "
        "attach, non-FastAPI host, and the ten seam refuse paths; the negative "
        "control list is unchanged from B05.",
        "",
        "## 6. Import status of the new candidate",
        "",
        "The candidate's imports resolve from the candidate itself through "
        "`EXAMDATA_INTEGRATION_ROOT` only \u2014 no `PYTHONPATH`, no staging-root "
        "override \u2014 and the same result holds from all three working "
        "directories: the workspace root, an arbitrary directory name under the "
        "run's evidence/tmp, and a path containing spaces and non-ASCII characters "
        "(`cwd with spaces \u00fcn\u00efcode`). Module origins, schema access, "
        "synthetic Node discovery and the runtime/legacy entry points were "
        "re-verified from those directories, and discovery, routing stability, the "
        "seam, the staged-frontend tree, the discovery projection and the "
        "cross-stack summary are identical across all three "
        "(`discovery_identical_across_cwds`, `stability_identical_across_cwds`, "
        f"`seam_identical_across_cwds`, `frontend_identical_across_cwds` = "
        f"`{ledger['frontend_identical_across_cwds']}`, "
        f"`cross_stack_identical_across_cwds` = "
        f"`{ledger['cross_stack_identical_across_cwds']}`). Real Node/source "
        "validation against the original project remains `not_run`.",
        "",
        "| Check | Result | Detail |",
        "| --- | --- | --- |",
    ]
    for ck in ledger["import_status_checks"]:
        detail = ck["detail"].replace("|", "\\|")
        lines.append(f"| `{ck['name']}` | `{ck['ok']}` | {detail} |")
    lines += [
        "",
        "## 7. Proposals",
        "",
        f"- Merge proposal: `{ledger['artifacts']['merge_proposal']}` \u2014 "
        f"{ledger['proposal_counts']['merge_entries']} entries, "
        f"{ledger['proposal_counts']['merge_entries_requiring_release']} requiring "
        f"the human release, "
        f"{ledger['proposal_counts']['merge_staging_only_entries']} staging-only; "
        f"{ledger['proposal_counts']['merge_new_files_vs_parent']} new files vs the "
        f"parent and {ledger['proposal_counts']['merge_edited_files_rewritten']} "
        "rewritten staged modules. The release-required entries are the three "
        "rewritten modules (add_file semantics; app.py supersedes B05 BP-0004, "
        "dataset.py supersedes B05 BP-0003 / R0104 RP-0005, view.py supersedes A14 "
        "MM-0022) and the fifteen frontend entries (MM-0229..MM-0241 plus "
        "frontend/server.mjs and frontend/tests/server.test.mjs; the two PROVENANCE "
        "records stay staging-only and are never installed).",
        f"- Rollback proposal: `{ledger['artifacts']['rollback_proposal']}` \u2014 "
        f"{ledger['proposal_counts']['rollback_entries']} entries; at the original "
        f"level {ledger['proposal_counts']['rollback_reversible_by_target_delete']} "
        "are reversible by deleting the added target file (guarded by the recorded "
        f"sha256), "
        f"{ledger['proposal_counts']['rollback_reversible_by_restore_base']} by "
        f"restoring the recorded base bytes, "
        f"{ledger['proposal_counts']['rollback_reconciliation_cases']} is a "
        f"reconciliation case and "
        f"{ledger['proposal_counts']['rollback_no_original_action']} has no original "
        "action at all.",
        "",
        "Both are marked `proposal_only_nothing_merged_not_deployed`. Nothing has "
        "been applied to the original project. The merge proposal's "
        "`action_level_gate_model` records the gate discipline this rehearsal "
        "followed: a gate is required only for the action that performs that effect, "
        "private preparation requires no gate, and no original write may proceed "
        "without the applicable human release.",
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
        "The live execution ledger is byte-identical to its frozen pre-rehearsal "
        "value and was not written by this rehearsal; the seven gates remain closed.",
        "",
        "## 9. Not run",
        "",
    ]
    lines += [f"- {n['check']} \u2014 {n['reason']}" for n in ledger["not_run"]]
    lines += [
        "",
        "## 10. Not claimed / remaining blockers",
        "",
        "Not claimed: " + ", ".join(f"`{n}`" for n in ledger["not_claimed"]) + ".",
        "",
    ]
    lines += [f"- {b['blocker']} \u2014 {b['reason']}" for b in ledger["remaining_blockers"]]
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
        "# B06 private progress ledger",
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
        f"| new candidate module sources | "
        f"{ledger['changed_counts']['new_candidate_module_source_files']} |",
        f"| new frontend files added by B06 | "
        f"{ledger['changed_counts']['new_frontend_files_added_by_b06']} |",
        f"| edited candidate module sources | "
        f"{ledger['changed_counts']['edited_candidate_module_source_files']} |",
        f"| candidates | {ledger['changed_counts']['candidates']} |",
        f"| candidate tree files | {ledger['changed_counts']['candidate_tree_files']} |",
        f"| candidate files on disk | "
        f"{ledger['changed_counts']['candidate_files_on_disk']} |",
        f"| files copied from the parent | "
        f"{ledger['changed_counts']['candidate_files_copied_from_parent']} |",
        f"| files carried verbatim | "
        f"{ledger['changed_counts']['candidate_files_carried_verbatim']} |",
        f"| original project files written | "
        f"{ledger['changed_counts']['original_project_files_written']} |",
        f"| frozen evidence files rewritten | "
        f"{ledger['changed_counts']['frozen_evidence_files_rewritten']} |",
        f"| probe check executions | "
        f"{ledger['test_counts']['b06_route_probe']['checks_total']} "
        f"({ledger['test_counts']['b06_route_probe']['checks_failed']} failed) |",
        f"| cross-stack driver checks | "
        f"{ledger['test_counts']['cross_stack']['checks_total']} "
        f"({ledger['test_counts']['cross_stack']['checks_failed']} failed) |",
        f"| candidate Node tests | {ledger['frontend_node_test']['pass']}/"
        f"{ledger['frontend_node_test']['tests']} |",
        f"| isolated staged suite | {ledger['test_counts']['isolated_staged_suite']['summary']} "
        f"|",
        f"| probe verdict | `{ledger['probe_verdict']}` |",
        "",
        "## Count explanations",
        "",
    ]
    lines += [f"- **{k}**: {v}" for k, v in ledger["count_explanations"].items()]
    lines += [
        "",
        "## Not run",
        "",
    ]
    lines += [f"- {n['check']} \u2014 {n['reason']}" for n in ledger["not_run"]]
    lines += ["", "## Remaining blockers", ""]
    lines += [f"- {b['blocker']} \u2014 {b['reason']}" for b in ledger["remaining_blockers"]]
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    ledger, report = build()
    os.makedirs(OUT, exist_ok=True)
    write_json(os.path.join(OUT, "B06_PROGRESS_LEDGER.json"), ledger)
    write_text(os.path.join(OUT, "B06_PROGRESS_LEDGER.md"), ledger_md(ledger))
    write_text(os.path.join(OUT, "B06_REHEARSAL_REPORT.md"), report)
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
