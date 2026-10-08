"""Record provenance for the A08 adapter fixtures (plan A03/A08).

The A08 IELTS/TOEFL adapter fixtures live under
``integration-staging/fixtures/synthetic/ielts-toefl/``. Like every staged fixture
they must carry a provenance entry, but they belong to this packet, so their
manifest is kept in its own file rather than editing the frozen A03 or A07
manifests. The fixtures are a new directory (not ``.../adapters/``) precisely so
the frozen A07 manifest, which globs ``.../adapters/*.json``, stays fresh.

Run with ``--check`` to verify without writing (the staged test asserts this).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

STAGING = Path(__file__).resolve().parents[1]
FIXTURE_DIR = STAGING / "fixtures" / "synthetic" / "ielts-toefl"
MANIFEST = FIXTURE_DIR / "PROVENANCE.json"

CREATED_AT = "2026-10-06T00:20:00+08:00"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def build_manifest() -> dict:
    entries = []
    for path in sorted(FIXTURE_DIR.glob("*.json")):
        if path.name == "PROVENANCE.json":
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("fixture_kind") != "synthetic":
            raise SystemExit(f"{path.name} is not labelled synthetic")
        entries.append({
            "path": f"integration-staging/fixtures/synthetic/ielts-toefl/{path.name}",
            "kind": "synthetic",
            "label": "synthetic_fixture",
            "provider": data.get("board"),
            "created_by": "Phase A executor (packet A08)",
            "created_at_local": CREATED_AT,
            "sha256": sha256(path),
            "bytes": path.stat().st_size,
            "note": data.get("_provenance", {}).get("purpose", ""),
        })
    return {
        "schema": "fixture-provenance/1",
        "scope": "A08 IELTS/TOEFL read-adapter synthetic fixtures",
        "note": ("Hand-authored synthetic fixtures shaped like IELTS and TOEFL source documents. "
                 "No upstream content, no real document hashes, no credentials, no real audio."),
        "created_by": "Phase A executor (packet A08)",
        "created_at_local": CREATED_AT,
        "entries": entries,
        "summary": {"entries": len(entries), "synthetic": len(entries)},
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="verify the manifest matches the fixtures without writing")
    args = parser.parse_args(argv)
    manifest = build_manifest()
    text = json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
    if args.check:
        if not MANIFEST.is_file():
            print("A08_PROVENANCE: FAIL (manifest missing)")
            return 1
        if MANIFEST.read_text(encoding="utf-8") != text:
            print("A08_PROVENANCE: FAIL (manifest is stale; re-run without --check)")
            return 1
        print(f"A08_PROVENANCE: PASS ({len(manifest['entries'])} entries)")
        return 0
    MANIFEST.write_text(text, encoding="utf-8")
    print(f"wrote {MANIFEST} ({len(manifest['entries'])} entries)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
