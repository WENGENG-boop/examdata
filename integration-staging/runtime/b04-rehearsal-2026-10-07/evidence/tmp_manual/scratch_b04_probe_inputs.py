"""Manual scratch 3: verify every input the planned b04_route_probe.py will hard-check.

Mirrors the planned probe code exactly:
* full inventory host (71 A12 dummies + 3 synthetic extras + 2 v2-prefix controls)
* baseline vs composed probe tuples (legacy byte-identity, v2 envelope controls)
* route-table delta + wrapper entry shape
* binary runtime through the composed full host
* N2 unscoped-handler install on the min host (parsed shapes)
* N3 mount, N5 late attach with context manager, N6 wrong type
* E: candidate/tools compose sha equality
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from pathlib import Path

CANDIDATE = Path(os.environ["B04_CANDIDATE_ROOT"]).resolve()
WORKSPACE = Path(os.environ["B04_WORKSPACE_ROOT"]).resolve()
sys.path.insert(0, str(CANDIDATE / "src"))
sys.dont_write_bytecode = True

from fastapi import FastAPI, Query  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

from examdata.integration.api import links  # noqa: E402
from examdata.integration.api.app import create_app  # noqa: E402
from examdata.integration.api.compose import attach_v2  # noqa: E402
from examdata.integration.api.dataset import SYLLABUS_FIXTURES  # noqa: E402
from examdata.integration.api.envelope import SCHEMA_VERSION  # noqa: E402

OUT: dict = {}
A12 = json.loads((WORKSPACE / "docs/integration/execution/A12_ROUTE_COMPATIBILITY_WORKSHEET.json")
                 .read_text(encoding="utf-8"))
ROWS = A12["rows"]


def concrete(path: str) -> str:
    return re.sub(r"\{([^}]+)\}", lambda m: "synthetic-" + re.sub(r"[^A-Za-z0-9_-]", "-", m.group(1)), path)


def sha(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=True)


by_path: dict[str, set] = {}
for row in ROWS:
    by_path.setdefault(row["legacy_path"], set()).add(row["method"].upper())

EXTRA_PATHS = ["/synthetic-legacy/numbers", "/synthetic-legacy/boom", "/synthetic-legacy/echo",
               "/api/v2/__synthetic_typed", "/api/v2/__synthetic_boom"]
OUT["extras_collide_with_inventory"] = sorted(set(EXTRA_PATHS) & set(by_path))
OUT["inventory_paths"] = len(by_path)
OUT["braced_paths"] = sum(1 for p in by_path if "{" in p)


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


def probe(client: TestClient, method: str, url: str, params=None) -> list:
    r = client.request(method, url, params=params)
    return [r.status_code, r.headers.get("content-type"), sha(r.content)]


def min_probe_all(client: TestClient) -> dict:
    return {
        "papers_200": probe(client, "GET", "/api/legacy/papers"),
        "numbers_default": probe(client, "GET", "/synthetic-legacy/numbers"),
        "numbers_422": probe(client, "GET", "/synthetic-legacy/numbers", {"limit": "abc"}),
        "boom_500": probe(client, "GET", "/synthetic-legacy/boom"),
        "absent_404": probe(client, "GET", "/api/legacy/absent"),
    }


INVENTORY_PROBES = [(f"inv:{row['method'].upper()} {row['legacy_path']}", row["method"].upper(),
                     concrete(row["legacy_path"])) for row in ROWS]
EXTRA_PROBES = [
    ("extra:numbers_default", "GET", "/synthetic-legacy/numbers"),
    ("extra:numbers_422", "GET", "/synthetic-legacy/numbers?limit=abc"),
    ("extra:boom_500", "GET", "/synthetic-legacy/boom"),
    ("extra:echo_405", "GET", "/synthetic-legacy/echo"),
    ("extra:echo_200", "POST", "/synthetic-legacy/echo"),
    ("extra:absent_404", "GET", "/api/legacy/absent"),
    ("extra:braced_post_405", "POST", concrete(next(r["legacy_path"] for r in ROWS if "{" in r["legacy_path"]))),
]
CONTROL_PROBES = [
    ("ctl:typed_422", "GET", "/api/v2/__synthetic_typed?q=abc"),
    ("ctl:v2_boom", "GET", "/api/v2/__synthetic_boom"),
    ("ctl:jobs_404", "GET", "/api/v2/jobs/does-not-exist"),
    ("ctl:unknown_404", "GET", "/api/v2/__synthetic_absent"),
    ("ctl:post_info_405", "POST", "/api/v2/info"),
    ("ctl:info_200", "GET", "/api/v2/info"),
]

# --- full-host probes -------------------------------------------------------
def full_probe_all(client: TestClient) -> dict:
    out = {}
    for name, method, url in INVENTORY_PROBES + EXTRA_PROBES + CONTROL_PROBES:
        if "?" in url:
            path, query = url.split("?", 1)
            key, value = query.split("=", 1)
            out[name] = probe(client, method, path, {key: value})
        else:
            out[name] = probe(client, method, url)
    return out


baseline = full_probe_all(TestClient(make_host(), raise_server_exceptions=False))

host2 = make_host()
OUT["host_routes_pre"] = len(host2.routes)
pre_doc = host2.openapi()
OUT["pre_doc_paths"] = len(pre_doc["paths"])
OUT["pre_middleware_none"] = host2.middleware_stack is None
before_tbl = [(getattr(r, "path", None), sorted(getattr(r, "methods", None) or []), type(r).__name__)
              for r in host2.routes]
attach_v2(host2)
after_tbl = [(getattr(r, "path", None), sorted(getattr(r, "methods", None) or []), type(r).__name__)
             for r in host2.routes]
OUT["host_routes_post"] = len(host2.routes)
OUT["route_table_delta"] = len(after_tbl) - len(before_tbl)
OUT["route_table_prefix_kept"] = after_tbl[:len(before_tbl)] == before_tbl
OUT["new_entry"] = after_tbl[len(before_tbl):]

with TestClient(host2, raise_server_exceptions=False) as client:
    composed = full_probe_all(client)
    served = client.get("/openapi.json")

post_doc = host2.openapi()
OUT["post_doc_paths"] = len(post_doc["paths"])
OUT["served_equals_direct"] = served.json() == post_doc
OUT["served_status"] = served.status_code

legacy_keys = [n for n, _, _ in INVENTORY_PROBES + EXTRA_PROBES]
OUT["legacy_identical"] = sorted(n for n in legacy_keys if baseline[n] != composed[n])
OUT["v2_differs"] = sorted(n for n, _, _ in CONTROL_PROBES if baseline[n] != composed[n])
OUT["v2_after"] = {n: composed[n] for n, _, _ in CONTROL_PROBES}
OUT["v2_baseline"] = {n: baseline[n] for n, _, _ in CONTROL_PROBES}
OUT["boom_pinned"] = composed["extra:boom_500"]
OUT["braced_post_405"] = composed["extra:braced_post_405"]

# parsed v2 control bodies
with TestClient(host2, raise_server_exceptions=False) as client:
    for name, method, url in CONTROL_PROBES:
        r = client.request(method, url.split("?")[0], params=({"q": "abc"} if "?" in url else None))
        try:
            body = r.json()
            OUT[f"parsed:{name}"] = {"schema_version": body.get("schema_version"),
                                     "code": (body.get("error") or {}).get("code"),
                                     "has_data": "data" in body}
        except Exception as exc:  # noqa: BLE001
            OUT[f"parsed:{name}"] = f"RAISED {type(exc).__name__}: {exc}"

# binary runtime through the composed full host
OUT["syllabus_fixture_ids"] = [r["public_id"] for r in SYLLABUS_FIXTURES]
sid = SYLLABUS_FIXTURES[0]["public_id"]
with TestClient(host2, raise_server_exceptions=False) as client:
    r200 = client.get(f"/api/v2/syllabuses/{sid}/content")
    r206 = client.get(f"/api/v2/syllabuses/{sid}/content", headers={"Range": "bytes=0-9"})
    r304 = client.get(f"/api/v2/syllabuses/{sid}/content", headers={"If-None-Match": r200.headers["etag"]})
    rh = client.head(f"/api/v2/syllabuses/{sid}/content")
    OUT["binary_200"] = [r200.status_code, r200.headers.get("content-type"), len(r200.content),
                         r200.headers.get("etag")]
    OUT["binary_206"] = [r206.status_code, r206.headers.get("content-range"), len(r206.content)]
    OUT["binary_304"] = [r304.status_code, len(r304.content)]
    OUT["binary_head"] = [rh.status_code, rh.headers.get("content-length")]

# --- N2 parsed shapes (min host, unscoped install before first request) -----
base_min = min_probe_all(TestClient(make_min_host(), raise_server_exceptions=False))

h2 = make_min_host()
v2 = create_app()
for exc_class, handler in v2.exception_handlers.items():
    h2.add_exception_handler(exc_class, handler)
with TestClient(h2, raise_server_exceptions=False) as c:
    after2 = min_probe_all(c)
    shapes = {}
    for key, method, url in [("boom_500", "GET", "/synthetic-legacy/boom"),
                             ("numbers_422", "GET", "/synthetic-legacy/numbers"),
                             ("absent_404", "GET", "/api/legacy/absent")]:
        r = c.get(url, params=({"limit": "abc"} if key == "numbers_422" else None))
        try:
            body = r.json()
            shapes[key] = {"schema_version": body.get("schema_version"),
                           "code": (body.get("error") or {}).get("code"),
                           "detail": body.get("detail")}
        except Exception:  # noqa: BLE001
            shapes[key] = r.text[:80]
    OUT["n2_shapes"] = shapes
OUT["n2_changed"] = sorted(k for k in base_min if base_min[k] != after2[k])
OUT["n2_after"] = after2
OUT["n2_baseline"] = base_min

# N2b: post-build mutation invisible (context manager style)
h2b = make_min_host()
with TestClient(h2b, raise_server_exceptions=False) as c:
    c.get("/api/legacy/papers")
assert h2b.middleware_stack is not None
installed_before = dict(h2b.exception_handlers)
for exc_class, handler in v2.exception_handlers.items():
    h2b.add_exception_handler(exc_class, handler)
with TestClient(h2b, raise_server_exceptions=False) as c:
    after2b = min_probe_all(c)
OUT["n2b_identical_to_baseline"] = after2b == base_min
OUT["n2b_installed_before_count"] = len(installed_before)
OUT["n2b_handler_keys_now"] = len(h2b.exception_handlers)

# N3 mount
h3 = make_min_host()
h3.mount("/api/v2", create_app())
with TestClient(h3, raise_server_exceptions=False) as c:
    r = c.get("/api/v2/info")
    OUT["n3_info"] = [r.status_code, r.headers.get("content-type")]
    try:
        OUT["n3_info_code"] = r.json().get("error", {}).get("code")
    except Exception as exc:  # noqa: BLE001
        OUT["n3_info_code"] = f"RAISED {type(exc).__name__}"
    OUT["n3_doubled"] = c.get("/api/v2/api/v2/info").status_code
OUT["n3_doc_v2_paths"] = sorted(p for p in h3.openapi()["paths"] if p.startswith("/api/v2"))

# N5 late attach (context manager)
h5 = make_min_host()
with TestClient(h5, raise_server_exceptions=False) as c:
    c.get("/api/legacy/papers")
OUT["n5_middleware_built"] = h5.middleware_stack is not None
try:
    attach_v2(h5)
    OUT["n5"] = "NOT REFUSED"
except RuntimeError as exc:
    OUT["n5"] = f"RuntimeError: {exc}"
OUT["n5_no_v2_paths"] = not any(p.startswith("/api/v2") for p in h5.openapi()["paths"])

# N6
for value in (None, "x"):
    try:
        attach_v2(value)
        OUT[f"n6_{value!r}"] = "NOT REFUSED"
    except TypeError as exc:
        OUT[f"n6_{value!r}"] = f"TypeError: {exc}"

# E: compose shas
cand_compose = CANDIDATE / "src/examdata/integration/api/compose.py"
tools_compose = Path(os.environ["B04_TMP_DIR"]).resolve().parent.parent / "tools" / "compose.py"
OUT["compose_candidate_sha"] = sha(cand_compose.read_bytes())
OUT["compose_tools_sha"] = sha(tools_compose.read_bytes())
OUT["compose_equal"] = OUT["compose_candidate_sha"] == OUT["compose_tools_sha"]

print(json.dumps(OUT, indent=1, ensure_ascii=True, default=str))
