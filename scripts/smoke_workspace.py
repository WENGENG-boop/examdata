"""Offline real-process smoke test of the merged launcher, using private ports/data."""
from __future__ import annotations

import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def main():
    root = Path(__file__).resolve().parents[1]
    sockets = []
    for _ in range(3):
        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        sockets.append(sock)
    ports = [sock.getsockname()[1] for sock in sockets]
    for sock in sockets:
        sock.close()
    with tempfile.TemporaryDirectory(prefix="examdata-merge-smoke-") as private:
        private = Path(private)
        env = dict(os.environ)
        env.update(EXAMDATA_DATA_DIR=str(private / "data"),
                   EXAMDATA_DATABASE_URL="sqlite:///" + str(private / "data/examdata.db").replace("\\", "/"),
                   EXAMDATA_API_KEY="workspace-smoke-synthetic-token",
                   EXAMDATA_V2_FACTORY="")
        with (private / "service.log").open("w", encoding="utf-8") as log:
            process = subprocess.Popen([
                sys.executable, "-B", "-m", "examdata.workspace", "--root", str(root),
                "--port", str(ports[0]), "--api-port", str(ports[1]), "--classic-port", str(ports[2]),
                "--shutdown-file", str(private / "shutdown")
            ], cwd=root, env=env, stdout=log, stderr=log)
            results = []
            base = f"http://127.0.0.1:{ports[0]}"

            def fetch(path, *, authenticated=True, method="GET"):
                request = Request(base + path, method=method,
                                  headers={"X-API-Key": env["EXAMDATA_API_KEY"]} if authenticated else {})
                try:
                    with urlopen(request, timeout=20) as response:
                        return response.status, response.read()
                except HTTPError as response:
                    return response.code, response.read()

            try:
                deadline = time.monotonic() + 35
                while True:
                    if process.poll() is not None:
                        raise AssertionError("Launcher exited before readiness")
                    try:
                        if fetch("/health")[0] == 200:
                            break
                    except (URLError, OSError):
                        pass
                    if time.monotonic() > deadline:
                        raise AssertionError("Workspace readiness timed out")
                    time.sleep(0.2)
                checks = [
                    ("/", 200, False), ("/app.js", 200, False),
                    ("/classic/", 200, False), ("/classic/app.js", 200, False),
                    ("/classic/search.mjs", 200, False), ("/classic/catalog.json", 200, False),
                    ("/classic/styles.css", 200, False), ("/docs", 200, False),
                    ("/openapi.json", 200, False), ("/health", 200, False),
                    ("/api/v1/boards", 401, False), ("/api/v1/boards", 200, True),
                    ("/api/v1/ielts/info", 200, True), ("/api/v1/toefl/info", 200, True),
                    ("/api/v2/courses", 503, True),
                ]
                for path, expected, authenticated in checks:
                    status, data = fetch(path, authenticated=authenticated)
                    assert status == expected, (path, status, data[:300])
                    results.append({"path": path, "status": status, "authenticated": authenticated})
                    if path == "/openapi.json":
                        routes = json.loads(data)["paths"]
                        for prefix in ("/api/v1/ielts/", "/api/v1/toefl/", "/api/v1/materials", "/api/v1/timetable"):
                            assert any(route.startswith(prefix) for route in routes), prefix
                status, data = fetch("/health", method="HEAD")
                assert not data
                results.append({"path": "/health", "method": "HEAD", "status": status})
            except Exception:
                log.flush()
                print((private / "service.log").read_text(encoding="utf-8", errors="replace"), file=sys.stderr)
                raise
            finally:
                (private / "shutdown").touch()
                process.wait(timeout=20)
            # The supervisor must clean up its two private component ports as well.
            for port in ports:
                with socket.socket() as sock:
                    assert sock.connect_ex(("127.0.0.1", port)) != 0, f"Orphan service on port {port}"
            print(json.dumps({"ok": True, "checks": results, "child_ports_cleaned": True}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
