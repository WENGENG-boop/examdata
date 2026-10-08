import sys, numpy as np
from PIL import Image
from rapidocr_onnxruntime import RapidOCR

path = sys.argv[1]
x0,y0,x1,y1 = [int(v) for v in sys.argv[2].split(",")]  # pixel coords in PNG
scale = float(sys.argv[3]) if len(sys.argv)>3 else 3.0
im = Image.open(path).convert("RGB")
crop = im.crop((x0,y0,x1,y1))
w,h = crop.size
crop = crop.resize((int(w*scale), int(h*scale)), Image.LANCZOS)
arr = np.array(crop)
ocr = RapidOCR()
res, _ = ocr(arr)
if not res:
    print("(no text)")
else:
    for box, txt, conf in res:
        xs=[p[0] for p in box]; ys=[p[1] for p in box]
        print(f"[y={(min(ys)+max(ys))/2/scale+y0:.0f} x={min(xs)/scale+x0:.0f} c={float(conf):.2f}] {txt}")
