#!/usr/bin/env python
"""G14b OCR sweep: book9 full (165p); book16/18/19 listening+audioscripts+keys.
Outputs per-book JSON; incremental save after each page.
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
DL = ROOT / "tmp_audit_ielts/downloads"

JOBS = {
    "g14b-scan-book9.json": (DL / "book_9.pdf", list(range(1, 166))),
    "g14b-scan-book16.json": (DL / "book_16.pdf",
                              list(range(9, 19)) + list(range(31, 41)) + list(range(54, 64))
                              + list(range(75, 85)) + list(range(97, 131))),
    "g14b-scan-book18.json": (DL / "book_18.pdf",
                              list(range(9, 19)) + list(range(32, 42)) + list(range(54, 64))
                              + list(range(77, 87)) + list(range(98, 129))),
    "g14b-scan-book19.json": (DL / "book_19.pdf",
                              list(range(9, 19)) + list(range(32, 42)) + list(range(54, 64))
                              + list(range(77, 87)) + list(range(98, 130))),
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
    print("ALL DONE", flush=True)


if __name__ == "__main__":
    main()
