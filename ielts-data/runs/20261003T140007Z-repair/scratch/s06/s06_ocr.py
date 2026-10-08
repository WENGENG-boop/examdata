#!/usr/bin/env python
"""S06 scratch OCR: render PDF pages and OCR them with rapidocr (word boxes + confidence).

Usage:
  s06_ocr.py --book 3 --pages 37 58 --out out.json --imgdir imgdir [--dpi 300] [--rect x0,y0,x1,y1]

--rect applies to all pages (PDF point coords, origin top-left) to crop a region before OCR.
Output JSON: {"pages":[{"file_page":N,"width":W,"height":H,"dpi":D,"rect":[...],"words":[{"text":..,"conf":..,"box":[[x,y]*4],"y0":..,"x0":..}],"elapsed_s":..}]}
Coordinates in output are PDF points (converted back from pixels when --rect or dpi used).
"""
import argparse
import json
import sys
import time
from pathlib import Path

import fitz  # pymupdf

PDFS = Path("C:/Users/weo/Desktop/api/tmp_audit_ielts/downloads")


def resolve_pdf(book=None, pdf=None):
    if pdf:
        return Path(pdf)
    return PDFS / f"book_{book}.pdf"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--book", type=int)
    ap.add_argument("--pdf")
    ap.add_argument("--pages", required=True, help="comma separated 1-based file pages")
    ap.add_argument("--out", required=True)
    ap.add_argument("--imgdir", help="if set, save rendered PNGs here")
    ap.add_argument("--dpi", type=float, default=300.0)
    ap.add_argument("--rect", help="x0,y0,x1,y1 in PDF points; crop all pages to this region")
    ap.add_argument("--max-pages", type=int, default=0)
    args = ap.parse_args()

    from rapidocr_onnxruntime import RapidOCR

    ocr = RapidOCR()
    doc = fitz.open(resolve_pdf(args.book, args.pdf))
    pages = [int(p) for p in args.pages.split(",") if p.strip()]
    if args.max_pages:
        pages = pages[: args.max_pages]
    rect = None
    if args.rect:
        rect = fitz.Rect(*[float(v) for v in args.rect.split(",")])
    imgdir = Path(args.imgdir) if args.imgdir else None
    if imgdir:
        imgdir.mkdir(parents=True, exist_ok=True)

    out = {"pdf": str(resolve_pdf(args.book, args.pdf)), "dpi": args.dpi, "pages": []}
    for fp in pages:
        page = doc[fp - 1]
        clip = rect if rect else None
        t0 = time.time()
        pix = page.get_pixmap(matrix=fitz.Matrix(args.dpi / 72.0, args.dpi / 72.0), clip=clip, alpha=False)
        if imgdir:
            pix.save(str(imgdir / f"p{fp:04d}.png"))
        import numpy as np

        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
        if pix.n == 4:
            img = img[:, :, :3]
        result, _ = ocr(img)
        scale = 72.0 / args.dpi
        ox, oy = (clip.x0, clip.y0) if clip else (0.0, 0.0)
        words = []
        if result:
            for box, text, conf in result:
                pts = [[round(ox + p[0] * scale, 2), round(oy + p[1] * scale, 2)] for p in box]
                xs = [p[0] for p in pts]
                ys = [p[1] for p in pts]
                words.append({
                    "text": text,
                    "conf": round(float(conf), 4),
                    "box": pts,
                    "x0": min(xs), "x1": max(xs), "y0": min(ys), "y1": max(ys),
                })
        words.sort(key=lambda w: (w["y0"], w["x0"]))
        out["pages"].append({
            "file_page": fp,
            "width": round(pix.width * scale, 2),
            "height": round(pix.height * scale, 2),
            "rect": [rect.x0, rect.y0, rect.x1, rect.y1] if rect else None,
            "words": words,
            "elapsed_s": round(time.time() - t0, 2),
        })
        print(f"page {fp}: {len(words)} words, {out['pages'][-1]['elapsed_s']}s", flush=True)

    Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
