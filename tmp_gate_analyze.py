"""分析 tmp_gate_audit_page.txt（按页门控版）：列匹配例外候选与 W 类明细。

用法: python tmp_gate_analyze.py [audit.txt] [cd_threshold]
"""
import re
import sys
from collections import defaultdict

PATH = sys.argv[1] if len(sys.argv) > 1 else "tmp_gate_audit_page.txt"
THRESH = float(sys.argv[2]) if len(sys.argv) > 2 else 3.0

row_re = re.compile(
    r"^  R p(\d+) ('[^']*') x=([\d.]+) y=([\d.]+) cal=([\d.]+|None)/([\d.eE-]+) "
    r"d=([\d.-]+|None) cls=(\w) cd=([\d.]+|None) ctx=(.*)$"
)
hdr_re = re.compile(r"^ms=(\d+) doc=(\d+) wanted=(\d+) removed=(\d+) added=(\d+)$")

rows = []
cur = None
summary_lines = []
with open(PATH, encoding="utf-8") as fh:
    for line in fh:
        line = line.rstrip("\n")
        if line.startswith(("docs scanned", "docs with", "removed cls", "added cls", "removed delta")):
            summary_lines.append(line)
            continue
        m = hdr_re.match(line)
        if m:
            cur = dict(ms=int(m.group(1)), doc=int(m.group(2)),
                       n_removed=int(m.group(4)), n_added=int(m.group(5)))
            continue
        m = row_re.match(line)
        if m and cur:
            cd = m.group(9)
            rows.append(dict(
                cur, p=int(m.group(1)), tok=m.group(2).strip("'"),
                x=float(m.group(3)), y=float(m.group(4)),
                cal=m.group(5), d=m.group(7), cls=m.group(8),
                cd=None if cd == "None" else float(cd), ctx=m.group(10)))

print("== summary ==")
for s in summary_lines:
    print(s)
print(f"\nparsed rows: {len(rows)}")
by_cls = defaultdict(int)
for r in rows:
    by_cls[r["cls"]] += 1
print(f"by cls: {dict(by_cls)}")

w_rows = [r for r in rows if r["cls"] == "W"]
near = [r for r in w_rows if r["cd"] is not None and r["cd"] <= THRESH]
print(f"\nW rows: {len(w_rows)}, W with cd<={THRESH}: {len(near)}")
near_docs = defaultdict(list)
for r in near:
    near_docs[(r["ms"], r["doc"])].append(r)
for (ms, doc), rs in sorted(near_docs.items()):
    print(f"\n-- ms={ms} doc={doc} ({len(rs)} rows) --")
    for r in sorted(rs, key=lambda r: (r["p"], r["x"])):
        print(f"  p{r['p']} {r['tok']!r} x={r['x']} y={r['y']} cal={r['cal']} "
              f"d={r['d']} cd={r['cd']} ctx={r['ctx']}")

# 全部 W 行按 doc 汇总（供人工复核）
print("\n== all W rows (doc -> count, min d, min cd) ==")
agg = defaultdict(lambda: [0, [], []])
for r in w_rows:
    a = agg[(r["ms"], r["doc"])]
    a[0] += 1
    a[1].append(float(r["d"]))
    if r["cd"] is not None:
        a[2].append(r["cd"])
for (ms, doc), (n, ds, cds) in sorted(agg.items()):
    print(f"ms={ms} doc={doc}: n={n} d_min={min(ds):.1f} d_max={max(ds):.1f} "
          f"cd_min={min(cds) if cds else None}")
