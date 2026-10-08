"""Dump 9396 MS PDF text spans with coordinates (unrotated space) to a file."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import pymupdf

PDF = Path(r"C:/Users/weo/Desktop/api/cie-location-batch/tmp/9396/2023-Nov-11/9396_w23_ms_11.pdf")
OUT = Path(r"C:/Users/weo/Desktop/api/cie-location-batch/work/codex_verify/9396-ms-textdump.txt")

doc = pymupdf.open(PDF)
lines = []
for pno in range(5, 15):
    page = doc[pno - 1]
    lines.append(f"===== PAGE {pno} rot={page.rotation} rect={page.rect} =====")
    spans = []
    d = page.get_text("dict")
    for block in d["blocks"]:
        if block.get("type") != 0:
            continue
        for ln in block["lines"]:
            for sp in ln["spans"]:
                t = sp["text"].strip()
                if not t:
                    continue
                x0, y0, x1, y1 = sp["bbox"]
                spans.append((round(x0, 1), round(y0, 1), round(x1, 1), round(y1, 1), t))
    spans.sort(key=lambda s: (s[0], s[1]))
    for x0, y0, x1, y1, t in spans:
        lines.append(f"x[{x0:6.1f},{x1:6.1f}] y[{y0:6.1f},{y1:6.1f}]  {t}")
    lines.append("")
doc.close()
OUT.write_text("\n".join(lines), encoding="utf-8")
print(f"wrote {OUT} ({len(lines)} lines)")
