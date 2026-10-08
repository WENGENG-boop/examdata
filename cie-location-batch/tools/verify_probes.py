"""联网确认：合法科目的正常目录 / 空目录 / 官方独有科目的业务拒绝。

保存每例的实际响应形状作为证据，不猜测。
"""
from __future__ import annotations

import io
import json
import sys

import batchlib as B
import catalogue_classify as C

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

CASES = [
    ("9709", 2024, "Jun", "已知有资源：验证正常目录"),
    ("9709", 2000, "Mar", "合法科目 + 极早年/春季：验证空目录形状"),
    ("0413", 2000, "Mar", "另一合法科目的空目录"),
    ("9709", 2026, "Jun", "当前年份（2026）"),
    ("0262", 2000, "Mar", "官方独有科目探查格 1"),
    ("0262", 2024, "Jun", "官方独有科目探查格 2"),
]


def main() -> int:
    B.ensure_dirs()
    B.setup_repo_import()
    from examdata.core.config import Settings
    from examdata.core.fetch import Fetcher

    results = []
    with Fetcher(Settings(max_retries=1)) as fetcher:
        for subject, year, season, why in CASES:
            response = fetcher.post_form(
                B.RENUM_URL, {"subject": subject, "year": year, "season": season},
                follow_redirects=False)
            body = response.content or b""
            verdict = C.classify_catalogue_response(response.status, response.text)
            record = {
                "subject": subject, "year": year, "season": season, "why": why,
                "http_status": response.status, "error": response.error,
                "body_sha256": B.sha256_bytes(body), "body_bytes": len(body),
                "raw_head": (response.text or "")[:500],
                "verdict": verdict["kind"], "detail": verdict.get("detail"),
                "total": verdict.get("total"),
                "rows": len(verdict["rows"]) if verdict["kind"] == "ok" else None,
                "fetched_at": B.now_iso(),
            }
            results.append(record)
            print(f"{subject} {year} {season}: HTTP {response.status} -> {verdict['kind']}"
                  + (f" total={verdict.get('total')}"
                     if verdict["kind"] == "ok" else f" ({verdict.get('detail')})"))
            print(f"    raw: {(response.text or '')[:200]}")
            if verdict["kind"] not in C.CONTINUE_KINDS:
                print(f"[停止] 出现停止类响应 {verdict['kind']}，不再继续探查")
                break

    B.atomic_write_json(B.WORK / "verify-probes.json", {
        "generated_at": B.now_iso(), "url": B.RENUM_URL, "results": results})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
