"""探测 Edexcel 时间表 PDF 版式：文本 + find_tables 结构（各年代抽样）。"""

import json
import sys
from pathlib import Path

import pymupdf

BASE = Path(r"C:/Users/weo/Desktop/api/tmp_edexcel_tt_probe")

SAMPLES = [
    ("2015 gcse", BASE / "downloads/edexcel/gcse/2015-06.pdf"),
    ("2017-01 intgcse", BASE / "downloads/content_check/International_GCSE_Timetable.pdf"),
    ("2018-01 gcse", BASE / "downloads/content_check/57065-gcse-timetable-january-2018-final.pdf"),
    ("2018-06 gce", BASE / "downloads/edexcel/gce/2018-06.pdf"),
    ("2018-06 intgcse R", BASE / "downloads/edexcel/intgcse/2018-06-r.pdf"),
    ("2019-10 ial", BASE / "downloads/content_check/october-2019-timetable-provisional_20190923.pdf"),
    ("2021-06 intgcse special", BASE / "downloads/content_check/Apr_May_2021_FINAL_Int_GCSE.pdf"),
    ("2021-06 intgcse june", BASE / "downloads/content_check/June-2021-Final-Int-GCSE.pdf"),
    ("2026-06 intgcse", BASE / "downloads/edexcel/intgcse/2026-06.pdf"),
]


def cell(v):
    if v is None:
        return ""
    return " ".join(str(v).split())[:60]


out = []
for tag, path in SAMPLES:
    if not path.exists():
        print(f"== {tag}: MISSING {path}")
        continue
    doc = pymupdf.open(str(path))
    print(f"\n{'='*100}\n== {tag}  {path.name}  pages={doc.page_count}")
    rec = {"tag": tag, "file": str(path), "pages": doc.page_count, "pages_info": []}
    for pi in range(min(4, doc.page_count)):
        page = doc[pi]
        text = page.get_text()
        flat = " ".join(text.split())
        tables = page.find_tables().tables
        tinfo = []
        for t in tables:
            rows = t.extract()
            tinfo.append({"bbox": [round(x, 1) for x in t.bbox], "nrows": len(rows),
                          "ncols": len(rows[0]) if rows else 0,
                          "first_rows": [[cell(c) for c in r] for r in rows[:7]]})
        rec["pages_info"].append({"page": pi, "text_head": flat[:500], "tables": tinfo})
        print(f"-- page {pi} tables={len(tables)} text: {flat[:180]}")
        for ti, t in enumerate(tinfo):
            print(f"   table{ti} bbox={t['bbox']} {t['nrows']}x{t['ncols']}")
            for r in t["first_rows"][:6]:
                print("     |", " | ".join(r))
    out.append(rec)
    doc.close()

(BASE / "evidence/layout_probe.json").write_text(
    json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print("\nsaved evidence/layout_probe.json")
