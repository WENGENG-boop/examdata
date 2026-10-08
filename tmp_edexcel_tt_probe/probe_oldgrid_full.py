"""old grid 完整单元格文本（不截断），用于写条目拆分/时长对齐代码。"""

import re
from pathlib import Path

import pymupdf

BASE = Path("downloads/edexcel")

TARGETS = [
    ("gce/2015-06.pdf", None),
    ("gce/2016-06.pdf", None),
    ("gce/2017-06.pdf", None),
    ("ial/2017-06.pdf", None),
    ("ial/2018-01.pdf", None),
    ("intgcse/2015-01-r.pdf", None),
]


def clean(t):
    return re.sub(r"\s+", " ", str(t or "")).strip()


for name, _ in TARGETS:
    doc = pymupdf.open(BASE / name)
    print("#" * 14, name)
    shown = 0
    for pno in range(doc.page_count):
        page = doc[pno]
        if page.rotation:
            page.set_rotation(0)
        for t in page.find_tables().tables:
            rows = t.extract()
            if not rows:
                continue
            hdr = [clean(c).lower() for c in rows[0]]
            if hdr[:2] not in (["date", "morning"], ["date", "morning session"]):
                continue
            print(f"=== p{pno+1} {len(rows)}x{len(rows[0])}")
            for r in rows[1:3]:
                for ci, c in enumerate(r):
                    print(f"   [c{ci}] {c!r}")
                print("   ----")
            shown += 1
            if shown >= 4:
                break
        if shown >= 4:
            break
    doc.close()
