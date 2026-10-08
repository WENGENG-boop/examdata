import sys, fitz
pdf = r"C:/Users/weo/Desktop/api/tmp_audit_ielts/downloads/book_3.pdf"
page_no = int(sys.argv[1])
doc = fitz.open(pdf)
page = doc[page_no-1]
hor=[]; ver=[]
for d in page.get_drawings():
    r = d["rect"]
    if r.width > 20 and r.height < 2: hor.append((round(r.y0,1), round(r.x0,1), round(r.x1,1)))
    elif r.height > 5 and r.width < 2: ver.append((round(r.x0,1), round(r.y0,1), round(r.y1,1)))
# merge segments on same y/x
from collections import defaultdict
hm=defaultdict(list)
for y,x0,x1 in hor: hm[y].append((x0,x1))
vm=defaultdict(list)
for x,y0,y1 in ver: vm[x].append((y0,y1))
print("HORIZONTAL lines (y: x-ranges):")
for y in sorted(hm):
    segs=sorted(hm[y])
    print(f"  y={y}: " + ", ".join(f"{a}-{b}" for a,b in segs))
print("VERTICAL lines (x: y-ranges):")
for x in sorted(vm):
    segs=sorted(vm[x])
    print(f"  x={x}: " + ", ".join(f"{a}-{b}" for a,b in segs))
