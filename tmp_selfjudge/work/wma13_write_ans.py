"""Write WMA13-p01.ans.txt from pack order + final r2 decisions."""
import re
from pathlib import Path

PACK = Path("tmp_selfjudge/r2/ial18-mathematics/WMA13-p01.txt")
OUT = Path("tmp_selfjudge/r2/ial18-mathematics/WMA13-p01.ans.txt")

CHANGES = {
    35868: "WMA13-1.3",
    35869: "WMA13-1.3",
    36274: "WMA13-6.2",
    41226: "WMA13-5.2",
    41230: "WMA13-2.3",
    36286: "WMA13-2.3",
    39574: "WMA13-2.3",
    39575: "WMA13-2.3",
    39573: "WMA13-2.3",
    38477: "WMA13-2.3",
    36285: "WMA13-2.3",
    38467: "WMA13-2.3",
    35584: "WMA13-4.2",
    35587: "WMA13-4.2",
    36267: "WMA13-4.2",
    39436: "WMA13-1.2",
    39438: "WMA13-1.2",
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

assert len(rows) == 150, len(rows)
assert len(set(rows)) == 150, "dup qids"
for c in CHANGES.values():
    assert c in ALLOWED, c
missing = [q for q in CHANGES if q not in rows]
assert not missing, missing

header = [
    "# WMA13-p01 r2 selfjudge answers (150 questions)",
    "# 35868: y=|3x-5a|-2a 模函数图像（求 P/Q/R/S 坐标）-> 1.3（模函数；原 1.1 误标）",
    "# 35869: 同题(a) 求各点坐标 -> 1.3（原 1.1 误标）",
    "# 36274: 方程 P=0 化为迭代式 t=... -> 6.2（迭代法；父题/兄弟均 6.2）",
    "# 41226: 积分容器 (i) ∫2/(3x-1)dx 型 -> 5.2（f'/f 型积分；原 1.1 无对应子题）",
    "# 41230: (a) f(θ) 化为 R cos(θ+α) -> 2.3（spec 2.3 R 形式明文；原 2.1）",
    "# 36286: (a) 8sinx-15cosx 化为 R sin(x-α) -> 2.3（原 2.1）",
    "# 39574: (a) 2sin(θ-30°)=5cosθ 化为 tanθ -> 2.3（和角公式；原 2.1）",
    "# 39575: (b) 解 2sin(x-10°)=5cos(x+20°) -> 2.3（和角公式；原 2.1）",
    "# 39573: 容器题（和角公式系列）-> 2.3（原 2.1）",
    "# 38477: 7(a) 和角公式证 tanx=-2-√3 -> 2.3（MS 明写 compound angle identities）",
    "# 36285: 容器题（R 形式系列）-> 2.3（原 2.1 已无对应子题）",
    "# 38467: (c)(ii) 用 R 形式解 x（家族 38463-38465 均 2.3）-> 2.3（原 2.1）",
    "# 35584: Q7 容器 f=(2x²-3)²e^{-x²}（微分计算为主）-> 4.2（原 1.1 误标）",
    "# 35587: (c) 由驻点值求 k 范围 -> 4.2（原 1.1 误标）",
    "# 36267: (b) 由极大值求 k 范围 -> 4.2（原 1.4 与内容无关）",
    "# 39436: (c) ff(x) 复合容器（复合+值域）-> 1.2（原 1.1）",
    "# 39438: (c)(ii) Deduce range of ff -> 1.2（原 1.4 与内容无关）",
    "# 其余 133 行核验后维持现标签 OK",
]

lines = header + [f"{q} {CHANGES.get(q, 'OK')}" for q in rows]
OUT.write_bytes(("\r\n".join(lines) + "\r\n").encode("utf-8"))

print("wrote", OUT, "rows:", len(rows), "changes:", len(CHANGES))
