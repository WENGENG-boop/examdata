"""B04 pre-build mechanics scratch (private; not evidence).

Empirically answers, against the frozen B03 candidate and a clearly synthetic
host, the questions that decide compose.py's shape:

  1. does host.include_router(v2_app.router) keep the v2 paths intact?
  2. what does the combined OpenAPI document contain (op ids, legacy ops)?
  3. what 404/405/500 shapes does the raw-include host produce for v2 paths?
  4. does FastAPI's ExceptionMiddleware read host.exception_handlers by
     reference (so a factory-time mutation is honored)?
"""
from __future__ import annotations

import json
import os
import sys

CANDIDATE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..",
    "b03-rehearsal-2026-10-07", "candidates", "b03-contracts-catalog-v1")
CANDIDATE = os.path.abspath(CANDIDATE)
sys.path.insert(0, os.path.join(CANDIDATE, "src"))
os.environ["EXAMDATA_INTEGRATION_ROOT"] = CANDIDATE

from fastapi import FastAPI, Query  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from starlette.routing import Match  # noqa: E402

from examdata.integration.api import create_app  # noqa: E402
from examdata.integration.api import links  # noqa: E402

out: dict = {}

# ---- 1. v2 app --------------------------------------------------------- #
v2 = create_app()
out["v2_route_types"] = [type(r).__name__ for r in v2.router.routes]
v2_doc = v2.openapi()
out["v2_openapi_path_count"] = len(v2_doc.get("paths", {}))
v2_ops = {}
for p, ops in v2_doc["paths"].items():
    for m, op in ops.items():
        v2_ops[f"{m.upper()} {p}"] = op.get("operationId")
out["v2_operation_id_sample"] = dict(list(v2_ops.items())[:3])
out["v2_operation_ids_unique"] = len(set(v2_ops.values())) == len(v2_ops)
bin_path = links.spec_for("syllabuses.content").full_path + "," + "get"
op = v2_doc["paths"][links.spec_for("syllabuses.content").full_path]["get"]
out["v2_binary_200_content_before_transform"] = sorted(
    op["responses"]["200"]["content"])
out["v2_binary_doc_is_transformed"] = "application/json" not in op["responses"]["200"]["content"]

# ---- 2. synthetic host ------------------------------------------------ #
host = FastAPI(title="synthetic-legacy-host")


@host.get("/papers")
def papers():
    return {"legacy": True}


@host.get("/numbers")
def numbers(limit: int = Query(0)):
    return {"limit": limit}


@host.get("/boom")
def boom():
    raise RuntimeError("synthetic legacy failure")


legacy_before = {}
pre = TestClient(host)
legacy_before["papers"] = (pre.get("/papers").status_code, pre.get("/papers").text,
                           pre.get("/papers").headers.get("content-type"))
r = pre.get("/numbers?limit=abc")
legacy_before["numbers_422"] = (r.status_code, r.text, r.headers.get("content-type"))
legacy_before["unknown_404"] = (pre.get("/nope").status_code, pre.get("/nope").text,
                                pre.get("/nope").headers.get("content-type"))
pre_stack = TestClient(host, raise_server_exceptions=False)
legacy_before["boom_500"] = (pre_stack.get("/boom").status_code,
                             pre_stack.get("/boom").text,
                             pre_stack.get("/boom").headers.get("content-type"))
host_doc_before = host.openapi()
out["legacy_before"] = legacy_before

# handler-dict reference question: build stack via a request, then compare
stack = host.middleware_stack
seen = []
node = stack
while node is not None:
    seen.append(type(node).__name__)
    node = getattr(node, "app", None)
out["middleware_chain"] = seen
exc_mw = None
node = stack
while node is not None:
    if "Exception" in type(node).__name__:
        exc_mw = node
        break
    node = getattr(node, "app", None)
