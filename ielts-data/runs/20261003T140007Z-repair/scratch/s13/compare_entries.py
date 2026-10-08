#!/usr/bin/env python
"""S13 三入口一致性验收（计划验收行：CLI 子进程 / Node HTTP 独立随机端口 / FastAPI TestClient）。

对同一身份（1/1、3/2、10/1、19/1、20/4、21/1）比较 normalized 关键字段与 coverage：
- v2 test（ok / identity.variant / completion unit_ids + status）
- v2 questions（count / total / 题号；含 10/1 分页 offset=39&limit=3）
- reading 整卷（ok / passage / 题数 / 题号 / answer_count）
- reading 单篇 passage=2（同上）
非法参数批次证明 fetch=0：fetch-guard 逐次记录 + requests.jsonl 行数前后对比。
不改既有 8000 服务进程；Node HTTP 用独立随机端口。

运行（examdata venv）：
  cd examdata
  ./.venv/Scripts/python.exe ../ielts-data/runs/20261003T140007Z-repair/scratch/s13/compare_entries.py
退出码：0=全部一致且 fetch=0；1=有不一致或 fetch>0。
"""
from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

SCRATCH = Path(__file__).resolve().parent
REPO = SCRATCH.parents[4]
IELTS_API = REPO / "ielts-api"
CLI = IELTS_API / "ielts-cli.mjs"
RUN_DIR = REPO / "ielts-data" / "runs" / "20261003T140007Z-repair"
REQUESTS = RUN_DIR / "requests.jsonl"
GUARD = SCRATCH / "fetch-guard.cjs"
GUARD_LOG = SCRATCH / "fetch-guard.log"
REPORT = SCRATCH / "three-entry-report.json"

os.environ["NODE_OPTIONS"] = (
    (os.environ.get("NODE_OPTIONS", "") + " --require " + str(GUARD).replace("\\", "/")).strip()
)
os.environ["FETCH_GUARD_LOG"] = str(GUARD_LOG)

sys.path.insert(0, str(REPO / "examdata" / "src"))
from fastapi.testclient import TestClient  # noqa: E402
from examdata.api.app import app  # noqa: E402

NODE = shutil.which("node") or "node"

IDENTITIES = [(1, 1), (3, 2), (10, 1), (19, 1), (20, 4), (21, 1)]

results: list[dict] = []


def run_cli(*args: object, timeout: float = 240.0) -> dict:
    p = subprocess.run(
        [NODE, str(CLI), *[str(a) for a in args]],
        cwd=str(IELTS_API),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )
    try:
        j = json.loads(p.stdout.strip())
    except Exception:
        j = None
    return {"exit": p.returncode, "json": j, "stderr": (p.stderr or "")[-200:]}


def _json_or_none(body: str):
    try:
        return json.loads(body)
    except Exception:
        return None


def http_get(path: str, timeout: float = 240.0) -> dict:
    req = urllib.request.Request(BASE + path)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return {"status": r.status, "json": _json_or_none(r.read().decode("utf-8", "replace"))}
    except urllib.error.HTTPError as e:
        return {"status": e.code, "json": _json_or_none(e.read().decode("utf-8", "replace"))}


client = TestClient(app)


def fastapi_get(path: str) -> dict:
    r = client.get(path)
    try:
        j = r.json()
    except Exception:
        j = None
    return {"status": r.status_code, "json": j}


def norm_v2test(d: dict | None) -> dict | None:
    if not d:
        return None
    units = (d.get("completion") or {}).get("units") or []
    return {
        "ok": d.get("ok"),
        "variant": (d.get("identity") or {}).get("variant"),
        "unit_ids": [u.get("unit_id") for u in units],
        "unit_status": {u.get("unit_id"): u.get("status") for u in units},
    }


def norm_v2questions(d: dict | None) -> dict | None:
    if not d:
        return None
    return {
        "ok": d.get("ok"),
        "count": d.get("count"),
        "total": d.get("total"),
        "numbers": [q.get("number") for q in (d.get("questions") or [])],
    }


