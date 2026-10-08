"""Write WMA14-p01.ans.txt from pack order + final r2 decisions."""
import re
from pathlib import Path

PACK = Path("tmp_selfjudge/r2/ial18-mathematics/WMA14-p01.txt")
OUT = Path("tmp_selfjudge/r2/ial18-mathematics/WMA14-p01.ans.txt")

CHANGES = {
    38042: "WMA14-5.1",
    36472: "WMA14-5.2",
    36474: "WMA14-5.2",
    37768: "WMA14-5.2",
    37770: "WMA14-5.2",
    38860: "WMA14-5.2",
    37108: "WMA14-5.2",
}

ALLOWED = {f"WMA14-{a}.{b}" for a, b in
           [(1, 1), (2, 1), (3, 1), (4, 1), (5, 1), (5, 2),
            (6, 1), (6, 2), (6, 3), (6, 4), (6, 5),
            (7, 1), (7, 2), (7, 3), (7, 4), (7, 5), (7, 6), (7, 7)]}

rows = []
for line in PACK.read_text(encoding="utf-8").splitlines():
    m = re.match(r"^\[(\d+)\] (\d+) ", line)
    if m:
        rows.append(int(m.group(2)))

assert len(rows) == 150, len(rows)
assert len(set(rows)) == 150, "dup qids"
for c in CHANGES.values():
    assert c in ALLOWED, c
missing = [q for q in CHANGES if q not in rows]
assert not missing, missing

header = [
    "# WMA14-p01 r2 selfjudge answers (150 questions)",
    "# 38042: (a) 隐函数曲线代 x=2 求 P 的 y（无参数内容）-> 5.1（父题 38041 与 (b)(c) 均 5.1；原 3.1）",
    "# 36472: Q3 药片溶解连通变化率题（dA/dt 恒定 -> dx/dt、dV/dt）-> 5.2（spec 5.2 明文 connected rates of change；原 5.1）",
    "# 36474: (b) 求体积减小速率 -> 5.2（连通变化率；原 5.1）",
    "# 37768: Q4 圆锥连通变化率题（dr/dt 恒定 -> dS/dt）-> 5.2（spec 5.2 明文；原 5.1）",
    "# 37770: (b) 表面积变化率 -> 5.2（连通变化率；原 5.1）",
    "# 38860: (i) 由 dV/dt 求 dr/dt（连通变化率）-> 5.2（原 5.1；父题 38859 保持 6.4 对应 (ii)）",
    "# 37108: (b) 水深变化率 -> 5.2（父题 37106 与 (a) 37107 均 5.2；原 5.1）",
    "# 其余 143 行核验后维持现标签 OK",
]

lines = header + [f"{q} {CHANGES.get(q, 'OK')}" for q in rows]
OUT.write_bytes(("\r\n".join(lines) + "\r\n").encode("utf-8"))

print("wrote", OUT, "rows:", len(rows), "changes:", len(CHANGES))
