import fitz

path = r"C:/Users/weo/Desktop/api/cie-location-batch/tmp/0472/2025-Jun-42/0472_s25_qp_42.pdf"
out = r"C:/Users/weo/Desktop/api/cie-location-batch/work/sheets/probe42"
import pathlib
pathlib.Path(out).mkdir(parents=True, exist_ok=True)

doc = fitz.open(path)

jobs = [
    (1, "p2_bottom", (40, 725, 575, 792), 4),
    (1, "p2_topright", (455, 15, 575, 120), 4),
    (1, "p2_zoom_right", (495, 730, 575, 792), 8),
    (2, "p3_bottom", (40, 725, 575, 792), 4),
    (3, "p4_bottom", (40, 725, 575, 792), 4),
]
for pi, name, (x0, y0, x1, y1), s in jobs:
    page = doc[pi]
    pm = page.get_pixmap(clip=fitz.Rect(x0, y0, x1, y1), matrix=fitz.Matrix(s, s))
    fp = f"{out}/{name}.png"
    pm.save(fp)
    print(f"{fp}  {pm.width}x{pm.height}")
