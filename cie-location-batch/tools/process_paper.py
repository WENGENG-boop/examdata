"""单命令跑完一卷：下载 -> OCR 定位 -> 本地逐题核验 -> 导入回读 -> 清理临时原件。

阶段顺序固定，任何一步失败就落盘、写 checkpoint 并立刻返回，不跳阶段也不掩盖：

1. `fetch`    本地缺原件时才联网（`fetch_paper.py`，统一 API，单线程）
2. `index`    `ocr_index.py` 逐页渲染 + OCR 识别题号，产出 schema 合法索引
3. `verify`   `verify_ocr.py` 逐区域裁剪核验；有任何 issues 就停在 validation_partial
4. `import`   `import_index.import_index` 走 CLI 导入 + API 回读比对
5. `cleanup`  `cleanup_paper.cleanup` 六条件闸门通过才删临时 PDF/图片

只有 1-5 全部成功退出码才是 0。`--stage` 可从中间阶段续跑。
"""
from __future__ import annotations

import argparse
import io
import json
import os
import subprocess
import sys
from pathlib import Path

import batchlib as B
import cleanup_paper as C
import import_index as I
import pipelinestate as S
import run_paper as R

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

EXIT_OK = 0
EXIT_BLOCKED = 1
EXIT_FAILED = 2
EXIT_VERIFY = 3

STAGES = ("fetch", "index", "verify", "import", "cleanup")
PY = sys.executable


def run_tool(script: str, args: list[str]) -> tuple[int, str]:
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    proc = subprocess.run([PY, str(B.TOOLS / script), *args], cwd=str(B.TOOLS),
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", env=env)
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def do_fetch(key: str) -> tuple[int, str]:
    info, problems = R.pdf_report(key, seed=False)
    if not problems:
        return EXIT_OK, "本地原件齐全，跳过下载"
    code, out = run_tool("fetch_paper.py", [key])
    if code == 2:
        return EXIT_BLOCKED, f"上游 HTTP 错误/超时，已停止联网：{out[-800:]}"
    if code == 3:
        return EXIT_BLOCKED, f"拒绝联网（目录扫描进行中）：{out[-800:]}"
    if code not in (0, 1):
        return EXIT_BLOCKED, f"fetch_paper 异常退出（code={code}），按停止规则处理：{out[-800:]}"
    return (EXIT_OK, out[-400:]) if code == 0 else (EXIT_FAILED, out[-800:])


def do_index(key: str) -> tuple[int, str]:
    code, out = run_tool("ocr_index.py", [key, "--force"])
    if code != 0:
        S.set_stage(key, "index_failed")
        return EXIT_FAILED, out[-1200:]
    return EXIT_OK, out[-400:]


def do_verify(key: str) -> tuple[int, str]:
    code, out = run_tool("verify_ocr.py", [key])
    if code != 0:
        S.set_stage(key, "validation_failed")
        return EXIT_FAILED, out[-1200:]
    index_file = I.index_path(key)
    data = json.loads(index_file.read_text(encoding="utf-8"))
    questions = [q["question"] for q in data["questions"]]
    problems, stats = C.verification_state(key, questions)
    if problems:
        S.set_stage(key, "validation_partial")
        B.append_jsonl(B.ERRORS, {"at": B.now_iso(), "key": key, "stage": "validation_partial",
                                  "errors": problems, "verification": stats})
        return EXIT_VERIFY, json.dumps({"verification": stats, "problems": problems},
                                       ensure_ascii=False)
    return EXIT_OK, json.dumps({"verification": stats}, ensure_ascii=False)


def do_import(key: str) -> tuple[int, str]:
    report = I.import_index(key)
    I.record(report)
    blob = json.dumps({k: report[k] for k in
                       ("stage", "question_count", "readback_verified", "import_succeeded",
                        "service_index_path", "index_sha256") if k in report},
                      ensure_ascii=False)
    return (EXIT_OK if report["exit_code"] == 0 else EXIT_FAILED), blob


def do_cleanup(key: str) -> tuple[int, str]:
    report = C.cleanup(key)
    blob = json.dumps({"stage": report["stage"], "deleted": len(report["deleted"]),
                       "freed_bytes": report["freed_bytes"],
                       "problems": report["problems"]}, ensure_ascii=False)
    return (EXIT_OK if report["exit_code"] == 0 else EXIT_FAILED), blob


HANDLERS = {"fetch": do_fetch, "index": do_index, "verify": do_verify,
            "import": do_import, "cleanup": do_cleanup}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("key", help="subject/year/season/paper，如 8386/2026/Jun/11")
    parser.add_argument("--stage", default="fetch", choices=STAGES,
                        help="从这个阶段开始跑到 cleanup")
    parser.add_argument("--only", choices=STAGES, help="只跑这一个阶段")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    start = STAGES.index(args.only or args.stage)
    results = []
    final = EXIT_OK
    for stage in STAGES[start:]:
        code, detail = HANDLERS[stage](args.key)
        results.append({"stage": stage, "exit": code, "detail": detail})
        if code != EXIT_OK:
            final = code
            break
        if args.only:
            break

    payload = {"key": args.key, "exit": final, "stages": results,
               "stage": (S.load(args.key) or {}).get("stage")}
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"=== {args.key}  退出码 {final}  当前阶段 {payload['stage']}")
        for row in results:
            mark = "OK " if row["exit"] == 0 else "!! "
            print(f" {mark}{row['stage']:8s} {row['detail']}")
    return final


if __name__ == "__main__":
    raise SystemExit(main())
