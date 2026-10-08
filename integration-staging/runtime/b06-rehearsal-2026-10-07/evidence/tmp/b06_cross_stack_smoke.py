"""Scratch smoke for b06_cross_stack.mjs (private; writes nothing).

Starts a private uvicorn instance of the B06 candidate read API, starts the
candidate frontend server (127.0.0.1, ephemeral ports) and runs the
cross-stack script against both. Prints the script's stdout/exit code.

cwd-independent; run from the run directory:
  B06_CANDIDATE_ROOT=<cand> EXAMDATA_INTEGRATION_ROOT=<cand> \
  python evidence/tmp/b06_cross_stack_smoke.py
"""
from __future__ import annotations

import os
import re
import socket
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

CAND = Path(os.environ["B06_CANDIDATE_ROOT"]).resolve()
RUN_DIR = Path(__file__).resolve().parents[2]
CROSS = RUN_DIR / "tools" / "b06_cross_stack.mjs"

sys.dont_write_bytecode = True
sys.path.insert(0, str(CAND / "src"))

import uvicorn  # noqa: E402
from examdata.integration.api.app import create_app  # noqa: E402


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait_http(url: str, timeout: float = 30.0) -> int:
    deadline = time.time() + timeout
    last: object = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=5) as resp:
                return resp.status
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(0.1)
    raise SystemExit(f"server did not answer {url}: {last}")


up_port = free_port()
config = uvicorn.Config(create_app(), host="127.0.0.1", port=up_port,
                        log_level="warning", loop="asyncio")
server = uvicorn.Server(config)
up_thread = threading.Thread(target=server.run, name="b06-smoke-upstream", daemon=True)
up_thread.start()
deadline = time.time() + 30
while not server.started and time.time() < deadline:
    time.sleep(0.05)
print("upstream_started:", server.started, "port:", up_port, flush=True)
if not server.started:
    raise SystemExit(1)

fe_port = free_port()
env = dict(os.environ)
env["FRONTEND_PORT"] = str(fe_port)
env["EXAMDATA_URL"] = f"http://127.0.0.1:{up_port}"
env.pop("EXAMDATA_API_KEY", None)

fe = subprocess.Popen(
    ["node", str(CAND / "frontend" / "server.mjs")],
    cwd=str(RUN_DIR), env=env,
    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8")

out_lines: list[str] = []
err_lines: list[str] = []


def _pump(stream, sink: list[str]) -> None:
    for line in stream:
        sink.append(line.rstrip("\n"))


threading.Thread(target=_pump, args=(fe.stdout, out_lines), daemon=True).start()
threading.Thread(target=_pump, args=(fe.stderr, err_lines), daemon=True).start()

banner_port = None
deadline = time.time() + 15
while time.time() < deadline and banner_port is None:
    for line in out_lines:
        match = re.search(r"http://127\.0\.0\.1:(\d+)", line)
        if match:
            banner_port = int(match.group(1))
            break
    if fe.poll() is not None:
        break
    time.sleep(0.05)
print("frontend_started:", fe.poll() is None, "banner_port:", banner_port,
      "requested:", fe_port, "match:", banner_port == fe_port, flush=True)

fe_base = f"http://127.0.0.1:{fe_port}"
up_base = f"http://127.0.0.1:{up_port}"
print("frontend / status:", wait_http(fe_base + "/"), flush=True)

cross = subprocess.run(
    ["node", str(CROSS), str(CAND / "frontend"), fe_base, up_base],
    cwd=str(RUN_DIR), capture_output=True, text=True, encoding="utf-8", timeout=300)
print("cross_stack_exit:", cross.returncode)
print("---- cross stdout ----")
print(cross.stdout)
print("---- cross stderr ----")
print(cross.stderr)

fe.terminate()
try:
    fe.wait(timeout=10)
except subprocess.TimeoutExpired:
    fe.kill()
    fe.wait(timeout=10)
print("frontend_returncode:", fe.returncode)
print("frontend_stderr:", err_lines[-5:])

server.should_exit = True
up_thread.join(timeout=10)
print("upstream_stopped:", not up_thread.is_alive())

raise SystemExit(0 if cross.returncode == 0 else cross.returncode)
