import fitz
import pathlib

path = r"C:/Users/weo/Desktop/api/cie-location-batch/tmp/0472/2025-Jun-42/0472_s25_qp_42.pdf"
out = r"C:/Users/weo/Desktop/api/cie-location-batch/work/sheets/probe42"
pathlib.Path(out).mkdir(parents=True, exist_ok=True)

doc = fitz.open(path)
jobs = [
    ("p2_line1_right", 1, (470, 55, 575, 90), 10),
    ("p2_br_zoom", 1, (480, 735, 560, 775), 10),
    ("p2_above_footer", 1, (55, 690, 575, 748), 4),
]
for name, pi, (x0, y0, x1, y1), s in jobs:
    page = doc[pi]
    pm = page.get_pixmap(clip=fitz.Rect(x0, y0, x1, y1), matrix=fitz.Matrix(s, s))
    fp = f"{out}/{name}.png"
    pm.save(fp)
    print(f"{fp}  {pm.width}x{pm.height}")

html = """<!doctype html><meta charset=utf-8><body style="background:#fff;margin:0">
<div style="font:12px monospace;background:#eee;padding:2px">A: p2_line1_right (470,55,575,90)@10x</div>
<img src="p2_line1_right.png" style="max-width:1260px;width:100%">
<div style="font:12px monospace;background:#eee;padding:2px">B: p2_br_zoom (480,735,560,775)@10x</div>
<img src="p2_br_zoom.png" style="max-width:1260px;width:100%">
<div style="font:12px monospace;background:#eee;padding:2px">C: p2_above_footer (55,690,575,748)@4x</div>
<img src="p2_above_footer.png" style="max-width:1260px;width:100%">
</body>"""
pathlib.Path(f"{out}/view.html").write_text(html, encoding="utf-8")
print("wrote view.html")
