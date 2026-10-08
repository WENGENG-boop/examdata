"""dump intgcse/2020-01 与 2020-06-r 的全部表格（含所有行），理解 blob 形态。"""

import re
from pathlib import Path

import pymupdf

BASE = Path("downloads/edexcel")

TARGETS = ["intgcse/2020-01.pdf", "intgcse/2020-06-r.pdf", "intgcse/2020-01-r.pdf", "intgcse/2020-11-r.pdf"]


def cellrepr(c, limit=200):
    s = str(c or "")
    if len(s) > limit:
        s = s[:limit] + "…"
    return s


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
            print(f"  == p{pno + 1} t{ti}: {t.row_count}x{t.col_count}")
            for ri, r in enumerate(rows):
                for ci, c in enumerate(r):
                    if c is None:
                        continue
                    s = str(c)
                    if not s.strip():
                        continue
                    print(f"     r{ri}c{ci}: {cellrepr(c)!r}")
                print("     ----")
    doc.close()
