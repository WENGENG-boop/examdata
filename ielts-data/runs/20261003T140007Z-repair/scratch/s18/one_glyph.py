import sys, pymupdf
book, page = sys.argv[1], int(sys.argv[2])
x0,y0,x1,y1 = [float(v) for v in sys.argv[3:7]]
dpi = float(sys.argv[7]) if len(sys.argv)>7 else 2400.0
thr = int(sys.argv[8]) if len(sys.argv)>8 else 128
doc = pymupdf.open(f"C:/Users/weo/Desktop/api/tmp_audit_ielts/downloads/book_{book}.pdf")
pg = doc[page-1]
scale = dpi/72.0
pix = pg.get_pixmap(matrix=pymupdf.Matrix(scale,scale), clip=pymupdf.Rect(x0,y0,x1,y1), alpha=False, colorspace=pymupdf.csGRAY)
s = pix.samples; stride = pix.stride
def dark(x,y): return s[y*stride+x] < thr
print(f"# dpi={dpi} thr={thr} size={pix.width}x{pix.height}")
for y in range(pix.height):
    print(''.join('#' if dark(x,y) else '.' for x in range(pix.width)))
