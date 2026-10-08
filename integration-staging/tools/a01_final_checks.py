#!/usr/bin/env python3
"""A01 closing checks for the Phase A integration (run AFTER the ledger is closed).

Validates:
  1. worksheet: 71 rows, baseline 71/71, allowed statuses, no merged_pass,
     exactly 7 deferred_active_owner rows with reasons, problems empty;
  2. cross-check: baseline route set == re-extraction route set (method+path);
  3. statics self-recorded tool hashes == on-disk hashes;
  4. ledger: 27 tasks, A00/A01 staged_pass, 7 gates all closed, 2 write roots,
     no merged_pass anywhere;
  5. artifact existence;
  6. sha256 manifest of both Phase A roots (excluding this transcript itself).

Writes (and prints) the transcript to
  docs/integration/execution/evidence/A01/final_checks.txt  (override with --out)
and exits 0 (PASS) or 1 (FAIL).

Phase A tool (integration-staging/tools/). Stdlib only; nothing original is touched.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

WS = Path(__file__).resolve().parents[2]
EXEC = WS / "docs" / "integration" / "execution"
EV_A01 = EXEC / "evidence" / "A01"
ROOTS = [WS / "integration-staging", EXEC]

EXPECTED_TASK_IDS = ["A%02d" % i for i in range(16)] + ["B%02d" % i for i in range(11)]
ALLOWED_WS_STATUSES = {
    "not_started", "in_progress", "staged_pass",
    "partial", "blocked", "deferred_active_owner", "not_run",
}

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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(EV_A01 / "final_checks.txt"))
    args = ap.parse_args()
    out_path = Path(args.out)
    if not out_path.is_absolute():
        out_path = (WS / out_path).resolve()
    else:
        out_path = out_path.resolve()

    lines: list[str] = []

    def emit(s: str = "") -> None:
        lines.append(s)

    now_local = datetime.now().astimezone()
    emit("=== A01 final checks (runner: integration-staging/tools/a01_final_checks.py) ===")
    emit(f"generated_at_local: {now_local.isoformat(timespec='seconds')}")
    emit(f"generated_at_utc:   {datetime.now(timezone.utc).isoformat(timespec='seconds')}")
    emit(f"cwd: {Path.cwd()}")
    emit()

    # ---- 1. artifact inventory -------------------------------------------------
    emit("--- 1. artifact inventory (files under the two Phase A roots, excluding this transcript) ---")
    all_files: list[Path] = []
    for root in ROOTS:
        for p in sorted(root.rglob("*")):
            if p.is_file() and p.resolve() != out_path:
                all_files.append(p)
    for p in all_files:
        emit(rel(p))
    emit()

    # ---- 2. worksheet validation ------------------------------------------------
    emit("--- 2. worksheet validation ---")
    try:
        wsht = load_json(EXEC / "A01_ROUTE_COMPATIBILITY_WORKSHEET.json")
        summary = wsht.get("summary", {})
        rows = wsht.get("rows", [])
        statuses: dict[str, int] = {}
        providers: dict[str, int] = {}
        for r in rows:
            statuses[r.get("status")] = statuses.get(r.get("status"), 0) + 1
            providers[r.get("provider")] = providers.get(r.get("provider"), 0) + 1
        deferred = [r for r in rows if r.get("status") == "deferred_active_owner"]
        emit(f"row_count={len(rows)} summary.row_count={summary.get('row_count')}")
        emit(f"baseline={summary.get('baseline_count')} coverage={summary.get('baseline_coverage')} "
             f"new={summary.get('new_in_reextract')} removed={summary.get('removed_from_reextract')}")
        emit(f"status_counts={json.dumps(statuses, sort_keys=True)}")
        emit(f"provider_counts={json.dumps(providers, sort_keys=True)}")
        emit(f"problems={json.dumps(wsht.get('problems'))}")
        check("worksheet.row_count_71", len(rows) == 71 and summary.get("row_count") == 71,
              f"rows={len(rows)}")
        check("worksheet.baseline_71_71",
              summary.get("baseline_count") == 71 and summary.get("baseline_coverage") == "71/71"
              and summary.get("new_in_reextract") == 0 and summary.get("removed_from_reextract") == 0)
        bad_status = set(statuses) - ALLOWED_WS_STATUSES
        check("worksheet.statuses_allowed", not bad_status, f"bad={sorted(bad_status)}")
        check("worksheet.no_merged_pass", "merged_pass" not in statuses)
        check("worksheet.deferred_7",
              len(deferred) == 7 and all((r.get("deferred_reason") or "").strip() for r in deferred),
              f"deferred={len(deferred)}")
        check("worksheet.problems_empty", wsht.get("problems") in ([], None))
        malformed = [r.get("legacy_path") for r in rows
                     if not r.get("legacy_path") or not r.get("method")
                     or not r.get("v2_target") or not r.get("compatibility_strategy")]
        check("worksheet.rows_complete", not malformed, f"malformed={malformed[:5]}")
        check("worksheet.providers_known",
              set(providers) <= {"ielts", "cie", "toefl", "platform", "mixed", "materials", "timetable"},
              f"providers={sorted(providers)}")

        # ---- 3. baseline == re-extraction (method+path) ------------------------
        emit()
        emit("--- 3. baseline vs re-extraction route-set equality ---")
        base = load_json(WS / "docs" / "integration" / "ROUTE_INVENTORY_CURRENT.json")
        rex = load_json(EV_A01 / "route_inventory_reextract.json")
        bset = {(r["method"], r["path"]) for r in base.get("routes", [])}
        rset = {(r["method"], r["path"]) for r in rex.get("routes", [])}
        emit(f"baseline_routes={len(bset)} reextract_routes={len(rset)} "
             f"missing={sorted(bset - rset)[:5]} extra={sorted(rset - bset)[:5]}")
        emit(f"groups_equal={base.get('groups') == rex.get('groups')}")
        check("routes.sets_equal", bset == rset and len(bset) == 71)
        check("routes.groups_equal",
              base.get("groups") == rex.get("groups")
              and sum(base.get("groups", {}).values()) == 71)
        check("routes.no_duplicates",
              rex.get("duplicate_method_paths") == [] and rex.get("explicit_route_count") == 71
              and base.get("explicit_route_count") == 71)
    except Exception as e:  # noqa: BLE001
        check("worksheet.load_and_validate", False, f"exception={e!r}")

    # ---- 4. statics self-hash cross-check ---------------------------------------
    emit()
    emit("--- 4. statics self-recorded tool hashes vs on-disk ---")
    try:
        statics = load_json(EV_A01 / "statics_extract.json")
        recorded = statics.get("source_and_tool_hashes", {})
        for tool_rel in ("integration-staging/tools/a01_static_inventory.py",
                         "integration-staging/tools/a01_inventory_routes.py"):
            disk = sha256_file(WS / tool_rel)
            rec = (recorded.get(tool_rel) or {}).get("sha256")
            emit(f"{tool_rel}: recorded={rec} on_disk={disk} match={rec == disk}")
            check(f"statics.self_hash[{Path(tool_rel).name}]", rec == disk)
    except Exception as e:  # noqa: BLE001
        check("statics.load_and_validate", False, f"exception={e!r}")

    # ---- 5. ledger validation ---------------------------------------------------
    emit()
    emit("--- 5. ledger validation ---")
    try:
        led = load_json(EXEC / "execution-ledger.json")
        tasks = led.get("tasks", [])
        by_id = {t.get("task_id"): t for t in tasks}
        ids = [t.get("task_id") for t in tasks]
        gates = led.get("gates", {})
        open_gates = [g for g, v in gates.items() if v.get("open")]
        all_statuses: dict[str, int] = {}
        for t in tasks:
            all_statuses[t["status"]] = all_statuses.get(t["status"], 0) + 1
        a00 = by_id.get("A00", {})
        a01 = by_id.get("A01", {})
        deferred_ids = [d.get("id") for d in led.get("deferred_work", [])]
        emit(f"schema={led.get('schema')} mode={led.get('mode')}")
        emit(f"task_count={len(ids)} unique={len(set(ids))}")
        emit(f"missing={[t for t in EXPECTED_TASK_IDS if t not in ids]} "
             f"unexpected={[t for t in ids if t not in EXPECTED_TASK_IDS]}")
        emit(f"status_counts={json.dumps(all_statuses, sort_keys=True)}")
        emit(f"A00_status={a00.get('status')} A01_status={a01.get('status')}")
        emit(f"gate_count={len(gates)} open_gates={open_gates}")
        emit(f"deferred_work_ids={deferred_ids}")
        expected_roots = [str((WS / 'integration-staging').as_posix()),
                          str((WS / 'docs' / 'integration' / 'execution').as_posix())]
        check("ledger.count_unique",
              len(ids) == 27 and len(set(ids)) == 27
              and not [t for t in EXPECTED_TASK_IDS if t not in ids]
              and not [t for t in ids if t not in EXPECTED_TASK_IDS])
        check("ledger.schema_mode",
              led.get("schema") == "examdata.integration.ledger/1"
              and led.get("mode") == "PHASE_A_ISOLATED_ONLY")
        check("ledger.a00_a01_staged",
              a00.get("status") == "staged_pass" and a01.get("status") == "staged_pass",
              f"A00={a00.get('status')} A01={a01.get('status')}")
        check("ledger.no_merged_pass", "merged_pass" not in all_statuses)
        check("ledger.gates_closed", len(gates) == 7 and not open_gates)
        check("ledger.a01_write_roots",
              a01.get("allowed_write_roots") == expected_roots
              and led.get("allowed_write_roots") == expected_roots,
              json.dumps(a01.get("allowed_write_roots")))
        check("ledger.a01_evidence_recorded",
              bool(a01.get("evidence_paths")) and bool(a01.get("input_hashes"))
              and bool(a01.get("commands")) and (a01.get("next_action") or "").strip() != "")
        check("ledger.deferred_work_present", len(deferred_ids) >= 6 and "DEF-01" in deferred_ids)

        own = load_json(EXEC / "ownership.json")
        own_roots = [r.get("path") for r in own.get("allowed_write_roots", [])]
        check("ownership.write_roots_2",
              len(own_roots) == 2 and set(own_roots) == set(expected_roots),
              json.dumps(own_roots))
    except Exception as e:  # noqa: BLE001
        check("ledger.load_and_validate", False, f"exception={e!r}")

    # ---- 6. artifact existence ---------------------------------------------------
    emit()
    emit("--- 6. artifact existence ---")
    required = [
        "docs/integration/execution/A01_ROUTE_COMPATIBILITY_WORKSHEET.json",
        "docs/integration/execution/A01_COMPONENT_INVENTORY.md",
        "docs/integration/execution/A01_CLI_INVENTORY.md",
        "docs/integration/execution/A01_CONFIGURATION_MATRIX.md",
        "docs/integration/execution/A01_DATA_ROOT_INVENTORY.md",
        "docs/integration/execution/A01_REPORT.md",
        "docs/integration/execution/execution-ledger.json",
        "docs/integration/execution/ownership.json",
        "docs/integration/execution/A00_INITIAL_REPORT.md",
        "docs/integration/execution/evidence/A00/final_checks.txt",
        "docs/integration/execution/evidence/A01/source_hashes_and_observation.txt",
        "docs/integration/execution/evidence/A01/route_inventory_reextract.json",
        "docs/integration/execution/evidence/A01/route_inventory_reextract_stdout.txt",
        "docs/integration/execution/evidence/A01/route_tool_diff.txt",
        "docs/integration/execution/evidence/A01/statics_extract.json",
        "docs/integration/execution/evidence/A01/statics_extract_stdout.txt",
        "docs/integration/execution/evidence/A01/statics_extract_stdout_FAILED_gbk_decode.txt",
        "docs/integration/execution/evidence/A01/worksheet_build_stdout.txt",
        "integration-staging/tools/ledger_update.py",
        "integration-staging/tools/a01_inventory_routes.py",
        "integration-staging/tools/a01_static_inventory.py",
        "integration-staging/tools/a01_worksheet_build.py",
        "integration-staging/tools/a01_final_checks.py",
    ]
    missing_files = [r for r in required if not (WS / r).is_file()]
    emit(f"missing={missing_files}")
    check("artifacts.all_present", not missing_files)

    # ---- 7. sha256 manifest -------------------------------------------------------
    emit()
    emit("--- 7. artifact sha256 manifest (excluding this transcript) ---")
    for p in all_files:
        emit(f"{sha256_file(p)} *{rel(p)}")

    # ---- verdict -------------------------------------------------------------------
    emit()
    emit("--- 8. verdict ---")
    failed = [(n, d) for n, ok, d in checks if not ok]
    for n, ok, d in checks:
        emit(f"{n}: {'PASS' if ok else 'FAIL'}{(' (' + d + ')') if d and not ok else ''}")
    ok_all = not failed
    emit(f"A01_FINAL_CHECKS_JSON: {'PASS' if ok_all else 'FAIL'}")
    emit(f"FINAL_CHECKS: {'PASS' if ok_all else 'FAIL'}")

    text = "\n".join(lines) + "\n"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text, encoding="utf-8", newline="\n")
    sys.stdout.write(text)
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
