"""Phase B ledger updater for docs/integration/execution/execution-ledger.json.

Companion to `ledger_update.py` (the Phase A tool). That tool stays frozen with
its Phase A assertions; this tool is the Phase B counterpart with stricter
invariants:

* versioned mode (`--phase-b-mode`, no silent reuse of PHASE_A_ISOLATED_ONLY);
* per-packet `allowed_write_roots` (the packet write set may never widen the
  two ledger roots);
* explicit status schema (`STATUSES`): `done`, `merged_pass`, `deployed`, `live`
  and any unknown alias are refused outright, because this tool cannot validate
  the original-side effect or completion they claim. Only a status this tool
  writes through its full validation (`staged_pass`) can satisfy a dependency;
* action-level gate requirements (`PACKET_ACTIONS`, R03): a gate is required only
  for the action that performs that effect. `private_preparation` performs no
  guarded effect and needs no gate; an action that writes originals always
  requires `original_paths_released`. A private-preparation pass records the
  packet's guarded action as NOT covered, so it can never satisfy an
  original-action prerequisite;
* patch-field protection (R02): `--patch-file` may set only whitelisted fields.
  Dependency, gate, ownership, effect, identity, and mode fields are reserved and
  a patch that touches one is refused. Dependency definitions need a dedicated
  audited operation, not a generic patch;
* the complete candidate record is built and validated (dependencies, action
  gates, evidence, blocked_by) before the single atomic publish; on any refusal
  the ledger bytes are left unchanged;
* gate declarations (`--open-gate`) require the human four-part credential
  (instruction text, timestamp, path scope, remaining constraints); a gate
  listed in the task's `blocked_by` is only lifted with `--allow-unblock`,
  the credential scope must cover every path the packet declares, and opening
  one gate never opens another;
* every status this tool writes records `original_changes_applied=false` with
  its basis, because no update it can make applies a change to the originals;
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
      --private-preparation-only \
      --patch-file patch.json
  b_ledger_update.py --task B00 --open-gate original_paths_released \
      --credential credential.json [--allow-unblock]
"""
from __future__ import annotations

import argparse
import copy
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

# Statuses that claim the original tree was merged into / deployed, or that claim
# completion this tool cannot validate. Never writable here (R01).
CLAIM_STATUSES = {"merged_pass", "deployed", "live", "done"}

# Explicit status schema. `done` is deliberately absent: the review reproduced
# `--status done` bypassing completion validation (R01), so it is rejected as an
# unsupported alias rather than treated as complete.
STATUSES = ("not_started", "in_progress", "partial", "blocked", "deferred", "staged_pass")

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

# Action-level gate requirements (R03). A packet maps each action it can perform
# to the gates *that action* needs. `private_preparation` (implicit for every
# packet) performs no guarded effect and needs no gate. The first listed action
# is the packet's primary action: what a bare `--status staged_pass` records. An
# optional action is claimed with `--action`. Every action that writes originals
# includes `original_paths_released`; an action that does none of the guarded
# effects needs none of those gates.
PACKET_ACTIONS: dict[str, dict[str, tuple[str, ...]]] = {
    "B00": {"released_baseline": ("original_paths_released",)},
    "B01": {"runtime_merge": ("original_paths_released",)},
    "B02": {"config_integration": ("original_paths_released",),
            "service_cutover": ("original_paths_released",
                                "existing_service_cutover_authorized")},
    "B03": {"catalog_private_snapshots": ("original_paths_released",),
            "real_data_write": ("original_paths_released", "real_data_write_authorized")},
    "B04": {"legacy_gateway_merge": ("original_paths_released",)},
    "B05": {"timetable_adapter_integration": ("original_paths_released",),
            "upstream_validation": ("original_paths_released",
                                    "upstream_requests_authorized"),
            "cie_resume": ("cie_resume_authorized",)},
    "B06": {"materials_integration": ("original_paths_released",),
            "service_cutover": ("original_paths_released",
                                "existing_service_cutover_authorized")},
    "B07": {"integration_merge": ("original_paths_released",),
            "service_cutover": ("original_paths_released",
                                "existing_service_cutover_authorized")},
    "B08": {"catalog_publish": ("original_paths_released",),
            "real_data_write": ("real_data_write_authorized",)},
    "B09": {"release_build": ("original_paths_released",)},
    "B10": {"release_package": ("original_paths_released",),
            "deployment": ("original_paths_released", "remote_deployment_authorized"),
            "original_cleanup": ("original_paths_released", "original_cleanup_authorized")},
}

# Fields a generic --patch-file may set. Everything else is refused (R02): the
# record is built and validated by this tool, not by an arbitrary patch.
PATCHABLE_FIELDS = frozenset({
    "notes", "commands", "exit_codes", "test_results", "changed_files",
    "evidence_paths", "input_hashes", "inputs", "remaining_gaps", "failures",
})

