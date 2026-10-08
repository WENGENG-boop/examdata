"""一次性探针：验证 import_index.py 的成功路径（CLI 幂等导入 + HTTP 回读）。

做法：把参考索引复制到临时 indexes 目录，临时把 B.INDEXES 指过去，
再调用 I.import_index(KEY)。不写 papers.json / errors.jsonl（不调用 record）。
服务端因为已有同一 qp sha 的**完全相同**的索引，导入是幂等的，不会改动任何共享状态。
"""
from __future__ import annotations

import io
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))

import batchlib as B
import import_index as I

if (getattr(sys.stdout, "encoding", "") or "").replace("-", "").lower() != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

KEY = "9709/2024/Jun/11"
REFERENCE = Path("C:/Users/weo/Desktop/api/cie-index-batch-2026-10-01"
                 "/9709/2024-Jun-11/cie-index.json")
SCRATCH = B.TMP / "_import_probe"

real_indexes = B.INDEXES
B.INDEXES = SCRATCH / "indexes"
try:
    target = I.index_path(KEY)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(REFERENCE, target)
    report = I.import_index(KEY)
finally:
    B.INDEXES = real_indexes

print(json.dumps({k: v for k, v in report.items() if k != "warnings"},
                 ensure_ascii=False, indent=2)[:2500])
print("warnings:", json.dumps(report["warnings"], ensure_ascii=False)[:600])
print()
print("stage:", report["stage"])
print("exit_code:", report["exit_code"])
print("import_succeeded:", report["import_succeeded"])
print("readback_verified:", report["readback_verified"])
print("question_count:", report["question_count"])
shutil.rmtree(SCRATCH, ignore_errors=True)
raise SystemExit(0 if report["stage"] == "imported_verified" else 1)
