#!/usr/bin/env python
"""W5 migration: inventory a source store, copy it, publish the catalog, or run all.

The migration follows the documented data layout (integration guide section 6,
A09 store decision) while keeping authorities separate.  Nothing here reads an
original project tree, a real database, a service or the network: the inputs
are the private synthetic stores under ``<run>/migration/`` and the read-only
candidate snapshot under ``<run>/candidates/closure-v1``.

What the destination looks like (everything inside it is produced by this
package, so a destination tree is fully reproducible):

======================  =====================================================
``.w5_dest_root.json``  ownership marker (written on create or empty-dir adoption)
``payload/<rel>``       byte copies of the migrated source files
``catalog/current.json``          atomic pointer (``catalog-pointer/1``)
``catalog/revisions/<rev>.json``  immutable revision bodies (candidate publisher)
======================  =====================================================

Rules that are deliberately *not* relaxed:

* a **collision on an authority-owned file is refused** (typed
  ``CollisionRefused``, exit 3) - the migration never overwrites source-owned
  bytes with different bytes; a collision on a rebuildable/derived file is
  overwritten and recorded as ``regenerated_over_rebuildable``;
* an existing identical file is an ``idempotent_skip``, so an interrupted run
  resumes without inventing differences;
* a publication is refused when the build fails (the candidate's
  ``CatalogBuilder`` returns ``ok=False``): nothing is published and the current
  pointer is untouched (exit 4);
* an injected fault never publishes: a half-copied destination stops before the
  build and a failure injected before the pointer swap stops after the build -
  in either case the current pointer is untouched and the run resumes
  idempotently;
* manual decisions are preserved byte-for-byte *and* surfaced: a decision whose
  ``subject_public_id`` matches an entry is attached as
  ``lineage["manual_decision"]``, which is exactly the traceability a
  ``manual_adjudicated`` claim requires under ``trust/1``;
* ``observed/run-checkpoint.json`` is observed read-only and is **not**
  migrated.

Usage / exit codes (identical for every tool in this package):

    0 ok | 1 error | 2 refusal (bad target) | 3 collision refused
    4 publication refused | 5 injected fault | 8 reconciliation findings

    python migrate.py inventory --source S --out FILE
    python migrate.py copy --source S --dest D [--manifest-out FILE]
                          [--fail-after-copies N]
    python migrate.py publish --source S --dest D [--select-scope all|mvp]
                          [--expect-current any|none|REVISION]
                          [--fail-before-pointer-swap]
    python migrate.py run --source S --dest D --manifest-dir DIR
                          [--fail-after-copies N] [--fail-before-pointer-swap]
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import w5_common as w5  # noqa: E402

DEST_MARKER_NAME = ".w5_dest_root.json"
DEST_MARKER_SCHEMA = "w5.dest-root-marker/1"

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_REFUSAL = 2
EXIT_COLLISION = 3
EXIT_PUBLISH_REFUSED = 4
EXIT_INJECTED = 5
EXIT_FINDINGS = 8

#: role -> whether the edge maps onto a catalog ``container_ref`` field.
CONTAINER_ROLES = ("in_container", "asset_of", "region_of")

#: Per-file-class conflict policy.  ``refuse`` protects authority-owned and
#: integration-owned records; ``overwrite`` is reserved for artifacts whose
#: owner documents them as rebuildable/derived; ``skip`` never migrates.
CLASS_POLICY: dict[str, str] = {
    "authority": "refuse",
    "integration": "refuse",
    "rebuildable": "overwrite",
    "derived": "overwrite",
    "read_only_observed": "skip",
    "tooling": "skip",
}


class CollisionRefused(Exception):
    """A destination file differs and its owner class forbids overwriting it."""

    def __init__(self, rel: str, reason: str) -> None:
        super().__init__(reason)
        self.rel = rel
        self.reason = reason


# --------------------------------------------------------------------------- #
# classification and inventory
# --------------------------------------------------------------------------- #
def classify(rel: str) -> dict[str, str]:
    """Class, authority and conflict policy of one source-relative path."""
    if rel.startswith("raw/"):
        klass = "authority"
    elif rel.startswith("assets/"):
        klass = "authority"
    elif rel.startswith("decisions/"):
        klass = "authority"
    elif rel.startswith("caches/"):
        klass = "rebuildable"
    elif rel == "index/aggregate-index.db":
        klass = "integration"
    elif rel == "index/aggregate-index.json":
        klass = "derived"
    elif rel in ("ownership.json", "provenance/PROVENANCE.json"):
        klass = "integration"
    elif rel.startswith("observed/"):
        klass = "read_only_observed"
    elif rel.startswith("."):
        klass = "tooling"
    else:
        raise ValueError(f"unclassified source path {rel!r}")
    return {"class": klass, "policy": CLASS_POLICY[klass],
            "authority": ("source" if rel.startswith(("raw/", "assets/", "caches/", "decisions/"))
                          else "integration")}


def load_index(source_root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """The source aggregate index rows and refs, read-only."""
    conn = sqlite3.connect(Path(source_root) / "index" / "aggregate-index.db")
    try:
        conn.row_factory = sqlite3.Row
        rows = [dict(r) for r in conn.execute("SELECT * FROM entities ORDER BY public_id")]
        refs = [dict(r) for r in conn.execute("SELECT * FROM refs ORDER BY ord")]
    finally:
        conn.close()
    return rows, refs


def file_links(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """For every payload path a source-relative path, the entities that point at it."""
    links: dict[str, dict[str, Any]] = {}
    for row in rows:
        for field in ("raw_path", "document_path"):
            rel = row.get(field)
            if not rel:
                continue
            entry = links.setdefault(rel, {"entity_ids": [], "asset_public_ids": []})
            if row["entity_id"] not in entry["entity_ids"]:
                entry["entity_ids"].append(row["entity_id"])
            if row["kind"] == "asset" and row["public_id"] not in entry["asset_public_ids"]:
                entry["asset_public_ids"].append(row["public_id"])
    for entry in links.values():
        entry["entity_ids"].sort()
        entry["asset_public_ids"].sort()
    return links


def inventory_rows(source_root: Path) -> dict[str, Any]:
    """One row per source file: class, policy, hashes, entity links, dest path."""
    source_root = Path(source_root)
    rows, _ = load_index(source_root)
    links = file_links(rows)
    files: list[dict[str, Any]] = []
    for path in w5.iter_files(source_root):
        rel = path.relative_to(source_root).as_posix()
        cls = classify(rel)
        link = links.get(rel, {"entity_ids": [], "asset_public_ids": []})
        files.append({
            "path": rel,
            "dest_path": (f"payload/{rel}" if cls["policy"] != "skip" else None),
            "sha256": w5.sha256_file(path),
            "size": path.stat().st_size,
            "class": cls["class"],
            "authority": cls["authority"],
            "policy": cls["policy"],
            "evidence_label": "synthetic_fixture",
            "entity_ids": link["entity_ids"],
            "asset_public_ids": link["asset_public_ids"],
        })
    files.sort(key=lambda r: r["path"])
    by_class: dict[str, int] = {}
    total_bytes = 0
    for row in files:
        by_class[row["class"]] = by_class.get(row["class"], 0) + 1
        total_bytes += row["size"]
    return {
        "files": files,
        "summary": {"file_count": len(files), "total_bytes": total_bytes,
                    "by_class": dict(sorted(by_class.items()))},
    }


def cmd_inventory(args: argparse.Namespace) -> int:
    source_root = Path(args.source)
    inv = inventory_rows(source_root)
    payload = {
        "schema": "w5.source-inventory/1",
        "source_root": str(source_root),
        "digests": w5.both_digests(source_root),
        "files": inv["files"],
        "summary": inv["summary"],
        "not_migrated": [r["path"] for r in inv["files"] if r["policy"] == "skip"],
    }
    w5.write_json(args.out, payload)
    w5.dump({"schema": payload["schema"], "files": payload["summary"]["file_count"],
             "by_class": payload["summary"]["by_class"],
             "digests": {k: v["sha256"] for k, v in payload["digests"].items()},
             "not_migrated": payload["not_migrated"], "out": str(args.out)})
    return EXIT_OK


# --------------------------------------------------------------------------- #
# source -> catalog sources
# --------------------------------------------------------------------------- #
def build_sources(source_root: Path, *, select_scope: str = "all") -> dict[str, Any]:
    """Construct candidate ``CatalogSource`` objects from the source index.

    The mapping is explicit and deterministic:

    * identity and locator are decoded from the persisted JSON (the
      ``__unknown__`` token becomes the ``UNKNOWN`` sentinel again);
    * refs with roles ``in_container`` / ``asset_of`` / ``region_of`` wire the
      target into ``container_ref`` (a source with several distinct targets is
      ambiguous and records a status instead of guessing);
    * a preserved manual decision whose ``subject_public_id`` matches the
      entry's public ID is surfaced as ``lineage["manual_decision"]``;
    * ``--select-scope mvp`` keeps only rows whose index scope is ``mvp``.
    """
    api = w5.catalog_api()
    CatalogSource = api["CatalogSource"]
    canonical = api["canonical"]
    decode_unknown = api["decode_unknown"]
    EntityKind = api["EntityKind"]

    source_root = Path(source_root)
    rows, refs = load_index(source_root)
    decisions = w5.read_json(source_root / "decisions" / "manual-decisions.json")

    derived_pids: set[str] = set()
    decoded_by_pid: dict[str, Any] = {}
    kind_by_pid: dict[str, Any] = {}
    for row in rows:
        decoded = decode_unknown(json.loads(row["identity_json"]))
        try:
            derived = canonical.public_id(EntityKind.coerce(row["kind"]), decoded)
        except (KeyError, TypeError, ValueError):
            continue
        derived_pids.add(derived)
        decoded_by_pid[row["public_id"]] = decoded
        kind_by_pid[row["public_id"]] = row["kind"]

    refs_by_from: dict[str, list[dict[str, Any]]] = {}
    for ref in refs:
        refs_by_from.setdefault(ref["from_public_id"], []).append(ref)

    decisions_by_subject: dict[str, list[dict[str, Any]]] = {}
    for decision in decisions["decisions"]:
        decisions_by_subject.setdefault(decision["subject_public_id"], []).append(decision)

    sources: list[Any] = []
    statuses: list[dict[str, Any]] = []
    for row in rows:
        pid = row["public_id"]
        decoded = decode_unknown(json.loads(row["identity_json"]))
        status: dict[str, Any] = {
            "entity_id": row["entity_id"],
            "recorded_public_id": pid,
            "kind": row["kind"],
            "system": row["system"],
            "scope": row["scope"],
            "identity_valid": True,
            "identity_problem": None,
            "container_refs": [],
            "unresolved_refs": [],
            "in_selected_scope": select_scope == "all" or row["scope"] == select_scope,
        }
        try:
            canonical.canonical_identity_string(EntityKind.coerce(row["kind"]), decoded)
            derived = canonical.public_id(EntityKind.coerce(row["kind"]), decoded)
        except (KeyError, TypeError, ValueError) as exc:
            status["identity_valid"] = False
            status["identity_problem"] = f"{type(exc).__name__}: {exc}"
            status["expected_in_catalog"] = False
            statuses.append(status)
            continue
        status["derived_public_id"] = derived
        status["recorded_id_matches_derived"] = derived == pid
        row_refs = [r for r in refs_by_from.get(pid, []) if r["role"] in CONTAINER_ROLES]
        targets = sorted({r["to_public_id"] for r in row_refs})
        status["container_refs"] = targets
        status["unresolved_refs"] = sorted(t for t in targets if t not in derived_pids)
        status["expected_in_catalog"] = (
            status["in_selected_scope"] and not status["unresolved_refs"])
        statuses.append(status)
        if not status["in_selected_scope"]:
            continue
        container_ref = targets[0] if len(targets) == 1 else None
        status["ambiguous_container_ref"] = len(targets) > 1
        matched = sorted(decisions_by_subject.get(pid, []), key=lambda d: d["decision_id"])
        lineage = ({"manual_decision": dict(matched[0])} if matched else None)
        sources.append(CatalogSource(
            kind=row["kind"],
            system=row["system"],
            identity_fields=decoded,
            native_locator=decode_unknown(json.loads(row["locator_json"])),
            container_ref=container_ref,
            source_revision=row["source_revision"],
            quality_summary=json.loads(row["quality_json"]) or {},
            content_class=row["content_class"],
            evidence_labels=(row["evidence_labels"].split(",") if row["evidence_labels"] else []),
            lineage=lineage,
            content_revision=row["content_revision"],
        ))
    return {"sources": sources, "statuses": statuses, "rows": rows, "refs": refs,
            "decisions": decisions,
            "index_records": {"entities": len(rows), "refs": len(refs),
                              "decisions": len(decisions["decisions"])}}


def input_revisions(source_root: Path) -> dict[str, Any]:
    source_root = Path(source_root)
    digests = w5.both_digests(source_root)
    return {
        "source_index_sha256": w5.sha256_file(source_root / "index" / "aggregate-index.db"),
        "source_tree_historical": digests["historical"]["sha256"],
        "source_tree_posix_v1": digests["posix_v1"]["sha256"],
    }


def build_catalog(source_root: Path, *, select_scope: str = "all") -> dict[str, Any]:
    api = w5.catalog_api()
    built = build_sources(source_root, select_scope=select_scope)
    result = api["CatalogBuilder"]().build(
        built["sources"], input_revisions=input_revisions(source_root),
        created_at=w5.FIXED_NOW)
    return {**built, "result": result}


# --------------------------------------------------------------------------- #
# copy
# --------------------------------------------------------------------------- #
def ensure_dest(dest_root: Path) -> str:
    """Create or adopt the destination root; refuse a foreign non-empty tree."""
    dest_root = Path(dest_root)
    marker = dest_root / DEST_MARKER_NAME

    def claim() -> None:
        w5.write_json(marker, {
            "schema": DEST_MARKER_SCHEMA,
            "created_by": "migration/tools/migrate.py",
            "note": "ownership marker; a destination without it is never written to",
        })

    if dest_root.exists():
        if not dest_root.is_dir():
            raise SystemExit(f"refusing: destination {dest_root} is not a directory")
        if marker.is_file() and w5.read_json(marker).get("schema") == DEST_MARKER_SCHEMA:
            return "adopted"
        foreign = [p for p in dest_root.rglob("*") if p.is_file()]
        if foreign:
            raise SystemExit(
                f"refusing: destination {dest_root} is non-empty and carries no "
                f"{DEST_MARKER_NAME} marker")
        # adopting an existing empty directory claims it too: without the marker
        # an interrupted first copy would leave files this tool refuses to resume
        claim()
        return "adopted_empty"
    dest_root.mkdir(parents=True)
    claim()
    return "created"


def copy_payload(source_root: Path, dest_root: Path, *,
                 manifest_out: Path | None = None,
                 fail_after_copies: int | None = None) -> dict[str, Any]:
    """Copy every migratable file; refuse (never overwrite) an authority collision."""
    source_root = Path(source_root)
    dest_root = Path(dest_root)
    adopted = ensure_dest(dest_root)
    inv = inventory_rows(source_root)
    rows: list[dict[str, Any]] = []
    copied = 0
    aborted = False
    collision: dict[str, Any] | None = None
    for row in inv["files"]:
        if row["policy"] == "skip":
            row["outcome"] = "skipped_not_migrated"
            rows.append(row)
            continue
        if collision is not None:
            row["outcome"] = "aborted_after_collision"
            rows.append(row)
            continue
        if aborted:
            row["outcome"] = "aborted_not_attempted"
            rows.append(row)
            continue
        src = source_root / row["path"]
        dst = dest_root / row["dest_path"]
        data = src.read_bytes()
        if dst.is_file():
            same = w5.sha256_bytes(dst.read_bytes()) == row["sha256"]
            if same:
                row["outcome"] = "idempotent_skip"
            elif row["policy"] == "refuse":
                row["outcome"] = "collision_refused"
                collision = {"path": row["path"],
                             "detail": ("destination differs and its owner class forbids "
                                        "overwriting it")}
                rows.append(row)
                continue
            else:
                dst.write_bytes(data)
                row["outcome"] = "regenerated_over_rebuildable"
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(data)
            row["outcome"] = "copied"
            copied += 1
        rows.append(row)
        if fail_after_copies is not None and copied >= fail_after_copies:
            aborted = True
    manifest = {
        "schema": "w5.copy-manifest/1",
        "source_root": str(source_root),
        "dest_root": str(dest_root),
        "adopted": adopted,
        "source_digests": w5.both_digests(source_root),
        "rows": rows,
        "summary": {
            "rows": len(rows),
            "copied": sum(1 for r in rows if r["outcome"] == "copied"),
            "idempotent_skip": sum(1 for r in rows if r["outcome"] == "idempotent_skip"),
            "regenerated_over_rebuildable": sum(
                1 for r in rows if r["outcome"] == "regenerated_over_rebuildable"),
            "skipped_not_migrated": sum(
                1 for r in rows if r["outcome"] == "skipped_not_migrated"),
            "collision_refused": sum(1 for r in rows if r["outcome"] == "collision_refused"),
            "aborted": sum(1 for r in rows if r["outcome"].startswith("aborted")),
        },
    }
    if manifest_out is not None:
        w5.write_json(manifest_out, manifest)
    status = "ok"
    exit_code = EXIT_OK
    if collision is not None:
        status = "collision_refused"
        exit_code = EXIT_COLLISION
    elif aborted:
        status = "injected_fault"
        exit_code = EXIT_INJECTED
    return {"manifest": manifest, "status": status, "exit_code": exit_code,
            "collision": collision, "copied": copied}


def cmd_copy(args: argparse.Namespace) -> int:
    result = copy_payload(Path(args.source), Path(args.dest),
                          manifest_out=(Path(args.manifest_out) if args.manifest_out else None),
                          fail_after_copies=args.fail_after_copies)
    outcome = {
        "status": result["status"],
        "dest_root": str(Path(args.dest)),
        "summary": result["manifest"]["summary"],
    }
    if result["collision"] is not None:
        outcome["collision"] = result["collision"]
        outcome["detail"] = ("refused to overwrite a differing authority-owned file; the "
                             "destination keeps the bytes it has")
    if result["status"] == "injected_fault":
        outcome["detail"] = f"injected fault: stopped after {result['copied']} copied files"
    w5.dump(outcome)
    return result["exit_code"]


# --------------------------------------------------------------------------- #
# publish
# --------------------------------------------------------------------------- #
def publish_catalog(source_root: Path, dest_root: Path, *,
                    select_scope: str = "all",
                    expect_current: str = "any",
                    fail_before_pointer_swap: bool = False,
                    now: str = w5.FIXED_NOW) -> dict[str, Any]:
    """Build the catalog from the source index and publish it behind the pointer."""
    built = build_catalog(source_root, select_scope=select_scope)
    return publish_built_catalog(
        built, source_root, dest_root, select_scope=select_scope,
        expect_current=expect_current,
        fail_before_pointer_swap=fail_before_pointer_swap, now=now)


def publish_built_catalog(built: dict[str, Any], source_root: Path, dest_root: Path, *,
                          select_scope: str = "all",
                          expect_current: str = "any",
                          fail_before_pointer_swap: bool = False,
                          now: str = w5.FIXED_NOW) -> dict[str, Any]:
    """Publish an already-built catalog behind the pointer.

    ``expect_current`` is ``"any"``, ``"none"`` (the builder observed *no*
    current pointer), or a dataset revision for a compare-and-swap publish.
    """
    api = w5.catalog_api()
    source_root = Path(source_root)
    dest_root = Path(dest_root)
    result = built["result"]
    info: dict[str, Any] = {
        "select_scope": select_scope,
        "expect_current": expect_current,
        "build_ok": result.ok,
        "candidate_revision": result.candidate_revision,
        "counts": result.counts,
        "diff": result.diff,
        "problems": result.problems,
        "index_records": built["index_records"],
        "statuses": built["statuses"],
    }
    if not result.ok:
        info.update({"status": "build_failed", "published": False,
                     "exit_code": EXIT_PUBLISH_REFUSED,
                     "detail": "the build did not pass validation; nothing was published "
                               "and the current pointer is untouched"})
        return info
    if fail_before_pointer_swap:
        info.update({"status": "injected_fault", "published": False,
                     "exit_code": EXIT_INJECTED,
                     "detail": "injected fault before the pointer swap: the built snapshot "
                               "was deliberately not published"})
        return info
    publisher = api["RevisionPublisher"](dest_root / "catalog")
    expected = (api["ANY_CURRENT"] if expect_current == "any"
                else None if expect_current == "none" else expect_current)
    try:
        pointer = publisher.publish(result.snapshot, expected_current=expected, now=now)
    except api["StalePublisherError"] as exc:
        info.update({"status": "stale", "published": False,
                     "exit_code": EXIT_PUBLISH_REFUSED, "detail": str(exc)})
        return info
    except api["PublicationRejected"] as exc:
        info.update({"status": "publication_rejected", "published": False,
                     "exit_code": EXIT_PUBLISH_REFUSED, "detail": str(exc)})
        return info
    revision = result.snapshot.dataset_revision
    info.update({
        "status": "published",
        "published": True,
        "exit_code": EXIT_OK,
        "pointer": pointer,
        "pointer_sha256": w5.sha256_file(publisher.pointer_path),
        "revision_path": f"catalog/revisions/{revision}.json",
        "revision_sha256": w5.sha256_file(publisher.revision_path(revision)),
    })
    return info


def cmd_publish(args: argparse.Namespace) -> int:
    info = publish_catalog(Path(args.source), Path(args.dest),
                           select_scope=args.select_scope,
                           expect_current=args.expect_current,
                           fail_before_pointer_swap=args.fail_before_pointer_swap)
    w5.dump({k: v for k, v in info.items() if k not in ("statuses",)})
    return info["exit_code"]


# --------------------------------------------------------------------------- #
# query evidence (the fixed query set a restore must reproduce)
# --------------------------------------------------------------------------- #
def query_evidence(dest_root: Path) -> dict[str, Any]:
    """The fixed query set over a published destination, as comparable evidence."""
    api = w5.catalog_api()
    dest_root = Path(dest_root)
    encode_unknown = api["encode_unknown"]
    store = w5.read_consistent_store(dest_root)
    entries = [store["entries"][pid] for pid in sorted(store["entries"])]
    counts: dict[str, int] = {}
    by_system: dict[str, int] = {}
    for entry in entries:
        counts[entry.kind] = counts.get(entry.kind, 0) + 1
        by_system[entry.system] = by_system.get(entry.system, 0) + 1
    fingerprint = [{
        "public_id": e.public_id,
        "kind": e.kind,
        "system": e.system,
        "content_hash": e.content_hash(),
        "native_locator": encode_unknown(dict(e.native_locator)),
    } for e in entries]
    flagged = [{"code": p.get("code"), "scope": p.get("scope"), "ref": p.get("ref"),
                "detail": p.get("detail")} for p in store["snapshot"].problems]
    asset_claims = {e.public_id: e.identity_fields["sha256"]
                    for e in entries if e.kind == "asset"}
    manual = {e.public_id: encode_unknown(e.lineage) for e in entries if e.lineage}
    payload = dest_root / "payload"
    provenance = w5.read_json(payload / "provenance" / "PROVENANCE.json")
    decisions = w5.read_json(payload / "decisions" / "manual-decisions.json")
    conn = sqlite3.connect(payload / "index" / "aggregate-index.db")
    try:
        scope_counts = {str(scope): int(count) for scope, count in conn.execute(
            "SELECT scope, COUNT(*) FROM entities GROUP BY scope ORDER BY scope")}
        kind_counts = {str(kind): int(count) for kind, count in conn.execute(
            "SELECT kind, COUNT(*) FROM entities GROUP BY kind ORDER BY kind")}
    finally:
        conn.close()
    queries = [
        {"id": "dataset_revision", "result": store["revision"]},
        {"id": "counts_by_kind", "result": dict(sorted(counts.items()))},
        {"id": "counts_by_system", "result": dict(sorted(by_system.items()))},
        {"id": "flagged", "result": flagged},
        {"id": "asset_sha256_claims", "result": dict(sorted(asset_claims.items()))},
        {"id": "manual_decision_lineage", "result": dict(sorted(manual.items()))},
        {"id": "payload_index_scope_counts", "result": scope_counts},
        {"id": "payload_index_kind_counts", "result": kind_counts},
        {"id": "decisions_file_sha256", "result": w5.sha256_file(
            payload / "decisions" / "manual-decisions.json")},
        {"id": "decisions_count", "result": len(decisions["decisions"])},
        {"id": "provenance_file_sha256", "result": w5.sha256_file(
            payload / "provenance" / "PROVENANCE.json")},
        {"id": "provenance_entries", "result": len(provenance["entries"])},
        {"id": "payload_index_db_sha256", "result": w5.sha256_file(
            payload / "index" / "aggregate-index.db")},
    ]
    return {
        "schema": "w5.query-evidence/1",
        "dest_root": str(dest_root),
        "dataset_revision": store["revision"],
        "pointer_sha256": store["pointer_sha256"],
        "revision_sha256": store["revision_sha256"],
        "counts": {"total": len(entries), **dict(sorted(counts.items()))},
        "fingerprint": fingerprint,
        "queries": queries,
    }


# --------------------------------------------------------------------------- #
# run: the whole sequence
# --------------------------------------------------------------------------- #
def cmd_run(args: argparse.Namespace) -> int:
    source_root = Path(args.source)
    dest_root = Path(args.dest)
    manifest_dir = Path(args.manifest_dir)
    manifest_dir.mkdir(parents=True, exist_ok=True)

    inv = inventory_rows(source_root)
    w5.write_json(manifest_dir / "inventory.json", {
        "schema": "w5.source-inventory/1",
        "source_root": str(source_root),
        "digests": w5.both_digests(source_root),
        "files": inv["files"],
        "summary": inv["summary"],
        "not_migrated": [r["path"] for r in inv["files"] if r["policy"] == "skip"],
    })

    copy_result = copy_payload(source_root, dest_root,
                               manifest_out=manifest_dir / "copy_manifest.json",
                               fail_after_copies=args.fail_after_copies)
    if copy_result["exit_code"] == EXIT_COLLISION:
        w5.dump({"status": "collision_refused",
                 "collision": copy_result["collision"],
                 "summary": copy_result["manifest"]["summary"]})
        return EXIT_COLLISION
    if copy_result["status"] == "injected_fault":
        # an interrupted copy never publishes: the pointer stays untouched and
        # no half-migrated destination ever presents a current revision
        w5.dump({"status": "injected_fault_after_partial_copy",
                 "copied": copy_result["copied"],
                 "summary": copy_result["manifest"]["summary"],
                 "published": False})
        return EXIT_INJECTED

    publish_info = publish_catalog(source_root, dest_root,
                                   select_scope=args.select_scope,
                                   fail_before_pointer_swap=args.fail_before_pointer_swap)
    w5.write_json(manifest_dir / "publish.json", {
        "schema": "w5.publish-report/1",
        **{k: v for k, v in publish_info.items() if k not in ("statuses",)},
        "row_statuses": publish_info["statuses"],
    })
    if args.fail_before_pointer_swap:
        w5.dump({"status": "injected_fault_before_pointer_swap",
                 "copied": copy_result["copied"],
                 "summary": copy_result["manifest"]["summary"],
                 "published": False})
        return EXIT_INJECTED
    if not publish_info["published"]:
        w5.dump({"status": publish_info["status"], "detail": publish_info["detail"],
                 "summary": copy_result["manifest"]["summary"]})
        return publish_info["exit_code"]

    evidence = query_evidence(dest_root)
    w5.write_json(manifest_dir / "query_evidence.json", evidence)
    w5.dump({"status": "ok",
             "source_root": str(source_root),
             "dest_root": str(dest_root),
             "summary": copy_result["manifest"]["summary"],
             "dataset_revision": evidence["dataset_revision"],
             "counts": evidence["counts"],
             "manifests": sorted(p.name for p in manifest_dir.iterdir()),
             "dest_digests": {k: v["sha256"] for k, v in w5.both_digests(dest_root).items()}})
    return EXIT_OK


# --------------------------------------------------------------------------- #
# cli
# --------------------------------------------------------------------------- #
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="command", required=True)

    p_inv = sub.add_parser("inventory", help="classify every source file; write inventory.json")
    p_inv.add_argument("--source", required=True)
    p_inv.add_argument("--out", required=True)
    p_inv.set_defaults(func=cmd_inventory)

    p_copy = sub.add_parser("copy", help="copy payload files (collision-refusing)")
    p_copy.add_argument("--source", required=True)
    p_copy.add_argument("--dest", required=True)
    p_copy.add_argument("--manifest-out", default=None)
    p_copy.add_argument("--fail-after-copies", type=int, default=None,
                        help="injected fault: stop after this many copied files (exit 5)")
    p_copy.set_defaults(func=cmd_copy)

    p_pub = sub.add_parser("publish", help="build and publish the catalog into the destination")
    p_pub.add_argument("--source", required=True)
    p_pub.add_argument("--dest", required=True)
    p_pub.add_argument("--select-scope", choices=("all", "mvp"), default="all")
    p_pub.add_argument("--expect-current", default="any",
                       help="'any', 'none' (no current pointer observed) or a dataset "
                            "revision for compare-and-swap")
    p_pub.add_argument("--fail-before-pointer-swap", action="store_true",
                       help="injected fault: build but do not publish (exit 5)")
    p_pub.set_defaults(func=cmd_publish)

    p_run = sub.add_parser("run", help="inventory + copy + publish + query evidence")
    p_run.add_argument("--source", required=True)
    p_run.add_argument("--dest", required=True)
    p_run.add_argument("--manifest-dir", required=True)
    p_run.add_argument("--select-scope", choices=("all", "mvp"), default="all")
    p_run.add_argument("--fail-after-copies", type=int, default=None)
    p_run.add_argument("--fail-before-pointer-swap", action="store_true")
    p_run.set_defaults(func=cmd_run)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
