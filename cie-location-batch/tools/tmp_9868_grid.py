"""临时脚本：把 9868 QP/MS 的区域裁剪按两列密排，每张 HTML 适配 1280x720 视口。"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import batchlib as B  # noqa: E402
import paperlib as P  # noqa: E402

KEY = "9868/2026/Jun/12"
COL_W = 640          # 每列 CSS 宽度
PAGE_H = 716         # 每张 HTML 的可用高度
CAP_H = 18           # 黄条标题高度
COLS = 2


def build(name: str, spec: list[dict]) -> list[Path]:
    import pymupdf

    tmp = P.paper_tmp(KEY)
    crop_dir = tmp / "crops"
    crop_dir.mkdir(parents=True, exist_ok=True)
    pdfs = {}
    for role in {item.get("role", "qp") for item in spec}:
        entry = P.load_paper(KEY)
        docs = entry[role]
        fn = docs[0] if isinstance(docs[0], str) else docs[0]["filename"]
        pdfs[role] = tmp / fn

    cells = []
    for i, item in enumerate(spec):
        role = item.get("role", "qp")
        page_no = int(item["page"])
        bbox = [float(v) for v in item["bbox"]]
        with pymupdf.open(pdfs[role]) as doc:
            page = doc[page_no - 1]
            w_pt = (bbox[3] - bbox[1]) if page.rotation % 180 else (bbox[2] - bbox[0])
        zoom = min(8.0, max(0.5, COL_W / w_pt))
        tag = f"{i:03d}-{role}-p{page_no}"
        out = crop_dir / f"grid-{name}-{tag}.png"
        P.crop_region(pdfs[role], page_no, bbox, out, zoom=zoom)
        with pymupdf.open(out) as d:
            w, h = d[0].rect.width, d[0].rect.height
        css_h = max(1, round(h * COL_W / w))
        cells.append((f"{item.get('label', tag)}", "/" + out.relative_to(B.BATCH_ROOT).as_posix(), css_h))

    pages: list[list] = []
    cur: list[list] = []
    heights = [0] * COLS
    for cell in cells:
        cost = cell[2] + CAP_H + 2
        col = 0 if heights[0] <= heights[1] else 1
        if heights[col] + cost > PAGE_H:
            other = 1 - col
            if heights[other] + cost <= PAGE_H:
                col = other
            else:
                pages.append(cur)
                cur = []
                heights = [0] * COLS
                col = 0
        cur.append([col, cell])
        heights[col] += cost
    if cur:
        pages.append(cur)

    outs: list[Path] = []
    for idx, page_cells in enumerate(pages, 1):
        cols = [[], []]
        for col, (label, src, css_h) in page_cells:
            cols[col].append(
                f'<div class=c><div class=cap>{label}</div>'
                f'<img src="{src}" style="width:{COL_W}px;height:{css_h}px"></div>')
        html = (
            "<!doctype html><html><head><meta charset='utf-8'>"
            f"<title>{name} {idx}</title><style>"
            "html,body{margin:0;padding:0;background:#fff}"
            ".row{display:flex;align-items:flex-start;width:1280px}"
            f".col{{width:{COL_W}px}}"
            ".cap{font:12px/16px monospace;background:#ff0;color:#000;padding:1px 3px;"
            "white-space:nowrap;overflow:hidden}"
            "img{display:block;border-bottom:1px solid #888}"
            "</style></head><body><div class=row>"
            f"<div class=col>{''.join(cols[0])}</div>"
            f"<div class=col>{''.join(cols[1])}</div>"
            "</div></body></html>")
        out = B.WORK / "sheets" / f"{name}-g{idx}.html"
        out.write_text(html, encoding="utf-8")
        outs.append(out)
    return outs


QP = [
    {"label": "QP p2 上 (Q1-Q2)", "page": 2, "bbox": [45, 58, 557, 420]},
    {"label": "QP p2 下 (Q3-Q4)", "page": 2, "bbox": [45, 415, 557, 782]},
    {"label": "QP p3 (Q5-Q6)", "page": 3, "bbox": [45, 58, 557, 400]},
    {"label": "QP p4 (Q7-Q12)", "page": 4, "bbox": [45, 58, 557, 400]},
    {"label": "QP p5 上 (Q13-Q16)", "page": 5, "bbox": [45, 58, 557, 340]},
    {"label": "QP p5 下 (Q17-Q20)", "page": 5, "bbox": [45, 335, 557, 630]},
    {"label": "QP p6 上 (Q21-Q26)", "page": 6, "bbox": [45, 58, 557, 340]},
    {"label": "QP p6 下 (Q27-Q32)", "page": 6, "bbox": [45, 335, 557, 630]},
    {"label": "QP p7 上 (Q33-Q34)", "page": 7, "bbox": [45, 58, 557, 420]},
    {"label": "QP p7 下 (Q35-Q36)", "page": 7, "bbox": [45, 415, 557, 782]},
    {"label": "QP p8 上 (Q37-Q38)", "page": 8, "bbox": [45, 58, 557, 420]},
    {"label": "QP p8 下 (Q39-Q40)", "page": 8, "bbox": [45, 415, 557, 782]},
]

MS = [
    {"label": "MS p2 上 (Q1-Q14)", "role": "ms", "page": 2, "bbox": [65, 50, 550, 400]},
    {"label": "MS p2 下 (Q15-Q28)", "role": "ms", "page": 2, "bbox": [65, 395, 550, 735]},
    {"label": "MS p3 (Q29-Q40)", "role": "ms", "page": 3, "bbox": [65, 50, 550, 380]},
]


def main() -> int:
    for name, spec in (("9868w-qp", QP), ("9868w-ms", MS)):
        pages = build(name, spec)
        print(f"== {name}: {len(pages)} 张")
        for p in pages:
            print(f"http://127.0.0.1:8792/work/sheets/{p.name}")
    import pymupdf
    for role, fname, npages in (("qp", "9868_s26_qp_12.pdf", 8), ("ms", "9868_s26_ms_12.pdf", 3)):
        with pymupdf.open(P.paper_tmp(KEY) / fname) as doc:
            for i in range(npages):
                pg = doc[i]
                print(f"{role} p{i+1}: images={len(pg.get_images())} drawings={len(pg.get_drawings())}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
