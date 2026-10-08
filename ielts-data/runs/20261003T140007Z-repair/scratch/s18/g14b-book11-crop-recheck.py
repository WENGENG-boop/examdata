#!/usr/bin/env python
"""G14b: high-DPI crop recheck of book_11.pdf p124 (t4R key) letter values.
Strips chosen from 400dpi OCR coordinates (PDF points).
"""
import json
import time
from pathlib import Path

import fitz
import numpy as np
from rapidocr_onnxruntime import RapidOCR

ROOT = Path("C:/Users/weo/Desktop/api")
S18 = ROOT / "ielts-data/runs/20261003T140007Z-repair/scratch/s18"
PDF = ROOT / "tmp_audit_ielts/downloads/book_11.pdf"

STRIPS = [
    ("p124-L-Q1-4",   (18, 110, 80, 160)),
    ("p124-L-Q5-9",   (18, 158, 80, 216)),
    ("p124-L-Q10-13", (18, 214, 80, 262)),
    ("p124-L-Q14-19", (18, 300, 80, 378)),
    ("p124-R-Q20-26", (240, 80, 285, 168)),
    ("p124-R-Q27-36", (240, 200, 285, 320)),
    ("p124-R-Q37-40", (240, 314, 285, 366)),
]
DPI = 600.0


def main():
    ocr = RapidOCR()
    doc = fitz.open(str(PDF))
    page = doc[124 - 1]
    out = {"pdf": str(PDF), "file_page": 124, "dpi": DPI, "strips": []}
    for name, (x0, y0, x1, y1) in STRIPS:
        rect = fitz.Rect(x0, y0, x1, y1)
        t0 = time.time()
        pix = page.get_pixmap(matrix=fitz.Matrix(DPI / 72.0, DPI / 72.0), clip=rect, alpha=False)
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
        if pix.n == 4:
            img = img[:, :, :3]
        result, _ = ocr(img)
        scale = 72.0 / DPI
        words = []
        if result:
            for box, text, conf in result:
                pts = [[round(x0 + p[0] * scale, 2), round(y0 + p[1] * scale, 2)] for p in box]
                xs = [p[0] for p in pts]
                ys = [p[1] for p in pts]
                words.append({"text": text, "conf": round(float(conf), 4),
                              "x0": min(xs), "x1": max(xs), "y0": min(ys), "y1": max(ys)})
        words.sort(key=lambda w: (w["y0"], w["x0"]))
        out["strips"].append({"strip": name, "rect": [x0, y0, x1, y1], "words": words,
                              "elapsed_s": round(time.time() - t0, 2)})
        print(f"{name}: " + " | ".join(f"{w['text']}({w['y0']:.0f})" for w in words), flush=True)
    (S18 / "g14b-book11-p124-crops.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("wrote g14b-book11-p124-crops.json", flush=True)


if __name__ == "__main__":
    main()
