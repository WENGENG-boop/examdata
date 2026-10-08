# -*- coding: utf-8 -*-
"""label_head_match 回归测试。

覆盖：全角括号（Bug A）、同视觉行父子标签误绑（Bug B）、
罗马数字被 OCR 读成 0/1/l（类别 2）。
"""
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import unicodedata

import verify_ocr as V

cases = [
    # --- Bug A：全角括号 + 括号内空格 ---
    ("11 \uff08 a \uff09", "11(a)", True),
    ("11 \uff08 a \uff09", "11", True),
    ("\uff08 a \uff09 Describ e the role", "11(a)", True),
    ("(a) Descri be the role", "11(a)", True),
    ("one mark per bullet point", "11(a)", False),
    ("elephants are big", "1(e)", False),
    ("4 \uff08 e \uff09 Cross-country", "4(e)", True),
    ("2 (c) The diagram", "2(c)", True),
    ("10 \uff08 a \uff09 five from the number", "10(a)", True),
    ("10a five from the number", "10(a)", True),
    # --- 父号不在本区域内，只剩后缀 ---
    ("(ii) something", "1(a)(ii)", True),
    ("ii something", "1(a)(ii)", True),
    ("5(a) describe how Louisa", "5", True),      # 5(a) 是 5 的子题
    # --- 类别 2：罗马数字 (i) 被 OCR 读成 (0) ---
    ("(2) (a) (0) Abilities are enduring state", "2(a)(i)", True),
    ("2a0 abilities are enduring state", "2(a)(i)", True),
    ("(c) (0) Explain, using a sporting example", "2(c)(i)", True),
    ("c0 explain using a sporting example", "2(c)(i)", True),
    ("(g) (i) at higher altitudes", "1(g)(i)", True),
    ("g0 define intrinsic motivation", "2(g)(i)", True),
    ("(e) (0) Suggest why", "2(e)(i)", True),
    ("(i) at higher altitudes", "1(g)(i)", True),
    ("(0) Abilities are enduring", "2(a)(i)", True),
    ("(1) at higher altitudes", "1(g)(i)", True),
    # --- 必须仍然判否 ---
    ("5(a) describe how Louisa", "4(a)", False),
    ("1(a)", "1(a)(i)", False),
    ("(2) (a) Abilities are enduring", "2(a)(i)", False),
    ("2023 involves ballistic", "3", False),
    ("(b) something", "2(a)(i)", False),
]

bad = 0
for text, qid, expected in cases:
    got = V.label_head_match(text, qid)
    mark = "OK " if got == expected else "BAD"
    if got != expected:
        bad += 1
    print(mark, repr(text)[:46], qid, "got", got, "exp", expected)
print("cases =", len(cases), "bad =", bad)
print("NFKC check:", repr(unicodedata.normalize("NFKC", "11 \uff08 a \uff09")))
raise SystemExit(1 if bad else 0)
