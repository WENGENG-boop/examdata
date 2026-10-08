"""Build the B07 rehearsal review report and the B07 private progress ledger.

Everything here is derived from artifacts already on disk (the candidate
manifest, the frozen layout validation, the archived probe captures, the
smoke record, the proposal JSONs and the staged-suite transcript), so no
count and no hash is typed by hand. This writes only inside
docs/integration/execution/; frozen evidence is read, never rewritten.

Two facts of this rehearsal are recorded deliberately and not hidden:

* the first build and smoke passes exposed an over-redaction defect in the
  new operations view's public projection (published.py rendered the internal
  schema tag and a slash-bearing denominator label as redacted path strings);
  the two edits that fixed it, the rebuild and the clean second smoke pass
  are recorded in the command table and in ``process_observations``, and the
  superseded first tree digest is named there;
* the probe's first capture attempt exited 1 with exactly one failing check,
  ``J_section_completed`` (a probe-internal attribute name); unlike the B06
  rehearsal the failed capture was not overwritten - it is kept at
  ``evidence/probe_run1.json`` and the clean rerun wrote
  ``evidence/probe_run2.json``.
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
FROZEN_EVID = os.path.join(OUT, "evidence", "B07", "b07-rehearsal-2026-10-07")
B06_FROZEN_PROBE = os.path.join(
    OUT, "evidence", "B06", "b06-rehearsal-2026-10-07", "probe_cwd1.json")

CST = timezone(timedelta(hours=8))

CANDIDATE = os.path.join(RUN, "candidates", "b07-operations-v1")
CANDIDATE_MANIFEST = os.path.join(CANDIDATE, "B07_CANDIDATE_MANIFEST.json")
PARENT = os.path.join(
    RUN, "..", "b06-rehearsal-2026-10-07", "candidates", "b06-frontend-v1",
)
VALIDATION = os.path.join(FROZEN_EVID, "B07_LAYOUT_VALIDATION.json")
SUITE_TXT = os.path.join(EVID, "isolated_staged_suite.txt")
SOURCE_EDITS = os.path.join(EVID, "source_edits.diff")
BUILD_RECORD = os.path.join(EVID, "build_run.json")
PROBE_RECORD = os.path.join(EVID, "probe_run2.json")
PROBE_FAILED = os.path.join(EVID, "probe_run1.json")
SMOKE_RECORD = os.path.join(EVID, "smoke_import.json")

MERGE_JSON = os.path.join(OUT, "B07_MERGE_PROPOSAL.json")
ROLLBACK_JSON = os.path.join(OUT, "B07_ROLLBACK_PROPOSAL.json")
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
RUN_REL = "integration-staging/runtime/b07-rehearsal-2026-10-07"
CAND_ABS = f"{WS_ABS}/{RUN_REL}/candidates/b07-operations-v1"
PROBE_ENV = (
    'B07_CANDIDATE_ROOT="$PWD/candidates/b07-operations-v1" '
    "B07_WORKSPACE_ROOT=\"" + WS_ABS + "\" "
    "B07_TMP_DIR=\"$PWD/evidence/tmp\" "
    "EXAMDATA_INTEGRATION_ROOT=\"$PWD/candidates/b07-operations-v1\" "
    "EXAMDATA_OPERATIONS_ROOT=\"$PWD/candidates/b07-operations-v1/"
    "fixtures/synthetic/operations/operations-root\" "
    "EXAMDATA_API_KEY=REDACTED_LOCAL_CREDENTIAL"
)
PROBE_RUN1 = (
    "PYTHONDONTWRITEBYTECODE=1 PYTHONIOENCODING=utf-8 "
    f'"{PY_ABS}" b07_route_probe.py '
    "1> evidence/probe_run1.json 2> evidence/probe_run1.err"
)
PROBE_RUN2 = (
    "PYTHONDONTWRITEBYTECODE=1 PYTHONIOENCODING=utf-8 "
    f'"{PY_ABS}" b07_route_probe.py '
    "1> evidence/probe_run2.json 2> evidence/probe_run2.err"
)

COMMANDS = [
    {
        "step": "build candidate, first pass",
        "command": "PYTHONIOENCODING=utf-8 PYTHONDONTWRITEBYTECODE=1 "
                   "C:/Users/weo/Desktop/api/examdata/.venv/Scripts/python.exe "
                   "b07_build_candidate.py 1> evidence/build_run.json "
                   "2> evidence/build_run.err; echo EXIT=$?",
        "cwd": "C:/Users/weo/Desktop/api/integration-staging/runtime/"
               "b07-rehearsal-2026-10-07",
        "exit_code": 0,
        "note": "first pass; its candidate tree digest was 7a1985b7\u2026 but the "
                "pass was superseded by the rebuild that followed the "
                "published.py over-redaction fix; the recorded build_run.json "
                "is the second pass",
    },
    {
        "step": "smoke import, first pass",
        "command": "PYTHONIOENCODING=utf-8 PYTHONDONTWRITEBYTECODE=1 "
                   "C:/Users/weo/Desktop/api/examdata/.venv/Scripts/python.exe "
                   "b07_smoke_import.py 1> evidence/smoke_import.json "
                   "2> evidence/smoke_import.err; echo EXIT=$?",
        "cwd": "C:/Users/weo/Desktop/api/integration-staging/runtime/"
               "b07-rehearsal-2026-10-07",
        "exit_code": 0,
        "note": "first pass; it exposed the over-redacted public projection of "
                "the new operations view (the internal schema tag and a "
                "slash-bearing denominator label were rendered as redacted "
                "path strings), which was fixed with two edits inside "
                "tools/published.py and rebuilt",
    },
    {
        "step": "build candidate, second pass (the recorded build)",
        "command": "PYTHONIOENCODING=utf-8 PYTHONDONTWRITEBYTECODE=1 "
                   "C:/Users/weo/Desktop/api/examdata/.venv/Scripts/python.exe "
                   "b07_build_candidate.py 1> evidence/build_run.json "
                   "2> evidence/build_run.err; echo EXIT=$?",
        "cwd": "C:/Users/weo/Desktop/api/integration-staging/runtime/"
               "b07-rehearsal-2026-10-07",
        "exit_code": 0,
        "note": "recorded pass after the fix; candidate tree digest 5df25984\u2026; "
                "evidence/build_run.json is this pass (all_ok=True, checks "
                "21/21, digest reproducible after the manifest write, stderr "
                "empty)",
    },
    {
        "step": "smoke import, second pass (the recorded smoke)",
        "command": "PYTHONIOENCODING=utf-8 PYTHONDONTWRITEBYTECODE=1 "
                   "C:/Users/weo/Desktop/api/examdata/.venv/Scripts/python.exe "
                   "b07_smoke_import.py 1> evidence/smoke_import.json "
                   "2> evidence/smoke_import.err; echo EXIT=$?",
        "cwd": "C:/Users/weo/Desktop/api/integration-staging/runtime/"
               "b07-rehearsal-2026-10-07",
        "exit_code": 0,
        "note": "clean pass; the public projection no longer carries the "
                "internal schema tag and denominator labels use '#' "
                "separators; evidence/smoke_import.json is this pass "
                "(structural_ok=True, stderr empty)",
    },
    {
        "step": "route probe, first capture attempt (kept)",
        "command": f"{PROBE_ENV} {PROBE_RUN1}; echo \"probe_exit=$?\"",
        "cwd": "C:/Users/weo/Desktop/api/integration-staging/runtime/"
               "b07-rehearsal-2026-10-07",
        "exit_code": 1,
        "note": "failed exactly one check, J_section_completed, on a "
                "probe-internal attribute name ('JobView' object has no "
                "attribute 'public_id'); 145 checks were recorded (85 positive "
                "/ 26 negative) before the J section aborted; this failed "
                "capture is kept at evidence/probe_run1.json and was NOT "
                "overwritten by the clean rerun",
    },
    {
        "step": "route probe, clean rerun (the archived capture)",
        "command": f"{PROBE_ENV} {PROBE_RUN2}; echo \"probe_exit=$?\"",
        "cwd": "C:/Users/weo/Desktop/api/integration-staging/runtime/"
               "b07-rehearsal-2026-10-07",
        "exit_code": 0,
        "note": "174/174 checks clean with 30 negatives / 111 positives; a "
                "one-line fix inside the probe and a scratch preflight in "
                "evidence/tmp (removed at cleanup) preceded this rerun; this "
                "rerun is evidence/probe_run2.json; stderr holds only the "
                "Starlette deprecation warning",
    },
    {
        "step": "validate (probe from 3 cwds)",
        "command": "rm -rf integration-staging/runtime/b07-rehearsal-2026-10-07"
                   "/__pycache__ && cd integration-staging/runtime/"
                   "b07-rehearsal-2026-10-07 && PYTHONIOENCODING=utf-8 "
                   "PYTHONDONTWRITEBYTECODE=1 "
                   "C:/Users/weo/Desktop/api/examdata/.venv/Scripts/python.exe "
                   "b07_validate.py; echo \"VALIDATE_EXIT=$?\"",
        "cwd": "C:/Users/weo/Desktop/api",
        "exit_code": 0,
        "note": "the validator itself writes the frozen evidence under "
                "docs/integration/execution/evidence/B07/b07-rehearsal-2026-10-07/"
                "(B07_LAYOUT_VALIDATION.json, b07_validation_run.txt, "
                "probe_cwd1..3.json); all three runs 174/174 from the "
                "workspace root, an arbitrary directory name and a path with "
                "spaces and non-ASCII characters",
    },
    {
        "step": "isolated staged suite",
        "command": "bash integration-staging/tools/run_staged_tests.sh -q "
                   "(background task; its output log was copied to "
                   "integration-staging/runtime/b07-rehearsal-2026-10-07/"
                   "evidence/isolated_staged_suite.txt and suite_exit=0 "
                   "appended)",
        "cwd": "C:/Users/weo/Desktop/api",
        "exit_code": 0,
        "note": "887 passed, 1 warning in 43.72s; the transcript's last line "
                "records suite_exit=0; ran exactly once, after every "
                "product-code change had stabilised",
    },
    {
        "step": "merge + rollback proposals",
        "command": "PYTHONIOENCODING=utf-8 PYTHONDONTWRITEBYTECODE=1 "
                   "C:/Users/weo/Desktop/api/examdata/.venv/Scripts/python.exe "
                   "b07_build_proposals.py; echo \"EXIT=$?\"",
        "cwd": "C:/Users/weo/Desktop/api/integration-staging/runtime/"
               "b07-rehearsal-2026-10-07",
        "exit_code": 0,
        "note": "clean on the first run (no failed-run history in this "
                "packet); all 11 digest checks true; 15 entries, 14 requiring "
                "the human release, 1 staging-only",
    },
    {
        "step": "review report + progress ledger",
        "command": "PYTHONIOENCODING=utf-8 PYTHONDONTWRITEBYTECODE=1 "
                   "C:/Users/weo/Desktop/api/examdata/.venv/Scripts/python.exe "
                   "b07_build_report.py; echo \"EXIT=$?\"",
        "cwd": "C:/Users/weo/Desktop/api/integration-staging/runtime/"
               "b07-rehearsal-2026-10-07",
        "exit_code": 0,
        "note": "writes B07_PROGRESS_LEDGER.json, B07_PROGRESS_LEDGER.md and "
                "B07_REHEARSAL_REPORT.md into docs/integration/execution/; "
                "frozen evidence is read, never rewritten",
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
        "b07_build_candidate.py",
        "b07_route_probe.py",
        "b07_smoke_import.py",
        "b07_validate.py",
        "b07_build_proposals.py",
        "b07_build_report.py",
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
    "J_operations_disabled_when_unconfigured",
    "J_route_leaves_carry_no_raw_paths_or_secrets",
    "J_disabled_app_has_no_operations_key",
    "J_missing_root_is_reported_not_raised",
    "J_operations_modules_expose_no_write_surface",
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
    "D_stability_digests_match_b06_ledger",
    "D_stability_ids_and_delta_match_b06_ledger",
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
    "J_operations_enabled_from_environment",
    "J_jobs_by_id_serves_current_only",
    "J_stages_reflect_the_checkpoints",
    "J_superseded_only_in_superseded_lists",
    "J_no_job_conflicts",
    "J_view_scanned_once_and_clean",
    "J_route_9191_stays_stopped_and_flags_resume",
    "J_route_9191_error_is_fixture_redacted",
    "J_route_9191_has_no_superseded_or_conflicts",
    "J_operations_warning_appended_on_route",
    "J_route_9191_envelope_completeness",
    "J_route_leaves_expose_the_placeholders",
    "J_route_8888_current_running_old_stopped_only_superseded",
    "J_deferred_job_fixture_still_served",
    "J_coverage_route_items_gaps_identical_with_and_without_operations",
    "J_route_coverage_warning_appended",
    "J_route_root_block_disclosed",
    "J_checkpoints_seven_rows_five_current_two_superseded",
    "J_checkpoint_payload_hashes_recompute_7_of_7",
    "J_checkpoint_payload_hashes_pin_three",
    "J_unsupported_checkpoint_recorded_unknown",
    "J_checkpoints_conflicts_empty",
    "J_jobs_briefs_show_stopped_and_superseded_states",
    "J_published_four_rows_and_schema_absent",
    "J_published_rows_pass_the_coverage_contract",
    "J_published_statuses_pinned",
    "J_computed_at_is_utc_second_precision",
    "J_candidate_tree_unchanged_by_the_view",
]


def build() -> tuple[dict, str]:
    manifest = load_json(CANDIDATE_MANIFEST)
    validation = load_json(VALIDATION)
    merge = load_json(MERGE_JSON)
    rollback = load_json(ROLLBACK_JSON)
    live = load_json(LEDGER)
    probe = load_json(PROBE_RECORD)
    probe_failed = load_json(PROBE_FAILED)
    build_record = load_json(BUILD_RECORD)
    smoke = load_json(SMOKE_RECORD)
    b06_probe = load_json(B06_FROZEN_PROBE)["report"]

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
    if not check_names:
        raise SystemExit("no frozen probe_cwd captures found in the B07 evidence")

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

    probe_counts = probe["counts"]
    if not probe.get("ok") or not (
        probe_counts["checks"] == 174
        and probe_counts["checks_failed"] == 0
        and probe_counts["negative_checks"] == 30
        and probe_counts["positive_checks"] == 111
    ):
        raise SystemExit("archived probe capture is not the clean 174/0/30/111 run")
    if probe_counts["checks"] != probe_runs[0]["checks"]:
        raise SystemExit("archived probe capture disagrees with the validation runs")

    failed_counts = probe_failed["counts"]
    failed_checks = [c["name"] for c in probe_failed["checks"] if not c.get("ok")]
    fail_detail = ""
    for c in probe_failed["checks"]:
        if not c.get("ok"):
            fail_detail = c.get("detail") or ""
    if (
        failed_checks != ["J_section_completed"]
        or not (
            failed_counts["checks"] == 145
            and failed_counts["checks_failed"] == 1
            and failed_counts["negative_checks"] == 26
            and failed_counts["positive_checks"] == 85
        )
        or "public_id" not in fail_detail
    ):
        raise SystemExit(
            "probe_run1.json is not the recorded single-failure J capture "
            "(145 checks / 1 failed / 26 negative / 85 positive)"
        )

    b06_negatives = b06_probe["negative_checks"]
    b06_positives = b06_probe["positive_checks"]
    renamed = {
        "D_stability_digests_match_b06_ledger":
            "D_stability_digests_match_b05_ledger",
        "D_stability_ids_and_delta_match_b06_ledger":
            "D_stability_ids_and_delta_match_b05_ledger",
    }
    if [renamed.get(n, n) for n in POSITIVES if not n.startswith("J_")] != b06_positives:
        raise SystemExit(
            "the B07 positive-control delta is not just the two ledger renames "
            "plus the new J section; refusing to claim it is"
        )
    if NEGATIVES[:len(b06_negatives)] != b06_negatives:
        raise SystemExit(
            "the B07 negative-control list is not the B06 list plus the J "
            "negatives; refusing to claim it is"
        )
    j_pos = [n for n in POSITIVES if n.startswith("J_")]
    j_neg = [n for n in NEGATIVES if n.startswith("J_")]
    if len(j_pos) != 28 or len(j_neg) != 5:
        raise SystemExit(
            f"expected 28 positive and 5 negative J checks, found "
            f"{len(j_pos)} and {len(j_neg)}"
        )
    if len(POSITIVES) != len(b06_positives) + 28:
        raise SystemExit(
            "the B07 positive-control count delta is not the J section; "
            "refusing to claim it is"
        )

    by_name = {c["name"]: c for c in probe_first["checks"]}
    for n in (
        "A_operations_root_is_candidate_fixture",
        "A_api_key_is_labelled_synthetic_control",
        "A_operations_root_env_name_pinned",
    ):
        c = by_name.get(n)
        if c is None or not c["ok"]:
            raise SystemExit(f"new B07 root-configuration check missing or failed: {n}")
    if len(import_checks) != 15:
        raise SystemExit(f"expected 15 A-section import checks, found {len(import_checks)}")
    if len(probe_runs) != 3:
        raise SystemExit(f"expected 3 probe runs, found {len(probe_runs)}")

    counts = manifest["counts"]
    tree = manifest["candidate_tree"]
    carried = manifest["carried_verbatim_tree"]
    parent = manifest["lineage"]["parent_tree"]
    new_modules = manifest["operations"]["new_modules"]
    edited = manifest["edited_files"]

    build_checks = build_record["checks"]
    if (
        len(build_checks) != 21
        or not all(build_checks.values())
        or not build_record["all_ok"]
        or not build_record["digest_reproducible_after_manifest_write"]
    ):
        raise SystemExit("build record is not the clean 21/21 reproducible pass")
    if (
        len(manifest["checks"]) != 21
        or sum(1 for v in manifest["checks"].values() if v) != 21
    ):
        raise SystemExit("candidate manifest checks are not 21/21")

    frontend = validation["frontend"]
    node_test = frontend.get("node_test")
    if not node_test or not node_test.get("counts"):
        raise SystemExit("validation record is missing the frontend node_test block")
    node_counts = node_test["counts"]
    if not (
        node_test.get("exit") == 0
        and node_counts.get("tests") == 41
        and node_counts.get("pass") == 41
        and node_counts.get("fail") == 0
    ):
        raise SystemExit("frontend node test block is not the recorded 41/41 pass")

    cross_stack = validation["cross_stack"]
    cross = cross_stack.get("cross") or {}
    cross_counts = cross.get("counts") or {}
    teardown = cross_stack.get("teardown") or {}
    if not (
        cross.get("exit") == 0
        and cross.get("ok") is True
        and cross_counts.get("checks") == 18
        and cross_counts.get("failed") == 0
        and teardown.get("upstream_stopped") is True
    ):
        raise SystemExit("validation cross-stack summary is not the recorded clean 18/0")

    smoke_counts = smoke["counts"]
    if smoke_counts != {
        "observations": 7,
        "coverage_rows": 7,
        "current_rows": 5,
        "superseded_rows": 2,
        "job_rows": 7,
        "published_rows": 4,
    } or not smoke.get("structural_ok"):
        raise SystemExit("smoke record is not the expected 7/7/5/2/7/4 structural pass")

    edited_desc = " and ".join(
        f"{os.path.basename(e['path'])} ({e['parent_sha256'][:8]}\u2026 \u2192 "
        f"{e['written_sha256'][:8]}\u2026)"
        for e in edited
    )
    module_desc = " and ".join(
        f"{os.path.basename(m['path'])} ({m['written_sha256'][:8]}\u2026)"
        for m in new_modules
    )

    ledger = {
        "ledger_version": "b07-private-progress-ledger/1",
        "generated_by": rel(os.path.abspath(__file__)),
        "generated_at": now,
        "kind": "private_progress_ledger",
        "note": "Private progress record for the B07 rehearsal. This is NOT the live "
        "execution ledger and does not replace it.",
        "packet": "B07",
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
        "status": "b07_private_rehearsal_complete_pending_human_release",
        "not_claimed": [
            "merged_pass",
            "deployment",
            "full B00/B01 completion",
        ],
        "changed_counts": {
            "new_staging_scripts": len(staging_scripts()),
            "new_candidate_module_source_files": len(new_modules),
            "new_operations_files_added_by_b07": counts["new_files_added_by_b07"],
            "edited_candidate_module_source_files": counts["edited_files_rewritten_by_b07"],
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
            "new_staging_scripts": "6 new B07 scripts: b07_build_candidate.py, "
            "b07_route_probe.py, b07_smoke_import.py, b07_validate.py, "
            "b07_build_proposals.py, b07_build_report.py (plus the rewritten "
            "module sources and fixtures authored under tools/, which count as "
            "candidate inputs, not as scripts)",
            "new_candidate_module_source_files": f"2 = the new operations package "
            f"modules against the parent: {module_desc}, authored under tools/ "
            "and written byte-identical into "
            "src/examdata/integration/operations/ (source_sha256 == "
            "written_sha256 in the manifest)",
            "new_operations_files_added_by_b07": "12 = 2 new module sources "
            "(operations/jobs.py, operations/published.py) + 10 labelled "
            "synthetic operations fixture files under "
            "fixtures/synthetic/operations/operations-root/ (PROVENANCE.json, "
            "README.md, expected-manifest.json and seven batch checkpoint "
            "files: run-ok, run-ok-stale, run-partial, unsupported, "
            "cie-batch-8888, cie-batch-8888-stale, cie-location-batch); the "
            "fixtures are explicitly labelled synthetic control data, never "
            "real records",
            "edited_candidate_module_source_files": "2 rewritten module sources "
            f"under tools/: {edited_desc}, each byte-identical to the "
            "candidate's copy; evidence/source_edits.diff records both "
            "rewrites plus the two new modules and the ten fixtures against "
            "the B06 bytes (14 sections)",
            "candidates": "1 new private candidate: b07-operations-v1, a child "
            "of the B06 frontend candidate",
            "candidate_files_copied_from_parent": "209 = the B06 on-disk "
            "non-cache files (208 digest files + B06_CANDIDATE_MANIFEST.json) "
            "carried byte-for-byte; 207 of them stay verbatim and 2 are "
            "rewritten by B07",
            "candidate_files_carried_verbatim": f"207 = 209 copied minus the 2 "
            f"rewritten modules; the recorded carried-verbatim tree digest is "
            f"{carried['sha256'][:8]}\u2026",
            "candidate_tree_files": "221 digest files = 207 carried verbatim + 2 "
            "rewritten + 12 new (2 modules + 10 fixtures); B07's digest rule "
            "excludes its own manifest and skips __pycache__/.pytest_cache",
            "candidate_files_on_disk": "222 = 221 digest files + "
            "B07_CANDIDATE_MANIFEST.json; the rehearsal ran with "
            "PYTHONDONTWRITEBYTECODE=1 so the candidate carries no __pycache__ "
            "files and on-disk equals digest + manifest exactly",
            "parent_tree_files": "208 = B06's digest count, which excluded "
            "B06's own manifest (B06 on-disk non-cache was 209); the two "
            "numbers describe different file sets by rule",
            "original_project_files_written": "0: nothing was written outside "
            "integration-staging/ and docs/integration/execution/",
            "frozen_evidence_files_rewritten": "0 existing frozen files rewritten: "
            "evidence/A00\u2013B06/**, evidence/R0104/** and the B02\u2013B06 runtime "
            "trees were read-only; B07's own evidence under "
            "evidence/B07/b07-rehearsal-2026-10-07/ was created new and nothing "
            "there was overwritten; the failed probe capture is a new file kept "
            "at evidence/probe_run1.json and the clean rerun wrote "
            "evidence/probe_run2.json, not over it",
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
            "probe_failed_capture_sha256": sha256_file(PROBE_FAILED),
            "smoke_record_sha256": sha256_file(SMOKE_RECORD),
            "merge_proposal_sha256": sha256_file(MERGE_JSON),
            "rollback_proposal_sha256": sha256_file(ROLLBACK_JSON),
            "suite_transcript_sha256": suite["transcript_sha256"],
            "source_edits_diff_sha256": sha256_file(SOURCE_EDITS),
            "build_record_sha256": sha256_file(BUILD_RECORD),
        },
        "test_counts": {
            "b07_route_probe": {
                "command": f"{PY} {RUN_REL}/b07_validate.py",
                "cwd": "C:/Users/weo/Desktop/api",
                "exit_code": 0,
                "runs": len(probe_runs),
                "checks_per_run": probe_runs[0]["checks"] if probe_runs else 0,
                "checks_total": checks_total,
                "checks_failed": checks_failed,
                "new_suite": True,
                "explanation": "New B07 route probe (the B06 probe extended for the "
                "operations view): 174 checks per run = the 138-check B06 face "
                "(A 12, B 14, C 19, D 10, E 7, F 7, G 9, H 24, S 10, N 26) plus "
                "36 new B07 checks - the three new A root-configuration checks "
                "and the J operations section (33 checks: 28 positive + 5 "
                "negative controls); 30 negative and 111 positive controls in "
                "total (the negative list extends B06's 25 with the five J "
                "negatives; the positive list is B06's 83 with the two "
                "ledger-stability checks renamed from _b05_ to _b06_ plus the 28 "
                "J checks). Executed from 3 different working directories "
                "(174 x 3 = 522 check executions), 0 failed; the J section "
                "drives the synthetic operations fixture root through the "
                "candidate's operations view. The archived capture is "
                "evidence/probe_run2.json (the clean rerun); the first capture "
                "attempt exited 1 and is kept, not overwritten, at "
                "evidence/probe_run1.json - see process_observations.",
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
                "explanation": "Count is unchanged from the R04/B02/B03/B04/B05/B06 "
                "baseline (887 passed). B07 adds no test file to the staged "
                "suite; its operations checks live in the probe's J section and "
                "the smoke tool, so a changed suite count would itself have been "
                "the finding. The suite ran exactly once, after every "
                "product-code change had stabilised (the published.py fix and "
                "rebuild preceded it; the only later code change was a "
                "probe-internal attribute name the staged suite does not "
                "collect); the transcript's last line records `suite_exit=0`.",
            },
            "candidate_build": {
                "command": "PYTHONIOENCODING=utf-8 PYTHONDONTWRITEBYTECODE=1 "
                "C:/Users/weo/Desktop/api/examdata/.venv/Scripts/python.exe "
                "b07_build_candidate.py 1> evidence/build_run.json "
                "2> evidence/build_run.err; echo EXIT=$?",
                "cwd": "C:/Users/weo/Desktop/api/integration-staging/runtime/"
                       "b07-rehearsal-2026-10-07",
                "exit_code": 0,
                "checks_total": len(manifest["checks"]),
                "checks_passed": sum(1 for v in manifest["checks"].values() if v),
                "stderr_bytes": os.path.getsize(os.path.join(EVID, "build_run.err")),
                "new_suite": True,
                "explanation": "21 build-time checks on the candidate itself "
                "(parent carried byte-identically, exactly the two intended "
                "rewrites and twelve intended additions, the ten fixture files "
                "byte-equal to the run's tools/operations-root, provenance "
                "hashes consistent, the two new modules compile, the digest is "
                "parent + new files and excludes the manifest, and the digest "
                "stays reproducible after the manifest write); all new. Build "
                "record: all_ok="
                f"{build_record['all_ok']}, "
                "digest_reproducible_after_manifest_write="
                f"{build_record['digest_reproducible_after_manifest_write']}, "
                "stderr empty. The build ran twice: the first pass "
                "(tree 7a1985b7\u2026) was superseded by the published.py "
                "over-redaction fix and rebuilt to 5df25984\u2026; this record is "
                "the second pass - see process_observations.",
            },
            "cross_stack": {
                "command": "part of the B07 probe (H section) via tools/"
                "b07_cross_stack.mjs",
                "cwd": "C:/Users/weo/Desktop/api/integration-staging/runtime/"
                       "b07-rehearsal-2026-10-07",
                "exit_code": cross.get("exit"),
                "checks_total": cross_counts.get("checks"),
                "checks_failed": cross_counts.get("failed"),
                "new_suite": True,
                "explanation": "The probe's H section starts an ephemeral uvicorn "
                "upstream and the staged frontend server on 127.0.0.1 "
                "(ephemeral loopback ports) and drives the candidate "
                "frontend's Node client/bridge through it: the cross-stack "
                "driver's 18 checks all pass, the served content is byte-equal "
                "across the proxy, the direct API and the disk fixture "
                "(content triple), the banner was seen and both processes are "
                "stopped again "
                f"(teardown verified: {json.dumps(cross_stack.get('teardown'))}).",
            },
            "smoke_import": {
                "command": "PYTHONIOENCODING=utf-8 PYTHONDONTWRITEBYTECODE=1 "
                "C:/Users/weo/Desktop/api/examdata/.venv/Scripts/python.exe "
                "b07_smoke_import.py 1> evidence/smoke_import.json "
                "2> evidence/smoke_import.err; echo EXIT=$?",
                "cwd": "C:/Users/weo/Desktop/api/integration-staging/runtime/"
                       "b07-rehearsal-2026-10-07",
                "exit_code": 0,
                "observations": smoke_counts["observations"],
                "coverage_rows": smoke_counts["coverage_rows"],
                "current_rows": smoke_counts["current_rows"],
                "superseded_rows": smoke_counts["superseded_rows"],
                "job_rows": smoke_counts["job_rows"],
                "published_rows": smoke_counts["published_rows"],
                "structural_ok": bool(smoke["structural_ok"]),
                "new_suite": True,
                "explanation": "The smoke tool drives the candidate's operations "
                "view in-process over the synthetic fixture root: 7 checkpoint "
                "observations (5 current + 2 superseded), 7 coverage rows, 7 "
                "job rows and 4 published rows; the root is configured with 7 "
                "scanned files and no problems; structural_ok=True. It ran "
                "twice: the first pass exposed the published.py over-redaction "
                "and the fix and rebuild were followed by the clean second "
                "pass recorded here (stderr empty).",
            },
        },
        "probe_verdict": validation["verdict"],
        "probe_findings": validation["findings"],
        "discovery_identical_across_cwds": validation["discovery_identical_across_cwds"],
        "stability_identical_across_cwds": validation.get(
            "stability_identical_across_cwds"),
        "seam_identical_across_cwds": validation.get("seam_identical_across_cwds"),
        "operations_identical_across_cwds": validation.get(
            "operations_identical_across_cwds"),
        "frontend_identical_across_cwds": validation.get(
            "frontend_identical_across_cwds"),
        "cross_stack_identical_across_cwds": validation.get(
            "cross_stack_identical_across_cwds"),
        "discovery_projection_identical_across_cwds": validation.get(
            "discovery_projection_identical_across_cwds"),
        "b07_vs_b06_ledger_consistent": validation.get("b07_vs_b06_ledger_consistent"),
        "candidate_tree_digest_reproducible": validation.get(
            "candidate_tree_digest_reproducible", {}).get("sha256_match"),
        "probe_stability": validation.get("stability"),
        "probe_b07_vs_b06_stability": validation.get("b07_vs_b06_stability"),
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
            "probe_failed_capture": rel(PROBE_FAILED),
            "smoke_record": rel(SMOKE_RECORD),
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
                "blocker": "original-project merge of the B07 entries",
                "reason": "gate original_paths_released is closed; an explicit "
                "human release with an explicit scope is required. The merge "
                "proposal has 14 release-required entries of 15: the two "
                "rewritten modules (app.py, dataset.py; add_file semantics "
                "because the whole integration package is new relative to the "
                "original project) and the twelve new files (operations/jobs.py, "
                "operations/published.py and the ten labelled synthetic "
                "operations fixtures); the candidate tree digest must be "
                "re-verified immediately before any original write.",
            },
            {
                "blocker": "release decision spans both proposals",
                "reason": "the B06 merge proposal's 18 release-required entries "
                "and B07's 14 should be decided together or stay deferred; the "
                "B07 proposal re-verifies the cross-reference against the B06 "
                "proposal (b06_merge_crossref_matches, "
                "supersession_chains_match) rather than re-proposing B06's "
                "entries",
            },
            {
                "blocker": "real Node component execution (ielts-api / toefl-api)",
                "reason": "gate original_paths_released is closed; the cross-stack "
                "rehearsal ran only against the private candidate and its staged "
                "frontend, on ephemeral loopback ports",
            },
            {
                "blocker": "real database schema / data-root migration",
                "reason": "gate real_data_write_authorized is closed; schema and "
                "data roots are deliberately unchanged by B07",
            },
            {
                "blocker": "real operations enablement and source fetching/recovery",
                "reason": "gates existing_service_cutover_authorized, "
                "upstream_requests_authorized and cie_resume_authorized are "
                "closed; the only operations root is the labelled synthetic "
                "fixture, and the stopped cie 9191 batch stays stopped - nothing "
                "is resumed, fetched or written back",
            },
            {
                "blocker": "deployment to any target",
                "reason": "gate remote_deployment_authorized is closed; the "
                "candidate is private-only",
            },
        ],
        "process_observations": [
            {
                "observation": "The first build and smoke passes exposed an "
                "over-redaction defect in the new operations view's public "
                "projection: published.py rendered the internal `coverage/1` "
                "schema tag and a slash-bearing denominator label "
                "(`manifest:expected-manifest.json/cie-questions:expected=7`) "
                "as redacted path strings (`coverage<path>`, "
                "`manifest:expected-manifest.json<path>`) because the "
                "production redactor treats slash-bearing label text as "
                "filesystem locations.",
                "handling": "Fixed with two edits inside tools/published.py: the "
                "internal schema tag is no longer emitted on public rows, and "
                "denominator labels use `#` separators so they cannot be "
                "mistaken for paths. The candidate was rebuilt (tree digest "
                "7a1985b7\u2026 \u2192 5df25984\u2026; file counts unchanged at "
                "221/222) and the clean second smoke pass confirmed it "
                "(schema tag absent, denominator `manifest:expected-manifest.json"
                "#cie-questions:expected=7`). Both edits are recorded in "
                "evidence/source_edits.diff; the pre-fix bytes are not archived "
                "separately - their rendering survives in this session's event "
                "log only.",
            },
            {
                "observation": "The probe's first capture attempt exited 1 with "
                "exactly one failing check, J_section_completed: a "
                "probe-internal attribute name (the J wrapper read "
                "`job.public_id` where the view exposes `job.id`), i.e. "
                "AttributeError: 'JobView' object has no attribute 'public_id'. "
                "145 checks were recorded (85 positive / 26 negative) before "
                "the J section aborted.",
                "handling": "One line inside the probe was fixed "
                "(public_id -> id), and a scratch preflight "
                "(evidence/tmp/j2_check.py, removed at cleanup) confirmed the J "
                "data (5 stage rows, 4 published rows without the schema tag, "
                "the 9191 completeness envelope, the warning) before the clean "
                "rerun. The rerun passed 174/174. Unlike the B06 rehearsal, "
                "the failed capture was NOT overwritten: it is kept at "
                "evidence/probe_run1.json, the clean capture at "
                "evidence/probe_run2.json; only the clean run is archived as "
                "the frozen cwd captures by the validator.",
            },
            {
                "observation": "The B07 probe reports 174 checks where the B06 "
                "probe reported 138, and its positive and negative control "
                "lists both extend B06's.",
                "handling": "Explained: 138 + 36 = 174 - the three new A "
                "root-configuration checks (operations root is the candidate's "
                "fixture, the API key is a labelled synthetic control, the "
                "env name is pinned) and the 33 new J checks (28 positive + 5 "
                "negative); the positive list is B06's with the two "
                "ledger-stability checks renamed from _b05_ to _b06_ plus the "
                "28 J positives (83 + 28 = 111), and the negative list is "
                "B06's 25 plus the 5 J negatives (30). The report script "
                "asserts all of these relations against the frozen B06 probe "
                "before writing anything.",
            },
            {
                "observation": "Unlike B06, the proposals generator exited 0 on "
                "its first run (no failed-run history in this packet); the "
                "build and smoke tools ran twice only because of the "
                "published.py over-redaction fix.",
                "handling": "Both build passes exited 0 with 21/21 checks and "
                "identical file counts (221 digest / 222 on-disk); only the "
                "recorded tree digest differs because published.py's bytes "
                "changed between them. The recorded artifacts are the second "
                "passes; the first pass is named in the command table and "
                "here.",
            },
        ],
    }

    report = report_md(ledger, validation)
    return ledger, report


def counted_carried(carried: dict, counts: dict) -> int:
    files = carried.get("files")
    if files is not None:
        return files
    return counts["files_copied_from_parent"] - counts["edited_files_rewritten_by_b07"]


def report_md(ledger: dict, validation: dict) -> str:
    c = ledger["changed_counts"]
    t = ledger["test_counts"]
    cmd_rows = [
        f"| {row['step']} | `{row['command']}` | `{row['cwd']}` | {row['exit_code']} |"
        for row in ledger["commands"]
    ]
    lines = [
        "# B07 rehearsal review report (private preparation only)",
        "",
        f"Generated: {ledger['generated_at']}  ",
        "Packet: **B07** — operations view (jobs / coverage / diagnostics) over "
        "the private read API  ",
        f"Status: `{ledger['status']}`  ",
        f"Probe verdict: `{ledger['probe_verdict']}`  ",
        f"Probe findings: {len(ledger['probe_findings'])}",
        "",
        "Nothing in this report has been merged or deployed. The original project was "
        "not read, imported or written by any B07 step. All seven gates are closed.",
        "",
        "## 1. What B07 rehearsed",
        "",
        "B07 owns the operations view over the private read API (jobs / coverage / "
        "diagnostics). What can be done without the human release is a rehearsal: "
        "carry the B06 candidate byte-for-byte, rewrite two modules — `app.py` "
        "(operations routes and diagnostics wiring) and `dataset.py` (operations "
        "projections) — and add the new `src/examdata/integration/operations/` "
        "package: `jobs.py` (read-only job views over a configured operations root; "
        "stopped jobs stay stopped and nothing is resumed or written back) and "
        "`published.py` (sanitized published-coverage projections with no raw paths, "
        "keys or secrets on any leaf), plus a fully synthetic operations fixture "
        "root (ten labelled files incl. seven batch checkpoints; proposed install "
        "target `examdata/tests/integration/fixtures/synthetic/operations/"
        "operations-root/`). The acceptance properties that do not need the "
        "original tree are then proven by the route probe: the J section drives the "
        "candidate's operations view through the synthetic fixture root (current-"
        "only jobs, checkpoint stages with superseded handling, a stopped 9191 batch "
        "flagged for resume with its error fixture-redacted, coverage and published "
        "projections without the internal schema tag, and the guarantee that the "
        "view leaves the candidate tree unchanged), while the carried B06 surface "
        "(frontend tree, discovery semantics and the private cross-stack rehearsal) "
        "is re-proven unchanged.",
        "",
        "## 2. Candidate and lineage",
        "",
        f"- Candidate: `{rel(CANDIDATE)}`",
        f"- Parent: `{rel(PARENT)}` (the B06 frontend candidate)",
        f"- Parent tree: {c['parent_tree_files']} files, sha256 "
        f"`{ledger['hashes']['parent_tree_sha256']}`",
        f"- Candidate tree: {c['candidate_tree_files']} files "
        f"({c['candidate_files_copied_from_parent']} copied from the parent, of "
        f"which {c['candidate_files_carried_verbatim']} stay verbatim and "
        f"{c['edited_candidate_module_source_files']} were rewritten, + "
        f"{c['new_operations_files_added_by_b07']} new operations files), sha256 "
        f"`{ledger['hashes']['candidate_tree_sha256']}`",
        f"- Candidate digest reproducible from the tree on disk: "
        f"`{ledger['candidate_tree_digest_reproducible']}` (re-checked independently "
        "by the validator, not just self-reported by the builder)",
        f"- Parent manifest sha256 unchanged at build time: "
        f"`{ledger['hashes']['parent_manifest_sha256']}`",
        "- Count explanation: B06's digest covered 208 files and its on-disk "
        "non-cache count was 209 (208 + B06 manifest). B07 copies all 209, rewrites "
        "2 and adds 12, so the candidate digest covers 221 = 207 verbatim + 2 "
        "rewritten + 12 new, and on-disk is 222 = 221 + the B07 manifest; the "
        "candidate carries no __pycache__ files (PYTHONDONTWRITEBYTECODE=1 "
        "throughout).",
        "",
        "The rewritten `app.py` supersedes B06 BP-0002 (chain: A14 MM-0015 → B05 "
        "BP-0004 → B06 BP-0002 → B07) and the rewritten `dataset.py` supersedes B06 "
        "BP-0003 (chain: A14 MM-0017 → R0104 RP-0005 → B05 BP-0003 → B06 BP-0003 → "
        "B07); the two new operations modules and the ten fixture files are new "
        "against the parent. The merge proposal re-verifies all of this in its 11 "
        "digest checks (`supersession_chains_match`, `new_modules_match_sources`, "
        "`operations_fixture_files_match_sources`, "
        "`operations_target_conventions_match_b01`, `b06_merge_crossref_matches`, "
        "`parent_tree_reverified`, `candidate_tree_reverified`), all true.",
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
        f"- **Route probe**: {t['b07_route_probe']['checks_per_run']} checks \u00d7 "
        f"{t['b07_route_probe']['runs']} working directories = "
        f"{t['b07_route_probe']['checks_total']} check executions, "
        f"{t['b07_route_probe']['checks_failed']} failed.",
        f"- **Isolated staged suite**: {t['isolated_staged_suite']['summary']} "
        f"(exit {t['isolated_staged_suite']['exit_code']}). Unchanged from the "
        "R04/B02/B03/B04/B05/B06 baseline of "
        f"{t['isolated_staged_suite']['baseline_passed']}; B07 adds no test file "
        "to that suite.",
        f"- **Build checks**: {t['candidate_build']['checks_passed']}/"
        f"{t['candidate_build']['checks_total']}.",
        f"- **Cross-stack rehearsal (part of the probe)**: "
        f"{t['cross_stack']['checks_total']} driver checks, "
        f"{t['cross_stack']['checks_failed']} failed; the candidate frontend's Node "
        f"test files passed {ledger['frontend_node_test']['pass']}/"
        f"{ledger['frontend_node_test']['tests']}.",
        f"- **Smoke import (operations view, in-process)**: "
        f"{t['smoke_import']['observations']} checkpoint observations "
        f"({t['smoke_import']['current_rows']} current / "
        f"{t['smoke_import']['superseded_rows']} superseded), "
        f"{t['smoke_import']['coverage_rows']} coverage rows, "
        f"{t['smoke_import']['job_rows']} job rows, "
        f"{t['smoke_import']['published_rows']} published rows; "
        f"`structural_ok={t['smoke_import']['structural_ok']}`.",
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
        "- **Section A — import and root configuration (15 checks)**: root env is the "
        "candidate, no staging-root override, no PYTHONPATH, candidate `src/` first "
        "on `sys.path`, every module origin inside the candidate, no original-tree "
        "module loaded, no product import of testing guards, 28 schema files parse, "
        "quality dimensions and identity kinds match the code, synthetic Node "
        "discovery (`fake_cli`) resolves inside the candidate, legacy bridge entry "
        "imports from the candidate; and the three new checks pin the operations "
        "root to the candidate's own fixture directory, the API key to a "
        "fixture-labelled synthetic control value, and the operations-root "
        "environment variable name (`EXAMDATA_OPERATIONS_ROOT`).",
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
        "- **Section D — combined OpenAPI and B06-ledger stability (10 checks)**: the "
        "path delta is exactly the registry; the pre-attach paths' operations are "
        "unchanged; operation ids are unique; the v2 operation ids match the "
        "standalone app; binary rows are documented with their media types; "
        "non-binary 200 responses serve the envelope schema; `/openapi.json` serves "
        "the same document as the direct call; a second instance yields the same "
        "digest; and the two renamed stability checks confirm the combined OpenAPI, "
        "standalone v2, legacy-operations and composed-route-table digests plus the "
        "operation ids and the 34-path delta still match the frozen B06 progress "
        "ledger (`b07_vs_b06_ledger_consistent` = "
        f"`{ledger['b07_vs_b06_ledger_consistent']}`).",
        "- **Section E — stability (7 checks)**: candidate bytes unchanged by the "
        "probe; fixture and contract digests unchanged; the manifest recomputes to "
        "221 files and the same tree digest; counts disclosed (221 digest / 222 "
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
        "- **Section J — the operations view over the synthetic fixture root (33 "
        "checks; 28 positive + 5 negative controls)**: the view is enabled from the "
        "environment only (root = the candidate's own synthetic fixture directory, "
        "API key = a fixture-labelled synthetic control); jobs are served "
        "current-only by id; stage rows reflect the checkpoints; superseded "
        "checkpoints appear only in superseded lists; no job conflicts are "
        "reported; the view scans the root once and cleanly; route 9191 stays "
        "stopped and flags resume; its error is fixture-redacted (no raw paths or "
        "secrets); it carries no superseded rows or conflicts; the operations "
        "warning is appended on the route; the 9191 envelope reports completeness; "
        "route leaves expose the placeholders; route 8888 serves the current "
        "running / old stopped rows only in superseded lists; a deferred job "
        "fixture is still served; the coverage route's items and gaps are identical "
        "with and without the operations view; the coverage warning is appended; "
        "the root block is disclosed without raw paths; seven checkpoint rows "
        "resolve to five current and two superseded; the checkpoint payload hashes "
        "recompute 7/7 with three pinned; the unsupported checkpoint is recorded as "
        "unknown; checkpoint conflicts stay empty; job briefs show stopped and "
        "superseded states; the published route serves four rows and the internal "
        "schema tag is absent; the published rows pass the coverage contract; "
        "statuses are pinned; `computed_at` is UTC second-precision; and the "
        "candidate tree is unchanged by the view. The five negative controls cover "
        "the disabled/unconfigured paths: operations stay off without "
        "configuration; route leaves carry no raw paths or secrets; a disabled app "
        "has no operations key; a missing root is reported, not raised; and the "
        "operations modules expose no write surface.",
        "- **Sections N1\u2013N6 — route-layer negative controls (16 checks, 15 "
        "negative) and section N7 — the seam refuse-path (10 negative checks)**: "
        "identical to B06 - raw include, unscoped install, mounts, double/late "
        "attach, non-FastAPI host, and the ten seam refuse paths; the negative "
        "control list extends B06's by exactly the five J negatives.",
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
        "seam, the operations view, the staged-frontend tree, the discovery "
        "projection and the cross-stack summary are identical across all three "
        "(`discovery_identical_across_cwds`, `stability_identical_across_cwds`, "
        f"`seam_identical_across_cwds`, `operations_identical_across_cwds` = "
        f"`{ledger['operations_identical_across_cwds']}`, "
        f"`frontend_identical_across_cwds` = "
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
        "rewritten staged modules. The release-required entries are the two "
        "rewritten modules (BP-0002 app.py, BP-0003 dataset.py; add_file semantics "
        "at the proposed targets because the whole integration package is new "
        "relative to the original project - superseding the unapplied B06 "
        "BP-0002/BP-0003) and the twelve new files: BP-0004 "
        "`operations/jobs.py`, BP-0005 `operations/published.py`, and the ten "
        "fixture files BP-0006\u2013BP-0015 under "
        "`examdata/tests/integration/fixtures/synthetic/operations/"
        "operations-root/`. The single staging-only entry is BP-0001, the "
        "candidate container (kept in integration-staging/; no original-project "
        "action proposed).",
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
        "# B07 private progress ledger",
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
        f"| new operations files added by B07 | "
        f"{ledger['changed_counts']['new_operations_files_added_by_b07']} |",
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
        f"{ledger['test_counts']['b07_route_probe']['checks_total']} "
        f"({ledger['test_counts']['b07_route_probe']['checks_failed']} failed) |",
        f"| cross-stack driver checks | "
        f"{ledger['test_counts']['cross_stack']['checks_total']} "
        f"({ledger['test_counts']['cross_stack']['checks_failed']} failed) |",
        f"| candidate Node tests | {ledger['frontend_node_test']['pass']}/"
        f"{ledger['frontend_node_test']['tests']} |",
        f"| smoke import observations | "
        f"{ledger['test_counts']['smoke_import']['observations']} "
        "(structural_ok "
        f"`{ledger['test_counts']['smoke_import']['structural_ok']}`) |",
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
    write_json(os.path.join(OUT, "B07_PROGRESS_LEDGER.json"), ledger)
    write_text(os.path.join(OUT, "B07_PROGRESS_LEDGER.md"), ledger_md(ledger))
    write_text(os.path.join(OUT, "B07_REHEARSAL_REPORT.md"), report)
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
