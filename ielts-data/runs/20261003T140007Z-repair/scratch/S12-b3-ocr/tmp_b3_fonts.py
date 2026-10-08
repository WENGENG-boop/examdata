import sys, fitz
pdf = r"C:/Users/weo/Desktop/api/tmp_audit_ielts/downloads/book_3.pdf"
page_no = int(sys.argv[1])
x0,y0,x1,y1 = [float(v) for v in sys.argv[2].split(",")]
doc = fitz.open(pdf)
page = doc[page_no-1]
clip = fitz.Rect(x0,y0,x1,y1)
d = page.get_text("dict", clip=clip)
for b in d["blocks"]:
    if b["type"]!=0: continue
    for l in b["lines"]:
        for s in l["spans"]:
            print(f"y={s['bbox'][1]:.1f} x={s['bbox'][0]:.1f} size={s['size']:.1f} font={s['font']} color={s['color']:06x} text={s['text']!r}")
