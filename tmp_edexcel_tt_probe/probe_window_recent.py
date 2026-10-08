"""检查 intgcse 2021+ 及 gce/2015-06 p2 中 'Window' 文本的上下文：是真实窗口条目还是说明文字。"""

import re
from pathlib import Path

import pymupdf

BASE = Path("downloads/edexcel")

TARGETS = [
    "intgcse/2021-11.pdf",
    "intgcse/2022-06.pdf",
    "intgcse/2023-06.pdf",
    "intgcse/2023-11.pdf",
    "intgcse/2024-06.pdf",
    "intgcse/2024-11.pdf",
    "intgcse/2025-06.pdf",
    "intgcse/2025-11.pdf",
    "intgcse/2026-06.pdf",
    "intgcse/2026-11.pdf",
    "intgcse/2027-06.pdf",
    "gce/2015-06.pdf",
]


def clean(t):
    return re.sub(r"\s+", " ", str(t or "")).strip()


for rel in TARGETS:
    path = BASE / rel
    if not path.exists():
        print(f"### MISSING {rel}")
        continue
    doc = pymupdf.open(path)
    print("#" * 30, rel)
    for pno in range(doc.page_count):
        page = doc[pno]
        if page.rotation:
            page.set_rotation(0)
        text = page.get_text()
        if "window" not in text.lower():
            continue
        print(f"  == p{pno + 1} ==")
        for m in re.finditer(r"(?i)window", text):
            a = max(0, m.start() - 120)
            b = min(len(text), m.end() + 120)
            snippet = text[a:b].replace("\n", "\\n")
            print(f"    ...{snippet}...")
        try:
            tabs = page.find_tables().tables
        except Exception as e:
            print(f"    <find_tables failed: {e}>")
            tabs = []
        for ti, t in enumerate(tabs):
            rows = t.extract()
            flat = " ".join(clean(c) for r in rows for c in r)
            mark = " <== TABLE HAS WINDOW" if "window" in flat.lower() else ""
            print(f"    table{ti}: {t.row_count}x{t.col_count}{mark}")
    doc.close()
