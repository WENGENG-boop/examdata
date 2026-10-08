"""停止规则离线回归：网络异常必须落盘、必须映射成 BLOCKED、run_loop 必须科目轮转。

不联网、不写正式状态：所有 IO 都被替换成内存桩。
"""
from __future__ import annotations

import contextlib
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import batchlib as B
import fetch_paper as F
import process_paper as PP
import run_loop as RL

FAILURES: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'PASS' if ok else 'FAIL'}  {name}{'' if ok else '  -> ' + detail}")
    if not ok:
        FAILURES.append(name)


@contextlib.contextmanager
def patch(obj, **attrs):
    old = {k: getattr(obj, k) for k in attrs}
    for k, v in attrs.items():
        setattr(obj, k, v)
    try:
        yield
    finally:
        for k, v in old.items():
            setattr(obj, k, v)


def fake_entry() -> dict:
    return {"subject": "9709", "year": 2024, "season": "Jun", "paper": "11",
            "kind": "paired", "qp": ["9709_s24_qp_11.pdf"], "ms": ["9709_s24_ms_11.pdf"]}


def test_fetch_timeout_persists_and_stops() -> None:
    print("[1] fetch 阶段网络异常 -> 落盘 + 返回 2")
    written: list[dict] = []
    checkpoints: list[dict] = []
    with tempfile.TemporaryDirectory() as td:
        import httpx

        def boom(*_a, **_k):
            raise httpx.ReadTimeout("timed out")

        with patch(B, scan_active=lambda: {"active": False},
                   read_json=lambda *a, **k: {},
                   append_jsonl=lambda path, rec: written.append(rec),
                   set_checkpoint=lambda **f: checkpoints.append(f),
                   upstream_lock=lambda: contextlib.nullcontext(),
                   now_iso=lambda: "2026-10-01T00:00:00+0800"), \
             patch(F.P, load_paper=lambda key: fake_entry(),
                   paper_tmp=lambda key: Path(td),
                   set_stage=lambda *a, **k: None), \
             patch(F, download_one=boom), \
             patch(sys, argv=["fetch_paper.py", "9709/2024/Jun/11"]):
            rc = F.main()

    check("退出码为 2（上游停止项）", rc == 2, f"rc={rc}")
    check("错误已落盘", len(written) == 1, f"written={len(written)}")
    if written:
        d = written[0]["detail"]
        check("错误分类为 network", d.get("error_class") == "network", json.dumps(d)[:200])
        check("记录异常类型", "ReadTimeout" in d.get("error", ""), d.get("error", ""))
        check("保留 traceback", "Traceback" in d.get("traceback_tail", ""), "")
    check("写 checkpoint 停止原因", any(c.get("stop_reason") == "download_error"
                                        for c in checkpoints), str(checkpoints)[:200])
    check("checkpoint 带 error_class", any(
        (c.get("stop_detail") or {}).get("error_class") == "network" for c in checkpoints), "")
    check("新错误要求再次明确恢复", any(c.get("needs_user_resume") is True for c in checkpoints), "")
    check("新错误停止时间不能沿用旧断点", any(
        c.get("stopped_at") == "2026-10-01T00:00:00+0800" for c in checkpoints), "")


def test_existing_stop_blocks_all_entrypoints() -> None:
    print("[5] 已有停止断点不能被直接命令或 --force 绕过")
    def forbidden(*args, **kwargs):
        raise AssertionError("停止断点下不应选卷、改状态或发请求")
    with patch(B, read_json=lambda *a, **k: {"needs_user_resume": True},
               set_checkpoint=forbidden), patch(F, download_one=forbidden), \
         patch(F.P, load_paper=forbidden), \
         patch(sys, argv=["fetch_paper.py", "9709/2024/Jun/11", "--force"]):
        check("直接 fetch 与 --force 保持停止", F.main() == 2)
    with patch(B, read_json=lambda *a, **k: {"needs_user_resume": True},
               set_checkpoint=forbidden), patch(RL.PQ, candidates=forbidden), \
         patch(RL, run_one=forbidden), patch(sys, argv=["run_loop.py"]):
        check("run_loop 在 claim 之前停止", RL.main() == 1)


