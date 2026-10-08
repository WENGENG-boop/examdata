#!/usr/bin/env python3
"""S06 scratch probe: dump rawdict chars in a bbox region of a page."""
import sys
import pathlib

import pymupdf

ROOT = pathlib.Path("C:/Users/weo/Desktop/api")
DOWNLOADS = ROOT / "tmp_audit_ielts" / "downloads"


def main():
    book, page_no = sys.argv[1], int(sys.argv[2])
    x0, y0, x1, y1 = [float(v) for v in sys.argv[3:7]]
    pdf = DOWNLOADS / f"book_{book}.pdf"
    doc = pymupdf.open(str(pdf))
    page = doc[page_no - 1]
    raw = page.get_text("rawdict")
    print(f"===== page {page_no} region ({x0},{y0})-({x1},{y1}) =====")
    for block in raw["blocks"]:
        if block.get("type") != 0:
            print(f"[image block bbox={block['bbox']}]")
            continue
        for line in block["lines"]:
            for span in line["spans"]:
                for ch in span["chars"]:
                    cx, cy = ch["bbox"][0], ch["bbox"][1]
                    if x0 <= cx <= x1 and y0 <= cy <= y1:
                        print(
                            f"{ch['bbox'][1]:7.1f} | {ch['bbox'][0]:6.1f}-{ch['bbox'][2]:6.1f} | "
                            f"c={ch['c']!r} font={span['font']} size={span['size']:.1f}"
                        )
    doc.close()


if __name__ == "__main__":
    main()
