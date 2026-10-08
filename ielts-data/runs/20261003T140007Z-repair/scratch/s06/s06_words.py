#!/usr/bin/env python3
"""S06 scratch probe: dump every word with coordinates for chosen pages.

Usage: python s06_words.py <book> <page> [<page>...]
Prints rows sorted by (y, x):  y | x0-x1 | text
"""
import sys
import pathlib

import pymupdf

ROOT = pathlib.Path("C:/Users/weo/Desktop/api")
DOWNLOADS = ROOT / "tmp_audit_ielts" / "downloads"


def main():
    book = sys.argv[1]
    pages = [int(p) for p in sys.argv[2:]]
    pdf = DOWNLOADS / f"book_{book}.pdf"
    doc = pymupdf.open(str(pdf))
    for pno in pages:
        page = doc[pno - 1]
        print(f"===== page {pno} (printed? {page.get_text('text').strip().splitlines()[-1] if page.get_text('text').strip() else '?'}) =====")
        words = page.get_text("words")
        for w in sorted(words, key=lambda w: (round(w[1], 1), w[0])):
            print(f"{w[1]:7.1f} | {w[0]:6.1f}-{w[2]:6.1f} | {w[4]}")
    doc.close()


if __name__ == "__main__":
    main()
