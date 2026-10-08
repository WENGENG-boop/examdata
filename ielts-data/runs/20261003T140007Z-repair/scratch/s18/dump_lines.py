#!/usr/bin/env python
"""S18 scratch: dump rawdict lines with tokenization for answer-key pages.

Usage: dump_lines.py <book> <page> [xmin] [xmax]
Prints each y-line: y0, then tokens (gap>4.5 split) as x0:text
"""
import sys

import pymupdf

DOWNLOADS = "C:/Users/weo/Desktop/api/tmp_audit_ielts/downloads"


def main():
    book = sys.argv[1]
    page_no = int(sys.argv[2])
    xmin = float(sys.argv[3]) if len(sys.argv) > 3 else 0
    xmax = float(sys.argv[4]) if len(sys.argv) > 4 else 9999
    doc = pymupdf.open(f"{DOWNLOADS}/book_{book}.pdf")
    pg = doc[page_no - 1]
    d = pg.get_text("rawdict")
    chars = []
    for blk in d["blocks"]:
        if blk["type"] != 0:
            continue
        for ln in blk["lines"]:
            for sp in ln["spans"]:
                for ch in sp["chars"]:
                    x0, y0, x1, y1 = ch["bbox"]
                    if x0 < xmin or x0 > xmax:
                        continue
                    chars.append((x0, y0, x1, y1, ch["c"], sp["font"], round(sp["size"], 1)))
    # group into y-lines (tol 3.5)
    chars.sort(key=lambda t: (t[1], t[0]))
    lines = []
    for c in chars:
        if lines and c[1] - lines[-1][-1][1] <= 3.5:
            lines[-1].append(c)
        else:
            lines.append([c])
    for ln in lines:
        ln.sort(key=lambda t: t[0])
        y0 = min(t[1] for t in ln)
        toks = []
        cur = [ln[0]]
        for prev, c in zip(ln, ln[1:]):
            if c[0] - prev[2] > 4.5:
                toks.append(cur)
                cur = [c]
            else:
                cur.append(c)
        toks.append(cur)
        desc = " | ".join(
            f"{t[0][0]:.1f}:{''.join(x[4] for x in t).strip()}" for t in toks if "".join(x[4] for x in t).strip()
        )
        fonts = ",".join(sorted({t[0][5] for t in toks}))
        if desc:
            print(f"y={y0:7.2f} [{fonts}] {desc}")


if __name__ == "__main__":
    main()
