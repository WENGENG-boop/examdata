import hashlib
import json
from pathlib import Path

RUN = Path(r"C:/Users/weo/Desktop/api/integration-staging/runtime/integration-closure-20261007-c8b4e0c8")
PARENT = Path(r"C:/Users/weo/Desktop/api/integration-staging/runtime/b07-reviewfix-20261007-774e4dad/candidates/b07-operations-v2")

def h(p: Path) -> str:
    d = hashlib.sha256()
    with p.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            d.update(chunk)
    return d.hexdigest()

input_hashes = {
    str(PARENT / "src/examdata/integration/operations/jobs.py"): h(PARENT / "src/examdata/integration/operations/jobs.py"),
    str(PARENT / "src/examdata/integration/api/dataset.py"): h(PARENT / "src/examdata/integration/api/dataset.py"),
    str(PARENT / "src/examdata/integration/api/app.py"): h(PARENT / "src/examdata/integration/api/app.py"),
    "tests/b07r2_common.py": h(RUN / "tests/b07r2_common.py"),
    "tests/test_b07r2_sanitize_keys.py": h(RUN / "tests/test_b07r2_sanitize_keys.py"),
}

output_rel = [
    "candidates/closure-v1/src/examdata/integration/operations/jobs.py",
    "candidates/closure-v1/src/examdata/integration/api/dataset.py",
    "candidates/closure-v1/src/examdata/integration/api/app.py",
    "tests/test_w3_sanitize_freshness.py",
    "tools/w3_reproduce.py",
    "tools/w3_pin_recheck.py",
    "evidence/w3/red_parent_w3_reproduce_20261007T102842Z.json",
    "evidence/w3/red_parent_w3_reproduce_20261007T102842Z.log",
    "evidence/w3/red_parent_tests_20261007T104539Z.txt",
    "evidence/w3/green_candidate_tests_20261007T104725Z.txt",
    "evidence/w3/full_suite_candidate_20261007T104725Z.txt",
    "evidence/w3/green_candidate_w3_reproduce_20261007T104034Z.json",
    "evidence/w3/green_candidate_w3_reproduce_20261007T104034Z.log",
    "evidence/w3/pin_recheck_candidate_20261007T110544Z.json",
    "evidence/w3/pin_recheck_candidate_20261007T110544Z.log",
    "evidence/w3/COMMANDS.md",
    "reports/W3_SANITIZATION_FRESHNESS_DECISION.md",
]
missing = [r for r in output_rel if not (RUN / r).exists()]
assert not missing, missing
output_hashes = {r: h(RUN / r) for r in output_rel}

action = (
    "Implement W3 (C05 + C06) on the candidate closure-v1. "
    "(C05) One-shot secret iterables: new operations/jobs.py materialize_secrets(secrets) "
    "(None -> (), a tuple returned unchanged, any other iterable fixed with tuple()) applied exactly "
    "once at each public projection boundary and reused for every sanitize call inside it — sanitize_tree, "
    "JobView.to_public, JobView.brief, JobsView.briefs, plus the api/app.py route boundaries (coverage "
    "route materializes at its boundary; the job-detail route materializes once and reuses one tuple for "
    "the job row, the superseded rows and the conflicts block) — so a tuple and a one-shot generator over "
    "the same secrets produce byte-identical, marker-free output; keys and values, lists, nested mappings, "
    "Unicode/path-shaped and overlapping secrets, the configured text limit and deterministic #2/#3 "
    "collision suffixes without record loss are unchanged, fixed schema keys are preserved, and public "
    "errors carry no internal exception text or absolute paths. "
    "(C06) New bounded TTL observation service in api/dataset.py: OperationsObservationService(root, "
    "entries=, ttl_seconds=DEFAULT_OPERATIONS_TTL_SECONDS=30.0, clock=, budget=, dataset_revision=) with "
    "all state under one lock; observe() serves the cached view while age <= ttl (honest recomputed "
    "age_seconds) and re-scans past it; every successful refresh stamps a fresh observation_revision "
    "obs-%06d (distinct from the dataset revision), observed_at, age_seconds=0.0, ttl_seconds and clears "
    "observation problems; a failed refresh never raises — before the first good view an unknown "
    "placeholder (staleness=unknown, observation_unavailable), after one the last good view served as "
    "stale with observation_refresh_failed and no _seen_at update (immediate retry on the next call); "
    "staleness is current only when every observed checkpoint's native updated_at parses, else unknown, "
    "never current; a configured-but-missing root keeps root_kind=missing + operations_root_missing with "
    "constant staleness=current; the block lives inside checkpoints['observation'] (observation_revision, "
    "observed_at, age_seconds, staleness, ttl_seconds, problems) so the frozen F4 top-level key set and "
    "the per-job freshness vocabulary are unchanged; default_dataset(operations_ttl=, operations_clock=) "
    "wires the service and app.py::_operations_now observes per request (falling back to the "
    "construction-time view when a dataset carries no service). No write surface anywhere "
    "(never enqueue/resume/cancel/fetch/write; no public name with resume/write/start/cancel/enqueue/"
    "delete/remove prefixes). New tests tests/test_w3_sanitize_freshness.py (20 tests: 9 C05 + 11 C06) "
    "asserting the public projection and HTTP output; new tools tools/w3_reproduce.py and "
    "tools/w3_pin_recheck.py; evidence batch stamps 20261007T102842Z..20261007T110544Z under "
    "evidence/w3/; reports/W3_SANITIZATION_FRESHNESS_DECISION.md documents the semantics and residual "
    "limits."
)

