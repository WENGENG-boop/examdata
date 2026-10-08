# -*- coding: utf-8 -*-
"""离线回归：numbering_problems 对单字母 i 的双重身份（字母 vs 罗马数字）判定。One-off."""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, "tools")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import cleanup_paper as C

TMP = Path(tempfile.mkdtemp(prefix="numfix_"))


def fake_index_dir(subject, year, season, paper):
    d = TMP / subject / f"{year}-{season}-{paper}"
    d.mkdir(parents=True, exist_ok=True)
    return d


C.B.index_dir = fake_index_dir


def run(questions):
    path = TMP / "9709" / "2024-Jun-11" / "cie-index.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"questions": questions}), encoding="utf-8")
    return C.numbering_problems("9709/2024/Jun/11")


def q(qid, parent=None):
    return {"question": qid, "parent": parent}


CASES = []
tops = lambda n: [q(str(i)) for i in range(1, n)]  # noqa: E731  顶层 1..n-1 补齐，避免顶层缺口干扰
# 1. a..k（含字母 i）直接子题 → 必须通过
CASES.append(("a..k 含 i 字母序列", tops(4) + [q("4")] + [q(f"4({c})", "4") for c in "abcdefghijk"], False, None))
# 2. a..h,j,k（真缺 i）→ 必须报
CASES.append(("a..h,j,k 真缺 i", tops(4) + [q("4")] + [q(f"4({c})", "4") for c in "abcdefghjk"], True, "4 子题号不连续"))
# 3. a,b,c → 通过
CASES.append(("a,b,c", tops(4) + [q("4"), q("4(a)", "4"), q("4(b)", "4"), q("4(c)", "4")], False, None))
# 4. 罗马数字 i,ii → 通过
CASES.append(("i,ii 罗马数字", tops(5) + [q("5"), q("5(i)", "5"), q("5(ii)", "5")], False, None))
# 5. a..j（含 i）→ 通过
CASES.append(("a..j 含 i", tops(6) + [q("6")] + [q(f"6({c})", "6") for c in "abcdefghij"], False, None))
# 6. 顶层缺 19 → 报顶层缺口
CASES.append(("顶层缺 19", [q(str(n)) for n in list(range(1, 19)) + [20]], True, "缺 19"))
# 7. a,b,d（真缺 c）→ 报
CASES.append(("a,b,d 真缺 c", tops(4) + [q("4"), q("4(a)", "4"), q("4(b)", "4"), q("4(d)", "4")], True, "4 子题号不连续"))
# 8. 修复前形态：a..h,j,k 直接 + 4(h)(i) 嵌套 → 报 4 缺 i
CASES.append(("a..h,j,k + 嵌套 4(h)(i)", tops(4) + [q("4")] + [q(f"4({c})", "4") for c in "abcdefghjk"]
              + [q("4(h)"), q("4(h)(i)", "4(h)")], True, "4 子题号不连续"))

failed = 0
for name, questions, want_problem, want_substr in CASES:
    problems, stats = run(questions)
    hit = any(want_substr in p for p in problems) if want_substr else not problems
    ok = (bool(problems) == want_problem) and hit
    print(f"{'PASS' if ok else 'FAIL'}  {name}: problems={problems} stats={stats}")
    failed += 0 if ok else 1

print(f"\n{'ALL PASS' if failed == 0 else f'{failed} FAILED'}")
sys.exit(1 if failed else 0)
