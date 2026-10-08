"""探测 Edexcel 时间表 PDF 版式（三）：Subject view 页与后续页（用于跳过规则）。"""

from pathlib import Path

import pymupdf

BASE = Path(r"C:/Users/weo/Desktop/api/tmp_edexcel_tt_probe")

CASES = [
    ("2015 gcse", BASE / "downloads/edexcel/gcse/2015-06.pdf", [6, 7, 10, 24]),
    ("2017-01 intgcse", BASE / "downloads/content_check/International_GCSE_Timetable.pdf", [5, 6, 12]),
    ("2026-06 intgcse", BASE / "downloads/edexcel/intgcse/2026-06.pdf", [4, 8, 12, 24]),
    ("2018-06 gce", BASE / "downloads/edexcel/gce/2018-06.pdf", [4, 5, 20, 32]),
]

for tag, path, pages in CASES:
    if not path.exists():
        print(f"MISSING {path}")
        continue
    print(f"\n{'#'*110}\n# {tag}  {path.name}  (pages={pymupdf.open(str(path)).page_count})")
    doc = pymupdf.open(str(path))
    for pi in pages:
        if pi >= doc.page_count:
            continue
        page = doc[pi]
        flat = " ".join(page.get_text().split())
        print(f"\n---- page {pi} ----")
        print("TEXT:", flat[:300])
        for ti, t in enumerate(page.find_tables().tables):
            rows = t.extract()
            print(f"  table{ti}: {len(rows)}x{len(rows[0]) if rows else 0}")
            for ri, r in enumerate(rows[:4]):
                print(f"    row{ri}:", [repr(c)[:70] for c in r])
    doc.close()
