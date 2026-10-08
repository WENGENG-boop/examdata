"""B04 pre-probe scratch 2: scoped handlers against the rebuilt candidate.

Run against iteration 3 of the candidate (compose.py with the server-error
fallback). Verifies:

  1. every legacy probe, including an uncaught exception, is byte-identical
     to the un-attached baseline;
  2. the v2-prefix synthetic controls all change shape (scoping works);
  3. with raise_server_exceptions=True both hosts raise the same legacy error;
  4. the v2 runtime answers through the composed host with the envelope.
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


PROBES = [
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
]


def probes(client: TestClient) -> dict:
    result = {}
    for key, method, url in PROBES:
        r = client.request(method, url)
        result[key] = {
            "status": r.status_code,
            "content_type": r.headers.get("content-type"),
            "sha256": hashlib.sha256(r.content).hexdigest(),
        }
    return result


baseline = probes(TestClient(make_host(), raise_server_exceptions=False))

host2 = make_host()
attach_v2(host2)
after = probes(TestClient(host2, raise_server_exceptions=False))

legacy_keys = [k for k in after if not k.startswith("v2_")]
out["legacy_identical"] = {k: baseline[k] == after[k] for k in legacy_keys}
out["legacy_identical_all"] = all(out["legacy_identical"].values())
out["v2_changed"] = {k: baseline[k]["status"] != after[k]["status"]
                     for k in after if k.startswith("v2_")}
out["boom_baseline"] = baseline["boom_500"]
out["boom_after"] = after["boom_500"]

# raise-mode equivalence for the legacy uncaught error
def raises(client: TestClient) -> str:
    try:
        client.get("/synthetic-legacy/boom")
        return "no-raise"
    except Exception as exc:  # noqa: BLE001
        return f"{type(exc).__name__}: {exc}"


out["boom_raise_baseline"] = raises(TestClient(make_host()))
out["boom_raise_after"] = raises(TestClient(host2))
out["boom_raise_same"] = out["boom_raise_baseline"] == out["boom_raise_after"]

# v2 envelope details through the composed host
client2 = TestClient(host2, raise_server_exceptions=False)
details = {}
for key, method, url in [
    ("jobs", "GET", "/api/v2/jobs/does-not-exist"),
    ("unknown", "GET", "/api/v2/unknown"),
    ("post_info", "POST", "/api/v2/info"),
    ("typed", "GET", "/api/v2/__synthetic_typed?q=abc"),
    ("stack_boom", "GET", "/api/v2/__synthetic_boom"),
]:
    r = client2.request(method, url)
    try:
        body = r.json()
    except Exception:  # noqa: BLE001
        body = None
    details[key] = {
        "status": r.status_code,
        "content_type": r.headers.get("content-type"),
        "schema_version": body.get("schema_version") if isinstance(body, dict) else None,
        "error_code": (body.get("error") or {}).get("code") if isinstance(body, dict) else None,
    }
r = client2.get("/api/v2/info")
body = r.json()
details["info"] = {
    "status": r.status_code,
    "content_type": r.headers.get("content-type"),
    "schema_version": body.get("schema_version"),
    "error_code": (body.get("error") or {}).get("code") if isinstance(body, dict) else None,
}
out["v2_details"] = details
out["v2_boom_is_envelope"] = details["stack_boom"]["content_type"] == "application/json" \
    and details["stack_boom"]["error_code"] == "internal_error"

print(json.dumps(out, ensure_ascii=True, indent=2, default=str))
