"""分词与词形归一：确定性、纯标准库。

规则固定（改动等同于模型版本变化）：

1. NFKC 归一 + 小写；
2. 取 Unicode 字母/数字串（``[^\\W_]+``）；
3. 丢弃长度 < 2 的 token（``x``、``a`` 这类单字符在题干与大纲里歧义太大）
   与纯数字 token（数字是题目数据而非知识点信号，且在语料里 df 极低，
   会把 IDF 抬得虚高，一个巧合的数字就能压过真正的主题词）；
4. 停用词按**折叠前的小写原形**匹配，表见 ``STOPWORDS``：
   功能词 + 少量只出现在题干里的指令词（calculate/find/show…）。
   刻意不收录 state/value/work/table/solve 这类在部分科目大纲里是术语的词；
5. 复数与词尾折叠 ``_fold``：``sses``→``ss``、``ies``→``y``、
   其余不以 ``ss``/``is``/``us``/``os`` 结尾的尾 ``s`` 去掉。
   折叠对查询与文档一视同仁，因此 "photosynthesis" 与 "photosynthesis"
   这类词形差异不会造成漏配。
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter

_TOKEN_RE = re.compile(r"[^\W_]+")
_DIGITS_RE = re.compile(r"^\d+$")

STOPWORDS: frozenset[str] = frozenset(
    """
    a an the and or but of to in on at by for with from as is are was were be been being
    it its this that these those which who whom whose there here their they them he she
    his her you your we our us i not no nor so such than then thus also both each few
    more most other some only own same too very can could may might must shall should
    will would do does did done doing have has had having if when where why how what all
    any because before after during between into through about above below up down out
    off over under again further once calculate find show hence give write answer marks
    question questions total following
    """.split()
)


def _fold(token: str) -> str:
    """去掉常见复数/词尾，减少 "plants" 与 "plant" 这类漏配。"""
    if len(token) <= 3:
        return token
    if token.endswith("sses"):
        return token[:-2]
    if token.endswith("ies") and len(token) > 4:
        return token[:-3] + "y"
    if token.endswith("s") and not token.endswith(("ss", "is", "us", "os")):
        return token[:-1]
    return token


def tokenize(text: str | None) -> list[str]:
    """切成归一后的词序列（保留顺序与重复，便于测试与统计）。"""
    if not text:
        return []
    normalized = unicodedata.normalize("NFKC", text).lower()
    out: list[str] = []
    for raw in _TOKEN_RE.findall(normalized):
        if len(raw) < 2 or _DIGITS_RE.match(raw) or raw in STOPWORDS:
            continue
        out.append(_fold(raw))
    return out


def term_counts(text: str | None) -> Counter[str]:
    """去重词频。BM25 查询侧按去重词计数：题干短，重复词不额外加权。"""
    return Counter(set(tokenize(text)))


__all__ = ["STOPWORDS", "term_counts", "tokenize"]
