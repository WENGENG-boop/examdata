# tmp: high-res OCR of book3 pages for note transcription. Delete after S12.
import sys, json
import pymupdf
import numpy as np
from rapidocr_onnxruntime import RapidOCR

PDF = r"C:/Users/weo/Desktop/api/tmp_audit_ielts/downloads/book_3.pdf"
doc = pymupdf.open(PDF)
ocr = RapidOCR()

pages = [int(x) for x in sys.argv[1].split(",")]
zoom = float(sys.argv[2]) if len(sys.argv) > 2 else 4.0

for fp in pages:
    page = doc[fp - 1]
    mat = pymupdf.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat, colorspace=pymupdf.csGRAY)
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width)
    res, _ = ocr(img)
    print(f"\n######## PAGE {fp} zoom={zoom} ({pix.width}x{pix.height}) ########")
    if not res:
        print("(no text)")
        continue
    rows = []
    for item in res:
        box, text, conf = item[0], item[1], item[2]
        xs = [p[0] for p in box]; ys = [p[1] for p in box]
        try:
            conf = float(conf)
        except (TypeError, ValueError):
            conf = 0.0
        rows.append((min(ys), min(xs), max(xs), conf, text))
    rows.sort()
    for y, x0, x1, conf, text in rows:
        print(f"[y={y/zoom:7.1f} x={x0/zoom:6.1f}-{x1/zoom:6.1f} c={conf:.2f}] {text}")
