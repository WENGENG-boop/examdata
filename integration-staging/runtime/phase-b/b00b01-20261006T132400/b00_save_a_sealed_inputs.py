"""B00 §2.1 - save the A-sealed inputs into the B00 evidence run dir.

Copies the sealed Phase A governance inputs byte-identically into
docs/integration/execution/evidence/B00/<run-id>/ and writes an index
recording source path, byte size, SHA256, copy time and the label
copied_snapshot for each one. Read-only on the originals.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

RUN_ID = "b00b01-20261006T132400"
API = Path(__file__).resolve().parents[4]
EVID = API / "docs/integration/execution/evidence/B00" / RUN_ID

INPUTS = [
    "docs/integration/execution/execution-ledger.json",
    "docs/integration/execution/ownership.json",
    "docs/integration/execution/A12_ROUTE_COMPATIBILITY_WORKSHEET.json",
    "docs/integration/execution/A14_MERGE_MAP.json",
    "docs/integration/execution/A14_MERGE_MAP.md",
    "docs/integration/execution/A14_RELEASE_MANIFEST.json",
    "docs/integration/execution/A14_REHEARSAL.json",
    "docs/integration/ROUTE_INVENTORY_CURRENT.json",
    "docs/integration/execution/PHASE_A_REPORT.md",
    "docs/integration/execution/PHASE_A_DEFERRED_WORK.md",
    "docs/integration/execution/PHASE_A_INDEPENDENT_REVIEW_2026-10-06.md",
    "docs/integration/execution/evidence/A15/independent_checks_2026-10-06.txt",
]


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    EVID.mkdir(parents=True, exist_ok=True)
    index = {
        "schema": "examdata.integration.b00_a_sealed_inputs/1",
        "run_id": RUN_ID,
        "created_at_local": datetime.now().astimezone().isoformat(timespec="seconds"),
        "purpose": (
            "byte-identical copies of the A-sealed governance inputs, taken as the "
            "B00 starting snapshot; originals untouched (original_read_only)"
        ),
        "files": [],
    }
    for rel in INPUTS:
        src = API / rel
        if not src.exists():
            print(f"MISSING: {rel}")
            return 1
        dst = EVID / f"a_sealed_{Path(rel).name}"
        shutil.copy2(src, dst)
        index["files"].append({
            "label": "copied_snapshot",
            "source_path": rel,
            "evidence_path": str(dst.relative_to(API)).replace("\\", "/"),
            "bytes": src.stat().st_size,
            "sha256": sha256_file(dst),
            "copied_at_local": datetime.now().astimezone().isoformat(timespec="seconds"),
        })
        print(f"copied {rel} -> {dst.name} ({index['files'][-1]['sha256'][:12]})")
    out = EVID / "B00_A_SEALED_INPUTS_INDEX.json"
    out.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
