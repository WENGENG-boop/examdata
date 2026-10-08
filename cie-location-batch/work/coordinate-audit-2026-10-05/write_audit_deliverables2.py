"""生成空 MS 分类、逐卷未完成清单、清理记录、可恢复 checkpoint（纯离线）。

全部由当前索引 JSON、papers.json、cleanup.jsonl、summary.json、checkpoint.json 计算。
结构可判定的给类别；需要 MS 原件才能定论的显式标 needs_original_evidence / 待核对，
不臆造理由，不填整页框。
"""
from __future__ import annotations

import collections
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

HERE = Path(__file__).parent
BATCH = HERE.parents[1]
sys.path.insert(0, str(BATCH / "tools"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import batchlib as B  # noqa: E402

OUT = HERE / "deliverables"
OUT.mkdir(exist_ok=True)
CST = timezone(timedelta(hours=8))
now = datetime.now(CST).isoformat(timespec="seconds")

papers = B.read_json(B.PAPERS, {}) or {}
summary = B.read_json(B.SUMMARY, {}) or {}
ck = B.read_json(B.CHECKPOINT, {}) or {}
state = B.read_json(B.WORK / "state.json", {}) or {}
evidence = B.read_json(HERE / "evidence.json", {}) or {}
entries = evidence.get("entries") or []


def load_index(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return {"_error": str(exc)}


def subtree(qid, children):
    out, stack = [], [qid]
    while stack:
        cur = stack.pop()
        for ch in children.get(cur, []):
            out.append(ch)
            stack.append(ch)
    return out


# ------------------------------------------------------- 空 MS 分类
empty_ms_records = []
class_counts = collections.Counter()
for e in entries:
    key = e["key"]
    idx = load_index(e["local_index"])
    if "_error" in idx:
        continue
    qs = {q["question"]: q for q in idx.get("questions") or []}
    children = collections.defaultdict(list)
    for q in idx.get("questions") or []:
        if q.get("parent"):
            children[q["parent"]].append(q["question"])

    # 各祖先链上的 ms 页
    def ancestor_ms_pages(qid):
        pages = []
        cur = qs.get(qid, {}).get("parent")
        seen = set()
        while cur and cur not in seen:
            seen.add(cur)
            pages += [r["page"] for r in (qs.get(cur, {}).get("ms") or [])]
            cur = qs.get(cur, {}).get("parent")
        return pages

    for q in idx.get("questions") or []:
        if q.get("ms"):
            continue
        qid = q["question"]
        desc = subtree(qid, children)
        desc_ms = sum(len(qs[d].get("ms") or []) for d in desc)
        sib_ms = 0
        parent = q.get("parent")
        if parent:
            for sib in children.get(parent, []):
                if sib != qid:
                    sib_ms += len(qs[sib].get("ms") or [])
        anc_pages = ancestor_ms_pages(qid)
        paper_ms_regions = sum(len(x.get("ms") or []) for x in idx["questions"])

        if paper_ms_regions == 0:
            cat = "整卷无MS区域"
            reason = ("该卷索引无任何 MS 区域（MS 文档摘要存在）；写作/口语卷的评分常为"
                      "通用评分表，需 MS 原件判定是通用评分标准、来源缺失还是解析遗漏")
            needs = True
        elif desc_ms > 0:
            cat = "父题聚合"
            reason = (f"该题是父题，MS 定位在其 {len(desc)} 个子题上"
                      f"（子题 MS 区域合计 {desc_ms}）")
            needs = False
        elif sib_ms > 0:
            cat = "共用评分区域"
            reason = (f"同父兄弟题共 {sib_ms} 个 MS 区域；本子题无独立 MS，"
                      "疑与兄弟共用评分区域")
            needs = True
        elif anc_pages:
            cat = "父题聚合"
            reason = f"MS 定位在祖先题上（MS 页码 {sorted(set(anc_pages))}）"
            needs = True
        else:
            cat = "待核对"
            reason = ("该题及其整支子树均无 MS 区域；需 MS 原件判定是"
                      "真实无独立评分、解析遗漏还是来源缺失")
            needs = True

        class_counts[cat] += 1
        empty_ms_records.append({
            "key": key, "question": qid, "parent": parent,
            "category": cat, "reason": reason,
            "needs_original_evidence": needs,
            "paper_ms_regions": paper_ms_regions,
            "qp_pages": sorted({r["page"] for r in q.get("qp") or []}),
            "ms_pages_in_subtree": sorted({r["page"] for d in desc
                                           for r in (qs[d].get("ms") or [])}),
            "ancestor_ms_pages": sorted(set(anc_pages)),
            "uncertain": bool(q.get("uncertain")),
            "index_sha256": e.get("index_sha256"),
            "source": "本次实测（由当前索引 JSON 结构判定）",
        })

empty_ms_doc = {
    "generated_at": now,
    "total": len(empty_ms_records),
    "by_category": dict(class_counts),
    "needs_original_evidence": sum(1 for r in empty_ms_records
                                   if r["needs_original_evidence"]),
    "schema_note": "cie-index-schema.json 的 Question 无理由字段，故理由与证据写入本旁侧日志。",
    "evidence_note": "结构类别为本次实测；标 needs_original_evidence 的必须在 MS 原件上"
                     "逐页确认后才能定论，当前未做（无图像输入 / 原件多已清理）。",
    "ms_originals_available_locally": sorted(
        {r["key"] for r in empty_ms_records
         if (papers.get(r["key"]) or {}).get("tmp_dir")
         and list(Path(papers[r["key"]]["tmp_dir"]).glob("**/*.pdf"))}),
    "ms_originals_available_note": "仅当 tmp 目录内实际存在 PDF 原件才算可用；"
                                   "目录残留 crops/pages PNG 不算。",
    "papers_with_zero_ms_regions": sorted(
        {r["key"] for r in empty_ms_records if r["paper_ms_regions"] == 0}),
    "records": empty_ms_records,
}
(OUT / "empty-ms-classification.json").write_text(
    json.dumps(empty_ms_doc, ensure_ascii=False, indent=2), encoding="utf-8")

# ------------------------------------------------------- 逐卷未完成清单
index_by_key = {e["key"]: e for e in entries}
live_keys = set()
for key, entry in papers.items():
    if not isinstance(entry, dict):
        continue
    stage = (state.get(key) or {}).get("stage") or entry.get("stage") or "discovered"
    if stage in {"cleaned", "ambiguous", "imported_verified"}:
        continue
    live_keys.add(key)

with (OUT / "incomplete-per-paper.jsonl").open("w", encoding="utf-8") as fh:
    for key, entry in papers.items():
        if not isinstance(entry, dict):
            continue
        e = index_by_key.get(key)
        if e is None:
            fh.write(json.dumps({
                "key": key, "kind": entry.get("kind"), "subject": entry.get("subject"),
                "year": entry.get("year"), "season": entry.get("season"),
                "paper": entry.get("paper"),
                "state": "no_index",
                "unfinished": "全部：无永久索引，题目/子题/评分项均未建立定位",
                "source": "本次实测（papers 与实际 indexes 差集）",
            }, ensure_ascii=False) + "\n")
            continue
        idx = load_index(e["local_index"])
        gaps = []
        if not e.get("visual_gate_passed"):
            gaps.append("视觉 gate 未通过")
        v = e.get("verification") or {}
        if v.get("missing"):
            gaps.append(f"{v['missing']} 区域无核验记录")
        if v.get("visual_evidence_missing"):
            gaps.append(f"{v['visual_evidence_missing']} 区域缺完整视觉证据")
        if e.get("comparison") == "different":
            gaps.append("本地/服务索引不一致")
        if e.get("uncertain"):
            gaps.append(f"{e['uncertain']} 条 uncertain")
        if e.get("missing_ms"):
            gaps.append(f"{e['missing_ms']} 条空 MS")
        if not e.get("service_index_exists"):
            gaps.append("服务目录无对应索引文件")
        fh.write(json.dumps({
            "key": key, "kind": entry.get("kind"), "subject": entry.get("subject"),
            "year": entry.get("year"), "season": entry.get("season"),
            "paper": entry.get("paper"),
            "state": "indexed" if not gaps else "indexed_with_gaps",
            "questions_total": e.get("questions"),
            "questions_empty_ms": e.get("missing_ms"),
            "uncertain": e.get("uncertain"),
            "missing_qp": e.get("missing_qp"),
            "qp_regions": e.get("qp_regions"),
            "ms_regions": e.get("ms_regions"),
            "visual_gate_passed": e.get("visual_gate_passed"),
            "comparison": e.get("comparison"),
            "verification": v,
            "verification_problems": e.get("verification_problems"),
            "unfinished": gaps or ["已有索引且当前门槛通过；仍需逐区域目视复核"],
            "index_sha256": e.get("index_sha256"),
            "source": "本次实测",
        }, ensure_ascii=False) + "\n")

# ------------------------------------------------------- 清理记录
cleanup_rows = B.read_jsonl(B.CLEANUP)
cleanup_doc = {
    "generated_at": now,
    "log_path": str(B.CLEANUP),
    "log_records": len(cleanup_rows),
    "by_stage": dict(collections.Counter(r.get("stage") for r in cleanup_rows)),
    "cleaned_records": sum(1 for r in cleanup_rows if r.get("stage") == "cleaned"),
    "cleaned_unique_keys": len({r["key"] for r in cleanup_rows
                                if r.get("stage") == "cleaned" and r.get("key")}),
    "cleanup_pending_unique_keys": len({r["key"] for r in cleanup_rows
                                        if r.get("stage") == "cleanup_pending"
                                        and r.get("key")}),
    "summary_cleanup": summary.get("cleanup"),
    "deleted_originals_retained_policy":
        "仅按 cleanup_paper.py 门槛与白名单清理；未验收原件不删，不删其他工作流文件。",
    "source": "本次实测（读取 cleanup.jsonl + summary.cleanup）",
}
(OUT / "cleanup-records.json").write_text(
    json.dumps(cleanup_doc, ensure_ascii=False, indent=2), encoding="utf-8")

# ------------------------------------------------------- 可恢复 checkpoint
stop_key = ck.get("current_paper")
resume = {
    "generated_at": now,
    "checkpoint_path": str(B.CHECKPOINT),
    "current_paper": stop_key,
    "stopped_at": ck.get("stopped_at"),
    "stop_detail": ck.get("stop_detail"),
    "stop_diagnosis": ck.get("stop_diagnosis"),
    "stop_reason": ck.get("stop_reason"),
    "needs_user_resume": ck.get("needs_user_resume"),
    "resume_policy": ck.get("resume_policy"),
    "network_resume_history": ck.get("network_resume"),
    "totals": ck.get("totals"),
    "stage_of_stop_paper": {
        "mirror_stage": (state.get(stop_key) or {}).get("stage"),
        "paper_stage": (papers.get(stop_key) or {}).get("stage"),
    },
    "authorization_state": "本轮无会话内明确联网授权；未发起任何新上游请求。",
    "pending_authorization_requests": [
        {"action": "resume_fetch", "paper": stop_key, "role": "qp",
         "blocked_by": "HTTP 502（2026-10-05T16:30:15+0800），needs_user_resume=true"},
        {"action": "refetch_originals",
         "papers": ["8386/2025/Jun/11", "8386/2026/Jun/12", "8386/2026/Jun/13",
                    "0495/2026/Jun/11"],
         "reason": "原件已清理，题号核对/空 MS 定论需重取原件"},
        {"action": "refetch_originals",
         "papers": ["8238/2025/Jun/32", "8238/2025/Nov/31", "8238/2025/Nov/32",
                    "8238/2025/Nov/33", "8238/2026/Jun/32"],
         "reason": "索引 0 个 MS 区域，需 MS 原件判定是否通用评分表/解析遗漏"},
    ],
    "local_originals_present": sorted(
        k for k, v in papers.items()
        if isinstance(v, dict) and v.get("tmp_dir")
        and list(Path(v["tmp_dir"]).glob("**/*.pdf"))),
    "local_work_continues_without_network": [
        "可恢复队列与交付物生成",
        "已有索引的结构化核验（不生成视觉验收记录）",
        "0472/2026/Jun/41 冲突的离线证据整理",
    ],
}
(OUT / "resume-checkpoint.json").write_text(
    json.dumps(resume, ensure_ascii=False, indent=2), encoding="utf-8")

# ------------------------------------------------------- 交付物索引
q = B.read_json(OUT / "resumable-queue-summary.json", {}) or {}
svc = evidence.get("service") or {}
stats = B.read_json(OUT / "stats.json", {}) or {}
source_gaps = B.read_json(OUT / "source-gaps.json", {}) or {}
num_probs = stats.get("numbering_problems") or []
readme = f'''# CIE 全量坐标作业 · 交付物索引（{now}）

本目录由 `write_queue_deliverables.py` 与 `write_audit_deliverables2.py` 从当前批次状态
（papers.json / work/state.json / cleanup.jsonl / summary.json / checkpoint.json /
catalogue-grid.json / 63 份索引 / evidence.json）实际重算生成，未沿用旧报告数字，未访问上游。

## 文件

| 文件 | 内容 | 来源标注 |
|---|---|---|
| `stats.json` | 机器可读统计总表 | 本次实测 |
| `resumable-queue.jsonl` | 可恢复队列 {q.get("selectable_total")} 卷（规范顺序，首行=下一个应处理卷） | 本次实测 |
| `resumable-queue-summary.json` | 队列计数、阶段错配、停止点位置 | 本次实测 |
| `blocked-queue.jsonl` | 阶段被跳过、不自动重试的卷 | 本次实测 |
| `reverify-queue.json` | 有索引但未过门槛的卷 + 待重验清理卷 | 本次实测 |
| `empty-ms-classification.json` | 空 MS {empty_ms_doc["total"]} 条逐条分类与理由 | 本次实测（结构判定） |
| `incomplete-per-paper.jsonl` | 逐卷未完成清单（13877 卷） | 本次实测 |
| `source-gaps.json` | 来源缺口（未列出科目/无索引科目） | 本次实测 |
| `service-conflicts.json` | 本地/服务索引冲突 | 本次实测 |
| `cleanup-records.json` | 清理记录 | 本次实测 |
| `resume-checkpoint.json` | 可恢复 checkpoint 与待授权请求 | 本次实测 |

## 关键实测数字

- 发现卷 {q.get("papers_total")}；有永久索引 {stats.get("indexes", {}).get("count")} 卷（{stats.get("indexes", {}).get("pct_of_papers")}%）。
- 队列：可处理 {q.get("selectable_total")}（paired/qp_only {q.get("selectable_by_kind", {}).get("paired", 0)}/{q.get("selectable_by_kind", {}).get("qp_only", 0)}，ms_only {q.get("ms_only_in_selectable")}）；被跳过 {q.get("blocked_total")}。
- 阶段错配 {q.get("stage_mismatch_count")} 卷：work/state.json 镜像阶段与 papers.json 不一致，pick_queue 会因此漏选。
- 空 MS {empty_ms_doc["total"]} 条：{"、".join(f"{k} {v}" for k, v in empty_ms_doc["by_category"].items())}；需原件定论 {empty_ms_doc["needs_original_evidence"]} 条。
- 题号异常 {len(num_probs)} 条；uncertain {stats.get("uncertain")} 条；视觉 gate 通过 {stats.get("verification", {}).get("gate_passed")} / 未通过 {stats.get("verification", {}).get("gate_failed")}。
- 服务目录索引 {svc.get("in_service")}/{svc.get("count")} 存在；一致 {svc.get("comparison_counts", {}).get("identical")}，不一致 {svc.get("comparison_counts", {}).get("different")}。
- 来源缺口：未列出科目 {source_gaps["unlisted_subjects_count"]}；第三方列出但无索引 {source_gaps["third_party_listed_without_index_count"]}。

## 本次实测 / 历史记录 / not_run

- 本次实测：上表全部数字，以及空 MS 结构分类、队列构成、来源缺口、清理记录、checkpoint。
- 历史记录（仅作线索）：`../检查报告.md` 中的旧 PhaseD 数字、`pending-work.json`、旧最终报告。
- not_run（本轮未做，不得当成已完成）：
  - 未访问上游、未下载/重试任何卷。
  - 未逐区域目视裁剪图（本会话模型无图像输入），因此**未生成任何视觉验收记录**。
  - 未调用实时 API 回读；服务比较为指定数据目录的磁盘文件比较。
  - 未导入、未清理、未修改任何批次原始状态文件。
  - 空 MS 中 {empty_ms_doc["needs_original_evidence"]} 条需 MS 原件才能定论；本地唯一存有 PDF 原件的是 0472/2026/Jun/41（其无空 MS），其余空 MS 卷原件均已清理。
  - 5 卷索引完全无 MS 区域（{ "、".join(empty_ms_doc["papers_with_zero_ms_regions"]) }），需 MS 原件判定是否通用评分表或解析遗漏。

## 待授权（联网）请求

'''
for req in resume["pending_authorization_requests"]:
    readme += f'- `{req["action"]}`：{req.get("paper") or "、".join(req["papers"])} —— {req["reason"] if "reason" in req else req["blocked_by"]}\n'
readme += f'''
## 无法由本代理完成的部分（如实声明）

完成判据要求“逐区域实际裁剪目视核验”。本会话模型无图像输入能力（Read 图片报
missing image_in capability），无法产生视觉验收记录；因此**目标不可能由本代理达到 complete**。
在获得图像输入能力或人工目视前，只能交付上述离线成果，不能声称范围内卷已完成。
'''
(OUT / "README.md").write_text(readme, encoding="utf-8")

print(json.dumps({
    "empty_ms_total": len(empty_ms_records),
    "by_category": dict(class_counts),
    "needs_original_evidence": empty_ms_doc["needs_original_evidence"],
    "ms_originals_available_locally": empty_ms_doc["ms_originals_available_locally"],
    "papers_with_local_pdf": sorted(
        k for k, v in papers.items()
        if isinstance(v, dict) and v.get("tmp_dir")
        and list(Path(v["tmp_dir"]).glob("**/*.pdf"))),
    "cleanup_records": cleanup_doc["log_records"],
    "cleanup_by_stage": cleanup_doc["by_stage"],
    "resume_stop": stop_key,
}, ensure_ascii=False, indent=2))
