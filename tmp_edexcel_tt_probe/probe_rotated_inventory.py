"""旋转文件全表清单 + intgcse/2020-01 blob 表是否被主表覆盖。"""

import re
from pathlib import Path

import pymupdf

BASE = Path("downloads/edexcel")
ROT = [
    "ial/2020-01.pdf",
    "intgcse/2020-01.pdf",
    "intgcse/2020-01-r.pdf",
    "intgcse/2020-06-r.pdf",
]

CODE_RE = re.compile(r"\b([0-9][A-Z0-9]{2,5})\s+([0-9][A-Z0-9]{1,2}(?:-[A-Z0-9]{1,3})?)\b")


def clean(t):
    return re.sub(r"\s+", " ", str(t or "")).strip()


def codes_in(text):
    return {f"{a} {b}" for a, b in CODE_RE.findall(text)}


for name in ROT:
    doc = pymupdf.open(BASE / name)
    print("#" * 10, name, "pages:", doc.page_count)
    for pno in range(doc.page_count):
        page = doc[pno]
        page.set_rotation(0)
        for t in page.find_tables().tables:
            rows = t.extract()
            if not rows:
                continue
            shape = f"{len(rows)}x{len(rows[0])}"
            first = clean(rows[0][0])[:55] if rows[0] else ""
            all_text = " ".join(clean(c) for r in rows for c in r)
            n = len(codes_in(all_text))
            print(f"  p{pno + 1} {shape} | {first!r} | codes~{n}")

print()
print("=" * 20, "intgcse/2020-01 duplicate check")
doc = pymupdf.open(BASE / "intgcse/2020-01.pdf")
main_codes: set[str] = set()
other_codes: set[str] = set()
for pno in range(doc.page_count):
    page = doc[pno]
    page.set_rotation(0)
    for t in page.find_tables().tables:
        rows = t.extract()
        if not rows:
            continue
        text = " ".join(clean(c) for r in rows for c in r)
        cs = codes_in(text)
        if len(rows) == 9:
            main_codes |= cs
        else:
            other_codes |= cs
print("main (9-row) codes:", len(main_codes))
print("other codes:", len(other_codes))
print("other - main:", sorted(other_codes - main_codes))
print("main - other:", sorted(main_codes - other_codes))
print("main sample:", sorted(main_codes)[:40])
