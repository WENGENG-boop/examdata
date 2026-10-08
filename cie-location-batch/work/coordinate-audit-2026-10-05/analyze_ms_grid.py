"""分析 MS 里的"评分网格"行，重建应有的区域 band，并与当前索引 ms 区域对差（纯离线）。

用途：判定 empty_ms（无 ms 区域）到底是"真实无独立评分"还是"解析遗漏/被前一行吞并"。
输入：<key>；读索引 documents 里的 ms sha 对应原件（tmp/ 下）。
判据：MS 页里形如 `1 B 1`（题号 答案 分数）的行即该题的评分项；行 band 取
      y0 = 行顶 - PAD, y1 = 下一行行顶 - PAD（页末行到行底 + PAD）。
输出：deliverables/ms-grid-<slug>.json，含每题的期望 band、当前索引区域、覆盖判定。

用法: python analyze_ms_grid.py 8238/2024/Nov/11 [8238/2024/Nov/12 ...]
"""
from __future__ import annotations

import glob
import hashlib
import json
import os
import re
import sys

import fitz

BATCH = r"C:/Users/weo/Desktop/api/cie-location-batch"
DELIV = os.path.join(BATCH, "work", "coordinate-audit-2026-10-05", "deliverables")
PAD = 1.8
ROW_RE = re.compile(r"^\s*(\d{1,3})\s+([A-Z]{1,3}|\d{1,3})\s+(\d{1,2})\s*$")


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def index_path(key: str) -> str:
    s, y, se, p = key.split("/")
    return os.path.join(BATCH, "indexes", s, f"{y}-{se}-{p}", "cie-index.json")


def grid_rows(doc) -> list[dict]:
    """返回网格行 [(page, question, answer, marks, y0, y1, x0, x1)]，按页序。

    注意：答案格是三个独立 text line（题号 / 答案 / 分数），只有 blocks 模式
    会把同一 y 带的三格合成一行文本，所以这里必须用 blocks。
    """
    out = []
    for pno in range(doc.page_count):
        page = doc[pno]
        for x0, y0, x1, y1, txt, _bno, _btype in page.get_text("blocks"):
            m = ROW_RE.match(" ".join(txt.split()))
            if not m:
                continue
            out.append({"page": pno + 1, "question": m.group(1),
                        "answer": m.group(2), "marks": int(m.group(3)),
                        "y0": round(y0, 2), "y1": round(y1, 2),
                        "x0": round(x0, 2), "x1": round(x1, 2)})
    return out


