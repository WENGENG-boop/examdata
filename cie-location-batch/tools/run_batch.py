"""串行跑一批已下载的卷：index -> verify -> import -> cleanup，逐卷落盘结果。

用法: run_batch.py <key> [<key> ...]
结果追加到 BATCH_ROOT/work/batch_results.jsonl。
"""
from __future__ import annotations

import io
import json
import os
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parent))

import batchlib as B  # noqa: E402

PY = sys.executable
OUT = B.WORK / "batch_results.jsonl"


def run_one(key: str, start: str) -> dict:
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    proc = subprocess.run(
        [PY, str(B.TOOLS / "process_paper.py"), key, "--stage", start, "--json"],
        cwd=str(B.TOOLS), capture_output=True, text=True, encoding="utf-8",
        errors="replace", env=env)
    payload: dict = {"key": key, "returncode": proc.returncode}
    try:
        payload["result"] = json.loads(proc.stdout)
    except json.JSONDecodeError:
        payload["stdout_tail"] = (proc.stdout or "")[-1500:]
        payload["stderr_tail"] = (proc.stderr or "")[-1500:]
    payload["at"] = B.now_iso()
    return payload


def main() -> int:
    start = os.environ.get("BATCH_START_STAGE", "index")
    keys = sys.argv[1:]
    for key in keys:
        payload = run_one(key, start)
        with OUT.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, ensure_ascii=False) + "\n")
        result = payload.get("result") or {}
        stage = result.get("stage")
        print(f"[{B.now_iso()}] {key} rc={payload['returncode']} stage={stage}", flush=True)
        for row in result.get("stages") or []:
            print(f"    {'OK ' if row['exit'] == 0 else '!! '}{row['stage']:8s} "
                  f"{str(row['detail'])[:220]}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
