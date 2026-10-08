"""相似题发现。

方法：**字符 n-gram 的 TF-IDF + 余弦相似度**，纯本地、确定性、无需外部模型。

为什么不用 embedding：现阶段没有可用的模型服务，且相似题的第一用途是
"同一知识点的同型题聚类"，字面 n-gram 在数学题干上已经能抓住
"同一模板换数字"这类真正需要去重的重复题；语义近似可以后续叠加。

关键工程细节：
- 题干先做**数字归一化**（所有数字替换为 #），否则"3x+5"和"7x+2"
  会被判成完全不同的题，而这恰恰是最需要识别为同型的一类。
- 只与**同科目**的题比较（跨科目的相似没有意义）。
- 用倒排索引（n-gram -> 题号）避免 O(N²) 全比。
- 只保留 score >= 阈值 的对，且每道题最多保留 top_k 个，控制表规模。
"""

from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from typing import Iterable, Optional

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..core.models import Document, Paper, Question, QuestionSimilarity, Subject

METHOD = "tfidf-ngram-v1"
NGRAM = 3
MIN_SCORE = 0.62
TOP_K = 5
MIN_TEXT_CHARS = 25

_NUM = re.compile(r"\d+(?:\.\d+)?")
_NON_WORD = re.compile(r"[^a-z0-9# ]+")
_SPACES = re.compile(r"\s+")
# 千分位空格："17 875" 与 "17875" 是同一个数，必须先合并再折叠，
# 否则同一道题会因为排版差异被归一化成两种形态，相似度算不出来。
# 只合并左侧 1-3 位、右侧恰好 3 位的组合，避免把相邻的两个独立数字粘起来。
_THOUSANDS = re.compile(r"(?<![\d.])(\d{1,3}) (?=\d{3}(?!\d))")


def normalize_text(text: str) -> str:
    """归一化：小写、千分位合并、数字折叠为 #、去标点、压缩空白。"""
    t = (text or "").lower()
    t = _THOUSANDS.sub(r"\1", t)
    t = _NUM.sub("#", t)
    t = _NON_WORD.sub(" ", t)
    t = _SPACES.sub(" ", t).strip()
    return t


def ngrams(text: str, n: int = NGRAM) -> list[str]:
    if len(text) < n:
        return [text] if text else []
    return [text[i : i + n] for i in range(len(text) - n + 1)]


def _tf(grams: Iterable[str]) -> Counter:
    return Counter(grams)


def _idf(doc_freq: dict[str, int], total: int) -> dict[str, float]:
    return {g: math.log((1 + total) / (1 + df)) + 1.0 for g, df in doc_freq.items()}


