"""B04 pre-probe scratch: scoped-handler behavior on legacy paths (private).

Verifies, before the assertions are baked into b04_route_probe.py:

  1. what a plain FastAPI host carries in ``exception_handlers`` before attach;
  2. that after ``attach_v2`` every legacy probe (200/404/405/422/500) is
     byte-identical to the un-attached baseline;
  3. that the v2-prefix synthetic controls change shape (scoping works);
  4. that the v2 runtime answers through the composed host.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys

CANDIDATE = os.path.abspath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..",
    "b04-rehearsal-2026-10-07", "candidates", "b04-routes-v1"))
sys.path.insert(0, os.path.join(CANDIDATE, "src"))
os.environ["EXAMDATA_INTEGRATION_ROOT"] = CANDIDATE

from fastapi import FastAPI, Query  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from starlette.exceptions import HTTPException as StarletteHTTPException  # noqa: E402

from examdata.integration.api import create_app  # noqa: E402
from examdata.integration.api.compose import attach_v2  # noqa: E402

out: dict = {}


def make_host() -> FastAPI:
    host = FastAPI(title="synthetic-legacy-host")

    @host.get("/papers")
    def papers():
        return {"legacy_route": "/papers", "synthetic": True}

    @host.post("/sample")
    def sample_post():
        return {"legacy_route": "/sample", "synthetic": True}

    @host.get("/sample")
    def sample_get():
        return {"legacy_route": "/sample", "synthetic": True}

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


def probes(client: TestClient) -> dict:
    result = {}
    for key, method, url in [
        ("papers_200", "GET", "/papers"),
        ("sample_get_200", "GET", "/sample"),
        ("sample_post_200", "POST", "/sample"),
        ("echo_get_405", "GET", "/synthetic-legacy/echo"),
        ("echo_post_200", "POST", "/synthetic-legacy/echo"),
        ("absent_404", "GET", "/synthetic-legacy/absent"),
        ("numbers_default", "GET", "/synthetic-legacy/numbers"),
        ("numbers_422", "GET", "/synthetic-legacy/numbers?limit=abc"),
        ("boom_500", "GET", "/synthetic-legacy/boom"),
        ("v2_typed_422", "GET", "/api/v2/__synthetic_typed?q=abc"),
        ("v2_stack_boom", "GET", "/api/v2/__synthetic_boom"),
        ("v2_unknown_404", "GET", "/api/v2/unknown"),
        ("v2_info_200", "GET", "/api/v2/info"),
        ("v2_jobs_404", "GET", "/api/v2/jobs/does-not-exist"),
        ("v2_post_info_405", "POST", "/api/v2/info"),
    ]:
        r = client.request(method, url)
        result[key] = {
            "status": r.status_code,
            "content_type": r.headers.get("content-type"),
            "sha256": hashlib.sha256(r.content).hexdigest(),
        }
    return result


fresh = make_host()
out["fresh_exception_handler_keys"] = [
    f"{k.__module__}.{k.__qualname__}" if isinstance(k, type) else str(k)
    for k in fresh.exception_handlers
]
out["fresh_has_http_exception_handler"] = StarletteHTTPException in fresh.exception_handlers
out["fresh_middleware_stack_is_none"] = fresh.middleware_stack is None

baseline = probes(TestClient(make_host(), raise_server_exceptions=False))

host2 = make_host()
attach_v2(host2)
after = probes(TestClient(host2, raise_server_exceptions=False))

legacy_keys = [k for k in after if not k.startswith("v2_")]
out["legacy_identical"] = {k: baseline[k] == after[k] for k in legacy_keys}
out["baseline"] = baseline
out["after"] = after
out["v2_changed"] = {k: baseline[k]["status"] != after[k]["status"]
                     for k in after if k.startswith("v2_")}

# what do the v2 answers actually look like?
client2 = TestClient(host2, raise_server_exceptions=True)
r = client2.get("/api/v2/jobs/does-not-exist")
try:
    body = r.json()
    out["v2_jobs_body"] = {"status": r.status_code, "code": body.get("error", {}).get("code"),
                           "content_type": r.headers.get("content-type")}
except Exception as exc:  # noqa: BLE001
    out["v2_jobs_body"] = f"RAISED:{type(exc).__name__}:{exc}"
r = client2.post("/api/v2/info")
body = r.json()
out["v2_post_info_body"] = {"status": r.status_code, "code": body.get("error", {}).get("code")}
r = client2.get("/api/v2/unknown")
body = r.json()
out["v2_unknown_body"] = {"status": r.status_code, "code": body.get("error", {}).get("code")}

print(json.dumps(out, ensure_ascii=True, indent=2, default=str))
