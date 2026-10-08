"""目录接口响应的纯分类函数（不联网，可离线回归）。

把「HTTP 状态」与「业务状态」分开：
- HTTP 非 2xx           -> http_error            (停止)
- 非 JSON / 非对象       -> invalid_json / invalid_shape (停止)
- 有 rows+total 且自洽    -> ok                    (继续)
- 有 rows+total 但不自洽  -> catalogue_incomplete  (停止)
- 明确 {status:101,data:null,message:"路径非法。"} -> subject_unavailable (继续)
- 其余任何业务码/形状     -> unknown_business_response (停止)

刻意不把「没有 rows」一律当成科目不可用：只有三个字段同时精确匹配才算。
"""
from __future__ import annotations

import json

ROUTE_UNAVAILABLE_STATUS = 101
ROUTE_UNAVAILABLE_MESSAGE = "路径非法。"

# 可以继续扫描的结论
CONTINUE_KINDS = {"ok", "subject_unavailable"}


def classify_catalogue_response(status: int, text: str | None) -> dict:
    """返回 {"kind": ..., "detail": ...}；kind 不在 CONTINUE_KINDS 里即为停止项。"""
    if not (200 <= status < 300):
        return {"kind": "http_error", "detail": f"HTTP {status}"}

    raw = text or ""
    try:
        payload = json.loads(raw)
    except (ValueError, TypeError) as exc:
        return {"kind": "invalid_json",
                "detail": f"{type(exc).__name__}: {exc}",
                "raw_head": raw[:500]}

    if not isinstance(payload, dict):
        return {"kind": "invalid_shape",
                "detail": f"top level is {type(payload).__name__}, expected object",
                "raw_head": raw[:500]}

    has_rows = "rows" in payload
    has_total = "total" in payload

    if has_rows or has_total:
        if not (has_rows and has_total):
            missing = "total" if has_rows else "rows"
            return {"kind": "catalogue_incomplete",
                    "detail": f"missing field: {missing}", "raw_head": raw[:500]}
        rows = payload["rows"]
        total = payload["total"]
        if not isinstance(rows, list):
            return {"kind": "catalogue_incomplete",
                    "detail": f"rows is {type(rows).__name__}, expected list",
                    "raw_head": raw[:500]}
        if isinstance(total, bool) or not isinstance(total, int):
            return {"kind": "catalogue_incomplete",
                    "detail": f"total is {type(total).__name__}, expected int",
                    "raw_head": raw[:500]}
        if total < 0:
            return {"kind": "catalogue_incomplete",
                    "detail": f"total is negative: {total}", "raw_head": raw[:500]}
        if total != len(rows):
            return {"kind": "catalogue_incomplete",
                    "detail": f"total={total} len(rows)={len(rows)}", "raw_head": raw[:500]}
        return {"kind": "ok", "total": total, "rows": rows}

    # 三个字段必须同时精确匹配，才认定是业务层路由不可用
    if (payload.get("status") == ROUTE_UNAVAILABLE_STATUS
            and payload.get("data", "MISSING") is None
            and payload.get("message") == ROUTE_UNAVAILABLE_MESSAGE):
        return {"kind": "subject_unavailable",
                "detail": f"business status {ROUTE_UNAVAILABLE_STATUS}",
                "raw_head": raw[:500]}

    return {"kind": "unknown_business_response",
            "detail": f"business status={payload.get('status')!r} "
                      f"keys={sorted(payload.keys())}",
            "raw_head": raw[:500]}
