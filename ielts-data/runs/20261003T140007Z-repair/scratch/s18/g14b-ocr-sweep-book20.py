#!/usr/bin/env python
"""G14b OCR sweep book20: full coverage of all 4 test PDFs (130 pages).
book20 = 4 separate test PDFs in ielts-data/raw/pdf-source/ (no text layer).
Outputs per-test JSON; incremental save every 10 pages.
"""
import json
import time
from pathlib import Path

import fitz
import numpy as np
from rapidocr_onnxruntime import RapidOCR

ROOT = Path("C:/Users/weo/Desktop/api")
R = ROOT / "ielts-data/runs/20261003T140007Z-repair"
S18 = R / "scratch/s18"
SRC = ROOT / "ielts-data/raw/pdf-source"

JOBS = {
    "g14b-scan-book20-test1.json": (SRC / "book20-test1.pdf", list(range(1, 35))),
    "g14b-scan-book20-test2.json": (SRC / "book20-test2.pdf", list(range(1, 36))),
    "g14b-scan-book20-test3.json": (SRC / "book20-test3.pdf", list(range(1, 32))),
    "g14b-scan-book20-test4.json": (SRC / "book20-test4.pdf", list(range(1, 31))),
}

DPI = 300.0


def run(name, pdf, pages, ocr):
    out = S18 / name
    if out.exists():
        print(f"skip existing {name}", flush=True)
        return
    doc = fitz.open(str(pdf))
    res = {"pdf": str(pdf), "dpi": DPI, "pages": []}
    for fp in pages:
        page = doc[fp - 1]
        t0 = time.time()
        pix = page.get_pixmap(matrix=fitz.Matrix(DPI / 72.0, DPI / 72.0), alpha=False)
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
        if pix.n == 4:
            img = img[:, :, :3]
        result, _ = ocr(img)
        scale = 72.0 / DPI
        words = []
        if result:
            for box, text, conf in result:
                pts = [[round(p[0] * scale, 2), round(p[1] * scale, 2)] for p in box]
                xs = [p[0] for p in pts]
                ys = [p[1] for p in pts]
                words.append({"text": text, "conf": round(float(conf), 4),
                              "x0": min(xs), "x1": max(xs), "y0": min(ys), "y1": max(ys)})
        words.sort(key=lambda w: (w["y0"], w["x0"]))
        res["pages"].append({"file_page": fp, "words": words, "elapsed_s": round(time.time() - t0, 2)})
        if fp % 10 == 0 or fp == pages[-1]:
            out.write_text(json.dumps(res, ensure_ascii=False, indent=0), encoding="utf-8")
        print(f"{name} p{fp}: {len(words)}w {res['pages'][-1]['elapsed_s']}s", flush=True)
    out.write_text(json.dumps(res, ensure_ascii=False, indent=0), encoding="utf-8")
    print(f"DONE {name}", flush=True)


def main():
    ocr = RapidOCR()
    for name, (pdf, pages) in JOBS.items():
        run(name, pdf, pages, ocr)
    print("ALL DONE book20", flush=True)


if __name__ == "__main__":
    main()
