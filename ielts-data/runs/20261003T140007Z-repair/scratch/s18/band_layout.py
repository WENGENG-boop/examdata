import re
import sys

path = sys.argv[1]
band = None
glyphs = []
for line in open(path, encoding="utf-8", errors="replace"):
    m = re.match(r"=== band y=([\d.]+)-([\d.]+)pt\s+\((\d+) glyphs\)", line)
    if m:
        if band:
            print(band[0], band[1], "|", "; ".join(glyphs))
        band = (m.group(1), m.group(2))
        glyphs = []
        continue
    g = re.match(r"--- glyph x=([\d.]+)-([\d.]+)pt", line)
    if g:
        glyphs.append(f"{g.group(1)}-{g.group(2)}")
if band:
    print(band[0], band[1], "|", "; ".join(glyphs))
