"""按状态计算真实统计，写入 summary.json。

统计口径严格区分：
- 实际请求过的格（requested=true）与仅为推断、从未请求的格
- 业务拒绝（subject_unavailable）与 HTTP/未知响应失败
- 已完成卷与仅发现身份的卷
不含任何 PDF/图片二进制，只读状态文件。
"""
from __future__ import annotations

import io
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import batchlib as B
from service_audit import build_manifest

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

STAGES = ["discovered", "downloading", "downloaded", "parsing_qp", "parsing_ms",
          "verifying_local", "validation_partial", "imported_verified",
          "cleanup_pending", "cleaned", "download_failed", "import_failed",
          "blocked", "conflict"]

REQUESTED_CELL_STATUS = {"complete", "no_resources", "subject_unavailable",
                         "catalogue_incomplete", "http_error", "invalid_json",
                         "invalid_shape", "unknown_business_response"}
FAILED_CELL_STATUS = {"catalogue_incomplete", "http_error", "invalid_json",
                      "invalid_shape", "unknown_business_response"}


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out = []
    for line in path.read_bytes().decode("utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            out.append({"unparsed": line[:200]})
    return out


def build() -> dict:
    subjects = B.read_json(B.SUBJECTS, {}) or {}
    grid = B.read_json(B.GRID, {}) or {}
    papers = B.read_json(B.PAPERS, {}) or {}
    checkpoint = B.read_json(B.CHECKPOINT, {}) or {}
    errors = read_jsonl(B.ERRORS)
    verification = read_jsonl(B.VERIFICATION)
    cleanup = read_jsonl(B.CLEANUP)

    raw_subjects = subjects.get("subjects", []) or []
    if isinstance(raw_subjects, dict):
        subj_recs = raw_subjects
    else:
        subj_recs = {r.get("code"): r for r in raw_subjects}

    cell_status = Counter(v.get("status") for v in grid.values())
    requested_cells = [k for k, v in grid.items() if v.get("requested")]
    inferred_cells = [k for k, v in grid.items()
                      if not v.get("requested") and v.get("status") == "subject_unavailable_inferred"]
    failed_cells = sorted(k for k, v in grid.items() if v.get("status") in FAILED_CELL_STATUS)

    total_expected = 0
    for rec in subj_recs.values():
        total_expected += rec.get("cells_total") or 0
    unqueried = total_expected - len(requested_cells) - len(inferred_cells)

    stage_counts = Counter(v.get("stage") for v in papers.values())
    kind_counts = Counter(v.get("kind") for v in papers.values())
    by_subject = defaultdict(Counter)
    for key, rec in papers.items():
        by_subject[key.split("/")[0]][rec.get("stage")] += 1

    subj_status = Counter(r.get("status") for r in subj_recs.values())

    verified_pairs = set()
    verified_issues = 0
    for rec in verification:
        key = rec.get("paper") or rec.get("key")
        if key:
            verified_pairs.add((key, rec.get("question"), rec.get("role")))
        if rec.get("issues"):
            verified_issues += 1

    def _stage(r: dict) -> str:
        return r.get("stage") or r.get("kind") or ""

    cleanup_ok = [r for r in cleanup if _stage(r) == "cleaned"]
    cleanup_pending = [r for r in cleanup if _stage(r) == "cleanup_pending"]
    cleanup_failed = [r for r in cleanup if _stage(r) == "cleanup_failed"]
    # 除 cleaned/cleanup_pending/cleanup_failed 外的记录都是额外清扫（scratch/image/
    # debug/work/test 等 stage），通用归类，避免新增 sweep 阶段被漏计。
    sweep_records = [r for r in cleanup if _stage(r) and _stage(r) not in
                     ("cleaned", "cleanup_pending", "cleanup_failed")]
    freed_bytes = sum(r.get("freed_bytes", 0) or 0 for r in cleanup_ok)
    # `cleaned` 记录的 `deleted` 多数是整数计数，路径明细在同 key 的
    # `cleanup_pending.targets` 里；但 work_probe_images_cleanup 这类附带记录直接给
    # [{path, bytes}] 列表。两种形状都要能计数并取路径，不能假定只有整数。
    def _deleted_count(r: dict) -> int:
        d = r.get("deleted")
        if isinstance(d, list):
            return len(d)
        return int(d or 0)

    def _deleted_paths(r: dict) -> list:
        d = r.get("deleted")
        if isinstance(d, list):
            out = []
            for item in d:
                if isinstance(item, dict) and item.get("path"):
                    out.append(str(item["path"]))
                elif isinstance(item, str):
                    out.append(item)
            return out
        return [str(p) for p in pending_targets.get(r.get("key", ""), [])]

    pending_targets: dict[str, list] = {}
    for r in cleanup_pending:
        pending_targets.setdefault(r.get("key", ""), []).extend(r.get("targets") or [])
    deleted_files = sum(_deleted_count(r) for r in cleanup_ok)
    deleted_paths = {p for r in cleanup_ok for p in _deleted_paths(r)}
    pdf_deleted = sum(1 for p in deleted_paths if p.lower().endswith(".pdf"))
    img_deleted = sum(1 for p in deleted_paths if p.lower().endswith(".png"))

    indexes = sorted(B.INDEXES.rglob("cie-index.json"))
    index_bytes = sum(p.stat().st_size for p in indexes)

    tmp_bytes = B.dir_bytes(B.TMP)
    tmp_pdfs = sorted(str(p) for p in B.TMP.rglob("*.pdf"))
    tmp_pngs = sorted(str(p) for p in B.TMP.rglob("*.png"))
    tmp_parts = sorted(str(p) for p in B.TMP.rglob("*.part"))

    unresolved_subjects = sorted(
        code for code, rec in subj_recs.items()
        if rec.get("status") not in ("subject_unavailable", "scanned"))
    unresolved_papers = sorted(
        k for k, v in papers.items()
        if v.get("stage") not in ("cleaned",))

    # 学科覆盖：有索引 / 无索引，以及第三方声明科目里还没产出索引的部分。
    # 只读 indexes/ 与 papers.json，不含任何二进制。
    indexed_subjects = sorted({p.relative_to(B.INDEXES).parts[0] for p in indexes})
    papers_subjects = sorted({k.split("/")[0] for k in papers})
    declared = sorted(code for code, rec in subj_recs.items()
                      if rec.get("third_party_confirmed"))
    subject_coverage = {
        "union_codes": len(subj_recs),
        "subjects_with_papers": len(papers_subjects),
        "subjects_with_index": len(indexed_subjects),
        "subjects_without_index": len(set(subj_recs) - set(indexed_subjects)),
        "indexed_subjects": indexed_subjects,
        "third_party_declared": len(declared),
        "third_party_declared_with_index": sorted(set(declared) & set(indexed_subjects)),
        "third_party_declared_without_index": sorted(set(declared) - set(indexed_subjects)),
    }

    manifest_path = Path(B.BATCH_ROOT) / "service-index-manifest.json"
    manifest = build_manifest()
    B.atomic_write_json(manifest_path, manifest)
    subject_coverage["service_index_manifest"] = manifest_path.name
    service_index = {
        "manifest": str(manifest_path),
        "generated_at": manifest.get("generated_at"),
        "disk_index_files": manifest.get("count"),
        "in_service": manifest.get("in_service"),
        "not_in_service": manifest.get("not_in_service"),
        "comparison_counts": manifest.get("comparison_counts"),
        "visual_gate_passed": manifest.get("visual_gate_passed"),
        "entries": [
            {"key": r.get("key"), "qp_sha256": r.get("qp_sha256"),
             "in_service": r.get("service_index_exists"),
             "comparison": r.get("comparison"),
             "visual_gate_passed": r.get("visual_gate_passed"),
             "service_index_path": r.get("service_index_path")}
            for r in (manifest.get("entries") or [])
        ],
    }

    return {
        "generated_at": B.now_iso(),
        "source": B.SOURCE,
        "subject_universe": {
            "union_codes": len(subj_recs),
            # third_party_catalogue 是描述性 dict（url/method/fetched_at/sha256/entries/codes），
            # 早期写 len(dict) 得到 7（键数），不是第三方科目数。真正的科目数在 codes。
            "third_party_listed": (subjects.get("third_party_catalogue") or {}).get("codes", 0),
            "third_party_entries": (subjects.get("third_party_catalogue") or {}).get("entries", 0),
            "third_party_only": len(subjects.get("third_party_only") or []),
            "official_only": len(subjects.get("official_only") or []),
            "third_party_completeness": subjects.get("third_party_completeness"),
            "status_counts": dict(subj_status),
            "not_fully_scanned": unresolved_subjects,
        },
        "catalogue_cells": {
            "expected_total": total_expected,
            "actually_requested": len(requested_cells),
            "inferred_not_requested": len(inferred_cells),
            "unqueried": max(unqueried, 0),
            "status_counts": dict(cell_status),
            "complete": cell_status.get("complete", 0),
            "no_resources": cell_status.get("no_resources", 0),
            "business_rejected_subject_unavailable": cell_status.get("subject_unavailable", 0),
            "failed": len(failed_cells),
            "failed_cells": failed_cells[:200],
        },
        "papers": {
            "total_discovered": len(papers),
            "kind_counts": dict(kind_counts),
            "stage_counts": dict(stage_counts),
            "by_subject": {s: dict(c) for s, c in sorted(by_subject.items())},
        },
        "subject_coverage": subject_coverage,
        "service_index": service_index,
        "pipeline": {
            "local_visual_verified": sum(1 for r in manifest["entries"]
                                         if r["visual_gate_passed"]),
            "downloaded": sum(1 for v in papers.values() if v.get("stage") in
                              ("downloaded", "parsing_qp", "parsing_ms", "verifying_local",
                               "validation_partial", "imported_verified", "cleanup_pending", "cleaned")),
            "fully_verified": sum(1 for r in manifest["entries"]
                                  if r["visual_gate_passed"] and r["comparison"] == "identical"
                                  and papers.get(r["key"], {}).get("readback_verified") is True),
            "historical_verified_stage": sum(1 for v in papers.values() if v.get("stage") in
                                             ("imported_verified", "cleanup_pending", "cleaned")),
            "cleaned_needing_reverification": sum(1 for r in manifest["entries"]
                if papers.get(r["key"], {}).get("stage") == "cleaned" and not r["visual_gate_passed"]),
            "imported_verified": stage_counts.get("imported_verified", 0),
            "cleaned": stage_counts.get("cleaned", 0),
            "validation_partial": stage_counts.get("validation_partial", 0),
            "conflict": stage_counts.get("conflict", 0),
            "blocked": stage_counts.get("blocked", 0),
            "verification_records": len(verification),
            "verification_questions_covered": len({(k, q) for k, q, _ in verified_pairs if k}),
            "verification_records_with_issues": verified_issues,
        },
        "cleanup": {
            "cleaned_papers": len({r.get("key") for r in cleanup_ok if r.get("key")}),
            "cleaned_records": len(cleanup_ok),
            "pending_records": len(cleanup_pending),
            "pending": sum(1 for r in papers.values() if r.get("stage") == "cleanup_pending"),
            "failed": sum(1 for r in papers.values() if r.get("stage") == "cleanup_failed"),
            "failed_records": len(cleanup_failed),
            "deleted_files": deleted_files,
            "deleted_pdfs": pdf_deleted,
            "deleted_images": img_deleted,
            "freed_bytes": freed_bytes,
            "freed_mb": round(freed_bytes / 1048576, 2),
            "sweeps": {
                "records": len(sweep_records),
                "files": sum(int(r.get("deleted") or 0) for r in sweep_records),
                "freed_bytes": sum(int(r.get("freed_bytes") or 0) for r in sweep_records),
                "by_stage": dict(Counter(_stage(r) for r in sweep_records)),
            },
            "total_freed_bytes": freed_bytes + sum(int(r.get("freed_bytes") or 0)
                                                   for r in sweep_records),
        },
        "storage": {
            "index_files": len(indexes),
            "index_bytes": index_bytes,
            "index_mb": round(index_bytes / 1048576, 3),
            "tmp_bytes": tmp_bytes,
            "tmp_mb": round(tmp_bytes / 1048576, 2),
            "tmp_pdf_count": len(tmp_pdfs),
            "tmp_png_count": len(tmp_pngs),
            "tmp_part_count": len(tmp_parts),
            "tmp_residue": (tmp_pdfs + tmp_pngs + tmp_parts)[:300],
        },
        "errors": {
            "total_records": len(errors),
            "kinds": dict(Counter(r.get("kind") or r.get("stage") or "unclassified" for r in errors)),
            "download_errors": sum(1 for r in errors if (r.get("kind") or r.get("stage"))
                                    in ("download_error", "download_failed", "download_exception")),
        },
        "checkpoint": {
            "current_cell": checkpoint.get("current_cell"),
            "current_paper": checkpoint.get("current_paper"),
            "stage": checkpoint.get("stage"),
            "stop_reason": checkpoint.get("stop_reason"),
            "updated_at": checkpoint.get("updated_at"),
        },
        "unresolved": {
            "papers_not_cleaned": len(unresolved_papers),
            "papers_not_cleaned_sample": unresolved_papers[:200],
            "cleaned_needing_reverification": [r["key"] for r in manifest["entries"]
                if papers.get(r["key"], {}).get("stage") == "cleaned" and not r["visual_gate_passed"]],
            "service_conflicts": [r["key"] for r in manifest["entries"]
                                  if r["comparison"] == "different"],
            "needs_user_resume": checkpoint.get("needs_user_resume", False),
        },
    }


def main() -> int:
    payload = build()
    B.atomic_write_json(B.SUMMARY, payload)
    print(json.dumps({
        "written": str(B.SUMMARY),
        "cells": payload["catalogue_cells"],
        "papers_total": payload["papers"]["total_discovered"],
        "stage_counts": payload["papers"]["stage_counts"],
        "cleanup": payload["cleanup"],
        "storage": {k: v for k, v in payload["storage"].items() if k != "tmp_residue"},
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
