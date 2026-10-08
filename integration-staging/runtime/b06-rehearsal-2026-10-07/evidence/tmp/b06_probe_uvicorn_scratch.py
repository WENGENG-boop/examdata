"""Scratch: verify uvicorn-in-thread recipe + content headers for the B06 cross-stack section."""
from __future__ import annotations

import hashlib
import json
import os
import socket
import sys
import threading
import time
import urllib.request
from pathlib import Path

CAND = Path(os.environ["B06_CANDIDATE_ROOT"]).resolve()
sys.dont_write_bytecode = True
sys.path.insert(0, str(CAND / "src"))

import uvicorn  # noqa: E402

from examdata.integration.api.app import create_app  # noqa: E402


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


port = free_port()
config = uvicorn.Config(create_app(), host="127.0.0.1", port=port,
                        log_level="warning", loop="asyncio")
server = uvicorn.Server(config)
thread = threading.Thread(target=server.run, name="b06-upstream", daemon=True)
thread.start()

deadline = time.time() + 30
while not server.started and time.time() < deadline:
    time.sleep(0.05)
print("upstream_started:", server.started, "port:", port)

base = f"http://127.0.0.1:{port}"


def get(path: str):
    with urllib.request.urlopen(base + path, timeout=30) as resp:
        return resp.status, dict(resp.headers), resp.read()


status, headers, body = get("/api/v2/info")
print("info:", status, json.loads(body)["schema_version"])

q = urllib.parse.quote("9999 2024 Jun")
status, headers, body = get(f"/api/v2/resources?system=cie&query={q}&limit=100")
doc = json.loads(body)
rows = doc["data"]["items"]
print("resources:", status, "n:", len(rows))
for row in rows:
    print(" row:", json.dumps({k: row.get(k) for k in
          ("public_id", "content_link", "content_available", "evidence")}, ensure_ascii=False))

link = rows[0]["content_link"]
status, headers, content = get(link)
print("content:", status, headers.get("content-type"), headers.get("content-length"),
      "x-content-sha256:", headers.get("x-content-sha256"), "etag:", headers.get("etag"))
print("sha256(bytes):", hashlib.sha256(content).hexdigest(), "len:", len(content))

status, headers, body = get("/health")
print("health:", status, body[:80])

server.should_exit = True
thread.join(timeout=10)
print("upstream_stopped:", not thread.is_alive())
