import sys, fitz
pdf = r"C:/Users/weo/Desktop/api/tmp_audit_ielts/downloads/book_3.pdf"
page_no = int(sys.argv[1])
doc = fitz.open(pdf)
page = doc[page_no-1]
print(f"== drawings page {page_no} ==")
seen=set()
for d in page.get_drawings():
    r = d["rect"]
    key=(round(r.x0),round(r.y0),round(r.x1),round(r.y1),d.get("type"))
    if key in seen: continue
    seen.add(key)
    print(f"{d.get('type')} ({r.x0:.1f},{r.y0:.1f})-({r.x1:.1f},{r.y1:.1f}) w={r.width:.1f} h={r.height:.1f}")
