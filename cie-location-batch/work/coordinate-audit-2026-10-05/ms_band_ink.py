"""对「悬空区域」（表头带候选）做墨迹证据核验（只读本地 PDF，不联网）。

对 deliverables/ms-row-audit-summary.json 里每个 dangling_regions 条目，
在该页显示坐标下统计区域条带内的：
  - 文本行（全部，含页眉）
  - 矢量绘图（get_drawings，矩形/线/路径）
  - 位图块（get_image_info）
条带内既无正文文本、又无矢量图形、又无位图，才能判定该区域不承载任何内容。

输出 deliverables/ms-band-ink.json
"""
import json
import os
import sys

import pymupdf

A = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, A)
from ms_row_audit import pdf_for, index_path, to_display  # noqa: E402

SUM = os.path.join(A, "deliverables", "ms-row-audit-summary.json")
OUT = os.path.join(A, "deliverables", "ms-band-ink.json")


def intersect(a, b, pad=1.0):
    return not (a[2] < b[0] - pad or a[0] > b[2] + pad
                or a[3] < b[1] - pad or a[1] > b[3] + pad)


def main():
    summary = json.load(open(SUM, encoding="utf-8"))
    idx_cache = {}
    doc_cache = {}
    rows = []
    for key, p in summary["per_paper"].items():
        for f in p.get("dangling_detail") or []:
            page = int(f["page"])
            if key not in idx_cache:
                idx_cache[key] = json.loads(index_path(key).read_text(encoding="utf-8"))
            if key not in doc_cache:
                doc_cache[key] = pymupdf.open(pdf_for(key, "ms"))
            doc = doc_cache[key]
            pg = doc[page - 1]
            rot = pg.rotation
            w, h = pg.mediabox.width, pg.mediabox.height
            rb = tuple(f["bbox"])

            lines = []
            for b in pg.get_text("dict")["blocks"]:
                if b.get("type") != 0:
                    continue
                for ln in b.get("lines", []):
                    db = to_display(tuple(ln["bbox"]), rot, w, h)
                    if intersect(db, rb):
                        lines.append((db, "".join(s["text"] for s in ln.get("spans", [])).strip()))
            # 表头行的下沿：区域条带内 Question/Answer/Marks 表头文字的最低点。
            hdr_bottom = max((db[3] for db, t in lines
                              if t in ("Question", "Answer", "Marks")), default=None)
            below = [t for db, t in lines
                     if hdr_bottom is not None and db[1] >= hdr_bottom - 1]
            drawings = 0
            drawings_below = 0
            for d in pg.get_drawings():
                r = d.get("rect")
                if r is None:
                    continue
                db = to_display((r.x0, r.y0, r.x1, r.y1), rot, w, h)
                if not intersect(db, rb):
                    continue
                if (db[2] - db[0]) * (db[3] - db[1]) > 4:
                    drawings += 1
                    if hdr_bottom is not None and db[1] >= hdr_bottom - 1:
                        drawings_below += 1
            images = 0
            for im in pg.get_image_info():
                bb = im.get("bbox")
                if bb is None:
                    continue
                if intersect(to_display(tuple(bb), rot, w, h), rb):
                    images += 1
            rows.append({"key": key, "page": page, "q": f.get("q"), "bbox": f["bbox"],
                         "rotation": rot, "lines": len(lines),
                         "header_bottom": None if hdr_bottom is None else round(hdr_bottom, 1),
                         "lines_below_header": [t[:60] for t in below],
                         "drawings": drawings, "drawings_below_header": drawings_below,
                         "images": images,
                         "text_inside": f.get("text_inside"),
                         "next_row_below": f.get("next_row_below"),
                         "above_all_rows": f.get("above_all_rows"),
                         "no_data_below_header": not below and drawings_below == 0 and images == 0})
    for d in doc_cache.values():
        d.close()
    nodata = [r for r in rows if r["no_data_below_header"]]
    json.dump({"regions": rows, "count": len(rows), "no_data_below_header": len(nodata)},
              open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"regions={len(rows)} no_data_below_header={len(nodata)}")
    print()
    print("== 表头带下方仍有内容的区域（不能当悬空删除） ==")
    for r in rows:
        if not r["no_data_below_header"]:
            print(f'  {r["key"]} p{r["page"]} q={r["q"]} bbox={r["bbox"]} '
                  f'hdr_bottom={r["header_bottom"]} below={r["lines_below_header"]} '
                  f'draw_below={r["drawings_below_header"]} img={r["images"]}')
    print("written", OUT)


if __name__ == "__main__":
    main()
