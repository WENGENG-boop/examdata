"""全库表头形态清点：每个 PDF 每页每表输出 行x列 + 表头签名（前 2 行截断）。"""

import re
from pathlib import Path

import pymupdf

BASE = Path("downloads/edexcel")


def clean(t):
    return re.sub(r"\s+", " ", str(t or "")).strip()


def sig(cells):
    out = []
    for c in cells[:9]:
        s = clean(c)
        if len(s) > 40:
            s = s[:40] + "…"
        out.append(s)
    return out


for path in sorted(BASE.rglob("*.pdf")):
    doc = pymupdf.open(path)
    print("#" * 20, path.relative_to(BASE))
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
            hdr = sig(rows[0]) if rows else []
            print(f"  p{pno + 1} t{ti}: {t.row_count}x{t.col_count} hdr={hdr}")
    doc.close()
