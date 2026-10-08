# -*- coding: utf-8 -*-
"""Probe exact glyph bytes for the 3 open punctuation points of 0472/2026/Jun/41.

- QP p2: form fields (Your name / Your age / What day you can help) punctuation
- QP p4: 3(b) last bullet "travel next[,] and why" comma presence; bullet char
- MS p7/p9/p11: readable text layer for cross-reference (comma / dash forms)

Writes work/_text_align_0472_41.txt
"""
import io
import pymupdf

BR = r"C:/Users/weo/Desktop/api/cie-location-batch"
QP = BR + "/tmp/0472/2026-Jun-41/0472_s26_qp_41.pdf"
MS = BR + "/tmp/0472/2026-Jun-41/0472_s26_ms_41.pdf"

out = io.StringIO()


def dump_qp(pno, ymin, ymax):
    doc = pymupdf.open(QP)
    page = doc[pno]
    out.write(f"##### QP page {pno + 1} (y {ymin}..{ymax}) #####\n")
    d = page.get_text("dict")
    for block in d["blocks"]:
        if block["type"] != 0:
            continue
        for line in block["lines"]:
            y0, y1 = line["bbox"][1], line["bbox"][3]
            if not (ymin <= y0 <= ymax):
                continue
            out.write(f"y {y0:7.1f}-{y1:7.1f} x {line['bbox'][0]:7.1f}-{line['bbox'][2]:7.1f}\n")
            for s in line["spans"]:
                cp = " ".join(f"{ord(c):04X}" for c in s["text"])
                out.write(f"    [{s['font']} {round(s['size'], 1)}] {s['text']!r}\n")
                out.write(f"      cps: {cp}\n")
    doc.close()
    out.write("\n")


def dump_ms(pno):
    doc = pymupdf.open(MS)
    page = doc[pno]
    out.write(f"##### MS page {pno + 1} (full text) #####\n")
    d = page.get_text("dict")
    for block in d["blocks"]:
        if block["type"] != 0:
            continue
        for line in block["lines"]:
            txt = "".join(s["text"] for s in line["spans"])
            out.write(f"y {line['bbox'][1]:7.1f} x {line['bbox'][0]:7.1f} {txt!r}\n")
    doc.close()
    out.write("\n")


dump_qp(1, 80, 520)   # p2: Q1 form
dump_qp(3, 80, 430)   # p4: Q3 / 3(a) / 3(b)
dump_ms(6)            # p7: Q1 answer table
dump_ms(8)            # p9: Q2
dump_ms(10)           # p11: Q3

with open(BR + "/work/_text_align_0472_41.txt", "w", encoding="utf-8") as f:
    f.write(out.getvalue())
print("saved", len(out.getvalue()), "chars")
