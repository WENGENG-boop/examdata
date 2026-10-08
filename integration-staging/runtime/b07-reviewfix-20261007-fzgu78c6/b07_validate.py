"""B07 rehearsal validation: run the B07 route probe from several working directories.

The probe is launched as a subprocess whose environment is deliberately stripped
of the two crutches this rehearsal must not rely on:

* ``PYTHONPATH`` is removed -- the candidate ``src/`` tree is put on the import
  path by the probe itself;
* ``EXAMDATA_INTEGRATION_STAGING_ROOT`` is removed -- the candidate root is
  supplied only through the explicit product variable
  ``EXAMDATA_INTEGRATION_ROOT``, and the operations root only through
  ``EXAMDATA_OPERATIONS_ROOT`` (pointed at the candidate's own synthetic
  fixture; ``EXAMDATA_API_KEY`` carries the fixture-labelled synthetic control
  string, never a real credential).

The same probe runs from three working directories -- the workspace root, the
private tmp directory, and a directory whose name contains spaces and non-ASCII
characters -- and the component-discovery result, the routing stability digests,
the B06 active-owner seam block, the staged-frontend tree projection, the
resource-discovery projection, the cross-stack rehearsal summary and the B07
operations-view block must be identical in all three. Volatile-by-design values
(ephemeral ports, process stdout tails, client-observation URLs that embed the
ephemeral port) are projected out before comparison. The byte-comparison
against the frozen B06 progress ledger must hold in every working directory,
and the candidate tree digest recorded in ``B07R_CANDIDATE_MANIFEST.json`` is
recomputed here, independently of the builder, so the rollback guard ("delete
only if the tree still matches") is checkable rather than merely asserted.

Writes evidence into a *new* directory under
``docs/integration/execution/evidence/B07/b07-reviewfix-20261007-fzgu78c6/``. Frozen
historical evidence (``evidence/B00/**`` ... ``evidence/B06/**``, the B02..B06
and R0104 runtime directories, ``runtime/phase-b/**``) is never touched.
"""
# Adapted copy of the frozen B07 validator (b07-rehearsal-2026-10-07) for the
# private review-fix rehearsal: RUN_ID / DESTINATION / MANIFEST_NAME and the
# docstring paths track the new candidate and evidence directory; all
# assertions are carried unchanged.
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[3]        # C:/Users/weo/Desktop/api
RUN_DIR = pathlib.Path(__file__).resolve().parent
RUN_ID = "b07-reviewfix-20261007-fzgu78c6"
DESTINATION = "b07-operations-v2"
CANDIDATE = ROOT / "integration-staging" / "runtime" / RUN_ID / "candidates" / DESTINATION
OPERATIONS_ROOT = CANDIDATE / "fixtures" / "synthetic" / "operations" / "operations-root"
SYNTHETIC_API_KEY = "REDACTED_LOCAL_CREDENTIAL"
EVIDENCE = ROOT / "docs" / "integration" / "execution" / "evidence" / "B07" / RUN_ID
TMP_DIR = RUN_DIR / "evidence" / "tmp"
SPACED_CWD = TMP_DIR / "cwd with spaces \u00fcn\u00efcode"
PY = ROOT / "examdata" / ".venv" / "Scripts" / "python.exe"

PROBE = "b07_route_probe.py"
MANIFEST_NAME = "B07R_CANDIDATE_MANIFEST.json"

STABILITY_KEYS = (
    "combined_openapi_digest",
    "v2_standalone_digest",
    "legacy_ops_digest",
    "composed_route_table_digest",
    "v2_operation_ids",
    "path_delta",
)

SEAM_KEYS = (
    "fixture_counts",
    "default_syllabus_ids",
    "route_statuses",
    "route_counts",
    "deferred",
    "private_injection",
)

LEDGER_KEYS = (
    "ledger_path",
    "ledger_sha256",
    "digest_mismatches",
    "ids_match",
    "ledger_ids",
    "probe_ids",
    "ledger_path_delta",
    "probe_path_delta",
)


