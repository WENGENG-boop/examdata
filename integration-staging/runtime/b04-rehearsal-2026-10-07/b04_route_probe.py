"""B04 route probe: composing the staged v2 routes into the shared application.

Runs entirely inside the private target-layout candidate and the two Phase A
write roots. It proves, for packet B04 ("Register v2 routes in the shared
application", MASTER_EXECUTION_PLAN_EN.md 891-895):

* the candidate imports at the target layout (explicit
  ``EXAMDATA_INTEGRATION_ROOT`` only: no directory-name heuristic, no
  ``PYTHONPATH``, no staging-root override) and every product module resolves
  inside the candidate;
* the A12 route-compatibility worksheet still describes 71 baseline rows, and
  the standalone v2 app serves exactly the 34 implemented registry routes with
  the shared envelope contract;
* the registry has no shadowing or intersecting patterns: every spec's concrete
  path resolves to its own route first (34 GET + 5 HEAD);
* composing the v2 app into a synthetic legacy host carrying all 71 baseline
  routes keeps every legacy response byte-identical (inventory + 7 synthetic
  extras), appends exactly one router entry, and adds exactly the document
  paths the registry lists; v2-prefix envelopes replace legacy shapes only
  under the v2 prefix (6 controls);
* the composed document is the "differences intentional and documented"
  acceptance evidence: unchanged pre-attach operations, unique operation IDs,
  v2 operation IDs equal to the standalone document's, binary rows documented
  with their media types and without a default ``application/json``, and every
  non-binary 200 schema exactly the shared envelope;
* the negative mechanics are pinned: a raw ``include_router`` serves v2 but
  keeps legacy error shapes; an unscoped handler install rewrites legacy
  404/422/500 bytes; a ``mount`` answers under the wrong route and documents
  nothing; double and late attaches are refused without mutation; non-FastAPI
  hosts are refused.

Nothing here writes to the candidate, the original tree, a database, a service
or frozen evidence. Scratch space is confined to the run directory's
``evidence/tmp``. The real merge into ``examdata/src/examdata/api/app.py``, real
Node execution and real source validation stay ``not_run`` because their gates
are closed.

Exit code 0 = every check passed; 1 = at least one check failed; 2 = the probe
refused to run (missing explicit configuration).
"""
from __future__ import annotations

import hashlib
import importlib
import json
import os
import re
import shutil
import sys
import traceback
from collections import Counter
from pathlib import Path

RUN_DIR = Path(__file__).resolve().parent
RUN_ID = "b04-rehearsal-2026-10-07"

#: Environment this probe refuses to run against by accident.
_REQUIRED_ENV = ("B04_CANDIDATE_ROOT", "B04_WORKSPACE_ROOT", "B04_TMP_DIR",
                 "EXAMDATA_INTEGRATION_ROOT")

SKIP_DIRS = {"__pycache__", ".pytest_cache"}

#: The compose hook is frozen for this rehearsal; any drift fails the probe.
EXPECTED_COMPOSE_SHA = "e220c007dba89d544cdd4c841c2ff5ab200b01e61556ba41a22a70c45f306efd"

#: The framework default for an unhandled server error: plain-text bytes with a
#: fixed sha, pinned so the scoped fallback is checked against the real host.
PLAIN_500_SHA = "e41656eb2ba6c6293bf6dd928e5a88cdbc50535cab661c1969e0f598e497ed62"

CHECKS: list[dict] = []
NEGATIVE_CHECKS: list[str] = []
POSITIVE_CHECKS: list[str] = []
NOT_RUN: list[dict] = []
MODULE_ORIGINS: dict[str, str] = {}


def check(name: str, ok: bool, detail: object = "", *, polarity: str = "neutral") -> bool:
    record = {"name": name, "ok": bool(ok), "detail": str(detail)[:600]}
    CHECKS.append(record)
    if polarity == "negative":
        NEGATIVE_CHECKS.append(name)
    elif polarity == "positive":
        POSITIVE_CHECKS.append(name)
    return bool(ok)


def run_section(tag: str, fn) -> None:
    try:
        fn()
    except Exception as exc:  # noqa: BLE001 - a crashed section must still be reported
        tail = traceback.format_exc(limit=4).strip().splitlines()[-3:]
        check(f"{tag}_section_completed", False,
              f"unexpected {type(exc).__name__}: {exc} | " + " | ".join(tail))


def sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def tree_digest(base: Path, exclude: tuple[str, ...] = ()) -> dict:
    entries: list[tuple[str, str]] = []
    for p in sorted(base.rglob("*")):
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        if p.is_file():
            rel = p.relative_to(base).as_posix()
            if rel in exclude:
                continue
            entries.append((rel, sha256(p)))
    digest = hashlib.sha256()
    for rel, h in entries:
        digest.update(f"{rel}\0{h}\n".encode("utf-8"))
    return {"files": len(entries), "excludes": list(exclude), "sha256": digest.hexdigest()}


