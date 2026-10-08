"""Write WMA13-p02.ans.txt from pack order + final r2 decisions."""
import re
from pathlib import Path

PACK = Path("tmp_selfjudge/r2/ial18-mathematics/WMA13-p02.txt")
OUT = Path("tmp_selfjudge/r2/ial18-mathematics/WMA13-p02.ans.txt")

CHANGES = {
    39971: "WMA13-2.3",
}

ALLOWED = {f"WMA13-{a}.{b}" for a, b in
           [(1, 1), (1, 2), (1, 3), (1, 4), (2, 1), (2, 2), (2, 3),
            (3, 1), (3, 2), (3, 3), (4, 1), (4, 2), (4, 3), (4, 4),
            (5, 1), (5, 2), (6, 1), (6, 2)]}

rows = []
for line in PACK.read_text(encoding="utf-8").splitlines():
    m = re.match(r"^\[(\d+)\] (\d+) ", line)
    if m:
        rows.append(int(m.group(2)))

assert len(rows) == 27, len(rows)
assert len(set(rows)) == 27, "dup qids"
for c in CHANGES.values():
    assert c in ALLOWED, c
missing = [q for q in CHANGES if q not in rows]
assert not missing, missing

header = [
    "# WMA13-p02 r2 selfjudge answers (27 questions)",
    "# 39971: (b) 5cos2x-12sin2x 化为 R cos(2x+\u03b1) -> 2.3（spec 2.3 R 形式明文；原 2.1）",
    "# 其余 26 行核验后维持现标签 OK",
]

lines = header + [f"{q} {CHANGES.get(q, 'OK')}" for q in rows]
OUT.write_bytes(("\r\n".join(lines) + "\r\n").encode("utf-8"))

print("wrote", OUT, "rows:", len(rows), "changes:", len(CHANGES))
