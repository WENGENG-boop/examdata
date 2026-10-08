import sys
# usage: lineview.py <charsfile> [ymin ymax] [xmin xmax]
fn = sys.argv[1]
ymin = float(sys.argv[2]) if len(sys.argv) > 2 else 0
ymax = float(sys.argv[3]) if len(sys.argv) > 3 else 10000
xmin = float(sys.argv[4]) if len(sys.argv) > 4 else 0
xmax = float(sys.argv[5]) if len(sys.argv) > 5 else 10000
import re
rows = []
pat = re.compile(r"y=\s*([\d.]+) x=\s*([\d.]+) bbox_x=\[\s*([\d.]+),\s*([\d.]+)\] font=(\S+) size=([\d.]+) ch=(.*)")
for line in open(fn, encoding="utf-8"):
    m = pat.match(line.strip())
    if not m: continue
    y, x, x0, x1, font, size, ch = float(m.group(1)), float(m.group(2)), float(m.group(3)), float(m.group(4)), m.group(5), float(m.group(6)), m.group(7)
    if not (ymin <= y <= ymax and xmin <= x <= xmax): continue
    rows.append((y, x, x0, x1, font, size, ch))
rows.sort()
# cluster into lines by y (tol 3)
lines = []
for r in rows:
    if lines and abs(r[0] - lines[-1][-1][0]) <= 3.0:
        lines[-1].append(r)
    else:
        lines.append([r])
import ast
for ln in lines:
    ln.sort(key=lambda r: r[1])
    text = "".join(ast.literal_eval(r[6]) if r[6].startswith("'") else r[6] for r in ln)
    y = ln[0][0]
    x0 = min(r[2] for r in ln); x1 = max(r[3] for r in ln)
    fonts = set(r[4] for r in ln); sizes = set(r[5] for r in ln)
    print(f"y={y:7.1f} x=[{x0:6.1f},{x1:6.1f}] fonts={sorted(fonts)} sizes={sorted(sizes)} | {text}")
