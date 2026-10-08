"""串行准备一批试卷：逐卷下载原件并生成提案，产出可交给核验子 agent 的队列。

为什么要串行：上游（cie.fraft.cn 与本地 /api/v1/paper）同一时刻只允许一个联网工作线程。
下载与扫描也不能同时进行，所以本脚本在扫描未结束时拒绝运行。

停止规则：任何一卷下载出现 HTTP 403/404/409/502、超时或连接错误，立即落盘并停止，
不自动重试、不跳过换别的科目/年份。已下载成功的卷保留，由核验流程继续处理。

用法：
    python tools/prepare_batch.py --limit 6 [--min-year 2000] [--kinds paired,qp_only]
                                  [--allow-during-scan]
"""
from __future__ import annotations

import argparse
import io
import json
import subprocess
import sys
import time
from pathlib import Path

import batchlib as B

SEASON_ORDER = {"Mar": 0, "Jun": 1, "Nov": 2}
QUEUE_DIR = B.WORK / "queue"
READY = QUEUE_DIR / "ready.json"
HISTORY = QUEUE_DIR / "prepared.jsonl"
SCAN_LAUNCH = B.WORK / "scan-launch.json"


def _stdout_utf8() -> None:
    enc = (getattr(sys.stdout, "encoding", "") or "").replace("-", "").lower()
    if enc != "utf8":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def scan_running() -> tuple[bool, str]:
    """用 checkpoint 与 launch 记录判断扫描是否仍在跑。"""
    launch = B.read_json(SCAN_LAUNCH, {}) or {}
    pid = launch.get("pid")
    if pid:
        try:
            import subprocess as _sp
            out = _sp.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                          capture_output=True, text=True, timeout=20).stdout
            if str(pid) in out:
                return True, f"扫描进程 PID {pid} 仍在运行"
        except Exception:
            pass
    ck = B.read_json(B.CHECKPOINT, {}) or {}
    if ck.get("stage") == "scanning_full" and not ck.get("stop_reason"):
        age = time.time() - (B.CHECKPOINT.stat().st_mtime if B.CHECKPOINT.exists() else 0)
        if age < 1800:
            return True, f"checkpoint 仍在 scanning_full（{int(age)} 秒前更新）"
    return False, ""


def sort_key(entry: dict) -> tuple:
    """新到旧：科目升序、年份降序、Jun/Nov/Mar 优先。"""
    return (entry.get("subject", ""), -int(entry.get("year", 0)),
            -SEASON_ORDER.get(entry.get("season", ""), 9), entry.get("paper", ""))


def pick(limit: int, kinds: set[str], min_year: int) -> list[str]:
    papers = B.read_json(B.PAPERS, {}) or {}
    rows = []
    for key, entry in papers.items():
        if not isinstance(entry, dict):
            continue
        if entry.get("kind") not in kinds:
            continue
        if entry.get("stage") not in (None, "discovered"):
            continue
        if int(entry.get("year", 0)) < min_year:
            continue
        if not entry.get("qp"):
            continue
        rows.append(entry)
    rows.sort(key=sort_key)
    return [r["key"] for r in rows[:limit]]


def run_step(script: str, args: list[str]) -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, str(B.TOOLS / script), *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(B.TOOLS), env={**__import__("os").environ, "PYTHONIOENCODING": "utf-8"})
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def main() -> int:
    _stdout_utf8()
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=6)
    ap.add_argument("--min-year", type=int, default=B.YEAR_START)
    ap.add_argument("--kinds", default="paired,qp_only")
    ap.add_argument("--allow-during-scan", action="store_true")
    args = ap.parse_args()

    busy, why = scan_running()
    if busy and not args.allow_during_scan:
        print(f"[拒绝] 目录扫描仍在进行：{why}")
        print("扫描与下载不能同时并发访问上游。等扫描结束后重跑，或显式加 --allow-during-scan。")
        return 1

    kinds = {k.strip() for k in args.kinds.split(",") if k.strip()}
    keys = pick(args.limit, kinds, args.min_year)
    if not keys:
        print("没有可准备的卷（都已完成或没有匹配的 kind）")
        return 0

    QUEUE_DIR.mkdir(parents=True, exist_ok=True)
    prepared: list[dict] = []
    print(f"准备 {len(keys)} 卷：")
    for key in keys:
        print(f"  -> {key}")
        code, out = run_step("fetch_paper.py", [key])
        tail = "\n".join(line for line in out.strip().splitlines()[-4:])
        print(f"     fetch 退出码 {code}\n{tail}")
        if code != 0:
            B.append_jsonl(B.ERRORS, {"at": B.now_iso(), "kind": "prepare_batch_stop",
                                      "key": key, "stage": "fetch",
                                      "exit_code": code, "output_tail": tail[-800:]})
            B.set_checkpoint(stage="stopped", stop_reason="download_error",
                             current_paper=key, last_progress_at=B.now_iso())
            print(f"[停止] {key} 下载失败，按规则停止本轮联网请求，不自动重试。")
            _write_ready(prepared)
            return 2

        code, out = run_step("run_paper.py", [key, "--stage", "propose"])
        tail = "\n".join(line for line in out.strip().splitlines()[-4:])
        print(f"     propose 退出码 {code}\n{tail}")
        record = {"key": key, "at": B.now_iso(), "propose_exit": code,
                  "output_tail": tail[-400:]}
        if code == 0:
            record["proposal"] = str(B.WORK / "proposals" /
                                     key.split("/")[0] /
                                     f"{key.split('/')[1]}-{key.split('/')[2]}-{key.split('/')[3]}.json")
            prepared.append(record)
        else:
            B.append_jsonl(B.ERRORS, {"at": B.now_iso(), "kind": "prepare_batch_propose",
                                      "key": key, "stage": "propose", "exit_code": code,
                                      "output_tail": tail[-800:]})
        B.append_jsonl(HISTORY, record)

    _write_ready(prepared)
    print(f"已准备 {len(prepared)}/{len(keys)} 卷，队列写入 {READY}")
    return 0


def _write_ready(prepared: list[dict]) -> None:
    B.atomic_write_json(READY, {"generated_at": B.now_iso(), "count": len(prepared),
                                "papers": prepared})
    B.set_checkpoint(prepare_ready_count=len(prepared),
                     last_prepare_at=B.now_iso())


if __name__ == "__main__":
    raise SystemExit(main())
