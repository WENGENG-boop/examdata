"""Scan all gap PDFs for span texts containing given substrings."""
import sys
import fitz

NEEDLES = sys.argv[1:] or ["0607", "8004", "0581", "General Paper", "Mathematics 2"]
FILES = ["2013-11", "2014-06", "2014-11", "2015-06", "2015-11", "2016-06", "2016-11"]

for fname in FILES:
    doc = fitz.open(f"tmp_materials_probe/downloads/zone5_gap7/{fname}.pdf")
    for page in doc:
        for block in page.get_text("dict")["blocks"]:
            if block["type"] != 0:
                continue
            for line in block["lines"]:
                for span in line["spans"]:
                    t = span["text"]
                    if any(n in t for n in NEEDLES):
                        y = round(span["bbox"][1], 1)
                        x0 = round(span["bbox"][0], 1)
                        print(f"{fname} p{page.number + 1} y={y:7.1f} x0={x0:6.1f} {t!r}")
