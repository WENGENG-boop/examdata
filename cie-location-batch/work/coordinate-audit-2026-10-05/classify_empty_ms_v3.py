"""空 MS（ms=[]）逐条分类 v3 —— 纯离线。

在 v2 之上增加关键一步：当某题的题号标签在 MS 文本层里**独占一行**出现时，
取该行的几何位置（unrotated x 带），检查它是否落在同卷**其他题已建的 ms 区域**内。
  - 落在其中 → 该题内容已被更粗粒度的父题/兄弟题区域覆盖（父题聚合），记 covered_by_parent_region；
  - 不在其中 → 确属解析遗漏，需补建区域，记 parse_omission。

v1 缺陷（已实测）：纯数字题号退化为裸数字匹配（"1" 命中整页任意数字），
把 0580 这类数学卷的父题误判成 parse_omission。

用法: python classify_empty_ms_v3.py [--out <path>]
输出: deliverables/empty-ms-classification.json
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
    "covered_by_parent_region": "父题聚合",
    "shared_region": "共用评分区域",
    "pending_visual": "待核对",
    "no_text_layer": "待核对",
}


def label_pattern(q: str) -> str:
    parts = re.findall(r"[0-9]+|[A-Za-z]+", q)
    core = r"\s*\(?\s*".join(re.escape(p) for p in parts)
    core += r"\s*\)?" * (len(parts) - 1)
    return core


def strict_regex(q: str) -> tuple[re.Pattern, re.Pattern]:
    core = label_pattern(q)
    alone = re.compile(r"(?m)^\s*" + core + r"\s*$", re.IGNORECASE)
    lead = re.compile(r"(?m)^\s*" + core + r"\s*[\.:,)\]\-–—]", re.IGNORECASE)
    return alone, lead


def label_line_bbox(page, q: str):
    """返回该题号标签独占一行的 (bbox_unrotated, 行文本)；找不到返回 (None, None)。"""
    core = label_pattern(q)
    want = re.compile(r"^\s*" + core + r"\s*$", re.IGNORECASE)
    for blk in page.get_text("dict")["blocks"]:
        if blk.get("type") != 0:
            continue
        for ln in blk.get("lines", []):
            txt = "".join(s.get("text", "") for s in ln.get("spans", []))
            if want.match(txt.strip()):
                return [round(float(v), 1) for v in ln["bbox"]], txt.strip()[:60]
    return None, None


def ms_path_for(key: str) -> str | None:
    subj, year, season, paper = key.split("/")
    d = os.path.join(BATCH, "tmp", subj, f"{year}-{season}-{paper}")
    if not os.path.isdir(d):
        return None
    cands = [f for f in os.listdir(d) if f.lower().endswith(".pdf") and "_ms_" in f.lower()]
    return os.path.join(d, sorted(cands)[0]) if cands else None


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
        doc = None
        npages = 0
        if ms_exists:
            doc = pymupdf.open(ms_path)
            npages = doc.page_count
            for i in range(npages):
                pages_text[i + 1] = doc[i].get_text() or ""

        regions_by_q = {q["question"]: (q.get("ms") or []) for q in questions if q.get("ms")}
        children_of: dict[str, list[dict]] = {}
        for q in questions:
            if q.get("parent"):
                children_of.setdefault(q["parent"], []).append(q)

        paper_rows: list[dict] = []
        for q in empties:
            qq = q["question"]
            qp_pages = sorted({r["page"] for r in (q.get("qp") or [])})
            alone_hits: dict[int, dict] = {}
            lead_hits: dict[int, str] = {}
            if ms_exists:
                ra, rl = strict_regex(qq)
                for p in range(1, npages + 1):
                    t = pages_text.get(p) or ""
                    if len(t.strip()) < 20 or not ra.search(t):
                        if len(t.strip()) >= 20:
                            m2 = rl.search(t)
                            if m2:
                                lead_hits[p] = m2.group(0).strip()[:60]
                        continue
                    bb, ln = label_line_bbox(doc[p - 1], qq)
                    alone_hits[p] = {"bbox": bb, "text": ln}

            # 命中行是否落在同卷其他题的 ms 区域内
            covering = []
            for p, hit in alone_hits.items():
                bb = hit.get("bbox")
                if not bb:
                    continue
                lx0 = min(bb[0], bb[2])
                lx1 = max(bb[0], bb[2])
                for other, regs in regions_by_q.items():
                    if other == qq:
                        continue
                    for r in regs:
                        if r["page"] != p:
                            continue
                        rx0, rx1 = sorted((r["bbox"][0], r["bbox"][2]))
                        if rx0 - 0.6 <= lx0 and lx1 <= rx1 + 0.6:
                            covering.append({"page": p, "by_question": other, "by_bbox": r["bbox"],
                                             "label_bbox": bb, "label_text": hit["text"]})
            kids = children_of.get(qq, [])
            kid_ms = {k["question"]: sorted({r["page"] for r in (k.get("ms") or [])}) for k in kids}
            kids_all_have_ms = bool(kids) and all(kid_ms[k["question"]] for k in kids)

            ev = {
                "index_sha256": idx_sha,
                "marks": q.get("marks"),
                "parent": q.get("parent"),
                "uncertain": bool(q.get("uncertain")),
                "qp_pages": qp_pages,
                "label_alone_lines": {str(p): v for p, v in alone_hits.items()},
                "label_lead_hit_pages": sorted(lead_hits),
                "covering_regions": covering,
                "children": [k["question"] for k in kids],
                "children_ms_pages": kid_ms,
                "ms_pages": npages,
                "ms_has_text_layer": any(len(v.strip()) >= 20 for v in pages_text.values()),
            }
            cat = reason = None
            if not ms_exists:
                cat, reason = "source_missing", f"本地无 MS 原件: {ms_path}"
            elif kids_all_have_ms:
                cat = "parent_delegated"
                reason = ("父题无独立 ms 区域；评分内容由子题 "
                          + "、".join(f"{k}(ms 页 {kid_ms[k['question']]})" for k in kids) + " 承载")
            elif covering:
                cat = "covered_by_parent_region"
                c = covering[0]
                reason = (f"MS 文本层第 {c['page']} 页存在独占一行的题号标签 {c['label_text']!r}"
                          f"（行 bbox={c['label_bbox']}），该行落在题 {c['by_question']} 的 ms 区域"
                          f"{c['by_bbox']} 内 → 内容已被更粗粒度区域覆盖，属父题/兄弟题聚合")
            elif alone_hits:
                cat = "parse_omission"
                reason = ("MS 文本层存在独占一行的题号标签且**不落在任何已有 ms 区域内**，索引漏建；命中页 "
                          + str(sorted(alone_hits))
                          + " 例: "
                          + json.dumps({str(k): v["text"] for k, v in list(alone_hits.items())[:2]}, ensure_ascii=False))
            else:
                parent = q.get("parent")
                pp = sorted({r["page"] for r in regions_by_q.get(parent, [])}) if parent else None
                shared = {k: sorted({r["page"] for r in v}) for k, v in regions_by_q.items()
                          if k != qq and set(r["page"] for r in v) & set(qp_pages)}
                if parent and pp and (set(pp) & set(qp_pages) or not qp_pages):
                    cat, reason = "parent_aggregate", f"父题 {parent} 已有 ms 区域（页 {pp}），与本题 qp 页 {qp_pages} 重合"
                elif shared:
                    cat, reason = "shared_region", "同卷其他题的 ms 区域页与本题 qp 页重合: " + json.dumps(shared, ensure_ascii=False)
                elif lead_hits:
                    cat = "pending_visual"
                    reason = ("只有行首弱匹配（标签非独占一行），可能是正文数字而非题号；需目视，命中页 "
                              + str(sorted(lead_hits)))
                elif ev["ms_has_text_layer"]:
                    cat, reason = "pending_visual", f"MS 有文本层但检索不到该题号标签；需目视（卷内 {npages} 页）"
                else:
                    cat, reason = "no_text_layer", f"MS 原件 {npages} 页全无文本层（扫描件），必须目视确认"

            rows.append({"paper": key, "question": qq, "category": cat,
                         "category_zh": CAT_ZH.get(cat, cat), "reason": reason,
                         "evidence": ev, "notes": (q.get("notes") or "")[:200]})
            paper_rows.append({"question": qq, "category": cat, "reason": reason})
            summary[cat] = summary.get(cat, 0) + 1

        if doc:
            doc.close()
        papers[key] = {"empty_ms_count": len(paper_rows), "index_sha256": idx_sha,
                       "ms_path": ms_path, "ms_pages": npages,
                       "questions_total": len(questions), "rows": paper_rows}

    zh: dict[str, int] = {}
    for k, v in summary.items():
        zh[CAT_ZH.get(k, k)] = zh.get(CAT_ZH.get(k, k), 0) + v
    out = {"generated_by": "classify_empty_ms_v3.py", "category_legend_zh": CAT_ZH,
           "summary": summary, "summary_zh": zh, "empty_ms_total": len(rows),
           "papers_with_empty_ms": len(papers), "papers": papers, "records": rows}
    json.dump(out, open(args.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps({"total": len(rows), "papers": len(papers),
                      "summary": summary, "summary_zh": zh}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