def probe_env() -> dict:
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    env.pop("EXAMDATA_INTEGRATION_STAGING_ROOT", None)
    env["B07_CANDIDATE_ROOT"] = str(CANDIDATE)
    env["B07_WORKSPACE_ROOT"] = str(ROOT)
    env["B07_TMP_DIR"] = str(TMP_DIR)
    env["EXAMDATA_INTEGRATION_ROOT"] = str(CANDIDATE)
    env["EXAMDATA_OPERATIONS_ROOT"] = str(OPERATIONS_ROOT)
    env["EXAMDATA_API_KEY"] = SYNTHETIC_API_KEY
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def run_probe(cwd: pathlib.Path) -> dict:
    path = RUN_DIR / PROBE
    env = probe_env()
    proc = subprocess.run([str(PY), str(path)], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", env=env, cwd=str(cwd),
                          timeout=900)
    out = (proc.stdout or "").strip()
    try:
        parsed = json.loads(out) if out else None
    except json.JSONDecodeError:
        parsed = None
    return {
        "cwd": str(cwd),
        "exit_code": proc.returncode,
        "report": parsed,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "env_pythonpath": env.get("PYTHONPATH"),
        "env_staging_override": env.get("EXAMDATA_INTEGRATION_STAGING_ROOT"),
        "env_root": env.get("EXAMDATA_INTEGRATION_ROOT"),
        "env_operations_root": env.get("EXAMDATA_OPERATIONS_ROOT"),
        "env_api_key_synthetic": env.get("EXAMDATA_API_KEY") == SYNTHETIC_API_KEY,
    }


def discovery_of(report: dict | None) -> dict | None:
    if not report:
        return None
    found = report.get("discovery", {}).get("from_candidate_cwd")
    if not found:
        return None
    return {k: found.get(k) for k in ("ids", "problems", "entry_path", "deployment_root")}


def stability_of(report: dict | None) -> dict | None:
    if not report:
        return None
    block = report.get("stability")
    if not isinstance(block, dict) or set(block) != set(STABILITY_KEYS):
        return None
    return block


def seam_of(report: dict | None) -> dict | None:
    if not report:
        return None
    block = report.get("seam")
    if not isinstance(block, dict) or set(block) != set(SEAM_KEYS):
        return None
    return block


def operations_of(report: dict | None) -> dict | None:
    """The B07 operations-view block (J section): derived from the candidate's
    own synthetic fixture root, expected to be fully deterministic, so the
    whole block is compared across working directories."""
    if not report:
        return None
    block = report.get("operations")
    if not isinstance(block, dict) or not block:
        return None
    return block


def frontend_of(report: dict | None) -> dict | None:
    """The staged-frontend projection, with volatile tails projected out.

    ``node_test`` / ``node_check`` keep only exit codes and counts: the raw
    stdout tails carry per-run durations. The node path itself is dropped for
    the same reason the version is kept -- only the interpreter's behaviour is
    under comparison.
    """
    if not report:
        return None
    block = report.get("frontend")
    if not isinstance(block, dict):
        return None
    node = block.get("node") or {}
    node_check = block.get("node_check") or {}
    node_test = block.get("node_test") or {}
    return {
        "files": block.get("files"),
        "provenance": block.get("provenance"),
        "node_version": node.get("version"),
        "node_check_exits": {rel: entry.get("exit") for rel, entry in node_check.items()},
        "node_test": {"exit": node_test.get("exit"), "counts": node_test.get("counts")},
    }


def projection_of(report: dict | None) -> dict | None:
    """The resource-discovery projection (G section): expected to be fully
    deterministic, so the whole block is compared."""
    if not report:
        return None
    block = report.get("discovery_projection")
    if not isinstance(block, dict) or not block:
        return None
    return block


def cross_of(report: dict | None) -> dict | None:
    """The cross-stack rehearsal summary (H section), with the ephemeral ports
    and port-bearing observation URLs projected out."""
    if not report:
        return None
    block = report.get("cross_stack")
    if not isinstance(block, dict):
        return None
    cross = block.get("cross") or {}
    teardown = block.get("teardown") or {}
    banner = block.get("banner") or {}
    return {
        "cross": {"exit": cross.get("exit"), "ok": cross.get("ok"),
                  "counts": cross.get("counts"), "failed": cross.get("failed")},
        "content_triple": block.get("content_triple"),
        "banner_seen": banner.get("port") is not None,
        "teardown": {"returncode_present": teardown.get("frontend_returncode") is not None,
                     "upstream_stopped": teardown.get("upstream_stopped")},
    }


