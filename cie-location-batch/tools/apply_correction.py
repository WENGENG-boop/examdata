"""修正分类器缺陷造成的误判，保留全部历史证据。

- 不删除、不覆盖 errors.jsonl 里的原条目
- 追加 classification_correction，含旧分类、新分类、对应请求与重新探查到的原响应证据
- 只解除由本缺陷导致的停止；存在其他 http_error / 未知响应停止项时拒绝执行
"""
from __future__ import annotations

import io
import json
import sys

import batchlib as B

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

DEFECT_STOP_REASON = "catalogue_incomplete"
CORRECTION_KIND = "classification_correction"
CELL = "0262|2000|Mar"


def main() -> int:
    B.ensure_dirs()
    lines = []
    if B.ERRORS.exists():
        lines = [json.loads(x) for x in
                 B.ERRORS.read_bytes().decode("utf-8").splitlines() if x.strip()]
    originals = [r for r in lines if r.get("kind") == "catalogue_incomplete"
                 and r.get("cell") == CELL]
    if not originals:
        print("errors.jsonl 中没有对应的原误判条目，无需修正")
        return 1

    others = [r for r in lines
              if r.get("kind") in {"catalogue_http_error", "probe_http_error",
                                   "catalogue_unknown_business_response",
                                   "catalogue_invalid_json", "catalogue_invalid_shape"}
              and r.get("kind") != CORRECTION_KIND]
    if others:
        print(f"存在其他停止项 {len(others)} 条，拒绝解除停止：{others[:2]}")
        return 2

    probes = B.read_json(B.WORK / "verify-probes.json", {}) or {}
    matching = [r for r in probes.get("results", [])
                if r["subject"] == "0262" and r["year"] == 2000 and r["season"] == "Mar"]
    if not matching:
        print("缺少 0262|2000|Mar 的重新探查证据，不能仅凭「缺 rows」改判")
        return 3
    evidence = matching[0]
    if evidence["verdict"] != "subject_unavailable":
        print(f"重新探查结论为 {evidence['verdict']}，不是科目不可用，拒绝改判")
        return 4

    correction = {
        "kind": CORRECTION_KIND,
        "cell": CELL,
        "supersedes": originals[0],
        "old_classification": "catalogue_incomplete",
        "new_classification": "subject_unavailable",
        "defect": "分类器把业务层路由不可用 {status:101,data:null,message:'路径非法。'} "
                  "误当作清单截断；原实现只查 payload['rows'] 缺失即抛 KeyError",
        "request": {"url": B.RENUM_URL, "method": "POST",
                    "params": {"subject": "0262", "year": 2000, "season": "Mar"}},
        "original_response_evidence": {
            "note": "原次请求未保存正文，仅存 body_sha256；下列为同参数重新探查所得",
            "http_status": evidence["http_status"],
            "body_sha256": evidence["body_sha256"],
            "raw_head": evidence["raw_head"],
            "reprobe_at": evidence["fetched_at"],
            "reprobe_verdict": evidence["verdict"],
        },
        "scope": "仅解除本缺陷造成的停止；未清除任何 HTTP 错误或未知响应停止记录",
        "at": B.now_iso(),
    }
    B.append_jsonl(B.ERRORS, correction)
    print("已追加 classification_correction")

    grid = B.read_json(B.GRID, {}) or {}
    if CELL in grid:
        grid[CELL].update({
            "status": "subject_unavailable",
            "requested": True,
            "correction": CORRECTION_KIND,
            "correction_at": correction["at"],
            "evidence": {
                "url": B.RENUM_URL, "method": "POST",
                "params": {"subject": "0262", "year": 2000, "season": "Mar"},
                "fetched_at": evidence["fetched_at"],
                "http_status": evidence["http_status"],
                "body_sha256": evidence["body_sha256"],
                "raw_head": evidence["raw_head"],
            },
        })
        grid[CELL].pop("error", None)
        B.atomic_write_json(B.GRID, grid)
        print(f"已把 {CELL} 改判为 subject_unavailable")

    state = B.read_json(B.CHECKPOINT, {}) or {}
    if state.get("stop_reason") == DEFECT_STOP_REASON:
        state.pop("stop_reason", None)
        state.pop("stop_detail", None)
        state["stage"] = "scan_ready"
        state["stop_lifted"] = {
            "reason": DEFECT_STOP_REASON, "by": CORRECTION_KIND,
            "at": correction["at"],
            "note": "仅解除分类器缺陷造成的停止；HTTP 错误停止规则未放宽",
        }
        state["updated_at"] = B.now_iso()
        B.atomic_write_json(B.CHECKPOINT, state)
        print("已解除分类器缺陷造成的停止状态")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
