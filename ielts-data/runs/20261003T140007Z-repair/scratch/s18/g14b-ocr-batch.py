#!/usr/bin/env python
"""G14b OCR batch:
  A) ToC hunt for books 9/16/18/19 (no text layer) -> g14b-toc-bookN.json
  B) book20 test1-4 listening parts 1-2 pages -> g14b-ocr20-testN-pXX.json
  C) book11 key pages 123/124 high-DPI recheck -> g14b-book11-keys-p123-124.json
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

JOBS = [
    (DL / "book_9.pdf", [2, 3, 4, 5, 6], 300, S18 / "g14b-toc-book9.json"),
    (DL / "book_16.pdf", [2, 3, 4, 5, 6], 300, S18 / "g14b-toc-book16.json"),
    (DL / "book_18.pdf", [2, 3, 4, 5, 6], 300, S18 / "g14b-toc-book18.json"),
    (DL / "book_19.pdf", [2, 3, 4, 5, 6], 300, S18 / "g14b-toc-book19.json"),
    (ROOT / "ielts-data/raw/pdf-source/book20-test1.pdf", [2, 3, 4], 250, S18 / "g14b-ocr20-test1-p234.json"),
    (ROOT / "ielts-data/raw/pdf-source/book20-test2.pdf", [3, 4], 250, S18 / "g14b-ocr20-test2-p34.json"),
    (ROOT / "ielts-data/raw/pdf-source/book20-test3.pdf", [3, 4], 250, S18 / "g14b-ocr20-test3-p34.json"),
    (ROOT / "ielts-data/raw/pdf-source/book20-test4.pdf", [3, 4], 250, S18 / "g14b-ocr20-test4-p34.json"),
    (DL / "book_11.pdf", [123, 124], 400, S18 / "g14b-book11-keys-p123-124.json"),
]


def main():
    ocr = RapidOCR()
    for pdf, pages, dpi, out in JOBS:
        if out.exists():
            print(f"skip existing {out.name}", flush=True)
            continue
        doc = fitz.open(str(pdf))
        res = {"pdf": str(pdf), "dpi": dpi, "pages": []}
        for fp in pages:
            page = doc[fp - 1]
            t0 = time.time()
            pix = page.get_pixmap(matrix=fitz.Matrix(dpi / 72.0, dpi / 72.0), alpha=False)
            img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
            if pix.n == 4:
                img = img[:, :, :3]
            result, _ = ocr(img)
            scale = 72.0 / dpi
            words = []
            if result:
                for box, text, conf in result:
                    pts = [[round(p[0] * scale, 2), round(p[1] * scale, 2)] for p in box]
                    xs = [p[0] for p in pts]
                    ys = [p[1] for p in pts]
                    words.append({
                        "text": text, "conf": round(float(conf), 4), "box": pts,
                        "x0": min(xs), "x1": max(xs), "y0": min(ys), "y1": max(ys),
                    })
            words.sort(key=lambda w: (w["y0"], w["x0"]))
            res["pages"].append({
                "file_page": fp,
                "width": round(pix.width * scale, 2),
                "height": round(pix.height * scale, 2),
                "words": words,
                "elapsed_s": round(time.time() - t0, 2),
            })
            print(f"{pdf.name} p{fp}: {len(words)} words {res['pages'][-1]['elapsed_s']}s", flush=True)
        out.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"wrote {out}", flush=True)
    print("ALL DONE", flush=True)


if __name__ == "__main__":
    main()
