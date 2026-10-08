import fitz, sys, pathlib
p = sys.argv[1]
pages_arg = sys.argv[2] if len(sys.argv)>2 else None
doc = fitz.open(p)
want = None
if pages_arg:
    want = set()
    for part in pages_arg.split(','):
        if '-' in part:
            a,b = part.split('-'); want |= set(range(int(a),int(b)+1))
        else: want.add(int(part))
print("PAGES", doc.page_count)
for i,page in enumerate(doc):
    n = i+1
    if want and n not in want: continue
    mb = page.mediabox
    rot = page.rotation
    blocks = page.get_text("blocks")
    txt_all = page.get_text().strip()
    print(f"\n===== page {n}  rot={rot} mediabox=({mb.x0:.1f},{mb.y0:.1f},{mb.x1:.1f},{mb.y1:.1f}) blocks={len(blocks)} chars={len(txt_all)}")
    if not txt_all:
        print("   [NO TEXT LAYER]")
        continue
    for b in blocks:
        x0,y0,x1,y1,t = b[0],b[1],b[2],b[3],b[4]
        t1 = " / ".join(t.split())[:110]
        print(f"   [{x0:7.1f},{y0:7.1f},{x1:7.1f},{y1:7.1f}] {t1}")
