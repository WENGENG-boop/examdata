#!/usr/bin/env python3
"""S06d: scan book PDFs for "Questions N-M" headers and empty pages."""
import json
import pathlib
import re
import sys

import pymupdf

ROOT = pathlib.Path("C:/Users/weo/Desktop/api")
DOWNLOADS = ROOT / "tmp_audit_ielts" / "downloads"

HDR_RE = re.compile(r"Questions?\s*(\d{1,3})\s*[-\u2013\u2014]\s*(\d{1,3})")

books = [int(a) for a in sys.argv[1:]] or [8, 11, 12, 17]

out = {}
for book in books:
    pdf = DOWNLOADS / f"book_{book}.pdf"
    doc = pymupdf.open(pdf)
    pages = []
    for i, page in enumerate(doc):
        text = page.get_text()
        words = len(text.split())
        hdrs = [f"{m.group(1)}-{m.group(2)}" for m in HDR_RE.finditer(text)]
        entry = {"p": i + 1, "w": words}
        if hdrs:
            entry["q"] = hdrs
        if words < 12:
            entry["empty"] = True
        pages.append(entry)
    out[book] = {"n_pages": doc.page_count, "pages": pages}
    doc.close()

print(json.dumps(out, ensure_ascii=False))
