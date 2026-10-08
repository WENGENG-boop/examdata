"""探测 Edexcel 时间表 PDF 版式（二）：原始单元格换行结构 + 后续页（Subject view）结构。"""

import json
from pathlib import Path

import pymupdf

BASE = Path(r"C:/Users/weo/Desktop/api/tmp_edexcel_tt_probe")

CASES = [
    ("2015 gcse", BASE / "downloads/edexcel/gcse/2015-06.pdf", [3, 4, 5]),
    ("2017-01 intgcse", BASE / "downloads/content_check/International_GCSE_Timetable.pdf", [3, 4]),
    ("2018-01 gcse", BASE / "downloads/content_check/57065-gcse-timetable-january-2018-final.pdf", [3]),
    ("2017 IAL", BASE / "downloads/content_check/IAL_provisional_Examination_Dates_20170622.pdf", [3, 4]),
    ("2018-06 gce", BASE / "downloads/edexcel/gce/2018-06.pdf", [3, 4]),
    ("2021-06 intgcse", BASE / "downloads/content_check/June-2021-Final-Int-GCSE.pdf", [3]),
    ("2026-06 intgcse", BASE / "downloads/edexcel/intgcse/2026-06.pdf", [3, 12]),
]


def show(tag, path, pages):
    print(f"\n{'#'*110}\n# {tag}  {path.name}")
    doc = pymupdf.open(str(path))
    for pi in pages:
        if pi >= doc.page_count:
            continue
        page = doc[pi]
        print(f"\n---- page {pi} ----")
        flat = " ".join(page.get_text().split())
        print("TEXT:", flat[:260])
        for ti, t in enumerate(page.find_tables().tables):
            rows = t.extract()
            print(f"  table{ti}: {len(rows)}x{len(rows[0]) if rows else 0}")
            for ri, r in enumerate(rows[:5]):
                print(f"    row{ri}:")
                for ci, c in enumerate(r):
                    print(f"      c{ci}: {c!r}")
    doc.close()


for tag, path, pages in CASES:
    if not path.exists():
        print(f"MISSING {path}")
        continue
    show(tag, path, pages)
