"""Scratch: capture the exact /api/v2/resources expectations for the B06 G section.

Private scratch; writes nothing. Runs against the private candidate.
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
    ("9999 2024 Jun", None),
    ("9999 2024 June", None),
    ("9999 2024 June", "cie"),
    ("9999 2024 Nov", None),
    ("9999 2024 Mar", None),
    ("9999 2024 mar", None),
    ("9999 2024 March", None),
    ("wma11 2024 June", None),
    ("wma11 2024 October", None),
    ("wma11 2024 January", None),
    ("wma11 2024 November", None),
    ("wma11 2024", None),
    ("wma11 2024 01", None),
    ("2024", None),
    ("Jun", None),
    ("9999 2024 Jun", "edexcel"),
    ("9999 2024 01", None),
    ("9999 202", None),
    ("qp", None),
    ("ms", None),
    ("q", None),
]

with TestClient(app, raise_server_exceptions=False) as client:
    print("==== all rows (limit=100) ====")
    resp = client.get("/api/v2/resources", params={"limit": "100"})
    body = resp.json()
    print("status", resp.status_code)
    items = body["data"]["items"]
    for item in items:
        print(json.dumps({
            "public_id": item["public_id"],
            "system": item["system"],
            "media_type": item["media_type"],
            "byte_size": item["byte_size"],
            "content_available": item["content_available"],
            "content_link": item["content_link"],
            "discovery": item["discovery"],
            "evidence": item.get("evidence"),
        }, ensure_ascii=False, sort_keys=True))
    print("n_items", len(items))
    print("sorted_by_public_id", [i["public_id"] for i in items] == sorted(i["public_id"] for i in items))
    print("all_have_discovery_key", all("discovery" in i for i in items))
    print("meta", json.dumps(body.get("meta", {}), ensure_ascii=False)[:300])

    print()
    print("==== empty params ====")
    r = client.get("/api/v2/resources")
    b = r.json()
    print("no-params ->", r.status_code, len(b["data"]["items"]),
          [i["public_id"] for i in b["data"]["items"]])

    print()
    print("==== system-only filter ====")
    for sysname in ("cie", "edexcel", "ielts"):
        r = client.get("/api/v2/resources", params={"system": sysname, "limit": "100"})
        b = r.json()
        print(f"system={sysname} ->", r.status_code, len(b.get("data", {}).get("items", [])),
              [i["public_id"] for i in b.get("data", {}).get("items", [])])

    print()
    print("==== unknown filter ====")
    r = client.get("/api/v2/resources", params={"bogus": "1"})
    print("bogus=1 ->", r.status_code, json.dumps(r.json(), ensure_ascii=False)[:400])

    print()
    print("==== per-query counts ====")
    for q, system in QUERIES:
        params = {"limit": "100"}
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
    print("==== detail routes ====")
    for pid in ("asset_umsge7vuubq3ncsz3zfe7b3golwybrmn",
                "asset_bpdesyagunzooa3vdff53jvkk4pzilbt",
                "asset_4fgmj24f44aqv3dnnwfrae3g4s5nmfdb"):
        d = client.get(f"/api/v2/resources/{pid}")
        db = d.json()
        item = db.get("data", {}).get("item", {})
        print(pid, d.status_code, "discovery:", json.dumps(item.get("discovery"), ensure_ascii=False),
              "has_key:", "discovery" in item)
