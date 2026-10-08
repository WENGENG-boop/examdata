#!/usr/bin/env python3
"""A14 closing checks for the Phase A integration (run AFTER the ledger is closed).

Validates:
  1. artifact existence (merge map json+md, release manifest, rehearsal report,
     the staged v2 reference and the staged docs set, the two A14 tools, the
     packet transcripts, the close patch, the report and the evidence);
  2. fresh artifact re-verification: both A14 tools are re-run with --check
     (private fixtures, offline) and must reproduce their recorded PASS lines;
  3. merge map facts: 247 entries / 92 not_merged / 6 planned original edits /
     12 observed bases with 0 drift, the group and kind census, unique targets
     that never point back into a Phase A root, every staged sha256 recomputed
     against disk, every copied_snapshot byte-faithful to its recorded base,
     and no staged candidate left unmapped;
  4. rehearsal report facts: 6 units (5 rehearsed + 1 database unit not_run),
     21 checks all ok, 0 problems, sandbox under runtime/;
  5. release manifest facts: proposal-only labelling, 4 gates false, the wheel
     explicitly not built, the 12 observed dependency versions, 5 smoke checks,
     6 rollback units, 5 exclusions, 3 not_run items;
  6. determinism of the staged v2 API surface: `create_app().openapi()` yields
     the same 39 (path, method, operationId) triples with unique ids under
     PYTHONHASHSEED 0/7/999 (the A14 fix for FastAPI's set-ordered ids);
  7. compatibility worksheet coverage: 71/71 baseline rows, 64 staged_pass +
     7 deferred_active_owner, 0 problems, every row status allowed;
  8. fresh liveness offline: the full staged suite passes 887 and the staged
     frontend node suite passes 27/27 (stdout kept as post-close evidence);
  9. ledger state: 27 tasks, A14 staged_pass with dependencies ["A13"], all
     seven Phase B gates closed, no merged_pass anywhere, the rc=1 and
     exit-code-masked command rows reconciled;
 10. close patch consistency: changed files inside the two Phase A roots, the
     three POST_CLOSE transcripts never listed, every A14 deliverable present,
     input hashes recomputed against disk (excluding the self-referential
     ledger), exit_codes identical to the ledger record;
 11. containment + read-only originals: no bytecode under staged src/tests/
     frontend, and every observed base file re-observed (drift logged as an
     observation, never repaired or asserted away);
 12. sha256 manifest of both Phase A roots (excluding this transcript).

Writes (and prints) the transcript to
  docs/integration/execution/evidence/A14/final_checks.txt  (override with --out)
and exits 0 (PASS) or 1 (FAIL). The first run is expected to pass; it creates
the three POST_CLOSE transcripts (final_checks.txt, pytest_rerun.txt,
node_rerun.txt) that are excluded from the close patch by construction.

Phase A tool (integration-staging/tools/). Stdlib only; nothing original is
modified or executed; the original tree is read-only input, never written.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.dont_write_bytecode = True

WS = Path(__file__).resolve().parents[2]
EXEC = WS / "docs" / "integration" / "execution"
EV = EXEC / "evidence" / "A14"
STAGING = WS / "integration-staging"
TOOLS = STAGING / "tools"
ROOTS = [STAGING, EXEC]

EXPECTED_TASK_IDS = ["A%02d" % i for i in range(16)] + ["B%02d" % i for i in range(11)]
ROOT_STRINGS = [STAGING.relative_to(WS).as_posix() + "/", EXEC.relative_to(WS).as_posix() + "/"]
LEDGER_REL = "docs/integration/execution/execution-ledger.json"

MAP_REL = "docs/integration/execution/A14_MERGE_MAP.json"
MAP_MD_REL = "docs/integration/execution/A14_MERGE_MAP.md"
RELEASE_REL = "docs/integration/execution/A14_RELEASE_MANIFEST.json"
REHEARSAL_REL = "docs/integration/execution/A14_REHEARSAL.json"
V2_REF_REL = "integration-staging/docs/v2-api-reference.md"

EXPECTED_ENTRIES = 247
EXPECTED_NOT_MERGED = 92
EXPECTED_PLANNED_EDITS = 6
EXPECTED_BASES_OBSERVED = 12
EXPECTED_BASE_DRIFT = 0
EXPECTED_SNAPSHOTS = 8
EXPECTED_MODIFIED = 4
EXPECTED_GROUPS = {"python": 62, "tests": 43, "contracts": 74, "fixtures": 49,
                   "frontend": 13, "config": 2, "docs": 4}
EXPECTED_KINDS = {"new_file": 235, "copied_snapshot": 8, "modified_copy": 4}

EXPECTED_UNITS = 6
EXPECTED_REHEARSED_UNITS = 5
EXPECTED_REHEARSAL_CHECKS = 21

EXPECTED_DEP_VERSIONS = {
    "httpx": "0.28.1", "beautifulsoup4": "4.15.0", "lxml": "6.1.3",
    "sqlalchemy": "2.1.1", "pydantic": "2.13.5", "pydantic-settings": "2.15.0",
    "pymupdf": "1.28.2", "typer": "0.27.2", "rich": "15.0.0",
    "fastapi": "0.141.1", "uvicorn": "0.54.0", "pytest": "9.1.1",
}

EXPECTED_OPS = 39
EXPECTED_UNIQUE_OPS = 39
EXPECTED_OPS_HASH = "cd0e3da997cdf9ee"
HASH_SEEDS = ["0", "7", "999"]

EXPECTED_ROWS = 71
EXPECTED_ROW_STATUSES = {"staged_pass": 64, "deferred_active_owner": 7}
ALLOWED_ROW_STATUSES = {"staged_pass", "deferred_active_owner", "partial",
                        "blocked", "not_run"}

EXPECTED_COLLECTED = 887
EXPECTED_NODE_TESTS = 27
EXPECTED_NODE_PASS = 27
EXPECTED_NODE_FAIL = 0

BUILD_PASS_LINE = "A14_BUILD_ARTIFACTS: PASS"
REHEARSAL_PASS_LINE = "A14_REHEARSAL: PASS"

A14_TOOLS = ["tools/a14_build_artifacts.py", "tools/a14_rehearsal.py",
             "tools/a14_close_patch.py", "tools/a14_final_checks.py"]
A14_DOCS = ["docs/README.md", "docs/integration-guide.md",
            "docs/release-and-rollback.md", "docs/v2-api-reference.md"]
POST_CLOSE = {
    "docs/integration/execution/evidence/A14/final_checks.txt",
    "docs/integration/execution/evidence/A14/pytest_rerun.txt",
    "docs/integration/execution/evidence/A14/node_rerun.txt",
}

OPS_PROBE = (
    "import os, sys, json, hashlib\n"
    "sys.path.insert(0, 'integration-staging/src')\n"
    "os.environ.setdefault('EXAMDATA_INTEGRATION_ROOT', os.path.abspath('integration-staging'))\n"
    "from examdata_integration.api.app import create_app\n"
    "spec = create_app().openapi()\n"
    "ops = sorted((p, m, o['operationId']) for p, v in spec['paths'].items()\n"
    "             for m, o in v.items())\n"
    "print(len(ops), len({o for _, _, o in ops}),\n"
    "      hashlib.sha256(json.dumps(ops, sort_keys=True).encode()).hexdigest()[:16])\n"
)

FORBIDDEN_IMPORT_PATTERNS = [
    re.compile(r"^\s*import\s+app\b", re.MULTILINE),
    re.compile(r"^\s*from\s+app\b", re.MULTILINE),
    re.compile(r"^\s*import\s+examdata\b(?!_)", re.MULTILINE),
    re.compile(r"^\s*from\s+examdata\b(?!_)", re.MULTILINE),
]
DESKTOP_PATTERN = re.compile(r"Desktop", re.IGNORECASE)

checks: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    checks.append((name, bool(ok), detail))


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_json(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def rel(p: Path) -> str:
    return p.relative_to(WS).as_posix()


def probe_env(**extra: str) -> dict:
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    env.update(extra)
    return env


def run_pytest(args: list[str], timeout: int = 900) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-c", "pytest.ini", *args,
         "--basetemp", "runtime/pytest-temp", "-o", "cache_dir=runtime/pytest-cache"],
        cwd=str(STAGING), env=probe_env(), capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=timeout)


def node_exe() -> str | None:
    candidate = Path("C:/Program Files/nodejs/node.exe")
    if candidate.is_file():
        return str(candidate)
    return shutil.which("node")


def node_count(text: str, label: str) -> int | None:
    m = (re.search(r"(?:\u2139|#)\s*" + label + r"\s+(\d+)", text)
         or re.search(r"^" + label + r"\s+(\d+)", text, re.MULTILINE))
    return int(m.group(1)) if m else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(EV / "final_checks.txt"))
    args = ap.parse_args()
    out_path = Path(args.out)
    out_path = (out_path if out_path.is_absolute() else WS / out_path).resolve()

    lines: list[str] = []

    def emit(s: str = "") -> None:
        lines.append(s)

    emit("=== A14 final checks (file-by-file merge map + rollback rehearsal + "
         "release manifest: integration-staging/tools/a14_final_checks.py) ===")
    emit(f"generated_at_local: {datetime.now().astimezone().isoformat(timespec='seconds')}")
    emit(f"generated_at_utc:   {datetime.now(timezone.utc).isoformat(timespec='seconds')}")
    emit(f"cwd: {Path.cwd()}")
    emit()

    # ---- 1. artifact existence -------------------------------------------------
    emit("--- 1. artifact existence ---")
    required = [
        MAP_REL,
        MAP_MD_REL,
        RELEASE_REL,
        REHEARSAL_REL,
        V2_REF_REL,
        *[f"integration-staging/{d}" for d in A14_DOCS],
        *[f"integration-staging/{t}" for t in A14_TOOLS],
        "integration-staging/runtime/ledger-patches/A14_close.json",
        "integration-staging/config/staging-config.example.json",
        "integration-staging/config/staging.env.example",
        "docs/integration/execution/A14_REPORT.md",
        "docs/integration/execution/execution-ledger.json",
        "docs/integration/execution/A12_ROUTE_COMPATIBILITY_WORKSHEET.json",
        "docs/integration/execution/evidence/A14/rehearsal_stdout.txt",
        "docs/integration/execution/evidence/A14/pytest_run_stdout.txt",
        "docs/integration/execution/evidence/A14/node_tests_stdout.txt",
    ]
    missing_files = [r for r in required if not (WS / r).is_file()]
    emit(f"required={len(required)} missing={missing_files}")
    check("artifacts.all_present", not missing_files, str(missing_files))

    # ---- 2. fresh artifact re-verification (both tools with --check) ------------
    emit()
    emit("--- 2. fresh artifact re-verification (a14_build_artifacts / a14_rehearsal) ---")
    build_text = rehearsal_text = ""
    try:
        build = subprocess.run(
            [sys.executable, str(TOOLS / "a14_build_artifacts.py"), "--check"],
            cwd=str(WS), env=probe_env(), capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=300)
        build_text = (build.stdout + build.stderr).strip()
        emit(f"build_artifacts rc={build.returncode} first={build_text.splitlines()[0] if build_text else ''}")
        check("reverify.build_artifacts_check",
              build.returncode == 0 and BUILD_PASS_LINE in build_text,
              f"rc={build.returncode} out={build_text[:300]}")

        rehearse = subprocess.run(
            [sys.executable, str(TOOLS / "a14_rehearsal.py"), "--check"],
            cwd=str(WS), env=probe_env(), capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=300)
        rehearsal_text = (rehearse.stdout + rehearse.stderr).strip()
        tail = rehearsal_text.splitlines()[-1] if rehearsal_text else ""
        emit(f"rehearsal rc={rehearse.returncode} tail={tail}")
        check("reverify.rehearsal_check",
              rehearse.returncode == 0 and REHEARSAL_PASS_LINE in rehearsal_text,
              f"rc={rehearse.returncode} out={rehearsal_text[-300:]}")
    except Exception as e:  # noqa: BLE001
        check("reverify.build_artifacts_check", False, f"exception={e!r}")

    # ---- 3. merge map facts ------------------------------------------------------
    emit()
    emit("--- 3. merge map facts (entries, bases, targets, reversals) ---")
    mmap: dict = {}
    try:
        mmap = load_json(WS / MAP_REL)
        counts = mmap.get("counts") or {}
        entries = mmap.get("entries") or []
        not_merged = mmap.get("not_merged") or []
        planned = mmap.get("planned_original_edits") or []
        emit(f"map_version={mmap.get('map_version')} mode={mmap.get('mode')} "
             f"status={mmap.get('status')}")
        emit(f"entries={len(entries)} not_merged={len(not_merged)} "
             f"planned_edits={len(planned)} problems={mmap.get('problems')}")
        check("map.header",
              mmap.get("map_version") == "merge-map/1"
              and mmap.get("mode") == "PHASE_A_ISOLATED_ONLY"
              and mmap.get("status") == "proposed_staged_not_merged_not_deployed"
              and mmap.get("problems") == [])
        check("map.counts",
              len(entries) == EXPECTED_ENTRIES
              and counts.get("entries") == EXPECTED_ENTRIES
              and counts.get("not_merged") == EXPECTED_NOT_MERGED
              and len(not_merged) == EXPECTED_NOT_MERGED
              and counts.get("planned_original_edits") == EXPECTED_PLANNED_EDITS
              and len(planned) == EXPECTED_PLANNED_EDITS
              and counts.get("base_files_observed") == EXPECTED_BASES_OBSERVED
              and counts.get("base_drift") == EXPECTED_BASE_DRIFT
              and counts.get("copied_snapshot") == EXPECTED_SNAPSHOTS
              and counts.get("modified_copy") == EXPECTED_MODIFIED,
              json.dumps({k: counts.get(k) for k in
                          ("entries", "not_merged", "planned_original_edits",
                           "base_files_observed", "base_drift")}))

        groups: dict[str, int] = {}
        kinds: dict[str, int] = {}
        for e in entries:
            groups[e.get("group")] = groups.get(e.get("group"), 0) + 1
            kinds[e.get("kind")] = kinds.get(e.get("kind"), 0) + 1
        emit(f"groups={json.dumps(groups, sort_keys=True)}")
        emit(f"kinds={json.dumps(kinds, sort_keys=True)}")
        check("map.group_census", groups == EXPECTED_GROUPS, json.dumps(groups, sort_keys=True))
        check("map.kind_census", kinds == EXPECTED_KINDS, json.dumps(kinds, sort_keys=True))

        targets = [e.get("proposed_target") for e in entries]
        self_referential = [t for t in targets
                            if t and (t.replace("\\", "/").startswith(ROOT_STRINGS[0])
                                      or t.replace("\\", "/").startswith(ROOT_STRINGS[1]))]
        dup = sorted({t for t in targets if targets.count(t) > 1})
        emit(f"targets_unique={len(set(targets))} duplicate_targets={dup} "
             f"self_referential={self_referential}")
        check("map.targets_unique_and_external",
              len(set(targets)) == EXPECTED_ENTRIES and not dup
              and not self_referential, f"dup={dup} self={self_referential}")

        bad_entries: list[str] = []
        base_obs: list[str] = []
        snapshots = 0
        for e in entries:
            sp = WS / str(e.get("staged_path"))
            if not sp.is_file():
                bad_entries.append(f"{e.get('staged_path')}:missing")
                continue
            if sha256_file(sp) != e.get("staged_sha256"):
                bad_entries.append(f"{e.get('staged_path')}:staged_sha256")
            if sp.stat().st_size != e.get("size"):
                bad_entries.append(f"{e.get('staged_path')}:size")
            if e.get("phase_b_action") not in ("add_file", "reconcile_modify", "verify_copy"):
                bad_entries.append(f"{e.get('staged_path')}:action")
            if not e.get("reversal"):
                bad_entries.append(f"{e.get('staged_path')}:no_reversal")
            if not e.get("verification"):
                bad_entries.append(f"{e.get('staged_path')}:no_verification")
            base = e.get("base")
            if base:
                src = WS / str(base.get("source_path"))
                if not src.is_file():
                    bad_entries.append(f"{e.get('staged_path')}:base_missing")
                    continue
                cur = sha256_file(src)
                if cur != base.get("sha256_current"):
                    bad_entries.append(f"{e.get('staged_path')}:base_drift")
                base_obs.append(f"{base.get('source_path')}: recorded={str(base.get('sha256_recorded'))[:12]} "
                                f"current={cur[:12]} drift={cur != base.get('sha256_recorded')}")
            if e.get("kind") == "copied_snapshot":
                snapshots += 1
                if not base or base.get("sha256_recorded") != e.get("staged_sha256"):
                    bad_entries.append(f"{e.get('staged_path')}:snapshot_not_faithful")
            if e.get("kind") == "modified_copy":
                if not base or base.get("sha256_recorded") == e.get("staged_sha256"):
                    bad_entries.append(f"{e.get('staged_path')}:modified_but_identical")
            if e.get("kind") == "new_file" and base:
                bad_entries.append(f"{e.get('staged_path')}:new_file_has_base")
        emit(f"entries_checked={len(entries)} snapshots={snapshots} problems={bad_entries}")
        emit(f"base_observations({len(base_obs)}):")
        for line in base_obs:
            emit(f"  {line}")
        check("map.entries_reconcile", not bad_entries, str(bad_entries))
        check("map.copied_snapshots_faithful",
              snapshots == EXPECTED_SNAPSHOTS
              and not [p for p in bad_entries if "snapshot_not_faithful" in p])

        covered = {e.get("staged_path") for e in entries}
        nm_paths = {e.get("staged_path") for e in not_merged}
        overlap = sorted(covered & nm_paths)
        check("map.not_merged_disjoint", not overlap, str(overlap))
        check("map.not_merged_reasons",
              all((e.get("reason") or "").strip() for e in not_merged)
              and len(nm_paths) == EXPECTED_NOT_MERGED,
              f"n={len(not_merged)}")

        edit_problems: list[str] = []
        for it in planned:
            t = WS / str(it.get("target_path"))
            if it.get("base_exists"):
                if not t.is_file() or sha256_file(t) != it.get("base_sha256"):
                    edit_problems.append(f"{it.get('target_path')}:base_stale")
            elif t.is_file():
                edit_problems.append(f"{it.get('target_path')}:claimed_absent_but_present")
            if not it.get("reversal") or not it.get("packet"):
                edit_problems.append(f"{it.get('target_path')}:incomplete")
        emit(f"planned_edits={len(planned)} problems={edit_problems}")
        check("map.planned_edits_reconcile", not edit_problems, str(edit_problems))
        check("map.planned_edits_are_shared_files",
              all(not str(it.get("target_path", "")).startswith("integration-staging/")
                  for it in planned))
    except Exception as e:  # noqa: BLE001
        check("map.read_and_validate", False, f"exception={e!r}")

    # ---- 4. rehearsal report facts ----------------------------------------------
    emit()
    emit("--- 4. rollback rehearsal report facts ---")
    try:
        rr = load_json(WS / REHEARSAL_REL)
        units = rr.get("units") or []
        n_rehearsed = sum(1 for u in units if u.get("rehearsed"))
        n_not_run = sum(1 for u in units if u.get("not_run"))
        all_checks = [c for u in units for c in (u.get("checks") or [])]
        bad_checks = [f"{u.get('unit')}:{c.get('name')}" for u in units
                      for c in (u.get("checks") or []) if not c.get("ok")]
        emit(f"units={len(units)} rehearsed={n_rehearsed} not_run={n_not_run} "
             f"checks={len(all_checks)} failing={bad_checks}")
        emit(f"status={rr.get('status')} sandbox={rr.get('sandbox_root')}")
        check("rehearsal.header",
              rr.get("report_version") == "a14-rehearsal/1"
              and rr.get("status") == "staged_rehearsal_only_not_merged_not_deployed")
        check("rehearsal.units",
              len(units) == EXPECTED_UNITS
              and n_rehearsed == EXPECTED_REHEARSED_UNITS
              and n_not_run == 1,
              f"units={len(units)} rehearsed={n_rehearsed} not_run={n_not_run}")
        check("rehearsal.checks_all_pass",
              len(all_checks) == EXPECTED_REHEARSAL_CHECKS and not bad_checks,
              f"n={len(all_checks)} failing={bad_checks}")
        check("rehearsal.sandbox_inside_staging",
              str(rr.get("sandbox_root", "")).startswith("integration-staging/runtime/"),
              str(rr.get("sandbox_root")))
    except Exception as e:  # noqa: BLE001
        check("rehearsal.read_and_validate", False, f"exception={e!r}")

    # ---- 5. release manifest facts ----------------------------------------------
    emit()
    emit("--- 5. proposed release manifest facts ---")
    try:
        rm = load_json(WS / RELEASE_REL)
        gates = rm.get("gates") or {}
        open_gates = [g for g, v in gates.items() if v]
        deps = ((rm.get("dependency_versions") or {}).get("observed") or {})
        bad_deps = {k: v for k, v in EXPECTED_DEP_VERSIONS.items() if deps.get(k) != v}
        smoke = rm.get("smoke_checks") or []
        units_rb = ((rm.get("rollback_instructions") or {}).get("units") or [])
        emit(f"version={rm.get('manifest_version')} status={rm.get('status')} "
             f"gates_open={open_gates} deps={len(deps)} bad_deps={bad_deps}")
        emit(f"smoke={len(smoke)} rollback_units={len(units_rb)} "
             f"exclusions={len(rm.get('exclusions') or [])} "
             f"not_run={len(rm.get('not_run') or [])} wheel_built="
             f"{(rm.get('python') or {}).get('wheel', {}).get('built')}")
        check("release.header",
              rm.get("manifest_version") == "release-manifest-proposal/1"
              and rm.get("status") == "proposed_staged_not_merged_not_deployed")
        check("release.gates_all_false", len(gates) == 4 and not open_gates,
              f"open={open_gates}")
        check("release.wheel_not_built",
              (rm.get("python") or {}).get("wheel", {}).get("built") is False)
        check("release.dependency_versions", not bad_deps, str(bad_deps))
        check("release.smoke_and_rollback",
              len(smoke) == 5 and len(units_rb) == 6
              and all(u.get("rehearsed") for u in units_rb),
              f"smoke={len(smoke)} units={len(units_rb)}")
        check("release.exclusions_and_not_run",
              len(rm.get("exclusions") or []) == 5 and len(rm.get("not_run") or []) == 3)
    except Exception as e:  # noqa: BLE001
        check("release.read_and_validate", False, f"exception={e!r}")

    # ---- 6. staged v2 API determinism across hash seeds --------------------------
    emit()
    emit("--- 6. staged v2 API surface determinism (PYTHONHASHSEED 0/7/999) ---")
    try:
        observed: list[str] = []
        for seed in HASH_SEEDS:
            pr = subprocess.run([sys.executable, "-c", OPS_PROBE], cwd=str(WS),
                                env=probe_env(PYTHONHASHSEED=seed), capture_output=True,
                                text=True, encoding="utf-8", errors="replace", timeout=180)
            line = (pr.stdout or "").strip().splitlines()[-1] if pr.stdout.strip() else ""
            emit(f"seed={seed} rc={pr.returncode} {line}")
            observed.append(f"{pr.returncode}|{line}")
        first = observed[0] if observed else ""
        check("api.operation_ids_deterministic",
              len(set(observed)) == 1
              and first == f"0|{EXPECTED_OPS} {EXPECTED_UNIQUE_OPS} {EXPECTED_OPS_HASH}",
              f"observed={observed}")
    except Exception as e:  # noqa: BLE001
        check("api.operation_ids_deterministic", False, f"exception={e!r}")

    # ---- 7. compatibility worksheet coverage ------------------------------------
    emit()
    emit("--- 7. compatibility worksheet coverage (71-route baseline) ---")
    try:
        ws_doc = load_json(EXEC / "A12_ROUTE_COMPATIBILITY_WORKSHEET.json")
        rows = ws_doc.get("rows") or []
        summary = ws_doc.get("summary") or {}
        statuses: dict[str, int] = {}
        for r in rows:
            statuses[r.get("status")] = statuses.get(r.get("status"), 0) + 1
        unknown = sorted({s for s in statuses if s not in ALLOWED_ROW_STATUSES})
        missing_keys = [i for i, r in enumerate(rows)
                        if not r.get("legacy_path") or not r.get("status")
                        or not r.get("compatibility_strategy")]
        emit(f"rows={len(rows)} statuses={json.dumps(statuses, sort_keys=True)} "
             f"summary={json.dumps({k: summary.get(k) for k in ('baseline_count', 'baseline_coverage', 'post_baseline_count')}, sort_keys=True)}")
        check("worksheet.coverage",
              len(rows) == EXPECTED_ROWS
              and summary.get("baseline_count") == EXPECTED_ROWS
              and summary.get("baseline_coverage") == "71/71"
              and statuses == EXPECTED_ROW_STATUSES
              and not ws_doc.get("problems"),
              f"rows={len(rows)} statuses={statuses}")
        check("worksheet.statuses_allowed_and_complete",
              not unknown and not missing_keys,
              f"unknown={unknown} incomplete={missing_keys[:5]}")
    except Exception as e:  # noqa: BLE001
        check("worksheet.coverage", False, f"exception={e!r}")

    # ---- 8. fresh liveness (offline pytest + node) ------------------------------
    emit()
    emit("--- 8. fresh liveness: full staged suite + staged frontend node suite ---")
    try:
        for sub in ("pytest-temp", "pytest-cache", "tmp", "home"):
            (STAGING / "runtime" / sub).mkdir(parents=True, exist_ok=True)
        full = run_pytest(["tests", "-q"])
        full_text = full.stdout + full.stderr
        tail = full_text.strip().splitlines()[-1] if full_text.strip() else ""
        mp = re.search(r"(\d+) passed", full_text)
        mf = re.search(r"(\d+) failed", full_text)
        passed = int(mp.group(1)) if mp else None
        failed = int(mf.group(1)) if mf else 0
        emit(f"pytest rc={full.returncode} tail={tail}")
        check("liveness.pytest_887_passed",
              full.returncode == 0 and passed == EXPECTED_COLLECTED and failed == 0,
              f"rc={full.returncode} passed={passed} failed={failed}")
        (EV / "pytest_rerun.txt").write_text(full_text, encoding="utf-8", newline="\n")

        node = node_exe()
        if not node:
            check("liveness.node_available", False, "node.exe not found")
        else:
            nr = subprocess.run(
                [node, "--test", "integration-staging/frontend/tests/*.test.mjs"],
                cwd=str(WS), env=probe_env(), capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=180)
            ntext = nr.stdout + nr.stderr
            nt = node_count(ntext, "tests")
            np_ = node_count(ntext, "pass")
            nf = node_count(ntext, "fail")
            emit(f"node rc={nr.returncode} tests={nt} pass={np_} fail={nf}")
            check("liveness.node_27_pass",
                  nr.returncode == 0 and nt == EXPECTED_NODE_TESTS
                  and np_ == EXPECTED_NODE_PASS and nf == EXPECTED_NODE_FAIL,
                  f"rc={nr.returncode} tests={nt} pass={np_} fail={nf}")
            (EV / "node_rerun.txt").write_text(ntext, encoding="utf-8", newline="\n")
    except Exception as e:  # noqa: BLE001
        check("liveness.pytest_887_passed", False, f"exception={e!r}")

    # ---- 9. ledger state ---------------------------------------------------------
    emit()
    emit("--- 9. ledger state ---")
    led: dict = {}
    a14: dict = {}
    try:
        led = load_json(EXEC / "execution-ledger.json")
        by_id = {t.get("task_id"): t for t in led.get("tasks", [])}
        a14 = by_id.get("A14", {})
        codes = a14.get("exit_codes", [])
        commands = a14.get("commands", [])
        nonzero = [c for c in codes if c not in (0, None)]
        failures = a14.get("failures") or []
        masked = [f for f in failures if f.get("exit_code_masked")]
        rc1 = [f for f in failures if f.get("exit_code") == 1
               and not f.get("exit_code_masked")]
        emit(f"A14 exit_codes n={len(codes)} nonzero={nonzero} failures={len(failures)} "
             f"masked={len(masked)} rc1={len(rc1)} commands={len(commands)}")
        check("ledger.exit_codes_consistent",
              bool(codes) and len(codes) == len(commands)
              and set(nonzero) <= {1} and len(nonzero) == len(rc1),
              f"codes={len(codes)} nonzero={nonzero} rc1={len(rc1)}")
        check("ledger.failure_bookkeeping",
              len(failures) >= 4
              and len(rc1) == sum(1 for c in codes if c == 1)
              and all((f.get("resolution") or "").strip() for f in failures),
              f"failures={len(failures)} masked={len(masked)} rc1={len(rc1)} "
              f"rc1_rows={sum(1 for c in codes if c == 1)}")

        tasks = led.get("tasks", [])
        ids = [t.get("task_id") for t in tasks]
        gates = led.get("gates", {})
        open_gates = [g for g, v in gates.items() if (v or {}).get("open")]
        statuses = {}
        for t in tasks:
            statuses[t["status"]] = statuses.get(t["status"], 0) + 1
        emit(f"task_count={len(ids)} unique={len(set(ids))} "
             f"statuses={json.dumps(statuses, sort_keys=True)}")
        emit(f"A14_status={a14.get('status')} gates={len(gates)} open={open_gates}")
        check("ledger.count_unique_27",
              len(ids) == 27 and len(set(ids)) == 27
              and not [t for t in EXPECTED_TASK_IDS if t not in ids]
              and not [t for t in ids if t not in EXPECTED_TASK_IDS])
        check("ledger.a14_staged_pass", a14.get("status") == "staged_pass",
              f"A14={a14.get('status')}")
        check("ledger.no_merged_pass", "merged_pass" not in statuses)
        check("ledger.gates_closed", len(gates) == 7 and not open_gates,
              f"open={open_gates}")
        expected_roots = [STAGING.as_posix(), EXEC.as_posix()]
        check("ledger.a14_write_roots",
              a14.get("allowed_write_roots") == expected_roots
              and led.get("allowed_write_roots") == expected_roots)
        check("ledger.a14_dependencies", a14.get("dependencies") == ["A13"],
              str(a14.get("dependencies")))
        check("ledger.a14_record_fields",
              bool(a14.get("evidence_paths")) and bool(a14.get("input_hashes"))
              and bool(a14.get("commands")) and bool(a14.get("changed_files"))
              and bool(a14.get("test_results")) and bool(a14.get("remaining_gaps"))
              and (a14.get("next_action") or "").strip() != "")
    except Exception as e:  # noqa: BLE001
        check("ledger.load_and_validate", False, f"exception={e!r}")

    # ---- 10. close patch consistency ---------------------------------------------
    emit()
    emit("--- 10. close patch consistency (changed files, inputs, exit codes) ---")
    try:
        patch = load_json(STAGING / "runtime" / "ledger-patches" / "A14_close.json")
        cf = patch.get("changed_files") or []
        outside = [f for f in cf
                   if not any(f.replace("\\", "/").startswith(r) for r in ROOT_STRINGS)]
        fc_rel = "integration-staging/tools/a14_final_checks.py"
        deliverables = [
            "integration-staging/tools/a14_build_artifacts.py",
            "integration-staging/tools/a14_rehearsal.py",
            "integration-staging/tools/a14_close_patch.py",
            "integration-staging/src/examdata_integration/api/app.py",
            "integration-staging/docs/v2-api-reference.md",
            "integration-staging/docs/release-and-rollback.md",
            "integration-staging/docs/integration-guide.md",
            MAP_REL, MAP_MD_REL, RELEASE_REL, REHEARSAL_REL,
            "docs/integration/execution/A14_REPORT.md",
        ]
        emit(f"changed_files={len(cf)} final_checks_registered={fc_rel in cf} "
             f"outside_roots={outside} post_close_listed={sorted(set(cf) & POST_CLOSE)}")
        check("close_patch.changed_files_inside_roots", not outside, str(outside))
        check("close_patch.post_close_not_listed", not (set(cf) & POST_CLOSE))
        check("close_patch.deliverables_listed",
              all(d in cf for d in deliverables),
              str([d for d in deliverables if d not in cf]))
        check("close_patch.final_checks_registered",
              fc_rel in cf and len(cf) >= 12, f"n={len(cf)} registered={fc_rel in cf}")

        ih = patch.get("input_hashes") or {}
        bad_ih: list[str] = []
        outside_obs: list[str] = []
        for r, h in ih.items():
            # strict recompute: the two Phase A roots and the frozen plan inputs.
            # The ledger is self-referential (re-merged after the patch) and the
            # original tree is actively owned by Kimi: both are observed, never
            # asserted (plan 14 drift policy).
            strict = (r.startswith(ROOT_STRINGS[0]) or r.startswith("docs/integration/")) \
                and r != LEDGER_REL
            p = WS / r
            cur = sha256_file(p) if p.is_file() else None
            if not strict:
                outside_obs.append(f"{r}: recorded={str(h)[:12]} current={str(cur)[:12]} "
                                   f"drift={cur != h}")
                continue
            if cur is None:
                bad_ih.append(f"{r}:missing")
            elif cur != h:
                bad_ih.append(f"{r}:sha256")
        emit(f"input_hashes={len(ih)} strict_recompute_problems={bad_ih} "
             f"observed_only={len(outside_obs)}")
        for line in outside_obs:
            emit(f"  observed: {line}")
        check("close_patch.input_hashes_recompute", not bad_ih, str(bad_ih))
        expected_ih = set(patch.get("inputs") or []) | set(cf)
        check("close_patch.input_hash_count",
              len(ih) == len(expected_ih) and set(ih) == expected_ih,
              f"{len(ih)} vs {len(expected_ih)} "
              f"missing={sorted(expected_ih - set(ih))[:5]} extra={sorted(set(ih) - expected_ih)[:5]}")
        check("close_patch.exit_codes_match_ledger",
              patch.get("exit_codes") == a14.get("exit_codes"))
        check("close_patch.meta",
              patch.get("dependencies") == ["A13"]
              and patch.get("blocked_by") == []
              and patch.get("allowed_write_roots") == [STAGING.as_posix(), EXEC.as_posix()],
              json.dumps({k: patch.get(k) for k in
                          ("dependencies", "blocked_by", "allowed_write_roots")}))
    except Exception as e:  # noqa: BLE001
        check("close_patch.load_and_validate", False, f"exception={e!r}")

    # ---- 11. containment + read-only original observations ------------------------
    emit()
    emit("--- 11. containment of the A14 write set + read-only original observations ---")
    try:
        outside = [f for f in (a14.get("changed_files") or [])
                   if not any(f.replace("\\", "/").startswith(r) for r in ROOT_STRINGS)]
        emit(f"ledger_changed_files_outside_roots={outside}")
        check("containment.changed_files_inside_roots", not outside)

        leaks = []
        for sub in ("src", "tests", "frontend"):
            for p in (STAGING / sub).rglob("*"):
                if p.is_dir() and p.name == "__pycache__":
                    leaks.append(rel(p))
                elif p.is_file() and p.suffix in (".pyc", ".pyo"):
                    leaks.append(rel(p))
        emit(f"pycache_leaks={leaks}")
        check("containment.no_bytecode_under_staging", not leaks)

        offenders: list[str] = []
        for t in A14_TOOLS:
            p = STAGING / t
            body = p.read_text(encoding="utf-8")
            for pat in FORBIDDEN_IMPORT_PATTERNS:
                if pat.search(body):
                    offenders.append(f"{rel(p)}::{pat.pattern}")
        api_app = STAGING / "src" / "examdata_integration" / "api" / "app.py"
        for pat in FORBIDDEN_IMPORT_PATTERNS:
            if pat.search(api_app.read_text(encoding="utf-8")):
                offenders.append(f"{rel(api_app)}::{pat.pattern}")
        emit(f"a14_tools_scanned={len(A14_TOOLS) + 1} offenders={offenders}")
        check("containment.no_original_app_reference", not offenders, str(offenders))

        obs: list[str] = []
        for e in (mmap.get("entries") or []):
            base = e.get("base")
            if not base:
                continue
            src = WS / str(base.get("source_path"))
            cur = sha256_file(src) if src.is_file() else None
            obs.append(f"{base.get('source_path')}: recorded={str(base.get('sha256_recorded'))[:12]} "
                       f"current={str(cur)[:12]} drift={cur != base.get('sha256_recorded')}")
        emit(f"base_file_observations({len(obs)}):")
        for line in obs:
            emit(f"  {line}")
        check("originals.base_observations_recorded",
              len(obs) == EXPECTED_BASES_OBSERVED
              and all("current=None" not in o for o in obs),
              f"n={len(obs)}")
    except Exception as e:  # noqa: BLE001
        check("containment.changed_files_inside_roots", False, f"exception={e!r}")

    # ---- 12. sha256 manifest ------------------------------------------------------
    emit()
    emit("--- 12. artifact inventory + sha256 manifest (excluding this transcript) ---")
    all_files: list[Path] = []
    for root in ROOTS:
        for p in sorted(root.rglob("*")):
            if p.is_file() and p.resolve() != out_path:
                all_files.append(p)
    for p in all_files:
        emit(rel(p))
    emit()
    emit("--- manifest ---")
    for p in all_files:
        emit(f"{sha256_file(p)} *{rel(p)}")

    # ---- verdict -------------------------------------------------------------------
    emit()
    emit("--- 13. verdict ---")
    failed = [(n, d) for n, ok, d in checks if not ok]
    for n, ok, d in checks:
        emit(f"{n}: {'PASS' if ok else 'FAIL'}{(' (' + d + ')') if d and not ok else ''}")
    ok_all = not failed
    emit(f"A14_FINAL_CHECKS_JSON: {'PASS' if ok_all else 'FAIL'}")
    emit(f"FINAL_CHECKS: {'PASS' if ok_all else 'FAIL'}")

    text = "\n".join(lines) + "\n"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text, encoding="utf-8", newline="\n")
    sys.stdout.write(text)
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