def find_similar(
    session: Session,
    *,
    subject_code: Optional[str] = None,
    replace: bool = False,
    question_ids: Optional[list[int]] = None,
    min_score: float = MIN_SCORE,
    top_k: int = TOP_K,
) -> dict[str, int]:
    """计算相似题并落库。replace=True 时先清空 method 相同的旧结果。"""
    stats = {"questions": 0, "pairs": 0, "skipped_short": 0, "skipped_ancestor": 0}

    rows = session.execute(
        _stmt(subject_code)
    ).all()

    targets = None if question_ids is None else set(question_ids)
    if targets == set():
        return stats
    if replace:
        deletion = delete(QuestionSimilarity).where(QuestionSimilarity.method == METHOD)
        scope = targets if targets is not None else ({row[0].id for row in rows} if subject_code else None)
        if scope is not None:
            deletion = deletion.where(QuestionSimilarity.question_a_id.in_(scope) | QuestionSimilarity.question_b_id.in_(scope))
        session.execute(deletion)

    # 1) 归一化 + 建倒排索引
    docs: list[tuple[int, str, Counter]] = []
    meta: dict[int, tuple[int, str]] = {}  # qid -> (paper_id, number_path)
    inverted: dict[str, list[int]] = defaultdict(list)
    subjects = {}
    for question, code, board_id, qualification_id in rows:
        subjects[question.id] = (board_id, qualification_id, code)
        norm = normalize_text(question.stem_text or "")
        meta[question.id] = (question.paper_id, question.number_path or "")
        if len(norm) < MIN_TEXT_CHARS:
            stats["skipped_short"] += 1
            continue
        grams = ngrams(norm)
        tf = _tf(grams)
        idx = len(docs)
        docs.append((question.id, norm, tf))
        for g in tf:
            inverted[g].append(idx)

    total = len(docs)
    stats["questions"] = total
    if total < 2:
        return stats

    # 2) IDF
    doc_freq = {g: len(ids) for g, ids in inverted.items()}
    idf = _idf(doc_freq, total)

    # 3) 向量归一化（只保留权重，长度后续乘）
    norms: list[float] = []
    weights: list[dict[str, float]] = []
    for _qid, _norm, tf in docs:
        w = {g: (1.0 + math.log(c)) * idf.get(g, 1.0) for g, c in tf.items()}
        n = math.sqrt(sum(v * v for v in w.values())) or 1.0
        weights.append(w)
        norms.append(n)

    # 4) 倒排累加点积：只有共享 n-gram 的题对才需要比较
    scores: dict[tuple[int, int], float] = defaultdict(float)
    for g, idxs in inverted.items():
        if len(idxs) < 2 or len(idxs) > 400:
            # 停用词级别的 n-gram（出现在几乎所有题里）不参与，省时间也降噪
            continue
        w = idf.get(g, 1.0)
        for a_pos in range(len(idxs)):
            a = idxs[a_pos]
            wa = weights[a].get(g)
            if wa is None:
                continue
            for b_pos in range(a_pos + 1, len(idxs)):
                b = idxs[b_pos]
                wb = weights[b].get(g)
                if wb is None:
                    continue
                scores[(a, b)] += wa * wb

    # 5) 余弦 + 阈值 + top_k
    per_question: dict[int, list[tuple[float, int]]] = defaultdict(list)
    for (a, b), dot in scores.items():
        cos = dot / (norms[a] * norms[b])
        if cos < min_score:
            continue
        qa, qb = docs[a][0], docs[b][0]
        if subjects[qa] != subjects[qb]:
            continue
        # 父子题（题干包含小问文本）在字面上天然高度重合，但它们是同一道题
        # 的不同层级，不是"相似题"。用同卷内的题号前缀关系剔除。
        if _is_ancestor_pair(meta.get(qa), meta.get(qb)):
            stats["skipped_ancestor"] += 1
            continue
        per_question[qa].append((cos, qb))
        per_question[qb].append((cos, qa))

    existing_pairs: set[tuple[int, int]] = set()
    if not replace:
        # 唯一约束是 (question_a_id, question_b_id, method)：不先查已存在的题对，
        # 第二次运行会直接撞约束报错。重复运行必须幂等。
        existing_pairs = {
            (a, b)
            for a, b in session.execute(
                select(
                    QuestionSimilarity.question_a_id, QuestionSimilarity.question_b_id
                ).where(QuestionSimilarity.method == METHOD)
            ).all()
        }

    written_pairs: set[tuple[int, int]] = set()
    for qa, neighbours in per_question.items():
        neighbours.sort(key=lambda t: (-t[0], t[1]))
        for cos, qb in neighbours[:top_k]:
            if targets is not None and qa not in targets and qb not in targets:
                continue
            lo, hi = (qa, qb) if qa < qb else (qb, qa)
            if (lo, hi) in written_pairs or (lo, hi) in existing_pairs:
                continue
            written_pairs.add((lo, hi))
            session.add(
                QuestionSimilarity(
                    question_a_id=lo,
                    question_b_id=hi,
                    method=METHOD,
                    score=round(cos, 4),
                    features={
                        "ngram": NGRAM,
                        "min_score": min_score,
                        "text_chars_a": len(docs[[d[0] for d in docs].index(lo)][1]),
                    },
                )
            )
            stats["pairs"] += 1
    session.flush()
    return stats


_ROOT = re.compile(r"^\s*(\d+)")

def _root_of(number_path: str) -> str:
    m = _ROOT.match(number_path or "")
    return m.group(1) if m else ""


def _is_ancestor_pair(
    a: Optional[tuple[int, str]], b: Optional[tuple[int, str]]
) -> bool:
    """同一道大题内部的题对不算相似题。

    两种情形都剔除，理由是同一个：对"找同型题"这个用途来说，
    用户手上已经有这道大题了，把它的其它小问还给他没有信息量。

    1. 父子关系：paper 14 的 "8" 与 "8(d)"、"3" 与 "3(b)"。
    2. 兄弟关系：paper 5 的 "10(a)" 与 "10(b)" —— 它们措辞几乎一致
       （"Find the value of a/b. Give a geometrical reason..."），
       字面相似度高达 0.89，但它们是同一道题的两个小问。

    不同卷的同号题不受影响（那才是真正需要识别的重复题）。
    """
    if a is None or b is None:
        return False
    if a[0] != b[0]:
        return False
    pa, pb = a[1], b[1]
    if not pa or not pb:
        return False
    if pa == pb:
        return True
    if pa.startswith(pb) or pb.startswith(pa):
        return True
    ra, rb = _root_of(pa), _root_of(pb)
    return bool(ra) and ra == rb


def _stmt(subject_code: Optional[str]):
    stmt = (
        select(Question, Subject.code, Document.board_id, Document.qualification_id)
        .join(Paper, Paper.id == Question.paper_id)
        .join(Document, Document.id == Paper.document_id)
        .join(Subject, Subject.id == Document.subject_id, isouter=True)
        .order_by(Question.id)
    )
    if subject_code:
        stmt = stmt.where(Subject.code == subject_code)
    return stmt
