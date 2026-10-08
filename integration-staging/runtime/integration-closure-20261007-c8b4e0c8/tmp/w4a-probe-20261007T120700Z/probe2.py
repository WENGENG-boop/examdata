"""W4a probe 2: answers-fail dispatch on a CIE question, jobs route shape, agreement problems."""
import dataclasses
import json

from fastapi.testclient import TestClient

from examdata.integration.api import openapi as openapi_mod
from examdata.integration.api.app import create_app
from examdata.integration.api.dataset import Dataset, default_dataset
from examdata.integration.contracts.enums import ExamSystem
from examdata.integration.providers.capabilities import Availability, Capability
from examdata.integration.providers.fixtures import FailingProvider, NullProvider
from examdata.integration.providers.protocol import ProviderDescriptor
from examdata.integration.providers.registry import ProviderRegistry

CIE_Q = "q_lkfcr6zycmxmr4bdx2edj437sxpxkylo"  # native "1", CIE, known from probe 1


def answers_fail(pid, system=ExamSystem.CIE):
    p = FailingProvider(pid)
    p.descriptor = ProviderDescriptor(
        provider_id=pid, exam_system=system, display_name="w4a failing",
        capabilities=frozenset({Capability.ANSWERS}), supported_filters={},
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


mix = make_ds([answers_fail("w4a_answers_fail"), NullProvider(
    "w4a_empty_ok", capabilities=frozenset({Capability.ANSWERS}))])
client = TestClient(create_app(dataset=mix))
r = client.get(f"/api/v2/questions/{CIE_Q}/answers")
j = r.json()
print("answers fail-first:", r.status_code, j["error"]["code"], j["error"]["message"])
print("details:", [(p["provider_id"], p["status"]) for p in j["error"]["details"]["providers"]])

# fixture-style success for comparison
ds = default_dataset(operations_root=None)
client2 = TestClient(create_app(dataset=ds))
r = client2.get(f"/api/v2/questions/{CIE_Q}/answers")
j = r.json()
print("answers ok:", r.status_code, j["meta"]["completeness"],
      "items:", len(j["data"]["items"]), "gaps:", len(j["data"]["gaps"]))

r = client2.get("/api/v2/jobs/job_synthetic_coverage")
j = r.json()
print("jobs data keys:", sorted(j["data"].keys()))
print("jobs data:", json.dumps(j["data"], ensure_ascii=False)[:400])

r = client2.get("/api/v2/tags/does-not-exist/questions")
print("tags unknown data:", r.json()["data"])

print("agreement_problems(create_app()):", openapi_mod.agreement_problems(create_app()))
print("agreement_problems(fixture ds app):", openapi_mod.agreement_problems(create_app(dataset=ds)))

# all three CIE question ids and their systems (sanity for later tests)
for e in ds.entries("question"):
    if e.public_id == CIE_Q:
        print("CIE_Q system:", e.system, "native:", e.native_locator.get("native_id"))
