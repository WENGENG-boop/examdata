# -*- coding: utf-8 -*-
"""帧27 边界核验: 渲染 4 条边界条带 PNG + HTML，供浏览器目视。只读本地 PDF。"""
import fitz
from pathlib import Path

BR = Path(r"C:/Users/weo/Desktop/api/cie-location-batch")
OUT = BR / "work" / "_p11_strips"
OUT.mkdir(exist_ok=True)

doc = fitz.open(BR / "tmp/0472/2026-Jun-22/0472_s26_qp_22.pdf")
p = doc[10]

strips = [
    ("A-excl-top", "A EXCLUDED top y16.4-58.8 (header debris?)", (30.4, 16.4, 540.4, 58.8), 3),
    ("B-incl-title", "B INCLUDED title y58.8-85.2 (title?)", (30.4, 58.8, 540.4, 85.2), 3),
    ("C-incl-bottom", "C INCLUDED bottom y669.0-700.6 ([5]?)", (30.4, 669.0, 540.4, 700.6), 3),
    ("D-excl-footer", "D EXCLUDED footer y700.6-766.0 (footer only?)", (30.4, 700.6, 540.4, 766.0), 3),
]

html = """<!doctype html><meta charset="utf-8">
<title>p11 strips frame27</title>
<style>body{background:#111;color:#eee;font:15px sans-serif;margin:8px}
.cell{margin:6px 0;border-bottom:1px solid #555} img{width:95%;max-width:1200px;display:block}
.lb{color:#ff0;font-weight:bold}</style>
<h2>0472/2026/Jun/22 Q5@p11 boundary strips (page 11, index 10)</h2>
"""
for name, label, rect, zoom in strips:
    pix = p.get_pixmap(matrix=fitz.Matrix(zoom, zoom), clip=fitz.Rect(rect))
    out = OUT / f"{name}.png"
    pix.save(str(out))
    print(name, "size", pix.width, pix.height)
    html += f'<div class="cell"><div class="lb">{label}</div><img src="/work/_p11_strips/{name}.png"></div>\n'

out_html = BR / "work" / "_p11_strips.html"
out_html.write_text(html, encoding="utf-8")
print("HTML:", out_html)
