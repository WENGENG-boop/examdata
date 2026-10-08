"""写解析器前最后复查：各版式实际表头 + 首数据行。"""

import re
from pathlib import Path

import pymupdf

BASE = Path("downloads/edexcel")


def clean(t):
    return re.sub(r"\s+", " ", str(t or "")).strip()


TARGETS = [
    "gce/2013-06.pdf",
    "gce/2015-06.pdf",
    "gce/2016-06.pdf",
    "gce/2017-06.pdf",
    "gce/2020-10.pdf",
    "ial/2019-06.pdf",
    "ial/2021-06.pdf",
    "intgcse/2014-06.pdf",
    "intgcse/2019-06.pdf",
    "intgcse/2021-06.pdf",
    "gcse/2013-06.pdf",
    "gcse/2019-06.pdf",
    "gcse/2023-06.pdf",
]

for name in TARGETS:
    path = BASE / name
    if not path.exists():
        print("#" * 12, name, "MISSING")
        continue
    doc = pymupdf.open(path)
    print("#" * 12, name, f"pages={doc.page_count}")
    for pno in range(doc.page_count):
        page = doc[pno]
        if page.rotation:
            page.set_rotation(0)
        for t in page.find_tables().tables:
            rows = t.extract()
            if not rows:
                continue
            hdr = [clean(c) for c in rows[0]]
            first = [repr(c)[:70] for c in (rows[1] if len(rows) > 1 else [])]
            print(f"  p{pno+1} {len(rows)}x{len(rows[0])} hdr={hdr}")
            print(f"       r1={first}")
    doc.close()
