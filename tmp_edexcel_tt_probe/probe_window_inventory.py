"""全库窗口表形态清点：找出所有含 '(Window)' 的表格，dump 表头与相关单元格（截断）。"""

import re
from pathlib import Path

import pymupdf

BASE = Path("downloads/edexcel")


def clean(t):
    return re.sub(r"\s+", " ", str(t or "")).strip()


def cellrepr(c, limit=160):
    s = str(c or "")
    if len(s) > limit:
        s = s[:limit] + "…"
    return s


for path in sorted(BASE.rglob("*.pdf")):
    doc = pymupdf.open(path)
    hits = []
    for pno in range(doc.page_count):
        page = doc[pno]
        if page.rotation:
            page.set_rotation(0)
        try:
            tabs = page.find_tables().tables
        except Exception as e:
            hits.append((pno + 1, f"<find_tables failed: {e}>", None))
            continue
        for ti, t in enumerate(tabs):
            rows = t.extract()
            flat = " ".join(clean(c) for r in rows for c in r)
            if "(window)" not in flat.lower():
                continue
            hdr = [clean(c).lower() for c in rows[0]] if rows else []
            while hdr and hdr[-1] == "":
                hdr.pop()
            hits.append((pno + 1, f"{t.row_count}x{t.col_count} hdr={hdr}", rows))
    if hits:
        print("#" * 20, path.relative_to(BASE))
        for pno, desc, rows in hits:
            print(f"  p{pno} {desc}")
            if rows:
                for ri, r in enumerate(rows[:6]):
                    for ci, c in enumerate(r):
                        if c is None:
                            continue
                        s = str(c)
                        if not s.strip():
                            continue
                        print(f"     r{ri}c{ci}: {cellrepr(c)!r}")
                    print("     ----")
    doc.close()
