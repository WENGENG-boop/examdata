"""Build the A01 route compatibility worksheet (plan section 5.5 / packet A01).

Merges the 71-route baseline with a fresh static re-extraction of the current
route modules, adds static AST enrichment (decorator kwargs, argument
defaults, return annotations, response-kind and side-effect call scans), and
applies the reviewed proposal rules for provider / v2_target /
compatibility_strategy / status.

Static only: reads route inventory JSONs and source text; never imports the
original application. Single write:
docs/integration/execution/A01_ROUTE_COMPATIBILITY_WORKSHEET.json
"""
from __future__ import annotations

import ast
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EV = ROOT / "docs/integration/execution/evidence/A01"
OUT = ROOT / "docs/integration/execution/A01_ROUTE_COMPATIBILITY_WORKSHEET.json"
BASELINE = ROOT / "docs/integration/ROUTE_INVENTORY_CURRENT.json"
REEXTRACT = EV / "route_inventory_reextract.json"

VERBS = {"get", "post", "put", "patch", "delete", "head", "options"}
RESPONSE_NAMES = {"JSONResponse", "Response", "FileResponse", "StreamingResponse",
                  "PlainTextResponse", "RedirectResponse", "ORJSONResponse", "HTMLResponse"}
SIDE_EFFECT_NAMES = {"open", "write_text", "write_bytes", "mkdir", "unlink", "rmdir", "rename",
                     "shutil", "subprocess", "create_subprocess_exec", "Popen", "remove",
                     "rmtree", "copytree", "copy", "system", "spawn", "check_output"}

COLUMNS = ["method", "legacy_path", "source_file", "handler", "native_parameters",
           "legacy_defaults", "legacy_success_shape", "legacy_error_shape", "binary_behavior",
           "side_effects", "provider", "v2_target", "compatibility_strategy", "fixture_ids",
           "test_ids", "status", "evidence_path", "deferred_reason"]


def sha256_file(p: Path) -> str | None:
    try:
        return hashlib.sha256(p.read_bytes()).hexdigest()
    except OSError:
        return None


def mtime_iso(p: Path) -> str:
    return datetime.fromtimestamp(p.stat().st_mtime).astimezone().isoformat(timespec="seconds")


def enrich_file(path: Path) -> dict:
    text = path.read_text(encoding="utf-8-sig")
    tree = ast.parse(text)
    out: dict = {}
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        info: dict = {"lineno": node.lineno}
        args = [a.arg for a in node.args.posonlyargs + node.args.args]
        info["args"] = args
        defaults: dict = {}
        dstart = len(args) - len(node.args.defaults)
        for i, d in enumerate(node.args.defaults):
            if isinstance(d, ast.Constant):
                defaults[args[dstart + i]] = ast.unparse(d)
        for a, d in zip(node.args.kwonlyargs, node.args.kw_defaults):
            if d is not None and isinstance(d, ast.Constant):
                defaults[a.arg] = ast.unparse(d)
        info["arg_defaults"] = defaults
        info["returns"] = ast.unparse(node.returns) if node.returns else ""
        doc = ast.get_docstring(node) or ""
        doc = doc.strip()
        info["doc_first_line"] = doc.splitlines()[0][:160] if doc else ""
        dec_kwargs: dict = {}
        for dec in node.decorator_list:
            if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute) and dec.func.attr in VERBS:
                for kw in dec.keywords:
                    if kw.arg:
                        try:
                            dec_kwargs[kw.arg] = ast.unparse(kw.value)
                        except (ValueError, RecursionError):
                            pass
        info["decorator_kwargs"] = dec_kwargs
        calls: set = set()
        for sub in ast.walk(node):
            if isinstance(sub, ast.Call):
                f = sub.func
                if isinstance(f, ast.Name):
                    calls.add(f.id)
                elif isinstance(f, ast.Attribute):
                    calls.add(f.attr)
        info["response_kinds"] = sorted(calls & RESPONSE_NAMES)
        info["side_effect_names"] = sorted(calls & SIDE_EFFECT_NAMES)
        out[node.name] = info
    return out


