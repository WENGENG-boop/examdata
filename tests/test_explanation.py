"""生成解析测试：官方内容与生成内容必须严格分离。

需求两条硬约束：
- "官方答案、官方评分标准、官方说明和系统生成的解题解析不能混为同一种数据。"
- "任何系统生成内容都必须能够与官方原始内容区分。"

这里不只测"字段值对不对"，更测**隔离性**：生成器无论怎么跑，
都不能写出一条 is_official=True 的行，也不能覆盖官方答案。
"""

from __future__ import annotations

import pytest
from sqlalchemy import func, select

from examdata.core.db import session_scope
from examdata.core.models import (
    GeneratedExplanation,
    MarkSchemeEntry,
    OfficialAnswer,
    Paper,
    Question,
)
from examdata.intelligence import (
    EXPLANATION_PROVIDER,
    generate_explanations,
    generate_for_question,
    review_explanation,
)


def _question_with_official(session) -> int | None:
    return session.scalar(
        select(MarkSchemeEntry.question_id)
        .where(MarkSchemeEntry.question_id.is_not(None))
        .order_by(MarkSchemeEntry.id)
        .limit(1)
    )


def _question_without_official(session) -> int | None:
    """找一道既无评分条目也无官方答案的题。"""
    with_official = set(
        session.scalars(
            select(MarkSchemeEntry.question_id).where(
                MarkSchemeEntry.question_id.is_not(None)
            )
        ).all()
    ) | set(session.scalars(select(OfficialAnswer.question_id)).all())
    for qid in session.scalars(select(Question.id).order_by(Question.id)).all():
        if qid not in with_official:
            return qid
    return None


# --------------------------------------------------------------------------
# 隔离性（最重要）
# --------------------------------------------------------------------------


def test_generated_content_is_never_official():
    with session_scope() as s:
        bad = s.scalar(
            select(func.count(GeneratedExplanation.id)).where(
                GeneratedExplanation.is_official.is_(True)
            )
        )
    assert bad == 0, "生成内容绝不能标为官方"


def test_generator_marks_rows_non_official():
    with session_scope() as s:
        qid = _question_with_official(s)
        if qid is None:
            pytest.skip("没有带官方评分条目的题目")
        obj = generate_for_question(s, qid, replace=True)
    assert obj is not None
    assert obj.is_official is False
    assert obj.provider == EXPLANATION_PROVIDER


def test_generator_never_overwrites_official_answer():
    """生成前后官方答案必须逐字节不变。"""
    with session_scope() as s:
        qid = _question_with_official(s)
        if qid is None:
            pytest.skip("没有带官方评分条目的题目")
        before = [
            (a.id, a.content)
            for a in s.scalars(
                select(OfficialAnswer).where(OfficialAnswer.question_id == qid)
            ).all()
        ]
        generate_for_question(s, qid, replace=True)

    with session_scope() as s:
        after = [
            (a.id, a.content)
            for a in s.scalars(
                select(OfficialAnswer).where(OfficialAnswer.question_id == qid)
            ).all()
        ]
    assert before == after, "生成解析不得改动官方答案"


def test_generated_rows_are_pending_by_default():
    """默认不可信：未经人工审核的生成内容不应被当作可信材料。"""
    with session_scope() as s:
        qid = _question_with_official(s)
        if qid is None:
            pytest.skip("没有带官方评分条目的题目")
        obj = generate_for_question(s, qid, replace=True)
        assert obj.review_status == "pending"


# --------------------------------------------------------------------------
# 只在有官方依据时生成
# --------------------------------------------------------------------------


def test_no_generation_without_official_basis():
    """没有官方依据就不生成——凭空造解析正是需求要防的事。"""
    with session_scope() as s:
        qid = _question_without_official(s)
        if qid is None:
            pytest.skip("所有题目都有官方依据")
        result = generate_for_question(s, qid, replace=True)
    assert result is None


def test_missing_question_returns_none():
    with session_scope() as s:
        assert generate_for_question(s, 10**9) is None


def test_generate_all_reports_skips():
    with session_scope() as s:
        stats = generate_explanations(s, limit=40)
    assert stats["scanned"] <= 40
    assert stats["generated"] + stats["skipped_no_official"] + stats["skipped_existing"] == stats["scanned"]


# --------------------------------------------------------------------------
# 内容质量
# --------------------------------------------------------------------------


def test_explanation_has_structure():
    with session_scope() as s:
        row = s.scalar(
            select(GeneratedExplanation).order_by(GeneratedExplanation.id).limit(1)
        )
    if row is None:
        pytest.skip("尚未生成解析，先跑 examdata explain")
    assert row.approach
    assert isinstance(row.steps, list)
    assert isinstance(row.marking_points, list)
    assert isinstance(row.common_errors, list)


def test_explanation_is_reproducible():
    """确定性：同一题重算两次结果必须一致（这是规则式而非模型生成的直接体现）。"""
    with session_scope() as s:
        qid = _question_with_official(s)
        if qid is None:
            pytest.skip("没有带官方评分条目的题目")
        first = generate_for_question(s, qid, replace=True)
        snapshot = (first.approach, list(first.steps), list(first.marking_points))

    with session_scope() as s:
        second = generate_for_question(s, qid, replace=True)
        again = (second.approach, list(second.steps), list(second.marking_points))
    assert snapshot == again


def test_marking_points_come_from_official_marks():
    """评分点必须由官方条目的 M/A/B 分值派生，不能自创。"""
    with session_scope() as s:
        row = s.scalar(
            select(GeneratedExplanation)
            .where(GeneratedExplanation.marking_points != [])
            .limit(1)
        )
        if row is None:
            pytest.skip("没有带评分点的生成解析")
        entry = s.scalar(
            select(MarkSchemeEntry).where(MarkSchemeEntry.question_id == row.question_id)
        )
    kinds = {p["kind"] for p in row.marking_points}
    if entry is not None and entry.method_marks:
        assert "method" in kinds
    total = sum(p.get("marks") or 0 for p in row.marking_points)
    assert total > 0


def test_provider_and_model_are_honest():
    """provider/model 必须如实反映"这是规则式、没有模型参与"。"""
    with session_scope() as s:
        row = s.scalar(select(GeneratedExplanation).limit(1))
    if row is None:
        pytest.skip("尚未生成解析")
    assert row.provider == "rule-based"
    assert row.model is None, "没有模型参与就不能编一个模型名"
    assert row.prompt_version


# --------------------------------------------------------------------------
# 审核
# --------------------------------------------------------------------------


def test_review_transitions_and_stays_non_official():
    with session_scope() as s:
        row = s.scalar(select(GeneratedExplanation).limit(1))
        if row is None:
            pytest.skip("尚未生成解析")
        eid = row.id

    with session_scope() as s:
        result = review_explanation(s, eid, status="approved", author="tester")
        assert result["review_status"] == "approved"

    with session_scope() as s:
        row = s.get(GeneratedExplanation, eid)
        assert row.is_official is False, "审核通过也不改变'这是生成内容'的事实"
        # 复原
        row.review_status = "pending"


def test_review_rejects_invalid_status():
    with session_scope() as s:
        row = s.scalar(select(GeneratedExplanation).limit(1))
        if row is None:
            pytest.skip("尚未生成解析")
        with pytest.raises(ValueError):
            review_explanation(s, row.id, status="looks-good", author="t")


def test_review_unknown_id_raises():
    with session_scope() as s:
        with pytest.raises(ValueError):
            review_explanation(s, 10**9, status="approved", author="t")
