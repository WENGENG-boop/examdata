"""BM25（Okapi）打分：纯标准库、确定性、无状态。

公式（参数固定，改动等同于模型版本变化）：

    score(q, d) = Σ_{t ∈ q} IDF(t) · tf(t,d) · (k1 + 1)
                  / (tf(t,d) + k1 · (1 − b + b · dl(d) / avgdl))

    IDF(t) = ln(1 + (N − df(t) + 0.5) / (df(t) + 0.5))

    k1 = 1.2，b = 0.75

- ``N`` 是语料文档数（对本题库 = 该科目全部 point），``df(t)`` 是包含 ``t`` 的文档数。
- ``tf`` 是**加权字段频次**：``tf(t,d) = Σ_f w_f · count_f(t)``，
  ``dl(d) = Σ_f w_f · len_f(d)``。字段与权重见 ``corpus.doc_for``
  （内容点自身句子 ×3、大纲原文 ×1、祖先链名字 ×1）。
  这是 BM25F 的简化形式：先把字段加权合成单一词频，再做长度归一。
- 查询侧按去重词计数（题干短，重复词不额外加权）。
- 分数相同的候选按 key 升序输出，保证任何一次运行的结果都可复现。
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Iterable, Sequence

from .text import term_counts, tokenize

K1 = 1.2
B = 0.75


@dataclass
class Doc:
    """一个候选文档：``key`` 是内容点 code，``fields`` 是 字段名 -> (权重, 文本)。"""

    key: str
    fields: dict[str, tuple[float, str]] = field(default_factory=dict)


def idf(n_docs: int, doc_freq: int) -> float:
    """BM25 概率型 IDF，恒为正（避免高频词贡献负分）。"""
    return math.log(1.0 + (n_docs - doc_freq + 0.5) / (doc_freq + 0.5))


class Bm25Index:
    """一次性建好的倒排索引；``score`` 是纯查询，不修改任何状态。"""

    def __init__(self, docs: Sequence[Doc]) -> None:
        self._keys: list[str] = []
        self._postings: dict[str, dict[int, float]] = {}
        self._lengths: list[float] = []
        for position, doc in enumerate(docs):
            counts: dict[str, float] = {}
            length = 0.0
            for weight, text in doc.fields.values():
                tokens = tokenize(text)
                length += weight * len(tokens)
                for token in tokens:
                    counts[token] = counts.get(token, 0.0) + weight
            self._keys.append(doc.key)
            self._lengths.append(length)
            for term, weighted_tf in counts.items():
                self._postings.setdefault(term, {})[position] = weighted_tf
        self._n_docs = len(docs)
        self._avgdl = (sum(self._lengths) / self._n_docs) if self._n_docs else 0.0
        self._idf = {
            term: idf(self._n_docs, len(posting)) for term, posting in self._postings.items()
        }

    def __len__(self) -> int:
        return self._n_docs

    @property
    def keys(self) -> list[str]:
        return list(self._keys)

    @property
    def avgdl(self) -> float:
        return self._avgdl

    def term_idf(self, term: str) -> float:
        return self._idf.get(term, 0.0)

    def score(self, text: str | None, *, top_k: int | None = None) -> list[tuple[str, float]]:
        """返回 [(key, score)]，按分数降序（同分按 key 升序），只保留 score > 0。"""
        counts = term_counts(text)
        if not counts or not self._n_docs:
            return []
        avgdl = self._avgdl or 1.0
        totals: dict[int, float] = {}
        for term in counts:
            posting = self._postings.get(term)
            if not posting:
                continue
            weight = self._idf[term]
            for position, weighted_tf in posting.items():
                length = self._lengths[position]
                denominator = weighted_tf + K1 * (1.0 - B + B * length / avgdl)
                totals[position] = totals.get(position, 0.0) + (
                    weight * weighted_tf * (K1 + 1.0) / denominator
                )
        ranked = sorted(totals.items(), key=lambda item: (-item[1], self._keys[item[0]]))
        out = [(self._keys[position], score) for position, score in ranked if score > 0.0]
        return out[:top_k] if top_k is not None else out

    def best(self, text: str | None) -> tuple[str, float] | None:
        hits = self.score(text, top_k=1)
        return hits[0] if hits else None


def build_index(docs: Iterable[Doc]) -> Bm25Index:
    return Bm25Index(list(docs))


__all__ = ["B", "K1", "Bm25Index", "Doc", "build_index", "idf"]
