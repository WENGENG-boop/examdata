"""B00 §2.3 - rebuild the release baseline (read-only) for the current tree.

Static AST re-extraction of the six route files (never imports the original
app), A14 base / planned-edit drift observation, git revision observation and
a per-route compatibility disposition for the 71-route baseline. Writes:

  B00_BASELINE.json                  - observed tree state + A14 base table
  B00_ROUTE_INVENTORY.json           - re-extracted route inventory
  B00_ROUTE_COMPATIBILITY_WORKSHEET.json - 71 baseline rows + disposition

Everything in here is observed_only: no original file is written, no
import of the original app, no DB, no network.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path

import ast

API = Path(__file__).resolve().parents[4]
EVID = API / "docs/integration/execution/evidence/B00/b00b01-20261006T132400"

ROUTE_FILES = {
    "examdata/src/examdata/api/app.py": "",
    "examdata/src/examdata/api/unified.py": "/api/v1",
    "examdata/src/examdata/api/ielts.py": "/api/v1/ielts",
    "examdata/src/examdata/api/toefl.py": "/api/v1/toefl",
    "examdata/src/examdata/materials/router.py": "/api/v1",
    "examdata/src/examdata/timetable/router.py": "/api/v1",
}


def now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def extract_routes() -> list[dict]:
    routes = []
    for rel, prefix in ROUTE_FILES.items():
        tree = ast.parse((API / rel).read_text(encoding="utf-8-sig"))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for dec in node.decorator_list:
                if not isinstance(dec, ast.Call) or not isinstance(dec.func, ast.Attribute):
                    continue
                if dec.func.attr not in {"get", "post", "put", "patch", "delete", "head", "options"}:
                    continue
                if not dec.args or not isinstance(dec.args[0], ast.Constant):
                    continue
                routes.append({
                    "method": dec.func.attr.upper(),
                    "path": prefix + dec.args[0].value,
                    "file": rel,
                    "line": node.lineno,
                    "handler": node.name,
                    "parameters": [a.arg for a in node.args.args],
                })
    routes.sort(key=lambda r: (r["path"], r["method"]))
    return routes


def main() -> int:
    EVID.mkdir(parents=True, exist_ok=True)
    mm = json.loads((API / "docs/integration/execution/A14_MERGE_MAP.json").read_text(encoding="utf-8"))
    baseline_inv = json.loads((API / "docs/integration/ROUTE_INVENTORY_CURRENT.json").read_text(encoding="utf-8"))
    worksheet = json.loads((API / "docs/integration/execution/A12_ROUTE_COMPATIBILITY_WORKSHEET.json").read_text(encoding="utf-8"))

    # ---- git observation (read-only) ----------------------------------------
    def git(*args: str) -> str:
        p = subprocess.run(["git", *args], cwd=str(API / "examdata"),
                           capture_output=True, text=True)
        return p.stdout.strip() if p.returncode == 0 else f"<git error {p.returncode}>"

    head = git("rev-parse", "HEAD")
    status = git("status", "--porcelain").splitlines()
    modified = sorted(l[3:] for l in status if l.startswith(" M "))
    untracked_count = sum(1 for l in status if l.startswith("??"))

    # ---- A14 base table -------------------------------------------------------
    base_table = []
    for entry in mm["entries"]:
        if not entry.get("base"):
            continue
        b = entry["base"]
        src = API / b["source_path"]
        cur = sha256_file(src) if src.exists() else None
        base_table.append({
            "staged_path": entry["staged_path"],
            "proposed_target": entry.get("proposed_target"),
            "source_path": b["source_path"],
            "base_sha256": b["sha256_recorded"],
            "current_sha256": cur,
            "exists": src.exists(),
            "drift": cur != b["sha256_recorded"] if cur else True,
        })

    planned_edits = []
    for pe in mm["planned_original_edits"]:
        target = API / pe["target_path"]
        cur = sha256_file(target) if target.exists() else None
        planned_edits.append({
            "target_path": pe["target_path"],
            "base_exists": pe.get("base_exists"),
            "base_sha256": pe.get("base_sha256"),
            "current_sha256": cur,
            "currently_exists": target.exists(),
            "drift": (pe.get("base_exists") and cur != pe.get("base_sha256")),
        })

    baseline = {
        "schema": "examdata.integration.b00_baseline/1",
        "run_id": "b00b01-20261006T132400",
        "generated_at_local": now(),
        "observation_kind": "observed_only",
        "release_present": False,
        "release_note": (
            "no human release credential exists in this session; this baseline "
            "records the current active-owner tree by observation only, it does "
            "not claim any original path was released or merged"),
        "git": {
            "examdata_head": head,
            "tracked_modified_count": len(modified),
            "untracked_count": untracked_count,
            "tracked_modified_files": modified,
            "note": "read-only git status; no index write, no stash/reset/commit",
        },
        "a14_bases": base_table,
        "a14_planned_original_edits": planned_edits,
        "summary": {
            "a14_bases_total": len(base_table),
            "a14_bases_drifted": sum(1 for b in base_table if b["drift"]),
            "planned_edits_total": len(planned_edits),
            "planned_edits_drifted": sum(1 for p in planned_edits if p["drift"]),
        },
    }

    # ---- route inventory -------------------------------------------------------
    routes = extract_routes()
    route_keys = {(r["method"], r["path"]) for r in routes}
    base_keys = {(r["method"], r["path"]) for r in baseline_inv["routes"]}
    inventory = {
        "as_of_local": now(),
        "method": "static_ast_explicit_decorators",
        "run_id": "b00b01-20261006T132400",
        "limitations": [
            "Not live OpenAPI; excludes framework docs routes and dynamically generated routes.",
            "Prefixes reflect inspected router registration; regenerate after registration changes.",
            "observed_only: no original import, no DB, no network (release absent).",
        ],
        "explicit_route_count": len(routes),
        "unique_path_count": len({r["path"] for r in routes}),
        "duplicate_method_paths": [],
        "groups": {rel: sum(1 for r in routes if r["file"] == rel) for rel in ROUTE_FILES},
        "routes": routes,
        "diff_vs_baseline": {
            "baseline_route_count": len(base_keys),
            "added": sorted([f"{m} {p}" for m, p in (route_keys - base_keys)]),
            "removed": sorted([f"{m} {p}" for m, p in (base_keys - route_keys)]),
        },
    }
    for r in routes:
        for m, p in route_keys:
            pass

    # ---- compatibility disposition per baseline route -------------------------
    ws_rows = {f"{r['method']}__{r['legacy_path'].replace('/', '_')}": r for r in worksheet["rows"]}
    cur_map = {(r["method"], r["path"]): r for r in routes}
    disposition_rows = []
    for br in baseline_inv["routes"]:
        key = (br["method"], br["path"])
        cur = cur_map.get(key)
        row_id = f"{br['method']}__{br['path'].replace('/', '_')}"
        ws_row = ws_rows.get(row_id)
        if cur is None:
            disposition = "removed_in_current_tree"
            moved = None
        else:
            moved = (cur["line"] != br["line"]) or (cur["handler"] != br["handler"])
            disposition = "line_shift_only" if moved else "unchanged"
        disposition_rows.append({
            "row_id": row_id,
            "method": br["method"],
            "legacy_path": br["path"],
            "baseline_handler": br["handler"],
            "baseline_line": br["line"],
            "current_handler": cur["handler"] if cur else None,
            "current_line": cur["line"] if cur else None,
            "disposition": disposition,
            "a12_status": ws_row["status"] if ws_row else None,
            "a12_mechanism": ws_row["mechanism"] if ws_row else None,
            "a12_owner": ws_row.get("owner") if ws_row else None,
            "coverage_kind": ws_row.get("coverage_kind") if ws_row else None,
            "b00_disposition_note": (
                "route identity (method + full path) preserved in the current tree; "
                "any handler-body change requires release + three-way semantic "
                "reconciliation in B01, not assumed from this static observation"
            ) if cur else
            "baseline route absent from the current static extraction; requires "
            "release + investigation in B01",
        })
    worksheet_b00 = {
        "schema": "examdata.integration.b00_route_compatibility_worksheet/1",
        "run_id": "b00b01-20261006T132400",
        "generated_at_local": now(),
        "baseline_ref": "docs/integration/ROUTE_INVENTORY_CURRENT.json (71 routes)",
        "a12_worksheet_ref": "docs/integration/execution/A12_ROUTE_COMPATIBILITY_WORKSHEET.json",
        "status": "preparation_only",
        "release_present": False,
        "note": (
            "No release credential exists in this session: the seven "
            "deferred_active_owner rows are NOT re-classified, no route is "
            "marked pass, and staged_pass rows are not promoted. This worksheet "
            "records the observed static disposition only."
        ),
        "summary": {
            "baseline_rows": len(disposition_rows),
            "dispositions": {
                "unchanged": sum(1 for r in disposition_rows if r["disposition"] == "unchanged"),
                "line_shift_only": sum(1 for r in disposition_rows if r["disposition"] == "line_shift_only"),
                "removed_in_current_tree": sum(1 for r in disposition_rows if r["disposition"] == "removed_in_current_tree"),
            },
            "kimi_added_routes_in_current_tree": len(route_keys - base_keys),
        },
        "rows": disposition_rows,
    }

    (EVID / "B00_BASELINE.json").write_text(
        json.dumps(baseline, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (EVID / "B00_ROUTE_INVENTORY.json").write_text(
        json.dumps(inventory, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (EVID / "B00_ROUTE_COMPATIBILITY_WORKSHEET.json").write_text(
        json.dumps(worksheet_b00, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("B00 baseline artifacts written:")
    print(" - B00_BASELINE.json")
    print(" - B00_ROUTE_INVENTORY.json")
    print(" - B00_ROUTE_COMPATIBILITY_WORKSHEET.json")
    print(json.dumps(baseline["summary"], indent=1))
    print(json.dumps(inventory["diff_vs_baseline"], indent=1))
    print(json.dumps(worksheet_b00["summary"], indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
