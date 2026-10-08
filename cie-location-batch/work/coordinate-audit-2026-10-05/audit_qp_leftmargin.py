"""离线审计：QP 区域左边界是否把印刷题号切在区域外。

对每个 QP 区域，渲染紧贴其左边界左侧的竖条 (left-30 .. left, y0 .. y0+22)，
统计墨迹像素比例。有条带墨迹 => 该区域左侧存在内容，可能是被切掉的印刷题号。

纯离线（只读本地 PDF + 索引），不联网。
用法：python audit_qp_leftmargin.py "8386/2026/Jun/12" "0495/2026/Jun/11"
"""
from __future__ import annotations

import glob
import json
import os
import sys

import fitz

BATCH = r"C:/Users/weo/Desktop/api/cie-location-batch"
STRIP_W = 30.0
STRIP_H = 22.0
SCALE = 4.0
INK_THRESHOLD = 0.002  # 墨迹像素占条带比例


def index_path(key: str) -> str:
    subject, year, season, paper = key.split("/")
    return os.path.join(BATCH, "indexes", subject, f"{year}-{season}-{paper}", "cie-index.json")


def qp_pdf(key: str) -> str:
    subject, year, season, paper = key.split("/")
    tmp = os.path.join(BATCH, "tmp", subject, f"{year}-{season}-{paper}")
    matches = [p for p in glob.glob(os.path.join(tmp, "*.pdf")) if "_qp_" in os.path.basename(p)]
    if len(matches) != 1:
        raise SystemExit(f"qp pdf not unique for {key}: {matches}")
    return matches[0]


def ink_ratio(page: fitz.Page, rect: fitz.Rect) -> float:
    if rect.width <= 0 or rect.height <= 0:
        return 0.0
    pm = page.get_pixmap(matrix=fitz.Matrix(SCALE, SCALE), clip=rect, colorspace=fitz.csGRAY)
    data = pm.samples
    dark = sum(1 for b in data if b < 160)
    return dark / max(1, len(data))


def main() -> int:
    keys = sys.argv[1:]
    rows = []
    for key in keys:
        with open(index_path(key), encoding="utf-8") as fh:
            idx = json.load(fh)
        doc = fitz.open(qp_pdf(key))
        for q in idx["questions"]:
            for r in q.get("qp") or []:
                page = doc[int(r["page"]) - 1]
                x0, y0, x1, y1 = (float(v) for v in r["bbox"])
                rect = fitz.Rect(max(0.0, x0 - STRIP_W), y0, x0, min(y1, y0 + STRIP_H))
                ratio = ink_ratio(page, rect)
                rows.append({"key": key, "question": q["question"], "page": int(r["page"]),
                             "bbox": [x0, y0, x1, y1], "left_strip_ink": round(ratio, 5),
                             "flag": ratio > INK_THRESHOLD})
        doc.close()
    flagged = [r for r in rows if r["flag"]]
    print(json.dumps({"total_qp_regions": len(rows), "flagged": len(flagged),
                      "flag_rows": flagged}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