def analyze(key: str) -> dict:
    idx = json.load(open(index_path(key), encoding="utf-8"))
    tmpdir = os.path.join(BATCH, "tmp", *key.split("/")[:2])
    tmpdir = os.path.join(BATCH, "tmp", key.split("/")[0],
                          f"{key.split('/')[1]}-{key.split('/')[2]}-{key.split('/')[3]}")
    pdfs = {sha256_file(p): p for p in glob.glob(os.path.join(tmpdir, "*.pdf"))}
    ms_sha = next((d["sha256"] for d in idx["documents"] if d["role"] == "ms"), None)
    res = {"key": key, "ms_sha256": ms_sha, "ms_original": pdfs.get(ms_sha)}
    if not ms_sha or ms_sha not in pdfs:
        res["error"] = "ms_original_missing"
        return res
    doc = fitz.open(pdfs[ms_sha])
    rows = grid_rows(doc)
    res["ms_pages"] = doc.page_count
    res["grid_rows"] = len(rows)
    # 每行 band：y0 = 行顶-PAD，y1 = 同一页下一行行顶-PAD；页末行到行底+PAD
    bands: dict[str, list[dict]] = {}
    for i, r in enumerate(rows):
        nxt = rows[i + 1] if i + 1 < len(rows) else None
        y1 = round(nxt["y0"] - PAD, 2) if (nxt and nxt["page"] == r["page"]) \
            else round(r["y1"] + PAD, 2)
        band = {"page": r["page"], "bbox": [78.4, round(r["y0"] - PAD, 2), 541.2, y1],
                "row_y": [r["y0"], r["y1"]],
                "text": f"{r['question']} {r['answer']} {r['marks']}"}
        bands.setdefault(r["question"], []).append(band)
    res["bands"] = bands
    # 与索引对差
    idx_ms = {}
    for q in idx["questions"]:
        idx_ms[str(q["question"])] = [{"page": r["page"], "bbox": r["bbox"]}
                                      for r in (q.get("ms") or [])]
    res["index_ms"] = idx_ms
    uncovered, misassigned, spurious, extra_rows = [], [], [], []
    for q, bs in bands.items():
        if q not in idx_ms or not idx_ms[q]:
            uncovered.append(q)
            continue
        for b in bs:
            hit = [r for r in idx_ms[q]
                   if r["page"] == b["page"] and abs(r["bbox"][1] - b["bbox"][1]) < 3.0]
            if not hit:
                misassigned.append({"question": q, "band": b,
                                    "index": idx_ms[q]})
    # y1 也须匹配：y1 偏大说明该区域吞并了下一题的网格行
    y1_bad = []
    for q, bs in bands.items():
        for b in bs:
            for r in idx_ms.get(q, []):
                if r["page"] == b["page"] and abs(r["bbox"][1] - b["bbox"][1]) < 3.0:
                    if r["bbox"][3] - b["bbox"][3] > 3.0:
                        y1_bad.append({"question": q, "index_bbox": r["bbox"],
                                       "expected_bbox": b["bbox"],
                                       "extra_height_pt": round(r["bbox"][3] - b["bbox"][3], 1),
                                       "note": "y1 偏大，吞并了下一题的行"})
    covered_qs = {q for q in idx_ms if idx_ms[q]}
    for q, regs in idx_ms.items():
        if q not in bands and regs:
            spurious.append({"question": q, "index": regs,
                             "note": "索引有 ms 区域但该页找不到网格行"})
    # 索引里的 ms 区域若在同页找不到对应 band（y0 不符），即"无法解释的区域"
    unexplained = []
    for q, regs in idx_ms.items():
        for r in regs:
            ok = any(b["page"] == r["page"] and abs(b["bbox"][1] - float(r["bbox"][1])) < 3.0
                     for b in bands.get(q, []))
            if not ok:
                unexplained.append({"question": q, "page": r["page"],
                                    "bbox": r["bbox"],
                                    "note": "该页该位置的 band 不存在（疑似页眉/表格标题被当成续页区域）"})
    res["verdict"] = {
        "questions_in_grid": len(bands),
        "questions_with_index_ms": len(covered_qs),
        "uncovered_rows(empty_ms 且网格里有行)": sorted(uncovered, key=int),
        "band_mismatch_rows": misassigned,
        "band_y1_too_long": y1_bad,
        "index_regions_without_row": spurious,
        "index_regions_unexplained": unexplained,
        "empty_ms_no_row_either": sorted(
            [str(q["question"]) for q in idx["questions"]
             if not (q.get("ms") or []) and str(q["question"]) not in bands], key=int),
        "rows_not_in_index_questions": sorted(
            [q for q in bands if q not in {str(x["question"]) for x in idx["questions"]}],
            key=int),
    }
    doc.close()
    return res


def main() -> int:
    os.makedirs(DELIV, exist_ok=True)
    rc = 0
    for key in sys.argv[1:]:
        try:
            res = analyze(key)
        except Exception as exc:  # noqa: BLE001
            print(f"{key}: ERROR {exc}")
            rc = 1
            continue
        slug = key.replace("/", "_")
        out = os.path.join(DELIV, f"ms-grid-{slug}.json")
        with open(out, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(res, fh, ensure_ascii=False, indent=1)
        v = res.get("verdict", {})
        print(json.dumps({"key": key, "pages": res.get("ms_pages"),
                          "rows": res.get("grid_rows"),
                          "grid_qs": v.get("questions_in_grid"),
                          "idx_ms_qs": v.get("questions_with_index_ms"),
                          "uncovered": v.get("uncovered_rows(empty_ms 且网格里有行)"),
                          "mismatch": len(v.get("band_mismatch_rows") or []),
                          "spurious": len(v.get("index_regions_without_row") or []),
                          "no_row_no_ms": v.get("empty_ms_no_row_either"),
                          "err": res.get("error")}, ensure_ascii=False))
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
