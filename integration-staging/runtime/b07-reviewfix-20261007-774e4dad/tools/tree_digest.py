#!/usr/bin/env python
"""Deterministic tree digest, reimplementing the documented B07 digest rule.

Rule (B07_CANDIDATE_MANIFEST.json ``digest_rule``, and identical to
``tree_digest`` in b07_build_candidate.py): sha256 over ``'path\\0sha256\\n'``
for every file under the root, sorted by path, excluding __pycache__/
.pytest_cache and excluding the named manifest itself.  ``path`` is the POSIX
relative path of the file under the root.

Used by review-fix run b07-reviewfix-20261007-774e4dad (the second private
review-fix run); logic identical to the documented rule and to the earlier
review-fix tool of run b07-reviewfix-20261007-fzgu78c6.

Usage:
    python tree_digest.py <base> [--exclude NAME]...
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib

SKIP_DIRS = {"__pycache__", ".pytest_cache"}


def file_sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tree_digest(base: pathlib.Path, exclude: tuple[str, ...] = ()) -> dict:
    """Deterministic digest over the files under ``base`` (path + content)."""
    entries: list[tuple[str, str]] = []
    for p in sorted(base.rglob("*")):
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        if p.is_file():
            rel = p.relative_to(base).as_posix()
            if rel in exclude:
                continue
            entries.append((rel, file_sha256(p)))
    digest = hashlib.sha256()
    for rel, h in entries:
        digest.update(f"{rel}\0{h}\n".encode("utf-8"))
    return {
        "base": str(base),
        "files": len(entries),
        "excludes": list(exclude),
        "sha256": digest.hexdigest(),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("base")
    ap.add_argument("--exclude", action="append", default=[])
    args = ap.parse_args()
    result = tree_digest(pathlib.Path(args.base), tuple(args.exclude))
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
