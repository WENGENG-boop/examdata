"""后台隐藏窗口启动目录扫描，记录 PID / 启动参数 / 日志路径 / checkpoint 路径。

启动前确认没有其他扫描或下载进程，避免重复请求上游。
"""
from __future__ import annotations

import io
import json
import subprocess
import sys

import batchlib as B

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

MARKERS = ("scan_catalogue", "process_paper", "download")
CREATE_NO_WINDOW = 0x08000000
DETACHED_PROCESS = 0x00000008


def other_workers() -> list[dict]:
    script = (
        "Get-CimInstance Win32_Process -Filter \"Name like '%python%'\" | "
        "Select-Object ProcessId,CommandLine | ConvertTo-Json -Compress"
    )
    try:
        out = subprocess.run(["powershell", "-NoProfile", "-Command", script],
                             capture_output=True, text=True, timeout=60)
    except Exception as exc:
        return [{"check_failed": str(exc)}]
    text = (out.stdout or "").strip()
    if not text:
        return []
    try:
        rows = json.loads(text)
    except ValueError:
        return []
    if isinstance(rows, dict):
        rows = [rows]
    me = str(sys.argv[0])
    found = []
    for row in rows:
        cmd = row.get("CommandLine") or ""
        if any(m in cmd for m in MARKERS) and "launch_scan" not in cmd:
            found.append({"pid": row.get("ProcessId"), "command": cmd[:300]})
    return found


def main() -> int:
    B.ensure_dirs()
    running = other_workers()
    if running:
        print("检测到可能重复请求上游的进程，已放弃启动：")
        for row in running:
            print(" ", row)
        return 1

    log_dir = B.WORK / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    stamp = B.now_iso().replace(":", "")
    out_path = log_dir / f"scan-{stamp}.out.log"
    err_path = log_dir / f"scan-{stamp}.err.log"

    argv = [sys.executable, str(B.TOOLS / "scan_catalogue.py"), *sys.argv[1:]]
    out_fh = open(out_path, "ab")
    err_fh = open(err_path, "ab")
    proc = subprocess.Popen(
        argv, cwd=str(B.TOOLS), stdout=out_fh, stderr=err_fh, stdin=subprocess.DEVNULL,
        creationflags=CREATE_NO_WINDOW | DETACHED_PROCESS, close_fds=True)
    out_fh.close()
    err_fh.close()

    record = {
        "pid": proc.pid,
        "argv": argv,
        "cwd": str(B.TOOLS),
        "stdout_log": str(out_path),
        "stderr_log": str(err_path),
        "checkpoint_path": str(B.CHECKPOINT),
        "grid_path": str(B.GRID),
        "papers_path": str(B.PAPERS),
        "launched_at": B.now_iso(),
        "python": sys.executable,
        "hidden_window": True,
    }
    B.atomic_write_json(B.WORK / "scan-launch.json", record)
    B.set_checkpoint(stage="scan_launched", scanner_pid=proc.pid,
                     scanner_stdout=str(out_path), scanner_stderr=str(err_path),
                     last_progress_at=B.now_iso())
    print(json.dumps(record, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
