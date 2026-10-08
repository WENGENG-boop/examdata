"""对真实 PDF 的目标断言：确认裁切精准且不混入版式噪声。仅临时验证用。"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import pymupdf

from examdata.paperqa.locator import locate

QP = ROOT / "tmpwork" / "probe" / "wec11.pdf"
MS = ROOT / "tmpwork" / "probe" / "wec11_rms.pdf"

NOISE = re.compile(r"DO NOT WRITE|\bSECTION\b|\bP\d{5}[A-Z]\b|turn over|\*P[A-Z0-9]{4,}\*|©", re.I)

checks = []


def check(name, cond, detail=""):
    checks.append((name, bool(cond), detail))


with pymupdf.open(QP) as qp, pymupdf.open(MS) as ms:
    # 1. Q4 收在总分行
    c = locate(qp, "4", "qp")
    t = " ".join(qp[p].get_text(clip=r) for p, r in c)
    check("qp Q4 单页", len(c) == 1, f"{len(c)}")
    check("qp Q4 页码=2", c[0][0] == 2, f"{c[0][0]}")
    check("qp Q4 y1<600 (旧 757.7)", c[0][1].y1 < 600, f"{c[0][1].y1:.1f}")
    check("qp Q4 含 'Total for Question 4'", "Total for Question 4" in t, t[-80:])

    # 2. MS 12(a) 高度收紧
    c = locate(ms, "12(a)", "ms")
    t = " ".join(ms[p].get_text(clip=r) for p, r in c)
    check("ms 12(a) 单页", len(c) == 1, f"{len(c)}")
    check("ms 12(a) 页码=10", c[0][0] == 10, f"{c[0][0]}")
    check("ms 12(a) h<250 (旧 618)", c[0][1].height < 250, f"{c[0][1].height:.1f}")
    check("ms 12(a) 含 'Answer'", "Answer" in t, t[:60])

    # 3. QP 12(b) 续页上边界
    c = locate(qp, "12(b)", "qp")
    last = c[-1][1]
    check("qp 12(b) 末页 index=12", c[-1][0] == 12, f"{c[-1][0]}")
    check("qp 12(b) 末页 y0>55 (旧 33.7)", last.y0 > 55, f"{last.y0:.1f}")

    # 4. 全题/子题一律无版式噪声
    dirty = []
    for q in ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12", "13", "14",
              "12(a)", "12(b)", "12(c)", "12(d)", "12(e)"]:
        for p, r in locate(qp, q, "qp"):
            m = NOISE.search(qp[p].get_text(clip=r))
            if m:
                dirty.append((q, p + 1, m.group(0)))
    check("QP 所有裁剪无噪声", not dirty, str(dirty))

    # 5. 13/14 只落在 p20（旧行为把 14 拖到 p25）
    check("qp 13 仅 p20", [p for p, _ in locate(qp, "13", "qp")] == [19],
          str([p for p, _ in locate(qp, "13", "qp")]))
    check("qp 14 仅 p20 (旧 6 页)", [p for p, _ in locate(qp, "14", "qp")] == [19],
          str([p for p, _ in locate(qp, "14", "qp")]))

    # 6. 带图题不丢图：Q4 的 diagram 在 p3 y≈93..365，必须仍被包含
    c = locate(qp, "4", "qp")
    check("qp Q4 包含整幅图 (y0<100)", c[0][1].y0 < 100, f"{c[0][1].y0:.1f}")
    check("qp Q4 x0 覆盖图左缘", c[0][1].x0 < 189, f"{c[0][1].x0:.1f}")

for name, ok, detail in checks:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}  {detail}")

print(f"\n{sum(1 for _, ok, _ in checks if ok)}/{len(checks)} passed")
sys.exit(0 if all(ok for _, ok, _ in checks) else 1)
