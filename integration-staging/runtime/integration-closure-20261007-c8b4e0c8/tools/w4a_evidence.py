"""W4a evidence generator: candidate OpenAPI snapshot, route-inventory refresh,
and the capability map (read-only, run-scoped).

Usage:
    python -B tools/w4a_evidence.py <candidate-root> <out-dir> [stamp]

Writes three stamped JSON artifacts into ``<out-dir>`` and prints a summary
(sha256 + size of every artifact) to stdout:

* ``openapi_candidate_<stamp>.json`` - the raw ``create_app().openapi()``
  document of the candidate tree.
* ``route_inventory_refresh_<stamp>.json`` - the live routes re-observed and
  compared, item by item, with ``evidence/w4/route_inventory.json``.
* ``capability_map_<stamp>.json`` - the sixteen families joined to the live
  OpenAPI document and the legacy registry, plus the production seam, the CLI
  interface, and the public unavailable-system behaviour.

Import discipline: the candidate ``src/`` goes on ``sys.path`` first and the
root-pointing ``EXAMDATA_*`` environment settings are cleared before
``examdata`` is imported, so the evidence describes the candidate tree only.
The baseline is resolved as ``<out-dir>/../w4/route_inventory.json``.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

METHODS = ("delete", "get", "head", "options", "patch", "post", "put", "trace")
FAMILY_COUNT = 16
CLI_LEAF_COUNT = 10


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, payload: Any) -> dict[str, Any]:
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
    path.write_text(text + "\n", encoding="utf-8")
    data = path.read_bytes()
    return {"path": str(path), "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest()}


def _prepare(candidate_root: Path) -> None:
    src = candidate_root / "src"
    if not src.is_dir():
        raise SystemExit(f"candidate root has no src/ directory: {candidate_root}")
    sys.path.insert(0, str(src))
    os.environ["EXAMDATA_INTEGRATION_ROOT"] = str(candidate_root)
    for name in ("EXAMDATA_INTEGRATION_STAGING_ROOT", "EXAMDATA_OPERATIONS_ROOT"):
        os.environ.pop(name, None)


def _registrations(document: dict[str, Any]) -> list[dict[str, str]]:
    """Every /api/v2 method registration in an OpenAPI document, sorted."""
    out: list[dict[str, str]] = []
    for path, item in sorted(document.get("paths", {}).items()):
        if not path.startswith("/api/v2"):
            continue
        for method in METHODS:
            operation = item.get(method)
            if operation is None:
                continue
            out.append({"method": method.upper(), "path": path,
                        "operation_id": operation.get("operationId", "")})
    return out


def _binary_pairs(registrations: list[dict[str, str]]) -> list[dict[str, str]]:
    """Paths registered for both GET and HEAD, with both operation ids."""
    by_path: dict[str, dict[str, str]] = {}
    for row in registrations:
        by_path.setdefault(row["path"], {})[row["method"]] = row["operation_id"]
    pairs: list[dict[str, str]] = []
    for path in sorted(by_path):
        methods = by_path[path]
        if "GET" in methods and "HEAD" in methods:
            pairs.append({"path": path, "get": methods["GET"], "head": methods["HEAD"]})
    return pairs


def _baseline_registrations(v2_routes: list[dict[str, Any]]) -> set[tuple[str, str, str]]:
    rows: set[tuple[str, str, str]] = set()
    for row in v2_routes:
        rows.add((row["method"].upper(), row["path"], row["operation_id"]))
        if row.get("binary") and row.get("operation_id_head"):
            rows.add(("HEAD", row["path"], row["operation_id_head"]))
    return rows


def _baseline_binary_pairs(v2_routes: list[dict[str, Any]]) -> list[dict[str, str]]:
    pairs = [
        {"path": row["path"], "get": row["operation_id"], "head": row["operation_id_head"]}
        for row in v2_routes
        if row.get("binary") and row.get("operation_id_head")
    ]
    return sorted(pairs, key=lambda pair: pair["path"])


def _pair_keys(pairs: list[dict[str, str]]) -> list[tuple[str, str, str]]:
    return sorted((pair["path"], pair["get"], pair["head"]) for pair in pairs)


def _walk_subcommands(parser: Any, prefix: str) -> tuple[list[str], list[str]]:
    """(all, leaf) command paths of an argparse parser tree, insertion order."""
    import argparse as _argparse

    all_commands: list[str] = []
    leaf_commands: list[str] = []
    for action in parser._actions:
        if not isinstance(action, _argparse._SubParsersAction):
            continue
        for name, subparser in action.choices.items():
            label = f"{prefix}{name}"
            child_all, child_leaf = _walk_subcommands(subparser, f"{label} ")
            all_commands.append(label)
            all_commands.extend(child_all)
            leaf_commands.extend(child_leaf)
            if not child_all:
                leaf_commands.append(label)
    return all_commands, leaf_commands


def _legacy_rows_match(legacy_rows: list[dict[str, Any]],
                       baseline_routes: list[dict[str, Any]]) -> bool:
    """Every raw registry row agrees with the baseline inventory row of the
    same row_id on (method, path, status, mechanism)."""
    baseline_rows = {row["row_id"]: row for row in baseline_routes}
    if len(legacy_rows) != len(baseline_rows):
        return False
    for raw in legacy_rows:
        base = baseline_rows.get(raw["row_id"])
        if base is None:
            return False
        if (base["method"].upper() != raw["method"].upper()
                or base["path"] != raw["legacy_path"]
                or base["status"] != raw["status"]
                or base["mechanism"] != raw["mechanism"]):
            return False
    return True


def _build_refresh(stamp: str, candidate_root: Path, baseline: dict[str, Any],
                   baseline_meta: dict[str, Any],
                   registrations: list[dict[str, str]],
                   pairs: list[dict[str, str]],
                   legacy: dict[str, Any],
                   legacy_rows: list[dict[str, Any]]) -> dict[str, Any]:
    counts = baseline["counts"]
    observed_paths = {row["path"] for row in registrations}
    observed_ids = {row["operation_id"] for row in registrations}
    observed_set = {(row["method"], row["path"], row["operation_id"]) for row in registrations}
    families = baseline["family_index"]
    families_missing = {
        family: [oid for oid in body.get("v2_operation_ids", []) if oid not in observed_ids]
        for family, body in sorted(families.items())
    }
    agreement = {
        "v2_route_count": len(observed_paths) == counts["v2_routes"],
        "v2_method_registration_count": len(registrations) == counts["v2_method_registrations"],
        "v2_registration_set_equal": observed_set == _baseline_registrations(baseline["v2_routes"]),
        "binary_route_pairs_equal": _pair_keys(pairs) == _pair_keys(
            _baseline_binary_pairs(baseline["v2_routes"])),
        "legacy_route_count": legacy["routes"] == counts["legacy_routes"],
        "legacy_status_counts_equal": legacy["by_status"] == counts["legacy_by_status"],
        "legacy_mechanism_counts_equal": legacy["by_mechanism"] == counts["legacy_by_mechanism"],
        "legacy_rows_match_baseline": _legacy_rows_match(
            legacy_rows, baseline["legacy_routes"]),
        "family_count": len(families) == FAMILY_COUNT,
        "families_all_operation_ids_present": not any(families_missing.values()),
    }
    agreement["all_true"] = all(agreement.values())
    observed = {
        "v2_paths": len(observed_paths),
        "v2_method_registrations": len(registrations),
        "v2_operation_ids": sorted(observed_ids),
        "v2_binary_pairs": pairs,
        "binary_get_operation_ids": [pair["get"] for pair in pairs],
        "legacy": legacy,
    }
    return {
        "schema": "integration.route_inventory.refresh/1",
        "stamp": stamp,
        "candidate_root": str(candidate_root),
        "read_at": _utc_now(),
        "based_on": baseline_meta,
        "baseline_counts": counts,
        "baseline_families_missing_operation_ids": families_missing,
        "carried_from_baseline": {
            "legacy_v2_equivalence": counts["legacy_v2_equivalence"],
            "note": ("the baseline's v2_equivalent_status split is a baseline-side "
                     "derivation over the same registry rows; equality of the raw "
                     "rows (row_id/method/path/status/mechanism) is the check here"),
        },
        "observed": observed,
        "agreement": agreement,
        "gaps_and_surprises": {
            "carried_from_baseline": True,
            "count": len(baseline.get("gaps_and_surprises", [])),
            "note": ("detail entries stay in the baseline; the W7 re-verification "
                     "pass owns their re-check"),
        },
    }


def _build_capability_map(stamp: str, candidate_root: Path, baseline: dict[str, Any],
                          baseline_meta: dict[str, Any],
                          registrations: list[dict[str, str]],
                          pairs: list[dict[str, str]],
                          legacy_rows: list[dict[str, Any]],
                          assembly: Any, cli: Any,
                          fixture_dataset: Any, unavailable_systems: dict[str, str],
                          behaviour: dict[str, Any]) -> dict[str, Any]:
    observed_ids = {row["operation_id"] for row in registrations}
    legacy_by_path: dict[str, dict[str, Any]] = {}
    for row in legacy_rows:
        legacy_by_path.setdefault(row["legacy_path"], row)

    families_block: dict[str, Any] = {}
    for family, body in sorted(baseline["family_index"].items()):
        operations = [
            {"operation_id": oid, "present": oid in observed_ids}
            for oid in body.get("v2_operation_ids", [])
        ]
        legacy_block: list[dict[str, Any]] = []
        for path in body.get("legacy_paths", []):
            row = legacy_by_path.get(path)
            matched_via = "exact"
            registry_path = path
            if row is None and path.startswith("/api/v1/"):
                stripped = "/" + path[len("/api/v1/"):]
                row = legacy_by_path.get(stripped)
                if row is not None:
                    matched_via = "prefix_stripped"
                    registry_path = stripped
            if row is None:
                legacy_block.append({"path": path, "matched": False})
            else:
                legacy_block.append({
                    "path": path,
                    "matched": True,
                    "matched_via": matched_via,
                    "registry_path": registry_path,
                    "row_id": row["row_id"],
                    "status": row["status"],
                    "mechanism": row["mechanism"],
                    "coverage_kind": row.get("coverage_kind"),
                    "v2_target": row.get("v2_target") or None,
                })
        families_block[family] = {
            "v2_operations": operations,
            "v2_missing": [row["operation_id"] for row in operations if not row["present"]],
            "legacy_paths": legacy_block,
            "legacy_unmatched": [row["path"] for row in legacy_block if not row["matched"]],
        }

    seam_entries = {
        "fixture_entries": ["build_fixture_dataset", "create_fixture_app"],
        "production_entries": ["ProductionConfig", "build_production_dataset",
                               "assemble_production", "create_production_app",
                               "production_capabilities"],
        "fail_closed_errors": ["ProductionAssemblyError", "MissingComponentError",
                               "MissingConfigurationError", "FixtureFallbackRefused",
                               "FixtureMarkerRefused", "ProductionValidationError"],
    }
    production_seam: dict[str, Any] = {
        "module": "examdata.integration.api.assembly",
        "module_file": str(Path(assembly.__file__).resolve()),
        "verified_by": "tests/test_w4_assembly.py",
    }
    for key, names in seam_entries.items():
        production_seam[key] = {
            name: callable(getattr(assembly, name, None)) for name in names
        }

    cli_block: dict[str, Any] = {"entry": "examdata.cli:app", "schema": cli.SCHEMA}
    try:
        all_commands, leaf_commands = _walk_subcommands(cli._parser(), "")
        cli_block.update({
            "commands": all_commands,
            "leaf_commands": leaf_commands,
            "leaf_count": len(leaf_commands),
            "declared_leaf_count": CLI_LEAF_COUNT,
            "leaf_count_matches_declared": len(leaf_commands) == CLI_LEAF_COUNT,
        })
    except Exception as exc:  # evidence must still land if introspection breaks
        cli_block["error"] = f"{type(exc).__name__}: {exc}"[:300]

    return {
        "schema": "integration.capability_map/1",
        "stamp": stamp,
        "candidate_root": str(candidate_root),
        "read_at": _utc_now(),
        "based_on": baseline_meta,
        "openapi": {
            "file": f"openapi_candidate_{stamp}.json",
            "v2_paths": len({row["path"] for row in registrations}),
            "v2_method_registrations": len(registrations),
            "binary_pairs": pairs,
        },
        "families": families_block,
        "family_join": {
            "key": "baseline family_index legacy_paths -> raw registry row legacy_path",
            "normalization": ("exact match first; a path that misses is retried with a "
                              "leading /api/v1 stripped, which resolves the baseline's "
                              "prefixed spelling of the unprefixed legacy mounts"),
        },
        "production_seam": production_seam,
        "cli_interface": cli_block,
        "systems": {
            "providers": [descriptor.to_dict()
                          for descriptor in fixture_dataset.registry.descriptors()],
            "unavailable_systems": dict(unavailable_systems),
        },
        "public_unavailable_behaviour": behaviour,
    }


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        raise SystemExit("usage: w4a_evidence.py <candidate-root> <out-dir> [stamp]")
    candidate_root = Path(argv[1]).resolve()
    out_dir = Path(argv[2]).resolve()
    stamp = argv[3] if len(argv) > 3 else time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    _prepare(candidate_root)
    out_dir.mkdir(parents=True, exist_ok=True)

    import examdata
    from examdata import cli
    from examdata.integration.api import assembly
    from examdata.integration.api.app import create_app
    from examdata.integration.api.dataset import UNAVAILABLE_SYSTEMS, default_dataset
    from examdata.integration.legacy import decisions
    from fastapi.testclient import TestClient

    baseline_path = out_dir.parent / "w4" / "route_inventory.json"
    if not baseline_path.is_file():
        raise SystemExit(f"baseline route inventory not found: {baseline_path}")
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    baseline_meta = {
        "path": "evidence/w4/route_inventory.json",
        "sha256": _sha256(baseline_path),
        "bytes": baseline_path.stat().st_size,
    }

    construction = "default"
    try:
        app = create_app()
    except Exception:
        construction = "fixture_fallback"
        app = create_app(dataset=default_dataset(operations_root=None))

    openapi = app.openapi()
    openapi_meta = _write_json(out_dir / f"openapi_candidate_{stamp}.json", openapi)
    registrations = _registrations(openapi)
    pairs = _binary_pairs(registrations)

    legacy_rows = decisions.rows()
    legacy = {
        "schema": decisions.SCHEMA,
        "registry_sha256": decisions.registry_sha256(),
        "routes": len(legacy_rows),
        "by_status": decisions.status_counts(),
        "by_mechanism": decisions.mechanism_counts(),
        "coverage": decisions.coverage_summary(),
    }

    refresh = _build_refresh(stamp, candidate_root, baseline, baseline_meta,
                             registrations, pairs, legacy, legacy_rows)
    refresh_meta = _write_json(
        out_dir / f"route_inventory_refresh_{stamp}.json", refresh)

    fixture_dataset = default_dataset(operations_root=None)
    try:
        response = TestClient(app).get("/api/v2/exam-systems")
        payload = response.json()
        data = payload.get("data") if isinstance(payload, dict) else None
        items = data.get("items") if isinstance(data, dict) else None
        behaviour: dict[str, Any] = {
            "status_code": response.status_code,
            "payload": payload,
            "unavailable_rows": [
                {"system": row.get("system"), "availability": row.get("availability"),
                 "providers": row.get("providers"), "reason": row.get("reason")}
                for row in (items or [])
                if isinstance(row, dict) and row.get("availability") == "unavailable"
            ],
        }
    except Exception as exc:
        behaviour = {"exception": f"{type(exc).__name__}: {exc}"[:500]}

    capability_map = _build_capability_map(
        stamp, candidate_root, baseline, baseline_meta, registrations, pairs,
        legacy_rows, assembly, cli, fixture_dataset, UNAVAILABLE_SYSTEMS, behaviour)
    capability_meta = _write_json(
        out_dir / f"capability_map_{stamp}.json", capability_map)

    summary = {
        "schema": "integration.w4a.evidence/1",
        "stamp": stamp,
        "candidate_root": str(candidate_root),
        "examdata_module": str(Path(examdata.__file__).resolve()),
        "app_construction": construction,
        "baseline": baseline_meta,
        "files": {
            f"openapi_candidate_{stamp}.json": openapi_meta,
            f"route_inventory_refresh_{stamp}.json": refresh_meta,
            f"capability_map_{stamp}.json": capability_meta,
        },
        "observations": {
            "v2_paths": len({row["path"] for row in registrations}),
            "v2_method_registrations": len(registrations),
            "binary_pairs": len(pairs),
            "legacy_routes": len(legacy_rows),
            "families": len(baseline["family_index"]),
            "cli_leaf_commands": capability_map["cli_interface"].get("leaf_count"),
        },
        "agreement": refresh["agreement"],
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
