"""驱动：对每个 MOCK_MODE 跑一遍 smoke_public_api.py，汇总每项的真实判定。"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PY = str(ROOT / ".venv" / "Scripts" / "python.exe")
MOCK = str(Path(__file__).parent / "mock_api.py")
SMOKE = str(ROOT / "scripts" / "smoke_public_api.py")
PORT = "8131"

MODES = [
    ("good", []),
    ("search_empty", []),
    ("boards_missing_board", []),
    ("boards_missing_fields", []),
    ("download_html", []),
    ("download_nolen", []),
    ("download_empty", []),
    ("download_truncated", []),
    ("notfound_200", []),
    ("paper_502", []),
    ("server_500", []),
    ("slow_health", ["--timeout", "1"]),
    ("good", ["--api-key", "k"]),
]

env = dict(os.environ, PYTHONIOENCODING="utf-8")


def run(mode: str, extra: list[str]) -> None:
    mock_env = dict(env, MOCK_MODE=mode, MOCK_PORT=PORT)
    if extra[:1] == ["--api-key"]:
        mock_env["MOCK_API_KEY"] = "k"
    mock = subprocess.Popen([PY, MOCK], env=mock_env)
    time.sleep(0.8)
    try:
        proc = subprocess.run(
            [PY, SMOKE, "--base-url", f"http://127.0.0.1:{PORT}", "--json", *extra],
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
        )
        label = f"{mode} {' '.join(extra)}".strip()
        raw = proc.stdout.strip()
        try:
            report = json.loads(raw)
        except json.JSONDecodeError:
            print(f"### {label}  exit={proc.returncode}  非 JSON 输出！")
            print("    stdout 尾部:", raw[-300:].replace("\n", " | "))
            print("    stderr 尾部:", proc.stderr.strip()[-400:].replace("\n", " | "))
            return
        verdict = " ".join(f"{c['key']}={c['status']}" for c in report["checks"])
        print(f"### {label}  exit={proc.returncode}  ok={report['ok']}")
        print(f"    {verdict}")
        for c in report["checks"]:
            if c["status"] == "FAIL":
                print(f"    ! {c['key']}: {c['detail'][:150]}")
                if c["hint"]:
                    print(f"      hint: {c['hint'][:110]}")
    finally:
        mock.terminate()
        mock.wait(timeout=10)


if __name__ == "__main__":
    only = sys.argv[1] if len(sys.argv) > 1 else ""
    for mode, extra in MODES:
        if only and only not in mode:
            continue
        run(mode, extra)
