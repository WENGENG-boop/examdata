"""分类器离线回归。不联网。

覆盖提示词要求的六种情形，外加若干边界（rows 非列表、total 负数、
total 是布尔、缺字段、status:101 但 message 不同）。
"""
from __future__ import annotations

import io
import json
import sys

import catalogue_classify as C

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

FAILURES = []


def check(name, got, want_kind, **want_fields):
    ok = got["kind"] == want_kind
    for key, value in want_fields.items():
        if got.get(key) != value:
            ok = False
    status = "PASS" if ok else "FAIL"
    if not ok:
        FAILURES.append(name)
    print(f"[{status}] {name}: kind={got['kind']}"
          + (f" total={got.get('total')} rows={len(got.get('rows') or [])}"
             if got["kind"] == "ok" else f" detail={got.get('detail')}"))


# 1. 正常有资源
rows37 = [{"file": f"9709_s24_qp_{i:02d}.pdf", "lessons": []} for i in range(1, 38)]
check("normal_with_resources",
      C.classify_catalogue_response(200, json.dumps({"total": 37, "rows": rows37})),
      "ok", total=37)

# 2. 正常空目录
check("normal_empty",
      C.classify_catalogue_response(200, json.dumps({"total": 0, "rows": []})),
      "ok", total=0)

# 3. 明确 status:101 路由不可用
check("explicit_route_unavailable",
      C.classify_catalogue_response(
          200, json.dumps({"status": 101, "data": None, "message": "路径非法。"},
                          ensure_ascii=False)),
      "subject_unavailable")

# 4a. 未知业务码
check("unknown_business_code",
      C.classify_catalogue_response(
          200, json.dumps({"status": 500, "data": None, "message": "服务器错误"},
                          ensure_ascii=False)),
      "unknown_business_response")

# 4b. status:101 但 message 不同 -> 不能当作科目不可用
check("status101_other_message",
      C.classify_catalogue_response(
          200, json.dumps({"status": 101, "data": None, "message": "参数错误"},
                          ensure_ascii=False)),
      "unknown_business_response")

# 4c. status:101 但 data 非 null
check("status101_data_not_null",
      C.classify_catalogue_response(
          200, json.dumps({"status": 101, "data": [], "message": "路径非法。"},
                          ensure_ascii=False)),
      "unknown_business_response")

# 5. 损坏 JSON
check("broken_json", C.classify_catalogue_response(200, "{not json at all"),
      "invalid_json")
check("empty_body", C.classify_catalogue_response(200, ""), "invalid_json")

# 6. total 与 rows 不一致
check("total_rows_mismatch",
      C.classify_catalogue_response(200, json.dumps({"total": 5, "rows": [1, 2]})),
      "catalogue_incomplete")

# 7. HTTP 层错误
check("http_404", C.classify_catalogue_response(404, "Not Found"), "http_error")
check("http_502", C.classify_catalogue_response(502, ""), "http_error")

# 8. 边界：rows 非列表 / total 类型错 / total 负数 / 缺字段 / 顶层非对象
check("rows_not_list",
      C.classify_catalogue_response(200, json.dumps({"total": 1, "rows": "x"})),
      "catalogue_incomplete")
check("total_bool",
      C.classify_catalogue_response(200, json.dumps({"total": True, "rows": [1]})),
      "catalogue_incomplete")
check("total_negative",
      C.classify_catalogue_response(200, json.dumps({"total": -1, "rows": []})),
      "catalogue_incomplete")
check("missing_total",
      C.classify_catalogue_response(200, json.dumps({"rows": []})),
      "catalogue_incomplete")
check("missing_rows",
      C.classify_catalogue_response(200, json.dumps({"total": 0})),
      "catalogue_incomplete")
check("top_level_list", C.classify_catalogue_response(200, "[]"), "invalid_shape")

print()
if FAILURES:
    print(f"回归失败 {len(FAILURES)} 项: {FAILURES}")
    raise SystemExit(1)
print("全部 17 项回归通过")
