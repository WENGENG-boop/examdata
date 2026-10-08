"""B07 route probe: integrating jobs, coverage, and diagnostics onto the
served API.

Runs entirely inside the private target-layout candidate and the two Phase A
write roots. It re-runs the B06 acceptance surface and adds, for packet B07
("Integrate jobs, coverage, and diagnostics", MASTER_EXECUTION_PLAN_EN.md 915-919):

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
  hosts are refused;
* the five feature families are supplied through ``Dataset.features``: the
  private fixture source passes the seam validators row by row, the routes
  serve its rows with both synthetic markers attached, returned rows are
  isolated copies, and a private source injected through ``create_app``
  changes what the routes serve without touching the frozen fixture path;
* the staged frontend tree is the candidate's whole "frontend" (17 files): the
  15 staged files are byte-equal to ``integration-staging/frontend`` and all
  13 provenance records (10 root + 3 fixture) match both the candidate bytes
  and the source bytes; the 2 new run files (``server.mjs`` and its test) are
  byte-equal to the frozen B06 run sources; ``node --check`` parses both new
  modules and ``node --test`` reports 41 tests / 41 pass / 0 fail;
* the discovery projection is pinned on the served resources route: six
  synthetic rows in sorted order with the ``discovery`` key always present
  (the four CIE/edexcel rows carry their exact discovery blocks; the IELTS and
  CIE graph rows carry ``null``), the three system filters, a 422
  ``unsupported_filter`` for unknown filters, and a 21-case query matrix
  covering season synonyms, token boundaries (``mar`` never reaches
  ``mark_scheme``; ``202`` is not ``2024``) and paper-suffix matching;
* the staged frontend server binds an ephemeral 127.0.0.1 port against the
  private read API and serves the staged page; the 18-check cross-stack probe
  passes and proxy content equals direct upstream equals the on-disk fixture
  bytes (same sha, 817 bytes);
* the six B06 stability values (combined / v2 standalone / legacy-ops digests,
  composed route-table digest, path delta 34 and the 39 v2 operation IDs) are
  compared value by value against ``B06_PROGRESS_LEDGER.json``;
* the seam's refusal semantics are pinned: unsupported status markers, missing
  evidence, non-fixture access modes, unavailable seasons without a reason,
  events with a date but no raw text, and windows whose parsed values do not
  match their declared boundaries are all refused before a route can serve
  them;
* the operations view is opt-in through ``EXAMDATA_OPERATIONS_ROOT`` pointed at
  the candidate's own synthetic fixture: 7 checkpoints (5 current, 2
  superseded) and 7 jobs read back read-only, the 9191 job staying
  ``stopped_requires_resume`` with its resume flag set and its error redacted
  (nothing resumes it), the 8888 route serving the current ``running``
  checkpoint and the older ``stopped`` one only as superseded, an unsupported
  checkpoint recorded as ``unknown`` with an ``unrecognised_checkpoint_format``
  problem, published coverage at 71.43 / 100.0 / 50.0 (partial / complete /
  partial) with an ``unknown`` row kept at a null percentage rather than a
  guess when no denominator is declared, the warning appended once on both
  routes, the configured root disclosed (scanned once: nothing skipped or
  truncated), coverage items/gaps identical with and without the view, and
  every served leaf sanitized (``<path>`` / ``<secret>`` placeholders; no raw
  fixture byte in the response).

Nothing here writes to the candidate, the original tree, a database, a
service, an operations root or frozen evidence. The only credential-shaped
value anywhere is the fixture-labelled synthetic control string. Scratch
space is confined to the run directory's ``evidence/tmp``. The real merge
into the original project, real Node/source validation, real source-provider
fetching from the frontend process, real job-service interaction, the real
frontend cutover and the real active-owner integration stay ``not_run``
because their gates are closed.

Exit code 0 = every check passed; 1 = at least one check failed; 2 = the probe
refused to run (missing explicit configuration).
"""
# Adapted copy of the frozen B07 probe (b07-rehearsal-2026-10-07/b07_route_probe.py)
# for the private review-fix rehearsal: RUN_ID, the candidate manifest name and
# the manifest count-disclosure check track B07R_CANDIDATE_MANIFEST.json; every
# other assertion is carried unchanged.
from __future__ import annotations

import hashlib
import importlib
import json
import os
import re
import shutil
import subprocess
import sys
import traceback
from collections import Counter
from pathlib import Path

RUN_DIR = Path(__file__).resolve().parent
RUN_ID = "b07-reviewfix-20261007-fzgu78c6"

#: Environment this probe refuses to run against by accident.
_REQUIRED_ENV = ("B07_CANDIDATE_ROOT", "B07_WORKSPACE_ROOT", "B07_TMP_DIR",
                 "EXAMDATA_INTEGRATION_ROOT", "EXAMDATA_OPERATIONS_ROOT",
                 "EXAMDATA_API_KEY")

#: The B06 rehearsal tree is the frozen baseline this candidate descends from;
#: its candidate compose copy, frontend sources and progress ledger are read
#: (never written) for the comparisons below.
B06_RUN_DIR = RUN_DIR.parent / "b06-rehearsal-2026-10-07"
B06_CANDIDATE_COMPOSE = (B06_RUN_DIR / "candidates" / "b06-frontend-v1"
                         / "src" / "examdata"
                         / "integration" / "api" / "compose.py")
B06_LEDGER_REL = "docs/integration/execution/B06_PROGRESS_LEDGER.json"

#: The only credential-shaped value this rehearsal ever uses: a synthetic
#: control string that the fixture itself labels as fake (never a real secret).
SYNTHETIC_KEY_CONTROL = "REDACTED_LOCAL_CREDENTIAL"

SKIP_DIRS = {"__pycache__", ".pytest_cache"}

