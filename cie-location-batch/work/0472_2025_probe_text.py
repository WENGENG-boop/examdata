"""Probe text layer of 0472/2025 QP for planned fix regions."""
import pymupdf as fitz
from pathlib import Path

BR = Path(r"C:/Users/weo/Desktop/api/cie-location-batch")
QP = BR / "tmp/0472/2025-Jun-11/0472_s25_qp_11.pdf"

doc = fitz.open(QP)
print("pages:", len(doc))

# planned regions to inspect: (page1based, y0, y1, label)
probes = [
    (3, 58.8, 144.4, "Q1 header (Questions 1-8?)"),
    (3, 144.4, 363.2, "Q1 content"),
    (6, 34.8, 161.2, "Q9 header?"),
    (6, 161.2, 355.2, "Q9 content"),
    (8, 34.8, 470.8, "Q15 header?"),
    (8, 470.8, 507.6, "Q15 content"),
    (9, 34.8, 218.0, "Q20 header?"),
    (9, 218.0, 353.6, "Q20 content"),
    (12, 58.8, 168.8, "Q29 header?"),
    (12, 168.8, 334.4, "Q29 content"),
    (14, 58.8, 168.8, "Q35 header?"),
    (14, 168.8, 352.0, "Q35 content"),
    (10, 194.4, 332.0, "Q24 new"),
    (10, 332.0, 415.6, "Q25 header part2?"),
    (10, 415.6, 551.2, "Q25 content"),
]

for page_no, y0, y1, label in probes:
    page = doc[page_no - 1]
    d = page.get_text("dict")
    print(f"\n===== p{page_no} [{y0},{y1}] {label} =====")
    for block in d["blocks"]:
        if block.get("type") != 0:
            print(f"  [IMAGE block bbox={[round(x,1) for x in block['bbox']]}]")
            continue
        for line in block["lines"]:
            lb = line["bbox"]
            cy = (lb[1] + lb[3]) / 2
            if y0 - 2 <= cy <= y1 + 2:
                txt = "".join(s["text"] for s in line["spans"])
                print(f"  y={lb[1]:.1f}-{lb[3]:.1f} x={lb[0]:.1f}-{lb[2]:.1f} | {txt}")
doc.close()
