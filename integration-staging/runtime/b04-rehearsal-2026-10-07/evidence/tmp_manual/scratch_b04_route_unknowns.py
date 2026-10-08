"""Manual scratch: resolve the remaining unknowns before b04_route_probe.py.

Unknowns:
1. shape of the compose-time `_IncludedRouter` entry appended by
   `host.include_router(v2.router)` (path attr? routes? original_router?)
2. A12 dummy host: braced legacy paths with no-arg handlers register cleanly
3. does `host.openapi()` before attach leave middleware_stack None
4. does `GET /openapi.json` serve the same JSON as `host.openapi()` after attach
5. binary fixture runtime through the composed host (fixture ids, 200/206/304/HEAD)
6. iter_routes ordering simulation on `v2.routes`
7. v2 operation ids equal between standalone doc and composed host doc
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from pathlib import Path

CANDIDATE = Path(os.environ["B04_CANDIDATE_ROOT"]).resolve()
sys.path.insert(0, str(CANDIDATE / "src"))
sys.dont_write_bytecode = True

from fastapi import FastAPI, Query  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

from examdata.integration.api import links  # noqa: E402
from examdata.integration.api import openapi as api_openapi  # noqa: E402
from examdata.integration.api.app import create_app  # noqa: E402
from examdata.integration.api.compose import attach_v2  # noqa: E402
from examdata.integration.api.dataset import SYLLABUS_FIXTURES  # noqa: E402

OUT: dict = {}
WORKSPACE = Path(os.environ["B04_WORKSPACE_ROOT"]).resolve()
A12 = json.loads((WORKSPACE / "docs/integration/execution/A12_ROUTE_COMPATIBILITY_WORKSHEET.json")
                 .read_text(encoding="utf-8"))
ROWS = A12["rows"]


def concrete(path: str) -> str:
    return re.sub(r"\{([^}]+)\}", lambda m: "synthetic-" + re.sub(r"[^A-Za-z0-9_-]", "-", m.group(1)), path)


# 1. _IncludedRouter introspection
v2 = create_app()
wrapper = v2.routes[0]
OUT["wrapper_type"] = type(wrapper).__name__
OUT["wrapper_attrs"] = sorted(a for a in dir(wrapper) if not a.startswith("_"))
OUT["wrapper_has_path"] = hasattr(wrapper, "path")
OUT["wrapper_path_value"] = getattr(wrapper, "path", "<absent>")
OUT["wrapper_routes_len"] = len(getattr(wrapper, "routes", None) or [])
OUT["wrapper_original_router"] = type(getattr(wrapper, "original_router", None)).__name__

routes_walked = list(api_openapi.iter_routes(v2.routes))
OUT["iter_routes_count"] = len(routes_walked)
OUT["iter_routes_types"] = sorted({type(r).__name__ for r in routes_walked})
OUT["iter_routes_get_head_first"] = [
    (sorted(getattr(r, "methods", None) or []), getattr(r, "path", None))
    for r in routes_walked[:4]
]

# ordering simulation sample for a binary row and a plain row
def first_match(method: str, path: str):
    for route in api_openapi.iter_routes(v2.routes):
        methods = getattr(route, "methods", None) or set()
        if method not in methods:
            continue
        rx = getattr(route, "path_regex", None)
        if rx is not None and rx.match(path):
            return route.path
    return None

for spec in links.ROUTE_SPECS:
    if spec.capability in ("syllabuses.content", "jobs.get", "timetables.events"):
        c = concrete(spec.full_path)
        OUT[f"order_{spec.capability}"] = {
            "concrete": c, "GET": first_match("GET", c),
            "HEAD": first_match("HEAD", c) if spec.binary else None,
        }

# 2. A12 dummy host construction
by_path: dict[str, set] = {}
for row in ROWS:
    by_path.setdefault(row["legacy_path"], set()).add(row["method"].upper())


def make_host():
    host = FastAPI()

    def stub():
        return {"legacy_route": "stub", "synthetic": True}

    for path, methods in by_path.items():
        host.add_api_route(path, stub, methods=sorted(methods))

    @host.get("/api/v2/__synthetic_typed")
    def typed(q: int = Query(1)):
        return {"q": q}

    @host.get("/api/v2/__synthetic_boom")
    def boom():
        raise RuntimeError("synthetic boom")

    return host


host = make_host()
OUT["dummy_host_route_count"] = len(host.routes)
try:
    with TestClient(host, raise_server_exceptions=False) as client:
        r = client.get(concrete("/api/v1/ielts/aggregate/{book}/{test}"))
        OUT["braced_dummy_probe"] = [r.status_code, r.headers.get("content-type"), r.text[:80]]
except Exception as exc:  # noqa: BLE001
    OUT["braced_dummy_probe"] = f"RAISED {type(exc).__name__}: {exc}"

# 3+4. openapi pre-attach + GET /openapi.json equality
host2 = make_host()
pre = host2.openapi()
OUT["pre_attach_middleware_stack_is_none"] = host2.middleware_stack is None
OUT["pre_attach_doc_paths"] = len(pre.get("paths", {}))
before_tbl = [(getattr(r, "path", None), sorted(getattr(r, "methods", None) or []),
               type(r).__name__)
              for r in host2.routes]
attach_v2(host2)
after_tbl = [(getattr(r, "path", None), sorted(getattr(r, "methods", None) or []),
              type(r).__name__)
             for r in host2.routes]
OUT["route_table_delta"] = len(after_tbl) - len(before_tbl)
OUT["route_table_prefix_kept"] = after_tbl[:len(before_tbl)] == before_tbl
OUT["new_entry"] = after_tbl[len(before_tbl):]
with TestClient(host2, raise_server_exceptions=False) as client:
    doc_direct = json.dumps(host2.openapi(), sort_keys=True, ensure_ascii=True)
    resp = client.get("/openapi.json")
    body = resp.json()
    OUT["openapi_route_equals_direct"] = body == host2.openapi()
    OUT["openapi_route_status"] = resp.status_code
    # binary runtime
    OUT["syllabus_fixture_ids"] = [r["public_id"] for r in SYLLABUS_FIXTURES]
    sid = SYLLABUS_FIXTURES[0]["public_id"]
    r200 = client.get(f"/api/v2/syllabuses/{sid}/content")
    OUT["binary_200"] = [r200.status_code, r200.headers.get("content-type"),
                         len(r200.content), r200.headers.get("etag")]
    r206 = client.get(f"/api/v2/syllabuses/{sid}/content", headers={"Range": "bytes=0-9"})
    OUT["binary_206"] = [r206.status_code, r206.headers.get("content-range"), len(r206.content)]
    r304 = client.get(f"/api/v2/syllabuses/{sid}/content",
                      headers={"If-None-Match": r200.headers.get("etag")})
    OUT["binary_304"] = [r304.status_code, len(r304.content)]
    rh = client.head(f"/api/v2/syllabuses/{sid}/content")
    OUT["binary_head"] = [rh.status_code, rh.headers.get("content-length")]
    OUT["direct_doc_sha"] = hashlib.sha256(doc_direct.encode()).hexdigest()[:16]

    # v2 control + legacy shapes on the composed host
    r_typed = client.get("/api/v2/__synthetic_typed", params={"q": "abc"}) \
        if any(getattr(rt, "path", None) == "/api/v2/__synthetic_typed" for rt in host2.routes) \
        else None
    OUT["controls_declared"] = r_typed is not None

# 5. binary doc rows after attach
after_doc = host2.openapi()
row = links.spec_for("syllabuses.content")
op = after_doc["paths"][row.full_path]["get"]
OUT["binary_doc_200_content"] = sorted(op["responses"]["200"]["content"].keys())
OUT["binary_doc_codes"] = sorted(str(k) for k in op["responses"].keys())
OUT["binary_doc_head_present"] = "head" in after_doc["paths"][row.full_path]

# 7. operation id equality standalone vs composed
standalone_doc = create_app().openapi()
v2_ids_standalone = {}
for p, ops in standalone_doc["paths"].items():
    for m, op in ops.items():
        v2_ids_standalone[f"{m.upper()} {p}"] = op.get("operationId")
composed_ids = {}
for p, ops in after_doc["paths"].items():
    if not p.startswith(links.PREFIX):
        continue
    for m, op in ops.items():
        composed_ids[f"{m.upper()} {p}"] = op.get("operationId")
OUT["v2_ids_equal"] = all(composed_ids.get(k) == v for k, v in v2_ids_standalone.items()) \
    and set(composed_ids) == set(v2_ids_standalone)
OUT["composed_id_count"] = len(composed_ids)

# verdict on api_openapi helpers on the v2 app
OUT["v2_runtime_pairs"] = len(api_openapi.runtime_pairs(v2))
OUT["v2_spec_pairs"] = len(api_openapi.spec_pairs(v2))
OUT["v2_head_pairs"] = len(api_openapi.runtime_head_pairs(v2))
OUT["v2_spec_head_pairs"] = len(api_openapi.spec_head_pairs(v2))
OUT["v2_advertised_pairs"] = len(links.advertised_pairs())
OUT["v2_agreement_problems"] = api_openapi.agreement_problems(v2)

print(json.dumps(OUT, indent=1, ensure_ascii=True, default=str))
