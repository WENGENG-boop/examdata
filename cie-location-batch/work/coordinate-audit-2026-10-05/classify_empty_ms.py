"""空 MS（ms=[]）逐条分类 —— 纯离线，只用本地索引 + 本地 MS 原件文本层。

用法: python classify_empty_ms.py [--out <path>]
输出: deliverables/empty-ms-classification.json  (+ 控制台摘要)

分类口径（每条给"具体证据"，不允许无证据下结论）：
  source_missing    : MS 原件不在本地 / sha 不匹配
  parse_omission    : MS 文本层里能检索到该题号标签（说明有独立评分行，索引漏建）
  no_text_layer     : MS 原件该题号所在页无文本层（扫描件）→ 必须目视，记为待核对
  parent_aggregate  : 该题有 ms 非空的父题，且父题 ms 区域页集合覆盖本题 qp 页 → 父题聚合
  shared_region     : 同卷另有题（非父子）的 ms 区域页集合与本题 qp 页重合 → 共用评分区域候选
  pending_visual    : 以上都不成立 → 待核对（列出需要目视的页）
"""
from __future__ import annotations

import argparse
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


def label_regex(q: str) -> re.Pattern:
    # "1(b)(ii)" -> 允许标签内部空白: 1\s*\(\s*b\s*\)\s*\(\s*ii\s*\)
    parts = re.findall(r"[0-9]+|[A-Za-z]+", q)
    pat = r"\s*".join(re.escape(p) for p in parts)
    # 允许罗马数字/字母之间夹括号
    return re.compile(pat, re.IGNORECASE)


def ms_path_for(key: str) -> str | None:
    subj, year, season, paper = key.split("/")
    d = os.path.join(BATCH, "tmp", subj, f"{year}-{season}-{paper}")
    if not os.path.isdir(d):
        return None
    cands = [f for f in os.listdir(d) if f.lower().endswith(".pdf") and "_ms_" in f.lower()]
    if not cands:
        return None
    return os.path.join(d, sorted(cands)[0])


def index_path(key: str) -> str:
    subj, year, season, paper = key.split("/")
    return os.path.join(BATCH, "indexes", subj, f"{year}-{season}-{paper}", "cie-index.json")


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

    import glob

    index_files = sorted(glob.glob(os.path.join(BATCH, "indexes", "*", "*", "cie-index.json")))
    out_rows: list[dict] = []
    summary: dict[str, int] = {}
    papers: dict[str, dict] = {}

    for f in index_files:
        key = key_of(f)
        idx = json.load(open(f, encoding="utf-8"))
        idx_sha = sha256_file(f)
        empties = [q for q in idx.get("questions", []) if not q.get("ms")]
        if not empties:
            continue
        ms_sha = next((d["sha256"] for d in idx.get("documents", []) if d["role"] == "ms"), None)
        msp = ms_path_for(key)
        docinfo: dict = {"ms_path": msp, "ms_exists": bool(msp and os.path.exists(msp))}
        text_pages: dict[int, bool] = {}
        hit_pages: dict[str, list[int]] = {}
        npages = 0
        if docinfo["ms_exists"]:
            try:
                doc = pymupdf.open(msp)
                npages = doc.page_count
                docinfo["ms_pages"] = npages
                for pno in range(npages):
                    t = doc[pno].get_text() or ""
                    text_pages[pno + 1] = len(t.strip()) >= 20
                for q in empties:
                    rx = label_regex(q["question"])
                    hits = [p for p in range(1, npages + 1) if text_pages.get(p) and rx.search(doc[p - 1].get_text() or "")]
                    hit_pages[q["question"]] = hits
                doc.close()
            except Exception as exc:  # noqa: BLE001
                docinfo["error"] = f"{type(exc).__name__}: {exc}"
        # 索引内已建的 ms 区域页集合（按题）
        ms_pages_by_q = {}
        for q in idx.get("questions", []):
            regs = q.get("ms") or []
            if regs:
                ms_pages_by_q[q["question"]] = sorted({r["page"] for r in regs})

        for q in empties:
            qq = q["question"]
            parent = q.get("parent")
            qp_pages = sorted({r["page"] for r in (q.get("qp") or [])})
            ev = {
                "index_sha256": idx_sha,
                "marks": q.get("marks"),
                "parent": parent,
                "uncertain": bool(q.get("uncertain")),
                "qp_pages": qp_pages,
                "ms_label_hit_pages": hit_pages.get(qq, []),
                "ms_has_text_layer_on_hit": None,
            }
            cat = None
            reason = None
            if not docinfo["ms_exists"]:
                cat, reason = "source_missing", f"本地无 MS 原件或路径缺失: {docinfo['ms_path']}"
            elif docinfo.get("error"):
                cat, reason = "source_missing", f"MS 原件无法打开: {docinfo['error']}"
            elif hit_pages.get(qq):
                cat, reason = "parse_omission", f"MS 文本层第 {hit_pages[qq]} 页可检索到题号标签，索引却无 ms 区域"
            else:
                # 无文本命中：判断父题聚合 / 共用区域
                parent_pages = ms_pages_by_q.get(parent) if parent else None
                shared = {k: v for k, v in ms_pages_by_q.items() if k != qq and set(v) & set(qp_pages)}
                if parent and parent_pages and set(parent_pages) & set(qp_pages or parent_pages):
                    cat = "parent_aggregate"
                    reason = f"父题 {parent} 已有 ms 区域（页 {parent_pages}），与本题 qp 页 {qp_pages} 重合"
                elif shared:
                    cat = "shared_region"
                    reason = "同卷其他题的 ms 区域页与本题 qp 页重合: " + json.dumps(shared, ensure_ascii=False)
                elif any(v for k, v in text_pages.items()):
                    cat = "pending_visual"
                    reason = ("MS 原件有文本层但检索不到该题号标签；"
                              f"需目视确认（卷内共 {npages} 页，其中 {sum(1 for v in text_pages.values() if v)} 页有文本层）")
                else:
                    cat = "no_text_layer"
                    reason = f"MS 原件 {npages} 页全无文本层（扫描件），必须目视确认"
            out_rows.append({
                "paper": key, "question": qq, "category": cat, "reason": reason, "evidence": ev,
                "ms_doc": docinfo, "notes": (q.get("notes") or "")[:200],
            })
            summary[cat] = summary.get(cat, 0) + 1
        papers[key] = {"empty": len(empties), "ms_pages": npages, "ms_path": msp,
                       "index_sha256": idx_sha}

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    payload = {
        "generated_at": __import__("datetime").datetime.now().astimezone().isoformat(timespec="seconds"),
        "index_files": len(index_files),
        "empty_ms_total": len(out_rows),
        "category_counts": summary,
        "papers": papers,
        "records": out_rows,
    }
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=1)
    print("total empty_ms:", len(out_rows))
    for k, v in sorted(summary.items(), key=lambda x: -x[1]):
        print(f"  {k}: {v}")
    print("written:", args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
