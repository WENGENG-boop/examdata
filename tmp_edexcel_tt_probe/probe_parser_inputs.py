"""动笔写 edexcel_parser.py 前的最后一批结构探测。"""

import json
import re
from pathlib import Path

import pymupdf

BASE = Path("downloads/edexcel")


def clean(t):
    return re.sub(r"\s+", " ", str(t or "")).strip()


def dump(rows, n=8, width=90):
    for r in rows[:n]:
        print("   ", [repr(c)[:width] for c in r])


print("=" * 20, "A: intgcse/2022-01 master + modern 对照")
doc = pymupdf.open(BASE / "intgcse/2022-01.pdf")
page = doc[3]
rows = page.find_tables().tables[0].extract()
print("master shape", len(rows), "x", len(rows[0]), "hdr:", rows[0])
dump(rows[1:5], 4)
found = {}
for pno in range(doc.page_count):
    if pno == 3:
        continue
    for t in doc[pno].find_tables().tables:
        rows = t.extract()
        if not rows:
            continue
        hdr = [clean(c).lower() for c in rows[0]]
        if hdr and hdr[0] == "date":
            if pno + 1 not in found:
                print(f"modern p{pno+1} shape {len(rows)}x{len(rows[0])} hdr {[clean(c) for c in rows[0]]}")
                dump(rows[1:4], 3)
            found[pno + 1] = True
            for r in rows[1:]:
                code = clean(r[1]) if len(r) > 1 else ""
                if code in {"4CH1 1C", "4HB1 01", "4SD0 1C"}:
                    print("   MATCH", [repr(c)[:110] for c in r])

print()
print("=" * 20, "B: intgcse/2020-01 p2/p3 小表")
doc = pymupdf.open(BASE / "intgcse/2020-01.pdf")
for pno in [1, 2]:
    page = doc[pno]
    page.set_rotation(0)
    for t in page.find_tables().tables:
        rows = t.extract()
        if not rows:
            continue
        print(f"p{pno+1} shape {len(rows)}x{len(rows[0])}")
        dump(rows[:7], 7, 120)

print()
print("=" * 20, "C: gce/2016-06 p4 window + cells API")
doc = pymupdf.open(BASE / "gce/2016-06.pdf")
page = doc[3]
for t in page.find_tables().tables:
    rows = t.extract()
    print("shape", len(rows), "x", len(rows[0]), "hdr", rows[0])
    dump(rows[1:], 6, 120)
    try:
        print("rows[1].cells:", t.rows[1].cells)
    except Exception as exc:  # noqa: BLE001
        print("cells API err:", type(exc).__name__, exc)

print()
print("=" * 20, "D: gce/2017-06 p4 date cell raw")
doc = pymupdf.open(BASE / "gce/2017-06.pdf")
page = doc[3]
for t in page.find_tables().tables:
    rows = t.extract()
    print("shape", len(rows), "x", len(rows[0]), "hdr", rows[0])
    dump(rows[1:], 6, 150)

print()
print("=" * 20, "E: modern 代码列空但其他列非空的行（样本）")
targets = [
    "gce/2020-10.pdf",
    "gcse/2019-06.pdf",
    "ial/2021-06.pdf",
    "intgcse/2021-06.pdf",
    "gce/2015-06.pdf",
    "gcse/2020-11.pdf",
]
count = 0
for name in targets:
    doc = pymupdf.open(BASE / name)
    for pno in range(doc.page_count):
        page = doc[pno]
        for t in page.find_tables().tables:
            rows = t.extract()
            if not rows:
                continue
            hdr = [clean(c).lower() for c in rows[0]]
            if not hdr or hdr[0] != "date":
                continue
            for r in rows[1:]:
                cells = [clean(c) for c in r]
                if len(cells) < 2:
                    continue
                if not cells[1] and any(cells[2:]):
                    count += 1
                    if count <= 15:
                        print(f"{name} p{pno+1}:", [repr(c)[:80] for c in r])
print("total code-empty rows:", count)

print()
print("=" * 20, "F: manifest R 键 / unobtainable 形状 / 文件名")
m = json.loads(Path("downloads/edexcel_manifest.json").read_text(encoding="utf-8"))
rkeys = [k for k in m["seasons"] if k.endswith("|R")]
print("R keys:", len(rkeys), rkeys)
for k, v in m["seasons"].items():
    if v.get("status") == "unobtainable":
        slim = {kk: vv for kk, vv in v.items() if kk != "attempts"}
        print("unobtainable", k, json.dumps(slim, ensure_ascii=False)[:400])
print("cancelled:", json.dumps(m["cancelled"], ensure_ascii=False)[:500])
for fam in ["gcse", "intgcse", "ial", "gce"]:
    names = sorted(p.name for p in (BASE / fam).glob("*.pdf"))
    print(fam, len(names), names)
