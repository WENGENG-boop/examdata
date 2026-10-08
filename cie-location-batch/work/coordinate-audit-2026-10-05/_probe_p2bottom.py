import fitz, json
p = r'tmp/8386/2026-Jun-12/8386_s26_qp_12.pdf'
d = fitz.open(p)
pg = d[1]  # page 2 (0-based)
print("page rect", pg.rect, "rotation", pg.rotation, "mediabox", pg.mediabox)
# drawings (ruled answer lines are vector lines)
ys=[]
for dr in pg.get_drawings():
    r = dr['rect']
    ys.append((round(r.y0,1), round(r.y1,1), round(r.x0,1), round(r.x1,1)))
ys.sort()
print("last 12 drawings by y0:")
for t in ys[-12:]:
    print(" ", t)
# text blocks
tb = pg.get_text("blocks")
tb.sort(key=lambda b: b[1])
print("last 8 text blocks:")
for b in tb[-8:]:
    print(" ", round(b[0],1), round(b[1],1), round(b[2],1), round(b[3],1), repr(b[4][:60]))
