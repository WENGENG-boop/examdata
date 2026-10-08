"""Shared helpers for the W5 synthetic migration/restore rehearsal (B08).

Everything here is stdlib-only.  The module never touches an original
application tree, a real database, a service or a network: the only inputs are
the private synthetic source stores this run builds under ``<run>/migration/``
and the read-only candidate snapshot under ``<run>/candidates/closure-v1``.

Digest algorithms (both inherited, see ``<run>/tools/tree_digest.py``):

* ``historical`` - sha256 over ``"<posix-rel-path>\\0<file-sha256>\\n"`` for
  every file, iterated in ``sorted(WindowsPath)`` order (the frozen B07 rule).
  ``tools/tree_digest.py`` iterates ``sorted(base.rglob("*"))`` on Windows, so
  it implements *this* ordering, not the portable one.
* ``posix-v1`` - the same byte format, iterated in sorted order of the POSIX
  relative path *string* (case-sensitive).

Both are recorded for every tree this package produces or verifies.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

TOOLS_DIR = Path(__file__).resolve().parent
MIGRATION_ROOT = TOOLS_DIR.parent
RUN_ROOT = MIGRATION_ROOT.parent
CANDIDATE_SRC = RUN_ROOT / "candidates" / "closure-v1" / "src"
EVIDENCE_ROOT = RUN_ROOT / "evidence" / "w5"

SOURCE_STORE = MIGRATION_ROOT / "source-store"
SOURCE_DEFECTS = MIGRATION_ROOT / "source-store-defects"
DEST_STORE = MIGRATION_ROOT / "dest-store"
DEST_STORE_2 = MIGRATION_ROOT / "dest-store-2"
DEST_RETRY = MIGRATION_ROOT / "dest-store-retry"
DEST_CONFLICT = MIGRATION_ROOT / "dest-store-conflict"
DEST_CAS = MIGRATION_ROOT / "dest-store-cas"
DEST_DEFECTS = MIGRATION_ROOT / "dest-store-defects"
TAMPER_STORE = MIGRATION_ROOT / "dest-store-tamper"
RESTORE_STORE = MIGRATION_ROOT / "restore-store"
SQLITE_EXPORT = MIGRATION_ROOT / "sqlite-export"
SQLITE_RESTORE = MIGRATION_ROOT / "sqlite-restore"
SQLITE_BARE_COPY = MIGRATION_ROOT / "sqlite-bare-copy"
MANIFEST_DIR = MIGRATION_ROOT / "manifests"

#: Fixed publication timestamp so two runs over the same source produce
#: byte-identical destination trees (repeatability is a checked property).
FIXED_NOW = "2026-10-07T00:00:00+00:00"

SKIP_DIR_NAMES = {"__pycache__", ".pytest_cache"}

#: Authority classes of the staged shapes.  Only authorities participate in
#: the collision-refusal rule; ``rebuildable`` and ``derived`` shapes may be
#: regenerated but are never silently treated as an authority.
AUTHORITY_CLASSES = ("authority", "rebuildable", "derived", "read_only_observed")


# --------------------------------------------------------------------------- #
# hashing / digests
# --------------------------------------------------------------------------- #
def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def iter_files(root: Path, *, skip: Iterable[str] = ()) -> list[Path]:
    """Every regular file under ``root``, skipping cache dirs and ``skip`` names."""
    skip_names = set(skip)
    out: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIR_NAMES)
        for name in sorted(filenames):
            if name in skip_names:
                continue
            out.append(Path(dirpath) / name)
    return out


class OutsideWorkingRoot(Exception):
    """A tool tried to touch a path outside ``<run>/migration``; refused."""


def guard_within(path: Path, root: Path) -> Path:
    """Resolve ``path`` and refuse it unless it lives under ``root``."""
    resolved = Path(path).resolve()
    root = Path(root).resolve()
    if resolved != root and root not in resolved.parents:
        raise OutsideWorkingRoot(f"refusing to operate outside {root}: {resolved}")
    return resolved


def fresh_copy(src: Path, dst: Path) -> dict[str, Any]:
    """Replace ``dst`` with a byte copy of the tree ``src`` (dst is private work)."""
    src = Path(src)
    if not src.is_dir():
        raise FileNotFoundError(f"not a directory: {src}")
    dst = guard_within(dst, MIGRATION_ROOT)
    if dst.exists():
        shutil.rmtree(dst)
    dst.mkdir(parents=True)
    files = 0
    for path in iter_files(src):
        out = dst / path.relative_to(src)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(path.read_bytes())
        files += 1
    return {"src": str(src), "dst": str(dst), "files": files}


def tree_entries(root: Path, order: str, *, skip: Iterable[str] = ()) -> list[tuple[str, str]]:
    """``[(posix_rel_path, sha256)]`` in the requested iteration order."""
    root = Path(root)
    files = [p for p in root.rglob("*") if p.is_file()]
    skip_names = set(skip)
    rows: list[tuple[str, str]] = []
    for path in files:
        if any(part in SKIP_DIR_NAMES for part in path.parts):
            continue
        rel = path.relative_to(root).as_posix()
        if rel in skip_names:
            continue
        rows.append((rel, ""))
    if order == "historical":
        # sorted(WindowsPath) == sorting the Path objects (case-insensitive on
        # Windows), which is exactly what the inherited tool does.
        rows.sort(key=lambda row: Path(root, row[0]))
    elif order == "posix-v1":
        rows.sort(key=lambda row: row[0])
    else:
        raise ValueError(f"unknown digest order {order!r}")
    return [(rel, sha256_file(root / rel)) for rel, _ in rows]


def tree_digest(root: Path, order: str = "historical", *, skip: Iterable[str] = ()) -> dict[str, Any]:
    """Deterministic tree digest in the inherited byte format."""
    entries = tree_entries(root, order, skip=skip)
    digest = hashlib.sha256()
    for rel, file_hash in entries:
        digest.update(f"{rel}\0{file_hash}\n".encode("utf-8"))
    return {
        "base": str(Path(root)),
        "files": len(entries),
        "order": order,
        "excludes": sorted(skip),
        "sha256": digest.hexdigest(),
    }


def both_digests(root: Path, *, skip: Iterable[str] = ()) -> dict[str, Any]:
    return {
        "historical": tree_digest(root, "historical", skip=skip),
        "posix_v1": tree_digest(root, "posix-v1", skip=skip),
    }


# --------------------------------------------------------------------------- #
# json helpers
# --------------------------------------------------------------------------- #
def canonical_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def write_json(path: Path, payload: Any) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                     encoding="utf-8", newline="\n")


def read_json(path: Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def dump(payload: Any) -> None:
    """Deterministic stdout JSON for every tool in this package."""
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# --------------------------------------------------------------------------- #
# candidate import (read-only)
# --------------------------------------------------------------------------- #
def candidate_importable() -> None:
    """Make ``examdata.integration`` importable from the frozen candidate snapshot."""
    src = str(CANDIDATE_SRC)
    if src not in sys.path:
        sys.path.insert(0, src)


def catalog_api() -> dict[str, Any]:
    """The candidate primitives this rehearsal exercises (read-only import)."""
    candidate_importable()
    from examdata.integration.catalog.builder import CatalogBuilder  # noqa: PLC0415
    from examdata.integration.catalog.model import (  # noqa: PLC0415
        CatalogSnapshot,
        CatalogSource,
        compute_revision,
        counts_for,
        decode_unknown,
        encode_unknown,
    )
    from examdata.integration.catalog.revision import (  # noqa: PLC0415
        ANY_CURRENT,
        PublicationRejected,
        RevisionPublisher,
        StalePublisherError,
    )
    from examdata.integration.catalog.store import (  # noqa: PLC0415
        CatalogStore,
        DuplicateNativeIdError,
    )
    from examdata.integration.contracts import canonical, trust  # noqa: PLC0415
    from examdata.integration.contracts.enums import EntityKind  # noqa: PLC0415
    return {
        "CatalogBuilder": CatalogBuilder,
        "CatalogSnapshot": CatalogSnapshot,
        "CatalogSource": CatalogSource,
        "compute_revision": compute_revision,
        "counts_for": counts_for,
        "decode_unknown": decode_unknown,
        "encode_unknown": encode_unknown,
        "ANY_CURRENT": ANY_CURRENT,
        "PublicationRejected": PublicationRejected,
        "RevisionPublisher": RevisionPublisher,
        "StalePublisherError": StalePublisherError,
        "CatalogStore": CatalogStore,
        "DuplicateNativeIdError": DuplicateNativeIdError,
        "canonical": canonical,
        "trust": trust,
        "EntityKind": EntityKind,
    }


# --------------------------------------------------------------------------- #
# store reading / consistency
# --------------------------------------------------------------------------- #
class StoreInconsistent(Exception):
    """A reader found the store incomplete or inconsistent; never silently used."""


def read_consistent_store(store_root: Path) -> dict[str, Any]:
    """Read one complete, hash-validated view of a catalog store.

    A reader validates the pointed revision before use: the pointer must name a
    retained revision whose body recomputes to the same ``dataset_revision`` and
    whose entries round-trip their public IDs.  Any failure raises
    :class:`StoreInconsistent` instead of returning a half-read store.
    """
    api = catalog_api()
    store_root = Path(store_root)
    pointer_path = store_root / "catalog" / "current.json"
    if not pointer_path.is_file():
        raise StoreInconsistent(f"no current pointer at {pointer_path}")
    pointer = read_json(pointer_path)
    if pointer.get("schema") != "catalog-pointer/1":
        raise StoreInconsistent(f"unknown pointer schema {pointer.get('schema')!r}")
    revision = pointer.get("dataset_revision")
    if not revision:
        raise StoreInconsistent("pointer carries no dataset_revision")
    revision_path = store_root / "catalog" / "revisions" / f"{revision}.json"
    if not revision_path.is_file():
        raise StoreInconsistent(f"pointed revision {revision!r} is not retained")
    body = revision_path.read_bytes()
    snapshot = api["CatalogSnapshot"].from_dict(json.loads(body.decode("utf-8")))
    if snapshot.dataset_revision != revision:
        raise StoreInconsistent("revision body does not carry the pointed revision id")
    recomputed = api["compute_revision"](snapshot.entries)
    if recomputed != revision:
        raise StoreInconsistent(
            f"revision body hash mismatch: recomputed {recomputed!r} != {revision!r}")
    for entry in snapshot.entries:
        derived = api["canonical"].public_id(api["EntityKind"].coerce(entry.kind),
                                             entry.identity_fields)
        if derived != entry.public_id:
            raise StoreInconsistent(f"entry {entry.public_id} does not round-trip its identity")
    return {
        "pointer": pointer,
        "pointer_sha256": sha256_file(pointer_path),
        "revision": revision,
        "revision_path": str(revision_path),
        "revision_sha256": sha256_bytes(body),
        "revision_bytes": len(body),
        "snapshot": snapshot,
        "entries": {entry.public_id: entry for entry in snapshot.entries},
    }


def entry_digest(entry: Any) -> str:
    return entry.content_hash()
