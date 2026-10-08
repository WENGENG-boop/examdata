import fitz, json
p = r"C:/Users/weo/Desktop/api/cie-location-batch/tmp/0472/2025-Jun-21/0472_s25_ms_21.pdf"
doc = fitz.open(p)
out = {}
for pno in [3,4,5]:
    page = doc[pno]
    # drawings: find rects that look like the table frame
    dr = page.get_drawings()
    rects = []
    for d in dr:
        r = d["rect"]
        if r.width > 300 and r.height > 300:
            rects.append([round(r.x0,1),round(r.y0,1),round(r.x1,1),round(r.y1,1)])
    # all text spans with x0>340
    spans = []
    for b in page.get_text("dict")["blocks"]:
        for l in b.get("lines", []):
            for s in l["spans"]:
                x0,y0,x1,y1 = s["bbox"]
                if x1 > 340:
                    spans.append([round(x0,1),round(y0,1),round(x1,1),round(y1,1), s["text"][:60]])
    out[f"p{pno+1}"] = {"big_rects": rects, "spans_x1_gt340": spans}
print(json.dumps(out, ensure_ascii=False, indent=1))
