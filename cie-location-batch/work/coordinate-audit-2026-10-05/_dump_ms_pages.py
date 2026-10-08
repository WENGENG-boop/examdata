import pymupdf, sys
p = sys.argv[1]
doc = pymupdf.open(p)
for i, page in enumerate(doc):
    print(f"\n########## page {i+1} rot={page.rotation} mediabox={page.mediabox}")
    txt = page.get_text().strip()
    if not txt:
        print("   [NO TEXT LAYER]"); continue
    for b in page.get_text("blocks"):
        x0,y0,x1,y1,t = b[0],b[1],b[2],b[3],b[4]
        t = " | ".join(t.split())
        print(f"   [{x0:7.1f},{y0:7.1f},{x1:7.1f},{y1:7.1f}] ({t[:230]})")
