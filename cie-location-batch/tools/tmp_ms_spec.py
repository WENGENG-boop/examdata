import json
import re
from pathlib import Path

import propose as PR

MS = Path(r"../tmp/8386/2026-Jun-11/8386_s26_ms_11.pdf")
OUT = Path(r"../work/proposals/8386/spec-ms.json")

PR.MS_LABEL_RE = re.compile(r"^\d{1,2}(?:\([a-z]\)(?:\([ivx]+\))?)?$")
doc = PR.read_doc(MS)
warnings = []
rows = PR.ms_rows(doc, warnings)

spec = []
for r in rows:
    if r["page"] < 7:
        continue
    x0, y0, x1, y1 = r["row_bbox"]
    spec.append({
        "label": r["label"],
        "role": "ms",
        "page": r["page"],
        "bbox": [x0, max(58.0, y0), x1, min(734.0, y1)],
    })

for pno, lab in ((2, "MS p2 full general-principles"), (5, "MS p5 full"), (6, "MS p6 full")):
    spec.append({"label": lab, "role": "ms", "page": pno, "bbox": [58.0, 58.0, 735.0, 734.0]})

OUT.write_text(json.dumps(spec, ensure_ascii=False, indent=1), encoding="utf-8")
print("rows", len(rows), "spec", len(spec))
print("warnings:", *warnings, sep="\n  ")
for s in spec:
    print(s["page"], s["label"], [round(v, 1) for v in s["bbox"]])
