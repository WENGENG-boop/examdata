#!/usr/bin/env python3
"""OCR runner for IELTS source PDFs (lives in ielts-data/tools, own venv).

Renders PDF pages (or a cropped rect) and runs RapidOCR (rapidocr-onnxruntime)
on the rendered image. Emits per-word boxes + confidence in PDF point
coordinates so results can be merged with the text-layer extraction done by
ielts-api/tools/pdf_extract.py.

Run with the local OCR venv (see requirements-ocr.txt):

  ielts-data/tools/ocr-venv/Scripts/python.exe ielts-data/tools/ocr_pages.py \
      --book 3 --pages 37,39 --out out.json --imgdir img/

Usage:
  --book N | --pdf PATH      source PDF (default: tmp_audit_ielts/downloads/book_N.pdf)
  --pages 1,2,5-7           1-based physical pages
  --rect x0,y0,x1,y1        optional PDF-point crop applied to every page
  --dpi D                   render scale (default 300)
  --out PATH                output JSON (required)
  --imgdir DIR              optionally save rendered PNGs
"""

import argparse
import json
import time
from pathlib import Path

import pymupdf  # PyMuPDF

ROOT = Path(__file__).resolve().parents[2]
DOWNLOADS = ROOT / "tmp_audit_ielts" / "downloads"
TOOL_VERSION = 1


def resolve_pdf(book=None, pdf=None):
    if pdf:
        return Path(pdf)
    return DOWNLOADS / f"book_{book}.pdf"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--book", type=int)
    ap.add_argument("--pdf")
    ap.add_argument("--pages", required=True, help="comma separated 1-based file pages")
    ap.add_argument("--out", required=True)
    ap.add_argument("--imgdir", help="if set, save rendered PNGs here")
    ap.add_argument("--dpi", type=float, default=300.0)
    ap.add_argument("--rect", help="x0,y0,x1,y1 in PDF points; crop all pages to this region")
    args = ap.parse_args()

    import importlib.metadata as importlib_metadata

    from rapidocr_onnxruntime import RapidOCR
    import numpy as np

    ocr = RapidOCR()
    pdf_path = resolve_pdf(args.book, args.pdf)
    doc = pymupdf.open(str(pdf_path))
    pages = [int(p) for p in args.pages.split(",") if p.strip()]
    rect = None
    if args.rect:
        rect = pymupdf.Rect(*[float(v) for v in args.rect.split(",")])
    imgdir = Path(args.imgdir) if args.imgdir else None
    if imgdir:
        imgdir.mkdir(parents=True, exist_ok=True)

    out = {
        "tool": "ocr_pages",
        "version": TOOL_VERSION,
        "engine": "rapidocr-onnxruntime",
        "engine_version": importlib_metadata.version("rapidocr-onnxruntime"),
        "pdf": str(pdf_path),
        "dpi": args.dpi,
        "pages": [],
    }
    for fp in pages:
        if fp < 1 or fp > len(doc):
            print(f"page {fp} out of range 1..{len(doc)}", flush=True)
            continue
        page = doc[fp - 1]
        clip = rect if rect else None
        t0 = time.time()
        pix = page.get_pixmap(matrix=pymupdf.Matrix(args.dpi / 72.0, args.dpi / 72.0), clip=clip, alpha=False)
        if imgdir:
            pix.save(str(imgdir / f"p{fp:04d}.png"))
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
                words.append(
                    {
                        "text": text,
                        "conf": round(float(conf), 4),
                        "box": pts,
                        "x0": min(xs),
                        "x1": max(xs),
                        "y0": min(ys),
                        "y1": max(ys),
                    }
                )
        words.sort(key=lambda w: (w["y0"], w["x0"]))
        out["pages"].append(
            {
                "file_page": fp,
                "width": round(pix.width * scale, 2),
                "height": round(pix.height * scale, 2),
                "rect": [rect.x0, rect.y0, rect.x1, rect.y1] if rect else None,
                "words": words,
                "elapsed_s": round(time.time() - t0, 2),
            }
        )
        print(f"page {fp}: {len(words)} words, {out['pages'][-1]['elapsed_s']}s", flush=True)

    Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
