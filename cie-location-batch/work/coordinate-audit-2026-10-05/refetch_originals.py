"""按重验队列顺序，逐卷重取原件（QP+MS）—— 串行、失败即停。

用法: python refetch_originals.py [--limit N] [--only key1,key2]
读 deliverables/reverify-queue.json，挑出原件不在本地且有待办的卷。
逐卷调用 tools/run_paper.py <key> --stage fetch（内部走 fetch_paper.py 的互斥与停止逻辑）。
任何非零退出即停止整个批次，并写 deliverables/refetch-log.json。
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

BATCH = r"C:/Users/weo/Desktop/api/cie-location-batch"
AUD = os.path.join(BATCH, "work", "coordinate-audit-2026-10-05")
DELIV = os.path.join(AUD, "deliverables")
PY = r"C:/Users/weo/Desktop/api/examdata/.venv/Scripts/python.exe"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--only", default="")
    args = ap.parse_args()

    q = json.load(open(os.path.join(DELIV, "reverify-queue.json"), encoding="utf-8"))["queue"]
    todo = [r for r in q if r["outstanding"] and not r["originals_present"]]
    if args.only:
        want = {x.strip() for x in args.only.split(",") if x.strip()}
        todo = [r for r in todo if r["key"] in want]
    if args.limit:
        todo = todo[: args.limit]

    log = {"started_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "entries": [],
           "planned": [r["key"] for r in todo], "stopped_early": False}
    out_path = os.path.join(DELIV, "refetch-log.json")
    print("计划重取 %d 卷" % len(todo), flush=True)
    for i, r in enumerate(todo, 1):
        key = r["key"]
        prior_stage = r["papers_stage"]
        t0 = time.time()
        proc = subprocess.run(
            [PY, os.path.join(BATCH, "tools", "run_paper.py"), key, "--stage", "fetch"],
            cwd=BATCH, capture_output=True, text=True, encoding="utf-8", errors="replace",
            env={**os.environ, "PYTHONIOENCODING": "utf-8"})
        entry = {"key": key, "prior_stage": prior_stage, "exit_code": proc.returncode,
                 "seconds": round(time.time() - t0, 1),
                 "stdout_tail": (proc.stdout or "")[-800:],
                 "stderr_tail": (proc.stderr or "")[-400:]}
        log["entries"].append(entry)
        print("[%d/%d] %s exit=%s %.1fs" % (i, len(todo), key, proc.returncode, entry["seconds"]),
              flush=True)
        if proc.returncode != 0:
            log["stopped_early"] = True
            log["stop_key"] = key
            break
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(log, fh, ensure_ascii=False, indent=1)
    log["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(log, fh, ensure_ascii=False, indent=1)
    ok = sum(1 for e in log["entries"] if e["exit_code"] == 0)
    print("完成 %d/%d，成功 %d，停止=%s" % (len(log["entries"]), len(todo), ok, log["stopped_early"]))
    return 0 if not log["stopped_early"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
