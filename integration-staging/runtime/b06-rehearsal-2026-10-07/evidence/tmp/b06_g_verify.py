"""Ad-hoc verification of the B06 candidate's resources discovery surface.

Private scratch (evidence/tmp). Imports the candidate at the target layout with
the explicit EXAMDATA_INTEGRATION_ROOT only; writes nothing outside stdout.
"""
import json
import os
import sys
from pathlib import Path

candidate = Path(os.environ["EXAMDATA_INTEGRATION_ROOT"]).resolve()
sys.path.insert(0, str(candidate / "src"))
sys.dont_write_bytecode = True

from starlette.testclient import TestClient  # noqa: E402
from examdata.integration.api.app import create_app  # noqa: E402

OUT = {}

CIE_MS = "asset_nz3uic3wquirttazjeo4fnsi3g7esn3k"
CIE_QP = "asset_umsge7vuubq3ncsz3zfe7b3golwybrmn"
EDX_MS = "asset_6xyrzhw4g5dy56xaxmhzk52da6zem5vu"
EDX_QP = "asset_jkw4xdasfrjtknr6ewnvus2rflr2r56n"
IELTS = "asset_bpdesyagunzooa3vdff53jvkk4pzilbt"
CIE_GRAPH = "asset_4fgmj24f44aqv3dnnwfrae3g4s5nmfdb"

QUERIES = [
    ("9999 2024 Jun", None),
    ("9999 2024 June", None),
    ("9999 2024 Jun", "cie"),
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

with TestClient(create_app(), raise_server_exceptions=False) as client:
    rows = client.get("/api/v2/resources").json()
    items = rows["data"]["items"]
    OUT["empty_rows"] = [
        {"public_id": it["public_id"], "system": it["system"],
         "media_type": it["media_type"], "byte_size": it["byte_size"],
         "content_available": it["content_available"],
         "has_discovery_key": "discovery" in it, "discovery": it.get("discovery")}
        for it in items
    ]
    OUT["empty_count"] = len(items)

    sys_filters = {}
    for system in ("cie", "edexcel", "ielts"):
        body = client.get("/api/v2/resources", params={"system": system}).json()
        sys_filters[system] = sorted(it["public_id"] for it in body["data"]["items"])
    OUT["system_filters"] = sys_filters

    bogus = client.get("/api/v2/resources", params={"bogus": "1"})
    bb = bogus.json()
    OUT["bogus_filter"] = {"status": bogus.status_code,
                           "code": (bb.get("error") or {}).get("code"),
                           "schema_version": bb.get("schema_version"),
                           "allowed": ((bb.get("error") or {}).get("details") or {}).get("allowed")}

    matrix = {}
    for query, system in QUERIES:
        params = {"query": query}
        if system is not None:
            params["system"] = system
        body = client.get("/api/v2/resources", params=params).json()
        matrix[f"{query}|{system or ''}"] = sorted(it["public_id"] for it in body["data"]["items"])
    OUT["matrix"] = matrix

    details = {}
    for name, ident in (("umsge", CIE_QP), ("ielts", IELTS), ("graph", CIE_GRAPH),
                        ("edx_ms", EDX_MS), ("edx_qp", EDX_QP), ("cie_ms", CIE_MS)):
        r = client.get(f"/api/v2/resources/{ident}")
        body = r.json()
        item = (body or {}).get("data", {}).get("item") if isinstance(body, dict) else None
        details[name] = {"status": r.status_code,
                         "has_discovery_key": isinstance(item, dict) and "discovery" in item,
                         "discovery": (item or {}).get("discovery") if isinstance(item, dict) else None}
    OUT["details"] = details

print(json.dumps(OUT, ensure_ascii=False, indent=1))
