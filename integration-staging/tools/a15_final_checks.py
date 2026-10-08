#!/usr/bin/env python3
"""A15 closing checks for the Phase A integration (run AFTER the ledger is closed).

Validates:
  1. artifact existence: the two A15 documents (PHASE_A_REPORT.md,
     PHASE_A_DEFERRED_WORK.md), the A15 tools, the close patch, the ledger, the
     compatibility worksheet, the A14 merge map / release manifest / rehearsal,
     every A00-A14 packet report and the A15 evidence directory;
  2. fresh cross-packet re-verification: a14_build_artifacts.py --check and
     a14_rehearsal.py --check reproduce their recorded PASS lines (private
     fixtures, offline, original tree read-only);
  3. ledger state: 27 tasks, A00-A15 all staged_pass, B00-B10 all not_started,
     all seven Phase B gates closed, no merged_pass anywhere, A15 dependencies
     ["A14"], A15 write roots = the two Phase A roots, A15 record fields present,
     no unexpected original change recorded;
  4. close patch consistency: changed files inside the two Phase A roots, the
     three POST_CLOSE transcripts never listed, every A15 deliverable present,
     input hashes recomputed against disk (strict for the two roots and the
     frozen docs/integration inputs, observed-only for the actively owned
     original tree, the self-referential ledger excluded), input-hash count and
     exit_codes identical to the ledger record;
  5. compatibility worksheet coverage: 71/71 baseline rows, 64 staged_pass +
     7 deferred_active_owner, 0 problems, every row status allowed;
  6. PHASE_A_REPORT.md content: every packet A00-A15 named, the staged/not-merged/
     not-deployed statement present, all seven gate names present, the deferred
     list and the merge map referenced, and NO affirmative completion claim;
  7. PHASE_A_DEFERRED_WORK.md content: DEF-01..DEF-06 present, all seven gate
     names present, the explicit-human-release rule present, Phase B entry
     conditions present;
  8. fresh liveness offline: the full staged suite passes 887 and the staged
     frontend node suite passes 27/27 (stdout kept as post-close evidence);
  9. containment + read-only originals: no bytecode under staged src/tests/
     frontend, the A15 tools never import the original application, and every
     recorded base file re-observed (drift logged, never repaired or asserted);
 10. sha256 manifest of both Phase A roots (excluding this transcript).

Writes (and prints) the transcript to
  docs/integration/execution/evidence/A15/final_checks.txt  (override with --out)
and exits 0 (PASS) or 1 (FAIL). It creates the three POST_CLOSE transcripts
(final_checks.txt, pytest_rerun.txt, node_rerun.txt) that are excluded from the
close patch by construction.

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
EV = EXEC / "evidence" / "A15"
STAGING = WS / "integration-staging"
TOOLS = STAGING / "tools"
ROOTS = [STAGING, EXEC]

EXPECTED_TASK_IDS = ["A%02d" % i for i in range(16)] + ["B%02d" % i for i in range(11)]
A_TASK_IDS = ["A%02d" % i for i in range(16)]
B_TASK_IDS = ["B%02d" % i for i in range(11)]
ROOT_STRINGS = [STAGING.relative_to(WS).as_posix() + "/", EXEC.relative_to(WS).as_posix() + "/"]
LEDGER_REL = "docs/integration/execution/execution-ledger.json"

REPORT_REL = "docs/integration/execution/PHASE_A_REPORT.md"
DEFERRED_REL = "docs/integration/execution/PHASE_A_DEFERRED_WORK.md"
MAP_REL = "docs/integration/execution/A14_MERGE_MAP.json"
MAP_MD_REL = "docs/integration/execution/A14_MERGE_MAP.md"
RELEASE_REL = "docs/integration/execution/A14_RELEASE_MANIFEST.json"
REHEARSAL_REL = "docs/integration/execution/A14_REHEARSAL.json"
WORKSHEET_REL = "docs/integration/execution/A12_ROUTE_COMPATIBILITY_WORKSHEET.json"

GATE_NAMES = [
    "original_paths_released",
    "real_data_write_authorized",
    "existing_service_cutover_authorized",
    "upstream_requests_authorized",
    "cie_resume_authorized",
    "remote_deployment_authorized",
    "original_cleanup_authorized",
]

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

A15_TOOLS = ["tools/a15_final_checks.py", "tools/a15_close_patch.py"]
A00_TO_A14_REPORTS = (["docs/integration/execution/A00_INITIAL_REPORT.md"]
                      + ["docs/integration/execution/A%02d_REPORT.md" % i
                         for i in range(1, 15)])
POST_CLOSE = {
    "docs/integration/execution/evidence/A15/final_checks.txt",
    "docs/integration/execution/evidence/A15/pytest_rerun.txt",
    "docs/integration/execution/evidence/A15/node_rerun.txt",
}

#: affirmative completion claims that must NOT appear in the A15 documents' own
#: prose. The scan drops Markdown blockquotes (the verbatim plan quote) and
#: inline code spans (status labels such as `staged_pass`) first, so the check
#: targets what this executor asserts, not what it quotes or labels.
FORBIDDEN_CLAIM_PATTERNS = [
    re.compile(r"\bintegration is complete\b", re.IGNORECASE),
    re.compile(r"\bdeployment is complete\b", re.IGNORECASE),
    re.compile(r"\bhas been deployed\b", re.IGNORECASE),
    re.compile(r"\bhave been merged\b", re.IGNORECASE),
    re.compile(r"\bmerged_pass\b"),
    re.compile(r"\bdeployed to production\b", re.IGNORECASE),
    re.compile(r"\bdeployment is live\b", re.IGNORECASE),
]

_CODE_SPAN = re.compile(r"`[^`]*`")


def prose(text: str) -> str:
    """The document's own assertions: drop blockquoted plan text and code spans."""
    out: list[str] = []
    for line in text.splitlines():
        if line.lstrip().startswith(">"):
            continue
        out.append(_CODE_SPAN.sub("", line))
    return "\n".join(out)

