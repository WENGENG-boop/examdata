"""Scratch exploration: what does the B06 candidate serve from /api/v2/resources?

Private scratch only; writes nothing. Runs against the private candidate.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

CAND = Path(os.environ["B06_CANDIDATE_ROOT"]).resolve()
sys.dont_write_bytecode = True
sys.path.insert(0, str(CAND / "src"))

from starlette.testclient import TestClient  # noqa: E402

from examdata.integration.api.app import create_app  # noqa: E402

app = create_app()

QUERIES = [
    (None, None),
    ("9999 2024 Jun", None),
    ("9999 2024 June", None),
    ("9999 2024 June", "cie"),
    ("9999 2024 Nov", None),
    ("9999 2024 Mar", None),
    ("9999 2024 mar", None),
    ("wma11 2024 June", None),
    ("wma11 2024 October", None),
    ("wma11 2024 January", None),
    ("wma11 2024", None),
    ("2024", None),
    ("Jun", None),
    ("9999 2024 Jun", "edexcel"),
    ("qp", None),
    ("ms", None),
    ("q", None),
]

with TestClient(app, raise_server_exceptions=False) as client:
    print("==== assets: all rows ====")
    resp = client.get("/api/v2/resources", params={"limit": "100"})
    body = resp.json()
    print("status", resp.status_code)
    for item in body["data"]["items"]:
        print(json.dumps({
            "public_id": item["public_id"],
            "system": item["system"],
            "media_type": item["media_type"],
            "byte_size": item["byte_size"],
            "discovery": item["discovery"],
            "content_available": item["content_available"],
        }, ensure_ascii=False, sort_keys=True))
    print("meta", json.dumps(body.get("meta", {}), ensure_ascii=False)[:400])

    print()
    print("==== per-query counts ====")
    for q, system in QUERIES:
        params = {}
        if q:
            params["query"] = q
        if system:
            params["system"] = system
        r = client.get("/api/v2/resources", params=params)
        b = r.json()
        rows = b.get("data", {}).get("items", [])
        ids = [row["public_id"] for row in rows]
        print(f"query={q!r} system={system!r} -> {r.status_code} n={len(ids)} {ids}")

    print()
    print("==== single resource detail ====")
    first_id = body["data"]["items"][0]["public_id"]
    detail = client.get(f"/api/v2/resources/{first_id}").json()
    print(json.dumps(detail, ensure_ascii=False, indent=1)[:1600])
