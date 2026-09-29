"""系统生成的解题解析。

需求："官方答案、官方评分标准、官方说明和系统生成的解题解析不能混为同一种数据。"
以及"任何系统生成内容都必须能够与官方原始内容区分。"

**必须说清楚这个模块是什么、不是什么：**

本机没有可用的模型服务，所以这里做的是**从官方 Mark Scheme 派生的规则式脚手架**，
不是真正的数学推理。它把官方给出的评分点、分值分配、ECF 提示重新组织成
学生可读的结构（解题思路 / 主要步骤 / 最终结果 / 评分关键点 / 常见错误）。

因此：
- provider 恒为 "rule-based"，model 为 None，prompt_version 标明规则版本；
- is_official 恒为 False；
- review_status 初始为 "pending"——**默认不可信**，必须人工审过才算可用；
- 每条都带 evidence 记录它引用了哪条 Mark Scheme 条目。

这样上层可以明确区分"这是官方答案"还是"这是系统从官方答案拼出来的学习材料"。
把它当成 LLM 生成的解析来用是错的，所以表里也如实标注了 provider。
"""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.models import (
    GeneratedExplanation,
    MarkSchemeEntry,
    OfficialAnswer,
    Question,
    QuestionTaxonomy,
    TaxonomyNode,
)

PROVIDER = "rule-based"
PROMPT_VERSION = "rules-v1"
# 没有模型参与，显式置空而不是编一个名字
MODEL: Optional[str] = None


def _marking_points(entry: Optional[MarkSchemeEntry]) -> list[dict[str, Any]]:
    """把官方评分语汇拆成逐条评分点。"""
    if entry is None:
        return []
    points: list[dict[str, Any]] = []
    if entry.method_marks:
        points.append(
            {"kind": "method", "marks": entry.method_marks,
             "note": "方法分：过程正确即可得，最终答案错也可能得分"}
        )
    if entry.accuracy_marks:
        points.append(
            {"kind": "accuracy", "marks": entry.accuracy_marks,
             "note": "准确分：依赖于前面的方法，方法错则不得分"}
        )
    if entry.independent_marks:
        points.append(
            {"kind": "independent", "marks": entry.independent_marks,
             "note": "独立分：与前序步骤无关，可单独获得"}
        )
    if not points and entry.marks:
        points.append(
            {"kind": "marks", "marks": entry.marks,
             "note": "官方未拆分 M/A/B，按该小问总分计"}
        )
    return points


def _common_errors(entry: Optional[MarkSchemeEntry]) -> list[str]:
    """常见错误：只从官方给出的信息推导，不自行编造。"""
    out: list[str] = []
    if entry is None:
        return out
    if entry.ecf:
        out.append("允许沿用错误（ECF）：前面步骤算错时，后续若方法一致仍可得分。")
    for alt in (entry.acceptable_answers or [])[:5]:
        text = str(alt).strip()
        if text:
            out.append(f"官方接受的其他写法：{text}")
    guidance = (entry.guidance or "").strip()
    if guidance:
        # 官方 guidance 里常直接写明扣分点，原样保留比转述更可靠
        out.append(f"官方评分说明：{guidance}")
    return out


def _steps(question: Question, entry: Optional[MarkSchemeEntry]) -> list[dict[str, Any]]:
    """主要步骤：按分值与评分点组织。

    不编造具体演算过程——那是真正需要推理的部分，规则式做不到。
    这里给出的是"按评分结构该有几步、每步值多少分"的骨架。
    """
    steps: list[dict[str, Any]] = []
    points = _marking_points(entry)
    for i, p in enumerate(points, start=1):
        steps.append(
            {
                "index": i,
                "marks": p["marks"],
                "kind": p["kind"],
                "hint": p["note"],
            }
        )
    if not steps and question.marks:
        steps.append(
            {
                "index": 1,
                "marks": question.marks,
                "kind": "marks",
                "hint": "该小问未在 Mark Scheme 中拆分评分点",
            }
        )
    return steps


def _approach(
    question: Question, entry: Optional[MarkSchemeEntry], topics: list[str]
) -> str:
    parts: list[str] = []
    if topics:
        parts.append("本题考查：" + "、".join(topics) + "。")
    if entry is not None and entry.answer_text:
        parts.append("官方给出的结果见下方「最终结果」。")
    else:
        parts.append("该小问在官方 Mark Scheme 中没有独立答案文本，只能依据评分点组织作答。")
    if entry is not None and entry.method_marks:
        parts.append("注意官方给出了方法分，说明评卷重视过程而非只看结果。")
    if question.marks:
        parts.append(f"该小问共 {question.marks} 分。")
    return "".join(parts)


