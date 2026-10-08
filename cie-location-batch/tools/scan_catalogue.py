"""扫目录格：第三方 43 科目全扫 2000–2026 × Mar/Jun/Nov；官方独有代码每科只探两格。

严格按提示词第 4 步与用户确认的范围方案：
- 单联网工作线程、一个共享 Fetcher、max_retries=1（不自动重试，避免与停止规则冲突）
- total == len(rows) 才继续，否则 catalogue_incomplete 并停止
- 明确 {status:101,data:null,message:"路径非法。"} 记为 subject_unavailable 并继续
- 其他未知业务响应 / 坏 JSON / 字段类型错 -> 记录具体错误并停止
- 每格落盘，每 5 分钟写进度
"""
from __future__ import annotations

import argparse
import io
import json
import sys
import time

import batchlib as B
import catalogue_classify as C

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

PROBE_CELLS = ((2000, "Mar"), (2024, "Jun"))
# 停止项：命中即落盘并结束本轮上游请求
STOP_KINDS = {"http_error", "invalid_json", "invalid_shape",
              "catalogue_incomplete", "unknown_business_response"}
FULL_SCAN_STATUSES = {"complete", "no_resources"}


def classify_rows(rows, subject, year, season):
    from collections import defaultdict
    recognized = defaultdict(list)
    unrecognized = []
    for row in rows:
        name = row.get("file") if isinstance(row, dict) else None
        match = B_FILE_RE.fullmatch(name) if isinstance(name, str) else None
        if not match:
            unrecognized.append({
                "file": name if isinstance(name, str) else repr(row)[:200],
                "reason": "filename_not_matching_qp_ms_pattern",
            })
            continue
        m = match.groupdict()
        if m["subject"] != subject:
            unrecognized.append({"file": name, "reason": f"subject_mismatch:{m['subject']}"})
            continue
        if int(m["year"]) != year % 100:
            unrecognized.append({"file": name, "reason": f"year_mismatch:{m['year']}"})
            continue
        if B.LETTER_SEASON[m["season"]] != season:
            unrecognized.append({"file": name, "reason": f"season_mismatch:{m['season']}"})
            continue
        recognized[(m["paper"], m["role"])].append(name)
    return recognized, unrecognized


import re
B_FILE_RE = re.compile(
    r"(?P<subject>\d{4})_(?P<season>[msw])(?P<year>\d{2})_(?P<role>qp|ms)_(?P<paper>\d{1,2})\.pdf"
)


def apply_cell(grid, papers, subject, year, season, rows, evidence):
    recognized, unrecognized = classify_rows(rows, subject, year, season)
    identities = sorted({paper for paper, _role in recognized})
    stats = {"paired": 0, "qp_only": 0, "ms_only": 0, "ambiguous": 0}
    ambiguous = []
    for paper in identities:
        qps = sorted(set(recognized.get((paper, "qp"), [])))
        mss = sorted(set(recognized.get((paper, "ms"), [])))
        key = B.paper_key(subject, year, season, paper)
        if len(qps) > 1 or len(mss) > 1:
            kind = "ambiguous"
            ambiguous.append({"paper": paper, "qp": qps, "ms": mss})
        elif qps and mss:
            kind = "paired"
        elif qps:
            kind = "qp_only"
        else:
            kind = "ms_only"
        stats[kind] += 1
        entry = papers.get(key) or {
            "key": key, "subject": subject, "year": year, "season": season, "paper": paper,
            "stage": "discovered", "discovered_at": B.now_iso(),
        }
        entry.update({"kind": kind, "qp": qps, "ms": mss,
                      "discovered_from": B.SOURCE,
                      "catalogue_cell": f"{subject}|{year}|{season}"})
        if kind == "ambiguous":
            entry["stage"] = "ambiguous"
        papers[key] = entry

    status = "complete" if rows else "no_resources"
    grid[f"{subject}|{year}|{season}"] = {
        "subject": subject, "year": year, "season": season,
        "status": status, "requested": True,
        "total": evidence["total"], "rows": len(rows),
        "identities": len(identities), "kinds": stats,
        "unrecognized": unrecognized, "ambiguous": ambiguous,
        "evidence": evidence,
    }
    return status, stats


