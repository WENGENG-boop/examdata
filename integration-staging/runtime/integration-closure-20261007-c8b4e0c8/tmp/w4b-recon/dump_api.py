"""W4b recon: dump the private v2 API's declared behavior for the browser mirror.

Read-only: builds the candidate app in-process (TestClient) and records every
route response the W4b fixture-server will mirror. Two configurations are
exercised: without and with EXAMDATA_OPERATIONS_ROOT (the candidate's own
synthetic operations fixture). Output: <run>/tmp/w4b-recon/api_dump/.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

RUN = Path(__file__).resolve().parents[2]
CANDIDATE = RUN / "candidates" / "closure-v1"
OPS_ROOT = CANDIDATE / "fixtures" / "synthetic" / "operations" / "operations-root"
OUT = RUN / "tmp" / "w4b-recon" / "api_dump"
OUT.mkdir(parents=True, exist_ok=True)

sys.dont_write_bytecode = True
os.environ["EXAMDATA_INTEGRATION_ROOT"] = str(CANDIDATE)
os.environ.pop("EXAMDATA_OPERATIONS_ROOT", None)
sys.path.insert(0, str(CANDIDATE / "src"))

from fastapi.testclient import TestClient  # noqa: E402

from examdata.integration.api.app import create_app  # noqa: E402
from examdata.integration.api.dataset import default_dataset  # noqa: E402

HEADER_KEYS = ("content-type", "content-length", "etag", "last-modified",
               "accept-ranges", "content-range", "x-content-sha256",
               "x-document-sha256", "x-page", "x-evidence")

records: list[dict] = []
binaries: dict[str, bytes] = {}


def slug(path: str) -> str:
    keep = [c if c.isalnum() else "_" for c in path]
    return "".join(keep)[:120]


def get(client: TestClient, path: str) -> dict:
    response = client.get(path)
    ctype = response.headers.get("content-type", "")
    body = response.content
    record = {"path": path, "status": response.status_code,
              "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}
    if "json" in ctype:
        try:
            record["json"] = response.json()
        except Exception as exc:  # noqa: BLE001
            record["json_error"] = str(exc)
    else:
        record["headers"] = {key: response.headers[key] for key in HEADER_KEYS
                             if key in response.headers}
        binaries[slug(path)] = body
    records.append(record)
    return record


def items_of(record: dict) -> list:
    data = (record.get("json") or {}).get("data") or {}
    if isinstance(data, dict):
        return data.get("items") or []
    return []


def ids_of(record: dict, key: str = "public_id") -> list[str]:
    out = []
    for row in items_of(record):
        value = row.get(key)
        if isinstance(value, str):
            out.append(value)
    return out


def probe(client: TestClient, label: str) -> None:
    print("== probe:", label, flush=True)
    base_lists = [
        "/api/v2/info", "/api/v2/exam-systems", "/api/v2/providers",
        "/api/v2/courses", "/api/v2/courses?system=cie", "/api/v2/courses?system=ielts",
        "/api/v2/courses?system=edexcel", "/api/v2/courses?system=toefl",
        "/api/v2/syllabuses", "/api/v2/syllabuses?system=cie",
        "/api/v2/syllabuses?system=ielts", "/api/v2/syllabuses?system=edexcel",
        "/api/v2/containers", "/api/v2/containers?system=cie",
        "/api/v2/containers?system=ielts", "/api/v2/containers?system=edexcel",
        "/api/v2/resources", "/api/v2/resources?system=cie",
        "/api/v2/resources?system=edexcel", "/api/v2/resources?system=ielts",
        "/api/v2/questions", "/api/v2/questions?system=ielts",
        "/api/v2/questions?system=cie", "/api/v2/questions?system=edexcel",
        "/api/v2/questions?system=toefl", "/api/v2/questions?book=synthetic-book-1",
        "/api/v2/tags", "/api/v2/materials", "/api/v2/materials?system=cie",
        "/api/v2/materials?system=edexcel", "/api/v2/materials?system=ielts",
        "/api/v2/timetables", "/api/v2/timetables?system=cie",
        "/api/v2/timetables/events", "/api/v2/timetables/events?system=cie",
        "/api/v2/timetables/windows", "/api/v2/timetables/windows?system=cie",
        "/api/v2/coverage", "/api/v2/coverage?system=cie", "/api/v2/gaps",
        "/api/v2/jobs/job_synthetic_coverage", "/api/v2/jobs/job:cie:cie-batch:8888",
        "/api/v2/jobs/job:ielts:synthetic-run-ok", "/api/v2/jobs/does-not-exist",
        "/api/v2/questions?system=ielts&book=SB1",
        "/api/v2/questions?system=ielts&book=synthetic/cambridge-1",
        "/api/v2/questions/does-not-exist", "/api/v2/questions/does-not-exist/answers",
        "/api/v2/resources?system=cie&subject=9999", "/api/v2/resources?bogus=1",
        "/api/v2/questions?bogus=1",
    ]
    list_records = {}
    for path in base_lists:
        list_records[path] = get(client, path)

    course_ids = ids_of(list_records["/api/v2/courses"])
    syllabus_ids = ids_of(list_records["/api/v2/syllabuses"])
    container_ids = ids_of(list_records["/api/v2/containers"])
    question_ids = ids_of(list_records["/api/v2/questions"])
    if not question_ids:
        for path, record in list_records.items():
            if path.startswith("/api/v2/questions?"):
                question_ids += ids_of(record)
    question_ids = sorted(set(question_ids))
    tag_ids = ids_of(list_records["/api/v2/tags"])
    material_ids = ids_of(list_records["/api/v2/materials"])
    resource_ids = ids_of(list_records["/api/v2/resources"])

    for cid in course_ids[:8]:
        get(client, f"/api/v2/courses/{cid}")
    for sid in syllabus_ids[:8]:
        get(client, f"/api/v2/syllabuses/{sid}")
        get(client, f"/api/v2/syllabuses/{sid}/content")
    for cid in container_ids[:8]:
        get(client, f"/api/v2/containers/{cid}")
        get(client, f"/api/v2/containers/{cid}/resources")
        get(client, f"/api/v2/containers/{cid}/questions")
    for qid in question_ids[:12]:
        get(client, f"/api/v2/questions/{qid}")
        get(client, f"/api/v2/questions/{qid}/answers")
        regions = get(client, f"/api/v2/questions/{qid}/regions")
        get(client, f"/api/v2/questions/{qid}/audio")
        region_rows = items_of(regions)
        for region in region_rows[:2]:
            rid = region.get("public_id") or region.get("region_id") or region.get("id")
            if isinstance(rid, str):
                get(client, f"/api/v2/questions/{qid}/crop?region={rid}")
                get(client, f"/api/v2/questions/{qid}/crop?region={rid}&page=1")
    for tid in tag_ids[:4]:
        get(client, f"/api/v2/tags/{tid}/questions")
    for mid in material_ids[:8]:
        get(client, f"/api/v2/materials/{mid}")
        get(client, f"/api/v2/materials/{mid}/content")
    for rid in resource_ids[:8]:
        get(client, f"/api/v2/resources/{rid}")
        get(client, f"/api/v2/assets/{rid}")
        get(client, f"/api/v2/resources/{rid}/content")
        get(client, f"/api/v2/assets/{rid}/content")


def main() -> None:
    os.environ.pop("EXAMDATA_OPERATIONS_ROOT", None)
    client = TestClient(create_app(dataset=default_dataset()))
    probe(client, "no-operations-root")
    no_ops = list(records)
    records.clear()

    os.environ["EXAMDATA_OPERATIONS_ROOT"] = str(OPS_ROOT)
    client_ops = TestClient(create_app(dataset=default_dataset()))
    probe(client_ops, "with-operations-root")
    with_ops = list(records)

    binary_dir = OUT / "binary"
    binary_dir.mkdir(exist_ok=True)
    for name, payload in binaries.items():
        (binary_dir / f"{name}.bin").write_bytes(payload)

    (OUT / "api_dump.json").write_text(json.dumps(
        {"candidate": str(CANDIDATE), "operations_root": str(OPS_ROOT),
         "no_operations_root": no_ops, "with_operations_root": with_ops},
        indent=2, sort_keys=True), encoding="utf-8")
    print(f"wrote {len(no_ops)} + {len(with_ops)} records to {OUT}", flush=True)
    print(f"binaries: {sorted(binaries)}", flush=True)


if __name__ == "__main__":
    main()
