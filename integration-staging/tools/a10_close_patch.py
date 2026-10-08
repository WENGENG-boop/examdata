#!/usr/bin/env python3
"""Build the A10 ledger close patch (docs/integration/execution/execution-ledger.json).

Computes the input hashes over the true inputs plus the A10 write set (excluding
the closing-checks transcript, which is produced *after* the ledger closes, and
this patch file itself), and emits a JSON object to be merged into the A10 task
record by ``integration-staging/tools/ledger_update.py --patch-file``.

Phase A tool (integration-staging/tools/). Stdlib only.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True

WS = Path(__file__).resolve().parents[2]
STAGING = WS / "integration-staging"
EXEC = WS / "docs" / "integration" / "execution"
OUT = STAGING / "runtime" / "ledger-patches" / "A10_close.json"

ROOTS = [STAGING.as_posix(), EXEC.as_posix()]

INPUTS = [
    "docs/integration/EXECUTOR_PROMPT_EN.md",
    "docs/integration/MASTER_EXECUTION_PLAN_EN.md",
    "docs/integration/ROUTE_INVENTORY_CURRENT.json",
    "docs/PROJECT_STATUS.md",
    "docs/integration/execution/execution-ledger.json",
    "docs/integration/execution/A09_REPORT.md",
    "docs/integration/execution/A09_STORE_DECISION.md",
    "docs/integration/execution/evidence/A09/final_checks.txt",
    "docs/integration/execution/evidence/A09/catalog_stdout.txt",
    "docs/integration/execution/evidence/A09/pytest_run_stdout.txt",
    # frozen A04 contracts the envelope and views map onto (read-only dependency)
    "integration-staging/src/examdata_integration/contracts/models.py",
    "integration-staging/src/examdata_integration/contracts/base.py",
    "integration-staging/src/examdata_integration/contracts/enums.py",
    "integration-staging/src/examdata_integration/contracts/canonical.py",
    "integration-staging/src/examdata_integration/contracts/quality.py",
    "integration-staging/src/examdata_integration/contracts/ids.py",
    "integration-staging/src/examdata_integration/contracts/jsonschema_lite.py",
    # frozen A05/A07/A08 provider layer and A09 catalog the API reads
    "integration-staging/src/examdata_integration/providers/capabilities.py",
    "integration-staging/src/examdata_integration/providers/results.py",
    "integration-staging/src/examdata_integration/providers/registry.py",
    "integration-staging/src/examdata_integration/providers/fixtures.py",
    "integration-staging/src/examdata_integration/catalog/model.py",
    "integration-staging/src/examdata_integration/catalog/store.py",
    "integration-staging/src/examdata_integration/catalog/builder.py",
    "integration-staging/src/examdata_integration/catalog/revision.py",
    # frozen A05 provider fixtures the dataset builds its snapshot from
    "integration-staging/fixtures/synthetic/cie/cie-index-synthetic.json",
    "integration-staging/fixtures/synthetic/edexcel/index-synthetic.json",
    "integration-staging/fixtures/synthetic/ielts/questions-synthetic.json",
    # frozen A02-A09 harness the A10 tests run under
    "integration-staging/pytest.ini",
    "integration-staging/tests/conftest.py",
    "integration-staging/tools/run_staged_tests.sh",
    "integration-staging/tools/ledger_update.py",
    "integration-staging/src/examdata_integration/testing/guards.py",
]

WRITE_GLOBS = [
    # A10 source files only: the api package is entirely new
    "integration-staging/src/examdata_integration/api/*.py",
    "integration-staging/tools/a10_*.py",
    # A10 test files only: test_api_*.py is a new, packet-owned prefix
    "integration-staging/tests/test_api_*.py",
    "integration-staging/runtime/ledger-patches/A10_close.json",
    "docs/integration/execution/A10_REPORT.md",
    "docs/integration/execution/evidence/A10/*",
]

# produced only after the ledger closes: listed but never hashed into the patch
POST_CLOSE = {
    "docs/integration/execution/evidence/A10/final_checks.txt",
}

COMMANDS = [
    {"seq": 1, "purpose": "Create the A10 evidence directory.",
     "tool": "Bash",
     "command": "mkdir -p docs/integration/execution/evidence/A10",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0, "evidence": None},
    {"seq": 2, "purpose": "Write the api package entry point (docstring only, imports nothing to avoid cycles).",
     "tool": "Write",
     "command": "Write tool: integration-staging/src/examdata_integration/api/__init__.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/src/examdata_integration/api/__init__.py"},
    {"seq": 3, "purpose": "Write the envelope: 5.1 builders, ApiError, ERROR_MAP, EMITTABLE_STATUSES, sanitizers.",
     "tool": "Write",
     "command": "Write tool: integration-staging/src/examdata_integration/api/envelope.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/src/examdata_integration/api/envelope.py"},
    {"seq": 4, "purpose": "Write pagination: limit parsing and revision-bound cursor paging over the frozen A09 codec.",
     "tool": "Write",
     "command": "Write tool: integration-staging/src/examdata_integration/api/pagination.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/src/examdata_integration/api/pagination.py"},
    {"seq": 5, "purpose": "Write the dataset: frozen-fixture providers, A09 builder snapshot, deferred fixture families.",
     "tool": "Write",
     "command": "Write tool: integration-staging/src/examdata_integration/api/dataset.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/src/examdata_integration/api/dataset.py"},
    {"seq": 6, "purpose": "Write the views: CatalogView lookups/filters and ProviderView multi-provider dispatch mapping.",
     "tool": "Write",
     "command": "Write tool: integration-staging/src/examdata_integration/api/view.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/src/examdata_integration/api/view.py"},
    {"seq": 7, "purpose": "Write the route registry: RouteSpec single source of truth, advertised/entry links.",
     "tool": "Write",
     "command": "Write tool: integration-staging/src/examdata_integration/api/links.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/src/examdata_integration/api/links.py"},
    {"seq": 8, "purpose": "Write the OpenAPI helpers: recursive route walk, runtime/spec pairs, response validation.",
     "tool": "Write",
     "command": "Write tool: integration-staging/src/examdata_integration/api/openapi.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/src/examdata_integration/api/openapi.py"},
    {"seq": 9, "purpose": "Write the app factory and all 29 v2 handlers (no docs/openapi routes served).",
     "tool": "Write",
     "command": "Write tool: integration-staging/src/examdata_integration/api/app.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/src/examdata_integration/api/app.py"},
    {"seq": 10, "purpose": "Write the five A10 test modules (envelope, routes, pagination, links/openapi, dataset).",
     "tool": "Write",
     "command": "Write tool: integration-staging/tests/test_api_{envelope,routes,pagination,links_openapi,dataset}.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/tests/"},
    {"seq": 11, "purpose": "First full staged suite run: 566 passed, 10 failed (the first regression signal for the new API).",
     "tool": "Bash",
     "command": "bash integration-staging/tools/run_staged_tests.sh -q",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 1,
     "evidence": "integration-staging/tests/"},
    {"seq": 12, "purpose": "Fix the 405 handler: document FRAMEWORK_STATUSES={405} in envelope.py and allow it in ApiError.__post_init__.",
     "tool": "Edit",
     "command": "Edit tool: integration-staging/src/examdata_integration/api/envelope.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/src/examdata_integration/api/envelope.py"},
    {"seq": 13, "purpose": "Fix view.filter: duck-type Mapping rows via _matches_mapping so the deferred dict fixtures can be filtered.",
     "tool": "Edit",
     "command": "Edit tool: integration-staging/src/examdata_integration/api/view.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/src/examdata_integration/api/view.py"},
    {"seq": 14, "purpose": "Fix tag_questions: answer an explicit deferred envelope instead of 404, matching /tags.",
     "tool": "Edit",
     "command": "Edit tool: integration-staging/src/examdata_integration/api/app.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/src/examdata_integration/api/app.py"},
    {"seq": 15, "purpose": "Fix test expectations against the verified implementation (dataset systems/keys, links hrefs, routes paths).",
     "tool": "Edit",
     "command": "Edit tool: integration-staging/tests/test_api_{dataset,links_openapi,routes}.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/tests/"},
    {"seq": 16, "purpose": "Second full staged suite run: 575 passed, 1 failed (the links href template comparison).",
     "tool": "Bash",
     "command": "bash integration-staging/tools/run_staged_tests.sh -q",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 1,
     "evidence": "integration-staging/tests/"},
    {"seq": 17, "purpose": "Fix the links test: compare entry-link hrefs after substituting {id} for the placeholder.",
     "tool": "Edit",
     "command": "Edit tool: integration-staging/tests/test_api_links_openapi.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/tests/test_api_links_openapi.py"},
    {"seq": 18, "purpose": "Third full staged suite run to green: 576 passed, 0 failed.",
     "tool": "Bash",
     "command": "bash integration-staging/tools/run_staged_tests.sh -q",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/tests/"},
    {"seq": 19, "purpose": "Write the 82-scenario offline API probe.",
     "tool": "Write",
     "command": "Write tool: integration-staging/tools/a10_probe_api.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/tools/a10_probe_api.py"},
    {"seq": 20, "purpose": "First probe run exited 1: the container identity scenario read item['native_locator'], but the detail exposes native_identity.",
     "tool": "Bash",
     "command": "examdata/.venv/Scripts/python.exe integration-staging/tools/a10_probe_api.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 1,
     "evidence": "integration-staging/tools/a10_probe_api.py"},
    {"seq": 21, "purpose": "Fix the probe expectations against the verified implementation (info paths/systems, limit codes, identity fields).",
     "tool": "Edit",
     "command": "Edit tool: integration-staging/tools/a10_probe_api.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/tools/a10_probe_api.py"},
    {"seq": 22, "purpose": "Second probe run exited 1: the answer scenario read item['candidates'], but the answer item exposes conflicts.",
     "tool": "Bash",
     "command": "examdata/.venv/Scripts/python.exe integration-staging/tools/a10_probe_api.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 1,
     "evidence": "integration-staging/tools/a10_probe_api.py"},
    {"seq": 23, "purpose": "Fix the probe answer-shape assertion to read conflicts and manual_decision.",
     "tool": "Edit",
     "command": "Edit tool: integration-staging/tools/a10_probe_api.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/tools/a10_probe_api.py"},
    {"seq": 24, "purpose": "Third probe run exited 1: the sanitization scenario used json.dumps without importing json.",
     "tool": "Bash",
     "command": "examdata/.venv/Scripts/python.exe integration-staging/tools/a10_probe_api.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 1,
     "evidence": "integration-staging/tools/a10_probe_api.py"},
    {"seq": 25, "purpose": "Add the missing json import to the probe.",
     "tool": "Edit",
     "command": "Edit tool: integration-staging/tools/a10_probe_api.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/tools/a10_probe_api.py"},
    {"seq": 26, "purpose": "Run the probe to green (82/82).",
     "tool": "Bash",
     "command": "examdata/.venv/Scripts/python.exe integration-staging/tools/a10_probe_api.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/tools/a10_probe_api.py"},
    {"seq": 27, "purpose": "Remove dead code: the unused filters parameter of _list_response and the unused _filters helper.",
     "tool": "Edit",
     "command": "Edit tool: integration-staging/src/examdata_integration/api/app.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/src/examdata_integration/api/app.py"},
    {"seq": 28, "purpose": "Fourth full staged suite run after the cleanup: 576 passed, 0 failed.",
     "tool": "Bash",
     "command": "bash integration-staging/tools/run_staged_tests.sh -q",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/tests/"},
    {"seq": 29, "purpose": "Capture the probe transcript.",
     "tool": "Bash",
     "command": "examdata/.venv/Scripts/python.exe integration-staging/tools/a10_probe_api.py > docs/integration/execution/evidence/A10/api_stdout.txt",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "docs/integration/execution/evidence/A10/api_stdout.txt"},
    {"seq": 30, "purpose": "Capture the staged-suite transcript (576 passed).",
     "tool": "Bash",
     "command": "bash integration-staging/tools/run_staged_tests.sh -q > docs/integration/execution/evidence/A10/pytest_run_stdout.txt",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "docs/integration/execution/evidence/A10/pytest_run_stdout.txt"},
    {"seq": 31, "purpose": "Write the A10 report.",
     "tool": "Write", "command": "Write tool: docs/integration/execution/A10_REPORT.md",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "docs/integration/execution/A10_REPORT.md"},
    {"seq": 32, "purpose": "Write the A10 closing-checks runner.",
     "tool": "Write", "command": "Write tool: integration-staging/tools/a10_final_checks.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/tools/a10_final_checks.py"},
    {"seq": 33, "purpose": "Write the A10 ledger close-patch builder.",
     "tool": "Write", "command": "Write tool: integration-staging/tools/a10_close_patch.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": 0,
     "evidence": "integration-staging/tools/a10_close_patch.py"},
    {"seq": 34, "purpose": "Run the A10 closing checks (after the ledger is closed).",
     "tool": "Bash",
     "command": "examdata/.venv/Scripts/python.exe integration-staging/tools/a10_final_checks.py",
     "cwd": "C:/Users/weo/Desktop/api", "exit_code": None,
     "evidence": "docs/integration/execution/evidence/A10/final_checks.txt"},
]

TEST_RESULTS = [
    {"check": "API probe: 82/82 scenarios PASS offline (A10_PROBE: PASS)",
     "result": "pass", "exit_code": 0,
     "evidence": "docs/integration/execution/evidence/A10/api_stdout.txt",
     "label": "synthetic_fixture",
     "note": "route inventory agreement + OpenAPI agreement; envelope shape and request-id echo/replacement; 404/400/422/405 error paths; native identity and native question order; answer conflict kept unresolved and missing answer slot left empty; region document hash + unverified status; IELTS regions 422 unsupported_capability; audio never dispatches; pagination limit/cursor with stale 409 and tampered 400; deferred families labelled; coverage never a percentage without a denominator; no original path leaks."},
    {"check": "Staged suite passes offline: 576 tests (146 new A10 + 430 A02-A09), 0 failures",
     "result": "pass", "exit_code": 0,
     "evidence": "docs/integration/execution/evidence/A10/pytest_run_stdout.txt",
     "label": "synthetic_fixture",
     "note": "30 envelope + 53 routes + 21 pagination + 19 links/openapi + 23 dataset tests, in the isolated harness with the module and network guards active. The single warning is the starlette/httpx TestClient deprecation notice."},
    {"check": "Runtime routes, the OpenAPI document and the advertised links agree exactly",
     "result": "pass", "exit_code": 0,
     "evidence": "integration-staging/tests/test_api_links_openapi.py",
     "label": "static_inspection",
     "note": "runtime_pairs(app) == spec_pairs(app) == advertised_pairs() (29 each); agreement_problems(app) == []; the five binary routes are registered nowhere and advertised nowhere, only recorded as deferred with a reason."},
    {"check": "The api package never imports or runs the original application",
     "result": "pass", "exit_code": 0,
     "evidence": "integration-staging/tests/test_api_dataset.py",
     "label": "static_inspection",
     "note": "every api module imports only the staged examdata_integration tree and stdlib; no api file names an original path or the original app module."},
    {"check": "Multi-provider dispatch never answers an empty 200",
     "result": "pass", "exit_code": 0,
     "evidence": "integration-staging/tests/test_api_routes.py",
     "label": "synthetic_fixture",
     "note": "any provider success yields data with a partial marker and warnings; when every provider fails the dispatch maps to the plan 5.2 status (422/503/404/502/500) rather than an empty success."},
]

FAILURES = [
    {"what": "First full staged suite run exited 1: 566 passed, 10 failed. The first real regression signal for the new API.",
     "evidence": "command row seq 11 (exit_code 1)",
     "resolution": "Two were implementation defects (the 405 handler raising because 405 is outside the 5.2 map; view.filter crashing on dict fixture rows) and eight were test expectations written against an assumed rather than observed shape. All fixed; see command rows seq 12-15."},
    {"what": "Second full staged suite run exited 1: 575 passed, 1 failed - the entry-links test compared a PLACEHOLDER href against the {id} route template.",
     "evidence": "command row seq 16 (exit_code 1)",
     "resolution": "Fixed in test_api_links_openapi.py: the href is compared after substituting {id} for PLACEHOLDER. Re-run to green (command row seq 18)."},
    {"what": "First probe run exited 1: the container identity scenario read item['native_locator'], but the detail payload exposes native_identity.",
     "evidence": "command row seq 20 (exit_code 1)",
     "resolution": "Fixed in a10_probe_api.py against the verified payload shape (command row seq 21)."},
    {"what": "Second probe run exited 1: the answer scenario read item['candidates'], but the answer item exposes conflicts (a list of two unresolved candidates).",
     "evidence": "command row seq 22 (exit_code 1)",
     "resolution": "Fixed in a10_probe_api.py to read conflicts and manual_decision (command row seq 23)."},
    {"what": "Third probe run exited 1: the sanitization scenario called json.dumps without importing json.",
     "evidence": "command row seq 24 (exit_code 1)",
     "resolution": "Added the missing import (command row seq 25); probe then passed 82/82 (command row seq 26)."},
]

REMAINING_GAPS = [
    "Only synthetic fixtures and in-process TestClient requests are used: no original database, no upstream fetch, no CIE batch resume, no service start.",
    "The five binary routes (syllabuses/resources/questions/assets/materials content, and the question crop) are deferred to A11: not registered, not advertised, only recorded with a reason.",
    "Resources and assets are one catalog entity; the plan's resource roles (QP/MS/ER/GT/insert/audio) are not modelled by the frozen fixtures.",
    "Materials, syllabuses, timetables and jobs are served from labelled synthetic fixtures; tags have no staged source. Active materials and historical timetable integration stay deferred to the active owner.",
    "The two UNKNOWN encodings ('__unknown__' in catalog dicts, 'unknown' in contract models) were not unified, because that would require editing the closed A09 to_dict; both are permitted by the plan.",
    "405 is framework-level routing outside the plan 5.2 map and is documented as such (FRAMEWORK_STATUSES).",
]

EVIDENCE_PATHS = [
    "docs/integration/execution/A10_REPORT.md",
    "docs/integration/execution/evidence/A10/api_stdout.txt",
    "docs/integration/execution/evidence/A10/final_checks.txt",
    "docs/integration/execution/evidence/A10/pytest_run_stdout.txt",
    "docs/integration/execution/execution-ledger.json",
    "integration-staging/runtime/ledger-patches/A10_close.json",
    "integration-staging/src/examdata_integration/api/__init__.py",
    "integration-staging/src/examdata_integration/api/app.py",
    "integration-staging/src/examdata_integration/api/dataset.py",
    "integration-staging/src/examdata_integration/api/envelope.py",
    "integration-staging/src/examdata_integration/api/links.py",
    "integration-staging/src/examdata_integration/api/openapi.py",
    "integration-staging/src/examdata_integration/api/pagination.py",
    "integration-staging/src/examdata_integration/api/view.py",
    "integration-staging/tests/test_api_dataset.py",
    "integration-staging/tests/test_api_envelope.py",
    "integration-staging/tests/test_api_links_openapi.py",
    "integration-staging/tests/test_api_pagination.py",
    "integration-staging/tests/test_api_routes.py",
    "integration-staging/tools/a10_close_patch.py",
    "integration-staging/tools/a10_final_checks.py",
    "integration-staging/tools/a10_probe_api.py",
]

NEXT_ACTION = ("A11 - binary responses (plan section 11): implement the five deferred content/crop routes with "
               "200/206/416 range handling and response budgets, path-traversal and drive/UNC-path rejection, "
               "wrong-media-type handling, disconnect and temp-file cleanup, using small immutable synthetic or "
               "copied samples; flip the five DEFERRED_SPECS rows to implemented and re-run the staged suite and probe.")

NOTES = ("All A10 inputs are synthetic fixtures or frozen contract/provider/catalog/harness sources; no original "
         "file was read and nothing was fetched. Five commands exited nonzero during development - two full staged "
         "suite runs (10 failures, then 1 failure) and three probe iterations - all resolved in-packet and recorded "
         "in failures. The api package is entirely new, so no frozen file was edited: the A00-A09 modules and their "
         "hashed fixtures are untouched. The app is built with docs/openapi/redoc URLs disabled so the runtime "
         "routes equal exactly the 29 /api/v2 routes while app.openapi() still builds in memory. Everything is "
         "staged: nothing is merged and nothing is deployed, and all seven Phase B gates stay closed.")


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def rel(p: Path) -> str:
    return p.relative_to(WS).as_posix()


def main() -> int:
    out_rel = rel(OUT)
    write_set: set[str] = set()
    for pattern in WRITE_GLOBS:
        for p in WS.glob(pattern):
            if p.is_file():
                write_set.add(rel(p))
    # the patch file is a meta-artefact of closing: never hashed against itself;
    # POST_CLOSE artefacts are produced after the ledger closes and must not be
    # listed as changed files (their hash would be stale by construction)
    write_set.discard(out_rel)
    write_set -= POST_CLOSE

    changed_files = sorted(write_set)
    roots_rel = [rel(STAGING) + "/", rel(EXEC) + "/"]
    outside = [f for f in changed_files
               if not any(f.startswith(r) for r in roots_rel)]

    input_hashes: dict[str, str] = {}
    for r in INPUTS:
        p = WS / r
        if p.is_file():
            input_hashes[r] = sha256_file(p)
    for r in changed_files:
        if r in POST_CLOSE:
            continue
        input_hashes[r] = sha256_file(WS / r)

    patch = {
        "dependencies": ["A09"],
        "allowed_write_roots": ROOTS,
        "blocked_by": [],
        "input_hashes": dict(sorted(input_hashes.items())),
        "changed_files": changed_files,
        "commands": COMMANDS,
        "exit_codes": [c["exit_code"] for c in COMMANDS],
        "test_results": TEST_RESULTS,
        "evidence_paths": EVIDENCE_PATHS,
        "failures": FAILURES,
        "remaining_gaps": REMAINING_GAPS,
        "next_action": NEXT_ACTION,
        "notes": NOTES,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(patch, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8", newline="\n")
    print(f"wrote {out_rel}")
    print(f"changed_files={len(changed_files)} input_hashes={len(input_hashes)} "
          f"exit_codes={patch['exit_codes']} outside_roots={outside}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
