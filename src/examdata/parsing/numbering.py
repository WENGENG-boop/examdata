"""题号文法：把文本块识别为题目层级。

严禁按 PDF 页切题。层级由题号文法 + 缩进 + 字号/粗体共同决定，
题目持续到出现同级或更高级的下一个题号为止。

关键点：一个文本块可能同时给出**大题号与小问号**，例如 "6 (a) Work out ..."。
这种情况必须产出编号链 [6, (a)]，其中 6 是顶层题目，而不是把 6(a) 当作小问。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

# Cambridge 题号文法（实测归纳，research/cambridge.md §7）：
#   1        大题（可能独占一行）
#   (a)      小问
#   (i)      子小问
#   6 (a)    大题与小问同行
# 分值形如 [2] 或 (2 marks)
_TOP_LEVEL = re.compile(r"^\s*(\d{1,2})\s+(?=\S)")
_TOP_LEVEL_BARE = re.compile(r"^\s*(\d{1,2})\s*$")
_INLINE_SUB = re.compile(r"^\s*(\d{1,2})\s*\(([a-z])\)")
_SUB_PAREN_ALPHA = re.compile(r"^\s*\(([a-z])\)")
_SUB_PAREN_ROMAN = re.compile(r"^\s*\(([ivx]+)\)")
_MARKS_BRACKET = re.compile(r"\[(\d{1,3})\]")
_MARKS_PAREN = re.compile(r"\((\d{1,3})\s*marks?\)", re.I)

_ROMAN_VALUES = {"i": 1, "ii": 2, "iii": 3, "iv": 4, "v": 5, "vi": 6, "vii": 7, "viii": 8}

# 页眉页脚与噪声：题号识别前必须剥离
_NOISE_PATTERNS = [
    re.compile(r"^\s*\[?Turn over\]?\s*$", re.I),
    re.compile(r"^\s*©\s*UCLES.*$", re.I),
    re.compile(r"^\s*\[?\d{2,4}_\d{2}_\d{4}_\d{2}\]?\s*$"),
    re.compile(r"^\s*Page\s+\d+\s*(of\s+\d+)?\s*$", re.I),
    re.compile(r"^\s*\d{4}\/\d{2}\/[A-Z]\/[A-Z]\/\d{2}\s*$"),
    re.compile(r"^\s*\*\s*\d{10,}\s*\*\s*$"),
    # 试卷页脚形如 "[1] 0580/11/M/J/24 © UCLES 2"
    re.compile(r"^\s*\[\d+\]\s+\d{4}\/\d{2}\/.*$"),
]


def is_noise(text: str) -> bool:
    t = text.strip()
    if not t:
        return True
    return any(p.match(t) for p in _NOISE_PATTERNS)


@dataclass
class NumberMatch:
    """识别出的题号。"""

    label: str
    depth: int
    kind: str  # question / sub / part
    rest: str = ""
    confidence: float = 0.0


def match_numbers(text: str) -> list[NumberMatch]:
    """把一个文本块识别为编号链。

    >>> [m.label for m in match_numbers("6 (a) Work out 28 - 16")]
    ['6', '(a)']
    >>> [m.label for m in match_numbers("(ii) Find the value")]
    ['(ii)']
    """
    if is_noise(text):
        return []
    s = text.strip()
    if not s:
        return []

    # 大题号与小问同行："6 (a) ..."
    m = _INLINE_SUB.match(s)
    if m:
        return [
            NumberMatch(label=m.group(1), depth=0, kind="question", rest="", confidence=0.85),
            NumberMatch(
                label=f"({m.group(2)})",
                depth=1,
                kind="sub",
                rest=s[m.end():].strip(),
                confidence=0.9,
            ),
        ]

    m = _TOP_LEVEL.match(s)
    if m:
        return [
            NumberMatch(
                label=m.group(1),
                depth=0,
                kind="question",
                rest=s[m.end():].strip(),
                confidence=0.85,
            )
        ]

    m = _TOP_LEVEL_BARE.match(s)
    if m:
        return [NumberMatch(label=m.group(1), depth=0, kind="question", rest="", confidence=0.8)]

    m = _SUB_PAREN_ALPHA.match(s)
    if m:
        return [
            NumberMatch(
                label=f"({m.group(1)})",
                depth=1,
                kind="sub",
                rest=s[m.end():].strip(),
                confidence=0.9,
            )
        ]

    m = _SUB_PAREN_ROMAN.match(s)
    if m:
        return [
            NumberMatch(
                label=f"({m.group(1)})",
                depth=2,
                kind="part",
                rest=s[m.end():].strip(),
                confidence=0.9,
            )
        ]

    return []


def match_number(text: str) -> Optional[NumberMatch]:
    """兼容接口：返回编号链中的第一个。"""
    chain = match_numbers(text)
    return chain[0] if chain else None


def extract_marks(text: str) -> tuple[Optional[int], Optional[str]]:
    """抽取分值。返回 (marks, 匹配到的原始片段)。"""
    m = _MARKS_BRACKET.search(text)
    if m:
        return int(m.group(1)), m.group(0)
    m = _MARKS_PAREN.search(text)
    if m:
        return int(m.group(1)), m.group(0)
    return None, None


_ROMAN_ORDER = ["i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x"]


def roman_to_int(value: str) -> Optional[int]:
    return _ROMAN_VALUES.get(value.lower())


def int_to_roman(value: int) -> Optional[str]:
    """1 -> 'i'，2 -> 'ii'。超出支持范围返回 None。"""
    if 1 <= value <= len(_ROMAN_ORDER):
        return _ROMAN_ORDER[value - 1]
    return None


def is_ambiguous_sub_label(label: str) -> bool:
    """(i)/(v)/(x) 既可能是字母小问，也可能是罗马数字子小问。

    必须结合同级序列才能判定，这里只做形态判断。
    """
    return (
        len(label) == 3
        and label.startswith("(")
        and label.endswith(")")
        and label[1] in ("i", "v", "x")
    )
