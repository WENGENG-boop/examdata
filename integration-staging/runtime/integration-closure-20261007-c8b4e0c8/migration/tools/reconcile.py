#!/usr/bin/env python
"""W5 reconciliation: per system / entity / scope, with explicit reject lists.

Matching total row counts alone is **not** acceptance, so this tool keeps a
double ledger per source row:

* what the source index says should be published (derived public ID, scope,
  identity validity, container references);
* what the destination store actually publishes (entries behind the pointer).

and then reports, explicitly: ``missing`` (should be published, is not),
``extra`` (published, was not expected), ``rejected`` (a row the migration must
refuse: invalid identity, unresolvable container reference, missing payload,
asset/document hash claim that does not match the bytes), ``flagged`` (identity
unresolved under the candidate's own trust rules - never treated as fatal), and
``mismatched`` (copy-manifest file rows whose destination bytes differ).

Exit codes: ``0`` verdict pass | ``1`` error | ``8`` verification findings.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import w5_common as w5  # noqa: E402
import migrate  # noqa: E402

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_FINDINGS = 8

NOTES = [
    "row totals alone are not acceptance: every expectation is a per-row double "
    "ledger (source index row -> published entry), and reject/mismatch lists are "
    "part of the verdict",
    "flagged rows carry an identity the candidate's own trust rules report as "
    "unresolved (``trust.identity_problems``; the not-applicable ``parent_native_id`` "
    "exception is honored, so a top-level row's UNKNOWN parent is *not* flagged); "
    "they are reported separately, never silently counted as clean, and never "
    "treated as fatal",
    "whenever the published ledger matches the expectation, the destination's "
    "persisted ``identity_unresolved`` problem refs are cross-checked against the "
    "predicted flagged set; a divergence is itself reported",
    "the aggregate index destination copy is compared byte-for-byte (it is an "
    "integration-owned byte copy, never merged)",
]


def _rejected_entry(status: dict[str, Any], reason: str, **extra: Any) -> dict[str, Any]:
    entry = {"entity_id": status["entity_id"],
             "public_id": status.get("derived_public_id")
             or status.get("recorded_public_id"),
             "system": status["system"], "kind": status["kind"], "reason": reason}
    entry.update(extra)
    return entry


def reconcile(source_root: Path, dest_root: Path, manifest_path: Path,
              publish_report_path: Path | None) -> dict[str, Any]:
    source_root, dest_root = Path(source_root), Path(dest_root)
    api = w5.catalog_api()
    decode_unknown = api["decode_unknown"]
    trust = api["trust"]
    EntityKind = api["EntityKind"]

    built = migrate.build_sources(source_root, select_scope="all")
    statuses = built["statuses"]
    rows = built["rows"]
    row_by_public = {r["public_id"]: r for r in rows}

    expected: dict[str, dict[str, Any]] = {}
    rejected: list[dict[str, Any]] = []
    flagged: list[dict[str, Any]] = []
    for status in statuses:
        if not status["identity_valid"]:
            rejected.append(_rejected_entry(
                status, "invalid_identity", detail=status["identity_problem"]))
            continue
        if status["unresolved_refs"]:
            rejected.append(_rejected_entry(
                status, "unresolved_container_ref", refs=status["unresolved_refs"]))
            continue
        pid = status["derived_public_id"]
        if status["in_selected_scope"]:
            expected[pid] = {"entity_id": status["entity_id"], "system": status["system"],
                             "kind": status["kind"], "scope": status["scope"]}
        if status.get("ambiguous_container_ref"):
            flagged.append({"public_id": pid, "entity_id": status["entity_id"],
                            "reason": "ambiguous_container_ref",
                            "container_refs": status["container_refs"]})
        row = row_by_public.get(status["recorded_public_id"])
        if row is None:
            continue
        for field in ("raw_path", "document_path"):
            rel = row.get(field)
            if rel and not (source_root / rel).is_file():
                existing = next((r for r in rejected if r.get("public_id") == pid
                                 and r["reason"] == "source_payload_missing"), None)
                if existing is None:
                    rejected.append(_rejected_entry(
                        status, "source_payload_missing", missing_paths=[rel]))
                elif rel not in existing["missing_paths"]:
                    existing["missing_paths"].append(rel)
        identity = decode_unknown(json.loads(row["identity_json"]))
        if row["kind"] == "asset" and row.get("raw_path"):
            rel = row["raw_path"]
            if (source_root / rel).is_file():
                claim, actual = identity.get("sha256"), w5.sha256_file(source_root / rel)
                if claim != actual:
                    rejected.append(_rejected_entry(
                        status, "asset_hash_mismatch", path=rel,
                        recorded_sha256=claim, actual_sha256=actual))
        if row["kind"] == "region":
            rel = row.get("document_path")
            if rel and (source_root / rel).is_file():
                claim, actual = (identity.get("document_sha256"),
                                 w5.sha256_file(source_root / rel))
                if claim != actual:
                    rejected.append(_rejected_entry(
                        status, "document_hash_mismatch", path=rel,
                        recorded_sha256=claim, actual_sha256=actual))
        if pid in expected:
            problems = trust.identity_problems(EntityKind.coerce(row["kind"]), identity)
            if problems:
                flagged.append({"public_id": pid, "entity_id": status["entity_id"],
                                "system": status["system"], "kind": row["kind"],
                                "reason": "identity_unresolved", "problems": problems})

    # destination side ---------------------------------------------------------
    reasons: list[str] = []
    dest_entries: dict[str, Any] = {}
    dest_revision: str | None = None
    dest_snapshot: Any = None
    try:
        store = w5.read_consistent_store(dest_root)
        dest_entries = store["entries"]
        dest_revision = store["revision"]
        dest_snapshot = store["snapshot"]
    except Exception as exc:  # noqa: BLE001 - an unreadable destination is a finding
        reasons.append(f"destination_unreadable: {type(exc).__name__}: {exc}")
        if not (dest_root / "catalog" / "current.json").exists():
            reasons.append("destination has no published catalog (current pointer absent)")
    dest_ids = set(dest_entries)

    if publish_report_path is not None:
        report = w5.read_json(publish_report_path)
        if not report.get("build_ok", False):
            reasons.append("publication_refused: the build did not pass validation")

    missing = [{"public_id": pid, **expected[pid]} for pid in sorted(set(expected) - dest_ids)]
    extra = [{"public_id": pid, "kind": dest_entries[pid].kind, "system": dest_entries[pid].system}
             for pid in sorted(dest_ids - set(expected))]

    # when the published ledger matches, the destination's own persisted
    # ``identity_unresolved`` problem refs must equal the predicted flagged set
    flagged_cross_check: dict[str, Any] | None = None
    if dest_snapshot is not None and not missing and not extra:
        dest_refs = sorted({pr.get("ref") for pr in dest_snapshot.problems
                            if pr.get("code") == "identity_unresolved"})
        predicted = sorted(f["public_id"] for f in flagged
                           if f["reason"] == "identity_unresolved")
        flagged_cross_check = {"predicted": predicted, "destination": dest_refs,
                               "match": dest_refs == predicted}
        if dest_refs != predicted:
            reasons.append(f"identity_unresolved_refs_mismatch: predicted "
                           f"{predicted} != destination {dest_refs}")

    # manifest file rows -------------------------------------------------------
    manifest = w5.read_json(manifest_path)
    mismatched: list[dict[str, Any]] = []
    for row in manifest["rows"]:
        if not row.get("dest_path"):
            continue
        target = dest_root / row["dest_path"]
        if not target.is_file():
            mismatched.append({"path": row["path"], "reason": "missing",
                               "manifest_sha256": row["sha256"]})
            continue
        actual = w5.sha256_file(target)
        if actual != row["sha256"]:
            mismatched.append({"path": row["path"], "reason": "content",
                               "manifest_sha256": row["sha256"], "actual_sha256": actual})

    # per-system / per-scope / per-kind rollups --------------------------------
    def rollup(key: str) -> dict[str, dict[str, int]]:
        out: dict[str, dict[str, int]] = {}
        for pid, meta in expected.items():
            bucket = out.setdefault(meta[key], {"expected": 0, "published": 0})
            bucket["expected"] += 1
            if pid in dest_ids:
                bucket["published"] += 1
        for entry in rejected:
            bucket = out.setdefault(entry.get(key) or "unknown", {})
            bucket["rejected"] = bucket.get("rejected", 0) + 1
        return {k: dict(sorted(v.items())) for k, v in sorted(out.items())}

    failed = bool(reasons or missing or extra or rejected or mismatched)
    return {
        "schema": "w5.reconciliation/1",
        "source_root": str(source_root),
        "dest_root": str(dest_root),
        "manifest": str(manifest_path),
        "publish_report": str(publish_report_path) if publish_report_path else None,
        "verdict": "fail" if failed else "pass",
        "reasons": reasons,
        "counts": {
            "source_rows": len(rows),
            "expected": len(expected),
            "published": len(dest_ids),
            "missing": len(missing),
            "extra": len(extra),
            "rejected": len(rejected),
            "flagged": len(flagged),
            "mismatched": len(mismatched),
        },
        "dataset_revision": dest_revision,
        "per_system": rollup("system"),
        "per_scope": rollup("scope"),
        "per_kind": rollup("kind"),
        "missing": missing,
        "extra": extra,
        "rejected": rejected,
        "flagged": flagged,
        "flagged_cross_check": flagged_cross_check,
        "mismatched": mismatched,
        "notes": NOTES,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", required=True)
    ap.add_argument("--dest", required=True)
    ap.add_argument("--manifest", required=True,
                    help="the copy manifest of the migration being reconciled")
    ap.add_argument("--publish-report", default=None)
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)

    result = reconcile(Path(args.source), Path(args.dest), Path(args.manifest),
                       Path(args.publish_report) if args.publish_report else None)
    if args.out:
        w5.write_json(args.out, result)
    w5.dump(result)
    return EXIT_OK if result["verdict"] == "pass" else EXIT_FINDINGS


if __name__ == "__main__":
    raise SystemExit(main())
