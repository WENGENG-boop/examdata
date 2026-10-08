"""Phase B ledger updater for docs/integration/execution/execution-ledger.json.

Companion to `ledger_update.py` (the Phase A tool). That tool stays frozen with
its Phase A assertions; this tool is the Phase B counterpart with stricter
invariants:

* versioned mode (`--phase-b-mode`, no silent reuse of PHASE_A_ISOLATED_ONLY);
* per-packet `allowed_write_roots` (the packet write set may never widen the
  two ledger roots);
* machine-checked packet `dependencies` and per-packet gate requirements
  (`PACKET_REQUIRED_GATES`): a `staged_pass` is refused while a listed dependency
  is incomplete or while a gate the packet requires is closed, unless the caller
  declares `--private-preparation-only` (the record then marks the guarded action
  unopened); `--validate-only` reports both per packet;
* gate declarations (`--open-gate`) require the human four-part credential
  (instruction text, timestamp, path scope, remaining constraints); a gate
  listed in the task's `blocked_by` is only lifted with `--allow-unblock`,
  the credential scope must cover every path the packet declares, and opening
  one gate never opens another;
* statuses that claim original-side effects (`merged_pass`, `deployed`,
  `live`) are refused outright; `staged_pass` is only recorded together with
  an explicit `original_changes_applied=false` declaration and a patch whose
  pass results carry concrete evidence; every status this tool writes records
  `original_changes_applied=false` with its basis, because no update it can
  make applies a change to the originals;
* sealed A records (task_id starting with "A") are never modified;
* `--expect-inputs` re-hashes named files (relative paths resolve against the
  workspace root, not the ledger's parent) and refuses the update when any
  digest changed, or the file vanished, since the caller recorded it;
* atomic write + read-back validation; history preserved via the append-only
  `history` list in the ledger root;
* `EXAMDATA_B_LEDGER` overrides the ledger path so the rejection self-test
  can run against a private copy (the real ledger is never touched by tests).

Usage:
  b_ledger_update.py --validate-only
  b_ledger_update.py --task B00 --status staged_pass \
      --phase-b-mode PHASE_B_PRIVATE_RECONCILIATION \
      --original-changes-applied false \
      --patch-file patch.json
  b_ledger_update.py --task B00 --open-gate original_paths_released \
      --credential credential.json [--allow-unblock]
"""
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

# Workspace root, derived from this tool's own location (never from the ledger
# path: EXAMDATA_B_LEDGER may point at a private copy in a different depth).
WORKSPACE = Path(__file__).resolve().parents[2]
LEDGER = Path(os.environ.get("EXAMDATA_B_LEDGER") or
              (WORKSPACE / "docs" / "integration" /
               "execution" / "execution-ledger.json"))

SCHEMA = "examdata.integration.ledger/1"

# Statuses that claim the original tree was merged into / deployed.
CLAIM_STATUSES = {"merged_pass", "deployed", "live"}

# Credential four-part keys required to open a gate.
CREDENTIAL_KEYS = ("instruction", "timestamp", "scope", "constraints")

GATES = (
    "original_paths_released",
    "real_data_write_authorized",
    "existing_service_cutover_authorized",
    "upstream_requests_authorized",
    "cie_resume_authorized",
    "remote_deployment_authorized",
    "original_cleanup_authorized",
)

PHASE_B_MODES = ("PHASE_B_PENDING_RELEASE", "PHASE_B_PRIVATE_RECONCILIATION")

# Per-packet gate requirements (PHASE_A_DEFERRED_WORK.md section 4). A packet may
# only record a pass for its *guarded action* when every gate it requires is open.
# A pass that covers only private preparation must say so explicitly
# (--private-preparation-only); the record then marks the guarded action unopened.
PACKET_REQUIRED_GATES: dict[str, tuple[str, ...]] = {
    "B00": ("original_paths_released",),
    "B01": ("original_paths_released",),
    "B02": ("original_paths_released", "existing_service_cutover_authorized"),
    "B03": ("original_paths_released", "real_data_write_authorized"),
    "B04": ("original_paths_released",),
    "B05": ("original_paths_released", "upstream_requests_authorized"),
    "B06": ("original_paths_released", "existing_service_cutover_authorized"),
    "B07": ("original_paths_released", "existing_service_cutover_authorized"),
    "B08": ("real_data_write_authorized",),
    "B09": ("original_paths_released",),
    "B10": ("original_paths_released", "remote_deployment_authorized",
            "original_cleanup_authorized"),
}