FORBIDDEN_IMPORT_PATTERNS = [
    re.compile(r"^\s*import\s+app\b", re.MULTILINE),
    re.compile(r"^\s*from\s+app\b", re.MULTILINE),
    re.compile(r"^\s*import\s+examdata\b(?!_)", re.MULTILINE),
    re.compile(r"^\s*from\s+examdata\b(?!_)", re.MULTILINE),
]

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
    EV.mkdir(parents=True, exist_ok=True)

    lines: list[str] = []

    def emit(s: str = "") -> None:
        lines.append(s)

    emit("=== A15 final checks (Phase A finish: PHASE_A_REPORT + deferred list + "
         "ownership-release requirements: integration-staging/tools/a15_final_checks.py) ===")
    emit(f"generated_at_local: {datetime.now().astimezone().isoformat(timespec='seconds')}")
    emit(f"generated_at_utc:   {datetime.now(timezone.utc).isoformat(timespec='seconds')}")
    emit(f"cwd: {Path.cwd()}")
    emit()

    # ---- 1. artifact existence -------------------------------------------------
    emit("--- 1. artifact existence ---")
    required = [
        REPORT_REL,
        DEFERRED_REL,
        LEDGER_REL,
        WORKSHEET_REL,
        MAP_REL,
        MAP_MD_REL,
        RELEASE_REL,
        REHEARSAL_REL,
        *A00_TO_A14_REPORTS,
        *[f"integration-staging/{t}" for t in A15_TOOLS],
        "integration-staging/runtime/ledger-patches/A15_close.json",
        "docs/integration/execution/ownership.json",
    ]
    missing_files = [r for r in required if not (WS / r).is_file()]
    emit(f"required={len(required)} missing={missing_files}")
    check("artifacts.all_present", not missing_files, str(missing_files))
    sizes = {r: (WS / r).stat().st_size for r in (REPORT_REL, DEFERRED_REL) if (WS / r).is_file()}
    emit(f"report_sizes={json.dumps(sizes)}")
    check("artifacts.documents_nontrivial",
          all(s > 4000 for s in sizes.values()) and len(sizes) == 2,
          json.dumps(sizes))

    # ---- 2. fresh cross-packet re-verification ----------------------------------
    emit()
    emit("--- 2. fresh cross-packet re-verification (a14_build_artifacts / a14_rehearsal) ---")
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

    # ---- 3. ledger state ---------------------------------------------------------
    emit()
    emit("--- 3. ledger state (A00-A15 staged_pass, B00-B10 not_started, gates closed) ---")
    led: dict = {}
    a15: dict = {}
    try:
        led = load_json(EXEC / "execution-ledger.json")
        by_id = {t.get("task_id"): t for t in led.get("tasks", [])}
        a15 = by_id.get("A15", {})
        tasks = led.get("tasks", [])
        ids = [t.get("task_id") for t in tasks]
        statuses = {}
        for t in tasks:
            statuses[t.get("status")] = statuses.get(t.get("status"), 0) + 1
        gates = led.get("gates", {})
        open_gates = [g for g, v in gates.items() if (v or {}).get("open")]

        a_status = {tid: by_id.get(tid, {}).get("status") for tid in A_TASK_IDS}
        b_status = {tid: by_id.get(tid, {}).get("status") for tid in B_TASK_IDS}
        bad_a = {k: v for k, v in a_status.items() if v != "staged_pass"}
        bad_b = {k: v for k, v in b_status.items() if v != "not_started"}
        emit(f"ledger_schema={led.get('schema')} mode={led.get('mode')} "
             f"task_count={len(ids)} unique={len(set(ids))}")
        emit(f"statuses={json.dumps(statuses, sort_keys=True)}")
        emit(f"A_statuses={json.dumps(a_status, sort_keys=True)}")
        emit(f"B_statuses={json.dumps(b_status, sort_keys=True)}")
        emit(f"gates={len(gates)} open={open_gates} "
             f"unexpected_original_changes={led.get('unexpected_original_changes')}")

        check("ledger.header",
              led.get("schema") == "examdata.integration.ledger/1"
              and led.get("mode") == "PHASE_A_ISOLATED_ONLY")
        check("ledger.count_unique_27",
              len(ids) == 27 and len(set(ids)) == 27
              and not [t for t in EXPECTED_TASK_IDS if t not in ids]
              and not [t for t in ids if t not in EXPECTED_TASK_IDS])
        check("ledger.all_a_staged_pass", not bad_a, json.dumps(bad_a))
        check("ledger.all_b_not_started", not bad_b, json.dumps(bad_b))
        check("ledger.no_merged_pass", "merged_pass" not in statuses)
        check("ledger.gates_closed", len(gates) == 7 and not open_gates,
              f"open={open_gates}")
        check("ledger.gate_names",
              sorted(gates.keys()) == sorted(GATE_NAMES),
              str(sorted(gates.keys())))
        check("ledger.no_unexpected_original_changes",
              led.get("unexpected_original_changes") == [],
              str(led.get("unexpected_original_changes")))

        expected_roots = [STAGING.as_posix(), EXEC.as_posix()]
        check("ledger.a15_write_roots",
              a15.get("allowed_write_roots") == expected_roots
              and led.get("allowed_write_roots") == expected_roots)
        check("ledger.a15_dependencies", a15.get("dependencies") == ["A14"],
              str(a15.get("dependencies")))
        check("ledger.a15_staged_pass", a15.get("status") == "staged_pass",
              f"A15={a15.get('status')}")
        check("ledger.a15_record_fields",
              bool(a15.get("evidence_paths")) and bool(a15.get("input_hashes"))
              and bool(a15.get("commands")) and bool(a15.get("changed_files"))
              and bool(a15.get("test_results")) and bool(a15.get("remaining_gaps")),
              json.dumps({k: bool(a15.get(k)) for k in
                          ("evidence_paths", "input_hashes", "commands",
                           "changed_files", "test_results", "remaining_gaps")}))
        check("ledger.a15_next_action",
              "phase b" in (a15.get("next_action") or "").lower()
              or "release" in (a15.get("next_action") or "").lower(),
              str(a15.get("next_action"))[:160])
    except Exception as e:  # noqa: BLE001
        check("ledger.load_and_validate", False, f"exception={e!r}")

    # ---- 4. close patch consistency ---------------------------------------------
    emit()
    emit("--- 4. close patch consistency (changed files, inputs, exit codes) ---")
    try:
        patch = load_json(STAGING / "runtime" / "ledger-patches" / "A15_close.json")
        cf = patch.get("changed_files") or []
        outside = [f for f in cf
                   if not any(f.replace("\\", "/").startswith(r) for r in ROOT_STRINGS)]
        fc_rel = "integration-staging/tools/a15_final_checks.py"
        cp_rel = "integration-staging/tools/a15_close_patch.py"
        deliverables = [
            fc_rel,
            cp_rel,
            REPORT_REL,
            DEFERRED_REL,
        ]
        emit(f"changed_files={len(cf)} outside_roots={outside} "
             f"post_close_listed={sorted(set(cf) & POST_CLOSE)}")
        check("close_patch.changed_files_inside_roots", not outside, str(outside))
        check("close_patch.post_close_not_listed", not (set(cf) & POST_CLOSE))
        check("close_patch.deliverables_listed",
              all(d in cf for d in deliverables),
              str([d for d in deliverables if d not in cf]))
        check("close_patch.tools_registered",
              fc_rel in cf and cp_rel in cf, f"n={len(cf)}")

        ih = patch.get("input_hashes") or {}
        bad_ih: list[str] = []
        outside_obs: list[str] = []
        for r, h in ih.items():
            # strict recompute: the two Phase A roots and the frozen
            # docs/integration inputs. The ledger is self-referential (re-merged
            # after the patch) and the original tree is actively owned by Kimi:
            # both are observed, never asserted (plan 14 drift policy).
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
              patch.get("exit_codes") == a15.get("exit_codes"),
              f"patch={len(patch.get('exit_codes') or [])} ledger={len(a15.get('exit_codes') or [])}")
        check("close_patch.meta",
              patch.get("dependencies") == ["A14"]
              and patch.get("blocked_by") == []
              and patch.get("allowed_write_roots") == [STAGING.as_posix(), EXEC.as_posix()],
              json.dumps({k: patch.get(k) for k in
                          ("dependencies", "blocked_by", "allowed_write_roots")}))
    except Exception as e:  # noqa: BLE001
        check("close_patch.load_and_validate", False, f"exception={e!r}")

    # ---- 5. compatibility worksheet coverage ------------------------------------
    emit()
    emit("--- 5. compatibility worksheet coverage (71-route baseline) ---")
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

    # ---- 6. PHASE_A_REPORT.md content -------------------------------------------
    emit()
    emit("--- 6. PHASE_A_REPORT.md content (packets, gates, staged/not-merged/not-deployed, no completion claim) ---")
    try:
        report = (WS / REPORT_REL).read_text(encoding="utf-8")
        missing_packets = [p for p in A_TASK_IDS if p not in report]
        missing_gates = [g for g in GATE_NAMES if g not in report]
        lower = report.lower()
        has_disclaimer = ("not merged" in lower and "not deployed" in lower
                          and "staged" in lower)
        refs = {r: (r in report) for r in
                ("PHASE_A_DEFERRED_WORK.md", "A14_MERGE_MAP", "execution-ledger.json",
                 "ownership")}
        forbidden = [pat.pattern for pat in FORBIDDEN_CLAIM_PATTERNS if pat.search(prose(report))]
        emit(f"packets_missing={missing_packets} gates_missing={missing_gates}")
        emit(f"disclaimer_present={has_disclaimer} refs={json.dumps(refs, sort_keys=True)}")
        emit(f"forbidden_claim_patterns_hit={forbidden}")
        check("report.packets_named", not missing_packets, str(missing_packets))
        check("report.gates_named", not missing_gates, str(missing_gates))
        check("report.staged_disclaimer", has_disclaimer)
        check("report.references", all(refs.values()),
              str([k for k, v in refs.items() if not v]))
        check("report.no_completion_claim", not forbidden, str(forbidden))
    except Exception as e:  # noqa: BLE001
        check("report.read_and_validate", False, f"exception={e!r}")

    # ---- 7. PHASE_A_DEFERRED_WORK.md content ------------------------------------
    emit()
    emit("--- 7. PHASE_A_DEFERRED_WORK.md content (DEF-01..06, gates, release rule) ---")
    try:
        deferred = (WS / DEFERRED_REL).read_text(encoding="utf-8")
        defs = ["DEF-%02d" % i for i in range(1, 7)]
        missing_defs = [d for d in defs if d not in deferred]
        missing_gates = [g for g in GATE_NAMES if g not in deferred]
        lower = deferred.lower()
        has_release = ("explicit human" in lower and "release" in lower)
        has_phaseb = "phase b" in lower
        has_ownership = "ownership.json" in deferred
        forbidden = [pat.pattern for pat in FORBIDDEN_CLAIM_PATTERNS if pat.search(prose(deferred))]
        emit(f"defs_missing={missing_defs} gates_missing={missing_gates} "
             f"release_rule={has_release} phase_b={has_phaseb} "
             f"ownership_ref={has_ownership}")
        emit(f"forbidden_claim_patterns_hit={forbidden}")
        check("deferred.defs_present", not missing_defs, str(missing_defs))
        check("deferred.gates_present", not missing_gates, str(missing_gates))
        check("deferred.release_rule_and_entry",
              has_release and has_phaseb and has_ownership)
        check("deferred.no_completion_claim", not forbidden, str(forbidden))
    except Exception as e:  # noqa: BLE001
        check("deferred.read_and_validate", False, f"exception={e!r}")

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
        check("liveness.section_error", False, f"exception={e!r}")

    # ---- 9. containment + read-only original observations ------------------------
    emit()
    emit("--- 9. containment of the A15 write set + read-only original observations ---")
    try:
        outside = [f for f in (a15.get("changed_files") or [])
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
        for t in A15_TOOLS:
            p = STAGING / t
            body = p.read_text(encoding="utf-8")
            for pat in FORBIDDEN_IMPORT_PATTERNS:
                if pat.search(body):
                    offenders.append(f"{rel(p)}::{pat.pattern}")
        emit(f"a15_tools_scanned={len(A15_TOOLS)} offenders={offenders}")
        check("containment.no_original_app_reference", not offenders, str(offenders))

        mmap = load_json(WS / MAP_REL)
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
              len(obs) == 12 and all("current=None" not in o for o in obs),
              f"n={len(obs)}")
    except Exception as e:  # noqa: BLE001
        check("containment.changed_files_inside_roots", False, f"exception={e!r}")

    # ---- 10. sha256 manifest -----------------------------------------------------
    emit()
    emit("--- 10. artifact inventory + sha256 manifest (excluding this transcript) ---")
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

    # ---- verdict ------------------------------------------------------------------
    emit()
    emit("--- 11. verdict ---")
    failed = [(n, d) for n, ok, d in checks if not ok]
    for n, ok, d in checks:
        emit(f"{n}: {'PASS' if ok else 'FAIL'}{(' (' + d + ')') if d and not ok else ''}")
    ok_all = not failed
    emit(f"A15_FINAL_CHECKS_JSON: {'PASS' if ok_all else 'FAIL'}")
    emit(f"FINAL_CHECKS: {'PASS' if ok_all else 'FAIL'}")

    text = "\n".join(lines) + "\n"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text, encoding="utf-8", newline="\n")
    sys.stdout.write(text)
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
