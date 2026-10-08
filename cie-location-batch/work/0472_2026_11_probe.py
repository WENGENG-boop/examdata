# -*- coding: utf-8 -*-
"""Probe MS table rows and QP question-number text-layer coordinates for 0472/2026/Jun/11."""
import json
import sys
from pathlib import Path

import fitz

BR = Path(r"C:/Users/weo/Desktop/api/cie-location-batch")
TMP = BR / "tmp" / "0472" / "2026-Jun-11"
OUT = BR / "work" / "0472_2026_11_probe.json"

qp = TMP / "0472_s26_qp_11.pdf"
ms = TMP / "0472_s26_ms_11.pdf"

result = {"qp": {"pages": []}, "ms": {"pages": []}}

for role, path in (("qp", qp), ("ms", ms)):
    doc = fitz.open(path)
    for i, page in enumerate(doc):
        r = page.rect
        entry = {"page": i + 1, "rect": [r.x0, r.y0, r.x1, r.y1], "rotation": page.rotation, "lines": []}
        d = page.get_text("dict")
        for block in d["blocks"]:
            if block.get("type") != 0:
                continue
            for line in block["lines"]:
                text = "".join(span["text"] for span in line["spans"])
                if not text.strip():
                    continue
                bbox = line["bbox"]
                entry["lines"].append({
                    "text": text,
                    "bbox": [round(v, 1) for v in bbox],
                })
        entry["lines"].sort(key=lambda x: (round(x["bbox"][1]), x["bbox"][0]))
        result[role]["pages"].append(entry)
    doc.close()

OUT.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
print("written", OUT)

# quick summary: ms p2/p3 lines that look like table rows
for p in result["ms"]["pages"]:
    print(f"== MS page {p['page']} rect={p['rect']} rot={p['rotation']} lines={len(p['lines'])}")
for p in result["qp"]["pages"]:
    print(f"== QP page {p['page']} rect={p['rect']} rot={p['rotation']} lines={len(p['lines'])}")
