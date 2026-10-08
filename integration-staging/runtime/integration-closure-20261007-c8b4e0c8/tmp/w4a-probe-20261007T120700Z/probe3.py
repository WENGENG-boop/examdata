"""W4a probe 3: shapes the compat tests assert on."""
import json

from fastapi.testclient import TestClient

from examdata.integration.api.app import create_app, default_content_store
from examdata.integration.api.dataset import default_dataset

ds = default_dataset(operations_root=None)
client = TestClient(create_app(dataset=ds))
store = default_content_store()


def data(path):
    r = client.get(path)
    assert r.status_code == 200, (path, r.status_code, r.text[:300])
    return r.json()


conts = data("/api/v2/containers")["data"]["items"]
print("containers:", [c["public_id"] for c in conts])
cid = conts[0]["public_id"]
res = data(f"/api/v2/containers/{cid}/resources")["data"]["items"]
print("resources for first container:", len(res))
print("resource item keys:", sorted(res[0].keys()) if res else None)

tt = data("/api/v2/timetables")
print("timetables data keys:", sorted(tt["data"].keys()))
season = (tt["data"].get("seasons") or [None])[0]
print("season row:", json.dumps(season)[:250] if season else None)
print("timetables completeness:", tt["meta"]["completeness"])

cov = data("/api/v2/coverage")
print("coverage completeness:", cov["meta"]["completeness"],
      "items:", len(cov["data"]["items"]))

gaps = data("/api/v2/gaps")
print("gaps completeness:", gaps["meta"]["completeness"],
      "items:", len(gaps["data"]["items"]))
print("gap item keys:", sorted(gaps["data"]["items"][0].keys()) if gaps["data"]["items"] else None)

assets = data("/api/v2/assets/asset_4fgmj24f44aqv3dnnwfrae3g4s5nmfdb")
print("asset item keys:", sorted(assets["data"]["item"].keys()))

# CIE question native 1(b): no crop
found = None
for entry in ds.entries("question"):
    native = str(entry.identity_fields.get("native_id")
                 or entry.native_locator.get("native_id"))
    if str(entry.system) == "cie" and native == "1(b)":
        found = entry
print("cie 1(b) entry:", found.public_id if found else None,
      "crop:", store.crop_for("cie", "1(b)"))

q = data(f"/api/v2/questions/{found.public_id}")["data"]["item"]
print("1(b) links:", sorted(q["links"].keys()))

# what does /info advertise look like (first row)
info = data("/api/v2/info")
print("info available[0]:", info["data"]["capabilities"]["available"][0])

# structure of /api/v2/questions list item
qs = data("/api/v2/questions")["data"]["items"]
print("question list count:", len(qs))
systems = sorted({q["system"] for q in qs})
print("question systems:", systems)