def tree_snapshot(base: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for p in sorted(base.rglob("*")):
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        if p.is_file():
            out[p.relative_to(base).as_posix()] = sha256(p)
    return out


def load_json(path: Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def canonical_digest(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=True)
                          .encode("utf-8")).hexdigest()


def concrete(path: str) -> str:
    """One concrete URL for a possibly-braced route path (ordering probes)."""
    return re.sub(r"\{([^}]+)\}",
                  lambda m: "synthetic-" + re.sub(r"[^A-Za-z0-9_-]", "-", m.group(1)),
                  path)


def json_or_none(response):
    try:
        return response.json()
    except Exception:  # noqa: BLE001 - a non-JSON body is a datum, not a crash
        return None


def main() -> int:
    missing = [name for name in _REQUIRED_ENV if not os.environ.get(name)]
    if missing:
        print(json.dumps({"ok": False, "refused": True,
                          "error": f"missing required environment variable(s): {missing}"},
                         ensure_ascii=True, indent=2))
        return 2

    candidate = Path(os.environ["B04_CANDIDATE_ROOT"]).resolve()
    workspace = Path(os.environ["B04_WORKSPACE_ROOT"]).resolve()
    tmp_root = Path(os.environ["B04_TMP_DIR"]).resolve()
    src = candidate / "src"
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(src))

    scratch = tmp_root / "routing"
    if scratch.exists():
        shutil.rmtree(scratch)
    scratch.mkdir(parents=True, exist_ok=True)

    before_snapshot = tree_snapshot(candidate)
    fixtures_digest_before = tree_digest(candidate / "fixtures" / "synthetic")
    contracts_digest_before = tree_digest(candidate / "contracts")

    # -- imports (after the candidate src is on the path) -------------------- #
    from fastapi import FastAPI, Query  # noqa: E402
    from starlette.testclient import TestClient  # noqa: E402

    from examdata.integration.api import links  # noqa: E402
    from examdata.integration.api import openapi as api_openapi  # noqa: E402
    from examdata.integration.api.app import create_app  # noqa: E402
    from examdata.integration.api.compose import attach_v2  # noqa: E402
    from examdata.integration.api.dataset import SYLLABUS_FIXTURES  # noqa: E402
    from examdata.integration.api.envelope import SCHEMA_VERSION as V2_SCHEMA_VERSION  # noqa: E402
    from examdata.integration.contracts import quality as quality_module  # noqa: E402
    from examdata.integration.contracts.enums import EntityKind  # noqa: E402
    from examdata.integration.runtime.manifest import load_manifest_set  # noqa: E402

    # -- the shared worksheet inventory and the synthetic legacy host -------- #
    worksheet_path = (workspace / "docs" / "integration" / "execution"
                      / "A12_ROUTE_COMPATIBILITY_WORKSHEET.json")
    worksheet_doc = load_json(worksheet_path)
    WORKSHEET_ROWS: list[dict] = worksheet_doc["rows"]

    by_path: dict[str, set[str]] = {}
    for row in WORKSHEET_ROWS:
        by_path.setdefault(row["legacy_path"], set()).add(row["method"].upper())

    INVENTORY_PROBES = [
        (f"inv:{row['method'].upper()} {row['legacy_path']}", row["method"].upper(),
         concrete(row["legacy_path"]))
        for row in WORKSHEET_ROWS
    ]
    BRAIDED_ROW = next(row["legacy_path"] for row in WORKSHEET_ROWS
                       if "{" in row["legacy_path"])
    EXTRA_PROBES = [
        ("extra:numbers_default", "GET", "/synthetic-legacy/numbers", None),
        ("extra:numbers_422", "GET", "/synthetic-legacy/numbers", {"limit": "abc"}),
        ("extra:boom_500", "GET", "/synthetic-legacy/boom", None),
        ("extra:echo_405", "GET", "/synthetic-legacy/echo", None),
        ("extra:echo_200", "POST", "/synthetic-legacy/echo", None),
        ("extra:absent_404", "GET", "/api/legacy/absent", None),
        ("extra:braced_post_405", "POST", concrete(BRAIDED_ROW), None),
    ]
    CONTROL_REQUESTS = [
        ("ctl:typed_422", "GET", "/api/v2/__synthetic_typed", {"q": "abc"}),
        ("ctl:v2_boom", "GET", "/api/v2/__synthetic_boom", None),
        ("ctl:jobs_404", "GET", "/api/v2/jobs/does-not-exist", None),
        ("ctl:unknown_404", "GET", "/api/v2/__synthetic_absent", None),
        ("ctl:post_info_405", "POST", "/api/v2/info", None),
        ("ctl:info_200", "GET", "/api/v2/info", None),
    ]

    def make_min_host() -> FastAPI:
        host = FastAPI()

        @host.get("/api/legacy/papers")
        def papers():
            return {"legacy": True}

        @host.get("/synthetic-legacy/numbers")
        def numbers(limit: int = 0):
            return {"limit": limit}

        @host.get("/synthetic-legacy/boom")
        def boom():
            raise RuntimeError("synthetic legacy failure")

        return host

    def make_host() -> FastAPI:
        host = FastAPI()

        def stub():
            return {"legacy_route": "stub", "synthetic": True}

        for path, methods in by_path.items():
            host.add_api_route(path, stub, methods=sorted(methods))

        @host.get("/synthetic-legacy/numbers")
        def numbers(limit: int = Query(0)):
            return {"limit": limit}

        @host.get("/synthetic-legacy/boom")
        def boom():
            raise RuntimeError("synthetic legacy failure")

        @host.post("/synthetic-legacy/echo")
        def echo():
            return {"echo": True}

        @host.get("/api/v2/__synthetic_typed")
        def typed(q: int = Query(1)):
            return {"q": q}

        @host.get("/api/v2/__synthetic_boom")
        def v2_boom():
            raise RuntimeError("synthetic v2-prefix failure")

        return host

    def probe_tuple(client: TestClient, method: str, url: str, params=None) -> list:
        response = client.request(method, url, params=params)
        return [response.status_code, response.headers.get("content-type"),
                hashlib.sha256(response.content).hexdigest()]

    def min_probe_all(client: TestClient) -> dict:
        return {
            "papers_200": probe_tuple(client, "GET", "/api/legacy/papers"),
            "numbers_default": probe_tuple(client, "GET", "/synthetic-legacy/numbers"),
            "numbers_422": probe_tuple(client, "GET", "/synthetic-legacy/numbers", {"limit": "abc"}),
            "boom_500": probe_tuple(client, "GET", "/synthetic-legacy/boom"),
            "absent_404": probe_tuple(client, "GET", "/api/legacy/absent"),
        }

    def full_probe_all(client: TestClient) -> dict:
        out: dict[str, list] = {}
        for name, method, url in INVENTORY_PROBES:
            out[name] = probe_tuple(client, method, url)
        for name, method, url, params in EXTRA_PROBES:
            out[name] = probe_tuple(client, method, url, params)
        for name, method, url, params in CONTROL_REQUESTS:
            out[name] = probe_tuple(client, method, url, params)
        return out

    def route_table(host: FastAPI) -> list:
        return [[getattr(route, "path", None), sorted(getattr(route, "methods", None) or []),
                 type(route).__name__] for route in host.routes]

    # ====================================================================== #
    # A: environment, origins, isolation, schema, node discovery
    # ====================================================================== #
    A_DISCOVERY: dict = {}

    def section_a() -> None:
        root_env = os.environ.get("EXAMDATA_INTEGRATION_ROOT")
        check("A_env_root_is_candidate",
              Path(root_env).resolve() == candidate,
              f"EXAMDATA_INTEGRATION_ROOT={root_env!r} candidate={candidate}")
        check("A_no_staging_override",
              "EXAMDATA_INTEGRATION_STAGING_ROOT" not in os.environ,
              "EXAMDATA_INTEGRATION_STAGING_ROOT must not be staged")
        check("A_no_pythonpath", not os.environ.get("PYTHONPATH"),
              f"PYTHONPATH={os.environ.get('PYTHONPATH')!r}")
        check("A_candidate_src_first_on_path",
              Path(sys.path[0]).resolve() == src.resolve(), f"sys.path[0]={sys.path[0]!r}")

        module_names = [
            "examdata.integration.api.app",
            "examdata.integration.api.compose",
            "examdata.integration.api.links",
            "examdata.integration.api.openapi",
            "examdata.integration.api.envelope",
            "examdata.integration.api.dataset",
            "examdata.integration.api.binary",
            "examdata.integration.api.pagination",
            "examdata.integration.api.view",
            "examdata.integration.catalog.builder",
            "examdata.integration.catalog.model",
            "examdata.integration.catalog.store",
            "examdata.integration.catalog.revision",
            "examdata.integration.providers.registry",
            "examdata.integration.providers.fixtures",
            "examdata.integration.providers.capabilities",
            "examdata.integration.contracts.quality",
            "examdata.integration.contracts.ids",
            "examdata.integration.contracts.enums",
            "examdata.integration.legacy.bridge",
            "examdata.integration.runtime.manifest",
        ]
        outside: list[str] = []
        for name in module_names:
            module = importlib.import_module(name)
            file = Path(module.__file__).resolve()
            MODULE_ORIGINS[name] = str(file)
            if not str(file).startswith(str(candidate) + os.sep):
                outside.append(f"{name} -> {file}")
        check("A_module_origins_within_candidate", not outside,
              "all candidate" if not outside else "; ".join(outside))

        venv = workspace / "examdata" / ".venv"
        offenders: list[str] = []
        for name, module in list(sys.modules.items()):
            file = getattr(module, "__file__", None)
            if not file:
                continue
            resolved = Path(file).resolve()
            text = str(resolved)
            if text.startswith(str(workspace / "examdata")):
                if not text.startswith(str(venv)):
                    offenders.append(f"{name} -> {text}")
        check("A_no_original_tree_module_loaded", not offenders,
              "no module from the original tree" if not offenders else "; ".join(offenders[:5]))

        product_root = candidate / "src" / "examdata" / "integration"
        import_hits: list[str] = []
        pattern = re.compile(r"^\s*(?:from|import)\s+.*(?:testing\.guards|testing\.node_guard|"
                             r"testing\s+import\s+(?:guards|node_guard))")
        for path in sorted(product_root.rglob("*.py")):
            if "testing" in path.relative_to(product_root).parts:
                continue
            for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if pattern.match(line):
                    import_hits.append(f"{path.relative_to(candidate)}:{lineno}")
        check("A_product_no_testing_guard_imports", not import_hits,
              "no product import of testing guards" if not import_hits else "; ".join(import_hits))

        schema_dir = candidate / "contracts" / "schema"
        schema_files = sorted(schema_dir.glob("*.json"))
        bad: list[str] = []
        for path in schema_files:
            try:
                load_json(path)
            except Exception as exc:  # noqa: BLE001
                bad.append(f"{path.name}: {exc}")
        check("A_schema_files_parse", len(schema_files) == 28 and not bad,
              f"{len(schema_files)} schema file(s); malformed: {bad or 'none'}")

        transitions = load_json(candidate / "contracts" / "quality-transitions.json")
        dims = transitions.get("dimensions", {})
        code_dims = quality_module.DIMENSIONS
        dim_problems: list[str] = []
        if set(dims) != set(code_dims):
            dim_problems.append(f"dimension names differ: file={sorted(dims)} code={sorted(code_dims)}")
        for name, values in dims.items():
            cls = code_dims.get(name)
            if cls is None:
                continue
            if {member.value for member in cls} != set(values):
                dim_problems.append(f"{name}: file={sorted(values)} code={sorted(m.value for m in cls)}")
        check("A_quality_dimensions_match_code", not dim_problems, dim_problems or "all dimensions agree")

        identity_keys = load_json(candidate / "contracts" / "identity-keys.json")
        kinds = sorted(identity_keys.get("kinds", {}))
        kind_problems = [name for name in kinds if not _coerce_ok(EntityKind, name)]
        check("A_identity_kinds_match_code",
              len(kinds) == len(list(EntityKind)) and not kind_problems,
              f"{len(kinds)} kind(s); unrecognised: {kind_problems or 'none'}")

        components_manifest = candidate / "components" / "manifest.json"
        manifest_set = load_manifest_set(components_manifest, deployment_root=candidate,
                                         require_entry_point=True)
        entry_ids = manifest_set.ids()
        entry = manifest_set.get("fake_cli")
        entry_path = str(entry.entry_path(candidate)) if entry else None
        problems = [p.to_dict() for p in manifest_set.problems]
        check("A_node_discovery_candidate_root",
              entry_ids == ["fake_cli"] and not problems
              and entry_path is not None
              and Path(entry_path).is_file()
              and Path(entry_path).resolve().is_relative_to(candidate),
              f"ids={entry_ids} problems={problems} entry={entry_path}")
        A_DISCOVERY.update({
            "ids": entry_ids,
            "problems": problems,
            "entry_path": entry_path,
            "deployment_root": str(candidate),
            "cwd": str(Path.cwd()),
        })

        legacy = importlib.import_module("examdata.integration.legacy.bridge")
        check("A_legacy_bridge_entry_imports_within_candidate",
              Path(legacy.__file__).resolve().is_relative_to(candidate),
              str(legacy.__file__))

    run_section("A", section_a)

    # ====================================================================== #
    # B: worksheet inventory + the standalone v2 registry and its ordering
    # ====================================================================== #
    WORKSHEET: dict = {}
    B_STATE: dict = {}

    def section_b() -> None:
        raw = worksheet_path.read_bytes()
        methods = Counter(row["method"].upper() for row in WORKSHEET_ROWS)
        post_rows = [row for row in WORKSHEET_ROWS if row["method"].upper() != "GET"]
        recorded_app_hash = (worksheet_doc.get("rescan", {})
                             .get("recorded_source_hashes", {})
                             .get("examdata/src/examdata/api/app.py"))
        WORKSHEET.update({
            "path": str(worksheet_path),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "rows": len(WORKSHEET_ROWS),
            "methods": dict(sorted(methods.items())),
            "post_row": {"method": post_rows[0]["method"].upper(),
                         "path": post_rows[0]["legacy_path"]} if len(post_rows) == 1 else None,
            "baseline_count": worksheet_doc.get("summary", {}).get("baseline_count"),
            "recorded_app_hash": recorded_app_hash,
        })
        check("B_worksheet_rows_71", len(WORKSHEET_ROWS) == 71,
              f"{len(WORKSHEET_ROWS)} row(s)")
        check("B_worksheet_methods_70_get_1_post", dict(methods) == {"GET": 70, "POST": 1},
              dict(sorted(methods.items())))
        check("B_worksheet_post_row_is_sample",
              len(post_rows) == 1 and post_rows[0]["legacy_path"] == "/sample",
              WORKSHEET["post_row"])
        check("B_worksheet_baseline_count_71",
              worksheet_doc.get("summary", {}).get("baseline_count") == 71,
              f"baseline_count={worksheet_doc.get('summary', {}).get('baseline_count')!r}")
        check("B_worksheet_app_hash_recorded",
              recorded_app_hash == "753749fac1361481034e0920c0543e3e621c0d638c21558c73852fd3237fef5d",
              str(recorded_app_hash))
        v2_rows = [row["legacy_path"] for row in WORKSHEET_ROWS
                   if row["legacy_path"].startswith("/api/v2")]
        check("B_worksheet_no_v2_paths", not v2_rows, v2_rows or "no /api/v2 legacy paths")

        v2 = create_app()
        specs = links.ROUTE_SPECS
        unique_paths = len({spec.full_path for spec in specs})
        check("B_v2_spec_counts",
              len(specs) == 34 and len(links.IMPLEMENTED_SPECS) == 34
              and not links.DEFERRED_SPECS
              and len([s for s in specs if s.binary]) == 5 and unique_paths == 34,
              f"specs={len(specs)} implemented={len(links.IMPLEMENTED_SPECS)} "
              f"deferred={len(links.DEFERRED_SPECS)} binary={len([s for s in specs if s.binary])} "
              f"unique_paths={unique_paths}")

        runtime = api_openapi.runtime_pairs(v2)
        spec = api_openapi.spec_pairs(v2)
        advertised = set(links.advertised_pairs())
        check("B_v2_runtime_spec_registry_agree",
              runtime == spec == advertised and len(runtime) == 34,
              f"runtime={len(runtime)} spec={len(spec)} advertised={len(advertised)}")
        runtime_head = api_openapi.runtime_head_pairs(v2)
        spec_head = api_openapi.spec_head_pairs(v2)
        expected_head = {("HEAD", s.full_path) for s in specs if s.binary}
        check("B_v2_head_pairs_binary_only",
              runtime_head == spec_head == expected_head and len(runtime_head) == 5,
              f"runtime_head={len(runtime_head)} spec_head={len(spec_head)}")
        problems = api_openapi.agreement_problems(v2)
        check("B_v2_agreement_problems_empty", problems == [], problems or "no agreement problems")

        B_STATE["standalone_doc"] = v2.openapi()
        routes = list(api_openapi.iter_routes(v2.routes))

        get_fail: list[str] = []
        head_fail: list[str] = []
        for route in routes:
            methods = getattr(route, "methods", None) or set()
            if "GET" in methods:
                target = concrete(route.path)
                first = _first_match(routes, "GET", target)
                if first != route.path:
                    get_fail.append(f"{target} -> {first}")
        for route in routes:
            methods = getattr(route, "methods", None) or set()
            if "HEAD" in methods:
                target = concrete(route.path)
                first = _first_match(routes, "HEAD", target)
                if first != route.path:
                    head_fail.append(f"{target} -> {first}")
        get_cases = len([r for r in routes if "GET" in (getattr(r, "methods", None) or set())])
        head_cases = len([r for r in routes if "HEAD" in (getattr(r, "methods", None) or set())])
        check("B_ordering_get_first_match_own_route",
              len(get_fail) == 0 and get_cases == 34,
              f"{get_cases} GET case(s); failures={get_fail[:3] or 'none'}", polarity="positive")
        check("B_ordering_head_first_match_own_route",
              len(head_fail) == 0 and head_cases == 5,
              f"{head_cases} HEAD case(s); failures={head_fail[:3] or 'none'}", polarity="positive")

        shadow: list[str] = []
        for i, route in enumerate(routes):
            if "{" not in route.path:
                continue
            for later in routes[i + 1:]:
                if later.path != route.path and route.path_regex.match(concrete(later.path)):
                    shadow.append(f"{route.path} shadows {later.path}")
        check("B_no_param_static_shadowing", not shadow, shadow[:3] or "no shadowed routes",
              polarity="positive")

        inter_problems: list[str] = []
        pairs = 0
        # GET and HEAD variants share one path pattern by design; compare each
        # distinct pattern exactly once (same-pattern pairs are the same route,
        # not an intersection risk).
        regex_by_path: dict[str, object] = {}
        for route in routes:
            regex_by_path.setdefault(route.path, route.path_regex)
        paths = sorted(regex_by_path)
        for i in range(len(paths)):
            for j in range(i + 1, len(paths)):
                pairs += 1
                witness = _unify(paths[i], paths[j])
                if witness is None:
                    continue
                if regex_by_path[paths[i]].match(witness) and regex_by_path[paths[j]].match(witness):
                    inter_problems.append(f"{paths[i]} x {paths[j]} @ {witness}")
        check("B_no_pattern_intersections", not inter_problems,
              f"{pairs} distinct-pattern pair(s); intersections={inter_problems[:3] or 'none'}",
              polarity="positive")

        B_STATE["ordering"] = {
            "get_cases": get_cases, "head_cases": head_cases,
            "get_failures": get_fail, "head_failures": head_fail,
            "shadowing_problems": shadow,
            "pairs_checked": pairs, "intersection_problems": inter_problems,
        }

    run_section("B", section_b)

    # ====================================================================== #
    # C: legacy baseline + composed host (byte identity and v2 envelopes)
    # ====================================================================== #
    C_STATE: dict = {}

    def section_c() -> None:
        with TestClient(make_host(), raise_server_exceptions=False) as client:
            baseline = full_probe_all(client)
        C_STATE["baseline"] = baseline

        host2 = make_host()
        C_STATE["host2"] = host2
        C_STATE["route_count_pre"] = len(host2.routes)
        pre_doc = host2.openapi()
        C_STATE["pre_doc"] = pre_doc
        C_STATE["pre_doc_paths"] = len(pre_doc["paths"])
        check("C_host_shape_pre_attach",
              len(host2.routes) == 80 and len(pre_doc["paths"]) == 76
              and host2.middleware_stack is None,
              f"routes={len(host2.routes)} doc_paths={len(pre_doc['paths'])} "
              f"middleware_built={host2.middleware_stack is not None}")

        before_tbl = route_table(host2)
        attach_v2(host2)
        after_tbl = route_table(host2)
        C_STATE["before_tbl"] = before_tbl
        C_STATE["after_tbl"] = after_tbl
        C_STATE["route_count_post"] = len(host2.routes)
        check("C_route_table_prefix_kept",
              after_tbl[:len(before_tbl)] == before_tbl
              and len(after_tbl) == len(before_tbl) + 1,
              f"before={len(before_tbl)} after={len(after_tbl)}", polarity="positive")
        check("C_route_table_single_wrapper_appended",
              after_tbl[len(before_tbl):] == [[None, [], "_IncludedRouter"]],
              after_tbl[len(before_tbl):], polarity="positive")

        with TestClient(host2, raise_server_exceptions=False) as client:
            composed = full_probe_all(client)
            served = client.get("/openapi.json")
            sid = SYLLABUS_FIXTURES[0]["public_id"]
            r200 = client.get(f"/api/v2/syllabuses/{sid}/content")
            r206 = client.get(f"/api/v2/syllabuses/{sid}/content", headers={"Range": "bytes=0-9"})
            r304 = client.get(f"/api/v2/syllabuses/{sid}/content",
                              headers={"If-None-Match": r200.headers.get("etag")})
            rhead = client.head(f"/api/v2/syllabuses/{sid}/content")
        C_STATE["composed"] = composed
        C_STATE["served_status"] = served.status_code
        C_STATE["served_body"] = json_or_none(served)

        legacy_names = [name for name, _, _ in INVENTORY_PROBES] + [name for name, _, _, _ in EXTRA_PROBES]
        inventory_names = [name for name, _, _ in INVENTORY_PROBES]
        extra_names = [name for name, _, _, _ in EXTRA_PROBES]
        inventory_changed = [name for name in inventory_names if baseline[name] != composed[name]]
        extra_changed = [name for name in extra_names if baseline[name] != composed[name]]
        check("C_legacy_inventory_byte_identical", not inventory_changed,
              f"{len(inventory_names)} row probe(s); changed={inventory_changed[:5] or 'none'}",
              polarity="positive")
        check("C_legacy_extras_byte_identical", not extra_changed,
              f"{len(extra_names)} extra probe(s); changed={extra_changed[:5] or 'none'}",
              polarity="positive")
        check("C_legacy_boom_bytes_pinned",
              composed["extra:boom_500"] == [500, "text/plain; charset=utf-8", PLAIN_500_SHA],
              composed["extra:boom_500"], polarity="positive")

        fixture_ids = [row["public_id"] for row in SYLLABUS_FIXTURES]
        check("C_binary_fixture_ids_pinned",
              fixture_ids == ["syl_synthetic_cie_0580", "syl_synthetic_ielts_book"],
              fixture_ids, polarity="positive")
        check("C_binary_content_200",
              r200.status_code == 200 and r200.headers.get("content-type") == "application/pdf"
              and len(r200.content) == 667
              and r200.headers.get("etag")
              == '"8440c06c6815e3028af1332449598d241329e3305133f57019f290cf277dd9da"',
              [r200.status_code, r200.headers.get("content-type"), len(r200.content),
               r200.headers.get("etag")], polarity="positive")
        check("C_binary_range_206",
              r206.status_code == 206 and r206.headers.get("content-range") == "bytes 0-9/667"
              and len(r206.content) == 10,
              [r206.status_code, r206.headers.get("content-range"), len(r206.content)],
              polarity="positive")
        check("C_binary_conditional_304",
              r304.status_code == 304 and len(r304.content) == 0,
              [r304.status_code, len(r304.content)], polarity="positive")
        check("C_binary_head_200",
              rhead.status_code == 200 and rhead.headers.get("content-length") == "667",
              [rhead.status_code, rhead.headers.get("content-length")], polarity="positive")

        expected = {
            "ctl:typed_422": (400, "invalid_request"),
            "ctl:v2_boom": (500, "internal_error"),
            "ctl:jobs_404": (404, "not_found"),
            "ctl:unknown_404": (404, "route_not_found"),
            "ctl:post_info_405": (405, "method_not_allowed"),
            "ctl:info_200": (200, None),
        }
        parsed: dict[str, dict] = {}
        with TestClient(host2, raise_server_exceptions=False) as client:
            for name, method, url, params in CONTROL_REQUESTS:
                response = client.request(method, url, params=params)
                body = json_or_none(response)
                parsed[name] = {
                    "status": response.status_code,
                    "content_type": response.headers.get("content-type"),
                    "schema_version": (body or {}).get("schema_version") if isinstance(body, dict) else None,
                    "code": ((body or {}).get("error") or {}).get("code") if isinstance(body, dict) else None,
                    "validation": api_openapi.validate_response(body) if isinstance(body, dict) else ["not-json"],
                    "has_data": isinstance(body, dict) and "data" in body,
                }
        C_STATE["parsed"] = parsed

        envelope_ok = {name: (item["status"] == expected[name][0]
                              and item["content_type"] == "application/json"
                              and item["schema_version"] == V2_SCHEMA_VERSION
                              and item["code"] == expected[name][1]
                              and item["validation"] == []
                              and item["has_data"])
                       for name, item in parsed.items()}
        check("C_v2_typed_400_invalid_request", envelope_ok["ctl:typed_422"],
              parsed["ctl:typed_422"], polarity="positive")
        check("C_v2_stack_boom_500_internal_error", envelope_ok["ctl:v2_boom"],
              parsed["ctl:v2_boom"], polarity="positive")
        check("C_v2_jobs_404_not_found", envelope_ok["ctl:jobs_404"],
              parsed["ctl:jobs_404"], polarity="positive")
        check("C_v2_unknown_404_route_not_found", envelope_ok["ctl:unknown_404"],
              parsed["ctl:unknown_404"], polarity="positive")
        check("C_v2_post_info_405_method_not_allowed", envelope_ok["ctl:post_info_405"],
              parsed["ctl:post_info_405"], polarity="positive")
        check("C_v2_info_200_envelope", envelope_ok["ctl:info_200"],
              parsed["ctl:info_200"], polarity="positive")

        unchanged = [name for name, _, _, _ in CONTROL_REQUESTS if baseline[name] == composed[name]]
        check("C_v2_controls_differ_from_baseline", not unchanged,
              f"{len(CONTROL_REQUESTS)} control(s); identical={unchanged or 'none'}",
              polarity="positive")

    run_section("C", section_c)

    # ====================================================================== #
    # D: the composed document and route table (the acceptance evidence)
    # ====================================================================== #
    DOC: dict = {}
    STABILITY: dict = {}

    def section_d() -> None:
        host2 = C_STATE["host2"]
        pre_doc = C_STATE["pre_doc"]
        post_doc = host2.openapi()
        C_STATE["post_doc"] = post_doc
        spec_paths = {spec.full_path for spec in links.ROUTE_SPECS}
        pre_paths = set(pre_doc["paths"])
        post_paths = set(post_doc["paths"])

        added = post_paths - pre_paths
        removed = pre_paths - post_paths
        check("D_path_delta_is_exactly_registry", added == spec_paths and not removed,
              f"added={len(added)} removed={len(removed)} "
              f"unexpected_added={sorted(added - spec_paths)[:3] or 'none'}",
              polarity="positive")

        changed_ops = [path for path in sorted(pre_paths)
                       if pre_doc["paths"][path] != post_doc["paths"][path]]
        check("D_pre_paths_operations_unchanged", not changed_ops,
              f"{len(pre_paths)} pre-attach path(s); changed={changed_ops[:5] or 'none'}",
              polarity="positive")

        all_ids = [op.get("operationId")
                   for operations in post_doc["paths"].values()
                   for op in operations.values()]
        dupes = sorted(name for name, count in Counter(all_ids).items() if count > 1)
        check("D_operation_ids_unique", not dupes,
              f"{len(all_ids)} operation(s); duplicates={dupes[:5] or 'none'}", polarity="positive")

        ids_standalone = _ids_for(C_STATE["standalone_pre"] if "standalone_pre" in C_STATE
                                  else B_STATE["standalone_doc"], spec_paths)
        ids_composed = _ids_for(post_doc, spec_paths)
        check("D_v2_operation_ids_match_standalone",
              ids_standalone == ids_composed and len(ids_composed) == 39,
              f"standalone={len(ids_standalone)} composed={len(ids_composed)} "
              f"mismatch={sorted(set(ids_standalone.items()) ^ set(ids_composed.items()))[:3] or 'none'}",
              polarity="positive")

        binary_problems: list[str] = []
        required_codes = {"200", "206", "304", "413", "416"}
        for spec in links.ROUTE_SPECS:
            if not spec.binary:
                continue
            operations = post_doc["paths"].get(spec.full_path) or {}
            for method in ("get", "head"):
                op = operations.get(method)
                if not op:
                    binary_problems.append(f"{spec.capability}: missing {method}")
                    continue
                for code in ("200", "206"):
                    content = sorted(op.get("responses", {}).get(code, {}).get("content", {}))
                    if set(content) != set(spec.media_types) or "application/json" in content:
                        binary_problems.append(f"{spec.capability} {method} {code}: {content}")
            documented = {str(code) for code in (operations.get("get", {}).get("responses") or {})}
            if not required_codes <= documented:
                binary_problems.append(f"{spec.capability}: missing {sorted(required_codes - documented)}")
        check("D_binary_rows_documented", not binary_problems,
              binary_problems[:4] or "5 binary row(s) documented with their media types",
              polarity="positive")

        schema_problems: list[str] = []
        non_binary = 0
        for spec in links.ROUTE_SPECS:
            if spec.binary:
                continue
            non_binary += 1
            operation = post_doc["paths"].get(spec.full_path, {}).get("get", {})
            schema = (operation.get("responses", {}).get("200", {}).get("content", {})
                      .get("application/json", {}).get("schema"))
            if schema != api_openapi.ENVELOPE_SCHEMA:
                schema_problems.append(spec.capability)
        check("D_nonbinary_200_schema_is_envelope", not schema_problems,
              f"{non_binary} non-binary route(s); mismatches={schema_problems[:5] or 'none'}",
              polarity="positive")

        check("D_openapi_route_serves_same_document",
              C_STATE["served_status"] == 200 and C_STATE["served_body"] == post_doc,
              f"status={C_STATE['served_status']} equal={C_STATE['served_body'] == post_doc}",
              polarity="positive")

        host3 = make_host()
        attach_v2(host3)
        digest_second = canonical_digest(host3.openapi())
        digest_first = canonical_digest(post_doc)
        check("D_second_instance_document_digest_equal", digest_second == digest_first,
              f"{digest_first[:16]} vs {digest_second[:16]}", polarity="positive")

        legacy_names = [name for name, _, _ in INVENTORY_PROBES] + [name for name, _, _, _ in EXTRA_PROBES]
        DOC.update({
            "pre_paths": len(pre_paths),
            "post_paths": len(post_paths),
            "path_delta": len(added),
            "pre_paths_operations_changed": changed_ops,
            "operation_count": len(all_ids),
            "v2_operation_id_count": len(ids_composed),
            "served_equals_direct": C_STATE["served_body"] == post_doc,
            "second_instance_digest_equal": digest_second == digest_first,
            "combined_openapi_digest": digest_first,
        })
        STABILITY.update({
            "combined_openapi_digest": digest_first,
            "v2_standalone_digest": canonical_digest(B_STATE["standalone_doc"]),
            "legacy_ops_digest": canonical_digest({name: C_STATE["composed"][name]
                                                   for name in legacy_names}),
            "composed_route_table_digest": canonical_digest(C_STATE["after_tbl"]),
            "v2_operation_ids": ids_composed,
            "path_delta": DOC["path_delta"],
        })

    run_section("D", section_d)

    # ====================================================================== #
    # E: candidate immutability, manifest, compose pin, scratch
    # ====================================================================== #
    def section_e() -> None:
        after_snapshot = tree_snapshot(candidate)
        changed = [rel for rel in set(before_snapshot) | set(after_snapshot)
                   if before_snapshot.get(rel) != after_snapshot.get(rel)]
        check("E_candidate_bytes_unchanged", not changed, changed[:8] or "identical")

        fixtures_digest_after = tree_digest(candidate / "fixtures" / "synthetic")
        contracts_digest_after = tree_digest(candidate / "contracts")
        check("E_fixture_and_contract_digests_unchanged",
              fixtures_digest_after == fixtures_digest_before
              and contracts_digest_after == contracts_digest_before,
              f"fixtures={fixtures_digest_after['sha256'][:12]} "
              f"contracts={contracts_digest_after['sha256'][:12]}")

        manifest_path = candidate / "B04_CANDIDATE_MANIFEST.json"
        manifest_doc = load_json(manifest_path)
        recorded = manifest_doc.get("candidate_tree", {})
        recomputed = tree_digest(candidate, tuple(recorded.get("excludes", [])))
        check("E_manifest_recompute_matches_recorded", recomputed == recorded,
              f"files={recomputed.get('files')} sha={str(recomputed.get('sha256'))[:16]}")
        on_disk = recomputed.get("files", 0) + 1
        check("E_manifest_counts_disclosed",
              recomputed.get("files") == 188 and on_disk == 189,
              f"digest_files={recomputed.get('files')} on_disk_non_cache={on_disk}")

        candidate_compose = sha256(candidate / "src" / "examdata" / "integration" / "api" / "compose.py")
        tools_compose = sha256(RUN_DIR / "tools" / "compose.py")
        check("E_compose_hook_frozen",
              candidate_compose == tools_compose == EXPECTED_COMPOSE_SHA,
              f"candidate={candidate_compose[:16]} tools={tools_compose[:16]} "
              f"expected={EXPECTED_COMPOSE_SHA[:16]}")

        payload_pattern = re.compile(rb"data:[a-zA-Z]+/")
        hits: list[str] = []
        for path in sorted((candidate / "fixtures").rglob("*.json")):
            if payload_pattern.search(path.read_bytes()):
                hits.append(path.relative_to(candidate).as_posix())
        check("E_no_embedded_data_payloads", not hits, hits[:5] or "no data: URIs in fixtures")

        marker = scratch / "probe_scratch.json"
        marker.write_text(json.dumps({"run_id": RUN_ID, "cwd": str(Path.cwd()),
                                      "purpose": "routing scratch (the probe's only write)"},
                                     ensure_ascii=True, indent=1), encoding="utf-8")
        check("E_scratch_marker_written",
              marker.is_file() and load_json(marker)["run_id"] == RUN_ID, str(marker))

    run_section("E", section_e)

    # ====================================================================== #
    # N1: a raw include_router serves v2 but keeps every legacy error shape
    # ====================================================================== #
    NEG: dict = {}

    def section_n1() -> None:
        with TestClient(make_min_host(), raise_server_exceptions=False) as client:
            base = min_probe_all(client)
        host = make_min_host()
        host.include_router(create_app().router)
        with TestClient(host, raise_server_exceptions=False) as client:
            after = min_probe_all(client)
            info = client.get("/api/v2/info")
            unknown = client.get("/api/v2/__nope")
            apierr = client.get("/api/v2/jobs/no-such-job")
        doc = host.openapi()
        binary_content = sorted((doc["paths"].get("/api/v2/syllabuses/{id}/content", {})
                                 .get("get", {}).get("responses", {}).get("200", {})
                                 .get("content", {})).keys())
        NEG["n1"] = {
            "info": [info.status_code, info.headers.get("content-type")],
            "unknown": [unknown.status_code, unknown.headers.get("content-type"),
                        json_or_none(unknown)],
            "apierror": [apierr.status_code, apierr.headers.get("content-type"),
                         apierr.content.decode("ascii", "replace")[:60]],
            "binary_200_content": binary_content,
            "legacy_changed": sorted(name for name in base if base[name] != after[name]),
        }
        unknown_body = json_or_none(unknown)
        check("N1_raw_include_serves_v2_unshaped_errors",
              info.status_code == 200
              and unknown.status_code == 404 and unknown_body == {"detail": "Not Found"}
              and apierr.status_code == 500
              and (apierr.headers.get("content-type") or "").startswith("text/plain")
              and apierr.content == b"Internal Server Error",
              NEG["n1"], polarity="negative")
        check("N1_raw_include_binary_row_keeps_application_json",
              "application/json" in binary_content
              and {"application/pdf", "image/png"} <= set(binary_content),
              binary_content, polarity="negative")
        check("N1_legacy_probes_unchanged", base == after,
              NEG["n1"]["legacy_changed"] or "5 probe(s) identical", polarity="positive")

    run_section("N1", section_n1)

    # ====================================================================== #
    # N2: an unscoped handler install rewrites legacy 404/422/500 bytes
    # ====================================================================== #
    def section_n2() -> None:
        with TestClient(make_min_host(), raise_server_exceptions=False) as client:
            base = min_probe_all(client)
        v2_app = create_app()
        host = make_min_host()
        for exc_class, handler in v2_app.exception_handlers.items():
            host.add_exception_handler(exc_class, handler)
        with TestClient(host, raise_server_exceptions=False) as client:
            after = min_probe_all(client)
            shapes: dict[str, dict] = {}
            for key, url, params in (("boom_500", "/synthetic-legacy/boom", None),
                                     ("numbers_422", "/synthetic-legacy/numbers", {"limit": "abc"}),
                                     ("absent_404", "/api/legacy/absent", None)):
                body = json_or_none(client.get(url, params=params))
                shapes[key] = {
                    "schema_version": (body or {}).get("schema_version") if isinstance(body, dict) else None,
                    "code": ((body or {}).get("error") or {}).get("code") if isinstance(body, dict) else None,
                    "detail": (body or {}).get("detail") if isinstance(body, dict) else None,
                }
        changed = sorted(name for name in base if base[name] != after[name])
        NEG["n2"] = {"changed": changed, "after": after, "shapes": shapes}
        check("N2_unscoped_install_changes_exactly_three_probes",
              changed == ["absent_404", "boom_500", "numbers_422"], changed, polarity="negative")
        check("N2_unscoped_legacy_500_becomes_json_envelope",
              after["boom_500"][0] == 500 and after["boom_500"][1] == "application/json"
              and shapes["boom_500"]["code"] == "internal_error",
              {"after": after["boom_500"], "shape": shapes["boom_500"]}, polarity="negative")
        check("N2_unscoped_legacy_422_becomes_400_envelope",
              after["numbers_422"][0] == 400 and shapes["numbers_422"]["code"] == "invalid_request",
              {"after": after["numbers_422"], "shape": shapes["numbers_422"]}, polarity="negative")
        check("N2_unscoped_legacy_404_becomes_envelope",
              after["absent_404"][0] == 404 and shapes["absent_404"]["code"] == "route_not_found",
              {"after": after["absent_404"], "shape": shapes["absent_404"]}, polarity="negative")

        built_host = make_min_host()
        with TestClient(built_host, raise_server_exceptions=False) as client:
            client.get("/api/legacy/papers")
        built = built_host.middleware_stack is not None
        for exc_class, handler in v2_app.exception_handlers.items():
            built_host.add_exception_handler(exc_class, handler)
        with TestClient(built_host, raise_server_exceptions=False) as client:
            after_built = min_probe_all(client)
        check("N2_post_build_handler_install_is_invisible",
              built and after_built == base,
              f"middleware_built={built} changed="
              f"{sorted(name for name in base if base[name] != after_built[name]) or 'none'}",
              polarity="negative")

    run_section("N2", section_n2)

    # ====================================================================== #
    # N3: a mount answers under the wrong route and documents nothing
    # ====================================================================== #
    def section_n3() -> None:
        host = make_min_host()
        host.mount("/api/v2", create_app())
        with TestClient(host, raise_server_exceptions=False) as client:
            direct = client.get("/api/v2/info")
            doubled = client.get("/api/v2/api/v2/info")
        direct_body = json_or_none(direct)
        doc_paths = sorted(path for path in host.openapi()["paths"]
                           if path.startswith("/api/v2"))
        NEG["n3"] = {
            "direct": [direct.status_code, direct.headers.get("content-type")],
            "direct_code": (direct_body or {}).get("error", {}).get("code") if isinstance(direct_body, dict) else None,
            "doubled_status": doubled.status_code,
            "doc_v2_paths": doc_paths,
        }
        check("N3_mount_documents_no_v2_paths", doc_paths == [], doc_paths or "no /api/v2 paths",
              polarity="negative")
        check("N3_mount_direct_info_is_wrong_route_envelope",
              direct.status_code == 404 and (direct_body or {}).get("error", {}).get("code")
              == "route_not_found",
              NEG["n3"], polarity="negative")
        check("N3_mount_requires_doubled_prefix", doubled.status_code == 200,
              f"GET /api/v2/api/v2/info -> {doubled.status_code}", polarity="negative")

    run_section("N3", section_n3)

    # ====================================================================== #
    # N4: double attach refused without mutation
    # ====================================================================== #
    def section_n4() -> None:
        host = make_host()
        attach_v2(host)
        routes_before = route_table(host)
        doc_before = canonical_digest(host.openapi())
        try:
            attach_v2(host)
            refused, message = False, "NOT REFUSED"
        except RuntimeError as exc:
            refused, message = True, str(exc)
        routes_after = route_table(host)
        doc_after = canonical_digest(host.openapi())
        NEG["n4"] = {"refused": refused, "message": message,
                     "routes_unchanged": routes_before == routes_after,
                     "doc_unchanged": doc_before == doc_after}
        check("N4_double_attach_refused",
              refused and message == "the staged v2 app is already attached to this host",
              NEG["n4"], polarity="negative")
        check("N4_double_attach_leaves_host_unchanged",
              routes_before == routes_after and doc_before == doc_after,
              {"routes": routes_before == routes_after, "doc": doc_before == doc_after},
              polarity="negative")

    run_section("N4", section_n4)

    # ====================================================================== #
    # N5: late attach refused after the host served its first request
    # ====================================================================== #
    def section_n5() -> None:
        host = make_min_host()
        with TestClient(host, raise_server_exceptions=False) as client:
            client.get("/api/legacy/papers")
        built = host.middleware_stack is not None
        try:
            attach_v2(host)
            refused, message = False, "NOT REFUSED"
        except RuntimeError as exc:
            refused, message = True, str(exc)
        v2_paths = sorted(path for path in host.openapi()["paths"]
                          if path.startswith("/api/v2"))
        NEG["n5"] = {"middleware_built": built, "refused": refused, "message": message,
                     "v2_paths_after": v2_paths}
        check("N5_late_attach_refused",
              built and refused and message == (
                  "attach_v2 must be called before the host serves its first request: the "
                  "middleware stack snapshots the exception handlers when it is built"),
              NEG["n5"], polarity="negative")
        check("N5_late_attach_no_v2_paths", v2_paths == [],
              v2_paths or "no /api/v2 paths after the refused attach", polarity="negative")

    run_section("N5", section_n5)

    # ====================================================================== #
    # N6: non-FastAPI hosts refused with the exact error
    # ====================================================================== #
    def section_n6() -> None:
        results: dict[str, str] = {}
        for value in (None, "x"):
            try:
                attach_v2(value)
                results[repr(value)] = "NOT REFUSED"
            except TypeError as exc:
                results[repr(value)] = str(exc)
        NEG["n6"] = results
        check("N6_non_fastapi_host_refused",
              all(message == "attach_v2 expects a FastAPI application"
                  for message in results.values()),
              results, polarity="negative")

    run_section("N6", section_n6)

    # ====================================================================== #
    # Report
    # ====================================================================== #
    NOT_RUN.extend([
        {"check": "real merge into examdata/src/examdata/api/app.py",
         "reason": "gate original_paths_released is closed; the plan entry remains a proposal "
                   "(deferred_pending_release) and the original tree was never read or written"},
        {"check": "real baseline verification against the actual legacy application",
         "reason": "gate original_paths_released is closed; the legacy side was simulated from "
                   "the frozen A12 route-compatibility worksheet, not from the original app"},
        {"check": "real Node component execution (fake-cli.mjs run via the Node runtime)",
         "reason": "gate original_paths_released is closed; only synthetic discovery and "
                   "importability of the component are rehearsed"},
        {"check": "real Node/source validation against the original project",
         "reason": "gate original_paths_released is closed; the original tree was never read"},
        {"check": "real database schema / data migration",
         "reason": "gate real_data_write_authorized is closed; no database is staged or touched"},
        {"check": "live service / upstream provider calls",
         "reason": "gate upstream_requests_authorized is closed; only synthetic fixture "
                   "providers ran"},
        {"check": "cutover of the existing service",
         "reason": "gate existing_service_cutover_authorized is closed"},
        {"check": "deployment to any target",
         "reason": "gate remote_deployment_authorized is closed; this candidate is private-only"},
        {"check": "cleanup of the original project",
         "reason": "gate original_cleanup_authorized is closed"},
        {"check": "credential usage of any kind",
         "reason": "no credential gate exists in the seven-gate model and none is needed: no "
                   "credential is used, read, fabricated or staged; the routing controls are "
                   "synthetic request parameters with no secret values"},
    ])

    failed = [record["name"] for record in CHECKS if not record["ok"]]
    ok = not failed
    candidate_manifest_path = candidate / "B04_CANDIDATE_MANIFEST.json"
    manifest_doc = load_json(candidate_manifest_path) if candidate_manifest_path.is_file() else {}
    recorded = manifest_doc.get("candidate_tree", {})
    recomputed = tree_digest(candidate, tuple(recorded.get("excludes", []))) if recorded else {}

    report = {
        "schema": "examdata.integration.b04_route_probe/1",
        "run_id": RUN_ID,
        "packet": "B04",
        "candidate_root": str(candidate),
        "environment": {
            "cwd": str(Path.cwd()),
            "python": sys.version.split()[0],
            "executable": sys.executable,
            "pythonpath": os.environ.get("PYTHONPATH"),
            "staging_override": os.environ.get("EXAMDATA_INTEGRATION_STAGING_ROOT"),
            "root_env": os.environ.get("EXAMDATA_INTEGRATION_ROOT"),
            "dont_write_bytecode": sys.dont_write_bytecode,
        },
        "candidate_manifest": {
            "path": str(candidate_manifest_path),
            "sha256": sha256(candidate_manifest_path) if candidate_manifest_path.is_file() else None,
            "recorded_tree": recorded,
            "recomputed_tree": recomputed,
            "digest_matches": bool(recorded) and recomputed == recorded,
            "counts": manifest_doc.get("counts"),
        },
        "module_origins": MODULE_ORIGINS,
        "discovery": {"from_candidate_cwd": A_DISCOVERY},
        "worksheet": WORKSHEET,
        "v2_specs": {
            "specs": len(links.ROUTE_SPECS),
            "implemented": len(links.IMPLEMENTED_SPECS),
            "deferred": len(links.DEFERRED_SPECS),
            "binary": len([s for s in links.ROUTE_SPECS if s.binary]),
            "unique_paths": len({s.full_path for s in links.ROUTE_SPECS}),
            "advertised_pairs": len(links.advertised_pairs()),
            "agreement_problems": (api_openapi.agreement_problems(create_app())
                                   if "B_v2_agreement_problems_empty" in POSITIVE_CHECKS else None),
        },
        "ordering": B_STATE.get("ordering"),
        "mechanics": {
            "route_count_pre": C_STATE.get("route_count_pre"),
            "route_count_post": C_STATE.get("route_count_post"),
            "pre_doc_paths": C_STATE.get("pre_doc_paths"),
            "post_doc_paths": DOC.get("post_paths"),
            "route_table_delta": (C_STATE.get("route_count_post") - C_STATE.get("route_count_pre"))
            if C_STATE.get("route_count_pre") is not None else None,
            "wrapper_entry": (C_STATE.get("after_tbl") or [None])[len(C_STATE.get("before_tbl") or [])]
            if C_STATE.get("after_tbl") else None,
        },
        "combined_doc": DOC,
        "negatives": NEG,
        "stability": STABILITY,
        "checks": CHECKS,
        "counts": {
            "checks": len(CHECKS),
            "checks_failed": len(failed),
            "negative_checks": len(NEGATIVE_CHECKS),
            "positive_checks": len(POSITIVE_CHECKS),
        },
        "negative_checks": NEGATIVE_CHECKS,
        "positive_checks": POSITIVE_CHECKS,
        "failed": failed,
        "ok": ok,
        "not_run": NOT_RUN,
        "note": ("private rehearsal only; not merged, not deployed; the original tree was never "
                 "read, imported or written; frozen evidence was not touched; scratch space was "
                 "confined to the run directory's evidence/tmp; no credential was used, read or "
                 "fabricated"),
    }
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return 0 if ok else 1