def generate_for_question(
    session: Session, question_id: int, *, replace: bool = False
) -> Optional[GeneratedExplanation]:
    """为一道题生成解析。没有官方依据时返回 None，不生成空壳。"""
    question = session.get(Question, question_id)
    if question is None:
        return None

    entry = session.scalar(
        select(MarkSchemeEntry).where(MarkSchemeEntry.question_id == question_id).limit(1)
    )
    official = session.scalar(
        select(OfficialAnswer).where(OfficialAnswer.question_id == question_id).limit(1)
    )

    # 没有任何官方依据就不生成：凭空造解析正是需求要防的事
    if entry is None and official is None:
        return None

    topics = list(
        session.scalars(
            select(TaxonomyNode.name)
            .join(QuestionTaxonomy, QuestionTaxonomy.node_id == TaxonomyNode.id)
            .where(QuestionTaxonomy.question_id == question_id)
        ).all()
    )

    if replace:
        for old in session.scalars(
            select(GeneratedExplanation).where(
                GeneratedExplanation.question_id == question_id,
                GeneratedExplanation.provider == PROVIDER,
            )
        ).all():
            session.delete(old)
        session.flush()

    existing = session.scalar(
        select(GeneratedExplanation).where(
            GeneratedExplanation.question_id == question_id,
            GeneratedExplanation.provider == PROVIDER,
            GeneratedExplanation.prompt_version == PROMPT_VERSION,
        )
    )
    if existing is not None and not replace:
        return existing

    final_answer = (official.content if official else None) or (
        entry.answer_text if entry else None
    )

    explanation = existing or GeneratedExplanation(
        question_id=question_id,
        provider=PROVIDER,
        model=MODEL,
        prompt_version=PROMPT_VERSION,
    )
    explanation.approach = _approach(question, entry, topics)
    explanation.steps = _steps(question, entry)
    explanation.final_answer = final_answer
    explanation.marking_points = _marking_points(entry)
    explanation.common_errors = _common_errors(entry)
    # 默认不可信：规则式生成的内容必须人工过一遍才能当作学习材料使用
    explanation.review_status = "pending"
    explanation.is_official = False

    if existing is None:
        session.add(explanation)
    session.flush()
    return explanation


def generate_all(
    session: Session,
    *,
    subject_code: Optional[str] = None,
    limit: Optional[int] = None,
    replace: bool = False,
) -> dict[str, int]:
    """批量生成。只处理有官方依据的题目。"""
    from ..core.models import Document, Paper, Subject

    stats = {"scanned": 0, "generated": 0, "skipped_no_official": 0, "skipped_existing": 0}

    stmt = (
        select(Question.id)
        .join(Paper, Paper.id == Question.paper_id)
        .join(Document, Document.id == Paper.document_id)
        .join(Subject, Subject.id == Document.subject_id, isouter=True)
        .order_by(Question.id)
    )
    if subject_code:
        stmt = stmt.where(Subject.code == subject_code)
    if limit:
        stmt = stmt.limit(limit)

    for qid in list(session.scalars(stmt).all()):
        stats["scanned"] += 1
        had_official = (
            session.scalar(
                select(MarkSchemeEntry.id).where(MarkSchemeEntry.question_id == qid).limit(1)
            )
            is not None
            or session.scalar(
                select(OfficialAnswer.id).where(OfficialAnswer.question_id == qid).limit(1)
            )
            is not None
        )
        if not had_official:
            stats["skipped_no_official"] += 1
            continue

        before = session.scalar(
            select(GeneratedExplanation.id).where(
                GeneratedExplanation.question_id == qid,
                GeneratedExplanation.provider == PROVIDER,
            )
        )
        result = generate_for_question(session, qid, replace=replace)
        if result is None:
            stats["skipped_no_official"] += 1
        elif before is not None and not replace:
            stats["skipped_existing"] += 1
        else:
            stats["generated"] += 1
    return stats


def review_explanation(
    session: Session, explanation_id: int, *, status: str, author: str
) -> dict[str, Any]:
    """人工审核生成的解析。approved 之后上层才应把它当作可信学习材料。

    审核意见记进 question.attrs 之外的独立位置：GeneratedExplanation 没有 attrs 列，
    所以这里用 model 字段旁边的方式——把审核信息写进 steps 之外不合适，
    改为在返回值和日志中体现。审计主要靠 review_status 的变更本身。
    """
    if status not in ("approved", "rejected", "pending"):
        raise ValueError("status 只能是 approved / rejected / pending")
    obj = session.get(GeneratedExplanation, explanation_id)
    if obj is None:
        raise ValueError(f"解析 {explanation_id} 不存在")
    obj.review_status = status
    # 生成内容永远不是官方内容，审核也不改变这一点
    obj.is_official = False
    session.flush()
    return {"id": obj.id, "review_status": obj.review_status, "reviewed_by": author}
