# -*- coding: utf-8 -*-
"""Append the stop_rule_hardening record to errors.jsonl (idempotent). One-off."""
import sys

sys.path.insert(0, "tools")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import batchlib as B

existing = B.ERRORS.read_text(encoding="utf-8") if B.ERRORS.exists() else ""
if '"stop_rule_hardening"' in existing:
    print("stop_rule_hardening already present, skip")
    sys.exit(0)

B.append_jsonl(B.ERRORS, {
    "kind": "stop_rule_hardening",
    "gap": "fetch_paper.py 以非 0/1/2/3 退出码崩溃时（未捕获异常），process_paper.do_fetch 落入 FAILED 分支，run_loop 会继续处理下一卷，违反“先落盘错误并停止本轮新的上游请求”规则",
    "fix": {
        "fetch_paper.py": "__main__ 增加 try/except BaseException：打印 traceback 后 SystemExit(4)",
        "process_paper.py": "do_fetch 增加 `code not in (0, 1)` -> EXIT_BLOCKED，异常退出按停止规则处理",
    },
    "tests": {
        "runner": "pytest 在 Python 3.14 下 capture 报 'I/O operation on closed file' 无法收集用例，改用直接运行脚本（三套件全部通过）",
        "test_stop_rule": "ALL PASS；新增用例 rc=4（内部崩溃）-> BLOCKED、rc=1（数据缺口）-> FAILED 不停止 均通过",
        "test_classify": "17/17 通过",
        "test_cleanup_gate": "ALL PASS",
    },
    "at": B.now_iso(),
})
print("appended stop_rule_hardening")
