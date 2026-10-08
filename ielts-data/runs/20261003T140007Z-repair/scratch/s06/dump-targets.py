#!/usr/bin/env python3
"""S06d: dump specific target pages for books 8/11/12/17."""
import pymupdf

ROOT = "C:/Users/weo/Desktop/api/tmp_audit_ielts/downloads"
TARGETS = {
    8: [64, 65, 66, 67, 68],
    11: [38, 39, 40, 41, 58, 59, 60, 61, 62],
    12: [54, 55, 56, 57, 58, 59],
    17: [53, 54, 55, 56, 57, 58],
}
for b, pages in TARGETS.items():
    doc = pymupdf.open(f"{ROOT}/book_{b}.pdf")
    for p in pages:
        print(f"\n########## book {b} fp{p} ##########")
        print(doc[p - 1].get_text())
    doc.close()
