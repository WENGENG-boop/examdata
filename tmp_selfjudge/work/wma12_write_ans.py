"""Write WMA12-p01.ans.txt from pack order + final r2 decisions."""
import re
from pathlib import Path

PACK = Path("tmp_selfjudge/r2/ial18-mathematics/WMA12-p01.txt")
OUT = Path("tmp_selfjudge/r2/ial18-mathematics/WMA12-p01.ans.txt")

CHANGES = {
    37626: "WMA12-5.1",
    37632: "WMA12-4.4",
    37633: "WMA12-4.3",
    37362: "WMA12-4.3",
    36338: "WMA12-4.3",
    36513: "WMA12-5.3",
    38884: "WMA12-7.1",
}

ALLOWED = {f"WMA12-{a}.{b}" for a, b in
           [(1, 1), (1, 2), (1, 3), (2, 1), (3, 1),
            (4, 1), (4, 2), (4, 3), (4, 4), (4, 5),
            (5, 1), (5, 2), (5, 3), (6, 1), (6, 2),
            (7, 1), (8, 1), (8, 2), (8, 3)]}

rows = []
for line in PACK.read_text(encoding="utf-8").splitlines():
    m = re.match(r"^\[(\d+)\] (\d+) ", line)
    if m:
        rows.append(int(m.group(2)))

assert len(rows) == 134, len(rows)
assert len(set(rows)) == 134, "dup qids"
for c in CHANGES.values():
    assert c in ALLOWED, c
missing = [q for q in CHANGES if q not in rows]
assert not missing, missing

header = [
    "# WMA12-p01 r2 selfjudge answers (134 questions)",
    "# 37626: y=a^(-x)+4 图像草图(渐近线/交点) -> 5.1（y=a^x 及其图像；原 2.1 系误标）",
    "# 37632: (i) 等比级数求和 Σ25(1/5)^r -> 4.4（几何级数求和；原 4.3 为增减/周期）",
    "# 37633: (ii) 递推序列 u_{n+1}=3u_n/(u_n+2) 周期性/单调性讨论 -> 4.3（原 4.1）",
    "# 37362: a_{n+1}=4-a_n, 求 a_107 需用周期性 -> 4.3（原 4.1）",
    "# 36338: a_n=cos^2(nπ/3) 周期序列求和 -> 4.3（原 4.1）",
    "# 36513: 碳-14 方程 N=kλ^t 解 t -> 5.3（a^x=b 型方程求解；原 5.1 为图像）",
    "# 38884: 容器优化题 (a) 建立 A=Px^2+Q/x -> 7.1（极值应用系列；原 2.1）",
    "# 其余 127 行核验后维持现标签 OK",
]

lines = header + [f"{q} {CHANGES.get(q, 'OK')}" for q in rows]
OUT.write_bytes(("\r\n".join(lines) + "\r\n").encode("utf-8"))

print("wrote", OUT, "rows:", len(rows), "changes:", len(CHANGES))
