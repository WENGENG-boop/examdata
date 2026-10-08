"""生成可恢复队列与来源缺口交付物（纯离线，不访问上游）。

输出到 work/coordinate-audit-2026-10-05/deliverables/：
  stats.json                 机器可读统计（全部由当前文件重算）
  resumable-queue.jsonl      按 pick_queue 规范顺序的可选卷（首行=下一个应处理卷）
  resumable-queue-summary.json  队列计数 + 停止点位置说明
  blocked-queue.jsonl        阶段被跳过的卷（需修复或人工决策，不自动重试）
  source-gaps.json           未列出科目 + 第三方列出但无索引科目
  service-conflicts.json     本地/服务索引不一致清单
"""
from __future__ import annotations

import collections
import hashlib
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

HERE = Path(__file__).parent
BATCH = HERE.parents[1]
TOOLS = BATCH / "tools"
sys.path.insert(0, str(TOOLS))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import batchlib as B  # noqa: E402
import pick_queue as Q  # noqa: E402

OUT = HERE / "deliverables"
OUT.mkdir(exist_ok=True)

CST = timezone(timedelta(hours=8))
now = datetime.now(CST).isoformat(timespec="seconds")


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_json(obj) -> str:
    return hashlib.sha256(
        json.dumps(obj, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()


papers = B.read_json(B.PAPERS, {}) or {}
summary = B.read_json(B.SUMMARY, {}) or {}
ck = B.read_json(B.CHECKPOINT, {}) or {}
grid = B.read_json(B.GRID, {}) or {}
state = B.read_json(B.WORK / "state.json", {}) or {}
evidence = B.read_json(HERE / "evidence.json", {}) or {}

entries = evidence.get("entries") or []
svc = evidence.get("service") or {}
counts = evidence.get("counts") or {}
stage_counts = evidence.get("stage_counts") or {}

cleaned = Q.cleaned_keys()
DONE = Q.DONE_STAGES
SKIP = Q.SKIP_STAGES

# ---------------------------------------------------------------- 队列
rows = []
stage_mismatch = []
for key, entry in papers.items():
    if not isinstance(entry, dict):
        continue
    mirror = (state.get(key) or {}).get("stage")
    paper_stage = entry.get("stage") or "discovered"
    stage = mirror or paper_stage
    if mirror and mirror != paper_stage:
        stage_mismatch.append({"key": key, "mirror_stage": mirror,
                               "paper_stage": paper_stage})
    kind = entry.get("kind")
    subject = entry.get("subject") or key.split("/")[0]
    rows.append({
        "key": key,
        "kind": kind,
        "subject": subject,
        "year": entry.get("year"),
        "season": entry.get("season"),
        "paper": entry.get("paper"),
        "stage": stage,
        "mirror_stage": mirror,
        "paper_stage": paper_stage,
        "cleaned_logged": key in cleaned,
    })

done_rows = [r for r in rows if r["cleaned_logged"] or r["stage"] in DONE]
live_rows = [r for r in rows if not (r["cleaned_logged"] or r["stage"] in DONE)]

selectable = [r for r in live_rows if r["stage"] not in SKIP]
blocked = [r for r in live_rows if r["stage"] in SKIP]

ordered = Q.interleave([dict(r) for r in selectable])
blocked_ordered = sorted(blocked, key=lambda r: (r["stage"], r["subject"], r["key"]))

with (OUT / "resumable-queue.jsonl").open("w", encoding="utf-8") as fh:
    for i, r in enumerate(ordered, 1):
        fh.write(json.dumps({"seq": i, **r}, ensure_ascii=False) + "\n")

with (OUT / "blocked-queue.jsonl").open("w", encoding="utf-8") as fh:
    for r in blocked_ordered:
        fh.write(json.dumps(r, ensure_ascii=False) + "\n")

# 停止点在队列中的位置
stop_key = ck.get("current_paper")
stop_pos = next((i for i, r in enumerate(ordered, 1) if r["key"] == stop_key), None)
if stop_pos is None:
    stop_pos = next((i for i, r in enumerate(blocked_ordered, 1)
                     if r["key"] == stop_key), None)
    stop_in = "blocked" if stop_pos else None
else:
    stop_in = "resumable"

queue_summary = {
    "generated_at": now,
    "papers_total": len(rows),
    "terminal_done": len(done_rows),
    "terminal_done_by_mirror_stage": dict(collections.Counter(
        r["stage"] for r in done_rows)),
    "terminal_done_cleaned_logged": sum(1 for r in done_rows if r["cleaned_logged"]),
    "live_total": len(live_rows),
    "selectable_total": len(ordered),
    "selectable_by_kind": dict(collections.Counter(r["kind"] for r in ordered)),
    "selectable_by_stage": dict(collections.Counter(r["stage"] for r in ordered)),
    "selectable_subjects": len({r["subject"] for r in ordered}),
    "blocked_total": len(blocked_ordered),
    "blocked_by_stage": dict(collections.Counter(r["stage"] for r in blocked_ordered)),
    "blocked_by_kind": dict(collections.Counter(r["kind"] for r in blocked_ordered)),
    "blocked_by_subject": dict(collections.Counter(r["subject"] for r in blocked_ordered)),
    "selectable_by_subject": dict(sorted(collections.Counter(
        r["subject"] for r in ordered).items(), key=lambda kv: (-kv[1], kv[0]))),
    "subjects_with_papers": len({r["subject"] for r in rows}),
    "subjects_fully_done": sorted({r["subject"] for r in done_rows} -
                                  {r["subject"] for r in live_rows}),
    "ms_only_in_selectable": sum(1 for r in ordered if r["kind"] == "ms_only"),
    "ms_only_in_blocked": sum(1 for r in blocked_ordered if r["kind"] == "ms_only"),
    "ms_only_note": "pick_queue 默认不选 ms_only（无 QP 不处理）；此处单列以免被吞掉。",
    "stage_mismatch_count": len(stage_mismatch),
    "stage_mismatch": stage_mismatch[:50],
    "stage_mismatch_note": "work/state.json 镜像阶段与 papers.json 阶段不一致；"
                           "pick_queue 以镜像为准，因此镜像陈旧会把卷误判为已终态。",
    "stop_key": stop_key,
    "stop_present_in": stop_in,
    "stop_seq": stop_pos,
    "stop_detail": {
        "key": stop_key,
        "mirror_stage": (state.get(stop_key) or {}).get("stage") if stop_key else None,
        "paper_stage": (papers.get(stop_key) or {}).get("stage") if stop_key else None,
        "cleaned_logged": stop_key in cleaned if stop_key else None,
        "in_selectable": stop_in == "resumable",
        "in_blocked": stop_in == "blocked",
    },
    "stop_note": (f"checkpoint 停于 {stop_key}（papers.json 记为 download_failed，"
                  "但 work/state.json 镜像仍是 2026-10-01 的 cleaned，"
                  "故按镜像口径不在待处理队列里）；联网未获授权，本轮不发起该卷 fetch。"
                  if stop_key else None),
    "first_three": [r["key"] for r in ordered[:3]],
}
(OUT / "resumable-queue-summary.json").write_text(
    json.dumps(queue_summary, ensure_ascii=False, indent=2), encoding="utf-8")

# ---------------------------------------------------------------- 来源缺口
su = summary.get("subject_universe") or {}
cov = summary.get("subject_coverage") or {}
subjects_doc = B.read_json(B.SUBJECTS, {}) or {}
listed = set(cov.get("third_party_declared_with_index") or []) | \
    set(cov.get("third_party_declared_without_index") or [])
official_only = list(subjects_doc.get("official_only") or [])

cells_by_subject = collections.defaultdict(list)
for cell in grid.values():
    if isinstance(cell, dict):
        cells_by_subject[cell.get("subject")].append(cell)

def cell_summary(code):
    cs = cells_by_subject.get(code, [])
    return {
        "cells": len(cs),
        "status_counts": dict(collections.Counter(c.get("status") for c in cs)),
        "requested_true": sum(1 for c in cs if c.get("requested")),
        "evidence_refs": sorted({c.get("evidence_ref") for c in cs if c.get("evidence_ref")}),
    }

unlisted = []
for code in sorted(official_only):
    info = cell_summary(code)
    unlisted.append({"subject": code, "listed_by_third_party": False, **info,
                     "gap": "来源未取得证据：第三方目录未列出该科，未请求其目录格，"
                            "不得换官方或其他镜像冒充同一原件。"})

declared_no_index = sorted(cov.get("third_party_declared_without_index") or [])
source_gaps = {
    "generated_at": now,
    "policy": "来源没有资源属于未取得证据；不换源、不重试、不用 --force 绕过。",
    "subject_universe": {
        "union_codes": su.get("union_codes"),
        "third_party_listed": len(listed),
        "official_only": len(official_only),
        "third_party_completeness": su.get("third_party_completeness"),
    },
    "catalogue_cells": summary.get("catalogue_cells"),
    "unlisted_subjects_count": len(unlisted),
    "unlisted_subjects": unlisted,
    "third_party_listed_without_index_count": len(declared_no_index),
    "third_party_listed_without_index": declared_no_index,
    "unresolved_papers_not_cleaned": (summary.get("unresolved") or {}).get("papers_not_cleaned"),
}
(OUT / "source-gaps.json").write_text(
    json.dumps(source_gaps, ensure_ascii=False, indent=2), encoding="utf-8")

# ---------------------------------------------------------------- 服务冲突
conflicts = []
for e in entries:
    if e.get("comparison") != "different":
        continue
    cf = e.get("changed_fields") or {}
    order = [k for k in ("text", "ms", "qp", "notes") if k in cf] + \
            [k for k in cf if k not in ("text", "ms", "qp", "notes")]
    v = e.get("verification") or {}
    conflicts.append({
        "key": e["key"],
        "changed_questions": e.get("changed_questions") or [],
        "changed_fields": {k: cf[k] for k in order},
        "local_index": e.get("local_index"),
        "local_index_sha256": e.get("index_sha256"),
        "service_index": e.get("service_index_path"),
        "missing_region_records": v.get("missing", 0),
        "visual_evidence_missing": v.get("visual_evidence_missing", 0),
        "verdict": "本地版正确（MS 文本层与原件逐字吻合；服务版 text 为 OCR 噪声）",
        "verdict_evidence": "work/coordinate-audit-2026-10-05/0472-2026-Jun-41-服务冲突判定.md",
        "resolution_state": "未修复：需目视定界 QP Q2（本地 y1=530.0 vs 服务 748.4）后重导入，"
                            "不得覆盖服务文件消除 different",
    })
(OUT / "service-conflicts.json").write_text(
    json.dumps({"generated_at": now, "count": len(conflicts), "conflicts": conflicts},
               ensure_ascii=False, indent=2), encoding="utf-8")

# ---------------------------------------------------------------- 重核验工作清单
reverify_entries = []
for e in entries:
    v = e.get("verification") or {}
    reasons = []
    if not e.get("visual_gate_passed"):
        reasons.append("视觉 gate 未通过")
    if v.get("missing", 0):
        reasons.append(f"{v['missing']} 个区域无核验记录")
    if v.get("visual_evidence_missing", 0):
        reasons.append(f"{v['visual_evidence_missing']} 个区域缺完整视觉证据")
    if e.get("comparison") == "different":
        reasons.append("本地/服务索引不一致")
    if e.get("uncertain", 0):
        reasons.append(f"{e['uncertain']} 条 uncertain")
    if e.get("missing_ms", 0):
        reasons.append(f"{e['missing_ms']} 条空 MS")
    if not reasons:
        continue
    reverify_entries.append({
        "key": e["key"], "reasons": reasons, "index_sha256": e.get("index_sha256"),
        "verification": v, "comparison": e.get("comparison"),
    })

unres = summary.get("unresolved") or {}
cleaned_reverify = list(unres.get("cleaned_needing_reverification") or [])
reverify = {
    "generated_at": now,
    "note": "有永久索引但未通过当前验收门槛的卷；需逐区域目视核验后追加绑定当前 index_sha256 "
            "的新记录，不得自动补 true。",
    "entries_count": len(reverify_entries),
    "entries": reverify_entries,
    "cleaned_needing_reverification_count": len(cleaned_reverify),
    "cleaned_needing_reverification": cleaned_reverify,
    "stage_mismatch": stage_mismatch,
    "service_conflicts": [c["key"] for c in conflicts],
}
(OUT / "reverify-queue.json").write_text(
    json.dumps(reverify, ensure_ascii=False, indent=2), encoding="utf-8")

# ---------------------------------------------------------------- stats
by_subject = collections.Counter(v.get("subject") for v in papers.values())
indexed_by_subject = collections.Counter(r.get("subject") for r in entries)
gate_by_subject = collections.Counter(r.get("subject") for r in entries
                                      if r.get("visual_gate_passed"))

num_problems = [{"key": e["key"], "problem": pr}
                for e in entries for pr in (e.get("verification_problems") or [])
                if "题号" in pr]
empty_ms = [{"key": e["key"], "missing_ms": e.get("missing_ms"),
             "questions": e.get("questions")} for e in entries if e.get("missing_ms")]

stats = {
    "generated_at": now,
    "provenance": "本次实测：全部字段由 papers.json/work/state.json/cleanup.jsonl/"
                  "summary.json/checkpoint.json/catalogue-grid.json/索引文件与 evidence.json 重算",
    "sources_unchanged": evidence.get("sources_unchanged"),
    "checked_at": evidence.get("checked_at"),
    "papers_total": evidence.get("papers_total"),
    "kind_counts": evidence.get("kind_counts"),
    "qp_file_entries": sum(len(v.get("qp") or []) for v in papers.values()),
    "ms_file_entries": sum(len(v.get("ms") or []) for v in papers.values()),
    "indexes": {
        "count": len(entries),
        "subjects": len(indexed_by_subject),
        "pct_of_papers": round(100.0 * len(entries) / max(1, evidence.get("papers_total") or 1), 4),
    },
    "missing_indexes": evidence.get("missing_indexes"),
    "stage_counts": stage_counts,
    "question_records": counts.get("questions"),
    "qp_regions": counts.get("qp_regions"),
    "ms_regions": counts.get("ms_regions"),
    "missing_qp": counts.get("missing_qp"),
    "missing_ms": counts.get("missing_ms"),
    "uncertain": counts.get("uncertain"),
    "schema_invalid_indexes": evidence.get("schema_invalid_indexes"),
    "basic_bbox_invalid_indexes": evidence.get("basic_bbox_invalid_indexes"),
    "service": {
        "service_index_dir": svc.get("service_index_dir"),
        "in_service": svc.get("in_service"),
        "count": svc.get("count"),
        "comparison_counts": svc.get("comparison_counts"),
        "conflicts": len(conflicts),
    },
    "verification": {
        "gate_passed": sum(1 for e in entries if e.get("visual_gate_passed")),
        "gate_failed": sum(1 for e in entries if not e.get("visual_gate_passed")),
        "missing": sum((e.get("verification") or {}).get("missing", 0) for e in entries),
        "visual_evidence_missing": sum(
            (e.get("verification") or {}).get("visual_evidence_missing", 0) for e in entries),
        "self_declared_unverified": sum(
            (e.get("verification") or {}).get("self_declared_unverified", 0) for e in entries),
    },
    "numbering_problems": num_problems,
    "empty_ms_by_paper": empty_ms,
    "queue": {
        "live_total": queue_summary["live_total"],
        "selectable_total": queue_summary["selectable_total"],
        "selectable_by_kind": queue_summary["selectable_by_kind"],
        "blocked_total": queue_summary["blocked_total"],
        "blocked_by_stage": queue_summary["blocked_by_stage"],
        "subjects_in_selectable": queue_summary["selectable_subjects"],
        "subjects_with_papers": queue_summary["subjects_with_papers"],
        "subjects_fully_done": queue_summary["subjects_fully_done"],
        "ms_only_selectable": queue_summary["ms_only_in_selectable"],
        "ms_only_blocked": queue_summary["ms_only_in_blocked"],
        "stage_mismatch_count": queue_summary["stage_mismatch_count"],
    },
    "checkpoint": {
        "current_paper": ck.get("current_paper"),
        "stopped_at": ck.get("stopped_at"),
        "stop_detail": ck.get("stop_detail"),
        "stop_diagnosis": ck.get("stop_diagnosis"),
        "needs_user_resume": ck.get("needs_user_resume"),
        "network_resume": ck.get("network_resume"),
    },
    "subject_universe": su,
    "catalogue_cells": summary.get("catalogue_cells"),
    "subject_coverage": cov,
    "cleanup": summary.get("cleanup"),
    "unresolved": summary.get("unresolved"),
    "storage": summary.get("storage"),
    "source_gaps": {
        "unlisted_subjects": source_gaps["unlisted_subjects_count"],
        "third_party_listed_without_index": source_gaps[
            "third_party_listed_without_index_count"],
    },
    "reverify": {
        "entries_count": len(reverify_entries),
        "cleaned_needing_reverification": len(cleaned_reverify),
        "stage_mismatch": len(stage_mismatch),
        "service_conflicts": len(conflicts),
    },
    "per_subject": {s: {"papers": by_subject[s], "indexes": indexed_by_subject[s],
                        "gate_passed": gate_by_subject[s]}
                    for s in sorted(by_subject)},
    "not_run": [
        "未访问上游；未下载/重试任何卷。",
        "未逐区域目视裁剪图（本会话模型无图像输入），因此未生成视觉验收记录。",
        "未调用实时 API 回读；服务比较为指定数据目录的磁盘文件比较。",
        "未导入、未清理、未修改任何批次原始状态文件。",
    ],
}
(OUT / "stats.json").write_text(json.dumps(stats, ensure_ascii=False, indent=2),
                                encoding="utf-8")

# ---------------------------------------------------------------- 自检
report = {
    "generated_at": now,
    "files": sorted(p.name for p in OUT.iterdir()),
    "queue_selectable": len(ordered),
    "queue_blocked": len(blocked_ordered),
    "live_total": len(live_rows),
    "live_check": len(ordered) + len(blocked_ordered) == len(live_rows),
    "unlisted_subjects": len(unlisted),
    "conflicts": len(conflicts),
    "reverify_entries": len(reverify_entries),
    "cleaned_needing_reverification": len(cleaned_reverify),
    "stage_mismatch": len(stage_mismatch),
    "first_queue_key": ordered[0]["key"] if ordered else None,
    "stop_key": stop_key,
    "stop_seq": stop_pos,
}
print(json.dumps(report, ensure_ascii=False, indent=2))
