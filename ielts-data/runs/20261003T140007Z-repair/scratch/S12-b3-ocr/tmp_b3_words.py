import sys, fitz, json
pdf = r"C:/Users/weo/Desktop/api/tmp_audit_ielts/downloads/book_3.pdf"
doc = fitz.open(pdf)
pages = [int(x) for x in sys.argv[1].split(",")]
for fp in pages:
    page = doc[fp-1]
    words = page.get_text("words")
    print(f"######## PAGE {fp} ########")
    # group by line: round y to 1 decimal
    from collections import defaultdict
    rows = defaultdict(list)
    for w in words:
        x0,y0,x1,y1,txt = w[0],w[1],w[2],w[3],w[4]
        rows[round(y0,0)].append((x0,txt))
    for y in sorted(rows):
        items = sorted(rows[y])
        line = " | ".join(f"{x:.0f}:{t}" for x,t in items)
        print(f"[y={y:.0f}] {line}")
