"""One launcher for the merged Python API, Web and classic frontend."""
from __future__ import annotations
import argparse
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
import time


def repository_root(explicit=None):
    root = Path(explicit or os.environ.get("EXAMDATA_WORKSPACE_ROOT") or Path.cwd()).resolve()
    if not (root / "pyproject.toml").is_file():
        raise ValueError("Run from the cloned repository or pass --root.")
    for rel in ("web/server.mjs", "frontend/server.mjs", "ielts-api/ielts-cli.mjs", "toefl-api/toefl-cli.mjs"):
        if not (root / rel).is_file():
            raise ValueError(f"Missing workspace component: {rel}")
    return root


def child_environment(root, api_port, web_port, classic_port, host):
    env = dict(os.environ)
    env.update(EXAMDATA_WORKSPACE_ROOT=str(root), EXAMDATA_INTEGRATION_ROOT=str(root),
               EXAMDATA_IELTS_DIR=str(root / "ielts-api"), EXAMDATA_TOEFL_DIR=str(root / "toefl-api"),
               EXAMDATA_TIMETABLE_DIR=str(root / "src/examdata/timetable/data"),
               EXAMDATA_URL=f"http://127.0.0.1:{api_port}", WEB_PORT=str(web_port), WEB_HOST=host,
               FRONTEND_PORT=str(classic_port), EXAMDATA_CLASSIC_URL=f"http://127.0.0.1:{classic_port}",
               PYTHONDONTWRITEBYTECODE="1")
    env.setdefault("EXAMDATA_DATA_DIR", str(root / ".data"))
    env.setdefault("EXAMDATA_DATABASE_URL", "sqlite:///" + str(Path(env["EXAMDATA_DATA_DIR"]) / "examdata.db").replace("\\", "/"))
    return env


def _check_port(port, host="127.0.0.1"):
    with socket.socket() as sock:
        sock.bind((host, port))


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run all merged services; Ctrl+C stops this launcher's children.")
    parser.add_argument("--root")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000, help="Web and API public port")
    parser.add_argument("--api-port", type=int, default=8001, help="Private Python API port")
    parser.add_argument("--classic-port", type=int, default=8002, help="Private classic frontend port")
    parser.add_argument("--check", action="store_true", help="Validate paths and runtime without starting services")
    parser.add_argument("--shutdown-file", help="Stop children cleanly when this optional control file appears")
    args = parser.parse_args(argv)
    children = []
    try:
        root = repository_root(args.root)
        node = shutil.which(os.environ.get("EXAMDATA_NODE", "node"))
        if not node:
            raise ValueError("Node.js >=20 is required.")
        major = int(subprocess.check_output([node, "--version"], text=True).strip().lstrip("v").split(".")[0])
        if major < 20:
            raise ValueError("Node.js >=20 is required.")
        ports = (args.port, args.api_port, args.classic_port)
        if len(set(ports)) != 3 or any(not 1 <= port <= 65535 for port in ports):
            raise ValueError("Choose three different ports between 1 and 65535.")
        env = child_environment(root, args.api_port, args.port, args.classic_port, args.host)
        if args.check:
            import json
            print(json.dumps({"ok": True, "root": str(root), "node_major": major, "ports": ports}))
            return 0
        for port, host in ((args.port, args.host), (args.api_port, "127.0.0.1"), (args.classic_port, "127.0.0.1")):
            _check_port(port, host)
        commands = [
            [sys.executable, "-m", "examdata.cli", "serve", "--host", "127.0.0.1", "--port", str(args.api_port)],
            [node, str(root / "frontend/server.mjs")],
            [node, str(root / "web/server.mjs")],
        ]
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        for command in commands:
            children.append(subprocess.Popen(command, cwd=root, env=env, creationflags=flags))
        print(f"Examdata: http://{args.host}:{args.port} | API: /api/v1 | classic: /classic/", flush=True)
        def stop(_signum, _frame):
            raise KeyboardInterrupt
        signal.signal(signal.SIGTERM, stop)
        while True:
            if args.shutdown_file and Path(args.shutdown_file).exists():
                return 0
            for child in children:
                if child.poll() is not None:
                    print(f"A workspace component exited (code {child.returncode}); stopping siblings.", file=sys.stderr)
                    return child.returncode or 1
            time.sleep(0.2)
    except KeyboardInterrupt:
        return 0
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    finally:
        for child in children:
            if child.poll() is None:
                child.terminate()
        for child in children:
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()


if __name__ == "__main__":
    raise SystemExit(main())