notes = (
    "Batch stamps 20261007T102842Z (parent reproduce), 20261007T104034Z (candidate reproduce), "
    "20261007T104539Z (RED tests), 20261007T104725Z (GREEN tests + FULL suite), 20261007T110544Z (pin "
    "re-check); all interpreter calls with -B and PYTHONDONTWRITEBYTECODE=1, EXAMDATA_INTEGRATION_STAGING_ROOT "
    "unset, all --basetemp dirs under <run>/tmp/ (w3-ev-red-/green-/full-, w3-reproduce/), no evidence file "
    "overwritten, nothing written outside <run>/** and the frozen trees touched read-only. "
    "RED (test_w3_sanitize_freshness.py vs the frozen parent) = 20 failed, 1 warning in 1.29s, exit 1 "
    "(expected RED); all 20 failures are the parent's C05/C06 defects: 9x C05 (generator-vs-tuple divergence "
    "incl. both HTTP routes leaking the marker and the briefs escaping the exhausted generator, plus "
    "materialize_secrets is not implemented), 11x C06 (8x the helper guard OperationsObservationService is "
    "not implemented, 1x KeyError 'observation', 1x default_dataset does not accept a 'operations_ttl' "
    "keyword, 1x OperationsDataset has no attribute staleness). "
    "GREEN (same tests vs candidate) = 20 passed, 1 warning in 1.37s, exit 0. "
    "FULL (candidate, inherited + W1 + W2 + W3) = 124 passed, 1 skipped, 1 warning in 2.25s, exit 0; "
    "124 = 104 baseline (28 inherited + 41 W1 + 35 W2) + 20 W3; the skip is the pre-existing W2 "
    "native-symlink case (WinError 1314, blocked, never counted as passed; the OS-locale error text in the "
    "skip line is GBK-encoded — the same known artifact class as W2's suite logs); the warning is the "
    "pre-existing fastapi/starlette httpx deprecation. "
    "tools/w3_reproduce.py reproductions: C05 parent generator_marker_count=7 vs tuple_marker_count=0, "
    "outputs_identical=false -> reproduced=true, candidate 0/0, byte-identical -> reproduced=false; C06 "
    "parent api=absent -> reproduced=true, candidate api=present with 17/17 checks true (obs-000001 first, "
    "obs-000001 cached within TTL, obs-000002 refreshed past TTL, fourth read stale) -> reproduced=false. "
    "Import provenance read-back: import-ok / ttl= 30.0 / svc= OperationsObservationService / "
    "materialize= materialize_secrets / app-ok True (no file retained). "
    "tools/w3_pin_recheck.py (new, read-only): all 11 section-J pin checks true, ok=true, exit 0 — 7 briefs "
    "exact with the 6 pinned (public_id, freshness) -> stage mappings, checkpoints public conflicts == [], "
    "missing root => root_kind == missing with problems exactly [operations_root_missing], no write-surface "
    "public names in operations/jobs.py or operations/published.py, and the candidate tree digest identical "
    "before and after the view build (8702c3faa6f4007e842b726958216fd14db28fc4390e8cfbbf0dcc0caa5242b8). "
    "The frozen tools/b07_route_probe.py and tools/b07_smoke_import.py cannot execute from this run's tree "
    "(their baselines are relative to the frozen b06 rehearsal root, absent here, and the smoke tool "
    "hardcodes a candidates/b07-operations-v2 path this run does not have), so w3_pin_recheck re-validated "
    "the same pins for W3 and W7 performs the comprehensive frozen-probe re-check. "
    "No inherited test or frozen artifact was edited; the frozen F4 top-level key set is unchanged (asserted "
    "by test_c06_public_projection_key_sets_are_frozen); no check was deleted, no xfail added, no exception "
    "swallowed, no exit code manufactured."
)

entry = {
    "task_id": "W3-sanitize-freshness",
    "action": action,
    "dependencies": ["W2-bounded-operations-io"],
    "status": "pass",
    "input_hashes": input_hashes,
    "output_hashes": output_hashes,
    "command": (
        "cd tests && env -u EXAMDATA_INTEGRATION_STAGING_ROOT "
        "PYTHONPATH=<run>/candidates/closure-v1/src PYTHONDONTWRITEBYTECODE=1 "
        "B07R2_EXPECT_CANDIDATE_ROOT=<run>/candidates/closure-v1 <python> -B -m pytest -c pytest.ini . "
        "-p no:cacheprovider --basetemp <run>/tmp/w3-ev-full-20261007T104725Z -q -rs"
    ),
    "cwd": "integration-staging/runtime/integration-closure-20261007-c8b4e0c8/tests",
    "exit_code": 0,
    "evidence_class": "private_synthetic",
    "evidence_paths": [
        "evidence/w3/red_parent_tests_20261007T104539Z.txt",
        "evidence/w3/green_candidate_tests_20261007T104725Z.txt",
        "evidence/w3/full_suite_candidate_20261007T104725Z.txt",
        "evidence/w3/red_parent_w3_reproduce_20261007T102842Z.json",
        "evidence/w3/green_candidate_w3_reproduce_20261007T104034Z.json",
        "evidence/w3/pin_recheck_candidate_20261007T110544Z.json",
        "evidence/w3/COMMANDS.md",
        "reports/W3_SANITIZATION_FRESHNESS_DECISION.md",
        "tests/test_w3_sanitize_freshness.py",
        "tools/w3_reproduce.py",
        "tools/w3_pin_recheck.py",
    ],
    "required_authorization": "none",
    "blockers": [],
    "notes": notes,
}

out = RUN / "tmp/ledger/w3_entry.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(entry, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print(f"wrote {out} ({len(input_hashes)} input, {len(output_hashes)} output hashes)")
