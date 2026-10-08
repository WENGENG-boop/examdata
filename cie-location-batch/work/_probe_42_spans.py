import fitz

path = r"C:/Users/weo/Desktop/api/cie-location-batch/tmp/0472/2025-Jun-42/0472_s25_qp_42.pdf"
doc = fitz.open(path)

for pi in (1, 2, 3):
    page = doc[pi]
    print(f"===== page {pi+1} =====")
    d = page.get_text("dict")
    spans = []
    for b in d["blocks"]:
        if b.get("type") != 0:
            continue
        for l in b["lines"]:
            for s in l["spans"]:
                spans.append((round(s["bbox"][1], 1), round(s["bbox"][0], 1),
                              round(s["bbox"][2], 1), round(s["bbox"][3], 1),
                              round(s["size"], 1), s["text"]))
    spans.sort()
    for y0, x0, x1, y1, size, text in spans:
        if y1 > 700 or y0 < 115:
            t = text.replace("\n", "\\n")
            if len(t) > 90:
                t = t[:90] + "…"
            print(f"  y{y0:6.1f}-{y1:6.1f} x{x0:6.1f}-{x1:6.1f} sz{size:4.1f}  {t!r}")