def _first_match(routes, method: str, target: str):
    for route in routes:
        if method not in (getattr(route, "methods", None) or set()):
            continue
        regex = getattr(route, "path_regex", None)
        if regex is not None and regex.match(target):
            return route.path
    return None


def _unify(left: str, right: str):
    """A concrete path both route patterns match, or None if none can exist."""
    left_segments = left.split("/")
    right_segments = right.split("/")
    if len(left_segments) != len(right_segments):
        return None
    witness: list[str] = []
    for a, b in zip(left_segments, right_segments):
        a_param = a.startswith("{") and a.endswith("}")
        b_param = b.startswith("{") and b.endswith("}")
        if not a_param and not b_param:
            if a != b:
                return None
            witness.append(a)
        elif a_param and b_param:
            witness.append("synthetic-both")
        elif a_param:
            witness.append(b)
        else:
            witness.append(a)
    return "/".join(witness)


def _ids_for(document: dict, spec_paths: set[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for path, operations in document.get("paths", {}).items():
        if path not in spec_paths:
            continue
        for method, operation in operations.items():
            out[f"{method.upper()} {path}"] = operation.get("operationId")
    return out


def _coerce_ok(enum_cls, name: str) -> bool:
    try:
        enum_cls.coerce(name)
        return True
    except ValueError:
        return False


if __name__ == "__main__":
    raise SystemExit(main())