def request_cell(fetcher, subject, year, season):
    response = fetcher.post_form(
        B.RENUM_URL, {"subject": subject, "year": year, "season": season},
        follow_redirects=False)
    body = response.content or b""
    evidence = {
        "url": B.RENUM_URL, "method": "POST",
        "params": {"subject": subject, "year": year, "season": season},
        "fetched_at": B.now_iso(),
        "http_status": response.status,
        "body_sha256": B.sha256_bytes(body),
        "raw_head": (response.text or "")[:500],
    }
    verdict = C.classify_catalogue_response(response.status, response.text)
    return verdict, evidence


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--subject", action="append", default=None)
    args = parser.parse_args()

    B.ensure_dirs()
    subjects_payload = B.read_json(B.SUBJECTS)
    if not subjects_payload:
        raise SystemExit("缺少 subjects.json")
    entries = subjects_payload["subjects"]
    if args.subject:
        wanted = set(args.subject)
        entries = [e for e in entries if e["code"] in wanted]

    grid = B.read_json(B.GRID, {}) or {}
    papers = B.read_json(B.PAPERS, {}) or {}

    probe_scope = [e for e in entries if not e["third_party_confirmed"]]
    full_scope = [e for e in entries if e["third_party_confirmed"]]
    queue = [(e, "probe") for e in probe_scope] + [(e, "full") for e in full_scope]

    B.setup_repo_import()
    from examdata.core.config import Settings
    from examdata.core.fetch import Fetcher

    processed = 0
    progress_mark = time.monotonic()
    last_subject = None

    with Fetcher(Settings(max_retries=1)) as fetcher:
        for entry, scope in queue:
            subject = entry["code"]
            last_subject = subject
            entry.setdefault("scan_scope", scope)
            entry["scan_scope"] = scope

            if scope == "probe":
                if entry.get("status") in {"subject_unavailable", "full_scan_required"}:
                    continue
                cells = list(PROBE_CELLS)
                verdicts = []
                stop = None
                for year, season in cells:
                    if args.limit and processed >= args.limit:
                        break
                    processed += 1
                    B.set_checkpoint(current_cell=f"{subject}|{year}|{season}",
                                     stage="scanning_probe", current_subject=subject,
                                     last_progress_at=B.now_iso())
                    verdict, evidence = request_cell(fetcher, subject, year, season)
                    evidence["requested"] = True
                    evidence["verdict"] = verdict["kind"]
                    verdicts.append({"year": year, "season": season, "verdict": verdict,
                                     "evidence": evidence})
                    if verdict["kind"] in STOP_KINDS:
                        stop = {"subject": subject, "year": year, "season": season,
                                "verdict": verdict, "evidence": evidence}
                        break
                    grid[f"{subject}|{year}|{season}"] = {
                        "subject": subject, "year": year, "season": season,
                        "status": verdict["kind"], "requested": True,
                        "evidence": evidence,
                    }
                    B.atomic_write_json(B.GRID, grid)
                if stop:
                    B.append_jsonl(B.ERRORS, {"kind": f"probe_{stop['verdict']['kind']}",
                                              **stop})
                    B.set_checkpoint(stop_reason=f"probe_{stop['verdict']['kind']}",
                                     stop_detail=stop, stage="stopped",
                                     current_subject=subject)
                    print(f"[停止] 探查 {subject} {stop['year']}/{stop['season']} "
                          f"{stop['verdict']['kind']}: {stop['verdict'].get('detail')}")
                    return 2
                if len(verdicts) < len(cells):
                    break
                all_unavailable = all(v["verdict"]["kind"] == "subject_unavailable"
                                      for v in verdicts)
                if all_unavailable:
                    entry["status"] = "subject_unavailable"
                    entry["subject_unavailable_evidence"] = [
                        {k: v["evidence"][k] for k in
                         ("params", "http_status", "body_sha256", "raw_head", "fetched_at")}
                        for v in verdicts
                    ]
                    probe_keys = [f"{subject}|{y}|{s}" for y, s in cells]
                    for year in range(B.YEAR_START, B.YEAR_END + 1):
                        for season in B.SEASONS:
                            key = f"{subject}|{year}|{season}"
                            if key in grid:
                                continue
                            grid[key] = {
                                "subject": subject, "year": year, "season": season,
                                "status": "subject_unavailable_inferred",
                                "requested": False,
                                "inferred_from": probe_keys,
                                "evidence_ref": f"subjects.json#/{subject}",
                            }
                else:
                    entry["status"] = "full_scan_required"
                    entry["probe_verdicts"] = [
                        {"year": v["year"], "season": v["season"], "kind": v["verdict"]["kind"],
                         "detail": v["verdict"].get("detail"),
                         "total": v["verdict"].get("total")}
                        for v in verdicts
                    ]
                    B.append_jsonl(B.ERRORS, {
                        "kind": "catalogue_probe_contradicts_directory",
                        "subject": subject,
                        "detail": "探查返回合法目录结构，与「第三方无此科目」不一致，已加入完整扫描范围",
                        "probe_verdicts": entry["probe_verdicts"], "at": B.now_iso(),
                    })
                    for year, season in cells:
                        key = f"{subject}|{year}|{season}"
                        if key in grid:
                            grid[key] = {**grid[key], "status": "probe_ok_pending_full_scan"}
                B.atomic_write_json(B.GRID, grid)
                B.atomic_write_json(B.SUBJECTS, subjects_payload)
                continue

            # scope == full：第三方列出的科目，扫全部格
            for year in range(B.YEAR_START, B.YEAR_END + 1):
                for season in B.SEASONS:
                    cell_key = f"{subject}|{year}|{season}"
                    existing = grid.get(cell_key)
                    if existing and existing.get("status") in FULL_SCAN_STATUSES:
                        continue
                    if args.limit and processed >= args.limit:
                        break
                    processed += 1
                    B.set_checkpoint(current_cell=cell_key, stage="scanning_full",
                                     current_subject=subject,
                                     last_progress_at=B.now_iso())
                    verdict, evidence = request_cell(fetcher, subject, year, season)
                    kind = verdict["kind"]
                    if kind == "ok":
                        evidence["total"] = verdict["total"]
                        apply_cell(grid, papers, subject, year, season,
                                   verdict["rows"], evidence)
                        B.atomic_write_json(B.PAPERS, papers)
                    elif kind == "subject_unavailable":
                        grid[cell_key] = {
                            "subject": subject, "year": year, "season": season,
                            "status": "declared_subject_route_mismatch",
                            "requested": True, "evidence": evidence,
                            "note": "第三方目录已列出该科目，但本格返回路由不可用；不整科跳过",
                        }
                        B.append_jsonl(B.ERRORS, {
                            "kind": "declared_subject_route_mismatch",
                            "cell": cell_key, "evidence": evidence, "at": B.now_iso(),
                        })
                    else:
                        grid[cell_key] = {
                            "subject": subject, "year": year, "season": season,
                            "status": kind, "requested": True,
                            "detail": verdict.get("detail"), "evidence": evidence,
                        }
                        B.atomic_write_json(B.GRID, grid)
                        B.append_jsonl(B.ERRORS, {
                            "kind": f"catalogue_{kind}", "cell": cell_key,
                            "detail": verdict.get("detail"), "evidence": evidence,
                            "at": B.now_iso(),
                        })
                        B.set_checkpoint(stop_reason=f"catalogue_{kind}",
                                         stop_detail={"cell": cell_key,
                                                      "detail": verdict.get("detail")},
                                         stage="stopped", current_cell=cell_key)
                        print(f"[停止] {cell_key} {kind}: {verdict.get('detail')}")
                        return 2
                    B.atomic_write_json(B.GRID, grid)
                    if time.monotonic() - progress_mark > 300:
                        progress_mark = time.monotonic()
                        done = sum(1 for v in grid.values()
                                   if v.get("status") in FULL_SCAN_STATUSES)
                        print(f"  [进度] 请求={processed} 格完成={done} "
                              f"身份={len(papers)} 当前={cell_key}", flush=True)
                        B.set_checkpoint(progress={"requests": processed,
                                                   "cells_done": done,
                                                   "papers": len(papers)},
                                         stage="scanning_full")
                if args.limit and processed >= args.limit:
                    break
            subject_cells = [f"{subject}|{y}|{s}"
                             for y in range(B.YEAR_START, B.YEAR_END + 1) for s in B.SEASONS]
            entry["cells_done"] = sum(
                1 for k in subject_cells
                if grid.get(k, {}).get("status") in FULL_SCAN_STATUSES)
            entry["cells_requested"] = sum(
                1 for k in subject_cells if grid.get(k, {}).get("requested"))
            entry["status"] = ("scanned" if entry["cells_requested"] == len(subject_cells)
                               else "scanning")
            B.atomic_write_json(B.SUBJECTS, subjects_payload)
            B.atomic_write_json(B.GRID, grid)
            if args.limit and processed >= args.limit:
                break

    cells_per_subject = len(B.SEASONS) * (B.YEAR_END - B.YEAR_START + 1)
    expected_cells = len(subjects_payload["subjects"]) * cells_per_subject
    done = sum(1 for v in grid.values() if v.get("status") in FULL_SCAN_STATUSES)
    inferred = sum(1 for v in grid.values()
                   if v.get("status") == "subject_unavailable_inferred")
    business_rejected = sum(1 for v in grid.values()
                            if v.get("status") in {"subject_unavailable",
                                                   "declared_subject_route_mismatch"})
    failed = sum(1 for v in grid.values() if v.get("status") in STOP_KINDS)
    unqueried = expected_cells - len(grid)
    complete = (unqueried == 0 and failed == 0)
    B.set_checkpoint(
        stage="scan_finished" if complete else "scan_finished_partial",
        current_cell=None, last_subject=last_subject, last_progress_at=B.now_iso(),
        totals={"requests": processed, "cells_done": done, "business_rejected": business_rejected,
                "inferred_cells": inferred, "failed_cells": failed,
                "unqueried_cells": unqueried, "expected_cells": expected_cells,
                "papers": len(papers), "complete": complete})
    print(f"扫描结束：实际请求 {processed} 次，实测完成格 {done}，"
          f"业务拒绝格 {business_rejected}，推断跳过格 {inferred}，"
          f"失败格 {failed}，未查格 {unqueried}，身份 {len(papers)}，"
          f"完整={complete}")
    return 0 if complete else 3


if __name__ == "__main__":
    raise SystemExit(main())
