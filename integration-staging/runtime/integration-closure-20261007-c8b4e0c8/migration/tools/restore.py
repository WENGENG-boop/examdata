#!/usr/bin/env python
"""W5 restore: pointer rollback, content restore, SQLite export/restore, probes.

Subcommands:

``pointer-rollback``
    Point the store's ``current.json`` back at the retained previous revision
    (the candidate publisher's own atomic rollback) and re-read the store to prove
    the rolled-back view is complete and consistent.

``content-restore``
    Rebuild a destination from scratch out of the source store plus the copy
    manifest: every manifest row is copied from the source after its sha256 is
    re-checked, the catalog is republished (fixed timestamp), and the restored
    tree and its recomputed query evidence are compared with the reference
    destination - content, hashes and queries must all match.

``sqlite-restore``
    Export the synthetic aggregate index with ``sqlite3.Connection.backup()`` and
    restore it into a fresh database; assert ``PRAGMA integrity_check``, schema
    text and row-content digests on all three copies.  Byte equality is *not*
    asserted for the restored copy: SQLite files are not byte-deterministic, so
    the equivalence criterion is integrity + schema + rows.

``bare-copy-probe``
    Demonstrate with a private scratch database that copying a live ``.db`` file
    alone (without its write-ahead log) can miss committed rows, while
    ``backup()`` from the open connection captures them.  This is why a bare copy
    of a live database is not a valid backup.

``tamper-probe``
    Copy a good destination and tamper with it twice: (v1) edit a revision body
    while keeping its file name - the revision recomputation must catch it; (v2)
    swap two entries' public IDs, rename the revision to the recomputed value and
    update the pointer - file names are self-consistent, so only the per-entry
    identity round-trip catches it.  The original store is never modified (its
    digests are re-asserted before and after).

``poke``
    Overwrite one private working file with exact bytes (used to inject the
    collision scenario); refuses any path outside ``<run>/migration``.

Exit codes: ``0`` ok | ``1`` error | ``2`` refusal | ``3`` collision refused
| ``4`` publication refused | ``5`` injected fault | ``8`` findings.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import w5_common as w5  # noqa: E402
import migrate  # noqa: E402

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_REFUSAL = 2
EXIT_FINDINGS = 8


# --------------------------------------------------------------------------- #
# small shared helpers
# --------------------------------------------------------------------------- #
def _file_map(root: Path) -> dict[str, str]:
    root = Path(root)
    return {p.relative_to(root).as_posix(): w5.sha256_file(p) for p in w5.iter_files(root)}


def _compare_trees(a: Path, b: Path) -> dict[str, Any]:
    map_a, map_b = _file_map(a), _file_map(b)
    only_a = sorted(set(map_a) - set(map_b))
    only_b = sorted(set(map_b) - set(map_a))
    differing = [{"path": rel, "sha_a": map_a[rel], "sha_b": map_b[rel]}
                 for rel in sorted(set(map_a) & set(map_b)) if map_a[rel] != map_b[rel]]
    digests = {"a": w5.both_digests(a), "b": w5.both_digests(b)}
    return {"equal": not only_a and not only_b and not differing,
            "files_a": len(map_a), "files_b": len(map_b),
            "only_in_a": only_a, "only_in_b": only_b, "differing": differing,
            "digests": {k: {o: v[o]["sha256"] for o in ("historical", "posix_v1")}
                        for k, v in digests.items()}}


def _evidence_diff(a: dict[str, Any], b: dict[str, Any],
                   ignore: tuple[str, ...] = ("dest_root",)) -> list[str]:
    return [k for k in sorted(set(a) | set(b))
            if k not in ignore and a.get(k) != b.get(k)]


# --------------------------------------------------------------------------- #
# pointer-rollback
# --------------------------------------------------------------------------- #
def cmd_pointer_rollback(args: argparse.Namespace) -> int:
    store = Path(args.store)
    api = w5.catalog_api()
    before = w5.read_consistent_store(store)
    old_current = before["revision"]
    old_previous = before["pointer"].get("previous")
    revisions_dir = store / "catalog" / "revisions"
    sha_before = {rev: w5.sha256_file(revisions_dir / f"{rev}.json")
                  for rev in (old_current, old_previous) if rev}
    publisher = api["RevisionPublisher"](store / "catalog")
    try:
        pointer = publisher.rollback(now=w5.FIXED_NOW)
    except Exception as exc:  # noqa: BLE001 - every rollback failure is reported
        w5.dump({"schema": "w5.pointer-rollback/1", "store": str(store), "ok": False,
                 "error": f"{type(exc).__name__}: {exc}"})
        return EXIT_ERROR
    after = w5.read_consistent_store(store)
    sha_after = {rev: w5.sha256_file(revisions_dir / f"{rev}.json")
                 for rev in (after["revision"], after["pointer"].get("previous")) if rev}
    checks = [
        {"id": "current_is_previous",
         "ok": after["revision"] == old_previous,
         "detail": f"{after['revision']} == {old_previous}"},
        {"id": "previous_is_old_current",
         "ok": after["pointer"].get("previous") == old_current,
         "detail": f"{after['pointer'].get('previous')} == {old_current}"},
        {"id": "revision_bytes_unchanged",
         "ok": all(sha_after.get(rev) == sha for rev, sha in sha_before.items()),
         "detail": f"revision bodies before={sha_before} after={sha_after}"},
        {"id": "store_consistent_after",
         "ok": True,
         "detail": f"entries of {after['revision']} round-trip their identities"},
    ]
    ok = all(c["ok"] for c in checks)
    result = {"schema": "w5.pointer-rollback/1", "store": str(store), "ok": ok,
              "pointer": pointer,
              "before": {"revision": old_current, "previous": old_previous},
              "after": {"revision": after["revision"],
                        "previous": after["pointer"].get("previous"),
                        "pointer_sha256": after["pointer_sha256"],
                        "revision_sha256": after["revision_sha256"],
                        "entries": len(after["entries"])},
              "checks": checks}
    if args.out_evidence:
        w5.write_json(args.out_evidence, migrate.query_evidence(store))
    w5.dump(result)
    return EXIT_OK if ok else EXIT_FINDINGS


# --------------------------------------------------------------------------- #
# content-restore
# --------------------------------------------------------------------------- #
def cmd_content_restore(args: argparse.Namespace) -> int:
    source, dest, reference = Path(args.source), Path(args.dest), Path(args.reference)
    manifest = w5.read_json(args.manifest)
    if manifest.get("schema") != "w5.copy-manifest/1":
        w5.dump({"schema": "w5.content-restore/1", "ok": False,
                 "error": f"unexpected manifest schema {manifest.get('schema')!r}"})
        return EXIT_ERROR
    adopted = migrate.ensure_dest(dest)
    drift: list[dict[str, Any]] = []
    restored = identical = 0
    rows_seen = 0
    for row in manifest["rows"]:
        if not row.get("dest_path"):
            continue
        rows_seen += 1
        src_file = source / row["path"]
        if not src_file.is_file():
            drift.append({"path": row["path"], "reason": "source file missing"})
            continue
        data = src_file.read_bytes()
        actual = w5.sha256_bytes(data)
        if actual != row["sha256"]:
            drift.append({"path": row["path"], "reason": "source bytes differ from the manifest",
                          "manifest_sha256": row["sha256"], "actual_sha256": actual})
            continue
        target = dest / row["dest_path"]
        if target.is_file() and target.read_bytes() == data:
            identical += 1
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        restored += 1
    if drift:
        w5.dump({"schema": "w5.content-restore/1", "ok": False,
                 "stage": "copy", "adopted": adopted, "drift": drift})
        return EXIT_ERROR
    published = migrate.publish_catalog(source, dest, now=w5.FIXED_NOW)
    if not published.get("published"):
        w5.dump({"schema": "w5.content-restore/1", "ok": False, "stage": "publish",
                 "adopted": adopted, "publish": {k: v for k, v in published.items()
                                                 if k != "statuses"}})
        return published.get("exit_code", EXIT_ERROR)
    tree = _compare_trees(dest, reference)
    live_evidence = migrate.query_evidence(dest)
    reference_evidence = migrate.query_evidence(reference)
    differing = _evidence_diff(live_evidence, reference_evidence)
    ok = tree["equal"] and not differing
    result = {
        "schema": "w5.content-restore/1",
        "ok": ok,
        "adopted": adopted,
        "restored_files": restored,
        "already_identical": identical,
        "manifest_rows": rows_seen,
        "publish": {"status": published["status"],
                    "dataset_revision": published["candidate_revision"],
                    "pointer_sha256": published.get("pointer_sha256")},
        "tree": tree,
        "query_evidence_equal": not differing,
        "query_evidence_differing_keys": differing,
    }
    if args.out_evidence:
        w5.write_json(args.out_evidence, live_evidence)
    w5.dump({k: v for k, v in result.items() if k != "tree"}
            | {"tree": {k: v for k, v in tree.items() if k != "differing"}})
    return EXIT_OK if ok else EXIT_FINDINGS


# --------------------------------------------------------------------------- #
# sqlite export / restore
# --------------------------------------------------------------------------- #
def _sqlite_connect_ro(path: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{Path(path).as_posix()}?mode=ro", uri=True)


def _sqlite_integrity(conn: sqlite3.Connection) -> list[str]:
    return [row[0] for row in conn.execute("PRAGMA integrity_check")]


def _cell(value: Any) -> Any:
    if isinstance(value, bytes):
        return {"hex": value.hex()}
    if isinstance(value, (int, float, str)) or value is None:
        return value
    return {"repr": repr(value)}


def _sqlite_content_digest(conn: sqlite3.Connection) -> dict[str, Any]:
    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' "
        "ORDER BY name")]
    payload: dict[str, Any] = {}
    counts: dict[str, int] = {}
    total = 0
    for table in tables:
        rows = [[_cell(v) for v in row] for row in conn.execute(f'SELECT * FROM "{table}"')]
        rows.sort(key=lambda r: json.dumps(r, ensure_ascii=False, sort_keys=True))
        payload[table] = rows
        counts[table] = len(rows)
        total += len(rows)
    blob = json.dumps(payload, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")
    return {"sha256": w5.sha256_bytes(blob), "tables": counts, "rows_total": total}


def _sqlite_schema_text(conn: sqlite3.Connection) -> str:
    rows = conn.execute(
        "SELECT type, name, sql FROM sqlite_master WHERE sql IS NOT NULL "
        "ORDER BY type, name").fetchall()
    return "\n".join(f"{t}|{n}|{sql}" for t, n, sql in rows)


def _sqlite_summary(path: Path, *, ro: bool = True) -> dict[str, Any]:
    conn = _sqlite_connect_ro(path) if ro else sqlite3.connect(path)
    try:
        integrity = _sqlite_integrity(conn)
        content = _sqlite_content_digest(conn)
        schema = _sqlite_schema_text(conn)
        return {"path": str(path), "bytes": path.stat().st_size,
                "integrity_check": integrity,
                "integrity_ok": integrity == ["ok"],
                "schema_sha256": w5.sha256_bytes(schema.encode("utf-8")),
                "content_sha256": content["sha256"],
                "tables": content["tables"], "rows_total": content["rows_total"]}
    finally:
        conn.close()


def cmd_sqlite_restore(args: argparse.Namespace) -> int:
    source_db = Path(args.db)
    export_dir = w5.guard_within(args.export, w5.MIGRATION_ROOT)
    restore_dir = w5.guard_within(args.restore, w5.MIGRATION_ROOT)
    export_dir.mkdir(parents=True, exist_ok=True)
    restore_dir.mkdir(parents=True, exist_ok=True)
    export_db = export_dir / "aggregate-index-export.db"
    restore_db = restore_dir / "aggregate-index-restored.db"
    for target in (export_db, restore_db):
        if target.exists():
            target.unlink()

    # export: a consistent snapshot of the open source database (backup API)
    src = _sqlite_connect_ro(source_db)
    try:
        mid = sqlite3.connect(export_db)
        try:
            src.backup(mid)
        finally:
            mid.close()
    finally:
        src.close()
    # restore: the export, restored into a fresh database with the same API
    mid = _sqlite_connect_ro(export_db)
    try:
        dst = sqlite3.connect(restore_db)
        try:
            mid.backup(dst)
        finally:
            dst.close()
    finally:
        mid.close()

    summaries = {"source": _sqlite_summary(source_db),
                 "export": _sqlite_summary(export_db),
                 "restored": _sqlite_summary(restore_db)}
    export_bytes_equal_source = export_db.read_bytes() == source_db.read_bytes()
    restored_bytes_equal_export = restore_db.read_bytes() == export_db.read_bytes()
    checks = []
    for name, summary in summaries.items():
        checks.append({"id": f"{name}_integrity", "ok": summary["integrity_ok"],
                       "detail": str(summary["integrity_check"])})
    checks.append({"id": "schema_equal",
                   "ok": len({s["schema_sha256"] for s in summaries.values()}) == 1,
                   "detail": {k: v["schema_sha256"] for k, v in summaries.items()}})
    checks.append({"id": "content_equal",
                   "ok": len({s["content_sha256"] for s in summaries.values()}) == 1,
                   "detail": {k: v["content_sha256"] for k, v in summaries.items()}})
    ok = all(c["ok"] for c in checks)
    w5.dump({"schema": "w5.sqlite-restore/1", "ok": ok,
             "note": "byte equality is deliberately not the criterion: SQLite files are not "
                     "byte-deterministic; equivalence = integrity_check + schema + row content",
             "byte_equality": {"export_equals_source": export_bytes_equal_source,
                               "restored_equals_export": restored_bytes_equal_export},
             "summaries": summaries, "checks": checks})
    return EXIT_OK if ok else EXIT_FINDINGS


# --------------------------------------------------------------------------- #
# bare-copy probe
# --------------------------------------------------------------------------- #
def _count_probe_rows(path: Path) -> dict[str, Any]:
    try:
        conn = sqlite3.connect(path)
    except sqlite3.Error as exc:
        return {"readable": False, "error": str(exc), "rows": None}
    try:
        try:
            (count,) = conn.execute("SELECT COUNT(*) FROM probe").fetchone()
            return {"readable": True, "error": None, "rows": int(count)}
        except sqlite3.Error as exc:
            return {"readable": True, "error": str(exc), "rows": None}
    finally:
        conn.close()


def cmd_bare_copy_probe(args: argparse.Namespace) -> int:
    work = w5.guard_within(args.work, w5.MIGRATION_ROOT)
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    live_db = work / "live-wal.db"
    wal_path = live_db.with_name(live_db.name + "-wal")
    bare_before = work / "bare-copy-while-open.db"
    bare_after = work / "bare-copy-after-close.db"
    export = work / "backup-export.db"

    conn = sqlite3.connect(live_db)
    try:
        mode = conn.execute("PRAGMA journal_mode=WAL").fetchone()[0]
        conn.execute("CREATE TABLE probe(seq INTEGER PRIMARY KEY, label TEXT NOT NULL)")
        conn.execute("INSERT INTO probe(seq, label) VALUES (1, 'committed-row')")
        conn.commit()
        wal_bytes = wal_path.stat().st_size if wal_path.exists() else 0
        bare_before.write_bytes(live_db.read_bytes())
        dst = sqlite3.connect(export)
        try:
            conn.backup(dst)
        finally:
            dst.close()
    finally:
        conn.close()
    bare_after.write_bytes(live_db.read_bytes())

    bare_before_rows = _count_probe_rows(bare_before)
    backup_rows = _count_probe_rows(export)
    bare_after_rows = _count_probe_rows(bare_after)
    export_summary = _sqlite_summary(export)
    demonstrates = (backup_rows["rows"] == 1
                    and (bare_before_rows["rows"] != 1)
                    and bare_after_rows["rows"] == 1)
    w5.dump({
        "schema": "w5.bare-copy-probe/1",
        "ok": demonstrates,
        "work": str(work),
        "journal_mode": mode,
        "wal_bytes_before_bare_copy": wal_bytes,
        "bare_copy_while_open": bare_before_rows,
        "backup_export": {**backup_rows, "integrity_ok": export_summary["integrity_ok"]},
        "bare_copy_after_close": bare_after_rows,
        "conclusion": ("copying only the .db file while a writer is open missed the committed "
                       "row; backup() included it; the checkpoint on close is what makes the "
                       "later bare copy complete - a bare copy of a live .db is not a valid "
                       "real backup"),
    })
    return EXIT_OK if demonstrates else EXIT_FINDINGS


# --------------------------------------------------------------------------- #
# tamper probe
# --------------------------------------------------------------------------- #
def _detect(store_root: Path) -> dict[str, Any]:
    try:
        store = w5.read_consistent_store(store_root)
        return {"detected": False, "error": None, "revision": store["revision"]}
    except w5.StoreInconsistent as exc:
        return {"detected": True, "error": str(exc)}
    except Exception as exc:  # noqa: BLE001
        return {"detected": True, "error": f"{type(exc).__name__}: {exc}",
                "unexpected_error_type": True}


def cmd_tamper_probe(args: argparse.Namespace) -> int:
    store, work = Path(args.store), Path(args.work)
    api = w5.catalog_api()
    digest_before = w5.both_digests(store)

    # ---- v1: edit the revision body in place, keep the file name -------------
    w5.fresh_copy(store, work)
    read = w5.read_consistent_store(work)
    body_path = Path(read["revision_path"])
    payload = json.loads(body_path.read_text(encoding="utf-8"))
    first = payload["entries"][0]
    first["native_locator"]["probe_tamper"] = "v1-kept-the-file-name"
    body_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                         encoding="utf-8", newline="\n")
    reloaded = api["CatalogSnapshot"].from_dict(json.loads(body_path.read_text(encoding="utf-8")))
    v1_recomputes = api["compute_revision"](reloaded.entries) == read["revision"]
    v1 = {**_detect(work), "revision_recomputes_to_name": v1_recomputes,
          "file_name": body_path.name, "revision": read["revision"]}

    # ---- v2: swap two entries' public IDs, rename the revision, update pointer
    w5.fresh_copy(store, work)
    read = w5.read_consistent_store(work)
    pointer_path = work / "catalog" / "current.json"
    body_path = Path(read["revision_path"])
    payload = json.loads(body_path.read_text(encoding="utf-8"))
    entries = payload["entries"]
    pair = next((i, j) for i in range(len(entries)) for j in range(i + 1, len(entries))
                if entries[i]["kind"] != entries[j]["kind"])
    i, j = pair
    entries[i]["public_id"], entries[j]["public_id"] = (entries[j]["public_id"],
                                                        entries[i]["public_id"])
    snapshot = api["CatalogSnapshot"].from_dict(payload)
    new_revision = api["compute_revision"](snapshot.entries)
    snapshot.dataset_revision = new_revision
    new_body = json.dumps(snapshot.to_dict(), ensure_ascii=False, sort_keys=True,
                          separators=(",", ":")) + "\n"
    new_path = work / "catalog" / "revisions" / f"{new_revision}.json"
    new_path.write_text(new_body, encoding="utf-8", newline="\n")
    pointer = json.loads(pointer_path.read_text(encoding="utf-8"))
    pointer["dataset_revision"] = new_revision
    pointer_path.write_text(json.dumps(pointer, ensure_ascii=False, indent=2) + "\n",
                            encoding="utf-8", newline="\n")
    reloaded = api["CatalogSnapshot"].from_dict(json.loads(new_path.read_text(encoding="utf-8")))
    v2_recomputes = api["compute_revision"](reloaded.entries) == new_revision
    v2 = {**_detect(work), "revision_recomputes_to_name": v2_recomputes,
          "file_name_matches_recomputed": new_path.name == f"{new_revision}.json",
          "old_revision": read["revision"], "new_revision": new_revision,
          "swapped": [entries[i]["public_id"], entries[j]["public_id"]]}

    digest_after = w5.both_digests(store)
    store_unchanged = (digest_before["historical"]["sha256"] == digest_after["historical"]["sha256"]
                       and digest_before["posix_v1"]["sha256"] == digest_after["posix_v1"]["sha256"])
    checks = [
        {"id": "v1_detected", "ok": v1["detected"], "detail": v1.get("error")},
        {"id": "v1_undetectable_by_name", "ok": v1["revision_recomputes_to_name"] is False,
         "detail": "edited body no longer recomputes to the file's revision name"},
        {"id": "v2_detected", "ok": v2["detected"], "detail": v2.get("error")},
        {"id": "v2_self_consistent_names", "ok": v2_recomputes is True,
         "detail": "file name and pointer match the recomputed revision; only the "
                   "per-entry round-trip check catches it"},
        {"id": "store_unchanged", "ok": store_unchanged,
         "detail": "the probe store's digests are identical before and after"},
    ]
    ok = all(c["ok"] for c in checks)
    w5.dump({"schema": "w5.tamper-probe/1", "ok": ok, "store": str(store), "work": str(work),
             "v1_edit_body_keep_name": v1, "v2_self_consistent_swap": v2,
             "store_digests_before": {k: v["sha256"] for k, v in digest_before.items()},
             "store_digests_after": {k: v["sha256"] for k, v in digest_after.items()},
             "checks": checks})
    return EXIT_OK if ok else EXIT_FINDINGS


# --------------------------------------------------------------------------- #
# poke
# --------------------------------------------------------------------------- #
def cmd_poke(args: argparse.Namespace) -> int:
    try:
        path = w5.guard_within(args.file, w5.MIGRATION_ROOT)
    except w5.OutsideWorkingRoot as exc:
        w5.dump({"schema": "w5.poke/1", "ok": False, "error": str(exc)})
        return EXIT_REFUSAL
    before = w5.sha256_file(path) if path.is_file() else None
    data = args.write_text.encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    w5.dump({"schema": "w5.poke/1", "ok": True, "file": str(path),
             "before_sha256": before, "after_sha256": w5.sha256_bytes(data),
             "bytes": len(data)})
    return EXIT_OK


# --------------------------------------------------------------------------- #
# cli
# --------------------------------------------------------------------------- #
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="command", required=True)

    p = sub.add_parser("pointer-rollback", help="restore the previous pointer atomically")
    p.add_argument("--store", required=True)
    p.add_argument("--out-evidence", default=None)
    p.set_defaults(func=cmd_pointer_rollback)

    p = sub.add_parser("content-restore", help="rebuild a destination from source + manifest")
    p.add_argument("--source", required=True)
    p.add_argument("--manifest", required=True)
    p.add_argument("--dest", required=True)
    p.add_argument("--reference", required=True,
                   help="the good destination to compare the restored tree with")
    p.add_argument("--out-evidence", default=None)
    p.set_defaults(func=cmd_content_restore)

    p = sub.add_parser("sqlite-restore", help="backup() export and restore of the index db")
    p.add_argument("--db", required=True)
    p.add_argument("--export", required=True)
    p.add_argument("--restore", required=True)
    p.set_defaults(func=cmd_sqlite_restore)

    p = sub.add_parser("bare-copy-probe", help="prove a bare .db copy is not a backup")
    p.add_argument("--work", required=True)
    p.set_defaults(func=cmd_bare_copy_probe)

    p = sub.add_parser("tamper-probe", help="two tamper modes; both must be caught")
    p.add_argument("--store", required=True)
    p.add_argument("--work", required=True)
    p.set_defaults(func=cmd_tamper_probe)

    p = sub.add_parser("poke", help="overwrite one private working file with exact bytes")
    p.add_argument("--file", required=True)
    p.add_argument("--write-text", required=True)
    p.set_defaults(func=cmd_poke)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
