import fitz, sys
sys.stdout.reconfigure(encoding='utf-8')
d = fitz.open(r'tmp/8386/2026-Jun-12/8386_s26_ms_12.pdf')
pg = d[13]
print("rect", pg.rect, "rotation", pg.rotation)
print("page.rotation_matrix", pg.rotation_matrix)
for b in sorted(pg.get_text("blocks"), key=lambda b: (round(b[1],1), round(b[0],1))):
    txt = b[4].replace("\n"," ")[:44]
    print(f"x0={b[0]:7.1f} y0={b[1]:7.1f} x1={b[2]:7.1f} y1={b[3]:7.1f} | {txt}")
