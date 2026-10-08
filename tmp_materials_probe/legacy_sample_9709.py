# -*- coding: utf-8 -*-
"""§5C sampling: for each 9709 event in 2013-11.json, locate the literal PDF row,
find the day bracket containing it, and confirm the bracket's day label."""
import json
import sys
from pathlib import Path

import pymupdf

sys.path.insert(0, str(Path("examdata/src")))
from examdata.timetable import parser as P  # noqa: E402

base = Path("examdata/src/examdata/timetable/data/zone5")
events = [e for e in json.loads((base / "2013-11.json").read_text(encoding="utf-8"))["events"]
          if e["subject_code"] == "9709"]
pdf = Path("tmp_materials_probe/downloads/zone5_gap7/2013-11.pdf")
doc = pymupdf.open(pdf)

rows = []
for page in doc:
    if not P._is_legacy_weekly_page(page.get_text()):
        continue
    spans = P._legacy_page_spans(page)
    brackets = []
    for d in page.get_drawings():
        r = d["rect"]
        items = d.get("items", [])
        if len(items) == 4 and all(i[0] == "l" for i in items) and (r.y1 - r.y0) > 80:
            brackets.append((round(r.y0, 1), round(r.y1, 1)))
    brackets.sort()
    labels = [(y, c) for (y, x0, _, t) in spans if x0 < 100 and (c := P._legacy_clean(t)) and P._legacy_parse_label(c)]
    for (y, x0, x1, t) in spans:
        c = P._legacy_clean(t)
        if c and c.startswith("9709/"):
            br = [i for i, (b0, b1) in enumerate(brackets) if b0 <= y <= b1]
            lab = [lc for (ly, lc) in labels if br and brackets[br[0]][0] <= ly <= brackets[br[0]][1]]
            row_spans = sorted(
                (round(x0, 1), P._legacy_clean(t2)) for (yy, x0, x1, t2) in spans
                if abs(yy - y) <= 3 and 100 < x0 < 460
            )
            rows.append({"page": page.number + 1, "y": y, "code": c, "bracket": br,
                         "label": lab, "literal": row_spans})

for e in events:
    code = f"9709/{e['paper_code']}"
    print(f"\n== event {e['date']} {e['weekday']} {e['session']} {code} {e['duration_raw']} ({e['level']}) ==")
    for r in [r for r in rows if r["code"] == code]:
        print(f"   PDF p{r['page']} y={r['y']:.1f} bracket={r['bracket']} label={r['label']}")
        print(f"   literal spans: {r['literal']}")
