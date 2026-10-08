#!/usr/bin/env python
"""W5 verification: check a migrated destination, a manifest, or two artifacts.

Subcommands (all deterministic JSON on stdout, all exit codes shared with the
rest of the W5 tool package):

``destination``
    Full verification of a migrated destination against its copy manifest, the
    source it was copied from and the recorded query evidence: per-file sha256,
    asset sha256 claims against payload bytes, region ``document_sha256`` against
    the referenced document, the ``PROVENANCE.json`` chain, the decisions file
    byte-for-byte, the aggregate index byte copy, the store view (pointer ->
    revision -> per-entry identity round-trip) and the recomputed query evidence.

``store-check``
    Read one consistent store view and compare it with explicit expectations
    (``--expect-revision``, ``--expect-pointer-sha256``); optionally write the
    recomputed ``query-evidence/1`` document with ``--out-evidence``.

``tree-diff``
    File-by-file comparison of two trees (relative path sets and sha256 values),
    including both inherited tree digests.

``evidence-diff``
    Compare two query-evidence JSON files, ignoring named top-level keys (default
    ``dest_root``, which legitimately differs between two dest roots).

``path-state``
    Assert existence / absence / sha256 / byte-equality of one path.

Exit codes: ``0`` ok | ``1`` error | ``8`` verification findings.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import w5_common as w5  # noqa: E402
import migrate  # noqa: E402

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_FINDINGS = 8

MAX_DETAIL_ITEMS = 20


def _findings(checks: list[dict[str, Any]], key: str = "failures") -> dict[str, Any]:
    bad = [c for c in checks if not c["ok"]]
    return {key: [c["id"] for c in bad], "ok": not bad}


def _capped(items: list[Any]) -> dict[str, Any]:
    return {"count": len(items), "items": items[:MAX_DETAIL_ITEMS],
            "truncated": len(items) > MAX_DETAIL_ITEMS}


# --------------------------------------------------------------------------- #
# destination verification
# --------------------------------------------------------------------------- #
def _payload_sha(payload: Path, rel: str) -> str | None:
    path = payload / rel
    return w5.sha256_file(path) if path.is_file() else None


def verify_destination(dest_root: Path, source_root: Path, manifest_dir: Path) -> dict[str, Any]:
    dest_root, source_root, manifest_dir = map(Path, (dest_root, source_root, manifest_dir))
    payload = dest_root / "payload"
    checks: list[dict[str, Any]] = []

    def add(cid: str, ok: bool, detail: str, **extra: Any) -> None:
        checks.append({"id": cid, "ok": bool(ok), "detail": detail, **extra})

    # 1. per-file manifest rows against the bytes on disk ----------------------
    manifest = w5.read_json(manifest_dir / "copy_manifest.json")
    bad_files: list[dict[str, Any]] = []
    missing_not_migrated: list[str] = []
    checked = 0
    for row in manifest["rows"]:
        if row.get("dest_path"):
            target = dest_root / row["dest_path"]
            if not target.is_file():
                bad_files.append({"path": row["path"], "reason": "missing"})
                continue
            sha = w5.sha256_file(target)
            size = target.stat().st_size
            if sha != row["sha256"] or size != row["size"]:
                bad_files.append({"path": row["path"], "reason": "content",
                                  "expected_sha256": row["sha256"], "actual_sha256": sha,
                                  "expected_size": row["size"], "actual_size": size})
            else:
                checked += 1
        else:
            if (dest_root / row["path"]).exists():
                missing_not_migrated.append(row["path"])
    add("manifest_files", not bad_files,
        f"{checked} migrated files verified against the manifest; "
        f"{len(bad_files)} mismatched or missing", **{"bad": _capped(bad_files)})
    add("not_migrated_absent", not missing_not_migrated,
        "read-only observed / tooling files are deliberately absent from the destination",
        present=missing_not_migrated)

    # 2. the source is unchanged since the copy --------------------------------
    live = w5.both_digests(source_root)
    recorded = manifest.get("source_digests", {})
    drift = {k: {"recorded": recorded.get(k, {}).get("sha256"),
                 "live": live[k]["sha256"]}
             for k in ("historical", "posix_v1")
             if recorded.get(k, {}).get("sha256") != live[k]["sha256"]}
    add("source_immutable", not drift,
        "source tree digests recomputed and compared with the manifest",
        drift=drift, digests={k: live[k]["sha256"] for k in live})

    # 3. one consistent store view ---------------------------------------------
    store: dict[str, Any] | None = None
    try:
        store = w5.read_consistent_store(dest_root)
        add("store_consistent", True,
            f"pointer -> revision {store['revision']} -> "
            f"{len(store['entries'])} entries round-trip their identities")
    except Exception as exc:  # noqa: BLE001 - any read failure is the finding
        add("store_consistent", False, f"{type(exc).__name__}: {exc}")

    if store is not None:
        entries = [store["entries"][pid] for pid in sorted(store["entries"])]

        # 4. asset sha256 claims against the payload bytes ---------------------
        asset_bad: list[dict[str, Any]] = []
        for entry in entries:
            if entry.kind != "asset":
                continue
            claim = entry.identity_fields.get("sha256")
            rel = entry.native_locator.get("path")
            actual = _payload_sha(payload, rel) if rel else None
            if actual is None or actual != claim:
                asset_bad.append({"public_id": entry.public_id, "path": rel,
                                  "claim": claim, "actual": actual})
        add("asset_claims", not asset_bad,
            f"{sum(1 for e in entries if e.kind == 'asset')} asset claims checked "
            f"against payload bytes", **{"bad": _capped(asset_bad)})

        # 5. region document_sha256 against the referenced document ------------
        region_bad: list[dict[str, Any]] = []
        for entry in entries:
            if entry.kind != "region":
                continue
            claim = entry.identity_fields.get("document_sha256")
            rel = entry.native_locator.get("document")
            actual = _payload_sha(payload, rel) if rel else None
            if actual is None or actual != claim:
                region_bad.append({"public_id": entry.public_id, "document": rel,
                                   "claim": claim, "actual": actual})
        add("region_documents", not region_bad,
            f"{sum(1 for e in entries if e.kind == 'region')} region document hashes "
            f"checked", **{"bad": _capped(region_bad)})

        # 6. manual decisions preserved byte-for-byte --------------------------
        src_decisions = source_root / "decisions" / "manual-decisions.json"
        dst_decisions = payload / "decisions" / "manual-decisions.json"
        same = (src_decisions.is_file() and dst_decisions.is_file()
                and src_decisions.read_bytes() == dst_decisions.read_bytes())
        add("decisions_bytes", same,
            "decisions/manual-decisions.json is byte-identical to the source copy",
            source_sha256=w5.sha256_file(src_decisions) if src_decisions.is_file() else None,
            dest_sha256=w5.sha256_file(dst_decisions) if dst_decisions.is_file() else None)

        # 7. aggregate index is a byte copy (integration-owned, never merged) --
        src_index = source_root / "index" / "aggregate-index.db"
        dst_index = payload / "index" / "aggregate-index.db"
        index_rows = {r["path"]: r["sha256"] for r in manifest["rows"]
                      if r["path"] == "index/aggregate-index.db"}
        same_index = (src_index.is_file() and dst_index.is_file()
                      and src_index.read_bytes() == dst_index.read_bytes())
        add("index_byte_copy", same_index and index_rows.get("index/aggregate-index.db")
            == (w5.sha256_file(dst_index) if dst_index.is_file() else None),
            "index/aggregate-index.db is the byte copy recorded in the manifest",
            source_sha256=w5.sha256_file(src_index) if src_index.is_file() else None,
            dest_sha256=w5.sha256_file(dst_index) if dst_index.is_file() else None,
            manifest_sha256=index_rows.get("index/aggregate-index.db"))

        # 8. provenance chain ---------------------------------------------------
        # Source provenance describes every source file; the observed
        # read-only file is deliberately not migrated, so the chain check
        # requires migrated rows to match payload bytes and non-migrated rows
        # to be absent from the destination.
        prov_path = payload / "provenance" / "PROVENANCE.json"
        prov_bad: list[dict[str, Any]] = []
        prov_entries = 0
        prov_not_migrated = 0
        migrated = {row["path"] for row in manifest["rows"] if row.get("dest_path")}
        if not prov_path.is_file():
            prov_bad.append({"reason": "PROVENANCE.json missing"})
        else:
            provenance = w5.read_json(prov_path)
            for entry in provenance["entries"]:
                prov_entries += 1
                if entry["path"] not in migrated:
                    if (payload / entry["path"]).exists():
                        prov_bad.append({"path": entry["path"],
                                         "reason": "not-migrated row exists in payload"})
                    else:
                        prov_not_migrated += 1
                    continue
                actual = _payload_sha(payload, entry["path"])
                if actual != entry["sha256"]:
                    prov_bad.append({"path": entry["path"], "recorded": entry["sha256"],
                                     "actual": actual})
        add("provenance_chain", not prov_bad,
            f"{prov_entries} provenance rows recomputed against payload bytes "
            f"({prov_not_migrated} describe not-migrated files and must be absent)",
            **{"bad": _capped(prov_bad)})

        # 9. recomputed query evidence vs the recorded one ----------------------
        live_evidence = migrate.query_evidence(dest_root)
        recorded_path = manifest_dir / "query_evidence.json"
        if recorded_path.is_file():
            recorded_evidence = w5.read_json(recorded_path)
            diff = [k for k in sorted(set(live_evidence) | set(recorded_evidence))
                    if k != "dest_root" and live_evidence.get(k) != recorded_evidence.get(k)]
            add("query_evidence", not diff,
                "recomputed query evidence equals the recorded evidence "
                "(all fields except dest_root)", differing_keys=diff)
        else:
            add("query_evidence", True,
                "no recorded query_evidence.json to compare against (skipped)")
    else:
        add("query_evidence", False, "store unreadable; evidence not recomputed")

    result = {
        "schema": "w5.verify-destination/1",
        "dest_root": str(dest_root),
        "source_root": str(source_root),
        "manifest_dir": str(manifest_dir),
        "checks": checks,
        **_findings(checks),
    }
    return result


def cmd_destination(args: argparse.Namespace) -> int:
    result = verify_destination(Path(args.dest), Path(args.source), Path(args.manifest_dir))
    if args.out:
        w5.write_json(args.out, result)
    w5.dump({k: v for k, v in result.items() if k != "checks"}
            | {"checks": [{"id": c["id"], "ok": c["ok"]} for c in result["checks"]]})
    return EXIT_OK if result["ok"] else EXIT_FINDINGS


# --------------------------------------------------------------------------- #
# store-check
# --------------------------------------------------------------------------- #
def cmd_store_check(args: argparse.Namespace) -> int:
    store_root = Path(args.store)
    checks: list[dict[str, Any]] = []
    summary: dict[str, Any] = {}
    try:
        store = w5.read_consistent_store(store_root)
    except Exception as exc:  # noqa: BLE001
        w5.dump({"schema": "w5.store-check/1", "store": str(store_root), "ok": False,
                 "error": f"{type(exc).__name__}: {exc}"})
        return EXIT_FINDINGS
    summary = {"revision": store["revision"], "pointer_sha256": store["pointer_sha256"],
               "revision_sha256": store["revision_sha256"],
               "entries": len(store["entries"])}
    if args.expect_revision:
        checks.append({"id": "expected_revision", "ok": store["revision"] == args.expect_revision,
                       "detail": f"current {store['revision']} vs expected "
                                 f"{args.expect_revision}"})
    if args.expect_pointer_sha256:
        checks.append({"id": "expected_pointer_sha256",
                       "ok": store["pointer_sha256"] == args.expect_pointer_sha256,
                       "detail": f"current {store['pointer_sha256']}"})
    evidence = migrate.query_evidence(store_root)
    if args.out_evidence:
        w5.write_json(args.out_evidence, evidence)
    ok = all(c["ok"] for c in checks)
    w5.dump({"schema": "w5.store-check/1", "store": str(store_root), "ok": ok,
             **summary, "checks": checks,
             "counts": evidence["counts"]})
    return EXIT_OK if ok else EXIT_FINDINGS


# --------------------------------------------------------------------------- #
# tree-diff
# --------------------------------------------------------------------------- #
def _file_map(root: Path) -> dict[str, str]:
    return {p.relative_to(root).as_posix(): w5.sha256_file(p) for p in w5.iter_files(root)}


def cmd_tree_diff(args: argparse.Namespace) -> int:
    a, b = Path(args.a), Path(args.b)
    skip = list(args.skip or [])
    map_a, map_b = _file_map(a), _file_map(b)
    only_a = sorted(set(map_a) - set(map_b))
    only_b = sorted(set(map_b) - set(map_a))
    differing = [{"path": rel, "sha_a": map_a[rel], "sha_b": map_b[rel]}
                 for rel in sorted(set(map_a) & set(map_b)) if map_a[rel] != map_b[rel]]
    digests = {"a": w5.both_digests(a, skip=skip), "b": w5.both_digests(b, skip=skip)}
    equal = not only_a and not only_b and not differing \
        and digests["a"]["historical"]["sha256"] == digests["b"]["historical"]["sha256"]
    w5.dump({"schema": "w5.tree-diff/1", "a": str(a), "b": str(b), "equal": equal,
             "files_a": len(map_a), "files_b": len(map_b),
             "only_in_a": _capped(only_a), "only_in_b": _capped(only_b),
             "differing": _capped(differing),
             "digests": {k: {o: v[o]["sha256"] for o in ("historical", "posix_v1")}
                         for k, v in digests.items()}})
    return EXIT_OK if equal else EXIT_FINDINGS


def cmd_evidence_diff(args: argparse.Namespace) -> int:
    a_path, b_path = Path(args.a), Path(args.b)
    a, b = w5.read_json(a_path), w5.read_json(b_path)
    ignore = set(args.ignore or ["dest_root"])
    keys = sorted(set(a) | set(b))
    differing = [{k: {"a": a.get(k), "b": b.get(k)}} for k in keys
                 if k not in ignore and a.get(k) != b.get(k)]
    equal = not differing
    w5.dump({"schema": "w5.evidence-diff/1", "a": str(a_path), "b": str(b_path),
             "equal": equal, "ignored": sorted(ignore),
             "differing_keys": [list(d)[0] for d in differing],
             "differing": _capped(differing)})
    return EXIT_OK if equal else EXIT_FINDINGS


def cmd_path_state(args: argparse.Namespace) -> int:
    path = Path(args.path)
    exists = path.exists()
    checks: list[dict[str, Any]] = []
    checks.append({"id": "existence", "ok": (exists if args.expect == "exists"
                                             else not exists),
                   "detail": f"{'exists' if exists else 'absent'} (expected {args.expect})"})
    sha = w5.sha256_file(path) if path.is_file() else None
    if args.sha256:
        checks.append({"id": "sha256", "ok": sha == args.sha256,
                       "detail": f"{sha} vs expected {args.sha256}"})
    equal_file: dict[str, Any] | None = None
    if args.equal_file:
        other = Path(args.equal_file)
        equal = path.is_file() and other.is_file() and path.read_bytes() == other.read_bytes()
        equal_file = {"path": str(other), "equal": equal,
                      "sha256": w5.sha256_file(other) if other.is_file() else None}
        checks.append({"id": "equal_file", "ok": equal,
                       "detail": f"bytes {'' if equal else 'not '}equal to {other}"})
    ok = all(c["ok"] for c in checks)
    w5.dump({"schema": "w5.path-state/1", "path": str(path), "exists": exists,
             "sha256": sha, "equal_file": equal_file, "ok": ok, "checks": checks})
    return EXIT_OK if ok else EXIT_FINDINGS


# --------------------------------------------------------------------------- #
# cli
# --------------------------------------------------------------------------- #
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="command", required=True)

    p = sub.add_parser("destination", help="full verification of a migrated destination")
    p.add_argument("--dest", required=True)
    p.add_argument("--source", required=True)
    p.add_argument("--manifest-dir", required=True)
    p.add_argument("--out", default=None)
    p.set_defaults(func=cmd_destination)

    p = sub.add_parser("store-check", help="read one consistent store view")
    p.add_argument("--store", required=True)
    p.add_argument("--expect-revision", default=None)
    p.add_argument("--expect-pointer-sha256", default=None)
    p.add_argument("--out-evidence", default=None)
    p.set_defaults(func=cmd_store_check)

    p = sub.add_parser("tree-diff", help="compare two trees file-by-file")
    p.add_argument("--a", required=True)
    p.add_argument("--b", required=True)
    p.add_argument("--skip", action="append", default=[])
    p.set_defaults(func=cmd_tree_diff)

    p = sub.add_parser("evidence-diff", help="compare two query-evidence files")
    p.add_argument("--a", required=True)
    p.add_argument("--b", required=True)
    p.add_argument("--ignore", action="append", default=None)
    p.set_defaults(func=cmd_evidence_diff)

    p = sub.add_parser("path-state", help="assert existence / sha256 / byte equality")
    p.add_argument("--path", required=True)
    p.add_argument("--expect", choices=("exists", "not-exists"), default="exists")
    p.add_argument("--sha256", default=None)
    p.add_argument("--equal-file", default=None)
    p.set_defaults(func=cmd_path_state)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
