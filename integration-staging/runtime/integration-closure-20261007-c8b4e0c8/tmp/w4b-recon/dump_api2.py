"""W4b recon supplement: crop without query params, the unprobed question, and
per-family full detail for the mirror. Read-only in-process probing."""
from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

RUN = Path(__file__).resolve().parents[2]
CANDIDATE = RUN / "candidates" / "closure-v1"
OUT = RUN / "tmp" / "w4b-recon"
sys.dont_write_bytecode = True
os.environ["EXAMDATA_INTEGRATION_ROOT"] = str(CANDIDATE)
os.environ.pop("EXAMDATA_OPERATIONS_ROOT", None)
sys.path.insert(0, str(CANDIDATE / "src"))

from fastapi.testclient import TestClient  # noqa: E402

from examdata.integration.api.app import create_app  # noqa: E402
from examdata.integration.api.dataset import default_dataset  # noqa: E402

records: list[dict] = []


def get(client: TestClient, path: str) -> dict:
    response = client.get(path)
    body = response.content
    ctype = response.headers.get("content-type", "")
    rec = {"path": path, "status": response.status_code, "bytes": len(body),
           "sha256": hashlib.sha256(body).hexdigest()}
    if "json" in ctype:
        rec["json"] = response.json()
    else:
        rec["headers"] = {k: response.headers[k] for k in
                          ("content-type", "content-length", "x-content-sha256",
                           "x-document-sha256", "x-page", "x-evidence") if k in response.headers}
    records.append(rec)
    return rec


def items_of(rec: dict) -> list:
    data = (rec.get("json") or {}).get("data") or {}
    return data.get("items") or [] if isinstance(data, dict) else []


def main() -> None:
    client = TestClient(create_app(dataset=default_dataset()))
    questions = get(client, "/api/v2/questions")
    qids = sorted({r["public_id"] for r in items_of(questions)})
    print("question ids:", qids, flush=True)
    for qid in qids:
        get(client, f"/api/v2/questions/{qid}/crop")
        get(client, f"/api/v2/questions/{qid}/audio")
    for qid in ("q_y4jdjciydgwnmnipurwlstb6ud26p4r5",):
        for suffix in ("", "/answers", "/regions", "/audio"):
            get(client, f"/api/v2/questions/{qid}{suffix}")
    # containers/questions cross-check and tags detail
    containers = get(client, "/api/v2/containers")
    for row in items_of(containers):
        cid = row["public_id"]
        for suffix in ("", "/resources", "/questions"):
            get(client, f"/api/v2/containers/{cid}{suffix}")
    tags = get(client, "/api/v2/tags")
    for row in items_of(tags):
        get(client, f"/api/v2/tags/{row['public_id']}/questions")
    (OUT / "api_dump2.json").write_text(json.dumps(
        {"candidate": str(CANDIDATE), "records": records}, indent=2, sort_keys=True),
        encoding="utf-8")
    print(f"wrote {len(records)} records", flush=True)


if __name__ == "__main__":
    main()
