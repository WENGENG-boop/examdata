"""全库扫描:非旋转 master 表分布 + 旋转 9 行表分布 + intgcse/2022-01 去重签名实测。"""

import re
from pathlib import Path

import pymupdf

BASE = Path("downloads/edexcel")

MASTER_HDR = [
    "date",
    "exam series",
    "board",
    "qual",
    "examination code",
    "subject",
    "title",
    "time",
    "duration",
]


def clean(t):
    return re.sub(r"\s+", " ", str(t or "")).strip()


print("=" * 20, "1) 非旋转 master 表扫描 (全库)")
for pdf in sorted(BASE.glob("*/*.pdf")):
    doc = pymupdf.open(pdf)
    for pno in range(doc.page_count):
        page = doc[pno]
        for t in page.find_tables().tables:
            rows = t.extract()
            if not rows or len(rows[0]) != 9:
                continue
            hdr = [clean(c).lower() for c in rows[0]]
            if hdr == MASTER_HDR:
                nonempty = sum(1 for r in rows[1:] if clean(r[4]))
                print(f"  {pdf.parent.name}/{pdf.name} p{pno + 1} {len(rows)}x9 events={nonempty}")

print()
print("=" * 20, "2) 旋转 9 行表扫描 (全库, set_rotation(0))")
for pdf in sorted(BASE.glob("*/*.pdf")):
    doc = pymupdf.open(pdf)
    hits = []
    for pno in range(doc.page_count):
        page = doc[pno]
        page.set_rotation(0)
        for t in page.find_tables().tables:
            rows = t.extract()
            if not rows or len(rows) != 9:
                continue
            if clean(rows[0][0]) == "Exam duration":
                hits.append(f"p{pno + 1}({len(rows[0])}c)")
    if hits:
        print(f"  {pdf.parent.name}/{pdf.name}: {hits}")

print()
print("=" * 20, "3) intgcse/2022-01 去重签名实测 (master vs modern)")
doc = pymupdf.open(BASE / "intgcse/2022-01.pdf")


def d_master(s):
    m = re.match(r"(\d{2})/(\d{2})/(\d{4})$", clean(s))
    return (int(m.group(1)), int(m.group(2))) if m else None


def d_modern(s):
    m = re.search(r"(\d{1,2})\s+([A-Z][a-z]+)", clean(s))
    if not m:
        return None
    months = "January February March April May June July August September October November December".split()
    try:
        return (int(m.group(1)), months.index(m.group(2)) + 1)
    except ValueError:
        return None


def combo(subj, title):
    subj, title = clean(subj), clean(title)
    if not title:
        return subj
    if title.lower().startswith(subj.lower()):
        return title
    return f"{subj} {title}"


master = {}
page = doc[3]
rows = page.find_tables().tables[0].extract()
for r in rows[1:]:
    r = [clean(c) for c in r]
    if not r[0] or not r[4]:
        continue
    master[r[4]] = (d_master(r[0]), r[7], combo(r[5], r[6]), r[8])

modern = {}
for pno in range(doc.page_count):
    if pno == 3:
        continue
    for t in doc[pno].find_tables().tables:
        rows = t.extract()
        if not rows:
            continue
        hdr = [clean(c).lower() for c in rows[0]]
        if not hdr or hdr[0] != "date":
            continue
        date_cur = time_cur = None
        for r in rows[1:]:
            r = [clean(c) for c in r]
            if r[0]:
                date_cur = r[0]
            if len(r) > 4 and r[4]:
                time_cur = r[4]
            code = r[1]
            if code and len(r) > 5:
                modern[code] = (d_modern(date_cur or ""), time_cur, combo(r[2], r[3]), r[5])

print("master n:", len(master), "modern n:", len(modern))
for c in sorted(set(master) | set(modern)):
    a, b = master.get(c), modern.get(c)
    if a != b:
        print("DIFF", c)
        print("   master:", a)
        print("   modern:", b)
print("done. common codes:", len(set(master) & set(modern)))
