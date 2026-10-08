import fitz, shutil, os

BASE = "ielts-data/runs/20261003T140007Z-repair/scratch/s18"
doc = fitz.open("tmp_audit_ielts/downloads/book_10.pdf")
page = doc[151]  # fp152 = GT A answer page
chars = []
d = page.get_text("rawdict")
for b in d["blocks"]:
    if b.get("type") != 0: continue
    for l in b.get("lines", []):
        for s in l.get("spans", []):
            for c in s.get("chars", []):
                chars.append((round(c["origin"][1],1), round(c["origin"][0],1), c["c"], s["font"], round(s["size"],1), round(s["bbox"][0],1), round(s["bbox"][2],1)))
chars.sort()
out = os.path.join(BASE, "fp152-textlayer-chars.txt")
with open(out, "w", encoding="utf-8") as f:
    for y, x, ch, font, size, x0, x1 in chars:
        f.write(f"y={y:7.1f} x={x:7.1f} bbox_x=[{x0:7.1f},{x1:7.1f}] font={font} size={size} ch={ch!r}\n")
print("chars:", len(chars), "->", out)

# region prints
def region(name, xlo, xhi, ylo, yhi):
    sel = [c for c in chars if xlo <= c[1] <= xhi and ylo <= c[0] <= yhi]
    print(f"\n=== {name} (x {xlo}-{xhi}, y {ylo}-{yhi}) n={len(sel)} ===")
    fonts = {}
    for c in sel:
        fonts[c[3]] = fonts.get(c[3], 0) + 1
    print("fonts:", fonts)
    for c in sel[:80]:
        print(f"  y={c[0]:7.1f} x={c[1]:7.1f} font={c[3]:28s} sz={c[4]} ch={c[2]!r}")

region("Q8-14 left col", 0, 110, 180, 275)
region("Q20-27 area", 220, 310, 85, 195)
region("Q28-40 area", 220, 310, 200, 365)

# file bookkeeping fix: p152-textlayer-chars.txt actually holds fp153 (doc[152]) content
src = os.path.join(BASE, "p152-textlayer-chars.txt")
dst = os.path.join(BASE, "fp153-textlayer-chars.txt")
if os.path.exists(src):
    shutil.copyfile(src, dst)
    print("\ncopied p152-textlayer-chars.txt -> fp153-textlayer-chars.txt")
