#!/usr/bin/env python
"""Record provenance for the B07 operations-root rehearsal fixtures.

The B07 operations view reads a synthetic operations root: seven fixture
checkpoints shaped like the native formats (CIE batch runner, IELTS
``ielts-run-checkpoint/1``, one deliberately unrecognised dialect), one
explicit expected manifest, and a README. They are authored under
``tools/operations-root/`` of this rehearsal run and copied verbatim into the
candidate at ``fixtures/synthetic/operations/operations-root/``.

The fixtures hold invented values only: no upstream content, no real batch or
run state, no real credentials. The stopped CIE checkpoint deliberately carries
a synthetic path and a ``sk-test-`` placeholder so the public sanitizer can be
exercised against them.

Recorded paths are relative to this manifest's own directory, so the same
manifest describes both the authored copy under ``tools/`` and the candidate
copy under ``fixtures/``.

Run with ``--check`` to verify without writing (prints the recorded table).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent / "operations-root"
MANIFEST = ROOT / "PROVENANCE.json"
CREATED_AT = "2026-10-07T05:50:00+08:00"
CREATED_BY = "B07 rehearsal executor (integration-staging)"

FIXTURES = {
    "README.md": {
        "label": "synthetic_documentation",
        "provider": None,
        "note": "Rehearsal README: what each fixture drives and how PROVENANCE.json is regenerated.",
    },
    "cie-location-batch/checkpoint.json": {
        "label": "synthetic_checkpoint",
        "provider": "cie",
        "note": "Stopped CIE batch (subject 9191) awaiting a manual resume; stop_detail carries a synthetic path and a synthetic key so public surfaces must sanitize them.",
    },
    "cie-batch-8888/checkpoint.json": {
        "label": "synthetic_checkpoint",
        "provider": "cie",
        "note": "Running CIE batch (subject 8888); the newest checkpoint for its batch id must win over the stale stopped copy.",
    },
    "cie-batch-8888-stale/checkpoint.json": {
        "label": "synthetic_checkpoint",
        "provider": "cie",
        "note": "Older stopped snapshot of the same CIE batch id; must land as a superseded row that can never override the newer running checkpoint.",
    },
    "run-ok/checkpoint.json": {
        "label": "synthetic_checkpoint",
        "provider": "ielts",
        "note": "Healthy IELTS run (0 errors); the current row for synthetic-run-ok that the older summary must never override.",
    },
    "run-ok-stale/checkpoint.json": {
        "label": "synthetic_checkpoint",
        "provider": "ielts",
        "note": "Older IELTS summary of synthetic-run-ok with one blocked source; kept as a superseded row only.",
    },
    "run-partial/checkpoint.json": {
        "label": "synthetic_checkpoint",
        "provider": "ielts",
        "note": "IELTS run with a blocked writing source; must stay partial and can never read as complete.",
    },
    "unsupported/checkpoint.json": {
        "label": "synthetic_checkpoint",
        "provider": None,
        "note": "Declares no recognised dialect; must surface as an unknown observation with a sanitized problem entry, never as a job.",
    },
    "expected-manifest.json": {
        "label": "synthetic_manifest",
        "provider": None,
        "note": "Explicit expected denominators (partial, exclusion, and no-denominator scopes) for the coverage view; denominators are declared, never inferred from published data.",
    },
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def build_manifest() -> dict:
    found = {
        p.relative_to(ROOT).as_posix()
        for p in ROOT.rglob("*")
        if p.is_file() and p.name != "PROVENANCE.json"
    }
    expected = set(FIXTURES)
    if found != expected:
        raise SystemExit(
            "fixture set drifted: missing=%s unexpected=%s"
            % (sorted(expected - found), sorted(found - expected))
        )
    entries = []
    for rel in sorted(FIXTURES):
        path = ROOT / rel
        spec = FIXTURES[rel]
        entries.append({
            "path": rel,
            "kind": "synthetic",
            "label": spec["label"],
            "provider": spec["provider"],
            "created_by": CREATED_BY,
            "created_at_local": CREATED_AT,
            "sha256": sha256(path),
            "bytes": path.stat().st_size,
            "note": spec["note"],
        })
    return {
        "schema": "fixture-provenance/1",
        "scope": "B07 operations-root rehearsal fixtures",
        "note": (
            "Synthetic fixtures shaped like the native checkpoint formats (CIE batch "
            "runner, ielts-run-checkpoint/1, one deliberately unrecognised dialect) plus "
            "an explicit expected manifest and README. Invented values only: no upstream "
            "content, no real batch/run state, no real credentials."
        ),
        "path_base": "relative to this manifest's directory",
        "created_by": CREATED_BY,
        "created_at_local": CREATED_AT,
        "entries": entries,
        "summary": {"entries": len(entries), "checkpoints": 7, "documents": 2},
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="verify the manifest matches the fixtures without writing")
    args = parser.parse_args(argv)
    manifest = build_manifest()
    text = json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
    for entry in manifest["entries"]:
        print(f"{entry['sha256']}  {entry['bytes']:>5}  {entry['path']}")
    if args.check:
        if not MANIFEST.is_file():
            print("B07_OPERATIONS_ROOT_PROVENANCE: FAIL (manifest missing)")
            return 1
        if MANIFEST.read_text(encoding="utf-8") != text:
            print("B07_OPERATIONS_ROOT_PROVENANCE: FAIL (manifest is stale; re-run without --check)")
            return 1
        print(f"B07_OPERATIONS_ROOT_PROVENANCE: PASS ({len(manifest['entries'])} entries)")
        return 0
    MANIFEST.write_text(text, encoding="utf-8")
    print(f"wrote {MANIFEST} ({len(manifest['entries'])} entries)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