#: The compose hook is frozen since B04; any drift fails the probe. The B06
#: candidate copy and this candidate's copy are both checked against the pin.
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

    candidate = Path(os.environ["B07_CANDIDATE_ROOT"]).resolve()
    workspace = Path(os.environ["B07_WORKSPACE_ROOT"]).resolve()
    tmp_root = Path(os.environ["B07_TMP_DIR"]).resolve()
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
    from examdata.integration.adapters.active_owner import (  # noqa: E402
        DEFERRED_ACTIVE_OWNER, EVIDENCE_SYNTHETIC, FeatureRowError,
        FeatureSource, FixtureFeatureSource, validate_feature_source)
    from examdata.integration.api.dataset import (  # noqa: E402
        SYLLABUS_FIXTURES, default_dataset, deferred_fixtures,
        fixture_feature_source, operations_view)
    from examdata.integration.api import dataset as dataset_module  # noqa: E402
    from examdata.integration.api.envelope import SCHEMA_VERSION as V2_SCHEMA_VERSION  # noqa: E402
    from examdata.integration.contracts import quality as quality_module  # noqa: E402
    from examdata.integration.contracts.enums import EntityKind  # noqa: E402
    from examdata.integration.contracts.models import Coverage  # noqa: E402
    from examdata.integration.operations import jobs as ops_jobs  # noqa: E402
    from examdata.integration.operations import published as ops_published  # noqa: E402
    from examdata.integration.runtime.manifest import load_manifest_set  # noqa: E402
    from examdata.integration.runtime.redact import contains_path  # noqa: E402

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
            "examdata.integration.adapters.active_owner",
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
            "examdata.integration.operations.jobs",
            "examdata.integration.operations.published",
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

        # -- the operations root and credential-shaped value must be the ---- #
        # -- private fixture ones, never anything from the original tree. --- #
        operations_root_env = Path(os.environ["EXAMDATA_OPERATIONS_ROOT"]).resolve()
        expected_operations_root = (candidate / "fixtures" / "synthetic"
                                    / "operations" / "operations-root").resolve()
        check("A_operations_root_is_candidate_fixture",
              operations_root_env == expected_operations_root,
              str(operations_root_env))

        check("A_api_key_is_labelled_synthetic_control",
              os.environ.get("EXAMDATA_API_KEY") == SYNTHETIC_KEY_CONTROL,
              "fixture-labelled synthetic control value")

        check("A_operations_root_env_name_pinned",
              dataset_module.OPERATIONS_ROOT_ENV == "EXAMDATA_OPERATIONS_ROOT",
              dataset_module.OPERATIONS_ROOT_ENV)

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

    # ====================================================================== #
    # S: the active-owner seam (private fixture source through Dataset.features)
    # ====================================================================== #
    S_STATE: dict = {}

    def section_s() -> None:
        fixture_source = fixture_feature_source()
        counts = validate_feature_source(fixture_source)
        S_STATE["fixture_counts"] = counts
        check("S_fixture_source_valid_counts",
              counts == {"syllabuses": 2, "materials": 2, "timetable_seasons": 2,
                         "timetable_events": 2, "timetable_windows": 2},
              counts, polarity="positive")

        default_ds = default_dataset()
        check("S_default_dataset_uses_fixture_source",
              isinstance(default_ds.features, FixtureFeatureSource),
              type(default_ds.features).__name__, polarity="positive")

        probe_rows = fixture_source.materials()
        probe_rows[0]["evidence"] = "tampered"
        probe_rows.append({"public_id": "mat_injected_probe"})
        after = fixture_source.materials()
        fresh_rows = fixture_feature_source().materials()
        check("S_rows_copy_isolated",
              after == fresh_rows and len(after) == 2,
              {"after_len": len(after), "fresh_len": len(fresh_rows),
               "first": {k: after[0].get(k)
                         for k in ("public_id", "evidence", "integration_status")}},
              polarity="positive")

        deferred = deferred_fixtures()
        families = ("syllabuses", "materials", "timetable_seasons",
                    "timetable_events", "timetable_windows")
        equal = all(deferred[name] == getattr(fixture_source, name)() for name in families)
        S_STATE["deferred"] = {"families_equal": equal, "tags": deferred["tags"],
                               "jobs": sorted(deferred["jobs"]),
                               "reason_len": len(deferred["reason"])}
        check("S_deferred_fixtures_through_seam",
              equal and deferred["tags"] == []
              and "job_synthetic_coverage" in deferred["jobs"]
              and bool(deferred["reason"]),
              S_STATE["deferred"], polarity="positive")

        with TestClient(create_app(), raise_server_exceptions=False) as client:
            resp = {
                "syllabuses": client.get("/api/v2/syllabuses"),
                "materials": client.get("/api/v2/materials"),
                "timetables": client.get("/api/v2/timetables"),
                "events": client.get("/api/v2/timetables/events"),
                "windows": client.get("/api/v2/timetables/windows"),
            }
        bodies = {name: json_or_none(view) for name, view in resp.items()}

        def items_of(body) -> list:
            return ((body or {}).get("data") or {}).get("items", [])

        def seasons_of(body) -> dict:
            return ((body or {}).get("data") or {})

        items = {name: items_of(bodies.get(name))
                 for name in ("syllabuses", "materials", "events", "windows")}
        seasons = seasons_of(bodies.get("timetables")).get("seasons", [])
        availability = seasons_of(bodies.get("timetables")).get("availability")
        marked = all(
            rows and all(row.get("evidence") == EVIDENCE_SYNTHETIC
                         and row.get("integration_status") == DEFERRED_ACTIVE_OWNER
                         for row in rows)
            for rows in (items["syllabuses"], items["materials"], items["events"],
                         items["windows"], seasons))
        S_STATE["route_statuses"] = {name: view.status_code for name, view in resp.items()}
        S_STATE["route_counts"] = {name: len(rows) for name, rows in items.items()}
        S_STATE["route_counts"]["seasons"] = len(seasons)
        check("S_route_rows_carry_markers",
              all(view.status_code == 200 for view in resp.values()) and marked,
              {"statuses": S_STATE["route_statuses"], "counts": S_STATE["route_counts"]},
              polarity="positive")

        cie_events = [row for row in items["events"] if row.get("system") == "cie"]
        check("S_cie_event_null_fields_preserved",
              len(cie_events) == 1 and all(
                  cie_events[0].get(k) is None for k in ("date", "session", "raw_text")),
              {k: cie_events[0].get(k) for k in ("date", "session", "raw_text")}
              if cie_events else "no cie event row",
              polarity="positive")

        check("S_seasons_unavailable_with_reason",
              availability == "unavailable" and len(seasons) == 2
              and all(row.get("availability") == "unavailable" and row.get("reason")
                      for row in seasons),
              {"availability": availability,
               "rows": [(row.get("system"), row.get("availability"), bool(row.get("reason")))
                        for row in seasons]},
              polarity="positive")

        cie_windows = [row for row in items["windows"] if row.get("system") == "cie"]
        edexcel_windows = [row for row in items["windows"] if row.get("system") == "edexcel"]
        cie_parsed = (cie_windows[0].get("parsed") or {}) if cie_windows else {}
        edexcel_parsed = (edexcel_windows[0].get("parsed") or {}) if edexcel_windows else {}
        check("S_windows_unknown_boundaries_declared",
              len(cie_windows) == 1
              and cie_windows[0].get("unknown_boundaries") == ["start", "end"]
              and cie_parsed.get("start") is None and cie_parsed.get("end") is None
              and len(edexcel_windows) == 1
              and edexcel_windows[0].get("unknown_boundaries") == ["end"]
              and edexcel_parsed.get("start") == "2026-06-01",
              {"cie": {"unknown": cie_windows[0].get("unknown_boundaries") if cie_windows else None,
                       "parsed": cie_parsed},
               "edexcel": {"unknown": edexcel_windows[0].get("unknown_boundaries")
                           if edexcel_windows else None,
                           "parsed": edexcel_parsed}},
              polarity="positive")

        base = fixture_feature_source()
        private = FixtureFeatureSource(
            syllabuses=[dict(row, public_id="syl_probe_private")
                        for row in base.syllabuses()[:1]],
            materials=[dict(row, public_id="mat_probe_private")
                       for row in base.materials()[:1]],
            timetable_seasons=base.timetable_seasons(),
            timetable_events=base.timetable_events(),
            timetable_windows=base.timetable_windows(),
        )
        private_app = create_app(dataset=default_dataset(features=private))
        with TestClient(private_app, raise_server_exceptions=False) as client:
            private_syl = json_or_none(client.get("/api/v2/syllabuses"))
            private_mat = json_or_none(client.get("/api/v2/materials"))
            old_syl = client.get("/api/v2/syllabuses/syl_synthetic_cie_0580")
            new_syl = client.get("/api/v2/syllabuses/syl_probe_private")
            old_mat = client.get("/api/v2/materials/mat_synthetic_cie_ins")
            new_mat = client.get("/api/v2/materials/mat_probe_private")
        private_ids = [row["public_id"] for row in items_of(private_syl)]
        private_mat_ids = [row["public_id"] for row in items_of(private_mat)]
        S_STATE["private_injection"] = {
            "syllabus_ids": private_ids, "material_ids": private_mat_ids,
            "detail_statuses": [old_syl.status_code, new_syl.status_code,
                                old_mat.status_code, new_mat.status_code],
        }
        check("S_private_source_served_by_routes",
              private_ids == ["syl_probe_private"]
              and private_mat_ids == ["mat_probe_private"]
              and old_syl.status_code == 404 and new_syl.status_code == 200
              and old_mat.status_code == 404 and new_mat.status_code == 200,
              S_STATE["private_injection"], polarity="positive")

        with TestClient(create_app(), raise_server_exceptions=False) as client:
            fresh = json_or_none(client.get("/api/v2/syllabuses"))
        fresh_ids = [row["public_id"] for row in items_of(fresh)]
        S_STATE["default_syllabus_ids"] = fresh_ids
        check("S_fixture_path_still_serves_after_injection",
              fresh_ids == ["syl_synthetic_cie_0580", "syl_synthetic_ielts_book"],
              fresh_ids, polarity="positive")

    run_section("S", section_s)

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
            mate = client.get("/api/v2/materials/mat_synthetic_cie_ins/content")
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
        check("C_material_content_200_pinned",
              mate.status_code == 200 and mate.headers.get("content-type") == "application/pdf"
              and len(mate.content) == 655
              and mate.headers.get("etag")
              == '"f5980cef27dfdb25e35a194b748da3ae274622de6dea1c97e72c410545760fef"',
              [mate.status_code, mate.headers.get("content-type"), len(mate.content),
               mate.headers.get("etag")], polarity="positive")

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

        # -- B07: the six B06 stability values, compared against the B06 ledger -- #
        ledger_path = workspace / B06_LEDGER_REL
        ledger_doc = load_json(ledger_path)
        ledger_stability = ledger_doc.get("probe_stability") or {}
        digest_values = ("combined_openapi_digest", "v2_standalone_digest",
                         "legacy_ops_digest", "composed_route_table_digest")
        mismatched = {name: {"probe": STABILITY.get(name), "ledger": ledger_stability.get(name)}
                      for name in digest_values
                      if STABILITY.get(name) != ledger_stability.get(name)}
        b07_vs_b06 = {
            "ledger_path": str(ledger_path),
            "ledger_sha256": sha256(ledger_path),
            "digest_mismatches": mismatched,
            "ids_match": ledger_stability.get("v2_operation_ids") == STABILITY["v2_operation_ids"],
            "ledger_ids": len(ledger_stability.get("v2_operation_ids") or {}),
            "probe_ids": len(STABILITY["v2_operation_ids"]),
            "ledger_path_delta": ledger_stability.get("path_delta"),
            "probe_path_delta": STABILITY["path_delta"],
        }
        DOC["b07_vs_b06_stability"] = b07_vs_b06
        check("D_stability_digests_match_b06_ledger", not mismatched,
              mismatched or "four digests equal to the B06 ledger", polarity="positive")
        check("D_stability_ids_and_delta_match_b06_ledger",
              b07_vs_b06["ids_match"] and b07_vs_b06["ledger_path_delta"] == 34
              and b07_vs_b06["probe_path_delta"] == 34,
              {key: b07_vs_b06[key] for key in ("ledger_ids", "probe_ids",
                                                "ledger_path_delta", "probe_path_delta")},
              polarity="positive")

    run_section("D", section_d)

    # ====================================================================== #
    # F: the staged frontend tree (bytes, provenance, Node runtime)
    # ====================================================================== #
    STAGED_FRONTEND_SOURCE = workspace / "integration-staging" / "frontend"
    FRONTEND_STAGED = (
        "PROVENANCE.json",
        "README.md",
        "app.js",
        "client.mjs",
        "fixture-server.mjs",
        "fixtures/PROVENANCE.json",
        "fixtures/catalog.json",
        "fixtures/resources.json",
        "fixtures/syllabi.json",
        "index.html",
        "search.mjs",
        "styles.css",
        "tests/client.test.mjs",
        "tests/flow.test.mjs",
        "tests/search.test.mjs",
    )
    FRONTEND_NEW = (
        ("server.mjs", B06_RUN_DIR / "tools" / "server.mjs"),
        ("tests/server.test.mjs", B06_RUN_DIR / "tools" / "tests" / "server.test.mjs"),
    )
    CIE_MS = "asset_nz3uic3wquirttazjeo4fnsi3g7esn3k"
    CIE_QP = "asset_umsge7vuubq3ncsz3zfe7b3golwybrmn"
    EDX_MS = "asset_6xyrzhw4g5dy56xaxmhzk52da6zem5vu"
    EDX_QP = "asset_jkw4xdasfrjtknr6ewnvus2rflr2r56n"
    IELTS = "asset_bpdesyagunzooa3vdff53jvkk4pzilbt"
    CIE_GRAPH = "asset_4fgmj24f44aqv3dnnwfrae3g4s5nmfdb"
    EXPECTED_QP_SHA = "6596e686e26208b79bef32ecb04561d8813da7b15419ceeb32728dd0c0420790"
    EXPECTED_QP_BYTES = 817
    F_STATE: dict = {}
    G_STATE: dict = {}
    H_STATE: dict = {}

    def section_f() -> None:
        frontend = candidate / "frontend"
        found = sorted(path.relative_to(frontend).as_posix()
                       for path in frontend.rglob("*") if path.is_file())
        expected = sorted(set(FRONTEND_STAGED) | {rel for rel, _ in FRONTEND_NEW})
        F_STATE["files"] = {rel: sha256(frontend / rel) for rel in found}
        check("F_frontend_tree_is_seventeen_files", found == expected and len(found) == 17,
              {"count": len(found), "unexpected": sorted(set(found) - set(expected)),
               "missing": sorted(set(expected) - set(found))},
              polarity="positive")

        staged_mismatch = [rel for rel in FRONTEND_STAGED
                           if sha256(frontend / rel) != sha256(STAGED_FRONTEND_SOURCE / rel)]
        check("F_staged_frontend_bytes_match_workspace_source", not staged_mismatch,
              staged_mismatch[:6] or f"{len(FRONTEND_STAGED)} staged files byte-equal to "
              "integration-staging/frontend", polarity="positive")

        new_mismatch = [rel for rel, source in FRONTEND_NEW
                        if sha256(frontend / rel) != sha256(source)]
        check("F_new_frontend_files_match_run_sources", not new_mismatch,
              new_mismatch[:6] or f"{len(FRONTEND_NEW)} new files byte-equal to the frozen B06 run sources",
              polarity="positive")

        root_records = load_json(frontend / "PROVENANCE.json").get("files") or []
        fixture_records = load_json(frontend / "fixtures" / "PROVENANCE.json").get("files") or []
        prov_problems: list[str] = []
        for record in root_records:
            rel = str(record.get("path"))
            recorded = record.get("staged_sha256")
            if not (recorded and recorded == sha256(frontend / rel)
                    and recorded == sha256(STAGED_FRONTEND_SOURCE / rel)):
                prov_problems.append(f"root:{rel}")
        for record in fixture_records:
            rel = str(record.get("path"))
            target = frontend / "fixtures" / rel
            recorded = record.get("sha256")
            if not (recorded and recorded == sha256(target)
                    and len(target.read_bytes()) == record.get("size_bytes")
                    and recorded == sha256(STAGED_FRONTEND_SOURCE / "fixtures" / rel)):
                prov_problems.append(f"fixtures:{rel}")
        F_STATE["provenance"] = {"root_records": len(root_records),
                                 "fixture_records": len(fixture_records),
                                 "problems": prov_problems}
        check("F_provenance_records_match_candidate_and_source",
              not prov_problems and len(root_records) == 10 and len(fixture_records) == 3,
              F_STATE["provenance"], polarity="positive")

        node = shutil.which("node")
        node_version = ""
        if node:
            version_run = subprocess.run([node, "--version"], capture_output=True, text=True,
                                         encoding="utf-8", timeout=60)
            node_version = version_run.stdout.strip()
        F_STATE["node"] = {"path": node, "version": node_version}
        check("F_node_available", bool(node) and node_version.startswith("v"),
              F_STATE["node"], polarity="positive")
        if not node:
            check("F_node_check_parses_new_frontend_js", False, "node not found",
                  polarity="positive")
            check("F_node_test_suite_41_passed", False, "node not found", polarity="positive")
            return

        node_check: dict = {}
        for rel, _ in FRONTEND_NEW:
            run = subprocess.run([node, "--check", str(frontend / rel)], capture_output=True,
                                 text=True, encoding="utf-8", timeout=120)
            node_check[rel] = {"exit": run.returncode,
                               "stderr_tail": run.stderr.strip().splitlines()[-3:]}
        F_STATE["node_check"] = node_check
        check("F_node_check_parses_new_frontend_js",
              all(entry["exit"] == 0 for entry in node_check.values()),
              node_check, polarity="positive")

        node_test = subprocess.run(
            [node, "--test", "tests/client.test.mjs", "tests/flow.test.mjs",
             "tests/search.test.mjs", "tests/server.test.mjs"],
            cwd=str(frontend), capture_output=True, text=True, encoding="utf-8", timeout=600)
        counts: dict = {}
        for key in ("tests", "pass", "fail"):
            match = re.search(rf"[\u2139#] {key} (\d+)", node_test.stdout)
            counts[key] = int(match.group(1)) if match else None
        F_STATE["node_test"] = {"exit": node_test.returncode, "counts": counts,
                                "stdout_tail": node_test.stdout.strip().splitlines()[-9:],
                                "stderr_tail": node_test.stderr.strip().splitlines()[-4:]}
        check("F_node_test_suite_41_passed",
              node_test.returncode == 0 and counts == {"tests": 41, "pass": 41, "fail": 0},
              F_STATE["node_test"], polarity="positive")

    def section_g() -> None:
        cie_pair = sorted([CIE_MS, CIE_QP])
        edx_pair = sorted([EDX_MS, EDX_QP])
        year_all = sorted([EDX_MS, EDX_QP, CIE_MS, CIE_QP])
        cie_block = {"board": "cie", "subject": "9999", "subject_title": "synthetic-subject",
                     "year": 2024, "season": "Jun", "paper": "11",
                     "document_type": "question_paper"}
        cie_ms_block = dict(cie_block, document_type="mark_scheme")
        edx_base = {"board": "edexcel", "subject": "wma11", "subject_title": None,
                    "year": "2024", "season": None, "paper": "wma11-01"}
        edx_qp_block = dict(edx_base, document_type="question_paper")
        edx_ms_block = dict(edx_base, document_type="mark_scheme")
        expected_rows = [
            {"public_id": CIE_GRAPH, "system": "cie", "media_type": None, "byte_size": None,
             "content_available": True, "has_discovery_key": True, "discovery": None},
            {"public_id": EDX_MS, "system": "edexcel", "media_type": "application/pdf",
             "byte_size": None, "content_available": True, "has_discovery_key": True,
             "discovery": edx_ms_block},
            {"public_id": IELTS, "system": "ielts", "media_type": None, "byte_size": None,
             "content_available": True, "has_discovery_key": True, "discovery": None},
            {"public_id": EDX_QP, "system": "edexcel", "media_type": "application/pdf",
             "byte_size": None, "content_available": True, "has_discovery_key": True,
             "discovery": edx_qp_block},
            {"public_id": CIE_MS, "system": "cie", "media_type": "application/pdf",
             "byte_size": None, "content_available": True, "has_discovery_key": True,
             "discovery": cie_ms_block},
            {"public_id": CIE_QP, "system": "cie", "media_type": "application/pdf",
             "byte_size": None, "content_available": True, "has_discovery_key": True,
             "discovery": cie_block},
        ]
        queries = [
            ("9999 2024 Jun", None), ("9999 2024 June", None), ("9999 2024 Jun", "cie"),
            ("9999 2024 Nov", None), ("9999 2024 Mar", None), ("9999 2024 mar", None),
            ("9999 2024 March", None), ("wma11 2024 June", None),
            ("wma11 2024 October", None), ("wma11 2024 January", None),
            ("wma11 2024 November", None), ("wma11 2024", None), ("wma11 2024 01", None),
            ("2024", None), ("Jun", None), ("9999 2024 Jun", "edexcel"),
            ("9999 2024 01", None), ("9999 202", None), ("qp", None), ("ms", None),
            ("q", None),
        ]
        wanted_matrix = {
            "9999 2024 Jun|": cie_pair,
            "9999 2024 June|": cie_pair,
            "9999 2024 Jun|cie": cie_pair,
            "9999 2024 Nov|": [],
            "9999 2024 Mar|": [],
            "9999 2024 mar|": [],
            "9999 2024 March|": [],
            "wma11 2024 June|": edx_pair,
            "wma11 2024 October|": edx_pair,
            "wma11 2024 January|": [],
            "wma11 2024 November|": [],
            "wma11 2024|": edx_pair,
            "wma11 2024 01|": edx_pair,
            "2024|": year_all,
            "Jun|": cie_pair,
            "9999 2024 Jun|edexcel": [],
            "9999 2024 01|": [],
            "9999 202|": [],
            "qp|": [],
            "ms|": [],
            "q|": [],
        }

        with TestClient(create_app(), raise_server_exceptions=False) as client:
            rows_view = client.get("/api/v2/resources")
            rows_body = json_or_none(rows_view)
            items = ((rows_body or {}).get("data") or {}).get("items") or []
            G_STATE["empty_status"] = rows_view.status_code
            G_STATE["empty_ids"] = [item.get("public_id") for item in items]
            G_STATE["rows"] = [
                {"public_id": item.get("public_id"), "system": item.get("system"),
                 "media_type": item.get("media_type"), "byte_size": item.get("byte_size"),
                 "content_available": item.get("content_available"),
                 "has_discovery_key": "discovery" in item,
                 "discovery": item.get("discovery")}
                for item in items]
            row_problems = [f"row {index}: {got.get('public_id')} != {want['public_id']}"
                            for index, (got, want) in enumerate(zip(G_STATE["rows"],
                                                                    expected_rows))
                            if got != want]
            if len(G_STATE["rows"]) != len(expected_rows):
                row_problems.append(f"count {len(G_STATE['rows'])} != {len(expected_rows)}")
            check("G_rows_six_sorted_with_discovery_blocks",
                  G_STATE["empty_status"] == 200 and not row_problems,
                  {"status": G_STATE["empty_status"],
                   "problems": row_problems or "six rows exact"}, polarity="positive")

            check("G_empty_query_returns_all_six",
                  G_STATE["empty_ids"] == [row["public_id"] for row in expected_rows],
                  G_STATE["empty_ids"], polarity="positive")

            system_filters = {}
            for system in ("cie", "edexcel", "ielts"):
                body = json_or_none(client.get("/api/v2/resources", params={"system": system}))
                system_filters[system] = sorted(
                    item.get("public_id")
                    for item in ((body or {}).get("data") or {}).get("items") or [])
            G_STATE["system_filters"] = system_filters
            check("G_system_filter_rows",
                  system_filters == {"cie": sorted([CIE_GRAPH, CIE_MS, CIE_QP]),
                                     "edexcel": edx_pair, "ielts": [IELTS]},
                  system_filters, polarity="positive")

            bogus = client.get("/api/v2/resources", params={"bogus": "1"})
            bogus_body = json_or_none(bogus) or {}
            G_STATE["unknown_filter"] = {
                "status": bogus.status_code,
                "code": (bogus_body.get("error") or {}).get("code"),
                "schema_version": bogus_body.get("schema_version"),
                "allowed": ((bogus_body.get("error") or {}).get("details") or {}).get("allowed"),
            }
            check("G_unknown_filter_422_unsupported_filter",
                  G_STATE["unknown_filter"] == {"status": 422, "code": "unsupported_filter",
                                                "schema_version": "examdata.v2/1",
                                                "allowed": ["media_type", "query", "system"]},
                  G_STATE["unknown_filter"], polarity="positive")

            matrix: dict = {}
            for query, system in queries:
                params = {"query": query}
                if system is not None:
                    params["system"] = system
                body = json_or_none(client.get("/api/v2/resources", params=params))
                matrix[f"{query}|{system or ''}"] = sorted(
                    item.get("public_id")
                    for item in ((body or {}).get("data") or {}).get("items") or [])
            G_STATE["matrix"] = matrix
            matrix_mismatches = {
                key: {"got": matrix.get(key), "want": wanted}
                for key, wanted in wanted_matrix.items() if matrix.get(key) != wanted}
            if set(matrix) != set(wanted_matrix):
                matrix_mismatches[".keys"] = sorted(set(matrix) ^ set(wanted_matrix))
            G_STATE["matrix_mismatches"] = matrix_mismatches
            check("G_query_matrix_all_21_cases",
                  not matrix_mismatches and len(wanted_matrix) == 21,
                  matrix_mismatches or "21/21 query cases match", polarity="positive")

            mar_ids = matrix.get("9999 2024 mar|")
            mark_scheme_rows = [row["public_id"] for row in G_STATE["rows"]
                                if (row.get("discovery") or {}).get("document_type")
                                == "mark_scheme"]
            check("G_boundary_mar_leaves_mark_scheme_alone",
                  mar_ids == [] and sorted(mark_scheme_rows) == sorted([CIE_MS, EDX_MS]),
                  {"mar": mar_ids, "mark_scheme_rows": mark_scheme_rows}, polarity="positive")

            check("G_boundary_202_is_not_2024",
                  matrix.get("9999 202|") == [] and matrix.get("9999 2024 Jun|") == cie_pair,
                  {"202": matrix.get("9999 202|"),
                   "9999 2024 Jun": matrix.get("9999 2024 Jun|")}, polarity="positive")

            check("G_boundary_paper_suffix_01_matches",
                  matrix.get("wma11 2024 01|") == edx_pair,
                  matrix.get("wma11 2024 01|") or "empty", polarity="positive")

            detail_expectations = [
                ("umsge", CIE_QP, cie_block),
                ("ielts", IELTS, None),
                ("graph", CIE_GRAPH, None),
                ("edx_ms", EDX_MS, edx_ms_block),
                ("edx_qp", EDX_QP, edx_qp_block),
                ("cie_ms", CIE_MS, cie_ms_block),
            ]
            details = {}
            detail_problems = []
            for name, ident, want in detail_expectations:
                view = client.get(f"/api/v2/resources/{ident}")
                body = json_or_none(view)
                item = ((body or {}).get("data") or {}).get("item") if isinstance(body, dict) \
                    else None
                details[name] = {
                    "status": view.status_code,
                    "has_discovery_key": isinstance(item, dict) and "discovery" in item,
                    "discovery": item.get("discovery") if isinstance(item, dict) else None,
                }
                if details[name] != {"status": 200, "has_discovery_key": True,
                                     "discovery": want}:
                    detail_problems.append(name)
            G_STATE["details"] = details
            check("G_detail_routes_carry_discovery_key", not detail_problems,
                  {"problems": detail_problems or "six detail routes exact",
                   "umsge": details["umsge"], "ielts": details["ielts"],
                   "graph": details["graph"]}, polarity="positive")

    def section_h() -> None:
        import socket
        import threading
        import time
        import urllib.request

        import uvicorn

        cross_stack = RUN_DIR / "tools" / "b07_cross_stack.mjs"

        def free_port() -> int:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.bind(("127.0.0.1", 0))
                return sock.getsockname()[1]

        def wait_http(url: str, timeout: float) -> bool:
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                try:
                    with urllib.request.urlopen(url, timeout=2) as response:
                        if response.status == 200:
                            return True
                except Exception:  # noqa: BLE001 - the server may not be up yet
                    pass
                time.sleep(0.2)
            return False

        def fetch_sha(url: str) -> tuple[str, int]:
            with urllib.request.urlopen(url, timeout=10) as response:
                payload = response.read()
            return hashlib.sha256(payload).hexdigest(), len(payload)

        up_port = free_port()
        fe_port = free_port()
        while fe_port == up_port:
            fe_port = free_port()
        up_base = f"http://127.0.0.1:{up_port}"
        fe_base = f"http://127.0.0.1:{fe_port}"
        H_STATE["ports"] = {"upstream": up_port, "frontend": fe_port}

        server = uvicorn.Server(uvicorn.Config(create_app(), host="127.0.0.1", port=up_port,
                                               log_level="warning", loop="asyncio"))
        upstream_thread = threading.Thread(target=server.run, daemon=True)
        upstream_thread.start()
        deadline = time.monotonic() + 30
        while not server.started and time.monotonic() < deadline:
            time.sleep(0.1)
        check("H_upstream_uvicorn_started", bool(server.started),
              {"upstream": up_base, "started": bool(server.started)}, polarity="positive")
        if not server.started:
            server.should_exit = True
            upstream_thread.join(10)
            return

        proc: subprocess.Popen | None = None
        stdout_lines: list[str] = []
        stderr_lines: list[str] = []

        def pump(stream, sink: list) -> None:
            for line in stream:
                sink.append(line.rstrip("\n"))

        try:
            env = dict(os.environ)
            env["FRONTEND_PORT"] = str(fe_port)
            env["EXAMDATA_URL"] = up_base
            env.pop("EXAMDATA_API_KEY", None)
            proc = subprocess.Popen(["node", str(candidate / "frontend" / "server.mjs")],
                                    cwd=str(RUN_DIR), env=env, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, text=True, encoding="utf-8")
            for stream, sink in ((proc.stdout, stdout_lines), (proc.stderr, stderr_lines)):
                threading.Thread(target=pump, args=(stream, sink), daemon=True).start()

            banner_port = None
            banner_deadline = time.monotonic() + 20
            while time.monotonic() < banner_deadline and proc.poll() is None:
                match = re.search(r"frontend server: http://127\.0\.0\.1:(\d+)",
                                  "\n".join(stdout_lines))
                if match:
                    banner_port = int(match.group(1))
                    break
                time.sleep(0.2)
            H_STATE["banner"] = {"port": banner_port, "first_line": stdout_lines[:1]}
            check("H_frontend_server_ephemeral_banner",
                  banner_port == fe_port and proc.poll() is None,
                  {"banner_port": banner_port, "expected_port": fe_port,
                   "alive": proc.poll() is None}, polarity="positive")

            check("H_frontend_serves_index", wait_http(fe_base + "/", 15),
                  fe_base + "/", polarity="positive")

            cross = subprocess.run(["node", str(cross_stack), str(candidate / "frontend"),
                                    fe_base, up_base], cwd=str(RUN_DIR), capture_output=True,
                                   text=True, encoding="utf-8", timeout=300)
            try:
                cross_doc = json.loads(cross.stdout)
            except json.JSONDecodeError:
                cross_doc = {}
            cross_checks = cross_doc.get("checks") or []
            for record in cross_checks:
                name = record.get("name")
                check(f"H_node_{name}", bool(record.get("ok")), record.get("detail", ""),
                      polarity="positive")
            cross_counts = cross_doc.get("counts") or {}
            H_STATE["cross"] = {
                "exit": cross.returncode, "ok": cross_doc.get("ok"),
                "counts": cross_counts,
                "failed": [record.get("name") for record in cross_checks
                           if not record.get("ok")],
                "observations": cross_doc.get("observations"),
                "stderr_tail": cross.stderr.strip().splitlines()[-3:],
                "stdout_tail": cross.stdout.strip().splitlines()[-2:],
            }
            check("H_cross_stack_all_18_pass",
                  cross.returncode == 0 and cross_doc.get("ok") is True
                  and cross_counts == {"checks": 18, "failed": 0},
                  H_STATE["cross"], polarity="positive")

            proxy_sha, proxy_bytes = fetch_sha(f"{fe_base}/api/v2/assets/{CIE_QP}/content")
            direct_sha, direct_bytes = fetch_sha(f"{up_base}/api/v2/assets/{CIE_QP}/content")
            disk_sha = sha256(candidate / "fixtures" / "synthetic" / "binary" / "cie-qp.pdf")
            H_STATE["content_triple"] = {
                "proxy": {"sha256": proxy_sha[:16], "bytes": proxy_bytes},
                "direct": {"sha256": direct_sha[:16], "bytes": direct_bytes},
                "disk": {"sha256": disk_sha[:16]},
                "expected": {"sha256": EXPECTED_QP_SHA[:16], "bytes": EXPECTED_QP_BYTES},
            }
            check("H_content_triple_proxy_direct_disk",
                  proxy_sha == direct_sha == disk_sha == EXPECTED_QP_SHA
                  and proxy_bytes == direct_bytes == EXPECTED_QP_BYTES,
                  H_STATE["content_triple"], polarity="positive")
        finally:
            if proc is not None:
                if proc.poll() is None:
                    proc.terminate()
                    try:
                        proc.wait(10)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        proc.wait(10)
            server.should_exit = True
            upstream_thread.join(15)
            H_STATE["teardown"] = {
                "frontend_returncode": proc.returncode if proc is not None else None,
                "frontend_stderr_tail": stderr_lines[-4:],
                "upstream_stopped": not upstream_thread.is_alive(),
            }
            check("H_rehearsal_processes_stopped",
                  proc is not None and proc.returncode is not None
                  and not upstream_thread.is_alive(),
                  H_STATE["teardown"], polarity="positive")

    run_section("F", section_f)
    run_section("G", section_g)
    run_section("H", section_h)

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

        manifest_path = candidate / "B07R_CANDIDATE_MANIFEST.json"
        manifest_doc = load_json(manifest_path)
        recorded = manifest_doc.get("candidate_tree", {})
        recomputed = tree_digest(candidate, tuple(recorded.get("excludes", [])))
        check("E_manifest_recompute_matches_recorded", recomputed == recorded,
              f"files={recomputed.get('files')} sha={str(recomputed.get('sha256'))[:16]}")
        recounted = sum(1 for path in candidate.rglob("*")
                        if path.is_file()
                        and not any(part in SKIP_DIRS for part in path.parts))
        check("E_manifest_counts_disclosed",
              recomputed.get("files") == recorded.get("files")
              and recounted == recomputed.get("files") + 1,
              f"digest_files={recomputed.get('files')} "
              f"recorded_files={recorded.get('files')} on_disk_non_cache={recounted}")

        candidate_compose = sha256(candidate / "src" / "examdata" / "integration" / "api" / "compose.py")
        b06_compose = sha256(B06_CANDIDATE_COMPOSE)
        check("E_compose_hook_frozen",
              candidate_compose == b06_compose == EXPECTED_COMPOSE_SHA,
              f"candidate={candidate_compose[:16]} b06_candidate={b06_compose[:16]} "
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
    # N7: the active-owner seam refuses over-claiming sources before routes
    # ====================================================================== #
    def section_n7() -> None:
        base = fixture_feature_source()

        def refused(fn) -> tuple[bool, str]:
            try:
                fn()
                return False, "accepted (no refusal)"
            except FeatureRowError as exc:
                return True, str(exc)[:200]
            except Exception as exc:  # noqa: BLE001 - a wrong exception is not a refusal
                return False, f"{type(exc).__name__}: {exc}"[:200]

        def source_with(**overrides):
            kwargs = {
                "syllabuses": base.syllabuses(),
                "materials": base.materials(),
                "timetable_seasons": base.timetable_seasons(),
                "timetable_events": base.timetable_events(),
                "timetable_windows": base.timetable_windows(),
            }
            kwargs.update(overrides)
            return FixtureFeatureSource(**kwargs)

        syllabuses = base.syllabuses()
        bad = dict(syllabuses[0])
        bad.pop("evidence")
        NEG["n7a"] = refused(lambda: source_with(syllabuses=[bad]))
        check("N7_refuses_missing_evidence_marker", NEG["n7a"][0], NEG["n7a"][1],
              polarity="negative")

        bad = dict(syllabuses[0])
        bad.pop("integration_status")
        NEG["n7b"] = refused(lambda: source_with(syllabuses=[bad]))
        check("N7_refuses_missing_status_marker", NEG["n7b"][0], NEG["n7b"][1],
              polarity="negative")

        bad = dict(syllabuses[0], source_evidence=["upstream"])
        NEG["n7c"] = refused(lambda: source_with(syllabuses=[bad]))
        check("N7_refuses_non_synthetic_source_evidence", NEG["n7c"][0], NEG["n7c"][1],
              polarity="negative")

        materials = base.materials()
        bad = dict(materials[0], access_mode="live")
        NEG["n7d"] = refused(lambda: source_with(materials=[bad]))
        check("N7_refuses_live_access_material", NEG["n7d"][0], NEG["n7d"][1],
              polarity="negative")

        seasons = base.timetable_seasons()
        bad = dict(seasons[0])
        bad.pop("reason")
        NEG["n7e"] = refused(lambda: source_with(timetable_seasons=[bad]))
        check("N7_refuses_unavailable_season_without_reason", NEG["n7e"][0], NEG["n7e"][1],
              polarity="negative")

        events = base.timetable_events()
        dated = next(row for row in events if row.get("date"))
        bad = dict(dated, raw_text=None)
        NEG["n7f"] = refused(lambda: source_with(timetable_events=[bad]))
        check("N7_refuses_date_without_raw_text", NEG["n7f"][0], NEG["n7f"][1],
              polarity="negative")

        windows = base.timetable_windows()
        cie_window = next(row for row in windows
                          if "start" in (row.get("unknown_boundaries") or ()))
        bad = dict(cie_window, parsed={"start": "2026-06-01", "end": None})
        NEG["n7g"] = refused(lambda: source_with(timetable_windows=[bad]))
        check("N7_refuses_unknown_boundary_with_parsed_value", NEG["n7g"][0], NEG["n7g"][1],
              polarity="negative")

        bad = dict(cie_window, unknown_boundaries=["start"])
        NEG["n7h"] = refused(lambda: source_with(timetable_windows=[bad]))
        check("N7_refuses_undeclared_missing_boundary", NEG["n7h"][0], NEG["n7h"][1],
              polarity="negative")

        class _UnvalidatedSource:
            def syllabuses(self):
                return None

            def materials(self):
                return base.materials()

            def timetable_seasons(self):
                return base.timetable_seasons()

            def timetable_events(self):
                return base.timetable_events()

            def timetable_windows(self):
                return base.timetable_windows()

        NEG["n7i"] = refused(lambda: validate_feature_source(_UnvalidatedSource()))
        check("N7_refuses_non_list_family_rows", NEG["n7i"][0], NEG["n7i"][1],
              polarity="negative")

        NEG["n7j"] = refused(lambda: default_dataset(features=_UnvalidatedSource()))
        check("N7_dataset_refuses_unvalidated_source", NEG["n7j"][0], NEG["n7j"][1],
              polarity="negative")

    run_section("N7", section_n7)

    # ====================================================================== #
    # J: the operations view: stopped jobs stay stopped, published coverage
    #    reads back from the one configured root, diagnostics are sanitized
    # ====================================================================== #
    J_STATE: dict = {}
    OPERATIONS_WARNING_TEXT = ("operations view: checkpoints are read-only observations from the "
                               "configured operations root; no job service is staged and nothing "
                               "is resumed or written")
    COMPUTED_AT_RE = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\+00:00")

    def _string_leaves(value):
        if isinstance(value, dict):
            for child in value.values():
                yield from _string_leaves(child)
        elif isinstance(value, list):
            for child in value:
                yield from _string_leaves(child)
        elif isinstance(value, str):
            yield value

    def section_j() -> None:
        tree_before = tree_snapshot(candidate)
        operations_root = (candidate / "fixtures" / "synthetic"
                           / "operations" / "operations-root")

        # -- the view is opt-in, and the configured root is the fixture one -- #
        off_dataset = default_dataset(operations_root=None)
        check("J_operations_disabled_when_unconfigured",
              off_dataset.operations is None,
              "default_dataset(operations_root=None) carries no operations view",
              polarity="negative")

        on_dataset = default_dataset()
        operations = on_dataset.operations
        check("J_operations_enabled_from_environment",
              operations is not None and operations.root == operations_root.resolve(),
              f"root={getattr(operations, 'root', None)}", polarity="positive")

        by_id = operations.jobs.by_id()
        check("J_jobs_by_id_serves_current_only",
              sorted(by_id) == ["job:cie:cie-batch:8888", "job:cie:cie-batch:9191",
                                "job:ielts:synthetic-run-ok",
                                "job:ielts:synthetic-run-partial",
                                "job:unknown:unknown:unsupported:checkpoint.json"],
              sorted(by_id), polarity="positive")

        stages = {job.id: job.stage for job in by_id.values()}
        check("J_stages_reflect_the_checkpoints",
              stages == {"job:cie:cie-batch:8888": "running",
                         "job:cie:cie-batch:9191": "stopped_requires_resume",
                         "job:ielts:synthetic-run-ok": "succeeded",
                         "job:ielts:synthetic-run-partial": "partial",
                         "job:unknown:unknown:unsupported:checkpoint.json": "unknown"},
              stages, polarity="positive")

        stale_8888 = operations.jobs.superseded_for("cie", "cie-batch:8888")
        stale_ok = operations.jobs.superseded_for("ielts", "synthetic-run-ok")
        check("J_superseded_only_in_superseded_lists",
              [job.stage for job in stale_8888] == ["stopped"]
              and [job.stage for job in stale_ok] == ["partial"]
              and operations.jobs.superseded_for("cie", "cie-batch:9191") == [],
              {"cie-batch:8888": [job.stage for job in stale_8888],
               "synthetic-run-ok": [job.stage for job in stale_ok]}, polarity="positive")

        check("J_no_job_conflicts",
              operations.jobs.conflicts == []
              and operations.jobs.conflicts_for("cie", "cie-batch:8888") == [],
              operations.jobs.conflicts, polarity="positive")

        check("J_view_scanned_once_and_clean",
              operations.truncated is False and operations.skipped == []
              and operations.problems == [] and operations.scanned_files == 7,
              {"scanned": operations.scanned_files, "truncated": operations.truncated,
               "skipped": operations.skipped, "problems": operations.problems},
              polarity="positive")

        # -- the served routes ------------------------------------------------- #
        with TestClient(create_app(), raise_server_exceptions=False) as client:
            jobs_9191 = json_or_none(client.get("/api/v2/jobs/job:cie:cie-batch:9191"))
            jobs_8888 = json_or_none(client.get("/api/v2/jobs/job:cie:cie-batch:8888"))
            deferred = json_or_none(client.get("/api/v2/jobs/job_synthetic_coverage"))
            coverage_on = json_or_none(client.get("/api/v2/coverage"))
        with TestClient(create_app(dataset=off_dataset), raise_server_exceptions=False) as client:
            coverage_off = json_or_none(client.get("/api/v2/coverage"))

        item = (jobs_9191 or {}).get("data", {}).get("item", {})
        check("J_route_9191_stays_stopped_and_flags_resume",
              item.get("public_id") == "job:cie:cie-batch:9191"
              and item.get("stage") == "stopped_requires_resume"
              and item.get("resume_required") is True
              and item.get("stop_reason") == "download_error"
              and (item.get("resume") or {}).get("needs_user_resume") is True
              and (item.get("resume") or {}).get("resume_policy") == "manual"
              and (item.get("stop") or {}).get("detail", {}).get("paper") == "11"
              and item.get("payload_sha256")
              == "9eb281a2a56df32383be6a7b11c86b7bb067f433526b294879c6367fca4ac554",
              {"stage": item.get("stage"), "resume": item.get("resume"),
               "stop": (item.get("stop") or {}).get("reason")}, polarity="positive")

        error_text = (item.get("stop") or {}).get("detail", {}).get("error")
        check("J_route_9191_error_is_fixture_redacted",
              error_text == "cannot download <path> for subject 9191: "
                            "HTTP 403 (key <secret>)",
              error_text if error_text is not None else "missing", polarity="positive")

        superseded_route = (jobs_9191 or {}).get("data", {}).get("superseded")
        check("J_route_9191_has_no_superseded_or_conflicts",
              superseded_route == [] and (jobs_9191 or {}).get("data", {}).get("conflicts") == [],
              {"superseded": superseded_route}, polarity="positive")

        warnings_9191 = ((jobs_9191 or {}).get("meta") or {}).get("warnings")
        check("J_operations_warning_appended_on_route",
              warnings_9191 == [OPERATIONS_WARNING_TEXT],
              warnings_9191, polarity="positive")
        check("J_route_9191_envelope_completeness",
              ((jobs_9191 or {}).get("meta") or {}).get("completeness") == "complete"
              and (jobs_9191 or {}).get("error") is None,
              ((jobs_9191 or {}).get("meta") or {}).get("completeness"), polarity="positive")

        # -- sanitization of the served diagnostics (data subtree only: the --
        # -- envelope's own schema_version string legitimately carries "/") -- #
        data_leaves = list(_string_leaves((jobs_9191 or {}).get("data")))
        raw_hits = [leaf for leaf in data_leaves
                    if "C:" in leaf or "weo" in leaf or SYNTHETIC_KEY_CONTROL in leaf]
        path_hits = [leaf for leaf in data_leaves if contains_path(leaf)]
        check("J_route_leaves_carry_no_raw_paths_or_secrets",
              not raw_hits and not path_hits,
              (raw_hits + path_hits)[:4], polarity="negative")
        check("J_route_leaves_expose_the_placeholders",
              any("<path>" in leaf for leaf in data_leaves)
              and any("<secret>" in leaf for leaf in data_leaves),
              f"{len(data_leaves)} string leaves", polarity="positive")

        item_8888 = (jobs_8888 or {}).get("data", {}).get("item", {})
        superseded_8888 = (jobs_8888 or {}).get("data", {}).get("superseded", [])
        superseded_stages = [row.get("stage") for row in superseded_8888]
        superseded_shas = [row.get("payload_sha256") for row in superseded_8888]
        check("J_route_8888_current_running_old_stopped_only_superseded",
              item_8888.get("stage") == "running"
              and item_8888.get("payload_sha256")
              == "c31696a05ce917d471249f289d409d98217ec4064e9043d7783821a8a1ccf0e3"
              and superseded_stages == ["stopped"]
              and superseded_shas
              == ["76559fb8ca482bd80a0075bceaea47870dc5b1932491a7d7a8eadf0aa5755673"],
              {"stage": item_8888.get("stage"), "superseded": superseded_stages},
              polarity="positive")

        deferred_item = (deferred or {}).get("data", {}).get("item", {})
        check("J_deferred_job_fixture_still_served",
              deferred_item.get("integration_status") == "deferred_active_owner"
              and deferred_item.get("evidence") == "synthetic_fixture"
              and ((deferred or {}).get("meta") or {}).get("completeness") == "unknown",
              deferred_item.get("public_id"), polarity="positive")

        # -- the coverage route: identical items/gaps, additive operations --- #
        on_data = (coverage_on or {}).get("data", {})
        off_data = (coverage_off or {}).get("data", {})
        check("J_coverage_route_items_gaps_identical_with_and_without_operations",
              on_data.get("items") is not None
              and canonical_digest({"items": on_data.get("items"),
                                    "gaps": on_data.get("gaps")})
              == canonical_digest({"items": off_data.get("items"),
                                   "gaps": off_data.get("gaps")}),
              canonical_digest({"items": on_data.get("items")})[:16], polarity="positive")
        check("J_disabled_app_has_no_operations_key",
              "operations" not in off_data, sorted(off_data), polarity="negative")
        check("J_route_coverage_warning_appended",
              ((coverage_on or {}).get("meta") or {}).get("warnings")
              == [OPERATIONS_WARNING_TEXT],
              ((coverage_on or {}).get("meta") or {}).get("warnings"), polarity="positive")

        root_public = (on_data.get("operations") or {}).get("root", {})
        check("J_route_root_block_disclosed",
              root_public == {"kind": "configured", "configured": True,
                              "scanned_files": 7, "truncated": False,
                              "skipped": [], "problems": []},
              root_public, polarity="positive")

        checkpoints_public = (on_data.get("operations") or {}).get("checkpoints", {})
        rows = checkpoints_public.get("rows", [])
        freshness_counts = Counter(row.get("freshness") for row in rows)
        check("J_checkpoints_seven_rows_five_current_two_superseded",
              len(rows) == 7 and freshness_counts == {"current": 5, "superseded": 2},
              dict(freshness_counts), polarity="positive")

        sha_mismatch: list[str] = []
        for row in rows:
            source = row.get("source")
            recorded_sha = row.get("payload_sha256")
            if not isinstance(source, str) or not isinstance(recorded_sha, str):
                sha_mismatch.append(str(source))
                continue
            payload = operations_root / source.replace(":", "/")
            if not payload.is_file() or sha256(payload) != recorded_sha:
                sha_mismatch.append(source)
        check("J_checkpoint_payload_hashes_recompute_7_of_7",
              len(rows) == 7 and not sha_mismatch,
              sha_mismatch[:4] or "7 files byte-bound to their recorded payload sha",
              polarity="positive")

        pin_by_source = {row.get("source"): row.get("payload_sha256") for row in rows}
        check("J_checkpoint_payload_hashes_pin_three",
              pin_by_source.get("cie-batch-8888:checkpoint.json")
              == "c31696a05ce917d471249f289d409d98217ec4064e9043d7783821a8a1ccf0e3"
              and pin_by_source.get("cie-batch-8888-stale:checkpoint.json")
              == "76559fb8ca482bd80a0075bceaea47870dc5b1932491a7d7a8eadf0aa5755673"
              and pin_by_source.get("cie-location-batch:checkpoint.json")
              == "9eb281a2a56df32383be6a7b11c86b7bb067f433526b294879c6367fca4ac554",
              pin_by_source, polarity="positive")

        unsupported_row = next((row for row in rows if row.get("state") == "unknown"), {})
        check("J_unsupported_checkpoint_recorded_unknown",
              unsupported_row.get("problems") == ["unrecognised_checkpoint_format"]
              and any("unrecognised_checkpoint_format" in (problem.get("problems") or [])
                      for problem in checkpoints_public.get("problems", [])),
              {"row": unsupported_row.get("source"),
               "problems": checkpoints_public.get("problems")}, polarity="positive")
        check("J_checkpoints_conflicts_empty",
              checkpoints_public.get("conflicts") == [],
              checkpoints_public.get("conflicts"), polarity="positive")

        briefs = (on_data.get("operations") or {}).get("jobs", [])
        brief_by_key = {(brief.get("public_id"), brief.get("freshness")): brief.get("stage")
                        for brief in briefs}
        check("J_jobs_briefs_show_stopped_and_superseded_states",
              len(briefs) == 7
              and brief_by_key.get(("job:cie:cie-batch:9191", "current"))
              == "stopped_requires_resume"
              and brief_by_key.get(("job:cie:cie-batch:8888", "current")) == "running"
              and brief_by_key.get(("job:cie:cie-batch:8888", "superseded")) == "stopped"
              and brief_by_key.get(("job:ielts:synthetic-run-ok", "superseded")) == "partial"
              and brief_by_key.get(("job:ielts:synthetic-run-partial", "current")) == "partial"
              and brief_by_key.get(("job:unknown:unknown:unsupported:checkpoint.json",
                                    "current")) == "unknown",
              len(briefs), polarity="positive")

        # -- the published coverage rows --------------------------------------- #
        published_public = (on_data.get("operations") or {}).get("published")
        pub_rows = published_public.get("rows", []) if isinstance(published_public, dict) else []
        check("J_published_four_rows_and_schema_absent",
              [row.get("public_id") for row in pub_rows]
              == ["coverage:published:cie-questions", "coverage:published:ielts-questions",
                  "coverage:published:edexcel-assets", "coverage:published:toefl-courses"]
              and all("schema" not in row for row in pub_rows),
              [row.get("public_id") for row in pub_rows], polarity="positive")

        validations = {row.get("public_id"): Coverage.from_dict(row).validate()
                       for row in pub_rows}
        check("J_published_rows_pass_the_coverage_contract",
              bool(pub_rows) and all(not problems for problems in validations.values()),
              {key: value for key, value in validations.items() if value},
              polarity="positive")

        by_public = {row.get("public_id"): row for row in pub_rows}
        cie_row = by_public.get("coverage:published:cie-questions", {})
        ielts_row = by_public.get("coverage:published:ielts-questions", {})
        edx_row = by_public.get("coverage:published:edexcel-assets", {})
        toefl_row = by_public.get("coverage:published:toefl-courses", {})
        edx_exclusions = edx_row.get("exclusions") or [{}]
        check("J_published_statuses_pinned",
              cie_row.get("percentage") == 71.43
              and cie_row.get("derived_status") == "partial"
              and cie_row.get("denominator")
              == "manifest:expected-manifest.json#cie-questions:expected=7"
              and ielts_row.get("percentage") == 100.0
              and ielts_row.get("derived_status") == "complete"
              and ielts_row.get("denominator")
              == "manifest:expected-manifest.json#ielts-questions:expected=8"
              and edx_row.get("percentage") == 50.0
              and edx_row.get("derived_status") == "partial"
              and edx_exclusions[0].get("public_id")
              == "asset_6xyrzhw4g5dy56xaxmhzk52da6zem5vu"
              and bool(edx_exclusions[0].get("reason"))
              and toefl_row.get("percentage") is None
              and toefl_row.get("denominator_known") is False
              and toefl_row.get("derived_status") == "unknown",
              {row.get("public_id"): row.get("percentage") for row in pub_rows},
              polarity="positive")

        check("J_computed_at_is_utc_second_precision",
              bool(pub_rows) and all(COMPUTED_AT_RE.fullmatch(str(row.get("computed_at")))
                                     for row in pub_rows),
              [row.get("computed_at") for row in pub_rows][:2], polarity="positive")

        # -- negative controls: a bad root is a recorded problem, not a raise -- #
        missing_view = default_dataset(
            operations_root=candidate / "fixtures" / "synthetic"
            / "operations" / "absent-root").operations
        check("J_missing_root_is_reported_not_raised",
              missing_view is not None and missing_view.root_kind == "missing"
              and [problem.get("code") for problem in missing_view.problems]
              == ["operations_root_missing"],
              {"kind": getattr(missing_view, "root_kind", None)}, polarity="negative")

        write_prefixes = ("resume", "write", "start", "cancel", "enqueue", "delete", "remove")
        suspicious: list[str] = []
        for module in (ops_jobs, ops_published):
            names = set(getattr(module, "__all__", ()) or ())
            names.update(name for name in dir(module) if not name.startswith("_"))
            suspicious.extend(f"{module.__name__}.{name}" for name in sorted(names)
                              if name.lower().startswith(write_prefixes))
        check("J_operations_modules_expose_no_write_surface",
              not suspicious,
              suspicious[:6] or "no resume/write/start/cancel/enqueue/delete/remove names",
              polarity="negative")

        tree_after = tree_snapshot(candidate)
        check("J_candidate_tree_unchanged_by_the_view", tree_before == tree_after,
              f"{len(tree_before)} files before and after", polarity="positive")

        J_STATE.update({
            "root": str(getattr(operations, "root", None)),
            "scanned_files": getattr(operations, "scanned_files", None),
            "root_block": root_public,
            "checkpoint_rows": len(rows),
            "freshness_counts": dict(freshness_counts),
            "jobs_by_id": sorted(by_id),
            "stages": stages,
            "briefs": len(briefs),
            "published": [{"public_id": row.get("public_id"),
                           "derived_status": row.get("derived_status"),
                           "percentage": row.get("percentage")} for row in pub_rows],
            "route_9191_error": error_text,
            "sanitized_leaf_count": len(data_leaves),
            "warnings": warnings_9191,
            "tree_unchanged": tree_before == tree_after,
        })

    run_section("J", section_j)

    # ====================================================================== #
    # Report
    # ====================================================================== #
    NOT_RUN.extend([
        {"check": "real merge into the original project",
         "reason": "gate original_paths_released is closed; the plan entry remains a proposal "
                   "(deferred_pending_release) and the original tree was never read or written"},
        {"check": "real active-owner integration (materials, syllabuses and timetables served "
                  "by the original owner modules)",
         "reason": "no owner release exists for the active-owner families; the seam serves only "
                   "clearly labelled synthetic fixtures and the real integration stays "
                   "deferred_active_owner"},
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
                   "real credential is used, read, fabricated or staged; the only "
                   "credential-shaped value anywhere is the fixture-labelled synthetic control "
                   "string the operations fixtures carry, and the routing controls are "
                   "synthetic request parameters with no secret values"},
        {"check": "real frontend cutover (the staged page and server on the live service)",
         "reason": "gate existing_service_cutover_authorized is closed; the staged frontend ran "
                   "only on an ephemeral 127.0.0.1 port against the private read API"},
        {"check": "real source-provider fetching from the frontend process",
         "reason": "gate upstream_requests_authorized is closed; the candidate frontend carries "
                   "no source-discovery logic and only proxies the private read API"},
        {"check": "real job-service interaction (resume / cancel / enqueue against a live queue)",
         "reason": "no job-service release exists and none is needed: the operations view is "
                   "read-only by construction, and a stopped job is only observed as stopped; "
                   "it is never resumed, restarted or written back"},
        {"check": "writes of any kind to an operations root (checkpoint repair, resume flags, "
                  "published manifests)",
         "reason": "gate original_paths_released is closed; the only operations root touched "
                   "was the candidate's own synthetic fixture directory, read once and never "
                   "modified"},
    ])

    failed = [record["name"] for record in CHECKS if not record["ok"]]
    ok = not failed
    candidate_manifest_path = candidate / "B07R_CANDIDATE_MANIFEST.json"
    manifest_doc = load_json(candidate_manifest_path) if candidate_manifest_path.is_file() else {}
    recorded = manifest_doc.get("candidate_tree", {})
    recomputed = tree_digest(candidate, tuple(recorded.get("excludes", []))) if recorded else {}

    report = {
        "schema": "examdata.integration.b07_route_probe/1",
        "run_id": RUN_ID,
        "packet": "B07",
        "candidate_root": str(candidate),
        "environment": {
            "cwd": str(Path.cwd()),
            "python": sys.version.split()[0],
            "executable": sys.executable,
            "pythonpath": os.environ.get("PYTHONPATH"),
            "staging_override": os.environ.get("EXAMDATA_INTEGRATION_STAGING_ROOT"),
            "root_env": os.environ.get("EXAMDATA_INTEGRATION_ROOT"),
            "operations_root": os.environ.get("EXAMDATA_OPERATIONS_ROOT"),
            "api_key_is_synthetic_control":
                os.environ.get("EXAMDATA_API_KEY") == SYNTHETIC_KEY_CONTROL,
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
        "seam": S_STATE,
        "operations": J_STATE,
        "frontend": F_STATE,
        "discovery_projection": G_STATE,
        "cross_stack": H_STATE,
        "b07_vs_b06_stability": DOC.get("b07_vs_b06_stability"),
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
                 "confined to the run directory's evidence/tmp; the active-owner seam was "
                 "rehearsed against labelled synthetic fixtures only; the operations view was "
                 "rehearsed against the candidate's own synthetic checkpoint fixtures, read "
                 "once, and stopped jobs were only observed as stopped; nothing was resumed, "
                 "started or written; the only credential-shaped value anywhere is the "
                 "fixture-labelled synthetic control string; no real credential was used, read "
                 "or fabricated; the staged frontend ran only on an ephemeral 127.0.0.1 server "
                 "against the private read API"),
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
