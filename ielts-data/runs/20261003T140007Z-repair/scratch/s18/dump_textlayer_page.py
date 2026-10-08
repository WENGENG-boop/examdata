import sys, fitz
book, page_no, out = sys.argv[1], int(sys.argv[2]), sys.argv[3]
doc = fitz.open(f"tmp_audit_ielts/downloads/book_{book}.pdf")
page = doc[page_no - 1]
chars = []
d = page.get_text("rawdict")
for b in d["blocks"]:
    if b.get("type") != 0: continue
    for l in b.get("lines", []):
        for s in l.get("spans", []):
            for c in s.get("chars", []):
                chars.append((round(c["origin"][1],1), round(c["origin"][0],1), c["c"], s["font"], round(s["size"],1), round(s["bbox"][0],1), round(s["bbox"][2],1)))
chars.sort()
with open(out, "w", encoding="utf-8") as f:
    for y, x, ch, font, size, x0, x1 in chars:
        f.write(f"y={y:7.1f} x={x:7.1f} bbox_x=[{x0:7.1f},{x1:7.1f}] font={font} size={size} ch={ch!r}\n")
print("chars:", len(chars), "->", out)
