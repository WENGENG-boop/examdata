import sys, fitz, numpy as np
from rapidocr_onnxruntime import RapidOCR

pdf = r"C:/Users/weo/Desktop/api/tmp_audit_ielts/downloads/book_3.pdf"
# args: page x0,y0,x1,y1 (PDF pts) zoom
page_no = int(sys.argv[1])
x0,y0,x1,y1 = [float(v) for v in sys.argv[2].split(",")]
zoom = float(sys.argv[3]) if len(sys.argv)>3 else 4.0

doc = fitz.open(pdf)
page = doc[page_no-1]
mat = fitz.Matrix(zoom, zoom)
pix = page.get_pixmap(matrix=mat, colorspace=fitz.csGRAY)
img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width)
# crop
cx0, cy0, cx1, cy1 = [int(v*zoom) for v in (x0,y0,x1,y1)]
cx0=max(0,cx0); cy0=max(0,cy0); cx1=min(pix.width,cx1); cy1=min(pix.height,cy1)
crop = img[cy0:cy1, cx0:cx1].copy()
crop = np.stack([crop]*3, axis=-1)
ocr = RapidOCR()
res, _ = ocr(crop)
if not res:
    print("(no text)")
else:
    for box, txt, conf in res:
        ys = [p[1] for p in box]; xs=[p[0] for p in box]
        py = (min(ys)+max(ys))/2/zoom + y0
        px = (min(xs))/zoom + x0
        print(f"[y={py:.1f} x={px:.1f} c={float(conf):.2f}] {txt}")
