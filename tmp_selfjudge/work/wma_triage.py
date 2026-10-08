"""Dump compact triage table for r2 packs: idx qid part marks cur | snippet."""
import re
import sys
from pathlib import Path

pack = Path(sys.argv[1])
out = Path(sys.argv[2])

lines = pack.read_text(encoding="utf-8").splitlines()
rows = []
cur = None
for line in lines:
    m = re.match(r"^\[(\d+)\] (\d+) (#\S+)?(?:\[C\])? (\d+mk|\?mk) cur=([A-Z0-9.-]+)", line)
    if m:
        rows.append([int(m.group(1)), int(m.group(2)), m.group(3) or "", m.group(4), m.group(5), ""])
        cur = rows[-1]
    elif cur is not None and line.strip() and not line.startswith("#"):
        if cur[5] == "":
            cur[5] = re.sub(r"\s+", " ", line.strip())[:150]

with out.open("w", encoding="utf-8") as f:
    f.write(f"# {pack.name}: {len(rows)} rows\n")
    for idx, qid, part, mk, code, snip in rows:
        f.write(f"{idx:3d} {qid} {part:8s} {mk:5s} {code:10s} {snip}\n")
print("rows:", len(rows), "->", out)
