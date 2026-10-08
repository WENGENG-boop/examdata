"""W4a probe: resolve remaining open questions before writing test_w4_api_compat.py.

Read-only against the candidate. Prints structured findings only.
"""
import dataclasses
import json

from fastapi.testclient import TestClient

from examdata.integration.api import openapi as openapi_mod
from examdata.integration.api.app import create_app, default_content_store
from examdata.integration.api.dataset import Dataset, default_dataset
from examdata.integration.contracts.enums import ExamSystem
from examdata.integration.providers.capabilities import Availability, Capability
from examdata.integration.providers.fixtures import FailingProvider, NullProvider
from examdata.integration.providers.protocol import ProviderDescriptor
from examdata.integration.providers.registry import ProviderRegistry

print("=== Dataset fields ===")
print([f.name for f in dataclasses.fields(Dataset)])

ds = default_dataset(operations_root=None)
app = create_app(dataset=ds)
client = TestClient(app)
store = default_content_store()


def jget(path):
    r = client.get(path)
    body = r.json() if r.headers.get("content-type", "").startswith("application/json") else None
    return r, body


print("=== courses ===")
r, j = jget("/api/v2/courses")
print(r.status_code, "items:", len(j["data"]["items"]))
print("first:", j["data"]["items"][0]["public_id"])
print("meta keys:", sorted(j["meta"].keys()))

print("=== assets: entries vs content store ===")
for e in ds.entries("asset"):
    sha = e.identity_fields.get("sha256")
    sample = store.for_asset(e.system, sha) if sha else None
    print(e.public_id, e.system, (sha or "")[:12], "in_store:", sample is not None)

print("=== question crop availability ===")
for e in ds.entries("question"):
    native = e.identity_fields.get("native_id") or e.native_locator.get("native_id")
    sample = store.crop_for(e.system, str(native))
    if sample is not None:
        print("crop:", e.public_id, native, "size:", sample.byte_size,
              "sha:", sample.sha256[:12], "media:", sample.media_type)

print("=== validate_response sweep ===")
routes = [
    "/api/v2/info", "/api/v2/exam-systems", "/api/v2/providers", "/api/v2/courses",
    "/api/v2/syllabuses", "/api/v2/containers", "/api/v2/resources", "/api/v2/questions",
    "/api/v2/tags", "/api/v2/materials", "/api/v2/timetables",
    "/api/v2/timetables/events", "/api/v2/timetables/windows", "/api/v2/coverage",
    "/api/v2/gaps", "/api/v2/jobs/job_synthetic_coverage",
]
for path in routes:
    r, j = jget(path)
    problems = openapi_mod.validate_response(j) if j is not None else ["no-json"]
    if problems:
        print("PROBLEM", path, r.status_code, problems)

# detail routes resolved from lists
course_id = jget("/api/v2/courses")[1]["data"]["items"][0]["public_id"]
syl = jget("/api/v2/syllabuses")[1]["data"]["items"]
syl_id = syl[0]["public_id"]
mat = jget("/api/v2/materials")[1]["data"]["items"]
mat_id = mat[0]["public_id"]
conts = jget("/api/v2/containers")[1]["data"]["items"]
cont_id = conts[0]["public_id"]
res = jget(f"/api/v2/containers/{cont_id}/resources")[1]["data"]["items"]
res_id = res[0]["public_id"]
qs = jget("/api/v2/questions")[1]["data"]["items"]
q_id = qs[0]["public_id"]
detail = [
    f"/api/v2/courses/{course_id}", f"/api/v2/syllabuses/{syl_id}",
    f"/api/v2/containers/{cont_id}", f"/api/v2/containers/{cont_id}/resources",
    f"/api/v2/containers/{cont_id}/questions", f"/api/v2/resources/{res_id}",
    f"/api/v2/questions/{q_id}", f"/api/v2/questions/{q_id}/answers",
    f"/api/v2/questions/{q_id}/regions", f"/api/v2/questions/{q_id}/audio",
    f"/api/v2/materials/{mat_id}", f"/api/v2/assets/{ds.entries('asset')[0].public_id}",
]
for path in detail:
    r, j = jget(path)
    problems = openapi_mod.validate_response(j) if j is not None else ["no-json"]
    if problems:
        print("PROBLEM", path, r.status_code, problems)
print("validate_response sweep done (only problems printed)")

print("=== tags routes behaviour ===")
r, j = jget("/api/v2/tags")
print("tags list:", r.status_code, "items:", len(j["data"]["items"]))
r, j = jget("/api/v2/tags/does-not-exist/questions")
print("unknown tag:", r.status_code, j["error"] and j["error"].get("code"))

print("=== syllabuses / materials ids ===")
print("syllabuses:", [row["public_id"] for row in syl])
print("materials:", [row["public_id"] for row in mat])

print("=== partial coverage (one success + one failure) ===")


def coverage_fail(pid):
    p = FailingProvider(pid)
    p.descriptor = ProviderDescriptor(
        provider_id=pid, exam_system=ExamSystem.CIE, display_name="w4a failing",
        capabilities=frozenset({Capability.COVERAGE}), supported_filters={},
        availability=Availability.AVAILABLE, limitations=())
    return p


def make_ds(providers):
    reg = ProviderRegistry()
    for p in providers:
        reg.register(p)
    base = default_dataset(operations_root=None)
    kwargs = {f.name: getattr(base, f.name) for f in dataclasses.fields(Dataset) if f.init}
    kwargs["registry"] = reg
    return Dataset(**kwargs)


mix = make_ds([coverage_fail("w4a_fail"), NullProvider(
    "w4a_empty_ok", capabilities=frozenset({Capability.COVERAGE}))])
client_mix = TestClient(create_app(dataset=mix))
r = client_mix.get("/api/v2/coverage")
j = r.json()
print("partial:", r.status_code, j["meta"]["completeness"])
print("warnings:", j["meta"]["warnings"])
print("meta keys:", sorted(j["meta"].keys()))
print("providers:", [(p["provider_id"], p["status"]) for p in j["meta"]["providers"]])
print("validate:", openapi_mod.validate_response(j))

print("=== total coverage failure (all providers fail) ===")
fail = make_ds([coverage_fail("w4a_fail_a"), coverage_fail("w4a_fail_b")])
client_fail = TestClient(create_app(dataset=fail))
r = client_fail.get("/api/v2/coverage")
j = r.json()
print("all-fail:", r.status_code, j["error"]["code"], "retryable:", j["error"]["retryable"])
print("message:", j["error"]["message"])
print("details providers:", [(p["provider_id"], p["status"]) for p in j["error"]["details"]["providers"]])
print("data:", j["data"])
print("validate:", openapi_mod.validate_response(j))

print("=== answers route with failing first provider for system ===")
# provider_for_system returns the FIRST descriptor for the system; put the failing one first.
mix2 = make_ds([coverage_fail("w4a_fail_cie_first"), NullProvider(
    "w4a_empty_ok2", capabilities=frozenset({Capability.COVERAGE}))])
r = TestClient(create_app(dataset=mix2)).get(f"/api/v2/questions/{q_id}/answers")
print("answers with failing system provider:", r.status_code, r.json()["error"] and r.json()["error"]["code"])

print("=== jobs route on production-style dataset ===")
base = default_dataset(operations_root=None)
print("job markers:", jget("/api/v2/jobs/job_synthetic_coverage")[1]["data"]["items"][0].get("evidence"))

print("=== done ===")