if exc_mw is not None:
    handlers_attr = getattr(exc_mw, "_exception_handlers", None)
    out["exc_mw_handlers_is_same_object"] = handlers_attr is host.exception_handlers
    if handlers_attr is not None:
        probe_key = type("ProbeError", (Exception,), {})
        host.exception_handlers[probe_key] = lambda r, e: None
        out["post_build_mutation_visible_in_mw"] = probe_key in handlers_attr
        del host.exception_handlers[probe_key]

# ---- 3. raw include (negative control semantics) ----------------------- #
host.include_router(v2.router)
out["host_route_types_after_include"] = [type(r).__name__ for r in host.routes]

doc_after = host.openapi()
out["host_openapi_path_count"] = len(doc_after.get("paths", {}))
combined_ops = {}
for p, ops in doc_after.get("paths", {}).items():
    for m, o in ops.items():
        combined_ops[f"{m.upper()} {p}"] = o.get("operationId")
out["combined_operation_ids_unique"] = len(set(combined_ops.values())) == len(combined_ops)
out["v2_op_ids_preserved"] = all(
    combined_ops.get(k) == v for k, v in v2_ops.items())
legacy_after = {k: doc_after["paths"].get(k) for k in host_doc_before["paths"]}
legacy_doc_unchanged = all(
    legacy_after[k] == v for k, v in host_doc_before["paths"].items())
out["legacy_doc_unchanged_by_include"] = legacy_doc_unchanged
bpath = links.spec_for("syllabuses.content").full_path
out["host_binary_200_content_after_include"] = sorted(
    doc_after["paths"][bpath]["get"]["responses"]["200"]["content"])

client = TestClient(host)
raw = {}
r = client.get("/api/v2/info")
raw["v2_info"] = (r.status_code, r.headers.get("content-type"), r.text[:80])
r = client.get("/api/v2/unknown")
raw["v2_unknown_404"] = (r.status_code, r.headers.get("content-type"), r.text)
try:
    r = client.get("/api/v2/jobs/does-not-exist")
    raw["v2_apierror_404"] = (r.status_code, r.headers.get("content-type"), r.text[:200])
except Exception as exc:
    raw["v2_apierror_404"] = f"RAISED:{type(exc).__name__}:{exc}"
r = client.get("/api/v2/")
raw["v2_root"] = (r.status_code, r.text[:80])
raw_check = TestClient(host, raise_server_exceptions=False)
r = raw_check.get("/api/v2/jobs/does-not-exist")
raw["v2_apierror_404_noraise"] = (r.status_code, r.headers.get("content-type"), r.text[:120])
out["raw_include_v2_shapes"] = raw

# legacy behavior after raw include (should be untouched)
legacy_after_probe = {}
post = TestClient(host)
legacy_after_probe["papers"] = (post.get("/papers").status_code, post.get("/papers").text,
                                post.get("/papers").headers.get("content-type"))
r = post.get("/numbers?limit=abc")
legacy_after_probe["numbers_422"] = (r.status_code, r.text, r.headers.get("content-type"))
legacy_after_probe["unknown_404"] = (post.get("/nope").status_code, post.get("/nope").text,
                                     post.get("/nope").headers.get("content-type"))
post_stack = TestClient(host, raise_server_exceptions=False)
legacy_after_probe["boom_500"] = (post_stack.get("/boom").status_code,
                                  post_stack.get("/boom").text,
                                  post_stack.get("/boom").headers.get("content-type"))
out["legacy_after_raw_include"] = legacy_after_probe
out["legacy_identical"] = legacy_before == legacy_after_probe

# ---- 4. include-context integrity ------------------------------------- #
v2_paths = sorted(p for p, o in doc_after["paths"].items() if p.startswith("/api/v2"))
out["v2_paths_in_host_doc"] = len(v2_paths)
out["v2_paths_expected"] = sum(
    2 if s.binary else 1 for s in links.IMPLEMENTED_SPECS)
out["first_v2_paths"] = v2_paths[:4]

print(json.dumps(out, ensure_ascii=True, indent=2, default=str))