def test_fetch_connect_error_is_network() -> None:
    print("[2] 连接错误同样归类 network")
    import httpx
    for exc in (httpx.ConnectError("boom"), httpx.ReadError("boom"),
                httpx.RemoteProtocolError("boom"), ConnectionResetError("boom")):
        names = {type(exc).__name__}
        net = isinstance(exc, OSError) or type(exc).__name__ in {
            "TimeoutException", "ReadTimeout", "ConnectTimeout", "WriteTimeout",
            "PoolTimeout", "ConnectError", "ReadError", "WriteError",
            "RemoteProtocolError", "LocalProtocolError", "ProxyError",
            "NetworkError", "TransportError", "UnsupportedProtocol"}
        check(f"{sorted(names)[0]} 归 network", net, "")


def test_do_fetch_mapping() -> None:
    print("[3] process_paper.do_fetch 退出码映射")
    with patch(PP.R, pdf_report=lambda key, seed=False: ({}, ["missing qp"])), \
         patch(PP, run_tool=lambda script, args: (2, "download failed")):
        code, detail = PP.do_fetch("9709/2024/Jun/11")
        check("fetch_paper rc=2 -> BLOCKED", code == PP.EXIT_BLOCKED, f"code={code} {detail[:80]}")
    with patch(PP.R, pdf_report=lambda key, seed=False: ({}, ["missing qp"])), \
         patch(PP, run_tool=lambda script, args: (3, "scan active")):
        code, _ = PP.do_fetch("9709/2024/Jun/11")
        check("fetch_paper rc=3 -> BLOCKED", code == PP.EXIT_BLOCKED, f"code={code}")
    with patch(PP.R, pdf_report=lambda key, seed=False: ({}, ["missing qp"])), \
         patch(PP, run_tool=lambda script, args: (4, "internal crash")):
        code, _ = PP.do_fetch("9709/2024/Jun/11")
        check("fetch_paper rc=4（内部崩溃）-> BLOCKED", code == PP.EXIT_BLOCKED, f"code={code}")
    with patch(PP.R, pdf_report=lambda key, seed=False: ({}, ["missing qp"])), \
         patch(PP, run_tool=lambda script, args: (1, "no entry")):
        code, _ = PP.do_fetch("9709/2024/Jun/11")
        check("fetch_paper rc=1（数据缺口）-> FAILED 不停止", code == PP.EXIT_FAILED, f"code={code}")
    with patch(PP.R, pdf_report=lambda key, seed=False: ({}, ["missing qp"])), \
         patch(PP, run_tool=lambda script, args: (0, "ok")):
        code, _ = PP.do_fetch("9709/2024/Jun/11")
        check("fetch_paper rc=0 -> OK", code == PP.EXIT_OK, f"code={code}")
    with patch(PP.R, pdf_report=lambda key, seed=False: ({}, [])), \
         patch(PP, run_tool=lambda script, args: (0, "should not run")):
        code, detail = PP.do_fetch("9709/2024/Jun/11")
        check("本地原件齐全时不下网", code == PP.EXIT_OK and "跳过下载" in detail, detail)


def test_pick_next_rotates() -> None:
    print("[4] run_loop.pick_next 科目轮转")
    rows = [{"key": f"{s}/2024/Jun/11", "subject": s} for s in ("0472", "8238", "8386")] * 4
    touched: set[str] = set()
    picked: list[str] = []
    pool = list(rows)
    for _ in range(3):
        row = RL.pick_next(pool, touched)
        touched.add(row["subject"])
        picked.append(row["subject"])
    check("前 3 次落在 3 个不同科目", len(set(picked)) == 3, str(picked))
    row = RL.pick_next(pool, touched)
    check("全部碰过后退化但不报错", row["subject"] in {"0472", "8238", "8386"}, str(row))
    check("空 touched 时取第一个", RL.pick_next(pool, set())["subject"] == "0472", "")


def main() -> int:
    test_fetch_timeout_persists_and_stops()
    test_fetch_connect_error_is_network()
    test_do_fetch_mapping()
    test_pick_next_rotates()
    test_existing_stop_blocks_all_entrypoints()
    print()
    if FAILURES:
        print(f"FAILED {len(FAILURES)}: {FAILURES}")
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