def ledger_of(report: dict | None) -> dict | None:
    if not report:
        return None
    block = report.get("b07_vs_b06_stability")
    if not isinstance(block, dict) or set(block) != set(LEDGER_KEYS):
        return None
    return block


def ledger_consistent(block: dict | None) -> bool:
    return bool(
        block
        and block.get("ids_match") is True
        and not block.get("digest_mismatches")
        and block.get("ledger_path_delta") == 34
        and block.get("probe_path_delta") == 34
    )


SKIP_DIRS = {"__pycache__", ".pytest_cache"}


def digest_of(base: pathlib.Path, exclude: tuple[str, ...] = ()) -> dict:
    """Independent re-implementation of the candidate tree digest.

    Deliberately not imported from the builder: the point is to reproduce the
    recorded value a second time, so that the rollback guard ("delete only if the
    tree still matches") is checkable rather than merely asserted.
    """
    entries: list[tuple[str, str]] = []
    for p in sorted(base.rglob("*")):
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        if p.is_file():
            rel = p.relative_to(base).as_posix()
            if rel in exclude:
                continue
            entries.append((rel, hashlib.sha256(p.read_bytes()).hexdigest()))
    digest = hashlib.sha256()
    for rel, h in entries:
        digest.update(f"{rel}\0{h}\n".encode("utf-8"))
    return {"files": len(entries), "sha256": digest.hexdigest()}


def files_on_disk(base: pathlib.Path) -> int:
    return sum(1 for p in base.rglob("*")
               if p.is_file() and not any(part in SKIP_DIRS for part in p.parts))


def digest_reproducibility() -> dict:
    manifest_path = CANDIDATE / MANIFEST_NAME
    raw = manifest_path.read_bytes()
    manifest = json.loads(raw.decode("utf-8"))
    recorded = manifest["candidate_tree"]
    recomputed = digest_of(CANDIDATE, tuple(recorded.get("excludes", [])))
    on_disk = files_on_disk(CANDIDATE)
    return {
        "recorded": recorded,
        "recomputed": recomputed,
        "files_match": recomputed["files"] == recorded["files"],
        "sha256_match": recomputed["sha256"] == recorded["sha256"],
        "files_on_disk": on_disk,
        "on_disk_matches_recorded_plus_manifest": on_disk == recorded["files"] + 1,
        "manifest_sha256": hashlib.sha256(raw).hexdigest(),
    }


