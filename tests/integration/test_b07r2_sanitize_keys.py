"""B07R2 STEP 2 (F4) — public sanitisation must cover mapping keys, not only values.

Required semantics (so the frozen tree fails RED here): every mapping key of
a public projection is passed through the same redaction as its values,
collisions after redaction are resolved deterministically without dropping or
overwriting records, fixed schema keys and record counts survive unchanged,
and the real candidate projection and HTTP handler emit no synthetic secret or
absolute path anywhere in the serialized output, keys included.
"""
from __future__ import annotations

import json
from pathlib import Path

import b07r2_common as c  # import first: pins EXAMDATA_INTEGRATION_ROOT + asserts candidate origin
from examdata.integration.api.app import create_app
from examdata.integration.api.dataset import default_dataset, operations_view
from examdata.integration.api.links import spec_for
from examdata.integration.operations.jobs import sanitize_tree
from fastapi.testclient import TestClient

import examdata.integration.api.app as app_module
import examdata.integration.api.dataset as dataset_module

c.assert_origin(app_module, "api.app")
c.assert_origin(dataset_module, "api.dataset")

SECRET = "S3CR3T-TOKEN-B07R2-7741"
ABS_WIN = "C:/Users/weo/Desktop/api/secret-area"


def _synthetic_operations_root(tmp_path: Path) -> Path:
    root = tmp_path / "ops"
    c.write_json(root / "cie" / "checkpoint.json", c.cie_checkpoint_document(
        stop_reason=f"halted at {SECRET}",
        stop_detail={f"log {SECRET}": f"see {ABS_WIN}/run.log", ABS_WIN: "directory"},
        needs_user_resume=True, resume_policy="manual",
        totals={f"count-{SECRET}": 1, "done": 1}))
    c.write_json(root / "expected-manifest.json", {
        "schema": "operations-expected/1",
        "scopes": [{"id": "cie-questions", "system": "cie", "kind": "question",
                    "expected": 1}]})
    return root


def _blob(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def test_f4_review_reproduction_secret_and_path_keys_are_redacted():
    """The review's exact F4 reproduction: secret-bearing key + absolute path
    key, plus collision behaviour. v1 leaves both keys unchanged."""
    value = {f"token {SECRET}": 1, f"token  {SECRET}": 2,          # collapse to same key
             ABS_WIN: {"note": f"leak {SECRET} at {ABS_WIN}"},
             f"{ABS_WIN}/run.log": [f"{ABS_WIN}/x", 7],
             "counters": {"done": 1}}
    out = sanitize_tree(value, secrets=(SECRET,))
    blob = json.dumps(out, ensure_ascii=False, sort_keys=True)
    assert SECRET not in blob, f"secret survived in {blob!r}"
    assert ABS_WIN not in blob and "C:/" not in blob and "/Users/weo" not in blob, blob
    assert len(out) == len(value), f"entries were dropped: {out!r}"
    assert out.get("counters") == {"done": 1}
    assert {out.get("token <secret>"), out.get("token <secret>#2")} == {1, 2}
    assert "<path>" in out and "<path>#2" in out
    assert out["<path>"] == {"note": "leak <secret> at <path>"}
    assert out["<path>#2"] == ["<path>", 7]


def test_f4_nested_lists_keep_record_counts():
    records = [{"public_id": f"job:cie:{SECRET}-{i}"} for i in range(3)]
    out = sanitize_tree({"rows": records, "tuple": ("a", f"{SECRET}")},
                        secrets=(SECRET,))
    assert len(out["rows"]) == 3
    assert len(out["tuple"]) == 2
    assert SECRET not in json.dumps(out)
    assert [row["public_id"] for row in out["rows"]] == [
        f"job:cie:<secret>-{i}" for i in range(3)]


def test_f4_collision_suffix_never_overwrites_an_existing_key():
    """A redacted key that collides with an already-emitted literal key must
    take the next free suffix instead of overwriting the record."""
    value = {"a": 1, "a#2": 2, "a ": 3}
    out = sanitize_tree(value)
    assert len(out) == 3, f"entries were dropped: {out!r}"
    assert out["a"] == 1
    assert out["a#2"] == 2
    assert out["a#3"] == 3


def test_f4_fixed_schema_keys_and_counts_survive():
    payload = {"public_id": "job:cie:cie-batch:synth", "stage": "running",
               "counters": {"done": 2, "total": 3},
               "evidence_refs": ["cie-scope:checkpoint.json"],
               "problems": [], "resume_required": False, "stop_reason": None}
    out = sanitize_tree(payload)
    assert set(out) == set(payload)
    assert out == payload


def test_f4_operations_projection_redacts_keys(tmp_path):
    root = _synthetic_operations_root(tmp_path)
    entry = c.make_entry("q:cie:synthetic-1", quality=c.QUALITY_VERIFIED)
    view = operations_view(entries=[entry], root=root,
                           dataset_revision="rev-b07r2-synthetic")
    assert view is not None
    public = view.to_public(secrets=(SECRET,))
    blob = _blob(public)
    assert SECRET not in blob, "secret survived in the public operations projection"
    assert ABS_WIN not in blob and "C:/" not in blob
    assert set(public) == {"read_only", "root", "checkpoints", "jobs", "published"}
    assert public["root"]["scanned_files"] == 1
    assert public["root"]["truncated"] is False
    assert public["published"] is not None
    assert len(public["published"]["rows"]) == 1
    assert public["published"]["rows"][0]["verified"] == 1
    assert len(public["jobs"]) == 1


def test_f4_http_routes_redact_keys(tmp_path, monkeypatch):
    monkeypatch.setenv("EXAMDATA_API_KEY", SECRET)
    root = _synthetic_operations_root(tmp_path)
    dataset = default_dataset(operations_root=root)
    client = TestClient(create_app(dataset=dataset))
    response = client.get(spec_for("coverage.get").full_path)
    assert response.status_code == 200, response.text
    operations = response.json()["data"]["operations"]
    assert set(operations) == {"read_only", "root", "checkpoints", "jobs", "published"}
    assert operations["root"]["scanned_files"] == 1
    assert len(operations["jobs"]) >= 1
    assert SECRET not in response.text, "secret survived in the /coverage HTTP response"
    assert ABS_WIN not in response.text and "C:/" not in response.text
    job_id = operations["jobs"][0]["public_id"]
    job_response = client.get(spec_for("jobs.get").full_path.replace("{id}", job_id))
    assert job_response.status_code == 200, job_response.text
    item = job_response.json()["data"]["item"]
    assert item["public_id"] == job_id
    expected_keys = {"public_id", "scope", "stage", "counters", "stop", "resume",
                     "sources", "evidence_refs", "resume_required", "stop_reason",
                     "freshness", "system", "scope_id", "scope_kind", "source",
                     "observed_at", "native_updated_at", "payload_sha256",
                     "problems", "input_revision", "output_refs"}
    assert not (expected_keys - set(item)), (
        f"job projection lost fields: {sorted(expected_keys - set(item))}")
    assert SECRET not in job_response.text, "secret survived in the /jobs/{id} HTTP response"
    assert ABS_WIN not in job_response.text and "C:/" not in job_response.text
