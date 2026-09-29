"""难度估计。

**明确边界**：这里产出的是 source="estimated" 的难度，与官方难度（如果有）
分表分行存储，绝不覆盖官方值。模型是确定性的启发式打分，不是 LLM 黑箱，
因此每次重跑结果一致，可被审计。

特征（都是解析产物里真实存在的量，不引入外部信息）：
- 分值：大题分越高，通常步骤越多、越难
- 题干长度：长题干往往含更多条件约束
- 小问数量与层级深度：层级越深，需要串联的步骤越多
- 关键词复杂度：出现 "prove" / "show that" / "hence" / "exact value"
  这类要求证明或精确解的措辞，显著提高难度
- 是否配图：需要读图/作图的题，认知负荷更高
- 知识点数量：跨知识点的综合题更难

打分归一化到 0-1，并把每个特征的原值与权重写进 features，
便于人工核对"为什么这道题被判为难"。
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..core.models import Difficulty, Document, Paper, Question, QuestionAsset, QuestionTaxonomy, Subject

MODEL_VERSION = "heuristic-v1"
SCALE = "0-1"

# 要求证明 / 精确解 / 串联前问的措辞：这些题对推理链长度要求高
_HARD_PHRASES: list[tuple[re.Pattern[str], float]] = [
    (re.compile(r"\bshow that\b", re.I), 0.18),
    (re.compile(r"\bprove\b", re.I), 0.22),
    (re.compile(r"\bverify\b", re.I), 0.10),
    (re.compile(r"\bexact value\b", re.I), 0.14),
    (re.compile(r"\bhence\b", re.I), 0.10),
    (re.compile(r"\bdeduce\b", re.I), 0.12),
    (re.compile(r"\bjustify\b", re.I), 0.12),
    (re.compile(r"\bexplain why\b", re.I), 0.10),
    (re.compile(r"\bin terms of\b", re.I), 0.08),
    (re.compile(r"\bleaving your answer\b", re.I), 0.06),
    (re.compile(r"\bcorrect to\b", re.I), 0.05),
    (re.compile(r"\bwithout using\b", re.I), 0.10),
]

# 权重：合计后线性映射到 0-1
W_MARKS = 0.34
W_LENGTH = 0.16
W_CHILDREN = 0.14
W_DEPTH = 0.08
W_PHRASES = 1.0  # 短语本身就是 0..0.2 量级的小权重，直接相加
W_FIGURE = 0.08
W_TAXONOMY = 0.06


@dataclass
class DifficultyEstimate:
    question_id: int
    value: float
    features: dict[str, Any] = field(default_factory=dict)


def _length_score(text: str) -> float:
    """对数饱和：0 字符 -> 0，约 600 字符 -> 1。"""
    n = len(text or "")
    if n <= 0:
        return 0.0
    return min(1.0, math.log1p(n) / math.log1p(600))


def estimate(
    *,
    marks: Optional[int],
    stem_text: str,
    child_count: int,
    depth: int,
    has_asset: bool,
    taxonomy_count: int,
) -> DifficultyEstimate:
    marks = marks or 0
    marks_score = min(1.0, marks / 12.0)
    length_score = _length_score(stem_text)
    children_score = min(1.0, child_count / 6.0)
    depth_score = min(1.0, depth / 3.0)

    phrase_total = 0.0
    phrase_hits: list[str] = []
    for pat, weight in _HARD_PHRASES:
        m = pat.search(stem_text or "")
        if m:
            phrase_total += weight
            phrase_hits.append(m.group(0).lower())
    phrase_score = min(1.0, phrase_total / 0.4)

    figure_score = 1.0 if has_asset else 0.0
    taxonomy_score = min(1.0, taxonomy_count / 3.0)

    raw = (
        W_MARKS * marks_score
        + W_LENGTH * length_score
        + W_CHILDREN * children_score
        + W_DEPTH * depth_score
        + W_FIGURE * figure_score
        + W_TAXONOMY * taxonomy_score
    )
    raw += phrase_total

    # 分值很低的小问（1 分）不该被判成"难"，给一个上限
    value = max(0.0, min(1.0, raw))
    if marks <= 1:
        value = min(value, 0.45)
    elif marks == 2:
        value = min(value, 0.65)

    features = {
        "marks": marks,
        "marks_score": round(marks_score, 4),
        "stem_chars": len(stem_text or ""),
        "length_score": round(length_score, 4),
        "child_count": child_count,
        "children_score": round(children_score, 4),
        "depth": depth,
        "depth_score": round(depth_score, 4),
        "hard_phrases": sorted(set(phrase_hits)),
        "phrase_score": round(phrase_score, 4),
        "has_asset": has_asset,
        "taxonomy_count": taxonomy_count,
        "taxonomy_score": round(taxonomy_score, 4),
        "weights": {
            "marks": W_MARKS,
            "length": W_LENGTH,
            "children": W_CHILDREN,
            "depth": W_DEPTH,
            "figure": W_FIGURE,
            "taxonomy": W_TAXONOMY,
        },
        "raw": round(raw, 4),
    }
    return DifficultyEstimate(question_id=0, value=round(value, 4), features=features)


def estimate_all(
    session: Session,
    *,
    subject_code: Optional[str] = None,
    replace: bool = False,
) -> dict[str, int]:
    """批量估计。只写 source="estimated" 的行，官方难度不受影响。"""
    stats = {"questions": 0, "written": 0}

    child_counts = dict(
        session.execute(
            select(Question.parent_id, func.count(Question.id))
            .where(Question.parent_id.is_not(None))
            .group_by(Question.parent_id)
        ).all()
    )
    asset_qids = set(session.scalars(select(QuestionAsset.question_id).distinct()).all())
    tax_counts = dict(
        session.execute(
            select(QuestionTaxonomy.question_id, func.count(QuestionTaxonomy.id)).group_by(
                QuestionTaxonomy.question_id
            )
        ).all()
    )

    stmt = (
        select(Question, Subject.code)
        .join(Paper, Paper.id == Question.paper_id)
        .join(Document, Document.id == Paper.document_id)
        .join(Subject, Subject.id == Document.subject_id, isouter=True)
        .order_by(Question.id)
    )
    if subject_code:
        stmt = stmt.where(Subject.code == subject_code)

    for question, _code in session.execute(stmt).all():
        stats["questions"] += 1
        if replace:
            for old in session.scalars(
                select(Difficulty).where(
                    Difficulty.question_id == question.id,
                    Difficulty.source == "estimated",
                )
            ).all():
                session.delete(old)
        else:
            exists = session.scalar(
                select(Difficulty.id).where(
                    Difficulty.question_id == question.id,
                    Difficulty.source == "estimated",
                )
            )
            if exists is not None:
                continue

        est = estimate(
            marks=question.marks,
            stem_text=question.stem_text or "",
            child_count=child_counts.get(question.id, 0),
            depth=question.depth or 0,
            has_asset=question.id in asset_qids,
            taxonomy_count=tax_counts.get(question.id, 0),
        )
        session.add(
            Difficulty(
                question_id=question.id,
                source="estimated",
                value=est.value,
                scale=SCALE,
                features=est.features,
                model_version=MODEL_VERSION,
            )
        )
        stats["written"] += 1
    session.flush()
    return stats
