# -*- coding: utf-8 -*-
"""Cross-check parser attribution vs visual day brackets on all 7 legacy PDFs.

For every weekly page:
  - brackets = 4-segment line paths with height > 80 (the gray margin brackets)
  - band_ys  = clustered 'Syllabus/Component' header span ys (parser's blocks)
  - check A: bracket midpoints map to distinct consecutive block indexes
  - check B: every day-label span (margin x<100) lies inside some bracket and
             block_of(label_y) == that bracket's block index
  - check C: every data-row span lies inside some bracket and
             block_of(row_y) == that bracket's block index
"""
import sys
from pathlib import Path

import pymupdf

sys.path.insert(0, str(Path("examdata/src")))
from examdata.timetable import parser as P  # noqa: E402

PDFS = sorted(Path("tmp_materials_probe/downloads/zone5_gap7").glob("*.pdf"))
failures = 0
pages_checked = 0
rows_checked = 0
labels_checked = 0

for pdf in PDFS:
    doc = pymupdf.open(pdf)
    for page in doc:
        if not P._is_legacy_weekly_page(page.get_text()):
            continue
        pages_checked += 1
        spans = P._legacy_page_spans(page)
        band_ys = P._legacy_cluster_ys(
            [y for (y, _x0, _x1, t) in spans if "Syllabus" in t and "Component" in t]
        )
        brackets = []
        for d in page.get_drawings():
            r = d["rect"]
            items = d.get("items", [])
            if len(items) == 4 and all(i[0] == "l" for i in items) and (r.y1 - r.y0) > 80:
                brackets.append((round(r.y0, 1), round(r.y1, 1)))
        brackets.sort()

        def block_of(y: float) -> int | None:
            idx = None
            for i, by in enumerate(band_ys):
                if y >= by - 6:
                    idx = i
            return idx

        def bracket_of(y: float) -> int | None:
            for i, (b0, b1) in enumerate(brackets):
                if b0 <= y <= b1:
                    return i
            return None

        tag = f"{pdf.name} p{page.number + 1}"
        if len(brackets) != len(band_ys):
            print(f"[FAIL-count] {tag}: {len(brackets)} brackets vs {len(band_ys)} header bands")
            failures += 1
            continue
        for i, (b0, b1) in enumerate(brackets):
            mid = (b0 + b1) / 2
            if block_of(mid) != i:
                print(f"[FAIL-A] {tag}: bracket{i} mid={mid:.1f} -> block {block_of(mid)}")
                failures += 1
        for (y, x0, x1, t) in spans:
            cleaned = P._legacy_clean(t)
            if not cleaned or P._legacy_is_noise(cleaned):
                continue
            if "Syllabus" in cleaned and "Component" in cleaned:
                continue
            if x0 < 100:
                # day label or margin glyph; only weekday/day text matters
                if P._legacy_parse_label(cleaned) is None:
                    continue
                labels_checked += 1
                b = bracket_of(y)
                if b is None or block_of(y) != b:
                    print(f"[FAIL-B] {tag}: label {cleaned!r} y={y:.1f} bracket={b} block={block_of(y)}")
                    failures += 1
                continue
            if x0 >= 140 and y > band_ys[0] - 5:
                if cleaned in ("Code", "Duration"):
                    continue
                b = bracket_of(y)
                if b is None or block_of(y) != b:
                    print(f"[FAIL-C] {tag}: row {cleaned[:50]!r} y={y:.1f} bracket={b} block={block_of(y)}")
                    failures += 1
                rows_checked += 1

print(f"\npages={pages_checked} labels_checked={labels_checked} rows_checked={rows_checked} failures={failures}")
