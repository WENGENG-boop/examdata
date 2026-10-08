#!/usr/bin/env python3
"""A12 legacy compatibility registry builder (plan 5.5, packet A12).

Writes `integration-staging/src/examdata_integration/legacy/registry.json`:
one row per baseline route of the 71-route compatibility worksheet, classified
into the A12 mechanism vocabulary, with the legacy contract text refined from
the frozen static extraction (`evidence/A12/legacy_shape_extract.json`).

Inputs (all read-only, all inside the workspace):
  * A01 route worksheet                 - the 71-row baseline list
  * A12 legacy shape extract            - per-route params/returns/raises
  * legacy/bridge.py                    - the verbatim node-CLI envelope strings

Nothing here reads, imports or executes the original application, a database,
a service or the network; the only import from the project is the staged
`legacy` package. Re-running is deterministic except for the timestamps.

Usage:
    python integration-staging/tools/a12_build_registry.py [--check]
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.dont_write_bytecode = True

WS = Path(__file__).resolve().parents[2]
STAGING = WS / "integration-staging"
SRC = STAGING / "src"
EXECUTION = WS / "docs" / "integration" / "execution"
WORKSHEET_PATH = EXECUTION / "A01_ROUTE_COMPATIBILITY_WORKSHEET.json"
EXTRACT_PATH = EXECUTION / "evidence" / "A12" / "legacy_shape_extract.json"
REGISTRY_PATH = SRC / "examdata_integration" / "legacy" / "registry.json"

sys.path.insert(0, str(SRC))

from examdata_integration.legacy import bridge  # noqa: E402
from examdata_integration.legacy.decisions import (  # noqa: E402
    ALLOWED_STATUSES,
    MECHANISMS,
    SCHEMA,
    row_id,
)

# ---------------------------------------------------------------------------
# mechanism table (frozen A12 decision; asserted against the worksheet)
# ---------------------------------------------------------------------------

ADAPTER = "add_v2_adapter_keep_legacy_defaults"
KEEP_ONLY = "keep_legacy_only"
NAMESPACE = "keep_legacy_namespace"
BRIDGE = "bridge_node_cli_keep_legacy_payload"
DEFERRED = "deferred_active_owner"

#: (method, path) -> mechanism, for the 64 extracted routes.
MECHANISM_TABLE: dict[tuple[str, str], str] = {}
for _m, _paths in (
    ("GET", ["/papers", "/questions", "/questions/{question_id}", "/taxonomy",
             "/papers/{paper_id}/tree", "/classifications",
             "/assets/{asset_id}/provenance", "/provenance/coverage",
             "/assets/{asset_id}"]),
    ("GET", ["/api/v1/boards", "/api/v1/paper", "/api/v1/paper/index",
             "/api/v1/search", "/api/v1/question/{question_id}"]),
    ("GET", ["/api/v1/ielts/cam21/coverage", "/api/v1/ielts/coverage",
             "/api/v1/ielts/iprog/coverage", "/api/v1/ielts/ito/coverage",
             "/api/v1/ielts/lfs-coverage", "/api/v1/ielts/zhan/coverage"]),
    ("GET", ["/api/v1/toefl/coverage"]),
):
    for _p in _paths:
        MECHANISM_TABLE[(_m, _p)] = ADAPTER

for _m, _paths in (
    ("GET", ["/paper-qa/resolve", "/paper-qa/query", "/health",
             "/questions/{question_id}/similar", "/monitor", "/review",
             "/overrides", "/questions/{question_id}/explanation",
             "/questions/{question_id}/provenance", "/explanations/review-queue"]),
    ("GET", ["/api/v1/cie-index-schema", "/api/v1/indexes/cie/{sha256}",
             "/api/v1/indexes/cie/{sha256}/question"]),
    ("GET", ["/api/v1/ielts/info"]),
    ("GET", ["/api/v1/toefl/info"]),
):
    for _p in _paths:
        MECHANISM_TABLE[(_m, _p)] = KEEP_ONLY
MECHANISM_TABLE[("POST", "/sample")] = KEEP_ONLY

for _p in ["/api/v1/ielts/v2/asset/{asset_id}", "/api/v1/ielts/v2/books",
           "/api/v1/ielts/v2/coverage", "/api/v1/ielts/v2/info",
           "/api/v1/ielts/v2/question/{question_id}",
           "/api/v1/ielts/v2/questions/{book}/{test}",
           "/api/v1/ielts/v2/test/{book}/{test}"]:
    MECHANISM_TABLE[("GET", _p)] = NAMESPACE

for _p in ["/api/v1/ielts/books/{book}", "/api/v1/ielts/reading/{book}/{test}",
           "/api/v1/ielts/reading-enriched/{book}/{test}",
           "/api/v1/ielts/listening/{book}/{test}",
           "/api/v1/ielts/aggregate/{book}/{test}",
           "/api/v1/ielts/cam21/reading/{test}",
           "/api/v1/ielts/cam21/listening/{test}",
           "/api/v1/ielts/ito/script/{book}/{test}",
           "/api/v1/ielts/listening-script/{book}",
           "/api/v1/ielts/listening-audio/{book}/{test}",
           "/api/v1/ielts/pdf/{book}", "/api/v1/ielts/pdf21",
           "/api/v1/ielts/iprog/listening/{book}/{test}",
           "/api/v1/ielts/zhan/reading/{book}/{test}",
           "/api/v1/toefl/sets", "/api/v1/toefl/get", "/api/v1/toefl/questions",
           "/api/v1/toefl/detail", "/api/v1/toefl/search", "/api/v1/toefl/jj"]:
    MECHANISM_TABLE[("GET", _p)] = BRIDGE

#: the seven deferred routes, by row id (source files are protected in Phase A
#: and were therefore never parsed; only their existence in A01 is reused).
DEFERRED_ROWS = {
    "GET__api_v1_materials",
    "GET__api_v1_materials_cie_in_paper",
    "GET__api_v1_materials_material_id",
    "GET__api_v1_materials_material_id_content",
    "GET__api_v1_timetable",
    "GET__api_v1_timetable_seasons",
    "GET__api_v1_timetable_windows",
}

#: v2 target for every adapter row (frozen A12 decision).
V2_TARGETS: dict[str, str] = {
    "GET__papers": "containers.list (pagination total/limit/offset/items preserved)",
    "GET__questions": "questions.list (pagination total/limit/offset/items preserved)",
    "GET__questions_question_id": "questions.get",
    "GET__papers_paper_id_tree": "containers.get + containers.questions (native hierarchy preserved)",
    "GET__assets_asset_id": "assets.get + assets.content (binary passthrough)",
    "GET__api_v1_boards": "exam-systems + providers (auto_detect rules preserved)",
    "GET__api_v1_paper": ("composition: containers.get + resources.get + assets.content "
                          "(three exits preserved: download=false manifest, format=json base64, "
                          "default raw bytes/ZIP)"),
    "GET__api_v1_paper_index": "containers.list (edexcel mode=both; non-edexcel 422 preserved)",
    "GET__api_v1_search": "questions.list (keyword/subject filters)",
    "GET__api_v1_question_question_id": ("questions.get + answers + regions "
                                         "(source block preserved)"),
    "GET__api_v1_ielts_cam21_coverage": "coverage.get",
    "GET__api_v1_ielts_coverage": "coverage.get",
    "GET__api_v1_ielts_iprog_coverage": "coverage.get",
    "GET__api_v1_ielts_ito_coverage": "coverage.get",
    "GET__api_v1_ielts_lfs_coverage": "coverage.get",
    "GET__api_v1_ielts_zhan_coverage": "coverage.get",
    "GET__api_v1_toefl_coverage": "coverage.get",
    "GET__taxonomy": "none staged (closest v2 surface: tags.*; taxonomy outside v2 scope)",
    "GET__classifications": "none staged (no v2 classification surface)",
    "GET__assets_asset_id_provenance": "none staged (no v2 provenance surface)",
    "GET__provenance_coverage": "none staged (no v2 provenance surface)",
}

#: Hand-refined contract text where the extractor is coarse. Each value was
#: read from the original source text (static inspection) in this packet.
SUCCESS_OVERRIDES: dict[str, str] = {
    "GET__questions_question_id": ("get_question_bundle: {question, paper, children, assets, "
                                   "official_answers, mark_scheme_entries, taxonomy, difficulty, "
                                   "similar_questions(limit=10)}"),
    "GET__papers_paper_id_tree": ("get_paper_tree: {paper, roots[{id, number_path, label, depth, "
                                  "kind, marks, page_from, page_to, asset_count, children}]}"),
    "GET__api_v1_boards": "dict{schema_version, auto_detect, boards[...]}",
    "GET__api_v1_paper": ("three exits: dict{...manifest, board, board_source} (download=false); "
                          "dict{...base64 payload, board, board_source} (format=json); "
                          "raw bytes/ZIP Response (default)"),
    "GET__api_v1_paper_index": "delegates: index_paper(subject, year, season, paper, mode)",
    "GET__api_v1_indexes_cie_sha256": ("read_index(data_dir, sha256, question): the imported CIE AI "
                                       "index JSON (or one question inside it)"),
    "GET__api_v1_indexes_cie_sha256_question": ("binary: cropped question/mark-scheme Response "
                                                "(Content-Disposition); json: json_payload + source "
                                                "metadata merged"),
    "GET__api_v1_question_question_id": ("dict{question_id, board, board_source, source{board, "
                                         "board_canonical, subject_code, ...}, bundle}"),
    "GET__health": "dict{status, papers}",
    "GET__monitor": "dict{sync, health, review_queue, ...}",
    "GET__provenance_coverage": "dict{coverage, complete} (complete = every ratio >= 1.0)",
    "GET__classifications": "dict{count, conflicts, items}",
    "GET__taxonomy": "dict{roots, topic_count}",
    "GET__paper_qa_resolve": "delegates: paperqa_resolve(...).metadata()",
    "GET__sample": ("dict{marks_total, requested_marks, questions[...]}; 422 unless count or "
                    "marks_target is given"),
}

ERROR_OVERRIDES: dict[str, str] = {
    "GET__api_v1_paper": ("422: 'format must be binary or json'; PaperQAError.status_code -> "
                          "422/404/403/409/502 with str(exc); upstream parse error -> 502 "
                          "'Invalid upstream response'"),
    "GET__api_v1_paper_index": ("422: 'CIE uses whole PDFs and an externally imported AI index' "
                                "(non-edexcel board); PaperQAError.status_code with str(exc)"),
    "GET__api_v1_indexes_cie_sha256": ("404: 'Index or question not found'; 422: 'Invalid index or "
                                       "PDF sha256'"),
    "GET__api_v1_indexes_cie_sha256_question": ("422: 'format must be binary or json'; 404: 'Index "
                                                "or question not found'; PaperQAError.status_code "
                                                "with str(exc); 422: 'Invalid index'"),
}

FIXTURE_DATASET = "examdata_integration.api.dataset:default_dataset"
FIXTURE_NODE_STUB = "inline:offline_node_stub"

STAGED_NOTE = ("staged_pass: built and verified in the isolated harness only; merge/deployment "
               "remain Phase B (gates closed)")
NODE_NOTE = (" node-CLI contract raised through runtime/runner; staged divergences are constants "
             "in legacy/bridge.py (STAGED_DIVERGENCES)")
DEFERRED_NOTE = ("source is owned by the active Kimi session (materials/timetable); Phase A must "
                 "not read or modify it; stays deferred until the human releases the path")

CONTRACT_TESTS = "tests/test_legacy_bridge_contracts.py"
ADAPTER_TESTS = "tests/test_legacy_adapters.py"


# ---------------------------------------------------------------------------
# rendering helpers (pure functions over the extraction records)
# ---------------------------------------------------------------------------

_WRAPPERS = ("Query", "Body", "Header", "Path", "Form", "Cookie")


def _first_arg(expr: str) -> str:
    inner = expr[expr.index("(") + 1:]
    depth = 0
    out: list[str] = []
    for ch in inner:
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            if depth == 0:
                break
            depth -= 1
        elif ch == "," and depth == 0:
            break
        out.append(ch)
    return "".join(out).strip()


def _constraints(expr: str) -> str:
    bits = re.findall(r"(alias|ge|le|gt|lt|min_length|max_length|pattern)=([^,()]+)", expr)
    keep = [f"{k}={v.strip()}" for k, v in bits]
    return " (" + ", ".join(keep) + ")" if keep else ""


def render_default(expr: str) -> str:
    expr = expr.strip()
    for wrapper in _WRAPPERS:
        if expr.startswith(wrapper + "("):
            arg = _first_arg(expr)
            extras = _constraints(expr)
            return (arg if arg else "...") + extras
    return expr


def render_params(params: list[dict]) -> str:
    parts = []
    for p in params:
        if "default" in p:
            parts.append(f"{p['name']}={render_default(p['default'])}")
        else:
            parts.append(p["name"])
    return ", ".join(parts)


def render_defaults(params: list[dict]) -> str:
    parts = [f"{p['name']}={render_default(p['default'])}"
             for p in params if "default" in p]
    return "; ".join(parts) if parts else "none"


def render_returns(returns: list[dict]) -> str:
    parts: list[str] = []
    for r in returns:
        kind = r["kind"]
        if kind == "dict":
            keys = r.get("keys") or []
            text = "dict{" + ", ".join(keys) + "}" if keys else "dict"
        elif kind == "call":
            text = f"delegates:{r.get('call')}"
        elif kind == "name":
            text = f"name:{r.get('name')}"
        elif kind == "await":
            text = "node:" + _run_command(r.get("expr", ""))
        else:  # pragma: no cover - extraction vocabulary is fixed
            text = str(kind)
        if text not in parts:
            parts.append(text)
    return " | ".join(parts)


def _run_command(expr: str) -> str:
    match = re.search(r"_run\(\s*'([^']+)'", expr)
    return match.group(1) if match else expr


def render_raises(raises: list[dict]) -> str:
    parts: list[str] = []
    for r in raises:
        if r.get("exception") != "HTTPException":  # pragma: no cover - fixed vocabulary
            text = f"{r.get('exception')}: {r.get('detail') or ''}".strip()
        else:
            status = r.get("status")
            detail = r.get("detail")
            label = str(status) if status is not None else "dynamic"
            text = f"{label}: {detail if detail else '(dynamic detail)'}"
        if text not in parts:
            parts.append(text)
    return "; ".join(parts) if parts else "none extracted"


def node_success_shape(board: str, returns: list[dict]) -> str:
    commands: list[str] = []
    for r in returns:
        if r.get("kind") == "await":
            cmd = _run_command(r.get("expr", ""))
            if cmd not in commands:
                commands.append(cmd)
    listing = " | ".join(commands) if commands else "?"
    return (f"node CLI '{board}' [{listing}] payload passed through; dict payloads get "
            f"'board' defaulted to '{board}'")


def node_error_shape(board: str) -> str:
    profile = bridge.BOARD_PROFILES[board]
    bits = [
        f"503: '{profile.queue_full_detail}'",
        f"503: '{profile.display} 聚合器未找到（缺少 {profile.script}）；已尝试：<dirs>'",
        f"503: '{profile.runtime_missing_detail}'",
        "503: '无法启动 node：<exc>'",
        f"504: '{profile.display} 聚合器超时（><limit>s）：<cmd>'",
        f"502: '{profile.cli} 退出码 <rc>：<stderr tail>'",
        f"502: '{profile.invalid_json_detail}'",
    ]
    return "; ".join(bits)


#: binary behavior per row; rows not listed are plain JSON.
BINARY_BEHAVIOR: dict[str, str] = {
    "GET__assets_asset_id": ("binary_file_response: attachment; media_type asset.mime or "
                             "application/octet-stream; 410 '资产文件已丢失' / 403 '资产路径无效' "
                             "guards"),
    "GET__api_v1_ielts_v2_asset_asset_id": ("binary_file_response: inline; media_type meta.mime or "
                                            "application/octet-stream; 404 guards"),
    "GET__paper_qa_query": "binary_or_json (format=binary|json; 422 otherwise)",
    "GET__api_v1_paper": ("binary_or_json_or_manifest: download=false manifest | format=json base64 "
                          "| default raw bytes/ZIP with Content-Disposition + Content-Length"),
    "GET__api_v1_indexes_cie_sha256_question": ("binary_or_json (format=binary|json; "
                                                "Content-Disposition on the binary exit)"),
    "GET__api_v1_paper_index": "json (non-edexcel board -> 422)",
}


def node_backed(route: dict) -> bool:
    return any(r.get("kind") == "await" for r in route["returns"])


# ---------------------------------------------------------------------------
# build
# ---------------------------------------------------------------------------

def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build() -> dict:
    worksheet = json.loads(WORKSHEET_PATH.read_text(encoding="utf-8"))
    extract = json.loads(EXTRACT_PATH.read_text(encoding="utf-8"))
    extract_routes = {(r["method"], r["path"]): r for r in extract["routes"]}

    assert len(worksheet["rows"]) == 71, "worksheet is not the 71-row baseline"
    assert len(extract_routes) == 64, "extraction no longer carries 64 routes"

    # every extracted route must have a mechanism; the counts are frozen
    missing = [k for k in extract_routes if k not in MECHANISM_TABLE]
    assert not missing, f"routes missing from the mechanism table: {missing}"
    counts = {name: 0 for name in MECHANISMS}
    for mechanism in MECHANISM_TABLE.values():
        counts[mechanism] += 1
    counts[DEFERRED] = len(DEFERRED_ROWS)
    expected = {ADAPTER: 21, KEEP_ONLY: 16, NAMESPACE: 7, BRIDGE: 20, DEFERRED: 7}
    assert counts == expected, f"mechanism counts {counts} != {expected}"

    rows: list[dict] = []
    for ws_row in worksheet["rows"]:
        method, path = ws_row["method"], ws_row["legacy_path"]
        rid = row_id(method, path)
        if rid in DEFERRED_ROWS:
            mechanism = DEFERRED
        else:
            mechanism = MECHANISM_TABLE[(method, path)]
        route = extract_routes.get((method, path))

        test_ids = [f"{CONTRACT_TESTS}::test_static_contract[{rid}]"]
        fixture_ids: list[str] = []
        coverage_kind = "static_contract"
        status = "staged_pass"
        note = STAGED_NOTE
        success = ""
        error = ""
        binary = "json"
        params_text = ""
        defaults_text = ""

        if mechanism == DEFERRED:
            status = "deferred_active_owner"
            note = DEFERRED_NOTE
            binary = "not_extracted (source protected)"
            test_ids.append(f"{CONTRACT_TESTS}::test_deferred_active_owner_rows")
            coverage_kind = "static_contract"
        else:
            assert route is not None, f"no extraction for {method} {path}"
            params_text = render_params(route["params"])
            defaults_text = render_defaults(route["params"])
            success = SUCCESS_OVERRIDES.get(rid) or render_returns(route["returns"])
            if node_backed(route):
                board = "ielts" if "ielts" in ws_row["source_file"] else "toefl"
                if rid not in SUCCESS_OVERRIDES:
                    success = node_success_shape(board, route["returns"])
                error = node_error_shape(board)
                binary = "json_via_node_cli"
                coverage_kind = "envelope_contract"
                fixture_ids = [FIXTURE_NODE_STUB]
                if mechanism == BRIDGE:
                    note += NODE_NOTE
                    test_ids.append(f"{CONTRACT_TESTS}::test_node_bridge_envelope[{board}]")
            else:
                error = ERROR_OVERRIDES.get(rid) or render_raises(route["raises"])

            if mechanism == ADAPTER:
                test_ids.append(f"{ADAPTER_TESTS}::test_adapter_fixture_translation[{rid}]")
                if not node_backed(route):
                    coverage_kind = "fixture_translation"
                    fixture_ids = [FIXTURE_DATASET]
            elif mechanism == NAMESPACE:
                test_ids.append(f"{CONTRACT_TESTS}::test_namespace_rows_preserved")
                note += " nested legacy namespace preserved unchanged in v2"
            elif mechanism == KEEP_ONLY:
                test_ids.append(f"{CONTRACT_TESTS}::test_keep_legacy_only_rows_have_no_v2_claim")
                note += " legacy-only surface; no v2 route is claimed for it"

        if rid in BINARY_BEHAVIOR:
            binary = BINARY_BEHAVIOR[rid]
        assert status in ALLOWED_STATUSES
        assert mechanism in MECHANISMS

        rows.append({
            "row_id": rid,
            "method": method,
            "legacy_path": path,
            "source_file": ws_row["source_file"],
            "handler": ws_row["handler"],
            "line": route["line"] if route else None,
            "handler_doc_line": ws_row.get("handler_doc_line", ""),
            "mechanism": mechanism,
            "row_origin": ws_row.get("row_origin", "baseline_71"),
            "owner": "kimi_active" if mechanism == DEFERRED else "integration_staging",
            "native_parameters": params_text,
            "legacy_defaults": defaults_text,
            "legacy_success_shape": success,
            "legacy_error_shape": error,
            "binary_behavior": binary,
            "side_effects": ws_row.get("side_effects", ""),
            "provider": ws_row.get("provider", ""),
            "v2_target": V2_TARGETS.get(rid, ""),
            "fixture_ids": fixture_ids,
            "test_ids": test_ids,
            "status": status,
            "coverage_kind": coverage_kind,
            "evidence_path": ("docs/integration/execution/A01_ROUTE_COMPATIBILITY_WORKSHEET.json"
                              if mechanism == DEFERRED else
                              "docs/integration/execution/evidence/A12/compat_probe.json"),
            "deferred_reason": (note if mechanism == DEFERRED else ""),
            "notes": note,
        })

    adapter_targets = {rid for rid, mech in
                       ((r["row_id"], r["mechanism"]) for r in rows) if mech == ADAPTER}
    assert adapter_targets == set(V2_TARGETS), "adapter rows and v2 targets disagree"
    assert all(r["v2_target"] == "" for r in rows if r["mechanism"] != ADAPTER)

    return {
        "schema": SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "generated_at_local": datetime.now().astimezone().isoformat(),
        "plan_ref": "docs/integration/MASTER_EXECUTION_PLAN_EN.md packet A12 (plan 5.5)",
        "sources": {
            "worksheet": {
                "path": "docs/integration/execution/A01_ROUTE_COMPATIBILITY_WORKSHEET.json",
                "sha256": sha256_file(WORKSHEET_PATH),
            },
            "shape_extract": {
                "path": "docs/integration/execution/evidence/A12/legacy_shape_extract.json",
                "sha256": sha256_file(EXTRACT_PATH),
            },
            "build_tool": {
                "path": "integration-staging/tools/a12_build_registry.py",
                "sha256": sha256_file(Path(__file__)),
            },
        },
        "source_hashes": extract["source_hashes"],
        "mechanisms": counts,
        "allowed_statuses": list(ALLOWED_STATUSES),
        "row_count": len(rows),
        "rows": rows,
    }


def main(argv: list[str]) -> int:
    document = build()
    text = json.dumps(document, ensure_ascii=False, indent=2) + "\n"
    if "--check" in argv:
        current = REGISTRY_PATH.read_text(encoding="utf-8") if REGISTRY_PATH.exists() else ""
        if current and json.loads(current).get("rows") == document["rows"]:
            print("[ok] registry rows are current (timestamps ignored)")
            return 0
        print("[FAIL] registry.json is stale; rerun without --check")
        return 1
    REGISTRY_PATH.write_text(text, encoding="utf-8")
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    print(f"[ok] wrote {REGISTRY_PATH.relative_to(WS)} "
          f"({len(text)} bytes, sha256 {digest[:16]}...)")
    print(f"[ok] rows={document['row_count']} mechanisms={document['mechanisms']}")
    by_kind: dict[str, int] = {}
    for row in document["rows"]:
        by_kind[row["coverage_kind"]] = by_kind.get(row["coverage_kind"], 0) + 1
    print(f"[ok] coverage_kind={by_kind}")
    by_status: dict[str, int] = {}
    for row in document["rows"]:
        by_status[row["status"]] = by_status.get(row["status"], 0) + 1
    print(f"[ok] status={by_status}")
    node_rows = [r for r in document["rows"] if r["binary_behavior"] == "json_via_node_cli"]
    print(f"[ok] node-backed rows={len(node_rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
