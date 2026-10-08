"""校准合成 fixture 的坐标/bbox 行为。仅临时验证用。"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import pymupdf

with pymupdf.open() as pdf:
    print("default page rect:", pdf.new_page().rect)
    page = pdf.new_page()
    page.insert_text((43, 100), '1')
    page.insert_text((80, 120), 'Question one text')
    page.insert_text((43, 300), '(Total for Question 1 = 1 mark)')
    page.insert_text((9.6, 400), 'DO NOT WRITE IN THIS AREA', rotate=90)
    page.insert_text((200, 816), 'Turn over')
    page.insert_text((43, 806), '*P75888A0328*')
    page.insert_text((49, 798), '2')
    page.insert_text((43, 59.5), 'SECTION')
    page.insert_text((70, 59.5), 'A')
    for w in sorted(page.get_text('words'), key=lambda w: w[1]):
        print(f"y0={w[1]:7.2f} y1={w[3]:7.2f} x0={w[0]:6.2f} x1={w[2]:6.2f} {w[4]!r}")
    print("--- drawings ---")
    page2 = pdf.new_page()
    page2.draw_rect(pymupdf.Rect(60, 200, 500, 600))
    page2.draw_rect(pymupdf.Rect(35, 36.4, 560.3, 794.1))
    for d in page2.get_drawings():
        print(d['rect'], 'w=', d['rect'].width, 'h=', d['rect'].height)
