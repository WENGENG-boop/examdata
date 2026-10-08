"""Write WMA14-p02.ans.txt from pack order + final r2 decisions."""
import re
from pathlib import Path

PACK = Path("tmp_selfjudge/r2/ial18-mathematics/WMA14-p02.txt")
OUT = Path("tmp_selfjudge/r2/ial18-mathematics/WMA14-p02.ans.txt")

CHANGES = {}

ALLOWED = {f"WMA14-{a}.{b}" for a, b in
           [(1, 1), (2, 1), (3, 1), (4, 1), (5, 1), (5, 2),
            (6, 1), (6, 2), (6, 3), (6, 4), (6, 5),
            (7, 1), (7, 2), (7, 3), (7, 4), (7, 5), (7, 6), (7, 7)]}

rows = []
for line in PACK.read_text(encoding="utf-8").splitlines():
    m = re.match(r"^\[(\d+)\] (\d+) ", line)
    if m:
        rows.append(int(m.group(2)))

assert len(rows) == 19, len(rows)
assert len(set(rows)) == 19, "dup qids"
for c in CHANGES.values():
    assert c in ALLOWED, c
missing = [q for q in CHANGES if q not in rows]
assert not missing, missing

header = [
    "# WMA14-p02 r2 selfjudge answers (19 questions)",
    "# 19 行逐行核验（参数微分/旋转体/二项展开/部分分式+微分方程/向量证明等）后维持现标签 OK",
]

lines = header + [f"{q} {CHANGES.get(q, 'OK')}" for q in rows]
OUT.write_bytes(("\r\n".join(lines) + "\r\n").encode("utf-8"))

print("wrote", OUT, "rows:", len(rows), "changes:", len(CHANGES))
