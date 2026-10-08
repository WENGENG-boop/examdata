import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pymupdf

QP = Path(r"C:/Users/weo/Desktop/api/cie-location-batch/tmp/9715/2023-Nov-21/9715_w23_qp_21.pdf")
with pymupdf.open(QP) as pdf:
    page = pdf[4]
    print("page5 rect", page.rect, "rot", page.rotation)
    xs0 = xs1 = ys0 = ys1 = None
    n = 0
    for d in page.get_drawings():
        r = d["rect"]
        if r.height > 300 and r.width > 300:
            n += 1
            xs0 = r.x0 if xs0 is None else min(xs0, r.x0)
            ys0 = r.y0 if ys0 is None else min(ys0, r.y0)
            xs1 = r.x1 if xs1 is None else max(xs1, r.x1)
            ys1 = r.y1 if ys1 is None else max(ys1, r.y1)
            if n <= 6:
                print("  big draw", [round(v, 1) for v in (r.x0, r.y0, r.x1, r.y1)], d.get("type"))
    print("big drawings:", n, "union:", None if n == 0 else [round(v, 1) for v in (xs0, ys0, xs1, ys1)])
