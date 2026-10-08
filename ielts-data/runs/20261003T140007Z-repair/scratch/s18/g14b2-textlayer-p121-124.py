import fitz, sys

pdf = r"C:/Users/weo/Desktop/api/tmp_audit_ielts/downloads/book_11.pdf"
out = r"C:/Users/weo/Desktop/api/ielts-data/runs/20261003T140007Z-repair/scratch/s18/g14b2-book11-textlayer-p121-124.txt"
doc = fitz.open(pdf)

with open(out, "w", encoding="utf-8") as f:
    for fp in (121, 122, 123, 124):
        page = doc[fp - 1]
        f.write(f"\n########## file_page {fp} (index {fp-1}) ##########\n")
        f.write("---- plain text ----\n")
        f.write(page.get_text("text"))
        f.write("\n---- words with coords (x0,y0,x1,y1,word) ----\n")
        for w in page.get_text("words"):
            f.write(f"({w[0]:6.1f},{w[1]:6.1f},{w[2]:6.1f},{w[3]:6.1f}) {w[4]!r}\n")
        f.write(f"---- end file_page {fp} ----\n")

print("done ->", out)
