#!/usr/bin/env python
"""S08 scratch OCR sweep: OCR all pages of a book PDF at given DPI, JSONL append per page.

Usage:
  ocr_sweep.py --book 9 --out out.jsonl [--dpi 150] [--pages 1-165] [--start 1]
Output: one JSON per line: {"file_page":N,"width":..,"height":..,"dpi":D,"words":[{"text","conf","x0","y0","x1","y1"}],"elapsed_s":..}
"""
import argparse
import json
import sys
import time
from pathlib import Path

import pymupdf as fitz

PDFS = Path("C:/Users/weo/Desktop/api/tmp_audit_ielts/downloads")


def parse_pages(spec, total):
    pages = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-")
            pages.extend(range(int(a), int(b) + 1))
        else:
            pages.append(int(part))
    return [p for p in pages if 1 <= p <= total]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--book", type=int, required=True)
    ap.add_argument("--pdf")
    ap.add_argument("--out", required=True)
    ap.add_argument("--dpi", type=float, default=150.0)
    ap.add_argument("--pages", default="")
    args = ap.parse_args()

    from rapidocr_onnxruntime import RapidOCR

    pdf = Path(args.pdf) if args.pdf else PDFS / f"book_{args.book}.pdf"
    ocr = RapidOCR()
    doc = fitz.open(pdf)
    total = len(doc)
    pages = parse_pages(args.pages, total) if args.pages else list(range(1, total + 1))

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for fp in pages:
            page = doc[fp - 1]
            t0 = time.time()
            pix = page.get_pixmap(matrix=fitz.Matrix(args.dpi / 72.0, args.dpi / 72.0), alpha=False)
            import numpy as np

            img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
            if pix.n == 4:
                img = img[:, :, :3]
            result, _ = ocr(img)
            scale = 72.0 / args.dpi
            words = []
            if result:
                for box, text, conf in result:
                    pts = [[round(p[0] * scale, 2), round(p[1] * scale, 2)] for p in box]
                    xs = [p[0] for p in pts]
                    ys = [p[1] for p in pts]
                    words.append({
                        "text": text,
                        "conf": round(float(conf), 4),
                        "x0": min(xs), "x1": max(xs), "y0": min(ys), "y1": max(ys),
                    })
            words.sort(key=lambda w: (w["y0"], w["x0"]))
            rec = {
                "file_page": fp,
                "width": round(pix.width * scale, 2),
                "height": round(pix.height * scale, 2),
                "dpi": args.dpi,
                "words": words,
                "elapsed_s": round(time.time() - t0, 2),
            }
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            f.flush()
            preview = " ".join(w["text"] for w in words[:8])
            print(f"page {fp}/{total}: {len(words)} words, {rec['elapsed_s']}s :: {preview[:90]}", flush=True)
    print("done", out)


if __name__ == "__main__":
    main()