def norm_reading(d: dict | None) -> dict | None:
    if not d:
        return None
    qs = d.get("questions") or []
    return {
        "ok": d.get("ok"),
        "passage": d.get("passage"),
        "count": len(qs),
        "numbers": [q.get("number") for q in qs],
        "answer_count": d.get("answer_count"),
    }


def compare_case(kind: str, book: int, test: int, params: str, norm, cli_args, http_path, fastapi_path):
    cli = run_cli(*cli_args)
    h = http_get(http_path)
    f = fastapi_get(fastapi_path)
    nc, nh, nf = norm(cli.get("json")), norm(h.get("json")), norm(f.get("json"))
    diffs = []
    if not (nc == nh == nf):
        diffs.append({"cli": nc, "http": nh, "fastapi": nf})
    if cli.get("exit") != 0:
        diffs.append({"cli_exit": cli.get("exit"), "stderr": cli.get("stderr")})
    row = {
        "kind": kind, "book": book, "test": test, "params": params,
        "consistent": not diffs, "diffs": diffs,
        "entries": {"cli": nc, "http": nh, "fastapi": nf},
        "http_status": h.get("status"), "fastapi_status": f.get("status"),
    }
    results.append(row)
    mark = "OK " if row["consistent"] else "DIFF"
    print(f"  [{mark}] {kind} {book}/{test}{params} cli/http/fastapi")
    return row


def guard_count() -> int:
    if not GUARD_LOG.exists():
        return 0
    return sum(1 for ln in GUARD_LOG.read_text(encoding="utf-8").splitlines() if ln.strip())


def requests_count() -> int:
    if not REQUESTS.exists():
        return 0
    return sum(1 for ln in REQUESTS.read_text(encoding="utf-8").splitlines() if ln.strip())


def free_port() -> int:
    for _ in range(50):
        port = 19000 + int.from_bytes(os.urandom(2), "big") % 500
        with socket.socket() as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise RuntimeError("找不到可用端口")


