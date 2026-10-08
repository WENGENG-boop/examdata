"""Append one validated entry to CLOSURE_LEDGER.json.

Usage:
    python -B tools/ledger_add.py <entry.json>

The entry file must be a JSON object with the required keys. Hashes listed in
"output_hashes" / "input_hashes" are verified against the actual files when the
value looks like a workspace-relative or absolute path (see resolve_hash).
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

RUN = Path(__file__).resolve().parent.parent
WS = RUN.parents[2]
LEDGER = RUN / "CLOSURE_LEDGER.json"


def resolve(rel: str) -> Path:
    p = Path(rel)
    if p.is_absolute():
        return p
    if (RUN / rel).exists():
        return RUN / rel
    return WS / rel

REQUIRED = (
    "task_id",
    "action",
    "dependencies",
    "status",
    "evidence_class",
    "required_authorization",
    "blockers",
)

VALID_STATUS = {"pending", "in_progress", "pass", "fail", "blocked_authorization",
                "blocked_environment", "not_applicable_with_reason", "done"}
VALID_EVIDENCE = {"private_synthetic", "private_real_data", "real_source",
                  "environment_probe", "historical_frozen"}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_ledger() -> dict:
    if LEDGER.exists():
        return json.loads(LEDGER.read_text(encoding="utf-8"))
    return {
        "schema": "closure.ledger/1",
        "run_root": str(RUN),
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "frozen_execution_ledger": {
            "path": "docs/integration/execution/execution-ledger.json",
            "sha256": "6d4449d3997b437fd3ea3a1fe7925fc78a7c0adbe0a5d3b793d6a8063101b4ba",
            "mutated": False,
        },
        "entries": [],
    }


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2
    entry = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
    missing = [k for k in REQUIRED if k not in entry]
    if missing:
        print(f"missing required keys: {missing}")
        return 2
    if entry["status"] not in VALID_STATUS:
        print(f"invalid status: {entry['status']}")
        return 2
    if entry["evidence_class"] not in VALID_EVIDENCE:
        print(f"invalid evidence_class: {entry['evidence_class']}")
        return 2

    for key in ("input_hashes", "output_hashes"):
        hashes = entry.get(key) or {}
        for rel, digest in list(hashes.items()):
            candidate = resolve(rel)
            if candidate.exists():
                actual = sha256_file(candidate)
                if actual != digest:
                    print(f"HASH MISMATCH {rel}: ledger={digest} actual={actual}")
                    return 3
            else:
                print(f"WARNING {key}: {rel} not found on disk (kept as declared)")
    for key in ("evidence_paths",):
        for rel in entry.get(key) or []:
            candidate = resolve(rel)
            if not candidate.exists():
                print(f"WARNING evidence path missing: {rel}")

    ledger = load_ledger()
    if any(e["task_id"] == entry["task_id"] for e in ledger["entries"]):
        print(f"duplicate task_id: {entry['task_id']}")
        return 2
    entry.setdefault("recorded_at", datetime.now(timezone.utc).isoformat(timespec="seconds"))
    ledger["entries"].append(entry)
    ledger["updated_at"] = entry["recorded_at"]
    LEDGER.write_text(json.dumps(ledger, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"appended {entry['task_id']} ({entry['status']}); entries={len(ledger['entries'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
