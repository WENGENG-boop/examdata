"""dump intgcse/2021-11 p11/p16 与 2022-06 p12/p17 的表头与前几行，判断是否 subject-view 表。"""

import re
from pathlib import Path

import pymupdf

BASE = Path("downloads/edexcel")


def clean(t):
    return re.sub(r"\s+", " ", str(t or "")).strip()


TARGETS = [
    ("intgcse/2021-11.pdf", [5, 6, 11, 16]),
    ("intgcse/2022-06.pdf", [5, 7, 12, 17]),
    ("intgcse/2018-06.pdf", None),
    ("intgcse/2019-01.pdf", None),
    ("intgcse/2021-06.pdf", None),
]

for rel, pages in TARGETS:
    path = BASE / rel
    doc = pymupdf.open(path)
    print("#" * 30, rel, "pages:", doc.page_count)
    for pno in range(doc.page_count):
        if pages is not None and (pno + 1) not in pages:
            continue
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
            print(f"  p{pno + 1} table{ti}: {t.row_count}x{t.col_count} hdr={hdr}")
            for ri, r in enumerate(rows[1:4], start=1):
                cells = [clean(c) for c in r]
                print(f"      r{ri}: {cells}")
    doc.close()
