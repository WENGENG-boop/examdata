#!/usr/bin/env python3
"""A12 route compatibility worksheet builder (plan 5.5, packet A12).

Writes `docs/integration/execution/A12_ROUTE_COMPATIBILITY_WORKSHEET.json`:
the A01 worksheet columns kept intact, each baseline row enriched with the
reviewed A12 fields (mechanism/status/evidence/test ids), plus one deferred
row for every route added to the four target api files *after* the 71-route
baseline was frozen.

The four api files are re-scanned statically (ast, never import) through
`a12_extract_legacy_shapes.extract` at build time, so post-baseline routes by
the active owner are detected without re-running the A01 inventory.

`materials/router.py` and `timetable/router.py` are existence-checked only
(their rows stay `deferred_active_owner`); they are never parsed, imported or
executed. No database, service, network or original-application access.

Usage:
    python integration-staging/tools/a12_build_worksheet.py [--check]
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.dont_write_bytecode = True

WS = Path(__file__).resolve().parents[2]
STAGING = WS / "integration-staging"
SRC = STAGING / "src"
TOOLS = STAGING / "tools"
EXECUTION = WS / "docs" / "integration" / "execution"
A01_PATH = EXECUTION / "A01_ROUTE_COMPATIBILITY_WORKSHEET.json"
REGISTRY_PATH = SRC / "examdata_integration" / "legacy" / "registry.json"
OUT_PATH = EXECUTION / "A12_ROUTE_COMPATIBILITY_WORKSHEET.json"

sys.path.insert(0, str(SRC))
sys.path.insert(0, str(TOOLS))

from examdata_integration.legacy import decisions  # noqa: E402
from a12_extract_legacy_shapes import extract as extract_shapes  # noqa: E402

SCHEMA = "examdata.integration.route_compatibility_worksheet/2"
PLAN_REF = ("docs/integration/MASTER_EXECUTION_PLAN_EN.md packet A12 (plan 5.5); "
            "supersedes the A01 proposal columns for reviewed rows")

POST_BASELINE_REASON = ("post-baseline route added by the active owner; "
                        "not reviewed in A12")
POST_BASELINE_NOTE = ("row_origin=post_baseline: detected by the frozen static "
                      "re-scan of the four target api files; Phase A does not "
                      "review it and no v2 claim is made; stays deferred until "
                      "the human releases the path")
UNREVIEWED = "not reviewed (post-baseline)"

NOTES = [
    "compatibility_strategy keeps the A01 proposal verbatim; mechanism (new column) "
    "is the reviewed A12 classification - where they differ the mechanism wins.",
    "a01_proposal records any A01 value that the reviewed A12 row replaced; absent "
    "keys were unchanged.",
    "row_origin=post_baseline rows were detected by re-scanning the four target api "
    "files at build time; they are deferred and unreviewed by design.",
    "materials/timetable sources are existence-checked only and never parsed "
    "(active-owner code protected in Phase A).",
]


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build() -> dict:
    a01 = json.loads(A01_PATH.read_text(encoding="utf-8"))
    registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))

    a01_rows = a01["rows"]
    reg_rows = registry["rows"]
    assert len(a01_rows) == 71, "A01 worksheet is not the 71-row baseline"
    assert len(reg_rows) == 71, "registry is not the 71-row baseline"

    a01_columns = list(a01["columns"])
    a01_extra = list(a01.get("extra_row_keys", []))
    columns = a01_columns + ["row_id", "mechanism", "coverage_kind", "owner", "notes"]
    extra_row_keys = a01_extra + ["line", "a01_proposal"]
    expected_keys = set(columns) | set(extra_row_keys)

    reg_by_key = {(r["method"], r["legacy_path"]): r for r in reg_rows}
    assert len(reg_by_key) == 71, "duplicate baseline keys in the registry"
    baseline_keys = set(reg_by_key)
    for ws_row in a01_rows:
        key = (ws_row["method"], ws_row["legacy_path"])
        assert key in reg_by_key, f"A01 row missing from registry: {key}"

    deferred = [r for r in reg_rows if r["mechanism"] == "deferred_active_owner"]
    assert len(deferred) == 7, "expected exactly the seven deferred rows"
    non_deferred = [r for r in reg_rows if r["mechanism"] != "deferred_active_owner"]

    # -- fresh static re-scan of the four target api files (never imported) ---
    fresh = extract_shapes()
    fresh_index: dict[tuple[str, str], list[dict]] = {}
    for route in fresh["routes"]:
        fresh_index.setdefault((route["method"], route["path"]), []).append(route)

    problems: list[str] = []
    if fresh["route_count"] < 64:
        problems.append(f"fresh re-scan found only {fresh['route_count']} routes "
                        f"(frozen extraction had 64)")
    changed_files = [rel for rel, digest in fresh["source_hashes"].items()
                     if registry["source_hashes"].get(rel) != digest]
    for rel in changed_files:
        problems.append(f"api file changed since the A12 shape extract: {rel}")

    drift: list[str] = []
    used_fresh: set[tuple[str, str]] = set()

    def find_fresh(row: dict) -> dict | None:
        matches = fresh_index.get((row["method"], row["legacy_path"]), [])
        if not matches:
            return None
        same_file = [m for m in matches if m["file"] == row["source_file"]]
        pick = (same_file or matches)[0]
        if len(matches) > 1:
            problems.append(f"duplicate re-scan matches for "
                            f"{row['method']} {row['legacy_path']}")
        used_fresh.add((pick["method"], pick["path"]))
        return pick

    rows: list[dict] = []
    strategy_mechanism_diffs: list[str] = []
    for ws_row in a01_rows:
        key = (ws_row["method"], ws_row["legacy_path"])
        reg = reg_by_key[key]
        merged = dict(ws_row)
        proposal: dict = {}
        for name, value in reg.items():
            if name == "row_id":
                continue
            if name in merged and merged[name] != value:
                proposal[name] = merged[name]
            merged[name] = value
        merged["row_id"] = reg["row_id"]

        if reg["mechanism"] == "deferred_active_owner":
            if fresh_index.get(key):  # pragma: no cover - protected files not scanned
                problems.append(f"deferred route found in scanned files: {key}")
        else:
            route = find_fresh(reg)
            if route is None:
                problems.append(f"baseline route missing from re-scan: "
                                f"{reg['method']} {reg['legacy_path']}")
                merged["line"] = reg.get("line")
            else:
                merged["line"] = route["line"]
                if reg.get("line") is not None and route["line"] != reg["line"]:
                    drift.append(f"{reg['row_id']}: line {reg['line']} -> {route['line']}")
                if route["handler"] != reg["handler"]:
                    drift.append(f"{reg['row_id']}: handler {reg['handler']} -> "
                                 f"{route['handler']}")

        if merged.get("compatibility_strategy") != merged["mechanism"]:
            strategy_mechanism_diffs.append(merged["row_id"])
        merged["a01_proposal"] = proposal
        assert set(merged.keys()) == expected_keys, (
            f"row {merged.get('row_id')} has unexpected keys: "
            f"{sorted(set(merged.keys()) ^ expected_keys)}")
        rows.append(merged)

    # -- post-baseline routes: in the scanned files, not in the baseline ------
    post_ids: list[str] = []
    for route in fresh["routes"]:
        key = (route["method"], route["path"])
        if key in baseline_keys or key in used_fresh:
            continue
        used_fresh.add(key)
        rid = decisions.row_id(route["method"], route["path"])
        post_ids.append(rid)
        row = {name: "" for name in columns}
        row.update({
            "method": route["method"],
            "legacy_path": route["path"],
            "source_file": route["file"],
            "handler": route["handler"],
            "legacy_error_shape": UNREVIEWED,
            "binary_behavior": UNREVIEWED,
            "side_effects": UNREVIEWED,
            "compatibility_strategy": "deferred",
            "status": "deferred_active_owner",
            "evidence_path": "",
            "deferred_reason": POST_BASELINE_REASON,
            "row_id": rid,
            "mechanism": "deferred_active_owner",
            "coverage_kind": "post_baseline_unreviewed",
            "owner": "kimi_active",
            "notes": POST_BASELINE_NOTE,
            "row_origin": "post_baseline",
            "handler_doc_line": "",
            "line": route["line"],
            "a01_proposal": {},
        })
        assert set(row.keys()) == expected_keys, f"post-baseline row {rid} keys"
        rows.append(row)

    if drift:
        problems.extend(f"re-scan drift: {d}" for d in drift)

    # -- active-owner existence check (never parsed) --------------------------
    active_owner_files = sorted({r["source_file"] for r in deferred})
    assert active_owner_files == [
        "examdata/src/examdata/materials/router.py",
        "examdata/src/examdata/timetable/router.py",
    ], f"unexpected deferred source files: {active_owner_files}"
    existence = [{"path": rel, "exists": (WS / rel).is_file()}
                 for rel in active_owner_files]

    by_status: dict[str, int] = {}
    by_mechanism: dict[str, int] = {}
    by_kind: dict[str, int] = {}
    by_provider: dict[str, int] = {}
    for row in rows:
        by_status[row["status"]] = by_status.get(row["status"], 0) + 1
        by_mechanism[row["mechanism"]] = by_mechanism.get(row["mechanism"], 0) + 1
        by_kind[row["coverage_kind"]] = by_kind.get(row["coverage_kind"], 0) + 1
        by_provider[row["provider"]] = by_provider.get(row["provider"], 0) + 1
    for row in rows:
        assert row["status"] in decisions.ALLOWED_STATUSES, row["row_id"]

    return {
        "schema": SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "generated_at_local": datetime.now().astimezone().isoformat(),
        "plan_ref": PLAN_REF,
        "columns": columns,
        "extra_row_keys": extra_row_keys,
        "notes": NOTES,
        "sources": {
            "a01_worksheet": {
                "path": "docs/integration/execution/A01_ROUTE_COMPATIBILITY_WORKSHEET.json",
                "sha256": sha256_file(A01_PATH),
            },
            "registry": {
                "path": "integration-staging/src/examdata_integration/legacy/registry.json",
                "sha256": sha256_file(REGISTRY_PATH),
            },
            "build_tool": {
                "path": "integration-staging/tools/a12_build_worksheet.py",
                "sha256": sha256_file(Path(__file__)),
            },
            "shape_rescan_tool": {
                "path": "integration-staging/tools/a12_extract_legacy_shapes.py",
                "sha256": sha256_file(TOOLS / "a12_extract_legacy_shapes.py"),
            },
        },
        "rescan": {
            "method": fresh["method"],
            "recorded_source_hashes": registry["source_hashes"],
            "fresh_source_hashes": fresh["source_hashes"],
            "changed_files": changed_files,
            "fresh_route_count": fresh["route_count"],
            "post_baseline_routes": post_ids,
            "line_or_handler_drift": drift,
        },
        "active_owner_files": existence,
        "summary": {
            "row_count": len(rows),
            "baseline_count": 71,
            "baseline_coverage": "71/71",
            "post_baseline_count": len(post_ids),
            "reviewed_baseline_rows": len(non_deferred),
            "deferred_active_owner_rows": len(deferred),
            "status_counts": by_status,
            "mechanism_counts": by_mechanism,
            "coverage_kind_counts": by_kind,
            "provider_counts": by_provider,
            "strategy_mechanism_diffs": len(strategy_mechanism_diffs),
        },
        "problems": problems,
        "rows": rows,
    }


def main(argv: list[str]) -> int:
    document = build()
    text = json.dumps(document, ensure_ascii=False, indent=2) + "\n"
    if "--check" in argv:
        current = OUT_PATH.read_text(encoding="utf-8") if OUT_PATH.exists() else ""
        if current and json.loads(current).get("rows") == document["rows"]:
            print("[ok] worksheet rows are current (timestamps ignored)")
            return 0
        print("[FAIL] worksheet is stale; rerun without --check")
        return 1
    OUT_PATH.write_text(text, encoding="utf-8")
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    summary = document["summary"]
    print(f"[ok] wrote {OUT_PATH.relative_to(WS)} "
          f"({len(text)} bytes, sha256 {digest[:16]}...)")
    print(f"[ok] rows={summary['row_count']} baseline={summary['baseline_count']} "
          f"post_baseline={summary['post_baseline_count']}")
    print(f"[ok] status={summary['status_counts']}")
    print(f"[ok] mechanism={summary['mechanism_counts']}")
    print(f"[ok] coverage_kind={summary['coverage_kind_counts']}")
    print(f"[ok] changed api files since extract={document['rescan']['changed_files']}")
    print(f"[ok] post-baseline ids={document['rescan']['post_baseline_routes']}")
    print(f"[ok] problems={document['problems']}")
    print(f"[ok] active-owner existence={document['active_owner_files']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
