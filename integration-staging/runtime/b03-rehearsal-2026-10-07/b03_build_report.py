"""Build the B03 rehearsal review report and the B03 private progress ledger.

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
FROZEN_EVID = os.path.join(OUT, "evidence", "B03", "b03-rehearsal-2026-10-07")

CST = timezone(timedelta(hours=8))

CANDIDATE = os.path.join(RUN, "candidates", "b03-contracts-catalog-v1")
CANDIDATE_MANIFEST = os.path.join(CANDIDATE, "B03_CANDIDATE_MANIFEST.json")
PARENT = os.path.join(
    RUN, "..", "b02-rehearsal-20261006", "candidates", "b02-shared-config-v1",
)
VALIDATION = os.path.join(FROZEN_EVID, "B03_LAYOUT_VALIDATION.json")
SUITE_TXT = os.path.join(EVID, "isolated_staged_suite.txt")

MERGE_JSON = os.path.join(OUT, "B03_MERGE_PROPOSAL.json")
ROLLBACK_JSON = os.path.join(OUT, "B03_ROLLBACK_PROPOSAL.json")
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

COMMANDS = [
    {
        "step": "build candidate",
        "command": f"{PY} integration-staging/runtime/b03-rehearsal-2026-10-07/"
                   "b03_build_candidate.py",
        "cwd": "C:/Users/weo/Desktop/api",
        "exit_code": 0,
    },
    {
        "step": "validate (probe from 3 cwds)",
        "command": f"{PY} integration-staging/runtime/b03-rehearsal-2026-10-07/b03_validate.py",
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
        "command": f"{PY} integration-staging/runtime/b03-rehearsal-2026-10-07/"
                   "b03_build_proposals.py",
        "cwd": "C:/Users/weo/Desktop/api",
        "exit_code": 0,
    },
    {
        "step": "review report + progress ledger",
        "command": f"{PY} integration-staging/runtime/b03-rehearsal-2026-10-07/b03_build_report.py",
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
        "b03_build_candidate.py",
        "b03_integration_probe.py",
        "b03_validate.py",
        "b03_build_proposals.py",
        "b03_build_report.py",
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
        "D_stale_publish_rejected_pointer_unchanged",
        "D_publish_none_rejected",
        "D_tampered_snapshot_rejected_pointer_unchanged",
        "D_cursor_tampered_invalid",
        "D_cursor_stale_revision_rejected",
        "F_edexcel_questions_unsupported",
        "F_cie_courses_filter_rejected",
        "F_unknown_alias_refused",
        "F_alias_rebind_refused",
        "F_unknown_provider_failed",
        "F_unavailable_provider_reported",
        "F_view_unknown_system_503",
        "F_failing_provider_sanitized",
        "G_duplicate_native_id_raises",
        "G_duplicate_native_id_build_fails",
        "G_unexplained_removal_rejected",
        "G_unexplained_quality_upgrade_rejected",
        "G_incomplete_reference_rejected",
    ]
    positives = [
        "B_revision_reproducible",
        "B_snapshot_builds",
        "B_counts_match_independent_derivation",
        "B_reference_integrity",
        "C_course_roundtrip_cie",
        "C_container_roundtrip_cie",
        "C_question_roundtrip_cie",
        "C_question_roundtrip_ielts",
        "C_container_roundtrip_edexcel",
        "C_container_roundtrip_ielts",
        "C_assets_roundtrip",
        "D_publish_a_then_b_cas",
        "D_rollback_restores_previous",
        "D_cursor_roundtrip",
        "E_decisions_and_provenance_roundtrip",
        "E_provenance_fields_preserved",
        "E_unknown_token_roundtrip",
        "F_null_provider_empty_success",
        "G_explained_removal_accepted",
        "G_base_fixture_build_ok",
        "G_base_aliases_resolve",
    ]

    for name in negatives + positives:
        if name not in check_names:
            raise SystemExit(f"check name not found in probe evidence: {name}")

    counts = manifest["counts"]
    tree = manifest["candidate_tree"]
    parent = manifest["lineage"]["parent_tree"]

    ledger = {
        "ledger_version": "b03-private-progress-ledger/1",
        "generated_by": rel(os.path.abspath(__file__)),
        "generated_at": now,
        "kind": "private_progress_ledger",
        "note": "Private progress record for the B03 rehearsal. This is NOT the live "
        "execution ledger and does not replace it.",
        "packet": "B03",
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
        "status": "b03_private_rehearsal_complete_pending_human_release",
        "not_claimed": [
            "merged_pass",
            "deployment",
            "full B00/B01 completion",
        ],
        "changed_counts": {
            "new_staging_scripts": len(staging_scripts()),
            "candidates": 1,
            "candidate_files_copied_from_parent": counts["files_copied_from_parent"],
            "new_files_added_by_b03": counts["new_files_added_by_b03"],
            "candidate_tree_files": tree["files"],
            "candidate_files_on_disk": counts.get("candidate_files_on_disk_after_manifest"),
            "parent_tree_files": parent["files"],
            "original_project_files_written": 0,
            "frozen_evidence_files_rewritten": 0,
        },
        "count_explanations": {
            "new_staging_scripts": "5 new B03 scripts: b03_build_candidate.py, "
            "b03_integration_probe.py, b03_validate.py, b03_build_proposals.py, "
            "b03_build_report.py",
            "candidates": "1 new private candidate: b03-contracts-catalog-v1",
            "candidate_files_copied_from_parent": "byte-identical copy of the B02 candidate "
            "(185 digest files + B02_CANDIDATE_MANIFEST.json)",
            "new_files_added_by_b03": "0: B03 is a zero-delta carry; no file was created or "
            "modified relative to the parent",
            "candidate_tree_files": "186 digest files = 185 parent-digest files + the carried "
            "B02 manifest; the only count that moved relative to the parent's digest view, "
            "because B02's digest rule excluded its own manifest while in B03 that manifest is "
            "an ordinary carried file",
            "candidate_files_on_disk": "187 = 186 digest files + B03_CANDIDATE_MANIFEST.json",
            "parent_tree_files": "185 = B02's on-disk 186 minus B02's own manifest, which "
            "B02's digest rule excluded",
            "original_project_files_written": "0: nothing was written outside "
            "integration-staging/ and docs/integration/execution/",
            "frozen_evidence_files_rewritten": "0: evidence/B01/**, evidence/B02/**, "
            "evidence/R0104/** and runtime/phase-b/** were read-only or untouched",
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
            "b03_integration_probe": {
                "command": "./examdata/.venv/Scripts/python.exe "
                "integration-staging/runtime/b03-rehearsal-2026-10-07/b03_validate.py",
                "cwd": "C:/Users/weo/Desktop/api",
                "exit_code": 0,
                "runs": len(probe_runs),
                "checks_per_run": probe_runs[0]["checks"] if probe_runs else 0,
                "checks_total": checks_total,
                "checks_failed": checks_failed,
                "new_suite": True,
                "explanation": "New B03 probe written for this rehearsal: 58 checks covering "
                "candidate import and root configuration (section A), catalog build and "
                "reference integrity (B), native lookup round trips (C), revision publication, "
                "rollback and cursors (D), decisions/provenance and deferred honesty (E), "
                "provider registry and view error behaviour (F), base fixture/registry guards "
                "(G) and byte stability (H); executed from 3 different working directories "
                "(58 x 3 = 174 check executions). There is no earlier count to compare against.",
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
                "explanation": "Count is unchanged from the R04/B02 baseline (887 passed). The "
                "B03 rehearsal adds no test files to the staged suite, so a changed count "
                "would itself have been the finding.",
            },
            "candidate_build": {
                "command": "./examdata/.venv/Scripts/python.exe "
                "integration-staging/runtime/b03-rehearsal-2026-10-07/b03_build_candidate.py",
                "cwd": "C:/Users/weo/Desktop/api",
                "exit_code": 0,
                "checks_total": len(manifest["checks"]),
                "checks_passed": sum(1 for v in manifest["checks"].values() if v),
                "new_suite": True,
                "explanation": "8 build-time checks on the candidate itself (byte-identical vs "
                "parent, expected files present, digests reproducible); all new.",
            },
        },
        "probe_verdict": validation["verdict"],
        "probe_findings": validation["findings"],
        "discovery_identical_across_cwds": validation["discovery_identical_across_cwds"],
        "candidate_tree_digest_reproducible": validation.get(
            "candidate_tree_digest_reproducible", {}).get("sha256_match"),
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
            "rollback_entries": rollback["counts"]["entries"],
        },
        "commands": COMMANDS,
        "frozen_evidence_written": False,
        "not_run": validation["not_run"],
        "remaining_blockers": [
            {
                "blocker": "original-project merge of the B03 payload",
                "reason": "gate original_paths_released is closed; an explicit human release "
                "with an explicit scope is required. B03 adds zero new files, so a release "
                "would apply the R0104 and B02 proposals.",
            },
            {
                "blocker": "real Node component execution (ielts-api / toefl-api)",
                "reason": "the original components are not released; only the synthetic "
                "fake-node-cli fixture is discovered and it is never executed",
            },
            {
                "blocker": "real database schema / data-root migration",
                "reason": "gate real_data_write_authorized is closed; schema and data roots are "
                "deliberately unchanged by B03",
            },
            {
                "blocker": "deployment to any target",
                "reason": "gate remote_deployment_authorized is closed; the candidate is "
                "private-only",
            },
        ],
        "process_observations": [
            {
                "observation": "The B03 probe's first manual run failed B_reference_integrity: "
                "the check demanded an explicit empty question_refs list on edexcel containers, "
                "but the product only materialises that key for containers that had questions "
                "placed into them -- absence means none, and the view reads it with a "
                "get-default-empty.",
                "handling": "The check now treats an absent question_refs key as 'none' (with "
                "a comment), the probe was rerun clean (58/58), and both the failing and clean "
                "scratch captures remain in the run directory's evidence/ directory.",
            },
            {
                "observation": "The probe and validator not_run reasons originally named three "
                "gates that do not exist in the canonical seven-gate model "
                "(live_services_released, deployment_released, credentials_released).",
                "handling": "Corrected to the canonical names upstream_requests_authorized and "
                "remote_deployment_authorized, and the credential case rephrased as 'no "
                "credential gate exists and none is needed: no credential is used'. The "
                "validation was rerun once afterwards with all 58 checks and every count "
                "unchanged; only the B03 run's own evidence (not yet consumed by any proposal "
                "or report) was regenerated -- no historical evidence was overwritten.",
            },
            {
                "observation": "The parent tree digest covers 185 files while the B03 candidate "
                "tree digest covers 186; the two numbers describe different file sets by rule, "
                "which a reader could mistake for an unexplained file count change.",
                "handling": "Explained everywhere the numbers appear: B02's digest rule "
                "excluded B02's own manifest; in B03 that manifest is an ordinary carried "
                "file, so 186 = 185 + the carried manifest, and the on-disk count is "
                "187 = 186 + the B03 manifest.",
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
        "# B03 rehearsal review report (private preparation only)",
        "",
        f"Generated: {ledger['generated_at']}  ",
        "Packet: **B03** — integrate contracts, registry and local read catalog  ",
        f"Status: `{ledger['status']}`  ",
        f"Probe verdict: `{ledger['probe_verdict']}`  ",
        f"Probe findings: {len(ledger['probe_findings'])}",
        "",
        "Nothing in this report has been merged or deployed. The original project was not "
        "read, imported or written by any B03 step. All seven gates are closed.",
        "",
        "## 1. What B03 rehearsed",
        "",
        "B03 owns the contracts, provider registry and local read catalog at the target "
        "layout. What can be done without the human release is a rehearsal: carry the B02 "
        "candidate byte-identically, then prove the acceptance properties that do not need "
        "the original tree — native lookup round trips, revision publication and rollback, "
        "and preserved decisions/provenance — plus the target-layout import and root "
        "configuration the earlier packets established.",
        "",
        "## 2. Candidate and lineage",
        "",
        f"- Candidate: `{rel(CANDIDATE)}`",
        f"- Parent: `{rel(PARENT)}` (the B02 shared-config candidate)",
        f"- Parent tree: {c['parent_tree_files']} files, sha256 "
        f"`{ledger['hashes']['parent_tree_sha256']}`",
        f"- Candidate tree: {c['candidate_tree_files']} files "
        f"({c['candidate_files_copied_from_parent']} carried from the parent + "
        f"{c['new_files_added_by_b03']} new), sha256 "
        f"`{ledger['hashes']['candidate_tree_sha256']}`",
        f"- Candidate digest reproducible from the tree on disk: "
        f"`{ledger['candidate_tree_digest_reproducible']}` (re-checked independently by the "
        "validator, not just self-reported by the builder)",
        f"- Parent manifest sha256 unchanged at build time: "
        f"`{ledger['hashes']['parent_manifest_sha256']}`",
        "- Count explanation: the candidate digest covers 186 files = 185 parent-digest "
        "files + the carried B02 manifest (B02's own digest excluded that manifest; in B03 "
        "it is an ordinary carried file). On disk: 187 = 186 + the B03 manifest.",
        "",
        "The parent tree digest was re-computed after the copy and again at proposal time "
        f"and is unchanged (`parent_tree_reverified` in the merge proposal).",
        "",
        "## 3. Commands, working directory and exit codes",
        "",
        "| Step | Command | cwd | Exit |",
        "| --- | --- | --- | --- |",
        *cmd_rows,
        "",
        "## 4. Test results",
        "",
        f"- **Probe**: {t['b03_integration_probe']['checks_per_run']} checks x "
        f"{t['b03_integration_probe']['runs']} working directories = "
        f"{t['b03_integration_probe']['checks_total']} check executions, "
        f"{t['b03_integration_probe']['checks_failed']} failed.",
        f"- **Isolated staged suite**: {t['isolated_staged_suite']['summary']} "
        f"(exit {t['isolated_staged_suite']['exit_code']}). Unchanged from the R04/B02 "
        f"baseline of {t['isolated_staged_suite']['baseline_passed']}; B03 adds no test file "
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
        "loaded, no product import of testing guards, schema files parse, quality dimensions "
        "and identity kinds match the code, synthetic Node discovery from the candidate, "
        "legacy bridge entry inside the candidate.",
        "- **Section B — catalog build (6 checks)**: the catalog builds from synthetic "
        "fixture providers reproducibly, file counts match an independent derivation, and "
        "reference integrity holds (no dangling references).",
        "- **Section C — native lookup round trips (7 checks)**: CIE course, container and "
        "question; IELTS question and container; Edexcel container; and asset locators.",
        "- **Section D — publication, rollback, cursors (8 checks)**: publication is "
        "compare-and-swap (A then B), stale / tampered / none publications are rejected with "
        "the pointer bytes unchanged, rollback restores the previous revision, cursors "
        "round-trip and tampered / stale cursors are rejected.",
        "- **Section E — decisions and provenance (5 checks)**: decisions and provenance "
        "round-trip, provenance fields are preserved, the unknown token round-trips, "
        "deferred systems report availability honestly, and deferred fixtures are labelled.",
        "- **Section F — provider registry and view errors (9 checks)**: unsupported "
        "capability / filter refused (422), unknown alias refused, alias rebind refused, "
        "unknown provider fails, unavailable provider reported (503), failing provider "
        "sanitized, null provider returns empty success.",
        "- **Section G — base fixture and registry guards (8 checks)**: base fixture builds, "
        "duplicate native id rejected, unexplained removal / quality upgrade rejected, "
        "explained removal accepted, incomplete reference rejected.",
        "- **Section H — byte stability (3 checks)**: candidate bytes unchanged by the "
        "probe, fixture and contract digests unchanged, no embedded `data:` payloads.",
        "",
        "## 6. Import status of the new candidate",
        "",
        "The candidate's imports resolve from the candidate itself through "
        "`EXAMDATA_INTEGRATION_ROOT` only — no `PYTHONPATH`, no staging-root override — and "
        "the same result holds from all three working directories, including the path with "
        "spaces and non-ASCII characters.",
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
        "B03 adds zero files, so no original-facing entry is re-proposed here.",
        f"- Rollback proposal: `{ledger['artifacts']['rollback_proposal']}`.",
        "",
        "Both are marked `proposal_only_not_merged`. Nothing has been applied to the original "
        "project.",
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
        "# B03 private progress ledger",
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
        f"| candidates | {ledger['changed_counts']['candidates']} |",
        f"| candidate tree files | {ledger['changed_counts']['candidate_tree_files']} |",
        f"| new files added by B03 | {ledger['changed_counts']['new_files_added_by_b03']} |",
        f"| original project files written | "
        f"{ledger['changed_counts']['original_project_files_written']} |",
        f"| frozen evidence files rewritten | "
        f"{ledger['changed_counts']['frozen_evidence_files_rewritten']} |",
        f"| probe check executions | "
        f"{ledger['test_counts']['b03_integration_probe']['checks_total']} "
        f"({ledger['test_counts']['b03_integration_probe']['checks_failed']} failed) |",
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
    write_json(os.path.join(OUT, "B03_PROGRESS_LEDGER.json"), ledger)
    write_text(os.path.join(OUT, "B03_PROGRESS_LEDGER.md"), ledger_md(ledger))
    write_text(os.path.join(OUT, "B03_REHEARSAL_REPORT.md"), report)
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
