"""临时工具：把索引里的 QP 区域 + 从 MS 文字层推出来的评分行带，排成密集表。

用法：python tmp_gridsheet.py <key> <name> --index <idx.json> [--cols N] [--colw PX] [--pageh PX]
输出：每张表的 URL 逐行打印到 stdout。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import pymupdf

import batchlib as B
import paperlib as P

LABEL_H = 26
DPR = 2
QNUM = re.compile(r"^\s*(\d{1,2})\s*(\(\s*[a-z]\s*\))?\s*(\(\s*[ivx]+\s*\))?\s*$")


def lines_of(page):
    groups = {}
    for w in page.get_text("words"):
        groups.setdefault((w[5], w[6]), []).append(w)
    out = []
    for v in groups.values():
        v.sort(key=lambda w: w[0])
        out.append(
            (
                min(w[1] for w in v),
                min(w[0] for w in v),
                max(w[2] for w in v),
                max(w[3] for w in v),
                " ".join(w[4] for w in v),
            )
        )
    out.sort()
    return out


def ms_rows(pdf: Path):
    """返回 {题号: [(page, bbox), ...]}，行带取该题号行的实际内容范围。"""
    rows = {}
    doc = pymupdf.open(pdf)
    for pno in range(doc.page_count):
        page = doc[pno]
        ls = lines_of(page)
        anchors = []
        for y0, x0, x1, y1, t in ls:
            if x0 < 132 and 40 < y0 < 740 and QNUM.match(t):
                anchors.append((y0, QNUM.match(t).group(0).strip()))
        if not anchors:
            continue
        body = [l for l in ls if 40 < l[0] < 745]
        tx0 = min(l[1] for l in body) - 4
        tx1 = max(l[2] for l in body) + 6
        for i, (ay, q) in enumerate(anchors):
            nxt = anchors[i + 1][0] if i + 1 < len(anchors) else 10**9
            inside = [l for l in ls if ay - 1 <= l[0] < nxt and l[3] < 740]
            y_end = max((l[3] for l in inside), default=ay + 12)
            bbox = [round(tx0, 1), round(ay - 3, 1), round(tx1, 1), round(min(730.0, y_end + 4), 1)]
            rows.setdefault(q.replace(" ", ""), []).append((pno + 1, bbox))
    doc.close()
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("key")
    ap.add_argument("name")
    ap.add_argument("--index", required=True)
    ap.add_argument("--cols", type=int, default=3)
    ap.add_argument("--colw", type=int, default=330)
    ap.add_argument("--pageh", type=int, default=1000)
    a = ap.parse_args()

    idx = json.loads(Path(a.index).read_text(encoding="utf-8"))
    ident = idx["identity"]
    stem = f"{ident['subject']}-{ident['year']}-{ident['season']}-{ident['paper']}"
    entry = P.load_paper(a.key)

    def pdf_for(role):
        docs = entry[role]
        name = docs[0] if isinstance(docs[0], str) else docs[0]["filename"]
        return P.paper_tmp(a.key) / name

    pdfs = {"qp": pdf_for("qp"), "ms": pdf_for("ms")}
    ms_map = ms_rows(pdfs["ms"]) if pdfs.get("ms") else {}

    items = []
    for q in idx["questions"]:
        for r in q["qp"]:
            items.append((q["question"], "qp", r["page"], r["bbox"]))
        for page, bbox in ms_map.get(q["question"], []):
            items.append((q["question"], "ms", page, bbox))

    crop_dir = P.paper_tmp(a.key) / "crops"
    crop_dir.mkdir(parents=True, exist_ok=True)
    cells = []
    for i, (q, role, pno, bbox) in enumerate(items):
        pdf = pdfs[role]
        with pymupdf.open(pdf) as d:
            page = d[pno - 1]
            w_pt = (bbox[2] - bbox[0]) if page.rotation % 180 == 0 else (bbox[3] - bbox[1])
            h_pt = (bbox[3] - bbox[1]) if page.rotation % 180 == 0 else (bbox[2] - bbox[0])
        zoom = min(6.0, max(0.4, DPR * a.colw / w_pt))
        out = crop_dir / f"g-{a.name}-{i:03d}-{role}-p{pno}.png"
        P.crop_region(pdf, pno, bbox, out, zoom=zoom)
        with pymupdf.open(out) as d:
            w = d[0].rect.width
            h = d[0].rect.height
        css_h = max(1, round(h * a.colw / w))
        cells.append((f"{q} [{role} p{pno}] {bbox}", "/" + out.relative_to(B.BATCH_ROOT).as_posix(), css_h))

    pages, cur, used = [], [], 0
    for c in cells:
        cost = (c[2] + LABEL_H + 4) / a.cols
        if cur and used + cost > a.pageh:
            pages.append(cur)
            cur, used = [], 0
        cur.append(c)
        used += cost
    if cur:
        pages.append(cur)

    urls = []
    for n, pg in enumerate(pages, 1):
        rows_html = []
        for j in range(0, len(pg), a.cols):
            cells_html = "".join(
                f'<div class=c><div class=cap>{lab}</div>'
                f'<img src="{src}" style="width:{a.colw}px;height:{h}px"></div>'
                for lab, src, h in pg[j : j + a.cols]
            )
            rows_html.append(f'<div class=r>{cells_html}</div>')
        html = (
            "<!doctype html><html><head><meta charset='utf-8'><style>"
            "html,body{margin:0;padding:0;background:#fff}"
            ".r{display:flex;align-items:flex-start}"
            f".c{{width:{a.colw}px}}"
            ".cap{font:11px/15px monospace;background:#ff0;color:#000;padding:1px 3px;"
            "white-space:nowrap;overflow:hidden}"
            "img{display:block;border-bottom:1px solid #888}"
            "</style></head><body>" + "".join(rows_html) + "</body></html>"
        )
        out = B.WORK / "sheets" / f"{stem}-{a.name}-grid-{n}.html"
        out.write_text(html, encoding="utf-8")
        urls.append(f"http://127.0.0.1:8792/work/sheets/{out.name}")
    for u in urls:
        print(u)
    print(f"# pages={len(urls)} cells={len(cells)} cols={a.cols} colw={a.colw}", file=sys.stderr)


if __name__ == "__main__":
    main()
