"""离线探针：用旧试点索引验证「CLI 导入 -> API 回读 -> 服务索引文件比对」这条链路。

不写 indexes/、不写 papers.json、不写 errors.jsonl；只报告。
"""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import batchlib as B
import import_index as I

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

OLD_INDEX = Path("C:/Users/weo/Desktop/api/cie-index-batch-2026-10-01/9709/2024-Jun-11/cie-index.json")
QP = B.TMP / "9709" / "2024-Jun-11" / "9709_s24_qp_11.pdf"
MS = B.TMP / "9709" / "2024-Jun-11" / "9709_s24_ms_11.pdf"


def main() -> int:
    for path in (OLD_INDEX, QP, MS):
        if not path.is_file():
            print(f"缺少 {path}")
            return 1

    local = json.loads(OLD_INDEX.read_bytes().decode("utf-8"))
    qp_sha = I.document_sha(local, "qp")
    print(f"索引题数 {len(local.get('questions') or [])}  qp_sha {qp_sha}")
    print(f"本地 QP 实际 sha {B.sha256_file(QP)}")

    target = I.service_index_path(qp_sha)
    print(f"服务索引目标 {target}  已存在={target.is_file()}")
    if target.is_file():
        existing = json.loads(target.read_bytes().decode("utf-8"))
        stripped = {k: v for k, v in existing.items() if k not in I.SERVICE_ADDED_FIELDS}
        print(f"服务索引去掉 {I.SERVICE_ADDED_FIELDS} 后与旧索引相同: {stripped == local}")
        print(f"服务索引额外字段: {sorted(set(existing) - set(local))}")

    code, out, err, parsed = I.run_cli(OLD_INDEX, QP, MS)
    print(f"\n[1] CLI exit={code}")
    print(f"    stdout={ (out or '').strip()[:400] }")
    if err and err.strip():
        print(f"    stderr={err.strip()[:400]}")
    if parsed:
        print(f"    解析: sha256={parsed.get('sha256')} questions={parsed.get('questions')} "
              f"path={parsed.get('path')}")
    if code != 0:
        print("CLI 未成功，停止探针")
        return 2

    status, body = I.http_get(f"http://127.0.0.1:8000/api/v1/indexes/cie/{qp_sha}")
    print(f"\n[2] GET /api/v1/indexes/cie/{qp_sha} -> HTTP {status}")
    if status != 200:
        print(f"    body={body[:300]!r}")
        return 3
    remote = json.loads(body.decode("utf-8"))
    errors, warnings = I.compare_index(local, remote)
    print(f"    比对错误 {len(errors)} 警告 {len(warnings)}")
    for e in errors[:10]:
        print(f"    ! {e}")
    for w in warnings[:10]:
        print(f"    ~ {w}")

    stored = json.loads(target.read_bytes().decode("utf-8"))
    same = {k: v for k, v in stored.items() if k not in I.SERVICE_ADDED_FIELDS} == local
    print(f"\n[3] 服务索引文件去掉 {I.SERVICE_ADDED_FIELDS} 后与本地一致: {same}")
    print(f"    题数 {len(stored.get('questions') or [])}")
    ok = not errors and same
    print(f"\n结果: {'通过' if ok else '不通过'}")
    return 0 if ok else 4


if __name__ == "__main__":
    raise SystemExit(main())
