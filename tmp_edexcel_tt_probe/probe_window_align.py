"""窗口表几何配对：坐标级 dump（gce/2017-06 为全库唯一「2 窗口 vs 3 单元」形态）。"""

import re
from pathlib import Path

import pymupdf

BASE = Path("downloads/edexcel")


def clean(t):
    return re.sub(r"\s+", " ", str(t or "")).strip()


def dump_table(path, pno_hint=None):
    doc = pymupdf.open(path)
    for pno in range(doc.page_count):
        if pno_hint is not None and pno + 1 != pno_hint:
            continue
        page = doc[pno]
        if page.rotation:
            page.set_rotation(0)
        for t in page.find_tables().tables:
            rows = t.extract()
            if not rows:
                continue
            hdr = [clean(c).lower() for c in rows[0]]
            while hdr and hdr[-1] == "":
                hdr.pop()
            if hdr[:2] != ["date", "unit"] and hdr[:2] != ["date", ""]:
                continue
            print(f"########## {path} p{pno+1} table {t.row_count}x{t.col_count}")
            for ri, row in enumerate(t.rows):
                print(f"  ROW {ri} bbox={tuple(round(v, 1) for v in row.bbox)}")
                for ci, cell in enumerate(row.cells):
                    if cell is None:
                        print(f"    c{ci}: None")
                        continue
                    rect = pymupdf.Rect(cell)
                    words = page.get_text("words", clip=rect)
                    # cluster by y
                    lines = {}
                    for w in words:
                        x0, y0, x1, y1, word = w[0], w[1], w[2], w[3], w[4]
                        key = round((y0 + y1) / 2)
                        lines.setdefault(key, []).append((x0, word))
                    print(f"    c{ci}: rect={tuple(round(v,1) for v in cell)}")
                    for y in sorted(lines):
                        txt = " ".join(w for _, w in sorted(lines[y]))
                        print(f"       y~{y}: {txt!r}")
            print()
    doc.close()


dump_table(BASE / "gce/2017-06.pdf")
dump_table(BASE / "gce/2015-06.pdf")
dump_table(BASE / "gce/2016-06.pdf")
