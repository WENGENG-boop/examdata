"""Manual scratch 2: measure the negative controls' real behavior.

N1 raw include (recheck), N2 unscoped handler install, N3 mount, N5 late attach,
N6 wrong host type.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

CANDIDATE = Path(os.environ["B04_CANDIDATE_ROOT"]).resolve()
sys.path.insert(0, str(CANDIDATE / "src"))
sys.dont_write_bytecode = True

from fastapi import FastAPI  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

from examdata.integration.api.app import create_app  # noqa: E402
from examdata.integration.api.compose import attach_v2  # noqa: E402

OUT: dict = {}


def sha(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def make_host() -> FastAPI:
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


def probes(client: TestClient) -> dict:
    out = {}
    r = client.get("/api/legacy/papers")
    out["papers_200"] = [r.status_code, r.headers.get("content-type"), sha(r.content)]
    r = client.get("/synthetic-legacy/numbers")
    out["numbers_default"] = [r.status_code, r.headers.get("content-type"), sha(r.content)]
    r = client.get("/synthetic-legacy/numbers", params={"limit": "abc"})
    out["numbers_422"] = [r.status_code, r.headers.get("content-type"), sha(r.content)]
    r = client.get("/synthetic-legacy/boom")
    out["boom_500"] = [r.status_code, r.headers.get("content-type"), sha(r.content)]
    r = client.get("/api/legacy/absent")
    out["absent_404"] = [r.status_code, r.headers.get("content-type"), sha(r.content)]
    return out


# N1: raw include
h = make_host()
with TestClient(h, raise_server_exceptions=False) as c:
    base = probes(c)
h.include_router(create_app().router)
with TestClient(h, raise_server_exceptions=False) as c:
    after = probes(c)
    r = c.get("/api/v2/info")
    OUT["n1_v2_info"] = [r.status_code, r.headers.get("content-type")]
    r = c.get("/api/v2/__nope")
    OUT["n1_v2_unknown"] = [r.status_code, r.headers.get("content-type"), r.text[:60]]
    r = c.get("/api/v2/jobs/no-such-job")
    OUT["n1_v2_apierror"] = [r.status_code, r.headers.get("content-type"), r.text[:60]]
    doc = h.openapi()
    row = doc["paths"].get("/api/v2/syllabuses/{id}/content", {}).get("get", {})
    OUT["n1_binary_200_content"] = sorted(row.get("responses", {}).get("200", {}).get("content", {}))
OUT["n1_legacy_unchanged"] = base == after

# N2: unscoped handler install (installed BEFORE the first request; after the
# stack is built the mutation is correctly invisible, which is a different fact)
h2 = make_host()
v2 = create_app()
for exc_class, handler in v2.exception_handlers.items():
    h2.add_exception_handler(exc_class, handler)
with TestClient(h2, raise_server_exceptions=False) as c:
    after2 = probes(c)
diff = {}
for k, before in base.items():
    if before != after2[k]:
        diff[k] = {"before": before, "after": after2[k]}
OUT["n2_changed_legacy"] = sorted(diff)
OUT["n2_diff"] = diff
OUT["n2_boom_after"] = after2["boom_500"]
OUT["n2_absent_after"] = after2["absent_404"]
OUT["n2_numbers_after"] = after2["numbers_422"]

# N3: mount
h3 = make_host()
h3.mount("/api/v2", create_app())
with TestClient(h3, raise_server_exceptions=False) as c:
    r = c.get("/api/v2/info")
    OUT["n3_info_direct"] = [r.status_code, r.headers.get("content-type"), r.text[:50]]
    r = c.get("/api/v2/api/v2/info")
    OUT["n3_doubled"] = [r.status_code, r.headers.get("content-type")]
    OUT["n3_doc_v2_paths"] = sorted(p for p in h3.openapi()["paths"] if p.startswith("/api/v2"))

# N5: late attach
h5 = make_host()
client5 = TestClient(h5, raise_server_exceptions=False)
client5.get("/api/legacy/papers")
OUT["n5_middleware_built"] = h5.middleware_stack is not None
try:
    attach_v2(h5)
    OUT["n5_result"] = "NOT REFUSED"
except RuntimeError as exc:
    OUT["n5_result"] = f"RuntimeError: {exc}"
OUT["n5_no_v2_paths_after"] = not any(
    p.startswith("/api/v2") for p in h5.openapi()["paths"])

# N6: wrong type
for value in (None, "x"):
    try:
        attach_v2(value)
        OUT[f"n6_{value!r}"] = "NOT REFUSED"
    except TypeError as exc:
        OUT[f"n6_{value!r}"] = f"TypeError: {exc}"

# N4: double attach (fresh host)
h4 = make_host()
attach_v2(h4)
before_routes = [(getattr(r, "path", None), sorted(getattr(r, "methods", None) or []))
                 for r in h4.routes]
before_doc = hashlib.sha256(json.dumps(h4.openapi(), sort_keys=True).encode()).hexdigest()
try:
    attach_v2(h4)
    OUT["n4_result"] = "NOT REFUSED"
except RuntimeError as exc:
    OUT["n4_result"] = f"RuntimeError: {exc}"
after_routes = [(getattr(r, "path", None), sorted(getattr(r, "methods", None) or []))
                for r in h4.routes]
after_doc = hashlib.sha256(json.dumps(h4.openapi(), sort_keys=True).encode()).hexdigest()
OUT["n4_routes_unchanged"] = before_routes == after_routes
OUT["n4_doc_unchanged"] = before_doc == after_doc

print(json.dumps(OUT, indent=1, ensure_ascii=True, default=str))
