"""Compute sha256 for the W5 ledger lock lists (read-only, no writes anywhere)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

RUN = Path(r"C:\Users\weo\Desktop\api\integration-staging\runtime\integration-closure-20261007-c8b4e0c8")

INPUTS = [
    "candidates/closure-v1/src/examdata/integration/catalog/store.py",
    "candidates/closure-v1/src/examdata/integration/catalog/revision.py",
    "candidates/closure-v1/src/examdata/integration/contracts/models.py",
    "candidates/closure-v1/src/examdata/integration/contracts/quality.py",
    "candidates/closure-v1/src/examdata/integration/contracts/canonical.py",
    "candidates/closure-v1/src/examdata/integration/operations/checkpoints.py",
    "candidates/closure-v1/src/examdata/integration/operations/published.py",
]

OUTPUTS = [
    "migration/tools/w5_common.py",
    "migration/tools/build_source.py",
    "migration/tools/migrate.py",
    "migration/tools/verify.py",
    "migration/tools/restore.py",
    "migration/tools/reconcile.py",
    "migration/tools/publish_concurrent.py",
    "migration/tools/rehearse.py",
    "migration/manifests/run-clean/copy_manifest.json",
    "migration/manifests/run-clean/inventory.json",
    "evidence/w5/COMMANDS.md",
    "evidence/w5/runs/w5-final/summary.json",
    "evidence/w5/runs/w5-final/11-concurrent-publish-race/race.json",
    "evidence/w5/runs/w5-final/12-lost-update-window-probe/window-probe.json",
    "evidence/w5/runs/w5-replay/summary.json",
    "evidence/w5/runs/w5-replay/comparison.json",
    "evidence/w5/runs/w5-replay/11-concurrent-publish-race/race.json",
    "evidence/w5/runs/w5-primary/summary.json",
    "evidence/w5/runs/smoke-racefix/summary.json",
    "evidence/w5/runs/smoke-racefix/11-concurrent-publish-race/race.json",
    "evidence/w5/findings/finding1_cas_lost_update.json",
    "evidence/w5/findings/finding2_windows_race_crash.json",
    "evidence/w5/findings/finding3_nested_unknown_identity.json",
    "evidence/w5/findings/finding3_nested_unknown_repro.out.txt",
    "reports/MIGRATION_AND_RESTORE_REPORT.md",
]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def collect(rels: list[str]) -> tuple[dict[str, str], list[str]]:
    out: dict[str, str] = {}
    missing: list[str] = []
    for rel in rels:
        p = RUN / rel
        if not p.exists():
            missing.append(rel)
            continue
        out[rel] = sha256_file(p)
    return out, missing


def main() -> int:
    inputs, miss_in = collect(INPUTS)
    outputs, miss_out = collect(OUTPUTS)
    print(json.dumps(
        {
            "input_hashes": inputs,
            "output_hashes": outputs,
            "missing_inputs": miss_in,
            "missing_outputs": miss_out,
        },
        indent=2,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
