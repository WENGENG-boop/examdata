# -*- coding: utf-8 -*-
"""Refined check: both bracket styles (4-line path, filled gray rect) + gap rows.

Rules:
  - bracket styles: (a) 4 'l' segments h>80 ; (b) gray filled rect w in [30,80], h in [60,400], x0 < 110
  - for each row/label: k = block_of(y) from header bands.
      * if y inside bracket j  -> require j == k
      * else (gap / below last): require bracket k exists and y is within
        [bracket_k.y1, bracket_{k+1}.y0] (or below last bracket), i.e. the row
        cannot belong to any other day.
"""
import sys
from pathlib import Path

import pymupdf

sys.path.insert(0, str(Path("examdata/src")))
from examdata.timetable import parser as P  # noqa: E402

PDFS = [p for p in sorted(Path("tmp_materials_probe/downloads/zone5_gap7").glob("*.pdf")) if ".alt-" not in p.name]
failures = 0
pages = rows_checked = labels_checked = 0
gap_rows = 0

for pdf in PDFS:
    doc = pymupdf.open(pdf)
    for page in doc:
        if not P._is_legacy_weekly_page(page.get_text()):
            continue
        pages += 1
        spans = P._legacy_page_spans(page)
        band_ys = P._legacy_cluster_ys(
            [y for (y, _x0, _x1, t) in spans if "Syllabus" in t and "Component" in t]
        )
        brackets = []
        for d in page.get_drawings():
            r = d["rect"]
            items = d.get("items", [])
            itypes = [i[0] for i in items]
            if len(items) == 4 and all(t == "l" for t in itypes) and (r.y1 - r.y0) > 80:
                brackets.append((round(r.y0, 1), round(r.y1, 1)))
            elif (
                itypes == ["re"]
                and d.get("type") == "f"
                and 30 <= (r.x1 - r.x0) <= 80
                and 60 <= (r.y1 - r.y0) <= 400
                and r.x0 < 110
                and d.get("fill")
                and abs(d["fill"][0] - 0.5) < 0.05
            ):
                brackets.append((round(r.y0, 1), round(r.y1, 1)))
        brackets.sort()
        tag = f"{pdf.name} p{page.number + 1}"

        def block_of(y: float) -> int | None:
            idx = None
            for i, by in enumerate(band_ys):
                if y >= by - 6:
                    idx = i
            return idx

        if len(brackets) != len(band_ys):
            print(f"[FAIL-count] {tag}: {len(brackets)} brackets vs {len(band_ys)} bands {brackets}")
            failures += 1
            continue

        def check(kind: str, y: float, text: str) -> None:
            global failures, gap_rows
            k = block_of(y)
            if k is None:
                print(f"[FAIL-noblock] {tag} {kind} {text!r} y={y:.1f}")
                failures += 1
                return
            for j, (b0, b1) in enumerate(brackets):
                if b0 <= y <= b1:
                    if j != k:
                        print(f"[FAIL-in] {tag} {kind} {text!r} y={y:.1f} in bracket{j} but block{k}")
                        failures += 1
                    return
            lo = brackets[k][1]
            hi = brackets[k + 1][0] if k + 1 < len(brackets) else 1e9
            if lo <= y <= hi:
                gap_rows += 1
                return
            print(f"[FAIL-out] {tag} {kind} {text!r} y={y:.1f} block{k} not in [{lo},{hi}]")
            failures += 1

        for (y, x0, x1, t) in spans:
            cleaned = P._legacy_clean(t)
            if not cleaned or P._legacy_is_noise(cleaned):
                continue
            if "Syllabus" in cleaned and "Component" in cleaned:
                continue
            if x0 < 100:
                if P._legacy_parse_label(cleaned) is None:
                    continue
                labels_checked += 1
                check("label", y, cleaned)
                continue
            if x0 >= 140 and y > band_ys[0] - 5 and cleaned not in ("Code", "Duration"):
                rows_checked += 1
                check("row", y, cleaned[:40])

print(f"\npages={pages} labels={labels_checked} rows={rows_checked} gap_rows={gap_rows} failures={failures}")
