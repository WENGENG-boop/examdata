"""连续串行处理卷：pick -> claim -> process_paper -> 记录 -> 下一卷。

规则：
- 一次只挑一卷、一次只保留一组 QP/MS；pick 后立刻 claim，避免重复派发
- 上游 HTTP 错误（process_paper 退出码 1）立刻停止本轮新请求，落盘 checkpoint
- 本地失败（退出码 2/3）记录后跳到下一卷，不在同一卷上反复重试
- 每 N 卷或 M 秒刷新 summary.json
- 不并发：整个进程串行，fetch_paper 内部还会拿上游互斥体
"""
from __future__ import annotations

import argparse
import collections
import io
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import batchlib as B
import pick_queue as PQ
import pipelinestate as S

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PY = sys.executable
LOOP_LOG = B.WORK / "loop_results.jsonl"
LOOP_STATE = B.WORK / "loop_state.json"


def log(record: dict) -> None:
    B.append_jsonl(LOOP_LOG, record)


def say(msg: str) -> None:
    stamp = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    print(f"[{stamp}] {msg}", flush=True)


def pick_next(rows: list[dict], touched: set[str]) -> dict:
    """优先挑本轮到目前还没碰过的科目，保证科目轮转而不是耗尽单科目。"""
    fresh = [r for r in rows if r["subject"] not in touched]
    return (fresh or rows)[0]


def run_one(key: str) -> tuple[int, str]:
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    proc = subprocess.run(
        [PY, str(B.TOOLS / "process_paper.py"), key, "--json"],
        cwd=str(B.TOOLS), capture_output=True, text=True, encoding="utf-8",
        errors="replace", env=env)
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def refresh_summary() -> None:
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    try:
        subprocess.run([PY, str(B.TOOLS / "build_summary.py")], cwd=str(B.TOOLS),
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", env=env, timeout=600)
    except Exception as exc:  # noqa: BLE001
        say(f"summary 刷新失败: {exc}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=20, help="本轮处理卷数上限")
    parser.add_argument("--max-seconds", type=int, default=3600)
    parser.add_argument("--kinds", default="paired,qp_only")
    parser.add_argument("--min-year", type=int, default=B.YEAR_START)
    parser.add_argument("--max-year", type=int, default=B.YEAR_END)
    parser.add_argument("--exclude-subjects", default="")
    parser.add_argument("--summary-every", type=int, default=10)
    parser.add_argument("--summary-seconds", type=int, default=300)
    args = parser.parse_args()

    if (B.read_json(B.CHECKPOINT, {}) or {}).get("needs_user_resume"):
        say("现有断点要求明确允许联网续跑；未选卷、未改状态、未发送请求")
        return 1

    kinds = {k.strip() for k in args.kinds.split(",") if k.strip()}
    exclude = {s.strip() for s in args.exclude_subjects.split(",") if s.strip()}

    started = time.time()
    attempted: set[str] = set()
    touched: set[str] = set()
    done = 0
    blocked = False
    stage_hist: collections.Counter = collections.Counter()
    last_summary = time.time()

    B.set_checkpoint(loop_stage="loop_started", loop_started_at=B.now_iso(),
                     loop_limit=args.limit)

    while done < args.limit:
        if time.time() - started > args.max_seconds:
            say(f"到达时间上限 {args.max_seconds}s，正常收尾")
            break
        rows = PQ.interleave(PQ.candidates(kinds, args.min_year, args.max_year, exclude))
        rows = [r for r in rows if r["key"] not in attempted]
        if not rows:
            say("没有剩余可处理卷")
            break
        row = pick_next(rows, touched)
        touched.add(row["subject"])
        key = row["key"]
        attempted.add(key)
        S.update(key, stage="queued", queued_at=B.now_iso(),
                 queued_kind=row["kind"], queued_subject=row["subject"])
        B.set_checkpoint(current_paper=key, loop_stage="processing",
                         loop_done=done, loop_attempted=len(attempted))
        say(f"开始 {key}  kind={row['kind']}  原阶段={row['stage']}")

        t0 = time.time()
        rc, out = run_one(key)
        elapsed = round(time.time() - t0, 1)
        entry = (S.load(key) or {})
        stage = entry.get("stage") or "?"
        stage_hist[stage] += 1
        log({"key": key, "returncode": rc, "stage": stage, "seconds": elapsed,
             "at": B.now_iso(), "tail": out[-2000:]})
        say(f"完成 {key}  rc={rc}  stage={stage}  {elapsed}s")

        if rc == 1:
            blocked = True
            B.set_checkpoint(loop_stage="stopped_upstream_http_error", current_paper=key,
                             needs_user_resume=True,
                             stop_reason=f"process_paper 退出码 1（上游 HTTP 停止项）：{key}",
                             stopped_at=B.now_iso())
            B.append_jsonl(B.ERRORS, {"at": B.now_iso(), "key": key, "stage": "loop_stopped",
                                      "errors": ["上游 HTTP 错误，本轮停止新请求"],
                                      "detail": out[-1200:]})
            say("检测到上游 HTTP 停止项，停止本轮新请求")
            break

        done += 1
        if done % args.summary_every == 0 or (time.time() - last_summary) > args.summary_seconds:
            refresh_summary()
            last_summary = time.time()
        B.set_checkpoint(loop_done=done, loop_attempted=len(attempted),
                         loop_stages=dict(stage_hist))

    refresh_summary()
    B.set_checkpoint(loop_stage=("stopped_upstream_http_error" if blocked else "loop_idle"),
                     loop_done=done, loop_attempted=len(attempted),
                     loop_stages=dict(stage_hist), loop_finished_at=B.now_iso())
    B.atomic_write_json(LOOP_STATE, {"done": done, "attempted": sorted(attempted),
                                     "stages": dict(stage_hist), "blocked": blocked,
                                     "seconds": round(time.time() - started, 1),
                                     "at": B.now_iso()})
    say(f"本轮结束：处理 {done} 卷，尝试 {len(attempted)} 卷，阶段分布 {dict(stage_hist)}")
    return 0 if not blocked else 1


if __name__ == "__main__":
    raise SystemExit(main())
