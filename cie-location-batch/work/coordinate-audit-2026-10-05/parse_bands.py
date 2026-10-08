import re
import sys

LINE_RE = re.compile(r"^\s*\(([\d.]+),([\d.]+),([\d.]+),([\d.]+)\)\s*\|\s?(.*)$")
PAGE_RE = re.compile(r"^### (?P<tag>\S+) p(\d+) ")
LABEL_RE = re.compile(r"^\d*\(?[a-h]\)")

def parse(path):
    pages = []
    cur = None
    for raw in open(path, encoding="utf-8", errors="replace"):
        m = PAGE_RE.match(raw)
        if m:
            cur = {"tag": m.group("tag"), "page": int(m.group(2)), "lines": []}
            pages.append(cur)
            continue
        if cur is None:
            continue
        m = LINE_RE.match(raw.rstrip("\n"))
        if m:
            x0, y0, x1, y1 = (float(m.group(i)) for i in range(1, 5))
            cur["lines"].append((x0, y0, x1, y1, m.group(5).strip()))
    return pages

def main():
    path = sys.argv[1]
    xmin_f = float(sys.argv[2]) if len(sys.argv) > 2 else 95.0
    xmax_f = float(sys.argv[3]) if len(sys.argv) > 3 else 560.0
    for pg in parse(path):
        lines = [l for l in pg["lines"] if xmin_f <= l[0] <= xmax_f]
        if not lines:
            print(f"== p{pg['page']} ({pg['tag']}): no content lines in x filter ==")
            continue
        miny = min(lines, key=lambda l: l[1])
        maxy = max(lines, key=lambda l: l[3])
        maxx = max(lines, key=lambda l: l[2])
        minx = min(l[0] for l in lines)
        print(f"== p{pg['page']} ({pg['tag']}) lines={len(lines)} minx0={minx:.1f}")
        print(f"   miny0={miny[1]:.1f} @ ({miny[0]:.1f},{miny[1]:.1f},{miny[2]:.1f},{miny[3]:.1f}) | {miny[4][:60]}")
        print(f"   maxy1={maxy[3]:.1f} @ ({maxy[0]:.1f},{maxy[1]:.1f},{maxy[2]:.1f},{maxy[3]:.1f}) | {maxy[4][:60]}")
        print(f"   maxx1={maxx[2]:.1f} @ ({maxx[0]:.1f},{maxx[1]:.1f},{maxx[2]:.1f},{maxx[3]:.1f}) | {maxx[4][:60]}")
        left = minx + 2.0
        for l in lines:
            if l[0] <= left:
                print(f"   L ({l[0]:.1f},{l[1]:.1f},{l[2]:.1f},{l[3]:.1f}) | {l[4][:70]}")
        for l in lines:
            if LABEL_RE.match(l[4]) and l[0] > left:
                print(f"   Q ({l[0]:.1f},{l[1]:.1f},{l[2]:.1f},{l[3]:.1f}) | {l[4][:70]}")

if __name__ == "__main__":
    main()
