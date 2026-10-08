"""离线审计：把索引里每个区域与原件文字层对照，找“区域里没有该题内容”的坏区域。

判据（纯本地，不联网）：
  * 区域矩形 = 未旋转空间 [x0,y0,x1,y1]（page_base=1）。
  * 取与区域矩形相交的所有文字块，去掉页眉/页脚/表格表头（"Question Answer Marks"）等
    非题目内容后，剩余字符数记为 content_chars。
  * content_chars == 0  → 区域里只有页眉页脚/表头 → 坏区域（BAD_empty）。
  * 否则若题号标签（如 "3(a)(iii)"）在区域文字里找不到 → 可疑（SUSPECT_label）。

输出：audit-regions-vs-text.json
用法：python audit_regions_vs_text.py <key> [<key> ...]
"""
from __future__ import annotations

import glob
import hashlib
import json
import os
import re
import sys

import fitz

ROOT = r"C:/Users/weo/Desktop/api"
BATCH = os.path.join(ROOT, "cie-location-batch")
OUT = os.path.join(BATCH, "work/coordinate-audit-2026-10-05/audit-regions-vs-text.json")

HEADER_FOOTER = re.compile(
    r"(Cambridge International AS Level|Cambridge International A Level|"
    r"Mark Scheme|PUBLISHED|May/June|October/November|February/March|"
    r"©\s*Cambridge University Press|©\s*UCLES|Page\s+\d+\s+of\s+\d+|"
    r"Question\s+Answer\s+Marks|Question\s+Answer|\[Turn over|"
    r"This document consists of|DO NOT WRITE IN THIS MARGIN|"
    r"BLANK PAGE|Permission to reproduce|Cambridge Assessment|"
    r"^\s*\d{4}/\d{2}\s*$|^\s*\d{4}/\d{1,2}\s*$)",
    re.IGNORECASE,
)


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def band_text(page: fitz.Page, rect: fitz.Rect) -> tuple[str, str]:
    """返回 (原始文字, 去掉页眉页脚后的文字)。page 必须已 set_rotation(0)。"""
    raw_parts: list[str] = []
    keep_parts: list[str] = []
    for block in page.get_text("blocks"):
        x0, y0, x1, y1, txt = block[0], block[1], block[2], block[3], block[4]
        if not txt.strip():
            continue
        if x1 <= rect.x0 or x0 >= rect.x1 or y1 <= rect.y0 or y0 >= rect.y1:
            continue
        raw_parts.append(txt.strip())
        lines = [ln.strip() for ln in txt.splitlines() if ln.strip()]
        keep = [ln for ln in lines if not HEADER_FOOTER.search(ln)]
        if keep:
            keep_parts.append(" ".join(keep))
    return " | ".join(raw_parts), " ".join(keep_parts)


def main() -> int:
    keys = sys.argv[1:]
    if not keys:
        print(__doc__)
        return 2
    report: dict = {"generated_at": None, "papers": {}}
    for key in keys:
        subject, year, season, paper = key.split("/")
        idx_path = os.path.join(BATCH, "indexes", subject, f"{year}-{season}-{paper}",
                                "cie-index.json")
        index = json.loads(open(idx_path, encoding="utf-8").read())
        tmp_dir = os.path.join(BATCH, "tmp", subject, f"{year}-{season}-{paper}")
        by_sha = {sha256_file(p): p for p in glob.glob(os.path.join(tmp_dir, "*.pdf"))}
        docs = {d["role"]: d["sha256"] for d in index["documents"]}
        opened: dict[str, fitz.Document] = {}
        for role, sha in docs.items():
            if sha in by_sha:
                opened[role] = fitz.open(by_sha[sha])
        rows = []
        for q in index["questions"]:
            for role in ("qp", "ms"):
                if role not in opened:
                    continue
                doc = opened[role]
                for i, r in enumerate(q.get(role) or []):
                    page_no = r["page"]
                    if page_no < 1 or page_no > len(doc):
                        rows.append({"question": q["question"], "role": role, "r": i,
                                     "page": page_no, "bbox": r["bbox"],
                                     "verdict": "BAD_page_oob", "raw": "", "keep": ""})
                        continue
                    page = doc[page_no - 1]
                    page.set_rotation(0)
                    rect = fitz.Rect(*r["bbox"])
                    raw, keep = band_text(page, rect)
                    label = q["question"]
                    keep_norm = keep.replace(" ", "")
                    has_label = label.replace(" ", "") in keep_norm
                    if not keep.strip():
                        verdict = "BAD_empty"
                    elif not has_label and role == "ms":
                        verdict = "SUSPECT_label"
                    elif not has_label and role == "qp":
                        verdict = "SUSPECT_label"
                    else:
                        verdict = "OK"
                    rows.append({"question": label, "role": role, "r": i, "page": page_no,
                                 "bbox": r["bbox"], "verdict": verdict,
                                 "raw": raw[:400], "keep": keep[:400]})
        counts: dict[str, int] = {}
        for row in rows:
            counts[row["verdict"]] = counts.get(row["verdict"], 0) + 1
        report["papers"][key] = {"regions": len(rows), "counts": counts, "rows": rows}
        print(f"{key}: {len(rows)} 区域 {counts}")
        for row in rows:
            if row["verdict"] != "OK":
                print(f"   {row['verdict']:14s} {row['question']:10s} {row['role']} "
                      f"p{row['page']} r{row['r']} bbox={row['bbox']} keep={row['keep'][:120]!r}")
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=1)
    print("写出：", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
