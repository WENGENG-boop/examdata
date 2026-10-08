"""把 64 个「已删除的表头带悬空区域」渲染成联页对照图，供人工/子代理目视复核。

每张联页图 4 列：每列 = 该页显示坐标 [52,748]×[34,128] 的竖直条带裁剪，
用红框标出被删除的条带（band）边界，列顶标注 key/page/q/类别。
输出 visual/_headerband/sheet-XX.png + manifest.json
"""
import json
import os
import sys

import pymupdf

A = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, A)
from ms_row_audit import pdf_for  # noqa: E402

LIST = os.path.join(A, "deliverables", "ms-header-band-fix-list.json")
OUTDIR = os.path.join(A, "visual", "_headerband")
SCALE = 3
PER_SHEET = 4
X0, X1 = 52.0, 748.0     # 显示 x 范围（横向）
Y0, Y1 = 34.0, 128.0     # 显示 y 范围（纵向）


def main():
    os.makedirs(OUTDIR, exist_ok=True)
    items = json.load(open(LIST, encoding="utf-8"))["items"]
    items.sort(key=lambda i: (i["key"], i["page"], i["q"]))
    docs = {}
    sheets = []
    for si in range(0, len(items), PER_SHEET):
        chunk = items[si:si + PER_SHEET]
        tiles = []
        for it in chunk:
            key = it["key"]
            if key not in docs:
                docs[key] = pymupdf.open(pdf_for(key, "ms"))
            pg = docs[key][it["page"] - 1]
            h = pg.mediabox.height
            clip = pymupdf.Rect(Y0, h - X1, Y1, h - X0)   # rot=90: x=显示y, y=h-显示x
            pm = pg.get_pixmap(matrix=pymupdf.Matrix(1, 1), clip=clip)
            tiles.append((it, pm))

        tw, th = tiles[0][1].width, tiles[0][1].height
        gap, label_h = 8, 16
        sheet_w = len(tiles) * (tw + gap) + gap
        sheet_h = label_h + th + gap
        doc = pymupdf.open()
        page = doc.new_page(width=sheet_w, height=sheet_h)
        for i, (it, pm) in enumerate(tiles):
            x = gap + i * (tw + gap)
            page.insert_image(pymupdf.Rect(x, label_h, x + tw, label_h + th), pixmap=pm)
            lab = "%s p%d %s" % (it["key"].replace("/", " "), it["page"], it["q"])
            page.insert_text((x + 1, label_h - 4), lab, fontsize=7)
            b = it["bbox_display"]
            for yy in (b[1], b[3]):
                py = label_h + (yy - Y0)
                if 0 <= py <= label_h + th:
                    page.draw_line(pymupdf.Point(x, py), pymupdf.Point(x + tw, py),
                                   color=(1, 0, 0), width=0.6)
        name = "sheet-%02d.png" % (si // PER_SHEET + 1)
        page.get_pixmap(matrix=pymupdf.Matrix(SCALE, SCALE)).save(os.path.join(OUTDIR, name))
        doc.close()
        sheets.append({"sheet": name, "columns": [
            {"key": it["key"], "page": it["page"], "q": it["q"],
             "classification": it["classification"],
             "lines_below_header": it["lines_below_header"],
             "drawings_below_header": it["drawings_below_header"],
             "bbox_display": it["bbox_display"]} for it in chunk]})
    json.dump({"sheets": sheets, "scale": SCALE, "display_window": [X0, X1, Y0, Y1],
               "note": "红线上/下界之间即被删除的条带；条带下方紧邻的是该页首个题号行"},
              open(os.path.join(OUTDIR, "manifest.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("sheets", len(sheets), "->", OUTDIR)


if __name__ == "__main__":
    main()