print("== S13 三入口一致性 ==")
GUARD_LOG.unlink(missing_ok=True)
port = free_port()
BASE = f"http://127.0.0.1:{port}"
print(f"Node HTTP: {BASE}")
server = subprocess.Popen(
    [NODE, str(CLI), "serve", str(port)],
    cwd=str(IELTS_API),
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
    encoding="utf-8",
    errors="replace",
)
try:
    deadline = time.time() + 30
    started = False
    while time.time() < deadline:
        line = server.stdout.readline()
        if not line:
            if server.poll() is not None:
                raise RuntimeError("serve 提前退出")
            continue
        if "listening" in line:
            started = True
            break
    if not started:
        raise RuntimeError("serve 启动超时")

    for b, t in IDENTITIES:
        compare_case("v2test", b, t, "",
                     norm_v2test,
                     ("test-v2", b, t), f"/api/ielts/v2/test/{b}/{t}", f"/api/v1/ielts/v2/test/{b}/{t}")
        compare_case("v2questions-reading", b, t, "?skill=reading",
                     norm_v2questions,
                     ("questions-v2", b, t, "--skill=reading"),
                     f"/api/ielts/v2/questions/{b}/{t}?skill=reading",
                     f"/api/v1/ielts/v2/questions/{b}/{t}?skill=reading")
        compare_case("reading-whole", b, t, "",
                     norm_reading,
                     ("reading", b, t), f"/api/reading/{b}/{t}", f"/api/v1/ielts/reading/{b}/{t}")
        compare_case("reading-single-p2", b, t, "?passage=2",
                     norm_reading,
                     ("reading", b, t, "2"), f"/api/reading/{b}/{t}/2", f"/api/v1/ielts/reading/{b}/{t}?passage=2")

    compare_case("v2questions-paged", 10, 1, "?offset=39&limit=3",
                 norm_v2questions,
                 ("questions-v2", 10, 1, "--offset=39", "--limit=3"),
                 "/api/ielts/v2/questions/10/1?offset=39&limit=3",
                 "/api/v1/ielts/v2/questions/10/1?offset=39&limit=3")

    # ---- 非法参数批次：fetch=0 证明 ----
    print("== 非法参数 fetch=0 ==")
    g0, r0 = guard_count(), requests_count()
    invalid_cases = [
        ("cli", ("reading", 99, 1)),
        ("cli", ("reading", 1, 99)),
        ("cli", ("reading", 1, 1, 9)),
        ("cli", ("reading-enriched", 99, 1, 1)),
        ("cli", ("test-v2", 99, 1)),
        ("cli", ("questions-v2", 10, 1, "--limit=501")),
        ("cli", ("questions-v2", 10, 1, "--offset=-1")),
        ("http", "/api/reading/99/1"),
        ("http", "/api/reading/1/99"),
        ("http", "/api/reading-enriched/99/1"),
        ("http", "/api/ielts/v2/test/99/1"),
        ("http", "/api/ielts/v2/questions/10/1?limit=501"),
        ("fastapi", "/api/v1/ielts/reading/99/1"),
        ("fastapi", "/api/v1/ielts/reading-enriched/99/1"),
        ("fastapi", "/api/v1/ielts/v2/test/99/1"),
        ("fastapi", "/api/v1/ielts/v2/questions/10/1?limit=501"),
    ]
    invalid_rows = []
    for kind, arg in invalid_cases:
        if kind == "cli":
            out = run_cli(*arg)
            j = out.get("json") or {}
            invalid_rows.append({"entry": "cli", "args": list(arg), "exit": out.get("exit"),
                                 "ok": j.get("ok"), "code": j.get("code")})
        elif kind == "http":
            h = http_get(arg)
            j = h.get("json") or {}
            invalid_rows.append({"entry": "http", "path": arg, "status": h.get("status"),
                                 "ok": j.get("ok"), "code": j.get("code")})
        else:
            f = fastapi_get(arg)
            j = f.get("json") or {}
            invalid_rows.append({"entry": "fastapi", "path": arg, "status": f.get("status"),
                                 "ok": j.get("ok"), "code": j.get("code")})
    time.sleep(0.5)
    g1, r1 = guard_count(), requests_count()
    new_lines = []
    if g1 > g0 and GUARD_LOG.exists():
        lines = [ln for ln in GUARD_LOG.read_text(encoding="utf-8").splitlines() if ln.strip()]
        new_lines = lines[g0:]
    invalid = {
        "cases": invalid_rows,
        "guard_before": g0, "guard_after": g1, "guard_delta": g1 - g0,
        "requests_before": r0, "requests_after": r1, "requests_delta": r1 - r0,
        "new_guard_lines": new_lines,
    }
    print(f"  guard_delta={g1 - g0} requests_delta={r1 - r0}")

    # ---- 选源失败（live，至多 2 次小请求）：reader 源覆盖边界 ----
    print("== 选源失败（live，reader 源） ==")
    src_rows = []
    for args in (("reading-enriched", 19, 1, 1), ("reading-enriched", 20, 1, 1)):
        out = run_cli(*args)
        j = out.get("json") or {}
        src_rows.append({
            "args": list(args), "exit": out.get("exit"),
            "ok": j.get("ok"), "source": j.get("source"),
            "error": j.get("error"), "hint": j.get("hint"),
            "question_count": j.get("question_count"),
        })
        print(f"  {args}: ok={j.get('ok')} source={j.get('source')} error={j.get('error')}")
    source_failure = {"cases": src_rows}

finally:
    try:
        server.kill()
        server.wait(timeout=10)
    except Exception:
        pass

summary = {
    "cases": len(results),
    "consistent": sum(1 for r in results if r["consistent"]),
    "inconsistent": sum(1 for r in results if not r["consistent"]),
}
fetch_zero = invalid["guard_delta"] == 0 and invalid["requests_delta"] == 0
ok = summary["inconsistent"] == 0 and fetch_zero
report = {
    "schema": "ielts.s13.three-entry/1",
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "run_dir": str(RUN_DIR),
    "node_http_base": BASE,
    "identities": IDENTITIES,
    "cases": results,
    "summary": summary,
    "invalid_batch": invalid,
    "source_failure": source_failure,
    "fetch_zero": fetch_zero,
    "ok": ok,
}
REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"== 汇总: {summary['consistent']}/{summary['cases']} 一致; fetch_zero={fetch_zero} ==")
print(f"报告: {REPORT}")
sys.exit(0 if ok else 1)