# Reserved fields (R02). Dependency, gate, ownership, effect, identity and mode
# fields may never be changed by a generic patch.
PROTECTED_FIELDS = frozenset({
    "task_id", "mode", "status", "action", "allowed_write_roots",
    "dependencies", "blocked_by", "original_changes_applied",
    "original_changes_applied_basis", "guarded_action_gates_open",
    "guarded_action_gates_missing", "updated_at",
})

# Statuses that count as a packet being complete for dependency purposes. Only a
# status this tool writes through its full validation qualifies; `done` and
# `merged_pass` are rejected on write and can never legitimately satisfy a
# dependency (R01).
COMPLETE_STATUSES = ("staged_pass",)


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


def action_gates(task_id: str, action: str) -> tuple[str, ...]:
    """Gates the named action needs; `private_preparation` needs none."""
    if action == "private_preparation":
        return ()
    return tuple(PACKET_ACTIONS.get(task_id, {}).get(action, ()))


def deps_incomplete(tasks: dict, candidate: dict, action: str) -> list[str]:
    """Dependencies that do not satisfy `candidate` for `action`.

    A dependency counts as complete only if its status is a validated complete
    status. For a non-private action a dependency that carries only a
    private-preparation pass does NOT satisfy it (R03): private preparation must
    not stand in for an original-action prerequisite.
    """
    out: list[str] = []
    for dep in candidate.get("dependencies") or []:
        rec = tasks.get(dep, {})
        status = rec.get("status")
        if status not in COMPLETE_STATUSES:
            out.append(f"{dep}={status}")
            continue
        if action != "private_preparation":
            if rec.get("action") == "private_preparation" \
                    or rec.get("guarded_action_gates_open") is False:
                out.append(f"{dep}={status} (private-preparation only)")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Phase B ledger updater (private preparation).")
    ap.add_argument("--task")
    ap.add_argument("--status")
    ap.add_argument("--action",
                    help="action this pass covers (default: the packet's primary action)")
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
            action_checks = {}
            actions = {"private_preparation": (), **PACKET_ACTIONS.get(tid, {})}
            for aname, gates in actions.items():
                miss = [g for g in gates if g not in open_gates_now]
                action_checks[aname] = {
                    "required_gates": list(gates),
                    "required_gates_missing": miss,
                    "guarded_action_open": not miss,
                }
            packet_checks[tid] = {
                "status": t.get("status"),
                "action": t.get("action"),
                "dependencies": deps,
                "dependencies_incomplete": incomplete,
                "actions": action_checks,
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
        protected = sorted(set(patch) & PROTECTED_FIELDS)
        if protected:
            print(f"REFUSED: patch may not set protected field(s) {protected}; "
                  "dependency/gate/ownership/effect/identity fields need a dedicated "
                  "audited operation, not a generic patch")
            return 2
        unknown = sorted(set(patch) - PATCHABLE_FIELDS)
        if unknown:
            print(f"REFUSED: patch field(s) not allowed: {unknown}; "
                  f"allowed: {sorted(PATCHABLE_FIELDS)}")
            return 2

    # ---- action selection (R03) ----------------------------------------------
    actions = PACKET_ACTIONS.get(args.task)
    if actions is None:
        print(f"REFUSED: no action model for packet {args.task!r}")
        return 2
    primary_action = next(iter(actions))
    if args.private_preparation_only:
        action = "private_preparation"
    elif args.action:
        if args.action not in actions:
            print(f"REFUSED: unknown action {args.action!r} for {args.task}; "
                  f"allowed: {sorted(('private_preparation', *actions))}")
            return 2
        action = args.action
    else:
        action = primary_action

    # ---- status schema (R01) --------------------------------------------------
    if args.status is not None:
        if args.status in CLAIM_STATUSES:
            print(f"REFUSED: status {args.status!r} claims original-side effects or "
                  "completion this tool cannot validate")
            return 2
        if args.status not in STATUSES:
            print(f"REFUSED: unsupported status {args.status!r}; allowed: {list(STATUSES)}")
            return 2
    is_pass = args.status == "staged_pass"
    if is_pass and args.original_changes_applied is None:
        print("REFUSED: staged_pass in Phase B requires --original-changes-applied "
              "true|false (private preparation must declare it false)")
        return 2
    if args.original_changes_applied == "true":
        print("REFUSED: --original-changes-applied true contradicts this private-"
              "preparation tool; merged effects need the human gates, not a flag")
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

    # ---- build the complete candidate record (validated before publish) -------
    stamp = now_local()
    candidate = copy.deepcopy(task)
    candidate["action"] = action
    if args.status is not None:
        candidate["status"] = args.status
        # Every status this tool can write is a private-preparation status: the
        # claim statuses are refused above, so no update made by this tool ever
        # applies a change to the originals.
        candidate["original_changes_applied"] = False
        candidate["original_changes_applied_basis"] = (
            f"phase-b private preparation ({args.status}, action={action}): no original "
            "path written; no gate opened; this tool refuses merged_pass/deployed/live/done")
    if args.phase_b_mode:
        candidate["mode"] = args.phase_b_mode
    if args.next_action is not None:
        candidate["next_action"] = args.next_action
    for key, value in patch.items():
        candidate[key] = value
    candidate["updated_at"] = stamp

    open_gates_set = {g for g, v in led["gates"].items() if v.get("open")}

    # ---- evidence guards for staged_pass (forge resistance, on the candidate) --
    if is_pass:
        commands = candidate.get("commands") or []
        test_results = candidate.get("test_results") or []
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

    # ---- machine-checked dependencies (on the candidate) ----------------------
    # Checked before the action-gate requirement: a pass whose prerequisites are
    # incomplete is refused for that reason even when the action's gate is also
    # closed (both are true; the dependency is the more fundamental blocker).
    if is_pass:
        incomplete = deps_incomplete(tasks, candidate, action)
        if incomplete:
            print(f"REFUSED: {args.task} dependencies are not complete: "
                  f"{', '.join(incomplete)} (complete means one of {COMPLETE_STATUSES})")
            return 2

    # ---- action-level gate requirement (R03, on the candidate) -----------------
    missing = [g for g in action_gates(args.task, action) if g not in open_gates_set]
    if is_pass and missing:
        print(f"REFUSED: action {action!r} on {args.task} requires gate(s) {missing}; "
              "pass --private-preparation-only to record a pass that covers only "
              "private preparation")
        return 2
    if action == "private_preparation":
        guarded_missing = [g for g in action_gates(args.task, primary_action)
                           if g not in open_gates_set]
        candidate["guarded_action_gates_open"] = False
        candidate["guarded_action_gates_missing"] = guarded_missing
        if args.status is not None:
            candidate["original_changes_applied_basis"] += (
                f"; private-preparation-only pass: the packet's guarded action "
                f"{primary_action!r} is NOT covered"
                + (f" (missing {guarded_missing})" if guarded_missing else ""))
    else:
        candidate["guarded_action_gates_open"] = not missing
        candidate["guarded_action_gates_missing"] = missing

    # ---- dependencies (gates blocking the packet) -----------------------------
    blocking = [d for d in candidate.get("blocked_by", []) if d.startswith("gate:")]
    still_blocked = [g for g in blocking if g[len("gate:"):] not in open_gates_set]
    if is_pass and still_blocked and not args.open_gate:
        print(f"REFUSED: {args.task} is blocked by {still_blocked}; staged_pass with a "
              "blocking gate requires recording the human release first "
              "(--open-gate --credential ... --allow-unblock)")
        return 2

    # ---- gate opening (validated before publish) ------------------------------
    cred = None
    if args.credential:
        cred = json.loads(Path(args.credential).read_text(encoding="utf-8"))
        missing_cred = [k for k in CREDENTIAL_KEYS if not str(cred.get(k, "")).strip()]
        if missing_cred:
            print(f"REFUSED: gate credential missing four-part elements: {missing_cred}")
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
        blocked_names = {b[len("gate:"):] for b in candidate.get("blocked_by", []) if b.startswith("gate:")}
        if (gate in blocked_names or gate in candidate.get("blocked_by", [])) and not args.allow_unblock:
            print(f"REFUSED: {gate!r} is in {args.task}'s blocked_by; pass "
                  "--allow-unblock to record a human release that lifts it")
            return 2
        # credential scope must cover every path the packet declares
        declared = list(candidate.get("changed_files", []))
        for target in declared:
            if not scope_covers(cred["scope"], target):
                print(f"REFUSED: credential scope {cred['scope']!r} does not cover "
                      f"declared path {target!r}")
                return 2

    # ---- publish: apply the validated candidate + gate changes atomically ------
    status_before = task.get("status")
    history = led.setdefault("history", [])
    task.clear()
    task.update(candidate)
    for gate in args.open_gate:
        led["gates"][gate] = {
            "open": True,
            "instruction": cred["instruction"],
            "opened_at": cred["timestamp"],
            "scope": cred["scope"],
            "constraints": cred["constraints"],
            "recorded_by": "b_ledger_update.py",
        }
    history.append({
        "at": stamp,
        "tool": "b_ledger_update.py",
        "task_id": args.task,
        "action": action,
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
        "action": action,
        "status": {t["task_id"]: t for t in check["tasks"]}[args.task]["status"],
        "gates_open": [g for g in check["gates"] if check["gates"][g]["open"]],
        "history_events": len(check.get("history", [])),
        "updated_at": stamp,
        "sha256": digest,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
