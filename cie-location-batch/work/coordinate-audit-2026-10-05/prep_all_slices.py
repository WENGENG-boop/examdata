"""为队列中"原件已回本地"的卷预生成页对图 / 工作清单 / 子代理提示词（纯离线）。

逐卷检查：索引 documents 的每个 sha256 是否都能在 tmp/ 找到原件；全在则：
  render_regions.py <key> 2      -> visual/<paperdir>/{裁剪,整页,manifest}
  make_review_slices.py <key>    -> pairs/<paperdir>/*.png + review/worklist-<slug>-*.json
  mk_prompt.py <slice>...        -> review/prompts/prompt-<slice>.txt
写 deliverables/prep-log.json。串行，单卷失败记录后继续下一卷。
用法: python prep_all_slices.py [--only k1,k2] [--limit N]
"""
from __future__ import annotations

import argparse
import glob
import hashlib
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
SCALE = "2"


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def run(args: list[str]) -> tuple[int, str]:
    proc = subprocess.run([PY] + args, cwd=AUD, capture_output=True, text=True,
                          encoding="utf-8", errors="replace",
                          env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    return proc.returncode, ((proc.stdout or "") + (proc.stderr or ""))[-1200:]


def originals_status(key: str) -> tuple[bool, str]:
    subject, year, season, paper = key.split("/")
    idx = os.path.join(BATCH, "indexes", subject, f"{year}-{season}-{paper}",
                       "cie-index.json")
    if not os.path.isfile(idx):
        return False, "no index"
    index = json.load(open(idx, encoding="utf-8"))
    tmpdir = os.path.join(BATCH, "tmp", subject, f"{year}-{season}-{paper}")
    have = {sha256_file(p) for p in glob.glob(os.path.join(tmpdir, "*.pdf"))}
    missing = [d["role"] for d in index["documents"] if d["sha256"] not in have]
    return (not missing), ("ok" if not missing else "missing:" + ",".join(missing))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--scale", default=SCALE)
    args = ap.parse_args()

    queue = json.load(open(os.path.join(DELIV, "reverify-queue.json"),
                           encoding="utf-8"))["queue"]
    todo = [r["key"] for r in queue if r["outstanding"]]
    if args.only:
        want = {x.strip() for x in args.only.split(",") if x.strip()}
        todo = [k for k in todo if k in want]
    if args.limit:
        todo = todo[: args.limit]

    log = {"started_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "scale": args.scale,
           "planned": todo, "entries": []}
    out_path = os.path.join(DELIV, "prep-log.json")
    print("计划预生成 %d 卷" % len(todo), flush=True)
    for i, key in enumerate(todo, 1):
        ready, why = originals_status(key)
        entry = {"key": key, "originals": why}
        if not ready:
            entry["skipped"] = "originals_not_local"
            log["entries"].append(entry)
            print("[%d/%d] %s SKIP (%s)" % (i, len(todo), key, why), flush=True)
            continue
        t0 = time.time()
        rc1, o1 = run(["render_regions.py", key, args.scale])
        entry["render_exit"] = rc1
        entry["render_out"] = o1
        if rc1 == 0:
            rc2, o2 = run(["make_review_slices.py", key, "--cap", "80"])
            entry["slices_exit"] = rc2
            entry["slices_out"] = o2
            slug = key.replace("/", "_")
            sl = sorted(glob.glob(os.path.join(AUD, "review", f"worklist-{slug}-*.json")))
            ids = [os.path.basename(p)[len("worklist-"):-len(".json")] for p in sl]
            entry["slices"] = ids
            if ids:
                rc3, o3 = run(["mk_prompt.py"] + ids)
                entry["prompt_exit"] = rc3
                entry["prompt_out"] = o3
        entry["seconds"] = round(time.time() - t0, 1)
        log["entries"].append(entry)
        print("[%d/%d] %s render=%s slices=%s %.1fs" %
              (i, len(todo), key, entry.get("render_exit"), entry.get("slices_exit"),
               entry["seconds"]), flush=True)
        with open(out_path, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(log, fh, ensure_ascii=False, indent=1)
    log["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    with open(out_path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(log, fh, ensure_ascii=False, indent=1)
    prepped = sum(1 for e in log["entries"] if "slices" in e and e["slices"])
    print("预生成完成 %d/%d" % (prepped, len(todo)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
