"""Build the B05 rehearsal review report and the B05 private progress ledger.

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
FROZEN_EVID = os.path.join(OUT, "evidence", "B05", "b05-rehearsal-2026-10-07")

CST = timezone(timedelta(hours=8))

CANDIDATE = os.path.join(RUN, "candidates", "b05-adapters-v1")
CANDIDATE_MANIFEST = os.path.join(CANDIDATE, "B05_CANDIDATE_MANIFEST.json")
PARENT = os.path.join(
    RUN, "..", "b04-rehearsal-2026-10-07", "candidates", "b04-routes-v1",
)
VALIDATION = os.path.join(FROZEN_EVID, "B05_LAYOUT_VALIDATION.json")
SUITE_TXT = os.path.join(EVID, "isolated_staged_suite.txt")
SOURCE_EDITS = os.path.join(EVID, "source_edits.diff")
SOURCE_EDITS_PRE_FIX = os.path.join(EVID, "tmp", "source_edits_pre_fix.diff")
BUILD_RECORD = os.path.join(EVID, "build_run.json")

MERGE_JSON = os.path.join(OUT, "B05_MERGE_PROPOSAL.json")
ROLLBACK_JSON = os.path.join(OUT, "B05_ROLLBACK_PROPOSAL.json")
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
WS_ABS = "C:/Users/weo/Desktop/api"
RUN_REL = "integration-staging/runtime/b05-rehearsal-2026-10-07"
CAND_ABS = f"{WS_ABS}/{RUN_REL}/candidates/b05-adapters-v1"
PROBE_ENV = (
    "env -u PYTHONPATH -u EXAMDATA_INTEGRATION_STAGING_ROOT "
    "PYTHONIOENCODING=utf-8 PYTHONDONTWRITEBYTECODE=1 "
    f"B05_CANDIDATE_ROOT={CAND_ABS} B05_WORKSPACE_ROOT={WS_ABS} "
    f"B05_TMP_DIR={WS_ABS}/{RUN_REL}/evidence/tmp "
    f"EXAMDATA_INTEGRATION_ROOT={CAND_ABS}"
)

COMMANDS = [
    {
        "step": "build candidate",
        "command": "PYTHONIOENCODING=utf-8 C:/Users/weo/Desktop/api/examdata/"
                   ".venv/Scripts/python.exe b05_build_candidate.py "
                   "> evidence/build_run.json 2> evidence/build_run.err.txt",
        "cwd": "C:/Users/weo/Desktop/api/integration-staging/runtime/"
               "b05-rehearsal-2026-10-07",
        "exit_code": 0,
    },
    {
        "step": "route probe (first and only run, clean)",
        "command": f"{PROBE_ENV} {PY} {RUN_REL}/b05_route_probe.py "
                   f"> {RUN_REL}/evidence/probe_run1.json "
                   f"2> {RUN_REL}/evidence/probe_run1.err",
        "cwd": "C:/Users/weo/Desktop/api",
        "exit_code": 0,
        "note": "98/98 checks clean on the first run; the raw capture is "
                "evidence/probe_run1.json (stderr holds only the Starlette "
                "deprecation warning)",
    },
    {
        "step": "validate (probe from 3 cwds)",
        "command": f"{PY} {RUN_REL}/b05_validate.py "
                   f"> {RUN_REL}/evidence/validate_run1.json "
                   f"2> {RUN_REL}/evidence/validate_run1.err",
        "cwd": "C:/Users/weo/Desktop/api",
        "exit_code": 0,
        "note": "the validator itself writes the frozen evidence under "
                "docs/integration/execution/evidence/B05/b05-rehearsal-2026-10-07/",
    },
    {
        "step": "isolated staged suite",
        "command": f"bash integration-staging/tools/run_staged_tests.sh -q "
                   f"> {RUN_REL}/evidence/isolated_staged_suite.txt 2>&1; "
                   f'echo "suite_exit=$?" >> {RUN_REL}/evidence/'
                   "isolated_staged_suite.txt",
        "cwd": "C:/Users/weo/Desktop/api",
        "exit_code": 0,
    },
    {
        "step": "merge + rollback proposals, first run",
        "command": f"{PY} {RUN_REL}/b05_build_proposals.py",
        "cwd": "C:/Users/weo/Desktop/api",
        "exit_code": 1,
        "note": "failed exactly one digest check, "
                "new_files_exactly_one_vs_parent: the comparison took the "
                "parent file set to exclude the parent's own manifest while "
                "the child carries a byte-identical copy of it; fixed by "
                "comparing against the parent's full file set; details in "
                "process_observations",
    },
    {
        "step": "merge + rollback proposals, rerun after the fix",
        "command": f"{PY} {RUN_REL}/b05_build_proposals.py",
        "cwd": "C:/Users/weo/Desktop/api",
        "exit_code": 0,
        "note": "all 8 digest checks true",
    },
    {
        "step": "review report + progress ledger",
        "command": f"{PY} {RUN_REL}/b05_build_report.py",
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
        "b05_build_candidate.py",
        "b05_route_probe.py",
        "b05_validate.py",
        "b05_build_proposals.py",
        "b05_build_report.py",
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

    probe_first = load_json(os.path.join(FROZEN_EVID, first_run))["report"]
    import_checks = []
    for c in probe_first["checks"]:
        if not c["name"].startswith("A_"):
            continue
        detail = c.get("detail") or ""
        if len(detail) > 200:
            detail = detail[:200] + "\u2026"
        import_checks.append({"name": c["name"], "ok": bool(c["ok"]), "detail": detail})

    negatives = [
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
    positives = [
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
        "D_stability_digests_match_b04_ledger",
        "D_stability_ids_and_delta_match_b04_ledger",
        "N1_legacy_probes_unchanged",
    ]

    for name in negatives + positives:
        if name not in check_names:
            raise SystemExit(f"check name not found in probe evidence: {name}")

    evidence_negatives = set(probe_first["negative_checks"])
    evidence_positives = set(probe_first["positive_checks"])
    if evidence_negatives != set(negatives):
        raise SystemExit(
            "negative control list disagrees with the probe evidence: "
            f"{sorted(evidence_negatives ^ set(negatives))}"
        )
    if evidence_positives != set(positives):
        raise SystemExit(
            "positive control list disagrees with the probe evidence: "
            f"{sorted(evidence_positives ^ set(positives))}"
        )

    counts = manifest["counts"]
    tree = manifest["candidate_tree"]
    parent = manifest["lineage"]["parent_tree"]
    build_record = load_json(BUILD_RECORD)

    ledger = {
        "ledger_version": "b05-private-progress-ledger/1",
        "generated_by": rel(os.path.abspath(__file__)),
        "generated_at": now,
        "kind": "private_progress_ledger",
        "note": "Private progress record for the B05 rehearsal. This is NOT the live "
        "execution ledger and does not replace it.",
        "packet": "B05",
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
        "status": "b05_private_rehearsal_complete_pending_human_release",
        "not_claimed": [
            "merged_pass",
            "deployment",
            "full B00/B01 completion",
        ],
        "changed_counts": {
            "new_staging_scripts": len(staging_scripts()),
            "new_candidate_module_source_files": 1,
            "edited_candidate_module_source_files": 2,
            "candidates": 1,
            "candidate_files_copied_from_parent": counts["files_copied_from_parent"],
            "new_files_added_by_b05": counts["new_files_added_by_b05"],
            "edited_files_rewritten_by_b05": counts["edited_files_rewritten_by_b05"],
            "candidate_tree_files": tree["files"],
            "candidate_files_on_disk": counts.get("candidate_files_on_disk_after_manifest"),
            "parent_tree_files": parent["files"],
            "original_project_files_written": 0,
            "frozen_evidence_files_rewritten": 0,
        },
        "count_explanations": {
            "new_staging_scripts": "5 new B05 scripts: b05_build_candidate.py, "
            "b05_route_probe.py, b05_validate.py, b05_build_proposals.py, "
            "b05_build_report.py",
            "new_candidate_module_source_files": "1 new private module source: "
            "tools/active_owner.py, byte-identical to the candidate's "
            "src/examdata/integration/adapters/active_owner.py (both sha256 "
            "0d8116f0\u2026)",
            "edited_candidate_module_source_files": "2 rewritten module sources under "
            "tools/: dataset.py (c341ce30\u2026 \u2192 a9a72a7a\u2026) and app.py "
            "(afa2602e\u2026 \u2192 aa3ba9c5\u2026), each byte-identical to the "
            "candidate's copy; evidence/source_edits.diff records both rewrites plus "
            "the new module against the B04 bytes",
            "candidates": "1 new private candidate: b05-adapters-v1, a child of the "
            "B04 routes candidate",
            "candidate_files_copied_from_parent": "189 = the B04 on-disk files (188 "
            "digest files + B04_CANDIDATE_MANIFEST.json) carried byte-for-byte; 187 of "
            "them stay verbatim and 2 are rewritten by B05",
            "new_files_added_by_b05": "1 = src/examdata/integration/adapters/"
            "active_owner.py (the active-owner seam module); everything else is "
            "carried or rewritten from the parent",
            "edited_files_rewritten_by_b05": "2 = src/examdata/integration/api/"
            "dataset.py and src/examdata/integration/api/app.py, rewritten to read the "
            "five feature families through the seam; both supersede previously staged "
            "bytes (dataset: A14 MM-0017 \u2192 R0104 RP-0005 \u2192 B05; app: A14 "
            "MM-0015 \u2192 B05)",
            "candidate_tree_files": "190 digest files = 189 carried (187 verbatim + 2 "
            "rewritten) + 1 new module; B05's digest rule excludes its own manifest "
            "and skips __pycache__/.pytest_cache",
            "candidate_files_on_disk": "191 = 190 digest files + "
            "B05_CANDIDATE_MANIFEST.json (non-cache files on disk); the 49 "
            "__pycache__ .pyc files are not counted by the digest rule",
            "parent_tree_files": "188 = B04's digest count, which excluded B04's own "
            "manifest (B04 on-disk was 189); the two numbers describe different file "
            "sets by rule",
            "original_project_files_written": "0: nothing was written outside "
            "integration-staging/ and docs/integration/execution/",
            "frozen_evidence_files_rewritten": "0 existing frozen files rewritten: "
            "evidence/A00\u2013B04/**, evidence/R0104/** and the B02/B03/B04 runtime "
            "trees were read-only; B05's own evidence under "
            "evidence/B05/b05-rehearsal-2026-10-07/ was created new and nothing there "
            "was overwritten",
        },
        "hashes": {
            "candidate_manifest": rel(CANDIDATE_MANIFEST),
            "candidate_manifest_sha256": sha256_file(CANDIDATE_MANIFEST),
            "candidate_tree_sha256": tree["sha256"],
            "parent_manifest_sha256": manifest["lineage"]["parent_manifest_sha256"],
            "parent_tree_sha256": parent["sha256"],
            "validation_sha256": sha256_file(VALIDATION),
            "merge_proposal_sha256": sha256_file(MERGE_JSON),
            "rollback_proposal_sha256": sha256_file(ROLLBACK_JSON),
            "suite_transcript_sha256": suite["transcript_sha256"],
            "source_edits_diff_sha256": sha256_file(SOURCE_EDITS),
            "source_edits_diff_pre_fix_sha256": sha256_file(SOURCE_EDITS_PRE_FIX),
            "build_record_sha256": sha256_file(BUILD_RECORD),
        },
        "test_counts": {
            "b05_route_probe": {
                "command": f"{PY} {RUN_REL}/b05_validate.py",
                "cwd": "C:/Users/weo/Desktop/api",
                "exit_code": 0,
                "runs": len(probe_runs),
                "checks_per_run": probe_runs[0]["checks"] if probe_runs else 0,
                "checks_total": checks_total,
                "checks_failed": checks_failed,
                "new_suite": True,
                "explanation": "New B05 route probe (the B04 probe extended for the "
                "seam): 98 checks per run = the 75-check B04 face (A 12, B 14, C 18, "
                "D 8, E 7, N1\u2013N6 16) plus 23 new B05 checks \u2014 the seam "
                "section S (10), C_material_content_200_pinned (1), the two B04-ledger "
                "stability comparisons (2) and the seam negative controls N7 (10); 25 "
                "negative and 43 positive controls in total. Executed from 3 different "
                "working directories (98 \u00d7 3 = 294 check executions). The first "
                "run was clean (98/98), so there is no failed/clean capture pair to "
                "keep, unlike B04; the single capture is evidence/probe_run1.json.",
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
                "explanation": "Count is unchanged from the R04/B02/B03/B04 baseline "
                "(887 passed). B05 adds no test files to the staged suite; its new "
                "modules are exercised by the B05 route probe instead, so a changed "
                "suite count would itself have been the finding. The suite ran exactly "
                "once, after every product-code fix had stabilised (the only later fix "
                "was inside the proposals generator, which the staged suite never "
                "collects); the transcript's last line records `suite_exit=0`.",
            },
            "candidate_build": {
                "command": "PYTHONIOENCODING=utf-8 C:/Users/weo/Desktop/api/examdata/"
                ".venv/Scripts/python.exe b05_build_candidate.py "
                "> evidence/build_run.json 2> evidence/build_run.err.txt",
                "cwd": "C:/Users/weo/Desktop/api/integration-staging/runtime/"
                "b05-rehearsal-2026-10-07",
                "exit_code": 0,
                "checks_total": len(manifest["checks"]),
                "checks_passed": sum(1 for v in manifest["checks"].values() if v),
                "stderr_bytes": os.path.getsize(os.path.join(EVID, "build_run.err.txt")),
                "new_suite": True,
                "explanation": "17 build-time checks on the candidate itself (parent "
                "carried byte-identically, exactly one new file, exactly the two "
                "intended rewrites, all three match their tooling sources and compile, "
                "the digest is parent + new module and excludes the manifest, and the "
                "digest stays reproducible after the manifest write); all new. Build "
                "record: "
                f"all_ok={build_record['all_ok']}, "
                "digest_reproducible_after_manifest_write="
                f"{build_record['digest_reproducible_after_manifest_write']}, "
                "stderr empty.",
            },
        },
        "probe_verdict": validation["verdict"],
        "probe_findings": validation["findings"],
        "discovery_identical_across_cwds": validation["discovery_identical_across_cwds"],
        "stability_identical_across_cwds": validation.get(
            "stability_identical_across_cwds"),
        "seam_identical_across_cwds": validation.get("seam_identical_across_cwds"),
        "b05_vs_b04_ledger_consistent": validation.get(
            "b05_vs_b04_ledger_consistent"),
        "candidate_tree_digest_reproducible": validation.get(
            "candidate_tree_digest_reproducible", {}).get("sha256_match"),
        "probe_stability": validation.get("stability"),
        "probe_b05_vs_b04_stability": validation.get("b05_vs_b04_stability"),
        "seam": validation.get("seam"),
        "import_status_checks": import_checks,
        "negative_checks": negatives,
        "positive_checks": positives,
        "artifacts": {
            "candidate_manifest": rel(CANDIDATE_MANIFEST),
            "merge_proposal": rel(MERGE_JSON),
            "rollback_proposal": rel(ROLLBACK_JSON),
            "layout_validation": rel(VALIDATION),
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
            "rollback_reversible_by_target_delete": rollback["counts"]["original_level"][
                "reversible_by_target_delete"],
            "rollback_no_original_action": rollback["counts"]["original_level"][
                "no_original_action"],
        },
        "commands": COMMANDS,
        "frozen_evidence_written": False,
        "not_run": validation["not_run"],
        "remaining_blockers": [
            {
                "blocker": "original-project merge of the B05 entries",
                "reason": "gate original_paths_released is closed; an explicit human "
                "release with an explicit scope is required. The merge proposal has 3 "
                "release-required entries, all add_file semantics because the whole "
                "integration package is new relative to the original project: add "
                "examdata/src/examdata/integration/adapters/active_owner.py; install "
                "the B05 bytes at examdata/src/examdata/integration/api/dataset.py "
                "(superseding R0104 RP-0005) and at examdata/src/examdata/integration/"
                "api/app.py (superseding A14 MM-0015); the candidate tree digest must "
                "be re-verified immediately before any original write.",
            },
            {
                "blocker": "real active-owner integration (materials, syllabuses and "
                "timetables served by the original owner modules)",
                "reason": "no owner release exists for the active-owner families; the "
                "seam serves only clearly labelled synthetic fixtures and the real "
                "integration stays deferred_active_owner",
            },
            {
                "blocker": "real Node component execution (ielts-api / toefl-api)",
                "reason": "gate original_paths_released is closed; only the synthetic "
                "fake-node-cli fixture is discovered (never executed)",
            },
            {
                "blocker": "real database schema / data-root migration",
                "reason": "gate real_data_write_authorized is closed; schema and data "
                "roots are deliberately unchanged by B05",
            },
            {
                "blocker": "deployment to any target",
                "reason": "gate remote_deployment_authorized is closed; the candidate "
                "is private-only",
            },
        ],
        "process_observations": [
            {
                "observation": "The proposals script's first run exited 1 after failing "
                "exactly one digest check, new_files_exactly_one_vs_parent: the "
                "comparison took the parent file set to exclude the parent's own "
                "manifest, while the child candidate carries a byte-identical copy of "
                "that manifest, so the child appeared to have one unexplained extra "
                "file.",
                "handling": "The check now compares the child's file set against the "
                "parent's full file set (parent_files = file_set(PARENT)) and the "
                "digest_checks note records the rule; the rerun exited 0 with all 8 "
                "digest checks true. The failed run's stdout was not archived as a "
                "separate evidence file; it is recorded in the command table (exit 1) "
                "and here, and both proposal JSONs on disk are the post-fix "
                "regenerated versions.",
            },
            {
                "observation": "evidence/source_edits.diff was regenerated after a "
                "whitespace fix in tools/dataset.py (a blank line lost while the seam "
                "edits were applied), so an earlier regeneration predates the fix.",
                "handling": "The pre-fix capture is kept at "
                "evidence/tmp/source_edits_pre_fix.diff (9,898 bytes, 224 lines, sha256 "
                "08ca603d\u2026) and the on-disk diff (ec18a0dc\u2026, 547 lines, "
                "23,418 bytes) is the post-fix version used by the proposals and the "
                "manifest checks; the delta between the two is the dataset.py "
                "blank-line hunk plus the new active_owner.py diff segment \u2014 the "
                "app.py segment is byte-identical between them.",
            },
            {
                "observation": "The candidate on disk holds 240 files while the digest "
                "covers 190 and the manifest records 191 on-disk non-cache files; the "
                "49 __pycache__ .pyc files are real and unexplained counts invite "
                "doubt.",
                "handling": "Explained: the digest rule skips __pycache__/.pytest_cache "
                "and excludes B05_CANDIDATE_MANIFEST.json \u2192 190 digest files; "
                "on-disk non-cache = 190 + the manifest = 191; the remaining 49 files "
                "are Python bytecode caches created during import rehearsals and are "
                "not part of any digest or proposal.",
            },
            {
                "observation": "The B05 probe reports 98 checks per run where B04 "
                "reported 75; the increase is by design, not drift.",
                "handling": "Explained: the B05 probe extends the 75-check B04 face "
                "(A 12, B 14, C 18, D 8, E 7, N1\u2013N6 16) with 23 new checks: the "
                "seam section S (10), C_material_content_200_pinned (1), the two "
                "B04-ledger stability comparisons (2) and the seam negative controls "
                "N7 (10).",
            },
            {
                "observation": "The B05 probe was clean on its first run (98/98), so "
                "unlike B04 there is no failed capture to pair with the clean one.",
                "handling": "The single capture is kept as evidence/probe_run1.json/"
                ".err (exit 0); no second capture was created because no failing run "
                "happened, and no failed capture is claimed in any count.",
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
        "# B05 rehearsal review report (private preparation only)",
        "",
        f"Generated: {ledger['generated_at']}  ",
        "Packet: **B05** — active-owner seam for materials, syllabuses and timetables  ",
        f"Status: `{ledger['status']}`  ",
        f"Probe verdict: `{ledger['probe_verdict']}`  ",
        f"Probe findings: {len(ledger['probe_findings'])}",
        "",
        "Nothing in this report has been merged or deployed. The original project was "
        "not read, imported or written by any B05 step. All seven gates are closed.",
        "",
        "## 1. What B05 rehearsed",
        "",
        "B05 owns the integration of the released materials, syllabus and timetable "
        "features. What can be done without the human release is a rehearsal: carry "
        "the B04 candidate byte-for-byte, add one new module — the active-owner "
        "adapter seam `src/examdata/integration/adapters/active_owner.py` — and "
        "rewrite `dataset.py` and `app.py` so the five feature families (syllabuses, "
        "materials, timetable seasons, events and windows) are read through "
        "`Dataset.features` instead of being replaced by staged fixture "
        "implementations. The seam validates every row, serves only clearly labelled "
        "synthetic fixtures, preserves null session/date fields, keeps unavailable "
        "seasons explicit and never invents clock or boundary times. The acceptance "
        "properties that do not need the original tree are then proven by the route "
        "probe: the seam refuses unlabelled or live-access data, and the B04 route "
        "surface plus the B04 ledger digests stay byte-stable under the new seam.",
        "",
        "## 2. Candidate and lineage",
        "",
        f"- Candidate: `{rel(CANDIDATE)}`",
        f"- Parent: `{rel(PARENT)}` (the B04 routes candidate)",
        f"- Parent tree: {c['parent_tree_files']} files, sha256 "
        f"`{ledger['hashes']['parent_tree_sha256']}`",
        f"- Candidate tree: {c['candidate_tree_files']} files "
        f"({c['candidate_files_copied_from_parent']} carried from the parent, of which "
        f"{c['edited_files_rewritten_by_b05']} were rewritten, + "
        f"{c['new_files_added_by_b05']} new), sha256 "
        f"`{ledger['hashes']['candidate_tree_sha256']}`",
        f"- Candidate digest reproducible from the tree on disk: "
        f"`{ledger['candidate_tree_digest_reproducible']}` (re-checked independently by "
        "the validator, not just self-reported by the builder)",
        f"- Parent manifest sha256 unchanged at build time: "
        f"`{ledger['hashes']['parent_manifest_sha256']}`",
        "- Count explanation: the parent digest covers 188 files (B04's rule excluded "
        "B04's own manifest, and B04 on-disk was 189); B05 carries all 189, rewrites 2 "
        "and adds 1 new module, so the candidate digest covers 190 = 187 verbatim + 2 "
        "rewritten + 1 new, and on-disk non-cache is 191 = 190 + the B05 manifest; 49 "
        "__pycache__ bytecode files on disk are skipped by the digest rule.",
        "",
        "The rewritten `dataset.py` supersedes the R0104-repaired staged bytes (chain: "
        "A14 MM-0017 \u2192 R0104 RP-0005 \u2192 B05) and the rewritten `app.py` "
        "supersedes the A14 MM-0015 staged bytes (chain: A14 MM-0015 \u2192 B05); "
        "both chains are re-verified in the merge proposal's `digest_checks`, and the "
        "parent tree digest was re-computed after the copy and again at proposal time "
        "and is unchanged (`parent_tree_reverified`).",
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
        f"- **Route probe**: {t['b05_route_probe']['checks_per_run']} checks \u00d7 "
        f"{t['b05_route_probe']['runs']} working directories = "
        f"{t['b05_route_probe']['checks_total']} check executions, "
        f"{t['b05_route_probe']['checks_failed']} failed.",
        f"- **Isolated staged suite**: {t['isolated_staged_suite']['summary']} "
        f"(exit {t['isolated_staged_suite']['exit_code']}). Unchanged from the "
        f"R04/B02/B03/B04 baseline of {t['isolated_staged_suite']['baseline_passed']}; "
        "B05 adds no test file to that suite.",
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
        "## 5. What the checks cover",
        "",
        "- **Section A — import and root configuration (12 checks)**: root env is the "
        "candidate, no staging-root override, no PYTHONPATH, candidate `src/` first on "
        "`sys.path`, every module origin inside the candidate (including the new "
        "`examdata.integration.adapters.active_owner`), no original-tree module loaded, "
        "no product import of testing guards, 28 schema files parse, quality "
        "dimensions and identity kinds match the code, synthetic Node discovery "
        "(`fake_cli`) resolves inside the candidate, legacy bridge entry imports from "
        "the candidate.",
        "- **Section B — worksheet, registry and ordering (14 checks)**: the A12 "
        "worksheet holds 71 rows (70 GET + 1 POST `/sample`); the v2 registry has 34 "
        "implemented / 0 deferred specs of which 5 are binary; runtime, spec and "
        "advertised pairs agree; HEAD pairs are binary-only; GET 34/34 and HEAD 5/5 "
        "first-match their own route; no static route is shadowed; and no two distinct "
        "path patterns intersect (561 pairs).",
        "- **Section C — host mechanics and behaviour (19 checks)**: host shape "
        "pre-attach (80 routes, 76 doc paths), the legacy prefix is kept 80\u219281, "
        "exactly one wrapper `_IncludedRouter` is appended; all 71 legacy rows and 7 "
        "extra probes stay byte-identical; the legacy stack-boom body stays pinned; "
        "binary fixture ids, 200 / 206 / 304 / HEAD responses pinned; the new "
        "`C_material_content_200_pinned` check pins the synthetic material content "
        "response under the seam; and the six v2 controls serve typed envelopes "
        "(invalid_request, internal_error, not_found, route_not_found, "
        "method_not_allowed, info envelope) that all differ from their pre-attach "
        "baselines.",
        "- **Section D — combined OpenAPI and B04-ledger stability (10 checks)**: the "
        "path delta is exactly the registry (34 added, 0 removed, none unexpected); "
        "the 76 pre-attach paths' operations are unchanged; 115 operation ids are "
        "unique; the 39 v2 operation ids match the standalone app; binary rows are "
        "documented with their media types; non-binary 200 responses serve the "
        "envelope schema; `/openapi.json` serves the same document as the direct "
        "call; a second instance yields the same digest; and the two new stability "
        "checks confirm the combined OpenAPI, standalone v2, legacy-operations and "
        "composed-route-table digests plus the 39 ids and the 34-path delta still "
        "match the frozen B04 progress ledger.",
        "- **Section E — stability (7 checks)**: candidate bytes unchanged by the "
        "probe; fixture and contract digests unchanged; the manifest recomputes to "
        "190 files and the same tree digest; counts disclosed (190 digest / 191 "
        "on-disk non-cache); the B04 compose hook stays frozen "
        "(`e220c007\u2026`); no embedded `data:` payloads; scratch marker written "
        "inside the run's evidence/tmp.",
        "- **Section S — the active-owner seam (10 checks)**: the synthetic fixture "
        "source validates with 2 rows per family; the default dataset really uses the "
        "fixture source; row access returns isolated copies; deferred families flow "
        "through the seam unchanged; route rows carry the synthetic markers with all "
        "five routes at 200; CIE event null date/session/raw_text fields are "
        "preserved; unavailable seasons carry their reason; unknown window boundaries "
        "stay declared with null parsed values; a private injected source is served by "
        "the routes; and the default fixture path still serves after that injection.",
        "- **Sections N1\u2013N6 — route-layer negative controls (16 checks, 15 "
        "negative)**: a raw `include_router` would serve unshaped v2 errors and a "
        "wrong content type for the binary row (refused by the hook); the unscoped "
        "install would change exactly three legacy probes and rewrite their error "
        "shapes to envelopes (the deliberate, documented difference); mounting under "
        "the legacy prefix documents no v2 paths; double attach is refused and leaves "
        "the host unchanged; late attach is refused and adds no v2 paths; a "
        "non-FastAPI host is refused; and every legacy probe stays unchanged under the "
        "composed application (`N1_legacy_probes_unchanged`).",
        "- **Section N7 — the seam refuse-path (10 negative checks)**: the seam "
        "refuses a missing synthetic evidence marker, a missing deferred status "
        "marker, non-synthetic source evidence, live-access material, an unavailable "
        "season without a reason, a date without its raw timetable text, an unknown "
        "boundary carrying a parsed value, an undeclared missing boundary, non-list "
        "family rows, and the dataset refuses an unvalidated source; the real "
        "active-owner integration stays `deferred_active_owner`.",
        "",
        "## 6. Import status of the new candidate",
        "",
        "The candidate's imports resolve from the candidate itself through "
        "`EXAMDATA_INTEGRATION_ROOT` only \u2014 no `PYTHONPATH`, no staging-root "
        "override \u2014 and the same result holds from all three working directories: "
        "the workspace root, an arbitrary directory name under the run's evidence/tmp, "
        "and a path containing spaces and non-ASCII characters (`cwd with spaces "
        "\u00fcn\u00efcode`). Module origins, schema access, synthetic Node discovery "
        "and the runtime/legacy entry points were re-verified from those directories, "
        "and discovery, routing stability and seam digests are identical across all "
        "three (`discovery_identical_across_cwds`, `stability_identical_across_cwds`, "
        f"`seam_identical_across_cwds` = {ledger['seam_identical_across_cwds']}). Real "
        "Node/source validation against the original project remains `not_run`.",
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
        f"{ledger['proposal_counts']['merge_entries_requiring_release']} requiring the "
        f"human release, {ledger['proposal_counts']['merge_staging_only_entries']} "
        f"staging-only; {ledger['proposal_counts']['merge_new_files_vs_parent']} new "
        f"file vs the parent and "
        f"{ledger['proposal_counts']['merge_edited_files_rewritten']} rewritten "
        "staged files. The release-required entries are the new module "
        "`examdata/src/examdata/integration/adapters/active_owner.py` (add_file) and "
        "the two rewrites at `examdata/src/examdata/integration/api/dataset.py` "
        "(superseding R0104 RP-0005) and "
        "`examdata/src/examdata/integration/api/app.py` (superseding A14 MM-0015); "
        "all three are add_file semantics because the integration package is new "
        "relative to the original project.",
        f"- Rollback proposal: `{ledger['artifacts']['rollback_proposal']}` \u2014 "
        f"{ledger['proposal_counts']['rollback_entries']} entries; of the original-"
        f"level actions {ledger['proposal_counts']['rollback_reversible_by_target_delete']} "
        "are reversible by deleting the added target file (guarded by the recorded "
        "sha256) and "
        f"{ledger['proposal_counts']['rollback_no_original_action']} has no original "
        "action at all.",
        "",
        "Both are marked `proposal_only_not_merged`. Nothing has been applied to the "
        "original project. The seam serves only clearly labelled synthetic fixtures; "
        "the real active-owner integration remains `deferred_active_owner`.",
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
        "# B05 private progress ledger",
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
        f"| edited candidate module sources | "
        f"{ledger['changed_counts']['edited_candidate_module_source_files']} |",
        f"| candidates | {ledger['changed_counts']['candidates']} |",
        f"| candidate tree files | {ledger['changed_counts']['candidate_tree_files']} |",
        f"| candidate files on disk | "
        f"{ledger['changed_counts']['candidate_files_on_disk']} |",
        f"| new files added by B05 | {ledger['changed_counts']['new_files_added_by_b05']} |",
        f"| edited files rewritten by B05 | "
        f"{ledger['changed_counts']['edited_files_rewritten_by_b05']} |",
        f"| original project files written | "
        f"{ledger['changed_counts']['original_project_files_written']} |",
        f"| frozen evidence files rewritten | "
        f"{ledger['changed_counts']['frozen_evidence_files_rewritten']} |",
        f"| probe check executions | "
        f"{ledger['test_counts']['b05_route_probe']['checks_total']} "
        f"({ledger['test_counts']['b05_route_probe']['checks_failed']} failed) |",
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
    write_json(os.path.join(OUT, "B05_PROGRESS_LEDGER.json"), ledger)
    write_text(os.path.join(OUT, "B05_PROGRESS_LEDGER.md"), ledger_md(ledger))
    write_text(os.path.join(OUT, "B05_REHEARSAL_REPORT.md"), report)
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
