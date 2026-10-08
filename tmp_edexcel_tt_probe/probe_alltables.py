"""dump 指定文件全部页面的表格表头/行数/首行，检查整体结构。"""

import re
from pathlib import Path

import pymupdf

BASE = Path("downloads/edexcel")


def clean(t):
    return re.sub(r"\s+", " ", str(t or "")).strip()


TARGETS = [
    "intgcse/2021-11.pdf",
    "intgcse/2022-01.pdf",
    "intgcse/2020-01.pdf",
    "intgcse/2020-06-r.pdf",
    "intgcse/2021-06.pdf",
]

for rel in TARGETS:
    path = BASE / rel
    doc = pymupdf.open(path)
    print("#" * 30, rel, "pages:", doc.page_count)
    for pno in range(doc.page_count):
        page = doc[pno]
        if page.rotation:
            page.set_rotation(0)
        try:
            tabs = page.find_tables().tables
        except Exception as e:
            print(f"  p{pno + 1} <find_tables failed: {e}>")
            continue
        for ti, t in enumerate(tabs):
            rows = t.extract()
            hdr = [clean(c) for c in rows[0]] if rows else []
            first = [clean(c) for c in rows[1]] if len(rows) > 1 else []
            print(f"  p{pno + 1} t{ti}: {t.row_count}x{t.col_count} hdr={hdr}")
            if first:
                print(f"       r1={first}")
    doc.close()
