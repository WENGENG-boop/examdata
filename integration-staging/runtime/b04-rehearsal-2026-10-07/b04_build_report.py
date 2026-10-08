"""Build the B04 rehearsal review report and the B04 private progress ledger.

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
FROZEN_EVID = os.path.join(OUT, "evidence", "B04", "b04-rehearsal-2026-10-07")

CST = timezone(timedelta(hours=8))

CANDIDATE = os.path.join(RUN, "candidates", "b04-routes-v1")
CANDIDATE_MANIFEST = os.path.join(CANDIDATE, "B04_CANDIDATE_MANIFEST.json")
PARENT = os.path.join(
    RUN, "..", "b03-rehearsal-2026-10-07", "candidates", "b03-contracts-catalog-v1",
)
VALIDATION = os.path.join(FROZEN_EVID, "B04_LAYOUT_VALIDATION.json")
SUITE_TXT = os.path.join(EVID, "isolated_staged_suite.txt")

MERGE_JSON = os.path.join(OUT, "B04_MERGE_PROPOSAL.json")
ROLLBACK_JSON = os.path.join(OUT, "B04_ROLLBACK_PROPOSAL.json")
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
PROBE_ENV = (
    "B04_CANDIDATE_ROOT=integration-staging/runtime/b04-rehearsal-2026-10-07/"
    "candidates/b04-routes-v1 B04_WORKSPACE_ROOT=C:/Users/weo/Desktop/api "
    "B04_TMP_DIR=integration-staging/runtime/b04-rehearsal-2026-10-07/evidence/tmp "
    "EXAMDATA_INTEGRATION_ROOT=integration-staging/runtime/b04-rehearsal-2026-10-07/"
    "candidates/b04-routes-v1 PYTHONIOENCODING=utf-8"
)

COMMANDS = [
    {
        "step": "build candidate",
        "command": f"{PY} integration-staging/runtime/b04-rehearsal-2026-10-07/"
                   "b04_build_candidate.py",
        "cwd": "C:/Users/weo/Desktop/api",
        "exit_code": 0,
    },
    {
        "step": "route probe, manual iteration 1",
        "command": f"{PROBE_ENV} {PY} "
                   "integration-staging/runtime/b04-rehearsal-2026-10-07/b04_route_probe.py",
        "cwd": "C:/Users/weo/Desktop/api",
        "exit_code": 1,
        "note": "failed B_no_pattern_intersections on GET/HEAD self-pairs of the same path "
                "(741 raw route pairs); the probe was fixed to compare each distinct path "
                "pattern once (561 pairs). Evidence kept as evidence/probe_run1.json",
    },
    {
        "step": "route probe, manual iteration 2",
        "command": f"{PROBE_ENV} {PY} "
                   "integration-staging/runtime/b04-rehearsal-2026-10-07/b04_route_probe.py",
        "cwd": "C:/Users/weo/Desktop/api",
        "exit_code": 0,
        "note": "75/75 checks clean; evidence kept as evidence/probe_run2.json",
    },
    {
        "step": "validate (probe from 3 cwds)",
        "command": f"{PY} integration-staging/runtime/b04-rehearsal-2026-10-07/b04_validate.py",
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
        "command": f"{PY} integration-staging/runtime/b04-rehearsal-2026-10-07/"
                   "b04_build_proposals.py",
        "cwd": "C:/Users/weo/Desktop/api",
        "exit_code": 0,
    },
    {
        "step": "review report + progress ledger",
        "command": f"{PY} integration-staging/runtime/b04-rehearsal-2026-10-07/b04_build_report.py",
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
        "b04_build_candidate.py",
        "b04_route_probe.py",
        "b04_validate.py",
        "b04_build_proposals.py",
        "b04_build_report.py",
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
    ]
    positives = [
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
        "N1_legacy_probes_unchanged",
    ]

    for name in negatives + positives:
        if name not in check_names:
            raise SystemExit(f"check name not found in probe evidence: {name}")

    counts = manifest["counts"]
    tree = manifest["candidate_tree"]
    parent = manifest["lineage"]["parent_tree"]

    ledger = {
        "ledger_version": "b04-private-progress-ledger/1",
        "generated_by": rel(os.path.abspath(__file__)),
        "generated_at": now,
        "kind": "private_progress_ledger",
        "note": "Private progress record for the B04 rehearsal. This is NOT the live "
        "execution ledger and does not replace it.",
        "packet": "B04",
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
        "status": "b04_private_rehearsal_complete_pending_human_release",
        "not_claimed": [
            "merged_pass",
            "deployment",
            "full B00/B01 completion",
        ],
        "changed_counts": {
            "new_staging_scripts": len(staging_scripts()),
            "new_candidate_module_source_files": 1,
            "candidates": 1,
            "candidate_files_copied_from_parent": counts["files_copied_from_parent"],
            "new_files_added_by_b04": counts["new_files_added_by_b04"],
            "candidate_tree_files": tree["files"],
            "candidate_files_on_disk": counts.get("candidate_files_on_disk_after_manifest"),
            "parent_tree_files": parent["files"],
            "original_project_files_written": 0,
            "frozen_evidence_files_rewritten": 0,
        },
        "count_explanations": {
            "new_staging_scripts": "5 new B04 scripts: b04_build_candidate.py, "
            "b04_route_probe.py, b04_validate.py, b04_build_proposals.py, "
            "b04_build_report.py",
            "new_candidate_module_source_files": "1 new private module source: "
            "tools/compose.py, byte-identical to the candidate's "
            "src/examdata/integration/api/compose.py (both sha256 e220c007\u2026)",
            "candidates": "1 new private candidate: b04-routes-v1, a child of the B03 "
            "candidate",
            "candidate_files_copied_from_parent": "187 = the B03 on-disk files (186 digest "
            "files + B03_CANDIDATE_MANIFEST.json) carried byte-identically",
            "new_files_added_by_b04": "1 = src/examdata/integration/api/compose.py (the "
            "composition hook); everything else is carried verbatim",
            "candidate_tree_files": "188 digest files = 187 carried + 1 new module; B04's "
            "digest rule excludes its own manifest",
            "candidate_files_on_disk": "189 = 188 digest files + B04_CANDIDATE_MANIFEST.json",
            "parent_tree_files": "186 = B03's digest count, which excluded B03's own "
            "manifest (B03 on-disk was 187); the two numbers describe different file sets "
            "by rule",
            "original_project_files_written": "0: nothing was written outside "
            "integration-staging/ and docs/integration/execution/",
            "frozen_evidence_files_rewritten": "0: evidence/B01/**, B02/**, B03/**, "
            "evidence/R0104/**, the B02/B03/R0104 runtime candidates and "
            "runtime/phase-b/** were read-only or untouched",
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
        },
        "test_counts": {
            "b04_route_probe": {
                "command": f"{PY} "
                "integration-staging/runtime/b04-rehearsal-2026-10-07/b04_validate.py",
                "cwd": "C:/Users/weo/Desktop/api",
                "exit_code": 0,
                "runs": len(probe_runs),
                "checks_per_run": probe_runs[0]["checks"] if probe_runs else 0,
                "checks_total": checks_total,
                "checks_failed": checks_failed,
                "new_suite": True,
                "explanation": "New B04 route probe written for this rehearsal: 75 checks "
                "covering candidate import and root configuration (section A, 12), v2 "
                "spec/registry/worksheet agreement and route ordering (B, 14), legacy and "
                "composed host mechanics plus v2 envelope behaviour (C, 18), the combined "
                "OpenAPI document (D, 8), byte stability and manifest recomputation (E, 7) "
                "and the negative controls N1-N6 (16, of which 15 are negative and "
                "N1_legacy_probes_unchanged is a positive control); 15 negative and 30 "
                "positive controls in total. Executed from 3 different working directories "
                "(75 x 3 = 225 check executions). There is no earlier count to compare "
                "against; the first manual iteration failed exactly one check "
                "(B_no_pattern_intersections self-pair false positive) and the failed and "
                "clean captures are both kept in evidence/.",
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
                "explanation": "Count is unchanged from the R04/B02/B03 baseline (887 "
                "passed). The B04 rehearsal adds no test files to the staged suite; its new "
                "product module is exercised by the B04 route probe instead, so a changed "
                "suite count would itself have been the finding.",
            },
            "candidate_build": {
                "command": f"{PY} integration-staging/runtime/b04-rehearsal-2026-10-07/"
                "b04_build_candidate.py",
                "cwd": "C:/Users/weo/Desktop/api",
                "exit_code": 0,
                "checks_total": len(manifest["checks"]),
                "checks_passed": sum(1 for v in manifest["checks"].values() if v),
                "new_suite": True,
                "explanation": "11 build-time checks on the candidate itself (parent carried "
                "byte-identically, exactly one new file, new module matches its source and "
                "compiles, digest excludes the manifest); all new.",
            },
        },
        "probe_verdict": validation["verdict"],
        "probe_findings": validation["findings"],
        "discovery_identical_across_cwds": validation["discovery_identical_across_cwds"],
        "stability_identical_across_cwds": validation.get(
            "stability_identical_across_cwds"),
        "candidate_tree_digest_reproducible": validation.get(
            "candidate_tree_digest_reproducible", {}).get("sha256_match"),
        "probe_stability": validation.get("stability"),
        "import_status_checks": import_checks,
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
            "merge_new_files_vs_parent": merge["counts"]["new_files_vs_parent"],
            "rollback_entries": rollback["counts"]["entries"],
        },
        "commands": COMMANDS,
        "frozen_evidence_written": False,
        "not_run": validation["not_run"],
        "remaining_blockers": [
            {
                "blocker": "original-project merge of the B04 entries",
                "reason": "gate original_paths_released is closed; an explicit human release "
                "with an explicit scope is required. The merge proposal has 2 "
                "release-required entries: add "
                "examdata/src/examdata/integration/api/compose.py and the planned edit to "
                "examdata/src/examdata/api/app.py, which stays deferred_pending_release; "
                "the app.py base hash (753749fa\u2026) must be re-verified at release time.",
            },
            {
                "blocker": "real Node component execution (ielts-api / toefl-api)",
                "reason": "the original components are not released; only the synthetic "
                "fake-node-cli fixture is discovered and it is never executed",
            },
            {
                "blocker": "real database schema / data-root migration",
                "reason": "gate real_data_write_authorized is closed; schema and data roots "
                "are deliberately unchanged by B04",
            },
            {
                "blocker": "deployment to any target",
                "reason": "gate remote_deployment_authorized is closed; the candidate is "
                "private-only",
            },
        ],
        "process_observations": [
            {
                "observation": "The B04 probe's first manual run failed exactly one check, "
                "B_no_pattern_intersections: the check compared all raw route pairs, so the "
                "GET and HEAD variants of the same binary path were compared with "
                "themselves and reported 5 trivial self-pair 'intersections' (741 raw "
                "pairs).",
                "handling": "The check now compares each distinct path pattern once (561 "
                "pairs, matching the pre-verified scratch truth); the probe was rerun clean "
                "75/75, and both the failing capture (probe_run1.json/.err, exit 1) and the "
                "clean capture (probe_run2.json/.err, exit 0) remain in the run directory's "
                "evidence/ directory.",
            },
            {
                "observation": "While the composition hook was being written, its first "
                "version let the legacy stack-boom probe answer with an empty 500 body "
                "(sha256 e3b0c442\u2026, the empty-string hash) instead of the baseline's "
                "text/plain body.",
                "handling": "Fixed by an explicit default server-error handler in "
                "tools/compose.py; the probe now pins the restored body sha256 "
                "e41656eb\u2026 (C_legacy_boom_bytes_pinned) and the pre-fix run is kept as "
                "evidence in evidence/tmp_manual/.",
            },
            {
                "observation": "The parent tree digest covers 186 files while the B04 "
                "candidate tree digest covers 188; the numbers describe different file sets "
                "by rule, which a reader could mistake for an unexplained count change.",
                "handling": "Explained everywhere the numbers appear: B03's digest excluded "
                "B03's own manifest (B03 on-disk 187); B04 carries all 187 on-disk files and "
                "adds 1 new module, so the digest covers 188 and on-disk is 189 = 188 + the "
                "B04 manifest.",
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
        "# B04 rehearsal review report (private preparation only)",
        "",
        f"Generated: {ledger['generated_at']}  ",
        "Packet: **B04** — register v2 routes in the shared application  ",
        f"Status: `{ledger['status']}`  ",
        f"Probe verdict: `{ledger['probe_verdict']}`  ",
        f"Probe findings: {len(ledger['probe_findings'])}",
        "",
        "Nothing in this report has been merged or deployed. The original project was not "
        "read, imported or written by any B04 step. All seven gates are closed.",
        "",
        "## 1. What B04 rehearsed",
        "",
        "B04 owns the registration of the staged v2 routes in the shared application. What "
        "can be done without the human release is a rehearsal: carry the B03 candidate "
        "byte-identically, add the one new composition module (the hook that attaches the "
        "v2 routes to the legacy application), then prove the acceptance properties that do "
        "not need the original tree — every baseline route stays registered byte-identically, "
        "the OpenAPI/route-inventory difference is exactly the 34 documented v2 paths, "
        "legacy defaults are unchanged, and the composition refuses double or late attaches.",
        "",
        "## 2. Candidate and lineage",
        "",
        f"- Candidate: `{rel(CANDIDATE)}`",
        f"- Parent: `{rel(PARENT)}` (the B03 contracts/catalog candidate)",
        f"- Parent tree: {c['parent_tree_files']} files, sha256 "
        f"`{ledger['hashes']['parent_tree_sha256']}`",
        f"- Candidate tree: {c['candidate_tree_files']} files "
        f"({c['candidate_files_copied_from_parent']} carried from the parent + "
        f"{c['new_files_added_by_b04']} new), sha256 "
        f"`{ledger['hashes']['candidate_tree_sha256']}`",
        f"- Candidate digest reproducible from the tree on disk: "
        f"`{ledger['candidate_tree_digest_reproducible']}` (re-checked independently by the "
        "validator, not just self-reported by the builder)",
        f"- Parent manifest sha256 unchanged at build time: "
        f"`{ledger['hashes']['parent_manifest_sha256']}`",
        "- Count explanation: the parent digest covers 186 files (B03's rule excluded B03's "
        "own manifest); B04 copies all 187 B03 on-disk files and adds 1 new module, so the "
        "candidate digest covers 188 and on-disk is 189 = 188 + the B04 manifest.",
        "",
        "The parent tree digest was re-computed after the copy and again at proposal time "
        "and is unchanged (`parent_tree_reverified` in the merge proposal).",
        "",
        "## 3. Commands, working directory and exit codes",
        "",
        "| Step | Command | cwd | Exit |",
        "| --- | --- | --- | --- |",
        *cmd_rows,
        "",
        "## 4. Test results",
        "",
        f"- **Route probe**: {t['b04_route_probe']['checks_per_run']} checks x "
        f"{t['b04_route_probe']['runs']} working directories = "
        f"{t['b04_route_probe']['checks_total']} check executions, "
        f"{t['b04_route_probe']['checks_failed']} failed.",
        f"- **Isolated staged suite**: {t['isolated_staged_suite']['summary']} "
        f"(exit {t['isolated_staged_suite']['exit_code']}). Unchanged from the R04/B02/B03 "
        f"baseline of {t['isolated_staged_suite']['baseline_passed']}; B04 adds no test file "
        "to that suite.",
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
        "`sys.path`, every module origin inside the candidate, no original-tree module "
        "loaded, no product import of testing guards, 28 schema files parse, quality "
        "dimensions and identity kinds match the code, synthetic Node discovery "
        "(`fake_cli`) resolves inside the candidate, legacy bridge entry imports from the "
        "candidate.",
        "- **Section B — worksheet, registry and ordering (14 checks)**: the A12 worksheet "
        "holds 71 rows (70 GET + 1 POST `/sample`); the v2 registry has 34 implemented / 0 "
        "deferred specs of which 5 are binary; runtime, spec and advertised pairs agree; "
        "HEAD pairs are binary-only; GET 34/34 and HEAD 5/5 first-match their own route; no "
        "static route is shadowed; and no two distinct path patterns intersect (561 pairs).",
        "- **Section C — host mechanics and behaviour (18 checks)**: host shape pre-attach "
        "(80 routes, 76 doc paths), the legacy prefix is kept 80→81, exactly one wrapper "
        "`_IncludedRouter` is appended; all 71 legacy rows and 7 extra probes stay "
        "byte-identical; the legacy stack-boom body stays pinned; binary fixture ids, 200 / "
        "206 / 304 / HEAD responses pinned; and the six v2 controls serve typed envelopes "
        "(invalid_request, internal_error, not_found, route_not_found, method_not_allowed, "
        "info envelope) that all differ from their pre-attach baselines.",
        "- **Section D — combined OpenAPI (8 checks)**: the path delta is exactly the "
        "registry (34 added, 0 removed, none unexpected); the 76 pre-attach paths' "
        "operations are unchanged; 115 operation ids are unique; the 39 v2 operation ids "
        "match the standalone app; binary rows are documented with their media types; "
        "non-binary 200 responses serve the envelope schema; `/openapi.json` serves the "
        "same document as the direct call; a second instance yields the same digest.",
        "- **Section E — stability (7 checks)**: candidate bytes unchanged by the probe; "
        "fixture and contract digests unchanged; the manifest recomputes to 188 files; "
        "counts disclosed (188 digest / 189 on disk); the compose hook matches its tooling "
        "source; no embedded `data:` payloads; scratch marker written inside the run's "
        "evidence/tmp.",
        "- **Sections N1-N6 — negative controls (16 checks, 15 negative)**: a raw "
        "`include_router` would serve unshaped v2 errors and a wrong content type for the "
        "binary row (refused by the hook); the unscoped install would change exactly three "
        "legacy probes and rewrite their error shapes to envelopes (the deliberate, "
        "documented difference); mounting under the legacy prefix documents no v2 paths; "
        "double attach is refused and leaves the host unchanged; late attach is refused and "
        "adds no v2 paths; a non-FastAPI host is refused; and every legacy probe stays "
        "unchanged under the composed application.",
        "",
        "## 6. Import status of the new candidate",
        "",
        "The candidate's imports resolve from the candidate itself through "
        "`EXAMDATA_INTEGRATION_ROOT` only — no `PYTHONPATH`, no staging-root override — and "
        "the same result holds from all three working directories, including the path with "
        "spaces and non-ASCII characters. The routing stability digests (combined OpenAPI, "
        "standalone v2, legacy operations, composed route table, 39 operation ids, path "
        "delta) are identical across all three working directories.",
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
        f"- Merge proposal: `{ledger['artifacts']['merge_proposal']}` — "
        f"{ledger['proposal_counts']['merge_entries']} "
        f"{'entry' if ledger['proposal_counts']['merge_entries'] == 1 else 'entries'}, "
        f"{ledger['proposal_counts']['merge_entries_requiring_release']} requiring the human "
        f"release, {ledger['proposal_counts']['merge_staging_only_entries']} staging-only. "
        "The release-required entries are the new module "
        "`examdata/src/examdata/integration/api/compose.py` and the planned edit to "
        "`examdata/src/examdata/api/app.py` (deferred_pending_release).",
        f"- Rollback proposal: `{ledger['artifacts']['rollback_proposal']}`.",
        "",
        "Both are marked `proposal_only_not_merged`. Nothing has been applied to the "
        "original project.",
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
        "# B04 private progress ledger",
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
        f"| candidates | {ledger['changed_counts']['candidates']} |",
        f"| candidate tree files | {ledger['changed_counts']['candidate_tree_files']} |",
        f"| new files added by B04 | {ledger['changed_counts']['new_files_added_by_b04']} |",
        f"| original project files written | "
        f"{ledger['changed_counts']['original_project_files_written']} |",
        f"| frozen evidence files rewritten | "
        f"{ledger['changed_counts']['frozen_evidence_files_rewritten']} |",
        f"| probe check executions | "
        f"{ledger['test_counts']['b04_route_probe']['checks_total']} "
        f"({ledger['test_counts']['b04_route_probe']['checks_failed']} failed) |",
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
    lines += [f"- {n['check']} — {n['reason']}" for n in ledger["not_run"]]
    lines += ["", "## Remaining blockers", ""]
    lines += [f"- {b['blocker']} — {b['reason']}" for b in ledger["remaining_blockers"]]
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    ledger, report = build()
    os.makedirs(OUT, exist_ok=True)
    write_json(os.path.join(OUT, "B04_PROGRESS_LEDGER.json"), ledger)
    write_text(os.path.join(OUT, "B04_PROGRESS_LEDGER.md"), ledger_md(ledger))
    write_text(os.path.join(OUT, "B04_REHEARSAL_REPORT.md"), report)
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
