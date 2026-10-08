"""Deterministic updater for docs/integration/execution/execution-ledger.json.

Phase A tool (integration-staging/tools/). Writes canonical JSON (indent=2,
ensure_ascii=False, trailing newline) and validates the result before exiting.

- Never touches gate values or task statuses other than the one selected.
- Refuses `merged_pass` (Phase A is isolated; nothing is merged).
- Refuses to change task_id or mode.
- --patch-file merges a JSON object into the task record (lists replace wholesale).

Usage:
  python ledger_update.py --task A01 --status in_progress --next-action "..."
  python ledger_update.py --task A01 --patch-file close_patch.json
  python ledger_update.py --validate-only
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

LEDGER = Path(__file__).resolve().parents[2] / "docs" / "integration" / "execution" / "execution-ledger.json"

PLAN_STATUSES = [
    "not_started", "in_progress", "staged_pass", "merged_pass",
    "partial", "blocked", "deferred_active_owner", "not_run",
]


def now_local() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def dump(led: dict, path: Path) -> str:
    text = json.dumps(led, ensure_ascii=False, indent=2) + "\n"
    path.write_text(text, encoding="utf-8")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", help="task_id to update, e.g. A01")
    ap.add_argument("--status", choices=PLAN_STATUSES)
    ap.add_argument("--next-action")
    ap.add_argument("--patch-file", help="JSON object merged into the task record")
    ap.add_argument("--validate-only", action="store_true")
    args = ap.parse_args()

    led = load(LEDGER)
    if led.get("mode") != "PHASE_A_ISOLATED_ONLY":
        print(f"REFUSED: ledger mode is {led.get('mode')!r}, expected PHASE_A_ISOLATED_ONLY")
        return 2
    tasks = {t["task_id"]: t for t in led["tasks"]}

    if args.validate_only:
        print(json.dumps({
            "ledger": str(LEDGER),
            "schema": led.get("schema"),
            "task_count": len(led["tasks"]),
            "gates": {g: led["gates"][g]["open"] for g in led["gates"]},
        }, ensure_ascii=False, indent=2))
        return 0

    if not args.task:
        print("REFUSED: --task is required for updates")
        return 2
    if args.task not in tasks:
        print(f"REFUSED: unknown task {args.task!r}; have {len(tasks)} tasks")
        return 2
    if args.status == "merged_pass":
        print("REFUSED: merged_pass is impossible in PHASE_A_ISOLATED_ONLY")
        return 2
    if args.status is None and args.patch_file is None and args.next_action is None:
        print("REFUSED: nothing to do (need --status, --next-action or --patch-file)")
        return 2

    task = tasks[args.task]
    if args.status:
        task["status"] = args.status
    if args.next_action is not None:
        task["next_action"] = args.next_action
    if args.patch_file:
        patch = json.loads(Path(args.patch_file).read_text(encoding="utf-8"))
        if not isinstance(patch, dict):
            print("REFUSED: patch file must contain a JSON object")
            return 2
        for key in ("task_id", "mode"):
            if key in patch:
                print(f"REFUSED: patch may not change {key!r}")
                return 2
        task.update(patch)

    stamp = now_local()
    task["updated_at"] = stamp
    led["updated_at"] = stamp

    digest = dump(led, LEDGER)

    check = load(LEDGER)  # validate the written file parses
    changed = {t["task_id"]: t for t in check["tasks"]}[args.task]
    print(json.dumps({
        "ledger": str(LEDGER),
        "task_id": args.task,
        "status": changed["status"],
        "updated_at": stamp,
        "sha256": digest,
        "gates_open": [g for g in check["gates"] if check["gates"][g]["open"]],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