def curate(r: dict, info: dict, mt: dict) -> dict:
    f, p, h = r["file"], r["path"], r["handler"]
    keep = dict(provider="cie", v2_target="keep_legacy_only",
                compatibility_strategy="keep_working_migration_decision_pending_A12",
                status="not_started", deferred_reason="")

    if f.endswith("materials/router.py"):
        vt = {"list_materials": "proposed:/api/v2/materials",
              "get_material": "proposed:/api/v2/materials/{id}",
              "get_material_content": "proposed:/api/v2/materials/{id}/content",
              "get_cie_in_paper": "proposed:/api/v2/containers/{id}/resources"}.get(h, "tbd")
        return dict(provider="materials", v2_target=vt,
                    compatibility_strategy="defer_until_owner_release",
                    status="deferred_active_owner",
                    deferred_reason=f"active owner (Kimi) modifying materials subsystem; router mtime {mt['materials']}; plan section 8.5")

    if f.endswith("timetable/router.py"):
        vt = {"get_timetable": "proposed:/api/v2/timetables",
              "list_timetable_seasons": "proposed:/api/v2/timetables",
              "get_timetable_windows": "proposed:/api/v2/timetables/windows"}.get(h, "tbd")
        return dict(provider="timetable", v2_target=vt,
                    compatibility_strategy="defer_until_owner_release",
                    status="deferred_active_owner",
                    deferred_reason=f"active owner (Kimi) modifying timetable subsystem; router mtime {mt['timetable']}; plan section 8.5")

    if f.endswith("api/ielts.py"):
        prov = "ielts"
        strat = "add_v2_adapter_keep_legacy_defaults"
        if "/v2/" in p:
            return dict(provider=prov, v2_target="keep_legacy_namespace",
                        compatibility_strategy="keep_nested_legacy_namespace_unchanged",
                        status="not_started", deferred_reason="")
        if "coverage" in p:
            vt = "proposed:/api/v2/coverage"
        elif p.endswith("/info"):
            vt = "keep_legacy_only"
            strat = "keep_working_migration_decision_pending_A12"
        elif "script" in p or "audio" in p:
            vt = "proposed:/api/v2/containers/{id}/resources"
        elif "books/" in p:
            vt = "proposed:/api/v2/containers"
        elif "aggregate" in p:
            vt = "proposed:/api/v2/containers/{id}"
        elif "pdf" in p or "lfs" in p:
            vt = "proposed:/api/v2/resources"
        elif "reading" in p or "listening" in p:
            vt = "proposed:/api/v2/containers/{id}/questions"
        else:
            vt = "tbd_at_A08"
            strat = "pending_A08_adapter"
        keep.update(provider=prov, v2_target=vt, compatibility_strategy=strat)
        return keep

    if f.endswith("api/toefl.py"):
        prov = "toefl"
        strat = "add_v2_adapter_keep_legacy_defaults"
        if "coverage" in p:
            vt = "proposed:/api/v2/coverage"
        elif p.endswith("/info") or p.endswith("/jj"):
            vt = "keep_legacy_only"
            strat = "keep_working_migration_decision_pending_A12"
        elif p.endswith("/sets"):
            vt = "proposed:/api/v2/containers"
        elif p.endswith("/get") or p.endswith("/detail"):
            vt = "proposed:/api/v2/containers/{id}"
        elif p.endswith("/questions"):
            vt = "proposed:/api/v2/containers/{id}/questions"
        elif p.endswith("/search"):
            vt = "proposed:/api/v2/questions"
        else:
            vt = "tbd_at_A08"
            strat = "pending_A08_adapter"
        keep.update(provider=prov, v2_target=vt, compatibility_strategy=strat)
        return keep

    if f.endswith("api/unified.py"):
        prov = "mixed"
        strat = "add_v2_adapter_keep_legacy_defaults"
        if p == "/api/v1/boards":
            vt = "proposed:/api/v2/exam-systems"
        elif "cie-index-schema" in p or "indexes/cie" in p:
            prov = "cie"
            vt = "keep_legacy_only"
            strat = "keep_working_migration_decision_pending_A12"
        elif p in ("/api/v1/paper", "/api/v1/paper/index"):
            vt = "proposed:/api/v2/containers"
        elif p.startswith("/api/v1/question/"):
            vt = "proposed:/api/v2/questions/{id}"
        elif p == "/api/v1/search":
            vt = "proposed:/api/v2/questions"
        else:
            vt = "tbd"
            strat = "pending_A12"
        keep.update(provider=prov, v2_target=vt, compatibility_strategy=strat)
        return keep

    # app.py (root legacy family)
    mapping = {
        "/health": ("platform", "keep_legacy_only"),
        "/monitor": ("platform", "keep_legacy_only"),
        "/classifications": ("cie", "proposed:/api/v2/tags"),
        "/taxonomy": ("cie", "proposed:/api/v2/tags"),
        "/papers": ("cie", "proposed:/api/v2/containers"),
        "/papers/{paper_id}/tree": ("cie", "proposed:/api/v2/containers/{id}"),
        "/questions": ("cie", "proposed:/api/v2/questions"),
        "/questions/{question_id}": ("cie", "proposed:/api/v2/questions/{id}"),
        "/questions/{question_id}/explanation": ("cie", "keep_legacy_only"),
        "/questions/{question_id}/provenance": ("cie", "keep_legacy_only"),
        "/questions/{question_id}/similar": ("cie", "keep_legacy_only"),
        "/assets/{asset_id}": ("cie", "proposed:/api/v2/assets/{id}/content"),
        "/assets/{asset_id}/provenance": ("cie", "proposed:/api/v2/assets/{id}"),
        "/provenance/coverage": ("cie", "proposed:/api/v2/coverage"),
        "/review": ("platform", "keep_legacy_only"),
        "/sample": ("platform", "keep_legacy_only"),
        "/overrides": ("platform", "keep_legacy_only"),
        "/explanations/review-queue": ("platform", "keep_legacy_only"),
        "/paper-qa/query": ("platform", "keep_legacy_only"),
        "/paper-qa/resolve": ("platform", "keep_legacy_only"),
    }
    prov, vt = mapping.get(p, ("cie", "keep_legacy_only"))
    strat = ("add_v2_adapter_keep_legacy_defaults" if vt.startswith("proposed:")
             else "keep_working_migration_decision_pending_A12")
    keep.update(provider=prov, v2_target=vt, compatibility_strategy=strat)
    return keep


