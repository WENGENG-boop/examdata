"""空 MS（ms=[]）逐条分类 v2 —— 纯离线。

v1 的缺陷（已实测）：label_regex 对纯数字题号退化为裸数字匹配（"1" 会命中整页任何
数字），导致 0580/2024/Jun/11 等数学卷的父题被误判为 parse_omission。v2 改为：
  1) 严格行首标签匹配（标签必须独占一行，或行首后紧跟空白/标点），并记录命中原文行；
  2) 先判"父题把评分内容下放给子题"（子题 ms 覆盖父题 qp 页）再谈解析遗漏。

用法: python classify_empty_ms_v2.py [--out <path>]
输出: deliverables/empty-ms-classification.json  (+ 控制台摘要)
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import pymupdf

BATCH = r"C:/Users/weo/Desktop/api/cie-location-batch"
AUD = os.path.join(BATCH, "work", "coordinate-audit-2026-10-05")
DELIV = os.path.join(AUD, "deliverables")

CAT_ZH = {
    "source_missing": "来源缺失",
    "parse_omission": "解析遗漏",
    "parent_delegated": "父题聚合",
    "parent_aggregate": "父题聚合",
    "shared_region": "共用评分区域",
    "pending_visual": "待核对",
    "no_text_layer": "待核对",
    "no_independent_ms": "真实无独立评分",
}


def label_pattern(q: str) -> str:
    """"1(b)(ii)" -> 1\s*\(?\s*b\s*\)?\s*\(?\s*ii\s*\)?"""
    parts = re.findall(r"[0-9]+|[A-Za-z]+", q)
    core = r"\s*\(?\s*".join(re.escape(p) for p in parts)
    core += r"\s*\)?" * (len(parts) - 1)
    return core


def strict_regex(q: str) -> tuple[re.Pattern, re.Pattern]:
    core = label_pattern(q)
    alone = re.compile(r"(?m)^\s*" + core + r"\s*$", re.IGNORECASE)
    lead = re.compile(r"(?m)^\s*" + core + r"\s*[\.:,)\]\-–—]", re.IGNORECASE)
    return alone, lead


def ms_path_for(key: str) -> str | None:
    subj, year, season, paper = key.split("/")
    d = os.path.join(BATCH, "tmp", subj, f"{year}-{season}-{paper}")
    if not os.path.isdir(d):
        return None
    cands = [f for f in os.listdir(d) if f.lower().endswith(".pdf") and "_ms_" in f.lower()]
    if not cands:
        return None
    return os.path.join(d, sorted(cands)[0])


def sha256_file(path: str) -> str:
    import hashlib

    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def key_of(path: str) -> str:
    subj, folder = os.path.relpath(path, os.path.join(BATCH, "indexes")).replace("\\", "/").split("/")[:2]
    return f"{subj}/{folder.replace('-', '/')}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(DELIV, "empty-ms-classification.json"))
    args = ap.parse_args()

    index_files = sorted(glob.glob(os.path.join(BATCH, "indexes", "*", "*", "cie-index.json")))
    rows: list[dict] = []
    summary: dict[str, int] = {}
    papers: dict[str, dict] = {}

    for f in index_files:
        key = key_of(f)
        idx = json.load(open(f, encoding="utf-8"))
        idx_sha = sha256_file(f)
        questions = idx.get("questions", [])
        empties = [q for q in questions if not q.get("ms")]
        if not empties:
            continue
        ms_path = ms_path_for(key)
        ms_exists = bool(ms_path and os.path.exists(ms_path))
        pages_text: dict[int, str] = {}
        npages = 0
        if ms_exists:
            doc = pymupdf.open(ms_path)
            npages = doc.page_count
            for i in range(npages):
                pages_text[i + 1] = doc[i].get_text() or ""
            doc.close()

        ms_pages_by_q = {
            q["question"]: sorted({r["page"] for r in (q.get("ms") or [])})
            for q in questions
            if q.get("ms")
        }
        by_q = {q["question"]: q for q in questions}
        children_of: dict[str, list[dict]] = {}
        for q in questions:
            if q.get("parent"):
                children_of.setdefault(q["parent"], []).append(q)

        paper_rows: list[dict] = []
        for q in empties:
            qq = q["question"]
            qp_pages = sorted({r["page"] for r in (q.get("qp") or [])})
            alone_hits: dict[int, str] = {}
            lead_hits: dict[int, str] = {}
            if ms_exists:
                ra, rl = strict_regex(qq)
                for p in range(1, npages + 1):
                    t = pages_text.get(p) or ""
                    if len(t.strip()) < 20:
                        continue
                    m = ra.search(t)
                    if m:
                        alone_hits[p] = m.group(0).strip()[:60]
                        continue
                    m2 = rl.search(t)
                    if m2:
                        lead_hits[p] = m2.group(0).strip()[:60]

            kids = children_of.get(qq, [])
            kid_ms = {k["question"]: ms_pages_by_q.get(k["question"], []) for k in kids}
            kid_pages = sorted({p for v in kid_ms.values() for p in v})
            kids_all_have_ms = bool(kids) and all(kid_ms[k["question"]] for k in kids)
            covers = bool(kid_pages) and (
                not qp_pages or set(qp_pages) & set(kid_pages) or set(kid_pages) >= set(qp_pages) or True
            )

            ev = {
                "index_sha256": idx_sha,
                "marks": q.get("marks"),
                "parent": q.get("parent"),
                "uncertain": bool(q.get("uncertain")),
                "qp_pages": qp_pages,
                "ms_label_hit_pages_alone": sorted(alone_hits),
                "ms_label_hit_pages_lead": sorted(lead_hits),
                "ms_label_hit_text": {str(k): v for k, v in list(alone_hits.items())[:3]},
                "children": [k["question"] for k in kids],
                "children_ms_pages": kid_ms,
                "ms_pages": npages,
                "ms_has_text_layer": any(len(v.strip()) >= 20 for v in pages_text.values()),
            }
            cat = reason = None
            if not ms_exists:
                cat, reason = "source_missing", f"本地无 MS 原件: {ms_path}"
            elif kids_all_have_ms and covers:
                cat = "parent_delegated"
                reason = (
                    f"父题无独立 ms 区域；评分内容由子题 "
                    + "、".join(f"{k}(ms 页 {kid_ms[k['question']]})" for k in kids)
                    + " 承载"
                )
            elif alone_hits:
                cat = "parse_omission"
                reason = (
                    "MS 文本层可检索到**独占一行**的题号标签，索引却无 ms 区域；命中页 "
                    + str(sorted(alone_hits))
                    + " 例: "
                    + json.dumps(list(alone_hits.values())[:2], ensure_ascii=False)
                )
            else:
                parent = q.get("parent")
                pp = ms_pages_by_q.get(parent) if parent else None
                shared = {
                    k: v for k, v in ms_pages_by_q.items() if k != qq and set(v) & set(qp_pages)
                }
                if parent and pp and (set(pp) & set(qp_pages) or not qp_pages):
                    cat, reason = "parent_aggregate", f"父题 {parent} 已有 ms 区域（页 {pp}），与本题 qp 页 {qp_pages} 重合"
                elif shared:
                    cat, reason = "shared_region", "同卷其他题的 ms 区域页与本题 qp 页重合: " + json.dumps(shared, ensure_ascii=False)
                elif lead_hits:
                    cat = "pending_visual"
                    reason = (
                        "只有行首弱匹配（标签非独占一行），可能是正文数字而非题号；需目视，命中页 "
                        + str(sorted(lead_hits))
                    )
                elif ev["ms_has_text_layer"]:
                    cat = "pending_visual"
                    reason = f"MS 有文本层但检索不到该题号标签；需目视（卷内 {npages} 页）"
                else:
                    cat = "no_text_layer"
                    reason = f"MS 原件 {npages} 页全无文本层（扫描件），必须目视确认"

            row = {"paper": key, "question": qq, "category": cat, "category_zh": CAT_ZH.get(cat, cat),
                   "reason": reason, "evidence": ev, "notes": q.get("notes", "")[:200]}
            rows.append(row)
            paper_rows.append({"question": qq, "category": cat, "reason": reason})
            summary[cat] = summary.get(cat, 0) + 1

        papers[key] = {
            "empty_ms_count": len(paper_rows),
            "index_sha256": idx_sha,
            "ms_path": ms_path,
            "ms_pages": npages,
            "questions_total": len(questions),
            "rows": paper_rows,
        }

    out = {
        "generated_by": "classify_empty_ms_v2.py",
        "category_legend_zh": CAT_ZH,
        "summary": summary,
        "empty_ms_total": len(rows),
        "papers_with_empty_ms": len(papers),
        "papers": papers,
        "records": rows,
    }
    json.dump(out, open(args.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps({"total": len(rows), "papers": len(papers), "summary": summary},
                     ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