def main() -> int:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    SPACED_CWD.mkdir(parents=True, exist_ok=True)

    if not CANDIDATE.is_dir():
        print(json.dumps({"verdict": "candidate_missing", "candidate": str(CANDIDATE)},
                         ensure_ascii=True, indent=2))
        return 1

    cwds = (ROOT, TMP_DIR, SPACED_CWD)
    results: list[dict] = []
    findings: list[dict] = []
    transcript: list[str] = []

    for cwd in cwds:
        result = run_probe(cwd)
        results.append(result)
        tag = f"cwd={cwd}"
        transcript.append(f"===== {tag} =====")
        transcript.append(f"$ cd {cwd} && {PY} {RUN_DIR / PROBE}")
        transcript.append("env PYTHONPATH=<unset> EXAMDATA_INTEGRATION_STAGING_ROOT=<unset> "
                          f"EXAMDATA_INTEGRATION_ROOT={CANDIDATE}")
        transcript.append(f"env EXAMDATA_OPERATIONS_ROOT={OPERATIONS_ROOT} "
                          "EXAMDATA_API_KEY=<fixture-labelled synthetic control>")
        transcript.append(f"[exit {result['exit_code']}]")
        transcript.append("--- stdout ---")
        transcript.append((result["stdout"] or "").rstrip("\n"))
        transcript.append("--- stderr ---")
        transcript.append((result["stderr"] or "").rstrip("\n"))
        transcript.append("")
        if result["exit_code"] != 0:
            findings.append({
                "id": "B07-PROBE-FAIL",
                "severity": "blocker",
                "cwd": str(cwd),
                "summary": f"{PROBE} exited {result['exit_code']}",
                "failed_checks": (result["report"] or {}).get("failed"),
                "stderr_tail": (result["stderr"] or "")[-600:],
            })
        if result["env_pythonpath"] is not None:
            findings.append({"id": "B07-PYTHONPATH-STAGED", "severity": "blocker",
                             "summary": "PYTHONPATH leaked into the probe environment",
                             "value": result["env_pythonpath"]})
        if result["env_staging_override"] is not None:
            findings.append({"id": "B07-STAGING-OVERRIDE-STAGED", "severity": "blocker",
                             "summary": "staging-root override leaked into the probe environment",
                             "value": result["env_staging_override"]})

    discovered = [discovery_of(r["report"]) for r in results]
    identical = len({json.dumps(d, sort_keys=True) for d in discovered}) == 1 \
        and all(d is not None for d in discovered)
    if not identical:
        findings.append({"id": "B07-DISCOVERY-CWD-DEPENDENT", "severity": "blocker",
                         "summary": "component discovery differs across working directories",
                         "discovery": discovered})

    stabilities = [stability_of(r["report"]) for r in results]
    stability_identical = len({json.dumps(s, sort_keys=True) for s in stabilities}) == 1 \
        and all(s is not None for s in stabilities)
    if not stability_identical:
        findings.append({"id": "B07-STABILITY-CWD-DEPENDENT", "severity": "blocker",
                         "summary": "routing stability digests differ across working "
                                    "directories or are missing",
                         "stability": stabilities})

    seams = [seam_of(r["report"]) for r in results]
    seam_identical = len({json.dumps(s, sort_keys=True) for s in seams}) == 1 \
        and all(s is not None for s in seams)
    if not seam_identical:
        findings.append({"id": "B07-SEAM-CWD-DEPENDENT", "severity": "blocker",
                         "summary": "the active-owner seam block differs across working "
                                    "directories or is missing",
                         "seam": seams})

    operation_blocks = [operations_of(r["report"]) for r in results]
    operations_identical = len({json.dumps(o, sort_keys=True) for o in operation_blocks}) == 1 \
        and all(o is not None for o in operation_blocks)
    if not operations_identical:
        findings.append({"id": "B07-OPERATIONS-CWD-DEPENDENT", "severity": "blocker",
                         "summary": "the operations-view block differs across working "
                                    "directories or is missing",
                         "operations": operation_blocks})

    frontends = [frontend_of(r["report"]) for r in results]
    frontend_identical = len({json.dumps(f, sort_keys=True) for f in frontends}) == 1 \
        and all(f is not None for f in frontends)
    if not frontend_identical:
        findings.append({"id": "B07-FRONTEND-CWD-DEPENDENT", "severity": "blocker",
                         "summary": "the staged-frontend projection differs across working "
                                    "directories or is missing",
                         "frontend": frontends})

    projections = [projection_of(r["report"]) for r in results]
    projection_identical = len({json.dumps(p, sort_keys=True) for p in projections}) == 1 \
        and all(p is not None for p in projections)
    if not projection_identical:
        findings.append({"id": "B07-PROJECTION-CWD-DEPENDENT", "severity": "blocker",
                         "summary": "the resource-discovery projection differs across working "
                                    "directories or is missing",
                         "discovery_projection": projections})

    crosses = [cross_of(r["report"]) for r in results]
    cross_identical = len({json.dumps(c, sort_keys=True) for c in crosses}) == 1 \
        and all(c is not None for c in crosses)
    if not cross_identical:
        findings.append({"id": "B07-CROSS-STACK-CWD-DEPENDENT", "severity": "blocker",
                         "summary": "the cross-stack rehearsal summary differs across working "
                                    "directories or is missing",
                         "cross_stack": crosses})

    ledgers = [ledger_of(r["report"]) for r in results]
    ledgers_consistent = all(ledger_consistent(block) for block in ledgers)
    if not ledgers_consistent:
        findings.append({"id": "B07-B06-LEDGER-MISMATCH", "severity": "blocker",
                         "summary": "the B07 probe did not reproduce the frozen B06 ledger "
                                    "stability values in every working directory",
                         "ledger": ledgers})

    probe_dirs = sorted({(r["report"] or {}).get("discovery", {}).get("from_candidate_cwd", {})
                         .get("cwd") for r in results if r["report"]})

    digest_check = digest_reproducibility()
    if not (digest_check["files_match"] and digest_check["sha256_match"]
            and digest_check["on_disk_matches_recorded_plus_manifest"]):
        findings.append({"id": "B07-DIGEST-NOT-REPRODUCIBLE", "severity": "blocker",
                         "summary": "the candidate tree digest in the manifest is not "
                                    "reproducible from the tree on disk, so the rollback guard "
                                    "would never match",
                         "recorded": digest_check["recorded"],
                         "recomputed": digest_check["recomputed"],
                         "files_on_disk": digest_check["files_on_disk"]})

    summary = {
        "schema": "examdata.integration.b07_rehearsal_validation/1",
        "run_id": RUN_ID,
        "packet": "B07",
        "candidate": str(CANDIDATE),
        "probe": PROBE,
        "runs": [
            {"cwd": r["cwd"], "exit_code": r["exit_code"],
             "checks": (r["report"] or {}).get("counts", {}).get("checks"),
             "checks_failed": (r["report"] or {}).get("counts", {}).get("checks_failed"),
             "ok": (r["report"] or {}).get("ok")}
            for r in results
        ],
        "discovery_identical_across_cwds": identical,
        "discovery": discovered[0] if identical else discovered,
        "stability_identical_across_cwds": stability_identical,
        "stability": stabilities[0] if stability_identical else stabilities,
        "seam_identical_across_cwds": seam_identical,
        "seam": seams[0] if seam_identical else seams,
        "operations_identical_across_cwds": operations_identical,
        "operations": operation_blocks[0] if operations_identical else operation_blocks,
        "frontend_identical_across_cwds": frontend_identical,
        "frontend": frontends[0] if frontend_identical else frontends,
        "discovery_projection_identical_across_cwds": projection_identical,
        "discovery_projection": projections[0] if projection_identical else projections,
        "cross_stack_identical_across_cwds": cross_identical,
        "cross_stack": crosses[0] if cross_identical else crosses,
        "b07_vs_b06_ledger_consistent": ledgers_consistent,
        "b07_vs_b06_stability": ledgers[0] if ledgers_consistent else ledgers,
        "in_process_cwds": probe_dirs,
        "candidate_tree_digest_reproducible": {
            "files_match": digest_check["files_match"],
            "sha256_match": digest_check["sha256_match"],
            "files_on_disk": digest_check["files_on_disk"],
            "on_disk_matches_recorded_plus_manifest":
                digest_check["on_disk_matches_recorded_plus_manifest"],
            "recorded": digest_check["recorded"],
            "recomputed": digest_check["recomputed"],
            "candidate_manifest_sha256": digest_check["manifest_sha256"],
        },
        "findings": findings,
        "not_run": [
            {"check": "real merge into the original project",
             "reason": "gate original_paths_released is closed; the plan entry remains a "
                       "proposal (deferred_pending_release) and the original tree was never "
                       "read or written"},
            {"check": "real active-owner integration (materials, syllabuses and timetables "
                      "served by the original owner modules)",
             "reason": "no owner release exists for the active-owner families; the seam serves "
                       "only clearly labelled synthetic fixtures and the real integration "
                       "stays deferred_active_owner"},
            {"check": "real baseline verification against the actual legacy application",
             "reason": "gate original_paths_released is closed; the legacy side was simulated "
                       "from the frozen A12 route-compatibility worksheet, not from the "
                       "original app"},
            {"check": "real Node component execution (fake-cli.mjs run via the Node runtime)",
             "reason": "gate original_paths_released is closed; only synthetic discovery and "
                       "importability of the component are rehearsed"},
            {"check": "real Node/source validation against the original project",
             "reason": "gate original_paths_released is closed; the original tree was never "
                       "read"},
            {"check": "real database schema / data migration",
             "reason": "gate real_data_write_authorized is closed; no database is staged or "
                       "touched"},
            {"check": "live service / upstream provider calls",
             "reason": "gate upstream_requests_authorized is closed; only synthetic fixture "
                       "providers ran"},
            {"check": "cutover of the existing service",
             "reason": "gate existing_service_cutover_authorized is closed"},
            {"check": "deployment to any target",
             "reason": "gate remote_deployment_authorized is closed; this candidate is "
                       "private-only"},
            {"check": "cleanup of the original project",
             "reason": "gate original_cleanup_authorized is closed"},
            {"check": "credential usage of any kind",
             "reason": "no credential gate exists in the seven-gate model and none is needed: "
                       "no real credential is used, read, fabricated or staged; the only "
                       "credential-shaped value anywhere is the fixture-labelled synthetic "
                       "control string the operations fixtures carry, and the routing controls "
                       "are synthetic request parameters with no secret values"},
            {"check": "real frontend cutover (the staged page and server on the live service)",
             "reason": "gate existing_service_cutover_authorized is closed; the staged frontend "
                       "ran only on an ephemeral 127.0.0.1 port against the private read API"},
            {"check": "real source-provider fetching from the frontend process",
             "reason": "gate upstream_requests_authorized is closed; the candidate frontend "
                       "carries no source-discovery logic and only proxies the private read "
                       "API"},
            {"check": "real job-service interaction (resume / cancel / enqueue against a live "
                      "queue)",
             "reason": "no job-service release exists and none is needed: the operations view "
                       "is read-only by construction, and a stopped job is only observed as "
                       "stopped; it is never resumed, restarted or written back"},
            {"check": "writes of any kind to an operations root (checkpoint repair, resume "
                      "flags, published manifests)",
             "reason": "gate original_paths_released is closed; the only operations root "
                       "touched was the candidate's own synthetic fixture directory, read once "
                       "and never modified"},
        ],
        "verdict": "b07_rehearsal_valid_private_only" if not findings else "b07_rehearsal_not_valid",
        "note": ("private candidate only; not merged, not deployed; the original tree was "
                 "neither read, imported nor written; the active-owner seam, the operations "
                 "view and the staged frontend were rehearsed against labelled synthetic "
                 "fixtures only; frozen evidence under evidence/B00/** ... evidence/B06/**, "
                 "evidence/R0104/** and the phase-b, b02, b03, b04, b05 and b06 runtime "
                 "directories was not touched"),
    }
    (EVIDENCE / "B07_LAYOUT_VALIDATION.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (EVIDENCE / "b07_validation_run.txt").write_text(
        "\n".join(transcript) + "\n", encoding="utf-8")
    for index, result in enumerate(results, start=1):
        (EVIDENCE / f"probe_cwd{index}.json").write_text(
            json.dumps({"cwd": result["cwd"], "exit_code": result["exit_code"],
                        "report": result["report"], "stderr": result["stderr"],
                        "env_operations_root": result["env_operations_root"],
                        "env_api_key_synthetic": result["env_api_key_synthetic"]},
                       ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps({"evidence": str(EVIDENCE), "verdict": summary["verdict"],
                      "findings": [f["id"] for f in findings],
                      "runs": summary["runs"],
                      "discovery_identical_across_cwds": identical,
                      "stability_identical_across_cwds": stability_identical,
                      "seam_identical_across_cwds": seam_identical,
                      "operations_identical_across_cwds": operations_identical,
                      "frontend_identical_across_cwds": frontend_identical,
                      "discovery_projection_identical_across_cwds": projection_identical,
                      "cross_stack_identical_across_cwds": cross_identical,
                      "b07_vs_b06_ledger_consistent": ledgers_consistent,
                      "candidate_tree_digest_reproducible":
                          summary["candidate_tree_digest_reproducible"]["sha256_match"]},
                     ensure_ascii=True, indent=2))
    return 0 if not findings else 1


if __name__ == "__main__":
    raise SystemExit(main())