def main() -> int:
    local = datetime.now().astimezone()
    utc = local.astimezone(timezone.utc)
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    reex = json.loads(REEXTRACT.read_text(encoding="utf-8"))
    base_routes = {(r["method"], r["path"]): r for r in baseline["routes"]}
    reex_routes = {(r["method"], r["path"]): r for r in reex["routes"]}

    files = sorted({r["file"] for r in baseline["routes"]} | {r["file"] for r in reex["routes"]})
    enrichment = {f: enrich_file(ROOT / f) for f in files}

    mat_p = ROOT / "examdata/src/examdata/materials/router.py"
    tt_p = ROOT / "examdata/src/examdata/timetable/router.py"
    mt = {"materials": mtime_iso(mat_p) if mat_p.is_file() else "unknown",
          "timetable": mtime_iso(tt_p) if tt_p.is_file() else "unknown"}

    order = list(base_routes.keys()) + [k for k in reex_routes if k not in base_routes]
    rows = []
    for key in order:
        method, path = key
        cur = reex_routes.get(key) or base_routes[key]
        if key in reex_routes and key in base_routes:
            origin = "baseline_71"
        elif key in reex_routes:
            origin = "new_in_reextract"
        else:
            origin = "baseline_only"
        info = enrichment.get(cur["file"], {}).get(cur["handler"], {})
        curated = curate(cur, info, mt)
        if origin == "baseline_only":
            curated = dict(curated, status="blocked",
                           deferred_reason="present in baseline but not found in the A01 re-extraction; "
                                           "investigate before acceptance")
        params = info.get("args") or cur.get("parameters") or []
        parts = []
        if info.get("decorator_kwargs"):
            parts.append("decorator:" + json.dumps(info["decorator_kwargs"], ensure_ascii=False, sort_keys=True))
        if info.get("arg_defaults"):
            parts.append("arg_defaults:" + json.dumps(info["arg_defaults"], ensure_ascii=False, sort_keys=True))
        rk = info.get("response_kinds", [])
        if "FileResponse" in rk:
            binary = "binary_file_response_hint"
        elif "StreamingResponse" in rk:
            binary = "binary_streaming_hint"
        elif cur["file"].endswith(("api/ielts.py", "api/toefl.py")):
            binary = "json_via_node_cli"
        else:
            binary = "pending_A12"
        if cur["file"].endswith(("api/ielts.py", "api/toefl.py")):
            side = "spawns_short_lived_node_subprocess (indirect; see A01 gateway_spawn_facts)"
        elif info.get("side_effect_names"):
            side = "static_call_scan:" + ",".join(info["side_effect_names"])
        else:
            side = "none_detected_statically"
        row = {
            "method": method, "legacy_path": path, "source_file": cur["file"], "handler": cur["handler"],
            "native_parameters": ", ".join(params),
            "legacy_defaults": "; ".join(parts) if parts else "pending_A12",
            "legacy_success_shape": info.get("returns") or "pending_A12",
            "legacy_error_shape": "pending_A12",
            "binary_behavior": binary,
            "side_effects": side,
            "provider": curated["provider"],
            "v2_target": curated["v2_target"],
            "compatibility_strategy": curated["compatibility_strategy"],
            "fixture_ids": [], "test_ids": [],
            "status": curated["status"],
            "evidence_path": "docs/integration/execution/evidence/A01/route_inventory_reextract.json",
            "deferred_reason": curated["deferred_reason"],
            "row_origin": origin,
            "handler_doc_line": info.get("doc_first_line", ""),
        }
        rows.append(row)

    # validation
    problems = []
    missing_baseline = [k for k in base_routes if k not in {(r["method"], r["legacy_path"]) for r in rows}]
    if missing_baseline:
        problems.append(f"baseline rows missing: {len(missing_baseline)}")
    reex_set = {(r["method"], r["legacy_path"]) for r in rows if r["row_origin"] in ("baseline_71", "new_in_reextract")}
    if reex_set != set(reex_routes):
        problems.append("row set does not match re-extraction set")
    if any(r["status"] == "merged_pass" for r in rows):
        problems.append("merged_pass status present")
    for r in rows:
        if r["source_file"].endswith(("materials/router.py", "timetable/router.py")) and r["status"] != "deferred_active_owner":
            problems.append(f"active-owned row not deferred: {r['legacy_path']}")

    removed = [k for k in base_routes if k not in reex_routes]
    new = [k for k in reex_routes if k not in base_routes]
    status_counts: dict = {}
    provider_counts: dict = {}
    for r in rows:
        status_counts[r["status"]] = status_counts.get(r["status"], 0) + 1
        provider_counts[r["provider"]] = provider_counts.get(r["provider"], 0) + 1

    worksheet = {
        "schema": "examdata.integration.route_compatibility_worksheet/1",
        "generated_at_local": local.isoformat(timespec="seconds"),
        "generated_at_utc": utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "plan_ref": "MASTER_EXECUTION_PLAN_EN.md section 5.5; packet A01",
        "columns": COLUMNS,
        "extra_row_keys": ["row_origin", "handler_doc_line"],
        "notes": [
            "v2_target and compatibility_strategy are static A01 proposals; they are validated or revised in A07-A12.",
            "fixture_ids and test_ids are filled from A03 onward; status stays not_started until fixture tests exist.",
            "legacy_error_shape defaults to pending_A12 until compatibility tests classify error behavior.",
        ],
        "summary": {
            "row_count": len(rows),
            "baseline_count": len(base_routes),
            "new_in_reextract": len(new),
            "removed_from_reextract": len(removed),
            "status_counts": status_counts,
            "provider_counts": provider_counts,
            "baseline_coverage": f"{len(base_routes) - len(missing_baseline)}/{len(base_routes)}",
        },
        "source_hashes": {
            **{f: sha256_file(ROOT / f) for f in files},
            "docs/integration/ROUTE_INVENTORY_CURRENT.json": sha256_file(BASELINE),
            "docs/integration/execution/evidence/A01/route_inventory_reextract.json": sha256_file(REEXTRACT),
        },
        "route_source_mtimes": mt,
        "problems": problems,
        "rows": rows,
    }
    OUT.write_text(json.dumps(worksheet, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(worksheet["summary"], ensure_ascii=False, indent=2))
    print("removed:", [f"{m} {p}" for m, p in removed])
    print("new:", [f"{m} {p}" for m, p in new])
    if problems:
        print("problems:")
        for p_ in problems:
            print(" -", p_)
        print("WORKSHEET_BUILD: FAIL")
        return 1
    print("WORKSHEET_BUILD: PASS" + ("_WITH_WARNINGS" if removed else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
