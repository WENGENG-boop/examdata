import fitz
from pathlib import Path

BR = Path(r"C:/Users/weo/Desktop/api/cie-location-batch")
T = BR / "tmp/0472/2025-Jun-21"
FOOT = T / "footers"
FOOT.mkdir(exist_ok=True)

qp = T / "0472_s25_qp_21.pdf"
ms = T / "0472_s25_ms_21.pdf"

def strip(src, rect, zoom, pages, prefix):
    doc = fitz.open(src)
    for i in pages:
        page = doc[i - 1]
        r = fitz.Rect(rect) & page.rect
        pix = page.get_pixmap(clip=r, matrix=fitz.Matrix(zoom, zoom))
        out = FOOT / f"{prefix}-p{i:03d}.png"
        pix.save(str(out))
        print(prefix, i, "size", pix.width, pix.height, "pagerect", page.rect, "rotation", page.rotation)
    doc.close()

# top-center page number region (pt): x 200-430, y 20-80
strip(qp, (200, 20, 430, 80), 4, range(1, 17), "pn-qp")
strip(ms, (200, 20, 430, 80), 4, range(1, 7), "pn-ms")
# MS footer region (bottom): x 150-460, y 700-785
strip(ms, (150, 700, 460, 785), 3, range(1, 7), "msfoot")

html = """<!doctype html><meta charset="utf-8">
<title>0472/2025/Jun/21 page numbers</title>
<style>body{background:#111;color:#eee;font:16px sans-serif;margin:8px}
.cell{margin:4px 0;border-bottom:1px solid #555} img{width:90%;max-width:1100px;display:block}
.lb{color:#ff0;font-weight:bold}</style>
<h2>QP page-number strips (index 1-16)</h2>
"""
for i in range(1, 17):
    html += f'<div class="cell"><div class="lb">QP page index {i}</div><img src="/tmp/0472/2025-Jun-21/footers/pn-qp-p{i:03d}.png"></div>\n'
html += "<h2>MS page-number strips (index 1-6)</h2>\n"
for i in range(1, 7):
    html += f'<div class="cell"><div class="lb">MS page index {i}</div><img src="/tmp/0472/2025-Jun-21/footers/pn-ms-p{i:03d}.png"></div>\n'
html += "<h2>MS footer strips (index 1-6)</h2>\n"
for i in range(1, 7):
    html += f'<div class="cell"><div class="lb">MS footer p{i}</div><img src="/tmp/0472/2025-Jun-21/footers/msfoot-p{i:03d}.png"></div>\n'
out_html = BR / "work/sheets/0472-2025-Jun-21-pgnum.html"
out_html.write_text(html, encoding="utf-8")
print("HTML:", out_html)
