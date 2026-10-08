import sys, os
sys.path.insert(0, r"C:/Users/weo/Desktop/api/integration-staging/src")
from examdata_integration.testing import guards
guards.install_module_guard()
guards.install_network_guard()

from fastapi import FastAPI
from fastapi.testclient import TestClient
import fastapi, starlette, httpx
app = FastAPI(title="probe")
@app.get("/ping")
def ping():
    return {"ok": True}
c = TestClient(app)
r = c.get("/ping")
print("status", r.status_code, r.json())
print("openapi paths", sorted(app.openapi()["paths"]))
print("runtime paths", sorted({getattr(rt, "path", None) for rt in app.routes if getattr(rt, "path", None)}))
print("versions", fastapi.__version__, starlette.__version__, httpx.__version__)