# Statuses that count as a packet being complete for dependency purposes.
COMPLETE_STATUSES = ("staged_pass", "merged_pass", "done")


def now_local() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump_atomic(led: dict, path: Path) -> str:
    """Canonical write: temp file + os.replace, then read-back validation."""
    text = json.dumps(led, ensure_ascii=False, indent=2) + "\n"
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    # read-back validation
    json.loads(path.read_text(encoding="utf-8"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def scope_covers(scope: str, path: str) -> bool:
    """True when a credential path scope covers a target path.

    A scope is a comma/semicolon-separated list of glob patterns, matched
    against the path with forward slashes. A pattern ending in `/**` or `/*`
    matches the prefix; a bare pattern matches itself and anything below it.
    """
    p = path.replace("\\", "/").lstrip("./")
    for pattern in [s.strip() for s in scope.replace(";", ",").split(",") if s.strip()]:
        pat = pattern.replace("\\", "/").lstrip("./")
        if fnmatch.fnmatch(p, pat):
            return True
        if p.startswith(pat.rstrip("/") + "/"):
            return True
    return False


def main() -> int:
    ap = argparse.ArgumentParser(description="Phase B ledger updater (private preparation).")
    ap.add_argument("--task")
    ap.add_argument("--status")
    ap.add_argument("--next-action")
    ap.add_argument("--patch-file")
    ap.add_argument("--phase-b-mode")
    ap.add_argument("--open-gate", action="append", default=[])
    ap.add_argument("--credential", help="JSON file with the human release credential (four parts)")
    ap.add_argument("--expect-inputs", help="JSON {relative_path: sha256} checked before update")
    ap.add_argument("--allow-unblock", action="store_true",
                    help="record that a human release lifts a gate listed in blocked_by")
    ap.add_argument("--original-changes-applied", choices=["true", "false"],
                    help="mandatory declaration for staged_pass in Phase B")
    ap.add_argument("--private-preparation-only", action="store_true",
                    help="declare that a staged_pass covers only private preparation, "
                         "not the packet's gate-guarded action")
    ap.add_argument("--validate-only", action="store_true")
    args = ap.parse_args()

    if not LEDGER.exists():
        print(f"REFUSED: ledger not found at {LEDGER}")
        return 2
    led = load(LEDGER)
    if led.get("schema") != SCHEMA:
        print(f"REFUSED: unexpected schema {led.get('schema')!r}")
        return 2
    tasks = {t["task_id"]: t for t in led["tasks"]}

    if args.validate_only:
        open_gates_now = {g for g, v in led["gates"].items() if v.get("open")}
        packet_checks = {}
        for tid, t in tasks.items():
            if tid.startswith("A"):
                continue
            deps = t.get("dependencies", []) or []
            incomplete = [d for d in deps
                          if tasks.get(d, {}).get("status") not in COMPLETE_STATUSES]
            required = list(PACKET_REQUIRED_GATES.get(tid, ()))
            missing = [g for g in required if g not in open_gates_now]
            packet_checks[tid] = {
                "status": t.get("status"),
                "dependencies": deps,
                "dependencies_incomplete": incomplete,
                "required_gates": required,
                "required_gates_missing": missing,
                "guarded_action_open": not missing,
            }
        print(json.dumps({
            "ledger": str(LEDGER),
            "schema": led.get("schema"),
            "mode": led.get("mode"),
            "task_count": len(led["tasks"]),
            "gates": {g: led["gates"][g]["open"] for g in led["gates"]},
            "history_events": len(led.get("history", [])),
            "packet_checks": packet_checks,
        }, ensure_ascii=False, indent=2))
        return 0

    if not args.task:
        print("REFUSED: --task is required for updates")
        return 2
    if args.task not in tasks:
        print(f"REFUSED: unknown task {args.task!r}")
        return 2
    if args.task.startswith("A"):
        print(f"REFUSED: sealed Phase A record {args.task!r} must never be modified")
        return 2
    task = tasks[args.task]

    # ---- patch shape (validated before anything else can fail) ---------------
    patch = {}
    if args.patch_file:
        patch = json.loads(Path(args.patch_file).read_text(encoding="utf-8"))
        if not isinstance(patch, dict):
            print("REFUSED: patch file must contain a JSON object")
            return 2
        for key in ("task_id", "mode", "status"):
            if key in patch:
                print(f"REFUSED: patch may not carry {key!r}")
                return 2
        if "allowed_write_roots" in patch:
            widening = [r for r in patch["allowed_write_roots"]
                        if r not in led.get("allowed_write_roots", [])]
            if widening:
                print(f"REFUSED: allowed_write_roots may not be widened beyond the "
                      f"ledger roots: {widening}")
                return 2

    # ---- status guards --------------------------------------------------------
    if args.status in ("merged_pass",):
        print("REFUSED: merged_pass claims the originals were merged; private "
              "preparation may only record staged_pass with "
              "original_changes_applied=false")
        return 2
    if args.status in CLAIM_STATUSES:
        print(f"REFUSED: status {args.status!r} claims original-side effects")
        return 2
    if args.status == "staged_pass" and args.original_changes_applied is None:
        print("REFUSED: staged_pass in Phase B requires --original-changes-applied "
              "true|false (private preparation must declare it false)")
        return 2
    if args.original_changes_applied == "true" and args.status == "staged_pass":
        print("REFUSED: --original-changes-applied true contradicts staged_pass; "
              "merged effects need the human gates, not a flag")
        return 2

    # ---- evidence guards for staged_pass (forge resistance) -------------------
    if args.status == "staged_pass":
        merged = {**task, **patch}
        commands = merged.get("commands") or []
        test_results = merged.get("test_results") or []
        if not commands or not all(
                isinstance(c.get("command"), str) and c["command"].strip() for c in commands):
            print("REFUSED: staged_pass requires concrete commands (command text "
                  "with exit codes) in the record")
            return 2
        if not all(isinstance(c.get("exit_code"), int) for c in commands):
            print("REFUSED: staged_pass requires an integer exit_code on every command")
            return 2
        for tr in test_results:
            if tr.get("result") == "pass" and not (tr.get("evidence") and tr.get("exit_code") is not None):
                print(f"REFUSED: pass test_result without concrete evidence/exit_code: "
                      f"{tr.get('check', '<unnamed>')!r}")
                return 2

    # ---- mode -----------------------------------------------------------------
    if args.phase_b_mode and args.phase_b_mode not in PHASE_B_MODES:
        print(f"REFUSED: unknown Phase B mode {args.phase_b_mode!r}")
        return 2

    # ---- concurrency detection ------------------------------------------------
    if args.expect_inputs:
        recorded = json.loads(Path(args.expect_inputs).read_text(encoding="utf-8"))
        changed = []
        for rel, digest in recorded.items():
            p = Path(rel) if Path(rel).is_absolute() else (WORKSPACE / rel)
            try:
                current = sha256_file(p)
            except OSError:
                changed.append(f"{rel} (missing at {p})")
                continue
            if current != digest:
                changed.append(f"{rel} ({digest[:8]} -> {current[:8]})")
        if changed:
            print("REFUSED: input digest changed since it was recorded: " + "; ".join(changed))
            return 2

    # ---- machine-checked dependencies and per-packet gate requirements (F04) ---
    # Checked before the blocked_by gate guard: dependency completeness and the
    # packet's full gate requirement are the more fundamental preconditions.
    open_gates_set = {g for g, v in led["gates"].items() if v.get("open")}
    if args.status == "staged_pass":
        deps = task.get("dependencies", []) or []
        incomplete = [d for d in deps
                      if tasks.get(d, {}).get("status") not in COMPLETE_STATUSES]
        if incomplete:
            detail = ", ".join(f"{d}={tasks.get(d, {}).get('status')}" for d in incomplete)
            print(f"REFUSED: {args.task} dependencies are not complete: {detail} "
                  f"(complete means one of {COMPLETE_STATUSES})")
            return 2
        required = PACKET_REQUIRED_GATES.get(args.task, ())
        missing = [g for g in required if g not in open_gates_set]
        if missing and not args.private_preparation_only:
            print(f"REFUSED: {args.task} requires gate(s) {missing} for its guarded "
                  "action; pass --private-preparation-only to record a pass that "
                  "covers only private preparation")
            return 2

    # ---- dependencies (gates blocking the packet) -----------------------------
    blocking = [d for d in task.get("blocked_by", []) if d.startswith("gate:")]
    open_gates = [g for g, v in led["gates"].items() if v.get("open")]
    still_blocked = [g for g in blocking if g[len("gate:"):] not in open_gates]
    if args.status == "staged_pass" and still_blocked and not args.open_gate:
        print(f"REFUSED: {args.task} is blocked by {still_blocked}; staged_pass with a "
              "blocking gate requires recording the human release first "
              "(--open-gate --credential ... --allow-unblock)")
        return 2

    status_before = task.get("status")
    stamp = now_local()
    history = led.setdefault("history", [])

    # ---- gate opening ---------------------------------------------------------
    cred = None
    if args.credential:
        cred = json.loads(Path(args.credential).read_text(encoding="utf-8"))
        missing = [k for k in CREDENTIAL_KEYS if not str(cred.get(k, "")).strip()]
        if missing:
            print(f"REFUSED: gate credential missing four-part elements: {missing}")
            return 2
    for gate in args.open_gate:
        if gate not in led["gates"]:
            print(f"REFUSED: unknown gate {gate!r}")
            return 2
        if cred is None:
            print(f"REFUSED: opening {gate!r} requires --credential with the "
                  "human four-part release (instruction, timestamp, scope, constraints)")
            return 2
        if len(args.open_gate) > 1:
            print("REFUSED: open gates one at a time (one credential, one gate)")
            return 2
        blocked_names = {b[len("gate:"):] for b in task.get("blocked_by", []) if b.startswith("gate:")}
        if (gate in blocked_names or gate in task.get("blocked_by", [])) and not args.allow_unblock:
            print(f"REFUSED: {gate!r} is in {args.task}'s blocked_by; pass "
                  "--allow-unblock to record a human release that lifts it")
            return 2
        # credential scope must cover every path the packet declares
        declared = list(patch.get("changed_files", [])) + list(task.get("changed_files", []))
        for target in declared:
            if not scope_covers(cred["scope"], target):
                print(f"REFUSED: credential scope {cred['scope']!r} does not cover "
                      f"declared path {target!r}")
                return 2

    # ---- apply ----------------------------------------------------------------
    if args.status:
        task["status"] = args.status
        # Every status this tool can write is a private-preparation status: the
        # claim statuses (merged_pass / deployed / live) are refused above, so
        # no update made by this tool ever applies a change to the originals.
        task["original_changes_applied"] = False
        task["original_changes_applied_basis"] = (
            f"phase-b private preparation ({args.status}): no original path written; "
            "no gate opened; this tool refuses merged_pass/deployed/live")
        required = PACKET_REQUIRED_GATES.get(args.task, ())
        missing_now = [g for g in required
                       if g not in {k for k, v in led["gates"].items() if v.get("open")}]
        if args.status == "staged_pass" and args.private_preparation_only:
            task["guarded_action_gates_open"] = not missing_now
            task["guarded_action_gates_missing"] = missing_now
            task["original_changes_applied_basis"] += (
                "; private-preparation-only pass: the packet's gate-guarded action "
                "is NOT covered" + (f" (missing {missing_now})" if missing_now else ""))
    if args.phase_b_mode:
        task["mode"] = args.phase_b_mode
    if args.next_action is not None:
        task["next_action"] = args.next_action
    for gate in args.open_gate:
        led["gates"][gate] = {
            "open": True,
            "instruction": cred["instruction"],
            "opened_at": cred["timestamp"],
            "scope": cred["scope"],
            "constraints": cred["constraints"],
            "recorded_by": "b_ledger_update.py",
        }
    task.update(patch)
    task["updated_at"] = stamp

    history.append({
        "at": stamp,
        "tool": "b_ledger_update.py",
        "task_id": args.task,
        "status_before": status_before,
        "status_after": task.get("status"),
        "mode": args.phase_b_mode or task.get("mode"),
        "gates_opened": list(args.open_gate),
        "patch_keys": sorted(patch.keys()),
    })
    led["updated_at"] = stamp

    digest = dump_atomic(led, LEDGER)
    check = load(LEDGER)
    print(json.dumps({
        "ledger": str(LEDGER),
        "task_id": args.task,
        "status": {t["task_id"]: t for t in check["tasks"]}[args.task]["status"],
        "gates_open": [g for g in check["gates"] if check["gates"][g]["open"]],
        "history_events": len(check.get("history", [])),
        "updated_at": stamp,
        "sha256": digest,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
