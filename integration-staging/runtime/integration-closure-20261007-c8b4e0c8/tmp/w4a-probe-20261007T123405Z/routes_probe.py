"""Probe: composed-host behaviour + operation-id determinism (W4a, read-only)."""
import hashlib
import sys
from collections import Counter
from pathlib import Path

CAND = Path(sys.argv[1])
sys.path.insert(0, str(CAND / "src"))
import os
os.environ["EXAMDATA_INTEGRATION_ROOT"] = str(CAND)

from fastapi import FastAPI
from fastapi.testclient import TestClient

from examdata.integration.api.app import create_app
from examdata.integration.api.compose import attach_v2
from examdata.integration.api.dataset import default_dataset
from examdata.integration.api.envelope import SCHEMA_VERSION

reg = CAND / "src/examdata/integration/legacy/registry.json"
print("registry sha256:", hashlib.sha256(reg.read_bytes()).hexdigest())


def ops_of(app):
    out = []
    for path, operations in app.openapi()["paths"].items():
        for method, op in operations.items():
            out.append((method, path, op.get("operationId")))
    return out


ds = default_dataset(operations_root=None)
app = create_app(dataset=ds)
ids = ops_of(app)
print("ops by method:", Counter(m for m, _, _ in ids))
print("total ops:", len(ids), "unique ids:", len(set(i for _, _, i in ids)))
print("missing ids:", [x for x in ids if not x[2]])

app2 = create_app(dataset=default_dataset(operations_root=None))
ids2 = ops_of(app2)
print("ids equal across builds:", ids == ids2)

host = FastAPI(title="w4a synthetic host")


@host.get("/health")
def health():
    return {"ok": True, "host": "legacy"}


@host.get("/boom")
def boom():
    raise RuntimeError("host boom")


attach_v2(host)
host_ids = [(m, p, i) for (m, p, i) in ops_of(host) if p.startswith("/api/v2")]
print("host v2 ops equal staged:", host_ids == ids)

with TestClient(host, raise_server_exceptions=False) as client:
    r = client.get("/health")
    print("health:", r.status_code, r.json())
    r = client.get("/api/v2/courses")
    print("v2 courses:", r.status_code, sorted(r.json().keys()),
          r.json()["meta"]["completeness"], r.json()["error"])
    r = client.get("/api/v2/nope")
    print("v2 nope:", r.status_code, r.json()["error"]["code"])
    r = client.get("/api/v2/containers/events")
    print("containers/events:", r.status_code, r.json()["error"]["code"])
    r = client.get("/api/v2/timetables/events")
    print("timetables/events:", r.status_code, type(r.json()["data"]).__name__)
    r = client.get("/nope")
    print("host nope:", r.status_code, r.text[:60], r.headers.get("content-type"))
    r = client.get("/boom")
    print("host boom:", r.status_code, repr(r.text[:60]),
          r.headers.get("content-type"))

print("SCHEMA_VERSION:", SCHEMA_VERSION)

try:
    attach_v2(object())
except TypeError:
    print("non-FastAPI refusal: TypeError ok")
try:
    attach_v2(host)
except RuntimeError:
    print("second attach refusal: RuntimeError ok")
host2 = FastAPI()
with TestClient(host2) as c2:
    c2.get("/")
try:
    attach_v2(host2)
except RuntimeError:
    print("late attach refusal: RuntimeError ok")
